"""Reproduce the exact-build specialized-enemy death boundary.

This continuation closes the specialized-class question left by the native
death event/credit map.  It joins the shipped one-argument ``CreatePawn``
route to the common Pawn constructor and update/death processor, inventories
every active shipped ``Minor=true`` definition and boss objective, and binds
the resulting event-2 predicate to the Rust mission-kill counter.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.death_event_credit_boundary import (
    DeathEventCreditBoundaryError,
    validate_death_event_credit_boundary_map,
)
from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_specialized_enemy_death_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)


class SpecializedEnemyDeathBoundaryError(RuntimeError):
    """Raised when the reviewed specialized-death boundary cannot reproduce."""


DEPENDENCY_SPEC = {
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
        "Pins the generic death processor's non-Mech TEAM_ENEMY/Minor event "
        "split and Mission:BaseUpdate's event-2 KilledVek consumer."
    ),
}


SOURCE_SPECS = (
    {
        "path": "scripts/global.lua",
        "size": 17_363,
        "sha256": "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2",
        "symbols": ["Pawn", "Minor = false", "DefaultTeam = TEAM_NONE"],
    },
    {
        "path": "scripts/pawns.lua",
        "size": 27_397,
        "sha256": "e999b8d98526c1e36f4746dd65b9d9e7ee3ca0b22029ed391d5b71fda49dc239",
        "symbols": ["Blob1", "MantisEgg", "WebbEgg1", "PunchMech"],
    },
    {
        "path": "scripts/advanced/ae_pawns.lua",
        "size": 18_501,
        "sha256": "e87efe90c0342f26969c14159e6b6c93766aeedcbc3319fb0f418048d129e9f4",
        "symbols": ["Totem1", "Totem2", "BonusDebris"],
    },
    {
        "path": "scripts/advanced/bosses/blobber.lua",
        "size": 2_341,
        "sha256": "0044135d2690c28b7f3a4178c010a0e97d12a07873276a2cc735a4331b0f728c",
        "symbols": ["BlobberBoss", "BlobB"],
    },
    {
        "path": "scripts/advanced/bosses/shaman.lua",
        "size": 1_323,
        "sha256": "1f9b4b3ac13b4af02a90351bb6e67e3f0785156e7d909f2f3d04342f32d7578c",
        "symbols": ["ShamanBoss", "TotemB"],
    },
    {
        "path": "scripts/advanced/missions/acid/mission_acidstorm.lua",
        "size": 2_901,
        "sha256": "71d3d80d27ddeee0f05b6f237eaba35e98b5e585d98e67331b0b56a62731f6b8",
        "symbols": ["Storm_Generator"],
    },
    {
        "path": "scripts/advanced/missions/snow/mission_hacking.lua",
        "size": 3_015,
        "sha256": "1d26d25e090ef69854001d48a676657bf049e37b432acf87aebf66936feb0e55",
        "symbols": ["Hacked_Building"],
    },
    {
        "path": "scripts/advanced/missions/snow/mission_shields.lua",
        "size": 3_640,
        "sha256": "43a620c78ab42e4fe94e78ba311086bcc5a28433c0a841ca90cc542447a430d6",
        "symbols": ["Shield_Building"],
    },
    {
        "path": "scripts/missions/acid/mission_barrels.lua",
        "size": 2_555,
        "sha256": "3101ea805315e49e6a098c240f242bea28e39466dd9c41deb253468d93f7fc48",
        "symbols": ["AcidVat"],
    },
    {
        "path": "scripts/missions/bosses/boss.lua",
        "size": 1_701,
        "sha256": "9a957789e714c6d22d2f90bcd79dbb68c897aaa530e23d5be50cf7cf650853f1",
        "symbols": ["Mission_Boss:StartBoss", "PAWN_FACTORY:CreatePawn"],
    },
    {
        "path": "scripts/missions/bosses/goo.lua",
        "size": 4_666,
        "sha256": "f6761a7cad49883fa85e631b3a524a6d56d0d593616aa3e1031b1c65b4bab03b",
        "symbols": ["BlobBoss", "BlobBossMed", "BlobBossSmall"],
    },
    {
        "path": "scripts/missions/bosses/slug.lua",
        "size": 1_654,
        "sha256": "cf93aa66cf65079d55518a446da2bffd85df4a3602c5afdf52bca6ab6c728d52",
        "symbols": ["SlugBoss", "SlugEgg1"],
    },
    {
        "path": "scripts/missions/bosses/spider.lua",
        "size": 3_242,
        "sha256": "f7d81d714922e1b5b22d5b76a8edcb6fb96dd61ae5b20a3008c66b5068046455",
        "symbols": ["SpiderBoss", "SpiderlingEgg1"],
    },
    {
        "path": "scripts/missions/mission_tutorial.lua",
        "size": 8_447,
        "sha256": "8629ce275906d97e3f53172ff7202ff3c59cd10322583c3c391a92621b8bbf39",
        "symbols": ["Tank:SetMech", "Artillery:SetMech", "PunchMech:SetMech"],
    },
    {
        "path": "scripts/missions/snow/mission_botdefense.lua",
        "size": 1_462,
        "sha256": "3b7138e0a0ba821fa46a557f726c94fbba4d7a856a201483873c74e7b06866ef",
        "symbols": ["pawn:SetTeam(TEAM_PLAYER)"],
    },
)


MINOR_OCCURRENCES = (
    ("scripts/advanced/ae_pawns.lua", 250, "Totem1"),
    ("scripts/advanced/ae_pawns.lua", 265, "Totem2"),
    ("scripts/advanced/ae_pawns.lua", 577, "BonusDebris"),
    ("scripts/advanced/bosses/blobber.lua", 57, "BlobB"),
    ("scripts/advanced/bosses/shaman.lua", 48, "TotemB"),
    ("scripts/advanced/missions/acid/mission_acidstorm.lua", 78, "Storm_Generator"),
    ("scripts/advanced/missions/snow/mission_hacking.lua", 86, "Hacked_Building"),
    ("scripts/advanced/missions/snow/mission_shields.lua", 85, "Shield_Building"),
    ("scripts/missions/acid/mission_barrels.lua", 73, "AcidVat"),
    ("scripts/missions/bosses/slug.lua", 59, "SlugEgg1"),
    ("scripts/missions/bosses/spider.lua", 93, "SpiderlingEgg1"),
    ("scripts/pawns.lua", 613, "Blob1"),
    ("scripts/pawns.lua", 629, "Blob2"),
    ("scripts/pawns.lua", 645, "MantisEgg"),
    ("scripts/pawns.lua", 1063, "WebbEgg1"),
    ("scripts/pawns.lua", 1083, "Spiderling1"),
    ("scripts/pawns.lua", 1096, "Spiderling2"),
)


COMMENTED_MINOR_OCCURRENCES = (
    ("scripts/missions/bosses/goo.lua", 66, "BlobBoss"),
    ("scripts/missions/bosses/goo.lua", 127, "BlobBossMed"),
)


BOSS_PAWN_OCCURRENCES = (
    ("scripts/advanced/bosses/blobber.lua", 4, "BlobberBoss"),
    ("scripts/advanced/bosses/bouncer.lua", 5, "BouncerBoss"),
    ("scripts/advanced/bosses/burnbug.lua", 5, "BurnbugBoss"),
    ("scripts/advanced/bosses/centipede.lua", 5, "CentipedeBoss"),
    ("scripts/advanced/bosses/crab.lua", 5, "CrabBoss"),
    ("scripts/advanced/bosses/digger.lua", 4, "DiggerBoss"),
    ("scripts/advanced/bosses/dung.lua", 4, "DungBoss"),
    ("scripts/advanced/bosses/leaper.lua", 4, "LeaperBoss"),
    ("scripts/advanced/bosses/mosquito.lua", 4, "MosquitoBoss"),
    ("scripts/advanced/bosses/scarab.lua", 5, "ScarabBoss"),
    ("scripts/advanced/bosses/shaman.lua", 4, "ShamanBoss"),
    ("scripts/advanced/bosses/starfish.lua", 5, "StarfishBoss"),
    ("scripts/missions/bosses/beetle.lua", 5, "BeetleBoss"),
    ("scripts/missions/bosses/bot.lua", 5, "BotBoss"),
    ("scripts/missions/bosses/firefly.lua", 5, "FireflyBoss"),
    ("scripts/missions/bosses/goo.lua", 8, "BlobBoss"),
    ("scripts/missions/bosses/hornet.lua", 5, "HornetBoss"),
    ("scripts/missions/bosses/psion.lua", 4, "Jelly_Boss"),
    ("scripts/missions/bosses/scorpion.lua", 5, "ScorpionBoss"),
    ("scripts/missions/bosses/slug.lua", 5, "SlugBoss"),
    ("scripts/missions/bosses/spider.lua", 5, "SpiderBoss"),
)


SET_MECH_OCCURRENCES = (
    ("scripts/missions/mission_tutorial.lua", 120, "Tank:SetMech()"),
    ("scripts/missions/mission_tutorial.lua", 129, "Artillery:SetMech()"),
    ("scripts/missions/mission_tutorial.lua", 163, "PunchMech:SetMech()"),
)


SET_TEAM_OCCURRENCES = (
    (
        "scripts/missions/snow/mission_botdefense.lua",
        14,
        "pawn:SetTeam(TEAM_PLAYER)",
    ),
)


REGION_SPECS = (
    {
        "id": "board_master_update",
        "start": 0x0016A8D0,
        "end": 0x0016BF62,
        "sha256": "6d32a302492920ae4353af4505e792776a18c4f9d8c26bd6cf1f9861a6f9129d",
        "basis": "Ghidra 12.1.3 Board master-update body.",
    },
    {
        "id": "pawn_constructor",
        "start": 0x0022A920,
        "end": 0x0022BAC8,
        "sha256": "f358d6de02d4e48a82c3a8d02fe52617cf280ea89bf959dcf0e4c4aadf60887d",
        "basis": "Ghidra 12.1.3 common Pawn constructor body.",
    },
    {
        "id": "pawn_definition_load",
        "start": 0x0022C0F0,
        "end": 0x0022CBB7,
        "sha256": "9c705957ab7a8afa137bb56e4d075b40a29ca8da45222fd318f2c821ac138148",
        "basis": "Ghidra 12.1.3 Pawn Lua-definition loader body.",
    },
    {
        "id": "death_processor",
        "start": 0x0022D5F0,
        "end": 0x0022E325,
        "sha256": "69e9121e9272ec2d865777ba0e7d810202df5f05ec380ab66d40f72445a90737",
        "basis": "Ghidra 12.1.3 common Pawn death processor body.",
    },
    {
        "id": "shared_pawn_update",
        "start": 0x00233EE0,
        "end": 0x00234C70,
        "sha256": "0f061f2c6ad29a87a1f86eb1b9a1d2a0aeb6c995c67c1a3073be67aa50accd0f",
        "basis": "Ghidra 12.1.3 shared Pawn update/death caller body.",
    },
    {
        "id": "pawn_factory",
        "start": 0x00244DF0,
        "end": 0x00244FE0,
        "sha256": "15a9ff7b5140c97a90f9907c90c506d051136da05475580861c2ba557cf88559",
        "basis": "Ghidra 12.1.3 named Pawn factory body.",
    },
    {
        "id": "pawn_factory_wrapper",
        "start": 0x00244FE0,
        "end": 0x00245066,
        "sha256": "f7148da1226256df25b4eb4aa019a4f7ffcf354bac806f6b18e7ead5aa3bf095",
        "basis": "Ghidra 12.1.3 one-argument factory wrapper body.",
    },
    {
        "id": "pawn_factory_construct",
        "start": 0x00245070,
        "end": 0x0024524E,
        "sha256": "a6960b16cf81bfc75671f7901ade8f6dff4e1320e003aa93a7a1a245b3acae7e",
        "basis": "Ghidra 12.1.3 factory allocation/construction helper body.",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "factory_wrapper_uses_default_team_mode",
        "region": "pawn_factory_wrapper",
        "start": 0x00245006,
        "hex": (
            "6a0283ec18c745fc000000008bcc8d45086aff6a00c741140f000000c7411000"
            "00000050c60100e89e30dcff8bcee8b7fdffff"
        ),
        "meaning": "The one-argument wrapper supplies selector 2 and calls the named factory.",
    },
    {
        "id": "factory_resolves_default_team",
        "region": "pawn_factory_construct",
        "start": 0x00245109,
        "hex": (
            "83fe02755083ec188bcc8965ec6834708300e8f02cdcff83ec18c645fc018bccc7"
            "41140f000000c74110000000008379141072048b01eb028bc16affc600008d450c"
            "6a0050e87d2fdcffc645fc00e86443e0ff8bf0"
        ),
        "meaning": "Selector 2 resolves the named definition's GetDefaultTeam value.",
    },
    {
        "id": "factory_allocates_common_pawn",
        "region": "pawn_factory_construct",
        "start": 0x0024515E,
        "hex": (
            "6828130000e8732311008bd8895de883ec14c645fc028bccc741140f000000c741"
            "10000000008379141072048b01eb028bc16affc600008d450c6a0050e8302fdcff"
            "568bcbe87857feff"
        ),
        "meaning": "Allocate 0x1328 bytes and invoke the common Pawn constructor.",
    },
    {
        "id": "pawn_vtable_install",
        "region": "pawn_constructor",
        "start": 0x0022A9BF,
        "hex": "c70620e38200",
        "meaning": "Install the common Pawn vtable at VA 0x0082e320.",
    },
    {
        "id": "pawn_team_constructor_argument",
        "region": "pawn_constructor",
        "start": 0x0022AA08,
        "hex": "89beb0000000",
        "meaning": "Store the resolved constructor team at Pawn+0xb0.",
    },
    {
        "id": "pawn_is_mech_default_false",
        "region": "pawn_constructor",
        "start": 0x0022AF35,
        "hex": "c786e009000005000000c686e409000000",
        "meaning": "Initialize the adjacent field and Pawn+0x9e4 IsMech=false.",
    },
    {
        "id": "pawn_minor_default_false",
        "region": "pawn_constructor",
        "start": 0x0022B2E8,
        "hex": "c786cc10000000000000c686d010000000",
        "meaning": "Initialize the adjacent field and Pawn+0x10d0 Minor=false.",
    },
    {
        "id": "pawn_minor_definition_load",
        "region": "pawn_definition_load",
        "start": 0x0022C4A2,
        "hex": "6a056858608300c60000e81fbbddff8bcfe8f8cee1ff83ec188883d0100000",
        "meaning": "Load Lua Pawn.Minor and store it at Pawn+0x10d0.",
    },
    {
        "id": "shared_update_death_gate",
        "region": "shared_pawn_update",
        "start": 0x002345AF,
        "hex": (
            "80bb2109000000741a83bb440900000074118a836409000084c075078bcbe81e"
            "90ffff"
        ),
        "meaning": "Gate and invoke the sole common death processor from shared Pawn update.",
    },
    {
        "id": "death_is_mech_split",
        "region": "death_processor",
        "start": 0x0022D63D,
        "hex": "8a86e40900008b3d54d28b0089bd18ffffff84c00f84e5010000",
        "meaning": "Read IsMech and enter the ordinary team branch only when it is false.",
    },
    {
        "id": "death_enemy_team_gate",
        "region": "death_processor",
        "start": 0x0022D83C,
        "hex": "8b86b000000083f8060f85e9040000",
        "meaning": "Require Pawn team +0xb0 to equal TEAM_ENEMY (6).",
    },
    {
        "id": "death_enemy_event_minor_split",
        "region": "death_processor",
        "start": 0x0022D93E,
        "hex": "8a86d010000068ffffff7f84c075046a02eb026a0ce838e5e6ff",
        "meaning": "Record event 2 for non-Minor enemies and event 12 for Minor enemies.",
    },
)


DIRECT_EDGE_SPECS = (
    {
        "id": "factory_wrapper_to_factory",
        "source_region": "pawn_factory_wrapper",
        "from": 0x00245034,
        "hex": "e8b7fdffff",
        "target_region": "pawn_factory",
        "target": 0x00244DF0,
    },
    {
        "id": "factory_to_construct_helper",
        "source_region": "pawn_factory",
        "from": 0x00244E56,
        "hex": "e815020000",
        "target_region": "pawn_factory_construct",
        "target": 0x00245070,
    },
    {
        "id": "construct_helper_to_pawn_constructor",
        "source_region": "pawn_factory_construct",
        "from": 0x002451A3,
        "hex": "e87857feff",
        "target_region": "pawn_constructor",
        "target": 0x0022A920,
    },
    {
        "id": "constructor_to_definition_loader",
        "source_region": "pawn_constructor",
        "from": 0x0022B785,
        "hex": "e866090000",
        "target_region": "pawn_definition_load",
        "target": 0x0022C0F0,
    },
    {
        "id": "board_to_shared_pawn_update",
        "source_region": "board_master_update",
        "from": 0x0016B444,
        "hex": "e8978a0c00",
        "target_region": "shared_pawn_update",
        "target": 0x00233EE0,
    },
    {
        "id": "shared_pawn_update_to_death_processor",
        "source_region": "shared_pawn_update",
        "from": 0x002345CD,
        "hex": "e81e90ffff",
        "target_region": "death_processor",
        "target": 0x0022D5F0,
    },
)


CALL_INVENTORY_SPECS = (
    {
        "id": "death_processor_callers",
        "target": 0x0022D5F0,
        "call_sites": [0x002345CD],
    },
    {
        "id": "shared_pawn_update_callers",
        "target": 0x00233EE0,
        "call_sites": [0x0016B444, 0x001EA3A0, 0x001EA510, 0x001EA580],
    },
    {
        "id": "pawn_constructor_callers",
        "target": 0x0022A920,
        "call_sites": [0x0016CE36, 0x002451A3],
    },
)


DATA_ANCHOR_SPEC = {
    "id": "get_default_team_name",
    "rva": 0x00437034,
    "hex": "47657444656661756c745465616d00",
    "meaning": "The factory selector-2 lookup name is GetDefaultTeam.",
}


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise SpecializedEnemyDeathBoundaryError("dependency JSON is not an object")
    return value


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    section = next(
        (
            item
            for item in image.sections
            if item.virtual_address <= rva < item.virtual_address + item.raw_size
        ),
        None,
    )
    if section is None or rva + size > section.virtual_address + section.raw_size:
        raise SpecializedEnemyDeathBoundaryError(
            f"RVA range 0x{rva:08x}+0x{size:x} is not file-backed"
        )
    offset = section.raw_offset + rva - section.virtual_address
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise SpecializedEnemyDeathBoundaryError("direct edge is not rel32 CALL")
    return rva + 5 + struct.unpack("<i", encoded[1:])[0]


def _raw_rel32_call_sites(image: Any, data: bytes, target_rva: int) -> set[int]:
    section = next((item for item in image.sections if item.name == ".text"), None)
    if section is None or not section.executable or not section.raw_size:
        raise SpecializedEnemyDeathBoundaryError("file-backed executable .text missing")
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


def _dependency_record() -> dict[str, str]:
    return dict(DEPENDENCY_SPEC)


def _source_records() -> list[dict[str, Any]]:
    return [dict(spec) for spec in SOURCE_SPECS]


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "start_rva": f"0x{spec['start']:08x}",
            "end_rva_exclusive": f"0x{spec['end']:08x}",
            "size": spec["end"] - spec["start"],
            "sha256": spec["sha256"],
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
            "instruction_hex": spec["hex"],
            "meaning": spec["meaning"],
        }
        for spec in CONTROL_WINDOW_SPECS
    ]


def _direct_edge_records() -> list[dict[str, str]]:
    return [
        {
            "id": spec["id"],
            "source_region": spec["source_region"],
            "from_rva": f"0x{spec['from']:08x}",
            "instruction_hex": spec["hex"],
            "target_region": spec["target_region"],
            "target_rva": f"0x{spec['target']:08x}",
        }
        for spec in DIRECT_EDGE_SPECS
    ]


def _call_inventory_records() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "target_rva": f"0x{spec['target']:08x}",
            "direct_call_sites": [
                f"0x{item:08x}" for item in spec["call_sites"]
            ],
            "complete_raw_rel32_inventory": True,
        }
        for spec in CALL_INVENTORY_SPECS
    ]


def _source_inventory() -> dict[str, Any]:
    minor_types = [item[2] for item in MINOR_OCCURRENCES]
    boss_types = [item[2] for item in BOSS_PAWN_OCCURRENCES]
    return {
        "global_minor_default": False,
        "active_minor_occurrences": [
            {"path": path, "line": line, "pawn_type": pawn_type}
            for path, line, pawn_type in MINOR_OCCURRENCES
        ],
        "active_minor_types": minor_types,
        "active_minor_type_count": len(minor_types),
        "minor_derived_child_types": [],
        "commented_non_effective_minor_occurrences": [
            {"path": path, "line": line, "pawn_type": pawn_type}
            for path, line, pawn_type in COMMENTED_MINOR_OCCURRENCES
        ],
        "boss_objective_occurrences": [
            {"path": path, "line": line, "pawn_type": pawn_type}
            for path, line, pawn_type in BOSS_PAWN_OCCURRENCES
        ],
        "boss_objective_types": boss_types,
        "boss_objective_type_count": len(boss_types),
        "boss_objective_minor_types": [],
        "minor_boss_auxiliary_types": [
            "BlobB",
            "TotemB",
            "SlugEgg1",
            "SpiderlingEgg1",
        ],
        "blob_boss_counting_forms": ["BlobBoss", "BlobBossMed", "BlobBossSmall"],
        "set_mech_occurrences": [
            {"path": path, "line": line, "source": source}
            for path, line, source in SET_MECH_OCCURRENCES
        ],
        "set_team_occurrences": [
            {"path": path, "line": line, "source": source}
            for path, line, source in SET_TEAM_OCCURRENCES
        ],
        "set_team_enemy_occurrences": [],
        "enemy_team_mech_construction_reachable_in_shipped_lua": False,
    }


def _contracts() -> dict[str, Any]:
    return {
        "generic_factory_path": {
            "source_call": "PAWN_FACTORY:CreatePawn(self:GetBossPawn())",
            "one_argument_wrapper_rva": "0x00244fe0",
            "wrapper_team_selector": 2,
            "team_lookup_name": "GetDefaultTeam",
            "allocated_object_size": 0x1328,
            "common_pawn_vtable_va": "0x0082e320",
            "common_pawn_constructor_rva": "0x0022a920",
            "is_mech_default": False,
            "minor_default": False,
            "lua_minor_loaded_after_defaults": True,
            "hidden_boss_subclass_on_reviewed_path": False,
        },
        "death_dispatch": {
            "normal_board_update_reaches_shared_pawn_update": True,
            "shared_pawn_update_death_processor_call_sites": 1,
            "death_processor_direct_call_sites": ["0x002345cd"],
            "death_processor_is_common": True,
        },
        "ordinary_enemy_event_predicate": {
            "scope": "a Pawn death that reaches the common death processor",
            "event_2_name": "EVENT_ENEMY_KILLED",
            "event_2_id": 2,
            "event_2_required_is_mech_value": False,
            "event_2_required_team_value": 6,
            "event_2_required_minor_value": False,
            "minor_enemy_event_id": 12,
            "mech_branch_is_separate": True,
            "leader_flag_is_a_gate": False,
            "tier_flag_is_a_gate": False,
            "pawn_type_name_is_a_gate": False,
        },
        "specialized_results": {
            "boss_objectives_emit_event_2_on_ordinary_death": True,
            "ordinary_leaders_and_psions_use_the_same_predicate": True,
            "blob_boss_each_nonminor_form_emits_event_2": True,
            "minor_boss_auxiliaries_emit_event_12_not_event_2": True,
            "all_other_active_minor_types_emit_event_12_not_event_2": True,
        },
        "solver_conformance": {
            "bridge_fields": ["team", "mech", "minor"],
            "rust_predicate": "enemy && !is_mech && !minor",
            "mission_acid_tank_extra_filter": "acid",
            "pre_v407_discrepancy": "enemy-team IS_MECH units were counted",
            "shipped_lua_reaches_discrepant_state": False,
            "fixed_in_simulator_version": 407,
            "simulator_version_bump_required": True,
            "failure_corpus_archive": (
                "recordings/failure_db_snapshot_sim_v406.jsonl"
            ),
            "failure_corpus_archive_size": 5_950_022,
            "failure_corpus_archive_sha256": (
                "c3ec8cb98534ddb8a394dd860851bf123d6cd502d676651a11692c3d9576dfc8"
            ),
        },
    }


def _findings() -> list[dict[str, str]]:
    return [
        {
            "id": "bosses_use_common_pawn_factory",
            "classification": "fact",
            "claim": (
                "Mission_Boss:StartBoss calls the one-argument named Pawn factory. "
                "That wrapper selects GetDefaultTeam, allocates one common 0x1328-byte "
                "Pawn object, installs the common Pawn vtable, and loads the Lua definition."
            ),
        },
        {
            "id": "common_death_dispatch",
            "classification": "fact",
            "claim": (
                "Board master update reaches the shared Pawn update. Its guarded death "
                "call is the sole direct caller of the common death processor."
            ),
        },
        {
            "id": "ordinary_enemy_event_predicate",
            "classification": "fact",
            "claim": (
                "The reached ordinary branch requires IsMech=false and team 6, then "
                "emits event 2 for Minor=false or event 12 for Minor=true. No leader, "
                "tier, boss, Psion, or Pawn type-name gate appears in the reviewed body."
            ),
        },
        {
            "id": "exact_shipped_minor_inventory",
            "classification": "fact",
            "claim": (
                "The accepted 153-file Lua tree has exactly 17 active Minor=true Pawn "
                "definitions, no child derived from one of those Minor types, and two "
                "non-effective commented BlobBoss Minor lines."
            ),
        },
        {
            "id": "boss_and_auxiliary_classification",
            "classification": "inference",
            "claim": (
                "All 21 nonempty BossPawn objectives are literal TEAM_ENEMY definitions "
                "that retain the global Minor=false default, so their ordinary deaths "
                "emit event 2. BlobB, TotemB, SlugEgg1, and SpiderlingEgg1 are the four "
                "boss-specific Minor auxiliaries and emit event 12 instead."
            ),
        },
        {
            "id": "blob_split_forms_each_count",
            "classification": "inference",
            "claim": (
                "BlobBossMed and BlobBossSmall inherit the non-Minor BlobBoss definition; "
                "the commented Minor assignments do not execute. Each split form therefore "
                "contributes its own ordinary event-2 death."
            ),
        },
        {
            "id": "rust_enemy_mech_discrepancy_fixed",
            "classification": "fact",
            "claim": (
                "Rust now excludes IS_MECH before mission-kill projection and retains the "
                "Minor and Mission_AcidTank ACID filters. Simulator v407 archives the "
                "pre-change v406 failure corpus."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "mech_death_branch_details",
            "question": "What are every event and pilot-side effect inside the separate Mech death branch?",
            "next_evidence": "Map that branch only if a solver feature needs more than its proven event-2 exclusion.",
        },
        {
            "id": "modded_specialized_pawns",
            "question": "Do installed mods create enemy-team Mechs or mutate Minor after construction?",
            "next_evidence": "Inventory a specific modded content tree before claiming its classifications.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do macOS and other depots use the same factory and death predicate?",
            "next_evidence": "Repeat this build-keyed map against another exact executable and scripts revision.",
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
        "dependency": _dependency_record(),
        "sources": _source_records(),
        "source_inventory": _source_inventory(),
        "regions": _region_records(),
        "control_windows": _control_window_records(),
        "direct_edges": _direct_edge_records(),
        "call_inventories": _call_inventory_records(),
        "data_anchor": {
            "id": DATA_ANCHOR_SPEC["id"],
            "rva": f"0x{DATA_ANCHOR_SPEC['rva']:08x}",
            "size": len(bytes.fromhex(DATA_ANCHOR_SPEC["hex"])),
            "hex": DATA_ANCHOR_SPEC["hex"],
            "meaning": DATA_ANCHOR_SPEC["meaning"],
        },
        "contracts": _contracts(),
        "findings": findings,
        "refines": {
            "artifact": DEPENDENCY_SPEC["path"],
            "resolved_unresolved_ids": ["specialized_enemy_death_classes"],
            "specialized_enemy_death_classes_proven": True,
        },
        "unresolved": unresolved,
        "solver_impact": {
            "simulator_contradiction_found": True,
            "contradiction_scope": "enemy-team IS_MECH mission-kill projection",
            "contradictory_state_reachable_in_shipped_lua": False,
            "simulator_change_applied": True,
            "simulator_version": 407,
            "changed_predicate": (
                "rust_solver/src/board.rs::unit_counts_for_mission_kill"
            ),
            "version_pins": [
                "rust_solver/src/lib.rs::SIMULATOR_VERSION",
                "src/solver/verify.py::SIMULATOR_VERSION",
            ],
        },
        "notes": [
            "This is exact-build static evidence, not a runtime trace.",
            "Event classifications apply after the common death processor is reached.",
            "Shipped-source reachability does not weaken the exact native IsMech predicate.",
            "The source inventory covers the accepted unmodified shipped Lua tree, not mods.",
        ],
        "summary": {
            "dependency_count": 1,
            "source_count": len(SOURCE_SPECS),
            "region_count": len(REGION_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "call_inventory_count": len(CALL_INVENTORY_SPECS),
            "data_anchor_count": 1,
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "active_minor_type_count": len(MINOR_OCCURRENCES),
            "boss_objective_type_count": len(BOSS_PAWN_OCCURRENCES),
            "minor_boss_auxiliary_type_count": 4,
            "generic_factory_path_proven": True,
            "specialized_enemy_death_classes_proven": True,
            "simulator_contradiction_found": True,
            "simulator_change_applied": True,
            "simulator_version": 407,
        },
    }


def _verify_dependency(executable: Path, content_root: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    path = repository_root / DEPENDENCY_SPEC["path"]
    if path.is_symlink() or not path.is_file():
        raise SpecializedEnemyDeathBoundaryError("death-event dependency missing")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DEPENDENCY_SPEC["file_sha256"]:
        raise SpecializedEnemyDeathBoundaryError("death-event dependency file differs")
    value = _read_json(path)
    if _canonical_sha256(value) != DEPENDENCY_SPEC["canonical_sha256"]:
        raise SpecializedEnemyDeathBoundaryError("death-event dependency fields differ")
    try:
        validate_death_event_credit_boundary_map(executable, content_root, value)
    except DeathEventCreditBoundaryError as exc:
        raise SpecializedEnemyDeathBoundaryError(
            f"death-event dependency does not reproduce: {exc}"
        ) from exc


def _line_code(line: str) -> str:
    """Return the code before a Lua single-line comment."""
    return line.split("--", 1)[0]


def _definition_block(text: str, pawn_type: str) -> str:
    declaration = re.search(
        rf"(?m)^[ \t]*{re.escape(pawn_type)}[ \t]*=[ \t\r\n]*\{{",
        text,
    )
    if declaration is None:
        raise SpecializedEnemyDeathBoundaryError(
            f"literal boss definition missing: {pawn_type}"
        )
    registration = re.search(
        rf"AddPawn(?:Name)?\([ \t]*[\"']{re.escape(pawn_type)}[\"'][ \t]*\)",
        text[declaration.start() :],
    )
    if registration is None:
        raise SpecializedEnemyDeathBoundaryError(
            f"boss registration missing: {pawn_type}"
        )
    end = declaration.start() + registration.end()
    return text[declaration.start() : end]


def _verify_sources(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise SpecializedEnemyDeathBoundaryError("content root is not a directory")

    selected: dict[str, str] = {}
    for spec in SOURCE_SPECS:
        source = root / Path(spec["path"])
        try:
            resolved = source.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise SpecializedEnemyDeathBoundaryError(
                f"source is missing or escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise SpecializedEnemyDeathBoundaryError(
                f"source is not a regular non-symlink file: {spec['path']}"
            )
        raw = resolved.read_bytes()
        if (
            len(raw) != spec["size"]
            or hashlib.sha256(raw).hexdigest() != spec["sha256"]
        ):
            raise SpecializedEnemyDeathBoundaryError(f"source differs: {spec['path']}")
        selected[spec["path"]] = raw.decode("utf-8")

    scripts_root = root / "scripts"
    lua_paths = sorted(
        (
            path
            for path in scripts_root.rglob("*.lua")
            if path.is_file() and not path.is_symlink()
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if len(lua_paths) != 153:
        raise SpecializedEnemyDeathBoundaryError("accepted-tree Lua file count differs")

    all_text: dict[str, str] = {}
    minor_actual: list[tuple[str, int]] = []
    boss_actual: list[tuple[str, int, str]] = []
    set_mech_actual: list[tuple[str, int, str]] = []
    set_team_actual: list[tuple[str, int, str]] = []
    active_text_parts: list[str] = []
    active_mech_property: list[tuple[str, int]] = []
    for path in lua_paths:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        all_text[relative] = text
        active_lines: list[str] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            code = _line_code(line)
            active_lines.append(code)
            if re.search(r"\bMinor\s*=\s*true\b", code):
                minor_actual.append((relative, line_number))
            boss_match = re.search(r"\bBossPawn\s*=\s*[\"']([^\"']*)[\"']", code)
            if boss_match and boss_match.group(1):
                boss_actual.append((relative, line_number, boss_match.group(1)))
            if re.search(r":\s*SetMech\s*\(", code):
                set_mech_actual.append((relative, line_number, code.strip()))
            if re.search(r":\s*SetTeam\s*\(", code):
                set_team_actual.append((relative, line_number, code.strip()))
            if re.search(r"\bMech\s*=\s*true\b", code):
                active_mech_property.append((relative, line_number))
        active_text_parts.append("\n".join(active_lines))

    if minor_actual != [(path, line) for path, line, _ in MINOR_OCCURRENCES]:
        raise SpecializedEnemyDeathBoundaryError("active Minor=true inventory differs")
    if boss_actual != list(BOSS_PAWN_OCCURRENCES):
        raise SpecializedEnemyDeathBoundaryError("BossPawn inventory differs")
    if set_mech_actual != list(SET_MECH_OCCURRENCES):
        raise SpecializedEnemyDeathBoundaryError("SetMech inventory differs")
    if set_team_actual != list(SET_TEAM_OCCURRENCES):
        raise SpecializedEnemyDeathBoundaryError("SetTeam inventory differs")
    if active_mech_property:
        raise SpecializedEnemyDeathBoundaryError("active Lua Mech=true property appeared")
    if any("TEAM_ENEMY" in source for _, _, source in set_team_actual):
        raise SpecializedEnemyDeathBoundaryError("enemy-team mutation appeared")

    for path, line_number, pawn_type in MINOR_OCCURRENCES:
        lines = all_text[path].splitlines()
        lower = max(0, line_number - 15)
        declaration = re.compile(rf"^[ \t]*{re.escape(pawn_type)}[ \t]*=")
        if not any(declaration.search(line) for line in lines[lower:line_number]):
            raise SpecializedEnemyDeathBoundaryError(
                f"Minor definition owner differs: {pawn_type}"
            )

    global_lua = selected["scripts/global.lua"]
    if not re.search(r"(?m)^[ \t]*Minor[ \t]*=[ \t]*false,", global_lua):
        raise SpecializedEnemyDeathBoundaryError("global Pawn Minor default differs")

    active_joined = "\n".join(active_text_parts)
    for _, _, minor_type in MINOR_OCCURRENCES:
        child = re.search(
            rf"(?m)^[ \t]*[A-Za-z_]\w*[ \t]*=[ \t\r\n]*"
            rf"{re.escape(minor_type)}[ \t]*:[ \t]*new[ \t]*\{{",
            active_joined,
        )
        if child is not None:
            raise SpecializedEnemyDeathBoundaryError(
                f"Minor-derived child appeared: {minor_type}"
            )

    boss_types = {item[2] for item in BOSS_PAWN_OCCURRENCES}
    minor_types = {item[2] for item in MINOR_OCCURRENCES}
    if boss_types & minor_types:
        raise SpecializedEnemyDeathBoundaryError("BossPawn unexpectedly marked Minor")
    for path, _line, pawn_type in BOSS_PAWN_OCCURRENCES:
        block = _definition_block(all_text[path], pawn_type)
        active_block = "\n".join(_line_code(line) for line in block.splitlines())
        if not re.search(r"\bDefaultTeam\s*=\s*TEAM_ENEMY\b", active_block):
            raise SpecializedEnemyDeathBoundaryError(
                f"boss team differs: {pawn_type}"
            )
        if re.search(r"\bMinor\s*=\s*true\b", active_block):
            raise SpecializedEnemyDeathBoundaryError(
                f"boss unexpectedly Minor: {pawn_type}"
            )

    goo = selected["scripts/missions/bosses/goo.lua"]
    for child in ("BlobBossMed", "BlobBossSmall"):
        if not re.search(
            rf"(?m)^[ \t]*{child}[ \t]*=[ \t]*BlobBoss:new\{{",
            goo,
        ):
            raise SpecializedEnemyDeathBoundaryError(
                f"Blob boss inheritance differs: {child}"
            )
    commented_minor_actual = [
        ("scripts/missions/bosses/goo.lua", number, owner)
        for number, owner in ((66, "BlobBoss"), (127, "BlobBossMed"))
        if "--Minor = true" in goo.splitlines()[number - 1]
    ]
    if commented_minor_actual != list(COMMENTED_MINOR_OCCURRENCES):
        raise SpecializedEnemyDeathBoundaryError("commented BlobBoss Minor lines differ")

    boss_base = selected["scripts/missions/bosses/boss.lua"]
    required_boss_route = (
        "function Mission_Boss:StartBoss()",
        "local pawn = PAWN_FACTORY:CreatePawn(self:GetBossPawn())",
        "Board:AddPawn(pawn)",
    )
    if any(token not in boss_base for token in required_boss_route):
        raise SpecializedEnemyDeathBoundaryError("Mission_Boss factory route differs")

    pawns = selected["scripts/pawns.lua"]
    for mech_type in ("PunchMech", "TankMech", "ArtiMech"):
        block = _definition_block(pawns, mech_type)
        if not re.search(r"\bDefaultTeam\s*=\s*TEAM_PLAYER\b", block):
            raise SpecializedEnemyDeathBoundaryError(
                f"tutorial Mech team differs: {mech_type}"
            )


def build_specialized_enemy_death_boundary_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build specialized-enemy death boundary."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise SpecializedEnemyDeathBoundaryError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise SpecializedEnemyDeathBoundaryError("executable identity differs")

    _verify_dependency(executable, content_root)
    _verify_sources(content_root)

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
            raise SpecializedEnemyDeathBoundaryError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise SpecializedEnemyDeathBoundaryError(
                f"region bytes differ: {spec['id']}"
            )
        ranges[spec["id"]] = (spec["start"], spec["end"])

    decode_ranges: dict[str, tuple[int, int]] = {}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["hex"])
        if _bytes_at(image, data, spec["start"], len(encoded)) != encoded:
            raise SpecializedEnemyDeathBoundaryError(
                f"control window differs: {spec['id']}"
            )
        start, end = ranges[spec["region"]]
        if not start <= spec["start"] < spec["start"] + len(encoded) <= end:
            raise SpecializedEnemyDeathBoundaryError(
                f"control window escapes region: {spec['id']}"
            )
        decode_ranges[f"window_{spec['id']}"] = (
            spec["start"],
            spec["start"] + len(encoded),
        )

    for spec in DIRECT_EDGE_SPECS:
        encoded = bytes.fromhex(spec["hex"])
        if _bytes_at(image, data, spec["from"], len(encoded)) != encoded:
            raise SpecializedEnemyDeathBoundaryError(
                f"direct edge differs: {spec['id']}"
            )
        source_start, source_end = ranges[spec["source_region"]]
        target_start, target_end = ranges[spec["target_region"]]
        if not source_start <= spec["from"] < spec["from"] + 5 <= source_end:
            raise SpecializedEnemyDeathBoundaryError(
                f"direct edge escapes source: {spec['id']}"
            )
        if not target_start <= spec["target"] < target_end:
            raise SpecializedEnemyDeathBoundaryError(
                f"direct edge escapes target: {spec['id']}"
            )
        if _direct_target(spec["from"], encoded) != spec["target"]:
            raise SpecializedEnemyDeathBoundaryError(
                f"direct edge target differs: {spec['id']}"
            )
        decode_ranges[f"edge_{spec['id']}"] = (
            spec["from"],
            spec["from"] + len(encoded),
        )

    anchor = DATA_ANCHOR_SPEC
    anchor_bytes = bytes.fromhex(anchor["hex"])
    if _bytes_at(image, data, anchor["rva"], len(anchor_bytes)) != anchor_bytes:
        raise SpecializedEnemyDeathBoundaryError("GetDefaultTeam data anchor differs")

    try:
        decoded = _decode_x86_regions(image, data, decode_ranges)
    except Exception as exc:
        raise SpecializedEnemyDeathBoundaryError(
            f"instruction alignment differs: {exc}"
        ) from exc
    for name, (start, end) in decode_ranges.items():
        cursor = start
        instructions = decoded[name]
        while cursor < end:
            instruction = instructions.get(cursor)
            if instruction is None:
                raise SpecializedEnemyDeathBoundaryError(
                    f"undecoded instruction in {name}"
                )
            cursor += len(instruction[1])
        if cursor != end:
            raise SpecializedEnemyDeathBoundaryError(
                f"reviewed range ends inside instruction: {name}"
            )

    for spec in CALL_INVENTORY_SPECS:
        actual = _raw_rel32_call_sites(image, data, spec["target"])
        if actual != set(spec["call_sites"]):
            raise SpecializedEnemyDeathBoundaryError(
                f"direct-call inventory differs: {spec['id']}"
            )

    return _expected_shape()


def validate_specialized_enemy_death_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise SpecializedEnemyDeathBoundaryError(
            "specialized enemy death boundary fields differ"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "generic_factory_path_proven": True,
        "specialized_enemy_death_classes_proven": True,
        "active_minor_type_count": len(MINOR_OCCURRENCES),
        "boss_objective_type_count": len(BOSS_PAWN_OCCURRENCES),
        "simulator_contradiction_found": True,
        "simulator_change_applied": True,
        "simulator_version": 407,
    }


def validate_specialized_enemy_death_boundary_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject dependency, source, byte, or prose drift."""
    expected = build_specialized_enemy_death_boundary_map(executable, content_root)
    if dict(value) != expected:
        raise SpecializedEnemyDeathBoundaryError(
            "specialized enemy death boundary differs from exact-build analysis"
        )
    result = validate_specialized_enemy_death_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_specialized_enemy_death_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
