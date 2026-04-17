/// Weapon simulation engine.
///
/// Given a unit, weapon, and target, compute the resulting board state.
/// Ports all 9 weapon types from Python simulate.py with exact semantic parity.

use crate::types::*;
use crate::board::*;
use crate::weapons::*;
use crate::movement::{direction_between, cardinal_direction};

// ── Blast Psion death explosion ──────────────────────────────────────────────

/// Apply death explosion: 1 bump damage to all 4 adjacent tiles.
/// Called when an enemy Vek dies while Blast Psion is alive on the board.
/// Handles chain reactions (explosion kills another Vek → another explosion).
fn apply_death_explosion(board: &mut Board, x: u8, y: u8, result: &mut ActionResult, depth: u8) {
    if depth > 8 { return; } // safety limit for chain reactions

    for &(dx, dy) in &DIRS {
        let nx = x as i8 + dx;
        let ny = y as i8 + dy;
        if nx < 0 || nx >= 8 || ny < 0 || ny >= 8 { continue; }
        let nx = nx as u8;
        let ny = ny as u8;

        // Pre-check: is there an alive non-Psion enemy that could chain-explode?
        let chain_check = if board.blast_psion {
            board.unit_at(nx, ny).and_then(|idx| {
                let u = &board.units[idx];
                if u.is_enemy() && u.hp > 0 && u.type_name_str() != "Jelly_Explode1" {
                    Some(idx)
                } else { None }
            })
        } else { None };

        // Apply 1 bump damage (ignores armor/acid)
        apply_damage_core(board, nx, ny, 1, result, DamageSource::Bump);

        // Chain reaction: if that enemy just died, it also explodes
        if let Some(idx) = chain_check {
            if board.units[idx].hp <= 0 {
                // Check if Blast Psion is still alive (killing it stops future explosions)
                let psion_alive = (0..board.unit_count as usize).any(|i| {
                    board.units[i].type_name_str() == "Jelly_Explode1" && board.units[i].hp > 0
                });
                if psion_alive {
                    apply_death_explosion(board, nx, ny, result, depth + 1);
                }
            }
        }
    }
}

// ── Web break ────────────────────────────────────────────────────────────────

/// Clear the WEB flag on any unit whose web_source_uid matches `src_uid`.
/// Restores move_speed to base_move so the unit can move this turn.
/// Called when an enemy is pushed or killed (both events break ITB grapples).
fn break_web_from(board: &mut Board, src_uid: u16) {
    if src_uid == 0 { return; }
    for i in 0..board.unit_count as usize {
        if board.units[i].web() && board.units[i].web_source_uid == src_uid {
            board.units[i].set_web(false);
            if board.units[i].move_speed == 0 {
                board.units[i].move_speed = board.units[i].base_move;
            }
        }
    }
}

// ── apply_damage ─────────────────────────────────────────────────────────────

/// Internal damage logic without death explosion processing.
/// Used by apply_death_explosion to avoid double-triggering.
fn apply_damage_core(board: &mut Board, x: u8, y: u8, damage: u8, result: &mut ActionResult, source: DamageSource) {
    if damage == 0 { return; }

    // Damage unit if present
    if let Some(idx) = board.unit_at(x, y) {
        let unit = &mut board.units[idx];

        if unit.shield() {
            // Shield absorbs any damage, consumed
            unit.set_shield(false);
        } else if unit.frozen() {
            // Frozen = invincible, damage unfreezes (0 actual damage)
            unit.set_frozen(false);
        } else {
            let actual = match source {
                DamageSource::Bump | DamageSource::Fire => damage as i8,
                _ => {
                    if unit.acid() {
                        (damage * 2) as i8
                    } else if unit.armor() {
                        (damage as i8 - 1).max(0)
                    } else {
                        damage as i8
                    }
                }
            };

            unit.hp -= actual;

            if unit.is_enemy() {
                result.enemy_damage_dealt += actual as i32;
                if unit.hp <= 0 {
                    result.enemies_killed += 1;
                    // Shell Psion killed: remove armor aura from all Vek
                    if board.armor_psion && board.units[idx].type_name_str() == "Jelly_Armor1" {
                        let other_alive = (0..board.unit_count as usize)
                            .any(|j| j != idx
                                && board.units[j].type_name_str() == "Jelly_Armor1"
                                && board.units[j].hp > 0);
                        if !other_alive {
                            board.armor_psion = false;
                            for j in 0..board.unit_count as usize {
                                if board.units[j].is_enemy() {
                                    board.units[j].flags.set(UnitFlags::ARMOR, false);
                                }
                            }
                        }
                    }

                    // Soldier Psion killed: remove +1 HP from all Vek
                    if board.soldier_psion && board.units[idx].type_name_str() == "Jelly_Health1" {
                        board.soldier_psion = false;
                        for j in 0..board.unit_count as usize {
                            if board.units[j].is_enemy() && board.units[j].hp > 0
                                && board.units[j].type_name_str() != "Jelly_Health1"
                            {
                                board.units[j].max_hp -= 1;
                                board.units[j].hp -= 1;
                                if board.units[j].hp <= 0 {
                                    result.enemies_killed += 1;
                                }
                            }
                        }
                    }

                    // Blood Psion killed: stop regen
                    if board.regen_psion && board.units[idx].type_name_str() == "Jelly_Regen1" {
                        board.regen_psion = false;
                    }

                    // Psion Tyrant killed: stop mech damage
                    if board.tyrant_psion && board.units[idx].type_name_str() == "Jelly_Lava1" {
                        board.tyrant_psion = false;
                    }

                    // Boss killed: clear flag for kill bonus in evaluate
                    if board.boss_alive && board.units[idx].type_name_str().contains("Boss") {
                        board.boss_alive = false;
                    }
                }
            } else if unit.is_player() {
                result.mech_damage_taken += actual as i32;
                if unit.hp <= 0 {
                    result.mechs_killed += 1;
                }
            }
        }
    }

    // Acid pool creation: unit with acid dies → acid pool on tile
    if let Some(idx) = board.unit_at(x, y) {
        let unit = &board.units[idx];
        if unit.hp <= 0 && unit.acid() {
            let tile = board.tile(x, y);
            if !tile.terrain.is_deadly_ground() || tile.terrain == Terrain::Water {
                board.tile_mut(x, y).flags |= TileFlags::ACID;
            }
        }
    }

    // Damage building if present — any damage destroys ALL buildings on the tile
    // (ITB rule: multi-building tiles are all-or-nothing, not incremental HP)
    let mut bldg_hp_lost: u8 = 0;
    {
        let tile = board.tile_mut(x, y);
        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
            let old_hp = tile.building_hp;
            tile.building_hp = 0;
            tile.terrain = Terrain::Rubble;
            bldg_hp_lost = old_hp;
            result.buildings_damaged += old_hp as i32;
            result.grid_damage += old_hp as i32;
            result.buildings_lost += 1;
        }
    }
    if bldg_hp_lost > 0 {
        board.grid_power = board.grid_power.saturating_sub(bldg_hp_lost);
    }

    // Ice: intact → cracked → water
    let tile = board.tile_mut(x, y);
    if tile.terrain == Terrain::Ice {
        if tile.cracked() || source == DamageSource::Fire {
            tile.terrain = Terrain::Water;
            tile.set_cracked(false);
            // Non-flying unit drowns
            if let Some(idx) = board.unit_at(x, y) {
                let unit = &mut board.units[idx];
                if unit.hp > 0 && !unit.flying() {
                    unit.hp = 0;
                    if unit.is_enemy() {
                        result.enemies_killed += 1;
                    }
                }
            }
        } else {
            tile.set_cracked(true);
        }
    }

    // Forest: weapon damage ignites (NOT bump/push damage)
    let tile = board.tile_mut(x, y);
    if tile.terrain == Terrain::Forest && source != DamageSource::Bump {
        tile.set_on_fire(true);
        // Tile stays Terrain::Forest with ON_FIRE flag.
        // Unit does NOT immediately catch fire — happens at end-of-turn.
    }

    // Sand: weapon damage → smoke (fire weapon → fire tile instead)
    let tile = board.tile_mut(x, y);
    if tile.terrain == Terrain::Sand && source == DamageSource::Weapon {
        tile.terrain = Terrain::Ground;
        // Note: fire_weapon flag not yet threaded; default to smoke.
        // Correct fire-on-sand requires knowing if weapon has FIRE flag.
        tile.set_smoke(true);
    }

    // ACID pool creation: unit with ACID dies → acid pool on tile
    if let Some(idx) = board.any_unit_at(x, y) {
        let unit = &board.units[idx];
        if unit.hp <= 0 && unit.acid() {
            let tile = board.tile_mut(x, y);
            if !tile.terrain.is_deadly_ground() || tile.terrain == Terrain::Water {
                tile.flags |= TileFlags::ACID;
                tile.set_on_fire(false); // acid pool extinguishes fire
            }
        }
    }

    // Multi-tile HP sync: mirror final HP to all entries sharing this uid.
    // Runs AFTER the body so kill-credit / Psion cleanup / explosion pre-check
    // don't re-fire on the twin. Currently only Dam_Pawn uses ExtraSpaces, and
    // Dam_Pawn is Team::Neutral so none of the enemy-gated side-effects would
    // fire anyway — but keep this generic so future multi-tile pawns are safe.
    if let Some(idx) = board.any_unit_at(x, y) {
        let uid = board.units[idx].uid;
        let hp = board.units[idx].hp;
        if uid != 0 {
            for j in 0..board.unit_count as usize {
                if j != idx && board.units[j].uid == uid {
                    board.units[j].hp = hp;
                }
            }
        }
    }

    // Old Earth Dam flood: if this damage killed the last dam tile, flood
    // the 2×7 strip behind the dam (drowns non-flying non-massive Vek).
    // uid-independent detection — works regardless of which tile took the
    // fatal hit. Idempotent via dam_alive gate.
    if board.dam_alive {
        let dam_dead = (0..board.unit_count as usize).all(|i| {
            let u = &board.units[i];
            u.type_name_str() != "Dam_Pawn" || u.hp <= 0
        });
        if dam_dead {
            trigger_dam_flood(board, result);
            board.dam_alive = false;
        }
    }

    // Web break: enemy webber killed → unweb any mechs they were holding.
    if let Some(idx) = board.any_unit_at(x, y) {
        let u = &board.units[idx];
        if u.hp <= 0 && u.is_enemy() {
            let dead_uid = u.uid;
            break_web_from(board, dead_uid);
        }
    }
}

