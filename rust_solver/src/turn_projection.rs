/// Turn projection: apply a complete plan and enemy phase to produce the
/// board state at the start of the NEXT player turn (turn+1).
///
/// # Combined Option B + C (Task #11 ship)
///
/// After the enemy phase, `requeue_enemies_heuristic` populates a new
/// queued target on each alive enemy using a cheap distance heuristic
/// (closest Building within `move_speed + 4` Manhattan, fallback to
/// closest mech, skip Webbed/Frozen/Smoked). This gives the downstream
/// evaluator real per-tile threats on the projected board so
/// `threats_cleared`, `building_coverage`, `perfect_defense_bonus`, and
/// body-block scoring all work on turn+1. Empirically the heuristic
/// agrees with real game AI on ~1-in-3 enemies — not perfect, but
/// strictly better than the no-queue baseline which scored 0%.
///
/// `board_to_json` additionally injects `eval_weights.pseudo_threat_eval =
/// true` so that any enemies the heuristic COULDN'T place a target on
/// (isolated enemies with no building/mech in reach) still contribute a
/// conservative penalty via the Option-C augmentation in `evaluate.rs`.
/// The two options are complementary: B handles the common "enemy has an
/// obvious target" case with a specific tile; C picks up the leftover
/// "enemy with no obvious target" case with a scalar penalty.

use crate::board::{Board, ActionResult, UnitFlags};
use crate::enemy::{simulate_enemy_attacks, apply_spawn_blocking};
use crate::simulate::simulate_action;
use crate::solver::MechAction;
use crate::types::{Terrain, idx_to_xy};
use crate::weapons::WeaponTable;

/// Assign a new queued target to each alive enemy based on closest reachable
/// threat. Pure function over the board; does not consume any simulation
/// state. Caller is responsible for clearing stale `queued_target_x/_y`
/// values first (this function overwrites them for enemies that find a
/// target; leaves them at -1 otherwise).
///
/// Priority:
///   1. Closest alive Building (Manhattan ≤ `move_speed + 4`)
///   2. Closest alive player mech (Manhattan ≤ `move_speed + 4`)
///   3. No target (leave at -1)
///
/// Skipped enemies:
///   - Webbed, Frozen — can't attack next turn
///   - Standing on Smoke — smoke cancels attacks
///
/// Ties broken by lowest tile index for determinism.
pub fn requeue_enemies_heuristic(board: &mut Board) {
    let n = board.unit_count as usize;
    for ei in 0..n {
        let (ex, ey, reach, alive, is_enemy, frozen, webbed) = {
            let e = &board.units[ei];
            (e.x, e.y,
             e.move_speed as i32 + 4,
             e.alive(), e.is_enemy(), e.frozen(), e.web())
        };
        if !alive || !is_enemy { continue; }
        if frozen || webbed { continue; }
        if board.tile(ex, ey).smoke() { continue; }

        // Pass 1: closest alive Building within reach.
        let mut best_bld: Option<(i32, usize)> = None; // (dist, flat_idx)
        for idx in 0..64usize {
            let tile = &board.tiles[idx];
            if tile.terrain != Terrain::Building || tile.building_hp == 0 {
                continue;
            }
            let (bx, by) = idx_to_xy(idx);
            let dist = (ex as i32 - bx as i32).abs() + (ey as i32 - by as i32).abs();
            if dist == 0 || dist > reach { continue; }
            match best_bld {
                None => best_bld = Some((dist, idx)),
                Some((d, _)) if dist < d => best_bld = Some((dist, idx)),
                _ => {}
            }
        }
        if let Some((_, idx)) = best_bld {
            let (bx, by) = idx_to_xy(idx);
            let e = &mut board.units[ei];
            e.queued_target_x = bx as i8;
            e.queued_target_y = by as i8;
            e.flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
            continue;
        }

        // Pass 2: closest alive player mech within reach.
        let mut best_mech: Option<(i32, usize)> = None; // (dist, mech_unit_idx)
        for mi in 0..n {
            let m = &board.units[mi];
            if !m.is_player() || !m.is_mech() || !m.alive() { continue; }
            let dist = (ex as i32 - m.x as i32).abs() + (ey as i32 - m.y as i32).abs();
            if dist == 0 || dist > reach { continue; }
            match best_mech {
                None => best_mech = Some((dist, mi)),
                Some((d, _)) if dist < d => best_mech = Some((dist, mi)),
                _ => {}
            }
        }
        if let Some((_, mi)) = best_mech {
            let (mx, my) = (board.units[mi].x, board.units[mi].y);
            let e = &mut board.units[ei];
            e.queued_target_x = mx as i8;
            e.queued_target_y = my as i8;
            e.flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        }
        // else: no target in reach — leave at -1. Option C's
        // pseudo_threat_eval will pick up the slack if the board still
        // has a building the enemy could harass via extended movement.
    }
}

