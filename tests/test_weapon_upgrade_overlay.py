from types import SimpleNamespace

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


def test_swap_mech_full_range_overlay_from_save(monkeypatch):
    bridge_data = {
        "units": [
            {
                "uid": 2,
                "type": "TeleMech",
                "mech": True,
                "weapons": ["Science_Swap"],
            }
        ]
    }

    class FakeState:
        weapons = [
            "Prime_Flamethrower",
            "",
            "Ranged_Ignite_A",
            "",
            "Science_Swap_AB",
            "",
        ]

    monkeypatch.setattr(
        "src.loop.commands.load_game_state",
        lambda profile="Alpha": FakeState(),
    )

    updates = _enrich_bridge_mech_weapons_from_save(bridge_data)

    assert updates == [{
        "uid": 2,
        "slot": 0,
        "base": "Science_Swap",
        "upgraded": "Science_Swap_AB",
    }]
    assert bridge_data["units"][0]["weapons"] == ["Science_Swap_AB"]


def test_firestorm_range_overlay_from_save(monkeypatch):
    bridge_data = {
        "units": [
            {
                "uid": 2,
                "type": "NapalmMech",
                "mech": True,
                "weapons": ["Science_RainingFire"],
            }
        ]
    }

    class FakeState:
        weapons = [
            "Prime_Flamethrower",
            "",
            "Brute_TC_DoubleShot",
            "",
            "Science_RainingFire_A",
            "",
        ]

    monkeypatch.setattr(
        "src.loop.commands.load_game_state",
        lambda profile="Alpha": FakeState(),
    )

    updates = _enrich_bridge_mech_weapons_from_save(bridge_data)

    assert updates == [{
        "uid": 2,
        "slot": 0,
        "base": "Science_RainingFire",
        "upgraded": "Science_RainingFire_A",
    }]
    assert bridge_data["units"][0]["weapons"] == ["Science_RainingFire_A"]


def test_quick_fire_damage_overlay_from_save(monkeypatch):
    bridge_data = {
        "units": [
            {
                "uid": 1,
                "type": "DoubletankMech",
                "mech": True,
                "weapons": ["Brute_TC_DoubleShot"],
            }
        ]
    }

    class FakeState:
        weapons = [
            "Prime_Flamethrower",
            "",
            "Brute_TC_DoubleShot_B",
            "",
            "Science_RainingFire_A",
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
        "base": "Brute_TC_DoubleShot",
        "upgraded": "Brute_TC_DoubleShot_B",
    }]
    assert bridge_data["units"][0]["weapons"] == ["Brute_TC_DoubleShot_B"]


def test_quick_fire_stronger_upgrade_replaces_same_base_suffix(monkeypatch):
    bridge_data = {
        "units": [
            {
                "uid": 1,
                "type": "DoubletankMech",
                "mech": True,
                "weapons": ["Brute_TC_DoubleShot_A"],
            }
        ]
    }

    class FakeState:
        weapons = [
            "Prime_Flamethrower",
            "",
            "Brute_TC_DoubleShot_AB",
            "",
            "Science_RainingFire_A",
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
        "base": "Brute_TC_DoubleShot",
        "upgraded": "Brute_TC_DoubleShot_AB",
    }]
    assert bridge_data["units"][0]["weapons"] == ["Brute_TC_DoubleShot_AB"]


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


def test_titan_fist_dash_overlay_from_save(monkeypatch):
    bridge_data = {
        "units": [
            {
                "uid": 0,
                "type": "PunchMech",
                "mech": True,
                "weapons": ["Prime_Punchmech"],
            }
        ]
    }

    class FakeState:
        weapons = [
            "Prime_Punchmech_A",
            "",
            "Brute_Tankmech",
            "",
            "Ranged_Artillerymech",
            "",
        ]

    monkeypatch.setattr(
        "src.loop.commands.load_game_state",
        lambda profile="Alpha": FakeState(),
    )

    updates = _enrich_bridge_mech_weapons_from_save(bridge_data)

    assert updates == [{
        "uid": 0,
        "slot": 0,
        "base": "Prime_Punchmech",
        "upgraded": "Prime_Punchmech_A",
    }]
    assert bridge_data["units"][0]["weapons"] == ["Prime_Punchmech_A"]


def test_rocket_artillery_damage_upgrades_overlay_from_save(monkeypatch):
    for upgraded in ("Ranged_Rocket_A", "Ranged_Rocket_B", "Ranged_Rocket_AB"):
        bridge_data = {
            "units": [
                {
                    "uid": 1,
                    "type": "RocketMech",
                    "mech": True,
                    "weapons": ["Ranged_Rocket", "Passive_Electric"],
                }
            ]
        }

        class FakeState:
            weapons = [
                "Brute_Jetmech",
                "",
                upgraded,
                "Passive_Electric_A",
                "Science_Repulse",
                "",
            ]

        monkeypatch.setattr(
            "src.loop.commands.load_game_state",
            lambda profile="Alpha", state=FakeState(): state,
        )

        updates = _enrich_bridge_mech_weapons_from_save(bridge_data)

        assert updates == [{
            "uid": 1,
            "slot": 0,
            "base": "Ranged_Rocket",
            "upgraded": upgraded,
        }]
        assert bridge_data["units"][0]["weapons"] == [
            upgraded,
            "Passive_Electric",
        ]


