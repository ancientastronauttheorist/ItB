"""Reproduce the reviewed native spawn-coordinate control-flow map.

The runtime coordinate observer deliberately named three seams without
claiming that all three were naturally reachable.  This module pins the exact
Windows executable and records what focused offline review can establish:

* caller 60 is the ordinary final coordinate selector;
* caller 59 is the logged emergency-placement selector; and
* caller 66 samples a supplied point vector without replacement before the
  scheduler may call the ordinary selector.  It does not return the sampled
  point as the final spawn coordinate.

The opaque virtual predicates and runtime reachability remain outside the
static claim.  Every published byte window, call edge, string, and caller ID is
rechecked against the executable and the original immutable RNG return map.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)
from src.observatory.rng_return_map import encode_rng_return_map


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_spawn_coordinate_path_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_RETURN_MAP_SHA256 = (
    "7da4ababb6aa91d7b834e68ea6d42a8a40b6ae379531f42cbbc96556cdcaae48"
)
RNG_CORE_RVA = 0x00387F16
SELECTOR_RVA = 0x00172A90
SCHEDULER_RVA = 0x001750F0


class SpawnCoordinatePathError(RuntimeError):
    """Raised when the exact native path map cannot be reproduced."""


REGION_SPECS = (
    {
        "id": "spawn_coordinate_selector",
        "start": SELECTOR_RVA,
        "end": 0x00172EF6,
        "sha256": (
            "9746df5a768534c54108600528bce8e0fd152d41e322bf0907dc92a434148904"
        ),
        "boundary_basis": (
            "Reviewed contiguous function extent through its RET; the next "
            "bytes are alignment padding."
        ),
    },
    {
        "id": "spawn_coordinate_scheduler",
        "start": SCHEDULER_RVA,
        "end": 0x0017526B,
        "sha256": (
            "639ea27e48757d5c7f08499522d7f8933dc874957f4d00a74bbeec4a6750bd89"
        ),
        "boundary_basis": (
            "Reviewed contiguous function extent through its RET and one "
            "following INT3 alignment byte."
        ),
    },
)


STRING_ANCHOR_SPECS = (
    {
        "id": "ordinary_enemy_candidate_class",
        "role_id": "ordinary_candidate_source",
        "reference_rva": 0x00172B06,
        "instruction_hex": "68a0e98200",
        "string_rva": 0x0042E9A0,
        "text": "enemy",
    },
    {
        "id": "emergency_placement_log",
        "role_id": "emergency_fallback",
        "reference_rva": 0x00172C86,
        "instruction_hex": "6898eb8200",
        "string_rva": 0x0042EB98,
        "text": (
            "Cannot spawn enemy in standard locations. Emergency placement "
            "engaged.\n"
        ),
    },
    {
        "id": "placement_failure_log",
        "role_id": "emergency_fallback_failure",
        "reference_rva": 0x00172E44,
        "instruction_hex": "68f4eb8200",
        "string_rva": 0x0042EBF4,
        "text": "Failed to find somewhere to put unit\n",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "ordinary_nonempty_gate",
        "region_id": "spawn_coordinate_selector",
        "start_rva": 0x00172C79,
        "instruction_hex": "3bce0f94c084c00f84dd010000",
        "evidence_class": "fact",
        "meaning": (
            "The final filtered ordinary vector branches directly to the "
            "standard selector when begin and end differ; equality continues "
            "into emergency placement."
        ),
    },
    {
        "id": "emergency_modulo_selection",
        "region_id": "spawn_coordinate_selector",
        "start_rva": 0x00172E05,
        "instruction_hex": (
            "3bfe743b2bf7c1fe0385f6750433d2eb08e8fb50210099f7fe8b75088b04d7"
            "89068b44d704894604"
        ),
        "evidence_class": "fact",
        "meaning": (
            "A nonempty emergency point vector computes its 8-byte element "
            "count, calls the shared RNG core, divides by that count, and "
            "copies the remainder-indexed point to the result."
        ),
    },
    {
        "id": "ordinary_modulo_selection",
        "region_id": "spawn_coordinate_selector",
        "start_rva": 0x00172E63,
        "instruction_hex": (
            "2bf1c1fe0385f6750433d2eb0be8a15021008b4dc899f7fe8b5cd1048b3cd1"
        ),
        "evidence_class": "fact",
        "meaning": (
            "The ordinary point vector computes its 8-byte element count, "
            "calls the shared RNG core, divides by that count, and loads the "
            "remainder-indexed point."
        ),
    },
    {
        "id": "scheduler_modulo_sample",
        "region_id": "spawn_coordinate_scheduler",
        "start_rva": 0x00175191,
        "instruction_hex": (
            "8b550c8bf28b45082bf0c1fe0385f6750433c9eb10e86b2d210099f7fe8b45"
            "088bca8b550c"
        ),
        "evidence_class": "fact",
        "meaning": (
            "The scheduler derives an 8-byte point count and obtains a "
            "remainder index from caller 66."
        ),
    },
    {
        "id": "scheduler_remove_and_repeat",
        "region_id": "spawn_coordinate_scheduler",
        "start_rva": 0x001751B6,
        "instruction_hex": (
            "8b34c88d04c88b58048d48082bd1525150e8b4931f008b450c83c40c83e808"
            "89450c39450875a3"
        ),
        "evidence_class": "fact",
        "meaning": (
            "The sampled point is loaded, the following elements are shifted "
            "over it, the local vector end is reduced by eight bytes, and the "
            "predicate loop repeats while candidates remain."
        ),
    },
    {
        "id": "scheduler_predicate_then_selector",
        "region_id": "spawn_coordinate_scheduler",
        "start_rva": 0x001751DD,
        "instruction_hex": (
            "8b078bcf6a0053568b400cffd084c074188b473c8bcf0345ecff308d45d850e8"
            "8fd8ffff8b308b5804"
        ),
        "evidence_class": "fact",
        "meaning": (
            "After the opaque virtual predicate remains true, the scheduler "
            "calls the separate spawn-coordinate selector; the sampled point "
            "is not copied as that selector's result."
        ),
    },
)


DIRECT_EDGE_SPECS = (
    {
        "id": "emergency_selector_to_rng_core",
        "source_region": "spawn_coordinate_selector",
        "from_rva": 0x00172E16,
        "instruction_hex": "e8fb502100",
        "target_id": "rng_core",
        "target_rva": RNG_CORE_RVA,
    },
    {
        "id": "ordinary_selector_to_rng_core",
        "source_region": "spawn_coordinate_selector",
        "from_rva": 0x00172E70,
        "instruction_hex": "e8a1502100",
        "target_id": "rng_core",
        "target_rva": RNG_CORE_RVA,
    },
    {
        "id": "scheduler_to_rng_core",
        "source_region": "spawn_coordinate_scheduler",
        "from_rva": 0x001751A6,
        "instruction_hex": "e86b2d2100",
        "target_id": "rng_core",
        "target_rva": RNG_CORE_RVA,
    },
    {
        "id": "scheduler_to_coordinate_selector",
        "source_region": "spawn_coordinate_scheduler",
        "from_rva": 0x001751FC,
        "instruction_hex": "e88fd8ffff",
        "target_id": "spawn_coordinate_selector",
        "target_rva": SELECTOR_RVA,
    },
)


DIRECT_CALLSITE_SPECS = (
    ("selector_call_168ed8", 0x00168ED8, "e8b39b0000", SELECTOR_RVA),
    ("selector_call_169457", 0x00169457, "e834960000", SELECTOR_RVA),
    ("selector_call_16e935", 0x0016E935, "e856410000", SELECTOR_RVA),
    ("selector_call_1751fc", 0x001751FC, "e88fd8ffff", SELECTOR_RVA),
    ("scheduler_call_183b5d", 0x00183B5D, "e88e15ffff", SCHEDULER_RVA),
    ("scheduler_call_185526", 0x00185526, "e8c5fbfeff", SCHEDULER_RVA),
    ("scheduler_call_1870ac", 0x001870AC, "e83fe0feff", SCHEDULER_RVA),
)


RNG_CALLER_SPECS = (
    {
        "caller_id": 59,
        "region_id": "spawn_coordinate_selector",
        "role_id": "emergency_coordinate_modulo",
        "domain": "gameplay",
        "meaning": (
            "Selects one point from the emergency-placement vector by exact "
            "raw RNG modulo candidate count."
        ),
    },
    {
        "caller_id": 60,
        "region_id": "spawn_coordinate_selector",
        "role_id": "ordinary_coordinate_modulo",
        "domain": "gameplay",
        "meaning": (
            "Selects one point from the final ordinary spawn vector by exact "
            "raw RNG modulo candidate count."
        ),
    },
    {
        "caller_id": 66,
        "region_id": "spawn_coordinate_scheduler",
        "role_id": "scheduler_predicate_order",
        "domain": "gameplay",
        "meaning": (
            "Chooses the next supplied point to test, removes it from the "
            "local vector, and repeats; it does not choose the final spawn "
            "coordinate."
        ),
    },
)


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _return_map_callers(return_map: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    if (
        return_map.get("schema_version") != 1
        or return_map.get("analysis_kind") != "native_rng_return_id_map"
    ):
        raise SpawnCoordinatePathError("unsupported RNG return map")
    digest = hashlib.sha256(
        encode_rng_return_map(return_map).encode("utf-8")
    ).hexdigest()
    if digest != EXPECTED_RETURN_MAP_SHA256:
        raise SpawnCoordinatePathError("RNG return map digest differs")
    identity = return_map.get("identity")
    if not isinstance(identity, Mapping) or (
        identity.get("platform") != "windows"
        or identity.get("architecture") != "x86"
        or identity.get("build_id") != EXPECTED_BUILD_ID
        or identity.get("executable_sha256") != EXPECTED_EXECUTABLE_SHA256
        or identity.get("executable_size") != EXPECTED_EXECUTABLE_SIZE
    ):
        raise SpawnCoordinatePathError("RNG return map identity differs")
    raw_callers = return_map.get("callers")
    if not isinstance(raw_callers, list):
        raise SpawnCoordinatePathError("RNG return map callers are missing")
    callers: dict[int, Mapping[str, Any]] = {}
    for expected_id, raw in enumerate(raw_callers, start=1):
        if not isinstance(raw, Mapping) or raw.get("caller_id") != expected_id:
            raise SpawnCoordinatePathError("RNG caller IDs are not contiguous")
        callers[expected_id] = raw
    return callers


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise SpawnCoordinatePathError(f"RVA 0x{rva:08x} is not file-backed")
    section = next(
        (
            candidate
            for candidate in image.sections
            if candidate.virtual_address <= rva
            and rva + size <= candidate.virtual_address + candidate.raw_size
        ),
        None,
    )
    if section is None or not section.executable:
        raise SpawnCoordinatePathError(f"RVA 0x{rva:08x} is not executable")
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise SpawnCoordinatePathError(f"RVA 0x{rva:08x} is not E8 rel32")
    return (rva + 5 + struct.unpack_from("<i", encoded, 1)[0]) & 0xFFFFFFFF


def _expected_regions() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "evidence_class": "fact",
            "start_rva": f"0x{spec['start']:08x}",
            "end_rva_exclusive": f"0x{spec['end']:08x}",
            "size": spec["end"] - spec["start"],
            "sha256": spec["sha256"],
            "section": ".text",
            "boundary_basis": spec["boundary_basis"],
        }
        for spec in REGION_SPECS
    ]


def _expected_anchors() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "role_id": spec["role_id"],
            "evidence_class": "fact",
            "reference_rva": f"0x{spec['reference_rva']:08x}",
            "instruction_hex": spec["instruction_hex"],
            "string_rva": f"0x{spec['string_rva']:08x}",
            "text": spec["text"],
        }
        for spec in STRING_ANCHOR_SPECS
    ]


def _expected_windows() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region_id": spec["region_id"],
            "start_rva": f"0x{spec['start_rva']:08x}",
            "size": len(bytes.fromhex(spec["instruction_hex"])),
            "instruction_hex": spec["instruction_hex"],
            "evidence_class": spec["evidence_class"],
            "meaning": spec["meaning"],
        }
        for spec in CONTROL_WINDOW_SPECS
    ]


def _expected_edges() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "source_region": spec["source_region"],
            "from_rva": f"0x{spec['from_rva']:08x}",
            "instruction_hex": spec["instruction_hex"],
            "target_id": spec["target_id"],
            "target_rva": f"0x{spec['target_rva']:08x}",
            "evidence_class": "fact",
        }
        for spec in DIRECT_EDGE_SPECS
    ]


def _expected_callsites() -> list[dict[str, Any]]:
    return [
        {
            "id": callsite_id,
            "from_rva": f"0x{from_rva:08x}",
            "instruction_hex": instruction_hex,
            "target_rva": f"0x{target_rva:08x}",
            "target_id": (
                "spawn_coordinate_selector"
                if target_rva == SELECTOR_RVA
                else "spawn_coordinate_scheduler"
            ),
            "evidence_class": "fact",
        }
        for callsite_id, from_rva, instruction_hex, target_rva in DIRECT_CALLSITE_SPECS
    ]


def _rng_roles(return_map: Mapping[str, Any]) -> list[dict[str, Any]]:
    callers = _return_map_callers(return_map)
    roles = []
    for spec in RNG_CALLER_SPECS:
        caller = callers[spec["caller_id"]]
        roles.append(
            {
                "caller_id": spec["caller_id"],
                "call_rva": caller.get("call_rva"),
                "return_rva": caller.get("return_rva"),
                "region_id": spec["region_id"],
                "role_id": spec["role_id"],
                "domain": spec["domain"],
                "evidence_class": "inference",
                "meaning": spec["meaning"],
            }
        )
    return roles


def _method() -> dict[str, Any]:
    return {
        "boundary_review": (
            "The two contiguous functions were reviewed with focused x86 "
            "disassembly, independently decoded, and hashed."
        ),
        "control_flow_review": (
            "Exact branch, vector-count, modulo, erase-loop, log, and direct-call "
            "windows are pinned. All E8 rel32 candidates targeting either "
            "reviewed function are exhaustively scanned in executable sections."
        ),
        "limitations": [
            (
                "The semantic names are conservative analyst inferences over "
                "exact machine-code facts."
            ),
            (
                "The scheduler's indirect virtual predicates are intentionally "
                "unnamed and unresolved."
            ),
            (
                "Static control flow does not prove natural runtime "
                "reachability or draw counts."
            ),
            (
                "The artifact applies only to the exact owner-observed Windows "
                "executable and original return map."
            ),
        ],
    }


def _conclusions() -> list[dict[str, Any]]:
    return [
        {
            "id": "fallback_is_emergency_placement",
            "evidence_class": "inference",
            "claim": (
                "Caller 59 is reached only after the ordinary filtered vector "
                "is empty and the executable emits its emergency-placement log."
            ),
        },
        {
            "id": "both_final_selectors_use_modulo",
            "evidence_class": "inference",
            "claim": (
                "Callers 59 and 60 both choose an 8-byte point with raw shared "
                "RNG modulo the exact candidate count."
            ),
        },
        {
            "id": "scheduler_is_predicate_order_not_final_selection",
            "evidence_class": "inference",
            "claim": (
                "Caller 66 randomizes a without-replacement order for opaque "
                "predicate checks. If the path proceeds, a separate call to "
                "the ordinary selector chooses the final coordinate."
            ),
        },
        {
            "id": "scheduler_draws_are_upstream_state",
            "evidence_class": "inference",
            "claim": (
                "When the scheduler path runs, zero or more caller-66 draws can "
                "advance the same shared stream before the final selector draw."
            ),
        },
    ]


def _summary(rng_roles: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "region_count": len(REGION_SPECS),
        "string_anchor_count": len(STRING_ANCHOR_SPECS),
        "control_window_count": len(CONTROL_WINDOW_SPECS),
        "direct_edge_count": len(DIRECT_EDGE_SPECS),
        "selector_direct_callsite_count": sum(
            target == SELECTOR_RVA for _, _, _, target in DIRECT_CALLSITE_SPECS
        ),
        "scheduler_direct_callsite_count": sum(
            target == SCHEDULER_RVA for _, _, _, target in DIRECT_CALLSITE_SPECS
        ),
        "rng_caller_ids": [role["caller_id"] for role in rng_roles],
        "final_selector_rng_caller_ids": [59, 60],
        "scheduler_rng_caller_ids": [66],
        "fallback_is_emergency_only": True,
        "scheduler_selects_final_coordinate": False,
    }


def _expected_shape(return_map: Mapping[str, Any]) -> dict[str, Any]:
    rng_roles = _rng_roles(return_map)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
        },
        "sources": {
            "rng_return_map_sha256": EXPECTED_RETURN_MAP_SHA256,
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
        },
        "method": _method(),
        "regions": _expected_regions(),
        "string_anchors": _expected_anchors(),
        "control_windows": _expected_windows(),
        "direct_call_edges": _expected_edges(),
        "direct_callsites": _expected_callsites(),
        "rng_callers": rng_roles,
        "conclusions": _conclusions(),
        "summary": _summary(rng_roles),
    }


def _scan_direct_calls(
    image: Any,
    data: bytes,
    targets: set[int],
) -> dict[int, list[int]]:
    hits = {target: [] for target in targets}
    for section in image.sections:
        if not section.executable:
            continue
        raw = data[section.raw_offset : section.raw_offset + section.raw_size]
        for offset in range(0, max(0, len(raw) - 4)):
            if raw[offset] != 0xE8:
                continue
            site = section.virtual_address + offset
            target = _direct_target(site, raw[offset : offset + 5])
            if target in hits:
                hits[target].append(site)
    return hits


def build_spawn_coordinate_path_map(
    executable: Path,
    return_map: Mapping[str, Any],
) -> dict[str, Any]:
    """Reproduce the exact-build spawn-coordinate path map."""
    expected = _expected_shape(return_map)
    data, image, digest = _load_executable(executable)
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
    ):
        raise SpawnCoordinatePathError("executable identity differs")

    ranges: dict[str, tuple[int, int]] = {}
    for spec in REGION_SPECS:
        size = spec["end"] - spec["start"]
        try:
            body = _region_bytes(
                image, data, spec["start"], size, ".text", spec["id"]
            )
        except Exception as exc:
            raise SpawnCoordinatePathError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise SpawnCoordinatePathError(f"region {spec['id']} bytes differ")
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise SpawnCoordinatePathError(str(exc)) from exc

    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["instruction_hex"])
        actual = _bytes_at(image, data, spec["start_rva"], len(encoded))
        if actual != encoded:
            raise SpawnCoordinatePathError(f"control window {spec['id']} differs")
        if spec["start_rva"] not in decoded[spec["region_id"]]:
            raise SpawnCoordinatePathError(
                f"control window {spec['id']} does not begin at an instruction"
            )

    callers = _return_map_callers(return_map)
    for spec, role in zip(RNG_CALLER_SPECS, expected["rng_callers"], strict=True):
        caller = callers[spec["caller_id"]]
        call_rva = int(caller["call_rva"], 16)
        encoded = decoded[spec["region_id"]].get(call_rva)
        if encoded is None or _direct_target(call_rva, encoded[1]) != RNG_CORE_RVA:
            raise SpawnCoordinatePathError(
                f"RNG caller {spec['caller_id']} does not target the core"
            )
        if caller.get("return_rva") != f"0x{call_rva + 5:08x}":
            raise SpawnCoordinatePathError(
                f"RNG caller {spec['caller_id']} return RVA differs"
            )
        if role["call_rva"] != f"0x{call_rva:08x}":
            raise SpawnCoordinatePathError(
                f"RNG caller {spec['caller_id']} binding differs"
            )

    for spec in STRING_ANCHOR_SPECS:
        text = spec["text"].encode("ascii") + b"\0"
        offset = image.rva_span_to_file_offset(spec["string_rva"], len(text))
        if offset is None or data[offset : offset + len(text)] != text:
            raise SpawnCoordinatePathError(f"string anchor {spec['id']} differs")
        encoded = bytes.fromhex(spec["instruction_hex"])
        if _bytes_at(image, data, spec["reference_rva"], len(encoded)) != encoded:
            raise SpawnCoordinatePathError(f"string reference {spec['id']} differs")
        expected_va = image.image_base + spec["string_rva"]
        if struct.pack("<I", expected_va) not in encoded:
            raise SpawnCoordinatePathError(
                f"string reference {spec['id']} target differs"
            )

    for spec in DIRECT_EDGE_SPECS:
        instruction = decoded[spec["source_region"]].get(spec["from_rva"])
        expected_bytes = bytes.fromhex(spec["instruction_hex"])
        if instruction is None or instruction[1] != expected_bytes:
            raise SpawnCoordinatePathError(f"direct edge {spec['id']} bytes differ")
        if _direct_target(spec["from_rva"], instruction[1]) != spec["target_rva"]:
            raise SpawnCoordinatePathError(f"direct edge {spec['id']} target differs")

    scanned = _scan_direct_calls(image, data, {SELECTOR_RVA, SCHEDULER_RVA})
    expected_scanned = {
        SELECTOR_RVA: [
            from_rva
            for _, from_rva, _, target_rva in DIRECT_CALLSITE_SPECS
            if target_rva == SELECTOR_RVA
        ],
        SCHEDULER_RVA: [
            from_rva
            for _, from_rva, _, target_rva in DIRECT_CALLSITE_SPECS
            if target_rva == SCHEDULER_RVA
        ],
    }
    if scanned != expected_scanned:
        raise SpawnCoordinatePathError("direct callsite catalog differs")
    for _, from_rva, instruction_hex, target_rva in DIRECT_CALLSITE_SPECS:
        encoded = bytes.fromhex(instruction_hex)
        if _bytes_at(image, data, from_rva, len(encoded)) != encoded:
            raise SpawnCoordinatePathError(
                f"direct callsite 0x{from_rva:08x} bytes differ"
            )
        if _direct_target(from_rva, encoded) != target_rva:
            raise SpawnCoordinatePathError(
                f"direct callsite 0x{from_rva:08x} target differs"
            )
    return expected


def validate_spawn_coordinate_path_map_binding(
    value: Mapping[str, Any],
    return_map: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable identities and reviewed fields without the executable."""
    if not isinstance(value, Mapping):
        raise SpawnCoordinatePathError("spawn-coordinate path map must be an object")
    expected = _expected_shape(return_map)
    if dict(value) != expected:
        raise SpawnCoordinatePathError("spawn-coordinate path map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "rng_caller_ids": expected["summary"]["rng_caller_ids"],
        "fallback_is_emergency_only": True,
        "scheduler_selects_final_coordinate": False,
    }


def validate_spawn_coordinate_path_map(
    executable: Path,
    value: Mapping[str, Any],
    return_map: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the path map and reject byte, address, or prose drift."""
    expected = build_spawn_coordinate_path_map(executable, return_map)
    if dict(value) != expected:
        raise SpawnCoordinatePathError(
            "spawn-coordinate path map differs from executable analysis"
        )
    result = validate_spawn_coordinate_path_map_binding(value, return_map)
    result["status"] = "verified"
    return result


def encode_spawn_coordinate_path_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
