from __future__ import annotations

from copy import deepcopy

import pytest

from src.observatory.msvc_rng_replay import (
    advance_state,
    result_from_advanced_state,
)
from src.observatory.spawn_coordinate_capsule_hw import (
    EXPECTED_BASE_PLAN_SHA256,
    EXPECTED_BASE_SOURCE_SHA256,
    EXPECTED_BUILD_RECEIPT_SHA256,
    EXPECTED_BOUNDARY_MAP_SHA256,
    EXPECTED_EXECUTABLE_SHA256,
    EXPECTED_FALLBACK_PREBYTES_SHA256,
    EXPECTED_INVENTORY_SHA256,
    EXPECTED_MODULE_SHA256,
    EXPECTED_PLAN_SHA256,
    EXPECTED_POSITION_BOUNDARY_SHA256,
    EXPECTED_RNG_OWNER_SHA256,
    EXPECTED_RNG_RETURN_MAP_SHA256,
    EXPECTED_SCHEDULER_PREBYTES_SHA256,
    EXPECTED_SELECTOR_ENTRY_PREBYTES_SHA256,
    EXPECTED_SELECTOR_REGION_SHA256,
    EXPECTED_SOURCE_SHA256,
    EXPECTED_SPAWN_BOUNDARY_SHA256,
    EXPECTED_STANDARD_PREBYTES_SHA256,
    SpawnCoordinateCapsuleHwError,
    correlate_spawn_coordinate_capsule_snapshot,
    validate_spawn_coordinate_capsule_build_identity,
    validate_spawn_coordinate_capsule_snapshot,
)


MODULE_SHA256 = "a" * 64


def _receipt() -> dict:
    return {
        "schema_version": 1,
        "kind": "observatory_spawn_coordinate_capsule_hw_observer_build",
        "observer_version": "observatory-spawn-coordinate-capsule-hw-observer/2",
        "build_id": "13725832",
        "architecture": "x86",
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        "executable_size": 5_530_112,
        "module_sha256": MODULE_SHA256,
        "module_filename": (
            "itb_observatory_spawn_coordinate_capsule_hw_observer_"
            f"{MODULE_SHA256}.dll"
        ),
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "hardware_breakpoint_plan_sha256": EXPECTED_PLAN_SHA256,
        "base_source_sha256": EXPECTED_BASE_SOURCE_SHA256,
        "base_hardware_breakpoint_plan_sha256": EXPECTED_BASE_PLAN_SHA256,
        "inventory_canonical_sha256": EXPECTED_INVENTORY_SHA256,
        "boundary_map_canonical_sha256": EXPECTED_BOUNDARY_MAP_SHA256,
        "rng_return_map_sha256": EXPECTED_RNG_RETURN_MAP_SHA256,
        "spawn_candidate_boundary_sha256": EXPECTED_SPAWN_BOUNDARY_SHA256,
        "position_observations_boundary_sha256": EXPECTED_POSITION_BOUNDARY_SHA256,
        "selector_region_sha256": EXPECTED_SELECTOR_REGION_SHA256,
        "selector_entry_prebytes_sha256": EXPECTED_SELECTOR_ENTRY_PREBYTES_SHA256,
        "scheduler_prebytes_sha256": EXPECTED_SCHEDULER_PREBYTES_SHA256,
        "selector_fallback_prebytes_sha256": EXPECTED_FALLBACK_PREBYTES_SHA256,
        "selector_standard_prebytes_sha256": EXPECTED_STANDARD_PREBYTES_SHA256,
        "rng_state_owner_sha256": EXPECTED_RNG_OWNER_SHA256,
        "loaded_or_armed": False,
        "executable_bytes_modified": False,
        "compile_flags": ["/arch:IA32", "/Qvec-"],
        "reproducibility": {
            "independent_build_count": 2,
            "module_bytes_identical": True,
            "attestations_identical": True,
        },
        "source_attestation": {
            "v1_source_unchanged": True,
            "executable_mutation_api_text_absent": True,
            "private_debug_register_transition_present": True,
            "fixed_capsule_ring_present": True,
            "pointer_values_published": False,
        },
        "machine_attestation": {
            "loader_entry_absent": True,
            "executable_mutation_api_imports_absent": True,
            "veh": {
                "direct_or_indirect_call_count": 0,
                "windows_api_call_count": 0,
                "x87_mmx_sse_avx_instruction_count": 0,
                "leading_int3_padding_size": 0,
            },
        },
    }


