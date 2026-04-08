"""The main solver: find the optimal mech action sequence.

Given a board state with known enemy intents, enumerate possible
mech actions (move + attack) and find the sequence that maximizes
the evaluation function.

Key features:
  - Recursive search supports any number of mechs (not just 3)
  - Simulates enemy attacks AFTER mech actions to predict building damage
  - Enhanced pruning prioritizes building defense, body-blocking, and push deflection
  - Time-limited search with aggressive pruning for 4+ mechs
"""

from __future__ import annotations

import math
import multiprocessing as mp
import time
from itertools import permutations
from dataclasses import dataclass, field
from src.model.board import Board, Unit
from src.model.weapons import get_weapon_def, get_weapon_name
from src.solver.movement import (
    get_reachable_tiles, get_adjacent, direction_between,
    push_destination, DIRS,
)
from src.solver.simulate import simulate_action
from src.solver.evaluate import evaluate, evaluate_breakdown


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


def get_weapon_targets(
    board: Board,
    mech: Unit,
    weapon_id: str,
) -> list[tuple[int, int]]:
    """Enumerate valid weapon targets from the mech's current position.

    Returns list of (target_x, target_y) for each valid target.
    """
    wdef = get_weapon_def(weapon_id)
    if wdef is None:
        return []

    mx, my = mech.x, mech.y
    targets = []

    if wdef.weapon_type == "melee":
        for nx, ny, _ in get_adjacent(mx, my):
            has_unit = board.unit_at(nx, ny) is not None
            if has_unit:
                targets.append((nx, ny))
            elif wdef.push != "none":
                # Push-capable melee can target empty tiles (e.g. to push
                # something that moves there later), but NEVER buildings —
                # punching a building destroys it for zero benefit.
                tile = board.tile(nx, ny)
                if not (tile.terrain == "building" and tile.building_hp > 0):
                    targets.append((nx, ny))

    elif wdef.weapon_type in ("projectile", "pull", "laser"):
        for d, (dx, dy) in enumerate(DIRS):
            nx, ny = mx + dx, my + dy
            if board.in_bounds(nx, ny):
                targets.append((nx, ny))

    elif wdef.weapon_type == "artillery":
        min_r = wdef.range_min
        for x in range(8):
            for y in range(8):
                dist = abs(x - mx) + abs(y - my)
                if dist < min_r:
                    continue
                if x != mx and y != my:
                    continue
                # Don't target friendly buildings
                tile = board.tile(x, y)
                if tile.terrain == "building" and tile.building_hp > 0:
                    continue
                targets.append((x, y))

    elif wdef.weapon_type == "self_aoe":
        targets.append((mx, my))

    elif wdef.weapon_type == "charge":
        for d, (dx, dy) in enumerate(DIRS):
            nx, ny = mx + dx, my + dy
            if board.in_bounds(nx, ny):
                targets.append((nx, ny))

    elif wdef.weapon_type == "leap":
        for x in range(8):
            for y in range(8):
                dist = abs(x - mx) + abs(y - my)
                if 1 <= dist <= wdef.range_max:
                    if board.is_passable(x, y, mech.flying):
                        targets.append((x, y))

    elif wdef.weapon_type == "swap":
        rng = wdef.range_max or 8
        for x in range(8):
            for y in range(8):
                dist = abs(x - mx) + abs(y - my)
                if 1 <= dist <= rng:
                    targets.append((x, y))

    return targets


