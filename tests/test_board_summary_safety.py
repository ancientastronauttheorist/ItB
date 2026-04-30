from src.loop.commands import _capture_board_summary
from src.model.board import Board


def _bridge_with_mech(*, flying=False, danger=None):
    return {
        "grid_power": 7,
        "tiles": [],
        "environment_danger_v2": danger or [],
        "units": [{
            "uid": 11,
            "type": "TeleMech",
            "x": 2,
            "y": 5,
            "hp": 1,
            "max_hp": 2,
            "team": 1,
            "mech": True,
            "move": 4,
            "weapons": ["Science_Swap"],
            "active": True,
            "can_move": True,
            "flying": flying,
        }],
    }


def test_summary_flags_mech_on_lethal_environment_danger():
    data = _bridge_with_mech(danger=[[2, 5, 1, 1, 0]])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mechs_on_danger"] == [{
        "uid": 11,
        "type": "TeleMech",
        "pos": [2, 5],
        "damage": 1,
    }]


def test_summary_honors_flying_immunity_for_environment_danger():
    data = _bridge_with_mech(flying=True, danger=[[2, 5, 1, 1, 1]])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mechs_on_danger"] == []


def test_summary_does_not_treat_spent_action_as_disabled():
    data = _bridge_with_mech()
    data["units"][0]["active"] = False
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mechs_disabled"] == []
