#!/usr/bin/env python3
"""Build and attest the dormant x86 spawn-coordinate HW observer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_itb_observatory_rng_core_observer as common


SOURCE = ROOT / "src" / "native" / "observatory_spawn_coordinate_hw_observer.c"
OBSERVER_VERSION = "observatory-spawn-coordinate-hw-observer/1"
EXPORT_NAME = "luaopen_itb_observatory_spawn_coordinate_hw_observer"
EXPECTED_EXECUTABLE_SHA256 = common.EXPECTED_EXECUTABLE_SHA256
EXPECTED_EXECUTABLE_SIZE = common.EXPECTED_EXECUTABLE_SIZE
EXPECTED_BUILD_ID = common.EXPECTED_BUILD_ID
EXPECTED_ARCHITECTURE = common.EXPECTED_ARCHITECTURE
EXPECTED_PE_TIMESTAMP = common.EXPECTED_PE_TIMESTAMP
EXPECTED_PE_SIZE_OF_IMAGE = common.EXPECTED_PE_SIZE_OF_IMAGE
EXPECTED_SELECTOR_REGION_RVA = 0x00172A90
EXPECTED_SELECTOR_REGION_SIZE = 0x466
EXPECTED_SELECTOR_REGION_SHA256 = (
    "9746df5a768534c54108600528bce8e0fd152d41e322bf0907dc92a434148904"
)
EXPECTED_SCHEDULER_REGION_RVA = 0x001750F0
EXPECTED_SCHEDULER_REGION_SIZE = 0x17B
EXPECTED_SCHEDULER_REGION_SHA256 = (
    "639ea27e48757d5c7f08499522d7f8933dc874957f4d00a74bbeec4a6750bd89"
)
EXPECTED_SCHEDULER_RVA = 0x001751AE
EXPECTED_SCHEDULER_PREBYTES = bytes.fromhex("8b45088bca8b550c")
EXPECTED_SELECTOR_FALLBACK_RVA = 0x00172E1E
EXPECTED_SELECTOR_FALLBACK_PREBYTES = bytes.fromhex("8b75088b04d78906")
EXPECTED_SELECTOR_STANDARD_RVA = 0x00172E7B
EXPECTED_SELECTOR_STANDARD_PREBYTES = bytes.fromhex("8b5cd1048b3cd18b")
EXPECTED_DR7 = 0x00000015
RECORD_CAPACITY = 256
CANDIDATE_CAPACITY = 64


class ObserverBuildError(RuntimeError):
    """Raised when a build or attestation cannot be trusted."""


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
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _validate_inputs(
    executable_path: Path,
    boundaries_path: Path,
    return_map_path: Path,
) -> dict[str, Any]:
    try:
        validated = common._validate_inputs(
            executable_path, boundaries_path, return_map_path
        )
    except (common.ObserverBuildError, OSError) as exc:
        raise ObserverBuildError(f"pinned observer input validation failed: {exc}") from exc
    executable: bytes = validated["executable"]
    image = validated["image"]
    spans = {
        "selector_region": (
            EXPECTED_SELECTOR_REGION_RVA,
            EXPECTED_SELECTOR_REGION_SIZE,
            EXPECTED_SELECTOR_REGION_SHA256,
        ),
        "scheduler_region": (
            EXPECTED_SCHEDULER_REGION_RVA,
            EXPECTED_SCHEDULER_REGION_SIZE,
            EXPECTED_SCHEDULER_REGION_SHA256,
        ),
    }
    region_bytes: dict[str, bytes] = {}
    for name, (rva, size, expected_sha256) in spans.items():
        offset = image.rva_to_offset(rva, size)
        value = executable[offset : offset + size]
        if _sha256(value) != expected_sha256:
            raise ObserverBuildError(f"{name} hash differs")
        if not image.section_for_rva(rva).executable:
            raise ObserverBuildError(f"{name} is not executable")
        region_bytes[name] = value
    seams = {
        "scheduler": (EXPECTED_SCHEDULER_RVA, EXPECTED_SCHEDULER_PREBYTES),
        "selector_fallback": (
            EXPECTED_SELECTOR_FALLBACK_RVA,
            EXPECTED_SELECTOR_FALLBACK_PREBYTES,
        ),
        "selector_standard": (
            EXPECTED_SELECTOR_STANDARD_RVA,
            EXPECTED_SELECTOR_STANDARD_PREBYTES,
        ),
    }
    seam_bytes: dict[str, bytes] = {}
    for name, (rva, expected) in seams.items():
        offset = image.rva_to_offset(rva, len(expected))
        value = executable[offset : offset + len(expected)]
        if value != expected:
            raise ObserverBuildError(f"{name} seam prebytes differ")
        if not image.section_for_rva(rva).executable:
            raise ObserverBuildError(f"{name} seam is not executable")
        seam_bytes[name] = value
    return {
        **validated,
        "region_bytes": region_bytes,
        "seam_bytes": seam_bytes,
    }


def _hardware_breakpoint_plan(
    source_sha256: str, identities: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "observatory_spawn_coordinate_hardware_breakpoint_plan",
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
            "source_sha256": source_sha256,
        },
        "static_regions": [
            {
                "id": "spawn_coordinate_selector",
                "rva": f"0x{EXPECTED_SELECTOR_REGION_RVA:08x}",
                "size": EXPECTED_SELECTOR_REGION_SIZE,
                "sha256": EXPECTED_SELECTOR_REGION_SHA256,
                "reviewed_role": (
                    "filters native point candidates and performs the final "
                    "standard or fallback coordinate draw"
                ),
            },
            {
                "id": "spawn_coordinate_scheduler",
                "rva": f"0x{EXPECTED_SCHEDULER_REGION_RVA:08x}",
                "size": EXPECTED_SCHEDULER_REGION_SIZE,
                "sha256": EXPECTED_SCHEDULER_REGION_SHA256,
                "reviewed_role": (
                    "randomly removes candidate points before invoking the "
                    "final coordinate selector"
                ),
            },
        ],
        "breakpoints": [
            {
                "slot": "DR0",
                "kind": "x86_execute_length_1_current_thread_only",
                "semantic_boundary": "scheduler_draw_resolved",
                "rva": f"0x{EXPECTED_SCHEDULER_RVA:08x}",
                "expected_prebytes_hex": EXPECTED_SCHEDULER_PREBYTES.hex(),
                "expected_prebytes_sha256": _sha256(EXPECTED_SCHEDULER_PREBYTES),
                "register_contract": (
                    "EAX=quotient; EDX=selected index; ESI=count; "
                    "[EBP+8]=begin; [EBP+0xc]=end"
                ),
            },
            {
                "slot": "DR1",
                "kind": "x86_execute_length_1_current_thread_only",
                "semantic_boundary": "selector_fallback_draw_resolved",
                "rva": f"0x{EXPECTED_SELECTOR_FALLBACK_RVA:08x}",
                "expected_prebytes_hex": EXPECTED_SELECTOR_FALLBACK_PREBYTES.hex(),
                "expected_prebytes_sha256": _sha256(
                    EXPECTED_SELECTOR_FALLBACK_PREBYTES
                ),
                "register_contract": (
                    "EAX=quotient; EDX=selected index; ESI=count; EDI=begin; "
                    "[EBP-0x44]=begin; [EBP-0x40]=end"
                ),
            },
            {
                "slot": "DR2",
                "kind": "x86_execute_length_1_current_thread_only",
                "semantic_boundary": "selector_standard_draw_resolved",
                "rva": f"0x{EXPECTED_SELECTOR_STANDARD_RVA:08x}",
                "expected_prebytes_hex": EXPECTED_SELECTOR_STANDARD_PREBYTES.hex(),
                "expected_prebytes_sha256": _sha256(
                    EXPECTED_SELECTOR_STANDARD_PREBYTES
                ),
                "register_contract": (
                    "EAX=quotient; EDX=selected index; ESI=count; ECX=begin; "
                    "[EBP-0x38]=begin; [EBP-0x34]=end"
                ),
            },
        ],
        "rng_reconstruction": {
            "formula": "raw_rng = quotient * candidate_count + selected_index",
            "basis": "resolved state immediately after signed idiv",
            "accepted_domain": {
                "quotient_min": 0,
                "quotient_max": 32767,
                "selected_index_min": 0,
                "candidate_count_min": 1,
                "candidate_count_max": CANDIDATE_CAPACITY,
            },
        },
        "debug_register_contract": {
            "arm_rejects_any_nonzero_dr0_dr1_dr2_dr3_or_dr7": True,
            "dr7_exact": f"0x{EXPECTED_DR7:08x}",
            "transition": "private_RaiseException_handled_by_VEH",
            "finish_requires_exact_owned_state_before_clear": True,
            "finish_clears_dr0_dr1_dr2_dr3_dr6_dr7": True,
        },
        "limits": {
            "record_capacity": RECORD_CAPACITY,
            "candidate_capacity_per_record": CANDIDATE_CAPACITY,
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
            "addresses_or_pointers_published": False,
        },
    }


def _c_bytes(name: str, data: bytes) -> str:
    values = ", ".join(f"0x{value:02x}" for value in data)
    return f"static const unsigned char {name}[{len(data)}] = {{{values}}};"


def _generated_include(identities: dict[str, Any], plan_sha256: str) -> bytes:
    digest = bytes.fromhex(EXPECTED_EXECUTABLE_SHA256)
    text = f"""/* Generated; do not edit or install independently. */
