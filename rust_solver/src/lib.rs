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
pub mod turn_projection;
pub mod beam;
pub mod replay;

/// Solve a turn given bridge JSON data.
///
/// Input: JSON string (bridge state format) + time limit in seconds.
/// Output: JSON string with solution (actions, score, stats).
#[pyfunction]
fn solve(py: Python<'_>, json_input: &str, time_limit: f64) -> PyResult<String> {
    // Release the GIL for the entire Rust computation
    py.allow_threads(|| {
        let (board, spawn_points, _danger_tiles, weights, disabled_mask, overlay_entries) =
            serde_bridge::board_from_json(json_input)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;

        // Build overlay table only when overrides are present; empty overlay
        // returns None so the solve reuses the compile-time WEAPONS directly.
        let overlay_pairs: Vec<(weapons::WId, weapons::PartialWeaponDef)> =
            overlay_entries.iter()
                .map(|e| (e.wid, e.patch.clone()))
                .collect();
        let overlay_table = weapons::build_overlay_table(&overlay_pairs);
        let weapons_table: &weapons::WeaponTable = match &overlay_table {
            Some(t) => &**t,
            None => &weapons::WEAPONS,
        };

        let solution = solver::solve_turn(
            &board,
            &spawn_points,
            time_limit,
            99999, // no pruning — Rust is fast enough to search exhaustively
            &weights,
            disabled_mask,
            weapons_table,
        );

        Ok(serde_bridge::solution_to_json(&solution, &overlay_entries))
    })
}

/// Score a specific plan of actions against the bridge state.
///
/// Input: bridge JSON + plan JSON (list of {mech_uid, move_to:[x,y], weapon_id, target:[x,y]}).
/// Output: JSON with Rust's evaluated score + post-enemy summary.
/// Diagnostic only — not used in the normal solve path.
#[pyfunction]
fn score_plan(py: Python<'_>, bridge_json: &str, plan_json: &str) -> PyResult<String> {
    use crate::enemy::{apply_spawn_blocking, simulate_enemy_attacks};
    use crate::evaluate::{consumed_spawn_block_bonus, evaluate, PsionState};
    use crate::movement::illegal_move_reason;
    use crate::board::count_unit_deaths_between;
    use crate::simulate::simulate_action_with_target2;
    use crate::solver::{
        arachnoid_spawns_from_events,
        core_of_the_earth_chasm_falls_from_events,
        efficient_explosives_from_events,
        lets_walk_control_distance_from_events,
        reverse_thrusters_four_damage_from_events,
        viscera_nanobots_heal_from_events,
        working_together_from_events,
    };
    use crate::weapons::wid_from_str;
    use crate::types::{Terrain, xy_to_idx};

    py.allow_threads(|| {
        let (mut board, spawn_points, _danger, weights, _disabled_mask, overlay_entries) =
            serde_bridge::board_from_json(bridge_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;

        let overlay_pairs: Vec<(weapons::WId, weapons::PartialWeaponDef)> =
            overlay_entries.iter().map(|e| (e.wid, e.patch.clone())).collect();
        let overlay_table = weapons::build_overlay_table(&overlay_pairs);
        let weapons_table: &weapons::WeaponTable = match &overlay_table {
            Some(t) => &**t,
            None => &weapons::WEAPONS,
        };

        #[derive(serde::Deserialize)]
        struct PlanAction {
            mech_uid: u16,
            move_to: [u8; 2],
            weapon_id: String,
            target: [u8; 2],
            #[serde(default)]
            target2: Option<[u8; 2]>,
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
        let mut mission_kills = 0i32;
        let mut unit_deaths = 0i32;
        let mut bumps = 0i32;
        let mut nanobots_heal = 0i32;
        let mut stay_with_me_heal = 0i32;
        let mut reverse_thrusters_four_damage = 0i32;
        let mut arachnoid_spawns = 0i32;
        let mut efficient_explosives = 0i32;
        let mut working_together = 0i32;
        let mut lets_walk_control_distance = 0i32;
        let mut core_of_the_earth_chasm_falls = 0i32;
        let mut illegal_events: Vec<String> = Vec::new();
        for act in &plan {
            let mech_idx = board.units.iter().position(|u| u.uid == act.mech_uid && u.alive());
            let mech_idx = match mech_idx {
                Some(i) => i,
                None => continue,
            };
            let wid = wid_from_str(&act.weapon_id);
            if let Some(reason) = illegal_move_reason(&board, mech_idx, (act.move_to[0], act.move_to[1])) {
                illegal_events.push(format!(
                    "illegal_move:{}:{}:{}",
                    act.move_to[0], act.move_to[1], reason
                ));
                continue;
            }
            let before_action = board.clone();
            let result = simulate_action_with_target2(
                &mut board, mech_idx,
                (act.move_to[0], act.move_to[1]),
                wid,
                (act.target[0], act.target[1]),
                act.target2.map(|t| (t[0], t[1])),
                weapons_table,
            );
            unit_deaths += count_unit_deaths_between(&before_action, &board);
            for event in result.events.iter().filter(|e| e.starts_with("illegal_")) {
                illegal_events.push(event.clone());
            }
            nanobots_heal += viscera_nanobots_heal_from_events(&result.events);
            stay_with_me_heal += result.mech_hp_repaired;
            reverse_thrusters_four_damage +=
                reverse_thrusters_four_damage_from_events(&result.events);
            arachnoid_spawns += arachnoid_spawns_from_events(&result.events);
            efficient_explosives += efficient_explosives_from_events(&result.events);
            working_together += working_together_from_events(&result.events);
            lets_walk_control_distance += lets_walk_control_distance_from_events(&result.events);
            core_of_the_earth_chasm_falls +=
                core_of_the_earth_chasm_falls_from_events(&result.events);
            kills += result.enemies_killed as i32;
            mission_kills += result.mission_kills as i32;
            bumps += result.buildings_bump_damaged as i32;
        }

        let buildings_mid = board.tiles.iter()
            .filter(|t| t.terrain == crate::types::Terrain::Building && t.building_hp > 0)
            .count() as i32;

        let before_enemy_phase = board.clone();
        let enemy_phase_result = simulate_enemy_attacks(&mut board, &original_positions, weapons_table);
        unit_deaths += count_unit_deaths_between(&before_enemy_phase, &board);
        let before_spawn_block = board.clone();
        let spawn_block_result = apply_spawn_blocking(&mut board, &spawn_points);
        unit_deaths += count_unit_deaths_between(&before_spawn_block, &board);
        kills += enemy_phase_result.enemies_killed + spawn_block_result.enemies_killed;
        mission_kills += enemy_phase_result.mission_kills + spawn_block_result.mission_kills;

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
        let (mut board_orig, _, _, _, _, _) = serde_bridge::board_from_json(bridge_json)
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
        let score = evaluate(&board, &spawn_points, &weights, kills, mission_kills, bumps, &psion_before, building_threats)
            + consumed_spawn_block_bonus(&board, &spawn_points, &weights, spawn_block_result.spawns_blocked)
            + nanobots_heal as f64 * weights.viscera_nanobots_heal_bonus
            + stay_with_me_heal as f64 * weights.stay_with_me_heal_bonus
            + reverse_thrusters_four_damage as f64
                * weights.reverse_thrusters_four_damage_bonus
            + arachnoid_spawns as f64 * weights.arachnoid_spawn_bonus
            + efficient_explosives as f64 * weights.efficient_explosives_bonus
            + working_together as f64 * weights.working_together_bonus
            + lets_walk_control_distance as f64 * weights.lets_walk_control_distance_bonus
            + core_of_the_earth_chasm_falls as f64 * weights.core_of_the_earth_bonus
            + if unit_deaths >= 7 {
                unit_deaths as f64 * weights.no_survivors_death_bonus
            } else {
                0.0
            };

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
            "player_grid_save_expected": board.player_grid_save_expected,
            "enemy_grid_save_expected": board.enemy_grid_save_expected,
            "mechs_alive": mechs_alive,
            "judo_hp": judo_hp,
            "kills": kills,
            "mission_kills": mission_kills,
            "unit_deaths": unit_deaths,
            "arachnoid_spawns": arachnoid_spawns,
            "efficient_explosives": efficient_explosives,
            "working_together": working_together,
            "core_of_the_earth_chasm_falls": core_of_the_earth_chasm_falls,
            "stay_with_me_heal": stay_with_me_heal,
            "bldgs_alive": bldgs_alive,
            "bldg_hp_total": bldg_hp_total,
            "dead_mechs": dead_mechs,
            "alive_mech_hp": alive_mech_hp,
            "current_turn": board.current_turn,
            "total_turns": board.total_turns,
            "remaining_spawns": board.remaining_spawns,
            "building_threats_bits": format!("{:b}", building_threats),
            "building_bumps": bumps,
            "viscera_nanobots_heal": nanobots_heal,
            "spawns_blocked": spawn_block_result.spawns_blocked,
            "illegal_events": illegal_events,
        });
        Ok(out.to_string())
    })
}

