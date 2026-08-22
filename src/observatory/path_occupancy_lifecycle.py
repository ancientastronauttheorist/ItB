"""Reproduce exact-build native path occupancy-lifecycle evidence.

This map joins the native ``Pawn:IsDead`` and ``Pawn:IsCorpse`` bindings to
the tile occupancy predicate used by path traversal and destination filtering.
It is intentionally narrow: the artifact distinguishes live pawns, persistent
corpse pawns, and transient dead non-corpse pawns without attempting to model
the broader death/effect scheduler.
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
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_path_occupancy_lifecycle_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000


class PathOccupancyLifecycleError(RuntimeError):
    """Raised when the exact path occupancy-lifecycle map cannot be reproduced."""


REGION_SPECS = (
    (
        "board_is_blocked",
        0x0015FF40,
        0x0015FFD3,
        "17436eb425b49baa211547ca79073ef7a473c124ca30f87fe099acdfd3f9752d",
        ".text",
        True,
        "Complete Board GridSearchable stop predicate through RET 0x0c.",
    ),
    (
        "path_manager_default_pawnspace",
        0x0016FD50,
        0x0016FD66,
        "b5eed1df511c992ecc74b23340515fe754981e7328c9cd6293c2771e0243e758",
        ".text",
        True,
        "Complete two-coordinate wrapper through RET 0x08.",
    ),
    (
        "path_manager_pawnspace_query",
        0x0016FD70,
        0x0016FDE1,
        "8bed0407e45f2443921799cbe630af6ddae0d7f14b1d3c6199c6e3de818d6f69",
        ".text",
        True,
        "Complete coordinate/mode pawn-space query through RET 0x0c.",
    ),
    (
        "counted_occupancy",
        0x0019FF40,
        0x0019FFD3,
        "1e3282851e31b74bfaba10d692ac4c31517d7416d47201c7e2eb5fdf36e4b1f1",
        ".text",
        True,
        "Complete per-tile counted-occupancy predicate through RET 0x04.",
    ),
    (
        "grid_tile_can_traverse",
        0x001A0150,
        0x001A0288,
        "548085ece564eb40e21535d5cbd8eb55b6f3fe2c60c35400ecd9028537f081ee",
        ".text",
        True,
        "Complete per-tile traversal predicate through RET 0x04.",
    ),
    (
        "pawn_is_corpse",
        0x0022CDE0,
        0x0022CE47,
        "806702601f6a75193f6479e0357150d5264c10b7661a434bac7eeb1a807606c7",
        ".text",
        True,
        "Complete native Pawn IsCorpse member through RET.",
    ),
    (
        "pawn_is_dead_thunk",
        0x002E39A2,
        0x002E39A7,
        "2583df412e7df54ae54a5b27baf8262583a3e4de9ed4ddfd2fef4f3209c53670",
        ".text",
        True,
        "Complete Pawn IsDead virtual thunk at vtable slot 0x10.",
    ),
    (
        "path_manager_vtable",
        0x0042E258,
        0x0042E2B0,
        "a28b80cae5599855be0bda4f19477e7c6199dbeba11bc75275d7ea4c544c1fd2",
        ".rdata",
        False,
        "Board +0x0c path-manager vtable through slot 0x54.",
    ),
)


CONTROL_WINDOW_SPECS = (
    (
        "constructor_path_manager_vtable",
        0x0015F1F0,
        "c707fce28200c70358e28200",
        "The Board constructor installs RVA 0x0042e258 on the +0x0c path-manager subobject.",
    ),
    (
        "board_stop_pawnspace_call",
        0x0015FF94,
        "8b460c8d4e0cff750cff75088b4050ffd084c07418",
        "Board stop filtering calls path-manager vtable slot 0x50 and blocks when it returns true.",
    ),
    (
        "default_pawnspace_hardcodes_true",
        0x0016FD50,
        "558bec8b016a01ff750cff75088b404cffd05dc20800",
        "The slot-0x50 wrapper pushes literal mode 1 before delegating to slot 0x4c.",
    ),
    (
        "pawnspace_query_forwards_mode",
        0x0016FDA9,
        "8b4508ff75108d0c408b465069750cbc2b00000334888bcee87a0103005e8be55dc20c00ff751083c65c8bcee8660103005e8be55dc20c00",
        "Both in-bounds and fallback tile paths forward the supplied mode to counted occupancy.",
    ),
    (
        "roadrunner_terrain_only",
        0x001A0188,
        "83f80475238b86e02a000083f801740e83f804740983f8090f85d50000005f33c05e8be55dc20400",
        "Low profile 4 returns from its terrain-only branch before ordinary occupancy calls.",
    ),
    (
        "ordinary_traversal_occupancy",
        0x001A01B9,
        "83f802530f94450be84afdffff3bc78bce6a010f94c7e86cfdffff84c074168bcee881f100008bc8e85adf090084c07404b301eb0232db6a018bcee847fdffff84c0740484ff7448",
        "Ordinary traversal calls counted occupancy with literal mode 1 and blocks a different counted pawn.",
    ),
    (
        "count_live_or_corpse",
        0x0019FF80,
        "8b86a00000008d1cbd000000008b0c038b018b4010ffd084c0742f8b8ea00000008b0c19e837ce080084c0751d8b86a4000000472b86a0000000c1f8023bf872bf",
        "Mode 1 counts an entry when IsDead is false or, for a dead pawn, IsCorpse is true.",
    ),
    (
        "iscorpse_binding",
        0x0027BD0A,
        "ff75f0c745e8e0cd6200ff75f0c745ec00000000518d4de85168b88e83008bc8e821070100",
        "The shipped IsCorpse name is registered to native RVA 0x0022cde0.",
    ),
    (
        "isdead_binding",
        0x0027C0A1,
        "ff75f0c745e8a2396e00ff75f0c745ec00000000518d4de85168fc8f83008bc8e88a030100",
        "The shipped IsDead name is registered to the RVA 0x002e39a2 virtual thunk.",
    ),
    (
        "isdead_thunk",
        0x002E39A2,
        "8b01ff6010",
        "Pawn IsDead dispatches through vtable slot 0x10.",
    ),
)


BINDING_SPECS = (
    {
        "name": "IsCorpse",
        "string_rva": 0x00438EB8,
        "string_bytes": b"IsCorpse\0",
        "member_store_rva": 0x0027BD0D,
        "name_reference_rva": 0x0027BD23,
        "native_entry_rva": 0x0022CDE0,
        "binding_kind": "direct_member",
    },
    {
        "name": "IsDead",
        "string_rva": 0x00438FFC,
        "string_bytes": b"IsDead\0",
        "member_store_rva": 0x0027C0A4,
        "name_reference_rva": 0x0027C0BA,
        "native_entry_rva": 0x002E39A2,
        "binding_kind": "virtual_thunk",
        "vtable_slot": 0x10,
    },
)


PATH_MANAGER_VTABLE_RVA = 0x0042E258
PATH_MANAGER_QUERY_SLOT = 0x4C
PATH_MANAGER_DEFAULT_SLOT = 0x50
PATH_MANAGER_QUERY_TARGET_RVA = 0x0016FD70
PATH_MANAGER_DEFAULT_TARGET_RVA = 0x0016FD50


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bytes_at(
    image: Any,
    data: bytes,
    rva: int,
    size: int,
    *,
    executable: bool | None = None,
) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise PathOccupancyLifecycleError(f"RVA 0x{rva:08x} is not file-backed")
    section = next(
        (
            item
            for item in image.sections
            if item.virtual_address <= rva
            and rva + size <= item.virtual_address + item.raw_size
        ),
        None,
    )
    if section is None:
        raise PathOccupancyLifecycleError(
            f"RVA 0x{rva:08x} has no containing section"
        )
    if executable is not None and section.executable != executable:
        raise PathOccupancyLifecycleError(
            f"RVA 0x{rva:08x} section permissions differ"
        )
    return data[offset : offset + size]


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": region_id,
            "evidence_class": "fact",
            "start_rva": f"0x{start:08x}",
            "end_rva_exclusive": f"0x{end:08x}",
            "size": end - start,
            "sha256": digest,
            "section": section,
            "decoded_as_code": decode,
            "boundary_basis": basis,
        }
        for region_id, start, end, digest, section, decode, basis in REGION_SPECS
    ]


def _control_windows() -> list[dict[str, Any]]:
    return [
        {
            "id": window_id,
            "start_rva": f"0x{start:08x}",
            "size": len(bytes.fromhex(encoded)),
            "instruction_hex": encoded,
            "evidence_class": "fact",
            "meaning": meaning,
        }
        for window_id, start, encoded, meaning in CONTROL_WINDOW_SPECS
    ]


def _bindings() -> list[dict[str, Any]]:
    records = []
    for spec in BINDING_SPECS:
        record = {
            "name": spec["name"],
            "evidence_class": "fact",
            "string_rva": f"0x{spec['string_rva']:08x}",
            "member_store_rva": f"0x{spec['member_store_rva']:08x}",
            "name_reference_rva": f"0x{spec['name_reference_rva']:08x}",
            "native_entry_rva": f"0x{spec['native_entry_rva']:08x}",
            "binding_kind": spec["binding_kind"],
        }
        if "vtable_slot" in spec:
            record["vtable_slot"] = f"0x{spec['vtable_slot']:02x}"
        records.append(record)
    return records


def _expected_shape() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "image_base": f"0x{EXPECTED_IMAGE_BASE:08x}",
        },
        "sources": {
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "upstream_artifacts": [
                {
                    "path": "data/observatory/native/windows_build_13725832_31fe35265598_path_boundaries.json",
                    "file_sha256": "098cbbc5a9dc4c99a07b5f85eac7aaa19812bf093249d1d3f6e6c5ec49277486",
                    "canonical_sha256": "99c8c30fa2e213039e6ba07f5f5062d6487aaa6286eee9cc9cb0cf6aaed23afc",
                },
                {
                    "path": "data/observatory/native/windows_build_13725832_31fe35265598_path_cost_ordering.json",
                    "file_sha256": "f21127154c770ca5db14fec30ec8f9460c7694927bda2c152db1d9d0e3961fb5",
                    "canonical_sha256": "2bd57afec6c28ca75f7964995dd69125439fe913286a94a7a7fda877c0d0ad7d",
                },
            ],
        },
        "method": {
            "boundary_review": "Focused x86 disassembly and a Ghidra 12.1.3 decompiler cross-check joined the shipped Pawn lifecycle bindings to tile occupancy, the Board path-manager vtable, ordinary traversal, and destination filtering.",
            "limitations": [
                "Semantic role names are bounded analyst inferences over exact machine-code facts.",
                "The artifact proves predicate behavior, not when the effect scheduler removes a transient dead pawn from the tile vector.",
                "Runtime IsCorpse values for every pawn subclass and lifecycle phase are not exhaustively captured.",
                "AddMove interruption, per-step effects, and scheduler timing remain outside this artifact.",
                "The artifact applies only to the exact owner-observed Windows executable.",
            ],
        },
        "bindings": _bindings(),
        "path_manager_vtable": {
            "evidence_class": "fact",
            "vtable_rva": f"0x{PATH_MANAGER_VTABLE_RVA:08x}",
            "slots": [
                {
                    "offset": f"0x{PATH_MANAGER_QUERY_SLOT:02x}",
                    "target_rva": f"0x{PATH_MANAGER_QUERY_TARGET_RVA:08x}",
                    "role": "pawn_space_query_with_mode",
                },
                {
                    "offset": f"0x{PATH_MANAGER_DEFAULT_SLOT:02x}",
                    "target_rva": f"0x{PATH_MANAGER_DEFAULT_TARGET_RVA:08x}",
                    "role": "pawn_space_query_default_mode_true",
                },
            ],
        },
        "regions": _region_records(),
        "control_windows": _control_windows(),
        "occupancy_mode": {
            "mode_0": {
                "result": "any_tile_entry",
                "evidence_class": "inference",
            },
            "mode_1": {
                "counts_live_pawn": True,
                "counts_dead_corpse_pawn": True,
                "counts_dead_non_corpse_pawn": False,
                "predicate": "not IsDead() or IsCorpse()",
                "evidence_class": "inference",
            },
            "ordinary_traversal_mode": 1,
            "destination_filter_mode": 1,
        },
        "path_behavior": {
            "ordinary_live_other_pawn_blocks_transit": True,
            "ordinary_persistent_corpse_blocks_transit": True,
            "ordinary_transient_dead_non_corpse_blocks_transit": False,
            "roadrunner_live_pawn_blocks_transit": False,
            "roadrunner_persistent_corpse_blocks_transit": False,
            "live_pawn_blocks_destination": True,
            "persistent_corpse_blocks_destination": True,
            "transient_dead_non_corpse_blocks_destination": False,
            "evidence_class": "inference",
        },
        "conclusions": [
            {
                "id": "mode_one_means_live_or_persistent_corpse",
                "evidence_class": "inference",
                "claim": "The mode-1 tile predicate returns occupied immediately when Pawn:IsDead is false. For a dead pawn it returns occupied only when Pawn:IsCorpse is true; dead non-corpse entries are skipped.",
            },
            {
                "id": "ordinary_pathing_counts_persistent_corpses",
                "evidence_class": "inference",
                "claim": "Ordinary low path profiles call the tile predicate with literal mode 1, so a live pawn or persistent corpse blocks traversal while a retained transient dead non-corpse pawn does not.",
            },
            {
                "id": "destination_filter_counts_persistent_corpses",
                "evidence_class": "inference",
                "claim": "Board IsBlocked dispatches through path-manager slot 0x50; that wrapper hardcodes mode 1, so returned reachable destinations cannot be live-pawn or persistent-corpse spaces.",
            },
            {
                "id": "roadrunner_transits_but_does_not_stop_on_corpses",
                "evidence_class": "inference",
                "claim": "PATH_ROADRUNNER=4 exits its terrain-only traversal branch before occupancy calls and may therefore transit a persistent corpse, while the common destination filter still rejects stopping there.",
            },
            {
                "id": "solver_needed_explicit_corpse_lifecycle_state",
                "evidence_class": "inference",
                "claim": "Rust v402 treated every hp<=0 unit as a hard path blocker and gave Road Runner no corpse transit exception. Exact native conformance requires distinguishing current/persistent corpse state from transient dead non-corpse state.",
            },
        ],
        "summary": {
            "region_count": len(REGION_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "binding_count": len(BINDING_SPECS),
            "mode_1_predicate": "live_or_persistent_corpse",
            "ordinary_persistent_corpse_blocks": True,
            "ordinary_transient_dead_non_corpse_blocks": False,
            "roadrunner_persistent_corpse_transit": True,
            "roadrunner_persistent_corpse_stop": False,
            "simulator_version": 403,
            "remaining_runtime_proof": [
                "matched IsCorpse values across disabled mechs and source Corpse=true pawns",
                "transient dead-pawn removal timing between separate player actions",
                "AddMove step effects, interruption, and scheduler timing",
                "non-Windows build equivalence",
            ],
        },
    }


def build_path_occupancy_lifecycle_map(executable: Path) -> dict[str, Any]:
    """Reproduce the exact-build native path occupancy-lifecycle map."""
    expected = _expected_shape()
    data, image, digest = _load_executable(executable)
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise PathOccupancyLifecycleError("executable identity differs")

    decoded_regions: dict[str, tuple[int, int]] = {}
    for region_id, start, end, expected_digest, _section, decode, _basis in REGION_SPECS:
        body = _bytes_at(image, data, start, end - start, executable=decode)
        if hashlib.sha256(body).hexdigest() != expected_digest:
            raise PathOccupancyLifecycleError(f"region {region_id} bytes differ")
        if decode:
            decoded_regions[region_id] = (start, end)

    control_regions = {
        f"control_{window_id}": (start, start + len(bytes.fromhex(encoded)))
        for window_id, start, encoded, _meaning in CONTROL_WINDOW_SPECS
    }
    try:
        _decode_x86_regions(image, data, {**decoded_regions, **control_regions})
    except Exception as exc:
        raise PathOccupancyLifecycleError(str(exc)) from exc

    for window_id, start, encoded_hex, _meaning in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(encoded_hex)
        if _bytes_at(image, data, start, len(encoded), executable=True) != encoded:
            raise PathOccupancyLifecycleError(f"control window {window_id} differs")

    for spec in BINDING_SPECS:
        if _bytes_at(
            image,
            data,
            spec["string_rva"],
            len(spec["string_bytes"]),
            executable=False,
        ) != spec["string_bytes"]:
            raise PathOccupancyLifecycleError(f"{spec['name']} binding string differs")

    vtable = _bytes_at(
        image,
        data,
        PATH_MANAGER_VTABLE_RVA,
        0x58,
        executable=False,
    )
    query_target = struct.unpack_from("<I", vtable, PATH_MANAGER_QUERY_SLOT)[0]
    default_target = struct.unpack_from("<I", vtable, PATH_MANAGER_DEFAULT_SLOT)[0]
    if query_target - image.image_base != PATH_MANAGER_QUERY_TARGET_RVA:
        raise PathOccupancyLifecycleError("path-manager query slot differs")
    if default_target - image.image_base != PATH_MANAGER_DEFAULT_TARGET_RVA:
        raise PathOccupancyLifecycleError("path-manager default slot differs")

    return expected


def validate_path_occupancy_lifecycle_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without requiring the executable."""
    if not isinstance(value, Mapping):
        raise PathOccupancyLifecycleError("path occupancy lifecycle map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise PathOccupancyLifecycleError("path occupancy lifecycle map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "mode_1_predicate": "live_or_persistent_corpse",
        "ordinary_persistent_corpse_blocks": True,
        "ordinary_transient_dead_non_corpse_blocks": False,
        "roadrunner_persistent_corpse_transit": True,
        "roadrunner_persistent_corpse_stop": False,
        "simulator_version": 403,
    }


def validate_path_occupancy_lifecycle_map(
    executable: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject byte, address, or prose drift."""
    expected = build_path_occupancy_lifecycle_map(executable)
    if dict(value) != expected:
        raise PathOccupancyLifecycleError(
            "path occupancy lifecycle map differs from executable analysis"
        )
    result = validate_path_occupancy_lifecycle_map_binding(value)
    result["status"] = "verified"
    return result


def encode_path_occupancy_lifecycle_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
