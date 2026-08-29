from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.observatory.enemy_spawn_candidate_boundary import (
    ANALYSIS_KIND,
    BLOCKED_PERM,
    BLOCKED_TEMP,
    DEPENDENCY_SPECS,
    EnemySpawnCandidateBoundaryError,
    EnemySpawnTileFacts,
    POOL_EMERGENCY_MAX_X_ROW,
    POOL_FAILURE,
    POOL_ORDINARY_PRIMARY,
    POOL_ORDINARY_TURN_ZERO_FOREST_RETRY,
    TERRAIN_FOREST,
    TERRAIN_ROAD,
    TERRAIN_WATER,
    default_enemy_spawn_zone,
    enemy_spawn_tile_is_valid,
    replay_enemy_spawn_candidate_pool_from_valid_points,
    selected_terrain_after_spawn,
    validate_enemy_spawn_candidate_boundary_map,
    validate_enemy_spawn_candidate_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_MAP = ROOT / "data" / "observatory" / "native" / (
    "windows_build_13725832_31fe35265598_enemy_spawn_candidate_boundary.json"
)
EXECUTABLE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")


def _load() -> dict:
    return json.loads(BOUNDARY_MAP.read_text(encoding="utf-8"))


def _valid_points(vector: dict) -> dict[int, list[list[int]]]:
    return {item["mode"]: item["points"] for item in vector["valid_points"]}


def test_committed_map_closes_parameterized_enemy_candidate_construction():
    value = _load()
    result = validate_enemy_spawn_candidate_boundary_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "950fc2618b36e901502d2da6fd256e987f343c6c1132453c3f431960e4f9a3e7"
        ),
        "enemy_source_order_proven": True,
        "primary_stable_filter_proven": True,
        "turn_zero_mode9_retry_proven": True,
        "emergency_max_x_row_proven": True,
        "enemy_validity_rejections_proven": True,
        "parameterized_replay_complete": True,
        "concrete_forecast_proven": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["summary"] == {
        "dependency_count": 6,
        "region_count": 9,
        "control_window_count": 15,
        "direct_edge_count": 16,
        "replay_vector_count": 5,
        "unresolved_count": 5,
        "enemy_source_order_proven": True,
        "primary_stable_filter_proven": True,
        "turn_zero_mode9_retry_proven": True,
        "emergency_max_x_row_proven": True,
        "enemy_validity_rejections_proven": True,
        "parameterized_replay_complete": True,
        "concrete_forecast_proven": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["solver_impact"]["simulator_version_bump_required"] is False


def test_default_enemy_zone_and_all_replay_branches_are_exact():
    assert default_enemy_spawn_zone() == (
        (5, 2),
        (5, 3),
        (5, 4),
        (5, 5),
        (6, 2),
        (6, 3),
        (6, 4),
        (6, 5),
        (7, 2),
        (7, 3),
        (7, 4),
        (7, 5),
    )

    value = _load()
    results = []
    for vector in value["replay_vectors"]:
        result = replay_enemy_spawn_candidate_pool_from_valid_points(
            vector["source_points"],
            vector["board_dimensions"][0],
            vector["board_dimensions"][1],
            vector["turn"],
            _valid_points(vector),
        )
        assert result == vector["expected"]
        results.append(result)

    assert [item["pool_kind"] for item in results] == [
        POOL_ORDINARY_PRIMARY,
        POOL_ORDINARY_TURN_ZERO_FOREST_RETRY,
        POOL_EMERGENCY_MAX_X_ROW,
        POOL_EMERGENCY_MAX_X_ROW,
        POOL_FAILURE,
    ]
    assert results[0]["candidates"] == [[5, 4], [6, 2]]
    assert results[1]["candidates"] == [[5, 3], [6, 5]]
    assert results[2]["candidates"] == [[7, 1], [7, 3]]
    assert results[3]["candidates"] == [[6, 2], [6, 7]]
    assert results[4]["rng_caller_id"] is None
    assert all(item["rng_consumed"] is False for item in results)


def test_enemy_validity_rejects_each_native_input_without_guessing_it():
    assert enemy_spawn_tile_is_valid(6, EnemySpawnTileFacts()) is True
    assert (
        enemy_spawn_tile_is_valid(
            9,
            EnemySpawnTileFacts(terrain=TERRAIN_FOREST),
        )
        is True
    )
    assert (
        enemy_spawn_tile_is_valid(
            6,
            EnemySpawnTileFacts(terrain=TERRAIN_FOREST),
        )
        is False
    )

    rejected = [
        EnemySpawnTileFacts(has_item=True),
        EnemySpawnTileFacts(active_pod=True),
        EnemySpawnTileFacts(block_spawn=BLOCKED_TEMP),
        EnemySpawnTileFacts(block_spawn=BLOCKED_PERM),
        EnemySpawnTileFacts(dangerous=True),
        EnemySpawnTileFacts(blocked_for_ground=True),
        EnemySpawnTileFacts(terrain=5),
        EnemySpawnTileFacts(terrain=TERRAIN_WATER),
        EnemySpawnTileFacts(acid=True),
        EnemySpawnTileFacts(existing_spawn_marker=True),
    ]
    assert all(not enemy_spawn_tile_is_valid(6, facts) for facts in rejected)
    assert enemy_spawn_tile_is_valid(6, EnemySpawnTileFacts(block_spawn=3)) is True

    with pytest.raises(EnemySpawnCandidateBoundaryError, match="mode must be 6 or 9"):
        enemy_spawn_tile_is_valid(1, EnemySpawnTileFacts())


def test_mode9_selected_forest_is_the_only_terrain_cleanup():
    assert (
        selected_terrain_after_spawn(
            POOL_ORDINARY_TURN_ZERO_FOREST_RETRY,
            TERRAIN_FOREST,
        )
        == TERRAIN_ROAD
    )
    assert (
        selected_terrain_after_spawn(POOL_ORDINARY_PRIMARY, TERRAIN_FOREST)
        == TERRAIN_FOREST
    )
    assert (
        selected_terrain_after_spawn(
            POOL_ORDINARY_TURN_ZERO_FOREST_RETRY,
            TERRAIN_WATER,
        )
        == TERRAIN_WATER
    )


def test_replay_rejects_ambiguous_or_out_of_contract_inputs():
    with pytest.raises(EnemySpawnCandidateBoundaryError, match="must be unique"):
        replay_enemy_spawn_candidate_pool_from_valid_points(
            [[5, 2], [5, 2]],
            8,
            8,
            0,
            {6: [], 9: []},
        )
    with pytest.raises(EnemySpawnCandidateBoundaryError, match="width >= 3"):
        default_enemy_spawn_zone(2, 8)
    with pytest.raises(EnemySpawnCandidateBoundaryError, match="mode must be 6 or 9"):
        replay_enemy_spawn_candidate_pool_from_valid_points(
            [[5, 2]],
            8,
            8,
            0,
            {1: []},
        )


def test_binding_rejects_contract_replay_or_solver_scope_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["emergency"]["same_row_order"] = "descending y"
    with pytest.raises(EnemySpawnCandidateBoundaryError, match="fields differ"):
        validate_enemy_spawn_candidate_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["replay_vectors"][2]["expected"]["candidates"].reverse()
    with pytest.raises(EnemySpawnCandidateBoundaryError, match="fields differ"):
        validate_enemy_spawn_candidate_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["solver_impact"]["production_forecast_enabled"] = True
    with pytest.raises(EnemySpawnCandidateBoundaryError, match="fields differ"):
        validate_enemy_spawn_candidate_boundary_map_binding(altered)


def test_artifact_file_is_immutable_and_hash_pinned():
    assert BOUNDARY_MAP.stat().st_size == 33_110
    assert hashlib.sha256(BOUNDARY_MAP.read_bytes()).hexdigest() == (
        "1ae8d63d5a605c814bd565f656b377076ce686856408503fc16479f89e363bde"
    )


def test_build_rejects_upstream_dependency_drift(tmp_path: Path):
    for spec in DEPENDENCY_SPECS:
        source = ROOT / spec["path"]
        destination = tmp_path / spec["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    changed = tmp_path / DEPENDENCY_SPECS[0]["path"]
    changed.write_bytes(changed.read_bytes() + b" ")

    with pytest.raises(EnemySpawnCandidateBoundaryError, match="dependency file differs"):
        validate_enemy_spawn_candidate_boundary_map(
            EXECUTABLE,
            _load(),
            tmp_path,
        )


def test_exact_local_executable_reproduces_candidate_map_when_available():
    if not EXECUTABLE.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_enemy_spawn_candidate_boundary_map(
        EXECUTABLE,
        _load(),
        ROOT,
    )
    assert result["status"] == "verified"
