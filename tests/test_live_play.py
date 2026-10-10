"""scripts/live_play.py against a fake bridge (a temp dir with a state file
and a thread that answers commands) and a fake engine. Nothing here touches
the game or the desktop: clicks go to a recorder.

    python3 -m unittest tests.test_live_play
"""

from __future__ import annotations

import copy
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_BRIDGE_DIR = tempfile.mkdtemp(prefix="itb_fake_bridge_")
os.environ["ITB_BRIDGE_DIR"] = _BRIDGE_DIR
sys.path.insert(0, str(REPO / "scripts"))
for _m in ("live_validate", "live_play"):
    if _m in sys.modules:
        importlib.reload(sys.modules[_m])
import live_play as lp  # noqa: E402
import live_validate as lv  # noqa: E402

lp.SETTLE_INTERVAL = 0.01
lp.POLL = 0.02
BRIDGE = Path(_BRIDGE_DIR)


def base_state() -> dict:
    tiles = []
    for x in range(8):
        for y in range(8):
            t = {"x": x, "y": y, "terrain": "ground", "terrain_id": 0}
            if (x, y) == (2, 2):
                t.update(terrain="building", terrain_id=1, building_hp=1)
            tiles.append(t)
    return {
        "phase": "combat_player", "turn": 1, "total_turns": 5, "mission_id": "Mission_Test",
        "in_active_mission": True, "grid_power": 7, "grid_power_max": 7, "bridge_ext_version": 1,
        "bridge_errors": [], "spawning_tiles": [[5, 5]], "tiles": tiles,
        "units": [
            {"uid": 0, "type": "PunchMech", "x": 6, "y": 6, "hp": 3, "max_hp": 3, "team": 1, "mech": True,
             "active": True, "moved": False, "weapons": ["Prime_Punchmech"],
             "weapons_exact": ["Prime_Punchmech_B", "Prime_Lasermech_A"],
             "weapon_slots": [{"slot": 0, "id": "Prime_Punchmech_B"}, {"slot": 1, "id": "Prime_Lasermech_A"}]},
            {"uid": 1, "type": "TankMech", "x": 6, "y": 1, "hp": 3, "max_hp": 3, "team": 1, "mech": True,
             "active": True, "moved": False, "weapons": ["Brute_Tankmech"], "weapons_exact": ["Brute_Tankmech"],
             "weapon_slots": [{"slot": 0, "id": "Brute_Tankmech"}]},
            {"uid": 100, "type": "Scorpion1", "x": 3, "y": 3, "hp": 3, "max_hp": 3, "team": 6, "mech": False,
             "active": False, "has_queued_attack": True, "queued_target": [2, 3]},
        ],
    }


def compact(state: dict) -> dict:
    """What itb_live's live_board_json gives for these simple boards."""
    us = []
    for u in state["units"]:
        if u.get("is_extra_tile") or u.get("hp", 0) <= 0:
            continue
        us.append({"uid": u["uid"], "type": u["type"], "x": u["x"], "y": u["y"], "hp": u["hp"],
                   "team": u["team"], "mech": u.get("mech", False),
                   **{f: bool(u.get(f)) for f in ("fire", "acid", "frozen", "shield", "web")}})
    us.sort(key=lambda u: u["uid"])
    bs = [{"x": t["x"], "y": t["y"], "hp": t["building_hp"]} for t in state["tiles"]
          if t["terrain"] == "building"]
    return {"grid_power": state["grid_power"], "buildings": bs, "units": us}


def unit(state, uid):
    return next(u for u in state["units"] if u["uid"] == uid)


def apply(state: dict, step: dict, damage: int = 1) -> None:
    """The fake game's rules (and the fake engine's, with damage=1)."""
    u = unit(state, step["uid"])
    if step["sub"] == "move":
        u["x"], u["y"] = step["to"]
        u["moved"] = True
    elif step["sub"] == "weapon":
        tx, ty = step["target"]
        for v in state["units"]:
            if (v["x"], v["y"]) == (tx, ty):
                v["hp"] -= damage
        u["active"] = False
    else:
        u["hp"] = min(u["max_hp"], u["hp"] + 1)
        u["active"] = False


