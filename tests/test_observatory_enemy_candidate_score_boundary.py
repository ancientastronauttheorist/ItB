from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.enemy_candidate_score_boundary import (
    ANALYSIS_KIND,
    DEBUGAI_CANDIDATE_MODE,
    EXPECTED_EXECUTABLE_SHA256,
    NORMAL_CANDIDATE_MODE,
    PRIORITY_TARGET_MODIFIER,
    SIGNED_MAX,
    TARGET_HISTORY_MODIFIER,
    EnemyCandidateScoreBoundaryError,
    encode_enemy_candidate_score_boundary_map,
    normalize_enemy_selected_weapon,
    replay_enemy_candidate_target_score,
    replay_enemy_positioning_clamp,
    replay_enemy_target_score_wrapper,
    validate_enemy_candidate_score_boundary_map,
    validate_enemy_candidate_score_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_enemy_candidate_score_boundary.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(BOUNDARY_MAP.read_text(encoding="utf-8"))


def _target_score(**overrides):
    values = {
        "weapon_index": 0,
        "weapon_count": 2,
        "callback_score": 7,
        "target": (3, 3),
        "target_history": (1, 1),
        "priority_target": (6, 6),
    }
    values.update(overrides)
    return replay_enemy_target_score_wrapper(**values)


def test_committed_map_binds_named_native_score_adjustments_without_overclaim():
    value = _load()
    result = validate_enemy_candidate_score_boundary_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "c0eeed00ebb646371d3ca33cac9d1c522"
            "24bb67025d1b6e6fa41a74115a7a457"
        ),
        "native_pre_post_adjustments_complete": True,
        "complete_candidate_materialization": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "dependency_count": 3,
        "region_count": 16,
        "control_window_count": 16,
        "direct_edge_count": 8,
        "data_anchor_count": 15,
        "method_binding_count": 2,
        "replay_vector_count": 14,
        "finding_count": 6,
        "unresolved_count": 5,
        "native_pre_post_adjustments_complete": True,
        "complete_candidate_materialization": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def test_field_names_and_offsets_are_exact_not_speculative_aliases():
    fields = _load()["contracts"]["field_bindings"]
    assert fields["current_health"] == {
        "pawn_offset": "+0x8a8",
        "component_offset": "+0x04",
        "native_name": "health",
        "setter": "SetHealth",
    }
    assert fields["max_health"] == {
        "pawn_offset": "+0x8ac",
        "component_offset": "+0x08",
        "native_name": "max_health",
    }
    assert fields["injured"] == {
        "pawn_offset": "+0x8d6",
        "component_offset": "+0x32",
        "native_state_name": "bInjured",
        "native_event_name": "injured",
    }
    assert fields["selected_weapon"] == {
        "pawn_offset": "+0x948",
        "archive_name": "iCurrentWeapon",
        "load_field": "Weapon",
        "lua_getter": "GetSelectedWeapon",
    }
    assert fields["target_history"]["archive_name"] == "targetHistory"
    assert fields["target_history"]["modifier"] == TARGET_HISTORY_MODIFIER
    assert fields["priority_target"]["archive_name"] == "priorityTarget"
    assert fields["priority_target"]["modifier"] == PRIORITY_TARGET_MODIFIER
    assert fields["priority_target"]["overrides_target_history"] is True


def test_normal_and_debug_routes_are_kept_distinct():
    contract = _load()["contracts"]["positioning_clamp"]
    assert contract["normal_route_mode"] == NORMAL_CANDIDATE_MODE == 0
    assert contract["debugai_route_mode"] == DEBUGAI_CANDIDATE_MODE == 1
    assert contract["normal_route_nonnegative_replacement"] == 0
    assert contract["debugai_route_nonnegative_replacement"] == 1

    windows = {item["id"]: item for item in _load()["control_windows"]}
    assert windows["normal_mode_zero"]["region_id"] == "normal_orchestrator"
    assert windows["debugai_mode_one"]["region_id"] == "debugai_route"


@pytest.mark.parametrize(
    (
        "raw_score",
        "injured",
        "moved",
        "health",
        "mode",
        "applied",
        "expected",
    ),
    [
        (7, True, True, 1, 0, True, 0),
        (0, True, True, 1, 0, True, 0),
        (-1, True, True, 1, 0, False, -1),
        (7, True, True, 1, 1, True, 1),
        (7, False, True, 1, 0, False, 7),
        (7, True, False, 1, 0, False, 7),
        (7, True, True, 2, 0, False, 7),
        (7, True, True, 0, 0, False, 7),
    ],
)
def test_positioning_clamp_truth_table(
    raw_score,
    injured,
    moved,
    health,
    mode,
    applied,
    expected,
):
    result = replay_enemy_positioning_clamp(
        raw_score,
        injured=injured,
        moved=moved,
        current_health=health,
        mode=mode,
    )
    assert result["clamp_applied"] is applied
    assert result["final_score"] == expected
    assert result["mode_forces_target_area_evaluation"] is (mode == 1)


def test_positioning_replay_rejects_unproven_modes_and_python_bool_as_integer():
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="mode must be"):
        replay_enemy_positioning_clamp(
            1,
            injured=True,
            moved=True,
            current_health=1,
            mode=2,
        )
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="raw_score"):
        replay_enemy_positioning_clamp(
            True,
            injured=True,
            moved=True,
            current_health=1,
        )
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="injured"):
        replay_enemy_positioning_clamp(
            1,
            injured=1,
            moved=True,
            current_health=1,
        )


