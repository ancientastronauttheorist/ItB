/// The main solver: find the optimal mech action sequence.
///
/// Recursive search over all mech orderings (parallelized via rayon).
/// Each permutation gets its own board copy and full time budget.

use std::time::{Duration, Instant};
use rayon::prelude::*;

use crate::types::*;
use crate::board::*;
use crate::weapons::*;
use crate::movement::*;
use crate::simulate::*;
use crate::enemy::*;
use crate::evaluate::*;

// ── MechAction ───────────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct MechAction {
    pub mech_uid: u16,
    pub mech_type: String,
    pub move_to: (u8, u8),
    pub weapon: WId,
    pub target: (u8, u8),
    pub description: String,
}

// ── Solution ─────────────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct Solution {
    pub actions: Vec<MechAction>,
    pub score: f64,
    pub elapsed_secs: f64,
    pub timed_out: bool,
    pub permutations_tried: usize,
    pub total_permutations: usize,
}

impl Solution {
    pub fn empty() -> Self {
        Solution {
            actions: Vec::new(),
            score: f64::NEG_INFINITY,
            elapsed_secs: 0.0,
            timed_out: false,
            permutations_tried: 0,
            total_permutations: 0,
        }
    }
}

// ── Weapon target enumeration ────────────────────────────────────────────────

