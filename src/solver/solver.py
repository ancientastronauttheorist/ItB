"""Solver data types (MechAction, Solution) and replay wrapper.

The actual search is performed by the Rust solver (itb_solver module).
This module provides:
  - MechAction / Solution dataclasses used across the codebase
  - replay_solution() — thin Python wrapper around itb_solver.replay_solution
    that adds the Python-side evaluate_breakdown for audit logs

The full Python combat simulator (src/solver/simulate.py) and the
enemy-phase Python helpers (_simulate_env_effects, _simulate_enemy_attacks,
_apply_spawn_blocking, _simulate_train_advance, _find_projectile_target,
etc.) were deleted in the simulate.py-removal PR series. Rust is the
only simulator now; replay_solution round-trips bridge JSON through it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.model.board import Board
from src.solver.evaluate import evaluate_breakdown


@dataclass
class MechAction:
    """A single mech's action: move somewhere, then attack."""
    mech_uid: int
    mech_type: str
    move_to: tuple[int, int]
    weapon: str
    target: tuple[int, int]
    description: str = ""


@dataclass
class Solution:
    """A complete turn solution (sequence of mech actions)."""
    actions: list[MechAction] = field(default_factory=list)
    score: float = float('-inf')
    buildings_saved: int = 0
    enemies_killed: int = 0
    mech_damage: int = 0
    # Search statistics
    elapsed_seconds: float = 0.0
    timed_out: bool = False
    permutations_tried: int = 0
    total_permutations: int = 0
    active_mech_count: int = 0



# ── Post-solve replay (verification snapshots) ──────────────────────────


def replay_solution(
    bridge_data: dict,
    solution: Solution,
    spawn_pts: list[tuple[int, int]],
    current_turn: int = 0,
    total_turns: int = 5,
    remaining_spawns: int = 2**31 - 1,
    weights=None,
) -> dict:
    """Re-simulate the best solution to capture detailed per-action data.

    Thin wrapper over `itb_solver.replay_solution` (Rust). Called ONCE
    after solve_turn() with the original (unmutated) bridge JSON dict.
    Returns enriched data: per-action ActionResult dicts, per-action
    board snapshots (for the verify loop), predicted post-enemy board
    summary, and score component breakdown.

    The Rust backend produces every field except `score_breakdown` —
    that runs on the Python side via `evaluate_breakdown()` because the
    evaluator owns weight/threat/psion machinery that hasn't moved to
    Rust yet (audit-only output, no programmatic consumer).
    """
    import itb_solver
    import json as _json

    # Build plan_json. Rust expects {mech_uid, move_to:[x,y], weapon_id,
    # target:[x,y]}. action.weapon already holds the weapon_id string
    # (e.g. "Prime_Punchmech"); wid_from_str maps unknowns to WId::None.
    # move_to can be None on synthetic actions — treat as "stay put" by
    # falling back to the mech's current position from bridge_data.
    bridge_units_by_uid = {
        int(u["uid"]): (int(u["x"]), int(u["y"]))
        for u in (bridge_data.get("units") or [])
    }
    plan = []
    for a in solution.actions:
        mt = a.move_to
        if mt is None:
            mt = bridge_units_by_uid.get(int(a.mech_uid), (0, 0))
        target = a.target if a.target is not None else (255, 255)
        plan.append({
            "mech_uid":  int(a.mech_uid),
            "move_to":   [int(mt[0]), int(mt[1])],
            "weapon_id": a.weapon or "None",
            "target":    [int(target[0]), int(target[1])],
        })

    raw = itb_solver.replay_solution(_json.dumps(bridge_data), _json.dumps(plan))
    data = _json.loads(raw)

    # Round-trip the post-enemy board so evaluate_breakdown has a real
    # Board to score (its weight/threat/psion logic runs on Python types).
    final_board_data = data.get("final_board") or {}
    final_board = Board.from_bridge_data(final_board_data)
    total_kills = sum(int(r.get("enemies_killed", 0)) for r in data.get("action_results", []))
    score_breakdown = evaluate_breakdown(
        final_board, spawn_pts, kills=total_kills,
        current_turn=current_turn,
        total_turns=total_turns,
        remaining_spawns=remaining_spawns,
        weights=weights,
    )

    return {
        "action_results":   data.get("action_results") or [],
        "predicted_states": data.get("predicted_states") or [],
        "predicted_outcome": data.get("predicted_outcome") or {},
        "score_breakdown":  score_breakdown,
    }


