/// Turn projection: apply a complete plan and enemy phase to produce the
/// board state at the start of the NEXT player turn (turn+1).
///
/// # Combined Option B + C (Task #11 ship)
///
/// After the enemy phase, `requeue_enemies_heuristic` populates a new
/// queued target on each alive enemy using a cheap distance heuristic
/// (closest Building within a conservative attack envelope, fallback to
/// closest mech, skip Frozen/Smoked and bespoke non-direct targeters).
/// Stationary enemies remain attack-capable, so their envelope uses weapon
/// family, range, splash, and push footprint without adding movement. This
/// gives the downstream evaluator real per-tile threats on the projected board so
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

use crate::board::{
    count_unit_deaths_between,
    ActionResult,
    Board,
    Unit,
    UnitFlags,
};
use crate::enemy::{
    apply_spawn_blocking,
    persisting_spawn_points,
    simulate_enemy_attacks,
};
use crate::simulate::simulate_action_with_target2;
use crate::solver::MechAction;
use crate::types::{Terrain, Team, DIRS, idx_to_xy, xy_to_idx};
use crate::weapons::{
    enemy_weapon_for_type,
    WeaponTable,
    WId,
};

#[derive(Clone, Debug)]
pub struct ProjectedScenario {
    pub label: String,
    pub board: Board,
    pub action_result: ActionResult,
    pub spawn_points: Vec<(u8, u8)>,
}

fn projected_enemy_weapon_id(enemy: &Unit) -> WId {
    let mut wid = enemy_weapon_for_type(enemy.type_name_str());
    if matches!(enemy.type_name_str(), "BotBoss" | "BotBoss2")
        && enemy.weapon2.0 == WId::BossHeal as u16
        && enemy.hp < enemy.max_hp
    {
        return WId::BossHeal;
    }
    if wid == WId::None {
        let is_big = enemy.type_name_str().contains("Boss")
            || enemy.type_name_str().contains("Leader");
        wid = if enemy.ranged() {
            if is_big { WId::FireflyAtk2 } else { WId::FireflyAtk1 }
        } else if is_big {
            WId::HornetAtk2
        } else {
            WId::HornetAtk1
        };
    }
    wid
}

fn projected_enemy_uses_special_targeting(enemy: &Unit) -> bool {
    let name = enemy.type_name_str();
    if name.contains("Egg")
        || name.starts_with("Jelly_")
        || name.starts_with("Shaman")
        || name.starts_with("Snowmine")
    {
        return true;
    }
    matches!(
        projected_enemy_weapon_id(enemy),
        WId::DiggerAtk1
            | WId::DiggerAtk2
            | WId::BlobberAtk1
            | WId::BlobberAtk2
            | WId::BlobberAtkB
            | WId::SpiderAtk1
            | WId::SpiderAtk2
            | WId::BlobAtk1
            | WId::BlobAtk2
            | WId::BlobAtkB
            | WId::StarfishAtk1
            | WId::StarfishAtk2
            | WId::StarfishAtkB1
            | WId::TumblebugAtk1
            | WId::TumblebugAtk2
            | WId::TumblebugAtkB
            | WId::PlasmodiaAtk1
            | WId::PlasmodiaAtk2
            | WId::ScorpionAtkB
            | WId::BossHeal
    )
}

fn projected_enemy_attack_reach(enemy: &Unit, weapons: &WeaponTable) -> i32 {
    let name = enemy.type_name_str();
    if name.starts_with("Shaman") {
        return 14;
    }
    if name.starts_with("Snowmine") {
        return 3;
    }
    let wid = projected_enemy_weapon_id(enemy);
    let weapon = &weapons[wid as usize];
    if matches!(wid, WId::StarfishAtk1 | WId::StarfishAtk2 | WId::StarfishAtkB1) {
        return 2;
    }
    if matches!(wid, WId::MothAtk1 | WId::MothAtk2) {
        return i32::from(weapon.range_max);
    }
    if matches!(
        wid,
        WId::TumblebugAtk1 | WId::TumblebugAtk2 | WId::TumblebugAtkB
    ) {
        return if wid == WId::TumblebugAtkB { 3 } else { 2 };
    }

    // Enemy artillery often inherits DEF.range_max=1 while setting
    // range_min=2; that inverted pair means board-wide targeting, not range
    // one. Dispatch by weapon family before trusting the raw maximum. A
    // cardinal line spans at most seven tiles, while unconstrained artillery
    // and global/two-click attacks may span the board's 14-tile Manhattan
    // diameter. Add a conservative footprint extension for line/AOE weapons
    // that can hit beyond their clicked tile.
    let direct_reach = match weapon.weapon_type {
        crate::types::WeaponType::Melee => {
            i32::from(weapon.range_max.max(1).max(weapon.path_size))
        }
        crate::types::WeaponType::Projectile
        | crate::types::WeaponType::Laser
        | crate::types::WeaponType::Charge
        | crate::types::WeaponType::Pull => {
            if weapon.range_max > 0 {
                i32::from(weapon.range_max)
            } else {
                7
            }
        }
        crate::types::WeaponType::SelfAoe => 1,
        crate::types::WeaponType::Artillery => 14,
        _ => 14,
    };
    let area_extension = if weapon.aoe_adjacent()
        || weapon.aoe_behind()
        || weapon.aoe_perpendicular()
        || enemy.weapon_target_behind
    {
        1
    } else {
        0
    };
    let bump_extension = if weapon.push != crate::types::PushDir::None {
        1
    } else {
        0
    };
    (direct_reach + area_extension + bump_extension).min(14)
}

pub(crate) fn projected_enemy_reach(
    enemy: &Unit,
    weapons: &WeaponTable,
) -> i32 {
    if enemy.web() || enemy.move_speed == 0 {
        projected_enemy_attack_reach(enemy, weapons)
    } else {
        enemy.move_speed as i32 + 4
    }
}

pub(crate) fn projected_enemy_has_attack_pressure(enemy: &Unit) -> bool {
    let name = enemy.type_name_str();
    if name.starts_with("Jelly_") {
        return false;
    }
    if name.starts_with("Snowmine") && enemy.web() {
        return false;
    }
    true
}

pub(crate) fn projected_enemy_smoke_cancels(enemy: &Unit) -> bool {
    !enemy.type_name_str().starts_with("Snowmine")
}

fn projected_starfish_target_score(board: &Board, enemy: &Unit) -> i32 {
    let mut score = 0;
    for (dx, dy) in [(1i8, 1i8), (1, -1), (-1, 1), (-1, -1)] {
        let x = enemy.x as i8 + dx;
        let y = enemy.y as i8 + dy;
        if !(0..8).contains(&x) || !(0..8).contains(&y) {
            continue;
        }
        let (x, y) = (x as u8, y as u8);
        if let Some(unit_idx) = board.unit_at(x, y) {
            let target = &board.units[unit_idx];
            if target.is_enemy() {
                // Skill:ScoreList penalizes queued friendly damage, except
                // that thawing a currently untargeted frozen ally is scored
                // like an enemy hit.
                score += if target.frozen() { 5 } else { -2 };
            } else {
                score += 5;
            }
        } else {
            let tile = board.tile(x, y);
            if tile.terrain == Terrain::Building && tile.building_hp > 0 {
                score += 5;
            }
        }
    }
    score
}

fn projected_tumblebug_damage_score(board: &Board, x: u8, y: u8) -> i32 {
    if let Some(unit_idx) = board.unit_at(x, y) {
        let target = &board.units[unit_idx];
        if target.is_enemy() {
            return if target.frozen() { 5 } else { -2 };
        }
        if target.is_player() {
            return 5;
        }
        return 0;
    }
    let tile = board.tile(x, y);
    if tile.terrain == Terrain::Building && tile.building_hp > 0 {
        5
    } else {
        0
    }
}

fn projected_tumblebug_target_legal(board: &Board, x: u8, y: u8) -> bool {
    !board.tile(x, y).has_pod() && board.tile(x, y).terrain != Terrain::Chasm
}

fn projected_tumblebug_can_spawn_rock(board: &Board, x: u8, y: u8) -> bool {
    if board.unit_at(x, y).is_some() || board.tile(x, y).has_pod() {
        return false;
    }
    if let Some(unit_idx) = board.any_unit_at(x, y) {
        // Disabled player mechs remain solid wrecks, but an exploded
        // BombRock is removed by the engine even though the simulator keeps
        // its hp<=0 record for outcome accounting and deterministic indices.
        if board.units[unit_idx].type_name_str() != "BombRock" {
            return false;
        }
    }
    !matches!(
        board.tile(x, y).terrain,
        Terrain::Building
            | Terrain::Mountain
            | Terrain::Water
            | Terrain::Chasm
            | Terrain::Lava
    )
}

fn projected_tumblebug_target_score(
    board: &Board,
    origin: (u8, u8),
    first_rock: (u8, u8),
    dir: (i8, i8),
    rock_count: usize,
) -> i32 {
    let mut damage_score = 0;
    let mut bonus_for_rock = 0;
    let mut rock = (first_rock.0 as i8, first_rock.1 as i8);
    for rock_index in 0..rock_count {
        if !(0..8).contains(&rock.0) || !(0..8).contains(&rock.1) {
            break;
        }
        let (rx, ry) = (rock.0 as u8, rock.1 as u8);
        if projected_tumblebug_can_spawn_rock(board, rx, ry) {
            // Native GetDeployLocScore remains opaque. A legal BombRock
            // placement approximates Lua's `deploy_score > 0` gate here. The
            // +10 deployment bonus is returned only when the exact visible
            // ScoreList footprint has a positive score, as in live Lua.
            bonus_for_rock += 10;
            damage_score += projected_tumblebug_damage_score(board, rx, ry);
            for &(dx, dy) in &DIRS {
                let nx = rock.0 + dx;
                let ny = rock.1 + dy;
                if !(0..8).contains(&nx) || !(0..8).contains(&ny) {
                    continue;
                }
                let pos = (nx as u8, ny as u8);
                if pos != origin && pos != first_rock {
                    damage_score += projected_tumblebug_damage_score(board, pos.0, pos.1);
                }
            }
        } else if rock_index == 0 {
            damage_score += projected_tumblebug_damage_score(board, rx, ry);
            break;
        }
        rock.0 += dir.0;
        rock.1 += dir.1;
    }
    if damage_score > 0 {
        damage_score + bonus_for_rock
    } else {
        0
    }
}

