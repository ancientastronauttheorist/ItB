#!/usr/bin/env python3
"""Build and attest the dormant x86 selector-entry Board/RNG observer."""

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

from scripts import build_itb_observatory_enemy_tournament_hw_observer as tournament
from scripts import build_itb_observatory_spawn_coordinate_hw_observer as base
from src.observatory.enemy_position_observations_boundary import (
    EnemyPositionObservationsBoundaryError,
    validate_enemy_position_observations_boundary_binding,
)
from src.observatory.enemy_spawn_candidate_boundary import (
    EnemySpawnCandidateBoundaryError,
    validate_enemy_spawn_candidate_boundary_map_binding,
)


common = base.common
SOURCE = (
    ROOT
    / "src"
    / "native"
    / "observatory_spawn_coordinate_capsule_hw_observer.c"
)
BASE_SOURCE = (
    ROOT / "src" / "native" / "observatory_spawn_coordinate_hw_observer.c"
)
OBSERVER_VERSION = "observatory-spawn-coordinate-capsule-hw-observer/2"
EXPORT_NAME = "luaopen_itb_observatory_spawn_coordinate_capsule_hw_observer"
EXPECTED_EXECUTABLE_SHA256 = base.EXPECTED_EXECUTABLE_SHA256
EXPECTED_EXECUTABLE_SIZE = base.EXPECTED_EXECUTABLE_SIZE
EXPECTED_BUILD_ID = base.EXPECTED_BUILD_ID
EXPECTED_ARCHITECTURE = base.EXPECTED_ARCHITECTURE
EXPECTED_PE_TIMESTAMP = base.EXPECTED_PE_TIMESTAMP
EXPECTED_PE_SIZE_OF_IMAGE = base.EXPECTED_PE_SIZE_OF_IMAGE
EXPECTED_SELECTOR_REGION_RVA = base.EXPECTED_SELECTOR_REGION_RVA
EXPECTED_SELECTOR_REGION_SIZE = base.EXPECTED_SELECTOR_REGION_SIZE
EXPECTED_SELECTOR_REGION_SHA256 = base.EXPECTED_SELECTOR_REGION_SHA256
EXPECTED_SELECTOR_ENTRY_RVA = 0x00172A90
EXPECTED_SELECTOR_ENTRY_PREBYTES = bytes.fromhex("558bec6aff")
EXPECTED_SCHEDULER_RVA = base.EXPECTED_SCHEDULER_RVA
EXPECTED_SCHEDULER_PREBYTES = base.EXPECTED_SCHEDULER_PREBYTES
EXPECTED_SELECTOR_FALLBACK_RVA = base.EXPECTED_SELECTOR_FALLBACK_RVA
EXPECTED_SELECTOR_FALLBACK_PREBYTES = base.EXPECTED_SELECTOR_FALLBACK_PREBYTES
EXPECTED_SELECTOR_STANDARD_RVA = base.EXPECTED_SELECTOR_STANDARD_RVA
EXPECTED_SELECTOR_STANDARD_PREBYTES = base.EXPECTED_SELECTOR_STANDARD_PREBYTES
EXPECTED_RNG_STATE_OWNER_RVA = tournament.EXPECTED_RNG_STATE_OWNER_RVA
EXPECTED_RNG_STATE_OWNER_SIZE = tournament.EXPECTED_RNG_STATE_OWNER_SIZE
EXPECTED_RNG_STATE_OWNER_SHA256 = tournament.EXPECTED_RNG_STATE_OWNER_SHA256
EXPECTED_RNG_STATE_OWNER_RELOCATION_OFFSETS = (
    tournament.EXPECTED_RNG_STATE_OWNER_RELOCATION_OFFSETS
)
EXPECTED_PREFERRED_IMAGE_BASE = tournament.EXPECTED_PREFERRED_IMAGE_BASE
EXPECTED_BASE_PLAN_SHA256 = (
    "6c22aa5cb62552afd7f08d9e942a82cbceb620aab3b1853f004c98534ea74e09"
)
EXPECTED_BASE_SOURCE_SHA256 = (
    "00e468dbafaf2da583b10b29593f672e9977c18e1cd81f31a267df83c21403a5"
)
EXPECTED_SPAWN_BOUNDARY_FILE_SHA256 = (
    "46661d1a86f6c50c4cd757ed2674a800891c2ac8ee5bcad60727294d79c2e4db"
)
EXPECTED_SPAWN_BOUNDARY_CANONICAL_SHA256 = (
    "9f6785d16f6c1102a7fd6e52d656b1438a12b1a3f216cbb99e5cadd269f53b3f"
)
EXPECTED_POSITION_BOUNDARY_FILE_SHA256 = (
    "5be65abbb996582666fca63fa6028431599627eeef24e4967cb524805de4ec8a"
)
EXPECTED_POSITION_BOUNDARY_CANONICAL_SHA256 = (
    "f7871672fac450ff60196638bb35e28fb865f11844ce2cab76e9ba8bcafc8329"
)
BOARD_PRIMARY_VTABLE_RVA = 0x0042E2FC
BOARD_SECONDARY_VTABLE_RVA = 0x0042E258
EXPECTED_DR7 = 0x00000055
CAPSULE_CAPACITY = 64
TILE_CAPACITY = 64
POINT_CAPACITY = 64
OCCUPANT_CAPACITY = 8