def _enumerate_mech_actions(
    board: Board,
    mech: Unit,
) -> list[tuple[tuple[int, int], str, tuple[int, int]]]:
    """Enumerate all possible (move_to, weapon, target) for a mech.

    Returns list of (move_pos, weapon_id, target_pos).
    """
    actions = []
    reachable = get_reachable_tiles(board, mech)

    for pos in reachable:
        old_x, old_y = mech.x, mech.y
        mech.x, mech.y = pos

        # Option 1: move only (no attack)
        actions.append((pos, "", (-1, -1)))

        # Option 2: primary weapon
        if mech.weapon:
            for target in get_weapon_targets(board, mech, mech.weapon):
                actions.append((pos, mech.weapon, target))

        # Option 3: secondary weapon
        if mech.weapon2:
            for target in get_weapon_targets(board, mech, mech.weapon2):
                actions.append((pos, mech.weapon2, target))

        # Option 4: repair (heal 1 HP, remove fire/acid)
        # Only useful if damaged or has removable status; can't repair if smoked
        tile = board.tile(pos[0], pos[1])
        if not getattr(tile, 'smoke', False):
            if mech.hp < mech.max_hp or mech.fire or mech.acid:
                actions.append((pos, "_REPAIR", (pos[0], pos[1])))

        mech.x, mech.y = old_x, old_y

    return actions


# --- Enemy Attack Simulation ---

def _find_projectile_target(board: Board, enemy: Unit) -> tuple[int, int]:
    """Trace a projectile from enemy position in queued direction.

    Returns (hit_x, hit_y) of first unit/mountain/building, or (-1, -1).
    """
    if enemy.queued_target_x < 0:
        return -1, -1

    dx = enemy.queued_target_x - enemy.x
    dy = enemy.queued_target_y - enemy.y
    # Normalize to unit direction
    if dx != 0:
        dx = 1 if dx > 0 else -1
    if dy != 0:
        dy = 1 if dy > 0 else -1

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
    grid_lost = 0

    unit = board.unit_at(x, y)
    if unit is not None and unit.is_player:
        unit.hp -= damage
        if unit.hp < 0:
            unit.hp = 0
        return 0  # mech absorbs hit, no grid damage

    tile = board.tile(x, y)
    if tile.terrain == "building" and tile.building_hp > 0:
        actual = min(damage, tile.building_hp)
        tile.building_hp -= actual
        grid_lost += actual
        if tile.building_hp <= 0:
            tile.terrain = "rubble"

    return grid_lost


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
        damage = enemy.weapon_damage if enemy.weapon_damage > 0 else (
            wdef.damage if wdef else 1)
        weapon_type = wdef.weapon_type if wdef else "melee"

        if weapon_type == "projectile":
            # Re-trace projectile path on current board state
            tx, ty = _find_projectile_target(board, enemy)
            if tx < 0:
                continue
            grid_lost = _apply_enemy_hit(board, tx, ty, damage)
            buildings_destroyed += grid_lost

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

        else:
            # Fallback for other weapon types: use queued target directly
            tx, ty = enemy.queued_target_x, enemy.queued_target_y
            grid_lost = _apply_enemy_hit(board, tx, ty, damage)
            buildings_destroyed += grid_lost

    return buildings_destroyed


# --- Recursive Search ---

def _is_wasted_attack(weapon_id: str, result) -> bool:
    """Check if a weapon was fired but accomplished nothing.

    Returns True only when ALL of these hold:
    - A weapon was actually fired (not move-only or repair)
    - Zero enemies killed or damaged
    - Zero buildings damaged
    - Zero mech damage (from push_self, etc.)
    - Zero pods collected or spawns blocked

    This correctly returns False for AoE weapons hitting adjacent
    units, push chains into terrain, fire/smoke placement, charge
    repositioning, etc. — because those produce non-zero results.
    """
    if not weapon_id or weapon_id == "_REPAIR":
        return False
    return (result.enemies_killed == 0
            and result.enemy_damage_dealt == 0
            and result.buildings_damaged == 0
            and result.buildings_lost == 0
            and result.mech_damage_taken == 0
            and result.pods_collected == 0)


