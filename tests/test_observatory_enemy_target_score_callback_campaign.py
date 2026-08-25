from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.observatory.enemy_target_score_callback_campaign import (
    EXPECTED_TARGET_SCORE_EVENTS,
    SEMANTIC_SHA256,
    build_enemy_target_score_callback_campaign_receipt,
)
from src.observatory.enemy_tournament_hw_campaign import EXPECTED_CANDIDATES


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_20260824_"
    "enemy_target_score_callback"
)
RECEIPT = CAPTURE_ROOT.with_name(CAPTURE_ROOT.name + "_receipt.json")
CLEANUP = CAPTURE_ROOT.with_name(CAPTURE_ROOT.name + "_cleanup_receipt.json")
REJECTED = CAPTURE_ROOT.with_name(
    CAPTURE_ROOT.name + "_pair002_precommand_rejection.json"
)
POST_INVENTORY = ROOT / "data" / "observatory" / "inventories" / (
    "windows_build_13725832_31fe35265598_"
    "post_enemy_target_score_callback_restore_20260824.json"
)
PRIOR_POST_INVENTORY = ROOT / "data" / "observatory" / "inventories" / (
    "windows_build_13725832_31fe35265598_"
    "post_enemy_target_area_callback_restore_20260824.json"
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_committed_target_score_campaign_rebuilds_exactly_and_is_neutral():
    receipt = _load(RECEIPT)
    rebuilt = build_enemy_target_score_callback_campaign_receipt(
        CAPTURE_ROOT,
        repository_root=ROOT,
    )

    assert rebuilt == receipt
    assert receipt["results"]["classification"] == (
        "fixed_firefly_get_target_score_runtime_matrix_correlated_to_"
        "target_areas_and_complete_native_tournament"
    )
    assert receipt["campaign"]["condition_orders"] == [
        ["control", "exact_hook"],
        ["exact_hook", "control"],
        ["control", "exact_hook"],
    ]
    assert receipt["results"]["control_attempt_counts"] == [0, 0, 0]
    assert receipt["results"]["exact_attempt_counts"] == [32, 32, 32]
    assert receipt["results"]["exact_event_counts"] == [32, 32, 32]
    assert receipt["results"]["semantic_sha256"] == SEMANTIC_SHA256
    assert receipt["results"]["all_event_streams_match"] is True
    assert receipt["results"]["all_semantic_outcomes_match"] is True
    assert receipt["results"]["all_slots_restored"] is True
    assert receipt["results"]["serialization_error_count"] == 0
    assert receipt["results"]["restore_conflict_count"] == 0
    assert all(
        pair["trace"]["event_payloads"] == EXPECTED_TARGET_SCORE_EVENTS
        and pair["trace"]["installed_get_target_score_slots"] == 15
        and pair["callback_comparison"]["both_restored"] is True
        and pair["whole_game_outcome"]
        == {
            "status": "matched",
            "difference_count": 0,
            "semantic_sha256": SEMANTIC_SHA256,
        }
        for pair in receipt["pairs"]
    )


def test_committed_target_score_campaign_correlates_areas_and_native_candidates():
    receipt = _load(RECEIPT)
    groups = receipt["correlation"]["score_groups"]

    assert len(groups) == len(EXPECTED_CANDIDATES) == 8
    for index, (candidate, group) in enumerate(
        zip(EXPECTED_CANDIDATES, groups, strict=True)
    ):
        assert group["candidate_index"] == index
        assert group["get_target_area_call_order"] == index
        assert group["get_target_score_call_orders"] == list(
            range(index * 4, index * 4 + 4)
        )
        assert group["origin"] == [
            candidate["destination_x"],
            candidate["destination_y"],
        ]
        assert group["raw_callback_scores"] == [0, 0, 0, 5]
        assert group["raw_unique_best_index"] == 3
        assert group["raw_unique_best_target"] == group["target_area"][3]
        assert group["native_candidate_target"] == [
            candidate["target_x"],
            candidate["target_y"],
        ]
        assert group["native_candidate_target_score"] == 5
        assert group["raw_best_matches_native_candidate"] is True
    repeat = receipt["correlation"]["selected_destination_repeat"]
    assert repeat["target_area_call_order"] == 8
    assert repeat["matches_candidate_index"] == 5
    assert repeat["additional_score_group_observed"] is False
    assert receipt["solver_conformance"]["rust_change_required"] is False
    assert receipt["solver_conformance"]["simulator_version_bump_required"] is False


def test_pair002_retained_output_attempt_is_bound_as_rejected_not_evidence():
    receipt = _load(RECEIPT)
    rejected = _load(REJECTED)
    diagnostic = receipt["diagnostics"]["pair002_precommand_rejection"]

    assert rejected["status"] == "rejected"
    assert rejected["valid_trial"] is False
    assert rejected["command_ack"] is None
    assert rejected["errors"]["command"] == (
        "enemy callback trial output already exists"
    )
    assert diagnostic["classification"] == (
        "safely_rejected_before_game_command"
    )
    assert diagnostic["chronology"] == (
        "after_exact_hook_before_accepted_control"
    )
    assert diagnostic["accepted_as_campaign_evidence"] is False
    assert receipt["campaign"]["accepted_trial_count"] == 6
    assert receipt["campaign"]["rejected_pre_command_trial_count"] == 1
    assert _sha256(REJECTED) == diagnostic["artifact"]["sha256"]


def test_target_score_cleanup_closes_restore_and_binds_artifacts():
    campaign = _load(RECEIPT)
    cleanup = _load(CLEANUP)
    assert cleanup["kind"] == (
        "observatory_enemy_target_score_callback_cleanup_receipt"
    )
    assert cleanup["supersedes_pending_state"]["resolved"] is True
    assert campaign["restore"]["install_restoration_pending"] is True
    assert campaign["restore"]["save_restoration_pending"] is True
    assert cleanup["install_restore"]["baseline_loader_restored_byte_exact"] is True
    assert cleanup["install_restore"]["removed_experimental_file_count"] == 10
    assert cleanup["install_restore"]["remaining_experimental_file_count"] == 0
    assert cleanup["bridge_cleanup"]["removed_observatory_file_count"] == 7
    assert cleanup["bridge_cleanup"]["remaining_observatory_file_count"] == 0
    assert cleanup["save_restore"]["file_set_and_bytes_match_pre_experiment"] is True
    assert cleanup["terminal_state"] == {
        "game_process_running": False,
        "callback_capsule_installed": False,
        "callback_controller_installed": False,
        "rng_seed_helper_installed": False,
        "gameflow_helper_installed": False,
        "experimental_modloader_installed": False,
        "observatory_bridge_artifact_present": False,
    }
    for artifact in (
        cleanup["campaign_evidence"]["receipt"],
        cleanup["campaign_evidence"]["rejected_precommand_diagnostic"],
        cleanup["install_restore"]["post_cleanup_inventory"],
        cleanup["save_restore"]["pre_experiment_manifest"],
        cleanup["save_restore"]["post_cleanup_manifest"],
    ):
        path = ROOT / artifact["path"]
        assert path.stat().st_size == artifact["size"]
        assert _sha256(path) == artifact["sha256"]

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


def test_post_cleanup_inventory_preserves_target_area_baseline_content():
    current = _load(POST_INVENTORY)
    prior = _load(PRIOR_POST_INVENTORY)

    assert current["executable"] == prior["executable"]
    assert current["native_libraries"] == prior["native_libraries"]
    assert current["content"]["scripts"] == prior["content"]["scripts"]
    assert current["content"]["maps"] == prior["content"]["maps"]
    assert current["steam"]["build_id"] == prior["steam"]["build_id"]
    assert (
        current["steam"]["installed_depots"]
        == prior["steam"]["installed_depots"]
    )
    assert current["steam"]["evidence"]["sha256"] != prior["steam"][
        "evidence"
    ]["sha256"]
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
