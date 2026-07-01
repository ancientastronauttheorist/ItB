import json
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


def _needs_upgrades_loadout() -> dict:
    loadout = _needs_cores_loadout()
    loadout["cores"] = 5
    return loadout


def _ready_loadout() -> dict:
    loadout = _needs_cores_loadout()
    loadout["cores"] = 0
    loadout["weapons"] = [
        "Brute_PierceShot",
        "",
        "Ranged_DeployBomb_A",
        "",
        "Science_TC_SwapOther",
        "",
    ]
    loadout["pilots"][1]["power"] = [1, 1]
    return loadout


def _mission_json(tmp_path, island_map: list[dict]) -> str:
    path = tmp_path / "island_map.json"
    path.write_text(json.dumps({
        "grid_power": 6,
        "units": [
            {"mech": True, "hp": 3, "weapons": ["Brute_PierceShot"]},
            {"mech": True, "hp": 3, "weapons": ["Ranged_DeployBomb_A"]},
            {"mech": True, "hp": 3, "weapons": ["Science_TC_SwapOther"]},
        ],
        "island_map": island_map,
    }))
    return str(path)


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
    assert status["setup_stage"] == "ATTEMPT_READY"
    assert status["resource_plan"]["missing_cores_for_attempt"] == 0


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
    assert status["structural_ready"] is True
    assert status["upgrade_ready"] is True


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

    assert status["setup_stage"] == "STRUCTURAL_BLOCKED"
    assert status["structural_ready"] is False
    assert status["upgrade_ready"] is False
    assert status["resource_plan"]["missing_cores_for_attempt"] == 2
    assert status["resource_plan"]["core_shortfall"] == 2
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
    assert setup["setup_stage"] == "NEEDS_CORES"
    assert setup["structural_ready"] is True
    assert setup["upgrade_ready"] is False
    assert setup["resource_plan"]["missing_cores_for_attempt"] == 5
    assert setup["resource_plan"]["core_shortfall"] == 5
    assert commands._no_survivors_structural_setup_gaps(setup) == []
    assert commands._no_survivors_precombat_guard(session) is None
    assert any("resource-gathering missions may continue" in item for item in plan)


def test_no_survivors_setup_stage_needs_upgrades_when_cores_available():
    setup = commands._no_survivors_setup_status_from_loadout(
        _needs_upgrades_loadout()
    )
    plan = commands._no_survivors_setup_plan(setup)

    assert setup["setup_stage"] == "NEEDS_UPGRADES"
    assert setup["resource_plan"]["missing_cores_for_attempt"] == 5
    assert setup["resource_plan"]["core_shortfall"] == 0
    assert any("Spend available cores" in item for item in plan)


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


def _status_session(targets: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        run_id="status_test",
        phase="combat_player",
        current_turn=2,
        squad="Bombermechs",
        achievement_targets=targets,
        tags=[],
        actions_executed=0,
        actions_remaining=lambda: 3,
        post_enemy_block=None,
    )


def test_status_includes_no_survivors_setup_for_target(monkeypatch):
    monkeypatch.setattr(
        commands,
        "_load_session",
        lambda: _status_session(["No Survivors"]),
    )
    monkeypatch.setattr(commands, "load_game_state", lambda profile="Alpha": None)
    monkeypatch.setattr(
        commands,
        "_read_no_survivors_run_loadout",
        lambda profile="Alpha": _not_ready_loadout(),
    )

    result = commands.cmd_status()

    setup = result["no_survivors_setup"]
    assert setup["setup_stage"] == "STRUCTURAL_BLOCKED"
    assert setup["attempt_ready"] is False
    assert setup["structural_ready"] is False
    assert "Move Silica/Pilot_Miner onto Bombling Mech." in setup["structural_gaps"]
    assert setup["resource_plan"]["core_shortfall"] == 2


def test_status_skips_no_survivors_setup_for_other_targets(monkeypatch):
    monkeypatch.setattr(
        commands,
        "_load_session",
        lambda: _status_session(["Powered Blast"]),
    )
    monkeypatch.setattr(commands, "load_game_state", lambda profile="Alpha": None)

    def unexpected_loadout(profile="Alpha"):
        raise AssertionError("No Survivors setup should not be read")

    monkeypatch.setattr(
        commands,
        "_read_no_survivors_run_loadout",
        unexpected_loadout,
    )

    result = commands.cmd_status()

    assert "no_survivors_setup" not in result


