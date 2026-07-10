from src.bridge.reader import (
    _is_infinite_spawn_mission,
    _reconcile_remaining_spawns_with_markers,
    _reconcile_victory_turns_with_live_turn,
)


def test_missing_metadata_ae_boss_mission_is_infinite_spawn():
    assert _is_infinite_spawn_mission("Mission_BlobberBoss") is True


def test_metadata_boss_mission_is_infinite_spawn():
    assert _is_infinite_spawn_mission("Mission_BeetleBoss") is True


def test_non_boss_fixed_roster_mission_is_not_infinite_spawn():
    assert _is_infinite_spawn_mission("Mission_Battle") is False


def test_final_turn_spawn_markers_override_zero_remaining_spawns():
    data = {
        "remaining_spawns": 0,
        "spawning_tiles": [[6, 1], [5, 0], [4, 1]],
    }

    _reconcile_remaining_spawns_with_markers(data)

    assert data["remaining_spawns"] == 3
    assert data["remaining_spawns_bridge_raw"] == 0
    assert data["remaining_spawns_reconciled_from_markers"] is True


def test_spawn_marker_reconciliation_keeps_larger_bridge_count():
    data = {
        "remaining_spawns": 4,
        "spawning_tiles": [[6, 1], [5, 0], [4, 1]],
    }

    _reconcile_remaining_spawns_with_markers(data)

    assert data == {
        "remaining_spawns": 4,
        "spawning_tiles": [[6, 1], [5, 0], [4, 1]],
    }


def test_spawn_marker_reconciliation_fails_closed_on_malformed_marker():
    data = {
        "remaining_spawns": 0,
        "spawning_tiles": [[6, 1], [9, 0]],
    }

    _reconcile_remaining_spawns_with_markers(data)

    assert data["remaining_spawns"] == 0
    assert "remaining_spawns_reconciled_from_markers" not in data


def test_live_turn_reconciles_stale_victory_countdown():
    data = {
        "phase": "combat_player",
        "turn": 4,
        "total_turns": 4,
        "victory_turns": 2,
    }

    _reconcile_victory_turns_with_live_turn(data)

    assert data["victory_turns"] == 1
    assert data["victory_turns_save_raw"] == 2
    assert data["victory_turns_reconciled_from_live_turn"] is True


def test_live_turn_keeps_matching_victory_countdown_unchanged():
    data = {
        "phase": "combat_player",
        "turn": 3,
        "total_turns": 4,
        "victory_turns": 2,
    }

    _reconcile_victory_turns_with_live_turn(data)

    assert data == {
        "phase": "combat_player",
        "turn": 3,
        "total_turns": 4,
        "victory_turns": 2,
    }


def test_victory_countdown_reconciliation_rejects_invalid_live_window():
    data = {
        "phase": "combat_player",
        "turn": 5,
        "total_turns": 4,
        "victory_turns": 2,
    }

    _reconcile_victory_turns_with_live_turn(data)

    assert "victory_turns" not in data
    assert data["victory_turns_save_raw"] == 2
    assert data["victory_turns_invalid_live_window"] is True
    assert "victory_turns_reconciled_from_live_turn" not in data
