"""Tests for strict native diagnostic checkpoint validation."""

from __future__ import annotations

import copy
import hashlib

import pytest

from src.observatory.native_checkpoint import (
    NativeCheckpointError,
    restore_hash_manifest_sha256,
    validate_native_checkpoint,
)
from src.observatory.rng_return_map import encode_rng_return_map


_DIGEST = "a" * 64


def _checkpoint() -> dict:
    records = [
        {
            "kind": "phase_marker",
            "seq": 0,
            "thread_slot": 0,
            "phase": "enemy_planning",
            "action": "enter",
        },
        {
            "kind": "span_marker",
            "seq": 1,
            "thread_slot": 0,
            "span_id": 7,
            "name": "spawner_next_pawn",
            "action": "enter",
            "detail": "normal",
        },
        {
            "kind": "rng_core",
            "seq": 2,
            "thread_slot": 0,
            "caller_id": 4,
            "result": 1234,
        },
        {
            "kind": "span_marker",
            "seq": 3,
            "thread_slot": 0,
            "span_id": 7,
            "name": "spawner_next_pawn",
            "action": "exit",
            "detail": "normal",
        },
        {
            "kind": "selected_record",
            "seq": 4,
            "thread_slot": 0,
            "turn": 2,
            "enemy_id": "pawn_17",
            "ai_dest": [3, 4],
            "ai_target": [3, 3],
            "skill_id": "firefly_1",
        },
        {
            "kind": "queue_snapshot",
            "seq": 5,
            "thread_slot": 0,
            "turn": 2,
            "phase": "enemy_planning",
            "queue": [
                {
                    "enemy_id": "pawn_17",
                    "position": [2, 4],
                    "destination": [3, 4],
                    "target": [3, 3],
                    "skill_id": "firefly_1",
                    "state": "queued",
                }
            ],
        },
    ]
    return {
        "schema_version": 1,
        "kind": "native_diagnostic_checkpoint",
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "executable_sha256": _DIGEST,
            "executable_size": 5_000_000,
            "build_id": "13725832",
            "inventory_sha256": _DIGEST,
            "boundary_map_sha256": _DIGEST,
            "rng_return_map_sha256": _DIGEST,
            "helper_sha256": _DIGEST,
            "hook_plan_sha256": _DIGEST,
            "restore_manifest_sha256": restore_hash_manifest_sha256(
                {"rng_core": _DIGEST}
            ),
        },
        "capture_id": "pair_01_hook_a",
        "integrity": {
            "overflow_count": 0,
            "unknown_caller_count": 0,
            "torn_record_count": 0,
            "restore_conflict": False,
            "hook_bytes_restored": True,
            "post_restore_hashes": {"rng_core": _DIGEST},
            "stopped_reason": None,
            "complete": True,
        },
        "records": records,
        "summary": {
            "record_count": 6,
            "rng_core_count": 1,
            "rng_seed_count": 0,
            "phase_marker_count": 1,
            "span_marker_count": 2,
            "selected_record_count": 1,
            "queue_snapshot_count": 1,
            "thread_count": 1,
            "last_sequence": 5,
            "capture_complete": True,
        },
    }


def _return_map(checkpoint: dict, count: int = 4) -> dict:
    catalog = {
        "schema_version": 1,
        "analysis_kind": "native_rng_return_id_map",
        "identity": {
            "platform": checkpoint["identity"]["platform"],
            "architecture": checkpoint["identity"]["architecture"],
            "executable_sha256": checkpoint["identity"]["executable_sha256"],
            "executable_size": checkpoint["identity"]["executable_size"],
            "build_id": checkpoint["identity"]["build_id"],
        },
        "callers": [
            {
                "caller_id": caller_id,
                "classification": {
                    "status": "unclassified_raw_candidate",
                    "source_region": None,
                },
            }
            for caller_id in range(1, count + 1)
        ],
    }
    checkpoint["identity"]["rng_return_map_sha256"] = hashlib.sha256(
        encode_rng_return_map(catalog).encode("utf-8")
    ).hexdigest()
    return catalog