pub fn project_plan(
    board: &Board,
    actions: &[MechAction],
    spawn_points: &[(u8, u8)],
    weapons: &WeaponTable,
) -> (Board, ActionResult) {
    let mut b = board.clone();
    let mut original_positions = [(0u8, 0u8); 16];
    for i in 0..b.unit_count as usize {
        original_positions[i] = (b.units[i].x, b.units[i].y);
    }
    let mut aggregate = ActionResult::default();
    for action in actions {
        let mech_idx = match b.units[..b.unit_count as usize]
            .iter()
            .position(|u| u.uid == action.mech_uid && u.alive())
        {
            Some(i) => i,
            None => continue,
        };
        let result = simulate_action(&mut b, mech_idx, action.move_to, action.weapon, action.target, weapons);
        aggregate.merge(&result);
    }
    let _ = simulate_enemy_attacks(&mut b, &original_positions, weapons);
    if !spawn_points.is_empty() {
        apply_spawn_blocking(&mut b, spawn_points);
    }
    // Clear fired queued attacks — subsequent re-queue populates new ones.
    for i in 0..b.unit_count as usize {
        let u = &mut b.units[i];
        if u.is_enemy() && u.hp > 0 {
            u.queued_target_x = -1;
            u.queued_target_y = -1;
            u.flags.set(UnitFlags::HAS_QUEUED_ATTACK, false);
        }
    }
    // Option B: heuristic re-queue for surviving enemies.
    requeue_enemies_heuristic(&mut b);
    // Reset player mechs for the next turn.
    for i in 0..b.unit_count as usize {
        let u = &mut b.units[i];
        if u.is_player() && u.hp > 0 {
            u.set_active(true);
            u.flags.insert(UnitFlags::CAN_MOVE);
        }
    }
    b.current_turn = b.current_turn.saturating_add(1);
    (b, aggregate)
}

