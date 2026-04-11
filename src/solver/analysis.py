"""Turn-level trigger detection and failure analysis for solver improvement.

Compares predicted vs actual board outcomes and flags conditions
that indicate solver bugs, model gaps, or search failures.

Trigger tiers:
  1: Prediction failures (solver was wrong about outcomes)
  2: Execution failures (bridge command didn't produce expected result)
  3: Search failures (solver couldn't find a good solution)
  4: Rule violations (solver broke game rules)
  6: Run patterns (strategic failures across turns)

Root-cause categories (operationally distinguishable):
  prediction_mismatch: predicted != actual (tiers 1, 4)
  execution_mismatch: bridge action didn't execute correctly (tier 2)
  search_exhaustion: solver timed out or pruned too aggressively (tier 3)
  strategic_decline: cumulative bad decisions over turns (tier 6)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


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


# --- Tier 2: Execution failure detection ---


def check_execution_failures(action_diffs: list[dict]) -> list[dict]:
    """Tier 2: Bridge action didn't produce expected game state change.

    Checks per-action diffs from auto_turn to detect cases where
    the bridge ACK said OK but the game state didn't actually change.
    """
    triggers = []
    for diff in action_diffs:
        pre = diff.get("pre_state", {})
        post = diff.get("post_state", {})
        idx = diff.get("action_index", "?")
        desc = diff.get("description", "")

        if not pre or not post:
            continue

        # Check if any mech changed state (moved, lost active status, etc.)
        pre_mechs = {m["uid"]: m for m in pre.get("mechs", [])}
        post_mechs = {m["uid"]: m for m in post.get("mechs", [])}

        mech_uid = diff.get("mech_uid")
        if mech_uid and mech_uid in pre_mechs and mech_uid in post_mechs:
            pre_m = pre_mechs[mech_uid]
            post_m = post_mechs[mech_uid]

            # Mech should have become inactive after action
            if pre_m.get("active") and post_m.get("active"):
                triggers.append({
                    "trigger": "action_not_executed",
                    "tier": 2,
                    "severity": "high",
                    "details": f"Action {idx} ({desc}): mech {mech_uid} still active after execution",
                })

    return triggers


# --- Root-cause classification ---


_TIER_TO_ROOT_CAUSE = {
    1: "prediction_mismatch",
    2: "execution_mismatch",
    3: "search_exhaustion",
    4: "prediction_mismatch",
    6: "strategic_decline",
}

# Triggers from per-action verification map to a distinct root cause:
# the predicted state diverged from reality even though the action ran.
_TRIGGER_TO_ROOT_CAUSE = {
    "per_action_desync": "model_drift",
}


def classify_root_cause(trigger: dict) -> str:
    """Map a trigger to its operationally distinguishable root cause.

    Trigger-name overrides take precedence over tier mapping so per-action
    desyncs can sit in tier 2 without colliding with bridge ACK failures.
    """
    name = trigger.get("trigger", "")
    if name in _TRIGGER_TO_ROOT_CAUSE:
        return _TRIGGER_TO_ROOT_CAUSE[name]
    return _TIER_TO_ROOT_CAUSE.get(trigger.get("tier", 0), "unknown")


# --- Failure database ---

FAILURE_DB_PATH = Path(__file__).parent.parent.parent / "recordings" / "failure_db.jsonl"


def append_to_failure_db(
    triggers: list[dict],
    run_id: str,
    mission_index: int,
    turn: int,
    context: dict,
) -> int:
    """Append triggers to the failure database (JSONL).

    Args:
        triggers: List of trigger dicts from detect_triggers().
        run_id: Current run ID.
        mission_index: Current mission index.
        turn: Turn number.
        context: Dict with squad, island, grid_power, solver_timed_out,
                 weight_version, solver_version.

    Returns:
        Number of records written.
    """
    if not triggers:
        return 0

    FAILURE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    with open(FAILURE_DB_PATH, "a") as f:
        for trigger in triggers:
            # Per-action triggers carry an action_index suffix so multiple
            # desyncs in the same turn don't collide on the unique id.
            action_idx = trigger.get("action_index")
            id_suffix = trigger["trigger"]
            if action_idx is not None:
                id_suffix = f"{id_suffix}_a{action_idx}"
            record = {
                "id": f"{run_id}_m{mission_index:02d}_t{turn:02d}_{id_suffix}",
                "timestamp": datetime.now().isoformat(),
                "run_id": run_id,
                "mission": mission_index,
                "turn": turn,
                "trigger": trigger["trigger"],
                "tier": trigger["tier"],
                "root_cause": classify_root_cause(trigger),
                "severity": trigger["severity"],
                "details": trigger["details"],
                "context": context,
                "solver_version": context.get("solver_version", "unknown"),
                "replay_file": f"recordings/{run_id}/m{mission_index:02d}_turn_{turn:02d}_board.json",
            }
            # Optional per-action fields (Phase 2 verify loop).
            for opt in ("action_index", "mech_uid", "category",
                        "subcategory", "diff"):
                if opt in trigger:
                    record[opt] = trigger[opt]
            f.write(json.dumps(record) + "\n")
            count += 1

    return count


def load_failure_db() -> list[dict]:
    """Load all records from the failure database."""
    if not FAILURE_DB_PATH.exists():
        return []
    records = []
    with open(FAILURE_DB_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def analyze_failures(min_samples: int = 30) -> dict:
    """Analyze failure database for patterns.

    Returns a report dict with stats, breakdowns, and pattern analysis.
    Applies minimum sample gates to prevent overfitting to noise.
    """
    records = load_failure_db()
    total = len(records)

    if total == 0:
        return {"total_records": 0, "message": "No failure records found."}

    # --- Basic counts (no minimum gate) ---
    by_trigger = {}
    by_severity = {"critical": 0, "high": 0, "medium": 0}
    by_root_cause = {}
    by_tier = {}
    by_turn = {}
    by_squad = {}
    by_island = {}

    for r in records:
        trigger = r.get("trigger", "unknown")
        by_trigger[trigger] = by_trigger.get(trigger, 0) + 1

        sev = r.get("severity", "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1

        rc = r.get("root_cause", "unknown")
        by_root_cause[rc] = by_root_cause.get(rc, 0) + 1

        tier = r.get("tier", 0)
        by_tier[tier] = by_tier.get(tier, 0) + 1

        turn = r.get("turn", 0)
        by_turn[turn] = by_turn.get(turn, 0) + 1

        ctx = r.get("context", {})
        squad = ctx.get("squad", "unknown")
        by_squad[squad] = by_squad.get(squad, 0) + 1
        island = ctx.get("island", "unknown")
        by_island[island] = by_island.get(island, 0) + 1

    report = {
        "total_records": total,
        "by_trigger": dict(sorted(by_trigger.items(), key=lambda x: -x[1])),
        "by_severity": by_severity,
        "by_root_cause": dict(sorted(by_root_cause.items(), key=lambda x: -x[1])),
        "by_tier": dict(sorted(by_tier.items(), key=lambda x: x[0])),
    }

    # --- Gated breakdowns ---
    unique_runs = len(set(r.get("run_id", "") for r in records))

    if unique_runs >= 10:
        report["by_squad"] = dict(sorted(by_squad.items(), key=lambda x: -x[1]))
        report["by_island"] = dict(sorted(by_island.items(), key=lambda x: -x[1]))
    else:
        report["by_squad_note"] = f"Need 10+ runs for squad breakdown (have {unique_runs})"

    total_turns = len(by_turn)
    if total_turns >= min_samples:
        report["by_turn"] = dict(sorted(by_turn.items(), key=lambda x: x[0]))
    else:
        report["by_turn_note"] = f"Need {min_samples}+ turns for temporal analysis (have {total_turns})"

    return report
