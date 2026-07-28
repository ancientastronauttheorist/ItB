from copy import deepcopy

from src.model.board import Board
from src.loop import commands


def _sandstorm_bridge() -> dict:
    return {
        "mission_id": "Mission_Sandstorm",
        "env_type": "sandstorm",
        "grid_power": 7,
        "tiles": [
            {"x": 2, "y": 2, "terrain": "building", "building_hp": 2},
        ],
        "units": [
            {
                "uid": 1,
                "type": "PunchMech",
                "x": 3,
                "y": 3,
                "hp": 3,
                "max_hp": 3,
                "team": 1,
                "mech": True,
            },
        ],
        "environment_danger": [[2, 2], [3, 3]],
        "environment_danger_v2": [[2, 2, 1, 0, 0], [3, 3, 1, 0, 0]],
    }


def test_sandstorm_warning_omits_phantom_damage():
    board = Board.from_bridge_data(_sandstorm_bridge())

    assert board.env_type == "sandstorm"
    assert board.environment_danger == set()
    assert board.environment_danger_v2 == {}
    assert board.environment_smoke == set()


def test_sandstorm_warning_is_not_reported_as_damage():
    bridge = _sandstorm_bridge()
    board = Board.from_bridge_data(bridge)

    assert commands._environment_danger_info(board, bridge) == {}


def test_sandstorm_raw_markers_do_not_break_held_checkpoint_parity():
    checkpoint = {
        "mission_id": "Mission_Sandstorm",
        "env_type": "sandstorm",
        "grid_power": 7,
        "grid_power_max": 7,
        "turn": 2,
        "total_turns": 4,
        "remaining_spawns": 0,
        "mission_kill_target": 0,
        "mission_kill_limit": 0,
        "mission_kills_done": 0,
        "mission_mountain_target": 0,
        "mission_mountains_destroyed": 0,
        "repair_platform_target": 0,
        "repair_platforms_used": 0,
        "freeze_building_target": 0,
        "tiles": [
            {"x": x, "y": y, "terrain": "ground"}
            for x in range(8)
            for y in range(8)
        ],
        "units": [],
        "environment_danger": [],
        "environment_danger_v2": [],
    }
    live_data = deepcopy(checkpoint)
    live_data["environment_danger"] = [[3, 3]]
    live_data["environment_danger_v2"] = [[3, 3, 1, 0, 0]]
    live_board = Board.from_bridge_data(live_data)

    result = commands._held_end_turn_post_player_parity_error(
        {"post_player_board": checkpoint, "actions": []},
        live_board,
        live_data,
    )

    assert result is None
