from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.selected_queue_hw import (
    SelectedQueueHwError,
    correlate_selected_queue_snapshot,
    validate_selected_queue_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE_SHA = "2cf202cc2e58c33651864ed8939b8491cc082048c300d82b63ff3cfbd76a5676"


def _receipt() -> dict:
    return {
        "schema_version": 1,
        "kind": "observatory_selected_queue_hw_observer_build",
        "observer_version": "observatory-selected-queue-hw-observer/1",
        "build_id": "13725832",
        "architecture": "x86",
        "executable_sha256": (
            "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
        ),
        "executable_size": 5_530_112,
        "module_sha256": MODULE_SHA,
        "hardware_breakpoint_plan_sha256": (
            "f99e1ba7b130799f27f6cc4e7a12aa4198bccb624ce994ae6a3fc063c30511b6"
        ),
        "boundary_map_canonical_sha256": (
            "ded91fdf8181b2ae310644ece211f77fecc4393c3cd1c43867cfd353af3d6dc2"
        ),
        "inventory_canonical_sha256": (
            "81fc5d328603c087154c00c8249e9f2e208539b24b7989bd9d805403192aa2b4"
        ),
        "selected_prebytes_sha256": (
            "8e2e44aae1e456d15513da12e097135d095ae740d579715d19e83cb65c35650b"
        ),
        "queue_prebytes_sha256": (
            "f63c44a5d0405f6e008755d711095ec30ac330c6b1bfcfbb43340ca8b0ed84b3"
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
    return {
        "schema_version": 1,
        "kind": "native_selected_queue_hw_observer_snapshot",
        "observer_version": "observatory-selected-queue-hw-observer/1",
        "capture_id": "selected-armed-01",
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "build_id": "13725832",
            "executable_sha256": (
                "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
            ),
            "executable_size": 5_530_112,
            "inventory_sha256": (
                "81fc5d328603c087154c00c8249e9f2e208539b24b7989bd9d805403192aa2b4"
            ),
            "boundary_map_sha256": (
                "ded91fdf8181b2ae310644ece211f77fecc4393c3cd1c43867cfd353af3d6dc2"
            ),
            "hardware_breakpoint_plan_sha256": (
                "f99e1ba7b130799f27f6cc4e7a12aa4198bccb624ce994ae6a3fc063c30511b6"
            ),
            "selected_prebytes_sha256": (
                "8e2e44aae1e456d15513da12e097135d095ae740d579715d19e83cb65c35650b"
            ),
            "queue_prebytes_sha256": (
                "f63c44a5d0405f6e008755d711095ec30ac330c6b1bfcfbb43340ca8b0ed84b3"
            ),
        },
        "integrity": {
            "state": "restored",
            "complete": True,
            "overflow_count": 0,
            "ordering_error_count": 0,
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
                "kind": "selected_record",
                "seq": 0,
                "pair_index": 0,
                "pawn_id": 1300,
                "current_weapon_raw": 0,
                "base_current_weapon_raw": 0,
                "ai_dest_x": 4,
                "ai_dest_y": 3,
                "ai_target_x": 4,
                "ai_target_y": 2,
                "selected_field_4_raw": 7,
                "selected_field_5_raw": 9,
            },
            {
                "kind": "queued_action",
                "seq": 1,
                "pair_index": 0,
                "pawn_id": 1300,
                "current_weapon_raw": 0,
                "base_current_weapon_raw": 0,
                "target_x": 4,
                "target_y": 2,
                "origin_x": 4,
                "origin_y": 3,
                "queued_shot_x": 4,
                "queued_shot_y": 2,
                "queued_skill_raw": 0,
            },
        ],
        "summary": {
            "record_count": 2,
            "selected_count": 1,
            "queue_count": 1,
            "pair_count": 1,
            "thread_count": 1,
            "last_sequence": 1,
            "pending_selection": False,
        },
    }


def _outcome() -> dict:
    return {
        "mission_id": "Mission_Power",
        "phase": "combat_player",
        "spawning_tiles": [],
        "environment_danger": [],
        "environment_danger_v2": [],
        "targeted_tiles": [[4, 1]],
        "units": [
            {
                "uid": 1300,
                "team": 6,
                "type": "Firefly1",
                "x": 4,
                "y": 3,
                "has_queued_attack": True,
            }
        ],
    }


def test_complete_pair_validates_and_correlates_to_bridge_queue():
    validated = validate_selected_queue_snapshot(
        _snapshot(), build_receipt=_receipt(), observed_module_sha256=MODULE_SHA
    )
    assert validated["selected"]["pawn_id"] == 1300

    result = correlate_selected_queue_snapshot(
        _snapshot(),
        _outcome(),
        build_receipt=_receipt(),
        observed_module_sha256=MODULE_SHA,
    )
    assert result["status"] == "correlated"
    assert result["summary"] == {
        "native_pair_count": 1,
        "internal_field_matches": True,
        "bridge_queue_matches": True,
        "correlated": True,
    }
    assert result["bridge"]["queue_corroboration"] == "targeted_tiles_ray"


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("integrity", "debug_registers_cleared"), False, "fully restored"),
        (("summary", "pair_count"), 2, "one exact"),
        (("identity", "build_id"), "other", "identity differs"),
    ],
)
def test_integrity_count_and_identity_drift_fail_closed(path, value, message):
    snapshot = _snapshot()
    snapshot[path[0]][path[1]] = value
    with pytest.raises(SelectedQueueHwError, match=message):
        validate_selected_queue_snapshot(
            snapshot,
            build_receipt=_receipt(),
            observed_module_sha256=MODULE_SHA,
        )


def test_native_or_bridge_queue_drift_is_unresolved_not_reinterpreted():
    snapshot = _snapshot()
    snapshot["records"][1]["queued_skill_raw"] = 1
    outcome = _outcome()
    outcome["units"][0]["queued_target_raw"] = [4, 1]

    result = correlate_selected_queue_snapshot(
        snapshot,
        outcome,
        build_receipt=_receipt(),
        observed_module_sha256=MODULE_SHA,
    )
    assert result["status"] == "unresolved"
    assert result["reasons"] == [
        "selected_weapon_queue_skill_mismatch",
        "bridge_queued_target_mismatch",
    ]


def test_missing_queue_fields_require_an_independent_matching_attack_ray():
    outcome = _outcome()
    outcome["targeted_tiles"] = [[5, 3]]

    result = correlate_selected_queue_snapshot(
        _snapshot(),
        outcome,
        build_receipt=_receipt(),
        observed_module_sha256=MODULE_SHA,
    )
    assert result["status"] == "unresolved"
    assert result["reasons"] == ["bridge_target_direction_mismatch"]


def test_committed_build_receipt_matches_the_validator_when_present():
    receipt_path = ROOT / "data" / "observatory" / "native" / (
        "windows_build_13725832_31fe35265598_selected_queue_hw_observer_receipt.json"
    )
    if not receipt_path.exists():
        pytest.skip("build receipt is added after reproducible Windows build")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    validate_selected_queue_snapshot(
        _snapshot(), build_receipt=receipt, observed_module_sha256=MODULE_SHA
    )