def _search_recursive(
    board: Board,
    mechs_remaining: list[Unit],
    actions_so_far: list[MechAction],
    kills_so_far: int,
    wasted_attacks_so_far: int,
    threat_tiles: set,
    building_threat_tiles: set,
    original_positions: dict,
    spawn_pts: list,
    max_actions: int,
    best: Solution,
    start_time: float,
    time_limit: float,
) -> None:
    """Recursively search mech action sequences.

    Supports any number of mechs. Time-checked at every level.
    """
    if time.time() - start_time > time_limit:
        return

    if not mechs_remaining:
        # All mechs acted — simulate enemy attacks and evaluate
        b_eval = board.copy()
        _simulate_enemy_attacks(b_eval, original_positions)
        score = evaluate(b_eval, spawn_pts, kills=kills_so_far)
        # Tiny penalty for wasted attacks — just enough to prefer
        # move-only over firing at empty tiles when all else is equal
        score -= wasted_attacks_so_far * 5
        if score > best.score:
            best.score = score
            best.actions = list(actions_so_far)
        return

    mech = mechs_remaining[0]
    rest = mechs_remaining[1:]

    actions = _enumerate_mech_actions(board, mech)
    actions = _prune_actions(board, mech, actions,
                             threat_tiles, building_threat_tiles,
                             spawn_pts, max_actions)

    for action in actions:
        if time.time() - start_time > time_limit:
            return

        b_next = board.copy()
        m = next(u for u in b_next.units if u.uid == mech.uid)
        result = simulate_action(b_next, m, action[0], action[1], action[2])

        wasted = 1 if _is_wasted_attack(action[1], result) else 0
        actions_so_far.append(_make_action(mech, *action))
        _search_recursive(
            b_next, rest, actions_so_far,
            kills_so_far + result.enemies_killed,
            wasted_attacks_so_far + wasted,
            threat_tiles, building_threat_tiles, original_positions,
            spawn_pts, max_actions, best,
            start_time, time_limit,
        )
        actions_so_far.pop()


def _solve_one_permutation(args):
    """Worker function for parallel permutation solving.

    Runs in a child process via multiprocessing. Takes all pre-computed
    data as a single tuple (for pool.map compatibility).
    """
    (board, mech_uids, threat_tiles, building_threat_tiles,
     original_positions, spawn_pts, effective_max, time_limit) = args

    # Reconstruct ordered mech list from UIDs
    active_mechs = []
    for uid in mech_uids:
        m = next((u for u in board.units if u.uid == uid), None)
        if m is not None:
            active_mechs.append(m)

    best = Solution()
    start_time = time.time()

    _search_recursive(
        board, active_mechs, [], 0, 0,
        threat_tiles, building_threat_tiles, original_positions,
        spawn_pts, effective_max, best,
        start_time, time_limit,
    )

    best.elapsed_seconds = time.time() - start_time
    return best