def _draw(kind: str, seq: int, raw_rng: int) -> dict:
    count = 4
    selected_index = raw_rng % count
    candidates = [{"x": index, "y": seq} for index in range(count)]
    return {
        "kind": kind,
        "seq": seq,
        "candidate_count": count,
        "selected_index": selected_index,
        "rng_quotient": raw_rng // count,
        "raw_rng": raw_rng,
        "selected_x": candidates[selected_index]["x"],
        "selected_y": candidates[selected_index]["y"],
        "candidates": candidates,
    }


def _snapshot() -> dict:
    receipt = _receipt()
    state_before = 0x12345678
    state_after = advance_state(state_before)
    selector_raw = result_from_advanced_state(state_after)
    draws = [
        _draw("scheduler_draw", 0, 101),
        _draw("selector_standard_draw", 1, selector_raw),
    ]
    tiles = []
    block_spawn = []
    for x in range(8):
        for y in range(8):
            occupant_ids = [17] if [x, y] == [3, 3] else []
            tiles.append(
                {
                    "x": x,
                    "y": y,
                    "terrain": 0,
                    "pod_state": 1 if [x, y] == [7, 7] else 0,
                    "item_present": [x, y] == [4, 4],
                    "acid": [x, y] == [2, 2],
                    "dangerous_flag": [x, y] == [1, 1],
                    "occupancy_count": len(occupant_ids),
                    "occupant_ids": occupant_ids,
                }
            )
            block_spawn.append({"x": x, "y": y, "value": int(y == 0)})
    selector = draws[1]
    capsules = [
        {
            "seq": 0,
            "draw_seq": 1,
            "selector_kind": "selector_standard_draw",
            "board_width": 8,
            "board_height": 8,
            "board_turn": 1,
            "pawn_id": 9,
            "pawn_team": 1,
            "rng_state_before": f"0x{state_before:08x}",
            "rng_state_after": f"0x{state_after:08x}",
            "raw_rng": selector_raw,
            "selected_index": selector["selected_index"],
            "selected_x": selector["selected_x"],
            "selected_y": selector["selected_y"],
            "block_spawn_values": block_spawn,
            "spawn_markers": [{"x": 0, "y": 0}],
            "dangerous_points_a": [{"x": 5, "y": 5}],
            "dangerous_points_b": [{"x": 6, "y": 6}],
            "tiles": tiles,
        }
    ]
    return {
        "schema_version": 1,
        "kind": "native_spawn_coordinate_capsule_hw_observer_snapshot",
        "observer_version": "observatory-spawn-coordinate-capsule-hw-observer/2",
        "capture_id": "spawn_capsule_pair001",
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "build_id": "13725832",
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": 5_530_112,
            "inventory_sha256": EXPECTED_INVENTORY_SHA256,
            "boundary_map_sha256": EXPECTED_BOUNDARY_MAP_SHA256,
            "spawn_candidate_boundary_sha256": EXPECTED_SPAWN_BOUNDARY_SHA256,
            "position_observations_boundary_sha256": EXPECTED_POSITION_BOUNDARY_SHA256,
            "hardware_breakpoint_plan_sha256": EXPECTED_PLAN_SHA256,
            "selector_region_sha256": EXPECTED_SELECTOR_REGION_SHA256,
            "selector_entry_prebytes_sha256": EXPECTED_SELECTOR_ENTRY_PREBYTES_SHA256,
            "scheduler_prebytes_sha256": EXPECTED_SCHEDULER_PREBYTES_SHA256,
            "selector_fallback_prebytes_sha256": EXPECTED_FALLBACK_PREBYTES_SHA256,
            "selector_standard_prebytes_sha256": EXPECTED_STANDARD_PREBYTES_SHA256,
            "rng_state_owner_sha256": EXPECTED_RNG_OWNER_SHA256,
        },
        "integrity": {
            "state": "restored",
            "complete": True,
            "overflow_count": 0,
            "candidate_error_count": 0,
            "capsule_error_count": 0,
            "rng_error_count": 0,
            "pairing_error_count": 0,
            "pointer_fault_count": 0,
            "transition_mismatch_count": 0,
            "wrong_thread_count": 0,
            "unexpected_breakpoint_count": 0,
            "torn_record_count": 0,
            "torn_capsule_count": 0,
            "debug_registers_armed": False,
            "debug_registers_cleared": True,
            "veh_installed": False,
            "veh_removed": True,
            "executable_file_released": True,
            "executable_bytes_modified": False,
            "seam_bytes_unchanged": True,
            "addresses_or_pointers_published": False,
        },
        "draw_records": draws,
        "capsules": capsules,
        "summary": {
            "draw_record_count": 2,
            "scheduler_count": 1,
            "selector_fallback_count": 0,
            "selector_standard_count": 1,
            "selector_count": 1,
            "capsule_entry_count": 1,
            "capsule_count": 1,
            "thread_count": 1,
            "last_draw_sequence": 1,
            "last_capsule_sequence": 0,
        },
    }