class ObserverBuildError(RuntimeError):
    """Raised when a capsule observer build cannot be trusted."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--native-boundaries", type=Path, required=True)
    parser.add_argument("--rng-return-map", type=Path, required=True)
    parser.add_argument("--spawn-candidate-boundary", type=Path, required=True)
    parser.add_argument(
        "--position-observations-boundary", type=Path, required=True
    )
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _load_bound_artifact(
    path: Path,
    *,
    label: str,
    expected_file_sha256: str,
    expected_canonical_sha256: str,
    validator: Any,
    error_type: type[Exception],
) -> dict[str, Any]:
    try:
        value, raw = common._load_json(path, label)
        if _sha256(raw) != expected_file_sha256:
            raise ObserverBuildError(f"{label} file hash differs")
        result = validator(value)
    except (OSError, error_type) as exc:
        raise ObserverBuildError(f"{label} validation failed: {exc}") from exc
    if result.get("artifact_sha256") != expected_canonical_sha256:
        raise ObserverBuildError(f"{label} canonical hash differs")
    return result


def _validate_inputs(args: argparse.Namespace) -> dict[str, Any]:
    try:
        identities = base._validate_inputs(
            args.executable,
            args.native_boundaries,
            args.rng_return_map,
        )
    except (base.ObserverBuildError, OSError) as exc:
        raise ObserverBuildError(
            f"pinned observer input validation failed: {exc}"
        ) from exc
    executable: bytes = identities["executable"]
    image = identities["image"]

    entry_offset = image.rva_to_offset(
        EXPECTED_SELECTOR_ENTRY_RVA,
        len(EXPECTED_SELECTOR_ENTRY_PREBYTES),
    )
    if executable[
        entry_offset : entry_offset + len(EXPECTED_SELECTOR_ENTRY_PREBYTES)
    ] != EXPECTED_SELECTOR_ENTRY_PREBYTES:
        raise ObserverBuildError("selector-entry prebytes differ")

    owner_offset = image.rva_to_offset(
        EXPECTED_RNG_STATE_OWNER_RVA,
        EXPECTED_RNG_STATE_OWNER_SIZE,
    )
    owner = executable[
        owner_offset : owner_offset + EXPECTED_RNG_STATE_OWNER_SIZE
    ]
    if _sha256(owner) != EXPECTED_RNG_STATE_OWNER_SHA256:
        raise ObserverBuildError("RNG state-owner bytes differ")
    relocations = tournament._base_relocations(executable, image)
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
            raise ObserverBuildError(
                "RNG state-owner relocation value is not image-local"
            )

    for rva in (
        EXPECTED_SELECTOR_ENTRY_RVA,
        EXPECTED_SCHEDULER_RVA,
        EXPECTED_SELECTOR_FALLBACK_RVA,
        EXPECTED_SELECTOR_STANDARD_RVA,
        EXPECTED_RNG_STATE_OWNER_RVA,
    ):
        if not image.section_for_rva(rva).executable:
            raise ObserverBuildError(
                f"pinned RVA 0x{rva:08x} is not executable"
            )

    spawn_binding = _load_bound_artifact(
        args.spawn_candidate_boundary,
        label="enemy spawn-candidate boundary",
        expected_file_sha256=EXPECTED_SPAWN_BOUNDARY_FILE_SHA256,
        expected_canonical_sha256=EXPECTED_SPAWN_BOUNDARY_CANONICAL_SHA256,
        validator=validate_enemy_spawn_candidate_boundary_map_binding,
        error_type=EnemySpawnCandidateBoundaryError,
    )
    position_binding = _load_bound_artifact(
        args.position_observations_boundary,
        label="enemy position-observations boundary",
        expected_file_sha256=EXPECTED_POSITION_BOUNDARY_FILE_SHA256,
        expected_canonical_sha256=EXPECTED_POSITION_BOUNDARY_CANONICAL_SHA256,
        validator=validate_enemy_position_observations_boundary_binding,
        error_type=EnemyPositionObservationsBoundaryError,
    )
    base_source = common._stable_bytes(BASE_SOURCE, "v1 observer source")
    if _sha256(base_source) != EXPECTED_BASE_SOURCE_SHA256:
        raise ObserverBuildError("v1 observer source dependency differs")
    return {
        **identities,
        "rng_owner_bytes": owner,
        "spawn_boundary_sha256": spawn_binding["artifact_sha256"],
        "position_boundary_sha256": position_binding["artifact_sha256"],
        "base_source_sha256": _sha256(base_source),
    }


def _hardware_breakpoint_plan(
    source_sha256: str,
    identities: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "observatory_spawn_coordinate_capsule_hardware_breakpoint_plan",
        "observer_version": OBSERVER_VERSION,
        "identity": {
            "platform": "windows",
            "architecture": EXPECTED_ARCHITECTURE,
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "inventory_sha256": identities["inventory_canonical_sha256"],
            "boundary_map_sha256": identities[
                "boundary_map_canonical_sha256"
            ],
            "rng_return_map_sha256": identities["return_map_sha256"],
            "spawn_candidate_boundary_sha256": identities[
                "spawn_boundary_sha256"
            ],
            "position_observations_boundary_sha256": identities[
                "position_boundary_sha256"
            ],
            "v1_source_sha256": identities["base_source_sha256"],
            "v1_plan_sha256": EXPECTED_BASE_PLAN_SHA256,
            "source_sha256": source_sha256,
        },
        "static_regions": [
            {
                "id": "spawn_coordinate_selector",
                "rva": f"0x{EXPECTED_SELECTOR_REGION_RVA:08x}",
                "size": EXPECTED_SELECTOR_REGION_SIZE,
                "sha256": EXPECTED_SELECTOR_REGION_SHA256,
            },
            {
                "id": "shared_rng_state_owner",
                "rva": f"0x{EXPECTED_RNG_STATE_OWNER_RVA:08x}",
                "size": EXPECTED_RNG_STATE_OWNER_SIZE,
                "sha256": EXPECTED_RNG_STATE_OWNER_SHA256,
                "relocation_offsets": list(
                    EXPECTED_RNG_STATE_OWNER_RELOCATION_OFFSETS
                ),
            },
        ],
        "breakpoints": [
            {
                "slot": "DR0",
                "semantic_boundary": "scheduler_draw_resolved",
                "rva": f"0x{EXPECTED_SCHEDULER_RVA:08x}",
                "expected_prebytes_hex": EXPECTED_SCHEDULER_PREBYTES.hex(),
            },
            {
                "slot": "DR1",
                "semantic_boundary": "selector_fallback_draw_resolved",
                "rva": f"0x{EXPECTED_SELECTOR_FALLBACK_RVA:08x}",
                "expected_prebytes_hex": (
                    EXPECTED_SELECTOR_FALLBACK_PREBYTES.hex()
                ),
            },
            {
                "slot": "DR2",
                "semantic_boundary": "selector_standard_draw_resolved",
                "rva": f"0x{EXPECTED_SELECTOR_STANDARD_RVA:08x}",
                "expected_prebytes_hex": (
                    EXPECTED_SELECTOR_STANDARD_PREBYTES.hex()
                ),
            },
            {
                "slot": "DR3",
                "semantic_boundary": "selector_entry_board_rng_capsule",
                "rva": f"0x{EXPECTED_SELECTOR_ENTRY_RVA:08x}",
                "expected_prebytes_hex": EXPECTED_SELECTOR_ENTRY_PREBYTES.hex(),
                "register_contract": (
                    "ECX=active Board; [ESP+4]=hidden Point return; "
                    "[ESP+8]=Pawn"
                ),
            },
        ],
        "board_capsule": {
            "board_identity": {
                "primary_vtable_rva": f"0x{BOARD_PRIMARY_VTABLE_RVA:08x}",
                "secondary_vtable_rva": f"0x{BOARD_SECONDARY_VTABLE_RVA:08x}",
            },
            "scalar_fields": ["width", "height", "turn"],
            "point_keyed_block_spawn_values": "complete 8x8 map-tree traversal",
            "point_vectors": [
                "existing spawn markers at +0x2d50/+0x2d54",
                "danger vector A at +0x7460/+0x7464",
                "danger vector B at +0x7470/+0x7474",
            ],
            "tile_fields": [
                "terrain +0x2ae0",
                "pod state +0x2ae4",
                "danger byte +0x2af0",
                "acid byte +0x2af1",
                "item presence +0x2b04",
                "raw occupancy vector and pointer-free Pawn IDs +0xa0/+0xa4",
            ],
            "tile_order": "x-major then y-minor",
            "pointer_values_published": False,
            "qualification": (
                "Raw occupancy membership is captured, but transient dead/non-corpse "
                "classification and the Lua-derived Pawn path profile remain separate "
                "inputs; this capsule does not by itself claim a universal forecast."
            ),
        },
        "rng_pairing": {
            "state_owner_rva": f"0x{EXPECTED_RNG_STATE_OWNER_RVA:08x}",
            "state_offset": "0x18",
            "transition": "state_after = state_before * 214013 + 2531011 mod 2^32",
            "result": "raw_rng = (state_after >> 16) & 0x7fff",
            "pairing": "each DR3 entry pairs with the next DR1 or DR2 draw",
        },
        "debug_register_contract": {
            "arm_rejects_any_nonzero_dr0_dr1_dr2_dr3_or_dr7": True,
            "dr7_exact": f"0x{EXPECTED_DR7:08x}",
            "finish_requires_exact_owned_state_before_clear": True,
            "finish_clears_dr0_dr1_dr2_dr3_dr6_dr7": True,
        },
        "limits": {
            "draw_record_capacity": base.RECORD_CAPACITY,
            "capsule_capacity": CAPSULE_CAPACITY,
            "tile_capacity": TILE_CAPACITY,
            "point_vector_capacity": POINT_CAPACITY,
            "occupants_per_tile_capacity": OCCUPANT_CAPACITY,
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


def _generated_include(
    identities: dict[str, Any],
    plan_sha256: str,
) -> bytes:
    owner = identities["rng_owner_bytes"]
    text = f"""/* Generated; do not edit or install independently. */
