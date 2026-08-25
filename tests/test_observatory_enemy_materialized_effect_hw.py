from __future__ import annotations

import copy

import pytest

from src.observatory.enemy_record_selector_boundary import (
    replay_enemy_record_selector,
)
from src.observatory.enemy_materialized_effect_hw import (
    EXPECTED_BOUNDARY_MAP_SHA256,
    EXPECTED_EXECUTABLE_SHA256,
    EXPECTED_MATERIALIZED_PREBYTES_SHA256,
    EXPECTED_PLAN_SHA256,
    EXPECTED_QUEUE_PREBYTES_SHA256,
    EXPECTED_RECORD_SELECTOR_SHA256,
    EXPECTED_RNG_RETURN_MAP_SHA256,
    EXPECTED_RNG_STATE_OWNER_SHA256,
    EXPECTED_SELECTED_PREBYTES_SHA256,
    EXPECTED_SELECTED_QUEUE_SOURCE_SHA256,
    EXPECTED_SELECTOR_PREBYTES_SHA256,
    EXPECTED_SKILL_EFFECT_BOUNDARY_SHA256,
    EnemyMaterializedEffectHwError,
    correlate_enemy_materialized_effect_snapshot,
    validate_enemy_materialized_effect_snapshot,
)
from src.observatory.msvc_rng_replay import advance_state


MODULE_SHA = "1" * 64
INVENTORY_SHA = "2" * 64


def _receipt() -> dict:
    return {
        "schema_version": 1,
        "kind": "observatory_enemy_materialized_effect_hw_observer_build",
        "observer_version": "observatory-enemy-materialized-effect-hw-observer/1",
        "build_id": "13725832",
        "architecture": "x86",
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        "executable_size": 5_530_112,
        "module_sha256": MODULE_SHA,
        "hardware_breakpoint_plan_sha256": EXPECTED_PLAN_SHA256,
        "boundary_map_canonical_sha256": EXPECTED_BOUNDARY_MAP_SHA256,
        "rng_return_map_sha256": EXPECTED_RNG_RETURN_MAP_SHA256,
        "record_selector_boundary_canonical_sha256": (
            EXPECTED_RECORD_SELECTOR_SHA256
        ),
        "skill_effect_boundary_canonical_sha256": (
            EXPECTED_SKILL_EFFECT_BOUNDARY_SHA256
        ),
        "selected_queue_source_sha256": EXPECTED_SELECTED_QUEUE_SOURCE_SHA256,
        "selector_prebytes_sha256": EXPECTED_SELECTOR_PREBYTES_SHA256,
        "selected_prebytes_sha256": EXPECTED_SELECTED_PREBYTES_SHA256,
        "queue_prebytes_sha256": EXPECTED_QUEUE_PREBYTES_SHA256,
        "materialized_prebytes_sha256": EXPECTED_MATERIALIZED_PREBYTES_SHA256,
        "rng_state_owner_sha256": EXPECTED_RNG_STATE_OWNER_SHA256,
        "inventory_canonical_sha256": INVENTORY_SHA,
        "loaded_or_armed": False,
        "executable_bytes_modified": False,
        "reproducibility": {
            "independent_build_count": 2,
            "module_bytes_identical": True,
            "attestations_identical": True,
        },
        "source_attestation": {
            "selected_queue_dependency_include_present": True,
            "historical_opener_export_neutralized": True,
            "executable_mutation_api_text_absent": True,
        },
        "machine_attestation": {
            "loader_entry_absent": True,
            "executable_mutation_api_imports_absent": True,
            "veh": {
                "direct_or_indirect_call_count": 0,
                "windows_api_call_count": 0,
                "x87_mmx_sse_avx_instruction_count": 0,
            },
        },
    }


def _candidates() -> list[dict]:
    return [
        {
            "seq": 0,
            "destination_x": 2,
            "destination_y": 2,
            "target_x": 3,
            "target_y": 2,
            "target_score": 2,
            "positioning_score": 0,
        },
        {
            "seq": 1,
            "destination_x": 3,
            "destination_y": 3,
            "target_x": 4,
            "target_y": 3,
            "target_score": 3,
            "positioning_score": 0,
        },
    ]