def solve_turn(
    board: Board,
    spawn_points: list[tuple[int, int]] = None,
    time_limit: float = 10.0,
    max_actions_per_mech: int = 50,
    environment_danger: set[tuple[int, int]] = None,
) -> Solution:
    """Find the best sequence of mech actions for this turn.

    Tries all orderings of active mechs using parallel recursive search.
    Each permutation runs in its own process with the full time budget.
    Supports any number of mechs (not limited to 3).
    Simulates enemy attacks after mech actions to predict building damage.

    Args:
        board: Current board state.
        spawn_points: Next turn's Vek spawn locations.
        time_limit: Maximum search time in seconds (each worker gets full budget).
        max_actions_per_mech: Limit actions per mech for pruning.
        environment_danger: Tiles that will become deadly at end of turn
            (tidal waves, air strikes, etc.). Non-flying units here will die.

    Returns:
        Solution with the best action sequence found.
    """
    start_time = time.time()
    best = Solution()

    # Store environment danger on board so evaluate() and _prune_actions() can use it
    board.environment_danger = environment_danger or set()

    # Include player mechs AND friendly controllable units (e.g., ArchiveArtillery)
    active_mechs = [m for m in board.mechs()
                    if m.active and m.hp > 0 and (m.is_mech or m.weapon)]
    if not active_mechs:
        return best

    spawn_pts = spawn_points or []

    # Pre-compute threat information
    threat_tiles = set()
    for e in board.enemies():
        if e.target_x >= 0:
            threat_tiles.add((e.target_x, e.target_y))

    # Building-specific threats — compute ACTUAL impact tiles.
    # For projectile enemies, trace the path to find the real hit
    # (the queued target may be behind a closer building/unit).
    building_threat_tiles = set()
    for e in board.enemies():
        if e.target_x < 0:
            continue
        wdef = get_weapon_def(e.weapon) if e.weapon else None
        weapon_type = wdef.weapon_type if wdef else "melee"
        if weapon_type == "projectile":
            # Trace projectile to find actual impact tile
            hit_x, hit_y = _find_projectile_target(board, e)
            if hit_x >= 0:
                t = board.tile(hit_x, hit_y)
                if t.terrain == "building" and t.building_hp > 0:
                    building_threat_tiles.add((hit_x, hit_y))
        else:
            # Melee/other: queued target is the actual hit tile
            tx, ty = e.target_x, e.target_y
            t = board.tile(tx, ty)
            if t.terrain == "building" and t.building_hp > 0:
                building_threat_tiles.add((tx, ty))

    # Capture original enemy positions for pushed-melee detection
    original_positions = {e.uid: (e.x, e.y) for e in board.enemies()}

    # Reduce search space for 4+ mechs
    effective_max = max_actions_per_mech
    if len(active_mechs) >= 4:
        effective_max = min(25, max_actions_per_mech)

    total_perms = math.factorial(len(active_mechs))
    mech_uids = [m.uid for m in active_mechs]

    # Build args for each permutation
    worker_args = []
    for ordering in permutations(range(len(active_mechs))):
        ordered_uids = [mech_uids[i] for i in ordering]
        worker_args.append((
            board.copy(),
            ordered_uids,
            threat_tiles,
            building_threat_tiles,
            original_positions,
            spawn_pts,
            effective_max,
            time_limit,
        ))

    # Parallel solve across all permutations
    num_workers = min(mp.cpu_count(), len(worker_args))
    if num_workers > 1 and len(worker_args) > 1:
        with mp.Pool(processes=num_workers) as pool:
            results = pool.map(_solve_one_permutation, worker_args)
    else:
        results = [_solve_one_permutation(a) for a in worker_args]

    # Pick the best result across all workers
    for r in results:
        if r.score > best.score:
            best = r

    elapsed = time.time() - start_time
    any_timed_out = any(r.elapsed_seconds >= time_limit * 0.95 for r in results)

    # Store search stats on solution
    best.elapsed_seconds = elapsed
    best.timed_out = any_timed_out
    best.permutations_tried = total_perms
    best.total_permutations = total_perms
    best.active_mech_count = len(active_mechs)

    print(f"Solver: score={best.score:.0f}, "
          f"{len(best.actions)} actions, {elapsed:.1f}s "
          f"({num_workers} workers, {total_perms} permutations)"
          f"{' (some timed out)' if any_timed_out else ' (all complete)'}")

    return best


def replay_solution(
    board: Board,
    solution: Solution,
    spawn_pts: list[tuple[int, int]],
) -> dict:
    """Re-simulate the best solution to capture detailed per-action data.

    Called ONCE after solve_turn() on the original (unmutated) board.
    Returns enriched data: per-action ActionResult, predicted post-enemy
    board summary, and score component breakdown.
    """
    b = board.copy()
    original_positions = {e.uid: (e.x, e.y) for e in b.enemies()}

    action_results = []
    total_kills = 0

    for action in solution.actions:
        # Find mech by UID on the (progressively mutated) board copy
        m = next((u for u in b.units if u.uid == action.mech_uid), None)
        if m is None:
            action_results.append({
                "enemies_killed": 0, "enemy_damage_dealt": 0,
                "buildings_lost": 0, "buildings_damaged": 0,
                "mech_damage_taken": 0, "pods_collected": 0,
                "spawns_blocked": 0, "events": [f"Mech UID {action.mech_uid} not found"],
            })
            continue

        result = simulate_action(b, m, action.move_to, action.weapon, action.target)
        total_kills += result.enemies_killed
        action_results.append({
            "enemies_killed": result.enemies_killed,
            "enemy_damage_dealt": result.enemy_damage_dealt,
            "buildings_lost": result.buildings_lost,
            "buildings_damaged": result.buildings_damaged,
            "grid_damage": result.grid_damage,
            "mech_damage_taken": result.mech_damage_taken,
            "mechs_killed": result.mechs_killed,
            "pods_collected": result.pods_collected,
            "spawns_blocked": result.spawns_blocked,
            "events": result.events,
        })

    # Simulate enemy attacks on post-mech board
    buildings_destroyed = _simulate_enemy_attacks(b, original_positions)

    # Score breakdown on predicted post-enemy board
    score_breakdown = evaluate_breakdown(b, spawn_pts, kills=total_kills)

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
        "predicted_outcome": predicted_outcome,
        "score_breakdown": score_breakdown,
    }


