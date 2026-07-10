"""Regression coverage for Force Swap lookahead serialization."""

from __future__ import annotations

import json

import pytest

from src.loop.commands import _solution_plan_payload
from src.solver.solver import MechAction, Solution

try:
    import itb_solver  # type: ignore

    _HAVE_WHEEL = True
except ImportError:
    _HAVE_WHEEL = False


def _force_swap_solution() -> Solution:
    return Solution(actions=[MechAction(
        mech_uid=1,
        mech_type="ExchangeMech",
        move_to=(3, 3),
        weapon="Science_TC_SwapOther",
        target=(3, 4),
        target2=(6, 2),
        description="Force Swap",
    )])


def _force_swap_board() -> dict:
    return {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "spawning_tiles": [],
        "tiles": [],
        "units": [
            {
                "uid": 1,
                "type": "ExchangeMech",
                "x": 3,
                "y": 3,
                "hp": 2,
                "max_hp": 2,
                "team": 1,
                "mech": True,
                "move": 3,
                "base_move": 3,
                "active": True,
                "weapons": ["Science_TC_SwapOther"],
            },
            {
                "uid": 2,
                "type": "Scorpion1",
                "x": 3,
                "y": 4,
                "hp": 2,
                "max_hp": 2,
                "team": 2,
                "move": 3,
                "base_move": 3,
                "pushable": True,
                "weapons": ["Scorpion1Atk1"],
            },
            {
                "uid": 3,
                "type": "Firefly1",
                "x": 6,
                "y": 2,
                "hp": 3,
                "max_hp": 3,
                "team": 2,
                "move": 2,
                "base_move": 2,
                "pushable": True,
                "weapons": ["Firefly1Atk1"],
            },
        ],
    }


def test_solution_plan_payload_preserves_force_swap_second_target():
    payload = _solution_plan_payload(_force_swap_solution())

    assert payload == [{
        "mech_uid": 1,
        "mech_type": "ExchangeMech",
        "move_to": [3, 3],
        "weapon_id": "Science_TC_SwapOther",
        "target": [3, 4],
        "target2": [6, 2],
    }]


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_serialized_force_swap_plan_projects_both_targets():
    payload = _solution_plan_payload(_force_swap_solution())

    raw = itb_solver.project_plan(
        json.dumps(_force_swap_board()),
        json.dumps(payload),
    )
    projected = json.loads(json.loads(raw)["board_json"])
    positions = {
        unit["uid"]: (unit["x"], unit["y"])
        for unit in projected["units"]
    }

    # A missing target2 produces invalid_force_swap_missing_second_target and
    # leaves both Vek in place. Successful projection must swap them instead.
    assert positions[2] == (6, 2)
    assert positions[3] == (3, 4)
