//! Accuracy harness for **Option A** turn projection (clear queued targets, no re-queue).
//!
//! For each (board_N, solve_N, board_{N+1}) triple found in recordings/,
//! this test:
//!   1. Parses board_N via `serde_bridge::board_from_json`
//!   2. Extracts the solver's chosen actions from solve_N
//!   3. Calls `project_plan(board_N, actions, spawn_points, weapons)` — Option A
//!   4. Parses actual board_{N+1}
//!   5. Computes accuracy metrics (see AGGREGATE output).
//!
//! Run via:
//!   DYLD_FRAMEWORK_PATH=$FW cargo test --release --no-default-features \
//!     --test eval_turn_projection -- --nocapture

use std::collections::HashSet;
use std::path::PathBuf;
use glob::glob;
use serde_json::Value;

use itb_solver::serde_bridge::board_from_json;
use itb_solver::turn_projection::{project_plan, board_to_json};
use itb_solver::solver::MechAction;
use itb_solver::weapons::{wid_from_str, WEAPONS};

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf()
}

fn extract_bridge_state(v: &Value) -> Option<String> {
    serde_json::to_string(v.pointer("/data/bridge_state")?).ok()
}

fn extract_actions(solve_v: &Value) -> Vec<MechAction> {
    let arr = match solve_v.pointer("/data/actions").and_then(|a| a.as_array()) {
        Some(a) => a,
        None => return vec![],
    };
    arr.iter().filter_map(|a| {
        let mech_uid  = a.get("mech_uid")?.as_u64()? as u16;
        let mech_type = a.get("mech_type").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let mv = a.get("move_to")?.as_array()?;
        let move_to = (mv.get(0)?.as_u64()? as u8, mv.get(1)?.as_u64()? as u8);
        let wid_str = a.get("weapon_id").and_then(|v| v.as_str()).unwrap_or("None");
        let target_arr = a.get("target")?.as_array()?;
        let target = (target_arr.get(0)?.as_u64()? as u8, target_arr.get(1)?.as_u64()? as u8);
        Some(MechAction { mech_uid, mech_type, move_to, weapon: wid_from_str(wid_str), target, description: String::new() })
    }).collect()
}

/// Queued-target match between projected and actual boards.
/// Returns (matched, total_shared_alive_enemies).
/// Option A: projected enemies all have target (-1,-1); matched only when
/// actual board also has (-1,-1) (frozen, webbed, out-of-range enemies).
fn queued_target_match(proj_json: &str, actual_json: &str) -> (usize, usize) {
    let (pb, _, _, _, _, _) = match board_from_json(proj_json)   { Ok(b) => b, Err(_) => return (0,0) };
    let (ab, _, _, _, _, _) = match board_from_json(actual_json) { Ok(b) => b, Err(_) => return (0,0) };
    let mut matched = 0usize;
    let mut total   = 0usize;
    for i in 0..pb.unit_count as usize {
        let pu = &pb.units[i];
        if !pu.is_enemy() || !pu.alive() { continue; }
        for j in 0..ab.unit_count as usize {
            let au = &ab.units[j];
            if au.uid == pu.uid && au.is_enemy() && au.alive() {
                total += 1;
                if pu.queued_target_x == au.queued_target_x && pu.queued_target_y == au.queued_target_y {
                    matched += 1;
                }
                break;
            }
        }
    }
    (matched, total)
}

fn building_hp_mae(proj_json: &str, actual_json: &str) -> f64 {
    let (pb, _, _, _, _, _) = match board_from_json(proj_json)   { Ok(b) => b, Err(_) => return f64::NAN };
    let (ab, _, _, _, _, _) = match board_from_json(actual_json) { Ok(b) => b, Err(_) => return f64::NAN };
    let sum: f64 = (0..64).map(|i| (pb.tiles[i].building_hp as i32 - ab.tiles[i].building_hp as i32).abs() as f64).sum();
    sum / 64.0
}

