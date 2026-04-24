"""Rust-facing weapon override tests.

The Python sim was deleted in PR-C of the simulator-removal series.
The schema/CLI/staging tests + Python parity-overlay tests that lived
here previously assumed Python's `simulate_weapon` was the consumer of
overrides. With Python sim gone, only the Rust-facing assertions matter:
that overrides REACH the Rust solver via `inject_into_bridge` and that
they actually move solver output (score or plan).

The override regression gate (every override has a fixture that proves
it changes solver behaviour) lives in tests/test_weapon_overrides_regression.py.
"""

from __future__ import annotations

import json
import pytest

from src.solver.weapon_overrides import inject_into_bridge


def test_override_changes_solver_plan_or_score():
    """Sanity-check the P3-7 regression gate's core invariant — prove
    that a non-trivial patch actually moves score or changes the plan
    when handed to the Rust solver."""
    itb_solver = pytest.importorskip("itb_solver")
    bd = {
        "grid_power": 7, "turn": 0, "total_turns": 5,
        "tiles": [{"x": x, "y": y, "terrain": "ground"}
                  for x in range(8) for y in range(8)],
        "units": [
            {"uid": 1, "type": "PunchMech", "x": 3, "y": 3,
             "hp": 3, "max_hp": 3, "team": 1, "mech": True,
             "weapons": ["Prime_Punchmech"], "move": 3, "active": True},
            {"uid": 2, "type": "Firefly1", "x": 4, "y": 3,
             "hp": 5, "max_hp": 5, "team": 6,
             "weapons": ["FireflyAtk1"], "queued_target": [3, 3]},
        ],
        "spawning_tiles": [],
    }
    stock = json.loads(itb_solver.solve(json.dumps(bd), 2.0))
    patched_bd = json.loads(json.dumps(bd))
    patched_bd["weapon_overrides"] = [
        {"weapon_id": "Prime_Punchmech", "damage": 99},
    ]
    patched = json.loads(itb_solver.solve(json.dumps(patched_bd), 2.0))
    # applied_overrides asymmetry is the weakest signal; score or plan
    # must also differ, mirroring the P3-7 assertion chain.
    assert stock.get("applied_overrides", []) == []
    assert patched.get("applied_overrides")
    score_moved = abs(patched["score"] - stock["score"]) > 1e-6
    plan_changed = (
        [a["description"] for a in stock["actions"]]
        != [a["description"] for a in patched["actions"]]
    )
    assert score_moved or plan_changed, (
        "99-damage Titan Fist should at minimum change kill count on a "
        "5HP Firefly — if this fires, the overlay isn't threading."
    )


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
