"""Reproduce exact-build Board-death event visibility timing.

This successor closes the event-frame question left by the native enemy-death
credit map.  It joins the sole pending-event publisher through Game and battle
dispatch to the BoardPlayer orchestrator, whose Board/effect update precedes
``Mission:BaseUpdate``.  The result is deliberately narrow: an event recorded
during that Board/effect pass is not readable by the same outer update's
``BaseUpdate``; it is promoted before the next ordinary active-battle update.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.death_event_credit_boundary import (
    DeathEventCreditBoundaryError,
    validate_death_event_credit_boundary_map,
)
from src.observatory.final_cave_replacement import (
    FinalCaveReplacementError,
    validate_final_cave_replacement_map,
)
from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_event_frame_visibility_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)


class EventFrameVisibilityError(RuntimeError):
    """Raised when the reviewed event-frame boundary cannot reproduce."""


DEPENDENCY_SPECS = (
    {
        "id": "death_event_credit_boundary",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_death_event_credit_boundary.json"
        ),
        "file_sha256": (
            "5f4efd7b808a619630199a1f11628650a7ea09886377a10e3a9e3907587c4688"
        ),
        "canonical_sha256": (
            "780d1000112a4d801dd9df342a6aac5720dcb5d4fdc482c028416f7d9f18bbc7"
        ),
        "role": (
            "Pins ordinary enemy-death event 2, the pending/readable arrays, the "
            "sole direct publisher, Game:GetEventCount, and Mission:BaseUpdate's "
            "KilledVek consumer."
        ),
    },
    {
        "id": "final_cave_replacement",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_final_cave_replacement.json"
        ),
        "file_sha256": (
            "1d7f6b05b4fa4ddc1566d1e4c87ff5487e5dace83fc2e594b801bc21f4effdb4"
        ),
        "canonical_sha256": (
            "b08b6d96d4d4ba0f53c024b301b17a039c8deb944632bbc6b8b4000a6e20af50"
        ),
        "role": (
            "Pins BoardPlayer construction and the primary orchestrator's exact "
            "Board/effect-update-before-BaseUpdate ordering."
        ),
    },
)


SOURCE_SPEC = {
    "path": "scripts/missions/missions.lua",
    "size": 29_573,
    "sha256": "505c02a8668ba2e39d868f95051ede81c6cc1611f1e409219b6caa4fbe1d0257",
    "reviewed_lines": [856, 873],
    "symbols": ["Mission:BaseUpdate", "Mission.KilledVek", "EVENT_ENEMY_KILLED"],
}


REGION_SPECS = (
    {
        "id": "event_recorder",
        "start": 0x0009BE90,
        "end": 0x0009BEFF,
        "sha256": "689f97fb534e0f7e8792e4ed7508a851f42171c34158b044581b5c488c0baaa2",
        "basis": "Ghidra 12.1.3 generic event-recorder body.",
    },
    {
        "id": "event_publisher",
        "start": 0x0009BF00,
        "end": 0x0009BF88,
        "sha256": "49ceab3bd5073935a21e3df26de48f3b7669318e80dcb569d8f694271fff3ee3",
        "basis": "Ghidra 12.1.3 pending-to-readable publisher body.",
    },
    {
        "id": "outer_main_update",
        "start": 0x000E45E0,
        "end": 0x000E5650,
        "sha256": "b5c2bd4bddb20bbda2dd87e2202c607f9ad9d6e5444a8dd361511e0ed15b81c1",
        "basis": "Ghidra 12.1.3 outer main-update body.",
    },
    {
        "id": "board_effect_update",
        "start": 0x00169BF0,
        "end": 0x0016A1F5,
        "sha256": "c047a08e5f274e629b6fec7151c94c89f5576ec3bbf11b0535546fb65d7c7877",
        "basis": "Ghidra 12.1.3 Board effect-queue update body.",
    },
    {
        "id": "board_master_update",
        "start": 0x0016A8D0,
        "end": 0x0016BF62,
        "sha256": "6d32a302492920ae4353af4505e792776a18c4f9d8c26bd6cf1f9861a6f9129d",
        "basis": "Ghidra 12.1.3 Board master-update body.",
    },
    {
        "id": "boardplayer_constructor",
        "start": 0x0017FA80,
        "end": 0x001805DE,
        "sha256": "c735b98c1ebef4e9c52c43239f752cfd45e99a7c1c18062235a3c24d5578c84a",
        "basis": "Ghidra 12.1.3 BoardPlayer constructor body.",
    },
    {
        "id": "primary_orchestrator",
        "start": 0x0018AE90,
        "end": 0x0018B36F,
        "sha256": "8a5e7744c920a70f30f8056271d452335be6d601625f8b8d935d5457b77ebf82",
        "basis": "Ghidra 12.1.3 BoardPlayer primary-update body.",
    },
    {
        "id": "mission_named_invoker",
        "start": 0x00199900,
        "end": 0x00199998,
        "sha256": "f104b8d01a7d8904631d4481f8c46efca50e906ff1ba29e34f980df21dde3ac6",
        "basis": "Ghidra 12.1.3 named Mission method invoker body.",
    },
    {
        "id": "game_constructor",
        "start": 0x00207B80,
        "end": 0x00207CA6,
        "sha256": "f866bd2c053776c24e913b19457b294a9f8105bcbb7c153e8cb877dc1447d617",
        "basis": "Ghidra 12.1.3 Game constructor body.",
    },
    {
        "id": "game_update",
        "start": 0x00208C40,
        "end": 0x00209124,
        "sha256": "d13dc28ca9785872da9803154a84015ad0a6825081cab500dd0f60a671dc6e63",
        "basis": "Ghidra 12.1.3 Game primary-update body.",
    },
    {
        "id": "get_event_count",
        "start": 0x0020E780,
        "end": 0x0020E7C1,
        "sha256": "1914235348cc79735d409cecfb4af66c02d538a9cad2badef3527beff5394e0e",
        "basis": "Ghidra 12.1.3 GameMap event-count reader body.",
    },
    {
        "id": "battle_update",
        "start": 0x0020EE60,
        "end": 0x0020F9F2,
        "sha256": "3ed314fbd5b9c24a0c017d5b29b10f059b951769e949b3a06907bfcf83f361ee",
        "basis": "Ghidra 12.1.3 active-battle controller-update body.",
    },
    {
        "id": "controller_setup",
        "start": 0x0020FCB0,
        "end": 0x0020FF53,
        "sha256": "7618d01a903b1919ab815ba33c5562cbacaadb5186118002e839d06048c27ff1",
        "basis": "Ghidra 12.1.3 battle BoardPlayer setup body.",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "event_record_pending",
        "region": "event_recorder",
        "start": 0x0009BE96,
        "hex": (
            "803d50d28b00005675588b7508b9b0d28b00a1a4d28b00897508ff04b08d45"
            "08508d45f850e8a00afeff8b45f88b4d0c894814a100d28b008b0dfcd18b002b"
            "c1c1f8023bf07d0e85f6780aff04b1"
        ),
        "meaning": "Increment the total and pending event arrays and retain the payload.",
    },
    {
        "id": "event_publish_pending",
        "region": "event_publisher",
        "start": 0x0009BF06,
        "hex": (
            "68fcd18b00b9f0d18b00e83bbafeff8d45fcc745fc00000000506a508d4df0"
            "c745f000000000c745f400000000c745f800000000e8711000008d45f0b9fcd1"
            "8b0050e813bbfeff"
        ),
        "meaning": "Copy pending counts to readable storage, then reset pending storage.",
    },
    {
        "id": "outer_publish_before_game_update",
        "region": "outer_main_update",
        "start": 0x000E55A7,
        "hex": "e87487f9ffe84f69fbffe8ea53ffff8b4f188b01ff5004",
        "meaning": "Publish events, then invoke Game vtable slot +0x04 in the same outer update.",
    },
    {
        "id": "outer_constructs_game_at_update_field",
        "region": "outer_main_update",
        "start": 0x000E4638,
        "hex": (
            "68a8940100e8992e270083c40489855cffffff8bc8c745fc00000000e827351200"
            "c745fcffffffff8bc8894718"
        ),
        "meaning": "Construct the exact Game object and retain it at outer object +0x18.",
    },
    {
        "id": "board_calls_effect_update",
        "region": "board_master_update",
        "start": 0x0016B461,
        "hex": "8b4d808b4340412b433cc1f802894d803bc80f82c9fdffff8bcbe870e7ffff",
        "meaning": "Reach the effect-queue update during the Board master update.",
    },
    {
        "id": "boardplayer_vtable_install",
        "region": "boardplayer_constructor",
        "start": 0x0017FAC8,
        "hex": "c70648018300",
        "meaning": "Install the BoardPlayer vtable at VA 0x00830148.",
    },
    {
        "id": "board_update_before_base_update",
        "region": "primary_orchestrator",
        "start": 0x0018B0DE,
        "hex": "8b4e04e8eaf7fdff",
        "meaning": "Load the Board and run its master update before the later BaseUpdate path.",
    },
    {
        "id": "base_update_gate_and_dispatch",
        "region": "primary_orchestrator",
        "start": 0x0018B181,
        "hex": (
            "83bec80f0000060f84b50100008bcee88be9ffffc686283900000083bee40f0000"
            "0074758b86941c00003bc7740a85c074068378040074618b86c80f000083f80574"
            "5683f806745183ec188bcc8965ec6878f98200e835cce7ff83ec18c645fc018bcc"
            "8d96d40f0000c741140f000000c74110000000008379141072048b01eb028bc16a"
            "ff6a0052c60000e8bfcee7ffc645fc00e8e6e60000"
        ),
        "meaning": "After Board update, prepare and invoke Mission:BaseUpdate when its gates permit.",
    },
    {
        "id": "game_vtable_install",
        "region": "game_constructor",
        "start": 0x00207BB7,
        "hex": "c70614508300",
        "meaning": "Install the Game vtable at VA 0x00835014.",
    },
    {
        "id": "game_active_battle_dispatch",
        "region": "game_update",
        "start": 0x00208E7F,
        "hex": (
            "83f8010f85440200008b461083b840c00000000f94059e9e8b0084c975078bc8"
            "e8bc5f0000"
        ),
        "meaning": "In Game mode 1, dispatch the active controller through the battle-update body.",
    },
    {
        "id": "event_count_reads_readable",
        "region": "get_event_count",
        "start": 0x0020E783,
        "hex": (
            "a1f4d18b008b15f0d18b002bc28b4d08c1f8023bc87d1485c978108b048a85"
            "c00f95c184c974115dc20400"
        ),
        "meaning": "Return the current readable-array count for a valid event ID.",
    },
    {
        "id": "battle_active_boardplayer_dispatch",
        "region": "battle_update",
        "start": 0x0020F0CF,
        "hex": (
            "8b8f04c2000085c90f84ca00000083bf50d60000000f85bd0000008b01ff5010"
        ),
        "meaning": "When +0xc204 is present and +0xd650 is zero, invoke its vtable slot +0x10.",
    },
    {
        "id": "controller_boardplayer_slot",
        "region": "controller_setup",
        "start": 0x0020FCDD,
        "hex": (
            "83bf04c20000008db704c20000740732c0e9440200008b9fb0580000c787b058"
            "000000000000c70600000000"
        ),
        "meaning": "Name +0xc204 as the setup destination retained in ESI.",
    },
    {
        "id": "controller_restored_boardplayer_store",
        "region": "controller_setup",
        "start": 0x0020FD63,
        "hex": (
            "68cc450000e86e77140083c40489459c8bc8c645fc03e802fdf6ff83ec18c645"
            "fc028bcc89659c8906"
        ),
        "meaning": "Construct a BoardPlayer and store its returned pointer into +0xc204.",
    },
    {
        "id": "controller_cached_pointer_transfer",
        "region": "controller_setup",
        "start": 0x0020FE07,
        "hex": "8d4f04e8712effff890685c0",
        "meaning": "Transfer the cached-controller helper result into the same +0xc204 slot.",
    },
    {
        "id": "controller_fresh_boardplayer_store",
        "region": "controller_setup",
        "start": 0x0020FE7E,
        "hex": (
            "68cc450000e85376140083c4048945a08bc8c745fc00000000e8e4fbf6ff83ec"
            "18c745fcffffffff8bcc8906"
        ),
        "meaning": "Construct the alternate fresh BoardPlayer and store it into +0xc204.",
    },
)


DIRECT_EDGE_SPECS = (
    {
        "id": "outer_to_game_constructor",
        "source_region": "outer_main_update",
        "from": 0x000E4654,
        "hex": "e827351200",
        "target_region": "game_constructor",
        "target": 0x00207B80,
        "meaning": "Construct the Game instance later dispatched from outer +0x18.",
    },
    {
        "id": "outer_to_event_publisher",
        "source_region": "outer_main_update",
        "from": 0x000E55AC,
        "hex": "e84f69fbff",
        "target_region": "event_publisher",
        "target": 0x0009BF00,
        "meaning": "Run the sole direct pending-event publisher.",
    },
    {
        "id": "board_update_to_effect_update",
        "source_region": "board_master_update",
        "from": 0x0016B47B,
        "hex": "e870e7ffff",
        "target_region": "board_effect_update",
        "target": 0x00169BF0,
        "meaning": "Advance the Board effect queue in the current Board update.",
    },
    {
        "id": "orchestrator_to_board_update",
        "source_region": "primary_orchestrator",
        "from": 0x0018B0E1,
        "hex": "e8eaf7fdff",
        "target_region": "board_master_update",
        "target": 0x0016A8D0,
        "meaning": "Run Board update before BaseUpdate.",
    },
    {
        "id": "orchestrator_to_named_invoker",
        "source_region": "primary_orchestrator",
        "from": 0x0018B215,
        "hex": "e8e6e60000",
        "target_region": "mission_named_invoker",
        "target": 0x00199900,
        "meaning": "Invoke the prepared BaseUpdate callback name.",
    },
    {
        "id": "game_update_to_battle_update",
        "source_region": "game_update",
        "from": 0x00208E9F,
        "hex": "e8bc5f0000",
        "target_region": "battle_update",
        "target": 0x0020EE60,
        "meaning": "Enter the active-battle update from Game mode 1.",
    },
    {
        "id": "battle_update_to_controller_setup",
        "source_region": "battle_update",
        "from": 0x0020F5A7,
        "hex": "e804070000",
        "target_region": "controller_setup",
        "target": 0x0020FCB0,
        "meaning": "Populate the active +0xc204 controller slot when required.",
    },
    {
        "id": "controller_restored_to_boardplayer_constructor",
        "source_region": "controller_setup",
        "from": 0x0020FD79,
        "hex": "e802fdf6ff",
        "target_region": "boardplayer_constructor",
        "target": 0x0017FA80,
        "meaning": "Construct the restored BoardPlayer stored at +0xc204.",
    },
    {
        "id": "controller_fresh_to_boardplayer_constructor",
        "source_region": "controller_setup",
        "from": 0x0020FE97,
        "hex": "e8e4fbf6ff",
        "target_region": "boardplayer_constructor",
        "target": 0x0017FA80,
        "meaning": "Construct the alternate fresh BoardPlayer stored at +0xc204.",
    },
)


DATA_POINTER_SPECS = (
    {
        "id": "game_update_vtable_slot",
        "data_rva": 0x00435018,
        "section": ".rdata",
        "hex": "408c6000",
        "target_region": "game_update",
        "target_rva": 0x00208C40,
        "role": "Game vtable slot +0x04 targets the exact Game update body.",
    },
    {
        "id": "boardplayer_primary_update_vtable_slot",
        "data_rva": 0x00430158,
        "section": ".rdata",
        "hex": "90ae5800",
        "target_region": "primary_orchestrator",
        "target_rva": 0x0018AE90,
        "role": "BoardPlayer vtable slot +0x10 targets the primary orchestrator.",
    },
)


STRING_ANCHOR_SPEC = {
    "id": "base_update_name",
    "string_rva": 0x0042F978,
    "string_hex": "4261736555706461746500",
    "reference_region": "primary_orchestrator",
    "reference_rva": 0x0018B1D1,
    "reference_hex": "6878f98200",
    "meaning": "Prepare the exact native Mission method name BaseUpdate.",
}


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EventFrameVisibilityError(f"dependency is not an object: {path}")
    return value


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise EventFrameVisibilityError(f"RVA 0x{rva:08x} is not file-backed")
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise EventFrameVisibilityError("reviewed direct edge is not CALL rel32")
    return rva + 5 + struct.unpack("<i", encoded[1:])[0]


def _raw_rel32_call_sites(image: Any, data: bytes, target_rva: int) -> set[int]:
    section = next((item for item in image.sections if item.name == ".text"), None)
    if section is None or not section.executable or not section.raw_size:
        raise EventFrameVisibilityError("file-backed executable .text section missing")
    body = data[section.raw_offset : section.raw_offset + section.raw_size]
    result: set[int] = set()
    for offset in range(len(body) - 4):
        if body[offset] != 0xE8:
            continue
        source_rva = section.virtual_address + offset
        target = source_rva + 5 + struct.unpack_from("<i", body, offset + 1)[0]
        if target == target_rva:
            result.add(source_rva)
    return result


def _dependency_records() -> list[dict[str, str]]:
    return [dict(spec) for spec in DEPENDENCY_SPECS]


def _source_record() -> dict[str, Any]:
    return dict(SOURCE_SPEC)


def _region_records() -> list[dict[str, Any]]:
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


def _control_window_records() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region": spec["region"],
            "start_rva": f"0x{spec['start']:08x}",
            "size": len(bytes.fromhex(spec["hex"])),
            "sha256": hashlib.sha256(bytes.fromhex(spec["hex"])).hexdigest(),
            "instruction_hex": spec["hex"],
            "evidence_class": "fact",
            "meaning": spec["meaning"],
        }
        for spec in CONTROL_WINDOW_SPECS
    ]


def _direct_edge_records() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "kind": "direct_rel32",
            "source_region": spec["source_region"],
            "from_rva": f"0x{spec['from']:08x}",
            "instruction_hex": spec["hex"],
            "target_region": spec["target_region"],
            "target_rva": f"0x{spec['target']:08x}",
            "evidence_class": "fact",
            "meaning": spec["meaning"],
        }
        for spec in DIRECT_EDGE_SPECS
    ]


def _data_pointer_records() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "data_rva": f"0x{spec['data_rva']:08x}",
            "section": spec["section"],
            "instruction_hex": spec["hex"],
            "target_region": spec["target_region"],
            "target_rva": f"0x{spec['target_rva']:08x}",
            "target_va": f"0x{EXPECTED_IMAGE_BASE + spec['target_rva']:08x}",
            "evidence_class": "fact",
            "role": spec["role"],
        }
        for spec in DATA_POINTER_SPECS
    ]


def _string_anchor_record() -> dict[str, Any]:
    spec = STRING_ANCHOR_SPEC
    return {
        "id": spec["id"],
        "string_rva": f"0x{spec['string_rva']:08x}",
        "string_hex": spec["string_hex"],
        "reference_region": spec["reference_region"],
        "reference_rva": f"0x{spec['reference_rva']:08x}",
        "reference_hex": spec["reference_hex"],
        "evidence_class": "fact",
        "meaning": spec["meaning"],
    }


def _contracts() -> dict[str, Any]:
    return {
        "event_buffers": {
            "recorder_destination": "pending",
            "publisher_source": "pending",
            "publisher_destination": "readable",
            "publisher_resets_pending": True,
            "get_event_count_source": "readable",
            "event_publisher_direct_call_sites": ["0x000e55ac"],
            "sole_direct_event_publisher_call_proven": True,
        },
        "dispatch_chain": {
            "outer_game_pointer_offset": "+0x18",
            "outer_game_construction_store_proven": True,
            "outer_game_vtable_slot": "+0x04",
            "game_vtable_slot_target_rva": "0x00208c40",
            "active_battle_mode_value": 1,
            "game_battle_controller_offset": "+0x10",
            "battle_boardplayer_offset": "+0xc204",
            "battle_alternate_controller_offset": "+0xd650",
            "boardplayer_update_vtable_slot": "+0x10",
            "boardplayer_vtable_slot_target_rva": "0x0018ae90",
            "normal_boardplayer_construction_paths_pinned": 2,
            "cached_controller_transfer_present": True,
            "active_boardplayer_dispatch_chain_proven": True,
        },
        "orchestrator_order": {
            "board_update_call_rva": "0x0018b0e1",
            "board_effect_update_call_rva": "0x0016b47b",
            "base_update_name_reference_rva": "0x0018b1d1",
            "base_update_invoker_call_rva": "0x0018b215",
            "board_effect_update_before_base_update": True,
        },
        "board_death_visibility": {
            "event_recorded_during": "Board/effect update",
            "publisher_runs_before_current_game_update": True,
            "same_outer_update_base_update_reads_new_event": False,
            "next_ordinary_outer_update_publishes_new_event": True,
            "next_ordinary_outer_update_base_update_can_read_new_event": True,
            "visibility_delay_outer_updates": 1,
            "multiple_same_pass_deaths_publish_as_one_readable_batch": True,
            "qualification": (
                "The next-update result assumes the active battle and Mission:BaseUpdate "
                "path still run; pause, teardown, or a terminal state can delay or end "
                "that consumer path."
            ),
        },
        "scope": {
            "applies_to": "events recorded during the normal Board/effect pass",
            "events_recorded_elsewhere_in_outer_update_generalized": False,
            "cached_controller_helper_return_type_independently_mapped": False,
            "wall_clock_frame_duration_claimed": False,
            "non_windows_equivalence_claimed": False,
        },
    }


def _findings() -> list[dict[str, str]]:
    return [
        {
            "id": "publisher_precedes_game_update",
            "classification": "fact",
            "claim": (
                "The sole direct event-publisher call occurs before the same outer "
                "update's Game vtable +0x04 dispatch. The same outer object constructs "
                "that exact Game type and retains it at the dispatched +0x18 field."
            ),
        },
        {
            "id": "game_to_boardplayer_join",
            "classification": "fact",
            "claim": (
                "Game vtable +0x04 is the pinned Game update; active mode 1 enters "
                "battle update, which invokes the present +0xc204 controller at vtable "
                "+0x10. BoardPlayer construction installs the pinned vtable, whose +0x10 "
                "slot is the primary orchestrator."
            ),
        },
        {
            "id": "board_effect_before_base_update",
            "classification": "fact",
            "claim": (
                "The primary orchestrator calls Board master update, which reaches the "
                "effect queue, before preparing and invoking Mission:BaseUpdate."
            ),
        },
        {
            "id": "same_update_invisibility",
            "classification": "inference",
            "claim": (
                "A death event recorded during Board/effect processing enters pending "
                "after that outer update's only publication point, so the later same-"
                "update BaseUpdate reader cannot see it."
            ),
        },
        {
            "id": "next_update_visibility",
            "classification": "inference",
            "claim": (
                "The next ordinary outer update promotes the pending batch before Game "
                "and BoardPlayer dispatch, allowing its later BaseUpdate to read it."
            ),
        },
        {
            "id": "rust_model_remains_conformant",
            "classification": "inference",
            "claim": (
                "The Rust simulator accounts for mission kills as resolved action "
                "outcomes rather than emulating Lua callback visibility per outer update; "
                "this scheduling evidence contradicts no current transition rule."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "non_board_event_producers",
            "question": "When are events raised outside the Board/effect pass published?",
            "next_evidence": "Map only a concrete non-Board event producer if solver behavior depends on it.",
        },
        {
            "id": "cached_controller_type",
            "question": "Which concrete type is returned by the cached-controller transfer helper?",
            "next_evidence": "Trace the +0x5248 writer only if a restored-session dispatch mismatch appears.",
        },
        {
            "id": "terminal_transition_delivery",
            "question": "Can mission teardown suppress the next BaseUpdate after a terminal Board death?",
            "next_evidence": "Trace a concrete terminal-death case through mission teardown if its counter differs.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do macOS and other depots use the same event publication schedule?",
            "next_evidence": "Repeat this build-keyed boundary map on another exact executable.",
        },
    ]


def _expected_shape() -> dict[str, Any]:
    findings = _findings()
    unresolved = _unresolved()
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "bits": 32,
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "image_base": f"0x{EXPECTED_IMAGE_BASE:08x}",
            "scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION_SHA256,
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
        },
        "dependencies": _dependency_records(),
        "source": _source_record(),
        "regions": _region_records(),
        "control_windows": _control_window_records(),
        "direct_edges": _direct_edge_records(),
        "data_pointers": _data_pointer_records(),
        "string_anchor": _string_anchor_record(),
        "contracts": _contracts(),
        "findings": findings,
        "refines": {
            "artifact": DEPENDENCY_SPECS[0]["path"],
            "resolved_unresolved_ids": ["exact_event_frame_visibility"],
            "exact_event_frame_visibility_proven": True,
            "same_outer_update_visibility": False,
            "next_ordinary_outer_update_visibility": True,
        },
        "unresolved": unresolved,
        "solver_impact": {
            "simulator_contradiction": False,
            "simulator_change_required": False,
            "simulator_version_bump_required": False,
            "conforming_paths": [
                "rust_solver/src/board.rs::ActionResult::record_enemy_kill",
                "rust_solver/src/board.rs::unit_counts_for_mission_kill",
            ],
            "reason": (
                "This closes native event-reader scheduling, not a board transition. "
                "The solver does not expose an intra-outer-update Lua callback surface."
            ),
        },
        "notes": [
            "This is exact-build static evidence, not a runtime trace.",
            "Next ordinary outer update is a control-flow statement, not a wall-clock duration guarantee.",
            "The same-update result is scoped to events recorded during Board/effect processing.",
            "Multiple deaths accumulated in one Board/effect pass become readable as one promoted batch.",
        ],
        "summary": {
            "dependency_count": len(DEPENDENCY_SPECS),
            "source_count": 1,
            "region_count": len(REGION_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "data_pointer_count": len(DATA_POINTER_SPECS),
            "string_anchor_count": 1,
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "active_boardplayer_dispatch_chain_proven": True,
            "board_effect_update_before_base_update_proven": True,
            "sole_direct_event_publisher_call_proven": True,
            "exact_event_frame_visibility_proven": True,
            "same_outer_update_visibility": False,
            "next_ordinary_outer_update_visibility": True,
            "simulator_change_required": False,
        },
    }


def _verify_dependencies(executable: Path, content_root: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    validators = {
        "death_event_credit_boundary": validate_death_event_credit_boundary_map,
        "final_cave_replacement": validate_final_cave_replacement_map,
    }
    for spec in DEPENDENCY_SPECS:
        path = repository_root / spec["path"]
        if path.is_symlink() or not path.is_file():
            raise EventFrameVisibilityError(f"dependency missing: {spec['id']}")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
            raise EventFrameVisibilityError(f"dependency file differs: {spec['id']}")
        value = _read_json(path)
        if _canonical_sha256(value) != spec["canonical_sha256"]:
            raise EventFrameVisibilityError(f"dependency fields differ: {spec['id']}")
        try:
            validators[spec["id"]](executable, content_root, value)
        except (DeathEventCreditBoundaryError, FinalCaveReplacementError) as exc:
            raise EventFrameVisibilityError(
                f"dependency does not reproduce: {spec['id']}: {exc}"
            ) from exc


def _verify_source(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise EventFrameVisibilityError("content root is not a directory")
    source = root / SOURCE_SPEC["path"]
    try:
        resolved = source.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise EventFrameVisibilityError("Mission source is missing or escapes content root") from exc
    if source.is_symlink() or not resolved.is_file():
        raise EventFrameVisibilityError("Mission source is not a regular non-symlink file")
    raw = resolved.read_bytes()
    if (
        len(raw) != SOURCE_SPEC["size"]
        or hashlib.sha256(raw).hexdigest() != SOURCE_SPEC["sha256"]
    ):
        raise EventFrameVisibilityError("Mission source identity differs")
    required = (
        b"function Mission:BaseUpdate()",
        b"self.KilledVek = self.KilledVek + Game:GetEventCount(EVENT_ENEMY_KILLED)",
    )
    if any(token not in raw for token in required):
        raise EventFrameVisibilityError("Mission event consumer differs")


def build_event_frame_visibility_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build Board-death event visibility boundary."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise EventFrameVisibilityError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise EventFrameVisibilityError("executable identity differs")

    _verify_dependencies(executable, content_root)
    _verify_source(content_root)

    ranges: dict[str, tuple[int, int]] = {}
    for spec in REGION_SPECS:
        try:
            body = _region_bytes(
                image,
                data,
                spec["start"],
                spec["end"] - spec["start"],
                ".text",
                spec["id"],
            )
        except Exception as exc:
            raise EventFrameVisibilityError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise EventFrameVisibilityError(f"region bytes differ: {spec['id']}")
        ranges[spec["id"]] = (spec["start"], spec["end"])

    decode_ranges: dict[str, tuple[int, int]] = {}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["hex"])
        if _bytes_at(image, data, spec["start"], len(encoded)) != encoded:
            raise EventFrameVisibilityError(f"control window differs: {spec['id']}")
        start, end = ranges[spec["region"]]
        if not start <= spec["start"] < spec["start"] + len(encoded) <= end:
            raise EventFrameVisibilityError(f"control window escapes region: {spec['id']}")
        decode_ranges[f"window_{spec['id']}"] = (
            spec["start"],
            spec["start"] + len(encoded),
        )

    for spec in DIRECT_EDGE_SPECS:
        encoded = bytes.fromhex(spec["hex"])
        if _bytes_at(image, data, spec["from"], len(encoded)) != encoded:
            raise EventFrameVisibilityError(f"direct edge differs: {spec['id']}")
        source_start, source_end = ranges[spec["source_region"]]
        target_start, target_end = ranges[spec["target_region"]]
        if not source_start <= spec["from"] < spec["from"] + 5 <= source_end:
            raise EventFrameVisibilityError(f"direct edge escapes source: {spec['id']}")
        if not target_start <= spec["target"] < target_end:
            raise EventFrameVisibilityError(f"direct edge escapes target: {spec['id']}")
        if _direct_target(spec["from"], encoded) != spec["target"]:
            raise EventFrameVisibilityError(f"direct edge target differs: {spec['id']}")
        decode_ranges[f"edge_{spec['id']}"] = (spec["from"], spec["from"] + 5)
        decode_ranges[f"edge_target_{spec['id']}"] = (
            spec["target"],
            min(spec["target"] + 16, target_end),
        )

    for spec in DATA_POINTER_SPECS:
        encoded = bytes.fromhex(spec["hex"])
        if _bytes_at(image, data, spec["data_rva"], len(encoded)) != encoded:
            raise EventFrameVisibilityError(f"data pointer differs: {spec['id']}")
        section = next(
            (
                item
                for item in image.sections
                if item.virtual_address
                <= spec["data_rva"]
                < item.virtual_address + item.raw_size
            ),
            None,
        )
        if section is None or section.name != spec["section"] or section.executable:
            raise EventFrameVisibilityError(f"data pointer section differs: {spec['id']}")
        (target_va,) = struct.unpack("<I", encoded)
        if target_va != image.image_base + spec["target_rva"]:
            raise EventFrameVisibilityError(f"data pointer target differs: {spec['id']}")
        target_start, target_end = ranges[spec["target_region"]]
        if not target_start <= spec["target_rva"] < target_end:
            raise EventFrameVisibilityError(f"data pointer target escapes region: {spec['id']}")
        decode_ranges[f"pointer_target_{spec['id']}"] = (
            spec["target_rva"],
            min(spec["target_rva"] + 16, target_end),
        )

    anchor = STRING_ANCHOR_SPEC
    string_bytes = bytes.fromhex(anchor["string_hex"])
    reference_bytes = bytes.fromhex(anchor["reference_hex"])
    if _bytes_at(image, data, anchor["string_rva"], len(string_bytes)) != string_bytes:
        raise EventFrameVisibilityError("BaseUpdate string anchor differs")
    if (
        _bytes_at(image, data, anchor["reference_rva"], len(reference_bytes))
        != reference_bytes
        or struct.pack("<I", image.image_base + anchor["string_rva"])
        not in reference_bytes
    ):
        raise EventFrameVisibilityError("BaseUpdate string reference differs")
    decode_ranges["base_update_string_reference"] = (
        anchor["reference_rva"],
        anchor["reference_rva"] + len(reference_bytes),
    )

    try:
        decoded = _decode_x86_regions(image, data, decode_ranges)
    except Exception as exc:
        raise EventFrameVisibilityError(f"instruction alignment differs: {exc}") from exc
    for name, (start, end) in decode_ranges.items():
        cursor = start
        instructions = decoded[name]
        while cursor < end:
            instruction = instructions.get(cursor)
            if instruction is None:
                raise EventFrameVisibilityError(f"undecoded instruction in {name}")
            cursor += len(instruction[1])
        if cursor != end:
            raise EventFrameVisibilityError(f"reviewed range ends inside instruction: {name}")

    if _raw_rel32_call_sites(image, data, 0x0009BF00) != {0x000E55AC}:
        raise EventFrameVisibilityError("event publisher direct-call inventory differs")

    edges = {spec["id"]: spec for spec in DIRECT_EDGE_SPECS}
    windows = {spec["id"]: spec for spec in CONTROL_WINDOW_SPECS}
    if not (
        edges["outer_to_event_publisher"]["from"]
        < windows["outer_publish_before_game_update"]["start"]
        + len(bytes.fromhex(windows["outer_publish_before_game_update"]["hex"]))
    ):
        raise EventFrameVisibilityError("outer publisher/Game order differs")
    if not (
        edges["orchestrator_to_board_update"]["from"]
        < windows["base_update_gate_and_dispatch"]["start"]
        < edges["orchestrator_to_named_invoker"]["from"] + 5
    ):
        raise EventFrameVisibilityError("Board/BaseUpdate order differs")
    if not (
        edges["orchestrator_to_board_update"]["target"]
        <= edges["board_update_to_effect_update"]["from"]
    ):
        raise EventFrameVisibilityError("Board/effect update relation differs")

    return _expected_shape()


def validate_event_frame_visibility_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise EventFrameVisibilityError("event-frame visibility map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "active_boardplayer_dispatch_chain_proven": True,
        "board_effect_update_before_base_update_proven": True,
        "sole_direct_event_publisher_call_proven": True,
        "exact_event_frame_visibility_proven": True,
        "same_outer_update_visibility": False,
        "next_ordinary_outer_update_visibility": True,
        "simulator_change_required": False,
    }


def validate_event_frame_visibility_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject dependency, source, byte, or prose drift."""
    expected = build_event_frame_visibility_map(executable, content_root)
    if dict(value) != expected:
        raise EventFrameVisibilityError(
            "event-frame visibility map differs from exact-build analysis"
        )
    result = validate_event_frame_visibility_map_binding(value)
    result["status"] = "verified"
    return result


def encode_event_frame_visibility_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
