/// Enemy attack simulation — post-mech-action phase.
///
/// Processes enemies in UID order (ascending = game's attack order).
/// Re-traces projectile paths on the post-mech board state.
/// Uses actual weapon type dispatch (not binary ranged/melee).

use crate::types::*;
use crate::board::*;
use crate::weapons::*;
use crate::simulate::{apply_damage, apply_push, apply_weapon_status};

/// Get effective damage for an enemy hit at a tile (Vek Hormones adds +1 vs other enemies).
fn enemy_hit_damage(board: &Board, x: u8, y: u8, base_damage: u8, vek_hormones: bool) -> u8 {
    if vek_hormones {
        if let Some(idx) = board.unit_at(x, y) {
            if board.units[idx].is_enemy() {
                return base_damage + 1;
            }
        }
    }
    base_damage
}

/// Apply environment_danger damage to a tile.
///
/// `lethal=true` (Deadly Threat: air strike, lightning, cataclysm, etc.) bypasses
/// shield, frozen, armor, and ACID — sets HP=0 outright. Buildings destroyed.
/// Hits flying units too (air strikes drop bombs from above).
///
/// `lethal=false` (tidal wave, sandstorm, etc.) does 1 damage with bump-like
/// semantics: ignored by armor/ACID, consumed by shield, skips flying units.
/// Buildings take 1 HP.
///
/// Inlined unit/building handling (does not call apply_damage) so we can bypass
/// shield/frozen for the lethal case without polluting the core damage path.
fn apply_env_danger(board: &mut Board, x: u8, y: u8, lethal: bool, result: &mut ActionResult) {
    // Damage unit if present
    if let Some(uidx) = board.unit_at(x, y) {
        let unit = &mut board.units[uidx];
        if unit.hp > 0 {
            if lethal {
                // Deadly Threat: bypass shield/frozen/armor/ACID, set HP=0
                let prev_hp = unit.hp;
                unit.hp = 0;
                unit.set_shield(false);
                unit.set_frozen(false);
                if unit.is_player() {
                    result.mechs_killed += 1;
                    result.mech_damage_taken += prev_hp as i32;
                } else if unit.is_enemy() {
                    result.enemies_killed += 1;
                    result.enemy_damage_dealt += prev_hp as i32;
                }
            } else if !unit.effectively_flying() {
                // Non-lethal env (1 dmg): bump-like — consumed by shield, ignores armor/ACID
                if unit.shield() {
                    unit.set_shield(false);
                } else if unit.frozen() {
                    unit.set_frozen(false);
                } else {
                    unit.hp -= 1;
                    if unit.is_player() {
                        result.mech_damage_taken += 1;
                        if unit.hp <= 0 { result.mechs_killed += 1; }
                    } else if unit.is_enemy() {
                        result.enemy_damage_dealt += 1;
                        if unit.hp <= 0 { result.enemies_killed += 1; }
                    }
                }
            }
            // else: flying, non-lethal env doesn't hit
        }
    }

    // Damage building if present (lethal destroys entirely, non-lethal does 1 HP)
    let tile = board.tile_mut(x, y);
    if tile.terrain == Terrain::Building && tile.building_hp > 0 {
        let dmg = if lethal { tile.building_hp } else { 1 };
        let old_hp = tile.building_hp;
        tile.building_hp = tile.building_hp.saturating_sub(dmg);
        let lost = old_hp - tile.building_hp;
        result.buildings_damaged += lost as i32;
        result.grid_damage += lost as i32;
        if tile.building_hp == 0 {
            tile.terrain = Terrain::Rubble;
            result.buildings_lost += 1;
        }
        board.grid_power = board.grid_power.saturating_sub(lost);
    }
}

