"""Step-function scoring for the "Kill N enemies" bonus objective.

BONUS_KILL_FIVE (mission.BonusObjs id=6) grants +1 rep star when the team
kills at least N Vek in the mission (N = 5 Easy / 7 Normal/Hard). The
evaluator fires the bonus exactly once — on the plan whose simulated kills
cross the cumulative target (pre-turn kills_done < target AND
post-turn kills_done + this_plan_kills ≥ target).

This matters because without cumulative tracking the solver sees only
per-turn kills scaled by enemy_killed (500 × future_factor) and has no
incentive to push through the rep threshold when easier kills elsewhere
score the same.
"""
from __future__ import annotations

from src.model.board import Board
from src.solver.evaluate import evaluate, evaluate_breakdown, EvalWeights


def _empty_board(kill_target: int = 0, kills_done: int = 0) -> Board:
    b = Board()
    b.grid_power = 5
    b.grid_power_max = 7
    b.mission_kill_target = kill_target
    b.mission_kills_done = kills_done
    return b


def _score(board: Board, kills: int) -> float:
    return evaluate(board, spawn_points=[], weights=EvalWeights(),
                    current_turn=2, total_turns=5, kills=kills)


def test_bonus_fires_when_plan_crosses_target():
    """kills_done=5, target=7, this plan kills 2 → cross → bonus fires."""
    b = _empty_board(kill_target=7, kills_done=5)
    with_bonus = _score(b, kills=2)      # 5 + 2 = 7 → cross
    without_bonus = _score(b, kills=1)   # 5 + 1 = 6 → below target
    diff = with_bonus - without_bonus
    # The 2-kill plan should score higher by the bonus PLUS the extra
    # kill's base value (kill_value scales with ff). Bonus alone is
    # 15000 × (0.25 + 0.75 × ff), ff at turn 2 / 5-turn mission ≈ 0.67
    # → ~11300. Assert we see at least most of that delta on top of the
    # one extra kill's base score.
    assert diff > 10_000, (
        f"Crossing the kill target should fire the bonus. "
        f"with={with_bonus}, without={without_bonus}, diff={diff}"
    )


def test_bonus_does_not_fire_if_target_already_hit():
    """kills_done=7, target=7 → already achieved → no additional bonus."""
    b = _empty_board(kill_target=7, kills_done=7)
    extra_kill = _score(b, kills=1)    # 7+1=8, target already hit
    no_kill = _score(b, kills=0)       # 7+0=7, target already hit
    # Only the per-turn kill_value should differentiate these — no
    # mission-kill bonus because the pre-turn count is already ≥ target.
    # Per-turn kill_value is ~500 × scaled(ff) ≈ a few hundred, way less
    # than the 15k bonus. Assert the diff is small.
    diff = extra_kill - no_kill
    assert diff < 5_000, (
        f"Bonus must not re-fire when target was already achieved. "
        f"extra={extra_kill}, none={no_kill}, diff={diff}"
    )


def test_bonus_does_not_fire_below_target():
    """kills_done=2, target=7, plan kills 3 → 5<7 → no bonus."""
    b = _empty_board(kill_target=7, kills_done=2)
    with_3 = _score(b, kills=3)   # 2+3 = 5, below target
    with_0 = _score(b, kills=0)
    diff = with_3 - with_0
    # 3 kills × per-turn kill_value ≈ 1500, no bonus.
    assert diff < 5_000, (
        f"Bonus should not fire below target. "
        f"3kills={with_3}, 0kills={with_0}, diff={diff}"
    )


def test_target_zero_neutralizes_scoring():
    """mission_kill_target=0 (missions without this bonus) → no-op."""
    b = _empty_board(kill_target=0, kills_done=0)
    s_high = _score(b, kills=7)   # would cross if target were 7
    s_low = _score(b, kills=0)
    # Only per-turn kill_value differentiates — small, not +15k.
    assert s_high - s_low < 10_000


def test_board_copy_preserves_kill_fields():
    """Board.copy() must preserve mission_kill_target/done for search branches."""
    b = _empty_board(kill_target=7, kills_done=3)
    c = b.copy()
    assert c.mission_kill_target == 7
    assert c.mission_kills_done == 3


def test_breakdown_reports_kill_bonus():
    b = _empty_board(kill_target=7, kills_done=5)
    bd = evaluate_breakdown(b, spawn_points=[], weights=EvalWeights(),
                            current_turn=2, total_turns=5, kills=3)
    info = bd["mission_kill_bonus"]
    assert info["target"] == 7
    assert info["done_pre_turn"] == 5
    assert info["kills_this_turn"] == 3
    assert info["score"] > 0

    b_below = _empty_board(kill_target=7, kills_done=2)
    bd_below = evaluate_breakdown(b_below, spawn_points=[], weights=EvalWeights(),
                                  current_turn=2, total_turns=5, kills=3)
    assert bd_below["mission_kill_bonus"]["score"] == 0.0


def test_bridge_data_missing_fields_defaults_to_zero():
    """Older bridges (pre-install) don't emit these fields. Must not crash."""
    data = {
        "tiles": [{"x": x, "y": y, "terrain": "ground"} for x in range(8) for y in range(8)],
        "units": [],
        "grid_power": 5,
        "turn": 1,
        # no mission_kill_target, no mission_kills_done, no mission_id
    }
    b = Board.from_bridge_data(data)
    assert b.mission_kill_target == 0
    assert b.mission_kills_done == 0
