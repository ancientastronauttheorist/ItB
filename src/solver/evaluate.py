"""Evaluate a board state for the solver.

Scores a board position considering buildings saved, enemies killed,
mech safety, and strategic positioning. Higher is better.
"""

from __future__ import annotations

from src.model.board import Board


def evaluate(board: Board, spawn_points: list[tuple[int, int]] = None) -> float:
    """Score a board state. Higher = better for the player.

    Called after simulating all 3 mech actions + enemy attacks.
    """
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

    score += buildings_alive * 10000
    score += total_building_hp * 2000

    # --- GRID POWER ---
    score += board.grid_power * 5000

    # --- ENEMIES ---
    enemies = board.enemies()
    for e in enemies:
        if e.hp <= 0:
            score += 500  # killed enemy
        else:
            score -= e.hp * 50  # remaining enemy HP is bad

    # --- MECHS ---
    mechs = board.mechs()
    for m in mechs:
        if m.hp <= 0:
            score -= 8000  # losing a mech is very bad
        else:
            score += m.hp * 100  # mech HP is good
            # Central positioning is slightly better
            cx = abs(m.x - 3.5)
            cy = abs(m.y - 3.5)
            score -= (cx + cy) * 5

    # --- SPAWNS BLOCKED ---
    if spawn_points:
        for sx, sy in spawn_points:
            if board.unit_at(sx, sy) is not None:
                score += 400  # blocking a spawn is good

    # --- PODS ---
    for x in range(8):
        for y in range(8):
            if board.tile(x, y).has_pod:
                score -= 100  # uncollected pod is slightly bad
                # Bonus if mech is adjacent
                for m in mechs:
                    dist = abs(m.x - x) + abs(m.y - y)
                    if dist <= 2:
                        score += 50

    return score


def evaluate_threats(board: Board) -> dict:
    """Analyze what threats remain on the board.

    Returns a summary of threatened buildings and unresolved attacks.
    """
    threats = board.get_threatened_buildings()
    enemy_attacks = []
    for u in board.enemies():
        if u.hp > 0 and u.target_x >= 0:
            enemy_attacks.append({
                "enemy": u.type,
                "at": (u.x, u.y),
                "target": (u.target_x, u.target_y),
                "damage": 1,  # TODO: look up actual weapon damage
            })

    return {
        "threatened_buildings": len(threats),
        "enemy_attacks": len(enemy_attacks),
        "details": enemy_attacks,
    }
