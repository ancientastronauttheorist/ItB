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
    "building_alive":      (5000.0, 20000.0),    # default 10000
    "enemy_killed":        (100.0, 2000.0),      # default 500
    "spawn_blocked":       (100.0, 1500.0),      # default 400
    "mech_hp":             (20.0, 500.0),        # default 100
    "grid_power":          (1000.0, 15000.0),    # default 5000
    "building_bump_damage": (-15000.0, -2000.0), # default -8000
    "bld_grid_floor":      (0.3, 0.9),           # default 0.6
    "bld_grid_scale":      (0.0, 1.0),           # default 0.4
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
    failure_corpus: list[dict] = None,
    lambda_failure: float = 100.0,
) -> float:
    """Score a weight configuration across all boards.

    Hybrid objective:

        objective = mean_fixed_score - lambda_failure * fired_failure_count

    The mean fixed score is the headline signal — it tells the tuner
    whether a candidate is winning the average board. The failure penalty
    adds direct pressure to fix known failure cases without polluting
    the per-board score.

    ``lambda_failure`` is calibrated against the typical fixed-score
    range (~1240 with 8 buildings × 100 + 7 grid × 50 + 3 mechs × 30):
    100 means "one avoided failure ≈ one building." The plan v1's
    λ=10000 was ~100× too high and would have crushed the base signal.

    ``failure_corpus`` is an optional list of failure_db records. If
    omitted, the function falls back to pure mean_fixed_score (preserves
    backwards compat with the v1 tuner objective).
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
                enriched = replay_solution(bridge_data, solution, spawns)
                if enriched and "predicted_outcome" in enriched:
                    total_score += _fixed_score(enriched["predicted_outcome"])
                    tested += 1
                    continue

            # Empty solution counts as zero fixed_score (no improvement).
            tested += 1

        except Exception:
            continue

    base = total_score / tested if tested > 0 else 0.0

    if not failure_corpus:
        return base

    fired = count_fired_triggers(weights, failure_corpus, time_limit)
    return base - lambda_failure * fired


def count_fired_triggers(
    weights: dict,
    failure_corpus: list[dict],
    time_limit: float = 5.0,
) -> int:
    """For each unique tunable failure, replay it and count whether the
    same trigger still fires under the candidate weights.

    Dedup key: ``(run_id, mission, trigger)``. One cascade in one mission
    counts as one data point, not five. Records flagged
    ``auto_fixable_by_tuning == False`` are skipped (re-tuning weights
    can't fix a model gap or a search-budget timeout).

    Records that point at a missing or unreadable replay file are
    counted as "still firing" — being unable to evaluate is no better
    than evaluating to a failure, and we don't want the tuner to silently
    drop hard-to-load cases.
    """
    from src.loop.commands import _load_board_from_recording, _solve_with_rust
    from src.solver.solver import replay_solution
    from src.solver.analysis import detect_triggers
    from pathlib import Path as _Path

    seen: set[tuple] = set()
    count = 0
    root = _Path(__file__).resolve().parent.parent.parent

    for record in failure_corpus:
        if not record.get("auto_fixable_by_tuning", False):
            continue
        # Audit-mode runs (e.g. environment hazard verification) are
        # excluded from the tuner training corpus — their failures don't
        # represent normal play and would bias the optimizer.
        if "audit" in record.get("context", {}).get("tags", []):
            continue

        key = (record.get("run_id"), record.get("mission"),
               record.get("trigger"))
        if key in seen:
            continue
        seen.add(key)

        replay_rel = record.get("replay_file", "")
        if not replay_rel:
            count += 1
            continue
        replay_path = root / replay_rel
        if not replay_path.exists():
            count += 1
            continue

        try:
            bridge_data, board, spawns, _ = _load_board_from_recording(replay_path)
        except Exception:
            count += 1
            continue

        try:
            solution = _solve_with_rust(bridge_data, time_limit, weights=weights)
        except Exception:
            count += 1
            continue

        if not solution.actions:
            count += 1  # empty solution = still fails
            continue

        try:
            enriched = replay_solution(bridge_data, solution, spawns)
        except Exception:
            count += 1
            continue

        # Build a synthetic delta+actual to feed detect_triggers, then
        # ask whether the original trigger name re-appears.
        predicted = enriched.get("predicted_outcome", {})
        # We don't have a fresh actual outcome (no live game), so reuse
        # the predicted outcome as both — this restricts re-detection to
        # tier-3/4 triggers (search failures, rule violations) which are
        # what the tuner can actually move. Tier-1 triggers (prediction
        # vs actual mismatches) are inherently inert in this offline path
        # and would never re-fire under any weight choice — that's fine,
        # it just means tier-1 records get auto-credited as "fixed."
        deltas = {
            "buildings_alive_diff": 0,
            "grid_power_diff": 0,
            "mech_hp_diff": [],
        }
        action_dicts = []
        for a in solution.actions:
            action_dicts.append({
                "mech_uid": a.mech_uid,
                "mech_type": a.mech_type,
                "move_to": list(a.move_to) if a.move_to else None,
                "weapon": a.weapon,
                "target": list(a.target),
                "description": a.description,
            })
        solve_data = {
            "actions": action_dicts,
            "action_results": enriched.get("action_results", []),
            "search_stats": {
                "timed_out": solution.timed_out,
                "elapsed_seconds": solution.elapsed_seconds,
                "permutations_tried": solution.permutations_tried,
                "total_permutations": solution.total_permutations,
            },
        }
        new_triggers = detect_triggers(
            actual=predicted, predicted=predicted,
            deltas=deltas, solve_data=solve_data, board=board,
        )
        new_names = {t["trigger"] for t in new_triggers}
        if record["trigger"] in new_names:
            count += 1

    return count


def tune_weights(
    board_files: list[Path],
    iterations: int = 100,
    time_limit: float = 5.0,
    failure_corpus: list[dict] = None,
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
    baseline_score = evaluate_weights(base, board_files, time_limit,
                                      failure_corpus=failure_corpus)
    print(f"  Baseline score: {baseline_score:.1f}")

    best_weights = dict(base)
    best_score = baseline_score
    history = [{"iteration": 0, "score": baseline_score, "phase": "baseline"}]

    # Phase 1: Random search
    random_iters = iterations // 2
    print(f"\n  Phase 1: Random search ({random_iters} iterations)...")

    for i in range(1, random_iters + 1):
        candidate = _random_weights(base)
        score = evaluate_weights(candidate, board_files, time_limit,
                                failure_corpus=failure_corpus)

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
                score = evaluate_weights(candidate, board_files, time_limit,
                                        failure_corpus=failure_corpus)

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
