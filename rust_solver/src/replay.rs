//! Per-action replay with snapshot capture.
//!
//! Mirrors `src/solver/solver.py::replay_solution` exactly so the Python
//! call site can be swapped to the Rust backend without consumer changes.
//! For each action in the plan: run `simulate_move`, snapshot, run
//! `simulate_attack`, snapshot. After all actions: run env effects + Vek
//! attacks (`simulate_enemy_attacks`) then `apply_spawn_blocking`. Build
//! `predicted_outcome` summary and serialize the post-enemy board via
//! `turn_projection::board_to_json` for Python's `evaluate_breakdown` to
//! consume.
//!
//! Snapshot shape matches `src/solver/verify.py::snapshot_after_action` /
//! `snapshot_after_move` byte-for-byte: same field names, same types, same
//! tile-sampling rule (touched tiles + 1-tile buffer).

use crate::board::Board;
use crate::enemy::{apply_spawn_blocking, simulate_enemy_attacks};
use crate::serde_bridge;
use crate::simulate::{simulate_attack, simulate_move};
use crate::turn_projection::board_to_json;
use crate::types::Terrain;
use crate::weapons::{self, build_overlay_table, wid_from_str, WeaponTable};

use serde_json::{json, Value};
use std::collections::BTreeSet;

#[derive(serde::Deserialize)]
struct PlanAction {
    mech_uid: u16,
    move_to: [u8; 2],
    weapon_id: String,
    target: [u8; 2],
}