def _validate(snapshot: dict) -> dict:
    return validate_spawn_coordinate_capsule_snapshot(
        snapshot,
        build_receipt=_receipt(),
        observed_module_sha256=MODULE_SHA256,
    )


def test_capsule_snapshot_validates_board_carriers_rng_and_candidate_pairing():
    result = _validate(_snapshot())

    capsule = result["capsules"][0]
    assert capsule["board"]["dangerous_points"] == [[1, 1], [5, 5], [6, 6]]
    assert capsule["board"]["occupied_points"] == [[3, 3]]
    assert capsule["board"]["tiles"][36]["item_present"] is True
    assert capsule["rng"]["raw_rng"] == result["draw_records"][1]["raw_rng"]
    assert result["claims"] == {
        "selector_entry_board_carriers_captured": True,
        "shared_rng_state_exact": True,
        "candidate_vector_pairing_exact": True,
        "transient_dead_noncorpse_occupancy_resolved": False,
        "pawn_path_profile_at_entry_resolved": False,
        "complete_future_forecast": False,
    }
    assert len(result["evidence_sha256"]) == 64


def test_capsule_snapshot_rejects_rng_transition_or_draw_replay_drift():
    snapshot = _snapshot()
    snapshot["capsules"][0]["rng_state_after"] = "0x00000000"
    with pytest.raises(SpawnCoordinateCapsuleHwError, match="RNG transition"):
        _validate(snapshot)

    snapshot = _snapshot()
    snapshot["capsules"][0]["raw_rng"] += 1
    with pytest.raises(SpawnCoordinateCapsuleHwError, match="draw replay"):
        _validate(snapshot)


def test_capsule_snapshot_rejects_missing_or_reordered_board_carriers():
    snapshot = _snapshot()
    snapshot["capsules"][0]["tiles"].pop()
    with pytest.raises(SpawnCoordinateCapsuleHwError, match="all 64 tiles"):
        _validate(snapshot)

    snapshot = _snapshot()
    snapshot["capsules"][0]["block_spawn_values"][1]["y"] = 2
    with pytest.raises(SpawnCoordinateCapsuleHwError, match="x-major order"):
        _validate(snapshot)


