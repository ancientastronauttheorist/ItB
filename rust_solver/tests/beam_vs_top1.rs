//! Diagnostic harness comparing depth-2 beam vs. single-turn top-1 solve
//! on the recordings corpus.
//!
//! For each `m00_turn_NN_board.json` in recordings/ (capped at 5 runs to
//! avoid single-corpus bias), this harness:
//!   1. Parses the bridge state
//!   2. Runs `solve_turn` for the single-turn top-1 score/plan
//!   3. Runs `solve_beam(depth=2, k=3)` for the beam top chain
//!   4. Reports: does beam pick a different level-0 plan? Chain score
//!      vs top-1 score? Level-1 bonus magnitude?
//!
//! This is a DIAGNOSTIC — there's no pass/fail gate. It tells us:
//!   - If beam NEVER picks differently: beam is not earning its compute
//!   - If beam ALWAYS picks differently: single-turn top-1 is structurally
//!     mis-ranking plans, and beam is paying off
//!   - The distribution of level-1 bonuses tells us how informative
//!     turn+1 projection is as a tie-breaker
//!
//! Run via:
//!   DYLD_FRAMEWORK_PATH=$FW cargo test --release --no-default-features \
//!     --test beam_vs_top1 -- --nocapture

use std::collections::HashSet;
use std::path::PathBuf;
use glob::glob;
use serde_json::Value;

use itb_solver::beam::solve_beam;
use itb_solver::serde_bridge::board_from_json;
use itb_solver::solver::{solve_turn, MechAction, Solution};
use itb_solver::weapons::WEAPONS;

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf()
}

fn extract_bridge_state(v: &Value) -> Option<String> {
    serde_json::to_string(v.pointer("/data/bridge_state")?).ok()
}

/// Two plans are "equivalent" when they have the same ordered list of
/// (mech_uid, move_to, weapon, target) tuples. Order matters because
/// permutation affects simulation outcomes (push chains, env timing).
fn plans_match(a: &[MechAction], b: &[MechAction]) -> bool {
    if a.len() != b.len() { return false; }
    for (ax, bx) in a.iter().zip(b.iter()) {
        if ax.mech_uid != bx.mech_uid { return false; }
        if ax.move_to != bx.move_to   { return false; }
        if (ax.weapon as u16) != (bx.weapon as u16) { return false; }
        if ax.target != bx.target     { return false; }
    }
    true
}

