"""Phantom-attack guard test (Rust sim).

When a Vek reports has_queued_attack=true but the Lua bridge failed to
populate queued_target_x/y (sentinel -1, -1), the enemy-phase simulator
used to silently skip the attack — treating the Vek as a non-combatant.
That masked a run-ending HornetBoss misjudgment.

The guard in `simulate_enemy_attacks` (Rust) now applies a
deterministic conservative damage estimate to the nearest building
instead of silently skipping. This test locks that behaviour in.

(The Python sim's parallel `_simulate_enemy_attacks` guard was removed
along with the Python sim in the simulate.py-removal PR series. The
Rust guard is the live one.)
"""
from __future__ import annotations

import json
import itb_solver


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
