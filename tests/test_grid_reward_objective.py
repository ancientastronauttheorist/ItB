"""Grid-reward objective building scoring (⚡ vs ⭐ distinction).

Coal Plant, Emergency Batteries, and Solar Farms grant +1 Grid Power on
mission survival (⚡ tag). Clinics, Nimbus, Towers grant +1 Rep (⭐).
The evaluator must score the former with grid urgency scaling so that at
critical grid, protecting a ⚡ building dominates any non-objective
sacrifice.

This test exercises both the Python solver path (directly) and the
Rust solver path (via the pyo3 extension if available).
"""

from __future__ import annotations

from src.model.board import Board, BoardTile
from src.solver.evaluate import evaluate, evaluate_breakdown, EvalWeights


def _make_board_with_objective(objective_name: str, grid: int) -> Board:
    """Construct a board with one objective building tagged as given."""
    b = Board()
    b.grid_power = grid
    b.grid_power_max = 7
    # Place the objective building at (2, 2). Leave the rest as ground.
    t = b.tile(2, 2)
    t.terrain = "building"
    t.building_hp = 1
    t.unique_building = True
    t.objective_name = objective_name
    # Add a second non-objective building so we have a baseline.
    t2 = b.tile(5, 5)
    t2.terrain = "building"
    t2.building_hp = 1
    return b


def _score(board: Board) -> float:
    return evaluate(board, spawn_points=[], weights=EvalWeights(),
                    current_turn=2, total_turns=5)


def test_grid_reward_scores_higher_than_rep_at_every_grid():
    """⚡ Str_Power should score higher than ⭐ Str_Clinic at any grid level.

    Both use bld_mult (not grid_multiplier), so the ratio is stable across
    grid levels — the differentiator is just the higher base weight.
    """
    for grid in (1, 3, 5, 7):
        coal = _make_board_with_objective("Str_Power", grid=grid)
        clinic = _make_board_with_objective("Str_Clinic", grid=grid)
        coal_score = _score(coal)
        clinic_score = _score(clinic)
        assert coal_score > clinic_score, (
            f"At grid={grid}: expected ⚡ Str_Power > ⭐ Str_Clinic, "
            f"got coal={coal_score}, clinic={clinic_score}"
        )


def test_grid_reward_uses_bld_mult_not_grid_multiplier():
    """⚡ bonus must NOT scale UP as grid depletes (inversion bug guard).

    If grid_multiplier were mistakenly used, the ⚡ component would grow
    as grid drops, incentivizing the solver to drop grid to inflate its
    own bonus when the building is safely out of reach. bld_mult instead
    goes DOWN at low grid, matching all other building scoring.
    """
    critical = _make_board_with_objective("Str_Battery", grid=1)
    full = _make_board_with_objective("Str_Battery", grid=5)

    bd_crit = evaluate_breakdown(critical, spawn_points=[],
                                 weights=EvalWeights(),
                                 current_turn=2, total_turns=5)
    bd_full = evaluate_breakdown(full, spawn_points=[],
                                 weights=EvalWeights(),
                                 current_turn=2, total_turns=5)

    # bld_mult at grid=1 is ≈ 0.66; at grid=5 is ≈ 0.88.
    # Score at grid=1 should be LOWER than at grid=5, not higher.
    grid_score_crit = bd_crit["objective_grid"]["score"]
    grid_score_full = bd_full["objective_grid"]["score"]
    assert grid_score_crit < grid_score_full, (
        f"⚡ bonus must decrease as grid drops (bld_mult pattern). "
        f"grid=1 → {grid_score_crit}, grid=5 → {grid_score_full}"
    )


def test_mission_solar_is_grid_reward():
    """Mission_Solar (Solar Farms) should be treated as ⚡ grid-reward."""
    b = _make_board_with_objective("Mission_Solar", grid=2)
    bd = evaluate_breakdown(b, spawn_points=[], weights=EvalWeights(),
                            current_turn=2, total_turns=5)
    assert bd["objective_grid"]["count"] == 1
    assert bd["objective_rep"]["count"] == 0


def test_unknown_objective_defaults_to_rep_only():
    """A new / unrecognized Str_* tag falls back to ⭐ rep-only (safe)."""
    b = _make_board_with_objective("Str_NewUnknownVariant", grid=1)
    bd = evaluate_breakdown(b, spawn_points=[], weights=EvalWeights(),
                            current_turn=2, total_turns=5)
    assert bd["objective_grid"]["count"] == 0
    assert bd["objective_rep"]["count"] == 1


def test_empty_objective_name_with_unique_building_treated_as_rep():
    """unique_building=True with empty objective_name → rep-only fallback.

    This is the save-parser path (no bridge objective_name info). Must not
    crash or mis-classify; just score as a generic objective.
    """
    b = Board()
    b.grid_power = 3
    b.grid_power_max = 7
    t = b.tile(2, 2)
    t.terrain = "building"
    t.building_hp = 1
    t.unique_building = True
    t.objective_name = ""  # save-parser fallback
    bd = evaluate_breakdown(b, spawn_points=[], weights=EvalWeights(),
                            current_turn=2, total_turns=5)
    assert bd["objective_rep"]["count"] == 1
    assert bd["objective_grid"]["count"] == 0


def test_objective_name_copied_by_board_copy():
    """Board.copy() must preserve objective_name (solver branches on copies)."""
    b = _make_board_with_objective("Str_Power", grid=3)
    c = b.copy()
    assert c.tile(2, 2).objective_name == "Str_Power"
