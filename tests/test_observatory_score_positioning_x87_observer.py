from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts import build_itb_observatory_score_positioning_x87_observer as observer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "native" / "observatory_score_positioning_x87_observer.c"
BUILDER = (
    ROOT / "scripts" / "build_itb_observatory_score_positioning_x87_observer.py"
)


def _identities() -> dict:
    return {
        "inventory_canonical_sha256": "a" * 64,
        "inventory_file_sha256": "b" * 64,
        "boundary_map_canonical_sha256": "c" * 64,
        "boundary_map_file_sha256": "d" * 64,
    }


def test_score_positioning_x87_source_is_inert_and_narrow():
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
    assert attestation["floating_control_mutation_text_absent"] is True
    assert attestation["private_debug_register_transition_present"] is True
    assert attestation["fixed_single_record_present"] is True
    assert attestation["exact_three_frame_filter_present"] is True


def test_hot_path_reads_exact_x87_context_without_calls_or_floating_writes():
    text = SOURCE.read_text(encoding="ascii")
    hot = text[
        text.index("/* OBS_HOT_PATH_BEGIN") : text.index("/* OBS_HOT_PATH_END */")
    ]

    assert '#pragma code_seg(push, ".obshot")' in hot
    assert "__readfsdword(0x24)" in hot
    assert "thread_id != g_owner_thread_id" in hot
    assert "context->FloatSave.ControlWord" in hot
    assert "OBS_INTEGER_HELPER_AFTER_LUA_RVA" in hot
    assert "OBS_NAMED_INVOKER_AFTER_HELPER_RVA" in hot
    assert "OBS_SCORE_POSITIONING_AFTER_NAMED_RVA" in hot
    assert "hot_range_readable" in hot
    for forbidden in (
        "HeapAlloc",
        "VirtualQuery",
        "CreateFile",
        "ReadFile",
        "RaiseException",
        "g_lua_gettop",
        "g_luaL_error",
        "GetCurrentThreadId",
        "VirtualProtect",
        "WriteProcessMemory",
        "_controlfp",
        "fldcw",
        "ldmxcsr",
    ):
        assert forbidden not in hot


def test_debug_register_transition_self_clears_after_exact_capture():
    text = SOURCE.read_text(encoding="ascii")

    assert "context->Dr0 != 0" in text
    assert "context->Dr1 != 0" in text
    assert "context->Dr2 != 0" in text
    assert "context->Dr3 != 0" in text
    assert "context->Dr7 != 0" in text
    assert "context->Dr0 = (DWORD)g_lua_conversion_address" in text
    assert "context->Dr7 = OBS_DR7_EXACT" in text
    assert "context->ContextFlags |= CONTEXT_DEBUG_REGISTERS" in text
    assert text.count("context->Dr0 = 0") >= 2
    assert text.count("context->Dr1 = 0") >= 2
    assert text.count("context->Dr2 = 0") >= 3
    assert text.count("context->Dr3 = 0") >= 3
    assert text.count("context->Dr7 = 0") >= 2
    assert "g_record.committed = 1" in text
    assert "g_debug_cleared = 1" in text
    assert "debug-register clearing failed; no checkpoint published" in text


def test_plan_breaks_immediately_before_fistp_and_pins_full_frame_chain():
    plan = observer._hardware_breakpoint_plan("e" * 64, _identities())

    assert plan["kind"] == (
        "observatory_score_positioning_x87_hardware_breakpoint_plan"
    )
    assert plan["identity"]["executable_sha256"] == (
        observer.EXPECTED_EXECUTABLE_SHA256
    )
    assert plan["identity"]["lua_dll_sha256"] == observer.EXPECTED_LUA_SHA256
    assert plan["breakpoint"] == {
        "slot": "DR0",
        "kind": "x86_execute_length_1_current_thread_only",
        "image": "lua5.1.dll",
        "semantic_boundary": "lua_tointeger_immediately_before_fistp",
        "rva": "0x00001729",
        "expected_prebytes_hex": "db5de4",
        "expected_prebytes_sha256": observer._sha256(bytes.fromhex("db5de4")),
        "observed_field": "CONTEXT.FloatSave.ControlWord",
    }
    assert [item["return_rva"] for item in plan["accepted_frame_chain"]] == [
        "0x000f8b8f",
        "0x000f87e2",
        "0x000f78da",
    ]
    assert plan["debug_register_contract"]["dr7_exact"] == "0x00000001"
    assert plan["mutation_contract"] == {
        "executable_bytes_modified": False,
        "lua_bytes_modified": False,
        "page_protection_changed": False,
        "gateway_allocated": False,
        "detour_installed": False,
        "x87_control_word_modified": False,
        "mxcsr_modified": False,
    }
    assert plan["hot_contract"]["x87_sse_mmx_avx_instructions"] is False


