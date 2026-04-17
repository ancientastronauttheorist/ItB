use pyo3::prelude::*;

pub mod types;
pub mod board;
pub mod weapons;
pub mod movement;
pub mod simulate;
pub mod enemy;
pub mod evaluate;
pub mod solver;
pub mod serde_bridge;

/// Solve a turn given bridge JSON data.
///
/// Input: JSON string (bridge state format) + time limit in seconds.
/// Output: JSON string with solution (actions, score, stats).
#[pyfunction]
fn solve(py: Python<'_>, json_input: &str, time_limit: f64) -> PyResult<String> {
    // Release the GIL for the entire Rust computation
    py.allow_threads(|| {
        let (board, spawn_points, _danger_tiles, weights) = serde_bridge::board_from_json(json_input)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;
        let solution = solver::solve_turn(
            &board,
            &spawn_points,
            time_limit,
            99999, // no pruning — Rust is fast enough to search exhaustively
            &weights,
        );

        Ok(serde_bridge::solution_to_json(&solution))
    })
}

/// Score a specific plan of actions against the bridge state.
///
/// Input: bridge JSON + plan JSON (list of {mech_uid, move_to:[x,y], weapon_id, target:[x,y]}).
/// Output: JSON with Rust's evaluated score + post-enemy summary.
/// Diagnostic only — not used in the normal solve path.
#[pyfunction]
fn score_plan(py: Python<'_>, bridge_json: &str, plan_json: &str) -> PyResult<String> {
    use crate::enemy::simulate_enemy_attacks;
    use crate::evaluate::{evaluate, PsionState};
    use crate::simulate::simulate_action;
    use crate::weapons::wid_from_str;
    use crate::types::{Terrain, xy_to_idx};

    py.allow_threads(|| {
        let (mut board, spawn_points, _danger, weights) = serde_bridge::board_from_json(bridge_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;

        #[derive(serde::Deserialize)]
        struct PlanAction {
            mech_uid: u16,
            move_to: [u8; 2],
            weapon_id: String,
            target: [u8; 2],
        }
        let plan: Vec<PlanAction> = serde_json::from_str(plan_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("plan parse: {}", e)))?;

        // Snapshot original positions (indexed by unit slot) for re-aim logic.
        // Matches solver::solve_turn's layout.
        let mut original_positions = [(0u8, 0u8); 16];
        for i in 0..board.unit_count as usize {
            original_positions[i] = (board.units[i].x, board.units[i].y);
        }
        let psion_before = PsionState::capture(&board);
        let buildings_before = board.tiles.iter()
            .filter(|t| t.terrain == crate::types::Terrain::Building && t.building_hp > 0)
            .count() as i32;

        let mut kills = 0i32;
        let mut bumps = 0i32;
        for act in &plan {
            let mech_idx = board.units.iter().position(|u| u.uid == act.mech_uid && u.alive());
            let mech_idx = match mech_idx {
                Some(i) => i,
                None => continue,
            };
            let wid = wid_from_str(&act.weapon_id);
            let result = simulate_action(
                &mut board, mech_idx,
                (act.move_to[0], act.move_to[1]),
                wid,
                (act.target[0], act.target[1]),
            );
            kills += result.enemies_killed as i32;
            bumps += result.buildings_bump_damaged as i32;
        }

        let buildings_mid = board.tiles.iter()
            .filter(|t| t.terrain == crate::types::Terrain::Building && t.building_hp > 0)
            .count() as i32;

        let _ = simulate_enemy_attacks(&mut board, &original_positions);

        let buildings_after = board.tiles.iter()
            .filter(|t| t.terrain == crate::types::Terrain::Building && t.building_hp > 0)
            .count() as i32;
        let mechs_alive = board.units.iter()
            .filter(|u| u.is_player() && u.is_mech() && u.hp > 0)
            .count() as i32;
        let judo_hp = board.units.iter()
            .find(|u| u.type_name_str() == "JudoMech")
            .map(|u| u.hp as i32)
            .unwrap_or(-1);

        // Recompute building_threats from the ORIGINAL (pre-action) board state
        // so threats_cleared / perfect_defense_bonus kick in correctly.
        let (mut board_orig, _, _, _) = serde_bridge::board_from_json(bridge_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;
        let _ = &mut board_orig; // silence unused_mut if not mutated
        let mut building_threats = 0u64;
        for i in 0..board_orig.unit_count as usize {
            let u = &board_orig.units[i];
            if !u.is_enemy() || !u.alive() || u.queued_target_x < 0 { continue; }
            let tx = u.queued_target_x as u8;
            let ty = u.queued_target_y as u8;
            let tile = board_orig.tile(tx, ty);
            if tile.terrain == Terrain::Building && tile.building_hp > 0 {
                building_threats |= 1u64 << xy_to_idx(tx, ty);
            }
        }
        let score = evaluate(&board, &spawn_points, &weights, kills, bumps, &psion_before, building_threats);

        // Count components for debugging
        let bldgs_alive = board.tiles.iter().filter(|t| t.terrain == Terrain::Building && t.building_hp > 0).count() as i32;
        let bldg_hp_total: i32 = board.tiles.iter().filter(|t| t.terrain == Terrain::Building).map(|t| t.building_hp as i32).sum();
        let dead_mechs = board.units.iter().filter(|u| u.is_player() && u.is_mech() && u.hp == 0).count() as i32;
        let alive_mechs = board.units.iter().filter(|u| u.is_player() && u.is_mech() && u.hp > 0).count() as i32;
        let alive_mech_hp: i32 = board.units.iter().filter(|u| u.is_player() && u.is_mech()).map(|u| u.hp as i32).sum();

        let out = serde_json::json!({
            "score": score,
            "buildings_before": buildings_before,
            "buildings_after_player": buildings_mid,
            "buildings_after_enemy": buildings_after,
            "buildings_destroyed_by_enemies": buildings_mid - buildings_after,
            "grid_power": board.grid_power,
            "mechs_alive": mechs_alive,
            "judo_hp": judo_hp,
            "kills": kills,
            "bldgs_alive": bldgs_alive,
            "bldg_hp_total": bldg_hp_total,
            "dead_mechs": dead_mechs,
            "alive_mech_hp": alive_mech_hp,
            "current_turn": board.current_turn,
            "total_turns": board.total_turns,
            "remaining_spawns": board.remaining_spawns,
            "building_threats_bits": format!("{:b}", building_threats),
            "building_bumps": bumps,
        });
        Ok(out.to_string())
    })
}

#[pymodule]
fn itb_solver(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(solve, m)?)?;
    m.add_function(wrap_pyfunction!(score_plan, m)?)?;
    Ok(())
}
