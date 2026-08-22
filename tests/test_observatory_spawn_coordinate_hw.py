from __future__ import annotations

from copy import deepcopy

import pytest

from src.observatory.spawn_coordinate_hw import (
    EXPECTED_PLAN_SHA256,
    SpawnCoordinateHwError,
    correlate_spawn_coordinate_snapshot,
    validate_spawn_coordinate_snapshot,
)


MODULE_SHA256 = "a" * 64


def _receipt() -> dict:
    return {
        "schema_version": 1,
        "kind": "observatory_spawn_coordinate_hw_observer_build",
        "observer_version": "observatory-spawn-coordinate-hw-observer/1",
        "build_id": "13725832",
        "architecture": "x86",
        "executable_sha256": (
            "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
        ),
        "executable_size": 5_530_112,
        "module_sha256": MODULE_SHA256,
        "hardware_breakpoint_plan_sha256": EXPECTED_PLAN_SHA256,
        "boundary_map_canonical_sha256": (
            "ded91fdf8181b2ae310644ece211f77fecc4393c3cd1c43867cfd353af3d6dc2"
        ),
        "inventory_canonical_sha256": (
            "81fc5d328603c087154c00c8249e9f2e208539b24b7989bd9d805403192aa2b4"
        ),
        "selector_region_sha256": (
            "9746df5a768534c54108600528bce8e0fd152d41e322bf0907dc92a434148904"
        ),
        "scheduler_region_sha256": (
            "639ea27e48757d5c7f08499522d7f8933dc874957f4d00a74bbeec4a6750bd89"
        ),
        "scheduler_prebytes_sha256": (
            "419b08b2e5f923a50b9c561f72289c66c4582a38f35816d8727787cdae8f9ea7"
        ),
        "selector_fallback_prebytes_sha256": (
            "fd2f466614b6c81c7e73fcdb8b000dd72200a8143400bd9528bedc1d69ffd4e6"
        ),
        "selector_standard_prebytes_sha256": (
            "c582fb84bc51ea60cbda9c2b62bbd3a9ef4103d42654486a3569da5f8997f011"
        ),
        "loaded_or_armed": False,
        "executable_bytes_modified": False,
        "reproducibility": {
            "independent_build_count": 2,
            "module_bytes_identical": True,
            "attestations_identical": True,
        },
        "machine_attestation": {
            "loader_entry_absent": True,
            "executable_mutation_api_imports_absent": True,
            "veh": {
                "direct_or_indirect_call_count": 0,
                "windows_api_call_count": 0,
            },
        },
    }


def _snapshot() -> dict:
    receipt = _receipt()
    return {
        "schema_version": 1,
        "kind": "native_spawn_coordinate_hw_observer_snapshot",
        "observer_version": "observatory-spawn-coordinate-hw-observer/1",
        "capture_id": "spawn_coordinate_pair001_armed",
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "build_id": "13725832",
            "executable_sha256": receipt["executable_sha256"],
            "executable_size": receipt["executable_size"],
            "inventory_sha256": receipt["inventory_canonical_sha256"],
            "boundary_map_sha256": receipt["boundary_map_canonical_sha256"],
            "hardware_breakpoint_plan_sha256": EXPECTED_PLAN_SHA256,
            "scheduler_region_sha256": receipt["scheduler_region_sha256"],
            "selector_region_sha256": receipt["selector_region_sha256"],
            "scheduler_prebytes_sha256": receipt[
                "scheduler_prebytes_sha256"
            ],
            "selector_fallback_prebytes_sha256": receipt[
                "selector_fallback_prebytes_sha256"
            ],
            "selector_standard_prebytes_sha256": receipt[
                "selector_standard_prebytes_sha256"
            ],
        },
        "integrity": {
            "state": "restored",
            "complete": True,
            "overflow_count": 0,
            "candidate_error_count": 0,
            "pointer_fault_count": 0,
            "transition_mismatch_count": 0,
            "wrong_thread_count": 0,
            "unexpected_breakpoint_count": 0,
            "torn_record_count": 0,
            "debug_registers_armed": False,
            "debug_registers_cleared": True,
            "veh_installed": False,
            "veh_removed": True,
            "executable_file_released": True,
            "executable_bytes_modified": False,
            "seam_bytes_unchanged": True,
        },
        "records": [
            {
                "kind": "scheduler_draw",
                "seq": 0,
                "candidate_count": 3,
                "selected_index": 2,
                "rng_quotient": 1,
                "raw_rng": 5,
                "selected_x": 3,
                "selected_y": 3,
                "candidates": [
                    {"x": 1, "y": 1},
                    {"x": 2, "y": 2},
                    {"x": 3, "y": 3},
                ],
            },
            {
                "kind": "selector_standard_draw",
                "seq": 1,
                "candidate_count": 2,
                "selected_index": 0,
                "rng_quotient": 2,
                "raw_rng": 4,
                "selected_x": 5,
                "selected_y": 3,
                "candidates": [{"x": 5, "y": 3}, {"x": 6, "y": 5}],
            },
        ],
        "summary": {
            "record_count": 2,
            "scheduler_count": 1,
            "selector_fallback_count": 0,
            "selector_standard_count": 1,
            "selector_count": 1,
            "thread_count": 1,
            "last_sequence": 1,
        },
    }


