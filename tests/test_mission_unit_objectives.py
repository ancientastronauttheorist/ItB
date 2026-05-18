"""Tests for unit-based mission objectives."""
from __future__ import annotations

import json
from pathlib import Path

from src.solver.mission_unit_objectives import (
    inject_into_bridge,
    load_mission_map,
    resolve_unit_objectives,
)


def test_mission_hacking_declares_destroy_and_protect_units():
    resolved = resolve_unit_objectives("Mission_Hacking")
    assert resolved["destroy"] == ["Hacked_Building"]
    assert "Snowtank1" in resolved["protect"]
    assert "Snowtank1_Player" in resolved["protect"]


def test_mission_freezebots_protects_robot_units():
    resolved = resolve_unit_objectives("Mission_FreezeBots")
    assert resolved["destroy"] == []
    assert resolved["protect"] == ["Snowtank", "Snowlaser"]


def test_mission_bomb_protects_proto_bombs():
    resolved = resolve_unit_objectives("Mission_Bomb")
    assert resolved["destroy"] == []
    assert resolved["protect"] == ["ProtoBomb"]


def test_train_missions_protect_train_units():
    assert resolve_unit_objectives("Mission_Train")["protect"] == ["Train"]
    assert resolve_unit_objectives("Mission_Armored_Train")["protect"] == ["Train"]


def test_mission_terraform_protects_terraformer():
    resolved = resolve_unit_objectives("Mission_Terraform")
    assert resolved["destroy"] == []
    assert resolved["protect"] == ["Terraformer"]


def test_mission_civilians_protects_vip_trucks():
    resolved = resolve_unit_objectives("Mission_Civilians")
    assert resolved["destroy"] == []
    assert resolved["protect"] == ["VIP_Truck"]


def test_mission_power_tracks_bonus_debris_when_present():
    resolved = resolve_unit_objectives("Mission_Power")
    assert resolved["destroy"] == ["BonusDebris"]
    assert resolved["protect"] == []


def test_mission_volatile_protects_volatile_vek():
    resolved = resolve_unit_objectives("Mission_Volatile")
    assert resolved["destroy"] == []
    assert "GlowingScorpion" in resolved["protect"]
    assert "Volatile_Vek" in resolved["protect"]


def test_boss_missions_destroy_the_leader_units():
    cases = {
        "Mission_BeetleBoss": "BeetleBoss",
        "Mission_BlobBoss": "BlobBoss",
        "Mission_BotBoss": "BotBoss",
        "Mission_FireflyBoss": "FireflyBoss",
        "Mission_HornetBoss": "HornetBoss",
        "Mission_JellyBoss": "Jelly_Boss",
        "Mission_ScorpionBoss": "ScorpionBoss",
        "Mission_SlugBoss": "SlugBoss",
        "Mission_SpiderBoss": "SpiderBoss",
    }
    for mission_id, pawn_type in cases.items():
        resolved = resolve_unit_objectives(mission_id)
        assert resolved["destroy"] == [pawn_type]
        assert resolved["protect"] == []


def test_unknown_mission_resolves_empty_lists():
    assert resolve_unit_objectives("Mission_NoSuch") == {
        "destroy": [],
        "protect": [],
    }


def test_bridge_values_take_precedence_independently():
    resolved = resolve_unit_objectives(
        "Mission_Hacking",
        bridge_destroy_existing=["Lua_Destroy"],
        bridge_protect_existing=["Lua_Protect"],
    )
    assert resolved == {
        "destroy": ["Lua_Destroy"],
        "protect": ["Lua_Protect"],
    }


def test_inject_into_bridge_writes_solver_fields():
    bd = {"mission_id": "Mission_Hacking"}
    inject_into_bridge(bd)
    assert bd["destroy_objective_unit_types"] == ["Hacked_Building"]
    assert "Snowtank1" in bd["protect_objective_unit_types"]


def test_load_mission_map_drops_bad_entries(tmp_path: Path):
    f = tmp_path / "unit_objectives.json"
    f.write_text(json.dumps({
        "_comment": "ignored",
        "Mission_OK": {"destroy": ["A"], "protect": ["B"]},
        "Mission_Empty": {"destroy": [], "protect": []},
        "Mission_Bad": ["not", "a", "dict"],
        "Mission_NonStrings": {"destroy": [1, None], "protect": ["C"]},
    }))
    assert load_mission_map(f) == {
        "Mission_OK": {"destroy": ["A"], "protect": ["B"]},
        "Mission_NonStrings": {"destroy": [], "protect": ["C"]},
    }