def _proof_args(checkpoint: dict) -> dict:
    catalog = _return_map(checkpoint)
    return {
        "expected_identity": copy.deepcopy(checkpoint["identity"]),
        "return_map": catalog,
        "expected_restore_hashes": copy.deepcopy(
            checkpoint["integrity"]["post_restore_hashes"]
        ),
    }


def test_accepts_complete_build_specific_diagnostic_checkpoint():
    checkpoint = _checkpoint()

    result = validate_native_checkpoint(checkpoint, **_proof_args(checkpoint))

    assert result["status"] == "verified"
    assert result["diagnostic_complete"] is True
    assert result["authority"] == "build_specific_diagnostic_only"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda item: item["records"][2].update(seq=9), "contiguous"),
        (lambda item: item["records"][2].update(result=32768), "result"),
        (lambda item: item["records"][2].update(pointer=123), "fields differ"),
        (
            lambda item: item["summary"].update(rng_core_count=2),
            "summary is inconsistent",
        ),
        (
            lambda item: item["identity"].update(executable_sha256="A" * 64),
            "lowercase SHA-256",
        ),
    ],
)
def test_fails_closed_on_torn_or_malformed_records(mutation, message):
    checkpoint = copy.deepcopy(_checkpoint())
    mutation(checkpoint)

    with pytest.raises(NativeCheckpointError, match=message):
        validate_native_checkpoint(checkpoint)


def test_unknown_caller_and_restore_failures_are_diagnostic_incomplete():
    checkpoint = _checkpoint()
    checkpoint["records"][2]["caller_id"] = 0
    checkpoint["integrity"].update(
        unknown_caller_count=1,
        hook_bytes_restored=False,
        complete=False,
    )
    checkpoint["summary"]["capture_complete"] = False

    result = validate_native_checkpoint(checkpoint, **_proof_args(checkpoint))

    assert result["status"] == "verified"
    assert result["diagnostic_complete"] is False


def test_complete_flag_cannot_hide_overflow_or_restore_conflict():
    checkpoint = _checkpoint()
    checkpoint["integrity"]["overflow_count"] = 1

    with pytest.raises(NativeCheckpointError, match="complete"):
        validate_native_checkpoint(checkpoint)


def test_expected_identity_is_exact():
    checkpoint = _checkpoint()
    expected = copy.deepcopy(checkpoint["identity"])
    expected["build_id"] = "another_build"

    with pytest.raises(NativeCheckpointError, match="identity does not match"):
        validate_native_checkpoint(checkpoint, expected_identity=expected)


def test_reported_restore_state_is_not_proof_without_external_bindings():
    checkpoint = _checkpoint()

    result = validate_native_checkpoint(checkpoint)

    assert result["reported_complete"] is True
    assert result["identity_verified"] is False
    assert result["caller_catalog_verified"] is False
    assert result["restore_hashes_verified"] is False
    assert result["diagnostic_complete"] is False


def test_fabricated_restore_hash_and_out_of_catalog_caller_cannot_complete():
    checkpoint = _checkpoint()
    proof = _proof_args(checkpoint)
    proof["expected_restore_hashes"] = {"rng_core": "f" * 64}

    with pytest.raises(NativeCheckpointError, match="trusted identity"):
        validate_native_checkpoint(checkpoint, **proof)

    checkpoint = _checkpoint()
    catalog = _return_map(checkpoint)
    checkpoint["integrity"]["post_restore_hashes"] = {"made_up_hook": "f" * 64}
    result = validate_native_checkpoint(
        checkpoint,
        expected_identity=copy.deepcopy(checkpoint["identity"]),
        return_map=catalog,
        expected_restore_hashes={"rng_core": _DIGEST},
    )
    assert result["restore_hashes_verified"] is False
    assert result["diagnostic_complete"] is False

    checkpoint = _checkpoint()
    checkpoint["records"][2]["caller_id"] = 200
    proof = _proof_args(checkpoint)
    result = validate_native_checkpoint(checkpoint, **proof)
    assert result["caller_catalog_verified"] is False
    assert result["diagnostic_complete"] is False
