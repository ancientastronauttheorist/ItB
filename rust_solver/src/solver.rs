/// The main solver: find the optimal mech action sequence.
///
/// Recursive search over all mech orderings (parallelized via rayon).
/// Each permutation gets its own board copy and full time budget.

use std::cmp::{Ordering, Reverse};
use std::collections::BinaryHeap;
use std::time::{Duration, Instant};
use rayon::prelude::*;

use crate::types::*;
use crate::board::*;
use crate::weapons::*;
use crate::movement::*;
use crate::simulate::*;
use crate::enemy::*;
use crate::evaluate::*;

#[inline]
fn disabled_mask_any(mask: DisabledMask) -> bool {
    mask.iter().any(|&word| word != 0)
}

#[inline]
fn disabled_mask_contains(mask: DisabledMask, weapon_id: WId) -> bool {
    if weapon_id == WId::None {
        return false;
    }
    let bit = weapon_id as usize;
    bit < mask.len() * 128 && ((mask[bit / 128] >> (bit % 128)) & 1) != 0
}

fn mission_missiles_action_bonus(board: &Board, actions: &[MechAction]) -> f64 {
    if board.mission_id != "Mission_Missiles" {
        return 0.0;
    }
    let mut saw_contraption = false;
    let mut used_contraption = false;
    for action in actions {
        if action.mech_type == "Missile_Unit" {
            saw_contraption = true;
            if matches!(action.weapon, WId::MissilesShield | WId::MissilesOneDmg) {
                used_contraption = true;
            }
        }
    }
    if used_contraption {
        60000.0
    } else if saw_contraption {
        -60000.0
    } else {
        0.0
    }
}

pub(crate) fn viscera_nanobots_heal_from_events(events: &[String]) -> i32 {
    events
        .iter()
        .filter_map(|event| event.strip_prefix("viscera_nanobots_heal:"))
        .filter_map(|payload| payload.rsplit(':').next())
        .filter_map(|amount| amount.parse::<i32>().ok())
        .sum()
}

pub(crate) fn powered_blast_from_events(events: &[String]) -> i32 {
    events
        .iter()
        .filter(|event| event.starts_with("achievement_powered_blast:"))
        .count() as i32
}

pub(crate) fn reverse_thrusters_four_damage_from_events(events: &[String]) -> i32 {
    events
        .iter()
        .filter(|event| event.starts_with("achievement_on_the_backburner:"))
        .count() as i32
}

// ── MechAction ───────────────────────────────────────────────────────────────

pub(crate) fn feed_the_flame_from_events(events: &[String]) -> i32 {
    events
        .iter()
        .filter(|event| event.starts_with("achievement_feed_the_flame:"))
        .count() as i32
}

pub(crate) fn arachnoid_spawns_from_events(events: &[String]) -> i32 {
    events
        .iter()
        .filter(|event| event.starts_with("achievement_spider_breeding:"))
        .count() as i32
}

pub(crate) fn lets_walk_control_distance_from_events(events: &[String]) -> i32 {
    events
        .iter()
        .filter_map(|event| {
            let rest = event.strip_prefix("achievement_lets_walk:distance:")?;
            let value = rest.split(':').next()?;
            value.parse::<i32>().ok()
        })
        .sum()
}

pub(crate) fn core_of_the_earth_chasm_falls_from_events(events: &[String]) -> i32 {
    events
        .iter()
        .filter(|event| event.starts_with("achievement_core_of_the_earth:chasm_fall:"))
        .count() as i32
}

#[derive(Clone, Debug)]
pub struct MechAction {
    pub mech_uid: u16,
    pub mech_type: String,
    pub move_to: (u8, u8),
    pub weapon: WId,
    pub target: (u8, u8),
    pub target2: Option<(u8, u8)>,
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

// ── BoundedTopK ──────────────────────────────────────────────────────────────
//
// Keeps the K highest-scoring plans encountered during the search. Backed by
// a min-heap of `Reverse<ScoredPlan>` so we can evict the current worst in
// O(log K) when a better plan arrives. Insertion sequence is the deterministic
// tiebreak: on equal scores, the EARLIER insertion wins (keeps its slot). This
// matters because depth-5 beam search will compound any nondeterminism at
// ties across levels — `tests/test_solver_determinism.py` asserts
// byte-identical output across 10 runs, and unstable tie handling here would
// flake it.

#[derive(Clone, Debug)]
pub struct ScoredPlan {
    pub score: f64,
    pub seq: u64,
    pub actions: Vec<MechAction>,
}

impl PartialEq for ScoredPlan {
    fn eq(&self, other: &Self) -> bool {
        self.score.to_bits() == other.score.to_bits() && self.seq == other.seq
    }
}
impl Eq for ScoredPlan {}
impl Ord for ScoredPlan {
    fn cmp(&self, other: &Self) -> Ordering {
        // "Greater" = better plan: higher score wins; on score tie, the earlier
        // insertion (smaller seq) wins. total_cmp handles any NaN scores
        // deterministically (shouldn't occur, but we don't want a panic here
        // silently corrupting the heap).
        self.score.total_cmp(&other.score)
            .then_with(|| other.seq.cmp(&self.seq))
    }
}
impl PartialOrd for ScoredPlan {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> { Some(self.cmp(other)) }
}

pub struct BoundedTopK {
    capacity: usize,
    heap: BinaryHeap<Reverse<ScoredPlan>>,
    next_seq: u64,
}

impl BoundedTopK {
    pub fn new(capacity: usize) -> Self {
        assert!(capacity >= 1, "BoundedTopK capacity must be >= 1");
        BoundedTopK {
            capacity,
            heap: BinaryHeap::with_capacity(capacity + 1),
            next_seq: 0,
        }
    }

    pub fn len(&self) -> usize { self.heap.len() }
    pub fn is_empty(&self) -> bool { self.heap.is_empty() }

    /// Offer a (score, actions) pair. Clones `actions` only if the plan
    /// actually enters the heap (i.e., beats the current worst slot). A full
    /// search can produce thousands of terminals per permutation — skipping
    /// the clone on rejected candidates keeps memory bounded.
    pub fn offer(&mut self, score: f64, actions: &[MechAction]) {
        let seq = self.next_seq;
        self.next_seq += 1;

        if self.heap.len() < self.capacity {
            let plan = ScoredPlan { score, seq, actions: actions.to_vec() };
            self.heap.push(Reverse(plan));
            return;
        }

        // At capacity. New plan must strictly beat the worst on SCORE to
        // enter — equal scores lose because our Ord treats later seqs as
        // worse (the new insertion is always the latest seq by construction).
        // Checking only the score here is equivalent to a full Ord compare
        // and avoids allocating `actions` for the rejection case.
        let worst_score = match self.heap.peek() {
            Some(Reverse(w)) => w.score,
            None => return,
        };
        if score.total_cmp(&worst_score) != Ordering::Greater {
            return;
        }

        let plan = ScoredPlan { score, seq, actions: actions.to_vec() };
        self.heap.pop();
        self.heap.push(Reverse(plan));
    }

