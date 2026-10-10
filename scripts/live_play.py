#!/usr/bin/env python3
"""Play Into the Breach live with the C++ engine (engine/build/itb_live).

Nothing runs on import; every command checks the bridge first (fresh
heartbeat, a readable state, `bridge_ext_disabled` unset) and refuses to act
otherwise.

    python3 scripts/live_play.py status
    python3 scripts/live_play.py deploy [--tiles C5,D6,E5] [--dry-run]
    python3 scripts/live_play.py turn [--time 10] [--threads 8] [--dry-run]
    python3 scripts/live_play.py end-turn
    python3 scripts/live_play.py mission [--max-turns 8]

turn: solve the live board, then execute the plan one sub-action at a time
(MOVE_NATIVE, falling back to MOVE; ATTACK / TWO_CLICK_ATTACK with the
weapon's slot; REPAIR) and after each one compare the live board with the
engine's prediction (units by uid: type, tile, HP, statuses; building HP;
never the save-based grid_power, which is stale mid-turn). A mismatch
re-solves from the live board. Does not end the turn.

end-turn: predicts the enemy phase from the board as it is, sends the bridge
END_TURN (it deactivates every mech, so no "units can still act" dialog),
clicks End Turn only if the bridge cannot end the turn itself, checks the
phase really changed, waits for the next player turn and compares grid, HP,
statuses, survivors and mech tiles with the prediction (Vek tiles are not
compared: the Vek move while the AI plans). New units are reported as spawns.

mission: turn + end-turn until the mission ends; stops at the first anomaly
(a step mismatch, a bridge error, an enemy-phase difference, a refused plan)
without ending the turn, so the board can be inspected.

deploy: places the mechs on the bridge's exported drop zone (tiles the deploy
UI refuses are not in it, and DEPLOY refuses them anyway) with a simple
heuristic, or on --tiles; verifies every mech's tile from the state. Confirm
the deployment in the game afterwards.

Every bridge state and engine prediction is archived under
recordings/live/<run>/ (git-ignored; force-add a run to keep it): the
turn-start board as m<MM>_turn_<TT>_solve_input.json, the executed plan as
m<MM>_turn_<TT>_solve.json (both in the old recordings' format, so
itb_inspect --corpus/--solve/--moves read them), every other state as
m<MM>_turn_<TT>_<label>_<NN>.json and each prediction beside it as
..._prediction.json. events.jsonl logs every command and ack.

Coordinates are the bridge's (x, y); the console prints A1-H8 as well.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_validate as lv  # noqa: E402  (bridge IPC; import-safe)

ITB_LIVE = REPO / "engine" / "build" / "itb_live"
LIVE_ROOT = REPO / "recordings" / "live"
CURRENT = REPO / ".local_runs" / "live_play" / "current.json"

HEARTBEAT = lv.BRIDGE / "itb_bridge_heartbeat"

# Timings (seconds). Tests shrink them.
SETTLE_INTERVAL = 0.4
SETTLE_TRIES = 8
POLL = 0.5
ACTION_TIMEOUT = 60.0

STEP_FIELDS = ("fire", "acid", "frozen", "shield", "web")
# Webs are released at End Turn and re-applied while the AI plans, after the
# point the engine predicts: not compared after the enemy phase.
ENEMY_FIELDS = ("fire", "acid", "frozen", "shield")


class Refused(Exception):
    """A safety check failed: nothing was sent to the game."""


class Anomaly(Exception):
    """Something the engine did not predict, or the bridge failed."""


def visual(x, y) -> str:
    return lv.visual(x, y)


def now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="milliseconds")


def say(msg: str = "") -> None:
    print(msg, flush=True)


# ------------------------------------------------------------------ bridge

class Bridge:
    """The Lua bridge in lv.BRIDGE (ITB_BRIDGE_DIR, default /tmp)."""

    def __init__(self, log=None):
        self.log = log or (lambda *_: None)

    def raw_state(self) -> dict | None:
        try:
            return lv.read_json(lv.STATE)
        except (OSError, json.JSONDecodeError):
            return None

    def heartbeat_age(self) -> float | None:
        try:
            return time.time() - HEARTBEAT.stat().st_mtime
        except OSError:
            return None

    def send(self, cmd: str, timeout: float = ACTION_TIMEOUT) -> str:
        self.log("cmd", cmd)
        try:
            ack = lv.send(cmd, timeout)
        except TimeoutError as e:
            self.log("ack", f"TIMEOUT {e}")
            raise Anomaly(f"{cmd.split()[0]}: {e}") from e
        self.log("ack", ack)
        return ack

    def fresh_state(self) -> dict:
        """A dump taken now: SNAPSHOT (the ack follows the dump), or on old
        bridges a no-op command and the next state file."""
        ack = self.send("SNAPSHOT live_play", 15)
        if ack.startswith("OK SNAPSHOT "):
            try:
                return lv.read_json(Path(ack[len("OK SNAPSHOT "):].strip()))
            except (OSError, json.JSONDecodeError):
                pass
        t0 = time.time()
        self.send("LUA return 'refresh'", 15)
        return lv.fresh_state(t0)

    def settled_state(self) -> dict:
        """A dump taken while the board is idle. Bridges that report
        `stable` say so directly; for older ones, wait until two dumps in a
        row agree (reads taken mid-animation showed stale unit tiles)."""
        prev = self.fresh_state()
        if prev.get("stable") is True:
            return prev
        for _ in range(SETTLE_TRIES):
            time.sleep(SETTLE_INTERVAL)
            cur = self.fresh_state()
            if cur.get("stable") is True:
                return cur
            if signature(cur) == signature(prev):
                return cur
            prev = cur
        raise Anomaly("the board did not settle (still animating?)")


def units(state: dict) -> list:
    return [u for u in state.get("units", []) if not u.get("is_extra_tile")]


def signature(state: dict):
    us = tuple(sorted((u.get("uid"), u.get("x"), u.get("y"), u.get("hp"), bool(u.get("active")))
                      + tuple(bool(u.get(f)) for f in STEP_FIELDS) for u in units(state)))
    ts = tuple(sorted((t.get("x"), t.get("y"), t.get("terrain"), t.get("building_hp"))
                      for t in state.get("tiles", [])))
    return state.get("phase"), state.get("turn"), us, ts


def active_mechs(state: dict) -> list:
    return [u for u in units(state) if u.get("team") == 1 and u.get("active") and (u.get("hp") or 0) > 0]


def in_combat(state: dict) -> bool:
    return state.get("phase") in ("combat_player", "combat_enemy") and state.get("in_active_mission", True)


def preflight(bridge: Bridge, args) -> dict:
    """Refuses (raises Refused) unless the bridge is alive and usable."""
    age = bridge.heartbeat_age()
    if age is None:
        raise Refused(f"no bridge heartbeat ({HEARTBEAT}): is the game running with the bridge installed?")
    if age > args.max_heartbeat_age:
        raise Refused(f"bridge heartbeat is {age:.0f}s old (limit {args.max_heartbeat_age:.0f}s): "
                      "game paused, in a menu, or the bridge stopped")
    state = bridge.raw_state()
    if state is None:
        raise Refused(f"no readable bridge state at {lv.STATE}")
    if state.get("bridge_ext_disabled"):
        raise Refused(f"bridge_ext_disabled is set ({state['bridge_ext_disabled']}): the extension "
                      "(exact weapons, moved flags, drop zone) is off. Restart the game to re-enable it.")
    return state


# ------------------------------------------------------------------ engine

class Engine:
    """engine/build/itb_live serve: loads the engines once per session."""

    def __init__(self, threads: int, game: str | None = None, log_path: Path | None = None):
        self.threads = threads
        self.game = game
        self.log_path = log_path
        self.proc = None

    def _start(self) -> None:
        if not ITB_LIVE.exists():
            raise Refused(f"{ITB_LIVE} not built: cmake --build engine/build")
        cmd = [str(ITB_LIVE)] + (["--game", self.game] if self.game else []) + \
              ["serve", "--threads", str(self.threads)]
        err = open(self.log_path, "a") if self.log_path else subprocess.DEVNULL
        say(f"loading the engine ({self.threads} thread(s))...")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
                                     text=True, bufsize=1)
        ready = self._read()
        if not ready.get("ready"):
            raise Refused(f"itb_live did not start: {ready.get('error', ready)}")

    def _read(self) -> dict:
        line = self.proc.stdout.readline()
        if not line:
            raise Anomaly("itb_live exited (see itb_live.log in the run directory)")
        return json.loads(line)

    def request(self, req: dict) -> dict:
        if self.proc is None:
            self._start()
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        reply = self._read()
        if not reply.get("ok"):
            raise Anomaly(f"itb_live {req.get('cmd')}: {reply.get('error')}")
        return reply

    def solve(self, path: Path, time_limit: float) -> dict:
        return self.request({"cmd": "solve", "state": str(path), "time_limit": time_limit,
                             "threads": self.threads})

    def predict(self, path: Path, plan: list) -> dict:
        return self.request({"cmd": "predict", "state": str(path), "plan": plan})

    def board(self, path: Path) -> dict:
        return self.request({"cmd": "board", "state": str(path)})["board"]

    def close(self) -> None:
        if self.proc is not None:
            try:
                self.proc.stdin.write('{"cmd": "quit"}\n')
                self.proc.stdin.flush()
                self.proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()
            self.proc = None


# ------------------------------------------------------------------ run directory

class Run:
    """recordings/live/<run>/: every state and prediction of a session."""

    def __init__(self, path: Path, meta: dict):
        self.path = path
        self.meta = meta  # {"missions": [[mission_id, last_turn], ...]}
        path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def open(cls, run: str | None, new: bool) -> "Run":
        if run:
            path = Path(run) if os.path.isabs(run) else LIVE_ROOT / run
            meta = cls._read_meta(path)
        elif not new and CURRENT.exists():
            try:
                cur = json.loads(CURRENT.read_text())
                path = Path(cur["run"])
                meta = cls._read_meta(path)
            except (OSError, ValueError, KeyError):
                path, meta = cls._new_path(), {}
        else:
            path, meta = cls._new_path(), {}
        r = cls(path, meta)
        r.save_meta()
        return r

    @staticmethod
    def _new_path() -> Path:
        return LIVE_ROOT / time.strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def _read_meta(path: Path) -> dict:
        try:
            return json.loads((path / "manifest.json").read_text())
        except (OSError, ValueError):
            return {}

    def save_meta(self) -> None:
        self.meta.setdefault("tool", "scripts/live_play.py")
        self.meta.setdefault("created", now_iso())
        (self.path / "manifest.json").write_text(json.dumps(self.meta, indent=1))
        CURRENT.parent.mkdir(parents=True, exist_ok=True)
        CURRENT.write_text(json.dumps({"run": str(self.path)}))

    def mission_index(self, state: dict) -> int:
        """Index of the state's mission; a new mission when the id changes or
        the turn goes back."""
        missions = self.meta.setdefault("missions", [])
        mid, turn = state.get("mission_id") or "unknown", int(state.get("turn") or 0)
        if missions and missions[-1][0] == mid and turn >= missions[-1][1]:
            missions[-1][1] = turn
        elif not missions or missions[-1][0] != mid or turn < missions[-1][1]:
            missions.append([mid, turn])
        self.save_meta()
        return len(missions) - 1

    def prefix(self, state: dict) -> str:
        return f"m{self.mission_index(state):02d}_turn_{int(state.get('turn') or 0):02d}"

    def wrap(self, state: dict, label: str, extra: dict | None = None) -> dict:
        data = {"source": "live_play", "bridge_state": state}
        data.update(extra or {})
        return {"timestamp": now_iso(), "run_id": self.path.name,
                "mission_index": self.mission_index(state), "turn": int(state.get("turn") or 0),
                "label": label, "data": data}

    def save_state(self, state: dict, label: str, extra: dict | None = None) -> Path:
        """Archives a bridge state; the first turn-start state of a turn is
        that turn's solve_input."""
        pre = self.prefix(state)
        if label == "start" and not (self.path / f"{pre}_solve_input.json").exists():
            path = self.path / f"{pre}_solve_input.json"
            label = "solve_input"
        else:
            n = 1
            while (self.path / f"{pre}_{label}_{n:02d}.json").exists():
                n += 1
            path = self.path / f"{pre}_{label}_{n:02d}.json"
        path.write_text(json.dumps(self.wrap(state, label, extra)))
        return path

    def save_json(self, name: str, obj) -> Path:
        path = self.path / name
        path.write_text(json.dumps(obj, indent=1))
        return path

    def event(self, kind: str, detail) -> None:
        with open(self.path / "events.jsonl", "a") as f:
            f.write(json.dumps({"t": now_iso(), "kind": kind, "detail": detail}) + "\n")


