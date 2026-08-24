from __future__ import annotations

import copy

import pytest

from src.observatory.score_positioning_x87 import (
    EXPECTED_BOUNDARY_SHA256,
    EXPECTED_EXECUTABLE_SHA256,
    EXPECTED_INVENTORY_SHA256,
    EXPECTED_LUA_SHA256,
    EXPECTED_MODULE_SHA256,
    EXPECTED_PLAN_SHA256,
    ScorePositioningX87Error,
    analyze_score_positioning_x87_snapshot,
    validate_score_positioning_x87_snapshot,
)


def _receipt() -> dict:
    return {
        "schema_version": 1,
        "kind": "observatory_score_positioning_x87_observer_build",
        "observer_version": "observatory-score-positioning-x87-observer/1",
        "build_id": "13725832",
        "architecture": "x86",
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        "executable_size": 5_530_112,
        "lua_dll_sha256": EXPECTED_LUA_SHA256,
        "lua_dll_size": 419_840,
        "inventory_canonical_sha256": EXPECTED_INVENTORY_SHA256,
        "boundary_map_canonical_sha256": EXPECTED_BOUNDARY_SHA256,
        "module_sha256": EXPECTED_MODULE_SHA256,
        "hardware_breakpoint_plan_sha256": EXPECTED_PLAN_SHA256,
        "score_positioning_rva": "0x000f7870",
        "score_positioning_sha256": (
            "9794db437203d18af0ce5245bc178f537e20f715b192c671cc7ecde7d279a42a"
        ),
        "named_integer_invoker_rva": "0x000f8770",
        "named_integer_invoker_sha256": (
            "59607f3c4741577e11c570b31aeb3dfaadec00d85ec8a69e024a7f06760e584e"
        ),
        "integer_helper_rva": "0x000f8a90",
        "integer_helper_sha256": (
            "1f979a7f27695df192b75d20e076aa1a6c5ad83a2f5657d6858e1c01d4f45704"
        ),
        "integer_call_rva": "0x000f8b89",
        "integer_call_bytes_hex": "ff15f0647d00",
        "lua_tointeger_rva": "0x000016d0",
        "lua_tointeger_sha256": (
            "2d935d28eefdd86c2035f20567820a17c7bc0b9941b5343bf3475fcf7c30b2ab"
        ),
        "lua_fld_rva": "0x00001726",
        "lua_fistp_rva": "0x00001729",
        "lua_conversion_bytes_hex": "dd45f0db5de4",
        "reproducibility": {
            "independent_build_count": 2,
            "module_bytes_identical": True,
            "attestations_identical": True,
        },
        "machine_attestation": {
            "loader_entry_absent": True,
            "executable_mutation_api_imports_absent": True,
            "floating_control_mutation_api_imports_absent": True,
            "veh": {
                "direct_or_indirect_call_count": 0,
                "windows_api_call_count": 0,
                "x87_sse_mmx_avx_instruction_count": 0,
            },
        },
        "loaded_or_armed": False,
        "executable_bytes_modified": False,
        "lua_bytes_modified": False,
        "floating_control_state_modified": False,
    }


def _snapshot(*, mode: str = "nearest_even", bits: int = 0) -> dict:
    control_word = 0x027F | bits
    return {
        "schema_version": 1,
        "kind": "native_score_positioning_x87_snapshot",
        "observer_version": "observatory-score-positioning-x87-observer/1",
        "capture_id": "score-x87-pair-001",
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "build_id": "13725832",
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": 5_530_112,
            "lua_dll_sha256": EXPECTED_LUA_SHA256,
            "lua_dll_size": 419_840,
            "inventory_sha256": EXPECTED_INVENTORY_SHA256,
            "boundary_map_sha256": EXPECTED_BOUNDARY_SHA256,
            "hardware_breakpoint_plan_sha256": EXPECTED_PLAN_SHA256,
            "integer_call_rva": "0x000f8b89",
            "lua_tointeger_rva": "0x000016d0",
            "lua_conversion_rva": "0x00001729",
        },
        "integrity": {
            "state": "restored",
            "complete": True,
            "ignored_non_score_count": 17,
            "pointer_fault_count": 0,
            "context_flag_error_count": 0,
            "transition_mismatch_count": 0,
            "wrong_thread_count": 0,
            "unexpected_breakpoint_count": 0,
            "torn_record_count": 0,
            "debug_registers_armed": False,
            "debug_registers_cleared": True,
            "veh_installed": False,
            "veh_removed": True,
            "executable_file_released": True,
            "lua_file_released": True,
            "executable_bytes_modified": False,
            "seams_unchanged": True,
        },
        "observation": {
            "seq": 1,
            "thread_id": 4312,
            "context_flags": 0x1001F,
            "control_word": control_word,
            "rounding_control_bits": bits,
            "rounding_mode": mode,
            "lua_conversion_rva": 0x00001729,
            "integer_helper_return_rva": 0x000F8B8F,
            "named_invoker_return_rva": 0x000F87E2,
            "score_positioning_return_rva": 0x000F78DA,
        },
        "summary": {
            "record_count": 1,
            "thread_count": 1,
            "observed_rounding_mode": mode,
        },
    }


