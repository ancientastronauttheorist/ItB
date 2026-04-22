"""Solver data types (MechAction, Solution) and replay infrastructure.

The actual search is performed by the Rust solver (itb_solver module).
This module provides:
  - MechAction / Solution dataclasses used across the codebase
  - replay_solution() for post-solve verification snapshots
  - Enemy attack simulation for replay predictions
"""

from __future__ import annotations

import os
import sys
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

    INVARIANT: enemy.queued_target is the first tile in the attack direction
    from the enemy's ORIGINAL position (queued_target - orig = unit cardinal
    vector). The bridge normalizes piQueuedShot against piOrigin so this
    invariant holds even when the enemy moved between queueing and firing.

    If the projectile walks off the board without hitting anything, fall
    back to the last valid tile — matches the game's GetProjectileEnd.

    Returns (hit_x, hit_y) of first unit/mountain/building or last valid
    tile, or (-1, -1) if no attack resolves.
    """
    if enemy.queued_target_x < 0:
        return -1, -1

    # Compute direction from ORIGINAL position to queued target
    ox = orig_x if orig_x >= 0 else enemy.x
    oy = orig_y if orig_y >= 0 else enemy.y
    dx = enemy.queued_target_x - ox
    dy = enemy.queued_target_y - oy
    if dx != 0:
        dx = 1 if dx > 0 else -1
    if dy != 0:
        dy = 1 if dy > 0 else -1

    # Must be a valid cardinal direction (exactly one axis non-zero)
    if (dx != 0 and dy != 0) or (dx == 0 and dy == 0):
        return -1, -1

    # Trace from CURRENT position in the original direction. If projectile
    # exits the board without hitting anything, return last valid tile.
    last_valid = (-1, -1)
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
        last_valid = (nx, ny)
    return last_valid


def _apply_charge_push(board: Board, x: int, y: int, dx: int, dy: int) -> None:
    """Push the unit at (x,y) one tile in direction (dx,dy). Buildings and
    non-pushable units absorb 1 bump damage instead of moving. Mirrors the
    Rust apply_push for the enemy-charge path — intentionally minimal
    (ignores chain pushes and swap-into-water nuances)."""
    u = board.unit_at(x, y)
    if u is None:
        # Building target: bump damage already handled by main hit
        return
    if not u.pushable and not u.is_mech:
        return
    nx, ny = x + dx, y + dy
    if not board.in_bounds(nx, ny):
        u.hp = max(0, u.hp - 1)
        return
    t = board.tile(nx, ny)
    if t.terrain == "mountain" or (t.terrain == "building" and t.building_hp > 0):
        u.hp = max(0, u.hp - 1)
        return
    if board.unit_at(nx, ny) is not None:
        u.hp = max(0, u.hp - 1)
        return
    u.x = nx
    u.y = ny


def _spawn_from_artillery(board: Board, x: int, y: int, weapon_id: str) -> None:
    """Spawn egg/blob unit when a Spider/Blobber artillery resolves.

    Mirrors the Rust `spawn_enemy` helper. Called from the artillery
    branch after damage is applied. No-op for all non-spawn weapons.
    The target tile must be clear (no live unit) and on terrain a small
    Vek can stand on — buildings, mountains, water, chasm, and lava
    reject the spawn (the in-game egg/blob silently fails to place).
    """
    spawn_type = None
    spawn_hp = 1
    if weapon_id in ("SpiderAtk1", "SpiderAtk2"):
        spawn_type = "WebbEgg1"
    elif weapon_id == "BlobberAtk1":
        spawn_type = "Blob1"
    elif weapon_id == "BlobberAtk2":
        spawn_type = "Blob2"
    else:
        return
    if not board.in_bounds(x, y):
        return
    if board.unit_at(x, y) is not None:
        return
    t = board.tile(x, y)
    if t.terrain in ("building", "mountain", "water", "chasm", "lava"):
        return
    # UID in 9000+ range to avoid colliding with bridge UIDs.
    existing_uids = [u.uid for u in board.units]
    new_uid = max([9000] + [uid for uid in existing_uids if uid >= 9000]) + 1
    from src.model.board import Unit as _U
    board.units.append(_U(
        uid=new_uid,
        type=spawn_type,
        x=x, y=y,
        hp=spawn_hp, max_hp=spawn_hp,
        team=6,  # enemy
        is_mech=False,
        move_speed=0,
        flying=False, massive=False, armor=False, pushable=True,
        weapon="",
        queued_target_x=x, queued_target_y=y,
    ))


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
    Shield blocks the unit-side negative status without being consumed here
    (the shield consumption path is in apply_damage). Tile-side acid still
    lands regardless of shield — the projectile splashes on the tile even
    if the unit is shielded.
    """
    if wdef is None:
        return
    if not board.in_bounds(x, y):
        return

    # Tile-side: acid weapon on liquid/ground terrain creates a persistent
    # A.C.I.D. Tile (water) or A.C.I.D. Pool (ground/rubble). Observed in
    # game: Alpha Centipede Corrosive Vomit splash on water converts it.
    if getattr(wdef, 'acid', False):
        tile = board.tile(x, y)
        if tile.terrain in ("water", "ground", "rubble"):
            tile.acid = True

    # Unit-side: ACID / WEB applied only to a living unit whose shield
    # isn't up. Web tracks the attacker UID so web-break-on-push/kill works.
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
            # Deadly Threat (Air Strike, Lightning, Cataclysm→chasm, Seismic→chasm,
            # Tidal→water): sets HP=0 outright. Bypasses shield/frozen/armor/ACID.
            # Hits flying units too — air strikes drop bombs from above, lightning
            # arcs down. Matches rust_solver/src/enemy.rs::apply_env_danger.
            if u:
                u.hp = 0
                u.shield = False
                u.frozen = False
            # Also destroy buildings on lethal env tiles
            tile = board.tile(dx, dy)
            if tile.terrain == "building" and tile.building_hp > 0:
                lost = tile.building_hp
                tile.building_hp = 0
                tile.terrain = "rubble"
                board.grid_power = max(0, board.grid_power - lost)
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
        # Spider/Arachnid eggs don't attack — they transform into Spiderlings
        # on their turn. Their queued_target is their own tile (hatch marker),
        # which would otherwise be processed as a self-hit melee attack.
        # Covers WebbEgg* (Hive) and SpiderlingEgg* (SpiderBoss finale),
        # plus any future egg type whose name contains "Egg".
        if (enemy.type.startswith("WebbEgg")
                or enemy.type.startswith("SpiderlingEgg")
                or "Egg" in enemy.type):
            continue
        if enemy.queued_target_x < 0:
            # PHANTOM-ATTACK GUARD: Vek reports has_queued_attack=true
            # but Lua bridge failed to populate a target. Don't silently
            # skip — apply conservative damage to the nearest building so
            # the scorer penalizes plans that ignore this Vek.
            # See CLAUDE.md §21 grid-drop investigation gate.
            if getattr(enemy, "has_queued_attack", False):
                dmg = enemy.weapon_damage if enemy.weapon_damage > 0 else 1
                # Warning suppressed in hot path — see enemy.rs note.
                # Re-enable with ITB_LOG_PHANTOM_ATTACK=1.
                if os.environ.get("ITB_LOG_PHANTOM_ATTACK"):
                    print(
                        f"WARN: Vek {enemy.uid} ({enemy.type}) "
                        f"has_queued_attack=true but no target — "
                        f"applying conservative damage",
                        file=sys.stderr,
                    )
                # Nearest building (Chebyshev distance).
                best = None
                best_d = 999
                for bx in range(8):
                    for by in range(8):
                        tile = board.tile(bx, by)
                        if tile.terrain == "building" and tile.building_hp > 0:
                            d = max(abs(bx - enemy.x), abs(by - enemy.y))
                            if d < best_d:
                                best_d = d
                                best = (bx, by)
                if best is not None:
                    grid_lost = _apply_enemy_hit(board, best[0], best[1], dmg)
                    buildings_destroyed += grid_lost
            continue

        # Smoke cancels attacks: enemy on a smoke tile cannot attack
        # (Eggs are Smoke-immune, but they're skipped above anyway.)
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
        # Unknown-enemy fallback: boss/leader types get a 3-dmg template
        # (mirrors Rust fallback — see rust_solver/src/enemy.rs). A blank
        # 1-dmg melee underestimates unmapped bosses by 3x and has caused
        # grid losses on finale missions.
        _is_big = wdef is None and (
            "Boss" in enemy.type or "Leader" in enemy.type)
        damage = enemy.weapon_damage if enemy.weapon_damage > 0 else (
            wdef.damage if wdef else (3 if _is_big else 1))
        weapon_type = wdef.weapon_type if wdef else (
            "projectile" if _is_big else "melee")

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

        elif weapon_type == "charge":
            # Charge: scans tiles from current pos in original queued direction
            # until a blocker (unit / building / mountain). Damages blocker.
            # For Flaming Abdomen (fire=True): lights every PASSED tile on
            # fire, excluding the final resting tile. For push="forward":
            # pushes the target in the charge direction.
            orig = original_positions.get(enemy.uid)
            ox, oy = (orig[0], orig[1]) if orig else (enemy.x, enemy.y)
            dx_raw = enemy.queued_target_x - ox
            dy_raw = enemy.queued_target_y - oy
            dx = (dx_raw > 0) - (dx_raw < 0)
            dy = (dy_raw > 0) - (dy_raw < 0)
            if (dx != 0) == (dy != 0):
                continue  # Not a cardinal direction — skip

            hit = None
            hit_i = 0
            for i in range(1, 8):
                nx = enemy.x + dx * i
                ny = enemy.y + dy * i
                if not board.in_bounds(nx, ny):
                    break
                t = board.tile(nx, ny)
                if t.terrain == "mountain":
                    hit = (nx, ny); hit_i = i; break
                if t.terrain in ("chasm",) and not t.terrain == "ground":
                    # Deadly ground doesn't block charge (charger dies)
                    pass
                if t.terrain == "building" and t.building_hp > 0:
                    hit = (nx, ny); hit_i = i; break
                if board.unit_at(nx, ny) is not None:
                    hit = (nx, ny); hit_i = i; break

            if hit is not None:
                hx, hy = hit
                # Fire trail: tiles i=1..(hit_i-2) inclusive (excludes final resting)
                if wdef and getattr(wdef, 'fire', False):
                    for i in range(1, hit_i - 1):
                        fx = enemy.x + dx * i
                        fy = enemy.y + dy * i
                        board.tile(fx, fy).fire = True
                        fu = board.unit_at(fx, fy)
                        if fu is not None and not fu.frozen:
                            fu.fire = True

                grid_lost = _apply_enemy_hit(board, hx, hy, damage)
                buildings_destroyed += grid_lost
                _apply_enemy_weapon_status(board, hx, hy, wdef, enemy.uid)

                # Forward push on target (mirrors Rust Charge+Forward handler).
                # Simple implementation: if tile behind-target (in charge dir)
                # is clear and in-bounds, move pushed unit there. Otherwise
                # bump damage. Buildings can't be pushed.
                if wdef and getattr(wdef, 'push', None) == 'forward':
                    _apply_charge_push(board, hx, hy, dx, dy)

        elif weapon_type == "melee":
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

        elif weapon_type == "artillery":
            # Artillery preserves its ORIGINAL OFFSET from the attacker when
            # the attacker is pushed. The queued target is a direction+distance
            # stored relative to the enemy — pushing the enemy shifts the
            # target tile by the same delta (confirmed empirically in Rust
            # sim: push Alpha Scarab D3→C3 with D7 original target → C7).
            orig = original_positions.get(enemy.uid)
            ox, oy = (orig[0], orig[1]) if orig else (enemy.x, enemy.y)
            offset_x = enemy.queued_target_x - ox
            offset_y = enemy.queued_target_y - oy
            tx = enemy.x + offset_x
            ty = enemy.y + offset_y
            if not board.in_bounds(tx, ty):
                continue
            # Cardinal axis required (exactly one axis non-zero)
            dx_sign = (offset_x > 0) - (offset_x < 0)
            dy_sign = (offset_y > 0) - (offset_y < 0)
            if (dx_sign != 0) == (dy_sign != 0):
                continue
            # Min-range check against the (new) attacker→target distance.
            curr_range = abs(offset_x) + abs(offset_y)
            if wdef and curr_range < wdef.range_min:
                continue
            grid_lost = _apply_enemy_hit(board, tx, ty, damage)
            buildings_destroyed += grid_lost
            _apply_enemy_weapon_status(board, tx, ty, wdef, enemy.uid)

            # Spawn-artillery side effect: Spider (eggs) and Blobber
            # (blobs) fire a 0-dmg artillery whose in-game effect is
            # placing a unit at the target tile. Mirrors the Rust
            # spawn_enemy logic in rust_solver/src/enemy.rs.
            _spawn_from_artillery(board, tx, ty, enemy.weapon)

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

    _simulate_train_advance(board)

    # Grid Defense expected save: each grid point lost had a
    # grid_defense_pct/100 chance to be blocked. Stored as float on the
    # board for the evaluator. Without this the solver over-predicts
    # building loss by ~1 grid/turn at the 15% baseline.
    gd = getattr(board, "grid_defense_pct", 15)
    board.enemy_grid_save_expected = buildings_destroyed * (gd / 100.0)

    return buildings_destroyed


