"""Validate build-keyed selector-entry Board/RNG capsule observations."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any

from src.observatory.msvc_rng_replay import (
    advance_state,
    result_from_advanced_state,
)


SCHEMA_VERSION = 1
SNAPSHOT_KIND = "native_spawn_coordinate_capsule_hw_observer_snapshot"
ANALYSIS_KIND = "spawn_coordinate_capsule_hw_validation"
OBSERVER_VERSION = "observatory-spawn-coordinate-capsule-hw-observer/2"
EXPECTED_PLAN_SHA256 = (
    "e79fb1f734f06dee9862b15f29e0bbccfa82e34b3fe2506565ab56ad45d39ca1"
)
EXPECTED_SOURCE_SHA256 = (
    "de4d7e79fe830611e640a05a2cfd7e81de322cf76a0308c1fb0612bb03b8fdf0"
)
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_INVENTORY_SHA256 = (
    "81fc5d328603c087154c00c8249e9f2e208539b24b7989bd9d805403192aa2b4"
)
EXPECTED_BOUNDARY_MAP_SHA256 = (
    "ded91fdf8181b2ae310644ece211f77fecc4393c3cd1c43867cfd353af3d6dc2"
)
EXPECTED_RNG_RETURN_MAP_SHA256 = (
    "7da4ababb6aa91d7b834e68ea6d42a8a40b6ae379531f42cbbc96556cdcaae48"
)
EXPECTED_SPAWN_BOUNDARY_SHA256 = (
    "9f6785d16f6c1102a7fd6e52d656b1438a12b1a3f216cbb99e5cadd269f53b3f"
)
EXPECTED_POSITION_BOUNDARY_SHA256 = (
    "f7871672fac450ff60196638bb35e28fb865f11844ce2cab76e9ba8bcafc8329"
)
EXPECTED_SELECTOR_REGION_SHA256 = (
    "9746df5a768534c54108600528bce8e0fd152d41e322bf0907dc92a434148904"
)
EXPECTED_SELECTOR_ENTRY_PREBYTES_SHA256 = (
    "19bad2162e08fd3b256f0af4024c51343feb7827eb43fd73dcfea11a662668d8"
)
EXPECTED_SCHEDULER_PREBYTES_SHA256 = (
    "419b08b2e5f923a50b9c561f72289c66c4582a38f35816d8727787cdae8f9ea7"
)
EXPECTED_FALLBACK_PREBYTES_SHA256 = (
    "fd2f466614b6c81c7e73fcdb8b000dd72200a8143400bd9528bedc1d69ffd4e6"
)
EXPECTED_STANDARD_PREBYTES_SHA256 = (
    "c582fb84bc51ea60cbda9c2b62bbd3a9ef4103d42654486a3569da5f8997f011"
)
EXPECTED_RNG_OWNER_SHA256 = (
    "db0c599f49594fdb9856180cf4337d3b95a0bdd7b1d227c662e25caf2a76a12f"
)
EXPECTED_BASE_SOURCE_SHA256 = (
    "00e468dbafaf2da583b10b29593f672e9977c18e1cd81f31a267df83c21403a5"
)
EXPECTED_BASE_PLAN_SHA256 = (
    "6c22aa5cb62552afd7f08d9e942a82cbceb620aab3b1853f004c98534ea74e09"
)

EVENT_KINDS = {
    "scheduler_draw",
    "selector_fallback_draw",
    "selector_standard_draw",
}
SELECTOR_KINDS = {"selector_fallback_draw", "selector_standard_draw"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_U32_RE = re.compile(r"^0x[0-9a-f]{8}$")
_CAPTURE_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
_SIGNED_MIN = -(1 << 31)
_SIGNED_MAX = (1 << 31) - 1


class SpawnCoordinateCapsuleHwError(RuntimeError):
    """Raised when selector-entry capsule evidence fails closed validation."""


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise SpawnCoordinateCapsuleHwError(
            f"{label} fields differ from the contract"
        )


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
        raise SpawnCoordinateCapsuleHwError(f"{label} is invalid")
    return value


def _signed(value: object, label: str) -> int:
    return _integer(value, label, minimum=_SIGNED_MIN, maximum=_SIGNED_MAX)


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise SpawnCoordinateCapsuleHwError(f"{label} is invalid")
    return value


def _u32(value: object, label: str) -> int:
    if type(value) is not str or _U32_RE.fullmatch(value) is None:
        raise SpawnCoordinateCapsuleHwError(f"{label} is not a canonical u32")
    return int(value, 16)


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


def _point(value: object, label: str) -> list[int]:
    if not isinstance(value, Mapping):
        raise SpawnCoordinateCapsuleHwError(f"{label} must be an object")
    _exact_keys(value, {"x", "y"}, label)
    return [
        _integer(value["x"], f"{label}.x", minimum=0, maximum=7),
        _integer(value["y"], f"{label}.y", minimum=0, maximum=7),
    ]


def _point_vector(value: object, label: str) -> list[list[int]]:
    if not isinstance(value, list) or len(value) > 64:
        raise SpawnCoordinateCapsuleHwError(f"{label} is invalid")
    points = [_point(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if len({tuple(point) for point in points}) != len(points):
        raise SpawnCoordinateCapsuleHwError(f"{label} contains duplicate points")
    return points


def _validate_receipt(
    receipt: Mapping[str, Any], observed_module_sha256: str
) -> dict[str, Any]:
    if (
        not isinstance(receipt, Mapping)
        or receipt.get("schema_version") != 1
        or receipt.get("kind")
        != "observatory_spawn_coordinate_capsule_hw_observer_build"
    ):
        raise SpawnCoordinateCapsuleHwError("capsule build receipt is invalid")
    if (
        type(observed_module_sha256) is not str
        or _SHA256_RE.fullmatch(observed_module_sha256) is None
    ):
        raise SpawnCoordinateCapsuleHwError("observed module SHA-256 is invalid")
    required = {
        "observer_version": OBSERVER_VERSION,
        "build_id": "13725832",
        "architecture": "x86",
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        "executable_size": 5_530_112,
        "module_sha256": observed_module_sha256,
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "hardware_breakpoint_plan_sha256": EXPECTED_PLAN_SHA256,
        "base_source_sha256": EXPECTED_BASE_SOURCE_SHA256,
        "base_hardware_breakpoint_plan_sha256": EXPECTED_BASE_PLAN_SHA256,
        "inventory_canonical_sha256": EXPECTED_INVENTORY_SHA256,
        "boundary_map_canonical_sha256": EXPECTED_BOUNDARY_MAP_SHA256,
        "rng_return_map_sha256": EXPECTED_RNG_RETURN_MAP_SHA256,
        "spawn_candidate_boundary_sha256": EXPECTED_SPAWN_BOUNDARY_SHA256,
        "position_observations_boundary_sha256": EXPECTED_POSITION_BOUNDARY_SHA256,
        "selector_region_sha256": EXPECTED_SELECTOR_REGION_SHA256,
        "selector_entry_prebytes_sha256": EXPECTED_SELECTOR_ENTRY_PREBYTES_SHA256,
        "scheduler_prebytes_sha256": EXPECTED_SCHEDULER_PREBYTES_SHA256,
        "selector_fallback_prebytes_sha256": EXPECTED_FALLBACK_PREBYTES_SHA256,
        "selector_standard_prebytes_sha256": EXPECTED_STANDARD_PREBYTES_SHA256,
        "rng_state_owner_sha256": EXPECTED_RNG_OWNER_SHA256,
    }
    for field, expected in required.items():
        if receipt.get(field) != expected:
            raise SpawnCoordinateCapsuleHwError(
                f"capsule build receipt {field} differs"
            )
    if receipt.get("module_filename") != (
        "itb_observatory_spawn_coordinate_capsule_hw_observer_"
        f"{observed_module_sha256}.dll"
    ):
        raise SpawnCoordinateCapsuleHwError(
            "capsule build receipt module filename differs"
        )
    reproducibility = receipt.get("reproducibility")
    source = receipt.get("source_attestation")
    machine = receipt.get("machine_attestation")
    veh = machine.get("veh") if isinstance(machine, Mapping) else None
    compile_flags = receipt.get("compile_flags")
    if (
        receipt.get("loaded_or_armed") is not False
        or receipt.get("executable_bytes_modified") is not False
        or not isinstance(reproducibility, Mapping)
        or reproducibility.get("independent_build_count") != 2
        or reproducibility.get("module_bytes_identical") is not True
        or reproducibility.get("attestations_identical") is not True
        or not isinstance(source, Mapping)
        or source.get("v1_source_unchanged") is not True
        or source.get("executable_mutation_api_text_absent") is not True
        or source.get("private_debug_register_transition_present") is not True
        or source.get("fixed_capsule_ring_present") is not True
        or source.get("pointer_values_published") is not False
        or not isinstance(machine, Mapping)
        or machine.get("loader_entry_absent") is not True
        or machine.get("executable_mutation_api_imports_absent") is not True
        or not isinstance(veh, Mapping)
        or veh.get("direct_or_indirect_call_count") != 0
        or veh.get("windows_api_call_count") != 0
        or veh.get("x87_mmx_sse_avx_instruction_count") != 0
        or veh.get("leading_int3_padding_size") != 0
        or not isinstance(compile_flags, list)
        or "/arch:IA32" not in compile_flags
        or "/Qvec-" not in compile_flags
    ):
        raise SpawnCoordinateCapsuleHwError(
            "capsule build safety attestation failed"
        )
    return required


def _validate_integrity(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SpawnCoordinateCapsuleHwError("snapshot.integrity must be an object")
    error_fields = {
        "overflow_count",
        "candidate_error_count",
        "capsule_error_count",
        "rng_error_count",
        "pairing_error_count",
        "pointer_fault_count",
        "transition_mismatch_count",
        "wrong_thread_count",
        "unexpected_breakpoint_count",
        "torn_record_count",
        "torn_capsule_count",
    }
    _exact_keys(
        value,
        error_fields
        | {
            "state",
            "complete",
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
    for field in error_fields:
        if _integer(value[field], f"snapshot.integrity.{field}", minimum=0) != 0:
            raise SpawnCoordinateCapsuleHwError(f"snapshot reports {field}")
    if (
        value["state"] != "restored"
        or _boolean(value["complete"], "snapshot.integrity.complete") is not True
        or _boolean(
            value["debug_registers_armed"],
            "snapshot.integrity.debug_registers_armed",
        )
        is not False
        or _boolean(
            value["debug_registers_cleared"],
            "snapshot.integrity.debug_registers_cleared",
        )
        is not True
        or _boolean(value["veh_installed"], "snapshot.integrity.veh_installed")
        is not False
        or _boolean(value["veh_removed"], "snapshot.integrity.veh_removed")
        is not True
        or _boolean(
            value["executable_file_released"],
            "snapshot.integrity.executable_file_released",
        )
        is not True
        or _boolean(
            value["executable_bytes_modified"],
            "snapshot.integrity.executable_bytes_modified",
        )
        is not False
        or _boolean(
            value["seam_bytes_unchanged"],
            "snapshot.integrity.seam_bytes_unchanged",
        )
        is not True
        or _boolean(
            value["addresses_or_pointers_published"],
            "snapshot.integrity.addresses_or_pointers_published",
        )
        is not False
    ):
        raise SpawnCoordinateCapsuleHwError(
            "capsule observer was not fully restored"
        )
    return dict(value)


def _validate_draws(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 256:
        raise SpawnCoordinateCapsuleHwError("draw_records count is invalid")
    expected = {
        "kind",
        "seq",
        "candidate_count",
        "selected_index",
        "rng_quotient",
        "raw_rng",
        "selected_x",
        "selected_y",
        "candidates",
    }
    records: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        label = f"draw_records[{index}]"
        if not isinstance(raw, Mapping):
            raise SpawnCoordinateCapsuleHwError(f"{label} must be an object")
        _exact_keys(raw, expected, label)
        kind = raw["kind"]
        if kind not in EVENT_KINDS or raw["seq"] != index:
            raise SpawnCoordinateCapsuleHwError(f"{label} header differs")
        count = _integer(
            raw["candidate_count"],
            f"{label}.candidate_count",
            minimum=1,
            maximum=64,
        )
        selected_index = _integer(
            raw["selected_index"],
            f"{label}.selected_index",
            minimum=0,
            maximum=count - 1,
        )
        quotient = _integer(
            raw["rng_quotient"], f"{label}.rng_quotient", minimum=0,
            maximum=32767,
        )
        raw_rng = _integer(
            raw["raw_rng"], f"{label}.raw_rng", minimum=0, maximum=32767
        )
        candidates_raw = raw["candidates"]
        if not isinstance(candidates_raw, list) or len(candidates_raw) != count:
            raise SpawnCoordinateCapsuleHwError(
                f"{label}.candidates length differs"
            )
        candidates = [
            _point(candidate, f"{label}.candidates[{candidate_index}]")
            for candidate_index, candidate in enumerate(candidates_raw)
        ]
        selected = [
            _integer(raw["selected_x"], f"{label}.selected_x", minimum=0, maximum=7),
            _integer(raw["selected_y"], f"{label}.selected_y", minimum=0, maximum=7),
        ]
        if raw_rng != quotient * count + selected_index:
            raise SpawnCoordinateCapsuleHwError(
                f"{label} RNG reconstruction differs"
            )
        if selected != candidates[selected_index]:
            raise SpawnCoordinateCapsuleHwError(
                f"{label} selected point differs"
            )
        records.append(
            {
                "kind": kind,
                "seq": index,
                "candidate_count": count,
                "selected_index": selected_index,
                "rng_quotient": quotient,
                "raw_rng": raw_rng,
                "selected": selected,
                "candidates": candidates,
            }
        )
    return records


def _validate_block_spawn(value: object, label: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 64:
        raise SpawnCoordinateCapsuleHwError(f"{label} must cover all 64 tiles")
    values: list[int] = []
    for index, raw in enumerate(value):
        item_label = f"{label}[{index}]"
        if not isinstance(raw, Mapping):
            raise SpawnCoordinateCapsuleHwError(f"{item_label} is invalid")
        _exact_keys(raw, {"x", "y", "value"}, item_label)
        if raw["x"] != index // 8 or raw["y"] != index % 8:
            raise SpawnCoordinateCapsuleHwError(
                f"{label} is not complete x-major order"
            )
        values.append(_signed(raw["value"], f"{item_label}.value"))
    return values


def _validate_tiles(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != 64:
        raise SpawnCoordinateCapsuleHwError(f"{label} must cover all 64 tiles")
    fields = {
        "x",
        "y",
        "terrain",
        "pod_state",
        "item_present",
        "acid",
        "dangerous_flag",
        "occupancy_count",
        "occupant_ids",
    }
    tiles: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        item_label = f"{label}[{index}]"
        if not isinstance(raw, Mapping):
            raise SpawnCoordinateCapsuleHwError(f"{item_label} is invalid")
        _exact_keys(raw, fields, item_label)
        point = [index // 8, index % 8]
        if raw["x"] != point[0] or raw["y"] != point[1]:
            raise SpawnCoordinateCapsuleHwError(
                f"{label} is not complete x-major order"
            )
        count = _integer(
            raw["occupancy_count"],
            f"{item_label}.occupancy_count",
            minimum=0,
            maximum=8,
        )
        occupant_ids = raw["occupant_ids"]
        if not isinstance(occupant_ids, list) or len(occupant_ids) != count:
            raise SpawnCoordinateCapsuleHwError(
                f"{item_label}.occupant_ids length differs"
            )
        tiles.append(
            {
                "point": point,
                "terrain": _signed(raw["terrain"], f"{item_label}.terrain"),
                "pod_state": _signed(raw["pod_state"], f"{item_label}.pod_state"),
                "item_present": _boolean(
                    raw["item_present"], f"{item_label}.item_present"
                ),
                "acid": _boolean(raw["acid"], f"{item_label}.acid"),
                "dangerous_flag": _boolean(
                    raw["dangerous_flag"], f"{item_label}.dangerous_flag"
                ),
                "occupant_ids": [
                    _signed(pawn_id, f"{item_label}.occupant_ids[{pawn_index}]")
                    for pawn_index, pawn_id in enumerate(occupant_ids)
                ],
            }
        )
    return tiles


def validate_spawn_coordinate_capsule_snapshot(
    snapshot: Mapping[str, Any],
    *,
    build_receipt: Mapping[str, Any],
    observed_module_sha256: str,
) -> dict[str, Any]:
    """Validate one restored selector-entry capsule stream and exact RNG pairing."""
    if not isinstance(snapshot, Mapping):
        raise SpawnCoordinateCapsuleHwError("capsule snapshot must be an object")
    _exact_keys(
        snapshot,
        {
            "schema_version",
            "kind",
            "observer_version",
            "capture_id",
            "identity",
            "integrity",
            "draw_records",
            "capsules",
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
        raise SpawnCoordinateCapsuleHwError("capsule snapshot header is invalid")
    expected = _validate_receipt(build_receipt, observed_module_sha256)

    identity = snapshot["identity"]
    if not isinstance(identity, Mapping):
        raise SpawnCoordinateCapsuleHwError("snapshot.identity must be an object")
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
            "spawn_candidate_boundary_sha256",
            "position_observations_boundary_sha256",
            "hardware_breakpoint_plan_sha256",
            "selector_region_sha256",
            "selector_entry_prebytes_sha256",
            "scheduler_prebytes_sha256",
            "selector_fallback_prebytes_sha256",
            "selector_standard_prebytes_sha256",
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
        "inventory_sha256": expected["inventory_canonical_sha256"],
        "boundary_map_sha256": expected["boundary_map_canonical_sha256"],
        "spawn_candidate_boundary_sha256": expected[
            "spawn_candidate_boundary_sha256"
        ],
        "position_observations_boundary_sha256": expected[
            "position_observations_boundary_sha256"
        ],
        "hardware_breakpoint_plan_sha256": expected[
            "hardware_breakpoint_plan_sha256"
        ],
        "selector_region_sha256": expected["selector_region_sha256"],
        "selector_entry_prebytes_sha256": expected[
            "selector_entry_prebytes_sha256"
        ],
        "scheduler_prebytes_sha256": expected["scheduler_prebytes_sha256"],
        "selector_fallback_prebytes_sha256": expected[
            "selector_fallback_prebytes_sha256"
        ],
        "selector_standard_prebytes_sha256": expected[
            "selector_standard_prebytes_sha256"
        ],
        "rng_state_owner_sha256": expected["rng_state_owner_sha256"],
    }
    if dict(identity) != identity_expected:
        raise SpawnCoordinateCapsuleHwError(
            "capsule snapshot identity differs from build receipt"
        )

    integrity = _validate_integrity(snapshot["integrity"])
    draws = _validate_draws(snapshot["draw_records"])
    capsules_raw = snapshot["capsules"]
    if not isinstance(capsules_raw, list) or not 1 <= len(capsules_raw) <= 64:
        raise SpawnCoordinateCapsuleHwError("capsules count is invalid")

    selector_draw_indexes = [
        index for index, draw in enumerate(draws) if draw["kind"] in SELECTOR_KINDS
    ]
    capsule_fields = {
        "seq",
        "draw_seq",
        "selector_kind",
        "board_width",
        "board_height",
        "board_turn",
        "pawn_id",
        "pawn_team",
        "rng_state_before",
        "rng_state_after",
        "raw_rng",
        "selected_index",
        "selected_x",
        "selected_y",
        "block_spawn_values",
        "spawn_markers",
        "dangerous_points_a",
        "dangerous_points_b",
        "tiles",
    }
    capsules: list[dict[str, Any]] = []
    paired_draws: list[int] = []
    for index, raw in enumerate(capsules_raw):
        label = f"capsules[{index}]"
        if not isinstance(raw, Mapping):
            raise SpawnCoordinateCapsuleHwError(f"{label} must be an object")
        _exact_keys(raw, capsule_fields, label)
        if raw["seq"] != index or raw["selector_kind"] not in SELECTOR_KINDS:
            raise SpawnCoordinateCapsuleHwError(f"{label} header differs")
        draw_seq = _integer(
            raw["draw_seq"], f"{label}.draw_seq", minimum=0,
            maximum=len(draws) - 1,
        )
        draw = draws[draw_seq]
        if draw["kind"] != raw["selector_kind"]:
            raise SpawnCoordinateCapsuleHwError(f"{label} selector pairing differs")
        state_before = _u32(raw["rng_state_before"], f"{label}.rng_state_before")
        state_after = _u32(raw["rng_state_after"], f"{label}.rng_state_after")
        if advance_state(state_before) != state_after:
            raise SpawnCoordinateCapsuleHwError(f"{label} RNG transition differs")
        raw_rng = _integer(
            raw["raw_rng"], f"{label}.raw_rng", minimum=0, maximum=32767
        )
        selected_index = _integer(
            raw["selected_index"],
            f"{label}.selected_index",
            minimum=0,
            maximum=draw["candidate_count"] - 1,
        )
        selected = [
            _integer(raw["selected_x"], f"{label}.selected_x", minimum=0, maximum=7),
            _integer(raw["selected_y"], f"{label}.selected_y", minimum=0, maximum=7),
        ]
        if (
            result_from_advanced_state(state_after) != raw_rng
            or raw_rng != draw["raw_rng"]
            or selected_index != draw["selected_index"]
            or selected != draw["selected"]
        ):
            raise SpawnCoordinateCapsuleHwError(f"{label} draw replay differs")
        width = _integer(raw["board_width"], f"{label}.board_width")
        height = _integer(raw["board_height"], f"{label}.board_height")
        if width != 8 or height != 8:
            raise SpawnCoordinateCapsuleHwError(f"{label} board dimensions differ")
        block_spawn = _validate_block_spawn(
            raw["block_spawn_values"], f"{label}.block_spawn_values"
        )
        spawn_markers = _point_vector(raw["spawn_markers"], f"{label}.spawn_markers")
        dangerous_a = _point_vector(
            raw["dangerous_points_a"], f"{label}.dangerous_points_a"
        )
        dangerous_b = _point_vector(
            raw["dangerous_points_b"], f"{label}.dangerous_points_b"
        )
        tiles = _validate_tiles(raw["tiles"], f"{label}.tiles")
        dangerous = sorted(
            {
                tuple(tile["point"])
                for tile in tiles
                if tile["dangerous_flag"]
            }
            | {tuple(point) for point in dangerous_a}
            | {tuple(point) for point in dangerous_b}
        )
        occupied = [tile["point"] for tile in tiles if tile["occupant_ids"]]
        paired_draws.append(draw_seq)
        capsules.append(
            {
                "seq": index,
                "draw_seq": draw_seq,
                "selector_kind": draw["kind"],
                "board": {
                    "width": width,
                    "height": height,
                    "turn": _integer(
                        raw["board_turn"], f"{label}.board_turn", minimum=0,
                        maximum=20,
                    ),
                    "pawn_id": _signed(raw["pawn_id"], f"{label}.pawn_id"),
                    "pawn_team": _integer(
                        raw["pawn_team"], f"{label}.pawn_team", minimum=0,
                        maximum=8,
                    ),
                    "block_spawn_values": block_spawn,
                    "spawn_markers": spawn_markers,
                    "dangerous_points_a": dangerous_a,
                    "dangerous_points_b": dangerous_b,
                    "dangerous_points": [list(point) for point in dangerous],
                    "occupied_points": occupied,
                    "tiles": tiles,
                },
                "rng": {
                    "state_before": raw["rng_state_before"],
                    "state_after": raw["rng_state_after"],
                    "raw_rng": raw_rng,
                },
                "selected_index": selected_index,
                "selected": selected,
                "candidates": draw["candidates"],
            }
        )
    if paired_draws != selector_draw_indexes:
        raise SpawnCoordinateCapsuleHwError(
            "capsules do not pair one-to-one with selector draws"
        )

    summary = snapshot["summary"]
    if not isinstance(summary, Mapping):
        raise SpawnCoordinateCapsuleHwError("snapshot.summary must be an object")
    _exact_keys(
        summary,
        {
            "draw_record_count",
            "scheduler_count",
            "selector_fallback_count",
            "selector_standard_count",
            "selector_count",
            "capsule_entry_count",
            "capsule_count",
            "thread_count",
            "last_draw_sequence",
            "last_capsule_sequence",
        },
        "snapshot.summary",
    )
    counts = Counter(draw["kind"] for draw in draws)
    expected_summary = {
        "draw_record_count": len(draws),
        "scheduler_count": counts["scheduler_draw"],
        "selector_fallback_count": counts["selector_fallback_draw"],
        "selector_standard_count": counts["selector_standard_draw"],
        "selector_count": len(selector_draw_indexes),
        "capsule_entry_count": len(capsules),
        "capsule_count": len(capsules),
        "thread_count": 1,
        "last_draw_sequence": len(draws) - 1,
        "last_capsule_sequence": len(capsules) - 1,
    }
    if dict(summary) != expected_summary:
        raise SpawnCoordinateCapsuleHwError("capsule snapshot summary differs")

    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": ANALYSIS_KIND,
        "capture_id": capture_id,
        "identity": dict(identity),
        "integrity": integrity,
        "draw_records": draws,
        "capsules": capsules,
        "claims": {
            "selector_entry_board_carriers_captured": True,
            "shared_rng_state_exact": True,
            "candidate_vector_pairing_exact": True,
            "transient_dead_noncorpse_occupancy_resolved": False,
            "pawn_path_profile_at_entry_resolved": False,
            "complete_future_forecast": False,
        },
    }
    result["evidence_sha256"] = _sha256(result)
    return result