def prediction_path(state_path: Path) -> Path:
    return state_path.with_name(state_path.stem + "_prediction.json")


# ------------------------------------------------------------------ comparing

def describe_unit(u: dict) -> str:
    return f"{u['type']}#{u['uid']}"


def diff_boards(want: dict, got: dict, known: set, *, enemy_phase: bool = False,
                acid_pools: frozenset = frozenset()) -> tuple[list, list]:
    """Differences between a predicted and a live compact board (itb_live's
    live_board_json). Returns (differences, notes). Units in `known` (the
    turn-start uids) are matched by uid; others by type/tile/HP (the engine
    numbers the units it creates itself). After the enemy phase only mech
    tiles are compared, and new units are notes (spawns), not differences.
    `acid_pools` are the pool tiles before the enemy phase: a Vek that moves
    onto one while planning next turn (the AI move the engine doesn't model)
    picks up ACID, which is a note, not a difference."""
    diffs, notes = [], []
    fields = ENEMY_FIELDS if enemy_phase else STEP_FIELDS
    w = {u["uid"]: u for u in want["units"]}
    g = {u["uid"]: u for u in got["units"]}
    for uid in sorted(known):
        a, b = w.get(uid), g.get(uid)
        if a is None and b is None:
            continue
        if a is None:
            diffs.append(f"{describe_unit(b)}: engine dead, game alive at {visual(b['x'], b['y'])} hp {b['hp']}")
            continue
        if b is None:
            diffs.append(f"{describe_unit(a)}: engine alive at {visual(a['x'], a['y'])} hp {a['hp']}, game dead")
            continue
        who = describe_unit(a)
        if a["type"] != b["type"]:
            diffs.append(f"{who}: engine {a['type']}, game {b['type']}")
        if (a["x"], a["y"]) != (b["x"], b["y"]) and (not enemy_phase or a.get("mech")):
            diffs.append(f"{who}: engine at {visual(a['x'], a['y'])}, game at {visual(b['x'], b['y'])}")
        if a["hp"] != b["hp"]:
            diffs.append(f"{who} hp: engine {a['hp']}, game {b['hp']}")
        for f in fields:
            if bool(a.get(f)) != bool(b.get(f)):
                moved = (a["x"], a["y"]) != (b["x"], b["y"])
                if (enemy_phase and f == "acid" and b.get(f) and not a.get("mech") and moved
                        and (b["x"], b["y"]) in acid_pools):
                    notes.append(f"{who} picked up the acid pool at {visual(b['x'], b['y'])} "
                                 "moving during AI planning")
                    continue
                diffs.append(f"{who} {f}: engine {bool(a.get(f))}, game {bool(b.get(f))}")
    key = (lambda u: (u["type"], u["hp"])) if enemy_phase else \
        (lambda u: (u["type"], u["x"], u["y"], u["hp"]) + tuple(bool(u.get(f)) for f in fields))
    new_w = Counter(key(u) for u in want["units"] if u["uid"] not in known)
    new_g = Counter(key(u) for u in got["units"] if u["uid"] not in known)
    for k, n in (new_w - new_g).items():
        line = f"engine has {n} new {k[0]} ({_key_text(k, enemy_phase)}) the game does not"
        (notes if enemy_phase else diffs).append(line)
    for k, n in (new_g - new_w).items():
        line = f"game has {n} new {k[0]} ({_key_text(k, enemy_phase)})"
        (notes if enemy_phase else diffs).append(line)
    wb = {(b["x"], b["y"]): b["hp"] for b in want["buildings"]}
    gb = {(b["x"], b["y"]): b["hp"] for b in got["buildings"]}
    for xy in sorted(set(wb) | set(gb)):
        if wb.get(xy) != gb.get(xy):
            diffs.append(f"building {visual(*xy)} hp: engine {wb.get(xy, 'gone')}, game {gb.get(xy, 'gone')}")
    if enemy_phase and want.get("grid_power") != got.get("grid_power"):
        diffs.append(f"grid: engine {want.get('grid_power')}, game {got.get('grid_power')}")
    return diffs, notes


