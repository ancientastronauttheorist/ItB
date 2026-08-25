from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.observatory.enemy_target_area_callback_campaign import (
    EXPECTED_TARGET_AREA_EVENTS,
    SEMANTIC_SHA256,
    build_enemy_target_area_callback_campaign_receipt,
)
from src.observatory.enemy_tournament_hw_campaign import EXPECTED_CANDIDATES


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_20260824_"
    "enemy_target_area_callback"
)
RECEIPT = CAPTURE_ROOT.with_name(CAPTURE_ROOT.name + "_receipt.json")
CLEANUP = CAPTURE_ROOT.with_name(CAPTURE_ROOT.name + "_cleanup_receipt.json")
POST_INVENTORY = ROOT / "data" / "observatory" / "inventories" / (
    "windows_build_13725832_31fe35265598_"
    "post_enemy_target_area_callback_restore_20260824.json"
)
PRIOR_POST_INVENTORY = ROOT / "data" / "observatory" / "inventories" / (
    "windows_build_13725832_31fe35265598_"
    "post_enemy_tournament_hw_restore_20260824.json"
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_committed_target_area_campaign_rebuilds_exactly_and_is_neutral():
    receipt = _load(RECEIPT)
    rebuilt = build_enemy_target_area_callback_campaign_receipt(
        CAPTURE_ROOT,
        repository_root=ROOT,
    )

    assert rebuilt == receipt
    assert receipt["results"]["classification"] == (
        "fixed_firefly_get_target_area_runtime_order_correlated_to_"
        "complete_native_tournament"
    )
    assert receipt["campaign"]["condition_orders"] == [
        ["control", "exact_hook"],
        ["exact_hook", "control"],
        ["control", "exact_hook"],
    ]
    assert receipt["results"]["control_attempt_counts"] == [0, 0, 0]
    assert receipt["results"]["exact_attempt_counts"] == [9, 9, 9]
    assert receipt["results"]["exact_event_counts"] == [9, 9, 9]
    assert receipt["results"]["semantic_sha256"] == SEMANTIC_SHA256
    assert receipt["results"]["all_event_streams_match"] is True
    assert receipt["results"]["all_semantic_outcomes_match"] is True
    assert receipt["results"]["all_slots_restored"] is True
    assert receipt["results"]["serialization_error_count"] == 0
    assert receipt["results"]["restore_conflict_count"] == 0
    assert all(
        pair["trace"]["event_payloads"] == EXPECTED_TARGET_AREA_EVENTS
        and pair["callback_comparison"]["both_restored"] is True
        and pair["whole_game_outcome"] == {
            "status": "matched",
            "difference_count": 0,
            "semantic_sha256": SEMANTIC_SHA256,
        }
        for pair in receipt["pairs"]
    )


def test_committed_target_area_campaign_correlates_native_candidates():
    receipt = _load(RECEIPT)
    correlation = receipt["correlation"]

    assert correlation["candidate_count"] == len(EXPECTED_CANDIDATES) == 8
    assert correlation["selected_input_index"] == 5
    for index, (candidate, call) in enumerate(
        zip(EXPECTED_CANDIDATES, correlation["candidate_calls"], strict=True)
    ):
        assert call["candidate_index"] == call["call_order"] == index
        assert call["origin"] == [
            candidate["destination_x"],
            candidate["destination_y"],
        ]
        assert call["candidate_target"] == [
            candidate["target_x"],
            candidate["target_y"],
        ]
        assert call["candidate_target_area_index"] == 3
        assert call["target_area"][3] == call["candidate_target"]
    repeat = correlation["selected_destination_repeat"]
    assert repeat["call_order"] == 8
    assert repeat["matches_candidate_call_order"] == 5
    assert repeat["origin"] == correlation["candidate_calls"][5]["origin"]
    assert repeat["target_area"] == correlation["candidate_calls"][5]["target_area"]
    assert receipt["solver_conformance"]["rust_change_required"] is False
    assert receipt["solver_conformance"]["simulator_version_bump_required"] is False


def test_target_area_cleanup_closes_restore_and_binds_artifacts():
    campaign = _load(RECEIPT)
    cleanup = _load(CLEANUP)
    assert cleanup["kind"] == (
        "observatory_enemy_target_area_callback_cleanup_receipt"
    )
    assert cleanup["supersedes_pending_state"]["resolved"] is True
    assert campaign["restore"]["install_restoration_pending"] is True
    assert campaign["restore"]["save_restoration_pending"] is True
    assert cleanup["install_restore"]["baseline_loader_restored_byte_exact"] is True
    assert cleanup["install_restore"]["removed_experimental_file_count"] == 10
    assert cleanup["install_restore"]["remaining_experimental_file_count"] == 0
    assert cleanup["bridge_cleanup"]["removed_observatory_file_count"] == 2
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


def test_post_cleanup_inventory_preserves_exact_campaign_baseline_content():
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
    assert current["steam"]["evidence"]["sha256"] != prior["steam"]["evidence"][
        "sha256"
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