def test_recommend_mission_uses_setup_routing_before_attempt_ready(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        commands,
        "_load_session",
        lambda: SimpleNamespace(achievement_targets=["No Survivors"], tags=[]),
    )
    monkeypatch.setattr(
        commands,
        "_read_no_survivors_run_loadout",
        lambda profile="Alpha": _needs_cores_loadout(),
    )
    island_json = _mission_json(tmp_path, [
        {
            "region_id": 1,
            "mission_id": "Mission_Generic",
            "bonus_objective_ids": [1],
            "environment": "Env_Null",
        },
        {
            "region_id": 2,
            "mission_id": "Mission_Disposal",
            "bonus_objective_ids": [],
            "environment": "Env_Null",
        },
    ])

    result = commands.cmd_recommend_mission(island_map_json=island_json)

    assert result["routing"] == "no_survivors_setup"
    assert result["no_survivors_setup"]["setup_stage"] == "NEEDS_CORES"
    assert result["top3"][0]["bonus_objective_ids"] == [1]


def test_recommend_mission_uses_attempt_routing_when_no_survivors_ready(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        commands,
        "_load_session",
        lambda: SimpleNamespace(achievement_targets=["No Survivors"], tags=[]),
    )
    monkeypatch.setattr(
        commands,
        "_read_no_survivors_run_loadout",
        lambda profile="Alpha": _ready_loadout(),
    )
    island_json = _mission_json(tmp_path, [
        {
            "region_id": 1,
            "mission_id": "Mission_Generic",
            "bonus_objective_ids": [1],
            "environment": "Env_Null",
        },
        {
            "region_id": 2,
            "mission_id": "Mission_Disposal",
            "bonus_objective_ids": [],
            "environment": "Env_Null",
        },
    ])

    result = commands.cmd_recommend_mission(island_map_json=island_json)

    assert result["routing"] == "no_survivors"
    assert result["no_survivors_setup"]["setup_stage"] == "ATTEMPT_READY"
    assert result["top3"][0]["mission_id"] == "Mission_Disposal"


def test_new_run_persists_no_survivors_setup_requirements(monkeypatch):
    requirement = {
        "kind": "pilot_slot",
        "pilot_id": "Pilot_Miner",
        "pilot_name": "Silica",
        "mech": "BomblingMech",
    }
    setup_payload = {
        "squad": "Bombermechs",
        "squad_key": "bombermechs",
        "mode": "achievement_hunt",
        "reason": "target 'No Survivors' requires Bombermechs",
        "requested_achievements": ["No Survivors"],
        "remaining_achievements": ["No Survivors"],
        "ui_setup": "Select the Bombermechs squad card, then Start.",
        "warnings": [],
        "setup_priorities": ["Pilot: put Silica on Bombling Mech."],
        "setup_requirements": [requirement],
    }
    fake_setup = SimpleNamespace(
        squad="Bombermechs",
        mode="achievement_hunt",
        reason="target 'No Survivors' requires Bombermechs",
        ui_setup="Select the Bombermechs squad card, then Start.",
        setup_priorities=["Pilot: put Silica on Bombling Mech."],
        setup_requirements=[requirement],
        warnings=[],
        to_dict=lambda: setup_payload,
    )
    manifests = []
    logs = []

    monkeypatch.setattr(
        commands,
        "recommend_squad_for_run",
        lambda **kwargs: fake_setup,
    )
    monkeypatch.setattr(
        commands,
        "detect_game_phase",
        lambda *args, **kwargs: "no_save",
    )
    monkeypatch.setattr(commands.RunSession, "save", lambda self, path=None: None)
    monkeypatch.setattr(
        commands,
        "_write_manifest",
        lambda session, extra=None: manifests.append((session, extra)),
    )

    class StubDecisionLog:
        def __init__(self, run_id):
            self.run_id = run_id

        def log_custom(self, label, message):
            logs.append((label, message))

    monkeypatch.setattr(commands, "DecisionLog", StubDecisionLog)

    result = commands.cmd_new_run(
        achievements=["No Survivors"],
        difficulty=0,
        tags=["achievement"],
    )

    assert result["setup"] == setup_payload
    assert manifests
    assert manifests[0][1]["setup"] == setup_payload
    assert logs
    assert logs[0][0] == "New Run"
    assert "Pilot_Miner" in logs[0][1]
    assert "BomblingMech" in logs[0][1]
