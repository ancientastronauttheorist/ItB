from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.observatory.rng_campaign_receipt import (
    PAIR_NAMES,
    RngCampaignReceiptError,
    build_seeded_rng_campaign_receipt,
    publish_seeded_rng_campaign_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_20260821_seeded_rng"
)
RECEIPT = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_20260821_"
    "seeded_rng_campaign_receipt.json"
)


def test_committed_seeded_campaign_receipt_is_exactly_reproducible():
    expected = build_seeded_rng_campaign_receipt(
        CAMPAIGN,
        repository_root=ROOT,
    )
    committed = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert committed == expected
    assert committed["results"] == {
        "classification": "return_preserving_but_not_whole_game_neutral",
        "direct_boundary_matches": 6,
        "mismatch_scope": ["/spawning_tiles/0/1"],
        "whole_game_matches": 2,
        "whole_game_mismatches": 4,
    }
    assert [pair["pair"] for pair in committed["pairs"]] == list(PAIR_NAMES)
    assert [pair["condition_order"] for pair in committed["pairs"]] == [
        "exact_then_control",
        "control_then_exact",
        "exact_then_control",
        "control_then_exact",
        "exact_then_control",
        "control_then_exact",
    ]
    assert all(
        pair["direct_boundary"]["status"] == "matched"
        for pair in committed["pairs"]
    )


def test_campaign_publication_is_create_only(tmp_path: Path):
    output = tmp_path / "receipt.json"
    path, digest = publish_seeded_rng_campaign_receipt(
        CAMPAIGN,
        repository_root=ROOT,
        output=output,
    )
    assert path == output
    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    with pytest.raises(RngCampaignReceiptError, match="already exists"):
        publish_seeded_rng_campaign_receipt(
            CAMPAIGN,
            repository_root=ROOT,
            output=output,
        )