def _key_text(k, enemy_phase: bool) -> str:
    return f"hp {k[1]}" if enemy_phase else f"at {visual(k[1], k[2])} hp {k[3]}"


# ------------------------------------------------------------------ executing

def load_loadout(path: str | None) -> dict:
    if not path:
        return {}
    with open(path) as f:
        return json.load(f)


def patch_state(state: dict, loadout: dict, moved: set) -> tuple[dict, dict]:
    """The solver's input: the live state, plus --loadout weapons for units
    the bridge gives no exact ids, plus moved flags the bridge does not
    export. Returns (state, patches)."""
    out = json.loads(json.dumps(state))
    patches = {}
    for u in units(out):
        if u.get("team") != 1:
            continue
        if u.get("type") in loadout and not u.get("weapons_exact"):
            u["weapons_exact"] = list(loadout[u["type"]])
            patches[f"{u['uid']}.weapons_exact"] = u["weapons_exact"]
        if u["uid"] in moved and "moved" not in u:
            u["moved"] = True
            patches[f"{u['uid']}.moved"] = True
    return out, patches


def check_loadout(state: dict, loadout: dict) -> None:
    missing = [describe_unit(u) for u in units(state)
               if u.get("team") == 1 and u.get("mech") and (u.get("hp") or 0) > 0
               and not u.get("weapons_exact") and u.get("type") not in loadout]
    if missing:
        raise Refused("the bridge does not export exact weapon ids (weapons_exact) for "
                      + ", ".join(missing) + ": update the bridge (scripts/install_modloader.sh) "
                      "or pass --loadout FILE ({\"<mech type>\": [\"<weapon id>\", ...]})")


