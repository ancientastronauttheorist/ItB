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
    use crate::enemy::simulate_enemy_attacks;
    use crate::evaluate::{evaluate, PsionState};
    use crate::simulate::simulate_action;
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
                weapons_table,
            );
            kills += result.enemies_killed as i32;
            bumps += result.buildings_bump_damaged as i32;
        }

        let buildings_mid = board.tiles.iter()
            .filter(|t| t.terrain == crate::types::Terrain::Building && t.building_hp > 0)
            .count() as i32;

        let _ = simulate_enemy_attacks(&mut board, &original_positions, weapons_table);

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
/// Option C behaviour: enemies on the projected board have NO queued targets
/// (`queued_target_x = -1`). The returned `board_json` injects
/// `eval_weights.pseudo_threat_eval = true` so that `evaluate()` runs the
/// queueless-threat augmentation (1.5× next_turn_threat_penalty per alive
/// enemy that can reach a building) when the projected board is re-evaluated
/// by a downstream solve call.
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
                "mechs_killed": result.mechs_killed,
                "buildings_lost": result.buildings_lost,
                "buildings_damaged": result.buildings_damaged,
                "grid_damage": result.grid_damage,
                "enemy_damage_dealt": result.enemy_damage_dealt,
                "mech_damage_taken": result.mech_damage_taken,
                "spawns_blocked": result.spawns_blocked,
                "pods_collected": result.pods_collected,
            },
            "projected_turn": projected.current_turn,
        });
        Ok(out.to_string())
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
pub const SIMULATOR_VERSION: u32 = 23;

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
    m.add_function(wrap_pyfunction!(solve_beam, m)?)?;
    m.add_function(wrap_pyfunction!(simulator_version, m)?)?;
    m.add_function(wrap_pyfunction!(replay_solution, m)?)?;
    Ok(())
}
