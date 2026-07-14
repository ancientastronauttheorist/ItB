//! Per-action replay with snapshot capture.
//!
//! Mirrors `src/solver/solver.py::replay_solution` exactly so the Python
//! call site can be swapped to the Rust backend without consumer changes.
//! For each action in the plan: run `simulate_move`, snapshot, run
//! `simulate_attack`, snapshot. After all actions: run env effects + Vek
//! attacks (`simulate_enemy_attacks`) then `apply_spawn_blocking`. Serialize
//! both the post-player board used by current-turn threat audits and the
//! post-enemy board used by Python's `evaluate_breakdown`.
//!
//! Snapshot shape matches `src/solver/verify.py::snapshot_after_action` /
//! `snapshot_after_move` byte-for-byte: same field names, same types, same
//! tile-sampling rule (touched tiles + 1-tile buffer).

use crate::board::{count_unit_deaths_between, ActionResult, Board, UnitFlags};
use crate::enemy::{
    apply_spawn_blocking,
    persisting_spawn_points,
    simulate_enemy_attacks,
};
use crate::movement::illegal_move_reason;
use crate::serde_bridge;
use crate::simulate::{
    clear_destroyed_digger_walls,
    simulate_attack_with_target2,
    simulate_move,
};
use crate::turn_projection::{
    advance_mission_tides_warning,
    board_to_json,
    requeue_enemies_heuristic,
};
use crate::types::Terrain;
use crate::weapons::{self, build_overlay_table, wid_from_str, WeaponTable, WId};

use serde_json::{json, Value};
use std::collections::BTreeSet;

#[derive(serde::Deserialize)]
struct PlanAction {
    mech_uid: u16,
    move_to: [u8; 2],
    weapon_id: String,
    target: [u8; 2],
    #[serde(default)]
    target2: Option<[u8; 2]>,
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
    let mut player_phase_result = ActionResult::default();
    let mut player_phase_unit_deaths = 0i32;

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
                    "repair_platforms_used": board.repair_platforms_used,
                });
                action_results.push(json!({
                    "enemies_killed": 0,
                    "mission_kills": 0,
                    "unit_deaths": 0,
                    "enemy_damage_dealt": 0,
                    "buildings_lost": 0,
                    "buildings_damaged": 0,
                    "mech_damage_taken": 0,
                    "mech_hp_repaired": 0,
                    "pods_collected": 0,
                    "repair_platforms_used": 0,
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

        // Phase 1: move. Diagnostic replay accepts hand-authored plans, so
        // validate moves before mutating; otherwise impossible plans can score
        // as clean by walking through buildings, units, or out-of-range tiles.
        let before_move_board = board.clone();
        let move_to = (act.move_to[0], act.move_to[1]);
        let illegal_move = illegal_move_reason(&board, mech_idx, move_to);
        let move_result = match illegal_move {
            Some(reason) => {
                let mut result = ActionResult::default();
                result.events.push(format!(
                    "illegal_move:{}:{}:{}",
                    move_to.0, move_to.1, reason
                ));
                result
            }
            None => simulate_move(&mut board, mech_idx, move_to),
        };
        let move_unit_deaths = count_unit_deaths_between(&before_move_board, &board);
        let mut post_move_extra_touched = pod_coords(&before_move_board);
        post_move_extra_touched.push(move_to);
        let post_move_snap = capture_snapshot(
            &board, i, mech_uid, &move_result.events, "after_move",
            &post_move_extra_touched,
            &new_unit_uids(&before_move_board, &board),
        );

        // Phase 2: attack
        let wid = wid_from_str(&act.weapon_id);
        let before_attack_board = board.clone();
        let attack_result = if illegal_move.is_some() {
            ActionResult::default()
        } else {
            simulate_attack_with_target2(
                &mut board,
                mech_idx,
                wid,
                (act.target[0], act.target[1]),
                act.target2.map(|t| (t[0], t[1])),
                weapons_table,
            )
        };
        if illegal_move.is_none() && wid == WId::None {
            // A replay plan entry with WId::None represents the bridge's
            // explicit skip after any move-only action, so the action is spent.
            board.units[mech_idx].set_active(false);
        }
        let attack_unit_deaths = count_unit_deaths_between(&before_attack_board, &board);
        let action_unit_deaths = move_unit_deaths + attack_unit_deaths;
        let mut all_events = move_result.events.clone();
        all_events.extend_from_slice(&attack_result.events);
        let mut post_attack_extra_touched = pod_coords(&before_attack_board);
        post_attack_extra_touched.push((act.target[0], act.target[1]));
        if let Some(target2) = act.target2 {
            post_attack_extra_touched.push((target2[0], target2[1]));
        }
        let post_attack_snap = capture_snapshot(
            &board, i, mech_uid, &all_events, "after_mech_action",
            &post_attack_extra_touched,
            &new_unit_uids(&before_attack_board, &board),
        );
        // The split replay path bypasses simulate_action_with_target2, so
        // settle Digger rock walls explicitly after capturing the action's
        // own simultaneous damage/push snapshot and before the next mech.
        clear_destroyed_digger_walls(&mut board);
        player_phase_result.merge(&move_result);
        player_phase_result.merge(&attack_result);
        player_phase_unit_deaths += action_unit_deaths;

        action_results.push(json!({
            "enemies_killed":     attack_result.enemies_killed,
            "mission_kills":      attack_result.mission_kills,
            "unit_deaths":        action_unit_deaths,
            "enemy_damage_dealt": attack_result.enemy_damage_dealt,
            "buildings_lost":     attack_result.buildings_lost,
            "buildings_damaged":  attack_result.buildings_damaged,
            "grid_damage":        attack_result.grid_damage,
            "mech_damage_taken":  attack_result.mech_damage_taken,
            "mech_hp_repaired":   move_result.mech_hp_repaired + attack_result.mech_hp_repaired,
            "mechs_killed":       attack_result.mechs_killed,
            "pods_collected":     move_result.pods_collected + attack_result.pods_collected,
            "repair_platforms_used": move_result.repair_platforms_used + attack_result.repair_platforms_used,
            "spawns_blocked":     attack_result.spawns_blocked,
            "events":             all_events,
        }));

        predicted_states.push(json!({
            "post_move":   post_move_snap,
            "post_attack": post_attack_snap,
        }));
    }

    // Preserve the complete board after every planned player action but
    // before environment/enemy resolution. Partial re-solve threat audits
    // must inspect this state; the final board below is advanced to the next
    // turn and heuristically re-queues enemies, so auditing it as the current
    // turn creates false building threats.
    let post_player_board_json: Value = serde_json::from_str(
        &board_to_json(&board, &spawn_points)
    ).map_err(|e| format!("post_player_board reparse: {}", e))?;

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
    let before_enemy_phase_board = board.clone();
    let enemy_phase_result = simulate_enemy_attacks(&mut board, &original_positions, weapons_table);
    let enemy_phase_unit_deaths = count_unit_deaths_between(&before_enemy_phase_board, &board);
    let projected_spawn_points = persisting_spawn_points(&board, &spawn_points);
    let before_spawn_block_board = board.clone();
    let spawn_block_result = apply_spawn_blocking(&mut board, &spawn_points);
    let spawn_block_unit_deaths = count_unit_deaths_between(&before_spawn_block_board, &board);
    let total_projected_kills = player_phase_result.enemies_killed
        + enemy_phase_result.enemies_killed
        + spawn_block_result.enemies_killed;
    let total_projected_mission_kills = player_phase_result.mission_kills
        + enemy_phase_result.mission_kills
        + spawn_block_result.mission_kills;
    let total_projected_unit_deaths = player_phase_unit_deaths
        + enemy_phase_unit_deaths
        + spawn_block_unit_deaths;
    board.add_mission_kills(total_projected_mission_kills);
    for i in 0..board.unit_count as usize {
        let u = &mut board.units[i];
        if u.is_enemy() && u.hp > 0 {
            u.queued_target_x = -1;
            u.queued_target_y = -1;
            u.flags.set(UnitFlags::HAS_QUEUED_ATTACK, false);
        }
    }
    for i in 0..board.unit_count as usize {
        let u = &mut board.units[i];
        if u.is_player() && u.hp > 0 {
            u.set_active(true);
            u.flags.insert(UnitFlags::CAN_MOVE);
        }
    }
    board.current_turn = board.current_turn.saturating_add(1);
    advance_mission_tides_warning(&mut board);
    requeue_enemies_heuristic(&mut board, weapons_table);

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
            let hp = u.hp.max(0);
            if u.hp > 0 { mechs_alive += 1; }
            mech_hp_list.push(json!({
                "uid": u.uid,
                "type": u.type_name_str(),
                "hp": hp,
                "max_hp": u.max_hp,
            }));
        } else if u.is_enemy() && u.hp > 0 && !u.burrowed() {
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
        "enemies_killed_by_player":       player_phase_result.enemies_killed,
        "enemies_killed_by_enemy_phase":  enemy_phase_result.enemies_killed,
        "enemies_killed_by_spawn_block":  spawn_block_result.enemies_killed,
        "enemies_killed_total_projected": total_projected_kills,
        "mission_kills_by_player":        player_phase_result.mission_kills,
        "mission_kills_by_enemy_phase":   enemy_phase_result.mission_kills,
        "mission_kills_by_spawn_block":   spawn_block_result.mission_kills,
        "mission_kills_total_projected":  total_projected_mission_kills,
        "mission_kills_done_projected":   board.mission_kills_done,
        "unit_deaths_by_player":          player_phase_unit_deaths,
        "unit_deaths_by_enemy_phase":     enemy_phase_unit_deaths,
        "unit_deaths_by_spawn_block":     spawn_block_unit_deaths,
        "unit_deaths_total_projected":    total_projected_unit_deaths,
        "mission_mountains_destroyed_projected": board.projected_mountains_destroyed(),
    });

    // Serialize the final post-enemy board so Python's evaluate_breakdown
    // can build a Board and score it. board_to_json emits bridge JSON;
    // Board.from_bridge_data on the Python side consumes it.
    let final_board_json: Value = serde_json::from_str(
        &board_to_json(&board, &projected_spawn_points)
    ).map_err(|e| format!("final_board reparse: {}", e))?;

    let out = json!({
        "action_results":   action_results,
        "predicted_states": predicted_states,
        "predicted_outcome": predicted_outcome,
        "post_player_board": post_player_board_json,
        "final_board":       final_board_json,
    });
    Ok(out.to_string())
}