#ifndef OBSERVATORY_SPAWN_COORDINATE_HW_BUILD_INC
#define OBSERVATORY_SPAWN_COORDINATE_HW_BUILD_INC

#define OBS_BUILD_ID \"{EXPECTED_BUILD_ID}\"
#define OBS_EXECUTABLE_SHA256 \"{EXPECTED_EXECUTABLE_SHA256}\"
#define OBS_EXECUTABLE_SIZE {EXPECTED_EXECUTABLE_SIZE}L
#define OBS_PE_TIMESTAMP 0x{EXPECTED_PE_TIMESTAMP:08x}u
#define OBS_PE_SIZE_OF_IMAGE 0x{EXPECTED_PE_SIZE_OF_IMAGE:08x}u
#define OBS_INVENTORY_SHA256 \"{identities['inventory_canonical_sha256']}\"
#define OBS_BOUNDARY_MAP_SHA256 \"{identities['boundary_map_canonical_sha256']}\"
#define OBS_HW_PLAN_SHA256 \"{plan_sha256}\"
#define OBS_SELECTOR_REGION_SHA256 \"{EXPECTED_SELECTOR_REGION_SHA256}\"
#define OBS_SCHEDULER_REGION_SHA256 \"{EXPECTED_SCHEDULER_REGION_SHA256}\"
#define OBS_SCHEDULER_RVA 0x{EXPECTED_SCHEDULER_RVA:08x}u
#define OBS_SCHEDULER_RVA_TEXT \"0x{EXPECTED_SCHEDULER_RVA:08x}\"
#define OBS_SCHEDULER_PREBYTE_SIZE {len(EXPECTED_SCHEDULER_PREBYTES)}u
#define OBS_SCHEDULER_PREBYTES_SHA256 \"{_sha256(EXPECTED_SCHEDULER_PREBYTES)}\"
#define OBS_SELECTOR_FALLBACK_RVA 0x{EXPECTED_SELECTOR_FALLBACK_RVA:08x}u
#define OBS_SELECTOR_FALLBACK_RVA_TEXT \"0x{EXPECTED_SELECTOR_FALLBACK_RVA:08x}\"
#define OBS_SELECTOR_FALLBACK_PREBYTE_SIZE {len(EXPECTED_SELECTOR_FALLBACK_PREBYTES)}u
#define OBS_SELECTOR_FALLBACK_PREBYTES_SHA256 \"{_sha256(EXPECTED_SELECTOR_FALLBACK_PREBYTES)}\"
#define OBS_SELECTOR_STANDARD_RVA 0x{EXPECTED_SELECTOR_STANDARD_RVA:08x}u
#define OBS_SELECTOR_STANDARD_RVA_TEXT \"0x{EXPECTED_SELECTOR_STANDARD_RVA:08x}\"
#define OBS_SELECTOR_STANDARD_PREBYTE_SIZE {len(EXPECTED_SELECTOR_STANDARD_PREBYTES)}u
#define OBS_SELECTOR_STANDARD_PREBYTES_SHA256 \"{_sha256(EXPECTED_SELECTOR_STANDARD_PREBYTES)}\"