/// Convert a single tile to Water, drowning any non-flying non-massive unit
/// standing on it. Idempotent: running on existing Water is a no-op.
/// Mountains / Buildings are not flooded (game engine refuses to overwrite).
///
/// TODO(dam-integration): in-game, drown deaths DO trigger Blast Psion
/// explosions. This helper uses direct `hp = 0` bypassing the explosion
/// dispatch. Swap to a `apply_damage(..., source=Water)` routed path once
/// the user verifies drown-credit semantics.
pub fn flood_tile(board: &mut Board, x: u8, y: u8, _result: &mut ActionResult) {
    if x >= 8 || y >= 8 { return; }
    let t = board.tile(x, y);
    if t.terrain == Terrain::Water { return; }
    if matches!(t.terrain, Terrain::Mountain | Terrain::Building) { return; }

    board.tile_mut(x, y).terrain = Terrain::Water;
    board.tile_mut(x, y).set_cracked(false);

    if let Some(idx) = board.unit_at(x, y) {
        let u = &board.units[idx];
        if !u.effectively_flying() && !u.massive() {
            board.units[idx].hp = 0;
            // No enemies_killed increment — user verifying in-game whether
            // flood kills credit pilot XP / achievements.
        }
    }
}

/// Trigger the Dam_Pawn death flood. Fires exactly once when the dam
/// transitions from alive → dead. Flood pattern from mission_dam.lua:
/// `for y = 1,7 do for x = 0,1 do SpaceDamage(DamPos + Point(x,y)) end end`.
fn trigger_dam_flood(board: &mut Board, result: &mut ActionResult) {
    let (px, py) = match board.dam_primary {
        Some(p) => p,
        None => return,
    };
    for x_off in 0i8..=1 {
        for y_off in 1i8..=7 {
            let tx = px as i8 + x_off;
            let ty = py as i8 + y_off;
            if tx >= 0 && tx < 8 && ty >= 0 && ty < 8 {
                flood_tile(board, tx as u8, ty as u8, result);
            }
        }
    }
}

/// Apply damage to whatever is at (x, y), including Blast Psion death explosions.
/// Source: Bump/Fire bypass armor and acid. Normal/Self respects them.
pub fn apply_damage(board: &mut Board, x: u8, y: u8, damage: u8, result: &mut ActionResult, source: DamageSource) {
    if damage == 0 { return; }

    // Pre-check: track alive non-Psion enemy for death explosion
    let death_check = if board.blast_psion {
        board.unit_at(x, y).and_then(|idx| {
            let u = &board.units[idx];
            if u.is_enemy() && u.hp > 0 && u.type_name_str() != "Jelly_Explode1" {
                Some(idx)
            } else { None }
        })
    } else { None };

    // Apply core damage
    apply_damage_core(board, x, y, damage, result, source);

    // Blast Psion death explosion: if tracked enemy just died, explode
    if let Some(idx) = death_check {
        if board.units[idx].hp <= 0 {
            apply_death_explosion(board, x, y, result, 0);
        }
    }
}

// ── apply_throw ──────────────────────────────────────────────────────────────

/// Vice Fist: target at (tx, ty) is grabbed and tossed to the tile BEHIND the
/// attacker at (ax, ay). The destination is the tile one step from the attacker
/// in the direction OPPOSITE to the attack direction. If the destination is
/// blocked (edge / mountain / building / unit), the target stays in place and
/// takes 1 bump damage; the blocker (if a building or unit) also takes 1.
///
/// This is a teleport (2-tile total displacement), NOT a 1-tile push: the
/// target jumps directly to behind-attacker without touching the attacker tile.
pub fn apply_throw(board: &mut Board, ax: u8, ay: u8, tx: u8, ty: u8, dir: usize, result: &mut ActionResult) {
    // Find ANY unit (including dead) at target — simultaneous damage+throw.
    let unit_idx = match board.any_unit_at(tx, ty) {
        Some(idx) => idx,
        None => return,
    };

    // Non-pushable non-mechs are immune
    if !board.units[unit_idx].pushable() && !board.units[unit_idx].is_mech() {
        return;
    }

    // Destination = attacker position + opposite-of-attack direction
    let opp = opposite_dir(dir);
    let (odx, ody) = DIRS[opp];
    let nx_i = ax as i8 + odx;
    let ny_i = ay as i8 + ody;

    // Blocked by map edge — target stays, takes bump
    if !in_bounds(nx_i, ny_i) {
        apply_damage(board, tx, ty, 1, result, DamageSource::Bump);
        return;
    }

    let nx = nx_i as u8;
    let ny = ny_i as u8;

    // Blocked by mountain — target bumps, mountain takes 1 damage
    if board.tile(nx, ny).terrain == Terrain::Mountain {
        apply_damage(board, tx, ty, 1, result, DamageSource::Bump);
        let mt = board.tile_mut(nx, ny);
        if mt.building_hp > 0 {
            mt.building_hp -= 1;
        }
        if mt.building_hp == 0 {
            mt.terrain = Terrain::Rubble;
        }
        return;
    }

    // Blocked by building — both take 1 bump (building loses grid power)
    if board.tile(nx, ny).terrain == Terrain::Building && board.tile(nx, ny).building_hp > 0 {
        apply_damage(board, tx, ty, 1, result, DamageSource::Bump);
        result.buildings_bump_damaged += 1;
        let bt = board.tile_mut(nx, ny);
        bt.building_hp -= 1;
        if bt.building_hp == 0 {
            bt.terrain = Terrain::Rubble;
            result.grid_damage += 1;
            result.buildings_lost += 1;
            board.grid_power = board.grid_power.saturating_sub(1);
        } else {
            result.buildings_damaged += 1;
            board.grid_power = board.grid_power.saturating_sub(1);
        }
        return;
    }

    // Blocked by another alive unit — both take 1 bump
    if let Some(blocker_idx) = board.unit_at(nx, ny) {
        if blocker_idx != unit_idx {
            apply_damage(board, tx, ty, 1, result, DamageSource::Bump);
            apply_damage(board, nx, ny, 1, result, DamageSource::Bump);
            return;
        }
    }

    // Destination clear — teleport the target there
    board.units[unit_idx].x = nx;
    board.units[unit_idx].y = ny;

    // Web break: enemy webber moved → unweb any mechs they were holding
    if board.units[unit_idx].is_enemy() {
        let pushed_uid = board.units[unit_idx].uid;
        break_web_from(board, pushed_uid);
    }

    // Fire tile: thrown unit catches fire
    if board.tile(nx, ny).on_fire() && board.units[unit_idx].hp > 0 && !board.units[unit_idx].shield() {
        board.units[unit_idx].set_fire(true);
    }

    // ACID pool: unit gains ACID, pool consumed
    if board.tile(nx, ny).acid() && board.tile(nx, ny).terrain != Terrain::Water {
        if board.units[unit_idx].hp > 0 && !board.units[unit_idx].shield() {
            board.units[unit_idx].set_acid(true);
        }
        board.tile_mut(nx, ny).flags.remove(TileFlags::ACID);
    }

    // Frozen unit on water → creates ice
    let dest_terrain = board.tile(nx, ny).terrain;
    if board.units[unit_idx].frozen() && dest_terrain == Terrain::Water {
        board.tile_mut(nx, ny).terrain = Terrain::Ice;
        board.tile_mut(nx, ny).set_cracked(false);
        return;
    }

    // Water/lava/chasm: kills non-flying ground units (Lava also sets fire on flying)
    if board.units[unit_idx].hp > 0 && !board.units[unit_idx].flying() {
        match dest_terrain {
            Terrain::Water | Terrain::Chasm => {
                board.units[unit_idx].hp = 0;
            }
            Terrain::Lava => {
                board.units[unit_idx].hp = 0;
            }
            _ => {}
        }
    } else if board.units[unit_idx].hp > 0 && board.units[unit_idx].flying()
        && dest_terrain == Terrain::Lava {
        if !board.units[unit_idx].shield() {
            board.units[unit_idx].set_fire(true);
        }
    }

    // Old Earth Mine: instant kill on thrown unit (bypasses shield), mine consumed.
    // Mirrors apply_push's mine handling so throw and push paths agree.
    if board.units[unit_idx].hp > 0 {
        let tile = board.tile(nx, ny);
        if tile.old_earth_mine() {
            board.units[unit_idx].hp = 0;
            if board.units[unit_idx].is_mech() {
                result.mechs_killed += 1;
            }
            board.tile_mut(nx, ny).set_old_earth_mine(false);
        } else if tile.freeze_mine() {
            if !board.units[unit_idx].shield() {
                board.units[unit_idx].set_frozen(true);
            } else {
                board.units[unit_idx].set_shield(false);
            }
            board.tile_mut(nx, ny).set_freeze_mine(false);
        }
    }
}

