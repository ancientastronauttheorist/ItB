/// Board evaluation function for the solver.
///
/// Scores a board position: buildings, grid power, enemies, mechs, spawns, pods.
/// Higher score = better for the player.
///
/// Turn-aware scoring: weights scale based on turns remaining.
/// Kills are worth MORE on early turns (prevent future attacks) and LESS on
/// the final turn (no future to protect). Buildings never scale (always critical).

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

#[derive(Clone, Debug)]
pub struct EvalWeights {
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
}

impl Default for EvalWeights {
    fn default() -> Self {
        EvalWeights {
            building_alive: 10000.0,
            building_hp: 2000.0,
            grid_power: 5000.0,
            enemy_killed: 500.0,
            enemy_hp_remaining: -50.0,
            mech_killed: -8000.0,
            mech_hp: 100.0,
            mech_centrality: -5.0,
            spawn_blocked: 400.0,
            pod_uncollected: -100.0,
            pod_proximity: 50.0,
            enemy_on_danger: 400.0,
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
/// `kills` is passed explicitly because dead enemies are filtered from iteration.
/// `spawn_points` are next turn's Vek spawn locations.
/// `blast_psion_was_active` should be true if the Blast Psion was alive BEFORE
/// mech actions but is now dead (Psion was killed this turn).
pub fn evaluate(
    board: &Board,
    spawn_points: &[(u8, u8)],
    weights: &EvalWeights,
    kills: i32,
    blast_psion_was_active: bool,
    armor_psion_was_active: bool,
) -> f64 {
    let mut score = 0.0;
    let ff = future_factor(board.current_turn, board.total_turns);

    // Grid power urgency multiplier (unchanged — handles grid-level urgency)
    let grid_multiplier = match board.grid_power {
        0..=1 => 5.0,
        2 => 3.0,
        3 => 2.0,
        _ => 1.0,
    };

    // ── Buildings: NO turn scaling (always critical) ────────────────────
    let mut buildings_alive = 0i32;
    let mut total_building_hp = 0i32;
    for tile in &board.tiles {
        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
            buildings_alive += 1;
            total_building_hp += tile.building_hp as i32;
        }
    }
    score += buildings_alive as f64 * weights.building_alive * grid_multiplier;
    score += total_building_hp as f64 * weights.building_hp * grid_multiplier;

    // ── Grid power: NO turn scaling ────────────────────────────────────
    score += board.grid_power as f64 * weights.grid_power;

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

    // ── Blast Psion kill bonus: SCALED by future_factor ─────────────────
    // Killing the Psion prevents death explosions for all remaining turns.
    // Worth more early (more future enemy deaths prevented), zero on final turn.
    if blast_psion_was_active && !board.blast_psion {
        score += 2000.0 * ff;
    }

    // ── Shell Psion kill bonus: removing armor makes all weapons effective ──
    if armor_psion_was_active && !board.armor_psion {
        score += 1500.0 * ff;
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
                score += scaled(weights.mech_killed, ff, 0.30, 0.70);
            }
        }
    }

    // ── Mechs: SCALED (mech loss/HP matters less on final turn) ─────────
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if !u.is_player() { continue; }
        if !u.is_mech() { continue; }

