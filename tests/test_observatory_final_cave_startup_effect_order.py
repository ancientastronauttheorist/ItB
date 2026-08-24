from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.final_cave_startup_effect_order import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    FinalCaveStartupEffectOrderError,
    validate_final_cave_startup_effect_order_map,
    validate_final_cave_startup_effect_order_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
EFFECT_ORDER_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / (
        "windows_build_13725832_31fe35265598_"
        "final_cave_startup_effect_order.json"
    )
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(EFFECT_ORDER_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_startup_effect_order_without_visual_overclaim():
    value = _load()
    result = validate_final_cave_startup_effect_order_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "a5290868718a0912c50c1caf914f7a62"
            "03d781d7a4b137352c9caf61c2c031df"
        ),
        "release_branch_proven": True,
        "record_order_proven": True,
        "script_evaluation_order_proven": True,
        "duplicated_pylon_records_proven": True,
        "visual_impact_order_proven": False,
        "wall_clock_duration_proven": False,
        "simulator_change_required": False,
    }
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "lua_source_count": 1,
        "dependency_count": 4,
        "region_count": 20,
        "data_anchor_count": 6,
        "registration_binding_count": 6,
        "vtable_binding_count": 1,
        "control_window_count": 9,
        "direct_edge_count": 15,
        "import_edge_count": 2,
        "finding_count": 7,
        "unresolved_count": 5,
        "release_branch_proven": True,
        "record_order_proven": True,
        "script_evaluation_order_proven": True,
        "duplicated_pylon_records_proven": True,
        "visual_impact_order_proven": False,
        "wall_clock_duration_proven": False,
        "simulator_change_required": False,
    }

    schedule = value["contracts"]["release_schedule"]
    assert schedule["is_release_result"] is True
    assert schedule["fast_version"] is False
    assert schedule["mountain_counts"] == [3, 4]
    assert schedule["pylon_count"] == 7
    assert schedule["record_counts_by_mountain_count"] == {"3": 44, "4": 46}
    assert schedule["record_type_counts_by_mountain_count"] == {
        "3": {
            "delay": 19,
            "board_shake": 1,
            "dropper": 18,
            "script": 3,
            "voice": 3,
        },
        "4": {
            "delay": 20,
            "board_shake": 1,
            "dropper": 19,
            "script": 3,
            "voice": 3,
        },
    }
    assert value["contracts"]["script_record"]["valid_startup_attempt_order"] == [
        0,
        1,
        2,
    ]
    assert value["contracts"]["delay_record"] == {
        "flag_offset": "+0xc4",
        "duration_offset": "+0xc8",
        "suffix_begins_at_next_record": True,
        "dispatcher_this_effect_suffix_vector_offset": "+0x2c44",
        "dispatcher_this_duration_vector_offset": "+0x2c50",
        "primary_board_effect_suffix_vector_offset": "+0x2c50",
        "primary_board_duration_vector_offset": "+0x2c5c",
        "paired_continuation_insert_position": "current vector beginning",
        "preserves_remaining_record_order": True,
    }
    assert value["contracts"]["semantic_boundary"] == {
        "logical_enemy_admission_precedes_first_record_dispatch": True,
        "mountain_records_precede_mech_scripts": True,
        "mech_scripts_precede_pylon_records": True,
        "pylon_records_precede_bomb_record": True,
        "each_pylon_has_two_independent_consecutive_dropper_records": True,
        "visual_impact_order_proven": False,
        "wall_clock_duration_proven": False,
    }
    assert {item["id"] for item in value["unresolved"]} == {
        "concrete_startup_rng_outputs",
        "presentation_timing_and_overlap",
        "modified_state_errors_and_collisions",
        "spawn_block_lifetime",
        "non_windows_equivalence",
    }


def test_binding_rejects_native_source_schedule_or_prose_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["registration_bindings"][4]["wrapper_rva"] = "0x00256981"
    with pytest.raises(FinalCaveStartupEffectOrderError, match="fields differ"):
        validate_final_cave_startup_effect_order_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["release_schedule"]["record_counts_by_mountain_count"][
        "3"
    ] = 43
    with pytest.raises(FinalCaveStartupEffectOrderError, match="fields differ"):
        validate_final_cave_startup_effect_order_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["semantic_boundary"]["visual_impact_order_proven"] = True
    with pytest.raises(FinalCaveStartupEffectOrderError, match="fields differ"):
        validate_final_cave_startup_effect_order_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][5]["claim"] += " overclaim"
    with pytest.raises(FinalCaveStartupEffectOrderError, match="fields differ"):
        validate_final_cave_startup_effect_order_map_binding(altered)


def test_exact_local_executable_and_source_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_final_cave_startup_effect_order_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["release_branch_proven"] is True
    assert result["record_order_proven"] is True
    assert result["script_evaluation_order_proven"] is True
    assert result["duplicated_pylon_records_proven"] is True
    assert result["visual_impact_order_proven"] is False
    assert result["wall_clock_duration_proven"] is False
