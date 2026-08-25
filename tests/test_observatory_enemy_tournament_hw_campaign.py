from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.observatory.enemy_record_selector_boundary import (
    replay_enemy_record_selector,
)
from src.observatory.enemy_tournament_hw_campaign import (
    EXPECTED_CANDIDATES,
    build_enemy_tournament_hw_campaign_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_20260824_"
    "enemy_tournament_hw"
)
RECEIPT = CAPTURE_ROOT.with_name(CAPTURE_ROOT.name + "_receipt.json")
CLEANUP = CAPTURE_ROOT.with_name(CAPTURE_ROOT.name + "_cleanup_receipt.json")


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_committed_enemy_tournament_rebuilds_exactly_and_is_neutral():
    receipt = _load(RECEIPT)
    rebuilt = build_enemy_tournament_hw_campaign_receipt(
        CAPTURE_ROOT,
        repository_root=ROOT,
    )

    assert rebuilt == receipt
    assert receipt["results"]["classification"] == (
        "complete_enemy_record_tournament_runtime_replay"
    )
    assert receipt["results"]["complete_restored_snapshots"] == 3
    assert receipt["results"]["candidate_counts"] == [8, 8, 8]
    assert receipt["results"]["draw_counts"] == [1, 1, 1]
    assert receipt["results"]["caller_ids"] == [30, 30, 30]
    assert receipt["results"]["selected_input_indices"] == [5, 5, 5]
    assert receipt["results"]["all_armed_observations_match"] is True
    assert receipt["results"]["all_semantic_outcomes_match"] is True
    assert receipt["results"]["semantic_sha256"] == (
        "957554169ca884c49e8770255ef6dc6aac5f51fafef3f64e8cad23294240c673"
    )
    assert len({tuple(pair["condition_order"]) for pair in receipt["pairs"]}) == 3
    assert all(
        pair["whole_game_outcome"]["control_dormant"] == "matched"
        and pair["whole_game_outcome"]["control_armed"] == "matched"
        and pair["whole_game_outcome"]["difference_count"] == 0
        for pair in receipt["pairs"]
    )


def test_committed_enemy_tournament_replays_exact_selection_and_queue():
    receipt = _load(RECEIPT)
    observation = receipt["pairs"][0]["observation"]
    replay = replay_enemy_record_selector(
        observation["candidate_records"],
        int(observation["selector_context"]["selector_rng_state_before"], 16),
        board_width=8,
        board_height=8,
    )

    assert observation["candidate_records"] == EXPECTED_CANDIDATES
    assert replay["selected_input_index"] == 5
    assert replay["selected_record"] == EXPECTED_CANDIDATES[5]
    assert replay["draw_count"] == 1
    assert replay["rng_transcript"][0]["caller_id"] == 30
    assert replay["canonical_observable_final_state"] == "0x6f5d21d2"
    assert observation["queue_origin"] == [5, 4]
    assert observation["queued_shot"] == [4, 4]
    assert observation["base_current_weapon_before_queue_raw"] == -1
    assert observation["base_current_weapon_at_queue_raw"] == 1


def test_enemy_tournament_cleanup_closes_restore_and_binds_artifacts():
    cleanup = _load(CLEANUP)
    assert cleanup["kind"] == "observatory_enemy_tournament_hw_cleanup_receipt"
    assert cleanup["supersedes_pending_state"]["resolved"] is True
    assert cleanup["install_restore"]["remaining_experimental_file_count"] == 0
    assert cleanup["bridge_cleanup"]["remaining_observatory_file_count"] == 0
    assert cleanup["save_restore"][
        "file_set_and_bytes_match_pre_experiment"
    ] is True
    assert cleanup["terminal_state"] == {
        "game_process_running": False,
        "enemy_tournament_hw_observer_installed": False,
        "rng_seed_helper_installed": False,
        "gameflow_helper_installed": False,
        "experimental_modloader_installed": False,
    }
    for section, key in (
        ("campaign_evidence", "receipt"),
        ("campaign_evidence", "observer_build_receipt"),
        ("campaign_evidence", "hardware_breakpoint_plan"),
        ("install_restore", "post_cleanup_inventory"),
        ("save_restore", "pre_experiment_manifest"),
    ):
        artifact = cleanup[section][key]
        path = ROOT / artifact["path"]
        assert path.stat().st_size == artifact["size"]
        assert _sha256(path) == artifact["sha256"]

    inventory = _load(
        ROOT / cleanup["install_restore"]["post_cleanup_inventory"]["path"]
    )
    scripts = {
        item["path"]: item
        for item in inventory["content"]["scripts"]["files"]
    }
    assert scripts["scripts/modloader.lua"] == {
        "path": "scripts/modloader.lua",
        "sha256": (
            "5af8e809e6ed036084c84caed97f6a51"
            "a84785db2c2c0ee0c150da99adabf22d"
        ),
        "size": 315686,
    }
    assert all(
        "observatory" not in item["path"].lower()
        for item in inventory["native_libraries"]
    )
    manifest = _load(
        ROOT / cleanup["save_restore"]["pre_experiment_manifest"]["path"]
    )
    assert manifest["tree_sha256"] == cleanup["save_restore"][
        "final_live_tree_sha256"
    ]
