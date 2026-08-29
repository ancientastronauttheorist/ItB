from __future__ import annotations

import copy
from pathlib import Path

import pytest

from src.observatory.enemy_spawn_candidate_boundary import (
    EnemySpawnCandidateBoundaryError,
    bridge_native_enemy_spawn_observations,
    replay_current_bridge_enemy_spawn_candidate_pool,
)
from src.observatory.native_spawn_input_reader import (
    ANALYSIS_KIND as NATIVE_ANALYSIS_KIND,
    CANDIDATE_REPLAY_ANALYSIS_KIND,
    EXPECTED_BUILD_ID,
    EXPECTED_EXECUTABLE_SHA256,
    EXPECTED_EXECUTABLE_SIZE,
    EXPECTED_IMAGE_SIZE,
    NativeSpawnInputReaderError,
    combine_current_bridge_native_capture,
    validate_current_bridge_native_capture_artifact,
)


ROOT = Path(__file__).resolve().parents[1]


def _bridge_payload() -> dict:
    tiles = []
    for y in range(8):
        for x in range(8):
            tiles.append({"x": x, "y": y, "terrain_id": 0})
    return {
        "mission_id": "Mission_Test",
        "phase": "combat_player",
        "turn": 2,
        "tiles": tiles,
        "spawning_tiles": [[5, 4]],
        "native_enemy_spawn_inputs": {
            "schema_version": 1,
            "current_snapshot_only": True,
            "enemy_zone_ordered_complete": True,
            "enemy_zone_ordered": [[5, 2], [5, 3], [5, 4], [5, 5]],
            "dangerous_tiles_complete": True,
            "dangerous_tiles": [[5, 2]],
            "ground_blocked_tiles_complete": True,
            "ground_blocked_tiles": [[5, 3]],
            "block_spawn_values_complete": False,
            "existing_spawn_marker_vector_complete": False,
        },
    }


def _bridge_payload_with_position_carriers() -> dict:
    payload = _bridge_payload()
    for tile in payload["tiles"]:
        tile["dangerous_item"] = False
    payload["native_enemy_position_inputs"] = {
        "schema_version": 1,
        "current_snapshot_only": True,
        "dangerous_item_tiles_complete": True,
        "dangerous_item_tiles": [],
        "pawn_flags_ordered_complete": True,
        "pawn_flags_ordered": [
            {
                "uid": 10,
                "ranged": True,
                "avoiding_mines": False,
            },
            {
                "uid": 11,
                "ranged": False,
                "avoiding_mines": True,
            },
        ],
    }
    payload["units"] = [
        {
            "uid": 10,
            "type": "Firefly1",
            "ranged": 1,
            "avoiding_mines": False,
        },
        {
            "uid": 11,
            "type": "Leaper1",
            "ranged": 0,
            "avoiding_mines": True,
        },
    ]
    return payload


def _block_values() -> dict[tuple[int, int], int]:
    return {(x, y): 0 for x in range(8) for y in range(8)}


def _native_capture() -> dict:
    blocks = _block_values()
    blocks[(5, 5)] = 2
    return {
        "schema_version": 1,
        "analysis_kind": NATIVE_ANALYSIS_KIND,
        "build_identity": {
            "platform": "windows",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "image_size": EXPECTED_IMAGE_SIZE,
        },
        "runtime_overlay_identity": {
            "path": "scripts/modloader.lua",
            "present": True,
            "size": 123,
            "sha256": "a" * 64,
        },
        "process_identity": {"pid": 42, "process_start_unix": 1000.0},
        "captured_at_utc": "2026-08-29T12:00:00+00:00",
        "current_snapshot_only": True,
        "block_spawn_values_complete": True,
        "block_spawn_values": [
            [x, y, blocks[(x, y)]] for x in range(8) for y in range(8)
        ],
        "existing_spawn_marker_vector_complete": True,
        "existing_spawn_marker_vector": [[5, 4]],
        "integrity": {
            "active_board_stable_during_capture": True,
            "native_inputs_stable_during_capture": True,
            "game_memory_written": False,
        },
    }


def test_modloader_exports_exact_current_only_native_spawn_carriers():
    source = (ROOT / "src" / "bridge" / "modloader.lua").read_text(
        encoding="utf-8"
    )
    assert 'Board:GetZone("enemy")' in source
    assert "return Board:IsDangerous(pt)" in source
    assert "return Board:IsBlocked(pt, PATH_GROUND)" in source
    assert "block_spawn_values_complete = false" in source
    assert "existing_spawn_marker_vector_complete = false" in source


def test_observation_normalizer_preserves_zone_order_and_explicit_gaps():
    observations = bridge_native_enemy_spawn_observations(_bridge_payload())
    assert observations == {
        "source_points": ((5, 2), (5, 3), (5, 4), (5, 5)),
        "dangerous_points": frozenset({(5, 2)}),
        "ground_blocked_points": frozenset({(5, 3)}),
        "missing_inputs": (
            "block_spawn_values",
            "existing_spawn_marker_vector",
        ),
        "complete_for_candidate_replay": False,
        "current_snapshot_only": True,
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data["native_enemy_spawn_inputs"].update(
            {"dangerous_tiles_complete": False}
        ),
        lambda data: data["native_enemy_spawn_inputs"].update(
            {"dangerous_tiles": [[8, 0]]}
        ),
        lambda data: data["native_enemy_spawn_inputs"].update(
            {"enemy_zone_ordered": [[5, 2], [5, 2]]}
        ),
        lambda data: data["native_enemy_spawn_inputs"].update(
            {"schema_version": 2}
        ),
    ],
)
def test_observation_normalizer_fails_closed_on_partial_or_malformed_data(mutate):
    data = _bridge_payload()
    mutate(data)
    with pytest.raises(EnemySpawnCandidateBoundaryError):
        bridge_native_enemy_spawn_observations(data)