fn pod_coords(board: &Board) -> Vec<(u8, u8)> {
    let mut pods = Vec::new();
    for x in 0..8u8 {
        for y in 0..8u8 {
            if board.tile(x, y).has_pod() {
                pods.push((x, y));
            }
        }
    }
    pods
}

// ── Snapshot helpers ────────────────────────────────────────────────────────

/// Mirror `src/solver/verify.py::snapshot_after_action` (and
/// `snapshot_after_move`). Captures every unit (alive or dead — diff
/// engine needs death/spawn detection) and the tiles touched by `events` or
/// `extra_touched` + a 1-tile buffer + the mech's current tile + every building
/// and currently-present pod tile. Buildings and pods are included globally
/// because they are critical safety state even when outside the sparse
/// event-derived neighborhood.
fn capture_snapshot(
    board: &Board,
    action_index: usize,
    mech_uid: u16,
    events: &[String],
    snapshot_phase: &str,
    extra_touched: &[(u8, u8)],
    unstable_spawn_uids: &[u16],
) -> Value {
    // Touched tile set: parse coords from events, always include the
    // mech's current tile.
    let mut touched: BTreeSet<(u8, u8)> = BTreeSet::new();
    for ev in events {
        for (x, y) in parse_coords(ev) {
            touched.insert((x, y));
        }
    }
    for &(x, y) in extra_touched {
        if x < 8 && y < 8 {
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
    for x in 0..8u8 {
        for y in 0..8u8 {
            let t = board.tile(x, y);
            if t.terrain == Terrain::Building || t.has_pod() {
                expanded.insert((x, y));
            }
        }
    }

    let mut units: Vec<Value> = Vec::with_capacity(board.unit_count as usize);
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.burrowed() && u.hp > 0 { continue; }
        let team_int: u8 = match u.team {
            crate::types::Team::Player  => 1,
            crate::types::Team::Neutral => 2,
            crate::types::Team::Enemy   => 6,
        };
        let queued_target = if u.queued_target_x >= 0 && u.queued_target_y >= 0 {
            json!([u.queued_target_x, u.queued_target_y])
        } else {
            Value::Null
        };
        let queued_origin = if u.queued_origin_x >= 0 && u.queued_origin_y >= 0 {
            json!([u.queued_origin_x, u.queued_origin_y])
        } else {
            Value::Null
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
            "queued_target": queued_target,
            "queued_origin": queued_origin,
            "has_queued_attack": u.has_queued_attack(),
            "status": {
                "fire":   u.fire(),
                "acid":   u.acid(),
                "frozen": u.frozen(),
                "shield": u.shield(),
                "web":    u.web(),
                "boosted": u.boosted(),
                "infected": u.infected(),
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
            "frozen":       t.frozen(),
            "shield":       t.shield(),
            "has_pod":      t.has_pod(),
            "repair_platform": t.repair_platform(),
        }));
    }

    json!({
        "action_index":   action_index,
        "mech_uid":       mech_uid,
        "snapshot_phase": snapshot_phase,
        "units":          units,
        "tiles_changed":  tiles_changed,
        "grid_power":     board.grid_power,
        "repair_platforms_used": board.repair_platforms_used,
        "unstable_spawn_uids": unstable_spawn_uids,
    })
}

