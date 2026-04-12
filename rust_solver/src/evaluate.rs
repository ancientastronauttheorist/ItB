/// Board evaluation function for the solver.
///
/// Scores a board position: buildings, grid power, enemies, mechs, spawns, pods.
/// Higher score = better for the player.
///
/// Turn-aware scoring: weights scale based on turns remaining.
/// Kills are worth MORE on early turns (prevent future attacks) and LESS on
/// the final turn (no future to protect). Buildings never scale (always critical).

use serde::Deserialize;
use crate::types::*;
use crate::board::*;

// ── Turn-aware scaling helpers ──────────────────────────────────────────────

/// Compute future_factor: 1.0 on first combat turn, 0.0 on final turn.
/// current_turn is 0-indexed from bridge (0 = deployment, 1 = first combat).
fn future_factor(current_turn: u8, total_turns: u8) -> f64 {
    if total_turns <= 1 { return 0.0; }
    // Combat turn = current_turn - 1 (turn 0 is deployment)
    // But clamp so we don't go negative
    let combat_turn = if current_turn > 0 { current_turn - 1 } else { 0 };
    let remaining = total_turns.saturating_sub(combat_turn + 1) as f64;
    let max_remaining = (total_turns - 1) as f64;
    (remaining / max_remaining).clamp(0.0, 1.0)
}

/// Scale a weight: base * (floor + scale * future_factor).
/// On first combat turn (ff=1.0): base * (floor + scale)
/// On final turn (ff=0.0): base * floor
#[inline]
fn scaled(base: f64, ff: f64, floor: f64, scale: f64) -> f64 {
    base * (floor + scale * ff)
}

// ── EvalWeights ──────────────────────────────────────────────────────────────

#[derive(Clone, Debug, Deserialize)]
#[serde(default)]
pub struct EvalWeights {
    // Core weights
    pub building_alive: f64,
    pub building_hp: f64,
    pub grid_power: f64,
    pub enemy_killed: f64,
    pub enemy_hp_remaining: f64, // negative
    pub mech_killed: f64,        // negative
    pub mech_hp: f64,
    pub mech_centrality: f64,    // negative (penalizes distance from center)
    pub spawn_blocked: f64,
    pub pod_uncollected: f64,    // negative
    pub pod_proximity: f64,
    pub enemy_on_danger: f64,

    // Psion kill bonuses (scaled by future_factor)
    pub psion_blast: f64,
    pub psion_shell: f64,
    pub psion_soldier: f64,
    pub psion_blood: f64,
    pub psion_tyrant: f64,

    // Status effect bonuses
    pub enemy_on_fire_bonus: f64,    // enemy on fire (will take 1 dmg/turn)
    pub mech_on_acid: f64,           // mech standing on ACID pool (penalty)
    pub friendly_npc_killed: f64,    // non-mech player unit killed (penalty)

    // Grid urgency multipliers (applied to building scores)
    pub grid_urgency_critical: f64,  // grid_power <= 1
    pub grid_urgency_high: f64,      // grid_power == 2
    pub grid_urgency_medium: f64,    // grid_power == 3

    // Achievement-specific (all default 0 — no effect in normal play)
    pub enemy_on_fire: f64,
    pub enemy_pushed_into_enemy: f64,
    pub chain_damage: f64,
    pub smoke_placed: f64,
    pub tiles_frozen: f64,
}

impl Default for EvalWeights {
    fn default() -> Self {
        EvalWeights {
            building_alive: 10000.0,
            building_hp: 2000.0,
            grid_power: 5000.0,
            enemy_killed: 500.0,
            enemy_hp_remaining: -50.0,
            mech_killed: -80000.0,
            mech_hp: 100.0,
            mech_centrality: -5.0,
            spawn_blocked: 400.0,
            pod_uncollected: -100.0,
            pod_proximity: 50.0,
            enemy_on_danger: 400.0,
            // Psion kill bonuses
            psion_blast: 2000.0,
            psion_shell: 1500.0,
            psion_soldier: 1000.0,
            psion_blood: 1600.0,
            psion_tyrant: 2500.0,
            // Status bonuses
            enemy_on_fire_bonus: 100.0,
            mech_on_acid: -200.0,
            friendly_npc_killed: -20000.0,  // 2x building value — never sacrifice NPCs for kills
            // Grid urgency
            grid_urgency_critical: 5.0,
            grid_urgency_high: 3.0,
            grid_urgency_medium: 2.0,
            // Achievement (all zero by default)
            enemy_on_fire: 0.0,
            enemy_pushed_into_enemy: 0.0,
            chain_damage: 0.0,
            smoke_placed: 0.0,
            tiles_frozen: 0.0,
        }
    }
}

// ── evaluate ─────────────────────────────────────────────────────────────────

/// Score a board state. Higher = better.
///
/// Turn-aware: weights for kills, damage, spawns, and mechs scale with
/// `future_factor` (1.0 on first combat turn, 0.0 on final turn).
/// Building and grid_power weights never scale (always critical).
///
/// Snapshot of Psion state before mech actions.
#[derive(Clone, Debug, Default)]
pub struct PsionState {
    pub blast: bool,
    pub armor: bool,
    pub soldier: bool,
    pub regen: bool,
    pub tyrant: bool,
}