def test_generated_include_pins_both_images_and_exact_conversion():
    include = observer._generated_include(_identities(), "f" * 64).decode("ascii")

    assert '#define OBS_HW_PLAN_SHA256 "' + "f" * 64 + '"' in include
    assert '#define OBS_INVENTORY_SHA256 "' + "a" * 64 + '"' in include
    assert '#define OBS_BOUNDARY_MAP_SHA256 "' + "c" * 64 + '"' in include
    assert "#define OBS_INTEGER_CALL_RVA 0x000f8b89u" in include
    assert "#define OBS_LUA_TOINTEGER_RVA 0x000016d0u" in include
    assert "#define OBS_LUA_CONVERSION_RVA 0x00001729u" in include
    assert "OBS_LUA_CONVERSION_BYTES[3]" in include
    assert "0xdb, 0x5d, 0xe4" in include
    assert "OBS_EXECUTABLE_SHA256_BYTES[32]" in include
    assert "OBS_LUA_SHA256_BYTES[32]" in include


def test_builder_rejects_unpinned_images(tmp_path):
    executable = tmp_path / "Breach.exe"
    lua = tmp_path / "lua5.1.dll"
    inventory = tmp_path / "inventory.json"
    boundaries = tmp_path / "boundaries.json"
    executable.write_bytes(b"not the pinned executable")
    lua.write_bytes(b"not the pinned Lua DLL")
    inventory.write_text(json.dumps({}), encoding="utf-8")
    boundaries.write_text(json.dumps({}), encoding="utf-8")
    args = argparse.Namespace(
        executable=executable,
        lua_dll=lua,
        inventory=inventory,
        native_boundaries=boundaries,
        output_root=tmp_path / "out",
    )

    with pytest.raises(observer.ObserverBuildError, match="Breach.exe"):
        observer._validate_inputs(args)


def test_builder_requires_inert_reproducible_api_free_machine_code():
    text = BUILDER.read_text(encoding="utf-8")

    assert '"/NOENTRY"' in text
    assert '"/NODEFAULTLIB"' in text
    assert '"/Brepro"' in text
    assert text.count("_compile_once(environment, include_data)") == 2
    assert '"independent_build_count": 2' in text
    assert "image.machine != 0x014C or image.entry_point != 0" in text
    assert "exports != [EXPORT_NAME]" in text
    assert '"direct_or_indirect_call_count": 0' in text
    assert '"x87_sse_mmx_avx_instruction_count": 0' in text
    assert '"floating_control_mutation_api_imports_absent": True' in text


def test_receipt_and_module_names_are_content_addressed(monkeypatch, tmp_path):
    module = b"pinned-x87-observer-module"
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
                "x87_sse_mmx_avx_instruction_count": 0,
            },
            "executable_mutation_api_imports_absent": True,
            "floating_control_mutation_api_imports_absent": True,
        },
    }
    monkeypatch.setattr(observer, "_validate_inputs", lambda *args: _identities())
    monkeypatch.setattr(
        observer.common,
        "_msvc_environment",
        lambda: ({}, "pinned x86 MSVC"),
    )
    monkeypatch.setattr(observer, "_compile_once", lambda *args: compiled)
    args = argparse.Namespace(
        executable=tmp_path / "Breach.exe",
        lua_dll=tmp_path / "lua5.1.dll",
        inventory=tmp_path / "inventory.json",
        native_boundaries=tmp_path / "boundaries.json",
        output_root=tmp_path / "out",
    )

    assert observer.build_observer(args) == 0
    stem = f"itb_observatory_score_positioning_x87_observer_{module_sha}"
    receipt_path = tmp_path / "out" / f"{stem}.dll.receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert (tmp_path / "out" / f"{stem}.dll").read_bytes() == module
    assert receipt["module_sha256"] == module_sha
    assert receipt["module_filename"] == f"{stem}.dll"
    assert receipt["loaded_or_armed"] is False
    assert receipt["executable_bytes_modified"] is False
    assert receipt["lua_bytes_modified"] is False
    assert receipt["floating_control_state_modified"] is False
    plan_name = receipt["hardware_breakpoint_plan_filename"]
    assert receipt["hardware_breakpoint_plan_sha256"] in plan_name
    assert (tmp_path / "out" / plan_name).is_file()