pub(crate) fn get_weapon_targets(board: &Board, mx: u8, my: u8, weapon_id: WId, mech_from: (u8, u8)) -> Vec<(u8, u8)> {
    let wdef = weapon_def(weapon_id);
    let mut targets = Vec::new();

    match wdef.weapon_type {
        WeaponType::Melee => {
            for &(dx, dy) in &DIRS {
                let nx = mx as i8 + dx;
                let ny = my as i8 + dy;
                if !in_bounds(nx, ny) { continue; }
                let nxu = nx as u8;
                let nyu = ny as u8;
                // Throw weapons (Vice Fist): the game rejects the target entirely
                // unless the throw destination — attacker + (attacker-target) — is
                // an unoccupied tile. Any unit, mountain, building, or wreck there
                // makes the weapon unfireable (the in-game "no target available"
                // error). Water / chasm / lava ARE valid destinations — throwing a
                // non-flying enemy into deadly terrain is the main use of the weapon.
                // Exception: if the destination equals the mech's pre-move tile, the
                // board still shows the mech there (board isn't updated during action
                // enumeration), but that tile will be vacated once the move executes,
                // so treat it as empty.
                if wdef.push == PushDir::Throw {
                    let throw_x = mx as i8 - dx;
                    let throw_y = my as i8 - dy;
                    if !in_bounds(throw_x, throw_y) { continue; }
                    let txu = throw_x as u8;
                    let tyu = throw_y as u8;
                    if (txu, tyu) != mech_from {
                        if board.unit_at(txu, tyu).is_some() { continue; }
                        if board.wreck_at(txu, tyu) { continue; }
                        let dest_tile = board.tile(txu, tyu);
                        if dest_tile.terrain == Terrain::Mountain { continue; }
                        if dest_tile.terrain == Terrain::Building && dest_tile.building_hp > 0 {
                            continue;
                        }
                    }
                }
                let has_unit = board.unit_at(nxu, nyu).is_some();
                if has_unit {
                    targets.push((nxu, nyu));
                } else if wdef.push != PushDir::None {
                    let tile = board.tile(nxu, nyu);
                    if !(tile.terrain == Terrain::Building && tile.building_hp > 0) {
                        targets.push((nxu, nyu));
                    }
                }
            }
        }
        WeaponType::Projectile | WeaponType::Laser => {
            for &(dx, dy) in &DIRS {
                let nx = mx as i8 + dx;
                let ny = my as i8 + dy;
                if !in_bounds(nx, ny) { continue; }
                // For projectiles: skip directions where the first obstacle is a
                // building (no enemy in between). Shooting our own buildings is
                // never beneficial and costs grid power.
                if wdef.weapon_type == WeaponType::Projectile && !wdef.phase() {
                    let mut first_is_building = false;
                    for i in 1..8i8 {
                        let px = mx as i8 + dx * i;
                        let py = my as i8 + dy * i;
                        if !in_bounds(px, py) { break; }
                        let tile = board.tile(px as u8, py as u8);
                        if tile.terrain == Terrain::Mountain { break; }
                        if tile.is_building() {
                            first_is_building = true;
                            break;
                        }
                        if (px as u8, py as u8) != mech_from
                            && board.unit_at(px as u8, py as u8).is_some()
                        {
                            break; // unit before building — safe to fire
                        }
                    }
                    if first_is_building { continue; }
                }
                targets.push((nx as u8, ny as u8));
            }
        }
        WeaponType::Pull => {
            // Pull weapons fire axis-aligned like artillery. The simulate path
            // uses cardinal_direction(attacker→target) to pick the pull axis, so
            // the target must lie on a cardinal line. Range is [range_min, range_max]
            // (0 means unlimited = 7).
            let min_r = wdef.range_min.max(1);
            let max_r = if wdef.range_max == 0 { 7 } else { wdef.range_max };
            for &(dx, dy) in &DIRS {
                for i in (min_r as i8)..=(max_r as i8) {
                    let nx = mx as i8 + dx * i;
                    let ny = my as i8 + dy * i;
                    if !in_bounds(nx, ny) { break; }
                    targets.push((nx as u8, ny as u8));
                }
            }
        }
        WeaponType::Artillery => {
            let min_r = wdef.range_min;
            for x in 0..8u8 {
                for y in 0..8u8 {
                    let dist = (x as i8 - mx as i8).unsigned_abs() + (y as i8 - my as i8).unsigned_abs();
                    if dist < min_r { continue; }
                    if x != mx && y != my { continue; } // axis-aligned only
                    let tile = board.tile(x, y);
                    if tile.terrain == Terrain::Building && tile.building_hp > 0 { continue; }
                    targets.push((x, y));
                }
            }
        }
        WeaponType::SelfAoe => {
            targets.push((mx, my));
        }
        WeaponType::Charge => {
            for &(dx, dy) in &DIRS {
                let nx = mx as i8 + dx;
                let ny = my as i8 + dy;
                if in_bounds(nx, ny) {
                    targets.push((nx as u8, ny as u8));
                }
            }
        }
        WeaponType::Leap => {
            let max_r = if wdef.range_max == 0 { 8 } else { wdef.range_max };
            for x in 0..8u8 {
                for y in 0..8u8 {
                    let dist = (x as i8 - mx as i8).unsigned_abs() + (y as i8 - my as i8).unsigned_abs();
                    if dist < 1 || dist > max_r { continue; }
                    if !board.is_blocked(x, y, true) { // leap always uses flying passability
                        targets.push((x, y));
                    }
                }
            }
        }
        WeaponType::Swap => {
            let max_r = if wdef.range_max == 0 { 8 } else { wdef.range_max };
            for x in 0..8u8 {
                for y in 0..8u8 {
                    let dist = (x as i8 - mx as i8).unsigned_abs() + (y as i8 - my as i8).unsigned_abs();
                    if dist >= 1 && dist <= max_r {
                        targets.push((x, y));
                    }
                }
            }
        }
        _ => {} // Passive, Deploy, TwoClick
    }

    targets
}

// ── Action enumeration ───────────────────────────────────────────────────────

type Action = ((u8, u8), WId, (u8, u8)); // (move_to, weapon, target)

