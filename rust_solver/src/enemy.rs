/// Enemy attack simulation — post-mech-action phase.
///
/// Processes enemies in bridge-provided order, falling back to UID order for
/// legacy payloads.
/// Re-traces projectile paths on the post-mech board state.
/// Uses actual weapon type dispatch (not binary ranged/melee).

use crate::types::*;
use crate::board::*;
use crate::weapons::*;
use crate::simulate::{
    apply_active_acid_storm,
    apply_auto_shield_after_building_damage,
    apply_damage,
    apply_damage_defer_death_explosion,
    apply_damage_with_bombrock_exclusion,
    apply_death_explosion,
    apply_environment_push,
    apply_push,
    apply_push_dead_bumps_live_blocker,
    apply_push_no_edge_bump,
    apply_teleport_on_land,
    apply_weapon_status,
    apply_weapon_status_with_impact_occupancy,
    flush_deferred_bump_grid_debt,
    leave_acid_pool_on_death,
    on_enemy_death,
    place_smoke,
    settle_building_grid_loss,
    simulate_snowmine_setup,
    thaw_frozen_building,
};

/// Spawn a new enemy unit at (x, y). Used by Spider/Blobber artillery
/// whose in-game effect is "create an egg / blob" at the telegraphed
/// tile. Returns true if the unit was placed, false if blocked.
///
/// A unit spawns only on terrain that can hold a small Vek:
/// Ground, Sand, Forest, Rubble, Fire, Ice. Blocked by buildings,
/// mountains, water, chasm, lava. Also blocked if a live unit already
/// occupies the tile (the game's attack resolves with no spawn).
///
/// The spawned unit inherits safe defaults: 1 HP, move 0, queued
/// target = own tile (so the egg-skip treats it as "hatching, not
/// attacking"). UID uses the next board-local pawn id, matching the
/// engine's live bridge ids closely enough for per-action verification.
pub(crate) fn spawn_enemy(
    board: &mut Board,
    x: u8, y: u8,
    type_name: &str,
    hp: i8,
) -> bool {
    // Board unit capacity is fixed (16). If full, skip spawn rather
    // than panic — the sim loses fidelity but stays alive.
    if board.unit_count as usize >= board.units.len() { return false; }
    // Occupied → no spawn
    if board.unit_at(x, y).is_some() { return false; }
    let t = board.tile(x, y);
    match t.terrain {
        Terrain::Ground | Terrain::Sand | Terrain::Forest
        | Terrain::Rubble | Terrain::Fire | Terrain::Ice => {}
        _ => return false,
    }
    let spawn_on_fire = t.on_fire() || t.terrain == Terrain::Fire;

    // Pick the next live-style pawn id. Earlier simulator versions used a
    // 9000+ synthetic range, which kept search state collision-free but made
    // bridge verification report false spawn diffs for player-phase spawns.
    let mut new_uid: u16 = 1;
    for i in 0..board.unit_count as usize {
        new_uid = new_uid.max(board.units[i].uid.saturating_add(1));
    }

    let mut u = Unit {
        uid: new_uid,
        x, y,
        hp, max_hp: hp,
        team: Team::Enemy,
        move_speed: 0,
        base_move: 0,
        queued_target_x: x as i8,
        queued_target_y: y as i8,
        ..Unit::default()
    };
    u.set_type_name(type_name);
    let idx = board.add_unit(u);
    if spawn_on_fire {
        board.units[idx].set_fire(true);
    }
    true
}

/// Spawn the source-authored stationary Totem created by ShamanAtk1/2.
///
/// Unlike Spider/Blobber children, a new Totem is not hatching or attacking
/// during the current enemy phase. It is a pushable Minor Vek with its own
/// projectile weapon, but no queued intent until the native engine selects one
/// on a later turn.
fn spawn_shaman_totem(
    board: &mut Board,
    x: u8,
    y: u8,
    type_name: &str,
    weapon: WId,
) -> bool {
    if !spawn_enemy(board, x, y, type_name, 1) {
        return false;
    }

    let idx = board
        .unit_at(x, y)
        .expect("successful Totem spawn occupies its target");
    let totem = &mut board.units[idx];
    totem.flags = UnitFlags::PUSHABLE | UnitFlags::MINOR;
    totem.weapon = WeaponId(weapon as u16);
    totem.queued_target_x = -1;
    totem.queued_target_y = -1;
    totem.queued_target_raw_x = -1;
    totem.queued_target_raw_y = -1;
    totem.queued_origin_x = -1;
    totem.queued_origin_y = -1;
    true
}

/// Whether DiggerAtk1/2's source-authored `sPawn = "Wall"` effect selects
/// this adjacent tile. The Lua predicate is narrower than ordinary ground
/// movement: PATH_PROJECTILE must be clear, Water and Time Pods are excluded,
/// and the later queued damage is a separate effect.
fn digger_wall_tile_eligible(board: &Board, x: u8, y: u8) -> bool {
    let tile = board.tile(x, y);
    if tile.terrain == Terrain::Water || tile.has_pod() {
        return false;
    }
    if matches!(tile.terrain, Terrain::Mountain | Terrain::Building) {
        return false;
    }
    board.any_unit_at(x, y).is_none()
}

// `for dir = DIR_START, DIR_END` traverses native up, right, down, left.
// Preserve that source order when assigning pawn IDs; retained bridge evidence
// records the surviving Walls in exactly this coordinate sequence.
const DIGGER_WALL_SOURCE_DIRS: [(i8, i8); 4] = [
    (0, -1),
    (1, 0),
    (0, 1),
    (-1, 0),
];

/// Materialize the neutral one-HP, zero-move rock pawn used by DiggerAtk1/2.
/// This deliberately does not reuse `spawn_enemy`: Wall is TEAM_NONE and has
/// no weapon, queued intent, movement, or enemy-phase behavior.
fn spawn_digger_wall(board: &mut Board, x: u8, y: u8) -> bool {
    if board.unit_count as usize >= board.units.len() {
        return false;
    }

    let mut new_uid = 1u16;
    for unit in board.units.iter().take(board.unit_count as usize) {
        new_uid = new_uid.max(unit.uid.saturating_add(1));
    }

    let mut wall = Unit {
        uid: new_uid,
        x,
        y,
        hp: 1,
        max_hp: 1,
        team: Team::Neutral,
        move_speed: 0,
        base_move: 0,
        flags: UnitFlags::PUSHABLE,
        queued_target_x: -1,
        queued_target_y: -1,
        queued_target_raw_x: -1,
        queued_target_raw_y: -1,
        queued_origin_x: -1,
        queued_origin_y: -1,
        ..Unit::default()
    };
    wall.set_type_name("Wall");
    let idx = board.add_unit(wall);
    if board.tile(x, y).on_fire() || board.tile(x, y).terrain == Terrain::Fire {
        board.units[idx].set_fire(true);
    }
    true
}

/// Spawn a Spider Psion death egg, falling back to the engine's adjacent
/// `sPawn` order when the death tile is no longer spawnable.
pub(crate) fn spawn_spider_psion_death_egg(board: &mut Board, x: u8, y: u8) -> bool {
    if spawn_enemy(board, x, y, "SpiderlingEgg1", 1) {
        return true;
    }

    // Same order used by live WebbEgg hatch fallback: bridge (x, y-1) first,
    // then (x+1, y), (x, y+1), (x-1, y).
    let fallback_dirs: [(i8, i8); 4] = [(0, -1), (1, 0), (0, 1), (-1, 0)];
    for &(dx, dy) in &fallback_dirs {
        let nx = x as i8 + dx;
        let ny = y as i8 + dy;
        if !in_bounds(nx, ny) {
            continue;
        }
        if spawn_enemy(board, nx as u8, ny as u8, "SpiderlingEgg1", 1) {
            return true;
        }
    }
    false
}

fn apply_mosquito_boss_attack(board: &mut Board, x: u8, y: u8, result: &mut ActionResult) {
    {
        let tile = board.tile_mut(x, y);
        tile.set_on_fire(false);
        tile.set_smoke(true);
    }

    if let Some(idx) = board.unit_at(x, y) {
        let old_hp = board.units[idx].hp.max(0) as i32;
        let was_enemy = board.units[idx].is_enemy();
        let was_player = board.units[idx].is_player();
        let mission_counted =
            unit_counts_for_mission_kill(board.mission_id.as_str(), &board.units[idx]);
        board.units[idx].set_shield(false);
        board.units[idx].set_frozen(false);
        board.units[idx].hp = 0;
        if was_enemy {
            result.enemy_damage_dealt += old_hp;
            result.record_enemy_kill(mission_counted);
            on_enemy_death(board, idx, result);
        } else if was_player {
            result.mech_damage_taken += old_hp;
            result.mechs_killed += 1;
        }
    }

    let tile_idx = xy_to_idx(x, y);
    let is_unique = (board.unique_buildings & (1u64 << tile_idx)) != 0;
    let mut hp_lost = 0u8;
    let mut destroyed = false;
    {
        let tile = board.tile_mut(x, y);
        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
            if tile.frozen() {
                tile.set_frozen(false);
                result.events.push(format!("building_thawed:{}:{}", x, y));
            } else {
                hp_lost = tile.building_hp;
                tile.building_hp = 0;
                tile.set_shield(false);
                if !is_unique {
                    tile.terrain = Terrain::Rubble;
                }
                destroyed = true;
            }
        }
    }
    if hp_lost > 0 {
        result.buildings_damaged += hp_lost as i32;
        result.buildings_lost += 1;
        result.grid_damage += hp_lost as i32;
        let grid_loss = settle_building_grid_loss(
            board,
            tile_idx,
            hp_lost,
            destroyed,
            is_unique,
            DamageSource::Weapon,
        );
        result.grid_damage += (grid_loss as i32) - (hp_lost as i32);
        board.grid_power = board.grid_power.saturating_sub(grid_loss);
    }
}

/// Get effective damage for an enemy hit at a tile. Vek Hormones adds its
/// source-defined magnitude only when the target is another enemy.
fn enemy_hit_damage(
    board: &Board,
    x: u8,
    y: u8,
    base_damage: u8,
    vek_hormones_damage: u8,
) -> u8 {
    if vek_hormones_damage > 0 {
        if let Some(idx) = board.unit_at(x, y) {
            if board.units[idx].is_enemy() {
                return base_damage.saturating_add(vek_hormones_damage);
            }
        }
    }
    base_damage
}

fn queued_origin_for_attack(enemy: &Unit, fallback: (u8, u8)) -> (u8, u8) {
    if enemy.flags.contains(UnitFlags::QUEUED_ORIGIN_SET)
        && enemy.queued_origin_x >= 0
        && enemy.queued_origin_y >= 0
    {
        (enemy.queued_origin_x as u8, enemy.queued_origin_y as u8)
    } else if in_bounds(fallback.0 as i8, fallback.1 as i8) {
        fallback
    } else {
        (enemy.x, enemy.y)
    }
}

/// Starfish attacks are self-targeted queued appendage strikes:
/// - normal/alpha Starfish damage the four diagonal tiles around themselves;
/// - Starfish Leader additionally pushes the four cardinal adjacent tiles
///   outward with zero damage.
///
/// Lua references:
/// - scripts/advanced/ae_weapons_enemy.lua::StarfishAtk1
/// - scripts/advanced/bosses/starfish.lua::StarfishAtkB1
fn apply_starfish_appendages(
    board: &mut Board,
    ex: u8,
    ey: u8,
    damage: u8,
    push_cardinals: bool,
    vek_hormones_damage: u8,
    result: &mut ActionResult,
) {
    for dir in 0..DIRS.len() {
        let (dx1, dy1) = DIRS[dir];
        let (dx2, dy2) = DIRS[(dir + 1) % DIRS.len()];
        let diag_x = ex as i8 + dx1 + dx2;
        let diag_y = ey as i8 + dy1 + dy2;
        if in_bounds(diag_x, diag_y) {
            let x = diag_x as u8;
            let y = diag_y as u8;
            let d = enemy_hit_damage(
                board,
                x,
                y,
                damage,
                vek_hormones_damage,
            );
            apply_damage(board, x, y, d, result, DamageSource::Weapon);
        }

        if push_cardinals {
            let card_x = ex as i8 + dx1;
            let card_y = ey as i8 + dy1;
            if in_bounds(card_x, card_y) {
                apply_push(board, card_x as u8, card_y as u8, dir, result);
            }
        }
    }
}

/// Apply environment_danger damage to a tile.
///
/// `lethal=true` (Deadly Threat: air strike, lightning, cataclysm, etc.) bypasses
/// shield, frozen, armor, and ACID — sets HP=0 outright. Buildings destroyed.
///
/// `flying_immune=true` (Tidal Wave, Cataclysm, Seismic — terrain-conversion
/// lethal hazards) skips effectively-flying units: water-conversion hovers
/// flyers; chasm-conversion hovers flyers. Massive non-flying still die
/// (chasm rules + project convention). Buildings on the tile still take
/// the lethal damage regardless. The bridge populates this per-tile via the
/// 5th element of `environment_danger_v2` entries; missing → false (treat as
/// pure Deadly Threat, preserving pre-fix behavior). Final Cave falling rocks
/// are Deadly Threats, not hoverable chasm conversion.
///
/// `lethal=false` is a genuine non-lethal damage payload. Generic legacy
/// payloads retain the conservative ground-only behavior. `acid=true` is the
/// exact Env_NanoStorm subclass: its SpaceDamage hits flyers too, deals one
/// damage, and applies ACID (or leaves an ACID pool when the status is blocked
/// or the tile was empty). NanoStorm selection excludes buildings.
/// Status/movement-only environments are removed from `env_danger` during
/// bridge deserialization.
///
/// Inlined unit/building handling (does not call apply_damage) so we can bypass
/// shield/frozen for the lethal case without polluting the core damage path.
fn apply_env_danger(
    board: &mut Board,
    x: u8, y: u8,
    lethal: bool,
    flying_immune: bool,
    acid: bool,
    flying_immune_damage: u8,
    skip_enemy_units: bool,
    result: &mut ActionResult,
) {
    // Preserve pre-hit occupancy for terrain semantics. A pawn killed by the
    // danger still occupied the tile when the engine applied SpaceDamage.
    let occupied_by_alive_unit_at_start = board.unit_at(x, y).is_some();
    let building_at_start = board.tile(x, y).is_building();
    let mission_tides_mountain = board.mission_id == "Mission_Tides"
        && board.tile(x, y).terrain == Terrain::Mountain;

    // Damage unit if present. Track whether an enemy died so we can run
    // the shared death-cleanup after the mutable borrow ends — Psion
    // auras must be torn down even on env kills, which bypass apply_damage.
    let mut enemy_died_idx: Option<usize> = None;
    let mut acid_unit_idx: Option<usize> = None;
    let mut acid_to_tile = acid && !occupied_by_alive_unit_at_start;
    if let Some(uidx) = board.unit_at(x, y) {
        let unit = &mut board.units[uidx];
        if unit.hp > 0 && !(skip_enemy_units && unit.is_enemy()) {
            let hp_before = unit.hp;
            // Tidal/Cataclysm/Seismic spare effectively-flying units. Massive
            // non-flying still die: water-conversion is destroy-not-drown per
            // project convention; chasm rules ignore Massive.
            // Env_Tides adds explicit DAMAGE_DEATH when the pre-effect terrain
            // is Mountain. That hit kills even a flyer before/while the tile
            // becomes Water; ordinary tide tiles retain flying immunity.
            let spared_by_flight = lethal
                && flying_immune
                && !mission_tides_mountain
                && unit.effectively_flying();
            if lethal && !spared_by_flight {
                // Outcome-equivalent DAMAGE_DEATH projection. Native clears
                // Shield/Frozen, applies Armor/ACID arithmetic, then clamps the
                // HP delta; stock supported health still reaches zero.
                let prev_hp = unit.hp;
                unit.hp = 0;
                unit.set_shield(false);
                unit.set_frozen(false);
                if unit.is_player() {
                    result.mechs_killed += 1;
                    result.mech_damage_taken += prev_hp as i32;
                } else if unit.is_enemy() {
                    result.record_enemy_kill(
                        unit_counts_for_mission_kill(board.mission_id.as_str(), unit)
                    );
                    result.enemy_damage_dealt += prev_hp as i32;
                    enemy_died_idx = Some(uidx);
                }
            } else if lethal && spared_by_flight {
                // Terrain-conversion lethal env spares flyers from the instant
                // kill. Mission_Tides still hits hovering units for 1 damage;
                // Cataclysm/Seismic flyers hover safely over the new chasm.
                if flying_immune_damage > 0 {
                    if unit.shield() {
                        unit.set_shield(false);
                    } else if unit.frozen() {
                        unit.set_frozen(false);
                    } else {
                        let damage = flying_immune_damage as i8;
                        unit.hp -= damage;
                        if unit.is_player() {
                            result.mech_damage_taken += damage as i32;
                            if unit.hp <= 0 {
                                result.mechs_killed += 1;
                            }
                        } else if unit.is_enemy() {
                            result.enemy_damage_dealt += damage as i32;
                            if unit.hp <= 0 {
                                result.record_enemy_kill(
                                    unit_counts_for_mission_kill(board.mission_id.as_str(), unit)
                                );
                                enemy_died_idx = Some(uidx);
                            }
                        }
                    }
                }
            } else if acid || !unit.effectively_flying() {
                // Non-lethal env (1 dmg): bump-like — consumed by shield, ignores armor/ACID
                if unit.shield() {
                    unit.set_shield(false);
                } else if unit.frozen() {
                    unit.set_frozen(false);
                } else {
                    unit.hp -= 1;
                    if unit.is_player() {
                        result.mech_damage_taken += 1;
                        if unit.hp <= 0 { result.mechs_killed += 1; }
                    } else if unit.is_enemy() {
                        result.enemy_damage_dealt += 1;
                        if unit.hp <= 0 {
                            result.record_enemy_kill(
                                unit_counts_for_mission_kill(board.mission_id.as_str(), unit)
                            );
                            enemy_died_idx = Some(uidx);
                        }
                    }
                }
            }
            // else: flying, generic non-lethal env doesn't hit
            if acid && unit.hp > 0 {
                // Match the simulator's shared one-SpaceDamage ordering:
                // resolve damage first, then apply status to a surviving
                // occupant. A shield consumed or Frozen thawed by this same
                // hit therefore no longer blocks ACID.
                if unit.shield() || unit.frozen() {
                    acid_to_tile = true;
                } else {
                    acid_unit_idx = Some(uidx);
                }
            }
            if unit.hp > 0 && unit.hp < hp_before {
                crate::simulate::cancel_damaged_burrower_attack(unit);
            }
        }
    }
    if let Some(idx) = acid_unit_idx {
        board.units[idx].set_acid(true);
    }
    if acid_to_tile {
        let tile = board.tile_mut(x, y);
        if matches!(tile.terrain, Terrain::Water | Terrain::Ground | Terrain::Rubble) {
            tile.set_acid(true);
        }
    }
    if let Some(idx) = enemy_died_idx {
        crate::simulate::on_enemy_death(board, idx, result);
        // Boss / Blast Psion EXPLODE-on-death aura — env_danger kills bypass
        // apply_damage's death-explosion site (simulate.rs:788), so we
        // dispatch the explosion here when an aura source is alive. The
        // dying Vek has hp=0 already; explosion damages 4 adjacent tiles.
        // (sim v38 follow-up to v37 boss aura test failure.)
        if (board.blast_psion || board.boss_psion) && board.units[idx].receives_psion_aura() {
            crate::simulate::apply_death_explosion(board, x, y, result, 0);
        }
    }

    // Damage building if present (lethal destroys entirely, non-lethal does 1 HP)
    let idx = xy_to_idx(x, y);
    let is_unique = (board.unique_buildings & (1u64 << idx)) != 0;
    let mut lost = 0u8;
    let mut destroyed = false;
    {
        let tile = board.tile_mut(x, y);
        if !acid && tile.terrain == Terrain::Building && tile.building_hp > 0 {
            if tile.frozen() {
                tile.set_frozen(false);
                result.events.push(format!("building_thawed:{}:{}", x, y));
            } else {
                let dmg = if lethal { tile.building_hp } else { 1 };
                let old_hp = tile.building_hp;
                tile.building_hp = tile.building_hp.saturating_sub(dmg);
                lost = old_hp - tile.building_hp;
                result.buildings_damaged += lost as i32;
                result.grid_damage += lost as i32;
                if tile.building_hp == 0 {
                    tile.terrain = Terrain::Rubble;
                    result.buildings_lost += 1;
                    destroyed = true;
                }
            }
        }
    }
    if lost > 0 {
        let grid_loss = settle_building_grid_loss(
            board,
            idx,
            lost,
            destroyed,
            is_unique,
            DamageSource::Weapon,
        );
        result.grid_damage += (grid_loss as i32) - (lost as i32);
        board.grid_power = board.grid_power.saturating_sub(grid_loss);
        apply_auto_shield_after_building_damage(board, x, y, lost, result);
    }

    if board.tile(x, y).has_pod() {
        board.tile_mut(x, y).set_has_pod(false);
        result.events.push(format!("pod_destroyed_env:{}:{}", x, y));
    }

    // Env_Airstrike emits ordinary DAMAGE_DEATH SpaceDamage with no terrain
    // override. On an empty cracked Ground tile that direct hit opens a
    // chasm. Keep this mission-scoped: terrain-conversion environments and
    // Final Cave hazards carry different explicit terrain semantics, while an
    // occupied pawn absorbs the terrain portion of the hit.
    if board.mission_id == "Mission_Airstrike"
        && lethal
        && !occupied_by_alive_unit_at_start
        && board.tile(x, y).terrain == Terrain::Ground
        && board.tile(x, y).cracked()
    {
        let tile = board.tile_mut(x, y);
        tile.terrain = Terrain::Chasm;
        tile.set_cracked(false);
    }

    // Exact sand-island terrain hazards assign TERRAIN_HOLE to every marked
    // non-building tile. Cataclysm does so across its current column;
    // Seismic Activity does so along its selected cross path. The bridge's
    // per-tile flying-immunity bit distinguishes these chasm conversions from
    // pure DAMAGE_DEATH threats such as Lightning. Their native selection,
    // ordering, and future warning generation remain outside this bounded
    // current-marker simulation.
    if matches!(
        board.mission_id.as_str(),
        "Mission_Cataclysm" | "Mission_Crack"
    ) && lethal
        && flying_immune
        && !building_at_start
    {
        let tile = board.tile_mut(x, y);
        tile.terrain = Terrain::Chasm;
        tile.building_hp = 0;
        tile.set_cracked(false);
    }

    // Exact Env_Tides:ApplyEffect source sets iTerrain=TERRAIN_WATER on every
    // marked tile in the current lane. MarkBoard/ApplyEffect omit live
    // buildings, so do not apply the terrain override if a stale or synthetic
    // payload nevertheless marks one. Mountain tiles receive DAMAGE_DEATH
    // plus the same terrain override and therefore also become Water.
    if board.mission_id == "Mission_Tides"
        && lethal
        && flying_immune
        && !building_at_start
    {
        let tile = board.tile_mut(x, y);
        tile.terrain = Terrain::Water;
    }
}

#[derive(Clone, Copy)]
struct AttackDamageSnapshot {
    unit_hp: [i8; 16],
    building_hp: [u8; 64],
}

impl AttackDamageSnapshot {
    fn capture(board: &Board) -> Self {
        let mut unit_hp = [0i8; 16];
        for (idx, hp) in unit_hp
            .iter_mut()
            .enumerate()
            .take(board.unit_count as usize)
        {
            *hp = board.units[idx].hp;
        }
        let mut building_hp = [0u8; 64];
        for (idx, hp) in building_hp.iter_mut().enumerate() {
            let tile = board.tiles[idx];
            *hp = if tile.terrain == Terrain::Building {
                tile.building_hp
            } else {
                0
            };
        }
        Self { unit_hp, building_hp }
    }

    fn any_unit_or_building_damage(self, board: &Board) -> bool {
        (0..board.unit_count.min(16) as usize)
            .any(|idx| board.units[idx].hp < self.unit_hp[idx])
            || board
                .tiles
                .iter()
                .enumerate()
                .any(|(idx, tile)| tile.building_hp < self.building_hp[idx])
    }
}

fn apply_void_shocker_after_attack(
    board: &mut Board,
    attacker_idx: usize,
    before: AttackDamageSnapshot,
    result: &mut ActionResult,
) {
    let damage = board.void_shocker_damage;
    if damage == 0
        || before.any_unit_or_building_damage(board)
        || attacker_idx >= board.unit_count as usize
        || board.units[attacker_idx].hp <= 0
        || !board.units[attacker_idx].is_enemy()
        || board.units[attacker_idx].void_shock_immune()
    {
        return;
    }

    let (uid, x, y) = {
        let attacker = &board.units[attacker_idx];
        (attacker.uid, attacker.x, attacker.y)
    };
    apply_damage(board, x, y, damage, result, DamageSource::Weapon);
    result.events.push(format!(
        "void_shocker:{}:{}:{}:{}",
        uid, x, y, damage
    ));
}

fn apply_env_danger_board(board: &mut Board, result: &mut ActionResult) {
    if board.mission_id == "Mission_Final_Cave"
        && matches!(
            board.env_final_cave_mode,
            FINAL_CAVE_ROCKS | FINAL_CAVE_LAVA
        )
        && !board.env_final_cave_locations.is_empty()
    {
        apply_mission_final_cave(board, result);
        return;
    }

    if board.mission_id == "Mission_Final"
        && matches!(board.env_volcano_mode, VOLCANO_ROCKS | VOLCANO_LAVA)
        && board.env_volcano_count > 0
    {
        apply_mission_final_volcano(board, result);
        return;
    }

    let flying_immune_damage = if board.mission_id == "Mission_Tides" { 1 } else { 0 };
    // Legacy Mission_Satellite markers have enough timing/displacement nuance
    // that they are not reliable enemy-kill evidence. Exact v377 payloads also
    // carry the living queued SatelliteRocket, which proves the source-defined
    // cardinal DAMAGE_DEATH: queued Vek attack first, then kill only an enemy
    // still occupying one of those exact exhaust tiles.
    let has_exact_satellite_launch = board.mission_id == "Mission_Satellite"
        && board.units[..board.unit_count as usize].iter().any(|unit| {
            unit.hp > 0
                && unit.team == Team::Player
                && unit.type_name_str() == "SatelliteRocket"
                && unit.satellite_launch_queued()
        });
    let skip_enemy_units = board.mission_id == "Mission_Satellite"
        && !has_exact_satellite_launch;
    for tile_idx in 0usize..64 {
        if board.env_danger & (1u64 << tile_idx) == 0 { continue; }
        let (x, y) = idx_to_xy(tile_idx);
        let bit = 1u64 << tile_idx;
        let lethal = board.env_danger_kill & bit != 0;
        let flying_immune = lethal && (board.env_danger_flying_immune & bit != 0);
        let acid = board.env_danger_acid & bit != 0;
        apply_env_danger(
            board,
            x,
            y,
            lethal,
            flying_immune,
            acid,
            flying_immune_damage,
            skip_enemy_units,
            result,
        );
    }
}

/// Ignite a unit that survives newly-created Lava. Terrain fire is blocked by
/// Shield without consuming it, unfreezes a surviving target, and honors the
/// same intrinsic/passive immunities as ordinary Lava landing.
fn apply_volcano_lava_fire(board: &mut Board, unit_idx: usize) {
    let unit = &board.units[unit_idx];
    let target_is_immune_vek = board.fire_psion
        && unit.receives_psion_aura()
        && unit.type_name_str() != "Jelly_Fire1";
    let flame_shielded_mech = board.flame_shielding
        && unit.is_player()
        && unit.is_mech();
    if unit.hp <= 0
        || unit.shield()
        || !unit.can_catch_fire()
        || target_is_immune_vek
        || flame_shielded_mech
    {
        return;
    }
    let unit = &mut board.units[unit_idx];
    unit.set_frozen(false);
    unit.set_fire(true);
}

/// Apply one zero-damage `iTerrain=TERRAIN_LAVA` effect from Env_Volcano.
/// Ordinary grounded units drown; Massive and effectively-flying units
/// survive and acquire Lava's fire status. The terrain assignment itself is
/// permanent and bypasses Shield/Frozen just like other deadly terrain.
fn apply_volcano_lava(
    board: &mut Board,
    x: u8,
    y: u8,
    result: &mut ActionResult,
) {
    {
        let tile = board.tile_mut(x, y);
        tile.terrain = Terrain::Lava;
        tile.building_hp = 0;
        tile.population = 0;
        tile.set_on_fire(false);
        tile.set_smoke(false);
        tile.set_acid(false);
        tile.set_frozen(false);
        tile.set_cracked(false);
        tile.set_has_pod(false);
        tile.set_freeze_mine(false);
        tile.set_old_earth_mine(false);
        tile.set_repair_platform(false);
        tile.set_shield(false);
        tile.set_grass(false);
        tile.conveyor_dir = -1;
    }

    let Some(unit_idx) = board.unit_at(x, y) else {
        return;
    };
    let effectively_flying = board.units[unit_idx].effectively_flying();
    let massive = board.units[unit_idx].massive();
    if !effectively_flying && !massive {
        let hp_before = board.units[unit_idx].hp.max(0) as i32;
        if board.units[unit_idx].is_enemy() {
            result.enemy_damage_dealt += hp_before;
        } else if board.units[unit_idx].is_player() {
            result.mech_damage_taken += hp_before;
        }
        crate::simulate::finish_instant_unit_death(
            board,
            unit_idx,
            result,
            x,
            y,
        );
    } else {
        apply_volcano_lava_fire(board, unit_idx);
    }
}

/// Apply one `DAMAGE_DEATH + iFire=1` volcanic projectile. Rocks use the
/// generic deadly-threat bookkeeping, then settle the source-defined fire and
/// full-mountain destruction on the resulting tile.
fn apply_volcano_rock(
    board: &mut Board,
    x: u8,
    y: u8,
    result: &mut ActionResult,
) {
    let was_mountain = board.tile(x, y).terrain == Terrain::Mountain;
    apply_env_danger(board, x, y, true, false, false, 0, false, result);

    if was_mountain {
        let tile = board.tile_mut(x, y);
        tile.terrain = Terrain::Rubble;
        tile.building_hp = 0;
        tile.set_cracked(false);
        result.events.push(format!(
            "achievement_miner_inconvenience:mountain_damage:{}:{}:1",
            x, y
        ));
    }

    let terrain = board.tile(x, y).terrain;
    if terrain == Terrain::Ice {
        let tile = board.tile_mut(x, y);
        tile.terrain = Terrain::Water;
        tile.set_on_fire(false);
        tile.set_smoke(false);
        tile.set_cracked(false);
    } else if matches!(
        terrain,
        Terrain::Ground | Terrain::Sand | Terrain::Forest | Terrain::Rubble | Terrain::Fire
    ) {
        let tile = board.tile_mut(x, y);
        if matches!(tile.terrain, Terrain::Sand | Terrain::Forest | Terrain::Fire) {
            tile.terrain = Terrain::Ground;
        }
        tile.set_smoke(false);
        tile.set_on_fire(true);
    }
}

fn apply_mission_final_volcano(board: &mut Board, result: &mut ActionResult) {
    let count = board.env_volcano_count.min(4) as usize;
    // Copy the tiny order array because death effects can mutably borrow Board.
    let locations = board.env_volcano_locations;
    for &tile_idx in locations.iter().take(count) {
        if tile_idx >= 64 {
            continue;
        }
        let (x, y) = idx_to_xy(tile_idx as usize);
        if board.env_volcano_mode == VOLCANO_LAVA {
            apply_volcano_lava(board, x, y, result);
        } else {
            apply_volcano_rock(board, x, y, result);
        }
    }
}

/// Apply the exact current Mission_Final_Cave Env_Final selection. Both modes
/// use DAMAGE_DEATH and therefore kill effectively-flying, Massive, Shielded,
/// and Frozen pawns. Rocks replace the tile with Road; tentacles replace it
/// with Lava. Selection RNG remains native and is never generated here.
fn apply_mission_final_cave(board: &mut Board, result: &mut ActionResult) {
    let locations = board.env_final_cave_locations.clone();
    let mode = board.env_final_cave_mode;
    for tile_idx in locations {
        if tile_idx >= 64 {
            continue;
        }
        let (x, y) = idx_to_xy(tile_idx as usize);
        apply_env_danger(board, x, y, true, false, false, 0, false, result);

        let tile = board.tile_mut(x, y);
        tile.terrain = if mode == FINAL_CAVE_ROCKS {
            Terrain::Ground
        } else {
            Terrain::Lava
        };
        tile.building_hp = 0;
        tile.population = 0;
        tile.set_cracked(false);
        tile.set_has_pod(false);
        tile.set_grass(false);
        tile.set_freeze_mine(false);
        tile.set_old_earth_mine(false);
        tile.set_repair_platform(false);
        tile.conveyor_dir = -1;
        if tile.terrain == Terrain::Lava {
            tile.set_on_fire(false);
        }
    }
}

/// Resolve the source-defined tail of a queued Satellite launch.
///
/// `Rocket_Launch:GetSkillEffect` queues four cardinal exhaust deaths and then
/// calls `FlyAway()` on the center pawn. Existing live regressions establish
/// that queued Vek attacks land before this effect. Compacting the fixed unit
/// array here mirrors `Board:GetPawn(id) == nil` without inventing an off-board
/// living coordinate or misclassifying a successful launch as a death.
fn resolve_mission_satellite_flyaways(board: &mut Board) {
    if board.mission_id != "Mission_Satellite" {
        return;
    }

    let old_count = board.unit_count as usize;
    let mut write = 0usize;
    for read in 0..old_count {
        let unit = board.units[read];
        let launched = unit.hp > 0
            && unit.team == Team::Player
            && unit.type_name_str() == "SatelliteRocket"
            && unit.satellite_launch_queued();
        if launched {
            for &(dx, dy) in &DIRS {
                let x = unit.x as i8 + dx;
                let y = unit.y as i8 + dy;
                if !(0..8).contains(&x) || !(0..8).contains(&y) {
                    continue;
                }
                let bit = 1u64 << xy_to_idx(x as u8, y as u8);
                board.env_danger &= !bit;
                board.env_danger_kill &= !bit;
                board.env_danger_flying_immune &= !bit;
                board.env_danger_acid &= !bit;
            }
            continue;
        }
        if write != read {
            board.units[write] = unit;
        }
        write += 1;
    }
    for idx in write..old_count {
        board.units[idx] = Unit::default();
    }
    board.unit_count = write as u8;
}

/// Apply Mission_Terratide's warned Sandstorm lane as smoke only.
///
/// The live `Env_Terratide` subclasses `Env_Tides`, but its `ApplyEffect`
/// writes `SpaceDamage.iSmoke = 1` instead of damage or terrain conversion.
/// Run this before the queued-attack smoke latch so Vek caught by the wave
/// lose their attacks for this enemy phase. `place_smoke` also mirrors normal
/// smoke behavior for fire removal, healing-smoke passives, and web release.
fn apply_env_smoke_board(board: &mut Board) {
    let mut smoke_bits = board.env_smoke;
    // Board:IsEnvironmentDanger mirrors Env_Tides:MarkBoard(), which omits a
    // Terratide warning marker when the current lane crosses a building.
    // Env_Tides:ApplyEffect() does not make that exception for
    // NewTerrain=TERRAIN_SAND: every tile in the lane receives iSmoke=1.
    // Reconstruct the complete effect row here while retaining env_smoke as
    // the bridge-visible warning mask used by turn projection/serialization.
    if board.mission_id == "Mission_Terratide" {
        let mut warned_rows = 0u16;
        if board.env_tides_planned == Some(true) {
            // Env_Terratide maps the source Index to y = 7 - Index. Index 8
            // is terminal/off-board and therefore has no current effect row.
            if let Some(index) = board.env_tides_index {
                if index <= 7 {
                    warned_rows |= 1u16 << (7 - index);
                }
            }
        } else if board.env_tides_planned.is_none() {
            // Legacy payloads have no Planned scalar; retain the visible-mask
            // behavior. Explicit false is authoritative and suppresses it.
            let mut warned = smoke_bits;
            while warned != 0 {
                let tile_idx = warned.trailing_zeros() as usize;
                warned &= warned - 1;
                let (_, y) = idx_to_xy(tile_idx);
                warned_rows |= 1u16 << y;
            }
        }
        smoke_bits = 0;
        for y in 0u8..8 {
            if warned_rows & (1u16 << y) == 0 {
                continue;
            }
            for x in 0u8..8 {
                smoke_bits |= 1u64 << xy_to_idx(x, y);
            }
        }
    }
    while smoke_bits != 0 {
        let tile_idx = smoke_bits.trailing_zeros() as usize;
        smoke_bits &= smoke_bits - 1;
        let (x, y) = idx_to_xy(tile_idx);
        place_smoke(board, x, y);
    }
}

/// Return the current spawn markers occupied by a living pawn at emergence.
///
/// Call this after enemy attacks and before spawn-blocking damage. A marker
/// persists even if that damage kills or thaws the pawn that blocked it.
pub fn persisting_spawn_points(
    board: &Board,
    spawn_points: &[(u8, u8)],
) -> Vec<(u8, u8)> {
    spawn_points.iter()
        .copied()
        .filter(|&(sx, sy)| board.unit_at(sx, sy).is_some())
        .collect()
}

/// Apply spawn blocking damage: units standing on spawn tiles take 1 damage
/// when Vek try to emerge. Damage bypasses armor and ACID (bump-like damage)
/// but is consumed by shield. Fires after enemy attacks, before next player turn.
pub fn apply_spawn_blocking(
    board: &mut Board,
    spawn_points: &[(u8, u8)],
) -> ActionResult {
    let mut result = ActionResult::default();
    for &(sx, sy) in spawn_points {
        if let Some(idx) = board.unit_at(sx, sy) {
            let stabilized_player_mech = board.stabilizers
                && board.units[idx].is_player()
                && board.units[idx].is_mech();
            let unit = &mut board.units[idx];
            if unit.hp <= 0 { continue; }
            result.spawns_blocked += 1;
            if stabilized_player_mech {
                continue;
            }
            if unit.shield() {
                unit.set_shield(false);
                continue;
            }
            if unit.frozen() {
                unit.set_frozen(false);
                continue;
            }
            // Bump-class damage: ignores armor/ACID. Route through apply_damage
            // so multi-tile HP mirroring + future dam-flood trigger run.
            let mut tmp_result = ActionResult::default();
            apply_damage(board, sx, sy, 1, &mut tmp_result, DamageSource::Bump);
            result.merge(&tmp_result);
        }
    }
    result
}

