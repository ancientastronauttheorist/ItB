"""Plan safety audit primitives for Solver 2.0.

The Rust evaluator still produces a scalar score, but the turn loop needs a
hard safety layer above that score. This module classifies whether a selected
plan preserves irreversible value such as grid power and building HP.
"""

from __future__ import annotations

from typing import Any


BLOCKING_KINDS = {
    "grid_damage",
    "building_destroyed",
    "building_hp_loss",
}


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _violation(kind: str, current: int, predicted: int,
               message: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "current": current,
        "predicted": predicted,
        "delta": predicted - current,
        "blocking": kind in BLOCKING_KINDS,
        "message": message,
    }


def audit_plan_safety(current: dict[str, Any],
                      predicted: dict[str, Any]) -> dict[str, Any]:
    """Classify a plan by comparing current board value to prediction.

    ``current`` is a pre-action board summary. ``predicted`` is the
    post-enemy-phase ``predicted_outcome`` produced by replay_solution.

    The audit is intentionally conservative: visible grid loss, building
    destruction, or partial building HP loss all make a plan dirty. Missing
    fields yield ``UNKNOWN`` rather than a false clean bill.
    """
    violations: list[dict[str, Any]] = []
    compared: list[str] = []

    cur_grid = _int_or_none(current.get("grid_power"))
    pred_grid = _int_or_none(predicted.get("grid_power"))
    if cur_grid is not None and pred_grid is not None:
        compared.append("grid_power")
        if pred_grid < cur_grid:
            violations.append(_violation(
                "grid_damage",
                cur_grid,
                pred_grid,
                "Predicted grid power drops before the next player turn.",
            ))

    cur_alive = _int_or_none(current.get("buildings_alive"))
    pred_alive = _int_or_none(predicted.get("buildings_alive"))
    if cur_alive is not None and pred_alive is not None:
        compared.append("buildings_alive")
        if pred_alive < cur_alive:
            violations.append(_violation(
                "building_destroyed",
                cur_alive,
                pred_alive,
                "Predicted outcome destroys one or more buildings.",
            ))

    cur_hp = _int_or_none(current.get("building_hp_total"))
    pred_hp = _int_or_none(predicted.get("building_hp_total"))
    if cur_hp is not None and pred_hp is not None:
        compared.append("building_hp_total")
        if pred_hp < cur_hp:
            violations.append(_violation(
                "building_hp_loss",
                cur_hp,
                pred_hp,
                "Predicted outcome loses building HP even if grid power stays visible.",
            ))

    blocking = any(v.get("blocking") for v in violations)
    if blocking:
        status = "DIRTY"
    elif compared:
        status = "CLEAN"
    else:
        status = "UNKNOWN"

    return {
        "status": status,
        "blocking": blocking,
        "violations": violations,
        "compared": compared,
        "current": {
            "grid_power": cur_grid,
            "buildings_alive": cur_alive,
            "building_hp_total": cur_hp,
        },
        "predicted": {
            "grid_power": pred_grid,
            "buildings_alive": pred_alive,
            "building_hp_total": pred_hp,
        },
    }


def plan_requires_safety_block(audit: dict[str, Any] | None,
                               *,
                               allow_dirty_plan: bool = False) -> bool:
    """Return True when auto_turn should stop before executing actions."""
    if allow_dirty_plan:
        return False
    if not isinstance(audit, dict):
        return False
    return bool(audit.get("blocking"))
