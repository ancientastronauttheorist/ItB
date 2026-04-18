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


# Triggers that are NOT tunable via solver weights:
# - per_action_desync: simulator model gap, not a search-space gap
# - solver_timeout / empty_solution: search budget, not weights
# - grid_critical / mech_destroyed: terminal strategic states; the turn
#   that caused them is what should be tuned, not the symptom
_TRIGGER_AUTO_FIXABLE = {
    # Tunable
    "self_damage_building":     True,
    "mech_on_acid":             True,
    "mech_on_danger":           True,
    "building_lost_unexpected": True,
    "mech_damage_unexpected":   True,
    "mech_killed_unexpected":   True,
    "grid_power_drop_unexpected": True,
    # Not tunable
    "per_action_desync":        False,
    "solver_timeout":           False,
    "empty_solution":           False,
    "grid_critical":            False,
    "mech_destroyed":           False,
    "action_not_executed":      False,
}


def _trigger_category(trigger_name: str) -> str:
    """Map a trigger name to a Phase 2 verify-style category for the
    backfill migration. New per_action_desync records carry their own
    category from the verify classifier."""
    return {
        "building_lost_unexpected":     "grid_power",
        "grid_power_drop_unexpected":   "grid_power",
        "mech_damage_unexpected":       "damage_amount",
        "mech_killed_unexpected":       "death",
        "mech_on_danger":               "death",
        "mech_on_acid":                 "damage_amount",
        "self_damage_building":         "damage_amount",
        "grid_critical":                "strategic_decline",
        "mech_destroyed":               "death",
        "solver_timeout":               "search_exhaustion",
        "empty_solution":               "search_exhaustion",
        "action_not_executed":          "click_miss",
    }.get(trigger_name, "unknown")


def is_auto_fixable_by_tuning(record: dict, board=None) -> bool:
    """Decide whether a failure record could plausibly be fixed by re-tuning weights.

    Two-tier check:
      1. If the record references a specific mech (``mech_uid``) and a board
         is provided, run a counterfactual: was the mech free to move
         (not webbed/frozen, move_speed > 0) AND did it have at least one
         reachable tile that wasn't in env_danger? If yes, the solver
         could have made a different choice under different weights.
      2. Otherwise fall back to the per-trigger lookup table.

    Per-action desyncs (model gaps) and search-budget triggers always
    return False — re-tuning weights cannot fix a missing simulator branch
    or a 5s timeout on a 10-mech permutation.
    """
    trigger = record.get("trigger", "")

    # Hard exclusion list — never tunable.
    if _TRIGGER_AUTO_FIXABLE.get(trigger) is False:
        return False
    if record.get("subcategory") == "model_gap_known":
        return False
    if record.get("context", {}).get("model_gap"):
        return False

    # Counterfactual path: only when we have a mech_uid AND a board to check.
    mech_uid = record.get("mech_uid")
    if mech_uid is not None and board is not None:
        mech = next((u for u in board.units if u.uid == mech_uid), None)
        if mech is None:
            return False
        if getattr(mech, "web", False) or getattr(mech, "frozen", False):
            return False
        move_speed = getattr(mech, "move_speed", 0) or 0
        if move_speed <= 0:
            return False
        # Conservative reachability: any in-bounds tile within Manhattan
        # distance ``move_speed`` that is not env_danger and not a
        # blocking terrain is "safe enough" for the counterfactual.
        env_danger = getattr(board, "environment_danger", set()) or set()
        for dx in range(-move_speed, move_speed + 1):
            for dy in range(-move_speed, move_speed + 1):
                if abs(dx) + abs(dy) > move_speed:
                    continue
                nx, ny = mech.x + dx, mech.y + dy
                if not (0 <= nx < 8 and 0 <= ny < 8):
                    continue
                if (nx, ny) in env_danger:
                    continue
                tile = board.tile(nx, ny)
                if tile.terrain in ("water", "chasm", "lava", "mountain"):
                    continue
                return True  # found at least one safe alternative
        return False

    # Fallback: per-trigger lookup. Default to False so we don't pollute
    # the tuner objective with records that have no clear tuning lever.
    return _TRIGGER_AUTO_FIXABLE.get(trigger, False)


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
            # ``fuzzy_signal`` is the self-healing loop Phase 0 hook —
            # readers (cmd_analyze, cmd_tune, regression corpus) use
            # ``.get()`` on optional fields so this is additive-safe.
            for opt in ("action_index", "mech_uid", "category",
                        "subcategory", "diff", "fuzzy_signal"):
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


# ── stale-row cutoff (shared with src/research/pattern_miner.py) ────────────
#
# The mining cutoff config lives at ``data/mining_cutoff.json`` and is also
# read by the override miner. Both consumers honor the same timestamp so a
# single bump retires stale rows from both the mining corpus and the tuner's
# failure corpus at once. Kept as a small duplicate of pattern_miner's
# helpers to avoid a weird analysis → research dependency edge.

_DEFAULT_CUTOFF_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "mining_cutoff.json"
)
_UNSET = object()


def _normalize_ts(ts: str) -> str:
    """Strip timezone offsets so two ISO strings compare lexicographically.

    Mirror of ``pattern_miner._normalize_ts`` — see that docstring.
    """
    if not ts:
        return ts
    cut = len(ts)
    for i in range(10, len(ts)):
        if ts[i] in "+-":
            cut = i
            break
    if ts.endswith("Z"):
        cut = min(cut, len(ts) - 1)
    return ts[:cut]


def load_failure_cutoff(path: Path | str | None = None) -> str | None:
    """Read ``min_timestamp`` from the mining-cutoff config, or None.

    Missing file / bad JSON / missing key = None (filter disabled).
    """
    p = Path(path) if path is not None else _DEFAULT_CUTOFF_PATH
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    ts = raw.get("min_timestamp")
    return str(ts) if isinstance(ts, str) and ts else None


def filter_by_timestamp(
    records: list[dict],
    min_timestamp: str | None | object = _UNSET,
) -> list[dict]:
    """Return records with ``timestamp >= min_timestamp``.

    ``min_timestamp`` is unset → load from ``data/mining_cutoff.json``.
    ``None`` → no filter applied (every row passes). An ISO string →
    used directly. Rows with no ``timestamp`` field pass through
    (legacy rows predate the stamp; treating them as post-cutoff
    keeps the filter conservative — over-including is preferable to
    silently dropping).
    """
    cutoff = (
        load_failure_cutoff() if min_timestamp is _UNSET else min_timestamp
    )
    if not cutoff:
        return list(records)
    cutoff_norm = _normalize_ts(cutoff)
    out: list[dict] = []
    for r in records:
        ts = r.get("timestamp")
        if not ts:
            out.append(r)
            continue
        if _normalize_ts(str(ts)) >= cutoff_norm:
            out.append(r)
    return out


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
