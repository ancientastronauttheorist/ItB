"""Tests for selected native record to queued-action correlation."""

from __future__ import annotations

import copy

from src.observatory.selected_record_correlation import correlate_selected_records
from tests.test_observatory_native_checkpoint import _checkpoint
from tests.test_observatory_spawn_rng_attribution import _refresh


def _selected_checkpoint() -> dict:
    checkpoint = copy.deepcopy(_checkpoint())
    checkpoint["records"] = [
        record
        for record in checkpoint["records"]
        if record["kind"] in {"selected_record", "queue_snapshot"}
    ]
    return _refresh(checkpoint)


def _correlate(checkpoint: dict):
    return correlate_selected_records(
        checkpoint,
        expected_identity=copy.deepcopy(checkpoint["identity"]),
        expected_restore_hashes=copy.deepcopy(
            checkpoint["integrity"]["post_restore_hashes"]
        ),
    )


def test_exact_destination_target_and_skill_correlate():
    result = _correlate(_selected_checkpoint())

    assert result["summary"] == {
        "selected_record_count": 1,
        "correlated": 1,
        "unresolved": 0,
    }
    assert result["correlations"][0]["queue_snapshot_sequence"] == 1


def test_mismatch_cancel_retarget_and_late_snapshot_stay_unresolved():
    mismatch = _selected_checkpoint()
    mismatch["records"][-1]["queue"][0]["target"] = [0, 0]
    assert (
        _correlate(mismatch)["correlations"][0]["reason"]
        == "target_mismatch"
    )

    cancelled = _selected_checkpoint()
    cancelled["records"][-1]["queue"][0]["state"] = "cancelled"
    assert (
        _correlate(cancelled)["correlations"][0]["reason"]
        == "queue_state_cancelled"
    )

    late = _selected_checkpoint()
    late["records"][-1]["phase"] = "enemy_execution"
    assert (
        _correlate(late)["correlations"][0]["reason"]
        == "late_queue_snapshot"
    )


def test_multiple_selected_records_are_ambiguous():
    checkpoint = _selected_checkpoint()
    duplicate = copy.deepcopy(checkpoint["records"][-2])
    checkpoint["records"].insert(-1, duplicate)
    _refresh(checkpoint)

    result = _correlate(checkpoint)

    assert result["summary"]["correlated"] == 0
    assert result["summary"]["unresolved"] == 2
    assert {
        item["reason"] for item in result["correlations"]
    } == {"multiple_selected_records"}


def test_later_retarget_invalidates_initial_queue_match():
    checkpoint = _selected_checkpoint()
    later = copy.deepcopy(checkpoint["records"][-1])
    later["queue"][0]["state"] = "retargeted"
    later["queue"][0]["target"] = [1, 1]
    checkpoint["records"].append(later)
    _refresh(checkpoint)

    result = _correlate(checkpoint)

    assert result["correlations"][0]["reason"] == "later_cancel_or_retarget"


def test_later_queued_field_drift_cannot_hide_without_retarget_label():
    checkpoint = _selected_checkpoint()
    later = copy.deepcopy(checkpoint["records"][-1])
    later["queue"][0]["target"] = [1, 1]
    checkpoint["records"].append(later)
    _refresh(checkpoint)

    result = _correlate(checkpoint)

    assert result["correlations"][0]["reason"] == "later_queue_field_drift"


def test_incomplete_checkpoint_cannot_correlate():
    checkpoint = _selected_checkpoint()
    checkpoint["integrity"].update(torn_record_count=1, complete=False)
    checkpoint["summary"]["capture_complete"] = False

    result = _correlate(checkpoint)

    assert result["correlations"][0]["reason"] == "checkpoint_incomplete"


def test_delayed_snapshot_and_missing_selected_skill_do_not_correlate():
    delayed = _selected_checkpoint()
    delayed["records"].insert(
        1,
        {
            "kind": "phase_marker",
            "seq": 0,
            "thread_slot": 0,
            "phase": "enemy_planning",
            "action": "enter",
        },
    )
    _refresh(delayed)
    assert (
        _correlate(delayed)["correlations"][0]["reason"]
        == "queue_snapshot_not_immediate"
    )

    missing_skill = _selected_checkpoint()
    missing_skill["records"][0]["skill_id"] = None
    assert (
        _correlate(missing_skill)["correlations"][0]["reason"]
        == "selected_skill_unavailable"
    )


def test_two_different_selections_before_one_snapshot_are_unresolved():
    checkpoint = _selected_checkpoint()
    second = copy.deepcopy(checkpoint["records"][0])
    second["enemy_id"] = "pawn_18"
    checkpoint["records"].insert(1, second)
    _refresh(checkpoint)

    result = _correlate(checkpoint)

    assert result["summary"]["correlated"] == 0
    assert result["summary"]["unresolved"] == 2
