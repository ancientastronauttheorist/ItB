"""Reproduce the exact-build Final Cave replacement-bomb boundary.

This immutable continuation joins the shipped missing-bomb callback to the
native Board effect queue, dropper animation, SpaceDamage application, pawn
factory, and Board:AddPawn path.  It proves materialization mechanics and
relative update order for Windows build 13725832.  It deliberately does not
invent the shared-RNG state, selected coordinate, pawn UID, wall-clock delay,
or repeated-cycle cadence that only settled runtime state can provide.
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
ANALYSIS_KIND = "final_cave_replacement_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
FINAL_END_SETTLEMENT_ARTIFACT_SHA256 = (
    "541237f7e723c1ec56b0328cb1f137f2a6725bda55c588d0a7ebc74adc55be0c"
)
FINAL_CAVE_OUTCOME_ARTIFACT_SHA256 = (
    "15e8c54660936296b3e5a4b76dbfa2f170aabc13157932c39daec8ae0ba7c529"
)
FINAL_CAVE_MAP_CHOICE_ARTIFACT_SHA256 = (
    "8068a847b328ba8137ff9c88864f66eaaa0bf93c5f8ba34aedd1b4115e7936db"
)


class FinalCaveReplacementError(RuntimeError):
    """Raised when the reviewed replacement map cannot be reproduced."""


SOURCE_SPECS = (
    {
        "path": "scripts/global.lua",
        "size": 17_363,
        "sha256": (
            "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2"
        ),
        "symbols": ["random_removal"],
        "reviewed_lines": [[583, 584]],
    },
    {
        "path": "scripts/missions/missions.lua",
        "size": 29_573,
        "sha256": (
            "505c02a8668ba2e39d868f95051ede81c6cc1611f1e409219b6caa4fbe1d0257"
        ),
        "symbols": ["Mission:BaseUpdate", "Mission:UpdateMission"],
        "reviewed_lines": [[856, 880]],
    },
    {
        "path": "scripts/missions/final/mission_final_two.lua",
        "size": 4_887,
        "sha256": (
            "c8a8e40f512939c1f4fd0e0df416e5cbaec00c639e2985ad776e13c38735b17c"
        ),
        "symbols": [
            "Mission_Final_Cave:UpdateMission",
            "Mission_Final_Cave:AddBomb",
            "BigBomb",
            "AddPawn",
        ],
        "reviewed_lines": [[116, 172], [175, 188]],
    },
)


REGION_SPECS = (
    {
        "id": "space_damage_copy",
        "start": 0x0015B9B0,
        "end": 0x0015BCB4,
        "sha256": "3846fdb1ca2ebc1b4b6e83a64994f82d4907938345ff0d856c9bbea690957fc6",
        "boundary_basis": "Ghidra 12.1.3 SpaceDamage copy function body.",
    },
    {
        "id": "dropper_update",
        "start": 0x0015DCE0,
        "end": 0x0015DEA3,
        "sha256": "aa9e95b94cd0c0f1fd1e1942371c0c4fd88450951deb7f0024b731b5bb43c4ce",
        "boundary_basis": "Ghidra 12.1.3 PylonAnimation update function body.",
    },
    {
        "id": "dropper_constructor",
        "start": 0x0015E170,
        "end": 0x0015E3CD,
        "sha256": "80abb0c25480fb565ea4525f37f0dfc678f5a687681e41e196c4639b6e875756",
        "boundary_basis": "Ghidra 12.1.3 PylonAnimation constructor body.",
    },
    {
        "id": "dropper_impact",
        "start": 0x0015E410,
        "end": 0x0015E45E,
        "sha256": "d7b8f9b38f877834a62e761ffabf0ad22f8cc7955dbfa1a8ddf1f323eb923fe6",
        "boundary_basis": "Ghidra 12.1.3 PylonAnimation impact function body.",
    },
    {
        "id": "apply_space_damage",
        "start": 0x00160110,
        "end": 0x001604BC,
        "sha256": "1597eb6d490f3ae9ee95547a0caa83999502b4ba9c3423bc50b1dca7acc20210",
        "boundary_basis": "Ghidra 12.1.3 Board SpaceDamage application body.",
    },
    {
        "id": "effect_enqueue",
        "start": 0x001606C0,
        "end": 0x00160752,
        "sha256": "0a07ee9377f4bc3bc13be075ccd2a45a01719c8181e231a4450b56d6dd98f4ae",
        "boundary_basis": "Ghidra 12.1.3 Board effect-enqueue function body.",
    },
    {
        "id": "board_add_effect",
        "start": 0x00160880,
        "end": 0x00160960,
        "sha256": "03a3cd32a9051785ee9467a2f63c416b72da009827f134c9dc87234d174f1965",
        "boundary_basis": "Ghidra 12.1.3 Board AddEffect binding body.",
    },
    {
        "id": "effect_dispatcher",
        "start": 0x001610D0,
        "end": 0x00161C6F,
        "sha256": "ccbecc70505f546c2d068ad7c95121f0c631aa27dd197127904de3faaff307c2",
        "boundary_basis": "Ghidra 12.1.3 SkillEffect record dispatcher body.",
    },
    {
        "id": "board_activity_boolean",
        "start": 0x001698E0,
        "end": 0x001698EF,
        "sha256": "0f857820b8f5fea9fcf8165260e7311c458f592b1b952c69bf9da7711359b11c",
        "boundary_basis": "Ghidra 12.1.3 Board activity Boolean wrapper body.",
    },
    {
        "id": "board_activity_reason",
        "start": 0x001698F0,
        "end": 0x00169B22,
        "sha256": "dc9eced8706681fbaa20781c972724170efe9653c37d277e6b8eaaacc5b61a13",
        "boundary_basis": "Ghidra 12.1.3 Board activity-reason function body.",
    },
    {
        "id": "board_effect_update",
        "start": 0x00169BF0,
        "end": 0x0016A1F5,
        "sha256": "c047a08e5f274e629b6fec7151c94c89f5576ec3bbf11b0535546fb65d7c7877",
        "boundary_basis": "Ghidra 12.1.3 Board effect-queue update body.",
    },
    {
        "id": "board_master_update",
        "start": 0x0016A8D0,
        "end": 0x0016BF62,
        "sha256": "6d32a302492920ae4353af4505e792776a18c4f9d8c26bd6cf1f9861a6f9129d",
        "boundary_basis": "Ghidra 12.1.3 Board master-update function body.",
    },
    {
        "id": "board_add_pawn",
        "start": 0x0016E8C0,
        "end": 0x0016EC8D,
        "sha256": "c9031f10d38ba7cb28959b3460aec686a4366b4697accc7479638436aaa7280a",
        "boundary_basis": "Ghidra 12.1.3 Board AddPawn function body.",
    },
    {
        "id": "primary_orchestrator",
        "start": 0x0018AE90,
        "end": 0x0018B36F,
        "sha256": "8a5e7744c920a70f30f8056271d452335be6d601625f8b8d935d5457b77ebf82",
        "boundary_basis": "Ghidra 12.1.3 primary update-orchestrator body.",
    },
    {
        "id": "mission_named_invoker",
        "start": 0x00199900,
        "end": 0x00199998,
        "sha256": "f104b8d01a7d8904631d4481f8c46efca50e906ff1ba29e34f980df21dde3ac6",
        "boundary_basis": "Previously reviewed exact-build function body.",
    },
    {
        "id": "pawn_factory",
        "start": 0x00244DF0,
        "end": 0x00244FE0,
        "sha256": "15a9ff7b5140c97a90f9907c90c506d051136da05475580861c2ba557cf88559",
        "boundary_basis": "Ghidra 12.1.3 pawn factory function body.",
    },
    {
        "id": "add_dropper_binding",
        "start": 0x002579A0,
        "end": 0x00257A7D,
        "sha256": "58c220e4690ef84da004018b95e6de9d13bb39341410e5735a05bdc0f1fb0aef",
        "boundary_basis": "Ghidra 12.1.3 SkillEffect AddDropper binding body.",
    },
    {
        "id": "dropper_factory",
        "start": 0x002599A0,
        "end": 0x00259CD8,
        "sha256": "f9e6200b9ef560b668f8bfc277e16ee523f7af76109704afb2ab387ac51dcad5",
        "boundary_basis": "Ghidra 12.1.3 effect-animation factory body.",
    },
    {
        "id": "space_damage_vector_push",
        "start": 0x00259F00,
        "end": 0x00259FB7,
        "sha256": "39a9908012609c47f77556aea5af0865f3eb36943b5a1860c4c338bb6ea6fbb7",
        "boundary_basis": "Ghidra 12.1.3 0x134-byte record vector-push body.",
    },
    {
        "id": "is_busy_registration_window",
        "start": 0x00279B30,
        "end": 0x00279B4E,
        "sha256": "0b5181d75dc16eee856790f67867debb484c9a3406ae1f4232c535978e07c421",
        "boundary_basis": "Instruction-aligned Luabind registration window.",
    },
    {
        "id": "add_pawn_registration_window",
        "start": 0x0027A14D,
        "end": 0x0027A16B,
        "sha256": "ab23ad325f32f5b601fac09c80f4dd1f75e352e9b883d3a36d846cfa607640da",
        "boundary_basis": "Instruction-aligned Luabind registration window.",
    },
    {
        "id": "add_effect_registration_window",
        "start": 0x0027A738,
        "end": 0x0027A75A,
        "sha256": "167ef9191442cdf7ec1a7bcb98708c4b50bef6cce56c28353b6ff073a1953db9",
        "boundary_basis": "Instruction-aligned Luabind registration window.",
    },
    {
        "id": "add_dropper_registration_window",
        "start": 0x0027B7D3,
        "end": 0x0027B7EE,
        "sha256": "1ea1e9f3b5ab20f3d53326943a9406eba68b4ef99a3473f9b93e1f70f2f009c7",
        "boundary_basis": "Instruction-aligned Luabind registration window.",
    },
    {
        "id": "is_busy_binding_helper",
        "start": 0x00287150,
        "end": 0x002871F0,
        "sha256": "22b23ab6f68448d0b4ddc76ce5dcba8746535f123436f61984a31295fec2e707",
        "boundary_basis": "Ghidra 12.1.3 IsBusy registration-helper body.",
    },
    {
        "id": "add_pawn_binding_helper",
        "start": 0x002881A0,
        "end": 0x00288240,
        "sha256": "b73cd813a1e33f0bf9c62b5794f095331024615f533bfe479d9b99afada2a29a",
        "boundary_basis": "Ghidra 12.1.3 AddPawn registration-helper body.",
    },
    {
        "id": "add_effect_binding_helper",
        "start": 0x00288A90,
        "end": 0x00288B31,
        "sha256": "d71d5c24cd2f3ef4d49db80aa0531569bdd9efe6a457d863cc2bc71db6125123",
        "boundary_basis": "Ghidra 12.1.3 AddEffect registration-helper body.",
    },
    {
        "id": "add_dropper_binding_helper",
        "start": 0x0028B8C0,
        "end": 0x0028B953,
        "sha256": "5bcf3481582c5ead2ee19a13851288c26477e216d00d6811747dda32b7ff191d",
        "boundary_basis": "Ghidra 12.1.3 AddDropper registration-helper body.",
    },
    {
        "id": "is_busy_thunk",
        "start": 0x002E39D2,
        "end": 0x002E39D7,
        "sha256": "ab52016d327a0e88baee8416e1beec908e075db79f28956ec176b75da633ee37",
        "boundary_basis": "Exact five-byte Board secondary-vtable thunk.",
    },
)


STRING_ANCHOR_SPECS = (
    {
        "id": "base_update",
        "region_id": "primary_orchestrator",
        "reference_rva": 0x0018B1D1,
        "instruction_hex": "6878f98200",
        "string_rva": 0x0042F978,
        "text": "BaseUpdate",
        "role": "mission callback invoked after the Board master update",
    },
    {
        "id": "dropper_tag",
        "region_id": "dropper_impact",
        "reference_rva": 0x0015E447,
        "instruction_hex": "6868e08200",
        "string_rva": 0x0042E068,
        "text": "dropper",
        "role": "impact tag emitted after applying stored SpaceDamage",
    },
    {
        "id": "is_busy_name",
        "region_id": "is_busy_binding_helper",
        "reference_rva": 0x0028719F,
        "instruction_hex": "c7420878858300",
        "string_rva": 0x00438578,
        "text": "IsBusy",
        "role": "Lua Board method registered to the exact thunk",
    },
    {
        "id": "add_pawn_name",
        "region_id": "add_pawn_binding_helper",
        "reference_rva": 0x002881EF,
        "instruction_hex": "c7420814878300",
        "string_rva": 0x00438714,
        "text": "AddPawn",
        "role": "Lua Board method registered to the exact add-pawn body",
    },
    {
        "id": "add_effect_name",
        "region_id": "add_effect_registration_window",
        "reference_rva": 0x0027A74E,
        "instruction_hex": "68b0888300",
        "string_rva": 0x004388B0,
        "text": "AddEffect",
        "role": "Lua Board method registered to the exact queueing body",
    },
    {
        "id": "add_dropper_name",
        "region_id": "add_dropper_registration_window",
        "reference_rva": 0x0027B7E2,
        "instruction_hex": "685c8d8300",
        "string_rva": 0x00438D5C,
        "text": "AddDropper",
        "role": "Lua SkillEffect method registered to the exact binding",
    },
)


DATA_POINTER_SPECS = (
    {
        "id": "board_apply_space_damage_slot",
        "data_rva": 0x0042E258,
        "section": ".rdata",
        "executable": False,
        "target_region": "apply_space_damage",
        "target_rva": 0x00160110,
        "role": "Board secondary vtable VA 0x0082e258 slot +0x00",
    },
    {
        "id": "board_effect_dispatch_slot",
        "data_rva": 0x0042E264,
        "section": ".rdata",
        "executable": False,
        "target_region": "effect_dispatcher",
        "target_rva": 0x001610D0,
        "role": "Board secondary vtable VA 0x0082e258 slot +0x0c",
    },
    {
        "id": "board_activity_slot",
        "data_rva": 0x0042E2C0,
        "section": ".rdata",
        "executable": False,
        "target_region": "board_activity_boolean",
        "target_rva": 0x001698E0,
        "role": "Board secondary vtable VA 0x0082e258 slot +0x68",
    },
    {
        "id": "dropper_update_slot",
        "data_rva": 0x0042E0B4,
        "section": ".rdata",
        "executable": False,
        "target_region": "dropper_update",
        "target_rva": 0x0015DCE0,
        "role": "PylonAnimation vtable VA 0x0082e0a0 slot +0x14",
    },
    {
        "id": "dropper_impact_slot",
        "data_rva": 0x0042E0C0,
        "section": ".rdata",
        "executable": False,
        "target_region": "dropper_impact",
        "target_rva": 0x0015E410,
        "role": "PylonAnimation vtable VA 0x0082e0a0 slot +0x20",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "board_update_before_base_update",
        "region_id": "primary_orchestrator",
        "start_rva": 0x0018B0DE,
        "instruction_hex": "8b4e04e8eaf7fdff",
        "meaning": "Load the Board and run its master update before the later BaseUpdate path.",
    },
    {
        "id": "base_update_gate_and_dispatch",
        "region_id": "primary_orchestrator",
        "start_rva": 0x0018B181,
        "instruction_hex": (
            "83bec80f0000060f84b50100008bcee88be9ffffc686283900000083bee40f0000"
            "0074758b86941c00003bc7740a85c074068378040074618b86c80f000083f80574"
            "5683f806745183ec188bcc8965ec6878f98200e835cce7ff83ec18c645fc018bcc"
            "8d96d40f0000c741140f000000c74110000000008379141072048b01eb028bc16a"
            "ff6a0052c60000e8bfcee7ffc645fc00e8e6e60000"
        ),
        "meaning": "After the native Board update, construct BaseUpdate and invoke it through the named mission dispatcher.",
    },
    {
        "id": "board_calls_effect_update",
        "region_id": "board_master_update",
        "start_rva": 0x0016B461,
        "instruction_hex": "8b4d808b4340412b433cc1f802894d803bc80f82c9fdffff8bcbe870e7ffff",
        "meaning": "The Board master update reaches the effect-queue update before returning to the orchestrator.",
    },
    {
        "id": "effect_dequeue_and_dispatch",
        "region_id": "board_effect_update",
        "start_rva": 0x00169D77,
        "instruction_hex": (
            "8d8d58ffffffe8de69ffffc745fc000000008bcb8b03038550ffffff508d854cff"
            "ffff50e860b800008b865c2c00008b96602c00008d04b88d48042bd1525150e8c4"
            "4720008386602c0000fc8d8558ffffff83c40c6a0083ec7c8bcc50e88769ffff8b"
            "460c8d4e0cff500c8d8d58ffffffe8b346faff"
        ),
        "meaning": "Copy and erase one eligible queued SkillEffect and dispatch its copied batch through Board secondary-vtable slot +0x0c.",
    },
    {
        "id": "effect_enqueue_vector",
        "region_id": "effect_enqueue",
        "start_rva": 0x00160708,
        "instruction_hex": (
            "8d8574ffffffc645fc01508d8e502c0000e8524f01008d45f0508d8e5c2c0000"
            "e8d35201008d8d74ffffff"
        ),
        "meaning": "Append the copied effect to Board+0x2c50 and its parallel timing entry at +0x2c5c.",
    },
    {
        "id": "effect_queue_activity_reason",
        "region_id": "board_activity_reason",
        "start_rva": 0x00169A5C,
        "instruction_hex": "8b86502c00003b86542c00007424b8060000005f5e5b8be55dc3",
        "meaning": "Return activity reason 6 while the Board+0x2c50 effect vector is nonempty.",
    },
    {
        "id": "is_busy_registration",
        "region_id": "is_busy_registration_window",
        "start_rva": 0x00279B30,
        "instruction_hex": "c745e8d2396e00ff75f0c745ec0c000000518d4de851518bc8e802d60000",
        "meaning": "Register thunk VA 0x006e39d2 with a +0x0c this-adjustment through the IsBusy helper.",
    },
    {
        "id": "is_busy_thunk_body",
        "region_id": "is_busy_thunk",
        "start_rva": 0x002E39D2,
        "instruction_hex": "8b01ff6068",
        "meaning": "Tail-dispatch Board:IsBusy through the adjusted secondary vtable slot +0x68.",
    },
    {
        "id": "add_pawn_registration",
        "region_id": "add_pawn_registration_window",
        "start_rva": 0x0027A14D,
        "instruction_hex": "c745e8c0e85600ff75f0c745ec00000000518d4de851518bc8e835e00000",
        "meaning": "Register native handler VA 0x0056e8c0 through the hard-coded AddPawn helper.",
    },
    {
        "id": "add_effect_registration",
        "region_id": "add_effect_registration_window",
        "start_rva": 0x0027A738,
        "instruction_hex": "c745e880085600ff75f0c745ec00000000518d4de85168b08883008bc8e836e30000",
        "meaning": "Register native handler VA 0x00560880 under the Lua method name AddEffect.",
    },
    {
        "id": "add_dropper_registration",
        "region_id": "add_dropper_registration_window",
        "start_rva": 0x0027B7D3,
        "instruction_hex": "c745eca0796500ff75f0518d4dec51685c8d83008bc8e8d2000100",
        "meaning": "Register native handler VA 0x006579a0 under the Lua method name AddDropper.",
    },
    {
        "id": "add_dropper_copies_record",
        "region_id": "add_dropper_binding",
        "start_rva": 0x002579CB,
        "instruction_hex": (
            "6aff6a008d853c010000c745fc01000000508d4d70e8eb06dbff8d4508c785a0"
            "00000004000000508d8d8cfdffffc785d000000000000000e8a83ff0ff8d858c"
            "fdffffc645fc02508d8dc0feffffe8923ff0ff8d85c0feffffc645fc03508bcee8"
            "d0240000"
        ),
        "meaning": "Store the image string, mark kind 4, deep-copy the SpaceDamage twice, and append an independent 0x134-byte record.",
    },
    {
        "id": "dispatcher_copies_record",
        "region_id": "effect_dispatcher",
        "start_rva": 0x00161400,
        "instruction_hex": "03c68d8d7cfdffff50e8a2a5ffffc645fc0883bd54feffff03",
        "meaning": "Deep-copy the next 0x134-byte SkillEffect record before interpreting it.",
    },
    {
        "id": "dispatcher_kind_factory",
        "region_id": "effect_dispatcher",
        "start_rva": 0x001614ED,
        "instruction_hex": (
            "83bd14feffff0075448d857cfdffff508d8dc8fbffffe8a8a4ffff81ec34010000"
            "c645fc0a8d85c8fbffff8bcc50e890a4ffff8b038bcbff108d8dc8fbffffc645fc"
            "08e86bcdfaffe9350100008d43f4f7d88d8d7cfdffff1bc023c350e851840f00"
        ),
        "meaning": "A nonzero kind reaches the animation factory with the copied record; kind 4 is handled by the dropper case there.",
    },
    {
        "id": "dropper_factory_kind_four",
        "region_id": "dropper_factory",
        "start_rva": 0x00259A02,
        "instruction_hex": (
            "8b8798000000c745840000000083f80475766810040000e8bdda0f008bf089b5b0"
            "feffff83ec14c645fc018bcc89a5b4feffff83c768c741140f000000c741100000"
            "00008379141072048b01eb028bc16aff6a0057c60000e871e6daff5381ec340100"
            "00c645fc028d85bcfeffff8bcc50e8381ff0ff8bcec645fc01e8ed46f0ff8bf0"
        ),
        "meaning": "Kind 4 allocates a 0x410-byte PylonAnimation and constructs it from the complete copied record and image string.",
    },
    {
        "id": "dropper_constructor_store",
        "region_id": "dropper_constructor",
        "start_rva": 0x0015E1E6,
        "instruction_hex": "8d4508c645fc02508d8edc020000c706a0e08200c786d802000000000000e8a7d7ffff",
        "meaning": "Install the PylonAnimation vtable and copy the complete SpaceDamage into object+0x2dc.",
    },
    {
        "id": "dropper_landing_calls_impact",
        "region_id": "dropper_update",
        "start_rva": 0x0015DE54,
        "instruction_hex": "8b078bcfff5020",
        "meaning": "At the reviewed landing branch, call PylonAnimation vtable slot +0x20.",
    },
    {
        "id": "dropper_impact_applies_record",
        "region_id": "dropper_impact",
        "start_rva": 0x0015E410,
        "instruction_hex": (
            "558bec51568bf181ec340100008bcc8d86dc02000050e885d5ffff8b4e048b01ff"
            "1083ec188bcc6a07c741140f000000c74110000000006868e08200c60100e87c9b"
            "eaffe8c7c6f1ff5e8be55dc3"
        ),
        "meaning": "Copy object+0x2dc and call Board secondary-vtable slot 0 before emitting the dropper tag.",
    },
    {
        "id": "spawn_string_guard",
        "region_id": "apply_space_damage",
        "start_rva": 0x001602FB,
        "instruction_hex": "83bdbc000000000f84640100008b07",
        "meaning": "Enter the pawn-spawn branch only when SpaceDamage sPawn length at +0xb4 is nonzero.",
    },
    {
        "id": "spawn_factory_and_add_pawn",
        "region_id": "apply_space_damage",
        "start_rva": 0x00160388,
        "instruction_hex": (
            "ffb5c40000008845d783ec188bccc741140f000000c74110000000008379141072"
            "048b01eb028bc16affc600008d85ac0000006a0050e80d7deaffb9f06b8d00e823"
            "4a0e008bd88d4ff4a154d28b008983201300008d45c8ff750cff75085350e8d3e4"
            "0000"
        ),
        "meaning": "Copy sPawn from record+0xa4, construct that pawn, then add it to the Board at the original record x/y.",
    },
)


DIRECT_EDGE_SPECS = (
    {
        "id": "orchestrator_to_board_update",
        "source_region": "primary_orchestrator",
        "from_rva": 0x0018B0E1,
        "instruction_hex": "e8eaf7fdff",
        "target_region": "board_master_update",
        "target_rva": 0x0016A8D0,
        "meaning": "Run the Board master update before BaseUpdate.",
    },
    {
        "id": "orchestrator_to_named_invoker",
        "source_region": "primary_orchestrator",
        "from_rva": 0x0018B215,
        "instruction_hex": "e8e6e60000",
        "target_region": "mission_named_invoker",
        "target_rva": 0x00199900,
        "meaning": "Invoke the prepared BaseUpdate callback name.",
    },
    {
        "id": "board_update_to_effect_update",
        "source_region": "board_master_update",
        "from_rva": 0x0016B47B,
        "instruction_hex": "e870e7ffff",
        "target_region": "board_effect_update",
        "target_rva": 0x00169BF0,
        "meaning": "Advance the Board effect queue in the current native Board update.",
    },
    {
        "id": "board_add_effect_to_enqueue",
        "source_region": "board_add_effect",
        "from_rva": 0x0016092C,
        "instruction_hex": "e88ffdffff",
        "target_region": "effect_enqueue",
        "target_rva": 0x001606C0,
        "meaning": "Pass the copied SkillEffect to the queue insertion routine.",
    },
    {
        "id": "activity_boolean_to_reason",
        "source_region": "board_activity_boolean",
        "from_rva": 0x001698E3,
        "instruction_hex": "e808000000",
        "target_region": "board_activity_reason",
        "target_rva": 0x001698F0,
        "meaning": "Convert the comprehensive Board activity reason to Boolean.",
    },
    {
        "id": "add_dropper_first_copy",
        "source_region": "add_dropper_binding",
        "from_rva": 0x00257A03,
        "instruction_hex": "e8a83ff0ff",
        "target_region": "space_damage_copy",
        "target_rva": 0x0015B9B0,
        "meaning": "Deep-copy the augmented AddDropper argument.",
    },
    {
        "id": "add_dropper_second_copy",
        "source_region": "add_dropper_binding",
        "from_rva": 0x00257A19,
        "instruction_hex": "e8923ff0ff",
        "target_region": "space_damage_copy",
        "target_rva": 0x0015B9B0,
        "meaning": "Deep-copy the independent record before vector insertion.",
    },
    {
        "id": "add_dropper_to_vector_push",
        "source_region": "add_dropper_binding",
        "from_rva": 0x00257A2B,
        "instruction_hex": "e8d0240000",
        "target_region": "space_damage_vector_push",
        "target_rva": 0x00259F00,
        "meaning": "Append the copied 0x134-byte dropper record to SkillEffect.",
    },
    {
        "id": "dispatcher_to_space_damage_copy",
        "source_region": "effect_dispatcher",
        "from_rva": 0x00161409,
        "instruction_hex": "e8a2a5ffff",
        "target_region": "space_damage_copy",
        "target_rva": 0x0015B9B0,
        "meaning": "Copy each record before dispatch.",
    },
    {
        "id": "dispatcher_to_animation_factory",
        "source_region": "effect_dispatcher",
        "from_rva": 0x0016154A,
        "instruction_hex": "e851840f00",
        "target_region": "dropper_factory",
        "target_rva": 0x002599A0,
        "meaning": "Create the animation selected by the record kind.",
    },
    {
        "id": "factory_to_dropper_constructor",
        "source_region": "dropper_factory",
        "from_rva": 0x00259A7E,
        "instruction_hex": "e8ed46f0ff",
        "target_region": "dropper_constructor",
        "target_rva": 0x0015E170,
        "meaning": "Construct PylonAnimation for kind 4.",
    },
    {
        "id": "constructor_to_space_damage_copy",
        "source_region": "dropper_constructor",
        "from_rva": 0x0015E204,
        "instruction_hex": "e8a7d7ffff",
        "target_region": "space_damage_copy",
        "target_rva": 0x0015B9B0,
        "meaning": "Retain a complete SpaceDamage copy at object+0x2dc.",
    },
    {
        "id": "impact_to_space_damage_copy",
        "source_region": "dropper_impact",
        "from_rva": 0x0015E426,
        "instruction_hex": "e885d5ffff",
        "target_region": "space_damage_copy",
        "target_rva": 0x0015B9B0,
        "meaning": "Copy the retained record before Board application.",
    },
    {
        "id": "apply_to_pawn_factory",
        "source_region": "apply_space_damage",
        "from_rva": 0x001603C8,
        "instruction_hex": "e8234a0e00",
        "target_region": "pawn_factory",
        "target_rva": 0x00244DF0,
        "meaning": "Construct the pawn named by SpaceDamage.sPawn.",
    },
    {
        "id": "apply_to_board_add_pawn",
        "source_region": "apply_space_damage",
        "from_rva": 0x001603E8,
        "instruction_hex": "e8d3e40000",
        "target_region": "board_add_pawn",
        "target_rva": 0x0016E8C0,
        "meaning": "Add the constructed pawn at the original SpaceDamage x/y.",
    },
    {
        "id": "is_busy_registration_to_helper",
        "source_region": "is_busy_registration_window",
        "from_rva": 0x00279B49,
        "instruction_hex": "e802d60000",
        "target_region": "is_busy_binding_helper",
        "target_rva": 0x00287150,
        "meaning": "Bind the exact thunk under the helper's hard-coded IsBusy name.",
    },
    {
        "id": "add_pawn_registration_to_helper",
        "source_region": "add_pawn_registration_window",
        "from_rva": 0x0027A166,
        "instruction_hex": "e835e00000",
        "target_region": "add_pawn_binding_helper",
        "target_rva": 0x002881A0,
        "meaning": "Bind the exact Board body under the helper's hard-coded AddPawn name.",
    },
    {
        "id": "add_effect_registration_to_helper",
        "source_region": "add_effect_registration_window",
        "from_rva": 0x0027A755,
        "instruction_hex": "e836e30000",
        "target_region": "add_effect_binding_helper",
        "target_rva": 0x00288A90,
        "meaning": "Register the exact Board:AddEffect handler and signature.",
    },
    {
        "id": "add_dropper_registration_to_helper",
        "source_region": "add_dropper_registration_window",
        "from_rva": 0x0027B7E9,
        "instruction_hex": "e8d2000100",
        "target_region": "add_dropper_binding_helper",
        "target_rva": 0x0028B8C0,
        "meaning": "Register the exact SkillEffect:AddDropper handler and signature.",
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


def _bytes_at(
    image: Any,
    data: bytes,
    rva: int,
    size: int,
    *,
    executable: bool | None = True,
    expected_section: str | None = None,
) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise FinalCaveReplacementError(
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
    if section is None or (
        executable is not None and section.executable is not executable
    ):
        expected = "executable" if executable else "non-executable"
        raise FinalCaveReplacementError(
            f"RVA 0x{rva:08x} is not in {expected} file-backed data"
        )
    if expected_section is not None and section.name != expected_section:
        raise FinalCaveReplacementError(
            f"RVA 0x{rva:08x} section differs: "
            f"{expected_section!r} != {section.name!r}"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise FinalCaveReplacementError(
            f"RVA 0x{rva:08x} is not an E8 rel32 call"
        )
    delta = struct.unpack_from("<i", encoded, 1)[0]
    return (rva + 5 + delta) & 0xFFFFFFFF


def _expected_sources() -> list[dict[str, Any]]:
    return [
        {
            "path": spec["path"],
            "size": spec["size"],
            "sha256": spec["sha256"],
            "symbols": spec["symbols"],
            "reviewed_lines": spec["reviewed_lines"],
            "evidence_class": "fact",
        }
        for spec in SOURCE_SPECS
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
            "boundary_basis": spec["boundary_basis"],
        }
        for spec in REGION_SPECS
    ]


def _expected_string_anchors() -> list[dict[str, Any]]:
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


def _expected_data_pointers() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "evidence_class": "fact",
            "data_rva": f"0x{spec['data_rva']:08x}",
            "section": spec["section"],
            "target_region": spec["target_region"],
            "target_rva": f"0x{spec['target_rva']:08x}",
            "target_va": f"0x{EXPECTED_IMAGE_BASE + spec['target_rva']:08x}",
            "role": spec["role"],
        }
        for spec in DATA_POINTER_SPECS
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
            "kind": "direct_rel32",
            "source_region": spec["source_region"],
            "from_rva": f"0x{spec['from_rva']:08x}",
            "instruction_hex": spec["instruction_hex"],
            "target": {
                "type": "region",
                "region": spec["target_region"],
                "rva": f"0x{spec['target_rva']:08x}",
            },
            "evidence_class": "fact",
            "meaning": spec["meaning"],
        }
        for spec in DIRECT_EDGE_SPECS
    ]


def _dependencies() -> list[dict[str, Any]]:
    return [
        {
            "artifact": (
                "data/observatory/native/"
                "windows_build_13725832_31fe35265598_final_end_settlement.json"
            ),
            "artifact_sha256": FINAL_END_SETTLEMENT_ARTIFACT_SHA256,
            "role": (
                "Pins Board:AddEffect copying, effect-vector activity reason "
                "6, and the later Final completion gate."
            ),
        },
        {
            "artifact": (
                "data/observatory/native/"
                "windows_build_13725832_31fe35265598_final_cave_outcome.json"
            ),
            "artifact_sha256": FINAL_CAVE_OUTCOME_ARTIFACT_SHA256,
            "role": (
                "Pins the +2-turn missing-bomb outcome boundary and leaves "
                "replacement materialization to this continuation."
            ),
        },
        {
            "artifact": (
                "data/observatory/native/"
                "windows_build_13725832_31fe35265598_final_cave_map_choice.json"
            ),
            "artifact_sha256": FINAL_CAVE_MAP_CHOICE_ARTIFACT_SHA256,
            "role": (
                "Pins random_int's exact nonzero-max CRT step while leaving "
                "the incoming shared RNG state unavailable."
            ),
        },
    ]


def _contracts() -> dict[str, Any]:
    return {
        "lua_replacement_callback": {
            "callback": "Mission_Final_Cave:UpdateMission",
            "entry_guard": "Board:IsBusy() must be false",
            "trigger": "IsBomb() must be false",
            "source_order": [
                "construct SkillEffect",
                "call AddBomb(effect)",
                "increase TurnLimit by 2",
                "call Board:AddEffect(effect)",
            ],
            "base_update_order": [
                "LiveEnvironment:MarkBoard",
                "bonus-objective bookkeeping",
                "Mission_Final_Cave:UpdateMission",
            ],
        },
        "candidate_selection": {
            "enumeration": "x=0..7 outer loop, y=0..7 inner loop",
            "excluded": [
                "Board:GetPawnTeam(point) == TEAM_PLAYER",
                "Board:IsBuilding(point)",
                "Board:IsEnvironmentDanger(point)",
            ],
            "empty_fallback": [4, 4],
            "draw": "random_removal(list) = table.remove(list, random_int(#list)+1)",
            "edge_predicate": "x <= 1 or x >= 6 or y <= 1 or y >= 6",
            "selection_rule": (
                "Repeatedly remove candidates while the selected point is on "
                "the edge and candidates remain. Any available interior point "
                "is therefore eventually selected; an all-edge pool returns "
                "the last removed edge point."
            ),
            "concrete_draw_count_known": False,
            "concrete_coordinate_known": False,
        },
        "dropper_record": {
            "space_damage_size": "0x134",
            "kind_offset": "0x98",
            "dropper_kind": 4,
            "image_string_offset": "0x68",
            "s_pawn_offset": "0xa4",
            "s_pawn_length_offset": "0xb4",
            "source_s_pawn": "BigBomb",
            "source_damage": 0,
            "source_terrain": "TERRAIN_ROAD",
            "source_sound": "/props/bomb_impact",
            "source_image": "units/mission/bomb.png",
            "copied_during_add_dropper": True,
            "later_lua_mutation_affects_stored_record": False,
        },
        "native_relative_order": {
            "orchestrator": [
                "Board master update",
                "Board effect-queue update within that Board update",
                "mission BaseUpdate",
                "Mission_Final_Cave:UpdateMission from shipped BaseUpdate",
            ],
            "same_board_update_dispatch_possible": False,
            "earliest_dispatch": "a later eligible Board effect update",
            "queued_effect_vector_offset": "0x2c50",
            "queued_effect_activity_reason": 6,
            "immediate_repeat_while_queue_nonempty": False,
        },
        "materialization_path": {
            "record_dispatch": "kind 4 -> PylonAnimation",
            "pylon_vtable_va": "0x0082e0a0",
            "stored_space_damage_offset": "0x2dc",
            "landing_callback_slot": "0x20",
            "impact_board_slot": "0x00",
            "spawn_guard": "SpaceDamage.sPawn length is nonzero",
            "pawn_factory_input": "SpaceDamage.sPawn",
            "board_add_pawn_location": "original SpaceDamage x/y",
            "source_result": "BigBomb is added at the selected AddBomb point",
        },
        "solver_boundary": {
            "materialization_mechanics_proven": True,
            "concrete_coordinate_proven": False,
            "pawn_uid_proven": False,
            "wall_clock_delay_proven": False,
            "repeat_cadence_after_dequeue_proven": False,
            "current_policy": (
                "Keep simulator v406's +2-turn pending marker, candidate set, "
                "depth stop, and mandatory fresh settled bridge read."
            ),
            "simulator_change_required": False,
        },
    }


def _method() -> dict[str, Any]:
    return {
        "boundary_review": (
            "Focused Ghidra 12.1.3 registration, vtable, call-graph, "
            "instruction, and decompiler review joined shipped Lua to the "
            "generic native dropper and pawn-materialization pipeline."
        ),
        "byte_verification": (
            "Capstone 5.0.7 redecodes every published executable region from "
            "its declared start; the verifier rechecks exact control windows, "
            "direct calls, callback strings, and vtable pointers."
        ),
        "copy_boundary": (
            "The AddDropper proof follows two full SpaceDamage copy calls into "
            "the 0x134-byte record vector; later dispatcher, constructor, and "
            "impact copies preserve that record through Board application."
        ),
        "limitations": [
            "Every native address and conclusion applies only to the pinned Windows executable.",
            "Static control flow proves relative engine order, not wall-clock frame timing.",
            "Incoming shared RNG state, selected coordinate, UID allocation, and repeated-cycle cadence remain unresolved.",
            "macOS and other executable builds require independent maps.",
        ],
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "source_callback_and_selection_are_exact",
            "evidence_class": "fact",
            "claim": (
                "Shipped Lua calls AddBomb only after Board:IsBusy is false and "
                "IsBomb is false, then adds exactly 2 to TurnLimit and calls "
                "Board:AddEffect. Candidate enumeration, exclusions, interior "
                "preference, all-edge behavior, and (4,4) fallback are exact."
            ),
            "supports": [
                "scripts/global.lua",
                "scripts/missions/missions.lua",
                "scripts/missions/final/mission_final_two.lua",
                "lua_replacement_callback",
                "candidate_selection",
            ],
            "limitations": [
                "The call-time candidate set and incoming shared RNG state are runtime inputs."
            ],
        },
        {
            "id": "board_update_precedes_replacement_callback",
            "evidence_class": "inference",
            "claim": (
                "The exact primary orchestrator runs the Board master update, "
                "including its effect-queue update, before invoking BaseUpdate; "
                "shipped BaseUpdate invokes UpdateMission last. A replacement "
                "queued by that callback cannot dispatch in the same already-"
                "completed Board-update pass."
            ),
            "supports": [
                "board_update_before_base_update",
                "base_update_gate_and_dispatch",
                "board_calls_effect_update",
                "orchestrator_to_board_update",
                "orchestrator_to_named_invoker",
                "board_update_to_effect_update",
            ],
            "limitations": [
                "The wall-clock duration until the next eligible Board update is not claimed."
            ],
        },
        {
            "id": "is_busy_blocks_queued_repeat",
            "evidence_class": "inference",
            "claim": (
                "The exact IsBusy binding adjusts to Board+0x0c and dispatches "
                "secondary-vtable slot +0x68. That slot returns true for any "
                "nonzero activity reason, and a nonempty +0x2c50 effect vector "
                "returns reason 6. The callback cannot queue another replacement "
                "while this newly queued batch remains in that vector."
            ),
            "supports": [
                "is_busy_registration",
                "is_busy_name",
                "is_busy_thunk_body",
                "board_activity_slot",
                "activity_boolean_to_reason",
                "effect_queue_activity_reason",
            ],
            "limitations": [
                "Activity after dequeue and the complete animation-lifetime cadence are not independently closed."
            ],
        },
        {
            "id": "add_dropper_copy_semantics_are_exact",
            "evidence_class": "inference",
            "claim": (
                "SkillEffect:AddDropper stores the image, writes kind 4, makes "
                "two full SpaceDamage copies, and appends an independent 0x134-"
                "byte record immediately. Later mutation of the Lua SpaceDamage "
                "cannot alter the queued record."
            ),
            "supports": [
                "add_dropper_registration",
                "add_dropper_name",
                "add_dropper_copies_record",
                "add_dropper_first_copy",
                "add_dropper_second_copy",
                "add_dropper_to_vector_push",
            ],
            "limitations": [
                "This says nothing about cancellation of an already queued outer SkillEffect."
            ],
        },
        {
            "id": "add_effect_queues_for_later_dispatch",
            "evidence_class": "inference",
            "claim": (
                "Board:AddEffect reaches the exact effect-enqueue routine, which "
                "appends the copied batch at Board+0x2c50. A later eligible "
                "effect update copies and erases one queued batch before "
                "dispatching it through Board secondary-vtable slot +0x0c."
            ),
            "supports": [
                "add_effect_registration",
                "add_effect_name",
                "board_add_effect_to_enqueue",
                "effect_enqueue_vector",
                "effect_dequeue_and_dispatch",
                "board_effect_dispatch_slot",
            ],
            "limitations": [
                "Eligibility timing is not converted into a wall-clock timestamp."
            ],
        },
        {
            "id": "dropper_preserves_space_damage_to_impact",
            "evidence_class": "inference",
            "claim": (
                "The dispatcher copies each 0x134-byte record. Kind 4 selects a "
                "PylonAnimation whose constructor copies the full record into "
                "object+0x2dc; its landing branch calls vtable slot +0x20, and "
                "the impact function copies that retained record for Board "
                "application."
            ),
            "supports": [
                "dispatcher_copies_record",
                "dispatcher_kind_factory",
                "dispatcher_to_animation_factory",
                "dropper_factory_kind_four",
                "factory_to_dropper_constructor",
                "dropper_constructor_store",
                "dropper_update_slot",
                "dropper_impact_slot",
                "dropper_landing_calls_impact",
                "dropper_impact_applies_record",
            ],
            "limitations": [
                "Visual interpolation and presentation timing are outside the materialization contract."
            ],
        },
        {
            "id": "bigbomb_drop_resolution_path_is_exact",
            "evidence_class": "inference",
            "claim": (
                "Dropper impact invokes Board's exact SpaceDamage application "
                "slot. A nonempty sPawn constructs that named pawn and calls the "
                "exact Board:AddPawn body at the original SpaceDamage x/y. Since "
                "shipped AddBomb set sPawn to BigBomb before the immediate copy, "
                "the selected point materializes a BigBomb when this path lands."
            ),
            "supports": [
                "scripts/missions/final/mission_final_two.lua",
                "board_apply_space_damage_slot",
                "dropper_impact_applies_record",
                "spawn_string_guard",
                "spawn_factory_and_add_pawn",
                "apply_to_pawn_factory",
                "apply_to_board_add_pawn",
                "add_pawn_registration",
                "add_pawn_name",
            ],
            "limitations": [
                "The selected x/y and newly allocated pawn UID are not statically known."
            ],
        },
        {
            "id": "replacement_rng_boundary_is_narrow",
            "evidence_class": "inference",
            "claim": (
                "The broad materialization gap is now split: native construction "
                "and AddPawn resolution are proven, while only the callback-time "
                "candidate set, variable random-removal draw count, incoming CRT "
                "state, concrete coordinate, UID, and full repeat cadence remain."
            ),
            "supports": [
                "candidate_selection",
                "bigbomb_drop_resolution_path_is_exact",
                (
                    "data/observatory/native/"
                    "windows_build_13725832_31fe35265598_final_cave_map_choice.json"
                ),
            ],
            "limitations": [
                "No concrete replacement position should be forecast without a settled live read."
            ],
        },
        {
            "id": "solver_boundary",
            "evidence_class": "inference",
            "claim": (
                "No Rust simulator semantic change is justified. Simulator v406 "
                "already models the exact +2-turn boundary, derives every "
                "source-reachable snapshot candidate, fabricates no pawn or UID, "
                "stops projection, and requires a fresh settled bridge read. The "
                "new native proof validates that conservative handoff."
            ),
            "supports": [
                "native_relative_order",
                "materialization_path",
                "solver_boundary",
            ],
            "limitations": [
                "A future runtime RNG/state capture could justify a separate build-keyed forecast."
            ],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "replacement_coordinate_and_draw_count",
            "question": (
                "What is the exact callback-time candidate set, number of "
                "random removals, incoming CRT state, and selected coordinate?"
            ),
            "static_status": (
                "Enumeration and filtering are exact, but those runtime inputs "
                "are not present in the binary or shipped Lua."
            ),
            "next_evidence": (
                "Keep the candidate-set forecast and consume a fresh settled "
                "bridge state after materialization."
            ),
        },
        {
            "id": "replacement_uid_timing_and_repeat_cadence",
            "question": (
                "What UID is allocated, how long does landing take, and when can "
                "a later loss start another replacement cycle?"
            ),
            "static_status": (
                "Earliest-later-update ordering and queue-stage IsBusy blocking "
                "are proven; post-dequeue animation activity and wall-clock "
                "cadence are not fully joined."
            ),
            "next_evidence": (
                "Use a bounded runtime capture only if exact cadence becomes "
                "necessary; current solver execution already waits for settled state."
            ),
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do macOS/native builds implement the same replacement path?",
            "static_status": "Only Windows build 13725832 is mapped.",
            "next_evidence": "Repeat the focused map against an exact macOS binary.",
        },
    ]


def _summary() -> dict[str, Any]:
    return {
        "lua_source_count": len(SOURCE_SPECS),
        "region_count": len(REGION_SPECS),
        "string_anchor_count": len(STRING_ANCHOR_SPECS),
        "data_pointer_count": len(DATA_POINTER_SPECS),
        "control_window_count": len(CONTROL_WINDOW_SPECS),
        "direct_edge_count": len(DIRECT_EDGE_SPECS),
        "finding_count": len(_findings()),
        "unresolved_count": len(_unresolved()),
        "replacement_materialization_path_proven": True,
        "callback_to_queue_order_proven": True,
        "add_dropper_copy_semantics_proven": True,
        "concrete_coordinate_proven": False,
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
        "supersedes": {
            "artifact": (
                "data/observatory/native/"
                "windows_build_13725832_31fe35265598_final_cave_outcome.json"
            ),
            "artifact_sha256": FINAL_CAVE_OUTCOME_ARTIFACT_SHA256,
            "resolved_gap_ids": ["replacement_materialization"],
            "split_remaining_gap_ids": [
                "replacement_coordinate_and_draw_count",
                "replacement_uid_timing_and_repeat_cadence",
            ],
            "continuation": (
                "The earlier immutable map left replacement materialization "
                "broadly unresolved. This map closes callback-to-AddPawn mechanics "
                "and splits the genuinely runtime-dependent coordinate, UID, and "
                "cadence questions into narrow explicit gaps."
            ),
        },
        "dependencies": _dependencies(),
        "sources": {
            "capstone_version": SUPPORTED_CAPSTONE_VERSION,
            "ghidra_version": "12.1.3",
            "lua_files": _expected_sources(),
        },
        "method": _method(),
        "regions": _expected_regions(),
        "string_anchors": _expected_string_anchors(),
        "data_pointers": _expected_data_pointers(),
        "control_windows": _expected_windows(),
        "direct_call_edges": _expected_edges(),
        "contracts": _contracts(),
        "findings": _findings(),
        "unresolved": _unresolved(),
        "summary": _summary(),
    }


def _verify_sources(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise FinalCaveReplacementError("content root is not a directory")
    for spec in SOURCE_SPECS:
        source = root / Path(spec["path"])
        try:
            resolved = source.resolve(strict=True)
        except OSError as exc:
            raise FinalCaveReplacementError(
                f"missing Lua source {spec['path']}"
            ) from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise FinalCaveReplacementError(
                f"Lua source escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise FinalCaveReplacementError(
                f"Lua source is not a regular non-symlink file: {spec['path']}"
            )
        raw = resolved.read_bytes()
        if (
            len(raw) != spec["size"]
            or hashlib.sha256(raw).hexdigest() != spec["sha256"]
        ):
            raise FinalCaveReplacementError(
                f"Lua source identity differs: {spec['path']}"
            )


def build_final_cave_replacement_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build replacement-bomb boundary map."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise FinalCaveReplacementError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise FinalCaveReplacementError("executable identity differs")
    _verify_sources(content_root)

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
            raise FinalCaveReplacementError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise FinalCaveReplacementError(
                f"region {spec['id']} bytes differ"
            )
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise FinalCaveReplacementError(str(exc)) from exc

    for spec in STRING_ANCHOR_SPECS:
        text = spec["text"].encode("ascii") + b"\0"
        offset = image.rva_span_to_file_offset(spec["string_rva"], len(text))
        if offset is None or data[offset : offset + len(text)] != text:
            raise FinalCaveReplacementError(
                f"string anchor {spec['id']} differs"
            )
        encoded = bytes.fromhex(spec["instruction_hex"])
        if _bytes_at(image, data, spec["reference_rva"], len(encoded)) != encoded:
            raise FinalCaveReplacementError(
                f"string reference {spec['id']} differs"
            )
        instruction = decoded[spec["region_id"]].get(spec["reference_rva"])
        if instruction is None or instruction[1] != encoded:
            raise FinalCaveReplacementError(
                f"string reference {spec['id']} is not an instruction"
            )
        expected_va = image.image_base + spec["string_rva"]
        if struct.pack("<I", expected_va) not in encoded:
            raise FinalCaveReplacementError(
                f"string reference {spec['id']} target differs"
            )

    for spec in DATA_POINTER_SPECS:
        raw = _bytes_at(
            image,
            data,
            spec["data_rva"],
            4,
            executable=spec["executable"],
            expected_section=spec["section"],
        )
        (target_va,) = struct.unpack("<I", raw)
        if target_va != image.image_base + spec["target_rva"]:
            raise FinalCaveReplacementError(
                f"data pointer {spec['id']} target differs"
            )
        if spec["target_rva"] not in decoded[spec["target_region"]]:
            raise FinalCaveReplacementError(
                f"data pointer {spec['id']} target is not an instruction"
            )

    region_by_id = {spec["id"]: spec for spec in REGION_SPECS}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["instruction_hex"])
        start = spec["start_rva"]
        if _bytes_at(image, data, start, len(encoded)) != encoded:
            raise FinalCaveReplacementError(
                f"control window {spec['id']} differs"
            )
        region = region_by_id[spec["region_id"]]
        if not (region["start"] <= start < start + len(encoded) <= region["end"]):
            raise FinalCaveReplacementError(
                f"control window {spec['id']} escapes its region"
            )
        instructions = decoded[spec["region_id"]]
        cursor = start
        while cursor < start + len(encoded):
            instruction = instructions.get(cursor)
            if instruction is None:
                raise FinalCaveReplacementError(
                    f"control window {spec['id']} crosses undecoded bytes"
                )
            cursor += len(instruction[1])
        if cursor != start + len(encoded):
            raise FinalCaveReplacementError(
                f"control window {spec['id']} ends inside an instruction"
            )

    for spec in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(spec["instruction_hex"])
        instruction = decoded[spec["source_region"]].get(spec["from_rva"])
        if instruction is None or instruction[1] != expected:
            raise FinalCaveReplacementError(
                f"direct edge {spec['id']} bytes differ"
            )
        if _direct_target(spec["from_rva"], expected) != spec["target_rva"]:
            raise FinalCaveReplacementError(
                f"direct edge {spec['id']} target differs"
            )
        if spec["target_rva"] not in decoded[spec["target_region"]]:
            raise FinalCaveReplacementError(
                f"direct edge {spec['id']} target is not an instruction"
            )

    windows = {spec["id"]: spec for spec in CONTROL_WINDOW_SPECS}
    edges = {spec["id"]: spec for spec in DIRECT_EDGE_SPECS}
    pointers = {spec["id"]: spec for spec in DATA_POINTER_SPECS}
    if not (
        edges["orchestrator_to_board_update"]["from_rva"]
        < windows["base_update_gate_and_dispatch"]["start_rva"]
        < edges["orchestrator_to_named_invoker"]["from_rva"] + 5
    ):
        raise FinalCaveReplacementError("Board/BaseUpdate order differs")
    if not (
        edges["add_dropper_first_copy"]["from_rva"]
        < edges["add_dropper_second_copy"]["from_rva"]
        < edges["add_dropper_to_vector_push"]["from_rva"]
    ):
        raise FinalCaveReplacementError("AddDropper copy order differs")
    if not (
        windows["dispatcher_copies_record"]["start_rva"]
        < windows["dispatcher_kind_factory"]["start_rva"]
        < edges["dispatcher_to_animation_factory"]["from_rva"] + 5
    ):
        raise FinalCaveReplacementError("record dispatch order differs")
    if not (
        pointers["dropper_impact_slot"]["target_rva"]
        == region_by_id["dropper_impact"]["start"]
        and pointers["board_apply_space_damage_slot"]["target_rva"]
        == region_by_id["apply_space_damage"]["start"]
    ):
        raise FinalCaveReplacementError("dropper/apply vtable relation differs")
    if not (
        edges["apply_to_pawn_factory"]["from_rva"]
        < edges["apply_to_board_add_pawn"]["from_rva"]
    ):
        raise FinalCaveReplacementError("pawn construction/add order differs")
    return _expected_shape()


def validate_final_cave_replacement_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping):
        raise FinalCaveReplacementError("replacement map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise FinalCaveReplacementError("replacement map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "replacement_materialization_path_proven": True,
        "callback_to_queue_order_proven": True,
        "add_dropper_copy_semantics_proven": True,
        "concrete_coordinate_proven": False,
        "simulator_change_required": False,
    }


def validate_final_cave_replacement_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject source, byte, address, or prose drift."""
    expected = build_final_cave_replacement_map(executable, content_root)
    if dict(value) != expected:
        raise FinalCaveReplacementError(
            "replacement map differs from exact-build analysis"
        )
    result = validate_final_cave_replacement_map_binding(value)
    result["status"] = "verified"
    return result


def encode_final_cave_replacement_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