/// Mission_Reactivation thaw: at the start of each enemy turn, the Lua
/// `Mission_Reactivation:NextTurn` thaws up to 2 frozen pawns from its
/// `self.Enemies` roster (see scripts/missions/snow/mission_reactivation.lua
/// lines 50-66). The thawed pawns DO NOT have a queued attack this turn
/// (they were frozen, so they never queued one) but become attackers on
/// the next player turn.
///
/// The simulator's enemy phase otherwise treats `frozen` as a permanent
/// inert state (`if enemy.frozen() { continue; }` skip). Without this
/// hook, the solver assumes the 4-7 frozen Vek placed at mission start
/// stay inert forever, and `enemy_hp_remaining` / next-turn threat
/// scoring under-counts the looming wave. That mis-pricing was the
/// proximate cause of the 4-grid leak on Lifeless Basin (Mission_Reactivation)
/// in run 20260425_185532_218 / 2026-04-28.
///
/// Selection is deterministic for solver reproducibility: thaw the two
/// LOWEST uid frozen enemies. The real game uses `random_removal` over
/// `self.Enemies`, but a 1-turn-horizon search just needs the COUNT to be
/// right so the eval term sees the post-thaw enemy_hp_remaining.
fn simulate_reactivation_thaw(board: &mut Board) {
    if board.mission_id != "Mission_Reactivation" { return; }
    let mut thawed = 0u8;
    // Stable iteration: by uid ascending so the same two pawns thaw on
    // every solve of the same board (the Python verifier compares the
    // same pair).
    let mut order: Vec<usize> = (0..board.unit_count as usize)
        .filter(|&i| {
            let u = &board.units[i];
            u.is_enemy() && u.hp > 0 && u.frozen()
        })
        .collect();
    order.sort_by_key(|&i| board.units[i].uid);
    for i in order {
        if thawed >= 2 { break; }
        board.units[i].set_frozen(false);
        thawed += 1;
    }
}

fn active_conveyor_mission(board: &Board) -> bool {
    matches!(board.mission_id.as_str(), "Mission_Belt" | "Mission_BeltRandom")
}

/// Conveyor effect: on active conveyor missions, all live units standing on
/// conveyor tiles are pushed one tile in the belt direction before Vek attacks
/// resolve. Some Detritus maps store decorative conveyor sprites in save data
/// without running an enemy-phase belt environment, so gate on mission id.
fn simulate_conveyor_belts(board: &mut Board, result: &mut ActionResult) {
    if !active_conveyor_mission(board) {
        return;
    }
    let mut moves: Vec<(usize, i16, u16, u8, u8)> = Vec::new();
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.hp <= 0 { continue; }
        let dir = board.tile(u.x, u.y).conveyor_dir;
        if !(0i8..=3i8).contains(&dir) { continue; }
        let (dx, dy) = DIRS[dir as usize];
        let projection = u.x as i16 * dx as i16 + u.y as i16 * dy as i16;
        moves.push((dir as usize, projection, u.uid, u.x, u.y));
    }

    // Front-to-back within each direction prevents same-direction belt chains
    // from bumping into units that should move out of the way this tick.
    moves.sort_by(|a, b| {
        a.0.cmp(&b.0)
            .then_with(|| b.1.cmp(&a.1))
            .then_with(|| a.2.cmp(&b.2))
    });

    let mut moved_uids: Vec<u16> = Vec::new();
    for (dir, _projection, uid, x, y) in moves {
        let Some(idx) = (0..board.unit_count as usize)
            .find(|&i| board.units[i].uid == uid)
        else {
            continue;
        };
        let u = &board.units[idx];
        if u.hp <= 0 || u.x != x || u.y != y { continue; }
        let (dx, dy) = DIRS[dir];
        let nx = x as i8 + dx;
        let ny = y as i8 + dy;
        if in_bounds(nx, ny) {
            let nxu = nx as u8;
            let nyu = ny as u8;
            if let Some(blocker_idx) = board.unit_at(nxu, nyu) {
                let blocker_uid = board.units[blocker_idx].uid;
                if blocker_idx != idx && moved_uids.contains(&blocker_uid) {
                    continue;
                }
            }
        }
        apply_environment_push(board, x, y, dir, result);
        let moved = board.units[idx].x != x || board.units[idx].y != y;
        if moved {
            moved_uids.push(uid);
        }
    }
}

/// Mission_Wind pushes units standing on marked rows before Vek attacks.
///
/// The bridge stores affected tiles in `env_wind` and the live Lua `WindDir`
/// in `env_wind_dir`. Precompute initially occupied wind tiles so a unit
/// pushed into another marked tile is not hit twice during one gust.
fn simulate_mission_wind(board: &mut Board, result: &mut ActionResult) {
    if board.env_wind == 0 || !(0..=3).contains(&board.env_wind_dir) {
        return;
    }
    let dir = board.env_wind_dir as usize;
    let mut targets: Vec<(u8, u8)> = Vec::new();
    match dir {
        3 => {
            for y in 0..8u8 {
                for x in 0..8u8 {
                    if board.env_wind & (1u64 << xy_to_idx(x, y)) != 0
                        && board.unit_at(x, y).is_some()
                    {
                        targets.push((x, y));
                    }
                }
            }
        }
        1 => {
            for y in 0..8u8 {
                for x in (0..8u8).rev() {
                    if board.env_wind & (1u64 << xy_to_idx(x, y)) != 0
                        && board.unit_at(x, y).is_some()
                    {
                        targets.push((x, y));
                    }
                }
            }
        }
        2 => {
            for x in 0..8u8 {
                for y in 0..8u8 {
                    if board.env_wind & (1u64 << xy_to_idx(x, y)) != 0
                        && board.unit_at(x, y).is_some()
                    {
                        targets.push((x, y));
                    }
                }
            }
        }
        0 => {
            for x in 0..8u8 {
                for y in (0..8u8).rev() {
                    if board.env_wind & (1u64 << xy_to_idx(x, y)) != 0
                        && board.unit_at(x, y).is_some()
                    {
                        targets.push((x, y));
                    }
                }
            }
        }
        _ => return,
    }

    for (x, y) in targets {
        if let Some(idx) = board.unit_at(x, y) {
            if board.units[idx].hp > 0 {
                apply_environment_push(board, x, y, dir, result);
            }
        }
    }
}

fn clear_pre_attack_dead_enemy_wrecks(board: &mut Board) {
    for i in 0..board.unit_count as usize {
        let u = &mut board.units[i];
        if u.hp <= 0 && u.is_enemy() {
            u.x = 8;
            u.y = 8;
        }
    }
}

fn hatch_spawn_destination(board: &Board, x: u8, y: u8) -> Option<(u8, u8)> {
    // Live HQ capture: a WebbEgg at E6 hatched onto adjacent F6, destroying a
    // 2-HP building. The Lua skill queues `sPawn` at the occupied egg tile, and
    // the engine's hidden fallback picked bridge `(x, y-1)` first.
    let hatch_dirs: [(i8, i8); 4] = [(0, -1), (1, 0), (0, 1), (-1, 0)];
    for &(dx, dy) in &hatch_dirs {
        let nx = x as i8 + dx;
        let ny = y as i8 + dy;
        if !in_bounds(nx, ny) {
            continue;
        }
        let hx = nx as u8;
        let hy = ny as u8;
        if board.unit_at(hx, hy).is_some() || board.wreck_at(hx, hy) {
            continue;
        }
        let tile = board.tile(hx, hy);
        match tile.terrain {
            Terrain::Building if tile.building_hp > 0 && !tile.shield() => return Some((hx, hy)),
            Terrain::Ground | Terrain::Sand | Terrain::Forest
            | Terrain::Rubble | Terrain::Fire | Terrain::Ice => return Some((hx, hy)),
            _ => {}
        }
    }
    None
}

/// Resolve the Mine-Bot's bespoke queued setup skill.
///
/// `SnowmineAtk1` ignores Smoke. If the pawn is grappled, the shipped Lua
/// returns an empty effect; otherwise a non-self target leaves a Freeze Mine
/// on the origin tile and moves the pawn to its queued destination without
/// dealing damage. The destination was path-validated when the game queued
/// the skill, so this phase only needs to reject a target that became occupied
/// or invalid while the player acted.
fn simulate_snowmine_attack(
    board: &mut Board,
    enemy_idx: usize,
    result: &mut ActionResult,
) {
    let (qtx, qty) = {
        let enemy = &board.units[enemy_idx];
        (enemy.queued_target_x, enemy.queued_target_y)
    };
    if !in_bounds(qtx, qty) {
        return;
    }
    simulate_snowmine_setup(board, enemy_idx, (qtx as u8, qty as u8), result);
}

