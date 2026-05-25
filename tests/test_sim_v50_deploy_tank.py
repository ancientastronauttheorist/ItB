"""Simulator v50 controllable Archive Tank regressions."""

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
def test_deploy_tank_stock_cannon_pushes_without_damage():
    board = {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "spawning_tiles": [],
        "tiles": [],
        "units": [
            {
                "uid": 40, "type": "Archive_Tank", "x": 3, "y": 3,
                "hp": 1, "max_hp": 1, "team": 1, "mech": False,
                "move": 4, "base_move": 4, "active": True,
                "weapons": ["Deploy_TankShot"],
            },
            {
                "uid": 2, "type": "Scorpion1", "x": 3, "y": 5,
                "hp": 3, "max_hp": 3, "team": 2, "move": 3,
                "base_move": 3, "pushable": True,
                "weapons": ["ScorpionAtk1"],
            },
        ],
    }

    post = _project(board, [{
        "mech_uid": 40,
        "move_to": [3, 3],
        "weapon_id": "Deploy_TankShot",
        "target": [3, 5],
    }])

    enemy = next(u for u in post["units"] if u["uid"] == 2)
    assert (enemy["x"], enemy["y"]) == (3, 6)
    assert enemy["hp"] == 3