/// Apply spawn blocking damage: units standing on spawn tiles take 1 damage
/// when Vek try to emerge. Damage bypasses armor and ACID (bump-like damage)
/// but is consumed by shield. Fires after enemy attacks, before next player turn.
pub fn apply_spawn_blocking(
    board: &mut Board,
    spawn_points: &[(u8, u8)],
) {
    for &(sx, sy) in spawn_points {
        if let Some(idx) = board.unit_at(sx, sy) {
            let unit = &mut board.units[idx];
            if unit.hp <= 0 { continue; }
            if unit.shield() {
                unit.set_shield(false);
                continue;
            }
            if unit.frozen() {
                unit.set_frozen(false);
                continue;
            }
            // Bump-class damage: ignores armor/ACID. Route through apply_damage
            // so multi-tile HP mirroring + future dam-flood trigger run.
            let mut tmp_result = ActionResult::default();
            apply_damage(board, sx, sy, 1, &mut tmp_result, DamageSource::Bump);
        }
    }
}

/// Simulate all enemy attacks on the post-mech-action board.
/// Processes in UID order. Returns buildings destroyed count.
///
/// `original_positions`: maps unit index -> (orig_x, orig_y) for direction/range checks.
pub fn simulate_enemy_attacks(
    board: &mut Board,
    original_positions: &[(u8, u8); 16],
) -> i32 {
    let mut buildings_destroyed = 0;
    let mut result = ActionResult::default();

    // Fire tick: burning units take 1 damage before attacks
    // Flame Shielding: player mechs immune to fire
    for i in 0..board.unit_count as usize {
        if board.units[i].fire() && board.units[i].hp > 0 {
            if board.flame_shielding && board.units[i].is_player() {
                continue; // mechs immune to fire with Flame Shielding
            }
            let x = board.units[i].x;
            let y = board.units[i].y;
            apply_damage(board, x, y, 1, &mut result, DamageSource::Fire);
        }
    }

    // Storm Generator: enemies in smoke take 1 damage
    if board.storm_generator {
        for i in 0..board.unit_count as usize {
            if board.units[i].is_enemy() && board.units[i].hp > 0 {
                let x = board.units[i].x;
                let y = board.units[i].y;
                if board.tile(x, y).smoke() {
                    apply_damage(board, x, y, 1, &mut result, DamageSource::Weapon);
                }
            }
        }
    }

    // Fire tick Psion kill cleanup: if a Psion died from fire, clear its flag
    if board.blast_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Explode1" && board.units[i].hp > 0);
        if !alive { board.blast_psion = false; }
    }
    if board.armor_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Armor1" && board.units[i].hp > 0);
        if !alive {
            board.armor_psion = false;
            for i in 0..board.unit_count as usize {
                if board.units[i].is_enemy() {
                    board.units[i].flags.set(UnitFlags::ARMOR, false);
                }
            }
        }
    }
    if board.soldier_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Health1" && board.units[i].hp > 0);
        if !alive {
            board.soldier_psion = false;
            for i in 0..board.unit_count as usize {
                if board.units[i].is_enemy() && board.units[i].hp > 0
                    && board.units[i].type_name_str() != "Jelly_Health1"
                {
                    board.units[i].max_hp -= 1;
                    board.units[i].hp -= 1;
                }
            }
        }
    }
    if board.regen_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Regen1" && board.units[i].hp > 0);
        if !alive { board.regen_psion = false; }
    }
    if board.tyrant_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Lava1" && board.units[i].hp > 0);
        if !alive { board.tyrant_psion = false; }
    }

    // Blood Psion regen: heal all non-Psion Vek by 1 (after fire, before attacks)
    if board.regen_psion {
        for i in 0..board.unit_count as usize {
            let u = &mut board.units[i];
            if u.is_enemy() && u.hp > 0 && u.type_name_str() != "Jelly_Regen1" {
                if u.hp < u.max_hp {
                    u.hp += 1;
                }
            }
        }
    }

    // Environment danger (air strikes, lightning, tidal waves) — fires BEFORE Vek attacks
    // per game's interleaved attack order. Env effects resolve first, killing units
    // that were going to attack. Their queued attacks then never fire (hp <= 0 check below).
    if board.env_danger != 0 {
        for tile_idx in 0usize..64 {
            if board.env_danger & (1u64 << tile_idx) == 0 { continue; }
            let (x, y) = idx_to_xy(tile_idx);
            let lethal = board.env_danger_kill & (1u64 << tile_idx) != 0;
            apply_env_danger(board, x, y, lethal, &mut result);
        }
    }

    // Collect enemy indices sorted by UID
    let mut enemy_indices: Vec<usize> = (0..board.unit_count as usize)
        .filter(|&i| board.units[i].is_enemy())
        .collect();
    enemy_indices.sort_by_key(|&i| board.units[i].uid);

    for &ei in &enemy_indices {
        let enemy = &board.units[ei];
        if enemy.hp <= 0 { continue; }
        if enemy.queued_target_x < 0 { continue; }

        // Smoke cancels attacks
        let tile = board.tile(enemy.x, enemy.y);
        if tile.smoke() { continue; }

        // Frozen enemies can't attack
        if enemy.frozen() { continue; }

        let ex = enemy.x;
        let ey = enemy.y;
        let qtx = enemy.queued_target_x;
        let qty = enemy.queued_target_y;
        let enemy_uid = enemy.uid;
        let orig = original_positions[ei];

        // Look up actual weapon type from enemy pawn type
        let enemy_wid = enemy_weapon_for_type(enemy.type_name_str());
        let wdef = if enemy_wid != WId::None {
            weapon_def(enemy_wid)
        } else {
            // Fallback: use ranged flag for unknown enemy types
            if enemy.ranged() {
                weapon_def(WId::FireflyAtk1) // generic projectile
            } else {
                weapon_def(WId::HornetAtk1) // generic melee
            }
        };

        // Use bridge-provided damage if available, else weapon def
        let base_damage = if enemy.weapon_damage > 0 {
            enemy.weapon_damage
        } else {
            wdef.damage
        };
        // Vek Hormones: +1 damage when enemy attacks hit other enemies
        // Applied per-hit below based on target occupant
        let damage = base_damage;

        let weapon_behind = enemy.weapon_target_behind;

        let vh = board.vek_hormones;

        match wdef.weapon_type {
            WeaponType::Projectile => {
                if let Some((tx, ty)) = find_projectile_target(board, ex, ey, orig.0, orig.1, qtx, qty) {
                    let d = enemy_hit_damage(board, tx, ty, damage, vh);
                    apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
                    if wdef.fire() {
                        if let Some(idx) = board.unit_at(tx, ty) {
                            if !board.units[idx].frozen() {
                                board.units[idx].set_fire(true);
                            }
                        }
                        board.tile_mut(tx, ty).set_on_fire(true);
                    }
                    // ACID / WEB / other status effects on the primary target
                    apply_weapon_status(board, tx, ty, wdef);
                    if wdef.web() {
                        if let Some(idx) = board.unit_at(tx, ty) {
                            board.units[idx].web_source_uid = enemy_uid;
                        }
                    }

                    // aoe_perpendicular: splash two tiles perpendicular to
                    // projectile direction (Alpha Centipede's Corrosive Vomit:
                    // 3-tile T splash, damage + ACID on each).
                    if wdef.aoe_perpendicular() {
                        let pdx = (tx as i8 - ex as i8).signum();
                        let pdy = (ty as i8 - ey as i8).signum();
                        let perp: &[(i8, i8)] = if pdx != 0 && pdy == 0 {
                            &[(0, 1), (0, -1)]
                        } else if pdy != 0 && pdx == 0 {
                            &[(1, 0), (-1, 0)]
                        } else {
                            &[]
                        };
                        for &(px, py) in perp {
                            let nx = tx as i8 + px;
                            let ny = ty as i8 + py;
                            if !in_bounds(nx, ny) { continue; }
                            let nxu = nx as u8;
                            let nyu = ny as u8;
                            let d2 = enemy_hit_damage(board, nxu, nyu, damage, vh);
                            apply_damage(board, nxu, nyu, d2, &mut result, DamageSource::Weapon);
                            apply_weapon_status(board, nxu, nyu, wdef);
                            if wdef.web() {
                                if let Some(idx) = board.unit_at(nxu, nyu) {
                                    board.units[idx].web_source_uid = enemy_uid;
                                }
                            }
                        }
                    }
                }
            }

            WeaponType::Laser => {
                // Piercing beam: fires in cardinal direction from enemy position,
                // damage starts at wdef.damage and decreases by 1 per tile (floor 1).
                // Stops at mountains and buildings (after damaging them).
                let dx = (qtx - orig.0 as i8).signum();
                let dy = (qty - orig.1 as i8).signum();
                if (dx != 0) != (dy != 0) {
                    let mut dmg = wdef.damage;
                    for i in 1..8i8 {
                        let nx = ex as i8 + dx * i;
                        let ny = ey as i8 + dy * i;
                        if !in_bounds(nx, ny) { break; }
                        let nxu = nx as u8;
                        let nyu = ny as u8;
                        let tile = board.tile(nxu, nyu);
                        if tile.terrain == Terrain::Mountain {
                            apply_damage(board, nxu, nyu, dmg, &mut result, DamageSource::Weapon);
                            break;
                        }
                        if tile.is_building() {
                            apply_damage(board, nxu, nyu, dmg, &mut result, DamageSource::Weapon);
                            break;
                        }
                        let d = enemy_hit_damage(board, nxu, nyu, dmg, vh);
                        apply_damage(board, nxu, nyu, d, &mut result, DamageSource::Weapon);
                        dmg = dmg.saturating_sub(1).max(1);
                    }
                }
            }

            WeaponType::Artillery => {
                // Artillery preserves its ORIGINAL OFFSET from the attacker when
                // the attacker is pushed. Per ITB's piQueuedShot semantics, the
                // queued target is a direction+distance stored relative to the
                // enemy — pushing the enemy relocates the target tile by the
                // same delta (confirmed empirically: push Alpha Scarab D3→C3
                // with D7 original target → new target shifts to C7).
                //
                // range_min guard: if the PUSHED distance is below the weapon's
                // minimum range, attack cancels (e.g. pushed adjacent to target).
                let offset_x = qtx - orig.0 as i8;
                let offset_y = qty - orig.1 as i8;
                let new_tx = ex as i8 + offset_x;
                let new_ty = ey as i8 + offset_y;
                if !in_bounds(new_tx, new_ty) { continue; }

                // Cardinal axis required (exactly one axis non-zero) for artillery
                // to have a direction for path_size > 1 handling.
                let dx_sign = offset_x.signum();
                let dy_sign = offset_y.signum();
                if (dx_sign != 0) == (dy_sign != 0) { continue; }

                // Min-range check against the (new) attacker→target distance.
                let curr_range = offset_x.abs() + offset_y.abs();
                if (curr_range as u8) < wdef.range_min { continue; }

                let tx = new_tx as u8;
                let ty = new_ty as u8;
                let d = enemy_hit_damage(board, tx, ty, damage, vh);
                apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);

                // path_size > 1: also damage subsequent tiles in attack direction
                // (e.g. Super Stinger's 3-tile line; Crab Artillery's 2-tile hit)
                for i in 1..wdef.path_size as i8 {
                    let tx_n = new_tx + dx_sign * i;
                    let ty_n = new_ty + dy_sign * i;
                    if !in_bounds(tx_n, ty_n) { break; }
                    let d_n = enemy_hit_damage(board, tx_n as u8, ty_n as u8, damage, vh);
                    apply_damage(board, tx_n as u8, ty_n as u8, d_n, &mut result, DamageSource::Weapon);
                }
            }

            WeaponType::Charge => {
                // Charge from CURRENT position in original queued direction
                let dx = (qtx - orig.0 as i8).signum();
                let dy = (qty - orig.1 as i8).signum();

                // Must be valid cardinal direction
                if (dx != 0) != (dy != 0) {
                    let mut hit: Option<(u8, u8)> = None;
                    for i in 1..8i8 {
                        let nx = ex as i8 + dx * i;
                        let ny = ey as i8 + dy * i;
                        if !in_bounds(nx, ny) { break; }
                        let nxu = nx as u8;
                        let nyu = ny as u8;

                        let tile = board.tile(nxu, nyu);
                        if tile.terrain == Terrain::Mountain { break; }
                        if tile.terrain.is_deadly_ground() { break; }
                        if tile.is_building() {
                            hit = Some((nxu, nyu));
                            break;
                        }
                        if board.unit_at(nxu, nyu).is_some() {
                            hit = Some((nxu, nyu));
                            break;
                        }
                    }

                    if let Some((hx, hy)) = hit {
                        let d = enemy_hit_damage(board, hx, hy, damage, vh);
                        apply_damage(board, hx, hy, d, &mut result, DamageSource::Weapon);
                    }
                }
            }

            WeaponType::SelfAoe => {
                if wdef.aoe_center() {
                    apply_damage(board, ex, ey, damage, &mut result, DamageSource::Weapon);
                }
                if wdef.aoe_adjacent() {
                    for (i, &(dx, dy)) in DIRS.iter().enumerate() {
                        let nx = ex as i8 + dx;
                        let ny = ey as i8 + dy;
                        if in_bounds(nx, ny) {
                            let d = enemy_hit_damage(board, nx as u8, ny as u8, damage, vh);
                            apply_damage(board, nx as u8, ny as u8, d, &mut result, DamageSource::Weapon);
                            // Push outward / inward per weapon def (Scorpion Leader's
                            // Massive Spinneret pushes every target away from itself).
                            match wdef.push {
                                PushDir::Outward => apply_push(board, nx as u8, ny as u8, i, &mut result),
                                PushDir::Inward => apply_push(board, nx as u8, ny as u8, opposite_dir(i), &mut result),
                                _ => {}
                            }
                            // Status effects (WEB from Massive Spinneret, etc.):
                            // apply to the live unit on that tile.
                            if wdef.web() {
                                if let Some(idx) = board.unit_at(nx as u8, ny as u8) {
                                    board.units[idx].set_web(true);
                                }
                            }
                        }
                    }
                }
            }

            WeaponType::Melee => {
                if weapon_behind {
                    // Line attack (e.g., Launching Stinger): 2-tile line in the original
                    // cardinal direction. When pushed, retrace direction from the ORIGINAL
                    // position so the attack fires correctly from the new position.
                    let dx = (qtx - orig.0 as i8).signum();
                    let dy = (qty - orig.1 as i8).signum();
                    // Must be a valid cardinal direction (exactly one axis non-zero)
                    if (dx != 0) == (dy != 0) { continue; }

                    let tx1 = ex as i8 + dx;
                    let ty1 = ey as i8 + dy;
                    if in_bounds(tx1, ty1) {
                        let d = enemy_hit_damage(board, tx1 as u8, ty1 as u8, damage, vh);
                        apply_damage(board, tx1 as u8, ty1 as u8, d, &mut result, DamageSource::Weapon);
                        apply_weapon_status(board, tx1 as u8, ty1 as u8, wdef);
                        if wdef.web() {
                            if let Some(idx) = board.unit_at(tx1 as u8, ty1 as u8) {
                                board.units[idx].web_source_uid = enemy_uid;
                            }
                        }
                    }
                    let tx2 = ex as i8 + dx * 2;
                    let ty2 = ey as i8 + dy * 2;
                    if in_bounds(tx2, ty2) {
                        let d2 = enemy_hit_damage(board, tx2 as u8, ty2 as u8, damage, vh);
                        apply_damage(board, tx2 as u8, ty2 as u8, d2, &mut result, DamageSource::Weapon);
                        apply_weapon_status(board, tx2 as u8, ty2 as u8, wdef);
                        if wdef.web() {
                            if let Some(idx) = board.unit_at(tx2 as u8, ty2 as u8) {
                                board.units[idx].web_source_uid = enemy_uid;
                            }
                        }
                    }
                } else {
                    // Standard single-tile melee: attack fixed queued target.
                    // If pushed out of adjacency, attack fails (enemy can't reach).
                    let tx = qtx as u8;
                    let ty = qty as u8;
                    let curr_dist = (ex as i32 - tx as i32).abs() + (ey as i32 - ty as i32).abs();
                    if curr_dist > 1 { continue; }

                    let d = enemy_hit_damage(board, tx, ty, damage, vh);
                    apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
                    apply_weapon_status(board, tx, ty, wdef);
                    if wdef.web() {
                        if let Some(idx) = board.unit_at(tx, ty) {
                            board.units[idx].web_source_uid = enemy_uid;
                        }
                    }
                }
            }

            _ => {
                let tx = qtx as u8;
                let ty = qty as u8;
                let d = enemy_hit_damage(board, tx, ty, damage, vh);
                apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
            }
        }
    }

    // Psion Tyrant: 1 damage to all player units (passive, not an attack — smoke doesn't cancel)
    if board.tyrant_psion {
        let tyrant_alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Lava1" && board.units[i].hp > 0);
        if tyrant_alive {
            for i in 0..board.unit_count as usize {
                let u = &mut board.units[i];
                if u.is_player() && u.hp > 0 {
                    if u.shield() {
                        u.set_shield(false);
                    } else if u.frozen() {
                        u.set_frozen(false);
                    } else {
                        // Weapon-type damage: armor reduces, ACID doubles
                        let actual: i8 = if u.acid() { 2 } else if u.armor() { 0 } else { 1 };
                        u.hp -= actual;
                    }
                }
            }
        } else {
            board.tyrant_psion = false;
        }
    }

    // Count buildings destroyed from result
    buildings_destroyed += result.grid_damage;
    buildings_destroyed
}