// ── apply_push ───────────────────────────────────────────────────────────────

/// Push unit at (x, y) in direction. Damage+push are simultaneous (dead units still push).
pub fn apply_push(board: &mut Board, x: u8, y: u8, direction: usize, result: &mut ActionResult) {
    // Find ANY unit (including dead) — simultaneous damage+push
    let unit_idx = match board.any_unit_at(x, y) {
        Some(idx) => idx,
        None => return,
    };

    // Non-pushable non-mechs are immune
    if !board.units[unit_idx].pushable() && !board.units[unit_idx].is_mech() {
        return;
    }

    let (dx, dy) = DIRS[direction];
    let nx_i = x as i8 + dx;
    let ny_i = y as i8 + dy;

    // Blocked by map edge
    if !in_bounds(nx_i, ny_i) {
        apply_damage(board, x, y, 1, result, DamageSource::Bump);
        return;
    }

    let nx = nx_i as u8;
    let ny = ny_i as u8;

    // Blocked by mountain — pushed unit bumps, mountain takes 1 damage
    if board.tile(nx, ny).terrain == Terrain::Mountain {
        apply_damage(board, x, y, 1, result, DamageSource::Bump);
        let mt = board.tile_mut(nx, ny);
        if mt.building_hp > 0 {
            mt.building_hp -= 1;
        }
        if mt.building_hp == 0 {
            mt.terrain = Terrain::Rubble;
        }
        return;
    }

    // Blocked by building — BOTH take 1 bump damage (empirically verified)
    if board.tile(nx, ny).terrain == Terrain::Building && board.tile(nx, ny).building_hp > 0 {
        apply_damage(board, x, y, 1, result, DamageSource::Bump);
        result.buildings_bump_damaged += 1;
        let bt = board.tile_mut(nx, ny);
        bt.building_hp -= 1;
        if bt.building_hp == 0 {
            bt.terrain = Terrain::Rubble;
            result.grid_damage += 1;
            result.buildings_lost += 1;
            board.grid_power = board.grid_power.saturating_sub(1);
        } else {
            result.buildings_damaged += 1;
            board.grid_power = board.grid_power.saturating_sub(1);
        }
        return;
    }

    // Blocked by another alive unit — BOTH take 1 bump
    if let Some(blocker_idx) = board.unit_at(nx, ny) {
        if blocker_idx != unit_idx {
            apply_damage(board, x, y, 1, result, DamageSource::Bump);
            apply_damage(board, nx, ny, 1, result, DamageSource::Bump);
            return;
        }
    }

    // Destination clear — move the unit
    board.units[unit_idx].x = nx;
    board.units[unit_idx].y = ny;

    // Web break: enemy webber pushed → unweb any mechs they were holding.
    // Position change alone breaks the grapple (regardless of whether the
    // push subsequently kills the webber via terrain/mine).
    if board.units[unit_idx].is_enemy() {
        let pushed_uid = board.units[unit_idx].uid;
        break_web_from(board, pushed_uid);
    }

    // Fire tile: pushed unit catches fire
    if board.tile(nx, ny).on_fire() && board.units[unit_idx].hp > 0 && !board.units[unit_idx].shield() {
        board.units[unit_idx].set_fire(true);
    }

    // ACID pool: unit gains ACID, pool consumed
    if board.tile(nx, ny).acid() && board.tile(nx, ny).terrain != Terrain::Water {
        if board.units[unit_idx].hp > 0 && !board.units[unit_idx].shield() {
            board.units[unit_idx].set_acid(true);
        }
        board.tile_mut(nx, ny).flags.remove(TileFlags::ACID);
    }

    // Frozen unit on water → creates ice (unit survives)
    let dest_terrain = board.tile(nx, ny).terrain;
    if board.units[unit_idx].frozen() && dest_terrain == Terrain::Water {
        board.tile_mut(nx, ny).terrain = Terrain::Ice;
        board.tile_mut(nx, ny).set_cracked(false);
        return; // unit survives on ice
    }

    // Frozen unit on lava → unfreeze, then lava kills non-flying
    if board.units[unit_idx].frozen() && dest_terrain == Terrain::Lava {
        board.units[unit_idx].set_frozen(false);
    }

    // Check deadly terrain (frozen flying = grounded)
    let unit = &board.units[unit_idx];
    let eff_flying = unit.effectively_flying();
    let dest_terrain = board.tile(nx, ny).terrain;

    if dest_terrain.is_deadly_ground() && !eff_flying {
        let is_enemy = board.units[unit_idx].is_enemy();
        let has_acid = board.units[unit_idx].acid();
        let can_explode = is_enemy && board.blast_psion
            && board.units[unit_idx].type_name_str() != "Jelly_Explode1";
        let unit = &mut board.units[unit_idx];
        unit.hp = 0;
        if is_enemy {
            result.enemies_killed += 1;
            if can_explode {
                apply_death_explosion(board, nx, ny, result, 0);
            }
        } else if unit.is_player() {
            result.mechs_killed += 1;
        }

        // ACID unit drowns in water → water becomes ACID tile
        if has_acid && dest_terrain == Terrain::Water {
            board.tile_mut(nx, ny).flags |= TileFlags::ACID;
        }
    } else {
        // Unit survived the push — check for Old Earth Mine (instant kill, bypasses shield)
        let tile = board.tile(nx, ny);
        if tile.old_earth_mine() {
            let is_enemy = board.units[unit_idx].is_enemy();
            let can_explode = is_enemy && board.blast_psion
                && board.units[unit_idx].type_name_str() != "Jelly_Explode1";
            board.units[unit_idx].hp = 0;
            if is_enemy {
                result.enemies_killed += 1;
                if can_explode {
                    apply_death_explosion(board, nx, ny, result, 0);
                }
            } else if board.units[unit_idx].is_player() {
                result.mechs_killed += 1;
            }
            board.tile_mut(nx, ny).set_old_earth_mine(false);
        }
        // Freeze mine: pushed unit gets frozen, mine consumed
        else {
            let tile = board.tile(nx, ny);
            if tile.freeze_mine() {
                if !board.units[unit_idx].shield() {
                    board.units[unit_idx].set_frozen(true);
                } else {
                    board.units[unit_idx].set_shield(false);
                }
                board.tile_mut(nx, ny).set_freeze_mine(false);
            }
        }
    }
}

// ── Weapon status effect application ────────────────────────────────────────