/// Top-level entrypoint. Returns the JSON string Python deserializes.
pub fn replay_solution(bridge_json: &str, plan_json: &str) -> Result<String, String> {
    let (mut board, spawn_points, _danger, _weights, _disabled, overlay_entries) =
        serde_bridge::board_from_json(bridge_json)?;

    let overlay_pairs: Vec<(weapons::WId, weapons::PartialWeaponDef)> =
        overlay_entries.iter().map(|e| (e.wid, e.patch.clone())).collect();
    let overlay_table = build_overlay_table(&overlay_pairs);
    let weapons_table: &WeaponTable = match &overlay_table {
        Some(t) => &**t,
        None => &weapons::WEAPONS,
    };

    let plan: Vec<PlanAction> = serde_json::from_str(plan_json)
        .map_err(|e| format!("plan parse: {}", e))?;

    // Capture original positions BEFORE any mutation — simulate_enemy_attacks
    // uses these for re-aim. Mirrors solver.py:657 + lib.rs:91-94.
    let mut original_positions = [(0u8, 0u8); 16];
    for i in 0..board.unit_count as usize {
        original_positions[i] = (board.units[i].x, board.units[i].y);
    }

    let mut action_results: Vec<Value> = Vec::with_capacity(plan.len());
    let mut predicted_states: Vec<Value> = Vec::with_capacity(plan.len());

    for (i, act) in plan.iter().enumerate() {
        let mech_uid = act.mech_uid;
        let mech_idx = board.units.iter().position(|u| u.uid == mech_uid && u.alive());
        let mech_idx = match mech_idx {
            Some(idx) => idx,
            None => {
                // Mirror solver.py:666-682 — error snapshot with empty units +
                // tiles_changed and an "error" key on both phases.
                let err_snap = json!({
                    "action_index": i,
                    "mech_uid": mech_uid,
                    "snapshot_phase": "after_mech_action",
                    "error": "mech_not_found",
                    "units": [],
                    "tiles_changed": [],
                    "grid_power": board.grid_power,
                });
                action_results.push(json!({
                    "enemies_killed": 0,
                    "enemy_damage_dealt": 0,
                    "buildings_lost": 0,
                    "buildings_damaged": 0,
                    "mech_damage_taken": 0,
                    "pods_collected": 0,
                    "spawns_blocked": 0,
                    "events": [format!("Mech UID {} not found", mech_uid)],
                }));
                predicted_states.push(json!({
                    "post_move":   err_snap.clone(),
                    "post_attack": err_snap,
                }));
                continue;
            }
        };

        // Phase 1: move
        let move_result = simulate_move(&mut board, mech_idx, (act.move_to[0], act.move_to[1]));
        let post_move_snap = capture_snapshot(
            &board, i, mech_uid, &move_result.events, "after_move",
        );

        // Phase 2: attack
        let wid = wid_from_str(&act.weapon_id);
        let attack_result = simulate_attack(
            &mut board, mech_idx, wid, (act.target[0], act.target[1]), weapons_table,
        );
        let mut all_events = move_result.events.clone();
        all_events.extend_from_slice(&attack_result.events);
        let post_attack_snap = capture_snapshot(
            &board, i, mech_uid, &all_events, "after_mech_action",
        );

        action_results.push(json!({
            "enemies_killed":     attack_result.enemies_killed,
            "enemy_damage_dealt": attack_result.enemy_damage_dealt,
            "buildings_lost":     attack_result.buildings_lost,
            "buildings_damaged":  attack_result.buildings_damaged,
            "grid_damage":        attack_result.grid_damage,
            "mech_damage_taken":  attack_result.mech_damage_taken,
            "mechs_killed":       attack_result.mechs_killed,
            "pods_collected":     move_result.pods_collected,
            "spawns_blocked":     attack_result.spawns_blocked,
            "events":             all_events,
        }));

        predicted_states.push(json!({
            "post_move":   post_move_snap,
            "post_attack": post_attack_snap,
        }));
    }

    // Snapshot building coords BEFORE the enemy phase so we can attribute
    // the post-enemy delta to enemies (mirrors solver.py:718's
    // buildings_destroyed return). Using a coord set rather than a scalar
    // count lets us tolerate mid-turn mission/state shifts — if a new
    // building appears in the post-enemy state (shouldn't happen in
    // vanilla ITB, but could from modded content or cross-mission
    // recording aliasing), it won't be counted as "destroyed" just
    // because the pre-count was off.
    let mut alive_building_coords_pre: std::collections::HashSet<(u8, u8)> =
        std::collections::HashSet::new();
    for x in 0..8u8 {
        for y in 0..8u8 {
            let t = board.tile(x, y);
            if t.terrain == Terrain::Building && t.building_hp > 0 {
                alive_building_coords_pre.insert((x, y));
            }
        }
    }

    // Env effects + Vek attacks. simulate_enemy_attacks handles env_danger
    // BEFORE Vek attacks (enemy.rs:287-297) — same ordering as Python's
    // _simulate_env_effects then _simulate_enemy_attacks.
    let _ = simulate_enemy_attacks(&mut board, &original_positions, weapons_table);
    apply_spawn_blocking(&mut board, &spawn_points);

    // Build predicted_outcome (mirrors solver.py:744-756).
    let mut buildings_alive = 0i32;
    let mut building_hp_total = 0i32;
    for tile in board.tiles.iter() {
        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
            buildings_alive += 1;
            building_hp_total += tile.building_hp as i32;
        }
    }
    let mut enemies_alive = 0i32;
    let mut enemy_hp_total = 0i32;
    let mut mechs_alive = 0i32;
    let mut mech_hp_list: Vec<Value> = Vec::new();
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.is_mech() {
            if u.hp > 0 { mechs_alive += 1; }
            mech_hp_list.push(json!({
                "uid": u.uid,
                "type": u.type_name_str(),
                "hp": u.hp,
                "max_hp": u.max_hp,
            }));
        } else if u.is_enemy() && u.hp > 0 {
            enemies_alive += 1;
            enemy_hp_total += u.hp as i32;
        }
    }
    // Count only coords that WERE alive pre-enemy and are now destroyed
    // (missing from alive set or hp dropped to 0). Coords that appear
    // alive post-enemy but were NOT alive pre-enemy are ignored — they
    // cannot have been "destroyed by enemies" this turn.
    let mut buildings_destroyed_by_enemies = 0i32;
    for (x, y) in &alive_building_coords_pre {
        let t = board.tile(*x, *y);
        if !(t.terrain == Terrain::Building && t.building_hp > 0) {
            buildings_destroyed_by_enemies += 1;
        }
    }

    let predicted_outcome = json!({
        "buildings_alive":               buildings_alive,
        "building_hp_total":             building_hp_total,
        "grid_power":                    board.grid_power,
        "enemies_alive":                 enemies_alive,
        "enemy_hp_total":                enemy_hp_total,
        "mechs_alive":                   mechs_alive,
        "mech_hp":                       mech_hp_list,
        "buildings_destroyed_by_enemies": buildings_destroyed_by_enemies,
    });

    // Serialize the final post-enemy board so Python's evaluate_breakdown
    // can build a Board and score it. board_to_json emits bridge JSON;
    // Board.from_bridge_data on the Python side consumes it.
    let final_board_json: Value = serde_json::from_str(
        &board_to_json(&board, &spawn_points)
    ).map_err(|e| format!("final_board reparse: {}", e))?;

    let out = json!({
        "action_results":   action_results,
        "predicted_states": predicted_states,
        "predicted_outcome": predicted_outcome,
        "final_board":       final_board_json,
    });
    Ok(out.to_string())
}

