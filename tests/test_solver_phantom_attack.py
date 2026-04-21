"""Phantom-attack guard tests.

When a Vek reports has_queued_attack=true but the Lua bridge failed to
populate queued_target_x/y (sentinel -1, -1), the enemy-phase simulator
used to silently skip the attack — treating the Vek as a non-combatant.
That masked a run-ending HornetBoss misjudgment.

The guard in `_simulate_enemy_attacks` (Python) and
`simulate_enemy_attacks` (Rust via itb_solver) now applies a
deterministic conservative damage estimate to the nearest building
instead of silently skipping. These tests lock that behaviour in.
"""
from __future__ import annotations

import json

import itb_solver

from src.model.board import Board, BoardTile, Unit
from src.solver.solver import _simulate_enemy_attacks


def _make_unit(**kwargs) -> Unit:
    """Minimal Unit with safe defaults; overrides from kwargs."""
    defaults = dict(
        uid=0, type="Scorpion1", x=0, y=0, hp=2, max_hp=2, team=6,
        is_mech=False, move_speed=3, flying=False, massive=False,
        armor=False, pushable=True, weapon="Scorpion1Atk1", weapon2="",
        active=True, base_move=3, shield=False, acid=False, frozen=False,
        fire=False, web=False, web_source_uid=-1, target_x=-1, target_y=-1,
        queued_target_x=-1, queued_target_y=-1, weapon_damage=2,
        weapon_target_behind=False, weapon_push=0, is_extra_tile=False,
        pilot_id="", pilot_value=0.0, has_queued_attack=False,
    )
    defaults.update(kwargs)
    return Unit(**defaults)


def _bare_board(building_at=(0, 0), building_hp=1, grid_power=5) -> Board:
    b = Board()
    bx, by = building_at
    b.tiles[bx][by] = BoardTile(terrain="building", building_hp=building_hp)
    b.grid_power = grid_power
    b.grid_power_max = 7
    return b


# ── Python sim ───────────────────────────────────────────────────────────────

def test_python_phantom_attack_damages_nearest_building():
    """has_queued_attack=true + no target must NOT silently skip."""
    board = _bare_board(building_at=(0, 0), building_hp=1, grid_power=5)
    vek = _make_unit(
        uid=42, type="HornetBoss", x=4, y=4,
        queued_target_x=-1, queued_target_y=-1,
        has_queued_attack=True, weapon_damage=2,
    )
    board.units.append(vek)

    buildings_destroyed = _simulate_enemy_attacks(board, original_positions={})

    # Conservative fallback: nearest building at (0,0) with HP=1 is destroyed.
    assert buildings_destroyed >= 1, (
        "Phantom attack should damage the nearest building, not silently skip"
    )
    assert board.tile(0, 0).building_hp == 0
    assert board.grid_power < 5, "Grid power must drop when a building is destroyed"


def test_python_phantom_attack_without_flag_still_skips():
    """has_queued_attack=false + no target => genuine non-combatant, skip."""
    board = _bare_board(building_at=(0, 0), building_hp=1, grid_power=5)
    vek = _make_unit(
        uid=42, type="Scorpion1", x=4, y=4,
        queued_target_x=-1, queued_target_y=-1,
        has_queued_attack=False, weapon_damage=2,
    )
    board.units.append(vek)

    buildings_destroyed = _simulate_enemy_attacks(board, original_positions={})

    assert buildings_destroyed == 0
    assert board.tile(0, 0).building_hp == 1
    assert board.grid_power == 5


# ── Rust sim (via itb_solver.solve) ──────────────────────────────────────────

def _rust_solve(board_dict: dict) -> dict:
    return json.loads(itb_solver.solve(json.dumps(board_dict), 2.0))


def _make_rust_board(has_queued_attack: bool) -> dict:
    return {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "tiles": [
            {"x": 0, "y": 0, "terrain": "building", "building_hp": 1},
        ],
        "units": [
            {
                "uid": 0, "type": "PunchMech", "x": 7, "y": 7,
                "hp": 3, "max_hp": 3, "team": 1, "mech": True,
                "move": 0, "active": True, "weapons": ["Prime_Punchmech"],
            },
            {
                "uid": 42, "type": "HornetBoss", "x": 4, "y": 4,
                "hp": 3, "max_hp": 3, "team": 6, "mech": False,
                "move": 3, "active": False,
                "weapons": ["HornetBossAtk1"],
                "queued_target": [-1, -1],
                "has_queued_attack": has_queued_attack,
                "weapon_damage": 2,
            },
        ],
        "spawning_tiles": [],
    }


def test_rust_phantom_attack_penalizes_score():
    """Rust solver must score the phantom-attack case WORSE than the
    same board with has_queued_attack=false (genuine non-combatant).

    With the guard: has_queued_attack=true → conservative damage to
    nearest building → grid_power drops → lower score.
    Without the flag: silent skip → building untouched → higher score.
    """
    with_flag = _rust_solve(_make_rust_board(has_queued_attack=True))
    no_flag = _rust_solve(_make_rust_board(has_queued_attack=False))

    score_with = with_flag["score"]
    score_without = no_flag["score"]

    assert score_with < score_without, (
        f"Phantom-attack guard must penalize score: "
        f"with_flag={score_with} vs no_flag={score_without}. "
        f"If they are equal, the guard silently skipped the attack."
    )