/// Apply a weapon's status effects to a tile and its occupant.
/// Called AFTER damage and push — if damage broke a shield, status will land.
pub fn apply_weapon_status(board: &mut Board, x: u8, y: u8, wdef: &WeaponDef) {
    // ── Tile effects ──
    if wdef.fire() {
        let tile = board.tile_mut(x, y);
        tile.set_smoke(false); // fire replaces smoke
        tile.set_on_fire(true);
    }
    if wdef.smoke() {
        let tile = board.tile_mut(x, y);
        tile.set_on_fire(false); // smoke replaces fire
        tile.set_smoke(true);
    }
    if wdef.freeze() {
        let tile = board.tile_mut(x, y);
        if tile.terrain == Terrain::Water {
            tile.terrain = Terrain::Ice;
            tile.set_cracked(false);
        } else if tile.terrain == Terrain::Ice && tile.cracked() {
            tile.set_cracked(false); // restore cracked ice
        }
        if tile.on_fire() {
            tile.set_on_fire(false); // freeze extinguishes fire
        }
    }
    if wdef.acid() {
        // Acid weapon on liquid/ground terrain creates a persistent
        // A.C.I.D. Tile (water) or A.C.I.D. Pool (ground/rubble).
        // Observed in game: Alpha Centipede Corrosive Vomit splash on
        // water converts it to A.C.I.D. Tile.
        let tile = board.tile_mut(x, y);
        if matches!(tile.terrain, Terrain::Water | Terrain::Ground | Terrain::Rubble) {
            tile.set_acid(true);
        }
    }

    // ── Unit effects ──
    if let Some(idx) = board.unit_at(x, y) {
        let unit = &board.units[idx];

        // Shield blocks negative status WITHOUT consuming the shield
        if unit.shield() && (wdef.fire() || wdef.acid() || wdef.web() || wdef.freeze()) {
            // Shield is a positive effect, always applies even if shield is up
            if wdef.shield() {
                board.units[idx].set_shield(true);
            }
            return;
        }

        if wdef.fire() {
            let u = &mut board.units[idx];
            if u.frozen() {
                u.set_frozen(false); // fire on frozen: unfreeze AND catch fire
            }
            u.set_fire(true);
        }
        if wdef.acid() {
            board.units[idx].set_acid(true);
        }
        if wdef.freeze() {
            let u = &mut board.units[idx];
            if u.fire() {
                u.set_fire(false); // freeze on fire: extinguish
            }
            u.set_frozen(true);
        }
        if wdef.web() {
            board.units[idx].set_web(true);
        }
        if wdef.shield() {
            board.units[idx].set_shield(true);
        }
    }
}

// ── Weapon simulation dispatch ───────────────────────────────────────────────

/// Simulate firing a weapon. Modifies board in-place.
pub fn simulate_weapon(
    board: &mut Board,
    attacker_idx: usize,
    weapon_id: WId,
    target_x: u8,
    target_y: u8,
) -> ActionResult {
    let mut result = ActionResult::default();
    let wdef = weapon_def(weapon_id);

    let ax = board.units[attacker_idx].x;
    let ay = board.units[attacker_idx].y;
    // Use cardinal_direction (any colinear distance) so artillery/projectile/laser/
    // charge/pull pick up the correct attack axis even when target isn't adjacent.
    // Melee targets ARE adjacent, so both helpers agree there.
    let attack_dir = cardinal_direction(ax, ay, target_x, target_y);

    match wdef.weapon_type {
        WeaponType::Melee => sim_melee(board, wdef, ax, ay, target_x, target_y, attack_dir, &mut result),
        WeaponType::Projectile => sim_projectile(board, ax, ay, wdef, attack_dir, &mut result),
        WeaponType::Artillery => sim_artillery(board, wdef, target_x, target_y, attack_dir, &mut result),
        WeaponType::SelfAoe => sim_self_aoe(board, ax, ay, wdef, &mut result),
        WeaponType::Pull | WeaponType::Swap => sim_pull_or_swap(board, attacker_idx, wdef, target_x, target_y, attack_dir, &mut result),
        WeaponType::Charge => sim_charge(board, attacker_idx, wdef, attack_dir, &mut result),
        WeaponType::Leap => sim_leap(board, attacker_idx, wdef, target_x, target_y, &mut result),
        WeaponType::Laser => sim_laser(board, ax, ay, wdef, attack_dir, &mut result),
        _ => {} // Passive, Deploy, TwoClick — no simulation
    }

    // Self damage
    if wdef.self_damage > 0 {
        let ax = board.units[attacker_idx].x;
        let ay = board.units[attacker_idx].y;
        apply_damage(board, ax, ay, wdef.self_damage, &mut result, DamageSource::SelfDamage);
    }

    // Self-freeze (Cryo-Launcher freezes attacker)
    if wdef.freeze() && weapon_id == WId::RangedIce {
        let u = &board.units[attacker_idx];
        if !u.shield() {
            board.units[attacker_idx].set_frozen(true);
        }
    }

    // Push self backward
    if wdef.push_self() {
        if let Some(dir) = attack_dir {
            let ax = board.units[attacker_idx].x;
            let ay = board.units[attacker_idx].y;
            apply_push(board, ax, ay, opposite_dir(dir), &mut result);
        }
    }

    result
}

// ── Melee ────────────────────────────────────────────────────────────────────

fn sim_melee(board: &mut Board, wdef: &WeaponDef, ax: u8, ay: u8, tx: u8, ty: u8, attack_dir: Option<usize>, result: &mut ActionResult) {
    apply_damage(board, tx, ty, wdef.damage, result, DamageSource::Weapon);

    // Chain weapon (Electric Whip): BFS through adjacent occupied tiles
    if wdef.chain() {
        let mut visited = 0u64;
        visited |= 1u64 << xy_to_idx(tx, ty);
        let mut queue: Vec<(u8, u8)> = vec![(tx, ty)];
        let mut head = 0;
        while head < queue.len() {
            let (cx, cy) = queue[head];
            head += 1;
            for &(dx, dy) in &DIRS {
                let nx = cx as i8 + dx;
                let ny = cy as i8 + dy;
                if !in_bounds(nx, ny) { continue; }
                let (nxu, nyu) = (nx as u8, ny as u8);
                let bit = 1u64 << xy_to_idx(nxu, nyu);
                if visited & bit != 0 { continue; }
                visited |= bit;
                // Chain doesn't pass through buildings (no Building Chain upgrade yet)
                if board.tile(nxu, nyu).is_building() { continue; }
                if board.unit_at(nxu, nyu).is_some() {
                    apply_damage(board, nxu, nyu, wdef.damage, result, DamageSource::Weapon);
                    queue.push((nxu, nyu));
                }
            }
        }
    }

    if let Some(dir) = attack_dir {
        // Apply weapon status BEFORE push (unit still at target tile)
        apply_weapon_status(board, tx, ty, wdef);

        match wdef.push {
            PushDir::Forward => apply_push(board, tx, ty, dir, result),
            PushDir::Flip => apply_push(board, tx, ty, opposite_dir(dir), result),
            PushDir::Backward => apply_push(board, tx, ty, opposite_dir(dir), result),
            PushDir::Perpendicular => apply_push(board, tx, ty, (dir + 1) % 4, result),
            PushDir::Outward => {
                apply_push(board, tx, ty, dir, result);
            }
            PushDir::Throw => apply_throw(board, ax, ay, tx, ty, dir, result),
            _ => {}
        }

        // AoE behind: hit tile behind target
        if wdef.aoe_behind() {
            let (ddx, ddy) = DIRS[dir];
            let bx = tx as i8 + ddx;
            let by = ty as i8 + ddy;
            if in_bounds(bx, by) {
                apply_damage(board, bx as u8, by as u8, wdef.damage, result, DamageSource::Weapon);
            }
        }

        // AoE perpendicular: hit tiles beside target, push in attack direction
        if wdef.aoe_perpendicular() {
            for &perp in &[(dir + 1) % 4, (dir + 3) % 4] {
                let (pdx, pdy) = DIRS[perp];
                let px = tx as i8 + pdx;
                let py = ty as i8 + pdy;
                if in_bounds(px, py) {
                    apply_damage(board, px as u8, py as u8, wdef.damage, result, DamageSource::Weapon);
                    if wdef.push == PushDir::Forward {
                        apply_push(board, px as u8, py as u8, dir, result);
                    }
                }
            }
        }
    }
}

// ── Projectile ───────────────────────────────────────────────────────────────