impl PsionState {
    pub fn capture(board: &Board) -> Self {
        PsionState {
            blast: board.blast_psion,
            armor: board.armor_psion,
            soldier: board.soldier_psion,
            regen: board.regen_psion,
            tyrant: board.tyrant_psion,
        }
    }
}

/// `kills` is passed explicitly because dead enemies are filtered from iteration.
/// `spawn_points` are next turn's Vek spawn locations.
/// `psion_before`: snapshot of Psion state before mech actions — used to detect kills.
pub fn evaluate(
    board: &Board,
    spawn_points: &[(u8, u8)],
    weights: &EvalWeights,
    kills: i32,
    psion_before: &PsionState,
) -> f64 {
    // Game over: grid power depleted — worst possible score
    if board.grid_power == 0 {
        return -999999.0;
    }

    let mut score = 0.0;
    let ff = future_factor(board.current_turn, board.total_turns);

    // Grid power urgency multiplier (from weights)
    let grid_multiplier = match board.grid_power {
        0..=1 => weights.grid_urgency_critical,
        2 => weights.grid_urgency_high,
        3 => weights.grid_urgency_medium,
        _ => 1.0,
    };

    // ── Buildings: NO turn scaling, NO urgency multiplier ────────────────
    // Urgency multiplier was previously applied here but caused an inversion:
    // 4 buildings at critical (5x) scored higher than 6 buildings at normal (1x).
    // Now buildings always use base weight — more buildings always beats fewer.
    let mut buildings_alive = 0i32;
    let mut total_building_hp = 0i32;
    for tile in &board.tiles {
        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
            buildings_alive += 1;
            total_building_hp += tile.building_hp as i32;
        }
    }
    score += buildings_alive as f64 * weights.building_alive;
    score += total_building_hp as f64 * weights.building_hp;

    // ── Grid power: urgency multiplier applied here ───────────────────
    // When grid is low, each grid point is worth more — this incentivizes
    // protecting buildings at low grid without the inversion bug.
    score += board.grid_power as f64 * weights.grid_power * grid_multiplier;

    // ── Enemies: SCALED (kills worth more early, less on final turn) ────
    // kill_value = 500 * (0.20 + 1.60 * ff) → turn 1: 900, mid: 500, final: 100
    score += kills as f64 * scaled(weights.enemy_killed, ff, 0.20, 1.60);
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.is_enemy() && u.alive() {
            // damage_value = -50 * (0.10 + 0.90 * ff) → final: -5
            score += u.hp as f64 * scaled(weights.enemy_hp_remaining, ff, 0.10, 0.90);
        }
    }

    // ── Psion kill bonuses: SCALED by future_factor (from weights) ──────
    if psion_before.blast && !board.blast_psion {
        score += weights.psion_blast * ff;
    }
    if psion_before.armor && !board.armor_psion {
        score += weights.psion_shell * ff;
    }
    if psion_before.soldier && !board.soldier_psion {
        score += weights.psion_soldier * ff;
    }
    if psion_before.regen && !board.regen_psion {
        score += weights.psion_blood * ff;
    }
    if psion_before.tyrant && !board.tyrant_psion {
        score += weights.psion_tyrant * ff;
    }

    // ── Environment danger: enemy scaled like kills, mech like mech_killed ─
    if board.env_danger != 0 {
        for i in 0..board.unit_count as usize {
            let u = &board.units[i];
            if !u.alive() { continue; }
            if !board.is_env_danger(u.x, u.y) { continue; }
            if u.flying() { continue; }

            if u.is_enemy() {
                score += scaled(weights.enemy_on_danger, ff, 0.20, 1.60);
            } else if u.is_player() {
                // Dead is dead — no future_factor scaling for mech loss
                score += weights.mech_killed;
            }
        }
    }

    // ── Enemies on fire: SCALED (will take 1 damage next turn) ─────────
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.is_enemy() && u.alive() && u.fire() {
            score += scaled(weights.enemy_on_fire_bonus, ff, 0.5, 0.5);
        }
    }

    // ── Mechs: SCALED (mech loss/HP matters less on final turn) ─────────
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if !u.is_player() { continue; }

        if !u.is_mech() {
            // Non-mech player units (ArchiveArtillery, Filler_Pawn, etc.)
            // Killing them loses a body-blocker and often involves pushing
            // them into buildings. Penalize to prevent sacrifice.
            if u.hp <= 0 {
                score += weights.friendly_npc_killed;
            }
            continue;
        }

        if u.hp <= 0 {
            // Dead is dead — pilot loss is permanent, no future_factor scaling
            score += weights.mech_killed;
        } else {
            score += u.hp as f64 * scaled(weights.mech_hp, ff, 0.20, 0.80);
            let cx = (u.x as f64 - 3.5).abs();
            let cy = (u.y as f64 - 3.5).abs();
            score += (cx + cy) * weights.mech_centrality * ff;

            // ACID tile avoidance: penalize mech on ACID pool
            let tile = board.tile(u.x, u.y);
            if tile.acid() && tile.terrain != Terrain::Water {
                score += scaled(weights.mech_on_acid, ff, 0.50, 0.50);
            }
        }
    }

    // ── Spawns blocked: SCALED (zero on final turn — no next-turn spawns) ─
    for &(sx, sy) in spawn_points {
        if board.unit_at(sx, sy).is_some() {
            score += weights.spawn_blocked * ff;
        }
    }

    // ── Pods: NO turn scaling ──────────────────────────────────────────
    for idx in 0..64 {
        let tile = &board.tiles[idx];
        if tile.has_pod() {
            score += weights.pod_uncollected;
            let (px, py) = idx_to_xy(idx);
            for i in 0..board.unit_count as usize {
                let u = &board.units[i];
                if u.is_player() && u.is_mech() && u.alive() {
                    let dist = (u.x as i32 - px as i32).abs() + (u.y as i32 - py as i32).abs();
                    if dist <= 2 {
                        score += weights.pod_proximity;
                    }
                }
            }
        }
    }

    score
}

