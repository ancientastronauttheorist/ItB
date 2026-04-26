"""Tests for the mission-aware 'do not kill X' bonus-objective resolver.

Sim v21 changed the `volatile_enemy_killed` penalty from unconditional
(every Volatile_Vek/GlowingScorpion kill) to mission-aware (only when
the active mission lists the type in its BonusObjs). The resolver pulls
the protected-type list from `data/mission_bonus_objectives.json` keyed
by mission_id, with a future Lua-bridge precedence path already wired.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.solver.mission_bonus_objectives import (
    inject_into_bridge,
    load_mission_map,
    resolve_bonus_types,
)


def test_resolve_known_mission_returns_protected_types():
    types = resolve_bonus_types("Mission_VolatileMine")
    # The shipping JSON file maps Mission_VolatileMine to Volatile / Scorpion
    # variants; we don't assert exact equality so adding more entries to
    # the file doesn't churn this test, only that the canonical type is
    # present.
    assert "GlowingScorpion" in types or "Volatile_Vek" in types, (
        f"expected GlowingScorpion / Volatile_Vek in protected types, got {types}"
    )


def test_resolve_unknown_mission_returns_empty():
    assert resolve_bonus_types("Mission_DoesNotExist") == []


def test_resolve_empty_mission_id_returns_empty():
    assert resolve_bonus_types("") == []


def test_resolve_bridge_value_takes_precedence(tmp_path: Path):
    # If the Lua bridge ever populates bonus_objective_unit_types directly,
    # the resolver must honor that over the JSON file.
    out = resolve_bonus_types(
        "Mission_VolatileMine",
        bridge_data_existing=["Custom_Vek"],
    )
    assert out == ["Custom_Vek"], (
        "Lua-side population must take precedence over the JSON map"
    )


def test_inject_into_bridge_writes_field():
    bd = {"mission_id": "Mission_VolatileMine"}
    inject_into_bridge(bd)
    assert "bonus_objective_unit_types" in bd
    assert isinstance(bd["bonus_objective_unit_types"], list)


def test_inject_unknown_mission_writes_empty_list():
    bd = {"mission_id": "Mission_Unknown"}
    inject_into_bridge(bd)
    # Must always set the key (Rust deserializer reads it as Option<Vec<_>>;
    # an empty list is correct and means "no protection").
    assert bd["bonus_objective_unit_types"] == []


def test_inject_no_mission_id_writes_empty_list():
    bd = {}
    inject_into_bridge(bd)
    assert bd["bonus_objective_unit_types"] == []


def test_inject_idempotent_on_existing_value():
    bd = {
        "mission_id": "Mission_VolatileMine",
        "bonus_objective_unit_types": ["Lua_Provided"],
    }
    inject_into_bridge(bd)
    assert bd["bonus_objective_unit_types"] == ["Lua_Provided"]


def test_load_mission_map_skips_metadata_keys(tmp_path: Path):
    # Underscore-prefixed keys in the JSON file are comments and must
    # not appear in the returned map.
    f = tmp_path / "test_map.json"
    f.write_text(json.dumps({
        "_comment": "skipped",
        "_format": {"...": "..."},
        "Mission_X": ["Volatile_Vek"],
    }))
    m = load_mission_map(f)
    assert m == {"Mission_X": ["Volatile_Vek"]}


def test_load_mission_map_drops_malformed_entries(tmp_path: Path):
    # A bad entry shouldn't break the loader — it just gets skipped.
    f = tmp_path / "bad.json"
    f.write_text(json.dumps({
        "Mission_OK": ["Type1"],
        "Mission_BadValue": "not_a_list",
        "Mission_EmptyList": [],
        "Mission_NonStringEntries": [42, None],
    }))
    m = load_mission_map(f)
    assert m == {"Mission_OK": ["Type1"]}


def test_load_mission_map_missing_file_returns_empty(tmp_path: Path):
    f = tmp_path / "missing.json"
    assert load_mission_map(f) == {}
