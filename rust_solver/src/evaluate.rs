/// Board evaluation function for the solver.
///
/// Scores a board position: buildings, grid power, enemies, mechs, spawns, pods.
/// Higher score = better for the player.

use crate::types::*;
use crate::board::*;

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
/// `kills` is passed explicitly because dead enemies are filtered from iteration.
/// `spawn_points` are next turn's Vek spawn locations.
pub fn evaluate(
    board: &Board,
    spawn_points: &[(u8, u8)],
    weights: &EvalWeights,
    kills: i32,
) -> f64 {
    let mut score = 0.0;

    // Grid power urgency multiplier
    let grid_multiplier = match board.grid_power {
        0..=1 => 5.0,
        2 => 3.0,
        3 => 2.0,
        _ => 1.0,
    };

    // Buildings (highest priority, scaled by urgency)
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

    // Grid power
    score += board.grid_power as f64 * weights.grid_power;

    // Enemies
    score += kills as f64 * weights.enemy_killed;
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.is_enemy() && u.alive() {
            score += u.hp as f64 * weights.enemy_hp_remaining;
        }
    }

    // Environment danger
    if board.env_danger != 0 {
        for i in 0..board.unit_count as usize {
            let u = &board.units[i];
            if !u.alive() { continue; }
            if !board.is_env_danger(u.x, u.y) { continue; }
            if u.flying() { continue; }

            if u.is_enemy() {
                score += weights.enemy_on_danger;
            } else if u.is_player() {
                score += weights.mech_killed; // very harsh penalty
            }
        }
    }

    // Mechs
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if !u.is_player() { continue; }
        if !u.is_mech() { continue; }

        if u.hp <= 0 {
            score += weights.mech_killed;
        } else {
            score += u.hp as f64 * weights.mech_hp;
            // Centrality: distance from board center (3.5, 3.5)
            let cx = (u.x as f64 - 3.5).abs();
            let cy = (u.y as f64 - 3.5).abs();
            score += (cx + cy) * weights.mech_centrality;
        }
    }

    // Spawns blocked
    for &(sx, sy) in spawn_points {
        if board.unit_at(sx, sy).is_some() {
            score += weights.spawn_blocked;
        }
    }

    // Pods
    for idx in 0..64 {
        let tile = &board.tiles[idx];
        if tile.has_pod() {
            score += weights.pod_uncollected;
            let (px, py) = idx_to_xy(idx);
            // Bonus if mech within 2 tiles
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
        let score = evaluate(&board, &[], &w, 0);
        // grid_power=7, no buildings, no units
        assert!((score - 35000.0).abs() < 0.01); // 7 * 5000
    }

    #[test]
    fn test_building_score() {
        let mut board = Board::default();
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 1;
        let w = EvalWeights::default();
        let score = evaluate(&board, &[], &w, 0);
        // grid_power=7 (multiplier=1.0): 7*5000 + 1*10000 + 1*2000
        assert!((score - 47000.0).abs() < 0.01);
    }

    #[test]
    fn test_kill_bonus() {
        let board = Board::default();
        let w = EvalWeights::default();
        let s0 = evaluate(&board, &[], &w, 0);
        let s1 = evaluate(&board, &[], &w, 2);
        assert!((s1 - s0 - 1000.0).abs() < 0.01); // 2 * 500
    }

    #[test]
    fn test_grid_urgency_multiplier() {
        let mut board = Board::default();
        board.grid_power = 1;
        board.tile_mut(0, 0).terrain = Terrain::Building;
        board.tile_mut(0, 0).building_hp = 1;
        let w = EvalWeights::default();
        let score = evaluate(&board, &[], &w, 0);
        // grid=1 (5x multiplier): 1*5000 + 1*10000*5 + 1*2000*5 = 5000+50000+10000 = 65000
        assert!((score - 65000.0).abs() < 0.01);
    }
}
