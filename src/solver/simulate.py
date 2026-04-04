"""Simulate weapon effects on the board.

Given a unit, weapon, and target, compute the resulting board state:
damage dealt, units pushed, status effects applied, buildings destroyed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.model.board import Board, Unit, TERRAIN_DEADLY_GROUND
from src.model.weapons import get_weapon_def, WeaponDef
from src.solver.movement import (
    DIRS, DIR_NAMES, direction_between, opposite_dir, push_destination,
    get_adjacent,
)


@dataclass
class ActionResult:
    """Result of simulating a mech action (move + attack)."""
    buildings_lost: int = 0
    buildings_damaged: int = 0
    grid_damage: int = 0
    enemies_killed: int = 0
    enemy_damage_dealt: int = 0
    mech_damage_taken: int = 0
    mechs_killed: int = 0
    pods_collected: int = 0
    spawns_blocked: int = 0  # mech standing on spawn point
    # Detailed logs
    events: list[str] = field(default_factory=list)


def apply_damage(board: Board, x: int, y: int, damage: int,
                 result: ActionResult, source: str = "") -> None:
    """Apply damage to whatever is at (x, y)."""
    if not board.in_bounds(x, y):
        return

    unit = board.unit_at(x, y)
    tile = board.tile(x, y)

    if unit and damage > 0:
        actual = damage
        if unit.armor:
            actual = max(0, damage - 1)
        unit.hp -= actual

        if unit.is_enemy:
            result.enemy_damage_dealt += actual
            if unit.hp <= 0:
                result.enemies_killed += 1
                result.events.append(f"Killed {unit.type} at ({x},{y})")
        elif unit.is_player:
            result.mech_damage_taken += actual
            if unit.hp <= 0:
                result.mechs_killed += 1
                result.events.append(f"Mech {unit.type} destroyed at ({x},{y})")

    if tile.terrain == "building" and tile.building_hp > 0 and damage > 0:
        tile.building_hp -= 1
        result.buildings_damaged += 1
        if tile.building_hp <= 0:
            tile.terrain = "rubble"
            result.buildings_lost += 1
            result.grid_damage += 1
            result.events.append(f"Building destroyed at ({x},{y})")


def apply_push(board: Board, x: int, y: int, direction: int,
               result: ActionResult) -> None:
    """Push unit at (x, y) in the given direction."""
    unit = board.unit_at(x, y)
    if unit is None:
        return
    if not unit.pushable and not unit.is_mech:
        return  # non-pushable non-mech (e.g., Psions)
    # Mechs are massive but still pushable by other mechs' weapons

    dest = push_destination(x, y, direction, board)
    if dest is None:
        # Bump damage: pushed into obstacle = 1 damage to the pushed unit
        apply_damage(board, x, y, 1, result, "bump")
        result.events.append(f"Bump: {unit.type} at ({x},{y}) blocked dir={DIR_NAMES[direction]}")
        return

    nx, ny = dest
    unit.x, unit.y = nx, ny
    tile = board.tile(nx, ny)

    # Check deadly terrain
    if tile.terrain in TERRAIN_DEADLY_GROUND and not unit.flying:
        unit.hp = 0
        if unit.is_enemy:
            result.enemies_killed += 1
            result.events.append(f"{unit.type} pushed into {tile.terrain} at ({nx},{ny})")
        elif unit.is_player:
            result.mechs_killed += 1

    result.events.append(f"Pushed {unit.type} ({x},{y})->({nx},{ny})")


def simulate_weapon(
    board: Board,
    attacker: Unit,
    weapon_id: str,
    target_x: int,
    target_y: int,
) -> ActionResult:
    """Simulate firing a weapon at a target.

    Modifies the board in-place. Returns an ActionResult with stats.
    """
    result = ActionResult()
    wdef = get_weapon_def(weapon_id)

    if wdef is None:
        result.events.append(f"Unknown weapon: {weapon_id}")
        return result

    ax, ay = attacker.x, attacker.y
    attack_dir = direction_between(ax, ay, target_x, target_y)

    if wdef.weapon_type == "melee":
        _sim_melee(board, attacker, wdef, target_x, target_y, attack_dir, result)
    elif wdef.weapon_type == "projectile":
        _sim_projectile(board, attacker, wdef, attack_dir, result)
    elif wdef.weapon_type == "artillery":
        _sim_artillery(board, attacker, wdef, target_x, target_y, result)
    elif wdef.weapon_type == "self_aoe":
        _sim_self_aoe(board, attacker, wdef, result)
    elif wdef.weapon_type in ("pull", "swap"):
        _sim_pull_or_swap(board, attacker, wdef, target_x, target_y, attack_dir, result)
    elif wdef.weapon_type == "charge":
        _sim_charge(board, attacker, wdef, attack_dir, result)
    elif wdef.weapon_type == "leap":
        _sim_leap(board, attacker, wdef, target_x, target_y, result)
    elif wdef.weapon_type == "laser":
        _sim_laser(board, attacker, wdef, attack_dir, result)

    # Self damage
    if wdef.self_damage > 0:
        apply_damage(board, attacker.x, attacker.y, wdef.self_damage, result, "self")

    # Push self backward
    if wdef.push_self and attack_dir is not None:
        apply_push(board, attacker.x, attacker.y, opposite_dir(attack_dir), result)

    return result


def _sim_melee(board, attacker, wdef, tx, ty, attack_dir, result):
    """Simulate melee weapon (adjacent tile hit + push)."""
    apply_damage(board, tx, ty, wdef.damage, result)

    if attack_dir is not None and wdef.push != "none":
        if wdef.push == "forward":
            apply_push(board, tx, ty, attack_dir, result)
        elif wdef.push == "flip" and attack_dir is not None:
            # Flip reverses the unit's attack direction
            apply_push(board, tx, ty, opposite_dir(attack_dir), result)
        elif wdef.push == "backward":
            # Vice Fist: fling target behind attacker
            opp = opposite_dir(attack_dir)
            apply_push(board, tx, ty, opp, result)
        elif wdef.push == "perpendicular":
            # Right Hook: push perpendicular
            perp = (attack_dir + 1) % 4
            apply_push(board, tx, ty, perp, result)

    if wdef.fire:
        board.tile(tx, ty).on_fire = True

    # Sword/spear: also hit perpendicular tiles
    if wdef.aoe_perpendicular and attack_dir is not None:
        perp1 = (attack_dir + 1) % 4
        perp2 = (attack_dir + 3) % 4
        for p in [perp1, perp2]:
            px, py = tx + DIRS[p][0], ty + DIRS[p][1]
            if board.in_bounds(px, py):
                apply_damage(board, px, py, wdef.damage, result)
                if wdef.push == "forward":
                    apply_push(board, px, py, attack_dir, result)


def _sim_projectile(board, attacker, wdef, attack_dir, result):
    """Simulate projectile weapon (fires in line, hits first obstacle)."""
    if attack_dir is None:
        return

    dx, dy = DIRS[attack_dir]
    ax, ay = attacker.x, attacker.y

    # Find first hit
    hit_x, hit_y = -1, -1
    for i in range(1, 8):
        nx, ny = ax + dx * i, ay + dy * i
        if not board.in_bounds(nx, ny):
            break
        tile = board.tile(nx, ny)
        if tile.terrain == "mountain":
            break
        if tile.terrain == "building" and tile.building_hp > 0 and not wdef.phase:
            hit_x, hit_y = nx, ny
            break
        unit = board.unit_at(nx, ny)
        if unit is not None:
            hit_x, hit_y = nx, ny
            break

    if hit_x >= 0:
        apply_damage(board, hit_x, hit_y, wdef.damage, result)
        if wdef.push == "forward":
            apply_push(board, hit_x, hit_y, attack_dir, result)
        elif wdef.push == "backward":
            apply_push(board, hit_x, hit_y, opposite_dir(attack_dir), result)
        if wdef.acid:
            unit = board.unit_at(hit_x, hit_y)
            if unit:
                pass  # TODO: acid status

    # Mirror shot: also fire backward
    if wdef.aoe_behind:
        opp = opposite_dir(attack_dir)
        odx, ody = DIRS[opp]
        for i in range(1, 8):
            nx, ny = ax + odx * i, ay + ody * i
            if not board.in_bounds(nx, ny):
                break
            tile = board.tile(nx, ny)
            if tile.terrain == "mountain":
                break
            if tile.terrain == "building" and tile.building_hp > 0:
                hit_x, hit_y = nx, ny
                break
            unit = board.unit_at(nx, ny)
            if unit is not None:
                apply_damage(board, nx, ny, wdef.damage, result)
                if wdef.push == "forward":
                    apply_push(board, nx, ny, opp, result)
                break


def _sim_artillery(board, attacker, wdef, tx, ty, result):
    """Simulate artillery weapon (arcs over obstacles, hits target area)."""
    # Center damage
    if wdef.aoe_center:
        apply_damage(board, tx, ty, wdef.damage, result)

    if wdef.fire:
        board.tile(tx, ty).on_fire = True
    if wdef.freeze:
        unit = board.unit_at(tx, ty)
        if unit:
            pass  # TODO: freeze status
    if wdef.shield:
        pass  # TODO: shield status

    # Adjacent tile effects (push outward)
    if wdef.aoe_adjacent:
        for i, (dx, dy) in enumerate(DIRS):
            nx, ny = tx + dx, ty + dy
            if not board.in_bounds(nx, ny):
                continue
            apply_damage(board, nx, ny, wdef.damage_outer, result)
            if wdef.push == "outward":
                apply_push(board, nx, ny, i, result)


def _sim_self_aoe(board, attacker, wdef, result):
    """Simulate self-centered AoE (repulse, area blast)."""
    ax, ay = attacker.x, attacker.y

    for i, (dx, dy) in enumerate(DIRS):
        nx, ny = ax + dx, ay + dy
        if not board.in_bounds(nx, ny):
            continue
        apply_damage(board, nx, ny, wdef.damage, result)
        if wdef.push == "outward":
            apply_push(board, nx, ny, i, result)
        elif wdef.push == "inward":
            apply_push(board, nx, ny, opposite_dir(i), result)


def _sim_pull_or_swap(board, attacker, wdef, tx, ty, attack_dir, result):
    """Simulate pull (attract shot, grav well) or swap (teleporter)."""
    if wdef.weapon_type == "swap":
        target = board.unit_at(tx, ty)
        if target:
            # Swap positions
            target.x, target.y, attacker.x, attacker.y = \
                attacker.x, attacker.y, target.x, target.y
            result.events.append(f"Swapped {attacker.type} <-> {target.type}")
        else:
            # Teleport self to empty tile
            attacker.x, attacker.y = tx, ty
            result.events.append(f"Teleported {attacker.type} to ({tx},{ty})")
        return

    # Pull: move target toward attacker
    if attack_dir is None:
        return
    target = board.unit_at(tx, ty)
    if target and target.pushable:
        pull_dir = opposite_dir(attack_dir)
        apply_push(board, tx, ty, pull_dir, result)


def _sim_charge(board, attacker, wdef, attack_dir, result):
    """Simulate charge weapon (rush forward until hitting something)."""
    if attack_dir is None:
        return

    dx, dy = DIRS[attack_dir]
    ax, ay = attacker.x, attacker.y

    # Find where we stop
    last_free_x, last_free_y = ax, ay
    hit_x, hit_y = -1, -1

    for i in range(1, 8):
        nx, ny = ax + dx * i, ay + dy * i
        if not board.in_bounds(nx, ny):
            break

        tile = board.tile(nx, ny)
        if tile.terrain == "mountain":
            break
        if tile.terrain == "building" and tile.building_hp > 0:
            hit_x, hit_y = nx, ny
            break
        if not wdef.flying_charge and tile.terrain in ("water", "chasm", "lava"):
            break

        unit = board.unit_at(nx, ny)
        if unit is not None:
            hit_x, hit_y = nx, ny
            break

        last_free_x, last_free_y = nx, ny

    # Move attacker to last free tile
    attacker.x, attacker.y = last_free_x, last_free_y

    # Deal damage to hit target
    if hit_x >= 0:
        apply_damage(board, hit_x, hit_y, wdef.damage, result)
        if wdef.push == "forward":
            apply_push(board, hit_x, hit_y, attack_dir, result)


def _sim_leap(board, attacker, wdef, tx, ty, result):
    """Simulate leap weapon (jump to target, AoE on landing)."""
    old_x, old_y = attacker.x, attacker.y
    attacker.x, attacker.y = tx, ty

    # Damage adjacent tiles on landing (not the tile we came from)
    from_dir = direction_between(tx, ty, old_x, old_y)
    for i, (dx, dy) in enumerate(DIRS):
        if i == from_dir:
            continue  # skip the tile we jumped from
        nx, ny = tx + dx, ty + dy
        if not board.in_bounds(nx, ny):
            continue
        apply_damage(board, nx, ny, wdef.damage, result)
        if wdef.push == "outward":
            apply_push(board, nx, ny, i, result)


def _sim_laser(board, attacker, wdef, attack_dir, result):
    """Simulate laser beam (hits all tiles in line, decreasing damage)."""
    if attack_dir is None:
        return

    dx, dy = DIRS[attack_dir]
    ax, ay = attacker.x, attacker.y
    dmg = wdef.damage

    for i in range(1, 8):
        nx, ny = ax + dx * i, ay + dy * i
        if not board.in_bounds(nx, ny):
            break

        tile = board.tile(nx, ny)
        # Beam stops at mountains
        if tile.terrain == "mountain":
            apply_damage(board, nx, ny, dmg, result)
            break
        # Beam stops at buildings (hits them)
        if tile.terrain == "building" and tile.building_hp > 0:
            apply_damage(board, nx, ny, dmg, result)
            break

        apply_damage(board, nx, ny, dmg, result)
        dmg = max(1, dmg - 1)  # damage decreases per tile


def simulate_action(
    board: Board,
    mech: Unit,
    move_to: tuple[int, int],
    weapon_id: str,
    target: tuple[int, int],
) -> ActionResult:
    """Simulate a complete mech action: move + attack.

    Modifies the board in-place.
    """
    # Move
    mech.x, mech.y = move_to

    # Collect pod if on one
    result = ActionResult()
    tile = board.tile(mech.x, mech.y)
    if tile.has_pod:
        tile.has_pod = False
        result.pods_collected += 1
        result.events.append(f"Collected pod at ({mech.x},{mech.y})")

    # Attack
    if weapon_id and target[0] >= 0:
        attack_result = simulate_weapon(board, mech, weapon_id, target[0], target[1])
        # Merge results
        result.buildings_lost += attack_result.buildings_lost
        result.buildings_damaged += attack_result.buildings_damaged
        result.grid_damage += attack_result.grid_damage
        result.enemies_killed += attack_result.enemies_killed
        result.enemy_damage_dealt += attack_result.enemy_damage_dealt
        result.mech_damage_taken += attack_result.mech_damage_taken
        result.mechs_killed += attack_result.mechs_killed
        result.events.extend(attack_result.events)

    mech.active = False
    return result