/// Simulate all enemy attacks on the post-mech-action board.
/// Processes in UID order and returns the accumulated outcome from fire,
/// environment, enemy attacks, and other enemy-phase effects.
///
/// `original_positions`: maps unit index -> (orig_x, orig_y) for direction/range checks.
pub fn simulate_enemy_attacks(
    board: &mut Board,
    original_positions: &[(u8, u8); 16],
    weapons: &WeaponTable,
) -> ActionResult {
    // Passive_PlayerTurnShield is explicitly limited to the player turn.
    // From this boundary onward, queued Vek, environments, fire, and spawn
    // blocking must damage mechs normally.
    board.networked_shielding = false;

    // Mission_Reactivation: thaw 2 frozen Vek at start of enemy phase.
    // Must run BEFORE the frozen-skip in the attack loop so newly-thawed
    // pawns are reflected in post-enemy state (they don't attack this
    // turn — no queued attack — but the eval scores their HP correctly).
    simulate_reactivation_thaw(board);

    let mut buildings_destroyed = 0;
    let mut result = ActionResult::default();
    flush_deferred_bump_grid_debt(board, &mut result);

    // Fire tick: burning units take 1 damage before attacks
    // Flame Shielding: player mechs immune to fire
    // Source-defined fire immunity: defensive skip. The fire-apply hooks never
    // set FIRE on Ariadne or a Supply Train body, so this branch only matters
    // when stale bridge/status data carries FIRE into the projection.
    for i in 0..board.unit_count as usize {
        if board.units[i].fire() && board.units[i].hp > 0 && !board.units[i].burrowed() {
            if board.flame_shielding && board.units[i].is_player() && board.units[i].is_mech() {
                continue; // mechs immune to fire with Flame Shielding
            }
            if !board.units[i].can_catch_fire() {
                // Fire-immune pawns clear stale FIRE without taking the tick.
                board.units[i].set_fire(false);
                continue;
            }
            if board.units[i].type_name_str() == "Dam_Pawn" {
                // Live Mission_Dam can show the neutral dam burning at 1 HP
                // on the final reward panel while the objective still fails.
                // Do not let the generic enemy-phase tick destroy it and
                // preempt queued Vek attacks with a phantom flood.
                continue;
            }
            // Fire Psion (LEADER_FIRE, Jelly_Fire1): all Vek immune to fire
            // damage while alive. The Fire Psion itself is exempt from this
            // immunity per the standard "aura source isn't subject to its
            // own aura" pattern, matching how Soldier Psion doesn't get
            // its own +1 HP buff. Defensively clear the FIRE flag so a
            // stale status doesn't tick once the Psion dies — the on-death
            // cleanup re-enables fire damage normally.
            if board.fire_psion && board.units[i].receives_psion_aura()
                && board.units[i].type_name_str() != "Jelly_Fire1"
            {
                continue;
            }
            let x = board.units[i].x;
            let y = board.units[i].y;
            apply_damage(board, x, y, 1, &mut result, DamageSource::Fire);
        }
    }

    // Storm Generator: enemies in smoke take the passive's effective damage.
    if board.storm_generator_damage > 0 {
        let damage = board.storm_generator_damage;
        for i in 0..board.unit_count as usize {
            if board.units[i].is_enemy()
                && board.units[i].hp > 0
                && !board.units[i].burrowed()
            {
                let x = board.units[i].x;
                let y = board.units[i].y;
                if board.tile(x, y).smoke() {
                apply_damage(board, x, y, damage, &mut result, DamageSource::Weapon);
                }
            }
        }
    }

    // Fire tick Psion kill cleanup: if a Psion died from fire, clear its flag
    if board.blast_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Explode1" && board.units[i].hp > 0);
        if !alive { board.blast_psion = false; }
    }
    if board.armor_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Armor1" && board.units[i].hp > 0);
        if !alive {
            board.armor_psion = false;
            for i in 0..board.unit_count as usize {
                if board.units[i].is_enemy() {
                    board.units[i].flags.set(UnitFlags::ARMOR, false);
                }
            }
        }
    }
    if board.soldier_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Health1" && board.units[i].hp > 0);
        if !alive {
            board.soldier_psion = false;
            // Only revert the +1 max_hp if the Boss Psion isn't ALSO providing
            // the same HEALTH buff. When boss_psion is alive the buff stays.
            if !board.boss_psion {
                for i in 0..board.unit_count as usize {
                    let tname = board.units[i].type_name_str();
                    if board.units[i].receives_psion_aura() && board.units[i].hp > 0
                        && tname != "Jelly_Health1"
                        && tname != "Jelly_Boss"
                    {
                        board.units[i].max_hp -= 1;
                        board.units[i].hp -= 1;
                    }
                }
            }
        }
    }
    if board.regen_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Regen1" && board.units[i].hp > 0);
        if !alive { board.regen_psion = false; }
    }
    if board.tyrant_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Lava1" && board.units[i].hp > 0);
        if !alive { board.tyrant_psion = false; }
    }
    // Psion Abomination (Jelly_Boss): combined HEALTH+REGEN+EXPLODE aura.
    // On death, also reverse the +1 max_hp on remaining non-boss, non-soldier
    // Vek — but ONLY if the Soldier Psion isn't also alive (the buff applies
    // once total, so we keep it as long as one source remains).
    if board.boss_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Boss" && board.units[i].hp > 0);
        if !alive {
            board.boss_psion = false;
            if !board.soldier_psion {
                for i in 0..board.unit_count as usize {
                    let tname = board.units[i].type_name_str();
                    if board.units[i].receives_psion_aura() && board.units[i].hp > 0
                        && tname != "Jelly_Health1"
                        && tname != "Jelly_Boss"
                    {
                        board.units[i].max_hp -= 1;
                        board.units[i].hp -= 1;
                    }
                }
            }
        }
    }
    if board.boost_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Boost1" && board.units[i].hp > 0);
        if !alive { board.boost_psion = false; }
    }
    if board.fire_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Fire1" && board.units[i].hp > 0);
        if !alive { board.fire_psion = false; }
    }
    if board.spider_psion {
        let alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Spider1" && board.units[i].hp > 0);
        if !alive { board.spider_psion = false; }
    }

    // Blood Psion regen: heal all non-Psion Vek by 1 (after fire, before attacks).
    // Also fires for the Psion Abomination (Jelly_Boss), which has the LEADER_BOSS
    // composite aura including REGEN. The boss itself is excluded from the heal
    // (it has its own HP), as is the Blood Psion (which never heals itself).
    if board.regen_psion || board.boss_psion {
        for i in 0..board.unit_count as usize {
            let u = &mut board.units[i];
            let tname = u.type_name_str();
            if u.receives_psion_aura() && u.hp > 0
                && tname != "Jelly_Regen1"
                && tname != "Jelly_Boss"
            {
                if u.hp < u.max_hp {
                    u.hp += 1;
                }
            }
        }
    }
    clear_pre_attack_dead_enemy_wrecks(board);

    // Environment danger (air strikes, lightning, etc.) usually fires BEFORE
    // Vek attacks. Some mission hazards resolve after queued attacks, so those
    // are deferred below until after the attack loop.
    let env_after_attacks = matches!(
        board.mission_id.as_str(),
        "Mission_Tides" | "Mission_Satellite"
    );
    if board.env_danger != 0 && !env_after_attacks {
        apply_env_danger_board(board, &mut result);
        clear_pre_attack_dead_enemy_wrecks(board);
    }

    // Terratide is a smoke wave, not a damaging tide. It resolves before
    // queued Vek attacks; the smoke-cancellation latch below therefore sees
    // newly smoked attackers and suppresses their current attack.
    if board.env_smoke != 0
        || (board.mission_id == "Mission_Terratide"
            && board.env_tides_planned == Some(true)
            && board.env_tides_index.is_some())
    {
        apply_env_smoke_board(board);
    }

    // Ice Storm freeze (sim v25). Fires at start of enemy turn — same step as
    // env_danger per Lua source: Env_SnowStorm.Instant=true, ApplyEffect()
    // queues SpaceDamage with iFrozen=1 iDamage=0 for all 9 marked tiles in
    // a single batch (mission_snowstorm.lua:28-53). Frozen units have HP
    // protected from the upcoming Vek attacks (the attack loop's
    // `if e.frozen() || e.web() { continue; }` skip). Buildings and mountains
    // receive the same frozen layer because the source does not exclude them.
    //
    // Order vs env_danger: env_danger fires first so Lightning kills the
    // unit before Ice Storm freezes its corpse. In practice Ice Storm and
    // Lightning don't co-exist on the same mission (they're mutually exclusive
    // env classes), so the order is a defensive convention rather than a
    // tested invariant.
    if board.env_freeze != 0 {
        for tile_idx in 0usize..64 {
            if board.env_freeze & (1u64 << tile_idx) == 0 { continue; }
            let (x, y) = idx_to_xy(tile_idx);
            if let Some(uidx) = board.unit_at(x, y) {
                let unit = &mut board.units[uidx];
                if unit.hp > 0 {
                    if unit.shield() {
                        // Native shield behavior blocks the negative Frozen
                        // status and consumes the shield even at iDamage=0.
                        unit.set_shield(false);
                    } else if !unit.frozen() {
                        // Already-frozen → idempotent (no double-flag); only
                        // freshly-applied freeze sets the flag.
                        unit.set_fire(false);
                        unit.set_frozen(true);
                    }
                }
            }
            let tile = board.tile_mut(x, y);
            if matches!(tile.terrain, Terrain::Building | Terrain::Mountain)
                && tile.building_hp > 0
            {
                if tile.shield() {
                    tile.set_shield(false);
                } else {
                    tile.set_on_fire(false);
                    tile.set_frozen(true);
                }
            }
            // Empty ground and other terrain do not carry a frozen layer.
        }
    }

    // Standard belt missions resolve conveyors before Vek attacks, so moved
    // Vek re-aim from their conveyor-shifted tile using the original queued
    // direction below. Mission_BeltRandom's environment event can appear after
    // queued attacks in the displayed attack order, so its belt tick is
    // applied after the attack loop.
    if board.mission_id == "Mission_Belt" {
        simulate_conveyor_belts(board, &mut result);
    }
    clear_pre_attack_dead_enemy_wrecks(board);

    // Mission_Wind rows are push lanes, not damage tiles. The gust resolves
    // before attacks; Vek then fire from their pushed tile while preserving
    // the original queued direction.
    simulate_mission_wind(board, &mut result);
    clear_pre_attack_dead_enemy_wrecks(board);

    // Egg hatch step: transform any surviving spider/spiderling egg into
    // its hatched live unit (sim v22/v115). Runs AFTER fire tick + env_danger
    // so eggs killed by those still die without hatching, but BEFORE the
    // attack loop so the hatched Spiderling participates in the unit
    // census the loop snapshots. The fresh hatchling has no queued
    // attack on its hatch turn (real game: bite happens turn after
    // hatch), so we clear queued_target + HAS_QUEUED_ATTACK so the
    // attack-loop's phantom-attack guard `continue`s cleanly without
    // applying conservative damage.
    //
    // Hatch table (verified against game source 2026-04-25, sim v23):
    //   WebbEgg1       → Spiderling1   (Hive Arachnid Spider laying egg)
    //   SpiderlingEgg1 → Spiderling1   (defensive: not in vanilla pawns.lua
    //                                   but registered in known_types.json
    //                                   from a prior research cycle —
    //                                   probably a campaign/finale variant
    //                                   or a bridge-side alias; mapping to
    //                                   Spiderling1 matches what the only
    //                                   known WebeggHatch skill produces)
    // Source citations:
    //   pawns.lua:1022 Spider1.SkillList = {"SpiderAtk1"}, Health=2
    //   pawns.lua:1038 Spider2.SkillList = {"SpiderAtk2"}, Health=4 (Alpha)
    //   pawns.lua:1059 WebbEgg1.SkillList = {"WebeggHatch1"}, Health=1
    //   pawns.lua:1078 Spiderling1.MoveSpeed=3, SkillList={"SpiderlingAtk1"}
    //   weapons_enemy.lua:758 SpiderAtk1.MyPawn = "WebbEgg1"
    //   weapons_enemy.lua:815 SpiderAtk2 = SpiderAtk1:new{...} — does NOT
    //     override MyPawn, so Spider2 (the Alpha) ALSO lays a WebbEgg1.
    //     Confirmed by localization: SpiderAtk2_Description = "Throw a
    //     sticky egg that hatches into a Spiderling." (regular Spiderling,
    //     singular).
    //   weapons_enemy.lua:830 WebeggHatch1.SpiderType = "Spiderling1"
    // CRITICAL: there is NO `WebbEgg2` pawn in the game. The pre-v23 sim
    // v22 hatch table claimed Alpha eggs were a distinct `WebbEgg2`
    // hatching to `Spiderling2` (a 2-dmg Alpha Spiderling). That was
    // bestiary-doc fiction — the bridge will never surface a `WebbEgg2`
    // type_name on a vanilla board. Removing the dead branch.
    //
    // Other "*Egg" types fall through unchanged — the egg-skip below
    // catches them so they never phantom-attack.
    //
    // Why this matters even though it's a 1-turn-deep solver: the
    // simulator emits `predicted_post_enemy_state` which `verify_action`
    // diffs against the actual post-enemy board. Pre-fix, the predicted
    // state showed a WebbEgg at hatch position; the live game showed a
    // Spiderling — every spider-bonus mission produced a desync row in
    // failure_db. Surfaced by the 20260425_185532_218 Archive run, where
    // 2-3 eggs piled up over turns 2-3 and were predicted as eggs but
    // played as a Spiderling wall on turns 3-4. A later Hard HQ capture
    // showed the engine's `sPawn` fallback placing the hatchling adjacent
    // to the occupied egg tile; if that destination is a live building, it
    // is destroyed before the Spiderling appears there.
    for i in 0..board.unit_count as usize {
        if board.units[i].hp <= 0 { continue; }
        let new_type: Option<&'static str> = {
            let name = board.units[i].type_name_str();
            // Per game source: ALL spider eggs in vanilla hatch into
            // Spiderling1 (1 HP, 1 dmg melee). See hatch-table comment
            // above. WebbEgg2 is bestiary-doc fiction; SpiderlingEgg1 is a
            // defensive alias kept because data/known_types.json has it.
            if name == "WebbEgg1" || name == "SpiderlingEgg1" {
                Some("Spiderling1")
            } else {
                None
            }
        };
        if let Some(target_type) = new_type {
            let hatch_to = {
                let u = &board.units[i];
                hatch_spawn_destination(board, u.x, u.y)
            };
            if let Some((hx, hy)) = hatch_to {
                let hp = board.tile(hx, hy).building_hp;
                if hp > 0 {
                    apply_damage(board, hx, hy, hp, &mut result, DamageSource::Weapon);
                }
                if board.tile(hx, hy).building_hp == 0 {
                    board.units[i].x = hx;
                    board.units[i].y = hy;
                }
            }
            let u = &mut board.units[i];
            u.set_type_name(target_type);
            // Spiderling stats (data/ref_vek_bestiary.md, pawn_stats.py).
            // 1 HP minor unit with melee bite. Eggs were also 1HP so
            // hp/max_hp don't change here.
            u.move_speed = 3;
            u.base_move = 3;
            // Bind weapon so a downstream call site that looks at
            // `unit.weapon` (rare on enemy turn — most paths read
            // weapon_damage/weapon_target_behind directly from the unit)
            // sees the right id. Damage stays on the unit's
            // weapon_damage field (telegraphed = 0 this turn = no
            // attack).
            u.weapon = WeaponId(WId::SpiderlingAtk1 as u16);
            u.weapon_damage = 0;
            u.weapon_push = 0;
            u.weapon_target_behind = false;
            // Clear the egg's "queued target = self-tile" so the attack
            // loop's egg-name skip is no longer needed for this unit
            // and the phantom-attack guard treats it as a no-op.
            u.queued_target_x = -1;
            u.queued_target_y = -1;
            u.flags.set(UnitFlags::HAS_QUEUED_ATTACK, false);
        }
    }

    // Smoke created by an earlier enemy attack does not retroactively cancel
    // a later enemy's already-queued attack. Latch which attackers are already
    // standing in smoke after all pre-attack enemy-phase effects have resolved.
    let mut smoke_cancelled_at_attack_start = [false; 16];
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.hp > 0 && u.is_enemy() && !u.burrowed() {
            smoke_cancelled_at_attack_start[i] = board.tile(u.x, u.y).smoke();
        }
    }

    // Collect enemy indices. Prefer the bridge's live attack_order when it is
    // available; UID order is only a legacy fallback. Mission_Factory captures
    // showed Pinnacle bots resolving in unit-list order, where sorting by UID
    // let a later Burnbug kill a Snowlaser before its live beam fired.
    let mut enemy_indices: Vec<usize> = (0..board.unit_count as usize)
        .filter(|&i| board.units[i].is_enemy() && !board.units[i].burrowed())
        .collect();
    if board.attack_order.is_empty() {
        enemy_indices.sort_by_key(|&i| board.units[i].uid);
    } else {
        let mut ordered: Vec<usize> = Vec::with_capacity(enemy_indices.len());
        for uid in &board.attack_order {
            if let Some(idx) = enemy_indices
                .iter()
                .copied()
                .find(|&i| board.units[i].uid == *uid)
            {
                if !ordered.contains(&idx) {
                    ordered.push(idx);
                }
            }
        }
        let mut remaining: Vec<usize> = enemy_indices
            .into_iter()
            .filter(|idx| !ordered.contains(idx))
            .collect();
        remaining.sort_by_key(|&i| board.units[i].uid);
        ordered.extend(remaining);
        enemy_indices = ordered;
    }

    for &ei in &enemy_indices {
        // A dead Vek remains pushable only for the rest of the queued action
        // that killed it. Once the next attack-order entry begins, live has
        // removed that corpse and later recoil/push effects may enter its tile.
        // Keep this at the action boundary so Moth artillery can still push a
        // lethally hit target into an occupied destination within one attack.
        clear_pre_attack_dead_enemy_wrecks(board);

        // Mission_Train replaces a destroyed moving train with a fresh,
        // stationary damaged train. Mission updates run between queued unit
        // actions, so materialize that replacement before the next enemy can
        // act on the same tiles.
        transition_destroyed_supply_train(board);

        let enemy = &board.units[ei];
        if enemy.hp <= 0 { continue; }
        // Spider/Arachnid eggs don't attack — they hatch into Spiderlings on
        // their turn. The hatch step above transforms WebbEgg1 +
        // SpiderlingEgg1 into Spiderling1 BEFORE this loop runs, so any
        // egg still here is an unhandled "*Egg" subtype (defensive). Skip
        // them as a fallback so an unmapped egg type doesn't phantom-melee.
        {
            let name = enemy.type_name_str();
            if name.starts_with("WebbEgg")
                || name.starts_with("SpiderlingEgg")
                || name.contains("Egg")
            {
                continue;
            }
        }
        // Mine-Bots use a bespoke attack-move setup skill rather than a
        // weapon strike. It is Smoke-immune, while Web/Frozen make it a no-op.
        // Handle it before the missing-target phantom-damage fallback and the
        // generic Smoke latch so neither can fabricate ordinary attack damage.
        if enemy.type_name_str().starts_with("Snowmine") {
            let attack_damage_before = AttackDamageSnapshot::capture(board);
            simulate_snowmine_attack(board, ei, &mut result);
            apply_void_shocker_after_attack(
                board,
                ei,
                attack_damage_before,
                &mut result,
            );
            continue;
        }
        if enemy.queued_target_x < 0 {
            // PHANTOM-ATTACK GUARD: Vek reports has_queued_attack=true
            // but the Lua bridge failed to populate a target. Don't
            // silently skip — apply conservative damage to the nearest
            // building so the scorer still penalizes plans that ignore
            // this Vek. See CLAUDE.md §21 grid-drop investigation gate.
            if enemy.has_queued_attack() {
                let attack_damage_before = AttackDamageSnapshot::capture(board);
                let ex = enemy.x;
                let ey = enemy.y;
                let dmg = if enemy.weapon_damage > 0 { enemy.weapon_damage as i8 } else { 1 };
                let uid = enemy.uid;
                let type_str = enemy.type_name_str().to_string();
                // Scan for nearest building (Chebyshev distance).
                let mut best: Option<(u8, u8, u32)> = None;
                for bx in 0u8..8 {
                    for by in 0u8..8 {
                        let tile = board.tile(bx, by);
                        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
                            let dx = (bx as i32 - ex as i32).abs() as u32;
                            let dy = (by as i32 - ey as i32).abs() as u32;
                            let d = dx.max(dy);
                            if best.map_or(true, |(_, _, bd)| d < bd) {
                                best = Some((bx, by, d));
                            }
                        }
                    }
                }
                // Warning suppressed in hot path — solver evaluates this hundreds of
                // thousands of times per turn and the log becomes unreadable. The
                // diagnostic value is preserved via the phantom-damage effect on the
                // score, which the tuner / replay will surface. Re-enable by setting
                // ITB_LOG_PHANTOM_ATTACK=1.
                if std::env::var("ITB_LOG_PHANTOM_ATTACK").is_ok() {
                    eprintln!(
                        "WARN: Vek {} ({}) has_queued_attack=true but no target — applying conservative damage",
                        uid, type_str);
                }
                if let Some((bx, by, _)) = best {
                    let idx = xy_to_idx(bx, by);
                    let is_unique = (board.unique_buildings & (1u64 << idx)) != 0;
                    if thaw_frozen_building(board, bx, by, &mut result) {
                        continue;
                    }
                    let (lost, destroyed) = {
                        let tile = board.tile_mut(bx, by);
                        let old_hp = tile.building_hp;
                        let applied = (dmg as u8).min(old_hp);
                        tile.building_hp = old_hp - applied;
                        let lost = old_hp - tile.building_hp;
                        result.buildings_damaged += lost as i32;
                        result.grid_damage += lost as i32;
                        let destroyed = tile.building_hp == 0;
                        if destroyed {
                            tile.terrain = Terrain::Rubble;
                            result.buildings_lost += 1;
                        }
                        (lost, destroyed)
                    };
                    let grid_loss = settle_building_grid_loss(
                        board,
                        idx,
                        lost,
                        destroyed,
                        is_unique,
                        DamageSource::Weapon,
                    );
                    result.grid_damage += (grid_loss as i32) - (lost as i32);
                    board.grid_power = board.grid_power.saturating_sub(grid_loss);
                    apply_auto_shield_after_building_damage(
                        board,
                        bx,
                        by,
                        lost,
                        &mut result,
                    );
                    buildings_destroyed += grid_loss as i32;
                }
                apply_void_shocker_after_attack(
                    board,
                    ei,
                    attack_damage_before,
                    &mut result,
                );
            }
            continue;
        }

        // Smoke cancels attacks
        // (Eggs have Smoke Immunity, but they're skipped above anyway.)
        if smoke_cancelled_at_attack_start[ei] { continue; }

        // Frozen enemies can't attack
        if enemy.frozen() { continue; }

        let ex = enemy.x;
        let ey = enemy.y;
        let qtx = enemy.queued_target_x;
        let qty = enemy.queued_target_y;
        let enemy_uid = enemy.uid;
        let orig = original_positions[ei];
        let queued_origin = queued_origin_for_attack(enemy, orig);
        let raw_queued_target = if enemy.flags.contains(UnitFlags::QUEUED_RAW_TARGET_SET) {
            Some((enemy.queued_target_raw_x, enemy.queued_target_raw_y))
        } else {
            None
        };

        // Look up actual weapon type from enemy pawn type
        let mut enemy_wid = enemy_weapon_for_type(enemy.type_name_str());

        // Bot Leader (BotBoss / BotBoss2) — Self-Repairing skill selection.
        // Per `scripts/missions/bosses/bot.lua:59-65`, `BotBoss:GetWeapon()`
        // returns skill index 2 (BossHeal) when `Pawn:IsDamaged()` and skill
        // index 1 (SnowBossAtk / SnowBossAtk2) otherwise. The bridge always
        // serializes `weapons[0]` into `unit.weapon` and `weapons[1]` into
        // `unit.weapon2`, so we can't read the active skill straight off the
        // unit. Mirror the boss's own decision instead: when the boss is
        // damaged AND has BossHeal as its second skill, the queued attack is
        // BossHeal — switch the dispatch wid so the SelfAoe arm fires the
        // immediate self-shield (the queued next-turn heal is outside the
        // 1-turn solver horizon — see lib.rs sim v31 notes).
        {
            let tname = enemy.type_name_str();
            if (tname == "BotBoss" || tname == "BotBoss2")
                && enemy.weapon2 == WeaponId(WId::BossHeal as u16)
                && enemy.hp < enemy.max_hp
            {
                enemy_wid = WId::BossHeal;
            }
        }
        // Unknown-enemy fallback. Boss/Leader types default to a stronger
        // template (Alpha Firefly / Alpha Hornet = 3 dmg) because an
        // unmapped boss missing from `enemy_weapon_for_type` is far more
        // dangerous than a 1-dmg basic Vek. Grid has been lost repeatedly
        // in finale missions where unknown bosses (e.g. SpiderBoss before
        // it was mapped) simulated as 1-dmg melee and the real attack hit
        // buildings un-modeled. See project_research_gate_gap memory.
        let wdef = if enemy_wid != WId::None {
            &weapons[enemy_wid as usize]
        } else {
            let name = enemy.type_name_str();
            let is_big = name.contains("Boss") || name.contains("Leader");
            if enemy.ranged() {
                if is_big {
                    &weapons[WId::FireflyAtk2 as usize] // alpha projectile, 3 dmg
                } else {
                    &weapons[WId::FireflyAtk1 as usize] // basic projectile
                }
            } else {
                if is_big {
                    &weapons[WId::HornetAtk2 as usize] // alpha melee, 3 dmg
                } else {
                    &weapons[WId::HornetAtk1 as usize] // basic melee
                }
            }
        };

        // Use bridge-provided damage if available, else weapon def
        let mut base_damage = if enemy.weapon_damage > 0 {
            enemy.weapon_damage
        } else {
            wdef.damage
        };
        // Boost Psion (LEADER_BOOSTED, Jelly_Boost1): +1 damage to all Vek
        // weapon attacks while alive. Excludes the Boost Psion itself per the
        // standard "aura source is exempt" pattern (consistent with Soldier
        // Psion's HP buff and Shell Psion's armor buff). Also skip the BossHeal
        // self-shield no-op (zero damage) — adding 1 there would bump a 0-dmg
        // shield-apply into a 1-dmg shield-apply, which isn't the intent.
        let attacker_tname = enemy.type_name_str();
        let boost_applies = board.boost_psion
            && enemy.receives_psion_aura()
            && attacker_tname != "Jelly_Boost1";
        if boost_applies && base_damage > 0 {
            base_damage += 1;
        }
        // Vek Hormones: +1 damage when enemy attacks hit other enemies
        // Applied per-hit below based on target occupant
        let damage = base_damage;

        // Alpha Hornet's second queued hit is an intrinsic property of
        // HornetAtk2.  Older/partial bridge payloads may omit the redundant
        // target-behind flag, so retain it as a compatibility supplement
        // rather than making exact WId behavior depend on it.
        let weapon_behind = wdef.aoe_behind() || enemy.weapon_target_behind;

        let vh = board.vek_hormones_damage;
        let attack_damage_before = AttackDamageSnapshot::capture(board);

        'queued_attack: {
        if matches!(enemy_wid, WId::StarfishAtk1 | WId::StarfishAtk2 | WId::StarfishAtkB1) {
            apply_starfish_appendages(
                board,
                ex,
                ey,
                damage,
                enemy_wid == WId::StarfishAtkB1,
                vh,
                &mut result,
            );
            break 'queued_attack;
        }

        // BossHeal special-case: Bot Leader's Self-Repairing skill applies
        // Shield to self this enemy turn and queues a +5 heal for the
        // FOLLOWING enemy turn (out of 1-turn solver horizon — see
        // lib.rs sim v31 notes for rationale). Implementation:
        // `apply_weapon_status` on the boss's own tile, which sets the
        // SHIELD flag on the unit per BossHeal's `flags: SHIELD`.
        // BossHeal does NOT consume the existing shield — `apply_weapon_status`
        // handles the "shield blocks negative status without consuming" rule
        // but Shield is itself a positive status, so it sets/refreshes
        // unconditionally. No damage is applied (wdef.damage=0), no push.
        if enemy_wid == WId::BossHeal {
            apply_weapon_status(board, ex, ey, wdef);
            break 'queued_attack;
        }

        if matches!(enemy_wid, WId::TotemAtk1 | WId::TotemAtk2 | WId::TotemAtkB) {
            // Totem/Spore attacks use the same live GetProjectileEnd line
            // trace as Firefly projectiles, then self-destruct.  Recompute
            // the impact from the current board so a pawn that moves into the
            // line can absorb the shot (and its push), while a vacated pawn
            // endpoint exposes the next blocker farther down the line.
            if let Some((tx, ty)) = find_projectile_target(
                board,
                ex,
                ey,
                queued_origin.0,
                queued_origin.1,
                qtx,
                qty,
                raw_queued_target,
            ) {
                let occupied_at_impact = board.unit_at(tx, ty).is_some();
                let d = enemy_hit_damage(board, tx, ty, damage, vh);
                apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
                apply_weapon_status_with_impact_occupancy(
                    board, tx, ty, wdef, occupied_at_impact,
                );
                if let Some(dir) = projectile_dir_from_queued_or_current(
                    ex,
                    ey,
                    queued_origin.0,
                    queued_origin.1,
                    qtx,
                    qty,
                    raw_queued_target,
                ) {
                    apply_push(board, tx, ty, dir, &mut result);
                }
            }

            apply_damage(board, ex, ey, 100, &mut result, DamageSource::Weapon);
            break 'queued_attack;
        }

        match wdef.weapon_type {
            WeaponType::Projectile => {
                if enemy_wid == WId::FireflyAtkB {
                    if let Some((dx, dy)) = projectile_delta_from_queued_or_current(
                        ex,
                        ey,
                        queued_origin.0,
                        queued_origin.1,
                        qtx,
                        qty,
                        raw_queued_target,
                    ) {
                        for (shot_dx, shot_dy) in [(dx, dy), (-dx, -dy)] {
                            if let Some((tx, ty)) = find_projectile_target_in_direction(
                                board, ex, ey, shot_dx, shot_dy,
                            ) {
                                let occupied_at_impact = board.unit_at(tx, ty).is_some();
                                let d = enemy_hit_damage(board, tx, ty, damage, vh);
                                apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
                                apply_weapon_status_with_impact_occupancy(
                                    board, tx, ty, wdef, occupied_at_impact,
                                );
                            }
                        }
                    }
                    break 'queued_attack;
                }
                if let Some((tx, ty)) = find_projectile_target(
                    board,
                    ex,
                    ey,
                    queued_origin.0,
                    queued_origin.1,
                    qtx,
                    qty,
                    raw_queued_target,
                ) {
                    let hit_was_object = {
                        let tile = board.tile(tx, ty);
                        tile.terrain == Terrain::Mountain
                            || (tile.terrain == Terrain::Building && tile.building_hp > 0)
                    };
                    // Burnbug/Gastropod hooks queue damage before their
                    // charge. Capture the pawn now because a lethal hit makes
                    // `unit_at` skip the corpse even though the queued charge
                    // still drags it toward the attacker.
                    let grapple_target = if wdef.projectile_grapple() {
                        board.unit_at(tx, ty).map(|idx| {
                            (
                                idx,
                                board.units[idx].hp,
                                board.units[idx].acid(),
                                board.tile(tx, ty).acid(),
                                board.units[idx].x,
                                board.units[idx].y,
                            )
                        })
                    } else {
                        None
                    };
                    let occupied_at_impact = board.unit_at(tx, ty).is_some();
                    let d = enemy_hit_damage(board, tx, ty, damage, vh);
                    let deferred_death_explosion = if wdef.projectile_grapple() {
                        apply_damage_defer_death_explosion(
                            board,
                            tx,
                            ty,
                            d,
                            &mut result,
                            DamageSource::Weapon,
                        )
                    } else {
                        apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
                        None
                    };
                    let grapple_killed_by_hit = grapple_target
                        .map(|(idx, pre_hp, _, _, _, _)| {
                            pre_hp > 0 && board.units[idx].hp <= 0
                        })
                        .unwrap_or(false);
                    if wdef.fire() {
                        if let Some(idx) = board.unit_at(tx, ty) {
                            let target_is_immune_vek = board.fire_psion
                                && board.units[idx].receives_psion_aura()
                                && board.units[idx].type_name_str() != "Jelly_Fire1";
                            let u = &mut board.units[idx];
                            // Pilot_Rock is fire-immune; skip even the
                            // "unfreeze + catch fire" combo so Ariadne on
                            // ice stays frozen rather than becoming a
                            // walking exception. Fire Psion grants Vek
                            // immunity to fire-status application.
                            if !u.frozen() && u.can_catch_fire()
                                && !(board.flame_shielding && u.is_player() && u.is_mech())
                                && !target_is_immune_vek
                            {
                                u.set_fire(true);
                            }
                        }
                        board.tile_mut(tx, ty).set_on_fire(true);
                    }
                    // ACID / WEB / other status effects on the primary target
                    apply_weapon_status_with_impact_occupancy(
                        board, tx, ty, wdef, occupied_at_impact,
                    );
                    if wdef.web() {
                        if let Some(idx) = board.unit_at(tx, ty) {
                            // Skip webber-uid tracking for Pilot_Soldier so
                            // Camila's Unit stays clean (no phantom webber).
                            if !board.units[idx].pilot_soldier() {
                                board.units[idx].web_source_uid = enemy_uid;
                            }
                        }
                    }
                    if wdef.projectile_grapple() {
                        if let Some(dir) = projectile_dir_from_queued_or_current(
                            ex, ey, queued_origin.0, queued_origin.1, qtx, qty, raw_queued_target,
                        ) {
                            apply_projectile_grapple(
                                board,
                                ei,
                                grapple_target.map(|(idx, _, _, _, _, _)| idx),
                                tx,
                                ty,
                                dir,
                                hit_was_object,
                                grapple_killed_by_hit,
                                &mut result,
                            );
                        }

                        if let Some((idx, _, was_acid, tile_had_acid, ox, oy)) = grapple_target {
                            let fx = board.units[idx].x;
                            let fy = board.units[idx].y;
                            if grapple_killed_by_hit && was_acid && (fx, fy) != (ox, oy) {
                                if !tile_had_acid {
                                    board.tile_mut(ox, oy).flags.remove(TileFlags::ACID);
                                }
                                leave_acid_pool_on_death(board, fx, fy);
                            }
                        }

                        if let Some(idx) = deferred_death_explosion {
                            let ex = board.units[idx].x;
                            let ey = board.units[idx].y;
                            apply_death_explosion(board, ex, ey, &mut result, 0);
                        }
                    }

                    // Centipede Leader's Caustic Vomit queues zero-damage ACID
                    // on every tile strictly between the attacker and impact.
                    // The normal Centipede/Alpha Centipede weapons do not.
                    if enemy_wid == WId::CentipedeAtkB {
                        let pdx = (tx as i8 - ex as i8).signum();
                        let pdy = (ty as i8 - ey as i8).signum();
                        if (pdx != 0) != (pdy != 0) {
                            let mut px = ex as i8 + pdx;
                            let mut py = ey as i8 + pdy;
                            while in_bounds(px, py) && (px as u8, py as u8) != (tx, ty) {
                                let occupied_at_impact = board.unit_at(px as u8, py as u8).is_some();
                                apply_weapon_status_with_impact_occupancy(
                                    board,
                                    px as u8,
                                    py as u8,
                                    wdef,
                                    occupied_at_impact,
                                );
                                px += pdx;
                                py += pdy;
                            }
                        }
                    }

                    // aoe_perpendicular: splash two tiles perpendicular to
                    // projectile direction (Alpha Centipede's Corrosive Vomit:
                    // 3-tile T splash, damage + ACID on each).
                    if wdef.aoe_perpendicular() {
                        let pdx = (tx as i8 - ex as i8).signum();
                        let pdy = (ty as i8 - ey as i8).signum();
                        let perp: &[(i8, i8)] = if pdx != 0 && pdy == 0 {
                            &[(0, 1), (0, -1)]
                        } else if pdy != 0 && pdx == 0 {
                            &[(1, 0), (-1, 0)]
                        } else {
                            &[]
                        };
                        for &(px, py) in perp {
                            let nx = tx as i8 + px;
                            let ny = ty as i8 + py;
                            if !in_bounds(nx, ny) { continue; }
                            let nxu = nx as u8;
                            let nyu = ny as u8;
                            let occupied_at_impact = board.unit_at(nxu, nyu).is_some();
                            let d2 = enemy_hit_damage(board, nxu, nyu, damage, vh);
                            apply_damage(board, nxu, nyu, d2, &mut result, DamageSource::Weapon);
                            apply_weapon_status_with_impact_occupancy(
                                board, nxu, nyu, wdef, occupied_at_impact,
                            );
                            if wdef.web() {
                                if let Some(idx) = board.unit_at(nxu, nyu) {
                                    if !board.units[idx].pilot_soldier() {
                                        board.units[idx].web_source_uid = enemy_uid;
                                    }
                                }
                            }
                        }
                    }
                }
            }

            WeaponType::Laser => {
                // Piercing beam: fires in cardinal direction from enemy position,
                // damage starts at wdef.damage and decreases by 1 per tile (floor 1).
                // Stops at mountains and buildings (after damaging them).
                if let Some((dx, dy)) = projectile_delta_from_queued_or_current(
                    ex, ey, queued_origin.0, queued_origin.1, qtx, qty, raw_queued_target,
                ) {
                    let mut dmg = wdef.damage;
                    for i in 1..8i8 {
                        let nx = ex as i8 + dx * i;
                        let ny = ey as i8 + dy * i;
                        if !in_bounds(nx, ny) { break; }
                        let nxu = nx as u8;
                        let nyu = ny as u8;
                        let tile = board.tile(nxu, nyu);
                        if tile.terrain == Terrain::Mountain {
                            apply_damage(board, nxu, nyu, dmg, &mut result, DamageSource::Weapon);
                            break;
                        }
                        if tile.is_building() {
                            apply_damage(board, nxu, nyu, dmg, &mut result, DamageSource::Weapon);
                            break;
                        }
                        let d = enemy_hit_damage(board, nxu, nyu, dmg, vh);
                        apply_damage(board, nxu, nyu, d, &mut result, DamageSource::Weapon);
                        dmg = dmg.saturating_sub(1).max(1);
                    }
                }
            }

            WeaponType::Artillery => {
                // Artillery preserves its ORIGINAL OFFSET from the attacker when
                // the attacker is pushed. Per ITB's piQueuedShot semantics, the
                // queued target is a direction+distance stored relative to the
                // enemy — pushing the enemy relocates the target tile by the
                // same delta (confirmed empirically: push Alpha Scarab D3→C3
                // with D7 original target → new target shifts to C7).
                //
                // range_min guard: if the PUSHED distance is below the weapon's
                // minimum range, attack cancels (e.g. pushed adjacent to target).
                let Some((offset_x, offset_y)) = queued_cardinal_offset_from_raw_or_current(
                    ex, ey, queued_origin.0, queued_origin.1, qtx, qty, raw_queued_target,
                ) else {
                    break 'queued_attack;
                };
                let new_tx = ex as i8 + offset_x;
                let new_ty = ey as i8 + offset_y;
                if !in_bounds(new_tx, new_ty) { break 'queued_attack; }

                // Cardinal axis required (exactly one axis non-zero) for artillery
                // to have a direction for path_size > 1 handling.
                let dx_sign = offset_x.signum();
                let dy_sign = offset_y.signum();
                if (dx_sign != 0) == (dy_sign != 0) { break 'queued_attack; }

                // Min-range check against the (new) attacker→target distance.
                let curr_range = offset_x.abs() + offset_y.abs();
                if (curr_range as u8) < wdef.range_min { break 'queued_attack; }
                if matches!(
                    enemy_wid,
                    WId::MothAtk1
                        | WId::MothAtk2
                        | WId::SnowartAtk1
                        | WId::SnowartAtk2
                        | WId::SnowBossAtk
                        | WId::SnowBossAtk2
                ) || is_crab_scarab_line_artillery(enemy_wid)
                {
                    if (curr_range as u8) > wdef.range_max {
                        break 'queued_attack;
                    }
                }

                let tx = new_tx as u8;
                let ty = new_ty as u8;
                let attack_dir = DIRS.iter()
                    .position(|&(ddx, ddy)| ddx == dx_sign && ddy == dy_sign);

                if wdef.push_self() {
                    if let Some(dir) = attack_dir {
                        apply_push_no_edge_bump(board, ex, ey, opposite_dir(dir), &mut result);
                    }
                }

                // Crab Leader's Raining Expulsions damages the artillery target
                // plus each cardinal tile in the projectile path before p2.
                if wdef.path_damage() && wdef.damage_outer > 0 {
                    for step in 1..curr_range {
                        let px = ex as i8 + dx_sign * step;
                        let py = ey as i8 + dy_sign * step;
                        if !in_bounds(px, py) { break; }
                        let d_p = enemy_hit_damage(board, px as u8, py as u8, wdef.damage_outer, vh);
                        apply_damage(board, px as u8, py as u8, d_p, &mut result, DamageSource::Weapon);
                    }
                }

                let d = enemy_hit_damage(board, tx, ty, damage, vh);
                apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
                if wdef.push == PushDir::Forward {
                    if let Some(dir) = attack_dir {
                        if matches!(enemy_wid, WId::MothAtk1 | WId::MothAtk2) {
                            // Repulsive Pellets keeps the killed target's
                            // forward push live long enough to bump an
                            // occupied destination. Keep this Moth-specific:
                            // generic and Cluster Artillery corpse pushes are
                            // absorbed by live blockers.
                            apply_push_dead_bumps_live_blocker(
                                board,
                                tx,
                                ty,
                                dir,
                                &mut result,
                            );
                        } else {
                            apply_push(board, tx, ty, dir, &mut result);
                        }
                    }
                }

                // Scarab Leader's Expectorating Glands queues zero-damage
                // outward pushes on the four tiles adjacent to the artillery
                // target. Keep this generic for any future artillery with
                // AOE_ADJACENT + PushDir::Outward.
                if wdef.aoe_adjacent() {
                    for (i, &(dx, dy)) in DIRS.iter().enumerate() {
                        let nx = new_tx + dx;
                        let ny = new_ty + dy;
                        if !in_bounds(nx, ny) { continue; }
                        let nxu = nx as u8;
                        let nyu = ny as u8;
                        if wdef.damage_outer > 0 {
                            let d_adj = enemy_hit_damage(board, nxu, nyu, wdef.damage_outer, vh);
                            apply_damage(board, nxu, nyu, d_adj, &mut result, DamageSource::Weapon);
                        }
                        if wdef.push == PushDir::Outward {
                            if wdef.no_edge_bump_adjacent_push() && wdef.damage_outer == 0 {
                                let bx = nx + dx;
                                let by = ny + dy;
                                if !in_bounds(bx, by) { continue; }
                            }
                            apply_push(board, nxu, nyu, i, &mut result);
                        }
                    }
                }

                // path_size > 1: also damage subsequent tiles in attack direction
                // (e.g. Super Stinger's 3-tile line; Crab Artillery's 2-tile hit)
                for i in 1..wdef.path_size as i8 {
                    let tx_n = new_tx + dx_sign * i;
                    let ty_n = new_ty + dy_sign * i;
                    if !in_bounds(tx_n, ty_n) { break; }
                    let d_n = enemy_hit_damage(board, tx_n as u8, ty_n as u8, damage, vh);
                    apply_damage(board, tx_n as u8, ty_n as u8, d_n, &mut result, DamageSource::Weapon);
                }

                // aoe_perpendicular: hit two tiles flanking the target
                // perpendicular to firing direction. Used by SnowBossAtk /
                // SnowBossAtk2 (Bot Leader's Vk8 Rockets Mk III/IV) — Lua
                // SnowartAtk1:GetSkillEffect (weapons_snow.lua:120-135)
                // damages p2 + p2+DIR_VECTORS[(dir+1)%4] + p2+DIR_VECTORS
                // [(dir-1)%4]. The dir here is computed from the (offset) cardinal
                // axis of attack, NOT the unit's facing — so we use dx_sign/dy_sign.
                if wdef.aoe_perpendicular() {
                    // Perp directions: rotate the firing axis 90° both ways.
                    // Firing east-west (dy_sign==0): perps are (0,±1).
                    // Firing north-south (dx_sign==0): perps are (±1,0).
                    let perp: [(i8, i8); 2] = if dx_sign != 0 && dy_sign == 0 {
                        [(0, 1), (0, -1)]
                    } else {
                        [(1, 0), (-1, 0)]
                    };
                    for &(pdx, pdy) in &perp {
                        let px = new_tx + pdx;
                        let py = new_ty + pdy;
                        if !in_bounds(px, py) { continue; }
                        let occupied_at_impact = board.unit_at(px as u8, py as u8).is_some();
                        let d_p = enemy_hit_damage(board, px as u8, py as u8, damage, vh);
                        apply_damage(board, px as u8, py as u8, d_p, &mut result, DamageSource::Weapon);
                        apply_weapon_status_with_impact_occupancy(
                            board, px as u8, py as u8, wdef, occupied_at_impact,
                        );
                    }
                }

                // Spawn-artillery side effects: Spider (webb eggs), Blobber
                // (blobs), and Shaman (Totems) fire a 0-dmg artillery whose real
                // effect is placing a unit at the target tile. Without
                // this the solver never sees the follow-up threat
                // (egg hatches → Spiderling damages building next turn).
                // SpiderBoss maps to SpiderAtk2 which also spawns eggs,
                // though the real boss drops 2-3; we approximate with 1.
                match enemy_wid {
                    WId::SpiderAtk1 | WId::SpiderAtk2 => {
                        spawn_enemy(board, tx, ty, "WebbEgg1", 1);
                    }
                    WId::BlobberAtk1 => {
                        spawn_enemy(board, tx, ty, "Blob1", 1);
                    }
                    WId::BlobberAtk2 => {
                        spawn_enemy(board, tx, ty, "Blob2", 1);
                    }
                    WId::BlobberAtkB => {
                        spawn_enemy(board, tx, ty, "BlobB", 2);
                    }
                    WId::ShamanAtk1 => {
                        spawn_shaman_totem(board, tx, ty, "Totem1", WId::TotemAtk1);
                    }
                    WId::ShamanAtk2 => {
                        spawn_shaman_totem(board, tx, ty, "Totem2", WId::TotemAtk2);
                    }
                    _ => {}
                }
            }

            WeaponType::Charge => {
                // Charge from CURRENT position in original queued direction
                if let Some((dx, dy)) = projectile_delta_from_queued_or_current(
                    ex, ey, queued_origin.0, queued_origin.1, qtx, qty, raw_queued_target,
                ) {
                    let mut hit: Option<(u8, u8)> = None;
                    let mut last_free = (ex, ey);
                    let mut path: Vec<(u8, u8)> = Vec::new();
                    let flying_charge = enemy_wid == WId::BeetleAtkB;
                    for i in 1..8i8 {
                        let nx = ex as i8 + dx * i;
                        let ny = ey as i8 + dy * i;
                        if !in_bounds(nx, ny) { break; }
                        let nxu = nx as u8;
                        let nyu = ny as u8;

                        let tile = board.tile(nxu, nyu);
                        if tile.terrain == Terrain::Mountain {
                            hit = Some((nxu, nyu));
                            break;
                        }
                        if tile.terrain.is_deadly_ground() && !flying_charge { break; }
                        if tile.is_building() {
                            hit = Some((nxu, nyu));
                            break;
                        }
                        if board.unit_at(nxu, nyu).is_some() {
                            hit = Some((nxu, nyu));
                            break;
                        }
                        path.push((nxu, nyu));
                        last_free = (nxu, nyu);
                    }

                    board.units[ei].x = last_free.0;
                    board.units[ei].y = last_free.1;
                    apply_teleport_on_land(board, ei);

                    if let Some((hx, hy)) = hit {
                        // Flaming Abdomen: fire on every PASSED tile (i=1..hit_i-1)
                        // EXCLUDING the final resting tile (i=hit_i-1). So fire
                        // on tiles i=1..=(hit_i-2).
                        if wdef.fire() {
                            let fire_count = path.len().saturating_sub(1);
                            for &(fx, fy) in path.iter().take(fire_count) {
                                board.tile_mut(fx, fy).set_on_fire(true);
                                if let Some(idx) = board.unit_at(fx, fy) {
                                    let target_is_immune_vek = board.fire_psion
                                        && board.units[idx].receives_psion_aura()
                                        && board.units[idx].type_name_str() != "Jelly_Fire1";
                                    let u = &mut board.units[idx];
                                    if !u.frozen() && u.can_catch_fire()
                                        && !(board.flame_shielding && u.is_player() && u.is_mech())
                                        && !target_is_immune_vek
                                    {
                                        u.set_fire(true);
                                    }
                                }
                            }
                        }

                        let d = enemy_hit_damage(board, hx, hy, damage, vh);
                        apply_damage(board, hx, hy, d, &mut result, DamageSource::Weapon);

                        // Forward push: pushes target in charge direction.
                        if wdef.push == PushDir::Forward {
                            let push_dir_idx: usize = match (dx, dy) {
                                (0, 1) => 0,
                                (1, 0) => 1,
                                (0, -1) => 2,
                                (-1, 0) => 3,
                                _ => 0,
                            };
                            apply_push(board, hx, hy, push_dir_idx, &mut result);
                        }
                    }
                }
            }

            WeaponType::SelfAoe => {
                // DiggerAtk1 builds neutral rock pawns on source-eligible
                // adjacent tiles as a separate effect from its queued hit.
                // Snapshot eligibility before damage: an occupied tile does
                // not gain a wall merely because this same attack clears it.
                // Materialize after damage so the Digger's own queued hit does
                // not destroy the newly-created one-HP wall; recorded live
                // boards retain these walls for later actions and turns.
                let mut digger_wall_tiles = [None; 4];
                if matches!(enemy_wid, WId::DiggerAtk1 | WId::DiggerAtk2) {
                    for (i, &(dx, dy)) in DIGGER_WALL_SOURCE_DIRS.iter().enumerate() {
                        let nx = ex as i8 + dx;
                        let ny = ey as i8 + dy;
                        if in_bounds(nx, ny)
                            && digger_wall_tile_eligible(board, nx as u8, ny as u8)
                        {
                            digger_wall_tiles[i] = Some((nx as u8, ny as u8));
                        }
                    }
                }
                if wdef.aoe_center() {
                    apply_damage(board, ex, ey, damage, &mut result, DamageSource::Weapon);
                }
                if wdef.aoe_adjacent() {
                    let mut adjacent_damage = if wdef.damage_outer > 0 {
                        wdef.damage_outer
                    } else {
                        damage
                    };
                    if boost_applies && adjacent_damage > 0 {
                        adjacent_damage += 1;
                    }
                    for (i, &(dx, dy)) in DIRS.iter().enumerate() {
                        let nx = ex as i8 + dx;
                        let ny = ey as i8 + dy;
                        if in_bounds(nx, ny) {
                            let d = enemy_hit_damage(board, nx as u8, ny as u8, adjacent_damage, vh);
                            apply_damage(board, nx as u8, ny as u8, d, &mut result, DamageSource::Weapon);
                            // Massive Spinneret's AddGrapple is immediate on
                            // the original adjacent survivor; its melee/push
                            // is queued afterward. An actual tile change in
                            // apply_push then clears this web, while a blocked
                            // push leaves the source-owned grapple intact.
                            if wdef.web() {
                                if let Some(idx) = board.unit_at(nx as u8, ny as u8) {
                                    if board.units[idx].hp > 0 && !board.units[idx].pilot_soldier() {
                                        board.units[idx].set_web(true);
                                        board.units[idx].web_source_uid = enemy_uid;
                                    }
                                }
                            }
                            // Push outward / inward per weapon def (Scorpion Leader's
                            // Massive Spinneret pushes every target away from itself).
                            match wdef.push {
                                PushDir::Outward => apply_push(board, nx as u8, ny as u8, i, &mut result),
                                PushDir::Inward => apply_push(board, nx as u8, ny as u8, opposite_dir(i), &mut result),
                                _ => {}
                            }
                        }
                    }
                }
                for (x, y) in digger_wall_tiles.into_iter().flatten() {
                    spawn_digger_wall(board, x, y);
                }
            }

            WeaponType::Melee => {
                if weapon_behind {
                    // Line attack (e.g., Launching Stinger): 2-tile line in the original
                    // cardinal direction. When pushed, retrace direction from the ORIGINAL
                    // position so the attack fires correctly from the new position.
                    let Some((dx, dy)) = projectile_delta_from_queued_or_current(
                        ex, ey, queued_origin.0, queued_origin.1, qtx, qty, raw_queued_target,
                    ) else {
                        break 'queued_attack;
                    };

                    let tx1 = ex as i8 + dx;
                    let ty1 = ey as i8 + dy;
                    if in_bounds(tx1, ty1) {
                        let occupied_at_impact = board.unit_at(tx1 as u8, ty1 as u8).is_some();
                        let d = enemy_hit_damage(board, tx1 as u8, ty1 as u8, damage, vh);
                        apply_damage(board, tx1 as u8, ty1 as u8, d, &mut result, DamageSource::Weapon);
                        apply_weapon_status_with_impact_occupancy(
                            board, tx1 as u8, ty1 as u8, wdef, occupied_at_impact,
                        );
                        if wdef.web() {
                            if let Some(idx) = board.unit_at(tx1 as u8, ty1 as u8) {
                                board.units[idx].web_source_uid = enemy_uid;
                            }
                        }
                    }
                    let tx2 = ex as i8 + dx * 2;
                    let ty2 = ey as i8 + dy * 2;
                    if in_bounds(tx2, ty2) {
                        let occupied_at_impact = board.unit_at(tx2 as u8, ty2 as u8).is_some();
                        let d2 = enemy_hit_damage(board, tx2 as u8, ty2 as u8, damage, vh);
                        apply_damage(board, tx2 as u8, ty2 as u8, d2, &mut result, DamageSource::Weapon);
                        apply_weapon_status_with_impact_occupancy(
                            board, tx2 as u8, ty2 as u8, wdef, occupied_at_impact,
                        );
                        if wdef.web() {
                            if let Some(idx) = board.unit_at(tx2 as u8, ty2 as u8) {
                                board.units[idx].web_source_uid = enemy_uid;
                            }
                        }
                    }
                } else {
                    if enemy_wid == WId::BouncerAtkB {
                        let Some(dir) = projectile_dir_from_queued_or_current(
                            ex, ey, queued_origin.0, queued_origin.1, qtx, qty, raw_queued_target,
                        ) else {
                            break 'queued_attack;
                        };
                        let (dx, dy) = DIRS[dir];
                        let tx = ex as i8 + dx;
                        let ty = ey as i8 + dy;
                        if !in_bounds(tx, ty) { break 'queued_attack; }
                        let (tx, ty) = (tx as u8, ty as u8);

                        let d = enemy_hit_damage(board, tx, ty, damage, vh);
                        apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
                        apply_push(board, tx, ty, dir, &mut result);

                        apply_push(board, ex, ey, opposite_dir(dir), &mut result);

                        for &perp in &[(dir + 1) % 4, (dir + 3) % 4] {
                            let (pdx, pdy) = DIRS[perp];
                            let px = tx as i8 + pdx;
                            let py = ty as i8 + pdy;
                            if !in_bounds(px, py) { continue; }
                            let (px, py) = (px as u8, py as u8);
                            let pd = enemy_hit_damage(board, px, py, damage, vh);
                            apply_damage(board, px, py, pd, &mut result, DamageSource::Weapon);
                            apply_push(board, px, py, dir, &mut result);
                        }
                        break 'queued_attack;
                    }

                    let (tx, ty, attack_dir) = if wdef.queued_damage_persists() {
                        // BlobBoss family registers queued damage before movement,
                        // but live captures show p2 is still interpreted as the
                        // original attacker-relative offset. A pushed Goo keeps
                        // firing; the target tile shifts by the same displacement.
                        let Some((offset_x, offset_y)) =
                            queued_cardinal_offset_from_raw_or_current(
                                ex,
                                ey,
                                queued_origin.0,
                                queued_origin.1,
                                qtx,
                                qty,
                                raw_queued_target,
                            )
                        else {
                            break 'queued_attack;
                        };
                        let new_tx = ex as i8 + offset_x;
                        let new_ty = ey as i8 + offset_y;
                        if !in_bounds(new_tx, new_ty) { break 'queued_attack; }
                        (new_tx as u8, new_ty as u8, None)
                    } else {
                        // Standard single-tile melee preserves the original
                        // queued direction, then re-aims from the attacker's
                        // current tile after pushes, swaps, and teleports.
                        let Some((dx, dy)) = projectile_delta_from_queued_or_current(
                            ex, ey, queued_origin.0, queued_origin.1, qtx, qty, raw_queued_target,
                        ) else {
                            break 'queued_attack;
                        };
                        let tx = ex as i8 + dx;
                        let ty = ey as i8 + dy;
                        if !in_bounds(tx, ty) { break 'queued_attack; }
                        let dir = DIRS.iter().position(|&(ddx, ddy)| ddx == dx && ddy == dy);
                        (tx as u8, ty as u8, dir)
                    };

                    if wdef.push_self() {
                        if let Some(dir) = attack_dir {
                            if matches!(enemy_wid, WId::BouncerAtk1 | WId::BouncerAtk2) {
                                apply_push_no_edge_bump(board, ex, ey, opposite_dir(dir), &mut result);
                            } else {
                                apply_push(board, ex, ey, opposite_dir(dir), &mut result);
                            }
                        }
                    }
                    if matches!(enemy_wid, WId::BurrowerAtk1 | WId::BurrowerAtk2) {
                        if let Some(dir) = attack_dir {
                            for &hit_dir in &[None, Some((dir + 1) % 4), Some((dir + 3) % 4)] {
                                let (hx, hy) = if let Some(perp) = hit_dir {
                                    let (pdx, pdy) = DIRS[perp];
                                    let hx = tx as i8 + pdx;
                                    let hy = ty as i8 + pdy;
                                    if !in_bounds(hx, hy) { continue; }
                                    (hx as u8, hy as u8)
                                } else {
                                    (tx, ty)
                                };
                                let occupied_at_impact = board.unit_at(hx, hy).is_some();
                                let d = enemy_hit_damage(board, hx, hy, damage, vh);
                                apply_damage(board, hx, hy, d, &mut result, DamageSource::Weapon);
                                apply_weapon_status_with_impact_occupancy(
                                    board, hx, hy, wdef, occupied_at_impact,
                                );
                            }
                            break 'queued_attack;
                        }
                    }
                    if enemy_wid == WId::MosquitoAtkB {
                        apply_mosquito_boss_attack(board, tx, ty, &mut result);
                        break 'queued_attack;
                    }
                    let target_had_mech = board.unit_at(tx, ty)
                        .is_some_and(|idx| board.units[idx].is_mech());
                    let target_was_mountain = board.tile(tx, ty).terrain == Terrain::Mountain;
                    let occupied_at_impact = board.unit_at(tx, ty).is_some();
                    let d = enemy_hit_damage(board, tx, ty, damage, vh);
                    if matches!(
                        enemy_wid,
                        WId::TumblebugAtk1 | WId::TumblebugAtk2 | WId::TumblebugAtkB
                    ) {
                        apply_damage_with_bombrock_exclusion(
                            board,
                            tx,
                            ty,
                            d,
                            &mut result,
                            DamageSource::Weapon,
                            Some((ex, ey)),
                        );
                    } else {
                        apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
                    }
                    if wdef.queued_damage_persists() && target_was_mountain {
                        // BlobBossAtk queues a second identical hit against
                        // mountains, destroying a full mountain in one squish.
                        apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
                    }
                    if wdef.push == PushDir::Forward {
                        if let Some(dir) = attack_dir {
                            apply_push(board, tx, ty, dir, &mut result);
                        }
                    }
                    apply_weapon_status_with_impact_occupancy(
                        board, tx, ty, wdef, occupied_at_impact,
                    );
                    if wdef.web() {
                        if let Some(idx) = board.unit_at(tx, ty) {
                            board.units[idx].web_source_uid = enemy_uid;
                        }
                    }
                    if wdef.queued_damage_persists()
                        && !target_had_mech
                        && board.units[ei].hp > 0
                        && board.unit_at(tx, ty).is_none()
                    {
                        let tile = board.tile(tx, ty);
                        if !matches!(tile.terrain, Terrain::Building | Terrain::Mountain)
                            && !tile.terrain.is_deadly_ground()
                        {
                            board.units[ei].x = tx;
                            board.units[ei].y = ty;
                        }
                    }
                }
            }

            _ => {
                // OOB guard: see Melee arm above. Catch-all path also fed
                // qtx/qty straight into tile_mut and panicked on M04.
                if qtx < 0 || qty < 0 || qtx >= 8 || qty >= 8 { break 'queued_attack; }
                let tx = qtx as u8;
                let ty = qty as u8;
                let d = enemy_hit_damage(board, tx, ty, damage, vh);
                apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
            }
        }
        }
        apply_void_shocker_after_attack(
            board,
            ei,
            attack_damage_before,
            &mut result,
        );
    }

    if board.env_danger != 0 && env_after_attacks {
        apply_env_danger_board(board, &mut result);
    }
    resolve_mission_satellite_flyaways(board);

    if board.mission_id == "Mission_BeltRandom" {
        simulate_conveyor_belts(board, &mut result);
    }

    // Psion Tyrant: 1 damage to all player units (passive, not an attack — smoke doesn't cancel)
    if board.tyrant_psion {
        let tyrant_alive = (0..board.unit_count as usize).any(|i|
            board.units[i].type_name_str() == "Jelly_Lava1" && board.units[i].hp > 0);
        if tyrant_alive {
            for i in 0..board.unit_count as usize {
                let u = &mut board.units[i];
                if u.is_player() && u.hp > 0 {
                    if u.shield() {
                        u.set_shield(false);
                    } else if u.frozen() {
                        u.set_frozen(false);
                    } else {
                        // Weapon-type damage: armor reduces, ACID doubles
                        let actual: i8 = if u.acid() { 2 } else if u.armor() { 0 } else { 1 };
                        u.hp -= actual;
                    }
                }
            }
        } else {
            board.tyrant_psion = false;
        }
    }

    // A final queued attack can destroy the moving train without another enemy
    // iteration to trigger the action-boundary transition above.
    transition_destroyed_supply_train(board);

    // Mission_Hacking:UpdateMission replaces the hostile Cannon Bot with a
    // fresh player-controlled pawn once the Hacking Facility is gone. At this
    // conservative enemy-phase boundary, carry that source-defined conversion
    // into the next player-turn projection. Exact mid-enemy-phase interruption
    // of an already queued bot attack remains native-scheduling dependent.
    transition_hacked_cannon_bot(board);

    // Train_Pawn end-of-enemy-phase advance: moves 2 tiles forward along its
    // rail (direction = primary_tile - extra_tile). If either destination
    // tile is blocked (mountain, building, any non-train unit, or a wreck),
    // the moving train destroys that blocker, stops before it, and is replaced
    // by a live Train_Damaged body. If destinations are off-board, treat as
    // surviving (train has reached the far edge).
    let train_result = simulate_train_advance(board);
    result.merge(&train_result);

    // Player-phase bump debt is flushed at enemy-turn start above. Enemy-phase
    // bumps can create the same deferred debt (for example Tumblebug BombRock
    // explosions into 2-HP regular buildings), and the live grid meter is
    // settled before the next player turn. Flush again before returning the
    // post-enemy prediction.
    flush_deferred_bump_grid_debt(board, &mut result);

    // Count buildings destroyed from result
    buildings_destroyed += result.grid_damage;

    // Grid Defense expected save: each grid point lost had a
    // grid_defense_pct/100 chance to be blocked. Track as float on the
    // board for the evaluator. Without this the solver over-predicts
    // building loss by ~1 grid/turn at the 15% baseline.
    let gd = board.grid_defense_pct as f32;
    board.enemy_grid_save_expected = (buildings_destroyed as f32) * (gd / 100.0);

    // Drain the Spider Psion pending-egg queue (sim v38/v105). Eggs spawned by
    // on_enemy_death during this enemy phase land here AFTER the hatch
    // loop has run, so they sit dormant until the NEXT enemy phase
    // (matching the game's AddQueuedDamage hatch behavior — see
    // weapons_enemy.lua:857). spawn_enemy skips occupied tiles internally,
    // so a Vek that moved onto the corpse's tile during the attack loop
    // won't get displaced.
    crate::simulate::drain_pending_spider_eggs(board);
    // Mission_AcidStorm refreshes all living pawns after the completed enemy
    // phase. This deliberately avoids assigning a native sub-effect time
    // while ensuring enemy-created eggs, blobs, and split children match the
    // next-player-turn projection.
    apply_active_acid_storm(board);

    result
}

/// Advance the Supply Train 2 tiles forward. Called at end of enemy phase.
///
/// Direction is inferred from the two tile entries sharing uid: forward =
/// primary - extra (extra_tile is the caboose, primary is the locomotive).
/// Normal Train_Pawn stops if either entered tile is blocked by a mountain,
/// building, or non-train unit: it advances through any preceding clear step,
/// destroys the blocker, then becomes a live Train_Damaged body. Armored Train
/// instead destroys everything in its two entered tiles and keeps moving (Lua
/// Armored_Train_Move queues DAMAGE_DEATH on both tiles before charge).
/// Off-board destinations count as reaching the exit — train stays alive at
/// its current position (not advanced off the board). Called once per turn.
pub fn simulate_train_advance(board: &mut Board) -> ActionResult {
    let mut result = ActionResult::default();
    if transition_destroyed_supply_train(board) {
        return result;
    }

    let mut primary: Option<usize> = None;
    let mut extra: Option<usize> = None;
    let mut armored_train = false;
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        let tname = u.type_name_str();
        if tname != "Train_Pawn" && tname != "Train_Armored" { continue; }
        if u.hp <= 0 { continue; }
        armored_train = tname == "Train_Armored";
        if u.is_extra_tile() { extra = Some(i); } else { primary = Some(i); }
    }
    let (p, e) = match (primary, extra) {
        (Some(p), Some(e)) => (p, e),
        _ => return result,
    };

    // Frozen pawns do not activate. Train movement is an enemy-phase skill,
    // so an intact frozen train neither advances nor damages itself.
    if board.units[p].frozen() || board.units[e].frozen() {
        return result;
    }

    let (px, py) = (board.units[p].x as i8, board.units[p].y as i8);
    let (ex, ey) = (board.units[e].x as i8, board.units[e].y as i8);
    let dx = px - ex;
    let dy = py - ey;
    // Must be unit-length cardinal (sanity check).
    if dx.abs() + dy.abs() != 1 { return result; }

    // The extra tile moves into (px+dx, py+dy) — that space is already train
    // body (primary's old position). The primary tile passes through
    // (px+dx, py+dy) on its way to (px+2dx, py+2dy). We must check BOTH new
    // tiles the train enters that weren't already train body:
    //   - (px+dx, py+dy): primary's intermediate step (extra's final pos)
    //   - (px+2dx, py+2dy): primary's final pos
    let steps = [(px + dx, py + dy), (px + 2 * dx, py + 2 * dy)];
    for (step_idx, (nx, ny)) in steps.iter().enumerate() {
        if *nx < 0 || *nx >= 8 || *ny < 0 || *ny >= 8 {
            // Off-board: train has reached the exit. Leave hp alive, don't
            // advance — subsequent turns won't find the train to re-advance
            // because its position is still valid on-board this turn.
            return result;
        }
        let (nxu, nyu) = (*nx as u8, *ny as u8);
        if armored_train {
            destroy_train_path_tile(board, nxu, nyu, &mut result);
            continue;
        }
        if board.is_blocked(nxu, nyu, false) {
            // Train_Move queues its partial charge before killing the blocker
            // and damaging itself. A second-step blocker therefore leaves the
            // stopped train one tile farther forward; a first-step blocker
            // leaves it at the original position.
            let cleared = step_idx as i8;
            board.units[p].x = (px + cleared * dx) as u8;
            board.units[p].y = (py + cleared * dy) as u8;
            board.units[e].x = (ex + cleared * dx) as u8;
            board.units[e].y = (ey + cleared * dy) as u8;

            destroy_train_path_tile(board, nxu, nyu, &mut result);

            // Train_Move applies ordinary one-point weapon damage to the
            // locomotive after the partial charge. Preserve shield/frozen/
            // armor/ACID semantics and mirror the logical pawn state across
            // its extra-space entry.
            if board.units[p].shield() {
                board.units[p].set_shield(false);
                board.units[e].set_shield(false);
            } else if board.units[p].frozen() {
                board.units[p].set_frozen(false);
                board.units[e].set_frozen(false);
            } else {
                let actual: i8 = if board.units[p].acid() {
                    2
                } else if board.units[p].armor() {
                    0
                } else {
                    1
                };
                board.units[p].hp -= actual;
                board.units[e].hp = board.units[p].hp;
            }
            transition_destroyed_supply_train(board);
            return result;
        }
    }

    // Path clear — advance both tiles 2 forward.
    board.units[p].x = (px + 2 * dx) as u8;
    board.units[p].y = (py + 2 * dy) as u8;
    board.units[e].x = (ex + 2 * dx) as u8;
    board.units[e].y = (ey + 2 * dy) as u8;
    result
}

/// Replace a destroyed moving train with the mission's live stopped variant.
///
/// Reuse the two fixed board slots but assign a fresh logical uid, matching
/// Mission_Train:StopTrain's RemovePawn + AddPawn transition and allowing
/// uid-level death accounting to observe the original train's death exactly
/// once. The fresh pawn clears statuses/intent and remains non-pushable.
pub(crate) fn transition_destroyed_supply_train(board: &mut Board) -> bool {
    let mut pair: Option<(usize, usize, &'static str, bool)> = None;

    for p in 0..board.unit_count as usize {
        let primary = &board.units[p];
        if primary.is_extra_tile() || primary.hp > 0 {
            continue;
        }
        let (damaged_type, armored) = match primary.type_name_str() {
            "Train_Pawn" => ("Train_Damaged", false),
            "Train_Armored" => ("Train_Armored_Damaged", true),
            _ => continue,
        };
        if let Some(e) = (0..board.unit_count as usize).find(|&e| {
            e != p
                && board.units[e].uid == primary.uid
                && board.units[e].is_extra_tile()
        }) {
            pair = Some((p, e, damaged_type, armored));
            break;
        }
    }

    let Some((p, e, damaged_type, armored)) = pair else {
        return false;
    };

    let old_primary = board.units[p];
    let old_extra = board.units[e];
    let offset_x = old_extra.x as i8 - old_primary.x as i8;
    let offset_y = old_extra.y as i8 - old_primary.y as i8;
    let mut new_uid: u16 = 1;
    for i in 0..board.unit_count as usize {
        new_uid = new_uid.max(board.units[i].uid.saturating_add(1));
    }

    let mut shared_flags = UnitFlags::empty();
    if old_primary.massive() {
        shared_flags |= UnitFlags::MASSIVE;
    }
    if armored {
        shared_flags |= UnitFlags::ARMOR;
    }

    let mut primary = Unit {
        uid: new_uid,
        x: old_primary.x,
        y: old_primary.y,
        hp: 1,
        max_hp: 1,
        team: Team::Player,
        flags: shared_flags,
        queued_target_x: -1,
        queued_target_y: -1,
        queued_target_raw_x: -1,
        queued_target_raw_y: -1,
        queued_origin_x: -1,
        queued_origin_y: -1,
        ..Unit::default()
    };
    primary.set_type_name(damaged_type);

    let extra_x = (old_primary.x as i8 + offset_x) as u8;
    let extra_y = (old_primary.y as i8 + offset_y) as u8;
    let mut extra = Unit {
        uid: new_uid,
        x: extra_x,
        y: extra_y,
        hp: 1,
        max_hp: 1,
        team: Team::Player,
        flags: shared_flags | UnitFlags::EXTRA_TILE,
        queued_target_x: -1,
        queued_target_y: -1,
        queued_target_raw_x: -1,
        queued_target_raw_y: -1,
        queued_origin_x: -1,
        queued_origin_y: -1,
        ..Unit::default()
    };
    extra.set_type_name(damaged_type);

    board.units[p] = primary;
    board.units[e] = extra;
    true
}

/// Replace Mission_Hacking's hostile Cannon Bot after the facility is gone.
///
/// The shipped mission callback removes the old `Snowtank1` pawn and adds a
/// fresh `Snowtank1_Player` on the same tile, explicitly copying only Shield.
/// Reuse the fixed board slot, assign a fresh logical uid, and reset every
/// other status/intent field through `Unit::default()`. The bridge does not
/// expose Mission_Hacking's BotID/HackID on legacy payloads, so require both
/// exact bridge-authored IDs and fail closed when either is missing.
pub(crate) fn transition_hacked_cannon_bot(board: &mut Board) -> bool {
    if board.mission_id != "Mission_Hacking" {
        return false;
    }
    let (Some(bot_uid), Some(facility_uid)) = (
        board.mission_hacking_bot_id,
        board.mission_hacking_hack_id,
    ) else {
        return false;
    };
    if board.units[..board.unit_count as usize]
        .iter()
        .any(|unit| unit.uid == facility_uid && unit.hp > 0)
    {
        return false;
    }

    let Some(bot_idx) = (0..board.unit_count as usize).find(|&i| {
        let unit = &board.units[i];
        unit.uid == bot_uid
            && unit.hp > 0
            && unit.team != Team::Player
            && unit.type_name_str() == "Snowtank1"
    }) else {
        return false;
    };

    let old_bot = board.units[bot_idx];
    let max_uid = board.units[..board.unit_count as usize]
        .iter()
        .map(|unit| unit.uid)
        .max()
        .unwrap_or(0);
    let Some(new_uid) = max_uid.checked_add(1) else {
        return false;
    };

    let mut flags = UnitFlags::PUSHABLE | UnitFlags::ACTIVE | UnitFlags::CAN_MOVE;
    if old_bot.shield() {
        flags |= UnitFlags::SHIELD;
    }
    let mut player_bot = Unit {
        uid: new_uid,
        x: old_bot.x,
        y: old_bot.y,
        hp: 1,
        max_hp: 1,
        team: Team::Player,
        move_speed: 3,
        base_move: 3,
        flags,
        weapon: WeaponId(WId::SnowtankAtk1 as u16),
        queued_target_x: -1,
        queued_target_y: -1,
        queued_target_raw_x: -1,
        queued_target_raw_y: -1,
        queued_origin_x: -1,
        queued_origin_y: -1,
        ..Unit::default()
    };
    player_bot.set_type_name("Snowtank1_Player");
    board.units[bot_idx] = player_bot;
    board.mission_hacking_bot_id = Some(new_uid);
    true
}

fn destroy_train_path_tile(
    board: &mut Board,
    x: u8,
    y: u8,
    result: &mut ActionResult,
) {
    if let Some(idx) = board.any_unit_at(x, y) {
        let tname = board.units[idx].type_name_str();
        if tname != "Train_Pawn" && tname != "Train_Armored" && tname != "Train_Armored_Damaged" {
            if board.units[idx].hp > 0 {
                let hp_removed = board.units[idx].hp.max(0) as i32;
                let was_enemy = board.units[idx].is_enemy();
                let was_player_mech =
                    board.units[idx].is_player() && board.units[idx].is_mech();
                board.units[idx].hp = 0;
                if was_enemy {
                    result.enemy_damage_dealt += hp_removed;
                    result.record_enemy_kill(
                        unit_counts_for_mission_kill(
                            board.mission_id.as_str(),
                            &board.units[idx],
                        )
                    );
                    on_enemy_death(board, idx, result);
                } else if was_player_mech {
                    result.mech_damage_taken += hp_removed;
                    result.mechs_killed += 1;
                }
            }
        }
    }

    let idx = xy_to_idx(x, y);
    let is_unique = (board.unique_buildings & (1u64 << idx)) != 0;
    let mut lost = 0u8;
    {
        let tile = board.tile_mut(x, y);
        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
            lost = tile.building_hp;
            tile.building_hp = 0;
            if !is_unique {
                tile.terrain = Terrain::Rubble;
            }
        } else if tile.terrain == Terrain::Mountain {
            tile.building_hp = 0;
            tile.terrain = Terrain::Rubble;
        }
    }
    if lost > 0 {
        let grid_loss = settle_building_grid_loss(
            board,
            idx,
            lost,
            true,
            is_unique,
            DamageSource::Weapon,
        );
        board.grid_power = board.grid_power.saturating_sub(grid_loss);
        result.buildings_damaged += lost as i32;
        result.buildings_lost += 1;
        result.grid_damage += grid_loss as i32;
    }
}

/// Trace projectile from enemy position in queued direction.
/// Returns (hit_x, hit_y) or None.
fn find_projectile_target(
    board: &Board,
    ex: u8,
    ey: u8,
    orig_x: u8,
    orig_y: u8,
    qtx: i8,
    qty: i8,
    raw_target: Option<(i8, i8)>,
) -> Option<(u8, u8)> {
    let (dx, dy) = projectile_delta_from_queued_or_current(
        ex, ey, orig_x, orig_y, qtx, qty, raw_target,
    )?;
    find_projectile_target_in_direction(board, ex, ey, dx, dy)
}

/// Return the tile that an enemy's queued intent threatens on the current
/// board. Most bridge intents already name their impact tile. Totem intents
/// instead retain the adjacent cardinal direction tile so their projectile
/// can re-run GetProjectileEnd when it resolves.
pub(crate) fn queued_enemy_threat_target(board: &Board, enemy: &Unit) -> Option<(u8, u8)> {
    if enemy.queued_target_x < 0 || enemy.queued_target_y < 0 {
        return None;
    }

    let enemy_wid = enemy_weapon_for_type(enemy.type_name_str());
    if matches!(enemy_wid, WId::TotemAtk1 | WId::TotemAtk2 | WId::TotemAtkB) {
        let queued_origin = queued_origin_for_attack(enemy, (enemy.x, enemy.y));
        let raw_queued_target = if enemy.flags.contains(UnitFlags::QUEUED_RAW_TARGET_SET) {
            Some((enemy.queued_target_raw_x, enemy.queued_target_raw_y))
        } else {
            None
        };
        return find_projectile_target(
            board,
            enemy.x,
            enemy.y,
            queued_origin.0,
            queued_origin.1,
            enemy.queued_target_x,
            enemy.queued_target_y,
            raw_queued_target,
        );
    }

    if in_bounds(enemy.queued_target_x, enemy.queued_target_y) {
        Some((enemy.queued_target_x as u8, enemy.queued_target_y as u8))
    } else {
        None
    }
}

fn cardinal_offset(from_x: u8, from_y: u8, qtx: i8, qty: i8) -> Option<(i8, i8)> {
    if qtx < 0 || qty < 0 { return None; }
    let dx = qtx - from_x as i8;
    let dy = qty - from_y as i8;
    if (dx != 0) == (dy != 0) { return None; }
    Some((dx, dy))
}

fn cardinal_delta(from_x: u8, from_y: u8, qtx: i8, qty: i8) -> Option<(i8, i8)> {
    let (dx, dy) = cardinal_offset(from_x, from_y, qtx, qty)?;
    Some((dx.signum(), dy.signum()))
}

fn projectile_delta_from_queued(orig_x: u8, orig_y: u8, qtx: i8, qty: i8) -> Option<(i8, i8)> {
    // Compute direction from ORIGINAL position to queued target.
    // Preserves cardinal attack direction after mech pushes.
    // INVARIANT: queued_target is relative to the original position (bridge
    // normalizes piQueuedShot against piOrigin when reading a mid-turn board).
    // The delta may be a full same-row/column offset; signum recovers direction.
    cardinal_delta(orig_x, orig_y, qtx, qty)
}

fn projectile_delta_from_queued_or_current(
    ex: u8,
    ey: u8,
    orig_x: u8,
    orig_y: u8,
    qtx: i8,
    qty: i8,
    raw_target: Option<(i8, i8)>,
) -> Option<(i8, i8)> {
    // The reconciled queued target is expressed from the attacker's CURRENT
    // tile. Raw piQueuedShot is save-derived and anchored to piOrigin, but can
    // remain stale after a native DIR_FLIP. Reconcile all three views:
    // agreement identifies either a normalized or legacy payload; otherwise
    // a valid current-frame target wins and raw is only the collapse fallback.
    let current_delta = cardinal_delta(ex, ey, qtx, qty);
    let origin_delta = projectile_delta_from_queued(orig_x, orig_y, qtx, qty);
    let raw_delta = raw_target.and_then(|(raw_qtx, raw_qty)| {
        projectile_delta_from_queued(orig_x, orig_y, raw_qtx, raw_qty)
    });

    if let Some(raw_delta) = raw_delta {
        if current_delta == Some(raw_delta) {
            return current_delta;
        }
        if origin_delta == Some(raw_delta) {
            return Some(raw_delta);
        }
        if current_delta.is_some() {
            return current_delta;
        }
        return Some(raw_delta);
    }

    current_delta.or(origin_delta)
}

fn queued_cardinal_offset_from_raw_or_current(
    ex: u8,
    ey: u8,
    orig_x: u8,
    orig_y: u8,
    qtx: i8,
    qty: i8,
    raw_target: Option<(i8, i8)>,
) -> Option<(i8, i8)> {
    let current_offset = cardinal_offset(ex, ey, qtx, qty);
    let origin_offset = cardinal_offset(orig_x, orig_y, qtx, qty);
    let raw_offset = raw_target.and_then(|(raw_qtx, raw_qty)| {
        cardinal_offset(orig_x, orig_y, raw_qtx, raw_qty)
    });

    if let Some(raw_offset) = raw_offset {
        if current_offset == Some(raw_offset) {
            return current_offset;
        }
        if origin_offset == Some(raw_offset) {
            return Some(raw_offset);
        }
        if current_offset.is_some() {
            return current_offset;
        }
        return Some(raw_offset);
    }

    // Legacy payloads without raw piQueuedShot store the full offset against
    // the recorded origin. Preserve that compatibility before falling back to
    // an unambiguous current-frame offset.
    origin_offset.or(current_offset)
}

fn find_projectile_target_in_direction(board: &Board, ex: u8, ey: u8, dx: i8, dy: i8) -> Option<(u8, u8)> {
    // Trace from CURRENT position in the original direction.
    // If the projectile walks off the board without hitting anything,
    // fall back to the last valid (on-board) tile — matches the game's
    // GetProjectileEnd which steps back after going off-board.
    let mut last_valid: Option<(u8, u8)> = None;
    for i in 1..8i8 {
        let nx = ex as i8 + dx * i;
        let ny = ey as i8 + dy * i;
        if !in_bounds(nx, ny) { break; }
        let nxu = nx as u8;
        let nyu = ny as u8;

        let tile = board.tile(nxu, nyu);
        if tile.terrain == Terrain::Mountain { return Some((nxu, nyu)); }
        if tile.terrain == Terrain::Building && tile.building_hp > 0 { return Some((nxu, nyu)); }
        if board.unit_at(nxu, nyu).is_some() { return Some((nxu, nyu)); }

        last_valid = Some((nxu, nyu));
    }
    last_valid
}

fn projectile_dir_from_queued_or_current(
    ex: u8,
    ey: u8,
    orig_x: u8,
    orig_y: u8,
    qtx: i8,
    qty: i8,
    raw_target: Option<(i8, i8)>,
) -> Option<usize> {
    let (dx, dy) = projectile_delta_from_queued_or_current(
        ex, ey, orig_x, orig_y, qtx, qty, raw_target,
    )?;
    DIRS.iter().position(|&(ddx, ddy)| ddx == dx && ddy == dy)
}

fn apply_projectile_grapple(
    board: &mut Board,
    attacker_idx: usize,
    target_idx: Option<usize>,
    hit_x: u8,
    hit_y: u8,
    dir: usize,
    hit_was_object: bool,
    direct_hit_killed_target: bool,
    result: &mut ActionResult,
) {
    if let Some(target_idx) = target_idx {
        if target_idx == attacker_idx
            || (board.units[target_idx].hp <= 0 && !direct_hit_killed_target)
            || !board.units[target_idx].pushable()
        {
            return;
        }

        let pull_dir = opposite_dir(dir);
        let (ax, ay) = (board.units[attacker_idx].x, board.units[attacker_idx].y);
        for _ in 0..8 {
            let (cx, cy) = (board.units[target_idx].x, board.units[target_idx].y);
            if (cx as i16 - ax as i16).abs() + (cy as i16 - ay as i16).abs() <= 1 {
                break;
            }
            apply_push(board, cx, cy, pull_dir, result);
            if board.units[target_idx].hp <= 0 && !direct_hit_killed_target {
                break;
            }
            let (nx, ny) = (board.units[target_idx].x, board.units[target_idx].y);
            if nx == cx && ny == cy {
                break;
            }
        }
        return;
    }

    if !hit_was_object {
        return;
    }

    let (dx, dy) = DIRS[dir];
    let stop_x = hit_x as i8 - dx;
    let stop_y = hit_y as i8 - dy;
    if !in_bounds(stop_x, stop_y) {
        return;
    }
    let (ax, ay) = (board.units[attacker_idx].x, board.units[attacker_idx].y);
    if stop_x as u8 == ax && stop_y as u8 == ay {
        return;
    }
    board.units[attacker_idx].x = stop_x as u8;
    board.units[attacker_idx].y = stop_y as u8;
    apply_teleport_on_land(board, attacker_idx);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::serde_bridge::board_from_json;
    use crate::simulate::{apply_damage, simulate_move, simulate_weapon};

    fn add_enemy_with_type(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8, type_name: &str, qtx: i8, qty: i8) -> usize {
        let mut unit = Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            queued_target_x: qtx,
            queued_target_y: qty,
            weapon_damage: 0,
            ..Default::default()
        };
        unit.set_type_name(type_name);
        board.add_unit(unit)
    }

    fn default_orig_pos(board: &Board) -> [(u8, u8); 16] {
        let mut pos = [(0u8, 0u8); 16];
        for i in 0..board.unit_count as usize {
            pos[i] = (board.units[i].x, board.units[i].y);
        }
        pos
    }

    #[test]
    fn test_pre_attack_smoke_still_cancels_enemy_attack() {
        let mut board = Board::default();
        board.grid_power = 6;
        board.grid_power_max = 7;
        board.tile_mut(5, 1).terrain = Terrain::Building;
        board.tile_mut(5, 1).building_hp = 2;
        board.tile_mut(5, 2).set_smoke(true);

        let mosquito = add_enemy_with_type(&mut board, 130, 5, 2, 2, "Mosquito1", 5, 1);
        board.units[mosquito].weapon_damage = 1;
        board.units[mosquito].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(5, 1).building_hp, 2);
        assert_eq!(board.grid_power, 6);
        assert_eq!(result.grid_damage, 0);
    }

    #[test]
    fn test_snowmine_attack_moves_and_leaves_freeze_mine_without_damage() {
        let mut board = Board::default();
        board.grid_power = 6;
        board.grid_power_max = 7;

        let snowmine =
            add_enemy_with_type(&mut board, 131, 3, 3, 1, "Snowmine1", 3, 5);
        board.units[snowmine]
            .flags
            .insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!((board.units[snowmine].x, board.units[snowmine].y), (3, 5));
        assert!(board.tile(3, 3).freeze_mine());
        assert_eq!(board.grid_power, 6);
        assert_eq!(result.grid_damage, 0);
        assert_eq!(result.buildings_damaged, 0);
    }

    #[test]
    fn test_smoke_does_not_cancel_snowmine_attack_move() {
        let mut board = Board::default();
        board.tile_mut(2, 2).set_smoke(true);

        // Snowmine2 shares SnowmineAtk1; exercise the type-family prefix in
        // addition to the base mission pawn covered above.
        let snowmine =
            add_enemy_with_type(&mut board, 132, 2, 2, 1, "Snowmine2", 4, 2);
        board.units[snowmine]
            .flags
            .insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!((board.units[snowmine].x, board.units[snowmine].y), (4, 2));
        assert!(board.tile(2, 2).freeze_mine());
        assert_eq!(result.grid_damage, 0);
    }

    #[test]
    fn test_webbed_snowmine_attack_move_is_inert() {
        let mut board = Board::default();
        let snowmine =
            add_enemy_with_type(&mut board, 133, 2, 2, 1, "Snowmine1", 4, 2);
        board.units[snowmine]
            .flags
            .insert(UnitFlags::HAS_QUEUED_ATTACK);
        board.units[snowmine].set_web(true);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!((board.units[snowmine].x, board.units[snowmine].y), (2, 2));
        assert!(!board.tile(2, 2).freeze_mine());
        assert_eq!(result.grid_damage, 0);
    }

    #[test]
    fn test_observatory_selected_record_drives_firefly_queue_direction() {
        // Windows build 13725832 selected/queue campaign, all three armed
        // captures: Firefly1 commits aiDest=(5,4), aiTarget=(4,4), then the
        // queue stores origin=(5,4), target/queuedShot=(4,4), skill=1.
        let mut board = Board::default();
        board.grid_power = 4;
        board.grid_power_max = 7;
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;

        let firefly = add_enemy_with_type(
            &mut board,
            1303,
            5,
            4,
            3,
            "Firefly1",
            4,
            4,
        );
        board.units[firefly].weapon_damage = 1;
        board.units[firefly].queued_origin_x = 5;
        board.units[firefly].queued_origin_y = 4;
        board.units[firefly].queued_target_raw_x = 4;
        board.units[firefly].queued_target_raw_y = 4;
        board.units[firefly].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
        );

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.grid_power, 3);
        assert_eq!(result.grid_damage, 1);
        assert_eq!(board.tile(3, 4).building_hp, 0);
    }

    #[test]
    fn test_acid_storm_enemy_phase_refreshes_fresh_enemy_spawns_and_keeps_prior_acid_after_death() {
        let mut board = Board::default();
        board.mission_id = "Mission_AcidStorm".to_string();
        add_enemy_with_type(&mut board, 90, 1, 1, 3, "Storm_Generator", -1, -1);
        let spider = add_enemy_with_type(&mut board, 91, 3, 1, 2, "Spider1", 3, 3);
        board.units[spider].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        let egg = board.unit_at(3, 3).expect("Spider attack should spawn a WebbEgg");
        assert_eq!(board.units[egg].type_name_str(), "WebbEgg1");
        assert!(
            board.units[egg].acid(),
            "the active ACID Storm refresh must cover fresh enemy spawns"
        );

        // Once the controller is gone, source UpdateMission stops rain but
        // never clears ACID already applied to existing pawns.
        board.units[0].hp = 0;
        let retained = egg;
        let second_spider = add_enemy_with_type(&mut board, 92, 5, 1, 2, "Spider1", 5, 3);
        board.units[second_spider]
            .flags
            .insert(UnitFlags::HAS_QUEUED_ATTACK);
        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(
            board.units[retained].acid(),
            "stopping the storm must not remove prior ACID"
        );
        let fresh = board.unit_at(5, 3).expect("second Spider attack should spawn a WebbEgg");
        assert!(
            !board.units[fresh].acid(),
            "a dead Storm_Generator must not acidify fresh spawns"
        );
    }

    #[test]
    fn test_snowart_and_botboss_queued_attacks_cancel_beyond_range_five() {
        for (uid, type_name, expected_damage) in [
            (134, "Snowart1", 1),
            (135, "BotBoss", 2),
        ] {
            let mut board = Board::default();
            board.grid_power = 6;
            board.grid_power_max = 7;
            board.tile_mut(0, 3).terrain = Terrain::Building;
            board.tile_mut(0, 3).building_hp = 2;

            let attacker =
                add_enemy_with_type(&mut board, uid, 6, 3, 5, type_name, 0, 3);
            board.units[attacker].weapon_damage = expected_damage;
            board.units[attacker]
                .flags
                .insert(UnitFlags::HAS_QUEUED_ATTACK);

            let orig = default_orig_pos(&board);
            let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

            assert_eq!(
                board.tile(0, 3).building_hp,
                2,
                "{type_name} must not resolve a queued artillery hit at distance 6"
            );
            assert_eq!(board.grid_power, 6);
            assert_eq!(result.grid_damage, 0);
        }
    }

    #[test]
    fn test_crab_scarab_queued_artillery_respects_exact_range() {
        for type_name in ["Scarab1", "Scarab2", "Crab1", "Crab2"] {
            for (target_x, should_hit) in [(2, true), (1, false)] {
                let mut board = Board::default();
                board.grid_power = 7;
                board.grid_power_max = 7;
                board.tile_mut(target_x, 3).terrain = Terrain::Building;
                board.tile_mut(target_x, 3).building_hp = 1;
                let attacker = add_enemy_with_type(
                    &mut board,
                    140,
                    7,
                    3,
                    5,
                    type_name,
                    target_x as i8,
                    3,
                );
                board.units[attacker]
                    .flags
                    .insert(UnitFlags::HAS_QUEUED_ATTACK);

                let orig = default_orig_pos(&board);
                let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

                assert_eq!(
                    board.tile(target_x, 3).building_hp,
                    if should_hit { 0 } else { 1 },
                    "{type_name} range {} result disagrees with Lua range 2..5",
                    7 - target_x,
                );
                assert_eq!(result.grid_damage > 0, should_hit);
            }
        }
    }

    #[test]
    fn test_terratide_wave_smokes_without_damage_and_cancels_queued_attack() {
        let input = r#"{
            "mission_id": "Mission_Terratide",
            "env_type": "tidal_or_cataclysm",
            "tiles": [
                {"x": 5, "y": 1, "terrain": "building", "building_hp": 2},
                {"x": 2, "y": 3, "terrain": "building", "building_hp": 2}
            ],
            "units": [
                {
                    "uid": 171,
                    "type": "Scorpion1",
                    "x": 5,
                    "y": 2,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 6,
                    "weapons": ["ScorpionAtk1"],
                    "queued_target": [5, 1],
                    "has_queued_attack": true,
                    "weapon_damage": 1
                },
                {
                    "uid": 2,
                    "type": "MirrorMech",
                    "x": 4,
                    "y": 4,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 1,
                    "mech": true,
                    "active": false,
                    "weapons": ["Brute_Mirrorshot"]
                }
            ],
            "grid_power": 4,
            "grid_power_max": 7,
            "spawning_tiles": [],
            "environment_danger_v2": [
                [5, 2, 1, 1, 1],
                [5, 1, 1, 1, 1],
                [2, 3, 1, 1, 1],
                [4, 4, 1, 1, 1]
            ]
        }"#;

        let (mut board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("Terratide bridge JSON parses");
        assert_eq!(board.env_danger, 0, "smoke lane must not be damage danger");
        assert!(board.is_env_smoke(5, 2));

        // Prove the queued attack is armed: without the smoke wave the same
        // parsed Scorpion line damages its adjacent target building.
        let mut no_wave = board.clone();
        no_wave.env_smoke = 0;
        let no_wave_orig = default_orig_pos(&no_wave);
        simulate_enemy_attacks(&mut no_wave, &no_wave_orig, &WEAPONS);
        assert_eq!(no_wave.tile(5, 1).building_hp, 1);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(5, 1).building_hp, 2, "queued attack is smoke-cancelled");
        assert_eq!(board.tile(2, 3).building_hp, 2, "wave does not damage buildings");
        assert_eq!(board.grid_power, 4);
        assert_eq!(result.grid_damage, 0);

        let scorpion = board.units.iter().find(|u| u.uid == 171).unwrap();
        let mirror = board.units.iter().find(|u| u.uid == 2).unwrap();
        assert_eq!(scorpion.hp, 3, "wave does not damage enemies");
        assert_eq!(mirror.hp, 3, "wave does not damage mechs");
        for &(x, y) in &[(5, 2), (5, 1), (2, 3), (4, 4)] {
            assert!(board.tile(x, y).smoke(), "Terratide should smoke ({x},{y})");
        }
    }

    #[test]
    fn test_enemy_attack_smoke_does_not_cancel_later_queued_attack() {
        let mut board = Board::default();
        board.grid_power = 6;
        board.grid_power_max = 7;
        board.boost_psion = true;
        board.tile_mut(5, 1).terrain = Terrain::Building;
        board.tile_mut(5, 1).building_hp = 2;

        add_enemy_with_type(&mut board, 126, 0, 0, 1, "Jelly_Boost1", -1, -1);
        let smoker = add_enemy_with_type(&mut board, 129, 5, 3, 2, "Mosquito1", 5, 2);
        board.units[smoker].weapon_damage = 1;
        board.units[smoker].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        let later = add_enemy_with_type(&mut board, 130, 5, 2, 2, "Mosquito1", 5, 1);
        board.units[later].weapon_damage = 1;
        board.units[later].set_shield(true);
        board.units[later].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        board.attack_order = vec![129, 130];

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(board.tile(5, 2).smoke(), "first Mosquito should smoke F3");
        assert_eq!(board.units[later].hp, 2, "shield should absorb the first hit");
        assert!(!board.units[later].shield(), "shield should be consumed");
        assert_eq!(board.tile(5, 1).building_hp, 0);
        assert_eq!(board.tile(5, 1).terrain, Terrain::Rubble);
        assert_eq!(board.grid_power, 4);
        assert_eq!(result.grid_damage, 2);
    }

    #[test]
    fn test_bouncer_attack_damages_proto_bomb() {
        let mut board = Board::default();
        let bomb_idx = board.add_unit(Unit {
            uid: 398,
            x: 5,
            y: 4,
            hp: 1,
            max_hp: 1,
            team: Team::Player,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });
        board.units[bomb_idx].set_type_name("ProtoBomb");

        let bouncer_idx = add_enemy_with_type(&mut board, 402, 4, 4, 3, "Bouncer1", 5, 4);
        board.units[bouncer_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(
            board.units[bomb_idx].hp <= 0,
            "Bouncer queued into a ProtoBomb should destroy the 1 HP protected unit"
        );
    }

    #[test]
    fn test_displaced_standard_melee_reaims_from_current_position() {
        let mut board = Board::default();
        let tele_idx = board.add_unit(Unit {
            uid: 2,
            x: 4,
            y: 3,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::MASSIVE | UnitFlags::PUSHABLE,
            ..Default::default()
        });
        let scorpion_idx = add_enemy_with_type(&mut board, 493, 4, 4, 6, "Scorpion2", 4, 2);
        board.units[scorpion_idx].weapon_damage = 3;
        board.units[scorpion_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let mut orig = default_orig_pos(&board);
        orig[tele_idx] = (3, 5);
        orig[scorpion_idx] = (4, 3);

        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(
            board.units[tele_idx].hp <= 0,
            "Scorpion2 should preserve original melee direction and hit E4"
        );
    }

    #[test]
    fn test_displaced_scorpion_prefers_normalized_current_target_over_stale_origin() {
        let mut board = Board::default();
        let tank_idx = board.add_unit(Unit {
            uid: 92,
            x: 6,
            y: 1,
            hp: 1,
            max_hp: 1,
            team: Team::Player,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });
        board.units[tank_idx].set_type_name("Archive_Tank");

        // Miner Inconvenience run 20260709_134054_884, Mission_Tanks turn 4:
        // Scorpion was displaced from G3 to G1. The bridge normalized the
        // live target to G2 (6,1), while retaining piOrigin G3 (5,1) and raw
        // piQueuedShot G4 (4,1). Live struck the adjacent tank at G2. Reading
        // direction from queued_origin -> normalized target reverses the hit.
        let scorpion_idx = add_enemy_with_type(&mut board, 102, 7, 1, 1, "Scorpion1", 6, 1);
        board.units[scorpion_idx].queued_origin_x = 5;
        board.units[scorpion_idx].queued_origin_y = 1;
        board.units[scorpion_idx].queued_target_raw_x = 4;
        board.units[scorpion_idx].queued_target_raw_y = 1;
        board.units[scorpion_idx].weapon_damage = 1;
        board.units[scorpion_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
        );

        let mut orig = default_orig_pos(&board);
        orig[scorpion_idx] = (5, 1);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(
            board.units[tank_idx].hp <= 0,
            "normalized current target should make the displaced Scorpion hit G2"
        );
    }

    #[test]
    fn test_displaced_blob_boss_retargets_queued_damage_by_offset() {
        let mut board = Board::default();
        board.grid_power = 7;
        board.grid_power_max = 7;
        board.tile_mut(5, 7).terrain = Terrain::Building;
        board.tile_mut(5, 7).building_hp = 2;
        board.tile_mut(6, 7).terrain = Terrain::Building;
        board.tile_mut(6, 7).building_hp = 2;

        // Live Ramming Speed regression: Large Goo was queued B3 -> A3, then
        // got pushed to B2 and attacked A2.
        let goo_idx = add_enemy_with_type(&mut board, 1029, 6, 6, 3, "BlobBoss", 5, 7);
        board.units[goo_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let mut orig = default_orig_pos(&board);
        orig[goo_idx] = (5, 6);

        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(5, 7).building_hp, 2, "old A3 target should survive");
        assert_eq!(board.tile(6, 7).building_hp, 0, "shifted A2 target should be hit");
    }

    #[test]
    fn test_perpendicular_push_then_laser_uses_raw_cardinal_direction() {
        let mut board = Board::default();
        board.grid_power = 7;
        board.grid_power_max = 7;
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 2;

        let laser_idx = add_enemy_with_type(&mut board, 1031, 4, 4, 3, "Snowlaser1", 3, 4);
        board.units[laser_idx].queued_origin_x = 4;
        board.units[laser_idx].queued_origin_y = 4;
        board.units[laser_idx].queued_target_raw_x = 3;
        board.units[laser_idx].queued_target_raw_y = 4;
        board.units[laser_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
        );

        let mut push_result = ActionResult::default();
        apply_push(&mut board, 4, 4, 2, &mut push_result);
        assert_eq!((board.units[laser_idx].x, board.units[laser_idx].y), (4, 3));
        assert_eq!(
            (board.units[laser_idx].queued_target_x, board.units[laser_idx].queued_target_y),
            (3, 3),
        );

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(
            board.tile(3, 3).building_hp,
            0,
            "the displaced Laser-Bot must still fire west instead of cancelling a false diagonal",
        );
    }

    #[test]
    fn test_displaced_laser_prefers_live_target_over_stale_raw_direction() {
        let mut board = Board::default();
        board.grid_power = 7;
        board.grid_power_max = 7;
        for x in [3, 5] {
            board.tile_mut(x, 3).terrain = Terrain::Building;
            board.tile_mut(x, 3).building_hp = 2;
        }

        let laser_idx = add_enemy_with_type(&mut board, 1034, 4, 4, 3, "Snowlaser1", 5, 4);
        board.units[laser_idx].queued_origin_x = 4;
        board.units[laser_idx].queued_origin_y = 4;
        // Raw save intent is west, but reconciled live queued_target is east
        // after a prior native DIR_FLIP.
        board.units[laser_idx].queued_target_raw_x = 3;
        board.units[laser_idx].queued_target_raw_y = 4;
        board.units[laser_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
        );

        let mut push_result = ActionResult::default();
        apply_push(&mut board, 4, 4, 2, &mut push_result);
        assert_eq!((board.units[laser_idx].x, board.units[laser_idx].y), (4, 3));
        assert_eq!(
            (board.units[laser_idx].queued_target_x, board.units[laser_idx].queued_target_y),
            (5, 3),
        );

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(5, 3).building_hp, 0, "live east target must be hit");
        assert_eq!(board.tile(3, 3).building_hp, 2, "stale raw west target must survive");
    }

    #[test]
    fn test_perpendicular_push_then_charge_uses_raw_cardinal_direction() {
        let mut board = Board::default();
        board.grid_power = 7;
        board.grid_power_max = 7;
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 2;

        let beetle_idx = add_enemy_with_type(&mut board, 1032, 4, 4, 4, "Beetle1", 3, 4);
        board.units[beetle_idx].queued_origin_x = 4;
        board.units[beetle_idx].queued_origin_y = 4;
        board.units[beetle_idx].queued_target_raw_x = 3;
        board.units[beetle_idx].queued_target_raw_y = 4;
        board.units[beetle_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
        );

        let mut push_result = ActionResult::default();
        apply_push(&mut board, 4, 4, 2, &mut push_result);
        assert_eq!((board.units[beetle_idx].x, board.units[beetle_idx].y), (4, 3));
        assert_eq!(
            (board.units[beetle_idx].queued_target_x, board.units[beetle_idx].queued_target_y),
            (3, 3),
        );

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(
            board.tile(3, 3).building_hp,
            1,
            "the displaced Beetle must charge west instead of cancelling a false diagonal",
        );
        assert_eq!((board.units[beetle_idx].x, board.units[beetle_idx].y), (4, 3));
    }

    #[test]
    fn test_perpendicular_push_then_blob_damage_uses_raw_offset() {
        let mut board = Board::default();
        board.grid_power = 7;
        board.grid_power_max = 7;
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 4;
        board.tile_mut(3, 2).terrain = Terrain::Building;
        board.tile_mut(3, 2).building_hp = 4;

        let goo_idx = add_enemy_with_type(&mut board, 1033, 4, 4, 3, "BlobBoss", 3, 4);
        board.units[goo_idx].queued_origin_x = 4;
        board.units[goo_idx].queued_origin_y = 4;
        board.units[goo_idx].queued_target_raw_x = 3;
        board.units[goo_idx].queued_target_raw_y = 4;
        board.units[goo_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
        );

        let mut push_result = ActionResult::default();
        apply_push(&mut board, 4, 4, 2, &mut push_result);
        assert_eq!((board.units[goo_idx].x, board.units[goo_idx].y), (4, 3));
        assert_eq!(
            (board.units[goo_idx].queued_target_x, board.units[goo_idx].queued_target_y),
            (3, 3),
        );

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(3, 3).building_hp, 0, "the west target should take Goo damage");
        assert_eq!(
            board.tile(3, 2).building_hp,
            4,
            "the stale-origin diagonal must not redirect Goo damage northwest",
        );
    }

    #[test]
    fn test_displaced_blob_prefers_live_target_over_stale_raw_offset() {
        let mut board = Board::default();
        board.grid_power = 7;
        board.grid_power_max = 7;
        for x in [3, 5] {
            board.tile_mut(x, 3).terrain = Terrain::Building;
            board.tile_mut(x, 3).building_hp = 4;
        }

        let goo_idx = add_enemy_with_type(&mut board, 1035, 4, 4, 3, "BlobBoss", 5, 4);
        board.units[goo_idx].queued_origin_x = 4;
        board.units[goo_idx].queued_origin_y = 4;
        board.units[goo_idx].queued_target_raw_x = 3;
        board.units[goo_idx].queued_target_raw_y = 4;
        board.units[goo_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
        );

        let mut push_result = ActionResult::default();
        apply_push(&mut board, 4, 4, 2, &mut push_result);
        assert_eq!((board.units[goo_idx].x, board.units[goo_idx].y), (4, 3));
        assert_eq!(
            (board.units[goo_idx].queued_target_x, board.units[goo_idx].queued_target_y),
            (5, 3),
        );

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(5, 3).building_hp, 0, "live east target must take Goo damage");
        assert_eq!(board.tile(3, 3).building_hp, 4, "stale raw west target must survive");
    }

    #[test]
    fn test_displaced_scarab_artillery_retargets_by_full_offset() {
        let mut board = Board::default();
        board.grid_power = 7;
        board.grid_power_max = 7;
        board.tile_mut(2, 1).terrain = Terrain::Building;
        board.tile_mut(2, 1).building_hp = 1;
        board.tile_mut(3, 1).terrain = Terrain::Building;
        board.tile_mut(3, 1).building_hp = 1;

        // Same live board: Scarab shifted G3 -> G2, so G6 shifted to G5.
        let scarab_idx = add_enemy_with_type(&mut board, 1030, 6, 1, 2, "Scarab1", 2, 1);
        board.units[scarab_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let mut orig = default_orig_pos(&board);
        orig[scarab_idx] = (5, 1);

        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(2, 1).building_hp, 1, "old G6 target should survive");
        assert_eq!(board.tile(3, 1).building_hp, 0, "shifted G5 target should be hit");
    }

    #[test]
    fn test_displaced_scarab_artillery_prefers_raw_offset_for_acid_bulk() {
        let mut board = Board::default();
        board.grid_power = 7;
        board.grid_power_max = 7;
        let bulk_idx = board.add_unit(Unit {
            uid: 0,
            x: 2,
            y: 6,
            hp: 1,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ACID,
            weapon: WeaponId(WId::BruteTcRicochet as u16),
            ..Default::default()
        });
        board.units[bulk_idx].set_type_name("BulkMech");
        let blocker_idx = board.add_unit(Unit {
            uid: 2,
            x: 4,
            y: 6,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::MASSIVE | UnitFlags::PUSHABLE,
            ..Default::default()
        });
        board.units[blocker_idx].set_type_name("FourwayMech");

        // Arachnophiles run 20260702_104642_726, Mission_Acid turn 3:
        // Scarab's normalized queued target pointed one tile short, but the
        // raw queued target preserved the live attacker-relative artillery
        // offset. Live hit ACID Bulk at B6 for doubled damage.
        let scarab_idx = add_enemy_with_type(&mut board, 2787, 6, 6, 2, "Scarab1", 2, 6);
        board.units[scarab_idx].queued_origin_x = 5;
        board.units[scarab_idx].queued_origin_y = 6;
        board.units[scarab_idx].queued_target_raw_x = 1;
        board.units[scarab_idx].queued_target_raw_y = 6;
        board.units[scarab_idx].weapon_damage = 1;
        board.units[scarab_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
        );

        let mut orig = default_orig_pos(&board);
        orig[scarab_idx] = (5, 6);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(board.units[bulk_idx].hp <= 0, "raw-offset Scarab shot should kill ACID Bulk");
        assert_eq!(board.units[blocker_idx].hp, 2, "artillery should ignore the intervening mech");
    }

    #[test]
    fn test_pushed_projectile_with_origin_tile_target_fires_from_current_position() {
        let mut board = Board::default();
        let mirror_idx = board.add_unit(Unit {
            uid: 1,
            x: 3,
            y: 6,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::MASSIVE | UnitFlags::PUSHABLE,
            ..Default::default()
        });
        board.units[mirror_idx].set_type_name("MirrorMech");

        // Live Frozen Titans regression: Firefly1 was queued from (4,6) into
        // MirrorMech, then Mirror Shot pushed it to (5,6). The bridge read
        // queued_target=(4,6), queued_origin=(4,6); live still fired from
        // current (5,6) through (4,6) into MirrorMech at (3,6).
        let firefly_idx = add_enemy_with_type(&mut board, 105, 5, 6, 2, "Firefly1", 4, 6);
        board.units[firefly_idx].queued_origin_x = 4;
        board.units[firefly_idx].queued_origin_y = 6;
        board.units[firefly_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK | UnitFlags::QUEUED_ORIGIN_SET,
        );

        let mut orig = default_orig_pos(&board);
        orig[firefly_idx] = (4, 6);

        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(
            board.units[mirror_idx].hp, 2,
            "Firefly projectile should infer direction from current position when target equals queued origin"
        );
    }

    #[test]
    fn test_seismic_flips_displaced_firefly_with_collapsed_normalized_target() {
        let mut board = Board::default();
        let mirror_idx = board.add_unit(Unit {
            uid: 1,
            x: 2,
            y: 2,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::MASSIVE | UnitFlags::PUSHABLE,
            ..Default::default()
        });
        board.units[mirror_idx].set_type_name("MirrorMech");
        let hydrant_idx = board.add_unit(Unit {
            uid: 2,
            x: 5,
            y: 1,
            hp: 2,
            max_hp: 3,
            team: Team::Player,
            weapon: WeaponId(WId::ScienceKoCrack as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ACTIVE,
            ..Default::default()
        });
        board.units[hydrant_idx].set_type_name("HydrantMech");

        // Chaos Roll Unfair run 20260710_013601_568, Mission_Train turn 2:
        // Mirror Shot displaced Firefly2 from (4,2) to (5,2).  The bridge's
        // normalized target became the stale queued origin (4,2), while raw
        // piQueuedShot=(3,2) retained the live -x projectile vector toward
        // Mirror.  Seismic at (5,2) must flip the projectile to +x.
        let firefly_idx = add_enemy_with_type(&mut board, 166, 5, 2, 5, "Firefly2", 4, 2);
        board.units[firefly_idx].max_hp = 6;
        board.units[firefly_idx].weapon_damage = 3;
        board.units[firefly_idx].queued_origin_x = 4;
        board.units[firefly_idx].queued_origin_y = 2;
        board.units[firefly_idx].queued_target_raw_x = 3;
        board.units[firefly_idx].queued_target_raw_y = 2;
        board.units[firefly_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
        );

        simulate_weapon(
            &mut board,
            hydrant_idx,
            WId::ScienceKoCrack,
            5,
            2,
        );
        assert_eq!(board.units[firefly_idx].hp, 4);
        assert_eq!(
            (board.units[firefly_idx].queued_target_x, board.units[firefly_idx].queued_target_y),
            (6, 2),
        );

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(
            board.units[mirror_idx].hp, 3,
            "Seismic-flipped Firefly projectile should fire away from MirrorMech"
        );
    }

    #[test]
    fn test_enemy_phase_bump_debt_flushes_before_player_turn() {
        let mut board = Board::default();
        board.grid_power = 7;
        board.grid_power_max = 7;
        board.tile_mut(3, 5).terrain = Terrain::Building;
        board.tile_mut(3, 5).building_hp = 2;

        let rock_idx = board.add_unit(Unit {
            uid: 80,
            x: 4,
            y: 5,
            hp: 1,
            max_hp: 1,
            team: Team::Neutral,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });
        board.units[rock_idx].set_type_name("BombRock");

        let dung_idx = add_enemy_with_type(&mut board, 81, 5, 5, 5, "Dung2", 4, 5);
        board.units[dung_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(board.units[rock_idx].hp <= 0, "Tumblebug should kill the queued BombRock");
        assert_eq!(board.tile(3, 5).building_hp, 1, "BombRock explosion should damage C5");
        assert_eq!(board.grid_power, 6, "enemy-phase bump debt must settle before player turn");
        assert_eq!(board.deferred_bump_grid_debt[xy_to_idx(3, 5)], 0);
        assert_eq!(result.grid_damage, 1);
    }

    #[test]
    fn test_conveyor_moves_enemy_before_projectile_attack() {
        let mut board = Board::default();
        board.mission_id = "Mission_Belt".to_string();
        board.grid_power = 6;
        board.grid_power_max = 7;
        board.tile_mut(1, 5).terrain = Terrain::Building;
        board.tile_mut(1, 5).building_hp = 1;
        board.tile_mut(5, 5).conveyor_dir = 3; // bridge conveyor3: x - 1

        let moth_idx = add_enemy_with_type(&mut board, 91, 5, 5, 3, "Moth1", 1, 5);
        board.units[moth_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        let mut orig = default_orig_pos(&board);
        orig[moth_idx] = (4, 5);

        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!((board.units[moth_idx].x, board.units[moth_idx].y), (5, 5),
            "Moth should ride the belt, fire, then push itself back");
        assert_eq!(board.tile(1, 5).building_hp, 0,
            "conveyor-shifted Moth should re-line the C7 building shot");
        assert_eq!(board.grid_power, 5);
    }

    #[test]
    fn test_conveyor_dir_two_capture_bumps_mech_into_building() {
        let mut board = Board::default();
        board.mission_id = "Mission_BeltRandom".to_string();
        board.grid_power = 5;
        board.grid_power_max = 7;
        board.tile_mut(3, 5).conveyor_dir = 0; // raw engine dir 2 after serde normalization
        board.tile_mut(3, 6).terrain = Terrain::Building;
        board.tile_mut(3, 6).building_hp = 2;
        add_mech_unit(&mut board, 2, 3, 5, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(
            (board.units[0].x, board.units[0].y),
            (3, 5),
            "blocked conveyor push should leave the mech on the belt tile"
        );
        assert_eq!(board.units[0].hp, 2);
        assert_eq!(board.tile(3, 6).building_hp, 1);
        assert_eq!(board.grid_power, 4);
    }

    #[test]
    fn test_beltrandom_queued_attack_resolves_before_random_belt_tick() {
        let mut board = Board::default();
        board.mission_id = "Mission_BeltRandom".to_string();
        board.grid_power = 6;
        board.grid_power_max = 7;
        board.tile_mut(4, 1).terrain = Terrain::Building;
        board.tile_mut(4, 1).building_hp = 1;
        board.tile_mut(4, 2).conveyor_dir = 3;

        let bouncer_idx = add_enemy_with_type(&mut board, 9, 4, 2, 1, "Bouncer1", 4, 1);
        board.units[bouncer_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(
            board.tile(4, 1).building_hp,
            0,
            "Mission_BeltRandom attack-order can let the queued Bouncer hit before belts"
        );
        assert_eq!(board.grid_power, 5);
    }

    #[test]
    fn test_conveyor_collision_with_same_tick_mover_does_not_bump_damage() {
        let mut board = Board::default();
        board.mission_id = "Mission_BeltRandom".to_string();
        board.tile_mut(2, 2).conveyor_dir = 1;
        board.tile_mut(4, 2).conveyor_dir = 3;
        add_mech_unit(&mut board, 0, 2, 2, 3);
        let bouncer_idx = add_enemy_with_type(&mut board, 9, 4, 2, 1, "Bouncer1", 4, 1);

        let mut result = ActionResult::default();
        simulate_conveyor_belts(&mut board, &mut result);

        assert_eq!(
            (board.units[0].x, board.units[0].y),
            (3, 2),
            "first belt rider should occupy the shared destination"
        );
        assert_eq!(
            (board.units[bouncer_idx].x, board.units[bouncer_idx].y),
            (4, 2),
            "second belt rider should remain in place when the shared tile is occupied"
        );
        assert_eq!(
            board.units[bouncer_idx].hp,
            1,
            "blocked same-tick belt collision should not kill the Bouncer"
        );
    }

    #[test]
    fn test_mission_missiles_decorative_conveyor_does_not_move_enemy_attack() {
        let mut board = Board::default();
        board.mission_id = "Mission_Missiles".to_string();
        board.grid_power = 3;
        board.grid_power_max = 7;
        board.tile_mut(4, 6).terrain = Terrain::Building;
        board.tile_mut(4, 6).building_hp = 2;
        board.tile_mut(3, 6).conveyor_dir = 0;

        let mosquito_idx = add_enemy_with_type(&mut board, 1426, 3, 6, 4, "Mosquito2", 4, 6);
        board.units[mosquito_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(
            (board.units[mosquito_idx].x, board.units[mosquito_idx].y),
            (3, 6),
            "decorative Landfill conveyor sprite at B5 should not move Mosquito2"
        );
        assert_eq!(
            board.tile(4, 6).building_hp,
            0,
            "B4 building should be hit when Mission_Missiles has Env_Null"
        );
        assert_eq!(board.grid_power, 1);
    }

    #[test]
    fn test_burrower_slam_hits_perpendicular_three_tile_row() {
        for (type_name, center_hp, flank_hp, expected_center, expected_flank) in [
            ("Burrower1", 2, 1, 1, 0),
            ("Burrower2", 2, 2, 0, 0),
        ] {
            let mut board = Board::default();
            // Live regression shape: Burrower at (5,4) attacks west toward
            // center (4,4). The engine hits (4,4) plus flanks (4,3)/(4,5).
            for (bx, by, hp) in [
                (4, 4, center_hp),
                (4, 3, flank_hp),
                (4, 5, flank_hp),
                (3, 4, 1),
            ] {
                board.tile_mut(bx, by).terrain = Terrain::Building;
                board.tile_mut(bx, by).building_hp = hp;
            }
            let idx = add_enemy_with_type(&mut board, 24, 5, 4, 3, type_name, 4, 4);
            board.units[idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

            let orig = default_orig_pos(&board);
            simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

            assert_eq!(board.tile(4, 4).building_hp, expected_center, "{type_name} should damage the center tile");
            assert_eq!(board.tile(4, 3).building_hp, expected_flank, "{type_name} should damage one perpendicular flank");
            assert_eq!(board.tile(4, 5).building_hp, expected_flank, "{type_name} should damage the other perpendicular flank");
            assert_eq!(board.tile(3, 4).building_hp, 1, "{type_name} should not hit a forward line tile");
        }
    }

    #[test]
    fn test_nonlethal_bump_damage_cancels_alpha_burrower_slam() {
        let mut board = Board::default();
        let boss = add_enemy_with_type(&mut board, 1124, 4, 3, 3, "BlobberBoss", -1, -1);
        board.units[boss].set_fire(true);
        let burrower =
            add_enemy_with_type(&mut board, 1197, 5, 4, 5, "Burrower2", 4, 4);
        board.units[burrower]
            .flags
            .insert(UnitFlags::HAS_QUEUED_ATTACK | UnitFlags::ACID | UnitFlags::FIRE);
        board.units[burrower].queued_origin_x = 5;
        board.units[burrower].queued_origin_y = 4;
        board.units[burrower]
            .flags
            .insert(UnitFlags::QUEUED_ORIGIN_SET);

        let mut bump = ActionResult::default();
        apply_damage(
            &mut board,
            5,
            4,
            1,
            &mut bump,
            DamageSource::Bump,
        );

        assert_eq!(board.units[burrower].hp, 4);
        assert_eq!(board.units[burrower].queued_target_x, -1);
        assert!(!board.units[burrower].has_queued_attack());
        assert!(board.units[burrower].burrowed());
        assert_eq!(board.unit_at(5, 4), None);
        assert_eq!(board.any_unit_at(5, 4), None);
        assert!(!board.units[burrower].fire());
        assert!(board.units[burrower].acid(), "ACID persists underground");
        let projected = crate::turn_projection::board_to_json(&board, &[]);
        assert!(
            !projected.contains("\"uid\":1197"),
            "an underground Burrower must be absent from projected board snapshots",
        );

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(
            board.units[boss].hp, 2,
            "the burning boss should take only its Fire tick; the canceled Burrower flank must not land",
        );
    }

    #[test]
    fn test_fire_tick_makes_surviving_burrower_retreat_before_its_attack() {
        let mut board = Board::default();
        board.grid_power = 6;
        board.grid_power_max = 7;
        board.tile_mut(4, 4).terrain = Terrain::Building;
        board.tile_mut(4, 4).building_hp = 2;

        let burrower =
            add_enemy_with_type(&mut board, 24, 5, 4, 3, "Burrower1", 4, 4);
        board.units[burrower]
            .flags
            .insert(UnitFlags::HAS_QUEUED_ATTACK | UnitFlags::FIRE);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[burrower].hp, 2);
        assert!(board.units[burrower].burrowed());
        assert!(!board.units[burrower].fire());
        assert!(!board.units[burrower].has_queued_attack());
        assert_eq!(board.tile(4, 4).building_hp, 2);
        assert_eq!(result.grid_damage, 0);
    }

    #[test]
    fn test_environment_damage_makes_surviving_burrower_retreat_before_attack() {
        let mut board = Board::default();
        board.grid_power = 6;
        board.grid_power_max = 7;
        board.env_danger = 1u64 << xy_to_idx(5, 4);
        board.tile_mut(4, 4).terrain = Terrain::Building;
        board.tile_mut(4, 4).building_hp = 2;

        let burrower =
            add_enemy_with_type(&mut board, 24, 5, 4, 3, "Burrower1", 4, 4);
        board.units[burrower]
            .flags
            .insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[burrower].hp, 2);
        assert!(board.units[burrower].burrowed());
        assert_eq!(board.tile(4, 4).building_hp, 2);
        assert_eq!(result.grid_damage, 0);
    }

    #[test]
    fn test_shielded_burrower_does_not_retreat_without_real_damage() {
        let mut board = Board::default();
        let burrower =
            add_enemy_with_type(&mut board, 24, 5, 4, 3, "Burrower1", 4, 4);
        board.units[burrower]
            .flags
            .insert(UnitFlags::HAS_QUEUED_ATTACK | UnitFlags::SHIELD);

        let mut result = ActionResult::default();
        apply_damage(
            &mut board,
            5,
            4,
            1,
            &mut result,
            DamageSource::Weapon,
        );

        assert_eq!(board.units[burrower].hp, 3);
        assert!(!board.units[burrower].shield());
        assert!(board.units[burrower].has_queued_attack());
        assert_eq!(board.units[burrower].queued_target_x, 4);
    }

    #[test]
    fn test_lethal_burrower_damage_is_a_kill_not_a_retreat() {
        let mut board = Board::default();
        let burrower =
            add_enemy_with_type(&mut board, 24, 5, 4, 1, "Burrower1", 4, 4);
        board.units[burrower]
            .flags
            .insert(UnitFlags::HAS_QUEUED_ATTACK);

        let mut result = ActionResult::default();
        apply_damage(
            &mut board,
            5,
            4,
            1,
            &mut result,
            DamageSource::Weapon,
        );

        assert_eq!(board.units[burrower].hp, 0);
        assert!(!board.units[burrower].burrowed());
        assert_eq!(result.enemies_killed, 1);
    }

    #[test]
    fn test_scarab_artillery_hits_target_directly() {
        let mut board = Board::default();
        // Scarab at (0,0) targeting building at (4,0) — artillery arcs over obstacles
        board.tile_mut(2, 0).terrain = Terrain::Mountain; // obstacle between
        board.tile_mut(4, 0).terrain = Terrain::Building;
        board.tile_mut(4, 0).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 0, 0, 3, "Scarab1", 4, 0);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        // Artillery should hit building at (4,0) directly, ignoring mountain
        assert_eq!(board.tile(4, 0).building_hp, 0, "Scarab artillery should hit building through mountain");
    }

    #[test]
    fn test_scarab_boss_artillery_pushes_adjacent_tiles() {
        let mut board = Board::default();
        board.tile_mut(4, 0).terrain = Terrain::Building;
        board.tile_mut(4, 0).building_hp = 2;

        let boss = add_enemy_with_type(&mut board, 1, 0, 0, 6, "ScarabBoss", 4, 0);
        board.units[boss].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        let pushed = add_mech_unit(&mut board, 2, 5, 0, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(4, 0).building_hp, 0, "Scarab Leader artillery should deal 4 center damage");
        assert_eq!((board.units[pushed].x, board.units[pushed].y), (6, 0),
            "adjacent unit should be pushed outward from the artillery target");
        assert_eq!(board.units[pushed].hp, 3, "adjacent push is zero-damage");
    }

    #[test]
    fn test_starfish_hits_diagonal_tiles_only() {
        let mut board = Board::default();
        let idx = add_enemy_with_type(&mut board, 10, 3, 3, 2, "Starfish1", 3, 3);
        board.units[idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        for &(x, y) in &[(4, 4), (4, 2), (2, 2), (2, 4)] {
            board.tile_mut(x, y).terrain = Terrain::Building;
            board.tile_mut(x, y).building_hp = 1;
        }
        for &(x, y) in &[(3, 4), (4, 3), (3, 2), (2, 3)] {
            board.tile_mut(x, y).terrain = Terrain::Building;
            board.tile_mut(x, y).building_hp = 1;
        }

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        for &(x, y) in &[(4, 4), (4, 2), (2, 2), (2, 4)] {
            assert_eq!(board.tile(x, y).building_hp, 0, "diagonal tile should be damaged");
        }
        for &(x, y) in &[(3, 4), (4, 3), (3, 2), (2, 3)] {
            assert_eq!(board.tile(x, y).building_hp, 1, "cardinal tile should not be damaged");
        }
    }

    #[test]
    fn test_starfish_leader_diagonal_damage_and_cardinal_push() {
        let mut board = Board::default();
        let idx = add_enemy_with_type(&mut board, 20, 3, 3, 6, "StarfishBoss", 3, 3);
        board.units[idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let pushed_idx = board.add_unit(Unit {
            uid: 21,
            x: 3,
            y: 4,
            hp: 4,
            max_hp: 4,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::MASSIVE | UnitFlags::PUSHABLE,
            ..Default::default()
        });
        let diagonal_idx = board.add_unit(Unit {
            uid: 22,
            x: 4,
            y: 4,
            hp: 5,
            max_hp: 5,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::MASSIVE | UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!((board.units[pushed_idx].x, board.units[pushed_idx].y), (3, 5),
            "cardinal adjacent unit should be pushed outward");
        assert_eq!(board.units[pushed_idx].hp, 4,
            "cardinal push is zero-damage unless it bumps");
        assert_eq!(board.units[diagonal_idx].hp, 2,
            "diagonal unit should take the leader's 3 damage");
    }

    #[test]
    fn test_starfish_variants_dispatch_exact_diagonal_damage() {
        for (pawn_type, expected_damage) in [
            ("Starfish1", 1),
            ("Starfish2", 2),
            ("StarfishBoss", 3),
        ] {
            let mut board = Board::default();
            let idx =
                add_enemy_with_type(&mut board, 30, 3, 3, 6, pawn_type, 3, 3);
            board.units[idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
            board.tile_mut(4, 4).terrain = Terrain::Building;
            board.tile_mut(4, 4).building_hp = 4;

            let orig = default_orig_pos(&board);
            simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

            assert_eq!(
                board.tile(4, 4).building_hp,
                4 - expected_damage,
                "{pawn_type} must dispatch its exact Lua diagonal damage",
            );
        }
    }

    #[test]
    fn test_terratide_index_reconstructs_markerless_current_smoke_lane() {
        let mut board = Board::default();
        board.mission_id = "Mission_Terratide".to_string();
        board.env_tides_index = Some(3);
        board.env_tides_planned = Some(true);
        for x in 0u8..8 {
            board.tile_mut(x, 4).terrain = Terrain::Building;
            board.tile_mut(x, 4).building_hp = 1;
        }
        assert_eq!(board.env_smoke, 0);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        for x in 0u8..8 {
            assert!(board.tile(x, 4).smoke(), "Index 3 should smoke ({x},4)");
        }
        assert!(!board.tile(0, 3).smoke());
        assert!(!board.tile(0, 5).smoke());
    }

    #[test]
    fn test_terratide_unplanned_index_does_not_reapply_smoke() {
        let mut board = Board::default();
        board.mission_id = "Mission_Terratide".to_string();
        board.env_tides_index = Some(3);
        board.env_tides_planned = Some(false);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!((0u8..8).all(|x| !board.tile(x, 4).smoke()));
    }

    #[test]
    fn test_mission_final_volcano_lava_converts_in_order_and_applies_survivor_rules() {
        let input = r#"{
            "mission_id":"Mission_Final",
            "env_type":"volcano",
            "mission_final_volcano":{
                "complete":true,"mode":2,"phase":1,
                "lava_start":[[1,2]],
                "locations":[[2,1],[3,1],[3,2],[3,3]],
                "planned":[[2,1],[3,1],[3,2],[3,3]]
            },
            "tiles":[
                {"x":2,"y":1,"terrain":"ground","smoke":true,"acid":true},
                {"x":3,"y":1,"terrain":"ground","fire":true},
                {"x":3,"y":2,"terrain":"ground"},
                {"x":3,"y":3,"terrain":"ground"}
            ],
            "units":[
                {"uid":10,"type":"Scorpion1","x":2,"y":1,"hp":3,"max_hp":3,
                 "team":6,"shield":true},
                {"uid":1,"type":"PunchMech","x":3,"y":1,"hp":3,"max_hp":3,
                 "team":1,"mech":true,"massive":true},
                {"uid":11,"type":"Hornet1","x":3,"y":2,"hp":2,"max_hp":2,
                 "team":6,"flying":true},
                {"uid":2,"type":"ShieldMech","x":3,"y":3,"hp":3,"max_hp":3,
                 "team":1,"mech":true,"massive":true,"shield":true}
            ],
            "environment_danger":[[2,1],[3,1],[3,2],[3,3]],
            "environment_danger_v2":[
                [2,1,0,0,0],[3,1,0,0,0],[3,2,0,0,0],[3,3,0,0,0]
            ],
            "spawning_tiles":[]
        }"#;
        let (mut board, ..) = board_from_json(input).expect("exact Lava payload parses");
        assert_eq!(board.env_volcano_mode, VOLCANO_LAVA);
        assert_eq!(board.env_volcano_locations, [17, 25, 26, 27]);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        for &(x, y) in &[(2, 1), (3, 1), (3, 2), (3, 3)] {
            assert_eq!(board.tile(x, y).terrain, Terrain::Lava);
            assert!(!board.tile(x, y).smoke());
            assert!(!board.tile(x, y).acid());
            assert!(!board.tile(x, y).on_fire());
        }
        assert_eq!(board.units[0].hp, 0, "ordinary grounded Vek drowns through Shield");
        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.units[1].hp, 3, "Massive mech survives new Lava");
        assert!(board.units[1].fire(), "Massive survivor catches Fire");
        assert_eq!(board.units[2].hp, 2, "flying Vek survives new Lava");
        assert!(board.units[2].fire(), "flying survivor catches Fire");
        assert_eq!(board.units[3].hp, 3);
        assert!(board.units[3].shield());
        assert!(!board.units[3].fire(), "Shield blocks terrain Fire status");
    }

    #[test]
    fn test_mission_final_volcano_rocks_kill_before_queued_attacks_and_leave_fire() {
        let input = r#"{
            "mission_id":"Mission_Final",
            "env_type":"volcano",
            "mission_final_volcano":{
                "complete":true,"mode":1,"phase":2,
                "lava_start":[[1,2]],
                "locations":[[2,3],[2,4],[4,2],[4,5]],
                "planned":[[2,3],[2,4],[4,2],[4,5]]
            },
            "tiles":[
                {"x":2,"y":3,"terrain":"ground"},
                {"x":2,"y":4,"terrain":"mountain","building_hp":2},
                {"x":4,"y":2,"terrain":"ground"},
                {"x":4,"y":5,"terrain":"lava"},
                {"x":2,"y":2,"terrain":"building","building_hp":2}
            ],
            "units":[
                {"uid":20,"type":"Hornet1","x":2,"y":3,"hp":2,"max_hp":2,
                 "team":6,"flying":true,"has_queued_attack":true,
                 "queued_target":[2,2],"weapons":["HornetAtk1"]}
            ],
            "attack_order":[20],
            "environment_danger":[[2,3],[2,4],[4,2],[4,5]],
            "environment_danger_v2":[
                [2,3,1,1,0],[2,4,1,1,0],[4,2,1,1,0],[4,5,1,1,0]
            ],
            "spawning_tiles":[]
        }"#;
        let (mut board, ..) = board_from_json(input).expect("exact Rocks payload parses");
        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.tile(2, 2).building_hp, 2, "Rocks resolve before Vek attacks");
        assert!(board.tile(2, 3).on_fire());
        assert_eq!(board.tile(2, 4).terrain, Terrain::Rubble);
        assert!(board.tile(2, 4).on_fire(), "destroyed mountain rubble burns");
        assert!(board.tile(4, 2).on_fire());
        assert_eq!(board.tile(4, 5).terrain, Terrain::Lava);
        assert!(!board.tile(4, 5).on_fire(), "Lava cannot host a separate Fire tile");
    }

    #[test]
    fn test_mission_final_cave_rocks_kill_flyer_before_attack_and_make_road() {
        let input = r#"{
            "mission_id":"Mission_Final_Cave","env_type":"final_cave","turn":1,
            "mission_final_cave":{
                "complete":true,"mode":1,"phase":1,"ordered":true,
                "instant":false,"water_target":true,
                "lava_path":[[2,0],[2,1],[2,2],[2,3]],
                "locations":[[2,2],[2,5],[5,2],[5,5]],
                "planned":[[2,2],[2,5],[5,2],[5,5]]
            },
            "tiles":[
                {"x":2,"y":1,"terrain":"building","building_hp":2},
                {"x":2,"y":2,"terrain":"water"},
                {"x":2,"y":5,"terrain":"mountain","building_hp":2},
                {"x":5,"y":2,"terrain":"chasm"},
                {"x":5,"y":5,"terrain":"forest"}
            ],
            "units":[
                {"uid":20,"type":"Hornet1","x":2,"y":2,"hp":2,"max_hp":2,
                 "team":6,"flying":true,"shield":true,"frozen":true,
                 "has_queued_attack":true,"queued_target":[2,1],
                 "weapons":["HornetAtk1"]}
            ],
            "attack_order":[20],
            "environment_danger":[[2,2],[2,5],[5,2],[5,5]],
            "environment_danger_v2":[
                [2,2,1,1,0],[2,5,1,1,0],[5,2,1,1,0],[5,5,1,1,0]
            ],
            "spawning_tiles":[]
        }"#;
        let (mut board, ..) = board_from_json(input).expect("exact Rocks payload parses");
        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.units[0].hp, 0, "DAMAGE_DEATH kills a frozen Shielded flyer");
        assert_eq!(board.tile(2, 1).building_hp, 2, "dead Vek never fires");
        for &(x, y) in &[(2u8, 2u8), (2, 5), (5, 2), (5, 5)] {
            assert_eq!(board.tile(x, y).terrain, Terrain::Ground);
            assert_eq!(board.tile(x, y).building_hp, 0);
        }
    }

    #[test]
    fn test_mission_final_cave_environment_kill_credit_excludes_minor_enemy() {
        let input = r#"{
            "mission_id":"Mission_Final_Cave","env_type":"final_cave","turn":1,
            "mission_final_cave":{
                "complete":true,"mode":1,"phase":1,"ordered":true,
                "instant":false,"water_target":true,
                "lava_path":[[2,0],[2,1],[2,2],[2,3]],
                "locations":[[2,2],[2,5]],
                "planned":[[2,2],[2,5]]
            },
            "tiles":[
                {"x":2,"y":2,"terrain":"ground"},
                {"x":2,"y":5,"terrain":"ground"}
            ],
            "units":[
                {"uid":20,"type":"Hornet1","x":2,"y":2,"hp":2,"max_hp":2,
                 "team":6,"flying":true},
                {"uid":21,"type":"Totem1","x":2,"y":5,"hp":1,"max_hp":1,
                 "team":6,"minor":true}
            ],
            "environment_danger":[[2,2],[2,5]],
            "environment_danger_v2":[[2,2,1,1,0],[2,5,1,1,0]],
            "spawning_tiles":[]
        }"#;
        let (mut board, ..) = board_from_json(input).expect("exact Rocks payload parses");
        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(result.enemies_killed, 2, "both enemy-team Pawns die");
        assert_eq!(
            result.mission_kills, 1,
            "native EVENT_ENEMY_KILLED excludes the Minor enemy"
        );
        assert!(board.units[..2].iter().all(|unit| unit.hp == 0));
    }

    #[test]
    fn test_mission_final_cave_tentacles_kill_all_mech_traits_and_make_lava() {
        let input = r#"{
            "mission_id":"Mission_Final_Cave","env_type":"final_cave","turn":2,
            "mission_final_cave":{
                "complete":true,"mode":2,"phase":2,"ordered":true,
                "instant":false,"water_target":false,
                "lava_path":[[2,0],[2,1],[2,2],[2,3]],
                "locations":[[5,1],[4,2],[4,4]],
                "planned":[[5,1],[4,2],[4,4]]
            },
            "tiles":[
                {"x":5,"y":1,"terrain":"ground","smoke":true},
                {"x":4,"y":2,"terrain":"water","acid":true},
                {"x":4,"y":4,"terrain":"forest"}
            ],
            "units":[
                {"uid":0,"type":"PunchMech","x":5,"y":1,"hp":4,"max_hp":4,
                 "team":1,"mech":true,"massive":true,"shield":true},
                {"uid":1,"type":"JetMech","x":4,"y":2,"hp":3,"max_hp":3,
                 "team":1,"mech":true,"flying":true},
                {"uid":2,"type":"IceMech","x":4,"y":4,"hp":3,"max_hp":3,
                 "team":1,"mech":true,"massive":true,"frozen":true}
            ],
            "environment_danger":[[5,1],[4,2],[4,4]],
            "environment_danger_v2":[
                [5,1,1,1,0],[4,2,1,1,0],[4,4,1,1,0]
            ],
            "spawning_tiles":[]
        }"#;
        let (mut board, ..) = board_from_json(input).expect("exact Lava payload parses");
        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(result.mechs_killed, 3);
        assert!(board.units[..3].iter().all(|unit| unit.hp == 0));
        assert!(!board.units[0].shield());
        assert!(!board.units[2].frozen());
        for &(x, y) in &[(5u8, 1u8), (4, 2), (4, 4)] {
            assert_eq!(board.tile(x, y).terrain, Terrain::Lava);
            assert_eq!(board.tile(x, y).building_hp, 0);
        }
    }

    #[test]
    fn test_sandstorm_markers_do_not_damage_mech_or_building() {
        let input = r#"{
            "mission_id": "Mission_Sandstorm",
            "env_type": "sandstorm",
            "tiles": [
                {"x": 2, "y": 2, "terrain": "building", "building_hp": 2}
            ],
            "units": [
                {
                    "uid": 1,
                    "type": "PunchMech",
                    "x": 3,
                    "y": 3,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 1,
                    "mech": true,
                    "active": false
                }
            ],
            "grid_power": 7,
            "grid_power_max": 7,
            "spawning_tiles": [],
            "environment_danger": [[2, 2], [3, 3]],
            "environment_danger_v2": [[2, 2, 1, 0, 0], [3, 3, 1, 0, 0]]
        }"#;

        let (mut board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("Sandstorm bridge JSON parses");
        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[0].hp, 3);
        assert_eq!(board.tile(2, 2).building_hp, 2);
        assert_eq!(board.grid_power, 7);
        assert_eq!(result.grid_damage, 0);
        assert_eq!(result.mech_damage_taken, 0);
    }

    #[test]
    fn test_nanostorm_applies_damage_and_acid_but_excludes_buildings() {
        let input = r#"{
            "mission_id": "Mission_NanoStorm",
            "env_type": "nanostorm",
            "tiles": [
                {"x": 2, "y": 2, "terrain": "building", "building_hp": 2}
            ],
            "units": [
                {
                    "uid": 1,
                    "type": "PunchMech",
                    "x": 3,
                    "y": 3,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 1,
                    "mech": true,
                    "active": false
                },
                {
                    "uid": 2,
                    "type": "Hornet1",
                    "x": 4,
                    "y": 4,
                    "hp": 2,
                    "max_hp": 2,
                    "team": 6,
                    "flying": true,
                    "active": false
                },
                {
                    "uid": 3,
                    "type": "ShieldMech",
                    "x": 6,
                    "y": 6,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 1,
                    "mech": true,
                    "shield": true,
                    "active": false
                },
                {
                    "uid": 4,
                    "type": "FrozenMech",
                    "x": 7,
                    "y": 7,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 1,
                    "mech": true,
                    "frozen": true,
                    "active": false
                }
            ],
            "grid_power": 7,
            "grid_power_max": 7,
            "spawning_tiles": [],
            "environment_danger_v2": [
                [2, 2, 1, 0, 0],
                [3, 3, 1, 0, 0],
                [4, 4, 1, 0, 0],
                [5, 5, 1, 0, 0],
                [6, 6, 1, 0, 0],
                [7, 7, 1, 0, 0]
            ]
        }"#;

        let (mut board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("NanoStorm bridge JSON parses");
        assert!(!board.is_env_danger(2, 2));
        assert!(board.is_env_danger_acid(3, 3));
        assert!(board.is_env_danger_acid(4, 4));
        assert!(board.is_env_danger_acid(5, 5));

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[0].hp, 2);
        assert!(board.units[0].acid());
        assert!(!board.units[0].frozen());
        assert_eq!(board.units[1].hp, 1);
        assert!(board.units[1].acid());
        assert_eq!(board.units[2].hp, 3);
        assert!(!board.units[2].shield());
        assert!(board.units[2].acid());
        assert_eq!(board.units[3].hp, 3);
        assert!(!board.units[3].frozen());
        assert!(board.units[3].acid());
        assert_eq!(board.tile(2, 2).building_hp, 2);
        assert_eq!(board.grid_power, 7);
        assert!(board.tile(5, 5).acid());
        assert_eq!(result.grid_damage, 0);
        assert_eq!(result.mech_damage_taken, 1);
        assert_eq!(result.enemy_damage_dealt, 1);
    }

    #[test]
    fn test_ice_storm_freezes_building_then_damage_only_thaws_it() {
        let mut board = Board::default();
        board.grid_power = 6;
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;
        board.env_freeze = 1u64 << xy_to_idx(3, 4);

        let orig = default_orig_pos(&board);
        let freeze_result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(board.tile(3, 4).frozen());
        assert_eq!(board.tile(3, 4).building_hp, 1);
        assert_eq!(board.grid_power, 6);
        assert_eq!(freeze_result.grid_damage, 0);

        let mut thaw_result = ActionResult::default();
        apply_damage(
            &mut board,
            3,
            4,
            1,
            &mut thaw_result,
            DamageSource::Weapon,
        );

        assert!(!board.tile(3, 4).frozen());
        assert_eq!(board.tile(3, 4).building_hp, 1);
        assert_eq!(board.grid_power, 6);
        assert_eq!(thaw_result.grid_damage, 0);
        assert!(thaw_result
            .events
            .iter()
            .any(|event| event == "building_thawed:3:4"));
    }

    #[test]
    fn test_ice_storm_shield_blocks_status_and_is_consumed() {
        let mut board = Board::default();
        let mut unit = Unit {
            uid: 7,
            x: 2,
            y: 2,
            hp: 2,
            max_hp: 2,
            team: Team::Enemy,
            ..Unit::default()
        };
        unit.set_shield(true);
        board.add_unit(unit);
        board.tile_mut(4, 4).terrain = Terrain::Mountain;
        board.tile_mut(4, 4).building_hp = 2;
        board.tile_mut(4, 4).set_shield(true);
        board.env_freeze =
            (1u64 << xy_to_idx(2, 2)) | (1u64 << xy_to_idx(4, 4));

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(!board.units[0].shield());
        assert!(!board.units[0].frozen());
        assert!(!board.tile(4, 4).shield());
        assert!(!board.tile(4, 4).frozen());
    }

    #[test]
    fn test_ice_storm_extinguishes_and_freezes_burning_unit_and_mountain() {
        let mut board = Board::default();
        let mut unit = Unit {
            uid: 7,
            x: 2,
            y: 2,
            hp: 2,
            max_hp: 2,
            team: Team::Enemy,
            ..Unit::default()
        };
        unit.set_fire(true);
        board.add_unit(unit);
        board.tile_mut(4, 4).terrain = Terrain::Mountain;
        board.tile_mut(4, 4).building_hp = 2;
        board.tile_mut(4, 4).set_on_fire(true);
        board.env_freeze =
            (1u64 << xy_to_idx(2, 2)) | (1u64 << xy_to_idx(4, 4));

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(!board.units[0].fire());
        assert!(board.units[0].frozen());
        assert!(!board.tile(4, 4).on_fire());
        assert!(board.tile(4, 4).frozen());
    }

    #[test]
    fn test_gastropod_projectile_keeps_traveling_after_target_moves() {
        let mut board = Board::default();
        board.grid_power = 6;
        board.tile_mut(1, 2).terrain = Terrain::Building;
        board.tile_mut(1, 2).building_hp = 1;
        add_enemy_with_type(&mut board, 99, 4, 2, 3, "Burnbug1", 3, 2);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(1, 2).building_hp, 0,
            "Burnbug/Gastropod hook should travel past the vacated first tile");
        assert_eq!(board.grid_power, 5,
            "The F7 building loss from run 20260504_210332_088 m01 t01 must be predicted");
    }

    #[test]
    fn test_alpha_burnbug_projectile_hits_mech_behind_empty_target_tile() {
        let mut board = Board::default();
        let mech_idx = board.add_unit(Unit {
            uid: 1,
            x: 4,
            y: 2,
            hp: 2,
            max_hp: 2,
            team: Team::Player,
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::PUSHABLE
                | UnitFlags::ARMOR,
            ..Default::default()
        });
        add_enemy_with_type(&mut board, 1535, 6, 2, 4, "Burnbug2", 5, 2);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[mech_idx].hp, 0,
            "Alpha Burnbug projectile should travel past empty F3 and kill armored Trimissile at F4");
        assert_eq!(result.mechs_killed, 1);
        assert_eq!(result.mech_damage_taken, 2);
    }

    #[test]
    fn test_gastropod_projectile_pulls_hit_unit_toward_attacker() {
        let mut board = Board::default();
        let target_idx = board.add_unit(Unit {
            uid: 2,
            x: 1,
            y: 2,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::MASSIVE | UnitFlags::PUSHABLE,
            ..Default::default()
        });
        add_enemy_with_type(&mut board, 99, 4, 2, 3, "Burnbug1", 3, 2);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[target_idx].hp, 2, "Hook deals 1 damage");
        assert_eq!((board.units[target_idx].x, board.units[target_idx].y), (3, 2),
            "Hook pulls the hit pawn until adjacent to the Gastropod");
    }

    #[test]
    fn test_lethal_gastropod_grapple_moves_corpse_before_blast_psion_burst() {
        let mut board = Board::default();
        board.grid_power = 5;
        board.grid_power_max = 7;
        board.blast_psion = true;
        board.tile_mut(3, 6).terrain = Terrain::Building;
        board.tile_mut(3, 6).building_hp = 2;
        board.tile_mut(5, 6).terrain = Terrain::Building;
        board.tile_mut(5, 6).building_hp = 2;
        board.tile_mut(5, 4).terrain = Terrain::Forest;
        board.tile_mut(5, 5).set_has_pod(true);

        let attacker_idx = add_enemy_with_type(
            &mut board, 359, 6, 5, 4, "Burnbug2", 5, 5,
        );
        add_enemy_with_type(&mut board, 360, 1, 1, 2, "Jelly_Explode1", -1, -1);
        let target_idx = add_enemy_with_type(
            &mut board, 361, 3, 5, 4, "Burnbug2", 3, 5,
        );
        board.units[target_idx].set_acid(true);
        board.attack_order = vec![359, 360, 361];

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(board.units[target_idx].hp <= 0);
        assert_eq!(
            board.units[attacker_idx].hp, 3,
            "Blast burst must damage the attacker beside the final corpse tile",
        );
        assert_eq!(
            board.tile(3, 6).building_hp, 2,
            "old death-tile neighbor must not receive the deferred burst",
        );
        assert_eq!(
            board.tile(5, 6).building_hp, 1,
            "final death-tile neighbor must receive the deferred burst",
        );
        assert_eq!(board.grid_power, 4);
        assert!(!board.tile(3, 5).acid(), "new ACID pool must leave the old tile");
        assert!(board.tile(5, 5).acid(), "ACID pool must follow the corpse");
        assert_eq!(board.tile(5, 4).terrain, Terrain::Ground);
        assert!(board.tile(5, 4).on_fire(), "Blast burst should ignite Forest");
        assert!(
            board.tile(5, 5).has_pod(),
            "dead corpse movement does not destroy a pod; the live emergent Vek does",
        );
    }

    #[test]
    fn test_burnbug_boss_uses_raw_queued_target_when_normalized_collapses() {
        let mut board = Board::default();
        board.grid_power = 6;
        board.grid_power_max = 7;
        board.tile_mut(0, 2).terrain = Terrain::Building;
        board.tile_mut(0, 2).building_hp = 1;

        let boss_idx = add_enemy_with_type(&mut board, 212, 4, 2, 4, "BurnbugBoss", 4, 2);
        board.units[boss_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
        );
        board.units[boss_idx].queued_origin_x = 4;
        board.units[boss_idx].queued_origin_y = 2;
        board.units[boss_idx].queued_target_raw_x = 3;
        board.units[boss_idx].queued_target_raw_y = 2;

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(0, 2).building_hp, 0);
        assert_eq!(board.grid_power, 5);
    }

    #[test]
    fn test_shaman_spawns_exact_totem_without_same_phase_attack() {
        let cases = [
            ("Shaman1", "Totem1", WId::TotemAtk1, 3),
            ("Shaman2", "Totem2", WId::TotemAtk2, 5),
        ];

        for (shaman_type, totem_type, totem_weapon, shaman_hp) in cases {
            let mut board = Board::default();
            board.grid_power = 2;
            board.grid_power_max = 2;
            board.tile_mut(3, 0).terrain = Terrain::Building;
            board.tile_mut(3, 0).building_hp = 1;

            let shaman_idx = add_enemy_with_type(
                &mut board,
                710,
                3,
                3,
                shaman_hp,
                shaman_type,
                3,
                1,
            );
            board.units[shaman_idx]
                .flags
                .insert(UnitFlags::HAS_QUEUED_ATTACK);

            let orig = default_orig_pos(&board);
            let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

            let totem_idx = board
                .unit_at(3, 1)
                .expect("Shaman artillery should place its Totem");
            let totem = &board.units[totem_idx];
            assert_eq!(totem.type_name_str(), totem_type);
            assert_eq!((totem.hp, totem.max_hp), (1, 1));
            assert_eq!(totem.team, Team::Enemy);
            assert_eq!((totem.move_speed, totem.base_move), (0, 0));
            assert!(totem.minor());
            assert!(totem.pushable());
            assert_eq!(totem.weapon, WeaponId(totem_weapon as u16));
            assert_eq!((totem.queued_target_x, totem.queued_target_y), (-1, -1));
            assert!(!totem.has_queued_attack());
            assert_eq!(board.tile(3, 0).building_hp, 1);
            assert_eq!(board.grid_power, 2);
            assert_eq!(result.grid_damage, 0);
        }
    }

    #[test]
    fn test_shaman_totem_spawn_fails_closed_on_occupied_or_blocked_target() {
        for blocked_by_terrain in [false, true] {
            let mut board = Board::default();
            let shaman_idx = add_enemy_with_type(
                &mut board,
                720,
                3,
                3,
                3,
                "Shaman1",
                3,
                1,
            );
            board.units[shaman_idx]
                .flags
                .insert(UnitFlags::HAS_QUEUED_ATTACK);

            if blocked_by_terrain {
                board.tile_mut(3, 1).terrain = Terrain::Water;
            } else {
                let blocker = Unit {
                    uid: 721,
                    x: 3,
                    y: 1,
                    hp: 3,
                    max_hp: 3,
                    team: Team::Player,
                    flags: UnitFlags::PUSHABLE | UnitFlags::IS_MECH,
                    ..Default::default()
                };
                board.add_unit(blocker);
            }

            let orig = default_orig_pos(&board);
            simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

            assert!(!board
                .units
                .iter()
                .take(board.unit_count as usize)
                .any(|unit| unit.type_name_str().starts_with("Totem")));
        }
    }

    #[test]
    fn test_spawned_shaman_totem_can_fire_and_self_destruct_next_phase() {
        let mut board = Board::default();
        board.grid_power = 2;
        board.grid_power_max = 2;
        board.tile_mut(0, 1).terrain = Terrain::Building;
        board.tile_mut(0, 1).building_hp = 1;

        let shaman_idx = add_enemy_with_type(
            &mut board,
            730,
            4,
            1,
            3,
            "Shaman1",
            2,
            1,
        );
        board.units[shaman_idx]
            .flags
            .insert(UnitFlags::HAS_QUEUED_ATTACK);
        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        let totem_idx = board.unit_at(2, 1).expect("Totem should spawn");
        board.units[shaman_idx].queued_target_x = -1;
        board.units[shaman_idx].queued_target_y = -1;
        board.units[shaman_idx]
            .flags
            .remove(UnitFlags::HAS_QUEUED_ATTACK);
        board.units[totem_idx].queued_target_x = 1;
        board.units[totem_idx].queued_target_y = 1;
        board.units[totem_idx].queued_origin_x = 2;
        board.units[totem_idx].queued_origin_y = 1;
        board.units[totem_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK | UnitFlags::QUEUED_ORIGIN_SET,
        );

        let next_orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &next_orig, &WEAPONS);

        assert_eq!(board.tile(0, 1).building_hp, 0);
        assert_eq!(board.grid_power, 1);
        assert!(board.units[totem_idx].hp <= 0);
    }

    #[test]
    fn test_totem_projectile_retraces_into_new_blocker_and_bumps_building() {
        let mut board = Board::default();
        board.grid_power = 2;
        board.grid_power_max = 2;
        board.tile_mut(2, 1).terrain = Terrain::Building;
        board.tile_mut(2, 1).building_hp = 1;

        let totem_idx = add_enemy_with_type(&mut board, 711, 4, 1, 1, "Totem1", 3, 1);
        board.units[totem_idx].weapon = WeaponId(WId::TotemAtk1 as u16);
        board.units[totem_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        board.units[totem_idx].flags.insert(UnitFlags::QUEUED_ORIGIN_SET);
        board.units[totem_idx].queued_origin_x = 4;
        board.units[totem_idx].queued_origin_y = 1;

        let wall_idx = board.add_unit(Unit {
            uid: 1,
            x: 3,
            y: 1,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::IS_MECH
                | UnitFlags::PUSHABLE
                | UnitFlags::MASSIVE
                | UnitFlags::ARMOR,
            ..Default::default()
        });

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(2, 1).building_hp, 0,
            "pushed WallMech should bump and destroy the building behind it");
        assert_eq!(board.grid_power, 1, "building bump loss should drop grid");
        assert_eq!(board.units[wall_idx].hp, 2,
            "armor blocks Totem weapon damage, but not the blocked-push bump");
        assert_eq!((board.units[wall_idx].x, board.units[wall_idx].y), (3, 1));
        assert!(board.units[totem_idx].hp <= 0, "Totem should self-destruct after firing");
    }

    #[test]
    fn test_totem_projectile_retraces_past_vacated_target_to_building() {
        // Chaos Roll Unfair run 20260710_013601_568, Mission_ShamanBoss
        // turn 1: TotemB at visual E3 queued west through Needle at E5.
        // Needle vacated before the enemy phase, exposing the 2-HP E6
        // building. Live re-ran GetProjectileEnd, destroyed E6, and spent the
        // final grid power.
        let mut board = Board::default();
        board.grid_power = 1;
        board.grid_power_max = 7;
        board.tile_mut(2, 3).terrain = Terrain::Building;
        board.tile_mut(2, 3).building_hp = 2;

        let totem_idx = add_enemy_with_type(&mut board, 252, 5, 3, 2, "TotemB", 4, 3);
        board.units[totem_idx].weapon = WeaponId(WId::TotemAtkB as u16);
        board.units[totem_idx].weapon_damage = 2;
        board.units[totem_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK | UnitFlags::QUEUED_ORIGIN_SET,
        );
        board.units[totem_idx].queued_origin_x = 5;
        board.units[totem_idx].queued_origin_y = 3;

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(2, 3).building_hp, 0,
            "TotemB projectile should continue through vacated E5 to E6");
        assert_eq!(board.grid_power, 0, "the 2-damage hit should spend the final grid");
        assert_eq!(result.buildings_lost, 1);
        assert!(board.units[totem_idx].hp <= 0, "TotemB should self-destruct after firing");
    }

    #[test]
    fn test_snowtank_mark_i_projectile_hits_line_target_and_sets_fire() {
        let mut board = Board::default();
        let pulse_idx = add_mech_unit(&mut board, 2, 2, 1, 3);
        add_enemy_with_type(&mut board, 97, 5, 1, 1, "Snowtank1", 4, 1);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[pulse_idx].hp, 2,
            "Cannon-Bot projectile should travel past the empty queued tile and hit PulseMech");
        assert!(board.units[pulse_idx].fire(),
            "Cannon 8R Mark I should set the hit unit on fire");
    }

    #[test]
    fn test_snowart_boom_uses_snowart_t_pattern() {
        let mut board = Board::default();
        board.grid_power = 4;
        board.grid_power_max = 7;
        for (bx, by) in [(1, 5), (2, 5), (0, 5)] {
            board.tile_mut(bx, by).terrain = Terrain::Building;
            board.tile_mut(bx, by).building_hp = 1;
        }
        add_enemy_with_type(&mut board, 2624, 1, 2, 1, "Snowart1_Boom", 1, 5);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(enemy_weapon_for_type("Snowart1_Boom"), WId::SnowartAtk1);
        assert_eq!(board.tile(1, 5).building_hp, 0, "target tile should be damaged");
        assert_eq!(board.tile(2, 5).building_hp, 0, "perpendicular lower tile should be damaged");
        assert_eq!(board.tile(0, 5).building_hp, 0, "perpendicular upper tile should be damaged");
        assert_eq!(board.grid_power, 1, "three 1-HP buildings should drop grid by 3");
    }

    #[test]
    fn test_bridge_attack_order_lets_snowlaser_fire_before_burnbug() {
        let mut board = Board::default();
        board.grid_power = 4;
        board.tile_mut(2, 2).terrain = Terrain::Building;
        board.tile_mut(2, 2).building_hp = 1;
        board.tile_mut(2, 3).terrain = Terrain::Forest;
        board.tile_mut(2, 4).terrain = Terrain::Forest;
        let bombling_idx = add_mech_unit(&mut board, 1, 2, 3, 3);

        let laser_idx = add_enemy_with_type(&mut board, 3806, 2, 4, 1, "Snowlaser1", 2, 3);
        let burnbug_idx = add_enemy_with_type(&mut board, 3805, 5, 4, 4, "Burnbug1", 4, 4);
        board.units[laser_idx].queued_origin_x = 2;
        board.units[laser_idx].queued_origin_y = 4;
        board.units[burnbug_idx].queued_origin_x = 5;
        board.units[burnbug_idx].queued_origin_y = 4;
        board.attack_order = vec![3806, 3805];

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[bombling_idx].hp, 1,
            "Snowlaser should fire first and hit Bombling for 2 before Burnbug kills it");
        assert!(board.units[bombling_idx].fire(),
            "Forest hit by the beam should leave Bombling on fire");
        assert_eq!(board.tile(2, 2).building_hp, 0,
            "Snowlaser beam should continue through Bombling and destroy the 1 HP building");
        assert!(board.units[laser_idx].hp <= 0,
            "Burnbug should still kill the Snowlaser later in the same enemy phase");
        assert_eq!(board.grid_power, 3);
    }

    #[test]
    fn test_moth_artillery_self_bounce_bumps_blocking_mech() {
        let mut board = Board::default();
        board.grid_power = 6;
        let pulse_idx = add_mech_unit(&mut board, 2, 5, 3, 3);
        let moth_idx = add_enemy_with_type(&mut board, 314, 4, 3, 3, "Moth1", 1, 3);
        board.units[moth_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        board.tile_mut(1, 3).terrain = Terrain::Building;
        board.tile_mut(1, 3).building_hp = 2;

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[pulse_idx].hp, 2,
            "Moth recoil should bump the mech behind it before artillery lands");
        assert_eq!(board.units[moth_idx].hp, 2,
            "Blocked self-bounce should also bump the Moth");
        assert_eq!((board.units[moth_idx].x, board.units[moth_idx].y), (4, 3),
            "Blocked recoil leaves the Moth in place");
        assert_eq!(board.tile(1, 3).building_hp, 1,
            "Moth artillery still damages its queued target after recoil");
    }

    #[test]
    fn test_moth_variants_enforce_exact_lua_range_and_damage() {
        for (pawn_type, distance, expected_damage) in [
            ("Moth1", 1u8, 0u8),
            ("Moth1", 2, 1),
            ("Moth2", 5, 3),
            ("Moth2", 6, 0),
        ] {
            let mut board = Board::default();
            let target_y = 1 + distance;
            let moth_idx = add_enemy_with_type(
                &mut board,
                50,
                1,
                1,
                4,
                pawn_type,
                1,
                target_y as i8,
            );
            board.units[moth_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
            board.tile_mut(1, target_y).terrain = Terrain::Building;
            board.tile_mut(1, target_y).building_hp = 4;

            let orig = default_orig_pos(&board);
            simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

            assert_eq!(
                board.tile(1, target_y).building_hp,
                4 - expected_damage,
                "{pawn_type} distance {distance} damage mismatch",
            );
            let expected_y = if expected_damage > 0 { 0 } else { 1 };
            assert_eq!(
                (board.units[moth_idx].x, board.units[moth_idx].y),
                (1, expected_y),
                "{pawn_type} must recoil only for a legal distance",
            );
        }
    }

    #[test]
    fn test_moth_artillery_killed_target_corpse_bumps_live_mech() {
        // Exact post-player shape from Chaos Roll Unfair run
        // 20260713_052159_731, Mission_Wind turn 4. Ignite pushed Alpha Moth
        // E5->F5 and Alpha Bouncer C5->B5. The displaced Moth retained its
        // original E5->A5 four-tile offset, so it fired F5->B5, killed the
        // Bouncer, and the Bouncer corpse bumped Ignite on A5.
        let mut board = Board::default();
        board.grid_power = 5;
        board.grid_power_max = 7;
        board.tile_mut(3, 1).terrain = Terrain::Building; // G5
        board.tile_mut(3, 1).building_hp = 2;

        let moth = add_enemy_with_type(&mut board, 813, 3, 2, 5, "Moth2", 3, 6);
        board.units[moth].set_fire(true);
        board.units[moth].queued_origin_x = 3;
        board.units[moth].queued_origin_y = 3;
        board.units[moth].queued_target_raw_x = 3;
        board.units[moth].queued_target_raw_y = 7;
        board.units[moth].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
        );

        let bouncer = add_enemy_with_type(&mut board, 822, 3, 6, 3, "Bouncer1", -1, -1);
        let ignite = add_mech_unit(&mut board, 2, 3, 7, 2);
        board.units[ignite].set_type_name("FlameMech");
        board.attack_order = vec![813, 822];

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[moth].hp, 3, "Fire plus blocked recoil costs the Moth 2 HP");
        assert_eq!((board.units[moth].x, board.units[moth].y), (3, 2));
        assert_eq!(board.tile(3, 1).building_hp, 1, "blocked recoil damages G5");
        assert_eq!(board.grid_power, 4);
        assert_eq!(result.grid_damage, 1);
        assert_eq!(board.units[bouncer].hp, 0, "Alpha Moth artillery kills the Bouncer");
        assert_eq!(board.units[ignite].hp, 1, "killed Bouncer corpse bumps Ignite for 1");
    }

    #[test]
    fn test_prior_enemy_kill_corpse_clears_before_later_moth_recoil() {
        // Chaos Roll Unfair 20260713_052159_731, Mission_DungBoss turn 1:
        // DungBoss killed Bouncer1 at (6,2) before Moth1 fired. Live removed
        // the Bouncer between queued actions, so the Moth recoiled from (5,2)
        // into the vacated tile without taking bump damage. Pre-v355 retained
        // the dead Bouncer as a wreck and incorrectly reduced the Moth 2->1.
        let mut board = Board::default();
        let boss = add_enemy_with_type(
            &mut board, 838, 6, 3, 4, "DungBoss", 6, 2,
        );
        board.units[boss].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let bouncer = add_enemy_with_type(
            &mut board, 840, 6, 2, 3, "Bouncer1", -1, -1,
        );
        let moth = add_enemy_with_type(
            &mut board, 842, 5, 2, 2, "Moth1", 3, 2,
        );
        board.units[moth].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        board.attack_order = vec![838, 840, 842];

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[bouncer].hp, 0, "DungBoss kills the Bouncer first");
        assert_eq!(
            (board.units[moth].x, board.units[moth].y),
            (6, 2),
            "later Moth recoil should enter the prior-action corpse tile",
        );
        assert_eq!(
            board.units[moth].hp,
            2,
            "a prior-action Vek corpse must not deal phantom recoil bump damage",
        );
    }

    #[test]
    fn test_bouncer_melee_self_bounce_and_target_push() {
        let mut board = Board::default();
        let target_idx = add_mech_unit(&mut board, 2, 4, 4, 3);
        let bouncer_idx = add_enemy_with_type(&mut board, 315, 4, 3, 3, "Bouncer1", 4, 4);
        board.units[bouncer_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!((board.units[bouncer_idx].x, board.units[bouncer_idx].y), (4, 2),
            "Bouncer should recoil before the horn hit resolves");
        assert_eq!(board.units[target_idx].hp, 2, "Bouncer horn deals 1 damage");
        assert_eq!((board.units[target_idx].x, board.units[target_idx].y), (4, 5),
            "Bouncer horn pushes the target forward");
    }

    #[test]
    fn test_bouncer_variants_dispatch_exact_damage_and_recoil() {
        for (pawn_type, expected_damage) in [
            ("Bouncer1", 1),
            ("Bouncer2", 3),
            ("BouncerBoss", 2),
        ] {
            let mut board = Board::default();
            let idx =
                add_enemy_with_type(&mut board, 40, 3, 3, 6, pawn_type, 3, 4);
            board.units[idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
            board.tile_mut(3, 4).terrain = Terrain::Building;
            board.tile_mut(3, 4).building_hp = 4;

            let orig = default_orig_pos(&board);
            simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

            assert_eq!(
                board.tile(3, 4).building_hp,
                4 - expected_damage,
                "{pawn_type} must dispatch its exact Lua damage",
            );
            assert_eq!(
                (board.units[idx].x, board.units[idx].y),
                (3, 2),
                "{pawn_type} must recoil before completing its strike",
            );
        }
    }

    #[test]
    fn test_burning_bouncer_on_ice_still_attacks_before_recoil_drowning() {
        let mut board = Board::default();
        board.grid_power = 7;
        board.grid_power_max = 7;
        board.tile_mut(5, 6).terrain = Terrain::Ice; // B3
        board.tile_mut(6, 6).terrain = Terrain::Water; // B2 recoil landing
        board.tile_mut(4, 6).terrain = Terrain::Building; // B4 Defense Lab
        board.tile_mut(4, 6).building_hp = 1;

        let bouncer_idx = add_enemy_with_type(&mut board, 541, 5, 6, 2, "Bouncer2", 4, 6);
        board.units[bouncer_idx].set_fire(true);
        board.units[bouncer_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(
            board.tile(5, 6).terrain,
            Terrain::Ice,
            "fire tick damage to an occupied ice tile should not melt the attacker's tile"
        );
        assert_eq!(
            board.tile(4, 6).building_hp,
            0,
            "burning Bouncer must still resolve its queued horn before recoil drowning"
        );
        assert_eq!(board.grid_power, 6);
        assert_eq!(result.grid_damage, 1);
        assert!(board.units[bouncer_idx].hp <= 0, "Bouncer drowns after recoil into water");
    }

    #[test]
    fn test_burning_scorpion_on_cracked_ground_survives_tick_and_attacks() {
        let mut board = Board::default();
        let exchange_idx = add_mech_unit(&mut board, 1, 4, 2, 1);
        let scorpion_idx = add_enemy_with_type(
            &mut board,
            509,
            5,
            2,
            3,
            "Scorpion1",
            4,
            2,
        );
        board.units[scorpion_idx].set_fire(true);
        board.units[scorpion_idx].queued_origin_x = 2;
        board.units[scorpion_idx].queued_origin_y = 2;
        board.units[scorpion_idx].queued_target_raw_x = 1;
        board.units[scorpion_idx].queued_target_raw_y = 2;
        board.units[scorpion_idx].weapon_damage = 1;
        board.units[scorpion_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
        );
        board.tile_mut(5, 2).set_cracked(true);

        let mut orig = default_orig_pos(&board);
        orig[scorpion_idx] = (2, 2);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(
            board.tile(5, 2).terrain,
            Terrain::Ground,
            "fire damage to a pawn must not collapse its occupied cracked Ground tile",
        );
        assert!(
            board.tile(5, 2).cracked(),
            "the occupied cracked Ground tile should remain cracked after the fire tick",
        );
        assert_eq!(
            board.units[scorpion_idx].hp,
            2,
            "the burning Scorpion should take only the one-point fire tick",
        );
        assert_eq!(
            board.units[exchange_idx].hp,
            0,
            "the surviving displaced Scorpion should complete its queued attack",
        );
    }

    #[test]
    fn test_airstrike_lethal_danger_collapses_empty_cracked_ground() {
        let mut board = Board::default();
        board.mission_id = "Mission_Airstrike".to_string();
        board.tile_mut(4, 3).set_cracked(true);
        let bit = 1u64 << xy_to_idx(4, 3);
        board.env_danger = bit;
        board.env_danger_kill = bit;

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(4, 3).terrain, Terrain::Chasm);
        assert!(!board.tile(4, 3).cracked());
    }

    #[test]
    fn test_airstrike_lethal_danger_does_not_collapse_occupied_cracked_ground() {
        let mut board = Board::default();
        board.mission_id = "Mission_Airstrike".to_string();
        let mech_idx = add_mech_unit(&mut board, 0, 4, 3, 3);
        board.tile_mut(4, 3).set_cracked(true);
        let bit = 1u64 << xy_to_idx(4, 3);
        board.env_danger = bit;
        board.env_danger_kill = bit;

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[mech_idx].hp, 0);
        assert_eq!(board.tile(4, 3).terrain, Terrain::Ground);
        assert!(board.tile(4, 3).cracked());
    }

    #[test]
    fn test_airstrike_nonlethal_danger_leaves_empty_cracked_ground() {
        let mut board = Board::default();
        board.mission_id = "Mission_Airstrike".to_string();
        board.tile_mut(4, 3).set_cracked(true);
        board.env_danger = 1u64 << xy_to_idx(4, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(4, 3).terrain, Terrain::Ground);
        assert!(board.tile(4, 3).cracked());
    }

    #[test]
    fn test_swapped_bouncer_uses_current_cardinal_target_when_origin_stale() {
        let mut board = Board::default();
        board.grid_power = 7;
        let target_idx = add_mech_unit(&mut board, 2, 2, 3, 2);
        let bouncer_idx = add_enemy_with_type(&mut board, 6036, 3, 3, 3, "Bouncer1", 2, 3);
        board.units[bouncer_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        board.units[bouncer_idx].set_web(true);
        board.units[bouncer_idx].queued_origin_x = 4;
        board.units[bouncer_idx].queued_origin_y = 2;
        board.tile_mut(1, 3).terrain = Terrain::Building;
        board.tile_mut(1, 3).building_hp = 1;

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[target_idx].hp, 0,
            "stale-origin swapped Bouncer should still hit and push-bump the adjacent mech");
        assert_eq!(board.tile(1, 3).building_hp, 0,
            "the forward push should bump into and damage the building behind the mech");
    }

    #[test]
    fn test_burning_dam_does_not_flood_before_bouncer_attack() {
        let mut board = Board::default();
        board.mission_id = "Mission_Dam".to_string();
        board.dam_alive = true;
        board.dam_primary = Some((4, 0));
        board.grid_power = 6;
        board.grid_power_max = 7;
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 2;

        let mut dam = Unit {
            uid: 121,
            x: 4,
            y: 0,
            hp: 1,
            max_hp: 2,
            team: Team::Neutral,
            flags: UnitFlags::MASSIVE | UnitFlags::FIRE,
            ..Default::default()
        };
        dam.set_type_name("Dam_Pawn");
        let dam_idx = board.add_unit(dam);

        let mut dam_extra = dam;
        dam_extra.x = 5;
        dam_extra.flags.insert(UnitFlags::EXTRA_TILE);
        board.add_unit(dam_extra);

        let exchange_idx = add_mech_unit(&mut board, 2, 4, 3, 2);
        board.units[exchange_idx].set_type_name("ExchangeMech");
        board.units[exchange_idx].flags.insert(UnitFlags::MASSIVE);

        let bouncer_idx = add_enemy_with_type(&mut board, 146, 5, 3, 3, "Bouncer1", 4, 3);
        board.units[bouncer_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[dam_idx].hp, 1, "Dam_Pawn fire should not tick in enemy phase");
        assert!(board.dam_alive, "Burning dam should not trigger a phantom flood");
        assert!(board.units[bouncer_idx].hp > 0, "Bouncer should not drown before attacking");
        assert!(board.units[exchange_idx].hp <= 0,
            "Bouncer hit plus building bump should match the live KIA");
        assert_eq!(result.mechs_killed, 1);
        assert_eq!(board.tile(3, 3).building_hp, 1,
            "Exchange should bump the E5 building after the horn hit");
    }

    #[test]
    fn test_beetle_charge_pushes_target_forward() {
        let mut board = Board::default();
        let target_idx = add_mech_unit(&mut board, 2, 5, 6, 2);
        let beetle_idx = add_enemy_with_type(&mut board, 46, 6, 6, 4, "Beetle1", 5, 6);
        board.units[beetle_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[target_idx].hp, 1, "Beetle should deal 1 charge damage");
        assert_eq!((board.units[target_idx].x, board.units[target_idx].y), (4, 6),
            "Beetle charge should push the hit target forward");
    }

    #[test]
    fn test_beetle_push_into_bouncer_chain_kills_rocket() {
        let mut board = Board::default();
        let rocket_idx = add_mech_unit(&mut board, 1, 5, 6, 2);
        let beetle_idx = add_enemy_with_type(&mut board, 46, 6, 6, 4, "Beetle1", 5, 6);
        let bouncer_idx = add_enemy_with_type(&mut board, 47, 4, 7, 1, "Bouncer2", 3, 6);
        board.units[beetle_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        board.units[bouncer_idx].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        board.units[bouncer_idx].weapon_damage = 3;

        let mut orig = default_orig_pos(&board);
        orig[bouncer_idx] = (3, 7);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(board.units[rocket_idx].hp <= 0,
            "Beetle B3->B4 displacement should let the alpha Bouncer kill Rocket");
        assert_eq!((board.units[rocket_idx].x, board.units[rocket_idx].y), (4, 5),
            "Bouncer should push the killed Rocket onward to C4");
        assert_eq!(board.units[bouncer_idx].hp, 1,
            "Bouncer edge recoil should not self-bump to death");
    }

    #[test]
    fn test_flipped_displaced_beetle_leader_charges_new_direction() {
        let mut board = Board::default();
        board.grid_power = 5;
        board.tile_mut(2, 3).terrain = Terrain::Building;
        board.tile_mut(2, 3).building_hp = 1;
        board.tile_mut(2, 6).terrain = Terrain::Building;
        board.tile_mut(2, 6).building_hp = 2;

        // Cataclysm HQ regression: the Beetle Leader started at D7 aimed E7,
        // got pushed to D6, then Seismic Capacitor flipped the preserved
        // direction. The post-flip queued target is C6 with origin D6, so the
        // flying charge should continue through C6 and hit B6, not the old E6.
        let boss_idx = add_enemy_with_type(&mut board, 1793, 2, 4, 3, "BeetleBoss", 2, 5);
        board.units[boss_idx].weapon_damage = 3;
        board.units[boss_idx].queued_origin_x = 2;
        board.units[boss_idx].queued_origin_y = 4;
        board.units[boss_idx].flags.insert(
            UnitFlags::HAS_QUEUED_ATTACK | UnitFlags::QUEUED_ORIGIN_SET,
        );

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(2, 3).building_hp, 1, "old E6 building should survive");
        assert_eq!(board.tile(2, 6).building_hp, 0, "flipped charge should destroy B6");
        assert_eq!(board.grid_power, 3, "2-HP B6 building drains two grid");
        assert_eq!((board.units[boss_idx].x, board.units[boss_idx].y), (2, 5),
            "charge should move the boss to the last free tile before impact");
    }

    #[test]
    fn test_crab_range_five_click_hits_forward_sixth_tile() {
        let mut board = Board::default();
        // Crab at (0,0) may click the range-five tile and its Type=2 effect
        // also damages the sixth tile in the same direction.
        board.tile_mut(5, 0).terrain = Terrain::Building;
        board.tile_mut(5, 0).building_hp = 1;
        board.tile_mut(6, 0).terrain = Terrain::Building;
        board.tile_mut(6, 0).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 0, 0, 3, "Crab1", 5, 0);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(5, 0).building_hp, 0, "Crab should hit clicked tile");
        assert_eq!(board.tile(6, 0).building_hp, 0, "Crab should hit tile after click");
    }

    #[test]
    fn test_crab_leader_damages_target_and_projectile_path() {
        let mut board = Board::default();
        // Crab Leader at (4,2) targeting (4,6): path tiles are (4,3..5),
        // target gets 2 damage, path gets 1 damage, tile past target is safe.
        board.tile_mut(4, 4).terrain = Terrain::Building;
        board.tile_mut(4, 4).building_hp = 1;
        board.tile_mut(4, 6).terrain = Terrain::Building;
        board.tile_mut(4, 6).building_hp = 2;
        board.tile_mut(4, 7).terrain = Terrain::Building;
        board.tile_mut(4, 7).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 4, 2, 6, "CrabBoss", 4, 6);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(4, 4).building_hp, 0, "Crab Leader should hit path tile");
        assert_eq!(board.tile(4, 6).building_hp, 0, "Crab Leader should hit target for 2 damage");
        assert_eq!(board.tile(4, 7).building_hp, 1, "Crab Leader should not hit beyond target");
    }

    #[test]
    fn test_blob_self_destructs_all_adjacent() {
        let mut board = Board::default();
        // Blob at (3,3) — self-AoE should hit self + 4 adjacent
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;
        board.tile_mut(4, 3).terrain = Terrain::Building;
        board.tile_mut(4, 3).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 3, 3, 1, "BlobMini", 3, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        // Blob should self-destruct (dies from AOE_CENTER)
        assert_eq!(board.units[0].hp, 0, "Blob should die from self-damage");
        // Adjacent buildings should take damage
        assert_eq!(board.tile(3, 4).building_hp, 0, "Adjacent building should be hit");
        assert_eq!(board.tile(4, 3).building_hp, 0, "Adjacent building should be hit");
    }

    #[test]
    fn test_blobber_leader_spawns_blob_leader() {
        let mut board = Board::default();
        add_enemy_with_type(&mut board, 10, 3, 3, 5, "BlobberBoss", 3, 5);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        let spawned = (0..board.unit_count as usize)
            .find(|&i| board.units[i].type_name_str() == "BlobB")
            .expect("Blobber Leader should spawn BlobB");
        assert_eq!((board.units[spawned].x, board.units[spawned].y), (3, 5));
        assert_eq!(board.units[spawned].hp, 2);
        assert_eq!(board.units[spawned].max_hp, 2);
    }

    #[test]
    fn test_blob_leader_split_self_aoe_damage() {
        let mut board = Board::default();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 2;
        let mech_idx = board.add_unit(Unit {
            uid: 2,
            x: 4,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::MASSIVE | UnitFlags::PUSHABLE,
            ..Default::default()
        });
        add_enemy_with_type(&mut board, 1, 3, 3, 2, "BlobB", 3, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[1].hp, 1, "Blob Leader should survive its 1 self damage");
        assert_eq!(board.tile(3, 4).building_hp, 0, "adjacent building should take 2 damage");
        assert_eq!(board.units[mech_idx].hp, 1, "adjacent mech should take 2 damage");
    }

    #[test]
    fn test_blob_boss_squish_moves_into_destroyed_building() {
        let mut board = Board::default();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;
        add_enemy_with_type(&mut board, 20, 3, 3, 3, "BlobBoss", 3, 4);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(3, 4).building_hp, 0);
        assert_eq!((board.units[0].x, board.units[0].y), (3, 4));
    }

    #[test]
    fn test_blob_boss_squish_destroys_full_mountain() {
        let mut board = Board::default();
        board.tile_mut(3, 4).terrain = Terrain::Mountain;
        board.tile_mut(3, 4).building_hp = 2;
        add_enemy_with_type(&mut board, 21, 3, 3, 3, "BlobBoss", 3, 4);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(3, 4).terrain, Terrain::Rubble);
        assert_eq!(board.tile(3, 4).building_hp, 0);
        assert_eq!((board.units[0].x, board.units[0].y), (3, 4));
    }

    #[test]
    fn test_beetle_charge_from_distance() {
        let mut board = Board::default();
        // Beetle at (0,0) targeting (5,0) — charges from current position
        board.tile_mut(5, 0).terrain = Terrain::Building;
        board.tile_mut(5, 0).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 0, 0, 4, "Beetle1", 5, 0);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        // Beetle should charge and hit the building
        assert_eq!(board.tile(5, 0).building_hp, 0, "Beetle charge should hit building");
    }

    #[test]
    fn test_digger_hits_all_adjacent() {
        let mut board = Board::default();
        // Digger at (3,3) — self_aoe hits all 4 adjacent
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;
        board.tile_mut(3, 2).terrain = Terrain::Building;
        board.tile_mut(3, 2).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 3, 3, 2, "Digger1", 3, 4);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        // Digger self-aoe should hit adjacent buildings (both directions)
        assert_eq!(board.tile(3, 4).building_hp, 0, "Digger should hit N building");
        assert_eq!(board.tile(3, 2).building_hp, 0, "Digger should hit S building");
    }

    #[test]
    fn test_digger_spawns_four_persistent_neutral_walls_after_own_damage() {
        let mut board = Board::default();
        add_enemy_with_type(&mut board, 1, 3, 3, 2, "Digger1", 3, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        let walls: Vec<&Unit> = board.units[..board.unit_count as usize]
            .iter()
            .filter(|unit| unit.type_name_str() == "Wall")
            .collect();
        assert_eq!(walls.len(), 4);
        for &(dx, dy) in &DIRS {
            let x = (3i8 + dx) as u8;
            let y = (3i8 + dy) as u8;
            let wall = walls
                .iter()
                .find(|wall| (wall.x, wall.y) == (x, y))
                .expect("every eligible cardinal should retain a Wall");
            assert_eq!(wall.team, Team::Neutral);
            assert_eq!((wall.hp, wall.max_hp), (1, 1));
            assert_eq!((wall.move_speed, wall.base_move), (0, 0));
            assert!(wall.pushable());
            assert_eq!(wall.weapon, WeaponId(WId::None as u16));
            assert_eq!((wall.queued_target_x, wall.queued_target_y), (-1, -1));
        }
        assert_eq!(board.unit_at(3, 2).map(|idx| board.units[idx].uid), Some(2));
        assert_eq!(board.unit_at(4, 3).map(|idx| board.units[idx].uid), Some(3));
        assert_eq!(board.unit_at(3, 4).map(|idx| board.units[idx].uid), Some(4));
        assert_eq!(board.unit_at(2, 3).map(|idx| board.units[idx].uid), Some(5));
    }

    #[test]
    fn test_alpha_digger_damages_occupied_tiles_and_walls_only_empty_cards() {
        let mut board = Board::default();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 2;
        let mech = add_mech_unit(&mut board, 2, 4, 3, 3);
        add_enemy_with_type(&mut board, 1, 3, 3, 4, "Digger2", 3, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(3, 4).building_hp, 0);
        assert_eq!(board.units[mech].hp, 1);
        assert!(!board.units[..board.unit_count as usize]
            .iter()
            .any(|unit| unit.type_name_str() == "Wall"
                && matches!((unit.x, unit.y), (3, 4) | (4, 3))));
        let wall_positions: Vec<(u8, u8)> = board.units[..board.unit_count as usize]
            .iter()
            .filter(|unit| unit.type_name_str() == "Wall")
            .map(|unit| (unit.x, unit.y))
            .collect();
        assert_eq!(wall_positions.len(), 2);
        assert!(wall_positions.contains(&(3, 2)));
        assert!(wall_positions.contains(&(2, 3)));
    }

    #[test]
    fn test_digger_wall_source_predicate_rejects_each_blocker_class() {
        for case in 0..6 {
            let mut board = Board::default();
            match case {
                0 => board.tile_mut(3, 4).terrain = Terrain::Mountain,
                1 => {
                    board.tile_mut(3, 4).terrain = Terrain::Building;
                    board.tile_mut(3, 4).building_hp = 1;
                }
                2 => board.tile_mut(3, 4).terrain = Terrain::Water,
                3 => board.tile_mut(3, 4).set_has_pod(true),
                4 => {
                    add_mech_unit(&mut board, 10, 3, 4, 3);
                }
                5 => {
                    let mut wreck = Unit {
                        uid: 10,
                        x: 3,
                        y: 4,
                        hp: 0,
                        max_hp: 1,
                        team: Team::Neutral,
                        ..Unit::default()
                    };
                    wreck.set_type_name("Wall");
                    board.add_unit(wreck);
                }
                _ => unreachable!(),
            }
            add_enemy_with_type(&mut board, 1, 3, 3, 2, "Digger1", 3, 3);

            let orig = default_orig_pos(&board);
            simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

            assert!(board.units[..board.unit_count as usize]
                .iter()
                .filter(|unit| unit.hp > 0 && unit.type_name_str() == "Wall")
                .all(|unit| (unit.x, unit.y) != (3, 4)),
                "case {case} must reject the north tile");
        }
    }

    #[test]
    fn test_digger_wall_blocks_later_enemy_projectile() {
        let mut board = Board::default();
        board.tile_mut(0, 3).terrain = Terrain::Building;
        board.tile_mut(0, 3).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 3, 3, 2, "Digger1", 3, 3);
        add_enemy_with_type(&mut board, 2, 6, 3, 2, "Firefly1", 0, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(0, 3).building_hp, 1,
            "the later projectile should stop at the newly-created Wall");
        let blocking_wall = board.units[..board.unit_count as usize]
            .iter()
            .find(|unit| unit.type_name_str() == "Wall" && (unit.x, unit.y) == (4, 3))
            .expect("Digger should create the east Wall before Firefly resolves");
        assert_eq!(blocking_wall.hp, 0);
    }

    #[test]
    fn test_digger_wall_spawn_skips_safely_at_board_capacity() {
        let mut board = Board::default();
        add_enemy_with_type(&mut board, 1, 3, 3, 2, "Digger1", 3, 3);
        for uid in 2..=16 {
            let mut unit = Unit {
                uid,
                x: 8,
                y: 8,
                hp: 1,
                max_hp: 1,
                team: Team::Neutral,
                ..Unit::default()
            };
            unit.set_type_name("CapacityDummy");
            board.add_unit(unit);
        }

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.unit_count, 16);
        assert!(!board.units.iter().any(|unit| unit.type_name_str() == "Wall"));
    }

    #[test]
    fn test_enemy_weapon_for_type_mapping() {
        assert_eq!(enemy_weapon_for_type("Firefly1"), WId::FireflyAtk1);
        assert_eq!(enemy_weapon_for_type("Scarab2"), WId::ScarabAtk2);
        assert_eq!(enemy_weapon_for_type("Beetle1"), WId::BeetleAtk1);
        assert_eq!(enemy_weapon_for_type("Digger1"), WId::DiggerAtk1);
        assert_eq!(enemy_weapon_for_type("BlobMini"), WId::BlobAtk1);
        assert_eq!(enemy_weapon_for_type("BlobB"), WId::BlobAtkB);
        assert_eq!(enemy_weapon_for_type("BlobberBoss"), WId::BlobberAtkB);
        assert_eq!(enemy_weapon_for_type("Crab1"), WId::CrabAtk1);
        assert_eq!(enemy_weapon_for_type("CrabBoss"), WId::CrabAtkB);
        assert_eq!(enemy_weapon_for_type("Totem1"), WId::TotemAtk1);
        assert_eq!(enemy_weapon_for_type("Totem2"), WId::TotemAtk2);
        assert_eq!(enemy_weapon_for_type("TotemB"), WId::TotemAtkB);
        assert_eq!(enemy_weapon_for_type("Shaman1"), WId::ShamanAtk1);
        assert_eq!(enemy_weapon_for_type("Shaman2"), WId::ShamanAtk2);
        assert_eq!(enemy_weapon_for_type("Snowtank1_Boom"), WId::SnowtankAtk1);
        assert_eq!(enemy_weapon_for_type("Snowlaser1_Boom"), WId::SnowlaserAtk1);
        assert_eq!(enemy_weapon_for_type("Snowart1_Boom"), WId::SnowartAtk1);
        assert_eq!(enemy_weapon_for_type("Unknown"), WId::None);
    }

    fn add_mech_unit(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8) -> usize {
        let mut unit = Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::ACTIVE | UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        };
        unit.set_type_name("PunchMech");
        board.add_unit(unit)
    }

    fn add_train(board: &mut Board, px: u8, py: u8, ex: u8, ey: u8) -> (usize, usize) {
        let mut primary = Unit {
            uid: 2524, x: px, y: py, hp: 1, max_hp: 1,
            team: Team::Player,
            flags: UnitFlags::default(),
            ..Default::default()
        };
        primary.set_type_name("Train_Pawn");
        let p = board.add_unit(primary);

        let mut extra = Unit {
            uid: 2524, x: ex, y: ey, hp: 1, max_hp: 1,
            team: Team::Player,
            flags: UnitFlags::EXTRA_TILE,
            ..Default::default()
        };
        extra.set_type_name("Train_Pawn");
        let e = board.add_unit(extra);
        (p, e)
    }

    fn add_armored_train(board: &mut Board, px: u8, py: u8, ex: u8, ey: u8) -> (usize, usize) {
        let mut primary = Unit {
            uid: 2525, x: px, y: py, hp: 1, max_hp: 1,
            team: Team::Player,
            flags: UnitFlags::ARMOR,
            ..Default::default()
        };
        primary.set_type_name("Train_Armored");
        let p = board.add_unit(primary);

        let mut extra = Unit {
            uid: 2525, x: ex, y: ey, hp: 1, max_hp: 1,
            team: Team::Player,
            flags: UnitFlags::ARMOR | UnitFlags::EXTRA_TILE,
            ..Default::default()
        };
        extra.set_type_name("Train_Armored");
        let e = board.add_unit(extra);
        (p, e)
    }

    #[test]
    fn test_train_advances_on_clear_path() {
        // Train at (4,7)+(4,6), forward direction (0,-1). Advances to (4,5)+(4,4).
        let mut board = Board::default();
        let (p, e) = add_train(&mut board, 4, 6, 4, 7);
        simulate_train_advance(&mut board);
        assert_eq!(board.units[p].hp, 1, "primary survives");
        assert_eq!(board.units[e].hp, 1, "extra survives");
        assert_eq!((board.units[p].x, board.units[p].y), (4, 4), "primary advanced 2 forward");
        assert_eq!((board.units[e].x, board.units[e].y), (4, 5), "extra advanced 2 forward");
    }

    #[test]
    fn test_frozen_train_does_not_activate() {
        let mut board = Board::default();
        let (p, e) = add_train(&mut board, 4, 6, 4, 7);
        board.units[p].set_frozen(true);
        board.units[e].set_frozen(true);

        let result = simulate_train_advance(&mut board);

        assert_eq!((board.units[p].x, board.units[p].y), (4, 6));
        assert_eq!((board.units[e].x, board.units[e].y), (4, 7));
        assert!(board.units[p].frozen());
        assert_eq!(result.enemies_killed, 0);
    }

    #[test]
    fn test_smoked_train_still_activates() {
        let mut board = Board::default();
        let (p, e) = add_train(&mut board, 4, 6, 4, 7);
        board.tile_mut(4, 6).set_smoke(true);

        simulate_train_advance(&mut board);

        assert_eq!((board.units[p].x, board.units[p].y), (4, 4));
        assert_eq!((board.units[e].x, board.units[e].y), (4, 5));
    }

    #[test]
    fn test_shielded_train_absorbs_blocked_charge_self_damage() {
        let mut board = Board::default();
        let (p, e) = add_train(&mut board, 4, 6, 4, 7);
        board.units[p].set_shield(true);
        board.units[e].set_shield(true);
        board.tile_mut(4, 5).terrain = Terrain::Mountain;
        board.tile_mut(4, 5).building_hp = 2;

        simulate_train_advance(&mut board);

        assert_eq!(board.units[p].type_name_str(), "Train_Pawn");
        assert_eq!(board.units[e].type_name_str(), "Train_Pawn");
        assert_eq!(board.units[p].hp, 1);
        assert_eq!(board.units[e].hp, 1);
        assert!(!board.units[p].shield());
        assert!(!board.units[e].shield());
        assert_eq!((board.units[p].x, board.units[p].y), (4, 6));
        assert_eq!(board.tile(4, 5).terrain, Terrain::Rubble);
    }

    #[test]
    fn test_train_stops_and_becomes_damaged_when_first_step_is_blocked() {
        // Train at (4,6)+(4,7) facing y-1. Mountain at (4,5) blocks first step.
        let mut board = Board::default();
        let (p, e) = add_train(&mut board, 4, 6, 4, 7);
        let old_uid = board.units[p].uid;
        board.tile_mut(4, 5).terrain = Terrain::Mountain;
        board.tile_mut(4, 5).building_hp = 2;
        simulate_train_advance(&mut board);
        assert_eq!(board.units[p].type_name_str(), "Train_Damaged");
        assert_eq!(board.units[e].type_name_str(), "Train_Damaged");
        assert_eq!(board.units[p].hp, 1, "stopped primary survives as damaged train");
        assert_eq!(board.units[e].hp, 1, "stopped extra survives as damaged train");
        assert_ne!(board.units[p].uid, old_uid, "replacement is a fresh logical pawn");
        assert_eq!(board.units[p].uid, board.units[e].uid);
        assert_eq!((board.units[p].x, board.units[p].y), (4, 6), "first-step block prevents movement");
        assert_eq!((board.units[e].x, board.units[e].y), (4, 7));
        assert_eq!(board.tile(4, 5).terrain, Terrain::Rubble, "blocking mountain is destroyed");
    }

    #[test]
    fn test_train_advances_one_step_kills_second_step_blocker_and_stops() {
        // Vek at (4,4) blocks second step.
        let mut board = Board::default();
        let (p, e) = add_train(&mut board, 4, 6, 4, 7);
        let vek = add_enemy_with_type(&mut board, 100, 4, 4, 2, "Scarab1", -1, -1);
        let result = simulate_train_advance(&mut board);
        assert_eq!(board.units[p].type_name_str(), "Train_Damaged");
        assert_eq!(board.units[e].type_name_str(), "Train_Damaged");
        assert_eq!((board.units[p].x, board.units[p].y), (4, 5));
        assert_eq!((board.units[e].x, board.units[e].y), (4, 6));
        assert_eq!(board.units[p].hp, 1);
        assert_eq!(board.units[e].hp, 1);
        assert_eq!(board.units[vek].hp, 0, "Train_Move DAMAGE_DEATH destroys the blocker");
        assert_eq!(result.enemies_killed, 1, "train kill reaches turn counters");
        assert_eq!(result.mission_kills, 1, "train kill reaches mission progress");
    }

    #[test]
    fn test_moth_kill_replaces_moving_train_before_advance() {
        // Exact Mission_Train shape from run 20260710_013601_568 m03 t1:
        // Moth artillery targets the rear train segment after recoiling into a
        // blocking mech. The moving train dies, then Mission_Train:StopTrain
        // creates a live damaged body at TrainLoc instead of losing it outright.
        let mut board = Board::default();
        board.mission_id = "Mission_Train".to_string();
        let blocker = add_mech_unit(&mut board, 2, 4, 4, 3);
        let moth = add_enemy_with_type(&mut board, 169, 4, 5, 2, "Moth1", 4, 7);
        board.units[moth].weapon_damage = 1;
        board.units[moth].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        let (p, e) = add_train(&mut board, 4, 6, 4, 7);
        let old_uid = board.units[p].uid;

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[blocker].hp, 2, "blocked Moth recoil bumps the mech");
        assert_eq!(board.units[moth].hp, 1, "blocked recoil also bumps the Moth");
        assert_eq!(board.units[p].type_name_str(), "Train_Damaged");
        assert_eq!(board.units[e].type_name_str(), "Train_Damaged");
        assert_eq!(board.units[p].hp, 1);
        assert_eq!(board.units[e].hp, 1);
        assert_ne!(board.units[p].uid, old_uid);
        assert_eq!((board.units[p].x, board.units[p].y), (4, 6));
        assert_eq!((board.units[e].x, board.units[e].y), (4, 7));
    }

    #[test]
    fn test_armored_train_kills_blocker_and_advances() {
        let mut board = Board::default();
        let (p, e) = add_armored_train(&mut board, 4, 6, 4, 7);
        let vek = add_enemy_with_type(&mut board, 100, 4, 4, 3, "Scarab1", -1, -1);
        board.tile_mut(4, 5).terrain = Terrain::Mountain;
        board.tile_mut(4, 5).building_hp = 2;

        simulate_train_advance(&mut board);

        assert_eq!(board.units[p].hp, 1, "armored train primary survives");
        assert_eq!(board.units[e].hp, 1, "armored train extra survives");
        assert_eq!(board.units[vek].hp, 0, "blocker is destroyed");
        assert_eq!(board.tile(4, 5).terrain, Terrain::Rubble, "mountain path tile is crushed");
        assert_eq!((board.units[p].x, board.units[p].y), (4, 4));
        assert_eq!((board.units[e].x, board.units[e].y), (4, 5));
    }

    #[test]
    fn test_train_survives_off_board_exit() {
        // Train one step from the edge facing y-1. New tiles would be (4,-1)
        // and (4,-2) — off board = exit reached, train stays alive in place.
        let mut board = Board::default();
        let (p, e) = add_train(&mut board, 4, 0, 4, 1);
        simulate_train_advance(&mut board);
        assert_eq!(board.units[p].hp, 1, "train alive at exit");
        assert_eq!(board.units[e].hp, 1);
        assert_eq!((board.units[p].x, board.units[p].y), (4, 0), "no position change at exit");
    }

    #[test]
    fn test_destroyed_train_is_replaced_by_damaged_body() {
        // Train pre-killed by Vek attack earlier in enemy phase.
        let mut board = Board::default();
        let (p, e) = add_train(&mut board, 4, 6, 4, 7);
        let old_uid = board.units[p].uid;
        board.units[p].hp = 0;
        board.units[e].hp = 0;
        simulate_train_advance(&mut board);
        assert_eq!(board.units[p].type_name_str(), "Train_Damaged");
        assert_eq!(board.units[e].type_name_str(), "Train_Damaged");
        assert_eq!(board.units[p].hp, 1);
        assert_eq!(board.units[e].hp, 1);
        assert_ne!(board.units[p].uid, old_uid);
        assert_eq!((board.units[p].x, board.units[p].y), (4, 6));
    }

    fn add_hacking_facility(board: &mut Board, hp: i8) -> usize {
        let mut facility = Unit {
            uid: 40,
            x: 3,
            y: 4,
            hp,
            max_hp: 1,
            team: Team::Enemy,
            flags: UnitFlags::MINOR | UnitFlags::SHIELD,
            ..Unit::default()
        };
        facility.set_type_name("Hacked_Building");
        board.add_unit(facility)
    }

    fn add_hostile_hacking_bot(board: &mut Board, uid: u16) -> usize {
        let mut bot = Unit {
            uid,
            x: 5,
            y: 4,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            move_speed: 4,
            base_move: 4,
            flags: UnitFlags::PUSHABLE
                | UnitFlags::SHIELD
                | UnitFlags::ACID
                | UnitFlags::FIRE
                | UnitFlags::WEB
                | UnitFlags::BOOSTED
                | UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
            weapon: WeaponId(WId::SnowtankAtk1 as u16),
            weapon2: WeaponId(WId::FireflyAtk2 as u16),
            queued_target_x: 5,
            queued_target_y: 7,
            queued_target_raw_x: 5,
            queued_target_raw_y: 7,
            queued_origin_x: 5,
            queued_origin_y: 4,
            weapon_damage: 3,
            weapon_push: 1,
            weapon_target_behind: true,
            web_source_uid: 99,
            ..Unit::default()
        };
        bot.set_type_name("Snowtank1");
        board.add_unit(bot)
    }

    fn set_hacking_identity(board: &mut Board, bot_uid: u16) {
        board.mission_hacking_bot_id = Some(bot_uid);
        board.mission_hacking_hack_id = Some(40);
    }

    #[test]
    fn test_hacking_conversion_replaces_bot_and_preserves_only_location_and_shield() {
        let mut board = Board::default();
        board.mission_id = "Mission_Hacking".to_string();
        add_hacking_facility(&mut board, 0);
        let bot = add_hostile_hacking_bot(&mut board, 41);
        set_hacking_identity(&mut board, 41);
        let old_uid = board.units[bot].uid;

        assert!(transition_hacked_cannon_bot(&mut board));

        let converted = &board.units[bot];
        assert_eq!(converted.type_name_str(), "Snowtank1_Player");
        assert_eq!((converted.x, converted.y), (5, 4));
        assert_eq!(converted.uid, 42);
        assert_eq!(board.mission_hacking_bot_id, Some(42));
        assert_ne!(converted.uid, old_uid);
        assert_eq!(converted.team, Team::Player);
        assert_eq!((converted.hp, converted.max_hp), (1, 1));
        assert_eq!((converted.move_speed, converted.base_move), (3, 3));
        assert_eq!(converted.weapon, WeaponId(WId::SnowtankAtk1 as u16));
        assert_eq!(converted.weapon2, WeaponId::NONE);
        assert_eq!(
            converted.flags,
            UnitFlags::PUSHABLE | UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::SHIELD,
        );
        assert!(converted.is_player_action_unit());
        assert_eq!(converted.queued_target_x, -1);
        assert_eq!(converted.queued_target_y, -1);
        assert_eq!(converted.queued_target_raw_x, -1);
        assert_eq!(converted.queued_target_raw_y, -1);
        assert_eq!(converted.queued_origin_x, -1);
        assert_eq!(converted.queued_origin_y, -1);
        assert_eq!(converted.weapon_damage, 0);
        assert_eq!(converted.weapon_push, 0);
        assert!(!converted.weapon_target_behind);
        assert_eq!(converted.web_source_uid, 0);
        assert!(!transition_hacked_cannon_bot(&mut board), "conversion is one-shot");
    }

    #[test]
    fn test_hacking_conversion_guards_missing_wrong_or_dead_identity() {
        let mut missing_ids = Board::default();
        missing_ids.mission_id = "Mission_Hacking".to_string();
        add_hacking_facility(&mut missing_ids, 0);
        add_hostile_hacking_bot(&mut missing_ids, 41);
        assert!(!transition_hacked_cannon_bot(&mut missing_ids));

        let mut facility_alive = Board::default();
        facility_alive.mission_id = "Mission_Hacking".to_string();
        add_hacking_facility(&mut facility_alive, 1);
        add_hostile_hacking_bot(&mut facility_alive, 41);
        set_hacking_identity(&mut facility_alive, 41);
        assert!(!transition_hacked_cannon_bot(&mut facility_alive));

        let mut wrong_mission = Board::default();
        wrong_mission.mission_id = "Mission_Filler".to_string();
        add_hostile_hacking_bot(&mut wrong_mission, 41);
        set_hacking_identity(&mut wrong_mission, 41);
        assert!(!transition_hacked_cannon_bot(&mut wrong_mission));

        let mut dead_bot = Board::default();
        dead_bot.mission_id = "Mission_Hacking".to_string();
        let dead = add_hostile_hacking_bot(&mut dead_bot, 41);
        set_hacking_identity(&mut dead_bot, 41);
        dead_bot.units[dead].hp = 0;
        assert!(!transition_hacked_cannon_bot(&mut dead_bot));

        let mut already_player = Board::default();
        already_player.mission_id = "Mission_Hacking".to_string();
        let player = add_hostile_hacking_bot(&mut already_player, 41);
        set_hacking_identity(&mut already_player, 41);
        already_player.units[player].team = Team::Player;
        assert!(!transition_hacked_cannon_bot(&mut already_player));
    }

    #[test]
    fn test_hacking_conversion_uses_stored_bot_id_not_unrelated_snowtank() {
        let mut board = Board::default();
        board.mission_id = "Mission_Hacking".to_string();
        add_hacking_facility(&mut board, 0);
        let tracked = add_hostile_hacking_bot(&mut board, 41);
        let unrelated = add_hostile_hacking_bot(&mut board, 42);
        set_hacking_identity(&mut board, 41);

        assert!(transition_hacked_cannon_bot(&mut board));
        assert_eq!(board.units[tracked].type_name_str(), "Snowtank1_Player");
        assert_eq!(board.units[unrelated].type_name_str(), "Snowtank1");
        assert_eq!(board.units[unrelated].team, Team::Enemy);

        let mut dead_tracked = Board::default();
        dead_tracked.mission_id = "Mission_Hacking".to_string();
        let tracked = add_hostile_hacking_bot(&mut dead_tracked, 41);
        let unrelated = add_hostile_hacking_bot(&mut dead_tracked, 42);
        dead_tracked.units[tracked].hp = 0;
        set_hacking_identity(&mut dead_tracked, 41);
        assert!(!transition_hacked_cannon_bot(&mut dead_tracked));
        assert_eq!(dead_tracked.units[unrelated].team, Team::Enemy);
    }

    #[test]
    fn test_enemy_phase_tail_carries_hacking_conversion_into_next_turn() {
        let mut board = Board::default();
        board.mission_id = "Mission_Hacking".to_string();
        add_hacking_facility(&mut board, 0);
        let bot = add_hostile_hacking_bot(&mut board, 41);
        set_hacking_identity(&mut board, 41);
        board.units[bot].flags.remove(UnitFlags::HAS_QUEUED_ATTACK);
        let original_positions = default_orig_pos(&board);

        simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!(board.units[bot].type_name_str(), "Snowtank1_Player");
        assert_eq!(board.units[bot].team, Team::Player);
        assert!(board.units[bot].is_player_action_unit());
    }

    fn add_beetle_boss(board: &mut Board, uid: u16, x: u8, y: u8, qtx: u8, qty: u8) -> usize {
        let mut unit = Unit {
            uid, x, y, hp: 6, max_hp: 6,
            team: Team::Enemy,
            flags: UnitFlags::MASSIVE,
            queued_target_x: qtx as i8,
            queued_target_y: qty as i8,
            weapon: WeaponId(WId::BeetleAtkB as u16),
            weapon_damage: 3,
            ..Default::default()
        };
        unit.set_type_name("BeetleBoss");
        board.add_unit(unit)
    }

    fn add_scorpion_boss(board: &mut Board, uid: u16, x: u8, y: u8) -> usize {
        let mut unit = Unit {
            uid, x, y, hp: 6, max_hp: 6,
            team: Team::Enemy,
            flags: UnitFlags::MASSIVE | UnitFlags::HAS_QUEUED_ATTACK,
            queued_target_x: x as i8,
            queued_target_y: y as i8,
            weapon: WeaponId(WId::ScorpionAtkB as u16),
            weapon_damage: 2,
            ..Default::default()
        };
        unit.set_type_name("ScorpionBoss");
        board.add_unit(unit)
    }

    #[test]
    fn test_scorpion_boss_spinneret_grapples_before_queued_outward_push() {
        // `ScorpionAtkB` applies AddGrapple immediately to each original
        // adjacent survivor, then queues its 2-damage outward melee. The
        // northern push is blocked so it retains the web/source; successful
        // pushes clear the just-applied web when their targets change tiles.
        let mut board = Board::default();
        board.tile_mut(3, 1).terrain = Terrain::Mountain;
        let north = add_mech_unit(&mut board, 10, 3, 2, 5);
        let east = add_mech_unit(&mut board, 11, 4, 3, 5);
        let south = add_mech_unit(&mut board, 12, 3, 4, 5);
        let west = add_mech_unit(&mut board, 13, 2, 3, 5);
        let boss = add_scorpion_boss(&mut board, 99, 3, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        // North takes the Spinneret hit plus the mountain bump, remains on
        // its original tile, and therefore keeps the immediate grapple.
        assert_eq!(board.units[north].hp, 2);
        assert_eq!((board.units[north].x, board.units[north].y), (3, 2));
        assert!(board.units[north].web());
        assert_eq!(board.units[north].web_source_uid, board.units[boss].uid);

        for (idx, expected_pos) in [(east, (5, 3)), (south, (3, 5)), (west, (1, 3))] {
            assert_eq!(board.units[idx].hp, 3, "every adjacent survivor takes 2 damage");
            assert_eq!((board.units[idx].x, board.units[idx].y), expected_pos);
            assert!(!board.units[idx].web(), "a successful push breaks the web");
            assert_eq!(board.units[idx].web_source_uid, 0);
        }
    }

    #[test]
    fn test_scorpion_boss_spinneret_skips_dead_and_soldier_web_targets() {
        use crate::board::PilotFlags;

        let mut board = Board::default();
        let dead = add_mech_unit(&mut board, 10, 3, 2, 2);
        let soldier = add_mech_unit(&mut board, 11, 4, 3, 5);
        board.units[soldier].pilot_flags = PilotFlags::SOLDIER;
        add_scorpion_boss(&mut board, 99, 3, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(board.units[dead].hp <= 0);
        assert!(!board.units[dead].web());
        assert_eq!(board.units[dead].web_source_uid, 0);
        assert!(!board.units[soldier].web());
        assert_eq!(board.units[soldier].web_source_uid, 0);
    }

    #[test]
    fn test_beetle_leader_weapon_mapping() {
        // Bridge sends "BeetleAtkB"; wid_from_str should map to the new weapon.
        assert_eq!(wid_from_str("BeetleAtkB"), WId::BeetleAtkB);
        assert_eq!(wid_to_str(WId::BeetleAtkB), "BeetleAtkB");
        assert_eq!(enemy_weapon_for_type("BeetleBoss"), WId::BeetleAtkB);
    }

    #[test]
    fn test_beetle_leader_adjacent_target_building() {
        // Beetle at (4,5), queued target (4,6) = adjacent building.
        // No passed tiles → no fire trail. Push on building = bump (building
        // ignores push but takes bump damage — the apply_damage on impact
        // already handled the main damage, so push is a no-op here).
        let mut board = Board::default();
        board.tile_mut(4, 6).terrain = Terrain::Building;
        board.tile_mut(4, 6).building_hp = 2;
        add_beetle_boss(&mut board, 100, 4, 5, 4, 6);
        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);
        // Building took 3 damage → destroyed. No fire tiles (no passed tiles).
        assert_eq!(board.tile(4, 6).building_hp, 0, "building destroyed");
        assert_eq!(board.tile(4, 5).on_fire(), false, "no fire on start tile");
    }

    #[test]
    fn test_beetle_leader_fire_trail_on_long_charge() {
        // Beetle at (4,7), target direction = y-1, blocker at (4,2).
        // Beetle passes through tiles at i=1..5 (y=6,5,4,3,2). Blocker at i=5.
        // Final resting = i=4 (y=3). Fire on i=1..3 (y=6,5,4). Target at y=2.
        let mut board = Board::default();
        // Put a vek at (4,2) as blocker
        add_enemy_with_type(&mut board, 200, 4, 2, 3, "Scarab1", -1, -1);
        add_beetle_boss(&mut board, 100, 4, 7, 4, 2);
        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        // Passed-through tiles get fire: (4,6), (4,5), (4,4). Final resting
        // (4,3) does NOT get fire. Target (4,2) takes damage.
        assert!(board.tile(4, 6).on_fire(), "fire on first passed tile");
        assert!(board.tile(4, 5).on_fire(), "fire on second passed tile");
        assert!(board.tile(4, 4).on_fire(), "fire on third passed tile");
        assert_eq!(board.tile(4, 3).on_fire(), false, "no fire on resting tile");
        assert_eq!(board.tile(4, 2).on_fire(), false, "no fire on target tile");
    }

    #[test]
    fn test_beetle_leader_push_on_impact() {
        // Beetle at (4,5), target (4,6). Beetle hits the enemy at (4,6) and
        // should push it forward (toward y+1) to (4,7). (4,7) is empty ground.
        let mut board = Board::default();
        let target = add_enemy_with_type(&mut board, 200, 4, 6, 2, "Scarab1", -1, -1);
        add_beetle_boss(&mut board, 100, 4, 5, 4, 6);
        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);
        // Target took 3 damage (2 HP → 0, dead) AND was pushed.
        // If Scarab dies first, push moves a dead unit. Per apply_push
        // (any_unit_at), dead units can still be pushed. We just verify
        // the damage applied correctly.
        assert!(board.units[target].hp <= 0, "target killed by 3 dmg (hp={})", board.units[target].hp);
    }

    #[test]
    fn test_alpha_centipede_applies_acid_to_target() {
        let mut board = Board::default();
        // Alpha Centipede at (0,3) firing east, target mech at (4,3).
        // Corrosive Vomit: 2 damage + ACID.
        let mech_idx = add_mech_unit(&mut board, 10, 4, 3, 3);
        add_enemy_with_type(&mut board, 1, 0, 3, 5, "Centipede2", 4, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[mech_idx].hp, 1, "Mech should take 2 damage from Corrosive Vomit");
        assert!(board.units[mech_idx].acid(), "Mech should be ACID'd by Corrosive Vomit");
    }

    #[test]
    fn test_normal_centipede_applies_one_damage_and_acid_t_splash() {
        let mut board = Board::default();
        let target_idx = add_mech_unit(&mut board, 10, 4, 3, 5);
        let north_idx = add_mech_unit(&mut board, 11, 4, 4, 5);
        let south_idx = add_mech_unit(&mut board, 12, 4, 2, 5);
        add_enemy_with_type(&mut board, 1, 0, 3, 3, "Centipede1", 4, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        for idx in [target_idx, north_idx, south_idx] {
            assert_eq!(board.units[idx].hp, 4);
            assert!(board.units[idx].acid());
        }
    }

    #[test]
    fn test_alpha_centipede_aoe_perpendicular_splashes() {
        let mut board = Board::default();
        // Alpha Centipede at (0,3) firing east, target mech at (4,3).
        // Perpendicular tiles (4,2) and (4,4) should also take 2 dmg + ACID.
        let target_idx = add_mech_unit(&mut board, 10, 4, 3, 5);
        let north_idx = add_mech_unit(&mut board, 11, 4, 4, 5);
        let south_idx = add_mech_unit(&mut board, 12, 4, 2, 5);
        add_enemy_with_type(&mut board, 1, 0, 3, 5, "Centipede2", 4, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[target_idx].hp, 3, "Primary target should take 2 damage");
        assert!(board.units[target_idx].acid(), "Primary target should be ACID'd");
        assert_eq!(board.units[north_idx].hp, 3, "Perpendicular N tile should take 2 damage");
        assert!(board.units[north_idx].acid(), "Perpendicular N tile should be ACID'd");
        assert_eq!(board.units[south_idx].hp, 3, "Perpendicular S tile should take 2 damage");
        assert!(board.units[south_idx].acid(), "Perpendicular S tile should be ACID'd");
    }

    #[test]
    fn test_alpha_centipede_converts_water_to_acid_tile() {
        // Alpha Centipede at (0,3) firing east, primary target (4,3).
        // Need an obstacle at (4,3) so projectile stops there — use a mech.
        // Perpendicular tile (4,4) is WATER — splash acid should convert it
        // to an A.C.I.D. Tile (water + acid flag).
        let mut board = Board::default();
        board.tile_mut(4, 4).terrain = Terrain::Water;
        let _mech_idx = add_mech_unit(&mut board, 10, 4, 3, 5);
        add_enemy_with_type(&mut board, 1, 0, 3, 5, "Centipede2", 4, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(4, 4).terrain, Terrain::Water,
            "Water tile stays water (now A.C.I.D. Tile, i.e. water + acid flag)");
        assert!(board.tile(4, 4).acid(),
            "Water tile hit by acid splash should become A.C.I.D. Tile");
    }

    #[test]
    fn test_alpha_centipede_converts_ground_to_acid_pool() {
        // Perpendicular splash on empty ground should create an acid pool.
        // Mech at primary target stops the projectile so splash lands.
        let mut board = Board::default();
        board.tile_mut(4, 4).terrain = Terrain::Ground;
        let _mech_idx = add_mech_unit(&mut board, 10, 4, 3, 5);
        add_enemy_with_type(&mut board, 1, 0, 3, 5, "Centipede2", 4, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(board.tile(4, 4).acid(),
            "Ground tile hit by acid splash should become A.C.I.D. Pool");
    }

    #[test]
    fn test_centipede_leader_acidifies_projectile_path() {
        // Centipede Leader at (0,3) firing east into a mech at (4,3).
        // Caustic Vomit damages/acidifies the impact T shape like Alpha
        // Centipede, and additionally applies zero-damage A.C.I.D. to
        // every tile in the flight path before impact.
        let mut board = Board::default();
        let target_idx = add_mech_unit(&mut board, 10, 4, 3, 6);
        add_enemy_with_type(&mut board, 1, 0, 3, 7, "CentipedeBoss", 4, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[target_idx].hp, 3, "Primary target should take 3 damage");
        assert!(board.units[target_idx].acid(), "Primary target should be ACID'd");
        for x in 1..4 {
            assert!(board.tile(x, 3).acid(), "path tile ({},3) should become A.C.I.D.", x);
        }
    }

    #[test]
    fn test_centipede_attack_lands_on_board_edge() {
        // Reproduces live scenario: Alpha Centipede at (0, 3) = E8 with
        // queued_target (0, 4) = D8 (first tile in +y attack direction).
        // Projectile walks +y through empty tiles D8..B8, past the edge,
        // falls back to A8 (last valid tile), and splashes A7 perpendicular.
        // Previously find_projectile_target returned None when the path
        // had no obstacle, skipping the attack entirely.
        let mut board = Board::default();
        board.tile_mut(0, 7).terrain = Terrain::Water;  // A8 = water
        board.tile_mut(1, 7).terrain = Terrain::Water;  // A7 = water
        let mut unit = Unit {
            uid: 1, x: 0, y: 3, hp: 5, max_hp: 5,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            queued_target_x: 0,  // first tile in attack direction
            queued_target_y: 4,  // +y from (0,3)
            weapon_damage: 0,
            ..Default::default()
        };
        unit.set_type_name("Centipede2");
        board.add_unit(unit);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        // A8 (primary impact) should be an acid tile
        assert!(board.tile(0, 7).acid(),
            "A8 (last-valid impact) should convert to A.C.I.D. Tile");
        // A7 (perpendicular splash) should also be an acid tile
        assert!(board.tile(1, 7).acid(),
            "A7 (perpendicular splash) should convert to A.C.I.D. Tile");
    }

    #[test]
    fn test_firefly_boss_fires_forward_and_backward_projectiles() {
        let mut board = Board::default();
        board.grid_power = 7;
        board.grid_power_max = 7;
        {
            let tile = board.tile_mut(2, 6);
            tile.terrain = Terrain::Building;
            tile.building_hp = 2;
        }

        add_enemy_with_type(&mut board, 803, 5, 6, 6, "FireflyBoss", 6, 6);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(
            board.tile(2, 6).terrain,
            Terrain::Rubble,
            "backward Burning Thorax projectile should destroy the first building behind the leader"
        );
        assert_eq!(board.grid_power, 5);
        assert_eq!(result.grid_damage, 2);
    }

    #[test]
    fn test_webb_egg_does_not_attack() {
        // WebbEgg1 at (3,3) with queued_target = own tile (3,3). The egg's
        // "action" is to hatch into a Spiderling — not an attack. Without
        // the skip, the fallback melee path would apply 1 damage to the
        // egg's own tile, self-destructing a 1-HP egg (phantom death).
        // Post-sim-v22 the egg now hatches in place (becomes Spiderling1)
        // instead of staying an egg, but it still must not self-damage.
        let mut board = Board::default();
        let egg_idx = add_enemy_with_type(&mut board, 1, 3, 3, 1, "WebbEgg1", 3, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[egg_idx].hp, 1,
            "Egg should not self-damage on its turn (hatching, not attacking)");
    }

    /// Sim v22/v115 hatch step: a WebbEgg present at the start of the enemy
    /// phase transforms into a Spiderling. The hatchling has no queued attack
    /// on its hatch turn (real-game: bite happens turn after hatch), so its
    /// own tile is not damaged. The unit's type_name flips, move_speed/weapon
    /// are bound to Spiderling stats, and live-style `sPawn` fallback can place
    /// it adjacent to the occupied egg tile.
    #[test]
    fn test_webb_egg_hatches_into_spiderling() {
        let mut board = Board::default();
        let egg_idx = add_enemy_with_type(&mut board, 1, 3, 3, 1, "WebbEgg1", 3, 3);
        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        let u = &board.units[egg_idx];
        assert_eq!(u.type_name_str(), "Spiderling1",
            "WebbEgg1 should hatch into Spiderling1");
        assert_eq!(u.hp, 1, "hatched Spiderling inherits 1 HP");
        assert_eq!(u.move_speed, 3, "Spiderling has move_speed=3 per pawn_stats");
        assert_eq!((u.x, u.y), (3, 2),
            "sPawn fallback should prefer bridge y-1 from the occupied egg tile");
        assert!(!u.has_queued_attack(),
            "fresh hatchling has no queued attack on its hatch turn");
        assert_eq!(u.queued_target_x, -1,
            "queued_target cleared so phantom-attack guard `continue`s");
    }

    #[test]
    fn test_webb_egg_hatches_onto_adjacent_building() {
        // Hard Rusting Hulks HQ regression: WebbEgg1 at visual E6 (bridge 2,3)
        // hatched onto adjacent F6 (bridge 2,2), destroying a 2-HP building and
        // draining exactly 2 grid before the next player turn.
        let mut board = Board::default();
        board.grid_power = 4;
        board.tile_mut(2, 2).terrain = Terrain::Building;
        board.tile_mut(2, 2).building_hp = 2;
        let egg_idx = add_enemy_with_type(&mut board, 1, 2, 3, 1, "WebbEgg1", 2, 3);

        let orig = default_orig_pos(&board);
        let grid_damage = simulate_enemy_attacks(&mut board, &orig, &WEAPONS).grid_damage;

        let u = &board.units[egg_idx];
        assert_eq!(u.type_name_str(), "Spiderling1");
        assert_eq!((u.x, u.y), (2, 2),
            "hatchling should occupy the adjacent building tile the live game selected");
        assert_eq!(board.tile(2, 2).building_hp, 0);
        assert_eq!(board.tile(2, 2).terrain, Terrain::Rubble);
        assert_eq!(board.grid_power, 2);
        assert_eq!(grid_damage, 2);
        assert!(!u.has_queued_attack(),
            "fresh hatchling still does not bite on the hatch turn");
    }

    #[test]
    fn test_webb_egg_hatch_fallback_skips_occupied_first_tile() {
        let mut board = Board::default();
        let mut blocker = Unit {
            uid: 2, x: 3, y: 2, hp: 3, max_hp: 3,
            team: Team::Player,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        };
        blocker.set_type_name("JetMech");
        board.add_unit(blocker);
        board.grid_power = 5;
        board.tile_mut(4, 3).terrain = Terrain::Building;
        board.tile_mut(4, 3).building_hp = 1;
        let egg_idx = add_enemy_with_type(&mut board, 1, 3, 3, 1, "WebbEgg1", 3, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!((board.units[egg_idx].x, board.units[egg_idx].y), (4, 3),
            "occupied y-1 tile should be skipped in favor of x+1 fallback");
        assert_eq!(board.grid_power, 4);
    }

    #[test]
    fn test_webb_egg_hatch_skips_shielded_building() {
        let mut board = Board::default();
        board.grid_power = 5;
        board.tile_mut(2, 2).terrain = Terrain::Building;
        board.tile_mut(2, 2).building_hp = 2;
        board.tile_mut(2, 2).set_shield(true);
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 1;
        let egg_idx = add_enemy_with_type(&mut board, 1, 2, 3, 1, "WebbEgg1", 2, 3);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!((board.units[egg_idx].x, board.units[egg_idx].y), (3, 3),
            "shielded first building should not be selected as sPawn fallback");
        assert_eq!(board.tile(2, 2).building_hp, 2,
            "shielded skipped building should be preserved");
        assert_eq!(board.tile(3, 3).building_hp, 0);
        assert_eq!(board.grid_power, 4);
    }

    #[test]
    fn test_webb_egg_hatch_all_adjacent_invalid_stays_on_egg_tile() {
        let mut board = Board::default();
        board.tile_mut(0, 1).terrain = Terrain::Water;
        board.tile_mut(1, 0).terrain = Terrain::Chasm;
        let egg_idx = add_enemy_with_type(&mut board, 1, 0, 0, 1, "WebbEgg1", 0, 0);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[egg_idx].type_name_str(), "Spiderling1");
        assert_eq!((board.units[egg_idx].x, board.units[egg_idx].y), (0, 0),
            "if every adjacent fallback tile is invalid, only the type flips");
    }

    #[test]
    fn test_alpha_spider_egg_hatches_into_regular_spiderling() {
        // Verified against game Lua source 2026-04-25:
        //   weapons_enemy.lua:815 `SpiderAtk2 = SpiderAtk1:new{...}` does
        //   not override `MyPawn`, so Spider2 (Alpha) inherits MyPawn =
        //   "WebbEgg1". And weapons_enemy.lua:830 WebeggHatch1.SpiderType =
        //   "Spiderling1". So Alpha Spider eggs hatch to a regular
        //   Spiderling1 (1 HP, 1 dmg melee), NOT a Spiderling2 Alpha.
        //   Localization confirms: SpiderAtk2_Description = "Throw a
        //   sticky egg that hatches into a Spiderling." (singular,
        //   regular).
        // Pre-v23 sim claimed there was a `WebbEgg2` that hatched into
        // `Spiderling2`; that pawn type does not exist in pawns.lua.
        // This test guards against re-introducing that fiction.
        let mut board = Board::default();
        // The egg laid by Spider2 is still a WebbEgg1 — no separate type.
        let egg_idx = add_enemy_with_type(&mut board, 1, 4, 4, 1, "WebbEgg1", 4, 4);
        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);
        assert_eq!(board.units[egg_idx].type_name_str(), "Spiderling1",
            "All vanilla spider eggs (regular and Alpha-laid) hatch into Spiderling1; \
             WebbEgg2 is bestiary-doc fiction (no such pawn in pawns.lua)");
    }

    #[test]
    fn test_spiderling_egg_hatches_into_spiderling() {
        // SpiderlingEgg1 (Corporate HQ SpiderBoss finale) → Spiderling1
        let mut board = Board::default();
        let egg_idx = add_enemy_with_type(&mut board, 1, 5, 5, 1, "SpiderlingEgg1", 5, 5);
        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);
        assert_eq!(board.units[egg_idx].type_name_str(), "Spiderling1",
            "SpiderlingEgg1 should hatch into Spiderling1");
    }

    #[test]
    fn test_spider_psion_death_egg_spawns_on_fire() {
        let mut board = Board::default();
        board.tile_mut(3, 3).set_on_fire(true);

        assert!(spawn_spider_psion_death_egg(&mut board, 3, 3));
        let egg_idx = board.unit_at(3, 3).expect("death egg should spawn");
        assert_eq!(board.units[egg_idx].type_name_str(), "SpiderlingEgg1");
        assert!(board.units[egg_idx].fire(), "death egg should inherit burning tile fire");
    }

    #[test]
    fn test_dead_egg_does_not_hatch() {
        // Egg killed by player attack pre-enemy-phase: hp=0 going in.
        // Hatch step must skip dead units so we don't resurrect Spiderlings.
        let mut board = Board::default();
        let mut unit = Unit {
            uid: 1, x: 2, y: 2, hp: 0, max_hp: 1,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            queued_target_x: 2,
            queued_target_y: 2,
            ..Default::default()
        };
        unit.set_type_name("WebbEgg1");
        let idx = board.add_unit(unit);
        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);
        assert_eq!(board.units[idx].type_name_str(), "WebbEgg1",
            "Dead egg must not hatch (resurrection guard)");
        assert_eq!(board.units[idx].hp, 0, "Dead egg stays dead");
    }

    #[test]
    fn test_alpha_scorpion_webs_target() {
        let mut board = Board::default();
        // Alpha Scorpion at (3,3) adjacent to mech at (3,4). Goring Spinneret:
        // 3 damage + WEB.
        let mech_idx = add_mech_unit(&mut board, 10, 3, 4, 5);
        let _scorp_idx = add_enemy_with_type(&mut board, 42, 3, 3, 5, "Scorpion2", 3, 4);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[mech_idx].hp, 2, "Mech should take 3 damage from Goring Spinneret");
        assert!(board.units[mech_idx].web(), "Mech should be webbed by Goring Spinneret");
        assert_eq!(board.units[mech_idx].web_source_uid, 42,
            "Web source should be Scorpion UID (for web-break on push/kill)");
    }

    #[test]
    fn test_alpha_hornet_weapon_id_hits_both_tiles_without_bridge_flag() {
        // Regression: HornetAtk2 itself defines the two-tile line. A legacy or
        // partial bridge payload must not silently lose the second hit when
        // weapon_target_behind is absent/false.
        let mut board = Board::default();
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 1;
        board.tile_mut(4, 3).terrain = Terrain::Building;
        board.tile_mut(4, 3).building_hp = 1;
        // Hornet at (2,3) firing east, queued target (3,3). Deliberately leave
        // weapon_target_behind false so the exact weapon identity is the proof.
        let mut unit = Unit {
            uid: 1, x: 2, y: 3, hp: 4, max_hp: 4,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            queued_target_x: 3,
            queued_target_y: 3,
            weapon_damage: 0,
            weapon_target_behind: false,
            ..Default::default()
        };
        unit.set_type_name("Hornet2");
        board.add_unit(unit);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(3, 3).building_hp, 0, "First tile destroyed");
        assert_eq!(board.tile(4, 3).building_hp, 0, "Behind tile destroyed");
    }

    // ── Pilot_Rock fire tick ────────────────────────────────────────────────

    #[test]
    fn test_pushed_alpha_hornet_reanchors_line_from_current_position() {
        let mut board = Board::default();
        for x in 2..=4 {
            board.tile_mut(x, 3).terrain = Terrain::Building;
            board.tile_mut(x, 3).building_hp = 1;
        }
        // Originally (2,3) -> (3,3), then pushed west to (1,3). The bridge
        // normalizes the selected tile to (2,3) while retaining the raw shot
        // and origin. Live therefore hits (2,3) and (3,3), not (3,3)/(4,3).
        let mut unit = Unit {
            uid: 1,
            x: 1,
            y: 3,
            hp: 4,
            max_hp: 4,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE
                | UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
            queued_target_x: 2,
            queued_target_y: 3,
            queued_target_raw_x: 3,
            queued_target_raw_y: 3,
            queued_origin_x: 2,
            queued_origin_y: 3,
            ..Default::default()
        };
        unit.set_type_name("Hornet2");
        board.add_unit(unit);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(2, 3).building_hp, 0, "re-anchored first tile");
        assert_eq!(board.tile(3, 3).building_hp, 0, "re-anchored second tile");
        assert_eq!(board.tile(4, 3).building_hp, 1, "stale behind tile survives");
    }

    #[test]
    fn test_pushed_hornet_boss_reanchors_full_offset_line() {
        let mut board = Board::default();
        for x in 3..=6 {
            board.tile_mut(x, 3).terrain = Terrain::Building;
            board.tile_mut(x, 3).building_hp = 1;
        }
        // Originally (2,3) -> (4,3), then pushed west to (1,3). Artillery
        // preserves the full +2 offset, so Super Stinger hits (3,3)..(5,3).
        let mut unit = Unit {
            uid: 1,
            x: 1,
            y: 3,
            hp: 6,
            max_hp: 6,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE
                | UnitFlags::HAS_QUEUED_ATTACK
                | UnitFlags::QUEUED_ORIGIN_SET
                | UnitFlags::QUEUED_RAW_TARGET_SET,
            queued_target_x: 3,
            queued_target_y: 3,
            queued_target_raw_x: 4,
            queued_target_raw_y: 3,
            queued_origin_x: 2,
            queued_origin_y: 3,
            ..Default::default()
        };
        unit.set_type_name("HornetBoss");
        board.add_unit(unit);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        for x in 3..=5 {
            assert_eq!(board.tile(x, 3).building_hp, 0, "re-anchored line tile {x}");
        }
        assert_eq!(board.tile(6, 3).building_hp, 1, "stale third tile survives");
    }

    #[test]
    fn test_pilot_rock_skips_fire_tick() {
        // Defensive guard: even if FIRE somehow gets set on Ariadne, the
        // fire-tick loop clears it and deals no damage.
        use crate::board::{PilotFlags, UnitFlags};
        let mut board = Board::default();
        let mut unit = Unit {
            uid: 1, x: 3, y: 3, hp: 5, max_hp: 5,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::ACTIVE | UnitFlags::FIRE,
            pilot_flags: PilotFlags::ROCK,
            move_speed: 3,
            ..Default::default()
        };
        unit.set_type_name("PunchMech");
        let idx = board.add_unit(unit);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[idx].hp, 5,
            "Pilot_Rock (Ariadne) must take 0 fire-tick damage");
        assert!(!board.units[idx].fire(),
            "Fire flag cleared as a safety net");
    }

    #[test]
    fn test_non_rock_takes_fire_tick_damage() {
        // Control: a player mech without Pilot_Rock still takes 1 fire
        // damage at the start of the enemy phase.
        use crate::board::UnitFlags;
        let mut board = Board::default();
        let mut unit = Unit {
            uid: 1, x: 3, y: 3, hp: 5, max_hp: 5,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::ACTIVE | UnitFlags::FIRE,
            move_speed: 3,
            ..Default::default()
        };
        unit.set_type_name("PunchMech");
        let idx = board.add_unit(unit);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[idx].hp, 4,
            "Default-pilot mech takes 1 fire-tick damage");
        assert!(board.units[idx].fire(),
            "Fire flag persists for a non-Rockman mech");
    }

    #[test]
    fn test_supply_train_types_clear_stale_fire_without_tick_damage() {
        for (uid, type_name) in [
            (2500, "Train_Pawn"),
            (2501, "Train_Damaged"),
            (2502, "Train_Armored"),
            (2503, "Train_Armored_Damage"),
        ] {
            let mut board = Board::default();
            let mut unit = Unit {
                uid,
                x: 3,
                y: 3,
                hp: 1,
                max_hp: 1,
                team: Team::Player,
                flags: UnitFlags::FIRE,
                ..Default::default()
            };
            unit.set_type_name(type_name);
            let idx = board.add_unit(unit);

            let orig = default_orig_pos(&board);
            simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

            assert_eq!(
                board.units[idx].hp, 1,
                "{type_name} must ignore enemy-phase fire damage"
            );
            assert!(
                !board.units[idx].fire(),
                "{type_name} should clear a stale FIRE flag"
            );
        }
    }

    #[test]
    fn test_protobomb_clears_stale_fire_without_tick_damage() {
        use crate::board::UnitFlags;
        let mut board = Board::default();
        let mut unit = Unit {
            uid: 2600,
            x: 3,
            y: 3,
            hp: 1,
            max_hp: 1,
            team: Team::Player,
            flags: UnitFlags::FIRE,
            ..Default::default()
        };
        unit.set_type_name("ProtoBomb");
        let idx = board.add_unit(unit);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[idx].hp, 1);
        assert!(!board.units[idx].fire());
    }

    #[test]
    fn test_flame_shielding_does_not_skip_ally_fire_tick() {
        // Regression: Archive_Tank is team Player but not a mech. Flame
        // Shielding must not prevent its fire tick.
        use crate::board::UnitFlags;
        let mut board = Board::default();
        board.flame_shielding = true;
        let mut unit = Unit {
            uid: 5326, x: 5, y: 1, hp: 1, max_hp: 1,
            team: Team::Player,
            flags: UnitFlags::ACTIVE | UnitFlags::FIRE,
            weapon: crate::board::WeaponId(WId::DeployTankShot as u16),
            move_speed: 0,
            ..Default::default()
        };
        unit.set_type_name("Archive_Tank");
        let idx = board.add_unit(unit);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[idx].hp, 0);
    }

    #[test]
    fn test_reactivation_thaws_two_per_enemy_turn() {
        // Mission_Reactivation thaws 2 frozen Vek per enemy turn.
        // Set up 4 frozen enemies on a Mission_Reactivation board with
        // no queued attacks (frozen pawns don't queue attacks). After
        // simulate_enemy_attacks, the 2 lowest-uid pawns should be
        // unfrozen (deterministic stand-in for the Lua random_removal),
        // the other 2 should still be frozen.
        let mut board = Board::default();
        board.mission_id = "Mission_Reactivation".to_string();
        for (uid, x) in [(10u16, 0u8), (20, 2), (30, 4), (40, 6)].iter() {
            let mut u = Unit {
                uid: *uid, x: *x, y: 0, hp: 3, max_hp: 3,
                team: Team::Enemy,
                flags: UnitFlags::FROZEN,
                queued_target_x: -1, queued_target_y: -1,
                weapon_damage: 0,
                ..Default::default()
            };
            u.set_type_name("Scorpion1");
            board.add_unit(u);
        }

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        // Two lowest-uid (10, 20) thawed; (30, 40) still frozen.
        let by_uid = |uid: u16| board.units.iter()
            .find(|u| u.uid == uid).expect("unit");
        assert!(!by_uid(10).frozen(), "uid 10 should thaw (lowest)");
        assert!(!by_uid(20).frozen(), "uid 20 should thaw (2nd lowest)");
        assert!(by_uid(30).frozen(), "uid 30 should remain frozen");
        assert!(by_uid(40).frozen(), "uid 40 should remain frozen");
    }

    #[test]
    fn test_reactivation_thaw_skipped_on_other_missions() {
        // Identical setup but mission_id != Mission_Reactivation: no
        // pawns should thaw.
        let mut board = Board::default();
        board.mission_id = "Mission_Stasis".to_string();
        for (uid, x) in [(10u16, 0u8), (20, 2)].iter() {
            let mut u = Unit {
                uid: *uid, x: *x, y: 0, hp: 3, max_hp: 3,
                team: Team::Enemy,
                flags: UnitFlags::FROZEN,
                queued_target_x: -1, queued_target_y: -1,
                weapon_damage: 0,
                ..Default::default()
            };
            u.set_type_name("Scorpion1");
            board.add_unit(u);
        }

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        for u in board.units.iter().take(board.unit_count as usize) {
            assert!(u.frozen(), "no thaw on non-Reactivation mission");
        }
    }

    #[test]
    fn test_reactivation_thaw_caps_at_two_even_with_more_frozen() {
        // 5 frozen enemies → only 2 thaw.
        let mut board = Board::default();
        board.mission_id = "Mission_Reactivation".to_string();
        for (uid, x) in [(1u16, 0u8), (2, 1), (3, 2), (4, 3), (5, 4)].iter() {
            let mut u = Unit {
                uid: *uid, x: *x, y: 0, hp: 3, max_hp: 3,
                team: Team::Enemy,
                flags: UnitFlags::FROZEN,
                queued_target_x: -1, queued_target_y: -1,
                weapon_damage: 0,
                ..Default::default()
            };
            u.set_type_name("Scorpion1");
            board.add_unit(u);
        }

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        let thawed = board.units.iter()
            .take(board.unit_count as usize)
            .filter(|u| !u.frozen())
            .count();
        assert_eq!(thawed, 2, "exactly 2 thaw per enemy turn");
    }

    // ── Pinnacle Bot Leader (sim v31) ─────────────────────────────────────────

    /// SnowBossAtk hits 3 tiles in a T-pattern (target + both perpendicular)
    /// for 2 damage each. Per `bot.lua:67` SnowBossAtk inherits SnowartAtk1's
    /// SkillEffect (weapons_snow.lua:120-135) which damages
    /// p2 + p2+DIR_VECTORS[(dir+1)%4] + p2+DIR_VECTORS[(dir-1)%4].
    #[test]
    fn test_snow_boss_atk_hits_three_tiles() {
        let mut board = Board::default();
        // Bot Leader at (0,3) — full HP so it casts SnowBossAtk (not BossHeal).
        // Targets (3,3): SnowartAtk1 fires east. dir=East (+x).
        // Perp tiles: (3,2) and (3,4).
        // Place 3 buildings at the 3 expected hit tiles.
        for (bx, by) in [(3, 3), (3, 2), (3, 4)] {
            board.tile_mut(bx, by).terrain = Terrain::Building;
            board.tile_mut(bx, by).building_hp = 3; // 3 HP so 2 dmg leaves 1
        }
        let mut boss = Unit {
            uid: 1, x: 0, y: 3, hp: 5, max_hp: 5,
            team: Team::Enemy,
            flags: UnitFlags::HAS_QUEUED_ATTACK,
            queued_target_x: 3, queued_target_y: 3,
            weapon_damage: 2,
            weapon: WeaponId(WId::SnowBossAtk as u16),
            weapon2: WeaponId(WId::BossHeal as u16),
            ..Default::default()
        };
        boss.set_type_name("BotBoss");
        board.add_unit(boss);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        // All three buildings took 2 damage each → 1 HP remaining.
        assert_eq!(board.tile(3, 3).building_hp, 1,
            "center tile (3,3) should take 2 dmg from SnowBossAtk");
        assert_eq!(board.tile(3, 2).building_hp, 1,
            "perp tile (3,2) should take 2 dmg from SnowBossAtk");
        assert_eq!(board.tile(3, 4).building_hp, 1,
            "perp tile (3,4) should take 2 dmg from SnowBossAtk");
    }

    /// SnowBossAtk2 (BotBoss2): same shape, 4 damage per tile.
    #[test]
    fn test_snow_boss_atk2_hits_three_tiles_for_four_damage() {
        let mut board = Board::default();
        for (bx, by) in [(3, 3), (3, 2), (3, 4)] {
            board.tile_mut(bx, by).terrain = Terrain::Building;
            board.tile_mut(bx, by).building_hp = 5;
        }
        let mut boss = Unit {
            uid: 1, x: 0, y: 3, hp: 6, max_hp: 6,
            team: Team::Enemy,
            flags: UnitFlags::HAS_QUEUED_ATTACK,
            queued_target_x: 3, queued_target_y: 3,
            weapon_damage: 4,
            weapon: WeaponId(WId::SnowBossAtk2 as u16),
            weapon2: WeaponId(WId::BossHeal as u16),
            ..Default::default()
        };
        boss.set_type_name("BotBoss2");
        board.add_unit(boss);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(3, 3).building_hp, 1, "center (3,3): 5-4=1");
        assert_eq!(board.tile(3, 2).building_hp, 1, "perp (3,2): 5-4=1");
        assert_eq!(board.tile(3, 4).building_hp, 1, "perp (3,4): 5-4=1");
    }

    #[test]
    fn test_bouncer_boss_enemy_attack_hits_t_pattern_and_bounces() {
        let mut board = Board::default();
        let center = board.add_unit(Unit {
            uid: 20, x: 3, y: 4, hp: 4, max_hp: 4,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::PUSHABLE,
            ..Default::default()
        });
        let left = board.add_unit(Unit {
            uid: 21, x: 2, y: 4, hp: 4, max_hp: 4,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::PUSHABLE,
            ..Default::default()
        });
        let right = board.add_unit(Unit {
            uid: 22, x: 4, y: 4, hp: 4, max_hp: 4,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let boss = add_enemy_with_type(&mut board, 10, 3, 3, 4, "BouncerBoss", 3, 4);
        board.units[boss].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!((board.units[boss].x, board.units[boss].y), (3, 2),
            "Bouncer Leader should bounce backward after attacking");
        assert_eq!((board.units[center].x, board.units[center].y), (3, 5));
        assert_eq!(board.units[center].hp, 2);
        assert_eq!((board.units[left].x, board.units[left].y), (2, 5));
        assert_eq!(board.units[left].hp, 2);
        assert_eq!((board.units[right].x, board.units[right].y), (4, 5));
        assert_eq!(board.units[right].hp, 2);
    }

    /// BossHeal applies Shield to self when boss is damaged. Per
    /// `bot.lua:32-41`, `BossHeal:GetSkillEffect` calls `AddDamage(SpaceDamage(p1))`
    /// with `iShield = 1` immediately. The detection in enemy.rs requires
    /// type=BotBoss/BotBoss2, weapon2=BossHeal, and hp<max_hp; under those
    /// conditions the dispatch wid is overridden to BossHeal and shield is
    /// applied to the boss's own tile.
    #[test]
    fn test_boss_heal_applies_shield_when_damaged() {
        let mut board = Board::default();
        // Damaged boss (3/5 HP) — IsDamaged() is true → telegraphs BossHeal.
        let mut boss = Unit {
            uid: 1, x: 4, y: 4, hp: 3, max_hp: 5,
            team: Team::Enemy,
            flags: UnitFlags::HAS_QUEUED_ATTACK,
            // Bridge typically reports queued_target = self for SelfTarget skills.
            queued_target_x: 4, queued_target_y: 4,
            weapon_damage: 2, // bridge always reports weapons[0].Damage
            weapon: WeaponId(WId::SnowBossAtk as u16),
            weapon2: WeaponId(WId::BossHeal as u16),
            ..Default::default()
        };
        boss.set_type_name("BotBoss");
        let bidx = board.add_unit(boss);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(board.units[bidx].shield(),
            "Damaged Bot Leader should apply Shield to itself via BossHeal");
        assert_eq!(board.units[bidx].hp, 3,
            "Boss HP unchanged (BossHeal deals 0 damage; queued +5 heal is NOT in 1-turn horizon)");
    }

    /// At full HP the boss does NOT cast BossHeal — `BotBoss:GetWeapon()`
    /// returns 1 (SnowBossAtk) when not damaged. The detection condition
    /// `hp < max_hp` is false, so the artillery arm fires normally.
    #[test]
    fn test_boss_does_not_heal_when_undamaged() {
        let mut board = Board::default();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 3;
        let mut boss = Unit {
            uid: 1, x: 0, y: 4, hp: 5, max_hp: 5, // FULL HP
            team: Team::Enemy,
            flags: UnitFlags::HAS_QUEUED_ATTACK,
            queued_target_x: 3, queued_target_y: 4,
            weapon_damage: 2,
            weapon: WeaponId(WId::SnowBossAtk as u16),
            weapon2: WeaponId(WId::BossHeal as u16),
            ..Default::default()
        };
        boss.set_type_name("BotBoss");
        let bidx = board.add_unit(boss);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(!board.units[bidx].shield(),
            "Undamaged boss should fire SnowBossAtk (no shield from BossHeal)");
        assert_eq!(board.tile(3, 4).building_hp, 1,
            "Building should take 2 dmg from SnowBossAtk center tile");
    }

    #[test]
    fn test_mosquito_leader_kills_through_shield_and_smokes_target() {
        let mut board = Board::default();
        let mut target = Unit {
            uid: 2,
            x: 4,
            y: 5,
            hp: 5,
            max_hp: 5,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::PUSHABLE,
            ..Default::default()
        };
        target.set_shield(true);
        let tidx = board.add_unit(target);

        let boss = add_enemy_with_type(&mut board, 1, 4, 4, 5, "MosquitoBoss", 4, 5);
        board.units[boss].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[tidx].hp, 0, "Mosquito Leader kill bypasses shield");
        assert!(!board.units[tidx].shield(), "bypassed shield is removed with the dead unit");
        assert!(board.tile(4, 5).smoke(), "Cloudburst Tentacles smokes the target tile");
    }

    fn add_player_mech(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8) -> usize {
        board.add_unit(Unit {
            uid,
            x,
            y,
            hp,
            max_hp: hp,
            team: Team::Player,
            flags: UnitFlags::IS_MECH | UnitFlags::PUSHABLE,
            ..Default::default()
        })
    }

    #[test]
    fn test_networked_shielding_blocks_player_phase_damage_but_not_enemy_attack() {
        let mut board = Board::default();
        board.networked_shielding = true;
        let mech = add_player_mech(&mut board, 2, 3, 4, 3);

        let mut player_result = ActionResult::default();
        apply_damage(
            &mut board,
            3,
            4,
            2,
            &mut player_result,
            DamageSource::SelfDamage,
        );
        assert_eq!(board.units[mech].hp, 3);
        assert_eq!(player_result.mech_damage_taken, 0);

        let vek = add_enemy_with_type(&mut board, 1, 3, 3, 2, "Hornet1", 3, 4);
        board.units[vek].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
        let orig = default_orig_pos(&board);
        let enemy_result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert!(!board.networked_shielding);
        assert_eq!(board.units[mech].hp, 2);
        assert_eq!(enemy_result.mech_damage_taken, 1);
    }

    #[test]
    fn test_networked_shielding_blocks_player_turn_old_earth_mine_damage() {
        let mut board = Board::default();
        board.networked_shielding = true;
        let mech = add_player_mech(&mut board, 2, 3, 3, 3);
        board.tile_mut(4, 3).set_old_earth_mine(true);

        let result = simulate_move(&mut board, mech, (4, 3));

        assert_eq!(board.units[mech].hp, 3);
        assert_eq!(result.mechs_killed, 0);
        assert!(!board.tile(4, 3).old_earth_mine());
    }

    #[test]
    fn test_void_shocker_retaliates_after_empty_attack() {
        let mut board = Board::default();
        board.void_shocker_damage = 1;
        let vek = add_enemy_with_type(&mut board, 1, 3, 3, 2, "Hornet1", 3, 4);
        board.units[vek].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.units[vek].hp, 1);
        assert_eq!(result.enemy_damage_dealt, 1);
        assert!(result.events.iter().any(|event| event.starts_with("void_shocker:1:")));
    }

    #[test]
    fn test_void_shocker_retaliates_when_attack_only_damages_mountain() {
        let mut board = Board::default();
        board.void_shocker_damage = 1;
        board.tile_mut(3, 4).terrain = Terrain::Mountain;
        board.tile_mut(3, 4).building_hp = 2;
        let vek = add_enemy_with_type(&mut board, 1, 3, 3, 2, "Hornet1", 3, 4);
        board.units[vek].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(3, 4).building_hp, 1);
        assert_eq!(board.units[vek].hp, 1);
    }

    #[test]
    fn test_void_shocker_does_not_retaliate_after_unit_or_building_damage() {
        for target_kind in ["unit", "building"] {
            let mut board = Board::default();
            board.void_shocker_damage = 1;
            let vek = add_enemy_with_type(&mut board, 1, 3, 3, 2, "Hornet1", 3, 4);
            board.units[vek].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
            if target_kind == "unit" {
                add_player_mech(&mut board, 2, 3, 4, 3);
            } else {
                board.tile_mut(3, 4).terrain = Terrain::Building;
                board.tile_mut(3, 4).building_hp = 2;
            }

            let orig = default_orig_pos(&board);
            let result = simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

            assert_eq!(board.units[vek].hp, 2, "target kind: {target_kind}");
            assert!(
                !result.events.iter().any(|event| event.starts_with("void_shocker:")),
                "target kind: {target_kind}"
            );
        }
    }

    #[test]
    fn test_void_shocker_counts_shield_and_frozen_absorption_as_no_damage() {
        for absorbed_by in ["shield", "frozen"] {
            let mut board = Board::default();
            board.void_shocker_damage = 1;
            let vek = add_enemy_with_type(&mut board, 1, 3, 3, 2, "Hornet1", 3, 4);
            board.units[vek].flags.insert(UnitFlags::HAS_QUEUED_ATTACK);
            let mech = add_player_mech(&mut board, 2, 3, 4, 3);
            if absorbed_by == "shield" {
                board.units[mech].set_shield(true);
            } else {
                board.units[mech].set_frozen(true);
            }

            let orig = default_orig_pos(&board);
            simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

            assert_eq!(board.units[mech].hp, 3, "absorption: {absorbed_by}");
            assert_eq!(board.units[vek].hp, 1, "absorption: {absorbed_by}");
        }
    }

    #[test]
    fn test_void_shocker_honors_source_immunity_and_multi_hit_damage() {
        let mut immune_board = Board::default();
        immune_board.void_shocker_damage = 1;
        let immune = add_enemy_with_type(
            &mut immune_board,
            1,
            3,
            3,
            2,
            "Blobber1",
            3,
            4,
        );
        immune_board.units[immune]
            .flags
            .insert(UnitFlags::HAS_QUEUED_ATTACK | UnitFlags::VOID_SHOCK_IMMUNE);
        let orig = default_orig_pos(&immune_board);
        simulate_enemy_attacks(&mut immune_board, &orig, &WEAPONS);
        assert_eq!(immune_board.units[immune].hp, 2);

        let mut multi_board = Board::default();
        multi_board.void_shocker_damage = 1;
        let starfish = add_enemy_with_type(
            &mut multi_board,
            10,
            3,
            3,
            3,
            "Starfish1",
            3,
            3,
        );
        multi_board.units[starfish]
            .flags
            .insert(UnitFlags::HAS_QUEUED_ATTACK);
        let mech = add_player_mech(&mut multi_board, 11, 4, 4, 3);
        let orig = default_orig_pos(&multi_board);
        simulate_enemy_attacks(&mut multi_board, &orig, &WEAPONS);
        assert!(multi_board.units[mech].hp < 3);
        assert_eq!(multi_board.units[starfish].hp, 3);
    }

    /// `enemy_weapon_for_type` mappings for the Bot Leader pawns.
    #[test]
    fn test_bot_leader_weapon_mapping() {
        assert_eq!(enemy_weapon_for_type("BotBoss"), WId::SnowBossAtk);
        assert_eq!(enemy_weapon_for_type("BotBoss2"), WId::SnowBossAtk2);
        assert_eq!(enemy_weapon_for_type("MosquitoBoss"), WId::MosquitoAtkB);
    }
}
