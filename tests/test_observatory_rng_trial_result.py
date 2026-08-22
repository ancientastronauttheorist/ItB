from __future__ import annotations

import copy
import json

import pytest

from scripts.itb_observatory_rng_trial import main as rng_trial_cli
from src.observatory.rng_trial_result import (
    RngTrialResultError,
    compare_rng_trial_results,
    result_sha256,
    validate_rng_trial_result,
)


CAPSULE_SHA = "a" * 64
ARM_SHA = "b" * 64


def _runtime(now: int = 1001) -> dict:
    return {
        "now_epoch": now,
        "mission_id": "Mission_Test",
        "turn": 2,
        "phase": "combat_enemy",
        "timeline_fingerprint": "c" * 64,
        "master_seed": -17,
        "region_id": "region0",
        "ai_seed_fingerprint": "d" * 64,
    }


def _result(condition: str) -> dict:
    exact = condition == "exact_hook"
    return {
        "schema_version": 2,
        "kind": "observatory_rng_trial_result",
        "host_version": "observatory-rng-trial-host/2",
        "capture_track": "owner_local_modified",
        "condition": condition,
        "capsule_sha256": CAPSULE_SHA,
        "arm_packet_sha256": ARM_SHA,
        "capture_id": "rng-pair-001",
        "checkpoint_seq": 0,
        "status": "complete",
        "error": "",
        "probe": {"kind": "random_int", "upper_bound": 7, "result": 3},
        "rng_control": {
            "kind": "build_keyed_seed",
            "seed": 0,
            "expected_result": 3,
            "helper_version": "observatory-rng-seed-helper/1",
            "helper_sha256": "e" * 64,
            "seed_applied": True,
        },
        "runtime_before": _runtime(1001),
        "runtime_after": _runtime(1002),
        "controller_status": {
            "consumed": True,
            "prepared": True,
            "activated": False,
            "written": exact,
        },
        "raw_written": exact,
        "target_restored": True,
    }


def _bool_result(condition: str) -> dict:
    result = _result(condition)
    result["probe"] = {"kind": "random_bool", "argument": 2, "result": True}
    result["rng_control"].update(seed=0, expected_result=True)
    return result


def test_validate_and_compare_exact_pair():
    control = validate_rng_trial_result(
        _result("control"),
        expected_condition="control",
        expected_capsule_sha256=CAPSULE_SHA,
        expected_arm_packet_sha256=ARM_SHA,
    )
    exact = validate_rng_trial_result(
        _result("exact_hook"),
        expected_condition="exact_hook",
        expected_capsule_sha256=CAPSULE_SHA,
        expected_arm_packet_sha256=ARM_SHA,
    )
    comparison = compare_rng_trial_results(
        control,
        exact,
        expected_capsule_sha256=CAPSULE_SHA,
        expected_arm_packet_sha256=ARM_SHA,
    )
    assert comparison["status"] == "matched"
    assert comparison["capture_track"] == "owner_local_modified"
    assert comparison["probe"]["result"] == 3
    assert comparison["runtime_identity"]["mission_id"] == "Mission_Test"
    assert comparison["control_result_sha256"] == result_sha256(control)
    assert comparison["exact_hook_result_sha256"] == result_sha256(exact)


def test_validate_and_compare_legacy_random_int_pair():
    control = _result("control")
    exact = _result("exact_hook")
    control["schema_version"] = 1
    exact["schema_version"] = 1

    comparison = compare_rng_trial_results(
        control,
        exact,
        expected_capsule_sha256=CAPSULE_SHA,
        expected_arm_packet_sha256=ARM_SHA,
    )

    assert comparison["status"] == "matched"
    assert comparison["schema_version"] == 2


def test_legacy_result_schema_rejects_bool_and_mixed_schema_pair():
    legacy_bool = _bool_result("control")
    legacy_bool["schema_version"] = 1
    with pytest.raises(RngTrialResultError, match="only supports random_int"):
        validate_rng_trial_result(legacy_bool)

    legacy_int = _result("control")
    legacy_int["schema_version"] = 1
    with pytest.raises(RngTrialResultError, match="schema_version mismatch"):
        compare_rng_trial_results(
            legacy_int,
            _result("exact_hook"),
            expected_capsule_sha256=CAPSULE_SHA,
            expected_arm_packet_sha256=ARM_SHA,
        )


def test_validate_and_compare_seeded_random_bool_pair():
    comparison = compare_rng_trial_results(
        _bool_result("control"),
        _bool_result("exact_hook"),
        expected_capsule_sha256=CAPSULE_SHA,
        expected_arm_packet_sha256=ARM_SHA,
    )

    assert comparison["status"] == "matched"
    assert comparison["probe"] == {
        "kind": "random_bool",
        "argument": 2,
        "result": True,
    }
    assert comparison["rng_control"]["expected_result"] is True


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(status="failed"), "did not complete"),
        (lambda value: value.update(target_restored=False), "not restored"),
        (lambda value: value.update(raw_written=True), "raw-write state"),
        (
            lambda value: value["rng_control"].update(seed_applied=False),
            "seed was not applied",
        ),
        (
            lambda value: value["runtime_after"].update(turn=3),
            "identity changed",
        ),
        (
            lambda value: value["controller_status"].update(activated=True),
            "safe state",
        ),
        (lambda value: value.update(capture_track="unknown"), "capture track"),
    ],
)
def test_result_validation_fails_closed(mutation, message):
    result = _result("control")
    mutation(result)
    with pytest.raises(RngTrialResultError, match=message):
        validate_rng_trial_result(result)


def test_pair_comparison_rejects_probe_or_runtime_drift():
    changed_probe = _result("exact_hook")
    changed_probe["probe"]["result"] = 4
    changed_probe["rng_control"].update(seed=11, expected_result=4)
    with pytest.raises(RngTrialResultError, match="probe mismatch"):
        compare_rng_trial_results(
            _result("control"),
            changed_probe,
            expected_capsule_sha256=CAPSULE_SHA,
            expected_arm_packet_sha256=ARM_SHA,
        )

    changed_runtime = _result("exact_hook")
    changed_runtime["runtime_before"]["master_seed"] = -18
    changed_runtime["runtime_after"]["master_seed"] = -18
    with pytest.raises(RngTrialResultError, match="runtime_before"):
        compare_rng_trial_results(
            _result("control"),
            changed_runtime,
            expected_capsule_sha256=CAPSULE_SHA,
            expected_arm_packet_sha256=ARM_SHA,
        )


def test_compare_results_cli_emits_strict_comparison(tmp_path, capsys):
    control = tmp_path / "control.json"
    exact = tmp_path / "exact.json"
    control.write_text(json.dumps(_result("control")), encoding="utf-8")
    exact.write_text(json.dumps(_result("exact_hook")), encoding="utf-8")
    assert rng_trial_cli(
        [
            "compare-results",
            "--control",
            str(control),
            "--exact-hook",
            str(exact),
            "--capsule-sha256",
            CAPSULE_SHA,
            "--arm-sha256",
            ARM_SHA,
        ]
    ) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["kind"] == "observatory_rng_trial_comparison"
    assert output["status"] == "matched"


def test_result_hash_is_type_sensitive():
    result = _result("control")
    digest = result_sha256(result)
    mutated = copy.deepcopy(result)
    mutated["probe"]["result"] = False
    with pytest.raises(RngTrialResultError):
        result_sha256(mutated)
    assert digest == result_sha256(result)
