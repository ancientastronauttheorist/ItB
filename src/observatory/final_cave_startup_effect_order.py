"""Reproduce exact-build Final Cave startup-effect queue order.

This continuation joins the shipped Final Cave Lua schedule to the native
``SkillEffect`` record builders and dispatcher.  It proves record construction,
copying, delay partitioning, and synchronous script-evaluation order.  It does
not claim wall-clock presentation timing or animation-impact interleave.
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
ANALYSIS_KIND = "final_cave_startup_effect_order_boundary_map"
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
SPAWN_ORDER_ARTIFACT_SHA256 = (
    "b798a97c582be31ffba3d173e00b24eefae32a9725d03fe7a2260ca1403214f4"
)
REPLACEMENT_ARTIFACT_SHA256 = (
    "b08b6d96d4d4ba0f53c024b301b17a039c8deb944632bbc6b8b4000a6e20af50"
)
CADENCE_ARTIFACT_SHA256 = (
    "578275064f6f55ca170128d954613d846eb9398a239c2462de87356549ca7b4e"
)
RECORD_SIZE = 0x134


class FinalCaveStartupEffectOrderError(RuntimeError):
    """Raised when the reviewed startup-effect map cannot be reproduced."""


LUA_SOURCE_SPEC = {
    "path": "scripts/missions/final/mission_final_two.lua",
    "size": 4_887,
    "sha256": "c8a8e40f512939c1f4fd0e0df416e5cbaec00c639e2985ad776e13c38735b17c",
    "symbols": [
        "FAST_VERSION",
        "SpawnMechs",
        "Mission_Final_Cave:StartMission",
        "Mission_Final_Cave:AddBomb",
    ],
}


REGION_SPECS = (
    {
        "id": "is_release_registration",
        "start": 0x0004B391,
        "end": 0x0004B3A7,
        "sha256": "ba3af457a85aaaef4a49b1bdff7d7ffd65e3ccf95a6ac6bcb0d2ba9c83b7ad62",
        "basis": "Ghidra 12.1.3 IsRelease registration window.",
    },
    {
        "id": "is_release_wrapper",
        "start": 0x00068EB0,
        "end": 0x00068EB3,
        "sha256": "e18aacce29affcdddaa5f641ac1ec12552e0fe9d066e6408941b1792818b8619",
        "basis": "Ghidra 12.1.3 shipped IsRelease wrapper body.",
    },
    {
        "id": "script_evaluator",
        "start": 0x0004CB20,
        "end": 0x0004CC79,
        "sha256": "8909ef982288cfb9fbd7a4ddd053078e2b85545334467f64b3c5986e32fd5ac7",
        "basis": "Ghidra 12.1.3 synchronous Lua buffer evaluator body.",
    },
    {
        "id": "space_damage_copy",
        "start": 0x0015B9B0,
        "end": 0x0015BCB4,
        "sha256": "3846fdb1ca2ebc1b4b6e83a64994f82d4907938345ff0d856c9bbea690957fc6",
        "basis": "Ghidra 12.1.3 complete SkillEffect record copy body.",
    },
    {
        "id": "apply_space_damage",
        "start": 0x00160110,
        "end": 0x001604BC,
        "sha256": "1597eb6d490f3ae9ee95547a0caa83999502b4ba9c3423bc50b1dca7acc20210",
        "basis": "Ghidra 12.1.3 Board SpaceDamage application body.",
    },
    {
        "id": "effect_dispatcher",
        "start": 0x001610D0,
        "end": 0x00161C6F,
        "sha256": "ccbecc70505f546c2d068ad7c95121f0c631aa27dd197127904de3faaff307c2",
        "basis": "Ghidra 12.1.3 ordered SkillEffect dispatcher body.",
    },
    {
        "id": "effect_suffix_insert",
        "start": 0x00175C90,
        "end": 0x00175D24,
        "sha256": "f20adaaea64d98610fc995394be8c391f13a5e4193c0e0936b174fece5d1cf52",
        "basis": (
            "Contiguous Ghidra 12.1.3 delayed effect-suffix insertion entry "
            "and count-calculation prefix; the complete function body is sparse."
        ),
    },
    {
        "id": "effect_delay_insert",
        "start": 0x001763D0,
        "end": 0x001765B2,
        "sha256": "e7d9004dacde914ee33f0b41500a7cb98ffa0b0f6ed91e20843300bb3be66c2c",
        "basis": "Ghidra 12.1.3 delayed-duration vector insertion body.",
    },
    {
        "id": "record_ctor",
        "start": 0x001999A0,
        "end": 0x00199C3D,
        "sha256": "2f17cc9bd3616c14305fb7fc1871bf0e37d09262825a99213f5b0568d6c6045d",
        "basis": "Ghidra 12.1.3 default SkillEffect record constructor.",
    },
    {
        "id": "add_voice",
        "start": 0x00256330,
        "end": 0x0025641E,
        "sha256": "daff04ed73a90edb06860f7c8f492f4e6167b093e4c9c87a126372cb9f6b45ea",
        "basis": "Ghidra 12.1.3 SkillEffect AddVoice wrapper.",
    },
    {
        "id": "add_delay",
        "start": 0x00256980,
        "end": 0x00256A26,
        "sha256": "56e5017dc5f97e3a36f414ad39dc9a0cda8ec55077defd9b7560a5e6b5b32571",
        "basis": "Ghidra 12.1.3 SkillEffect AddDelay wrapper.",
    },
    {
        "id": "add_dropper",
        "start": 0x002579A0,
        "end": 0x00257A7D,
        "sha256": "58c220e4690ef84da004018b95e6de9d13bb39341410e5735a05bdc0f1fb0aef",
        "basis": "Ghidra 12.1.3 SkillEffect AddDropper wrapper.",
    },
    {
        "id": "add_script",
        "start": 0x00257A80,
        "end": 0x00257B64,
        "sha256": "5d90280d770c0a71ac491e978bb8256960bc898b513c9562329335412953bf24",
        "basis": "Ghidra 12.1.3 SkillEffect AddScript wrapper.",
    },
    {
        "id": "add_board_shake",
        "start": 0x00258580,
        "end": 0x0025871A,
        "sha256": "ba58702321b01df1f1ba7c39d1110ceb5ff90dc5a69b0b4546c4ca55b701e5f1",
        "basis": "Ghidra 12.1.3 SkillEffect AddBoardShake wrapper.",
    },
    {
        "id": "vector_push",
        "start": 0x00259F00,
        "end": 0x00259FB7,
        "sha256": "39a9908012609c47f77556aea5af0865f3eb36943b5a1860c4c338bb6ea6fbb7",
        "basis": "Ghidra 12.1.3 common 0x134-byte record append body.",
    },
    {
        "id": "voice_registration",
        "start": 0x0027B701,
        "end": 0x0027B71C,
        "sha256": "8b444ae0831bacc85c7f5bb12c8e38c8cfde4085f6a219626947105704b7cf4b",
        "basis": "Ghidra 12.1.3 AddVoice registration window.",
    },
    {
        "id": "dropper_registration",
        "start": 0x0027B7D3,
        "end": 0x0027B7EE,
        "sha256": "1ea1e9f3b5ab20f3d53326943a9406eba68b4ef99a3473f9b93e1f70f2f009c7",
        "basis": "Ghidra 12.1.3 AddDropper registration window.",
    },
    {
        "id": "script_registration",
        "start": 0x0027B80F,
        "end": 0x0027B82A,
        "sha256": "417a2a414ed07472c734658f208138d36903d140204ca0458d70c958cfc166b0",
        "basis": "Ghidra 12.1.3 AddScript registration window.",
    },
    {
        "id": "delay_registration",
        "start": 0x0027B937,
        "end": 0x0027B952,
        "sha256": "0da010be0bbf2b3b5e6040f41ff218d1b4c33587d8bd47784f643028bd3e3e17",
        "basis": "Ghidra 12.1.3 AddDelay registration window.",
    },
    {
        "id": "shake_registration",
        "start": 0x0027BB69,
        "end": 0x0027BB84,
        "sha256": "5a4010b5e4d3a645da9a39339670f8428532b2b11e927b8cac10abbc59c8b4de",
        "basis": "Ghidra 12.1.3 AddBoardShake registration window.",
    },
)


DATA_ANCHOR_SPECS = (
    ("is_release_name", 0x00420AD8, b"IsRelease\0"),
    ("add_voice_name", 0x00438CDC, b"AddVoice\0"),
    ("add_dropper_name", 0x00438D5C, b"AddDropper\0"),
    ("add_script_name", 0x00438D74, b"AddScript\0"),
    ("add_delay_name", 0x00438DD0, b"AddDelay\0"),
    ("add_board_shake_name", 0x00438E6C, b"AddBoardShake\0"),
)


REGISTRATION_SPECS = (
    {
        "lua_name": "IsRelease",
        "region_id": "is_release_registration",
        "wrapper_rva": 0x00068EB0,
        "wrapper_instruction_rva": 0x0004B391,
        "wrapper_instruction_hex": "68b08e4600",
        "name_anchor": "is_release_name",
        "name_instruction_rva": 0x0004B396,
        "name_instruction_hex": "bad80a8200",
    },
    {
        "lua_name": "AddVoice",
        "region_id": "voice_registration",
        "wrapper_rva": 0x00256330,
        "wrapper_instruction_rva": 0x0027B701,
        "wrapper_instruction_hex": "c745ec30636500",
        "name_anchor": "add_voice_name",
        "name_instruction_rva": 0x0027B710,
        "name_instruction_hex": "68dc8c8300",
    },
    {
        "lua_name": "AddDropper",
        "region_id": "dropper_registration",
        "wrapper_rva": 0x002579A0,
        "wrapper_instruction_rva": 0x0027B7D3,
        "wrapper_instruction_hex": "c745eca0796500",
        "name_anchor": "add_dropper_name",
        "name_instruction_rva": 0x0027B7E2,
        "name_instruction_hex": "685c8d8300",
    },
    {
        "lua_name": "AddScript",
        "region_id": "script_registration",
        "wrapper_rva": 0x00257A80,
        "wrapper_instruction_rva": 0x0027B80F,
        "wrapper_instruction_hex": "c745ec807a6500",
        "name_anchor": "add_script_name",
        "name_instruction_rva": 0x0027B81E,
        "name_instruction_hex": "68748d8300",
    },
    {
        "lua_name": "AddDelay",
        "region_id": "delay_registration",
        "wrapper_rva": 0x00256980,
        "wrapper_instruction_rva": 0x0027B937,
        "wrapper_instruction_hex": "c745ec80696500",
        "name_anchor": "add_delay_name",
        "name_instruction_rva": 0x0027B946,
        "name_instruction_hex": "68d08d8300",
    },
    {
        "lua_name": "AddBoardShake",
        "region_id": "shake_registration",
        "wrapper_rva": 0x00258580,
        "wrapper_instruction_rva": 0x0027BB69,
        "wrapper_instruction_hex": "c745ec80856500",
        "name_anchor": "add_board_shake_name",
        "name_instruction_rva": 0x0027BB78,
        "name_instruction_hex": "686c8e8300",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "script_eval_calls",
        "region_id": "script_evaluator",
        "start": 0x0004CB77,
        "hex": (
            "2bcb8d450c83fa1068540d82000f43450c5150ff3548608900ff15d4647d00"
            "83c41085c07534505050ff3548608900ff15d0647d0083c41085c0751e"
        ),
        "meaning": "The evaluator calls luaL_loadbuffer and then lua_pcall synchronously.",
    },
    {
        "id": "apply_script_first",
        "region_id": "apply_space_damage",
        "start": 0x00160144,
        "hex": (
            "83bdf800000000745283ec188bccc741140f000000c741100000000083791410"
            "72048b01eb028bc16affc600008d85e80000006a0050e8517feaff8d45d850"
            "e898c9eeff8b45ec83f810720f406a0150ff75d8e86476eaff83c40c"
        ),
        "meaning": (
            "A nonempty record+0xe0 script is copied and evaluated before "
            "board damage logic."
        ),
    },
    {
        "id": "dispatcher_order_setup",
        "region_id": "effect_dispatcher",
        "start": 0x001613CD,
        "hex": (
            "b8c1de31358b7d0c8bcf8b75082bcef7e9c78564fdffff00000000c1fa068b"
            "c2c1e81f03c20f84f706000033c0898568fdffff03c68d8d7cfdffff50"
            "e8a2a5ffff"
        ),
        "meaning": (
            "The dispatcher derives record count from vector span and copies "
            "record zero first."
        ),
    },
    {
        "id": "dispatcher_kind_zero_apply",
        "region_id": "effect_dispatcher",
        "start": 0x001614ED,
        "hex": (
            "83bd14feffff0075448d857cfdffff508d8dc8fbffffe8a8a4ffff81ec340100"
            "00c645fc0a8d85c8fbffff8bcc50e890a4ffff8b038bcbff108d8dc8fbffff"
            "c645fc08e86bcdfaff"
        ),
        "meaning": "Default kind zero reaches the Board SpaceDamage virtual apply slot.",
    },
    {
        "id": "dispatcher_delay_gate_advance",
        "region_id": "effect_dispatcher",
        "start": 0x00161924,
        "hex": (
            "f30f108544feffff0f57c90f2ec19ff6c4447b07b801000000eb0233c084c0"
            "75518d8d7cfdffffc645fc07e84cc9faff8b7d0cb8c1de31358b75088bcfff"
            "8564fdffff2bce818568fdffff34010000f7e9c1fa068bc2c1e81f03c2398564"
            "fdffff8b8568fdffff0f826ffaffffe959010000"
        ),
        "meaning": (
            "Zero-duration records advance by one 0x134-byte slot; nonzero "
            "duration leaves the loop for continuation setup."
        ),
    },
    {
        "id": "dispatcher_delay_suffix",
        "region_id": "effect_dispatcher",
        "start": 0x00161A14,
        "hex": (
            "698564fdffff340100008d4de4c68560fdffff00ffb560fdffffc745e400000000"
            "ff750c0534010000c745e80000000003450850c745ec00000000e89c6901008d"
            "8d14ffffffe8f14bfbff8b45e48d4de4898514ffffff8b45e8898518ffffff8b"
            "45ec89851cffffffc745e400000000c745e800000000c745ec00000000e8b94b"
            "fbff8d8514ffffff508d8b442c000051ff318d856cfdffff50e8dd4101008d85"
            "44feffff508d8b502c000051ff318d856cfdffff50e8014901008d8d14ffffff"
            "e8c6c9faff8d8d7cfdffffc645fc07e8b7c7faff8b7d0c8b7508"
        ),
        "meaning": (
            "A delay copies the suffix beginning at the next record and "
            "inserts it and the duration at the beginnings of paired Board "
            "vectors."
        ),
    },
    {
        "id": "script_build_append",
        "region_id": "add_script",
        "start": 0x00257AAE,
        "hex": (
            "6a008d8dbcfeffffc745fc00000000e8de1ef4ff6aff6a008d4508c645fc0150"
            "8d4d9ce8fa05dbff8d85bcfeffff508d8d54fcffffe8c83ef0ff8d8554fcffff"
            "c645fc02508d8d88fdffffe8b23ef0ff8d8588fdffffc645fc03508bcee8f023"
            "0000"
        ),
        "meaning": (
            "AddScript constructs a record, stores the script, copies it, "
            "and appends immediately."
        ),
    },
    {
        "id": "delay_build_append",
        "region_id": "add_delay",
        "start": 0x002569AE,
        "hex": (
            "6a008d8dbcfeffffe8e52ff4fff30f1045088d85bcfeffffc745fc000000008d"
            "8d88fdffff50f30f114584c6458001e8ce4ff0ff8d8588fdffffc645fc01508b"
            "cee80c350000"
        ),
        "meaning": (
            "AddDelay sets record+0xc4 and record+0xc8, copies the record, "
            "and appends immediately."
        ),
    },
    {
        "id": "vector_push_tail",
        "region_id": "vector_push",
        "start": 0x00259F83,
        "hex": "8b4e04894d08894df0c745fc0100000085c9740657e8131af0ff81460434010000",
        "meaning": "The common append copies at the current end and advances it by exactly 0x134.",
    },
)


DIRECT_EDGE_SPECS = (
    ("voice_to_push", "add_voice", 0x002563D0, "e82b3b0000", "vector_push", 0x00259F00),
    ("delay_to_ctor", "add_delay", 0x002569B6, "e8e52ff4ff", "record_ctor", 0x001999A0),
    ("delay_to_copy", "add_delay", 0x002569DD, "e8ce4ff0ff", "space_damage_copy", 0x0015B9B0),
    ("delay_to_push", "add_delay", 0x002569EF, "e80c350000", "vector_push", 0x00259F00),
    ("dropper_to_push", "add_dropper", 0x00257A2B, "e8d0240000", "vector_push", 0x00259F00),
    ("script_to_ctor", "add_script", 0x00257ABD, "e8de1ef4ff", "record_ctor", 0x001999A0),
    ("script_to_copy_one", "add_script", 0x00257AE3, "e8c83ef0ff", "space_damage_copy", 0x0015B9B0),
    ("script_to_copy_two", "add_script", 0x00257AF9, "e8b23ef0ff", "space_damage_copy", 0x0015B9B0),
    ("script_to_push", "add_script", 0x00257B0B, "e8f0230000", "vector_push", 0x00259F00),
    ("shake_to_push", "add_board_shake", 0x002586E2, "e819180000", "vector_push", 0x00259F00),
    (
        "vector_push_to_copy",
        "vector_push",
        0x00259F98,
        "e8131af0ff",
        "space_damage_copy",
        0x0015B9B0,
    ),
    (
        "dispatcher_to_copy",
        "effect_dispatcher",
        0x00161409,
        "e8a2a5ffff",
        "space_damage_copy",
        0x0015B9B0,
    ),
    (
        "apply_to_script_evaluator",
        "apply_space_damage",
        0x00160183,
        "e898c9eeff",
        "script_evaluator",
        0x0004CB20,
    ),
    (
        "dispatcher_to_suffix_insert",
        "effect_dispatcher",
        0x00161AAE,
        "e8dd410100",
        "effect_suffix_insert",
        0x00175C90,
    ),
    (
        "dispatcher_to_delay_insert",
        "effect_dispatcher",
        0x00161ACA,
        "e801490100",
        "effect_delay_insert",
        0x001763D0,
    ),
)


IMPORT_EDGE_SPECS = (
    ("evaluator_to_lual_loadbuffer", 0x0004CB90, "ff15d4647d00", "luaL_loadbuffer", 18, 0x003D64D4),
    ("evaluator_to_lua_pcall", 0x0004CBA6, "ff15d0647d00", "lua_pcall", 71, 0x003D64D0),
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
        raise FinalCaveStartupEffectOrderError(
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
        raise FinalCaveStartupEffectOrderError(
            f"RVA 0x{rva:08x} is not wholly in {expected_section}"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise FinalCaveStartupEffectOrderError(
            f"RVA 0x{rva:08x} is not an E8 rel32 call"
        )
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
            "boundary_basis": spec["basis"],
        }
        for spec in REGION_SPECS
    ]


def _expected_data_anchors() -> list[dict[str, Any]]:
    return [
        {
            "id": anchor_id,
            "evidence_class": "fact",
            "rva": f"0x{rva:08x}",
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "section": ".rdata",
            "text": payload[:-1].decode("ascii"),
        }
        for anchor_id, rva, payload in DATA_ANCHOR_SPECS
    ]


def _expected_registrations() -> list[dict[str, Any]]:
    return [
        {
            "lua_name": spec["lua_name"],
            "region_id": spec["region_id"],
            "wrapper_rva": f"0x{spec['wrapper_rva']:08x}",
            "wrapper_instruction_rva": f"0x{spec['wrapper_instruction_rva']:08x}",
            "wrapper_instruction_hex": spec["wrapper_instruction_hex"],
            "name_anchor": spec["name_anchor"],
            "name_instruction_rva": f"0x{spec['name_instruction_rva']:08x}",
            "name_instruction_hex": spec["name_instruction_hex"],
            "evidence_class": "fact",
        }
        for spec in REGISTRATION_SPECS
    ]


def _expected_windows() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "region_id": spec["region_id"],
            "start_rva": f"0x{spec['start']:08x}",
            "size": len(bytes.fromhex(spec["hex"])),
            "sha256": hashlib.sha256(bytes.fromhex(spec["hex"])).hexdigest(),
            "instruction_hex": spec["hex"],
            "evidence_class": "fact",
            "meaning": spec["meaning"],
        }
        for spec in CONTROL_WINDOW_SPECS
    ]


def _expected_direct_edges() -> list[dict[str, Any]]:
    return [
        {
            "id": edge_id,
            "source_region": source,
            "from_rva": f"0x{rva:08x}",
            "instruction_hex": encoded,
            "target_region": target_region,
            "target_rva": f"0x{target_rva:08x}",
            "evidence_class": "fact",
        }
        for edge_id, source, rva, encoded, target_region, target_rva in DIRECT_EDGE_SPECS
    ]


def _expected_import_edges() -> list[dict[str, Any]]:
    return [
        {
            "id": edge_id,
            "source_region": "script_evaluator",
            "from_rva": f"0x{rva:08x}",
            "instruction_hex": encoded,
            "library": "lua5.1.dll",
            "name": name,
            "hint": hint,
            "iat_rva": f"0x{iat_rva:08x}",
            "evidence_class": "fact",
        }
        for edge_id, rva, encoded, name, hint, iat_rva in IMPORT_EDGE_SPECS
    ]


def _release_schedule() -> dict[str, Any]:
    return {
        "is_release_result": True,
        "fast_version": False,
        "mountain_counts": [3, 4],
        "pylon_count": 7,
        "record_counts_by_mountain_count": {"3": 44, "4": 46},
        "record_type_counts_by_mountain_count": {
            "3": {"delay": 19, "board_shake": 1, "dropper": 18, "script": 3, "voice": 3},
            "4": {"delay": 20, "board_shake": 1, "dropper": 19, "script": 3, "voice": 3},
        },
        "requested_delay_total_by_mountain_count": {"3": 21.6, "4": 21.8},
        "segments": [
            "delay 2; board shake 3",
            "for each mountain: one rock dropper; delay 0.2",
            "delay 1",
            "for Mech ids 0, 1, 2: one SetSpace/SpawnAnimation script; delay 0.5",
            "delay 1; MissionFinal_Pylons voice; delay 3",
            "for each of seven pylons: two consecutive copied building droppers; delay 0.5",
            "MissionFinal_Bomb voice; MissionFinal_BombResponse voice; delay 7",
            "delay 2; one BigBomb dropper",
        ],
        "record_index_formulas": {
            "mountain_dropper_j": "2 + 2*j",
            "mech_script_i": "3 + 2*mountain_count + 2*i",
            "first_pylon_dropper_j": "12 + 2*mountain_count + 3*j",
            "second_pylon_dropper_j": "13 + 2*mountain_count + 3*j",
            "bomb_dropper": "37 + 2*mountain_count",
        },
    }


def _contracts() -> dict[str, Any]:
    return {
        "record_storage": {
            "record_size": RECORD_SIZE,
            "common_append_rva": "0x00259f00",
            "append_is_immediate": True,
            "append_preserves_call_order": True,
            "later_source_mutation_changes_prior_record": False,
        },
        "script_record": {
            "script_string_offset": "+0xe0",
            "default_kind": 0,
            "kind_zero_board_apply_rva": "0x00160110",
            "loadbuffer_iat_rva": "0x003d64d4",
            "pcall_iat_rva": "0x003d64d0",
            "evaluation_is_synchronous": True,
            "valid_startup_attempt_order": [0, 1, 2],
        },
        "delay_record": {
            "flag_offset": "+0xc4",
            "duration_offset": "+0xc8",
            "suffix_begins_at_next_record": True,
            "dispatcher_this_effect_suffix_vector_offset": "+0x2c44",
            "dispatcher_this_duration_vector_offset": "+0x2c50",
            "primary_board_effect_suffix_vector_offset": "+0x2c50",
            "primary_board_duration_vector_offset": "+0x2c5c",
            "paired_continuation_insert_position": "current vector beginning",
            "preserves_remaining_record_order": True,
        },
        "release_schedule": _release_schedule(),
        "semantic_boundary": {
            "logical_enemy_admission_precedes_first_record_dispatch": True,
            "mountain_records_precede_mech_scripts": True,
            "mech_scripts_precede_pylon_records": True,
            "pylon_records_precede_bomb_record": True,
            "each_pylon_has_two_independent_consecutive_dropper_records": True,
            "visual_impact_order_proven": False,
            "wall_clock_duration_proven": False,
        },
        "solver_handoff": {
            "current_policy": "Consume a fresh settled bridge state before solving Final Cave.",
            "simulator_change_required": False,
            "reason": (
                "The solver consumes settled state; presentation timing, "
                "concrete RNG outputs, coordinates, and UIDs remain outside "
                "this static boundary."
            ),
        },
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "release_branch_is_exact",
            "evidence_class": "inference",
            "claim": (
                "The registered shipped IsRelease wrapper returns true, so "
                "FAST_VERSION is false and every source-level release voice "
                "and delay branch is included."
            ),
            "supports": [
                "is_release_name",
                "is_release_registration",
                "is_release_wrapper",
                LUA_SOURCE_SPEC["path"],
            ],
        },
        {
            "id": "builders_append_independent_records",
            "evidence_class": "inference",
            "claim": (
                "The reviewed AddVoice, AddDelay, AddDropper, AddScript, and "
                "AddBoardShake wrappers immediately reach the common 0x134-byte "
                "append. Complete record copies preserve source call order and "
                "insulate earlier records from later Lua object mutation."
            ),
            "supports": [
                "vector_push_tail",
                "vector_push_to_copy",
                "voice_to_push",
                "delay_to_push",
                "dropper_to_push",
                "script_to_push",
                "shake_to_push",
            ],
        },
        {
            "id": "delays_partition_without_reordering",
            "evidence_class": "inference",
            "claim": (
                "The dispatcher starts at record zero and advances by one "
                "0x134-byte record. A nonzero delay stores the suffix beginning "
                "at the next record plus its duration, so later continuation "
                "preserves the remaining record order."
            ),
            "supports": [
                "dispatcher_order_setup",
                "dispatcher_delay_gate_advance",
                "dispatcher_delay_suffix",
                "dispatcher_to_suffix_insert",
                "dispatcher_to_delay_insert",
                "final_cave_replacement_cadence",
            ],
        },
        {
            "id": "mech_scripts_are_attempted_in_id_order",
            "evidence_class": "inference",
            "claim": (
                "On an unmodified valid startup, the three queued chunks are "
                "dispatched in Mech-id order 0, 1, 2. Kind zero reaches Board "
                "SpaceDamage apply, which evaluates each nonempty script through "
                "luaL_loadbuffer and synchronous lua_pcall before proceeding."
            ),
            "supports": [
                LUA_SOURCE_SPEC["path"],
                "script_build_append",
                "dispatcher_kind_zero_apply",
                "board_apply_vtable_slot",
                "apply_script_first",
                "evaluator_to_lual_loadbuffer",
                "evaluator_to_lua_pcall",
            ],
            "limitations": [
                "Arbitrary modified-state Lua errors or cancellation are not ruled out."
            ],
        },
        {
            "id": "duplicate_pylon_droppers_are_real_records",
            "evidence_class": "inference",
            "claim": (
                "Each of the seven exact pylon iterations appends two consecutive "
                "independent building-dropper records before its following 0.5 "
                "delay. This proves two record and animation creations, not their "
                "eventual visual overlap or impact order."
            ),
            "supports": [
                LUA_SOURCE_SPEC["path"],
                "builders_append_independent_records",
                "delays_partition_without_reordering",
                "final_cave_startup",
            ],
        },
        {
            "id": "startup_effect_order_is_closed",
            "evidence_class": "inference",
            "claim": (
                "For exact cave maps, ordered dispatch is delay/shake, all "
                "mountain pairs, Mech scripts 0-2, all duplicated pylon pairs, "
                "and the final bomb dropper. The exact record total is 44 for "
                "three mountains and 46 for four."
            ),
            "supports": [
                "release_branch_is_exact",
                "builders_append_independent_records",
                "delays_partition_without_reordering",
                "mech_scripts_are_attempted_in_id_order",
                "duplicate_pylon_droppers_are_real_records",
            ],
        },
        {
            "id": "solver_boundary_remains_settled_read",
            "evidence_class": "inference",
            "claim": (
                "No Rust change is justified: enemy admission is already proven "
                "to precede this queue, while the existing stage-change handoff "
                "consumes the concrete post-presentation board from a fresh "
                "settled bridge read."
            ),
            "supports": ["final_cave_startup_spawn_order", "startup_effect_order_is_closed"],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "concrete_startup_rng_outputs",
            "question": "Which coordinates, identities, and UIDs occur in a particular startup?",
            "static_status": (
                "The call skeleton and effect order are exact, but incoming CRT "
                "state and concrete results are not."
            ),
            "next_evidence": "Use a fresh settled bridge read or a matched startup trace.",
        },
        {
            "id": "presentation_timing_and_overlap",
            "question": "When do queued animations land in wall-clock time, and which overlap?",
            "static_status": (
                "Requested delay values and record creation order are exact; "
                "frame cadence, animation duration, and impact overlap are not."
            ),
            "next_evidence": (
                "Capture timestamped presentation telemetry only if UI timing "
                "becomes solver-relevant."
            ),
        },
        {
            "id": "modified_state_errors_and_collisions",
            "question": (
                "How do arbitrary script errors, cancellation, occupancy "
                "collisions, or terrain replacement alter presentation?"
            ),
            "static_status": (
                "The ordinary exact startup path is pinned; adversarial or "
                "modified-effect outcomes are not generalized."
            ),
            "next_evidence": (
                "Add a narrowly controlled trace or separate exact-build "
                "boundary map for the concrete edge case."
            ),
        },
        {
            "id": "spawn_block_lifetime",
            "question": (
                "Exactly when do temporary and permanent startup spawn blocks "
                "clear or persist?"
            ),
            "static_status": (
                "Synchronous writes and their placement before enemy selection "
                "are proven, but full lifetime semantics are outside this queue "
                "map."
            ),
            "next_evidence": (
                "Map the BlockSpawn cleanup and phase-reset consumers if "
                "forecasting across settlement becomes necessary."
            ),
        },
        {
            "id": "non_windows_equivalence",
            "question": (
                "Do macOS and other executable builds use identical record and "
                "dispatcher semantics?"
            ),
            "static_status": "This evidence is keyed only to Windows build 13725832.",
            "next_evidence": "Produce independent build-keyed maps.",
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
            "scripts_revision_sha256": EXPECTED_SCRIPTS_REVISION_SHA256,
        },
        "sources": {
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
            "lua_files": [{**LUA_SOURCE_SPEC, "evidence_class": "fact"}],
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
                    "Pins exact cave maps, zone cardinalities, source RNG "
                    "skeleton, and source-relative schedule."
                ),
            },
            {
                "id": "final_cave_startup_spawn_order",
                "artifact": (
                    "data/observatory/native/windows_build_13725832_"
                    "31fe35265598_final_cave_startup_spawn_order.json"
                ),
                "artifact_sha256": SPAWN_ORDER_ARTIFACT_SHA256,
                "role": (
                    "Pins boss and ordinary logical admission before any "
                    "startup record dispatch."
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
                    "Pins AddDropper complete record copying and kind-4 "
                    "animation construction."
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
                    "Pins dispatcher-to-active-animation continuation and "
                    "busy-to-impact settlement."
                ),
            },
        ],
        "supersedes": {
            "artifact": (
                "data/observatory/native/windows_build_13725832_"
                "31fe35265598_final_cave_startup.json"
            ),
            "resolved_facets": [
                "startup_effect_record_order",
                "intra_effect_add_script_evaluation_order",
                "duplicated_pylon_dropper_records",
                "release_delay_branch",
            ],
            "remaining_gap_ids": [item["id"] for item in _unresolved()],
        },
        "method": {
            "boundary_review": (
                "Focused Ghidra 12.1.3 registration, record-builder, dispatcher, "
                "Board-apply, vtable, and Lua-evaluator review."
            ),
            "source_review": (
                "Exact shipped Lua identity plus checked construction order and "
                "exact cave-map zone counts from the pinned startup artifact."
            ),
            "limitations": [
                "Every native address applies only to the pinned Windows executable.",
                (
                    "Requested delay values are semantic scheduler inputs, not "
                    "measured wall-clock seconds."
                ),
                (
                    "Record and animation creation order does not prove visual "
                    "impact overlap or order."
                ),
                "Concrete startup RNG outputs, coordinates, and UIDs remain unknown.",
            ],
        },
        "contracts": _contracts(),
        "regions": _expected_regions(),
        "data_anchors": _expected_data_anchors(),
        "registration_bindings": _expected_registrations(),
        "vtable_bindings": [
            {
                "id": "board_apply_vtable_slot",
                "pointer_rva": "0x0042e258",
                "pointer_section": ".rdata",
                "target_region": "apply_space_damage",
                "target_rva": "0x00160110",
                "evidence_class": "fact",
            }
        ],
        "control_windows": _expected_windows(),
        "direct_call_edges": _expected_direct_edges(),
        "import_call_edges": _expected_import_edges(),
        "findings": _findings(),
        "unresolved": _unresolved(),
        "summary": {
            "lua_source_count": 1,
            "dependency_count": 4,
            "region_count": len(REGION_SPECS),
            "data_anchor_count": len(DATA_ANCHOR_SPECS),
            "registration_binding_count": len(REGISTRATION_SPECS),
            "vtable_binding_count": 1,
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "import_edge_count": len(IMPORT_EDGE_SPECS),
            "finding_count": len(_findings()),
            "unresolved_count": len(_unresolved()),
            "release_branch_proven": True,
            "record_order_proven": True,
            "script_evaluation_order_proven": True,
            "duplicated_pylon_records_proven": True,
            "visual_impact_order_proven": False,
            "wall_clock_duration_proven": False,
            "simulator_change_required": False,
        },
    }


def _verify_lua_source(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise FinalCaveStartupEffectOrderError("content root is not a directory")
    source = root / Path(LUA_SOURCE_SPEC["path"])
    try:
        resolved = source.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise FinalCaveStartupEffectOrderError(
            "Final Cave Lua source is unavailable or escapes the content root"
        ) from exc
    if source.is_symlink() or not resolved.is_file():
        raise FinalCaveStartupEffectOrderError(
            "Final Cave Lua source is not a regular non-symlink file"
        )
    data = resolved.read_bytes()
    if (
        len(data) != LUA_SOURCE_SPEC["size"]
        or hashlib.sha256(data).hexdigest() != LUA_SOURCE_SPEC["sha256"]
    ):
        raise FinalCaveStartupEffectOrderError("Final Cave Lua source identity differs")

    if not data.startswith(b"local FAST_VERSION = not IsRelease() --debug purposes"):
        raise FinalCaveStartupEffectOrderError("FAST_VERSION source branch differs")
    spawn_start = data.index(b"local function SpawnMechs(effect,zone)")
    spawn_end = data.index(b"function Mission_Final_Cave:MissionEnd()", spawn_start)
    spawn = data[spawn_start:spawn_end]
    if not (
        b"for i = 0,2 do" in spawn
        and spawn.count(b"effect:AddScript(") == 1
        and spawn.count(b"effect:AddDelay(0.5)") == 1
        and spawn.index(b":SetSpace(") < spawn.index(b":SpawnAnimation()")
    ):
        raise FinalCaveStartupEffectOrderError("SpawnMechs source body differs")

    start = data.index(b"function Mission_Final_Cave:StartMission()")
    end = data.index(b"function Mission_Final_Cave:UpdateSpawning()", start)
    body = data[start:end]
    ordered = (
        b"effect:AddDelay(2)",
        b"effect:AddBoardShake(3)",
        b"effect:AddDropper(rock,\"effects/shotdown_rock.png\")",
        b"effect:AddDelay(1)",
        b"SpawnMechs(effect,drop_zone)",
        b"effect:AddVoice(\"MissionFinal_Pylons\",PAWN_ID_CEO)",
        b"effect:AddDropper(building,\"combat/tiles_grass/building_fall.png\")",
        b"effect:AddVoice(\"MissionFinal_Bomb\",PAWN_ID_MECH)",
        b"effect:AddDelay(7)",
        b"self:AddBomb(effect, bomb_loc)",
        b"Board:AddEffect(effect)",
    )
    positions = [body.index(fragment) for fragment in ordered]
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        raise FinalCaveStartupEffectOrderError("StartMission effect source order differs")
    duplicate = b"effect:AddDropper(building,\"combat/tiles_grass/building_fall.png\")"
    if body.count(duplicate) != 2 or body.count(b"if not FAST_VERSION then") != 3:
        raise FinalCaveStartupEffectOrderError(
            "release or duplicate-dropper source structure differs"
        )
    add_bomb_start = data.index(b"function Mission_Final_Cave:AddBomb(effect, bomb_loc)")
    add_bomb_end = data.index(b"function Mission_Final_Cave:IsEndBlocked()", add_bomb_start)
    if (
        data[add_bomb_start:add_bomb_end].count(
            b"effect:AddDropper(add_bomb,\"units/mission/bomb.png\")"
        )
        != 1
    ):
        raise FinalCaveStartupEffectOrderError("AddBomb dropper source differs")


def build_final_cave_startup_effect_order_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build Final Cave startup-effect order map."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise FinalCaveStartupEffectOrderError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise FinalCaveStartupEffectOrderError("executable identity differs")
    _verify_lua_source(content_root)

    ranges: dict[str, tuple[int, int]] = {}
    for spec in REGION_SPECS:
        size = spec["end"] - spec["start"]
        try:
            body = _region_bytes(image, data, spec["start"], size, ".text", spec["id"])
        except Exception as exc:
            raise FinalCaveStartupEffectOrderError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise FinalCaveStartupEffectOrderError(f"region {spec['id']} bytes differ")
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise FinalCaveStartupEffectOrderError(str(exc)) from exc

    anchors = {anchor_id: (rva, payload) for anchor_id, rva, payload in DATA_ANCHOR_SPECS}
    for anchor_id, rva, payload in DATA_ANCHOR_SPECS:
        if _file_backed_bytes(image, data, rva, len(payload), ".rdata") != payload:
            raise FinalCaveStartupEffectOrderError(f"data anchor {anchor_id} differs")

    region_by_id = {spec["id"]: spec for spec in REGION_SPECS}
    for spec in REGISTRATION_SPECS:
        region = region_by_id[spec["region_id"]]
        for key in ("wrapper", "name"):
            rva = spec[f"{key}_instruction_rva"]
            expected = bytes.fromhex(spec[f"{key}_instruction_hex"])
            if not region["start"] <= rva < rva + len(expected) <= region["end"]:
                raise FinalCaveStartupEffectOrderError(
                    f"registration {spec['lua_name']} escapes its region"
                )
            instruction = decoded[spec["region_id"]].get(rva)
            if instruction is None or instruction[1] != expected:
                raise FinalCaveStartupEffectOrderError(
                    f"registration {spec['lua_name']} {key} instruction differs"
                )
        name_rva, _ = anchors[spec["name_anchor"]]
        name_instruction = bytes.fromhex(spec["name_instruction_hex"])
        encoded_name_va = struct.unpack_from("<I", name_instruction, 1)[0]
        if encoded_name_va != image.image_base + name_rva:
            raise FinalCaveStartupEffectOrderError(
                f"registration {spec['lua_name']} name target differs"
            )

    pointer = _file_backed_bytes(image, data, 0x0042E258, 4, ".rdata")
    if struct.unpack("<I", pointer)[0] != image.image_base + 0x00160110:
        raise FinalCaveStartupEffectOrderError("Board apply vtable slot differs")

    for spec in CONTROL_WINDOW_SPECS:
        expected = bytes.fromhex(spec["hex"])
        start = spec["start"]
        if _file_backed_bytes(image, data, start, len(expected), ".text") != expected:
            raise FinalCaveStartupEffectOrderError(f"control window {spec['id']} differs")
        region = region_by_id[spec["region_id"]]
        if not region["start"] <= start < start + len(expected) <= region["end"]:
            raise FinalCaveStartupEffectOrderError(
                f"control window {spec['id']} escapes its region"
            )
        cursor = start
        while cursor < start + len(expected):
            instruction = decoded[spec["region_id"]].get(cursor)
            if instruction is None:
                raise FinalCaveStartupEffectOrderError(
                    f"control window {spec['id']} crosses undecoded bytes"
                )
            cursor += len(instruction[1])
        if cursor != start + len(expected):
            raise FinalCaveStartupEffectOrderError(
                f"control window {spec['id']} ends inside an instruction"
            )

    for edge_id, source, rva, encoded_hex, target_region, target_rva in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(encoded_hex)
        instruction = decoded[source].get(rva)
        if (
            instruction is None
            or instruction[1] != expected
            or _direct_target(rva, expected) != target_rva
        ):
            raise FinalCaveStartupEffectOrderError(f"direct edge {edge_id} differs")
        if target_rva not in decoded[target_region]:
            raise FinalCaveStartupEffectOrderError(
                f"direct edge {edge_id} target is not an instruction"
            )

    imports = image.imports()
    for edge_id, rva, encoded_hex, name, hint, iat_rva in IMPORT_EDGE_SPECS:
        expected = bytes.fromhex(encoded_hex)
        instruction = decoded["script_evaluator"].get(rva)
        if instruction is None or instruction[1] != expected:
            raise FinalCaveStartupEffectOrderError(f"import edge {edge_id} bytes differ")
        if (
            len(expected) != 6
            or expected[:2] != b"\xff\x15"
            or struct.unpack_from("<I", expected, 2)[0]
            != image.image_base + iat_rva
        ):
            raise FinalCaveStartupEffectOrderError(f"import edge {edge_id} slot differs")
        if not any(
            record["iat_rva"] == f"0x{iat_rva:08x}"
            and str(record["library"]).casefold() == "lua5.1.dll"
            and record["name"] == name
            and record["hint"] == hint
            for record in imports
        ):
            raise FinalCaveStartupEffectOrderError(f"import edge {edge_id} binding differs")

    if _file_backed_bytes(image, data, 0x00068EB0, 3, ".text") != b"\xb0\x01\xc3":
        raise FinalCaveStartupEffectOrderError("IsRelease return value differs")
    return _expected_shape()


def validate_final_cave_startup_effect_order_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping):
        raise FinalCaveStartupEffectOrderError("effect-order map must be an object")
    if dict(value) != _expected_shape():
        raise FinalCaveStartupEffectOrderError("effect-order map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "release_branch_proven": True,
        "record_order_proven": True,
        "script_evaluation_order_proven": True,
        "duplicated_pylon_records_proven": True,
        "visual_impact_order_proven": False,
        "wall_clock_duration_proven": False,
        "simulator_change_required": False,
    }


def validate_final_cave_startup_effect_order_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject source, byte, address, or prose drift."""
    expected = build_final_cave_startup_effect_order_map(executable, content_root)
    if dict(value) != expected:
        raise FinalCaveStartupEffectOrderError("effect-order map differs from exact-build analysis")
    result = validate_final_cave_startup_effect_order_map_binding(value)
    result["status"] = "verified"
    return result


def encode_final_cave_startup_effect_order_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
