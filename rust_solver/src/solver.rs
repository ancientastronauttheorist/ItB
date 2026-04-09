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

fn get_weapon_targets(board: &Board, mx: u8, my: u8, weapon_id: WId) -> Vec<(u8, u8)> {
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
        WeaponType::Projectile | WeaponType::Pull | WeaponType::Laser => {
            for &(dx, dy) in &DIRS {
                let nx = mx as i8 + dx;
                let ny = my as i8 + dy;
                if in_bounds(nx, ny) {
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

fn enumerate_actions(board: &Board, mech_idx: usize) -> Vec<Action> {
    let unit = &board.units[mech_idx];
    let mut actions = Vec::with_capacity(100);

    let positions = reachable_tiles(board, mech_idx);

    for &pos in &positions {
        let old = (unit.x, unit.y);

        // Temporarily move for target enumeration
        // (We don't actually mutate — just compute targets from pos)
        // Move-only
        actions.push((pos, WId::None, (255, 255)));

        // Primary weapon
        let w1_id = WId::from_raw(unit.weapon.0);
        if w1_id != WId::None {
            for &target in &get_weapon_targets(board, pos.0, pos.1, w1_id) {
                actions.push((pos, w1_id, target));
            }
        }

        // Secondary weapon
        let w2_id = WId::from_raw(unit.weapon2.0);
        if w2_id != WId::None {
            for &target in &get_weapon_targets(board, pos.0, pos.1, w2_id) {
                actions.push((pos, w2_id, target));
            }
        }

        // Repair (if damaged/on_fire/acid and not smoked)
        let tile = board.tile(pos.0, pos.1);
        if !tile.smoke() {
            if unit.hp < unit.max_hp || unit.fire() || unit.acid() {
                actions.push((pos, WId::Repair, pos));
            }
        }

        let _ = old; // suppress unused warning
    }

    actions
}

// ── Action pruning ───────────────────────────────────────────────────────────

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
    blast_psion_was_active: bool,
    armor_psion_was_active: bool,
) {
    if Instant::now() > deadline { return; }

    if depth >= mech_order.len() {
        // All mechs acted — simulate enemy attacks and evaluate
        let mut b_eval = board.clone();
        simulate_enemy_attacks(&mut b_eval, original_positions);
        let score = evaluate(&b_eval, spawn_points, weights, kills_so_far, blast_psion_was_active, armor_psion_was_active);

        if score > *best_score {
            *best_score = score;
            *best_actions = actions_so_far.clone();
        }
        return;
    }

    let mech_idx = mech_order[depth];
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
            threat_tiles, building_threats, spawn_bits,
            original_positions,
            spawn_points, max_actions, weights, deadline,
            best_score, best_actions,
            blast_psion_was_active,
            armor_psion_was_active,
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
    let blast_psion_was_active = board.blast_psion;
    let armor_psion_was_active = board.armor_psion;

    let perms = permutations(n);
    let total_perms = perms.len();
    let deadline = Instant::now() + Duration::from_secs_f64(time_limit_secs);

    // Map permutation indices to actual unit indices
    let perm_mapped: Vec<Vec<usize>> = perms.iter()
        .map(|p| p.iter().map(|&i| active[i]).collect())
        .collect();

    // Parallel search via rayon
    let results: Vec<(f64, Vec<MechAction>, bool)> = perm_mapped.par_iter().map(|mech_order| {
        let mut best_score = f64::NEG_INFINITY;
        let mut best_actions = Vec::new();
        let mut actions_buf = Vec::new();

        search_recursive(
            board, mech_order, 0,
            &mut actions_buf, 0,
            threat_tiles, building_threats, spawn_bits,
            &original_positions,
            spawn_points, effective_max, weights, deadline,
            &mut best_score, &mut best_actions,
            blast_psion_was_active,
            armor_psion_was_active,
        );

        let timed_out = Instant::now() > deadline;
        (best_score, best_actions, timed_out)
    }).collect();

    // Find global best
    let mut best = Solution::empty();
    let mut any_timed_out = false;
    for (score, actions, timed_out) in results {
        if timed_out { any_timed_out = true; }
        if score > best.score {
            best.score = score;
            best.actions = actions;
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
