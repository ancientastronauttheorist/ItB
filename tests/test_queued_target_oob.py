"""Regression test for the M04 (Old Town) OOB panic — Fix #2 / sim v27.

A Vek at row 7 with a normalized direction of +1 produced a queued_target
of (8, _), which is off the 8x8 grid. The Rust simulator's Melee + catch-all
attack arms cast that to u8 and called Board::tile_mut, panicking with
``index out of bounds: the len is 64 but the index is 69``. Index 69 = 8*8+5,
unambiguously a (x=8, y=5) tile. The same drift caused Python ``board.tile``
IndexErrors in ``get_threatened_buildings`` and ``cmd_read``.

This test reproduces the crash by feeding the solver a JSON input with an
on-board Vek (row 7) and a deliberately off-board ``queued_target`` of
(8, 5). Pre-fix this panicked the Rust simulator. Post-fix the off-board
queued attack is silently skipped (matching the existing phantom-attack
``continue`` style) and the solver returns a valid plan.

The test also exercises the Python ``board.tile`` consumers in
``Board.get_threatened_buildings`` and ``cmd_read``'s telegraphed-attack
scan, since those are reached via ``Board.from_bridge`` when the bridge
delivers an off-board target.
"""

from __future__ import annotations

import json
import sys
import os

# Ensure project root on sys.path for ``src.*`` imports.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import itb_solver
from src.model.board import Board


def _bridge_state_with_oob_queued_target() -> dict:
    """Build a minimal bridge-style state with a Scorpion at row 7 whose
    queued_target points off-board at (8, 5).
    """
    units = [
        # Mech: standard PunchMech at (0, 0) so the solver has something to do.
        {
            "uid": 0, "type": "PunchMech", "x": 0, "y": 0,
            "hp": 3, "max_hp": 3, "team": 1, "mech": True,
            "move": 4, "active": True, "weapons": ["Prime_Punchmech"],
        },
        # Scorpion at row 7 with off-board queued_target — exact M04 shape.
        # Scorpion1 maps to ScorpionAtk1 (WeaponType::Melee), which is the
        # arm where the panic was reproducing.
        {
            "uid": 1, "type": "Scorpion1", "x": 7, "y": 4,
            "hp": 2, "max_hp": 2, "team": 6, "mech": False,
            "move": 3, "active": False, "flying": False,
            "weapons": ["ScorpionAtk1"],
            # Off-board target — the bug's exact failure shape.
            "queued_target": [8, 5],
            "has_queued_attack": True,
        },
    ]
    return {
        "phase": "combat_player",
        "turn": 1,
        "total_turns": 5,
        "grid_power": 5,
        "grid_power_max": 7,
        "tiles": [{"x": 0, "y": 0, "terrain": "building", "building_hp": 1}],
        "units": units,
        "spawning_tiles": [],
        "environment_danger_v2": [],
    }


def test_rust_solve_does_not_panic_on_oob_queued_target():
    """Solver must not panic with an off-board queued_target on the input."""
    state = _bridge_state_with_oob_queued_target()
    # Pre-fix: this raised ``index out of bounds: the len is 64 but the index
    # is 69`` from rust_solver/src/enemy.rs apply_damage path.
    raw = itb_solver.solve(json.dumps(state), 2.0)
    parsed = json.loads(raw)
    # Solve returned, no panic. Plan may be empty (1 mech, off-board threat),
    # but `actions` field must exist.
    assert "actions" in parsed, parsed


def test_python_board_handles_oob_queued_target():
    """Board.from_bridge_data + get_threatened_buildings must not IndexError."""
    state = _bridge_state_with_oob_queued_target()
    board = Board.from_bridge_data(state)
    # Pre-fix: get_threatened_buildings raised IndexError on the OOB target.
    threats = board.get_threatened_buildings()
    # Off-board target → no threat recorded, no exception.
    assert isinstance(threats, list), threats


def test_normalize_queued_targets_nulls_oob():
    """`_normalize_queued_targets` must turn off-board normalized coords
    into ``None`` (or skip them) so downstream consumers never see them.
    """
    from src.bridge.reader import _normalize_queued_targets
    # Patch the save-file origin reader: a clean unit test should not
    # depend on filesystem state.
    import src.bridge.reader as reader_mod
    orig = reader_mod._read_queued_origins_from_save
    try:
        reader_mod._read_queued_origins_from_save = lambda: {1: (7, 4)}
        # Vek at (7,4), origin (7,4), queued raw at (8,4) → ddx=+1, normalized
        # to (cx+1, cy+0) = (8, 4) — off-board, must be cleared.
        units = [{
            "uid": 1, "x": 7, "y": 4, "queued_target": [8, 4],
        }]
        _normalize_queued_targets(units)
        # Either cleared to None, or the key omitted/falsy.
        qt = units[0].get("queued_target")
        assert qt is None, f"expected queued_target cleared, got {qt!r}"
    finally:
        reader_mod._read_queued_origins_from_save = orig


if __name__ == "__main__":
    test_rust_solve_does_not_panic_on_oob_queued_target()
    print("PASS: rust solve no panic on OOB queued_target")
    test_python_board_handles_oob_queued_target()
    print("PASS: python Board.get_threatened_buildings no IndexError")
    test_normalize_queued_targets_nulls_oob()
    print("PASS: _normalize_queued_targets nulls off-board coords")
