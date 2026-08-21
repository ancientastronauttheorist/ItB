"""Build and verify stable return-address IDs for the native RNG core.

The catalog deliberately scans every byte for raw x86 ``E8 rel32`` candidates.
That is broader than instruction decoding: executed return addresses can be
assigned a stable small ID, while non-executed opcode-looking data is harmless.
Reviewed calls are labeled from the separately verified PE boundary map; every
other candidate remains explicitly unclassified.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.pe_boundary_map import (
    PEBoundaryError,
    _load_executable,
    validate_pe_boundary_map,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_rng_return_id_map"
UNKNOWN_CALLER_ID = 0
MAX_CALLER_ID = 255


class RNGReturnMapError(PEBoundaryError):
    """Raised when a build-keyed RNG return map cannot be proven exact."""


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_rva(value: Any, label: str) -> int:
    if (
        type(value) is not str
        or len(value) != 10
        or not value.startswith("0x")
    ):
        raise RNGReturnMapError(f"{label} is not a canonical 32-bit RVA")
    try:
        parsed = int(value[2:], 16)
    except ValueError as exc:
        raise RNGReturnMapError(
            f"{label} is not a canonical 32-bit RVA"
        ) from exc
    if value != f"0x{parsed:08x}":
        raise RNGReturnMapError(f"{label} is not a canonical 32-bit RVA")
    return parsed


def _rng_core_rva(boundaries: Mapping[str, Any]) -> int:
    regions = boundaries.get("regions")
    if not isinstance(regions, list):
        raise RNGReturnMapError("boundary map regions must be an array")
    matches = [
        item
        for item in regions
        if isinstance(item, Mapping) and item.get("id") == "rng_core"
    ]
    if len(matches) != 1:
        raise RNGReturnMapError("boundary map must contain exactly one rng_core")
    return _parse_rva(matches[0].get("start_rva"), "rng_core.start_rva")


def _reviewed_calls(boundaries: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    edges = boundaries.get("direct_call_edges")
    if not isinstance(edges, list):
        raise RNGReturnMapError("boundary map call edges must be an array")
    result: dict[int, Mapping[str, Any]] = {}
    for item in edges:
        if not isinstance(item, Mapping):
            raise RNGReturnMapError("boundary map call edge must be an object")
        target = item.get("target")
        if (
            item.get("kind") != "direct_rel32"
            or not isinstance(target, Mapping)
            or target.get("type") != "region"
            or target.get("region") != "rng_core"
        ):
            continue
        call_rva = _parse_rva(item.get("from_rva"), "direct call from_rva")
        if call_rva in result:
            raise RNGReturnMapError("duplicate reviewed RNG-core call RVA")
        result[call_rva] = item
    return result


def _scan_rng_calls(data: bytes, image: Any, core_rva: int) -> list[tuple[int, str]]:
    candidates: dict[int, str] = {}
    for section in image.sections:
        if not section.executable:
            continue
        body = data[section.raw_offset : section.raw_offset + section.raw_size]
        for offset in range(max(0, len(body) - 4)):
            if body[offset] != 0xE8:
                continue
            (relative,) = struct.unpack_from("<i", body, offset + 1)
            call_rva = section.virtual_address + offset
            target = (call_rva + 5 + relative) & 0xFFFFFFFF
            if target == core_rva:
                previous = candidates.get(call_rva)
                if previous is not None and previous != section.name:
                    raise RNGReturnMapError(
                        "overlapping executable sections give one call RVA "
                        "multiple identities"
                    )
                candidates[call_rva] = section.name
    return sorted(candidates.items())


def build_rng_return_map(
    executable: Path,
    boundaries: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a deterministic caller-ID catalog for one exact reviewed build."""
    try:
        boundary_result = validate_pe_boundary_map(
            executable,
            boundaries,
            inventory=inventory,
        )
    except PEBoundaryError as exc:
        raise RNGReturnMapError(str(exc)) from exc
    data, image, _digest = _load_executable(executable)
    core_rva = _rng_core_rva(boundaries)
    reviewed = _reviewed_calls(boundaries)
    candidates = _scan_rng_calls(data, image, core_rva)
    if not candidates:
        raise RNGReturnMapError("no raw rel32 calls to the RNG core were found")
    if len(candidates) > MAX_CALLER_ID:
        raise RNGReturnMapError("RNG caller catalog exceeds the one-byte ID cap")

    callers = []
    for caller_id, (call_rva, section) in enumerate(candidates, start=1):
        edge = reviewed.get(call_rva)
        if edge is None:
            classification = {
                "status": "unclassified_raw_candidate",
                "edge_id": None,
                "source_region": None,
                "meaning": None,
            }
        else:
            classification = {
                "status": "reviewed_direct_call",
                "edge_id": edge["id"],
                "source_region": edge["source_region"],
                "meaning": edge["meaning"],
            }
        callers.append(
            {
                "caller_id": caller_id,
                "call_rva": f"0x{call_rva:08x}",
                "return_rva": f"0x{call_rva + 5:08x}",
                "section": section,
                "classification": classification,
            }
        )

    reviewed_count = sum(
        item["classification"]["status"] == "reviewed_direct_call"
        for item in callers
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "identity": boundary_result["identity"],
        "sources": {
            "inventory_canonical_sha256": _canonical_sha256(inventory),
            "boundary_map_canonical_sha256": _canonical_sha256(boundaries),
        },
        "rng_core": {
            "region_id": "rng_core",
            "entry_rva": f"0x{core_rva:08x}",
            "unknown_caller_id": UNKNOWN_CALLER_ID,
            "maximum_caller_id": MAX_CALLER_ID,
        },
        "method": {
            "candidate_scan": (
                "Scan every file-backed byte of executable PE sections for raw "
                "E8 rel32 values whose decoded target is rng_core."
            ),
            "stable_id_rule": (
                "Sort by call RVA and assign IDs 1..N; reserve ID 0 for an "
                "executed return address absent from this exact catalog."
            ),
            "runtime_rule": (
                "A native helper may record only the matching small ID, never "
                "an absolute address or pointer."
            ),
            "limitations": [
                "Raw candidates may be opcode-looking bytes embedded in data or operands.",
                "Only boundary-map call sites are semantically reviewed.",
                "Any executed unknown caller makes complete attribution invalid.",
                "The IDs are valid only for the exact executable identity.",
            ],
        },
        "callers": callers,
        "summary": {
            "raw_call_candidate_count": len(callers),
            "reviewed_call_count": reviewed_count,
            "unclassified_call_count": len(callers) - reviewed_count,
            "unknown_caller_id": UNKNOWN_CALLER_ID,
        },
    }


def validate_rng_return_map(
    executable: Path,
    catalog: Mapping[str, Any],
    boundaries: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the catalog and reject any identity, caller, or label drift."""
    if not isinstance(catalog, Mapping):
        raise RNGReturnMapError("RNG return catalog must be an object")
    expected = build_rng_return_map(
        executable,
        boundaries,
        inventory=inventory,
    )
    if dict(catalog) != expected:
        raise RNGReturnMapError(
            "RNG return catalog differs from the exact executable and boundary map"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "verified",
        "identity": expected["identity"],
        "summary": expected["summary"],
    }


def encode_rng_return_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
