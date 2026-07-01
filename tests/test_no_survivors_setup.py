from src.capture import save_parser
from src.loop import commands


NO_SURVIVORS_SAVE = """
GameData = {["network"] = 7, ["networkMax"] = 7, ["difficulty"] = 0,
["current"] = {["difficulty"] = 0, ["islands"] = 2, ["squad"] = 11,
["mechs"] = {"PierceMech", "BomblingMech", "ExchangeMech", },
["weapons"] = {"Brute_PierceShot", "", "Ranged_DeployBomb", "", "Science_TC_SwapOther", "", },
["pilot0"] = {["id"] = "Pilot_Archive", ["name"] = "Esther", },
["pilot1"] = {["id"] = "Pilot_Miner", ["name"] = "Silica", ["power"] = {1, 1, }, },
["pilot2"] = {["id"] = "Pilot_Detritus", ["name"] = "Steve", },
},}
SquadData = {["money"] = 2, ["cores"] = 3,
["pawn1"] = {["primary"] = "Ranged_DeployBomb", ["primary_mod1"] = {1, }, ["primary_mod2"] = {}, },
}
"""


def test_no_survivors_setup_falls_back_to_undo_save(tmp_path):
    undo_path = tmp_path / "undoSave.lua"
    undo_path.write_text(NO_SURVIVORS_SAVE)

    loadout = commands._read_no_survivors_run_loadout(
        profile_path=tmp_path / "profile.lua",
        save_paths=[tmp_path / "saveData.lua", undo_path],
    )
    status = commands._no_survivors_setup_status_from_loadout(loadout)

    assert loadout["source"] == "undoSave.lua"
    assert [item["source"] for item in loadout["source_attempts"]] == [
        "profile",
        "saveData.lua",
        "undoSave.lua",
    ]
    assert status["attempt_ready"] is True


def test_no_survivors_setup_reports_resources_without_blocking(tmp_path):
    save_path = tmp_path / "saveData.lua"
    save_path.write_text(NO_SURVIVORS_SAVE)

    loadout = commands._read_save_current_run_loadout(path=save_path)
    status = commands._no_survivors_setup_status_from_loadout(loadout)

    assert status["attempt_ready"] is True
    assert status["resources"] == {
        "grid_power": 7,
        "grid_power_max": 7,
        "money": 2,
        "cores": 3,
    }


def test_save_parser_load_game_state_reports_squad_resources(tmp_path, monkeypatch):
    profile_dir = tmp_path / "profile_Alpha"
    profile_dir.mkdir()
    (profile_dir / "saveData.lua").write_text(NO_SURVIVORS_SAVE)
    monkeypatch.setattr(save_parser, "SAVE_DIR", tmp_path)

    state = save_parser.load_game_state("Alpha")

    assert state is not None
    assert state.money == 2
    assert state.cores == 3


def test_save_parser_extracts_pawn_pilot_power(tmp_path):
    save_path = tmp_path / "saveData.lua"
    save_path.write_text(
        """
RegionData = {["iBattleRegion"] = 0,
["region0"] = {["player"] = {["sMission"] = "Mission_Test",
["iCurrentTurn"] = 1, ["iTeamTurn"] = 1, ["iState"] = 0, ["victory"] = 4,
["map_data"] = {["name"] = "Test Map", ["map"] = {}, ["pawn_count"] = 1,
["pawn1"] = {["id"] = 1, ["type"] = "BomblingMech",
["location"] = Point(1, 2), ["health"] = 3, ["max_health"] = 3,
["iTeamId"] = 1, ["mech"] = true, ["primary"] = "Ranged_DeployBomb",
["pilot"] = {["id"] = "Pilot_Miner", ["name"] = "Silica", ["power"] = {1, 1, }, },
},},},},}
"""
    )

    data = save_parser.parse_save_file(save_path)
    player = data["RegionData"]["region0"]["player"]
    mission = save_parser.extract_mission_state(player, player["map_data"])

    assert mission.pawns[0].pilot_id == "Pilot_Miner"
    assert mission.pawns[0].pilot_power == [1, 1]