// ── Snapshot helpers ────────────────────────────────────────────────────────

/// Mirror `src/solver/verify.py::snapshot_after_action` (and
/// `snapshot_after_move`). Captures every unit (alive or dead — diff
/// engine needs death/spawn detection) and only the tiles touched by
/// `events` + a 1-tile buffer + the mech's current tile.
fn capture_snapshot(
    board: &Board,
    action_index: usize,
    mech_uid: u16,
    events: &[String],
    snapshot_phase: &str,
) -> Value {
    // Touched tile set: parse coords from events, always include the
    // mech's current tile.
    let mut touched: BTreeSet<(u8, u8)> = BTreeSet::new();
    for ev in events {
        for (x, y) in parse_coords(ev) {
            touched.insert((x, y));
        }
    }
    if let Some(idx) = board.units.iter().position(|u| u.uid == mech_uid) {
        touched.insert((board.units[idx].x, board.units[idx].y));
    }

    // 1-tile buffer (3x3 around each touched tile) for chain effects.
    let mut expanded: BTreeSet<(u8, u8)> = BTreeSet::new();
    for (tx, ty) in &touched {
        for dx in -1i8..=1 {
            for dy in -1i8..=1 {
                let nx = *tx as i8 + dx;
                let ny = *ty as i8 + dy;
                if (0..8).contains(&nx) && (0..8).contains(&ny) {
                    expanded.insert((nx as u8, ny as u8));
                }
            }
        }
    }

    let mut units: Vec<Value> = Vec::with_capacity(board.unit_count as usize);
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        let team_int: u8 = match u.team {
            crate::types::Team::Player  => 1,
            crate::types::Team::Neutral => 2,
            crate::types::Team::Enemy   => 6,
        };
        units.push(json!({
            "uid":     u.uid,
            "type":    u.type_name_str(),
            "pos":     [u.x, u.y],
            "hp":      u.hp,
            "max_hp":  u.max_hp,
            "alive":   u.hp > 0,
            "active":  u.active(),
            "is_mech": u.is_mech(),
            "team":    team_int,
            "status": {
                "fire":   u.fire(),
                "acid":   u.acid(),
                "frozen": u.frozen(),
                "shield": u.shield(),
                "web":    u.web(),
            },
        }));
    }

    let mut tiles_changed: Vec<Value> = Vec::with_capacity(expanded.len());
    for (x, y) in &expanded {
        let t = board.tile(*x, *y);
        tiles_changed.push(json!({
            "x":            x,
            "y":            y,
            "terrain":      terrain_to_str(t.terrain),
            "building_hp":  t.building_hp,
            "fire":         t.on_fire(),
            "acid":         t.acid(),
            "smoke":        t.smoke(),
            "has_pod":      t.has_pod(),
        }));
    }

    json!({
        "action_index":   action_index,
        "mech_uid":       mech_uid,
        "snapshot_phase": snapshot_phase,
        "units":          units,
        "tiles_changed":  tiles_changed,
        "grid_power":     board.grid_power,
    })
}

