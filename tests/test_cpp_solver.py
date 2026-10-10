"""Tests for the C++ solver adapter (src/solver/cpp_solver.py) and bindings.

Isolated: imports only the adapter, the model and verify (no capture /
control / desktop modules, no game). The engine tests need the built module
(engine/build/python, see CLAUDE.md) and the game scripts (ITB_GAME_DIR or
.local_decompile); they skip otherwise.

    python3 -m unittest tests.test_cpp_solver -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
os.environ.setdefault("ITB_SAVE_DIR", tempfile.mkdtemp(prefix="itb_cpp_test_save_"))

from src.solver import cpp_solver  # noqa: E402
from src.solver.verify import diff_states  # noqa: E402
from src.model.board import Board  # noqa: E402

RECORDING = REPO / "recordings/20260517_105759_344/m17_turn_04_solve_input.json"


def _engine_available() -> bool:
    try:
        cpp_solver.import_engine_module()
    except ImportError:
        return False
    return bool(cpp_solver.resolve_game_root())


def _bridge(path: Path = RECORDING) -> dict:
    return json.loads(path.read_text())["data"]["bridge_state"]


class PlanShapeTests(unittest.TestCase):
    def test_entries_after_unit_action(self):
        plan = [
            {"uid": 0, "kind": "weapon"},
            {"uid": 1, "kind": "none", "move": [1, 1]},
            {"uid": 0, "kind": "none", "move": [2, 2]},  # move after attack
            {"uid": 1, "kind": "weapon"},
        ]
        self.assertEqual(cpp_solver.plan_entries_after_unit_action(plan), [2])

    def test_interleaving_detection_and_regroup(self):
        plan = [
            {"uid": 0, "kind": "none", "move": [1, 1], "weapon": "", "target": None},
            {"uid": 1, "kind": "weapon", "move": [3, 3], "weapon": "W1", "target": [4, 4]},
            {"uid": 0, "kind": "weapon", "move": None, "weapon": "W0", "target": [1, 2]},
        ]
        self.assertTrue(cpp_solver.is_interleaved(plan))
        regrouped = cpp_solver.regroup_by_unit(plan)
        self.assertFalse(cpp_solver.is_interleaved(regrouped))
        self.assertEqual(len(regrouped), 2)
        self.assertEqual(regrouped[0]["uid"], 0)
        self.assertEqual(regrouped[0]["move"], [1, 1])
        self.assertEqual(regrouped[0]["kind"], "weapon")
        self.assertEqual(regrouped[0]["target"], [1, 2])
        self.assertEqual(regrouped[1]["uid"], 1)

    def test_contiguous_plan_is_not_interleaved(self):
        plan = [{"uid": 0, "kind": "none", "move": [1, 1]},
                {"uid": 0, "kind": "weapon"}, {"uid": 1, "kind": "weapon"}]
        self.assertFalse(cpp_solver.is_interleaved(plan))

    def test_visual_notation(self):
        self.assertEqual(cpp_solver.visual((3, 5)), "C5")
        self.assertEqual(cpp_solver.visual((0, 0)), "H8")

    def test_requested_solver(self):
        old = os.environ.pop("ITB_SOLVER", None)
        try:
            self.assertEqual(cpp_solver.requested_solver(), "cpp")
            os.environ["ITB_SOLVER"] = "rust"
            self.assertEqual(cpp_solver.requested_solver(), "rust")
            self.assertEqual(cpp_solver.requested_solver("cpp"), "cpp")
        finally:
            os.environ.pop("ITB_SOLVER", None)
            if old is not None:
                os.environ["ITB_SOLVER"] = old

    def test_overlays(self):
        self.assertEqual(cpp_solver.overlay_blocks_cpp(["final_turn_pod_collection"]), [])
        self.assertEqual(cpp_solver.overlay_blocks_cpp(["hold_the_door"]), ["hold_the_door"])

    def test_to_mech_actions_conventions(self):
        bridge = {"units": [{"uid": 0, "type": "PunchMech"}, {"uid": 1, "type": "TankMech"}]}
        entries = [
            {"uid": 0, "kind": "none", "move": [2, 2], "weapon": "", "target": None},
            {"uid": 1, "kind": "repair", "move": None, "weapon": "Skill_Repair", "target": [5, 5]},
            {"uid": 0, "kind": "weapon", "move": None, "weapon": "Prime_Punchmech",
             "target": [2, 3], "target2": None},
        ]
        sim = {"steps": [
            {"pos_before": [1, 1], "pos_after": [2, 2]},
            {"pos_before": [5, 5], "pos_after": [5, 5]},
            {"pos_before": [2, 2], "pos_after": [2, 2]},
        ]}
        acts = cpp_solver.to_mech_actions(entries, sim, bridge)
        self.assertEqual((acts[0].move_to, acts[0].weapon, acts[0].target), ((2, 2), "None", (255, 255)))
        self.assertEqual((acts[1].move_to, acts[1].weapon, acts[1].target), ((5, 5), "_REPAIR", (5, 5)))
        self.assertEqual((acts[2].move_to, acts[2].weapon, acts[2].target),
                         ((2, 2), "Prime_Punchmech", (2, 3)))
        self.assertIn("move G7→F6", acts[0].description)

    def test_bridge_board_merge(self):
        raw = {
            "mission_id": "Mission_Test", "turn": 2, "attack_order": [7],
            "tiles": [{"x": 0, "y": 0, "terrain": "building", "terrain_id": 1,
                       "building_hp": 1, "objective_name": "Str_Power"}],
            "units": [
                {"uid": 0, "type": "PunchMech", "x": 1, "y": 1, "hp": 3, "max_hp": 3, "team": 1,
                 "mech": True, "active": True, "pilot_id": "Pilot_Original", "move": 3,
                 "weapons": ["Prime_Punchmech"]},
                {"uid": 7, "type": "Firefly1", "x": 2, "y": 2, "hp": 3, "max_hp": 3, "team": 6,
                 "mech": False, "active": False, "has_queued_attack": True,
                 "queued_target": [2, 3], "queued_target_raw": [2, 3]},
                {"uid": 8, "type": "Hornet1", "x": 4, "y": 4, "hp": 2, "max_hp": 2, "team": 6},
            ],
        }
        eng = {
            "grid_power": 5, "grid_power_max": 7, "turn": 2, "total_turns": 5, "spawning_tiles": [],
            "tiles": [{"x": 0, "y": 0, "terrain": "rubble", "terrain_id": 2, "lava": False,
                       "fire": False, "smoke": False, "acid": False, "shield": False,
                       "frozen": False, "cracked": False, "pod": False, "conveyor": -1, "item": ""}],
            "units": [
                {"uid": 0, "type": "PunchMech", "x": 1, "y": 2, "hp": 0, "max_hp": 3, "team": 1,
                 "mech": True, "active": False, "has_queued_attack": False, "web": False},
                {"uid": 7, "type": "Firefly1", "x": 2, "y": 2, "hp": 1, "max_hp": 3, "team": 6,
                 "mech": False, "active": False, "has_queued_attack": False, "web": False},
                {"uid": 8, "type": "Hornet1", "x": 4, "y": 4, "hp": 0, "max_hp": 2, "team": 6,
                 "mech": False, "active": False, "has_queued_attack": False, "web": False},
            ],
        }
        out = cpp_solver.bridge_board(eng, raw)
        self.assertEqual(out["grid_power"], 5)
        self.assertNotIn("attack_order", out)
        self.assertEqual(out["mission_id"], "Mission_Test")
        by_uid = {u["uid"]: u for u in out["units"]}
        self.assertNotIn(8, by_uid)  # dead Vek removed
        self.assertEqual(by_uid[0]["hp"], 0)  # mech wreck kept
        self.assertEqual(by_uid[0]["pilot_id"], "Pilot_Original")
        self.assertEqual((by_uid[0]["x"], by_uid[0]["y"]), (1, 2))
        self.assertFalse(by_uid[7]["has_queued_attack"])
        self.assertNotIn("queued_target", by_uid[7])
        self.assertNotIn("queued_target_raw", by_uid[7])
        self.assertEqual(out["tiles"][0]["terrain"], "rubble")
        self.assertEqual(out["tiles"][0]["objective_name"], "Str_Power")


@unittest.skipUnless(_engine_available(), "itb_engine module or game scripts not available")
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = cpp_solver.get_engine(2, 0)
        cls.module = cpp_solver.import_engine_module()

    def test_module_attributes(self):
        self.assertTrue(self.module.ENGINE_VERSION.startswith("cpp-engine-"))
        self.assertGreaterEqual(self.engine.threads, 2)

    def test_load_reports_board(self):
        out = json.loads(self.engine.load(json.dumps(_bridge())))
        self.assertEqual(out["mission_id"], "Mission_Crack")
        self.assertEqual(out["active_units"], 3)
        self.assertEqual(len(out["board"]["tiles"]), 64)

    def test_bad_input_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.engine.load(json.dumps({"tiles": []}))

    def test_solve_and_predicted_states(self):
        bridge = _bridge()
        out = cpp_solver.solve(bridge, 2.0, spawns=[tuple(s) for s in bridge["spawning_tiles"]],
                               current_turn=bridge["turn"], total_turns=bridge["total_turns"],
                               threads=2)
        self.assertTrue(out.ok, out.reason)
        acts = out.solution.actions
        self.assertTrue(acts)
        states = out.enriched["predicted_states"]
        self.assertEqual(len(states), len(acts))
        units = {u["uid"]: u for u in bridge["units"]}
        for a, st in zip(acts, states):
            self.assertIn(a.mech_uid, units)
            self.assertIn("post_attack", st)
            if a.weapon not in ("None", "_REPAIR"):
                self.assertIn(a.weapon, units[a.mech_uid]["weapons"])
            for key in ("units", "tiles_changed", "grid_power", "snapshot_phase"):
                self.assertIn(key, st["post_attack"])
        # Recording-shaped extras.
        for key in ("post_player_board", "final_board", "predicted_outcome",
                    "score_breakdown", "action_results"):
            self.assertIn(key, out.enriched)
        self.assertEqual(len(out.enriched["final_board"]["tiles"]), 64)
        self.assertEqual(out.enriched["final_board"]["turn"], bridge["turn"] + 1)
        self.assertEqual(out.meta["solver"], "cpp")
        self.assertIn("worst_case", out.meta)

    def test_predicted_states_round_trip_through_verify(self):
        bridge = _bridge()
        out = cpp_solver.solve(bridge, 1.0, threads=2)
        self.assertTrue(out.ok, out.reason)
        plan = out.meta["executed_plan"]
        sim = json.loads(self.engine.simulate(json.dumps(bridge), cpp_solver._plan_payload(plan)))
        last = {int(e["uid"]): i for i, e in enumerate(plan)}
        skipped = set()
        for i, step in enumerate(sim["steps"]):
            board = Board.from_bridge_data(cpp_solver.bridge_board(step["after_action"], bridge))
            if plan[i]["kind"] == "none" and last[int(plan[i]["uid"])] == i:
                skipped.add(int(plan[i]["uid"]))  # the bot SKIPs it
            for u in board.units:
                if u.uid in skipped:
                    u.active = False
            diff = diff_states(out.enriched["predicted_states"][i]["post_attack"], board)
            self.assertTrue(diff.is_empty(), diff.to_dict())

    def test_desync_is_detected(self):
        bridge = _bridge()
        out = cpp_solver.solve(bridge, 1.0, threads=2)
        self.assertTrue(out.ok, out.reason)
        snap = out.enriched["predicted_states"][0]["post_attack"]
        # The unchanged starting board must differ from the prediction
        # after the first action (it kills or damages something).
        diff = diff_states(snap, Board.from_bridge_data(bridge))
        self.assertFalse(diff.is_empty())

    def test_can_move_false_pins_the_unit(self):
        bridge = _bridge()
        for u in bridge["units"]:
            if u["uid"] == 2:  # RockartMech: the solver moves it on this board
                u["can_move"] = False
        raw = json.loads(self.engine.solve(json.dumps(bridge),
                                           json.dumps({"time_limit": 1.0, "simulate": False})))
        for a in raw["plan"]:
            if a["uid"] == 2:
                self.assertIsNone(a["move"])

    def test_interleaved_plan_snapshots(self):
        # A moves, B fires, A fires: the engine accepts the interleaving, the
        # adapter keeps A active after its move-only entry (no SKIP), and the
        # regrouped plan scores the same here.
        bridge = _bridge()
        plan = [
            {"uid": 2, "move": [1, 5], "kind": "none", "weapon": "", "target": None, "target2": None},
            {"uid": 0, "move": None, "kind": "weapon", "weapon": "Prime_Lightning_A",
             "target": [4, 2], "target2": None},
            {"uid": 2, "move": None, "kind": "weapon", "weapon": "Ranged_Rockthrow",
             "target": [1, 1], "target2": None},
        ]
        bj = json.dumps(bridge)
        sim = json.loads(self.engine.simulate(bj, json.dumps(plan)))
        self.assertEqual(sim["refused"], -1, sim.get("refused_reason"))
        enriched = cpp_solver.build_enriched(bridge, sim, plan, [], bridge["turn"],
                                             bridge["total_turns"], 2**31 - 1)
        first = {u["uid"]: u for u in enriched["predicted_states"][0]["post_attack"]["units"]}
        self.assertTrue(first[2]["active"])  # still has its attack
        self.assertEqual(first[2]["pos"], [1, 5])
        acts = cpp_solver.to_mech_actions(plan, sim, bridge)
        self.assertEqual(acts[2].move_to, (1, 5))  # acts from where it moved
        inter = json.loads(self.engine.evaluate(bj, json.dumps(plan)))
        regrouped = json.loads(self.engine.evaluate(
            bj, cpp_solver._plan_payload(cpp_solver.regroup_by_unit(plan))))
        self.assertTrue(inter["ok"] and regrouped["ok"])
        self.assertEqual(inter["worst_case_vector"], regrouped["worst_case_vector"])

    def test_every_active_unit_ends_the_plan(self):
        # A plan that leaves units unused gets no-op entries (SKIP) for them,
        # so the End Turn gate finds no actions left.
        bridge = _bridge()
        meta = {}
        plan = [{"uid": 0, "move": None, "kind": "weapon", "weapon": "Prime_Lightning_A",
                 "target": [4, 2], "target2": None}]
        bj = json.dumps(bridge)
        sim = json.loads(self.engine.simulate(bj, json.dumps(plan)))
        plan2, sim2 = cpp_solver._end_idle_units(self.engine, bj, bridge, plan, sim, meta)
        self.assertEqual(sorted(meta["idle_units_skipped"]), [1, 2])
        self.assertEqual(len(sim2["steps"]), 3)
        enriched = cpp_solver.build_enriched(bridge, sim2, plan2, [], bridge["turn"],
                                             bridge["total_turns"], 2**31 - 1)
        last = {u["uid"]: u for u in enriched["predicted_states"][-1]["post_attack"]["units"]}
        self.assertFalse(last[0]["active"] or last[1]["active"] or last[2]["active"])
        acts = cpp_solver.to_mech_actions(plan2, sim2, bridge)
        self.assertTrue(acts[1].description.endswith("skip"))
        self.assertEqual(acts[1].weapon, "None")

    def test_move_only_last_entry_predicts_skip(self):
        bridge = _bridge()
        plan = [{"uid": 2, "move": [1, 5], "kind": "none", "weapon": "", "target": None,
                 "target2": None}]
        sim = json.loads(self.engine.simulate(json.dumps(bridge), json.dumps(plan)))
        self.assertEqual(sim["refused"], -1, sim.get("refused_reason"))
        enriched = cpp_solver.build_enriched(bridge, sim, plan, [], bridge["turn"],
                                             bridge["total_turns"], 2**31 - 1)
        units = {u["uid"]: u for u in enriched["predicted_states"][0]["post_attack"]["units"]}
        self.assertFalse(units[2]["active"])  # the bot SKIPs it
        self.assertIsNotNone(enriched["predicted_states"][0]["post_move"])


if __name__ == "__main__":
    unittest.main()
