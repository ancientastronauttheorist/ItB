"""Validate and replay build-keyed native enemy-tournament observations."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from src.observatory.enemy_record_selector_boundary import (
    EnemyRecordSelectorBoundaryError,
    replay_enemy_record_selector,
)
from src.observatory.msvc_rng_replay import advance_state


SCHEMA_VERSION = 1
SNAPSHOT_KIND = "native_enemy_tournament_hw_snapshot"
ANALYSIS_KIND = "enemy_tournament_hw_replay_correlation"
OBSERVER_VERSION = "observatory-enemy-tournament-hw-observer/1"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_PLAN_SHA256 = (
    "e9af1b68805383f062d222c85b01aebb83e4febb3c92e72942634ae9529afc25"
)
EXPECTED_BOUNDARY_MAP_SHA256 = (
    "ded91fdf8181b2ae310644ece211f77fecc4393c3cd1c43867cfd353af3d6dc2"
)
EXPECTED_RNG_RETURN_MAP_SHA256 = (
    "7da4ababb6aa91d7b834e68ea6d42a8a40b6ae379531f42cbbc96556cdcaae48"
)
EXPECTED_RECORD_SELECTOR_SHA256 = (
    "1a7ef818d1e889849e68301cb3e94d2291bc908f98b7501c5033d390ba110bfc"
)
EXPECTED_SELECTED_QUEUE_SOURCE_SHA256 = (
    "c57293d35e4bba11edfc1b66233368fb32a3ce51c04c01aea681a9024c3b2be6"
)
EXPECTED_SELECTOR_PREBYTES_SHA256 = hashlib.sha256(
    bytes.fromhex("558bec6aff68")
).hexdigest()
EXPECTED_SELECTED_PREBYTES_SHA256 = hashlib.sha256(
    bytes.fromhex("8b0152ff5028")
).hexdigest()
EXPECTED_QUEUE_PREBYTES_SHA256 = hashlib.sha256(
    bytes.fromhex("83ec188bcc")
).hexdigest()
EXPECTED_RNG_STATE_OWNER_SHA256 = (
    "db0c599f49594fdb9856180cf4337d3b95a0bdd7b1d227c662e25caf2a76a12f"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_U32_RE = re.compile(r"^0x[0-9a-f]{8}$")
_CAPTURE_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
_SIGNED_MIN = -(1 << 31)
_SIGNED_MAX = (1 << 31) - 1


class EnemyTournamentHwError(RuntimeError):
    """Raised when tournament evidence is malformed or fails exact replay."""


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise EnemyTournamentHwError(f"{label} fields differ from the contract")


def _integer(
    value: object,
    label: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if (
        type(value) is not int
        or (minimum is not None and value < minimum)
        or (maximum is not None and value > maximum)
    ):
        raise EnemyTournamentHwError(f"{label} is invalid")
    return value


def _signed(value: object, label: str) -> int:
    return _integer(value, label, minimum=_SIGNED_MIN, maximum=_SIGNED_MAX)


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


def _u32(value: object, label: str) -> int:
    if type(value) is not str or _U32_RE.fullmatch(value) is None:
        raise EnemyTournamentHwError(f"{label} is not a canonical u32")
    return int(value, 16)


def _point(
    record: Mapping[str, Any],
    prefix: str,
    label: str,
    *,
    width: int,
    height: int,
) -> list[int]:
    x = _integer(record[f"{prefix}_x"], f"{label}.{prefix}_x", minimum=0)
    y = _integer(record[f"{prefix}_y"], f"{label}.{prefix}_y", minimum=0)
    if x >= width or y >= height:
        raise EnemyTournamentHwError(f"{label}.{prefix} is off board")
    return [x, y]


def _validate_receipt(
    receipt: Mapping[str, Any], observed_module_sha256: str
) -> dict[str, Any]:
    if (
        not isinstance(receipt, Mapping)
        or receipt.get("schema_version") != 1
        or receipt.get("kind")
        != "observatory_enemy_tournament_hw_observer_build"
    ):
        raise EnemyTournamentHwError("enemy-tournament build receipt is invalid")
    if (
        type(observed_module_sha256) is not str
        or _SHA256_RE.fullmatch(observed_module_sha256) is None
    ):
        raise EnemyTournamentHwError("observed module SHA-256 is invalid")
    required = {
        "observer_version": OBSERVER_VERSION,
        "build_id": "13725832",
        "architecture": "x86",
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        "executable_size": 5_530_112,
        "module_sha256": observed_module_sha256,
        "hardware_breakpoint_plan_sha256": EXPECTED_PLAN_SHA256,
        "boundary_map_canonical_sha256": EXPECTED_BOUNDARY_MAP_SHA256,
        "rng_return_map_sha256": EXPECTED_RNG_RETURN_MAP_SHA256,
        "record_selector_boundary_canonical_sha256": (
            EXPECTED_RECORD_SELECTOR_SHA256
        ),
        "selected_queue_source_sha256": EXPECTED_SELECTED_QUEUE_SOURCE_SHA256,
        "selector_prebytes_sha256": EXPECTED_SELECTOR_PREBYTES_SHA256,
        "selected_prebytes_sha256": EXPECTED_SELECTED_PREBYTES_SHA256,
        "queue_prebytes_sha256": EXPECTED_QUEUE_PREBYTES_SHA256,
        "rng_state_owner_sha256": EXPECTED_RNG_STATE_OWNER_SHA256,
    }
    for field, expected in required.items():
        if receipt.get(field) != expected:
            raise EnemyTournamentHwError(
                f"enemy-tournament build receipt {field} differs"
            )
    reproducibility = receipt.get("reproducibility")
    source = receipt.get("source_attestation")
    machine = receipt.get("machine_attestation")
    veh = machine.get("veh") if isinstance(machine, Mapping) else None
    if (
        receipt.get("loaded_or_armed") is not False
        or receipt.get("executable_bytes_modified") is not False
        or not isinstance(reproducibility, Mapping)
        or reproducibility.get("independent_build_count") != 2
        or reproducibility.get("module_bytes_identical") is not True
        or reproducibility.get("attestations_identical") is not True
        or not isinstance(source, Mapping)
        or source.get("selected_queue_dependency_include_present") is not True
        or source.get("historical_opener_export_neutralized") is not True
        or source.get("executable_mutation_api_text_absent") is not True
        or not isinstance(machine, Mapping)
        or machine.get("loader_entry_absent") is not True
        or machine.get("executable_mutation_api_imports_absent") is not True
        or not isinstance(veh, Mapping)
        or veh.get("direct_or_indirect_call_count") != 0
        or veh.get("windows_api_call_count") != 0
        or veh.get("x87_mmx_sse_avx_instruction_count") != 0
    ):
        raise EnemyTournamentHwError(
            "enemy-tournament build safety attestation failed"
        )
    return required


def _validate_integrity(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EnemyTournamentHwError("snapshot.integrity must be an object")
    _exact_keys(
        value,
        {
            "state",
            "complete",
            "overflow_count",
            "ordering_error_count",
            "pointer_fault_count",
            "transition_mismatch_count",
            "wrong_thread_count",
            "unexpected_breakpoint_count",
            "torn_candidate_count",
            "torn_record_count",
            "debug_registers_armed",
            "debug_registers_cleared",
            "veh_installed",
            "veh_removed",
            "executable_file_released",
            "executable_bytes_modified",
            "seam_bytes_unchanged",
            "addresses_or_pointers_published",
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
        "torn_candidate_count",
        "torn_record_count",
    ):
        if _integer(value[field], f"snapshot.integrity.{field}", minimum=0) != 0:
            raise EnemyTournamentHwError(f"snapshot reports {field}")
    if (
        value["state"] != "restored"
        or value["complete"] is not True
        or value["debug_registers_armed"] is not False
        or value["debug_registers_cleared"] is not True
        or value["veh_installed"] is not False
        or value["veh_removed"] is not True
        or value["executable_file_released"] is not True
        or value["executable_bytes_modified"] is not False
        or value["seam_bytes_unchanged"] is not True
        or value["addresses_or_pointers_published"] is not False
    ):
        raise EnemyTournamentHwError(
            "enemy-tournament observer was not fully restored"
        )
    return dict(value)


def _validate_candidates(value: object) -> list[dict[str, int]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 256:
        raise EnemyTournamentHwError("candidate_records count is invalid")
    expected = {
        "seq",
        "destination_x",
        "destination_y",
        "target_x",
        "target_y",
        "target_score",
        "positioning_score",
    }
    records: list[dict[str, int]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise EnemyTournamentHwError(f"candidate_records[{index}] is invalid")
        _exact_keys(raw, expected, f"candidate_records[{index}]")
        if raw["seq"] != index:
            raise EnemyTournamentHwError("candidate record order differs")
        records.append(
            {
                field: _signed(raw[field], f"candidate_records[{index}].{field}")
                for field in expected
                if field != "seq"
            }
        )
    return records


def validate_enemy_tournament_snapshot(
    snapshot: Mapping[str, Any],
    *,
    build_receipt: Mapping[str, Any],
    observed_module_sha256: str,
) -> dict[str, Any]:
    """Validate a restored snapshot and require exact selector/RNG replay."""
    if not isinstance(snapshot, Mapping):
        raise EnemyTournamentHwError("enemy-tournament snapshot must be an object")
    _exact_keys(
        snapshot,
        {
            "schema_version",
            "kind",
            "observer_version",
            "capture_id",
            "identity",
            "integrity",
            "selector_context",
            "candidate_records",
            "selected_record",
            "queued_action",
            "summary",
        },
        "snapshot",
    )
    capture_id = snapshot["capture_id"]
    if (
        snapshot["schema_version"] != SCHEMA_VERSION
        or snapshot["kind"] != SNAPSHOT_KIND
        or snapshot["observer_version"] != OBSERVER_VERSION
        or type(capture_id) is not str
        or _CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise EnemyTournamentHwError("enemy-tournament snapshot header is invalid")
    expected = _validate_receipt(build_receipt, observed_module_sha256)

    identity = snapshot["identity"]
    if not isinstance(identity, Mapping):
        raise EnemyTournamentHwError("snapshot.identity must be an object")
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
            "rng_return_map_sha256",
            "record_selector_boundary_sha256",
            "selected_queue_source_sha256",
            "hardware_breakpoint_plan_sha256",
            "selector_prebytes_sha256",
            "selected_prebytes_sha256",
            "queue_prebytes_sha256",
            "rng_state_owner_sha256",
        },
        "snapshot.identity",
    )
    identity_expected = {
        "platform": "windows",
        "architecture": expected["architecture"],
        "build_id": expected["build_id"],
        "executable_sha256": expected["executable_sha256"],
        "executable_size": expected["executable_size"],
        "inventory_sha256": build_receipt.get("inventory_canonical_sha256"),
        "boundary_map_sha256": expected["boundary_map_canonical_sha256"],
        "rng_return_map_sha256": expected["rng_return_map_sha256"],
        "record_selector_boundary_sha256": expected[
            "record_selector_boundary_canonical_sha256"
        ],
        "selected_queue_source_sha256": expected[
            "selected_queue_source_sha256"
        ],
        "hardware_breakpoint_plan_sha256": expected[
            "hardware_breakpoint_plan_sha256"
        ],
        "selector_prebytes_sha256": expected["selector_prebytes_sha256"],
        "selected_prebytes_sha256": expected["selected_prebytes_sha256"],
        "queue_prebytes_sha256": expected["queue_prebytes_sha256"],
        "rng_state_owner_sha256": expected["rng_state_owner_sha256"],
    }
    if dict(identity) != identity_expected:
        raise EnemyTournamentHwError("snapshot identity differs from build receipt")
    integrity = _validate_integrity(snapshot["integrity"])

    context = snapshot["selector_context"]
    if not isinstance(context, Mapping):
        raise EnemyTournamentHwError("selector_context must be an object")
    _exact_keys(
        context,
        {
            "pawn_id",
            "current_weapon_raw",
            "base_current_weapon_raw",
            "board_width",
            "board_height",
            "interior_favorable",
            "selector_rng_state_before",
            "selector_rng_state_after",
        },
        "selector_context",
    )
    pawn_id = _integer(context["pawn_id"], "selector_context.pawn_id", minimum=0)
    current_weapon = _signed(
        context["current_weapon_raw"], "selector_context.current_weapon_raw"
    )
    base_weapon = _signed(
        context["base_current_weapon_raw"],
        "selector_context.base_current_weapon_raw",
    )
    width = _integer(
        context["board_width"], "selector_context.board_width", minimum=1
    )
    height = _integer(
        context["board_height"], "selector_context.board_height", minimum=1
    )
    if type(context["interior_favorable"]) is not bool:
        raise EnemyTournamentHwError("selector_context.interior_favorable is invalid")
    rng_before = _u32(
        context["selector_rng_state_before"],
        "selector_context.selector_rng_state_before",
    )
    rng_after = _u32(
        context["selector_rng_state_after"],
        "selector_context.selector_rng_state_after",
    )
    candidates = _validate_candidates(snapshot["candidate_records"])

    selected = snapshot["selected_record"]
    queued = snapshot["queued_action"]
    if not isinstance(selected, Mapping) or not isinstance(queued, Mapping):
        raise EnemyTournamentHwError("selected_record or queued_action is invalid")
    _exact_keys(
        selected,
        {
            "kind",
            "seq",
            "pawn_id",
            "current_weapon_raw",
            "base_current_weapon_raw",
            "ai_dest_x",
            "ai_dest_y",
            "ai_target_x",
            "ai_target_y",
            "selected_field_4_raw",
            "selected_field_5_raw",
        },
        "selected_record",
    )
    _exact_keys(
        queued,
        {
            "kind",
            "seq",
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
        },
        "queued_action",
    )
    if (
        selected["kind"] != "selected_record"
        or selected["seq"] != 0
        or queued["kind"] != "queued_action"
        or queued["seq"] != 1
    ):
        raise EnemyTournamentHwError("selected/queue event order differs")
    for label, record, fields in (
        (
            "selected_record",
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
            "queued_action",
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
            _signed(record[field], f"{label}.{field}")
    selected_dest = _point(
        selected, "ai_dest", "selected_record", width=width, height=height
    )
    selected_target = _point(
        selected, "ai_target", "selected_record", width=width, height=height
    )
    queue_target = _point(
        queued, "target", "queued_action", width=width, height=height
    )
    queue_origin = _point(
        queued, "origin", "queued_action", width=width, height=height
    )
    queued_shot = _point(
        queued, "queued_shot", "queued_action", width=width, height=height
    )

    selected_record = {
        "destination_x": selected_dest[0],
        "destination_y": selected_dest[1],
        "target_x": selected_target[0],
        "target_y": selected_target[1],
        "target_score": selected["selected_field_4_raw"],
        "positioning_score": selected["selected_field_5_raw"],
    }
    try:
        replay = replay_enemy_record_selector(
            candidates, rng_before, board_width=width, board_height=height
        )
    except EnemyRecordSelectorBoundaryError as exc:
        raise EnemyTournamentHwError(f"native selector replay failed: {exc}") from exc
    expected_after = rng_before
    for _ in range(replay["draw_count"]):
        expected_after = advance_state(expected_after)
    if replay["selected_record"] != selected_record:
        raise EnemyTournamentHwError("selected record differs from exact replay")
    if rng_after != expected_after:
        raise EnemyTournamentHwError("selector RNG-after state differs from exact replay")
    if context["interior_favorable"] is not replay["interior_favorable"]:
        raise EnemyTournamentHwError("native interior-favorable flag differs from replay")
    if (
        selected["pawn_id"] != pawn_id
        or queued["pawn_id"] != pawn_id
        or selected["current_weapon_raw"] != current_weapon
        or queued["current_weapon_raw"] != current_weapon
        or queued["queued_skill_raw"] != current_weapon
        or selected["base_current_weapon_raw"] != base_weapon
        or queued["base_current_weapon_raw"] != current_weapon
        or selected_dest != queue_origin
        or selected_target != queue_target
        or selected_target != queued_shot
    ):
        raise EnemyTournamentHwError("selected record does not bind to queue commit")

    summary = snapshot["summary"]
    if not isinstance(summary, Mapping):
        raise EnemyTournamentHwError("snapshot.summary must be an object")
    _exact_keys(
        summary,
        {
            "selector_count",
            "candidate_count",
            "selected_count",
            "queue_count",
            "pair_count",
            "thread_count",
            "stage",
            "pending_selection",
        },
        "snapshot.summary",
    )
    expected_summary = {
        "selector_count": 1,
        "candidate_count": len(candidates),
        "selected_count": 1,
        "queue_count": 1,
        "pair_count": 1,
        "thread_count": 1,
        "stage": 3,
        "pending_selection": False,
    }
    if dict(summary) != expected_summary:
        raise EnemyTournamentHwError("snapshot summary differs")

    return {
        "capture_id": capture_id,
        "identity": dict(identity),
        "integrity": integrity,
        "snapshot_sha256": _sha256(snapshot),
        "module_sha256": observed_module_sha256,
        "selector_context": dict(context),
        "candidate_records": candidates,
        "selected": dict(selected),
        "queued": dict(queued),
        "replay": replay,
        "expected_rng_state_after": f"0x{expected_after:08x}",
    }


def correlate_enemy_tournament_snapshot(
    snapshot: Mapping[str, Any],
    outcome: Mapping[str, Any],
    *,
    build_receipt: Mapping[str, Any],
    observed_module_sha256: str,
) -> dict[str, Any]:
    """Bind an exact native tournament replay to the next bridge enemy queue."""
    validated = validate_enemy_tournament_snapshot(
        snapshot,
        build_receipt=build_receipt,
        observed_module_sha256=observed_module_sha256,
    )
    if not isinstance(outcome, Mapping):
        raise EnemyTournamentHwError("bridge outcome must be an object")
    selected = validated["selected"]
    queued = validated["queued"]
    context = validated["selector_context"]
    width = context["board_width"]
    height = context["board_height"]
    queue_origin = _point(
        queued, "origin", "queued", width=width, height=height
    )
    queued_shot = _point(
        queued, "queued_shot", "queued", width=width, height=height
    )
    reasons: list[str] = []
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
    replay = validated["replay"]
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
            "candidate_count": len(validated["candidate_records"]),
            "selected_input_index": replay["selected_input_index"],
            "selected_source": replay["selected_source"],
            "draw_count": replay["draw_count"],
            "rng_state_before": context["selector_rng_state_before"],
            "rng_state_after": context["selector_rng_state_after"],
            "queue_origin": queue_origin,
            "queued_shot": queued_shot,
            "current_weapon_raw": selected["current_weapon_raw"],
            "base_current_weapon_before_queue_raw": selected[
                "base_current_weapon_raw"
            ],
            "base_current_weapon_at_queue_raw": queued[
                "base_current_weapon_raw"
            ],
        },
        "replay": replay,
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
            "native_replay_exact": True,
            "selected_queue_binding_exact": True,
            "bridge_queue_matches": not any(
                reason.startswith("bridge_") for reason in unique_reasons
            ),
            "correlated": not unique_reasons,
        },
    }
