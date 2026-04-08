"""Turn-level trigger detection for solver improvement.

Compares predicted vs actual board outcomes and flags conditions
that indicate solver bugs, model gaps, or search failures.
Pure functions — no file I/O, no side effects.

Trigger tiers:
  1: Prediction failures (solver was wrong about outcomes)
  3: Search failures (solver couldn't find a good solution)
  4: Rule violations (solver broke game rules)
  6: Run patterns (strategic failures across turns)
"""

from __future__ import annotations


def detect_triggers(
    actual: dict,
    predicted: dict,
    deltas: dict,
    solve_data: dict,
    board=None,
) -> list[dict]:
    """Detect all trigger conditions for a completed turn.

    Args:
        actual: Actual board summary after enemy turn resolved.
        predicted: Solver's predicted outcome from replay_solution().
        deltas: Computed differences (actual - predicted).
        solve_data: The full solve recording data dict.
        board: Original pre-solve Board object (for tile checks). Optional.

    Returns:
        List of trigger dicts with keys: trigger, tier, severity, details.
    """
    triggers = []
    triggers.extend(_check_prediction_failures(actual, predicted, deltas))
    triggers.extend(_check_search_failures(solve_data))
    triggers.extend(_check_rule_violations(solve_data, board))
    triggers.extend(_check_run_patterns(actual))
    return triggers


def _check_prediction_failures(actual: dict, predicted: dict,
                                deltas: dict) -> list[dict]:
    """Tier 1: Solver predicted an outcome that didn't match reality."""
    triggers = []

    buildings_diff = deltas.get("buildings_alive_diff", 0)
    if buildings_diff < 0:
        triggers.append({
            "trigger": "building_lost_unexpected",
            "tier": 1,
            "severity": "critical",
            "details": (
                f"Predicted {predicted.get('buildings_alive', '?')} buildings, "
                f"actual {actual.get('buildings_alive', '?')} ({buildings_diff})"
            ),
        })

    grid_diff = deltas.get("grid_power_diff", 0)
    if grid_diff < 0:
        actual_grid = actual.get("grid_power", 7)
        triggers.append({
            "trigger": "grid_power_drop_unexpected",
            "tier": 1,
            "severity": "critical" if actual_grid <= 2 else "high",
            "details": (
                f"Predicted grid {predicted.get('grid_power', '?')}, "
                f"actual {actual_grid} ({grid_diff})"
            ),
        })

    for md in deltas.get("mech_hp_diff", []):
        if md.get("diff", 0) < 0:
            triggers.append({
                "trigger": "mech_damage_unexpected",
                "tier": 1,
                "severity": "high",
                "details": (
                    f"{md.get('type', '?')}: predicted HP "
                    f"{md.get('predicted_hp', '?')}, "
                    f"actual {md.get('actual_hp', '?')} ({md['diff']})"
                ),
            })

    return triggers


def _check_search_failures(solve_data: dict) -> list[dict]:
    """Tier 3: Solver couldn't find a good solution in time."""
    triggers = []

    stats = solve_data.get("search_stats", {})
    if stats.get("timed_out"):
        triggers.append({
            "trigger": "solver_timeout",
            "tier": 3,
            "severity": "medium",
            "details": (
                f"Timed out after {stats.get('elapsed_seconds', '?'):.1f}s, "
                f"tried {stats.get('permutations_tried', '?')}/"
                f"{stats.get('total_permutations', '?')} permutations"
            ),
        })

    actions = solve_data.get("actions", [])
    if not actions:
        triggers.append({
            "trigger": "empty_solution",
            "tier": 3,
            "severity": "high",
            "details": "Solver returned no actions",
        })

    return triggers


def _check_rule_violations(solve_data: dict, board) -> list[dict]:
    """Tier 4: Solver's own actions violated game rules or hurt the player."""
    triggers = []

    # Self-damage to buildings (from action_results)
    for i, ar in enumerate(solve_data.get("action_results", [])):
        bld_damaged = ar.get("buildings_damaged", 0)
        bld_lost = ar.get("buildings_lost", 0)
        if bld_damaged > 0 or bld_lost > 0:
            actions = solve_data.get("actions", [])
            mech = actions[i].get("mech_type", "?") if i < len(actions) and isinstance(actions[i], dict) else "?"
            triggers.append({
                "trigger": "self_damage_building",
                "tier": 4,
                "severity": "critical",
                "details": (
                    f"Action {i} ({mech}) damaged {bld_damaged} building HP, "
                    f"destroyed {bld_lost} buildings"
                ),
            })

    # Mech placement checks (need board for tile data)
    if board is not None:
        env_danger = board.environment_danger if hasattr(board, 'environment_danger') else set()
        for action in solve_data.get("actions", []):
            if not isinstance(action, dict):
                continue
            move_to = action.get("move_to")
            mech_type = action.get("mech_type", "?")
            if not move_to:
                continue
            mx, my = move_to[0], move_to[1]
            if board.in_bounds(mx, my):
                tile = board.tile(mx, my)
                if tile.acid:
                    triggers.append({
                        "trigger": "mech_on_acid",
                        "tier": 4,
                        "severity": "high",
                        "details": f"{mech_type} moved to acid tile ({mx},{my})",
                    })
                if (mx, my) in env_danger:
                    triggers.append({
                        "trigger": "mech_on_danger",
                        "tier": 4,
                        "severity": "critical",
                        "details": f"{mech_type} moved to danger tile ({mx},{my})",
                    })

    return triggers


def _check_run_patterns(actual: dict) -> list[dict]:
    """Tier 6: Strategic red flags for the overall run."""
    triggers = []

    grid = actual.get("grid_power", 7)
    if grid <= 2:
        triggers.append({
            "trigger": "grid_critical",
            "tier": 6,
            "severity": "high",
            "details": f"Grid power at {grid} (critical)",
        })

    for mech in actual.get("mech_hp", []):
        if mech.get("hp", 1) <= 0:
            triggers.append({
                "trigger": "mech_destroyed",
                "tier": 6,
                "severity": "critical",
                "details": f"{mech.get('type', '?')} destroyed (HP=0)",
            })

    return triggers
