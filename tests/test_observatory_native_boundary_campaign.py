from __future__ import annotations

import json
from pathlib import Path

from src.observatory.native_boundary_campaign import (
    SELECTED_RECEIPT_KIND,
    SPAWN_COORDINATE_RECEIPT_KIND,
    SPAWN_COORDINATE_RNG_RECEIPT_KIND,
    SPAWN_RECEIPT_KIND,
    SPAWN_REPLAY_RECEIPT_KIND,
    build_selected_queue_campaign_receipt,
    build_spawn_coordinate_campaign_receipt,
    build_spawn_coordinate_rng_campaign_receipt,
    build_spawn_replay_campaign_receipt,
    build_spawn_span_campaign_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "data" / "observatory" / "captures"
SPAWN_ROOT = CAPTURES / (
    "windows_build_13725832_owner_local_modified_20260822_spawn_span"
)
SPAWN_REPLAY_ROOT = CAPTURES / (
    "windows_build_13725832_owner_local_modified_20260822_spawn_replay"
)
SELECTED_ROOT = CAPTURES / (
    "windows_build_13725832_owner_local_modified_20260822_selected_queue"
)
SPAWN_COORDINATE_ROOT = CAPTURES / (
    "windows_build_13725832_owner_local_modified_20260822_spawn_coordinate"
)
SPAWN_COORDINATE_RNG_ROOT = CAPTURES / (
    "windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_rng"
)


def test_committed_spawn_span_campaign_is_complete_and_source_bounded():
    receipt = build_spawn_span_campaign_receipt(
        SPAWN_ROOT,
        repository_root=ROOT,
    )

    assert receipt["kind"] == SPAWN_RECEIPT_KIND
    assert receipt["campaign"]["pair_count"] == 3
    assert receipt["results"]["draw_count_per_span"] == [3, 3, 3]
    assert receipt["results"]["selected_pawns"] == [
        "Firefly2",
        "Scarab2",
        "Scarab2",
    ]
    assert [draw["result"] for draw in receipt["pairs"][0]["native_draws"]] == [
        24976,
        26204,
        24669,
    ]
    assert [pair["whole_game_outcome"]["status"] for pair in receipt["pairs"]] == [
        "mismatched",
        "mismatched",
        "matched",
    ]
    assert all(
        pair["restoration"]
        == {
            "native_hook_bytes": True,
            "spawn_wrapper": True,
            "restore_conflict": False,
        }
        for pair in receipt["pairs"]
    )


def test_committed_spawn_replay_campaign_recovers_exact_native_choices():
    receipt = build_spawn_replay_campaign_receipt(
        SPAWN_REPLAY_ROOT,
        repository_root=ROOT,
    )

    assert receipt["kind"] == SPAWN_REPLAY_RECEIPT_KIND
    assert receipt["campaign"]["pair_count"] == 3
    assert receipt["results"]["draw_count_per_replay"] == [3, 3, 3]
    assert receipt["results"]["selected_pawns"] == [
        "Firefly2",
        "Scarab2",
        "Firefly2",
    ]
    assert receipt["results"]["observable_pre_states"] == [
        "0x14c88732",
        "0x14ca8e21",
        "0x14cf8cc9",
    ]
    assert receipt["results"]["whole_game_outcomes"] == [
        "matched",
        "mismatched",
        "mismatched",
    ]
    assert [pair["replay"]["native_results"] for pair in receipt["pairs"]] == [
        [6988, 26456, 12828],
        [14826, 21631, 24783],
        [2424, 29057, 30541],
    ]
    assert all(
        pair["restoration"]
        == {
            "native_hook_bytes": True,
            "nextpawn_wrapper": True,
            "random_element_wrapper": True,
            "restore_conflict": False,
        }
        for pair in receipt["pairs"]
    )


def test_committed_selected_queue_campaign_is_neutral_and_correlated():
    receipt = build_selected_queue_campaign_receipt(
        SELECTED_ROOT,
        repository_root=ROOT,
    )

    assert receipt["kind"] == SELECTED_RECEIPT_KIND
    assert receipt["campaign"]["pair_count"] == 3
    assert receipt["campaign"]["condition_order_count"] == 3
    assert receipt["results"]["records_per_armed_snapshot"] == [2, 2, 2]
    assert receipt["results"]["event_order"] == [
        "selected_record",
        "queued_action",
    ]
    assert receipt["results"]["stable_native_fields"] == {
        "pawn_id": 1303,
        "ai_destination": [5, 4],
        "ai_target": [4, 4],
        "queue_origin": [5, 4],
        "queue_target": [4, 4],
        "queued_shot": [4, 4],
        "current_weapon_raw": 1,
        "queued_skill_raw": 1,
        "selected_rank_fields_raw": [5, 5],
        "base_current_weapon_raw": -1,
    }
    assert all(
        pair["whole_game_outcome"]
        == {
            "control_dormant": "matched",
            "control_armed": "matched",
            "semantic_sha256": pair["whole_game_outcome"]["semantic_sha256"],
        }
        for pair in receipt["pairs"]
    )
    assert all(pair["observer_integrity"]["seam_bytes_unchanged"] for pair in receipt["pairs"])


def test_committed_spawn_coordinate_campaign_proves_order_and_modulo_only():
    receipt = build_spawn_coordinate_campaign_receipt(
        SPAWN_COORDINATE_ROOT,
        repository_root=ROOT,
    )

    assert receipt["kind"] == SPAWN_COORDINATE_RECEIPT_KIND
    assert receipt["campaign"]["pair_count"] == 3
    assert receipt["campaign"]["condition_orders"] == [
        ["control", "dormant", "armed"],
        ["armed", "dormant", "control"],
        ["dormant", "control", "armed"],
    ]
    assert receipt["results"]["candidate_order"] == [
        [5, 2],
        [5, 3],
        [5, 4],
        [6, 2],
        [6, 5],
    ]
    assert receipt["results"]["raw_rng_values"] == [5290, 3963, 20348]
    assert receipt["results"]["selected_indices"] == [0, 3, 3]
    assert receipt["results"]["control_dormant_statuses"] == [
        "mismatched",
        "mismatched",
        "mismatched",
    ]
    assert receipt["results"]["control_armed_statuses"] == [
        "mismatched",
        "matched",
        "mismatched",
    ]
    assert receipt["results"]["classification"].endswith(
        "upstream_rng_call_order_unresolved"
    )


def test_committed_combined_coordinate_rng_campaign_explains_ordinal_drift():
    receipt = build_spawn_coordinate_rng_campaign_receipt(
        SPAWN_COORDINATE_RNG_ROOT,
        repository_root=ROOT,
    )

    assert receipt["kind"] == SPAWN_COORDINATE_RNG_RECEIPT_KIND
    assert receipt["campaign"]["pair_count"] == 3
    assert receipt["results"]["selector_caller_ids"] == [60, 60, 60]
    assert receipt["results"]["selector_raw_rng"] == [3642, 15777, 30530]
    assert receipt["results"]["selector_rng_ordinals"] == [1495, 1475, 1450]
    assert receipt["results"]["ordinal_deltas_from_first"] == [0, -20, -45]
    assert receipt["results"]["classified_count_deltas_from_first"] == [
        0,
        -20,
        -45,
    ]
    assert receipt["results"]["ordinal_deltas_fully_accounted"] is True
    assert receipt["results"]["unclassified_varying_caller_ids"] == []
    assert receipt["results"]["domain_counts"] == [
        {"domain": "presentation", "counts": [1271, 1250, 1225]},
        {"domain": "gameplay", "counts": [2, 3, 2]},
        {"domain": "shared_lua_boundary", "counts": [6, 6, 7]},
    ]
    assert receipt["solver_conformance"]["simulator_version_bump_required"] is False
    assert all(
        pair["restoration"]
        == {
            "rng_core_complete": True,
            "rng_core_hook_bytes_restored": True,
            "coordinate_complete": True,
            "coordinate_debug_registers_cleared": True,
            "coordinate_veh_removed": True,
            "coordinate_seam_bytes_unchanged": True,
        }
        for pair in receipt["pairs"]
    )


def test_published_receipts_rebuild_exactly_when_present():
    cases = [
        (
            SPAWN_ROOT,
            CAPTURES
            / "windows_build_13725832_owner_local_modified_20260822_spawn_span_receipt.json",
            build_spawn_span_campaign_receipt,
        ),
        (
            SPAWN_REPLAY_ROOT,
            CAPTURES
            / "windows_build_13725832_owner_local_modified_20260822_spawn_replay_receipt.json",
            build_spawn_replay_campaign_receipt,
        ),
        (
            SELECTED_ROOT,
            CAPTURES
            / "windows_build_13725832_owner_local_modified_20260822_selected_queue_receipt.json",
            build_selected_queue_campaign_receipt,
        ),
        (
            SPAWN_COORDINATE_ROOT,
            CAPTURES
            / "windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_receipt.json",
            build_spawn_coordinate_campaign_receipt,
        ),
        (
            SPAWN_COORDINATE_RNG_ROOT,
            CAPTURES
            / "windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_rng_receipt.json",
            build_spawn_coordinate_rng_campaign_receipt,
        ),
    ]
    for campaign_root, receipt_path, builder in cases:
        if not receipt_path.exists():
            continue
        committed = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert committed == builder(campaign_root, repository_root=ROOT)
