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
from src.solver.evaluate import evaluate


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
            if board.unit_at(nx, ny) or wdef.push != "none":
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

        mech.x, mech.y = old_x, old_y

    return actions


# --- Enemy Attack Simulation ---

def _simulate_enemy_attacks(board: Board, original_positions: dict) -> int:
    """Simulate all enemy attacks on the post-mech-action board.

    Approximates enemy damage using their weapon definitions.
    Enemies killed (hp <= 0) don't attack. Melee enemies pushed away
    from their target don't attack (no longer adjacent).

    This is a pragmatic v1: handles direct damage correctly but
    ignores enemy push effects, AoE splash, and charge mechanics.
    Catches ~80% of building threats.

    Args:
        board: Board state after mech actions (WILL BE MUTATED).
        original_positions: {enemy_uid: (orig_x, orig_y)} from before
            mech actions, used to detect pushed melee enemies.

    Returns:
        Number of buildings destroyed.
    """
    buildings_destroyed = 0

    for enemy in board.enemies():
        if enemy.target_x < 0:
            continue

        tx, ty = enemy.target_x, enemy.target_y

        # Skip melee enemies that were pushed away from their target
        orig = original_positions.get(enemy.uid)
        if orig:
            orig_dist = abs(orig[0] - tx) + abs(orig[1] - ty)
            curr_dist = abs(enemy.x - tx) + abs(enemy.y - ty)
            # Melee: was adjacent, now isn't → can't attack
            if orig_dist <= 1 and curr_dist > 1:
                continue

        # Look up actual weapon damage
        wdef = get_weapon_def(enemy.weapon) if enemy.weapon else None
        damage = wdef.damage if wdef else 1

        # Check if a mech is body-blocking the attack
        blocker = board.unit_at(tx, ty)
        if blocker is not None and blocker.is_player:
            blocker.hp -= damage
            if blocker.hp <= 0:
                blocker.hp = 0
            continue

        # Building takes damage (always 1 grid damage regardless of weapon)
        tile = board.tile(tx, ty)
        if tile.terrain == "building" and tile.building_hp > 0:
            tile.building_hp -= 1
            buildings_destroyed += 1
            if tile.building_hp <= 0:
                tile.terrain = "rubble"

    return buildings_destroyed


# --- Recursive Search ---

def _search_recursive(
    board: Board,
    mechs_remaining: list[Unit],
    actions_so_far: list[MechAction],
    kills_so_far: int,
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
        if score > best.score:
            best.score = score
            best.actions = list(actions_so_far)
        return

    mech = mechs_remaining[0]
    rest = mechs_remaining[1:]

    actions = _enumerate_mech_actions(board, mech)
    actions = _prune_actions(board, mech, actions,
                             threat_tiles, building_threat_tiles, max_actions)

    for action in actions:
        if time.time() - start_time > time_limit:
            return

        b_next = board.copy()
        m = next(u for u in b_next.units if u.uid == mech.uid)
        result = simulate_action(b_next, m, action[0], action[1], action[2])

        actions_so_far.append(_make_action(mech, *action))
        _search_recursive(
            b_next, rest, actions_so_far,
            kills_so_far + result.enemies_killed,
            threat_tiles, building_threat_tiles, original_positions,
            spawn_pts, max_actions, best,
            start_time, time_limit,
        )
        actions_so_far.pop()


def solve_turn(
    board: Board,
    spawn_points: list[tuple[int, int]] = None,
    time_limit: float = 10.0,
    max_actions_per_mech: int = 50,
) -> Solution:
    """Find the best sequence of mech actions for this turn.

    Tries all orderings of active mechs using recursive search.
    Supports any number of mechs (not limited to 3).
    Simulates enemy attacks after mech actions to predict building damage.

    Args:
        board: Current board state.
        spawn_points: Next turn's Vek spawn locations.
        time_limit: Maximum search time in seconds.
        max_actions_per_mech: Limit actions per mech for pruning.

    Returns:
        Solution with the best action sequence found.
    """
    start_time = time.time()
    best = Solution()

    active_mechs = [m for m in board.mechs() if m.active and m.hp > 0]
    if not active_mechs:
        return best

    spawn_pts = spawn_points or []

    # Pre-compute threat information
    threat_tiles = set()
    for e in board.enemies():
        if e.target_x >= 0:
            threat_tiles.add((e.target_x, e.target_y))

    # Building-specific threats (tiles where enemy attack would hit a building)
    building_threat_tiles = set()
    for tx, ty, _ in board.get_threatened_buildings():
        building_threat_tiles.add((tx, ty))

    # Capture original enemy positions for pushed-melee detection
    original_positions = {e.uid: (e.x, e.y) for e in board.enemies()}

    # Reduce search space for 4+ mechs
    effective_max = max_actions_per_mech
    if len(active_mechs) >= 4:
        effective_max = min(25, max_actions_per_mech)

    # Try all mech orderings
    for ordering in permutations(range(len(active_mechs))):
        if time.time() - start_time > time_limit:
            break

        mechs_ordered = [active_mechs[i] for i in ordering]
        _search_recursive(
            board, mechs_ordered, [], 0,
            threat_tiles, building_threat_tiles, original_positions,
            spawn_pts, effective_max, best,
            start_time, time_limit,
        )

    elapsed = time.time() - start_time
    print(f"Solver: score={best.score:.0f}, "
          f"{len(best.actions)} actions, {elapsed:.1f}s")

    return best


def _prune_actions(board, mech, actions, threat_tiles,
                   building_threat_tiles, max_n):
    """Prune actions to the top N by quick heuristic.

    Prioritizes actions that:
    1. Body-block building threats (move onto a tile an enemy targets)
    2. Neutralize threats (attack or push enemies off threatened tiles)
    3. Push enemies AWAY from buildings they're threatening
    4. Kill enemies
    5. Block spawns
    """
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

            # Any attack is better than no attack
            s += 10

        # Spawn blocking
        if move_to in threat_tiles and move_to not in building_threat_tiles:
            s += 30

        return s

    actions.sort(key=score_action, reverse=True)
    return actions[:max_n]


def _make_action(mech, move_to, weapon_id, target) -> MechAction:
    """Create a MechAction from solver data."""
    desc_parts = [f"{mech.type}"]
    if move_to != (mech.x, mech.y):
        desc_parts.append(f"move ({mech.x},{mech.y})->({move_to[0]},{move_to[1]})")
    if weapon_id:
        wname = get_weapon_name(weapon_id)
        desc_parts.append(f"fire {wname} at ({target[0]},{target[1]})")
    return MechAction(
        mech_uid=mech.uid,
        mech_type=mech.type,
        move_to=move_to,
        weapon=weapon_id,
        target=target,
        description=", ".join(desc_parts),
    )
