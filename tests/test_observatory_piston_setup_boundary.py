from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.observatory.piston_setup_boundary import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    PistonSetupBoundaryError,
    replay_piston_start_mission,
    validate_piston_setup_boundary_map,
    validate_piston_setup_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_MAP = ROOT / "data" / "observatory" / "native" / (
    "windows_build_13725832_31fe35265598_piston_setup_boundary.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(BOUNDARY_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_parameterized_piston_setup_rng_boundary():
    value = _load()
    result = validate_piston_setup_boundary_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "0368d923cef97c4bb500c287a355ae43b24c0d59bf81529731f2956a8fd7717f"
        ),
        "candidate_order_proven": True,
        "zone_order_proven": True,
        "rejected_draw_count_proven": True,
        "constructor_draw_proven": True,
        "parameterized_replay_complete": True,
        "concrete_forecast_proven": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "binding_count": 8,
        "candidate_order_proven": True,
        "concrete_forecast_proven": False,
        "constructor_draw_proven": True,
        "control_window_count": 18,
        "data_pointer_count": 3,
        "dependency_count": 3,
        "direct_edge_count": 22,
        "finding_count": 7,
        "map_count": 7,
        "parameterized_replay_complete": True,
        "region_count": 33,
        "rejected_draw_count_proven": True,
        "replay_vector_count": 21,
        "scalar_anchor_count": 6,
        "simulator_change_required": False,
        "simulator_version": 408,
        "source_count": 6,
        "string_anchor_count": 9,
        "unresolved_count": 4,
        "vector_anchor_count": 4,
        "zone_order_proven": True,
    }
    assert value["refines"] == [
        {
            "artifact": (
                "data/observatory/native/"
                "windows_build_13725832_31fe35265598_"
                "piston_scheduler_boundary.json"
            ),
            "qualification": (
                "The stock setup grammar and parameterized replay are exact. "
                "The incoming shared state, concrete used-map registry, and "
                "future selected map remain runtime inputs rather than static facts."
            ),
            "resolved_unresolved_ids": ["mission_piston_setup_rng"],
        }
    ]
    assert {item["id"] for item in value["unresolved"]} == {
        "incoming_shared_crt_state",
        "concrete_used_map_registry",
        "concrete_runtime_instances",
        "modded_or_non_windows_setup",
    }
    assert value["solver_impact"]["simulator_change_required"] is False
    assert value["solver_impact"]["current_simulator_version"] == 408


def test_exact_map_pool_zone_order_and_initial_rejections_are_pinned():
    value = _load()
    maps = value["maps"]
    assert [item["map_name"] for item in maps] == [
        "acid0",
        "acid1",
        "acid10",
        "acid11",
        "acid15",
        "acid3",
        "acid4",
    ]
    assert [item["map_list_index_zero_based"] for item in maps] == [
        0,
        1,
        2,
        3,
        7,
        9,
        10,
    ]
    assert maps[0]["pistons_zone"][:4] == [[4, 7], [4, 6], [5, 6], [5, 5]]
    assert maps[4]["tags"] == ["generic", "acid", "pistons"]

    rejected = [
        item["source"]
        for candidate in maps
        for item in candidate["initial_eligible_directions"]
        if item["guaranteed_initial_rejection"]
    ]
    assert rejected == [[2, 0], [2, 7]]
    assert all(not item["embedded_pawns"] for item in maps)
    assert all(not item["spawns"] for item in maps)


