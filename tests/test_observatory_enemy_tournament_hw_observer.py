from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts import build_itb_observatory_enemy_tournament_hw_observer as observer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "native" / "observatory_enemy_tournament_hw_observer.c"
BASE_SOURCE = ROOT / "src" / "native" / "observatory_selected_queue_hw_observer.c"
BUILDER = ROOT / "scripts" / "build_itb_observatory_enemy_tournament_hw_observer.py"


def _identities() -> dict:
    return {
        "inventory_canonical_sha256": "a" * 64,
        "boundary_map_canonical_sha256": "b" * 64,
        "boundary_map_file_sha256": "c" * 64,
        "return_map_sha256": "d" * 64,
        "record_selector_canonical_sha256": "e" * 64,
        "record_selector_file_sha256": "f" * 64,
        "selected_queue_source_sha256": "1" * 64,
        "rng_state_owner_bytes": bytes(range(131)),
        "rng_state_owner_relocation_offsets": (6, 13, 66, 83, 110, 122),
        "selector_relocation_offsets": (6,),
    }


def test_source_is_inert_and_reuses_one_hash_pinned_runtime_dependency():
    source = SOURCE.read_bytes()
    attestation = observer._attest_source(source)
    text = source.decode("ascii")

    assert text.count("__declspec(dllexport)") == 1
    assert observer.EXPORT_NAME in text
    assert "DllMain" not in text
    assert text.count('#include "observatory_selected_queue_hw_observer.c"') == 1
    assert "#define dllexport noinline" in text
    assert attestation["selected_queue_dependency_include_present"] is True
    assert attestation["historical_opener_export_neutralized"] is True
    assert attestation["rng_owner_relocation_normalization_present"] is True
    assert attestation["executable_mutation_api_text_absent"] is True
    assert attestation["fixed_candidate_ring_present"] is True
    assert observer._sha256(BASE_SOURCE.read_bytes()) == (
        observer.EXPECTED_SELECTED_QUEUE_SOURCE_SHA256
    )


def test_hot_path_captures_ordered_vector_rng_states_and_three_seams_api_free():
    text = SOURCE.read_text(encoding="ascii")
    hot = text[
        text.index("/* TOURNAMENT_HOT_PATH_BEGIN") : text.index(
            "/* TOURNAMENT_HOT_PATH_END */"
        )
    ]

    assert '#pragma code_seg(push, ".obshot")' in hot
    assert "context->Dr0 = (DWORD)g_tournament_selector_address" in hot
    assert "context->Dr1 = (DWORD)g_selected_address" in hot
    assert "context->Dr2 = (DWORD)g_queue_address" in hot
    assert "context->Dr7 = TOURNAMENT_DR7_ARM" in hot
    assert "context->Dr7 = TOURNAMENT_DR7_AFTER_SELECTOR" in hot
    assert "context->Dr7 = TOURNAMENT_DR7_QUEUE_ONLY" in hot
    assert "g_tournament_rng_before" in hot
    assert "g_tournament_rng_after" in hot
    assert "g_tournament_candidates[index]" in hot
    assert "record->committed = index + 1" in hot
    assert "g_tournament_stage = TOURNAMENT_STAGE_COMPLETE" in hot
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


def test_capture_layout_matches_reviewed_selector_vector_and_rng_owner_contract():
    text = SOURCE.read_text(encoding="ascii")

    for offset in ("8u", "0x0cu", "0x10u", "0x14u", "0x24u"):
        assert f"context_pointer + {offset}" in text
    for index in range(6):
        assert f"source[{index}]" in text
    assert "context_pointer - 0x14u" in text
    assert "owner_result + TOURNAMENT_RNG_STATE_OFFSET" in text
    assert "pawn + 0x9a4u" in text
    assert "pawn + 0x948u" in text
    assert "board + 0x48u" in text
    assert "board + 0x4cu" in text


