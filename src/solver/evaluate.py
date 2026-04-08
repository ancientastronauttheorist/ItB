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

    # Environment hazard awareness
    enemy_on_danger: float = 400      # non-flying enemy on danger tile (near-certain kill)

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

    # --- GRID POWER URGENCY ---
    # When grid power is critically low, building protection becomes
    # exponentially more important. Every building hit could end the run.
    grid_multiplier = 1.0
    if board.grid_power <= 1:
        grid_multiplier = 5.0   # one hit from game over
    elif board.grid_power <= 2:
        grid_multiplier = 3.0   # very critical
    elif board.grid_power <= 3:
        grid_multiplier = 2.0   # elevated danger

    # --- BUILDINGS (highest priority, scaled by urgency) ---
    buildings_alive = 0
    total_building_hp = 0
    for x in range(8):
        for y in range(8):
            t = board.tile(x, y)
            if t.terrain == "building" and t.building_hp > 0:
                buildings_alive += 1
                total_building_hp += t.building_hp

    score += buildings_alive * w.building_alive * grid_multiplier
    score += total_building_hp * w.building_hp * grid_multiplier

    # --- GRID POWER ---
    score += board.grid_power * w.grid_power

    # --- ENEMIES ---
    # Dead enemies are filtered by board.enemies(), so we use the
    # explicit kills parameter instead of iterating dead units.
    score += kills * w.enemy_killed

    for e in board.enemies():
        score += e.hp * w.enemy_hp_remaining  # remaining HP is bad (negative weight)

    # --- ENVIRONMENT DANGER ---
    # Non-flying enemies on danger tiles will die when environment resolves
    # (tidal wave floods, air strike lands). Treat as near-certain kills.
    # Non-flying mechs on danger tiles is very bad (mech will die too).
    if hasattr(board, 'environment_danger') and board.environment_danger:
        for e in board.enemies():
            if (e.x, e.y) in board.environment_danger and not e.flying:
                score += w.enemy_on_danger
        for m in board.mechs():
            if m.hp > 0 and (m.x, m.y) in board.environment_danger and not m.flying:
                score += w.mech_killed  # reuse mech_killed penalty (very harsh)

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


def evaluate_breakdown(
    board: Board,
    spawn_points: list[tuple[int, int]] = None,
    weights: EvalWeights = None,
    kills: int = 0,
) -> dict:
    """Score a board state and return per-component breakdown.

    Same logic as evaluate(), but returns a dict with each scoring
    component separated. Only call on the final solution (not during
    search) since it builds a dict instead of a bare float.
    """
    w = weights or DEFAULT_WEIGHTS

    # --- GRID POWER URGENCY ---
    grid_multiplier = 1.0
    if board.grid_power <= 1:
        grid_multiplier = 5.0
    elif board.grid_power <= 2:
        grid_multiplier = 3.0
    elif board.grid_power <= 3:
        grid_multiplier = 2.0

    # --- BUILDINGS ---
    buildings_alive = 0
    total_building_hp = 0
    for x in range(8):
        for y in range(8):
            t = board.tile(x, y)
            if t.terrain == "building" and t.building_hp > 0:
                buildings_alive += 1
                total_building_hp += t.building_hp

    buildings_score = buildings_alive * w.building_alive * grid_multiplier
    building_hp_score = total_building_hp * w.building_hp * grid_multiplier

    # --- GRID POWER ---
    grid_power_score = board.grid_power * w.grid_power

    # --- ENEMIES ---
    enemies_killed_score = kills * w.enemy_killed

    enemy_hp_total = 0
    for e in board.enemies():
        enemy_hp_total += e.hp
    enemy_hp_score = enemy_hp_total * w.enemy_hp_remaining

    # --- ENVIRONMENT DANGER ---
    danger_enemies_on = 0
    danger_mechs_on = 0
    danger_score = 0.0
    if hasattr(board, 'environment_danger') and board.environment_danger:
        for e in board.enemies():
            if (e.x, e.y) in board.environment_danger and not e.flying:
                danger_enemies_on += 1
                danger_score += w.enemy_on_danger
        for m in board.mechs():
            if m.hp > 0 and (m.x, m.y) in board.environment_danger and not m.flying:
                danger_mechs_on += 1
                danger_score += w.mech_killed

    # --- MECHS ---
    mechs = board.mechs()
    mechs_alive = 0
    mechs_dead = 0
    total_mech_hp = 0
    mech_score = 0.0
    for m in mechs:
        if m.hp <= 0:
            mechs_dead += 1
            mech_score += w.mech_killed
        else:
            mechs_alive += 1
            total_mech_hp += m.hp
            mech_score += m.hp * w.mech_hp
            cx = abs(m.x - 3.5)
            cy = abs(m.y - 3.5)
            mech_score += (cx + cy) * w.mech_centrality

    # --- SPAWNS BLOCKED ---
    spawns_blocked = 0
    if spawn_points:
        for sx, sy in spawn_points:
            if board.unit_at(sx, sy) is not None:
                spawns_blocked += 1
    spawns_score = spawns_blocked * w.spawn_blocked

    # --- PODS ---
    pods_uncollected = 0
    pods_proximity = 0
    pods_score = 0.0
    for x in range(8):
        for y in range(8):
            if board.tile(x, y).has_pod:
                pods_uncollected += 1
                pods_score += w.pod_uncollected
                for m in mechs:
                    dist = abs(m.x - x) + abs(m.y - y)
                    if dist <= 2:
                        pods_proximity += 1
                        pods_score += w.pod_proximity

    total = (buildings_score + building_hp_score + grid_power_score
             + enemies_killed_score + enemy_hp_score + danger_score
             + mech_score + spawns_score + pods_score)

    # Sanity check: must match evaluate()
    expected = evaluate(board, spawn_points, weights, kills)
    assert abs(total - expected) < 0.01, (
        f"evaluate_breakdown total {total} != evaluate() {expected}"
    )

    return {
        "total": total,
        "grid_multiplier": grid_multiplier,
        "buildings_alive": {"count": buildings_alive, "score": buildings_score},
        "building_hp": {"total": total_building_hp, "score": building_hp_score},
        "grid_power": {"value": board.grid_power, "score": grid_power_score},
        "enemies_killed": {"count": kills, "score": enemies_killed_score},
        "enemy_hp_remaining": {"total": enemy_hp_total, "score": enemy_hp_score},
        "environment_danger": {
            "enemies_on": danger_enemies_on,
            "mechs_on": danger_mechs_on,
            "score": danger_score,
        },
        "mechs": {
            "alive": mechs_alive,
            "dead": mechs_dead,
            "total_hp": total_mech_hp,
            "score": mech_score,
        },
        "spawns_blocked": {"count": spawns_blocked, "score": spawns_score},
        "pods": {
            "uncollected": pods_uncollected,
            "proximity": pods_proximity,
            "score": pods_score,
        },
    }


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