/// Check if a weapon action would have any effect on the board.
/// Returns false when firing at empty space where no unit can be hit or pushed —
/// the solver should prefer move-only/skip in that case. Conservative: returns
/// true when uncertain (e.g., unknown weapon types) to avoid hiding real options.
fn weapon_action_has_effect(board: &Board, move_to: (u8, u8), weapon_id: WId, target: (u8, u8)) -> bool {
    if weapon_id == WId::None || weapon_id == WId::Repair {
        return true;
    }
    let wdef = weapon_def(weapon_id);
    let (mx, my) = move_to;

    let unit_at = |x: u8, y: u8| board.unit_at(x, y).is_some();
    let adj_has_unit = |x: u8, y: u8| {
        for &(dx, dy) in &DIRS {
            let ax = x as i8 + dx;
            let ay = y as i8 + dy;
            if in_bounds(ax, ay) && unit_at(ax as u8, ay as u8) { return true; }
        }
        false
    };

    match wdef.weapon_type {
        WeaponType::Melee => unit_at(target.0, target.1),
        WeaponType::Projectile | WeaponType::Laser | WeaponType::Pull => {
            // Trace from move_to toward target direction — any unit in line = effect
            let dx = (target.0 as i8 - mx as i8).signum();
            let dy = (target.1 as i8 - my as i8).signum();
            if dx == 0 && dy == 0 { return false; }
            for i in 1..8i8 {
                let px = mx as i8 + dx * i;
                let py = my as i8 + dy * i;
                if !in_bounds(px, py) { break; }
                if unit_at(px as u8, py as u8) { return true; }
                let tile = board.tile(px as u8, py as u8);
                if tile.terrain == Terrain::Mountain || tile.is_building() { break; }
            }
            false
        }
        WeaponType::Artillery => unit_at(target.0, target.1) || adj_has_unit(target.0, target.1),
        WeaponType::SelfAoe => unit_at(mx, my) || adj_has_unit(mx, my),
        WeaponType::Charge => {
            // Charges forward until it hits something
            let dx = (target.0 as i8 - mx as i8).signum();
            let dy = (target.1 as i8 - my as i8).signum();
            if dx == 0 && dy == 0 { return false; }
            for i in 1..8i8 {
                let px = mx as i8 + dx * i;
                let py = my as i8 + dy * i;
                if !in_bounds(px, py) { return false; }
                if unit_at(px as u8, py as u8) { return true; }
                let tile = board.tile(px as u8, py as u8);
                if tile.terrain == Terrain::Mountain || tile.is_building() { return false; }
            }
            false
        }
        // Leap/Swap/Deploy/TwoClick: positional or utility — don't filter
        _ => true,
    }
}

fn enumerate_actions(board: &Board, mech_idx: usize) -> Vec<Action> {
    let unit = &board.units[mech_idx];
    let mut actions = Vec::with_capacity(100);

    // Frozen mechs can ONLY repair (to break free). No movement, no attacks.
    if unit.frozen() {
        let pos = (unit.x, unit.y);
        let tile = board.tile(pos.0, pos.1);
        if !tile.smoke() {
            actions.push((pos, WId::Repair, pos));
        }
        return actions;
    }

    // MID_ACTION mechs (can_move=false): already moved, only generate
    // attack/repair options from current position.
    let positions = if unit.can_move() {
        reachable_tiles(board, mech_idx)
    } else {
        vec![(unit.x, unit.y)]
    };

    for &pos in &positions {
        // Move-only / skip — always available so search can stay put.
        // (For MID_ACTION mechs, this is the "skip attack" option.)
        actions.push((pos, WId::None, (255, 255)));

        // Smoke blocks ALL actions (attack + repair) — only move-only is valid
        let tile = board.tile(pos.0, pos.1);
        if !tile.smoke() {
            // Primary weapon — filter out no-op fires (empty space, nothing affected)
            let w1_id = WId::from_raw(unit.weapon.0);
            if w1_id != WId::None {
                let mech_from = (unit.x, unit.y);
                for &target in &get_weapon_targets(board, pos.0, pos.1, w1_id, mech_from) {
                    if weapon_action_has_effect(board, pos, w1_id, target) {
                        actions.push((pos, w1_id, target));
                    }
                }
            }

            // Secondary weapon
            let w2_id = WId::from_raw(unit.weapon2.0);
            if w2_id != WId::None {
                for &target in &get_weapon_targets(board, pos.0, pos.1, w2_id, (unit.x, unit.y)) {
                    if weapon_action_has_effect(board, pos, w2_id, target) {
                        actions.push((pos, w2_id, target));
                    }
                }
            }

            // Repair (if damaged/on_fire/acid/frozen)
            if unit.hp < unit.max_hp || unit.fire() || unit.acid() || unit.frozen() {
                actions.push((pos, WId::Repair, pos));
            }
        }
    }

    actions
}

// ── Action pruning ───────────────────────────────────────────────────────────

