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