/// Parse `(x, y)` coord pairs out of an event string. Only on-board
/// coords (0-7) survive. Mirrors `verify.py::parse_tiles_from_events`.
fn parse_coords(s: &str) -> Vec<(u8, u8)> {
    let mut out = Vec::new();
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] != b'(' { i += 1; continue; }
        // Parse "( <digit>+ , <digit>+ )" with optional whitespace.
        let mut j = i + 1;
        while j < bytes.len() && bytes[j].is_ascii_whitespace() { j += 1; }
        let xs = j;
        while j < bytes.len() && bytes[j].is_ascii_digit() { j += 1; }
        if j == xs { i += 1; continue; }
        let x_str = &s[xs..j];
        while j < bytes.len() && bytes[j].is_ascii_whitespace() { j += 1; }
        if j >= bytes.len() || bytes[j] != b',' { i += 1; continue; }
        j += 1;
        while j < bytes.len() && bytes[j].is_ascii_whitespace() { j += 1; }
        let ys = j;
        while j < bytes.len() && bytes[j].is_ascii_digit() { j += 1; }
        if j == ys { i += 1; continue; }
        let y_str = &s[ys..j];
        while j < bytes.len() && bytes[j].is_ascii_whitespace() { j += 1; }
        if j >= bytes.len() || bytes[j] != b')' { i += 1; continue; }
        if let (Ok(x), Ok(y)) = (x_str.parse::<u8>(), y_str.parse::<u8>()) {
            if x < 8 && y < 8 {
                out.push((x, y));
            }
        }
        i = j + 1;
    }
    out
}

fn terrain_to_str(t: Terrain) -> &'static str {
    match t {
        Terrain::Ground   => "ground",
        Terrain::Building => "building",
        Terrain::Mountain => "mountain",
        Terrain::Water    => "water",
        Terrain::Chasm    => "chasm",
        Terrain::Lava     => "lava",
        Terrain::Forest   => "forest",
        Terrain::Sand     => "sand",
        Terrain::Ice      => "ice",
        Terrain::Rubble   => "rubble",
        Terrain::Fire     => "fire",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_coords_extracts_pairs_and_filters_off_board() {
        let evs = vec![
            "Killed Hornet at (3,5)".to_string(),
            "Building destroyed at (4, 2) (1 grid damage)".to_string(),
            "Pushed Hornet (3,5)->(3,6)".to_string(),
            "Out of bounds (9,9) ignored".to_string(),
            "no coords here".to_string(),
        ];
        let mut all: BTreeSet<(u8, u8)> = BTreeSet::new();
        for ev in &evs {
            for c in parse_coords(ev) {
                all.insert(c);
            }
        }
        assert!(all.contains(&(3, 5)));
        assert!(all.contains(&(4, 2)));
        assert!(all.contains(&(3, 6)));
        assert!(!all.contains(&(9, 9)));
        // "(1 grid damage)" has no comma so it's not a coord pair.
    }

    #[test]
    fn replay_solution_empty_plan_returns_baseline_outcome() {
        // Minimal bridge JSON: a single mech, no enemies, no buildings.
        let bridge = r#"{
          "tiles": [],
          "units": [
            {"uid": 1, "type": "PunchMech", "x": 4, "y": 4,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "move": 4, "active": true, "weapons": ["Prime_Punchmech"]}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 1,
          "total_turns": 5
        }"#;
        let plan = "[]";
        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        assert_eq!(v["action_results"].as_array().unwrap().len(), 0);
        assert_eq!(v["predicted_states"].as_array().unwrap().len(), 0);
        assert_eq!(v["predicted_outcome"]["mechs_alive"], 1);
        assert_eq!(v["predicted_outcome"]["enemies_alive"], 0);
        assert!(v["final_board"].is_object());
    }
}
