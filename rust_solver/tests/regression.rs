//! Regression test: run the solver against every recorded board and assert
//! it doesn't crash, produce empty solutions on active boards, or emit
//! out-of-bounds actions.
//!
//! Does NOT assert score equality or action equality — those legitimately
//! change with weight tuning and tie-breaking.

use std::collections::HashSet;
use std::path::PathBuf;

use glob::glob;
use serde_json::Value;

use itb_solver::serde_bridge::board_from_json;
use itb_solver::solver::{solve_turn, Solution};

/// Load known_issues.json and extract Rust-scoped entries.
/// Returns set of (run_id, turn, trigger_name) tuples.
fn load_known_issues() -> HashSet<(String, u32, String)> {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf();
    let path = repo_root.join("tests/known_issues.json");

    let Ok(raw) = std::fs::read_to_string(&path) else {
        return HashSet::new();
    };
    let Ok(v): Result<Value, _> = serde_json::from_str(&raw) else {
        return HashSet::new();
    };

    let mut out = HashSet::new();
    if let Some(entries) = v.get("entries").and_then(|e| e.as_array()) {
        for e in entries {
            let scope = e.get("scope").and_then(|v| v.as_str()).unwrap_or("both");
            if scope != "rust" && scope != "both" {
                continue;
            }
            let run_id = e.get("run_id").and_then(|v| v.as_str()).unwrap_or("");
            let turn = e.get("turn").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
            let trig = e.get("trigger").and_then(|v| v.as_str()).unwrap_or("");
            if !run_id.is_empty() && !trig.is_empty() {
                out.insert((run_id.to_string(), turn, trig.to_string()));
            }
        }
    }
    out
}

/// Recording JSON wraps bridge state at `.data.bridge_state`.
/// Extract that subtree and re-serialize for board_from_json.
fn extract_bridge_state(recording: &Value) -> Result<String, String> {
    let bs = recording
        .pointer("/data/bridge_state")
        .ok_or_else(|| "missing .data.bridge_state".to_string())?;
    serde_json::to_string(bs).map_err(|e| format!("reserialize: {}", e))
}

/// A board "requires" actions (i.e. the solver SHOULD produce a non-empty plan)
/// only when there's at least one active player mech AND at least one enemy on the board.
/// Otherwise empty actions is a correct outcome (no-op turn).
fn case_requires_actions(bridge: &Value) -> bool {
    let units = bridge.get("units").and_then(|u| u.as_array());
    let has_active_mech = units
        .map(|us| {
            us.iter().any(|u| {
                u.get("team").and_then(|v| v.as_u64()) == Some(0)
                    && u.get("active").and_then(|v| v.as_bool()).unwrap_or(false)
            })
        })
        .unwrap_or(false);

    // Enemies can appear either under top-level "enemies" (summary) or as
    // team=1 entries in "units" (canonical). Check both.
    let has_enemy_unit = units
        .map(|us| {
            us.iter()
                .any(|u| u.get("team").and_then(|v| v.as_u64()) == Some(1))
        })
        .unwrap_or(false);
    let has_enemy_summary = bridge
        .get("enemies")
        .and_then(|e| e.as_array())
        .map(|a| !a.is_empty())
        .unwrap_or(false);

    has_active_mech && (has_enemy_unit || has_enemy_summary)
}