def test_plan_pins_selector_selected_queue_and_owner_state_without_mutation():
    plan = observer._hardware_breakpoint_plan("2" * 64, _identities())

    assert plan["kind"] == "observatory_enemy_tournament_hardware_breakpoint_plan"
    assert [(item["slot"], item["rva"]) for item in plan["breakpoints"]] == [
        ("DR0", "0x000f7dd0"),
        ("DR1", "0x000f6854"),
        ("DR2", "0x00227d20"),
    ]
    assert plan["debug_register_contract"]["arm_dr7_exact"] == "0x00000015"
    assert plan["debug_register_contract"]["after_selector_dr7_exact"] == (
        "0x00000014"
    )
    assert plan["debug_register_contract"]["queue_only_dr7_exact"] == (
        "0x00000010"
    )
    rng = plan["rng_state_contract"]
    assert rng["owner_rva"] == "0x0038ed32"
    assert rng["owner_region_size"] == 131
    assert rng["owner_region_sha256"] == observer.EXPECTED_RNG_STATE_OWNER_SHA256
    assert rng["preferred_image_base"] == "0x00400000"
    assert rng["base_relocation_offsets"] == [6, 13, 66, 83, 110, 122]
    assert rng["state_offset"] == "0x18"
    assert rng["owner_called_once_on_arm_thread_before_debug_register_arm"] is True
    assert rng["state_read_before_selector_and_after_selected_copy"] is True
    assert plan["mutation_contract"] == {
        "executable_bytes_modified": False,
        "page_protection_changed": False,
        "gateway_allocated": False,
        "detour_installed": False,
    }
    assert plan["hot_contract"]["x87_mmx_sse_avx_state_changes"] is False


def test_generated_include_pins_all_code_and_evidence_dependencies():
    include = observer._generated_include(_identities(), "3" * 64).decode("ascii")

    assert '#define OBS_HW_PLAN_SHA256 "' + "3" * 64 + '"' in include
    assert "#define OBS_TOURNAMENT_SELECTOR_RVA 0x000f7dd0u" in include
    assert "#define OBS_SELECTED_RVA 0x000f6854u" in include
    assert "#define OBS_QUEUE_RVA 0x00227d20u" in include
    assert "#define OBS_RNG_STATE_OWNER_RVA 0x0038ed32u" in include
    assert '#define OBS_RECORD_SELECTOR_BOUNDARY_SHA256 "' + "e" * 64 + '"' in include
    assert '#define OBS_SELECTED_QUEUE_SOURCE_SHA256 "' + "1" * 64 + '"' in include
    assert "OBS_TOURNAMENT_SELECTOR_PREBYTES[6]" in include
    assert "OBS_RNG_STATE_OWNER_BYTES[131]" in include
    assert "#define OBS_PREFERRED_IMAGE_BASE 0x00400000u" in include
    assert "#define OBS_RNG_STATE_OWNER_RELOCATION_COUNT 6u" in include
    assert "6u, 13u, 66u, 83u, 110u, 122u" in include


def test_builder_rejects_an_unpinned_executable(tmp_path):
    executable = tmp_path / "Breach.exe"
    boundaries = tmp_path / "boundaries.json"
    return_map = tmp_path / "return_map.json"
    record_selector = tmp_path / "record_selector.json"
    executable.write_bytes(b"not the pinned executable")
    boundaries.write_text(json.dumps({}), encoding="utf-8")
    return_map.write_text(json.dumps({}), encoding="utf-8")
    record_selector.write_text(json.dumps({}), encoding="utf-8")
    args = argparse.Namespace(
        executable=executable,
        native_boundaries=boundaries,
        rng_return_map=return_map,
        record_selector_boundary=record_selector,
    )

    with pytest.raises(observer.ObserverBuildError, match="pinned observer"):
        observer._validate_inputs(args)


def test_builder_requires_inert_x86_reproducible_machine_attestation():
    text = BUILDER.read_text(encoding="utf-8")

    assert '"/NOENTRY"' in text
    assert '"/NODEFAULTLIB"' in text
    assert '"/Brepro"' in text
    assert text.count("_compile_once(environment, include_data)") == 2
    assert '"independent_build_count": 2' in text
    assert "image.machine != 0x014C or image.entry_point != 0" in text
    assert "exports != [EXPORT_NAME]" in text
    assert 'attestation["x87_mmx_sse_avx_instruction_count"] = 0' in text
    assert '"executable_mutation_api_imports_absent": True' in text


def test_receipt_and_module_names_are_content_addressed(monkeypatch, tmp_path):
    module = b"pinned-tournament-observer"
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
        record_selector_boundary=tmp_path / "record_selector.json",
        output_root=tmp_path / "out",
    )

    assert observer.build_observer(args) == 0
    stem = f"itb_observatory_enemy_tournament_hw_observer_{module_sha}"
    receipt_path = tmp_path / "out" / f"{stem}.dll.receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert (tmp_path / "out" / f"{stem}.dll").read_bytes() == module
    assert receipt["module_sha256"] == module_sha
    assert receipt["module_filename"] == f"{stem}.dll"
    assert receipt["selected_queue_source_sha256"] == "1" * 64
    assert receipt["loaded_or_armed"] is False
    assert receipt["executable_bytes_modified"] is False
    plan_name = receipt["hardware_breakpoint_plan_filename"]
    assert receipt["hardware_breakpoint_plan_sha256"] in plan_name
    assert (tmp_path / "out" / plan_name).is_file()
