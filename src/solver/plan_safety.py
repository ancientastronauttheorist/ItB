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
    "objective_building_destroyed",
    "objective_building_hp_loss",
    "pod_lost",
    "mech_lost",
    "mech_on_danger",
    "mech_disabled",
    "bigbomb_lost",
    "protected_objective_unit_lost",
    "protected_objective_unit_unfrozen",
}

NON_OVERRIDABLE_KINDS = {
    "bigbomb_lost",
    "objective_building_destroyed",
    "objective_building_hp_loss",
    "protected_objective_unit_lost",
    "protected_objective_unit_unfrozen",
}


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _list_or_empty(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _violation(kind: str, current: Any, predicted: Any,
               message: str, details: Any | None = None) -> dict[str, Any]:
    out = {
        "kind": kind,
        "current": current,
        "predicted": predicted,
        "blocking": kind in BLOCKING_KINDS,
        "message": message,
    }
    if isinstance(current, int) and isinstance(predicted, int):
        out["delta"] = predicted - current
    if details is not None:
        out["details"] = details
    return out


def audit_plan_safety(current: dict[str, Any],
                      predicted: dict[str, Any]) -> dict[str, Any]:
    """Classify a plan by comparing current board value to prediction.

    ``current`` is a pre-action board summary. ``predicted`` is the detailed
    post-enemy board summary derived from replay_solution.

    The audit is intentionally conservative: visible grid loss, building
    destruction, partial building HP loss, objective loss, pod loss, mech
    death, or leaving a mech in lethal environment danger all make a plan
    dirty. Missing fields yield ``UNKNOWN`` rather than a false clean bill.
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

    cur_obj_alive = _int_or_none(current.get("objective_buildings_alive"))
    pred_obj_alive = _int_or_none(predicted.get("objective_buildings_alive"))
    if cur_obj_alive is not None and pred_obj_alive is not None:
        compared.append("objective_buildings_alive")
        if pred_obj_alive < cur_obj_alive:
            violations.append(_violation(
                "objective_building_destroyed",
                cur_obj_alive,
                pred_obj_alive,
                "Predicted outcome destroys one or more objective buildings.",
            ))

    cur_obj_hp = _int_or_none(current.get("objective_building_hp_total"))
    pred_obj_hp = _int_or_none(predicted.get("objective_building_hp_total"))
    if cur_obj_hp is not None and pred_obj_hp is not None:
        compared.append("objective_building_hp_total")
        if pred_obj_hp < cur_obj_hp:
            violations.append(_violation(
                "objective_building_hp_loss",
                cur_obj_hp,
                pred_obj_hp,
                "Predicted outcome loses objective-building HP.",
            ))

    cur_pods = _int_or_none(current.get("pods_present"))
    pred_pods = _int_or_none(predicted.get("pods_present"))
    if cur_pods is not None and pred_pods is not None:
        compared.append("pods_present")
        if pred_pods < cur_pods:
            pods_collected = _int_or_none(predicted.get("pods_collected")) or 0
            unaccounted = cur_pods - pred_pods - max(0, pods_collected)
            if unaccounted > 0:
                violations.append(_violation(
                    "pod_lost",
                    cur_pods,
                    pred_pods,
                    "Predicted outcome loses a pod without recording collection.",
                    {"pods_collected": pods_collected},
                ))

    cur_mechs = _int_or_none(current.get("mechs_alive"))
    pred_mechs = _int_or_none(predicted.get("mechs_alive"))
    if cur_mechs is not None and pred_mechs is not None:
        compared.append("mechs_alive")
        if pred_mechs < cur_mechs:
            violations.append(_violation(
                "mech_lost",
                cur_mechs,
                pred_mechs,
                "Predicted outcome destroys one or more mechs.",
            ))

    cur_mech_hp = _int_or_none(current.get("mech_hp_total"))
    pred_mech_hp = _int_or_none(predicted.get("mech_hp_total"))
    if cur_mech_hp is not None and pred_mech_hp is not None:
        compared.append("mech_hp_total")
        if pred_mech_hp < cur_mech_hp:
            violations.append(_violation(
                "mech_hp_loss",
                cur_mech_hp,
                pred_mech_hp,
                "Predicted outcome loses mech HP.",
            ))

    if "mechs_on_danger" in current or "mechs_on_danger" in predicted:
        compared.append("mechs_on_danger")
        danger_mechs = _list_or_empty(predicted.get("mechs_on_danger"))
        if danger_mechs:
            violations.append(_violation(
                "mech_on_danger",
                0,
                len(danger_mechs),
                "Predicted plan leaves one or more mechs on lethal environment danger.",
                danger_mechs,
            ))

    if "mechs_disabled" in current or "mechs_disabled" in predicted:
        compared.append("mechs_disabled")
        current_disabled_uids = {
            item.get("uid")
            for item in _list_or_empty(current.get("mechs_disabled"))
            if isinstance(item, dict)
        }
        new_disabled = [
            item for item in _list_or_empty(predicted.get("mechs_disabled"))
            if isinstance(item, dict) and item.get("uid") not in current_disabled_uids
        ]
        if new_disabled:
            violations.append(_violation(
                "mech_disabled",
                len(current_disabled_uids),
                len(current_disabled_uids) + len(new_disabled),
                "Predicted plan leaves one or more additional mechs disabled.",
                new_disabled,
            ))

    cur_bigbomb = current.get("bigbomb_alive")
    pred_bigbomb = predicted.get("bigbomb_alive")
    if isinstance(cur_bigbomb, bool) and isinstance(pred_bigbomb, bool):
        compared.append("bigbomb_alive")
        if cur_bigbomb and not pred_bigbomb:
            violations.append(_violation(
                "bigbomb_lost",
                cur_bigbomb,
                pred_bigbomb,
                "Predicted outcome destroys the Renfield Bomb.",
            ))

    cur_protected = _int_or_none(current.get("protected_objective_units_alive"))
    pred_protected = _int_or_none(predicted.get("protected_objective_units_alive"))
    if cur_protected is not None and pred_protected is not None:
        compared.append("protected_objective_units_alive")
        if pred_protected < cur_protected:
            violations.append(_violation(
                "protected_objective_unit_lost",
                cur_protected,
                pred_protected,
                "Predicted outcome destroys one or more protected objective units.",
                {
                    "current_units": _list_or_empty(current.get("protected_objective_units")),
                    "predicted_units": _list_or_empty(predicted.get("protected_objective_units")),
                },
            ))

    cur_frozen = _int_or_none(current.get("protected_objective_units_frozen"))
    pred_frozen = _int_or_none(predicted.get("protected_objective_units_frozen"))
    mission_id = current.get("mission_id") or predicted.get("mission_id")
    if (
        mission_id == "Mission_FreezeBots"
        and cur_frozen is not None
        and pred_frozen is not None
    ):
        compared.append("protected_objective_units_frozen")
        if pred_frozen < cur_frozen:
            violations.append(_violation(
                "protected_objective_unit_unfrozen",
                cur_frozen,
                pred_frozen,
                "Predicted outcome unfreezes one or more freeze-bot objective units.",
                {
                    "current_units": _list_or_empty(current.get("protected_objective_units")),
                    "predicted_units": _list_or_empty(predicted.get("protected_objective_units")),
                },
            ))

    blocking = any(v.get("blocking") for v in violations)
    if blocking:
        status = "DIRTY"
    elif violations:
        status = "WARN"
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
            "objective_buildings_alive": cur_obj_alive,
            "objective_building_hp_total": cur_obj_hp,
            "pods_present": cur_pods,
            "mechs_alive": cur_mechs,
            "mech_hp_total": cur_mech_hp,
            "mechs_on_danger": _list_or_empty(current.get("mechs_on_danger")),
            "mechs_disabled": _list_or_empty(current.get("mechs_disabled")),
            "bigbomb_alive": cur_bigbomb if isinstance(cur_bigbomb, bool) else None,
            "protected_objective_units_alive": cur_protected,
            "protected_objective_units_frozen": cur_frozen,
        },
        "predicted": {
            "grid_power": pred_grid,
            "buildings_alive": pred_alive,
            "building_hp_total": pred_hp,
            "objective_buildings_alive": pred_obj_alive,
            "objective_building_hp_total": pred_obj_hp,
            "pods_present": pred_pods,
            "mechs_alive": pred_mechs,
            "mech_hp_total": pred_mech_hp,
            "mechs_on_danger": _list_or_empty(predicted.get("mechs_on_danger")),
            "mechs_disabled": _list_or_empty(predicted.get("mechs_disabled")),
            "bigbomb_alive": pred_bigbomb if isinstance(pred_bigbomb, bool) else None,
            "protected_objective_units_alive": pred_protected,
            "protected_objective_units_frozen": pred_frozen,
        },
    }


def plan_requires_safety_block(audit: dict[str, Any] | None,
                               *,
                               allow_dirty_plan: bool = False) -> bool:
    """Return True when auto_turn should stop before executing actions."""
    if not isinstance(audit, dict):
        return False
    if allow_dirty_plan:
        return any(
            isinstance(v, dict)
            and v.get("blocking")
            and v.get("kind") in NON_OVERRIDABLE_KINDS
            for v in audit.get("violations", []) or []
        )
    return bool(audit.get("blocking"))
