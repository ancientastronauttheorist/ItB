from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from scripts import (
    build_itb_observatory_spawn_coordinate_capsule_hw_observer as observer,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "src"
    / "native"
    / "observatory_spawn_coordinate_capsule_hw_observer.c"
)
BASE_SOURCE = ROOT / "src" / "native" / "observatory_spawn_coordinate_hw_observer.c"
BUILDER = (
    ROOT
    / "scripts"
    / "build_itb_observatory_spawn_coordinate_capsule_hw_observer.py"
)
MODULE_SHA256 = (
    "bb099e829df74d4d7e1841a5ac70174bbdd2712ddfcdc0b2c9f633d32e0f17b9"
)
MODULE = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / f"itb_observatory_spawn_coordinate_capsule_hw_observer_{MODULE_SHA256}.dll"
)
BUILD_RECEIPT = MODULE.with_suffix(".dll.receipt.json")
PLAN = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / (
        "windows_build_13725832_spawn_coordinate_capsule_hw_plan_"
        "e79fb1f734f06dee9862b15f29e0bbccfa82e34b3fe2506565ab56ad45d39ca1.json"
    )
)
DORMANT_LOAD_RECEIPT = (
    ROOT
    / "data"
    / "observatory"
    / "captures"
    / (
        "windows_build_13725832_owner_local_modified_20260829_"
        "spawn_coordinate_capsule_dormant_load_receipt.json"
    )
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identities() -> dict:
    return {
        "inventory_canonical_sha256": "a" * 64,
        "boundary_map_canonical_sha256": "b" * 64,
        "boundary_map_file_sha256": "c" * 64,
        "return_map_sha256": "d" * 64,
        "spawn_boundary_sha256": "e" * 64,
        "position_boundary_sha256": "f" * 64,
        "base_source_sha256": observer.EXPECTED_BASE_SOURCE_SHA256,
        "rng_owner_bytes": bytes(range(131)),
    }


def test_capsule_source_is_inert_and_reuses_hash_pinned_v1_dependency():
    source = SOURCE.read_bytes()
    base_source = BASE_SOURCE.read_bytes()
    attestation = observer._attest_source(source, base_source)
    text = source.decode("ascii")

    assert text.count("__declspec(dllexport)") == 1
    assert observer.EXPORT_NAME in text
    assert "DllMain" not in text
    assert text.count('#include "observatory_spawn_coordinate_hw_observer.c"') == 1
    assert "#define dllexport noinline" in text
    assert attestation["v1_source_unchanged"] is True
    assert attestation["fixed_capsule_ring_present"] is True
    assert attestation["pointer_values_published"] is False
    assert observer._sha256(base_source) == observer.EXPECTED_BASE_SOURCE_SHA256


def test_capsule_hot_path_owns_four_breakpoints_and_is_api_free():
    text = SOURCE.read_text(encoding="ascii")
    hot = text[
        text.index("/* CAPSULE_HOT_PATH_BEGIN") : text.index(
            "/* CAPSULE_HOT_PATH_END */"
        )
    ]

    assert '#pragma code_seg(push, ".obshot")' in hot
    assert "context->Dr0 = (DWORD)g_scheduler_address" in hot
    assert "context->Dr1 = (DWORD)g_selector_fallback_address" in hot
    assert "context->Dr2 = (DWORD)g_selector_standard_address" in hot
    assert "context->Dr3 = (DWORD)g_selector_entry_address" in hot
    assert "context->Dr7 = CAPSULE_DR7_EXACT" in hot
    assert "capsule->rng_state_before" in hot
    assert "expected_rng_state =" in hot
    assert "capsule->committed = capsule_index + 1" in hot
    for forbidden in (
        "HeapAlloc",
        "VirtualQuery",
        "CreateFile",
        "ReadFile",
        "RaiseException",
        "lua_",
        "luaL_",
        "GetCurrentThreadId",
        "VirtualProtect",
        "WriteProcessMemory",
    ):
        assert forbidden not in hot


def test_plan_pins_selector_entry_board_rng_and_no_mutation_contract():
    plan = observer._hardware_breakpoint_plan("1" * 64, _identities())

    assert plan["kind"] == (
        "observatory_spawn_coordinate_capsule_hardware_breakpoint_plan"
    )
    assert [(item["slot"], item["rva"]) for item in plan["breakpoints"]] == [
        ("DR0", "0x001751ae"),
        ("DR1", "0x00172e1e"),
        ("DR2", "0x00172e7b"),
        ("DR3", "0x00172a90"),
    ]
    assert plan["debug_register_contract"]["dr7_exact"] == "0x00000055"
    assert plan["board_capsule"]["tile_order"] == "x-major then y-minor"
    assert plan["board_capsule"]["pointer_values_published"] is False
    assert plan["rng_pairing"]["pairing"] == (
        "each DR3 entry pairs with the next DR1 or DR2 draw"
    )
    assert plan["hot_contract"]["x87_mmx_sse_avx_state_changes"] is False
    assert plan["mutation_contract"] == {
        "executable_bytes_modified": False,
        "page_protection_changed": False,
        "gateway_allocated": False,
        "detour_installed": False,
    }


def test_generated_include_pins_all_four_seams_board_vtables_and_rng_owner():
    include = observer._generated_include(_identities(), "2" * 64).decode("ascii")

    assert '#define OBS_CAPSULE_HW_PLAN_SHA256 "' + "2" * 64 + '"' in include
    assert "#define OBS_SELECTOR_ENTRY_RVA 0x00172a90u" in include
    assert "#define OBS_RNG_STATE_OWNER_RVA 0x0038ed32u" in include
    assert "#define OBS_BOARD_PRIMARY_VTABLE_RVA 0x0042e2fcu" in include
    assert "#define OBS_BOARD_SECONDARY_VTABLE_RVA 0x0042e258u" in include
    assert "OBS_RNG_STATE_OWNER_BYTES[131]" in include
    assert '#define OBS_SPAWN_CANDIDATE_BOUNDARY_SHA256 "' + "e" * 64 + '"' in include
    assert '#define OBS_POSITION_OBSERVATIONS_BOUNDARY_SHA256 "' + "f" * 64 + '"' in include


def test_builder_rejects_an_unpinned_executable(tmp_path):
    executable = tmp_path / "Breach.exe"
    boundaries = tmp_path / "boundaries.json"
    returns = tmp_path / "returns.json"
    spawn = tmp_path / "spawn.json"
    position = tmp_path / "position.json"
    executable.write_bytes(b"not the pinned executable")
    for path in (boundaries, returns, spawn, position):
        path.write_text(json.dumps({}), encoding="utf-8")
    args = argparse.Namespace(
        executable=executable,
        native_boundaries=boundaries,
        rng_return_map=returns,
        spawn_candidate_boundary=spawn,
        position_observations_boundary=position,
    )

    with pytest.raises(observer.ObserverBuildError, match="pinned observer"):
        observer._validate_inputs(args)


def test_builder_requires_scalar_inert_x86_reproducible_machine_attestation():
    text = BUILDER.read_text(encoding="utf-8")

    assert '"/NOENTRY"' in text
    assert '"/NODEFAULTLIB"' in text
    assert '"/Brepro"' in text
    assert '"/arch:IA32"' in text
    assert '"/Qvec-"' in text
    assert text.count("_compile_once(environment, base_include, capsule_include)") == 2
    assert '"independent_build_count": 2' in text
    assert "image.machine != 0x014C or image.entry_point != 0" in text
    assert "exports != [EXPORT_NAME]" in text
    assert '"x87_mmx_sse_avx_instruction_count": 0' in text
    assert '"direct_or_indirect_call_count": 0' in text


def test_receipt_and_module_names_are_content_addressed(monkeypatch, tmp_path):
    module = b"pinned-capsule-observer"
    module_sha = observer._sha256(module)
    compiled = {
        "module": module,
        "module_sha256": module_sha,
        "exports": [observer.EXPORT_NAME],
        "imports": ["bcrypt.dll", "kernel32.dll"],
        "compiler_stdout": "stable",
        "machine_attestation": {
            "loader_entry_absent": True,
            "veh": {
                "direct_or_indirect_call_count": 0,
                "windows_api_call_count": 0,
                "x87_mmx_sse_avx_instruction_count": 0,
            },
            "executable_mutation_api_imports_absent": True,
        },
    }
    monkeypatch.setattr(observer, "_validate_inputs", lambda *args: _identities())
    monkeypatch.setattr(
        observer.common, "_msvc_environment", lambda: ({}, "pinned x86 MSVC")
    )
    monkeypatch.setattr(observer, "_compile_once", lambda *args: compiled)
    args = argparse.Namespace(
        executable=tmp_path / "Breach.exe",
        native_boundaries=tmp_path / "boundaries.json",
        rng_return_map=tmp_path / "returns.json",
        spawn_candidate_boundary=tmp_path / "spawn.json",
        position_observations_boundary=tmp_path / "position.json",
        output_root=tmp_path / "out",
    )

    assert observer.build_observer(args) == 0
    stem = f"itb_observatory_spawn_coordinate_capsule_hw_observer_{module_sha}"
    receipt_path = tmp_path / "out" / f"{stem}.dll.receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert (tmp_path / "out" / f"{stem}.dll").read_bytes() == module
    assert receipt["module_sha256"] == module_sha
    assert receipt["module_filename"] == f"{stem}.dll"
    assert receipt["spawn_candidate_boundary_sha256"] == "e" * 64
    assert receipt["position_observations_boundary_sha256"] == "f" * 64
    assert receipt["loaded_or_armed"] is False
    assert receipt["executable_bytes_modified"] is False
    plan_name = receipt["hardware_breakpoint_plan_filename"]
    assert receipt["hardware_breakpoint_plan_sha256"] in plan_name
    assert (tmp_path / "out" / plan_name).is_file()


def test_committed_dormant_load_receipt_binds_exact_inert_artifacts():
    receipt = json.loads(DORMANT_LOAD_RECEIPT.read_text(encoding="utf-8"))
    installed = receipt["installed_artifacts"]
    build = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))

    assert not MODULE.exists()
    assert not any((ROOT / "data" / "observatory").rglob("*.dll"))
    assert build["module_sha256"] == MODULE_SHA256
    assert build["module_size"] == installed["observer_module"]["size"]
    assert build["module_sha256"] == installed["observer_module"]["sha256"]
    assert _sha256_file(BUILD_RECEIPT) == installed["build_receipt"]["sha256"]
    assert _sha256_file(PLAN) == installed["hardware_breakpoint_plan"]["sha256"]
    assert _sha256_file(ROOT / "src" / "bridge" / "modloader.lua") == (
        installed["modloader"]["sha256"]
    )
    assert receipt["bridge_observation"]["ack"] == (
        "OK OBS_SPAWN_CAPSULE_LOAD_CHECK "
        "state=dormant consumed=false armed=false"
    )
    assert receipt["claims"] == {
        "capture_started": False,
        "debug_registers_armed": False,
        "module_loaded_in_game_process": True,
        "native_selector_or_rng_runtime_evidence_captured": False,
        "observer_consumed": False,
        "observer_state_dormant": True,
        "prepare_or_seed_command_executed": False,
        "veh_installed": False,
    }