pub fn board_to_json(board: &Board, spawn_points: &[(u8, u8)]) -> String {
    use serde_json::{json, Value};
    use crate::weapons::{wid_to_str, WId};
    let mut tiles: Vec<Value> = Vec::with_capacity(64);
    for idx in 0..64usize {
        let tile = &board.tiles[idx];
        let is_default = tile.terrain == Terrain::Ground
            && tile.building_hp == 0 && tile.population == 0
            && tile.flags.bits() == 0 && tile.conveyor_dir == -1;
        if is_default { continue; }
        let (x, y) = idx_to_xy(idx);
        let terrain_str = match tile.terrain {
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
        };
        let mut t = json!({ "x": x, "y": y, "terrain": terrain_str });
        if tile.terrain == Terrain::Building {
            t["building_hp"] = json!(tile.building_hp);
        } else if tile.building_hp > 0 {
            t["building_hp"] = json!(tile.building_hp);
        }
        if tile.population > 0    { t["population"]        = json!(tile.population); }
        if tile.on_fire()         { t["fire"]              = json!(true); }
        if tile.smoke()           { t["smoke"]             = json!(true); }
        if tile.acid()            { t["acid"]              = json!(true); }
        if tile.frozen()          { t["frozen"]            = json!(true); }
        if tile.cracked()         { t["cracked"]           = json!(true); }
        if tile.has_pod()         { t["has_pod"]           = json!(true); }
        if tile.freeze_mine()     { t["freeze_mine"]       = json!(true); }
        if tile.old_earth_mine()  { t["old_earth_mine"]    = json!(true); }
        if tile.repair_platform() {
            t["repair_platform"] = json!(true);
            t["item"] = json!("Item_Repair_Mine");
        }
        if tile.conveyor_dir >= 0 { t["conveyor"]          = json!(tile.conveyor_dir); }
        if (board.unique_buildings >> idx) & 1 != 0 {
            t["unique_building"] = json!(true);
            if (board.grid_reward_buildings >> idx) & 1 != 0 {
                t["objective_name"] = json!("Str_Power");
            }
        }
        tiles.push(t);
    }
    let mut units: Vec<Value> = Vec::with_capacity(board.unit_count as usize);
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.hp <= 0 { continue; }
        let team_int: u8 = match u.team {
            crate::types::Team::Player  => 1,
            crate::types::Team::Neutral => 2,
            crate::types::Team::Enemy   => 6,
        };
        let mut weapons_list: Vec<String> = Vec::new();
        if u.weapon.0 != 0 && u.weapon.0 != 0xFFFF {
            let wid: WId = unsafe { std::mem::transmute(u.weapon.0 as u8) };
            weapons_list.push(wid_to_str(wid).to_string());
        }
        if u.weapon2.0 != 0 && u.weapon2.0 != 0xFFFF {
            let wid: WId = unsafe { std::mem::transmute(u.weapon2.0 as u8) };
            weapons_list.push(wid_to_str(wid).to_string());
        }
        let qt: Value = if u.queued_target_x >= 0 {
            json!([u.queued_target_x, u.queued_target_y])
        } else {
            json!([-1i8, -1i8])
        };
        let mut unit_val = json!({
            "uid":        u.uid,
            "type":       u.type_name_str(),
            "x":          u.x,
            "y":          u.y,
            "hp":         u.hp,
            "max_hp":     u.max_hp,
            "team":       team_int,
            "mech":       u.is_mech(),
            "move":       u.move_speed,
            "base_move":  u.base_move,
            "active":     u.active(),
            "can_move":   u.can_move(),
            "pushable":   u.pushable(),
            "queued_target": qt,
        });
        if !weapons_list.is_empty()       { unit_val["weapons"]              = json!(weapons_list); }
        if u.flying()                     { unit_val["flying"]               = json!(true); }
        if u.massive()                    { unit_val["massive"]              = json!(true); }
        if u.armor()                      { unit_val["armor"]                = json!(true); }
        if u.shield()                     { unit_val["shield"]               = json!(true); }
        if u.acid()                       { unit_val["acid"]                 = json!(true); }
        if u.frozen()                     { unit_val["frozen"]               = json!(true); }
        if u.fire()                       { unit_val["fire"]                 = json!(true); }
        if u.web()                        { unit_val["web"]                  = json!(true); }
        if u.ranged()                     { unit_val["ranged"]               = json!(1u8); }
        if u.has_queued_attack()          { unit_val["has_queued_attack"]    = json!(true); }
        if u.is_extra_tile()              { unit_val["is_extra_tile"]        = json!(true); }
        if u.web_source_uid != 0          { unit_val["web_source_uid"]       = json!(u.web_source_uid); }
        if u.weapon_damage > 0            { unit_val["weapon_damage"]        = json!(u.weapon_damage); }
        if u.weapon_push > 0              { unit_val["weapon_push"]          = json!(u.weapon_push); }
        if u.weapon_target_behind         { unit_val["weapon_target_behind"] = json!(true); }
        if u.pilot_value != 0.0           { unit_val["pilot_value"]          = json!(u.pilot_value as f64); }
        units.push(unit_val);
    }
    let spawning_tiles: Vec<Vec<u8>> = spawn_points.iter().map(|&(x, y)| vec![x, y]).collect();
    let mut env_danger_v2: Vec<Vec<u8>> = Vec::new();
    for idx in 0..64usize {
        let bit = 1u64 << idx;
        if board.env_danger & bit != 0 {
            let (x, y) = idx_to_xy(idx);
            let kill_int: u8 = if board.env_danger_kill & bit != 0 { 1 } else { 0 };
            // 5th field: flying_immune (sim v19+). 1 = Tidal/Cataclysm/Seismic
            // (effectively-flying spared); 0 = Air Strike / Lightning / non-
            // lethal hazard. Always 0 unless the lethal bit is set.
            let flying_immune: u8 = if kill_int != 0
                && (board.env_danger_flying_immune & bit != 0) { 1 } else { 0 };
            env_danger_v2.push(vec![x, y, 1, kill_int, flying_immune]);
        }
    }
    // Option C: enable pseudo_threat_eval on the projected board so the
    // evaluator's queueless-threat augmentation fires as a fallback for
    // enemies the heuristic couldn't place a target on. EvalWeights has
    // struct-level #[serde(default)], so this sparse object falls through
    // to Rust defaults for every other field.
    let out = json!({
        "tiles":                 tiles,
        "units":                 units,
        "grid_power":            board.grid_power,
        "grid_power_max":        board.grid_power_max,
        "turn":                  board.current_turn,
        "total_turns":           board.total_turns,
        "remaining_spawns":      board.remaining_spawns,
        "spawning_tiles":        spawning_tiles,
        "environment_danger_v2": env_danger_v2,
        "mission_id":            board.mission_id,
        "mission_kill_target":   board.mission_kill_target,
        "mission_kills_done":    board.mission_kills_done,
        "repair_platform_target": board.repair_platform_target,
        "repair_platforms_used":  board.repair_platforms_used,
        "bonus_objective_unit_types":   board.bonus_dont_kill_types,
        "destroy_objective_unit_types": board.destroy_objective_unit_types,
        "protect_objective_unit_types": board.protect_objective_unit_types,
        "eval_weights":          json!({ "pseudo_threat_eval": true }),
    });
    serde_json::to_string(&out).unwrap_or_else(|_| "{}".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::board::{Board, Unit, UnitFlags};
    use crate::serde_bridge::board_from_json;
    use crate::types::{Team, Terrain, xy_to_idx};
    use crate::weapons::WEAPONS;

    fn simple_board() -> (Board, Vec<(u8, u8)>) {
        let mut b = Board::default();
        b.total_turns = 5; b.current_turn = 1; b.remaining_spawns = 2;
        // Player mech
        let mut mech = Unit::default();
        mech.uid = 0; mech.set_type_name("PunchMech");
        mech.x = 1; mech.y = 1; mech.hp = 3; mech.max_hp = 3;
        mech.team = Team::Player;
        mech.flags = UnitFlags::IS_MECH | UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        mech.move_speed = 3; mech.base_move = 3;
        b.add_unit(mech);
        // Enemy with a queued attack pointing at a building. Place it far
        // from the mech so the building (4,3) is clearly the closer
        // target after the heuristic runs post-enemy-phase.
        let mut enemy = Unit::default();
        enemy.uid = 10; enemy.set_type_name("Hornet");
        enemy.x = 4; enemy.y = 4; enemy.hp = 1; enemy.max_hp = 1;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE | UnitFlags::HAS_QUEUED_ATTACK;
        enemy.move_speed = 2; enemy.base_move = 2;
        enemy.queued_target_x = 4; enemy.queued_target_y = 3;
        b.add_unit(enemy);
        // Building tile that enemy targets (and that will survive because
        // the Hornet is 1-dmg melee against a 1-HP building — enemy is
        // also 1 HP, it kills the building, enemy still alive).
        let idx = xy_to_idx(4, 3);
        b.tiles[idx].terrain = Terrain::Building;
        b.tiles[idx].building_hp = 1;
        (b, vec![])
    }

    #[test]
    fn test_project_plan_deterministic() {
        let (board, spawn_points) = simple_board();
        let (b1, _) = project_plan(&board, &[], &spawn_points, &WEAPONS);
        let (b2, _) = project_plan(&board, &[], &spawn_points, &WEAPONS);
        assert_eq!(b1.current_turn, b2.current_turn);
        assert_eq!(b1.grid_power, b2.grid_power);
        for i in 0..b1.unit_count as usize {
            assert_eq!(b1.units[i].hp, b2.units[i].hp);
            assert_eq!(b1.units[i].queued_target_x, b2.units[i].queued_target_x);
            assert_eq!(b1.units[i].queued_target_y, b2.units[i].queued_target_y);
        }
    }

    #[test]
    fn test_mechs_active_after_projection() {
        let (board, spawn_points) = simple_board();
        let (projected, _) = project_plan(&board, &[], &spawn_points, &WEAPONS);
        for i in 0..projected.unit_count as usize {
            let u = &projected.units[i];
            if u.is_player() && u.is_mech() && u.alive() {
                assert!(u.active(),   "mech uid={} must be active", u.uid);
                assert!(u.can_move(), "mech uid={} must have CAN_MOVE", u.uid);
            }
        }
    }

    #[test]
    fn test_turn_incremented() {
        let (board, spawn_points) = simple_board();
        let initial = board.current_turn;
        let (projected, _) = project_plan(&board, &[], &spawn_points, &WEAPONS);
        assert_eq!(projected.current_turn, initial + 1);
    }

    #[test]
    fn test_heuristic_picks_closest_building() {
        // Surviving enemy at (4,4). Two buildings: (4,3) dist=1 and
        // (0,0) dist=8 (out of reach 2+4=6). Heuristic should pick (4,3).
        let mut b = Board::default();
        b.total_turns = 5; b.current_turn = 1;
        // Keep the original building target alive — don't seed the
        // enemy with HAS_QUEUED_ATTACK so simulate_enemy_attacks won't
        // destroy the building; we're testing requeue_enemies_heuristic
        // in isolation via project_plan's post-enemy-phase pass.
        let mut enemy = Unit::default();
        enemy.uid = 10; enemy.set_type_name("Hornet");
        enemy.x = 4; enemy.y = 4; enemy.hp = 1; enemy.max_hp = 1;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        enemy.move_speed = 2; enemy.base_move = 2;
        enemy.queued_target_x = -1; enemy.queued_target_y = -1;
        b.add_unit(enemy);
        b.tiles[xy_to_idx(4, 3)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(4, 3)].building_hp = 1;
        b.tiles[xy_to_idx(0, 0)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(0, 0)].building_hp = 1;

        requeue_enemies_heuristic(&mut b);

        let e = &b.units[0];
        assert_eq!(e.queued_target_x, 4, "should target close building x");
        assert_eq!(e.queued_target_y, 3, "should target close building y");
        assert!(e.has_queued_attack(), "HAS_QUEUED_ATTACK must be set");
    }

    #[test]
    fn test_heuristic_fallback_to_mech_when_no_building() {
        // Enemy at (4,4), reach 2+4=6. Mech at (3,3) dist=2. No buildings.
        // Heuristic should pick the mech.
        let mut b = Board::default();
        b.total_turns = 5; b.current_turn = 1;
        let mut mech = Unit::default();
        mech.uid = 0; mech.set_type_name("PunchMech");
        mech.x = 3; mech.y = 3; mech.hp = 3; mech.max_hp = 3;
        mech.team = Team::Player;
        mech.flags = UnitFlags::IS_MECH | UnitFlags::ACTIVE | UnitFlags::PUSHABLE;
        mech.move_speed = 3; mech.base_move = 3;
        b.add_unit(mech);
        let mut enemy = Unit::default();
        enemy.uid = 10; enemy.set_type_name("Hornet");
        enemy.x = 4; enemy.y = 4; enemy.hp = 1; enemy.max_hp = 1;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        enemy.move_speed = 2;
        enemy.queued_target_x = -1; enemy.queued_target_y = -1;
        b.add_unit(enemy);

        requeue_enemies_heuristic(&mut b);

        let e = &b.units[1];
        assert_eq!(e.queued_target_x, 3);
        assert_eq!(e.queued_target_y, 3);
        assert!(e.has_queued_attack());
    }

    #[test]
    fn test_heuristic_skips_frozen_webbed_smoked() {
        let mut b = Board::default();
        b.total_turns = 5; b.current_turn = 1;
        // Building right next to each enemy so that WITHOUT the skip
        // filters they'd definitely get targeted.
        b.tiles[xy_to_idx(3, 3)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(3, 3)].building_hp = 1;
        let mk_enemy = |uid: u16, x: u8, y: u8, extra_flag: UnitFlags| {
            let mut e = Unit::default();
            e.uid = uid; e.set_type_name("Hornet");
            e.x = x; e.y = y; e.hp = 1; e.max_hp = 1;
            e.team = Team::Enemy;
            e.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE | extra_flag;
            e.move_speed = 2;
            e.queued_target_x = -1; e.queued_target_y = -1;
            e
        };
        b.add_unit(mk_enemy(10, 4, 3, UnitFlags::FROZEN));
        b.add_unit(mk_enemy(11, 3, 4, UnitFlags::WEB));
        // Third enemy on a smoke tile.
        let mut smoked = mk_enemy(12, 2, 3, UnitFlags::empty());
        b.add_unit(smoked);
        b.tiles[xy_to_idx(2, 3)].set_smoke(true);
        // Re-apply frozen flag via set_frozen so filter sees it.
        b.units[0].set_frozen(true);
        b.units[1].set_web(true);

        requeue_enemies_heuristic(&mut b);

        for i in 0..b.unit_count as usize {
            let e = &b.units[i];
            assert_eq!(e.queued_target_x, -1,
                "skipped enemy uid={} must stay queue-less", e.uid);
            assert!(!e.has_queued_attack());
        }
    }

    #[test]
    fn test_project_plan_double_turn() {
        let (board, spawn_points) = simple_board();
        let initial = board.current_turn;
        let (p1, _) = project_plan(&board, &[], &spawn_points, &WEAPONS);
        let (p2, _) = project_plan(&p1, &[], &spawn_points, &WEAPONS);
        assert_eq!(p2.current_turn, initial + 2);
    }

    #[test]
    fn test_board_to_json_roundtrip() {
        let (mut board, spawn_points) = simple_board();
        board.bonus_dont_kill_types.push("Volatile_Vek".to_string());
        board.destroy_objective_unit_types.push("Hacked_Building".to_string());
        board.protect_objective_unit_types.push("Snowtank".to_string());
        let alive_before: usize = (0..board.unit_count as usize)
            .filter(|&i| board.units[i].alive()).count();
        let json_str = board_to_json(&board, &spawn_points);
        let (b2, _sp, _, weights, _, _) = board_from_json(&json_str)
            .expect("board_to_json must be parseable by board_from_json");
        let alive_after: usize = (0..b2.unit_count as usize)
            .filter(|&i| b2.units[i].alive()).count();
        assert_eq!(alive_before, alive_after, "unit count must survive round-trip");
        assert_eq!(board.grid_power, b2.grid_power);
        assert_eq!(board.current_turn, b2.current_turn);
        assert_eq!(b2.bonus_dont_kill_types, vec!["Volatile_Vek".to_string()]);
        assert_eq!(b2.destroy_objective_unit_types, vec!["Hacked_Building".to_string()]);
        assert_eq!(b2.protect_objective_unit_types, vec!["Snowtank".to_string()]);
        // Option C: round-trip must preserve the pseudo_threat_eval flag
        // that board_to_json injects.
        assert!(weights.pseudo_threat_eval,
            "projected board_to_json must set eval_weights.pseudo_threat_eval=true");
    }

    #[test]
    fn test_board_to_json_preserves_destroyed_unique_building_hp_zero() {
        let (mut board, spawn_points) = simple_board();
        let idx = xy_to_idx(4, 6);
        board.tiles[idx].terrain = Terrain::Building;
        board.tiles[idx].building_hp = 0;
        board.unique_buildings |= 1u64 << idx;
        board.grid_reward_buildings |= 1u64 << idx;

        let json_str = board_to_json(&board, &spawn_points);
        let value: serde_json::Value = serde_json::from_str(&json_str)
            .expect("board_to_json emits valid json");
        let tile = value["tiles"].as_array().unwrap().iter()
            .find(|t| t["x"] == 4 && t["y"] == 6)
            .expect("destroyed unique building tile is serialized");
        assert_eq!(tile["terrain"], "building");
        assert_eq!(tile["building_hp"], 0);
        assert_eq!(tile["unique_building"], true);

        let (roundtrip, _sp, _, _weights, _, _) = board_from_json(&json_str)
            .expect("projected final board must round-trip");
        assert_eq!(roundtrip.tiles[idx].terrain, Terrain::Building);
        assert_eq!(roundtrip.tiles[idx].building_hp, 0);
        assert_ne!(roundtrip.unique_buildings & (1u64 << idx), 0);
    }
}
