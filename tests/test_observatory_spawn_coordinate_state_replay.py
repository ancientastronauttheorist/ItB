"""Tests for post-hoc native spawn-selector state replay evidence."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.spawn_coordinate_state_replay import (
    CAMPAIGN_RELATIVE,
    RECEIPT_KIND,
    SpawnCoordinateStateReplayError,
    build_spawn_coordinate_state_replay_receipt,
    canonical_json_bytes,
    recover_selector_replay_vector,
)


ROOT = Path(__file__).resolve().parents[1]
COMMITTED_RECEIPT = (
    ROOT
    / "data/observatory/captures/"
    "windows_build_13725832_owner_local_modified_20260822_"
    "spawn_coordinate_state_replay_receipt.json"
)
SOURCE_RECEIPT = (
    ROOT
    / "data/observatory/captures/"
    "windows_build_13725832_owner_local_modified_20260822_"
    "spawn_coordinate_rng_receipt.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pair_inputs(pair_name: str = "pair001") -> tuple[dict, dict, dict, dict]:
    source = _load(SOURCE_RECEIPT)
    pair = next(item for item in source["pairs"] if item["pair"] == pair_name)
    pair_dir = ROOT / CAMPAIGN_RELATIVE / pair_name
    return (
        pair,
        _load(pair_dir / "rng_checkpoint.json"),
        _load(pair_dir / "attribution.json"),
        _load(pair_dir / "coordinate_analysis.json"),
    )


def test_committed_selector_state_receipt_rebuilds_exactly():
    receipt = build_spawn_coordinate_state_replay_receipt(ROOT)

    assert receipt["kind"] == RECEIPT_KIND
    assert receipt["results"] == {
        "classification": (
            "selector_time_observable_state_recovered_post_hoc_"
            "exact_replay_not_prospective"
        ),
        "observable_pre_states": [
            "0x161229bc",
            "0x495e317b",
            "0x2c54aa4a",
        ],
        "raw_rng_values": [3642, 15777, 30530],
        "replay_count": 3,
        "selected_coordinates": [[5, 4], [5, 4], [5, 2]],
        "selected_indices": [2, 2, 0],
    }
    assert canonical_json_bytes(receipt) == COMMITTED_RECEIPT.read_bytes()


def test_selector_state_vectors_preserve_hidden_bit_ambiguity_only():
    receipt = build_spawn_coordinate_state_replay_receipt(ROOT)

    for vector in receipt["vectors"]:
        raw_states = [int(value, 16) for value in vector["raw_pre_state_candidates_hex"]]
        assert len(raw_states) == 2
        assert raw_states[0] ^ raw_states[1] == 0x80000000
        assert raw_states[0] & 0x7FFFFFFF == vector["observable_pre_state"]
        assert vector["raw_rng"] % vector["candidate_count"] == vector["selected_index"]
        assert vector["candidates"][vector["selected_index"]] == vector["selected"]


def test_selector_state_recovery_rejects_changed_following_result():
    pair, checkpoint, attribution, analysis = _pair_inputs()
    sequence = attribution["events"][0]["rng_sequence"]
    changed = copy.deepcopy(checkpoint)
    changed["records"][sequence + 1]["result"] ^= 1

    with pytest.raises(SpawnCoordinateStateReplayError):
        recover_selector_replay_vector(
            pair=pair,
            checkpoint=changed,
            attribution=attribution,
            coordinate_analysis=analysis,
        )


def test_selector_state_recovery_rejects_candidate_order_drift():
    pair, checkpoint, attribution, analysis = _pair_inputs()
    changed = copy.deepcopy(attribution)
    changed["events"][0]["candidates"][0], changed["events"][0]["candidates"][1] = (
        changed["events"][0]["candidates"][1],
        changed["events"][0]["candidates"][0],
    )

    with pytest.raises(SpawnCoordinateStateReplayError):
        recover_selector_replay_vector(
            pair=pair,
            checkpoint=checkpoint,
            attribution=changed,
            coordinate_analysis=analysis,
        )