fn spawn_projected_bombrock(board: &mut Board, x: u8, y: u8) -> bool {
    if board.unit_count as usize >= board.units.len()
        || !projected_tumblebug_can_spawn_rock(board, x, y)
    {
        return false;
    }
    let mut uid = 1u16;
    for i in 0..board.unit_count as usize {
        uid = uid.max(board.units[i].uid.saturating_add(1));
    }
    let on_fire = board.tile(x, y).on_fire() || board.tile(x, y).terrain == Terrain::Fire;
    let mut rock = Unit {
        uid,
        x,
        y,
        hp: 1,
        max_hp: 1,
        team: Team::Neutral,
        flags: UnitFlags::PUSHABLE,
        ..Unit::default()
    };
    rock.set_type_name("BombRock");
    rock.set_fire(on_fire);
    board.add_unit(rock);
    true
}

fn requeue_tumblebug_heuristic(board: &mut Board, enemy_idx: usize, wid: WId) {
    let (ex, ey) = (board.units[enemy_idx].x, board.units[enemy_idx].y);
    let rock_count = if wid == WId::TumblebugAtkB { 2 } else { 1 };
    let mut best: Option<(i32, usize, u8, u8)> = None;
    for (dir_index, &(dx, dy)) in DIRS.iter().enumerate() {
        let tx = ex as i8 + dx;
        let ty = ey as i8 + dy;
        if !(0..8).contains(&tx) || !(0..8).contains(&ty) {
            continue;
        }
        let (tx, ty) = (tx as u8, ty as u8);
        if !projected_tumblebug_target_legal(board, tx, ty) {
            continue;
        }
        let score = projected_tumblebug_target_score(
            board,
            (ex, ey),
            (tx, ty),
            (dx, dy),
            rock_count,
        );
        if best.is_none_or(|(best_score, best_dir, _, _)| {
            score > best_score || (score == best_score && dir_index < best_dir)
        }) {
            best = Some((score, dir_index, tx, ty));
        }
    }

    let Some((score, dir_index, tx, ty)) = best else {
        return;
    };
    if score <= 0 {
        return;
    }

    let first_spawned = spawn_projected_bombrock(board, tx, ty);
    if wid == WId::TumblebugAtkB && first_spawned {
        let (dx, dy) = DIRS[dir_index];
        let second_x = tx as i8 + dx;
        let second_y = ty as i8 + dy;
        if (0..8).contains(&second_x) && (0..8).contains(&second_y) {
            spawn_projected_bombrock(board, second_x as u8, second_y as u8);
        }
    }

    let enemy = &mut board.units[enemy_idx];
    enemy.queued_target_x = tx as i8;
    enemy.queued_target_y = ty as i8;
    enemy.flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
}

