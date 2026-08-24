from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.death_event_credit_boundary import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    DeathEventCreditBoundaryError,
    validate_death_event_credit_boundary_map,
    validate_death_event_credit_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
CREDIT_MAP = ROOT / "data" / "observatory" / "native" / (
    "windows_build_13725832_31fe35265598_death_event_credit_boundary.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(CREDIT_MAP.read_text(encoding="utf-8"))


def test_committed_map_proves_environment_mission_credit_split_without_overclaim():
    value = _load()
    result = validate_death_event_credit_boundary_map_binding(value)

    assert result == {
        "analysis_kind": ANALYSIS_KIND,
        "artifact_sha256": (
            "780d1000112a4d801dd9df342a6aac57"
            "20dcb5d4fdc482c028416f7d9f18bbc7"
        ),
        "environment_mech_credit_bypass_proven": True,
        "environment_owner_pipeline_proven": True,
        "exact_event_frame_visibility_proven": False,
        "mission_enemy_killed_event_proven": True,
        "schema_version": 1,
        "shipped_lua_onkill_callback_proven": False,
        "simulator_change_required": False,
        "status": "bound",
    }
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "absolute_reference_anchor_count": 13,
        "absolute_reference_count": 27,
        "control_window_count": 37,
        "data_anchor_count": 1,
        "dependency_count": 1,
        "direct_edge_count": 15,
        "environment_mech_credit_bypass_proven": True,
        "environment_owner_pipeline_proven": True,
        "exact_event_frame_visibility_proven": False,
        "finding_count": 11,
        "mission_enemy_killed_event_proven": True,
        "region_count": 24,
        "shipped_lua_onkill_callback_proven": False,
        "simulator_change_required": False,
        "source_count": 6,
        "unresolved_count": 6,
    }

    owner = value["contracts"]["owner_pipeline"]
    assert owner["skill_effect_iowner_offset"] == "+0x5c"
    assert owner["skill_effect_size_bytes"] == 0x7C
    assert owner["current_owner_address"] == "0x008bd254"
    assert owner["environment_owner_value"] == -10
    assert owner["environment_owner_pipeline_proven"] is True

    event = value["contracts"]["mission_event"]
    assert event["event_enemy_killed_value"] == 2
    assert event["nonminor_enemy_event"] == 2
    assert event["minor_enemy_event"] == 12
    assert event["mission_base_update_consumes_event_enemy_killed"] is True
    assert event["exact_same_or_next_update_visibility_proven"] is False

    credit = value["contracts"]["credit"]
    assert credit["mech_owner_inclusive_range"] == [0, 2]
    assert credit["mech_owner_xp_bucket"] == "xp_<owner>"
    assert credit["mech_owner_kill_bucket"] == "kill_<owner>"
    assert credit["nonmech_owner_xp_bucket"] == "env_xp"
    assert credit["environment_generates_mech_xp_or_kill_bucket"] is False
    assert credit["i_kills_offset"] == "+0x098c"
    assert credit["i_kill_count_offset"] == "+0x0a60"
    assert credit["i_mission_damage_offset"] == "+0x1170"
    assert credit["i_mission_damage_is_health_delta_not_death_credit"] is True

    onkill = value["contracts"]["onkill"]
    assert onkill == {
        "all_nonempty_values_are_localization_keys": True,
        "matching_lua_function_definition_count": 0,
        "mechanics_implemented_in_get_skill_effect": True,
        "native_only_offset_consumers_exhausted": False,
        "shipped_lua_callback_field_proven": False,
        "shipped_lua_occurrence_count": 7,
        "shipped_nonempty_value_count": 6,
    }
    assert {item["id"] for item in value["unresolved"]} == {
        "native_only_onkill_offset_consumers",
        "exact_event_frame_visibility",
        "achievement_counter_tail",
        "specialized_enemy_death_classes",
        "environment_any_kill_bucket_consumers",
        "non_windows_equivalence",
    }


def test_binding_rejects_owner_event_credit_or_scope_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["owner_pipeline"]["environment_owner_value"] = -9
    with pytest.raises(DeathEventCreditBoundaryError, match="fields differ"):
        validate_death_event_credit_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["mission_event"]["minor_enemy_event"] = 2
    with pytest.raises(DeathEventCreditBoundaryError, match="fields differ"):
        validate_death_event_credit_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["credit"][
        "environment_generates_mech_xp_or_kill_bucket"
    ] = True
    with pytest.raises(DeathEventCreditBoundaryError, match="fields differ"):
        validate_death_event_credit_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["onkill"]["shipped_lua_callback_field_proven"] = True
    with pytest.raises(DeathEventCreditBoundaryError, match="fields differ"):
        validate_death_event_credit_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["solver_impact"]["simulator_change_required"] = True
    with pytest.raises(DeathEventCreditBoundaryError, match="fields differ"):
        validate_death_event_credit_boundary_map_binding(altered)


def test_exact_local_executable_sources_and_dependency_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_death_event_credit_boundary_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["environment_owner_pipeline_proven"] is True
    assert result["mission_enemy_killed_event_proven"] is True
    assert result["environment_mech_credit_bypass_proven"] is True
    assert result["shipped_lua_onkill_callback_proven"] is False
    assert result["exact_event_frame_visibility_proven"] is False
    assert result["simulator_change_required"] is False