def test_capsule_snapshot_rejects_occupancy_or_point_vector_drift():
    snapshot = _snapshot()
    snapshot["capsules"][0]["tiles"][27]["occupancy_count"] = 2
    with pytest.raises(SpawnCoordinateCapsuleHwError, match="length differs"):
        _validate(snapshot)

    snapshot = _snapshot()
    snapshot["capsules"][0]["dangerous_points_a"].append({"x": 5, "y": 5})
    with pytest.raises(SpawnCoordinateCapsuleHwError, match="duplicate points"):
        _validate(snapshot)


def test_capsule_snapshot_rejects_selector_pairing_or_summary_drift():
    snapshot = _snapshot()
    snapshot["capsules"][0]["draw_seq"] = 0
    with pytest.raises(SpawnCoordinateCapsuleHwError, match="selector pairing"):
        _validate(snapshot)

    snapshot = _snapshot()
    snapshot["summary"]["capsule_count"] = 2
    with pytest.raises(SpawnCoordinateCapsuleHwError, match="summary differs"):
        _validate(snapshot)


def test_capsule_snapshot_rejects_build_or_restoration_safety_drift():
    receipt = _receipt()
    receipt["machine_attestation"]["veh"]["x87_mmx_sse_avx_instruction_count"] = 1
    with pytest.raises(SpawnCoordinateCapsuleHwError, match="safety attestation"):
        validate_spawn_coordinate_capsule_snapshot(
            _snapshot(),
            build_receipt=receipt,
            observed_module_sha256=MODULE_SHA256,
        )

    snapshot = deepcopy(_snapshot())
    snapshot["integrity"]["addresses_or_pointers_published"] = True
    with pytest.raises(SpawnCoordinateCapsuleHwError, match="not fully restored"):
        _validate(snapshot)


def test_capsule_live_preflight_requires_exact_module_and_receipt_bytes():
    receipt = _receipt()
    receipt["module_sha256"] = EXPECTED_MODULE_SHA256
    receipt["module_filename"] = (
        "itb_observatory_spawn_coordinate_capsule_hw_observer_"
        f"{EXPECTED_MODULE_SHA256}.dll"
    )

    identity = validate_spawn_coordinate_capsule_build_identity(
        receipt,
        observed_module_sha256=EXPECTED_MODULE_SHA256,
        observed_build_receipt_sha256=EXPECTED_BUILD_RECEIPT_SHA256,
    )

    assert identity["module_sha256"] == EXPECTED_MODULE_SHA256
    with pytest.raises(SpawnCoordinateCapsuleHwError, match="receipt bytes differ"):
        validate_spawn_coordinate_capsule_build_identity(
            receipt,
            observed_module_sha256=EXPECTED_MODULE_SHA256,
            observed_build_receipt_sha256="0" * 64,
        )


def test_capsule_correlation_requires_exact_next_turn_spawn_marker_order():
    snapshot = _snapshot()
    selected = snapshot["capsules"][0]
    result = correlate_spawn_coordinate_capsule_snapshot(
        snapshot,
        {
            "mission_id": "Mission_Power",
            "phase": "combat_player",
            "turn": 2,
            "spawning_tiles": [[selected["selected_x"], selected["selected_y"]]],
        },
        build_receipt=_receipt(),
        observed_module_sha256=MODULE_SHA256,
    )

    assert result["status"] == "correlated"
    assert result["native"]["selected_spawn_coordinates"] == result["bridge"][
        "spawning_tiles"
    ]
    assert result["native"]["capsule_board_turns"] == [1]


def test_capsule_correlation_rejects_stale_turn_or_different_spawn_marker():
    snapshot = _snapshot()
    result = correlate_spawn_coordinate_capsule_snapshot(
        snapshot,
        {
            "mission_id": "Mission_Power",
            "phase": "combat_player",
            "turn": 1,
            "spawning_tiles": [[7, 7]],
        },
        build_receipt=_receipt(),
        observed_module_sha256=MODULE_SHA256,
    )

    assert result["status"] == "rejected"
    assert result["reasons"] == [
        "bridge_turn_did_not_advance",
        "selector_results_differ_from_spawn_markers",
    ]
