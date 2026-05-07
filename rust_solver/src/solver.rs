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
                    if has_unit { path_has_unit = true; }
                    if has_unit || path_has_unit {
                        targets.push((nxu, nyu));
                    } else if wdef.push != PushDir::None {
                        let tile = board.tile(nxu, nyu);
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
                    let is_building = tile.is_building();
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
            let min_r = if wdef.range_min == 0 { 1 } else { wdef.range_min };
            // Fixed-distance leaps (Aerial Bombs: range_min == range_max) fly
            // over a straight cardinal line and land on the target, so the
            // target must share a row or column with the attacker. Variable
            // leaps (Hydraulic Legs) can land anywhere within range.
            let cardinal_only = wdef.range_min > 0 && wdef.range_min == wdef.range_max;
            for x in 0..8u8 {
                for y in 0..8u8 {
                    if cardinal_only && x != mx && y != my { continue; }
                    let dist = (x as i8 - mx as i8).unsigned_abs() + (y as i8 - my as i8).unsigned_abs();
                    if dist < min_r || dist > max_r { continue; }
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
        _ => {} // Passive, Deploy, TwoClick
    }

    targets
}

// ── Action enumeration ───────────────────────────────────────────────────────

type Action = ((u8, u8), WId, (u8, u8)); // (move_to, weapon, target)

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
        WeaponType::Melee => {
            // For path_size>1 melee (Prime_Spear) any unit in the cardinal
            // line from move_to to target counts as an effect — the spear
            // damages every tile it passes through.
            if unit_at(target.0, target.1) { return true; }
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
        let attack_pos = (action_unit.x, action_unit.y);

        // Smoke blocks most pawn actions (attack + repair). Mission_Trapped
        // Decoy Buildings have IgnoreSmoke=true in the Lua mission script, so
        // they can still self-destruct from a smoked tile.
        let tile = action_board.tile(attack_pos.0, attack_pos.1);
        let ignores_smoke = action_unit.type_name_str() == "Trapped_Building";
        if !tile.smoke() || ignores_smoke {
            // Primary weapon — filter out no-op fires (empty space, nothing affected)
            let w1_id = WId::from_raw(action_unit.weapon.0);
            if w1_id != WId::None {
                let mech_from = (unit.x, unit.y);
                for &target in &get_weapon_targets(action_board, attack_pos.0, attack_pos.1, w1_id, mech_from, weapons) {
                    if weapon_action_has_effect(action_board, attack_pos, w1_id, target, weapons) {
                        actions.push((pos, w1_id, target));
                    }
                }
            }

            // Secondary weapon
            let w2_id = WId::from_raw(action_unit.weapon2.0);
            if w2_id != WId::None {
                for &target in &get_weapon_targets(action_board, attack_pos.0, attack_pos.1, w2_id, (unit.x, unit.y), weapons) {
                    if weapon_action_has_effect(action_board, attack_pos, w2_id, target, weapons) {
                        actions.push((pos, w2_id, target));
                    }
                }
            }

            // Repair (if damaged/on_fire/acid/frozen)
            if action_unit.hp < action_unit.max_hp || action_unit.fire() || action_unit.acid() || action_unit.frozen() {
                actions.push((pos, WId::Repair, attack_pos));
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
    let mut scored: Vec<(i32, usize)> = actions.iter().enumerate().map(|(i, &(move_to, weapon_id, target))| {
        let mut s = 0i32;
        let attack_origin = attack_origin_after_move(board, mech_idx, move_to);

        let move_bit = 1u64 << xy_to_idx(attack_origin.0, attack_origin.1);

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
            let wdef = &weapons[weapon_id as usize];
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
    bumps_so_far: i32,
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
        simulate_enemy_attacks(&mut b_eval, original_positions, weapons);
        apply_spawn_blocking(&mut b_eval, spawn_points);
        let raw = evaluate(&b_eval, spawn_points, weights, kills_so_far, bumps_so_far, psion_before, building_threats);
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
        let score = raw - soft_disable_penalty_so_far * penalty_scale;


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
            actions_so_far, kills_so_far, bumps_so_far, soft_disable_penalty_so_far,
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

    for &(move_to, weapon_id, target) in &actions {
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
        let result = simulate_action(&mut b_next, mech_idx, move_to, weapon_id, target, weapons);

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

        let action = make_action(&board.units[mech_idx], move_to, weapon_id, target);
        actions_so_far.push(action);

        search_recursive(
            &b_next, mech_order, depth + 1,
            actions_so_far,
            kills_so_far + result.enemies_killed,
            bumps_so_far + result.buildings_bump_damaged,
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
                &mut actions_buf, 0, 0, 0.0,
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
            simulate_action(&mut b_check, mech_idx, action.move_to, action.weapon, action.target, weapons);
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
            u.is_player() && u.alive() && u.active()
                && (u.is_mech() || u.weapon.0 > 0)
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
            &mut actions_buf, 0, 0, 0.0,
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