/// Check if pushing a unit from (x,y) in `direction` would damage a building.
/// Returns true when the push destination tile is a building (push is blocked,
/// both the pushed unit and the building take 1 bump damage).
fn push_hits_building(x: u8, y: u8, direction: usize, board: &Board) -> bool {
    let (dx, dy) = DIRS[direction];
    let nx = x as i8 + dx;
    let ny = y as i8 + dy;
    if !in_bounds(nx, ny) { return false; }
    board.tile(nx as u8, ny as u8).is_building()
}

fn prune_actions(
    board: &Board,
    _mech_idx: usize,
    actions: &mut Vec<Action>,
    threat_tiles: u64,       // bitset
    building_threats: u64,   // bitset
    spawn_bits: u64,         // bitset of spawn tiles
    max_n: usize,
) {
    if actions.len() <= max_n { return; }

    // Score each action by heuristic
    let mut scored: Vec<(i32, usize)> = actions.iter().enumerate().map(|(i, &(move_to, weapon_id, target))| {
        let mut s = 0i32;

        let move_bit = 1u64 << xy_to_idx(move_to.0, move_to.1);

        // Body-blocking a building threat
        if building_threats & move_bit != 0 { s += 200; }

        // Attacking near threats
        if weapon_id != WId::None && weapon_id != WId::Repair && target.0 < 8 {
            let target_bit = 1u64 << xy_to_idx(target.0, target.1);
            if threat_tiles & target_bit != 0 { s += 100; }

            // Check if target has a unit (prefer attacking units over empty)
            if board.unit_at(target.0, target.1).is_some() { s += 10; }

            // Friendly fire penalty
            if let Some(idx) = board.unit_at(target.0, target.1) {
                if board.units[idx].is_player() { s -= 300; }
            }

            // BUILDING DAMAGE PENALTY: penalize actions that push units into buildings.
            // When a push is blocked by a building, both the unit and building take
            // 1 bump damage — losing grid power. Apply -300 per building at risk.
            let wdef = weapon_def(weapon_id);
            if wdef.push != PushDir::None {
                match wdef.weapon_type {
                    // Melee / Projectile / Charge / Laser: Forward push on the hit target
                    WeaponType::Melee | WeaponType::Projectile | WeaponType::Charge | WeaponType::Laser => {
                        if wdef.push == PushDir::Forward || wdef.push == PushDir::Backward || wdef.push == PushDir::Flip {
                            if let Some(dir) = direction_between(move_to.0, move_to.1, target.0, target.1) {
                                let push_dir = match wdef.push {
                                    PushDir::Forward => dir,
                                    PushDir::Backward | PushDir::Flip => (dir + 2) % 4,
                                    _ => dir,
                                };
                                if push_hits_building(target.0, target.1, push_dir, board) {
                                    s -= 300;
                                }
                            }
                        } else if wdef.push == PushDir::Outward {
                            // Projectile with outward push (e.g., Grav Cannon): push target outward
                            if let Some(dir) = direction_between(move_to.0, move_to.1, target.0, target.1) {
                                if push_hits_building(target.0, target.1, dir, board) {
                                    s -= 300;
                                }
                            }
                        }
                        // Also check AoE perpendicular tiles (e.g., Janus Cannon)
                        if wdef.aoe_perpendicular() {
                            if let Some(dir) = direction_between(move_to.0, move_to.1, target.0, target.1) {
                                for &perp in &[(dir + 1) % 4, (dir + 3) % 4] {
                                    let (pdx, pdy) = DIRS[perp];
                                    let px = target.0 as i8 + pdx;
                                    let py = target.1 as i8 + pdy;
                                    if in_bounds(px, py) {
                                        let push_d = if wdef.push == PushDir::Forward { dir } else { perp };
                                        if push_hits_building(px as u8, py as u8, push_d, board) {
                                            s -= 300;
                                        }
                                    }
                                }
                            }
                        }
                    }
                    // Artillery: center gets pushed in attack direction (Forward) or outward;
                    // adjacent tiles get pushed outward if aoe_adjacent
                    WeaponType::Artillery => {
                        // Center tile push
                        if let Some(dir) = direction_between(move_to.0, move_to.1, target.0, target.1) {
                            if wdef.push == PushDir::Forward {
                                if push_hits_building(target.0, target.1, dir, board) {
                                    s -= 300;
                                }
                            }
                        }
                        // Adjacent tiles pushed outward
                        if wdef.aoe_adjacent() && wdef.push == PushDir::Outward {
                            for (d, &(dx, dy)) in DIRS.iter().enumerate() {
                                let nx = target.0 as i8 + dx;
                                let ny = target.1 as i8 + dy;
                                if !in_bounds(nx, ny) { continue; }
                                if push_hits_building(nx as u8, ny as u8, d, board) {
                                    // Only penalize if there's actually a unit to push
                                    if board.unit_at(nx as u8, ny as u8).is_some() {
                                        s -= 300;
                                    }
                                }
                            }
                        }
                    }
                    // SelfAoe (e.g., Science Mech push): pushes all 4 adjacent tiles outward
                    WeaponType::SelfAoe => {
                        // move_to is the mech position; adjacent tiles get pushed outward
                        for (d, &(dx, dy)) in DIRS.iter().enumerate() {
                            let nx = move_to.0 as i8 + dx;
                            let ny = move_to.1 as i8 + dy;
                            if !in_bounds(nx, ny) { continue; }
                            let push_d = if wdef.push == PushDir::Outward { d } else { (d + 2) % 4 };
                            if push_hits_building(nx as u8, ny as u8, push_d, board) {
                                if board.unit_at(nx as u8, ny as u8).is_some() {
                                    s -= 300;
                                }
                            }
                        }
                    }
                    // Leap: lands on target, pushes adjacent outward
                    WeaponType::Leap => {
                        if wdef.aoe_adjacent() && wdef.push == PushDir::Outward {
                            for (d, &(dx, dy)) in DIRS.iter().enumerate() {
                                let nx = target.0 as i8 + dx;
                                let ny = target.1 as i8 + dy;
                                if !in_bounds(nx, ny) { continue; }
                                if push_hits_building(nx as u8, ny as u8, d, board) {
                                    if board.unit_at(nx as u8, ny as u8).is_some() {
                                        s -= 300;
                                    }
                                }
                            }
                        }
                    }
                    _ => {}
                }
            }
        }

        // Mech blocks a spawn tile by standing on it
        if spawn_bits & move_bit != 0 { s += 80; }

        // Push enemy onto a spawn tile
        if spawn_bits != 0 && weapon_id != WId::None && weapon_id != WId::Repair && target.0 < 8 {
            if let Some(enemy_idx) = board.unit_at(target.0, target.1) {
                if board.units[enemy_idx].is_enemy() {
                    if let Some(dir) = direction_between(move_to.0, move_to.1, target.0, target.1) {
                        if let Some(dest) = push_destination(target.0, target.1, dir, board) {
                            let dest_bit = 1u64 << xy_to_idx(dest.0, dest.1);
                            if spawn_bits & dest_bit != 0 { s += 60; }
                        }
                    }
                }
            }
        }

        (s, i)
    }).collect();

    scored.sort_by(|a, b| b.0.cmp(&a.0));
    let keep: Vec<Action> = scored.iter().take(max_n).map(|&(_, i)| actions[i]).collect();
    *actions = keep;
}

