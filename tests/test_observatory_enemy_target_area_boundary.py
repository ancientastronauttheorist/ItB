from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.enemy_target_area_boundary import (
    ANALYSIS_KIND,
    REPAIR_SKILL_ID,
    REPAIR_SKILL_INDEX,
    TARGET_AREA_GATE_REPLAY_KIND,
    EnemyTargetAreaBoundaryError,
    encode_enemy_target_area_boundary_map,
    replay_enemy_target_area_gate,
    replay_usable_skill_scan,
    resolve_enemy_skill_index,
    validate_enemy_target_area_boundary_map,
    validate_enemy_target_area_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_enemy_target_area_boundary.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(BOUNDARY_MAP.read_text(encoding="utf-8"))


def _skill(skill_id: str, limited: int = 0, remaining: int = 0) -> dict:
    return {
        "id": skill_id,
        "limited": limited,
        "remaining_uses": remaining,
    }


def _gate(**overrides: object) -> dict:
    payload = {
        "candidate_mode": 0,
        "board_attached": True,
        "active": True,
        "smoke_on_tile": False,
        "busy": False,
        "ignore_smoke": False,
        "disable_immunity": False,
        "terrain_is_water": False,
        "flying": False,
        "bonus_shift": 0,
        "is_mech": False,
        "skills": [_skill("FireflyAtk1")],
        "selected_weapon": 0,
    }
    payload.update(overrides)
    return replay_enemy_target_area_gate(**payload)


def test_committed_map_binds_complete_gate_without_callback_overclaim():
    value = _load()
    result = validate_enemy_target_area_boundary_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "80b8f425daacfc82e5a320e9922bcd60d7c3ff676e400ea7e21d72e230d5f009"
        ),
        "ordinary_target_area_gate_complete": True,
        "repair_sentinel_resolved": True,
        "lua_target_area_output_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["summary"] == {
        "region_count": 26,
        "control_window_count": 18,
        "direct_edge_count": 13,
        "call_inventory_count": 3,
        "data_anchor_count": 16,
        "method_binding_count": 5,
        "verified_core_lua_file_count": 152,
        "raw_non_line_comment_literal_match_count": 206,
        "block_commented_literal_match_count": 8,
        "active_literal_skill_list_assignment_count": 198,
        "maximum_literal_skill_list_arity": 2,
        "replay_vector_count": 17,
        "finding_count": 6,
        "unresolved_count": 4,
        "ordinary_target_area_gate_complete": True,
        "repair_sentinel_resolved": True,
        "lua_target_area_output_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def test_repair_sentinel_is_separate_and_checked_before_vector_bounds():
    value = _load()
    binding = value["contracts"]["field_bindings"]["repair_shared_pointer"]
    dispatch = value["contracts"]["target_area_dispatch"]

    assert binding == {
        "skill_manager_object_offset": "+0x68",
        "skill_manager_control_offset": "+0x6c",
        "skill_id": REPAIR_SKILL_ID,
        "resolver_index": REPAIR_SKILL_INDEX,
        "stored_outside_weapon_vector": True,
    }
    assert dispatch["resolver_order"] == [
        "literal_50_repair",
        "in_range_vector",
        "null",
    ]
    assert resolve_enemy_skill_index(50, 0)["resolution"] == "repair"
    assert resolve_enemy_skill_index(50, 51)["resolution"] == "repair"
    assert resolve_enemy_skill_index(1, 2)["resolution"] == "vector"
    assert resolve_enemy_skill_index(-1, 2)["resolution"] == "null"
    assert resolve_enemy_skill_index(2, 2)["resolution"] == "null"


def test_active_source_census_separates_block_comments_from_shipped_assignments():
    source = _load()["source_inventory"]

    assert source["verified_lua_file_count"] == 152
    assert source["raw_non_line_comment_literal_match_count"] == 206
    assert source["block_commented_literal_match_count"] == 8
    assert source["active_literal_skill_list_assignment_count"] == 198
    assert source["active_arity_distribution"] == {"0": 26, "1": 161, "2": 11}
    assert source["maximum_literal_arity"] == 2
    assert len(source["maximum_occurrences"]) == 11
    assert {
        (entry["path"], entry["line"])
        for entry in source["block_commented_matches"]
    } == {
        ("scripts/advanced/ae_pawns.lua", 316),
        ("scripts/advanced/ae_pawns.lua", 333),
        ("scripts/advanced/ae_pawns.lua", 351),
        ("scripts/advanced/ae_pawns.lua", 595),
        ("scripts/advanced/ae_pawns.lua", 614),
        ("scripts/weapons_deploy.lua", 452),
        ("scripts/weapons_deploy.lua", 456),
        ("scripts/weapons_deploy.lua", 460),
    }
    assert source["scope_note"].endswith(
        "native equipment, save overlays, or mods."
    )


def test_usable_skill_scan_exact_ids_and_limited_use_boundary():
    result = replay_usable_skill_scan(
        [
            _skill("Move"),
            _skill("Move_Power"),
            _skill("BossHeal", limited=1, remaining=0),
            _skill("FireflyAtk1"),
            _skill("BossHeal", limited=2, remaining=1),
        ]
    )

    assert result["usable_indices"] == [3, 4]
    assert result["has_usable_skill"] is True
    assert [entry["reason"] for entry in result["entries"]] == [
        "excluded_move",
        "excluded_move_power",
        "limited_exhausted",
        "unlimited",
        "limited_with_remaining_use",
    ]


