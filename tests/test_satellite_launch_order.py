import json

from src.bridge.reader import _mark_satellite_launch_danger_flying_immune
from src.loop.commands import _load_board_from_recording
from src.model.board import Board


def _satellite_state():
    return {
        "mission_id": "Mission_Satellite",
        "grid_power": 5,
        "grid_power_max": 7,
        "targeted_tiles": [[3, 5], [5, 5], [4, 4], [4, 6]],
        "environment_danger": [[3, 5], [5, 5], [4, 4], [4, 6], [0, 0]],
        "environment_danger_v2": [
            [3, 5, 1, 1, 0],
            [5, 5, 1, 1, 0],
            [4, 4, 1, 1, 0],
            [4, 6, 1, 1, 0],
            [0, 0, 1, 1, 0],
        ],
        "tiles": [],
        "units": [
            {
                "uid": 2146,
                "type": "SatelliteRocket",
                "team": 1,
                "hp": 2,
                "max_hp": 2,
                "x": 4,
                "y": 5,
                "weapons": ["Rocket_Launch"],
                "queued_launch": True,
            },
        ],
    }


def test_reader_marks_satellite_launch_danger_flying_immune():
    state = _satellite_state()

    _mark_satellite_launch_danger_flying_immune(state)

    assert state["environment_danger"] == [[3, 5], [5, 5], [4, 4], [4, 6], [0, 0]]
    assert state["environment_danger_v2"] == [
        [3, 5, 1, 1, 1],
        [5, 5, 1, 1, 1],
        [4, 4, 1, 1, 1],
        [4, 6, 1, 1, 1],
        [0, 0, 1, 1, 0],
    ]
    assert state["targeted_tiles"] == [[3, 5], [5, 5], [4, 4], [4, 6]]


def test_board_marks_satellite_targets_as_flying_immune_env_danger():
    state = _satellite_state()
    state["environment_danger"] = []
    state["environment_danger_v2"] = []

    board = Board.from_bridge_data(state)

    assert (3, 5) in board.environment_danger
    assert (5, 5) in board.environment_danger
    assert (4, 4) in board.environment_danger
    assert (4, 6) in board.environment_danger
    assert board.environment_danger_flying_immune == {
        (3, 5),
        (5, 5),
        (4, 4),
        (4, 6),
    }


def test_recording_loader_normalizes_stale_satellite_payload(tmp_path):
    path = tmp_path / "turn_02_board.json"
    path.write_text(json.dumps({"data": {"bridge_state": _satellite_state()}}))

    bridge_data, board, _spawns, _environment_danger = _load_board_from_recording(path)

    assert bridge_data["environment_danger_v2"][0] == [3, 5, 1, 1, 1]
    assert (3, 5) in board.environment_danger_flying_immune
