"""Solver data types (MechAction, Solution) and replay infrastructure.

The actual search is performed by the Rust solver (itb_solver module).
This module provides:
  - MechAction / Solution dataclasses used across the codebase
  - replay_solution() for post-solve verification snapshots
  - Enemy attack simulation for replay predictions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.model.board import Board, Unit
from src.model.weapons import get_weapon_def
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


# ── Enemy attack simulation (used by replay_solution) ────────────────────






# --- Enemy Attack Simulation ---

def _find_projectile_target(board: Board, enemy: Unit,
                            orig_x: int = -1, orig_y: int = -1) -> tuple[int, int]:
    """Trace a projectile from enemy position in queued direction.

    Uses the ORIGINAL position (before mech pushes) to compute the cardinal
    attack direction, then traces from the CURRENT position. This correctly
    handles pushed enemies: their attack direction is preserved from the
    original position, not recomputed from the new position.

    Returns (hit_x, hit_y) of first unit/mountain/building, or (-1, -1).
    """
    if enemy.queued_target_x < 0:
        return -1, -1

    # Compute direction from ORIGINAL position to queued target
    ox = orig_x if orig_x >= 0 else enemy.x
    oy = orig_y if orig_y >= 0 else enemy.y
    dx = enemy.queued_target_x - ox
    dy = enemy.queued_target_y - oy
    # Normalize to unit direction
    if dx != 0:
        dx = 1 if dx > 0 else -1
    if dy != 0:
        dy = 1 if dy > 0 else -1

    # Must be a valid cardinal direction (exactly one axis non-zero)
    if (dx != 0 and dy != 0) or (dx == 0 and dy == 0):
        return -1, -1

    # Trace from CURRENT position in the original direction
    for i in range(1, 8):
        nx, ny = enemy.x + dx * i, enemy.y + dy * i
        if not board.in_bounds(nx, ny):
            break
        tile = board.tile(nx, ny)
        if tile.terrain == "mountain":
            return nx, ny
        if tile.terrain == "building" and tile.building_hp > 0:
            return nx, ny
        unit = board.unit_at(nx, ny)
        if unit is not None:
            return nx, ny
    return -1, -1


def _apply_enemy_hit(board: Board, x: int, y: int, damage: int) -> int:
    """Apply one enemy hit to a tile. Returns grid power lost."""
    if not board.in_bounds(x, y):
        return 0
    unit = board.unit_at(x, y)
    if unit is not None and unit.is_player:
        unit.hp -= damage
        if unit.hp < 0:
            unit.hp = 0
        return 0  # mech absorbs hit, no grid damage

    tile = board.tile(x, y)
    if tile.terrain == "building" and tile.building_hp > 0:
        grid_lost = tile.building_hp  # ALL buildings destroyed (all-or-nothing)
        tile.building_hp = 0
        tile.terrain = "rubble"
        board.grid_power = max(0, board.grid_power - grid_lost)
        return grid_lost
    return 0


def _apply_enemy_weapon_status(board: Board, x: int, y: int,
                               wdef, attacker_uid: int) -> None:
    """Apply enemy weapon status effects (acid, web) to whatever is at (x, y).

    Mirrors rust_solver apply_weapon_status for the enemy-attack paths.
    Shield blocks negative status without being consumed here — the shield
    consumption path is in apply_damage. Enemy weapons with acid or web
    that hit a dead unit still skip (no ghost statuses).
    """
    if wdef is None:
        return
    unit = board.unit_at(x, y)
    if unit is None or unit.hp <= 0:
        return
    if unit.shield:
        return
    if getattr(wdef, 'acid', False):
        unit.acid = True
    if getattr(wdef, 'web', False):
        unit.web = True
        unit.web_source_uid = attacker_uid


def _simulate_env_effects(board: Board):
    """Simulate end-of-turn environment effects on units/tiles.

    Called BEFORE enemy attacks (matching the game's interleaved order).
    Uses environment_danger_v2 for per-tile lethality and env_type for
    effect type (freeze for snow, smoke for sandstorm, etc.).
    """
    v2 = getattr(board, 'environment_danger_v2', {})
    env_type = getattr(board, 'env_type', 'unknown')

    for (dx, dy), (dmg, lethal) in v2.items():
        if not board.in_bounds(dx, dy):
            continue
        u = board.unit_at(dx, dy)

        if lethal:
            # Lethal env: kill ground units (bypass shield/frozen/armor)
            if u and not u.flying:
                u.hp = 0
        elif env_type == "snow":
            # Ice Storm: freeze non-flying units (shield blocks freeze)
            if u and not u.flying and not u.shield:
                u.frozen = True
        elif env_type == "sandstorm":
            # Sandstorm: add smoke to tile
            board.tile(dx, dy).smoke = True
        # Wind (push) is too complex to simulate here — skip


def _apply_spawn_blocking(board: Board, spawn_points: list) -> None:
    """Units standing on spawn tiles take 1 damage when Vek try to emerge.
    Bypasses armor and ACID (bump-like damage) but is consumed by shield.
    Fires AFTER enemy attacks, BEFORE the next player turn.
    Mirrors rust_solver/src/enemy.rs::apply_spawn_blocking.
    """
    for sx, sy in spawn_points:
        unit = board.unit_at(sx, sy)
        if unit is None or unit.hp <= 0:
            continue
        if unit.shield:
            unit.shield = False
        elif unit.frozen:
            unit.frozen = False
        else:
            unit.hp -= 1


def _simulate_enemy_attacks(board: Board, original_positions: dict) -> int:
    """Simulate all enemy attacks on the post-mech-action board.

    Processes enemies in UID order (ascending = attack order).
    Re-computes projectile paths on the post-mech board state.
    Handles melee TargetBehind (Alpha Hornet behind-tile hit).
    Skips dead enemies and melee enemies pushed out of range.

    Args:
        board: Board state after mech actions (WILL BE MUTATED).
        original_positions: {enemy_uid: (orig_x, orig_y)} from before
            mech actions, used to detect pushed melee enemies.

    Returns:
        Number of buildings destroyed.
    """
    buildings_destroyed = 0

    # Fire damage tick: burning units take 1 damage BEFORE attacks resolve.
    # A burning 1 HP Vek dies before it can attack. Fire ignores Armor/ACID.
    for u in board.units:
        if u.fire and u.hp > 0:
            u.hp -= 1
            # Fire does NOT damage buildings (buildings are immune to fire)

    # Process in UID order (ascending = game's attack order)
    enemies = sorted(board.enemies(), key=lambda e: e.uid)

    for enemy in enemies:
        if enemy.hp <= 0:
            continue
        if enemy.queued_target_x < 0:
            continue

        # Smoke cancels attacks: enemy on a smoke tile cannot attack
        enemy_tile = board.tile(enemy.x, enemy.y)
        if enemy_tile.smoke:
            continue

        # Frozen enemies cannot attack (their telegraphed attack is cancelled)
        if enemy.frozen:
            continue

        wdef = get_weapon_def(enemy.weapon) if enemy.weapon else None
        # Shamans use support-type weapons (buff allies, no direct damage)
        if wdef and wdef.weapon_type == "support":
            continue
        damage = enemy.weapon_damage if enemy.weapon_damage > 0 else (
            wdef.damage if wdef else 1)
        weapon_type = wdef.weapon_type if wdef else "melee"

        if weapon_type == "projectile":
            # Re-trace projectile path on current board state
            # Use original position to compute cardinal direction (handles pushed enemies)
            orig = original_positions.get(enemy.uid)
            ox, oy = (orig[0], orig[1]) if orig else (-1, -1)
            tx, ty = _find_projectile_target(board, enemy, ox, oy)
            if tx < 0:
                continue
            grid_lost = _apply_enemy_hit(board, tx, ty, damage)
            buildings_destroyed += grid_lost
            _apply_enemy_weapon_status(board, tx, ty, wdef, enemy.uid)

            # aoe_perpendicular: splash two tiles perpendicular to projectile
            # direction (Alpha Centipede's Corrosive Vomit: 3-tile T splash,
            # damage + ACID on each).
            if wdef and wdef.aoe_perpendicular:
                dx = tx - enemy.x
                dy = ty - enemy.y
                if dx != 0 and dy == 0:
                    perp_offsets = ((0, 1), (0, -1))
                elif dy != 0 and dx == 0:
                    perp_offsets = ((1, 0), (-1, 0))
                else:
                    perp_offsets = ()
                for px, py in perp_offsets:
                    nx, ny = tx + px, ty + py
                    if not board.in_bounds(nx, ny):
                        continue
                    grid_lost = _apply_enemy_hit(board, nx, ny, damage)
                    buildings_destroyed += grid_lost
                    _apply_enemy_weapon_status(board, nx, ny, wdef, enemy.uid)

        elif weapon_type in ("melee", "charge"):
            tx, ty = enemy.queued_target_x, enemy.queued_target_y

            # Skip if pushed away from target (no longer adjacent)
            orig = original_positions.get(enemy.uid)
            if orig:
                curr_dist = abs(enemy.x - tx) + abs(enemy.y - ty)
                if curr_dist > 1:
                    continue

            # Primary hit
            grid_lost = _apply_enemy_hit(board, tx, ty, damage)
            buildings_destroyed += grid_lost
            _apply_enemy_weapon_status(board, tx, ty, wdef, enemy.uid)

            # TargetBehind: hit tile behind target
            target_behind = enemy.weapon_target_behind or (
                wdef.aoe_behind if wdef else False)
            if target_behind:
                dx = tx - enemy.x
                dy = ty - enemy.y
                bx, by = tx + dx, ty + dy
                if board.in_bounds(bx, by):
                    grid_lost = _apply_enemy_hit(board, bx, by, damage)
                    buildings_destroyed += grid_lost
                    _apply_enemy_weapon_status(board, bx, by, wdef, enemy.uid)

        elif weapon_type == "self_aoe":
            # Scorpion Leader's Massive Spinneret and similar: hit all 4
            # cardinal adjacent tiles at enemy's CURRENT position (after push).
            DIRS = ((0, 1), (1, 0), (0, -1), (-1, 0))
            for dx, dy in DIRS:
                nx, ny = enemy.x + dx, enemy.y + dy
                if board.in_bounds(nx, ny):
                    grid_lost = _apply_enemy_hit(board, nx, ny, damage)
                    buildings_destroyed += grid_lost
                    # Web the target (grapple "hold"): future work to apply
                    # the web flag to pushed-to tile if needed. For now,
                    # match simulate.py apply_weapon_status semantics.
                    if wdef and getattr(wdef, 'web', False):
                        u = board.unit_at(nx, ny)
                        if u is not None:
                            u.web = True

        else:
            # Fallback for other weapon types: use queued target directly
            tx, ty = enemy.queued_target_x, enemy.queued_target_y
            grid_lost = _apply_enemy_hit(board, tx, ty, damage)
            buildings_destroyed += grid_lost

    return buildings_destroyed


# ── Post-solve replay (verification snapshots) ──────────────────────────


def replay_solution(
    board: Board,
    solution: Solution,
    spawn_pts: list[tuple[int, int]],
    current_turn: int = 0,
    total_turns: int = 5,
    remaining_spawns: int = 2**31 - 1,
) -> dict:
    """Re-simulate the best solution to capture detailed per-action data.

    Called ONCE after solve_turn() on the original (unmutated) board.
    Returns enriched data: per-action ActionResult, per-action board
    snapshots (for the verify loop), predicted post-enemy board summary,
    and score component breakdown.
    """
    from src.solver.verify import snapshot_after_action, snapshot_after_move
    from src.solver.simulate import simulate_move, simulate_attack

    b = board.copy()
    original_positions = {e.uid: (e.x, e.y) for e in b.enemies()}

    action_results = []
    predicted_states = []
    total_kills = 0

    for i, action in enumerate(solution.actions):
        m = next((u for u in b.units if u.uid == action.mech_uid), None)
        if m is None:
            error_snap = {
                "action_index": i,
                "mech_uid": action.mech_uid,
                "snapshot_phase": "after_mech_action",
                "error": "mech_not_found",
                "units": [], "tiles_changed": [], "grid_power": b.grid_power,
            }
            action_results.append({
                "enemies_killed": 0, "enemy_damage_dealt": 0,
                "buildings_lost": 0, "buildings_damaged": 0,
                "mech_damage_taken": 0, "pods_collected": 0,
                "spawns_blocked": 0, "events": [f"Mech UID {action.mech_uid} not found"],
            })
            predicted_states.append({
                "post_move": error_snap,
                "post_attack": error_snap,
            })
            continue

        # Phase 1: Move only
        move_result = simulate_move(b, m, action.move_to)
        post_move_snap = snapshot_after_move(b, i, action.mech_uid, move_result.events)

        # Phase 2: Attack (or repair/skip)
        attack_result = simulate_attack(b, m, action.weapon, action.target)
        total_kills += attack_result.enemies_killed
        all_events = move_result.events + attack_result.events

        action_results.append({
            "enemies_killed": attack_result.enemies_killed,
            "enemy_damage_dealt": attack_result.enemy_damage_dealt,
            "buildings_lost": attack_result.buildings_lost,
            "buildings_damaged": attack_result.buildings_damaged,
            "grid_damage": attack_result.grid_damage,
            "mech_damage_taken": attack_result.mech_damage_taken,
            "mechs_killed": attack_result.mechs_killed,
            "pods_collected": move_result.pods_collected,
            "spawns_blocked": attack_result.spawns_blocked,
            "events": all_events,
        })

        post_attack_snap = snapshot_after_action(b, i, action.mech_uid, all_events)

        predicted_states.append({
            "post_move": post_move_snap,
            "post_attack": post_attack_snap,
        })

    # Simulate environment effects (freeze, smoke, etc.) BEFORE enemy attacks
    _simulate_env_effects(b)

    # Simulate enemy attacks on post-mech board
    buildings_destroyed = _simulate_enemy_attacks(b, original_positions)

    # Spawn-blocking damage: mechs ending on spawn tiles take 1 damage each.
    # Matches rust_solver/src/solver.rs where apply_spawn_blocking runs after
    # simulate_enemy_attacks during search scoring.
    _apply_spawn_blocking(b, spawn_pts)

    # Score breakdown on predicted post-enemy board
    score_breakdown = evaluate_breakdown(b, spawn_pts, kills=total_kills,
                                         current_turn=current_turn,
                                         total_turns=total_turns,
                                         remaining_spawns=remaining_spawns)

    # Predicted outcome summary
    buildings_alive = 0
    building_hp_total = 0
    for x in range(8):
        for y in range(8):
            t = b.tile(x, y)
            if t.terrain == "building" and t.building_hp > 0:
                buildings_alive += 1
                building_hp_total += t.building_hp

    predicted_outcome = {
        "buildings_alive": buildings_alive,
        "building_hp_total": building_hp_total,
        "grid_power": b.grid_power,
        "enemies_alive": len(b.enemies()),
        "enemy_hp_total": sum(e.hp for e in b.enemies()),
        "mechs_alive": len([m for m in b.mechs() if m.hp > 0]),
        "mech_hp": [
            {"uid": m.uid, "type": m.type, "hp": m.hp, "max_hp": m.max_hp}
            for m in b.mechs()
        ],
        "buildings_destroyed_by_enemies": buildings_destroyed,
    }

    return {
        "action_results": action_results,
        "predicted_states": predicted_states,
        "predicted_outcome": predicted_outcome,
        "score_breakdown": score_breakdown,
    }


