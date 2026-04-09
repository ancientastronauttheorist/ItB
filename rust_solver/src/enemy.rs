/// Enemy attack simulation — post-mech-action phase.
///
/// Processes enemies in UID order (ascending = game's attack order).
/// Re-traces projectile paths on the post-mech board state.

use crate::types::*;
use crate::board::*;
use crate::weapons::*;

/// Apply one enemy hit to a tile. Returns grid power lost.
fn apply_enemy_hit(board: &mut Board, x: u8, y: u8, damage: u8) -> i32 {
    if !in_bounds(x as i8, y as i8) { return 0; }

    // Mech absorbs hit
    if let Some(idx) = board.unit_at(x, y) {
        if board.units[idx].is_player() {
            board.units[idx].hp -= damage as i8;
            if board.units[idx].hp < 0 { board.units[idx].hp = 0; }
            return 0;
        }
    }

    // Building takes damage
    let tile = board.tile_mut(x, y);
    if tile.terrain == Terrain::Building && tile.building_hp > 0 {
        let actual = damage.min(tile.building_hp);
        tile.building_hp -= actual;
        if tile.building_hp == 0 {
            tile.terrain = Terrain::Rubble;
        }
        return actual as i32;
    }

    0
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

/// Simulate all enemy attacks on the post-mech-action board.
/// Processes in UID order. Returns buildings destroyed count.
///
/// `original_positions`: maps unit index -> (orig_x, orig_y) for melee range check.
pub fn simulate_enemy_attacks(
    board: &mut Board,
    original_positions: &[(u8, u8); 16],
) -> i32 {
    let mut buildings_destroyed = 0;

    // Fire tick: burning units take 1 damage before attacks
    for i in 0..board.unit_count as usize {
        if board.units[i].fire() && board.units[i].hp > 0 {
            board.units[i].hp -= 1;
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

        let damage = if enemy.weapon_damage > 0 {
            enemy.weapon_damage
        } else {
            // Fallback: look up weapon def
            let wid = crate::weapons::wid_from_str(""); // simplified
            let wdef = weapon_def(wid);
            if wdef.damage > 0 { wdef.damage } else { 1 }
        };

        let ex = enemy.x;
        let ey = enemy.y;
        let qtx = enemy.queued_target_x;
        let qty = enemy.queued_target_y;
        let weapon_behind = enemy.weapon_target_behind;

        // Determine weapon type from the weapon field
        let enemy_weapon = enemy.weapon;
        let wdef = weapon_def(WId::None); // default
        let weapon_type = if enemy_weapon.0 > 0 && (enemy_weapon.0 as usize) < WEAPON_COUNT {
            // Safety: cast the raw weapon id
            let wid_val = enemy_weapon.0 as u8;
            WEAPONS.get(wid_val as usize).map(|w| w.weapon_type).unwrap_or(WeaponType::Melee)
        } else {
            WeaponType::Melee
        };
        let _ = wdef;

        let orig = original_positions[ei];

        match weapon_type {
            WeaponType::Projectile => {
                // Re-trace projectile on current board using ORIGINAL position for direction
                if let Some((tx, ty)) = find_projectile_target(board, ex, ey, orig.0, orig.1, qtx, qty) {
                    buildings_destroyed += apply_enemy_hit(board, tx, ty, damage);
                }
            }
            WeaponType::Melee | WeaponType::Charge => {
                let tx = qtx as u8;
                let ty = qty as u8;

                // Skip if pushed away from target (no longer adjacent)
                let curr_dist = (ex as i32 - tx as i32).abs() + (ey as i32 - ty as i32).abs();
                if curr_dist > 1 { continue; }

                // Primary hit
                buildings_destroyed += apply_enemy_hit(board, tx, ty, damage);

                // TargetBehind
                if weapon_behind {
                    let ddx = tx as i8 - ex as i8;
                    let ddy = ty as i8 - ey as i8;
                    let bx = tx as i8 + ddx;
                    let by = ty as i8 + ddy;
                    if in_bounds(bx, by) {
                        buildings_destroyed += apply_enemy_hit(board, bx as u8, by as u8, damage);
                    }
                }
            }
            _ => {
                // Fallback: use queued target directly
                let tx = qtx as u8;
                let ty = qty as u8;
                buildings_destroyed += apply_enemy_hit(board, tx, ty, damage);
            }
        }
    }

    buildings_destroyed
}