fn check_solution(sol: &Solution, require_actions: bool, case_id: &str) -> Result<(), String> {
    // Score sanity: NEG_INFINITY only valid when no actions were expected
    if sol.score == f64::NEG_INFINITY && require_actions {
        return Err(format!(
            "{}: score is -inf on active board (search produced nothing)",
            case_id
        ));
    }

    // Empty actions: only valid if no actions expected OR solver timed out
    if require_actions && sol.actions.is_empty() && !sol.timed_out {
        return Err(format!(
            "{}: empty actions on active board (not timed out)",
            case_id
        ));
    }

    // In-bounds validity for all actions
    for (i, a) in sol.actions.iter().enumerate() {
        if a.move_to.0 >= 8 || a.move_to.1 >= 8 {
            return Err(format!(
                "{}: action[{}] move_to out of bounds: {:?}",
                case_id, i, a.move_to
            ));
        }
        // target of (255, 255) is the sentinel for "no target" (move-only or repair)
        if a.target.0 != 255 && (a.target.0 >= 8 || a.target.1 >= 8) {
            return Err(format!(
                "{}: action[{}] target out of bounds: {:?}",
                case_id, i, a.target
            ));
        }
    }
    Ok(())
}

#[test]
fn regression_all_boards() {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf();
    let pattern = repo_root.join("recordings/*/m*_turn_*_board.json");
    let pattern_str = pattern.to_str().expect("path to str");

    let known = load_known_issues();
    let mut total = 0usize;
    let mut wins = 0usize;
    let mut expected_failures = 0usize;
    let mut unexpected: Vec<String> = Vec::new();

    for entry in glob(pattern_str).expect("bad glob") {
        let path = match entry {
            Ok(p) => p,
            Err(_) => continue,
        };
        total += 1;

        let raw = match std::fs::read_to_string(&path) {
            Ok(s) => s,
            Err(e) => {
                unexpected.push(format!("{:?}: read failed: {}", path, e));
                continue;
            }
        };
        let recording: Value = match serde_json::from_str(&raw) {
            Ok(v) => v,
            Err(e) => {
                unexpected.push(format!("{:?}: parse failed: {}", path, e));
                continue;
            }
        };
        let run_id = recording
            .get("run_id")
            .and_then(|v| v.as_str())
            .unwrap_or("?")
            .to_string();
        let turn = recording
            .get("turn")
            .and_then(|v| v.as_u64())
            .unwrap_or(0) as u32;
        let mission = recording
            .get("mission_index")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        let case_id = format!("{}/m{:02}_turn_{:02}", run_id, mission, turn);

        let bridge = recording.pointer("/data/bridge_state");
        let require_actions = bridge.map(case_requires_actions).unwrap_or(false);

        let bridge_json = match extract_bridge_state(&recording) {
            Ok(j) => j,
            Err(e) => {
                unexpected.push(format!("{}: {}", case_id, e));
                continue;
            }
        };

        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let (board, spawns, _danger, weights, disabled_mask, _overlay) =
                board_from_json(&bridge_json).map_err(|e| format!("board_from_json: {}", e))?;
            Ok::<_, String>(solve_turn(&board, &spawns, 2.0, 99999, &weights, disabled_mask, &itb_solver::weapons::WEAPONS))
        }));

        let outcome = match result {
            Ok(Ok(sol)) => check_solution(&sol, require_actions, &case_id),
            Ok(Err(e)) => Err(format!("{}: {}", case_id, e)),
            Err(_) => Err(format!("{}: PANIC", case_id)),
        };

        match outcome {
            Ok(()) => wins += 1,
            Err(msg) => {
                // Classify by our internal trigger taxonomy for allowlist matching
                let trig = if msg.contains("PANIC") {
                    "panic"
                } else if msg.contains("empty actions") || msg.contains("-inf") {
                    "empty_solution"
                } else if msg.contains("out of bounds") {
                    "oob_action"
                } else {
                    "other"
                };
                if known.contains(&(run_id.clone(), turn, trig.to_string())) {
                    expected_failures += 1;
                } else {
                    unexpected.push(msg);
                }
            }
        }
    }

    println!(
        "\nRust regression: total={} wins={} expected_failures={} unexpected={}",
        total,
        wins,
        expected_failures,
        unexpected.len()
    );

    assert!(
        unexpected.is_empty(),
        "Unexpected regressions ({}):\n  {}",
        unexpected.len(),
        unexpected
            .iter()
            .take(20)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n  ")
    );
}