def test_exact_current_replay_requires_native_only_inputs_and_filters_stably():
    data = _bridge_payload()
    blocks = _block_values()
    blocks[(5, 5)] = 2

    replay = replay_current_bridge_enemy_spawn_candidate_pool(
        data,
        block_spawn_values=blocks,
        existing_spawn_marker_points={(5, 4)},
    )

    assert replay["pool_kind"] == "emergency_max_x_row"
    assert replay["candidates"] == [
        [7, 0],
        [7, 1],
        [7, 2],
        [7, 3],
        [7, 4],
        [7, 5],
        [7, 6],
        [7, 7],
    ]
    assert replay["input_boundary"] == {
        "bridge_native_observations": "exact_current",
        "block_spawn_values": "explicit_native_input",
        "existing_spawn_marker_vector": "explicit_native_input",
        "future_forecast": False,
    }


def test_broader_is_spawning_carrier_is_never_used_as_marker_vector():
    data = _bridge_payload()
    data["spawning_tiles"] = [[5, 4]]
    replay = replay_current_bridge_enemy_spawn_candidate_pool(
        data,
        block_spawn_values=_block_values(),
        existing_spawn_marker_points=set(),
    )
    assert replay["pool_kind"] == "ordinary_primary"
    assert replay["candidates"] == [[5, 4], [5, 5]]


def test_replay_rejects_incomplete_block_map_and_incomplete_board():
    data = _bridge_payload()
    blocks = _block_values()
    blocks.pop((7, 7))
    with pytest.raises(EnemySpawnCandidateBoundaryError, match="complete 8x8"):
        replay_current_bridge_enemy_spawn_candidate_pool(
            data,
            block_spawn_values=blocks,
            existing_spawn_marker_points=set(),
        )

    incomplete = copy.deepcopy(data)
    incomplete["tiles"].pop()
    with pytest.raises(EnemySpawnCandidateBoundaryError, match="complete 8x8"):
        replay_current_bridge_enemy_spawn_candidate_pool(
            incomplete,
            block_spawn_values=_block_values(),
            existing_spawn_marker_points=set(),
        )


def test_bridge_sandwich_combines_exact_native_capture_into_current_replay():
    before = _bridge_payload_with_position_carriers()
    before["timestamp"] = 100.0
    after = copy.deepcopy(before)
    after["timestamp"] = 101.0

    result = combine_current_bridge_native_capture(
        before,
        _native_capture(),
        after,
    )

    assert result["analysis_kind"] == CANDIDATE_REPLAY_ANALYSIS_KIND
    assert result["current_snapshot_only"] is True
    assert result["future_forecast"] is False
    assert result["bridge_state_identity"]["stable_across_native_capture"] is True
    assert len(result["bridge_state_identity"]["projection_sha256"]) == 64
    assert result["candidate_replay"]["pool_kind"] == "emergency_max_x_row"
    assert result["position_observation_replay"] == {
        "dangerous_points": [[5, 2]],
        "dangerous_item_points": [],
        "pawn_flags_ordered": [
            {
                "uid": 10,
                "ranged": True,
                "avoiding_mines": False,
            },
            {
                "uid": 11,
                "ranged": False,
                "avoiding_mines": True,
            },
        ],
        "complete_for_current_score_positioning": True,
        "current_snapshot_only": True,
        "future_candidate_time": False,
    }
    assert result["integrity"] == {
        "bridge_refresh_sandwich": True,
        "bridge_projection_stable": True,
        "native_board_stable": True,
        "native_inputs_stable": True,
        "future_forecast": False,
        "position_observation_carriers_complete": True,
    }
    assert validate_current_bridge_native_capture_artifact(result) == result


def test_bridge_sandwich_fails_closed_on_state_or_native_integrity_drift():
    before = _bridge_payload()
    after = copy.deepcopy(before)
    after["tiles"][0]["terrain_id"] = 3
    with pytest.raises(NativeSpawnInputReaderError, match="bridge spawn inputs"):
        combine_current_bridge_native_capture(before, _native_capture(), after)

    native = _native_capture()
    native["integrity"]["native_inputs_stable_during_capture"] = False
    with pytest.raises(NativeSpawnInputReaderError, match="native capture integrity"):
        combine_current_bridge_native_capture(before, native, before)

    valid = combine_current_bridge_native_capture(
        before,
        _native_capture(),
        before,
    )
    valid["candidate_replay"]["candidate_count"] += 1
    with pytest.raises(NativeSpawnInputReaderError, match="deterministic replay"):
        validate_current_bridge_native_capture_artifact(valid)