def weapon_slot(state: dict, uid: int, weapon: str, loadout: dict) -> int:
    """The bridge ATTACK slot (0 = primary, 1 = secondary) of `weapon`."""
    unit = next((u for u in units(state) if u["uid"] == uid), None)
    if unit is None:
        raise Anomaly(f"unit {uid} is not on the board")
    for s in unit.get("weapon_slots") or []:
        if s.get("id") == weapon and isinstance(s.get("slot"), int):
            return s["slot"]
    for listed in (loadout.get(unit.get("type")), unit.get("weapons_exact"), unit.get("weapons")):
        if listed and weapon in listed:
            return listed.index(weapon)
    raise Anomaly(f"{describe_unit(unit)} has no weapon {weapon} (bridge: "
                  f"{unit.get('weapons_exact') or unit.get('weapons')})")


def step_text(step: dict, names: dict) -> str:
    who = f"{names.get(step['uid'], 'unit')}#{step['uid']}"
    if step["sub"] == "move":
        return f"{who} move to {visual(*step['to'])}"
    if step["sub"] == "repair":
        return f"{who} repair"
    t = step["target"]
    text = f"{who} {step['weapon']} at {visual(*t)}"
    if step.get("target2"):
        text += f" then {visual(*step['target2'])}"
    return text


def execute_step(bridge: Bridge, step: dict, state: dict, loadout: dict) -> str:
    uid = step["uid"]
    if step["sub"] == "move":
        x, y = step["to"]
        ack = bridge.send(f"MOVE_NATIVE {uid} {x} {y}")
        if not ack.startswith("OK"):
            say(f"    MOVE_NATIVE failed ({ack}); using MOVE")
            ack = bridge.send(f"MOVE {uid} {x} {y}")
        elif "[SetSpace]" in ack:
            say("    note: MOVE_NATIVE fell back to SetSpace (arrival effects skipped)")
    elif step["sub"] == "weapon":
        slot = weapon_slot(state, uid, step["weapon"], loadout)
        tx, ty = step["target"]
        if step.get("target2"):
            x2, y2 = step["target2"]
            ack = bridge.send(f"TWO_CLICK_ATTACK {uid} {slot} {tx} {ty} {x2} {y2}")
        else:
            ack = bridge.send(f"ATTACK {uid} {slot} {tx} {ty}")
    else:
        ack = bridge.send(f"REPAIR {uid}")
    if not ack.startswith("OK"):
        raise Anomaly(f"bridge refused {step['sub']}: {ack}")
    return ack


def plan_summary(pred: dict) -> str:
    if not pred.get("searched", True):
        return "no active unit (nothing to solve)"
    wc = pred.get("worst_case") or {}
    tiers = " ".join(f"{k}={wc[k]}" for k in ("grid", "building_hp", "mechs", "mech_hp", "objectives_failed",
                                                 "objectives", "kills", "vek_hp", "position") if k in wc)
    proof = "proven optimal" if pred.get("proven_optimal") else \
        f"best found, optimal in the first {pred.get('proven_components', 0)} tiers"
    secs = (pred.get("stats") or {}).get("time_s", 0)
    return f"{proof} ({secs:.1f}s); worst case {tiers}"


def print_plan(pred: dict) -> None:
    say(f"plan: {plan_summary(pred)}")
    for i, a in enumerate(pred.get("plan", []), 1):
        say(f"  {i}. {a['description']}")
    if not pred.get("plan"):
        say("  (no actions)")
    for w in pred.get("warnings", []):
        say(f"  warning: {w}")


