from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.final_cave_block_spawn_lifetime import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    FinalCaveBlockSpawnLifetimeError,
    validate_final_cave_block_spawn_lifetime_map,
    validate_final_cave_block_spawn_lifetime_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
LIFETIME_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / (
        "windows_build_13725832_31fe35265598_"
        "final_cave_block_spawn_lifetime.json"
    )
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(LIFETIME_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_ordinary_spawn_block_lifetime_without_overclaim():
    value = _load()
    result = validate_final_cave_block_spawn_lifetime_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "69d63632fe6585ac02864e09e3106e79"
            "6e47abadd65991e41e1b76a1e2370889"
        ),
        "block_values_proven": True,
        "spawn_rejection_proven": True,
        "temporary_cleanup_boundary_proven": True,
        "permanent_player_turn_persistence_proven": True,
        "permanent_cross_board_persistence_proven": False,
        "simulator_change_required": False,
    }
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "lua_source_count": 1,
        "accepted_tree_lua_file_count": 153,
        "dependency_count": 3,
        "region_count": 11,
        "data_anchor_count": 11,
        "constant_binding_count": 3,
        "method_binding_count": 2,
        "control_window_count": 13,
        "direct_edge_count": 11,
        "direct_callsite_target_count": 3,
        "field_reference_function_count": 7,
        "finding_count": 7,
        "unresolved_count": 4,
        "block_values_proven": True,
        "spawn_rejection_proven": True,
        "temporary_cleanup_boundary_proven": True,
        "permanent_player_turn_persistence_proven": True,
        "permanent_cross_board_persistence_proven": False,
        "simulator_change_required": False,
    }

    assert value["contracts"]["registered_values"] == {
        "BLOCKED_NONE": 0,
        "BLOCKED_TEMP": 1,
        "BLOCKED_PERM": 2,
    }
    assert value["contracts"]["spawn_validity"] == {
        "rejects_blocked_temp": True,
        "rejects_blocked_perm": True,
        "checks_blocks_before_remaining_tile_rules": True,
    }
    assert value["contracts"]["phase_lifetime"] == {
        "phase_dispatch_table": {
            "phase_0_target_rva": "0x0018a48f",
            "phase_1_target_rva": "0x0018a770",
        },
        "stage_start_requested_phase": 1,
        "end_turn_sweep_mode": 6,
        "end_turn_clears_temporary": False,
        "player_turn_phase": 0,
        "player_turn_sweep_mode": 1,
        "player_turn_clears_temporary": True,
        "cleanup_precedes_player_turn_ui": True,
    }
    assert value["contracts"]["board_lifetime"] == {
        "board_reset_zeros_all_8x8_values": True,
        "permanent_survives_player_turn_cleanup": True,
        "permanent_survives_board_reset": False,
        "explicit_block_spawn_overwrite_still_possible": True,
    }
    assert value["contracts"]["final_cave_startup"] == {
        "mountain_value": 1,
        "pylon_value": 2,
        "both_affect_startup_enemy_selection": True,
        "mountain_temp_survives_stage_start_phase_one": True,
        "mountain_temp_clears_before_first_player_turn_ui": True,
        "pylon_perm_survives_player_turn_cleanup": True,
    }
    assert {item["id"] for item in value["unresolved"]} == {
        "runtime_block_map_observability",
        "explicit_or_modified_clear_calls",
        "presentation_collisions",
        "non_windows_equivalence",
    }
    assert value["identity"]["base_inventory_scripts_revision_sha256"] == (
        "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
    )
    inventory = next(
        item for item in value["dependencies"] if item["id"] == "base_scripts_inventory"
    )
    assert inventory["scripts_file_count"] == 305
    assert inventory["overlay_path"] == "scripts/modloader.lua"
    assert {item["sha256"] for item in inventory["accepted_overlay_files"]} == {
        "8d765cb4d501f1cdc83a6423ad7c2f66e01d98844ec3e8afd1f3c099e4763c10",
        "f94fabbe75aad2463e08ab28bf052e31db95b7724f31adbfc002aa102675f1a2",
    }


def test_binding_rejects_native_lifetime_contract_or_prose_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["constant_bindings"][1]["value"] = 2
    with pytest.raises(FinalCaveBlockSpawnLifetimeError, match="fields differ"):
        validate_final_cave_block_spawn_lifetime_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["phase_lifetime"]["end_turn_clears_temporary"] = True
    with pytest.raises(FinalCaveBlockSpawnLifetimeError, match="fields differ"):
        validate_final_cave_block_spawn_lifetime_map_binding(altered)

    altered = copy.deepcopy(value)
    jump_table = next(
        item
        for item in altered["data_anchors"]
        if item["id"] == "phase_dispatch_entries_zero_one"
    )
    jump_table["hex"] = "0000000000000000"
    with pytest.raises(FinalCaveBlockSpawnLifetimeError, match="fields differ"):
        validate_final_cave_block_spawn_lifetime_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["board_lifetime"]["permanent_survives_board_reset"] = True
    with pytest.raises(FinalCaveBlockSpawnLifetimeError, match="fields differ"):
        validate_final_cave_block_spawn_lifetime_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][4]["claim"] += " overclaim"
    with pytest.raises(FinalCaveBlockSpawnLifetimeError, match="fields differ"):
        validate_final_cave_block_spawn_lifetime_map_binding(altered)


def test_exact_local_executable_and_source_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_final_cave_block_spawn_lifetime_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["block_values_proven"] is True
    assert result["spawn_rejection_proven"] is True
    assert result["temporary_cleanup_boundary_proven"] is True
    assert result["permanent_player_turn_persistence_proven"] is True
    assert result["permanent_cross_board_persistence_proven"] is False