#ifndef OBSERVATORY_SPAWN_COORDINATE_CAPSULE_HW_BUILD_INC
#define OBSERVATORY_SPAWN_COORDINATE_CAPSULE_HW_BUILD_INC

#define OBS_CAPSULE_HW_PLAN_SHA256 "{plan_sha256}"
#define OBS_SPAWN_CANDIDATE_BOUNDARY_SHA256 "{identities['spawn_boundary_sha256']}"
#define OBS_POSITION_OBSERVATIONS_BOUNDARY_SHA256 "{identities['position_boundary_sha256']}"
#define OBS_SELECTOR_ENTRY_RVA 0x{EXPECTED_SELECTOR_ENTRY_RVA:08x}u
#define OBS_SELECTOR_ENTRY_RVA_TEXT "0x{EXPECTED_SELECTOR_ENTRY_RVA:08x}"
#define OBS_SELECTOR_ENTRY_PREBYTE_SIZE {len(EXPECTED_SELECTOR_ENTRY_PREBYTES)}u
#define OBS_SELECTOR_ENTRY_PREBYTES_SHA256 "{_sha256(EXPECTED_SELECTOR_ENTRY_PREBYTES)}"
#define OBS_RNG_STATE_OWNER_RVA 0x{EXPECTED_RNG_STATE_OWNER_RVA:08x}u
#define OBS_RNG_STATE_OWNER_RVA_TEXT "0x{EXPECTED_RNG_STATE_OWNER_RVA:08x}"
#define OBS_RNG_STATE_OWNER_SIZE {EXPECTED_RNG_STATE_OWNER_SIZE}u
#define OBS_RNG_STATE_OWNER_SHA256 "{EXPECTED_RNG_STATE_OWNER_SHA256}"
#define OBS_PREFERRED_IMAGE_BASE 0x{EXPECTED_PREFERRED_IMAGE_BASE:08x}u
#define OBS_RNG_STATE_OWNER_RELOCATION_COUNT {len(EXPECTED_RNG_STATE_OWNER_RELOCATION_OFFSETS)}u
#define OBS_BOARD_PRIMARY_VTABLE_RVA 0x{BOARD_PRIMARY_VTABLE_RVA:08x}u
#define OBS_BOARD_SECONDARY_VTABLE_RVA 0x{BOARD_SECONDARY_VTABLE_RVA:08x}u

