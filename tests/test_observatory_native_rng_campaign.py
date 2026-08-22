from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.observatory.native_rng_campaign import (
    NativeRngCampaignError,
    build_native_rng_campaign_receipt,
    publish_native_rng_campaign_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_20260822_native_rng_core_atomic"
)
RECEIPT = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_20260822_"
    "native_rng_core_atomic_receipt.json"
)


def test_committed_native_rng_campaign_receipt_is_reproducible():
    expected = build_native_rng_campaign_receipt(CAMPAIGN, repository_root=ROOT)
    committed = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert committed == expected
    assert committed["results"]["complete_restored_checkpoints"] == 2
    assert committed["results"]["first_seeded_result"] == 24356
    assert committed["results"]["exact_result_stream_common_prefix"] == 104
    assert committed["results"]["stable_reviewed_result_sequences"] == [
        19,
        29,
        30,
        31,
    ]
    assert [pair["condition_order"] for pair in committed["pairs"]] == [
        "exact_then_control",
        "control_then_exact",
    ]


def test_native_campaign_fails_closed_on_checkpoint_tamper(tmp_path: Path):
    campaign = tmp_path / "campaign"
    import shutil

    shutil.copytree(CAMPAIGN, campaign)
    checkpoint_path = campaign / "pair003" / "exact_hook_checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["records"][0]["result"] += 1
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")

    with pytest.raises((NativeRngCampaignError, ValueError)):
        build_native_rng_campaign_receipt(campaign, repository_root=ROOT)


def test_native_campaign_publication_is_create_only(tmp_path: Path):
    output = tmp_path / "receipt.json"
    path, digest = publish_native_rng_campaign_receipt(
        CAMPAIGN,
        repository_root=ROOT,
        output=output,
    )
    assert path == output
    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    with pytest.raises(NativeRngCampaignError, match="already exists"):
        publish_native_rng_campaign_receipt(
            CAMPAIGN,
            repository_root=ROOT,
            output=output,
        )
