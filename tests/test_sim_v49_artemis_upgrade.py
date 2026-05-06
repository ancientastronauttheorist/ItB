"""Simulator v49 Artemis Artillery Buildings Immune regression tests."""

from __future__ import annotations

import json

import pytest

try:
    import itb_solver  # type: ignore
    _HAVE_WHEEL = True
except ImportError:
    _HAVE_WHEEL = False


def _project(board: dict, plan: list[dict]) -> dict:
    raw = itb_solver.project_plan(json.dumps(board), json.dumps(plan))
    out = json.loads(raw)
    board_json = out["board_json"]
    return json.loads(board_json) if isinstance(board_json, str) else board_json


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_artemis_a_direct_building_damage_is_zero():
    board = {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "spawning_tiles": [],
        "tiles": [{
            "x": 3,
            "y": 5,
            "terrain": "building",
            "building_hp": 1,
        }],
        "units": [{
            "uid": 1, "type": "ArtiMech", "x": 3, "y": 3,
            "hp": 3, "max_hp": 3, "team": 1, "mech": True,
            "move": 3, "base_move": 3, "active": True,
            "weapons": ["Ranged_Artillerymech_A"],
        }],
    }

    post = _project(board, [{
        "mech_uid": 1,
        "move_to": [3, 3],
        "weapon_id": "Ranged_Artillerymech_A",
        "target": [3, 5],
    }])

    building = next(t for t in post["tiles"] if t["x"] == 3 and t["y"] == 5)
    assert building["building_hp"] == 1
    assert post["grid_power"] == 5


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_artemis_a_push_bump_can_still_damage_building():
    board = {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "spawning_tiles": [],
        "tiles": [{
            "x": 3,
            "y": 7,
            "terrain": "building",
            "building_hp": 1,
        }],
        "units": [
            {
                "uid": 1, "type": "ArtiMech", "x": 3, "y": 3,
                "hp": 3, "max_hp": 3, "team": 1, "mech": True,
                "move": 3, "base_move": 3, "active": True,
                "weapons": ["Ranged_Artillerymech_A"],
            },
            {
                "uid": 2, "type": "Scorpion1", "x": 3, "y": 6,
                "hp": 2, "max_hp": 2, "team": 2, "move": 3,
                "base_move": 3, "pushable": True,
                "weapons": ["ScorpionAtk1"],
            },
        ],
    }

    post = _project(board, [{
        "mech_uid": 1,
        "move_to": [3, 3],
        "weapon_id": "Ranged_Artillerymech_A",
        "target": [3, 5],
    }])

    building = next(t for t in post["tiles"] if t["x"] == 3 and t["y"] == 7)
    assert building["terrain"] == "rubble"
    assert building.get("building_hp", 0) == 0
    assert post["grid_power"] == 4
