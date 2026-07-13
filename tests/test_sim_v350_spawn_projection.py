"""Simulator v350 projected spawn-marker lifecycle regressions."""

from __future__ import annotations

import json

import pytest

try:
    import itb_solver  # type: ignore
    _HAVE_WHEEL = True
except ImportError:
    _HAVE_WHEEL = False


def _board(*, units: list[dict] | None = None) -> dict:
    return {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "remaining_spawns": 2,
        "spawning_tiles": [[2, 2], [5, 5]],
        "tiles": [],
        "units": units or [],
    }


def _decode_board(raw: str) -> tuple[dict, dict]:
    out = json.loads(raw)
    board_json = out["board_json"]
    board = json.loads(board_json) if isinstance(board_json, str) else board_json
    return out, board


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_project_plan_consumes_unblocked_spawn_markers():
    out, board = _decode_board(
        itb_solver.project_plan(json.dumps(_board()), "[]")
    )

    assert out["spawn_points"] == []
    assert board["spawning_tiles"] == []
    # The positive sentinel remains conservative pressure for the spawned Vek
    # whose identity/movement this bounded projection does not materialize.
    assert board["remaining_spawns"] == 2


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_project_plan_retains_only_marker_blocked_at_emergence():
    blocker = {
        "uid": 1,
        "type": "PunchMech",
        "x": 2,
        "y": 2,
        "hp": 1,
        "max_hp": 3,
        "team": 1,
        "mech": True,
        "move": 3,
        "base_move": 3,
        "active": True,
        "weapons": ["Prime_Punchmech"],
    }

    out, board = _decode_board(
        itb_solver.project_plan(json.dumps(_board(units=[blocker])), "[]")
    )

    assert out["action_result"]["spawns_blocked"] == 1
    assert out["spawn_points"] == [[2, 2]]
    assert board["spawning_tiles"] == [[2, 2]]
    assert all(unit["uid"] != 1 for unit in board["units"])


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_project_plan_scenarios_use_consumed_marker_set():
    raw = itb_solver.project_plan_scenarios(
        json.dumps(_board()),
        "[]",
        3,
    )
    scenarios = json.loads(raw)["scenarios"]

    assert scenarios
    for scenario in scenarios:
        board_json = scenario["board_json"]
        board = json.loads(board_json) if isinstance(board_json, str) else board_json
        assert scenario["spawn_points"] == []
        assert board["spawning_tiles"] == []


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_replay_final_board_consumes_unblocked_spawn_markers():
    blocker = {
        "uid": 1,
        "type": "PunchMech",
        "x": 2,
        "y": 2,
        "hp": 1,
        "max_hp": 3,
        "team": 1,
        "mech": True,
        "move": 3,
        "base_move": 3,
        "active": False,
        "weapons": ["Prime_Punchmech"],
    }

    replay = json.loads(
        itb_solver.replay_solution(json.dumps(_board(units=[blocker])), "[]")
    )

    assert replay["post_player_board"]["spawning_tiles"] == [[2, 2], [5, 5]]
    assert replay["final_board"]["spawning_tiles"] == [[2, 2]]
    assert replay["final_board"]["units"] == []
