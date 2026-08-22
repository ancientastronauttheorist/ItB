from __future__ import annotations

import copy

import pytest

from src.observatory.callback_trial_result import (
    CallbackTrialResultError,
    compare_callback_trial_results,
    validate_callback_trial_result,
)


def _runtime(now: int, *, turn: int, phase: str) -> dict:
    return {
        "now_epoch": now,
        "mission_id": "Mission_Test",
        "turn": turn,
        "phase": phase,
        "timeline_fingerprint": "1" * 64,
        "master_seed": -17,
        "region_id": "Archive_A",
        "ai_seed_fingerprint": "2" * 64,
    }


def _result(condition: str) -> dict:
    exact = condition == "exact_hook"
    return {
        "schema_version": 1,
        "kind": "observatory_callback_trial_result",
        "host_version": "observatory-callback-trial-host/2",
        "capture_track": "owner_local_modified",
        "condition": condition,
        "capsule_sha256": "a" * 64,
        "arm_packet_sha256": "b" * 64,
        "binding_manifest_sha256": "c" * 64,
        "callback_join_sha256": "d" * 64,
        "capture_id": "callback-score-001",
        "checkpoint_seq": 0,
        "callback_family": "score_positioning",
        "status": "complete",
        "error": "",
        "runtime_before": _runtime(
            1001 if exact else 2001,
            turn=2,
            phase="combat_enemy",
        ),
        "runtime_after": _runtime(
            1002 if exact else 2002,
            turn=3,
            phase="combat_player",
        ),
        "controller_status": {
            "consumed": True,
            "prepared": True,
            "activated": False,
            "written": exact,
        },
        "raw_written": exact,
        "raw_event_count": 3 if exact else 0,
        "attempted_calls": 3 if exact else 0,
        "serialization_errors": 0,
        "slot_count": 65,
        "slots_restored": True,
    }


def test_validate_and_compare_useful_pair():
    control = validate_callback_trial_result(_result("control"))
    exact = validate_callback_trial_result(_result("exact_hook"))
    comparison = compare_callback_trial_results(
        control,
        exact,
        expected_capsule_sha256="a" * 64,
        expected_arm_packet_sha256="b" * 64,
    )
    assert comparison["status"] == "matched"
    assert comparison["exact_hook_event_count"] == 3
    assert comparison["both_restored"] is True


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("slots_restored", False, "not complete and restored"),
        ("raw_written", False, "lacks raw output"),
        ("serialization_errors", 1, "adapter errors"),
    ],
)
def test_exact_result_rejects_incomplete_evidence(field, value, match):
    exact = _result("exact_hook")
    exact[field] = value
    if field == "serialization_errors":
        with pytest.raises(CallbackTrialResultError, match=match):
            compare_callback_trial_results(
                _result("control"),
                exact,
                expected_capsule_sha256="a" * 64,
                expected_arm_packet_sha256="b" * 64,
            )
    else:
        with pytest.raises(CallbackTrialResultError, match=match):
            validate_callback_trial_result(exact)


def test_pair_rejects_zero_events_and_identity_drift():
    exact = _result("exact_hook")
    exact["raw_event_count"] = 0
    exact["attempted_calls"] = 0
    with pytest.raises(CallbackTrialResultError, match="observed no usable calls"):
        compare_callback_trial_results(
            _result("control"),
            exact,
            expected_capsule_sha256="a" * 64,
            expected_arm_packet_sha256="b" * 64,
        )

    drifted = copy.deepcopy(_result("exact_hook"))
    drifted["runtime_after"]["turn"] = 4
    with pytest.raises(CallbackTrialResultError, match="exactly one enemy decision cycle"):
        validate_callback_trial_result(drifted)
