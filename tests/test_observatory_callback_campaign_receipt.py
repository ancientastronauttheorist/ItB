from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from src.observatory.callback_campaign_receipt import (
    CallbackCampaignReceiptError,
    build_callback_campaign_receipt,
    publish_callback_campaign_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_20260822_natural_callbacks"
)
RECEIPT = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_20260822_"
    "natural_callback_campaign_receipt.json"
)


def test_committed_callback_campaign_receipt_is_reproducible():
    expected = build_callback_campaign_receipt(CAMPAIGN, repository_root=ROOT)
    committed = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert committed == expected
    assert committed["results"] == {
        "accepted_events": 620,
        "attempted_calls": 622,
        "bounded_dropped_events": 2,
        "classification": "live_callback_invocation_and_restoration_with_bounded_outcomes",
        "complete_restored_pairs": 5,
        "get_skill_effect_repeat": {
            "control_outcomes_repeat": True,
            "counterbalanced": True,
            "event_streams_repeat": True,
            "exact_outcomes_repeat": True,
        },
        "mismatch_scope": [
            "/spawning_tiles/0/0",
            "/spawning_tiles/0/1",
        ],
        "whole_game_matches": 3,
        "whole_game_mismatches": 2,
    }


def test_callback_campaign_fails_closed_on_trace_tamper(tmp_path: Path):
    campaign = tmp_path / "campaign"
    shutil.copytree(CAMPAIGN, campaign)
    trace_path = campaign / "get_target_area_pair001" / "exact_hook_trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace["events"][0]["kind"] = "get_skill_effect"
    trace_path.write_text(json.dumps(trace), encoding="utf-8")

    with pytest.raises(CallbackCampaignReceiptError):
        build_callback_campaign_receipt(campaign, repository_root=ROOT)


def test_callback_campaign_publication_is_create_only(tmp_path: Path):
    output = tmp_path / "receipt.json"
    path, digest = publish_callback_campaign_receipt(
        CAMPAIGN,
        repository_root=ROOT,
        output=output,
    )
    assert path == output
    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    with pytest.raises(CallbackCampaignReceiptError, match="already exists"):
        publish_callback_campaign_receipt(
            CAMPAIGN,
            repository_root=ROOT,
            output=output,
        )