def _prune_actions(board, mech, actions, threat_tiles,
                   building_threat_tiles, spawn_points, max_n):
    """Prune actions to the top N by quick heuristic.

    Prioritizes actions that:
    1. Body-block building threats (move onto a tile an enemy targets)
    2. Neutralize threats (attack or push enemies off threatened tiles)
    3. Push enemies AWAY from buildings they're threatening
    4. Kill enemies
    5. Block spawns (mech on spawn tile, or push enemy onto spawn tile)
    """
    spawn_set = set(spawn_points) if spawn_points else set()
    if len(actions) <= max_n:
        return actions

    def score_action(a):
        move_to, weapon_id, target = a
        s = 0

        # HIGH: Body-blocking a building threat
        if move_to in building_threat_tiles:
            s += 200  # mech absorbs hit instead of building

        # Bonus for attacking near threatened tiles
        if weapon_id and target[0] >= 0:
            wdef = get_weapon_def(weapon_id)
            if wdef and wdef.damage > 0:
                for tx, ty in threat_tiles:
                    dist = abs(target[0] - tx) + abs(target[1] - ty)
                    if dist == 0:
                        s += 100  # direct threat neutralization
                    elif dist <= 1:
                        s += 50

            # Push direction scoring: push enemy AWAY from threatened building
            if wdef and wdef.push != "none" and target[0] >= 0:
                enemy = board.unit_at(target[0], target[1])
                if enemy and enemy.target_x >= 0:
                    threatened = (enemy.target_x, enemy.target_y)
                    push_dir = direction_between(
                        move_to[0], move_to[1], target[0], target[1]
                    )
                    if push_dir is not None:
                        dest = push_destination(
                            target[0], target[1], push_dir, board
                        )
                        if dest is not None:
                            # Enemy will move — can it still attack the building?
                            new_dist = abs(dest[0] - threatened[0]) + \
                                       abs(dest[1] - threatened[1])
                            if new_dist > 1:
                                s += 150  # push deflects melee attack

            # PENALTY: Attacking a tile with a friendly mech
            if target[0] >= 0:
                friendly = board.unit_at(target[0], target[1])
                if friendly and friendly.is_player:
                    s -= 300  # heavy penalty for friendly fire

            # Prefer attacks that target something over move-only,
            # but don't reward attacking empty ground
            target_unit = board.unit_at(target[0], target[1])
            target_tile = board.tile(target[0], target[1])
            has_target = (target_unit is not None
                          or target_tile.terrain in ("building", "mountain"))
            has_aoe = (wdef and (wdef.aoe_adjacent or getattr(wdef, 'aoe_perpendicular', False)
                       or getattr(wdef, 'aoe_behind', False)))
            if has_target or has_aoe:
                s += 10

        # Mech blocks a spawn tile by standing on it
        if spawn_set and move_to in spawn_set:
            s += 80

        # Push enemy onto a spawn tile
        if spawn_set and weapon_id and target[0] >= 0:
            wdef_sp = get_weapon_def(weapon_id) if weapon_id != "_REPAIR" else None
            if wdef_sp and wdef_sp.push != "none":
                enemy_sp = board.unit_at(target[0], target[1])
                if enemy_sp and enemy_sp.is_enemy:
                    push_dir_sp = direction_between(
                        move_to[0], move_to[1], target[0], target[1])
                    if push_dir_sp is not None:
                        dest_sp = push_destination(
                            target[0], target[1], push_dir_sp, board)
                        if dest_sp is not None and dest_sp in spawn_set:
                            s += 60  # enemy on spawn blocks it too

        # ACID tile avoidance: don't move mechs onto acid tiles
        # (acid doubles all damage taken, disables armor)
        move_tile = board.tile(move_to[0], move_to[1])
        if move_tile.acid and not mech.acid:
            s -= 200  # mech will gain acid status

        # Smoke: bonus for pushing enemies onto smoke tiles (cancels their attack)
        if weapon_id and target[0] >= 0:
            wdef_smoke = get_weapon_def(weapon_id) if weapon_id != "_REPAIR" else None
            if wdef_smoke and wdef_smoke.push != "none":
                enemy_s = board.unit_at(target[0], target[1])
                if enemy_s and enemy_s.is_enemy and enemy_s.queued_target_x >= 0:
                    push_dir_s = direction_between(
                        move_to[0], move_to[1], target[0], target[1])
                    if push_dir_s is not None:
                        dest_s = push_destination(
                            target[0], target[1], push_dir_s, board)
                        if dest_s is not None:
                            dest_tile = board.tile(dest_s[0], dest_s[1])
                            if dest_tile.smoke:
                                s += 200  # enemy attack will be cancelled

        # Environment danger: avoid non-flying mechs stepping on danger tiles
        if board.environment_danger and move_to in board.environment_danger:
            if not mech.flying:
                s -= 300  # mech will die when environment resolves

        # Environment danger: bonus for pushing non-flying enemies onto danger tiles
        if board.environment_danger and weapon_id and target[0] >= 0:
            wdef_env = get_weapon_def(weapon_id) if weapon_id != "_REPAIR" else None
            if wdef_env and wdef_env.push != "none":
                enemy = board.unit_at(target[0], target[1])
                if enemy and enemy.is_enemy and not enemy.flying:
                    push_dir = direction_between(
                        move_to[0], move_to[1], target[0], target[1]
                    )
                    if push_dir is not None:
                        dest = push_destination(
                            target[0], target[1], push_dir, board
                        )
                        if dest is not None and dest in board.environment_danger:
                            s += 250  # enemy will die when environment resolves

        return s

    actions.sort(key=score_action, reverse=True)
    return actions[:max_n]