PLAN = [
    {"sub": "move", "uid": 0, "to": [3, 4], "action": 0},
    {"sub": "weapon", "uid": 0, "weapon": "Prime_Lasermech_A", "target": [3, 3], "target2": None, "action": 0},
    {"sub": "weapon", "uid": 1, "weapon": "Brute_Tankmech", "target": [3, 3], "target2": None, "action": 1},
]


class FakeEngine:
    def __init__(self, plan=PLAN, after_enemy=None):
        self.plan = plan
        self.after_enemy = after_enemy
        self.solves = []
        self.predicts = []

    @staticmethod
    def _state(path) -> dict:
        d = json.loads(Path(path).read_text())
        return d["data"]["bridge_state"] if "data" in d else d

    def _simulate(self, st: dict, steps: list) -> dict:
        b = copy.deepcopy(st)
        out = []
        for i, s in enumerate(steps):
            apply(b, s)
            out.append(dict(s, index=i, status="ok", board=compact(b)))
        after = compact(b)
        enemy = copy.deepcopy(self.after_enemy(b)) if self.after_enemy else compact(b)
        plan = [{"uid": s["uid"], "description": f"#{s['uid']} {s['sub']}"} for s in steps]
        return {"ok": True, "plan": plan, "steps": out, "refused": -1, "start": compact(st),
                "after_player": after, "after_enemy": enemy, "enemy_phase": {"mission_ended": False},
                "warnings": []}

    def solve(self, path, time_limit):
        st = self._state(path)
        self.solves.append(st)
        active = {u["uid"] for u in st["units"] if u.get("team") == 1 and u.get("active")}
        moved = {u["uid"] for u in st["units"] if u.get("moved")}
        steps = [s for s in self.plan if s["uid"] in active and not (s["sub"] == "move" and s["uid"] in moved)]
        out = self._simulate(st, steps)
        out.update(searched=True, proven_optimal=True, worst_case={"grid": 0}, stats={"time_s": 0.1})
        return out

    def predict(self, path, plan):
        self.predicts.append(plan)
        return self._simulate(self._state(path), [])

    def board(self, path):
        return compact(self._state(path))

    def close(self):
        pass


