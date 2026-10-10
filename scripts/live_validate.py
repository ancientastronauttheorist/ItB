#!/usr/bin/env python3
"""Live validation of the C++ engine against the running game.

Session helper for engine/LIVE_TEST_PLAN.md. It only acts when you run one
of its commands; nothing here runs on import or in the background.

    python3 scripts/live_validate.py list
    python3 scripts/live_validate.py check                  # bridge smoke test + new fields
    python3 scripts/live_validate.py predict <scenario>     # offline: synthetic board -> engine
    python3 scripts/live_validate.py run <scenario>         # live: build, predict, act, capture, diff
    python3 scripts/live_validate.py diff <prediction.json> <state.json>
    python3 scripts/live_validate.py log [state.json]       # the phase log of a state/capture

`run <scenario>` (game at a player turn, debug flag file present):
  1. sends SCENARIO (engine/live_scenarios/<name>.json, placeholders
     resolved against the current board) and saves the bridge's snapshot;
  2. runs `itb_inspect --predict` on that snapshot with the scenario's
     actions, every hidden branch enumerated;
  3. sends the actions (MOVE_NATIVE / MOVE / ATTACK / FIRE);
  4. if the scenario ends the turn, asks you to click End Turn and waits for
     the bridge's enemy-phase captures (after the spawns, before the AI);
  5. diffs the game's board with each predicted outcome and saves
     everything under .local_runs/live_validation/<time>_<name>/.

Coordinates are the bridge's (x, y); boards print in A1-H8 notation too.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCENARIOS = REPO / "engine" / "live_scenarios"
INSPECT = REPO / "engine" / "build" / "itb_inspect"
RUNS = REPO / ".local_runs" / "live_validation"

BRIDGE = Path(os.environ.get("ITB_BRIDGE_DIR") or "/tmp")
STATE = BRIDGE / "itb_state.json"
CMD = BRIDGE / "itb_cmd.txt"
CMD_TMP = BRIDGE / "itb_cmd.txt.live_validate.tmp"
ACK = BRIDGE / "itb_ack.txt"
DEBUG_FLAG = BRIDGE / "itb_bridge_debug"
PRE_SPAWN = BRIDGE / "itb_state_enemy_prespawn.json"
POST_SPAWN = BRIDGE / "itb_state_enemy_postspawn.json"

# Fullscreen 1360x768 (first live session): tile (x, y) and End Turn.
END_TURN_SCREEN = (128, 89)


def tile_screen(x: int, y: int) -> tuple[int, int]:
    return 676 + 57 * (x - y), 117 + 41 * (x + y)


def visual(x: int, y: int) -> str:
    if not (0 <= x < 8 and 0 <= y < 8):
        return "--"
    return f"{chr(ord('H') - y)}{8 - x}"


def xy(p) -> str:
    return f"({p[0]},{p[1]}) {visual(p[0], p[1])}"


# ---------------------------------------------------------------- bridge IPC

_seq = int(time.time()) % 100000


def send(cmd: str, timeout: float = 60.0) -> str:
    """Writes one bridge command and returns its ack (without the #seq)."""
    global _seq
    _seq += 1
    try:
        ACK.unlink()
    except FileNotFoundError:
        pass
    CMD_TMP.write_text(f"#{_seq} {cmd}", encoding="utf-8")
    os.replace(CMD_TMP, CMD)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ACK.exists():
            text = ACK.read_text(encoding="utf-8").strip()
            if text.startswith("#"):
                seq, _, rest = text.partition(" ")
                if seq[1:] != str(_seq):
                    time.sleep(0.1)
                    continue
                text = rest
            return text
        time.sleep(0.1)
    raise TimeoutError(f"no ack for {cmd.split()[0]} within {timeout:.0f}s (is the game running a mission?)")


def read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fresh_state(after: float, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if STATE.stat().st_mtime >= after:
                return read_json(STATE)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(0.1)
    return read_json(STATE)


# ---------------------------------------------------------------- scenarios

def load_scenario(name: str) -> dict:
    path = SCENARIOS / (name if name.endswith(".json") else name + ".json")
    if not path.exists():
        sys.exit(f"no scenario {path}")
    return read_json(path)


def unit_tiles(state: dict) -> dict:
    """(x, y) -> unit for every unit entry (extra tiles included)."""
    return {(u["x"], u["y"]): u for u in state.get("units", [])}


def danger_tiles(state: dict) -> list:
    rows = state.get("environment_danger_v2") or [[p[0], p[1]] for p in state.get("environment_danger", [])]
    return [(r[0], r[1]) for r in rows]


class Resolver:
    """Replaces "at" placeholders with board coordinates:
    danger:N (the Nth environment mark, scan order), type:T (unit T's main
    tile), type:T:extra (its first extra tile), near:<placeholder> (the first
    free in-bounds neighbour that is not marked), free (a free plain tile).
    "dx"/"dy" offset the result."""

    def __init__(self, state: dict, spec: dict):
        self.state = state
        self.danger = danger_tiles(state)
        self.used = set()
        # Tiles the scenario itself fills.
        for ps in spec.get("pawns", []):
            if "x" in ps and "y" in ps:
                self.used.add((ps["x"], ps["y"]))

    def occupied(self, p) -> bool:
        if p in self.used:
            return True
        u = unit_tiles(self.state).get(p)
        return u is not None and u.get("hp", 1) > 0 and u.get("team") != 6

    def point(self, at: str):
        if at.startswith("danger:"):
            i = int(at.split(":")[1])
            if i >= len(self.danger):
                raise ValueError(f"{at}: only {len(self.danger)} environment marks on this board")
            return self.danger[i]
        if at.startswith("type:"):
            parts = at.split(":")
            want_extra = len(parts) > 2 and parts[2] == "extra"
            for u in self.state.get("units", []):
                if u.get("type") == parts[1] and bool(u.get("is_extra_tile")) == want_extra:
                    return (u["x"], u["y"])
            raise ValueError(f"{at}: no such unit on the board")
        if at.startswith("near:"):
            base = self.point(at[5:])
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p = (base[0] + d[0], base[1] + d[1])
                if 0 <= p[0] < 8 and 0 <= p[1] < 8 and p not in self.danger and not self.occupied(p):
                    return p
            raise ValueError(f"{at}: no free neighbour")
        if at == "free":
            for x in range(8):
                for y in range(8):
                    p = (x, y)
                    if p not in self.danger and not self.occupied(p) and 1 <= x <= 6 and 1 <= y <= 6:
                        return p
            raise ValueError("free: no free tile")
        raise ValueError(f"unknown placeholder {at}")

    def fix(self, obj: dict) -> dict:
        if "at" in obj:
            p = self.point(obj["at"])
            p = (p[0] + obj.get("dx", 0), p[1] + obj.get("dy", 0))
            obj = {k: v for k, v in obj.items() if k not in ("at", "dx", "dy")}
            obj["x"], obj["y"] = p
            self.used.add(p)
        return obj

    def resolve(self, spec: dict) -> dict:
        spec = copy.deepcopy(spec)
        for key in ("tiles", "tiles_after", "spawns"):
            spec[key] = [self.fix(t) for t in spec.get(key, [])]
        pawns = []
        for ps in spec.get("pawns", []):
            ps = self.fix(ps)
            if isinstance(ps.get("queue"), dict):
                ps["queue"] = self.fix(ps["queue"])
            pawns.append(ps)
        spec["pawns"] = pawns
        return spec


def pawn_uid(ref: str, spec: dict, created: dict) -> int:
    """uid:N -> N; pawn:I -> the uid of spec.pawns[I] (1-based)."""
    kind, _, val = ref.partition(":")
    if kind == "uid":
        return int(val)
    if kind == "pawn":
        i = int(val)
        ps = spec["pawns"][i - 1]
        if "uid" in ps:
            return ps["uid"]
        if "ref" in ps:
            return pawn_uid(f"pawn:{ps['ref']}", spec, created)
        if i not in created:
            raise ValueError(f"{ref}: the scenario did not create that pawn")
        return created[i]
    raise ValueError(f"bad pawn reference {ref}")


def engine_actions(scn: dict, spec: dict, created: dict) -> list:
    out = []
    for a in scn.get("actions", []):
        act = {"uid": pawn_uid(a["pawn"], spec, created)}
        if "move" in a:
            act["move"] = a["move"]
        if "weapon" in a:
            act["weapon"] = a["weapon"]
        elif "slot" in a:
            act["slot"] = a["slot"]
        if a.get("repair"):
            act["repair"] = True
        if "target" in a:
            act["target"] = a["target"]
        out.append(act)
    return out


def bridge_commands(scn: dict, spec: dict, created: dict) -> list:
    cmds = []
    for a in scn.get("actions", []):
        uid = pawn_uid(a["pawn"], spec, created)
        if "move" in a:
            x, y = a["move"]
            cmds.append(f"MOVE_NATIVE {uid} {x} {y}" if a.get("native") else f"MOVE {uid} {x} {y}")
        if "native_slot" in a:
            tx, ty = a["target"]
            cmds.append(f"FIRE {uid} {a['native_slot']} {tx} {ty}")
        elif "slot" in a:
            tx, ty = a["target"]
            cmds.append(f"ATTACK {uid} {a['slot']} {tx} {ty}")
        elif a.get("repair"):
            cmds.append(f"REPAIR {uid}")
    return cmds


def apply_overrides(state: dict, scn: dict, spec: dict, created: dict) -> dict:
    state = copy.deepcopy(state)
    for ref, fields in scn.get("engine_overrides", {}).items():
        uid = pawn_uid(ref, spec, created)
        for u in state.get("units", []):
            if u.get("uid") == uid:
                u.update(fields)
    return state


# ---------------------------------------------------------------- synthetic board

SYNTH_MECHS = [(0, "PunchMech", ["Prime_Punchmech"]), (1, "TankMech", ["Brute_Tankmech"]),
               (2, "ArtiMech", ["Ranged_Artillerymech"])]


def synth_state(scn: dict) -> tuple[dict, dict, dict]:
    """A bridge-format board built from the scenario alone (all ground, Rift
    Walkers squad), for offline predictions. Returns (state, spec, created)."""
    syn = scn.get("synth", {})
    base = {"tiles": [], "units": list(syn.get("units", [])),
            "environment_danger_v2": syn.get("environment_danger_v2", [])}
    spec = Resolver(base, scn["scenario"]).resolve(scn["scenario"])
    tiles = {}
    for x in range(8):
        for y in range(8):
            tiles[(x, y)] = {"x": x, "y": y, "terrain": "ground", "terrain_id": 0}
    names = {"ground": 0, "building": 1, "rubble": 2, "water": 3, "mountain": 4, "ice": 5,
             "forest": 6, "sand": 7, "chasm": 9}
    for t in spec.get("tiles", []) + spec.get("tiles_after", []):
        tl = tiles[(t["x"], t["y"])]
        if "terrain" in t:
            tl["terrain"] = t["terrain"]
            tl["terrain_id"] = 3 if t["terrain"] == "lava" else names[t["terrain"]]
            if t["terrain"] == "lava":
                tl["lava"] = True
        for k in ("fire", "smoke", "acid", "cracked", "frozen", "shield", "populated", "item"):
            if k in t:
                tl[k] = t[k]
        if "hp" in t:
            tl["ice_hp" if tl["terrain"] == "ice" else "building_hp"] = t["hp"]
    units = []
    placed = {}
    created = {}
    mech_type = {uid: (typ, w) for uid, typ, w in SYNTH_MECHS}
    for uid, typ, weapons in SYNTH_MECHS:
        units.append({"uid": uid, "type": typ, "x": 7 - uid, "y": 0, "team": 1, "mech": True,
                      "active": True, "weapons": weapons})
    units.extend(base["units"])
    for i, ps in enumerate(spec.get("pawns", []), start=1):
        if "ref" in ps:
            u = placed[ps["ref"]]
            if ps.get("readd"):
                units.remove(u)
                units.append(u)
            placed[i] = u
            continue
        if "uid" in ps:
            u = next((v for v in units if v["uid"] == ps["uid"] and not v.get("is_extra_tile")), None)
            if u is None:
                typ, w = mech_type.get(ps["uid"], ("PunchMech", ["Prime_Punchmech"]))
                u = {"uid": ps["uid"], "type": typ, "team": 1, "mech": True, "active": True, "weapons": w}
                units.append(u)
        else:
            uid = 100 + i
            created[i] = uid
            u = {"uid": uid, "type": ps["type"], "team": ps.get("team", 6), "active": True}
            units.append(u)
        if "x" in ps:
            u["x"], u["y"] = ps["x"], ps["y"]
        for k in ("hp", "fire", "acid", "shield", "frozen", "boosted", "injured"):
            if k in ps:
                u[k] = ps[k]
        placed[i] = u
    for i, ps in enumerate(spec.get("pawns", []), start=1):
        q = ps.get("queue")
        if isinstance(q, dict):
            u = placed[i]
            if u.get("team") == 6:
                u["has_queued_attack"] = True
                u["queued_target"] = [q["x"], q["y"]]
                u["queued_origin"] = [u["x"], u["y"]]
            else:
                u["queued_any"] = {"skill": q.get("slot", 1), "target": [q["x"], q["y"]],
                                   "origin": [u["x"], u["y"]]}
    spawns = spec.get("spawns", [])
    state = {
        "phase": "combat_player", "turn": syn.get("turn", 1), "total_turns": syn.get("total_turns", 5),
        "grid_power": 7, "grid_power_max": 7, "mission_id": syn.get("mission_id", "Mission_Survive"),
        "tiles": [tiles[(x, y)] for y in range(8) for x in range(8)],
        "units": units,
        "attack_order": [u["uid"] for u in units if u.get("team") == 6 and u.get("has_queued_attack")],
        "environment_danger_v2": base["environment_danger_v2"],
        "spawning_tiles": [[s["x"], s["y"]] for s in spawns],
        "spawn_queue": [{"type": s["type"], "x": s["x"], "y": s["y"]} for s in spawns],
        "spawn_queue_matches_markers": True,
    }
    state = apply_overrides(state, scn, spec, created)
    return state, spec, created


# ---------------------------------------------------------------- engine

def run_engine(state_path: Path, actions: list, out_dir: Path, enemy: bool) -> tuple[str, dict | None]:
    if not INSPECT.exists():
        return f"(no {INSPECT}: build the engine first)", None
    actions_path = out_dir / "actions.json"
    actions_path.write_text(json.dumps(actions, indent=1))
    pred_path = out_dir / "prediction.json"
    cmd = [str(INSPECT), "--predict", str(state_path), "--actions", "@" + str(actions_path),
           "--branches", "--json", str(pred_path)]
    if not enemy:
        cmd.append("--no-enemy")
    res = subprocess.run(cmd, capture_output=True, text=True)
    text = res.stdout + (("\n" + res.stderr) if res.stderr else "")
    (out_dir / "prediction.txt").write_text(text)
    pred = read_json(pred_path) if pred_path.exists() else None
    return text, pred


# ---------------------------------------------------------------- diff

UNIT_FIELDS = ("x", "y", "hp", "fire", "acid", "shield", "frozen")
TILE_FIELDS = ("terrain", "building_hp", "fire", "smoke", "acid", "cracked")


def compare(engine_board: dict, game: dict) -> list:
    """Differences between an engine outcome board and a bridge state."""
    diffs = []
    game_units = {u["uid"]: u for u in game.get("units", []) if not u.get("is_extra_tile")}
    for e in engine_board["units"]:
        g = game_units.get(e["uid"])
        label = f"{e['type']}#{e['uid']}"
        if not e["alive"]:
            if g is not None and g.get("hp", 1) > 0:
                diffs.append(f"{label}: engine dead, game alive at {xy((g['x'], g['y']))} hp {g['hp']}")
            continue
        if g is None or g.get("hp", 1) <= 0:
            diffs.append(f"{label}: engine alive at {xy((e['x'], e['y']))} hp {e['hp']}, game dead/gone")
            continue
        for f in UNIT_FIELDS:
            ev, gv = e.get(f), g.get(f)
            if f in ("fire", "acid", "shield", "frozen"):
                ev, gv = bool(ev), bool(gv)
            if ev != gv:
                diffs.append(f"{label} {f}: engine {ev}, game {gv}")
    engine_uids = {e["uid"] for e in engine_board["units"]}
    for uid, g in game_units.items():
        if uid not in engine_uids and g.get("hp", 1) > 0:
            match = [e for e in engine_board["units"] if e["alive"] and (e["x"], e["y"]) == (g["x"], g["y"])
                     and e["type"] == g["type"]]
            if not match:
                diffs.append(f"game has {g['type']}#{uid} at {xy((g['x'], g['y']))}, engine none there")
    game_tiles = {(t["x"], t["y"]): t for t in game.get("tiles", [])}
    for e in engine_board["tiles"]:
        g = game_tiles.get((e["x"], e["y"]))
        if g is None:
            continue
        for f in TILE_FIELDS:
            ev, gv = e.get(f), g.get(f)
            if f in ("fire", "smoke", "acid", "cracked"):
                ev, gv = bool(ev), bool(gv)
            if f == "building_hp" and g.get("terrain") not in ("building", "mountain"):
                continue
            if ev != gv:
                diffs.append(f"tile {xy((e['x'], e['y']))} {f}: engine {ev}, game {gv}")
    return diffs


def report_diff(pred: dict, game: dict, label: str) -> str:
    lines = [f"== engine vs game ({label})"]
    best = None
    for i, o in enumerate(pred["outcomes"]):
        d = compare(o["board"], game)
        choices = " ".join(f"{c['kind']} {c['pick'] + 1}/{c['options']}" for c in o["choices"]) or "-"
        lines.append(f"  outcome {i + 1} [{choices}]: {len(d)} difference(s)")
        if best is None or len(d) < len(best[1]):
            best = (i, d)
    if best is not None:
        lines.append(f"  closest: outcome {best[0] + 1}")
        lines += [f"    {d}" for d in best[1]] or ["    (identical on the compared fields)"]
    lines.append("  note: grid_power in enemy-phase captures is the save's turn-start value; "
                 "compare building HP here and grid on the next player turn.")
    return "\n".join(lines)


def phase_log_summary(state: dict, turn: int | None = None) -> str:
    log = state.get("phase_log") or {}
    entries = log.get("entries", [])
    lines = []
    for e in entries:
        if turn is not None and e.get("turn") != turn:
            continue
        k = e.get("kind")
        if k in ("selected", "env_step", "base_next_turn", "plan_environment", "scenario", "appeared", "gone"):
            extra = ""
            if k == "env_step":
                extra = f" strike {e.get('current_attack')}"
            elif k in ("selected", "appeared"):
                extra = f" {e.get('type')}#{e.get('uid')}"
            elif k == "gone":
                extra = f" #{e.get('uid')}"
            lines.append(f"  frame {e.get('frame')} team {e.get('team')}: {k}{extra}")
        elif k == "hp":
            lines.append(f"  frame {e.get('frame')} team {e.get('team')}: hp #{e['uid']} {e['from']} -> {e['to']}"
                         f" at {xy((e['x'], e['y']))}")
        elif k == "tile":
            lines.append(f"  frame {e.get('frame')} team {e.get('team')}: tile {xy((e['x'], e['y']))}"
                         f" {e['from']} -> {e['to']}")
        elif k == "busy":
            lines.append(f"  frame {e.get('frame')}: busy {e.get('from')} -> {e.get('to')}")
    strikes = state.get("env_strike_log") or []
    if strikes:
        lines.append("  env_strike_log: " + "; ".join(f"turn {s.get('turn')} {s.get('current_attack')}"
                                                       for s in strikes))
    return "\n".join(lines) if lines else "  (no phase log: is the debug flag file there?)"


# ---------------------------------------------------------------- commands

def cmd_list(_args) -> None:
    for path in sorted(SCENARIOS.glob("*.json")):
        scn = read_json(path)
        print(f"{path.stem:22} {scn.get('question', '')}")
        print(f"{'':22} mission: {scn.get('mission', 'any')}")


def cmd_check(_args) -> None:
    print("debug flag:", "present" if DEBUG_FLAG.exists() else f"MISSING (touch {DEBUG_FLAG})")
    t0 = time.time()
    try:
        print("DEBUG_STATUS:", send("DEBUG_STATUS", 15))
        print("SNAPSHOT:", send("SNAPSHOT check", 15))
    except TimeoutError as e:
        print("bridge:", e)
        return
    st = fresh_state(t0)
    print(f"phase {st.get('phase')} turn {st.get('turn')} mission {st.get('mission_id')} "
          f"env_class {st.get('env_class')} env_type {st.get('env_type')}")
    print("bridge_ext_version:", st.get("bridge_ext_version"), " bridge_errors:", st.get("bridge_errors"))
    ms = st.get("mission_state") or {}
    print(f"mission_state: key {ms.get('key')} {ms.get('native_key')} classes {ms.get('class_chain')} "
          f"env {ms.get('env_class_chain')} turn_limit {ms.get('turn_limit')} truncated {ms.get('dump_truncated')}")
    print(f"save_source {st.get('save_source')}  power_start {st.get('mission_power_start')}  "
          f"blocked_spawns {st.get('mission_blocked_spawns')}  bonus {st.get('bonus_objective_ids')}")
    print(f"spawn_queue ({st.get('spawn_queue_source')}, matches markers: {st.get('spawn_queue_matches_markers')}):",
          [(s.get('type'), xy((s.get('x'), s.get('y')))) for s in st.get("spawn_queue", [])])
    print("attack_order:", st.get("attack_order"), " attack_order_all:", st.get("attack_order_all"))
    if st.get("deploying") or st.get("turn") == 0:
        print(f"drop_zone ({st.get('drop_zone_source')}):", [visual(*p) for p in st.get("drop_zone", [])])
        print("deployment_zone:", [visual(*p) for p in st.get("deployment_zone", [])])
    print("zones:", {k: len(v) for k, v in (st.get("zones") or {}).items()})
    for u in st.get("units", []):
        if u.get("team") != 1 or u.get("is_extra_tile"):
            continue
        slots = ", ".join(
            f"{s.get('id')}{'' if s.get('powered', True) else ' (unpowered)'}"
            + (f" uses {s.get('uses')}/{s.get('limited')} ({s.get('uses_basis', 'saved')})" if s.get("limited") else "")
            for s in u.get("weapon_slots", []))
        p = u.get("pilot") or {}
        print(f"  {u['type']}#{u['uid']} {xy((u['x'], u['y']))} hp {u['hp']}/{u.get('max_hp')} active {u.get('active')} "
              f"moved {u.get('moved')} ({u.get('moved_source')}) shots {u.get('shots_remaining')}")
        print(f"      weapons: {slots or u.get('weapons')}")
        if p:
            print(f"      pilot {p.get('id')} level {p.get('level')} xp {p.get('xp')} skills {p.get('skill1')}/{p.get('skill2')}")
        if u.get("queued_any"):
            print(f"      queued (non-enemy): {u['queued_any']}")
    print("\nCompare by eye: weapon names and upgrades with the mech panels, pilot XP bars,\n"
          "spawn markers, the drop zone during deployment.")


def cmd_predict(args) -> None:
    scn = load_scenario(args.scenario)
    state, spec, created = synth_state(scn)
    out_dir = RUNS / f"{time.strftime('%Y%m%d_%H%M%S')}_{scn['name']}_offline"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "synthetic_state.json").write_text(json.dumps(state, indent=1))
    text, _ = run_engine(out_dir / "synthetic_state.json", engine_actions(scn, spec, created), out_dir,
                         scn.get("end_turn", False))
    print(text)
    print(f"(synthetic board: all ground, Rift Walkers at (7,0)/(6,0)/(5,0) unless placed; {out_dir})")


def wait_for_capture(t0: float, timeout: float) -> tuple[str, dict] | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for path, label in ((POST_SPAWN, "after the spawns, before the AI"),):
            try:
                if path.stat().st_mtime >= t0:
                    time.sleep(0.3)
                    return label, read_json(path)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        time.sleep(0.25)
    try:
        if PRE_SPAWN.stat().st_mtime >= t0:
            return "after the Vek and environment, before the spawns", read_json(PRE_SPAWN)
    except FileNotFoundError:
        pass
    return None


def cmd_run(args) -> None:
    scn = load_scenario(args.scenario)
    if not DEBUG_FLAG.exists():
        sys.exit(f"debug flag missing: touch {DEBUG_FLAG}, then rerun")
    out_dir = RUNS / f"{time.strftime('%Y%m%d_%H%M%S')}_{scn['name']}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"== {scn['name']}: {scn.get('question', '')}\n   mission: {scn.get('mission', 'any')}")
    t0 = time.time()
    send("SNAPSHOT before_scenario", 15)
    current = fresh_state(t0)
    if current.get("phase") != "combat_player":
        sys.exit(f"not a player turn (phase {current.get('phase')})")
    if danger_tiles(current) and "danger:" not in json.dumps(scn["scenario"]):
        print("warning: this board has environment marks; they will strike the scenario board too")
    spec = Resolver(current, scn["scenario"]).resolve(scn["scenario"])
    spec_path = out_dir / "scenario.json"
    spec_path.write_text(json.dumps(spec, indent=1))
    if args.speed:
        print("SET_SPEED:", send(f"SET_SPEED {args.speed}", 15))
    ack = send(f"SCENARIO @{spec_path}", 120)
    if not ack.startswith("OK SCENARIO"):
        sys.exit(f"SCENARIO failed: {ack}")
    report = json.loads(ack[len("OK SCENARIO "):])
    (out_dir / "scenario_report.json").write_text(json.dumps(report, indent=1))
    if report.get("errors"):
        print("SCENARIO errors:\n  " + "\n  ".join(report["errors"]))
    created = {c["index"]: c["uid"] for c in report.get("created", [])}
    before = read_json(Path(report["snapshot"]))
    before = apply_overrides(before, scn, spec, created)
    before_path = out_dir / "before.json"
    before_path.write_text(json.dumps(before, indent=1))
    print("board set up; attack_order", before.get("attack_order"), "spawn_queue",
          [(s["type"], xy((s["x"], s["y"]))) for s in before.get("spawn_queue", [])])

    text, pred = run_engine(before_path, engine_actions(scn, spec, created), out_dir, scn.get("end_turn", False))
    print("\n" + text)

    t_actions = time.time()
    for c in bridge_commands(scn, spec, created):
        print(c, "->", send(c, 60))
    if scn.get("end_turn"):
        for p in (PRE_SPAWN, POST_SPAWN):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        t_click = time.time()
        print(f"\n>>> Click End Turn now (fullscreen 1360x768: {END_TURN_SCREEN}). Waiting for the enemy phase...")
        cap = wait_for_capture(t_click, args.timeout)
        if cap is None:
            sys.exit("no enemy-phase capture: was End Turn clicked, and is the debug flag there?")
        label, game = cap
        shutil.copy(POST_SPAWN if POST_SPAWN.exists() else PRE_SPAWN, out_dir / "game_capture.json")
        if PRE_SPAWN.exists():
            shutil.copy(PRE_SPAWN, out_dir / "game_prespawn.json")
    else:
        label = "after the actions"
        send("SNAPSHOT after_actions", 30)
        game = fresh_state(t_actions)
        (out_dir / "game_capture.json").write_text(json.dumps(game, indent=1))
    if pred:
        diff = report_diff(pred, game, label)
        print("\n" + diff)
        (out_dir / "diff.txt").write_text(diff)
    log = phase_log_summary(game, before.get("turn"))
    print("\n== game phase log (this turn)\n" + log)
    (out_dir / "phase_log.txt").write_text(log)
    print("\nobserve:\n  - " + "\n  - ".join(scn.get("observe", [])))
    print(f"\nsaved in {out_dir}")


def cmd_diff(args) -> None:
    print(report_diff(read_json(Path(args.prediction)), read_json(Path(args.state)), args.state))


def cmd_log(args) -> None:
    st = read_json(Path(args.state)) if args.state else read_json(STATE)
    print(phase_log_summary(st))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("list").set_defaults(func=cmd_list)
    sub.add_parser("check").set_defaults(func=cmd_check)
    p = sub.add_parser("predict")
    p.add_argument("scenario")
    p.set_defaults(func=cmd_predict)
    p = sub.add_parser("run")
    p.add_argument("scenario")
    p.add_argument("--speed", choices=["fast", "visual"], help="SET_SPEED before the scenario")
    p.add_argument("--timeout", type=float, default=180.0, help="seconds to wait for the enemy phase")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("diff")
    p.add_argument("prediction")
    p.add_argument("state")
    p.set_defaults(func=cmd_diff)
    p = sub.add_parser("log")
    p.add_argument("state", nargs="?")
    p.set_defaults(func=cmd_log)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
