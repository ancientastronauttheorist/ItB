"""Reproduce the exact-build Final Cave startup boundary and RNG skeleton.

The artifact built here joins three independently checkable evidence classes:

* exact x86 regions and instruction-level order after ``CreateNextPhase``;
* exact shipped Lua source order inside ``BaseStart`` and Final Cave startup;
* the complete exact map revision and the nine maps tagged ``final_cave``.

It deliberately does not invent native map-choice RNG, spawn selection,
queued-effect settlement, or concrete random results.  Those remain runtime
or deeper-native questions even though the surrounding call skeleton and all
static candidate sets are now pinned.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.content_inventory import InventoryError, build_manifest
from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "final_cave_startup_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
EXPECTED_MAPS_REVISION_SHA256 = (
    "a16ed060190402ab83d5968c000917c9979944dd11beb154329ba002cfcb28d4"
)


class FinalCaveStartupError(RuntimeError):
    """Raised when the reviewed Final Cave startup map cannot be reproduced."""


LUA_SOURCE_SPECS = (
    {
        "path": "scripts/game.lua",
        "size": 9_747,
        "sha256": (
            "8fc587a6d341f43cf521ae2c95e91e5739355cb929581a18f9c374fba2c88db7"
        ),
        "symbols": ["GameObject:CreateNextPhase"],
    },
    {
        "path": "scripts/global.lua",
        "size": 17_363,
        "sha256": (
            "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2"
        ),
        "symbols": ["random_element", "random_removal"],
    },
    {
        "path": "scripts/environments.lua",
        "size": 8_924,
        "sha256": (
            "5f8a7d74f537abb33bc88c1f9669f3f6fabdd5c8c51aad3486d2e965e4fb80ec"
        ),
        "symbols": [
            "Environment:IsValidTarget",
            "Environment:FindEndpoints",
            "Environment:GetCrossPath",
            "Env_Attack:Start",
        ],
    },
    {
        "path": "scripts/missions/missions.lua",
        "size": 29_573,
        "sha256": (
            "505c02a8668ba2e39d868f95051ede81c6cc1611f1e409219b6caa4fbe1d0257"
        ),
        "symbols": [
            "CreateMission",
            "Mission:GetMapTag",
            "Mission:BaseStart",
            "Mission:GetStartingPawns",
            "Mission:SpawnPawns",
            "Mission:SetupDiffMod",
        ],
    },
    {
        "path": "scripts/missions/final/env_final.lua",
        "size": 4_529,
        "sha256": (
            "8d9220a9f7c0b6f3887ec8b9ffdd351b25cd4c53696d2f401c81dbeb932a6f33"
        ),
        "symbols": ["Env_Final", "Env_Final:Start"],
    },
    {
        "path": "scripts/missions/final/mission_final_two.lua",
        "size": 4_887,
        "sha256": (
            "c8a8e40f512939c1f4fd0e0df416e5cbaec00c639e2985ad776e13c38735b17c"
        ),
        "symbols": [
            "Mission_Final_Cave",
            "SpawnMechs",
            "Mission_Final_Cave:StartMission",
        ],
    },
)


COMMON_DEPLOYMENT = ((3, 3), (3, 4), (2, 4), (2, 3))
MAP_SPECS = (
    {
        "path": "maps/cave1.map",
        "size": 1_591,
        "sha256": (
            "0969e29ad7645fc4758060f8cf5d47fe032e20677cd52387e6f1ab54abe0fc8a"
        ),
        "pylons": ((1, 4), (1, 3), (3, 1), (6, 2), (6, 6), (5, 6), (2, 6)),
        "mountain": ((7, 6), (6, 1), (1, 7), (0, 5)),
    },
    {
        "path": "maps/cave2.map",
        "size": 1_656,
        "sha256": (
            "a5f49331e09055f65b57e16e185638586869b1984fdb36c43312440bead63ba4"
        ),
        "pylons": ((1, 5), (0, 5), (4, 5), (6, 6), (6, 1), (5, 1), (2, 2)),
        "mountain": ((7, 6), (5, 4), (1, 7)),
    },
    {
        "path": "maps/cave3.map",
        "size": 1_610,
        "sha256": (
            "6731d53830bce7e367b6587f8b49f2306840a200091024e8586a393d150cd228"
        ),
        "pylons": ((1, 6), (4, 5), (5, 7), (4, 7), (6, 3), (1, 1), (5, 1)),
        "mountain": ((1, 7), (3, 6), (5, 0), (7, 2)),
    },
    {
        "path": "maps/cave4.map",
        "size": 1_627,
        "sha256": (
            "d2b651d5277fd5fdd985cf203c7c16cbd4f2ea70f4fb6b624654031dc0ea1654"
        ),
        "pylons": ((4, 5), (5, 7), (6, 3), (1, 5), (0, 3), (6, 1), (3, 0)),
        "mountain": ((1, 6), (2, 7), (7, 3), (2, 1)),
    },
    {
        "path": "maps/cave5.map",
        "size": 1_654,
        "sha256": (
            "447fb1b56c70e6d333d9e7c10f119ce1b4018a67d79efd92352693ea9ee77004"
        ),
        "pylons": ((7, 4), (1, 1), (5, 6), (3, 1), (4, 1), (1, 5), (1, 6)),
        "mountain": ((2, 7), (6, 6), (7, 2), (3, 0)),
    },
    {
        "path": "maps/caveAE1.map",
        "size": 1_663,
        "sha256": (
            "d65a49baefbbb7c53af6cff4363441073777d49df06c8513d05e371f48f7f1c0"
        ),
        "pylons": ((6, 6), (4, 5), (6, 3), (1, 6), (1, 5), (6, 1), (1, 1)),
        "mountain": ((7, 6), (1, 7), (0, 5), (5, 3)),
    },
    {
        "path": "maps/caveAE2.map",
        "size": 1_757,
        "sha256": (
            "d38c016d487154c2d897aa00d102b585aa9a59bc3e6ef17dccaeb62d47677679"
        ),
        "pylons": ((1, 6), (3, 6), (1, 2), (6, 3), (6, 2), (5, 5), (4, 1)),
        "mountain": ((6, 0), (0, 3), (4, 3)),
    },
    {
        "path": "maps/caveAE3.map",
        "size": 1_682,
        "sha256": (
            "62245dd2017b7ad3b00d86b9b8c203f4e335857a77d935b92d2511aa96b5c7e9"
        ),
        "pylons": ((5, 6), (3, 1), (4, 1), (1, 5), (3, 6), (6, 4), (6, 3)),
        "mountain": ((5, 0), (0, 2), (1, 1)),
    },
    {
        "path": "maps/caveAE4.map",
        "size": 1_728,
        "sha256": (
            "dfb7ab98d97890cf89240832d1e1ca541e71e9da1c4de34d42b4b8581999e052"
        ),
        "pylons": ((1, 5), (5, 4), (5, 3), (6, 1), (3, 1), (2, 1), (6, 6)),
        "mountain": ((7, 5), (7, 4), (1, 0)),
    },
)


REGION_SPECS = (
    {
        "id": "phase_transition",
        "start": 0x001891D0,
        "end": 0x0018964D,
        "sha256": (
            "3a5b364d9af48610bb07f8e44d5cb9ddb4051f4cb4a5fa0ad0db8eb51522073f"
        ),
    },
    {
        "id": "map_selector",
        "start": 0x00182AF0,
        "end": 0x00182F26,
        "sha256": (
            "c6190e9784cd302c39f0784bd263c9112c277522cd8e1fc54694b85a383a3761"
        ),
    },
    {
        "id": "map_loader",
        "start": 0x001658F0,
        "end": 0x00165BDD,
        "sha256": (
            "1fd6e2beb3c3743510c0aeccfbf6a32701f09f74f0ab1c44f0519ff287d65e38"
        ),
    },
    {
        "id": "base_start_dispatch",
        "start": 0x001831C0,
        "end": 0x0018334F,
        "sha256": (
            "fe91da3c9574d19e0e017385e9c5dfb1b47c3a9ef22ef009edb5ac92d1e162ec"
        ),
    },
    {
        "id": "phase_named_invoker",
        "start": 0x00197020,
        "end": 0x001970E5,
        "sha256": (
            "8bef18ab0d4307aaf94a837b8780bf81c7d21d4456839ccecf1ddbef141b5b5d"
        ),
    },
    {
        "id": "mission_named_invoker",
        "start": 0x00199900,
        "end": 0x00199998,
        "sha256": (
            "f104b8d01a7d8904631d4481f8c46efca50e906ff1ba29e34f980df21dde3ac6"
        ),
    },
)


STRING_ANCHOR_SPECS = (
    {
        "id": "create_next_phase",
        "region_id": "phase_transition",
        "reference_rva": 0x0018949D,
        "instruction_hex": "68dcf78200",
        "string_rva": 0x0042F7DC,
        "text": "CreateNextPhase",
        "role": "phase-construction callback",
    },
    {
        "id": "get_map_tag",
        "region_id": "map_selector",
        "reference_rva": 0x00182B84,
        "instruction_hex": "68e4f18200",
        "string_rva": 0x0042F1E4,
        "text": "GetMapTag",
        "role": "mission map-tag callback",
    },
    {
        "id": "get_map_vetoes",
        "region_id": "map_selector",
        "reference_rva": 0x00182BE0,
        "instruction_hex": "680cf28200",
        "string_rva": 0x0042F20C,
        "text": "GetMapVetoes",
        "role": "mission map-veto callback",
    },
    {
        "id": "get_map",
        "region_id": "map_selector",
        "reference_rva": 0x00182C5C,
        "instruction_hex": "6804f28200",
        "string_rva": 0x0042F204,
        "text": "GetMap",
        "role": "empty-tag explicit-map fallback",
    },
    {
        "id": "random_map",
        "region_id": "map_selector",
        "reference_rva": 0x00182D25,
        "instruction_hex": "6828f28200",
        "string_rva": 0x0042F228,
        "text": "RandomMap",
        "role": "nonempty-tag native map selection",
    },
    {
        "id": "add_map",
        "region_id": "map_loader",
        "reference_rva": 0x00165AAB,
        "instruction_hex": "6820e68200",
        "string_rva": 0x0042E620,
        "text": "AddMap",
        "role": "map registration/loading callback",
    },
    {
        "id": "base_start",
        "region_id": "base_start_dispatch",
        "reference_rva": 0x00183277,
        "instruction_hex": "6844f28200",
        "string_rva": 0x0042F244,
        "text": "BaseStart",
        "role": "mission startup callback",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "post_create_native_order",
        "region_id": "phase_transition",
        "start_rva": 0x001894E0,
        "instruction_hex": (
            "e83bdb000083ec188bf483ec188bcc6a00c741140f000000c7411000000000"
            "68dcdf8000c60100e8c4eae7ff568bcbe8dc95ffff8b4b04e8d4c3fdff6a"
            "028bcbe8ab8000008bcbe8e41e000083ec4c8d45a48bcc50e89631faff8b"
            "cbe81fa7ffff8bcbe8789cffff"
        ),
        "meaning": (
            "After CreateNextPhase returns, call map_selector, map_loader, "
            "intermediate board initialization, and base_start_dispatch in "
            "that relative order."
        ),
    },
    {
        "id": "map_tag_and_veto_callbacks",
        "region_id": "map_selector",
        "start_rva": 0x00182B7C,
        "instruction_hex": (
            "83ec188bcc8965a868e4f18200e88252e8ff83ec18c645fc028bcc8d9ed40f"
            "0000895d94c741140f000000c74110000000008379141072048b01eb028bc1"
            "6aff6a0053c60000e80955e8ff8d45bcc645fc0150e86cf6faff83ec18c645"
            "fc038bcc8965a8680cf28200e82652e8ff83ec18c645fc048bccc741140f00"
            "0000c74110000000008379141072048b01eb028bc16aff6a0053c60000e8b6"
            "54e8ff8d459cc645fc0350e879400100c645fc05"
        ),
        "meaning": "Obtain GetMapTag before GetMapVetoes for the current mission.",
    },
    {
        "id": "nonempty_tag_random_map_branch",
        "region_id": "map_selector",
        "start_rva": 0x00182C32,
        "instruction_hex": (
            "83ec18837dcc008bcc8965b0c741140f000000c7411000000000755f837914"
            "1072048b01eb028bc16a066804f28200c60000e86753e8ff83ec18c645fc06"
            "8bccc741140f000000c74110000000008379141072048b01eb028bc16aff6a"
            "0053c60000e83754e8ff8d45d4c645fc0550e89af5faff8bf0e99900000083"
            "79141072048b01eb028bc16aff6a006878688d00c60000e80654e8ff83ec18"
            "c645fc088bcc8965b4c741140f000000c74110000000008379141072048b01"
            "eb028bc16affc600008d45bc6a0050e8d053e8ff83ec18c645fc098bccc741"
            "140f000000c74110000000008379141072048b01eb028bc16a096828f28200"
            "c60000e89e52e8ff8d45d4c645fc0550b9a8578900e85ca9f8ff8bf0"
        ),
        "meaning": (
            "Use GetMap only for an empty tag; a nonempty tag takes the "
            "RandomMap path."
        ),
    },
    {
        "id": "add_map_dispatch",
        "region_id": "map_loader",
        "start_rva": 0x00165A9D,
        "instruction_hex": (
            "e82e26eaff83ec18c645fc048bcc6820e68200e85b23eaff8d45a8c645fc00"
            "50b9a8578900e8694ffdff"
        ),
        "meaning": "Dispatch AddMap while loading the selected map.",
    },
    {
        "id": "base_start_named_dispatch",
        "region_id": "base_start_dispatch",
        "start_rva": 0x00183259,
        "instruction_hex": (
            "8bccc741140f000000c74110000000008379141072048b01eb028bc16a0968"
            "44f28200c60000e84c4de8ff83ec18c745fc000000008bcc8dbed40f0000c7"
            "41140f000000c74110000000008379141072048b01eb028bc16aff6a0057c6"
            "0000e8134ee8ffc745fcffffffffe837660100"
        ),
        "meaning": "Construct BaseStart and dispatch it on the current mission.",
    },
)


DIRECT_EDGE_SPECS = (
    {
        "id": "phase_to_create_next_invoker",
        "source_region": "phase_transition",
        "from_rva": 0x001894E0,
        "instruction_hex": "e83bdb0000",
        "target_region": "phase_named_invoker",
        "target_rva": 0x00197020,
    },
    {
        "id": "phase_to_map_selector",
        "source_region": "phase_transition",
        "from_rva": 0x0018950F,
        "instruction_hex": "e8dc95ffff",
        "target_region": "map_selector",
        "target_rva": 0x00182AF0,
    },
    {
        "id": "phase_to_map_loader",
        "source_region": "phase_transition",
        "from_rva": 0x00189517,
        "instruction_hex": "e8d4c3fdff",
        "target_region": "map_loader",
        "target_rva": 0x001658F0,
    },
    {
        "id": "phase_to_base_start_dispatch",
        "source_region": "phase_transition",
        "from_rva": 0x00189543,
        "instruction_hex": "e8789cffff",
        "target_region": "base_start_dispatch",
        "target_rva": 0x001831C0,
    },
    {
        "id": "base_start_to_named_invoker",
        "source_region": "base_start_dispatch",
        "from_rva": 0x001832C4,
        "instruction_hex": "e837660100",
        "target_region": "mission_named_invoker",
        "target_rva": 0x00199900,
    },
)


_POINT_RE = re.compile(r"Point\(\s*(\d+)\s*,\s*(\d+)\s*\)")


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise FinalCaveStartupError(
            f"RVA 0x{rva:08x} is not contiguous file-backed data"
        )
    section = next(
        (
            candidate
            for candidate in image.sections
            if candidate.virtual_address <= rva
            and rva + size
            <= candidate.virtual_address + candidate.raw_size
        ),
        None,
    )
    if section is None or not section.executable:
        raise FinalCaveStartupError(
            f"RVA 0x{rva:08x} is not executable file-backed data"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise FinalCaveStartupError(
            f"RVA 0x{rva:08x} is not an E8 rel32 call"
        )
    delta = struct.unpack_from("<i", encoded, 1)[0]
    return (rva + 5 + delta) & 0xFFFFFFFF


def _points(body: str, label: str) -> tuple[tuple[int, int], ...]:
    result = tuple((int(x), int(y)) for x, y in _POINT_RE.findall(body))
    if len(result) != len(set(result)) or any(
        not (0 <= x < 8 and 0 <= y < 8) for x, y in result
    ):
        raise FinalCaveStartupError(f"invalid or duplicate points in {label}")
    return result


def _parse_map(data: bytes, path: str) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FinalCaveStartupError(f"map is not UTF-8: {path}") from exc
    name = Path(path).stem
    if not re.match(rf"^{re.escape(name)}\s*=\s*\{{", text):
        raise FinalCaveStartupError(f"map root name differs: {path}")
    tags_match = re.search(r'\["tags"\]\s*=\s*\{([^}]*)\}', text)
    if tags_match is None:
        raise FinalCaveStartupError(f"map tags are missing: {path}")
    tags = tuple(re.findall(r'"([^"]+)"', tags_match.group(1)))
    zones: dict[str, tuple[tuple[int, int], ...]] = {}
    for zone in ("pylons", "deployment", "mountain"):
        match = re.search(
            rf'\["{zone}"\]\s*=\s*\{{([^}}]*)\}}',
            text,
        )
        if match is None:
            raise FinalCaveStartupError(f"map zone {zone} is missing: {path}")
        zones[zone] = _points(match.group(1), f"{path}:{zone}")
    return {"tags": tags, "zones": zones}


def _expected_sources() -> list[dict[str, Any]]:
    return [
        {
            "path": spec["path"],
            "size": spec["size"],
            "sha256": spec["sha256"],
            "symbols": spec["symbols"],
            "evidence_class": "fact",
        }
        for spec in LUA_SOURCE_SPECS
    ]


def _expected_maps() -> list[dict[str, Any]]:
    return [
        {
            "path": spec["path"],
            "size": spec["size"],
            "sha256": spec["sha256"],
            "tags": ["final_cave", "volcano"],
            "zones": {
                "deployment": [list(point) for point in COMMON_DEPLOYMENT],
                "mountain": [list(point) for point in spec["mountain"]],
                "pylons": [list(point) for point in spec["pylons"]],
            },
            "evidence_class": "fact",
        }
        for spec in MAP_SPECS
    ]


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
            "boundary_basis": (
                "Ghidra 12.1.3 function body corroborated by complete "
                "Capstone 5.0.7 decoding from the reviewed entry."
            ),
        }
        for spec in REGION_SPECS
    ]


def _expected_anchors() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region_id": spec["region_id"],
            "evidence_class": "fact",
            "reference_rva": f"0x{spec['reference_rva']:08x}",
            "instruction_hex": spec["instruction_hex"],
            "string_rva": f"0x{spec['string_rva']:08x}",
            "text": spec["text"],
            "role": spec["role"],
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
            "target_region": spec["target_region"],
            "target_rva": f"0x{spec['target_rva']:08x}",
            "evidence_class": "fact",
        }
        for spec in DIRECT_EDGE_SPECS
    ]


def _rng_schedule() -> list[dict[str, Any]]:
    return [
        {
            "order": 1,
            "scope": "Mission:GetMapTag",
            "family": "random_int",
            "bounds": [1],
            "occurrence": "exactly once",
            "meaning": (
                "random_element over the one-entry MapTags table selects "
                "final_cave; whether random_int(1) advances native state is open."
            ),
        },
        {
            "order": 2,
            "scope": "native RandomMap",
            "family": "native map-selection RNG",
            "bounds": None,
            "occurrence": "opaque native selection",
            "meaning": (
                "Choose from the exact tag-matching installed pool subject "
                "to native edition/filter/veto policy."
            ),
        },
        {
            "order": 3,
            "scope": "Env_Final:Start/FindEndpoints",
            "family": "random_bool and random_int",
            "bounds": [2, "endpoint_count", "endpoint_count", 2],
            "occurrence": "orientation, two endpoint removals, optional swap",
            "meaning": (
                "Choose cross-path orientation/endpoints before the cave "
                "mission's StartMission callback."
            ),
        },
        {
            "order": 4,
            "scope": "Environment:GetCrossPath loop",
            "family": "random_int",
            "bounds": ["best_step_count"],
            "occurrence": "once per accepted path step",
            "meaning": "Choose among equally close path steps until an endpoint is reached.",
        },
        {
            "order": 5,
            "scope": "Mission_Final_Cave:StartMission bomb tile",
            "family": "random_int",
            "bounds": [4],
            "occurrence": "exactly once",
            "meaning": "Remove the bomb tile from the four deployment tiles.",
        },
        {
            "order": 6,
            "scope": "Mission_Final_Cave:StartMission optional enemy",
            "family": "random_int",
            "bounds": [2],
            "occurrence": "exactly once",
            "meaning": (
                "Result zero invokes NextPawn and SpawnPawn on the bomb tile; "
                "that nested spawn-selection RNG is not statically resolved."
            ),
        },
        {
            "order": 7,
            "scope": "Mission_Final_Cave:StartMission mountain droppers",
            "family": "random_int",
            "bounds": ["mountain_count ... 1"],
            "occurrence": "one removal per map mountain-zone tile",
            "meaning": "Randomize effect-queue order while consuming every mountain-zone tile.",
        },
        {
            "order": 8,
            "scope": "SpawnMechs",
            "family": "random_int",
            "bounds": [3, 2, 1],
            "occurrence": "exactly three removals",
            "meaning": "Assign mech IDs 0, 1, and 2 to the three non-bomb deployment tiles.",
        },
        {
            "order": 9,
            "scope": "Mission_Final_Cave:StartMission pylons",
            "family": "random_int",
            "bounds": [7, 6, 5, 4, 3, 2, 1],
            "occurrence": "exactly seven removals",
            "meaning": "Randomize effect-queue order while consuming every pylon-zone tile.",
        },
        {
            "order": 10,
            "scope": "Mission_Final_Cave:StartMission boss",
            "family": "random_int",
            "bounds": [3],
            "occurrence": "exactly once",
            "meaning": "Choose BeetleBoss, FireflyBoss, or HornetBoss before BaseStart returns.",
        },
        {
            "order": 11,
            "scope": "Mission:SetupDiffMod",
            "family": "conditional Lua RNG",
            "bounds": None,
            "occurrence": "depends on the native-assigned DiffMod",
            "meaning": "Runs after cave StartMission and can consume RNG on easy/hard modifiers.",
        },
        {
            "order": 12,
            "scope": "Mission:SpawnPawns(GetStartingPawns())",
            "family": "native spawn-selection and coordinate RNG",
            "bounds": None,
            "occurrence": "one SpawnPawn call per computed starting count",
            "meaning": "Runs last in BaseStart; exact NextPawn and placement RNG remain open.",
        },
    ]


def _startup_contract() -> dict[str, Any]:
    mountain_counts = {
        Path(spec["path"]).stem: len(spec["mountain"]) for spec in MAP_SPECS
    }
    return {
        "native_order": [
            "GAME.CreateNextPhase",
            "map selection",
            "map loading/AddMap",
            "intermediate board initialization",
            "mission BaseStart",
        ],
        "base_start_order": [
            "Env_Final:new",
            "Env_Final:Start",
            "Mission_Final_Cave:StartMission",
            "Mission:SetupDiffMod",
            "Mission:SpawnPawns(Mission:GetStartingPawns())",
        ],
        "common_deployment_tiles": [list(point) for point in COMMON_DEPLOYMENT],
        "bomb_candidates": [list(point) for point in COMMON_DEPLOYMENT],
        "mech_ids": [0, 1, 2],
        "bomb_and_mech_assignment_permutations": 24,
        "pylon_tiles_per_map": 7,
        "mountain_drop_counts": mountain_counts,
        "boss_candidates": ["BeetleBoss", "FireflyBoss", "HornetBoss"],
        "effect_queue_order": (
            "Cave StartMission queues its combined effect before spawning the "
            "boss; BaseStart then runs SetupDiffMod and ordinary SpawnPawns."
        ),
        "effect_settlement_timing_proven": False,
    }


def _method() -> dict[str, Any]:
    return {
        "boundary_review": (
            "Focused Capstone 5.0.7 disassembly and Ghidra 12.1.3 "
            "function/reference/call-graph review joined CreateNextPhase to "
            "map selection, map loading, and BaseStart."
        ),
        "source_review": (
            "Exact Lua hashes and semantic statements pin BaseStart, "
            "environment path construction, cave startup, and random helpers."
        ),
        "map_review": (
            "The complete exact map-tree revision and every final_cave-tagged "
            "map hash, tag, and startup zone are rechecked."
        ),
        "limitations": [
            "Every native address applies only to the pinned Windows executable.",
            "Static call order does not prove queued-effect settlement time.",
            "The RandomMap algorithm, edition filtering, and concrete choice are not inferred.",
            "The Lua RNG skeleton does not prove native state advancement or nested spawn calls.",
            "macOS and other executable builds require independent native maps.",
        ],
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "native_startup_order",
            "evidence_class": "inference",
            "claim": (
                "On the exact Windows build, phase_transition returns from "
                "CreateNextPhase, selects and loads a map, performs intermediate "
                "board initialization, and then dispatches BaseStart."
            ),
            "supports": [
                "post_create_native_order",
                "phase_to_create_next_invoker",
                "phase_to_map_selector",
                "phase_to_map_loader",
                "phase_to_base_start_dispatch",
                "base_start_to_named_invoker",
            ],
        },
        {
            "id": "final_cave_map_pool",
            "evidence_class": "fact",
            "claim": (
                "The exact map revision contains nine final_cave-tagged maps; "
                "all share the same four deployment tiles and each supplies "
                "seven pylon tiles plus three or four mountain-drop tiles."
            ),
            "supports": [spec["path"] for spec in MAP_SPECS],
        },
        {
            "id": "base_start_source_order",
            "evidence_class": "fact",
            "claim": (
                "Exact Lua runs Env_Final:Start before "
                "Mission_Final_Cave:StartMission, then SetupDiffMod, then "
                "ordinary starting SpawnPawns."
            ),
            "supports": [
                "scripts/missions/missions.lua",
                "scripts/missions/final/env_final.lua",
                "scripts/missions/final/mission_final_two.lua",
            ],
        },
        {
            "id": "startup_rng_skeleton",
            "evidence_class": "fact",
            "claim": (
                "Exact Lua pins the relative random_int/random_bool call "
                "skeleton from the one-entry map tag through environment path, "
                "bomb/mech assignment, dropper order, boss choice, and later "
                "difficulty/start-spawn work."
            ),
            "supports": ["rng_schedule"],
        },
        {
            "id": "center_assignment",
            "evidence_class": "fact",
            "claim": (
                "The bomb consumes one of four center deployment tiles and "
                "mech IDs 0, 1, and 2 consume the other three, producing 24 "
                "source-reachable assignment permutations."
            ),
            "supports": ["startup_contract", "scripts/missions/final/mission_final_two.lua"],
        },
        {
            "id": "solver_boundary",
            "evidence_class": "inference",
            "claim": (
                "No cross-stage Rust forecast is justified yet: native map and "
                "spawn choices plus effect settlement remain unresolved. The "
                "solver should keep detecting the stage change and consuming a "
                "fresh settled bridge state."
            ),
            "supports": [
                "native_startup_order",
                "final_cave_map_pool",
                "startup_rng_skeleton",
            ],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "native_random_map",
            "question": "How does RandomMap filter and choose the concrete cave map?",
            "static_status": (
                "The nonempty-tag branch and exact installed tag pool are pinned; "
                "native edition filtering, call count, and choice are not."
            ),
            "next_evidence": "Map the RandomMap callee or capture a seeded phase transition.",
        },
        {
            "id": "native_rng_state",
            "question": (
                "Which source-level random calls advance native state, including random_int(1)?"
            ),
            "static_status": "Source call order is pinned; native state transitions are not.",
            "next_evidence": "Use a matched seeded trace around one synthetic cave startup.",
        },
        {
            "id": "environment_path_result",
            "question": "Which concrete LavaPath is selected on each cave map?",
            "static_status": (
                "The source algorithm and map revision are exact, but concrete "
                "RNG values and Board predicate results are not replayed here."
            ),
            "next_evidence": "Replay captured RNG values or retain the live LavaPath payload.",
        },
        {
            "id": "spawn_selection_and_coordinates",
            "question": "What are exact NextPawn and SpawnPawn RNG/call-order semantics?",
            "static_status": (
                "The optional pre-bomb spawn, boss call, and final base SpawnPawns "
                "positions in source order are known; nested native behavior is not."
            ),
            "next_evidence": "Join existing spawn-coordinate anchors to a cave startup trace.",
        },
        {
            "id": "startup_effect_settlement",
            "question": (
                "When do queued rock, mech, pylon, and bomb effects settle "
                "relative to boss and ordinary starting spawns?"
            ),
            "static_status": (
                "Board:AddEffect source order is known, but asynchronous queue "
                "execution and reused SpaceDamage copying remain unproven."
            ),
            "next_evidence": "Capture queue depth and board identity through one startup.",
        },
    ]


def _summary() -> dict[str, Any]:
    return {
        "lua_source_count": len(LUA_SOURCE_SPECS),
        "final_cave_map_count": len(MAP_SPECS),
        "region_count": len(REGION_SPECS),
        "string_anchor_count": len(STRING_ANCHOR_SPECS),
        "control_window_count": len(CONTROL_WINDOW_SPECS),
        "direct_edge_count": len(DIRECT_EDGE_SPECS),
        "finding_count": len(_findings()),
        "unresolved_count": len(_unresolved()),
        "relative_startup_order_proven": True,
        "map_pool_proven": True,
        "lua_rng_call_skeleton_proven": True,
        "concrete_rng_outputs_proven": False,
        "effect_settlement_timing_proven": False,
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
            "maps_revision_sha256": EXPECTED_MAPS_REVISION_SHA256,
        },
        "sources": {
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
            "lua_files": _expected_sources(),
            "maps": _expected_maps(),
        },
        "method": _method(),
        "regions": _expected_regions(),
        "string_anchors": _expected_anchors(),
        "control_windows": _expected_windows(),
        "direct_call_edges": _expected_edges(),
        "rng_schedule": _rng_schedule(),
        "startup_contract": _startup_contract(),
        "findings": _findings(),
        "unresolved": _unresolved(),
        "summary": _summary(),
    }


def _verify_lua_sources(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise FinalCaveStartupError("content root is not a directory")
    for spec in LUA_SOURCE_SPECS:
        source = root / Path(spec["path"])
        try:
            resolved = source.resolve(strict=True)
        except OSError as exc:
            raise FinalCaveStartupError(
                f"missing Lua source {spec['path']}"
            ) from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise FinalCaveStartupError(
                f"Lua source escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise FinalCaveStartupError(
                f"Lua source is not a regular non-symlink file: {spec['path']}"
            )
        data = resolved.read_bytes()
        if (
            len(data) != spec["size"]
            or hashlib.sha256(data).hexdigest() != spec["sha256"]
        ):
            raise FinalCaveStartupError(
                f"Lua source identity differs: {spec['path']}"
            )


def _verify_maps(content_root: Path) -> None:
    root = content_root.resolve()
    try:
        manifest = build_manifest(root, "maps")
    except InventoryError as exc:
        raise FinalCaveStartupError(str(exc)) from exc
    if manifest["revision_sha256"] != EXPECTED_MAPS_REVISION_SHA256:
        raise FinalCaveStartupError("maps revision differs")
    manifest_paths = {entry["path"] for entry in manifest["files"]}
    expected_tagged = [spec["path"] for spec in MAP_SPECS]
    observed_tagged: list[str] = []
    for entry in manifest["files"]:
        path = entry["path"]
        if not path.endswith(".map"):
            continue
        data = (root / Path(path)).read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FinalCaveStartupError(f"map is not UTF-8: {path}") from exc
        tags_match = re.search(r'\["tags"\]\s*=\s*\{([^}]*)\}', text)
        if tags_match and "final_cave" in re.findall(
            r'"([^"]+)"', tags_match.group(1)
        ):
            observed_tagged.append(path)
    if sorted(observed_tagged, key=str.casefold) != sorted(
        expected_tagged, key=str.casefold
    ):
        raise FinalCaveStartupError("final_cave-tagged map pool differs")

    for spec in MAP_SPECS:
        if spec["path"] not in manifest_paths:
            raise FinalCaveStartupError(f"missing map {spec['path']}")
        source = root / Path(spec["path"])
        if source.is_symlink() or not source.is_file():
            raise FinalCaveStartupError(
                f"map is not a regular non-symlink file: {spec['path']}"
            )
        data = source.read_bytes()
        if (
            len(data) != spec["size"]
            or hashlib.sha256(data).hexdigest() != spec["sha256"]
        ):
            raise FinalCaveStartupError(f"map identity differs: {spec['path']}")
        parsed = _parse_map(data, spec["path"])
        if parsed != {
            "tags": ("final_cave", "volcano"),
            "zones": {
                "pylons": spec["pylons"],
                "deployment": COMMON_DEPLOYMENT,
                "mountain": spec["mountain"],
            },
        }:
            raise FinalCaveStartupError(f"map semantic fields differ: {spec['path']}")


def build_final_cave_startup_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build Final Cave startup boundary map."""
    data, image, digest = _load_executable(executable)
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise FinalCaveStartupError("executable identity differs")
    _verify_lua_sources(content_root)
    _verify_maps(content_root)

    ranges: dict[str, tuple[int, int]] = {}
    for spec in REGION_SPECS:
        size = spec["end"] - spec["start"]
        try:
            body = _region_bytes(
                image,
                data,
                spec["start"],
                size,
                ".text",
                spec["id"],
            )
        except Exception as exc:
            raise FinalCaveStartupError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise FinalCaveStartupError(f"region {spec['id']} bytes differ")
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise FinalCaveStartupError(str(exc)) from exc

    for spec in STRING_ANCHOR_SPECS:
        text = spec["text"].encode("ascii") + b"\0"
        offset = image.rva_span_to_file_offset(spec["string_rva"], len(text))
        if offset is None or data[offset : offset + len(text)] != text:
            raise FinalCaveStartupError(f"string anchor {spec['id']} differs")
        encoded = bytes.fromhex(spec["instruction_hex"])
        actual = _bytes_at(image, data, spec["reference_rva"], len(encoded))
        if actual != encoded:
            raise FinalCaveStartupError(f"string reference {spec['id']} differs")
        instruction = decoded[spec["region_id"]].get(spec["reference_rva"])
        if instruction is None or instruction[1] != encoded:
            raise FinalCaveStartupError(
                f"string reference {spec['id']} is not an instruction"
            )
        expected_va = image.image_base + spec["string_rva"]
        if struct.pack("<I", expected_va) not in encoded:
            raise FinalCaveStartupError(
                f"string reference {spec['id']} target differs"
            )

    region_specs = {spec["id"]: spec for spec in REGION_SPECS}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["instruction_hex"])
        start = spec["start_rva"]
        if _bytes_at(image, data, start, len(encoded)) != encoded:
            raise FinalCaveStartupError(f"control window {spec['id']} differs")
        region = region_specs[spec["region_id"]]
        if not (region["start"] <= start < start + len(encoded) <= region["end"]):
            raise FinalCaveStartupError(
                f"control window {spec['id']} escapes its region"
            )
        instructions = decoded[spec["region_id"]]
        if start not in instructions:
            raise FinalCaveStartupError(
                f"control window {spec['id']} does not start at an instruction"
            )
        cursor = start
        while cursor < start + len(encoded):
            instruction = instructions.get(cursor)
            if instruction is None:
                raise FinalCaveStartupError(
                    f"control window {spec['id']} crosses undecoded bytes"
                )
            cursor += len(instruction[1])
        if cursor != start + len(encoded):
            raise FinalCaveStartupError(
                f"control window {spec['id']} ends inside an instruction"
            )

    for spec in DIRECT_EDGE_SPECS:
        instruction = decoded[spec["source_region"]].get(spec["from_rva"])
        expected = bytes.fromhex(spec["instruction_hex"])
        if instruction is None or instruction[1] != expected:
            raise FinalCaveStartupError(f"direct edge {spec['id']} bytes differ")
        if _direct_target(spec["from_rva"], expected) != spec["target_rva"]:
            raise FinalCaveStartupError(f"direct edge {spec['id']} target differs")
        if spec["target_rva"] not in decoded[spec["target_region"]]:
            raise FinalCaveStartupError(
                f"direct edge {spec['id']} target is not an instruction"
            )

    ordered_edges = {
        spec["id"]: spec["from_rva"] for spec in DIRECT_EDGE_SPECS
    }
    if not (
        ordered_edges["phase_to_create_next_invoker"]
        < ordered_edges["phase_to_map_selector"]
        < ordered_edges["phase_to_map_loader"]
        < ordered_edges["phase_to_base_start_dispatch"]
    ):
        raise FinalCaveStartupError("phase startup edge order differs")
    return _expected_shape()


def validate_final_cave_startup_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping):
        raise FinalCaveStartupError("startup map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise FinalCaveStartupError("startup map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "relative_startup_order_proven": True,
        "map_pool_proven": True,
        "lua_rng_call_skeleton_proven": True,
        "concrete_rng_outputs_proven": False,
        "simulator_change_required": False,
    }


def validate_final_cave_startup_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject source, map, byte, address, or prose drift."""
    expected = build_final_cave_startup_map(executable, content_root)
    if dict(value) != expected:
        raise FinalCaveStartupError(
            "startup map differs from exact-build analysis"
        )
    result = validate_final_cave_startup_map_binding(value)
    result["status"] = "verified"
    return result


def encode_final_cave_startup_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
