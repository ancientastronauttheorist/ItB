"""Evaluate a board state for the solver.

Scores a board position considering buildings saved, enemies killed,
mech safety, and strategic positioning. Higher is better.

Supports configurable weights via EvalWeights dataclass for
achievement-specific strategy adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from src.model.board import Board


@dataclass
class EvalWeights:
    """Configurable evaluation weights.

    Default values are tuned for general play (protect buildings,
    kill enemies, keep mechs alive). Achievement strategies modify
    specific weights to incentivize achievement-specific behavior.

    Example: "Scorched Earth" achievement → increase enemy_on_fire
    Example: "Unwitting Allies" → increase enemy_pushed_into_enemy
    """
    building_alive: float = 10000
    building_hp: float = 2000
    grid_power: float = 5000
    enemy_killed: float = 500
    enemy_hp_remaining: float = -50
    mech_killed: float = -8000
    mech_hp: float = 100
    mech_centrality: float = -5      # penalizes distance from center
    spawn_blocked: float = 400
    pod_uncollected: float = -100
    pod_proximity: float = 50         # bonus for mech within 2 tiles of pod

    # Achievement-specific (all default 0 — no effect in normal play)
    enemy_on_fire: float = 0          # "This is Fine", "Scorched Earth"
    enemy_pushed_into_enemy: float = 0  # "Unwitting Allies"
    chain_damage: float = 0           # "Chain Attack"
    smoke_placed: float = 0           # "Stormy Weather"
    tiles_frozen: float = 0           # "Cryo Expert"


DEFAULT_WEIGHTS = EvalWeights()


def evaluate(
    board: Board,
    spawn_points: list[tuple[int, int]] = None,
    weights: EvalWeights = None,
    kills: int = 0,
) -> float:
    """Score a board state. Higher = better for the player.

    Called after simulating all mech actions (before enemy attacks).

    Args:
        board: The board state to evaluate.
        spawn_points: Next turn's Vek spawn locations.
        weights: Evaluation weights (uses DEFAULT_WEIGHTS if None).
        kills: Number of enemies killed during simulation. Passed
               explicitly because board.enemies() filters dead units,
               making it impossible to count kills from board state alone.
    """
    w = weights or DEFAULT_WEIGHTS
    score = 0.0

    # --- BUILDINGS (highest priority) ---
    buildings_alive = 0
    total_building_hp = 0
    for x in range(8):
        for y in range(8):
            t = board.tile(x, y)
            if t.terrain == "building" and t.building_hp > 0:
                buildings_alive += 1
                total_building_hp += t.building_hp

    score += buildings_alive * w.building_alive
    score += total_building_hp * w.building_hp

    # --- GRID POWER ---
    score += board.grid_power * w.grid_power

    # --- ENEMIES ---
    # Dead enemies are filtered by board.enemies(), so we use the
    # explicit kills parameter instead of iterating dead units.
    score += kills * w.enemy_killed

    for e in board.enemies():
        score += e.hp * w.enemy_hp_remaining  # remaining HP is bad (negative weight)

    # --- MECHS ---
    mechs = board.mechs()
    for m in mechs:
        if m.hp <= 0:
            score += w.mech_killed  # losing a mech is very bad
        else:
            score += m.hp * w.mech_hp
            # Central positioning is slightly better
            cx = abs(m.x - 3.5)
            cy = abs(m.y - 3.5)
            score += (cx + cy) * w.mech_centrality

    # --- SPAWNS BLOCKED ---
    if spawn_points:
        for sx, sy in spawn_points:
            if board.unit_at(sx, sy) is not None:
                score += w.spawn_blocked

    # --- PODS ---
    for x in range(8):
        for y in range(8):
            if board.tile(x, y).has_pod:
                score += w.pod_uncollected  # negative weight = bad
                # Bonus if mech is nearby
                for m in mechs:
                    dist = abs(m.x - x) + abs(m.y - y)
                    if dist <= 2:
                        score += w.pod_proximity

    return score


def evaluate_threats(board: Board) -> dict:
    """Analyze what threats remain on the board.

    Returns a summary of threatened buildings and unresolved attacks.
    Note: damage values are approximate (TODO: look up actual weapon damage).
    """
    threats = board.get_threatened_buildings()
    enemy_attacks = []
    for u in board.enemies():
        if u.hp > 0 and u.target_x >= 0:
            enemy_attacks.append({
                "enemy": u.type,
                "at": (u.x, u.y),
                "target": (u.target_x, u.target_y),
                "damage": 1,  # TODO: look up actual weapon damage from pawn_stats
            })

    return {
        "threatened_buildings": len(threats),
        "enemy_attacks": len(enemy_attacks),
        "details": enemy_attacks,
    }
