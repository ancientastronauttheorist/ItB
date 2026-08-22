from __future__ import annotations

import json
from pathlib import Path

from src.observatory.native_boundary_campaign import (
    SELECTED_RECEIPT_KIND,
    SPAWN_RECEIPT_KIND,
    build_selected_queue_campaign_receipt,
    build_spawn_span_campaign_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "data" / "observatory" / "captures"
SPAWN_ROOT = CAPTURES / (
    "windows_build_13725832_owner_local_modified_20260822_spawn_span"
)
SELECTED_ROOT = CAPTURES / (
    "windows_build_13725832_owner_local_modified_20260822_selected_queue"
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


def test_published_receipts_rebuild_exactly_when_present():
    cases = [
        (
            SPAWN_ROOT,
            CAPTURES
            / "windows_build_13725832_owner_local_modified_20260822_spawn_span_receipt.json",
            build_spawn_span_campaign_receipt,
        ),
        (
            SELECTED_ROOT,
            CAPTURES
            / "windows_build_13725832_owner_local_modified_20260822_selected_queue_receipt.json",
            build_selected_queue_campaign_receipt,
        ),
    ]
    for campaign_root, receipt_path, builder in cases:
        if not receipt_path.exists():
            continue
        committed = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert committed == builder(campaign_root, repository_root=ROOT)
