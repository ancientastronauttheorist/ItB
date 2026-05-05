"""Simulator v47 web + repair regressions."""

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
def test_repair_extinguishes_current_tile_fire():
    board = {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "spawning_tiles": [],
        "tiles": [{"x": 3, "y": 3, "terrain": "ground", "fire": True}],
        "units": [{
            "uid": 1, "type": "PunchMech", "x": 3, "y": 3,
            "hp": 1, "max_hp": 3, "team": 1, "mech": True,
            "move": 3, "base_move": 3, "active": True, "fire": True,
            "weapons": ["Prime_Punchmech"],
        }],
    }

    post = _project(board, [{
        "mech_uid": 1,
        "move_to": [3, 3],
        "weapon_id": "_REPAIR",
        "target": [3, 3],
    }])

    unit = next(u for u in post["units"] if u["uid"] == 1)
    tile = next((t for t in post["tiles"] if t["x"] == 3 and t["y"] == 3), {})
    assert unit["hp"] == 2
    assert not unit.get("fire", False)
    assert not tile.get("fire", False)


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_push_breaks_pushed_units_own_web():
    board = {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "spawning_tiles": [],
        "tiles": [],
        "units": [
            {
                "uid": 1, "type": "PulseMech", "x": 3, "y": 3,
                "hp": 3, "max_hp": 3, "team": 1, "mech": True,
                "move": 3, "base_move": 3, "active": True,
                "weapons": ["Science_Repulse"],
            },
            {
                "uid": 2, "type": "PunchMech", "x": 3, "y": 2,
                "hp": 3, "max_hp": 3, "team": 1, "mech": True,
                "move": 0, "base_move": 3, "active": False,
                "web": True, "web_source_uid": 99,
                "weapons": ["Prime_Punchmech"],
            },
        ],
    }

    post = _project(board, [{
        "mech_uid": 1,
        "move_to": [3, 3],
        "weapon_id": "Science_Repulse",
        "target": [3, 3],
    }])

    unit = next(u for u in post["units"] if u["uid"] == 2)
    assert (unit["x"], unit["y"]) == (3, 1)
    assert not unit.get("web", False)
