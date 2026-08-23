from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.final_cave_startup_spawn_order import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    FinalCaveStartupSpawnOrderError,
    validate_final_cave_startup_spawn_order_map,
    validate_final_cave_startup_spawn_order_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
SPAWN_ORDER_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / (
        "windows_build_13725832_31fe35265598_"
        "final_cave_startup_spawn_order.json"
    )
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(SPAWN_ORDER_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_logical_startup_spawn_order_without_rng_overclaim():
    value = _load()
    result = validate_final_cave_startup_spawn_order_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "b798a97c582be31ffba3d173e00b24ee"
            "fae32a9725d03fe7a2260ca1403214f4"
        ),
        "spawn_overloads_bound": True,
        "implicit_selector_and_space_commit_proven": True,
        "logical_admission_before_effect_dispatch_proven": True,
        "visual_animation_interleave_proven": False,
        "concrete_rng_outputs_proven": False,
        "simulator_change_required": False,
    }
    assert value["identity"]["executable_sha256"] == (
        EXPECTED_EXECUTABLE_SHA256
    )
    assert value["summary"] == {
        "lua_source_count": 2,
        "dependency_count": 4,
        "region_count": 12,
        "data_anchor_count": 2,
        "control_window_count": 9,
        "direct_edge_count": 11,
        "finding_count": 6,
        "unresolved_count": 5,
        "spawn_overloads_bound": True,
        "implicit_selector_and_space_commit_proven": True,
        "synchronous_spawn_block_write_proven": True,
        "logical_admission_before_effect_dispatch_proven": True,
        "visual_animation_interleave_proven": False,
        "concrete_rng_outputs_proven": False,
        "simulator_change_required": False,
    }

    contracts = value["contracts"]
    assert contracts["spawn_overloads"] == {
        "lua_name": "SpawnPawn",
        "implicit_wrapper_rva": "0x00169150",
        "implicit_point": [-1, -1],
        "explicit_wrapper_rva": "0x001690c0",
        "explicit_point_preserved": True,
        "both_reach_central_spawn_pawn": True,
    }
    assert contracts["logical_admission"][
        "invalid_point_calls_standard_selector"
    ] is True
    assert contracts["logical_admission"]["commit_is_synchronous"] is True
    assert contracts["spawn_blocking"]["write_is_synchronous"] is True
    assert contracts["scheduler_order"] == {
        "board_master_update_call_rva": "0x0018b0e1",
        "phase_transition_call_rva": "0x0018b169",
        "board_update_precedes_phase_transition": True,
        "second_board_update_after_transition_same_pass": False,
        "startup_effect_dispatch_same_orchestrator_pass": False,
    }
    assert contracts["semantic_boundary"] == {
        "boss_and_ordinary_logical_admission_before_startup_effect_dispatch": True,
        "queued_mech_scripts_execute_before_enemy_admission": False,
        "queued_rock_pylon_bomb_impacts_execute_before_enemy_admission": False,
        "visual_animation_interleave_proven": False,
        "wall_clock_timing_proven": False,
    }

    dependencies = {entry["id"] for entry in value["dependencies"]}
    assert dependencies == {
        "final_cave_startup",
        "spawn_coordinate_paths",
        "final_cave_replacement",
        "final_cave_replacement_cadence",
    }
    findings = {entry["id"] for entry in value["findings"]}
    assert findings == {
        "spawn_overloads_are_exact",
        "implicit_enemy_spawn_selects_and_commits_space",
        "spawn_blocks_precede_implicit_selection",
        "logical_spawns_precede_startup_effect_dispatch",
        "startup_rng_order_is_narrower",
        "solver_boundary",
    }
    unresolved = {entry["id"] for entry in value["unresolved"]}
    assert unresolved == {
        "incoming_startup_rng_state",
        "concrete_spawn_identities_and_coordinates",
        "startup_visual_interleave",
        "startup_uid_allocation",
        "non_windows_equivalence",
    }


def test_binding_rejects_wrapper_order_or_prose_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["control_windows"][0]["instruction_hex"] = "90"
    with pytest.raises(
        FinalCaveStartupSpawnOrderError, match="fields differ"
    ):
        validate_final_cave_startup_spawn_order_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["direct_call_edges"][4]["target_rva"] = "0x00172a91"
    with pytest.raises(
        FinalCaveStartupSpawnOrderError, match="fields differ"
    ):
        validate_final_cave_startup_spawn_order_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["semantic_boundary"][
        "visual_animation_interleave_proven"
    ] = True
    with pytest.raises(
        FinalCaveStartupSpawnOrderError, match="fields differ"
    ):
        validate_final_cave_startup_spawn_order_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][3]["claim"] += " overclaim"
    with pytest.raises(
        FinalCaveStartupSpawnOrderError, match="fields differ"
    ):
        validate_final_cave_startup_spawn_order_map_binding(altered)


def test_exact_local_executable_and_sources_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_final_cave_startup_spawn_order_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["spawn_overloads_bound"] is True
    assert result["implicit_selector_and_space_commit_proven"] is True
    assert result["logical_admission_before_effect_dispatch_proven"] is True
    assert result["visual_animation_interleave_proven"] is False
    assert result["concrete_rng_outputs_proven"] is False
