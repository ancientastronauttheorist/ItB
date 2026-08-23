"""Reproduce the exact-build Final end and effect-settlement boundary.

This immutable follow-up closes two questions left open by the earlier Final
phase-scheduler map:

* both shipped Final stages reach ordinary victory through a turn-limit/state
  short circuit that precedes ``IsEndBlocked``; and
* a ``SkillEffect`` queued by ``MissionEnd`` keeps the BoardPlayer activity
  gate nonzero, so the later phase handoff cannot run while that queue remains
  populated.

The artifact is deliberately narrower than a runtime trace.  It does not
claim concrete presentation timestamps, prove that arbitrary modified effects
cannot be cancelled, or map the post-``StartMechTravel`` campaign-victory UI.
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
ANALYSIS_KIND = "final_end_settlement_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
SUPERSEDED_SCHEDULER_ARTIFACT_SHA256 = (
    "93b022aa4d7c745805e68485d9a6fc36466ac3cb713b519d1cfe648d1a63a79a"
)


class FinalEndSettlementError(RuntimeError):
    """Raised when the reviewed Final end/settlement map cannot be reproduced."""


SOURCE_SPECS = (
    {
        "path": "scripts/missions/missions.lua",
        "size": 29_573,
        "sha256": (
            "505c02a8668ba2e39d868f95051ede81c6cc1611f1e409219b6caa4fbe1d0257"
        ),
        "symbols": [
            "Mission.TurnLimit",
            "Mission:IsEndBlocked",
            "Mission:IsNextPhase",
        ],
        "reviewed_lines": [[56, 111]],
    },
    {
        "path": "scripts/missions/final/mission_final.lua",
        "size": 3_318,
        "sha256": (
            "f92875ba570871b7b3184adb168105c8f29150398b8b14e87a863f67d6c61e29"
        ),
        "symbols": [
            "Mission_Final",
            "Mission_Final:MissionEnd",
            "Mission_Final:IsEndBlocked",
        ],
        "reviewed_lines": [[3, 13], [59, 122]],
    },
    {
        "path": "scripts/missions/final/mission_final_two.lua",
        "size": 4_887,
        "sha256": (
            "c8a8e40f512939c1f4fd0e0df416e5cbaec00c639e2985ad776e13c38735b17c"
        ),
        "symbols": [
            "Mission_Final_Cave",
            "Mission_Final_Cave:MissionEnd",
            "Mission_Final_Cave:UpdateMission",
            "Mission_Final_Cave:IsEndBlocked",
        ],
        "reviewed_lines": [[3, 13], [25, 33], [116, 124], [175, 177]],
    },
)


REGION_SPECS = (
    {
        "id": "board_constructor",
        "start": 0x0015F150,
        "end": 0x0015F85A,
        "sha256": (
            "ebeddd7980834f5a8a2715f2df794d51675107b478758cfd2db10f1d3fb11f16"
        ),
        "boundary_basis": "Ghidra 12.1.3 Board constructor function body.",
    },
    {
        "id": "effect_enqueue",
        "start": 0x001606C0,
        "end": 0x00160752,
        "sha256": (
            "0a07ee9377f4bc3bc13be075ccd2a45a01719c8181e231a4450b56d6dd98f4ae"
        ),
        "boundary_basis": "Ghidra 12.1.3 effect-enqueue function body.",
    },
    {
        "id": "board_add_effect",
        "start": 0x00160880,
        "end": 0x00160960,
        "sha256": (
            "03a3cd32a9051785ee9467a2f63c416b72da009827f134c9dc87234d174f1965"
        ),
        "boundary_basis": "Ghidra 12.1.3 Board AddEffect binding body.",
    },
    {
        "id": "board_activity_boolean",
        "start": 0x001698E0,
        "end": 0x001698EF,
        "sha256": (
            "0f857820b8f5fea9fcf8165260e7311c458f592b1b952c69bf9da7711359b11c"
        ),
        "boundary_basis": "Ghidra 12.1.3 Board activity boolean wrapper.",
    },
    {
        "id": "board_activity_reason",
        "start": 0x001698F0,
        "end": 0x00169B22,
        "sha256": (
            "dc9eced8706681fbaa20781c972724170efe9653c37d277e6b8eaaacc5b61a13"
        ),
        "boundary_basis": "Ghidra 12.1.3 Board activity-reason function body.",
    },
    {
        "id": "boardplayer_constructor",
        "start": 0x0017FA80,
        "end": 0x001805DE,
        "sha256": (
            "c735b98c1ebef4e9c52c43239f752cfd45e99a7c1c18062235a3c24d5578c84a"
        ),
        "boundary_basis": "Ghidra 12.1.3 BoardPlayer constructor function body.",
    },
    {
        "id": "is_next_phase",
        "start": 0x00182F30,
        "end": 0x00182FFA,
        "sha256": (
            "e8f4a1233b90831e3a17c0496f71bfa3de8ead5bfbb170236763bb3d21d2d432"
        ),
        "boundary_basis": "Previously reviewed exact-build function body.",
    },
    {
        "id": "end_readiness",
        "start": 0x00185BC0,
        "end": 0x00185D92,
        "sha256": (
            "a3fcc9c4e1f4561c46f1b371f515090001578c02bebc718029dc5939f17fae16"
        ),
        "boundary_basis": "Previously reviewed exact-build function body.",
    },
    {
        "id": "turn_state_transition",
        "start": 0x0018A2C0,
        "end": 0x0018A955,
        "sha256": (
            "903ca7d14ba5317753901f70ec24acfb31ea44e947d3ebce3246651897bc2b90"
        ),
        "boundary_basis": "Ghidra 12.1.3 BoardPlayer state-transition body.",
    },
    {
        "id": "phase_transition",
        "start": 0x001891D0,
        "end": 0x0018964D,
        "sha256": (
            "3a5b364d9af48610bb07f8e44d5cb9ddb4051f4cb4a5fa0ad0db8eb51522073f"
        ),
        "boundary_basis": "Previously reviewed exact-build function body.",
    },
    {
        "id": "primary_orchestrator",
        "start": 0x0018AE90,
        "end": 0x0018B36F,
        "sha256": (
            "8a5e7744c920a70f30f8056271d452335be6d601625f8b8d935d5457b77ebf82"
        ),
        "boundary_basis": "Previously reviewed exact-build function body.",
    },
    {
        "id": "mission_end_dispatch",
        "start": 0x0018B780,
        "end": 0x0018B9FF,
        "sha256": (
            "00e1f495aa53d2a439c4eeb6e41e1d5ac5b304e0c050e4343bd0433f9ff74ee9"
        ),
        "boundary_basis": "Previously reviewed exact-build function body.",
    },
    {
        "id": "boardplayer_activity_bridge",
        "start": 0x001936E0,
        "end": 0x001936ED,
        "sha256": (
            "28b7c171070ae6f815fb1f5bc3f59431d581243a17720b2b55a9c7a158ee521b"
        ),
        "boundary_basis": "Ghidra 12.1.3 BoardPlayer virtual bridge body.",
    },
    {
        "id": "mission_named_invoker",
        "start": 0x00199900,
        "end": 0x00199998,
        "sha256": (
            "f104b8d01a7d8904631d4481f8c46efca50e906ff1ba29e34f980df21dde3ac6"
        ),
        "boundary_basis": "Previously reviewed exact-build function body.",
    },
    {
        "id": "add_effect_registration_window",
        "start": 0x0027A738,
        "end": 0x0027A75A,
        "sha256": (
            "167ef9191442cdf7ec1a7bcb98708c4b50bef6cce56c28353b6ff073a1953db9"
        ),
        "boundary_basis": (
            "Instruction-aligned Luabind registration window inside the "
            "reviewed registration function; this is not a function boundary."
        ),
    },
)


STRING_ANCHOR_SPECS = (
    {
        "id": "get_turn_limit",
        "region_id": "end_readiness",
        "reference_rva": 0x00185C24,
        "instruction_hex": "6858f38200",
        "string_rva": 0x0042F358,
        "text": "GetTurnLimit",
        "role": "current mission turn-limit callback",
    },
    {
        "id": "is_end_blocked",
        "region_id": "end_readiness",
        "reference_rva": 0x00185CC1,
        "instruction_hex": "6808f58200",
        "string_rva": 0x0042F508,
        "text": "IsEndBlocked",
        "role": "fallback mission-end veto callback",
    },
    {
        "id": "mission_end",
        "region_id": "mission_end_dispatch",
        "reference_rva": 0x0018B984,
        "instruction_hex": "68e8f98200",
        "string_rva": 0x0042F9E8,
        "text": "MissionEnd",
        "role": "mission completion callback",
    },
    {
        "id": "board_add_effect",
        "region_id": "add_effect_registration_window",
        "reference_rva": 0x0027A74E,
        "instruction_hex": "68b0888300",
        "string_rva": 0x004388B0,
        "text": "AddEffect",
        "role": "Board method registered to the reviewed native binding",
    },
)


DATA_POINTER_SPECS = (
    {
        "id": "boardplayer_activity_slot",
        "data_rva": 0x00430188,
        "vtable_va": 0x00830148,
        "slot_offset": 0x40,
        "target_region": "boardplayer_activity_bridge",
        "target_rva": 0x001936E0,
        "role": "BoardPlayer virtual activity slot used by the orchestrator",
    },
    {
        "id": "board_activity_slot",
        "data_rva": 0x0042E2C0,
        "vtable_va": 0x0082E258,
        "slot_offset": 0x68,
        "target_region": "board_activity_boolean",
        "target_rva": 0x001698E0,
        "role": "Board secondary-vtable activity boolean slot",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "board_secondary_vtable_install",
        "region_id": "board_constructor",
        "start_rva": 0x0015F1F0,
        "instruction_hex": "c707fce28200c70358e28200",
        "meaning": (
            "Install the Board primary vtable and its secondary vtable at "
            "Board+0x0c."
        ),
    },
    {
        "id": "effect_enqueue_vector",
        "region_id": "effect_enqueue",
        "start_rva": 0x00160708,
        "instruction_hex": (
            "8d8574ffffffc645fc01508d8e502c0000e8524f01008d45f050"
            "8d8e5c2c0000e8d3520100"
        ),
        "meaning": (
            "Append the copied 0x7c-byte effect to the Board vector at "
            "+0x2c50 and its parallel timing value at +0x2c5c."
        ),
    },
    {
        "id": "effect_queue_activity_reason",
        "region_id": "board_activity_reason",
        "start_rva": 0x00169A5C,
        "instruction_hex": (
            "8b86502c00003b86542c00007424b8060000005f5e5b8be55dc3"
        ),
        "meaning": (
            "Return nonzero activity reason 6 while the +0x2c50 effect "
            "vector begin and end pointers differ."
        ),
    },
    {
        "id": "activity_reason_to_boolean",
        "region_id": "board_activity_boolean",
        "start_rva": 0x001698E0,
        "instruction_hex": "83c1f4e808000000f7d81bc0f7d8c3",
        "meaning": (
            "Call the Board activity-reason routine and return true exactly "
            "when its result is nonzero."
        ),
    },
    {
        "id": "boardplayer_vtable_install",
        "region_id": "boardplayer_constructor",
        "start_rva": 0x0017FAC8,
        "instruction_hex": "c70648018300",
        "meaning": "Install the BoardPlayer vtable at VA 0x00830148.",
    },
    {
        "id": "board_construction_and_attachment",
        "region_id": "boardplayer_constructor",
        "start_rva": 0x0018052D,
        "instruction_hex": (
            "e8a96f1d0083c4048945f08bc8c645fc23e80decfdffc645fc22"
            "8d9600390000894604"
        ),
        "meaning": (
            "Allocate and construct the Board, then retain its pointer at "
            "BoardPlayer+0x04."
        ),
    },
    {
        "id": "final_limit_short_circuit",
        "region_id": "end_readiness",
        "start_rva": 0x00185C71,
        "instruction_hex": (
            "e84a38ecff83bee40f0000007424398654010000752283bec80f000002"
            "7513b0018b4df464890d00000000595f5e8be55dc3"
        ),
        "meaning": (
            "After GetTurnLimit, return ready when an active Board exists, "
            "turn equals that limit, and BoardPlayer state is 2. This return "
            "precedes the later IsEndBlocked dispatch."
        ),
    },
    {
        "id": "turn_state_store",
        "region_id": "turn_state_transition",
        "start_rva": 0x0018A367,
        "instruction_hex": (
            "8b4f048d8564ffffff50e8fabaf6ffc745fc000000008b9d64ffffff"
            "89b7c80f000083fe050f878a050000"
        ),
        "meaning": (
            "Store the requested transition argument into BoardPlayer state "
            "+0xfc8 before dispatching its state-specific branch."
        ),
    },
    {
        "id": "mission_end_callback_then_state_five",
        "region_id": "mission_end_dispatch",
        "start_rva": 0x0018B984,
        "instruction_hex": (
            "68e8f98200e882c4e7ff83ec18c745fc000000008d86d40f00008bcc"
            "50e86af2ebffc745fcffffffffe84edf00008bcee8370200006a058bce"
            "e8fee8ffff"
        ),
        "meaning": (
            "Dispatch MissionEnd, perform reviewed completion bookkeeping, "
            "then request BoardPlayer state 5."
        ),
    },
    {
        "id": "handoff_activity_gate",
        "region_id": "primary_orchestrator",
        "start_rva": 0x0018B11A,
        "instruction_hex": (
            "8b068bce8b4040ffd084c0755a8b86c80f000083f80475046a03eb44"
            "83f80575468a86a81a000084c0753c3886c845000075348d8e54200000"
            "e8d873060084c075258bcee8cd7dffff84c074098bcee862e0ffffeb11"
        ),
        "meaning": (
            "Exit the handoff branch when BoardPlayer activity is true. Only "
            "an activity-clear state 5 can reach IsNextPhase and the phase "
            "transition."
        ),
    },
    {
        "id": "add_effect_registration",
        "region_id": "add_effect_registration_window",
        "start_rva": 0x0027A738,
        "instruction_hex": (
            "c745e880085600ff75f0c745ec00000000518d4de85168b0888300"
            "8bc8e836e30000"
        ),
        "meaning": (
            "Register native handler VA 0x00560880 under the Lua method name "
            "AddEffect."
        ),
    },
)


DIRECT_EDGE_SPECS = (
    {
        "id": "boardplayer_constructor_to_board_constructor",
        "source_region": "boardplayer_constructor",
        "from_rva": 0x0018053E,
        "instruction_hex": "e80decfdff",
        "target_region": "board_constructor",
        "target_rva": 0x0015F150,
        "meaning": "Construct the Board retained by BoardPlayer.",
    },
    {
        "id": "board_add_effect_to_effect_enqueue",
        "source_region": "board_add_effect",
        "from_rva": 0x0016092C,
        "instruction_hex": "e88ffdffff",
        "target_region": "effect_enqueue",
        "target_rva": 0x001606C0,
        "meaning": "Pass the copied SkillEffect to the queue insertion routine.",
    },
    {
        "id": "board_activity_boolean_to_reason",
        "source_region": "board_activity_boolean",
        "from_rva": 0x001698E3,
        "instruction_hex": "e808000000",
        "target_region": "board_activity_reason",
        "target_rva": 0x001698F0,
        "meaning": "Obtain the comprehensive Board activity reason code.",
    },
    {
        "id": "mission_dispatch_to_end_readiness",
        "source_region": "mission_end_dispatch",
        "from_rva": 0x0018B826,
        "instruction_hex": "e895a3ffff",
        "target_region": "end_readiness",
        "target_rva": 0x00185BC0,
        "meaning": "Evaluate the ordinary mission-end readiness boundary.",
    },
    {
        "id": "mission_dispatch_to_named_invoker",
        "source_region": "mission_end_dispatch",
        "from_rva": 0x0018B9AD,
        "instruction_hex": "e84edf0000",
        "target_region": "mission_named_invoker",
        "target_rva": 0x00199900,
        "meaning": "Execute the constructed MissionEnd callback.",
    },
    {
        "id": "mission_dispatch_to_state_transition",
        "source_region": "mission_end_dispatch",
        "from_rva": 0x0018B9BD,
        "instruction_hex": "e8fee8ffff",
        "target_region": "turn_state_transition",
        "target_rva": 0x0018A2C0,
        "meaning": "Enter requested BoardPlayer state 5 after MissionEnd.",
    },
    {
        "id": "primary_to_is_next_phase",
        "source_region": "primary_orchestrator",
        "from_rva": 0x0018B15E,
        "instruction_hex": "e8cd7dffff",
        "target_region": "is_next_phase",
        "target_rva": 0x00182F30,
        "meaning": "Evaluate IsNextPhase only after the activity gate clears.",
    },
    {
        "id": "primary_to_phase_transition",
        "source_region": "primary_orchestrator",
        "from_rva": 0x0018B169,
        "instruction_hex": "e862e0ffff",
        "target_region": "phase_transition",
        "target_rva": 0x001891D0,
        "meaning": "Create the next phase only after a true predicate result.",
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
        raise FinalEndSettlementError(
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
        raise FinalEndSettlementError(
            f"RVA 0x{rva:08x} is not in {expected} file-backed data"
        )
    if expected_section is not None and section.name != expected_section:
        raise FinalEndSettlementError(
            f"RVA 0x{rva:08x} section differs: "
            f"{expected_section!r} != {section.name!r}"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise FinalEndSettlementError(
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
            "section": ".rdata",
            "vtable_va": f"0x{spec['vtable_va']:08x}",
            "slot_offset": f"0x{spec['slot_offset']:02x}",
            "target_region": spec["target_region"],
            "target_rva": f"0x{spec['target_rva']:08x}",
            "target_va": (
                f"0x{EXPECTED_IMAGE_BASE + spec['target_rva']:08x}"
            ),
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


def _contracts() -> dict[str, Any]:
    return {
        "ordinary_final_end_trigger": {
            "inputs": [
                "active Board pointer is nonzero",
                "current turn equals Mission:GetTurnLimit()",
                "BoardPlayer state equals 2",
            ],
            "result": "end_readiness returns true",
            "is_end_blocked_invoked_on_this_branch": False,
            "applies_to": ["Mission_Final", "Mission_Final_Cave"],
            "cave_extension_behavior": (
                "Mission_Final_Cave may increase TurnLimit by 2 after a "
                "missing bomb; the equality check uses the current Lua value."
            ),
        },
        "mission_end_effect_handoff": {
            "lua_enqueue": "MissionEnd calls Board:AddEffect(effect)",
            "native_effect_vector_offset": "0x2c50",
            "native_effect_vector_end_offset": "0x2c54",
            "nonempty_activity_reason": 6,
            "boardplayer_activity_vtable_offset": "0x40",
            "board_activity_vtable_offset": "0x68",
            "completion_state": 5,
            "handoff_requires_activity_clear": True,
            "surface_handoff_after_clear": (
                "IsNextPhase -> phase_transition -> GAME.CreateNextPhase"
            ),
            "cave_exit_after_clear": (
                "IsNextPhase is false and the ordinary completed-mission exit "
                "branch runs."
            ),
        },
    }


def _method() -> dict[str, Any]:
    return {
        "boundary_review": (
            "Focused Ghidra 12.1.3 constructor, vtable, reference, call-graph, "
            "and decompiler review joined Final readiness to the Board "
            "SkillEffect queue and the later completion-state handoff."
        ),
        "byte_verification": (
            "Capstone 5.0.7 redecodes every published executable region from "
            "its declared start; the verifier rechecks exact windows, direct "
            "calls, callback strings, and both vtable pointers."
        ),
        "limitations": [
            "Every native address and conclusion applies only to the pinned Windows executable.",
            "Static activity gating proves queue-empty ordering, not wall-clock timing or arbitrary modified-effect cancellation behavior.",
            "The post-StartMechTravel campaign-victory and presentation path remains outside this map.",
            "macOS and other executable builds require independent maps.",
        ],
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "final_limit_bypasses_end_block",
            "evidence_class": "inference",
            "claim": (
                "On the reviewed ordinary state-2 limit boundary, native end "
                "readiness returns true before constructing or invoking "
                "IsEndBlocked. The always-true Final callbacks therefore do "
                "not veto this exact branch."
            ),
            "supports": [
                "end_readiness",
                "get_turn_limit",
                "final_limit_short_circuit",
                "is_end_blocked",
            ],
            "limitations": [
                "Other state/turn combinations continue through the separate fallback gates."
            ],
        },
        {
            "id": "both_final_stages_use_current_limit",
            "evidence_class": "inference",
            "claim": (
                "Mission_Final and Mission_Final_Cave both inherit the native "
                "turn-limit completion mechanism despite overriding "
                "IsEndBlocked to true. The cave's source-level +2 replacement "
                "extension moves the equality boundary because native code "
                "queries the current GetTurnLimit value."
            ),
            "supports": [
                "scripts/missions/missions.lua",
                "scripts/missions/final/mission_final.lua",
                "scripts/missions/final/mission_final_two.lua",
                "ordinary_final_end_trigger",
            ],
            "limitations": [
                "This does not make bomb destruction a terminal loss or predict replacement coordinates."
            ],
        },
        {
            "id": "mission_end_queues_native_effect",
            "evidence_class": "inference",
            "claim": (
                "Both shipped Final MissionEnd callbacks call Board:AddEffect. "
                "The exact AddEffect registration selects the reviewed native "
                "binding, which copies the SkillEffect and appends it to the "
                "Board vector rooted at +0x2c50."
            ),
            "supports": [
                "scripts/missions/final/mission_final.lua",
                "scripts/missions/final/mission_final_two.lua",
                "board_add_effect",
                "add_effect_registration",
                "board_add_effect_to_effect_enqueue",
                "effect_enqueue_vector",
            ],
            "limitations": [
                "Individual presentation opcodes inside the effect are not reconstructed here."
            ],
        },
        {
            "id": "queued_effect_is_board_activity",
            "evidence_class": "inference",
            "claim": (
                "A nonempty +0x2c50 effect vector returns Board activity reason "
                "6; the exact Board secondary-vtable slot converts any nonzero "
                "reason to true, and BoardPlayer's activity slot delegates to "
                "that Board slot."
            ),
            "supports": [
                "effect_queue_activity_reason",
                "activity_reason_to_boolean",
                "board_activity_slot",
                "boardplayer_activity_slot",
                "boardplayer_activity_bridge",
            ],
            "limitations": [
                "Reason 6 is one of several activity sources checked by the comprehensive routine."
            ],
        },
        {
            "id": "phase_handoff_waits_for_activity_clear",
            "evidence_class": "inference",
            "claim": (
                "After dispatching MissionEnd, native code requests "
                "BoardPlayer completion state 5. The primary orchestrator "
                "exits the handoff branch while BoardPlayer activity is true; "
                "only after it is false can state 5 reach IsNextPhase and the "
                "surface phase transition."
            ),
            "supports": [
                "mission_end_callback_then_state_five",
                "turn_state_store",
                "handoff_activity_gate",
                "primary_to_is_next_phase",
                "primary_to_phase_transition",
            ],
            "limitations": [
                "Additional native flags in the same handoff branch can delay it further."
            ],
        },
        {
            "id": "final_mission_end_effects_precede_exit",
            "evidence_class": "inference",
            "claim": (
                "Mission_Final's queued fall/slide effect and "
                "Mission_Final_Cave's queued StartMechTravel effect keep the "
                "reviewed handoff/exit gate closed at least until their native "
                "effect vector is empty and the comprehensive Board activity "
                "check returns zero."
            ),
            "supports": [
                "mission_end_queues_native_effect",
                "queued_effect_is_board_activity",
                "phase_handoff_waits_for_activity_clear",
            ],
            "limitations": [
                "The later campaign-victory UI and save settlement are not mapped."
            ],
        },
        {
            "id": "solver_boundary",
            "evidence_class": "inference",
            "claim": (
                "No Rust simulator semantic change follows. Combat still ends "
                "at the live limit boundary, and cross-stage state must still "
                "come from a fresh settled bridge read rather than fabricated "
                "MissionEnd animation or cave-start results."
            ),
            "supports": [
                "both_final_stages_use_current_limit",
                "phase_handoff_waits_for_activity_clear",
            ],
            "limitations": [
                "Concrete cave RNG and post-travel campaign state remain separate boundaries."
            ],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "post_travel_campaign_victory",
            "question": (
                "How does Board:StartMechTravel settle into campaign victory, "
                "profile/save mutation, and final presentation?"
            ),
            "static_status": (
                "The MissionEnd queue and activity-clear exit gate are pinned; "
                "the post-script campaign path is not."
            ),
            "next_evidence": (
                "Continue static review from the StartMechTravel binding and "
                "the cave's false IsNextPhase exit branch."
            ),
        },
        {
            "id": "arbitrary_effect_cancellation",
            "question": (
                "Can a modified/debug path cancel a queued MissionEnd effect "
                "rather than executing every action?"
            ),
            "static_status": (
                "Ordinary queue-empty ordering is exact; arbitrary mutation "
                "or cancellation is outside shipped Final source reachability."
            ),
            "next_evidence": "Treat modified cancellation as out of scope unless observed.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do macOS/native builds implement the same boundary?",
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
        "final_end_state_trigger_proven": True,
        "mission_effect_handoff_gate_proven": True,
        "post_travel_campaign_victory_proven": False,
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
                "windows_build_13725832_31fe35265598_final_phase_scheduler.json"
            ),
            "artifact_sha256": SUPERSEDED_SCHEDULER_ARTIFACT_SHA256,
            "resolved_gap_ids": [
                "final_end_state_trigger",
                "mission_end_effect_settlement",
            ],
            "narrowed_gap_ids": ["cave_countdown_outcome"],
            "correction": (
                "The earlier immutable artifact conservatively described an "
                "external Final end-state trigger. Exact review now proves a "
                "turn-limit/state-2 readiness short circuit before "
                "IsEndBlocked; no Final-only external writer is required."
            ),
        },
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
        raise FinalEndSettlementError("content root is not a directory")
    for spec in SOURCE_SPECS:
        source = root / Path(spec["path"])
        try:
            resolved = source.resolve(strict=True)
        except OSError as exc:
            raise FinalEndSettlementError(
                f"missing Lua source {spec['path']}"
            ) from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise FinalEndSettlementError(
                f"Lua source escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise FinalEndSettlementError(
                f"Lua source is not a regular non-symlink file: {spec['path']}"
            )
        raw = resolved.read_bytes()
        if (
            len(raw) != spec["size"]
            or hashlib.sha256(raw).hexdigest() != spec["sha256"]
        ):
            raise FinalEndSettlementError(
                f"Lua source identity differs: {spec['path']}"
            )


def build_final_end_settlement_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build Final end/settlement boundary map."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise FinalEndSettlementError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise FinalEndSettlementError("executable identity differs")
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
            raise FinalEndSettlementError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise FinalEndSettlementError(
                f"region {spec['id']} bytes differ"
            )
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise FinalEndSettlementError(str(exc)) from exc

    for spec in STRING_ANCHOR_SPECS:
        text = spec["text"].encode("ascii") + b"\0"
        offset = image.rva_span_to_file_offset(spec["string_rva"], len(text))
        if offset is None or data[offset : offset + len(text)] != text:
            raise FinalEndSettlementError(
                f"string anchor {spec['id']} differs"
            )
        encoded = bytes.fromhex(spec["instruction_hex"])
        if _bytes_at(image, data, spec["reference_rva"], len(encoded)) != encoded:
            raise FinalEndSettlementError(
                f"string reference {spec['id']} differs"
            )
        instruction = decoded[spec["region_id"]].get(spec["reference_rva"])
        if instruction is None or instruction[1] != encoded:
            raise FinalEndSettlementError(
                f"string reference {spec['id']} is not an instruction"
            )
        expected_va = image.image_base + spec["string_rva"]
        if struct.pack("<I", expected_va) not in encoded:
            raise FinalEndSettlementError(
                f"string reference {spec['id']} target differs"
            )

    region_by_id = {spec["id"]: spec for spec in REGION_SPECS}
    for spec in DATA_POINTER_SPECS:
        raw = _bytes_at(
            image,
            data,
            spec["data_rva"],
            4,
            executable=False,
            expected_section=".rdata",
        )
        (target_va,) = struct.unpack("<I", raw)
        if target_va != image.image_base + spec["target_rva"]:
            raise FinalEndSettlementError(
                f"data pointer {spec['id']} target differs"
            )
        if spec["data_rva"] != (
            spec["vtable_va"] - image.image_base + spec["slot_offset"]
        ):
            raise FinalEndSettlementError(
                f"data pointer {spec['id']} vtable offset differs"
            )
        if spec["target_rva"] not in decoded[spec["target_region"]]:
            raise FinalEndSettlementError(
                f"data pointer {spec['id']} target is not an instruction"
            )

    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["instruction_hex"])
        start = spec["start_rva"]
        if _bytes_at(image, data, start, len(encoded)) != encoded:
            raise FinalEndSettlementError(
                f"control window {spec['id']} differs"
            )
        region = region_by_id[spec["region_id"]]
        if not (region["start"] <= start < start + len(encoded) <= region["end"]):
            raise FinalEndSettlementError(
                f"control window {spec['id']} escapes its region"
            )
        instructions = decoded[spec["region_id"]]
        cursor = start
        while cursor < start + len(encoded):
            instruction = instructions.get(cursor)
            if instruction is None:
                raise FinalEndSettlementError(
                    f"control window {spec['id']} crosses undecoded bytes"
                )
            cursor += len(instruction[1])
        if cursor != start + len(encoded):
            raise FinalEndSettlementError(
                f"control window {spec['id']} ends inside an instruction"
            )

    for spec in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(spec["instruction_hex"])
        instruction = decoded[spec["source_region"]].get(spec["from_rva"])
        if instruction is None or instruction[1] != expected:
            raise FinalEndSettlementError(
                f"direct edge {spec['id']} bytes differ"
            )
        if _direct_target(spec["from_rva"], expected) != spec["target_rva"]:
            raise FinalEndSettlementError(
                f"direct edge {spec['id']} target differs"
            )
        if spec["target_rva"] not in decoded[spec["target_region"]]:
            raise FinalEndSettlementError(
                f"direct edge {spec['id']} target is not an instruction"
            )

    edges = {spec["id"]: spec["from_rva"] for spec in DIRECT_EDGE_SPECS}
    windows = {
        spec["id"]: spec["start_rva"] for spec in CONTROL_WINDOW_SPECS
    }
    if not (
        edges["mission_dispatch_to_named_invoker"]
        < edges["mission_dispatch_to_state_transition"]
    ):
        raise FinalEndSettlementError("MissionEnd/state-5 order differs")
    if not (
        windows["handoff_activity_gate"]
        < edges["primary_to_is_next_phase"]
        < edges["primary_to_phase_transition"]
    ):
        raise FinalEndSettlementError("activity/handoff order differs")
    return _expected_shape()


def validate_final_end_settlement_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping):
        raise FinalEndSettlementError("settlement map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise FinalEndSettlementError("settlement map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "final_end_state_trigger_proven": True,
        "mission_effect_handoff_gate_proven": True,
        "post_travel_campaign_victory_proven": False,
        "simulator_change_required": False,
    }


def validate_final_end_settlement_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject source, byte, address, or prose drift."""
    expected = build_final_end_settlement_map(executable, content_root)
    if dict(value) != expected:
        raise FinalEndSettlementError(
            "settlement map differs from exact-build analysis"
        )
    result = validate_final_end_settlement_map_binding(value)
    result["status"] = "verified"
    return result


def encode_final_end_settlement_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
