from src.loop.commands import _enrich_bridge_mech_weapons_from_save


def test_partial_resolve_keeps_upgraded_weapon_overlay(monkeypatch):
    from src.loop.commands import _re_solve_partial
    from src.loop.session import RunSession
    from src.model.board import Board
    import itb_solver
    import json

    bridge_data = {
        "phase": "combat_player",
        "turn": 1,
        "grid_power": 5,
        "grid_power_max": 7,
        "units": [
            {
                "uid": 2,
                "type": "PulseMech",
                "mech": True,
                "team": 1,
                "x": 4,
                "y": 2,
                "hp": 5,
                "max_hp": 3,
                "active": True,
                "weapons": ["Science_Repulse"],
            }
        ],
        "tiles": [],
        "spawning_tiles": [],
    }

    class FakeState:
        weapons = [
            "Brute_Jetmech",
            "",
            "Ranged_Rocket",
            "",
            "Science_Repulse_A",
            "",
        ]

    captured = {}

    def fake_solve(payload, _time_limit):
        captured["payload"] = json.loads(payload)
        return json.dumps({"actions": []})

    monkeypatch.setattr(
        "src.loop.commands.load_game_state",
        lambda profile="Alpha": FakeState(),
    )
    monkeypatch.setattr(itb_solver, "solve", fake_solve)

    _re_solve_partial(
        Board(),
        bridge_data,
        done_uids=set(),
        mid_action_uid=None,
        time_limit=1.0,
        session=RunSession(),
    )

    pulse = captured["payload"]["units"][0]
    assert pulse["weapons"] == ["Science_Repulse_A"]
    assert captured["payload"]["weapon_upgrade_overlays"] == [{
        "uid": 2,
        "slot": 0,
        "base": "Science_Repulse",
        "upgraded": "Science_Repulse_A",
    }]


def test_ranged_ignite_backburn_overlay_from_save(monkeypatch):
    bridge_data = {
        "units": [
            {
                "uid": 1,
                "type": "IgniteMech",
                "mech": True,
                "weapons": ["Ranged_Ignite"],
            }
        ]
    }

    class FakeState:
        weapons = [
            "Prime_Flamethrower",
            "",
            "Ranged_Ignite_A",
            "",
            "Science_Swap",
            "",
        ]

    monkeypatch.setattr(
        "src.loop.commands.load_game_state",
        lambda profile="Alpha": FakeState(),
    )

    updates = _enrich_bridge_mech_weapons_from_save(bridge_data)

    assert updates == [{
        "uid": 1,
        "slot": 0,
        "base": "Ranged_Ignite",
        "upgraded": "Ranged_Ignite_A",
    }]
    assert bridge_data["units"][0]["weapons"] == ["Ranged_Ignite_A"]


def test_artemis_buildings_immune_overlay_from_save(monkeypatch):
    bridge_data = {
        "units": [
            {
                "uid": 1,
                "type": "ArtiMech",
                "mech": True,
                "weapons": ["Ranged_Artillerymech"],
            }
        ]
    }

    class FakeState:
        weapons = [
            "Prime_Punchmech",
            "",
            "Ranged_Artillerymech_A",
            "",
            "Science_Repulse",
            "",
        ]

    monkeypatch.setattr(
        "src.loop.commands.load_game_state",
        lambda profile="Alpha": FakeState(),
    )

    updates = _enrich_bridge_mech_weapons_from_save(bridge_data)

    assert updates == [{
        "uid": 1,
        "slot": 0,
        "base": "Ranged_Artillerymech",
        "upgraded": "Ranged_Artillerymech_A",
    }]
    assert bridge_data["units"][0]["weapons"] == ["Ranged_Artillerymech_A"]