/// Project a plan (sequence of mech actions) forward one full turn:
/// apply mech actions, simulate enemy phase, reset mechs for the next turn.
///
/// Input: bridge JSON (board state) + plan JSON (array of action objects,
///   same shape as `score_plan`'s plan input).
/// Output: JSON string with:
///   - `board_json`: projected board in bridge-compatible format (can be
///     passed directly to `solve` / `solve_top_k` for depth-2 beam).
///   - `action_result`: aggregate outcome of the mech actions + enemy phase
///     (enemies_killed, mechs_killed, buildings_lost, grid_damage, ...).
///   - `spawn_points`: spawn tile list forwarded from the input board.
///
/// Projection re-queues surviving enemies with the deterministic heuristic in
/// `turn_projection.rs`. The returned `board_json` still injects
/// `eval_weights.pseudo_threat_eval = true` so enemies without heuristic
/// targets remain conservatively penalized by downstream solve calls.
#[pyfunction]
fn project_plan(py: Python<'_>, bridge_json: &str, plan_json: &str) -> PyResult<String> {
    use crate::turn_projection::{project_plan as tp_project_plan, board_to_json};
    use crate::solver::MechAction;
    use crate::weapons::wid_from_str;

    py.allow_threads(|| {
        let (board, spawn_points, _danger, _weights, _disabled_mask, _overlay_entries) =
            serde_bridge::board_from_json(bridge_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;

        let overlay_pairs: Vec<(weapons::WId, weapons::PartialWeaponDef)> =
            _overlay_entries.iter().map(|e| (e.wid, e.patch.clone())).collect();
        let overlay_table = weapons::build_overlay_table(&overlay_pairs);
        let weapons_table: &weapons::WeaponTable = match &overlay_table {
            Some(t) => &**t,
            None => &weapons::WEAPONS,
        };

        #[derive(serde::Deserialize)]
        struct PlanAction {
            mech_uid: u16,
            #[serde(default)]
            mech_type: String,
            move_to: [u8; 2],
            weapon_id: String,
            target: [u8; 2],
            #[serde(default)]
            target2: Option<[u8; 2]>,
        }
        let raw_plan: Vec<PlanAction> = serde_json::from_str(plan_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(
                format!("plan parse: {}", e)))?;

        let actions: Vec<MechAction> = raw_plan.iter().map(|a| MechAction {
            mech_uid: a.mech_uid,
            mech_type: a.mech_type.clone(),
            move_to: (a.move_to[0], a.move_to[1]),
            weapon: wid_from_str(&a.weapon_id),
            target: (a.target[0], a.target[1]),
            target2: a.target2.map(|t| (t[0], t[1])),
            description: String::new(),
        }).collect();

        let (projected, result) = tp_project_plan(&board, &actions, &spawn_points, weapons_table);

        let proj_board_json = board_to_json(&projected, &spawn_points);

        // Aggregate spawning_tiles forward (same as input)
        let spawn_json: Vec<serde_json::Value> = spawn_points.iter()
            .map(|&(x, y)| serde_json::json!([x, y]))
            .collect();

        let out = serde_json::json!({
            "board_json": proj_board_json,
            "spawn_points": spawn_json,
            "action_result": {
                "enemies_killed": result.enemies_killed,
                "mission_kills": result.mission_kills,
                "unit_deaths": result.unit_deaths,
                "mechs_killed": result.mechs_killed,
                "buildings_lost": result.buildings_lost,
                "buildings_damaged": result.buildings_damaged,
                "grid_damage": result.grid_damage,
                "enemy_damage_dealt": result.enemy_damage_dealt,
                "mech_damage_taken": result.mech_damage_taken,
                "mech_hp_repaired": result.mech_hp_repaired,
                "spawns_blocked": result.spawns_blocked,
                "pods_collected": result.pods_collected,
                "repair_platforms_used": result.repair_platforms_used,
            },
            "projected_turn": projected.current_turn,
        });
        Ok(out.to_string())
    })
}

/// Project a plan into a bounded set of plausible next-turn enemy-intent
/// scenarios. Scenario 0 is the same heuristic requeue used by `project_plan`.
/// Additional scenarios retarget one eligible enemy at a high-value reachable
/// building, capped by `max_scenarios`.
#[pyfunction]
fn project_plan_scenarios(
    py: Python<'_>,
    bridge_json: &str,
    plan_json: &str,
    max_scenarios: usize,
) -> PyResult<String> {
    use crate::turn_projection::{
        board_to_json,
        project_plan_scenarios as tp_project_plan_scenarios,
    };
    use crate::solver::MechAction;
    use crate::weapons::wid_from_str;

    py.allow_threads(|| {
        let (board, spawn_points, _danger, _weights, _disabled_mask, _overlay_entries) =
            serde_bridge::board_from_json(bridge_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;

        let overlay_pairs: Vec<(weapons::WId, weapons::PartialWeaponDef)> =
            _overlay_entries.iter().map(|e| (e.wid, e.patch.clone())).collect();
        let overlay_table = weapons::build_overlay_table(&overlay_pairs);
        let weapons_table: &weapons::WeaponTable = match &overlay_table {
            Some(t) => &**t,
            None => &weapons::WEAPONS,
        };

        #[derive(serde::Deserialize)]
        struct PlanAction {
            mech_uid: u16,
            #[serde(default)]
            mech_type: String,
            move_to: [u8; 2],
            weapon_id: String,
            target: [u8; 2],
            #[serde(default)]
            target2: Option<[u8; 2]>,
        }
        let raw_plan: Vec<PlanAction> = serde_json::from_str(plan_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(
                format!("plan parse: {}", e)))?;

        let actions: Vec<MechAction> = raw_plan.iter().map(|a| MechAction {
            mech_uid: a.mech_uid,
            mech_type: a.mech_type.clone(),
            move_to: (a.move_to[0], a.move_to[1]),
            weapon: wid_from_str(&a.weapon_id),
            target: (a.target[0], a.target[1]),
            target2: a.target2.map(|t| (t[0], t[1])),
            description: String::new(),
        }).collect();

        let spawn_json: Vec<serde_json::Value> = spawn_points.iter()
            .map(|&(x, y)| serde_json::json!([x, y]))
            .collect();

        let scenarios = tp_project_plan_scenarios(
            &board,
            &actions,
            &spawn_points,
            weapons_table,
            max_scenarios,
        );
        let scenario_json: Vec<serde_json::Value> = scenarios.iter().map(|s| {
            serde_json::json!({
                "label": s.label,
                "board_json": board_to_json(&s.board, &spawn_points),
                "spawn_points": spawn_json,
                "action_result": {
                    "enemies_killed": s.action_result.enemies_killed,
                    "mission_kills": s.action_result.mission_kills,
                    "unit_deaths": s.action_result.unit_deaths,
                    "mechs_killed": s.action_result.mechs_killed,
                    "buildings_lost": s.action_result.buildings_lost,
                    "buildings_damaged": s.action_result.buildings_damaged,
                    "grid_damage": s.action_result.grid_damage,
                    "enemy_damage_dealt": s.action_result.enemy_damage_dealt,
                    "mech_damage_taken": s.action_result.mech_damage_taken,
                    "mech_hp_repaired": s.action_result.mech_hp_repaired,
                    "spawns_blocked": s.action_result.spawns_blocked,
                    "pods_collected": s.action_result.pods_collected,
                    "repair_platforms_used": s.action_result.repair_platforms_used,
                },
                "projected_turn": s.board.current_turn,
            })
        }).collect();

        Ok(serde_json::json!({ "scenarios": scenario_json }).to_string())
    })
}

/// Top-K solve: returns up to `k` plans sorted by raw score descending.
///
/// Feeds the depth-2+ beam search — each beam level needs ranked candidates
/// to expand. Unlike `solve`, this does NOT apply the two-stage clean-plan
/// filter: the caller wants top-K by raw score, and swapping a lower-score
/// clean plan into slot [0] would violate the sorted-desc contract.
///
/// Output: JSON array of solution objects (same per-entry shape as `solve`).
/// When fewer than `k` unique plans exist, the array is shorter.
#[pyfunction]
fn solve_top_k(py: Python<'_>, json_input: &str, time_limit: f64, k: usize) -> PyResult<String> {
    py.allow_threads(|| {
        let (board, spawn_points, _danger_tiles, weights, disabled_mask, overlay_entries) =
            serde_bridge::board_from_json(json_input)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;

        let overlay_pairs: Vec<(weapons::WId, weapons::PartialWeaponDef)> =
            overlay_entries.iter()
                .map(|e| (e.wid, e.patch.clone()))
                .collect();
        let overlay_table = weapons::build_overlay_table(&overlay_pairs);
        let weapons_table: &weapons::WeaponTable = match &overlay_table {
            Some(t) => &**t,
            None => &weapons::WEAPONS,
        };

        let solutions = solver::solve_turn_top_k(
            &board,
            &spawn_points,
            time_limit,
            99999,
            &weights,
            disabled_mask,
            weapons_table,
            k,
        );

        let json_items: Vec<String> = solutions.iter()
            .map(|sol| serde_bridge::solution_to_json(sol, &overlay_entries))
            .collect();
        // Each solution_to_json is a JSON object; concatenate into an array.
        Ok(format!("[{}]", json_items.join(",")))
    })
}

/// Simulator semantic version. Must be kept in lockstep with
/// Python's ``src/solver/verify.py::SIMULATOR_VERSION``. Bump when
/// simulator behavior changes in a way that invalidates pre-bump
/// predictions (e.g., Storm Generator implemented, Spartan Shield
/// fixed, PushDir::Flip semantics changed). A mismatch between the
/// loaded wheel's value and the Python constant indicates a stale
/// wheel after a rebuild — ``cmd_solve`` rejects it with a clear
/// error so we never run new Python bindings against old Rust code.
// v3 (2026-04-22): pilot passives wired into the simulator. The Python
// constant was bumped at ship time but the Rust side was missed; this
// brings the wheel in line so `_check_wheel_sim_version` stops
// erroring on live cmd_solve. See src/solver/verify.py for the full
// per-bump changelog.
//
// v6 (2026-04-23): catch-up bump. Python was advanced through v4 (Rift
// Walkers mechanics pass), v5 (building HP underflow + Aerial Bombs
// damage + Python smoke parity), and v6 (Brute_Bombrun transit damage)
// without a matching Rust bump each time — live cmd_solve was
// erroring on wheel_sim_version_mismatch. Bringing Rust to v6 clears
// the block. Any future bump MUST edit both constants atomically.
//
// v7 (2026-04-23, grid-drop deep dive): Mirrorshot mountain damage,
// dead-pusher no longer bumps live blocker, non-unique multi-HP
// buildings preserve grid_power on bump. See src/solver/verify.py for
// the full per-bump changelog.
//
// v8 (2026-04-23, Mission_Teleporter): teleporter pad swap now modelled.
// Bridge extracts pad pairs via Board.AddTeleport hook and emits
// `teleporter_pairs`; Rust Board carries them; `apply_teleport_on_land`
// fires at every move-end site (apply_push, apply_throw, sim_charge,
// sim_leap, Swap weapon, mech move) AFTER terrain-kill / mines so
// corpses don't teleport. Closes the silent position desync that caused
// grid loss on run 20260423_131700_144 Disposal Site C (ScienceMech
// predicted E3, actual C3 — exact 2-tile pad swap).
// v14: Cluster Artillery (Ranged_Defensestrike) center-tile damage
// corrected from 0 → 1 in weapons.rs. Matches game behavior where the
// weapon deals 1 damage to the center target tile in addition to the
// 4 adjacent tiles. Surfaced by grid_drop investigation on
// run 20260424_011517_057 t03 (predicted grid=3, actual=4).
// v15: Cracked-ground → Chasm on damage in simulate.rs (was only
// handled for Ice terrain). Unit standing on a damaged cracked-ground
// tile falls in and dies; Massive does NOT save from Chasm. Plus new
// `volatile_enemy_killed` EvalWeights term to preserve Volatile Vek
// (GlowingScorpion) for Weather Watch ⭐ bonus. Surfaced by R.S.T.
// Weather Watch mission, run 20260424_011517_057 turn 1.
// v16: Volatile Vek pattern-match fix. The simulator previously only
// triggered Explosive Decay on units whose type_name contained
// "Volatile_Vek", but the live game uses "GlowingScorpion" as the
// unit class name for the Weather Watch Volatile. Added
// Unit::is_volatile_vek() helper matching both, used by all four
// decay-firing sites in simulate.rs and the Volatile-kill penalty in
// evaluate.rs. Closes the chain-reaction gap that killed LaserMech on
// run 20260424_011517_057 turn 1 (solver didn't predict the decay →
// cracked-C5 → chasm → mech death).
// v17: Non-unique 2-HP building damage is now incremental. Previously
// apply_damage_core treated non-unique buildings as all-or-nothing
// (any damage destroyed the full HP pool), which over-predicted HP
// loss against 2-HP non-objective buildings. Aerial Bombs transit
// damage against F6 (HP=2) predicted destruction, actual took 1 HP
// → survived at HP=1. Fix: always use damage.min(building_hp); the
// is_unique flag now only controls terrain-transition at hp=0
// (objective buildings retain Terrain::Building, regulars become
// Rubble). Mirrors the existing incremental behavior in apply_push.
// Surfaced by grid_drop investigation on run 20260424_144237_364
// turn 1 (snapshots/grid_drop_20260424_144237_364_t01_a1).
// v19 (2026-04-25, flying-on-terrain-conversion env): apply_env_danger
// now spares effectively-flying units on terrain-conversion lethal
// hazards (Tidal Wave, Cataclysm, Seismic). Air Strike / Lightning /
// Satellite Rocket continue to kill flyers. New per-tile bit
// `env_danger_flying_immune` carries the distinction; bridge emits a
// 5th element on each `environment_danger_v2` entry, with an
// `env_type`-based fallback for older recordings. Closes the silent
// "Hornet on Tidal" desync (m04 Artifact Vaults, run 20260425_005049_742)
// where the solver projected a flying enemy dead and wasted a turn,
// letting the live Hornet destroy the Power Generator.
// v20 (2026-04-25, full-pull pull weapons): Brute_Grapple "Grappling
// Hook" and Science_Gravwell "Grav Well" now drag the target ALL the
// way to the tile adjacent to the mech, mirroring the wiki ("pull
// units to the Mech" / "pulls its target towards you... not able to
// pull enemies into the Gravity Mech for bump damage"). Previously
// both used the 1-tile path shared with Science_Pullmech (Attraction
// Pulse), under-predicting the destination by 1 tile per tile of pull
// distance. Encoded via new WeaponFlags::FULL_PULL bit; sim_pull_or_swap
// loops apply_push until the target reaches mech-adjacency, dies, or
// bumps a blocker. Science_Pullmech remains 1-tile (correctly per wiki).
// Also fixes BruteGrapple display name "Vice Fist" → "Grappling Hook"
// (Vice Fist is Prime_Shift's name).
//
// v21 (2026-04-25, mission-aware "do not kill X" bonus penalty):
//   The `volatile_enemy_killed` evaluator term used to fire
//   unconditionally on every Volatile_Vek / GlowingScorpion kill,
//   regardless of the active mission's BonusObjs. New
//   `Board::bonus_dont_kill_types: Vec<String>` populated from
//   `JsonInput::bonus_objective_unit_types` gates the penalty per
//   mission. Empty list (most missions) = penalty no-ops. Python
//   side resolves via `data/mission_bonus_objectives.json` keyed by
//   mission_id, with a future Lua-bridge precedence path already
//   wired (TODO comment in modloader.lua). Surfaced by the
//   20260425_185532_218 Archive Inc loss where boards with a stray
//   GlowingScorpion fired the penalty even though the active mission
//   had no BONUS_PROTECT_X.
// v22 (2026-04-25, WebbEgg → Spiderling hatch sim):
//   The simulator left WebbEgg / SpiderlingEgg units unchanged across
//   the enemy phase, while the live game transforms them into live
//   Spiderlings on hatch turn — every spider-bonus mission produced
//   verify_action desyncs and a wall-of-Spiderlings surprise on turn
//   3-4. New hatch step at the start of `simulate_enemy_attacks`
//   (after fire/env_danger so dead eggs don't resurrect) flips
//   WebbEgg1/SpiderlingEgg1 → Spiderling1, WebbEgg2 → Spiderling2,
//   updates move_speed/weapon_id, clears queued_target +
//   HAS_QUEUED_ATTACK so the attack loop's phantom-attack guard
//   `continue`s cleanly (real game: hatchling's bite is turn after
//   hatch). Surfaced by the 20260425_185532_218 Archive Inc loss.
// v23 (2026-04-25, hatch-table corrected against game Lua source):
//   v22 shipped with a hatch table mined from the bestiary doc; we
//   then validated against the actual game scripts and found the doc
//   was wrong:
//     pawns.lua has NO `WebbEgg2` pawn at all — both Spider1 and
//     Spider2 (Alpha) lay a WebbEgg1 (weapons_enemy.lua:760 sets
//     `SpiderAtk1.MyPawn="WebbEgg1"`, and weapons_enemy.lua:815
//     `SpiderAtk2 = SpiderAtk1:new{...}` does not override MyPawn).
//     weapons_enemy.lua:830 `WebeggHatch1.SpiderType="Spiderling1"`
//     means EVERY spider egg hatches into a regular Spiderling1
//     (1 HP, 1 dmg melee), NOT an Alpha Spiderling2.
//   Removed the dead `WebbEgg2 → Spiderling2` branch and its test;
//   added a guard test asserting Alpha-laid eggs hatch to Spiderling1.
//   `SpiderlingEgg1 → Spiderling1` retained as a defensive fallback
//   (not in vanilla pawns.lua but registered in known_types.json from
//   a prior research cycle; mapping to Spiderling1 matches the only
//   WebeggHatch skill). No behavior change on real boards (the bogus
//   branch was unreachable since the bridge never surfaces WebbEgg2)
//   but version bumped because the semantic-mapping table changed.
//   Pre-v23 rows archived to failure_db_snapshot_sim_v22.jsonl.
// v24 (2026-04-25, three player-weapon fixes after Lua audit):
//   - Prime_Spear: Range/PathSize now 2 (was 1). The spear stabs along
//     a 2-tile cardinal path, hitting any in-path unit and the target
//     tile per weapons_prime.lua:792-846. Solver enumerates range-2
//     stabs; sim_melee handles in-path damage before final-tile push.
//   - Brute_Sniper: damage = max(0, min(MaxDamage, dist - 1)) per
//     weapons_brute.lua:969-991. Adjacent shots now correctly deal 0
//     damage; dist=2 -> 1 dmg; dist >= MaxDamage+1 -> MaxDamage.
//     Encoded as a reusable WeaponFlags::DAMAGE_SCALES_WITH_DIST flag.
//   - Brute_Grapple: when target tile has no pawn but is blocked by
//     mountain or intact building, the mech itself charges along the
//     line and stops at target-dir, per weapons_brute.lua:339-389.
//     Previously sim_pull_or_swap silently exited in the no-pawn
//     branch; now self-charges (FULL_PULL gated). No damage to obstacle.
//   Pre-v24 rows archived to failure_db_snapshot_sim_v23.jsonl.
// v25 (2026-04-27, Ice Storm freeze application):
//   Vanilla Env_SnowStorm tiles ("Ice Storm") were misclassified by the bridge
//   as `lightning_or_airstrike` with kill=1 because Env_SnowStorm shares the
//   `LiveEnvironment.Locations` field with Lightning/Air Strike, and the
//   field-signature heuristic in modloader.lua:733 fired before the class-name
//   fallback at line 760 — so Ice Storm tiles came across the wire as
//   instant-kill Deadly Threats. Live consequence: Cryogenic Labs t1 score
//   -158k with predicted_grid=0, mechs avoiding freeze tiles as if they were
//   Air Strike, missing the freeze upside on enemies.
//
//   Bridge fix: class-metatable check (`Env_SnowStorm`) runs BEFORE field
//   signatures and walks the inheritance chain. Vanilla SnowStorm
//   (Acid=false) routes into the new `state.environment_freeze` channel —
//   non-lethal, status-only. NanoStorm (Env_SnowStorm subclass with
//   Acid=true) takes the existing non-lethal env_danger path
//   (kill=0, damage=1). Field signatures stay as fallback for unrecognized
//   classes; SnowStorm's Locations no longer leaks into the lightning branch.
//
//   Simulator: new `Board::env_freeze: u64` bitset. At start of enemy turn
//   (right after env_danger application), every alive unit on a freeze tile
//   gets `Frozen=true`. Shield blocks the freeze and is consumed (ITB shield
//   rule: "blocks one instance of damage + negative effects"). Already-
//   frozen units are idempotent. Buildings and mountains are untouched —
//   Frozen is a unit status. Frozen Vek skip their attacks via the existing
//   `if e.frozen() || e.web() { continue; }` guard, so damage prevention is
//   captured naturally in the post-state.
//
//   Evaluator: small forward-looking `enemy_on_danger`-magnitude reward for
//   non-flying enemies sitting on freeze tiles, signalling "push enemies
//   here" pre-application. Mech-on-freeze cost rides the existing
//   `mech_self_frozen` weight (-12000) — one lost turn, far less bad than
//   the `mech_killed` magnitude that fires on real env_danger non-lethal
//   tiles (sandstorm/wind/nano).
//
//   Wire: new optional `environment_freeze: Vec<[u8;2]>` on JsonInput.
//   Older recordings without the field deserialize with env_freeze=0 — no
//   behavior change on the existing corpus, just unblocks future Pinnacle
//   freeze missions. Pre-v25 rows archived to failure_db_snapshot_sim_v24.jsonl.
//
// v26 (2026-04-27, Science_Gravwell single-tile pull):
//   v20 added FULL_PULL to BOTH Brute_Grapple and Science_Gravwell, citing
//   wiki phrasing "pulls its target towards you... not able to pull enemies
//   into the Gravity Mech for bump damage". The wiki was ambiguous; the game
//   Lua is authoritative. Brute_Grapple uses
//     ret:AddCharge(Board:GetSimplePath(target, p1 + DIR_VECTORS[direction]),
//                   FULL_DELAY)
//   which IS a multi-tile drag → keeps FULL_PULL. But Science_Gravwell's
//   GetSkillEffect (weapons_science.lua:115-124) only does
//     local damage = SpaceDamage(p2, self.Damage, GetDirection(p1 - p2))
//     ret:AddArtillery(damage,"effects/shot_pull_U.png")
//   `SpaceDamage(loc, dmg, push_dir)` is a single 1-tile push — no AddCharge,
//   no path-walk. Gravwell pulls its target ONE tile toward the mech, period.
//   The v20 fix systematically over-predicted pull distance by N-1 tiles per
//   cast; failure_db rows from the 2026-04-27 Pinnacle Robotics run (m13 t03
//   Hornet predicted at (3,3)/hp=1 vs actual (2,3)/hp=2, plus several earlier
//   push_dir / damage_amount desyncs on Science_Gravwell) all match the
//   single-pull reading. Removed FULL_PULL from weapons.rs[41]; new tests
//   `test_science_gravwell_is_single_tile_pull` and
//   `test_science_gravwell_single_pull_long_distance` reproduce m13 t03 and
//   prevent regression. Existing pre-v20 tests (`test_grav_well_pulls_target_
//   toward_attacker`, `test_grav_well_no_pull_into_blocker`) updated to
//   single-pull; obsolete v20 regression check `test_science_gravwell_pulls_
//   to_adjacent` removed. Brute_Grapple unchanged (correctly full-pull per
//   its own AddCharge Lua). Pre-v26 rows archived to
//   failure_db_snapshot_sim_v25.jsonl.
//
// v27 (2026-04-28, queued_target OOB guard):
//   M04 (Old Town) panicked mid-turn with
//   `index out of bounds: the len is 64 but the index is 69` from
//   `enemy.rs::apply_damage` → `Board::tile_mut`. 69 = 8*8 + 5 = (x=8, y=5),
//   off-board on an 8×8 grid. Root cause: bridge reader's
//   `_normalize_queued_targets` rewrites `queued_target` to
//   `(cx + ddx, cy + ddy)` for direction-sane delta, but never bounds-checks
//   the result. A Vek at cx=7 with ddx=+1 produces x=8. The Melee arm and
//   catch-all `_ =>` arm in `apply_enemy_attacks` cast the bogus qtx/qty to
//   `u8` and called `apply_damage` which panicked in `tile_mut`. Same drift
//   crashed Python `board.tile()` in `get_threatened_buildings` and
//   `cmd_read`'s telegraphed-attack scan. Fix: bridge reader nulls
//   off-board normalized targets; Rust Melee + catch-all gain
//   `if qtx<0||qty<0||qtx>=8||qty>=8 { continue; }` matching the existing
//   phantom-attack `continue` style; Python sites bounds-check before
//   `self.tile()`. Defensive fix — affected boards previously crashed
//   before predictions could be compared, so no failure_db rows are
//   invalidated. Pre-v27 corpus archived as
//   `failure_db_snapshot_sim_v26.jsonl` per CLAUDE.md rule 22.
//
// v28 (2026-04-28, infinite-spawn future_factor floor):
//   Corp HQ M05 (Mission_Final / boss-style) defeat: solver returned a
//   no-attack JudoMech G3→G7 plan on the bridge-reported "final" turn
//   because `future_factor` collapsed to 0. On boss / Mission_Infinite
//   missions the bridge reports `total_turns = current_turn` every
//   turn (turn_limit is null in `data/mission_metadata.json`), so
//   ff=0.0 made every kill score 0 (enemy_killed × ff = 0).
//   Fix: Python `src/bridge/reader.py` reads
//   `data/mission_metadata.json` and stamps `is_infinite_spawn=true`
//   on bridge_data when `infinite_spawn` is set or the mission is a
//   `boss_mission` with turn_limit=null. JsonInput passes the flag
//   into `Board::infinite_spawn`, and `evaluate::future_factor` floors
//   the factor at 0.5 when the flag is true (kills still rewarded
//   without overweighting future on a mission with no real "final"
//   turn). `remaining_spawns=0` still wins (genuine end of mission).
//   Rationale: feedback_grid_management.md — "infinite-spawn missions
//   grind grid across many turns". Pre-v28 corpus archived as
//   `failure_db_snapshot_sim_v27.jsonl` per CLAUDE.md rule 22.
//
// v29 (2026-04-28, BlobBoss queued-damage persists):
//   M13 turn 4 (Mission_BlobBoss finale) lost the run when WallMech's
//   Grappling Hook pulled BlobBoss D6→E6 and the simulator predicted no
//   D5 hit, while the real game still applied BlobBossAtk's queued 4
//   damage — the 2-HP Corp Tower fell, grid 2→0, defeat. Per
//   `scripts/missions/bosses/goo.lua:172-187`, BlobBossAtk:GetSkillEffect
//   calls AddQueuedDamage(SpaceDamage(p2, 4)) BEFORE adding the optional
//   move; the queued damage is registered against the target tile and
//   fires next enemy turn regardless of where the boss has been pushed
//   or pulled. Fix: new `WeaponFlags::QUEUED_DAMAGE_PERSISTS`, three new
//   weapon defs (`BlobBossAtk` / `BlobBossAtkMed` / `BlobBossAtkSmall` —
//   all 4-damage Melee with the persists flag), `enemy_weapon_for_type`
//   maps `BlobBoss` / `BlobBossMed` / `BlobBossSmall` to them, and the
//   Melee arm in `apply_enemy_attacks` now skips its `curr_dist > 1`
//   cancel when `wdef.queued_damage_persists()` is set. The OOB bounds
//   check on (qtx, qty) inherited from v27 makes this safe to apply when
//   the attacker is non-adjacent. Pre-v29 corpus archived as
//   `failure_db_snapshot_sim_v28.jsonl` per CLAUDE.md rule 22.
// v30 (2026-04-28) — Mission_Reactivation thaw: at start of each enemy
//   phase, thaw the 2 lowest-uid frozen enemy pawns when
//   `board.mission_id == "Mission_Reactivation"`. Mirrors
//   `Mission_Reactivation:NextTurn` in
//   `scripts/missions/snow/mission_reactivation.lua` lines 50-66 (which
//   uses `random_removal` to thaw 2 pawns/turn). Without this hook the
//   solver thought Lifeless Basin's frozen Vek were permanently inert
//   and under-priced threats to the grid: the proximate cause of the
//   4-grid leak in run 20260425_185532_218 (sim_v29 → sim_v30 fix).
// v31 (2026-04-28) — Pinnacle Bot Leader weapon defs (SnowBossAtk +
//   BossHeal). Per `scripts/missions/bosses/bot.lua`:
//     • SnowBossAtk = SnowartAtk1:new{Damage = 2}  (line 67) — 3-tile T
//       artillery (target + both perpendicular tiles for 2 damage each)
//       per `weapons_snow.lua:120-135`. SnowBossAtk2 = same with damage 4.
//     • BossHeal = SelfTarget:new{...}  (lines 28-41) — when boss is
//       damaged at end of player turn, queues this skill instead of
//       SnowBossAtk; on resolve, applies Shield to self IMMEDIATELY and
//       queues +5 HP / remove-shield for the FOLLOWING enemy turn.
//   Pre-v31 the simulator fell through to the Boss/Leader unknown-enemy
//   fallback (3-dmg single-target Alpha melee), so plans against the Bot
//   Leader mispredicted "deal 3 damage = boss almost dead" while the
//   real game was 2 dmg × 3-tile splash + auto-shield. Implementation:
//     1. Three new WIds (SnowBossAtk=119, SnowBossAtk2=120, BossHeal=121)
//        with proper weapon defs in `rust_solver/src/weapons.rs`.
//     2. `enemy_weapon_for_type`: BotBoss → SnowBossAtk,
//        BotBoss2 → SnowBossAtk2.
//     3. `sim_artillery` (player-side) + the enemy.rs Artillery arm now
//        honor `WeaponFlags::AOE_PERP` (previously only `sim_melee` and the
//        Projectile arm did) — required for the 3-tile T pattern.
//     4. enemy.rs enemy-attack loop special-cases BossHeal: when the
//        firing unit is BotBoss/BotBoss2, has BossHeal as weapon2, and is
//        damaged (`hp < max_hp`), the dispatch wid is overridden to
//        BossHeal and `apply_weapon_status` is called on the boss's own
//        tile to set the SHIELD flag. Mirrors the Lua `BotBoss:GetWeapon`
//        decision (skill index 2 vs 1).
//   Out of scope (deferred to a future sim version): the queued next-turn
//   +5 heal, which is outside the 1-turn solver horizon. Single-turn
//   prediction now correctly models damage AND end-of-turn shield state;
//   multi-turn lookahead can later add the pending-heal as a unit flag.
//   Pre-v31 corpus archived as `failure_db_snapshot_sim_v30.jsonl` per
//   CLAUDE.md rule 22.
//
// v32 (2026-04-28): player-phase Grid Defense expected save. Cluster
// Artillery (Ranged_Defensestrike) and other player weapons that clipped
// buildings were over-predicting grid loss by ~0.15 per friendly-fire
// hit — the simulator only modeled the 15% resist roll on the enemy
// phase. Per text.lua:122 ("This building resisted damage!") the roll
// fires for ALL building damage instances, including the player's own.
// All 8 Ranged_Defensestrike grid_power desyncs in failure_db.jsonl
// over-predicted by 1 — exactly the 1-resist-per-7-hits rate the 15%
// would predict. Fix: new `Board::player_grid_save_expected: f32` (mirror
// of `enemy_grid_save_expected`), accumulated in `simulate_action` per
// player action via `result.grid_damage * grid_defense_pct / 100`,
// surfaced in `evaluate::eff_grid` alongside the enemy save. Doesn't
// change deterministic grid_power decrements — the building still gets
// destroyed in the sim — only gives the evaluator a calibrated
// expectation so it stops over-penalizing plans that incidentally clip
// a building. Pre-v32 corpus archived as
// `failure_db_snapshot_sim_v31.jsonl` per CLAUDE.md rule 22.
//
// v33 (2026-04-28): Freeze Tank (Pinnacle Garden) modelling. Mission_FreezeBots
// spawns `Freeze_Tank` (HP=1, MoveSpeed=4, DefaultTeam=TEAM_PLAYER) per
// `scripts/missions/snow/snow_helper.lua:2-13`. Pre-v33 the solver had no
// PawnStats entry and `Pinnacle_FreezeTank` mapped to `WId::None` (DEF
// weapon — 0-damage melee), so killing or losing the Freeze Tank to a
// chain push was free in the score. Adds:
//   • `Freeze_Tank` PawnStats (move 4, ranged=1, pushable=true,
//     default_weapon=Pinnacle_FreezeTank) so move/push semantics are right.
//   • `WId::PinnacleFreezeTank` (=122) + WeaponDef (Projectile, dmg 0,
//     push None, FREEZE flag) so any phase-internal serialization round-trip
//     keeps the weapon name. Per `weapons_base.lua:426-446` TankDefault
//     defaults to RANGE_PROJECTILE; Lua override sets Damage=0, Push=0,
//     Freeze=1.
//   • `wid_from_str` / `wid_to_str` mappings.
// Friendly-NPC kill penalty (-20000) already applied in `evaluate.rs:722-728`
// because `is_player() && !is_mech()` — no evaluator change needed. Pre-v33
// corpus archived as `failure_db_snapshot_sim_v32.jsonl` per CLAUDE.md rule
// 22. The Freeze Tank's auto-fire happens at the start of the player turn
// before the solver acts (mirrors Filler_Pawn's Filler_Attack design); we
// observe the post-freeze board on next bridge read rather than simulating
// the friendly fire ourselves.
//
// v34 (2026-04-28): Burnbug Leader (BurnbugBoss / "Gastropod Leader")
// modelling for the Archive Inc Corp HQ finale. Pre-v34 the simulator had
// no PawnStats entry for `BurnbugBoss` and `enemy_weapon_for_type` returned
// WId::None for it, falling through to the unknown-Boss fallback (3-dmg
// single-target Alpha melee). The fallback got the damage approximately
// right but completely missed the boss type's HP / move / Massive flags
// and the weapon-specific FIRE status, leading to mech disable + grid 0
// drain on a Corp HQ run. Adds:
//   • `BurnbugBoss` PawnStats (HP not stored — bridge supplies live HP — but
//     move_speed=3, ranged=1, massive=true, default_weapon=BurnbugAtkB)
//     per `scripts/advanced/bosses/burnbug.lua:11-25`
//     (Health=6, MoveSpeed=3, Ranged=1, Massive=true, Tier=BOSS).
//   • `WId::BurnbugAtkB` (=123) + WeaponDef (Melee, 3 dmg, FIRE flag) per
//     `scripts/advanced/bosses/burnbug.lua:28-38`
//     (`BurnbugAtkB = BurnbugAtk1:new{Damage=3, BossFire=true, ...}`).
//     Modeled identically to BurnbugAtk2 — both are
//     `BurnbugAtk1:new{Damage=3}` derivatives. The cardinal-line grapple
//     mechanics from `scripts/advanced/ae_weapons_enemy.lua:261-309` are
//     simplified to a 1-tile melee with FIRE applied to the target,
//     matching the existing BurnbugAtk1 / BurnbugAtk2 simplification.
//   • `enemy_weapon_for_type`: BurnbugBoss → BurnbugAtkB.
//   • `wid_from_str` / `wid_to_str` mappings + display name "Flaming
//     Proboscis".
// Out of scope: `BossFire = true` ignites all 4 cardinal tiles around the
// boss when it fires (per Lua loop at lines 278-285). No existing weapon
// def can express "primary attack + around-self status" in one entry —
// would need a new flag + sim hook. The around-self trail's mech-on-fire
// damage is bounded at 1/turn while the mech remains on a trail tile and
// is dwarfed by the boss's 3-dmg primary attack, so the omission is a
// known minor under-prediction (deferred). The full grapple-pull
// mechanics (drag a hit pawn to the tile adjacent to the boss, OR
// self-charge the boss to an obstacle) are also not modeled — same
// simplification used for BurnbugAtk1 / BurnbugAtk2 since unit ship.
// Pre-v34 corpus archived as `failure_db_snapshot_sim_v33.jsonl` per
// CLAUDE.md rule 22.
//
// v35 (Flame Behemoths integration): three sim-semantics changes shipped
// together since the Flame Behemoths squad surfaced all three gaps at once.
//   1. Vulcan Artillery (Ranged_Ignite) no longer ignites the 4 cardinal
//      adjacent tiles — only the center tile gets Fire status; adjacent
//      tiles get push only. Confirmed via Lua weapons_ranged.lua:305 and
//      the in-game tooltip "Light THE TARGET on Fire and push adjacent
//      tiles". Pre-fix the solver over-credited Vulcan with 5-tile
//      ignition.
//   2. Science_Swap (Teleporter) now triggers the full landing pipeline
//      on both swapped units (water/lava/chasm death, fire/ACID pickup,
//      mines, teleporter pads) — previously only teleporter pads fired,
//      making the Swap Mech's primary kill mode invisible to the solver.
//      Refactored the inline post-move block from `apply_throw` into
//      `apply_landing_effects` so throw and swap share one pipeline.
//   3. Prime_Flamethrower (Flame Thrower) now deals +2 damage to a target
//      that is already on Fire at firing time, matching the Lua semantic
//      `Damage + FireDamage` and the in-game tooltip "Damage units already
//      on Fire". Gated by the new `BURNS_FIRE_TARGETS` weapon flag.
// v36 — Two predictions changed:
//   1. Renfield Bomb (BigBomb) tracked via Board.bigbomb_alive; the
//      alive→dead transition pays `bigbomb_killed` (-200000 default) on
//      Mission_Final_Cave. Friendly_npc_killed still fires; bigbomb_killed
//      stacks on top to reflect that losing the bomb fails the run.
//   2. `_REPAIR` plans now correctly resolve via `wid_from_str` →
//      WId::Repair instead of falling through to WId::None. simulate_attack
//      executes the repair branch (heal +1, clear fire/acid/frozen,
//      set_active(false)). Repair-using boards now score with the heal
//      properly modeled instead of being treated as a no-op.
// Pre-v36 corpus archived as `failure_db_snapshot_sim_v35.jsonl`.
// v37 — Four new Psion aura hooks change predictions on boards with
// these enemies present:
//   1. Jelly_Boss (Psion Abomination) — composite aura: +1 max_hp + regen
//      heal + Vek-explode-on-death simultaneously. Reuses the existing
//      soldier/regen/blast aura code paths via OR-gated triggers; the
//      max_hp buff is dedup'd so Boss + Jelly_Health1 simultaneously
//      alive does not double-stack.
//   2. Jelly_Boost1 (LEADER_BOOSTED) — Vek weapon damage +1 while alive,
//      excluding the Psion's own attacks. Applied at base_damage in
//      enemy.rs:646-660.
//   3. Jelly_Fire1 (LEADER_FIRE) — two parts: Vek immune to Fire damage
//      (fire-tick block + every set_fire callsite gated on !fire_psion
//      for Vek targets), AND Vek dying creates Fire on their tile (top
//      of on_enemy_death, fire-hostable terrain only).
//   4. Jelly_Spider1 (LEADER_SPIDER) — Vek dying spawns a WebbEgg1 on
//      their tile (existing egg-spawn sim handles hatch).
// All four flags clear properly when the source Psion dies.
// Pre-v37 corpus archived as `failure_db_snapshot_sim_v36.jsonl`.
// v38 — Two surgical fixes to v37's known follow-ups:
//   1. Boss/Blast Psion EXPLODE-on-death now fires when a Vek dies via
//      env_danger (lethal volcano eruption, lightning, tidal wave,
//      cataclysm). Previously the explosion was dispatched only at
//      caller sites in apply_damage / apply_push (deadly terrain) /
//      mine paths; env_danger called on_enemy_death but skipped the
//      explosion. Fix: apply_death_explosion is now pub(crate) and
//      apply_env_danger dispatches it after on_enemy_death when
//      blast_psion || boss_psion is alive. (v39 follow-up: centralize
//      explosion into on_enemy_death so push-deadly + mine + ice-drown
//      + dam-flood paths also fire it.)
//   2. Spider Psion (LEADER_SPIDER) WebbEgg1 spawn deferred via
//      Board.pending_spider_eggs queue. Previously the egg was spawned
//      directly in on_enemy_death, but the enemy-phase hatch loop ran
//      AFTER the spawn, so eggs hatched in the same enemy phase they
//      were spawned. Fix: queue the (x,y) in on_enemy_death; drain at
//      the END of simulate_enemy_attacks (after hatch loop, after
//      train advance). Eggs now sit dormant until the next enemy
//      phase, matching the game's AddQueuedDamage semantics from
//      weapons_enemy.lua:857.
// v39 — Added Support_Wind / Wind Torrent modeling. The solver now recognizes
//   `Support_Wind` as an AE any-class global-push support weapon, enumerates
//   one representative target per fixed custom edge zone, and simulates the
//   Lua scan-order push of every pawn in the selected direction. Pre-v39 corpus
//   archived as `failure_db_snapshot_sim_v38.jsonl`.
// v40 — Standard single-tile enemy melee re-aims from the attacker's current
//   position using the original queued direction after displacement. BlobBoss
//   still uses its v29 queued-damage path. Fixes Venting Center T1
//   Scorpion2 swap killing TeleMech at E4. Pre-v40 corpus archived as
//   `failure_db_snapshot_sim_v39.jsonl`.
// v41 — Vulcan Artillery (Ranged_Ignite) zero-damage adjacent pushes no
//   longer apply off-board edge-bump damage. Pre-v41 corpus archived as
//   `failure_db_snapshot_sim_v40.jsonl`.
// v42 — Instant terrain/mine deaths from push/swap/throw landing effects now
//   run enemy-death side effects, including Blast/Boss Psion death explosions,
//   Volatile decay, and psion aura teardown. Prime Flamethrower damage+push
//   kills defer Blast/Boss Psion explosion to the post-push corpse tile.
//   Replay snapshots also include all building tiles so Grid Defense and Blast
//   Psion building diffs are visible even when event telemetry is sparse.
//   Pre-v42 corpus archived as `failure_db_snapshot_sim_v41.jsonl`.
// v43 — Final-cave Renfield Bomb is pushable/bumpable, and Vulcan Artillery
//   Backburn (`Ranged_Ignite_A`) lights the tile behind the shooter on fire.
//   Pre-v43 corpus archived as `failure_db_snapshot_sim_v42.jsonl`.
// v44 — Burnbug/Gastropod proboscis attacks are projectile grapples rather
//   than one-tile melee. Vacated first target tiles no longer nullify the
//   shot; the hook travels to the first blocker, damages it, and pulls a hit
//   pawn toward the attacker or the attacker toward an object. Fixes Normal
//   run 20260504_210332_088 m01 t01 F7 grid loss. Pre-v44 corpus archived as
//   `failure_db_snapshot_sim_v43.jsonl`.
// v45 — Projected final-board JSON now preserves `building_hp: 0` on
//   destroyed unique objective buildings. Bridge terrain parsing also trusts
//   engine terrain ids over stale strings, fixing id 5 = Ice being mislabeled
//   as Lava in older bridge recordings. This prevents candidate audits from
//   resurrecting failed Coal Plant / Power objectives and stops false lava
//   deaths on Pinnacle ice. Pre-v45 corpus archived as
//   `failure_db_snapshot_sim_v44.jsonl`.
// v46 — Crab Leader (`CrabBoss` / `CrabAtkB`) now maps to Raining Expulsions:
//   2-damage artillery target plus 1 damage to every tile in the projectile
//   path. Fixes Normal run 20260504_210332_088 m05 t01/t02 grid-loss
//   underprediction. Pre-v46 corpus archived as
//   `failure_db_snapshot_sim_v45.jsonl`.
// v47 — Web/repair cleanup from Artifact Vaults: pushing a webbed pawn clears
//   that pawn's own web_source_uid + WEB flag, and Repair extinguishes the
//   occupied tile's fire as well as the unit fire status. Bridge attack-intent
//   extraction also now trusts save iQueuedSkill over stale GetSelectedWeapon
//   to avoid false phantom attacks. Pre-v47 corpus archived as
//   `failure_db_snapshot_sim_v46.jsonl`.
// v48 — Mission_Repair platforms (`Item_Repair_Mine`) now round-trip through
//   bridge/Python/Rust tile state, heal via the engine's -10 item damage with
//   a live-observed cap of at least 5 HP, consume on landing/push/swap/throw,
//   and increment repair-platform objective progress. Pre-v48 corpus archived
//   as `failure_db_snapshot_sim_v47.jsonl`.
// v49 - Blocked pushes no longer clear a pawn's own web. The game only breaks
//   web when the pawn actually changes tiles; bumping into an obstacle leaves
//   it webbed. Also models `Ranged_Artillerymech_A` direct building immunity.
//   Pre-v49 corpus archived as `failure_db_snapshot_sim_v48.jsonl`.
// v50 - Archive / Deploy Tank `Deploy_TankShot` is modeled as a controllable
//   friendly projectile push weapon (0 damage, forward push), so Stock Cannon
//   tanks participate in the solver search. Pre-v50 corpus archived as
//   `failure_db_snapshot_sim_v49.jsonl`.
// v51 - Mission_Trapped Decoy Building `Trapped_Explode` is modeled as an
//   expendable player-team self-destruct: kills itself and adjacent
//   non-building tiles while preserving neighboring buildings. Pre-v51 corpus
//   archived as `failure_db_snapshot_sim_v50.jsonl`.
// v52 - Corporate HQ Bouncer Leader (`BouncerBoss` / `BouncerAtkB`) now maps
//   to Sweeping Horns: 2-damage forward-push T-pattern plus boss bounce-back.
//   Pre-v52 corpus archived as `failure_db_snapshot_sim_v51.jsonl`.
// v53 - Python solve payloads copy static pawn Armor into Rust JSON when the
//   Lua bridge omits it; this fixes Bouncer Leader damage predictions. Pre-v53
//   corpus archived as `failure_db_snapshot_sim_v52.jsonl`.
// v54 - Archive Armored Train (`Train_Armored`) advances like the normal train
//   but destroys blockers in the two entered tiles instead of dying. Pre-v54
//   corpus archived as `failure_db_snapshot_sim_v53.jsonl`.
// v55 - Live Storage Vaults fixes: Rocket Artillery center-kill pushes now
//   let dead targets bump live blockers and killed non-pushable targets bump
//   static blockers; repair platforms cap overheal at max_hp+2. Pre-v55
//   corpus archived as `failure_db_snapshot_sim_v54.jsonl`.
// v56 - Science_Repulse_A (Shield Self) applies Shield to the firing Pulse
//   Mech after Repulse resolves; loadout overlay now recognizes
//   Science_Repulse_A/AB. Pre-v56 corpus archived as
//   `failure_db_snapshot_sim_v55.jsonl`.
// v57 - Illegal Leap weapon landings no-op with an
//   `illegal_leap_landing:x:y:reason` replay event instead of letting
//   diagnostic score_plan/replay inputs stack units on blocked tiles.
//   Pre-v57 corpus archived as `failure_db_snapshot_sim_v56.jsonl`.
// v58 - Detritus Contraption weapons are modeled as global non-source unit
//   effects. Pre-v58 corpus archived as `failure_db_snapshot_sim_v57.jsonl`.
// v59 - Detritus barrage targeting excludes the source tile and soft-disable
//   masks cover WId >= 128. Pre-v59 corpus archived as
//   `failure_db_snapshot_sim_v58.jsonl`.
// v60 - Static Spider1/Spider2 pawn stats are pushable; solve payloads no
//   longer inject false `pushable=false` for normal/alpha Spiders. Pre-v60
//   corpus archived as `failure_db_snapshot_sim_v59.jsonl`.
// v61 - Mission_Teleporter action enumeration now targets attacks from the
//   post-pad-swap position, while invalid diagonal SelfAoe clicks no-op in
//   replay/sim. Pre-v61 corpus archived as
//   `failure_db_snapshot_sim_v60.jsonl`.
// v62 - Move-then-attack enumeration again targets from the post-move tile for
//   ordinary movement; v61 accidentally used the pre-move tile except on
//   teleporter pads. Pre-v62 corpus archived as
//   `failure_db_snapshot_sim_v61.jsonl`.
// v63 - Partial re-solves now re-apply save-file upgraded weapon overlays so
//   upgraded semantics such as Science_Repulse_A Shield Self remain predicted
//   after an earlier turn desync. Pre-v63 corpus archived as
//   `failure_db_snapshot_sim_v62.jsonl`.
// v64 - Player movement enumeration treats ACID pools as non-stoppable tiles,
//   hardening the "never move onto ACID voluntarily" operational rule and
//   avoiding bridge/status ambiguity after ACID-pool moves. Pre-v64 corpus
//   archived as `failure_db_snapshot_sim_v63.jsonl`.
// v65 - Smoke placed onto a queued web source immediately releases units webbed
//   by that source, matching Scorpion Leader web cancellation when Rocket
//   smoke lands behind the shooter. Pre-v65 corpus archived as
//   `failure_db_snapshot_sim_v64.jsonl`.
// v66 - Save-file overlays now recognize Rocket Artillery damage upgrades
//   (`Ranged_Rocket_A/B/AB`), and Rust models their increased damage while
//   preserving Rocket-specific smoke and corpse-push behavior. Pre-v66 corpus
//   archived as `failure_db_snapshot_sim_v65.jsonl`.
// v67 - Cannon-Bot (`SnowtankAtk1` / Cannon 8R Mark I) is a Firefly-style
//   projectile that sets the hit target on fire, not a melee attack. This
//   predicts Mission_FreezeBots line hits such as run 20260508_122657_124
//   m01 t01 PulseMech fire damage. Pre-v67 corpus archived as
//   `failure_db_snapshot_sim_v66.jsonl`.
// v68 - AE Moths and Bouncers resolve queued recoil self-push plus forward
//   target push in their normal enemy attack paths. This predicts Moth recoil
//   bumping a blocking mech before artillery, as seen in run
//   20260508_134925_472 m02 t02. Pre-v68 corpus archived as
//   `failure_db_snapshot_sim_v67.jsonl`.
// v69 - Mission_Trapped 2-HP Coal Plant building tiles are inferred as
//   objective-style buildings when the bridge omits `unique_building`, so
//   push-bump HP damage decrements grid power. Pre-v69 corpus archived as
//   `failure_db_snapshot_sim_v68.jsonl`.
// v70 - Leap weapon target enumeration / replay no-op reject chasm landing
//   tiles. Live Aerial Bombs on a Cataclysm chasm tile click-missed instead of
//   moving JetMech or damaging the transit tile. Pre-v70 corpus archived as
//   `failure_db_snapshot_sim_v69.jsonl`.
// v71 - Rocket Artillery center push does not add phantom map-edge bump
//   damage when the target has no tile to move into. Pre-v71 corpus archived as
//   `failure_db_snapshot_sim_v70.jsonl`.
// v72 - ACID weapons acidify live occupied targets without creating an
//   immediate ground pool beneath them. Pre-v72 corpus archived as
//   `failure_db_snapshot_sim_v71.jsonl`.
// v73 - Starfish / Starfish Leader appendage attacks are self-targeted
//   diagonal damage patterns, with StarfishAtkB1 additionally pushing the
//   four cardinal adjacent tiles. Pre-v73 corpus archived as
//   `failure_db_snapshot_sim_v72.jsonl`.
// v74 - Aerial Bombs rejects water/lava landing tiles. Live JetMech water
//   landings spend the attack as a no-op without damaging transit tiles.
//   Pre-v74 corpus archived as `failure_db_snapshot_sim_v73.jsonl`.
// v75 - Repulse zero-damage adjacent pushes do not add phantom map-edge bump
//   damage when the outward destination is off-board. Pre-v75 corpus archived
//   as `failure_db_snapshot_sim_v74.jsonl`.
// v76 - WebbEgg1 adjacency webs are inferred in Rust bridge loading and after
//   simulated movement/landing while preserving active non-egg grapples.
//   Pre-v76 corpus archived as
//   `failure_db_snapshot_sim_v75.jsonl`.
// v77 - BurrowerAtk1/BurrowerAtk2 melee slams damage the center target tile
//   plus the two perpendicular flank tiles. Pre-v77 corpus archived as
//   `failure_db_snapshot_sim_v76.jsonl`.
// v78 - Save-file upgraded weapon overlays derive modeled upgraded IDs from
//   pawn primary_mod*/secondary_mod* power pips when GameData.current.weapons
//   stays on base weapon IDs. Pre-v78 corpus archived as
//   `failure_db_snapshot_sim_v77.jsonl`.
// v79 - Player artillery target enumeration briefly allowed off-axis targets;
//   reverted in v80 after live Rocket Artillery proved those bridge-accepted
//   targets no-op in-engine. Pre-v79 corpus archived as
//   `failure_db_snapshot_sim_v78.jsonl`.
// v80 - Player artillery targeting is cardinal-only again, and diagnostic
//   score/replay reject illegal moves, smoke-blocked attacks, and invalid
//   weapon target areas instead of validating impossible hand-written plans.
//   Pre-v80 corpus archived as `failure_db_snapshot_sim_v79.jsonl`.
// v81 - Normal Psions (`Jelly_Health1` family, including Blast Psion) are
//   pushable. Solve payload enrichment no longer injects `pushable=false`,
//   allowing Repulse/Rocket bump damage into blockers. Pre-v81 corpus archived
//   as `failure_db_snapshot_sim_v80.jsonl`.
// v82 - Blast Psion aura explosions do not recursively trigger additional
//   Blast Psion aura explosions from enemies killed by the first burst.
//   Pre-v82 corpus archived as `failure_db_snapshot_sim_v81.jsonl`.
// v83 - Dam flood drowning uses the instant-death path, so drowned Vek emit
//   Blast Psion / Volatile side effects instead of raw `hp = 0`.
//   Pre-v83 corpus archived as `failure_db_snapshot_sim_v82.jsonl`.
// v84 - Minor Vek carry a UnitFlags::MINOR marker and are excluded from Psion
//   aura bonuses (Blast/Boss death explosions, HP/armor/regen/fire/boost/spider
//   effects). Dam flood iteration now matches mission_dam.lua's y-major loop.
//   Pre-v84 corpus archived as `failure_db_snapshot_sim_v83.jsonl`.
// v85 - Direct weapon/explosion damage to buildings drains current Grid Power
//   per building HP lost again; non-unique multi-HP bump/push collision damage
//   still drains only on destruction. Pre-v85 corpus archived as
//   `failure_db_snapshot_sim_v84.jsonl`.
// v86 - Aerial Bombs upgraded weapon IDs (`Brute_Jetmech_A/B/AB`) are modeled
//   from save overlays. The +1 Range branch expands Jet Mech target search to
//   2-3 cardinal tiles while preserving water/lava landing illegality.
//   Pre-v86 corpus archived as `failure_db_snapshot_sim_v85.jsonl`.
// v87 - Blobber Leader package (`BlobberBoss`, `BlobberAtkB`, `BlobB`,
//   `BlobAtkB`) is modeled directly: boss artillery spawns 2-HP Blob Leaders,
//   and enemy SelfAoe can use split inner/outer damage for BlobB's 1 self
//   damage plus 2 adjacent damage. Pre-v87 corpus archived as
//   `failure_db_snapshot_sim_v86.jsonl`.
// v88 - Briefly treated ordinary burning ground as not igniting flying units;
//   superseded by v89 after a settled bridge read proved the live desync was a
//   verification timing issue. Pre-v88 corpus archived as
//   `failure_db_snapshot_sim_v87.jsonl`.
// v89 - Restores ordinary tile-fire ignition for flying units and pairs it
//   with a Python auto_turn settle retry for transient predicted-true status
//   diffs immediately after bridge sub-actions. Pre-v89 corpus archived as
//   `failure_db_snapshot_sim_v88.jsonl`.
// v90 - Ramming Engines recoil/self-damage on sand now consumes the sand and
//   creates smoke, matching live Mission_Terratide turn 1 ChargeMech behavior.
//   Pre-v90 corpus archived as `failure_db_snapshot_sim_v89.jsonl`.
// v91 - Diagnostic score_plan now applies spawn blocking after enemy attacks,
//   matching replay/project_plan and avoiding false-clean manual plan audits.
//   Pre-v91 corpus archived as `failure_db_snapshot_sim_v90.jsonl`.
// v92 - Shield Projector can target and protect buildings, including its
//   second line tile; building shields are consumed before HP/grid damage.
//   Pre-v92 corpus archived as `failure_db_snapshot_sim_v91.jsonl`.
// v93 - Mission_BoomBots `*_Boom` Pinnacle bots now use intrinsic Explosive
//   Decay on death, splashing adjacent buildings/mechs like Volatile Vek.
//   Pre-v93 corpus archived as `failure_db_snapshot_sim_v92.jsonl`.
// v94 - Burst Beam powered Ally Immune loadouts (`Prime_Lasermech_A` / `_AB`)
//   now overlay from save data and skip friendly unit damage while preserving
//   beam decay through the friendly tile.
//   Pre-v94 corpus archived as `failure_db_snapshot_sim_v93.jsonl`.
// v95 - Titan Fist powered loadouts (`Prime_Punchmech_A` / `_B` / `_AB`)
//   now overlay from save data; Dash / Dash+Damage use Charge semantics and
//   record Ramming Speed candidate kills at distance >=5.
//   Pre-v95 corpus archived as `failure_db_snapshot_sim_v94.jsonl`.
// v96 - Taurus Cannon direct edge pushes and Artemis adjacent edge pushes no
//   longer add off-board bump damage; on-board blocker bumps remain intact.
//   Pre-v96 corpus archived as `failure_db_snapshot_sim_v95.jsonl`.
// v97 - Boosted unit status now enters solver payloads, adds +1 weapon damage
//   / repair healing, and is consumed on attack or repair.
//   Pre-v97 corpus archived as `failure_db_snapshot_sim_v96.jsonl`.
// v98 - Titan Fist Dash follows Lua AddCharge/Projectile pathing through
//   water/lava instead of stopping at water, and dead Dash Punch targets can
//   still bump a live blocker behind them. Pre-v98 corpus archived as
//   `failure_db_snapshot_sim_v97.jsonl`.
// v99 - Final Cave Env_Final danger is falling-rock/tentacle death, not
//   hoverable cataclysm chasm conversion; ignore stale flying_immune=1
//   payloads on Mission_Final_Cave so flying mechs cannot stand on marked
//   cave-collapse tiles. Pre-v99 corpus archived as
//   `failure_db_snapshot_sim_v98.jsonl`.
// v100 - Lua bridge exports live Stable/IsGuarding state as `pushable=false`,
//   and Python board parsing preserves live pushability overrides so Final Cave
//   leaders are not predicted to move when Taurus/Artemis push them.
//   Pre-v100 corpus archived as `failure_db_snapshot_sim_v99.jsonl`.
// v101 - Aerial Bombs smoke consumes transit Forest tiles before damage, and
//   Morgan Lejeune (Pilot_Chemical) gains Boost after enemy kills instead of
//   always clearing Boost at action end. Pre-v101 corpus archived as
//   `failure_db_snapshot_sim_v100.jsonl`.
// v102 - Mission_Wind rows are no longer modeled as direct environment damage;
//   the bridge marks them separately until it can export live WindDir for full
//   push simulation. Pre-v102 corpus archived as
//   `failure_db_snapshot_sim_v101.jsonl`.
// v103 - Rust replay verification snapshots now include `status.boosted`, matching
//   Python snapshots and preventing Kai/Morgan Boost from surfacing as false
//   status/click_miss desyncs. Pre-v103 corpus archived as
//   `failure_db_snapshot_sim_v102.jsonl`.
// v104 - Kai Miller (Pilot_Arrogant) Boost is state-based: full-HP Kai remains
//   Boosted after attacks and regains Boost after Repair/repair platforms,
//   while damage below full HP clears Boost. Pre-v104 corpus archived as
//   `failure_db_snapshot_sim_v103.jsonl`.
// v105 - Arachnid Psion death eggs materialize immediately after player-phase
//   kills as SpiderlingEgg1 using live-style next pawn ids; enemy-phase eggs
//   still drain after the hatch loop so they do not hatch in the same phase.
//   Pre-v105 corpus archived as `failure_db_snapshot_sim_v104.jsonl`.
// v106 - Mission_Belt conveyors move live units before Vek attacks, and
//   save/bridge conveyor parsing no longer cross-pairs a tile loc with a
//   later tile's custom sprite. Pre-v106 corpus archived as
//   `failure_db_snapshot_sim_v105.jsonl`.
// v107 - Conveyor belts move live units before Vek attacks on any map with
//   live conveyor tiles, not just Mission_Belt. Pre-v107 corpus archived as
//   `failure_db_snapshot_sim_v106.jsonl`.
// v108 - Mission_Repair platforms consume/count for full-health units without
//   overhealing them; damaged units still use the max_hp+2 overheal cap. Also
//   corrects dirty fallback solve reporting. Pre-v108 corpus archived as
//   `failure_db_snapshot_sim_v107.jsonl`.
// v109 - Leap attacks that relocate the firing unit now break that unit's own
//   web and resolve landing effects, so Aerial Bombs catches fire when landing
//   on an already-burning Forest tile and consumes it to burning Ground.
//   Pre-v109 corpus archived as
//   `failure_db_snapshot_sim_v108.jsonl`.
// v110 - Aerial Bombs over an occupied transit tile applies occupant damage
//   and smoke without generic terrain damage, preserving sand under Pulse on
//   D3 in Hard Rusting Hulks run 20260512_181719_119 Mission_Holes turn 2.
//   Pre-v110 corpus archived as
//   `failure_db_snapshot_sim_v109.jsonl`.
// v111 - Non-unique multi-HP building bump damage can defer grid loss until
//   that same building is later destroyed, matching C4 in Hard Rusting Hulks
//   run 20260512_181719_119 Mission_Holes turn 2. Pre-v111 corpus archived as
//   `failure_db_snapshot_sim_v110.jsonl`.
// v112 - Scarab Leader's Expectorating Glands is modeled as 4-damage artillery
//   with zero-damage outward adjacent pushes, and synthetic default tiles now
//   use conveyor_dir=-1 so no-belt tests do not pre-shift enemy attacks. Pre-v112
//   corpus archived as `failure_db_snapshot_sim_v111.jsonl`.
// v113 - Spider Psion death eggs follow a Rocket-killed corpse that is pushed
//   into a clear tile, matching Hard Rusting Hulks run 20260513_144310_771
//   Mission_Solar turn 3 where C2 -> C1 produced the live egg at C1. Pre-v113
//   corpus archived as `failure_db_snapshot_sim_v112.jsonl`.
// v114 - Deferred non-unique multi-HP bump grid debt flushes at enemy-turn
//   start, matching Hard Rusting Hulks run 20260513_144310_771 Mission_Holes
//   turn 2 where Rocket bumped B4 2->1, grid stayed 4 during player phase,
//   then dropped to 3 by next player turn. Pre-v114 corpus archived as
//   `failure_db_snapshot_sim_v113.jsonl`.
// v115 - WebbEgg / SpiderlingEgg hatch uses live-style `sPawn` adjacent fallback
//   instead of in-place mutation; if the destination is a live building, the
//   building is destroyed and full HP drains grid. Matches Hard Rusting Hulks
//   run 20260513_144310_771 Mission_FireflyBoss turn 2, where E6 hatched onto
//   F6 and destroyed a 2-HP building. Pre-v115 corpus archived as
//   `failure_db_snapshot_sim_v114.jsonl`.
// v116 - Landing on smoke extinguishes carried unit fire. Matches Hard Rusting
//   Hulks run 20260513_230944_542 Mission_Airstrike turn 2, where Jet used
//   Aerial Bombs from H3 to already-smoked F3 and live cleared fire while the
//   simulator kept it. Pre-v116 corpus archived as
//   `failure_db_snapshot_sim_v115.jsonl`.
// v117 - Beetle charge attacks push their hit target forward, and Bouncer
//   self-recoil into the board edge does not deal self-bump damage. Matches
//   Hard Rusting Hulks run 20260513_230944_542 Mission_Airstrike turn 4:
//   Beetle shoved Rocket B3->B4, then Bouncer hit B4 and pushed the KIA
//   Rocket to C4. Pre-v117 corpus archived as
//   `failure_db_snapshot_sim_v116.jsonl`.
// v118 - Mission_Terraform's controllable Terraformer_Attack is modeled as a
//   3x2 instant-kill terrain-conversion sweep, so active Terraformer units are
//   included in solver actor permutations. Pre-v118 corpus archived as
//   `failure_db_snapshot_sim_v117.jsonl`.
// v119 - Mission_Terraform custom grassland is tracked as a tile flag and
//   scored as remaining objective debt; Terraformer sweeps clear the flag.
//   Pre-v119 corpus archived as `failure_db_snapshot_sim_v118.jsonl`.
// v120 - Live AE Lua ids `Dung1` / `Dung2` and `DungAtk1` / `DungAtk2`
//   map onto the existing Tumblebug weapon model. Pre-v120 corpus archived
//   as `failure_db_snapshot_sim_v119.jsonl`.
// v121 - BombRock / Unstable Boulder is catalogued as a neutral explosive
//   Tumblebug boulder; destroying it deals 1 adjacent bump-class damage, while
//   Tumblebug self-detonation excludes the source tile. Pre-v121 corpus
//   archived as `failure_db_snapshot_sim_v120.jsonl`.
// v122 - Time Pods are fragile map objects: player mech landing collects,
//   while enemy/non-mech landing or direct tile damage destroys without
//   collection credit. Pre-v122 corpus archived as
//   `failure_db_snapshot_sim_v121.jsonl`.
// v123 - BlobBoss death split materializes Large Goo -> 2 Medium Goo and
//   Medium Goo -> 2 Small Goo using deterministic Lua-diamond candidate
//   selection; Goo queued attacks also destroy full mountains and move into
//   non-mech targets when the squish clears the tile. Pre-v123 corpus
//   archived as `failure_db_snapshot_sim_v122.jsonl`.
// v124 - Moved queued attackers preserve the original attacker-relative target
//   offset. BlobBoss queued-damage persistence now shifts with the Goo after
//   pushes/pulls/swaps instead of treating piQueuedShot as an absolute tile;
//   bridge payloads also expose piOrigin and normalize piQueuedShot when the
//   Vek has already moved. Regression anchor: Ramming Speed run
//   20260516_120646_726, HQ turn 1, BlobBoss B3->B2 retargeted A3->A2 and
//   Scarab G3->G2 retargeted G6->G5. Pre-v124 corpus archived as
//   `failure_db_snapshot_sim_v123.jsonl`.
// v125 - Blast Psion explosions chain through eligible non-minor Vek.
// v126 - Mission_Disposal A.C.I.D. Launcher (`Disposal_Attack`) is modeled as
//   a controllable player-side mission ally weapon: artillery target, lethal
//   acid cross, and mountain-clear terrain conversion. Pre-v126 corpus
//   archived as `failure_db_snapshot_sim_v125.jsonl`.
// v127 - Killing the last Boost Psion clears the visible Boosted status from
//   all surviving Vek immediately. Pre-v127 corpus archived as
//   `failure_db_snapshot_sim_v126.jsonl`.
// v128 - Disposal_Attack dissolves building tiles inside its acid cross, not
//   only units/mountains/status. Pre-v128 corpus archived as
//   `failure_db_snapshot_sim_v127.jsonl`.
// v129 - Decorative conveyor sprites on Env_Null missions do not run an
//   enemy-phase belt tick. Conveyor movement is gated to Mission_Belt and
//   Mission_BeltRandom. Pre-v129 corpus archived as
//   `failure_db_snapshot_sim_v128.jsonl`.
// v130 - Live AE Tumblebug Leader ids `DungBoss` / `DungAtkB` map onto the
//   existing Alpha Tumblebug boulder attack model (3-damage queued
//   boulder/tile hit; boulders are already exposed by the bridge). Pre-v130
//   corpus archived as `failure_db_snapshot_sim_v129.jsonl`.
// v131 - BombRock death explosions fire immediately on damage+push weapons
//   instead of being swallowed by the deferred corpse-push path; dead
//   BombRocks do not push onward as corpses. Pre-v131 corpus archived as
//   `failure_db_snapshot_sim_v130.jsonl`.
// v132 - Weapon damage that ignites Forest consumes it to burning Ground
//   immediately, matching live Prime Punch hits on forest-occupied enemies.
//   Pre-v132 corpus archived as `failure_db_snapshot_sim_v131.jsonl`.
// v133 - Directionless Artemis-style artillery was temporarily broadened to
//   board-wide targeting; live D6->F2 proved that off-axis FireWeapon no-ops.
//   Pre-v133 corpus archived as `failure_db_snapshot_sim_v132.jsonl`.
// v134 - Restore player artillery target areas to cardinal-only, including
//   Artemis. Diagnostic replay now rejects off-axis Artemis shots as illegal
//   no-ops. Pre-v134 corpus archived as `failure_db_snapshot_sim_v133.jsonl`.
// v135 - Rock Accelerator materializes a neutral 1 HP RockThrown on empty
//   target tiles, matching Blitzkrieg run 20260517_105759_344 Mission_Train
//   turn 3. Pre-v135 corpus archived as `failure_db_snapshot_sim_v134.jsonl`.
// v136 - RockThrown spawned during active Mission_AcidStorm inherits ACID
//   immediately, matching Blitzkrieg run 20260517_105759_344 The Wasteland
//   turn 1. Pre-v136 corpus archived as `failure_db_snapshot_sim_v135.jsonl`.
// v137 - Repair/Repair Drop during active Mission_AcidStorm leaves player
//   units ACIDed after healing, matching The Wasteland turn 2. Pre-v137
//   corpus archived as `failure_db_snapshot_sim_v136.jsonl`.
// v138 - Rock Launcher defers Boom Bot / Volatile center death decay until
//   after its perpendicular side pushes, matching Mission_BoomBots where the
//   side Boom Tank is shoved out before the killed center bot explodes.
//   Pre-v138 corpus archived as `failure_db_snapshot_sim_v137.jsonl`.
// v141 - Mosquito Leader `MosquitoBoss` / `MosquitoAtkB` modeled as
//   shield-piercing smoke+web instant kill. Pre-v141 corpus archived as
//   `failure_db_snapshot_sim_v140.jsonl`.
// v142 - Raw `web_probes.IsGrappled=true` is authoritative even when older
//   bridge fallback cleared `web=false`; infer queued web source ownership.
//   Pre-v142 corpus archived as `failure_db_snapshot_sim_v141.jsonl`.
// v143 - Arachnophiles base kit modeled: bridge-executable Ricochet Rocket,
//   Arachnoid Injector spawn-on-kill, spawned Arachnoid bite, and Area Shift.
//   Pre-v143 corpus archived as `failure_db_snapshot_sim_v142.jsonl`.
// v144 - Prime Flamethrower killed-target pushes can corpse-bump live blockers,
//   matching Perfect Strategy run 20260517_175633_388 Mission_Teleporter turn 4.
//   Cluster Artillery outer corpse absorption remains unchanged. Pre-v144 corpus
//   archived as `failure_db_snapshot_sim_v143.jsonl`.
// v145 - Mission_Airstrike / Mission_Lightning override stale
//   flying_immune=1 env_danger_v2 payloads so bombs/lightning kill flying mechs;
//   terrain-conversion missions keep flyer immunity. Pre-v145 corpus archived
//   as `failure_db_snapshot_sim_v144.jsonl`.
// v146 - Frozen buildings thaw on damage instead of taking building/grid
//   damage, and Mission_FreezeBldg objective tiles are scored from live thaw
//   state. Pre-v146 corpus archived as `failure_db_snapshot_sim_v145.jsonl`.
// v147 - Flame Shielding protects player mechs only, not controllable mission
//   allies such as Archive_Tank. Mission_Tanks Archive Tanks are also surfaced
//   as protected objective units. Pre-v147 corpus archived as
//   `failure_db_snapshot_sim_v146.jsonl`.
// v148 - Mission_Wind exports live WindDir and simulates wind row pushes before
//   Vek attacks, including bump/grid damage. Pre-v148 corpus archived as
//   `failure_db_snapshot_sim_v147.jsonl`.
// v149 - Attack-phase landing effects collect/destroy Time Pods, so Aerial
//   Bombs landing on a pod records collection instead of leaving the pod in
//   predicted state. Pre-v149 corpus archived as
//   `failure_db_snapshot_sim_v148.jsonl`.
// v150 - Aerial Bombs transit over Mission_FreezeBldg frozen objective
//   buildings thaws and damages the building, with grid loss deferred to
//   enemy-turn settle. Pre-v150 corpus archived as
//   `failure_db_snapshot_sim_v149.jsonl`.
// v151 - Minor Vek such as Totems still count as enemies_killed for scoring,
//   but no longer advance mission.KilledVek objectives like "Kill at least
//   5 Enemies". Pre-v151 corpus archived as
//   `failure_db_snapshot_sim_v150.jsonl`.
// v152 - Stale non-egg `web_source_uid` from bridge input is replaced when an
//   alive queued web attack currently targets the webbed unit's tile. Fixes
//   false web-clears after moving the wrong stale source. Pre-v152 corpus
//   archived as `failure_db_snapshot_sim_v151.jsonl`.
// v153 - Firefly Leader (`FireflyAtkB` / Burning Thorax) fires paired
//   projectiles in both the queued direction and the opposite direction.
//   Pre-v153 corpus archived as `failure_db_snapshot_sim_v152.jsonl`.
// v155 - Science_Swap / Teleporter target validation is cardinal-line only,
//   matching Lua GetTargetArea. Diagonal or out-of-range swap targets now no-op
//   in replay/scoring instead of projecting a fake teleport. Pre-v155 corpus
//   archived as `failure_db_snapshot_sim_v154.jsonl`.
// v156 - FIRE weapon status on Sand/Forest consumes the terrain to burning
//   Ground immediately, matching live Flamethrower/Ranged_Ignite verification.
//   Pre-v156 corpus archived as `failure_db_snapshot_sim_v155.jsonl`.
// v157 - Pinnacle FACTION_BOTS (`Snowtank*`, `Snowart*`, `Snowlaser*`,
//   `Snowmine*`, `BotBoss*`) are not Vek and do not receive Psion auras.
//   Pre-v157 corpus archived as `failure_db_snapshot_sim_v156.jsonl`.
// v158 - Prime_Flamethrower lights the struck tile before pushing, but a
//   target pushed off that tile does not carry Fire status. Pre-v158 corpus
//   archived as `failure_db_snapshot_sim_v157.jsonl`.
// v159 - Prime_Flamethrower's newly lit target tile ignites grounded occupants
//   even if pushed away, but flying occupants only catch it if they remain on
//   or land on a burning tile. Pre-v159 corpus archived as
//   `failure_db_snapshot_sim_v158.jsonl`.
// v160 - Fire weapons no longer mark non-fire-hosting terrain (for example
//   Water) as a burning tile; Prime_Flamethrower still applies direct Fire to
//   a flying target if its push is blocked and the target remains on the struck
//   tile. Pre-v160 corpus archived as `failure_db_snapshot_sim_v159.jsonl`.
// v161 - Boosted Prime_Flamethrower adds Boost's +1 weapon damage to its
//   conditional FireDamage branch only when the target was already burning,
//   and powered Flame Thrower range IDs (`_A` / `_B` / `_AB`) are modeled.
//   Pre-v161 corpus archived as `failure_db_snapshot_sim_v160.jsonl`.
// v162 - Fire weapon tile status can live on Grid Buildings without damaging
//   them; upgraded Flame Thrower line paths ignite intermediate building tiles.
//   Pre-v162 corpus archived as `failure_db_snapshot_sim_v161.jsonl`.
// v163 - Breaking a web on one board entry clears every duplicate segment with
//   the same logical uid, matching multi-tile mission units such as trains.
//   Pre-v163 corpus archived as `failure_db_snapshot_sim_v162.jsonl`.
// v164 - FIRE weapon tile status can sit on intact Mountain tiles. Backburn
//   (`Ranged_Ignite_A`) lights the mountain directly behind the shooter without
//   damaging it. Pre-v164 corpus archived as `failure_db_snapshot_sim_v163.jsonl`.
// v165 - Science_Swap target relocation breaks the moved target's own web,
//   matching the engine rule that actual tile changes break grapples. Pre-v165
//   corpus archived as `failure_db_snapshot_sim_v164.jsonl`.
// v166 - Cataclysm squad weapons modeled: Hydraulic Lifter two-click throws,
//   Tri-Rocket's three sequential line hits, and Seismic Capacitor's on-kill
//   adjacent crack creation. Pre-v166 corpus archived as
//   `failure_db_snapshot_sim_v165.jsonl`.
// v167 - Tri-Rocket simultaneous damage+push cleanup: killed ACID units move
//   their corpse acid pool to the pushed destination, and later rockets bump
//   units entering a just-vacated killed-corpse tile. Pre-v167 corpus archived
//   as `failure_db_snapshot_sim_v166.jsonl`.
// v168 - Seismic Capacitor on-kill crack effect damages adjacent Mountains
//   by 1 HP instead of ignoring them. Pre-v168 corpus archived as
//   `failure_db_snapshot_sim_v167.jsonl`.
// v169 - Tri-Rocket killed adjacent missile targets corpse-bump live center
//   blockers when pushed into them. Pre-v169 corpus archived as
//   `failure_db_snapshot_sim_v168.jsonl`.
// v170 - Tri-Rocket targets killed by terrain after landing do not leave a
//   vacated corpse-bump tile. Pre-v170 corpus archived as
//   `failure_db_snapshot_sim_v169.jsonl`.
// v171 - VIP_Truck_Move is a range-3 path movement skill even though the VIP
//   Truck pawn has MoveSpeed=0. Solver/replay now enumerate and simulate the
//   skill as an attack-phase AddMove. Pre-v171 corpus archived as
//   `failure_db_snapshot_sim_v170.jsonl`.
// v172 - Tri-Rocket center targets inherit LineArtillery's range-2 minimum;
//   targeting an adjacent center tile spends the bridge action without an
//   engine effect. Pre-v172 corpus archived as
//   `failure_db_snapshot_sim_v171.jsonl`.
// v173 - Enemy-phase non-unique multi-HP bump grid debt now flushes before
//   returning to the next player turn, matching Tumblebug BombRock explosions
//   that damage 2-HP buildings. Pre-v173 corpus archived as
//   `failure_db_snapshot_sim_v172.jsonl`.
// v174 - Tri-Rocket center-hit BombRocks resolve as a forward killed-boulder
//   collision inside the rocket line, without emitting the normal side blast.
//   Matches Cataclysm Unfair stress run 20260521_120049_468 Mission_Lightning
//   turn 2, where B4 BombRock damaged B3->B2 Dung2 but not C4 Scorpion2.
//   Pre-v174 corpus archived as `failure_db_snapshot_sim_v173.jsonl`.
// v175 - Save-file upgraded weapon overlays now recognize Cataclysm powered
//   IDs (`Prime_TC_Punt_*`, `Ranged_Crack_*`, `Science_KO_Crack_*`), matching
//   live bridge execution after shop/reactor upgrades. Pre-v175 corpus
//   archived as `failure_db_snapshot_sim_v174.jsonl`.
// v176 - Python bridge reader reconciles save-stale per-unit DIR_FLIP targets
//   with live Board:IsTargeted markers before constructing solver input.
//   Pre-v176 corpus archived as `failure_db_snapshot_sim_v175.jsonl`.
// v177 - Mission_Wind raw engine WindDir is converted to the solver's
//   bridge-coordinate direction order before wind pushes. Pre-v177 corpus
//   archived as `failure_db_snapshot_sim_v176.jsonl`.
// v178 - Enemy queued-target origins are preserved through player-phase
//   displacement and DIR_FLIP retargets, and enemy Charge attacks now move the
//   charger along the charge path. Fixes a displaced Seismic-flipped Beetle
//   Leader charge in Cataclysm Unfair stress run 20260521_120049_468
//   Mission_BeetleBoss turn 2. Pre-v178 corpus archived as
//   `failure_db_snapshot_sim_v177.jsonl`.
// v179 - Hydraulic Lifter landing damage that ignites a Forest now immediately
//   sets fire on the thrown surviving unit. Fixes Cataclysm Unfair stress run
//   20260521_120049_468 Mission_Volatile turn 1, where Prime_TC_Punt_AB threw
//   Firefly2 onto E3 Forest and live set status.fire. Pre-v179 corpus archived
//   as `failure_db_snapshot_sim_v178.jsonl`.
// v180 - Mirror Shot killed forward targets still resolve the forward corpse
//   bump into live blockers. Fixes Frozen Titans Untouchable run
//   20260521_223240_242 Mission_Airstrike turn 1, where Brute_Mirrorshot killed
//   BonusDebris on F6 and live bumped IceMech on E6 for 1 HP. Pre-v180 corpus
//   archived as `failure_db_snapshot_sim_v179.jsonl`.
// v181 - Conveyor sprite directions from the engine are normalized to solver
//   DIRS before simulation. Fixes Rusting Hulks Untouchable run
//   20260521_232056_112 Mission_BeltRandom turn 1, where raw conveyor2 on C5
//   bumped PulseMech into B5 and cost 1 HP + 1 grid. Pre-v181 corpus archived
//   as `failure_db_snapshot_sim_v180.jsonl`.
// v184 - Webbed `Prime_Leap` / Hydraulic Legs no-ops like live instead of
//   jumping, self-damaging, and killing landing-adjacent units. Fixes Hazardous
//   Mechs Healing run 20260522_154935_555 Mission_Barrels turn 2, where a
//   webbed Leap Mech was asked to leap from C4 to B3 and live left the Leaper
//   alive. Pre-v184 corpus archived as `failure_db_snapshot_sim_v183.jsonl`.
// v185 - `Prime_Leap` / Hydraulic Legs target area is cardinal-line only,
//   matching Leap_Attack:GetTargetArea's DIR_VECTORS[i] * k enumeration.
//   Fixes the same Healing run Mission_Barrels turn 3, where E3->G4 ACKed
//   but live no-oped. Pre-v185 corpus archived as
//   `failure_db_snapshot_sim_v184.jsonl`.
// v186 - Passive_Leech / Viscera Nanobots heals player mechs after attack
//   kills, including Hazardous self-damage recoil that drops the attacker to
//   0 before the kill-heal revives it. Fixes Healing run
//   20260522_154935_555 Mission_Civilians turn 2, where Brute_Unstable killed
//   a Vek and live healed UnstableTank from recoil back to full. Pre-v186
//   corpus archived as `failure_db_snapshot_sim_v185.jsonl`.
// v187 - Science_AcidShot / Acid Projector direct off-board pushes do not
//   edge-bump, and the zero-damage ACID status is suppressed in that blocked
//   edge case. Fixes Healing run 20260522_154935_555 Mission_Civilians turn 4,
//   where Nano B2->A2 left a 1-HP Scarab alive and un-acidified. Pre-v187
//   corpus archived as `failure_db_snapshot_sim_v186.jsonl`.
// v188 - Science_AcidShot applies ACID but does not push hit units at all;
//   when the projectile endpoint is the map-edge tile in its fire direction,
//   the zero-damage ACID payload is still suppressed. Fixes the same Healing
//   run Mission_Belt turn 2, where Nano D4->E4 acidified the G4 Scarab but
//   live left it on G4 instead of pushing it to H4. Pre-v188 corpus archived
//   as `failure_db_snapshot_sim_v187.jsonl`.
// v189 - Science_AcidShot does push clean targets when ACID is newly applied,
//   but already-acid targets keep their tile and edge endpoints still no-op.
//   Fixes Healing run 20260522_154935_555 Corporate HQ turn 2, where Nano
//   G7->F7 pushed the Beetle Leader from E7 to D7. Pre-v189 corpus archived
//   as `failure_db_snapshot_sim_v188.jsonl`.
// v190 - Prime_Leap / Hydraulic Legs killed landing-adjacent targets still
//   resolve their outward corpse push into live blockers. Fixes Healing run
//   20260522_154935_555 Corporate HQ turn 3, where a killed Leaper on D4
//   corpse-bumped UnstableTank on D5. Pre-v190 corpus archived as
//   `failure_db_snapshot_sim_v189.jsonl`.
// v191 - Passive_Leech / Viscera Nanobots remains active even after the Nano
//   Mech is disabled. Fixes the same Healing run Corporate HQ turn 4, where
//   dead Nano's passive healed UnstableTank's recoil after killing Leaper1.
//   Pre-v191 corpus archived as `failure_db_snapshot_sim_v190.jsonl`.
// v192 - Wrecks block pushed units. Fixes the same Healing run Corporate HQ
//   turn 4, where Prime_Leap pushed an acid Beetle Leader into disabled Nano's
//   wreck on C7; live applied a bump and left the boss on C6. Pre-v192 corpus
//   archived as `failure_db_snapshot_sim_v191.jsonl`.
// v193 - Ignore stale teleporter pad pairs unless the active mission is
//   Mission_Teleporter. A stale pair leaked into Mission_AcidTank and made the
//   sim teleport Hazardous mechs after recoil/movement while the engine left
//   them in place. Pre-v193 corpus archived as
//   `failure_db_snapshot_sim_v192.jsonl`.
// v194 - Passive_Leech / Viscera Nanobots heal credit is limited to direct
//   weapon-damage kills. Hydraulic Legs edge-bump kills still count for score
//   and mission kills, but live did not heal the Leap Mech. Pre-v194 corpus
//   archived as `failure_db_snapshot_sim_v193.jsonl`.
// v195 - Science_AcidShot / Acid Projector still pushes an already-ACID target
//   when the push destination is legal; only the edge-endpoint zero-damage no-op
//   suppresses the direct push. Pre-v195 corpus archived as
//   `failure_db_snapshot_sim_v194.jsonl`.
// v196 - Prime_Leap / Hydraulic Legs resolves landing tile effects after Leap
//   self-damage, so Bethany's shield can be stripped before an ACID pool on the
//   landing tile applies. Pre-v196 corpus archived as
//   `failure_db_snapshot_sim_v195.jsonl`.
// v197 - Prime_Leap / Hydraulic Legs moves a killed ACID target's new pool with
//   the simultaneously-pushed corpse instead of leaving it on the damage tile.
//   Pre-v197 corpus archived as `failure_db_snapshot_sim_v196.jsonl`.
// v198 - Instant-killing a web source releases its grapple, Terraformer sweeps
//   clear grass on ACID ground without converting that tile to Sand, and replay
//   WId::None plan entries deactivate the skipped unit. Pre-v198 corpus
//   archived as `failure_db_snapshot_sim_v197.jsonl`.
// v199 - ACID death pools on Sand become Ground, and Brute_Unstable pushback
//   bump kills count as Viscera Nanobots killing blows. Pre-v199 corpus
//   archived as `failure_db_snapshot_sim_v198.jsonl`.
// v200 - Weapon damage that kills a pawn standing on cracked Ground leaves the
//   tile cracked; only direct damage to the empty tile opens a chasm. Pre-v200
//   corpus archived as `failure_db_snapshot_sim_v199.jsonl`.
// v201 - The occupied-crack exception is weapon-damage-only; self-damage such
//   as Hydraulic Legs recoil still collapses cracked Ground under the mech.
//   Pre-v201 corpus archived as `failure_db_snapshot_sim_v200.jsonl`.
// v202 - Brute_Unstable recoil still bumps a live rear blocker even when
//   Hazardous self-damage has dropped the attacker to 0 before Viscera
//   Nanobots revives it. Pre-v202 corpus archived as
//   `failure_db_snapshot_sim_v201.jsonl`.
// v203 - Prime_Leap / Hydraulic Legs damage collapses occupied cracked
//   landing-adjacent tiles, and Viscera Nanobots cannot revive a mech killed by
//   chasm/water/lava terrain under its own tile. Pre-v203 corpus archived as
//   `failure_db_snapshot_sim_v202.jsonl`.
// v204 - Bump/collision damage to a pawn standing on cracked Ground is
//   absorbed by the pawn and does not open a chasm under the occupied tile.
//   Pre-v204 corpus archived as `failure_db_snapshot_sim_v203.jsonl`.
// v205 - Brute_Unstable direct weapon kills do not synthesize a corpse ACID
//   pool on the target tile. Pre-v205 corpus archived as
//   `failure_db_snapshot_sim_v204.jsonl`.
// v206 - Ground Prime_Leap / Hydraulic Legs cannot land on Water or Lava;
//   live consumes the click as an unfired action. Pre-v206 corpus archived as
//   `failure_db_snapshot_sim_v205.jsonl`.
// v207 - Prime_Leap / Hydraulic Legs applies Viscera Nanobots revive before
//   landing tile fire/ACID pickup, after self-damage. Pre-v207 corpus archived
//   as `failure_db_snapshot_sim_v206.jsonl`.
// v208 - Viscera Nanobots revive clears negative statuses carried by the
//   temporarily disabled mech before any later landing effects can reapply
//   them. Pre-v208 corpus archived as `failure_db_snapshot_sim_v207.jsonl`.
// v209 - Brute_Unstable recoil still bumps live rear blockers, but recoil into
//   the board edge does not self-bump. Fixes Healing run 20260522_193613_471
//   Mission_Volatile turn 2, where edge recoil was over-predicted by 1 HP.
//   Pre-v209 corpus archived as `failure_db_snapshot_sim_v208.jsonl`.
// v210 - Mission_Dam flood clears tile fire when it converts a burning Forest
//   to Water. Fixes Healing run 20260522_193613_471 Mission_Dam turn 2, where
//   a Leap-ignited flooded tile was predicted as water+fire. Pre-v210 corpus
//   archived as `failure_db_snapshot_sim_v209.jsonl`.
// v211 - Brute_Unstable killed direct targets still resolve their forward
//   corpse push into live blockers. Fixes Healing run 20260522_193613_471
//   Mission_BlobberBoss turn 2, where a killed BlobB corpse bumped NanoMech.
//   Pre-v211 corpus archived as `failure_db_snapshot_sim_v210.jsonl`.
// v212 - Weapon/bump-class damage to a pawn standing on Ice is pawn-only: it
//   can damage/kill/push the pawn, but does not crack or melt the underlying
//   ice tile. Pre-v212 corpus archived as `failure_db_snapshot_sim_v211.jsonl`.
// v213 - Brute_Unstable self-damage on an Ice firing tile applies its HP hit
//   first, then resolves the origin tile as Water after recoil. Fixes Healing
//   run 20260522_193613_471 Mission_Survive turn 2, where D5 flooded after
//   Unstable recoiled to D6. Pre-v213 corpus archived as
//   `failure_db_snapshot_sim_v212.jsonl`.
// v214 - Reverts the v213 overgeneralization for intact Brute_Unstable ice
//   origins, and models Hydraulic Legs breaking occupied Ice only when the
//   hit pawn is grounded. Flying targets still leave occupied Ice intact.
//   Fixes Healing run 20260522_193613_471 Mission_Survive turn 3, where
//   Beetle2 on F5 left Water after Leap push, while Unstable's intact E4
//   firing tile stayed Ice. Pre-v214 corpus archived as
//   `failure_db_snapshot_sim_v213.jsonl`.
// v215 - Hydraulic Legs only breaks occupied Ice after a grounded target is
//   actually displaced off the original tile. A blocked push/corpse bump leaves
//   the occupied Ice intact. Fixes Healing run 20260522_193613_471 Pinnacle
//   Mission_Factory turn 4, where Leaper1 died on C3 but the C2 blocker kept
//   the corpse on intact Ice. Pre-v215 corpus archived as
//   `failure_db_snapshot_sim_v214.jsonl`.
// v216 - Hydraulic Legs friendly landing-adjacent pushes can enter an existing
//   dead-unit/wreck tile without taking the normal wreck bump. Fixes Healing run
//   20260522_193613_471 Pinnacle Mission_FreezeMines turn 2, where Leaper1 was
//   already dead on F2 and UnstableTank later moved E2->F2. Pre-v216 corpus
//   archived as `failure_db_snapshot_sim_v215.jsonl`.
// v217 - Long Hydraulic Legs jumps also damage interior transit units with
//   acid/armor-ignoring pass-over damage. Hydraulic Legs-triggered BombRock
//   blasts exclude the landing Leap Mech. Fixes Healing run
//   20260522_193613_471 Pinnacle Mission_SnowStorm turn 2, where Leap E1->E6
//   damaged acid Dung2 on E4 by 1 HP and detonated E5 BombRock without
//   blast-damaging Leap. Pre-v217 corpus archived as
//   `failure_db_snapshot_sim_v216.jsonl`.
// v218 - Hydraulic Legs Nanobots healing caps at the engine/base mech HP, but
//   direct Unstable Cannon kills can still heal recoil back to the save-overlaid
//   max HP. Fixes the same Mission_SnowStorm turn 2, where Leap stayed 4/5
//   after killing Leaper1 while UnstableTank healed its Dung2 kill back to 5/5.
//   Pre-v218 corpus archived as `failure_db_snapshot_sim_v217.jsonl`.
// v219 - Long Hydraulic Legs pass-over damage skips the first transit tile next
//   to the takeoff point as well as the final pre-landing tile. Fixes Healing
//   run 20260522_193613_471 Pinnacle Mission_SnowStorm turn 4, where Leap
//   jumped C4->F4 and live left Mosquito1 on D4 at 2/2. Pre-v219 corpus
//   archived as `failure_db_snapshot_sim_v218.jsonl`.
// v220 - Removes synthetic Prime_Leap transit damage entirely; vanilla
//   Hydraulic Legs only damages landing-adjacent tiles plus recoil. Also makes
//   Brute_Unstable direct target pushes omit off-board edge-bump damage. Fixes
//   Healing run 20260522_193613_471 Corporate HQ turn 1, where Blood Psion and
//   Mosquito Leader both survived at 1 HP. Pre-v220 corpus archived as
//   `failure_db_snapshot_sim_v219.jsonl`.
// v221 - Hydraulic Legs push kills into deadly terrain credit Viscera
//   Nanobots healing, and occupied Ice stays intact when the pushed target dies
//   after displacement. Fixes Healing run 20260522_193613_471 Corporate HQ
//   turn 4, where a Beetle pushed from B2 into water died, Leap healed to 5/5,
//   and B2 stayed Ice. Pre-v221 corpus archived as
//   `failure_db_snapshot_sim_v220.jsonl`.
// v222 - Models powered `Prime_Leap_A/B/AB` and `Brute_Unstable_A/B/AB`
//   loadout IDs from save overlays. Fixes Healing run 20260522_193613_471
//   Volcanic Hive turn 1, where live fired `Brute_Unstable_AB` and its extra
//   self-damage plus recoil bump left UnstableTank at 4 HP. Pre-v222 corpus
//   archived as `failure_db_snapshot_sim_v221.jsonl`.
// v223 - Viscera Nanobots heals self-damage overkill from HP floor 0, and
//   Unstable Cannon recovery preserves carried statuses. Fixes Healing run
//   20260522_193613_471 Volcanic Hive turn 4, where burning UnstableTank fired
//   `Brute_Unstable_AB` at 1 HP, killed Jelly_Lava1, and live ended at 2 HP
//   still burning. Pre-v223 corpus archived as
//   `failure_db_snapshot_sim_v222.jsonl`.
// v224 - Acid Projector can push a live enemy into an existing dead enemy
//   wreck without bump damage. Fixes Healing run 20260522_193613_471 Final
//   Cave turn 3, where NanoMech pushed Hornet1 into dead Scarab1's tile and
//   live left Hornet1 alive at 1 HP. Pre-v224 corpus archived as
//   `failure_db_snapshot_sim_v223.jsonl`.
// v225 - Spawn blocking now records every occupied emergence tile before
//   resolving shield/frozen/damage, and terminal scoring credits blockers
//   destroyed by emergence damage. This makes 1 HP RockThrown blockers count
//   toward spawn-block achievements such as Blitzkrieg's Hold the Line.
//   Pre-v225 corpus archived as `failure_db_snapshot_sim_v224.jsonl`.
// v226 - Spider Psion death eggs use live-style adjacent fallback if a pushed
//   corpse retargets the egg to water/chasm/lava or another unspawnable tile.
//   Fixes Blitzkrieg run 20260524_112729_036 Mission_AcidStorm turn 3, where
//   the live bridge spawned SpiderlingEgg1 uid 530 after Rock Accelerator
//   pushed a killed Scorpion corpse onto water. Pre-v226 corpus archived as
//   `failure_db_snapshot_sim_v225.jsonl`.
// v227 - AE Totem/Spore attacks fire at the queued-time projectile endpoint
//   and then self-destruct, instead of re-tracing through post-player blockers
//   or falling back to generic unmapped Vek behavior. Fixes Blitzkrieg run
//   20260524_112729_036 Mission_Barrels turn 3, where TotemAtk1 destroyed
//   the G6 building after WallMech moved onto G5. Pre-v227 corpus archived as
//   `failure_db_snapshot_sim_v226.jsonl`.
// v228 - Killing a Blast Psion clears the explode-on-death aura before later
//   Chain Whip hits in the same target-first chain resolve. Pre-v228 corpus
//   archived as `failure_db_snapshot_sim_v227.jsonl`.
// v229 - Destroyed objective building ruins (terrain=Building, HP 0) block
//   Brute_Grapple/Pull target scans instead of letting Hook target a pawn
//   behind the ruin. Pre-v229 corpus archived as
//   `failure_db_snapshot_sim_v228.jsonl`.
// v230 - Pull replay/execution also stops when an old/invalid target names a
//   pawn behind a destroyed objective building ruin, so the simulator does not
//   pull through the first projectile blocker. Pre-v230 corpus archived as
//   `failure_db_snapshot_sim_v229.jsonl`.
// v231 - Cryo-Launcher self-freeze now applies freeze tile cleanup at the
//   shooter's tile, clearing carried fire and extinguishing burning ground.
//   Pre-v231 corpus archived as `failure_db_snapshot_sim_v230.jsonl`.
// v232 - Save-file upgraded overlays now model Janus Cannon damage upgrades
//   and Spartan Shield damage upgrades, so powered Brute_Mirrorshot_A/B/AB and
//   Prime_ShieldBash_B/AB solve with live damage. Pre-v232 corpus archived as
//   `failure_db_snapshot_sim_v231.jsonl`.
// v233 - Breaking one web source now reattaches a webbed unit to another live
//   queued web source targeting the same tile instead of clearing WEB outright.
//   Fixes Random Squad Change the Odds run 20260527_152006_916 Mission_Mines
//   turn 4, where Combat Mech killed the F2 Scorpion but remained webbed by
//   the E1 Scorpion. Pre-v233 corpus archived as
//   `failure_db_snapshot_sim_v232.jsonl`.
// v234 - Plain Titan Fist killed-target pushes can corpse-bump a live blocker,
//   matching Dash Punch corpse-bump policy. Fixes Random Squad Change the Odds
//   run 20260527_152006_916 Corporate HQ turn 1, where a killed Blob corpse
//   bumped Boulder Mech at A6. Pre-v234 corpus archived as
//   `failure_db_snapshot_sim_v233.jsonl`.
// v235 - Add Brute_PierceShot / AP Cannon coverage for Pierce Mech.
//   Pre-v235 corpus archived as `failure_db_snapshot_sim_v234.jsonl`.
// v236 - AP Cannon resolves the second target damage/push before moving the
//   first target, so adjacent targets do not take ordinary collision bump
//   damage from each other. Fixes Loot Boxes run 20260530_124216_453 mission 1
//   turn 1. Pre-v236 corpus archived as `failure_db_snapshot_sim_v235.jsonl`.
// v237 - Repair platforms do not trigger for hostile units. Fixes Loot Boxes
//   run 20260530_124216_453 Mission_Repair turn 2, where Vice Fist threw
//   Firefly1 onto a repair platform and live left it unhealed. Pre-v237 corpus
//   archived as `failure_db_snapshot_sim_v236.jsonl`.
// v238 - Pushed projectile Vek whose bridge queued target equals queued origin
//   infer direction from current position. Fixes Frozen Titans Trick Shot run
//   20260601_105838_091 Mission_Power turn 2, where Firefly1 still shot
//   MirrorMech after Mirror Shot displacement. Pre-v238 corpus archived as
//   `failure_db_snapshot_sim_v237.jsonl`.
// v239 - Mirror Shot backward arm with no blocker still damages adjacent empty
//   sand, converting it to smoked ground. Fixes Frozen Titans Trick Shot run
//   20260601_105838_091 Mission_Bomb turn 1, where Brute_Mirrorshot_A smoked
//   H6 behind MirrorMech. Pre-v239 corpus archived as
//   `failure_db_snapshot_sim_v238.jsonl`.
// v240 - Freezing an enemy web source releases units webbed by that source.
//   Fixes Frozen Titans Trick Shot run 20260601_105838_091 Mission_Bomb turn
//   4, where Cryo-Launcher froze a Leaper but the sim left ProtoBomb webbed.
//   Pre-v240 corpus archived as `failure_db_snapshot_sim_v239.jsonl`.
// v241 - BombRock blast damage uses bump-class unit math while still
//   converting adjacent occupied sand to smoked ground. Fixes Frozen Titans
//   Trick Shot run 20260601_105838_091 Mission_Cataclysm turn 1, where
//   Shield Bash destroyed a BombRock beside a Dung on sand. Pre-v241 corpus
//   archived as `failure_db_snapshot_sim_v240.jsonl`.
// v242 - Mirror Shot defers a killed forward BombRock blast until after its
//   push/bump resolution. Fixes Frozen Titans Trick Shot run
//   20260601_105838_091 Mission_Filler turn 2, where a frozen Ice Mech behind
//   the rock thawed from the push before taking BombRock blast damage.
//   Pre-v242 corpus archived as `failure_db_snapshot_sim_v241.jsonl`.
// v243 - Mirror Shot backward arm affects only the adjacent rear tile; it does
//   not skip an empty adjacent tile to hit a farther blocker. Fixes Frozen
//   Titans Trick Shot run 20260601_105838_091 Corporate HQ turn 4, where E2->D2
//   killed the forward Jelly at B2 but did not hit the Moth at G2 through
//   empty F2. Pre-v243 corpus archived as `failure_db_snapshot_sim_v242.jsonl`.
// v244 - Mirror Shot backward arm can still skip an empty adjacent tile to hit
//   a farther terrain blocker, while preserving v243's non-adjacent-pawn miss.
//   Fixes Frozen Titans Trick Shot run 20260601_154715_670 Disposal Site C turn
//   3, where E7->D7 destroyed the G7 building through empty F7. Pre-v244 corpus
//   archived as `failure_db_snapshot_sim_v243.jsonl`.
// v245 - Mirror Shot backward arm can also skip empty rear tiles to a farther
//   pawn when the forward arm hit was adjacent. Preserves v243's long-forward
//   non-adjacent-pawn miss. Fixes Frozen Titans Trick Shot run
//   20260601_154715_670 Chemical Field A turn 3, where D6->D7 hit D3 Mosquito
//   and bumped frozen D2 Bouncer. Pre-v245 corpus archived as
//   `failure_db_snapshot_sim_v244.jsonl`.
// v246 - Frozen units absorb weapon terrain ignition on their occupied Forest
//   tile. Fixes Frozen Titans Trick Shot run 20260601_174638_420
//   Mission_Survive turn 4, where Mirror Shot thawed/pushed IceMech off E6
//   but live left E6 as unburned Forest. Pre-v246 corpus archived as
//   `failure_db_snapshot_sim_v245.jsonl`.
// v247 - Mirror Shot backward arm skips adjacent rear sand to hit a farther
//   pawn even when the forward hit was non-adjacent, and leaves the skipped
//   sand unchanged. Fixes Frozen Titans Trick Shot run 20260601_174638_420
//   Mission_Filler turn 3, where Brute_Mirrorshot_A killed IceMech at E8
//   through empty sand E7. Pre-v247 corpus archived as
//   `failure_db_snapshot_sim_v246.jsonl`.
// v248 - Mirror Shot backward arm also skips adjacent rear conveyor tiles to a
//   farther pawn. Fixes Frozen Titans Trick Shot run 20260601_221405_894
//   Mission_BeltRandom turn 4, where Brute_Mirrorshot_A killed IceMech at D8
//   through conveyor D7. Pre-v248 corpus archived as
//   `failure_db_snapshot_sim_v247.jsonl`.
// v249 - Mission_Tides applies queued Vek attacks before the tidal wave, and
//   flying units on a tide tile take 1 damage instead of being fully spared.
//   Pre-v249 corpus archived as failure_db_snapshot_sim_v248.jsonl.
// v250 - Python verify loop matches Spider Psion death eggs by type+tile when
//   the live engine allocates a different UID than the simulator. Fixes Frozen
//   Titans Trick Shot run 20260601_221405_894 Mission_Solar turn 3, where
//   Mirror Shot correctly produced a SpiderlingEgg1 at D5 but live used
//   uid 1904 instead of predicted uid 1902. Pre-v250 corpus archived as
//   failure_db_snapshot_sim_v249.jsonl.
// v251 - Per-sub-action move verification tolerates the live bridge keeping a
//   Time Pod visible under the moved mech until the action finishes. Full
//   post-action verification still catches unrecovered or destroyed pods.
//   Fixes Frozen Titans Trick Shot run 20260601_221405_894 Mission_Solar
//   turn 3. Pre-v251 corpus archived as failure_db_snapshot_sim_v250.jsonl.
// v252 - Mirror Shot direct projectile pushes at the off-board edge deal only
//   Janus weapon damage, matching live Scarab2 survival on Mission_Final turn
//   3. On-board live-blocker corpse bumps remain enabled. Pre-v252 corpus
//   archived as failure_db_snapshot_sim_v251.jsonl.
// v253 - Cryo-Launcher self-freeze is suppressed when the flying IceMech fires
//   while over water; the target still freezes, but IceMech stays unfrozen and
//   the water tile remains water. Fixes Mission_Final_Cave turn 1 in Trick
//   Shot run 20260601_221405_894. Pre-v253 corpus archived as
//   failure_db_snapshot_sim_v252.jsonl.
// v254 - Direct non-shield hits refresh existing fire-tile pickup for the
//   occupant. Fixes Frozen Titans Trick Shot run 20260602_095732_968
//   Mission_Armored_Train turn 2, where Prime_ShieldBash hit a Moth standing
//   on fire and live set status.fire. Pre-v254 corpus archived as
//   failure_db_snapshot_sim_v253.jsonl.
// v255 - Cryo-Launcher self-freeze suppression over water is limited to the
//   observed Mission_Final_Cave case; Mission_Tides water still freezes the
//   flying IceMech and turns its tile to ice. Fixes Frozen Titans Trick Shot
//   run 20260602_095732_968 Mission_Tides turn 2. Pre-v255 corpus archived as
//   failure_db_snapshot_sim_v254.jsonl.
// v256 - Weapon damage that ignites an occupied Forest immediately applies
//   fire status to the surviving occupant. Fixes Frozen Titans Trick Shot run
//   20260602_095732_968 Corporate HQ turn 4, where Prime_ShieldBash hit a
//   Firefly on Forest and live set status.fire. Pre-v256 corpus archived as
//   failure_db_snapshot_sim_v255.jsonl.
// v257 - Spartan Shield direct hits collapse occupied cracked Ground into a
//   chasm, killing grounded targets and clearing webs when the hit kills a
//   webber. Fixes Frozen Titans Trick Shot run 20260602_095732_968 R.S.T.
//   Mission_Crack turn 3, where Prime_ShieldBash hit a Scorpion on cracked
//   Ground. Pre-v257 corpus archived as failure_db_snapshot_sim_v256.jsonl.
// v258 - Weapon damage to a live enemy web source clears/reassigns that web
//   even if the webber survives. Fixes Frozen Titans Trick Shot run
//   20260602_095732_968 Mission_Solar turn 3, where Prime_ShieldBash damaged
//   a Scorpion web source for 2, live cleared Guard's web, and the Scorpion
//   survived at 1 HP. Pre-v258 corpus archived as
//   failure_db_snapshot_sim_v257.jsonl.
// v259 - Mission_Tides turn projection/replay advances the tidal warning mask
//   to the next player turn so plan safety blocks mechs parked on the next
//   wave lane. Fixes Lightning War run 20260603 Mission_Tides turn 2, where
//   Electric and Rockart ended on the next tide lane and Electric was webbed
//   by a spawned Leaper. Pre-v259 corpus archived as
//   failure_db_snapshot_sim_v258.jsonl.
// v260 - Rock Launcher empty-target rock spawns do not apply center terrain
//   damage. Live preserves Forest/no fire under the spawned RockThrown. Fixes
//   Lightning War run 20260610_184414_692 Archive Mission_Mines turn 1, where
//   Ranged_Rockthrow at E3 spawned a rock but left the forest intact. Pre-v260
//   corpus archived as failure_db_snapshot_sim_v259.jsonl.
// v261 - Brute_Grapple full-pull transit skips Old Earth / freeze mine
//   triggers until the final resting tile. Fixes Lightning War run
//   20260610_222220_354 Mission_Mines turn 1, where Hook pulled a flying
//   Jelly_Regen1 across an intermediate Old Earth Mine and live left it alive.
//   Pre-v261 corpus archived as failure_db_snapshot_sim_v260.jsonl.
// v262 - Old Earth Artillery damage does not release a surviving enemy web
//   source. Fixes Lightning War run 20260610_222220_354 Archive
//   Mission_Artillery turn 4, where ArchiveArtillery damaged a Scorpion web
//   source but ElectricMech stayed webbed. Pre-v262 corpus archived as
//   failure_db_snapshot_sim_v261.jsonl.
// v263 - Bomb Dispenser / Walking Bomb support for Bombermechs Powered Blast:
//   line-artillery ground deploy target, spawned temporary Walking Bomb, and
//   Trigger self-destruct AoE. Pre-v263 corpus archived as
//   failure_db_snapshot_sim_v262.jsonl.
// v264 - Powered Blast achievement event and scoring hook for AP Cannon kills
//   through Walking Bomb. Pre-v264 corpus archived as
//   failure_db_snapshot_sim_v263.jsonl.
// v265 - Brute_Grapple full-pull stops before dead unit wrecks without bump
//   damage. Fixes Lightning War run 20260613_002031_059 Mission_Survive turn 1,
//   where Hook over-killed a Leaper against a wreck and the survivor destroyed
//   ElectricMech after End Turn. Pre-v265 corpus archived as
//   failure_db_snapshot_sim_v264.jsonl.
// v266 - Brute_KickBack / Reverse Thrusters modeled as a dash-away weapon:
//   clicked landing tile, distance-scaled damage and smoke on the reverse tile,
//   fixed 1 self-damage, attack-phase landing effects, upgraded range IDs, and
//   the On the Backburner 4+ effective-damage achievement event. Pre-v266
//   corpus archived as failure_db_snapshot_sim_v265.jsonl.
// v267 - Ranged_SmokeFire / Smoldering Shells adjacent smoke skips occupied
//   adjacent tiles; live Backburner run showed an occupied adjacent Scarab was
//   not smoke-cancelled. Pre-v267 corpus archived as
//   failure_db_snapshot_sim_v266.jsonl.
// v268 - Passive_HealingSmoke / Nanofilter Mending is parsed from bridge
//   weapons and consumes smoke under player mechs to heal 1 HP. Reverse
//   Thrusters now places source smoke instead of impact smoke, matching live
//   Backburner damage_amount desyncs. Pre-v268 corpus archived as
//   failure_db_snapshot_sim_v267.jsonl.
// v269 - Heat Sinkers weapon coverage: Quick-Fire Rockets, Thermal
//   Discharger, and Firestorm Generator IDs, line/fire simulation, and the
//   Feed the Flame fresh-ignition achievement event. Pre-v269 corpus archived
//   as failure_db_snapshot_sim_v268.jsonl.
// v270 - Dam flood destroys Time Pods on flooded tiles without collection
//   credit. Fixes Bombermechs Complete Victory run 20260619_234224_725
//   Mission_Dam turn 1, where live washed away a pod at (4,5) but Rust kept
//   has_pod=true. Pre-v270 corpus archived as failure_db_snapshot_sim_v269.jsonl.
// v271 - Old Earth Mine mission metadata and replay safety track
//   Mission_Mines' mech-damage objective so Complete Victory routing does not
//   misclassify mine damage as harmless. Pre-v271 corpus archived as
//   failure_db_snapshot_sim_v270.jsonl.
// v272 - AP Cannon first-target push can move a friendly first target into a
//   killed second target's tile instead of treating the dead Vek as a bumping
//   wreck. Fixes Bombermechs Complete Victory run 20260623_014749_422
//   Mission_Mines turn 4. Pre-v272 corpus archived as
//   failure_db_snapshot_sim_v271.jsonl.
// v273 - Enemy-phase replay honors bridge-provided attack order instead of
//   blindly sorting by UID. Fixes Bombermechs Complete Victory run
//   20260623_035936_734 Mission_Factory turn 2, where live Snowlaser fired
//   before a lower-UID Burnbug killed it. Pre-v273 corpus archived as
//   failure_db_snapshot_sim_v272.jsonl.
// v274 - Mission_Repair platform healing caps at the unit's max HP instead
//   of overhealing to max_hp+2. Fixes Bombermechs Complete Victory run
//   20260623_105703_708 Bad Repairs turn 1, where BomlingMech healed from
//   1/3 to live 3/3 but the sim projected 5/3. Pre-v274 corpus archived as
//   failure_db_snapshot_sim_v273.jsonl.
// v275 - Science_TC_SwapOther Force Swap is a first-class two-target action:
//   solver/replay/bridge JSON carry target2, and the simulator swaps the
//   adjacent first target with the second target plus A/B upgrade effects.
//   Pre-v275 corpus archived as failure_db_snapshot_sim_v274.jsonl.
// v276 - A queued shot normalized off-board by the bridge is a canceled attack,
//   not an unknown phantom attack. This prevents conservative phantom damage
//   after Force Swap moves artillery Vek so their preserved offset points off
//   the board. Pre-v276 corpus archived as failure_db_snapshot_sim_v275.jsonl.
// v277 - AP Cannon's second-target damage does not receive generic Boost and
//   its direct edge push does not add off-board bump damage. Fixes
//   Bombermechs Complete Victory run 20260623_105703_708 Mission_ScarabBoss
//   turn 4, where upgraded AP left the Scarab Leader at 1 HP live but Rust
//   predicted a kill. Pre-v277 corpus archived as
//   failure_db_snapshot_sim_v276.jsonl.
// v278 - Standard melee Vek can recover direction from their current tile
//   when Force Swap relocates them and the bridge updates queued_target but
//   leaves queued_origin stale. Fixes Bombermechs Complete Victory run
//   20260624_083454_845 Mission_Lightning turn 1, where a swapped Bouncer
//   killed ExchangeMech live but Rust dropped the diagonal stale-origin
//   attack.
// v280 - Mission_Shields generator shields absorb damage and push without
//   being consumed while the Shield_Building is alive, then clear when the
//   generator dies. Fixes Arachnophiles Spider Breeding run
//   20260624_150610_500 Mission_Shields turn 1.
// v281 - Ricochet Rocket is modeled and executed as a real two-click bounce
//   instead of the old bridge one-click no-op path. Fixes Arachnophiles Spider
//   Breeding run 20260624_150610_500 Mission_Shields turn 2.
// v282 - Webbed Ricochet Rocket is treated as a no-op and omitted from solve
//   enumeration, matching the same Mission_Shields turn 2 live bridge result.
// v283 - Mission_Shields generator protection is implicit for non-generator
//   enemies/buildings while Shield_Building is alive, even when the bridge
//   snapshot lacks individual shield bits. Fixes the same turn 2 Arachnoid
//   Injector hit on Scorpion1 at F2.
// v284 - Arachnoid Injector is cardinal-line artillery. Off-axis bridge
//   FireWeapon calls can ACK and spend the action while doing no damage.
// v285 - Raw queued targets are preserved as a fallback when normalized enemy
//   targets collapse to origin/current, fixing BurnbugBoss post-enemy grid
//   prediction in Arachnophiles Spider Breeding run 20260624_184517_189.
//   ACID Arachnoid self-destruct also leaves an ACID pool on its death tile.
// v286 - Merged Heat Sinkers Feed the Flame parity onto the Complete
//   Victory/Spider line: Heat Engines fire/lava Boost consumption, Firestorm
//   endpoint/pod behavior, Thermal Discharger dam-flood ordering,
//   Mission_BeltRandom late conveyor timing, and Mission_Satellite late launch
//   threat timing. Pre-v286 corpus archived as failure_db_snapshot_sim_v285.jsonl.
// v287 - Merged Lightning War / Stay With Me parity onto the Complete
//   Victory/Spider/Feed line: Dam_Pawn fire-tick skip, Reverse Thrusters
//   backblast smoke without same-action Nanofilter recoil healing,
//   Smoldering Shells A/B/AB overlays, pre-attack enemy wreck clearing,
//   RockThrown pod destruction, Chain Whip Shell Psion armor snapshotting,
//   and Stay With Me heal scoring. Pre-v287 corpus archived as
//   failure_db_snapshot_sim_v286.jsonl.
// v288 - Control Shot is modeled as a two-click target-unit/destination
//   forced movement, including webbed controlled movement and Let's Walk enemy
//   movement-distance events. Pre-v288 corpus archived as
//   failure_db_snapshot_sim_v287.jsonl.
// v289 - Projected board safety now sees Rust project_plan board_json in the
//   Python loop, and environment hazards destroy Time Pods on affected tiles.
//   Fixes Mission_Tides preserving a pod and missing next-wave mech danger in
//   Mist Eaters Let's Walk run 20260627_104252_085. Pre-v289 corpus archived
//   as failure_db_snapshot_sim_v288.jsonl.
// v290 - Control Shot powered variants A/B/AB are modeled with 3/3/4 tile
//   controlled-move budgets for Let's Walk farming. Pre-v290 corpus archived
//   as failure_db_pre_v290_lets_walk_control_shot_upgrades.jsonl.
// v291 - Control Shot first-click target units must be within the weapon range;
//   raw bridge GetFinalEffect can otherwise move targets the live UI refuses.
//   Pre-v291 corpus archived as failure_db_pre_v291_control_shot_target_range.jsonl.
// v292 - Control Shot target enumeration/replay is enemy-only for Let's Walk;
//   allied target attempts do not earn progress and can miss in the live UI path.
//   Pre-v292 corpus archived as failure_db_pre_v292_control_shot_enemy_targets.jsonl.
// v293 - Control Shot first-click target units must be in a straight firing
//   line from the Control Mech; diagonal in-range targets are visible UI misses.
//   Pre-v293 corpus archived as failure_db_pre_v293_control_shot_line_targets.jsonl.
// v294 - Control Shot first-click target units must be the first projectile
//   blocker in that line; buildings/mountains/units can obstruct the visible UI.
//   Pre-v294 corpus archived as failure_db_pre_v294_control_shot_projectile_blockers.jsonl.
// v295 - Control Shot first-click target units are adjacent-only; weapon
//   upgrades still increase only the controlled enemy move budget.
//   Pre-v295 corpus archived as failure_db_pre_v295_control_shot_adjacent_target.jsonl.
// v296 - Smoldering Shells skips the inbound projectile tile for range-2 shots.
//   Pre-v296 corpus archived as failure_db_pre_v296_smoldering_shells_inbound_smoke.jsonl.
// v297 - Mission_Barrels AcidVat deaths leave water+ACID runoff terrain.
//   Pre-v297 corpus archived as failure_db_snapshot_sim_v296.jsonl.
// v298 - Spawned enemies, including Spider Psion death eggs, inherit tile Fire.
//   Pre-v298 corpus archived as failure_db_snapshot_sim_v297.jsonl.
// v299 - Boosted Reverse Thrusters adds +1 distance damage and boosted recoil,
//   matching Mist Eaters Let's Walk run 20260628_101633_260 Mission_Disposal
//   turn 1. Pre-v299 corpus archived as failure_db_snapshot_sim_v298.jsonl.
// v300 - Smoldering Shells skips the inbound projectile tile on even-range
//   shots, not only range 2. Pre-v300 corpus archived as
//   failure_db_snapshot_sim_v299.jsonl.
// v301 - Ranged_SmokeFire skipped occupied adjacent tiles no longer clear
//   carried fire. Live Let's Walk Mission_Belt turn 3 left burning Control
//   Mech on an occupied adjacent tile after Smoldering Shells. Pre-v301 corpus
//   archived as failure_db_snapshot_sim_v300.jsonl.
// v302 - Ground movement BFS treats other live friendly units as hard blockers
//   instead of walk-through tiles. Live Let's Walk Mission_Terraform turn 2
//   refused SmokeMech pathing through the Terraformer. Pre-v302 corpus archived
//   as failure_db_snapshot_sim_v301.jsonl.
// v303 - Smoke placed directly onto an occupied tile clears the occupant's
//   carried fire without applying Nanofilter healing. Live Let's Walk
//   Mission_Terraform turn 4 left the Reverse Thrusters backblast Firefly
//   not-on-fire after the hit tile was smoked. Pre-v303 corpus archived as
//   failure_db_snapshot_sim_v302.jsonl.
// v304 - Smoldering Shells damage does not release a surviving enemy web
//   source. Fixes Mist Eaters Let's Walk run 20260629_021050_272 Archive
//   Mission_Mines turn 2, where Smoldering Shells damaged a Scorpion web
//   source but Needle stayed webbed. Pre-v304 corpus archived as
//   failure_db_snapshot_sim_v303.jsonl.
// v305 - Smoldering Shells smoke footprint matches live Lua: base smokes only
//   the two side tiles, while More Smoke smokes all four cardinal neighbors
//   without diagonals. Fixes Mist Eaters Let's Walk run 20260629_073305_098
//   Mission_Barrels turn 1 D6 far-tile smoke drift. Pre-v305 corpus archived
//   as failure_db_snapshot_sim_v304.jsonl.
// v306 - AP Cannon killed ACID second targets still resolve corpse-bump damage
//   into a live blocker and leave an ACID pool for a friendly first target
//   entering the wreck tile. Friendly first targets also collide with adjacent
//   live second targets before the second target vacates when the second target
//   survives AP damage. Fixes Hold the Door run 20260629_190949_968 Mission_Acid
//   turn 4 and Mission_Survive turn 3. Pre-v306 corpus archived as
//   failure_db_snapshot_sim_v305.jsonl.
// v307 - AP Cannon delays Mission_Barrels AcidVat death-terrain until after
//   the first target push. Live lets an enemy first target enter the killed
//   vat tile alive before the tile becomes ACID water. Fixes Hold the Door run
//   20260629_205354_395 Mission_Barrels turn 1. Pre-v307 corpus archived as
//   failure_db_snapshot_sim_v306.jsonl.
// v308 - Tri-Rocket direct pushes into the map edge do not add off-board edge
//   bump damage, while later rockets can still bump another unit into that
//   target. Fixes Cataclysm Core run 20260630_143648_199 Corporate HQ turn 1,
//   where the Mosquito Leader survived at 1 HP. Pre-v308 corpus archived as
//   failure_db_snapshot_sim_v307.jsonl.
// v309 - Enemy-attack smoke cancellation uses smoke present before the queued
//   attack loop, so smoke created by an earlier enemy attack does not cancel a
//   later already-queued attack. Fixes Bombermechs No Survivors run
//   20260630_181556_177 Mission_Missiles turn 3. Pre-v309 corpus archived as
//   failure_db_snapshot_sim_v308.jsonl.
// v310 - Detritus Contraption action enumeration honors Missile_Unit
//   IgnoreSmoke=true, so a smoked Contraption can still spend its global
//   barrages. Fixes Bombermechs No Survivors run 20260630_181556_177
//   Mission_Missiles turn 4 failed "Use the Detritus Contraption four times".
//   Pre-v310 corpus archived as failure_db_snapshot_sim_v309.jsonl.
// v311 - Bomb Dispenser's 2 Bombs upgrade (`Ranged_DeployBomb_A`) overlays
//   from save power state, enumerates true two-click deploy targets in
//   different directions, and spawns two Walking Bombs. Fixes Bombermechs
//   No Survivors run 20260630_181556_177 after powering the upgrade on R.S.T.
//   Pre-v311 corpus archived as failure_db_snapshot_sim_v310.jsonl.
// v312 - Area Shift emits a Working Together achievement event when four
//   adjacent non-Slide units actually change tiles, and the achievement
//   overlay scores that event. Pre-v312 corpus archived as
//   failure_db_snapshot_sim_v311.jsonl.
// v313 - Ricochet Rocket emits an Efficient Explosives achievement event when
//   one action kills at least three enemies, and the achievement overlay scores
//   that event. Pre-v313 corpus archived as failure_db_snapshot_sim_v312.jsonl.
// v314 - Arachnoid Injector damage to a surviving Scorpion web source keeps
//   the grapple attached, matching live Arachnophiles Mission_Repair evidence.
//   Pre-v314 corpus archived as failure_db_snapshot_sim_v313.jsonl.
// v315 - Arachnoid Injector kills on intrinsic explosive targets such as
//   Mission_BoomBots `*_Boom` pawns do not leave a persistent Arachnoid.
//   Pre-v315 corpus archived as failure_db_snapshot_sim_v314.jsonl.
// v316 - Mission_BoomBots `Snow*1_Boom` pawns map to their base Pinnacle bot
//   attacks, and Snowart artillery hits the target plus perpendicular tiles.
//   Pre-v316 corpus archived as failure_db_snapshot_sim_v315.jsonl.
// v317 - Ricochet Rocket killed targets still corpse-bump live blockers,
//   matching live friendly KIA evidence from Arachnophiles Mission_SnowBattle.
//   Pre-v317 corpus archived as failure_db_snapshot_sim_v316.jsonl.
// v318 - Displaced enemy artillery prefers bridge raw queued target offsets
//   when present, matching live Scarab shots after target normalization.
//   Pre-v318 corpus archived as failure_db_snapshot_sim_v317.jsonl.
// v319 - Boosted Ricochet Rocket special two-click simulation applies the
//   same +1 damage adjustment as ordinary weapons, matching live Fenrir
//   Opener evidence on Arachnophiles Mission_Armored_Train.
//   Pre-v319 corpus archived as failure_db_snapshot_sim_v318.jsonl.
// v320 - Spawned Arachnoid Bite killed targets corpse-bump live blockers,
//   matching Mission_SnowStorm evidence where a killed egg sack bumped and
//   detonated a BombRock. Pre-v320 corpus archived as
//   failure_db_snapshot_sim_v319.jsonl.
// v321 - Efficient Explosives achievement credit excludes killed egg pawns,
//   matching live Arachnophiles Spider Leader evidence where Ricochet killed
//   SpiderlingEgg units but Ach_Squad_Spiders_3 stayed locked. Pre-v321 corpus
//   archived as failure_db_snapshot_sim_v320.jsonl.
// v322 - Area Shift lets live shifted units enter dead enemy wreck tiles
//   without bump damage, matching Arachnophiles Mission_Tanks evidence.
//   Pre-v322 corpus archived as failure_db_snapshot_sim_v321.jsonl.
// v323 - Efficient Explosives event credit is limited to Ricochet Rocket's
//   direct hit and push-lane kills, excluding Health Psion aura-collapse
//   deaths observed in Arachnophiles run 20260703_004111_094. The live bridge
//   also executes Ricochet with the native two-click SkillEffect instead of
//   synthetic DamageSpace so the game achievement hook can observe the shot.
//   Pre-v323 corpus archived as failure_db_snapshot_sim_v322.jsonl.
pub const SIMULATOR_VERSION: u32 = 323;

#[pyfunction]
fn simulator_version() -> u32 {
    SIMULATOR_VERSION
}

/// Replay a solver plan to capture per-action snapshots for the verify
/// loop. Mirrors `src/solver/solver.py::replay_solution()` exactly.
///
/// Input:
///   - `bridge_json`: bridge state (same shape as `solve` / `score_plan`).
///   - `plan_json`: list of `{mech_uid, move_to:[x,y], weapon_id, target:[x,y]}`.
///
/// Output JSON:
///   {
///     "action_results":   [<one per action>],
///     "predicted_states": [{"post_move": <snap>, "post_attack": <snap>}, ...],
///     "predicted_outcome": {<post-enemy summary>},
///     "final_board":       <bridge JSON of post-enemy board>
///   }
///
/// Snapshot shape matches `verify.py::diff_states` byte-for-byte.
#[pyfunction]
fn replay_solution(py: Python<'_>, bridge_json: &str, plan_json: &str) -> PyResult<String> {
    py.allow_threads(|| {
        crate::replay::replay_solution(bridge_json, plan_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
    })
}

/// Depth-N beam search. Task #10.
///
/// Input:
///   - `bridge_json`: board state (same shape as `solve`)
///   - `depth`: 1 or 2. Depth ≥ 3 is deferred.
///   - `k`: beam width at every level. v1 uses `k` for level_0 and
///     `max(k/2, 1)` for level_1; keeping a single knob in the Python
///     surface lets callers tune without picking exact K per level.
///   - `time_limit_secs`: total wall-clock budget, split 40/60 between
///     level 0 and the aggregate level-1 sub-solves.
///
/// Output: JSON array of chain objects, sorted by `chain_score` desc.
/// Each chain: `{chain_score, level_0: <solution>, level_1_best: <solution>|null}`.
/// Empty board (no active mechs) → `[]`.
#[pyfunction]
fn solve_beam(
    py: Python<'_>,
    bridge_json: &str,
    depth: usize,
    k: usize,
    time_limit_secs: f64,
) -> PyResult<String> {
    py.allow_threads(|| {
        let (board, spawn_points, _danger, weights, disabled_mask, overlay_entries) =
            serde_bridge::board_from_json(bridge_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;

        let overlay_pairs: Vec<(weapons::WId, weapons::PartialWeaponDef)> =
            overlay_entries.iter().map(|e| (e.wid, e.patch.clone())).collect();
        let overlay_table = weapons::build_overlay_table(&overlay_pairs);
        let weapons_table: &weapons::WeaponTable = match &overlay_table {
            Some(t) => &**t,
            None => &weapons::WEAPONS,
        };

        let k_per_level = [k, (k / 2).max(1)];
        let chains = crate::beam::solve_beam(
            &board,
            &spawn_points,
            depth,
            &k_per_level[..depth.min(2)],
            time_limit_secs,
            &weights,
            disabled_mask,
            weapons_table,
        );

        let items: Vec<String> = chains.iter().map(|c| {
            let lvl0 = serde_bridge::solution_to_json(&c.level_0, &overlay_entries);
            let lvl1 = match &c.level_1_best {
                Some(s) => serde_bridge::solution_to_json(s, &overlay_entries),
                None    => "null".to_string(),
            };
            format!("{{\"chain_score\":{},\"level_0\":{},\"level_1_best\":{}}}",
                    c.chain_score, lvl0, lvl1)
        }).collect();
        Ok(format!("[{}]", items.join(",")))
    })
}

#[pymodule]
fn itb_solver(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(solve, m)?)?;
    m.add_function(wrap_pyfunction!(solve_top_k, m)?)?;
    m.add_function(wrap_pyfunction!(score_plan, m)?)?;
    m.add_function(wrap_pyfunction!(project_plan, m)?)?;
    m.add_function(wrap_pyfunction!(project_plan_scenarios, m)?)?;
    m.add_function(wrap_pyfunction!(solve_beam, m)?)?;
    m.add_function(wrap_pyfunction!(simulator_version, m)?)?;
    m.add_function(wrap_pyfunction!(replay_solution, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::score_plan;
    use pyo3::Python;

    #[test]
    fn score_plan_applies_spawn_blocking_after_repair() {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let bridge_json = r#"{
                "mission_id": "Mission_Volatile",
                "tiles": [],
                "units": [
                    {
                        "uid": 2,
                        "type": "ScienceMech",
                        "x": 5,
                        "y": 2,
                        "hp": 1,
                        "max_hp": 2,
                        "team": 1,
                        "mech": true,
                        "active": true,
                        "weapons": ["Science_Pullmech", "Science_Shield"]
                    }
                ],
                "grid_power": 7,
                "spawning_tiles": [[5, 2]]
            }"#;
            let plan_json = r#"[
                {
                    "mech_uid": 2,
                    "move_to": [5, 2],
                    "weapon_id": "_REPAIR",
                    "target": [5, 2]
                }
            ]"#;

            let raw = score_plan(py, bridge_json, plan_json).expect("score_plan succeeds");
            let scored: serde_json::Value = serde_json::from_str(&raw).expect("valid score JSON");

            assert_eq!(
                scored["alive_mech_hp"].as_i64(),
                Some(1),
                "repair should heal to 2, then spawn blocking should deal 1 damage"
            );
            assert_eq!(scored["dead_mechs"].as_i64(), Some(0));
        });
    }
}
