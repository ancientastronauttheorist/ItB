"""Reproduce the exact-build Final Cave countdown outcome boundary.

This immutable follow-up closes the conservative ``cave_countdown_outcome``
gap left by the earlier Final settlement map.  It joins the state-transition
callers, the native outcome writer, the exact ``Board:GetPawnCount`` binding,
and the shipped Final Cave source.

The reviewed ordinary state-2 path writes outcome code 1 as soon as the
current turn reaches the current ``GetTurnLimit`` value.  That closed path
does not consult the bomb, objectives, or ``IsEndBlocked``.  A separate forced
state-0 path can write outcome code 3 when ``GetPawnCount(TEAM_MECH)`` is zero.
The artifact does not predict replacement-bomb timing or coordinates and does
not claim equivalence for another executable build.
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
ANALYSIS_KIND = "final_cave_outcome_boundary_map"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_IMAGE_BASE = 0x00400000
EXPECTED_SCRIPTS_REVISION_SHA256 = (
    "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
)
SUPERSEDED_END_SETTLEMENT_ARTIFACT_SHA256 = (
    "541237f7e723c1ec56b0328cb1f137f2a6725bda55c588d0a7ebc74adc55be0c"
)
CAMPAIGN_SETTLEMENT_ARTIFACT_SHA256 = (
    "cb3d8105929e0a428a6627760919302360ee7a0eb181dbb2e3b04531138a81a7"
)


class FinalCaveOutcomeError(RuntimeError):
    """Raised when the reviewed Final Cave outcome map cannot be reproduced."""


SOURCE_SPECS = (
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
            "Mission_Final_Cave:UpdateObjectives",
            "Mission_Final_Cave:AddBomb",
            "Mission_Final_Cave:IsEndBlocked",
            "BigBomb",
        ],
        "reviewed_lines": [[3, 13], [25, 33], [116, 188]],
    },
)


REGION_SPECS = (
    {
        "id": "outcome_initialization_window",
        "start": 0x0017FE04,
        "end": 0x0017FE22,
        "sha256": (
            "7403d51f5d2f6916f2c2bde7c22fc6398ef7dd194bfc91a37b150a0d78b024eb"
        ),
        "boundary_basis": (
            "Instruction-aligned outcome-field initialization window inside "
            "the Ghidra 12.1.3 BoardPlayer constructor."
        ),
    },
    {
        "id": "get_pawn_count",
        "start": 0x001716C0,
        "end": 0x0017188B,
        "sha256": (
            "692c77c25d30bc26468f48881677077e352705224888c70b6ecf8d32ed9c90c6"
        ),
        "boundary_basis": "Ghidra 12.1.3 Board GetPawnCount function body.",
    },
    {
        "id": "final_mode_predicate",
        "start": 0x00183080,
        "end": 0x001830C5,
        "sha256": (
            "0d0782d0f859541aa7eae0a0b33ca195305672cc6fbbc2c5626ca68e96ccd70f"
        ),
        "boundary_basis": "Ghidra 12.1.3 mission-mode predicate body.",
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
        "id": "state_transition",
        "start": 0x0018A2C0,
        "end": 0x0018A955,
        "sha256": (
            "903ca7d14ba5317753901f70ec24acfb31ea44e947d3ebce3246651897bc2b90"
        ),
        "boundary_basis": "Ghidra 12.1.3 BoardPlayer state-transition body.",
    },
    {
        "id": "outcome_dispatch",
        "start": 0x0018B780,
        "end": 0x0018B9FF,
        "sha256": (
            "00e1f495aa53d2a439c4eeb6e41e1d5ac5b304e0c050e4343bd0433f9ff74ee9"
        ),
        "boundary_basis": "Ghidra 12.1.3 mission-outcome dispatcher body.",
    },
    {
        "id": "outcome_getter",
        "start": 0x001937C0,
        "end": 0x001937C7,
        "sha256": (
            "705bd97156f230addc79eb9489880df1d2a025762435056cf5a33937b8508e79"
        ),
        "boundary_basis": "Ghidra 12.1.3 BoardPlayer outcome getter body.",
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
        "id": "get_pawn_count_registration_window",
        "start": 0x0027A469,
        "end": 0x0027A48E,
        "sha256": (
            "7741af697793add35e3c4a455e28fb35257031f78e6fffe8cb6004f27ea6e130"
        ),
        "boundary_basis": (
            "Instruction-aligned Luabind registration window inside the "
            "reviewed registration function; this is not a function boundary."
        ),
    },
    {
        "id": "team_mech_registration_window",
        "start": 0x0027E8AA,
        "end": 0x0027E8E8,
        "sha256": (
            "d0d4a0fd0b014a6725c97a7fcd7ec1c174fc2a7b97b9aec9bf0a1d4a4fd327e9"
        ),
        "boundary_basis": (
            "Instruction-aligned Lua constant-registration window inside the "
            "reviewed registration function; this is not a function boundary."
        ),
    },
)


STRING_ANCHOR_SPECS = (
    {
        "id": "bonus_debris",
        "region_id": "get_pawn_count",
        "reference_rva": 0x00171729,
        "instruction_hex": "ba58ea8200",
        "string_rva": 0x0042EA58,
        "text": "BonusDebris",
        "role": "special pawn-type prefix excluded from the primary count",
    },
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
        "id": "state_disabled",
        "region_id": "outcome_dispatch",
        "reference_rva": 0x0018B894,
        "instruction_hex": "68a4f98200",
        "string_rva": 0x0042F9A4,
        "text": "State_Disabled",
        "role": "outcome-code-3 failure presentation state",
    },
    {
        "id": "final_victory",
        "region_id": "outcome_dispatch",
        "reference_rva": 0x0018B96A,
        "instruction_hex": "68f4f98200",
        "string_rva": 0x0042F9F4,
        "text": "/ui/battle/final_victory",
        "role": "Final mission victory presentation route",
    },
    {
        "id": "mission_end",
        "region_id": "outcome_dispatch",
        "reference_rva": 0x0018B984,
        "instruction_hex": "68e8f98200",
        "string_rva": 0x0042F9E8,
        "text": "MissionEnd",
        "role": "mission completion callback",
    },
    {
        "id": "get_pawn_count_name",
        "region_id": "get_pawn_count_registration_window",
        "reference_rva": 0x0027A482,
        "instruction_hex": "689c878300",
        "string_rva": 0x0043879C,
        "text": "GetPawnCount",
        "role": "Lua Board method mapped to native VA 0x005716c0",
    },
    {
        "id": "team_mech_name",
        "region_id": "team_mech_registration_window",
        "reference_rva": 0x0027E8AA,
        "instruction_hex": "68a0978300",
        "string_rva": 0x004397A0,
        "text": "TEAM_MECH",
        "role": "Lua team constant registered with integer value 4",
    },
)


DATA_POINTER_SPECS = (
    {
        "id": "state_case_zero",
        "data_rva": 0x0018A958,
        "section": ".text",
        "executable": True,
        "target_region": "state_transition",
        "target_rva": 0x0018A48F,
        "role": "state-transition jump-table entry 0",
    },
    {
        "id": "state_case_one",
        "data_rva": 0x0018A95C,
        "section": ".text",
        "executable": True,
        "target_region": "state_transition",
        "target_rva": 0x0018A770,
        "role": "state-transition jump-table entry 1",
    },
    {
        "id": "state_case_two",
        "data_rva": 0x0018A960,
        "section": ".text",
        "executable": True,
        "target_region": "state_transition",
        "target_rva": 0x0018A399,
        "role": "state-transition jump-table entry 2",
    },
    {
        "id": "outcome_getter_vtable_slot",
        "data_rva": 0x00430194,
        "section": ".rdata",
        "executable": False,
        "target_region": "outcome_getter",
        "target_rva": 0x001937C0,
        "role": "BoardPlayer vtable VA 0x00830148 slot +0x4c",
    },
)


CONTROL_WINDOW_SPECS = (
    {
        "id": "pending_codes_initialized",
        "region_id": "outcome_initialization_window",
        "start_rva": 0x0017FE04,
        "instruction_hex": "c7860019000002000000c7860419000002000000",
        "meaning": (
            "Initialize primary outcome +0x1900 and secondary outcome +0x1904 "
            "to pending code 2."
        ),
    },
    {
        "id": "pawn_count_candidate_filter",
        "region_id": "get_pawn_count",
        "start_rva": 0x00171700,
        "instruction_hex": (
            "8b4f3c8d44241c50be0b0000008b0c91e83b150d008bc8837914108d59107202"
            "8b098b1b8bc683fb0bba58ea82000f42c350e879aaefff8bf083c40485f67515"
            "83fb0b730583ceffeb0bb80b0000003bc31bf6f7de8b44243083f81072106a01"
            "4050ff742424e89560e9ff83c40c8b4424108b4f3c8d1c8500000000ff75088b"
            "0c19e8d9c00c0084c0741c8b473c8b0c038b018b4010ffd084c0750b85f67407"
            "b801000000eb0233c08b4f3cff750801442418"
        ),
        "meaning": (
            "Build the primary team-matched, non-BonusDebris pawn count used "
            "by the function's zero/nonzero result contract."
        ),
    },
    {
        "id": "pawn_count_zero_contract",
        "region_id": "get_pawn_count",
        "start_rva": 0x00171837,
        "instruction_hex": (
            "85db743a660f6ec60f5bc0660f6ecbf30f5e0508cc83000f5bc9f30f5cc8f30f"
            "5f0d74cb8300f30f2cc15f5e5b8b4c242833cce85b5c1e008be55dc204008b4c"
            "24348bc35f5e5b33cce8455c1e008be55dc20400"
        ),
        "meaning": (
            "Return zero exactly when the primary count is zero; any nonzero "
            "primary count is clamped to a result of at least one."
        ),
    },
    {
        "id": "get_pawn_count_binding",
        "region_id": "get_pawn_count_registration_window",
        "start_rva": 0x0027A469,
        "instruction_hex": (
            "ff75f0c745e8c0165700ff75f0c745ec00000000518d4de851689c8783008bc8"
            "e8f2e70000"
        ),
        "meaning": (
            "Register native handler VA 0x005716c0 under the Lua Board method "
            "name GetPawnCount."
        ),
    },
    {
        "id": "team_mech_constant",
        "region_id": "team_mech_registration_window",
        "start_rva": 0x0027E8AA,
        "instruction_hex": (
            "68a09783008d8d20f8ffff518bc8e8931fddff8bd88b4b08ff710468f0d8ffff"
            "ff33ff15c0647d00ff73048b3b57ff15e4647d006a04ff33ff158c647d00"
        ),
        "meaning": "Register Lua constant TEAM_MECH with exact integer value 4.",
    },
    {
        "id": "final_limit_short_circuit",
        "region_id": "end_readiness",
        "start_rva": 0x00185C71,
        "instruction_hex": (
            "e84a38ecff83bee40f0000007424398654010000752283bec80f0000027513b001"
            "8b4df464890d00000000595f5e8be55dc3"
        ),
        "meaning": (
            "After GetTurnLimit, return ready when an active Board exists, "
            "turn equals that limit, and BoardPlayer state is 2, before the "
            "later IsEndBlocked fallback."
        ),
    },
    {
        "id": "turn_state_store_and_dispatch",
        "region_id": "state_transition",
        "start_rva": 0x0018A367,
        "instruction_hex": (
            "8b4f048d8564ffffff50e8fabaf6ffc745fc000000008b9d64ffffff89b7c80f"
            "000083fe050f878a050000ff24b558a95800"
        ),
        "meaning": (
            "Store the requested state at +0xfc8 and dispatch through the "
            "six-entry state jump table."
        ),
    },
    {
        "id": "state_two_nonforced_outcome_dispatch",
        "region_id": "state_transition",
        "start_rva": 0x0018A3A7,
        "instruction_hex": "6a008bcfe8d0130000",
        "meaning": "State case 2 calls the outcome dispatcher with forced=false.",
    },
    {
        "id": "state_zero_forced_outcome_dispatch",
        "region_id": "state_transition",
        "start_rva": 0x0018A494,
        "instruction_hex": "6a018bcfe8e3120000",
        "meaning": "State case 0 calls the outcome dispatcher with forced=true.",
    },
    {
        "id": "outcome_entry_guards",
        "region_id": "outcome_dispatch",
        "start_rva": 0x0018B7A6,
        "instruction_hex": (
            "83be00190000020f853a0200008b8e941c00008d86981c00003bc8741885c974"
            "1483790400750e8a860d17000084c00f841202000080be0e170000000f850502"
            "0000"
        ),
        "meaning": (
            "Only a pending primary outcome reaches classification, subject "
            "to the reviewed mission-owner and tutorial/reentry guards."
        ),
    },
    {
        "id": "state_three_pending_suppression",
        "region_id": "outcome_dispatch",
        "start_rva": 0x0018B7E8,
        "instruction_hex": (
            "83bec80f000003751583be0419000002750cc7860019000002000000eb3b"
        ),
        "meaning": "State 3 preserves pending code 2 when the secondary code is 2.",
    },
    {
        "id": "ordinary_ready_writes_success",
        "region_id": "outcome_dispatch",
        "start_rva": 0x0018B806,
        "instruction_hex": (
            "8a860c17000084c08b8604190000752583f802752083bee40f000000741d8bcee8"
            "95a3ffff84c07412c7860019000001000000eb06898600190000"
        ),
        "meaning": (
            "With ordinary flags, secondary code 2, an active Board, and true "
            "end readiness, write primary outcome code 1."
        ),
    },
    {
        "id": "forced_zero_mechs_writes_failure",
        "region_id": "outcome_dispatch",
        "start_rva": 0x0018B841,
        "instruction_hex": (
            "83be00190000027535807d080074228b4e046a04e8665efeff85c075148a860d17"
            "000084c0750ac7860019000003000000"
        ),
        "meaning": (
            "If the result is still pending and forced evaluation is true, "
            "call GetPawnCount(4) and write code 3 only when it returns zero."
        ),
    },
    {
        "id": "committed_result_gate",
        "region_id": "outcome_dispatch",
        "start_rva": 0x0018B872,
        "instruction_hex": "83be00190000020f846e010000",
        "meaning": "Return while outcome remains pending; continue only for a result.",
    },
    {
        "id": "failure_presentation_route",
        "region_id": "outcome_dispatch",
        "start_rva": 0x0018B88B,
        "instruction_hex": (
            "83be0019000003752568a4f982008d8e701a0000e8ecc6e7ff68dcdf80008d8e"
            "881a0000e8dcc6e7ffe9f9000000"
        ),
        "meaning": "Outcome code 3 selects the disabled/failure presentation route.",
    },
    {
        "id": "final_victory_route",
        "region_id": "outcome_dispatch",
        "start_rva": 0x0018B936,
        "instruction_hex": (
            "6a028bcee84177ffff84c075196a038bcee83477ffff84c0750c83ec188bcc68c4"
            "f98200eb1383be9045000003751783ec188bcc68f4f98200e89cc4e7ffe8c7fb"
            "f4ff"
        ),
        "meaning": (
            "A committed non-failure result in Final mode 3 selects "
            "/ui/battle/final_victory."
        ),
    },
    {
        "id": "mission_end_then_state_five",
        "region_id": "outcome_dispatch",
        "start_rva": 0x0018B97C,
        "instruction_hex": (
            "83ec188bcc89650868e8f98200e882c4e7ff83ec18c745fc000000008d86d40f"
            "00008bcc50e86af2ebffc745fcffffffffe84edf00008bcee8370200006a058bce"
            "e8fee8ffff"
        ),
        "meaning": (
            "Dispatch MissionEnd, perform completion bookkeeping, then request "
            "BoardPlayer state 5."
        ),
    },
    {
        "id": "outcome_getter_body",
        "region_id": "outcome_getter",
        "start_rva": 0x001937C0,
        "instruction_hex": "8b8100190000c3",
        "meaning": "Return the primary outcome stored at BoardPlayer+0x1900.",
    },
)


DIRECT_EDGE_SPECS = (
    {
        "id": "state_two_to_outcome_dispatch",
        "source_region": "state_transition",
        "from_rva": 0x0018A3AB,
        "instruction_hex": "e8d0130000",
        "target_region": "outcome_dispatch",
        "target_rva": 0x0018B780,
        "meaning": "State case 2 invokes nonforced outcome classification.",
    },
    {
        "id": "state_zero_to_outcome_dispatch",
        "source_region": "state_transition",
        "from_rva": 0x0018A498,
        "instruction_hex": "e8e3120000",
        "target_region": "outcome_dispatch",
        "target_rva": 0x0018B780,
        "meaning": "State case 0 invokes forced outcome classification.",
    },
    {
        "id": "outcome_to_end_readiness",
        "source_region": "outcome_dispatch",
        "from_rva": 0x0018B826,
        "instruction_hex": "e895a3ffff",
        "target_region": "end_readiness",
        "target_rva": 0x00185BC0,
        "meaning": "Ordinary outcome classification queries end readiness.",
    },
    {
        "id": "outcome_to_get_pawn_count",
        "source_region": "outcome_dispatch",
        "from_rva": 0x0018B855,
        "instruction_hex": "e8665efeff",
        "target_region": "get_pawn_count",
        "target_rva": 0x001716C0,
        "meaning": "Forced pending classification queries GetPawnCount(4).",
    },
    {
        "id": "outcome_to_final_mode_predicate_two",
        "source_region": "outcome_dispatch",
        "from_rva": 0x0018B93A,
        "instruction_hex": "e84177ffff",
        "target_region": "final_mode_predicate",
        "target_rva": 0x00183080,
        "meaning": "Presentation tests mission mode 2.",
    },
    {
        "id": "outcome_to_final_mode_predicate_three",
        "source_region": "outcome_dispatch",
        "from_rva": 0x0018B947,
        "instruction_hex": "e83477ffff",
        "target_region": "final_mode_predicate",
        "target_rva": 0x00183080,
        "meaning": "Presentation tests mission mode 3 before the Final route.",
    },
    {
        "id": "outcome_to_mission_named_invoker",
        "source_region": "outcome_dispatch",
        "from_rva": 0x0018B9AD,
        "instruction_hex": "e84edf0000",
        "target_region": "mission_named_invoker",
        "target_rva": 0x00199900,
        "meaning": "Invoke the prepared MissionEnd callback name.",
    },
    {
        "id": "outcome_to_state_transition",
        "source_region": "outcome_dispatch",
        "from_rva": 0x0018B9BD,
        "instruction_hex": "e8fee8ffff",
        "target_region": "state_transition",
        "target_rva": 0x0018A2C0,
        "meaning": "Request completion state 5 after MissionEnd dispatch.",
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
        raise FinalCaveOutcomeError(
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
        raise FinalCaveOutcomeError(
            f"RVA 0x{rva:08x} is not in {expected} file-backed data"
        )
    if expected_section is not None and section.name != expected_section:
        raise FinalCaveOutcomeError(
            f"RVA 0x{rva:08x} section differs: "
            f"{expected_section!r} != {section.name!r}"
        )
    return data[offset : offset + size]


def _direct_target(rva: int, encoded: bytes) -> int:
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise FinalCaveOutcomeError(
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


def _dependencies() -> list[dict[str, Any]]:
    return [
        {
            "artifact": (
                "data/observatory/native/"
                "windows_build_13725832_31fe35265598_final_end_settlement.json"
            ),
            "artifact_sha256": SUPERSEDED_END_SETTLEMENT_ARTIFACT_SHA256,
            "role": (
                "Pins the current-limit state-2 readiness short circuit and "
                "MissionEnd activity-clear handoff."
            ),
        },
        {
            "artifact": (
                "data/observatory/native/"
                "windows_build_13725832_31fe35265598_final_campaign_settlement.json"
            ),
            "artifact_sha256": CAMPAIGN_SETTLEMENT_ARTIFACT_SHA256,
            "role": (
                "Pins downstream consumption of outcome code 3 as campaign "
                "result 2 and every other committed code as result 1."
            ),
        },
    ]


def _contracts() -> dict[str, Any]:
    return {
        "outcome_codes": {
            "storage_offset": "0x1900",
            "secondary_offset": "0x1904",
            "pending": 2,
            "victory": 1,
            "failure": 3,
            "initial_primary": 2,
            "initial_secondary": 2,
        },
        "ordinary_final_cave_countdown": {
            "transition_state": 2,
            "forced_evaluation": False,
            "inputs": [
                "primary and secondary outcome codes are pending (2)",
                "ordinary mission-owner/tutorial guards admit classification",
                "active Board pointer is nonzero",
                "current turn equals the current Mission:GetTurnLimit()",
                "BoardPlayer state equals 2",
            ],
            "result": "primary outcome code 1",
            "is_end_blocked_invoked_on_ready_branch": False,
            "bomb_or_objective_query_between_ready_and_write": False,
            "next_steps": [
                "Final victory presentation",
                "MissionEnd callback",
                "BoardPlayer completion state 5",
            ],
        },
        "forced_no_mech_failure": {
            "transition_state": 0,
            "forced_evaluation": True,
            "only_when_primary_still_pending": True,
            "query": "Board:GetPawnCount(TEAM_MECH)",
            "team_constant": 4,
            "zero_result": "primary outcome code 3",
            "nonzero_result": "primary outcome remains pending",
        },
        "missing_bomb_lifecycle": {
            "source_trigger": "not IsBomb() after Board:IsBusy() is false",
            "source_effect": "queue AddBomb and add 2 to TurnLimit",
            "countdown_uses_extended_limit": True,
            "direct_terminal_bomb_check_in_ready_to_victory_path": False,
            "replacement_timing_or_coordinate_predicted": False,
        },
        "campaign_consumption": {
            "outcome_getter_offset": "0x4c",
            "outcome_code_3": "campaign result 2",
            "every_other_committed_outcome": "campaign result 1",
            "result_1_route": "campaign victory",
        },
    }


def _method() -> dict[str, Any]:
    return {
        "boundary_review": (
            "Focused Ghidra 12.1.3 constructor, registration, jump-table, "
            "call-graph, instruction, and decompiler review joined the state-2 "
            "and state-0 callers to the outcome writer and its downstream UI."
        ),
        "byte_verification": (
            "Capstone 5.0.7 redecodes every published executable region from "
            "its declared start; the verifier rechecks exact control windows, "
            "direct calls, strings, and jump/vtable pointers."
        ),
        "negative_boundary": (
            "The no-bomb/objective conclusion is limited to the closed "
            "state-2 readiness-to-code-1 instruction path. It is not a claim "
            "about arbitrary modified callbacks or every earlier scheduler step."
        ),
        "limitations": [
            "Every native address and conclusion applies only to the pinned Windows executable.",
            "Static control flow proves relative outcome order, not wall-clock callback timing.",
            "Replacement-bomb timing, coordinate selection, and repeated cycles remain unresolved.",
            "macOS and other executable builds require independent maps.",
        ],
    }


def _findings() -> list[dict[str, Any]]:
    return [
        {
            "id": "outcome_storage_and_callers_are_exact",
            "evidence_class": "inference",
            "claim": (
                "BoardPlayer initializes primary +0x1900 and secondary +0x1904 "
                "to pending code 2. The state jump table maps state 2 to a "
                "nonforced outcome-dispatch call and state 0 to a forced call."
            ),
            "supports": [
                "pending_codes_initialized",
                "state_case_zero",
                "state_case_two",
                "turn_state_store_and_dispatch",
                "state_two_nonforced_outcome_dispatch",
                "state_zero_forced_outcome_dispatch",
            ],
            "limitations": [
                "Debug/cheat writers of the secondary result are outside ordinary reachability."
            ],
        },
        {
            "id": "final_cave_limit_writes_victory",
            "evidence_class": "inference",
            "claim": (
                "On the ordinary Final Cave state-2 boundary, current turn "
                "equal to the current GetTurnLimit makes end readiness true "
                "and the outcome dispatcher writes code 1. It then selects "
                "the Final victory route, dispatches MissionEnd, and requests "
                "completion state 5."
            ),
            "supports": [
                "state_two_nonforced_outcome_dispatch",
                "outcome_to_end_readiness",
                "final_limit_short_circuit",
                "ordinary_ready_writes_success",
                "final_victory_route",
                "mission_end_then_state_five",
            ],
            "limitations": [
                "The precise runtime frame on which each presentation step appears is not claimed."
            ],
        },
        {
            "id": "countdown_does_not_recheck_bomb_or_objectives",
            "evidence_class": "inference",
            "claim": (
                "The closed ordinary path from the state-2 caller through the "
                "ready return and code-1 write contains no bomb, objective, or "
                "IsEndBlocked query. Final Cave's always-true IsEndBlocked and "
                "zero-reputation objective callback do not veto that reached "
                "countdown boundary."
            ),
            "supports": [
                "scripts/missions/final/mission_final_two.lua",
                "final_limit_short_circuit",
                "ordinary_ready_writes_success",
                "ordinary_final_cave_countdown",
            ],
            "limitations": [
                "Earlier UpdateMission work can change when the boundary is reached."
            ],
        },
        {
            "id": "missing_bomb_delays_instead_of_directly_losing",
            "evidence_class": "inference",
            "claim": (
                "A missing BigBomb is handled in shipped Lua by queuing a "
                "replacement and adding two to TurnLimit. Native readiness "
                "queries that current value, and the reached limit writes "
                "victory without a second bomb check. Bomb destruction is "
                "therefore a delay/replacement boundary, not a direct terminal "
                "loss predicate in the reviewed path."
            ),
            "supports": [
                "scripts/missions/final/mission_final_two.lua",
                "get_turn_limit",
                "missing_bomb_lifecycle",
                "final_cave_limit_writes_victory",
            ],
            "limitations": [
                "Replacement uncertainty can still make a projected plan unsafe to execute blindly."
            ],
        },
        {
            "id": "forced_zero_mech_failure_is_separate",
            "evidence_class": "inference",
            "claim": (
                "Only while the primary result remains pending does a forced "
                "state-0 evaluation call the exact Board:GetPawnCount binding "
                "with TEAM_MECH value 4. A zero result writes failure code 3; "
                "the ordinary state-2 limit victory has already committed code "
                "1 and does not enter this branch."
            ),
            "supports": [
                "get_pawn_count_binding",
                "team_mech_constant",
                "pawn_count_zero_contract",
                "forced_zero_mechs_writes_failure",
                "state_zero_forced_outcome_dispatch",
            ],
            "limitations": [
                "The map uses only the exact zero/nonzero contract needed by the outcome writer."
            ],
        },
        {
            "id": "campaign_result_join_is_exact",
            "evidence_class": "inference",
            "claim": (
                "The pinned BoardPlayer vtable getter returns +0x1900. The "
                "downstream campaign artifact maps code 3 to result 2 and "
                "other committed results, including code 1, to result 1; "
                "result 1 is the campaign-victory settlement route."
            ),
            "supports": [
                "outcome_getter_vtable_slot",
                "outcome_getter_body",
                "campaign_consumption",
                (
                    "data/observatory/native/"
                    "windows_build_13725832_31fe35265598_final_campaign_settlement.json"
                ),
            ],
            "limitations": [
                "Runtime filesystem success and a concrete run's written bytes remain separate evidence."
            ],
        },
        {
            "id": "solver_boundary",
            "evidence_class": "inference",
            "claim": (
                "No Rust simulator semantic change follows. Simulator v406 "
                "already applies the source-guaranteed +2 missing-bomb edge "
                "and stops at unresolved replacement materialization. The "
                "combat solver should continue to treat current-bomb loss as "
                "strategically severe and require a fresh live board before "
                "forecasting from the replacement."
            ),
            "supports": [
                "missing_bomb_delays_instead_of_directly_losing",
                "final_cave_limit_writes_victory",
            ],
            "limitations": [
                "This proof does not resolve native replacement timing or coordinates."
            ],
        },
    ]


def _unresolved() -> list[dict[str, str]]:
    return [
        {
            "id": "replacement_materialization",
            "question": (
                "On which runtime update and coordinate does a replacement "
                "BigBomb materialize after each loss?"
            ),
            "static_status": (
                "Lua guarantees AddBomb and +2 turns; concrete native callback "
                "timing and random_removal output are not predicted."
            ),
            "next_evidence": (
                "Use a bounded live replacement capture only if a solver "
                "mismatch requires concrete timing or coordinates."
            ),
        },
        {
            "id": "modified_outcome_paths",
            "question": (
                "Can debug, cheat, or modified callbacks write another "
                "secondary outcome or alter the reviewed guards?"
            ),
            "static_status": (
                "Ordinary shipped Final Cave reachability is pinned; modified "
                "outcome writers are outside this artifact."
            ),
            "next_evidence": "Treat modified paths as out of scope unless observed.",
        },
        {
            "id": "non_windows_equivalence",
            "question": "Do macOS/native builds implement the same outcome boundary?",
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
        "cave_countdown_outcome_proven": True,
        "bomb_is_direct_terminal_loss": False,
        "forced_zero_mech_failure_proven": True,
        "campaign_result_join_proven": True,
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
                "windows_build_13725832_31fe35265598_final_end_settlement.json"
            ),
            "artifact_sha256": SUPERSEDED_END_SETTLEMENT_ARTIFACT_SHA256,
            "resolved_gap_ids": ["cave_countdown_outcome"],
            "continuation": (
                "The earlier immutable map proves readiness and narrows the "
                "countdown result. This map continues through exact outcome "
                "storage, failure classification, presentation, and campaign "
                "result consumption."
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
        raise FinalCaveOutcomeError("content root is not a directory")
    for spec in SOURCE_SPECS:
        source = root / Path(spec["path"])
        try:
            resolved = source.resolve(strict=True)
        except OSError as exc:
            raise FinalCaveOutcomeError(
                f"missing Lua source {spec['path']}"
            ) from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise FinalCaveOutcomeError(
                f"Lua source escapes content root: {spec['path']}"
            ) from exc
        if source.is_symlink() or not resolved.is_file():
            raise FinalCaveOutcomeError(
                f"Lua source is not a regular non-symlink file: {spec['path']}"
            )
        raw = resolved.read_bytes()
        if (
            len(raw) != spec["size"]
            or hashlib.sha256(raw).hexdigest() != spec["sha256"]
        ):
            raise FinalCaveOutcomeError(
                f"Lua source identity differs: {spec['path']}"
            )


def build_final_cave_outcome_map(
    executable: Path,
    content_root: Path,
) -> dict[str, Any]:
    """Reproduce the exact-build Final Cave countdown outcome map."""
    try:
        data, image, digest = _load_executable(executable)
    except Exception as exc:
        raise FinalCaveOutcomeError(str(exc)) from exc
    if (
        digest != EXPECTED_EXECUTABLE_SHA256
        or len(data) != EXPECTED_EXECUTABLE_SIZE
        or image.architecture != "x86"
        or image.bits != 32
        or image.image_base != EXPECTED_IMAGE_BASE
    ):
        raise FinalCaveOutcomeError("executable identity differs")
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
            raise FinalCaveOutcomeError(str(exc)) from exc
        if hashlib.sha256(body).hexdigest() != spec["sha256"]:
            raise FinalCaveOutcomeError(
                f"region {spec['id']} bytes differ"
            )
        ranges[spec["id"]] = (spec["start"], spec["end"])
    try:
        decoded = _decode_x86_regions(image, data, ranges)
    except Exception as exc:
        raise FinalCaveOutcomeError(str(exc)) from exc

    for spec in STRING_ANCHOR_SPECS:
        text = spec["text"].encode("ascii") + b"\0"
        offset = image.rva_span_to_file_offset(spec["string_rva"], len(text))
        if offset is None or data[offset : offset + len(text)] != text:
            raise FinalCaveOutcomeError(
                f"string anchor {spec['id']} differs"
            )
        encoded = bytes.fromhex(spec["instruction_hex"])
        if _bytes_at(image, data, spec["reference_rva"], len(encoded)) != encoded:
            raise FinalCaveOutcomeError(
                f"string reference {spec['id']} differs"
            )
        instruction = decoded[spec["region_id"]].get(spec["reference_rva"])
        if instruction is None or instruction[1] != encoded:
            raise FinalCaveOutcomeError(
                f"string reference {spec['id']} is not an instruction"
            )
        expected_va = image.image_base + spec["string_rva"]
        if struct.pack("<I", expected_va) not in encoded:
            raise FinalCaveOutcomeError(
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
            raise FinalCaveOutcomeError(
                f"data pointer {spec['id']} target differs"
            )
        if spec["target_rva"] not in decoded[spec["target_region"]]:
            raise FinalCaveOutcomeError(
                f"data pointer {spec['id']} target is not an instruction"
            )

    region_by_id = {spec["id"]: spec for spec in REGION_SPECS}
    for spec in CONTROL_WINDOW_SPECS:
        encoded = bytes.fromhex(spec["instruction_hex"])
        start = spec["start_rva"]
        if _bytes_at(image, data, start, len(encoded)) != encoded:
            raise FinalCaveOutcomeError(
                f"control window {spec['id']} differs"
            )
        region = region_by_id[spec["region_id"]]
        if not (region["start"] <= start < start + len(encoded) <= region["end"]):
            raise FinalCaveOutcomeError(
                f"control window {spec['id']} escapes its region"
            )
        instructions = decoded[spec["region_id"]]
        cursor = start
        while cursor < start + len(encoded):
            instruction = instructions.get(cursor)
            if instruction is None:
                raise FinalCaveOutcomeError(
                    f"control window {spec['id']} crosses undecoded bytes"
                )
            cursor += len(instruction[1])
        if cursor != start + len(encoded):
            raise FinalCaveOutcomeError(
                f"control window {spec['id']} ends inside an instruction"
            )

    for spec in DIRECT_EDGE_SPECS:
        expected = bytes.fromhex(spec["instruction_hex"])
        instruction = decoded[spec["source_region"]].get(spec["from_rva"])
        if instruction is None or instruction[1] != expected:
            raise FinalCaveOutcomeError(
                f"direct edge {spec['id']} bytes differ"
            )
        if _direct_target(spec["from_rva"], expected) != spec["target_rva"]:
            raise FinalCaveOutcomeError(
                f"direct edge {spec['id']} target differs"
            )
        if spec["target_rva"] not in decoded[spec["target_region"]]:
            raise FinalCaveOutcomeError(
                f"direct edge {spec['id']} target is not an instruction"
            )

    pointers = {spec["id"]: spec for spec in DATA_POINTER_SPECS}
    windows = {spec["id"]: spec for spec in CONTROL_WINDOW_SPECS}
    edges = {spec["id"]: spec for spec in DIRECT_EDGE_SPECS}
    if not (
        pointers["state_case_two"]["target_rva"]
        < windows["state_two_nonforced_outcome_dispatch"]["start_rva"]
        < edges["state_two_to_outcome_dispatch"]["from_rva"] + 5
    ):
        raise FinalCaveOutcomeError("state-2 dispatch relation differs")
    if not (
        pointers["state_case_zero"]["target_rva"]
        < windows["state_zero_forced_outcome_dispatch"]["start_rva"]
        < edges["state_zero_to_outcome_dispatch"]["from_rva"] + 5
    ):
        raise FinalCaveOutcomeError("state-0 dispatch relation differs")
    if not (
        windows["ordinary_ready_writes_success"]["start_rva"]
        < edges["outcome_to_end_readiness"]["from_rva"]
        < windows["forced_zero_mechs_writes_failure"]["start_rva"]
        < edges["outcome_to_get_pawn_count"]["from_rva"] + 5
    ):
        raise FinalCaveOutcomeError("success/failure classification order differs")
    if not (
        windows["final_victory_route"]["start_rva"]
        < edges["outcome_to_mission_named_invoker"]["from_rva"]
        < edges["outcome_to_state_transition"]["from_rva"]
    ):
        raise FinalCaveOutcomeError("victory/MissionEnd/state-5 order differs")
    return _expected_shape()


def validate_final_cave_outcome_map_binding(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable reviewed fields without accessing the installation."""
    if not isinstance(value, Mapping):
        raise FinalCaveOutcomeError("outcome map must be an object")
    expected = _expected_shape()
    if dict(value) != expected:
        raise FinalCaveOutcomeError("outcome map fields differ")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": _canonical_sha256(value),
        "cave_countdown_outcome_proven": True,
        "bomb_is_direct_terminal_loss": False,
        "forced_zero_mech_failure_proven": True,
        "campaign_result_join_proven": True,
        "simulator_change_required": False,
    }


def validate_final_cave_outcome_map(
    executable: Path,
    content_root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the map and reject source, byte, address, or prose drift."""
    expected = build_final_cave_outcome_map(executable, content_root)
    if dict(value) != expected:
        raise FinalCaveOutcomeError(
            "outcome map differs from exact-build analysis"
        )
    result = validate_final_cave_outcome_map_binding(value)
    result["status"] = "verified"
    return result


def encode_final_cave_outcome_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
