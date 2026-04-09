"""Simulate weapon effects on the board.

Given a unit, weapon, and target, compute the resulting board state:
damage dealt, units pushed, status effects applied, buildings destroyed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.model.board import Board, Unit, TERRAIN_DEADLY_GROUND
from src.model.weapons import get_weapon_def, WeaponDef
from src.solver.movement import (
    DIRS, DIR_NAMES, direction_between, opposite_dir,
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


def _apply_death_explosion(board: Board, x: int, y: int, dead_type: str,
                           result: ActionResult, depth: int = 0) -> None:
    """Apply Blast Psion death explosion: 1 damage to all 4 adjacent tiles.

    Triggered when an enemy Vek dies while a Blast Psion is alive on the board.
    The Blast Psion itself does NOT explode (it grants the effect to others).
    Chain reactions are supported with a depth limit to prevent infinite loops.
    """
    if depth > 8:
        return  # safety limit for chain reactions

    result.events.append(f"Death explosion at ({x},{y}) from {dead_type}")

    for dx, dy in DIRS:
        nx, ny = x + dx, y + dy
        if not board.in_bounds(nx, ny):
            continue

        # Check for chain kills BEFORE applying damage
        adj_unit = board.unit_at(nx, ny)
        adj_was_alive = adj_unit and adj_unit.hp > 0 and adj_unit.is_enemy if adj_unit else False
        adj_type = adj_unit.type if adj_unit else ""

        # Explosion damage (1, treated like bump — ignores armor/acid)
        apply_damage(board, nx, ny, 1, result, "bump")

        # Chain reaction: if an enemy just died from this explosion, it also explodes
        if adj_was_alive and adj_unit.hp <= 0:
            # Check if blast psion is still alive (killing it stops future explosions)
            psion_alive = any(
                u.type == "Jelly_Explode1" and u.hp > 0
                for u in board.units
            )
            if psion_alive and adj_type != "Jelly_Explode1":
                _apply_death_explosion(board, nx, ny, adj_type, result, depth + 1)


def apply_damage(board: Board, x: int, y: int, damage: int,
                 result: ActionResult, source: str = "") -> None:
    """Apply damage to whatever is at (x, y).

    Args:
        source: "bump" for push/bump damage (ignores Armor and ACID),
                "fire" for fire damage (ignores Armor and ACID),
                "" for normal weapon damage (reduced by Armor, doubled by ACID).
    """
    if not board.in_bounds(x, y):
        return

    unit = board.unit_at(x, y)
    tile = board.tile(x, y)

    if unit and damage > 0:
        was_alive = unit.hp > 0
        # Shield blocks one damage instance (any source except chasm/deadly)
        # and prevents negative status effects. Consumed after blocking.
        if unit.shield:
            unit.shield = False
            result.events.append(f"Shield absorbed {damage} damage on {unit.type} at ({x},{y})")
        elif unit.frozen:
            # Frozen units are invincible: any damage unfreezes dealing 0 damage.
            # Exception: fire unfreezes AND sets on fire (handled separately).
            unit.frozen = False
            result.events.append(f"Unfroze {unit.type} at ({x},{y}) (damage negated)")
        else:
            actual = damage
            # Bump and fire damage ignore Armor and ACID
            if source not in ("bump", "fire"):
                if unit.acid:
                    # ACID disables armor entirely and doubles weapon damage.
                    # Also applies to self-damage from weapons (source="self").
                    actual = damage * 2
                elif unit.armor:
                    actual = max(0, damage - 1)
            unit.hp -= actual

            if unit.is_enemy:
                result.enemy_damage_dealt += actual
                if unit.hp <= 0:
                    result.enemies_killed += 1
                    result.events.append(f"Killed {unit.type} at ({x},{y})")
                    # Shell Psion killed: remove armor aura from all Vek
                    if board.armor_psion_active and unit.type == "Jelly_Armor1":
                        other_alive = any(
                            u.type == "Jelly_Armor1" and u.hp > 0 and u is not unit
                            for u in board.units
                        )
                        if not other_alive:
                            board.armor_psion_active = False
                            for other in board.units:
                                if other.is_enemy:
                                    other.armor = False
                    # Blast Psion death explosion: all Vek explode on death
                    if (was_alive and board.blast_psion_active
                            and unit.type != "Jelly_Explode1"):
                        _apply_death_explosion(board, x, y, unit.type, result)
            elif unit.is_player:
                result.mech_damage_taken += actual
                if unit.hp <= 0:
                    result.mechs_killed += 1
                    result.events.append(f"Mech {unit.type} destroyed at ({x},{y})")

    if tile.terrain == "building" and tile.building_hp > 0 and damage > 0:
        # Buildings take full weapon damage (each HP lost = 1 grid power)
        actual_bldg = damage if source not in ("bump",) else 1
        old_hp = tile.building_hp
        tile.building_hp = max(0, tile.building_hp - actual_bldg)
        hp_lost = old_hp - tile.building_hp
        result.buildings_damaged += hp_lost
        result.grid_damage += hp_lost
        board.grid_power = max(0, board.grid_power - hp_lost)
        if tile.building_hp <= 0:
            tile.terrain = "rubble"
            result.buildings_lost += 1
            result.events.append(f"Building destroyed at ({x},{y}) ({hp_lost} grid damage)")
        elif hp_lost > 0:
            result.events.append(f"Building damaged at ({x},{y}) ({hp_lost} grid damage)")

    # Ice tile destruction: ice → cracked → water
    # Fire attacks skip cracked and go straight to water.
    if tile.terrain == "ice" and damage > 0:
        if tile.cracked or source == "fire":
            tile.terrain = "water"
            tile.cracked = False
            result.events.append(f"Ice broke into water at ({x},{y})")
            # If there's a non-flying unit on the tile, it drowns
            if unit and unit.hp > 0 and not unit.flying:
                unit.hp = 0
                if unit.is_enemy:
                    result.enemies_killed += 1
                    result.events.append(f"{unit.type} drowned at ({x},{y})")
        else:
            tile.cracked = True
            result.events.append(f"Ice cracked at ({x},{y})")


def apply_push(board: Board, x: int, y: int, direction: int,
               result: ActionResult) -> None:
    """Push unit at (x, y) one tile in the given direction.

    Game rules for push:
    - Damage and push are SIMULTANEOUS — a unit killed by the weapon's
      damage is still pushed (its corpse collides with obstacles).
    - If destination is empty ground: unit moves there
    - If destination is deadly terrain (water/chasm/lava): unit moves there
      and dies (non-flying ground units). Flying units survive water/chasm.
    - If destination is blocked (edge, mountain, building, or another unit):
      the pushed unit takes 1 bump damage and does NOT move.
      If blocked by another unit, BOTH units take 1 bump damage.
    - If blocked by a building, BOTH the unit AND building take 1 bump damage.
    - Bump damage ignores Armor and ACID (source="bump").
    - Mountains take 1 damage when bumped into (2 HP, becomes rubble at 0).
    - There is NO chain pushing: A pushed into B = collision, B stays.
    """
    # Use _any_ unit at this tile, including dead (hp<=0).
    # In ITB, damage and push are simultaneous — a killed unit still
    # gets pushed and can bump into buildings/units.
    unit = None
    for u in board.units:
        if u.x == x and u.y == y:
            unit = u
            break
    if unit is None:
        return
    if not unit.pushable and not unit.is_mech:
        return  # non-pushable non-mech units are immune to push

    dx, dy = DIRS[direction]
    nx, ny = x + dx, y + dy

    # Blocked by map edge
    if not board.in_bounds(nx, ny):
        apply_damage(board, x, y, 1, result, "bump")
        result.events.append(
            f"Bump: {unit.type} at ({x},{y}) blocked by edge"
        )
        return

    tile_dest = board.tile(nx, ny)

    # Blocked by mountain — pushed unit takes bump, mountain takes 1 damage
    if tile_dest.terrain == "mountain":
        apply_damage(board, x, y, 1, result, "bump")
        tile_dest.building_hp = getattr(tile_dest, 'building_hp', 2)
        if tile_dest.building_hp > 0:
            tile_dest.building_hp -= 1
        if tile_dest.building_hp <= 0:
            tile_dest.terrain = "rubble"
            result.events.append(f"Mountain destroyed at ({nx},{ny})")
        result.events.append(
            f"Bump: {unit.type} at ({x},{y}) blocked by mountain"
        )
        return

    # Blocked by building — pushed unit takes bump, building ALSO takes bump damage
    if tile_dest.terrain == "building" and tile_dest.building_hp > 0:
        apply_damage(board, x, y, 1, result, "bump")
        # Building takes bump damage too (empirically verified)
        tile_dest.building_hp -= 1
        board.grid_power = max(0, board.grid_power - 1)
        if tile_dest.building_hp <= 0:
            result.grid_damage += 1
            result.events.append(
                f"Bump: building at ({nx},{ny}) destroyed by collision"
            )
        else:
            result.events.append(
                f"Bump: building at ({nx},{ny}) damaged by collision"
            )
        result.events.append(
            f"Bump: {unit.type} at ({x},{y}) blocked by building at ({nx},{ny})"
        )
        return

    # Blocked by another unit — BOTH take 1 bump damage, neither moves
    blocker = board.unit_at(nx, ny)
    if blocker is not None:
        apply_damage(board, x, y, 1, result, "bump")
        apply_damage(board, nx, ny, 1, result, "bump")
        result.events.append(
            f"Bump: {unit.type} at ({x},{y}) collided with "
            f"{blocker.type} at ({nx},{ny})"
        )
        return

    # Destination is clear — move the unit
    unit.x, unit.y = nx, ny

    # Check deadly terrain after moving
    # Frozen flying units are grounded — they drown in water/chasm/lava
    effectively_flying = unit.flying and not unit.frozen
    if tile_dest.terrain in TERRAIN_DEADLY_GROUND and not effectively_flying:
        unit.hp = 0
        if unit.is_enemy:
            result.enemies_killed += 1
            # Blast Psion: Vek dying in deadly terrain also explodes
            if (board.blast_psion_active
                    and unit.type != "Jelly_Explode1"):
                _apply_death_explosion(board, nx, ny, unit.type, result)
        elif unit.is_player:
            result.mechs_killed += 1
        result.events.append(
            f"{unit.type} pushed into {tile_dest.terrain} at ({nx},{ny})"
        )
    else:
        result.events.append(f"Pushed {unit.type} ({x},{y})->({nx},{ny})")
        # Check environment danger: unit won't die now, but will when
        # the environment resolves at end of turn (tidal wave, air strike)
        if (hasattr(board, 'environment_danger') and board.environment_danger
                and (nx, ny) in board.environment_danger and not unit.flying):
            result.events.append(
                f"{unit.type} on danger tile ({nx},{ny}) -- will die at end of turn"
            )


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
        _sim_artillery(board, attacker, wdef, target_x, target_y, attack_dir, result)
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

    # TargetBehind: also hit the tile behind the target (Alpha Hornet)
    if wdef.aoe_behind and attack_dir is not None:
        dx, dy = DIRS[attack_dir]
        bx, by = tx + dx, ty + dy
        if board.in_bounds(bx, by):
            apply_damage(board, bx, by, wdef.damage, result)
            result.events.append(
                f"Behind-hit at ({bx},{by}) for {wdef.damage}"
            )

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


def _sim_artillery(board, attacker, wdef, tx, ty, attack_dir, result):
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

    # Behind tile damage (Old Earth Artillery: hits target + tile behind)
    if wdef.aoe_behind and attack_dir is not None:
        dx, dy = DIRS[attack_dir]
        bx, by = tx + dx, ty + dy
        if board.in_bounds(bx, by):
            apply_damage(board, bx, by, wdef.damage, result)

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

    # Repair action
    if weapon_id == "_REPAIR":
        healed = min(1, mech.max_hp - mech.hp)
        mech.hp = min(mech.hp + 1, mech.max_hp)
        mech.fire = False
        mech.acid = False
        result.events.append(
            f"{mech.type} repaired at ({mech.x},{mech.y})"
            f" (+{healed} HP, cleared fire/acid)")
        mech.active = False
        return result

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
