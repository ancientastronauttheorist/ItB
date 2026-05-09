from pathlib import Path

from src.capture import save_parser
from src.capture.save_parser import Point, extract_mission_state, parse_lua_value


def test_bare_numeric_lua_array_parses_as_list():
    value, pos = parse_lua_value("{3, 3, }")

    assert value == [3, 3]
    assert pos == len("{3, 3, }")


def test_partial_upgrade_mod_group_does_not_overlay():
    mission = extract_mission_state(
        {"sMission": "Mission_Test"},
        {
            "pawn_count": 1,
            "pawn1": {
                "id": 1,
                "type": "RocketMech",
                "location": Point(2, 2),
                "health": 5,
                "max_health": 5,
                "iTeamId": 1,
                "mech": True,
                "primary": "Ranged_Rocket",
                "primary_mod1": [3, 0],
                "primary_mod2": [0, 0],
            },
        },
    )

    assert mission.pawns[0].primary_weapon == "Ranged_Rocket"


def test_extract_mission_state_overlays_modeled_weapon_mods():
    mission = extract_mission_state(
        {"sMission": "Mission_Test"},
        {
            "pawn_count": 1,
            "pawn1": {
                "id": 1,
                "type": "RocketMech",
                "location": Point(2, 2),
                "health": 5,
                "max_health": 5,
                "iTeamId": 1,
                "mech": True,
                "primary": "Ranged_Rocket",
                "primary_mod1": [3, 3],
                "primary_mod2": [0, 0],
            },
        },
    )

    assert mission.pawns[0].primary_weapon == "Ranged_Rocket_A"


def test_load_game_state_overlays_squad_pawn_mods(tmp_path, monkeypatch):
    profile_dir = tmp_path / "profile_Test"
    profile_dir.mkdir()
    (profile_dir / "saveData.lua").write_text(
        """
GameData = {
["network"] = 5,
["networkMax"] = 7,
["difficulty"] = 0,
["current"] = {
["mechs"] = {"JetMech", "RocketMech", "PulseMech", },
["weapons"] = {"Brute_Jetmech", "", "Ranged_Rocket", "Passive_Electric_A", "Science_Repulse", "", },
},
}

SquadData = {
["pawn1"] = {
["primary"] = "Ranged_Rocket",
["primary_mod1"] = {3, 3, },
["primary_mod2"] = {0, 0, },
["secondary"] = "Passive_Electric",
["secondary_mod1"] = {1, 1, 1, },
["secondary_mod2"] = {0, },
},
["pawn2"] = {
["primary"] = "Science_Repulse",
["primary_mod1"] = {3, },
["primary_mod2"] = {0, 0, },
},
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(save_parser, "SAVE_DIR", Path(tmp_path))

    state = save_parser.load_game_state("Test")

    assert state.weapons == [
        "Brute_Jetmech",
        "",
        "Ranged_Rocket_A",
        "Passive_Electric_A",
        "Science_Repulse_A",
        "",
    ]
