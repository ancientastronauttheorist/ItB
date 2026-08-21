"""Tests for bounded spawn-selection RNG attribution."""

from __future__ import annotations

import copy
import hashlib
from collections import Counter

import pytest

from src.observatory.native_checkpoint import NativeCheckpointError
from src.observatory.rng_return_map import encode_rng_return_map
from src.observatory.spawn_rng_attribution import analyze_spawn_rng
from tests.test_observatory_native_checkpoint import _checkpoint, _return_map


def _refresh(checkpoint: dict) -> dict:
    kinds = Counter()
    threads = set()
    for seq, record in enumerate(checkpoint["records"]):
        record["seq"] = seq
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


def _analyze(checkpoint: dict, **kwargs):
    return analyze_spawn_rng(
        checkpoint,
        expected_identity=copy.deepcopy(checkpoint["identity"]),
        expected_restore_hashes=copy.deepcopy(
            checkpoint["integrity"]["post_restore_hashes"]
        ),
        **kwargs,
    )


def test_attributes_draws_and_classifies_lua_leaf_callers():
    checkpoint = _checkpoint()
    return_map = {
        "schema_version": 1,
        "analysis_kind": "native_rng_return_id_map",
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "executable_sha256": "a" * 64,
            "executable_size": 5_000_000,
            "build_id": "13725832",
        },
        "callers": [
            {
                "caller_id": index,
                "classification": {
                    "status": (
                        "reviewed_direct_call"
                        if index == 4
                        else "unclassified_raw_candidate"
                    ),
                    "source_region": "random_int_1" if index == 4 else None,
                },
            }
            for index in range(1, 5)
        ]
    }
    checkpoint["identity"]["rng_return_map_sha256"] = hashlib.sha256(
        encode_rng_return_map(return_map).encode("utf-8")
    ).hexdigest()

    result = _analyze(checkpoint, return_map=return_map)

    assert result["summary"]["resolved_with_draws"] == 1
    assert result["spans"][0]["draw_sequences"] == [2]
    assert result["spans"][0]["caller_origins"] == ["lua_random_leaf"]


def test_supplied_return_map_must_match_checkpoint_digest():
    checkpoint = _checkpoint()
    return_map = {
        "schema_version": 1,
        "analysis_kind": "native_rng_return_id_map",
        "identity": {},
        "callers": [],
    }

    with pytest.raises(NativeCheckpointError, match="digest does not match"):
        _analyze(checkpoint, return_map=return_map)


def test_shortcut_is_no_draw_only_when_explicitly_marked():
    checkpoint = copy.deepcopy(_checkpoint())
    checkpoint["records"] = [
        record
        for record in checkpoint["records"]
        if record["kind"] != "rng_core"
    ]
    for record in checkpoint["records"]:
        if record["kind"] == "span_marker":
            record["detail"] = "shortcut_no_draw"
    _refresh(checkpoint)

    result = _analyze(checkpoint)

    assert result["spans"][0]["status"] == "resolved_no_draw"

    for record in checkpoint["records"]:
        if record["kind"] == "span_marker":
            record["detail"] = "normal"
    result = _analyze(checkpoint)
    assert result["spans"][0]["reason"] == "no_rng_draw_observed"


def test_reseed_and_nested_spans_remain_unresolved():
    reseeded = copy.deepcopy(_checkpoint())
    reseeded["records"].insert(
        3,
        {"kind": "rng_seed", "seq": 0, "thread_slot": 0, "seed": 42},
    )
    _refresh(reseeded)

    result = _analyze(reseeded, return_map=_return_map(reseeded))
    assert result["spans"][0]["reason"] == "rng_reseed_inside_span"

    nested = copy.deepcopy(_checkpoint())
    nested["records"].insert(
        2,
        {
            "kind": "span_marker",
            "seq": 0,
            "thread_slot": 0,
            "span_id": 8,
            "name": "spawner_next_pawn",
            "action": "enter",
            "detail": "normal",
        },
    )
    nested["records"].insert(
        4,
        {
            "kind": "span_marker",
            "seq": 0,
            "thread_slot": 0,
            "span_id": 8,
            "name": "spawner_next_pawn",
            "action": "exit",
            "detail": "normal",
        },
    )
    _refresh(nested)

    result = _analyze(nested, return_map=_return_map(nested))
    assert result["summary"]["unresolved"] == 2
    assert {
        span["reason"] for span in result["spans"]
    } == {"overlapping_or_nested_spawn_spans"}


def test_incomplete_checkpoint_cannot_produce_resolved_attribution():
    checkpoint = _checkpoint()
    checkpoint["integrity"].update(hook_bytes_restored=False, complete=False)
    checkpoint["summary"]["capture_complete"] = False

    result = _analyze(checkpoint, return_map=_return_map(checkpoint))

    assert result["spans"][0]["status"] == "unresolved"
    assert result["spans"][0]["reason"] == "checkpoint_incomplete"


def test_caller_id_outside_bound_catalog_cannot_resolve():
    checkpoint = _checkpoint()
    checkpoint["records"][2]["caller_id"] = 200
    result = _analyze(checkpoint, return_map=_return_map(checkpoint))

    assert result["spans"][0]["status"] == "unresolved"
