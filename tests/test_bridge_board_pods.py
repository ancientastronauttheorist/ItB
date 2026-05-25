from src.model.board import Board


def test_from_bridge_data_accepts_final_board_has_pod_field():
    board = Board.from_bridge_data({
        "grid_power": 7,
        "tiles": [
            {"x": 2, "y": 3, "terrain": "ground", "has_pod": True},
        ],
        "units": [],
    })

    assert board.tile(2, 3).has_pod is True
