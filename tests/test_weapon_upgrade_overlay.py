from src.loop.commands import _enrich_bridge_mech_weapons_from_save


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