fn mech_hp_mae(proj_json: &str, actual_json: &str) -> (f64, usize) {
    let (pb, _, _, _, _, _) = match board_from_json(proj_json)   { Ok(b) => b, Err(_) => return (f64::NAN, 0) };
    let (ab, _, _, _, _, _) = match board_from_json(actual_json) { Ok(b) => b, Err(_) => return (f64::NAN, 0) };
    let mut sum = 0.0f64;
    let mut n   = 0usize;
    for i in 0..pb.unit_count as usize {
        let pu = &pb.units[i];
        if !pu.is_player() || !pu.is_mech() { continue; }
        for j in 0..ab.unit_count as usize {
            let au = &ab.units[j];
            if au.uid == pu.uid && au.is_player() && au.is_mech() {
                sum += (pu.hp as i32 - au.hp as i32).abs() as f64;
                n   += 1;
                break;
            }
        }
    }
    if n == 0 { (0.0, 0) } else { (sum / n as f64, n) }
}

fn enemy_count_diff(proj_json: &str, actual_json: &str) -> i32 {
    let (pb, _, _, _, _, _) = match board_from_json(proj_json)   { Ok(b) => b, Err(_) => return 0 };
    let (ab, _, _, _, _, _) = match board_from_json(actual_json) { Ok(b) => b, Err(_) => return 0 };
    let pc = (0..pb.unit_count as usize).filter(|&i| pb.units[i].is_enemy() && pb.units[i].alive()).count() as i32;
    let ac = (0..ab.unit_count as usize).filter(|&i| ab.units[i].is_enemy() && ab.units[i].alive()).count() as i32;
    pc - ac
}