fn new_unit_uids(before: &Board, after: &Board) -> Vec<u16> {
    let before_uids: BTreeSet<u16> = before.units[..before.unit_count as usize]
        .iter()
        .map(|unit| unit.uid)
        .collect();
    after.units[..after.unit_count as usize]
        .iter()
        .filter(|unit| !before_uids.contains(&unit.uid))
        .map(|unit| unit.uid)
        .collect()
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
    use serde_json::json;

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

    /// Regression: `_REPAIR` plans must heal +1 HP and deactivate the mech in
    /// the predicted snapshot. Pre-fix `wid_from_str("_REPAIR")` returned
    /// `WId::None`, so `simulate_attack` skipped the Repair branch entirely
    /// and the predicted state showed (hp unchanged, active=true) while the
    /// game produced (hp+1, active=false). That mismatch generated 24+
    /// `click_miss|_REPAIR|attack` entries in failure_db.jsonl.
    #[test]
    fn replay_solution_repair_plan_predicts_heal_and_deactivate() {
        // PunchMech at (4,4), HP 1/3, no enemies, no buildings. Plan: repair.
        let bridge = r#"{
          "tiles": [],
          "units": [
            {"uid": 1, "type": "PunchMech", "x": 4, "y": 4,
             "hp": 1, "max_hp": 3, "team": 1, "mech": true,
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
        // move_to == current pos (no actual move), weapon_id _REPAIR, target self.
        let plan = r#"[{
          "mech_uid": 1,
          "move_to": [4, 4],
          "weapon_id": "_REPAIR",
          "target": [4, 4]
        }]"#;
        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        let states = v["predicted_states"].as_array().unwrap();
        assert_eq!(states.len(), 1, "one action → one predicted state");
        let post_attack = &states[0]["post_attack"];
        let units = post_attack["units"].as_array().unwrap();
        let mech = units.iter().find(|u| u["uid"] == 1).expect("mech in snapshot");
        assert_eq!(mech["hp"], 2,
            "Repair must heal +1 HP in predicted snapshot (was {} pre-fix)",
            mech["hp"]);
        assert_eq!(mech["active"], false,
            "Repair must clear active flag in predicted snapshot (was {} pre-fix)",
            mech["active"]);
    }

    #[test]
    fn replay_solution_reports_total_unit_deaths() {
        let bridge = r#"{
          "tiles": [],
          "units": [
            {"uid": 1, "type": "PunchMech", "x": 4, "y": 4,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "move": 4, "active": true, "weapons": ["Prime_Punchmech"]},
            {"uid": 10, "type": "Spiderling1", "x": 4, "y": 3,
             "hp": 1, "max_hp": 1, "team": 6, "mech": false,
             "move": 3, "active": false, "weapons": ["SpiderlingAtk1"]}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 1,
          "total_turns": 5
        }"#;
        let plan = r#"[{
          "mech_uid": 1,
          "move_to": [4, 4],
          "weapon_id": "Prime_Punchmech",
          "target": [4, 3]
        }]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        assert_eq!(v["action_results"][0]["unit_deaths"], 1);
        assert_eq!(v["predicted_outcome"]["unit_deaths_by_player"], 1);
        assert_eq!(v["predicted_outcome"]["unit_deaths_total_projected"], 1);
    }

    #[test]
    fn replay_solution_snapshots_include_boosted_status() {
        let bridge = r#"{
          "tiles": [],
          "units": [
            {"uid": 0, "type": "JetMech", "x": 2, "y": 3,
             "hp": 2, "max_hp": 2, "team": 1, "mech": true,
             "flying": true, "move": 5, "active": true, "boosted": true,
             "weapons": ["Brute_Jetmech"]}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 1,
          "total_turns": 4
        }"#;
        let plan = r#"[{
          "mech_uid": 0,
          "move_to": [2, 3],
          "weapon_id": "None",
          "target": [255, 255]
        }]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        let post_attack_units = v["predicted_states"][0]["post_attack"]["units"].as_array().unwrap();
        let jet = post_attack_units.iter().find(|u| u["uid"] == 0).unwrap();
        assert_eq!(jet["active"], false,
            "Replay WId::None plan entries represent bridge skips and must deactivate the unit");
        assert_eq!(jet["status"]["boosted"], true,
            "Replay snapshots must preserve Boosted so verify does not create false status diffs");
    }

    #[test]
    fn replay_solution_snapshots_preserve_queued_attacks() {
        let bridge = r#"{
          "tiles": [],
          "units": [
            {"uid": 1, "type": "PunchMech", "x": 4, "y": 4,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "move": 4, "active": true, "weapons": ["Prime_Punchmech"]},
            {"uid": 99, "type": "BurnbugBoss", "x": 4, "y": 2,
             "hp": 6, "max_hp": 6, "team": 6, "weapons": ["BurnbugAtkB"],
             "has_queued_attack": true,
             "queued_target": [3, 2],
             "queued_origin": [4, 2]}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 1,
          "total_turns": 5
        }"#;
        let plan = r#"[{
          "mech_uid": 1,
          "move_to": [4, 4],
          "weapon_id": "None",
          "target": [255, 255]
        }]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        for phase in ["post_move", "post_attack"] {
            let units = v["predicted_states"][0][phase]["units"].as_array().unwrap();
            let boss = units.iter().find(|u| u["uid"] == 99).unwrap();
            assert_eq!(boss["queued_target"], json!([3, 2]));
            assert_eq!(boss["queued_origin"], json!([4, 2]));
            assert_eq!(boss["has_queued_attack"], true);
        }
    }

    #[test]
    fn replay_solution_burrower_retreat_prevents_phantom_boss_kill() {
        let bridge = r#"{
            "mission_id": "Mission_BlobberBoss",
            "turn": 4,
            "total_turns": 4,
            "grid_power": 7,
            "tiles": [
                {"x": 5, "y": 5, "terrain": "forest"}
            ],
            "units": [
                {
                    "uid": 1, "type": "IgniteMech", "x": 0, "y": 6,
                    "hp": 4, "max_hp": 4, "team": 1, "mech": true,
                    "active": true, "move": 3, "weapons": ["Ranged_Ignite"]
                },
                {
                    "uid": 2, "type": "HornetMech", "x": 2, "y": 5,
                    "hp": 5, "max_hp": 5, "team": 1, "mech": true,
                    "active": true, "flying": true, "move": 4,
                    "weapons": ["Vek_Hornet"]
                },
                {
                    "uid": 1124, "type": "BlobberBoss", "x": 5, "y": 5,
                    "hp": 5, "max_hp": 5, "team": 6, "pushable": true,
                    "weapons": ["BlobberAtkB"]
                },
                {
                    "uid": 1197, "type": "Burrower2", "x": 4, "y": 5,
                    "hp": 5, "max_hp": 5, "team": 6, "pushable": false,
                    "has_queued_attack": true,
                    "queued_target": [4, 6], "queued_origin": [4, 5],
                    "weapons": ["Burrower_Atk2"]
                }
            ]
        }"#;
        let plan = r#"[
            {
                "mech_uid": 2, "move_to": [6, 5],
                "weapon_id": "Vek_Hornet", "target": [5, 5]
            },
            {
                "mech_uid": 1, "move_to": [1, 4],
                "weapon_id": "Ranged_Ignite", "target": [5, 4]
            }
        ]"#;

        let raw = replay_solution(bridge, plan).expect("exact HQ replay succeeds");
        let value: Value = serde_json::from_str(&raw).expect("valid replay JSON");

        let post_player = value["post_player_board"]["units"]
            .as_array()
            .expect("post-player units");
        assert!(
            post_player.iter().all(|u| u["uid"] != 1197),
            "the damaged Alpha Burrower should already be underground",
        );
        let post_boss = post_player
            .iter()
            .find(|u| u["uid"] == 1124)
            .expect("boss survives player phase");
        assert_eq!(post_boss["hp"], 3);
        assert_eq!(post_boss["x"], 5);
        assert_eq!(post_boss["y"], 6);
        assert_eq!(post_boss["fire"], true);

        let final_units = value["final_board"]["units"]
            .as_array()
            .expect("final units");
        assert!(final_units.iter().all(|u| u["uid"] != 1197));
        let final_boss = final_units
            .iter()
            .find(|u| u["uid"] == 1124)
            .expect("boss survives the canceled Burrower slam");
        assert_eq!(final_boss["hp"], 2);
        assert_eq!(value["predicted_outcome"]["enemies_killed_by_enemy_phase"], 0);
    }

    #[test]
    fn replay_solution_reverse_thrusters_backblast_smoke_does_not_same_action_heal() {
        let bridge = r#"{
          "tiles": [],
          "units": [
            {"uid": 0, "type": "NeedleMech", "x": 3, "y": 3,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "flying": true, "move": 4, "active": true,
             "weapons": ["Brute_KickBack", "Passive_HealingSmoke"]},
            {"uid": 10, "type": "Spiderling1", "x": 3, "y": 2,
             "hp": 1, "max_hp": 1, "team": 6}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 2,
          "total_turns": 4
        }"#;
        let plan = r#"[{
          "mech_uid": 0,
          "move_to": [3, 3],
          "weapon_id": "Brute_KickBack",
          "target": [3, 5]
        }]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        assert_eq!(v["action_results"][0]["mech_damage_taken"], 1);
        let post_attack = &v["predicted_states"][0]["post_attack"];
        let mech = post_attack["units"].as_array().unwrap()
            .iter()
            .find(|u| u["uid"] == 0)
            .unwrap();
        assert_eq!(
            mech["hp"], 2,
            "Reverse Thrusters recoil should remain in replay snapshots until a later Nanofilter trigger"
        );
        let tiles = post_attack["tiles_changed"].as_array().unwrap();
        let backblast = tiles.iter()
            .find(|t| t["x"] == 3 && t["y"] == 2)
            .expect("backblast tile should be serialized");
        assert_eq!(
            backblast["smoke"], true,
            "Reverse Thrusters smokes the damaged backblast tile"
        );
        assert!(
            tiles.iter().all(|t| !(t["x"] == 3 && t["y"] == 3 && t["smoke"] == true)),
            "Reverse Thrusters should not leave smoke on the launch tile"
        );
    }

    #[test]
    fn replay_solution_smoldering_shells_adjacent_live_footprint() {
        let bridge = r#"{
          "tiles": [
            {"x": 4, "y": 3, "terrain": "building", "building_hp": 1}
          ],
          "units": [
            {"uid": 1, "type": "SmokeMech", "x": 4, "y": 4,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "move": 3, "active": true,
             "weapons": ["Ranged_SmokeFire"]},
            {"uid": 653, "type": "Scorpion1", "x": 4, "y": 2,
             "hp": 3, "max_hp": 3, "team": 6, "mech": false,
             "move": 3, "active": false,
             "weapons": ["ScorpionAtk1"]},
            {"uid": 655, "type": "Spiderling1", "x": 3, "y": 2,
             "hp": 1, "max_hp": 1, "team": 6, "mech": false,
             "move": 3, "active": false, "fire": true,
             "weapons": ["SpiderlingAtk1"]}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 2,
          "total_turns": 4
        }"#;
        let plan = r#"[{
          "mech_uid": 1,
          "move_to": [4, 4],
          "weapon_id": "Ranged_SmokeFire",
          "target": [4, 2]
        }]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        let post_attack = &v["predicted_states"][0]["post_attack"];
        let units = post_attack["units"].as_array().unwrap();
        let spiderling = units.iter().find(|u| u["uid"] == 655).unwrap();
        assert_eq!(
            spiderling["status"]["fire"], true,
            "Smoldering Shells adjacent effect should skip occupied adjacent units entirely"
        );
        let building_tile = post_attack["tiles_changed"].as_array().unwrap()
            .iter()
            .find(|t| t["x"] == 4 && t["y"] == 3)
            .unwrap();
        assert_eq!(
            building_tile["smoke"], false,
            "Smoldering Shells adjacent effect should skip building tiles"
        );
    }

    #[test]
    fn replay_solution_counts_aerial_bombs_pod_collection() {
        let bridge = r#"{
          "tiles": [
            {"x": 3, "y": 5, "terrain": "ground", "has_pod": true}
          ],
          "units": [
            {"uid": 0, "type": "JetMech", "x": 3, "y": 3,
             "hp": 2, "max_hp": 2, "team": 1, "mech": true,
             "flying": true, "move": 5, "active": true,
             "weapons": ["Brute_Jetmech"]}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 2,
          "total_turns": 4
        }"#;
        let plan = r#"[{
          "mech_uid": 0,
          "move_to": [3, 3],
          "weapon_id": "Brute_Jetmech",
          "target": [3, 5]
        }]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        assert_eq!(v["action_results"][0]["pods_collected"], 1);

        let post_attack = &v["predicted_states"][0]["post_attack"];
        let jet = post_attack["units"].as_array().unwrap()
            .iter()
            .find(|u| u["uid"] == 0)
            .unwrap();
        assert_eq!(jet["pos"], json!([3, 5]));
        let pod_tile = post_attack["tiles_changed"].as_array().unwrap()
            .iter()
            .find(|t| t["x"] == 3 && t["y"] == 5)
            .unwrap();
        assert_eq!(pod_tile["has_pod"], false);
    }

    #[test]
    fn replay_solution_distant_ranged_ignite_serializes_destroyed_time_pod() {
        let bridge = r#"{
          "tiles": [
            {"x": 1, "y": 2, "terrain": "ground", "has_pod": true}
          ],
          "units": [
            {"uid": 0, "type": "IgniteMech", "x": 6, "y": 2,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "move": 3, "active": true,
             "weapons": ["Ranged_Ignite"]}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 2,
          "total_turns": 4
        }"#;
        let plan = r#"[{
          "mech_uid": 0,
          "move_to": [6, 2],
          "weapon_id": "Ranged_Ignite",
          "target": [1, 2]
        }]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();

        let post_move_tiles = v["predicted_states"][0]["post_move"]["tiles_changed"]
            .as_array()
            .unwrap();
        let pod_before_attack = post_move_tiles
            .iter()
            .find(|tile| tile["x"] == 1 && tile["y"] == 2)
            .expect("distant pre-attack pod must be serialized");
        assert_eq!(pod_before_attack["has_pod"], true);

        let post_attack_tiles = v["predicted_states"][0]["post_attack"]["tiles_changed"]
            .as_array()
            .unwrap();
        let burned_pod = post_attack_tiles
            .iter()
            .find(|tile| tile["x"] == 1 && tile["y"] == 2)
            .expect("distant Ignite target must be serialized");
        assert_eq!(burned_pod["fire"], true);
        assert_eq!(burned_pod["has_pod"], false);

        for board_key in ["post_player_board", "final_board"] {
            let tiles = v[board_key]["tiles"].as_array().unwrap();
            assert!(
                tiles.iter().all(|tile| tile["has_pod"].as_bool() != Some(true)),
                "{board_key} must not retain a pod destroyed by Ignite"
            );
        }
    }

    #[test]
    fn replay_solution_preserves_building_tile_shields_in_all_checkpoints() {
        let bridge = r#"{
          "mission_id": "Mission_Belt",
          "tiles": [
            {"x": 1, "y": 5, "terrain": "building", "building_hp": 1, "shield": true},
            {"x": 1, "y": 6, "terrain": "building", "building_hp": 1, "shield": true},
            {"x": 4, "y": 3, "terrain": "building", "building_hp": 1, "shield": true}
          ],
          "units": [
            {"uid": 0, "type": "PunchMech", "x": 6, "y": 4,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "move": 4, "active": true, "weapons": ["Prime_Punchmech"]}
          ],
          "grid_power": 4,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 1,
          "total_turns": 4
        }"#;
        let plan = r#"[{
          "mech_uid": 0,
          "move_to": [6, 4],
          "weapon_id": "None",
          "target": [255, 255]
        }]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        let shielded = [(1, 5), (1, 6), (4, 3)];

        for phase in ["post_move", "post_attack"] {
            let tiles = v["predicted_states"][0][phase]["tiles_changed"]
                .as_array()
                .unwrap();
            for (x, y) in shielded {
                let tile = tiles
                    .iter()
                    .find(|tile| tile["x"] == x && tile["y"] == y)
                    .expect("building tiles are always included in action snapshots");
                assert_eq!(tile["shield"], true, "{phase} omitted shield at ({x},{y})");
            }
        }

        for checkpoint in ["post_player_board", "final_board"] {
            let tiles = v[checkpoint]["tiles"].as_array().unwrap();
            for (x, y) in shielded {
                let tile = tiles
                    .iter()
                    .find(|tile| tile["x"] == x && tile["y"] == y)
                    .expect("shielded building should be serialized");
                assert_eq!(
                    tile["shield"], true,
                    "{checkpoint} omitted shield at ({x},{y})"
                );
            }
        }
    }

    #[test]
    fn replay_solution_empty_plan_returns_baseline_outcome() {
        // The current-turn enemy has no queued attack. The final board advances
        // one turn and heuristically queues it against the only building.
        let bridge = r#"{
          "tiles": [
            {"x": 4, "y": 2, "terrain": "building", "building_hp": 2}
          ],
          "units": [
            {"uid": 1, "type": "PunchMech", "x": 4, "y": 4,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "move": 4, "active": true, "weapons": ["Prime_Punchmech"]},
            {"uid": 10, "type": "Firefly1", "x": 6, "y": 2,
             "hp": 3, "max_hp": 3, "team": 6, "mech": false,
             "move": 3, "active": false, "weapons": ["FireflyAtk1"],
             "has_queued_attack": false}
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
        assert_eq!(v["predicted_outcome"]["enemies_alive"], 1);
        assert!(v["post_player_board"].is_object());
        assert_eq!(v["post_player_board"]["turn"], 1);
        let post_enemy = v["post_player_board"]["units"].as_array().unwrap()
            .iter().find(|u| u["uid"] == 10).unwrap();
        assert_eq!(post_enemy["queued_target"], json!([-1, -1]));
        assert_ne!(post_enemy["has_queued_attack"], true);
        assert!(v["final_board"].is_object());
        assert_eq!(v["final_board"]["turn"], 2);
        let next_turn_enemy = v["final_board"]["units"].as_array().unwrap()
            .iter().find(|u| u["uid"] == 10).unwrap();
        assert_eq!(next_turn_enemy["queued_target"], json!([4, 2]));
        assert_eq!(next_turn_enemy["has_queued_attack"], true);
    }

    #[test]
    fn replay_final_board_consumes_unblocked_spawn_markers() {
        let bridge = r#"{
          "tiles": [],
          "units": [
            {"uid": 1, "type": "PunchMech", "x": 2, "y": 2,
             "hp": 1, "max_hp": 3, "team": 1, "mech": true,
             "move": 3, "active": false, "weapons": ["Prime_Punchmech"]}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [[2, 2], [5, 5]],
          "environment_danger": [],
          "remaining_spawns": 2,
          "turn": 1,
          "total_turns": 5
        }"#;

        let raw = replay_solution(bridge, "[]").expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();

        assert_eq!(
            v["post_player_board"]["spawning_tiles"],
            json!([[2, 2], [5, 5]]),
            "pre-emergence evidence must retain every current marker",
        );
        assert_eq!(
            v["final_board"]["spawning_tiles"],
            json!([[2, 2]]),
            "only the marker blocked at emergence persists",
        );
        let wreck = v["final_board"]["units"].as_array().unwrap()
            .iter()
            .find(|unit| unit["uid"] == 1)
            .expect("the disabled player mech must persist as a wreck");
        assert_eq!((wreck["x"].as_u64(), wreck["y"].as_u64()), (Some(2), Some(2)));
        assert_eq!(wreck["hp"], 0);
    }

    #[test]
    fn replay_solution_mission_tides_advances_final_warning_lane() {
        let bridge = r#"{
          "mission_id": "Mission_Tides",
          "turn": 2,
          "total_turns": 3,
          "tiles": [],
          "environment_danger_v2": [[1, 3, 1, 1, 1]],
          "spawning_tiles": [],
          "remaining_spawns": 0,
          "grid_power": 7,
          "grid_power_max": 7,
          "units": [
            {"uid": 0, "type": "PunchMech", "x": 1, "y": 5,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "move": 4, "active": true, "weapons": ["Prime_Punchmech"]}
          ]
        }"#;
        let plan = r#"[{
          "mech_uid": 0,
          "move_to": [1, 4],
          "weapon_id": "None",
          "target": [255, 255]
        }]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        let final_board = &v["final_board"];
        assert_eq!(final_board["turn"], 3);
        let danger = final_board["environment_danger_v2"].as_array().unwrap();
        assert!(danger.iter().any(|entry| entry == &json!([1, 4, 1, 1, 1])));
        assert!(!danger.iter().any(|entry| entry == &json!([1, 3, 1, 1, 1])));
    }

    #[test]
    fn replay_solution_terratide_smokes_full_row_and_advances_final_warning_lane() {
        let bridge = r#"{
          "mission_id": "Mission_Terratide",
          "env_type": "sandstorm",
          "turn": 2,
          "total_turns": 3,
          "tiles": [
            {"x": 0, "y": 4, "terrain": "building", "building_hp": 1},
            {"x": 0, "y": 3, "terrain": "building", "building_hp": 1}
          ],
          "environment_danger_v2": [
            [1, 4, 1, 0, 0], [2, 4, 1, 0, 0], [3, 4, 1, 0, 0],
            [4, 4, 1, 0, 0], [5, 4, 1, 0, 0], [6, 4, 1, 0, 0],
            [7, 4, 1, 0, 0]
          ],
          "spawning_tiles": [],
          "remaining_spawns": 0,
          "grid_power": 5,
          "grid_power_max": 7,
          "units": []
        }"#;

        let raw = replay_solution(bridge, "[]").expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        let final_board = &v["final_board"];
        assert_eq!(final_board["turn"], 3);
        assert_eq!(final_board["grid_power"], 5);

        let danger = final_board["environment_danger_v2"].as_array().unwrap();
        assert_eq!(danger.len(), 7);
        assert!(danger.iter().all(|entry| {
            entry[1] == json!(3) && entry[3] == json!(0) && entry[4] == json!(0)
        }));
        assert!(!danger.iter().any(|entry| entry[1] == json!(4)));
        for x in 1u8..8 {
            assert!(danger.iter().any(|entry| entry == &json!([x, 3, 1, 0, 0])));
        }

        let current_lane_building = final_board["tiles"]
            .as_array()
            .unwrap()
            .iter()
            .find(|tile| tile["x"] == json!(0) && tile["y"] == json!(4))
            .expect("current-lane building should be serialized");
        assert_eq!(current_lane_building["building_hp"], 1);
        assert_eq!(current_lane_building["smoke"], true);
    }

    #[test]
    fn replay_solution_mission_tides_wave_destroys_pod() {
        let bridge = r#"{
          "mission_id": "Mission_Tides",
          "turn": 2,
          "total_turns": 3,
          "tiles": [
            {"x": 1, "y": 3, "terrain": "ground", "has_pod": true}
          ],
          "environment_danger_v2": [[1, 3, 1, 1, 1]],
          "spawning_tiles": [],
          "remaining_spawns": 0,
          "grid_power": 7,
          "grid_power_max": 7,
          "units": []
        }"#;
        let plan = "[]";

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        let final_tiles = v["final_board"]["tiles"].as_array().unwrap();
        let pod_tiles: Vec<_> = final_tiles.iter()
            .filter(|tile| tile["has_pod"].as_bool() == Some(true))
            .collect();
        assert!(pod_tiles.is_empty(), "Tidal wave should destroy pods on flooded tiles");
    }

    #[test]
    fn replay_solution_noops_attack_from_smoke() {
        let bridge = r#"{
          "tiles": [
            {"x": 3, "y": 7, "terrain": "ground", "smoke": true}
          ],
          "units": [
            {"uid": 0, "type": "JetMech", "x": 4, "y": 7,
             "hp": 4, "max_hp": 2, "team": 1, "mech": true,
             "flying": true, "move": 5, "active": true,
             "weapons": ["Brute_Jetmech"]}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 2,
          "total_turns": 4
        }"#;
        let plan = r#"[{
          "mech_uid": 0,
          "move_to": [3, 7],
          "weapon_id": "Brute_Jetmech",
          "target": [3, 5]
        }]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        let events = v["action_results"][0]["events"].as_array().unwrap();
        assert!(
            events.iter().any(|e| e.as_str() == Some("illegal_attack_smoke:3:7")),
            "smoked attack origin should be reported as an illegal diagnostic action"
        );
        let post_attack_units = v["predicted_states"][0]["post_attack"]["units"].as_array().unwrap();
        let jet = post_attack_units.iter().find(|u| u["uid"] == 0).unwrap();
        assert_eq!(jet["pos"], json!([3, 7]), "illegal smoke attack must not leap to target");
    }

    #[test]
    fn replay_solution_noops_off_axis_rocket_target() {
        let bridge = r#"{
          "tiles": [],
          "units": [
            {"uid": 1, "type": "RocketMech", "x": 2, "y": 3,
             "hp": 5, "max_hp": 3, "team": 1, "mech": true,
             "move": 3, "active": true,
             "weapons": ["Ranged_Rocket_A"]},
            {"uid": 899, "type": "Burnbug1", "x": 4, "y": 5,
             "hp": 3, "max_hp": 3, "team": 6, "weapons": ["BurnbugAtk1"]}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 2,
          "total_turns": 4
        }"#;
        let plan = r#"[{
          "mech_uid": 1,
          "move_to": [2, 3],
          "weapon_id": "Ranged_Rocket_A",
          "target": [4, 5]
        }]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();
        let events = v["action_results"][0]["events"].as_array().unwrap();
        assert!(
            events.iter().any(|e| {
                e.as_str()
                    .is_some_and(|s| s.starts_with("illegal_weapon_target:4:5:"))
            }),
            "off-axis Rocket Artillery target should be reported as illegal"
        );
        let post_attack_units = v["predicted_states"][0]["post_attack"]["units"].as_array().unwrap();
        let burnbug = post_attack_units.iter().find(|u| u["uid"] == 899).unwrap();
        assert_eq!(burnbug["hp"], 3, "illegal off-axis rocket target must not damage Burnbug1");
    }

    #[test]
    fn replay_solution_train_stop_is_visible_to_next_player_action() {
        // Chaos Roll Unfair run 20260710_013601_568, Mission_Train turn 3.
        // Hydrant killed Train_Pawn uid 164, Mission_Train immediately
        // replaced it with Train_Damaged uid 198, then the already-planned
        // Mirror Shot at that same tile killed the replacement. Before the
        // player-action mission hook, replay left a dead Train_Pawn in place,
        // so Mirror Shot passed through and falsely preserved the objective.
        let bridge = r#"{
          "mission_id": "Mission_Train",
          "protect_objective_unit_types": ["Train"],
          "tiles": [
            {"x": 0, "y": 4, "terrain": "building", "building_hp": 1}
          ],
          "units": [
            {"uid": 0, "type": "NeedleMech", "x": 5, "y": 5,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "flying": true, "move": 4, "active": true,
             "weapons": ["Brute_KickBack"]},
            {"uid": 1, "type": "MirrorMech", "x": 2, "y": 2,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "move": 3, "active": true, "weapons": ["Brute_Mirrorshot"]},
            {"uid": 2, "type": "HydrantMech", "x": 5, "y": 1,
             "hp": 2, "max_hp": 3, "team": 1, "mech": true,
             "move": 3, "active": true, "weapons": ["Science_KO_Crack"]},
            {"uid": 164, "type": "Train_Pawn", "x": 4, "y": 2,
             "hp": 1, "max_hp": 1, "team": 1, "mech": false,
             "move": 0, "active": false, "pushable": false,
             "weapons": ["Train_Move"]},
            {"uid": 164, "type": "Train_Pawn", "x": 4, "y": 3,
             "hp": 1, "max_hp": 1, "team": 1, "mech": false,
             "move": 0, "active": false, "pushable": false,
             "is_extra_tile": true, "weapons": []},
            {"uid": 196, "type": "Moth2", "x": 4, "y": 6,
             "hp": 3, "max_hp": 6, "team": 6, "mech": false,
             "move": 3, "active": false, "weapons": ["MothAtk2"],
             "has_queued_attack": true, "queued_origin": [4, 6],
             "queued_target": [4, 3]},
            {"uid": 197, "type": "Moth1", "x": 4, "y": 4,
             "hp": 4, "max_hp": 4, "team": 6, "mech": false,
             "move": 3, "active": false, "weapons": ["MothAtk1"],
             "has_queued_attack": true, "queued_origin": [4, 4],
             "queued_target": [0, 4]}
          ],
          "attack_order": [196, 197],
          "grid_power": 2,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 3,
          "total_turns": 3
        }"#;
        let plan = r#"[
          {"mech_uid": 0, "move_to": [5, 5],
           "weapon_id": "_REPAIR", "target": [5, 5]},
          {"mech_uid": 2, "move_to": [3, 2],
           "weapon_id": "Science_KO_Crack", "target": [4, 2]},
          {"mech_uid": 1, "move_to": [4, 1],
           "weapon_id": "Brute_Mirrorshot", "target": [4, 2]}
        ]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();

        let post_seismic = v["predicted_states"][1]["post_attack"]["units"]
            .as_array()
            .unwrap();
        let stopped: Vec<_> = post_seismic
            .iter()
            .filter(|u| u["uid"] == 198 && u["type"] == "Train_Damaged")
            .collect();
        assert_eq!(stopped.len(), 2, "replacement keeps both train tiles");
        assert!(stopped.iter().all(|u| u["alive"] == true));
        assert!(stopped.iter().any(|u| u["pos"] == json!([4, 2])));
        assert!(stopped.iter().any(|u| u["pos"] == json!([4, 3])));

        let post_mirror = v["predicted_states"][2]["post_attack"]["units"]
            .as_array()
            .unwrap();
        let destroyed: Vec<_> = post_mirror
            .iter()
            .filter(|u| u["uid"] == 198 && u["type"] == "Train_Damaged")
            .collect();
        assert_eq!(destroyed.len(), 2);
        assert!(
            destroyed.iter().all(|u| u["alive"] == false),
            "the next player action must hit and destroy the fresh stopped train",
        );
        assert_eq!(v["action_results"][1]["unit_deaths"], 1);
        assert_eq!(v["action_results"][2]["unit_deaths"], 1);
        assert_eq!(
            v["predicted_outcome"]["grid_power"], 1,
            "queued Moth building damage, not the train transition, spends the final grid",
        );
    }

    #[test]
    fn replay_solution_shaman_hq_totem_retraces_after_needle_vacates() {
        // Chaos Roll Unfair run 20260710_013601_568, Mission_ShamanBoss
        // turn 1. This is the live board and exact three-action line that
        // v339 scored as grid-safe. Reverse Thrusters vacates visual E5 and
        // smokes Firefly2 at F4. TotemB must then re-run GetProjectileEnd in
        // its original direction, pass through empty E5, and destroy the
        // 2-HP E6 building for the final grid power.
        let bridge = r#"{
          "mission_id": "Mission_ShamanBoss",
          "destroy_objective_unit_types": ["ShamanBoss"],
          "tiles": [
            {"x": 1, "y": 2, "terrain": "building", "building_hp": 1, "unique_building": true},
            {"x": 2, "y": 2, "terrain": "building", "building_hp": 1},
            {"x": 1, "y": 3, "terrain": "building", "building_hp": 1},
            {"x": 2, "y": 3, "terrain": "building", "building_hp": 2},
            {"x": 1, "y": 6, "terrain": "building", "building_hp": 1},
            {"x": 5, "y": 6, "terrain": "building", "building_hp": 2},
            {"x": 6, "y": 6, "terrain": "building", "building_hp": 2}
          ],
          "units": [
            {"uid": 0, "type": "NeedleMech", "x": 3, "y": 3,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "flying": true, "massive": true, "pushable": true,
             "shield": true, "move": 4, "active": true,
             "weapons": ["Brute_KickBack"]},
            {"uid": 1, "type": "MirrorMech", "x": 2, "y": 4,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "massive": true, "pushable": true, "move": 3, "active": true,
             "weapons": ["Brute_Mirrorshot"]},
            {"uid": 2, "type": "HydrantMech", "x": 3, "y": 5,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "flying": true, "massive": true, "pushable": true,
             "move": 4, "active": true, "weapons": ["Science_KO_Crack"]},
            {"uid": 204, "type": "ShamanBoss", "x": 5, "y": 5,
             "hp": 6, "max_hp": 5, "team": 6, "mech": false,
             "massive": true, "pushable": true, "move": 2, "active": false,
             "weapons": ["ShamanAtkB"], "has_queued_attack": false},
            {"uid": 205, "type": "Jelly_Health1", "x": 6, "y": 5,
             "hp": 2, "max_hp": 2, "team": 6, "mech": false,
             "flying": true, "pushable": true, "move": 2, "active": false,
             "weapons": [], "has_queued_attack": false},
            {"uid": 206, "type": "Firefly1", "x": 6, "y": 4,
             "hp": 4, "max_hp": 3, "team": 6, "mech": false,
             "pushable": true, "move": 2, "active": false,
             "weapons": ["FireflyAtk1"], "weapon_damage": 1,
             "has_queued_attack": true, "queued_origin": [6, 4],
             "queued_target": [5, 4], "queued_target_raw": [5, 4],
             "queued_target_normalized": true},
            {"uid": 207, "type": "Firefly2", "x": 4, "y": 2,
             "hp": 6, "max_hp": 5, "team": 6, "mech": false,
             "pushable": true, "move": 2, "active": false,
             "weapons": ["FireflyAtk2"], "weapon_damage": 3,
             "has_queued_attack": true, "queued_origin": [4, 2],
             "queued_target": [3, 2], "queued_target_raw": [3, 2],
             "queued_target_normalized": true},
            {"uid": 252, "type": "TotemB", "x": 5, "y": 3,
             "hp": 2, "max_hp": 2, "team": 6, "mech": false,
             "minor": true, "pushable": true, "move": 0, "active": false,
             "weapons": ["TotemAtkB"], "weapon_damage": 2,
             "has_queued_attack": true, "queued_origin": [5, 3],
             "queued_target": [4, 3], "queued_target_raw": [4, 3],
             "queued_target_normalized": true}
          ],
          "attack_order": [206, 207, 252],
          "grid_power": 1,
          "grid_power_max": 7,
          "spawning_tiles": [[6, 2], [6, 3]],
          "environment_danger": [],
          "remaining_spawns": 1,
          "is_infinite_spawn": true,
          "turn": 1,
          "total_turns": 4,
          "victory_turns": 2
        }"#;
        let plan = r#"[
          {"mech_uid": 0, "move_to": [5, 2],
           "weapon_id": "Brute_KickBack", "target": [6, 2]},
          {"mech_uid": 2, "move_to": [7, 5],
           "weapon_id": "Science_KO_Crack", "target": [6, 5]},
          {"mech_uid": 1, "move_to": [2, 5],
           "weapon_id": "Brute_Mirrorshot", "target": [3, 5]}
        ]"#;

        let raw = replay_solution(bridge, plan).expect("replay should succeed");
        let v: Value = serde_json::from_str(&raw).unwrap();

        assert_eq!(v["predicted_outcome"]["grid_power"], 0);
        assert_eq!(v["predicted_outcome"]["buildings_destroyed_by_enemies"], 1);

        let final_units = v["final_board"]["units"].as_array().unwrap();
        for uid in [0, 1, 2] {
            let mech = final_units.iter().find(|u| u["uid"] == uid).unwrap();
            assert!(mech["hp"].as_i64().unwrap() > 0, "mech {uid} should survive");
        }
        let firefly2 = final_units.iter().find(|u| u["uid"] == 207).unwrap();
        assert!(firefly2["hp"].as_i64().unwrap() > 0,
            "smoked Firefly2 should survive without resolving its queued shot");

        let final_tiles = v["final_board"]["tiles"].as_array().unwrap();
        let firefly_tile = final_tiles.iter()
            .find(|t| t["x"] == 4 && t["y"] == 2)
            .unwrap();
        assert_eq!(firefly_tile["smoke"], true,
            "Reverse Thrusters should leave Firefly2 smoked at attack start");
        let e6_building = final_tiles.iter()
            .find(|t| t["x"] == 2 && t["y"] == 3)
            .unwrap();
        assert_eq!(e6_building["terrain"], "rubble");
    }
}