/// Trace projectile from enemy position in queued direction.
/// Returns (hit_x, hit_y) or None.
fn find_projectile_target(board: &Board, ex: u8, ey: u8, orig_x: u8, orig_y: u8, qtx: i8, qty: i8) -> Option<(u8, u8)> {
    if qtx < 0 { return None; }

    // Compute direction from ORIGINAL position to queued target.
    // This preserves the cardinal attack direction after pushes.
    let dx = (qtx - orig_x as i8).signum();
    let dy = (qty - orig_y as i8).signum();

    // Must be a valid cardinal direction (exactly one axis non-zero)
    if (dx != 0 && dy != 0) || (dx == 0 && dy == 0) { return None; }

    // Trace from CURRENT position in the original direction
    for i in 1..8i8 {
        let nx = ex as i8 + dx * i;
        let ny = ey as i8 + dy * i;
        if !in_bounds(nx, ny) { break; }
        let nxu = nx as u8;
        let nyu = ny as u8;

        let tile = board.tile(nxu, nyu);
        if tile.terrain == Terrain::Mountain { return Some((nxu, nyu)); }
        if tile.terrain == Terrain::Building && tile.building_hp > 0 { return Some((nxu, nyu)); }
        if board.unit_at(nxu, nyu).is_some() { return Some((nxu, nyu)); }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn add_enemy_with_type(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8, type_name: &str, qtx: i8, qty: i8) -> usize {
        let mut unit = Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            queued_target_x: qtx,
            queued_target_y: qty,
            weapon_damage: 0,
            ..Default::default()
        };
        unit.set_type_name(type_name);
        board.add_unit(unit)
    }

    fn default_orig_pos(board: &Board) -> [(u8, u8); 16] {
        let mut pos = [(0u8, 0u8); 16];
        for i in 0..board.unit_count as usize {
            pos[i] = (board.units[i].x, board.units[i].y);
        }
        pos
    }

    #[test]
    fn test_scarab_artillery_hits_target_directly() {
        let mut board = Board::default();
        // Scarab at (0,0) targeting building at (4,0) — artillery arcs over obstacles
        board.tile_mut(2, 0).terrain = Terrain::Mountain; // obstacle between
        board.tile_mut(4, 0).terrain = Terrain::Building;
        board.tile_mut(4, 0).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 0, 0, 3, "Scarab1", 4, 0);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig);

        // Artillery should hit building at (4,0) directly, ignoring mountain
        assert_eq!(board.tile(4, 0).building_hp, 0, "Scarab artillery should hit building through mountain");
    }

    #[test]
    fn test_crab_hits_two_tiles() {
        let mut board = Board::default();
        // Crab at (0,0) targeting (4,0) — should also hit (5,0)
        board.tile_mut(4, 0).terrain = Terrain::Building;
        board.tile_mut(4, 0).building_hp = 1;
        board.tile_mut(5, 0).terrain = Terrain::Building;
        board.tile_mut(5, 0).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 0, 0, 3, "Crab1", 4, 0);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig);

        assert_eq!(board.tile(4, 0).building_hp, 0, "Crab should hit first tile");
        assert_eq!(board.tile(5, 0).building_hp, 0, "Crab should hit second tile");
    }

    #[test]
    fn test_blob_self_destructs_all_adjacent() {
        let mut board = Board::default();
        // Blob at (3,3) — self-AoE should hit self + 4 adjacent
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;
        board.tile_mut(4, 3).terrain = Terrain::Building;
        board.tile_mut(4, 3).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 3, 3, 1, "BlobMini", 3, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig);

        // Blob should self-destruct (dies from AOE_CENTER)
        assert_eq!(board.units[0].hp, 0, "Blob should die from self-damage");
        // Adjacent buildings should take damage
        assert_eq!(board.tile(3, 4).building_hp, 0, "Adjacent building should be hit");
        assert_eq!(board.tile(4, 3).building_hp, 0, "Adjacent building should be hit");
    }

    #[test]
    fn test_beetle_charge_from_distance() {
        let mut board = Board::default();
        // Beetle at (0,0) targeting (5,0) — charges from current position
        board.tile_mut(5, 0).terrain = Terrain::Building;
        board.tile_mut(5, 0).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 0, 0, 4, "Beetle1", 5, 0);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig);

        // Beetle should charge and hit the building
        assert_eq!(board.tile(5, 0).building_hp, 0, "Beetle charge should hit building");
    }

    #[test]
    fn test_digger_hits_all_adjacent() {
        let mut board = Board::default();
        // Digger at (3,3) — self_aoe hits all 4 adjacent
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;
        board.tile_mut(3, 2).terrain = Terrain::Building;
        board.tile_mut(3, 2).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 3, 3, 2, "Digger1", 3, 4);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig);

        // Digger self-aoe should hit adjacent buildings (both directions)
        assert_eq!(board.tile(3, 4).building_hp, 0, "Digger should hit N building");
        assert_eq!(board.tile(3, 2).building_hp, 0, "Digger should hit S building");
    }

    #[test]
    fn test_enemy_weapon_for_type_mapping() {
        assert_eq!(enemy_weapon_for_type("Firefly1"), WId::FireflyAtk1);
        assert_eq!(enemy_weapon_for_type("Scarab2"), WId::ScarabAtk2);
        assert_eq!(enemy_weapon_for_type("Beetle1"), WId::BeetleAtk1);
        assert_eq!(enemy_weapon_for_type("Digger1"), WId::DiggerAtk1);
        assert_eq!(enemy_weapon_for_type("BlobMini"), WId::BlobAtk1);
        assert_eq!(enemy_weapon_for_type("Crab1"), WId::CrabAtk1);
        assert_eq!(enemy_weapon_for_type("Unknown"), WId::None);
    }

    fn add_mech_unit(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8) -> usize {
        let mut unit = Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::ACTIVE | UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        };
        unit.set_type_name("PunchMech");
        board.add_unit(unit)
    }

    #[test]
    fn test_alpha_centipede_applies_acid_to_target() {
        let mut board = Board::default();
        // Alpha Centipede at (0,3) firing east, target mech at (4,3).
        // Corrosive Vomit: 2 damage + ACID.
        let mech_idx = add_mech_unit(&mut board, 10, 4, 3, 3);
        add_enemy_with_type(&mut board, 1, 0, 3, 5, "Centipede2", 4, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig);

        assert_eq!(board.units[mech_idx].hp, 1, "Mech should take 2 damage from Corrosive Vomit");
        assert!(board.units[mech_idx].acid(), "Mech should be ACID'd by Corrosive Vomit");
    }

    #[test]
    fn test_alpha_centipede_aoe_perpendicular_splashes() {
        let mut board = Board::default();
        // Alpha Centipede at (0,3) firing east, target mech at (4,3).
        // Perpendicular tiles (4,2) and (4,4) should also take 2 dmg + ACID.
        let target_idx = add_mech_unit(&mut board, 10, 4, 3, 5);
        let north_idx = add_mech_unit(&mut board, 11, 4, 4, 5);
        let south_idx = add_mech_unit(&mut board, 12, 4, 2, 5);
        add_enemy_with_type(&mut board, 1, 0, 3, 5, "Centipede2", 4, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig);

        assert_eq!(board.units[target_idx].hp, 3, "Primary target should take 2 damage");
        assert!(board.units[target_idx].acid(), "Primary target should be ACID'd");
        assert_eq!(board.units[north_idx].hp, 3, "Perpendicular N tile should take 2 damage");
        assert!(board.units[north_idx].acid(), "Perpendicular N tile should be ACID'd");
        assert_eq!(board.units[south_idx].hp, 3, "Perpendicular S tile should take 2 damage");
        assert!(board.units[south_idx].acid(), "Perpendicular S tile should be ACID'd");
    }

    #[test]
    fn test_alpha_scorpion_webs_target() {
        let mut board = Board::default();
        // Alpha Scorpion at (3,3) adjacent to mech at (3,4). Goring Spinneret:
        // 3 damage + WEB.
        let mech_idx = add_mech_unit(&mut board, 10, 3, 4, 5);
        let _scorp_idx = add_enemy_with_type(&mut board, 42, 3, 3, 5, "Scorpion2", 3, 4);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig);

        assert_eq!(board.units[mech_idx].hp, 2, "Mech should take 3 damage from Goring Spinneret");
        assert!(board.units[mech_idx].web(), "Mech should be webbed by Goring Spinneret");
        assert_eq!(board.units[mech_idx].web_source_uid, 42,
            "Web source should be Scorpion UID (for web-break on push/kill)");
    }

    #[test]
    fn test_alpha_hornet_line_still_hits_both_tiles() {
        // Regression: Alpha Hornet's 2-tile line attack (weapon_behind) should
        // still damage both tiles after the fix.
        let mut board = Board::default();
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 1;
        board.tile_mut(4, 3).terrain = Terrain::Building;
        board.tile_mut(4, 3).building_hp = 1;
        // Hornet at (2,3) firing east, queued target (3,3). weapon_target_behind=true.
        let mut unit = Unit {
            uid: 1, x: 2, y: 3, hp: 4, max_hp: 4,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            queued_target_x: 3,
            queued_target_y: 3,
            weapon_damage: 0,
            weapon_target_behind: true,
            ..Default::default()
        };
        unit.set_type_name("Hornet2");
        board.add_unit(unit);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig);

        assert_eq!(board.tile(3, 3).building_hp, 0, "First tile destroyed");
        assert_eq!(board.tile(4, 3).building_hp, 0, "Behind tile destroyed");
    }
}