#[cfg(test)]
mod tests {
    use super::*;

    fn no_psion() -> PsionState { PsionState::default() }

    #[test]
    fn test_empty_board_score() {
        let board = Board::default();
        let w = EvalWeights::default();
        let score = evaluate(&board, &[], &w, 0, &no_psion());
        assert!((score - 35000.0).abs() < 0.01);
    }

    #[test]
    fn test_building_score() {
        let mut board = Board::default();
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 1;
        let w = EvalWeights::default();
        let score = evaluate(&board, &[], &w, 0, &no_psion());
        assert!((score - 47000.0).abs() < 0.01);
    }

    #[test]
    fn test_kill_scales_with_turn() {
        let w = EvalWeights::default();
        let p = no_psion();
        let mut b1 = Board::default();
        b1.current_turn = 1;
        b1.total_turns = 5;
        let s0 = evaluate(&b1, &[], &w, 0, &p);
        let s1 = evaluate(&b1, &[], &w, 2, &p);
        assert!((s1 - s0 - 1800.0).abs() < 1.0);

        let mut b5 = Board::default();
        b5.current_turn = 5;
        b5.total_turns = 5;
        let s0 = evaluate(&b5, &[], &w, 0, &p);
        let s1 = evaluate(&b5, &[], &w, 2, &p);
        assert!((s1 - s0 - 200.0).abs() < 1.0);
    }

    #[test]
    fn test_grid_urgency_multiplier() {
        let mut board = Board::default();
        board.grid_power = 1;
        board.tile_mut(0, 0).terrain = Terrain::Building;
        board.tile_mut(0, 0).building_hp = 1;
        let w = EvalWeights::default();
        let score = evaluate(&board, &[], &w, 0, &no_psion());
        assert!((score - 65000.0).abs() < 0.01);
    }

    #[test]
    fn test_spawn_blocked_zero_on_final_turn() {
        let w = EvalWeights::default();
        let mut board = Board::default();
        board.current_turn = 5;
        board.total_turns = 5;
        board.add_unit(Unit {
            uid: 0, x: 3, y: 3, hp: 3, max_hp: 3,
            team: Team::Player, move_speed: 3,
            flags: UnitFlags::IS_MECH | UnitFlags::PUSHABLE | UnitFlags::ACTIVE,
            ..Unit::default()
        });
        let with_spawn = evaluate(&board, &[(3, 3)], &w, 0, &no_psion());
        let without_spawn = evaluate(&board, &[], &w, 0, &no_psion());
        assert!((with_spawn - without_spawn).abs() < 1.0);
    }

    #[test]
    fn test_future_factor() {
        assert!((future_factor(0, 5) - 1.0).abs() < 0.01);
        assert!((future_factor(1, 5) - 1.0).abs() < 0.01);
        assert!((future_factor(3, 5) - 0.5).abs() < 0.01);
        assert!((future_factor(5, 5) - 0.0).abs() < 0.01);
    }

    #[test]
    fn test_psion_kill_bonus() {
        let w = EvalWeights::default();
        let mut board = Board::default();
        board.current_turn = 1;
        board.total_turns = 5;
        // Blast Psion was active before, now dead
        let p_blast = PsionState { blast: true, ..Default::default() };
        let with_bonus = evaluate(&board, &[], &w, 0, &p_blast);
        let without_bonus = evaluate(&board, &[], &w, 0, &no_psion());
        assert!((with_bonus - without_bonus - 2000.0).abs() < 1.0);
    }

    #[test]
    fn test_tyrant_psion_kill_bonus() {
        let w = EvalWeights::default();
        let mut board = Board::default();
        board.current_turn = 1;
        board.total_turns = 5;
        let p_tyrant = PsionState { tyrant: true, ..Default::default() };
        let with = evaluate(&board, &[], &w, 0, &p_tyrant);
        let without = evaluate(&board, &[], &w, 0, &no_psion());
        assert!((with - without - 2500.0).abs() < 1.0);
    }
}
