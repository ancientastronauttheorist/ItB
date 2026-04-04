"""The main solver: find the optimal 3-mech action sequence.

Given a board state with known enemy intents, enumerate possible
mech actions (move + attack) and find the sequence that maximizes
the evaluation function.

Search space: for each of 3 mechs (in all 6 orderings):
  - reachable tiles (movement BFS)
  - for each position, valid weapon targets
  - evaluate the result

Uses aggressive pruning: prioritize actions that neutralize threats.
"""

from __future__ import annotations

import time
from itertools import permutations
from dataclasses import dataclass, field
from src.model.board import Board, Unit
from src.model.weapons import get_weapon_def
from src.solver.movement import (
    get_reachable_tiles, get_adjacent, direction_between, DIRS,
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
        # Adjacent tiles only
        for nx, ny, _ in get_adjacent(mx, my):
            # Must have something to hit, or weapon has push
            if board.unit_at(nx, ny) or wdef.push != "none":
                targets.append((nx, ny))

    elif wdef.weapon_type in ("projectile", "pull", "laser"):
        # Four cardinal directions
        for d, (dx, dy) in enumerate(DIRS):
            nx, ny = mx + dx, my + dy
            if board.in_bounds(nx, ny):
                targets.append((nx, ny))  # direction encoded as adjacent tile

    elif wdef.weapon_type == "artillery":
        # Any tile within range (skip adjacent)
        min_r = wdef.range_min
        for x in range(8):
            for y in range(8):
                dist = abs(x - mx) + abs(y - my)
                if dist < min_r:
                    continue
                # Artillery must be in same row or column
                if x != mx and y != my:
                    continue
                targets.append((x, y))

    elif wdef.weapon_type == "self_aoe":
        # Self-targeted, no specific target needed
        targets.append((mx, my))

    elif wdef.weapon_type == "charge":
        # Four cardinal directions
        for d, (dx, dy) in enumerate(DIRS):
            # Check there's room to charge
            nx, ny = mx + dx, my + dy
            if board.in_bounds(nx, ny):
                targets.append((nx, ny))

    elif wdef.weapon_type == "leap":
        # Any reachable tile (limited range)
        for x in range(8):
            for y in range(8):
                dist = abs(x - mx) + abs(y - my)
                if 1 <= dist <= wdef.range_max:
                    if board.is_passable(x, y, mech.flying):
                        targets.append((x, y))

    elif wdef.weapon_type == "swap":
        # Any unit within range
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
        # Temporarily move mech to test weapon targets
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


def solve_turn(
    board: Board,
    spawn_points: list[tuple[int, int]] = None,
    time_limit: float = 10.0,
    max_actions_per_mech: int = 50,
) -> Solution:
    """Find the best sequence of mech actions for this turn.

    Tries all orderings of the 3 mechs, and for each ordering,
    searches through possible actions with pruning.

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

    # Pre-compute enemy attack targets for threat scoring
    threat_tiles = set()
    for e in board.enemies():
        if e.target_x >= 0:
            threat_tiles.add((e.target_x, e.target_y))

    # Try all mech orderings
    for ordering in permutations(range(len(active_mechs))):
        if time.time() - start_time > time_limit:
            break

        mechs_ordered = [active_mechs[i] for i in ordering]

        # Get actions for first mech
        actions_0 = _enumerate_mech_actions(board, mechs_ordered[0])
        # Prune to top N by quick heuristic
        actions_0 = _prune_actions(board, mechs_ordered[0], actions_0,
                                    threat_tiles, max_actions_per_mech)

        for a0 in actions_0:
            if time.time() - start_time > time_limit:
                break

            b1 = board.copy()
            m0 = next(u for u in b1.units if u.uid == mechs_ordered[0].uid)
            r0 = simulate_action(b1, m0, a0[0], a0[1], a0[2])

            if len(mechs_ordered) < 2:
                score = evaluate(b1, spawn_pts)
                if score > best.score:
                    best = Solution(
                        actions=[_make_action(mechs_ordered[0], *a0)],
                        score=score,
                    )
                continue

            # Second mech
            actions_1 = _enumerate_mech_actions(b1, next(
                u for u in b1.units if u.uid == mechs_ordered[1].uid))
            actions_1 = _prune_actions(b1, mechs_ordered[1], actions_1,
                                        threat_tiles, max_actions_per_mech)

            for a1 in actions_1:
                if time.time() - start_time > time_limit:
                    break

                b2 = b1.copy()
                m1 = next(u for u in b2.units if u.uid == mechs_ordered[1].uid)
                r1 = simulate_action(b2, m1, a1[0], a1[1], a1[2])

                if len(mechs_ordered) < 3:
                    score = evaluate(b2, spawn_pts)
                    if score > best.score:
                        best = Solution(
                            actions=[
                                _make_action(mechs_ordered[0], *a0),
                                _make_action(mechs_ordered[1], *a1),
                            ],
                            score=score,
                        )
                    continue

                # Third mech
                actions_2 = _enumerate_mech_actions(b2, next(
                    u for u in b2.units if u.uid == mechs_ordered[2].uid))
                actions_2 = _prune_actions(b2, mechs_ordered[2], actions_2,
                                            threat_tiles, max_actions_per_mech)

                for a2 in actions_2:
                    if time.time() - start_time > time_limit:
                        break

                    b3 = b2.copy()
                    m2 = next(u for u in b3.units if u.uid == mechs_ordered[2].uid)
                    r2 = simulate_action(b3, m2, a2[0], a2[1], a2[2])

                    score = evaluate(b3, spawn_pts)
                    if score > best.score:
                        best = Solution(
                            actions=[
                                _make_action(mechs_ordered[0], *a0),
                                _make_action(mechs_ordered[1], *a1),
                                _make_action(mechs_ordered[2], *a2),
                            ],
                            score=score,
                        )

    elapsed = time.time() - start_time
    print(f"Solver: score={best.score:.0f}, "
          f"{len(best.actions)} actions, {elapsed:.1f}s")

    return best


def _prune_actions(board, mech, actions, threat_tiles, max_n):
    """Prune actions to the top N by quick heuristic.

    Prioritizes actions that:
    1. Neutralize threats (attack threatened tiles or push enemies off them)
    2. Kill enemies
    3. Block spawns
    """
    if len(actions) <= max_n:
        return actions

    def score_action(a):
        move_to, weapon_id, target = a
        s = 0

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
            # Any attack is better than no attack
            s += 10

        # Bonus for moving to spawn point
        if move_to in threat_tiles:
            s += 30  # body-blocking

        return s

    actions.sort(key=score_action, reverse=True)
    return actions[:max_n]


def _make_action(mech, move_to, weapon_id, target) -> MechAction:
    """Create a MechAction from solver data."""
    from src.model.weapons import get_weapon_name
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