// ── Recursive search ─────────────────────────────────────────────────────────

fn search_recursive(
    board: &Board,
    mech_order: &[usize],
    depth: usize,
    actions_so_far: &mut Vec<MechAction>,
    kills_so_far: i32,
    bumps_so_far: i32,
    threat_tiles: u64,
    building_threats: u64,
    spawn_bits: u64,
    original_positions: &[(u8, u8); 16],
    spawn_points: &[(u8, u8)],
    max_actions: usize,
    weights: &EvalWeights,
    deadline: Instant,
    best_score: &mut f64,
    best_actions: &mut Vec<MechAction>,
    best_clean_score: &mut f64,
    best_clean_actions: &mut Vec<MechAction>,
    initial_building_count: i32,
    psion_before: &PsionState,
) {
    if Instant::now() > deadline { return; }

    if depth >= mech_order.len() {
        // All mechs acted — snapshot buildings before enemy phase
        let mut b_eval = board.clone();
        let buildings_before_enemy = count_buildings(&b_eval);
        simulate_enemy_attacks(&mut b_eval, original_positions);
        apply_spawn_blocking(&mut b_eval, spawn_points);
        let score = evaluate(&b_eval, spawn_points, weights, kills_so_far, bumps_so_far, psion_before, building_threats);


        if score > *best_score {
            *best_score = score;
            *best_actions = actions_so_far.clone();
        }
        let mech_buildings_lost = initial_building_count - buildings_before_enemy;
        if mech_buildings_lost == 0 && score > *best_clean_score {
            *best_clean_score = score;
            *best_clean_actions = actions_so_far.clone();
        }
        return;
    }

    let mech_idx = mech_order[depth];

    // Skip dead mechs (killed by a previous action in this permutation)
    if !board.units[mech_idx].alive() {
        // Still recurse to the next depth so the remaining mechs can act
        search_recursive(
            board, mech_order, depth + 1,
            actions_so_far, kills_so_far, bumps_so_far,
            threat_tiles, building_threats, spawn_bits,
            original_positions,
            spawn_points, max_actions, weights, deadline,
            best_score, best_actions,
            best_clean_score, best_clean_actions, initial_building_count,
            psion_before,
        );
        return;
    }

    let mut actions = enumerate_actions(board, mech_idx);
    prune_actions(board, mech_idx, &mut actions, threat_tiles, building_threats, spawn_bits, max_actions);

    for &(move_to, weapon_id, target) in &actions {
        if Instant::now() > deadline { return; }

        let mut b_next = board.clone(); // ~800 byte memcpy
        let result = simulate_action(&mut b_next, mech_idx, move_to, weapon_id, target);

        let action = make_action(&board.units[mech_idx], move_to, weapon_id, target);
        actions_so_far.push(action);

        search_recursive(
            &b_next, mech_order, depth + 1,
            actions_so_far,
            kills_so_far + result.enemies_killed,
            bumps_so_far + result.buildings_bump_damaged,
            threat_tiles, building_threats, spawn_bits,
            original_positions,
            spawn_points, max_actions, weights, deadline,
            best_score, best_actions,
            best_clean_score, best_clean_actions, initial_building_count,
            psion_before,
        );

        actions_so_far.pop();
    }
}

