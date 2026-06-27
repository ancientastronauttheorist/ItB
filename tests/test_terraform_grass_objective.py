import textwrap

from src.bridge import reader as bridge_reader
from src.bridge.reader import (
    _active_region_keys,
    _grass_tiles_from_region_blocks,
    _region_blocks,
    _read_terraform_grass_tiles_from_save,
    _safe_to_overlay_save_grass,
)
from src.model.board import Board
from src.solver.evaluate import EvalWeights, evaluate, evaluate_breakdown


def test_active_region_grass_tiles_are_parsed_from_custom_sprite():
    content = textwrap.dedent(
        r'''
        ["region0"] = {["player"] = {["iState"] = 4, ["iCurrentTurn"] = 0, },
        ["map_data"] = {
        {["loc"] = Point( 1, 1 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
        }, },
        ["region6"] = {["player"] = {["iState"] = 0, ["iCurrentTurn"] = 4, },
        ["map_data"] = {
        {["loc"] = Point( 3, 3 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
        {["loc"] = Point( 4, 4 ), ["terrain"] = 3, ["custom"] = "ground_grass.png", },
        {["loc"] = Point( 7, 2 ), ["terrain"] = 7, },
        }, },
        '''
    )

    data = {
        "mission_id": "Mission_Terraform",
        "turn": 4,
        "phase": "combat_player",
        "active_mechs": 1,
        "mission_seeds": {
            "region0": {"state": 4, "turn": 0},
            "region6": {"state": 0, "turn": 4},
        },
        "units": [
            {
                "team": 1,
                "hp": 2,
                "active": True,
                "weapons": ["Terraformer_Attack"],
            }
        ],
    }

    assert _active_region_keys(data) == ["region6"]
    assert _safe_to_overlay_save_grass(data) is True
    assert _grass_tiles_from_region_blocks(
        _region_blocks(content),
        {"region6"},
    ) == {(3, 3), (4, 4)}


def test_read_terraform_grass_tiles_uses_platform_save_reader(monkeypatch):
    content = textwrap.dedent(
        r'''
        ["region4"] = {["player"] = {["iState"] = 4, ["iCurrentTurn"] = 0, },
        ["map_data"] = {
        {["loc"] = Point( 1, 1 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
        }, },
        ["region5"] = {["player"] = {["iState"] = 0, ["iCurrentTurn"] = 3, },
        ["map_data"] = {
        {["loc"] = Point( 3, 2 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
        {["loc"] = Point( 4, 3 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
        }, },
        '''
    )
    calls = []

    def fake_read_save_text(filename, profile="Alpha"):
        calls.append((filename, profile))
        return content if filename == "saveData.lua" else None

    monkeypatch.setattr(bridge_reader, "_read_save_text", fake_read_save_text)
    data = {
        "mission_id": "Mission_Terraform",
        "turn": 3,
        "mission_seeds": {
            "region4": {"state": 4, "turn": 0},
            "region5": {"state": 0, "turn": 3},
        },
    }

    assert _read_terraform_grass_tiles_from_save(data) == {(3, 2), (4, 3)}
    assert calls == [("saveData.lua", "Alpha")]


def test_save_grass_overlay_is_blocked_mid_turn():
    data = {
        "mission_id": "Mission_Terraform",
        "phase": "combat_player",
        "active_mechs": 0,
        "units": [
            {
                "team": 1,
                "hp": 2,
                "active": False,
                "weapons": ["Terraformer_Attack"],
            }
        ],
    }

    assert _safe_to_overlay_save_grass(data) is False


def test_mission_terraform_grass_scores_as_remaining_objective_debt():
    board = Board()
    board.grid_power = 7
    board.grid_power_max = 7
    board.mission_id = "Mission_Terraform"
    board.tile(3, 3).grass = True

    weights = EvalWeights(mission_terraform_grass_remaining=-2500)
    score_with_grass = evaluate(
        board,
        weights=weights,
        current_turn=4,
        total_turns=5,
        remaining_spawns=0,
    )
    board.tile(3, 3).grass = False
    score_without_grass = evaluate(
        board,
        weights=weights,
        current_turn=4,
        total_turns=5,
        remaining_spawns=0,
    )

    assert score_without_grass - score_with_grass == 2500
    info = evaluate_breakdown(
        board,
        weights=weights,
        current_turn=4,
        total_turns=5,
        remaining_spawns=0,
    )["mission_terraform_grass"]
    assert info == {"remaining": 0, "score": 0}


def test_bridge_grass_field_sets_board_tile_flag():
    board = Board.from_bridge_data({
        "mission_id": "Mission_Terraform",
        "tiles": [
            {"x": 2, "y": 5, "terrain": "ground", "grass": True},
            {"x": 3, "y": 4, "terrain": "ground", "custom": "ground_grass.png"},
        ],
        "units": [],
    })

    assert board.tile(2, 5).grass is True
    assert board.tile(3, 4).grass is True