class FakeBridge:
    """Answers /tmp-style commands from a thread, like the Lua bridge."""

    def __init__(self, state: dict):
        self.state = state
        self.commands = []
        self.damage = 1
        self.refuse_native = False
        self.end_turn_ack = "NEEDS_MCP_CLICK END_TURN method=SetActive"
        self.refused_deploy = set()
        self.export_moved = True
        self.next_turn = None  # function(state) -> next player-turn state
        self.stop = threading.Event()
        self.write_state()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def write_state(self, path=None):
        path = path or lv.STATE
        tmp = Path(str(path) + ".tmp")
        st = copy.deepcopy(self.state)
        if not self.export_moved:
            for u in st["units"]:
                u.pop("moved", None)
        tmp.write_text(json.dumps(st))
        os.replace(tmp, path)

    def advance(self):
        """The game after End Turn: the enemy phase, then the next turn."""
        self.state["phase"] = "combat_enemy"
        self.write_state()
        time.sleep(0.05)
        self.state = self.next_turn(self.state) if self.next_turn else self.default_next(self.state)
        self.write_state()

    @staticmethod
    def default_next(st):
        st = copy.deepcopy(st)
        st["phase"] = "combat_player"
        st["turn"] += 1
        for u in st["units"]:
            if u["team"] == 1:
                u["active"], u["moved"] = True, False
        return st

    def handle(self, cmd: str) -> str:
        parts = cmd.split()
        name, args = parts[0], parts[1:]
        if name == "SNAPSHOT":
            path = BRIDGE / f"itb_snapshot_{args[0] if args else 'x'}.json"
            self.write_state(path)
            return f"OK SNAPSHOT {path}"
        if name == "LUA":
            return "OK LUA: refresh"
        if name in ("MOVE_NATIVE", "MOVE"):
            if name == "MOVE_NATIVE" and self.refuse_native:
                return "ERROR: unknown command: MOVE_NATIVE"
            uid, x, y = (int(v) for v in args)
            apply(self.state, {"sub": "move", "uid": uid, "to": [x, y]})
            return f"OK {name} {uid} to {x},{y} [FireWeapon[0]] at {x},{y}"
        if name == "ATTACK":
            uid, slot, x, y = (int(v) for v in args)
            apply(self.state, {"sub": "weapon", "uid": uid, "target": [x, y]}, self.damage)
            return f"OK ATTACK {uid} slot={slot} at {x},{y} [FireWeapon]"
        if name == "REPAIR":
            apply(self.state, {"sub": "repair", "uid": int(args[0])})
            return f"OK REPAIR {args[0]}"
        if name == "END_TURN":
            for u in self.state["units"]:
                if u["team"] == 1:
                    u["active"] = False
            if self.end_turn_ack.startswith("OK"):
                threading.Thread(target=self.advance, daemon=True).start()
            return self.end_turn_ack
        if name == "DEPLOY":
            uid, x, y = (int(v) for v in args)
            if (x, y) in self.refused_deploy:
                return f"ERROR: DEPLOY refused: {x},{y} reserved tile (pylons)"
            u = unit(self.state, uid)
            u["x"], u["y"] = x, y
            return f"OK DEPLOY {uid} at {x},{y}"
        return f"ERROR: unknown command: {name}"

    def loop(self):
        while not self.stop.is_set():
            (BRIDGE / "itb_bridge_heartbeat").write_text("1")
            if lv.CMD.exists():
                text = lv.CMD.read_text().strip()
                lv.CMD.unlink()
                seq, _, cmd = text.partition(" ")
                self.commands.append(cmd)
                ack = self.handle(cmd)
                tmp = BRIDGE / "itb_ack.txt.tmp"
                tmp.write_text(f"{seq} {ack}")
                os.replace(tmp, lv.ACK)
                self.write_state()
            time.sleep(0.005)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)


class LivePlayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="itb_live_play_"))
        self._roots = (lp.LIVE_ROOT, lp.CURRENT)
        lp.LIVE_ROOT = self.tmp / "live"
        lp.CURRENT = self.tmp / "current.json"
        self.clicks = []
        self.fb = None

    def tearDown(self):
        if self.fb:
            self.fb.close()
        lp.LIVE_ROOT, lp.CURRENT = self._roots
        shutil.rmtree(self.tmp, ignore_errors=True)

    def bridge(self, state=None) -> FakeBridge:
        self.fb = FakeBridge(state or base_state())
        return self.fb

    def click(self, xy):
        self.clicks.append(xy)
        threading.Thread(target=self.fb.advance, daemon=True).start()
        return True

    def run_cmd(self, argv, engine=None) -> int:
        return lp.main(argv + ["--new-run"] if "--run" not in argv else argv, engine=engine or FakeEngine(),
                       click=self.click)

    def run_dir(self) -> Path:
        return Path(json.loads(lp.CURRENT.read_text())["run"])

    def acting(self):
        return [c for c in self.fb.commands if c.split()[0] not in ("SNAPSHOT", "LUA")]

    # ---------------------------------------------------------------- safety

    def test_refuses_a_stale_heartbeat(self):
        self.bridge()
        self.fb.close()
        old = time.time() - 120
        os.utime(BRIDGE / "itb_bridge_heartbeat", (old, old))
        self.assertEqual(self.run_cmd(["turn"]), 2)
        self.assertEqual(self.fb.commands, [])

    def test_refuses_when_the_extension_is_disabled(self):
        st = base_state()
        st["bridge_ext_disabled"] = "budget: dump took 1.2s"
        self.bridge(st)
        self.assertEqual(self.run_cmd(["turn"]), 2)
        self.assertEqual(self.acting(), [])

    def test_refuses_without_exact_weapons_unless_given_a_loadout(self):
        st = base_state()
        for u in st["units"]:
            u.pop("weapons_exact", None)
            u.pop("weapon_slots", None)
        self.bridge(st)
        self.assertEqual(self.run_cmd(["turn"]), 2)
        loadout = self.tmp / "loadout.json"
        loadout.write_text(json.dumps({"PunchMech": ["Prime_Punchmech_B", "Prime_Lasermech_A"],
                                       "TankMech": ["Brute_Tankmech"]}))
        eng = FakeEngine()
        self.assertEqual(self.run_cmd(["turn", "--dry-run", "--loadout", str(loadout)], eng), 0)
        solved = eng.solves[0]
        self.assertEqual(unit(solved, 0)["weapons_exact"], ["Prime_Punchmech_B", "Prime_Lasermech_A"])
        # The live state is archived as it was, beside the patched input.
        raws = list(self.run_dir().glob("*_start_raw_*.json"))
        self.assertEqual(len(raws), 1)
        self.assertNotIn("weapons_exact", unit(json.loads(raws[0].read_text())["data"]["bridge_state"], 0))
        # A slot from the loadout order (secondary = 1).
        self.assertEqual(lp.weapon_slot(st, 0, "Prime_Lasermech_A", lp.load_loadout(str(loadout))), 1)

    def test_dry_run_sends_no_action(self):
        self.bridge()
        eng = FakeEngine()
        self.assertEqual(self.run_cmd(["turn", "--dry-run"], eng), 0)
        self.assertEqual(self.acting(), [])
        self.assertEqual(len(eng.solves), 1)
        self.assertEqual(self.run_cmd(["deploy", "--dry-run"]), 2)  # turn 1: not a deployment
        self.assertEqual(self.acting(), [])

    # ---------------------------------------------------------------- turn

    def test_turn_executes_and_matches(self):
        self.bridge()
        eng = FakeEngine()
        self.assertEqual(self.run_cmd(["turn"], eng), 0)
        self.assertEqual(self.acting(), ["MOVE_NATIVE 0 3 4", "ATTACK 0 1 3 3", "ATTACK 1 0 3 3"])
        self.assertEqual(len(eng.solves), 1)
        run = self.run_dir()
        names = sorted(p.name for p in run.iterdir())
        self.assertIn("m00_turn_01_solve_input.json", names)
        self.assertIn("m00_turn_01_solve_input_prediction.json", names)
        self.assertIn("m00_turn_01_step1_01.json", names)
        self.assertIn("m00_turn_01_step3_01.json", names)
        self.assertIn("events.jsonl", names)
        solve = json.loads((run / "m00_turn_01_solve.json").read_text())
        self.assertEqual(solve["data"]["actions"][0],
                         {"mech_uid": 0, "move_to": [3, 4], "weapon_id": "Prime_Lasermech_A", "target": [3, 3]})
        self.assertNotIn("partial_re_solve", solve["data"])
        wrapper = json.loads((run / "m00_turn_01_solve_input.json").read_text())
        self.assertEqual(wrapper["data"]["bridge_state"]["mission_id"], "Mission_Test")
        self.assertEqual(wrapper["run_id"], run.name)

    def test_a_mismatch_re_solves_from_the_live_board(self):
        self.bridge()
        self.fb.damage = 2  # the game hits harder than the engine predicts
        eng = FakeEngine()
        self.assertEqual(self.run_cmd(["turn"], eng), 1)
        self.assertEqual(len(eng.solves), 2)
        # The re-solve saw the live board: mech 0 has moved and acted.
        self.assertFalse(unit(eng.solves[1], 0)["active"])
        self.assertEqual(unit(eng.solves[1], 100)["hp"], 1)
        self.assertEqual(self.acting(), ["MOVE_NATIVE 0 3 4", "ATTACK 0 1 3 3", "ATTACK 1 0 3 3"])
        solve = json.loads((self.run_dir() / "m00_turn_01_solve.json").read_text())
        self.assertTrue(solve["data"]["partial_re_solve"])

    def test_move_native_falls_back_to_move(self):
        self.bridge()
        self.fb.refuse_native = True
        self.assertEqual(self.run_cmd(["turn"]), 0)
        self.assertEqual(self.acting()[:2], ["MOVE_NATIVE 0 3 4", "MOVE 0 3 4"])

    def test_old_bridge_moved_flags_are_tracked(self):
        self.bridge()
        self.fb.damage = 2
        self.fb.export_moved = False
        eng = FakeEngine()
        self.run_cmd(["turn"], eng)
        self.assertNotIn("moved", unit(eng.solves[0], 0))
        self.assertTrue(unit(eng.solves[1], 0).get("moved"))

    # ---------------------------------------------------------------- end turn

    def test_end_turn_clicks_when_the_bridge_cannot_and_compares(self):
        self.bridge()
        eng = FakeEngine()
        self.assertEqual(self.run_cmd(["end-turn"], eng), 0)
        self.assertEqual(self.acting(), ["END_TURN"])
        self.assertEqual(self.clicks, [lv.END_TURN_SCREEN])
        self.assertEqual(eng.predicts, [[]])
        self.assertEqual(self.fb.state["turn"], 2)
        self.assertTrue(list(self.run_dir().glob("m00_turn_02_after_enemy_*.json")))

    def test_end_turn_without_a_click_when_the_bridge_ends_it(self):
        self.bridge()
        self.fb.end_turn_ack = "OK END_TURN phase=combat_player method=EndTurn"
        self.assertEqual(self.run_cmd(["end-turn"]), 0)
        self.assertEqual(self.clicks, [])

    def test_end_turn_reports_enemy_phase_differences_and_spawns(self):
        self.bridge()

        def next_turn(st):
            st = FakeBridge.default_next(st)
            unit(st, 1)["hp"] = 1  # the engine did not see this coming
            unit(st, 100)["x"] = 4  # Vek move while the AI plans: not a difference
            st["units"].append({"uid": 101, "type": "Firefly1", "x": 5, "y": 5, "hp": 3, "team": 6})
            return st

        self.fb.next_turn = next_turn
        out = []
        orig = lp.say
        lp.say = lambda m="": out.append(m)
        try:
            code = self.run_cmd(["end-turn"])
        finally:
            lp.say = orig
        self.assertEqual(code, 1)
        text = "\n".join(out)
        self.assertIn("TankMech#1 hp: engine 3, game 1", text)
        self.assertIn("Firefly1#101", text)
        self.assertNotIn("Scorpion1#100: engine at", text)

    def test_end_turn_refuses_outside_a_player_turn(self):
        st = base_state()
        st["phase"] = "combat_enemy"
        self.bridge(st)
        self.assertEqual(self.run_cmd(["end-turn"]), 2)
        self.assertEqual(self.acting(), [])

    def test_mission_stops_at_the_first_anomaly_before_ending_the_turn(self):
        self.bridge()
        self.fb.damage = 2
        self.assertEqual(self.run_cmd(["mission"]), 1)
        self.assertNotIn("END_TURN", self.acting())

    def test_mission_plays_until_the_mission_ends(self):
        self.bridge()

        def next_turn(st):
            st = FakeBridge.default_next(st)
            if st["turn"] > 2:
                st["phase"], st["in_active_mission"] = "unknown", False
            return st

        self.fb.next_turn = next_turn
        self.assertEqual(self.run_cmd(["mission"]), 0)
        self.assertEqual(self.acting().count("END_TURN"), 2)

    # ---------------------------------------------------------------- deploy

    def deploy_state(self):
        st = base_state()
        st["turn"] = 0
        st["deploying"] = True
        st["drop_zone"] = [[x, y] for x in range(1, 4) for y in range(1, 7)]
        st["drop_zone_source"] = "zone"
        for u in st["units"]:
            if u["team"] == 1:
                u["x"], u["y"] = -1, -1
        return st

    def test_deploy_uses_the_drop_zone_and_skips_refused_tiles(self):
        self.bridge(self.deploy_state())
        ranked = lp.choose_deploy_tiles(self.fb.state, [tuple(p) for p in self.fb.state["drop_zone"]], 2)
        self.fb.refused_deploy = {ranked[0]}
        self.assertEqual(self.run_cmd(["deploy"]), 0)
        deploys = [c for c in self.acting() if c.startswith("DEPLOY")]
        self.assertEqual(len(deploys), 3)  # one refused, retried elsewhere
        placed = {(u["x"], u["y"]) for u in self.fb.state["units"] if u["team"] == 1}
        self.assertNotIn(ranked[0], placed)
        self.assertTrue(placed <= {tuple(p) for p in self.fb.state["drop_zone"]})

    def test_deploy_tiles_override(self):
        self.bridge(self.deploy_state())
        self.assertEqual(self.run_cmd(["deploy", "--tiles", "A1,C5"]), 2)  # A1 is outside the zone
        self.assertEqual(self.acting(), [])
        self.assertEqual(self.run_cmd(["deploy", "--tiles", "C5,E6"]), 0)
        self.assertEqual(self.acting(), ["DEPLOY 0 3 5", "DEPLOY 1 2 3"])
        self.assertEqual(lp.parse_tiles("3,5;2,2"), [(3, 5), (2, 2)])

    # ---------------------------------------------------------------- comparing

    def test_diff_boards(self):
        a = compact(base_state())
        b = copy.deepcopy(a)
        self.assertEqual(lp.diff_boards(a, b, {0, 1, 100}), ([], []))
        b["units"][2]["x"] = 4
        b["buildings"] = []
        diffs, _ = lp.diff_boards(a, b, {0, 1, 100})
        self.assertEqual(diffs, ["Scorpion1#100: engine at E5, game at E4", "building F6 hp: engine 1, game gone"])
        diffs, _ = lp.diff_boards(a, b, {0, 1, 100}, enemy_phase=True)
        self.assertEqual(diffs, ["building F6 hp: engine 1, game gone"])
        # Units the engine creates have engine uids: matched by type and tile.
        a["units"].append({"uid": 500, "type": "Spiderling1", "x": 1, "y": 1, "hp": 1, "team": 6, "mech": False})
        b = copy.deepcopy(a)
        b["units"][-1]["uid"] = 120
        self.assertEqual(lp.diff_boards(a, b, {0, 1, 100})[0], [])


