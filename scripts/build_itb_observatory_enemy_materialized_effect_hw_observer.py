#!/usr/bin/env python3
"""Build and attest the dormant x86 enemy-materialized-effect HW observer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_itb_observatory_selected_queue_hw_observer as base
from src.observatory.enemy_record_selector_boundary import (
    EnemyRecordSelectorBoundaryError,
    validate_enemy_record_selector_boundary_map,
)
from src.observatory.enemy_skill_effect_boundary import (
    EnemySkillEffectBoundaryError,
    validate_enemy_skill_effect_boundary_map,
)


common = base.common
SOURCE = ROOT / "src" / "native" / "observatory_enemy_materialized_effect_hw_observer.c"
SELECTED_QUEUE_SOURCE = (
    ROOT / "src" / "native" / "observatory_selected_queue_hw_observer.c"
)
OBSERVER_VERSION = "observatory-enemy-materialized-effect-hw-observer/1"
EXPORT_NAME = "luaopen_itb_observatory_enemy_materialized_effect_hw_observer"
EXPECTED_EXECUTABLE_SHA256 = base.EXPECTED_EXECUTABLE_SHA256
EXPECTED_EXECUTABLE_SIZE = base.EXPECTED_EXECUTABLE_SIZE
EXPECTED_BUILD_ID = base.EXPECTED_BUILD_ID
EXPECTED_ARCHITECTURE = base.EXPECTED_ARCHITECTURE
EXPECTED_PE_TIMESTAMP = base.EXPECTED_PE_TIMESTAMP
EXPECTED_PE_SIZE_OF_IMAGE = base.EXPECTED_PE_SIZE_OF_IMAGE
EXPECTED_SELECTED_RVA = base.EXPECTED_SELECTED_RVA
EXPECTED_SELECTED_PREBYTES = base.EXPECTED_SELECTED_PREBYTES
EXPECTED_QUEUE_RVA = base.EXPECTED_QUEUE_RVA
EXPECTED_QUEUE_PREBYTES = base.EXPECTED_QUEUE_PREBYTES
EXPECTED_SELECTOR_RVA = 0x000F7DD0
EXPECTED_SELECTOR_PREBYTES = bytes.fromhex("558bec6aff68")
EXPECTED_SELECTOR_CONTROL_WINDOW_SIZE = 16
EXPECTED_SELECTOR_RELOCATION_OFFSETS = (6,)
EXPECTED_ORCHESTRATOR_CALL_RVA = 0x000F682E
EXPECTED_ORCHESTRATOR_CALL = bytes.fromhex("e89d150000")
EXPECTED_APPEND_CALL_RVA = 0x000F7BBE
EXPECTED_APPEND_CALL = bytes.fromhex("e88d080000")
EXPECTED_APPEND_TARGET_RVA = 0x000F8450
EXPECTED_MATERIALIZED_RVA = 0x00268323
EXPECTED_MATERIALIZED_PREBYTES = bytes.fromhex("8b4df464890d00000000")
EXPECTED_RNG_STATE_OWNER_RVA = 0x0038ED32
EXPECTED_RNG_STATE_OWNER_SIZE = 131
EXPECTED_RNG_STATE_OWNER_SHA256 = (
    "db0c599f49594fdb9856180cf4337d3b95a0bdd7b1d227c662e25caf2a76a12f"
)
EXPECTED_PREFERRED_IMAGE_BASE = 0x00400000
EXPECTED_RNG_STATE_OWNER_RELOCATION_OFFSETS = (6, 13, 66, 83, 110, 122)
EXPECTED_RECORD_SELECTOR_FILE_SHA256 = (
    "73ccd7972fd25f2f455173673fed19b2310f6039e58b8cf5118236ff4f8b2022"
)
EXPECTED_RECORD_SELECTOR_CANONICAL_SHA256 = (
    "1a7ef818d1e889849e68301cb3e94d2291bc908f98b7501c5033d390ba110bfc"
)
EXPECTED_SKILL_EFFECT_FILE_SHA256 = (
    "bd8fe003c19d8440569a7a6fb0ba1524481280e4f5dc31afdb5d93a2bc5d9c13"
)
EXPECTED_SKILL_EFFECT_CANONICAL_SHA256 = (
    "d3502ffc37ce5fb0a685e6df3587173f2076f0701e944dbd4888ee0f46711bdd"
)
EXPECTED_SELECTED_QUEUE_SOURCE_SHA256 = (
    "c57293d35e4bba11edfc1b66233368fb32a3ce51c04c01aea681a9024c3b2be6"
)
EXPECTED_DR7_ARM = 0x00000015
EXPECTED_DR7_AFTER_SELECTOR = 0x00000014
EXPECTED_DR7_WAIT_MATERIALIZED = 0x00000050
EXPECTED_DR7_QUEUE_ONLY = 0x00000010
RNG_STATE_OFFSET = 0x18
RECORD_CAPACITY = 256


class ObserverBuildError(RuntimeError):
    """Raised when a materialized_effect observer build cannot be trusted."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--native-boundaries", type=Path, required=True)
    parser.add_argument("--rng-return-map", type=Path, required=True)
    parser.add_argument("--record-selector-boundary", type=Path, required=True)
    parser.add_argument("--skill-effect-boundary", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _direct_call_target(call_rva: int, data: bytes) -> int:
    if len(data) != 5 or data[0] != 0xE8:
        raise ObserverBuildError(f"RVA 0x{call_rva:08x} is not a rel32 call")
    (relative,) = struct.unpack_from("<i", data, 1)
    return (call_rva + 5 + relative) & 0xFFFFFFFF


def _base_relocations(data: bytes, image: common.PEImage) -> set[int]:
    if len(data) < 0x40:
        raise ObserverBuildError("PE image is truncated before relocations")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    optional = pe_offset + 24
    if optional + 144 > len(data) or struct.unpack_from("<H", data, optional)[0] != 0x10B:
        raise ObserverBuildError("PE32 optional header is invalid")
    directory_count = struct.unpack_from("<I", data, optional + 92)[0]
    if directory_count <= 5:
        raise ObserverBuildError("PE image has no base-relocation directory")
    relocation_rva, relocation_size = struct.unpack_from(
        "<II", data, optional + 96 + 5 * 8
    )
    if relocation_rva == 0 or relocation_size < 8:
        raise ObserverBuildError("PE base-relocation directory is empty")
    offset = image.rva_to_offset(relocation_rva, relocation_size)
    cursor = offset
    end = offset + relocation_size
    relocations: set[int] = set()
    while cursor < end:
        if cursor + 8 > end:
            raise ObserverBuildError("PE base-relocation block is truncated")
        page_rva, block_size = struct.unpack_from("<II", data, cursor)
        if page_rva == 0 and block_size == 0:
            break
        if block_size < 8 or block_size % 2 or cursor + block_size > end:
            raise ObserverBuildError("PE base-relocation block is malformed")
        for entry_offset in range(cursor + 8, cursor + block_size, 2):
            entry = struct.unpack_from("<H", data, entry_offset)[0]
            relocation_type = entry >> 12
            if relocation_type == 3:
                relocations.add(page_rva + (entry & 0x0FFF))
            elif relocation_type != 0:
                raise ObserverBuildError(
                    f"unreviewed PE relocation type: {relocation_type}"
                )
        cursor += block_size
    return relocations


def _validate_inputs(args: argparse.Namespace) -> dict[str, Any]:
    try:
        identities = base._validate_inputs(
            args.executable, args.native_boundaries, args.rng_return_map
        )
    except (base.ObserverBuildError, OSError) as exc:
        raise ObserverBuildError(f"pinned observer input validation failed: {exc}") from exc

    executable: bytes = identities["executable"]
    image = identities["image"]
    selector_offset = image.rva_to_offset(
        EXPECTED_SELECTOR_RVA, len(EXPECTED_SELECTOR_PREBYTES)
    )
    selector = executable[
        selector_offset : selector_offset + len(EXPECTED_SELECTOR_PREBYTES)
    ]
    if selector != EXPECTED_SELECTOR_PREBYTES:
        raise ObserverBuildError("record-selector entry prebytes differ")

    materialized_offset = image.rva_to_offset(
        EXPECTED_MATERIALIZED_RVA, len(EXPECTED_MATERIALIZED_PREBYTES)
    )
    materialized = executable[
        materialized_offset : materialized_offset
        + len(EXPECTED_MATERIALIZED_PREBYTES)
    ]
    if materialized != EXPECTED_MATERIALIZED_PREBYTES:
        raise ObserverBuildError("materialized-effect seam prebytes differ")

    owner_offset = image.rva_to_offset(
        EXPECTED_RNG_STATE_OWNER_RVA, EXPECTED_RNG_STATE_OWNER_SIZE
    )
    owner = executable[owner_offset : owner_offset + EXPECTED_RNG_STATE_OWNER_SIZE]
    if _sha256(owner) != EXPECTED_RNG_STATE_OWNER_SHA256:
        raise ObserverBuildError("RNG state-owner bytes differ")
    relocations = _base_relocations(executable, image)
    selector_relocations = tuple(
        sorted(
            rva - EXPECTED_SELECTOR_RVA
            for rva in relocations
            if EXPECTED_SELECTOR_RVA
            <= rva
            < EXPECTED_SELECTOR_RVA + EXPECTED_SELECTOR_CONTROL_WINDOW_SIZE
        )
    )
    if selector_relocations != EXPECTED_SELECTOR_RELOCATION_OFFSETS:
        raise ObserverBuildError("selector control-window relocation offsets differ")
    owner_relocations = tuple(
        sorted(
            rva - EXPECTED_RNG_STATE_OWNER_RVA
            for rva in relocations
            if EXPECTED_RNG_STATE_OWNER_RVA
            <= rva
            < EXPECTED_RNG_STATE_OWNER_RVA + EXPECTED_RNG_STATE_OWNER_SIZE
        )
    )
    if owner_relocations != EXPECTED_RNG_STATE_OWNER_RELOCATION_OFFSETS:
        raise ObserverBuildError("RNG state-owner relocation offsets differ")
    for relocation_offset in owner_relocations:
        absolute = struct.unpack_from("<I", owner, relocation_offset)[0]
        if not EXPECTED_PREFERRED_IMAGE_BASE <= absolute < (
            EXPECTED_PREFERRED_IMAGE_BASE + EXPECTED_PE_SIZE_OF_IMAGE
        ):
            raise ObserverBuildError("RNG state-owner relocation value is not image-local")

    orchestrator_offset = image.rva_to_offset(
        EXPECTED_ORCHESTRATOR_CALL_RVA, len(EXPECTED_ORCHESTRATOR_CALL)
    )
    orchestrator_call = executable[
        orchestrator_offset : orchestrator_offset + len(EXPECTED_ORCHESTRATOR_CALL)
    ]
    if (
        orchestrator_call != EXPECTED_ORCHESTRATOR_CALL
        or _direct_call_target(EXPECTED_ORCHESTRATOR_CALL_RVA, orchestrator_call)
        != EXPECTED_SELECTOR_RVA
    ):
        raise ObserverBuildError("orchestrator no longer calls the selector entry")

    append_offset = image.rva_to_offset(
        EXPECTED_APPEND_CALL_RVA, len(EXPECTED_APPEND_CALL)
    )
    append_call = executable[
        append_offset : append_offset + len(EXPECTED_APPEND_CALL)
    ]
    if (
        append_call != EXPECTED_APPEND_CALL
        or _direct_call_target(EXPECTED_APPEND_CALL_RVA, append_call)
        != EXPECTED_APPEND_TARGET_RVA
    ):
        raise ObserverBuildError("candidate loop no longer calls the record append helper")

    for rva in (
        EXPECTED_SELECTOR_RVA,
        EXPECTED_SELECTED_RVA,
        EXPECTED_QUEUE_RVA,
        EXPECTED_MATERIALIZED_RVA,
        EXPECTED_RNG_STATE_OWNER_RVA,
    ):
        if not image.section_for_rva(rva).executable:
            raise ObserverBuildError(f"pinned RVA 0x{rva:08x} is not executable")

    try:
        record_map, record_bytes = common._load_json(
            args.record_selector_boundary, "enemy record-selector boundary"
        )
        if _sha256(record_bytes) != EXPECTED_RECORD_SELECTOR_FILE_SHA256:
            raise ObserverBuildError("enemy record-selector artifact file hash differs")
        if _canonical_json(record_map) != record_bytes:
            raise ObserverBuildError("enemy record-selector artifact is not canonical JSON")
        binding = validate_enemy_record_selector_boundary_map(
            args.executable, record_map
        )
    except (EnemyRecordSelectorBoundaryError, OSError) as exc:
        raise ObserverBuildError(
            f"enemy record-selector boundary validation failed: {exc}"
        ) from exc
    if binding.get("artifact_sha256") != EXPECTED_RECORD_SELECTOR_CANONICAL_SHA256:
        raise ObserverBuildError("enemy record-selector canonical hash differs")

    try:
        skill_effect_map, skill_effect_bytes = common._load_json(
            args.skill_effect_boundary,
            "enemy SkillEffect boundary",
        )
        if _sha256(skill_effect_bytes) != EXPECTED_SKILL_EFFECT_FILE_SHA256:
            raise ObserverBuildError("enemy SkillEffect artifact file hash differs")
        if _canonical_json(skill_effect_map) != skill_effect_bytes:
            raise ObserverBuildError(
                "enemy SkillEffect artifact is not canonical JSON"
            )
        skill_effect_binding = validate_enemy_skill_effect_boundary_map(
            args.executable,
            skill_effect_map,
        )
    except (EnemySkillEffectBoundaryError, OSError) as exc:
        raise ObserverBuildError(
            f"enemy SkillEffect boundary validation failed: {exc}"
        ) from exc
    if (
        skill_effect_binding.get("artifact_sha256")
        != EXPECTED_SKILL_EFFECT_CANONICAL_SHA256
    ):
        raise ObserverBuildError("enemy SkillEffect canonical hash differs")

    selected_queue_source = common._stable_bytes(
        SELECTED_QUEUE_SOURCE, "selected/queue observer source dependency"
    )
    if _sha256(selected_queue_source) != EXPECTED_SELECTED_QUEUE_SOURCE_SHA256:
        raise ObserverBuildError("selected/queue source dependency differs")

    return {
        **identities,
        "selector_prebytes": selector,
        "materialized_prebytes": materialized,
        "selector_relocation_offsets": selector_relocations,
        "rng_state_owner_bytes": owner,
        "rng_state_owner_relocation_offsets": owner_relocations,
        "record_selector_file_sha256": _sha256(record_bytes),
        "record_selector_canonical_sha256": binding["artifact_sha256"],
        "skill_effect_file_sha256": _sha256(skill_effect_bytes),
        "skill_effect_canonical_sha256": skill_effect_binding[
            "artifact_sha256"
        ],
        "selected_queue_source_sha256": _sha256(selected_queue_source),
    }


def _hardware_breakpoint_plan(
    source_sha256: str, identities: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "observatory_enemy_materialized_effect_hardware_breakpoint_plan",
        "observer_version": OBSERVER_VERSION,
        "identity": {
            "platform": "windows",
            "architecture": EXPECTED_ARCHITECTURE,
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "inventory_sha256": identities["inventory_canonical_sha256"],
            "boundary_map_sha256": identities["boundary_map_canonical_sha256"],
            "rng_return_map_sha256": identities["return_map_sha256"],
            "record_selector_boundary_sha256": identities[
                "record_selector_canonical_sha256"
            ],
            "skill_effect_boundary_sha256": identities[
                "skill_effect_canonical_sha256"
            ],
            "selected_queue_source_sha256": identities[
                "selected_queue_source_sha256"
            ],
            "source_sha256": source_sha256,
        },
        "breakpoints": [
            {
                "slot": "DR0",
                "kind": "x86_execute_length_1_current_thread_only",
                "semantic_boundary": "complete_ordered_record_vector_before_selector_rng",
                "rva": f"0x{EXPECTED_SELECTOR_RVA:08x}",
                "expected_prebytes_hex": EXPECTED_SELECTOR_PREBYTES.hex(),
                "expected_prebytes_sha256": _sha256(EXPECTED_SELECTOR_PREBYTES),
                "live_identity_comparison": (
                    "six relocation-free entry bytes; the full selector region "
                    "is pinned by the executable and record-selector hashes"
                ),
                "register_contract": (
                    "ECX=selector context; vector begin/end/capacity at +08/+0c/+10; "
                    "AI=ECX-0x14; Pawn=[AI+4]"
                ),
            },
            {
                "slot": "DR1",
                "kind": "x86_execute_length_1_current_thread_only",
                "semantic_boundary": "selected_record_after_copy",
                "rva": f"0x{EXPECTED_SELECTED_RVA:08x}",
                "expected_prebytes_hex": EXPECTED_SELECTED_PREBYTES.hex(),
                "expected_prebytes_sha256": _sha256(EXPECTED_SELECTED_PREBYTES),
                "register_contract": "EBX=AI; selected record at AI+0x50; Pawn=[EBX+4]",
            },
            {
                "slot": "DR3",
                "kind": "x86_execute_length_1_current_thread_only",
                "semantic_boundary": (
                    "selected_skill_effect_after_annotation_and_both_"
                    "native_postprocess_passes"
                ),
                "rva": f"0x{EXPECTED_MATERIALIZED_RVA:08x}",
                "expected_prebytes_hex": EXPECTED_MATERIALIZED_PREBYTES.hex(),
                "expected_prebytes_sha256": _sha256(
                    EXPECTED_MATERIALIZED_PREBYTES
                ),
                "arm_timing": "enabled only after the selected-record copy",
                "register_contract": (
                    "EDI=Skill; materialized SkillEffect cache at EDI+0x18"
                ),
            },
            {
                "slot": "DR2",
                "kind": "x86_execute_length_1_current_thread_only",
                "semantic_boundary": "queued_action_stable_read",
                "rva": f"0x{EXPECTED_QUEUE_RVA:08x}",
                "expected_prebytes_hex": EXPECTED_QUEUE_PREBYTES.hex(),
                "expected_prebytes_sha256": _sha256(EXPECTED_QUEUE_PREBYTES),
                "register_contract": "ESI=Pawn",
            },
        ],
        "rng_state_contract": {
            "owner_rva": f"0x{EXPECTED_RNG_STATE_OWNER_RVA:08x}",
            "owner_region_size": EXPECTED_RNG_STATE_OWNER_SIZE,
            "owner_region_sha256": EXPECTED_RNG_STATE_OWNER_SHA256,
            "preferred_image_base": f"0x{EXPECTED_PREFERRED_IMAGE_BASE:08x}",
            "base_relocation_offsets": list(
                EXPECTED_RNG_STATE_OWNER_RELOCATION_OFFSETS
            ),
            "live_identity_comparison": (
                "all non-relocation bytes exact; each HIGHLOW dword equals "
                "the pinned file dword plus the loaded-image delta"
            ),
            "state_offset": f"0x{RNG_STATE_OFFSET:02x}",
            "owner_called_once_on_arm_thread_before_debug_register_arm": True,
            "state_read_before_selector_and_after_selected_copy": True,
        },
        "debug_register_contract": {
            "arm_rejects_any_nonzero_dr0_dr1_dr2_dr3_or_dr7": True,
            "arm_dr7_exact": f"0x{EXPECTED_DR7_ARM:08x}",
            "after_selector_dr7_exact": f"0x{EXPECTED_DR7_AFTER_SELECTOR:08x}",
            "wait_materialized_dr7_exact": (
                f"0x{EXPECTED_DR7_WAIT_MATERIALIZED:08x}"
            ),
            "queue_only_dr7_exact": f"0x{EXPECTED_DR7_QUEUE_ONLY:08x}",
            "transition": "private_RaiseException_handled_by_VEH",
            "queue_commit_clears_dr0_dr1_dr2_dr3_dr6_dr7": True,
            "finish_requires_proven_clear_state": True,
        },
        "data_contract": {
            "record_size_bytes": 24,
            "record_fields": [
                "destination_x",
                "destination_y",
                "target_x",
                "target_y",
                "target_score",
                "positioning_score",
            ],
            "ordered_vector_copied_before_first_selector_instruction": True,
            "selected_record_and_queue_require_same_pawn": True,
            "materialized_effect_requires_selected_origin_and_target": True,
            "materialized_effect_fields": [
                "effect_count",
                "queued_count",
                "owner_id",
                "skill_source_tag",
                "origin",
                "selected_target",
                "queued_loc",
                "queued_damage",
                "queued_animation",
                "queued_private_origin",
                "queued_private_source_tag",
                "queued_boost_marker",
                "native_skill_key",
            ],
            "addresses_or_pointers_published": False,
        },
        "limits": {
            "candidate_capacity": RECORD_CAPACITY,
            "selected_capacity": 1,
            "queue_capacity": 1,
            "materialized_effect_capacity": 1,
            "thread_capacity": 1,
        },
        "mutation_contract": {
            "executable_bytes_modified": False,
            "page_protection_changed": False,
            "gateway_allocated": False,
            "detour_installed": False,
        },
        "hot_contract": {
            "allocation": False,
            "file_io": False,
            "lua_or_game_calls": False,
            "locks": False,
            "clocks": False,
            "windows_api_calls": False,
            "x87_mmx_sse_avx_state_changes": False,
            "addresses_or_pointers_published": False,
        },
    }


def _c_bytes(name: str, data: bytes) -> str:
    values = ", ".join(f"0x{value:02x}" for value in data)
    return f"static const unsigned char {name}[{len(data)}] = {{{values}}};"


def _generated_include(identities: dict[str, Any], plan_sha256: str) -> bytes:
    digest = bytes.fromhex(EXPECTED_EXECUTABLE_SHA256)
    text = f"""/* Generated; do not edit or install independently. */
#ifndef OBSERVATORY_SELECTED_QUEUE_HW_BUILD_INC
#define OBSERVATORY_SELECTED_QUEUE_HW_BUILD_INC

#define OBS_BUILD_ID \"{EXPECTED_BUILD_ID}\"
#define OBS_EXECUTABLE_SHA256 \"{EXPECTED_EXECUTABLE_SHA256}\"
#define OBS_EXECUTABLE_SIZE {EXPECTED_EXECUTABLE_SIZE}L
#define OBS_PE_TIMESTAMP 0x{EXPECTED_PE_TIMESTAMP:08x}u
#define OBS_PE_SIZE_OF_IMAGE 0x{EXPECTED_PE_SIZE_OF_IMAGE:08x}u
#define OBS_INVENTORY_SHA256 \"{identities['inventory_canonical_sha256']}\"
#define OBS_BOUNDARY_MAP_SHA256 \"{identities['boundary_map_canonical_sha256']}\"
#define OBS_RNG_RETURN_MAP_SHA256 \"{identities['return_map_sha256']}\"
#define OBS_RECORD_SELECTOR_BOUNDARY_SHA256 \"{identities['record_selector_canonical_sha256']}\"
#define OBS_SKILL_EFFECT_BOUNDARY_SHA256 \"{identities['skill_effect_canonical_sha256']}\"
#define OBS_SELECTED_QUEUE_SOURCE_SHA256 \"{identities['selected_queue_source_sha256']}\"
#define OBS_HW_PLAN_SHA256 \"{plan_sha256}\"
#define OBS_SELECTED_RVA 0x{EXPECTED_SELECTED_RVA:08x}u
#define OBS_SELECTED_RVA_TEXT \"0x{EXPECTED_SELECTED_RVA:08x}\"
#define OBS_SELECTED_PREBYTE_SIZE {len(EXPECTED_SELECTED_PREBYTES)}u
#define OBS_SELECTED_PREBYTES_SHA256 \"{_sha256(EXPECTED_SELECTED_PREBYTES)}\"
#define OBS_QUEUE_RVA 0x{EXPECTED_QUEUE_RVA:08x}u
#define OBS_QUEUE_RVA_TEXT \"0x{EXPECTED_QUEUE_RVA:08x}\"
#define OBS_QUEUE_PREBYTE_SIZE {len(EXPECTED_QUEUE_PREBYTES)}u
#define OBS_QUEUE_PREBYTES_SHA256 \"{_sha256(EXPECTED_QUEUE_PREBYTES)}\"
#define OBS_MATERIALIZED_RVA 0x{EXPECTED_MATERIALIZED_RVA:08x}u
#define OBS_MATERIALIZED_RVA_TEXT \"0x{EXPECTED_MATERIALIZED_RVA:08x}\"
#define OBS_MATERIALIZED_PREBYTE_SIZE {len(EXPECTED_MATERIALIZED_PREBYTES)}u
#define OBS_MATERIALIZED_PREBYTES_SHA256 \"{_sha256(EXPECTED_MATERIALIZED_PREBYTES)}\"
#define OBS_MATERIALIZED_EFFECT_SELECTOR_RVA 0x{EXPECTED_SELECTOR_RVA:08x}u
#define OBS_MATERIALIZED_EFFECT_SELECTOR_RVA_TEXT \"0x{EXPECTED_SELECTOR_RVA:08x}\"
#define OBS_MATERIALIZED_EFFECT_SELECTOR_PREBYTE_SIZE {len(EXPECTED_SELECTOR_PREBYTES)}u
#define OBS_MATERIALIZED_EFFECT_SELECTOR_PREBYTES_SHA256 \"{_sha256(EXPECTED_SELECTOR_PREBYTES)}\"
#define OBS_RNG_STATE_OWNER_RVA 0x{EXPECTED_RNG_STATE_OWNER_RVA:08x}u
#define OBS_RNG_STATE_OWNER_RVA_TEXT \"0x{EXPECTED_RNG_STATE_OWNER_RVA:08x}\"
#define OBS_RNG_STATE_OWNER_SIZE {EXPECTED_RNG_STATE_OWNER_SIZE}u
#define OBS_RNG_STATE_OWNER_SHA256 \"{EXPECTED_RNG_STATE_OWNER_SHA256}\"
#define OBS_PREFERRED_IMAGE_BASE 0x{EXPECTED_PREFERRED_IMAGE_BASE:08x}u
#define OBS_RNG_STATE_OWNER_RELOCATION_COUNT {len(EXPECTED_RNG_STATE_OWNER_RELOCATION_OFFSETS)}u

{_c_bytes('OBS_EXECUTABLE_SHA256_BYTES', digest)}
{_c_bytes('OBS_SELECTED_PREBYTES', EXPECTED_SELECTED_PREBYTES)}
{_c_bytes('OBS_QUEUE_PREBYTES', EXPECTED_QUEUE_PREBYTES)}
{_c_bytes('OBS_MATERIALIZED_PREBYTES', EXPECTED_MATERIALIZED_PREBYTES)}
{_c_bytes('OBS_MATERIALIZED_EFFECT_SELECTOR_PREBYTES', EXPECTED_SELECTOR_PREBYTES)}
{_c_bytes('OBS_RNG_STATE_OWNER_BYTES', identities['rng_state_owner_bytes'])}
static const size_t OBS_RNG_STATE_OWNER_RELOCATION_OFFSETS[
    OBS_RNG_STATE_OWNER_RELOCATION_COUNT
] = {{{', '.join(f'{value}u' for value in EXPECTED_RNG_STATE_OWNER_RELOCATION_OFFSETS)}}};

#endif
"""
    return text.encode("ascii")


def _attest_source(source: bytes) -> dict[str, Any]:
    try:
        value = source.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise ObserverBuildError("observer source must remain ASCII") from exc
    if value.count("__declspec(dllexport)") != 1 or value.count(EXPORT_NAME) != 1:
        raise ObserverBuildError("observer source must expose exactly one Lua opener")
    if "DllMain" in value:
        raise ObserverBuildError("observer source must have no loader-time behavior")
    dependency_include = '#include "observatory_selected_queue_hw_observer.c"'
    if value.count(dependency_include) != 1:
        raise ObserverBuildError("selected/queue source dependency include differs")
    if (
        "#define dllexport noinline" not in value
        or "observatory_selected_queue_base_opener_unexported" not in value
    ):
        raise ObserverBuildError("historical opener export neutralization differs")
    start = value.find("/* MATERIALIZED_EFFECT_HOT_PATH_BEGIN")
    end = value.find("/* MATERIALIZED_EFFECT_HOT_PATH_END */")
    if start < 0 or end <= start:
        raise ObserverBuildError("materialized_effect hot-path markers are missing")
    hot = value[start:end]
    banned_hot = (
        "HeapAlloc",
        "VirtualAlloc",
        "VirtualProtect",
        "WriteProcessMemory",
        "CreateFile",
        "ReadFile",
        "lua_",
        "luaL_",
        "RaiseException",
        "GetCurrentThreadId",
        "QueryPerformance",
        "EnterCriticalSection",
        "malloc",
        "free(",
        "fopen",
    )
    found = [name for name in banned_hot if name in hot]
    if found:
        raise ObserverBuildError(f"observer hot path contains cold API text: {found}")
    required = (
        '#pragma code_seg(push, ".obshot")',
        "observer_enemy_materialized_effect_veh",
        "context->Dr0 = (DWORD)g_materialized_effect_selector_address",
        "context->Dr1 = (DWORD)g_selected_address",
        "context->Dr2 = (DWORD)g_queue_address",
        "context->Dr3 = (DWORD)g_materialized_effect_address",
        "context->Dr7 = MATERIALIZED_EFFECT_DR7_ARM",
        "context->Dr7 = MATERIALIZED_EFFECT_DR7_AFTER_SELECTOR",
        "context->Dr7 = MATERIALIZED_EFFECT_DR7_WAIT_MATERIALIZED",
        "context->Dr7 = MATERIALIZED_EFFECT_DR7_QUEUE_ONLY",
        "g_materialized_effect_rng_before",
        "g_materialized_effect_rng_after",
        "g_materialized_effect_candidates[index]",
        "g_materialized_effect_record",
        "materialized_effect_copy_string",
        "context->Dr0 = 0",
        "context->Dr1 = 0",
        "context->Dr2 = 0",
        "context->Dr7 = 0",
        "context->EFlags |= OBS_EFLAGS_RF",
        "hot_range_readable",
    )
    if any(item not in hot for item in required):
        raise ObserverBuildError("observer materialized_effect VEH source contract differs")
    if (
        value.count("materialized_effect_relocated_region_equal(") != 3
        or "actual_value != expected_value + delta" not in value
        or "OBS_RNG_STATE_OWNER_RELOCATION_OFFSETS[index]" not in value
    ):
        raise ObserverBuildError("relocation-normalized owner identity check differs")
    banned_source = (
        "WriteProcessMemory",
        "CreateRemoteThread",
        "OpenProcess",
        "VirtualProtect",
        "FlushInstructionCache",
        "DebugActiveProcess",
    )
    found_source = [name for name in banned_source if name in value]
    if found_source:
        raise ObserverBuildError(
            f"observer source contains executable-mutation surface: {found_source}"
        )
    return {
        "source_sha256": _sha256(source),
        "hot_source_sha256": _sha256(hot.encode("ascii")),
        "selected_queue_dependency_include_present": True,
        "historical_opener_export_neutralized": True,
        "rng_owner_relocation_normalization_present": True,
        "executable_mutation_api_text_absent": True,
        "private_debug_register_transition_present": True,
        "fixed_candidate_ring_present": "g_materialized_effect_candidates[OBS_RECORD_CAP]"
        in value,
    }


def _normalize_output(value: str, temporary_root: Path) -> str:
    result = value.strip()
    for spelling, replacement in (
        (str(temporary_root), "<temporary-build>"),
        (temporary_root.as_posix(), "<temporary-build>"),
        (str(ROOT), "<source-root>"),
        (ROOT.as_posix(), "<source-root>"),
    ):
        result = result.replace(spelling, replacement)
    return result


def _attest_hot_section(data: bytes, image: common.PEImage) -> dict[str, Any]:
    attestation = base._attest_hot_section(data, image)
    try:
        import capstone
        import capstone.x86_const as x86_const
    except ImportError as exc:
        raise ObserverBuildError("Capstone 5.0.7 is required for VEH proof") from exc
    if capstone.__version__ != "5.0.7":
        raise ObserverBuildError(f"unreviewed Capstone version: {capstone.__version__}")
    matches = [section for section in image.sections if section.name == ".obshot"]
    if len(matches) != 1:
        raise ObserverBuildError("compiled observer needs one .obshot section")
    section = matches[0]
    raw = data[section.raw_offset : section.raw_offset + section.virtual_size]
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    state_groups = tuple(
        value
        for name, value in vars(x86_const).items()
        if name.startswith((
            "X86_GRP_FPU",
            "X86_GRP_MMX",
            "X86_GRP_SSE",
            "X86_GRP_AVX",
        ))
        and type(value) is int
    )
    state_instructions = [
        f"0x{instruction.address:08x}:{instruction.mnemonic}"
        for instruction in decoder.disasm(raw, image.image_base + section.virtual_address)
        if any(instruction.group(group) for group in state_groups)
    ]
    if state_instructions:
        raise ObserverBuildError(
            f"compiled VEH changes x87/MMX/SSE/AVX state: {state_instructions}"
        )
    attestation["x87_mmx_sse_avx_instruction_count"] = 0
    return attestation


def _compile_once(environment: dict[str, str], include_data: bytes) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="itb_observatory_enemy_materialized_effect_hw_") as raw:
        temporary = Path(raw)
        (temporary / "observatory_selected_queue_hw_build.inc").write_bytes(
            include_data
        )
        dll = temporary / "itb_observatory_enemy_materialized_effect_hw_observer.dll"
        obj = temporary / "observatory_enemy_materialized_effect_hw_observer.obj"
        cl = shutil.which("cl.exe", path=environment.get("PATH"))
        linker = shutil.which("link.exe", path=environment.get("PATH"))
        if cl is None or linker is None:
            raise ObserverBuildError("MSVC compiler or linker disappeared")
        compile_command = [
            cl,
            "/nologo",
            "/c",
            "/TC",
            "/O2",
            "/Oi",
            "/Ob3",
            "/Oy",
            "/W4",
            "/WX",
            "/GS-",
            "/Gy",
            "/Zl",
            f"/I{temporary}",
            f"/Fo{obj}",
            str(SOURCE),
        ]
        compiled = subprocess.run(
            compile_command,
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if compiled.returncode != 0:
            detail = (compiled.stderr or compiled.stdout).strip()
            raise ObserverBuildError(
                "MSVC compilation failed" + (f": {detail}" if detail else "")
            )
        link_command = [
            linker,
            "/NOLOGO",
            "/DLL",
            "/NOENTRY",
            "/NODEFAULTLIB",
            f"/OUT:{dll}",
            "/INCREMENTAL:NO",
            "/Brepro",
            "/OPT:REF",
            "/OPT:ICF",
            str(obj),
            "kernel32.lib",
            "bcrypt.lib",
        ]
        linked = subprocess.run(
            link_command,
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if linked.returncode != 0:
            detail = (linked.stderr or linked.stdout).strip()
            raise ObserverBuildError(
                "MSVC link failed" + (f": {detail}" if detail else "")
            )
        compiler_stdout = _normalize_output(
            "\n".join(
                item for item in (compiled.stdout, linked.stdout) if item.strip()
            ),
            temporary,
        )
        module = common._stable_bytes(dll, "compiled observer")
    image = common._parse_pe(module)
    if image.machine != 0x014C or image.entry_point != 0:
        raise ObserverBuildError("compiled observer is not an inert x86 DLL")
    exports = common._pe_exports(module, image)
    if exports != [EXPORT_NAME]:
        raise ObserverBuildError(f"compiled observer exports differ: {exports}")
    imports = sorted(name.lower() for name in common._pe_imports(module, image))
    if not set(imports) <= {"bcrypt.dll", "kernel32.dll"} or (
        "kernel32.dll" not in imports
    ):
        raise ObserverBuildError(f"compiled observer imports differ: {imports}")
    mutation_names = (
        b"VirtualProtect",
        b"WriteProcessMemory",
        b"CreateRemoteThread",
        b"FlushInstructionCache",
        b"DebugActiveProcess",
    )
    if any(name in module for name in mutation_names):
        raise ObserverBuildError("compiled observer imports executable-mutation APIs")
    hot = _attest_hot_section(module, image)
    return {
        "module": module,
        "module_sha256": _sha256(module),
        "exports": exports,
        "imports": imports,
        "compiler_stdout": compiler_stdout,
        "machine_attestation": {
            "loader_entry_absent": True,
            "pe_entry_point_rva": "0x00000000",
            "veh": hot,
            "executable_mutation_api_imports_absent": True,
        },
    }


def _write_create_only(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ObserverBuildError(f"immutable output already exists: {path.name}") from exc


def build_observer(args: argparse.Namespace) -> int:
    identities = _validate_inputs(args)
    source = common._stable_bytes(SOURCE, "observer source")
    source_attestation = _attest_source(source)
    source_sha = _sha256(source)
    plan = _hardware_breakpoint_plan(source_sha, identities)
    plan_data = _canonical_json(plan)
    plan_sha = _sha256(plan_data)
    include_data = _generated_include(identities, plan_sha)
    try:
        environment, compiler = common._msvc_environment()
    except (common.ObserverBuildError, OSError, subprocess.SubprocessError) as exc:
        raise ObserverBuildError(str(exc)) from exc
    first = _compile_once(environment, include_data)
    second = _compile_once(environment, include_data)
    for field in (
        "module",
        "module_sha256",
        "exports",
        "imports",
        "compiler_stdout",
        "machine_attestation",
    ):
        if first[field] != second[field]:
            raise ObserverBuildError(f"independent reproducibility builds differ: {field}")
    module = first["module"]
    module_sha = first["module_sha256"]
    output_root = Path(os.path.abspath(args.output_root.expanduser()))
    stem = f"itb_observatory_enemy_materialized_effect_hw_observer_{module_sha}"
    module_path = output_root / f"{stem}.dll"
    receipt_path = output_root / f"{stem}.dll.receipt.json"
    plan_path = output_root / (
        f"windows_build_{EXPECTED_BUILD_ID}_enemy_materialized_effect_hw_plan_{plan_sha}.json"
    )
    receipt = {
        "schema_version": 1,
        "kind": "observatory_enemy_materialized_effect_hw_observer_build",
        "observer_version": OBSERVER_VERSION,
        "module_filename": module_path.name,
        "module_sha256": module_sha,
        "module_size": len(module),
        "architecture": EXPECTED_ARCHITECTURE,
        "export_name": EXPORT_NAME,
        "exports": first["exports"],
        "imports": first["imports"],
        "source_path": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": source_sha,
        "selected_queue_source_path": SELECTED_QUEUE_SOURCE.relative_to(
            ROOT
        ).as_posix(),
        "selected_queue_source_sha256": identities[
            "selected_queue_source_sha256"
        ],
        "generated_include_sha256": _sha256(include_data),
        "source_attestation": source_attestation,
        "machine_attestation": first["machine_attestation"],
        "compiler": compiler,
        "compiler_stdout": first["compiler_stdout"],
        "reproducibility": {
            "independent_build_count": 2,
            "module_bytes_identical": True,
            "attestations_identical": True,
        },
        "compile_flags": [
            "/c",
            "/TC",
            "/O2",
            "/Oi",
            "/Ob3",
            "/Oy",
            "/W4",
            "/WX",
            "/GS-",
            "/Gy",
            "/Zl",
            "/DLL",
            "/NOENTRY",
            "/NODEFAULTLIB",
            "/INCREMENTAL:NO",
            "/Brepro",
            "/OPT:REF",
            "/OPT:ICF",
        ],
        "build_id": EXPECTED_BUILD_ID,
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        "executable_size": EXPECTED_EXECUTABLE_SIZE,
        "inventory_canonical_sha256": identities["inventory_canonical_sha256"],
        "boundary_map_canonical_sha256": identities[
            "boundary_map_canonical_sha256"
        ],
        "boundary_map_file_sha256": identities["boundary_map_file_sha256"],
        "rng_return_map_sha256": identities["return_map_sha256"],
        "record_selector_boundary_canonical_sha256": identities[
            "record_selector_canonical_sha256"
        ],
        "record_selector_boundary_file_sha256": identities[
            "record_selector_file_sha256"
        ],
        "skill_effect_boundary_canonical_sha256": identities[
            "skill_effect_canonical_sha256"
        ],
        "skill_effect_boundary_file_sha256": identities[
            "skill_effect_file_sha256"
        ],
        "selector_rva": f"0x{EXPECTED_SELECTOR_RVA:08x}",
        "selector_prebytes_hex": EXPECTED_SELECTOR_PREBYTES.hex(),
        "selector_prebytes_sha256": _sha256(EXPECTED_SELECTOR_PREBYTES),
        "selector_control_window_relocation_offsets": list(
            identities["selector_relocation_offsets"]
        ),
        "selected_rva": f"0x{EXPECTED_SELECTED_RVA:08x}",
        "selected_prebytes_hex": EXPECTED_SELECTED_PREBYTES.hex(),
        "selected_prebytes_sha256": _sha256(EXPECTED_SELECTED_PREBYTES),
        "queue_rva": f"0x{EXPECTED_QUEUE_RVA:08x}",
        "queue_prebytes_hex": EXPECTED_QUEUE_PREBYTES.hex(),
        "queue_prebytes_sha256": _sha256(EXPECTED_QUEUE_PREBYTES),
        "materialized_rva": f"0x{EXPECTED_MATERIALIZED_RVA:08x}",
        "materialized_prebytes_hex": EXPECTED_MATERIALIZED_PREBYTES.hex(),
        "materialized_prebytes_sha256": _sha256(
            EXPECTED_MATERIALIZED_PREBYTES
        ),
        "rng_state_owner_rva": f"0x{EXPECTED_RNG_STATE_OWNER_RVA:08x}",
        "rng_state_owner_size": EXPECTED_RNG_STATE_OWNER_SIZE,
        "rng_state_owner_sha256": EXPECTED_RNG_STATE_OWNER_SHA256,
        "rng_state_owner_relocation_offsets": list(
            identities["rng_state_owner_relocation_offsets"]
        ),
        "preferred_image_base": f"0x{EXPECTED_PREFERRED_IMAGE_BASE:08x}",
        "hardware_breakpoint_plan_filename": plan_path.name,
        "hardware_breakpoint_plan_sha256": plan_sha,
        "loaded_or_armed": False,
        "executable_bytes_modified": False,
    }
    _write_create_only(module_path, module)
    _write_create_only(plan_path, plan_data)
    _write_create_only(receipt_path, _canonical_json(receipt))
    if common._stable_bytes(module_path, "published observer") != module:
        raise ObserverBuildError("published observer failed byte verification")
    print(
        f"observer={module_path} sha256={module_sha} size={len(module)} "
        f"receipt={receipt_path}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return build_observer(args)
    except (ObserverBuildError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