{_c_bytes('OBS_EXECUTABLE_SHA256_BYTES', digest)}
{_c_bytes('OBS_SCHEDULER_PREBYTES', EXPECTED_SCHEDULER_PREBYTES)}
{_c_bytes('OBS_SELECTOR_FALLBACK_PREBYTES', EXPECTED_SELECTOR_FALLBACK_PREBYTES)}
{_c_bytes('OBS_SELECTOR_STANDARD_PREBYTES', EXPECTED_SELECTOR_STANDARD_PREBYTES)}

#endif
"""
    return text.encode("ascii")


def _attest_source(source: bytes) -> dict[str, Any]:
    try:
        text = source.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise ObserverBuildError("observer source must remain ASCII") from exc
    if text.count("__declspec(dllexport)") != 1 or text.count(EXPORT_NAME) != 1:
        raise ObserverBuildError("observer source must expose exactly one Lua opener")
    if "DllMain" in text:
        raise ObserverBuildError("observer source must have no loader-time behavior")
    start = text.find("/* OBS_HOT_PATH_BEGIN")
    end = text.find("/* OBS_HOT_PATH_END */")
    if start < 0 or end <= start:
        raise ObserverBuildError("observer hot-path markers are missing")
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
        "observer_spawn_coordinate_veh",
        "context->Dr0 = (DWORD)g_scheduler_address",
        "context->Dr1 = (DWORD)g_selector_fallback_address",
        "context->Dr2 = (DWORD)g_selector_standard_address",
        "context->Dr7 = OBS_DR7_EXACT",
        "context->ContextFlags |= CONTEXT_DEBUG_REGISTERS",
        "context->Dr0 = 0",
        "context->Dr1 = 0",
        "context->Dr2 = 0",
        "context->Dr7 = 0",
        "context->EFlags |= OBS_EFLAGS_RF",
        "hot_range_readable",
        "g_readable_ranges[index]",
        "record->raw_rng = quotient * count + selected_index",
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
        "executable_mutation_api_text_absent": True,
        "private_debug_register_transition_present": True,
        "fixed_ring_present": "g_records[OBS_RECORD_CAP]" in text,
        "candidate_capacity": CANDIDATE_CAPACITY,
    }


def _attest_hot_section(data: bytes, image: common.PEImage) -> dict[str, Any]:
    try:
        import capstone
        import capstone.x86_const as x86_const
        from capstone.x86 import X86_OP_IMM
    except ImportError as exc:
        raise ObserverBuildError("Capstone 5.0.7 is required for VEH proof") from exc
    if capstone.__version__ != "5.0.7":
        raise ObserverBuildError(f"unreviewed Capstone version: {capstone.__version__}")
    matches = [section for section in image.sections if section.name == ".obshot"]
    if len(matches) != 1:
        raise ObserverBuildError("compiled observer needs one .obshot section")
    section = matches[0]
    if not section.executable or section.virtual_size <= 0:
        raise ObserverBuildError("compiled .obshot section is not executable")
    raw = data[section.raw_offset : section.raw_offset + section.virtual_size]
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    instructions = list(decoder.disasm(raw, image.image_base + section.virtual_address))
    if not instructions or sum(item.size for item in instructions) != len(raw):
        raise ObserverBuildError("compiled VEH does not decode contiguously")
    calls = []
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
    start = image.image_base + section.virtual_address
    end = start + len(raw)
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
                or not start <= instruction.operands[0].imm < end
            ):
                raise ObserverBuildError("compiled VEH has an external/indirect jump")
        if any(instruction.group(group) for group in vector_groups):
            raise ObserverBuildError("compiled VEH changes vector/MMX/x87 state")
        if instruction.mnemonic in {"int", "int1", "int3", "syscall", "sysenter", "hlt"}:
            raise ObserverBuildError(
                f"compiled VEH contains forbidden {instruction.mnemonic}"
            )
    if calls:
        raise ObserverBuildError(f"compiled VEH contains hot-path calls: {calls}")
    if returns == 0:
        raise ObserverBuildError("compiled VEH has no return")
    return {
        "section_rva": f"0x{section.virtual_address:08x}",
        "section_size": len(raw),
        "section_sha256": _sha256(raw),
        "instruction_count": len(instructions),
        "branch_count": branches,
        "return_count": returns,
        "direct_or_indirect_call_count": 0,
        "windows_api_call_count": 0,
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


def _compile_once(environment: dict[str, str], include_data: bytes) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="itb_observatory_spawn_coordinate_hw_") as raw:
        temporary = Path(raw)
        (temporary / "observatory_spawn_coordinate_hw_build.inc").write_bytes(include_data)
        dll = temporary / "itb_observatory_spawn_coordinate_hw_observer.dll"
        obj = temporary / "observatory_spawn_coordinate_hw_observer.obj"
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
    if not set(imports) <= {"bcrypt.dll", "kernel32.dll"} or "kernel32.dll" not in imports:
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
    machine_attestation = {
        "loader_entry_absent": True,
        "pe_entry_point_rva": "0x00000000",
        "veh": _attest_hot_section(module, image),
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
        raise ObserverBuildError(f"immutable output already exists: {path.name}") from exc


def build_observer(args: argparse.Namespace) -> int:
    identities = _validate_inputs(
        args.executable, args.native_boundaries, args.rng_return_map
    )
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
    stem = f"itb_observatory_spawn_coordinate_hw_observer_{module_sha}"
    module_path = output_root / f"{stem}.dll"
    receipt_path = output_root / f"{stem}.dll.receipt.json"
    plan_path = output_root / (
        f"windows_build_{EXPECTED_BUILD_ID}_spawn_coordinate_hw_plan_{plan_sha}.json"
    )
    receipt = {
        "schema_version": 1,
        "kind": "observatory_spawn_coordinate_hw_observer_build",
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
        "selector_region_rva": f"0x{EXPECTED_SELECTOR_REGION_RVA:08x}",
        "selector_region_size": EXPECTED_SELECTOR_REGION_SIZE,
        "selector_region_sha256": EXPECTED_SELECTOR_REGION_SHA256,
        "scheduler_region_rva": f"0x{EXPECTED_SCHEDULER_REGION_RVA:08x}",
        "scheduler_region_size": EXPECTED_SCHEDULER_REGION_SIZE,
        "scheduler_region_sha256": EXPECTED_SCHEDULER_REGION_SHA256,
        "scheduler_rva": f"0x{EXPECTED_SCHEDULER_RVA:08x}",
        "scheduler_prebytes_hex": EXPECTED_SCHEDULER_PREBYTES.hex(),
        "scheduler_prebytes_sha256": _sha256(EXPECTED_SCHEDULER_PREBYTES),
        "selector_fallback_rva": f"0x{EXPECTED_SELECTOR_FALLBACK_RVA:08x}",
        "selector_fallback_prebytes_hex": (
            EXPECTED_SELECTOR_FALLBACK_PREBYTES.hex()
        ),
        "selector_fallback_prebytes_sha256": _sha256(
            EXPECTED_SELECTOR_FALLBACK_PREBYTES
        ),
        "selector_standard_rva": f"0x{EXPECTED_SELECTOR_STANDARD_RVA:08x}",
        "selector_standard_prebytes_hex": (
            EXPECTED_SELECTOR_STANDARD_PREBYTES.hex()
        ),
        "selector_standard_prebytes_sha256": _sha256(
            EXPECTED_SELECTOR_STANDARD_PREBYTES
        ),
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