    /// Consume and return plans sorted best-first (highest score, earliest
    /// insertion on ties). `BinaryHeap::into_sorted_vec` returns items in
    /// ascending order of their Ord; for `Reverse<T>`, ascending is the
    /// reverse of `T`, which matches our "best first" requirement.
    pub fn into_sorted_desc(self) -> Vec<ScoredPlan> {
        self.heap.into_sorted_vec().into_iter().map(|Reverse(p)| p).collect()
    }
}

// ── Weapon target enumeration ────────────────────────────────────────────────

fn reverse_thrusters_landing_blocked(
    board: &Board,
    x: u8,
    y: u8,
    flying: bool,
    vacated: (u8, u8),
) -> bool {
    let tile = board.tile(x, y);
    if tile.terrain.blocks_all() {
        return true;
    }
    if !flying && tile.terrain.is_deadly_ground() {
        return true;
    }
    if tile.terrain == Terrain::Building {
        return true;
    }
    if (x, y) != vacated {
        board.unit_at(x, y).is_some() || board.wreck_at(x, y)
    } else {
        false
    }
}

pub(crate) fn get_weapon_targets(
    board: &Board,
    mx: u8,
    my: u8,
    weapon_id: WId,
    mech_from: (u8, u8),
    weapons: &WeaponTable,
) -> Vec<(u8, u8)> {
    let wdef = &weapons[weapon_id as usize];
    let mut targets = Vec::new();

    if weapon_id == WId::VipTruckMove {
        let Some(unit_idx) = board.unit_at(mx, my) else {
            return targets;
        };
        let range = wdef.range_max.max(3);
        for pos in reachable_tiles_with_speed(board, unit_idx, range) {
            if pos != (mx, my) {
                targets.push(pos);
            }
        }
        return targets;
    }

    if is_thermal_discharger(weapon_id) {
        let max_r = wdef.range_max.max(1);
        for &(dx, dy) in &DIRS {
            for i in 1..=(max_r as i8) {
                let nx = mx as i8 + dx * i;
                let ny = my as i8 + dy * i;
                if !in_bounds(nx, ny) { break; }
                targets.push((nx as u8, ny as u8));
            }
        }
        return targets;
    }

    if is_firestorm_generator(weapon_id) {
        let min_r = wdef.range_min.max(1);
        let max_r = wdef.range_max.max(min_r);
        for &(dx, dy) in &DIRS {
            for i in (min_r as i8)..=(max_r as i8) {
                let nx = mx as i8 + dx * i;
                let ny = my as i8 + dy * i;
                if !in_bounds(nx, ny) { break; }
                targets.push((nx as u8, ny as u8));
            }
        }
        return targets;
    }

    match wdef.weapon_type {
        WeaponType::Melee => {
            // For path_size>1 melee (Prime_Spear: Range=2, PathSize=2 in
            // Lua scripts/weapons_prime.lua:792-846) the weapon enumerates
            // tiles +1..=+range_max in each cardinal direction. Lua
            // GetTargetArea breaks only on board edge — units in the path
            // do NOT stop enumeration; they merely receive transit damage
            // when the player picks a further tile. Standard 1-tile melee
            // (range_max=1, the historical default) keeps its prior logic.
            let max_r = wdef.range_max.max(1);
            for &(dx, dy) in &DIRS {
                // Throw weapons (Vice Fist) are always range_max=1 in Lua;
                // check the throw-destination once per direction.
                if wdef.push == PushDir::Throw {
                    let throw_x = mx as i8 - dx;
                    let throw_y = my as i8 - dy;
                    if !in_bounds(throw_x, throw_y) { continue; }
                    let txu = throw_x as u8;
                    let tyu = throw_y as u8;
                    // Throw weapons (Vice Fist): the game rejects the target
                    // entirely unless the throw destination — attacker +
                    // (attacker-target) — is an unoccupied tile. Any unit,
                    // mountain, building, or wreck there makes the weapon
                    // unfireable (the in-game "no target available" error).
                    // Water / chasm / lava ARE valid destinations — throwing
                    // a non-flying enemy into deadly terrain is the main use
                    // of the weapon. Exception: if the destination equals the
                    // mech's pre-move tile, the board still shows the mech
                    // there (board isn't updated during action enumeration),
                    // but that tile will be vacated once the move executes,
                    // so treat it as empty.
                    if (txu, tyu) != mech_from {
                        if board.unit_at(txu, tyu).is_some() { continue; }
                        if board.wreck_at(txu, tyu) { continue; }
                        let dest_tile = board.tile(txu, tyu);
                        if dest_tile.terrain == Terrain::Mountain { continue; }
                        // Any Building terrain blocks Vice Fist targeting,
                        // including destroyed objective unique_buildings
                        // (terrain=Building, hp=0). In-game the target
                        // highlight disappears.
                        if dest_tile.terrain == Terrain::Building { continue; }
                    }
                }
                // Track whether any tile in the path so far holds a unit —
                // this lets a path_size>1 stab target the further tile even
                // when only the closer tile is occupied (the spear damages
                // both, only the furthest is pushed).
                let mut path_has_unit = false;
                for i in 1..=(max_r as i8) {
                    let nx = mx as i8 + dx * i;
                    let ny = my as i8 + dy * i;
                    if !in_bounds(nx, ny) { break; }
                    let nxu = nx as u8;
                    let nyu = ny as u8;
                    let has_unit = board.unit_at(nxu, nyu).is_some();
                    let tile = board.tile(nxu, nyu);
                    if has_unit { path_has_unit = true; }
                    if has_unit || path_has_unit {
                        targets.push((nxu, nyu));
                    } else if wdef.chain() && wdef.building_immune() && tile.is_building() {
                        targets.push((nxu, nyu));
                    } else if wdef.push != PushDir::None {
                        if !(tile.terrain == Terrain::Building && tile.building_hp > 0) {
                            targets.push((nxu, nyu));
                        }
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
            // Pull weapons (Grappling Hook, Gravity Well, etc.) fire a
            // cardinal-line projectile. In-game the line STOPS at the first
            // occupant (unit, mountain, or building) — that occupant IS the
            // only valid target in that direction. Empty tiles, chasms, water,
            // lava, smoke, rubble do NOT stop the line. Without this blocking
            // check the solver enumerated tiles past allied mechs and picked
            // plans the game UI refuses to execute (e.g. Hook Mech D7 → D3
            // with Lightning Mech at D5 in the line). Range = [range_min,
            // range_max], range_max=0 means unlimited (clamped to 7).
            let min_r = wdef.range_min.max(1);
            let max_r = if wdef.range_max == 0 { 7 } else { wdef.range_max };
            for &(dx, dy) in &DIRS {
                for i in (min_r as i8)..=(max_r as i8) {
                    let nx = mx as i8 + dx * i;
                    let ny = my as i8 + dy * i;
                    if !in_bounds(nx, ny) { break; }
                    let ux = nx as u8;
                    let uy = ny as u8;
                    let tile = board.tile(ux, uy);
                    let has_unit = board.unit_at(ux, uy).is_some();
                    let is_mountain = tile.terrain == Terrain::Mountain;
                    // Destroyed unique/objective buildings can remain encoded
                    // as terrain=Building with HP 0. Live Grappling Hook still
                    // treats that ruin as the first projectile blocker, so do
                    // not enumerate units behind it.
                    let is_building = tile.terrain == Terrain::Building;
                    if has_unit || is_mountain || is_building {
                        // First blocker — this is the sole valid target in
                        // this direction. Push it even if non-pushable
                        // (Stable / building / mountain): sim_pull_or_swap
                        // currently no-ops on non-pushable, which matches the
                        // ?-targetable-but-no-effect behavior the player sees.
                        // Full self-pull semantics (mech moves toward Stable
                        // anchor) are a separate TODO.
                        targets.push((ux, uy));
                        break;
                    }
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
                    let zero_damage_building_center_ok = matches!(
                        weapon_id,
                        WId::RangedIgnite | WId::RangedIgniteA
                            | WId::RangedCrackB | WId::RangedCrackAB
                    );
                    if tile.terrain == Terrain::Building
                        && tile.building_hp > 0
                        && !wdef.shield()
                        && !zero_damage_building_center_ok
                    {
                        continue;
                    }
                    targets.push((x, y));
                }
            }
        }
        WeaponType::Deploy => {
            let min_r = wdef.range_min.max(1);
            let max_r = if wdef.range_max == 0 { 8 } else { wdef.range_max };
            for &(dx, dy) in &DIRS {
                for i in (min_r as i8)..=(max_r as i8) {
                    let nx = mx as i8 + dx * i;
                    let ny = my as i8 + dy * i;
                    if !in_bounds(nx, ny) { break; }
                    let ux = nx as u8;
                    let uy = ny as u8;
                    if !board.is_blocked(ux, uy, false) {
                        targets.push((ux, uy));
                    }
                }
            }
        }
        WeaponType::TwoClick if is_force_swap(weapon_id) => {
            for (first, _second) in enumerate_force_swap_targets(board, mx, my) {
                targets.push(first);
            }
        }
        WeaponType::TwoClick if is_ricochet_rocket(weapon_id) => {
            for (first, _second) in enumerate_ricochet_targets(board, mx, my) {
                targets.push(first);
            }
        }
        WeaponType::TwoClick if is_control_shot(weapon_id) => {
            let target_range = control_shot_target_range(wdef);
            let move_budget = control_shot_move_budget(wdef);
            for (first, _second) in
                enumerate_control_shot_targets(board, (mx, my), target_range, move_budget)
            {
                targets.push(first);
            }
        }
        WeaponType::TwoClick if is_deploy_bomb_two_click(weapon_id) => {
            for (dir, _vec) in DIRS.iter().enumerate() {
                targets.extend(enumerate_deploy_bomb_line_targets(board, mx, my, dir, wdef));
            }
        }
        WeaponType::TwoClick if is_hydraulic_lifter(weapon_id) => {
            let throw_range = wdef.range_max.max(1);
            for &(dx, dy) in &DIRS {
                let grab_x = mx as i8 + dx;
                let grab_y = my as i8 + dy;
                if !in_bounds(grab_x, grab_y) { continue; }
                let gx = grab_x as u8;
                let gy = grab_y as u8;
                let Some(unit_idx) = board.unit_at(gx, gy) else { continue; };
                let target = &board.units[unit_idx];
                if !target.pushable() && !target.is_mech() { continue; }

                for i in 1..=(throw_range as i8) {
                    let land_x = grab_x + dx * i;
                    let land_y = grab_y + dy * i;
                    if !in_bounds(land_x, land_y) { break; }
                    let lx = land_x as u8;
                    let ly = land_y as u8;
                    if !board.is_blocked(lx, ly, true) {
                        targets.push((lx, ly));
                    }
                }
            }
        }
        WeaponType::SelfAoe => {
            if is_mass_shift(weapon_id) {
                for &(dx, dy) in &DIRS {
                    let nx = mx as i8 + dx;
                    let ny = my as i8 + dy;
                    if in_bounds(nx, ny) {
                        targets.push((nx as u8, ny as u8));
                    }
                }
            } else {
                targets.push((mx, my));
            }
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
        WeaponType::DashAway => {
            let attacker_flying = board
                .unit_at(mx, my)
                .or_else(|| board.unit_at(mech_from.0, mech_from.1))
                .map(|idx| board.units[idx].flying())
                .unwrap_or(false);
            let min_r = wdef.range_min.max(1);
            let max_r = if wdef.range_max == 0 { 7 } else { wdef.range_max };
            for &(dx, dy) in &DIRS {
                for i in (min_r as i8)..=(max_r as i8) {
                    let nx = mx as i8 + dx * i;
                    let ny = my as i8 + dy * i;
                    if !in_bounds(nx, ny) { break; }
                    let ux = nx as u8;
                    let uy = ny as u8;
                    if !reverse_thrusters_landing_blocked(
                        board,
                        ux,
                        uy,
                        attacker_flying,
                        mech_from,
                    ) {
                        targets.push((ux, uy));
                    }
                }
            }
        }
        WeaponType::Leap => {
            if prime_leap_blocked_by_web(board, mx, my, weapon_id) {
                return targets;
            }
            let max_r = if wdef.range_max == 0 { 8 } else { wdef.range_max };
            let min_r = if wdef.range_min == 0 { 1 } else { wdef.range_min };
            let aerial_bombs = is_aerial_bombs(weapon_id);
            let attacker_flying = board.unit_at(mx, my)
                .map(|idx| board.units[idx].flying())
                .unwrap_or(false);
            // Leap_Attack:GetTargetArea enumerates DIR_VECTORS[i] * k for
            // every range step. That includes variable-range Hydraulic Legs:
            // it can jump far, but only along a row or column.
            for x in 0..8u8 {
                for y in 0..8u8 {
                    if x != mx && y != my { continue; }
                    let dist = (x as i8 - mx as i8).unsigned_abs() + (y as i8 - my as i8).unsigned_abs();
                    if dist < min_r || dist > max_r { continue; }
                    let landing_terrain = board.tile(x, y).terrain;
                    if landing_terrain == Terrain::Chasm { continue; }
                    if !attacker_flying && matches!(landing_terrain, Terrain::Water | Terrain::Lava) {
                        continue;
                    }
                    if aerial_bombs && matches!(landing_terrain, Terrain::Water | Terrain::Lava) {
                        continue;
                    }
                    if !board.is_blocked(x, y, true) { // leap uses flying passability except chasm landings
                        targets.push((x, y));
                    }
                }
            }
        }
        WeaponType::Swap => {
            let max_r = if wdef.range_max == 0 { 8 } else { wdef.range_max };
            let min_r = wdef.range_min.max(1);
            for &(dx, dy) in &DIRS {
                for i in (min_r as i8)..=(max_r as i8) {
                    let nx = mx as i8 + dx * i;
                    let ny = my as i8 + dy * i;
                    if !in_bounds(nx, ny) { break; }
                    targets.push((nx as u8, ny as u8));
                }
            }
        }
        WeaponType::HealAll => {
            // ZONE_ALL: click is just a fire confirmation — the effect is
            // global. Emit the firing mech's own tile as the single target
            // so the MCP click planner has a valid coord and the search
            // doesn't explode into 64 identical actions.
            targets.push((mx, my));
        }
        WeaponType::GlobalPush => {
            // Support_Wind uses four fixed target zones at the board edges.
            // One representative tile per direction is enough; each click
            // triggers a global push independent of the caster's position.
            targets.extend_from_slice(&SUPPORT_WIND_TARGETS);
        }
        WeaponType::GlobalUnitEffect => {
            // Support_Missiles is ZONE_ALL, but Lua GetTargetArea still
            // requires clicking one live affected unit. For FriendlyFire
            // variants (Detritus Contraption), the source tile is explicitly
            // excluded; clicking it silently spends the action with no effect.
            let mut fallback = None;
            for u in &board.units {
                if u.hp <= 0 || (u.x, u.y) == (mx, my) { continue; }
                if u.is_enemy() {
                    targets.push((u.x, u.y));
                    return targets;
                }
                if wdef.targets_allies() && fallback.is_none() {
                    fallback = Some((u.x, u.y));
                }
            }
            if let Some(target) = fallback {
                targets.push(target);
            }
        }
        WeaponType::Terraformer => {
            for &(dx, dy) in &DIRS {
                let nx = mx as i8 + dx;
                let ny = my as i8 + dy;
                if in_bounds(nx, ny) {
                    targets.push((nx as u8, ny as u8));
                }
            }
        }
        WeaponType::Disposal => {
            // Grenade_Base artillery can target any board tile except the
            // firing tile. The custom effect handles buildings/terrain/units.
            for x in 0..8u8 {
                for y in 0..8u8 {
                    if (x, y) == (mx, my) { continue; }
                    let dist = (x as i8 - mx as i8).unsigned_abs()
                        + (y as i8 - my as i8).unsigned_abs();
                    if dist >= wdef.range_min && (wdef.range_max == 0 || dist <= wdef.range_max) {
                        targets.push((x, y));
                    }
                }
            }
        }
        _ => {} // Passive, Deploy, TwoClick
    }

    targets
}

fn prime_leap_blocked_by_web(board: &Board, mx: u8, my: u8, weapon_id: WId) -> bool {
    if weapon_id != WId::PrimeLeap {
        return false;
    }
    match board.unit_at(mx, my) {
        Some(idx) => board.units[idx].web(),
        None => false,
    }
}

// ── Action enumeration ───────────────────────────────────────────────────────

type Action = ((u8, u8), WId, (u8, u8), Option<(u8, u8)>); // (move_to, weapon, target, target2)

fn control_shot_target_range(_wdef: &WeaponDef) -> u8 {
    1
}

fn control_shot_move_budget(wdef: &WeaponDef) -> u8 {
    wdef.range_max.max(2)
}

fn control_shot_eligible_unit(unit: &Unit) -> bool {
    unit.alive() && unit.is_enemy() && !unit.is_extra_tile() && !unit.frozen() && unit.move_speed > 0
}

fn control_shot_target_in_line(source: (u8, u8), first: (u8, u8)) -> bool {
    source.0 == first.0 || source.1 == first.1
}

fn control_shot_has_clear_projectile_line(
    board: &Board,
    source: (u8, u8),
    first: (u8, u8),
) -> bool {
    let dx = (first.0 as i8 - source.0 as i8).signum();
    let dy = (first.1 as i8 - source.1 as i8).signum();
    matches!(
        first_projectile_blocker_from(board, source.0 as i8, source.1 as i8, dx, dy),
        Some(blocker) if blocker == first
    )
}

fn enumerate_control_shot_targets(
    board: &Board,
    source: (u8, u8),
    target_range: u8,
    move_budget: u8,
) -> Vec<((u8, u8), (u8, u8))> {
    let mut out = Vec::with_capacity(96);
    for idx in 0..board.unit_count as usize {
        let unit = &board.units[idx];
        if !control_shot_eligible_unit(unit) {
            continue;
        }
        let first = (unit.x, unit.y);
        if first == source {
            continue;
        }
        if !control_shot_target_in_line(source, first) {
            continue;
        }
        if !control_shot_has_clear_projectile_line(board, source, first) {
            continue;
        }
        let target_distance = (first.0 as i8 - source.0 as i8).unsigned_abs()
            + (first.1 as i8 - source.1 as i8).unsigned_abs();
        if target_distance > target_range {
            continue;
        }
        for dest in controlled_reachable_tiles(board, idx, move_budget) {
            if dest != first {
                out.push((first, dest));
            }
        }
    }
    out
}

fn post_move_board_for_attack(board: &Board, mech_idx: usize, move_to: (u8, u8)) -> Option<Board> {
    let unit = &board.units[mech_idx];
    if move_to == (unit.x, unit.y) || board.teleport_partner(move_to.0, move_to.1).is_none() {
        return None;
    }

    let mut b = board.clone();
    simulate_move(&mut b, mech_idx, move_to);
    Some(b)
}

fn attack_origin_after_move(board: &Board, mech_idx: usize, move_to: (u8, u8)) -> (u8, u8) {
    let unit = &board.units[mech_idx];
    if move_to != (unit.x, unit.y) {
        if let Some(partner) = board.teleport_partner(move_to.0, move_to.1) {
            return partner;
        }
    }
    move_to
}

fn force_swap_eligible(board: &Board, unit_idx: usize) -> bool {
    let unit = &board.units[unit_idx];
    unit.alive() && (unit.pushable() || unit.is_mech())
}

fn enumerate_force_swap_targets(board: &Board, sx: u8, sy: u8) -> Vec<((u8, u8), (u8, u8))> {
    let mut out = Vec::new();
    for &(dx, dy) in &DIRS {
        let fx = sx as i8 + dx;
        let fy = sy as i8 + dy;
        if !in_bounds(fx, fy) {
            continue;
        }
        let first = (fx as u8, fy as u8);
        let Some(first_idx) = board.unit_at(first.0, first.1) else {
            continue;
        };
        if !force_swap_eligible(board, first_idx) {
            continue;
        }
        for i in 0..board.unit_count as usize {
            if i == first_idx || !force_swap_eligible(board, i) {
                continue;
            }
            let u = &board.units[i];
            if (u.x, u.y) == (sx, sy) {
                continue;
            }
            out.push((first, (u.x, u.y)));
        }
    }
    out
}

fn solver_projectile_blocker_at(board: &Board, x: u8, y: u8) -> bool {
    let tile = board.tile(x, y);
    tile.terrain == Terrain::Mountain || tile.is_building() || board.unit_at(x, y).is_some()
}

fn first_projectile_blocker_from(
    board: &Board,
    sx: i8,
    sy: i8,
    dx: i8,
    dy: i8,
) -> Option<(u8, u8)> {
    for i in 1..8i8 {
        let nx = sx + dx * i;
        let ny = sy + dy * i;
        if !in_bounds(nx, ny) {
            break;
        }
        let x = nx as u8;
        let y = ny as u8;
        if solver_projectile_blocker_at(board, x, y) {
            return Some((x, y));
        }
    }
    None
}

fn enumerate_ricochet_targets(board: &Board, sx: u8, sy: u8) -> Vec<((u8, u8), (u8, u8))> {
    let mut out = Vec::new();
    for (dir, &(dx, dy)) in DIRS.iter().enumerate() {
        let Some(first) = first_projectile_blocker_from(
            board,
            sx as i8,
            sy as i8,
            dx,
            dy,
        ) else {
            continue;
        };
        if board.tile(first.0, first.1).is_building()
            && board.unit_at(first.0, first.1).is_none()
        {
            continue;
        }
        for side in [(dir + 1) % 4, (dir + 3) % 4] {
            let (sdx, sdy) = DIRS[side];
            let mut fallback = None;
            for i in 1..8i8 {
                let tx = first.0 as i8 + sdx * i;
                let ty = first.1 as i8 + sdy * i;
                if !in_bounds(tx, ty) {
                    break;
                }
                let second = (tx as u8, ty as u8);
                if fallback.is_none() {
                    fallback = Some(second);
                }
                if solver_projectile_blocker_at(board, second.0, second.1) {
                    out.push((first, second));
                    fallback = None;
                    break;
                }
            }
            if let Some(second) = fallback {
                out.push((first, second));
            }
        }
    }
    out
}

fn enumerate_deploy_bomb_line_targets(
    board: &Board,
    sx: u8,
    sy: u8,
    dir: usize,
    wdef: &WeaponDef,
) -> Vec<(u8, u8)> {
    let mut out = Vec::new();
    let min_r = wdef.range_min.max(1);
    let max_r = if wdef.range_max == 0 { 8 } else { wdef.range_max };
    let (dx, dy) = DIRS[dir];
    for dist in (min_r as i8)..=(max_r as i8) {
        let nx = sx as i8 + dx * dist;
        let ny = sy as i8 + dy * dist;
        if !in_bounds(nx, ny) {
            break;
        }
        let target = (nx as u8, ny as u8);
        if !board.is_blocked(target.0, target.1, false) {
            out.push(target);
        }
    }
    out
}

fn enumerate_deploy_bomb_two_click_targets(
    board: &Board,
    sx: u8,
    sy: u8,
    wdef: &WeaponDef,
) -> Vec<((u8, u8), (u8, u8))> {
    let mut out = Vec::new();
    for (first_dir, _vec) in DIRS.iter().enumerate() {
        let first_targets = enumerate_deploy_bomb_line_targets(board, sx, sy, first_dir, wdef);
        if first_targets.is_empty() {
            continue;
        }
        let mut second_targets = Vec::new();
        for offset in 1..=3 {
            let second_dir = (first_dir + offset) % DIRS.len();
            second_targets.extend(enumerate_deploy_bomb_line_targets(
                board, sx, sy, second_dir, wdef,
            ));
        }
        for first in &first_targets {
            for second in &second_targets {
                out.push((*first, *second));
            }
        }
    }
    out
}

fn weapon_can_damage_terrain(weapon_id: WId, wdef: &WeaponDef) -> bool {
    if weapon_id == WId::None || weapon_id == WId::Repair {
        return false;
    }
    wdef.damage > 0 || wdef.damage_outer > 0 || wdef.fire()
}

fn tile_weapon_terrain_effect(tile: &Tile, weapon_id: WId, wdef: &WeaponDef) -> bool {
    if !weapon_can_damage_terrain(weapon_id, wdef) {
        return false;
    }
    match tile.terrain {
        Terrain::Mountain => tile.building_hp > 0,
        Terrain::Ice => true,
        Terrain::Ground => tile.cracked(),
        Terrain::Forest | Terrain::Sand => wdef.fire(),
        _ => false,
    }
}

fn tile_fire_weapon_status_effect(tile: &Tile) -> bool {
    if !matches!(
        tile.terrain,
        Terrain::Ground | Terrain::Sand | Terrain::Forest | Terrain::Rubble
            | Terrain::Building | Terrain::Ice | Terrain::Fire | Terrain::Mountain
    ) {
        return false;
    }
    !tile.on_fire() || tile.smoke() || matches!(tile.terrain, Terrain::Sand | Terrain::Forest)
}

/// Check if a weapon action would have any effect on the board.
/// Returns false when firing at empty space where no unit can be hit or pushed —
/// the solver should prefer move-only/skip in that case. Conservative: returns
/// true when uncertain (e.g., unknown weapon types) to avoid hiding real options.
fn weapon_action_has_effect(
    board: &Board,
    move_to: (u8, u8),
    weapon_id: WId,
    target: (u8, u8),
    weapons: &WeaponTable,
) -> bool {
    if weapon_id == WId::None || weapon_id == WId::Repair {
        return true;
    }
    let wdef = &weapons[weapon_id as usize];
    let (mx, my) = move_to;

    if weapon_id == WId::VipTruckMove {
        return target != (mx, my);
    }

    let unit_at = |x: u8, y: u8| board.unit_at(x, y).is_some();
    let adj_has_unit = |x: u8, y: u8| {
        for &(dx, dy) in &DIRS {
            let ax = x as i8 + dx;
            let ay = y as i8 + dy;
            if in_bounds(ax, ay) && unit_at(ax as u8, ay as u8) { return true; }
        }
        false
    };
    let shieldable_at = |x: u8, y: u8| {
        if let Some(idx) = board.unit_at(x, y) {
            return !board.units[idx].shield();
        }
        let tile = board.tile(x, y);
        tile.is_building() && !tile.shield()
    };

    if is_thermal_discharger(weapon_id) {
        let Some(dir) = cardinal_direction(mx, my, target.0, target.1) else {
            return false;
        };
        let (dx, dy) = DIRS[dir];
        let distance = (target.0 as i8 - mx as i8).unsigned_abs()
            + (target.1 as i8 - my as i8).unsigned_abs();
        if distance == 0 || distance > wdef.range_max.max(1) {
            return false;
        }
        for i in 1..=(distance as i8) {
            let px = mx as i8 + dx * i;
            let py = my as i8 + dy * i;
            if !in_bounds(px, py) { break; }
            let ux = px as u8;
            let uy = py as u8;
            if unit_at(ux, uy)
                || tile_weapon_terrain_effect(board.tile(ux, uy), weapon_id, wdef)
                || (wdef.fire() && tile_fire_weapon_status_effect(board.tile(ux, uy)))
            {
                return true;
            }
            for &side in &[(dir + 1) % 4, (dir + 3) % 4] {
                let (sdx, sdy) = DIRS[side];
                let sx = px + sdx;
                let sy = py + sdy;
                if in_bounds(sx, sy) && unit_at(sx as u8, sy as u8) {
                    return true;
                }
            }
        }
        return false;
    }

    if is_firestorm_generator(weapon_id) {
        let Some(dir) = cardinal_direction(mx, my, target.0, target.1) else {
            return false;
        };
        let distance = (target.0 as i8 - mx as i8).unsigned_abs()
            + (target.1 as i8 - my as i8).unsigned_abs();
        if distance < wdef.range_min || distance > wdef.range_max {
            return false;
        }
        let (dx, dy) = DIRS[dir];
        for i in 1..=(distance as i8) {
            let px = mx as i8 + dx * i;
            let py = my as i8 + dy * i;
            if !in_bounds(px, py) { break; }
            if tile_fire_weapon_status_effect(board.tile(px as u8, py as u8)) {
                return true;
            }
        }
        return unit_at(target.0, target.1);
    }

    match wdef.weapon_type {
        WeaponType::Melee => {
            // For path_size>1 melee (Prime_Spear) any unit in the cardinal
            // line from move_to to target counts as an effect — the spear
            // damages every tile it passes through.
            if unit_at(target.0, target.1) { return true; }
            let target_tile = board.tile(target.0, target.1);
            if tile_weapon_terrain_effect(target_tile, weapon_id, wdef) {
                return true;
            }
            if wdef.chain() && wdef.building_immune() && target_tile.is_building() {
                return true;
            }
            if wdef.path_size > 1 || wdef.range_max > 1 {
                let dx_diff = target.0 as i8 - mx as i8;
                let dy_diff = target.1 as i8 - my as i8;
                if dx_diff == 0 && dy_diff == 0 { return false; }
                let dx = dx_diff.signum();
                let dy = dy_diff.signum();
                let dist = dx_diff.abs().max(dy_diff.abs());
                for i in 1..dist {
                    let px = mx as i8 + dx * i;
                    let py = my as i8 + dy * i;
                    if !in_bounds(px, py) { break; }
                    if unit_at(px as u8, py as u8) { return true; }
                    if tile_weapon_terrain_effect(
                        board.tile(px as u8, py as u8), weapon_id, wdef
                    ) {
                        return true;
                    }
                }
                return false;
            }
            false
        }
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
                if tile_weapon_terrain_effect(tile, weapon_id, wdef) {
                    return true;
                }
                if tile.terrain == Terrain::Mountain || tile.is_building() { break; }
            }
            false
        }
        WeaponType::Artillery => {
            if is_tri_rocket(weapon_id) {
                let Some(dir) = cardinal_direction(mx, my, target.0, target.1) else {
                    return false;
                };
                let (dx, dy) = DIRS[dir];
                for offset in [1i8, 0, -1] {
                    let px = target.0 as i8 + dx * offset;
                    let py = target.1 as i8 + dy * offset;
                    if !in_bounds(px, py) { continue; }
                    let ux = px as u8;
                    let uy = py as u8;
                    if unit_at(ux, uy) {
                        return true;
                    }
                    let tile = board.tile(ux, uy);
                    if tile.terrain == Terrain::Mountain
                        || tile.terrain == Terrain::Ice
                        || (tile.terrain == Terrain::Ground && tile.cracked())
                    {
                        return true;
                    }
                }
                return false;
            }
            let Some(dir) = cardinal_direction(mx, my, target.0, target.1) else {
                return false;
            };
            let distance = (target.0 as i8 - mx as i8).unsigned_abs()
                + (target.1 as i8 - my as i8).unsigned_abs();
            if distance < wdef.range_min.max(1) {
                return false;
            }
            if tile_weapon_terrain_effect(board.tile(target.0, target.1), weapon_id, wdef) {
                return true;
            }
            if wdef.shield() {
                if shieldable_at(target.0, target.1) {
                    return true;
                }
                if wdef.aoe_behind() {
                    let (dx, dy) = DIRS[dir];
                    let bx = target.0 as i8 + dx;
                    let by = target.1 as i8 + dy;
                    if in_bounds(bx, by) && shieldable_at(bx as u8, by as u8) {
                        return true;
                    }
                }
                if wdef.aoe_adjacent() {
                    for &(dx, dy) in &DIRS {
                        let ax = target.0 as i8 + dx;
                        let ay = target.1 as i8 + dy;
                        if in_bounds(ax, ay) && shieldable_at(ax as u8, ay as u8) {
                            return true;
                        }
                    }
                }
            }
            unit_at(target.0, target.1) || adj_has_unit(target.0, target.1)
        },
        WeaponType::TwoClick if is_hydraulic_lifter(weapon_id) => {
            let Some(dir) = cardinal_direction(mx, my, target.0, target.1) else {
                return false;
            };
            let dist = (target.0 as i8 - mx as i8).unsigned_abs()
                + (target.1 as i8 - my as i8).unsigned_abs();
            if dist < 2 {
                return false;
            }
            let (dx, dy) = DIRS[dir];
            let grab_x = mx as i8 + dx;
            let grab_y = my as i8 + dy;
            if !in_bounds(grab_x, grab_y) || board.is_blocked(target.0, target.1, true) {
                return false;
            }
            let Some(unit_idx) = board.unit_at(grab_x as u8, grab_y as u8) else {
                return false;
            };
            let target_unit = &board.units[unit_idx];
            target_unit.pushable() || target_unit.is_mech()
        }
        WeaponType::TwoClick if is_deploy_bomb_two_click(weapon_id) => {
            !board.is_blocked(target.0, target.1, false)
        }
        WeaponType::Deploy => !board.is_blocked(target.0, target.1, false),
        WeaponType::SelfAoe => {
            if is_walking_bomb_trigger(weapon_id) {
                adj_has_unit(mx, my)
            } else {
                unit_at(mx, my) || adj_has_unit(mx, my)
            }
        },
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
        WeaponType::HealAll => {
            // Repair Drop has an effect iff at least one TEAM_PLAYER unit
            // would actually change: hp below max, disabled (hp<=0), or
            // carrying fire/acid/frozen. Otherwise skip so the mech's
            // action isn't wasted on a no-op heal.
            board.units.iter().any(|u| {
                u.team == Team::Player
                    && (u.hp < u.max_hp || u.fire() || u.acid() || u.frozen())
            })
        }
        WeaponType::GlobalPush => {
            // The firing mech itself is a pawn, so a live caster means the
            // action has an effect. Keep this explicit for replay/test boards.
            board.units.iter().any(|u| u.hp > 0)
        }
        WeaponType::GlobalUnitEffect => {
            if wdef.shield() {
                board.units.iter().any(|u| u.hp > 0 && (u.x, u.y) != (mx, my) && !u.shield())
            } else {
                board.units.iter().any(|u| u.hp > 0 && (u.x, u.y) != (mx, my))
            }
        }
        WeaponType::Terraformer => {
            terraformer_sweep_tiles(mx, my, target.0, target.1)
                .map(|tiles| tiles.iter().any(|&(x, y)| {
                    if unit_at(x, y) { return true; }
                    let tile = board.tile(x, y);
                    tile.smoke()
                        || tile.on_fire()
                        || (!matches!(tile.terrain, Terrain::Mountain | Terrain::Sand))
                }))
                .unwrap_or(false)
        }
        WeaponType::Disposal => {
            disposal_cross_tiles(target.0, target.1).iter().any(|&(x, y)| {
                if unit_at(x, y) { return true; }
                let tile = board.tile(x, y);
                tile.terrain == Terrain::Mountain || !tile.acid()
            })
        }
        // Leap/Swap/Deploy/TwoClick: positional or utility — don't filter
        _ => true,
    }
}

fn enumerate_actions(board: &Board, mech_idx: usize, weapons: &WeaponTable) -> Vec<Action> {
    let unit = &board.units[mech_idx];
    let mut actions = Vec::with_capacity(100);

    // Frozen mechs can ONLY repair (to break free). No movement, no attacks.
    if unit.frozen() {
        let pos = (unit.x, unit.y);
        let tile = board.tile(pos.0, pos.1);
        if !tile.smoke() {
            actions.push((pos, WId::Repair, pos, None));
        }
        return actions;
    }

    // Webbed mechs can attack or repair, but their normal move phase is
    // locked until the web source moves/dies or the mech is pushed.
    // MID_ACTION mechs (can_move=false): already moved, only generate
    // attack/repair options from current position.
    let positions = if unit.can_move() && !unit.web() {
        reachable_tiles(board, mech_idx)
    } else {
        vec![(unit.x, unit.y)]
    };

    for &pos in &positions {
        // Move-only / skip — always available so search can stay put.
        // (For MID_ACTION mechs, this is the "skip attack" option.)
        actions.push((pos, WId::None, (255, 255), None));

        // Teleporter pads fire during the move phase. Attack targeting,
        // smoke checks, and effect filtering must therefore use the post-swap
        // board while the emitted move_to remains the pad tile to step onto.
        let post_move_board = post_move_board_for_attack(board, mech_idx, pos);
        let action_board = match &post_move_board {
            Some(b) => b,
            None => board,
        };
        let action_unit = &action_board.units[mech_idx];
        if !action_unit.alive() {
            continue;
        }
        // Normal moves attack from `pos`. Teleporter moves attack from the
        // partner tile after the pad swap, represented by `action_board`.
        let attack_pos = attack_origin_after_move(board, mech_idx, pos);

        // Smoke blocks most pawn actions (attack + repair). These mission
        // pawns have IgnoreSmoke=true in their Lua definitions.
        let tile = action_board.tile(attack_pos.0, attack_pos.1);
        let ignores_smoke = action_unit.type_name_str() == "Trapped_Building"
            || action_unit.type_name_str() == "Disposal_Unit"
            || action_unit.type_name_str() == "Missile_Unit";
        if !tile.smoke() || ignores_smoke {
            // Primary weapon — filter out no-op fires (empty space, nothing affected)
            let w1_id = WId::from_raw(action_unit.weapon.0);
            if w1_id != WId::None {
                let mech_from = (unit.x, unit.y);
                if is_force_swap(w1_id) {
                    for (first, second) in enumerate_force_swap_targets(action_board, attack_pos.0, attack_pos.1) {
                        actions.push((pos, w1_id, first, Some(second)));
                    }
                } else if is_control_shot(w1_id) {
                    let wdef = &weapons[w1_id as usize];
                    let target_range = control_shot_target_range(wdef);
                    let move_budget = control_shot_move_budget(wdef);
                    for (first, second) in
                        enumerate_control_shot_targets(action_board, attack_pos, target_range, move_budget)
                    {
                        actions.push((pos, w1_id, first, Some(second)));
                    }
                } else if is_deploy_bomb_two_click(w1_id) {
                    let wdef = &weapons[w1_id as usize];
                    for (first, second) in
                        enumerate_deploy_bomb_two_click_targets(action_board, attack_pos.0, attack_pos.1, wdef)
                    {
                        actions.push((pos, w1_id, first, Some(second)));
                    }
                } else if is_ricochet_rocket(w1_id) && !action_unit.web() {
                    for (first, second) in enumerate_ricochet_targets(action_board, attack_pos.0, attack_pos.1) {
                        actions.push((pos, w1_id, first, Some(second)));
                    }
                } else {
                    for &target in &get_weapon_targets(action_board, attack_pos.0, attack_pos.1, w1_id, mech_from, weapons) {
                        if weapon_action_has_effect(action_board, attack_pos, w1_id, target, weapons) {
                            actions.push((pos, w1_id, target, None));
                        }
                    }
                }
            }

            // Secondary weapon
            let w2_id = WId::from_raw(action_unit.weapon2.0);
            if w2_id != WId::None {
                if is_force_swap(w2_id) {
                    for (first, second) in enumerate_force_swap_targets(action_board, attack_pos.0, attack_pos.1) {
                        actions.push((pos, w2_id, first, Some(second)));
                    }
                } else if is_control_shot(w2_id) {
                    let wdef = &weapons[w2_id as usize];
                    let target_range = control_shot_target_range(wdef);
                    let move_budget = control_shot_move_budget(wdef);
                    for (first, second) in
                        enumerate_control_shot_targets(action_board, attack_pos, target_range, move_budget)
                    {
                        actions.push((pos, w2_id, first, Some(second)));
                    }
                } else if is_deploy_bomb_two_click(w2_id) {
                    let wdef = &weapons[w2_id as usize];
                    for (first, second) in
                        enumerate_deploy_bomb_two_click_targets(action_board, attack_pos.0, attack_pos.1, wdef)
                    {
                        actions.push((pos, w2_id, first, Some(second)));
                    }
                } else if is_ricochet_rocket(w2_id) && !action_unit.web() {
                    for (first, second) in enumerate_ricochet_targets(action_board, attack_pos.0, attack_pos.1) {
                        actions.push((pos, w2_id, first, Some(second)));
                    }
                } else {
                    for &target in &get_weapon_targets(action_board, attack_pos.0, attack_pos.1, w2_id, (unit.x, unit.y), weapons) {
                        if weapon_action_has_effect(action_board, attack_pos, w2_id, target, weapons) {
                            actions.push((pos, w2_id, target, None));
                        }
                    }
                }
            }

            // Repair (if damaged/on_fire/acid/frozen/infected)
            if action_unit.hp < action_unit.max_hp
                || action_unit.fire()
                || action_unit.acid()
                || action_unit.frozen()
                || action_unit.infected()
            {
                actions.push((pos, WId::Repair, attack_pos, None));
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

fn is_aerial_bombs(weapon_id: WId) -> bool {
    matches!(
        weapon_id,
        WId::BruteJetmech
            | WId::BruteJetmechA
            | WId::BruteJetmechB
            | WId::BruteJetmechAB
    )
}

fn aerial_bombs_transit_smoke_score(
    board: &Board,
    origin: (u8, u8),
    target: (u8, u8),
    weapon_id: WId,
    wdef: &WeaponDef,
) -> i32 {
    if !is_aerial_bombs(weapon_id) || !wdef.smoke() {
        return 0;
    }
    let Some(dir) = cardinal_direction(origin.0, origin.1, target.0, target.1) else {
        return 0;
    };
    let (dx, dy) = DIRS[dir];
    let mut x = origin.0 as i8 + dx;
    let mut y = origin.1 as i8 + dy;
    let target_i = (target.0 as i8, target.1 as i8);
    let mut score = 0;

    while in_bounds(x, y) && (x, y) != target_i {
        let ux = x as u8;
        let uy = y as u8;
        if let Some(idx) = board.unit_at(ux, uy) {
            let u = &board.units[idx];
            if u.is_enemy()
                && u.alive()
                && u.queued_target_x >= 0
                && !u.frozen()
                && !board.tile(ux, uy).smoke()
            {
                score += if u.queued_target_x < 8 && u.queued_target_y >= 0 && u.queued_target_y < 8 {
                    let target_tile = board.tile(u.queued_target_x as u8, u.queued_target_y as u8);
                    if target_tile.is_building() { 420 } else { 180 }
                } else if u.has_queued_attack() {
                    180
                } else {
                    0
                };
            }
        }
        x += dx;
        y += dy;
    }

    score
}

fn charge_first_hit(
    board: &Board,
    origin: (u8, u8),
    target: (u8, u8),
    weapon_id: WId,
    wdef: &WeaponDef,
) -> Option<((u8, u8), u8, Option<usize>)> {
    let dir = cardinal_direction(origin.0, origin.1, target.0, target.1)?;
    let (dx, dy) = DIRS[dir];
    for i in 1..8i8 {
        let px = origin.0 as i8 + dx * i;
        let py = origin.1 as i8 + dy * i;
        if !in_bounds(px, py) { break; }
        let x = px as u8;
        let y = py as u8;
        let tile = board.tile(x, y);
        if tile.terrain == Terrain::Mountain { break; }
        if tile.is_building() { return Some(((x, y), i as u8, None)); }
        if charge_terrain_blocks(weapon_id, wdef, tile.terrain) { break; }
        if let Some(idx) = board.unit_at(x, y) {
            return Some(((x, y), i as u8, Some(idx)));
        }
    }
    None
}

fn charge_terrain_blocks(weapon_id: WId, wdef: &WeaponDef, terrain: Terrain) -> bool {
    if wdef.flying_charge() {
        return false;
    }
    if matches!(weapon_id, WId::PrimePunchmechA | WId::PrimePunchmechAB) {
        return terrain == Terrain::Chasm;
    }
    terrain.is_deadly_ground()
}

fn direct_weapon_damage_would_kill(unit: &Unit, wdef: &WeaponDef) -> bool {
    if unit.shield() || unit.frozen() {
        return false;
    }
    let mut damage = wdef.damage as i8;
    if unit.armor() && damage > 0 {
        damage -= 1;
    }
    if unit.acid() {
        damage *= 2;
    }
    damage >= unit.hp
}

fn mission_mountain_tile_score(board: &Board, x: u8, y: u8) -> i32 {
    if board.mission_mountain_target == 0 {
        return 0;
    }
    let tile = board.tile(x, y);
    if tile.terrain != Terrain::Mountain || tile.building_hp == 0 {
        return 0;
    }
    if tile.building_hp == 1 { 900 } else { 220 }
}

fn first_projectile_terrain_effect_score(
    board: &Board,
    origin: (u8, u8),
    target: (u8, u8),
    weapon_id: WId,
    wdef: &WeaponDef,
) -> i32 {
    let dx = (target.0 as i8 - origin.0 as i8).signum();
    let dy = (target.1 as i8 - origin.1 as i8).signum();
    if dx == 0 && dy == 0 {
        return 0;
    }
    for i in 1..8i8 {
        let px = origin.0 as i8 + dx * i;
        let py = origin.1 as i8 + dy * i;
        if !in_bounds(px, py) { break; }
        let ux = px as u8;
        let uy = py as u8;
        if board.unit_at(ux, uy).is_some() {
            return 0;
        }
        let tile = board.tile(ux, uy);
        if tile_weapon_terrain_effect(tile, weapon_id, wdef) {
            return mission_mountain_tile_score(board, ux, uy);
        }
        if tile.terrain == Terrain::Mountain || tile.is_building() {
            break;
        }
    }
    0
}

fn mission_mountain_action_score(
    board: &Board,
    origin: (u8, u8),
    weapon_id: WId,
    target: (u8, u8),
    weapons: &WeaponTable,
) -> i32 {
    if board.mission_mountain_target == 0
        || weapon_id == WId::None
        || weapon_id == WId::Repair
        || target.0 >= 8
    {
        return 0;
    }
    let wdef = &weapons[weapon_id as usize];
    match wdef.weapon_type {
        WeaponType::Projectile | WeaponType::Laser | WeaponType::Pull => {
            first_projectile_terrain_effect_score(board, origin, target, weapon_id, wdef)
        }
        WeaponType::Melee | WeaponType::Artillery => {
            if tile_weapon_terrain_effect(board.tile(target.0, target.1), weapon_id, wdef) {
                mission_mountain_tile_score(board, target.0, target.1)
            } else {
                0
            }
        }
        WeaponType::SelfAoe => {
            if target != origin {
                return 0;
            }
            DIRS.iter().map(|&(dx, dy)| {
                let x = origin.0 as i8 + dx;
                let y = origin.1 as i8 + dy;
                if in_bounds(x, y) {
                    mission_mountain_tile_score(board, x as u8, y as u8)
                } else {
                    0
                }
            }).sum()
        }
        WeaponType::Leap => {
            if !wdef.aoe_adjacent() {
                return 0;
            }
            DIRS.iter().map(|&(dx, dy)| {
                let x = target.0 as i8 + dx;
                let y = target.1 as i8 + dy;
                if in_bounds(x, y) {
                    mission_mountain_tile_score(board, x as u8, y as u8)
                } else {
                    0
                }
            }).sum()
        }
        _ => 0,
    }
}

fn prune_actions(
    board: &Board,
    mech_idx: usize,
    actions: &mut Vec<Action>,
    threat_tiles: u64,       // bitset
    building_threats: u64,   // bitset
    spawn_bits: u64,         // bitset of spawn tiles
    max_n: usize,
    weapons: &WeaponTable,
) {
    if actions.len() <= max_n { return; }

    // Score each action by heuristic
    let mut scored: Vec<(i32, usize)> = actions.iter().enumerate().map(|(i, &(move_to, weapon_id, target, target2))| {
        let mut s = 0i32;
        let attack_origin = attack_origin_after_move(board, mech_idx, move_to);

        let move_bit = 1u64 << xy_to_idx(attack_origin.0, attack_origin.1);

        // Body-blocking a building threat
        if building_threats & move_bit != 0 { s += 200; }

        // Attacking near threats
        if weapon_id != WId::None && weapon_id != WId::Repair && target.0 < 8 {
            let target_bit = 1u64 << xy_to_idx(target.0, target.1);
            if threat_tiles & target_bit != 0 { s += 100; }
            if let Some((tx2, ty2)) = target2 {
                let target2_bit = 1u64 << xy_to_idx(tx2, ty2);
                if threat_tiles & target2_bit != 0 { s += 100; }
            }

            // Check if target has a unit (prefer attacking units over empty)
            if board.unit_at(target.0, target.1).is_some() { s += 10; }
            // Friendly fire penalty
            if let Some(idx) = board.unit_at(target.0, target.1) {
                if board.units[idx].is_player() { s -= 300; }
            }

            // BUILDING DAMAGE PENALTY: penalize actions that push units into buildings.
            // When a push is blocked by a building, both the unit and building take
            // 1 bump damage — losing grid power. Apply -300 per building at risk.
            let wdef = &weapons[weapon_id as usize];
            if is_arachnoid_injector(weapon_id) {
                if let Some(idx) = board.unit_at(target.0, target.1) {
                    let target_unit = &board.units[idx];
                    if target_unit.is_enemy() && direct_weapon_damage_would_kill(target_unit, wdef) {
                        s += 2500;
                    }
                }
            }
            s += mission_mountain_action_score(
                board,
                attack_origin,
                weapon_id,
                target,
                weapons,
            );
            s += aerial_bombs_transit_smoke_score(
                board,
                attack_origin,
                target,
                weapon_id,
                wdef,
            );
            if is_reverse_thrusters(weapon_id) {
                if let Some((hx, hy, distance, _dir)) = reverse_thrusters_hit_tile(
                    attack_origin.0,
                    attack_origin.1,
                    target.0,
                    target.1,
                ) {
                    let hit_bit = 1u64 << xy_to_idx(hx, hy);
                    if threat_tiles & hit_bit != 0 { s += 100; }
                    if let Some(idx) = board.unit_at(hx, hy) {
                        if board.units[idx].is_enemy() {
                            s += 40;
                            let base = distance.saturating_add(wdef.damage);
                            let effective = if board.units[idx].acid() {
                                base.saturating_mul(2)
                            } else if board.units[idx].armor() {
                                base.saturating_sub(1)
                            } else {
                                base
                            };
                            if effective >= 4 {
                                s += 2000;
                            }
                        } else if board.units[idx].is_player() {
                            s -= 300;
                        }
                    }
                }
            }
            if wdef.push != PushDir::None {
                match wdef.weapon_type {
                    // Melee / Projectile / Charge / Laser: Forward push on the hit target
                    WeaponType::Melee | WeaponType::Projectile | WeaponType::Charge | WeaponType::Laser => {
                        if wdef.push == PushDir::Forward || wdef.push == PushDir::Backward || wdef.push == PushDir::Flip {
                            if let Some(dir) = direction_between(attack_origin.0, attack_origin.1, target.0, target.1) {
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
                            if let Some(dir) = direction_between(attack_origin.0, attack_origin.1, target.0, target.1) {
                                if push_hits_building(target.0, target.1, dir, board) {
                                    s -= 300;
                                }
                            }
                        }
                        // Also check AoE perpendicular tiles (e.g., Janus Cannon)
                        if wdef.aoe_perpendicular() {
                            if let Some(dir) = direction_between(attack_origin.0, attack_origin.1, target.0, target.1) {
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
                        if let Some(dir) = direction_between(attack_origin.0, attack_origin.1, target.0, target.1) {
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
                        // attack_origin is the mech position after any pad swap;
                        // adjacent tiles get pushed outward.
                        for (d, &(dx, dy)) in DIRS.iter().enumerate() {
                            let nx = attack_origin.0 as i8 + dx;
                            let ny = attack_origin.1 as i8 + dy;
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
                    // Global push (Wind Torrent): every pawn moves one tile
                    // in the selected direction, so pre-penalize any pawn that
                    // would bump a building. Full projection still owns exact
                    // scoring; this just keeps pruning from liking grid-risky
                    // candidates too much.
                    WeaponType::GlobalPush => {
                        if let Some(push_d) = support_wind_dir_from_target(target.0, target.1) {
                            for u in board.units.iter().filter(|u| u.hp > 0) {
                                if push_hits_building(u.x, u.y, push_d, board) {
                                    s -= 300;
                                }
                            }
                        }
                    }
                    _ => {}
                }
            }

            if wdef.weapon_type == WeaponType::Charge {
                if let Some((_hit, distance, Some(idx))) =
                    charge_first_hit(board, attack_origin, target, weapon_id, wdef)
                {
                    let hit_unit = &board.units[idx];
                    if hit_unit.is_enemy() {
                        s += 10;
                        if matches!(
                            weapon_id,
                            WId::PrimePunchmechA | WId::PrimePunchmechAB
                        ) && distance >= 5
                        {
                            s += if direct_weapon_damage_would_kill(hit_unit, wdef) {
                                900
                            } else {
                                120
                            };
                        }
                    } else if hit_unit.is_player() {
                        s -= 300;
                    }
                }
            }
        }

        // Mech blocks a spawn tile by standing on it
        if spawn_bits & move_bit != 0 { s += 80; }

        // Push enemy onto a spawn tile
        if spawn_bits != 0 && weapon_id != WId::None && weapon_id != WId::Repair && target.0 < 8 {
            if let Some(enemy_idx) = board.unit_at(target.0, target.1) {
                if board.units[enemy_idx].is_enemy() {
                    if let Some(dir) = direction_between(attack_origin.0, attack_origin.1, target.0, target.1) {
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

    // Score descending; on tie, preserve enumeration order by original
    // index ascending. Without the tiebreak, equal-score actions could
    // flip between runs on an unstable sort — at depth 5 that's the
    // kind of nondeterminism that compounds into inconsistent beam
    // survivors and unreproducible failures.
    scored.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
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
    mission_kills_so_far: i32,
    unit_deaths_so_far: i32,
    bumps_so_far: i32,
    nanobots_heal_so_far: i32,
    powered_blast_so_far: i32,
    reverse_thrusters_four_damage_so_far: i32,
    feed_the_flame_so_far: i32,
    arachnoid_spawns_so_far: i32,
    lets_walk_control_distance_so_far: i32,
    core_of_the_earth_so_far: i32,
    stay_with_me_heal_so_far: i32,
    pods_collected_so_far: i32,
    soft_disable_penalty_so_far: f64,
    threat_tiles: u64,
    building_threats: u64,
    spawn_bits: u64,
    original_positions: &[(u8, u8); 16],
    spawn_points: &[(u8, u8)],
    max_actions: usize,
    weights: &EvalWeights,
    deadline: Instant,
    disabled_mask: DisabledMask,
    allow_disabled_weapons: bool,
    weapons: &WeaponTable,
    best_score: &mut f64,
    best_actions: &mut Vec<MechAction>,
    best_clean_score: &mut f64,
    best_clean_actions: &mut Vec<MechAction>,
    initial_building_count: i32,
    psion_before: &PsionState,
    top_k_out: &mut Option<BoundedTopK>,
) {
    if Instant::now() > deadline { return; }

    if depth >= mech_order.len() {
        // All mechs acted — snapshot buildings before enemy phase
        let mut b_eval = board.clone();
        let buildings_before_enemy = count_buildings(&b_eval);
        let before_enemy_phase = b_eval.clone();
        let enemy_phase_result = simulate_enemy_attacks(&mut b_eval, original_positions, weapons);
        let enemy_phase_unit_deaths = count_unit_deaths_between(&before_enemy_phase, &b_eval);
        let before_spawn_block = b_eval.clone();
        let spawn_block_result = apply_spawn_blocking(&mut b_eval, spawn_points);
        let spawn_block_unit_deaths = count_unit_deaths_between(&before_spawn_block, &b_eval);
        let projected_kills = kills_so_far
            + enemy_phase_result.enemies_killed
            + spawn_block_result.enemies_killed;
        let projected_mission_kills = mission_kills_so_far
            + enemy_phase_result.mission_kills
            + spawn_block_result.mission_kills;
        let projected_unit_deaths = unit_deaths_so_far
            + enemy_phase_unit_deaths
            + spawn_block_unit_deaths;
        let raw = evaluate(
            &b_eval, spawn_points, weights,
            projected_kills, projected_mission_kills,
            bumps_so_far, psion_before, building_threats,
        ) + consumed_spawn_block_bonus(&b_eval, spawn_points, weights, spawn_block_result.spawns_blocked);
        // Tier 2 soft-disable bias: penalize any candidate plan that
        // relies on a weapon in the session's disabled_actions list.
        // Subtracted at terminal evaluation so the search retains its
        // normal comparisons between branches — we're biasing the
        // objective, not pruning branches.
        //
        // Scale by `bld_mult` (same factor used for building scoring in
        // `evaluate`) when in forced-use mode (Pass 2). At low grid the
        // value of saving a building drops to bld_mult * building_alive
        // (~6,000 at grid=0, bld_mult=0.6), and a flat 10,000 penalty
        // would exceed it — flipping the choice back to pure-move and
        // throwing the mission. Scaling preserves the documented
        // invariant: "won't throw the mission for a single forced use."
        // Pass 1 (`allow_disabled_weapons=false`) never reaches this
        // path with non-zero penalty (disabled branches are pruned at
        // enumeration), so the scaling is a no-op there.
        let penalty_scale = if allow_disabled_weapons {
            let eff_grid_eval = b_eval.grid_power as f64
                + b_eval.enemy_grid_save_expected as f64
                + b_eval.player_grid_save_expected as f64;
            let grid_health_eval = eff_grid_eval / (b_eval.grid_power_max as f64).max(1.0);
            (weights.bld_grid_floor + weights.bld_grid_scale * grid_health_eval).max(0.1)
        } else {
            1.0
        };
        let mission_action_bonus = mission_missiles_action_bonus(&b_eval, actions_so_far);
        let nanobots_heal_bonus =
            nanobots_heal_so_far as f64 * weights.viscera_nanobots_heal_bonus;
        let powered_blast_bonus =
            powered_blast_so_far as f64 * weights.powered_blast_bonus;
        let reverse_thrusters_four_damage_bonus =
            reverse_thrusters_four_damage_so_far as f64
                * weights.reverse_thrusters_four_damage_bonus;
        let feed_the_flame_bonus =
            feed_the_flame_so_far as f64 * weights.feed_the_flame_bonus;
        let arachnoid_spawn_bonus =
            arachnoid_spawns_so_far as f64 * weights.arachnoid_spawn_bonus;
        let lets_walk_control_distance_bonus =
            lets_walk_control_distance_so_far as f64 * weights.lets_walk_control_distance_bonus;
        let core_of_the_earth_bonus =
            core_of_the_earth_so_far as f64 * weights.core_of_the_earth_bonus;
        let stay_with_me_heal_bonus =
            stay_with_me_heal_so_far as f64 * weights.stay_with_me_heal_bonus;
        let no_survivors_bonus = if projected_unit_deaths >= 7 {
            projected_unit_deaths as f64 * weights.no_survivors_death_bonus
        } else {
            0.0
        };
        let pod_collected_penalty =
            pods_collected_so_far as f64 * weights.pod_collected;
        let score = raw
            + mission_action_bonus
            + nanobots_heal_bonus
            + powered_blast_bonus
            + reverse_thrusters_four_damage_bonus
            + feed_the_flame_bonus
            + arachnoid_spawn_bonus
            + lets_walk_control_distance_bonus
            + core_of_the_earth_bonus
            + stay_with_me_heal_bonus
            + no_survivors_bonus
            + pod_collected_penalty
            - soft_disable_penalty_so_far * penalty_scale;


        if score > *best_score {
            *best_score = score;
            *best_actions = actions_so_far.clone();
        }
        let mech_buildings_lost = initial_building_count - buildings_before_enemy;
        if mech_buildings_lost == 0 && score > *best_clean_score {
            *best_clean_score = score;
            *best_clean_actions = actions_so_far.clone();
        }
        if let Some(top_k) = top_k_out.as_mut() {
            top_k.offer(score, actions_so_far.as_slice());
        }
        return;
    }

    let mech_idx = mech_order[depth];

    // Skip dead mechs (killed by a previous action in this permutation)
    if !board.units[mech_idx].alive() {
        // Still recurse to the next depth so the remaining mechs can act
        search_recursive(
            board, mech_order, depth + 1,
            actions_so_far, kills_so_far, mission_kills_so_far,
            unit_deaths_so_far, bumps_so_far,
            nanobots_heal_so_far, powered_blast_so_far,
            reverse_thrusters_four_damage_so_far,
            feed_the_flame_so_far,
            arachnoid_spawns_so_far,
            lets_walk_control_distance_so_far,
            core_of_the_earth_so_far,
            stay_with_me_heal_so_far,
            pods_collected_so_far, soft_disable_penalty_so_far,
            threat_tiles, building_threats, spawn_bits,
            original_positions,
            spawn_points, max_actions, weights, deadline,
            disabled_mask,
            allow_disabled_weapons,
            weapons,
            best_score, best_actions,
            best_clean_score, best_clean_actions, initial_building_count,
            psion_before,
            top_k_out,
        );
        return;
    }

    let mut actions = enumerate_actions(board, mech_idx, weapons);
    prune_actions(board, mech_idx, &mut actions, threat_tiles, building_threats, spawn_bits, max_actions, weapons);

    for &(move_to, weapon_id, target, target2) in &actions {
        if Instant::now() > deadline { return; }

        // Soft-disable: a weapon in the session's disabled_actions mask has
        // already desynced N times — its damage prediction is untrusted, so
        // planning around it is a gamble. Two-pass search in `solve_turn`:
        //
        //   Pass 1 (`allow_disabled_weapons=false`): drop disabled-weapon
        //     branches entirely. This is the default — when alternatives
        //     exist, the solver picks a reliable plan. (Previously the
        //     ONLY behavior; comment cited run 20260428_165811_685 where
        //     a flat penalty was overridden by a 23k kill bonus and the
        //     solver fired Ranged_Defensestrike anyway, then mech died.)
        //
        //   Pass 2 (`allow_disabled_weapons=true`): admit disabled-weapon
        //     branches with `soft_disabled_penalty` accrued at terminal
        //     evaluation. Run only when Pass 1 returned an empty/no-attack
        //     plan AND the predicted outcome is critical (grid will drop
        //     near 0). This is the "forced use" path — better to gamble
        //     on a buggy weapon than concede the mission. Observed on
        //     run 20260428_165811_685 turn 3 (Mission_Volatile): both
        //     squad attack weapons were soft-disabled; Pass 1 produced a
        //     pure-move plan that lost the run (grid 1→0, 4 buildings
        //     destroyed); the Pass 2 plan would have saved 1 building by
        //     firing Attract Shot at the building-threatening Scorpion.
        //
        let is_disabled = disabled_mask_contains(disabled_mask, weapon_id);
        if is_disabled && !allow_disabled_weapons {
            continue;
        }

        let mut b_next = board.clone(); // ~800 byte memcpy
        let result = simulate_action_with_target2(
            &mut b_next,
            mech_idx,
            move_to,
            weapon_id,
            target,
            target2,
            weapons,
        );
        let unit_deaths_add = count_unit_deaths_between(board, &b_next);
        let nanobots_heal_add = viscera_nanobots_heal_from_events(&result.events);
        let powered_blast_add = powered_blast_from_events(&result.events);
        let reverse_thrusters_four_damage_add =
            reverse_thrusters_four_damage_from_events(&result.events);
        let feed_the_flame_add = feed_the_flame_from_events(&result.events);
        let arachnoid_spawns_add = arachnoid_spawns_from_events(&result.events);
        let lets_walk_control_distance_add = lets_walk_control_distance_from_events(&result.events);
        let core_of_the_earth_add = core_of_the_earth_chasm_falls_from_events(&result.events);
        let stay_with_me_heal_add = result.mech_hp_repaired;

        // Accrue the soft-disable penalty per disabled-weapon use along the
        // branch. Pass 1 (`allow_disabled_weapons=false`) never reaches
        // here for disabled weapons (the `continue` above drops them), so
        // accrual is a no-op. Pass 2 (`allow_disabled_weapons=true`)
        // reaches here for disabled-weapon branches and accumulates the
        // penalty — paid once at terminal evaluation, scaled by `bld_mult`
        // so the cost stays proportional to building value at low grid.
        let penalty_add: f64 = if is_disabled {
            weights.soft_disabled_penalty
        } else {
            0.0
        };

        let action = make_action(&board.units[mech_idx], move_to, weapon_id, target, target2);
        actions_so_far.push(action);

        search_recursive(
            &b_next, mech_order, depth + 1,
            actions_so_far,
            kills_so_far + result.enemies_killed,
            mission_kills_so_far + result.mission_kills,
            unit_deaths_so_far + unit_deaths_add,
            bumps_so_far + result.buildings_bump_damaged,
            nanobots_heal_so_far + nanobots_heal_add,
            powered_blast_so_far + powered_blast_add,
            reverse_thrusters_four_damage_so_far + reverse_thrusters_four_damage_add,
            feed_the_flame_so_far + feed_the_flame_add,
            arachnoid_spawns_so_far + arachnoid_spawns_add,
            lets_walk_control_distance_so_far + lets_walk_control_distance_add,
            core_of_the_earth_so_far + core_of_the_earth_add,
            stay_with_me_heal_so_far + stay_with_me_heal_add,
            pods_collected_so_far + result.pods_collected,
            soft_disable_penalty_so_far + penalty_add,
            threat_tiles, building_threats, spawn_bits,
            original_positions,
            spawn_points, max_actions, weights, deadline,
            disabled_mask,
            allow_disabled_weapons,
            weapons,
            best_score, best_actions,
            best_clean_score, best_clean_actions, initial_building_count,
            psion_before,
            top_k_out,
        );

        actions_so_far.pop();
    }
}

fn make_action(
    unit: &Unit,
    move_to: (u8, u8),
    weapon_id: WId,
    target: (u8, u8),
    target2: Option<(u8, u8)>,
) -> MechAction {
    let name = unit.type_name_str();
    let mut desc = name.to_string();
    if move_to != (unit.x, unit.y) {
        desc += &format!(", move {}\u{2192}{}",
            bridge_to_visual(unit.x, unit.y),
            bridge_to_visual(move_to.0, move_to.1));
    }
    if weapon_id == WId::Repair {
        desc += ", repair";
    } else if weapon_id == WId::VipTruckMove {
        desc += &format!(", drive {}→{}",
            bridge_to_visual(unit.x, unit.y),
            bridge_to_visual(target.0, target.1));
    } else if weapon_id != WId::None {
        desc += &format!(", fire {} at {}",
            weapon_name(weapon_id),
            bridge_to_visual(target.0, target.1));
        if let Some((tx2, ty2)) = target2 {
            desc += &format!(" and {}", bridge_to_visual(tx2, ty2));
        }
    }

    MechAction {
        mech_uid: unit.uid,
        mech_type: name.to_string(),
        move_to,
        weapon: weapon_id,
        target,
        target2,
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
        // OOB guard: bridge can deliver off-board queued_target after direction
        // normalization (M04 2026-04-28 — cx=7,ddx=+1 → x=8). board.tile() and
        // xy_to_idx panic on x>=8 / y>=8. Upstream `reader.py` nulls these,
        // but defense-in-depth here ensures direct-JSON solve calls (tests,
        // future bridge bugs) don't crash. See sim v27 changelog.
        if u.queued_target_x >= 8 || u.queued_target_y < 0 || u.queued_target_y >= 8 { continue; }
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
    disabled_mask: DisabledMask,
    weapons: &WeaponTable,
) -> Solution {
    let active: Vec<usize> = (0..board.unit_count as usize)
        .filter(|&i| {
            let u = &board.units[i];
            u.is_player_action_unit()
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
    // Inner closure: run the parallel rayon search with a given allow flag.
    // Returns (best_score, best_actions, best_clean_score, best_clean_actions, any_timed_out).
    let run_pass = |allow: bool| -> (f64, Vec<MechAction>, f64, Vec<MechAction>, bool) {
        let results: Vec<(f64, Vec<MechAction>, f64, Vec<MechAction>, bool)> = perm_mapped.par_iter().map(|mech_order| {
            let mut best_score = f64::NEG_INFINITY;
            let mut best_actions = Vec::new();
            let mut best_clean_score = f64::NEG_INFINITY;
            let mut best_clean_actions = Vec::new();
            let mut actions_buf = Vec::new();
            let mut top_k_out: Option<BoundedTopK> = None;

            search_recursive(
                board, mech_order, 0,
                &mut actions_buf, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0,
                threat_tiles, building_threats, spawn_bits,
                &original_positions,
                spawn_points, effective_max, weights, deadline,
                disabled_mask,
                allow,
                weapons,
                &mut best_score, &mut best_actions,
                &mut best_clean_score, &mut best_clean_actions, initial_building_count,
                &psion_before,
                &mut top_k_out,
            );

            let timed_out = Instant::now() > deadline;
            (best_score, best_actions, best_clean_score, best_clean_actions, timed_out)
        }).collect();

        let mut bs = f64::NEG_INFINITY;
        let mut ba: Vec<MechAction> = Vec::new();
        let mut cs = f64::NEG_INFINITY;
        let mut ca: Vec<MechAction> = Vec::new();
        let mut any_to = false;
        for (score, actions, clean_score, clean_actions, timed_out) in results {
            if timed_out { any_to = true; }
            if score > bs {
                bs = score;
                ba = actions;
            }
            if clean_score > cs {
                cs = clean_score;
                ca = clean_actions;
            }
        }
        (bs, ba, cs, ca, any_to)
    };

    // Pass 1: hard-skip soft-disabled weapons. This is the default; when
    // alternatives exist, the solver picks a reliable plan.
    let (mut best_score_v, mut best_actions_v, mut clean_score_v, mut clean_actions_v, mut any_timed_out) =
        run_pass(false);

    // Pass 2: only when Pass 1 produced no attacks AND the predicted
    // outcome is critical (mission-loss territory). Admit disabled-weapon
    // branches with the configured `soft_disabled_penalty` accrued at
    // terminal evaluation. The penalty still biases away from disabled
    // weapons, but if firing one saves enough buildings to beat pure-move
    // (after penalty), it wins. This is the "forced use" path.
    //
    // Trigger conditions:
    //   - At least one weapon in the disabled mask is on the active
    //     squad (else Pass 2 is identical to Pass 1).
    //   - Pass 1 plan has zero attacks (every action is move-only / skip).
    //   - Pass 1 predicted outcome is grid-critical: predicted final
    //     grid_power == 0, OR ≥ 2 buildings lost this turn (mission is
    //     hemorrhaging — gambling on a bad weapon-prediction is acceptable).
    //
    // The grid_power == 0 / many-buildings-lost gate keeps Pass 2 from
    // firing on routine "no attack opportunities" turns where hard-skip
    // is genuinely correct (e.g., all enemies out of range).
    let pass1_has_attack = best_actions_v.iter()
        .any(|a| a.weapon != WId::None && a.weapon != WId::Repair);
    if disabled_mask_any(disabled_mask) && !best_actions_v.is_empty() && !pass1_has_attack {
        // Re-simulate Pass 1 plan to inspect predicted outcome.
        let mut b_check = board.clone();
        for action in &best_actions_v {
            let mech_idx = match board.units.iter().position(|u| u.uid == action.mech_uid) {
                Some(i) => i,
                None => continue,
            };
            simulate_action_with_target2(
                &mut b_check,
                mech_idx,
                action.move_to,
                action.weapon,
                action.target,
                action.target2,
                weapons,
            );
        }
        let buildings_before_enemy = count_buildings(&b_check);
        simulate_enemy_attacks(&mut b_check, &original_positions, weapons);
        let buildings_after_enemy = count_buildings(&b_check);
        let buildings_lost = buildings_before_enemy - buildings_after_enemy;
        let grid_critical = b_check.grid_power == 0 || buildings_lost >= 2;

        if grid_critical {
            let (bs2, ba2, cs2, ca2, to2) = run_pass(true);
            if to2 { any_timed_out = true; }
            // Take Pass 2 result if it strictly beats Pass 1 — penalty is
            // already baked into bs2, so a higher score here means firing
            // a disabled weapon is worth its predicted-cost-of-misprediction.
            if bs2 > best_score_v {
                best_score_v = bs2;
                best_actions_v = ba2;
            }
            if cs2 > clean_score_v {
                clean_score_v = cs2;
                clean_actions_v = ca2;
            }
        }
    }

    let mut best = Solution::empty();
    best.score = best_score_v;
    best.actions = best_actions_v;
    let global_clean_score = clean_score_v;
    let global_clean_actions = clean_actions_v;

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

// ── Top-K solve ──────────────────────────────────────────────────────────────
//
// Returns the K highest-scoring plans by raw `evaluate()` score (no two-stage
// clean-plan filter — that belongs to single-plan `solve_turn`). Meant to feed
// the depth-2+ beam search: each beam level needs ranked candidates to expand.
//
// The clean-plan post-process is deliberately skipped here. A candidate that
// sacrifices a building for a decisive strategic gain is a valid beam node,
// and swapping in a lower-raw-score clean plan at position [0] would violate
// the sorted-descending contract that the caller depends on.

pub fn solve_turn_top_k(
    board: &Board,
    spawn_points: &[(u8, u8)],
    time_limit_secs: f64,
    max_actions_per_mech: usize,
    weights: &EvalWeights,
    disabled_mask: DisabledMask,
    weapons: &WeaponTable,
    k: usize,
) -> Vec<Solution> {
    if k == 0 {
        return Vec::new();
    }

    let active: Vec<usize> = (0..board.unit_count as usize)
        .filter(|&i| {
            let u = &board.units[i];
            u.is_player_action_unit()
        })
        .collect();

    if active.is_empty() {
        return Vec::new();
    }

    let n = active.len();
    let effective_max = if n >= 4 { max_actions_per_mech.min(25) } else { max_actions_per_mech };
    let (threat_tiles, building_threats) = precompute_threats(board);

    let mut spawn_bits = 0u64;
    for &(sx, sy) in spawn_points {
        spawn_bits |= 1u64 << xy_to_idx(sx, sy);
    }

    let mut original_positions = [(0u8, 0u8); 16];
    for i in 0..board.unit_count as usize {
        original_positions[i] = (board.units[i].x, board.units[i].y);
    }

    let psion_before = PsionState::capture(board);

    let perms = permutations(n);
    let total_perms = perms.len();
    let deadline = Instant::now() + Duration::from_secs_f64(time_limit_secs);
    let start = Instant::now();

    let perm_mapped: Vec<Vec<usize>> = perms.iter()
        .map(|p| p.iter().map(|&i| active[i]).collect())
        .collect();

    let initial_building_count = count_buildings(board);

    // Each rayon thread builds its own BoundedTopK. rayon collect preserves
    // input order so the downstream merge is deterministic regardless of
    // thread scheduling.
    let results: Vec<(BoundedTopK, bool)> = perm_mapped.par_iter().map(|mech_order| {
        let mut top_k_local: Option<BoundedTopK> = Some(BoundedTopK::new(k));
        // Dummy best tracking — required by search_recursive's signature but
        // unused in the top-K path. Kept as `f64::NEG_INFINITY` seeds so any
        // real terminal score wins and we don't short-circuit anything.
        let mut best_score = f64::NEG_INFINITY;
        let mut best_actions = Vec::new();
        let mut best_clean_score = f64::NEG_INFINITY;
        let mut best_clean_actions = Vec::new();
        let mut actions_buf = Vec::new();

        search_recursive(
            board, mech_order, 0,
            &mut actions_buf, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0,
            threat_tiles, building_threats, spawn_bits,
            &original_positions,
            spawn_points, effective_max, weights, deadline,
            disabled_mask,
            // Top-K (beam) path keeps the hard-skip default. The two-pass
            // forced-use fallback in `solve_turn` is for the single-best
            // plan only; expanding it into beam node generation would
            // double the search budget across every depth without a
            // matching benefit (beam already explores diverse plans).
            false,
            weapons,
            &mut best_score, &mut best_actions,
            &mut best_clean_score, &mut best_clean_actions, initial_building_count,
            &psion_before,
            &mut top_k_local,
        );

        let timed_out = Instant::now() > deadline;
        (top_k_local.expect("local top_k was Some at entry"), timed_out)
    }).collect();

    // Merge: walk permutations in input order and offer each plan to a
    // single global BoundedTopK. Local plans arrive in descending rank,
    // so the global heap's insertion sequence encodes permutation order
    // first, then within-permutation rank — giving stable tiebreaks across
    // runs even when rayon schedules differently.
    let mut global = BoundedTopK::new(k);
    let mut any_timed_out = false;
    for (local, timed_out) in results {
        if timed_out { any_timed_out = true; }
        for plan in local.into_sorted_desc() {
            global.offer(plan.score, plan.actions.as_slice());
        }
    }

    let elapsed = (Instant::now() - start).as_secs_f64();

    global.into_sorted_desc().into_iter().map(|plan| Solution {
        actions: plan.actions,
        score: plan.score,
        elapsed_secs: elapsed,
        timed_out: any_timed_out,
        permutations_tried: total_perms,
        total_permutations: total_perms,
    }).collect()
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

#[cfg(test)]
mod top_k_tests {
    //! Unit tests for `BoundedTopK`.
    //!
    //! The invariants under test are exactly what beam search will rely on:
    //!   - sorted-descending output,
    //!   - bounded capacity (worst evicted when full),
    //!   - deterministic tiebreaks on equal scores (earlier insertion wins).
    //!
    //! If these flake, `tests/test_solver_determinism.py` will flake at depth
    //! 1 already — but catching the regression here gives a sharper failure
    //! message than a byte-diff at the Python layer.
    use super::*;

    #[test]
    fn nanobots_heal_events_sum_actual_hp_restored() {
        let events = vec![
            "viscera_nanobots_heal:1:1:2".to_string(),
            "other_event".to_string(),
            "viscera_nanobots_heal:0:2:3".to_string(),
        ];

        assert_eq!(viscera_nanobots_heal_from_events(&events), 5);
    }

    #[test]
    fn feed_the_flame_events_count_exact_achievement_events() {
        let events = vec![
            "achievement_feed_the_flame:new_fire:3:weapon:Science_RainingFire_A:target:3:4".to_string(),
            "other_event".to_string(),
            "achievement_on_the_backburner:damage:4:target:3:2".to_string(),
        ];

        assert_eq!(feed_the_flame_from_events(&events), 1);
    }

    #[test]
    fn trapped_building_can_attack_from_smoke() {
        let mut board = Board::default();
        board.tile_mut(3, 3).set_smoke(true);
        let idx = board.add_unit(Unit {
            uid: 10,
            x: 3,
            y: 3,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::TrappedExplode as u16),
            flags: UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });
        board.units[idx].set_type_name("Trapped_Building");

        let actions = enumerate_actions(&board, idx, &WEAPONS);
        assert!(actions.iter().any(|a| a.1 == WId::TrappedExplode));
    }

    #[test]
    fn control_shot_target_enumeration_respects_first_click_range() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 12,
            x: 2,
            y: 1,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::ScienceTcControl as u16),
            flags: UnitFlags::ACTIVE | UnitFlags::IS_MECH | UnitFlags::PUSHABLE,
            move_speed: 0,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 100,
            x: 1,
            y: 1,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            flags: UnitFlags::PUSHABLE | UnitFlags::IS_MECH,
            move_speed: 3,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 101,
            x: 2,
            y: 2,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 102,
            x: 2,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 103,
            x: 3,
            y: 2,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        });

        let targets = get_weapon_targets(
            &board,
            2,
            1,
            WId::ScienceTcControl,
            (2, 1),
            &WEAPONS,
        );
        assert!(
            targets.contains(&(2, 2)),
            "Control Shot should offer adjacent enemy first-click targets"
        );
        assert!(
            !targets.contains(&(2, 3)),
            "Control Shot must not offer non-adjacent target units"
        );
        assert!(
            !targets.contains(&(1, 1)),
            "Control Shot should not offer allied targets while farming Let's Walk"
        );
        assert!(
            !targets.contains(&(3, 2)),
            "Control Shot should not offer diagonal first-click targets"
        );

        let actions = enumerate_actions(&board, idx, &WEAPONS);
        assert!(
            actions.iter().any(|a| {
                a.1 == WId::ScienceTcControl && a.2 == (2, 2) && a.3 == Some((0, 2))
            }),
            "action enumeration should keep adjacent Control Shot targets and two-space destinations"
        );
        assert!(
            actions.iter().all(|a| !(a.1 == WId::ScienceTcControl && a.2 == (2, 3))),
            "action enumeration should reject non-adjacent Control Shot targets"
        );
        assert!(
            actions.iter().all(|a| !(a.1 == WId::ScienceTcControl && a.2 == (1, 1))),
            "action enumeration should reject allied Control Shot targets"
        );
        assert!(
            actions.iter().all(|a| !(a.1 == WId::ScienceTcControl && a.2 == (3, 2))),
            "action enumeration should reject diagonal Control Shot targets"
        );
    }

    #[test]
    fn control_shot_target_enumeration_respects_projectile_blockers() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 12,
            x: 2,
            y: 1,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::ScienceTcControl as u16),
            flags: UnitFlags::ACTIVE | UnitFlags::IS_MECH | UnitFlags::PUSHABLE,
            move_speed: 0,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 101,
            x: 2,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 102,
            x: 3,
            y: 1,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        });
        {
            let tile = board.tile_mut(2, 2);
            tile.terrain = Terrain::Building;
            tile.building_hp = 2;
        }

        let targets = get_weapon_targets(
            &board,
            2,
            1,
            WId::ScienceTcControl,
            (2, 1),
            &WEAPONS,
        );
        assert!(
            targets.contains(&(3, 1)),
            "Control Shot should offer unobstructed first-click targets"
        );
        assert!(
            !targets.contains(&(2, 3)),
            "Control Shot should not offer targets behind projectile blockers"
        );

        let actions = enumerate_actions(&board, idx, &WEAPONS);
        assert!(
            actions.iter().any(|a| a.1 == WId::ScienceTcControl && a.2 == (3, 1)),
            "action enumeration should keep unobstructed Control Shot targets"
        );
        assert!(
            actions.iter().all(|a| !(a.1 == WId::ScienceTcControl && a.2 == (2, 3))),
            "action enumeration should reject obstructed Control Shot targets"
        );
    }

    #[test]
    fn infected_full_hp_mech_can_repair() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 11,
            x: 3,
            y: 1,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::ACTIVE | UnitFlags::IS_MECH | UnitFlags::INFECTED,
            move_speed: 0,
            ..Default::default()
        });
        board.units[idx].set_type_name("PulseMech");

        let actions = enumerate_actions(&board, idx, &WEAPONS);
        assert!(
            actions.iter().any(|a| a.1 == WId::Repair),
            "Vek Mites must make Repair a legal action even at full HP"
        );
    }

    #[test]
    fn shield_bash_can_target_mountain_terrain() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 21,
            x: 4,
            y: 4,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            weapon: WeaponId(WId::PrimeShieldBash as u16),
            flags: UnitFlags::ACTIVE | UnitFlags::IS_MECH | UnitFlags::PUSHABLE,
            move_speed: 0,
            ..Default::default()
        });
        board.tile_mut(4, 3).terrain = Terrain::Mountain;
        board.tile_mut(4, 3).building_hp = 1;

        let actions = enumerate_actions(&board, idx, &WEAPONS);

        assert!(
            actions.iter().any(|a| {
                a.0 == (4, 4) && a.1 == WId::PrimeShieldBash && a.2 == (4, 3)
            }),
            "Spartan Shield should treat damaging a mountain as a real action"
        );
    }

    #[test]
    fn mirror_shot_can_target_direction_to_first_mountain() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 22,
            x: 4,
            y: 4,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            weapon: WeaponId(WId::BruteMirrorshot as u16),
            flags: UnitFlags::ACTIVE | UnitFlags::IS_MECH | UnitFlags::PUSHABLE,
            move_speed: 0,
            ..Default::default()
        });
        board.tile_mut(4, 2).terrain = Terrain::Mountain;
        board.tile_mut(4, 2).building_hp = 1;

        let actions = enumerate_actions(&board, idx, &WEAPONS);

        assert!(
            actions.iter().any(|a| {
                a.0 == (4, 4) && a.1 == WId::BruteMirrorshot && a.2 == (4, 3)
            }),
            "Mirror Shot should keep a direction click when the first blocker is a mountain"
        );
    }

    #[test]
    fn mission_force_pruning_keeps_damaged_mountain_shot() {
        let mut board = Board::default();
        board.mission_id = "Mission_Force".to_string();
        board.mission_mountain_target = 2;
        let idx = board.add_unit(Unit {
            uid: 23,
            x: 4,
            y: 4,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            weapon: WeaponId(WId::BruteMirrorshot as u16),
            flags: UnitFlags::ACTIVE | UnitFlags::IS_MECH | UnitFlags::PUSHABLE,
            move_speed: 0,
            ..Default::default()
        });
        board.tile_mut(4, 2).terrain = Terrain::Mountain;
        board.tile_mut(4, 2).building_hp = 1;

        let mut actions = vec![
            ((4, 4), WId::None, (255, 255), None),
            ((4, 4), WId::BruteMirrorshot, (4, 3), None),
            ((4, 4), WId::BruteMirrorshot, (5, 4), None),
        ];

        prune_actions(
            &board,
            idx,
            &mut actions,
            0,
            0,
            0,
            1,
            &WEAPONS,
        );

        assert_eq!(
            actions,
            vec![((4, 4), WId::BruteMirrorshot, (4, 3), None)],
            "Mission_Force pruning should keep the damaged-mountain shot"
        );
    }

    #[test]
    fn webbed_mech_cannot_use_normal_move_phase() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 12,
            x: 4,
            y: 4,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::ACTIVE | UnitFlags::IS_MECH | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE | UnitFlags::WEB,
            move_speed: 4,
            base_move: 4,
            weapon: WeaponId(WId::PrimeShieldBash as u16),
            ..Default::default()
        });
        board.units[idx].set_type_name("GuardMech");
        let enemy_idx = board.add_unit(Unit {
            uid: 212,
            x: 4,
            y: 3,
            hp: 1,
            max_hp: 1,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        });
        board.units[enemy_idx].set_type_name("Leaper1");

        let actions = enumerate_actions(&board, idx, &WEAPONS);

        assert!(!actions.is_empty(), "webbed mechs should still have attack/skip options");
        assert!(
            actions.iter().all(|a| a.0 == (4, 4)),
            "webbed normal movement must stay on the current tile; got {:?}",
            actions
        );
    }

    #[test]
    fn webbed_leap_mech_cannot_use_hydraulic_legs() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 12,
            x: 4,
            y: 4,
            hp: 2,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::ACTIVE | UnitFlags::IS_MECH | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE | UnitFlags::WEB,
            move_speed: 4,
            base_move: 4,
            weapon: WeaponId(WId::PrimeLeap as u16),
            ..Default::default()
        });
        board.units[idx].set_type_name("LeapMech");
        let enemy_idx = board.add_unit(Unit {
            uid: 212,
            x: 5,
            y: 5,
            hp: 1,
            max_hp: 1,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        });
        board.units[enemy_idx].set_type_name("Leaper1");

        let actions = enumerate_actions(&board, idx, &WEAPONS);

        assert!(
            actions.iter().any(|a| a.1 == WId::Repair),
            "damaged webbed Leap Mech should still be able to repair"
        );
        assert!(
            !actions.iter().any(|a| a.1 == WId::PrimeLeap),
            "webbed Leap Mech must not enumerate Hydraulic Legs; got {:?}",
            actions
        );
    }

