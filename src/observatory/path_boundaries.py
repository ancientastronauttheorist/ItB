"""Reproduce the reviewed native movement/path boundary map.

This exact-build artifact joins the shipped Lua names to their native entries,
pins the path-profile constants, and records the narrow movement facts needed
for solver conformance.  In particular, ``Pawn:GetPathProf`` returns low-nibble
profile 4 for ``Road_Runner`` and the corresponding grid traversal branch does
not consult the ordinary occupancy helpers.  Reachable output still applies
the board's stop-blocking predicate, so the ability permits transit through an
occupied tile without permitting a stop on that tile.

The map intentionally does not recover proprietary source or claim complete
path-cost/tie-breaking semantics.  Every published address, byte window,
function hash, string, binding, and vtable slot is rechecked against the exact
owner-observed Windows executable.
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
ANALYSIS_KIND = "native_path_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"


class PathBoundaryError(RuntimeError):
    """Raised when the exact native path map cannot be reproduced."""


REGION_SPECS = (
    (
        "board_get_simple_reachable",
        0x00174060,
        0x001740E9,
        "59259634c2a99a3bb9b3219c3d824488130abbf2d5a4ff7126ad8c7c26e8282a",
        "Reviewed wrapper extent through RET 0x14; the next byte is INT3 padding.",
    ),
    (
        "board_get_reachable",
        0x00174180,
        0x001742C1,
        "e283c5dd59fcf995221823cc3b5af3de9db2889b026e10c1623be492374a416b",
        "Reviewed wrapper extent through RET 0x14; the next byte is INT3 padding.",
    ),
    (
        "board_get_path",
        0x001742D0,
        0x0017438E,
        "a018d8395fcc60e14794c778029607fff585a4d4fb40524b26abafe53972fb31",
        "Reviewed wrapper extent through RET 0x18; the next byte is INT3 padding.",
    ),
    (
        "pawn_get_path_prof",
        0x00232F90,
        0x002330CA,
        "3cc91e8ef2be9950114b088f141a4087057bf7eee702aade83be716e1bccfa40",
        "Reviewed function extent through its final RET; the next byte is INT3.",
    ),
    (
        "reachable_core",
        0x000CE7E0,
        0x000CE9A0,
        "f7b3287d2854115b30ad2d6126d9d573c37d5fabfdd471f1776c5f911990926f",
        "Reviewed function extent through RET 0x14; the next function begins immediately.",
    ),
    (
        "reachable_search",
        0x000CEC40,
        0x000CF2F0,
        "05bebc52863ead8a3ea9a0272301253f726dd03f94a56e1491f7ab7202963645",
        "Reviewed graph-search function extent through RET 0x14.",
    ),
    (
        "path_core",
        0x000CF410,
        0x000CF9DF,
        "3477ed0edb02f50d6e5f92b5c09596c6d6bcc30398a3f5636e3091c3db1f75b4",
        "Reviewed path-search function extent through RET 0x18; INT3 follows.",
    ),
    (
        "simple_reachable_core",
        0x000CFA40,
        0x000CFE88,
        "fd5ad50aba168c7cd33a28aad5972dd61f5b422345675c818b4cfd5ec2e9e9fd",
        "Reviewed simple-reachability function extent through RET 0x18.",
    ),
    (
        "board_is_blocked",
        0x0015FF40,
        0x0015FFD3,
        "17436eb425b49baa211547ca79073ef7a473c124ca30f87fe099acdfd3f9752d",
        "Reviewed Board GridSearchable stop-blocking slot through RET 0x0c.",
    ),
    (
        "grid_tile_can_traverse",
        0x001A0150,
        0x001A0288,
        "548085ece564eb40e21535d5cbd8eb55b6f3fe2c60c35400ecd9028537f081ee",
        "Reviewed per-tile traversal predicate through RET 0x04.",
    ),
    (
        "grid_tile_stop_blocking",
        0x001AF400,
        0x001AF4C0,
        "3e50987e1ad95543c637180b6480cf80c6caa6bbb3a0d3e6974eaa791060fe8e",
        "Reviewed stop-blocking predicate plus its contiguous nine-entry terrain jump table.",
    ),
    (
        "directional_wall_blocking",
        0x00174440,
        0x001744D3,
        "bb7833d592bf38ba0b17f4c41a4f9675094e91fd9e43c9115c601eda7ae80f25",
        "Reviewed directional-wall GridSearchable slot through RET 0x10.",
    ),
)


PATH_CONSTANT_SPECS = (
    ("PATH_PROJECTILE", 3, 0x004396FC, 0x0027E1AE, "68fc968300", 0x0027E1E2, "6a03"),
    ("PATH_FLYER", 1, 0x004396F0, 0x0027E243, "68f0968300", 0x0027E277, "6a01"),
    ("PATH_GROUND", 0, 0x0043971C, 0x0027E2D8, "681c978300", 0x0027E30C, "6a00"),
    ("PATH_MASSIVE", 2, 0x0043970C, 0x0027E36D, "680c978300", 0x0027E3A1, "6a02"),
    ("PATH_PHASING", 9, 0x00439738, 0x0027E402, "6838978300", 0x0027E436, "6a09"),
    ("PATH_BURROWER", 7, 0x00439728, 0x0027E497, "6828978300", 0x0027E4CB, "6a07"),
    ("PATH_ROADRUNNER", 4, 0x00439754, 0x0027E52C, "6854978300", 0x0027E560, "6a04"),
)


API_BINDING_SPECS = (
    {
        "name": "IsBlocked",
        "string_rva": 0x00438530,
        "name_reference_rva": 0x00279AD7,
        "name_reference_hex": "6830858300",
        "member_store_rva": 0x00279AC1,
        "member_store_hex": "c745e8df396e00",
        "native_entry_rva": 0x002E39DF,
        "binding_kind": "virtual_thunk",
        "thunk_hex": "8b01ff600c",
        "vtable_slot": 0x0C,
        "resolved_target_rva": 0x0015FF40,
    },
    {
        "name": "GetSimpleReachable",
        "string_rva": 0x00438628,
        "name_reference_rva": 0x0028783F,
        "name_reference_hex": "c7420828868300",
        "member_store_rva": 0x00279DDF,
        "member_store_hex": "c745e860405700",
        "native_entry_rva": 0x00174060,
        "binding_kind": "direct_member",
    },
    {
        "name": "GetReachable",
        "string_rva": 0x00438644,
        "name_reference_rva": 0x0028797F,
        "name_reference_hex": "c7420844868300",
        "member_store_rva": 0x00279E21,
        "member_store_hex": "c745e880415700",
        "native_entry_rva": 0x00174180,
        "binding_kind": "direct_member",
    },
    {
        "name": "GetPath",
        "string_rva": 0x00438678,
        "name_reference_rva": 0x00287B6F,
        "name_reference_hex": "c7420878868300",
        "member_store_rva": 0x00279EA6,
        "member_store_hex": "c745e8d0425700",
        "native_entry_rva": 0x001742D0,
        "binding_kind": "direct_member",
    },
    {
        "name": "GetPathProf",
        "string_rva": 0x00439068,
        "name_reference_rva": 0x0027C1FC,
        "name_reference_hex": "6868908300",
        "member_store_rva": 0x0027C1E6,
        "member_store_hex": "c745e8902f6300",
        "native_entry_rva": 0x00232F90,
        "binding_kind": "direct_member",
    },
)


BOARD_VTABLE = {
    "complete_object_locator_rva": 0x0044E4DC,
    "region_start_rva": 0x0042E2F8,
    "vtable_rva": 0x0042E2FC,
    "end_rva_exclusive": 0x0042E31C,
    "sha256": "67bc861002deb04f06f11458ad2e90c7606ebe067667437aff0686f9129c7c42",
    "slots": (
        (0x00, 0x0015F860, "lifecycle"),
        (0x04, 0x0015EB20, "grid_extent"),
        (0x08, 0x00162280, "is_valid"),
        (0x0C, 0x0015FF40, "is_blocked"),
        (0x10, 0x00174440, "directional_wall_blocking"),
        (0x14, 0x00162210, "can_traverse"),
        (0x18, 0x001621B0, "destination_cost"),
        (0x1C, 0x00162190, "source_cost"),
    ),
}


CONTROL_WINDOW_SPECS = (
    (
        "roadrunner_path_profile",
        "pawn_get_path_prof",
        0x00233074,
        "83ec188bcc6818658300e88d4dddff8b078bcf8b4004ffd084c074178b87b0000000be04000000c1e0040bc65f5e5b8be55dc3",
        "A successful Road_Runner property query returns (pawn identifier << 4) OR 4.",
    ),
    (
        "massive_or_ground_profile_fallback",
        "pawn_get_path_prof",
        0x002330A7,
        "8bcfe8e21d000084c0b9020000008b87b00000000f45f1c1e0045f0bc65e5b8be55dc3",
        "The final fallback chooses low profile 2 when the Massive predicate is true, otherwise 0, and prefixes the pawn identifier.",
    ),
    (
        "roadrunner_terrain_only_transit",
        "grid_tile_can_traverse",
        0x001A0188,
        "83f80475238b86e02a000083f801740e83f804740983f8090f85d50000005f33c05e8be55dc20400",
        "Low profile 4 has a dedicated branch: Building, Mountain, and Hole reject transit; every other terrain returns true without an occupancy-helper call.",
    ),
    (
        "reachable_profile_and_projectile_filter_gate",
        "board_get_reachable",
        0x0017421A,
        "c745fc0000000083e00fc745ec0100000089451483fb037478",
        "The wrapper retains both the full path profile and its low nibble; exact profile 3 skips its final destination-filter loop.",
    ),
    (
        "reachable_destination_stop_filter",
        "board_get_reachable",
        0x00174241,
        "8b068d1cfd000000008b4df0ff740304ff3403e8e7a8feff83b8e02a0000037506837d1406741a8b068b4df0ff7518ff7418048b11ff34188b420cffd084c0741c",
        "Each non-projectile candidate is terrain-checked and then passed to the Board vtable +0x0c stop-blocking predicate; blocked candidates are removed.",
    ),
    (
        "reachable_budget_and_stop_filter",
        "reachable_core",
        0x000CE8F0,
        "3bc6744083c0108d4ddc50e8e02c0000395de87f22ff75108b078bcfff75e0ff75dc8b400cffd084c0750c8d45dc508d4dd0e85967feff",
        "Only nodes within the requested movement budget whose vtable +0x0c predicate is false are copied into reachable output.",
    ),
    (
        "roadrunner_obeys_directional_walls",
        "directional_wall_blocking",
        0x001744A4,
        "8b451483e00f83f801741b83f803741683f806741183f805740cb8010000005e8be55dc21000",
        "Only low profiles 1, 3, 6, and 5 bypass a present directional wall; profile 4 remains wall-blocked.",
    ),
    (
        "board_stop_blocking_includes_occupancy",
        "board_is_blocked",
        0x0015FF86,
        "ff75108bcae870f4040084c075368b460c8d4e0cff750cff75088b4050ffd084c07418837d1009751bff750c8bceff7508e89498000083f806740932c05e8be55dc20c00",
        "After tile blocking passes, Board stop-blocking consults its pawn-space manager and reports an occupied destination blocked except for its separate profile-9 special case.",
    ),
    (
        "get_path_same_point_is_empty",
        "board_get_path",
        0x001742F6,
        "8b750c8b45188b5510c745f0000000003b7514752d3bd075298b4508c70000000000c7400400000000c74008000000008b4df464890d00000000595e8be55dc21800",
        "GetPath returns an empty point vector immediately when start and end are equal.",
    ),
    (
        "reachable_cardinal_neighbor_order",
        "reachable_search",
        0x000CEF80,
        "8b04f5b4578d00ff75088b0cf5b8578d0003c78b55b803ca8945bc8b035652894dc08bcb8b401057c745c400007a44ffd084c00f85c5010000",
        "Reachability expands four neighbors from the two shipped direction tables and checks the directional-wall slot before traversal.",
    ),
)


DIRECT_EDGE_SPECS = (
    ("simple_wrapper_to_core", "board_get_simple_reachable", 0x001740A0, "e89bb9f5ff", "simple_reachable_core", 0x000CFA40),
    ("reachable_wrapper_to_core", "board_get_reachable", 0x001741CE, "e80da6f5ff", "reachable_core", 0x000CE7E0),
    ("reachable_core_to_search", "reachable_core", 0x000CE879, "e8c2030000", "reachable_search", 0x000CEC40),
    ("path_wrapper_to_core", "board_get_path", 0x00174345, "e8c6b0f5ff", "path_core", 0x000CF410),
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


def _bytes_at(
    image: Any,
    data: bytes,
    rva: int,
    size: int,
    *,
    require_executable: bool | None = None,
) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise PathBoundaryError(f"RVA 0x{rva:08x} is not file-backed")
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
        raise PathBoundaryError(f"RVA 0x{rva:08x} has no containing section")
    if require_executable is not None and section.executable != require_executable:
        raise PathBoundaryError(f"RVA 0x{rva:08x} section permissions differ")
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise PathBoundaryError(f"RVA 0x{rva:08x} is not E8 rel32")
    return (rva + 5 + struct.unpack_from("<i", encoded, 1)[0]) & 0xFFFFFFFF


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": region_id,
            "evidence_class": "fact",
            "start_rva": f"0x{start:08x}",
            "end_rva_exclusive": f"0x{end:08x}",
            "size": end - start,
            "sha256": digest,
            "section": ".text",
            "boundary_basis": basis,
        }
        for region_id, start, end, digest, basis in REGION_SPECS
    ]


def _path_constants() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "value": value,
            "evidence_class": "fact",
            "string_rva": f"0x{string_rva:08x}",
            "string_reference_rva": f"0x{reference_rva:08x}",
            "string_reference_hex": reference_hex,
            "value_push_rva": f"0x{value_rva:08x}",
            "value_push_hex": value_hex,
        }
        for (
            name,
            value,
            string_rva,
            reference_rva,
            reference_hex,
            value_rva,
            value_hex,
        ) in PATH_CONSTANT_SPECS
    ]


def _api_bindings() -> list[dict[str, Any]]:
    records = []
    for spec in API_BINDING_SPECS:
        record = {
            "name": spec["name"],
            "evidence_class": "fact",
            "string_rva": f"0x{spec['string_rva']:08x}",
            "name_reference_rva": f"0x{spec['name_reference_rva']:08x}",
            "name_reference_hex": spec["name_reference_hex"],
            "member_store_rva": f"0x{spec['member_store_rva']:08x}",
            "member_store_hex": spec["member_store_hex"],
            "binding_kind": spec["binding_kind"],
            "native_entry_rva": f"0x{spec['native_entry_rva']:08x}",
        }
        if spec["binding_kind"] == "virtual_thunk":
            record.update(
                {
                    "thunk_hex": spec["thunk_hex"],
                    "vtable_slot": f"0x{spec['vtable_slot']:02x}",
                    "resolved_target_rva": f"0x{spec['resolved_target_rva']:08x}",
                }
            )
        records.append(record)
    return records


def _board_vtable() -> dict[str, Any]:
    return {
        "evidence_class": "fact",
        "complete_object_locator_rva": f"0x{BOARD_VTABLE['complete_object_locator_rva']:08x}",
        "region_start_rva": f"0x{BOARD_VTABLE['region_start_rva']:08x}",
        "vtable_rva": f"0x{BOARD_VTABLE['vtable_rva']:08x}",
        "end_rva_exclusive": f"0x{BOARD_VTABLE['end_rva_exclusive']:08x}",
        "sha256": BOARD_VTABLE["sha256"],
        "slots": [
            {
                "offset": f"0x{offset:02x}",
                "target_rva": f"0x{target:08x}",
                "role": role,
            }
            for offset, target, role in BOARD_VTABLE["slots"]
        ],
    }


def _control_windows() -> list[dict[str, Any]]:
    return [
        {
            "id": window_id,
            "region_id": region_id,
            "start_rva": f"0x{start:08x}",
            "size": len(bytes.fromhex(encoded)),
            "instruction_hex": encoded,
            "evidence_class": "fact",
            "meaning": meaning,
        }
        for window_id, region_id, start, encoded, meaning in CONTROL_WINDOW_SPECS
    ]


def _direct_edges() -> list[dict[str, Any]]:
    return [
        {
            "id": edge_id,
            "source_region": source_region,
            "from_rva": f"0x{source:08x}",
            "instruction_hex": encoded,
            "target_id": target_id,
            "target_rva": f"0x{target:08x}",
            "evidence_class": "fact",
        }
        for edge_id, source_region, source, encoded, target_id, target in DIRECT_EDGE_SPECS
    ]


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
        },
        "sources": {"capstone_version": SUPPORTED_CAPSTONE_VERSION},
        "method": {
            "boundary_review": "Contiguous native wrappers, cores, predicates, and the Pawn path-profile function were reviewed with focused x86 disassembly and independently hashed.",
            "binding_review": "Shipped Lua registration names, absolute member pointers, the IsBlocked virtual thunk, the Board RTTI-linked vtable, and path-constant registrations are pinned independently.",
            "limitations": [
                "Semantic role names are conservative analyst inferences over exact machine-code facts.",
                "The artifact does not claim complete path-cost, tie-breaking, team-specific occupancy, or every path-profile mode.",
                "Static control flow does not replace matched live traces for runtime ordering or edge-case reachability.",
                "Solver safety policies for ACID and hazardous terrain remain separate from native legality.",
                "The artifact applies only to the exact owner-observed Windows executable.",
            ],
        },
        "path_constants": _path_constants(),
        "api_bindings": _api_bindings(),
        "board_gridsearch_vtable": _board_vtable(),
        "regions": _region_records(),
        "control_windows": _control_windows(),
        "direct_call_edges": _direct_edges(),
        "conclusions": [
            {
                "id": "path_api_entries_are_exact",
                "evidence_class": "inference",
                "claim": "The shipped Board GetSimpleReachable, GetReachable, and GetPath names bind to the three reviewed wrappers, while Pawn GetPathProf binds to the reviewed profile function.",
            },
            {
                "id": "path_profiles_embed_pawn_identity",
                "evidence_class": "inference",
                "claim": "Pawn GetPathProf stores the pawn identifier in the high bits and a base path mode in the low nibble; Road_Runner selects base mode 4.",
            },
            {
                "id": "roadrunner_transits_occupied_tiles_but_cannot_stop_there",
                "evidence_class": "inference",
                "claim": "Profile 4 takes a terrain-only traversal branch without ordinary occupancy-helper calls, but GetReachable still applies Board IsBlocked before returning a destination, and that stop predicate rejects occupied pawn spaces.",
            },
            {
                "id": "roadrunner_is_not_flight",
                "evidence_class": "inference",
                "claim": "Profile 4 remains blocked by directional walls and rejects Building, Mountain, and Hole transit; it is distinct from PATH_FLYER=1.",
            },
            {
                "id": "solver_had_a_roadrunner_input_gap",
                "evidence_class": "inference",
                "claim": "The bridge already reports Pilot_Hotshot, but the reviewed Rust baseline mapped no Hotshot flag and hard-blocked every occupied BFS tile, so it omitted native-legal through-unit routes.",
            },
        ],
        "summary": {
            "path_constant_count": len(PATH_CONSTANT_SPECS),
            "api_binding_count": len(API_BINDING_SPECS),
            "region_count": len(REGION_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "roadrunner_profile": 4,
            "roadrunner_can_transit_occupied": True,
            "roadrunner_can_stop_occupied": False,
            "get_path_same_point_empty": True,
            "remaining_runtime_proof": [
                "weighted path-cost and tie-breaking details",
                "team-specific ordinary occupancy edge cases",
                "matched native path/reachable result ordering",
            ],
        },
    }


def build_path_boundary_map(executable: Path) -> dict[str, Any]:
    """Reproduce the exact-build native path boundary map."""
    expected = _expected_shape()
    data, image, digest = _load_executable(executable)
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
    ):
        raise PathBoundaryError("executable identity differs")

    regions: dict[str, tuple[int, int]] = {}
    for region_id, start, end, expected_digest, _basis in REGION_SPECS:
        body = _bytes_at(
            image, data, start, end - start, require_executable=True
        )
        if hashlib.sha256(body).hexdigest() != expected_digest:
            raise PathBoundaryError(f"region {region_id} bytes differ")
        regions[region_id] = (start, end)

    # The terrain jump table embedded after grid_tile_stop_blocking's code is
    # data, so constrain instruction starts using only the pure-code regions.
    decoded_regions = {
        key: value for key, value in regions.items() if key != "grid_tile_stop_blocking"
    }
    try:
        decoded = _decode_x86_regions(image, data, decoded_regions)
    except Exception as exc:
        raise PathBoundaryError(str(exc)) from exc

    for window_id, region_id, start, encoded_hex, _meaning in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(encoded_hex)
        if _bytes_at(image, data, start, len(encoded), require_executable=True) != encoded:
            raise PathBoundaryError(f"control window {window_id} differs")
        if start not in decoded[region_id]:
            raise PathBoundaryError(
                f"control window {window_id} does not begin at an instruction"
            )

    for (
        name,
        value,
        string_rva,
        reference_rva,
        reference_hex,
        value_rva,
        value_hex,
    ) in PATH_CONSTANT_SPECS:
        raw_name = name.encode("ascii") + b"\0"
        if _bytes_at(image, data, string_rva, len(raw_name)) != raw_name:
            raise PathBoundaryError(f"path constant string {name} differs")
        reference = bytes.fromhex(reference_hex)
        if _bytes_at(image, data, reference_rva, len(reference), require_executable=True) != reference:
            raise PathBoundaryError(f"path constant reference {name} differs")
        if struct.pack("<I", image.image_base + string_rva) not in reference:
            raise PathBoundaryError(f"path constant reference {name} target differs")
        value_bytes = bytes.fromhex(value_hex)
        if _bytes_at(image, data, value_rva, len(value_bytes), require_executable=True) != value_bytes:
            raise PathBoundaryError(f"path constant value {name} differs")
        if value_bytes != bytes((0x6A, value & 0xFF)):
            raise PathBoundaryError(f"path constant encoding {name} differs")

    for spec in API_BINDING_SPECS:
        raw_name = spec["name"].encode("ascii") + b"\0"
        if _bytes_at(image, data, spec["string_rva"], len(raw_name)) != raw_name:
            raise PathBoundaryError(f"API string {spec['name']} differs")
        name_reference = bytes.fromhex(spec["name_reference_hex"])
        if _bytes_at(
            image,
            data,
            spec["name_reference_rva"],
            len(name_reference),
            require_executable=True,
        ) != name_reference or struct.pack(
            "<I", image.image_base + spec["string_rva"]
        ) not in name_reference:
            raise PathBoundaryError(f"API name reference {spec['name']} differs")
        member_store = bytes.fromhex(spec["member_store_hex"])
        if _bytes_at(
            image,
            data,
            spec["member_store_rva"],
            len(member_store),
            require_executable=True,
        ) != member_store or struct.pack(
            "<I", image.image_base + spec["native_entry_rva"]
        ) not in member_store:
            raise PathBoundaryError(f"API member binding {spec['name']} differs")
        if spec["binding_kind"] == "virtual_thunk":
            thunk = bytes.fromhex(spec["thunk_hex"])
            if _bytes_at(
                image,
                data,
                spec["native_entry_rva"],
                len(thunk),
                require_executable=True,
            ) != thunk:
                raise PathBoundaryError("IsBlocked virtual thunk differs")

    vtable_start = BOARD_VTABLE["region_start_rva"]
    vtable_end = BOARD_VTABLE["end_rva_exclusive"]
    vtable_body = _bytes_at(
        image,
        data,
        vtable_start,
        vtable_end - vtable_start,
        require_executable=False,
    )
    if hashlib.sha256(vtable_body).hexdigest() != BOARD_VTABLE["sha256"]:
        raise PathBoundaryError("Board GridSearchable vtable bytes differ")
    locator_va = struct.unpack_from("<I", vtable_body, 0)[0]
    if locator_va != image.image_base + BOARD_VTABLE["complete_object_locator_rva"]:
        raise PathBoundaryError("Board vtable complete-object locator differs")
    for offset, target, _role in BOARD_VTABLE["slots"]:
        actual = struct.unpack_from("<I", vtable_body, 4 + offset)[0]
        if actual != image.image_base + target:
            raise PathBoundaryError(f"Board vtable slot 0x{offset:02x} differs")

    for edge_id, source_region, source, encoded_hex, _target_id, target in DIRECT_EDGE_SPECS:
        encoded = bytes.fromhex(encoded_hex)
        instruction = decoded[source_region].get(source)
        if instruction is None or instruction[1] != encoded:
            raise PathBoundaryError(f"direct edge {edge_id} bytes differ")
        if _direct_target(source, encoded) != target:
            raise PathBoundaryError(f"direct edge {edge_id} target differs")

    return expected


def validate_path_boundary_map_binding(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate immutable identities and reviewed fields without the executable."""
    if not isinstance(value, Mapping):
        raise PathBoundaryError("path boundary map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise PathBoundaryError("path boundary map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "roadrunner_profile": 4,
        "roadrunner_can_transit_occupied": True,
        "roadrunner_can_stop_occupied": False,
    }


def validate_path_boundary_map(
    executable: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the path map and reject byte, address, or prose drift."""
    expected = build_path_boundary_map(executable)
    if dict(value) != expected:
        raise PathBoundaryError("path boundary map differs from executable analysis")
    result = validate_path_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_path_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
