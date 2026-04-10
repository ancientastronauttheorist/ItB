"""Weight auto-tuning engine for the solver.

Finds better EvalWeights by replaying recorded boards with candidate
weights and measuring outcomes with a fixed (weight-independent) scorer.

Uses random search + coordinate refinement — no external optimization
libraries required. Upgradable to Bayesian/CMA-ES when scikit-optimize
or cma are available.

Tuning is per-turn: for each recorded board state, "do these weights
produce a better single-turn outcome?" This avoids the broken
credit-assignment problem of multi-turn optimization.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

# The 5 most impactful weights to tune, with search ranges.
# All other weights are held at their defaults from active.json.
TUNABLE_WEIGHTS = {
    "building_alive": (5000.0, 20000.0),   # default 10000
    "enemy_killed":   (100.0, 2000.0),     # default 500
    "spawn_blocked":  (100.0, 1500.0),     # default 400
    "mech_hp":        (20.0, 500.0),       # default 100
    "grid_power":     (1000.0, 15000.0),   # default 5000
}


def _load_base_weights() -> dict:
    """Load base weights from active.json."""
    weights_path = Path(__file__).parent.parent.parent / "weights" / "active.json"
    if weights_path.exists():
        with open(weights_path) as f:
            return json.load(f).get("weights", {})
    return {}


def _random_weights(base: dict) -> dict:
    """Generate a random weight vector within search ranges."""
    w = dict(base)
    for name, (lo, hi) in TUNABLE_WEIGHTS.items():
        w[name] = random.uniform(lo, hi)
    return w


def _perturb_weight(base: dict, name: str, factor: float) -> dict:
    """Create a copy with one weight multiplied by factor."""
    w = dict(base)
    lo, hi = TUNABLE_WEIGHTS[name]
    w[name] = max(lo, min(hi, w[name] * factor))
    return w


def evaluate_weights(
    weights: dict,
    board_files: list[Path],
    time_limit: float = 5.0,
) -> float:
    """Score a weight configuration across all boards.

    For each board: Rust solver with these weights → replay_solution → fixed_score.
    Returns mean fixed_score across all boards.
    """
    from src.loop.commands import (
        _load_board_from_recording, _solve_with_rust, _fixed_score,
    )
    from src.solver.solver import replay_solution

    total_score = 0.0
    tested = 0

    for bf in board_files:
        try:
            bridge_data, board, spawns, _ = _load_board_from_recording(bf)
            solution = _solve_with_rust(bridge_data, time_limit, weights=weights)

            if solution.actions:
                enriched = replay_solution(board, solution, spawns)
                if enriched and "predicted_outcome" in enriched:
                    total_score += _fixed_score(enriched["predicted_outcome"])
                    tested += 1
                    continue

            # Empty solution — score the board as-is (no improvement)
            from src.loop.commands import _capture_board_summary
            # Can't capture live board summary without bridge, so score 0 for empty
            tested += 1

        except Exception:
            continue

    return total_score / tested if tested > 0 else 0.0


def tune_weights(
    board_files: list[Path],
    iterations: int = 100,
    time_limit: float = 5.0,
) -> dict:
    """Find better weights via random search + coordinate refinement.

    Phase 1 (50% of iterations): Random search — sample random weight
    vectors, evaluate, keep best.
    Phase 2 (50% of iterations): Coordinate refinement — for each of
    5 tunable weights, try perturbations of current best.

    Returns dict with best_weights, best_score, baseline_score, history.
    """
    base = _load_base_weights()

    # Evaluate baseline
    print(f"  Evaluating baseline weights on {len(board_files)} boards...")
    baseline_score = evaluate_weights(base, board_files, time_limit)
    print(f"  Baseline score: {baseline_score:.1f}")

    best_weights = dict(base)
    best_score = baseline_score
    history = [{"iteration": 0, "score": baseline_score, "phase": "baseline"}]

    # Phase 1: Random search
    random_iters = iterations // 2
    print(f"\n  Phase 1: Random search ({random_iters} iterations)...")

    for i in range(1, random_iters + 1):
        candidate = _random_weights(base)
        score = evaluate_weights(candidate, board_files, time_limit)

        if score > best_score:
            improvement = score - best_score
            best_weights = candidate
            best_score = score
            print(f"    [{i}] New best: {score:.1f} (+{improvement:.1f})")
            history.append({
                "iteration": i, "score": score, "phase": "random",
                "weights": {k: candidate[k] for k in TUNABLE_WEIGHTS},
            })

        if i % 10 == 0 and i != random_iters:
            print(f"    [{i}/{random_iters}] Best so far: {best_score:.1f}")

    print(f"  Phase 1 complete. Best: {best_score:.1f}")

    # Phase 2: Coordinate refinement
    refine_iters = iterations - random_iters
    perturbations = [0.5, 0.75, 0.9, 1.1, 1.25, 1.5]
    print(f"\n  Phase 2: Coordinate refinement ({refine_iters} iterations)...")

    iter_count = 0
    improved_in_pass = True

    while iter_count < refine_iters and improved_in_pass:
        improved_in_pass = False
        for name in TUNABLE_WEIGHTS:
            if iter_count >= refine_iters:
                break
            for factor in perturbations:
                if iter_count >= refine_iters:
                    break
                iter_count += 1
                candidate = _perturb_weight(best_weights, name, factor)
                score = evaluate_weights(candidate, board_files, time_limit)

                if score > best_score:
                    improvement = score - best_score
                    best_weights = candidate
                    best_score = score
                    improved_in_pass = True
                    print(f"    [{random_iters + iter_count}] {name} x{factor}: "
                          f"{score:.1f} (+{improvement:.1f})")
                    history.append({
                        "iteration": random_iters + iter_count,
                        "score": score, "phase": "refine",
                        "param": name, "factor": factor,
                        "weights": {k: best_weights[k] for k in TUNABLE_WEIGHTS},
                    })

    print(f"  Phase 2 complete. Best: {best_score:.1f}")

    return {
        "best_weights": best_weights,
        "best_score": best_score,
        "baseline_score": baseline_score,
        "improvement": best_score - baseline_score,
        "improvement_pct": ((best_score - baseline_score) / baseline_score * 100
                            if baseline_score > 0 else 0),
        "iterations_used": random_iters + iter_count,
        "boards_tested": len(board_files),
        "history": history,
        "tuned_params": {k: best_weights[k] for k in TUNABLE_WEIGHTS},
    }
