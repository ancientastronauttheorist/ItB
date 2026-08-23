"""Reproduce the exact-build Final mission phase-scheduler boundary map.

This module joins two evidence classes without claiming more than either one
can prove alone:

* exact shipped Lua source defines ``IsNextPhase`` and ``CreateNextPhase`` and
  names ``Mission_Final_Cave`` as the surface mission's next phase; and
* focused x86 review pins the native relative order around ``IsEndBlocked``,
  ``MissionEnd``, ``IsNextPhase``, and ``CreateNextPhase``.

The native state change that lets both Final stages leave their always-true
``IsEndBlocked`` callback, queued-effect settlement, and cave startup RNG stay
explicitly unresolved.  Every published source hash, string reference,
function region, control window, and direct edge is rechecked here.
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
ANALYSIS_KIND = "final_phase_scheduler_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)


class FinalPhaseSchedulerError(RuntimeError):
    """Raised when the reviewed Final scheduler map cannot be reproduced."""


LUA_SOURCE_SPECS = (
    {
        "path": "scripts/game.lua",
        "size": 9_747,
        "sha256": (
            "8fc587a6d341f43cf521ae2c95e91e5739355cb929581a18f9c374fba2c88db7"
        ),
        "symbols": [
            "GameObject:GetMissionId",
            "GameObject:GetMission",
            "GameObject:CreateNextPhase",
        ],
    },
    {
        "path": "scripts/missions/missions.lua",
        "size": 29_573,
        "sha256": (
            "505c02a8668ba2e39d868f95051ede81c6cc1611f1e409219b6caa4fbe1d0257"
        ),
        "symbols": [
            "Mission.NextPhase",
            "Mission:IsEndBlocked",
            "Mission:IsNextPhase",
            "Mission:MissionEnd",
        ],
    },
    {
        "path": "scripts/missions/final/mission_final.lua",
        "size": 3_318,
        "sha256": (
            "f92875ba570871b7b3184adb168105c8f29150398b8b14e87a863f67d6c61e29"
        ),
        "symbols": [
            "Mission_Final",
            "Mission_Final.NextPhase",
            "Mission_Final:MissionEnd",
            "Mission_Final:IsEndBlocked",
        ],
    },
    {
        "path": "scripts/missions/final/mission_final_two.lua",
        "size": 4_887,
        "sha256": (
            "c8a8e40f512939c1f4fd0e0df416e5cbaec00c639e2985ad776e13c38735b17c"
        ),
        "symbols": [
            "Mission_Final_Cave",
            "Mission_Final_Cave:StartMission",
            "Mission_Final_Cave:MissionEnd",
            "Mission_Final_Cave:IsEndBlocked",
        ],
    },
)


REGION_SPECS = (
    {
        "id": "is_next_phase",
        "start": 0x00182F30,
        "end": 0x00182FFA,
        "sha256": (
            "e8f4a1233b90831e3a17c0496f71bfa3de8ead5bfbb170236763bb3d21d2d432"
        ),
    },
    {
        "id": "end_readiness",
        "start": 0x00185BC0,
        "end": 0x00185D92,
        "sha256": (
            "a3fcc9c4e1f4561c46f1b371f515090001578c02bebc718029dc5939f17fae16"
        ),
    },
    {
        "id": "phase_transition",
        "start": 0x001891D0,
        "end": 0x0018964D,
        "sha256": (
            "3a5b364d9af48610bb07f8e44d5cb9ddb4051f4cb4a5fa0ad0db8eb51522073f"
        ),
    },
    {
        "id": "primary_orchestrator",
        "start": 0x0018AE90,
        "end": 0x0018B36F,
        "sha256": (
            "8a5e7744c920a70f30f8056271d452335be6d601625f8b8d935d5457b77ebf82"
        ),
    },
    {
        "id": "mission_end_dispatch",
        "start": 0x0018B780,
        "end": 0x0018B9FF,
        "sha256": (
            "00e1f495aa53d2a439c4eeb6e41e1d5ac5b304e0c050e4343bd0433f9ff74ee9"
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
        "id": "is_next_phase",
        "region_id": "is_next_phase",
        "reference_rva": 0x00182F83,
        "instruction_hex": "681cf28200",
        "string_rva": 0x0042F21C,
        "text": "IsNextPhase",
        "role": "next-phase predicate callback",
    },
    {
        "id": "get_turn_limit",
        "region_id": "end_readiness",
        "reference_rva": 0x00185C24,
        "instruction_hex": "6858f38200",
        "string_rva": 0x0042F358,
        "text": "GetTurnLimit",
        "role": "normal mission-end readiness input",
    },
    {
        "id": "is_end_blocked",
        "region_id": "end_readiness",
        "reference_rva": 0x00185CC1,
        "instruction_hex": "6808f58200",
        "string_rva": 0x0042F508,
        "text": "IsEndBlocked",
        "role": "normal mission-end readiness veto",
    },
    {
        "id": "is_environment_effect",
        "region_id": "end_readiness",
        "reference_rva": 0x00185D2A,
        "instruction_hex": "683cf58200",
        "string_rva": 0x0042F53C,
        "text": "IsEnvironmentEffect",
        "role": "normal mission-end environment guard",
    },
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
        "id": "game_object",
        "region_id": "phase_transition",
        "reference_rva": 0x001894CF,
        "instruction_hex": "6824f88200",
        "string_rva": 0x0042F824,
        "text": "GAME",
        "role": "phase-construction receiver",
    },
    {
        "id": "mission_end",
        "region_id": "mission_end_dispatch",
        "reference_rva": 0x0018B984,
        "instruction_hex": "68e8f98200",
        "string_rva": 0x0042F9E8,
        "text": "MissionEnd",
        "role": "mission-end callback",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "is_next_phase_callback_result",
        "region_id": "is_next_phase",
        "start_rva": 0x00182F7B,
        "instruction_hex": (
            "83ec188bcc8965f0681cf28200e8834ee8ff83ec18c745fc000000008bcc"
            "81c6d40f0000c741140f000000c74110000000008379141072048b01eb02"
            "8bc16aff6a0056c60000e80a51e8ffc745fcffffffffe84e66ecff84c07412"
            "b001"
        ),
        "meaning": (
            "Invoke IsNextPhase on the current mission and return true only "
            "when the extracted Lua boolean is true."
        ),
    },
    {
        "id": "end_blocked_false_gate",
        "region_id": "end_readiness",
        "start_rva": 0x00185CB9,
        "instruction_hex": (
            "83ec188bcc8965ec6808f58200e84521e8ff83ec18c745fc010000008bcc"
            "c741140f000000c74110000000008379141072048b01eb028bc16aff6a00"
            "57c60000e8d223e8ffc745fcffffffffe81639ecff84c07571"
        ),
        "meaning": (
            "Invoke IsEndBlocked and branch to the end-readiness false return "
            "when the extracted Lua boolean is true."
        ),
    },
    {
        "id": "end_readiness_dispatch",
        "region_id": "mission_end_dispatch",
        "start_rva": 0x0018B816,
        "instruction_hex": (
            "83f802752083bee40f000000741d8bcee895a3ffff84c07412"
            "c7860019000001000000eb06898600190000"
        ),
        "meaning": (
            "On the ordinary pending-end state, call end_readiness and promote "
            "the state only when it returns true; otherwise preserve the "
            "incoming state."
        ),
    },
    {
        "id": "mission_end_named_dispatch",
        "region_id": "mission_end_dispatch",
        "start_rva": 0x0018B8FA,
        "instruction_hex": (
            "8bcee84fabffff84c00f85a9000000e82276ffff84c075248b8690450000"
            "b90100000083f80375048bc8eb0b83f801ba020000000f44cae8fa0bf5ff"
            "6a028bcee84177ffff84c075196a038bcee83477ffff84c0750c83ec188bcc"
            "68c4f98200eb1383be9045000003751783ec188bcc68f4f98200e89cc4e7ff"
            "e8c7fbf4ff83c41883ec188bcc89650868e8f98200e882c4e7ff83ec18"
            "c745fc000000008d86d40f00008bcc50e86af2ebffc745fcffffffff"
            "e84edf0000"
        ),
        "meaning": (
            "On the reviewed completion branch, evaluate IsNextPhase for "
            "presentation selection before constructing and executing the "
            "MissionEnd callback."
        ),
    },
    {
        "id": "primary_mission_end_dispatch",
        "region_id": "primary_orchestrator",
        "start_rva": 0x0018B06C,
        "instruction_hex": "83be041900000274096a008bcee802070000",
        "meaning": (
            "Call mission_end_dispatch when the sampled end state is no "
            "longer the waiting value."
        ),
    },
    {
        "id": "primary_next_phase_handoff",
        "region_id": "primary_orchestrator",
        "start_rva": 0x0018B11A,
        "instruction_hex": (
            "8b068bce8b4040ffd084c0755a8b86c80f000083f80475046a03eb44"
            "83f80575468a86a81a000084c0753c3886c845000075348d8e54200000"
            "e8d873060084c075258bcee8cd7dffff84c074098bcee862e0ffffeb11"
            "8b4e04e8c831feff6a068bcee83ff1ffff"
        ),
        "meaning": (
            "On the completed-mission path, evaluate IsNextPhase and call "
            "phase_transition only for a true result; the false branch takes "
            "the ordinary mission-exit transition."
        ),
    },
    {
        "id": "phase_create_next_dispatch",
        "region_id": "phase_transition",
        "start_rva": 0x00189475,
        "instruction_hex": (
            "83ec18c645fc058bcc896598c741140f000000c741100000000083791410"
            "72048b01eb028bc16a0f68dcf78200c60000e826ebe7ff83ec18c645fc06"
            "8bccc741140f000000c74110000000008379141072048b01eb028bc16a04"
            "6824f88200c60000e8f4eae7ffc645fc01e83bdb0000"
        ),
        "meaning": (
            "Construct CreateNextPhase and GAME arguments and pass them to "
            "the reviewed phase named invoker."
        ),
    },
)


DIRECT_EDGE_SPECS = (
    {
        "id": "mission_dispatch_to_end_readiness",
        "source_region": "mission_end_dispatch",
        "from_rva": 0x0018B826,
        "instruction_hex": "e895a3ffff",
        "target_region": "end_readiness",
        "target_rva": 0x00185BC0,
    },
    {
        "id": "mission_dispatch_to_is_next_phase",
        "source_region": "mission_end_dispatch",
        "from_rva": 0x0018B909,
        "instruction_hex": "e82276ffff",
        "target_region": "is_next_phase",
        "target_rva": 0x00182F30,
    },
    {
        "id": "mission_dispatch_to_named_invoker",
        "source_region": "mission_end_dispatch",
        "from_rva": 0x0018B9AD,
        "instruction_hex": "e84edf0000",
        "target_region": "mission_named_invoker",
        "target_rva": 0x00199900,
    },
    {
        "id": "primary_to_mission_dispatch",
        "source_region": "primary_orchestrator",
        "from_rva": 0x0018B079,
        "instruction_hex": "e802070000",
        "target_region": "mission_end_dispatch",
        "target_rva": 0x0018B780,
    },
    {
        "id": "primary_to_is_next_phase",
        "source_region": "primary_orchestrator",
        "from_rva": 0x0018B15E,
        "instruction_hex": "e8cd7dffff",
        "target_region": "is_next_phase",
        "target_rva": 0x00182F30,
    },
    {
        "id": "primary_to_phase_transition",
        "source_region": "primary_orchestrator",
        "from_rva": 0x0018B169,
        "instruction_hex": "e862e0ffff",
        "target_region": "phase_transition",
        "target_rva": 0x001891D0,
    },
    {
        "id": "phase_transition_to_named_invoker",
        "source_region": "phase_transition",
        "from_rva": 0x001894E0,
        "instruction_hex": "e83bdb0000",
        "target_region": "phase_named_invoker",
        "target_rva": 0x00197020,
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


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise FinalPhaseSchedulerError(
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
        raise FinalPhaseSchedulerError(
            f"RVA 0x{rva:08x} is not in executable file-backed data"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise FinalPhaseSchedulerError(
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
            "evidence_class": "fact",
        }
        for spec in LUA_SOURCE_SPECS
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


def _method() -> dict[str, Any]:
    return {
        "boundary_review": (
            "Focused Capstone 5.0.7 disassembly and a Ghidra 12.1.3 "
            "function/reference/call-graph cross-check joined the named Lua "
            "callbacks to the native mission-completion and phase-transition "
            "paths."
        ),
        "source_review": (
            "Only normalized semantic conclusions and exact source hashes are "
            "published; no proprietary source or decompiler output is stored."
        ),
        "limitations": [
            "Every native address and conclusion applies only to the pinned Windows executable.",
            "Semantic role names are bounded analyst inferences over exact strings, bytes, branches, and direct calls.",
            "Static order does not prove runtime branch frequency or identify the external event that advances an always-blocked Final mission.",
            "Queued SkillEffect settlement, presentation timing, cave startup callback order, and cave startup RNG remain outside this map.",
            "macOS and other executable builds require independent maps.",
        ],
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "normal_end_readiness_veto",
            "evidence_class": "inference",
            "claim": (
                "The reviewed normal readiness path obtains GetTurnLimit, "
                "invokes IsEndBlocked, and returns false when the extracted "
                "IsEndBlocked result is true."
            ),
            "supports": [
                "end_readiness",
                "get_turn_limit",
                "is_end_blocked",
                "end_blocked_false_gate",
            ],
            "limitations": [
                "The native state machine also accepts externally advanced end states; this finding does not identify that trigger."
            ],
        },
        {
            "id": "mission_end_callback_order",
            "evidence_class": "inference",
            "claim": (
                "On the reviewed completion branch, mission_end_dispatch "
                "evaluates IsNextPhase for presentation selection before it "
                "constructs and executes the MissionEnd callback."
            ),
            "supports": [
                "mission_end_dispatch",
                "is_next_phase",
                "mission_end",
                "mission_end_named_dispatch",
                "mission_named_invoker",
            ],
            "limitations": [
                "A preceding native guard can skip the callback branch, and queued effects may settle later."
            ],
        },
        {
            "id": "native_phase_handoff_order",
            "evidence_class": "inference",
            "claim": (
                "The primary orchestrator calls mission_end_dispatch first, "
                "then on its completed-mission path evaluates IsNextPhase and "
                "calls phase_transition only when that predicate is true."
            ),
            "supports": [
                "primary_orchestrator",
                "primary_mission_end_dispatch",
                "primary_next_phase_handoff",
                "primary_to_mission_dispatch",
                "primary_to_is_next_phase",
                "primary_to_phase_transition",
            ],
            "limitations": [
                "This is relative control-flow order, not a timestamped runtime trace."
            ],
        },
        {
            "id": "create_next_phase_dispatch",
            "evidence_class": "inference",
            "claim": (
                "phase_transition constructs CreateNextPhase and GAME "
                "arguments and passes them to the reviewed phase named "
                "invoker."
            ),
            "supports": [
                "phase_transition",
                "create_next_phase",
                "game_object",
                "phase_create_next_dispatch",
                "phase_named_invoker",
            ],
            "limitations": [
                "The exact post-call board/map initialization sequence remains outside the named dispatch boundary."
            ],
        },
        {
            "id": "final_surface_target",
            "evidence_class": "fact",
            "claim": (
                "The exact Lua sources define IsNextPhase as a nonempty "
                "NextPhase test, define GameObject:CreateNextPhase to replace "
                "the current mission slot with CreateMission(next_phase), and "
                "set Mission_Final.NextPhase to Mission_Final_Cave."
            ),
            "supports": [
                "scripts/game.lua",
                "scripts/missions/missions.lua",
                "scripts/missions/final/mission_final.lua",
            ],
            "limitations": [
                "Source semantics do not by themselves prove the native trigger or effect-settlement timing."
            ],
        },
        {
            "id": "solver_boundary",
            "evidence_class": "inference",
            "claim": (
                "No current-turn combat simulation change follows from this "
                "map. The safe boundary remains to detect the live stage "
                "change, refresh bridge state, and never fabricate cave setup "
                "RNG or queued MissionEnd settlement."
            ),
            "supports": [
                "native_phase_handoff_order",
                "create_next_phase_dispatch",
                "final_surface_target",
            ],
            "limitations": [
                "A future exact cave-start scheduler map or controlled trace may justify additional modeling."
            ],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "final_end_state_trigger",
            "question": (
                "Which native event advances Mission_Final and "
                "Mission_Final_Cave despite their always-true IsEndBlocked?"
            ),
            "static_status": (
                "The ordinary readiness veto and later relative handoff order "
                "are mapped, but the external state transition is not."
            ),
            "next_evidence": (
                "Map writes to the reviewed end-state field or capture a "
                "build-keyed Final countdown transition."
            ),
        },
        {
            "id": "mission_end_effect_settlement",
            "question": (
                "When do Mission_Final's queued fall, bounce, and Board:Slide "
                "effects settle relative to CreateNextPhase?"
            ),
            "static_status": (
                "Callback dispatch order is mapped; the SkillEffect scheduler "
                "and presentation queue are not."
            ),
            "next_evidence": (
                "Trace the effect queue and stage identity across one surface "
                "handoff without changing gameplay semantics."
            ),
        },
        {
            "id": "cave_start_order",
            "question": (
                "What is the exact native order for CreateMission, map swap, "
                "Mission_Final_Cave:StartMission, spawns, and opening RNG?"
            ),
            "static_status": (
                "The named CreateNextPhase boundary is mapped, but subsequent "
                "native initialization is not classified."
            ),
            "next_evidence": (
                "Continue static review from phase_named_invoker and join it "
                "to StartMission and map-construction anchors."
            ),
        },
        {
            "id": "cave_countdown_outcome",
            "question": (
                "Which native transition ends Mission_Final_Cave, and how are "
                "bomb survival, objectives, and victory settled?"
            ),
            "static_status": (
                "MissionEnd is named, but the final countdown trigger and "
                "outcome settlement remain untraced."
            ),
            "next_evidence": (
                "Map the cave end-state writer or retain a controlled exact-build final-turn capture."
            ),
        },
    ]


def _summary() -> dict[str, Any]:
    return {
        "lua_source_count": len(LUA_SOURCE_SPECS),
        "region_count": len(REGION_SPECS),
        "string_anchor_count": len(STRING_ANCHOR_SPECS),
        "control_window_count": len(CONTROL_WINDOW_SPECS),
        "direct_edge_count": len(DIRECT_EDGE_SPECS),
        "finding_count": len(_findings()),
        "unresolved_count": len(_unresolved()),
        "relative_handoff_order_proven": True,
        "final_surface_target_proven": True,
        "final_end_state_trigger_proven": False,
        "mission_effect_settlement_proven": False,
        "simulator_change_required": False,
        "remaining_runtime_proof": [
            "Final end-state trigger",
            "MissionEnd queued-effect settlement",
            "cave startup callback and RNG order",
            "cave countdown outcome settlement",
            "non-Windows build equivalence",
        ],
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
            "lua_files": _expected_sources(),
        },
        "method": _method(),
        "regions": _expected_regions(),
        "string_anchors": _expected_anchors(),
        "control_windows": _expected_windows(),
        "direct_call_edges": _expected_edges(),
        "findings": _findings(),
        "unresolved": _unresolved(),
        "summary": _summary(),
    }


def _verify_lua_sources(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise FinalPhaseSchedulerError("content root is not a directory")
    for spec in LUA_SOURCE_SPECS:
        source = root / Path(spec["path"])
        try:
            resolved = source.resolve(strict=True)
        except OSError as exc:
            raise FinalPhaseSchedulerError(
                f"missing Lua source {spec['path']}"
            ) from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise FinalPhaseSchedulerError(
                f"Lua source escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise FinalPhaseSchedulerError(
                f"Lua source is not a regular non-symlink file: {spec['path']}"
            )
        data = resolved.read_bytes()
        if (
            len(data) != spec["size"]
            or hashlib.sha256(data).hexdigest() != spec["sha256"]
        ):
            raise FinalPhaseSchedulerError(
                f"Lua source identity differs: {spec['path']}"
            )


def build_final_phase_scheduler_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build Final scheduler boundary map."""
    data, image, digest = _load_executable(executable)
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise FinalPhaseSchedulerError("executable identity differs")
    _verify_lua_sources(content_root)

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
            raise FinalPhaseSchedulerError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise FinalPhaseSchedulerError(
                f"region {spec['id']} bytes differ"
            )
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise FinalPhaseSchedulerError(str(exc)) from exc

    for spec in STRING_ANCHOR_SPECS:
        text = spec["text"].encode("ascii") + b"\0"
        offset = image.rva_span_to_file_offset(spec["string_rva"], len(text))
        if offset is None or data[offset : offset + len(text)] != text:
            raise FinalPhaseSchedulerError(
                f"string anchor {spec['id']} differs"
            )
        encoded = bytes.fromhex(spec["instruction_hex"])
        actual = _bytes_at(
            image, data, spec["reference_rva"], len(encoded)
        )
        if actual != encoded:
            raise FinalPhaseSchedulerError(
                f"string reference {spec['id']} differs"
            )
        instruction = decoded[spec["region_id"]].get(spec["reference_rva"])
        if instruction is None or instruction[1] != encoded:
            raise FinalPhaseSchedulerError(
                f"string reference {spec['id']} is not an instruction"
            )
        expected_va = image.image_base + spec["string_rva"]
        if struct.pack("<I", expected_va) not in encoded:
            raise FinalPhaseSchedulerError(
                f"string reference {spec['id']} target differs"
            )

    region_specs = {spec["id"]: spec for spec in REGION_SPECS}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["instruction_hex"])
        start = spec["start_rva"]
        actual = _bytes_at(image, data, start, len(encoded))
        if actual != encoded:
            raise FinalPhaseSchedulerError(
                f"control window {spec['id']} differs"
            )
        region = region_specs[spec["region_id"]]
        if not (region["start"] <= start < start + len(encoded) <= region["end"]):
            raise FinalPhaseSchedulerError(
                f"control window {spec['id']} escapes its region"
            )
        instructions = decoded[spec["region_id"]]
        if start not in instructions:
            raise FinalPhaseSchedulerError(
                f"control window {spec['id']} does not start at an instruction"
            )
        cursor = start
        while cursor < start + len(encoded):
            instruction = instructions.get(cursor)
            if instruction is None:
                raise FinalPhaseSchedulerError(
                    f"control window {spec['id']} crosses undecoded bytes"
                )
            cursor += len(instruction[1])
        if cursor != start + len(encoded):
            raise FinalPhaseSchedulerError(
                f"control window {spec['id']} ends inside an instruction"
            )

    for spec in DIRECT_EDGE_SPECS:
        instruction = decoded[spec["source_region"]].get(spec["from_rva"])
        expected = bytes.fromhex(spec["instruction_hex"])
        if instruction is None or instruction[1] != expected:
            raise FinalPhaseSchedulerError(
                f"direct edge {spec['id']} bytes differ"
            )
        if _direct_target(spec["from_rva"], expected) != spec["target_rva"]:
            raise FinalPhaseSchedulerError(
                f"direct edge {spec['id']} target differs"
            )
        if spec["target_rva"] not in decoded[spec["target_region"]]:
            raise FinalPhaseSchedulerError(
                f"direct edge {spec['id']} target is not an instruction"
            )

    primary_edges = {
        spec["id"]: spec["from_rva"] for spec in DIRECT_EDGE_SPECS
    }
    if not (
        primary_edges["primary_to_mission_dispatch"]
        < primary_edges["primary_to_is_next_phase"]
        < primary_edges["primary_to_phase_transition"]
    ):
        raise FinalPhaseSchedulerError("primary handoff edge order differs")
    return _expected_shape()


def validate_final_phase_scheduler_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping):
        raise FinalPhaseSchedulerError("scheduler map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise FinalPhaseSchedulerError("scheduler map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "relative_handoff_order_proven": True,
        "final_surface_target_proven": True,
        "final_end_state_trigger_proven": False,
        "simulator_change_required": False,
    }


def validate_final_phase_scheduler_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject source, byte, address, or prose drift."""
    expected = build_final_phase_scheduler_map(executable, content_root)
    if dict(value) != expected:
        raise FinalPhaseSchedulerError(
            "scheduler map differs from exact-build analysis"
        )
    result = validate_final_phase_scheduler_map_binding(value)
    result["status"] = "verified"
    return result


def encode_final_phase_scheduler_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
