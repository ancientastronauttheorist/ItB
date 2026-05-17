import json

from src.loop.commands import (
    _annotate_pending_grid_debt,
    _capture_board_summary,
    _compute_deltas,
    _summary_with_pending_grid_debt,
)
from src.loop.session import RunSession
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


def test_summary_tracks_protected_objective_units_from_mission_metadata():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_FreezeBots"
    data["units"].extend([
        {
            "uid": 301,
            "type": "Snowtank1",
            "x": 1,
            "y": 2,
            "hp": 1,
            "max_hp": 1,
            "team": 6,
            "mech": False,
            "move": 4,
            "weapons": [],
            "frozen": True,
        },
        {
            "uid": 302,
            "type": "Snowlaser2",
            "x": 2,
            "y": 2,
            "hp": 0,
            "max_hp": 1,
            "team": 6,
            "mech": False,
            "move": 4,
            "weapons": [],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["protected_objective_units_alive"] == 1
    assert summary["protected_objective_units_frozen"] == 1
    assert [u["type"] for u in summary["protected_objective_units"]] == [
        "Snowtank1",
        "Snowlaser2",
    ]


def test_summary_tracks_proto_bombs_from_mission_metadata():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Bomb"
    data["units"].extend([
        {
            "uid": 401,
            "type": "ProtoBomb",
            "x": 3,
            "y": 4,
            "hp": 1,
            "max_hp": 1,
            "team": 1,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
        {
            "uid": 402,
            "type": "ProtoBomb",
            "x": 4,
            "y": 2,
            "hp": 0,
            "max_hp": 1,
            "team": 1,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["protected_objective_units_alive"] == 1
    assert [u["type"] for u in summary["protected_objective_units"]] == [
        "ProtoBomb",
        "ProtoBomb",
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


def test_pending_grid_debt_detects_delayed_grid_scalar(tmp_path, monkeypatch):
    board = Board()
    board.grid_power = 5
    board.grid_power_max = 7
    for x, y, hp in ((3, 4, 2), (4, 2, 1), (5, 6, 2)):
        board.tile(x, y).terrain = "building"
        board.tile(x, y).building_hp = hp
    bridge_data = {
        "turn": 2,
        "mission_seeds": {
            "region6": {"state": 0, "mission": "Mission4"}
        },
    }
    log_path = tmp_path / "resist_probe.jsonl"
    log_path.write_text(json.dumps({
        "run_id": "run",
        "region": "region6",
        "turn": 2,
        "grid_power": 5,
        "building_hp_map": {
            "D5": 2,
            "F4": 2,
            "B3": 2,
        },
    }) + "\n")
    monkeypatch.setattr(
        "src.loop.commands._recording_dir",
        lambda session: tmp_path,
    )

    debt = _annotate_pending_grid_debt(
        RunSession(run_id="run"),
        board,
        bridge_data,
    )

    assert debt == 1
    assert bridge_data["_pending_grid_debt"] == 1
    summary = _summary_with_pending_grid_debt(
        {"grid_power": 5, "building_hp_total": 5},
        debt,
    )
    assert summary["visible_grid_power"] == 5
    assert summary["grid_power"] == 4


def test_pending_grid_debt_ignores_stale_same_region_turn(tmp_path, monkeypatch):
    board = Board()
    board.grid_power = 7
    board.grid_power_max = 7
    for x, y, hp in ((1, 2, 1), (1, 6, 1), (2, 6, 1), (4, 3, 2), (5, 3, 2), (5, 6, 1)):
        board.tile(x, y).terrain = "building"
        board.tile(x, y).building_hp = hp
    bridge_data = {
        "turn": 1,
        "mission_id": "Mission_Disposal",
        "master_seed": 113578278,
        "mission_seeds": {
            "region1": {"state": 0, "mission": "Mission1"}
        },
    }
    log_path = tmp_path / "resist_probe.jsonl"
    log_path.write_text(
        json.dumps({
            "run_id": "run",
            "mission_id": "Mission_Tides",
            "region": "region1",
            "mission_slot": "Mission3",
            "turn": 1,
            "master_seed": 814802298,
            "grid_power": 5,
            "building_hp_map": {
                "C8": 1,
                "B8": 1,
                "C7": 1,
                "B7": 1,
                "G6": 2,
                "F6": 2,
                "B5": 1,
                "B4": 2,
            },
        }) + "\n" + json.dumps({
            "run_id": "run",
            "mission_id": "Mission_Disposal",
            "region": "region1",
            "mission_slot": "Mission1",
            "turn": 1,
            "master_seed": 113578278,
            "grid_power": 7,
            "building_hp_map": {
                "F7": 1,
                "B7": 1,
                "B6": 1,
                "E4": 2,
                "E3": 2,
                "B3": 1,
            },
        }) + "\n"
    )
    monkeypatch.setattr(
        "src.loop.commands._recording_dir",
        lambda session: tmp_path,
    )

    debt = _annotate_pending_grid_debt(
        RunSession(run_id="run"),
        board,
        bridge_data,
    )

    assert debt == 0
    assert "_pending_grid_debt" not in bridge_data
