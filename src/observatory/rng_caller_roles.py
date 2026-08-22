"""Build-keyed semantic overlay for RNG callers seen before spawn selection.

The native RNG return map intentionally leaves raw call candidates unlabeled.
This module adds a separate, immutable overlay for the small set of callers
that varied in the matched spawn-coordinate campaign.  Keeping the overlay
separate preserves the return-map digest embedded in already captured native
checkpoints.

Region boundaries and prose meanings are reviewed analyst evidence.  The
builder independently pins the executable identity, hashes every declared
function, decodes each function contiguously with Capstone, verifies every
RNG call against the original return map, and checks literal string anchors.
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
ANALYSIS_KIND = "native_rng_caller_role_overlay"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_RETURN_MAP_SHA256 = (
    "7da4ababb6aa91d7b834e68ea6d42a8a40b6ae379531f42cbbc96556cdcaae48"
)
RNG_CORE_RVA = 0x00387F16


class RNGCallerRoleError(RuntimeError):
    """Raised when the caller-role overlay cannot be reproduced exactly."""


REGION_SPECS = (
    {
        "id": "particle_emitter_update",
        "start": 0x000BC910,
        "end": 0x000BCB09,
        "boundary_basis": (
            "Reviewed contiguous function extent through its RET, with the "
            "next byte beginning INT3 alignment padding."
        ),
    },
    {
        "id": "particle_emitter_spawn",
        "start": 0x000BCB10,
        "end": 0x000BCD8F,
        "boundary_basis": (
            "Reviewed contiguous function extent through its RET, with the "
            "next byte beginning INT3 alignment padding."
        ),
    },
    {
        "id": "environment_xp_allocator",
        "start": 0x0018F1C0,
        "end": 0x0018F37F,
        "boundary_basis": (
            "Reviewed contiguous function extent through its RET, corroborated "
            "by both env_xp literal references."
        ),
    },
    {
        "id": "pilot_portrait_update",
        "start": 0x00225430,
        "end": 0x00225DB9,
        "boundary_basis": (
            "Reviewed contiguous function extent through its RET, corroborated "
            "by Pilot_Blink, Pilot_Glare, and Pilot_Look literals."
        ),
    },
    {
        "id": "unit_status_effect_update",
        "start": 0x00233110,
        "end": 0x00233ED3,
        "boundary_basis": (
            "Reviewed contiguous function extent through its RET, corroborated "
            "by water-splash, UnitFire, UnitInfected, and UnitAcid literals."
        ),
    },
)


STRING_ANCHOR_SPECS = (
    ("particle_variance", "particle_presentation", 0x000BBD1B, 0x00426100, "variance"),
    ("particle_random_rot", "particle_presentation", 0x000BBE63, 0x00426124, "random_rot"),
    ("particle_angle_variance", "particle_presentation", 0x000BBEB5, 0x00426130, "angle_variance"),
    ("particle_max_particles", "particle_presentation", 0x000BBFE1, 0x0042615C, "max_particles"),
    ("particle_burst_count", "particle_presentation", 0x000BC159, 0x0042617C, "burst_count"),
    ("particle_image_count", "particle_presentation", 0x000BC1A9, 0x00426188, "image_count"),
    ("environment_xp", "environment_xp_allocation", 0x0018F20B, 0x0042FC7C, "env_xp"),
    ("pilot_blink", "pilot_portrait_presentation", 0x00225AF2, 0x00435A30, "Pilot_Blink"),
    ("pilot_glare", "pilot_portrait_presentation", 0x00225B9A, 0x00435DBC, "Pilot_Glare"),
    ("pilot_look", "pilot_portrait_presentation", 0x00225B9F, 0x00435DA0, "Pilot_Look"),
    ("water_splash", "unit_status_presentation", 0x002332A2, 0x00436524, "/props/water_splash_small"),
    ("unit_fire", "unit_status_presentation", 0x002335FE, 0x00436550, "UnitFire"),
    ("unit_infected", "unit_status_presentation", 0x00233912, 0x00436540, "UnitInfected"),
    ("unit_acid", "unit_acid_presentation", 0x00233B89, 0x00436568, "UnitAcid"),
)


CALL_EDGE_SPECS = (
    {
        "id": "particle_update_to_spawn",
        "source_region": "particle_emitter_update",
        "from_rva": 0x000BC93D,
        "target_region": "particle_emitter_spawn",
        "target_rva": 0x000BCB10,
        "meaning": (
            "The particle update function directly invokes the particle "
            "parameter initializer."
        ),
    },
)


CALLER_ROLE_SPECS = (
    (4, "particle_emitter_update", "particle_presentation", "presentation"),
    (5, "particle_emitter_spawn", "particle_presentation", "presentation"),
    (6, "particle_emitter_spawn", "particle_presentation", "presentation"),
    (7, "particle_emitter_spawn", "particle_presentation", "presentation"),
    (9, "particle_emitter_spawn", "particle_presentation", "presentation"),
    (10, "particle_emitter_spawn", "particle_presentation", "presentation"),
    (11, "particle_emitter_spawn", "particle_presentation", "presentation"),
    (12, "particle_emitter_spawn", "particle_presentation", "presentation"),
    (13, "particle_emitter_spawn", "particle_presentation", "presentation"),
    (72, "environment_xp_allocator", "environment_xp_allocation", "gameplay"),
    (101, "pilot_portrait_update", "pilot_portrait_presentation", "presentation"),
    (114, "unit_status_effect_update", "unit_acid_presentation", "presentation"),
    (115, "unit_status_effect_update", "unit_acid_presentation", "presentation"),
)


ROLE_MEANINGS = {
    "particle_presentation": (
        "RNG populates or perturbs particle-emitter presentation parameters; "
        "the associated parser exposes variance, rotation, particle-count, "
        "burst-count, and image-count fields."
    ),
    "environment_xp_allocation": (
        "RNG distributes the env_xp integer across an eligible object vector."
    ),
    "pilot_portrait_presentation": (
        "RNG selects timing or variants for Pilot_Blink, Pilot_Glare, and "
        "Pilot_Look portrait presentation."
    ),
    "unit_acid_presentation": (
        "The paired RNG calls choose UnitAcid effect coordinates inside the "
        "unit status-effect presentation update."
    ),
}

EXPECTED_REGION_SHA256 = {
    "particle_emitter_update": "1aa268abcbe940e46d51d62d5eb2f1cc5e0808f5c05fa9e9b418416948499739",
    "particle_emitter_spawn": "08ad84f7ed82e6e9922a84d69a7b0935a84034651a07d78d84cdbd3a7f6ae0c3",
    "environment_xp_allocator": "9dbcb30e982d9491c9d6ffeb4af06e4651f31292246d5eb16484f968e3093c5d",
    "pilot_portrait_update": "9a0e31e6c085670ca7d1ae797274f0e0fca39e0dcf47a27e609aaad3f1b01f70",
    "unit_status_effect_update": "9abf728541fd750a1065f6ad725037caa6a0ff7e80abc52aa2351d832a053c62",
}

EXPECTED_ANCHOR_INSTRUCTION_HEX = {
    "particle_variance": "6800618200",
    "particle_random_rot": "6824618200",
    "particle_angle_variance": "6830618200",
    "particle_max_particles": "685c618200",
    "particle_burst_count": "687c618200",
    "particle_image_count": "6888618200",
    "environment_xp": "687cfc8200",
    "pilot_blink": "68305a8300",
    "pilot_glare": "b9bc5d8300",
    "pilot_look": "b8a05d8300",
    "water_splash": "6824658300",
    "unit_fire": "ba50658300",
    "unit_infected": "ba40658300",
    "unit_acid": "ba68658300",
}

EXPECTED_CALL_EDGE_INSTRUCTION_HEX = {
    "particle_update_to_spawn": "e8ce010000",
}


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
        raise RNGCallerRoleError("unsupported RNG return map")
    digest = hashlib.sha256(encode_rng_return_map(return_map).encode("utf-8")).hexdigest()
    if digest != EXPECTED_RETURN_MAP_SHA256:
        raise RNGCallerRoleError("RNG return map digest differs from reviewed input")
    identity = return_map.get("identity")
    if not isinstance(identity, Mapping) or (
        identity.get("platform") != "windows"
        or identity.get("architecture") != "x86"
        or identity.get("build_id") != EXPECTED_BUILD_ID
        or identity.get("executable_sha256") != EXPECTED_EXECUTABLE_SHA256
        or identity.get("executable_size") != EXPECTED_EXECUTABLE_SIZE
    ):
        raise RNGCallerRoleError("RNG return map identity differs")
    raw_callers = return_map.get("callers")
    if not isinstance(raw_callers, list):
        raise RNGCallerRoleError("RNG return map callers are missing")
    callers: dict[int, Mapping[str, Any]] = {}
    for index, raw in enumerate(raw_callers, start=1):
        if not isinstance(raw, Mapping) or raw.get("caller_id") != index:
            raise RNGCallerRoleError("RNG return map caller IDs are not contiguous")
        callers[index] = raw
    return callers


def _instruction_bytes(
    data: bytes,
    image: Any,
    decoded: Mapping[str, Mapping[int, tuple[str, bytes]]],
    region_id: str,
    rva: int,
) -> bytes:
    instruction = decoded.get(region_id, {}).get(rva)
    if instruction is None:
        raise RNGCallerRoleError(
            f"0x{rva:08x} is not a decoded instruction in {region_id}"
        )
    return instruction[1]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise RNGCallerRoleError(f"0x{rva:08x} is not an E8 rel32 call")
    relative = struct.unpack_from("<i", encoded, 1)[0]
    return (rva + 5 + relative) & 0xFFFFFFFF


def _production_shape(return_map: Mapping[str, Any]) -> dict[str, Any]:
    callers = _return_map_callers(return_map)
    roles = []
    for caller_id, region_id, role_id, domain in CALLER_ROLE_SPECS:
        caller = callers.get(caller_id)
        if caller is None:
            raise RNGCallerRoleError(f"RNG caller {caller_id} is missing")
        roles.append(
            {
                "caller_id": caller_id,
                "call_rva": caller.get("call_rva"),
                "return_rva": caller.get("return_rva"),
                "region_id": region_id,
                "role_id": role_id,
                "domain": domain,
                "evidence_class": "inference",
                "meaning": ROLE_MEANINGS[role_id],
            }
        )
    return {
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
        "caller_roles": roles,
    }


def _method() -> dict[str, Any]:
    return {
        "boundary_review": (
            "Contiguous function extents were reviewed with focused x86 "
            "disassembly; every extent is independently decoded and hashed."
        ),
        "semantic_review": (
            "Roles are conservative inferences from literal anchors, direct "
            "calls, parameter math, and the original stable caller IDs."
        ),
        "limitations": [
            "The overlay labels only callers needed by the matched coordinate campaign.",
            "Static roles do not by themselves prove runtime ordering or draw counts.",
            "Presentation labels describe the reviewed functions, not whole-game RNG independence.",
            "The overlay is valid only for the exact executable and original return-map digest.",
        ],
    }


def _expected_regions() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "evidence_class": "fact",
            "start_rva": f"0x{spec['start']:08x}",
            "end_rva_exclusive": f"0x{spec['end']:08x}",
            "size": spec["end"] - spec["start"],
            "sha256": EXPECTED_REGION_SHA256[spec["id"]],
            "section": ".text",
            "boundary_basis": spec["boundary_basis"],
        }
        for spec in REGION_SPECS
    ]


def _expected_anchors() -> list[dict[str, Any]]:
    return [
        {
            "id": anchor_id,
            "role_id": role_id,
            "evidence_class": "fact",
            "reference_rva": f"0x{ref_rva:08x}",
            "instruction_hex": EXPECTED_ANCHOR_INSTRUCTION_HEX[anchor_id],
            "string_rva": f"0x{string_rva:08x}",
            "text": text,
        }
        for anchor_id, role_id, ref_rva, string_rva, text in STRING_ANCHOR_SPECS
    ]


def _expected_edges() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "evidence_class": "fact",
            "source_region": spec["source_region"],
            "from_rva": f"0x{spec['from_rva']:08x}",
            "instruction_hex": EXPECTED_CALL_EDGE_INSTRUCTION_HEX[spec["id"]],
            "target_region": spec["target_region"],
            "target_rva": f"0x{spec['target_rva']:08x}",
            "meaning": spec["meaning"],
        }
        for spec in CALL_EDGE_SPECS
    ]


def _expected_summary(caller_roles: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "region_count": len(REGION_SPECS),
        "string_anchor_count": len(STRING_ANCHOR_SPECS),
        "direct_call_edge_count": len(CALL_EDGE_SPECS),
        "caller_role_count": len(caller_roles),
        "presentation_caller_ids": [
            item["caller_id"]
            for item in caller_roles
            if item["domain"] == "presentation"
        ],
        "gameplay_caller_ids": [
            item["caller_id"]
            for item in caller_roles
            if item["domain"] == "gameplay"
        ],
    }


def build_rng_caller_role_map(
    executable: Path,
    return_map: Mapping[str, Any],
) -> dict[str, Any]:
    """Reproduce the reviewed overlay from the exact Windows executable."""
    shape = _production_shape(return_map)
    data, image, digest = _load_executable(executable)
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
    ):
        raise RNGCallerRoleError("executable identity differs from reviewed build")

    regions: list[dict[str, Any]] = []
    ranges: dict[str, tuple[int, int]] = {}
    for spec in REGION_SPECS:
        start = spec["start"]
        end = spec["end"]
        size = end - start
        try:
            body = _region_bytes(image, data, start, size, ".text", spec["id"])
        except Exception as exc:
            raise RNGCallerRoleError(str(exc)) from exc
        actual_region_sha256 = hashlib.sha256(body).hexdigest()
        if actual_region_sha256 != EXPECTED_REGION_SHA256[spec["id"]]:
            raise RNGCallerRoleError(f"region {spec['id']} bytes differ")
        regions.append(_expected_regions()[len(regions)])
        ranges[spec["id"]] = (start, end)
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise RNGCallerRoleError(str(exc)) from exc

    callers = _return_map_callers(return_map)
    caller_roles = shape["caller_roles"]
    for role in caller_roles:
        call_rva = int(role["call_rva"], 16)
        encoded = _instruction_bytes(
            data, image, decoded, role["region_id"], call_rva
        )
        if _direct_target(call_rva, encoded) != RNG_CORE_RVA:
            raise RNGCallerRoleError(
                f"caller {role['caller_id']} does not target rng_core"
            )
        caller = callers[role["caller_id"]]
        if caller.get("return_rva") != f"0x{call_rva + 5:08x}":
            raise RNGCallerRoleError(
                f"caller {role['caller_id']} return RVA differs"
            )

    anchors = []
    for anchor_id, role_id, ref_rva, string_rva, text in STRING_ANCHOR_SPECS:
        offset = image.rva_span_to_file_offset(string_rva, len(text) + 1)
        if offset is None or data[offset : offset + len(text) + 1] != (
            text.encode("ascii") + b"\0"
        ):
            raise RNGCallerRoleError(f"string anchor {anchor_id} differs")
        ref_offset = image.rva_to_file_offset(ref_rva)
        if ref_offset is None:
            raise RNGCallerRoleError(f"string reference {anchor_id} is not file-backed")
        expected_va = image.image_base + string_rva
        immediate = struct.pack("<I", expected_va)
        window = data[ref_offset : ref_offset + 8]
        marker = window.find(immediate)
        if marker < 0:
            raise RNGCallerRoleError(f"string reference {anchor_id} differs")
        instruction_size = marker + 4
        instruction_hex = window[:instruction_size].hex()
        if instruction_hex != EXPECTED_ANCHOR_INSTRUCTION_HEX[anchor_id]:
            raise RNGCallerRoleError(f"string reference {anchor_id} bytes differ")
        anchors.append(_expected_anchors()[len(anchors)])

    edges = []
    for spec in CALL_EDGE_SPECS:
        encoded = _instruction_bytes(
            data,
            image,
            decoded,
            spec["source_region"],
            spec["from_rva"],
        )
        if _direct_target(spec["from_rva"], encoded) != spec["target_rva"]:
            raise RNGCallerRoleError(f"call edge {spec['id']} target differs")
        if encoded.hex() != EXPECTED_CALL_EDGE_INSTRUCTION_HEX[spec["id"]]:
            raise RNGCallerRoleError(f"call edge {spec['id']} bytes differ")
        edges.append(_expected_edges()[len(edges)])

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        **shape,
        "method": _method(),
        "regions": regions,
        "string_anchors": anchors,
        "direct_call_edges": edges,
        "summary": _expected_summary(caller_roles),
    }


def validate_rng_caller_role_map_binding(
    value: Mapping[str, Any],
    return_map: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable identity and caller bindings without the executable."""
    if not isinstance(value, Mapping):
        raise RNGCallerRoleError("caller-role overlay must be an object")
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("analysis_kind") != ANALYSIS_KIND
    ):
        raise RNGCallerRoleError("unsupported caller-role overlay schema")
    shape = _production_shape(return_map)
    expected_fields = {
        "schema_version",
        "analysis_kind",
        "identity",
        "sources",
        "method",
        "regions",
        "string_anchors",
        "direct_call_edges",
        "caller_roles",
        "summary",
    }
    if set(value) != expected_fields:
        raise RNGCallerRoleError("caller-role overlay fields differ")
    for field in ("identity", "sources", "caller_roles"):
        if value.get(field) != shape[field]:
            raise RNGCallerRoleError(f"caller-role overlay {field} differs")
    roles = shape["caller_roles"]
    expected_static = {
        "method": _method(),
        "regions": _expected_regions(),
        "string_anchors": _expected_anchors(),
        "direct_call_edges": _expected_edges(),
        "summary": _expected_summary(roles),
    }
    for field, expected in expected_static.items():
        if value.get(field) != expected:
            raise RNGCallerRoleError(f"caller-role overlay {field} differs")
    expected_presentation = expected_static["summary"]["presentation_caller_ids"]
    expected_gameplay = expected_static["summary"]["gameplay_caller_ids"]
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "caller_role_count": len(roles),
        "presentation_caller_ids": expected_presentation,
        "gameplay_caller_ids": expected_gameplay,
    }


def validate_rng_caller_role_map(
    executable: Path,
    value: Mapping[str, Any],
    return_map: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the overlay and reject any byte, address, or prose drift."""
    expected = build_rng_caller_role_map(executable, return_map)
    if dict(value) != expected:
        raise RNGCallerRoleError(
            "caller-role overlay differs from exact executable analysis"
        )
    result = validate_rng_caller_role_map_binding(value, return_map)
    result["status"] = "verified"
    return result


def encode_rng_caller_role_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
