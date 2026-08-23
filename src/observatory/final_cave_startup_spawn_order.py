"""Reproduce the exact-build Final Cave startup spawn-admission order.

This continuation joins the immutable Final Cave startup map to the native
``Board:SpawnPawn`` overloads and the previously reviewed coordinate selector.
It proves logical pawn admission and queue order, not presentation timing or
concrete RNG results.
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


SCHEMA_VERSION = 1
ANALYSIS_KIND = "final_cave_startup_spawn_order_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
STARTUP_ARTIFACT_SHA256 = (
    "4cf2f05a267ed87a8cf5b14edbc874343a3969cef2dfb98e849f645ec177f942"
)
SPAWN_PATH_ARTIFACT_SHA256 = (
    "6a5ee719660542979f0e827acd917e43640a018ec6101960e79bafb9a51ce5ed"
)
REPLACEMENT_ARTIFACT_SHA256 = (
    "b08b6d96d4d4ba0f53c024b301b17a039c8deb944632bbc6b8b4000a6e20af50"
)
CADENCE_ARTIFACT_SHA256 = (
    "578275064f6f55ca170128d954613d846eb9398a239c2462de87356549ca7b4e"
)


class FinalCaveStartupSpawnOrderError(RuntimeError):
    """Raised when the reviewed startup spawn-order map cannot be reproduced."""


LUA_SOURCE_SPECS = (
    {
        "path": "scripts/missions/missions.lua",
        "size": 29_573,
        "sha256": (
            "505c02a8668ba2e39d868f95051ede81c6cc1611f1e409219b6caa4fbe1d0257"
        ),
        "symbols": [
            "Mission:BaseStart",
            "Mission:SpawnPawns",
            "Mission:GetStartingPawns",
            "Mission:SetupDiffMod",
        ],
    },
    {
        "path": "scripts/missions/final/mission_final_two.lua",
        "size": 4_887,
        "sha256": (
            "c8a8e40f512939c1f4fd0e0df416e5cbaec00c639e2985ad776e13c38735b17c"
        ),
        "symbols": [
            "Mission_Final_Cave:StartMission",
            "SpawnMechs",
            "Mission_Final_Cave:AddBomb",
        ],
    },
)


REGION_SPECS = (
    {
        "id": "implicit_spawn_registration",
        "start": 0x0027A259,
        "end": 0x0027A27B,
        "sha256": "06a248cc7cc07d426a3fafa88c788d99648a5ea9c3c01d344a7867bdc96f7ba4",
        "boundary_basis": (
            "Ghidra 12.1.3 registration window binding SpawnPawn to the "
            "one-pawn/no-point wrapper."
        ),
    },
    {
        "id": "explicit_spawn_registration",
        "start": 0x0027A2C0,
        "end": 0x0027A2E2,
        "sha256": "28c42d87177da34d97788f5e3a278b4d9805c5a5fd2b955c7b4c2cecf7a0d4ed",
        "boundary_basis": (
            "Ghidra 12.1.3 registration window binding SpawnPawn to the "
            "pawn-plus-point wrapper."
        ),
    },
    {
        "id": "block_spawn_registration",
        "start": 0x0027A97C,
        "end": 0x0027A99E,
        "sha256": "ea7a2dad021276620d4cc7611b0aa4b3b2c16811f09b8105f8ccf750bf727f35",
        "boundary_basis": (
            "Ghidra 12.1.3 registration window binding BlockSpawn to its "
            "synchronous tile-field writer."
        ),
    },
    {
        "id": "spawn_pawn",
        "start": 0x00168D30,
        "end": 0x00168FB9,
        "sha256": "d7aff32427746b800d306a225eb7dd68aadc3a81fae56e1c18774fe062c7d355",
        "boundary_basis": "Ghidra 12.1.3 central Board SpawnPawn body.",
    },
    {
        "id": "common_spawn_wrapper",
        "start": 0x00168FC0,
        "end": 0x001690C0,
        "sha256": "ab1ed558fdb3c9ce5ae86b73e31098eec7bd8b36b4cad22e1d1938027e57450a",
        "boundary_basis": "Ghidra 12.1.3 shared explicit-point Lua wrapper body.",
    },
    {
        "id": "explicit_spawn_wrapper",
        "start": 0x001690C0,
        "end": 0x00169148,
        "sha256": "6b9a45776060e29ee5f758b63e02a10cbe633542ab7e70c160f0e21a84222446",
        "boundary_basis": "Ghidra 12.1.3 pawn-plus-point Lua wrapper body.",
    },
    {
        "id": "implicit_spawn_wrapper",
        "start": 0x00169150,
        "end": 0x00169168,
        "sha256": "c4f0b6932376d1bf75d1d3ef634b0d46a19670809fe487290019f4cbee667e3c",
        "boundary_basis": "Ghidra 12.1.3 one-pawn/no-point Lua wrapper body.",
    },
    {
        "id": "board_add_pawn",
        "start": 0x0016E8C0,
        "end": 0x0016EC8D,
        "sha256": "c9031f10d38ba7cb28959b3460aec686a4366b4697accc7479638436aaa7280a",
        "boundary_basis": (
            "Ghidra 12.1.3 Board pawn-admission body containing invalid-point "
            "selection and the SetSpace call."
        ),
    },
    {
        "id": "block_spawn",
        "start": 0x0016C140,
        "end": 0x0016C168,
        "sha256": "7784bee48dc7ca89bbfd29a64dd1fe2cfefe54a707d05f3ac6d5714b6d471b6b",
        "boundary_basis": "Ghidra 12.1.3 BlockSpawn binding body.",
    },
    {
        "id": "pawn_set_space",
        "start": 0x002301B0,
        "end": 0x00230317,
        "sha256": "bb2f39cac0a81d266296d890dc52d4755da0b60c5c517dd0ee08b714bf10eb3c",
        "boundary_basis": "Ghidra 12.1.3 Pawn logical-space setter body.",
    },
    {
        "id": "pawn_set_space_entry",
        "start": 0x00230320,
        "end": 0x00230339,
        "sha256": "a5034f607b779f10498f79683ac5401dd25c6387a3def070de3776488265865c",
        "boundary_basis": (
            "Ghidra 12.1.3 Pawn SetSpace public entry wrapper."
        ),
    },
    {
        "id": "primary_orchestrator",
        "start": 0x0018AE90,
        "end": 0x0018B36F,
        "sha256": "8a5e7744c920a70f30f8056271d452335be6d601625f8b8d935d5457b77ebf82",
        "boundary_basis": (
            "Ghidra 12.1.3 primary game-loop orchestrator containing the Board "
            "update and later phase-transition call."
        ),
    },
)


DATA_ANCHOR_SPECS = (
    {
        "id": "spawn_pawn_name",
        "rva": 0x00438708,
        "section": ".rdata",
        "data": b"SpawnPawn\0",
        "meaning": "Lua registration name shared by both reviewed overloads.",
    },
    {
        "id": "block_spawn_name",
        "rva": 0x00438964,
        "section": ".rdata",
        "data": b"BlockSpawn\0",
        "meaning": "Lua registration name for the synchronous tile-field writer.",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "implicit_invalid_point",
        "region_id": "implicit_spawn_wrapper",
        "start_rva": 0x00169150,
        "instruction_hex": (
            "558bec83e4f86aff6affff7508e8cefbffff8be55dc20400"
        ),
        "meaning": (
            "The no-point wrapper supplies (-1,-1) and synchronously calls the "
            "central SpawnPawn body."
        ),
    },
    {
        "id": "explicit_wrapper_parse_and_forward",
        "region_id": "explicit_spawn_wrapper",
        "start_rva": 0x001690E6,
        "instruction_hex": (
            "6aff6aff83ec18c745fc000000008bcc8d45086aff6a00c741140f000000"
            "c741100000000050c60100e8bcefe9ff8bcee8a5feffff"
        ),
        "meaning": (
            "The explicit overload parses the supplied Point and calls the "
            "shared wrapper rather than replacing it with the invalid sentinel."
        ),
    },
    {
        "id": "common_wrapper_to_spawn",
        "region_id": "common_spawn_wrapper",
        "start_rva": 0x00169071,
        "instruction_hex": (
            "8bcfc745f00f000000ff7520c745ec0000000056c645dc00e8a2fcffff"
        ),
        "meaning": (
            "The shared explicit-point wrapper forwards the parsed pawn and "
            "point to the central SpawnPawn body."
        ),
    },
    {
        "id": "enemy_board_add_branch",
        "region_id": "spawn_pawn",
        "start_rva": 0x00168F61,
        "instruction_hex": (
            "83beb0000000017407e8c1040000eb2d8d45dc50e8465900006a008bce"
            "e81dd50c006a018bcee864e60c00"
        ),
        "meaning": (
            "The ordinary non-special path sends native team-field value 1 "
            "through Board pawn admission before applying spawn state."
        ),
    },
    {
        "id": "invalid_point_select_and_commit",
        "region_id": "board_add_pawn",
        "start_rva": 0x0016E91B,
        "instruction_hex": (
            "8b038bcbff7514ff75108b4008ffd084c07519568d45b08bcb50e856410000"
            "8b08894d108b4004894514eb068b45148b4d1050518bcee8ca190c00"
        ),
        "meaning": (
            "Board admission tests the supplied Point, calls the standard "
            "coordinate selector only when invalid, then passes the resulting "
            "Point to Pawn SetSpace."
        ),
    },
    {
        "id": "pawn_space_fields_commit",
        "region_id": "pawn_set_space",
        "start_rva": 0x0023029D,
        "instruction_hex": (
            "8b86ec0800008986f40800008b86f00800008986f80800008b45088986ec08"
            "00008b450c8986f0080000c686810f000000"
        ),
        "meaning": (
            "SetSpace preserves the previous point, writes the new x/y to "
            "pawn+0x8ec/+0x8f0, and clears the pending-space flag."
        ),
    },
    {
        "id": "block_spawn_tile_write",
        "region_id": "block_spawn",
        "start_rva": 0x0016C140,
        "instruction_hex": (
            "558bec83ec088d450881c158740000508d45f850e8e75ff6ff8b45f88b4d10"
            "8948188be55dc20c00"
        ),
        "meaning": (
            "BlockSpawn resolves the tile and writes the requested block value "
            "to tile+0x18 before returning."
        ),
    },
    {
        "id": "orchestrator_board_update",
        "region_id": "primary_orchestrator",
        "start_rva": 0x0018B0DE,
        "instruction_hex": "8b4e04e8eaf7fdff",
        "meaning": "The primary orchestrator runs the Board master update.",
    },
    {
        "id": "orchestrator_phase_transition",
        "region_id": "primary_orchestrator",
        "start_rva": 0x0018B167,
        "instruction_hex": "8bcee862e0ffff",
        "meaning": (
            "The same orchestrator calls phase transition only later in the "
            "same pass."
        ),
    },
)


DIRECT_EDGE_SPECS = (
    {
        "id": "explicit_to_common_wrapper",
        "source_region": "explicit_spawn_wrapper",
        "from_rva": 0x00169116,
        "instruction_hex": "e8a5feffff",
        "target_id": "common_spawn_wrapper",
        "target_rva": 0x00168FC0,
    },
    {
        "id": "common_wrapper_to_spawn_pawn",
        "source_region": "common_spawn_wrapper",
        "from_rva": 0x00169089,
        "instruction_hex": "e8a2fcffff",
        "target_id": "spawn_pawn",
        "target_rva": 0x00168D30,
    },
    {
        "id": "implicit_wrapper_to_spawn_pawn",
        "source_region": "implicit_spawn_wrapper",
        "from_rva": 0x0016915D,
        "instruction_hex": "e8cefbffff",
        "target_id": "spawn_pawn",
        "target_rva": 0x00168D30,
    },
    {
        "id": "spawn_special_to_board_add_pawn",
        "source_region": "spawn_pawn",
        "from_rva": 0x00168D7C,
        "instruction_hex": "e83f5b0000",
        "target_id": "board_add_pawn",
        "target_rva": 0x0016E8C0,
    },
    {
        "id": "spawn_terrain_three_to_board_add_pawn",
        "source_region": "spawn_pawn",
        "from_rva": 0x00168DC0,
        "instruction_hex": "e8fb5a0000",
        "target_id": "board_add_pawn",
        "target_rva": 0x0016E8C0,
    },
    {
        "id": "spawn_enemy_to_board_add_pawn",
        "source_region": "spawn_pawn",
        "from_rva": 0x00168F75,
        "instruction_hex": "e846590000",
        "target_id": "board_add_pawn",
        "target_rva": 0x0016E8C0,
    },
    {
        "id": "board_add_pawn_to_selector",
        "source_region": "board_add_pawn",
        "from_rva": 0x0016E935,
        "instruction_hex": "e856410000",
        "target_id": "spawn_coordinate_selector",
        "target_rva": 0x00172A90,
    },
    {
        "id": "board_add_pawn_to_set_space",
        "source_region": "board_add_pawn",
        "from_rva": 0x0016E951,
        "instruction_hex": "e8ca190c00",
        "target_id": "pawn_set_space_entry",
        "target_rva": 0x00230320,
    },
    {
        "id": "pawn_set_space_entry_to_body",
        "source_region": "pawn_set_space_entry",
        "from_rva": 0x0023032E,
        "instruction_hex": "e87dfeffff",
        "target_id": "pawn_set_space",
        "target_rva": 0x002301B0,
    },
    {
        "id": "orchestrator_to_board_master_update",
        "source_region": "primary_orchestrator",
        "from_rva": 0x0018B0E1,
        "instruction_hex": "e8eaf7fdff",
        "target_id": "board_master_update",
        "target_rva": 0x0016A8D0,
    },
    {
        "id": "orchestrator_to_phase_transition",
        "source_region": "primary_orchestrator",
        "from_rva": 0x0018B169,
        "instruction_hex": "e862e0ffff",
        "target_id": "phase_transition",
        "target_rva": 0x001891D0,
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


def _file_backed_bytes(
    image: Any,
    data: bytes,
    rva: int,
    size: int,
    expected_section: str,
) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise FinalCaveStartupSpawnOrderError(
            f"RVA 0x{rva:08x} is not contiguous file-backed data"
        )
    section = next(
        (
            candidate
            for candidate in image.sections
            if candidate.virtual_address <= rva
            and rva + size <= candidate.virtual_address + candidate.raw_size
        ),
        None,
    )
    if section is None or section.name != expected_section:
        raise FinalCaveStartupSpawnOrderError(
            f"RVA 0x{rva:08x} is not wholly in {expected_section}"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise FinalCaveStartupSpawnOrderError(
            f"RVA 0x{rva:08x} is not an E8 rel32 call"
        )
    delta = struct.unpack_from("<i", encoded, 1)[0]
    return (rva + 5 + delta) & 0xFFFFFFFF


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


def _expected_data_anchors() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "evidence_class": "fact",
            "rva": f"0x{spec['rva']:08x}",
            "size": len(spec["data"]),
            "sha256": hashlib.sha256(spec["data"]).hexdigest(),
            "section": spec["section"],
            "meaning": spec["meaning"],
        }
        for spec in DATA_ANCHOR_SPECS
    ]


def _expected_windows() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region_id": spec["region_id"],
            "start_rva": f"0x{spec['start_rva']:08x}",
            "size": len(bytes.fromhex(spec["instruction_hex"])),
            "sha256": hashlib.sha256(
                bytes.fromhex(spec["instruction_hex"])
            ).hexdigest(),
            "instruction_hex": spec["instruction_hex"],
            "evidence_class": "fact",
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


def _contracts() -> dict[str, Any]:
    return {
        "source_relative_order": [
            "optional explicit pre-bomb SpawnPawn at bomb_loc",
            "mountain and pylon BlockSpawn writes while constructing one SkillEffect",
            "Board:AddEffect queues the combined startup effect",
            "boss identity draw and implicit SpawnPawn",
            "BaseStart SetupDiffMod",
            "ordinary NextPawn and implicit SpawnPawn calls",
            "BaseStart return",
            "earliest eligible later Board effect dispatch",
        ],
        "spawn_overloads": {
            "lua_name": "SpawnPawn",
            "implicit_wrapper_rva": "0x00169150",
            "implicit_point": [-1, -1],
            "explicit_wrapper_rva": "0x001690c0",
            "explicit_point_preserved": True,
            "both_reach_central_spawn_pawn": True,
        },
        "logical_admission": {
            "invalid_point_calls_standard_selector": True,
            "selector_rva": "0x00172a90",
            "selected_point_passed_to_set_space": True,
            "current_space_x_offset": "pawn+0x8ec",
            "current_space_y_offset": "pawn+0x8f0",
            "commit_is_synchronous": True,
        },
        "spawn_blocking": {
            "lua_name": "BlockSpawn",
            "native_wrapper_rva": "0x0016c140",
            "tile_field_offset": "+0x18",
            "write_is_synchronous": True,
            "writes_precede_boss_and_ordinary_selector_calls": True,
        },
        "scheduler_order": {
            "board_master_update_call_rva": "0x0018b0e1",
            "phase_transition_call_rva": "0x0018b169",
            "board_update_precedes_phase_transition": True,
            "second_board_update_after_transition_same_pass": False,
            "startup_effect_dispatch_same_orchestrator_pass": False,
        },
        "semantic_boundary": {
            "boss_and_ordinary_logical_admission_before_startup_effect_dispatch": True,
            "queued_mech_scripts_execute_before_enemy_admission": False,
            "queued_rock_pylon_bomb_impacts_execute_before_enemy_admission": False,
            "visual_animation_interleave_proven": False,
            "wall_clock_timing_proven": False,
        },
        "solver_handoff": {
            "current_policy": (
                "Keep the stage-change boundary and consume a fresh settled "
                "bridge state before solving Final Cave."
            ),
            "reason": (
                "Native call order is now exact, but incoming CRT state, "
                "concrete identities, coordinates, and UIDs are unavailable."
            ),
            "simulator_change_required": False,
        },
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "spawn_overloads_are_exact",
            "evidence_class": "inference",
            "claim": (
                "The exact registration windows bind the same SpawnPawn Lua "
                "name to distinct explicit-point and no-point wrappers. The "
                "no-point wrapper supplies (-1,-1); the explicit wrapper "
                "preserves its parsed Point; both reach the central native "
                "SpawnPawn body synchronously."
            ),
            "supports": [
                "spawn_pawn_name",
                "implicit_spawn_registration",
                "explicit_spawn_registration",
                "implicit_invalid_point",
                "explicit_wrapper_parse_and_forward",
                "common_wrapper_to_spawn",
            ],
        },
        {
            "id": "implicit_enemy_spawn_selects_and_commits_space",
            "evidence_class": "inference",
            "claim": (
                "For the source-defined boss and ordinary enemy pawns, native "
                "admission receives the invalid sentinel, calls the exact "
                "standard coordinate selector, and passes its Point to "
                "SetSpace. The pawn's logical x/y fields are written before "
                "Board:SpawnPawn returns."
            ),
            "supports": [
                "enemy_board_add_branch",
                "spawn_special_to_board_add_pawn",
                "spawn_terrain_three_to_board_add_pawn",
                "spawn_enemy_to_board_add_pawn",
                "invalid_point_select_and_commit",
                "board_add_pawn_to_selector",
                "board_add_pawn_to_set_space",
                "pawn_space_fields_commit",
                "spawn_coordinate_paths",
            ],
            "limitations": [
                "Concrete candidates, RNG state, selected points, and UIDs are not recovered."
            ],
        },
        {
            "id": "spawn_blocks_precede_implicit_selection",
            "evidence_class": "inference",
            "claim": (
                "Each cave mountain and pylon BlockSpawn call writes its tile "
                "field synchronously while StartMission constructs the effect. "
                "Those writes have completed before the later boss and ordinary "
                "implicit selector calls; they are not delayed with the dropper "
                "records."
            ),
            "supports": [
                "scripts/missions/final/mission_final_two.lua",
                "block_spawn_name",
                "block_spawn_registration",
                "block_spawn_tile_write",
            ],
        },
        {
            "id": "logical_spawns_precede_startup_effect_dispatch",
            "evidence_class": "inference",
            "claim": (
                "The primary orchestrator has already completed its only Board "
                "master update before it enters phase transition and BaseStart. "
                "Cave StartMission queues one combined effect, then admits the "
                "boss; BaseStart later admits the ordinary starting pawns. "
                "Their identities and logical spaces are therefore committed "
                "before any queued Mech SetSpace script or rock, pylon, or bomb "
                "dropper from that effect can dispatch."
            ),
            "supports": [
                "final_cave_startup",
                "final_cave_replacement",
                "final_cave_replacement_cadence",
                "orchestrator_board_update",
                "orchestrator_phase_transition",
                "implicit_enemy_spawn_selects_and_commits_space",
            ],
            "limitations": [
                "Later visual spawn animations and effect presentation may overlap; their wall-clock interleave is not inferred."
            ],
        },
        {
            "id": "startup_rng_order_is_narrower",
            "evidence_class": "inference",
            "claim": (
                "The boss identity draw precedes its synchronous coordinate "
                "selection. Each ordinary NextPawn result is likewise obtained "
                "before that pawn's selector call. Queued startup effects do "
                "not consume their later execution-time work between those "
                "identity and placement calls."
            ),
            "supports": [
                "scripts/missions/missions.lua",
                "scripts/missions/final/mission_final_two.lua",
                "logical_spawns_precede_startup_effect_dispatch",
            ],
            "limitations": [
                "Nested NextPawn draws, incoming shared CRT state, and concrete outputs remain unknown."
            ],
        },
        {
            "id": "solver_boundary",
            "evidence_class": "inference",
            "claim": (
                "No Rust semantic change is justified. The existing stage-change "
                "handoff waits for a fresh settled bridge state, which already "
                "contains the concrete boss, ordinary pawns, Mech positions, "
                "terrain, pylons, and bomb after presentation settles."
            ),
            "supports": [
                "logical_spawns_precede_startup_effect_dispatch",
                "startup_rng_order_is_narrower",
            ],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "incoming_startup_rng_state",
            "question": "What shared CRT state enters the post-map cave startup draws?",
            "static_status": (
                "Call order is narrower, but timing-dependent upstream consumers "
                "and the incoming state are not ordinary bridge fields."
            ),
            "next_evidence": "Deliver selector-time native state or control every upstream draw.",
        },
        {
            "id": "concrete_spawn_identities_and_coordinates",
            "question": "Which NextPawn results and selected coordinates occur in one startup?",
            "static_status": (
                "Identity-before-coordinate order and the selector path are exact; "
                "concrete RNG results and callback-time candidate vectors are not."
            ),
            "next_evidence": "Use a build-keyed settled read or a matched startup trace.",
        },
        {
            "id": "startup_visual_interleave",
            "question": "How do spawn animations interleave visually with queued startup records?",
            "static_status": (
                "Logical admission before effect dispatch is exact; rendering, "
                "animation overlap, frame cadence, and wall-clock timing are not."
            ),
            "next_evidence": "Capture timestamped presentation telemetry only if UI timing matters.",
        },
        {
            "id": "startup_uid_allocation",
            "question": "Which UIDs are assigned to the boss, ordinary pawns, pylons, and bomb?",
            "static_status": "Logical construction order is known; allocator state is not.",
            "next_evidence": "Read the fresh settled bridge state after startup.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do macOS and other Windows builds use the same admission order?",
            "static_status": "This map is keyed only to Windows build 13725832.",
            "next_evidence": "Produce independent build-keyed boundary maps.",
        },
    ]


def _summary() -> dict[str, Any]:
    return {
        "lua_source_count": len(LUA_SOURCE_SPECS),
        "dependency_count": 4,
        "region_count": len(REGION_SPECS),
        "data_anchor_count": len(DATA_ANCHOR_SPECS),
        "control_window_count": len(CONTROL_WINDOW_SPECS),
        "direct_edge_count": len(DIRECT_EDGE_SPECS),
        "finding_count": len(_findings()),
        "unresolved_count": len(_unresolved()),
        "spawn_overloads_bound": True,
        "implicit_selector_and_space_commit_proven": True,
        "synchronous_spawn_block_write_proven": True,
        "logical_admission_before_effect_dispatch_proven": True,
        "visual_animation_interleave_proven": False,
        "concrete_rng_outputs_proven": False,
        "simulator_change_required": False,
    }


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
            "scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION_SHA256,
        },
        "sources": {
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
            "lua_files": [
                {
                    "path": spec["path"],
                    "size": spec["size"],
                    "sha256": spec["sha256"],
                    "symbols": spec["symbols"],
                    "evidence_class": "fact",
                }
                for spec in LUA_SOURCE_SPECS
            ],
        },
        "dependencies": [
            {
                "id": "final_cave_startup",
                "artifact": (
                    "data/observatory/native/windows_build_13725832_"
                    "31fe35265598_final_cave_startup.json"
                ),
                "artifact_sha256": STARTUP_ARTIFACT_SHA256,
                "role": (
                    "Pins map/phase/BaseStart order, exact startup sources, "
                    "map zones, and the source-level RNG skeleton."
                ),
            },
            {
                "id": "spawn_coordinate_paths",
                "artifact": (
                    "data/observatory/native/windows_build_13725832_"
                    "31fe35265598_spawn_coordinate_paths.json"
                ),
                "artifact_sha256": SPAWN_PATH_ARTIFACT_SHA256,
                "role": (
                    "Pins the standard coordinate selector, ordinary/fallback "
                    "modulo semantics, and upstream scheduler distinction."
                ),
            },
            {
                "id": "final_cave_replacement",
                "artifact": (
                    "data/observatory/native/windows_build_13725832_"
                    "31fe35265598_final_cave_replacement.json"
                ),
                "artifact_sha256": REPLACEMENT_ARTIFACT_SHA256,
                "role": (
                    "Pins immediate AddDropper record copying, AddEffect queue "
                    "insertion, and later dropper dispatch/materialization."
                ),
            },
            {
                "id": "final_cave_replacement_cadence",
                "artifact": (
                    "data/observatory/native/windows_build_13725832_"
                    "31fe35265598_final_cave_replacement_cadence.json"
                ),
                "artifact_sha256": CADENCE_ARTIFACT_SHA256,
                "role": (
                    "Pins effect dispatch through the later Board scheduler and "
                    "active-animation settlement semantics."
                ),
            },
        ],
        "supersedes": {
            "artifact": (
                "data/observatory/native/windows_build_13725832_"
                "31fe35265598_final_cave_startup.json"
            ),
            "resolved_facets": [
                "native_spawn_overload_binding",
                "implicit_spawn_selector_entry",
                "synchronous_logical_space_commit",
                "startup_spawn_admission_vs_effect_dispatch",
                "startup_space_damage_copying",
            ],
            "remaining_gap_ids": [item["id"] for item in _unresolved()],
        },
        "method": {
            "boundary_review": (
                "Focused Ghidra 12.1.3 registration, wrapper, call-graph, field-"
                "write, and primary-orchestrator review."
            ),
            "source_review": (
                "Exact shipped Lua hashes and checked lexical order join "
                "StartMission, BaseStart, SpawnPawns, BlockSpawn, and AddEffect."
            ),
            "limitations": [
                "Every native address applies only to the pinned Windows executable.",
                "Logical admission is distinct from visual spawn-animation settlement.",
                "Incoming RNG state, concrete identities, coordinates, and UIDs remain unknown.",
                "macOS and other executable builds require independent maps.",
            ],
        },
        "contracts": _contracts(),
        "regions": _expected_regions(),
        "data_anchors": _expected_data_anchors(),
        "control_windows": _expected_windows(),
        "direct_call_edges": _expected_edges(),
        "findings": _findings(),
        "unresolved": _unresolved(),
        "summary": _summary(),
    }


def _verify_lua_sources(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise FinalCaveStartupSpawnOrderError("content root is not a directory")
    contents: dict[str, bytes] = {}
    for spec in LUA_SOURCE_SPECS:
        source = root / Path(spec["path"])
        try:
            resolved = source.resolve(strict=True)
        except OSError as exc:
            raise FinalCaveStartupSpawnOrderError(
                f"missing Lua source {spec['path']}"
            ) from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise FinalCaveStartupSpawnOrderError(
                f"Lua source escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise FinalCaveStartupSpawnOrderError(
                f"Lua source is not a regular non-symlink file: {spec['path']}"
            )
        data = resolved.read_bytes()
        if (
            len(data) != spec["size"]
            or hashlib.sha256(data).hexdigest() != spec["sha256"]
        ):
            raise FinalCaveStartupSpawnOrderError(
                f"Lua source identity differs: {spec['path']}"
            )
        contents[spec["path"]] = data

    missions = contents["scripts/missions/missions.lua"]
    start = missions.index(b"function Mission:BaseStart()")
    end = missions.index(b"function Mission:AddDebris()", start)
    base_start = missions[start:end]
    if not (
        base_start.index(b"self:StartMission()")
        < base_start.index(b"self:SetupDiffMod()")
        < base_start.index(b"self:SpawnPawns(self:GetStartingPawns())")
    ):
        raise FinalCaveStartupSpawnOrderError("BaseStart source order differs")
    spawn_start = missions.index(b"function Mission:SpawnPawns(count)")
    spawn_end = missions.index(b"function Mission:GetDiffMod()", spawn_start)
    if missions[spawn_start:spawn_end].count(
        b"Board:SpawnPawn(self:NextPawn())"
    ) != 1:
        raise FinalCaveStartupSpawnOrderError("SpawnPawns source body differs")

    cave = contents["scripts/missions/final/mission_final_two.lua"]
    start = cave.index(b"function Mission_Final_Cave:StartMission()")
    end = cave.index(b"function Mission_Final_Cave:UpdateSpawning()", start)
    cave_start = cave[start:end]
    ordered = (
        b"Board:SpawnPawn(self:NextPawn(),bomb_loc)",
        b"Board:BlockSpawn(rock.loc,BLOCKED_TEMP)",
        b"Board:BlockSpawn(building.loc,BLOCKED_PERM)",
        b"Board:AddEffect(effect)",
        b"Board:SpawnPawn(random_element(self.BossList))",
    )
    positions = [cave_start.index(fragment) for fragment in ordered]
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        raise FinalCaveStartupSpawnOrderError("Cave StartMission source order differs")


def build_final_cave_startup_spawn_order_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build startup spawn-order boundary map."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise FinalCaveStartupSpawnOrderError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise FinalCaveStartupSpawnOrderError("executable identity differs")
    _verify_lua_sources(content_root)

    ranges: dict[str, tuple[int, int]] = {}
    for spec in REGION_SPECS:
        size = spec["end"] - spec["start"]
        try:
            body = _region_bytes(
                image, data, spec["start"], size, ".text", spec["id"]
            )
        except Exception as exc:
            raise FinalCaveStartupSpawnOrderError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise FinalCaveStartupSpawnOrderError(
                f"region {spec['id']} bytes differ"
            )
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise FinalCaveStartupSpawnOrderError(str(exc)) from exc

    for spec in DATA_ANCHOR_SPECS:
        actual = _file_backed_bytes(
            image, data, spec["rva"], len(spec["data"]), spec["section"]
        )
        if actual != spec["data"]:
            raise FinalCaveStartupSpawnOrderError(
                f"data anchor {spec['id']} differs"
            )

    region_specs = {spec["id"]: spec for spec in REGION_SPECS}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["instruction_hex"])
        start = spec["start_rva"]
        actual = _file_backed_bytes(image, data, start, len(encoded), ".text")
        if actual != encoded:
            raise FinalCaveStartupSpawnOrderError(
                f"control window {spec['id']} differs"
            )
        region = region_specs[spec["region_id"]]
        if not (region["start"] <= start < start + len(encoded) <= region["end"]):
            raise FinalCaveStartupSpawnOrderError(
                f"control window {spec['id']} escapes its region"
            )
        cursor = start
        while cursor < start + len(encoded):
            instruction = decoded[spec["region_id"]].get(cursor)
            if instruction is None:
                raise FinalCaveStartupSpawnOrderError(
                    f"control window {spec['id']} crosses undecoded bytes"
                )
            cursor += len(instruction[1])
        if cursor != start + len(encoded):
            raise FinalCaveStartupSpawnOrderError(
                f"control window {spec['id']} ends inside an instruction"
            )

    for spec in DIRECT_EDGE_SPECS:
        instruction = decoded[spec["source_region"]].get(spec["from_rva"])
        expected = bytes.fromhex(spec["instruction_hex"])
        if instruction is None or instruction[1] != expected:
            raise FinalCaveStartupSpawnOrderError(
                f"direct edge {spec['id']} bytes differ"
            )
        if _direct_target(spec["from_rva"], expected) != spec["target_rva"]:
            raise FinalCaveStartupSpawnOrderError(
                f"direct edge {spec['id']} target differs"
            )

    orchestrator_calls = [
        (rva, _direct_target(rva, encoded))
        for rva, (_, encoded) in decoded["primary_orchestrator"].items()
        if len(encoded) == 5 and encoded[0] == 0xE8
    ]
    board_calls = [
        rva for rva, target in orchestrator_calls if target == 0x0016A8D0
    ]
    phase_calls = [
        rva for rva, target in orchestrator_calls if target == 0x001891D0
    ]
    if board_calls != [0x0018B0E1] or phase_calls != [0x0018B169]:
        raise FinalCaveStartupSpawnOrderError(
            "primary orchestrator Board/phase call inventory differs"
        )
    if not board_calls[0] < phase_calls[0]:
        raise FinalCaveStartupSpawnOrderError(
            "primary orchestrator startup order differs"
        )
    return _expected_shape()


def validate_final_cave_startup_spawn_order_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping):
        raise FinalCaveStartupSpawnOrderError("spawn-order map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise FinalCaveStartupSpawnOrderError("spawn-order map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "spawn_overloads_bound": True,
        "implicit_selector_and_space_commit_proven": True,
        "logical_admission_before_effect_dispatch_proven": True,
        "visual_animation_interleave_proven": False,
        "concrete_rng_outputs_proven": False,
        "simulator_change_required": False,
    }


def validate_final_cave_startup_spawn_order_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject source, byte, address, or prose drift."""
    expected = build_final_cave_startup_spawn_order_map(executable, content_root)
    if dict(value) != expected:
        raise FinalCaveStartupSpawnOrderError(
            "spawn-order map differs from exact-build analysis"
        )
    result = validate_final_cave_startup_spawn_order_map_binding(value)
    result["status"] = "verified"
    return result


def encode_final_cave_startup_spawn_order_map(
    value: Mapping[str, Any],
) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
