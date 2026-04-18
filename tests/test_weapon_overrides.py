"""P3-3: schema + round-trip tests for the Python override loader.

The loader is the last thing between a curated ``data/weapon_overrides.json``
and the Rust solve. Its job is (a) fail loudly on malformed entries, (b)
strip free-form metadata before it crosses the FFI boundary, and (c) put
base/runtime entries in the right bridge-JSON keys.
"""
from __future__ import annotations

import json
import pytest

from src.solver.weapon_overrides import (
    OverrideSchemaError,
    apply_runtime,
    clear_runtime,
    inject_into_bridge,
    load_base_overrides,
)


def test_load_missing_file_returns_empty(tmp_path):
    assert load_base_overrides(tmp_path / "nope.json") == []


def test_load_strips_free_form_metadata(tmp_path):
    p = tmp_path / "ov.json"
    p.write_text(json.dumps([
        {
            "weapon_id": "Ranged_Defensestrike",
            "damage": 1,
            "note": "Vision disagreed — see mismatches log 2026-04-18",
            "source_mismatch_ts": "2026-04-18T00:46:22+00:00",
            "reviewer": "aircow",
        }
    ]))
    loaded = load_base_overrides(p)
    assert loaded == [{"weapon_id": "Ranged_Defensestrike", "damage": 1}]


def test_load_rejects_unknown_flag_name(tmp_path):
    p = tmp_path / "ov.json"
    p.write_text(json.dumps([
        {"weapon_id": "Prime_Punchmech", "flags_set": ["FIRE", "NOT_A_FLAG"]}
    ]))
    with pytest.raises(OverrideSchemaError, match="unknown flag names"):
        load_base_overrides(p)


def test_load_rejects_entry_with_no_patch(tmp_path):
    p = tmp_path / "ov.json"
    p.write_text(json.dumps([{"weapon_id": "Prime_Punchmech", "note": "x"}]))
    with pytest.raises(OverrideSchemaError, match="no patchable fields"):
        load_base_overrides(p)


def test_load_rejects_non_array_top_level(tmp_path):
    p = tmp_path / "ov.json"
    p.write_text(json.dumps({"weapon_id": "Prime_Punchmech", "damage": 1}))
    with pytest.raises(OverrideSchemaError, match="top-level must be a JSON array"):
        load_base_overrides(p)


def test_inject_splits_base_and_runtime():
    bd: dict = {}
    base = [{"weapon_id": "Prime_Punchmech", "damage": 3}]
    runtime = [{"weapon_id": "Prime_Punchmech", "damage": 99}]
    inject_into_bridge(bd, base=base, runtime=runtime)
    assert bd["weapon_overrides"] == base
    assert bd["weapon_overrides_runtime"] == runtime


def test_inject_empty_leaves_bridge_untouched():
    bd: dict = {}
    inject_into_bridge(bd)
    assert "weapon_overrides" not in bd
    assert "weapon_overrides_runtime" not in bd


def test_python_runtime_overlay_patches_get_weapon_def():
    from src.model.weapons import get_weapon_def
    try:
        stock = get_weapon_def("Prime_Punchmech")
        assert stock.damage == 2 and not stock.fire
        bd = {
            "weapon_overrides": [{"weapon_id": "Prime_Punchmech", "damage": 7}],
            "weapon_overrides_runtime": [
                {"weapon_id": "Prime_Punchmech", "flags_set": ["FIRE"]},
                # Runtime wins the damage field on conflict.
                {"weapon_id": "Prime_Punchmech", "damage": 99},
            ],
        }
        apply_runtime(bd)
        patched = get_weapon_def("Prime_Punchmech")
        assert patched.damage == 99, "runtime layer should win damage"
        assert patched.fire is True, "flag from runtime layer applied"
        # Unrelated weapon untouched.
        assert get_weapon_def("Brute_Tankmech").damage == 1
    finally:
        clear_runtime()
    # Overlay reverts after clear.
    assert get_weapon_def("Prime_Punchmech").damage == 2


def test_python_runtime_overlay_affects_simulate_weapon():
    """End-to-end parity: Python simulate_weapon damage reflects overlay."""
    from src.model.board import Board
    from src.solver.simulate import simulate_weapon

    def _board_with_mech_and_enemy(dmg: int):
        # Build a minimal bridge dict then construct a Board from it.
        bridge = {
            "grid_power": 7, "turn": 0, "total_turns": 5,
            "tiles": [{"x": x, "y": y, "terrain": "ground"}
                      for x in range(8) for y in range(8)],
            "units": [
                {"uid": 1, "type": "PunchMech", "x": 3, "y": 3,
                 "hp": 3, "max_hp": 3, "team": 1, "mech": True,
                 "weapons": ["Prime_Punchmech"], "move": 3, "active": True},
                {"uid": 2, "type": "Firefly1", "x": 4, "y": 3,
                 "hp": 5, "max_hp": 5, "team": 6,
                 "weapons": ["FireflyAtk1"]},
            ],
            "spawning_tiles": [],
        }
        return Board.from_bridge_data(bridge)

    # Stock: Titan Fist does 2 damage → enemy drops from 5 to 3.
    clear_runtime()
    board = _board_with_mech_and_enemy(2)
    mech = next(u for u in board.units if u.uid == 1)
    simulate_weapon(board, mech, "Prime_Punchmech", 4, 3)
    enemy = next(u for u in board.units if u.uid == 2)
    assert enemy.hp == 3, "stock damage baseline"

    # Override damage to 4 → enemy should drop to 1.
    try:
        apply_runtime({"weapon_overrides": [
            {"weapon_id": "Prime_Punchmech", "damage": 4},
        ]})
        board2 = _board_with_mech_and_enemy(4)
        mech2 = next(u for u in board2.units if u.uid == 1)
        simulate_weapon(board2, mech2, "Prime_Punchmech", 4, 3)
        enemy2 = next(u for u in board2.units if u.uid == 2)
        assert enemy2.hp == 1, "overlay damage took effect"
    finally:
        clear_runtime()


def test_inject_round_trip_through_rust_applies_and_audits():
    """End-to-end: loader → inject → itb_solver.solve → applied_overrides."""
    itb_solver = pytest.importorskip("itb_solver")
    bd = {
        "grid_power": 7, "turn": 0, "total_turns": 5,
        "tiles": [{"x": x, "y": y, "terrain": "ground"}
                  for x in range(8) for y in range(8)],
        "units": [
            {"uid": 1, "type": "PunchMech", "x": 3, "y": 3,
             "hp": 3, "max_hp": 3, "team": 1, "mech": True,
             "weapons": ["Prime_Punchmech"], "move": 3, "active": True},
            {"uid": 2, "type": "Firefly1", "x": 5, "y": 3,
             "hp": 2, "max_hp": 2, "team": 6,
             "weapons": ["FireflyAtk1"], "queued_target": [3, 3]},
        ],
        "spawning_tiles": [],
    }
    inject_into_bridge(
        bd,
        base=[{"weapon_id": "Prime_Punchmech", "damage": 5, "note": "dropped"}],
        runtime=[{"weapon_id": "Prime_Punchmech", "flags_set": ["FIRE"]}],
    )
    out = json.loads(itb_solver.solve(json.dumps(bd), 2.0))
    applied = out.get("applied_overrides", [])
    sources = [(e["weapon_id"], e["source"], tuple(e["fields"])) for e in applied]
    assert ("Prime_Punchmech", "base", ("damage",)) in sources
    assert ("Prime_Punchmech", "runtime", ("flags_set",)) in sources