fn make_action(unit: &Unit, move_to: (u8, u8), weapon_id: WId, target: (u8, u8)) -> MechAction {
    let name = unit.type_name_str();
    let mut desc = name.to_string();
    if move_to != (unit.x, unit.y) {
        desc += &format!(", move {}\u{2192}{}",
            bridge_to_visual(unit.x, unit.y),
            bridge_to_visual(move_to.0, move_to.1));
    }
    if weapon_id == WId::Repair {
        desc += ", repair";
    } else if weapon_id != WId::None {
        desc += &format!(", fire {} at {}",
            weapon_name(weapon_id),
            bridge_to_visual(target.0, target.1));
    }

    MechAction {
        mech_uid: unit.uid,
        mech_type: name.to_string(),
        move_to,
        weapon: weapon_id,
        target,
        description: desc,
    }
}

// ── Permutation generation ───────────────────────────────────────────────────

fn permutations(n: usize) -> Vec<Vec<usize>> {
    let mut result = Vec::new();
    let mut items: Vec<usize> = (0..n).collect();
    permute(&mut items, 0, &mut result);
    result
}

fn permute(items: &mut Vec<usize>, start: usize, result: &mut Vec<Vec<usize>>) {
    if start == items.len() {
        result.push(items.clone());
        return;
    }
    for i in start..items.len() {
        items.swap(start, i);
        permute(items, start + 1, result);
        items.swap(start, i);
    }
}

// ── Pre-compute threats as bitsets ───────────────────────────────────────────

fn precompute_threats(board: &Board) -> (u64, u64) {
    let mut threat_tiles = 0u64;
    let mut building_threats = 0u64;

    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if !u.is_enemy() || !u.alive() || u.queued_target_x < 0 { continue; }
        let tx = u.queued_target_x as u8;
        let ty = u.queued_target_y as u8;
        let bit = 1u64 << xy_to_idx(tx, ty);
        threat_tiles |= bit;

        let tile = board.tile(tx, ty);
        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
            building_threats |= bit;
        }
    }

    (threat_tiles, building_threats)
}

fn count_buildings(board: &Board) -> i32 {
    let mut count = 0;
    for tile in &board.tiles {
        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
            count += 1;
        }
    }
    count
}

// ── Main solve entry point ───────────────────────────────────────────────────

