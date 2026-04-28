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
//   damage at D5 — the 2-HP Corp Tower fell, grid 2→0, defeat. Per
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
pub const SIMULATOR_VERSION: u32 = 29;

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
