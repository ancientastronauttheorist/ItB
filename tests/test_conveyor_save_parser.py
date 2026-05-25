from src.bridge.reader import _parse_conveyor_belts_from_save_text


def test_conveyor_parser_does_not_cross_tile_entries():
    save_text = """
["map"] = {{["loc"] = Point( 1, 5 ), ["terrain"] = 1, ["health_max"] = 1, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 2, 5 ), ["terrain"] = 0, ["custom"] = "conveyor0.png", },
{["loc"] = Point( 3, 6 ), ["terrain"] = 1, ["health_max"] = 2, },
},
"""

    belts = _parse_conveyor_belts_from_save_text(save_text)

    assert belts == {
        (2, 4): 3,
        (2, 5): 0,
    }
