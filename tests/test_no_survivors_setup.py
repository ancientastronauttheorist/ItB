from types import SimpleNamespace

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


def _not_ready_loadout() -> dict:
    return {
        "status": "OK",
        "source": "test",
        "squad_index": 11,
        "grid_power": 6,
        "grid_power_max": 7,
        "money": 0,
        "cores": 0,
        "mechs": ["PierceMech", "BomblingMech", "ExchangeMech"],
        "weapons": [
            "Brute_PierceShot",
            "",
            "Ranged_DeployBomb_A",
            "",
            "Science_TC_SwapOther",
            "",
        ],
        "pilots": [
            {
                "slot": 0,
                "id": "Pilot_Miner",
                "name": "Silica",
                "power": [0, 0],
            },
            {"slot": 1, "id": "Pilot_Detritus", "name": "Steve", "power": []},
            {"slot": 2, "id": "Pilot_Archive", "name": "Esther", "power": []},
        ],
    }


def _needs_cores_loadout() -> dict:
    return {
        "status": "OK",
        "source": "test",
        "squad_index": 11,
        "grid_power": 7,
        "grid_power_max": 7,
        "money": 1,
        "cores": 0,
        "mechs": ["PierceMech", "BomblingMech", "ExchangeMech"],
        "weapons": [
            "Brute_PierceShot",
            "",
            "Ranged_DeployBomb",
            "",
            "Science_TC_SwapOther",
            "",
        ],
        "pilots": [
            {"slot": 0, "id": "Pilot_Archive", "name": "Esther", "power": []},
            {
                "slot": 1,
                "id": "Pilot_Miner",
                "name": "Silica",
                "power": [0, 0],
            },
            {"slot": 2, "id": "Pilot_Detritus", "name": "Steve", "power": []},
        ],
    }


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


def test_no_survivors_require_ready_blocks_with_plan():
    status = commands._no_survivors_setup_status_from_loadout(_not_ready_loadout())
    blocked = commands._require_no_survivors_setup_ready(status)

    assert blocked["status"] == "BLOCKED"
    assert blocked["blocking"] is True
    assert blocked["precombat_block"] is True
    assert "Move Silica/Pilot_Miner onto Bombling Mech." in blocked["setup_plan"]
    assert any("Double Shot" in item for item in blocked["setup_plan"])


def test_no_survivors_precombat_guard_allows_core_gathering(monkeypatch):
    monkeypatch.setattr(
        commands,
        "_read_no_survivors_run_loadout",
        lambda profile="Alpha": _needs_cores_loadout(),
    )
    session = SimpleNamespace(
        achievement_targets=["No Survivors"],
        tags=[],
    )

    setup = commands._no_survivors_setup_status_from_loadout(_needs_cores_loadout())
    plan = commands._no_survivors_setup_plan(setup)

    assert setup["attempt_ready"] is False
    assert commands._no_survivors_structural_setup_gaps(setup) == []
    assert commands._no_survivors_precombat_guard(session) is None
    assert any("resource-gathering missions may continue" in item for item in plan)


def test_no_survivors_precombat_guard_only_for_target(monkeypatch):
    monkeypatch.setattr(
        commands,
        "_read_no_survivors_run_loadout",
        lambda profile="Alpha": _not_ready_loadout(),
    )
    target_session = SimpleNamespace(
        achievement_targets=["No Survivors"],
        tags=[],
    )
    other_session = SimpleNamespace(
        achievement_targets=["Powered Blast"],
        tags=[],
    )

    blocked = commands._no_survivors_precombat_guard(target_session)

    assert blocked is not None
    assert blocked["status"] == "NO_SURVIVORS_SETUP_BLOCKED"
    assert commands._no_survivors_precombat_guard(other_session) is None


def test_deploy_recommended_blocks_no_survivors_before_deploy(monkeypatch):
    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (
            object(),
            {
                "deployment_zone": [(0, 0), (0, 1), (0, 2)],
                "turn": 0,
                "phase": "deployment",
            },
        ),
    )
    monkeypatch.setattr(
        commands,
        "_load_session",
        lambda: SimpleNamespace(achievement_targets=["No Survivors"], tags=[]),
    )
    monkeypatch.setattr(
        commands,
        "_read_no_survivors_run_loadout",
        lambda profile="Alpha": _not_ready_loadout(),
    )

    def unexpected_rank(*args, **kwargs):
        raise AssertionError("deploy ranking should not run when setup is blocked")

    monkeypatch.setattr(commands, "recommend_deploy_tiles", unexpected_rank)

    result = commands.cmd_deploy_recommended(skip_initial_refresh=True)

    assert result["status"] == "NO_SURVIVORS_SETUP_BLOCKED"
    assert result["blocking"] is True
