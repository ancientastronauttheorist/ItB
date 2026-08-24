"""Reproduce the exact-build native Mission_Piston scheduler boundary.

This map closes the stock Trash Compactor ordering/cancellation seam left by
the corpse-classification work.  It binds the Lua ``Board:GetPawns`` method to
the native Board pawn vector, follows that same vector through neutral planning
and first-queued-pawn execution, and pins the queue clears that cancel a dead
Piston before it can be selected.  The claim is deliberately scoped to the
shipped ``Mission_Piston`` on exact Windows build 13725832.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.corpse_classification_boundary import (
    CorpseClassificationBoundaryError,
    validate_corpse_classification_boundary_map,
)
from src.observatory.event_frame_visibility import (
    EventFrameVisibilityError,
    validate_event_frame_visibility_map,
)
from src.observatory.pe_boundary_map import (
    SUPPORTED_CAPSTONE_VERSION,
    _decode_x86_regions,
    _load_executable,
    _region_bytes,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "native_piston_scheduler_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)


class PistonSchedulerBoundaryError(RuntimeError):
    """Raised when the exact Piston scheduler map cannot reproduce."""


DEPENDENCY_SPECS = (
    {
        "id": "corpse_classification_boundary",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_"
            "corpse_classification_boundary.json"
        ),
        "file_sha256": (
            "7cefd651d3f19fc44179bb83044d4bfd02ebc360d2c198d4487a4cc172b7c5bf"
        ),
        "canonical_sha256": (
            "401eefc2bd6b59f70861cc1c7bc35d4a67597d2d621cd18655f8dcac285abe6e"
        ),
        "role": (
            "Pins Piston Corpse=true classification, persistent corpse occupancy, "
            "the common Pawn update/death boundary, and exact shipped-source identity."
        ),
    },
    {
        "id": "event_frame_visibility",
        "path": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_event_frame_visibility.json"
        ),
        "file_sha256": (
            "1b4c3e6584b7bd39cbd563ebddb47dabe72a4d987f6852c8e1ce66a969da003d"
        ),
        "canonical_sha256": (
            "5a4d00bb24fd58ad017f9e0d262de0f402676fe0a3434332247c83e23cb8e65c"
        ),
        "role": (
            "Pins BoardPlayer construction, its primary update, and the exact "
            "Board/effect-update-before-Mission:BaseUpdate outer chronology."
        ),
    },
)


SOURCE_SPECS = (
    {
        "path": "scripts/missions/acid/mission_piston.lua",
        "size": 2_420,
        "sha256": "1f426bad3b4149f0088831680264f716a3f9cc6acebf828306946c55990d51ad",
        "reviewed_lines": [2, 8, 48, 52, 53, 54, 55, 56, 57, 68, 73, 77, 83, 84],
        "symbols": [
            "Mission_Piston",
            "Mission_Piston:StartMission",
            "Pawn_Piston_U",
            "Piston_U_Atk:GetTargetScore",
            "Piston_U_Atk:GetSkillEffect",
        ],
    },
    {
        "path": "scripts/missions/missions.lua",
        "size": 29_573,
        "sha256": "505c02a8668ba2e39d868f95051ede81c6cc1611f1e409219b6caa4fbe1d0257",
        "reviewed_lines": [68, 69, 601, 856, 858, 1018, 1020],
        "symbols": ["Mission", "Mission:BaseUpdate", "Mission_Auto"],
    },
    {
        "path": "scripts/environments.lua",
        "size": 8_924,
        "sha256": "5f8a7d74f537abb33bc88c1f9669f3f6fabdd5c8c51aad3486d2e965e4fb80ec",
        "reviewed_lines": [3, 7, 8, 9, 25],
        "symbols": ["Environment:IsEffect", "Environment:ApplyEffect", "Env_Null"],
    },
)


REGION_SPECS = (
    ("pawn_vector_copy", 0x000F5E70, 0x000F5E90, "19d6a934402e070f4b8915880bb04cbbf3706faf894a84fcff15d9ade8d6d449", "Ghidra 12.1.3 Board pawn-vector copy wrapper."),
    ("ai_list_setup", 0x000F5FF0, 0x000F6181, "5f27875a6bab87f4b6e5bacfbfd6a8e56809b1ac6d1bd268fd745293f39b89b0", "Ghidra 12.1.3 enemy/neutral planning-list setup body."),
    ("getpawns", 0x001663A0, 0x00166474, "28a992ac057274edfd5c298743871fa6db4c9fa23d7f7acbfac7bfe87cffbc32", "Ghidra 12.1.3 native Board:GetPawns target body."),
    ("board_activity_boolean", 0x001698E0, 0x001698EF, "0f857820b8f5fea9fcf8165260e7311c458f592b1b952c69bf9da7711359b11c", "Ghidra 12.1.3 Board activity Boolean wrapper."),
    ("board_activity_reason", 0x001698F0, 0x00169B22, "dc9eced8706681fbaa20781c972724170efe9653c37d277e6b8eaaacc5b61a13", "Ghidra 12.1.3 comprehensive Board activity-reason body."),
    ("board_master_update", 0x0016A8D0, 0x0016BF62, "6d32a302492920ae4353af4505e792776a18c4f9d8c26bd6cf1f9861a6f9129d", "Ghidra 12.1.3 Board master update body."),
    ("endturn_selector", 0x00170B30, 0x00170B84, "6d6de375908dc4ad2884b055e222854592d1fbe3dbaecefc7db427fe98f08f7b", "Ghidra 12.1.3 first-queued-pawn selector body."),
    ("current_pawn", 0x00171D70, 0x00171DAE, "7d0034868f9001328944556ee7e929e603d48c8ba3dd633482b6e295120801b8", "Ghidra 12.1.3 first-active-pawn selector body."),
    ("getpawns_filter", 0x00173DF0, 0x00173F2E, "08b128f01b39c846cc71c45f702a8e8e7b7b7b4460acc3970cfba8fc1d754a5b", "Ghidra 12.1.3 Board pawn-vector filter body."),
    ("endturn_executor", 0x00189810, 0x00189A64, "e4b39f6ecfb001e1ebc38df37334546806a95b8c1474b0eb50551947e775e860", "Ghidra 12.1.3 environment/queued-pawn executor body."),
    ("phase_update", 0x00189B20, 0x0018A2B4, "60e572e11e81c6f4a6f111785eaeb171be78655905af581c1884f29d550c2bbd", "Ghidra 12.1.3 battle phase-update body."),
    ("phase_driver", 0x0018A2C0, 0x0018A955, "903ca7d14ba5317753901f70ec24acfb31ea44e947d3ebce3246651897bc2b90", "Ghidra 12.1.3 battle phase-transition driver body."),
    ("primary_orchestrator", 0x0018AE90, 0x0018B36F, "8a5e7744c920a70f30f8056271d452335be6d601625f8b8d935d5457b77ebf82", "Ghidra 12.1.3 BoardPlayer primary-update body."),
    ("boardplayer_busy_thunk", 0x001936E0, 0x001936ED, "28b7c171070ae6f815fb1f5bc3f59431d581243a17720b2b55a9c7a158ee521b", "Ghidra 12.1.3 BoardPlayer-to-Board activity thunk."),
    ("queued_predicate", 0x00228E20, 0x00228E60, "4836b9b1a2f01261a5138ddf5992200a4a21ff96a1948fafe19d48cf7cc638dc", "Ghidra 12.1.3 Pawn queued-action predicate body."),
    ("queue_reset", 0x00228E60, 0x00228E76, "53028cd6ca9c06fb6b99d9c790ec70e5732285a67a2fe5d2c9c208a7c81fb24b", "Ghidra 12.1.3 direct queued-action reset body."),
    ("shared_pawn_update", 0x00233EE0, 0x00234C70, "0f061f2c6ad29a87a1f86eb1b9a1d2a0aeb6c995c67c1a3073be67aa50accd0f", "Ghidra 12.1.3 shared Pawn update/death body."),
    ("pawn_kill", 0x0023D2E0, 0x0023D34B, "0a5d113dc0441f670a948a57ee4e3b07593815596b049075d3303ec3a7fd2903", "Ghidra 12.1.3 explicit Pawn:Kill body."),
    ("pawn_is_active", 0x0023E8B0, 0x0023E939, "449310a80188de96a31ca52afdd3c1db0784bfd136322352f467c2d770ff41b9", "Ghidra 12.1.3 Pawn planning-active predicate body."),
    ("getpawns_registration", 0x0027AAC2, 0x0027AAE3, "df0430d44a1122f78a01bdec2e73ff8451c010a584f3078d56dc61cd06e147d3", "Instruction-aligned Board:GetPawns registration window."),
    ("getpawns_binding_helper", 0x00289370, 0x00289410, "d5894c4bdf5264ef9a20707dcefe72bed7587ebd8ea7787d00d4bb6f1c7a687c", "Ghidra 12.1.3 GetPawns Luabind helper body."),
)


CONTROL_WINDOW_SPECS = (
    ("ai_board_vector_copy", "ai_list_setup", 0x000F601D, "8b45088b0b8983840000008d45e450e83ffeffff", "Load the Board pointer, then copy its +0x3c pawn vector without sorting."),
    ("ai_team_or_neutral_filter", "ai_list_setup", 0x000F6070, "8b3783beb00000000674328a867c09000084c07528", "Retain team 6 or Pawn+0x97c Neutral entries in encounter order."),
    ("getpawns_registration", "getpawns_registration", 0x0027AAC2, "ff75f0c745e8a0635600ff75f0c745ec00000000518d4de851518bc8e88de80000", "Register native target VA 0x005663a0 through the GetPawns helper."),
    ("current_pawn_order", "current_pawn", 0x00171D70, "56578bf933f68b47402b473cc1f80285c0741d8b473c8b0cb0e822cb0c0084c075138b4740462b473cc1f8023bf072e35f33c05ec38b473c5f8b04b05ec3", "Return the first planning-active Pawn from Board+[0x3c,0x40)."),
    ("queued_predicate", "queued_predicate", 0x00228E20, "558bec83e4f851568bf18b4e3c85c9750732c05e8be55dc38b01ff7624ff76208b4014ffd084c07410837e28ff740ab8010000005e8be55dc333c05e8be55dc3", "Require a skill manager, valid queued target coordinates, and nonnegative queued action index."),
    ("selector_order", "endturn_selector", 0x00170B30, "53568bf133db5733ff8b46402b463cc1f80285c0743866660f1f8400000000008b4e3c8d04bd000000008b0c01e8be820b0084c0740a85db75068b463c8b1cb88b4e40472b4e3cc1f9023bf972d25f5e8bc35bc3", "Scan Board+[0x3c,0x40) first-to-last and retain the first queued Pawn."),
    ("executor_busy_then_select", "endturn_executor", 0x0018999C, "8b068bce8b4040ffd084c00f85a7000000f30f108ecc0f00000f57d20f2fca761cf30f1005d0c88b00f30f5905e8ca8300f30f5cc8f30f118ecc0f00000f2f96cc0f000072728b4e04e84671feff8986d00f000085c07460", "Do not choose the next queued Pawn while Board activity is nonzero; otherwise call the first-queued selector."),
    ("explicit_kill_queue_clear", "pawn_kill", 0x0023D31A, "c6862109000001c74628ffffffffc74620ffffffffc74624ffffffff", "Set new-death byte +0x921 and clear queued index/coordinates."),
    ("shared_update_queue_clear", "shared_pawn_update", 0x00234C3F, "c74328ffffffffc74320ffffffffc74324ffffffff", "Every completed shared Pawn update clears queued index/coordinates before return."),
    ("standalone_queue_clear", "queue_reset", 0x00228E60, "c74128ffffffffc74120ffffffffc74124ffffffffc3", "The direct reset helper clears the same three queued fields."),
    ("phase_plan_dispatch", "phase_driver", 0x0018A479, "ffb7540100008d8fc0000000e866bbf6ff", "Enter the AI planning-list setup during the planning phase transition."),
    ("phase_execute_dispatch", "phase_driver", 0x0018A820, "8bcfe8e9efffff", "Enter the queued-pawn executor during the enemy-action phase transition."),
    ("primary_board_update", "primary_orchestrator", 0x0018B0DE, "8b4e04e8eaf7fdff", "Run the Board master update before the later battle phase update."),
    ("primary_phase_update", "primary_orchestrator", 0x0018B18E, "8bcee88be9ffff", "Run the battle phase update after Board/pawn cleanup."),
    ("activity_boolean", "board_activity_boolean", 0x001698E0, "83c1f4e808000000f7d81bc0f7d8c3", "Convert the comprehensive Board activity reason into a Boolean gate."),
)


DIRECT_EDGE_SPECS = (
    ("ai_setup_to_vector_copy", "ai_list_setup", 0x000F602C, "e83ffeffff", "pawn_vector_copy", 0x000F5E70, "Copy the Board pawn vector before filtering planning actors."),
    ("getpawns_to_filter", "getpawns", 0x001663FA, "e8f1d90000", "getpawns_filter", 0x00173DF0, "Filter the Board pawn vector while preserving encounter order."),
    ("board_update_to_shared_pawn_update", "board_master_update", 0x0016B444, "e8978a0c00", "shared_pawn_update", 0x00233EE0, "Update each Board pawn before the effect queue and phase dispatcher continue."),
    ("current_pawn_to_active", "current_pawn", 0x00171D89, "e822cb0c00", "pawn_is_active", 0x0023E8B0, "Test each planning candidate for live active state."),
    ("selector_to_queued_predicate", "endturn_selector", 0x00170B5D, "e8be820b00", "queued_predicate", 0x00228E20, "Test each Board-vector Pawn for a complete queued action."),
    ("executor_to_selector", "endturn_executor", 0x001899E5, "e84671feff", "endturn_selector", 0x00170B30, "Choose the next queued Pawn only after Board activity clears."),
    ("phase_update_to_executor", "phase_update", 0x0018A0A7, "e864f7ffff", "endturn_executor", 0x00189810, "Advance the active enemy/environment executor from phase update."),
    ("phase_driver_to_ai_setup", "phase_driver", 0x0018A485, "e866bbf6ff", "ai_list_setup", 0x000F5FF0, "Build queued actions from the Board vector at planning transition."),
    ("phase_driver_to_executor", "phase_driver", 0x0018A822, "e8e9efffff", "endturn_executor", 0x00189810, "Start enemy action execution from the phase transition."),
    ("primary_to_board_update", "primary_orchestrator", 0x0018B0E1, "e8eaf7fdff", "board_master_update", 0x0016A8D0, "Run Board and per-Pawn updates before phase selection."),
    ("primary_to_phase_update", "primary_orchestrator", 0x0018B190, "e88be9ffff", "phase_update", 0x00189B20, "Run phase scheduling after the Board update."),
    ("activity_boolean_to_reason", "board_activity_boolean", 0x001698E3, "e808000000", "board_activity_reason", 0x001698F0, "Query the comprehensive Board activity reason."),
    ("registration_to_getpawns_helper", "getpawns_registration", 0x0027AADE, "e88de80000", "getpawns_binding_helper", 0x00289370, "Bind the stored target through the helper that names GetPawns."),
)


DATA_POINTER_SPECS = (
    ("boardplayer_primary_slot", 0x00430158, ".rdata", "90ae5800", "primary_orchestrator", 0x0018AE90, "BoardPlayer vtable VA 0x00830148 slot +0x10."),
    ("boardplayer_busy_slot", 0x00430188, ".rdata", "e0365900", "boardplayer_busy_thunk", 0x001936E0, "BoardPlayer vtable VA 0x00830148 slot +0x40."),
    ("board_activity_slot", 0x0042E2C0, ".rdata", "e0985600", "board_activity_boolean", 0x001698E0, "Board secondary vtable VA 0x0082e258 slot +0x68."),
)


STRING_ANCHOR_SPEC = {
    "id": "getpawns_name",
    "string_rva": 0x004389F8,
    "string_hex": "4765745061776e7300",
    "reference_region": "getpawns_binding_helper",
    "reference_rva": 0x002893BF,
    "reference_hex": "c74208f8898300",
    "meaning": "The binding helper names the registered native target GetPawns.",
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
        raise PistonSchedulerBoundaryError(f"dependency is not an object: {path}")
    return value


def _bytes_at(image: Any, data: bytes, rva: int, size: int) -> bytes:
    offset = image.rva_span_to_file_offset(rva, size)
    if offset is None:
        raise PistonSchedulerBoundaryError(f"RVA 0x{rva:08x} is not file-backed")
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise PistonSchedulerBoundaryError("reviewed direct edge is not CALL rel32")
    return rva + 5 + struct.unpack("<i", encoded[1:])[0]


def _dependency_records() -> list[dict[str, str]]:
    return [dict(spec) for spec in DEPENDENCY_SPECS]


def _source_records() -> list[dict[str, Any]]:
    return [dict(spec) for spec in SOURCE_SPECS]


def _region_records() -> list[dict[str, Any]]:
    return [
        {
            "id": item[0],
            "evidence_class": "fact",
            "start_rva": f"0x{item[1]:08x}",
            "end_rva_exclusive": f"0x{item[2]:08x}",
            "size": item[2] - item[1],
            "sha256": item[3],
            "section": ".text",
            "boundary_basis": item[4],
        }
        for item in REGION_SPECS
    ]


def _control_window_records() -> list[dict[str, Any]]:
    return [
        {
            "id": item[0],
            "region": item[1],
            "start_rva": f"0x{item[2]:08x}",
            "size": len(bytes.fromhex(item[3])),
            "sha256": hashlib.sha256(bytes.fromhex(item[3])).hexdigest(),
            "instruction_hex": item[3],
            "evidence_class": "fact",
            "meaning": item[4],
        }
        for item in CONTROL_WINDOW_SPECS
    ]


def _direct_edge_records() -> list[dict[str, Any]]:
    return [
        {
            "id": item[0],
            "kind": "direct_rel32",
            "source_region": item[1],
            "from_rva": f"0x{item[2]:08x}",
            "instruction_hex": item[3],
            "target_region": item[4],
            "target_rva": f"0x{item[5]:08x}",
            "evidence_class": "fact",
            "meaning": item[6],
        }
        for item in DIRECT_EDGE_SPECS
    ]


def _data_pointer_records() -> list[dict[str, Any]]:
    return [
        {
            "id": item[0],
            "data_rva": f"0x{item[1]:08x}",
            "section": item[2],
            "instruction_hex": item[3],
            "target_region": item[4],
            "target_rva": f"0x{item[5]:08x}",
            "target_va": f"0x{EXPECTED_IMAGE_BASE + item[5]:08x}",
            "evidence_class": "fact",
            "role": item[6],
        }
        for item in DATA_POINTER_SPECS
    ]


def _string_anchor_record() -> dict[str, Any]:
    item = STRING_ANCHOR_SPEC
    return {
        "id": item["id"],
        "string_rva": f"0x{item['string_rva']:08x}",
        "string_hex": item["string_hex"],
        "reference_region": item["reference_region"],
        "reference_rva": f"0x{item['reference_rva']:08x}",
        "reference_hex": item["reference_hex"],
        "evidence_class": "fact",
        "meaning": item["meaning"],
    }


def _contracts() -> dict[str, Any]:
    return {
        "mission_source": {
            "mission_id": "Mission_Piston",
            "base_class": "Mission_Auto",
            "environment_override_present": False,
            "inherited_environment": "Env_Null",
            "environment_is_effect": False,
            "environment_apply_effect": False,
            "piston_team": "TEAM_NONE",
            "piston_neutral": True,
            "piston_health": 1,
            "piston_move_speed": 0,
            "piston_pushable": False,
            "piston_corpse": True,
            "target_score": 100,
            "effect": "queued zero-damage fixed-direction push on the front tile",
        },
        "board_vector_order": {
            "board_vector_begin_offset": "+0x3c",
            "board_vector_end_offset": "+0x40",
            "getpawns_binding_target_rva": "0x001663a0",
            "getpawns_preserves_board_vector_order": True,
            "planning_copies_board_vector_order": True,
            "planning_team_value": 6,
            "planning_neutral_offset": "+0x97c",
            "planning_includes_team_or_neutral": True,
            "planning_filter_stable": True,
            "execution_returns_first_queued_pawn": True,
            "uid_sort_present": False,
            "pistons_and_vek_share_order_source": True,
        },
        "queued_action": {
            "skill_manager_offset": "+0x3c",
            "target_x_offset": "+0x20",
            "target_y_offset": "+0x24",
            "action_index_offset": "+0x28",
            "queued_requires_skill_manager": True,
            "queued_requires_valid_target": True,
            "queued_requires_nonnegative_action_index": True,
            "board_activity_checked_before_next_selection": True,
            "board_activity_vtable_chain": [
                "BoardPlayer+0x40",
                "Board secondary vtable+0x68",
                "Board activity reason",
            ],
        },
        "death_cancellation": {
            "new_death_flag_offset": "+0x921",
            "explicit_kill_clears_queued_fields": True,
            "shared_pawn_update_clears_queued_fields_before_return": True,
            "standalone_reset_clears_queued_fields": True,
            "planning_active_requires_not_dead": True,
            "board_update_precedes_phase_update": True,
            "earlier_queued_effect_blocks_next_selection_until_board_idle": True,
            "corpse_remains_occupancy": True,
            "corpse_retains_queued_action": False,
            "stock_piston_death_before_selection_cancels_action": True,
            "covered_stock_paths": [
                "player or other effect before enemy phase",
                "fire resolved during Pawn/Board update",
                "earlier queued Vek action while Board remains busy",
            ],
        },
        "exact_action_order": {
            "planning_phase_transition_call_rva": "0x0018a485",
            "execution_phase_transition_call_rva": "0x0018a822",
            "selector_call_rva": "0x001899e5",
            "order": "first-to-last Board pawn vector among still-queued pawns",
            "piston_push_occurs_at_piston_vector_slot": True,
            "vek_and_piston_actions_interleave": True,
            "dead_piston_slot_is_skipped": True,
            "corpse_wreck_is_not_removed_by_action_cancellation": True,
            "environment_precedence_changes_order": False,
            "environment_precedence_reason": "Mission_Piston inherits no-op Env_Null",
        },
        "scope": {
            "applies_to": "stock Mission_Piston on exact Windows build 13725832",
            "static_native_analysis": True,
            "runtime_trace_required_for_this_boundary": False,
            "mission_setup_rng_modeled": False,
            "other_neutral_actor_families_generalized": False,
            "modded_environment_or_scheduler_generalized": False,
            "non_windows_equivalence_claimed": False,
        },
    }


def _findings() -> list[dict[str, str]]:
    return [
        {
            "id": "getpawns_is_board_vector_order",
            "classification": "fact",
            "claim": (
                "The exact GetPawns binding targets the native routine that filters "
                "Board+[0x3c,0x40) in encounter order and emits pawn IDs without sorting."
            ),
        },
        {
            "id": "neutral_pistons_join_vek_planning",
            "classification": "fact",
            "claim": (
                "AI planning copies that Board vector, retains team 6 or Neutral+0x97c "
                "pawns in place, and therefore plans stock Pistons and Vek from one order."
            ),
        },
        {
            "id": "execution_uses_same_vector",
            "classification": "fact",
            "claim": (
                "The queued-action selector scans the Board vector first-to-last and "
                "returns the first Pawn whose skill manager, target, and action index "
                "still describe a complete queued action."
            ),
        },
        {
            "id": "board_idle_gate_separates_actions",
            "classification": "fact",
            "claim": (
                "The executor checks the exact Board activity vtable chain before each "
                "new selection, so an earlier queued effect must settle before another "
                "Piston or Vek can be chosen."
            ),
        },
        {
            "id": "death_clears_piston_queue",
            "classification": "fact",
            "claim": (
                "Explicit Pawn:Kill and the tail of every shared Pawn update both clear "
                "queued target coordinates and action index; planning also rejects dead "
                "pawns. Corpse=true does not preserve an executable queue."
            ),
        },
        {
            "id": "piston_has_no_environment_action",
            "classification": "fact",
            "claim": (
                "Mission_Piston declares no Environment override, inherits Mission's "
                "Env_Null, and Env_Null inherits false IsEffect/ApplyEffect callbacks."
            ),
        },
        {
            "id": "exact_stock_piston_chronology",
            "classification": "inference",
            "claim": (
                "For the shipped mission, living Piston pushes interleave with Vek in "
                "Board-vector order. A Piston killed before its slot keeps its corpse "
                "wreck but loses its queued push before the selector can dispatch it."
            ),
        },
        {
            "id": "rust_projection_must_interleave",
            "classification": "inference",
            "claim": (
                "A conforming projection must preserve bridge unit order, merge Piston "
                "pushes with Vek actions at their Board-vector slots, and skip a dead "
                "Piston action without deleting its corpse occupancy."
            ),
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "mission_piston_setup_rng",
            "question": "What is the exact native setup RNG and rejected-candidate call order?",
            "next_evidence": "Map random_removal/random_element and Board placement helpers only if pre-mission generation enters solver scope.",
        },
        {
            "id": "general_corpse_lifecycle_states",
            "question": "What are every non-Piston transition into and out of lifecycle states 2/3/4?",
            "next_evidence": "Continue the corpse-classification boundary per concrete pawn family; it is no longer a Mission_Piston scheduler blocker.",
        },
        {
            "id": "modded_scheduler_variants",
            "question": "Can mods add an Environment or alternate scheduler to Mission_Piston?",
            "next_evidence": "Build a content-keyed map for the exact modded Lua tree before using this order there.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do macOS and other Windows depots use the same Piston scheduler?",
            "next_evidence": "Repeat this boundary map on the other exact executable and content tree.",
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
        "sources": _source_records(),
        "regions": _region_records(),
        "control_windows": _control_window_records(),
        "direct_edges": _direct_edge_records(),
        "data_pointers": _data_pointer_records(),
        "string_anchor": _string_anchor_record(),
        "contracts": _contracts(),
        "findings": findings,
        "refines": [
            {
                "artifact": DEPENDENCY_SPECS[0]["path"],
                "resolved_unresolved_ids": ["mission_piston_action_order"],
                "narrowed_unresolved_ids": ["lifecycle_state_transition_timing"],
                "qualification": (
                    "The general lifecycle-state question remains, but exact stock "
                    "Piston planning, execution, death cancellation, and corpse occupancy "
                    "are sufficient to close the Mission_Piston scheduler gate."
                ),
            }
        ],
        "unresolved": unresolved,
        "solver_impact": {
            "simulator_contradiction_found": True,
            "simulator_change_required": True,
            "previous_simulator_version": 407,
            "implemented_simulator_version": 408,
            "simulator_version_bump_required": True,
            "changes": [
                "preserve native Board-vector order in the bridge payload",
                "interleave Piston pushes and Vek actions in Rust",
                "cancel dead Piston pushes while preserving corpse occupancy",
                "replace the blanket safety gate with payload-completeness checks",
            ],
            "conforming_paths": [
                "src/bridge/modloader.lua::mission_pistons",
                "src/model/board.py::validate_mission_piston_payload",
                "rust_solver/src/enemy.rs::simulate_enemy_attacks",
                "src/loop/commands.py::_mission_piston_forecast_block",
            ],
        },
        "notes": [
            "This is exact-build static evidence, not a runtime trace.",
            "The no-environment conclusion is content-keyed to the shipped Lua tree.",
            "Board-vector order is native pointer order, not Pawn UID order.",
            "A dead Corpse=true Piston remains a blocker but not an action source.",
        ],
        "summary": {
            "dependency_count": len(DEPENDENCY_SPECS),
            "source_count": len(SOURCE_SPECS),
            "region_count": len(REGION_SPECS),
            "control_window_count": len(CONTROL_WINDOW_SPECS),
            "direct_edge_count": len(DIRECT_EDGE_SPECS),
            "data_pointer_count": len(DATA_POINTER_SPECS),
            "string_anchor_count": 1,
            "finding_count": len(findings),
            "unresolved_count": len(unresolved),
            "board_vector_order_proven": True,
            "neutral_piston_planning_proven": True,
            "vek_piston_interleaving_proven": True,
            "dead_piston_action_cancellation_proven": True,
            "mission_environment_is_null": True,
            "mission_piston_scheduler_gate_closed": True,
            "simulator_change_required": True,
            "simulator_version": 408,
        },
    }


def _verify_dependencies(executable: Path, content_root: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    validators = {
        "corpse_classification_boundary": validate_corpse_classification_boundary_map,
        "event_frame_visibility": validate_event_frame_visibility_map,
    }
    error_types = (CorpseClassificationBoundaryError, EventFrameVisibilityError)
    for spec in DEPENDENCY_SPECS:
        path = repository_root / spec["path"]
        if path.is_symlink() or not path.is_file():
            raise PistonSchedulerBoundaryError(f"dependency missing: {spec['id']}")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != spec["file_sha256"]:
            raise PistonSchedulerBoundaryError(f"dependency file differs: {spec['id']}")
        value = _read_json(path)
        if _canonical_sha256(value) != spec["canonical_sha256"]:
            raise PistonSchedulerBoundaryError(f"dependency fields differ: {spec['id']}")
        try:
            validators[spec["id"]](executable, content_root, value)
        except error_types as exc:
            raise PistonSchedulerBoundaryError(
                f"dependency does not reproduce: {spec['id']}: {exc}"
            ) from exc


def _verify_sources(content_root: Path) -> None:
    root = content_root.resolve()
    if not root.is_dir():
        raise PistonSchedulerBoundaryError("content root is not a directory")
    values: dict[str, bytes] = {}
    for spec in SOURCE_SPECS:
        source = root / spec["path"]
        try:
            resolved = source.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise PistonSchedulerBoundaryError(
                f"source is missing or escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise PistonSchedulerBoundaryError(
                f"source is not a regular non-symlink file: {spec['path']}"
            )
        raw = resolved.read_bytes()
        if len(raw) != spec["size"] or hashlib.sha256(raw).hexdigest() != spec["sha256"]:
            raise PistonSchedulerBoundaryError(f"source identity differs: {spec['path']}")
        values[spec["path"]] = raw

    piston = values["scripts/missions/acid/mission_piston.lua"]
    piston_tokens = (
        b"Mission_Piston = Mission_Auto:new",
        b"Neutral = true",
        b"Corpse = true",
        b"MoveSpeed = 0",
        b"DefaultTeam = TEAM_NONE",
        b"Pushable = false",
        b"return 100",
        b"ret:AddQueuedDamage(SpaceDamage(p1+DIR_VECTORS[self.Direction],0,self.Direction))",
    )
    if any(token not in piston for token in piston_tokens) or b"Environment =" in piston:
        raise PistonSchedulerBoundaryError("Mission_Piston source semantics differ")

    missions = values["scripts/missions/missions.lua"]
    mission_tokens = (
        b'Environment = "Env_Null"',
        b"LiveEnvironment = Env_Null",
        b"Mission_Auto = Mission_Infinite:new",
    )
    if any(token not in missions for token in mission_tokens):
        raise PistonSchedulerBoundaryError("Mission inheritance semantics differ")

    environments = values["scripts/environments.lua"]
    environment_tokens = (
        b"function Environment:IsEffect() return false end",
        b"function Environment:ApplyEffect() return false end",
        b"Env_Null = Environment:new{ InQueue = false, }",
    )
    if any(token not in environments for token in environment_tokens):
        raise PistonSchedulerBoundaryError("Env_Null semantics differ")


def build_piston_scheduler_boundary_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact stock Mission_Piston scheduler boundary."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise PistonSchedulerBoundaryError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise PistonSchedulerBoundaryError("executable identity differs")

    _verify_dependencies(executable, content_root)
    _verify_sources(content_root)

    ranges: dict[str, tuple[int, int]] = {}
    for region_id, start, end, expected_hash, _basis in REGION_SPECS:
        try:
            body = _region_bytes(
                image, data, start, end - start, ".text", region_id
            )
        except Exception as exc:
            raise PistonSchedulerBoundaryError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != expected_hash:
            raise PistonSchedulerBoundaryError(f"region bytes differ: {region_id}")
        ranges[region_id] = (start, end)

    decode_ranges: dict[str, tuple[int, int]] = {}
    for window_id, region_id, start, expected_hex, _meaning in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(expected_hex)
        if _bytes_at(image, data, start, len(encoded)) != encoded:
            raise PistonSchedulerBoundaryError(f"control window differs: {window_id}")
        region_start, region_end = ranges[region_id]
        if not region_start <= start < start + len(encoded) <= region_end:
            raise PistonSchedulerBoundaryError(f"control window escapes region: {window_id}")
        decode_ranges[f"window_{window_id}"] = (start, start + len(encoded))

    for edge_id, source_region, source, expected_hex, target_region, target, _meaning in DIRECT_EDGE_SPECS:
        encoded = bytes.fromhex(expected_hex)
        if _bytes_at(image, data, source, len(encoded)) != encoded:
            raise PistonSchedulerBoundaryError(f"direct edge differs: {edge_id}")
        source_start, source_end = ranges[source_region]
        target_start, target_end = ranges[target_region]
        if not source_start <= source < source + 5 <= source_end:
            raise PistonSchedulerBoundaryError(f"direct edge escapes source: {edge_id}")
        if not target_start <= target < target_end:
            raise PistonSchedulerBoundaryError(f"direct edge escapes target: {edge_id}")
        if _direct_target(source, encoded) != target:
            raise PistonSchedulerBoundaryError(f"direct edge target differs: {edge_id}")
        decode_ranges[f"edge_{edge_id}"] = (source, source + 5)

    for pointer_id, data_rva, section_name, expected_hex, target_region, target_rva, _role in DATA_POINTER_SPECS:
        encoded = bytes.fromhex(expected_hex)
        if _bytes_at(image, data, data_rva, len(encoded)) != encoded:
            raise PistonSchedulerBoundaryError(f"data pointer differs: {pointer_id}")
        section = next(
            (
                item
                for item in image.sections
                if item.virtual_address <= data_rva < item.virtual_address + item.raw_size
            ),
            None,
        )
        if section is None or section.name != section_name or section.executable:
            raise PistonSchedulerBoundaryError(f"data pointer section differs: {pointer_id}")
        (target_va,) = struct.unpack("<I", encoded)
        if target_va != image.image_base + target_rva:
            raise PistonSchedulerBoundaryError(f"data pointer target differs: {pointer_id}")
        target_start, target_end = ranges[target_region]
        if not target_start <= target_rva < target_end:
            raise PistonSchedulerBoundaryError(f"data pointer target escapes region: {pointer_id}")

    anchor = STRING_ANCHOR_SPEC
    string_bytes = bytes.fromhex(anchor["string_hex"])
    reference_bytes = bytes.fromhex(anchor["reference_hex"])
    if _bytes_at(image, data, anchor["string_rva"], len(string_bytes)) != string_bytes:
        raise PistonSchedulerBoundaryError("GetPawns string anchor differs")
    if (
        _bytes_at(image, data, anchor["reference_rva"], len(reference_bytes))
        != reference_bytes
        or struct.pack("<I", image.image_base + anchor["string_rva"])
        not in reference_bytes
    ):
        raise PistonSchedulerBoundaryError("GetPawns string reference differs")
    decode_ranges["getpawns_name_reference"] = (
        anchor["reference_rva"],
        anchor["reference_rva"] + len(reference_bytes),
    )

    try:
        decoded = _decode_x86_regions(image, data, decode_ranges)
    except Exception as exc:
        raise PistonSchedulerBoundaryError(f"instruction alignment differs: {exc}") from exc
    for name, (start, end) in decode_ranges.items():
        cursor = start
        instructions = decoded[name]
        while cursor < end:
            instruction = instructions.get(cursor)
            if instruction is None:
                raise PistonSchedulerBoundaryError(f"undecoded instruction in {name}")
            cursor += len(instruction[1])
        if cursor != end:
            raise PistonSchedulerBoundaryError(f"reviewed range ends inside instruction: {name}")

    if not (
        0x0018B0E1 < 0x0018B190
        and 0x00233EE0 < 0x00234C3F < 0x00234C70
        and 0x001899A3 < 0x001899E5
    ):
        raise PistonSchedulerBoundaryError("reviewed scheduler chronology differs")

    return _expected_shape()


def validate_piston_scheduler_boundary_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping) or dict(value) != _expected_shape():
        raise PistonSchedulerBoundaryError("Piston scheduler map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "board_vector_order_proven": True,
        "vek_piston_interleaving_proven": True,
        "dead_piston_action_cancellation_proven": True,
        "mission_environment_is_null": True,
        "mission_piston_scheduler_gate_closed": True,
        "simulator_change_required": True,
        "simulator_version": 408,
    }


def validate_piston_scheduler_boundary_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject dependency, source, byte, or prose drift."""
    expected = build_piston_scheduler_boundary_map(executable, content_root)
    if dict(value) != expected:
        raise PistonSchedulerBoundaryError(
            "Piston scheduler map differs from exact-build analysis"
        )
    result = validate_piston_scheduler_boundary_map_binding(value)
    result["status"] = "verified"
    return result


def encode_piston_scheduler_boundary_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