def _bridge_to_visual(x: int, y: int) -> str:
    """Convert bridge (x,y) to visual notation like 'C5'.

    The game board shows Row numbers 1-8 (left edge) and Column letters
    A-H (right edge). Bridge coords map as: Col = chr(72-y), Row = 8-x.
    """
    col = chr(72 - y)  # H for y=0, G for y=1, ..., A for y=7
    row = 8 - x
    return f"{col}{row}"


def _make_action(mech, move_to, weapon_id, target) -> MechAction:
    """Create a MechAction from solver data."""
    desc_parts = [f"{mech.type}"]
    if move_to != (mech.x, mech.y):
        src = _bridge_to_visual(mech.x, mech.y)
        dst = _bridge_to_visual(move_to[0], move_to[1])
        desc_parts.append(f"move {src}\u2192{dst}")
    if weapon_id == "_REPAIR":
        desc_parts.append("repair")
    elif weapon_id:
        wname = get_weapon_name(weapon_id)
        tgt = _bridge_to_visual(target[0], target[1])
        desc_parts.append(f"fire {wname} at {tgt}")
    return MechAction(
        mech_uid=mech.uid,
        mech_type=mech.type,
        move_to=move_to,
        weapon=weapon_id,
        target=target,
        description=", ".join(desc_parts),
    )
