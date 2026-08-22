"""Tests for strict native/Lua spawn replay capsules."""

from __future__ import annotations

import copy
import hashlib
from collections import Counter

import pytest

from src.observatory.rng_return_map import encode_rng_return_map
from src.observatory.spawn_replay_ledger import (
    SpawnReplayLedgerError,
    analyze_spawn_replay,
)
from tests.test_observatory_native_checkpoint import _checkpoint


CONTROLLER_SHA256 = "c411c5e1d84cfae079b6b5f6b69b9bc022d0f0a9a87af5bf877ca1c1badb699f"


def _refresh(checkpoint: dict) -> dict:
    kinds = Counter()
    threads = set()
    for sequence, record in enumerate(checkpoint["records"]):
        record["seq"] = sequence
        kinds[record["kind"]] += 1
        threads.add(record["thread_slot"])
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
    checkpoint["integrity"]["unknown_caller_count"] = 0
    return checkpoint


def _return_map(checkpoint: dict) -> dict:
    callers = []
    for caller_id in range(1, 26):
        source = (
            "random_int_1"
            if caller_id == 21
            else "random_bool_1"
            if caller_id == 25
            else None
        )
        callers.append(
            {
                "caller_id": caller_id,
                "classification": {
                    "status": (
                        "reviewed_direct_call"
                        if source is not None
                        else "unclassified_raw_candidate"
                    ),
                    "source_region": source,
                },
            }
        )
    value = {
        "schema_version": 1,
        "analysis_kind": "native_rng_return_id_map",
        "identity": {
            key: checkpoint["identity"][key]
            for key in (
                "platform",
                "architecture",
                "executable_sha256",
                "executable_size",
                "build_id",
            )
        },
        "callers": callers,
    }
    checkpoint["identity"]["rng_return_map_sha256"] = hashlib.sha256(
        encode_rng_return_map(value).encode("utf-8")
    ).hexdigest()
    return value


def _case(results=(24976, 26204, 24669), *, boss_draw=False):
    checkpoint = _checkpoint()
    callers = [21, 21, 21] + ([25] if boss_draw else [])
    checkpoint["records"] = [
        {
            "kind": "rng_core",
            "seq": index,
            "thread_slot": 0,
            "caller_id": callers[index],
            "result": result,
        }
        for index, result in enumerate(results)
    ]
    _refresh(checkpoint)
    return_map = _return_map(checkpoint)
    ledger = {
        "schema_version": 1,
        "kind": "spawn_rng_replay_ledger",
        "controller_version": "observatory-spawn-replay-controller/1",
        "controller_sha256": CONTROLLER_SHA256,
        "capture_id": checkpoint["capture_id"],
        "write_mode": "create_only",
        "raw_record_count": len(results),
        "source_identity": {
            "spawner_expected_sha256": "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301",
            "spawner_expected_source_suffix": "scripts/spawner_backend.lua",
            "spawner_expected_linedefined": 174,
            "spawner_runtime_source": "B:/SteamLibrary/steamapps/common/Into the Breach/scripts/spawner_backend.lua",
            "spawner_runtime_linedefined": 174,
            "random_element_expected_sha256": "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2",
            "random_element_expected_source_suffix": "scripts/global.lua",
            "random_element_expected_linedefined": 560,
            "random_element_runtime_source": "B:/SteamLibrary/steamapps/common/Into the Breach/scripts/global.lua",
            "random_element_runtime_linedefined": 560,
            "source_locations_verified": True,
        },
        "integrity": {
            "complete": True,
            "next_wrapper_restored": True,
            "random_wrapper_restored": True,
            "restore_conflict": False,
            "nested_next_count": 0,
            "nested_random_count": 0,
            "observer_status_error_count": 0,
            "span_overflow_count": 0,
            "candidate_overflow_count": 0,
            "invalid_candidate_count": 0,
            "input_snapshot_error_count": 0,
            "random_install_error_count": 0,
            "candidate_count_mismatch_count": 0,
            "active_depth": 0,
        },
        "spans": [
            {
                "span_id": 1,
                "name": "spawner_next_pawn",
                "detail": "normal",
                "inputs": {
                    "num_weak": 0,
                    "num_upgrades": 5,
                    "upgrade_streak": 1,
                    "num_spawns": 5,
                    "upgrade_max": 3,
                    "used_bosses": 1,
                    "num_bosses": 1,
                    "curr_weak_ratio": {
                        "present": True,
                        "numerator": 0,
                        "denominator": 5,
                    },
                    "curr_upgrade_ratio": {
                        "present": True,
                        "numerator": 5,
                        "denominator": 5,
                    },
                },
                "inputs_valid": True,
                "candidate_events": [
                    {
                        "event_id": 1,
                        "entry_count": 1,
                        "exit_count": 2,
                        "detail": "normal",
                        "list_length": 3,
                        "candidates_valid": True,
                        "available": ["Mosquito", "Scarab", "Firefly"],
                        "selected_base": "Firefly",
                    }
                ],
                "selected_pawn": "Firefly2",
                "selected_max_level": 2,
                "boss_available": True,
                "random_wrapper_restored": True,
                "entry_count": 0,
                "exit_count": len(results),
            }
        ],
        "summary": {
            "span_count": 1,
            "candidate_event_count": 1,
            "complete": True,
        },
    }
    return checkpoint, return_map, ledger