def _simulate_train_advance(board: Board) -> None:
    """Advance the Supply Train 2 tiles forward. End of enemy phase.

    Forward direction is inferred from the two Train_Pawn tile entries
    sharing a uid (primary - extra). The train is destroyed (both tiles
    hp = 0, mirrored) if either entered tile is blocked by a mountain,
    building, or a non-train unit/wreck. Off-board destinations are
    treated as the train reaching the exit — hp stays alive, position
    is not advanced.

    Mirrors rust_solver/src/enemy.rs::simulate_train_advance.
    """
    primary = None
    extra = None
    for u in board.units:
        if u.type != "Train_Pawn" or u.hp <= 0:
            continue
        if u.is_extra_tile:
            extra = u
        else:
            primary = u
    if primary is None or extra is None:
        return

    dx = primary.x - extra.x
    dy = primary.y - extra.y
    if abs(dx) + abs(dy) != 1:
        return

    steps = [(primary.x + dx, primary.y + dy),
             (primary.x + 2 * dx, primary.y + 2 * dy)]
    for nx, ny in steps:
        if not board.in_bounds(nx, ny):
            # Off-board: train reached the exit. Leave alive in place.
            return
        t = board.tile(nx, ny)
        if t.terrain in ("mountain", "building"):
            primary.hp = 0
            extra.hp = 0
            return
        for u in board.units:
            if u.x == nx and u.y == ny and u.type != "Train_Pawn":
                # Any non-train unit (including dead wrecks) blocks.
                primary.hp = 0
                extra.hp = 0
                return

    # Path clear — advance both tiles 2 forward.
    primary.x += 2 * dx
    primary.y += 2 * dy
    extra.x += 2 * dx
    extra.y += 2 * dy


# ── Post-solve replay (verification snapshots) ──────────────────────────


def replay_solution(
    board: Board,
    solution: Solution,
    spawn_pts: list[tuple[int, int]],
    current_turn: int = 0,
    total_turns: int = 5,
    remaining_spawns: int = 2**31 - 1,
    weights=None,
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

    # Score breakdown on predicted post-enemy board — pass the caller's
    # active weights so the recorded breakdown reflects what the solver
    # actually used (active.json), not DEFAULT_WEIGHTS.
    score_breakdown = evaluate_breakdown(b, spawn_pts, kills=total_kills,
                                         current_turn=current_turn,
                                         total_turns=total_turns,
                                         remaining_spawns=remaining_spawns,
                                         weights=weights)

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


