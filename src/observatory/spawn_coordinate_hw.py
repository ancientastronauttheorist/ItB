"""Validate and correlate build-keyed native spawn-coordinate observations."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from typing import Any


SCHEMA_VERSION = 1
SNAPSHOT_KIND = "native_spawn_coordinate_hw_observer_snapshot"
ANALYSIS_KIND = "spawn_coordinate_hw_correlation"
OBSERVER_VERSION = "observatory-spawn-coordinate-hw-observer/1"
EXPECTED_PLAN_SHA256 = (
    "6c22aa5cb62552afd7f08d9e942a82cbceb620aab3b1853f004c98534ea74e09"
)
EVENT_KINDS = {
    "scheduler_draw",
    "selector_fallback_draw",
    "selector_standard_draw",
}
SELECTOR_KINDS = {"selector_fallback_draw", "selector_standard_draw"}


class SpawnCoordinateHwError(RuntimeError):
    """Raised when spawn-coordinate evidence is malformed or unresolved."""


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise SpawnCoordinateHwError(f"{label} fields differ from the contract")


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
        raise SpawnCoordinateHwError(f"{label} is invalid")
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


def _point(value: object, label: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        raise SpawnCoordinateHwError(f"{label} is not a point")
    x = _integer(value[0], f"{label}[0]", minimum=0, maximum=7)
    y = _integer(value[1], f"{label}[1]", minimum=0, maximum=7)
    return [x, y]


def _validate_receipt(
    receipt: Mapping[str, Any], observed_module_sha256: str
) -> dict[str, Any]:
    if receipt.get("schema_version") != 1 or receipt.get("kind") != (
        "observatory_spawn_coordinate_hw_observer_build"
    ):
        raise SpawnCoordinateHwError("spawn-coordinate build receipt is invalid")
    required = {
        "observer_version": OBSERVER_VERSION,
        "build_id": "13725832",
        "architecture": "x86",
        "executable_sha256": (
            "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
        ),
        "module_sha256": observed_module_sha256,
        "hardware_breakpoint_plan_sha256": EXPECTED_PLAN_SHA256,
        "boundary_map_canonical_sha256": (
            "ded91fdf8181b2ae310644ece211f77fecc4393c3cd1c43867cfd353af3d6dc2"
        ),
        "selector_region_sha256": (
            "9746df5a768534c54108600528bce8e0fd152d41e322bf0907dc92a434148904"
        ),
        "scheduler_region_sha256": (
            "639ea27e48757d5c7f08499522d7f8933dc874957f4d00a74bbeec4a6750bd89"
        ),
        "scheduler_prebytes_sha256": (
            "419b08b2e5f923a50b9c561f72289c66c4582a38f35816d8727787cdae8f9ea7"
        ),
        "selector_fallback_prebytes_sha256": (
            "fd2f466614b6c81c7e73fcdb8b000dd72200a8143400bd9528bedc1d69ffd4e6"
        ),
        "selector_standard_prebytes_sha256": (
            "c582fb84bc51ea60cbda9c2b62bbd3a9ef4103d42654486a3569da5f8997f011"
        ),
    }
    for field, expected in required.items():
        if receipt.get(field) != expected:
            raise SpawnCoordinateHwError(
                f"spawn-coordinate build receipt {field} differs"
            )
    reproducibility = receipt.get("reproducibility")
    machine = receipt.get("machine_attestation")
    veh = machine.get("veh") if isinstance(machine, Mapping) else None
    if (
        receipt.get("loaded_or_armed") is not False
        or not isinstance(reproducibility, Mapping)
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
        raise SpawnCoordinateHwError(
            "spawn-coordinate build safety attestation failed"
        )
    return required


def validate_spawn_coordinate_snapshot(
    snapshot: Mapping[str, Any],
    *,
    build_receipt: Mapping[str, Any],
    observed_module_sha256: str,
) -> dict[str, Any]:
    """Validate one restored coordinate event stream and its candidate lists."""
    if not isinstance(snapshot, Mapping):
        raise SpawnCoordinateHwError("spawn-coordinate snapshot must be an object")
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
        raise SpawnCoordinateHwError("spawn-coordinate snapshot header is invalid")
    expected = _validate_receipt(build_receipt, observed_module_sha256)

    identity = snapshot["identity"]
    if not isinstance(identity, Mapping):
        raise SpawnCoordinateHwError("snapshot.identity must be an object")
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
            "scheduler_region_sha256",
            "selector_region_sha256",
            "scheduler_prebytes_sha256",
            "selector_fallback_prebytes_sha256",
            "selector_standard_prebytes_sha256",
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
        "scheduler_region_sha256": expected["scheduler_region_sha256"],
        "selector_region_sha256": expected["selector_region_sha256"],
        "scheduler_prebytes_sha256": expected["scheduler_prebytes_sha256"],
        "selector_fallback_prebytes_sha256": expected[
            "selector_fallback_prebytes_sha256"
        ],
        "selector_standard_prebytes_sha256": expected[
            "selector_standard_prebytes_sha256"
        ],
    }
    if dict(identity) != identity_expected:
        raise SpawnCoordinateHwError("snapshot identity differs from build receipt")

    integrity = snapshot["integrity"]
    if not isinstance(integrity, Mapping):
        raise SpawnCoordinateHwError("snapshot.integrity must be an object")
    _exact_keys(
        integrity,
        {
            "state",
            "complete",
            "overflow_count",
            "candidate_error_count",
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
        "candidate_error_count",
        "pointer_fault_count",
        "transition_mismatch_count",
        "wrong_thread_count",
        "unexpected_breakpoint_count",
        "torn_record_count",
    ):
        if _integer(integrity[field], f"snapshot.integrity.{field}", minimum=0):
            raise SpawnCoordinateHwError(f"snapshot reports {field}")
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
        raise SpawnCoordinateHwError(
            "spawn-coordinate observer was not fully restored"
        )

    summary = snapshot["summary"]
    records = snapshot["records"]
    if not isinstance(summary, Mapping) or not isinstance(records, list):
        raise SpawnCoordinateHwError("snapshot records or summary is invalid")
    _exact_keys(
        summary,
        {
            "record_count",
            "scheduler_count",
            "selector_fallback_count",
            "selector_standard_count",
            "selector_count",
            "thread_count",
            "last_sequence",
        },
        "snapshot.summary",
    )
    record_count = _integer(
        summary["record_count"], "snapshot.summary.record_count", minimum=1,
        maximum=256,
    )
    scheduler_count = _integer(
        summary["scheduler_count"], "snapshot.summary.scheduler_count", minimum=0
    )
    fallback_count = _integer(
        summary["selector_fallback_count"],
        "snapshot.summary.selector_fallback_count",
        minimum=0,
    )
    standard_count = _integer(
        summary["selector_standard_count"],
        "snapshot.summary.selector_standard_count",
        minimum=0,
    )
    selector_count = _integer(
        summary["selector_count"], "snapshot.summary.selector_count", minimum=1
    )
    if (
        record_count != len(records)
        or record_count != scheduler_count + fallback_count + standard_count
        or selector_count != fallback_count + standard_count
        or summary["thread_count"] != 1
        or summary["last_sequence"] != record_count - 1
    ):
        raise SpawnCoordinateHwError("snapshot summary counts differ")

    counts: Counter[str] = Counter()
    normalized: list[dict[str, Any]] = []
    record_fields = {
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
    for index, raw_record in enumerate(records):
        label = f"snapshot.records[{index}]"
        if not isinstance(raw_record, Mapping):
            raise SpawnCoordinateHwError(f"{label} must be an object")
        _exact_keys(raw_record, record_fields, label)
        kind = raw_record["kind"]
        if kind not in EVENT_KINDS or raw_record["seq"] != index:
            raise SpawnCoordinateHwError(f"{label} header differs")
        candidate_count = _integer(
            raw_record["candidate_count"],
            f"{label}.candidate_count",
            minimum=1,
            maximum=64,
        )
        selected_index = _integer(
            raw_record["selected_index"],
            f"{label}.selected_index",
            minimum=0,
            maximum=candidate_count - 1,
        )
        quotient = _integer(
            raw_record["rng_quotient"],
            f"{label}.rng_quotient",
            minimum=0,
            maximum=32767,
        )
        raw_rng = _integer(
            raw_record["raw_rng"], f"{label}.raw_rng", minimum=0,
            maximum=32767,
        )
        candidates = raw_record["candidates"]
        if not isinstance(candidates, list) or len(candidates) != candidate_count:
            raise SpawnCoordinateHwError(f"{label}.candidates length differs")
        points: list[list[int]] = []
        for candidate_index, candidate in enumerate(candidates):
            if not isinstance(candidate, Mapping):
                raise SpawnCoordinateHwError(
                    f"{label}.candidates[{candidate_index}] must be an object"
                )
            _exact_keys(candidate, {"x", "y"}, f"{label}.candidates[{candidate_index}]")
            points.append(
                _point(
                    [candidate["x"], candidate["y"]],
                    f"{label}.candidates[{candidate_index}]",
                )
            )
        selected = _point(
            [raw_record["selected_x"], raw_record["selected_y"]],
            f"{label}.selected",
        )
        if raw_rng != quotient * candidate_count + selected_index:
            raise SpawnCoordinateHwError(f"{label} RNG reconstruction differs")
        if selected != points[selected_index]:
            raise SpawnCoordinateHwError(f"{label} selected point differs")
        counts[kind] += 1
        normalized.append(
            {
                "kind": kind,
                "seq": index,
                "candidate_count": candidate_count,
                "selected_index": selected_index,
                "rng_quotient": quotient,
                "raw_rng": raw_rng,
                "selected": selected,
                "candidates": points,
            }
        )
    if (
        counts["scheduler_draw"] != scheduler_count
        or counts["selector_fallback_draw"] != fallback_count
        or counts["selector_standard_draw"] != standard_count
    ):
        raise SpawnCoordinateHwError("snapshot record kinds differ from summary")
    return {
        "capture_id": snapshot["capture_id"],
        "identity": dict(identity),
        "snapshot_sha256": _sha256(snapshot),
        "module_sha256": observed_module_sha256,
        "records": normalized,
        "summary": dict(summary),
    }


def correlate_spawn_coordinate_snapshot(
    snapshot: Mapping[str, Any],
    outcome: Mapping[str, Any],
    *,
    build_receipt: Mapping[str, Any],
    observed_module_sha256: str,
) -> dict[str, Any]:
    """Correlate final selector results with bridge-reported spawn markers."""
    validated = validate_spawn_coordinate_snapshot(
        snapshot,
        build_receipt=build_receipt,
        observed_module_sha256=observed_module_sha256,
    )
    if not isinstance(outcome, Mapping):
        raise SpawnCoordinateHwError("bridge outcome must be an object")
    reasons: list[str] = []
    if outcome.get("mission_id") != "Mission_Power":
        reasons.append("bridge_mission_mismatch")
    if outcome.get("phase") != "combat_player":
        reasons.append("bridge_phase_mismatch")
    raw_spawning = outcome.get("spawning_tiles")
    if not isinstance(raw_spawning, list):
        reasons.append("bridge_spawning_tiles_missing")
        spawning: list[list[int]] = []
    else:
        try:
            spawning = [_point(point, f"outcome.spawning_tiles[{i}]") for i, point in enumerate(raw_spawning)]
        except SpawnCoordinateHwError:
            reasons.append("bridge_spawning_tiles_invalid")
            spawning = []
    selectors = [
        record
        for record in validated["records"]
        if record["kind"] in SELECTOR_KINDS
    ]
    selected_points = [record["selected"] for record in selectors]
    if Counter(map(tuple, selected_points)) != Counter(map(tuple, spawning)):
        reasons.append("selector_spawn_marker_mismatch")
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
        "events": validated["records"],
        "native": {
            "scheduler_draw_count": validated["summary"]["scheduler_count"],
            "selector_draw_count": validated["summary"]["selector_count"],
            "selector_fallback_count": validated["summary"][
                "selector_fallback_count"
            ],
            "selector_standard_count": validated["summary"][
                "selector_standard_count"
            ],
            "selected_spawn_coordinates": selected_points,
            "raw_rng_sequence": [
                record["raw_rng"] for record in validated["records"]
            ],
        },
        "bridge": {"spawning_tiles": spawning},
        "summary": {
            "candidate_order_captured": True,
            "rng_reconstruction_exact": True,
            "selector_matches_spawn_markers": not any(
                reason.startswith("selector_spawn_marker")
                for reason in unique_reasons
            ),
            "correlated": not unique_reasons,
        },
    }