        if u.hp <= 0 {
            // mech_killed = -8000 * (0.30 + 0.70 * ff) → final: -2400
            score += scaled(weights.mech_killed, ff, 0.30, 0.70);
        } else {
            // mech_hp = 100 * (0.20 + 0.80 * ff) → final: 20
            score += u.hp as f64 * scaled(weights.mech_hp, ff, 0.20, 0.80);
            // Centrality: zero on final turn (no future positioning value)
            let cx = (u.x as f64 - 3.5).abs();
            let cy = (u.y as f64 - 3.5).abs();
            score += (cx + cy) * weights.mech_centrality * ff;
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

    #[test]
    fn test_empty_board_score() {
        let board = Board::default();
        let w = EvalWeights::default();
        let score = evaluate(&board, &[], &w, 0, false, false);
        // grid_power=7, no buildings, no units
        assert!((score - 35000.0).abs() < 0.01); // 7 * 5000
    }

    #[test]
    fn test_building_score() {
        let mut board = Board::default();
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 1;
        let w = EvalWeights::default();
        let score = evaluate(&board, &[], &w, 0, false, false);
        // grid_power=7 (multiplier=1.0): 7*5000 + 1*10000 + 1*2000
        assert!((score - 47000.0).abs() < 0.01);
    }

    #[test]
    fn test_kill_scales_with_turn() {
        let w = EvalWeights::default();

        // Turn 1 of 5 (first combat): ff=1.0, kill = 500 * (0.20 + 1.60) = 900
        let mut b1 = Board::default();
        b1.current_turn = 1;
        b1.total_turns = 5;
        let s0 = evaluate(&b1, &[], &w, 0, false, false);
        let s1 = evaluate(&b1, &[], &w, 2, false, false);
        assert!((s1 - s0 - 1800.0).abs() < 1.0); // 2 * 900

        // Final turn (turn 5): ff=0.0, kill = 500 * 0.20 = 100
        let mut b5 = Board::default();
        b5.current_turn = 5;
        b5.total_turns = 5;
        let s0 = evaluate(&b5, &[], &w, 0, false, false);
        let s1 = evaluate(&b5, &[], &w, 2, false, false);
        assert!((s1 - s0 - 200.0).abs() < 1.0); // 2 * 100
    }

    #[test]
    fn test_grid_urgency_multiplier() {
        let mut board = Board::default();
        board.grid_power = 1;
        board.tile_mut(0, 0).terrain = Terrain::Building;
        board.tile_mut(0, 0).building_hp = 1;
        let w = EvalWeights::default();
        let score = evaluate(&board, &[], &w, 0, false, false);
        // grid=1 (5x multiplier): 1*5000 + 1*10000*5 + 1*2000*5 = 5000+50000+10000 = 65000
        assert!((score - 65000.0).abs() < 0.01);
    }

    #[test]
    fn test_spawn_blocked_zero_on_final_turn() {
        let w = EvalWeights::default();
        let mut board = Board::default();
        board.current_turn = 5;
        board.total_turns = 5;
        // Add a mech on a spawn point
        board.add_unit(Unit {
            uid: 0, x: 3, y: 3, hp: 3, max_hp: 3,
            team: Team::Player, move_speed: 3,
            flags: UnitFlags::IS_MECH | UnitFlags::PUSHABLE | UnitFlags::ACTIVE,
            ..Unit::default()
        });
        let with_spawn = evaluate(&board, &[(3, 3)], &w, 0, false, false);
        let without_spawn = evaluate(&board, &[], &w, 0, false, false);
        // On final turn, spawn_blocked * ff = 400 * 0.0 = 0
        assert!((with_spawn - without_spawn).abs() < 1.0);
    }

    #[test]
    fn test_future_factor() {
        // Turn 0 (deployment): ff = 1.0 (clamped, combat_turn=0)
        assert!((future_factor(0, 5) - 1.0).abs() < 0.01);
        // Turn 1 (first combat): ff = 4/4 = 1.0
        assert!((future_factor(1, 5) - 1.0).abs() < 0.01);
        // Turn 3 (mid): ff = 2/4 = 0.5
        assert!((future_factor(3, 5) - 0.5).abs() < 0.01);
        // Turn 5 (final): ff = 0/4 = 0.0
        assert!((future_factor(5, 5) - 0.0).abs() < 0.01);
    }

    #[test]
    fn test_psion_kill_bonus() {
        let w = EvalWeights::default();
        let mut board = Board::default();
        board.current_turn = 1;
        board.total_turns = 5;
        // Psion was active before, now dead
        let with_bonus = evaluate(&board, &[], &w, 0, true, false);
        let without_bonus = evaluate(&board, &[], &w, 0, false, false);
        // bonus = 2000 * ff = 2000 * 1.0 = 2000
        assert!((with_bonus - without_bonus - 2000.0).abs() < 1.0);
    }
}
