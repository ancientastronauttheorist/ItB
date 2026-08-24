"""Validate exact-build ScorePositioning x87 runtime observations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


SCHEMA_VERSION = 1
SNAPSHOT_KIND = "native_score_positioning_x87_snapshot"
ANALYSIS_KIND = "score_positioning_x87_observation_analysis"
OBSERVER_VERSION = "observatory-score-positioning-x87-observer/1"
EXPECTED_MODULE_SHA256 = (
    "515376611fb75ff58ed5323b654eb8dd2402996e5e4dbc237d870d3c5fbab504"
)
EXPECTED_PLAN_SHA256 = (
    "5a104c63de813099febaabe692e2e89e313459d6579dd8808e4c4bb2516013b0"
)
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_LUA_SHA256 = (
    "0157f0c34e72b32e63ebf3fdd9a21215de674b51b6d1750ebe545ef3093a0c14"
)
EXPECTED_INVENTORY_SHA256 = (
    "81fc5d328603c087154c00c8249e9f2e208539b24b7989bd9d805403192aa2b4"
)
EXPECTED_BOUNDARY_SHA256 = (
    "ded91fdf8181b2ae310644ece211f77fecc4393c3cd1c43867cfd353af3d6dc2"
)
ROUNDING_BITS_TO_MODE = {
    0x0000: "nearest_even",
    0x0400: "down",
    0x0800: "up",
    0x0C00: "toward_zero",
}


class ScorePositioningX87Error(RuntimeError):
    """Raised when x87 build or runtime evidence is malformed."""


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ScorePositioningX87Error(f"{label} fields differ from the contract")


def _integer(
    value: object,
    label: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if (
        type(value) is not int
        or (minimum is not None and value < minimum)
        or (maximum is not None and value > maximum)
    ):
        raise ScorePositioningX87Error(f"{label} is invalid")
    return value


def _sha256(value: object) -> str:
    payload = (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_receipt(
    receipt: Mapping[str, Any], observed_module_sha256: str
) -> dict[str, Any]:
    if receipt.get("schema_version") != 1 or receipt.get("kind") != (
        "observatory_score_positioning_x87_observer_build"
    ):
        raise ScorePositioningX87Error("x87 observer build receipt is invalid")
    expected = {
        "observer_version": OBSERVER_VERSION,
        "build_id": "13725832",
        "architecture": "x86",
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        "executable_size": 5_530_112,
        "lua_dll_sha256": EXPECTED_LUA_SHA256,
        "lua_dll_size": 419_840,
        "inventory_canonical_sha256": EXPECTED_INVENTORY_SHA256,
        "boundary_map_canonical_sha256": EXPECTED_BOUNDARY_SHA256,
        "module_sha256": observed_module_sha256,
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
    }
    if observed_module_sha256 != EXPECTED_MODULE_SHA256:
        raise ScorePositioningX87Error("observed x87 module digest is not pinned")
    for field, expected_value in expected.items():
        if receipt.get(field) != expected_value:
            raise ScorePositioningX87Error(f"x87 build receipt {field} differs")
    reproducibility = receipt.get("reproducibility")
    machine = receipt.get("machine_attestation")
    veh = machine.get("veh") if isinstance(machine, Mapping) else None
    if (
        not isinstance(reproducibility, Mapping)
        or reproducibility.get("independent_build_count") != 2
        or reproducibility.get("module_bytes_identical") is not True
        or reproducibility.get("attestations_identical") is not True
        or not isinstance(veh, Mapping)
        or veh.get("direct_or_indirect_call_count") != 0
        or veh.get("windows_api_call_count") != 0
        or veh.get("x87_sse_mmx_avx_instruction_count") != 0
        or machine.get("loader_entry_absent") is not True
        or machine.get("executable_mutation_api_imports_absent") is not True
        or machine.get("floating_control_mutation_api_imports_absent") is not True
        or receipt.get("loaded_or_armed") is not False
        or receipt.get("executable_bytes_modified") is not False
        or receipt.get("lua_bytes_modified") is not False
        or receipt.get("floating_control_state_modified") is not False
    ):
        raise ScorePositioningX87Error("x87 observer build safety attestation failed")
    return expected


def validate_score_positioning_x87_snapshot(
    snapshot: Mapping[str, Any],
    *,
    build_receipt: Mapping[str, Any],
    observed_module_sha256: str,
) -> dict[str, Any]:
    """Validate one restored observation at the exact FISTP boundary."""
    if not isinstance(snapshot, Mapping):
        raise ScorePositioningX87Error("x87 snapshot must be an object")
    _exact_keys(
        snapshot,
        {
            "schema_version",
            "kind",
            "observer_version",
            "capture_id",
            "identity",
            "integrity",
            "observation",
            "summary",
        },
        "snapshot",
    )
    if (
        snapshot["schema_version"] != SCHEMA_VERSION
        or snapshot["kind"] != SNAPSHOT_KIND
        or snapshot["observer_version"] != OBSERVER_VERSION
        or type(snapshot["capture_id"]) is not str
        or not snapshot["capture_id"]
    ):
        raise ScorePositioningX87Error("x87 snapshot header is invalid")
    receipt_expected = _validate_receipt(build_receipt, observed_module_sha256)

    identity = snapshot["identity"]
    if not isinstance(identity, Mapping):
        raise ScorePositioningX87Error("snapshot.identity must be an object")
    _exact_keys(
        identity,
        {
            "platform",
            "architecture",
            "build_id",
            "executable_sha256",
            "executable_size",
            "lua_dll_sha256",
            "lua_dll_size",
            "inventory_sha256",
            "boundary_map_sha256",
            "hardware_breakpoint_plan_sha256",
            "integer_call_rva",
            "lua_tointeger_rva",
            "lua_conversion_rva",
        },
        "snapshot.identity",
    )
    expected_identity = {
        "platform": "windows",
        "architecture": receipt_expected["architecture"],
        "build_id": receipt_expected["build_id"],
        "executable_sha256": receipt_expected["executable_sha256"],
        "executable_size": receipt_expected["executable_size"],
        "lua_dll_sha256": receipt_expected["lua_dll_sha256"],
        "lua_dll_size": receipt_expected["lua_dll_size"],
        "inventory_sha256": receipt_expected["inventory_canonical_sha256"],
        "boundary_map_sha256": receipt_expected[
            "boundary_map_canonical_sha256"
        ],
        "hardware_breakpoint_plan_sha256": receipt_expected[
            "hardware_breakpoint_plan_sha256"
        ],
        "integer_call_rva": receipt_expected["integer_call_rva"],
        "lua_tointeger_rva": receipt_expected["lua_tointeger_rva"],
        "lua_conversion_rva": receipt_expected["lua_fistp_rva"],
    }
    if dict(identity) != expected_identity:
        raise ScorePositioningX87Error("x87 snapshot identity differs from receipt")

    integrity = snapshot["integrity"]
    if not isinstance(integrity, Mapping):
        raise ScorePositioningX87Error("snapshot.integrity must be an object")
    _exact_keys(
        integrity,
        {
            "state",
            "complete",
            "ignored_non_score_count",
            "pointer_fault_count",
            "context_flag_error_count",
            "transition_mismatch_count",
            "wrong_thread_count",
            "unexpected_breakpoint_count",
            "torn_record_count",
            "debug_registers_armed",
            "debug_registers_cleared",
            "veh_installed",
            "veh_removed",
            "executable_file_released",
            "lua_file_released",
            "executable_bytes_modified",
            "seams_unchanged",
        },
        "snapshot.integrity",
    )
    _integer(
        integrity["ignored_non_score_count"],
        "snapshot.integrity.ignored_non_score_count",
        minimum=0,
    )
    for field in (
        "pointer_fault_count",
        "context_flag_error_count",
        "transition_mismatch_count",
        "wrong_thread_count",
        "unexpected_breakpoint_count",
        "torn_record_count",
    ):
        if _integer(integrity[field], f"snapshot.integrity.{field}", minimum=0) != 0:
            raise ScorePositioningX87Error(f"x87 snapshot reports {field}")
    if (
        integrity["state"] != "restored"
        or integrity["complete"] is not True
        or integrity["debug_registers_armed"] is not False
        or integrity["debug_registers_cleared"] is not True
        or integrity["veh_installed"] is not False
        or integrity["veh_removed"] is not True
        or integrity["executable_file_released"] is not True
        or integrity["lua_file_released"] is not True
        or integrity["executable_bytes_modified"] is not False
        or integrity["seams_unchanged"] is not True
    ):
        raise ScorePositioningX87Error("x87 observer was not fully restored")

    observation = snapshot["observation"]
    if not isinstance(observation, Mapping):
        raise ScorePositioningX87Error("snapshot.observation must be an object")
    _exact_keys(
        observation,
        {
            "seq",
            "thread_id",
            "context_flags",
            "control_word",
            "rounding_control_bits",
            "rounding_mode",
            "lua_conversion_rva",
            "integer_helper_return_rva",
            "named_invoker_return_rva",
            "score_positioning_return_rva",
        },
        "snapshot.observation",
    )
    if observation["seq"] != 1:
        raise ScorePositioningX87Error("x87 observation sequence differs")
    _integer(observation["thread_id"], "snapshot.observation.thread_id", minimum=1)
    _integer(
        observation["context_flags"],
        "snapshot.observation.context_flags",
        minimum=1,
    )
    control_word = _integer(
        observation["control_word"],
        "snapshot.observation.control_word",
        minimum=0,
        maximum=0xFFFF,
    )
    rounding_bits = _integer(
        observation["rounding_control_bits"],
        "snapshot.observation.rounding_control_bits",
        minimum=0,
        maximum=0x0C00,
    )
    rounding_mode = ROUNDING_BITS_TO_MODE.get(rounding_bits)
    if (
        rounding_bits != control_word & 0x0C00
        or observation["rounding_mode"] != rounding_mode
        or observation["lua_conversion_rva"] != 0x00001729
        or observation["integer_helper_return_rva"] != 0x000F8B8F
        or observation["named_invoker_return_rva"] != 0x000F87E2
        or observation["score_positioning_return_rva"] != 0x000F78DA
    ):
        raise ScorePositioningX87Error("x87 observation boundary or mode differs")

    summary = snapshot["summary"]
    if not isinstance(summary, Mapping):
        raise ScorePositioningX87Error("snapshot.summary must be an object")
    _exact_keys(
        summary,
        {"record_count", "thread_count", "observed_rounding_mode"},
        "snapshot.summary",
    )
    if dict(summary) != {
        "record_count": 1,
        "thread_count": 1,
        "observed_rounding_mode": rounding_mode,
    }:
        raise ScorePositioningX87Error("x87 snapshot summary differs")
    return {
        "capture_id": snapshot["capture_id"],
        "identity": dict(identity),
        "snapshot_sha256": _sha256(snapshot),
        "module_sha256": observed_module_sha256,
        "control_word": control_word,
        "rounding_control_bits": rounding_bits,
        "rounding_mode": rounding_mode,
        "ignored_non_score_count": integrity["ignored_non_score_count"],
    }


def analyze_score_positioning_x87_snapshot(
    snapshot: Mapping[str, Any],
    *,
    build_receipt: Mapping[str, Any],
    observed_module_sha256: str,
) -> dict[str, Any]:
    """Return the narrow conclusion justified by one exact runtime hit."""
    validated = validate_score_positioning_x87_snapshot(
        snapshot,
        build_receipt=build_receipt,
        observed_module_sha256=observed_module_sha256,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": ANALYSIS_KIND,
        "capture_id": validated["capture_id"],
        "identity": validated["identity"],
        "snapshot_sha256": validated["snapshot_sha256"],
        "module_sha256": validated["module_sha256"],
        "observation": {
            "control_word": validated["control_word"],
            "rounding_control_bits": validated["rounding_control_bits"],
            "rounding_mode": validated["rounding_mode"],
            "ignored_non_score_count": validated["ignored_non_score_count"],
            "boundary": "lua5.1.dll!lua_tointeger immediately before FISTP",
            "frame_chain": [
                "ScorePositioning",
                "named_integer_invoker",
                "integer_helper",
                "lua_tointeger",
            ],
        },
        "claims": {
            "proven": [
                "The observed ScorePositioning integer conversion used the recorded x87 rounding-control mode at the exact FISTP boundary.",
                "The one-shot current-thread debug register and VEH were removed, both pinned files were released, and both image seams remained unchanged before publication.",
            ],
            "not_proven": [
                "That every future process or non-ScorePositioning Lua integer conversion uses the same rounding-control mode.",
                "A complete native enemy tournament replay; this observation resolves only its ScorePositioning integer-conversion mode.",
            ],
        },
    }