@pytest.mark.parametrize(
    ("bits", "mode"),
    [
        (0x0000, "nearest_even"),
        (0x0400, "down"),
        (0x0800, "up"),
        (0x0C00, "toward_zero"),
    ],
)
def test_validator_accepts_each_real_x87_rounding_mode(bits, mode):
    result = validate_score_positioning_x87_snapshot(
        _snapshot(mode=mode, bits=bits),
        build_receipt=_receipt(),
        observed_module_sha256=EXPECTED_MODULE_SHA256,
    )

    assert result["rounding_control_bits"] == bits
    assert result["rounding_mode"] == mode
    assert result["ignored_non_score_count"] == 17


def test_analysis_states_narrow_runtime_claim_and_restoration():
    result = analyze_score_positioning_x87_snapshot(
        _snapshot(),
        build_receipt=_receipt(),
        observed_module_sha256=EXPECTED_MODULE_SHA256,
    )

    assert result["kind"] == "score_positioning_x87_observation_analysis"
    assert result["observation"]["rounding_mode"] == "nearest_even"
    assert result["observation"]["boundary"].endswith("before FISTP")
    assert len(result["claims"]["proven"]) == 2
    assert len(result["claims"]["not_proven"]) == 2


@pytest.mark.parametrize(
    ("path", "value", "match"),
    [
        (("identity", "lua_conversion_rva"), "0x00001723", "identity"),
        (("integrity", "veh_removed"), False, "fully restored"),
        (("integrity", "pointer_fault_count"), 1, "pointer_fault_count"),
        (("observation", "rounding_control_bits"), 0x0400, "boundary or mode"),
        (("observation", "integer_helper_return_rva"), 0, "boundary or mode"),
        (("summary", "record_count"), 2, "summary"),
    ],
)
def test_validator_rejects_identity_restoration_and_observation_drift(
    path, value, match
):
    snapshot = _snapshot()
    snapshot[path[0]][path[1]] = value

    with pytest.raises(ScorePositioningX87Error, match=match):
        validate_score_positioning_x87_snapshot(
            snapshot,
            build_receipt=_receipt(),
            observed_module_sha256=EXPECTED_MODULE_SHA256,
        )


def test_validator_rejects_extra_fields_and_wrong_module():
    snapshot = _snapshot()
    snapshot["observation"]["address"] = 0x10001729
    with pytest.raises(ScorePositioningX87Error, match="fields differ"):
        validate_score_positioning_x87_snapshot(
            snapshot,
            build_receipt=_receipt(),
            observed_module_sha256=EXPECTED_MODULE_SHA256,
        )

    with pytest.raises(ScorePositioningX87Error, match="not pinned"):
        validate_score_positioning_x87_snapshot(
            _snapshot(),
            build_receipt=_receipt(),
            observed_module_sha256="0" * 64,
        )


def test_validator_rejects_receipt_machine_attestation_drift():
    receipt = copy.deepcopy(_receipt())
    receipt["machine_attestation"]["veh"]["x87_sse_mmx_avx_instruction_count"] = 1

    with pytest.raises(ScorePositioningX87Error, match="safety attestation"):
        validate_score_positioning_x87_snapshot(
            _snapshot(),
            build_receipt=receipt,
            observed_module_sha256=EXPECTED_MODULE_SHA256,
        )