pub fn solve_turn(
    board: &Board,
    spawn_points: &[(u8, u8)],
    time_limit_secs: f64,
    max_actions_per_mech: usize,
    weights: &EvalWeights,
) -> Solution {
    let active: Vec<usize> = (0..board.unit_count as usize)
        .filter(|&i| {
            let u = &board.units[i];
            u.is_player() && u.alive() && u.active()
                && (u.is_mech() || u.weapon.0 > 0)
        })
        .collect();

    if active.is_empty() {
        return Solution::empty();
    }

    let n = active.len();
    let effective_max = if n >= 4 { max_actions_per_mech.min(25) } else { max_actions_per_mech };
    let (threat_tiles, building_threats) = precompute_threats(board);

    // Precompute spawn tile bitset for pruning
    let mut spawn_bits = 0u64;
    for &(sx, sy) in spawn_points {
        spawn_bits |= 1u64 << xy_to_idx(sx, sy);
    }

    // Original positions for pushed-melee detection
    let mut original_positions = [(0u8, 0u8); 16];
    for i in 0..board.unit_count as usize {
        original_positions[i] = (board.units[i].x, board.units[i].y);
    }

    // Track Psion states before mech actions (for psion kill bonuses)
    let psion_before = PsionState::capture(board);

    let perms = permutations(n);
    let total_perms = perms.len();
    let deadline = Instant::now() + Duration::from_secs_f64(time_limit_secs);

    // Map permutation indices to actual unit indices
    let perm_mapped: Vec<Vec<usize>> = perms.iter()
        .map(|p| p.iter().map(|&i| active[i]).collect())
        .collect();

    // Initial building count for two-stage clean-plan tracking
    let initial_building_count = count_buildings(board);

    // Parallel search via rayon
    let results: Vec<(f64, Vec<MechAction>, f64, Vec<MechAction>, bool)> = perm_mapped.par_iter().map(|mech_order| {
        let mut best_score = f64::NEG_INFINITY;
        let mut best_actions = Vec::new();
        let mut best_clean_score = f64::NEG_INFINITY;
        let mut best_clean_actions = Vec::new();
        let mut actions_buf = Vec::new();

        search_recursive(
            board, mech_order, 0,
            &mut actions_buf, 0, 0,
            threat_tiles, building_threats, spawn_bits,
            &original_positions,
            spawn_points, effective_max, weights, deadline,
            &mut best_score, &mut best_actions,
            &mut best_clean_score, &mut best_clean_actions, initial_building_count,
            &psion_before,
        );

        let timed_out = Instant::now() > deadline;
        (best_score, best_actions, best_clean_score, best_clean_actions, timed_out)
    }).collect();

    // Find global best + global clean best
    let mut best = Solution::empty();
    let mut any_timed_out = false;
    let mut global_clean_score = f64::NEG_INFINITY;
    let mut global_clean_actions = Vec::new();
    for (score, actions, clean_score, clean_actions, timed_out) in results {
        if timed_out { any_timed_out = true; }
        if score > best.score {
            best.score = score;
            best.actions = actions;
        }
        if clean_score > global_clean_score {
            global_clean_score = clean_score;
            global_clean_actions = clean_actions;
        }
    }

    // Two-stage filter: prefer clean plan if within threshold of best
    if global_clean_score > f64::NEG_INFINITY && !best.actions.is_empty() {
        let gap = best.score - global_clean_score;
        let threshold = (best.score.abs() * weights.building_preservation_threshold).max(500.0);
        if gap <= threshold {
            best.score = global_clean_score;
            best.actions = global_clean_actions;
        }
    }

    best.elapsed_secs = (Instant::now() - (deadline - Duration::from_secs_f64(time_limit_secs))).as_secs_f64();
    best.timed_out = any_timed_out;
    best.permutations_tried = total_perms;
    best.total_permutations = total_perms;

    best
}

// ── WId helper ───────────────────────────────────────────────────────────────

impl WId {
    pub fn from_raw(v: u16) -> WId {
        if v == 0 { return WId::None; }
        if v == 0xFFFF { return WId::Repair; }
        // Safety: we trust the values stored in Unit.weapon
        unsafe { std::mem::transmute::<u8, WId>(v as u8) }
    }
}
