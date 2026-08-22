from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts import build_itb_observatory_spawn_coordinate_hw_observer as observer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "native" / "observatory_spawn_coordinate_hw_observer.c"
BUILDER = ROOT / "scripts" / "build_itb_observatory_spawn_coordinate_hw_observer.py"


def _identities() -> dict:
    return {
        "inventory_canonical_sha256": "a" * 64,
        "boundary_map_canonical_sha256": "b" * 64,
        "boundary_map_file_sha256": "c" * 64,
        "return_map_sha256": "d" * 64,
    }


def test_spawn_coordinate_source_is_inert_and_has_one_narrow_lua_surface():
    source = SOURCE.read_bytes()
    attestation = observer._attest_source(source)
    text = source.decode("ascii")

    assert text.count("__declspec(dllexport)") == 1
    assert observer.EXPORT_NAME in text
    assert "DllMain" not in text
    assert "AddVectoredExceptionHandler" in text
    assert "RemoveVectoredExceptionHandler" in text
    assert text.count("RaiseException(") == 1
    assert attestation["executable_mutation_api_text_absent"] is True
    assert attestation["private_debug_register_transition_present"] is True
    assert attestation["fixed_ring_present"] is True
    assert attestation["candidate_capacity"] == 64


def test_veh_contract_is_current_thread_fixed_ring_and_api_free():
    text = SOURCE.read_text(encoding="ascii")
    hot = text[
        text.index("/* OBS_HOT_PATH_BEGIN") : text.index("/* OBS_HOT_PATH_END */")
    ]

    assert '#pragma code_seg(push, ".obshot")' in hot
    assert "__readfsdword(0x24)" in hot
    assert "thread_id != g_owner_thread_id" in hot
    assert "g_record_count >= OBS_RECORD_CAP" in hot
    assert "record->raw_rng = quotient * count + selected_index" in hot
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


def test_debug_register_transition_owns_three_execute_slots_and_clears_all():
    text = SOURCE.read_text(encoding="ascii")

    assert "context->Dr0 = (DWORD)g_scheduler_address" in text
    assert "context->Dr1 = (DWORD)g_selector_fallback_address" in text
    assert "context->Dr2 = (DWORD)g_selector_standard_address" in text
    assert "context->Dr7 = OBS_DR7_EXACT" in text
    assert text.count("context->Dr0 = 0") == 1
    assert text.count("context->Dr1 = 0") == 1
    assert text.count("context->Dr2 = 0") == 1
    assert text.count("context->Dr3 = 0") == 2
    assert text.count("context->Dr7 = 0") == 1
    assert "debug-register clearing failed; no checkpoint published" in text


def test_plan_pins_regions_seams_and_rng_reconstruction():
    plan = observer._hardware_breakpoint_plan("e" * 64, _identities())

    assert plan["kind"] == "observatory_spawn_coordinate_hardware_breakpoint_plan"
    assert [(item["slot"], item["rva"]) for item in plan["breakpoints"]] == [
        ("DR0", "0x001751ae"),
        ("DR1", "0x00172e1e"),
        ("DR2", "0x00172e7b"),
    ]
    assert [item["expected_prebytes_hex"] for item in plan["breakpoints"]] == [
        "8b45088bca8b550c",
        "8b75088b04d78906",
        "8b5cd1048b3cd18b",
    ]
    assert plan["debug_register_contract"]["dr7_exact"] == "0x00000015"
    assert plan["rng_reconstruction"]["formula"] == (
        "raw_rng = quotient * candidate_count + selected_index"
    )
    assert plan["mutation_contract"] == {
        "executable_bytes_modified": False,
        "page_protection_changed": False,
        "gateway_allocated": False,
        "detour_installed": False,
    }


def test_generated_include_pins_three_seams_and_two_regions():
    include = observer._generated_include(_identities(), "f" * 64).decode("ascii")

    assert '#define OBS_HW_PLAN_SHA256 "' + "f" * 64 + '"' in include
    assert "#define OBS_SCHEDULER_RVA 0x001751aeu" in include
    assert "#define OBS_SELECTOR_FALLBACK_RVA 0x00172e1eu" in include
    assert "#define OBS_SELECTOR_STANDARD_RVA 0x00172e7bu" in include
    assert observer.EXPECTED_SELECTOR_REGION_SHA256 in include
    assert observer.EXPECTED_SCHEDULER_REGION_SHA256 in include


def test_builder_rejects_an_unpinned_executable(tmp_path):
    executable = tmp_path / "Breach.exe"
    boundaries = tmp_path / "boundaries.json"
    return_map = tmp_path / "return_map.json"
    executable.write_bytes(b"not the pinned executable")
    boundaries.write_text(json.dumps({}), encoding="utf-8")
    return_map.write_text(json.dumps({}), encoding="utf-8")

    with pytest.raises(observer.ObserverBuildError, match="pinned observer"):
        observer._validate_inputs(executable, boundaries, return_map)


def test_builder_requires_inert_x86_reproducible_binary_attestation():
    text = BUILDER.read_text(encoding="utf-8")

    assert '"/NOENTRY"' in text
    assert '"/NODEFAULTLIB"' in text
    assert '"/Brepro"' in text
    assert text.count("_compile_once(environment, include_data)") == 2
    assert '"independent_build_count": 2' in text
    assert "image.machine != 0x014C or image.entry_point != 0" in text
    assert "exports != [EXPORT_NAME]" in text
    assert '"direct_or_indirect_call_count": 0' in text


def test_receipt_and_module_names_are_content_addressed(monkeypatch, tmp_path):
    module = b"pinned-coordinate-observer-module"
    module_sha = observer._sha256(module)
    compiled = {
        "module": module,
        "module_sha256": module_sha,
        "exports": [observer.EXPORT_NAME],
        "imports": ["bcrypt.dll", "kernel32.dll"],
        "compiler_stdout": "stable",
        "machine_attestation": {
            "loader_entry_absent": True,
            "veh": {"direct_or_indirect_call_count": 0},
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
        output_root=tmp_path / "out",
    )

    assert observer.build_observer(args) == 0
    stem = f"itb_observatory_spawn_coordinate_hw_observer_{module_sha}"
    receipt_path = tmp_path / "out" / f"{stem}.dll.receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert (tmp_path / "out" / f"{stem}.dll").read_bytes() == module
    assert receipt["module_sha256"] == module_sha
    assert receipt["loaded_or_armed"] is False
    assert receipt["executable_bytes_modified"] is False
    plan_name = receipt["hardware_breakpoint_plan_filename"]
    assert receipt["hardware_breakpoint_plan_sha256"] in plan_name
    assert (tmp_path / "out" / plan_name).is_file()