def wait_player_turn(bridge: Bridge, timeout: float, after_turn: int | None = None) -> dict | None:
    """The state once it is a player turn with an active mech (the active
    flags lag the turn change), or a non-combat phase; None on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = bridge.raw_state() or {}
        if st and not in_combat(st):
            return st
        if (st.get("phase") == "combat_player" and active_mechs(st)
                and (after_turn is None or int(st.get("turn") or 0) > after_turn)):
            return st
        time.sleep(POLL)
    return None


def write_executed_plan(run: Run, start: dict, pred0: dict, executed: list, resolved: bool) -> None:
    """m<MM>_turn_<TT>_solve.json in the old recordings' format."""
    actions = {}
    order = []
    for plan_id, step in executed:
        key = (plan_id, step["action"])
        if key not in actions:
            actions[key] = {"mech_uid": step["uid"], "move_to": None, "weapon_id": "", "target": None}
            order.append(key)
        a = actions[key]
        if step["sub"] == "move":
            a["move_to"] = step["to"]
        elif step["sub"] == "repair":
            a["weapon_id"] = "_REPAIR"
        else:
            a["weapon_id"] = step["weapon"]
            a["target"] = step["target"]
            if step.get("target2"):
                a["target2"] = step["target2"]
    data = {"source": "live_play", "actions": [actions[k] for k in order], "predicted_states": [],
            "engine_plan": pred0.get("plan", []), "proven_optimal": pred0.get("proven_optimal"),
            "worst_case": pred0.get("worst_case")}
    if resolved:
        data["partial_re_solve"] = True
    rec = {"timestamp": now_iso(), "run_id": run.path.name, "mission_index": run.mission_index(start),
           "turn": int(start.get("turn") or 0), "label": "solve", "data": data}
    run.save_json(f"{run.prefix(start)}_solve.json", rec)


def play_turn(ctx) -> list:
    """One player turn. Returns the anomalies (empty: every step matched)."""
    bridge, engine, run, args = ctx.bridge, ctx.engine, ctx.run, ctx.args
    preflight(bridge, args)
    state = wait_player_turn(bridge, args.active_wait)
    if state is None:
        raise Refused(f"no active mech within {args.active_wait:.0f}s: not a player turn?")
    if not in_combat(state):
        raise Refused(f"not in combat (phase {state.get('phase')})")
    state = bridge.settled_state()
    check_loadout(state, ctx.loadout)
    known = {u["uid"] for u in units(state)}
    names = {u["uid"]: u.get("type", "?") for u in units(state)}
    moved: set = set()
    anomalies: list = []
    say(f"== {state.get('mission_id')} turn {state.get('turn')}: solving ({args.time:g}s, {args.threads} threads)")

    def solve(st: dict, label: str) -> tuple[Path, dict]:
        solver_input, patches = patch_state(st, ctx.loadout, moved)
        path = run.save_state(solver_input, label, {"patches": patches} if patches else None)
        if patches:
            run.save_state(st, label + "_raw")
        pred = engine.solve(path, args.time)
        run.save_json(prediction_path(path).name, pred)
        run.event("solve", {"state": path.name, "plan": pred.get("plan"), "proven": pred.get("proven_optimal")})
        return path, pred

    start = state
    _, pred = solve(state, "start")
    pred0 = pred
    print_plan(pred)
    if args.dry_run:
        say("dry run: nothing executed")
        return anomalies
    if pred.get("refused", -1) >= 0:
        raise Anomaly(f"the engine refused its own plan: {pred.get('refused_reason')}")

    executed, plan_id, resolves, i = [], 0, 0, 0
    steps = pred["steps"]
    while i < len(steps):
        step = steps[i]
        text = step_text(step, names)
        execute_step(bridge, step, state, ctx.loadout)
        if step["sub"] == "move":
            moved.add(step["uid"])
        executed.append((plan_id, step))
        state = bridge.settled_state()
        path = run.save_state(state, f"step{len(executed)}")
        live = engine.board(path)
        diffs, _ = diff_boards(step["board"], live, known)
        run.event("step", {"step": text, "state": path.name, "diffs": diffs})
        if not diffs:
            say(f"  step {len(executed)} {text}: matches")
            i += 1
            continue
        say(f"  step {len(executed)} {text}: MISMATCH")
        for d in diffs:
            say(f"      {d}")
        anomalies.append(f"step {len(executed)} {text}: " + "; ".join(diffs))
        resolves += 1
        if resolves > args.max_resolves:
            raise Anomaly(f"{resolves - 1} re-solves this turn and still mismatching: stopping")
        if not active_mechs(state):
            break
        say(f"  re-solving from the live board ({resolves}/{args.max_resolves})")
        _, pred = solve(state, "resolve")
        print_plan(pred)
        if pred.get("refused", -1) >= 0:
            raise Anomaly(f"the engine refused its own plan: {pred.get('refused_reason')}")
        steps, i, plan_id = pred["steps"], 0, plan_id + 1
    write_executed_plan(run, start, pred0, executed, resolves > 0)
    if "after_enemy" in pred:
        e = pred["after_enemy"]
        say(f"predicted after the enemy phase: grid {e['grid_power']}, "
            + ", ".join(f"{describe_unit(u)} hp {u['hp']}" for u in e["units"] if u.get("mech")))
    say("turn played: " + ("all steps matched" if not anomalies else f"{len(anomalies)} mismatch(es)"))
    return anomalies


# ------------------------------------------------------------------ end turn