@pytest.mark.parametrize(
    ("overrides", "blocked_by"),
    [
        ({"active": False}, "active"),
        ({"smoke_on_tile": True}, "smoke"),
        ({"terrain_is_water": True}, "water"),
        ({"bonus_shift": 1}, "bonus_shift"),
        ({"skills": [_skill("Move")]}, "usable_skill"),
    ],
)
def test_each_ordinary_gate_failure_blocks_dispatch(overrides, blocked_by):
    result = _gate(**overrides)

    assert result["analysis_kind"] == TARGET_AREA_GATE_REPLAY_KIND
    assert result["ordinary_eligible"] is False, blocked_by
    assert result["mode_override"] is False
    assert result["target_area_wrapper_invoked"] is False
    assert result["selected_weapon_normalization"] is None
    assert result["skill_resolution"] is None
    assert result["lua_get_target_area_invoked"] is False


def test_smoke_immunities_and_busy_state_bypass_smoke_disable():
    ignore = _gate(smoke_on_tile=True, ignore_smoke=True)
    immunity = _gate(smoke_on_tile=True, disable_immunity=True)
    busy = _gate(smoke_on_tile=True, busy=True)

    assert ignore["smoke"]["attack_disabled"] is False
    assert immunity["smoke"]["attack_disabled"] is False
    assert busy["smoke"]["smoke_present_for_gate"] is False
    assert all(
        result["target_area_wrapper_invoked"]
        for result in (ignore, immunity, busy)
    )


def test_water_blocks_only_attached_not_busy_nonflying_pawn():
    grounded = _gate(terrain_is_water=True)
    flying = _gate(terrain_is_water=True, flying=True)
    busy = _gate(terrain_is_water=True, busy=True)
    detached = _gate(terrain_is_water=True, board_attached=False)

    assert grounded["water"]["grounded_nonflying_in_water"] is True
    assert grounded["target_area_wrapper_invoked"] is False
    for result in (flying, busy, detached):
        assert result["water"]["grounded_nonflying_in_water"] is False
        assert result["target_area_wrapper_invoked"] is True


def test_is_mech_is_only_fallback_for_missing_usable_skill():
    skills = [_skill("Move"), _skill("BossHeal", limited=1, remaining=0)]
    ordinary = _gate(skills=skills, selected_weapon=-1)
    mech = _gate(skills=skills, selected_weapon=-1, is_mech=True)

    assert ordinary["ordinary_eligible"] is False
    assert mech["ordinary_eligible"] is True
    assert mech["target_area_wrapper_invoked"] is True
    assert mech["skill_resolution"]["resolution"] == "null"
    assert mech["lua_get_target_area_invoked"] is False


def test_debugai_mode_bypasses_gate_but_not_resolver_validity():
    result = _gate(
        candidate_mode=1,
        board_attached=False,
        active=False,
        smoke_on_tile=True,
        terrain_is_water=True,
        bonus_shift=5,
        skills=[],
        selected_weapon=-1,
    )

    assert result["ordinary_eligible"] is False
    assert result["mode_override"] is True
    assert result["target_area_wrapper_invoked"] is True
    assert result["skill_resolution"]["resolution"] == "null"
    assert result["lua_get_target_area_invoked"] is False


def test_candidate_normalization_makes_repair_unreachable_for_small_vector():
    result = _gate(
        skills=[_skill("FireflyAtk1"), _skill("BossHeal")],
        selected_weapon=50,
    )

    normalization = result["selected_weapon_normalization"]
    assert normalization == {
        "original_weapon_index": 50,
        "weapon_count": 2,
        "normalized_weapon_index": 0,
        "changed": True,
    }
    assert result["skill_resolution"]["resolution"] == "vector"
    assert result["skill_resolution"]["skill_id"] == "FireflyAtk1"


def test_input_schema_and_integer_domains_fail_closed():
    with pytest.raises(EnemyTargetAreaBoundaryError, match="fields differ"):
        replay_usable_skill_scan([{"id": "FireflyAtk1", "limited": 0}])
    with pytest.raises(EnemyTargetAreaBoundaryError, match="nonempty string"):
        replay_usable_skill_scan([_skill("")])
    with pytest.raises(EnemyTargetAreaBoundaryError, match="candidate_mode"):
        _gate(candidate_mode=2)
    with pytest.raises(EnemyTargetAreaBoundaryError, match="must be a boolean"):
        _gate(active=1)
    with pytest.raises(EnemyTargetAreaBoundaryError, match="signed 32-bit"):
        resolve_enemy_skill_index(1 << 40, 2)


def test_binding_rejects_semantic_source_and_replay_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["field_bindings"]["bonus_shift"]["pawn_offset"] = "+0xa68"
    with pytest.raises(EnemyTargetAreaBoundaryError, match="fields differ"):
        validate_enemy_target_area_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["source_inventory"]["active_literal_skill_list_assignment_count"] = 206
    with pytest.raises(EnemyTargetAreaBoundaryError, match="fields differ"):
        validate_enemy_target_area_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["control_windows"][0]["instruction_hex"] += "90"
    with pytest.raises(EnemyTargetAreaBoundaryError, match="fields differ"):
        validate_enemy_target_area_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["replay_vectors"][0]["expected"]["has_usable_skill"] = True
    with pytest.raises(EnemyTargetAreaBoundaryError, match="fields differ"):
        validate_enemy_target_area_boundary_map_binding(altered)


def test_encoding_is_deterministic_and_round_trips():
    value = _load()
    encoded = encode_enemy_target_area_boundary_map(value)

    assert encoded.endswith("\n")
    assert json.loads(encoded) == value
    assert encoded == encode_enemy_target_area_boundary_map(value)


def test_exact_local_executable_and_sources_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")

    result = validate_enemy_target_area_boundary_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["ordinary_target_area_gate_complete"] is True
    assert result["repair_sentinel_resolved"] is True
    assert result["lua_target_area_output_complete"] is False
    assert result["simulator_change_required"] is False