def test_replay_pins_hidden_constructor_draw_and_dynamic_zone_removal():
    result = replay_piston_start_mission("acid0", 0)

    assert result["accepted_count"] == 4
    assert result["rejected_count"] == 0
    assert result["attempt_count"] == 4
    assert result["draw_count"] == 12
    assert result["draw_count_formula_holds"] is True
    assert result["canonical_observable_final_state"] == "0x6dc4fe0c"
    assert result["placements"] == [
        {
            "placement_index": 1,
            "source": [4, 2],
            "direction": "up",
            "direction_native_value": 0,
            "pawn_type": "Pawn_Piston_U",
            "front": [4, 1],
            "constructor_raw_result": 21238,
            "forward_removed_from_zone": True,
        },
        {
            "placement_index": 2,
            "source": [4, 6],
            "direction": "left",
            "direction_native_value": 3,
            "pawn_type": "Pawn_Piston_L",
            "front": [3, 6],
            "constructor_raw_result": 11797,
            "forward_removed_from_zone": False,
        },
        {
            "placement_index": 3,
            "source": [5, 2],
            "direction": "down",
            "direction_native_value": 2,
            "pawn_type": "Pawn_Piston_D",
            "front": [5, 3],
            "constructor_raw_result": 10450,
            "forward_removed_from_zone": False,
        },
        {
            "placement_index": 4,
            "source": [5, 5],
            "direction": "right",
            "direction_native_value": 1,
            "pawn_type": "Pawn_Piston_R",
            "front": [6, 5],
            "constructor_raw_result": 28100,
            "forward_removed_from_zone": True,
        },
    ]
    assert [item["source"] for item in result["rng_transcript"]] == [
        "random_removal(pistons_zone)",
        "random_element(eligible_directions)",
        "Pawn common constructor raw draw",
    ] * 4
    assert [
        item["bound"] for item in result["rng_transcript"] if "constructor" in item["source"]
    ] == [None, None, None, None]


def test_replay_rejected_candidates_consume_only_one_draw_each():
    result = replay_piston_start_mission("acid1", 1)

    assert result["attempt_count"] == 6
    assert result["accepted_count"] == 4
    assert result["rejected_count"] == 2
    assert result["draw_count"] == 14
    assert result["canonical_observable_final_state"] == "0x41bbb05f"
    rejected = [item for item in result["attempts"] if not item["accepted"]]
    assert [(item["source"], item["draws_consumed"]) for item in rejected] == [
        ([2, 7], 1),
        ([2, 0], 1),
    ]
    accepted = [item for item in result["attempts"] if item["accepted"]]
    assert all(item["draws_consumed"] == 3 for item in accepted)


def test_replay_canonicalizes_only_the_permanently_hidden_state_bit():
    low = replay_piston_start_mission("acid4", 1)
    high = replay_piston_start_mission("acid4", 0x80000001)
    assert low["input_state"] == "0x00000001"
    assert high["input_state"] == "0x80000001"
    assert low["canonical_observable_pre_call_state"] == "0x00000001"
    assert high["canonical_observable_pre_call_state"] == "0x00000001"
    assert {key: value for key, value in low.items() if key != "input_state"} == {
        key: value for key, value in high.items() if key != "input_state"
    }

    for state in (True, -1, 0x1_0000_0000, "1"):
        with pytest.raises(PistonSetupBoundaryError, match="32-bit unsigned"):
            replay_piston_start_mission("acid4", state)  # type: ignore[arg-type]
    with pytest.raises(PistonSetupBoundaryError, match="map name must be one of"):
        replay_piston_start_mission("acid2", 1)


def test_binding_rejects_draw_zone_guard_or_solver_scope_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["rng_grammar"]["accepted_attempt_draws"] = 2
    with pytest.raises(PistonSetupBoundaryError, match="fields differ"):
        validate_piston_setup_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["maps"][1]["pistons_zone"][8] = [2, 1]
    with pytest.raises(PistonSetupBoundaryError, match="fields differ"):
        validate_piston_setup_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["guarded_paths"][
        "fallback_reachable_for_candidate_zone_points"
    ] = True
    with pytest.raises(PistonSetupBoundaryError, match="fields differ"):
        validate_piston_setup_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["solver_impact"]["simulator_change_required"] = True
    with pytest.raises(PistonSetupBoundaryError, match="fields differ"):
        validate_piston_setup_boundary_map_binding(altered)


def test_artifact_file_is_immutable_and_hash_pinned():
    assert BOUNDARY_MAP.stat().st_size == 113_312
    assert hashlib.sha256(BOUNDARY_MAP.read_bytes()).hexdigest() == (
        "dfd1ab705beee79f06a609865930f918b937745c22393f516c5f84720a69b230"
    )
    assert not BOUNDARY_MAP.is_symlink()


def test_exact_local_executable_sources_maps_and_dependencies_reproduce_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_piston_setup_boundary_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["candidate_order_proven"] is True
    assert result["zone_order_proven"] is True
    assert result["constructor_draw_proven"] is True
    assert result["parameterized_replay_complete"] is True
    assert result["concrete_forecast_proven"] is False
    assert result["simulator_change_required"] is False
    assert result["simulator_version"] == 408
