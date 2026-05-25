"""Golden post-enemy replay checks for recorded prediction misses.

These tests replay the exact historical plan instead of re-solving. That
guards the simulator against dodging an old bug by choosing a different line.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.loop import commands
from src.model.board import Board

REPO = Path(__file__).resolve().parent.parent
RUN = REPO / "recordings" / "20260513_144310_771"


def _plan_from_solve(solve_rec: dict) -> list[dict]:
    plan = []
    for action in (solve_rec.get("data") or {}).get("actions") or []:
        move_to = action.get("move_to") or [255, 255]
        target = action.get("target") or [255, 255]
        plan.append({
            "mech_uid": int(action["mech_uid"]),
            "move_to": [int(move_to[0]), int(move_to[1])],
            "weapon_id": action.get("weapon_id") or action.get("weapon") or "None",
            "target": [int(target[0]), int(target[1])],
        })
    return plan


@pytest.mark.regression
def test_hq_turn2_webb_egg_recorded_plan_now_predicts_actual_post_enemy():
    board_path = RUN / "m11_turn_02_board.json"
    solve_path = RUN / "m11_turn_02_solve.json"
    post_path = RUN / "m11_turn_02_post_enemy.json"
    if not (board_path.exists() and solve_path.exists() and post_path.exists()):
        pytest.skip("HQ WebbEgg artifact not present in this checkout")

    import itb_solver

    board_rec = json.loads(board_path.read_text())
    solve_rec = json.loads(solve_path.read_text())
    post_rec = json.loads(post_path.read_text())
    bridge = (board_rec.get("data") or {}).get("bridge_state")
    actual = (post_rec.get("data") or {}).get("actual_outcome") or {}
    assert bridge and actual

    replay = json.loads(
        itb_solver.replay_solution(
            json.dumps(bridge),
            json.dumps(_plan_from_solve(solve_rec)),
        )
    )
    final_board = replay.get("final_board") or {}
    summary = commands._capture_board_summary(
        Board.from_bridge_data(final_board),
        final_board,
    )
    summary.update(replay.get("predicted_outcome") or {})

    assert summary["grid_power"] == actual["grid_power"]
    assert summary["buildings_alive"] == actual["buildings_alive"]
    assert summary["building_hp_total"] == actual["building_hp_total"]