@pytest.mark.parametrize(
    ("weapon_index", "weapon_count", "expected", "changed"),
    [
        (-2, 2, -2, False),
        (-1, 2, -1, False),
        (0, 0, 0, False),
        (0, 2, 0, False),
        (1, 2, 1, False),
        (2, 2, 0, True),
        (50, 2, 0, True),
    ],
)
def test_candidate_selected_weapon_normalization(
    weapon_index,
    weapon_count,
    expected,
    changed,
):
    result = normalize_enemy_selected_weapon(weapon_index, weapon_count)
    assert result["normalized_weapon_index"] == expected
    assert result["changed"] is changed


def test_target_history_penalty_and_positive_floor_boundaries():
    for callback_score in range(1, 6):
        result = _target_score(callback_score=callback_score, target=(1, 1))
        assert result["native_modifier"] == -5
        assert result["positive_floor_applied"] is True
        assert result["final_score"] == 1

    result = _target_score(callback_score=6, target=(1, 1))
    assert result["positive_floor_applied"] is False
    assert result["final_score"] == 1

    result = _target_score(callback_score=0, target=(1, 1))
    assert result["positive_floor_applied"] is False
    assert result["final_score"] == -5


def test_priority_bonus_overrides_history_when_both_points_match():
    result = _target_score(
        callback_score=2,
        target=(4, 4),
        target_history=(4, 4),
        priority_target=(4, 4),
    )
    assert result["target_history_match"] is True
    assert result["priority_target_match"] is True
    assert result["priority_overrode_history"] is True
    assert result["native_modifier"] == 10
    assert result["final_score"] == 12


def test_invalid_weapon_skips_callback_and_returns_modifier_only():
    result = _target_score(
        weapon_index=-1,
        callback_score=None,
        target=(1, 1),
    )
    assert result["callback_invoked"] is False
    assert result["native_modifier"] == -5
    assert result["final_score"] == -5

    result = _target_score(
        weapon_index=3,
        callback_score=None,
        target=(6, 6),
    )
    assert result["callback_invoked"] is False
    assert result["native_modifier"] == 10
    assert result["final_score"] == 10


def test_wrapper_literal_50_exception_is_separate_from_candidate_normalization():
    wrapper = _target_score(
        weapon_index=50,
        callback_score=4,
        target=(1, 1),
    )
    assert wrapper["weapon_index"] == 50
    assert wrapper["callback_invoked"] is True
    assert wrapper["positive_floor_applied"] is True
    assert wrapper["final_score"] == 1

    candidate = replay_enemy_candidate_target_score(
        weapon_index=50,
        weapon_count=2,
        callback_score=4,
        target=(3, 3),
        target_history=(1, 1),
        priority_target=(6, 6),
    )
    assert candidate["candidate_weapon_normalization"] == {
        "original_weapon_index": 50,
        "weapon_count": 2,
        "normalized_weapon_index": 0,
        "changed": True,
    }
    assert candidate["weapon_index"] == 0
    assert candidate["callback_invoked"] is True
    assert candidate["final_score"] == 4


def test_callback_presence_must_match_native_resolver_branch():
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="required"):
        _target_score(callback_score=None)
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="must be null"):
        _target_score(weapon_index=-1, callback_score=7)


def test_target_score_uses_native_signed_32_bit_addition():
    result = _target_score(callback_score=SIGNED_MAX, target=(6, 6))
    assert result["native_modifier"] == 10
    assert result["final_score"] == -2147483639


def test_target_score_rejects_bad_points_counts_and_integer_types():
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="exactly two"):
        _target_score(target=(1, 2, 3))
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="weapon_count"):
        _target_score(weapon_count=-1)
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="weapon_index"):
        _target_score(weapon_index=True)
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="callback_score"):
        _target_score(callback_score=SIGNED_MAX + 1)


def test_committed_replay_vectors_recompute_from_public_helpers():
    value = _load()
    for vector in value["replay_vectors"]:
        payload = vector["input"]
        if vector["kind"] == "positioning_clamp":
            result = replay_enemy_positioning_clamp(
                payload["raw_score"],
                injured=payload["injured"],
                moved=payload["moved"],
                current_health=payload["current_health"],
                mode=payload["mode"],
            )
            assert result["clamp_applied"] == vector["expected"]["clamp_applied"]
            assert result["final_score"] == vector["expected"]["final_score"]
            assert result["route"] == vector["expected"]["route"]
            continue

        replay = (
            replay_enemy_candidate_target_score
            if vector["kind"] == "candidate_target_score"
            else replay_enemy_target_score_wrapper
        )
        result = replay(**payload)
        for key, expected in vector["expected"].items():
            assert result[key] == expected


def test_binding_rejects_native_claim_or_replay_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["field_bindings"]["injured"]["pawn_offset"] = "+0x8d5"
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="fields differ"):
        validate_enemy_candidate_score_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["replay_boundary"]["complete_candidate_materialization"] = True
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="fields differ"):
        validate_enemy_candidate_score_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["control_windows"][2]["instruction_hex"] += "90"
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="fields differ"):
        validate_enemy_candidate_score_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["replay_vectors"][0]["expected"]["final_score"] = 7
    with pytest.raises(EnemyCandidateScoreBoundaryError, match="fields differ"):
        validate_enemy_candidate_score_boundary_map_binding(altered)


def test_encoding_is_deterministic_and_round_trips():
    value = _load()
    encoded = encode_enemy_candidate_score_boundary_map(value)
    assert encoded.endswith("\n")
    assert json.loads(encoded) == value
    assert encoded == encode_enemy_candidate_score_boundary_map(value)


def test_exact_local_executable_reproduces_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_enemy_candidate_score_boundary_map(executable, _load())
    assert result["status"] == "verified"
    assert result["native_pre_post_adjustments_complete"] is True
    assert result["complete_candidate_materialization"] is False
    assert result["simulator_change_required"] is False