fn sim_projectile(board: &mut Board, ax: u8, ay: u8, wdef: &WeaponDef, attack_dir: Option<usize>, result: &mut ActionResult) {
    let dir = match attack_dir {
        Some(d) => d,
        None => return,
    };

    let (dx, dy) = DIRS[dir];

    // Find first hit
    let mut hit_x: i8 = -1;
    let mut hit_y: i8 = -1;
    for i in 1..8i8 {
        let nx = ax as i8 + dx * i;
        let ny = ay as i8 + dy * i;
        if !in_bounds(nx, ny) { break; }
        let nxu = nx as u8;
        let nyu = ny as u8;

        let tile = board.tile(nxu, nyu);
        if tile.terrain == Terrain::Mountain { break; }
        if tile.is_building() && !wdef.phase() {
            hit_x = nx; hit_y = ny; break;
        }
        if board.unit_at(nxu, nyu).is_some() {
            hit_x = nx; hit_y = ny; break;
        }
    }

    if hit_x >= 0 {
        let hx = hit_x as u8;
        let hy = hit_y as u8;
        apply_damage(board, hx, hy, wdef.damage, result, DamageSource::Weapon);
        apply_weapon_status(board, hx, hy, wdef); // status BEFORE push (unit still here)
        match wdef.push {
            PushDir::Forward => apply_push(board, hx, hy, dir, result),
            PushDir::Backward => apply_push(board, hx, hy, opposite_dir(dir), result),
            _ => {}
        }
    }

    // Mirror shot (aoe_behind): also fire backward
    if wdef.aoe_behind() {
        let opp = opposite_dir(dir);
        let (odx, ody) = DIRS[opp];
        for i in 1..8i8 {
            let nx = ax as i8 + odx * i;
            let ny = ay as i8 + ody * i;
            if !in_bounds(nx, ny) { break; }
            let nxu = nx as u8;
            let nyu = ny as u8;

            let tile = board.tile(nxu, nyu);
            if tile.terrain == Terrain::Mountain { break; }
            if tile.is_building() { break; }
            if board.unit_at(nxu, nyu).is_some() {
                apply_damage(board, nxu, nyu, wdef.damage, result, DamageSource::Weapon);
                if wdef.push == PushDir::Forward {
                    apply_push(board, nxu, nyu, opp, result);
                }
                break;
            }
        }
    }
}

// ── Artillery ────────────────────────────────────────────────────────────────

fn sim_artillery(board: &mut Board, wdef: &WeaponDef, tx: u8, ty: u8, attack_dir: Option<usize>, result: &mut ActionResult) {
    // Center damage
    if wdef.aoe_center() {
        apply_damage(board, tx, ty, wdef.damage, result, DamageSource::Weapon);
    }

    // Apply status effects to center tile (fire, freeze, smoke, shield, acid)
    apply_weapon_status(board, tx, ty, wdef);

    // Behind tile damage (Old Earth Artillery)
    if wdef.aoe_behind() {
        if let Some(dir) = attack_dir {
            let (ddx, ddy) = DIRS[dir];
            let bx = tx as i8 + ddx;
            let by = ty as i8 + ddy;
            if in_bounds(bx, by) {
                apply_damage(board, bx as u8, by as u8, wdef.damage, result, DamageSource::Weapon);
                apply_weapon_status(board, bx as u8, by as u8, wdef);
            }
        }
    }

    // Adjacent tile effects (push outward)
    if wdef.aoe_adjacent() {
        for (i, &(dx, dy)) in DIRS.iter().enumerate() {
            let nx = tx as i8 + dx;
            let ny = ty as i8 + dy;
            if !in_bounds(nx, ny) { continue; }
            apply_damage(board, nx as u8, ny as u8, wdef.damage_outer, result, DamageSource::Weapon);
            if wdef.push == PushDir::Outward {
                apply_push(board, nx as u8, ny as u8, i, result);
            }
            apply_weapon_status(board, nx as u8, ny as u8, wdef);
        }
    }
}

// ── Self AoE ─────────────────────────────────────────────────────────────────

fn sim_self_aoe(board: &mut Board, ax: u8, ay: u8, wdef: &WeaponDef, result: &mut ActionResult) {
    for (i, &(dx, dy)) in DIRS.iter().enumerate() {
        let nx = ax as i8 + dx;
        let ny = ay as i8 + dy;
        if !in_bounds(nx, ny) { continue; }
        apply_damage(board, nx as u8, ny as u8, wdef.damage, result, DamageSource::Weapon);
        match wdef.push {
            PushDir::Outward => apply_push(board, nx as u8, ny as u8, i, result),
            PushDir::Inward => apply_push(board, nx as u8, ny as u8, opposite_dir(i), result),
            _ => {}
        }
        apply_weapon_status(board, nx as u8, ny as u8, wdef);
    }
}

// ── Pull / Swap ──────────────────────────────────────────────────────────────

fn sim_pull_or_swap(board: &mut Board, attacker_idx: usize, wdef: &WeaponDef, tx: u8, ty: u8, attack_dir: Option<usize>, result: &mut ActionResult) {
    if wdef.weapon_type == WeaponType::Swap {
        if let Some(target_idx) = board.unit_at(tx, ty) {
            // Stable/Massive neutrals (e.g. Dam_Pawn) are immune to swap.
            // Mechs are always swap-eligible regardless of pushable flag.
            if !board.units[target_idx].pushable() && !board.units[target_idx].is_mech() {
                return;
            }
            // Swap positions
            let (ax, ay) = (board.units[attacker_idx].x, board.units[attacker_idx].y);
            board.units[target_idx].x = ax;
            board.units[target_idx].y = ay;
            board.units[attacker_idx].x = tx;
            board.units[attacker_idx].y = ty;
        } else {
            // Teleport to empty tile
            board.units[attacker_idx].x = tx;
            board.units[attacker_idx].y = ty;
        }
        let _ = result; // no damage from swap
        return;
    }

    // Pull: move target toward attacker
    if let Some(dir) = attack_dir {
        if let Some(_target_idx) = board.unit_at(tx, ty) {
            if board.units[_target_idx].pushable() {
                apply_push(board, tx, ty, opposite_dir(dir), result);
            }
        }
    }
}

// ── Charge ───────────────────────────────────────────────────────────────────

fn sim_charge(board: &mut Board, attacker_idx: usize, wdef: &WeaponDef, attack_dir: Option<usize>, result: &mut ActionResult) {
    let dir = match attack_dir {
        Some(d) => d,
        None => return,
    };

    let (dx, dy) = DIRS[dir];
    let ax = board.units[attacker_idx].x;
    let ay = board.units[attacker_idx].y;

    let mut last_free = (ax, ay);
    let mut hit: Option<(u8, u8)> = None;

    for i in 1..8i8 {
        let nx = ax as i8 + dx * i;
        let ny = ay as i8 + dy * i;
        if !in_bounds(nx, ny) { break; }
        let nxu = nx as u8;
        let nyu = ny as u8;

        let tile = board.tile(nxu, nyu);
        if tile.terrain == Terrain::Mountain { break; }
        if tile.is_building() { hit = Some((nxu, nyu)); break; }
        if !wdef.flying_charge() && tile.terrain.is_deadly_ground() { break; }
        if board.unit_at(nxu, nyu).is_some() { hit = Some((nxu, nyu)); break; }

        last_free = (nxu, nyu);
    }

    // Move attacker to last free tile
    board.units[attacker_idx].x = last_free.0;
    board.units[attacker_idx].y = last_free.1;

    // Damage hit target
    if let Some((hx, hy)) = hit {
        apply_damage(board, hx, hy, wdef.damage, result, DamageSource::Weapon);
        apply_weapon_status(board, hx, hy, wdef); // status BEFORE push
        if wdef.push == PushDir::Forward {
            apply_push(board, hx, hy, dir, result);
        }
    }
}

// ── Leap ─────────────────────────────────────────────────────────────────────

fn sim_leap(board: &mut Board, attacker_idx: usize, wdef: &WeaponDef, tx: u8, ty: u8, result: &mut ActionResult) {
    let old_x = board.units[attacker_idx].x;
    let old_y = board.units[attacker_idx].y;
    board.units[attacker_idx].x = tx;
    board.units[attacker_idx].y = ty;

    // Apply status to landing tile (Jetmech smokes landing spot)
    apply_weapon_status(board, tx, ty, wdef);

    // Damage adjacent tiles (skip source direction)
    let from_dir = direction_between(tx, ty, old_x, old_y);
    for (i, &(dx, dy)) in DIRS.iter().enumerate() {
        if Some(i) == from_dir { continue; }
        let nx = tx as i8 + dx;
        let ny = ty as i8 + dy;
        if !in_bounds(nx, ny) { continue; }
        apply_damage(board, nx as u8, ny as u8, wdef.damage, result, DamageSource::Weapon);
        if wdef.push == PushDir::Outward {
            apply_push(board, nx as u8, ny as u8, i, result);
        }
    }
}

// ── Laser ────────────────────────────────────────────────────────────────────