def _snapshot(*, rng_before: int = 2) -> dict:
    candidates = _candidates()
    records = [{key: value for key, value in item.items() if key != "seq"} for item in candidates]
    replay = replay_enemy_record_selector(records, rng_before)
    rng_after = rng_before
    for _ in range(replay["draw_count"]):
        rng_after = advance_state(rng_after)
    selected = replay["selected_record"]
    return {
        "schema_version": 1,
        "kind": "native_enemy_materialized_effect_hw_snapshot",
        "observer_version": "observatory-enemy-materialized-effect-hw-observer/1",
        "capture_id": "materialized_effect-test-001",
        "identity": {
            "platform": "windows",
            "architecture": "x86",
            "build_id": "13725832",
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": 5_530_112,
            "inventory_sha256": INVENTORY_SHA,
            "boundary_map_sha256": EXPECTED_BOUNDARY_MAP_SHA256,
            "rng_return_map_sha256": EXPECTED_RNG_RETURN_MAP_SHA256,
            "record_selector_boundary_sha256": EXPECTED_RECORD_SELECTOR_SHA256,
            "skill_effect_boundary_sha256": EXPECTED_SKILL_EFFECT_BOUNDARY_SHA256,
            "selected_queue_source_sha256": EXPECTED_SELECTED_QUEUE_SOURCE_SHA256,
            "hardware_breakpoint_plan_sha256": EXPECTED_PLAN_SHA256,
            "selector_prebytes_sha256": EXPECTED_SELECTOR_PREBYTES_SHA256,
            "selected_prebytes_sha256": EXPECTED_SELECTED_PREBYTES_SHA256,
            "queue_prebytes_sha256": EXPECTED_QUEUE_PREBYTES_SHA256,
            "materialized_prebytes_sha256": EXPECTED_MATERIALIZED_PREBYTES_SHA256,
            "rng_state_owner_sha256": EXPECTED_RNG_STATE_OWNER_SHA256,
        },
        "integrity": {
            "state": "restored",
            "complete": True,
            "overflow_count": 0,
            "ordering_error_count": 0,
            "pointer_fault_count": 0,
            "transition_mismatch_count": 0,
            "wrong_thread_count": 0,
            "unexpected_breakpoint_count": 0,
            "torn_candidate_count": 0,
            "torn_record_count": 0,
            "torn_materialized_count": 0,
            "debug_registers_armed": False,
            "debug_registers_cleared": True,
            "veh_installed": False,
            "veh_removed": True,
            "executable_file_released": True,
            "executable_bytes_modified": False,
            "seam_bytes_unchanged": True,
            "addresses_or_pointers_published": False,
        },
        "selector_context": {
            "pawn_id": 1303,
            "current_weapon_raw": 1,
            "base_current_weapon_raw": -1,
            "board_width": 8,
            "board_height": 8,
            "interior_favorable": replay["interior_favorable"],
            "selector_rng_state_before": f"0x{rng_before:08x}",
            "selector_rng_state_after": f"0x{rng_after:08x}",
        },
        "candidate_records": candidates,
        "selected_record": {
            "kind": "selected_record",
            "seq": 0,
            "pawn_id": 1303,
            "current_weapon_raw": 1,
            "base_current_weapon_raw": -1,
            "ai_dest_x": selected["destination_x"],
            "ai_dest_y": selected["destination_y"],
            "ai_target_x": selected["target_x"],
            "ai_target_y": selected["target_y"],
            "selected_field_4_raw": selected["target_score"],
            "selected_field_5_raw": selected["positioning_score"],
        },
        "materialized_effect": {
            "effect_count": 0,
            "queued_count": 1,
            "owner_id": 1303,
            "skill_owner_id": 1303,
            "skill_source_tag": 7,
            "origin_x": selected["destination_x"],
            "origin_y": selected["destination_y"],
            "selected_target_x": selected["target_x"],
            "selected_target_y": selected["target_y"],
            "queued_loc_x": (
                selected["target_x"]
                + selected["target_x"]
                - selected["destination_x"]
            ),
            "queued_loc_y": (
                selected["target_y"]
                + selected["target_y"]
                - selected["destination_y"]
            ),
            "queued_damage": 1,
            "queued_private_origin_x": selected["destination_x"],
            "queued_private_origin_y": selected["destination_y"],
            "queued_private_source_tag": 7,
            "queued_boost_marker": False,
            "queued_animation_length": len("ExploFirefly1"),
            "queued_animation": "ExploFirefly1",
            "skill_key_length": len("FireflyAtk1"),
            "skill_key": "FireflyAtk1",
        },
        "queued_action": {
            "kind": "queued_action",
            "seq": 1,
            "pawn_id": 1303,
            "current_weapon_raw": 1,
            "base_current_weapon_raw": 1,
            "target_x": selected["target_x"],
            "target_y": selected["target_y"],
            "origin_x": selected["destination_x"],
            "origin_y": selected["destination_y"],
            "queued_shot_x": selected["target_x"],
            "queued_shot_y": selected["target_y"],
            "queued_skill_raw": 1,
        },
        "summary": {
            "selector_count": 1,
            "candidate_count": len(candidates),
            "selected_count": 1,
            "materialized_effect_count": 1,
            "queue_count": 1,
            "pair_count": 1,
            "thread_count": 1,
            "stage": 4,
            "pending_selection": False,
        },
    }


def _outcome() -> dict:
    return {
        "mission_id": "Mission_Power",
        "phase": "combat_player",
        "spawning_tiles": [],
        "environment_danger": [],
        "environment_danger_v2": [],
        "targeted_tiles": [[3, 2], [4, 2]],
        "units": [
            {
                "team": 6,
                "uid": 1303,
                "type": "Firefly1",
                "x": 2,
                "y": 2,
                "has_queued_attack": True,
                "queued_origin": None,
                "queued_target": None,
                "queued_target_raw": None,
            }
        ],
    }


