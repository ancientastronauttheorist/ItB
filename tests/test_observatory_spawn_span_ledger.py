"""Tests for strict post-restore spawn-span ledger merging."""

from __future__ import annotations

import copy
from collections import Counter

import pytest

from src.observatory.native_checkpoint import validate_native_checkpoint
from src.observatory.spawn_span_ledger import (
    SpawnSpanLedgerError,
    merge_spawn_span_ledger,
)
from tests.test_observatory_native_checkpoint import _checkpoint


_CONTROLLER_SHA256 = "c" * 64


def _refresh(checkpoint: dict) -> dict:
    kinds = Counter()
    threads = set()
    for sequence, record in enumerate(checkpoint["records"]):
        record["seq"] = sequence
        kinds[record["kind"]] += 1
        threads.add(record["thread_slot"])
    checkpoint["integrity"]["unknown_caller_count"] = sum(
        record["kind"] == "rng_core" and record["caller_id"] == 0
        for record in checkpoint["records"]
    )
    checkpoint["summary"] = {
        "record_count": len(checkpoint["records"]),
        "rng_core_count": kinds["rng_core"],
        "rng_seed_count": kinds["rng_seed"],
        "phase_marker_count": kinds["phase_marker"],
        "span_marker_count": kinds["span_marker"],
        "selected_record_count": kinds["selected_record"],
        "queue_snapshot_count": kinds["queue_snapshot"],
        "thread_count": len(threads),
        "last_sequence": len(checkpoint["records"]) - 1,
        "capture_complete": checkpoint["integrity"]["complete"],
    }
    return checkpoint


def _raw_checkpoint() -> dict:
    checkpoint = _checkpoint()
    checkpoint["records"] = [
        {
            "kind": "rng_core",
            "seq": 0,
            "thread_slot": 0,
            "caller_id": 4,
            "result": result,
        }
        for result in (11, 22, 33, 44, 55)
    ]
    return _refresh(checkpoint)


def _ledger(checkpoint: dict) -> dict:
    return {
        "schema_version": 1,
        "kind": "spawn_rng_span_ledger",
        "controller_version": "observatory-spawn-span-controller/1",
        "controller_sha256": _CONTROLLER_SHA256,
        "capture_id": checkpoint["capture_id"],
        "write_mode": "create_only",
        "raw_record_count": len(checkpoint["records"]),
        "source_identity": {
            "expected_sha256": "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301",
            "expected_source_suffix": "scripts/spawner_backend.lua",
            "expected_linedefined": 174,
            "runtime_source": "B:/SteamLibrary/steamapps/common/Into the Breach/scripts/spawner_backend.lua",
            "runtime_linedefined": 174,
            "source_location_verified": True,
        },
        "integrity": {
            "complete": True,
            "wrapper_restored": True,
            "restore_conflict": False,
            "nested_call_count": 0,
            "observer_status_error_count": 0,
            "span_overflow_count": 0,
            "count_regression_count": 0,
            "active_depth": 0,
        },
        "spans": [
            {
                "span_id": 1,
                "name": "spawner_next_pawn",
                "detail": "normal",
                "entry_count": 1,
                "exit_count": 3,
                "selected_pawn": "Firefly2",
            },
            {
                "span_id": 2,
                "name": "spawner_next_pawn",
                "detail": "normal",
                "entry_count": 3,
                "exit_count": 3,
                "selected_pawn": "Hornet1",
            },
        ],
        "summary": {"span_count": 2, "complete": True},
    }


def _merge(checkpoint: dict, ledger: dict) -> dict:
    return merge_spawn_span_ledger(
        checkpoint,
        ledger,
        expected_controller_sha256=_CONTROLLER_SHA256,
    )


def test_merges_half_open_boundaries_without_changing_raw_evidence():
    checkpoint = _raw_checkpoint()
    original = copy.deepcopy(checkpoint)

    merged = _merge(checkpoint, _ledger(checkpoint))

    assert checkpoint == original
    assert [record["kind"] for record in merged["records"]] == [
        "rng_core",
        "span_marker",
        "rng_core",
        "rng_core",
        "span_marker",
        "span_marker",
        "span_marker",
        "rng_core",
        "rng_core",
    ]
    assert [(item["action"], item["span_id"]) for item in merged["records"] if item["kind"] == "span_marker"] == [
        ("enter", 1), ("exit", 1), ("enter", 2), ("exit", 2)
    ]
    assert [
        item["result"] for item in merged["records"] if item["kind"] == "rng_core"
    ] == [11, 22, 33, 44, 55]
    assert merged["integrity"] == original["integrity"]
    assert merged["summary"]["record_count"] == 9
    assert merged["summary"]["rng_core_count"] == 5
    assert merged["summary"]["span_marker_count"] == 4
    validate_native_checkpoint(merged)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda ledger: ledger.update(raw_record_count=4), "count drift"),
        (lambda ledger: ledger.update(write_mode="append"), "create-only"),
        (lambda ledger: ledger.update(controller_sha256="d" * 64), "controller SHA"),
        (lambda ledger: ledger["source_identity"].update(expected_linedefined=99), "source line"),
        (lambda ledger: ledger["integrity"].update(wrapper_restored=False), "not restored"),
        (lambda ledger: ledger["summary"].update(span_count=9), "summary span count"),
        (lambda ledger: ledger["spans"][0].update(exit_count=6), "exit_count"),
        (lambda ledger: ledger["spans"][1].update(entry_count=2), "overlap"),
        (lambda ledger: ledger["spans"][1].update(span_id=8), "contiguous"),
        (lambda ledger: ledger["spans"][0].update(selected_pawn="firefly 2"), "selected pawn"),
        (lambda ledger: ledger["spans"][0].update(detail="original_error"), "must be normal"),
        (lambda ledger: ledger["spans"][0].update(extra=True), "fields differ"),
    ],
)
def test_rejects_count_drift_non_create_only_and_ambiguous_ranges(mutation, message):
    checkpoint = _raw_checkpoint()
    ledger = _ledger(checkpoint)
    mutation(ledger)

    with pytest.raises(SpawnSpanLedgerError, match=message):
        _merge(checkpoint, ledger)


def test_rejects_multi_thread_incomplete_or_already_augmented_raw_snapshot():
    checkpoint = _raw_checkpoint()
    checkpoint["records"][1]["thread_slot"] = 1
    _refresh(checkpoint)
    with pytest.raises(SpawnSpanLedgerError, match="exactly one observed thread"):
        _merge(checkpoint, _ledger(checkpoint))

    checkpoint = _raw_checkpoint()
    checkpoint["integrity"].update(hook_bytes_restored=False, complete=False)
    _refresh(checkpoint)
    with pytest.raises(SpawnSpanLedgerError, match="incomplete or restoration"):
        _merge(checkpoint, _ledger(checkpoint))

    checkpoint = _checkpoint()
    with pytest.raises(SpawnSpanLedgerError, match="only unmodified RNG-core"):
        _merge(checkpoint, _ledger(checkpoint))