#[test]
fn beam_vs_top1_harness() {
    let recordings = repo_root().join("recordings");
    let pattern    = recordings.join("*/m00_turn_*_board.json");
    let pstr       = pattern.to_str().unwrap();

    let mut all: Vec<PathBuf> = Vec::new();
    for entry in glob(pstr).expect("glob") {
        if let Ok(p) = entry { all.push(p); }
    }
    all.sort();

    // Cap at 5 unique runs for diagnostic signal without burning wall-clock.
    let mut seen: HashSet<String> = HashSet::new();
    let selected: Vec<_> = all.into_iter().filter(|bp| {
        let run = bp.parent().unwrap().file_name().unwrap().to_str().unwrap().to_string();
        if seen.len() < 5 { seen.insert(run.clone()); true } else { seen.contains(&run) }
    }).collect();

    println!("\n=== Beam (depth=2, k=3) vs Top-1 harness ===");
    println!("boards_available: {}", selected.len());

    let mut processed       = 0usize;
    let mut same_plan       = 0usize;
    let mut diff_plan       = 0usize;
    let mut beam_higher_ch  = 0usize;
    let mut beam_equal_ch   = 0usize;
    let mut beam_lower_lvl0 = 0usize; // beam's level_0.score < top-1.score (possible if chain_score ranks it)
    let mut sum_bonus       = 0.0f64;
    let mut bonus_n         = 0usize;

    let time_limit = 4.0_f64; // per board; harness runs 5 boards × 4s = 20s worst case

    for bp in &selected {
        let raw = match std::fs::read_to_string(bp) { Ok(s) => s, Err(_) => continue };
        let v: Value = match serde_json::from_str(&raw) { Ok(v) => v, Err(_) => continue };
        let bridge = match extract_bridge_state(&v) { Some(s) => s, None => continue };

        let (board, spawn_points, _danger, weights, disabled_mask, _overlay) =
            match board_from_json(&bridge) { Ok(r) => r, Err(_) => continue };

        // Single-turn top-1.
        let top1: Solution = solve_turn(
            &board, &spawn_points, time_limit, 99_999,
            &weights, disabled_mask, &WEAPONS,
        );
        if top1.actions.is_empty() { continue; } // No active mechs — not useful.

        // Depth-2 beam with k=3 at level 0 (→ k=1 at level 1 via the
        // k/2.max(1) split inside solve_beam's pyo3 shim isn't used here;
        // we call the Rust fn directly with explicit k_per_level).
        let chains = solve_beam(
            &board, &spawn_points, 2, &[3, 2], time_limit,
            &weights, disabled_mask, &WEAPONS,
        );
        if chains.is_empty() { continue; }
        let top_chain = &chains[0];

        processed += 1;
        let same = plans_match(&top1.actions, &top_chain.level_0.actions);
        if same { same_plan += 1; } else { diff_plan += 1; }

        if top_chain.chain_score > top1.score { beam_higher_ch += 1; }
        else if (top_chain.chain_score - top1.score).abs() < 1e-6 { beam_equal_ch += 1; }

        if top_chain.level_0.score < top1.score { beam_lower_lvl0 += 1; }

        if let Some(sub) = &top_chain.level_1_best {
            sum_bonus += sub.score;
            bonus_n += 1;
        }

        let run  = bp.parent().unwrap().file_name().unwrap().to_str().unwrap();
        let fname = bp.file_name().unwrap().to_str().unwrap();
        let tstr  = fname.trim_start_matches("m00_turn_").trim_end_matches("_board.json");
        let bonus = top_chain.level_1_best.as_ref().map(|s| s.score).unwrap_or(0.0);
        println!(
            "  [run={} t={}] same={} top1={:.0} beam_lvl0={:.0} bonus={:.0} chain={:.0}",
            run, tstr, same as u8,
            top1.score, top_chain.level_0.score, bonus, top_chain.chain_score,
        );
    }

    if processed == 0 {
        println!("WARNING: no boards processed — check recordings/ and bridge state format");
        return;
    }

    let avg_bonus = if bonus_n > 0 { sum_bonus / bonus_n as f64 } else { 0.0 };
    let diff_pct  = diff_plan as f64 * 100.0 / processed as f64;

    println!("\n=== AGGREGATE ===");
    println!("processed:           {}", processed);
    println!("same_plan:           {} ({:.0}%)", same_plan, 100.0 - diff_pct);
    println!("different_plan:      {} ({:.0}%) ← beam picked a different level-0 plan", diff_plan, diff_pct);
    println!("beam_higher_chain:   {} (chain_score > top1.score)", beam_higher_ch);
    println!("beam_equal_chain:    {}", beam_equal_ch);
    println!("beam_lvl0_lt_top1:   {} ← beam picked a worse level-0 because level-1 bonus compensated", beam_lower_lvl0);
    println!("avg_level_1_bonus:   {:.0}  (avg score of best sub-plan across processed chains)", avg_bonus);
    println!();
    println!("Interpretation guide:");
    println!("  diff_plan == 0  → beam is not earning its compute; fallback to top-1");
    println!("  diff_plan > 0   → beam finds plans that single-turn ranks lower but which score");
    println!("                    higher when evaluated across the projected turn+1");
    println!("  beam_lvl0_lt_top1 > 0 → beam is deliberately sacrificing turn-1 score for");
    println!("                          better turn+1 outcome; that's the beam-value signal");
}
