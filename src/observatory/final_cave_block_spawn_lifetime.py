"""Reproduce the exact-build Final Cave spawn-block lifetime boundary.

This continuation joins the shipped Final Cave ``BlockSpawn`` calls to the
native block-value registrations, spawn predicate, per-player-turn cleanup,
and board reset.  It proves the ordinary lifetime of temporary and permanent
spawn blocks without claiming concrete startup RNG, presentation timing, or
terrain/dropper collision behavior.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.content_inventory import build_manifest
from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "final_cave_block_spawn_lifetime_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
BASE_SCRIPTS_INVENTORY_SPEC = {
    "path": (
        "data/observatory/inventories/windows_build_13725832_31fe35265598_"
        "post_native_boundaries_restore_20260822.json"
    ),
    "size": 125_456,
    "sha256": "4be0c9382ab38ec264dd4673180eedc0c20f826569f790219002c1a35dae9355",
    "scripts_file_count": 305,
    "scripts_byte_count": 15_967_494,
    "base_scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION_SHA256,
    "overlay_path": "scripts/modloader.lua",
    "accepted_overlay_files": [
        {
            "id": "restored_project_bridge",
            "size": 132_609,
            "sha256": (
                "8d765cb4d501f1cdc83a6423ad7c2f66e01d98844ec3e8afd1f3c099e4763c10"
            ),
        },
        {
            "id": "current_project_bridge",
            "size": 315_652,
            "sha256": (
                "f94fabbe75aad2463e08ab28bf052e31db95b7724f31adbfc002aa102675f1a2"
            ),
        },
    ],
}

# Preserve the published artifact's original overlay inventory while allowing
# later hash-reviewed project bridge revisions during exact-tree verification.
# This exception never weakens the other 304 scripts-entry comparisons.
POST_PUBLICATION_PROJECT_BRIDGE_OVERLAYS = (
    {
        "id": "mission_piston_v408_project_bridge",
        "size": 315_686,
        "sha256": (
            "5af8e809e6ed036084c84caed97f6a51a84785db2c2c0ee0c150da99adabf22d"
        ),
    },
)
STARTUP_SPAWN_ORDER_ARTIFACT_SHA256 = (
    "b798a97c582be31ffba3d173e00b24eefae32a9725d03fe7a2260ca1403214f4"
)
STARTUP_EFFECT_ORDER_ARTIFACT_SHA256 = (
    "a5290868718a0912c50c1caf914f7a6203d781d7a4b137352c9caf61c2c031df"
)


class FinalCaveBlockSpawnLifetimeError(RuntimeError):
    """Raised when the reviewed spawn-block lifetime map cannot be reproduced."""


LUA_SOURCE_SPEC = {
    "path": "scripts/missions/final/mission_final_two.lua",
    "size": 4_887,
    "sha256": "c8a8e40f512939c1f4fd0e0df416e5cbaec00c639e2985ad776e13c38735b17c",
    "symbols": [
        "Mission_Final_Cave:StartMission",
        "BLOCKED_TEMP",
        "BLOCKED_PERM",
    ],
}


REGION_SPECS = (
    {
        "id": "method_registration",
        "start": 0x0027A97C,
        "end": 0x0027A9C3,
        "sha256": "c926152802b24353d4a72f79ccdff985e7a243b4d65c22ecba890d6755d7f3e6",
        "basis": (
            "Instruction-aligned Ghidra 12.1.3 Luabind window registering "
            "BlockSpawn and ClearBlockSpawns."
        ),
    },
    {
        "id": "constant_registration",
        "start": 0x002809F1,
        "end": 0x00280AB7,
        "sha256": "b8a957b372bf1eab1815fa92704664ce8e8c0aa5d13cc896b6125c7033afea7c",
        "basis": (
            "Instruction-aligned Ghidra 12.1.3 Luabind window registering "
            "BLOCKED_NONE, BLOCKED_TEMP, and BLOCKED_PERM."
        ),
    },
    {
        "id": "tile_map_accessor",
        "start": 0x000D2140,
        "end": 0x000D21B1,
        "sha256": "cd9b47796453ecb67552f855fa3f17d44db4e419d01b37ec23b885e94f58a4d8",
        "basis": "Ghidra 12.1.3 Point-keyed map accessor body.",
    },
    {
        "id": "block_spawn",
        "start": 0x0016C140,
        "end": 0x0016C168,
        "sha256": "7784bee48dc7ca89bbfd29a64dd1fe2cfefe54a707d05f3ac6d5714b6d471b6b",
        "basis": "Ghidra 12.1.3 Board BlockSpawn binding body.",
    },
    {
        "id": "clear_block_spawns",
        "start": 0x0016C170,
        "end": 0x0016C1F8,
        "sha256": "c2a7ed8009fbb20870e34181221eb03e1653e41186da776bc6a343a8d754c19f",
        "basis": "Ghidra 12.1.3 Board ClearBlockSpawns binding body.",
    },
    {
        "id": "phase_tile_sweep",
        "start": 0x00168C20,
        "end": 0x00168D29,
        "sha256": "42896d726c2d1cccd25eff5d875e5837b5eb540f418f18b4209ea8e41569a11e",
        "basis": (
            "Ghidra 12.1.3 phase-mode tile sweep containing the sole native "
            "direct ClearBlockSpawns call."
        ),
    },
    {
        "id": "spawn_coordinate_selector",
        "start": 0x00172A90,
        "end": 0x00172EF6,
        "sha256": "9746df5a768534c54108600528bce8e0fd152d41e322bf0907dc92a434148904",
        "basis": "Previously reviewed exact standard spawn-coordinate selector.",
    },
    {
        "id": "spawn_validity",
        "start": 0x00172F00,
        "end": 0x001732C2,
        "sha256": "ece436016741d70821025fcc00b3e30965480a2b99a00960449e9262592956bb",
        "basis": "Ghidra 12.1.3 native spawn-coordinate validity predicate.",
    },
    {
        "id": "board_reset",
        "start": 0x001671E0,
        "end": 0x001673C5,
        "sha256": "c042e0b245017ee8fa1ca38bb80ce4d9d864acf1b52a18ae685ea577116e740a",
        "basis": "Ghidra 12.1.3 Board map/reset body.",
    },
    {
        "id": "phase_transition",
        "start": 0x001891D0,
        "end": 0x0018964D,
        "sha256": "3a5b364d9af48610bb07f8e44d5cb9ddb4051f4cb4a5fa0ad0db8eb51522073f",
        "basis": "Previously reviewed exact phase-transition body.",
    },
    {
        "id": "phase_driver",
        "start": 0x0018A2C0,
        "end": 0x0018A955,
        "sha256": "903ca7d14ba5317753901f70ec24acfb31ea44e947d3ebce3246651897bc2b90",
        "basis": "Ghidra 12.1.3 battle phase driver body.",
    },
)


DATA_ANCHOR_SPECS = (
    {
        "id": "block_spawn_name",
        "rva": 0x00438964,
        "section": ".rdata",
        "data": b"BlockSpawn\0",
        "meaning": "Registered Board method name.",
    },
    {
        "id": "clear_block_spawns_name",
        "rva": 0x00438994,
        "section": ".rdata",
        "data": b"ClearBlockSpawns\0",
        "meaning": "Registered Board cleanup method name.",
    },
    {
        "id": "blocked_none_name",
        "rva": 0x00439B18,
        "section": ".rdata",
        "data": b"BLOCKED_NONE\0",
        "meaning": "Registered no-block global name.",
    },
    {
        "id": "blocked_temp_name",
        "rva": 0x00439B08,
        "section": ".rdata",
        "data": b"BLOCKED_TEMP\0",
        "meaning": "Registered temporary-block global name.",
    },
    {
        "id": "blocked_perm_name",
        "rva": 0x00439B34,
        "section": ".rdata",
        "data": b"BLOCKED_PERM\0",
        "meaning": "Registered permanent-block global name.",
    },
    {
        "id": "blocked_none_value",
        "rva": 0x004156EC,
        "section": ".rdata",
        "data": struct.pack("<I", 0),
        "meaning": "Registered BLOCKED_NONE integer storage.",
    },
    {
        "id": "blocked_temp_value",
        "rva": 0x004156D0,
        "section": ".rdata",
        "data": struct.pack("<I", 1),
        "meaning": "Registered BLOCKED_TEMP integer storage.",
    },
    {
        "id": "blocked_perm_value",
        "rva": 0x004156D4,
        "section": ".rdata",
        "data": struct.pack("<I", 2),
        "meaning": "Registered BLOCKED_PERM integer storage.",
    },
    {
        "id": "player_turn_ui",
        "rva": 0x0042F430,
        "section": ".rdata",
        "data": b"/ui/battle/player_turn\0",
        "meaning": "Player-phase presentation anchor.",
    },
    {
        "id": "end_turn_ui",
        "rva": 0x0042F92C,
        "section": ".rdata",
        "data": b"/ui/battle/end_turn\0",
        "meaning": "End-turn phase presentation anchor.",
    },
    {
        "id": "phase_dispatch_entries_zero_one",
        "rva": 0x0018A958,
        "section": ".text",
        "data": struct.pack(
            "<II",
            EXPECTED_IMAGE_BASE + 0x0018A48F,
            EXPECTED_IMAGE_BASE + 0x0018A770,
        ),
        "meaning": (
            "Phase-driver jump-table entries bind phase zero to the player "
            "branch and phase one to the end-turn branch."
        ),
    },
)


CONSTANT_BINDING_SPECS = (
    {
        "id": "blocked_none",
        "name_anchor": "blocked_none_name",
        "name_reference_rva": 0x00280A09,
        "name_instruction_hex": "68189b8300",
        "value_anchor": "blocked_none_value",
        "value_reference_rva": 0x00280A1C,
        "value_instruction_hex": "68ec568100",
        "value": 0,
    },
    {
        "id": "blocked_temp",
        "name_anchor": "blocked_temp_name",
        "name_reference_rva": 0x00280A4B,
        "name_instruction_hex": "68089b8300",
        "value_anchor": "blocked_temp_value",
        "value_reference_rva": 0x00280A5E,
        "value_instruction_hex": "68d0568100",
        "value": 1,
    },
    {
        "id": "blocked_perm",
        "name_anchor": "blocked_perm_name",
        "name_reference_rva": 0x00280A8D,
        "name_instruction_hex": "68349b8300",
        "value_anchor": "blocked_perm_value",
        "value_reference_rva": 0x00280AA0,
        "value_instruction_hex": "68d4568100",
        "value": 2,
    },
)


METHOD_BINDING_SPECS = (
    {
        "id": "block_spawn",
        "name_anchor": "block_spawn_name",
        "name_reference_rva": 0x0027A992,
        "name_instruction_hex": "6864898300",
        "wrapper_region": "block_spawn",
        "wrapper_rva": 0x0016C140,
        "wrapper_reference_rva": 0x0027A97C,
        "wrapper_instruction_hex": "c745e840c15600",
    },
    {
        "id": "clear_block_spawns",
        "name_anchor": "clear_block_spawns_name",
        "name_reference_rva": 0x0027A9B7,
        "name_instruction_hex": "6894898300",
        "wrapper_region": "clear_block_spawns",
        "wrapper_rva": 0x0016C170,
        "wrapper_reference_rva": 0x0027A9A1,
        "wrapper_instruction_hex": "c745e870c15600",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "blocked_none_registration",
        "region_id": "constant_registration",
        "start_rva": 0x002809F1,
        "instruction_hex": (
            "8d8d78fcffffe8c4b9deff8bd38d8d70fcffffe8d7b9deff"
            "68189b83008d8df0f4ffff518bc8e834fedcff68ec5681008bc8"
            "e868fedcff8d8df0f4ffffe8adebdcff"
        ),
        "meaning": "BLOCKED_NONE is bound to the integer stored as zero.",
    },
    {
        "id": "blocked_temp_registration",
        "region_id": "constant_registration",
        "start_rva": 0x00280A33,
        "instruction_hex": (
            "8d8d70fcffffe882b9deff8bd38d8d68fcffffe895b9deff"
            "68089b83008d8de4f4ffff518bc8e8f2fddcff68d05681008bc8"
            "e826fedcff8d8de4f4ffffe86bebdcff"
        ),
        "meaning": "BLOCKED_TEMP is bound to the integer stored as one.",
    },
    {
        "id": "blocked_perm_registration",
        "region_id": "constant_registration",
        "start_rva": 0x00280A75,
        "instruction_hex": (
            "8d8d68fcffffe840b9deff8bd38d8d60fcffffe853b9deff"
            "68349b83008d8dd8f4ffff518bc8e8b0fddcff68d45681008bc8"
            "e8e4fddcff8d8dd8f4ffffe829ebdcff"
        ),
        "meaning": "BLOCKED_PERM is bound to the integer stored as two.",
    },
    {
        "id": "block_spawn_tile_write",
        "region_id": "block_spawn",
        "start_rva": 0x0016C140,
        "instruction_hex": (
            "558bec83ec088d450881c158740000508d45f850e8e75ff6ff"
            "8b45f88b4d108948188be55dc20c00"
        ),
        "meaning": (
            "BlockSpawn resolves Board+0x7458 by Point and synchronously writes "
            "the supplied integer to the map node's +0x18 value."
        ),
    },
    {
        "id": "clear_only_temporary",
        "region_id": "clear_block_spawns",
        "start_rva": 0x0016C18F,
        "instruction_hex": (
            "8bb358740000578b068945fc0f1f4400003bc674418b4810894de8"
            "8b4814894dec8b40188945f083f801751d8d45e8508d45f450"
            "8d8b58740000e8725ff6ff8b45f4c74018000000008d4dfc"
            "e8501df0ff8b45fcebbb"
        ),
        "meaning": (
            "ClearBlockSpawns visits every stored entry, changes only value "
            "one to zero, and leaves all other values untouched."
        ),
    },
    {
        "id": "phase_sweep_cleanup_gate",
        "region_id": "phase_tile_sweep",
        "start_rva": 0x00168D14,
        "instruction_hex": "837d080175078bcbe84f340000",
        "meaning": (
            "The phase tile sweep calls ClearBlockSpawns only when its mode "
            "argument equals one."
        ),
    },
    {
        "id": "spawn_rejects_both_block_values",
        "region_id": "spawn_validity",
        "start_rva": 0x00172F6A,
        "instruction_hex": (
            "8d4d10518d4dec518d8f58740000e8c3f1f5ff8b45ec83781802"
            "0f84220300008d4510508d45ec508d8f58740000e8a3f1f5ff"
            "8b45ec837818010f8402030000"
        ),
        "meaning": (
            "Spawn validity reads Board+0x7458 and rejects value two and value "
            "one before its remaining tile checks."
        ),
    },
    {
        "id": "player_phase_runs_cleanup",
        "region_id": "phase_driver",
        "start_rva": 0x0018A4C9,
        "instruction_hex": "8bcfe8607000008b4f046a01e846e7fdff",
        "meaning": (
            "The accepted player-phase branch performs its turn setup and "
            "passes mode one to the phase tile sweep."
        ),
    },
    {
        "id": "player_phase_ui_after_cleanup",
        "region_id": "phase_driver",
        "start_rva": 0x0018A550,
        "instruction_hex": "c645fc028bcc6830f48200e8b0d8e7ff",
        "meaning": (
            "The player-turn UI anchor is constructed later in the same phase "
            "branch, after the mode-one cleanup call."
        ),
    },
    {
        "id": "end_turn_phase_skips_cleanup",
        "region_id": "phase_driver",
        "start_rva": 0x0018A77E,
        "instruction_hex": "8b4f046a06e898e4fdff",
        "meaning": (
            "The end-turn phase passes mode six to the tile sweep, which fails "
            "the mode-one cleanup gate."
        ),
    },
    {
        "id": "end_turn_ui_anchor",
        "region_id": "phase_driver",
        "start_rva": 0x0018A801,
        "instruction_hex": "c645fc0e8bcc682cf98200e8ffd5e7ff",
        "meaning": "The reviewed mode-six branch is the end-turn UI branch.",
    },
    {
        "id": "stage_start_requests_phase_one",
        "region_id": "phase_transition",
        "start_rva": 0x001895E0,
        "instruction_hex": "6a018bcbe8d70c0000",
        "meaning": (
            "After board and mission initialization, phase transition requests "
            "phase one rather than the player phase."
        ),
    },
    {
        "id": "board_reset_zeros_every_tile",
        "region_id": "board_reset",
        "start_rva": 0x0016725E,
        "instruction_hex": (
            "8b46508d8e5874000089465433db894dfc9033ff8d45e8895de850"
            "897dec e86fa6f6ff8b4dfc8bf03b3174118b46103bd875033b7e14"
            "0f9cc084c074298d45e88945f88d45f8515051e8f4b9f6ff8b4dfc"
            "5083c01050568d45f450e822baf6ff8b75f48b4dfc47c7461800000000"
            "83ff087ca14383fb087c99"
        ).replace(" ", ""),
        "meaning": (
            "The Board reset path materializes all 8x8 entries and writes zero "
            "to each value, bounding permanent blocks to the current Board."
        ),
    },
)


DIRECT_EDGE_SPECS = (
    ("block_spawn_to_tile_map", "block_spawn", 0x0016C154, "e8e75ff6ff", "tile_map_accessor", 0x000D2140),
    ("clear_to_tile_map", "clear_block_spawns", 0x0016C1C9, "e8725ff6ff", "tile_map_accessor", 0x000D2140),
    ("phase_sweep_to_clear", "phase_tile_sweep", 0x00168D1C, "e84f340000", "clear_block_spawns", 0x0016C170),
    ("spawn_validity_to_tile_map_perm", "spawn_validity", 0x00172F78, "e8c3f1f5ff", "tile_map_accessor", 0x000D2140),
    ("spawn_validity_to_tile_map_temp", "spawn_validity", 0x00172F98, "e8a3f1f5ff", "tile_map_accessor", 0x000D2140),
    ("selector_validity_a", "spawn_coordinate_selector", 0x00172B84, "e877030000", "spawn_validity", 0x00172F00),
    ("selector_validity_b", "spawn_coordinate_selector", 0x00172C33, "e8c8020000", "spawn_validity", 0x00172F00),
    ("selector_validity_c", "spawn_coordinate_selector", 0x00172D15, "e8e6010000", "spawn_validity", 0x00172F00),
    ("player_phase_to_tile_sweep", "phase_driver", 0x0018A4D5, "e846e7fdff", "phase_tile_sweep", 0x00168C20),
    ("end_turn_phase_to_tile_sweep", "phase_driver", 0x0018A783, "e898e4fdff", "phase_tile_sweep", 0x00168C20),
    ("stage_start_to_phase_driver", "phase_transition", 0x001895E4, "e8d70c0000", "phase_driver", 0x0018A2C0),
)


DIRECT_CALLSITE_CATALOG_SPECS = (
    {
        "target_region": "clear_block_spawns",
        "target_rva": 0x0016C170,
        "callsites": [0x00168D1C],
        "meaning": "The phase tile sweep is the sole raw E8 caller of ClearBlockSpawns.",
    },
    {
        "target_region": "phase_tile_sweep",
        "target_rva": 0x00168C20,
        "callsites": [0x0018A4D5, 0x0018A783],
        "meaning": "Only the player and end-turn phase branches call the reviewed sweep.",
    },
    {
        "target_region": "spawn_validity",
        "target_rva": 0x00172F00,
        "callsites": [
            0x00160C1A,
            0x00160D8C,
            0x00160E6F,
            0x00160F5B,
            0x00168E7C,
            0x001722D3,
            0x00172B84,
            0x00172C33,
            0x00172D15,
        ],
        "meaning": (
            "The complete raw E8 catalog includes all nine reviewed native "
            "spawn-validity callers; three lie in the standard selector."
        ),
    },
)


FIELD_REFERENCE_CATALOG = [
    {
        "function_rva": "0x0015f150",
        "instruction_rvas": ["0x0015f649"],
        "role": "Board constructor initializes the Point-keyed map.",
    },
    {
        "function_rva": "0x0015f8b0",
        "instruction_rvas": ["0x0015f9d6", "0x0015f9dc", "0x0015f9f2"],
        "role": "Board destruction releases the map.",
    },
    {
        "function_rva": "0x00163d80",
        "instruction_rvas": ["0x001654b6"],
        "role": "Board archive/load handling enumerates nonzero map entries.",
    },
    {
        "function_rva": "0x001671e0",
        "instruction_rvas": ["0x00167261"],
        "role": "Board reset writes zero across the 8x8 map.",
    },
    {
        "function_rva": "0x0016c140",
        "instruction_rvas": ["0x0016c149"],
        "role": "BlockSpawn writes the requested value.",
    },
    {
        "function_rva": "0x0016c170",
        "instruction_rvas": ["0x0016c18f", "0x0016c1c3"],
        "role": "ClearBlockSpawns enumerates and selectively clears temporary values.",
    },
    {
        "function_rva": "0x00172f00",
        "instruction_rvas": ["0x00172f72", "0x00172f92"],
        "role": "Spawn validity rejects temporary and permanent values.",
    },
]


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_backed_bytes(
    image: Any,
    data: bytes,
    rva: int,
    size: int,
    expected_section: str,
) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise FinalCaveBlockSpawnLifetimeError(
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
        raise FinalCaveBlockSpawnLifetimeError(
            f"RVA 0x{rva:08x} is not wholly in {expected_section}"
        )
    return data[offset : offset + size]


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise FinalCaveBlockSpawnLifetimeError(
            f"RVA 0x{rva:08x} is not file-backed"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise FinalCaveBlockSpawnLifetimeError(
            f"RVA 0x{rva:08x} is not an E8 rel32 call"
        )
    delta = struct.unpack_from("<i", encoded, 1)[0]
    return (rva + 5 + delta) & 0xFFFFFFFF


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
        for offset in range(max(0, len(raw) - 4)):
            if raw[offset] != 0xE8:
                continue
            site = section.virtual_address + offset
            target = _direct_target(site, raw[offset : offset + 5])
            if target in hits:
                hits[target].append(site)
    return hits


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
            "boundary_basis": spec["basis"],
        }
        for spec in REGION_SPECS
    ]


def _expected_data_anchors() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "rva": f"0x{spec['rva']:08x}",
            "section": spec["section"],
            "size": len(spec["data"]),
            "sha256": hashlib.sha256(spec["data"]).hexdigest(),
            "hex": spec["data"].hex(),
            "meaning": spec["meaning"],
            "evidence_class": "fact",
        }
        for spec in DATA_ANCHOR_SPECS
    ]


def _expected_constant_bindings() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region_id": "constant_registration",
            "name_anchor": spec["name_anchor"],
            "name_reference_rva": f"0x{spec['name_reference_rva']:08x}",
            "name_instruction_hex": spec["name_instruction_hex"],
            "value_anchor": spec["value_anchor"],
            "value_reference_rva": f"0x{spec['value_reference_rva']:08x}",
            "value_instruction_hex": spec["value_instruction_hex"],
            "registered_value": spec["value"],
            "evidence_class": "fact",
        }
        for spec in CONSTANT_BINDING_SPECS
    ]


def _expected_method_bindings() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region_id": "method_registration",
            "name_anchor": spec["name_anchor"],
            "name_reference_rva": f"0x{spec['name_reference_rva']:08x}",
            "name_instruction_hex": spec["name_instruction_hex"],
            "wrapper_region": spec["wrapper_region"],
            "wrapper_rva": f"0x{spec['wrapper_rva']:08x}",
            "wrapper_reference_rva": f"0x{spec['wrapper_reference_rva']:08x}",
            "wrapper_instruction_hex": spec["wrapper_instruction_hex"],
            "evidence_class": "fact",
        }
        for spec in METHOD_BINDING_SPECS
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
            "meaning": spec["meaning"],
            "evidence_class": "fact",
        }
        for spec in CONTROL_WINDOW_SPECS
    ]


def _expected_edges() -> list[dict[str, Any]]:
    return [
        {
            "id": edge_id,
            "source_region": source_region,
            "from_rva": f"0x{from_rva:08x}",
            "instruction_hex": instruction_hex,
            "target_region": target_region,
            "target_rva": f"0x{target_rva:08x}",
            "evidence_class": "fact",
        }
        for (
            edge_id,
            source_region,
            from_rva,
            instruction_hex,
            target_region,
            target_rva,
        ) in DIRECT_EDGE_SPECS
    ]


def _expected_callsite_catalog() -> list[dict[str, Any]]:
    return [
        {
            "target_region": spec["target_region"],
            "target_rva": f"0x{spec['target_rva']:08x}",
            "raw_e8_callsites": [f"0x{site:08x}" for site in spec["callsites"]],
            "meaning": spec["meaning"],
            "evidence_class": "fact",
        }
        for spec in DIRECT_CALLSITE_CATALOG_SPECS
    ]


def _contracts() -> dict[str, Any]:
    return {
        "registered_values": {
            "BLOCKED_NONE": 0,
            "BLOCKED_TEMP": 1,
            "BLOCKED_PERM": 2,
        },
        "storage": {
            "board_map_offset": "+0x7458",
            "point_x_offset": "+0x10",
            "point_y_offset": "+0x14",
            "block_value_offset": "+0x18",
        },
        "spawn_validity": {
            "rejects_blocked_temp": True,
            "rejects_blocked_perm": True,
            "checks_blocks_before_remaining_tile_rules": True,
        },
        "clear_block_spawns": {
            "clears_value": 1,
            "replacement_value": 0,
            "preserves_value": 2,
            "native_direct_callsites": ["0x00168d1c"],
        },
        "phase_lifetime": {
            "phase_dispatch_table": {
                "phase_0_target_rva": "0x0018a48f",
                "phase_1_target_rva": "0x0018a770",
            },
            "stage_start_requested_phase": 1,
            "end_turn_sweep_mode": 6,
            "end_turn_clears_temporary": False,
            "player_turn_phase": 0,
            "player_turn_sweep_mode": 1,
            "player_turn_clears_temporary": True,
            "cleanup_precedes_player_turn_ui": True,
        },
        "board_lifetime": {
            "board_reset_zeros_all_8x8_values": True,
            "permanent_survives_player_turn_cleanup": True,
            "permanent_survives_board_reset": False,
            "explicit_block_spawn_overwrite_still_possible": True,
        },
        "final_cave_startup": {
            "mountain_value": 1,
            "pylon_value": 2,
            "both_affect_startup_enemy_selection": True,
            "mountain_temp_survives_stage_start_phase_one": True,
            "mountain_temp_clears_before_first_player_turn_ui": True,
            "pylon_perm_survives_player_turn_cleanup": True,
        },
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "blocked_constants_are_exact",
            "evidence_class": "fact",
            "claim": (
                "Exact native registration binds BLOCKED_NONE, BLOCKED_TEMP, "
                "and BLOCKED_PERM to integer values zero, one, and two."
            ),
            "supports": [
                "blocked_none_registration",
                "blocked_temp_registration",
                "blocked_perm_registration",
            ],
        },
        {
            "id": "both_block_values_reject_spawns",
            "evidence_class": "inference",
            "claim": (
                "BlockSpawn writes the requested value synchronously to the "
                "Board+0x7458 Point map, and native spawn validity rejects both "
                "temporary value one and permanent value two before its other "
                "tile rules."
            ),
            "supports": [
                "block_spawn_tile_write",
                "spawn_rejects_both_block_values",
                "selector_validity_a",
                "selector_validity_b",
                "selector_validity_c",
            ],
        },
        {
            "id": "temporary_cleanup_is_exact",
            "evidence_class": "inference",
            "claim": (
                "ClearBlockSpawns walks the same Point map and changes only "
                "value one to zero. Value two survives this cleanup."
            ),
            "supports": [
                "clear_only_temporary",
                "clear_to_tile_map",
                "phase_sweep_to_clear",
            ],
        },
        {
            "id": "player_turn_is_the_native_cleanup_boundary",
            "evidence_class": "inference",
            "claim": (
                "The phase tile sweep has one native ClearBlockSpawns call, "
                "guarded by mode one. The player-turn branch passes one before "
                "constructing its player-turn UI, while the end-turn branch "
                "passes six and skips cleanup."
            ),
            "supports": [
                "phase_sweep_cleanup_gate",
                "phase_dispatch_entries_zero_one",
                "player_phase_runs_cleanup",
                "player_phase_ui_after_cleanup",
                "end_turn_phase_skips_cleanup",
                "end_turn_ui_anchor",
            ],
        },
        {
            "id": "final_cave_startup_lifetime_is_exact",
            "evidence_class": "inference",
            "claim": (
                "On the ordinary exact Final Cave startup, mountain value-one "
                "and pylon value-two marks both constrain the already-proven "
                "boss and ordinary startup selection. Stage initialization "
                "requests phase one, so temporary mountain marks are not "
                "cleared there; the later first player-turn cleanup removes "
                "them before player-turn UI, while permanent pylon marks "
                "survive that cleanup."
            ),
            "supports": [
                LUA_SOURCE_SPEC["path"],
                "final_cave_startup_spawn_order",
                "stage_start_requests_phase_one",
                "player_turn_is_the_native_cleanup_boundary",
                "temporary_cleanup_is_exact",
            ],
            "limitations": [
                "This is semantic phase order, not a wall-clock presentation trace."
            ],
        },
        {
            "id": "permanent_is_board_scoped",
            "evidence_class": "inference",
            "claim": (
                "Permanent means preserved by ordinary ClearBlockSpawns, not "
                "immortal storage. The Board reset path writes zero to all 8x8 "
                "entries, and an explicit later BlockSpawn call can overwrite "
                "a value."
            ),
            "supports": ["board_reset_zeros_every_tile", "field_reference_catalog"],
        },
        {
            "id": "solver_boundary_remains_settled_read",
            "evidence_class": "inference",
            "claim": (
                "No Rust semantic change follows. Native startup selection "
                "already consumes both block kinds, temporary marks clear before "
                "the first actionable player state, and the bridge supplies the "
                "concrete settled terrain and units. Keep the fresh stage-change "
                "read rather than forecasting startup RNG or presentation."
            ),
            "supports": [
                "final_cave_startup_lifetime_is_exact",
                "final_cave_startup_effect_order",
            ],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "runtime_block_map_observability",
            "question": "What exact block-map values exist in an arbitrary modified live mission?",
            "static_status": (
                "Ordinary exact-build semantics are pinned, but the bridge does "
                "not export the native Board+0x7458 map."
            ),
            "next_evidence": (
                "Expose the map only if a concrete modified-mission solver need "
                "cannot be answered from settled terrain and spawn markers."
            ),
        },
        {
            "id": "explicit_or_modified_clear_calls",
            "question": "Can mods or modified Lua clear blocks at another time?",
            "static_status": (
                "ClearBlockSpawns is Lua-registered. The 153 files in either "
                "accepted hash-pinned content tree contain no identifier use, "
                "but other modified scripts may invoke it."
            ),
            "next_evidence": "Treat modified-script calls as a separate build/content identity.",
        },
        {
            "id": "presentation_collisions",
            "question": (
                "How do occupied rock, pylon, or bomb droppers and terrain "
                "replacement interleave visually?"
            ),
            "static_status": (
                "Spawn-block lifetime is exact; arbitrary dropper collisions "
                "and visual impact overlap remain outside this map."
            ),
            "next_evidence": "Use a narrow controlled trace only if gameplay state diverges.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do other executable builds use the same lifetime rules?",
            "static_status": "This evidence is keyed only to Windows build 13725832.",
            "next_evidence": "Produce an independent build-keyed map.",
        },
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
            "image_base": f"0x{EXPECTED_IMAGE_BASE:08x}",
            "base_inventory_scripts_revision_sha256": (
                BASE_SCRIPTS_INVENTORY_SPEC["base_scripts_revision_sha256"]
            ),
            "scripts_identity_scope": (
                "base inventory exact outside one accepted project bridge overlay"
            ),
        },
        "sources": {
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
            "lua_files": [{**LUA_SOURCE_SPEC, "evidence_class": "fact"}],
            "accepted_tree_lua_search": {
                "root": "scripts",
                "glob": "**/*.lua",
                "file_count": 153,
                "needle": "ClearBlockSpawns",
                "matching_files": [],
                "evidence_class": "fact",
            },
        },
        "dependencies": [
            {
                "id": "final_cave_startup_spawn_order",
                "artifact": (
                    "data/observatory/native/windows_build_13725832_"
                    "31fe35265598_final_cave_startup_spawn_order.json"
                ),
                "artifact_sha256": STARTUP_SPAWN_ORDER_ARTIFACT_SHA256,
                "role": (
                    "Pins both BlockSpawn writes before boss and ordinary "
                    "startup selection and before queued effect dispatch."
                ),
            },
            {
                "id": "final_cave_startup_effect_order",
                "artifact": (
                    "data/observatory/native/windows_build_13725832_"
                    "31fe35265598_final_cave_startup_effect_order.json"
                ),
                "artifact_sha256": STARTUP_EFFECT_ORDER_ARTIFACT_SHA256,
                "role": (
                    "Pins queued startup record order while leaving this "
                    "spawn-block lifetime facet to the present continuation."
                ),
            },
            {
                "id": "base_scripts_inventory",
                "artifact": BASE_SCRIPTS_INVENTORY_SPEC["path"],
                "artifact_sha256": BASE_SCRIPTS_INVENTORY_SPEC["sha256"],
                "role": (
                    "Pins all 305 baseline scripts entries. Verification "
                    "requires all 304 analysis-relevant entries to match and "
                    "permits only one of two hash-pinned project bridge overlays."
                ),
                "scripts_file_count": BASE_SCRIPTS_INVENTORY_SPEC[
                    "scripts_file_count"
                ],
                "base_inventory_scripts_revision_sha256": (
                    BASE_SCRIPTS_INVENTORY_SPEC["base_scripts_revision_sha256"]
                ),
                "overlay_path": BASE_SCRIPTS_INVENTORY_SPEC["overlay_path"],
                "accepted_overlay_files": BASE_SCRIPTS_INVENTORY_SPEC[
                    "accepted_overlay_files"
                ],
            },
        ],
        "supersedes": {
            "artifact": (
                "data/observatory/native/windows_build_13725832_"
                "31fe35265598_final_cave_startup_effect_order.json"
            ),
            "resolved_facets": ["spawn_block_lifetime"],
            "remaining_gap_ids": [item["id"] for item in _unresolved()],
        },
        "method": {
            "boundary_review": (
                "Focused Ghidra 12.1.3 registration, Point-map field-reference, "
                "spawn-validity, cleanup, Board-reset, phase-driver, and call-graph review."
            ),
            "binary_verification": (
                "Capstone 5.0.7 rechecks instruction-aligned regions and windows; "
                "the verifier also scans every executable byte for raw E8 calls "
                "to the cleanup, phase sweep, and spawn-validity targets."
            ),
            "source_review": (
                "The exact Final Cave source is hash-pinned and lexical block "
                "calls are checked. A hash-pinned baseline inventory verifies "
                "all scripts except one accepted project bridge overlay, and "
                "all 153 accepted-tree Lua files are searched for the "
                "ClearBlockSpawns identifier."
            ),
            "limitations": [
                "Every native address applies only to the pinned Windows executable.",
                "Raw E8 catalog completeness does not classify hypothetical indirect native calls.",
                "Modified Lua can invoke the registered cleanup at another time.",
                "The accepted project bridge overlay is not treated as shipped game source.",
                "This map proves semantic phase order, not wall-clock presentation timing.",
            ],
        },
        "contracts": _contracts(),
        "regions": _expected_regions(),
        "data_anchors": _expected_data_anchors(),
        "constant_bindings": _expected_constant_bindings(),
        "method_bindings": _expected_method_bindings(),
        "control_windows": _expected_windows(),
        "direct_call_edges": _expected_edges(),
        "direct_callsite_catalog": _expected_callsite_catalog(),
        "field_reference_catalog": FIELD_REFERENCE_CATALOG,
        "findings": _findings(),
        "unresolved": _unresolved(),
        "summary": {
            "lua_source_count": 1,
            "accepted_tree_lua_file_count": 153,
            "dependency_count": 3,
            "region_count": len(REGION_SPECS),
            "data_anchor_count": len(DATA_ANCHOR_SPECS),
            "constant_binding_count": len(CONSTANT_BINDING_SPECS),
            "method_binding_count": len(METHOD_BINDING_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "direct_callsite_target_count": len(DIRECT_CALLSITE_CATALOG_SPECS),
            "field_reference_function_count": len(FIELD_REFERENCE_CATALOG),
            "finding_count": len(_findings()),
            "unresolved_count": len(_unresolved()),
            "block_values_proven": True,
            "spawn_rejection_proven": True,
            "temporary_cleanup_boundary_proven": True,
            "permanent_player_turn_persistence_proven": True,
            "permanent_cross_board_persistence_proven": False,
            "simulator_change_required": False,
        },
    }


def _verify_scripts_identity(content_root: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    inventory_path = repository_root / BASE_SCRIPTS_INVENTORY_SPEC["path"]
    if inventory_path.is_symlink() or not inventory_path.is_file():
        raise FinalCaveBlockSpawnLifetimeError(
            "base scripts inventory is not a regular non-symlink file"
        )
    inventory_bytes = inventory_path.read_bytes()
    if (
        len(inventory_bytes) != BASE_SCRIPTS_INVENTORY_SPEC["size"]
        or hashlib.sha256(inventory_bytes).hexdigest()
        != BASE_SCRIPTS_INVENTORY_SPEC["sha256"]
    ):
        raise FinalCaveBlockSpawnLifetimeError("base scripts inventory differs")
    try:
        inventory = json.loads(inventory_bytes)
        baseline = inventory["content"]["scripts"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise FinalCaveBlockSpawnLifetimeError(
            "base scripts inventory shape differs"
        ) from exc
    if (
        baseline.get("file_count")
        != BASE_SCRIPTS_INVENTORY_SPEC["scripts_file_count"]
        or baseline.get("byte_count")
        != BASE_SCRIPTS_INVENTORY_SPEC["scripts_byte_count"]
        or baseline.get("revision_sha256")
        != BASE_SCRIPTS_INVENTORY_SPEC["base_scripts_revision_sha256"]
        or not isinstance(baseline.get("files"), list)
    ):
        raise FinalCaveBlockSpawnLifetimeError(
            "base scripts inventory identity differs"
        )

    actual = build_manifest(content_root, "scripts")
    if actual["file_count"] != BASE_SCRIPTS_INVENTORY_SPEC["scripts_file_count"]:
        raise FinalCaveBlockSpawnLifetimeError("scripts file count differs")
    baseline_files = {entry["path"]: entry for entry in baseline["files"]}
    actual_files = {entry["path"]: entry for entry in actual["files"]}
    if baseline_files.keys() != actual_files.keys():
        raise FinalCaveBlockSpawnLifetimeError("scripts paths differ")

    overlay_path = BASE_SCRIPTS_INVENTORY_SPEC["overlay_path"]
    for path, expected in baseline_files.items():
        if path != overlay_path and actual_files[path] != expected:
            raise FinalCaveBlockSpawnLifetimeError(
                f"analysis-relevant scripts entry differs: {path}"
            )
    actual_overlay = actual_files[overlay_path]
    accepted_overlays = {
        (item["size"], item["sha256"])
        for item in (
            *BASE_SCRIPTS_INVENTORY_SPEC["accepted_overlay_files"],
            *POST_PUBLICATION_PROJECT_BRIDGE_OVERLAYS,
        )
    }
    if (actual_overlay["size"], actual_overlay["sha256"]) not in accepted_overlays:
        raise FinalCaveBlockSpawnLifetimeError(
            "project bridge overlay is not an accepted hash-pinned version"
        )


def _verify_lua_source(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise FinalCaveBlockSpawnLifetimeError("content root is not a directory")
    _verify_scripts_identity(root)
    source = root / Path(LUA_SOURCE_SPEC["path"])
    try:
        resolved = source.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise FinalCaveBlockSpawnLifetimeError(
            "Final Cave Lua source is missing or escapes the content root"
        ) from exc
    if source.is_symlink() or not resolved.is_file():
        raise FinalCaveBlockSpawnLifetimeError(
            "Final Cave Lua source is not a regular non-symlink file"
        )
    data = resolved.read_bytes()
    if (
        len(data) != LUA_SOURCE_SPEC["size"]
        or hashlib.sha256(data).hexdigest() != LUA_SOURCE_SPEC["sha256"]
    ):
        raise FinalCaveBlockSpawnLifetimeError("Final Cave Lua source differs")

    start = data.index(b"function Mission_Final_Cave:StartMission()")
    end = data.index(b"function Mission_Final_Cave:UpdateSpawning()", start)
    body = data[start:end]
    temporary = b"Board:BlockSpawn(rock.loc,BLOCKED_TEMP)"
    permanent = b"Board:BlockSpawn(building.loc,BLOCKED_PERM)"
    boss = b"Board:SpawnPawn(random_element(self.BossList))"
    if not (body.index(temporary) < body.index(permanent) < body.index(boss)):
        raise FinalCaveBlockSpawnLifetimeError(
            "Final Cave BlockSpawn lexical order differs"
        )

    scripts_root = root / "scripts"
    files = sorted(
        (
            path
            for path in scripts_root.rglob("*.lua")
            if path.is_file() and not path.is_symlink()
        ),
        key=lambda path: path.relative_to(scripts_root).as_posix(),
    )
    if len(files) != 153:
        raise FinalCaveBlockSpawnLifetimeError("shipped Lua file count differs")
    matches = [path for path in files if b"ClearBlockSpawns" in path.read_bytes()]
    if matches:
        raise FinalCaveBlockSpawnLifetimeError(
            "shipped Lua unexpectedly calls ClearBlockSpawns"
        )


def build_final_cave_block_spawn_lifetime_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build Final Cave spawn-block lifetime map."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise FinalCaveBlockSpawnLifetimeError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise FinalCaveBlockSpawnLifetimeError("executable identity differs")
    _verify_lua_source(content_root)

    ranges: dict[str, tuple[int, int]] = {}
    for spec in REGION_SPECS:
        size = spec["end"] - spec["start"]
        try:
            body = _region_bytes(
                image, data, spec["start"], size, ".text", spec["id"]
            )
        except Exception as exc:
            raise FinalCaveBlockSpawnLifetimeError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise FinalCaveBlockSpawnLifetimeError(
                f"region {spec['id']} bytes differ"
            )
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise FinalCaveBlockSpawnLifetimeError(str(exc)) from exc

    anchors = {spec["id"]: spec for spec in DATA_ANCHOR_SPECS}
    for spec in DATA_ANCHOR_SPECS:
        actual = _file_backed_bytes(
            image, data, spec["rva"], len(spec["data"]), spec["section"]
        )
        if actual != spec["data"]:
            raise FinalCaveBlockSpawnLifetimeError(
                f"data anchor {spec['id']} differs"
            )

    for spec in CONSTANT_BINDING_SPECS:
        for kind in ("name", "value"):
            rva = spec[f"{kind}_reference_rva"]
            encoded = bytes.fromhex(spec[f"{kind}_instruction_hex"])
            if _bytes_at(image, data, rva, len(encoded)) != encoded:
                raise FinalCaveBlockSpawnLifetimeError(
                    f"constant binding {spec['id']} {kind} reference differs"
                )
            instruction = decoded["constant_registration"].get(rva)
            if instruction is None or instruction[1] != encoded:
                raise FinalCaveBlockSpawnLifetimeError(
                    f"constant binding {spec['id']} {kind} is not an instruction"
                )
            anchor = anchors[spec[f"{kind}_anchor"]]
            if struct.pack("<I", image.image_base + anchor["rva"]) not in encoded:
                raise FinalCaveBlockSpawnLifetimeError(
                    f"constant binding {spec['id']} {kind} target differs"
                )

    for spec in METHOD_BINDING_SPECS:
        name = bytes.fromhex(spec["name_instruction_hex"])
        wrapper = bytes.fromhex(spec["wrapper_instruction_hex"])
        if _bytes_at(
            image, data, spec["name_reference_rva"], len(name)
        ) != name:
            raise FinalCaveBlockSpawnLifetimeError(
                f"method binding {spec['id']} name reference differs"
            )
        if _bytes_at(
            image, data, spec["wrapper_reference_rva"], len(wrapper)
        ) != wrapper:
            raise FinalCaveBlockSpawnLifetimeError(
                f"method binding {spec['id']} wrapper reference differs"
            )
        if decoded["method_registration"].get(spec["name_reference_rva"], (None, None))[1] != name:
            raise FinalCaveBlockSpawnLifetimeError(
                f"method binding {spec['id']} name is not an instruction"
            )
        if decoded["method_registration"].get(spec["wrapper_reference_rva"], (None, None))[1] != wrapper:
            raise FinalCaveBlockSpawnLifetimeError(
                f"method binding {spec['id']} wrapper is not an instruction"
            )
        name_anchor = anchors[spec["name_anchor"]]
        if struct.pack("<I", image.image_base + name_anchor["rva"]) not in name:
            raise FinalCaveBlockSpawnLifetimeError(
                f"method binding {spec['id']} name target differs"
            )
        if struct.pack("<I", image.image_base + spec["wrapper_rva"]) not in wrapper:
            raise FinalCaveBlockSpawnLifetimeError(
                f"method binding {spec['id']} wrapper target differs"
            )

    region_specs = {spec["id"]: spec for spec in REGION_SPECS}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["instruction_hex"])
        start = spec["start_rva"]
        if _bytes_at(image, data, start, len(encoded)) != encoded:
            raise FinalCaveBlockSpawnLifetimeError(
                f"control window {spec['id']} differs"
            )
        region = region_specs[spec["region_id"]]
        if not (region["start"] <= start < start + len(encoded) <= region["end"]):
            raise FinalCaveBlockSpawnLifetimeError(
                f"control window {spec['id']} escapes its region"
            )
        cursor = start
        instructions = decoded[spec["region_id"]]
        while cursor < start + len(encoded):
            instruction = instructions.get(cursor)
            if instruction is None:
                raise FinalCaveBlockSpawnLifetimeError(
                    f"control window {spec['id']} crosses undecoded bytes"
                )
            cursor += len(instruction[1])
        if cursor != start + len(encoded):
            raise FinalCaveBlockSpawnLifetimeError(
                f"control window {spec['id']} ends inside an instruction"
            )

    for (
        edge_id,
        source_region,
        from_rva,
        instruction_hex,
        target_region,
        target_rva,
    ) in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(instruction_hex)
        instruction = decoded[source_region].get(from_rva)
        if instruction is None or instruction[1] != expected:
            raise FinalCaveBlockSpawnLifetimeError(
                f"direct edge {edge_id} bytes differ"
            )
        if _direct_target(from_rva, expected) != target_rva:
            raise FinalCaveBlockSpawnLifetimeError(
                f"direct edge {edge_id} target differs"
            )
        if target_rva not in decoded[target_region]:
            raise FinalCaveBlockSpawnLifetimeError(
                f"direct edge {edge_id} target is not an instruction"
            )

    targets = {spec["target_rva"] for spec in DIRECT_CALLSITE_CATALOG_SPECS}
    scanned = _scan_direct_calls(image, data, targets)
    expected_scanned = {
        spec["target_rva"]: spec["callsites"]
        for spec in DIRECT_CALLSITE_CATALOG_SPECS
    }
    if scanned != expected_scanned:
        raise FinalCaveBlockSpawnLifetimeError("direct callsite catalog differs")

    return _expected_shape()


def validate_final_cave_block_spawn_lifetime_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping):
        raise FinalCaveBlockSpawnLifetimeError(
            "spawn-block lifetime map must be an object"
        )
    if dict(value) != _expected_shape():
        raise FinalCaveBlockSpawnLifetimeError(
            "spawn-block lifetime map fields differ"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "block_values_proven": True,
        "spawn_rejection_proven": True,
        "temporary_cleanup_boundary_proven": True,
        "permanent_player_turn_persistence_proven": True,
        "permanent_cross_board_persistence_proven": False,
        "simulator_change_required": False,
    }


def validate_final_cave_block_spawn_lifetime_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject source, byte, address, or prose drift."""
    expected = build_final_cave_block_spawn_lifetime_map(executable, content_root)
    if dict(value) != expected:
        raise FinalCaveBlockSpawnLifetimeError(
            "spawn-block lifetime map differs from exact-build analysis"
        )
    result = validate_final_cave_block_spawn_lifetime_map_binding(value)
    result["status"] = "verified"
    return result


def encode_final_cave_block_spawn_lifetime_map(
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
