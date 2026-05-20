"""Plan safety audit primitives for Solver 2.0.

The Rust evaluator still produces a scalar score, but the turn loop needs a
hard safety layer above that score. This module classifies whether a selected
plan preserves irreversible value such as grid power and building HP.
"""

from __future__ import annotations

import os
from typing import Any


BLOCKING_KINDS = {
    "grid_damage",
    "grid_timeline_collapse",
    "building_destroyed",
    "building_hp_loss",
    "pylon_destroyed",
    "pylon_hp_loss",
    "objective_building_destroyed",
    "objective_building_hp_loss",
    "pod_lost",
    "pod_unrecovered_final",
    "mech_lost",
    "mech_acid",
    "mech_fire",
    "mech_webbed",
    "mech_on_danger",
    "mech_disabled",
    "bigbomb_lost",
    "protected_objective_unit_lost",
    "protected_objective_unit_unfrozen",
    "destroy_objective_unit_alive_final",
    "mech_damage_objective_failed",
    "freeze_building_objective_failed",
    "terraform_grass_objective_failed",
    "mountain_objective_failed",
    "mite_objective_failed",
    "kill_objective_failed",
    "kill_limit_objective_failed",
}

NON_OVERRIDABLE_KINDS = {
    "grid_timeline_collapse",
    "pylon_destroyed",
    "pylon_hp_loss",
    "bigbomb_lost",
    "objective_building_destroyed",
    "objective_building_hp_loss",
    "pod_unrecovered_final",
    "protected_objective_unit_lost",
    "protected_objective_unit_unfrozen",
    "destroy_objective_unit_alive_final",
    "mech_damage_objective_failed",
    "freeze_building_objective_failed",
    "terraform_grass_objective_failed",
    "mountain_objective_failed",
    "mite_objective_failed",
    "kill_objective_failed",
    "kill_limit_objective_failed",
}

FINAL_CAVE_EMERGENCY_PYLON_KINDS = {
    "pylon_destroyed",
    "pylon_hp_loss",
}

FINAL_CAVE_EMERGENCY_ALLOWED_KINDS = {
    "grid_damage",
    "building_destroyed",
    "building_hp_loss",
    "pylon_destroyed",
    "pylon_hp_loss",
}

FINAL_CAVE_RESIST_GAMBLE_ALLOWED_KINDS = {
    "grid_damage",
    "grid_timeline_collapse",
    "building_destroyed",
    "building_hp_loss",
    "pylon_destroyed",
    "pylon_hp_loss",
}

FINAL_BOMB_DIRTY_ALLOWED_KINDS = {
    "grid_damage",
    "building_destroyed",
    "building_hp_loss",
    "objective_building_destroyed",
    "objective_building_hp_loss",
}


LOSS_KINDS = {
    "grid_damage": "grid_power",
    "building_destroyed": "buildings_alive",
    "building_hp_loss": "building_hp_total",
    "pylon_destroyed": "pylons_alive",
    "pylon_hp_loss": "pylon_hp_total",
    "objective_building_destroyed": "objective_buildings_alive",
    "objective_building_hp_loss": "objective_building_hp_total",
    "pod_lost": "pods_present",
    "pod_unrecovered_final": "pods_present",
    "mech_lost": "mechs_alive",
    "mech_acid": "mechs_acid",
    "mech_fire": "mechs_fire",
    "mech_webbed": "mechs_webbed",
    "mech_on_danger": "mechs_on_danger",
    "mech_disabled": "mechs_disabled",
    "bigbomb_lost": "bigbomb_alive",
    "protected_objective_unit_lost": "protected_objective_units_alive",
    "protected_objective_unit_unfrozen": "protected_objective_units_frozen",
    "destroy_objective_unit_alive_final": "destroy_objective_units_alive",
    "mech_hp_loss": "mech_hp_total",
    "mech_damage_objective_failed": "mech_damage_taken_total",
    "freeze_building_objective_failed": "freeze_buildings_thawed",
    "terraform_grass_objective_failed": "terraform_grass_remaining",
    "mountain_objective_failed": "mission_mountains_destroyed",
    "mite_objective_failed": "mites_remaining",
    "kill_objective_failed": "mission_kills_done",
    "kill_limit_objective_failed": "mission_kills_done",
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
               message: str, details: Any | None = None,
               *, blocking: bool | None = None) -> dict[str, Any]:
    out = {
        "kind": kind,
        "current": current,
        "predicted": predicted,
        "blocking": kind in BLOCKING_KINDS if blocking is None else blocking,
        "message": message,
    }
    if isinstance(current, int) and isinstance(predicted, int):
        out["delta"] = predicted - current
    if details is not None:
        out["details"] = details
    return out


