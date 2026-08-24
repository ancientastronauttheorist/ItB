from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.observatory.enemy_score_positioning_semantics import (
    replay_score_positioning_native_integer,
)
from src.observatory.score_positioning_x87_campaign import (
    EXPECTED_CONTROL_WORD,
    EXPECTED_ROUNDING_MODE,
    build_score_positioning_x87_campaign_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_20260824_"
    "score_positioning_x87"
)
RECEIPT = CAPTURE_ROOT.with_name(CAPTURE_ROOT.name + "_receipt.json")
CLEANUP = CAPTURE_ROOT.with_name(CAPTURE_ROOT.name + "_cleanup_receipt.json")


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_committed_x87_campaign_rebuilds_exactly_and_is_neutral():
    receipt = _load(RECEIPT)
    rebuilt = build_score_positioning_x87_campaign_receipt(
        CAPTURE_ROOT,
        repository_root=ROOT,
    )

    assert rebuilt == receipt
    assert receipt["results"] == {
        "classification": "score_positioning_x87_rounding_mode_resolved",
        "complete_restored_snapshots": 3,
        "records_per_armed_snapshot": [1, 1, 1],
        "control_words": [639, 639, 639],
        "rounding_modes": ["nearest_even", "nearest_even", "nearest_even"],
        "stable_control_word": EXPECTED_CONTROL_WORD,
        "stable_rounding_mode": EXPECTED_ROUNDING_MODE,
        "all_semantic_outcomes_match": True,
        "semantic_sha256": (
            "957554169ca884c49e8770255ef6dc6aac5f51fafef3f64e8cad23294240c673"
        ),
    }
    assert len({tuple(pair["condition_order"]) for pair in receipt["pairs"]}) == 3
    assert all(
        pair["whole_game_outcome"]["control_dormant"] == "matched"
        and pair["whole_game_outcome"]["control_armed"] == "matched"
        and pair["whole_game_outcome"]["difference_count"] == 0
        for pair in receipt["pairs"]
    )


def test_committed_x87_campaign_selects_nearest_even_replay():
    mode = _load(RECEIPT)["results"]["stable_rounding_mode"]

    assert replay_score_positioning_native_integer(
        numerator=1, denominator=2, x87_rounding_mode=mode
    )["result"] == 0
    assert replay_score_positioning_native_integer(
        numerator=3, denominator=2, x87_rounding_mode=mode
    )["result"] == 2
    assert replay_score_positioning_native_integer(
        numerator=-1, denominator=2, x87_rounding_mode=mode
    )["result"] == 0
    assert replay_score_positioning_native_integer(
        numerator=-3, denominator=2, x87_rounding_mode=mode
    )["result"] == -2


def test_x87_cleanup_closes_pending_restore_and_binds_artifacts():
    cleanup = _load(CLEANUP)
    assert cleanup["kind"] == "observatory_score_positioning_x87_cleanup_receipt"
    assert cleanup["supersedes_pending_state"]["resolved"] is True
    assert cleanup["install_restore"]["remaining_experimental_file_count"] == 0
    assert cleanup["bridge_cleanup"]["remaining_observatory_file_count"] == 0
    assert cleanup["save_restore"]["file_set_and_bytes_match_pre_experiment"] is True
    assert cleanup["terminal_state"] == {
        "game_process_running": False,
        "score_positioning_x87_observer_installed": False,
        "rng_seed_helper_installed": False,
        "gameflow_helper_installed": False,
        "experimental_modloader_installed": False,
    }
    for section, key in (
        ("campaign_evidence", "receipt"),
        ("campaign_evidence", "observer_build_receipt"),
        ("install_restore", "post_cleanup_inventory"),
        ("save_restore", "trial_start_manifest"),
        ("save_restore", "pre_experiment_manifest"),
    ):
        artifact = cleanup[section][key]
        path = ROOT / artifact["path"]
        assert path.stat().st_size == artifact["size"]
        assert _sha256(path) == artifact["sha256"]
