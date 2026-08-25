from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.observatory.enemy_materialized_effect_hw_campaign import (
    EXPECTED_CANDIDATES,
    EXPECTED_MATERIALIZED_EFFECT,
    build_enemy_materialized_effect_hw_campaign_receipt,
)
from src.observatory.enemy_record_selector_boundary import (
    replay_enemy_record_selector,
)


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_20260824_"
    "enemy_materialized_effect_hw"
)
RECEIPT = CAPTURE_ROOT.with_name(CAPTURE_ROOT.name + "_receipt.json")
CLEANUP = CAPTURE_ROOT.with_name(CAPTURE_ROOT.name + "_cleanup_receipt.json")
POST_INVENTORY = ROOT / "data" / "observatory" / "inventories" / (
    "windows_build_13725832_31fe35265598_"
    "post_enemy_materialized_effect_hw_restore_20260824.json"
)
PRIOR_POST_INVENTORY = ROOT / "data" / "observatory" / "inventories" / (
    "windows_build_13725832_31fe35265598_"
    "post_enemy_skill_effect_callback_restore_20260824.json"
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_artifact(artifact: dict) -> None:
    path = ROOT / artifact["path"]
    assert path.stat().st_size == artifact["size"]
    assert _sha256(path) == artifact["sha256"]


def test_committed_enemy_materialized_effect_rebuilds_exactly_and_is_neutral():
    receipt = _load(RECEIPT)
    rebuilt = build_enemy_materialized_effect_hw_campaign_receipt(
        CAPTURE_ROOT,
        repository_root=ROOT,
    )

    assert rebuilt == receipt
    assert receipt["results"]["classification"] == (
        "selected_firefly_skill_effect_materialization_runtime_proven"
    )
    assert receipt["campaign"]["condition_orders"] == [
        ["control", "dormant", "armed"],
        ["armed", "dormant", "control"],
        ["dormant", "control", "armed"],
    ]
    assert receipt["results"]["candidate_counts"] == [8, 8, 8]
    assert receipt["results"]["draw_counts"] == [1, 1, 1]
    assert receipt["results"]["selected_input_indices"] == [5, 5, 5]
    assert receipt["results"]["materialized_effects"] == [
        EXPECTED_MATERIALIZED_EFFECT
    ] * 3
    assert receipt["results"]["materialized_locations"] == [[3, 4]] * 3
    assert receipt["results"]["materialized_damages"] == [1, 1, 1]
    assert receipt["results"]["materialized_animations"] == [
        "ExploFirefly1"
    ] * 3
    assert receipt["results"]["native_skill_keys"] == ["FireflyAtk1"] * 3
    assert receipt["results"]["all_armed_observations_match"] is True
    assert receipt["results"]["all_semantic_outcomes_match"] is True
    assert receipt["results"]["semantic_sha256"] == (
        "957554169ca884c49e8770255ef6dc6aac5f51fafef3f64e8cad23294240c673"
    )
    assert all(
        pair["whole_game_outcome"]
        == {
            "control_armed": "matched",
            "control_dormant": "matched",
            "difference_count": 0,
            "semantic_sha256": (
                "957554169ca884c49e8770255ef6dc6aac5f51fafef3f64e8cad23294240c673"
            ),
        }
        and pair["observer_integrity"]["torn_materialized_count"] == 0
        for pair in receipt["pairs"]
    )


def test_committed_enemy_materialized_effect_binds_raw_selected_and_settled_queue():
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
    assert replay["canonical_observable_final_state"] == "0x6f5d21d2"
    assert observation["materialized_effect"] == EXPECTED_MATERIALIZED_EFFECT
    assert observation["materialized_effect"]["origin_x"] == 5
    assert observation["materialized_effect"]["origin_y"] == 4
    assert observation["materialized_effect"]["selected_target_x"] == 4
    assert observation["materialized_effect"]["selected_target_y"] == 4
    assert observation["materialized_effect"]["queued_loc_x"] == 3
    assert observation["materialized_effect"]["queued_loc_y"] == 4
    assert observation["queue_origin"] == [5, 4]
    assert observation["queued_shot"] == [4, 4]
    assert receipt["solver_conformance"]["rust_change_required"] is False
    assert receipt["solver_conformance"][
        "simulator_version_bump_required"
    ] is False


def test_enemy_materialized_effect_cleanup_closes_restore_and_binds_artifacts():
    campaign = _load(RECEIPT)
    cleanup = _load(CLEANUP)

    assert cleanup["kind"] == (
        "observatory_enemy_materialized_effect_hw_cleanup_receipt"
    )
    assert campaign["restore"]["install_restoration_pending"] is True
    assert campaign["restore"]["save_restoration_pending"] is True
    assert cleanup["supersedes_pending_state"]["resolved"] is True
    assert cleanup["install_restore"]["baseline_loader_restored_byte_exact"] is True
    assert cleanup["install_restore"]["quarantined_experimental_dll_count"] == 3
    assert cleanup["install_restore"]["remaining_experimental_file_count"] == 0
    assert cleanup["bridge_cleanup"]["accepted_snapshot_count_archived"] == 3
    assert cleanup["bridge_cleanup"]["remaining_observatory_file_count"] == 0
    assert cleanup["bridge_cleanup"][
        "remaining_rejected_snapshot_or_temp_count"
    ] == 0
    assert cleanup["save_restore"][
        "file_set_and_bytes_match_pre_experiment"
    ] is True
    assert cleanup["terminal_state"] == {
        "continue_helper_installed": False,
        "enemy_materialized_effect_hw_observer_installed": False,
        "experimental_modloader_installed": False,
        "game_process_running": False,
        "observatory_bridge_artifact_present": False,
        "rng_seed_helper_installed": False,
    }
    for artifact in (
        cleanup["campaign_evidence"]["receipt"],
        cleanup["campaign_evidence"]["observer_build_receipt"],
        cleanup["campaign_evidence"]["hardware_breakpoint_plan"],
        cleanup["install_restore"]["post_cleanup_inventory"],
        cleanup["save_restore"]["pre_experiment_manifest"],
        cleanup["save_restore"]["post_cleanup_manifest"],
        *cleanup["rejected_diagnostics"]["artifacts"],
    ):
        _assert_artifact(artifact)

    before = _load(
        ROOT / cleanup["save_restore"]["pre_experiment_manifest"]["path"]
    )
    after = _load(
        ROOT / cleanup["save_restore"]["post_cleanup_manifest"]["path"]
    )
    assert before == after
    assert before["file_count"] == 32
    assert before["total_bytes"] == 2_434_067
    assert before["tree_sha256"] == campaign["campaign"]["save_tree_sha256"]


def test_post_cleanup_inventory_preserves_prior_campaign_baseline_content():
    current = _load(POST_INVENTORY)
    prior = _load(PRIOR_POST_INVENTORY)

    assert current["executable"] == prior["executable"]
    assert current["native_libraries"] == prior["native_libraries"]
    assert current["content"]["scripts"] == prior["content"]["scripts"]
    assert current["content"]["maps"] == prior["content"]["maps"]
    assert current["steam"]["build_id"] == prior["steam"]["build_id"]
    assert current["steam"]["installed_depots"] == prior["steam"][
        "installed_depots"
    ]
    scripts = {
        item["path"]: item for item in current["content"]["scripts"]["files"]
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
        for item in current["native_libraries"]
    )
