"""Reproduce the exact-build Final Cave replacement-cadence boundary map.

This continuation joins the already-published replacement materialization
map to the native animation scheduler.  It proves that the kind-4 dropper is
registered in the same active-animation vector consulted by ``Board:IsBusy``
and that the dropper stays busy until its synchronous impact has run.

The map deliberately does not forecast the replacement coordinate, RNG draw
count, pawn UID, or wall-clock presentation duration.  Those remain fresh-read
or runtime-observation boundaries.
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
ANALYSIS_KIND = "final_cave_replacement_cadence_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
REPLACEMENT_ARTIFACT_SHA256 = (
    "b08b6d96d4d4ba0f53c024b301b17a039c8deb944632bbc6b8b4000a6e20af50"
)


class FinalCaveReplacementCadenceError(RuntimeError):
    """Raised when the reviewed replacement-cadence map cannot be reproduced."""


LUA_SOURCE_SPEC = {
    "path": "scripts/game.lua",
    "size": 9_747,
    "sha256": "8fc587a6d341f43cf521ae2c95e91e5739355cb929581a18f9c374fba2c88db7",
    "symbols": ["Values.pod_z", "Values.pod_velocity"],
    "semantic_values": {"pod_z": 300, "pod_velocity": 0.7},
    "required_fragments": (
        b'Values["pod_z"] = 300',
        b'Values["pod_velocity"] = 0.7',
    ),
}


REGION_SPECS = (
    {
        "id": "pylon_busy_predicate",
        "start": 0x0015D1B0,
        "end": 0x0015D1E6,
        "sha256": "26ed8d4d519db8c0047488ff70b7732cf7e8ab78e98463a9f294c681703ff19d",
        "boundary_basis": "Ghidra 12.1.3 PodAnimation activity-predicate body.",
    },
    {
        "id": "pod_animation_constructor",
        "start": 0x0015D1F0,
        "end": 0x0015D615,
        "sha256": "1396b7e9834300dd6699dc61b800bbf62bd73c0383b50d0fcb8902926f999fd2",
        "boundary_basis": "Ghidra 12.1.3 PodAnimation constructor body.",
    },
    {
        "id": "pylon_lifetime_predicate",
        "start": 0x0015D6C0,
        "end": 0x0015D71A,
        "sha256": "955e292a8c64ea5348747dd668dfb2536be5f6baa83cf0ffbebbff1aba73afd3",
        "boundary_basis": "Ghidra 12.1.3 PodAnimation lifetime-predicate body.",
    },
    {
        "id": "pylon_update",
        "start": 0x0015DCE0,
        "end": 0x0015DEA3,
        "sha256": "aa9e95b94cd0c0f1fd1e1942371c0c4fd88450951deb7f0024b731b5bb43c4ce",
        "boundary_basis": "Ghidra 12.1.3 PylonAnimation update body.",
    },
    {
        "id": "effect_dispatcher",
        "start": 0x001610D0,
        "end": 0x00161C6F,
        "sha256": "ccbecc70505f546c2d068ad7c95121f0c631aa27dd197127904de3faaff307c2",
        "boundary_basis": "Ghidra 12.1.3 SkillEffect record-dispatcher body.",
    },
    {
        "id": "board_activity_reason",
        "start": 0x001698F0,
        "end": 0x00169B22,
        "sha256": "dc9eced8706681fbaa20781c972724170efe9653c37d277e6b8eaaacc5b61a13",
        "boundary_basis": "Ghidra 12.1.3 Board activity-reason body.",
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
        "boundary_basis": "Ghidra 12.1.3 Board master-update body.",
    },
)


DATA_ANCHOR_SPECS = (
    {
        "id": "pod_z_name",
        "rva": 0x0042DF88,
        "section": ".rdata",
        "data": b"pod_z\0",
        "meaning": "Native value lookup key used for the dropper's start height.",
    },
    {
        "id": "pod_velocity_name",
        "rva": 0x0042DFB0,
        "section": ".rdata",
        "data": b"pod_velocity\0",
        "meaning": "Native value lookup key used by the PodAnimation constructor.",
    },
    {
        "id": "float_sign_mask",
        "rva": 0x0043D7C0,
        "section": ".rdata",
        "data": bytes.fromhex("00000080000000800000008000000080"),
        "meaning": (
            "Four IEEE-754 sign bits used by XORPS to negate the "
            "pod_z-derived start height."
        ),
    },
)


VTABLE_SPECS = (
    {
        "id": "board_effect_dispatch_slot",
        "data_rva": 0x0042E264,
        "vtable_va": 0x0082E258,
        "slot": 0x0C,
        "target_rva": 0x001610D0,
        "role": "Board secondary vtable slot +0x0c",
    },
    {
        "id": "board_activity_slot",
        "data_rva": 0x0042E2C0,
        "vtable_va": 0x0082E258,
        "slot": 0x68,
        "target_rva": 0x001698E0,
        "role": "Board secondary vtable slot +0x68",
    },
    {
        "id": "pylon_lifetime_slot",
        "data_rva": 0x0042E0A4,
        "vtable_va": 0x0082E0A0,
        "slot": 0x04,
        "target_rva": 0x0015D6C0,
        "role": "PylonAnimation vtable slot +0x04",
    },
    {
        "id": "pylon_busy_slot",
        "data_rva": 0x0042E0AC,
        "vtable_va": 0x0082E0A0,
        "slot": 0x0C,
        "target_rva": 0x0015D1B0,
        "role": "PylonAnimation vtable slot +0x0c",
    },
    {
        "id": "pylon_update_slot",
        "data_rva": 0x0042E0B4,
        "vtable_va": 0x0082E0A0,
        "slot": 0x14,
        "target_rva": 0x0015DCE0,
        "role": "PylonAnimation vtable slot +0x14",
    },
    {
        "id": "pylon_impact_slot",
        "data_rva": 0x0042E0C0,
        "vtable_va": 0x0082E0A0,
        "slot": 0x20,
        "target_rva": 0x0015E410,
        "role": "PylonAnimation vtable slot +0x20",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "constructor_start_height_sign",
        "region_id": "pod_animation_constructor",
        "start_rva": 0x0015D4DC,
        "instruction_hex": (
            "660f6e4b0c83ec180f5bc98bcc6a0c68b0df8200f30f58c8f30f118e"
            "d4010000c741140f000000c7411000000000c60100e8beaaeaffe85904ef"
            "fff30f108ec0010000f30f1096bc010000f30f5c8eb8010000f30f5c96"
            "b4010000f30f1145ecf30f114de00f28c1f30f1155e4f30f59c10f28ca"
            "f30f59caf30f58c1e8631deefff30f1055e40f28d80f57c90f2ed99ff6"
            "c4447a050f28c1eb10f30f1045e00f28caf30f5ecbf30f5ec3f30f594d"
            "ecf30f5945ecf30f114de8f30f108ed40100008b45e8f30f1145ec0f28"
            "c18986c4010000f30f5986c40100008b45ec8986c8010000f30f5ec2e8"
            "881ceeff0f570dc0d783008b4b28f30f1186d8010000f30f118ed4010000"
        ),
        "meaning": (
            "Look up pod_z and pod_velocity, derive the fall trajectory, XOR "
            "the positive pod_z-derived start-height sign bit, and store the "
            "negative fall field at object+0x1d4."
        ),
    },
    {
        "id": "dispatcher_secondary_this",
        "region_id": "board_effect_update",
        "start_rva": 0x00169DD9,
        "instruction_hex": "8b460c8d4e0cff500c",
        "meaning": (
            "Dispatch through Board's secondary vtable with this adjusted to "
            "primary Board+0x0c."
        ),
    },
    {
        "id": "dispatcher_active_append",
        "region_id": "effect_dispatcher",
        "start_rva": 0x0016154A,
        "instruction_hex": (
            "e851840f008bf88db3142d00008d8574fdffff89bd74fdffff3b46047333"
            "8b068d8d74fdffff3bc177278bf92bf88b4604c1ff023b46087508518bce"
            "e8e5a1f3ff8b4e048b0685c974208b04b88901eb198b46043b4608750851"
            "8bcee8c5a1f3ff8b460485c07402893883460404"
        ),
        "meaning": (
            "Append the factory result to dispatcher-this+0x2d14..+0x2d18, "
            "which normalizes to primary Board+0x2d20..+0x2d24."
        ),
    },
    {
        "id": "activity_active_loop",
        "region_id": "board_activity_reason",
        "start_rva": 0x001698F9,
        "instruction_hex": (
            "8b86202d00003b86242d000074458b86242d000033ff2b86202d0000c1f8"
            "0285c074300f1f40008b86202d00008b0cb88b018b400cffd084c00f85b1"
            "0000008b86242d0000472b86202d0000c1f8023bf872d4"
        ),
        "meaning": (
            "Iterate primary Board+0x2d20..+0x2d24 and branch when an "
            "animation's vtable slot +0x0c reports active."
        ),
    },
    {
        "id": "activity_reason_eight_return",
        "region_id": "board_activity_reason",
        "start_rva": 0x001699E9,
        "instruction_hex": "b8080000005f5e5b8be55dc3",
        "meaning": "Return Board activity reason 8 for an active animation.",
    },
    {
        "id": "master_active_loop",
        "region_id": "board_master_update",
        "start_rva": 0x0016A9A8,
        "instruction_hex": (
            "8b83242d000033f62b83202d0000c1f80285c0746c0f1f008b83202d0000"
            "8b0cb08b018b4004ffd084c08b83202d00008b0cb0753385c974068b016a"
            "01ff108b83202d00008b93242d00008d04b08d48042bd1525150e87d3b20"
            "008383242d0000fc83c40c4eeb058b01ff50148b83242d0000462b83202d"
            "0000c1f8023bf07297"
        ),
        "meaning": (
            "Call each active animation's lifetime slot +0x04; destroy and "
            "erase it when false, otherwise call its update slot +0x14."
        ),
    },
    {
        "id": "master_effect_update_call",
        "region_id": "board_master_update",
        "start_rva": 0x0016B461,
        "instruction_hex": (
            "8b4d808b4340412b433cc1f802894d803bc80f82c9fdffff8bcbe870e7ffff"
        ),
        "meaning": (
            "Call the Board effect-queue update after the earlier active-"
            "animation loop in this same master update."
        ),
    },
    {
        "id": "pylon_fall_to_impact",
        "region_id": "pylon_update",
        "start_rva": 0x0015DD39,
        "instruction_hex": (
            "f30f1087dc0100000f57e40f2fc40f8744010000f30f1087d40100008d8f"
            "d40100000f2fc40f832d010000f30f101dd0c88b008d45f0f30f108fc401"
            "0000f30f1087b4010000f30f1097c8010000f30f59cbc745f000000000f3"
            "0f59d3f30f58c1f30f1187b4010000f30f1087b8010000f30f58c2f30f"
            "1187b8010000f30f1087d8010000f30f59c3f30f58010f2fe0f30f11010f"
            "47c1f30f10000f2fc4f30f11010f82b0000000c745e4000000008b45e489"
            "87c401000051c745e8000000008d8fe00100008b45e88987c8010000e8a3"
            "96f2ff8b87fc0100008d4dec48c745ec0400000083f8048945f08d55f0c7"
            "45e8000000000f4dd18d45e88d8f24010000833a000f4fc28b0089878c02"
            "0000c687ac02000001e8cc0700008b078bcfff5020"
        ),
        "meaning": (
            "While object+0x1d4 is negative, integrate the fall; on crossing "
            "zero clamp it nonnegative and synchronously call impact slot +0x20."
        ),
    },
)


DIRECT_EDGE_SPECS = (
    {
        "id": "master_to_effect_update",
        "source_region": "board_master_update",
        "from_rva": 0x0016B47B,
        "instruction_hex": "e870e7ffff",
        "target_region": "board_effect_update",
        "target_rva": 0x00169BF0,
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
        raise FinalCaveReplacementCadenceError(
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
    if section is None or section.name != expected_section:
        raise FinalCaveReplacementCadenceError(
            f"RVA 0x{rva:08x} is not wholly in {expected_section}"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise FinalCaveReplacementCadenceError(
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


def _expected_vtables() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "evidence_class": "fact",
            "data_rva": f"0x{spec['data_rva']:08x}",
            "vtable_va": f"0x{spec['vtable_va']:08x}",
            "slot": f"0x{spec['slot']:02x}",
            "target_rva": f"0x{spec['target_rva']:08x}",
            "target_va": f"0x{EXPECTED_IMAGE_BASE + spec['target_rva']:08x}",
            "section": ".rdata",
            "role": spec["role"],
        }
        for spec in VTABLE_SPECS
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


def _contracts() -> dict[str, Any]:
    return {
        "board_layout_alias": {
            "effect_dispatch_this": "primary Board+0x0c",
            "dispatcher_vector_begin": "this+0x2d14",
            "dispatcher_vector_end": "this+0x2d18",
            "primary_vector_begin": "Board+0x2d20",
            "primary_vector_end": "Board+0x2d24",
            "same_vector_proven": True,
        },
        "initial_fall": {
            "lua_pod_z": 300,
            "lua_pod_velocity": 0.7,
            "constructor_operation": "flip IEEE-754 sign bit",
            "fall_field": "object+0x1d4",
            "fall_field_source": "positive board coordinate plus pod_z",
            "initial_fall_field_strictly_negative": True,
        },
        "busy_and_impact": {
            "board_activity_reason": 8,
            "activity_virtual_slot": "PylonAnimation+0x0c",
            "lifetime_virtual_slot": "PylonAnimation+0x04",
            "update_virtual_slot": "PylonAnimation+0x14",
            "impact_virtual_slot": "PylonAnimation+0x20",
            "busy_while_fall_field_negative": True,
            "lifetime_kept_while_fall_field_negative": True,
            "impact_runs_on_nonnegative_crossing": True,
            "callback_can_observe_nonbusy_missing_bomb_before_impact": False,
        },
        "native_relative_order": {
            "active_animation_update_before_effect_dispatch": True,
            "effect_dispatch_before_lua_replacement_callback": True,
            "new_dropper_first_updates_on_later_board_pass": True,
            "impact_applies_bigbomb_synchronously": True,
        },
        "repeat_cadence": {
            "turn_limit_increment_per_idle_missing_bomb_callback": 2,
            "replacement_effects_per_idle_missing_bomb_callback": 1,
            "duplicate_replacement_before_impact_possible": False,
            "next_replacement_requires_later_bomb_loss": True,
            "semantic_repeat_cadence_proven": True,
            "wall_clock_duration_known": False,
        },
        "solver_handoff": {
            "current_policy": (
                "Keep simulator v406's +2-turn pending marker, candidate set, "
                "depth stop, and mandatory fresh settled bridge read."
            ),
            "reason": (
                "Cadence is now closed, but coordinate selection and UID "
                "allocation still cannot be forecast from a projected snapshot."
            ),
            "simulator_change_required": False,
        },
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "dispatcher_result_enters_busy_vector",
            "evidence_class": "inference",
            "claim": (
                "The effect update calls the dispatcher with this adjusted to "
                "Board+0x0c. The dispatcher's +0x2d14 vector therefore aliases "
                "primary Board+0x2d20, so its PylonAnimation factory result is "
                "immediately visible to the Board activity and update loops."
            ),
            "supports": [
                "dispatcher_secondary_this",
                "board_effect_dispatch_slot",
                "dispatcher_active_append",
                "activity_active_loop",
                "master_active_loop",
            ],
            "limitations": [
                "The field names are analyst labels; the offsets and pointer adjustment are exact."
            ],
        },
        {
            "id": "pylon_is_busy_until_impact",
            "evidence_class": "inference",
            "claim": (
                "The exact game.lua pod_z value 300 makes the constructor's "
                "start-height field positive before its IEEE-754 sign bit is "
                "flipped, so object+0x1d4 starts strictly negative; pod_velocity "
                "0.7 controls the derived trajectory. Both Pylon lifetime and "
                "activity predicates stay true while the fall field is negative. "
                "The Pylon update clamps it nonnegative only on landing and then "
                "synchronously calls impact, leaving no callback-visible "
                "nonbusy/no-bomb gap."
            ),
            "supports": [
                "scripts/game.lua",
                "pod_z_name",
                "pod_velocity_name",
                "float_sign_mask",
                "constructor_start_height_sign",
                "pylon_lifetime_slot",
                "pylon_busy_slot",
                "pylon_update_slot",
                "pylon_impact_slot",
                "pylon_fall_to_impact",
            ],
            "limitations": [
                "Wall-clock animation duration and rendering cadence are not derived."
            ],
        },
        {
            "id": "replacement_repeat_cadence_is_exact",
            "evidence_class": "inference",
            "claim": (
                "A newly queued replacement first blocks IsBusy through the "
                "effect vector, then through the active PylonAnimation until "
                "impact materializes BigBomb. Subsequent UpdateMission calls "
                "therefore cannot queue a duplicate; another +2/replacement "
                "cycle requires that materialized bomb to be lost later and the "
                "Board to become idle again."
            ),
            "supports": [
                "final_cave_replacement",
                "dispatcher_result_enters_busy_vector",
                "pylon_is_busy_until_impact",
                "master_active_loop",
                "master_effect_update_call",
            ],
            "limitations": [
                "The selected coordinate, new UID, and elapsed presentation time remain unknown."
            ],
        },
        {
            "id": "solver_boundary",
            "evidence_class": "inference",
            "claim": (
                "No Rust simulator semantic change is justified. Simulator "
                "v406 already applies one +2 edge, stops projection before "
                "fabricating the replacement pawn, and requires a fresh settled "
                "bridge read; cadence proof removes a native ambiguity without "
                "making coordinate or UID prediction possible."
            ),
            "supports": [
                "replacement_repeat_cadence_is_exact",
                "final_cave_replacement",
            ],
            "limitations": [
                "A future proven RNG-state boundary could justify a narrower handoff."
            ],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "replacement_coordinate_and_draw_count",
            "question": "Which eligible tile and random-removal draw count occur on a concrete callback?",
            "static_status": (
                "Candidate semantics are exact, but callback-time occupancy and incoming CRT state are not."
            ),
            "next_evidence": "Use a settled build-keyed runtime read or prove the incoming RNG state.",
        },
        {
            "id": "replacement_uid_allocation",
            "question": "Which UID is assigned to the materialized BigBomb?",
            "static_status": (
                "Pawn construction and Board:AddPawn are proven; the live allocator state is not."
            ),
            "next_evidence": "Read the settled bridge state after impact.",
        },
        {
            "id": "replacement_wall_clock_duration",
            "question": "How long does queueing, falling, and presentation take in wall-clock time?",
            "static_status": (
                "Semantic ordering is exact; frame delta, rendering, and machine timing are intentionally not converted to seconds."
            ),
            "next_evidence": "Capture timestamped exact-build presentation telemetry only if UI timing matters.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do macOS and other Windows builds use the same cadence implementation?",
            "static_status": "This map is keyed only to Windows build 13725832.",
            "next_evidence": "Produce independent build-keyed boundary maps.",
        },
    ]


def _summary() -> dict[str, Any]:
    return {
        "lua_source_count": 1,
        "region_count": len(REGION_SPECS),
        "data_anchor_count": len(DATA_ANCHOR_SPECS),
        "vtable_pointer_count": len(VTABLE_SPECS),
        "control_window_count": len(CONTROL_WINDOW_SPECS),
        "direct_edge_count": len(DIRECT_EDGE_SPECS),
        "finding_count": len(_findings()),
        "unresolved_count": len(_unresolved()),
        "active_registration_proven": True,
        "busy_until_impact_proven": True,
        "duplicate_before_impact_excluded": True,
        "semantic_repeat_cadence_proven": True,
        "wall_clock_duration_proven": False,
        "concrete_coordinate_proven": False,
        "concrete_uid_proven": False,
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
                    "path": LUA_SOURCE_SPEC["path"],
                    "size": LUA_SOURCE_SPEC["size"],
                    "sha256": LUA_SOURCE_SPEC["sha256"],
                    "symbols": LUA_SOURCE_SPEC["symbols"],
                    "semantic_values": LUA_SOURCE_SPEC["semantic_values"],
                    "evidence_class": "fact",
                }
            ],
        },
        "dependencies": [
            {
                "id": "final_cave_replacement",
                "artifact": (
                    "data/observatory/native/windows_build_13725832_"
                    "31fe35265598_final_cave_replacement.json"
                ),
                "artifact_sha256": REPLACEMENT_ARTIFACT_SHA256,
                "role": (
                    "Pins Lua callback guards, effect queueing, Pylon impact, "
                    "BigBomb construction, and Board:AddPawn materialization."
                ),
            }
        ],
        "supersedes": {
            "artifact": (
                "data/observatory/native/windows_build_13725832_"
                "31fe35265598_final_cave_replacement.json"
            ),
            "resolved_facets": [
                "active_animation_registration",
                "busy_until_dropper_impact",
                "semantic_replacement_repeat_cadence",
            ],
            "remaining_gap_ids": [
                "replacement_coordinate_and_draw_count",
                "replacement_uid_allocation",
                "replacement_wall_clock_duration",
            ],
        },
        "method": {
            "boundary_review": (
                "Focused Ghidra 12.1.3 vtable, multiple-inheritance this-"
                "adjustment, field-use, instruction, and decompiler review."
            ),
            "source_review": (
                "The exact game.lua hash plus pod_z and pod_velocity values are "
                "validated without publishing proprietary source bodies."
            ),
            "limitations": [
                "Every native address and conclusion applies only to the pinned Windows executable.",
                "Relative order does not supply a wall-clock duration.",
                "Incoming CRT state, concrete coordinate, and UID allocator state remain unknown.",
                "macOS and other builds require independent maps.",
            ],
        },
        "contracts": _contracts(),
        "regions": _expected_regions(),
        "data_anchors": _expected_data_anchors(),
        "vtable_pointers": _expected_vtables(),
        "control_windows": _expected_windows(),
        "direct_call_edges": _expected_edges(),
        "findings": _findings(),
        "unresolved": _unresolved(),
        "summary": _summary(),
    }


def _verify_lua_source(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise FinalCaveReplacementCadenceError("content root is not a directory")
    source = root / Path(LUA_SOURCE_SPEC["path"])
    try:
        resolved = source.resolve(strict=True)
    except OSError as exc:
        raise FinalCaveReplacementCadenceError(
            f"missing Lua source {LUA_SOURCE_SPEC['path']}"
        ) from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise FinalCaveReplacementCadenceError(
            f"Lua source escapes content root: {LUA_SOURCE_SPEC['path']}"
        ) from exc
    if source.is_symlink() or not resolved.is_file():
        raise FinalCaveReplacementCadenceError(
            f"Lua source is not a regular non-symlink file: {LUA_SOURCE_SPEC['path']}"
        )
    data = resolved.read_bytes()
    if (
        len(data) != LUA_SOURCE_SPEC["size"]
        or hashlib.sha256(data).hexdigest() != LUA_SOURCE_SPEC["sha256"]
        or any(
            data.count(fragment) != 1
            for fragment in LUA_SOURCE_SPEC["required_fragments"]
        )
    ):
        raise FinalCaveReplacementCadenceError(
            "Lua source identity, pod_z, or pod_velocity differs: "
            f"{LUA_SOURCE_SPEC['path']}"
        )


def build_final_cave_replacement_cadence_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build replacement-cadence boundary map."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise FinalCaveReplacementCadenceError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise FinalCaveReplacementCadenceError("executable identity differs")
    _verify_lua_source(content_root)

    ranges: dict[str, tuple[int, int]] = {}
    for spec in REGION_SPECS:
        size = spec["end"] - spec["start"]
        try:
            body = _region_bytes(
                image, data, spec["start"], size, ".text", spec["id"]
            )
        except Exception as exc:
            raise FinalCaveReplacementCadenceError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise FinalCaveReplacementCadenceError(
                f"region {spec['id']} bytes differ"
            )
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise FinalCaveReplacementCadenceError(str(exc)) from exc

    for spec in DATA_ANCHOR_SPECS:
        actual = _file_backed_bytes(
            image, data, spec["rva"], len(spec["data"]), spec["section"]
        )
        if actual != spec["data"]:
            raise FinalCaveReplacementCadenceError(
                f"data anchor {spec['id']} differs"
            )

    for spec in VTABLE_SPECS:
        encoded = _file_backed_bytes(
            image, data, spec["data_rva"], 4, ".rdata"
        )
        target_va = struct.unpack("<I", encoded)[0]
        if spec["data_rva"] != spec["vtable_va"] - EXPECTED_IMAGE_BASE + spec["slot"]:
            raise FinalCaveReplacementCadenceError(
                f"vtable layout {spec['id']} differs"
            )
        if target_va != EXPECTED_IMAGE_BASE + spec["target_rva"]:
            raise FinalCaveReplacementCadenceError(
                f"vtable target {spec['id']} differs"
            )

    region_specs = {spec["id"]: spec for spec in REGION_SPECS}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["instruction_hex"])
        start = spec["start_rva"]
        actual = _file_backed_bytes(image, data, start, len(encoded), ".text")
        if actual != encoded:
            raise FinalCaveReplacementCadenceError(
                f"control window {spec['id']} differs"
            )
        region = region_specs[spec["region_id"]]
        if not (region["start"] <= start < start + len(encoded) <= region["end"]):
            raise FinalCaveReplacementCadenceError(
                f"control window {spec['id']} escapes its region"
            )
        instructions = decoded[spec["region_id"]]
        cursor = start
        while cursor < start + len(encoded):
            instruction = instructions.get(cursor)
            if instruction is None:
                raise FinalCaveReplacementCadenceError(
                    f"control window {spec['id']} crosses undecoded bytes"
                )
            cursor += len(instruction[1])
        if cursor != start + len(encoded):
            raise FinalCaveReplacementCadenceError(
                f"control window {spec['id']} ends inside an instruction"
            )

    for spec in DIRECT_EDGE_SPECS:
        instruction = decoded[spec["source_region"]].get(spec["from_rva"])
        expected = bytes.fromhex(spec["instruction_hex"])
        if instruction is None or instruction[1] != expected:
            raise FinalCaveReplacementCadenceError(
                f"direct edge {spec['id']} bytes differ"
            )
        if _direct_target(spec["from_rva"], expected) != spec["target_rva"]:
            raise FinalCaveReplacementCadenceError(
                f"direct edge {spec['id']} target differs"
            )
        if spec["target_rva"] not in decoded[spec["target_region"]]:
            raise FinalCaveReplacementCadenceError(
                f"direct edge {spec['id']} target is not an instruction"
            )

    if not (
        0x0C + 0x2D14 == 0x2D20
        and 0x0C + 0x2D18 == 0x2D24
        and 0x0016A9A8 < 0x0016B47B
    ):
        raise FinalCaveReplacementCadenceError(
            "Board layout alias or scheduler order invariant differs"
        )
    return _expected_shape()


def validate_final_cave_replacement_cadence_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping):
        raise FinalCaveReplacementCadenceError("cadence map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise FinalCaveReplacementCadenceError("cadence map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "active_registration_proven": True,
        "busy_until_impact_proven": True,
        "semantic_repeat_cadence_proven": True,
        "concrete_coordinate_proven": False,
        "concrete_uid_proven": False,
        "simulator_change_required": False,
    }


def validate_final_cave_replacement_cadence_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject source, byte, address, or prose drift."""
    expected = build_final_cave_replacement_cadence_map(executable, content_root)
    if dict(value) != expected:
        raise FinalCaveReplacementCadenceError(
            "cadence map differs from exact-build analysis"
        )
    result = validate_final_cave_replacement_cadence_map_binding(value)
    result["status"] = "verified"
    return result


def encode_final_cave_replacement_cadence_map(
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