    #[test]
    fn prime_leap_targets_are_cardinal_only() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 12,
            x: 5,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::ACTIVE | UnitFlags::IS_MECH | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE,
            move_speed: 4,
            base_move: 4,
            weapon: WeaponId(WId::PrimeLeap as u16),
            ..Default::default()
        });
        board.units[idx].set_type_name("LeapMech");

        let targets = get_weapon_targets(&board, 5, 3, WId::PrimeLeap, (5, 3), &WEAPONS);

        assert!(targets.contains(&(5, 1)), "cardinal long landing should be legal");
        assert!(
            !targets.contains(&(4, 1)),
            "Hydraulic Legs should not enumerate non-cardinal landing G4 from E3; got {:?}",
            targets
        );
    }

    #[test]
    fn reverse_thrusters_targets_include_vacated_start_tile() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 12,
            x: 3,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::ACTIVE
                | UnitFlags::IS_MECH
                | UnitFlags::CAN_MOVE
                | UnitFlags::PUSHABLE
                | UnitFlags::FLYING,
            move_speed: 4,
            base_move: 4,
            weapon: WeaponId(WId::BruteKickBack as u16),
            ..Default::default()
        });
        board.units[idx].set_type_name("NeedleMech");

        let targets = get_weapon_targets(
            &board,
            3,
            5,
            WId::BruteKickBack,
            (3, 3),
            &WEAPONS,
        );

        assert!(
            targets.contains(&(3, 3)),
            "Reverse Thrusters should allow landing on the tile vacated by pre-attack movement; got {:?}",
            targets
        );
    }

    #[test]
    fn prime_leap_ground_mech_cannot_target_deadly_ground_landings() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 12,
            x: 5,
            y: 3,
            hp: 5,
            max_hp: 5,
            team: Team::Player,
            flags: UnitFlags::ACTIVE | UnitFlags::IS_MECH | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE,
            move_speed: 5,
            base_move: 5,
            weapon: WeaponId(WId::PrimeLeap as u16),
            ..Default::default()
        });
        board.units[idx].set_type_name("LeapMech");
        board.tile_mut(4, 3).terrain = Terrain::Water;
        board.tile_mut(3, 3).terrain = Terrain::Lava;

        let targets = get_weapon_targets(&board, 5, 3, WId::PrimeLeap, (5, 3), &WEAPONS);

        assert!(
            !targets.contains(&(4, 3)),
            "Hydraulic Legs should not enumerate water landing D4 for a ground mech"
        );
        assert!(
            !targets.contains(&(3, 3)),
            "Hydraulic Legs should not enumerate lava landing E4 for a ground mech"
        );
    }

    #[test]
    fn bomb_dispenser_targets_empty_cardinal_deploy_tiles() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 12,
            x: 3,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::ACTIVE | UnitFlags::IS_MECH | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE,
            move_speed: 4,
            base_move: 4,
            weapon: WeaponId(WId::RangedDeployBomb as u16),
            ..Default::default()
        });
        board.units[idx].set_type_name("BomblingMech");
        let occupied = board.add_unit(Unit {
            uid: 21,
            x: 3,
            y: 5,
            hp: 1,
            max_hp: 1,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        });
        board.units[occupied].set_type_name("Leaper1");
        board.tile_mut(5, 3).terrain = Terrain::Mountain;

        let targets = get_weapon_targets(
            &board,
            3,
            3,
            WId::RangedDeployBomb,
            (3, 3),
            &WEAPONS,
        );

        assert!(targets.contains(&(3, 1)), "range-2 cardinal tile should be legal");
        assert!(targets.contains(&(6, 3)), "LineArtillery continues behind blockers");
        assert!(!targets.contains(&(4, 4)), "off-axis tile should not be legal");
        assert!(!targets.contains(&(3, 5)), "occupied deploy tile should be rejected");
        assert!(!targets.contains(&(5, 3)), "mountain deploy tile should be rejected");
        assert!(weapon_action_has_effect(
            &board,
            (3, 3),
            WId::RangedDeployBomb,
            (3, 1),
            &WEAPONS,
        ));
        assert!(!weapon_action_has_effect(
            &board,
            (3, 3),
            WId::RangedDeployBomb,
            (3, 5),
            &WEAPONS,
        ));
    }

    #[test]
    fn upgraded_bomb_dispenser_enumerates_two_deploy_clicks() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 12,
            x: 3,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::ACTIVE | UnitFlags::IS_MECH | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE,
            move_speed: 4,
            base_move: 4,
            weapon: WeaponId(WId::RangedDeployBombA as u16),
            ..Default::default()
        });
        board.units[idx].set_type_name("BomblingMech");
        let occupied = board.add_unit(Unit {
            uid: 21,
            x: 3,
            y: 5,
            hp: 1,
            max_hp: 1,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        });
        board.units[occupied].set_type_name("Leaper1");
        board.tile_mut(5, 3).terrain = Terrain::Mountain;

        let targets = get_weapon_targets(
            &board,
            3,
            3,
            WId::RangedDeployBombA,
            (3, 3),
            &WEAPONS,
        );
        assert!(targets.contains(&(3, 1)), "first click can use a range-2 deploy tile");
        assert!(!targets.contains(&(3, 5)), "occupied first click should be rejected");
        assert!(!targets.contains(&(5, 3)), "blocked first click should be rejected");

        let actions = enumerate_actions(&board, idx, &WEAPONS);
        assert!(
            actions.iter().any(|a| {
                a.1 == WId::RangedDeployBombA
                    && a.2 == (3, 1)
                    && a.3 == Some((1, 3))
            }),
            "2 Bombs should emit first and second deploy targets in different directions"
        );
        assert!(
            !actions.iter().any(|a| {
                a.1 == WId::RangedDeployBombA
                    && a.2 == (3, 1)
                    && a.3 == Some((3, 0))
            }),
            "second deploy target must not reuse the first target direction"
        );
    }

    #[test]
    fn arachnoid_injector_targets_are_cardinal_artillery() {
        let mut board = Board::default();
        let mech_idx = board.add_unit(Unit {
            uid: 1,
            x: 2,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::ACTIVE | UnitFlags::PUSHABLE,
            weapon: WeaponId(WId::RangedArachnoid as u16),
            ..Default::default()
        });
        let _scorpion = board.add_unit(Unit {
            uid: 94,
            x: 6,
            y: 2,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });
        let _leaper = board.add_unit(Unit {
            uid: 95,
            x: 2,
            y: 6,
            hp: 1,
            max_hp: 1,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let targets = get_weapon_targets(
            &board,
            2,
            3,
            WId::RangedArachnoid,
            (2, 3),
            &WEAPONS,
        );

        assert!(targets.contains(&(2, 6)), "same-column artillery tile should be legal");
        assert!(!targets.contains(&(6, 2)), "off-axis E6->F2 live FireWeapon is a no-op");
        assert!(weapon_action_has_effect(
            &board,
            (2, 3),
            WId::RangedArachnoid,
            (2, 6),
            &WEAPONS,
        ));
        let actions = enumerate_actions(&board, mech_idx, &WEAPONS);
        assert!(
            actions.iter().any(|a| a.1 == WId::RangedArachnoid && a.2 == (2, 6)),
            "Arachnoid Injector should be emitted as a live solver action",
        );
        let mut pruned = actions.clone();
        prune_actions(&board, mech_idx, &mut pruned, 0, 0, 0, 1, &WEAPONS);
        assert!(
            pruned.iter().any(|a| a.1 == WId::RangedArachnoid && a.2 == (2, 6)),
            "Arachnoid Injector killing blows should survive tight pruning",
        );
        assert!(!weapon_action_has_effect(
            &board,
            (2, 3),
            WId::RangedArachnoid,
            (6, 2),
            &WEAPONS,
        ));
    }

    #[test]
    fn vip_truck_with_move_helper_is_active_solver_unit() {
        let mut board = Board::default();
        board.current_turn = 2;
        board.total_turns = 4;
        board.protect_objective_unit_types.push("VIP_Truck".to_string());

        let truck_idx = board.add_unit(Unit {
            uid: 1197,
            x: 3,
            y: 3,
            hp: 1,
            max_hp: 1,
            team: Team::Player,
            flags: UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE,
            move_speed: 0,
            base_move: 0,
            weapon: WeaponId(WId::VipTruckMove as u16),
            ..Default::default()
        });
        board.units[truck_idx].set_type_name("VIP_Truck");

        let enemy_idx = board.add_unit(Unit {
            uid: 200,
            x: 3,
            y: 0,
            hp: 2,
            max_hp: 2,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            move_speed: 3,
            queued_target_x: 3,
            queued_target_y: 3,
            weapon_damage: 1,
            ..Default::default()
        });
        board.units[enemy_idx].set_type_name("Firefly1");

        assert_eq!(board.active_mechs(), vec![truck_idx]);

        let solution = solve_turn(
            &board,
            &[],
            1.0,
            25,
            &EvalWeights::default(),
            [0; 2],
            &WEAPONS,
        );

        assert!(
            solution.actions.iter().any(|a| {
                a.mech_uid == 1197
                    && a.weapon == WId::VipTruckMove
                    && a.move_to == (3, 3)
                    && a.target != (3, 3)
            }),
            "solver should use VIP_Truck_Move on the threatened truck; got {:?}",
            solution.actions
        );
    }

    #[test]
    fn detritus_global_effect_targets_live_non_source_unit() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 20,
            x: 1,
            y: 3,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::MissilesOneDmg as u16),
            flags: UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 21,
            x: 6,
            y: 3,
            hp: 5,
            max_hp: 5,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let actions = enumerate_actions(&board, idx, &WEAPONS);
        assert!(actions.iter().any(|a| {
            a.1 == WId::MissilesOneDmg && a.2 == (6, 3)
        }));
        assert!(!actions.iter().any(|a| {
            a.1 == WId::MissilesOneDmg && a.2 == (1, 3)
        }));
    }

    #[test]
    fn mission_missiles_prefers_contraption_use_over_skip() {
        let mut board = Board::default();
        board.mission_id = "Mission_Missiles".to_string();
        board.grid_power = 3;
        board.grid_power_max = 7;
        let idx = board.add_unit(Unit {
            uid: 20,
            x: 1,
            y: 3,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::MissilesShield as u16),
            weapon2: WeaponId(WId::MissilesOneDmg as u16),
            flags: UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });
        board.units[idx].set_type_name("Missile_Unit");
        board.add_unit(Unit {
            uid: 21,
            x: 6,
            y: 3,
            hp: 5,
            max_hp: 5,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let solution = solve_turn(
            &board,
            &[],
            1.0,
            25,
            &EvalWeights::default(),
            [0; 2],
            &WEAPONS,
        );

        assert!(
            solution.actions.iter().any(|a| {
                a.mech_type == "Missile_Unit"
                    && matches!(a.weapon, WId::MissilesShield | WId::MissilesOneDmg)
            }),
            "Mission_Missiles should spend a Detritus Contraption shot instead of skipping"
        );
    }

    #[test]
    fn mission_missiles_smoked_contraption_can_still_fire() {
        let mut board = Board::default();
        board.mission_id = "Mission_Missiles".to_string();
        let idx = board.add_unit(Unit {
            uid: 20,
            x: 1,
            y: 3,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::MissilesShield as u16),
            weapon2: WeaponId(WId::MissilesOneDmg as u16),
            flags: UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });
        board.units[idx].set_type_name("Missile_Unit");
        board.tile_mut(1, 3).set_smoke(true);
        board.add_unit(Unit {
            uid: 21,
            x: 6,
            y: 3,
            hp: 5,
            max_hp: 5,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let actions = enumerate_actions(&board, idx, &WEAPONS);
        assert!(
            actions.iter().any(|a| {
                matches!(a.1, WId::MissilesShield | WId::MissilesOneDmg)
                    && a.2 != (1, 3)
            }),
            "Missile_Unit has IgnoreSmoke=true and should still enumerate barrages while smoked"
        );
    }

    #[test]
    fn titan_fist_dash_enumerates_direction_selector_for_long_target() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 0,
            x: 1,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            weapon: WeaponId(WId::PrimePunchmechA as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 100,
            x: 6,
            y: 3,
            hp: 2,
            max_hp: 2,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let actions = enumerate_actions(&board, idx, &WEAPONS);

        assert!(
            actions.iter().any(|a| {
                a.0 == (1, 3) && a.1 == WId::PrimePunchmechA && a.2 == (2, 3)
            }),
            "Dash Punch should click the adjacent east direction selector"
        );
    }

    #[test]
    fn artemis_artillery_rejects_off_axis_targets() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 2,
            x: 2,
            y: 4,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::RangedArtillerymech as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 2214,
            x: 6,
            y: 2,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let targets = get_weapon_targets(
            &board,
            board.units[idx].x,
            board.units[idx].y,
            WId::RangedArtillerymech,
            (board.units[idx].x, board.units[idx].y),
            &WEAPONS,
        );

        assert!(
            !targets.contains(&(6, 2)),
            "Artemis D6->F2 is off-axis and live FireWeapon spends an effectless shot"
        );
        assert!(
            targets.contains(&(2, 2)),
            "Artemis should still target cardinal F6 from D6"
        );
    }

    #[test]
    fn arachnoid_injector_rejects_off_axis_targets() {
        // Live Arachnoid Injector no-ops when FireWeapon is pointed off-axis.
        // Regression anchor: Lucky Start run 20260615_221604_970
        // Mission_Airstrike turn 1 tried ScorpioMech D5 -> off-axis E1;
        // live Firefly1 stayed at 3 HP while the simulator predicted 2 HP.
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 2,
            x: 3,
            y: 4,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            weapon: WeaponId(WId::RangedArachnoid as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 102,
            x: 7,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 103,
            x: 7,
            y: 4,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let targets = get_weapon_targets(
            &board,
            board.units[idx].x,
            board.units[idx].y,
            WId::RangedArachnoid,
            (board.units[idx].x, board.units[idx].y),
            &WEAPONS,
        );

        assert!(
            !targets.contains(&(7, 3)),
            "Arachnoid D5->E1 is off-axis and live FireWeapon spends an effectless shot"
        );
        assert!(
            targets.contains(&(7, 4)),
            "Arachnoid should still target cardinal D1 from D5"
        );
    }

    #[test]
    fn hydraulic_lifter_enumerates_second_click_landings() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 2,
            x: 3,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            weapon: WeaponId(WId::PrimeTcPunt as u16),
            flags: UnitFlags::IS_MECH | UnitFlags::PUSHABLE | UnitFlags::ACTIVE,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 90,
            x: 3,
            y: 2,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let targets = get_weapon_targets(
            &board,
            board.units[idx].x,
            board.units[idx].y,
            WId::PrimeTcPunt,
            (board.units[idx].x, board.units[idx].y),
            &WEAPONS,
        );

        assert!(targets.contains(&(3, 1)));
        assert!(targets.contains(&(3, 0)));
        assert!(!targets.contains(&(3, 2)), "first click tile is not the solver target");
    }

    #[test]
    fn tri_rocket_excludes_adjacent_center_target() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 2,
            x: 3,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            weapon: WeaponId(WId::RangedCrack as u16),
            flags: UnitFlags::IS_MECH | UnitFlags::PUSHABLE | UnitFlags::ACTIVE,
            ..Default::default()
        });

        let targets = get_weapon_targets(
            &board,
            board.units[idx].x,
            board.units[idx].y,
            WId::RangedCrack,
            (board.units[idx].x, board.units[idx].y),
            &WEAPONS,
        );

        assert!(!targets.contains(&(3, 2)));
        assert!(targets.contains(&(3, 1)));
        assert!(!targets.contains(&(2, 2)), "Tri-Rocket target area is still cardinal-only");
    }

    #[test]
    fn vulcan_artillery_can_target_building_center_for_adjacent_push() {
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 2,
            x: 5,
            y: 1,
            hp: 2,
            max_hp: 3,
            team: Team::Player,
            weapon: WeaponId(WId::RangedIgnite as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });
        {
            let tile = board.tile_mut(5, 3);
            tile.terrain = Terrain::Building;
            tile.building_hp = 1;
        }
        board.add_unit(Unit {
            uid: 231,
            x: 5,
            y: 2,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let actions = enumerate_actions(&board, idx, &WEAPONS);

        assert!(
            actions.iter().any(|a| {
                a.0 == (5, 1) && a.1 == WId::RangedIgnite && a.2 == (5, 3)
            }),
            "Vulcan Artillery should be able to target a live building when the zero-damage center shot pushes adjacent attackers"
        );
    }

    #[test]
    fn rock_accelerator_rejects_off_axis_targets() {
        // Rock Accelerator is implemented in the Artillery simulator arm, but
        // its live target area is a straight cardinal line rather than an
        // Artemis-style arc. See docs/research/blitzkrieg_boulder_mech.md.
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 2,
            x: 2,
            y: 5,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::RangedRockthrow as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });

        let targets = get_weapon_targets(
            &board,
            board.units[idx].x,
            board.units[idx].y,
            WId::RangedRockthrow,
            (board.units[idx].x, board.units[idx].y),
            &WEAPONS,
        );

        assert!(
            !targets.contains(&(6, 3)),
            "Rock Accelerator must not target off-axis E2 from C6"
        );
        assert!(
            targets.contains(&(2, 3)),
            "Rock Accelerator should still target cardinal E6 from C6"
        );
    }

    #[test]
    fn science_swap_ab_rejects_diagonal_targets() {
        // Live Flame Behemoths run 20260519_224158_398, Mission_Holes turn 2:
        // TeleMech at D7 fired upgraded Teleporter at C6. The bridge fired
        // Science_Swap_AB, but the engine target area is cardinal-only, so the
        // diagonal click spent an effectless action.
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 2,
            x: 1,
            y: 4,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::ScienceSwapAB as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });

        let targets = get_weapon_targets(
            &board,
            board.units[idx].x,
            board.units[idx].y,
            WId::ScienceSwapAB,
            (board.units[idx].x, board.units[idx].y),
            &WEAPONS,
        );

        assert!(
            !targets.contains(&(2, 5)),
            "Teleporter D7->C6 is diagonal and must not be enumerated"
        );
        assert!(
            targets.contains(&(1, 0)),
            "Upgraded Teleporter should still reach straight-line H7 at range 4"
        );
    }

    #[test]
    fn self_aoe_after_teleporter_targets_post_swap_tile() {
        // Mission_Teleporter m23 turn 4: action enumeration used the pad tile
        // as Repulse's click target even though the move phase swapped Pulse
        // to the paired pad before ATTACK. That stale diagonal target spent the
        // action without pushing the adjacent Bouncer.
        let mut board = Board::default();
        board.teleporter_pairs.push((4, 4, 5, 3));
        let idx = board.add_unit(Unit {
            uid: 2,
            x: 5,
            y: 4,
            hp: 5,
            max_hp: 3,
            team: Team::Player,
            weapon: WeaponId(WId::ScienceRepulseA as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ACTIVE
                | UnitFlags::CAN_MOVE,
            move_speed: 4,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 738,
            x: 5,
            y: 2,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let actions = enumerate_actions(&board, idx, &WEAPONS);

        assert!(
            actions.iter().any(|a| {
                a.0 == (4, 4) && a.1 == WId::ScienceRepulseA && a.2 == (5, 3)
            }),
            "Repulse after pad swap must click the post-teleport Pulse tile"
        );
        assert!(
            !actions.iter().any(|a| {
                a.0 == (4, 4) && a.1 == WId::ScienceRepulseA && a.2 == (4, 4)
            }),
            "Repulse must not keep the stale pre-teleport pad target"
        );
    }

    #[test]
    fn moved_aerial_bombs_targets_from_post_move_tile() {
        // Mission_Teleporter m23 turn 4 recovery: JetMech at G1 could move to
        // D3, but Aerial Bombs still had to target from D3. Targeting G3 was
        // only legal from the pre-move G1 tile and spent the bridge attack as a
        // no-op click_miss.
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 0,
            x: 7,
            y: 1,
            hp: 5,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::BruteJetmech as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::FLYING
                | UnitFlags::ACTIVE
                | UnitFlags::CAN_MOVE,
            move_speed: 5,
            ..Default::default()
        });

        let actions = enumerate_actions(&board, idx, &WEAPONS);

        assert!(
            !actions.iter().any(|a| {
                a.0 == (5, 4) && a.1 == WId::BruteJetmech && a.2 == (5, 1)
            }),
            "Aerial Bombs after G1->D3 must not keep pre-move target G3"
        );
        assert!(
            actions.iter().any(|a| {
                a.0 == (5, 4) && a.1 == WId::BruteJetmech && a.2 == (5, 2)
            }),
            "Aerial Bombs after G1->D3 should enumerate targets from D3"
        );
    }

    #[test]
    fn rocket_artillery_rejects_off_axis_targets() {
        // Live Rocket Artillery no-ops when FireWeapon is pointed off-axis.
        // Keep Rocket-specific enumeration cardinal-only so the solver doesn't
        // choose bridge-accepted but effectless diagonal targets.
        // Regression anchor: Rusting Hulks Mission_Reactivation turn 2 tried
        // RocketMech E6 -> off-axis C4; live Burnbug1 survived untouched.
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 1,
            x: 2,
            y: 3,
            hp: 5,
            max_hp: 3,
            team: Team::Player,
            weapon: WeaponId(WId::RangedRocketA as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ACTIVE
                | UnitFlags::CAN_MOVE,
            move_speed: 3,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 899,
            x: 4,
            y: 5,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let actions = enumerate_actions(&board, idx, &WEAPONS);

        assert!(
            !actions.iter().any(|a| {
                a.0 == (2, 3) && a.1 == WId::RangedRocketA && a.2 == (4, 5)
            }),
            "Rocket artillery must not enumerate off-axis target C4 from E6"
        );
    }

    #[test]
    fn shield_projector_enumerates_building_defense_targets() {
        // Zenith Guard Corporate HQ dirty-chain deep dive: Defense Mech must be
        // able to click a threatened building directly, or the empty tile before
        // it when Shield Projector's second line tile is the useful shield.
        let mut direct = Board::default();
        let idx = direct.add_unit(Unit {
            uid: 2,
            x: 4,
            y: 3,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::ScienceShield as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });
        {
            let tile = direct.tile_mut(2, 3);
            tile.terrain = Terrain::Building;
            tile.building_hp = 1;
        }

        let actions = enumerate_actions(&direct, idx, &WEAPONS);
        assert!(
            actions.iter().any(|a| {
                a.0 == (4, 3) && a.1 == WId::ScienceShield && a.2 == (2, 3)
            }),
            "Shield Projector should be able to target the live building at C5"
        );

        let mut line_tile = Board::default();
        let idx = line_tile.add_unit(Unit {
            uid: 2,
            x: 4,
            y: 3,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::ScienceShield as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });
        {
            let tile = line_tile.tile_mut(1, 3);
            tile.terrain = Terrain::Building;
            tile.building_hp = 1;
        }

        let actions = enumerate_actions(&line_tile, idx, &WEAPONS);
        assert!(
            actions.iter().any(|a| {
                a.0 == (4, 3) && a.1 == WId::ScienceShield && a.2 == (2, 3)
            }),
            "Shield Projector should keep the empty C5 target when B5 is shielded by the second line tile"
        );
    }

    #[test]
    fn aerial_bombs_from_smoke_origin_is_not_enumerated() {
        // Mission_Reactivation turn 2 diagnostic: a hand-written line put
        // JetMech on smoked A5 then fired Aerial Bombs at C5. The solver was
        // right to omit the attack; smoke cancels mech attacks from that tile.
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 0,
            x: 4,
            y: 7,
            hp: 4,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::BruteJetmech as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::FLYING
                | UnitFlags::ACTIVE
                | UnitFlags::CAN_MOVE,
            move_speed: 5,
            ..Default::default()
        });
        board.tile_mut(3, 7).set_smoke(true);

        let actions = enumerate_actions(&board, idx, &WEAPONS);
        assert!(
            actions.iter().any(|a| {
                a.0 == (3, 7) && a.1 == WId::None && a.2 == (255, 255)
            }),
            "Jet should still be allowed to move onto smoked A5"
        );
        assert!(
            !actions.iter().any(|a| {
                a.0 == (3, 7) && a.1 == WId::BruteJetmech && a.2 == (3, 5)
            }),
            "Aerial Bombs must not be available from a smoked attack origin"
        );

        board.tile_mut(3, 7).set_smoke(false);
        let actions = enumerate_actions(&board, idx, &WEAPONS);
        assert!(
            actions.iter().any(|a| {
                a.0 == (3, 7) && a.1 == WId::BruteJetmech && a.2 == (3, 5)
            }),
            "Clearing smoke should restore the Aerial Bombs target"
        );
    }

    #[test]
    fn aerial_bombs_transit_smoke_building_threat_survives_pruning() {
        // Hard Rusting Hulks 20260513_230944_542, Forgotten Hills turn 4:
        // Jet E6->B5 firing at B3 smokes the B4 Bouncer and cancels its A4
        // building attack. With four active units, the live search prunes to
        // 25 actions per unit; this line must be scored like a threat answer.
        let mut board = Board::default();
        let idx = board.add_unit(Unit {
            uid: 0,
            x: 2,
            y: 3,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            weapon: WeaponId(WId::BruteJetmech as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::FLYING
                | UnitFlags::ACTIVE
                | UnitFlags::CAN_MOVE,
            move_speed: 4,
            ..Default::default()
        });
        board.add_unit(Unit {
            uid: 100,
            x: 4,
            y: 6,
            hp: 4,
            max_hp: 4,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE | UnitFlags::HAS_QUEUED_ATTACK,
            queued_target_x: 4,
            queued_target_y: 7,
            ..Default::default()
        });
        {
            let tile = board.tile_mut(4, 7);
            tile.terrain = Terrain::Building;
            tile.building_hp = 1;
        }

        let (threat_tiles, building_threats) = precompute_threats(&board);
        let mut actions = enumerate_actions(&board, idx, &WEAPONS);
        assert!(
            actions.iter().any(|a| {
                a.0 == (3, 6) && a.1 == WId::BruteJetmech && a.2 == (5, 6)
            }),
            "Jet E6->B5, Aerial Bombs at B3 should be legal before pruning"
        );

        prune_actions(
            &board,
            idx,
            &mut actions,
            threat_tiles,
            building_threats,
            0,
            25,
            &WEAPONS,
        );

        assert!(
            actions.iter().any(|a| {
                a.0 == (3, 6) && a.1 == WId::BruteJetmech && a.2 == (5, 6)
            }),
            "transit smoke over the B4 attacker must survive the four-unit pruning cap"
        );
    }

    #[test]
    fn bounded_top_k_basic_desc_ordering() {
        let mut h = BoundedTopK::new(5);
        h.offer(10.0, &[]);
        h.offer(30.0, &[]);
        h.offer(20.0, &[]);
        let out = h.into_sorted_desc();
        assert_eq!(out.len(), 3);
        assert_eq!(out[0].score, 30.0);
        assert_eq!(out[1].score, 20.0);
        assert_eq!(out[2].score, 10.0);
    }

    #[test]
    fn bounded_top_k_respects_capacity() {
        let mut h = BoundedTopK::new(3);
        for s in [10.0, 50.0, 20.0, 40.0, 30.0] {
            h.offer(s, &[]);
        }
        let out = h.into_sorted_desc();
        assert_eq!(out.len(), 3);
        assert_eq!(out[0].score, 50.0);
        assert_eq!(out[1].score, 40.0);
        assert_eq!(out[2].score, 30.0);
    }

    #[test]
    fn bounded_top_k_earlier_insertion_wins_ties() {
        // All three plans fit (capacity >= n). Output must preserve insertion
        // order, because within equal scores our Ord treats smaller seq as
        // "better" (the deterministic tiebreak).
        let mut h = BoundedTopK::new(3);
        h.offer(10.0, &[]);
        h.offer(10.0, &[]);
        h.offer(10.0, &[]);
        let out = h.into_sorted_desc();
        assert_eq!(out.len(), 3);
        assert_eq!(out[0].seq, 0);
        assert_eq!(out[1].seq, 1);
        assert_eq!(out[2].seq, 2);
    }

    #[test]
    fn bounded_top_k_tie_rejects_later_insertion_at_capacity() {
        // Capacity 2; four tied offers — first two win, last two are rejected
        // because ties lose against incumbents (later seqs are "worse").
        let mut h = BoundedTopK::new(2);
        h.offer(10.0, &[]); // seq=0
        h.offer(10.0, &[]); // seq=1
        h.offer(10.0, &[]); // seq=2 → rejected
        h.offer(10.0, &[]); // seq=3 → rejected
        let out = h.into_sorted_desc();
        assert_eq!(out.len(), 2);
        assert_eq!(out[0].seq, 0);
        assert_eq!(out[1].seq, 1);
    }

    #[test]
    fn bounded_top_k_higher_score_evicts_worst() {
        // Fill with two tied plans, then a strictly higher score arrives —
        // it evicts the later-seq tied plan (the current worst).
        let mut h = BoundedTopK::new(2);
        h.offer(10.0, &[]); // seq=0
        h.offer(10.0, &[]); // seq=1
        h.offer(20.0, &[]); // seq=2 — evicts seq=1
        let out = h.into_sorted_desc();
        assert_eq!(out.len(), 2);
        assert_eq!(out[0].score, 20.0);
        assert_eq!(out[0].seq, 2);
        assert_eq!(out[1].score, 10.0);
        assert_eq!(out[1].seq, 0);
    }

    #[test]
    fn bounded_top_k_empty() {
        let h = BoundedTopK::new(5);
        assert!(h.is_empty());
        assert_eq!(h.len(), 0);
        assert_eq!(h.into_sorted_desc().len(), 0);
    }

    #[test]
    fn bounded_top_k_k_greater_than_plans_returns_all() {
        let mut h = BoundedTopK::new(10);
        h.offer(10.0, &[]);
        h.offer(20.0, &[]);
        h.offer(5.0, &[]);
        let out = h.into_sorted_desc();
        assert_eq!(out.len(), 3);
        assert_eq!(out[0].score, 20.0);
        assert_eq!(out[1].score, 10.0);
        assert_eq!(out[2].score, 5.0);
    }

    #[test]
    fn bounded_top_k_lower_score_rejected_at_capacity() {
        let mut h = BoundedTopK::new(2);
        h.offer(100.0, &[]);
        h.offer(50.0, &[]);
        // Below current worst (50) — rejected without allocating.
        h.offer(10.0, &[]);
        let out = h.into_sorted_desc();
        assert_eq!(out.len(), 2);
        assert_eq!(out[0].score, 100.0);
        assert_eq!(out[1].score, 50.0);
    }

    #[test]
    fn bounded_top_k_actions_preserved() {
        // Smoke-check that the action payload rides through the heap intact.
        let mut h = BoundedTopK::new(2);
        let a = vec![MechAction {
            mech_uid: 7,
            mech_type: "PunchMech".to_string(),
            move_to: (3, 4),
            weapon: WId::None,
            target: (3, 4),
            target2: None,
            description: "test".to_string(),
        }];
        h.offer(5.0, &a);
        let out = h.into_sorted_desc();
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].actions.len(), 1);
        assert_eq!(out[0].actions[0].mech_uid, 7);
        assert_eq!(out[0].actions[0].move_to, (3, 4));
    }

    #[test]
    #[should_panic(expected = "BoundedTopK capacity must be >= 1")]
    fn bounded_top_k_rejects_zero_capacity() {
        // k=0 is meaningless and would break the peek-when-full branch.
        let _ = BoundedTopK::new(0);
    }
}