fn sim_laser(board: &mut Board, ax: u8, ay: u8, wdef: &WeaponDef, attack_dir: Option<usize>, result: &mut ActionResult) {
    let dir = match attack_dir {
        Some(d) => d,
        None => return,
    };

    let (dx, dy) = DIRS[dir];
    let mut dmg = wdef.damage;

    for i in 1..8i8 {
        let nx = ax as i8 + dx * i;
        let ny = ay as i8 + dy * i;
        if !in_bounds(nx, ny) { break; }
        let nxu = nx as u8;
        let nyu = ny as u8;

        let tile = board.tile(nxu, nyu);
        // Beam stops at mountains (but hits them)
        if tile.terrain == Terrain::Mountain {
            apply_damage(board, nxu, nyu, dmg, result, DamageSource::Weapon);
            break;
        }
        // Beam stops at buildings (but hits them)
        if tile.is_building() {
            apply_damage(board, nxu, nyu, dmg, result, DamageSource::Weapon);
            break;
        }

        apply_damage(board, nxu, nyu, dmg, result, DamageSource::Weapon);
        dmg = dmg.saturating_sub(1).max(1); // damage floor = 1
    }
}

// ── simulate_action (move + attack) ──────────────────────────────────────────

/// Simulate a complete mech action: move + attack. Modifies board in-place.
pub fn simulate_action(
    board: &mut Board,
    mech_idx: usize,
    move_to: (u8, u8),
    weapon_id: WId,
    target: (u8, u8),
) -> ActionResult {
    let mut result = ActionResult::default();

    // Move
    let old_pos = (board.units[mech_idx].x, board.units[mech_idx].y);
    board.units[mech_idx].x = move_to.0;
    board.units[mech_idx].y = move_to.1;

    // Collect pod
    {
        let tile = board.tile_mut(move_to.0, move_to.1);
        if tile.has_pod() {
            tile.set_has_pod(false);
            result.pods_collected += 1;
        }
    }

    // ACID pool pickup: mech gains ACID, pool consumed
    {
        let tile = board.tile(move_to.0, move_to.1);
        if tile.acid() && tile.terrain != Terrain::Water {
            if !board.units[mech_idx].shield() {
                board.units[mech_idx].set_acid(true);
            }
            board.tile_mut(move_to.0, move_to.1).flags.remove(TileFlags::ACID);
        }
    }

    // Old Earth Mine: kills mech on arrival (bypasses shield), mine consumed
    if move_to != old_pos {
        let tile = board.tile(move_to.0, move_to.1);
        if tile.old_earth_mine() {
            board.units[mech_idx].hp = 0;
            result.mechs_killed += 1;
            board.tile_mut(move_to.0, move_to.1).set_old_earth_mine(false);
        }
    }

    // Freeze mine: freezes mech on arrival, mine consumed
    if move_to != old_pos {
        let tile = board.tile(move_to.0, move_to.1);
        if tile.freeze_mine() {
            if !board.units[mech_idx].shield() {
                board.units[mech_idx].set_frozen(true);
            } else {
                board.units[mech_idx].set_shield(false);
            }
            board.tile_mut(move_to.0, move_to.1).set_freeze_mine(false);
        }
    }

    // Fire tile: mech catches fire on arrival (if not shielded).
    // Mirrors apply_push's fire-catch logic so move and push paths agree.
    if move_to != old_pos {
        let tile = board.tile(move_to.0, move_to.1);
        if tile.on_fire() && board.units[mech_idx].hp > 0 && !board.units[mech_idx].shield() {
            board.units[mech_idx].set_fire(true);
        }
    }

    // Repair
    if weapon_id == WId::Repair {
        let unit = &mut board.units[mech_idx];
        unit.hp = unit.hp.min(unit.max_hp - 1) + 1; // heal 1
        unit.set_fire(false);
        unit.set_acid(false);
        unit.set_frozen(false);
        unit.set_active(false);
        return result;
    }

    // Frozen mech cannot attack — only repair (handled above) is allowed
    if board.units[mech_idx].frozen() {
        board.units[mech_idx].set_active(false);
        return result;
    }

    // Attack
    if weapon_id != WId::None {
        let attack_result = simulate_weapon(board, mech_idx, weapon_id, target.0, target.1);
        result.merge(&attack_result);
    }

    board.units[mech_idx].set_active(false);
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_test_board() -> Board {
        Board::default()
    }

    fn add_enemy(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8) -> usize {
        board.add_unit(Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        })
    }

    fn add_mech(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8, weapon: WId) -> usize {
        board.add_unit(Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Player,
            weapon: crate::board::WeaponId(weapon as u16),
            flags: UnitFlags::IS_MECH | UnitFlags::ACTIVE | UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        })
    }

    #[test]
    fn test_push_into_water_kills() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Water;
        let idx = add_enemy(&mut board, 1, 3, 3, 2);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result); // push N into water
        assert_eq!(board.units[idx].hp, 0);
        assert_eq!(result.enemies_killed, 1);
    }

    #[test]
    fn test_push_into_building_both_take_damage() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;
        let idx = add_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result); // push N into building
        assert_eq!(board.units[idx].hp, 2); // -1 bump
        assert_eq!(board.tile(3, 4).building_hp, 0); // building destroyed
        assert_eq!(result.grid_damage, 1);
    }

    #[test]
    fn test_dead_unit_still_pushes_into_building() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;

        // Enemy at (3,3) with 0 HP (just killed)
        board.add_unit(Unit {
            uid: 1, x: 3, y: 3, hp: 0, max_hp: 2,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        // Dead unit corpse still bumps the building
        assert_eq!(board.tile(3, 4).building_hp, 0);
        assert_eq!(result.grid_damage, 1);
    }

    #[test]
    fn test_bump_ignores_armor() {
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 0, 0, 3);
        board.units[idx].flags |= UnitFlags::ARMOR;

        let mut result = ActionResult::default();
        apply_push(&mut board, 0, 0, 2, &mut result); // push S off edge
        // Bump damage ignores armor: should take 1, not 0
        assert_eq!(board.units[idx].hp, 2);
    }

    #[test]
    fn test_titan_fist_kill_and_push() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::PrimePunchmech);
        let enemy_idx = add_enemy(&mut board, 1, 3, 4, 2);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmech, 3, 4);
        // 2 damage kills 2HP hornet
        assert_eq!(result.enemies_killed, 1);
        // Dead unit pushed forward (simultaneous)
        assert_eq!(board.units[enemy_idx].y, 5); // moved from 4 to 5
    }

    #[test]
    fn test_frozen_unit_invincible() {
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 3, 3, 2);
        board.units[idx].set_frozen(true);

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 5, &mut result, DamageSource::Weapon);
        // Damage unfreezes but deals 0
        assert_eq!(board.units[idx].hp, 2);
        assert!(!board.units[idx].frozen());
    }

    #[test]
    fn test_shield_absorbs_damage() {
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 3, 3, 2);
        board.units[idx].set_shield(true);

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 5, &mut result, DamageSource::Weapon);
        assert_eq!(board.units[idx].hp, 2); // no damage
        assert!(!board.units[idx].shield()); // shield consumed
    }

    #[test]
    fn test_laser_damage_decay() {
        let mut board = make_test_board();
        // Place enemies along a line
        add_enemy(&mut board, 1, 1, 0, 10);
        add_enemy(&mut board, 2, 2, 0, 10);
        add_enemy(&mut board, 3, 3, 0, 10);

        let mech_idx = add_mech(&mut board, 0, 0, 0, 3, WId::PrimeLasermech);
        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeLasermech, 1, 0);

        // Laser damage: 3, 2, 1 (decreasing, floor 1)
        // Enemies at indices 0,1,2; mech at index 3
        assert_eq!(board.units[0].hp, 7); // (1,0): 10-3
        assert_eq!(board.units[1].hp, 8); // (2,0): 10-2
        assert_eq!(board.units[2].hp, 9); // (3,0): 10-1
    }

    #[test]
    fn test_acid_projector_applies_acid() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::ScienceAcidShot);
        let enemy_idx = add_enemy(&mut board, 1, 3, 4, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceAcidShot, 3, 4);
        // Acid Projector should apply ACID status to target
        assert!(board.units[enemy_idx].acid(), "Enemy should have ACID after Acid Projector");
    }

    #[test]
    fn test_cryo_launcher_freezes_target_and_self() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::RangedIce);
        let enemy_idx = add_enemy(&mut board, 1, 3, 6, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedIce, 3, 6);
        assert!(board.units[enemy_idx].frozen(), "Target should be frozen");
        assert!(board.units[mech_idx].frozen(), "Cryo-Launcher should self-freeze");
    }

    #[test]
    fn test_shield_blocks_status_without_consuming() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::ScienceAcidShot);
        let enemy_idx = add_enemy(&mut board, 1, 3, 4, 3);
        board.units[enemy_idx].set_shield(true);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceAcidShot, 3, 4);
        // Shield should block ACID but shield consumed by the 0-damage hit?
        // Acid Projector does 0 damage, so shield NOT consumed. Status also blocked.
        assert!(!board.units[enemy_idx].acid(), "Shield should block ACID status");
        assert!(board.units[enemy_idx].shield(), "Shield should NOT be consumed by 0 damage");
    }

    #[test]
    fn test_push_onto_fire_tile() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).set_on_fire(true);
        let idx = add_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        assert!(board.units[idx].fire(), "Unit pushed onto fire tile should catch fire");
    }

    #[test]
    fn test_jetmech_smokes_landing() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 0, 0, 3, WId::BruteJetmech);

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteJetmech, 2, 2);
        // Jetmech Aerial Bombs: smoke on landing tile
        assert!(board.tile(2, 2).smoke(), "Jetmech landing tile should have smoke");
    }

    #[test]
    fn test_freeze_water_creates_ice() {
        let mut board = make_test_board();
        board.tile_mut(3, 6).terrain = Terrain::Water;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::RangedIce);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedIce, 3, 6);
        assert_eq!(board.tile(3, 6).terrain, Terrain::Ice, "Freeze on water should create ice");
    }

    #[test]
    fn test_forest_ignites_on_weapon_damage() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Forest;
        add_enemy(&mut board, 1, 3, 4, 3);
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::PrimePunchmech);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmech, 3, 4);
        assert!(board.tile(3, 4).on_fire(), "Forest should ignite from weapon damage");
        assert_eq!(board.tile(3, 4).terrain, Terrain::Forest, "Terrain should stay Forest");
    }

    #[test]
    fn test_sand_becomes_smoke_on_weapon_damage() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Sand;
        add_enemy(&mut board, 1, 3, 4, 3);
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::PrimePunchmech);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmech, 3, 4);
        assert!(board.tile(3, 4).smoke(), "Sand should become smoke from weapon damage");
        assert_eq!(board.tile(3, 4).terrain, Terrain::Ground, "Sand should become ground");
    }

    #[test]
    fn test_frozen_unit_on_water_creates_ice() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Water;
        let idx = add_enemy(&mut board, 1, 3, 3, 3);
        board.units[idx].set_frozen(true);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        // Frozen unit on water → ice, unit survives
        assert_eq!(board.tile(3, 4).terrain, Terrain::Ice);
        assert!(board.units[idx].hp > 0, "Frozen unit should survive on newly-created ice");
    }

    #[test]
    fn test_acid_unit_death_creates_pool() {
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 3, 3, 1);
        board.units[idx].set_acid(true);

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 2, &mut result, DamageSource::Weapon);
        assert!(board.tile(3, 3).acid(), "ACID unit death should create acid pool");
    }

    // ── Vice Fist (Prime_Shift) Throw mechanic ────────────────────────────────

    #[test]
    fn test_vice_fist_throws_to_clear_tile_behind_attacker() {
        // JudoMech at (3,3) attacks east at Hornet at (4,3).
        // Throw destination = (2,3), behind attacker (opposite of attack dir).
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let enemy_idx = add_enemy(&mut board, 99, 4, 3, 2);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeShift, 4, 3);
        assert_eq!(board.units[mech_idx].x, 3, "JudoMech stays at (3,3)");
        assert_eq!(board.units[mech_idx].y, 3);
        assert_eq!(board.units[enemy_idx].x, 2, "Hornet thrown to (2,3) behind JudoMech");
        assert_eq!(board.units[enemy_idx].y, 3);
        assert_eq!(board.units[enemy_idx].hp, 1, "Hornet took 1 dmg from Vice Fist");
    }

    #[test]
    fn test_vice_fist_blocked_by_mountain_behind() {
        // Mountain at (2,3) blocks throw → enemy stays + bump.
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Mountain;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let enemy_idx = add_enemy(&mut board, 99, 4, 3, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeShift, 4, 3);
        assert_eq!(board.units[enemy_idx].x, 4, "Hornet stays at (4,3) — throw blocked");
        assert_eq!(board.units[enemy_idx].hp, 1, "3 HP - 1 weapon - 1 bump = 1");
    }

    #[test]
    fn test_vice_fist_throws_into_water_drowns() {
        // Water at (2,3); non-flying enemy thrown there → dies.
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Water;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let enemy_idx = add_enemy(&mut board, 99, 4, 3, 5);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeShift, 4, 3);
        assert_eq!(board.units[enemy_idx].x, 2, "Enemy moved to water tile");
        assert_eq!(board.units[enemy_idx].hp, 0, "Drowned in water (non-flying)");
    }

    #[test]
    fn test_vice_fist_blocked_by_edge_bumps() {
        // JudoMech at (0,3) facing east; throw destination (-1,3) is off-board.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 0, 3, 5, WId::PrimeShift);
        let enemy_idx = add_enemy(&mut board, 99, 1, 3, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeShift, 1, 3);
        assert_eq!(board.units[enemy_idx].x, 1, "Stays at (1,3) — off-board edge");
        assert_eq!(board.units[enemy_idx].hp, 1, "3 - 1 weapon - 1 bump = 1");
    }

    #[test]
    fn test_vice_fist_blocked_by_unit_behind() {
        // Unit already behind attacker → throw blocked, both bump.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let target_idx = add_enemy(&mut board, 99, 4, 3, 4);
        let blocker_idx = add_enemy(&mut board, 100, 2, 3, 4);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeShift, 4, 3);
        assert_eq!(board.units[target_idx].x, 4, "Target stays at (4,3) — blocked");
        assert_eq!(board.units[target_idx].hp, 2, "Target: 4 - 1 weapon - 1 bump = 2");
        assert_eq!(board.units[blocker_idx].hp, 3, "Blocker: 4 - 1 bump = 3");
    }

    // ── Vice Fist target-enumeration rejection ────────────────────────────────
    // The game surfaces a "no target available" error when the throw destination
    // is blocked, even though the sim's apply_throw fallback would resolve it as
    // a bump. The solver must match the game and skip those targets entirely.

    fn throw_targets(board: &Board, mech_pos: (u8, u8), mech_from: (u8, u8)) -> Vec<(u8, u8)> {
        crate::solver::get_weapon_targets(board, mech_pos.0, mech_pos.1, WId::PrimeShift, mech_from)
    }

    #[test]
    fn test_vice_fist_enum_rejects_enemy_behind() {
        // Enemy already on the destination tile → target not offered.
        let mut board = make_test_board();
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 4, 3, 3); // target east
        let _blocker = add_enemy(&mut board, 100, 2, 3, 3); // blocker west (throw dest)

        let targets = throw_targets(&board, (3, 3), (3, 3));
        assert!(!targets.contains(&(4, 3)), "East target must be rejected — (2,3) occupied");
    }

    #[test]
    fn test_vice_fist_enum_rejects_building_behind() {
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Building;
        board.tile_mut(2, 3).building_hp = 1;
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 4, 3, 3);

        let targets = throw_targets(&board, (3, 3), (3, 3));
        assert!(!targets.contains(&(4, 3)), "East target must be rejected — building at (2,3)");
    }

    #[test]
    fn test_vice_fist_enum_rejects_mountain_behind() {
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Mountain;
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 4, 3, 3);

        let targets = throw_targets(&board, (3, 3), (3, 3));
        assert!(!targets.contains(&(4, 3)), "East target must be rejected — mountain at (2,3)");
    }

    #[test]
    fn test_vice_fist_enum_rejects_wreck_behind() {
        let mut board = make_test_board();
        // Dead unit = wreck
        board.add_unit(Unit {
            uid: 200, x: 2, y: 3, hp: 0, max_hp: 3,
            team: Team::Enemy,
            ..Default::default()
        });
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 4, 3, 3);

        let targets = throw_targets(&board, (3, 3), (3, 3));
        assert!(!targets.contains(&(4, 3)), "East target must be rejected — wreck at (2,3)");
    }

    #[test]
    fn test_vice_fist_enum_rejects_edge_behind() {
        // Mech at column 0 facing east → throw dest (-1, 3) off-board.
        let mut board = make_test_board();
        let _mech = add_mech(&mut board, 0, 0, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 1, 3, 3);

        let targets = throw_targets(&board, (0, 3), (0, 3));
        assert!(!targets.contains(&(1, 3)), "East target must be rejected — off-board behind");
    }

    #[test]
    fn test_vice_fist_enum_allows_water_behind() {
        // Water at the destination IS a valid target — main strategic use.
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Water;
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 4, 3, 3);

        let targets = throw_targets(&board, (3, 3), (3, 3));
        assert!(targets.contains(&(4, 3)), "Water destination must be allowed");
    }

    #[test]
    fn test_vice_fist_enum_allows_chasm_behind() {
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Chasm;
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 4, 3, 3);

        let targets = throw_targets(&board, (3, 3), (3, 3));
        assert!(targets.contains(&(4, 3)), "Chasm destination must be allowed");
    }

    #[test]
    fn test_vice_fist_enum_allows_destination_is_mech_from() {
        // Mech originally at (3, 3), moves to (4, 3), attacks east at (5, 3).
        // Throw destination = (3, 3) = mech_from. After the move executes, (3, 3)
        // is vacated, so the throw must be allowed even though the stale board
        // still shows the mech there.
        let mut board = make_test_board();
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 5, 3, 3);

        // Simulate post-move position at (4, 3), mech_from still (3, 3).
        let targets = throw_targets(&board, (4, 3), (3, 3));
        assert!(targets.contains(&(5, 3)), "Throw dest == mech_from must be allowed");
    }

    // ── Cluster Artillery (Ranged_Defensestrike) ──────────────────────────────
    // SiegeMech weapon: targets a CENTER tile (which is NOT damaged) and hits
    // the 4 cardinal-adjacent tiles with 1 damage + push outward. Used to
    // protect a building/objective by clearing enemies around it.

    #[test]
    fn test_cluster_artillery_no_damage_to_center() {
        // Center has an enemy — should NOT take damage.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 0, 0, 2, WId::RangedDefensestrike);
        let center_idx = add_enemy(&mut board, 99, 4, 4, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedDefensestrike, 4, 4);
        assert_eq!(board.units[center_idx].hp, 3, "Center tile NOT damaged");
        assert_eq!(board.units[center_idx].x, 4, "Center NOT pushed");
        assert_eq!(board.units[center_idx].y, 4);
    }

    #[test]
    fn test_cluster_artillery_damages_and_pushes_adjacent() {
        // 4 enemies adjacent to center (4,4) at N/S/E/W — each takes 1 damage
        // and is pushed OUTWARD (away from center).
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 0, 0, 2, WId::RangedDefensestrike);
        let n = add_enemy(&mut board, 1, 4, 5, 3); // north of center
        let s = add_enemy(&mut board, 2, 4, 3, 3); // south
        let e = add_enemy(&mut board, 3, 5, 4, 3); // east
        let w = add_enemy(&mut board, 4, 3, 4, 3); // west

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedDefensestrike, 4, 4);
        // Each enemy: 3 - 1 (weapon) = 2 HP, then pushed 1 tile outward
        assert_eq!(board.units[n].hp, 2);
        assert_eq!(board.units[n].y, 6, "N enemy pushed further north (5→6)");
        assert_eq!(board.units[s].hp, 2);
        assert_eq!(board.units[s].y, 2, "S enemy pushed further south (3→2)");
        assert_eq!(board.units[e].hp, 2);
        assert_eq!(board.units[e].x, 6, "E enemy pushed east (5→6)");
        assert_eq!(board.units[w].hp, 2);
        assert_eq!(board.units[w].x, 2, "W enemy pushed west (3→2)");
    }

    #[test]
    fn test_cluster_artillery_protects_building_in_center() {
        // Building in center, enemies around it. Building should NOT take damage.
        let mut board = make_test_board();
        board.tile_mut(4, 4).terrain = Terrain::Building;
        board.tile_mut(4, 4).building_hp = 1;
        let mech_idx = add_mech(&mut board, 0, 0, 0, 2, WId::RangedDefensestrike);
        let attacker = add_enemy(&mut board, 1, 4, 5, 3); // adjacent to building

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedDefensestrike, 4, 4);
        assert_eq!(board.tile(4, 4).building_hp, 1, "Building survives intact");
        assert_eq!(board.units[attacker].hp, 2, "Adjacent enemy damaged");
        // Adjacent enemy at (4,5) pushed north away from center → (4,6)
        assert_eq!(board.units[attacker].y, 6, "Pushed north (away from center)");
    }

    // ── Grav Well (Science_Gravwell) ───────────────────────────────────────────
    // Gravity Mech weapon: artillery (range ≥2) that pulls the targeted unit
    // one tile TOWARD the attacker. No damage. Used to drag enemies into
    // friendly attack lanes or off threatened buildings.

    #[test]
    fn test_grav_well_pulls_target_toward_attacker() {
        // GravMech at (3,3) pulls target at (3,6) one tile south toward attacker.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::ScienceGravwell);
        let enemy_idx = add_enemy(&mut board, 99, 3, 6, 4);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceGravwell, 3, 6);
        assert_eq!(board.units[enemy_idx].x, 3, "Stays in column");
        assert_eq!(board.units[enemy_idx].y, 5, "Pulled 1 tile toward attacker (6→5)");
        assert_eq!(board.units[enemy_idx].hp, 4, "No damage from Grav Well itself");
    }

    #[test]
    fn test_grav_well_no_pull_into_blocker() {
        // Unit blocking the destination → both bump.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::ScienceGravwell);
        let blocker = add_enemy(&mut board, 1, 3, 5, 3);
        let target = add_enemy(&mut board, 2, 3, 6, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceGravwell, 3, 6);
        assert_eq!(board.units[target].y, 6, "Target stays — destination blocked");
        assert_eq!(board.units[target].hp, 2, "Bump damage");
        assert_eq!(board.units[blocker].hp, 2, "Blocker bumped too");
    }

    // ── Vek Hormones (Passive_FriendlyFire) ──────────────────────────────────
    // GravMech passive: enemies do +1 damage to OTHER enemies (not to mechs).
    // The board carries a vek_hormones flag set via the Lua bridge passive
    // detection. enemy_hit_damage() bumps damage when source AND target are Vek.

    fn add_enemy_with_attack(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8,
                              weapon: WId, dmg: u8, target_x: i8, target_y: i8) -> usize {
        board.add_unit(Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Enemy,
            weapon: crate::board::WeaponId(weapon as u16),
            weapon_damage: dmg,
            queued_target_x: target_x,
            queued_target_y: target_y,
            flags: UnitFlags::ACTIVE | UnitFlags::PUSHABLE,
            ..Default::default()
        })
    }

    #[test]
    fn test_vek_hormones_boosts_vek_vs_vek_damage() {
        // Hornet (1 dmg) attacks an adjacent enemy. With vek_hormones the hit
        // deals 2 damage; without it, 1. Verify by running an enemy-phase sim.
        use crate::enemy::simulate_enemy_attacks;
        let mut board = make_test_board();
        board.vek_hormones = true;
        // Hornet at (3,3) targets enemy at (3,4) — north (DIRS index 0)
        add_enemy_with_attack(&mut board, 1, 3, 3, 2, WId::HornetAtk1, 1, 3, 4);
        let target = add_enemy(&mut board, 2, 3, 4, 3);
        let original = [(255u8, 255u8); 16];

        simulate_enemy_attacks(&mut board, &original);
        assert_eq!(board.units[target].hp, 1,
            "Target Vek took 2 damage (1 base + 1 hormone bonus)");
    }

    #[test]
    fn test_vek_hormones_does_not_boost_vek_vs_mech() {
        // Same setup but target is a mech — base damage only.
        use crate::enemy::simulate_enemy_attacks;
        let mut board = make_test_board();
        board.vek_hormones = true;
        add_enemy_with_attack(&mut board, 1, 3, 3, 2, WId::HornetAtk1, 1, 3, 4);
        let mech_idx = add_mech(&mut board, 99, 3, 4, 3, WId::PrimePunchmech);
        let original = [(255u8, 255u8); 16];

        simulate_enemy_attacks(&mut board, &original);
        assert_eq!(board.units[mech_idx].hp, 2,
            "Mech took base 1 damage (hormones don't boost vs mechs)");
    }

    #[test]
    fn test_vek_hormones_off_no_boost() {
        // Sanity: with flag OFF, vek-on-vek is just base damage.
        use crate::enemy::simulate_enemy_attacks;
        let mut board = make_test_board();
        board.vek_hormones = false;
        add_enemy_with_attack(&mut board, 1, 3, 3, 2, WId::HornetAtk1, 1, 3, 4);
        let target = add_enemy(&mut board, 2, 3, 4, 3);
        let original = [(255u8, 255u8); 16];

        simulate_enemy_attacks(&mut board, &original);
        assert_eq!(board.units[target].hp, 2, "Base 1 damage only");
    }
}