def test_ricochet_rocket_damage_upgrade_overlay_from_save(monkeypatch):
    bridge_data = {
        "units": [
            {
                "uid": 0,
                "type": "BulkMech",
                "mech": True,
                "weapons": ["Brute_TC_Ricochet"],
            }
        ]
    }

    class FakeState:
        weapons = [
            "Brute_TC_Ricochet_A",
            "",
            "Ranged_Arachnoid",
            "",
            "Science_MassShift",
            "",
        ]

    monkeypatch.setattr(
        "src.loop.commands.load_game_state",
        lambda profile="Alpha": FakeState(),
    )

    updates = _enrich_bridge_mech_weapons_from_save(bridge_data)

    assert updates == [{
        "uid": 0,
        "slot": 0,
        "base": "Brute_TC_Ricochet",
        "upgraded": "Brute_TC_Ricochet_A",
    }]
    assert bridge_data["units"][0]["weapons"] == ["Brute_TC_Ricochet_A"]


def test_force_amp_passive_overlay_from_save(monkeypatch):
    bridge_data = {
        "units": [
            {
                "uid": 1,
                "type": "MirrorMech",
                "mech": True,
                "weapons": ["Brute_Mirrorshot_A"],
            }
        ]
    }

    class FakeState:
        weapons = [
            "Prime_ShieldBash",
            "",
            "Brute_Mirrorshot_A",
            "Passive_ForceAmp",
            "Ranged_Ice",
            "",
        ]

    monkeypatch.setattr(
        "src.loop.commands.load_game_state",
        lambda profile="Alpha": FakeState(),
    )

    updates = _enrich_bridge_mech_weapons_from_save(bridge_data)

    assert updates == [{
        "uid": 1,
        "slot": 1,
        "base": "Passive_ForceAmp",
        "upgraded": "Passive_ForceAmp",
    }]
    assert bridge_data["units"][0]["weapons"] == [
        "Brute_Mirrorshot_A",
        "Passive_ForceAmp",
    ]


def test_cataclysm_upgraded_weapons_overlay_from_save(monkeypatch):
    bridge_data = {
        "units": [
            {
                "uid": 0,
                "type": "BottlecapMech",
                "mech": True,
                "weapons": ["Prime_TC_Punt"],
            },
            {
                "uid": 1,
                "type": "TrimissileMech",
                "mech": True,
                "weapons": ["Ranged_Crack"],
            },
            {
                "uid": 2,
                "type": "HydrantMech",
                "mech": True,
                "weapons": ["Science_KO_Crack"],
            },
        ]
    }

    class FakeState:
        weapons = [
            "Prime_TC_Punt_B",
            "",
            "Ranged_Crack_B",
            "",
            "Science_KO_Crack_A",
            "",
        ]

    monkeypatch.setattr(
        "src.loop.commands.load_game_state",
        lambda profile="Alpha": FakeState(),
    )

    updates = _enrich_bridge_mech_weapons_from_save(bridge_data)

    assert updates == [
        {
            "uid": 0,
            "slot": 0,
            "base": "Prime_TC_Punt",
            "upgraded": "Prime_TC_Punt_B",
        },
        {
            "uid": 1,
            "slot": 0,
            "base": "Ranged_Crack",
            "upgraded": "Ranged_Crack_B",
        },
        {
            "uid": 2,
            "slot": 0,
            "base": "Science_KO_Crack",
            "upgraded": "Science_KO_Crack_A",
        },
    ]
    assert bridge_data["units"][0]["weapons"] == ["Prime_TC_Punt_B"]
    assert bridge_data["units"][1]["weapons"] == ["Ranged_Crack_B"]
    assert bridge_data["units"][2]["weapons"] == ["Science_KO_Crack_A"]


def test_powered_pawn_mods_overlay_when_current_weapons_stay_base(monkeypatch):
    bridge_data = {
        "units": [
            {
                "uid": 1,
                "type": "RocketMech",
                "mech": True,
                "weapons": ["Ranged_Rocket", "Passive_Electric"],
            },
            {
                "uid": 2,
                "type": "PulseMech",
                "mech": True,
                "weapons": ["Science_Repulse"],
            },
        ]
    }

    class FakeState:
        weapons = [
            "Brute_Jetmech",
            "",
            "Ranged_Rocket",
            "Passive_Electric_A",
            "Science_Repulse",
            "",
        ]
        active_mission = SimpleNamespace(pawns=[
            SimpleNamespace(
                pawn_id=1,
                primary_weapon="Ranged_Rocket",
                primary_mod1=[3, 3],
                primary_mod2=[0, 0],
                secondary_weapon="Passive_Electric",
                secondary_mod1=[1, 1, 1],
                secondary_mod2=[0],
            ),
            SimpleNamespace(
                pawn_id=2,
                primary_weapon="Science_Repulse",
                primary_mod1=[3],
                primary_mod2=[0, 0],
                secondary_weapon="",
                secondary_mod1=[],
                secondary_mod2=[],
            ),
        ])

    monkeypatch.setattr(
        "src.loop.commands.load_game_state",
        lambda profile="Alpha": FakeState(),
    )

    updates = _enrich_bridge_mech_weapons_from_save(bridge_data)

    assert updates == [
        {
            "uid": 1,
            "slot": 0,
            "base": "Ranged_Rocket",
            "upgraded": "Ranged_Rocket_A",
        },
        {
            "uid": 2,
            "slot": 0,
            "base": "Science_Repulse",
            "upgraded": "Science_Repulse_A",
        },
    ]
    assert bridge_data["units"][0]["weapons"] == [
        "Ranged_Rocket_A",
        "Passive_Electric",
    ]
    assert bridge_data["units"][1]["weapons"] == ["Science_Repulse_A"]
