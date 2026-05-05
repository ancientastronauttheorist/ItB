from src.loop.commands import _capture_board_summary, _compute_deltas
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


def test_summary_excludes_friendly_objective_units_from_mech_loss():
    data = _bridge_with_mech()
    data["units"].append({
        "uid": 492,
        "type": "Disposal_Unit",
        "x": 2,
        "y": 4,
        "hp": 2,
        "max_hp": 2,
        "team": 1,
        "mech": False,
        "move": 0,
        "weapons": ["Disposal_Attack"],
        "active": True,
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mechs_alive"] == 1
    assert summary["mech_hp_total"] == 1
    assert summary["mech_hp"] == [
        {"uid": 11, "type": "TeleMech", "hp": 1, "max_hp": 2}
    ]


def test_summary_keeps_dead_player_mechs_for_post_enemy_diff():
    data = _bridge_with_mech()
    data["units"][0]["hp"] = 0
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mechs_alive"] == 0
    assert summary["mech_hp_total"] == 0
    assert summary["mech_hp"] == [
        {"uid": 11, "type": "TeleMech", "hp": 0, "max_hp": 2}
    ]


def test_summary_treats_missing_hp_unique_building_as_destroyed_projection():
    data = _bridge_with_mech()
    data["tiles"].append({
        "x": 4,
        "y": 6,
        "terrain": "building",
        "unique_building": True,
        "objective_name": "Str_Power",
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert board.tile(4, 6).building_hp == 0
    assert summary["objective_buildings_alive"] == 0
    assert summary["objective_building_hp_total"] == 0


def test_bridge_terrain_id_overrides_stale_lava_name_for_ice():
    data = _bridge_with_mech()
    data["tiles"].append({
        "x": 5,
        "y": 5,
        "terrain": "lava",
        "terrain_id": 5,
    })
    board = Board.from_bridge_data(data)

    assert board.tile(5, 5).terrain == "ice"


def test_deltas_flags_predicted_mech_missing_from_actual_as_dead():
    predicted = {
        "buildings_alive": 7,
        "building_hp_total": 10,
        "grid_power": 6,
        "enemies_alive": 3,
        "mech_hp": [
            {"uid": 11, "type": "TeleMech", "hp": 2, "max_hp": 2}
        ],
    }
    actual = {
        "buildings_alive": 7,
        "building_hp_total": 10,
        "grid_power": 6,
        "enemies_alive": 3,
        "mech_hp": [],
    }

    deltas = _compute_deltas(predicted, actual)

    assert deltas["mech_hp_diff"] == [{
        "uid": 11,
        "type": "TeleMech",
        "predicted_hp": 2,
        "actual_hp": 0,
        "diff": -2,
    }]
    assert deltas["unexpected_events"] == [
        "TeleMech took 2 unexpected damage"
    ]