def test_snapshot_replays_complete_ordered_materialized_effect_and_rng_state_exactly():
    result = validate_enemy_materialized_effect_snapshot(
        _snapshot(), build_receipt=_receipt(), observed_module_sha256=MODULE_SHA
    )

    assert result["replay"]["selected_source"] == "displaced_primary_fallback"
    assert result["replay"]["selected_input_index"] == 0
    assert [item["caller_id"] for item in result["replay"]["rng_transcript"]] == [
        30,
        31,
        33,
    ]
    assert result["expected_rng_state_after"] == "0x5e86b31f"
    assert result["selected"]["ai_dest_x"] == 2
    assert result["materialized_effect"]["queued_loc_x"] == 4
    assert result["queued"]["origin_x"] == 2


def test_raw_hidden_rng_bit_is_preserved_while_selector_replay_stays_equivalent():
    result = validate_enemy_materialized_effect_snapshot(
        _snapshot(rng_before=0x80000002),
        build_receipt=_receipt(),
        observed_module_sha256=MODULE_SHA,
    )

    assert result["replay"]["canonical_observable_pre_call_state"] == "0x00000002"
    assert result["selector_context"]["selector_rng_state_after"] == "0xde86b31f"


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda value: value["selected_record"].__setitem__(
                "selected_field_4_raw", 99
            ),
            "selected record differs",
        ),
        (
            lambda value: value["selector_context"].__setitem__(
                "selector_rng_state_after", "0x00000000"
            ),
            "RNG-after state differs",
        ),
        (
            lambda value: value["selector_context"].__setitem__(
                "interior_favorable", False
            ),
            "interior-favorable flag differs",
        ),
        (
            lambda value: value["queued_action"].__setitem__("target_x", 4),
            "does not bind to queue commit",
        ),
        (
            lambda value: value["queued_action"].__setitem__(
                "base_current_weapon_raw", -1
            ),
            "does not bind to queue commit",
        ),
        (
            lambda value: value["materialized_effect"].__setitem__(
                "skill_owner_id", 999
            ),
            "materialized SkillEffect does not bind",
        ),
        (
            lambda value: value["materialized_effect"].__setitem__(
                "queued_loc_y", 3
            ),
            "not on the selected attack ray",
        ),
        (
            lambda value: value["materialized_effect"].__setitem__(
                "skill_key_length", 1
            ),
            "length or bytes differ",
        ),
        (
            lambda value: value["candidate_records"][1].__setitem__("seq", 0),
            "record order differs",
        ),
        (
            lambda value: value["integrity"].__setitem__(
                "addresses_or_pointers_published", True
            ),
            "not fully restored",
        ),
    ],
)
def test_snapshot_rejects_replay_queue_order_and_integrity_drift(mutator, message):
    snapshot = _snapshot()
    mutator(snapshot)

    with pytest.raises(EnemyMaterializedEffectHwError, match=message):
        validate_enemy_materialized_effect_snapshot(
            snapshot, build_receipt=_receipt(), observed_module_sha256=MODULE_SHA
        )


def test_snapshot_rejects_extra_fields_and_receipt_safety_drift():
    snapshot = _snapshot()
    snapshot["native_pointer"] = "0x12345678"
    with pytest.raises(EnemyMaterializedEffectHwError, match="snapshot fields differ"):
        validate_enemy_materialized_effect_snapshot(
            snapshot, build_receipt=_receipt(), observed_module_sha256=MODULE_SHA
        )

    receipt = _receipt()
    receipt["machine_attestation"]["veh"][
        "x87_mmx_sse_avx_instruction_count"
    ] = 1
    with pytest.raises(EnemyMaterializedEffectHwError, match="safety attestation"):
        validate_enemy_materialized_effect_snapshot(
            _snapshot(), build_receipt=receipt, observed_module_sha256=MODULE_SHA
        )


def test_correlator_binds_exact_native_replay_to_bridge_queue():
    result = correlate_enemy_materialized_effect_snapshot(
        _snapshot(),
        _outcome(),
        build_receipt=_receipt(),
        observed_module_sha256=MODULE_SHA,
    )

    assert result["status"] == "correlated"
    assert result["summary"] == {
        "native_replay_exact": True,
        "selected_queue_binding_exact": True,
        "materialized_effect_binding_exact": True,
        "bridge_queue_matches": True,
        "correlated": True,
    }
    assert result["native"]["candidate_count"] == 2
    assert result["native"]["materialized_queued_loc"] == [4, 2]
    assert result["native"]["native_skill_key"] == "FireflyAtk1"
    assert result["bridge"]["queue_corroboration"] == "targeted_tiles_ray"


def test_correlator_reports_bridge_mismatch_without_weakening_native_proof():
    outcome = copy.deepcopy(_outcome())
    outcome["units"][0]["uid"] = 999

    result = correlate_enemy_materialized_effect_snapshot(
        _snapshot(),
        outcome,
        build_receipt=_receipt(),
        observed_module_sha256=MODULE_SHA,
    )

    assert result["status"] == "unresolved"
    assert "bridge_selected_enemy_missing" in result["reasons"]
    assert result["summary"]["native_replay_exact"] is True
