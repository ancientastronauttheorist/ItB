"""Simulator v48 repair-platform regressions."""

from __future__ import annotations

import json

import pytest

from src.model.board import Board
from src.solver.evaluate import EvalWeights, evaluate, evaluate_breakdown

try:
    import itb_solver  # type: ignore
    _HAVE_WHEEL = True
except ImportError:
    _HAVE_WHEEL = False


def _project(board: dict, plan: list[dict]) -> tuple[dict, dict]:
    raw = itb_solver.project_plan(json.dumps(board), json.dumps(plan))
    out = json.loads(raw)
    board_json = out["board_json"]
    post = json.loads(board_json) if isinstance(board_json, str) else board_json
    return out, post


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_repair_platform_heals_consumes_and_counts_objective_progress():
    board = {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "mission_id": "Mission_Repair",
        "repair_platform_target": 3,
        "repair_platforms_used": 2,
        "spawning_tiles": [],
        "tiles": [{"x": 3, "y": 3, "terrain": "ground", "item": "Item_Repair_Mine"}],
        "units": [{
            "uid": 1, "type": "PunchMech", "x": 3, "y": 2,
            "hp": 1, "max_hp": 3, "team": 1, "mech": True,
            "move": 3, "base_move": 3, "active": True,
            "weapons": ["Prime_Punchmech"],
        }],
    }

    out, post = _project(board, [{
        "mech_uid": 1,
        "move_to": [3, 3],
        "weapon_id": "",
        "target": [3, 3],
    }])

    unit = next(u for u in post["units"] if u["uid"] == 1)
    assert unit["hp"] == 5
    assert post["repair_platforms_used"] == 3
    assert out["action_result"]["repair_platforms_used"] == 1
    tile = next((t for t in post["tiles"] if t["x"] == 3 and t["y"] == 3), {})
    assert not tile.get("repair_platform", False)
    assert tile.get("item") != "Item_Repair_Mine"


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_repair_platform_caps_at_max_hp_plus_two_not_flat_five():
    board = {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "mission_id": "Mission_Repair",
        "repair_platform_target": 3,
        "repair_platforms_used": 0,
        "spawning_tiles": [],
        "tiles": [{"x": 3, "y": 3, "terrain": "ground", "item": "Item_Repair_Mine"}],
        "units": [{
            "uid": 1, "type": "JetMech", "x": 3, "y": 2,
            "hp": 4, "max_hp": 2, "team": 1, "mech": True,
            "move": 5, "base_move": 5, "active": True,
            "weapons": ["Brute_Jetmech"],
        }],
    }

    _, post = _project(board, [{
        "mech_uid": 1,
        "move_to": [3, 3],
        "weapon_id": "",
        "target": [3, 3],
    }])

    unit = next(u for u in post["units"] if u["uid"] == 1)
    assert unit["hp"] == 4


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_repair_platform_roundtrips_when_unused():
    board = {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "mission_id": "Mission_Repair",
        "repair_platform_target": 3,
        "repair_platforms_used": 1,
        "spawning_tiles": [],
        "tiles": [{"x": 4, "y": 4, "terrain": "ground", "repair_platform": True}],
        "units": [],
    }

    _, post = _project(board, [])

    tile = next(t for t in post["tiles"] if t["x"] == 4 and t["y"] == 4)
    assert tile["repair_platform"] is True
    assert tile["item"] == "Item_Repair_Mine"
    assert post["repair_platform_target"] == 3
    assert post["repair_platforms_used"] == 1


def test_bridge_item_sets_python_repair_platform_and_copy_preserves_progress():
    board = Board.from_bridge_data({
        "grid_power": 5,
        "tiles": [{"x": 2, "y": 5, "terrain": "ground", "item": "Item_Repair_Mine"}],
        "units": [],
        "repair_platform_target": 3,
        "repair_platforms_used": 2,
    })

    assert board.tile(2, 5).repair_platform is True
    copied = board.copy()
    assert copied.tile(2, 5).repair_platform is True
    assert copied.repair_platform_target == 3
    assert copied.repair_platforms_used == 2


def test_repair_objective_scoring_values_completion():
    incomplete = Board()
    incomplete.grid_power = 5
    incomplete.grid_power_max = 7
    incomplete.repair_platform_target = 3
    incomplete.repair_platforms_used = 2

    complete = incomplete.copy()
    complete.repair_platforms_used = 3

    kwargs = dict(
        spawn_points=[],
        weights=EvalWeights(),
        current_turn=2,
        total_turns=5,
        kills=0,
    )
    assert evaluate(complete, **kwargs) > evaluate(incomplete, **kwargs) + 5_000

    info = evaluate_breakdown(complete, **kwargs)["mission_repair_bonus"]
    assert info["target"] == 3
    assert info["used"] == 3
    assert info["threshold_score"] > 0
