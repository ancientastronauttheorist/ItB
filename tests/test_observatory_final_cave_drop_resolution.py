from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.final_cave_drop_resolution import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    FinalCaveDropResolutionError,
    validate_final_cave_drop_resolution_map,
    validate_final_cave_drop_resolution_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
RESOLUTION_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_final_cave_drop_resolution.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(RESOLUTION_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_ordinary_drop_resolution_without_rng_overclaim():
    value = _load()
    result = validate_final_cave_drop_resolution_map_binding(value)

    assert result["schema_version"] == 1
    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["status"] == "bound"
    assert result["artifact_sha256"] == (
        "6a3ac4e52834d7c43c7152f06b7763a9"
        "ec49245dbad86be5883213c47ea2a498"
    )
    assert result["ordinary_pylon_two_hp_proven"] is True
    assert result["pre_start_pylon_occupancy_excluded"] is True
    assert result["terrain_before_spawn_proven"] is True
    assert result["occupied_sPawn_collision_order_proven"] is True
    assert result["optional_startup_enemy_replacement_proven"] is True
    assert result["simulator_change_required"] is False
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "lua_source_count": 1,
        "dependency_count": 7,
        "runtime_corroboration_count": 3,
        "region_count": 26,
        "data_anchor_count": 9,
        "field_binding_count": 3,
        "method_binding_count": 4,
        "control_window_count": 19,
        "direct_edge_count": 17,
        "finding_count": 8,
        "unresolved_count": 6,
        "ordinary_pylon_two_hp_proven": True,
        "pre_start_pylon_occupancy_excluded": True,
        "terrain_before_spawn_proven": True,
        "occupied_sPawn_collision_order_proven": True,
        "optional_startup_enemy_replacement_proven": True,
        "simulator_change_required": False,
    }

    assert value["contracts"]["ordinary_pylons"] == {
        "pylons_per_map": 7,
        "dropper_records_per_pylon": 2,
        "construction_tile_unoccupied": True,
        "source_i_damage": 0,
        "first_impact_current_hp": 1,
        "first_impact_max_hp": 1,
        "second_impact_current_hp": 2,
        "second_impact_max_hp": 2,
        "later_startup_enemy_admission_rejected_by_permanent_block": True,
        "retained_capture_count": 3,
    }
    assert value["contracts"]["pre_start_occupancy"] == {
        "exact_map_spawn_lists_empty": True,
        "surface_transition_boardplayer_state": 5,
        "carried_pawn_logical_coordinates_before_base_start": [-1, -1],
        "carried_pawn_readd_returns_before_base_start": True,
        "state_five_skips_native_auto_deploy_tail": True,
        "only_source_reachable_pre_pylon_spawn": "optional enemy at bomb_loc",
        "bomb_loc_is_deployment_tile": True,
        "deployment_and_pylon_zones_disjoint_on_all_maps": True,
        "deployment_and_mountain_zones_disjoint_on_all_maps": True,
        "ordinary_pylon_is_pawn_space_at_construction": False,
    }
    assert {item["id"] for item in value["dependencies"]} == {
        "final_end_settlement",
        "final_cave_startup",
        "final_cave_startup_spawn_order",
        "final_cave_startup_effect_order",
        "final_cave_replacement",
        "final_cave_replacement_cadence",
        "final_cave_block_spawn_lifetime",
    }
    assert value["supersedes"]["artifact"].endswith(
        "final_cave_startup_effect_order.json"
    )
    assert value["refines"] == {
        "artifact": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_final_cave_replacement.json"
        ),
        "finding": "bigbomb_drop_resolution_path_is_exact",
        "qualification": (
            "The dispatch-to-AddPawn route is exact, but factory construction "
            "and AddPawn occur only when the post-occupant blocker recheck "
            "accepts the selected point."
        ),
    }
    assert "carried_pawns_are_offboard_before_startmission" in {
        item["id"] for item in value["findings"]
    }
    collision = value["contracts"]["sPawn_collision"]
    assert collision["occupied_tile_action"] == (
        "Pawn:Kill(false) for every tile occupant"
    )
    assert collision["blocker_recheck_after_removal"] is True
    assert value["contracts"]["final_cave_bomb"][
        "optional_enemy_is_replaced_when_branch_taken"
    ] is True
    assert value["contracts"]["final_cave_bomb"][
        "startup_bomb_point_not_spawn_blocked"
    ] is True
    assert value["contracts"]["final_cave_bomb"][
        "selected_enemy_killed_before_blocker_recheck"
    ] is True
    assert value["contracts"]["final_cave_bomb"][
        "bigbomb_materializes_only_if_blocker_recheck_passes"
    ] is True
    assert value["contracts"]["final_cave_bomb"][
        "destroyed_pylon_permanent_block_can_abort_after_enemy_kill"
    ] is True
    assert {
        item["matched_map_source"] for item in value["runtime_corroboration"]
    } == {"maps/cave2.map", "maps/caveAE2.map", "maps/caveAE4.map"}
    assert all(
        item["pylon_hp_values"] == [2, 2, 2, 2, 2, 2, 2]
        for item in value["runtime_corroboration"]
    )
    assert {item["id"] for item in value["unresolved"]} == {
        "death_damage_callbacks_and_attribution",
        "adversarial_modified_collisions",
        "concrete_replacement_point_and_block_state",
        "startup_visual_impact_interleave",
        "concrete_startup_rng_coordinates_and_uids",
        "non_windows_equivalence",
    }


def test_binding_rejects_layout_collision_or_prose_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["field_bindings"][1]["record_offset"] = "+0xa8"
    with pytest.raises(FinalCaveDropResolutionError, match="fields differ"):
        validate_final_cave_drop_resolution_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["ordinary_pylons"]["second_impact_current_hp"] = 1
    with pytest.raises(FinalCaveDropResolutionError, match="fields differ"):
        validate_final_cave_drop_resolution_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["sPawn_collision"]["blocker_recheck_after_removal"] = False
    with pytest.raises(FinalCaveDropResolutionError, match="fields differ"):
        validate_final_cave_drop_resolution_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["method_bindings"][3]["target_rva"] = "0x0023d2e1"
    with pytest.raises(FinalCaveDropResolutionError, match="fields differ"):
        validate_final_cave_drop_resolution_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][4]["claim"] += " overclaim"
    with pytest.raises(FinalCaveDropResolutionError, match="fields differ"):
        validate_final_cave_drop_resolution_map_binding(altered)


def test_exact_local_executable_source_dependencies_and_captures_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_final_cave_drop_resolution_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["ordinary_pylon_two_hp_proven"] is True
    assert result["pre_start_pylon_occupancy_excluded"] is True
    assert result["terrain_before_spawn_proven"] is True
    assert result["occupied_sPawn_collision_order_proven"] is True
    assert result["optional_startup_enemy_replacement_proven"] is True
