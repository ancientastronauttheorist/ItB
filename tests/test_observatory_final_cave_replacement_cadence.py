from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.final_cave_replacement_cadence import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    FinalCaveReplacementCadenceError,
    validate_final_cave_replacement_cadence_map,
    validate_final_cave_replacement_cadence_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
CADENCE_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_final_cave_replacement_cadence.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(CADENCE_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_semantic_repeat_cadence_without_rng_overclaim():
    value = _load()
    result = validate_final_cave_replacement_cadence_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "578275064f6f55ca170128d954613d84"
            "6eb9398a239c2462de87356549ca7b4e"
        ),
        "active_registration_proven": True,
        "busy_until_impact_proven": True,
        "semantic_repeat_cadence_proven": True,
        "concrete_coordinate_proven": False,
        "concrete_uid_proven": False,
        "simulator_change_required": False,
    }
    assert value["identity"]["executable_sha256"] == (
        EXPECTED_EXECUTABLE_SHA256
    )
    assert value["summary"] == {
        "lua_source_count": 1,
        "region_count": 8,
        "data_anchor_count": 3,
        "vtable_pointer_count": 6,
        "control_window_count": 8,
        "direct_edge_count": 1,
        "finding_count": 4,
        "unresolved_count": 4,
        "active_registration_proven": True,
        "busy_until_impact_proven": True,
        "duplicate_before_impact_excluded": True,
        "semantic_repeat_cadence_proven": True,
        "wall_clock_duration_proven": False,
        "concrete_coordinate_proven": False,
        "concrete_uid_proven": False,
        "simulator_change_required": False,
    }

    layout = value["contracts"]["board_layout_alias"]
    assert layout == {
        "effect_dispatch_this": "primary Board+0x0c",
        "dispatcher_vector_begin": "this+0x2d14",
        "dispatcher_vector_end": "this+0x2d18",
        "primary_vector_begin": "Board+0x2d20",
        "primary_vector_end": "Board+0x2d24",
        "same_vector_proven": True,
    }

    initial = value["contracts"]["initial_fall"]
    assert initial["lua_pod_z"] == 300
    assert initial["lua_pod_velocity"] == 0.7
    assert initial["initial_fall_field_strictly_negative"] is True

    busy = value["contracts"]["busy_and_impact"]
    assert busy["board_activity_reason"] == 8
    assert busy["busy_while_fall_field_negative"] is True
    assert busy["impact_runs_on_nonnegative_crossing"] is True
    assert (
        busy["callback_can_observe_nonbusy_missing_bomb_before_impact"]
        is False
    )

    repeat = value["contracts"]["repeat_cadence"]
    assert repeat["turn_limit_increment_per_idle_missing_bomb_callback"] == 2
    assert repeat["replacement_effects_per_idle_missing_bomb_callback"] == 1
    assert repeat["duplicate_replacement_before_impact_possible"] is False
    assert repeat["semantic_repeat_cadence_proven"] is True
    assert repeat["wall_clock_duration_known"] is False

    unresolved = {item["id"] for item in value["unresolved"]}
    assert unresolved == {
        "replacement_coordinate_and_draw_count",
        "replacement_uid_allocation",
        "replacement_wall_clock_duration",
        "non_windows_equivalence",
    }


def test_binding_rejects_vtable_source_or_prose_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["vtable_pointers"][0]["target_rva"] = "0x00000000"
    with pytest.raises(FinalCaveReplacementCadenceError, match="fields differ"):
        validate_final_cave_replacement_cadence_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["sources"]["lua_files"][0]["semantic_values"]["pod_z"] = 299
    with pytest.raises(FinalCaveReplacementCadenceError, match="fields differ"):
        validate_final_cave_replacement_cadence_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][1]["claim"] += " overclaim"
    with pytest.raises(FinalCaveReplacementCadenceError, match="fields differ"):
        validate_final_cave_replacement_cadence_map_binding(altered)


def test_exact_local_executable_and_source_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_final_cave_replacement_cadence_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["active_registration_proven"] is True
    assert result["busy_until_impact_proven"] is True
    assert result["semantic_repeat_cadence_proven"] is True
    assert result["concrete_coordinate_proven"] is False
    assert result["concrete_uid_proven"] is False
    assert result["simulator_change_required"] is False