def audit_plan_safety(current: dict[str, Any],
                      predicted: dict[str, Any],
                      *,
                      block_mech_hp_loss: bool = False,
                      block_mech_status_loss: bool = False) -> dict[str, Any]:
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
        if pred_grid <= 0:
            violations.append(_violation(
                "grid_timeline_collapse",
                cur_grid,
                pred_grid,
                "Predicted grid power reaches 0 before the next player turn.",
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

    cur_pylons = _int_or_none(current.get("pylons_alive"))
    pred_pylons = _int_or_none(predicted.get("pylons_alive"))
    if cur_pylons is not None and pred_pylons is not None:
        compared.append("pylons_alive")
        if pred_pylons < cur_pylons:
            violations.append(_violation(
                "pylon_destroyed",
                cur_pylons,
                pred_pylons,
                "Predicted final-cave outcome destroys one or more pylons.",
            ))

    cur_pylon_hp = _int_or_none(current.get("pylon_hp_total"))
    pred_pylon_hp = _int_or_none(predicted.get("pylon_hp_total"))
    if cur_pylon_hp is not None and pred_pylon_hp is not None:
        compared.append("pylon_hp_total")
        if pred_pylon_hp < cur_pylon_hp:
            violations.append(_violation(
                "pylon_hp_loss",
                cur_pylon_hp,
                pred_pylon_hp,
                "Predicted final-cave outcome loses pylon HP.",
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

    mission_id = current.get("mission_id") or predicted.get("mission_id")
    cur_turn = _int_or_none(current.get("turn"))
    pred_turn = _int_or_none(predicted.get("turn"))
    cur_total_turns = _int_or_none(current.get("total_turns"))
    pred_total_turns = _int_or_none(predicted.get("total_turns"))
    final_turn = (
        cur_turn is not None
        and cur_total_turns is not None
        and cur_turn >= cur_total_turns
    ) or (
        pred_turn is not None
        and pred_total_turns is not None
        and pred_turn >= pred_total_turns
    )

    cur_pods = _int_or_none(current.get("pods_present"))
    pred_pods = _int_or_none(predicted.get("pods_present"))
    if cur_pods is not None and pred_pods is not None:
        compared.append("pods_present")
        pods_collected = _int_or_none(predicted.get("pods_collected")) or 0
        if pred_pods < cur_pods:
            unaccounted = cur_pods - pred_pods - max(0, pods_collected)
            if unaccounted > 0:
                violations.append(_violation(
                    "pod_lost",
                    cur_pods,
                    pred_pods,
                    "Predicted outcome loses a pod without recording collection.",
                    {"pods_collected": pods_collected},
                ))
        if final_turn and pred_pods > 0:
            violations.append(_violation(
                "pod_unrecovered_final",
                cur_pods,
                pred_pods,
                "Predicted final-turn outcome leaves a Time Pod unrecovered.",
                {"pods_collected": pods_collected},
            ))

    cur_grass = _int_or_none(current.get("terraform_grass_remaining"))
    pred_grass = _int_or_none(predicted.get("terraform_grass_remaining"))
    if mission_id == "Mission_Terraform" and cur_grass is not None and pred_grass is not None:
        compared.append("terraform_grass_remaining")
        if final_turn and pred_grass > 0:
            violations.append(_violation(
                "terraform_grass_objective_failed",
                cur_grass,
                pred_grass,
                "Predicted final-turn outcome leaves Terraform grassland uncleared.",
                {
                    "current_tiles": _list_or_empty(current.get("terraform_grass_tiles")),
                    "predicted_tiles": _list_or_empty(predicted.get("terraform_grass_tiles")),
                },
            ))

    cur_mountain_target = _int_or_none(current.get("mission_mountain_target"))
    pred_mountain_target = _int_or_none(predicted.get("mission_mountain_target"))
    mountain_target = cur_mountain_target or pred_mountain_target
    cur_mountains = _int_or_none(current.get("mission_mountains_destroyed"))
    pred_mountains = _int_or_none(predicted.get("mission_mountains_destroyed"))
    if mountain_target and cur_mountains is not None and pred_mountains is not None:
        compared.append("mission_mountains_destroyed")
        if final_turn and pred_mountains < mountain_target:
            violations.append(_violation(
                "mountain_objective_failed",
                cur_mountains,
                pred_mountains,
                "Predicted final-turn outcome leaves the mountain objective short.",
                {
                    "target": mountain_target,
                    "planned_mountains": _int_or_none(
                        predicted.get("mission_mountains_planned")
                    ) or 0,
                    "current_tiles": _list_or_empty(
                        current.get("mission_mountain_tiles")
                    ),
                    "predicted_tiles": _list_or_empty(
                        predicted.get("mission_mountain_tiles")
                    ),
                },
            ))

    cur_mites = _int_or_none(current.get("mites_remaining"))
    pred_mites = _int_or_none(predicted.get("mites_remaining"))
    cur_mites_tracked = (
        current.get("mites_status_tracked") is True
        or isinstance(current.get("mechs_infected"), list)
    )
    pred_mites_tracked = (
        predicted.get("mites_status_tracked") is True
        or isinstance(predicted.get("mechs_infected"), list)
    )
    if (
        cur_mites is not None
        and pred_mites is not None
        and (cur_mites_tracked or pred_mites_tracked or cur_mites > 0 or pred_mites > 0)
    ):
        compared.append("mites_remaining")
        audited_pred_mites = pred_mites
        if cur_mites_tracked and not pred_mites_tracked and cur_mites > pred_mites:
            audited_pred_mites = cur_mites
        if final_turn and audited_pred_mites > 0:
            violations.append(_violation(
                "mite_objective_failed",
                cur_mites,
                audited_pred_mites,
                "Predicted final-turn outcome leaves Vek Mites attached.",
                {
                    "current_mechs": _list_or_empty(current.get("mechs_infected")),
                    "predicted_mechs": _list_or_empty(predicted.get("mechs_infected")),
                    "predicted_status_tracked": pred_mites_tracked,
                },
            ))

    cur_kill_target = _int_or_none(current.get("mission_kill_target"))
    pred_kill_target = _int_or_none(predicted.get("mission_kill_target"))
    kill_target = cur_kill_target or pred_kill_target
    cur_kill_limit = _int_or_none(current.get("mission_kill_limit"))
    pred_kill_limit = _int_or_none(predicted.get("mission_kill_limit"))
    kill_limit = cur_kill_limit or pred_kill_limit
    cur_kills_done = _int_or_none(current.get("mission_kills_done"))
    pred_kills_done = _int_or_none(predicted.get("mission_kills_done"))
    if (
        kill_target is not None
        and kill_target > 0
        and cur_kills_done is not None
        and pred_kills_done is not None
    ):
        compared.append("mission_kill_target")
        compared.append("mission_kills_done")
        if final_turn and pred_kills_done < kill_target:
            violations.append(_violation(
                "kill_objective_failed",
                cur_kills_done,
                pred_kills_done,
                "Predicted final-turn outcome does not complete the kill objective.",
                {
                    "target": kill_target,
                    "planned_kills": _int_or_none(predicted.get("mission_kills_planned")),
                },
            ))
    if (
        kill_limit is not None
        and kill_limit > 0
        and cur_kills_done is not None
        and pred_kills_done is not None
    ):
        compared.append("mission_kill_limit")
        compared.append("mission_kills_done")
        if pred_kills_done > kill_limit:
            violations.append(_violation(
                "kill_limit_objective_failed",
                cur_kills_done,
                pred_kills_done,
                "Predicted outcome exceeds the kill-limit objective.",
                {
                    "limit": kill_limit,
                    "planned_kills": _int_or_none(predicted.get("mission_kills_planned")),
                },
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
                (
                    "Predicted outcome loses mech HP, which blocks "
                    "the active Perfect Battle target."
                    if block_mech_hp_loss
                    else "Predicted outcome loses mech HP."
                ),
                blocking=block_mech_hp_loss,
            ))

    cur_mech_damage = _int_or_none(current.get("mech_damage_taken_total"))
    pred_mech_damage = _int_or_none(predicted.get("mech_damage_taken_total"))
    cur_mech_damage_limit = _int_or_none(
        current.get("mech_damage_objective_limit")
    )
    pred_mech_damage_limit = _int_or_none(
        predicted.get("mech_damage_objective_limit")
    )
    mech_damage_limit = cur_mech_damage_limit or pred_mech_damage_limit
    if (
        mech_damage_limit is not None
        and cur_mech_damage is not None
        and pred_mech_damage is not None
    ):
        compared.append("mech_damage_taken_total")
        compared.append("mech_damage_objective_limit")
        if pred_mech_damage >= mech_damage_limit:
            violations.append(_violation(
                "mech_damage_objective_failed",
                cur_mech_damage,
                pred_mech_damage,
                "Predicted mech damage reaches the mission objective limit.",
                {"limit": mech_damage_limit},
            ))

    if "mechs_acid" in current or "mechs_acid" in predicted:
        compared.append("mechs_acid")
        current_acid_uids = {
            item.get("uid")
            for item in _list_or_empty(current.get("mechs_acid"))
            if isinstance(item, dict)
        }
        new_acid = [
            item for item in _list_or_empty(predicted.get("mechs_acid"))
            if isinstance(item, dict) and item.get("uid") not in current_acid_uids
        ]
        if new_acid:
            violations.append(_violation(
                "mech_acid",
                len(current_acid_uids),
                len(current_acid_uids) + len(new_acid),
                "Predicted plan leaves one or more additional mechs ACIDed.",
                new_acid,
            ))

    if "mechs_fire" in current or "mechs_fire" in predicted:
        compared.append("mechs_fire")
        current_fire_uids = {
            item.get("uid")
            for item in _list_or_empty(current.get("mechs_fire"))
            if isinstance(item, dict)
        }
        new_fire = [
            item for item in _list_or_empty(predicted.get("mechs_fire"))
            if isinstance(item, dict) and item.get("uid") not in current_fire_uids
        ]
        if new_fire:
            violations.append(_violation(
                "mech_fire",
                len(current_fire_uids),
                len(current_fire_uids) + len(new_fire),
                "Predicted plan leaves one or more additional mechs on Fire.",
                new_fire,
                blocking=block_mech_status_loss,
            ))

    if "mechs_webbed" in current or "mechs_webbed" in predicted:
        compared.append("mechs_webbed")
        current_web_uids = {
            item.get("uid")
            for item in _list_or_empty(current.get("mechs_webbed"))
            if isinstance(item, dict)
        }
        new_web = [
            item for item in _list_or_empty(predicted.get("mechs_webbed"))
            if isinstance(item, dict) and item.get("uid") not in current_web_uids
        ]
        if new_web:
            violations.append(_violation(
                "mech_webbed",
                len(current_web_uids),
                len(current_web_uids) + len(new_web),
                "Predicted plan leaves one or more additional mechs webbed.",
                new_web,
                blocking=block_mech_status_loss,
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

    cur_destroy = _int_or_none(current.get("destroy_objective_units_alive"))
    pred_destroy = _int_or_none(predicted.get("destroy_objective_units_alive"))
    if cur_destroy is not None and pred_destroy is not None:
        compared.append("destroy_objective_units_alive")
        if final_turn and pred_destroy > 0:
            violations.append(_violation(
                "destroy_objective_unit_alive_final",
                cur_destroy,
                pred_destroy,
                "Predicted final-turn outcome leaves one or more destroy-objective units alive.",
                {
                    "current_units": _list_or_empty(current.get("destroy_objective_units")),
                    "predicted_units": _list_or_empty(predicted.get("destroy_objective_units")),
                },
            ))

    cur_frozen = _int_or_none(current.get("protected_objective_units_frozen"))
    pred_frozen = _int_or_none(predicted.get("protected_objective_units_frozen"))
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

    cur_freeze_target = _int_or_none(current.get("freeze_building_target"))
    pred_freeze_target = _int_or_none(predicted.get("freeze_building_target"))
    freeze_target = cur_freeze_target or pred_freeze_target
    cur_freeze_thawed = _int_or_none(current.get("freeze_buildings_thawed"))
    pred_freeze_thawed = _int_or_none(predicted.get("freeze_buildings_thawed"))
    cur_freeze_alive = _int_or_none(current.get("freeze_buildings_alive"))
    pred_freeze_alive = _int_or_none(predicted.get("freeze_buildings_alive"))
    if (
        mission_id == "Mission_FreezeBldg"
        and freeze_target is not None
        and pred_freeze_thawed is not None
    ):
        compared.append("freeze_building_target")
        compared.append("freeze_buildings_thawed")
        if pred_freeze_alive is not None:
            compared.append("freeze_buildings_alive")
        impossible = pred_freeze_alive is not None and pred_freeze_alive < freeze_target
        if impossible or (final_turn and pred_freeze_thawed < freeze_target):
            violations.append(_violation(
                "freeze_building_objective_failed",
                cur_freeze_thawed if cur_freeze_thawed is not None else 0,
                pred_freeze_thawed,
                "Predicted outcome cannot complete the frozen-building thaw objective.",
                {
                    "target": freeze_target,
                    "current_alive": cur_freeze_alive,
                    "predicted_alive": pred_freeze_alive,
                    "current_buildings": _list_or_empty(current.get("freeze_buildings")),
                    "predicted_buildings": _list_or_empty(predicted.get("freeze_buildings")),
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
            "mission_id": mission_id,
            "turn": cur_turn,
            "total_turns": cur_total_turns,
            "grid_power": cur_grid,
            "buildings_alive": cur_alive,
            "building_hp_total": cur_hp,
            "pylons_alive": cur_pylons,
            "pylon_hp_total": cur_pylon_hp,
            "objective_buildings_alive": cur_obj_alive,
            "objective_building_hp_total": cur_obj_hp,
            "pods_present": cur_pods,
            "mechs_alive": cur_mechs,
            "mech_hp_total": cur_mech_hp,
            "mech_damage_taken_total": cur_mech_damage,
            "mech_damage_objective_limit": cur_mech_damage_limit,
            "mechs_acid": _list_or_empty(current.get("mechs_acid")),
            "mechs_fire": _list_or_empty(current.get("mechs_fire")),
            "mechs_webbed": _list_or_empty(current.get("mechs_webbed")),
            "mechs_on_danger": _list_or_empty(current.get("mechs_on_danger")),
            "mechs_disabled": _list_or_empty(current.get("mechs_disabled")),
            "bigbomb_alive": cur_bigbomb if isinstance(cur_bigbomb, bool) else None,
            "destroy_objective_units_alive": cur_destroy,
            "protected_objective_units_alive": cur_protected,
            "protected_objective_units_frozen": cur_frozen,
            "freeze_building_target": cur_freeze_target,
            "freeze_buildings_alive": cur_freeze_alive,
            "freeze_buildings_thawed": cur_freeze_thawed,
            "terraform_grass_remaining": cur_grass,
            "mission_mountain_target": cur_mountain_target,
            "mission_mountains_destroyed": cur_mountains,
            "mites_remaining": cur_mites,
            "mites_status_tracked": cur_mites_tracked,
            "mechs_infected": _list_or_empty(current.get("mechs_infected")),
            "mission_kill_target": cur_kill_target,
            "mission_kill_limit": cur_kill_limit,
            "mission_kills_done": cur_kills_done,
        },
        "predicted": {
            "mission_id": mission_id,
            "turn": pred_turn,
            "total_turns": pred_total_turns,
            "grid_power": pred_grid,
            "buildings_alive": pred_alive,
            "building_hp_total": pred_hp,
            "pylons_alive": pred_pylons,
            "pylon_hp_total": pred_pylon_hp,
            "objective_buildings_alive": pred_obj_alive,
            "objective_building_hp_total": pred_obj_hp,
            "pods_present": pred_pods,
            "mechs_alive": pred_mechs,
            "mech_hp_total": pred_mech_hp,
            "mech_damage_taken_total": pred_mech_damage,
            "mech_damage_objective_limit": pred_mech_damage_limit,
            "mechs_acid": _list_or_empty(predicted.get("mechs_acid")),
            "mechs_fire": _list_or_empty(predicted.get("mechs_fire")),
            "mechs_webbed": _list_or_empty(predicted.get("mechs_webbed")),
            "mechs_on_danger": _list_or_empty(predicted.get("mechs_on_danger")),
            "mechs_disabled": _list_or_empty(predicted.get("mechs_disabled")),
            "bigbomb_alive": pred_bigbomb if isinstance(pred_bigbomb, bool) else None,
            "destroy_objective_units_alive": pred_destroy,
            "protected_objective_units_alive": pred_protected,
            "protected_objective_units_frozen": pred_frozen,
            "freeze_building_target": pred_freeze_target,
            "freeze_buildings_alive": pred_freeze_alive,
            "freeze_buildings_thawed": pred_freeze_thawed,
            "terraform_grass_remaining": pred_grass,
            "mission_mountain_target": pred_mountain_target,
            "mission_mountains_destroyed": pred_mountains,
            "mites_remaining": pred_mites,
            "mites_status_tracked": pred_mites_tracked,
            "mechs_infected": _list_or_empty(predicted.get("mechs_infected")),
            "mission_kill_target": pred_kill_target,
            "mission_kill_limit": pred_kill_limit,
            "mission_kills_done": pred_kills_done,
            "mission_kills_planned": _int_or_none(predicted.get("mission_kills_planned")),
        },
    }


def plan_requires_safety_block(audit: dict[str, Any] | None,
                               *,
                               allow_dirty_plan: bool = False,
                               allow_timeline_collapse_debug: bool = False) -> bool:
    """Return True when auto_turn should stop before executing actions."""
    if not isinstance(audit, dict):
        return True
    if audit.get("status") == "UNKNOWN":
        return True
    if allow_dirty_plan:
        debug_collapse = (
            allow_timeline_collapse_debug
            or os.environ.get("ITB_ALLOW_TIMELINE_COLLAPSE_DEBUG") == "1"
        )
        allow_final_cave_pylon = final_cave_emergency_pylon_loss_allowed(audit)
        allow_final_cave_resist = final_cave_resist_gamble_allowed(audit)
        allow_final_bomb_dirty = final_bomb_dirty_consent_allowed(audit)
        return any(
            isinstance(v, dict)
            and v.get("blocking")
            and v.get("kind") in NON_OVERRIDABLE_KINDS
            and not (
                debug_collapse
                and v.get("kind") == "grid_timeline_collapse"
            )
            and not (
                allow_final_cave_pylon
                and v.get("kind") in FINAL_CAVE_EMERGENCY_PYLON_KINDS
            )
            and not (
                allow_final_cave_resist
                and v.get("kind") in FINAL_CAVE_RESIST_GAMBLE_ALLOWED_KINDS
            )
            and not (
                allow_final_bomb_dirty
                and v.get("kind") in FINAL_BOMB_DIRTY_ALLOWED_KINDS
            )
            for v in audit.get("violations", []) or []
        )
    return bool(audit.get("blocking"))


def final_bomb_dirty_consent_allowed(
    audit: dict[str, Any] | None,
) -> bool:
    """Return whether exact dirty consent may finish the last Renfield turn.

    The live loop can accept ordinary city/lab damage on the final
    ``Mission_Bomb`` turn only after review. The Renfield bombs must survive,
    grid must stay above zero, and the dirty kinds must be limited to building
    losses; protected-unit/objective losses remain non-consentable.
    """
    if not isinstance(audit, dict) or audit.get("status") != "DIRTY":
        return False
    current = audit.get("current") if isinstance(audit.get("current"), dict) else {}
    predicted = (
        audit.get("predicted") if isinstance(audit.get("predicted"), dict) else {}
    )
    mission_id = current.get("mission_id") or predicted.get("mission_id")
    if mission_id != "Mission_Bomb":
        return False

    turn = _int_or_none(current.get("turn")) or _int_or_none(predicted.get("turn"))
    total_turns = (
        _int_or_none(current.get("total_turns"))
        or _int_or_none(predicted.get("total_turns"))
    )
    if turn is None or total_turns is None or turn < total_turns:
        return False

    kinds = {
        v.get("kind")
        for v in audit.get("violations", []) or []
        if isinstance(v, dict) and v.get("blocking")
    }
    if not kinds:
        return False
    if not kinds <= FINAL_BOMB_DIRTY_ALLOWED_KINDS:
        return False

    pred_grid = _int_or_none(predicted.get("grid_power"))
    if pred_grid is None or pred_grid <= 0:
        return False

    cur_protected = _int_or_none(current.get("protected_objective_units_alive"))
    pred_protected = _int_or_none(predicted.get("protected_objective_units_alive"))
    if (
        cur_protected is None
        or pred_protected is None
        or pred_protected < cur_protected
    ):
        return False

    cur_mechs = _int_or_none(current.get("mechs_alive"))
    pred_mechs = _int_or_none(predicted.get("mechs_alive"))
    if cur_mechs is None or pred_mechs is None or pred_mechs < cur_mechs:
        return False

    for key in (
        "mechs_acid",
        "mechs_fire",
        "mechs_webbed",
        "mechs_on_danger",
        "mechs_disabled",
    ):
        if _list_or_empty(predicted.get(key)):
            return False
    return True


def final_cave_emergency_pylon_loss_allowed(
    audit: dict[str, Any] | None,
) -> bool:
    """Return whether exact dirty consent may override final-cave pylon loss."""
    if not isinstance(audit, dict) or audit.get("status") != "DIRTY":
        return False
    current = audit.get("current") if isinstance(audit.get("current"), dict) else {}
    predicted = (
        audit.get("predicted") if isinstance(audit.get("predicted"), dict) else {}
    )
    mission_id = current.get("mission_id") or predicted.get("mission_id")
    if mission_id != "Mission_Final_Cave":
        return False

    kinds = {
        v.get("kind")
        for v in audit.get("violations", []) or []
        if isinstance(v, dict) and v.get("blocking")
    }
    if not kinds:
        return False
    if not kinds & FINAL_CAVE_EMERGENCY_PYLON_KINDS:
        return False
    if not kinds <= FINAL_CAVE_EMERGENCY_ALLOWED_KINDS:
        return False

    pred_grid = _int_or_none(predicted.get("grid_power"))
    if pred_grid is None or pred_grid <= 0:
        return False
    if predicted.get("bigbomb_alive") is not True:
        return False

    cur_mechs = _int_or_none(current.get("mechs_alive"))
    pred_mechs = _int_or_none(predicted.get("mechs_alive"))
    if cur_mechs is None or pred_mechs is None or pred_mechs < cur_mechs:
        return False

    cur_mech_hp = _int_or_none(current.get("mech_hp_total"))
    pred_mech_hp = _int_or_none(predicted.get("mech_hp_total"))
    if cur_mech_hp is None or pred_mech_hp is None or pred_mech_hp < cur_mech_hp:
        return False

    for key in (
        "mechs_acid",
        "mechs_fire",
        "mechs_webbed",
        "mechs_on_danger",
        "mechs_disabled",
    ):
        if _list_or_empty(predicted.get(key)):
            return False
    return True


def final_cave_resist_gamble_allowed(
    audit: dict[str, Any] | None,
) -> bool:
    """Return whether exact dirty consent may attempt a final-cave resist win.

    This is the narrow Hail Mary exception: on the last Renfield Bomb turn, a
    reviewed plan can be executed even when the deterministic model predicts
    grid collapse, provided the bomb and all mechs survive and the only
    blocking losses are ordinary final-cave pylons/buildings/grid.
    """
    if not isinstance(audit, dict) or audit.get("status") != "DIRTY":
        return False
    current = audit.get("current") if isinstance(audit.get("current"), dict) else {}
    predicted = (
        audit.get("predicted") if isinstance(audit.get("predicted"), dict) else {}
    )
    mission_id = current.get("mission_id") or predicted.get("mission_id")
    if mission_id != "Mission_Final_Cave":
        return False

    turn = _int_or_none(current.get("turn")) or _int_or_none(predicted.get("turn"))
    total_turns = (
        _int_or_none(current.get("total_turns"))
        or _int_or_none(predicted.get("total_turns"))
    )
    if turn is None or total_turns is None or turn < total_turns:
        return False

    kinds = {
        v.get("kind")
        for v in audit.get("violations", []) or []
        if isinstance(v, dict) and v.get("blocking")
    }
    if "grid_timeline_collapse" not in kinds:
        return False
    if not kinds <= FINAL_CAVE_RESIST_GAMBLE_ALLOWED_KINDS:
        return False

    pred_grid = _int_or_none(predicted.get("grid_power"))
    if pred_grid is None or pred_grid > 0:
        return False
    if predicted.get("bigbomb_alive") is not True:
        return False

    cur_mechs = _int_or_none(current.get("mechs_alive"))
    pred_mechs = _int_or_none(predicted.get("mechs_alive"))
    if cur_mechs is None or pred_mechs is None or pred_mechs < cur_mechs:
        return False

    cur_mech_hp = _int_or_none(current.get("mech_hp_total"))
    pred_mech_hp = _int_or_none(predicted.get("mech_hp_total"))
    if cur_mech_hp is None or pred_mech_hp is None or pred_mech_hp < cur_mech_hp:
        return False

    pred_pylons = _int_or_none(predicted.get("pylons_alive"))
    if pred_pylons is not None and pred_pylons <= 0:
        return False
    pred_pylon_hp = _int_or_none(predicted.get("pylon_hp_total"))
    if pred_pylon_hp is not None and pred_pylon_hp <= 0:
        return False

    for key in (
        "mechs_acid",
        "mechs_fire",
        "mechs_webbed",
        "mechs_on_danger",
        "mechs_disabled",
    ):
        if _list_or_empty(predicted.get(key)):
            return False
    return True


def safety_loss_profile(audit: dict[str, Any] | None) -> dict[str, Any]:
    """Summarize dirty-plan tradeoffs in a stable, machine-readable shape."""
    if not isinstance(audit, dict):
        return {
            "label": "unknown",
            "blocking": False,
            "losses": {},
            "non_overridable": False,
        }

    losses: dict[str, int] = {}
    kinds: list[str] = []
    non_overridable = False
    for violation in audit.get("violations", []) or []:
        if not isinstance(violation, dict):
            continue
        kind = violation.get("kind")
        if not isinstance(kind, str):
            continue
        kinds.append(kind)
        non_overridable = non_overridable or kind in NON_OVERRIDABLE_KINDS
        metric = LOSS_KINDS.get(kind)
        if metric is None:
            continue
        delta = violation.get("delta")
        if isinstance(delta, int) and delta < 0:
            amount = -delta
        else:
            current = violation.get("current")
            predicted = violation.get("predicted")
            amount = 1
            if isinstance(current, int) and isinstance(predicted, int):
                amount = max(1, current - predicted)
        losses[metric] = losses.get(metric, 0) + amount

    label = _profile_label(audit.get("status"), kinds, non_overridable)
    return {
        "label": label,
        "blocking": bool(audit.get("blocking")),
        "losses": losses,
        "non_overridable": non_overridable,
    }


def _profile_label(status: Any,
                   kinds: list[str],
                   non_overridable: bool) -> str:
    if status == "CLEAN":
        return "clean"
    if status == "WARN":
        return "warning"
    if status == "UNKNOWN":
        return "unknown"
    kind_set = set(kinds)
    if "grid_timeline_collapse" in kind_set:
        return "timeline_collapse"
    if "pylon_destroyed" in kind_set or "pylon_hp_loss" in kind_set:
        return "pylon_loss"
    if non_overridable:
        return "objective_loss"
    if "grid_damage" in kind_set and "mech_lost" in kind_set:
        return "grid_and_mech_loss"
    if "grid_damage" in kind_set:
        return "grid_loss"
    if "building_destroyed" in kind_set:
        return "building_loss"
    if "mech_lost" in kind_set:
        return "mech_loss"
    if "building_hp_loss" in kind_set:
        return "building_hp_loss"
    if (
        "mech_disabled" in kind_set
        or "mech_on_danger" in kind_set
        or "mech_acid" in kind_set
        or "mech_fire" in kind_set
        or "mech_webbed" in kind_set
    ):
        return "mech_disabled"
    if "pod_lost" in kind_set:
        return "pod_loss"
    if "mech_hp_loss" in kind_set:
        return "mech_hp_loss"
    if kinds:
        return "mixed_dirty"
    return "unknown"
