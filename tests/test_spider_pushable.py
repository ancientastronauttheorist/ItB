from src.model.board import Board
from src.model.pawn_stats import get_pawn_stats


def test_normal_and_alpha_spiders_are_pushable() -> None:
    assert get_pawn_stats("Spider1").pushable is True
    assert get_pawn_stats("Spider2").pushable is True


def test_bridge_board_keeps_spider_pushable_by_static_stats() -> None:
    board = Board.from_bridge_data({
        "units": [
            {
                "uid": 624,
                "type": "Spider1",
                "x": 3,
                "y": 3,
                "hp": 1,
                "max_hp": 2,
                "team": 6,
                "mech": False,
            }
        ],
        "tiles": [],
    })

    spider = board.units[0]
    assert spider.pushable is True
