"""Tests for the `remaining_spawn_penalty` scoring term.

The evaluator does not materialize or simulate queued Vek spawns: it only
models blocking damage to mechs sitting on spawn tiles. `remaining_spawn_penalty`
compensates for that gap with a flat per-spawn penalty that collapses to 0
on the final turn (via future_factor).

Python is the source of truth for this test file; the Rust mirror is
covered by cargo tests under rust_solver/src/evaluate.rs#tests.
"""
from __future__ import annotations

from src.model.board import Board, BoardTile
from src.solver.evaluate import (
    DEFAULT_WEIGHTS,
    EvalWeights,
    evaluate,
    evaluate_breakdown,
)


def _make_board() -> Board:
    """Minimal viable board for scoring: grid alive, one building, no units."""
    b = Board()
    b.grid_power = 5
    b.grid_power_max = 7
    # One building so the board has nonzero "stuff to defend".
    b.tiles[3][3] = BoardTile(terrain="building", building_hp=1)
    return b


def test_remaining_spawn_penalty_matches_per_spawn_magnitude() -> None:
    """remaining_spawns=2 should score lower than remaining_spawns=0 by
    approximately 2 * remaining_spawn_penalty (at ff=1.0, turn 1 of 5)."""
    b = _make_board()
    s0 = evaluate(b, current_turn=1, total_turns=5, remaining_spawns=0)
    s2 = evaluate(b, current_turn=1, total_turns=5, remaining_spawns=2)
    delta = s0 - s2
    expected = 2 * DEFAULT_WEIGHTS.remaining_spawn_penalty  # ff=1.0 on turn 1
    assert abs(delta - expected) < 1.0, (
        f"Expected s0-s2 ~= {expected}, got {delta:.1f} "
        f"(s0={s0:.1f}, s2={s2:.1f})"
    )


def test_remaining_spawn_penalty_zero_on_final_turn() -> None:
    """On the final turn (ff=0), the penalty must collapse to 0 regardless
    of remaining_spawns value."""
    b = _make_board()
    s0 = evaluate(b, current_turn=5, total_turns=5, remaining_spawns=0)
    s3 = evaluate(b, current_turn=5, total_turns=5, remaining_spawns=3)
    # ff=0 at current_turn=total_turns, so penalty term is zeroed out.
    assert abs(s0 - s3) < 1.0, (
        f"Final turn should zero the penalty but got delta={s0 - s3:.1f}"
    )


def test_remaining_spawn_penalty_respects_default_sentinel() -> None:
    """The default sentinel (2**31-1, meaning 'unknown') must NOT apply the
    penalty — otherwise un-bridged callers get their score annihilated."""
    b = _make_board()
    s_sentinel = evaluate(b, current_turn=1, total_turns=5)  # default sentinel
    s_zero = evaluate(b, current_turn=1, total_turns=5, remaining_spawns=0)
    assert abs(s_sentinel - s_zero) < 1.0, (
        f"Sentinel should match remaining_spawns=0 (no penalty), "
        f"got sentinel={s_sentinel:.1f} vs zero={s_zero:.1f}"
    )


def test_remaining_spawn_penalty_caps_at_eight() -> None:
    """Bogus large values are capped at 8 to keep the score bounded."""
    b = _make_board()
    s8 = evaluate(b, current_turn=1, total_turns=5, remaining_spawns=8)
    s100 = evaluate(b, current_turn=1, total_turns=5, remaining_spawns=100)
    assert abs(s8 - s100) < 1.0, (
        f"Cap at 8 should flatten large values, got s8={s8:.1f}, s100={s100:.1f}"
    )


def test_remaining_spawn_penalty_in_breakdown() -> None:
    """evaluate_breakdown exposes the penalty as its own component."""
    b = _make_board()
    br = evaluate_breakdown(b, current_turn=1, total_turns=5, remaining_spawns=3)
    assert "remaining_spawns" in br
    assert br["remaining_spawns"]["count"] == 3
    # ff=1.0 on turn 1 → full penalty applied, negative sign.
    expected = -3 * DEFAULT_WEIGHTS.remaining_spawn_penalty
    assert abs(br["remaining_spawns"]["score"] - expected) < 1.0


def test_remaining_spawn_penalty_zero_when_weight_zero() -> None:
    """With the weight zeroed, the penalty must disappear entirely
    (useful for tuning or for achievement strategies that want it off)."""
    b = _make_board()
    w = EvalWeights(remaining_spawn_penalty=0)
    s0 = evaluate(b, weights=w, current_turn=1, total_turns=5, remaining_spawns=0)
    s5 = evaluate(b, weights=w, current_turn=1, total_turns=5, remaining_spawns=5)
    assert abs(s0 - s5) < 1.0
