//! Regression test: run the solver against every tracked recorded board and assert
//! it doesn't crash, produce empty solutions on active boards, or emit
//! out-of-bounds actions.
//!
//! Does NOT assert score equality or action equality — those legitimately
//! change with weight tuning and tie-breaking.

use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::process::Command;

use glob::glob;
use serde_json::Value;

use itb_solver::serde_bridge::board_from_json;
use itb_solver::solver::{solve_turn, Solution};
use itb_solver::board::Board;

/// Return board recordings for the Rust corpus. By default this uses only
/// tracked files so local live-run artifacts do not turn regression into an
/// unbounded crawl. Set ITB_REGRESSION_INCLUDE_UNTRACKED=1 to opt into the old
/// glob behavior when investigating a local recording before curating it.
fn recording_board_paths(repo_root: &Path) -> Vec<PathBuf> {
    if std::env::var("ITB_REGRESSION_INCLUDE_UNTRACKED").as_deref() == Ok("1") {
        return glob_recording_board_paths(repo_root);
    }

    let output = Command::new("git")
        .arg("-C")
        .arg(repo_root)
        .arg("ls-files")
        .arg("recordings/*/m*_turn_*_board.json")
        .output();
    match output {
        Ok(out) if out.status.success() => String::from_utf8_lossy(&out.stdout)
            .lines()
            .filter(|line| !line.trim().is_empty())
            .map(|line| repo_root.join(line))
            .collect(),
        _ => glob_recording_board_paths(repo_root),
    }
}

fn glob_recording_board_paths(repo_root: &Path) -> Vec<PathBuf> {
    let pattern = repo_root.join("recordings/*/m*_turn_*_board.json");
    let pattern_str = pattern.to_str().expect("path to str");
    glob(pattern_str)
        .expect("bad glob")
        .filter_map(Result::ok)
        .collect()
}

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

/// Require a non-empty plan when the parsed board has a supported ready player
/// actor and a living enemy. Use the same admission as search, including armed
/// mission allies and the move-only VIP Truck, rather than obsolete wire-team
/// numbers or raw summaries that the parser does not consume.
fn case_requires_actions(board: &Board) -> bool {
    !board.active_mechs().is_empty() && !board.enemies().is_empty()
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
    let paths = recording_board_paths(&repo_root);

    let known = load_known_issues();
    let mut total = 0usize;
    let mut wins = 0usize;
    let mut action_required_cases = 0usize;
    let mut expected_failures = 0usize;
    let mut unexpected: Vec<String> = Vec::new();

    for path in paths {
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
            let require_actions = case_requires_actions(&board);
            // Admission remains counted if search panics on this parsed board.
            action_required_cases += usize::from(require_actions);
            let solution = solve_turn(&board, &spawns, 2.0, 99999, &weights, disabled_mask, &itb_solver::weapons::WEAPONS);
            Ok::<_, String>((solution, require_actions))
        }));

        let outcome = match result {
            Ok(Ok((sol, require_actions))) => {
                check_solution(&sol, require_actions, &case_id)
            },
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
        "\nRust regression: total={} action_required={} wins={} expected_failures={} unexpected={}",
        total,
        action_required_cases,
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

#[cfg(test)]
mod admission_tests {
    use super::*;
    use serde_json::json;

    fn player() -> Value {
        json!({"uid":0,"type":"CombatMech","x":0,"y":0,"hp":3,
               "team":1,"mech":true,"active":true})
    }

    fn enemy() -> Value {
        json!({"uid":1,"type":"Firefly1","x":7,"y":7,"hp":2,"team":6})
    }

    fn requires(units: Vec<Value>) -> bool {
        let input = json!({"tiles":[],"units":units}).to_string();
        let (board, _, _, _, _, _) = board_from_json(&input).unwrap();
        case_requires_actions(&board)
    }

    #[test]
    fn canonical_teams_and_parser_defaults_require_actions() {
        assert!(requires(vec![player(), enemy()]));
        let mut mech = player();
        mech.as_object_mut().unwrap().remove("team");
        mech.as_object_mut().unwrap().remove("active");
        let mut vek = enemy();
        vek.as_object_mut().unwrap().remove("team");
        assert!(requires(vec![mech, vek]));
    }

    #[test]
    fn sole_mission_actor_requires_actions() {
        for (kind, weapon) in [("ArchiveArtillery", "Archive_ArtShot"), ("Acid_Tank", "Acid_Tank_Attack")] {
            let ally = json!({"uid":2,"type":kind,"x":0,"y":0,"hp":2,
                              "team":1,"mech":false,"active":true,"weapons":[weapon]});
            assert!(requires(vec![ally, enemy()]), "{} should act", kind);
        }
        let truck = json!({"uid":2,"type":"VIP_Truck","x":0,"y":0,"hp":2,
                           "team":1,"mech":false,"active":true,"move":3});
        assert!(requires(vec![truck, enemy()]));
    }

    #[test]
    fn unsupported_or_unready_units_do_not_trigger_action_requirement() {
        for (key, value) in [("active", json!(false)), ("hp", json!(0)),
                             ("is_extra_tile", json!(true)), ("team", json!(2)),
                             ("mech", json!(false))] {
            let mut actor = player();
            actor[key] = value;
            assert!(!requires(vec![actor, enemy()]), "{} exclusion", key);
        }
    }

    #[test]
    fn no_living_enemy_does_not_trigger_action_requirement() {
        assert!(!requires(vec![player()]));
        for (key, value) in [("hp", json!(0)), ("team", json!(2))] {
            let mut vek = enemy();
            vek[key] = value;
            assert!(!requires(vec![player(), vek]));
        }
        let input = json!({"units":[player()],"enemies":[{"type":"Firefly1"}]}).to_string();
        let (board, _, _, _, _, _) = board_from_json(&input).unwrap();
        assert!(!case_requires_actions(&board), "raw summary is not a parsed enemy");
    }

    #[test]
    fn required_board_checks_reject_injected_empty_solutions() {
        let required = requires(vec![player(), enemy()]);
        assert!(required);
        let mut solution = Solution::empty();
        assert!(check_solution(&solution, required, "injected").unwrap_err().contains("-inf"));
        solution.score = 0.0;
        assert!(check_solution(&solution, required, "injected").unwrap_err().contains("empty actions"));
        solution.timed_out = true;
        assert!(check_solution(&solution, required, "injected").is_ok());
        solution.timed_out = false;
        assert!(check_solution(&solution, false, "inactive").is_ok());
    }
}