def click_end_turn(xy: tuple) -> bool:
    """Clicks End Turn at screen point xy (fullscreen 1360x768 default).
    False if no clicking tool is available."""
    cliclick = shutil.which("cliclick") or "/opt/homebrew/bin/cliclick"
    if not os.path.exists(cliclick):
        return False
    subprocess.run(["osascript", "-e", 'tell application "Into the Breach" to activate'],
                   capture_output=True, check=False)
    time.sleep(0.4)
    x, y = xy
    subprocess.run([cliclick, f"m:{x},{y}", "w:150", f"c:{x},{y}"], capture_output=True, check=False)
    return True


def phase_left(bridge: Bridge, turn: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = bridge.raw_state() or {}
        if st.get("phase") != "combat_player" or int(st.get("turn") or 0) > turn:
            return True
        time.sleep(POLL)
    return False


def end_turn(ctx) -> list:
    """End Turn, wait for the next player turn, compare with the engine."""
    bridge, engine, run, args = ctx.bridge, ctx.engine, ctx.run, ctx.args
    state = preflight(bridge, args)
    if state.get("phase") != "combat_player":
        raise Refused(f"not a player turn (phase {state.get('phase')})")
    state = bridge.settled_state()
    check_loadout(state, ctx.loadout)
    turn = int(state.get("turn") or 0)
    known = {u["uid"] for u in units(state)}
    solver_input, patches = patch_state(state, ctx.loadout, set())
    path = run.save_state(solver_input, "end_turn", {"patches": patches} if patches else None)
    pred = engine.predict(path, [])
    run.save_json(prediction_path(path).name, pred)
    if args.dry_run:
        e = pred["after_enemy"]
        say(f"dry run: would end turn {turn}; predicted grid {e['grid_power']}")
        return []

    say(f"== ending turn {turn}")
    ack = bridge.send("END_TURN", 70)
    anomalies = []
    if ack.startswith("OK END_TURN"):
        say(f"  bridge ended the turn ({ack})")
        left = phase_left(bridge, turn, 10)
    else:
        if ack.startswith("NEEDS_MCP_CLICK"):
            say("  bridge deactivated the mechs; clicking End Turn")
        else:
            say(f"  bridge END_TURN failed ({ack}); clicking End Turn (a 'units can still act' "
                "dialog may need YES)")
        left = False
        for attempt in range(3):
            if args.no_click or not ctx.click(args.end_turn_xy):
                say(f"  >>> click End Turn now (screen {args.end_turn_xy[0]},{args.end_turn_xy[1]} in "
                    "fullscreen 1360x768); waiting")
                left = phase_left(bridge, turn, args.timeout)
                break
            run.event("click", {"end_turn": list(args.end_turn_xy), "attempt": attempt + 1})
            left = phase_left(bridge, turn, 8)
            if left:
                break
            say(f"  End Turn click {attempt + 1} did not register; retrying")
    if not left:
        raise Anomaly("the turn did not end (phase still combat_player)")

    say("  enemy phase...")
    after = wait_player_turn(bridge, args.timeout, after_turn=turn)
    if after is None:
        raise Anomaly(f"no next player turn within {args.timeout:.0f}s")
    if not in_combat(after):
        path = run.save_state(after, "after_enemy")
        say(f"mission over (phase {after.get('phase')}); engine predicted mission end: "
            f"{pred.get('enemy_phase', {}).get('mission_ended')}")
        ctx.mission_over = True
        return anomalies
    after = bridge.settled_state()
    path = run.save_state(after, "after_enemy")
    live = engine.board(path)
    pools = frozenset((t["x"], t["y"]) for t in state.get("tiles", []) if t.get("acid"))
    diffs, notes = diff_boards(pred["after_enemy"], live, known, enemy_phase=True, acid_pools=pools)
    run.event("enemy_phase", {"state": path.name, "diffs": diffs, "notes": notes})
    spawns = [f"{describe_unit(u)} at {visual(u['x'], u['y'])}" for u in live["units"] if u["uid"] not in known]
    if spawns:
        say("  new units (spawns): " + ", ".join(spawns))
    for n in notes:
        say(f"  note: {n}")
    if diffs:
        say("  enemy phase: DIFF")
        for d in diffs:
            say(f"      {d}")
        anomalies.append("enemy phase: " + "; ".join(diffs))
    else:
        say(f"  enemy phase: MATCH (grid {live['grid_power']})")
    if pred.get("enemy_phase", {}).get("mission_ended"):
        say("  the engine expected the mission to end here")
    return anomalies


# ------------------------------------------------------------------ deploy

def parse_tile(text: str) -> tuple:
    text = text.strip()
    try:
        if "," in text:
            x, y = (int(v) for v in text.split(","))
            if 0 <= x < 8 and 0 <= y < 8:
                return x, y
        else:
            col, row = text[0].upper(), int(text[1:])
            if "A" <= col <= "H" and 1 <= row <= 8:
                return 8 - row, ord("H") - ord(col)
    except (ValueError, IndexError):
        pass
    raise ValueError(f"bad tile {text!r} (A1-H8, or x,y separated by ';')")


def choose_deploy_tiles(state: dict, zone: list, count: int) -> list:
    """Drop-zone tiles ranked: 2-3 tiles from the nearest Vek or spawn (close
    enough to act on turn 1, not adjacent), near buildings, off the edge,
    spread at least 2 apart."""
    vek = [(u["x"], u["y"]) for u in units(state) if u.get("team") == 6 and (u.get("hp") or 0) > 0]
    vek += [tuple(p) for p in state.get("spawning_tiles", [])]
    buildings = [(t["x"], t["y"]) for t in state.get("tiles", []) if t.get("terrain") == "building"]
    taken = {(u["x"], u["y"]) for u in units(state) if not (u.get("team") == 1 and u.get("mech"))}
    # The bridge's drop zone already leaves out what the deploy UI refuses;
    # never pick a tile that is plainly not walkable either.
    taken |= {(t["x"], t["y"]) for t in state.get("tiles", [])
              if t.get("terrain") in ("building", "mountain", "water", "lava", "chasm")}
    cand = [tuple(p) for p in zone if tuple(p) not in taken]

    def dist(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def score(p):
        d = min((dist(p, v) for v in vek), default=dist(p, (3.5, 3.5)) + 2)
        near_b = sum(1 for b in buildings if dist(p, b) <= 2)
        edge = p[0] in (0, 7) or p[1] in (0, 7)
        return -2 * abs(d - 2.5) + 0.5 * near_b - (1 if edge else 0)

    ranked = sorted(cand, key=lambda p: (-score(p), p))
    chosen = []
    for spread in (2, 1):
        for p in ranked:
            if len(chosen) == count:
                break
            if p not in chosen and all(dist(p, c) >= spread for c in chosen):
                chosen.append(p)
    return chosen + [p for p in ranked if p not in chosen]


def deploy(ctx) -> list:
    bridge, run, args = ctx.bridge, ctx.run, ctx.args
    state = preflight(bridge, args)
    state = bridge.fresh_state()
    if int(state.get("turn") or 0) != 0:
        raise Refused(f"not deployment (turn {state.get('turn')}, phase {state.get('phase')})")
    zone = [tuple(p) for p in (state.get("drop_zone") or state.get("deployment_zone") or [])]
    if not zone:
        raise Refused("the bridge exports no drop zone (drop_zone / deployment_zone)")
    mechs = sorted((u for u in units(state) if u.get("team") == 1 and u.get("mech") and (u.get("hp") or 0) > 0),
                   key=lambda u: u["uid"])
    if not mechs and args.uids:
        # Mechs not yet placed aren't on the board, so the state can't list
        # them; the caller names their uids (a fresh run's squad is 0, 1, 2).
        mechs = [{"uid": int(u), "type": "mech", "team": 1, "mech": True, "hp": 1}
                 for u in args.uids.split(",") if u.strip()]
    if not mechs:
        raise Refused("no mechs found on the board (unplaced mechs aren't in the state); "
                      "pass --uids, e.g. --uids 0,1,2")
    run.save_state(state, "deploy")
    source = state.get("drop_zone_source") or ("deployment_zone" if not state.get("drop_zone") else "?")
    say(f"== deployment: {len(mechs)} mech(s), drop zone ({source}): " + " ".join(visual(*p) for p in zone))
    if args.tiles:
        try:
            wanted = parse_tiles(args.tiles)
        except ValueError as e:
            raise Refused(str(e)) from e
        if len(wanted) < len(mechs):
            raise Refused(f"--tiles gives {len(wanted)} tile(s) for {len(mechs)} mech(s)")
        for p in wanted:
            if p not in zone:
                raise Refused(f"{visual(*p)} {p} is not in the drop zone")
        ranked = wanted
    else:
        ranked = choose_deploy_tiles(state, zone, len(mechs))
    plan = list(zip(mechs, ranked))
    for m, p in plan:
        say(f"  {describe_unit(m)} -> {visual(*p)} {p}")
    if args.dry_run:
        say("dry run: nothing placed")
        return []
    used = set()
    spare = [p for p in ranked[len(mechs):]] if not args.tiles else []
    placed = {}
    for m, p in plan:
        while True:
            if p in used:
                p = spare.pop(0) if spare else None
            if p is None:
                raise Anomaly(f"no drop-zone tile left for {describe_unit(m)}")
            ack = bridge.send(f"DEPLOY {m['uid']} {p[0]} {p[1]}", 15)
            if ack.startswith("OK"):
                used.add(p)
                placed[m["uid"]] = p
                break
            say(f"  DEPLOY {describe_unit(m)} at {visual(*p)} refused: {ack}")
            if args.tiles or not spare:
                raise Anomaly(f"DEPLOY refused: {ack}")
            used.add(p)
            p = spare.pop(0)
    state = bridge.settled_state()
    run.save_state(state, "deployed")
    where = {u["uid"]: (u["x"], u["y"]) for u in units(state)}
    wrong = [f"{uid} at {where.get(uid)} (wanted {p})" for uid, p in placed.items() if where.get(uid) != p]
    if wrong:
        raise Anomaly("deployment not reflected in the state: " + ", ".join(wrong))
    say("deployed and verified. Confirm the deployment in the game.")
    return []


def parse_tiles(text: str) -> list:
    """"C5,D6,E5" (A1-H8) or "3,5;2,4;4,4" (bridge x,y)."""
    if ";" in text:
        return [parse_tile(t) for t in text.split(";") if t.strip()]
    return [parse_tile(t) for t in text.split(",") if t.strip()]


# ------------------------------------------------------------------ status / mission

def status(ctx) -> list:
    bridge = ctx.bridge
    age = bridge.heartbeat_age()
    say(f"heartbeat: {'none' if age is None else f'{age:.1f}s old'}")
    st = bridge.raw_state()
    if st is None:
        say(f"no readable state at {lv.STATE}")
        return []
    say(f"{st.get('mission_id')} turn {st.get('turn')}/{st.get('total_turns')} phase {st.get('phase')} "
        f"grid {st.get('grid_power')}/{st.get('grid_power_max')}"
        + (f" (estimate now {st['grid_power_estimate']})" if "grid_power_estimate" in st else ""))
    say(f"bridge_ext_version {st.get('bridge_ext_version')}  errors {len(st.get('bridge_errors') or [])}"
        + (f"  EXTENSION DISABLED: {st['bridge_ext_disabled']}" if st.get("bridge_ext_disabled") else ""))
    for u in sorted(units(st), key=lambda u: (u.get("team") != 1, u["uid"])):
        if (u.get("hp") or 0) <= 0:
            continue
        line = f"  {describe_unit(u):24} {visual(u['x'], u['y'])} hp {u['hp']}/{u.get('max_hp')}"
        if u.get("team") == 1:
            line += f" active {u.get('active')} moved {u.get('moved')}"
            if u.get("mech"):
                line += f" weapons {u.get('weapons_exact') or u.get('weapons')}"
        elif u.get("has_queued_attack") and u.get("queued_target"):
            line += f" -> {visual(*u['queued_target'])}"
        say(line)
    if st.get("spawning_tiles"):
        say("  spawns at " + " ".join(visual(*p) for p in st["spawning_tiles"]))
    if int(st.get("turn") or 0) == 0:
        zone = st.get("drop_zone") or st.get("deployment_zone") or []
        say(f"  drop zone ({st.get('drop_zone_source')}): " + " ".join(visual(*p) for p in zone))
    if CURRENT.exists():
        say(f"run directory: {json.loads(CURRENT.read_text()).get('run')}")
    return []


def mission(ctx) -> list:
    args = ctx.args
    for n in range(args.max_turns):
        st = ctx.bridge.raw_state() or {}
        if st and not in_combat(st):
            say(f"mission over (phase {st.get('phase')})")
            return []
        anomalies = play_turn(ctx)
        if anomalies:
            say("stopping before End Turn: " + anomalies[0])
            return anomalies
        if args.dry_run:
            return []
        anomalies = end_turn(ctx)
        if anomalies:
            say("stopping: " + anomalies[0])
            return anomalies
        if ctx.mission_over:
            return []
    say(f"stopped after {args.max_turns} turn(s) (--max-turns)")
    return []


class Context:
    def __init__(self, args, bridge=None, engine=None, run=None, click=None):
        self.args = args
        self.run = run
        self.bridge = bridge or Bridge(log=lambda k, d: self.run.event(k, d) if self.run else None)
        self.engine = engine
        self.loadout = load_loadout(getattr(args, "loadout", None))
        self.click = click or click_end_turn
        self.mission_over = False


COMMANDS = {"turn": play_turn, "end-turn": end_turn, "mission": mission, "deploy": deploy, "status": status}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--run", help="run directory (under recordings/live/, or absolute); default: the current one")
    common.add_argument("--new-run", action="store_true", help="start a new run directory")
    common.add_argument("--dry-run", action="store_true", help="solve / choose and print, never act")
    common.add_argument("--max-heartbeat-age", type=float, default=10.0, help="refuse if the heartbeat is older (s)")
    common.add_argument("--loadout", help="JSON {mech type: [weapon ids]} for bridges without weapons_exact")
    engine = argparse.ArgumentParser(add_help=False)
    engine.add_argument("--time", type=float, default=10.0, help="solver time limit per solve (s)")
    engine.add_argument("--threads", type=int, default=8)
    engine.add_argument("--game", help="game install for the engine (default: ITB_GAME_DIR / build default)")
    engine.add_argument("--max-resolves", type=int, default=3, help="re-solves per turn before giving up")
    engine.add_argument("--active-wait", type=float, default=20.0, help="wait for active mechs (s)")
    ending = argparse.ArgumentParser(add_help=False)
    ending.add_argument("--timeout", type=float, default=180.0, help="wait for the next player turn (s)")
    ending.add_argument("--no-click", action="store_true", help="never click; ask to click End Turn instead")
    ending.add_argument("--end-turn-xy", type=lambda s: tuple(int(v) for v in s.split(",")),
                        default=lv.END_TURN_SCREEN, help="End Turn screen point (default: fullscreen 1360x768)")
    sub.add_parser("status", parents=[common], help="bridge and board summary")
    sub.add_parser("turn", parents=[common, engine], help="play one player turn (not End Turn)")
    sub.add_parser("end-turn", parents=[common, engine, ending], help="End Turn and check the enemy phase")
    p = sub.add_parser("mission", parents=[common, engine, ending], help="turns until the mission ends")
    p.add_argument("--max-turns", type=int, default=10)
    p = sub.add_parser("deploy", parents=[common], help="place the mechs in the drop zone")
    p.add_argument("--tiles", help="tiles in mech uid order: C5,D6,E5 or 3,5;2,4;4,4")
    p.add_argument("--uids", help="mech uids when they aren't on the board yet, e.g. 0,1,2")
    return ap


def main(argv=None, *, bridge=None, engine=None, click=None) -> int:
    args = build_parser().parse_args(argv)
    run = None if args.command == "status" else Run.open(args.run, args.new_run)
    ctx = Context(args, bridge=bridge, engine=engine, run=run, click=click)
    if ctx.engine is None and args.command in ("turn", "end-turn", "mission"):
        ctx.engine = Engine(args.threads, args.game, run.path / "itb_live.log")
    try:
        if run:
            run.event("command", {"argv": sys.argv[1:] if argv is None else list(argv)})
        anomalies = COMMANDS[args.command](ctx)
        return 1 if anomalies else 0
    except Refused as e:
        say(f"REFUSED: {e}")
        return 2
    except Anomaly as e:
        say(f"STOPPED: {e}")
        if run:
            run.event("anomaly", str(e))
        return 1
    finally:
        if ctx.engine is not None and engine is None:
            ctx.engine.close()


if __name__ == "__main__":
    sys.exit(main())