#[test]
fn eval_turn_projection_harness() {
    let recordings = repo_root().join("recordings");
    let pattern    = recordings.join("*/m00_turn_*_board.json");
    let pstr       = pattern.to_str().unwrap();

    let mut all: Vec<(PathBuf, PathBuf, PathBuf)> = Vec::new();
    for entry in glob(pstr).expect("glob") {
        let bp = match entry { Ok(p) => p, Err(_) => continue };
        let fname = match bp.file_name().and_then(|f| f.to_str()) { Some(s) => s, None => continue };
        let after  = fname.trim_start_matches("m00_turn_");
        let tstr   = after.trim_end_matches("_board.json");
        let tnum: u32 = match tstr.parse() { Ok(n) => n, Err(_) => continue };
        let dir = bp.parent().unwrap();
        let sp  = dir.join(format!("m00_turn_{:02}_solve.json", tnum));
        let nbp = dir.join(format!("m00_turn_{:02}_board.json", tnum + 1));
        if sp.exists() && nbp.exists() { all.push((bp, sp, nbp)); }
    }
    all.sort_by(|a, b| a.0.cmp(&b.0));

    // Limit to 5 unique runs to avoid single-corpus bias.
    let mut seen: HashSet<String> = HashSet::new();
    let selected: Vec<_> = all.into_iter().filter(|(bp, _, _)| {
        let run = bp.parent().unwrap().file_name().unwrap().to_str().unwrap().to_string();
        if seen.len() < 5 { seen.insert(run.clone()); true } else { seen.contains(&run) }
    }).collect();

    println!("\n=== Option A Turn Projection Accuracy Harness (clear queued targets, no re-queue) ===");
    println!("triples_available: {}", selected.len());

    let mut t_match   = 0usize;
    let mut t_shared  = 0usize;
    let mut t_bldg    = 0.0f64;
    let mut t_mech    = 0.0f64;
    let mut t_mech_n  = 0usize;
    let mut t_ediff   = 0i32;
    let mut processed = 0usize;

    for (bp, sp, nbp) in &selected {
        let board_raw  = match std::fs::read_to_string(bp)  { Ok(s) => s, Err(_) => continue };
        let board_v: Value = match serde_json::from_str(&board_raw)  { Ok(v) => v, Err(_) => continue };
        let bridge_str = match extract_bridge_state(&board_v) { Some(s) => s, None => continue };

        let next_raw   = match std::fs::read_to_string(nbp)  { Ok(s) => s, Err(_) => continue };
        let next_v: Value  = match serde_json::from_str(&next_raw)   { Ok(v) => v, Err(_) => continue };
        let next_str   = match extract_bridge_state(&next_v)  { Some(s) => s, None => continue };

        let solve_raw  = match std::fs::read_to_string(sp)   { Ok(s) => s, Err(_) => continue };
        let solve_v: Value = match serde_json::from_str(&solve_raw)  { Ok(v) => v, Err(_) => continue };
        let actions = extract_actions(&solve_v);

        let (board, spawn_points, _, _, _, _) = match board_from_json(&bridge_str) {
            Ok(b) => b,
            Err(e) => { println!("  SKIP (parse): {:?}: {}", bp, e); continue; }
        };

        // Project with Option A (clear queued targets, no re-queue)
        let (projected, result) = project_plan(&board, &actions, &spawn_points, &WEAPONS);
        let proj_json = board_to_json(&projected, &spawn_points);

        let (qm, qs)       = queued_target_match(&proj_json, &next_str);
        let bldg_v         = building_hp_mae(&proj_json, &next_str);
        let (mhp, mhp_n)   = mech_hp_mae(&proj_json, &next_str);
        let ecount         = enemy_count_diff(&proj_json, &next_str);

        t_match  += qm;
        t_shared += qs;
        t_bldg   += bldg_v;
        t_mech   += mhp * mhp_n as f64;
        t_mech_n += mhp_n;
        t_ediff  += ecount;
        processed += 1;

        let qpct = if qs > 0 { qm as f64 / qs as f64 * 100.0 } else { f64::NAN };
        let run  = bp.parent().unwrap().file_name().unwrap().to_str().unwrap();
        let turn = bp.file_name().unwrap().to_str().unwrap()
            .trim_start_matches("m00_turn_").trim_end_matches("_board.json");
        println!("  [run={} t={}] qmatch={:.0}%({}/{}), bldg_mae={:.3}, mech_mae={:.2}, e_diff={:+}, kills={}, bldgs_lost={}",
            run, turn, qpct, qm, qs, bldg_v, mhp, ecount,
            result.enemies_killed, result.buildings_lost);
    }

    if processed == 0 {
        println!("WARNING: no triples processed — check recordings directory");
        return;
    }

    let avg_qmatch   = if t_shared > 0 { t_match as f64 / t_shared as f64 * 100.0 } else { f64::NAN };
    let avg_bldg_mae = t_bldg / processed as f64;
    let avg_mech_mae = if t_mech_n > 0 { t_mech / t_mech_n as f64 } else { 0.0 };
    let avg_e_diff   = t_ediff as f64 / processed as f64;

    println!("\n=== AGGREGATE (B + C: heuristic re-queue + pseudo_threat_eval) ===");
    println!("triples_processed:              {}", processed);
    println!("enemy_queued_target_match_pct:  {:.1}%  ({}/{} shared enemies)", avg_qmatch, t_match, t_shared);
    println!("building_hp_mae:                {:.4}  (per-tile mean abs err, 64 tiles)", avg_bldg_mae);
    println!("mech_hp_mae:                    {:.4}  ({} mech pairs)", avg_mech_mae, t_mech_n);
    println!("enemy_count_diff (proj-actual): {:.2}  (positive = sim over-predicts kills)", avg_e_diff);
    println!();
    println!("B: heuristic re-queue (closest Building in reach, fallback closest mech;");
    println!("   skip Webbed/Frozen/Smoke). Expected qmatch ~29% against real game AI.");
    println!("C: board_to_json injects eval_weights.pseudo_threat_eval=true so enemies");
    println!("   the heuristic left queueless still contribute a threat penalty via the");
    println!("   Option-C block in evaluate.rs.");
}
