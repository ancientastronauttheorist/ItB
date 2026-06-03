import json

from src.loop.commands import (
    _annotate_pending_grid_debt,
    _capture_board_summary,
    _compute_deltas,
    _evaluate_solution_safety,
    _summary_with_pending_grid_debt,
)
from src.loop.session import RunSession
from src.model.board import Board
from src.solver.solver import Solution


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


def test_summary_honors_board_flying_immunity_when_bridge_payload_is_stale():
    data = _bridge_with_mech(flying=True, danger=[[2, 5, 1, 1, 0]])
    data["mission_id"] = "Mission_Satellite"
    data["targeted_tiles"] = [[2, 5]]
    data["units"].append({
        "uid": 98,
        "type": "SatelliteRocket",
        "x": 2,
        "y": 4,
        "hp": 2,
        "max_hp": 2,
        "team": 1,
        "mech": False,
        "move": 0,
        "weapons": ["Rocket_Launch"],
        "active": False,
        "queued_launch": True,
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert (2, 5) in board.environment_danger_flying_immune
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


def test_summary_tracks_mech_damage_objective_from_bonus_ids():
    data = _bridge_with_mech()
    data["bonus_objective_ids"] = [4, 1]
    data["units"].append({
        "uid": 12,
        "type": "IgniteMech",
        "x": 3,
        "y": 5,
        "hp": 3,
        "max_hp": 3,
        "team": 1,
        "mech": True,
        "move": 4,
        "weapons": ["Ranged_Ignite"],
        "active": True,
        "can_move": True,
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mech_damage_taken_total"] == 1
    assert summary["mech_damage_objective_limit"] == 4


def test_summary_ignores_save_overlay_gap_at_bridge_cap_for_mech_damage_objective():
    data = _bridge_with_mech()
    data["bonus_objective_ids"] = [4]
    data["mech_stat_overlays"] = [
        {"uid": 11, "bridge_max_hp": 2, "save_max_hp": 4},
    ]
    data["units"][0]["hp"] = 2
    data["units"][0]["max_hp"] = 4
    data["units"][0]["bridge_reported_max_hp"] = 2
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mech_damage_taken_total"] == 0
    assert summary["mech_damage_objective_limit"] == 4
    assert summary["mech_hp"] == [
        {"uid": 11, "type": "TeleMech", "hp": 2, "max_hp": 4}
    ]


def test_summary_counts_bridge_cap_damage_below_cap_for_mech_damage_objective():
    data = _bridge_with_mech()
    data["bonus_objective_ids"] = [4]
    data["mech_stat_overlays"] = [
        {"uid": 11, "bridge_max_hp": 2, "save_max_hp": 4},
    ]
    data["units"][0]["hp"] = 1
    data["units"][0]["max_hp"] = 4
    data["units"][0]["bridge_reported_max_hp"] = 2
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mech_damage_taken_total"] == 1
    assert summary["mech_damage_objective_limit"] == 4


def test_solution_safety_prefers_projected_board_summary(monkeypatch):
    data = _bridge_with_mech()
    data["bonus_objective_ids"] = [4]
    data["mech_stat_overlays"] = [
        {"uid": 11, "bridge_max_hp": 2, "save_max_hp": 4},
    ]
    data["units"][0]["hp"] = 2
    data["units"][0]["max_hp"] = 4
    data["units"][0]["bridge_reported_max_hp"] = 2
    board = Board.from_bridge_data(data)
    final_board_data = json.loads(json.dumps(data))
    final_board_data.pop("bonus_objective_ids", None)
    final_board_data.pop("mech_stat_overlays", None)
    final_board_data["environment_danger_v2"] = [[2, 5, 1, 1, 1]]
    final_board_data["units"][0]["x"] = 2
    final_board_data["units"][0]["y"] = 5
    final_board_data["units"][0].pop("bridge_reported_max_hp", None)
    stale_predicted = {
        "mission_id": "Mission_Tides",
        "turn": 1,
        "total_turns": 3,
        "grid_power": 7,
        "mechs_on_danger": [],
        "mech_damage_taken_total": 2,
        "mech_damage_objective_limit": None,
    }

    monkeypatch.setattr(
        "src.loop.commands.replay_solution",
        lambda *args, **kwargs: {
            "predicted_outcome": dict(stale_predicted),
            "final_board": final_board_data,
            "action_results": [],
        },
    )

    result = _evaluate_solution_safety(
        board,
        data,
        Solution(),
        [],
        current_turn=1,
        total_turns=3,
        remaining_spawns=0,
    )

    predicted = result["predicted_board_summary"]
    assert predicted["mechs_on_danger"] == [{
        "uid": 11,
        "type": "TeleMech",
        "pos": [2, 5],
        "damage": 1,
    }]
    assert predicted["mech_damage_taken_total"] == 0
    assert predicted["mech_damage_objective_limit"] == 4
    assert result["plan_safety"]["blocking"] is True
    assert [
        item["kind"] for item in result["plan_safety"]["violations"]
    ] == ["mech_on_danger"]


def test_summary_tracks_mission_kill_objective_progress():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_SnowStorm"
    data["mission_kill_target"] = 5
    data["mission_kill_limit"] = 4
    data["mission_kills_done"] = 4
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mission_kill_target"] == 5
    assert summary["mission_kill_limit"] == 4
    assert summary["mission_kills_done"] == 4


def test_summary_omits_mech_damage_objective_without_bonus_id():
    data = _bridge_with_mech()
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mech_damage_taken_total"] == 1
    assert summary["mech_damage_objective_limit"] is None


def test_summary_tracks_freeze_building_objective_progress():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_FreezeBldg"
    data["freeze_building_target"] = 3
    data["freeze_building_tiles"] = [[1, 1], [2, 1], [3, 1]]
    data["tiles"].extend([
        {
            "x": 1,
            "y": 1,
            "terrain": "building",
            "building_hp": 1,
            "frozen": True,
        },
        {
            "x": 2,
            "y": 1,
            "terrain": "building",
            "building_hp": 1,
            "frozen": False,
        },
        {
            "x": 3,
            "y": 1,
            "terrain": "rubble",
            "building_hp": 0,
            "frozen": False,
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["freeze_building_target"] == 3
    assert summary["freeze_buildings_alive"] == 2
    assert summary["freeze_buildings_frozen"] == 1
    assert summary["freeze_buildings_thawed"] == 1
    assert summary["freeze_buildings"] == [
        {"pos": [1, 1], "alive": True, "frozen": True, "hp": 1},
        {"pos": [2, 1], "alive": True, "frozen": False, "hp": 1},
        {"pos": [3, 1], "alive": False, "frozen": False, "hp": 0},
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


def test_summary_tracks_archive_tanks_from_mission_metadata():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Tanks"
    data["units"].extend([
        {
            "uid": 501,
            "type": "Archive_Tank",
            "x": 3,
            "y": 4,
            "hp": 1,
            "max_hp": 1,
            "team": 1,
            "mech": False,
            "move": 3,
            "weapons": ["Deploy_TankShot"],
        },
        {
            "uid": 502,
            "type": "Archive_Tank",
            "x": 4,
            "y": 4,
            "hp": 0,
            "max_hp": 1,
            "team": 1,
            "mech": False,
            "move": 3,
            "weapons": ["Deploy_TankShot"],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["protected_objective_units_alive"] == 1
    assert [u["type"] for u in summary["protected_objective_units"]] == [
        "Archive_Tank",
        "Archive_Tank",
    ]


def test_summary_tracks_destroy_objective_units_from_mission_metadata():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_AcidStorm"
    data["units"].extend([
        {
            "uid": 601,
            "type": "Storm_Generator",
            "x": 2,
            "y": 2,
            "hp": 3,
            "max_hp": 3,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
        {
            "uid": 602,
            "type": "Storm_Generator",
            "x": 4,
            "y": 2,
            "hp": 0,
            "max_hp": 3,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["destroy_objective_units_alive"] == 1
    assert [u["type"] for u in summary["destroy_objective_units"]] == [
        "Storm_Generator",
        "Storm_Generator",
    ]


def test_summary_tracks_dam_pawn_destroy_objective_from_metadata():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Dam"
    data["units"].extend([
        {
            "uid": 603,
            "type": "Dam_Pawn",
            "x": 0,
            "y": 0,
            "hp": 2,
            "max_hp": 2,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
        {
            "uid": 604,
            "type": "Dam_Pawn",
            "x": 1,
            "y": 0,
            "hp": 0,
            "max_hp": 2,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["destroy_objective_units_alive"] == 1
    assert [u["type"] for u in summary["destroy_objective_units"]] == [
        "Dam_Pawn",
        "Dam_Pawn",
    ]


def test_summary_tracks_bonus_debris_objective_from_bonus_id():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Survive"
    data["bonus_objective_ids"] = [7]
    data["destroy_objective_unit_types"] = ["BonusDebris"]
    data["units"].extend([
        {
            "uid": 701,
            "type": "BonusDebris",
            "x": 4,
            "y": 3,
            "hp": 1,
            "max_hp": 1,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
        {
            "uid": 702,
            "type": "BonusDebris",
            "x": 5,
            "y": 3,
            "hp": 0,
            "max_hp": 1,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["destroy_objective_units_alive"] == 1
    assert [u["type"] for u in summary["destroy_objective_units"]] == [
        "BonusDebris",
        "BonusDebris",
    ]


def test_summary_tracks_terraform_grass_counter_tiles():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Terraform"
    data["tiles"].extend([
        {"x": 3, "y": 2, "terrain": "ground", "grass": True},
        {"x": 4, "y": 3, "terrain": "ground", "custom": "ground_grass.png"},
        {"x": 6, "y": 6, "terrain": "ground"},
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["terraform_grass_remaining"] == 2
    assert summary["terraform_grass_tiles"] == [[3, 2], [4, 3]]


def test_summary_tracks_mission_force_mountain_counter():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Force"
    data["mission_mountain_target"] = 2
    data["mission_mountains_destroyed"] = 1
    data["mission_mountain_tiles"] = [[2, 2], [4, 4]]
    data["tiles"].extend([
        {"x": 2, "y": 2, "terrain": "mountain", "building_hp": 1},
        {"x": 4, "y": 4, "terrain": "mountain", "building_hp": 2},
        {"x": 5, "y": 5, "terrain": "rubble", "building_hp": 0},
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mission_mountain_target"] == 2
    assert summary["mission_mountains_destroyed"] == 1
    assert summary["mission_mountain_tiles"] == [
        {"pos": [2, 2], "hp": 1},
        {"pos": [4, 4], "hp": 2},
    ]


def test_summary_tracks_infected_mechs_for_mite_counter():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Holes"
    data["units"][0]["infected"] = True
    data["units"].append({
        "uid": 12,
        "type": "IgniteMech",
        "x": 4,
        "y": 5,
        "hp": 3,
        "max_hp": 3,
        "team": 1,
        "mech": True,
        "move": 4,
        "weapons": ["Ranged_Ignite"],
        "infected": False,
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mites_status_tracked"] is True
    assert summary["mites_remaining"] == 1
    assert summary["mechs_infected"] == [{
        "uid": 11,
        "type": "TeleMech",
        "pos": [2, 5],
    }]


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


def test_summary_counts_enemy_targets_on_objective_buildings():
    data = _bridge_with_mech()
    data["tiles"].append({
        "x": 4,
        "y": 2,
        "terrain": "building",
        "building_hp": 1,
        "unique_building": True,
        "objective_name": "Str_Power",
    })
    data["units"].append({
        "uid": 106,
        "type": "Moth1",
        "x": 6,
        "y": 2,
        "hp": 3,
        "max_hp": 3,
        "team": 6,
        "mech": False,
        "move": 3,
        "weapons": ["MothAtk1"],
        "queued_target": [4, 2],
        "has_queued_attack": True,
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["objective_buildings_targeted"] == 1
    assert summary["objective_building_targets"] == [{
        "uid": 106,
        "type": "Moth1",
        "pos": [6, 2],
        "target": [4, 2],
    }]


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