def _outcome(spawning_tiles: list[list[int]] | None = None) -> dict:
    return {
        "mission_id": "Mission_Power",
        "phase": "combat_player",
        "spawning_tiles": [[5, 3]] if spawning_tiles is None else spawning_tiles,
    }


def test_snapshot_validates_candidate_order_rng_and_selected_coordinate():
    validated = validate_spawn_coordinate_snapshot(
        _snapshot(),
        build_receipt=_receipt(),
        observed_module_sha256=MODULE_SHA256,
    )

    assert [event["raw_rng"] for event in validated["records"]] == [5, 4]
    assert validated["records"][1]["selected"] == [5, 3]
    assert validated["records"][1]["candidates"] == [[5, 3], [6, 5]]


def test_snapshot_rejects_rng_reconstruction_drift():
    snapshot = _snapshot()
    snapshot["records"][1]["raw_rng"] = 5

    with pytest.raises(SpawnCoordinateHwError, match="RNG reconstruction"):
        validate_spawn_coordinate_snapshot(
            snapshot,
            build_receipt=_receipt(),
            observed_module_sha256=MODULE_SHA256,
        )


def test_snapshot_rejects_selected_candidate_drift():
    snapshot = _snapshot()
    snapshot["records"][1]["selected_x"] = 6

    with pytest.raises(SpawnCoordinateHwError, match="selected point"):
        validate_spawn_coordinate_snapshot(
            snapshot,
            build_receipt=_receipt(),
            observed_module_sha256=MODULE_SHA256,
        )


def test_snapshot_rejects_build_or_restoration_drift():
    receipt = _receipt()
    receipt["hardware_breakpoint_plan_sha256"] = "0" * 64
    with pytest.raises(SpawnCoordinateHwError, match="plan_sha256 differs"):
        validate_spawn_coordinate_snapshot(
            _snapshot(),
            build_receipt=receipt,
            observed_module_sha256=MODULE_SHA256,
        )

    snapshot = _snapshot()
    snapshot["integrity"]["debug_registers_cleared"] = False
    with pytest.raises(SpawnCoordinateHwError, match="not fully restored"):
        validate_spawn_coordinate_snapshot(
            snapshot,
            build_receipt=_receipt(),
            observed_module_sha256=MODULE_SHA256,
        )


def test_correlation_matches_final_selector_to_bridge_spawn_marker():
    result = correlate_spawn_coordinate_snapshot(
        _snapshot(),
        _outcome(),
        build_receipt=_receipt(),
        observed_module_sha256=MODULE_SHA256,
    )

    assert result["status"] == "correlated"
    assert result["native"]["raw_rng_sequence"] == [5, 4]
    assert result["native"]["selected_spawn_coordinates"] == [[5, 3]]
    assert result["summary"]["selector_matches_spawn_markers"] is True


def test_correlation_rejects_a_different_bridge_spawn_marker():
    result = correlate_spawn_coordinate_snapshot(
        deepcopy(_snapshot()),
        _outcome([[6, 5]]),
        build_receipt=_receipt(),
        observed_module_sha256=MODULE_SHA256,
    )

    assert result["status"] == "unresolved"
    assert result["reasons"] == ["selector_spawn_marker_mismatch"]