def _analyze(checkpoint, return_map, ledger):
    return analyze_spawn_replay(
        checkpoint,
        ledger,
        expected_controller_sha256=CONTROLLER_SHA256,
        return_map=return_map,
        expected_identity=copy.deepcopy(checkpoint["identity"]),
        expected_restore_hashes=copy.deepcopy(
            checkpoint["integrity"]["post_restore_hashes"]
        ),
    )


def test_builds_exact_live_observable_state_and_candidate_replay():
    checkpoint, return_map, ledger = _case()

    result = _analyze(checkpoint, return_map, ledger)

    assert result["observable_pre_state_hex"] == "0x143e0bae"
    assert result["raw_pre_state_candidates"] == ["0x143e0bae", "0x943e0bae"]
    assert result["future_observable_stream_exact"] is True
    assert result["candidate_choice"]["selected_index_zero_based"] == 2
    assert result["candidate_choice"]["selected_base"] == "Firefly"
    assert result["upgrade_branch"]["selected_upgrade"] is True
    assert result["selected_pawn"] == "Firefly2"
    assert result["replay_verified"] is True


def test_validates_natural_fourth_boss_draw_and_false_result():
    results = (13289, 23359, 19469, 24737)
    checkpoint, return_map, ledger = _case(results, boss_draw=True)
    span = ledger["spans"][0]
    span["candidate_events"][0].update(
        list_length=2,
        available=["Scarab", "Firefly"],
    )
    span["inputs"].update(used_bosses=0, num_bosses=1)

    result = _analyze(checkpoint, return_map, ledger)

    assert result["boss_branch"] == {
        "guard_reached": True,
        "boss_available": True,
        "chance": 2,
        "raw_result": 24737,
        "selected_boss": False,
    }
    assert result["selected_pawn"] == "Firefly2"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda checkpoint, _ledger: checkpoint["records"][1].update(caller_id=22),
            "caller sequence",
        ),
        (
            lambda checkpoint, _ledger: checkpoint["records"][2].update(thread_slot=1),
            "exactly one RNG thread",
        ),
        (
            lambda _checkpoint, ledger: (
                ledger["spans"][0]["candidate_events"][0].update(
                    selected_base="Scarab"
                ),
                ledger["spans"][0].update(selected_pawn="Scarab2"),
            ),
            "modulo replay differs",
        ),
        (
            lambda _checkpoint, ledger: ledger["integrity"].update(
                random_wrapper_restored=False
            ),
            "integrity failed",
        ),
        (
            lambda _checkpoint, ledger: ledger["spans"][0].update(
                selected_pawn="FireflyBoss"
            ),
            "replayed final level",
        ),
    ],
)
def test_fails_closed_on_gaps_threads_candidate_drift_or_restoration(
    mutation, message
):
    checkpoint, return_map, ledger = _case()
    mutation(checkpoint, ledger)
    _refresh(checkpoint)

    with pytest.raises(SpawnReplayLedgerError, match=message):
        _analyze(checkpoint, return_map, ledger)
