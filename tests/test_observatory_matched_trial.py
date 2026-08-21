"""Tests for the offline control-versus-exact-hook receipt boundary."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.observatory.matched_trial import (
    MatchedTrialError,
    compare_matched_receipts,
    contract_sha256,
    load_json_contract,
    validate_suite_contract,
    validate_trial_receipt,
)


def _sha(number: int) -> str:
    return f"{number:064x}"


def _suite() -> dict:
    return {
        "schema_version": 1,
        "kind": "observatory_matched_trial_suite",
        "suite_id": "rng-global-neutrality-01",
        "pair_nonce": _sha(1),
        "artifact_hashes": {
            "build_identity_sha256": _sha(2),
            "inventory_sha256": _sha(3),
            "controller_sha256": _sha(4),
            "helper_sha256": _sha(5),
            "hook_sha256": _sha(6),
        },
        "scenario_sha256": _sha(7),
        "start_state_sha256": _sha(8),
        "restore_expected_sha256": _sha(9),
    }


def _receipt(condition: str, nonce: int, *, timing_offset: int = 0) -> dict:
    suite = _suite()
    return {
        "schema_version": 1,
        "kind": "observatory_matched_trial_receipt",
        "suite": suite,
        "condition": condition,
        "receipt_nonce": _sha(nonce),
        "preflight": {
            "ready": True,
            "build_identity_sha256": suite["artifact_hashes"]["build_identity_sha256"],
            "inventory_sha256": suite["artifact_hashes"]["inventory_sha256"],
            "start_state_sha256": suite["start_state_sha256"],
        },
        "completion": {"scenario_complete": True, "receipt_complete": True},
        "restore": {
            "attempted": True,
            "succeeded": True,
            "restored_sha256": suite["restore_expected_sha256"],
        },
        "post_bytes": {
            "verified": True,
            "sha256": suite["restore_expected_sha256"],
        },
        "output": {
            "outcome": "completed",
            "seed": _sha(10),
            "queue": _sha(11),
            "spawn": _sha(12),
            "crash": {"observed": False, "signature_sha256": None},
            "counters": {
                "mission_ticks": 8,
                "enemy_decisions": 3,
                "queued_actions": 3,
                "spawn_events": 2,
            },
            "timing": {
                "wall_duration_ms": 100 + timing_offset,
                "max_tick_ms": 18 + timing_offset,
                "total_ticks": 8,
            },
        },
    }


def test_validate_contracts_are_canonical_and_digest_stable():
    suite = validate_suite_contract(_suite())
    receipt = validate_trial_receipt(_receipt("control", 20), expected_suite=suite)

    assert receipt["suite"] == suite
    assert contract_sha256(suite) == contract_sha256(copy.deepcopy(suite))
    assert contract_sha256(receipt) == contract_sha256(copy.deepcopy(receipt))


def test_comparator_accepts_only_timing_difference_and_reports_it():
    comparison = compare_matched_receipts(
        _receipt("control", 20),
        _receipt("exact_hook", 21, timing_offset=5),
        expected_suite=_suite(),
    )

    assert comparison["status"] == "matched"
    assert comparison["timing"]["wall_duration_delta_ms"] == 5
    assert comparison["timing"]["max_tick_delta_ms"] == 5
    assert comparison["semantic_output"]["queue"] == _sha(11)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("output", "seed"), _sha(99), "semantic output drift"),
        (("output", "queue"), _sha(99), "semantic output drift"),
        (("output", "spawn"), _sha(99), "semantic output drift"),
        (("output", "counters", "spawn_events"), 99, "semantic output drift"),
        (("output", "timing", "total_ticks"), 99, "semantic output drift"),
        (("preflight", "ready"), False, "failed preflight"),
        (("completion", "receipt_complete"), False, "torn or incomplete"),
        (("restore", "succeeded"), False, "restore failure"),
        (("post_bytes", "verified"), False, "post-byte verification"),
        (("output", "outcome"), "failed", "did not complete"),
        (("output", "crash"), {"observed": True, "signature_sha256": _sha(98)}, "reports a crash"),
    ],
)
def test_comparator_rejects_drift_and_failed_receipts(path, value, message):
    control = _receipt("control", 20)
    exact_hook = _receipt("exact_hook", 21)
    cursor = exact_hook
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value

    with pytest.raises(MatchedTrialError, match=message):
        compare_matched_receipts(control, exact_hook, expected_suite=_suite())


def test_validator_rejects_unknown_fields_bad_hash_and_suite_mismatch():
    unknown = _receipt("control", 20)
    unknown["unexpected"] = True
    with pytest.raises(MatchedTrialError, match="unknown fields"):
        validate_trial_receipt(unknown)

    bad_hash = _suite()
    bad_hash["artifact_hashes"]["hook_sha256"] = "UPPERCASE"
    with pytest.raises(MatchedTrialError, match="lowercase SHA-256"):
        validate_suite_contract(bad_hash)

    mismatched = _receipt("control", 20)
    mismatched["suite"]["scenario_sha256"] = _sha(97)
    with pytest.raises(MatchedTrialError, match="expected suite"):
        validate_trial_receipt(mismatched, expected_suite=_suite())


def test_comparator_rejects_static_drift_and_reused_receipt_nonce():
    control = _receipt("control", 20)
    exact_hook = _receipt("exact_hook", 21)
    exact_hook["post_bytes"]["sha256"] = _sha(97)
    with pytest.raises(MatchedTrialError, match="post_bytes.sha256 mismatch"):
        compare_matched_receipts(control, exact_hook)

    exact_hook = _receipt("exact_hook", 20)
    with pytest.raises(MatchedTrialError, match="distinct receipt nonces"):
        compare_matched_receipts(control, exact_hook)


def test_file_reader_and_cli_are_strict_and_read_only(tmp_path: Path):
    suite_path = tmp_path / "suite.json"
    control_path = tmp_path / "control.json"
    hook_path = tmp_path / "hook.json"
    suite_path.write_text(json.dumps(_suite()), encoding="utf-8")
    control_path.write_text(json.dumps(_receipt("control", 20)), encoding="utf-8")
    hook_path.write_text(json.dumps(_receipt("exact_hook", 21)), encoding="utf-8")

    assert load_json_contract(suite_path, "suite")["kind"] == "observatory_matched_trial_suite"
    cli = Path(__file__).parents[1] / "scripts" / "itb_observatory_trial.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(cli),
            "compare",
            "--suite",
            str(suite_path),
            "--control",
            str(control_path),
            "--exact-hook",
            str(hook_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "matched"

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    with pytest.raises(MatchedTrialError, match="duplicate JSON key"):
        load_json_contract(duplicate, "duplicate")
