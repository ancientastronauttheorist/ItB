"""Validate and correlate build-keyed selected-record/queue observations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


SCHEMA_VERSION = 1
SNAPSHOT_KIND = "native_selected_queue_hw_observer_snapshot"
ANALYSIS_KIND = "selected_queue_hw_correlation"
OBSERVER_VERSION = "observatory-selected-queue-hw-observer/1"


class SelectedQueueHwError(RuntimeError):
    """Raised when selected/queue evidence is malformed or unresolved."""


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise SelectedQueueHwError(f"{label} fields differ from the contract")


def _integer(value: object, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        raise SelectedQueueHwError(f"{label} is invalid")
    return value


def _sha256(value: object) -> str:
    payload = (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _point(record: Mapping[str, Any], prefix: str, label: str) -> list[int]:
    x = _integer(record[f"{prefix}_x"], f"{label}.{prefix}_x", minimum=0)
    y = _integer(record[f"{prefix}_y"], f"{label}.{prefix}_y", minimum=0)
    if x > 7 or y > 7:
        raise SelectedQueueHwError(f"{label}.{prefix} is off board")
    return [x, y]


def _validate_receipt(
    receipt: Mapping[str, Any], observed_module_sha256: str
) -> dict[str, Any]:
    if receipt.get("schema_version") != 1 or receipt.get("kind") != (
        "observatory_selected_queue_hw_observer_build"
    ):
        raise SelectedQueueHwError("selected/queue build receipt is invalid")
    required = {
        "observer_version": OBSERVER_VERSION,
        "build_id": "13725832",
        "architecture": "x86",
        "executable_sha256": (
            "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
        ),
        "module_sha256": observed_module_sha256,
        "hardware_breakpoint_plan_sha256": (
            "f99e1ba7b130799f27f6cc4e7a12aa4198bccb624ce994ae6a3fc063c30511b6"
        ),
        "boundary_map_canonical_sha256": (
            "ded91fdf8181b2ae310644ece211f77fecc4393c3cd1c43867cfd353af3d6dc2"
        ),
        "selected_prebytes_sha256": (
            "8e2e44aae1e456d15513da12e097135d095ae740d579715d19e83cb65c35650b"
        ),
        "queue_prebytes_sha256": (
            "f63c44a5d0405f6e008755d711095ec30ac330c6b1bfcfbb43340ca8b0ed84b3"
        ),
    }
    for field, expected in required.items():
        if receipt.get(field) != expected:
            raise SelectedQueueHwError(
                f"selected/queue build receipt {field} differs"
            )
    if receipt.get("loaded_or_armed") is not False:
        raise SelectedQueueHwError("selected/queue build was not inert")
    reproducibility = receipt.get("reproducibility")
    machine = receipt.get("machine_attestation")
    veh = machine.get("veh") if isinstance(machine, Mapping) else None
    if (
        not isinstance(reproducibility, Mapping)
        or reproducibility.get("independent_build_count") != 2
        or reproducibility.get("module_bytes_identical") is not True
        or reproducibility.get("attestations_identical") is not True
        or not isinstance(veh, Mapping)
        or veh.get("direct_or_indirect_call_count") != 0
        or veh.get("windows_api_call_count") != 0
        or machine.get("loader_entry_absent") is not True
        or machine.get("executable_mutation_api_imports_absent") is not True
        or receipt.get("executable_bytes_modified") is not False
    ):
        raise SelectedQueueHwError("selected/queue build safety attestation failed")
    return required


def validate_selected_queue_snapshot(
    snapshot: Mapping[str, Any],
    *,
    build_receipt: Mapping[str, Any],
    observed_module_sha256: str,
) -> dict[str, Any]:
    """Validate one restored, single-enemy hardware-breakpoint snapshot."""
    if not isinstance(snapshot, Mapping):
        raise SelectedQueueHwError("selected/queue snapshot must be an object")
    _exact_keys(
        snapshot,
        {
            "schema_version",
            "kind",
            "observer_version",
            "capture_id",
            "identity",
            "integrity",
            "records",
            "summary",
        },
        "snapshot",
    )
    if (
        snapshot["schema_version"] != SCHEMA_VERSION
        or snapshot["kind"] != SNAPSHOT_KIND
        or snapshot["observer_version"] != OBSERVER_VERSION
        or type(snapshot["capture_id"]) is not str
        or not snapshot["capture_id"]
    ):
        raise SelectedQueueHwError("selected/queue snapshot header is invalid")
    expected = _validate_receipt(build_receipt, observed_module_sha256)

    identity = snapshot["identity"]
    if not isinstance(identity, Mapping):
        raise SelectedQueueHwError("snapshot.identity must be an object")
    _exact_keys(
        identity,
        {
            "platform",
            "architecture",
            "build_id",
            "executable_sha256",
            "executable_size",
            "inventory_sha256",
            "boundary_map_sha256",
            "hardware_breakpoint_plan_sha256",
            "selected_prebytes_sha256",
            "queue_prebytes_sha256",
        },
        "snapshot.identity",
    )
    identity_expected = {
        "platform": "windows",
        "architecture": expected["architecture"],
        "build_id": expected["build_id"],
        "executable_sha256": expected["executable_sha256"],
        "executable_size": build_receipt.get("executable_size"),
        "inventory_sha256": build_receipt.get("inventory_canonical_sha256"),
        "boundary_map_sha256": expected["boundary_map_canonical_sha256"],
        "hardware_breakpoint_plan_sha256": expected[
            "hardware_breakpoint_plan_sha256"
        ],
        "selected_prebytes_sha256": expected["selected_prebytes_sha256"],
        "queue_prebytes_sha256": expected["queue_prebytes_sha256"],
    }
    if dict(identity) != identity_expected:
        raise SelectedQueueHwError("snapshot identity differs from build receipt")

    integrity = snapshot["integrity"]
    if not isinstance(integrity, Mapping):
        raise SelectedQueueHwError("snapshot.integrity must be an object")
    _exact_keys(
        integrity,
        {
            "state",
            "complete",
            "overflow_count",
            "ordering_error_count",
            "pointer_fault_count",
            "transition_mismatch_count",
            "wrong_thread_count",
            "unexpected_breakpoint_count",
            "torn_record_count",
            "debug_registers_armed",
            "debug_registers_cleared",
            "veh_installed",
            "veh_removed",
            "executable_file_released",
            "executable_bytes_modified",
            "seam_bytes_unchanged",
        },
        "snapshot.integrity",
    )
    for field in (
        "overflow_count",
        "ordering_error_count",
        "pointer_fault_count",
        "transition_mismatch_count",
        "wrong_thread_count",
        "unexpected_breakpoint_count",
        "torn_record_count",
    ):
        if _integer(integrity[field], f"snapshot.integrity.{field}", minimum=0) != 0:
            raise SelectedQueueHwError(f"snapshot reports {field}")
    if (
        integrity["state"] != "restored"
        or integrity["complete"] is not True
        or integrity["debug_registers_armed"] is not False
        or integrity["debug_registers_cleared"] is not True
        or integrity["veh_installed"] is not False
        or integrity["veh_removed"] is not True
        or integrity["executable_file_released"] is not True
        or integrity["executable_bytes_modified"] is not False
        or integrity["seam_bytes_unchanged"] is not True
    ):
        raise SelectedQueueHwError("selected/queue observer was not fully restored")

    summary = snapshot["summary"]
    records = snapshot["records"]
    if not isinstance(summary, Mapping) or not isinstance(records, list):
        raise SelectedQueueHwError("snapshot records or summary is invalid")
    _exact_keys(
        summary,
        {
            "record_count",
            "selected_count",
            "queue_count",
            "pair_count",
            "thread_count",
            "last_sequence",
            "pending_selection",
        },
        "snapshot.summary",
    )
    expected_summary = {
        "record_count": 2,
        "selected_count": 1,
        "queue_count": 1,
        "pair_count": 1,
        "thread_count": 1,
        "last_sequence": 1,
        "pending_selection": False,
    }
    if dict(summary) != expected_summary or len(records) != 2:
        raise SelectedQueueHwError("snapshot is not one exact selected/queue pair")

    selected, queued = records
    selected_fields = {
        "kind",
        "seq",
        "pair_index",
        "pawn_id",
        "current_weapon_raw",
        "base_current_weapon_raw",
        "ai_dest_x",
        "ai_dest_y",
        "ai_target_x",
        "ai_target_y",
        "selected_field_4_raw",
        "selected_field_5_raw",
    }
    queue_fields = {
        "kind",
        "seq",
        "pair_index",
        "pawn_id",
        "current_weapon_raw",
        "base_current_weapon_raw",
        "target_x",
        "target_y",
        "origin_x",
        "origin_y",
        "queued_shot_x",
        "queued_shot_y",
        "queued_skill_raw",
    }
    if not isinstance(selected, Mapping) or not isinstance(queued, Mapping):
        raise SelectedQueueHwError("snapshot records must be objects")
    _exact_keys(selected, selected_fields, "snapshot.records[0]")
    _exact_keys(queued, queue_fields, "snapshot.records[1]")
    if (
        selected["kind"] != "selected_record"
        or selected["seq"] != 0
        or selected["pair_index"] != 0
        or queued["kind"] != "queued_action"
        or queued["seq"] != 1
        or queued["pair_index"] != 0
    ):
        raise SelectedQueueHwError("snapshot record order differs")
    for label, record, fields in (
        (
            "snapshot.records[0]",
            selected,
            (
                "pawn_id",
                "current_weapon_raw",
                "base_current_weapon_raw",
                "selected_field_4_raw",
                "selected_field_5_raw",
            ),
        ),
        (
            "snapshot.records[1]",
            queued,
            (
                "pawn_id",
                "current_weapon_raw",
                "base_current_weapon_raw",
                "queued_skill_raw",
            ),
        ),
    ):
        for field in fields:
            _integer(record[field], f"{label}.{field}")
    _point(selected, "ai_dest", "snapshot.records[0]")
    _point(selected, "ai_target", "snapshot.records[0]")
    _point(queued, "target", "snapshot.records[1]")
    _point(queued, "origin", "snapshot.records[1]")
    _point(queued, "queued_shot", "snapshot.records[1]")
    return {
        "capture_id": snapshot["capture_id"],
        "identity": dict(identity),
        "snapshot_sha256": _sha256(snapshot),
        "module_sha256": observed_module_sha256,
        "selected": dict(selected),
        "queued": dict(queued),
    }


def correlate_selected_queue_snapshot(
    snapshot: Mapping[str, Any],
    outcome: Mapping[str, Any],
    *,
    build_receipt: Mapping[str, Any],
    observed_module_sha256: str,
) -> dict[str, Any]:
    """Correlate the native pair internally and with the next bridge queue."""
    validated = validate_selected_queue_snapshot(
        snapshot,
        build_receipt=build_receipt,
        observed_module_sha256=observed_module_sha256,
    )
    if not isinstance(outcome, Mapping):
        raise SelectedQueueHwError("bridge outcome must be an object")
    selected = validated["selected"]
    queued = validated["queued"]
    reasons: list[str] = []
    selected_dest = _point(selected, "ai_dest", "selected")
    selected_target = _point(selected, "ai_target", "selected")
    queue_target = _point(queued, "target", "queued")
    queue_origin = _point(queued, "origin", "queued")
    queued_shot = _point(queued, "queued_shot", "queued")
    if selected["pawn_id"] != queued["pawn_id"]:
        reasons.append("pawn_id_mismatch")
    if selected_dest != queue_origin:
        reasons.append("destination_origin_mismatch")
    if selected_target != queue_target or selected_target != queued_shot:
        reasons.append("selected_target_queue_mismatch")
    if selected["current_weapon_raw"] != queued["current_weapon_raw"]:
        reasons.append("current_weapon_drift")
    if selected["current_weapon_raw"] != queued["queued_skill_raw"]:
        reasons.append("selected_weapon_queue_skill_mismatch")

    if outcome.get("mission_id") != "Mission_Power":
        reasons.append("bridge_mission_mismatch")
    if outcome.get("phase") != "combat_player":
        reasons.append("bridge_phase_mismatch")
    if outcome.get("spawning_tiles") != []:
        reasons.append("bridge_spawn_activity")
    if outcome.get("environment_danger") not in (None, []):
        reasons.append("bridge_environment_activity")
    if outcome.get("environment_danger_v2") not in (None, []):
        reasons.append("bridge_environment_v2_activity")
    units = outcome.get("units")
    enemies = (
        [unit for unit in units if isinstance(unit, Mapping) and unit.get("team") == 6]
        if isinstance(units, list)
        else []
    )
    matching = [unit for unit in enemies if unit.get("uid") == selected["pawn_id"]]
    bridge_enemy: Mapping[str, Any] | None = matching[0] if len(matching) == 1 else None
    bridge_queue_mode: str | None = None
    bridge_queue_target: object = None
    bridge_targeted_tiles: list[list[int]] = []
    if len(enemies) != 1:
        reasons.append("bridge_enemy_count_mismatch")
    if bridge_enemy is None:
        reasons.append("bridge_selected_enemy_missing")
    else:
        if bridge_enemy.get("type") != "Firefly1":
            reasons.append("bridge_enemy_type_mismatch")
        if bridge_enemy.get("has_queued_attack") is not True:
            reasons.append("bridge_queue_missing")
        if [bridge_enemy.get("x"), bridge_enemy.get("y")] != queue_origin:
            reasons.append("bridge_origin_mismatch")
        reported_origin = bridge_enemy.get("queued_origin")
        if reported_origin is not None and reported_origin != queue_origin:
            reasons.append("bridge_queued_origin_mismatch")
        bridge_queue_target = bridge_enemy.get("queued_target_raw")
        if bridge_queue_target is None:
            bridge_queue_target = bridge_enemy.get("queued_target")
        if bridge_queue_target is not None:
            bridge_queue_mode = "exact_queue_field"
            if bridge_queue_target != queued_shot:
                reasons.append("bridge_queued_target_mismatch")
        else:
            # Synthetic trial pawns are queued entirely in memory.  The normal
            # bridge can therefore see GetSelectedWeapon() and the affected
            # tiles while its save-backed piOrigin/piQueuedShot fields remain
            # absent.  Corroborate the native immediate target against that
            # independent attack ray instead of inventing missing save data.
            raw_targeted = outcome.get("targeted_tiles")
            if isinstance(raw_targeted, list):
                bridge_targeted_tiles = [
                    [tile[0], tile[1]]
                    for tile in raw_targeted
                    if (
                        isinstance(tile, list)
                        and len(tile) == 2
                        and all(type(coord) is int for coord in tile)
                    )
                ]
            dx = queued_shot[0] - queue_origin[0]
            dy = queued_shot[1] - queue_origin[1]
            ray_matches = [
                tile
                for tile in bridge_targeted_tiles
                if (
                    (tile[0] - queue_origin[0]) * dy
                    == (tile[1] - queue_origin[1]) * dx
                    and (tile[0] - queue_origin[0]) * dx
                    + (tile[1] - queue_origin[1]) * dy
                    > 0
                )
            ]
            bridge_queue_mode = "targeted_tiles_ray"
            if abs(dx) + abs(dy) != 1 or not ray_matches:
                reasons.append("bridge_target_direction_mismatch")

    unique_reasons = list(dict.fromkeys(reasons))
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": ANALYSIS_KIND,
        "capture_id": validated["capture_id"],
        "identity": validated["identity"],
        "snapshot_sha256": validated["snapshot_sha256"],
        "module_sha256": validated["module_sha256"],
        "status": "correlated" if not unique_reasons else "unresolved",
        "reasons": unique_reasons,
        "native": {
            "pawn_id": selected["pawn_id"],
            "ai_destination": selected_dest,
            "ai_target": selected_target,
            "queue_origin": queue_origin,
            "queue_target": queue_target,
            "queued_shot": queued_shot,
            "current_weapon_raw": selected["current_weapon_raw"],
            "queued_skill_raw": queued["queued_skill_raw"],
            "selected_rank_fields_raw": [
                selected["selected_field_4_raw"],
                selected["selected_field_5_raw"],
            ],
            "base_current_weapon_raw": selected["base_current_weapon_raw"],
        },
        "bridge": {
            "enemy_count": len(enemies),
            "matched_uid": bridge_enemy is not None,
            "queue_corroboration": bridge_queue_mode,
            "queued_origin": (
                bridge_enemy.get("queued_origin") if bridge_enemy else None
            ),
            "queued_target": bridge_queue_target,
            "targeted_tiles": bridge_targeted_tiles,
        },
        "summary": {
            "native_pair_count": 1,
            "internal_field_matches": not any(
                reason
                in {
                    "pawn_id_mismatch",
                    "destination_origin_mismatch",
                    "selected_target_queue_mismatch",
                    "current_weapon_drift",
                    "selected_weapon_queue_skill_mismatch",
                }
                for reason in unique_reasons
            ),
            "bridge_queue_matches": not any(
                reason.startswith("bridge_") for reason in unique_reasons
            ),
            "correlated": not unique_reasons,
        },
    }