/// Assign a new queued target to each alive enemy based on closest reachable
/// threat. Pure function over the board; does not consume any simulation
/// state. Caller is responsible for clearing stale `queued_target_x/_y`
/// values first (this function overwrites them for enemies that find a
/// target; leaves them at -1 otherwise).
///
/// Priority:
///   1. Closest alive Building within the projected reach envelope
///   2. Closest alive player mech within the projected reach envelope
///   3. No target (leave at -1)
///
/// Skipped enemies:
///   - Frozen — can't attack next turn
///   - Standing on Smoke — smoke cancels ordinary attacks
///   - Bespoke self/spawn/setup targeters — a building tile would be illegal
///     or ineffective; Option C retains conservative queueless pressure
///
/// Webbed and naturally immobile enemies use a weapon-aware attack footprint
/// without movement. Mobile enemies retain the bounded `move_speed + 4`
/// heuristic and are surfaced as incomplete by the Python forecast audit.
/// Mission Snowmines are explicit exceptions: Smoke does not cancel their
/// setup attack, while Web does.
///
/// Ties broken by lowest tile index for determinism.
pub fn requeue_enemies_heuristic(board: &mut Board, weapons: &WeaponTable) {
    let n = board.unit_count as usize;
    for ei in 0..n {
        let (ex, ey, reach, alive, is_enemy, frozen) = {
            let e = &board.units[ei];
            (
                e.x,
                e.y,
                projected_enemy_reach(e, weapons),
                e.alive(),
                e.is_enemy(),
                e.frozen(),
            )
        };
        if !alive || !is_enemy { continue; }
        if !projected_enemy_has_attack_pressure(&board.units[ei]) { continue; }
        if frozen { continue; }
        if board.tile(ex, ey).smoke()
            && projected_enemy_smoke_cancels(&board.units[ei])
        {
            continue;
        }
        let enemy_wid = projected_enemy_weapon_id(&board.units[ei]);
        if matches!(
            enemy_wid,
            WId::StarfishAtk1 | WId::StarfishAtk2 | WId::StarfishAtkB1
        ) {
            // Lua exposes only the Starfish's own tile and scores the four
            // queued diagonal damage cells. Preserve that exact target shape
            // whenever the known footprint has a positive native-style score.
            if projected_starfish_target_score(board, &board.units[ei]) > 0 {
                let e = &mut board.units[ei];
                e.queued_target_x = ex as i8;
                e.queued_target_y = ey as i8;
                e.flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
            }
            continue;
        }
        if matches!(
            enemy_wid,
            WId::TumblebugAtk1 | WId::TumblebugAtk2 | WId::TumblebugAtkB
        ) {
            // Tumblebug planning immediately materializes one BombRock (two
            // for the Leader when both tiles are legal), then queues the hit
            // on the first selected adjacent tile. Native movement and
            // GetDeployLocScore remain heuristic, but the resulting board
            // now carries the real spawned blockers and next-turn explosion.
            requeue_tumblebug_heuristic(board, ei, enemy_wid);
            continue;
        }
        if projected_enemy_uses_special_targeting(&board.units[ei]) { continue; }

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

fn apply_plan_and_enemy_phase(
    board: &Board,
    actions: &[MechAction],
    spawn_points: &[(u8, u8)],
    weapons: &WeaponTable,
) -> (Board, ActionResult, Vec<(u8, u8)>) {
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
        let before_action = b.clone();
        let result = simulate_action_with_target2(
            &mut b,
            mech_idx,
            action.move_to,
            action.weapon,
            action.target,
            action.target2,
            weapons,
        );
        let mut result = result;
        result.unit_deaths = count_unit_deaths_between(&before_action, &b);
        aggregate.merge(&result);
    }
    let before_enemy_phase = b.clone();
    let enemy_phase_result = simulate_enemy_attacks(&mut b, &original_positions, weapons);
    let mut enemy_phase_result = enemy_phase_result;
    enemy_phase_result.unit_deaths = count_unit_deaths_between(&before_enemy_phase, &b);
    aggregate.merge(&enemy_phase_result);
    // A marker persists only when a living pawn occupies it at emergence.
    // Capture occupancy before the bump-class blocking damage: a blocker that
    // dies or thaws from that damage still prevented this Vek from emerging,
    // so the marker remains for the next turn. Unoccupied markers are consumed
    // by emergence even though the unknown Vek itself is not materialized by
    // this bounded projection.
    let blocked_spawn_points = persisting_spawn_points(&b, spawn_points);
    if !spawn_points.is_empty() {
        let before_spawn_block = b.clone();
        let spawn_result = apply_spawn_blocking(&mut b, spawn_points);
        let mut spawn_result = spawn_result;
        spawn_result.unit_deaths = count_unit_deaths_between(&before_spawn_block, &b);
        aggregate.merge(&spawn_result);
    }
    b.add_mission_kills(aggregate.mission_kills);
    // Clear fired queued attacks — subsequent scenario re-queues populate new ones.
    for i in 0..b.unit_count as usize {
        let u = &mut b.units[i];
        if u.is_enemy() && u.hp > 0 {
            u.queued_target_x = -1;
            u.queued_target_y = -1;
            u.flags.set(UnitFlags::HAS_QUEUED_ATTACK, false);
        }
    }
    // Reset player mechs for the next turn.
    for i in 0..b.unit_count as usize {
        let u = &mut b.units[i];
        if u.is_player() && u.hp > 0 {
            u.set_active(true);
            u.flags.insert(UnitFlags::CAN_MOVE);
        }
    }
    b.current_turn = b.current_turn.saturating_add(1);
    advance_mission_tides_warning(&mut b);
    (b, aggregate, blocked_spawn_points)
}

pub(crate) fn advance_mission_tides_warning(board: &mut Board) {
    if board.mission_id == "Mission_Terratide" {
        if board.env_smoke == 0 {
            return;
        }

        // Env_Terratide inherits Env_Tides::Plan(), which increments Index,
        // but its sand branch maps the warned lane to y = 7 - Index. Thus its
        // next warning moves toward y=0, opposite Mission_Tides. Rebuild every
        // represented next row so columns omitted by a building in the old
        // lane can reappear; MarkBoard omits only buildings in the new lane.
        let mut warned = board.env_smoke;
        let mut next_rows = 0u16;
        while warned != 0 {
            let tile_idx = warned.trailing_zeros() as usize;
            warned &= warned - 1;
            let (_, y) = idx_to_xy(tile_idx);
            if y > 0 {
                next_rows |= 1u16 << (y - 1);
            }
        }

        let mut next_smoke = 0u64;
        for y in 0u8..8 {
            if next_rows & (1u16 << y) == 0 {
                continue;
            }
            for x in 0u8..8 {
                if !board.tile(x, y).is_building() {
                    next_smoke |= 1u64 << xy_to_idx(x, y);
                }
            }
        }
        board.env_smoke = next_smoke;
        return;
    }

    if board.mission_id != "Mission_Tides" {
        return;
    }

    // Env_Tides::Plan increments Index, and MarkBoard reconstructs only that
    // new y=Index lane. It does not shift the old marker bits column by
    // column: a column is omitted when any live building exists at or below
    // the new lane, or when the new tile is already Water. Rebuild every
    // represented row from board state so previously omitted columns can
    // reappear when appropriate while Lua's building shadow stays intact.
    let mut next_rows = 0u16;
    if let Some(index) = board.env_tides_index {
        // The live scalar is authoritative even if every visible marker was
        // omitted by building shadow / existing Water. Preserve 8 as the
        // terminal off-board Index without constructing an invalid row.
        let next_index = index.saturating_add(1).min(8);
        board.env_tides_index = Some(next_index);
        if next_index < 8 {
            next_rows |= 1u16 << next_index;
        }
    } else {
        // Legacy recordings do not carry Index. Keep the marker-derived
        // direction fallback exactly as before.
        let mut warned = board.env_danger;
        while warned != 0 {
            let tile_idx = warned.trailing_zeros() as usize;
            warned &= warned - 1;
            let (_, y) = idx_to_xy(tile_idx);
            if y < 7 {
                next_rows |= 1u16 << (y + 1);
            }
        }
    }

    let mut next_danger = 0u64;
    for y in 0u8..8 {
        if next_rows & (1u16 << y) == 0 {
            continue;
        }
        for x in 0u8..8 {
            let building_shadow =
                (0u8..=y).any(|scan_y| board.tile(x, scan_y).is_building());
            let convert = board.tile(x, y).terrain != Terrain::Water;
            if !building_shadow && convert {
                next_danger |= 1u64 << xy_to_idx(x, y);
            }
        }
    }
    board.env_danger = next_danger;
    board.env_danger_kill = next_danger;
    board.env_danger_flying_immune = next_danger;
}

pub fn project_plan(
    board: &Board,
    actions: &[MechAction],
    spawn_points: &[(u8, u8)],
    weapons: &WeaponTable,
) -> (Board, ActionResult) {
    let (b, aggregate, _) = project_plan_with_spawns(
        board, actions, spawn_points, weapons,
    );
    (b, aggregate)
}

/// Project one turn and return the spawn markers that genuinely persist.
///
/// Existing callers that only need board/action parity can use
/// [`project_plan`]. Depth-2 callers must use this form so an unblocked marker
/// consumed by emergence is not offered as a phantom block on the next turn.
pub fn project_plan_with_spawns(
    board: &Board,
    actions: &[MechAction],
    spawn_points: &[(u8, u8)],
    weapons: &WeaponTable,
) -> (Board, ActionResult, Vec<(u8, u8)>) {
    let (mut b, aggregate, blocked_spawn_points) = apply_plan_and_enemy_phase(
        board, actions, spawn_points, weapons,
    );
    // Option B: heuristic re-queue for surviving enemies.
    requeue_enemies_heuristic(&mut b, weapons);
    (b, aggregate, blocked_spawn_points)
}

pub fn project_plan_scenarios(
    board: &Board,
    actions: &[MechAction],
    spawn_points: &[(u8, u8)],
    weapons: &WeaponTable,
    max_scenarios: usize,
) -> Vec<ProjectedScenario> {
    let max_scenarios = max_scenarios.max(1);
    let (base, aggregate, blocked_spawn_points) = apply_plan_and_enemy_phase(
        board, actions, spawn_points, weapons,
    );
    let mut scenarios = Vec::with_capacity(max_scenarios);

    let mut heuristic = base.clone();
    requeue_enemies_heuristic(&mut heuristic, weapons);
    let mut signatures = vec![target_signature(&heuristic)];
    scenarios.push(ProjectedScenario {
        label: "heuristic_requeue".to_string(),
        board: heuristic.clone(),
        action_result: aggregate.clone(),
        spawn_points: blocked_spawn_points.clone(),
    });

    let mut retargets = building_retarget_candidates(&base, weapons);
    retargets.sort_by(|a, b| {
        // Higher building HP first, then closer targets, then stable uid/tile.
        b.building_hp.cmp(&a.building_hp)
            .then(a.distance.cmp(&b.distance))
            .then(a.enemy_uid.cmp(&b.enemy_uid))
            .then(a.tile_idx.cmp(&b.tile_idx))
    });

    for retarget in retargets {
        if scenarios.len() >= max_scenarios {
            break;
        }
        let mut variant = heuristic.clone();
        let enemy_idx = match variant.units[..variant.unit_count as usize]
            .iter()
            .position(|u| u.uid == retarget.enemy_uid && u.alive())
        {
            Some(i) => i,
            None => continue,
        };
        let enemy = &mut variant.units[enemy_idx];
        if enemy.queued_target_x == retarget.x as i8
            && enemy.queued_target_y == retarget.y as i8
        {
            continue;
        }
        enemy.queued_target_x = retarget.x as i8;
        enemy.queued_target_y = retarget.y as i8;
        enemy.flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        let signature = target_signature(&variant);
        if signatures.iter().any(|s| *s == signature) {
            continue;
        }
        signatures.push(signature);
        scenarios.push(ProjectedScenario {
            label: format!(
                "retarget_building_uid{}_{}_{}",
                retarget.enemy_uid, retarget.x, retarget.y,
            ),
            board: variant,
            action_result: aggregate.clone(),
            spawn_points: blocked_spawn_points.clone(),
        });
    }

    scenarios
}

#[derive(Clone, Copy, Debug)]
struct RetargetCandidate {
    enemy_uid: u16,
    x: u8,
    y: u8,
    tile_idx: usize,
    distance: i32,
    building_hp: u8,
}

fn building_retarget_candidates(
    board: &Board,
    weapons: &WeaponTable,
) -> Vec<RetargetCandidate> {
    let n = board.unit_count as usize;
    let mut out = Vec::new();
    for ei in 0..n {
        let e = &board.units[ei];
        if !eligible_for_requeue(board, ei) {
            continue;
        }
        let reach = projected_enemy_reach(e, weapons);
        for idx in 0..64usize {
            let tile = &board.tiles[idx];
            if tile.terrain != Terrain::Building || tile.building_hp == 0 {
                continue;
            }
            let (bx, by) = idx_to_xy(idx);
            let dist = (e.x as i32 - bx as i32).abs()
                + (e.y as i32 - by as i32).abs();
            if dist == 0 || dist > reach {
                continue;
            }
            out.push(RetargetCandidate {
                enemy_uid: e.uid,
                x: bx,
                y: by,
                tile_idx: idx,
                distance: dist,
                building_hp: tile.building_hp,
            });
        }
    }
    out
}

fn eligible_for_requeue(board: &Board, unit_idx: usize) -> bool {
    let e = &board.units[unit_idx];
    e.alive()
        && e.is_enemy()
        && projected_enemy_has_attack_pressure(e)
        && !e.frozen()
        && (!board.tile(e.x, e.y).smoke() || !projected_enemy_smoke_cancels(e))
        && !projected_enemy_uses_special_targeting(e)
}

fn target_signature(board: &Board) -> Vec<(u16, i8, i8)> {
    let mut sig = Vec::new();
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.alive() && u.is_enemy() {
            sig.push((u.uid, u.queued_target_x, u.queued_target_y));
        }
    }
    sig.sort_unstable();
    sig
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
        if tile.shield()          { t["shield"]            = json!(true); }
        if tile.cracked()         { t["cracked"]           = json!(true); }
        if tile.has_pod()         { t["has_pod"]           = json!(true); }
        if tile.freeze_mine()     { t["freeze_mine"]       = json!(true); }
        if tile.old_earth_mine()  { t["old_earth_mine"]    = json!(true); }
        if tile.grass() {
            t["grass"] = json!(true);
            t["custom"] = json!("ground_grass.png");
        }
        if tile.repair_platform() {
            t["repair_platform"] = json!(true);
            t["item"] = json!("Item_Repair_Mine");
        }
        if let Some(engine_dir) =
            crate::serde_bridge::solver_dir_to_engine_dir(tile.conveyor_dir)
        {
            // board_from_json treats this interchange field as an engine
            // DIR_* value and normalizes it into solver coordinates.
            t["conveyor"] = json!(engine_dir);
        }
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
        // Dead player mechs remain physical wrecks while disabled (including
        // across later turns of the mission).
        // Movement and push simulation consults Board::wreck_at, so dropping
        // them from the post-player checkpoint can silently authorize an
        // enemy-phase replay rooted in different blocker topology.  Dead
        // enemies/neutral units are removed by the game and stay omitted.
        let persistent_player_wreck =
            u.hp <= 0 && u.team == crate::types::Team::Player && u.is_mech();
        if (u.hp <= 0 && !persistent_player_wreck) || u.burrowed() { continue; }
        let serialized_hp = if persistent_player_wreck { 0 } else { u.hp };
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
        let qo: Value = if u.queued_origin_x >= 0 {
            json!([u.queued_origin_x, u.queued_origin_y])
        } else {
            json!([-1i8, -1i8])
        };
        let mut unit_val = json!({
            "uid":        u.uid,
            "type":       u.type_name_str(),
            "x":          u.x,
            "y":          u.y,
            "hp":         serialized_hp,
            "max_hp":     u.max_hp,
            "team":       team_int,
            "mech":       u.is_mech(),
            "move":       u.move_speed,
            "base_move":  u.base_move,
            "active":     u.active(),
            "can_move":   u.can_move(),
            "pushable":   u.pushable(),
            "queued_target": qt,
            "queued_origin": qo,
        });
        if !weapons_list.is_empty()       { unit_val["weapons"]              = json!(weapons_list); }
        if u.flying()                     { unit_val["flying"]               = json!(true); }
        if u.massive()                    { unit_val["massive"]              = json!(true); }
        if u.minor()                      { unit_val["minor"]                = json!(true); }
        if u.armor()                      { unit_val["armor"]                = json!(true); }
        if u.shield()                     { unit_val["shield"]               = json!(true); }
        if u.acid()                       { unit_val["acid"]                 = json!(true); }
        if u.frozen()                     { unit_val["frozen"]               = json!(true); }
        if u.fire()                       { unit_val["fire"]                 = json!(true); }
        if u.infected()                   { unit_val["infected"]             = json!(true); }
        if u.web()                        { unit_val["web"]                  = json!(true); }
        if u.boosted()                    { unit_val["boosted"]              = json!(true); }
        if u.ranged()                     { unit_val["ranged"]               = json!(1u8); }
        if u.has_queued_attack()          { unit_val["has_queued_attack"]    = json!(true); }
        if u.queued_target_raw_x >= 0 && u.queued_target_raw_y >= 0 {
            unit_val["queued_target_raw"] = json!([
                u.queued_target_raw_x,
                u.queued_target_raw_y,
            ]);
        }
        if u.is_extra_tile()              { unit_val["is_extra_tile"]        = json!(true); }
        if u.web_source_uid != 0          { unit_val["web_source_uid"]       = json!(u.web_source_uid); }
        if u.weapon_damage > 0            { unit_val["weapon_damage"]        = json!(u.weapon_damage); }
        if u.weapon_push > 0              { unit_val["weapon_push"]          = json!(u.weapon_push); }
        if u.weapon_target_behind         { unit_val["weapon_target_behind"] = json!(true); }
        if u.pilot_value != 0.0           { unit_val["pilot_value"]          = json!(u.pilot_value as f64); }
        let pilot_id = if u.pilot_flags.contains(crate::board::PilotFlags::SOLDIER) {
            Some("Pilot_Soldier")
        } else if u.pilot_flags.contains(crate::board::PilotFlags::ROCK) {
            Some("Pilot_Rock")
        } else if u.pilot_flags.contains(crate::board::PilotFlags::REPAIRMAN) {
            Some("Pilot_Repairman")
        } else if u.pilot_flags.contains(crate::board::PilotFlags::CHEMICAL) {
            Some("Pilot_Chemical")
        } else if u.pilot_flags.contains(crate::board::PilotFlags::ARROGANT) {
            Some("Pilot_Arrogant")
        } else {
            None
        };
        if let Some(pilot_id) = pilot_id  { unit_val["pilot_id"]             = json!(pilot_id); }
        units.push(unit_val);
    }
    let spawning_tiles: Vec<Vec<u8>> = spawn_points.iter().map(|&(x, y)| vec![x, y]).collect();
    let mut freeze_building_tiles: Vec<Vec<u8>> = Vec::new();
    let mut freeze_bits = board.freeze_building_tiles;
    while freeze_bits != 0 {
        let bit_idx = freeze_bits.trailing_zeros() as usize;
        freeze_bits &= freeze_bits - 1;
        let (x, y) = idx_to_xy(bit_idx);
        freeze_building_tiles.push(vec![x, y]);
    }
    let mut mission_mountain_tiles: Vec<Vec<u8>> = Vec::new();
    let mut mountain_bits = board.mission_mountain_tiles;
    while mountain_bits != 0 {
        let bit_idx = mountain_bits.trailing_zeros() as usize;
        mountain_bits &= mountain_bits - 1;
        let (x, y) = idx_to_xy(bit_idx);
        mission_mountain_tiles.push(vec![x, y]);
    }
    let mut env_danger_v2: Vec<Vec<u8>> = Vec::new();
    for idx in 0..64usize {
        let bit = 1u64 << idx;
        if (board.env_danger | board.env_smoke) & bit != 0 {
            let (x, y) = idx_to_xy(idx);
            let kill_int: u8 = if board.env_smoke & bit != 0 {
                0
            } else if board.env_danger_kill & bit != 0 {
                1
            } else {
                0
            };
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
        "environment_tides_index": board.env_tides_index,
        "environment_danger_v2": env_danger_v2,
        "env_type":              if board.env_danger_acid != 0 || board.mission_id == "Mission_NanoStorm" {
            "nanostorm"
        } else if board.env_smoke != 0 || board.mission_id == "Mission_Sandstorm" {
            "sandstorm"
        } else {
            "unknown"
        },
        "mission_id":            board.mission_id,
        "mission_kill_target":   board.mission_kill_target,
        "mission_kill_limit":    board.mission_kill_limit,
        "mission_kills_done":    board.mission_kills_done,
        "mission_mountain_target": board.mission_mountain_target,
        "mission_mountains_destroyed": board.projected_mountains_destroyed(),
        "mission_mountain_tiles": mission_mountain_tiles,
        "repair_platform_target": board.repair_platform_target,
        "repair_platforms_used":  board.repair_platforms_used,
        "freeze_building_target": board.freeze_building_target,
        "freeze_building_tiles":  freeze_building_tiles,
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
    fn test_projection_consumes_unblocked_spawn_markers() {
        let mut b = Board::default();
        b.total_turns = 5;
        b.current_turn = 1;
        b.remaining_spawns = 2;
        let spawn_points = vec![(2, 2), (5, 5)];

        let (_, result, projected_spawn_points) = project_plan_with_spawns(
            &b,
            &[],
            &spawn_points,
            &WEAPONS,
        );

        assert_eq!(result.spawns_blocked, 0);
        assert!(projected_spawn_points.is_empty());
    }

    #[test]
    fn test_projection_retains_marker_when_blocking_damage_kills_blocker() {
        let mut b = Board::default();
        b.total_turns = 5;
        b.current_turn = 1;
        b.remaining_spawns = 2;
        let mut blocker = Unit::default();
        blocker.uid = 1;
        blocker.set_type_name("PunchMech");
        blocker.x = 2;
        blocker.y = 2;
        blocker.hp = 1;
        blocker.max_hp = 3;
        blocker.team = Team::Player;
        blocker.flags = UnitFlags::IS_MECH | UnitFlags::ACTIVE
            | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        b.add_unit(blocker);
        let spawn_points = vec![(2, 2), (5, 5)];

        let (projected, result, projected_spawn_points) = project_plan_with_spawns(
            &b,
            &[],
            &spawn_points,
            &WEAPONS,
        );

        assert_eq!(result.spawns_blocked, 1);
        assert_eq!(projected_spawn_points, vec![(2, 2)]);
        assert!(!projected.units[0].alive());
    }

    #[test]
    fn test_projection_retains_marker_when_blocking_damage_thaws_blocker() {
        let mut b = Board::default();
        b.total_turns = 5;
        b.current_turn = 1;
        b.remaining_spawns = 1;
        let mut blocker = Unit::default();
        blocker.uid = 1;
        blocker.set_type_name("PunchMech");
        blocker.x = 2;
        blocker.y = 2;
        blocker.hp = 1;
        blocker.max_hp = 3;
        blocker.team = Team::Player;
        blocker.flags = UnitFlags::IS_MECH | UnitFlags::ACTIVE
            | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        blocker.set_frozen(true);
        b.add_unit(blocker);
        let spawn_points = vec![(2, 2)];

        let (projected, result, projected_spawn_points) = project_plan_with_spawns(
            &b,
            &[],
            &spawn_points,
            &WEAPONS,
        );

        assert_eq!(result.spawns_blocked, 1);
        assert_eq!(projected_spawn_points, spawn_points);
        assert_eq!(projected.units[0].hp, 1);
        assert!(!projected.units[0].frozen());
    }

    #[test]
    fn test_mission_tides_projection_advances_warning_lane() {
        let mut b = Board::default();
        b.mission_id = "Mission_Tides".to_string();
        b.total_turns = 3;
        b.current_turn = 2;
        b.remaining_spawns = 0;
        for x in [1u8, 6u8] {
            let bit = 1u64 << xy_to_idx(x, 3);
            b.env_danger |= bit;
            b.env_danger_kill |= bit;
            b.env_danger_flying_immune |= bit;
        }

        let (projected, _) = project_plan(&b, &[], &[], &WEAPONS);

        assert_eq!(projected.current_turn, 3);
        assert!(!projected.is_env_danger(1, 3));
        assert!(!projected.is_env_danger(6, 3));
        assert!(projected.is_env_danger(1, 4));
        assert!(projected.is_env_danger(6, 4));
        assert!(projected.is_env_danger_kill(1, 4));
        assert!(projected.is_env_danger_flying_immune(6, 4));
    }

    #[test]
    fn test_mission_tides_projection_reconstructs_building_shadow_and_convert_mask() {
        let mut b = Board::default();
        b.mission_id = "Mission_Tides".to_string();
        b.total_turns = 3;
        b.current_turn = 2;
        b.remaining_spawns = 0;

        // The serialized y=3 warning can be sparse. On the next Plan call,
        // Lua rebuilds y=4 from Env_Tides.Index instead of shifting only the
        // old bits. A building in any earlier flooded row shadows its column;
        // a building or existing Water tile on the new row also has no marker.
        b.tile_mut(0, 1).terrain = Terrain::Building;
        b.tile_mut(0, 1).building_hp = 1;
        b.tile_mut(2, 4).terrain = Terrain::Building;
        b.tile_mut(2, 4).building_hp = 1;
        b.tile_mut(3, 4).terrain = Terrain::Water;
        for x in [2u8, 3u8, 4u8, 5u8, 7u8] {
            b.tile_mut(x, 3).terrain = Terrain::Water;
        }
        for x in [1u8, 6u8] {
            let bit = 1u64 << xy_to_idx(x, 3);
            b.env_danger |= bit;
            b.env_danger_kill |= bit;
            b.env_danger_flying_immune |= bit;
        }

        let (projected, _) = project_plan(&b, &[], &[], &WEAPONS);

        assert_eq!(projected.current_turn, 3);
        for x in [0u8, 2u8, 3u8] {
            assert!(
                !projected.is_env_danger(x, 4),
                "Lua warning construction should omit ({x},4)"
            );
        }
        for x in [1u8, 4u8, 5u8, 6u8, 7u8] {
            assert!(projected.is_env_danger(x, 4), "expected warning at ({x},4)");
            assert!(projected.is_env_danger_kill(x, 4));
            assert!(projected.is_env_danger_flying_immune(x, 4));
        }
    }

    #[test]
    fn test_mission_tides_index_advances_markerless_lane_and_spawn_boundary() {
        let mut b = Board::default();
        b.mission_id = "Mission_Tides".to_string();
        b.total_turns = 5;
        b.current_turn = 2;
        b.env_tides_index = Some(3);

        // The current warning is completely invisible. Index still advances
        // to y=4. A building shadow and existing Water suppress warnings, but
        // Env_Tides::Plan permanently blocks every x in the full lane.
        b.tile_mut(0, 1).terrain = Terrain::Building;
        b.tile_mut(0, 1).building_hp = 1;
        b.tile_mut(2, 4).terrain = Terrain::Water;

        let (projected, _) = project_plan(&b, &[], &[], &WEAPONS);

        assert_eq!(projected.env_tides_index, Some(4));
        assert!(!projected.is_env_danger(0, 4));
        assert!(!projected.is_env_danger(2, 4));
        for x in [1u8, 3, 4, 5, 6, 7] {
            assert!(projected.is_env_danger(x, 4));
        }
        for x in 0u8..8 {
            assert!(projected.is_tides_spawn_permanently_blocked(x, 4));
            assert!(!projected.is_tides_spawn_permanently_blocked(x, 5));
        }
    }

    #[test]
    fn test_mission_tides_index_beats_stale_visible_marker_row() {
        let mut b = Board::default();
        b.mission_id = "Mission_Tides".to_string();
        b.env_tides_index = Some(3);
        b.env_danger = 1u64 << xy_to_idx(6, 5);
        b.env_danger_kill = b.env_danger;
        b.env_danger_flying_immune = b.env_danger;

        let (projected, _) = project_plan(&b, &[], &[], &WEAPONS);

        assert_eq!(projected.env_tides_index, Some(4));
        for x in 0u8..8 {
            assert!(projected.is_env_danger(x, 4));
            assert!(!projected.is_env_danger(x, 6));
        }
    }

    #[test]
    fn test_mission_tides_conservative_projection_keeps_current_marker() {
        let mut b = Board::default();
        b.mission_id = "Mission_Tides".to_string();
        b.env_tides_index = Some(3);
        let mut blocker = Unit::default();
        blocker.uid = 1;
        blocker.set_type_name("PunchMech");
        blocker.x = 5;
        blocker.y = 4;
        blocker.hp = 2;
        blocker.max_hp = 3;
        blocker.team = Team::Player;
        blocker.flags = UnitFlags::IS_MECH | UnitFlags::PUSHABLE;
        b.add_unit(blocker);

        let (projected, result, projected_spawns) =
            project_plan_with_spawns(&b, &[], &[(5, 4)], &WEAPONS);

        assert_eq!(result.spawns_blocked, 1);
        assert_eq!(projected.env_tides_index, Some(4));
        assert!(projected.is_tides_spawn_permanently_blocked(5, 4));
        // Rust does not model native future-spawn selection, and the effect of
        // BlockSpawn on a marker that already persisted through emergence is
        // untraced. Conservatively retain that known marker; do not fabricate
        // a native deletion from the source-derived future eligibility mask.
        assert_eq!(projected_spawns, vec![(5, 4)]);
        assert_eq!(projected.units[0].hp, 1);
    }

    #[test]
    fn test_mission_tides_legacy_marker_fallback_still_advances() {
        let mut b = Board::default();
        b.mission_id = "Mission_Tides".to_string();
        b.env_danger = 1u64 << xy_to_idx(3, 2);
        b.env_danger_kill = b.env_danger;
        b.env_danger_flying_immune = b.env_danger;

        let (projected, _) = project_plan(&b, &[], &[], &WEAPONS);

        assert_eq!(projected.env_tides_index, None);
        for x in 0u8..8 {
            assert!(projected.is_env_danger(x, 3));
        }
    }

    #[test]
    fn test_mission_terratide_projection_smokes_full_row_and_advances_warning_backwards() {
        let mut b = Board::default();
        b.mission_id = "Mission_Terratide".to_string();
        b.total_turns = 3;
        b.current_turn = 2;
        b.remaining_spawns = 0;

        // Live MarkBoard omits buildings from its warning markers, while
        // ApplyEffect still smokes the complete current row. The next warned
        // row also contains a building at x=0, matching run
        // 20260713_052159_731 turn 2 -> 3.
        b.tile_mut(0, 4).terrain = Terrain::Building;
        b.tile_mut(0, 4).building_hp = 1;
        b.tile_mut(0, 3).terrain = Terrain::Building;
        b.tile_mut(0, 3).building_hp = 1;
        for x in 1u8..8 {
            b.env_smoke |= 1u64 << xy_to_idx(x, 4);
        }

        let (projected, _) = project_plan(&b, &[], &[], &WEAPONS);

        assert_eq!(projected.current_turn, 3);
        for x in 0u8..8 {
            assert!(
                projected.tile(x, 4).smoke(),
                "current Terratide lane should smoke ({x},4), including buildings",
            );
            assert!(
                !projected.is_env_smoke(x, 4),
                "old y=4 warning must not persist at ({x},4)",
            );
        }
        assert!(!projected.is_env_smoke(0, 3));
        for x in 1u8..8 {
            assert!(
                projected.is_env_smoke(x, 3),
                "next Terratide warning should advance to ({x},3)",
            );
        }
        assert_eq!(projected.env_danger, 0);
        assert_eq!(projected.env_danger_kill, 0);
    }

    #[test]
    fn test_mission_terratide_prior_building_does_not_shadow_next_warning() {
        let mut b = Board::default();
        b.mission_id = "Mission_Terratide".to_string();
        b.tile_mut(0, 4).terrain = Terrain::Building;
        b.tile_mut(0, 4).building_hp = 1;
        for x in 1u8..8 {
            b.env_smoke |= 1u64 << xy_to_idx(x, 4);
        }

        let (projected, _) = project_plan(&b, &[], &[], &WEAPONS);

        for x in 0u8..8 {
            assert!(
                projected.is_env_smoke(x, 3),
                "a higher-y building must not shadow Terratide warning ({x},3)",
            );
        }
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

        requeue_enemies_heuristic(&mut b, &crate::weapons::WEAPONS);

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

        requeue_enemies_heuristic(&mut b, &crate::weapons::WEAPONS);

        let e = &b.units[1];
        assert_eq!(e.queued_target_x, 3);
        assert_eq!(e.queued_target_y, 3);
        assert!(e.has_queued_attack());
    }

    #[test]
    fn test_heuristic_requeues_webbed_but_skips_frozen_smoked() {
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
        let smoked = mk_enemy(12, 2, 3, UnitFlags::empty());
        b.add_unit(smoked);
        b.tiles[xy_to_idx(2, 3)].set_smoke(true);
        // Re-apply frozen flag via set_frozen so filter sees it.
        b.units[0].set_frozen(true);
        b.units[1].set_web(true);

        requeue_enemies_heuristic(&mut b, &crate::weapons::WEAPONS);

        for i in [0usize, 2usize] {
            let e = &b.units[i];
            assert_eq!(e.queued_target_x, -1,
                "skipped enemy uid={} must stay queue-less", e.uid);
            assert!(!e.has_queued_attack());
        }
        let webbed = &b.units[1];
        assert_eq!(webbed.queued_target_x, 3);
        assert_eq!(webbed.queued_target_y, 3);
        assert!(webbed.has_queued_attack());
    }

    #[test]
    fn test_webbed_melee_enemy_reach_excludes_movement() {
        let mut b = Board::default();
        b.total_turns = 5;
        b.current_turn = 1;
        let mut enemy = Unit::default();
        enemy.uid = 10;
        enemy.set_type_name("Scorpion1");
        enemy.x = 0;
        enemy.y = 0;
        enemy.hp = 1;
        enemy.max_hp = 1;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        enemy.move_speed = 3;
        enemy.set_web(true);
        enemy.queued_target_x = -1;
        enemy.queued_target_y = -1;
        b.add_unit(enemy);

        b.tiles[xy_to_idx(0, 1)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(0, 1)].building_hp = 1;
        requeue_enemies_heuristic(&mut b, &crate::weapons::WEAPONS);
        assert_eq!(b.units[0].queued_target_x, 0);
        assert_eq!(b.units[0].queued_target_y, 1);

        b.tiles[xy_to_idx(0, 1)] = Default::default();
        b.tiles[xy_to_idx(0, 2)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(0, 2)].building_hp = 1;
        b.units[0].queued_target_x = -1;
        b.units[0].queued_target_y = -1;
        b.units[0].flags.remove(UnitFlags::HAS_QUEUED_ATTACK);
        requeue_enemies_heuristic(&mut b, &crate::weapons::WEAPONS);
        assert_eq!(b.units[0].queued_target_x, -1);
        assert!(!b.units[0].has_queued_attack());
    }

    #[test]
    fn test_webbed_projectile_uses_unlimited_line_reach() {
        let mut b = Board::default();
        let mut enemy = Unit::default();
        enemy.uid = 10;
        enemy.set_type_name("Firefly1");
        enemy.x = 0;
        enemy.y = 0;
        enemy.hp = 1;
        enemy.max_hp = 1;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        enemy.move_speed = 3;
        enemy.set_web(true);
        enemy.queued_target_x = -1;
        enemy.queued_target_y = -1;
        b.add_unit(enemy);
        b.tiles[xy_to_idx(0, 7)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(0, 7)].building_hp = 1;

        requeue_enemies_heuristic(&mut b, &crate::weapons::WEAPONS);

        assert_eq!(b.units[0].queued_target_x, 0);
        assert_eq!(b.units[0].queued_target_y, 7);
        assert!(b.units[0].has_queued_attack());
    }

    #[test]
    fn test_webbed_artillery_uses_full_board_reach() {
        let mut b = Board::default();
        let mut enemy = Unit::default();
        enemy.uid = 10;
        enemy.set_type_name("Scarab1");
        enemy.x = 0;
        enemy.y = 0;
        enemy.hp = 1;
        enemy.max_hp = 1;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        enemy.set_web(true);
        enemy.queued_target_x = -1;
        enemy.queued_target_y = -1;
        b.add_unit(enemy);
        b.tiles[xy_to_idx(7, 7)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(7, 7)].building_hp = 1;

        requeue_enemies_heuristic(&mut b, &crate::weapons::WEAPONS);

        assert_eq!(b.units[0].queued_target_x, 7);
        assert_eq!(b.units[0].queued_target_y, 7);
        assert!(b.units[0].has_queued_attack());
    }

    #[test]
    fn test_webbed_moth_reach_stops_at_lua_maximum() {
        let moth = |building_y: u8| {
            let mut b = Board::default();
            let mut enemy = Unit::default();
            enemy.uid = 10;
            enemy.set_type_name("Moth1");
            enemy.x = 0;
            enemy.y = 0;
            enemy.hp = 3;
            enemy.max_hp = 3;
            enemy.team = Team::Enemy;
            enemy.flags =
                UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
            enemy.set_web(true);
            enemy.queued_target_x = -1;
            enemy.queued_target_y = -1;
            b.add_unit(enemy);
            b.tiles[xy_to_idx(0, building_y)].terrain = Terrain::Building;
            b.tiles[xy_to_idx(0, building_y)].building_hp = 1;
            b
        };

        let mut at_maximum = moth(5);
        assert_eq!(
            projected_enemy_reach(&at_maximum.units[0], &WEAPONS),
            5,
        );
        requeue_enemies_heuristic(&mut at_maximum, &WEAPONS);
        assert_eq!(at_maximum.units[0].queued_target_y, 5);
        assert!(at_maximum.units[0].has_queued_attack());

        let mut beyond_maximum = moth(6);
        requeue_enemies_heuristic(&mut beyond_maximum, &WEAPONS);
        assert_eq!(beyond_maximum.units[0].queued_target_y, -1);
        assert!(!beyond_maximum.units[0].has_queued_attack());
    }

    #[test]
    fn test_tumblebug_projection_spawns_bombrock_and_queues_its_hit() {
        let mut board = Board::default();
        let mut dung = Unit::default();
        dung.uid = 10;
        dung.set_type_name("Dung1");
        dung.x = 3;
        dung.y = 3;
        dung.hp = 2;
        dung.max_hp = 2;
        dung.team = Team::Enemy;
        dung.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        dung.set_web(true);
        dung.queued_target_x = -1;
        dung.queued_target_y = -1;
        board.add_unit(dung);
        board.tiles[xy_to_idx(3, 1)].terrain = Terrain::Building;
        board.tiles[xy_to_idx(3, 1)].building_hp = 2;

        requeue_enemies_heuristic(&mut board, &WEAPONS);

        assert_eq!(
            (board.units[0].queued_target_x, board.units[0].queued_target_y),
            (3, 2),
        );
        assert!(board.units[0].has_queued_attack());
        let rock_idx = (0..board.unit_count as usize)
            .find(|&i| board.units[i].type_name_str() == "BombRock")
            .expect("Tumblebug planning must immediately spawn BombRock");
        assert_eq!((board.units[rock_idx].x, board.units[rock_idx].y), (3, 2));
        assert_eq!(board.units[rock_idx].team, Team::Neutral);
        assert_eq!(board.units[rock_idx].hp, 1);

        let mut original_positions = [(0u8, 0u8); 16];
        for i in 0..board.unit_count as usize {
            original_positions[i] = (board.units[i].x, board.units[i].y);
        }
        simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!(board.units[rock_idx].hp, 0);
        assert_eq!(
            board.tile(3, 1).building_hp,
            1,
            "queued hit must detonate the projected boulder on the next enemy phase",
        );
    }

    #[test]
    fn test_tumblebug_leader_projection_spawns_two_rocks_in_attack_line() {
        let mut board = Board::default();
        let mut boss = Unit::default();
        boss.uid = 20;
        boss.set_type_name("DungBoss");
        boss.x = 3;
        boss.y = 4;
        boss.hp = 6;
        boss.max_hp = 6;
        boss.team = Team::Enemy;
        boss.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        boss.set_web(true);
        boss.queued_target_x = -1;
        boss.queued_target_y = -1;
        board.add_unit(boss);
        board.tiles[xy_to_idx(3, 1)].terrain = Terrain::Building;
        board.tiles[xy_to_idx(3, 1)].building_hp = 2;

        requeue_enemies_heuristic(&mut board, &WEAPONS);

        assert_eq!(
            (board.units[0].queued_target_x, board.units[0].queued_target_y),
            (3, 3),
        );
        let rocks: Vec<usize> = (0..board.unit_count as usize)
            .filter(|&i| board.units[i].type_name_str() == "BombRock")
            .collect();
        assert_eq!(rocks.len(), 2);
        assert_eq!(
            rocks
                .iter()
                .map(|&i| (board.units[i].x, board.units[i].y))
                .collect::<Vec<_>>(),
            vec![(3, 3), (3, 2)],
        );

        let mut original_positions = [(0u8, 0u8); 16];
        for i in 0..board.unit_count as usize {
            original_positions[i] = (board.units[i].x, board.units[i].y);
        }
        simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert!(
            rocks.iter().all(|&i| board.units[i].hp <= 0),
            "projected rock HP after chain: {:?}",
            rocks.iter().map(|&i| board.units[i].hp).collect::<Vec<_>>(),
        );
        assert_eq!(
            board.tile(3, 1).building_hp,
            1,
            "first boulder must chain into the Leader's second boulder",
        );
    }

    #[test]
    fn test_tumblebug_leader_projection_skips_blocked_second_rock_only() {
        let mut board = Board::default();
        let mut boss = Unit::default();
        boss.uid = 25;
        boss.set_type_name("DungBoss");
        boss.x = 3;
        boss.y = 4;
        boss.hp = 6;
        boss.max_hp = 6;
        boss.team = Team::Enemy;
        boss.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        boss.set_web(true);
        boss.queued_target_x = -1;
        boss.queued_target_y = -1;
        board.add_unit(boss);
        board.tiles[xy_to_idx(2, 3)].terrain = Terrain::Building;
        board.tiles[xy_to_idx(2, 3)].building_hp = 2;
        board.tiles[xy_to_idx(3, 2)].terrain = Terrain::Water;
        for (x, y) in [(4, 4), (3, 5), (2, 4)] {
            board.tiles[xy_to_idx(x, y)].terrain = Terrain::Chasm;
        }

        requeue_enemies_heuristic(&mut board, &WEAPONS);

        assert_eq!(
            (board.units[0].queued_target_x, board.units[0].queued_target_y),
            (3, 3),
        );
        let rocks: Vec<(u8, u8)> = (0..board.unit_count as usize)
            .filter(|&i| board.units[i].type_name_str() == "BombRock")
            .map(|i| (board.units[i].x, board.units[i].y))
            .collect();
        assert_eq!(rocks, vec![(3, 3)]);
    }

    #[test]
    fn test_tumblebug_projection_does_not_spawn_when_first_target_is_blocked() {
        let mut board = Board::default();
        let mut boss = Unit::default();
        boss.uid = 30;
        boss.set_type_name("DungBoss");
        boss.x = 3;
        boss.y = 3;
        boss.hp = 6;
        boss.max_hp = 6;
        boss.team = Team::Enemy;
        boss.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        boss.set_web(true);
        boss.queued_target_x = -1;
        boss.queued_target_y = -1;
        board.add_unit(boss);

        board.tiles[xy_to_idx(3, 2)].terrain = Terrain::Building;
        board.tiles[xy_to_idx(3, 2)].building_hp = 2;
        for (x, y) in [(3, 4), (4, 3), (2, 3)] {
            board.tiles[xy_to_idx(x, y)].terrain = Terrain::Chasm;
        }

        requeue_enemies_heuristic(&mut board, &WEAPONS);

        assert_eq!(
            (board.units[0].queued_target_x, board.units[0].queued_target_y),
            (3, 2),
        );
        assert!(board.units[0].has_queued_attack());
        assert!(
            (0..board.unit_count as usize)
                .all(|i| board.units[i].type_name_str() != "BombRock"),
            "blocked first target prevents both Leader boulder spawns",
        );
    }

    #[test]
    fn test_tumblebug_projection_rejects_harmless_empty_rock_targets() {
        let mut board = Board::default();
        let mut dung = Unit::default();
        dung.uid = 35;
        dung.set_type_name("Dung1");
        dung.x = 3;
        dung.y = 3;
        dung.hp = 2;
        dung.max_hp = 2;
        dung.team = Team::Enemy;
        dung.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        dung.set_web(true);
        dung.queued_target_x = -1;
        dung.queued_target_y = -1;
        board.add_unit(dung);

        requeue_enemies_heuristic(&mut board, &WEAPONS);

        assert!(!board.units[0].has_queued_attack());
        assert!(
            (0..board.unit_count as usize)
                .all(|i| board.units[i].type_name_str() != "BombRock"),
            "Lua returns zero when the fake explosion has no positive target score",
        );
    }

    #[test]
    fn test_tumblebug_projected_bombrock_legality_matrix() {
        let mut board = Board::default();
        assert!(projected_tumblebug_can_spawn_rock(&board, 2, 2));

        board.tiles[xy_to_idx(2, 2)].terrain = Terrain::Water;
        assert!(!projected_tumblebug_can_spawn_rock(&board, 2, 2));
        board.tiles[xy_to_idx(2, 2)].terrain = Terrain::Chasm;
        assert!(!projected_tumblebug_can_spawn_rock(&board, 2, 2));
        board.tiles[xy_to_idx(2, 2)].terrain = Terrain::Building;
        board.tiles[xy_to_idx(2, 2)].building_hp = 2;
        assert!(!projected_tumblebug_can_spawn_rock(&board, 2, 2));

        board.tiles[xy_to_idx(2, 2)] = Default::default();
        board.tiles[xy_to_idx(2, 2)].set_has_pod(true);
        assert!(!projected_tumblebug_target_legal(&board, 2, 2));
        assert!(!projected_tumblebug_can_spawn_rock(&board, 2, 2));

        board.tiles[xy_to_idx(2, 2)] = Default::default();
        let mut blocker = Unit::default();
        blocker.uid = 40;
        blocker.set_type_name("PunchMech");
        blocker.x = 2;
        blocker.y = 2;
        blocker.hp = 3;
        blocker.max_hp = 3;
        blocker.team = Team::Player;
        board.add_unit(blocker);
        assert!(projected_tumblebug_target_legal(&board, 2, 2));
        assert!(!projected_tumblebug_can_spawn_rock(&board, 2, 2));

        board.units[0].hp = 0;
        assert!(
            !projected_tumblebug_can_spawn_rock(&board, 2, 2),
            "a disabled player mech remains a blocking wreck",
        );
        board.units[0].set_type_name("BombRock");
        board.units[0].team = Team::Neutral;
        assert!(
            projected_tumblebug_can_spawn_rock(&board, 2, 2),
            "an exploded BombRock's retained record must not block the next planning phase",
        );
    }

    #[test]
    fn test_webbed_starfish_requeues_self_for_positive_diagonal_score() {
        let mut b = Board::default();
        let mut enemy = Unit::default();
        enemy.uid = 10;
        enemy.set_type_name("Starfish1");
        enemy.x = 0;
        enemy.y = 0;
        enemy.hp = 1;
        enemy.max_hp = 1;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        enemy.set_web(true);
        enemy.queued_target_x = -1;
        enemy.queued_target_y = -1;
        b.add_unit(enemy);
        b.tiles[xy_to_idx(1, 1)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(1, 1)].building_hp = 1;

        assert_eq!(projected_enemy_reach(&b.units[0], &crate::weapons::WEAPONS), 2);
        requeue_enemies_heuristic(&mut b, &crate::weapons::WEAPONS);

        assert_eq!(b.units[0].queued_target_x, 0);
        assert_eq!(b.units[0].queued_target_y, 0);
        assert!(b.units[0].has_queued_attack());
    }

    #[test]
    fn test_starfish_zero_score_projection_stays_queueless() {
        let mut b = Board::default();
        let mut enemy = Unit::default();
        enemy.uid = 10;
        enemy.set_type_name("Starfish2");
        enemy.x = 3;
        enemy.y = 3;
        enemy.hp = 4;
        enemy.max_hp = 4;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        enemy.queued_target_x = -1;
        enemy.queued_target_y = -1;
        b.add_unit(enemy);

        requeue_enemies_heuristic(&mut b, &crate::weapons::WEAPONS);

        assert_eq!(b.units[0].queued_target_x, -1);
        assert_eq!(b.units[0].queued_target_y, -1);
        assert!(!b.units[0].has_queued_attack());
    }

    #[test]
    fn test_requeued_starfish_damages_on_second_projection() {
        let mut b = Board::default();
        b.grid_power = 7;
        b.grid_power_max = 7;
        b.current_turn = 1;
        b.total_turns = 5;
        let mut enemy = Unit::default();
        enemy.uid = 10;
        enemy.set_type_name("Starfish1");
        enemy.x = 0;
        enemy.y = 0;
        enemy.hp = 2;
        enemy.max_hp = 2;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        enemy.set_web(true);
        enemy.queued_target_x = -1;
        enemy.queued_target_y = -1;
        b.add_unit(enemy);
        b.tiles[xy_to_idx(1, 1)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(1, 1)].building_hp = 1;

        let (queued, _) = project_plan(&b, &[], &[], &WEAPONS);
        let (attacked, _) = project_plan(&queued, &[], &[], &WEAPONS);

        assert_eq!(queued.units[0].queued_target_x, 0);
        assert_eq!(queued.units[0].queued_target_y, 0);
        assert_eq!(attacked.tile(1, 1).building_hp, 0);
        assert_eq!(attacked.grid_power, 6);
    }

    #[test]
    fn test_stationary_special_attack_reach_covers_collateral() {
        let mk = |name: &str| {
            let mut enemy = Unit::default();
            enemy.set_type_name(name);
            enemy.hp = 1;
            enemy.max_hp = 1;
            enemy.team = Team::Enemy;
            enemy.set_web(true);
            enemy
        };

        assert_eq!(projected_enemy_reach(&mk("Tumblebug1"), &WEAPONS), 2);
        assert_eq!(projected_enemy_reach(&mk("DungBoss"), &WEAPONS), 3);
        assert_eq!(projected_enemy_reach(&mk("Bouncer1"), &WEAPONS), 2);
        assert_eq!(projected_enemy_reach(&mk("BouncerBoss"), &WEAPONS), 3);
        assert_eq!(projected_enemy_reach(&mk("Shaman1"), &WEAPONS), 14);
        let mut snowmine = mk("Snowmine1");
        snowmine.set_web(false);
        snowmine.move_speed = 0;
        assert_eq!(projected_enemy_reach(&snowmine, &WEAPONS), 3);
    }

    #[test]
    fn test_stationary_special_targeting_stays_queueless() {
        let mut b = Board::default();
        let mut enemy = Unit::default();
        enemy.uid = 10;
        enemy.set_type_name("Blobber1");
        enemy.x = 0;
        enemy.y = 0;
        enemy.hp = 2;
        enemy.max_hp = 2;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        enemy.set_web(true);
        enemy.queued_target_x = -1;
        enemy.queued_target_y = -1;
        b.add_unit(enemy);
        b.tiles[xy_to_idx(7, 7)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(7, 7)].building_hp = 1;

        requeue_enemies_heuristic(&mut b, &WEAPONS);

        assert_eq!(b.units[0].queued_target_x, -1);
        assert!(!b.units[0].has_queued_attack());
    }

    #[test]
    fn test_bespoke_and_passive_enemies_stay_queueless() {
        let mut b = Board::default();
        b.tiles[xy_to_idx(3, 3)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(3, 3)].building_hp = 1;

        let mut bot = Unit::default();
        bot.uid = 10;
        bot.set_type_name("BotBoss");
        bot.x = 3;
        bot.y = 2;
        bot.hp = 2;
        bot.max_hp = 4;
        bot.team = Team::Enemy;
        bot.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        bot.weapon2.0 = WId::BossHeal as u16;
        bot.queued_target_x = -1;
        bot.queued_target_y = -1;
        b.add_unit(bot);

        let mut egg = Unit::default();
        egg.uid = 11;
        egg.set_type_name("WebbEgg1");
        egg.x = 2;
        egg.y = 3;
        egg.hp = 1;
        egg.max_hp = 1;
        egg.team = Team::Enemy;
        egg.flags = UnitFlags::ACTIVE | UnitFlags::PUSHABLE;
        egg.queued_target_x = -1;
        egg.queued_target_y = -1;
        b.add_unit(egg);

        let mut scorpion = Unit::default();
        scorpion.uid = 12;
        scorpion.set_type_name("ScorpionBoss");
        scorpion.x = 4;
        scorpion.y = 3;
        scorpion.hp = 5;
        scorpion.max_hp = 5;
        scorpion.team = Team::Enemy;
        scorpion.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        scorpion.queued_target_x = -1;
        scorpion.queued_target_y = -1;
        b.add_unit(scorpion);

        let mut psion = Unit::default();
        psion.uid = 13;
        psion.set_type_name("Jelly_Armor1");
        psion.x = 3;
        psion.y = 4;
        psion.hp = 2;
        psion.max_hp = 2;
        psion.team = Team::Enemy;
        psion.flags = UnitFlags::ACTIVE | UnitFlags::PUSHABLE;
        psion.queued_target_x = -1;
        psion.queued_target_y = -1;
        b.add_unit(psion);

        let mut shaman = Unit::default();
        shaman.uid = 14;
        shaman.set_type_name("Shaman1");
        shaman.x = 1;
        shaman.y = 3;
        shaman.hp = 3;
        shaman.max_hp = 3;
        shaman.team = Team::Enemy;
        shaman.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        shaman.queued_target_x = -1;
        shaman.queued_target_y = -1;
        b.add_unit(shaman);

        let mut snowmine = Unit::default();
        snowmine.uid = 15;
        snowmine.set_type_name("Snowmine1");
        snowmine.x = 5;
        snowmine.y = 3;
        snowmine.hp = 1;
        snowmine.max_hp = 1;
        snowmine.team = Team::Enemy;
        snowmine.flags = UnitFlags::ACTIVE | UnitFlags::PUSHABLE;
        snowmine.move_speed = 0;
        snowmine.queued_target_x = -1;
        snowmine.queued_target_y = -1;
        b.add_unit(snowmine);

        requeue_enemies_heuristic(&mut b, &WEAPONS);

        for enemy in &b.units[..b.unit_count as usize] {
            assert_eq!(enemy.queued_target_x, -1);
            assert!(!enemy.has_queued_attack());
        }
    }

    #[test]
    fn test_naturally_stationary_projectile_uses_attack_range() {
        let mut b = Board::default();
        let mut enemy = Unit::default();
        enemy.uid = 10;
        enemy.set_type_name("Totem1");
        enemy.x = 0;
        enemy.y = 0;
        enemy.hp = 2;
        enemy.max_hp = 2;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::PUSHABLE;
        enemy.move_speed = 0;
        enemy.queued_target_x = -1;
        enemy.queued_target_y = -1;
        b.add_unit(enemy);
        b.tiles[xy_to_idx(0, 7)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(0, 7)].building_hp = 1;

        requeue_enemies_heuristic(&mut b, &WEAPONS);

        assert_eq!(b.units[0].queued_target_x, 0);
        assert_eq!(b.units[0].queued_target_y, 7);
        assert!(b.units[0].has_queued_attack());
    }

    #[test]
    fn test_requeued_webbed_projectile_damages_on_second_projection() {
        let mut b = Board::default();
        b.grid_power = 7;
        b.grid_power_max = 7;
        b.current_turn = 1;
        b.total_turns = 5;
        let mut enemy = Unit::default();
        enemy.uid = 10;
        enemy.set_type_name("Firefly1");
        enemy.x = 0;
        enemy.y = 0;
        enemy.hp = 2;
        enemy.max_hp = 2;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        enemy.set_web(true);
        enemy.queued_target_x = -1;
        enemy.queued_target_y = -1;
        b.add_unit(enemy);
        b.tiles[xy_to_idx(0, 7)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(0, 7)].building_hp = 1;

        let (queued, _) = project_plan(&b, &[], &[], &WEAPONS);
        let (attacked, _) = project_plan(&queued, &[], &[], &WEAPONS);

        assert_eq!(queued.units[0].queued_target_x, 0);
        assert_eq!(queued.units[0].queued_target_y, 7);
        assert_eq!(attacked.tile(0, 7).building_hp, 0);
        assert_eq!(attacked.grid_power, 6);
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
    fn test_project_plan_scenarios_includes_webbed_retarget() {
        let mut b = Board::default();
        b.total_turns = 5; b.current_turn = 1; b.remaining_spawns = 2;

        let mut mech = Unit::default();
        mech.uid = 0; mech.set_type_name("PunchMech");
        mech.x = 1; mech.y = 1; mech.hp = 3; mech.max_hp = 3;
        mech.team = Team::Player;
        mech.flags = UnitFlags::IS_MECH | UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        mech.move_speed = 3; mech.base_move = 3;
        b.add_unit(mech);

        let mut enemy = Unit::default();
        enemy.uid = 10; enemy.set_type_name("Hornet");
        enemy.x = 4; enemy.y = 4; enemy.hp = 1; enemy.max_hp = 1;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        enemy.move_speed = 2; enemy.base_move = 2;
        enemy.set_web(true);
        enemy.queued_target_x = -1; enemy.queued_target_y = -1;
        b.add_unit(enemy);

        b.tiles[xy_to_idx(4, 3)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(4, 3)].building_hp = 1;
        b.tiles[xy_to_idx(5, 4)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(5, 4)].building_hp = 2;

        let scenarios = project_plan_scenarios(&b, &[], &[], &WEAPONS, 4);

        assert!(scenarios.len() >= 2, "expected base + retarget scenarios");
        assert_eq!(scenarios[0].label, "heuristic_requeue");
        assert_eq!(scenarios[0].board.units[1].queued_target_x, 4);
        assert_eq!(scenarios[0].board.units[1].queued_target_y, 3);
        assert!(scenarios.iter().any(|s| {
            s.label.starts_with("retarget_building_uid10_5_4")
                && s.board.units[1].queued_target_x == 5
                && s.board.units[1].queued_target_y == 4
        }));
    }

    #[test]
    fn test_project_plan_scenarios_is_bounded_and_deterministic() {
        let (board, spawn_points) = simple_board();

        let a = project_plan_scenarios(&board, &[], &spawn_points, &WEAPONS, 1);
        let b = project_plan_scenarios(&board, &[], &spawn_points, &WEAPONS, 1);

        assert_eq!(a.len(), 1);
        assert_eq!(b.len(), 1);
        assert_eq!(a[0].label, "heuristic_requeue");
        assert_eq!(a[0].board.current_turn, b[0].board.current_turn);
        assert_eq!(a[0].board.grid_power, b[0].board.grid_power);
    }

    #[test]
    fn test_board_to_json_roundtrip() {
        let (mut board, spawn_points) = simple_board();
        board.mission_id = "Mission_Tides".to_string();
        board.env_tides_index = Some(3);
        board.units[1].queued_target_raw_x = 5;
        board.units[1].queued_target_raw_y = 4;
        board.units[0].pilot_flags = crate::board::PilotFlags::ROCK;
        board.units[0].pilot_value = 0.75;
        board.units[1].flags |= UnitFlags::MINOR | UnitFlags::RANGED | UnitFlags::MASSIVE;
        board.bonus_dont_kill_types.push("Volatile_Vek".to_string());
        board.destroy_objective_unit_types.push("Hacked_Building".to_string());
        board.protect_objective_unit_types.push("Snowtank".to_string());
        let mut wreck = Unit::default();
        wreck.uid = 42;
        wreck.set_type_name("PunchMech");
        wreck.x = 6;
        wreck.y = 1;
        // Overkill is represented internally as negative HP in some damage
        // paths.  The persisted checkpoint canonicalizes every wreck to 0.
        wreck.hp = -2;
        wreck.max_hp = 3;
        wreck.team = Team::Player;
        wreck.flags = UnitFlags::IS_MECH | UnitFlags::PUSHABLE;
        board.add_unit(wreck);
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
        assert_eq!(b2.env_tides_index, Some(3));
        assert!(b2.is_tides_spawn_permanently_blocked(7, 3));
        assert_eq!(b2.units[1].queued_target_raw_x, 5);
        assert_eq!(b2.units[1].queued_target_raw_y, 4);
        assert!(b2.units[1].minor());
        assert!(b2.units[1].ranged());
        assert!(b2.units[1].massive());
        assert!(b2.units[0].pilot_flags.contains(crate::board::PilotFlags::ROCK));
        assert_eq!(b2.units[0].pilot_value, 0.75);
        let wreck_after = (0..b2.unit_count as usize)
            .map(|i| &b2.units[i])
            .find(|unit| unit.uid == 42)
            .expect("dead player-mech wreck must survive round-trip");
        assert_eq!((wreck_after.x, wreck_after.y, wreck_after.hp), (6, 1, 0));
        assert!(b2.wreck_at(6, 1));
        assert_eq!(b2.bonus_dont_kill_types, vec!["Volatile_Vek".to_string()]);
        assert_eq!(b2.destroy_objective_unit_types, vec!["Hacked_Building".to_string()]);
        assert_eq!(b2.protect_objective_unit_types, vec!["Snowtank".to_string()]);
        // Option C: round-trip must preserve the pseudo_threat_eval flag
        // that board_to_json injects.
        assert!(weights.pseudo_threat_eval,
            "projected board_to_json must set eval_weights.pseudo_threat_eval=true");
    }

    #[test]
    fn test_board_to_json_preserves_sandstorm_environment_identity() {
        let mut board = Board::default();
        board.mission_id = "Mission_Sandstorm".to_string();

        let json_str = board_to_json(&board, &[]);
        let value: serde_json::Value =
            serde_json::from_str(&json_str).expect("board_to_json emits valid json");

        assert_eq!(value["env_type"], "sandstorm");
        assert_eq!(
            value["environment_danger_v2"].as_array().unwrap().len(),
            0,
            "unmodeled Sandstorm markers must not re-enter the damage channel"
        );
    }

    #[test]
    fn test_board_to_json_preserves_nanostorm_environment_identity() {
        let mut board = Board::default();
        board.mission_id = "Mission_NanoStorm".to_string();
        let bit = 1u64 << xy_to_idx(4, 3);
        board.env_danger = bit;
        board.env_danger_acid = bit;

        let json_str = board_to_json(&board, &[]);
        let value: serde_json::Value =
            serde_json::from_str(&json_str).expect("board_to_json emits valid json");

        assert_eq!(value["env_type"], "nanostorm");
        assert_eq!(
            value["environment_danger_v2"],
            serde_json::json!([[4, 3, 1, 0, 0]])
        );
    }

    #[test]
    fn test_board_to_json_roundtrip_preserves_all_conveyor_directions() {
        let (mut board, spawn_points) = simple_board();
        for solver_dir in 0..4i8 {
            board.tile_mut(solver_dir as u8, 7).conveyor_dir = solver_dir;
        }

        let json_str = board_to_json(&board, &spawn_points);
        let value: serde_json::Value =
            serde_json::from_str(&json_str).expect("board_to_json emits valid json");
        let expected_engine_dirs = [2, 1, 0, 3];
        for (solver_dir, expected_engine_dir) in
            expected_engine_dirs.into_iter().enumerate()
        {
            let tile = value["tiles"]
                .as_array()
                .unwrap()
                .iter()
                .find(|tile| tile["x"] == solver_dir && tile["y"] == 7)
                .expect("conveyor tile is serialized");
            assert_eq!(
                tile["conveyor"],
                expected_engine_dir,
                "solver direction {solver_dir} must serialize in engine coordinates",
            );
        }

        let (roundtrip, _sp, _, _weights, _, _) = board_from_json(&json_str)
            .expect("projected conveyor board must round-trip");
        for solver_dir in 0..4i8 {
            assert_eq!(
                roundtrip.tile(solver_dir as u8, 7).conveyor_dir,
                solver_dir,
                "solver direction {solver_dir} changed across checkpoint round-trip",
            );
        }
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