@unittest.skipUnless(lp.ITB_LIVE.exists(), "engine/build/itb_live not built")
class ItbLiveTest(unittest.TestCase):
    """The real engine on an archived state (needs the game's scripts)."""

    def test_board_of_an_archived_live_state(self):
        state = next((REPO / "recordings" / "live" / "2026-10-09").glob("Mission_Final_Cave_t2_start_*.json"))
        res = subprocess.run([str(lp.ITB_LIVE), "board", str(state)], capture_output=True, text=True, timeout=120)
        out = json.loads(res.stdout)
        if not out.get("ok") and "scripts" in out.get("error", ""):
            self.skipTest("no game install (set ITB_GAME_DIR)")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["turn"], 2)
        self.assertEqual(len([u for u in out["board"]["units"] if u["mech"]]), 3)


def tearDownModule():
    shutil.rmtree(_BRIDGE_DIR, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()


class DiffBoardsTest(unittest.TestCase):
    """The enemy-phase comparison's handling of AI planning moves."""

    @staticmethod
    def board(units, buildings=(), grid=5):
        return {"units": list(units), "buildings": list(buildings), "grid_power": grid}

    @staticmethod
    def vek(x, y, acid=False):
        return {"uid": 97, "type": "Firefly1", "x": x, "y": y, "hp": 3, "acid": acid}

    def test_acid_pool_picked_up_by_an_ai_move_is_a_note(self):
        want = self.board([self.vek(7, 1)])
        got = self.board([self.vek(7, 3, acid=True)])
        diffs, notes = lp.diff_boards(want, got, {97}, enemy_phase=True, acid_pools=frozenset({(7, 3)}))
        self.assertEqual(diffs, [])
        self.assertTrue(any("acid pool" in n for n in notes))

    def test_acid_without_a_pool_is_still_a_difference(self):
        want = self.board([self.vek(7, 1)])
        got = self.board([self.vek(7, 3, acid=True)])
        diffs, _ = lp.diff_boards(want, got, {97}, enemy_phase=True, acid_pools=frozenset())
        self.assertEqual(len(diffs), 1)
