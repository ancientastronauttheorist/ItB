"""grid_power evaluator contribution must be strictly monotonic in grid_power.

Regression for the Ice Forest defeat (2026-04-24): the old formula
`eff_grid * weights.grid_power * grid_multiplier` produced a non-monotonic
score curve (grid=3 with multiplier=3.0 scored higher than grid=5 with
multiplier=1.0), causing the solver to prefer plans ending at lower grid
over plans preserving grid. Current formula splits into a linear base
reward + below-threshold urgency penalty.
"""

from __future__ import annotations

from src.model.board import Board, BoardTile
from src.solver.evaluate import evaluate, EvalWeights


def _board_at_grid(grid: int, grid_max: int = 7) -> Board:
    """Minimal board with the given grid_power. No units, no buildings —
    isolates the grid_power scoring term."""
    b = Board()
    b.grid_power = grid
    b.grid_power_max = grid_max
    return b


def test_grid_power_score_is_strictly_monotonic():
    """Score must be strictly increasing as grid_power rises from 0 to max."""
    w = EvalWeights()
    prev_score = None
    prev_g = None
    for g in range(0, 8):
        score = evaluate(_board_at_grid(g), spawn_points=[], weights=w,
                         current_turn=2, total_turns=5)
        if prev_score is not None:
            assert score > prev_score, (
                f"grid={g} score={score} but grid={prev_g} score={prev_score} "
                f"— not monotonic! This is the exact bug that cost Ice Forest."
            )
        prev_score = score
        prev_g = g


def test_grid_drop_is_always_penalized():
    """A plan ending at grid=N must always score lower than one ending at
    grid=N+1 for all N in [0, grid_max). Covers the specific pathology where
    grid=3 used to beat grid=5."""
    w = EvalWeights()
    for n in range(0, 7):
        lower = evaluate(_board_at_grid(n), spawn_points=[], weights=w,
                         current_turn=2, total_turns=5)
        higher = evaluate(_board_at_grid(n + 1), spawn_points=[], weights=w,
                          current_turn=2, total_turns=5)
        assert higher > lower, f"grid={n+1} ({higher}) ≤ grid={n} ({lower})"


def test_capacity_penalty_is_convex_in_gap():
    """Capacity-loss penalty must penalize multi-grid bleeds super-linearly.

    Regression for the "flat plateau" bug (Run-2/Run-3 Pinnacle bleed): each
    grid in 4..=max was worth only 5000, so the solver willingly traded grid
    for any tactical gain >5k, sliding from 6→2 across an island. Convex
    capacity_penalty term ensures the marginal cost of the 2nd grid lost
    exceeds the marginal cost of the 1st, etc.
    """
    w = EvalWeights()
    # Marginal costs of dropping 1 grid: cost(g) = score(g+1) - score(g).
    margins = []
    for g in range(0, 7):
        lower = evaluate(_board_at_grid(g), spawn_points=[], weights=w,
                         current_turn=2, total_turns=5)
        higher = evaluate(_board_at_grid(g + 1), spawn_points=[], weights=w,
                          current_turn=2, total_turns=5)
        margins.append(higher - lower)
    # Marginal cost of dropping the Nth grid (counting down from full grid_max=7)
    # must be non-decreasing as we drop further. margins[6] = 7→6 cost,
    # margins[5] = 6→5, etc. Reverse so margins_desc[i] is "cost of i-th drop".
    margins_desc = list(reversed(margins))
    for i in range(1, len(margins_desc)):
        assert margins_desc[i] >= margins_desc[i - 1], (
            f"marginal cost of {i+1}-th grid drop ({margins_desc[i]:.0f}) is less "
            f"than {i}-th drop ({margins_desc[i-1]:.0f}) — convexity violated. "
            f"This is the flat-plateau bug; the convex term should sting more "
            f"each step."
        )


def test_capacity_penalty_disabled_recovers_old_curve():
    """Setting grid_capacity_penalty=0 disables the convex term entirely.

    Lets the auto-tuner (or a session experiment) revert to the pre-fix
    curve without code changes. Provides a clean A/B knob.
    """
    w_off = EvalWeights()
    w_off.grid_capacity_penalty = 0.0
    # With penalty off, grid=N+1 should beat grid=N by exactly w.grid_power
    # (5000) for all N >= crisis_threshold (no urgency penalty either).
    diff_5_6 = (evaluate(_board_at_grid(6), spawn_points=[], weights=w_off,
                         current_turn=2, total_turns=5)
                - evaluate(_board_at_grid(5), spawn_points=[], weights=w_off,
                           current_turn=2, total_turns=5))
    diff_6_7 = (evaluate(_board_at_grid(7), spawn_points=[], weights=w_off,
                         current_turn=2, total_turns=5)
                - evaluate(_board_at_grid(6), spawn_points=[], weights=w_off,
                           current_turn=2, total_turns=5))
    assert abs(diff_5_6 - 5000.0) < 1e-6
    assert abs(diff_6_7 - 5000.0) < 1e-6


def test_below_threshold_penalty_scales_with_urgency():
    """At crisis grid, the below-threshold penalty must be proportional to
    the urgency multiplier — more severe crisis → steeper penalty."""
    # Two evaluator configs: same everywhere except grid_urgency_medium.
    w_low = EvalWeights()
    w_low.grid_urgency_medium = 1.5

    w_high = EvalWeights()
    w_high.grid_urgency_medium = 5.0

    # At grid=3 (medium crisis), higher urgency should yield LOWER score.
    low_urgency_score = evaluate(_board_at_grid(3), spawn_points=[], weights=w_low,
                                 current_turn=2, total_turns=5)
    high_urgency_score = evaluate(_board_at_grid(3), spawn_points=[], weights=w_high,
                                  current_turn=2, total_turns=5)
    assert high_urgency_score < low_urgency_score, (
        f"higher urgency={w_high.grid_urgency_medium} should punish grid=3 "
        f"MORE than urgency={w_low.grid_urgency_medium}, but got "
        f"high={high_urgency_score} low={low_urgency_score}"
    )

    # At grid=5 (above threshold), urgency should not matter.
    low_urgency_safe = evaluate(_board_at_grid(5), spawn_points=[], weights=w_low,
                                current_turn=2, total_turns=5)
    high_urgency_safe = evaluate(_board_at_grid(5), spawn_points=[], weights=w_high,
                                 current_turn=2, total_turns=5)
    assert abs(high_urgency_safe - low_urgency_safe) < 1e-6, (
        "Above crisis threshold, urgency multiplier must not affect the "
        "grid_power score — the penalty is gated on eff_grid < threshold."
    )