{_c_bytes('OBS_SELECTOR_ENTRY_PREBYTES', EXPECTED_SELECTOR_ENTRY_PREBYTES)}
{_c_bytes('OBS_RNG_STATE_OWNER_BYTES', owner)}
static const unsigned short OBS_RNG_STATE_OWNER_RELOCATION_OFFSETS[
    OBS_RNG_STATE_OWNER_RELOCATION_COUNT
] = {{{', '.join(f'{value}u' for value in EXPECTED_RNG_STATE_OWNER_RELOCATION_OFFSETS)}}};

#endif
"""
    return text.encode("ascii")


def _attest_source(source: bytes, base_source: bytes) -> dict[str, Any]:
    try:
        text = source.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise ObserverBuildError("observer source must remain ASCII") from exc
    if text.count("__declspec(dllexport)") != 1 or text.count(EXPORT_NAME) != 1:
        raise ObserverBuildError("observer source must expose exactly one Lua opener")
    if "DllMain" in text:
        raise ObserverBuildError("observer source must have no loader-time behavior")
    start = text.find("/* CAPSULE_HOT_PATH_BEGIN")
    end = text.find("/* CAPSULE_HOT_PATH_END */")
    if start < 0 or end <= start:
        raise ObserverBuildError("capsule hot-path markers are missing")
    hot = text[start:end]
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
        "observer_spawn_coordinate_capsule_veh",
        "context->Dr3 = (DWORD)g_selector_entry_address",
        "context->Dr7 = CAPSULE_DR7_EXACT",
        "context->Dr0 = 0",
        "context->Dr1 = 0",
        "context->Dr2 = 0",
        "context->Dr3 = 0",
        "context->Dr7 = 0",
        "context->EFlags |= OBS_EFLAGS_RF",
        "capsule->rng_state_before",
        "expected_rng_state =",
        "CAPSULE_BOARD_BLOCK_MAP_OFFSET",
        "CAPSULE_BOARD_DANGER_A_BEGIN_OFFSET",
        "CAPSULE_BOARD_DANGER_B_BEGIN_OFFSET",
        "CAPSULE_TILE_OCCUPANCY_BEGIN_OFFSET",
        "capsule->committed = capsule_index + 1",
    )
    if any(item not in hot for item in required):
        raise ObserverBuildError("observer VEH source contract differs")
    banned_source = (
        "WriteProcessMemory",
        "CreateRemoteThread",
        "OpenProcess",
        "VirtualProtect",
        "FlushInstructionCache",
        "DebugActiveProcess",
    )
    found_source = [name for name in banned_source if name in text]
    if found_source:
        raise ObserverBuildError(
            f"observer source contains executable-mutation surface: {found_source}"
        )
    return {
        "source_sha256": _sha256(source),
        "hot_source_sha256": _sha256(hot.encode("ascii")),
        "v1_source_sha256": _sha256(base_source),
        "v1_source_unchanged": _sha256(base_source)
        == EXPECTED_BASE_SOURCE_SHA256,
        "executable_mutation_api_text_absent": True,
        "private_debug_register_transition_present": True,
        "fixed_capsule_ring_present": (
            "g_capsules[CAPSULE_RECORD_CAP]" in text
        ),
        "pointer_values_published": False,
    }


def _compile_once(
    environment: dict[str, str],
    base_include: bytes,
    capsule_include: bytes,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="itb_observatory_spawn_coordinate_capsule_hw_"
    ) as raw:
        temporary = Path(raw)
        (temporary / "observatory_spawn_coordinate_hw_build.inc").write_bytes(
            base_include
        )
        (
            temporary
            / "observatory_spawn_coordinate_capsule_hw_build.inc"
        ).write_bytes(capsule_include)
        dll = temporary / "itb_observatory_spawn_coordinate_capsule_hw_observer.dll"
        obj = temporary / "observatory_spawn_coordinate_capsule_hw_observer.obj"
        cl = shutil.which("cl.exe", path=environment.get("PATH"))
        linker = shutil.which("link.exe", path=environment.get("PATH"))
        if cl is None or linker is None:
            raise ObserverBuildError("MSVC compiler or linker disappeared")
        compiled = subprocess.run(
            [
                cl,
                "/nologo",
                "/c",
                "/TC",
                "/O2",
                "/Oi",
                "/Ob3",
                "/arch:IA32",
                "/Qvec-",
                "/Oy",
                "/W4",
                "/WX",
                "/GS-",
                "/Gy",
                "/Zl",
                f"/I{temporary}",
                f"/Fo{obj}",
                str(SOURCE),
            ],
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
        linked = subprocess.run(
            [
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
            ],
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
        compiler_stdout = base._normalize_output(
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
        raise ObserverBuildError("compiled observer imports mutation APIs")
    machine_attestation = {
        "loader_entry_absent": True,
        "pe_entry_point_rva": "0x00000000",
        "veh": _attest_capsule_hot_section(module, image),
        "executable_mutation_api_imports_absent": True,
    }
    return {
        "module": module,
        "module_sha256": _sha256(module),
        "exports": exports,
        "imports": imports,
        "compiler_stdout": compiler_stdout,
        "machine_attestation": machine_attestation,
    }


def _write_create_only(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ObserverBuildError(
            f"immutable output already exists: {path.name}"
        ) from exc


def _attest_capsule_hot_section(data: bytes, image: Any) -> dict[str, Any]:
    import capstone
    import capstone.x86_const as x86_const
    from capstone.x86 import X86_OP_IMM

    if capstone.__version__ != "5.0.7":
        raise ObserverBuildError(
            f"unreviewed Capstone version: {capstone.__version__}"
        )
    matches = [section for section in image.sections if section.name == ".obshot"]
    if len(matches) != 1:
        raise ObserverBuildError("compiled observer needs one .obshot section")
    section = matches[0]
    if not section.executable or section.virtual_size <= 0:
        raise ObserverBuildError("compiled .obshot section is not executable")
    raw = data[section.raw_offset : section.raw_offset + section.virtual_size]
    padding_size = 0
    code = raw
    code_start = image.image_base + section.virtual_address
    code_end = code_start + len(code)
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    instructions = list(decoder.disasm(code, code_start))
    if not instructions or sum(item.size for item in instructions) != len(code):
        raise ObserverBuildError("compiled capsule VEH does not decode contiguously")
    calls: list[str] = []
    returns = 0
    branches = 0
    vector_groups = tuple(
        getattr(x86_const, name)
        for name in (
            "X86_GRP_FPU",
            "X86_GRP_MMX",
            "X86_GRP_SSE1",
            "X86_GRP_SSE2",
            "X86_GRP_AVX",
            "X86_GRP_AVX2",
        )
        if hasattr(x86_const, name)
    )
    for instruction in instructions:
        if instruction.group(capstone.CS_GRP_CALL):
            calls.append(f"0x{instruction.address:08x}")
        if instruction.group(capstone.CS_GRP_RET):
            returns += 1
        if instruction.group(capstone.CS_GRP_JUMP):
            branches += 1
            if (
                len(instruction.operands) != 1
                or instruction.operands[0].type != X86_OP_IMM
                or not code_start <= instruction.operands[0].imm < code_end
            ):
                raise ObserverBuildError(
                    "compiled capsule VEH has an external/indirect jump"
                )
        if any(instruction.group(group) for group in vector_groups):
            raise ObserverBuildError(
                "compiled capsule VEH changes vector/MMX/x87 state"
            )
        if instruction.mnemonic in {
            "int",
            "int1",
            "int3",
            "syscall",
            "sysenter",
            "hlt",
        }:
            raise ObserverBuildError(
                "compiled capsule VEH contains forbidden "
                f"{instruction.mnemonic} at 0x{instruction.address:08x}"
            )
    if calls:
        raise ObserverBuildError(
            f"compiled capsule VEH contains hot-path calls: {calls}"
        )
    if returns == 0:
        raise ObserverBuildError("compiled capsule VEH has no return")
    return {
        "section_rva": f"0x{section.virtual_address:08x}",
        "section_size": len(raw),
        "section_sha256": _sha256(raw),
        "code_rva": f"0x{section.virtual_address + padding_size:08x}",
        "code_size": len(code),
        "code_sha256": _sha256(code),
        "leading_int3_padding_size": padding_size,
        "leading_int3_padding_unreachable": True,
        "instruction_count": len(instructions),
        "branch_count": branches,
        "return_count": returns,
        "direct_or_indirect_call_count": 0,
        "windows_api_call_count": 0,
        "x87_mmx_sse_avx_instruction_count": 0,
    }


def build_observer(args: argparse.Namespace) -> int:
    identities = _validate_inputs(args)
    source = common._stable_bytes(SOURCE, "observer source")
    base_source = common._stable_bytes(BASE_SOURCE, "v1 observer source")
    source_attestation = _attest_source(source, base_source)
    plan = _hardware_breakpoint_plan(_sha256(source), identities)
    plan_data = _canonical_json(plan)
    plan_sha = _sha256(plan_data)
    base_include = base._generated_include(
        identities,
        EXPECTED_BASE_PLAN_SHA256,
    )
    capsule_include = _generated_include(identities, plan_sha)
    try:
        environment, compiler = common._msvc_environment()
    except (common.ObserverBuildError, OSError, subprocess.SubprocessError) as exc:
        raise ObserverBuildError(str(exc)) from exc
    first = _compile_once(environment, base_include, capsule_include)
    second = _compile_once(environment, base_include, capsule_include)
    for field in (
        "module",
        "module_sha256",
        "exports",
        "imports",
        "compiler_stdout",
        "machine_attestation",
    ):
        if first[field] != second[field]:
            raise ObserverBuildError(
                f"independent reproducibility builds differ: {field}"
            )
    module = first["module"]
    module_sha = first["module_sha256"]
    output_root = Path(os.path.abspath(args.output_root.expanduser()))
    stem = f"itb_observatory_spawn_coordinate_capsule_hw_observer_{module_sha}"
    module_path = output_root / f"{stem}.dll"
    receipt_path = output_root / f"{stem}.dll.receipt.json"
    plan_path = output_root / (
        f"windows_build_{EXPECTED_BUILD_ID}_spawn_coordinate_capsule_hw_plan_"
        f"{plan_sha}.json"
    )
    receipt = {
        "schema_version": 1,
        "kind": "observatory_spawn_coordinate_capsule_hw_observer_build",
        "observer_version": OBSERVER_VERSION,
        "module_filename": module_path.name,
        "module_sha256": module_sha,
        "module_size": len(module),
        "architecture": EXPECTED_ARCHITECTURE,
        "export_name": EXPORT_NAME,
        "exports": first["exports"],
        "imports": first["imports"],
        "source_path": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": _sha256(source),
        "base_source_path": BASE_SOURCE.relative_to(ROOT).as_posix(),
        "base_source_sha256": _sha256(base_source),
        "base_hardware_breakpoint_plan_sha256": EXPECTED_BASE_PLAN_SHA256,
        "base_generated_include_sha256": _sha256(base_include),
        "generated_include_sha256": _sha256(capsule_include),
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
            "/arch:IA32",
            "/Qvec-",
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
        "inventory_canonical_sha256": identities[
            "inventory_canonical_sha256"
        ],
        "boundary_map_canonical_sha256": identities[
            "boundary_map_canonical_sha256"
        ],
        "boundary_map_file_sha256": identities["boundary_map_file_sha256"],
        "rng_return_map_sha256": identities["return_map_sha256"],
        "spawn_candidate_boundary_sha256": identities[
            "spawn_boundary_sha256"
        ],
        "position_observations_boundary_sha256": identities[
            "position_boundary_sha256"
        ],
        "selector_region_rva": f"0x{EXPECTED_SELECTOR_REGION_RVA:08x}",
        "selector_region_size": EXPECTED_SELECTOR_REGION_SIZE,
        "selector_region_sha256": EXPECTED_SELECTOR_REGION_SHA256,
        "selector_entry_rva": f"0x{EXPECTED_SELECTOR_ENTRY_RVA:08x}",
        "selector_entry_prebytes_hex": EXPECTED_SELECTOR_ENTRY_PREBYTES.hex(),
        "selector_entry_prebytes_sha256": _sha256(
            EXPECTED_SELECTOR_ENTRY_PREBYTES
        ),
        "scheduler_rva": f"0x{EXPECTED_SCHEDULER_RVA:08x}",
        "scheduler_prebytes_sha256": _sha256(EXPECTED_SCHEDULER_PREBYTES),
        "selector_fallback_rva": f"0x{EXPECTED_SELECTOR_FALLBACK_RVA:08x}",
        "selector_fallback_prebytes_sha256": _sha256(
            EXPECTED_SELECTOR_FALLBACK_PREBYTES
        ),
        "selector_standard_rva": f"0x{EXPECTED_SELECTOR_STANDARD_RVA:08x}",
        "selector_standard_prebytes_sha256": _sha256(
            EXPECTED_SELECTOR_STANDARD_PREBYTES
        ),
        "rng_state_owner_rva": f"0x{EXPECTED_RNG_STATE_OWNER_RVA:08x}",
        "rng_state_owner_size": EXPECTED_RNG_STATE_OWNER_SIZE,
        "rng_state_owner_sha256": EXPECTED_RNG_STATE_OWNER_SHA256,
        "rng_state_offset": "0x18",
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
