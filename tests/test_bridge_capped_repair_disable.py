from src.loop import commands
from src.loop.session import RunSession


def test_bridge_capped_repair_disable_flags_raw_cap_heal_gap():
    bridge_data = {
        "mech_stat_overlays": [
            {"uid": 2, "bridge_max_hp": 2, "save_max_hp": 4},
        ],
        "units": [
            {"uid": 2, "hp": 2, "max_hp": 4, "mech": True},
        ],
    }

    reasons = commands._bridge_capped_repair_disable_reasons(bridge_data)

    assert reasons == ["uid=2:hp=2:bridge_max=2:save_max=4"]


def test_bridge_capped_repair_disable_keeps_status_repairs_available():
    bridge_data = {
        "mech_stat_overlays": [
            {"uid": 2, "bridge_max_hp": 2, "save_max_hp": 4},
        ],
        "units": [
            {"uid": 2, "hp": 2, "max_hp": 4, "mech": True, "acid": True},
        ],
    }

    assert commands._bridge_capped_repair_disable_reasons(bridge_data) == []


def test_maybe_disable_bridge_capped_repair_adds_single_repair_block():
    session = RunSession()
    bridge_data = {
        "mech_stat_overlays": [
            {"uid": 1, "bridge_max_hp": 3, "save_max_hp": 5},
        ],
        "units": [
            {"uid": 1, "hp": 3, "max_hp": 5, "mech": True},
        ],
    }

    assert commands._maybe_disable_bridge_capped_repair(session, bridge_data, turn=1)
    assert session.disabled_actions == [
        {
            "weapon_id": "_REPAIR",
            "cause_pattern": "bridge_repair_cap:uid=1:hp=3:bridge_max=3:save_max=5",
            "expires_turn": 100,
            "strategic_override": True,
        }
    ]
    assert not commands._maybe_disable_bridge_capped_repair(session, bridge_data, turn=2)
    assert session.disabled_actions[0]["expires_turn"] == 101
