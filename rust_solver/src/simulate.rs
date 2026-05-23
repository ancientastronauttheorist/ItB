/// Weapon simulation engine.
///
/// Given a unit, weapon, and target, compute the resulting board state.
/// Ports all 9 weapon types from Python simulate.py with exact semantic parity.

use crate::types::*;
use crate::board::*;
use crate::weapons::*;
use crate::movement::{direction_between, cardinal_direction};

fn refresh_arrogant_boost(unit: &mut Unit) {
    if unit.pilot_arrogant() {
        unit.set_boosted(unit.hp > 0 && unit.hp >= unit.max_hp);
    }
}

fn refresh_all_arrogant_boosts(board: &mut Board) {
    for i in 0..board.unit_count as usize {
        refresh_arrogant_boost(&mut board.units[i]);
    }
}

fn clear_mites(unit: &mut Unit) {
    if unit.is_player() && unit.is_mech() {
        unit.set_infected(false);
    }
}

// ── Blast Psion death explosion ──────────────────────────────────────────────

/// Apply death explosion: 1 bump damage to all 4 adjacent tiles.
/// Called when an enemy Vek dies while Blast Psion is alive on the board.
/// Eligible non-minor Vek killed by the burst can emit their own Blast Psion
/// explosion; minor pawns still do not receive the aura.
/// Volatile Vek's "Explosive Decay": 1 damage to all 4 adjacent tiles
/// when it dies, for any cause. Bump-class unit damage ignores armor/acid,
/// and the explosion ignites damaged forest tiles.
///
/// Per `data/vek.json` #262 the base-game Volatile Vek explodes for 1
/// damage. Matches the Blast Psion aura in shape but is unit-intrinsic
/// rather than aura-conditional — ``apply_damage``'s "track then check"
/// pattern doesn't need re-entry protection here because the helper
/// calls ``apply_damage_core`` directly (which doesn't re-trigger this
/// helper). A ``depth`` cap still covers the chain-of-volatiles case
/// where one explosion kills an adjacent volatile vek.
pub fn apply_volatile_decay(board: &mut Board, x: u8, y: u8, result: &mut ActionResult, depth: u8) {
    if depth > 8 { return; }

    for &(dx, dy) in &DIRS {
        let nx = x as i8 + dx;
        let ny = y as i8 + dy;
        if nx < 0 || nx >= 8 || ny < 0 || ny >= 8 { continue; }
        let nx = nx as u8;
        let ny = ny as u8;

        let status_blocked = board.unit_at(nx, ny)
            .map(|idx| board.units[idx].shield() || board.units[idx].frozen())
            .unwrap_or(false);

        // Track adjacent Volatile Vek for the chain check — if this 1
        // damage kills one, it explodes too.
        let chain_idx = board.unit_at(nx, ny).and_then(|idx| {
            let u = &board.units[idx];
            if u.is_enemy() && u.hp > 0 && u.is_volatile_vek() {
                Some(idx)
            } else { None }
        });

        apply_damage_core(board, nx, ny, 1, result, DamageSource::Bump);
        apply_explosive_decay_tile_effects(board, nx, ny, status_blocked);

        if let Some(idx) = chain_idx {
            if board.units[idx].hp <= 0 {
                apply_volatile_decay(board, nx, ny, result, depth + 1);
            }
        }
    }
}

fn apply_explosive_decay_tile_effects(board: &mut Board, x: u8, y: u8, status_blocked: bool) {
    if board.tile(x, y).terrain != Terrain::Forest {
        return;
    }

    let tile = board.tile_mut(x, y);
    tile.terrain = Terrain::Ground;
    tile.set_smoke(false);
    tile.set_on_fire(true);

    if let Some(idx) = board.unit_at(x, y) {
        let target_is_immune_vek = board.fire_psion
            && board.units[idx].receives_psion_aura()
            && board.units[idx].type_name_str() != "Jelly_Fire1";
        if !status_blocked
            && board.units[idx].hp > 0
            && board.units[idx].can_catch_fire()
            && !(board.flame_shielding && board.units[idx].is_player() && board.units[idx].is_mech())
            && !target_is_immune_vek
        {
            board.units[idx].set_fire(true);
        }
    }
}

/// Boss/Blast Psion EXPLODE-on-death helper. Public to the crate so
/// non-weapon kill paths (env_danger lethal kills, etc.) can dispatch the
/// explosion themselves — `on_enemy_death` does NOT fire this; explosion
/// dispatch is currently caller-side at apply_damage (weapon kills),
/// `finish_instant_unit_death` (push/swap/throw terrain + mine kills), and
/// apply_env_danger (lethal env kills, since sim v38).
pub(crate) fn apply_death_explosion(board: &mut Board, x: u8, y: u8, result: &mut ActionResult, depth: u8) {
    if depth > 8 { return; }

    for &(dx, dy) in &DIRS {
        let nx = x as i8 + dx;
        let ny = y as i8 + dy;
        if nx < 0 || nx >= 8 || ny < 0 || ny >= 8 { continue; }
        let nx = nx as u8;
        let ny = ny as u8;

        let chain_idx = blast_explosion_chain_candidate(board, nx, ny);
        // Apply 1 bump damage (ignores armor/acid)
        apply_damage_core(board, nx, ny, 1, result, DamageSource::Bump);
        if let Some(idx) = chain_idx {
            if board.units[idx].hp <= 0 {
                apply_death_explosion(board, nx, ny, result, depth + 1);
            }
        }
    }
}

fn blast_explosion_chain_candidate(board: &Board, x: u8, y: u8) -> Option<usize> {
    if !board.blast_psion && !board.boss_psion {
        return None;
    }
    board.unit_at(x, y).and_then(|idx| {
        let u = &board.units[idx];
        let tname = u.type_name_str();
        if u.receives_psion_aura()
            && u.hp > 0
            && tname != "Jelly_Explode1"
            && tname != "Jelly_Boss"
        {
            Some(idx)
        } else {
            None
        }
    })
}

fn apply_bombrock_explosion(
    board: &mut Board,
    x: u8,
    y: u8,
    result: &mut ActionResult,
    exclude: Option<(u8, u8)>,
    depth: u8,
) {
    if depth > 8 { return; }

    for &(dx, dy) in &DIRS {
        let nx = x as i8 + dx;
        let ny = y as i8 + dy;
        if nx < 0 || nx >= 8 || ny < 0 || ny >= 8 { continue; }
        let (nx, ny) = (nx as u8, ny as u8);
        if exclude == Some((nx, ny)) { continue; }
        apply_damage_inner(board, nx, ny, 1, result, DamageSource::Bump, None, depth + 1);
    }
}

// ── Teleporter pad swap (Mission_Teleporter) ─────────────────────────────────

/// End-of-movement teleporter-pad swap. Called from every call site that
/// lands a unit on a new tile: `apply_push` destination-clear branch,
/// `apply_throw` landing, mech-move in `simulate_action`, Swap-weapon in
/// `sim_pull_or_swap`, dash landing in `sim_charge`, leap landing in
/// `sim_leap`. Pull uses `apply_push` so it's covered transitively.
///
/// Game rules (from scripts/missions/acid/mission_teleport.lua + wiki):
///   - Fires only for LIVE units (`hp > 0`). Corpses don't teleport; the
///     unit may have drowned / been mined out before pad evaluation, so
///     callers run this AFTER terrain-kill / old-earth-mine / volatile
///     decay resolves.
///   - If paired pad is empty → unit teleports to partner.
///   - If paired pad has an occupant → the two swap positions.
///   - Pad swap does NOT break web (unlike push). Fire/acid/frozen/shield
///     carry with the swapped unit; no status change.
///   - Does NOT recurse. The adjacent-paired-pads + dash infinite-loop bug
///     is a known vanilla glitch; our deterministic sim fires the swap
///     once per move-end and moves on — matches how a single `MOVE` command
///     lands in the bridge (one pos delta per sub-action).
///   - Safe no-op when `board.teleporter_pairs` is empty (vast majority of
///     missions) — the linear scan in `Board::teleport_partner` is cheap.
#[inline]
pub fn apply_teleport_on_land(board: &mut Board, unit_idx: usize) {
    if board.units[unit_idx].hp <= 0 { return; }
    let ux = board.units[unit_idx].x;
    let uy = board.units[unit_idx].y;
    let (px, py) = match board.teleport_partner(ux, uy) {
        Some(pair) => pair,
        None => return,
    };
    // Partner occupant (if any). `unit_at` skips corpses; a wreck on the
    // partner tile blocks move-onto normally, but pads in vanilla are
    // placed on clear ground so this edge case shouldn't come up. We still
    // guard by checking for a live occupant only — a wreck under the
    // partner silently leaves the wreck where it is (consistent with how
    // push-onto-wreck is treated: blocker).
    let partner_idx = board.unit_at(px, py);
    // Move current unit to the partner pad.
    board.units[unit_idx].x = px;
    board.units[unit_idx].y = py;
    // Swap the partner unit (if any, and not the same pawn in multi-tile
    // edge cases) back onto the original pad.
    if let Some(other_idx) = partner_idx {
        if other_idx != unit_idx {
            board.units[other_idx].x = ux;
            board.units[other_idx].y = uy;
        }
    }
}

/// Resolve Time Pod contact when a unit lands on a tile. Player mechs collect
/// pods; every other live unit destroys the pod without collection credit.
#[inline]
fn apply_pod_on_land(board: &mut Board, unit_idx: usize, result: &mut ActionResult) {
    if board.units[unit_idx].hp <= 0 { return; }
    let x = board.units[unit_idx].x;
    let y = board.units[unit_idx].y;
    if !board.tile(x, y).has_pod() { return; }

    board.tile_mut(x, y).set_has_pod(false);
    if board.units[unit_idx].is_player() && board.units[unit_idx].is_mech() {
        result.pods_collected += 1;
        result.events.push(format!("pod_collected:{}:{}", x, y));
    } else {
        result.events.push(format!("pod_destroyed_by_landing:{}:{}", x, y));
    }
}

// ── apply_landing_effects ────────────────────────────────────────────────────

/// Resolve the post-move landing pipeline at a unit's current tile: own
/// web-break, web-break if the moved unit is an enemy webber, smoke extinguish,
/// Fire pickup, ACID pickup, frozen-grounded-on-water → Ice, water/lava/chasm
/// death (with Flying / Massive exemptions), Lava-ignites-flying, Old Earth
/// Mine, Freeze Mine, repair platform, and finally teleporter-pad swap. Caller
/// must have already updated the unit's `x`/`y` to the destination tile; this
/// function reads `board.units[idx].(x,y)` and resolves effects there.
///
/// Shared between `apply_throw` (Vice Fist relocation) and `sim_pull_or_swap`
/// (Science_Swap Teleporter). Before this helper existed, swap silently
/// skipped every landing effect except teleporter pads — making "swap a Vek
/// into water/chasm/lava" invisible to the solver despite being the Swap
/// Mech's primary kill mode. Confirmed via Lua scripts/weapons_science.lua:216
/// (Science_Swap.GetSkillEffect calls AddTeleport, which routes through the
/// engine's standard tile-landing pipeline) and the in-game tooltip
/// "Swap places with a nearby tile".
///
/// Order matches `apply_throw`'s historical inline ordering exactly so that
/// extracting the helper is a behaviour-preserving refactor on the throw
/// path:
///   1. break the moved unit's own web
///   2. break webs sourced FROM this unit (if enemy webber moved)
///   3. Smoke on tile → clear unit fire
///   4. Fire on tile → set unit fire (Flame Shielding exempts player mechs)
///   5. ACID pool on tile → set unit acid, consume pool
///   6. frozen non-flying + Water → tile becomes Ice, return early
///   7. Water/Lava drown non-flying-non-Massive; Chasm kills any non-flying
///   8. Lava + flying → ignite (Flame Shielding exempts player mechs)
///   9. Old Earth Mine → instant kill, mine consumed
///  10. Freeze Mine → freeze (or pop shield), mine consumed
///  11. Repair platform → heal by Item_Repair_Mine's -10 damage, consume
///  12. Teleporter pad → swap to partner if paired
///  13. WebbEgg1 adjacency refresh → newly adjacent units become webbed
fn apply_repair_platform(board: &mut Board, unit_idx: usize, result: &mut ActionResult) {
    if board.units[unit_idx].hp <= 0 { return; }
    let x = board.units[unit_idx].x;
    let y = board.units[unit_idx].y;
    if !board.tile(x, y).repair_platform() { return; }

    board.tile_mut(x, y).set_repair_platform(false);
    let before = board.units[unit_idx].hp;
    // Lua defines Item_Repair_Mine as SpaceDamage(-10). Live Mission_Repair
    // captures show damaged 3-max-HP mechs healing up to 5/3 while a 2-max-HP
    // Jet stayed at 4/2, matching an overheal cap of max_hp + 2. A full-health
    // mech still consumes/counts the platform, but does not gain extra HP.
    if before < board.units[unit_idx].max_hp {
        let cap = board.units[unit_idx].max_hp.saturating_add(2);
        board.units[unit_idx].hp = before.saturating_add(10).min(cap);
    }
    refresh_arrogant_boost(&mut board.units[unit_idx]);
    board.repair_platforms_used = board.repair_platforms_used.saturating_add(1);
    result.repair_platforms_used += 1;
    result.events.push(format!(
        "repair_platform:{}:{}:{}->{}",
        x, y, before, board.units[unit_idx].hp
    ));
}

fn apply_fire_tile_pickup(board: &mut Board, unit_idx: usize, x: u8, y: u8) {
    if !board.tile(x, y).on_fire() {
        return;
    }
    if board.tile(x, y).terrain == Terrain::Forest {
        board.tile_mut(x, y).terrain = Terrain::Ground;
    }
    let target_is_immune_vek = board.fire_psion
        && board.units[unit_idx].receives_psion_aura()
        && board.units[unit_idx].type_name_str() != "Jelly_Fire1";
    if board.units[unit_idx].hp > 0
        && !board.units[unit_idx].shield()
        && board.units[unit_idx].can_catch_fire()
        && !(board.flame_shielding && board.units[unit_idx].is_player() && board.units[unit_idx].is_mech())
        && !target_is_immune_vek
    {
        board.units[unit_idx].set_fire(true);
    }
}

fn tile_can_host_fire(board: &Board, x: u8, y: u8) -> bool {
    matches!(
        board.tile(x, y).terrain,
        Terrain::Ground | Terrain::Sand | Terrain::Forest | Terrain::Rubble | Terrain::Building
            | Terrain::Ice | Terrain::Fire | Terrain::Mountain
    )
}

fn apply_fire_weapon_unit_status(board: &mut Board, unit_idx: usize) {
    if board.units[unit_idx].shield() {
        return;
    }

    let fire_psion = board.fire_psion;
    let target_is_immune_vek = fire_psion
        && board.units[unit_idx].receives_psion_aura()
        && board.units[unit_idx].type_name_str() != "Jelly_Fire1";

    let u = &mut board.units[unit_idx];
    if u.frozen() {
        u.set_frozen(false);
    }
    if u.can_catch_fire()
        && !(board.flame_shielding && u.is_player() && u.is_mech())
        && !target_is_immune_vek
    {
        u.set_fire(true);
        clear_mites(u);
    }
}

fn apply_smoke_tile_extinguish(board: &mut Board, unit_idx: usize, x: u8, y: u8) {
    if board.tile(x, y).smoke() && board.units[unit_idx].fire() {
        board.units[unit_idx].set_fire(false);
    }
}

fn apply_landing_effects(board: &mut Board, unit_idx: usize, result: &mut ActionResult) {
    let nx = board.units[unit_idx].x;
    let ny = board.units[unit_idx].y;

    // 1. Any actual tile change breaks the moved unit's own web. Blocked
    // pushes do not call this helper, so their grapple remains attached.
    clear_unit_web(board, unit_idx);

    // 2. Web break: enemy webber moved → unweb any mechs they were holding.
    if board.units[unit_idx].is_enemy() {
        let webber_uid = board.units[unit_idx].uid;
        break_web_from(board, webber_uid);
    }

    // 3. Time Pod contact: attack-phase movement (Aerial Bombs, pushes, swaps)
    // collects/destroys pods just like ordinary movement.
    apply_pod_on_land(board, unit_idx, result);

    // 4. Smoke tile: carried unit fire is extinguished on landing.
    apply_smoke_tile_extinguish(board, unit_idx, nx, ny);

    // 5. Fire tile: unit catches fire (Flame Shielding exempts player mechs;
    //    Fire Psion grants Vek the same immunity). Burning Forest is consumed
    //    to burning Ground when a unit lands on it.
    apply_fire_tile_pickup(board, unit_idx, nx, ny);

    // 6. ACID pool: unit gains ACID, pool consumed
    if board.tile(nx, ny).acid() && board.tile(nx, ny).terrain != Terrain::Water {
        if board.units[unit_idx].hp > 0 && !board.units[unit_idx].shield() {
            board.units[unit_idx].set_acid(true);
        }
        board.tile_mut(nx, ny).flags.remove(TileFlags::ACID);
    }

    // 7. Frozen GROUNDED unit on Water → Ice tile (no drown). Frozen FLYING
    // units fall through to the deadly-terrain check below — frozen cancels
    // flight so they drown / fall normally.
    let dest_terrain = board.tile(nx, ny).terrain;
    if board.units[unit_idx].frozen() && !board.units[unit_idx].flying()
        && dest_terrain == Terrain::Water {
        board.tile_mut(nx, ny).terrain = Terrain::Ice;
        board.tile_mut(nx, ny).set_cracked(false);
        return;
    }

    // 8. Water / Lava / Chasm death.
    // 9. Lava + flying → fire status (combined branch).
    if board.units[unit_idx].hp > 0 && !board.units[unit_idx].effectively_flying() {
        let massive = board.units[unit_idx].massive();
        match dest_terrain {
            Terrain::Water | Terrain::Lava => {
                if !massive {
                    finish_instant_unit_death(board, unit_idx, result, nx, ny);
                }
            }
            Terrain::Chasm => {
                finish_instant_unit_death(board, unit_idx, result, nx, ny);
            }
            _ => {}
        }
    } else if board.units[unit_idx].hp > 0 && board.units[unit_idx].effectively_flying()
        && dest_terrain == Terrain::Lava {
        let target_is_immune_vek = board.fire_psion
            && board.units[unit_idx].receives_psion_aura()
            && board.units[unit_idx].type_name_str() != "Jelly_Fire1";
        if !board.units[unit_idx].shield()
            && board.units[unit_idx].can_catch_fire()
            && !(board.flame_shielding && board.units[unit_idx].is_player() && board.units[unit_idx].is_mech())
            && !target_is_immune_vek
        {
            board.units[unit_idx].set_fire(true);
        }
    }

    // 10-11. Mines.
    if board.units[unit_idx].hp > 0 {
        let tile = board.tile(nx, ny);
        if tile.old_earth_mine() {
            finish_instant_unit_death(board, unit_idx, result, nx, ny);
            board.tile_mut(nx, ny).set_old_earth_mine(false);
        } else if tile.freeze_mine() {
            if !board.units[unit_idx].shield() {
                board.units[unit_idx].set_frozen(true);
            } else {
                board.units[unit_idx].set_shield(false);
            }
            board.tile_mut(nx, ny).set_freeze_mine(false);
        }
    }

    // 12. Repair platform item: fires after terrain/mine resolution, before
    // teleporter relocation consumes the unit's landing tile.
    apply_repair_platform(board, unit_idx, result);

    // 13. Teleporter pad: fires LAST, after terrain/mine/item resolution.
    apply_teleport_on_land(board, unit_idx);

    // 14. Spider/Web Egg adjacency webs are tile-based and can apply after a
    // unit lands beside an existing egg or after a teleporter swap.
    board.refresh_webb_egg_grapples();
}

// ── Web break ────────────────────────────────────────────────────────────────

/// Clear the WEB flag on any unit whose web_source_uid matches `src_uid`.
/// Restores move_speed to base_move so the unit can move this turn.
/// Called when an enemy is pushed or killed (both events break ITB grapples).
fn break_web_from(board: &mut Board, src_uid: u16) {
    if src_uid == 0 { return; }
    for i in 0..board.unit_count as usize {
        if board.units[i].web() && board.units[i].web_source_uid == src_uid {
            clear_unit_web(board, i);
        }
    }
}

/// Clear a unit's own web status. A pushed webbed pawn breaks free even when
/// the web source stays put; source movement/death is handled by
/// `break_web_from`.
fn clear_unit_web(board: &mut Board, unit_idx: usize) {
    if !board.units[unit_idx].web() { return; }
    let logical_uid = board.units[unit_idx].uid;
    for i in 0..board.unit_count as usize {
        if board.units[i].uid != logical_uid || !board.units[i].web() {
            continue;
        }
        board.units[i].set_web(false);
        board.units[i].web_source_uid = 0;
        if board.units[i].move_speed == 0 {
            board.units[i].move_speed = board.units[i].base_move;
        }
    }
}

fn leave_acid_pool_on_death(board: &mut Board, x: u8, y: u8) {
    let terrain = board.tile(x, y).terrain;
    if !terrain.is_deadly_ground() || terrain == Terrain::Water {
        let tile = board.tile_mut(x, y);
        tile.flags |= TileFlags::ACID;
        tile.set_on_fire(false);
        if matches!(terrain, Terrain::Ground | Terrain::Sand) {
            tile.terrain = Terrain::Ground;
            tile.set_grass(false);
        }
    }
}

/// Place smoke on a tile. If the tile holds an enemy currently webbing a unit,
/// the smoke-cancelled queued attack releases that grapple immediately.
fn place_smoke(board: &mut Board, x: u8, y: u8) {
    let tile = board.tile_mut(x, y);
    tile.set_on_fire(false); // smoke replaces fire
    tile.set_smoke(true);

    if let Some(idx) = board.unit_at(x, y) {
        if board.units[idx].is_enemy() {
            let uid = board.units[idx].uid;
            break_web_from(board, uid);
        }
    }
}

// ── apply_damage ─────────────────────────────────────────────────────────────

/// Internal damage logic without death explosion processing.
/// Used by apply_death_explosion to avoid double-triggering.
/// Shared Psion-aura / boss cleanup invoked when an enemy dies. Called
/// from ``apply_damage`` (weapon/bump kills) and ``apply_env_danger``
/// (lethal environment kills that bypass the core damage path — e.g.
/// Air Strike, Cataclysm, Tidal Wave, Seismic→chasm). Without this in
/// the env-kill path, a Soldier/Shell/Blood/Tyrant Psion killed by
/// environment retains its aura indefinitely: all surviving Vek keep
/// +1 HP / Armor / regen / boosted damage that should have cleared.
///
/// Caller invariant: the unit at ``idx`` has just had its HP set to 0.
///
/// NOTE: this helper does NOT dispatch the Boss/Blast Psion EXPLODE
/// explosion. Explosion dispatch is currently caller-side at
/// `apply_damage`:788 (weapon kills), `apply_push`:1137 + 1164
/// (push-into-deadly-terrain, mine), and `apply_env_danger` (lethal env
/// kills, since sim v38). See v39 follow-up to centralize so other latent
/// paths (ice-drown, dam-flood) get covered too.
pub(crate) fn on_enemy_death(
    board: &mut Board,
    idx: usize,
    result: &mut ActionResult,
) {
    // Capture the dying unit's tile + type before any flag teardown — the
    // AE Fire/Spider Psion on-death effects mutate the board AT this tile.
    let dying_tname_owned: String = board.units[idx].type_name_str().to_string();
    let dx = board.units[idx].x;
    let dy = board.units[idx].y;

    if let Some((child_type, child_hp, child_weapon)) =
        blob_boss_death_spawn(&dying_tname_owned)
    {
        spawn_blob_boss_children(board, dx, dy, board.units[idx].uid, &dying_tname_owned,
                                child_type, child_hp, child_weapon, result);
    }

    // ── Fire Psion (AE LEADER_FIRE) on-death fire ─────────────────────────
    // While Fire Psion is alive, every Vek that dies leaves Fire on its tile.
    // Excludes the Psion itself and the Boost/Spider/other AE psions per the
    // standard "aura source is exempt" pattern. Fire is suppressed if the
    // tile's terrain can't host fire (water/chasm/lava/ice — water becomes
    // ACID-pool only via the dedicated path; chasm/lava ignore fire status).
    // Mountains don't host fire either (the destroyed-mountain Rubble case
    // can host fire, but live mountains are skipped to match the Lua rule
    // SetFire only applies to ground-class tiles).
    if board.fire_psion && board.units[idx].receives_psion_aura() && dying_tname_owned != "Jelly_Fire1" {
        // Tile filter: fire is meaningless on water/chasm/lava and on intact
        // mountain. The set_on_fire flag is harmless on those tiles but we
        // skip for hygiene + parity with apply_weapon_status's behavior.
        let t = board.tile(dx, dy);
        let fire_ok = matches!(
            t.terrain,
            Terrain::Ground | Terrain::Sand | Terrain::Forest | Terrain::Rubble
                | Terrain::Ice | Terrain::Fire
        );
        if fire_ok {
            board.tile_mut(dx, dy).set_smoke(false); // fire replaces smoke
            board.tile_mut(dx, dy).set_on_fire(true);
        }
    }

    // ── Spider Psion (AE LEADER_SPIDER) on-death egg ──────────────────────
    // While Spider Psion is alive, every Vek that dies leaves a Spiderling
    // Egg (SpiderlingEgg1) on its tile. The egg-hatch logic (per
    // `project_egg_spawn_sim`) turns it into a Spiderling at the NEXT enemy
    // phase. Excludes the Psion itself.
    //
    // sim v38: we DEFER the actual `spawn_enemy` call to a board-level
    // queue (`pending_spider_eggs`) drained at the END of
    // `simulate_enemy_attacks`. Pre-v38 we spawned the egg immediately,
    // which caused this same-phase hatch chain when the Vek died during
    // the enemy phase (env_danger / fire-tick / chain-reaction kill):
    //   1. on_enemy_death → spawn_enemy → WebbEgg1 placed on board
    //   2. enemy.rs:513 hatch loop runs (still in same enemy phase)
    //   3. egg → Spiderling1 immediately
    // Per game's Lua at weapons_enemy.lua:857, WebbEgg1 hatches via
    // `AddQueuedDamage` — the egg DOES NOT hatch in the same enemy phase
    // as the spawn. Deferring the spawn until after the hatch loop fixes
    // this. (When the trigger is a player-phase weapon kill, hatching is
    // a non-issue — the egg sits there until the next enemy phase.)
    if board.spider_psion && board.units[idx].receives_psion_aura() && dying_tname_owned != "Jelly_Spider1" {
        board.pending_spider_eggs.push((dx, dy));
    }

    // Shell Psion killed: remove armor aura from all Vek
    if board.armor_psion && board.units[idx].type_name_str() == "Jelly_Armor1" {
        let other_alive = (0..board.unit_count as usize)
            .any(|j| j != idx
                && board.units[j].type_name_str() == "Jelly_Armor1"
                && board.units[j].hp > 0);
        if !other_alive {
            board.armor_psion = false;
            for j in 0..board.unit_count as usize {
                if board.units[j].is_enemy() {
                    board.units[j].flags.set(UnitFlags::ARMOR, false);
                }
            }
        }
    }

    // Soldier Psion killed: remove +1 HP from all Vek — but only if the Boss
    // Psion (which also grants the HEALTH buff) isn't keeping the buff alive.
    if board.soldier_psion && board.units[idx].type_name_str() == "Jelly_Health1" {
        board.soldier_psion = false;
        if !board.boss_psion {
            for j in 0..board.unit_count as usize {
                let tname = board.units[j].type_name_str();
                if board.units[j].receives_psion_aura() && board.units[j].hp > 0
                    && tname != "Jelly_Health1"
                    && tname != "Jelly_Boss"
                {
                    board.units[j].max_hp -= 1;
                    board.units[j].hp -= 1;
                    if board.units[j].hp <= 0 {
                        result.record_enemy_kill(!board.units[j].minor());
                    }
                }
            }
        }
    }

    // Psion Abomination (Jelly_Boss) killed: tear down the LEADER_BOSS combined
    // aura. REGEN + EXPLODE just clear via the flag flip; HEALTH (the +1 HP buff)
    // reverses ONLY if the Soldier Psion isn't also keeping it alive.
    if board.boss_psion && board.units[idx].type_name_str() == "Jelly_Boss" {
        board.boss_psion = false;
        if !board.soldier_psion {
            for j in 0..board.unit_count as usize {
                let tname = board.units[j].type_name_str();
                if board.units[j].receives_psion_aura() && board.units[j].hp > 0
                    && tname != "Jelly_Health1"
                    && tname != "Jelly_Boss"
                {
                    board.units[j].max_hp -= 1;
                    board.units[j].hp -= 1;
                    if board.units[j].hp <= 0 {
                        result.record_enemy_kill(!board.units[j].minor());
                    }
                }
            }
        }
    }

    // Blood Psion killed: stop regen
    if board.regen_psion && board.units[idx].type_name_str() == "Jelly_Regen1" {
        board.regen_psion = false;
    }

    // Psion Tyrant killed: stop mech damage
    if board.tyrant_psion && board.units[idx].type_name_str() == "Jelly_Lava1" {
        board.tyrant_psion = false;
    }

    // Boost Psion (AE) killed: stop +1 weapon damage to Vek attacks and clear
    // the visible Boosted status the engine removes from all surviving Vek.
    if board.boost_psion && board.units[idx].type_name_str() == "Jelly_Boost1" {
        let other_alive = (0..board.unit_count as usize)
            .any(|j| j != idx
                && board.units[j].type_name_str() == "Jelly_Boost1"
                && board.units[j].hp > 0);
        if !other_alive {
            board.boost_psion = false;
            for j in 0..board.unit_count as usize {
                if board.units[j].is_enemy() {
                    board.units[j].set_boosted(false);
                }
            }
        }
    }

    // Fire Psion (AE) killed: stop fire-immunity + on-death-fire
    if board.fire_psion && board.units[idx].type_name_str() == "Jelly_Fire1" {
        board.fire_psion = false;
    }

    // Spider Psion (AE) killed: stop on-death-egg-spawn
    if board.spider_psion && board.units[idx].type_name_str() == "Jelly_Spider1" {
        board.spider_psion = false;
    }

    // Boss killed: clear flag for kill bonus in evaluate
    if board.boss_alive && board.units[idx].type_name_str().contains("Boss") {
        board.boss_alive = false;
    }
}

fn blob_boss_death_spawn(name: &str) -> Option<(&'static str, i8, WId)> {
    match name {
        "BlobBoss" => Some(("BlobBossMed", 2, WId::BlobBossAtkMed)),
        "BlobBossMed" => Some(("BlobBossSmall", 1, WId::BlobBossAtkSmall)),
        _ => None,
    }
}

fn spawn_blob_boss_children(
    board: &mut Board,
    death_x: u8,
    death_y: u8,
    parent_uid: u16,
    parent_type: &str,
    child_type: &str,
    child_hp: i8,
    child_weapon: WId,
    result: &mut ActionResult,
) {
    let mut spawned = 0u8;
    let mut primary = blob_boss_split_candidates(board, death_x, death_y, 1, 2);
    let mut backup = blob_boss_split_candidates(board, death_x, death_y, 3, 4);

    while spawned < 2 {
        let loc = if !primary.is_empty() {
            Some(primary.remove(0))
        } else if !backup.is_empty() {
            Some(backup.remove(0))
        } else {
            None
        };
        let Some((sx, sy)) = loc else { break; };
        if !spawn_blob_boss_child(board, sx, sy, child_type, child_hp, child_weapon) {
            continue;
        }
        spawned += 1;
        result.events.push(format!(
            "blob_split:{}:{}:{}:{}->{}:{}:{}",
            parent_uid, parent_type, death_x, death_y, child_type, sx, sy
        ));
        // The first child now occupies its tile, so the second child must not
        // reuse that candidate if it was also present in the backup list.
        primary.retain(|&p| p != (sx, sy));
        backup.retain(|&p| p != (sx, sy));
    }
}

fn blob_boss_split_candidates(
    board: &Board,
    cx: u8,
    cy: u8,
    min_dist: u8,
    max_dist: u8,
) -> Vec<(u8, u8)> {
    let mut out = Vec::new();
    let size = 4i8;
    let corner_x = cx as i8 - size;
    let corner_y = cy as i8 - size;
    // Lua general_DiamondTarget scans the surrounding square row-major from
    // center - (size,size), then filters to the Manhattan diamond. The real
    // Goo split uses random_removal from this list; the simulator takes the
    // first valid deterministic representatives so searches are reproducible.
    for y in corner_y..=(corner_y + size * 2) {
        for x in corner_x..=(corner_x + size * 2) {
            if !in_bounds(x, y) {
                continue;
            }
            let ux = x as u8;
            let uy = y as u8;
            if (ux, uy) == (cx, cy) {
                continue;
            }
            let dist = (x - cx as i8).unsigned_abs() + (y - cy as i8).unsigned_abs();
            if dist < min_dist || dist > max_dist {
                continue;
            }
            if board.is_blocked(ux, uy, false) {
                continue;
            }
            out.push((ux, uy));
        }
    }
    out
}

fn spawn_blob_boss_child(
    board: &mut Board,
    x: u8,
    y: u8,
    child_type: &str,
    base_hp: i8,
    child_weapon: WId,
) -> bool {
    if board.unit_count as usize >= board.units.len() {
        return false;
    }
    if board.unit_at(x, y).is_some() || board.wreck_at(x, y) {
        return false;
    }
    if board.is_blocked(x, y, false) {
        return false;
    }

    let mut hp = base_hp;
    let mut max_hp = base_hp;
    if board.soldier_psion || board.boss_psion {
        hp += 1;
        max_hp += 1;
    }

    let mut new_uid: u16 = 1;
    for i in 0..board.unit_count as usize {
        new_uid = new_uid.max(board.units[i].uid.saturating_add(1));
    }

    let mut flags = UnitFlags::PUSHABLE | UnitFlags::MASSIVE;
    if board.armor_psion {
        flags.insert(UnitFlags::ARMOR);
    }

    let mut unit = Unit {
        uid: new_uid,
        x,
        y,
        hp,
        max_hp,
        team: Team::Enemy,
        move_speed: 3,
        base_move: 3,
        flags,
        weapon: WeaponId(child_weapon as u16),
        queued_target_x: -1,
        queued_target_y: -1,
        ..Unit::default()
    };
    unit.set_type_name(child_type);
    board.add_unit(unit);
    true
}

fn next_spawn_uid(board: &Board) -> u16 {
    let mut new_uid: u16 = 1;
    for i in 0..board.unit_count as usize {
        new_uid = new_uid.max(board.units[i].uid.saturating_add(1));
    }
    new_uid
}

fn acid_storm_active(board: &Board) -> bool {
    board.mission_id == "Mission_AcidStorm"
        && board.units[..board.unit_count as usize]
            .iter()
            .any(|u| u.hp > 0 && u.type_name_str() == "Storm_Generator")
}

fn spawn_rock_thrown(board: &mut Board, x: u8, y: u8) -> bool {
    if board.unit_count as usize >= board.units.len() {
        return false;
    }
    if board.is_blocked(x, y, false) {
        return false;
    }

    let mut unit = Unit {
        uid: next_spawn_uid(board),
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
        ..Unit::default()
    };
    unit.set_type_name("RockThrown");
    if acid_storm_active(board) {
        unit.set_acid(true);
    }
    board.add_unit(unit);
    true
}

fn spawn_arachnoid(
    board: &mut Board,
    x: u8,
    y: u8,
    acid_attack: bool,
    result: &mut ActionResult,
) -> bool {
    if board.unit_count as usize >= board.units.len() {
        return false;
    }
    if board.unit_at(x, y).is_some() {
        return false;
    }

    let terrain = board.tile(x, y).terrain;
    if matches!(terrain, Terrain::Mountain | Terrain::Building)
        || terrain.is_deadly_ground()
    {
        return false;
    }

    let weapon = if acid_attack {
        WId::DeployUnitAracnoidAtkB
    } else {
        WId::DeployUnitAracnoidAtk
    };
    let mut unit = Unit {
        uid: next_spawn_uid(board),
        x,
        y,
        hp: 1,
        max_hp: 1,
        team: Team::Player,
        move_speed: 3,
        base_move: 3,
        flags: UnitFlags::ACTIVE | UnitFlags::PUSHABLE,
        weapon: WeaponId(weapon as u16),
        queued_target_x: -1,
        queued_target_y: -1,
        ..Unit::default()
    };
    unit.set_type_name(if acid_attack {
        "DeployUnit_AracnoidB"
    } else {
        "DeployUnit_Aracnoid"
    });
    let idx = board.add_unit(unit);
    apply_landing_effects(board, idx, result);
    true
}

/// Materialize Spider Psion death eggs queued by `on_enemy_death`.
///
/// Player-phase kills need the egg on-board immediately for replay snapshots
/// and partial re-solves. Enemy-phase kills call this only after the hatch
/// loop, so newly-created eggs still wait until the next enemy phase.
pub(crate) fn drain_pending_spider_eggs(board: &mut Board) {
    let pending = std::mem::take(&mut board.pending_spider_eggs);
    for (x, y) in pending {
        crate::enemy::spawn_enemy(board, x, y, "SpiderlingEgg1", 1);
    }
}

fn retarget_pending_spider_egg(board: &mut Board, from_x: u8, from_y: u8, to_x: u8, to_y: u8) {
    if (from_x, from_y) == (to_x, to_y) {
        return;
    }
    for egg in board.pending_spider_eggs.iter_mut().rev() {
        if *egg == (from_x, from_y) {
            *egg = (to_x, to_y);
            break;
        }
    }
}

/// Finish a non-damage instant death path after the caller has determined the
/// unit dies at its current tile: drowning/falling from a push, swap, throw, or
/// Old Earth Mine. This mirrors apply_damage_core's bookkeeping plus the
/// caller-side Blast Psion / Volatile Vek explosions that instant-kill paths
/// must dispatch themselves.
fn finish_instant_unit_death(
    board: &mut Board,
    unit_idx: usize,
    result: &mut ActionResult,
    death_x: u8,
    death_y: u8,
) {
    if board.units[unit_idx].hp <= 0 {
        return;
    }

    let is_enemy = board.units[unit_idx].is_enemy();
    let is_player = board.units[unit_idx].is_player();
    let mission_counted = is_enemy && !board.units[unit_idx].minor();
    let has_acid = board.units[unit_idx].acid();
    let dying_uid = board.units[unit_idx].uid;
    let is_volatile = is_enemy && board.units[unit_idx].is_volatile_vek();
    let dying_tname = board.units[unit_idx].type_name_str().to_string();
    let can_explode = is_enemy
        && (board.blast_psion || board.boss_psion)
        && board.units[unit_idx].receives_psion_aura()
        && dying_tname != "Jelly_Explode1"
        && dying_tname != "Jelly_Boss";
    let death_terrain = board.tile(death_x, death_y).terrain;

    board.units[unit_idx].hp = 0;

    if is_enemy {
        result.record_enemy_kill(mission_counted);
        on_enemy_death(board, unit_idx, result);
        break_web_from(board, dying_uid);
        if is_volatile {
            apply_volatile_decay(board, death_x, death_y, result, 0);
        }
        if can_explode {
            apply_death_explosion(board, death_x, death_y, result, 0);
        }
    } else if is_player {
        result.mechs_killed += 1;
    }

    // ACID units leave an acid pool/tile on normal ground and water. Lava/chasm
    // consume it, matching the existing apply_damage_core behavior.
    if has_acid && (!death_terrain.is_deadly_ground() || death_terrain == Terrain::Water) {
        leave_acid_pool_on_death(board, death_x, death_y);
    }
}

/// Apply normal damage but defer Blast Psion explosion dispatch until the
/// caller has resolved a simultaneous push. Used for single SpaceDamage-style
/// damage+push hits where live game death effects occur from the final corpse
/// tile rather than the pre-push damage tile.
fn apply_damage_defer_death_explosion(
    board: &mut Board,
    x: u8,
    y: u8,
    damage: u8,
    result: &mut ActionResult,
    source: DamageSource,
) -> Option<usize> {
    if damage == 0 { return None; }

    let death_check = if board.blast_psion || board.boss_psion {
        board.unit_at(x, y).and_then(|idx| {
            let u = &board.units[idx];
            let tname = u.type_name_str();
            if u.receives_psion_aura() && u.hp > 0
                && tname != "Jelly_Explode1"
                && tname != "Jelly_Boss"
            {
                Some(idx)
            } else { None }
        })
    } else { None };

    let volatile_check = board.unit_at(x, y).and_then(|idx| {
        let u = &board.units[idx];
        if u.is_enemy() && u.hp > 0 && u.is_volatile_vek() {
            Some(idx)
        } else { None }
    });

    // BombRock explosions are not a corpse-position death aura: live
    // Unstable Boulders detonate from the tile that took damage, before
    // a push weapon can shove the dead boulder onward.
    let bombrock_check = board.unit_at(x, y).and_then(|idx| {
        let u = &board.units[idx];
        if u.hp > 0 && u.type_name_str() == "BombRock" {
            Some(idx)
        } else { None }
    });

    apply_damage_core(board, x, y, damage, result, source);

    if let Some(idx) = bombrock_check {
        if board.units[idx].hp <= 0 {
            apply_bombrock_explosion(board, x, y, result, None, 0);
        }
    }

    if let Some(idx) = volatile_check {
        if board.units[idx].hp <= 0 {
            apply_volatile_decay(board, x, y, result, 0);
        }
    }

    death_check.filter(|idx| board.units[*idx].hp <= 0)
}

/// Grid-power accounting for building HP changes.
///
/// Non-unique multi-HP buildings have a live-engine wrinkle: a bump can reduce
/// HP without moving the visible grid scalar. Store that latent debt on the
/// board so immediate action verification can pass; the debt is charged when
/// the enemy turn starts, or earlier if the same building is destroyed.
pub(crate) fn settle_building_grid_loss(
    board: &mut Board,
    idx: usize,
    hp_lost: u8,
    destroyed: bool,
    is_unique: bool,
    source: DamageSource,
) -> u8 {
    if hp_lost == 0 {
        return 0;
    }

    if matches!(source, DamageSource::Bump | DamageSource::WeaponDeferredGrid)
        && !is_unique
        && !destroyed
    {
        board.deferred_bump_grid_debt[idx] =
            board.deferred_bump_grid_debt[idx].saturating_add(hp_lost);
        return 0;
    }

    let mut grid_loss = hp_lost;
    if destroyed {
        grid_loss = grid_loss.saturating_add(board.deferred_bump_grid_debt[idx]);
        board.deferred_bump_grid_debt[idx] = 0;
    }
    grid_loss
}

/// Charge all pending non-unique multi-HP bump debt at enemy-turn boundaries.
///
/// Live captures show the building HP loss appears immediately, while the grid
/// meter can lag until the turn rolls. Player-phase bump debt flushes at
/// enemy-turn start; enemy-phase bump debt flushes again before the next player
/// turn so post-enemy projection includes the settled grid loss.
pub(crate) fn flush_deferred_bump_grid_debt(
    board: &mut Board,
    result: &mut ActionResult,
) -> u8 {
    let mut total = 0u8;
    for debt in board.deferred_bump_grid_debt.iter_mut() {
        if *debt == 0 {
            continue;
        }
        total = total.saturating_add(*debt);
        *debt = 0;
    }

    if total > 0 {
        result.grid_damage += total as i32;
        board.grid_power = board.grid_power.saturating_sub(total);
    }
    total
}

pub(crate) fn thaw_frozen_building(
    board: &mut Board,
    x: u8,
    y: u8,
    result: &mut ActionResult,
) -> bool {
    let tile = board.tile_mut(x, y);
    if tile.terrain == Terrain::Building && tile.building_hp > 0 && tile.frozen() {
        tile.set_frozen(false);
        result.events.push(format!("building_thawed:{}:{}", x, y));
        return true;
    }
    false
}


fn apply_damage_core(board: &mut Board, x: u8, y: u8, damage: u8, result: &mut ActionResult, source: DamageSource) {
    if damage == 0 { return; }

    let occupied_by_alive_unit_at_start = board.unit_at(x, y).is_some();

    // Damage unit if present
    if let Some(idx) = board.unit_at(x, y) {
        let unit = &mut board.units[idx];

        if unit.shield() {
            // Shield absorbs any damage, consumed
            unit.set_shield(false);
        } else if unit.frozen() {
            // Frozen = invincible, damage unfreezes (0 actual damage)
            unit.set_frozen(false);
            clear_mites(unit);
        } else {
            let actual = match source {
                DamageSource::Bump => {
                    // Force Amp (Passive_ForceAmp): Vek take +1 from bump-class
                    // damage (push collisions AND blocking emerging Vek). The
                    // Bot Leader is a sentient enemy and is explicitly exempt
                    // per the wiki — gate on type name.
                    let tname = unit.type_name_str();
                    let is_sentient = tname == "BotBoss" || tname == "BotBoss2";
                    if board.force_amp && unit.is_enemy() && !is_sentient {
                        (damage + 1) as i8
                    } else {
                        damage as i8
                    }
                }
                DamageSource::Fire => damage as i8,
                _ => {
                    if unit.acid() {
                        (damage * 2) as i8
                    } else if unit.armor() {
                        (damage as i8 - 1).max(0)
                    } else {
                        damage as i8
                    }
                }
            };

            unit.hp -= actual;
            if actual > 0 {
                clear_mites(unit);
            }

            if unit.is_enemy() {
                result.enemy_damage_dealt += actual as i32;
                if unit.hp <= 0 {
                    result.record_enemy_kill_with_leech_credit(
                        !unit.minor(),
                        matches!(
                            source,
                            DamageSource::Weapon
                                | DamageSource::WeaponCracksOccupied
                                | DamageSource::WeaponNoAcidPool
                        ),
                    );
                    on_enemy_death(board, idx, result);
                }
            } else if unit.is_player() {
                result.mech_damage_taken += actual as i32;
                if unit.hp <= 0 {
                    result.mechs_killed += 1;
                }
            }
        }
    }

    // Acid pool creation: unit with acid dies → acid pool on tile
    if source != DamageSource::WeaponNoAcidPool {
        if let Some(idx) = board.unit_at(x, y) {
            let unit = &board.units[idx];
            if unit.hp <= 0 && unit.acid() {
                let tile = board.tile(x, y);
                if !tile.terrain.is_deadly_ground() || tile.terrain == Terrain::Water {
                    leave_acid_pool_on_death(board, x, y);
                }
            }
        }
    }

    if source != DamageSource::WeaponUnitOnly && source != DamageSource::ChainWhip {
        // Time Pods are fragile map objects: direct tile damage destroys them
        // unless they were already collected by a player mech landing.
        if damage > 0 && board.tile(x, y).has_pod() {
            board.tile_mut(x, y).set_has_pod(false);
            result.events.push(format!("pod_destroyed_by_damage:{}:{}", x, y));
        }

        // Damage building if present — incremental HP damage. Direct weapon and
        // explosion damage drains current grid per building HP lost. Push/bump
        // collision damage has its own non-unique multi-HP exception below.
        let mut bldg_hp_lost: u8 = 0;
        let mut bldg_destroyed = false;
        let mut bldg_is_unique = false;
        let mut bldg_idx = 0usize;
        {
            let idx = xy_to_idx(x, y);
            let is_unique = (board.unique_buildings & (1u64 << idx)) != 0;
            let tile = board.tile_mut(x, y);
            if tile.terrain == Terrain::Building && tile.building_hp > 0 {
                if tile.shield() {
                    tile.set_shield(false);
                } else if tile.frozen() {
                    tile.set_frozen(false);
                    result.events.push(format!("building_thawed:{}:{}", x, y));
                } else {
                    let hp_lost = damage.min(tile.building_hp);
                    tile.building_hp = tile.building_hp.saturating_sub(hp_lost);
                    if tile.building_hp == 0 {
                        tile.set_shield(false);
                        if !is_unique {
                            tile.terrain = Terrain::Rubble;
                        }
                    }
                    bldg_hp_lost = hp_lost;
                    result.buildings_damaged += hp_lost as i32;
                    result.grid_damage += hp_lost as i32;
                    if tile.building_hp == 0 {
                        result.buildings_lost += 1;
                    }
                    bldg_idx = idx;
                    bldg_is_unique = is_unique;
                    bldg_destroyed = tile.building_hp == 0;
                }
            }
        }
        if bldg_hp_lost > 0 {
            let grid_loss = settle_building_grid_loss(
                board,
                bldg_idx,
                bldg_hp_lost,
                bldg_destroyed,
                bldg_is_unique,
                source,
            );
            result.grid_damage += (grid_loss as i32) - (bldg_hp_lost as i32);
            board.grid_power = board.grid_power.saturating_sub(grid_loss);
        }

        // Damage mountain — HP 2 → 1 → 0 (Rubble). Does not affect grid_power.
        {
            let tile = board.tile_mut(x, y);
            if tile.terrain == Terrain::Mountain && tile.building_hp > 0 {
                tile.building_hp = tile.building_hp.saturating_sub(1);
                if tile.building_hp == 0 {
                    tile.terrain = Terrain::Rubble;
                }
            }
        }

        // Ice: intact → cracked → water
        let tile = board.tile_mut(x, y);
        if tile.terrain == Terrain::Ice {
            if tile.cracked() || source == DamageSource::Fire {
                tile.terrain = Terrain::Water;
                tile.set_cracked(false);
                // Non-flying unit drowns. effectively_flying() = flying && !frozen,
                // so a frozen flying unit loses its flight and drowns here.
                // Massive units survive drowning (drown-immunity applies to Water).
                if let Some(idx) = board.unit_at(x, y) {
                    let unit = &mut board.units[idx];
                    if unit.hp > 0 && !unit.effectively_flying() && !unit.massive() {
                        unit.hp = 0;
                        if unit.is_enemy() {
                            result.record_enemy_kill(!unit.minor());
                        }
                    }
                }
            } else {
                tile.set_cracked(true);
            }
        }

        // Cracked ground collapses only when the tile itself is damaged.
        // Live Mission_Bomb captures show a pawn standing on cracked ground
        // absorbs ordinary weapon SpaceDamage: the pawn can die while the
        // tile remains cracked Ground for the next hit. Self-damage still
        // damages the mech's tile, so Hydraulic Legs can open a chasm under
        // its landing mech.
        let tile = board.tile_mut(x, y);
        let occupied_tile_absorbs_crack_hit =
            occupied_by_alive_unit_at_start
            && matches!(
                source,
                DamageSource::Weapon | DamageSource::Bump | DamageSource::WeaponNoAcidPool
            );
        if tile.terrain == Terrain::Ground
            && tile.cracked()
            && !occupied_tile_absorbs_crack_hit {
            tile.terrain = Terrain::Chasm;
            tile.set_cracked(false);
            if let Some(idx) = board.unit_at(x, y) {
                let unit = &mut board.units[idx];
                    if unit.hp > 0 && !unit.effectively_flying() {
                        unit.hp = 0;
                        if unit.is_enemy() {
                            result.record_enemy_kill(!unit.minor());
                        } else if unit.is_player() {
                            result.mechs_killed += 1;
                        }
                    }
                }
        }

        // Forest: weapon damage ignites (NOT bump/push damage)
        let tile = board.tile_mut(x, y);
        if tile.terrain == Terrain::Forest && source != DamageSource::Bump {
            tile.terrain = Terrain::Ground;
            tile.set_on_fire(true);
            // Live consumes the forest immediately: the tile becomes burning Ground.
            // Unit does NOT immediately catch fire — happens at end-of-turn.
        }

        // Sand: weapon/self damage -> smoke (fire weapon -> fire tile instead)
        let tile = board.tile_mut(x, y);
        if tile.terrain == Terrain::Sand
            && matches!(
                source,
                DamageSource::Weapon
                    | DamageSource::SelfDamage
                    | DamageSource::WeaponCracksOccupied
                    | DamageSource::WeaponNoAcidPool
            ) {
            tile.terrain = Terrain::Ground;
            // Note: fire_weapon flag not yet threaded; default to smoke.
            // Correct fire-on-sand requires knowing if weapon has FIRE flag.
            tile.set_smoke(true);
        }
    }

    // Chain Whip is not generic tile damage: it leaves Ice/Sand/Pods/etc.
    // alone, but live captures show it ignites Forest under a zapped pawn.
    if source == DamageSource::ChainWhip {
        let ignited = {
            let tile = board.tile_mut(x, y);
            if tile.terrain == Terrain::Forest {
                tile.terrain = Terrain::Ground;
                tile.set_on_fire(true);
                true
            } else {
                false
            }
        };
        if ignited {
            if let Some(idx) = board.unit_at(x, y) {
                if board.units[idx].hp > 0 {
                    board.units[idx].set_fire(true);
                }
            }
        }
    }

    // ACID pool creation: unit with ACID dies → acid pool on tile
    if source != DamageSource::WeaponNoAcidPool {
        if let Some(idx) = board.any_unit_at(x, y) {
            let unit = &board.units[idx];
            if unit.hp <= 0 && unit.acid() {
                leave_acid_pool_on_death(board, x, y);
            }
        }
    }

    // Multi-tile HP sync: mirror final HP to all entries sharing this uid.
    // Runs AFTER the body so kill-credit / Psion cleanup / explosion pre-check
    // don't re-fire on the twin. Currently only Dam_Pawn uses ExtraSpaces, and
    // Dam_Pawn is Team::Neutral so none of the enemy-gated side-effects would
    // fire anyway — but keep this generic so future multi-tile pawns are safe.
    if let Some(idx) = board.any_unit_at(x, y) {
        let uid = board.units[idx].uid;
        let hp = board.units[idx].hp;
        if uid != 0 {
            for j in 0..board.unit_count as usize {
                if j != idx && board.units[j].uid == uid {
                    board.units[j].hp = hp;
                }
            }
        }
    }

    // Old Earth Dam flood: if this damage killed the last dam tile, flood
    // the 2×7 strip behind the dam (drowns non-flying non-massive Vek).
    // uid-independent detection — works regardless of which tile took the
    // fatal hit. Idempotent via dam_alive gate.
    if board.dam_alive {
        let dam_dead = (0..board.unit_count as usize).all(|i| {
            let u = &board.units[i];
            u.type_name_str() != "Dam_Pawn" || u.hp <= 0
        });
        if dam_dead {
            trigger_dam_flood(board, result);
            board.dam_alive = false;
        }
    }

    // Renfield Bomb destruction: flip bigbomb_alive once the last BigBomb
    // pawn drops to hp <= 0. The evaluator's PsionState.bigbomb captures
    // the pre-action state and scores the alive→dead transition with
    // `bigbomb_killed`. No flood/AOE side effect — the bomb's mission-end
    // detonation is out of the 1-turn solver horizon (and irrelevant once
    // it's dead). Idempotent via the bigbomb_alive gate.
    if board.bigbomb_alive {
        let bomb_dead = (0..board.unit_count as usize).all(|i| {
            let u = &board.units[i];
            u.type_name_str() != "BigBomb" || u.hp <= 0
        });
        if bomb_dead {
            board.bigbomb_alive = false;
        }
    }

    // Web break: enemy webber killed → unweb any mechs they were holding.
    if let Some(idx) = board.any_unit_at(x, y) {
        let u = &board.units[idx];
        if u.hp <= 0 && u.is_enemy() {
            let dead_uid = u.uid;
            break_web_from(board, dead_uid);
        }
    }

    refresh_all_arrogant_boosts(board);
}

/// Convert a single tile to Water, drowning any non-flying non-massive unit
/// standing on it. Idempotent: running on existing Water is a no-op.
/// Mountains / Buildings are not flooded (game engine refuses to overwrite).
pub fn flood_tile(board: &mut Board, x: u8, y: u8, result: &mut ActionResult) {
    if x >= 8 || y >= 8 { return; }
    let t = board.tile(x, y);
    if t.terrain == Terrain::Water {
        board.tile_mut(x, y).set_on_fire(false);
        return;
    }
    if matches!(t.terrain, Terrain::Mountain | Terrain::Building) { return; }

    let tile = board.tile_mut(x, y);
    tile.terrain = Terrain::Water;
    tile.set_cracked(false);
    tile.set_on_fire(false);

    if let Some(idx) = board.unit_at(x, y) {
        let drowns = {
            let u = &board.units[idx];
            u.hp > 0 && !u.effectively_flying() && !u.massive()
        };
        if drowns {
            finish_instant_unit_death(board, idx, result, x, y);
        }
    }
}

/// Trigger the Dam_Pawn death flood. Fires exactly once when the dam
/// transitions from alive → dead. Flood pattern from mission_dam.lua:
/// `for y = 1,7 do for x = 0,1 do SpaceDamage(DamPos + Point(x,y)) end end`.
fn trigger_dam_flood(board: &mut Board, result: &mut ActionResult) {
    let (px, py) = match board.dam_primary {
        Some(p) => p,
        None => return,
    };
    for y_off in 1i8..=7 {
        for x_off in 0i8..=1 {
            let tx = px as i8 + x_off;
            let ty = py as i8 + y_off;
            if tx >= 0 && tx < 8 && ty >= 0 && ty < 8 {
                flood_tile(board, tx as u8, ty as u8, result);
            }
        }
    }
}

/// Apply damage to whatever is at (x, y), including Blast Psion death
/// explosions and Volatile Vek decay.
/// Source: Bump/Fire bypass armor and acid. Normal/Self respects them.
/// WeaponUnitOnly mirrors weapon damage against occupants while leaving
/// buildings/terrain unchanged. ChainWhip is unit-only except for igniting
/// Forest under a hit pawn.
pub fn apply_damage(board: &mut Board, x: u8, y: u8, damage: u8, result: &mut ActionResult, source: DamageSource) {
    apply_damage_inner(board, x, y, damage, result, source, None, 0);
}

pub fn apply_damage_with_bombrock_exclusion(
    board: &mut Board,
    x: u8,
    y: u8,
    damage: u8,
    result: &mut ActionResult,
    source: DamageSource,
    exclude: Option<(u8, u8)>,
) {
    apply_damage_inner(board, x, y, damage, result, source, exclude, 0);
}

fn apply_viscera_nanobots_heal(
    board: &mut Board,
    attacker_idx: usize,
    kills: i32,
    result: &mut ActionResult,
) {
    if board.viscera_nanobots_heal == 0 || kills <= 0 {
        return;
    }
    let attacker = &board.units[attacker_idx];
    if !attacker.is_player() || !attacker.is_mech() {
        return;
    }

    let heal = (board.viscera_nanobots_heal as i32 * kills).min(i8::MAX as i32) as i8;
    if heal <= 0 {
        return;
    }
    let was_disabled = board.units[attacker_idx].hp <= 0;
    if was_disabled && disabled_unit_is_on_deadly_terrain(board, attacker_idx) {
        result.events.push(format!(
            "viscera_nanobots_blocked_by_terrain:{}:{}",
            board.units[attacker_idx].uid, kills
        ));
        return;
    }
    let old_hp = board.units[attacker_idx].hp;
    let max_hp = board.units[attacker_idx].max_hp;
    let new_hp = (old_hp + heal).min(max_hp);
    let actual_heal = new_hp - old_hp;
    if actual_heal <= 0 {
        return;
    }

    board.units[attacker_idx].hp = new_hp;
    if was_disabled && new_hp > 0 {
        clear_unit_web(board, attacker_idx);
        let attacker = &mut board.units[attacker_idx];
        attacker.set_fire(false);
        attacker.set_acid(false);
        attacker.set_frozen(false);
        clear_mites(attacker);
        if result.mechs_killed > 0 {
            result.mechs_killed -= 1;
        }
    }
    result.events.push(format!(
        "viscera_nanobots_heal:{}:{}:{}",
        board.units[attacker_idx].uid, kills, actual_heal
    ));
}

fn disabled_unit_is_on_deadly_terrain(board: &Board, unit_idx: usize) -> bool {
    let unit = &board.units[unit_idx];
    if unit.hp > 0 || unit.effectively_flying() {
        return false;
    }
    match board.tile(unit.x, unit.y).terrain {
        Terrain::Chasm => true,
        Terrain::Water | Terrain::Lava => !unit.massive(),
        _ => false,
    }
}

fn apply_damage_inner(
    board: &mut Board,
    x: u8,
    y: u8,
    damage: u8,
    result: &mut ActionResult,
    source: DamageSource,
    bombrock_exclude: Option<(u8, u8)>,
    bombrock_depth: u8,
) {
    if damage == 0 { return; }

    // Pre-check: track alive non-Psion enemy for Blast Psion / Psion Abomination
    // death explosion. Both auras share the same EXPLODE-on-death effect.
    let death_check = if board.blast_psion || board.boss_psion {
        board.unit_at(x, y).and_then(|idx| {
            let u = &board.units[idx];
            let tname = u.type_name_str();
            if u.receives_psion_aura() && u.hp > 0
                && tname != "Jelly_Explode1"
                && tname != "Jelly_Boss"
            {
                Some(idx)
            } else { None }
        })
    } else { None };

    // Pre-check: track Volatile Vek for Explosive Decay (unit-intrinsic, no aura dep).
    let volatile_check = board.unit_at(x, y).and_then(|idx| {
        let u = &board.units[idx];
        if u.is_enemy() && u.hp > 0 && u.is_volatile_vek() {
            Some(idx)
        } else { None }
    });

    // Tumblebug BombRock / Unstable Boulder is a neutral 1 HP pawn with the
    // engine's Explodes flag: destroying it deals 1 bump-class damage to
    // cardinal-adjacent tiles. Tumblebugs exclude their own source tile when
    // detonating the queued boulder.
    let bombrock_check = board.unit_at(x, y).and_then(|idx| {
        let u = &board.units[idx];
        if u.hp > 0 && u.type_name_str() == "BombRock" {
            Some(idx)
        } else { None }
    });

    // Apply core damage
    apply_damage_core(board, x, y, damage, result, source);

    if let Some(idx) = bombrock_check {
        if board.units[idx].hp <= 0 {
            apply_bombrock_explosion(
                board,
                x,
                y,
                result,
                bombrock_exclude,
                bombrock_depth,
            );
        }
    }

    // Volatile Vek decay fires first — it's a tier-0 unit effect. If the
    // ensuing damage kills a Blast Psion–tagged enemy that was adjacent,
    // the second helper will still see it dead and chain correctly.
    if let Some(idx) = volatile_check {
        if board.units[idx].hp <= 0 {
            apply_volatile_decay(board, x, y, result, 0);
        }
    }

    // Blast Psion death explosion: if tracked enemy just died, explode
    if let Some(idx) = death_check {
        if board.units[idx].hp <= 0 {
            apply_death_explosion(board, x, y, result, 0);
        }
    }
}

fn apply_direct_weapon_damage(board: &mut Board, x: u8, y: u8, damage: u8, wdef: &WeaponDef, result: &mut ActionResult) {
    if wdef.building_immune() {
        let tile = board.tile(x, y);
        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
            return;
        }
    }
    apply_damage(board, x, y, damage, result, DamageSource::Weapon);
}

// ── apply_throw ──────────────────────────────────────────────────────────────

/// Vice Fist: target at (tx, ty) is grabbed and tossed to the tile BEHIND the
/// attacker at (ax, ay). The destination is the tile one step from the attacker
/// in the direction OPPOSITE to the attack direction. If the destination is
/// blocked (edge / mountain / building / unit), the target stays in place and
/// takes 1 bump damage; the blocker (if a building or unit) also takes 1.
///
/// This is a teleport (2-tile total displacement), NOT a 1-tile push: the
/// target jumps directly to behind-attacker without touching the attacker tile.
pub fn apply_throw(board: &mut Board, ax: u8, ay: u8, tx: u8, ty: u8, dir: usize, result: &mut ActionResult) {
    // Find ANY unit (including dead) at target — simultaneous damage+throw.
    let unit_idx = match board.any_unit_at(tx, ty) {
        Some(idx) => idx,
        None => return,
    };

    // Non-pushable non-mechs are immune
    if !board.units[unit_idx].pushable() && !board.units[unit_idx].is_mech() {
        return;
    }

    // Destination = attacker position + opposite-of-attack direction
    let opp = opposite_dir(dir);
    let (odx, ody) = DIRS[opp];
    let nx_i = ax as i8 + odx;
    let ny_i = ay as i8 + ody;

    // Blocked by map edge — target stays, takes bump
    if !in_bounds(nx_i, ny_i) {
        apply_damage(board, tx, ty, 1, result, DamageSource::Bump);
        return;
    }

    let nx = nx_i as u8;
    let ny = ny_i as u8;

    // Blocked by mountain — target bumps, mountain takes 1 damage
    if board.tile(nx, ny).terrain == Terrain::Mountain {
        apply_damage(board, tx, ty, 1, result, DamageSource::Bump);
        let mt = board.tile_mut(nx, ny);
        if mt.building_hp > 0 {
            mt.building_hp -= 1;
        }
        if mt.building_hp == 0 {
            mt.terrain = Terrain::Rubble;
        }
        return;
    }

    // Blocked by building — live building both take 1 bump; destroyed
    // objective building (terrain=Building, hp=0, e.g. Emergency Batteries
    // after destruction) still blocks but takes no further damage.
    //
    // Grid-power accounting mirrors apply_push: non-unique multi-HP buildings
    // can defer bump grid loss until destruction. Unique/inferred objective
    // buildings lose grid immediately per HP.
    if board.tile(nx, ny).terrain == Terrain::Building {
        let dest_idx = xy_to_idx(nx, ny);
        let is_unique = (board.unique_buildings & (1u64 << dest_idx)) != 0;
        if board.tile(nx, ny).building_hp > 0 {
            apply_damage(board, tx, ty, 1, result, DamageSource::Bump);
            if thaw_frozen_building(board, nx, ny, result) {
                return;
            }
            result.buildings_bump_damaged += 1;
            // Guard: apply_damage above can trigger volatile decay / blast
            // psion chains that damage adjacent tiles, including (nx, ny).
            // That path may have already driven building_hp to 0, so the
            // outer `> 0` guard is stale. Use saturating_sub to avoid u8
            // underflow (debug panic / release wrap-to-255).
            let (hp_lost, destroyed) = {
                let bt = board.tile_mut(nx, ny);
                let old_hp = bt.building_hp;
                bt.building_hp = bt.building_hp.saturating_sub(1);
                let hp_lost = old_hp.saturating_sub(bt.building_hp);
                let destroyed = old_hp > 0 && bt.building_hp == 0;
                if destroyed && !is_unique {
                    bt.terrain = Terrain::Rubble;
                }
                (hp_lost, destroyed)
            };
            if destroyed {
                result.buildings_lost += 1;
            } else if hp_lost > 0 {
                result.buildings_damaged += hp_lost as i32;
            }
            let grid_loss = settle_building_grid_loss(
                board,
                dest_idx,
                hp_lost,
                destroyed,
                is_unique,
                DamageSource::Bump,
            );
            result.grid_damage += grid_loss as i32;
            board.grid_power = board.grid_power.saturating_sub(grid_loss);
        } else {
            // Destroyed objective: bump the thrown unit only.
            apply_damage(board, tx, ty, 1, result, DamageSource::Bump);
        }
        return;
    }

    // Blocked by another alive unit — both take 1 bump
    if let Some(blocker_idx) = board.unit_at(nx, ny) {
        if blocker_idx != unit_idx {
            apply_damage(board, tx, ty, 1, result, DamageSource::Bump);
            apply_damage(board, nx, ny, 1, result, DamageSource::Bump);
            return;
        }
    }

    // Destination clear — teleport the target there, then resolve landing
    // effects (web-break, fire/ACID pickup, water/lava/chasm death,
    // lava-ignites-flying, mines, teleporter pad). See
    // `apply_landing_effects` for the full ordered pipeline.
    board.units[unit_idx].x = nx;
    board.units[unit_idx].y = ny;
    apply_landing_effects(board, unit_idx, result);
}

// ── flip_queued_attack ───────────────────────────────────────────────────────

/// Flip a unit's queued attack direction 180° around its own position.
/// This is the true semantic for Spartan Shield (Prime_ShieldBash) and
/// Confusion Ray (Science_Confuse): the bashed enemy still attacks next
/// turn, but its target is mirrored across its own tile. If the flipped
/// target would fall off the board, the attack is cancelled by setting
/// queued_target_x = -1 (the sentinel enemy.rs:314 reads as "no target").
///
/// Ignores units with no queued attack (queued_target_x < 0 already).
/// Intentionally does NOT flip attacks for units whose queued_target
/// equals their own position (self-destructs, spawn effects, etc.) —
/// there's no "direction" to flip. Does not mutate HP, status, or
/// position; this is purely a target-vector rewrite.
pub fn flip_queued_attack(board: &mut Board, x: u8, y: u8) {
    let idx = match board.unit_at(x, y) {
        Some(i) => i,
        None => return,
    };
    let unit = &mut board.units[idx];
    if unit.hp <= 0 { return; }
    if unit.queued_target_x < 0 { return; }
    let qtx = unit.queued_target_x as i32;
    let qty = unit.queued_target_y as i32;
    let ux = unit.x as i32;
    let uy = unit.y as i32;
    let (origin_x, origin_y) = if unit.flags.contains(UnitFlags::QUEUED_ORIGIN_SET)
        && unit.queued_origin_x >= 0
        && unit.queued_origin_y >= 0
    {
        (unit.queued_origin_x as i32, unit.queued_origin_y as i32)
    } else {
        (ux, uy)
    };
    let offset_x = qtx - origin_x;
    let offset_y = qty - origin_y;
    if offset_x == 0 && offset_y == 0 {
        // Self-targeted (suicide bomber / egg spawner) — no vector to flip.
        return;
    }
    let flipped_x = ux - offset_x;
    let flipped_y = uy - offset_y;
    if !(0..8).contains(&flipped_x) || !(0..8).contains(&flipped_y) {
        // Flipped target is off-board: cancel the attack entirely.
        unit.queued_target_x = -1;
        unit.queued_target_y = -1;
        unit.queued_origin_x = -1;
        unit.queued_origin_y = -1;
        unit.flags.remove(UnitFlags::QUEUED_ORIGIN_SET);
    } else {
        unit.queued_target_x = flipped_x as i8;
        unit.queued_target_y = flipped_y as i8;
        unit.queued_origin_x = unit.x as i8;
        unit.queued_origin_y = unit.y as i8;
        unit.flags.insert(UnitFlags::QUEUED_ORIGIN_SET);
    }
}

// ── apply_push ───────────────────────────────────────────────────────────────

#[derive(Clone, Copy)]
struct PushPolicy {
    dead_nonpushable_collides: bool,
    dead_bumps_live_blocker: bool,
    edge_bump_damage: bool,
}

const DEFAULT_PUSH_POLICY: PushPolicy = PushPolicy {
    dead_nonpushable_collides: false,
    dead_bumps_live_blocker: false,
    edge_bump_damage: true,
};

const ROCKET_CENTER_PUSH_POLICY: PushPolicy = PushPolicy {
    dead_nonpushable_collides: true,
    dead_bumps_live_blocker: true,
    edge_bump_damage: false,
};

const DASH_PUNCH_PUSH_POLICY: PushPolicy = PushPolicy {
    dead_nonpushable_collides: false,
    dead_bumps_live_blocker: true,
    edge_bump_damage: true,
};

const FLAMETHROWER_PUSH_POLICY: PushPolicy = PushPolicy {
    dead_nonpushable_collides: false,
    dead_bumps_live_blocker: true,
    edge_bump_damage: true,
};

const TRI_ROCKET_PUSH_POLICY: PushPolicy = PushPolicy {
    dead_nonpushable_collides: false,
    dead_bumps_live_blocker: true,
    edge_bump_damage: true,
};

const BRUTE_UNSTABLE_RECOIL_PUSH_POLICY: PushPolicy = PushPolicy {
    dead_nonpushable_collides: false,
    dead_bumps_live_blocker: true,
    edge_bump_damage: false,
};

const BRUTE_UNSTABLE_TARGET_PUSH_POLICY: PushPolicy = PushPolicy {
    dead_nonpushable_collides: false,
    dead_bumps_live_blocker: true,
    edge_bump_damage: true,
};

const NO_EDGE_BUMP_PUSH_POLICY: PushPolicy = PushPolicy {
    dead_nonpushable_collides: false,
    dead_bumps_live_blocker: false,
    edge_bump_damage: false,
};

/// Push unit at (x, y) in direction. Damage+push are simultaneous; a
/// corpse still pushes into static obstacles (building/mountain/edge) and
/// takes/deals bump damage there. Exception: by default, a dead corpse pushed
/// INTO a live blocker unit is absorbed silently — no bump to either. See the
/// in-body comment on the unit-blocker branch for the snapshot citation.
pub fn apply_push(board: &mut Board, x: u8, y: u8, direction: usize, result: &mut ActionResult) {
    apply_push_with_policy(board, x, y, direction, result, DEFAULT_PUSH_POLICY);
}

pub(crate) fn apply_push_no_edge_bump(
    board: &mut Board,
    x: u8,
    y: u8,
    direction: usize,
    result: &mut ActionResult,
) {
    apply_push_with_policy(board, x, y, direction, result, NO_EDGE_BUMP_PUSH_POLICY);
}

fn apply_rocket_center_push(
    board: &mut Board,
    x: u8,
    y: u8,
    direction: usize,
    result: &mut ActionResult,
) {
    apply_push_with_policy(board, x, y, direction, result, ROCKET_CENTER_PUSH_POLICY);
}

fn apply_push_with_policy(
    board: &mut Board,
    x: u8,
    y: u8,
    direction: usize,
    result: &mut ActionResult,
    policy: PushPolicy,
) {
    // Find ANY unit (including dead) — simultaneous damage+push
    let unit_idx = match board.any_unit_at(x, y) {
        Some(idx) => idx,
        None => return,
    };

    // BombRocks explode as soon as they are destroyed. The dead boulder does
    // not continue as a pushable corpse for Taurus/Rocket-style damage+push.
    if board.units[unit_idx].hp <= 0 && board.units[unit_idx].type_name_str() == "BombRock" {
        return;
    }

    // Non-pushable non-mechs are immune
    if !board.units[unit_idx].pushable()
        && !board.units[unit_idx].is_mech()
        && !(policy.dead_nonpushable_collides && board.units[unit_idx].hp <= 0)
    {
        return;
    }

    let (dx, dy) = DIRS[direction];
    let nx_i = x as i8 + dx;
    let ny_i = y as i8 + dy;

    // Blocked by map edge
    if !in_bounds(nx_i, ny_i) {
        if policy.edge_bump_damage {
            apply_damage(board, x, y, 1, result, DamageSource::Bump);
        }
        return;
    }

    let nx = nx_i as u8;
    let ny = ny_i as u8;

    // Blocked by mountain — pushed unit bumps, mountain takes 1 damage
    if board.tile(nx, ny).terrain == Terrain::Mountain {
        apply_damage(board, x, y, 1, result, DamageSource::Bump);
        let mt = board.tile_mut(nx, ny);
        if mt.building_hp > 0 {
            mt.building_hp -= 1;
        }
        if mt.building_hp == 0 {
            mt.terrain = Terrain::Rubble;
        }
        return;
    }

    // Blocked by building — live building: BOTH take 1 bump.
    // Destroyed objective (terrain=Building, hp=0): only pushed unit bumps.
    //
    // Grid-power accounting: non-unique multi-HP buildings can defer bump
    // grid loss until the building is fully destroyed (bhp -> 0). Unique /
    // inferred objective buildings have per-HP grid worth and decrement
    // grid_power on every HP lost.
    //
    // Regression: grid_drop_20260421_161809_372_t02_a0 (Taurus Cannon push
    // into bhp=2 Residential: actual bhp 2→1 with grid unchanged) and
    // m00_turn_03 Ranged_Rocket bump from commit 2a86ca1 (pred grid would be
    // 4 with old code, actual grid stayed 5).
    if board.tile(nx, ny).terrain == Terrain::Building {
        let dest_idx = xy_to_idx(nx, ny);
        let is_unique = (board.unique_buildings & (1u64 << dest_idx)) != 0;
        if board.tile(nx, ny).building_hp > 0 {
            apply_damage(board, x, y, 1, result, DamageSource::Bump);
            if thaw_frozen_building(board, nx, ny, result) {
                return;
            }
            result.buildings_bump_damaged += 1;
            // Guard: apply_damage above can trigger volatile decay / blast
            // psion chains that damage adjacent tiles, including (nx, ny).
            // That path may have already driven building_hp to 0, so the
            // outer `> 0` guard is stale. Use saturating_sub to avoid u8
            // underflow (debug panic / release wrap-to-255).
            let (hp_lost, destroyed) = {
                let bt = board.tile_mut(nx, ny);
                let old_hp = bt.building_hp;
                bt.building_hp = bt.building_hp.saturating_sub(1);
                let hp_lost = old_hp.saturating_sub(bt.building_hp);
                let destroyed = old_hp > 0 && bt.building_hp == 0;
                if destroyed && !is_unique {
                    bt.terrain = Terrain::Rubble;
                }
                (hp_lost, destroyed)
            };
            if destroyed {
                result.buildings_lost += 1;
            } else if hp_lost > 0 {
                result.buildings_damaged += hp_lost as i32;
            }
            let grid_loss = settle_building_grid_loss(
                board,
                dest_idx,
                hp_lost,
                destroyed,
                is_unique,
                DamageSource::Bump,
            );
            result.grid_damage += grid_loss as i32;
            board.grid_power = board.grid_power.saturating_sub(grid_loss);
        } else {
            apply_damage(board, x, y, 1, result, DamageSource::Bump);
        }
        return;
    }

    // Blocked by a wreck — pushed unit bumps, wreck stays inert.
    if board.wreck_at(nx, ny) {
        apply_damage(board, x, y, 1, result, DamageSource::Bump);
        return;
    }

    // Blocked by another alive unit — BOTH take 1 bump.
    //
    // Exception: if the pushed unit is already dead (HP<=0), its corpse
    // does NOT deal bump damage to a live blocker unit. Static obstacles
    // (building/mountain/edge, handled above) still bump with a corpse —
    // see `test_dead_unit_still_pushes_into_building`. But in-game, a
    // simultaneous kill+push does NOT splash onto an adjacent live Vek
    // or mech: the corpse is consumed. Observed on snapshot
    // `grid_drop_20260421_131027_968_t03_a0` (Cluster Artillery kills
    // Train_Damaged on (4,4); sim predicted the corpse bumped the
    // Jelly_Explode1 at (3,4), actual game left the Jelly at full HP).
    if let Some(blocker_idx) = board.unit_at(nx, ny) {
        if blocker_idx != unit_idx {
            if board.units[unit_idx].hp <= 0 {
                if policy.dead_bumps_live_blocker {
                    apply_damage(board, nx, ny, 1, result, DamageSource::Bump);
                    return;
                }
                // Dead pusher: corpse absorbed by live blocker, no bump.
                return;
            }
            apply_damage(board, x, y, 1, result, DamageSource::Bump);
            apply_damage(board, nx, ny, 1, result, DamageSource::Bump);
            return;
        }
    }

    if !board.units[unit_idx].pushable() && !board.units[unit_idx].is_mech() {
        // Rocket-center corpse semantics can still damage blockers, but a
        // non-pushable corpse with open space behind does not need a visible
        // position change.
        return;
    }

    let retarget_death_egg = board.units[unit_idx].hp <= 0 && board.units[unit_idx].is_enemy();

    // Destination clear: only an actual tile change breaks the pushed unit's
    // own web. Blocked pushes bump in place and leave the grapple attached.
    clear_unit_web(board, unit_idx);
    board.units[unit_idx].x = nx;
    board.units[unit_idx].y = ny;
    if retarget_death_egg {
        retarget_pending_spider_egg(board, x, y, nx, ny);
    }
    apply_pod_on_land(board, unit_idx, result);

    // Web break: enemy webber pushed → unweb any mechs they were holding.
    // Position change alone breaks the grapple (regardless of whether the
    // push subsequently kills the webber via terrain/mine).
    if board.units[unit_idx].is_enemy() {
        let pushed_uid = board.units[unit_idx].uid;
        break_web_from(board, pushed_uid);
    }

    // Fire tile: pushed unit catches fire (Fire Psion grants Vek immunity).
    apply_fire_tile_pickup(board, unit_idx, nx, ny);

    // ACID pool: unit gains ACID, pool consumed
    if board.tile(nx, ny).acid() && board.tile(nx, ny).terrain != Terrain::Water {
        if board.units[unit_idx].hp > 0 && !board.units[unit_idx].shield() {
            board.units[unit_idx].set_acid(true);
        }
        board.tile_mut(nx, ny).flags.remove(TileFlags::ACID);
    }

    // Frozen GROUNDED unit on water → creates ice (unit survives). Frozen
    // FLYING units skip this: frozen cancels flight, so the unit drops from
    // the air and drowns per the deadly-terrain check below (unless Massive).
    let dest_terrain = board.tile(nx, ny).terrain;
    if board.units[unit_idx].frozen() && !board.units[unit_idx].flying()
        && dest_terrain == Terrain::Water {
        board.tile_mut(nx, ny).terrain = Terrain::Ice;
        board.tile_mut(nx, ny).set_cracked(false);
        return; // unit survives on ice
    }

    // Frozen unit on lava → unfreeze, then lava kills non-flying
    if board.units[unit_idx].frozen() && dest_terrain == Terrain::Lava {
        board.units[unit_idx].set_frozen(false);
    }

    // Check deadly terrain (frozen flying = grounded).
    // Massive prevents DROWNING in Water/Lava only — Chasm always kills
    // non-flying units (a pit-fall is a destroy, not a drown).
    let unit = &board.units[unit_idx];
    let eff_flying = unit.effectively_flying();
    let is_massive = unit.massive();
    let dest_terrain = board.tile(nx, ny).terrain;

    let deadly_kill = !eff_flying && match dest_terrain {
        Terrain::Chasm => true,
        Terrain::Water | Terrain::Lava => !is_massive,
        _ => false,
    };

    if deadly_kill {
        finish_instant_unit_death(board, unit_idx, result, nx, ny);
    } else {
        // Unit survived the push — check for Old Earth Mine (instant kill, bypasses shield)
        let tile = board.tile(nx, ny);
        if tile.old_earth_mine() {
            finish_instant_unit_death(board, unit_idx, result, nx, ny);
            board.tile_mut(nx, ny).set_old_earth_mine(false);
        }
        // Freeze mine: pushed unit gets frozen, mine consumed
        else {
            let tile = board.tile(nx, ny);
            if tile.freeze_mine() {
                if !board.units[unit_idx].shield() {
                    board.units[unit_idx].set_frozen(true);
                } else {
                    board.units[unit_idx].set_shield(false);
                }
                board.tile_mut(nx, ny).set_freeze_mine(false);
            }
        }
    }

    // Repair platform item fires after terrain/mine resolution and before
    // teleporter relocation consumes the landing tile.
    apply_repair_platform(board, unit_idx, result);

    // Teleporter pad: fires LAST, after terrain-kill / mine / item / fire /
    // acid have had a chance to mutate the unit (dead units don't swap).
    apply_teleport_on_land(board, unit_idx);
}

// ── Weapon status effect application ────────────────────────────────────────

/// Apply a weapon's status effects to a tile and its occupant.
/// Called AFTER damage and push — if damage broke a shield, status will land.
pub fn apply_weapon_status(board: &mut Board, x: u8, y: u8, wdef: &WeaponDef) {
    let occupied_at_impact = board.unit_at(x, y).is_some();
    apply_weapon_status_with_impact_occupancy(board, x, y, wdef, occupied_at_impact);
}

fn apply_fire_weapon_tile_status(board: &mut Board, x: u8, y: u8) {
    if !tile_can_host_fire(board, x, y) {
        return;
    }
    let tile = board.tile_mut(x, y);
    if matches!(tile.terrain, Terrain::Sand | Terrain::Forest) {
        tile.terrain = Terrain::Ground;
    }
    tile.set_smoke(false);
    tile.set_on_fire(true);
}

/// Apply status with explicit pre-damage occupancy for ACID fall-to-feet logic.
/// Damage can kill the occupant before status is applied; that should not turn a
/// live-target ACID hit into an empty-tile pool.
pub fn apply_weapon_status_with_impact_occupancy(
    board: &mut Board,
    x: u8,
    y: u8,
    wdef: &WeaponDef,
    occupied_at_impact: bool,
) {
    // ── Tile effects ──
    if wdef.fire() {
        apply_fire_weapon_tile_status(board, x, y);
    }
    if wdef.smoke() {
        place_smoke(board, x, y);
    }
    if wdef.freeze() {
        let tile = board.tile_mut(x, y);
        if tile.terrain == Terrain::Water {
            tile.terrain = Terrain::Ice;
            tile.set_cracked(false);
        } else if tile.terrain == Terrain::Ice && tile.cracked() {
            tile.set_cracked(false); // restore cracked ice
        }
        if tile.on_fire() {
            tile.set_on_fire(false); // freeze extinguishes fire
        }
    }
    if wdef.acid() {
        // Acid weapons apply ACID to live units, but do not create a ground
        // pool underneath them until that ACID unit dies. If the status is
        // blocked by shield/frozen, it "falls to feet" and acidifies the tile.
        // Empty liquid/ground hits still create a persistent A.C.I.D. Tile/Pool.
        let acid_falls_to_tile = match board.unit_at(x, y) {
            Some(idx) => {
                let u = &board.units[idx];
                u.shield() || u.frozen()
            }
            None => !occupied_at_impact,
        };
        if acid_falls_to_tile {
            let tile = board.tile_mut(x, y);
            if matches!(tile.terrain, Terrain::Water | Terrain::Ground | Terrain::Rubble) {
                tile.set_acid(true);
            }
        }
    }

    if wdef.shield() {
        let tile = board.tile_mut(x, y);
        if tile.is_building() {
            tile.set_shield(true);
        }
    }

    // ── Unit effects ──
    if let Some(idx) = board.unit_at(x, y) {
        let unit = &board.units[idx];

        // Shield blocks negative status WITHOUT consuming the shield
        if unit.shield() && (wdef.fire() || wdef.acid() || wdef.web() || wdef.freeze()) {
            // Shield is a positive effect, always applies even if shield is up
            if wdef.shield() {
                board.units[idx].set_shield(true);
            }
            return;
        }

        if wdef.fire() {
            // Pilot_Rock (Ariadne) is fire-immune. Flame Shielding blocks
            // player mechs; Fire Psion grants the same immunity to Vek.
            // Freeze-on-fire still unfreezes because that mechanic is
            // independent of fire application.
            apply_fire_weapon_unit_status(board, idx);
        }
        if wdef.acid() {
            if !board.units[idx].frozen() {
                board.units[idx].set_acid(true);
                clear_mites(&mut board.units[idx]);
            }
        }
        if wdef.freeze() {
            let u = &mut board.units[idx];
            if u.fire() {
                u.set_fire(false); // freeze on fire: extinguish
            }
            u.set_frozen(true);
            clear_mites(u);
        }
        if wdef.web() {
            // Pilot_Soldier (Camila Vera) is web-immune. The web_source_uid
            // setter at the enemy-weapon site is also guarded on this flag,
            // so a Camila-piloted mech never ends up in a half-webbed state.
            if !board.units[idx].pilot_soldier() {
                board.units[idx].set_web(true);
            }
        }
        if wdef.shield() {
            board.units[idx].set_shield(true);
        }
    }
}

// ── Weapon simulation dispatch ───────────────────────────────────────────────

/// Simulate firing a weapon using the compile-time default weapon table.
/// Thin wrapper around `simulate_weapon_with` retained for test call sites.
pub fn simulate_weapon(
    board: &mut Board,
    attacker_idx: usize,
    weapon_id: WId,
    target_x: u8,
    target_y: u8,
) -> ActionResult {
    simulate_weapon_with(board, attacker_idx, weapon_id, target_x, target_y, &WEAPONS)
}

/// Simulate firing a weapon. Modifies board in-place. `weapons` supplies
/// the effective `WeaponDef` table (defaults or overlay-patched).
pub fn simulate_weapon_with(
    board: &mut Board,
    attacker_idx: usize,
    weapon_id: WId,
    target_x: u8,
    target_y: u8,
    weapons: &WeaponTable,
) -> ActionResult {
    let mut result = ActionResult::default();
    let base_wdef = &weapons[weapon_id as usize];
    let mut boosted_wdef;
    let wdef = if board.units[attacker_idx].boosted() {
        boosted_wdef = *base_wdef;
        if boosted_wdef.damage > 0 {
            boosted_wdef.damage = boosted_wdef.damage.saturating_add(1);
        }
        if boosted_wdef.damage_outer > 0 {
            boosted_wdef.damage_outer = boosted_wdef.damage_outer.saturating_add(1);
        }
        if boosted_wdef.self_damage > 0 {
            boosted_wdef.self_damage = boosted_wdef.self_damage.saturating_add(1);
        }
        if boosted_wdef.burns_fire_targets() {
            boosted_wdef.boost_bonus = 1;
        }
        &boosted_wdef
    } else {
        base_wdef
    };

    let ax = board.units[attacker_idx].x;
    let ay = board.units[attacker_idx].y;
    // Use cardinal_direction (any colinear distance) so artillery/projectile/laser/
    // charge/pull pick up the correct attack axis even when target isn't adjacent.
    // Melee targets ARE adjacent, so both helpers agree there.
    let attack_dir = cardinal_direction(ax, ay, target_x, target_y);
    let seismic_target_idx = if is_seismic_capacitor(weapon_id) {
        board.unit_at(target_x, target_y)
    } else {
        None
    };

    if weapon_id == WId::TrappedExplode {
        sim_trapped_explode(board, attacker_idx, &mut result);
        return result;
    }

    if wdef.weapon_type == WeaponType::Leap {
        if let Some(reason) = leap_landing_illegal_reason(
            board, attacker_idx, weapon_id, target_x, target_y,
        ) {
            result.events.push(format!(
                "illegal_leap_landing:{}:{}:{}",
                target_x, target_y, reason
            ));
            return result;
        }
    }

    if weapon_id == WId::VipTruckMove {
        let move_result = simulate_move(board, attacker_idx, (target_x, target_y));
        result.merge(&move_result);
        return result;
    }

    let leech_kills_before = result.leech_credit_kills;

    match wdef.weapon_type {
        WeaponType::Melee => sim_melee(board, wdef, ax, ay, target_x, target_y, attack_dir, &mut result),
        WeaponType::Projectile => {
            sim_projectile(board, ax, ay, weapon_id, wdef, attack_dir, &mut result)
        },
        WeaponType::Artillery if is_arachnoid_injector(weapon_id) => {
            sim_arachnoid_injector(
                board,
                weapon_id,
                wdef,
                ax,
                ay,
                target_x,
                target_y,
                attack_dir,
                &mut result,
            )
        }
        WeaponType::Artillery if is_tri_rocket(weapon_id) => {
            sim_tri_rocket(board, wdef, ax, ay, target_x, target_y, attack_dir, &mut result)
        }
        WeaponType::Artillery => sim_artillery(board, weapon_id, wdef, ax, ay, target_x, target_y, attack_dir, &mut result),
        WeaponType::SelfAoe => {
            if is_mass_shift(weapon_id) {
                if let Some(dir) = direction_between(ax, ay, target_x, target_y) {
                    sim_mass_shift(board, ax, ay, wdef, dir, &mut result);
                } else {
                    result.events.push(format!(
                        "invalid_mass_shift_target:{}:{}:from:{}:{}",
                        target_x, target_y, ax, ay
                    ));
                }
            } else if self_aoe_target_in_area(ax, ay, target_x, target_y) {
                sim_self_aoe(board, ax, ay, wdef, &mut result);
            } else {
                result.events.push(format!(
                    "invalid_self_aoe_target:{}:{}:from:{}:{}",
                    target_x, target_y, ax, ay
                ));
            }
        },
        WeaponType::Pull | WeaponType::Swap => sim_pull_or_swap(board, attacker_idx, wdef, target_x, target_y, attack_dir, &mut result),
        WeaponType::Charge => sim_charge(board, attacker_idx, weapon_id, wdef, attack_dir, &mut result),
        WeaponType::Leap => sim_leap(board, attacker_idx, weapon_id, wdef, target_x, target_y, &mut result),
        WeaponType::Laser => sim_laser(board, ax, ay, wdef, attack_dir, &mut result),
        WeaponType::HealAll => sim_heal_all(board, &mut result),
        WeaponType::GlobalPush => {
            if let Some(dir) = support_wind_dir_from_target(target_x, target_y) {
                sim_global_push(board, dir, &mut result);
            }
        }
        WeaponType::GlobalUnitEffect => sim_global_unit_effect(
            board, wdef, (ax, ay), (target_x, target_y), &mut result,
        ),
        WeaponType::TwoClick if is_hydraulic_lifter(weapon_id) => {
            sim_hydraulic_lifter(board, wdef, ax, ay, target_x, target_y, attack_dir, &mut result)
        }
        WeaponType::Terraformer => sim_terraformer(board, ax, ay, target_x, target_y, &mut result),
        WeaponType::Disposal => sim_disposal(board, target_x, target_y, &mut result),
        _ => {} // Passive, Deploy, TwoClick — no simulation
    }

    if let Some(idx) = seismic_target_idx {
        if board.units[idx].hp <= 0 {
            create_adjacent_cracks(board, target_x, target_y, &mut result);
        }
    }

    if is_arachnoid_attack(weapon_id) {
        board.units[attacker_idx].hp = 0;
    }

    // Self damage. Skipped for Charge weapons — sim_charge applies it inline
    // only when the charge actually hits a target (empty-tile charges take no
    // recoil in the game, but the solver used to over-predict HP by 1).
    if wdef.self_damage > 0 && wdef.weapon_type != WeaponType::Charge {
        let ax = board.units[attacker_idx].x;
        let ay = board.units[attacker_idx].y;
        apply_damage(board, ax, ay, wdef.self_damage, &mut result, DamageSource::SelfDamage);
    }

    let mut leech_heal_applied = false;

    // Leap movement is a real tile change, but live resolves Nanobots from
    // Leap kills after queued self-damage and before landing tile effects.
    // This lets a self-disabled Hazardous mech revive, then catch fire/ACID
    // from its destination. Recoil still strips shields before landing ACID.
    if wdef.weapon_type == WeaponType::Leap {
        let leech_kills = result.leech_credit_kills - leech_kills_before;
        apply_viscera_nanobots_heal(board, attacker_idx, leech_kills, &mut result);
        leech_heal_applied = true;

        let lx = board.units[attacker_idx].x;
        let ly = board.units[attacker_idx].y;
        if (lx, ly) != (ax, ay) {
            apply_landing_effects(board, attacker_idx, &mut result);
        }
    }

    // Push self backward
    if wdef.push_self() {
        if let Some(dir) = attack_dir {
            let ax = board.units[attacker_idx].x;
            let ay = board.units[attacker_idx].y;
            let kills_before = result.enemies_killed;
            let recoil_policy = if weapon_id == WId::BruteUnstable {
                BRUTE_UNSTABLE_RECOIL_PUSH_POLICY
            } else {
                DEFAULT_PUSH_POLICY
            };
            apply_push_with_policy(board, ax, ay, opposite_dir(dir), &mut result, recoil_policy);
            let pushback_kills = result.enemies_killed - kills_before;
            if pushback_kills > 0 {
                result.leech_credit_kills += pushback_kills;
            }
        }
    }

    if !leech_heal_applied {
        let leech_kills = result.leech_credit_kills - leech_kills_before;
        apply_viscera_nanobots_heal(board, attacker_idx, leech_kills, &mut result);
    }

    // Self-freeze (Cryo-Launcher freezes attacker)
    if wdef.freeze() && weapon_id == WId::RangedIce {
        let u = &board.units[attacker_idx];
        if !u.shield() {
            board.units[attacker_idx].set_frozen(true);
        }
    }

    result
}

// ── Terraformer ────────────────────────────────────────────────────────────────

fn apply_terraformer_tile(board: &mut Board, x: u8, y: u8, result: &mut ActionResult) {
    if let Some(idx) = board.unit_at(x, y) {
        let hp_before = board.units[idx].hp.max(0) as i32;
        let was_enemy = board.units[idx].is_enemy();
        let was_player = board.units[idx].is_player();
        finish_instant_unit_death(board, idx, result, x, y);
        if hp_before > 0 && board.units[idx].hp <= 0 {
            if was_enemy {
                result.enemy_damage_dealt += hp_before;
            } else if was_player {
                result.mech_damage_taken += hp_before;
            }
        }
    }

    if board.tile(x, y).terrain == Terrain::Building && board.tile(x, y).building_hp > 0 {
        if thaw_frozen_building(board, x, y, result) {
            return;
        }
        let idx = xy_to_idx(x, y);
        let is_unique = (board.unique_buildings & (1u64 << idx)) != 0;
        let hp_lost = {
            let tile = board.tile_mut(x, y);
            let lost = tile.building_hp;
            tile.building_hp = 0;
            tile.set_shield(false);
            lost
        };
        if hp_lost > 0 {
            result.buildings_damaged += hp_lost as i32;
            result.buildings_lost += 1;
            let grid_loss = settle_building_grid_loss(
                board,
                idx,
                hp_lost,
                true,
                is_unique,
                DamageSource::Weapon,
            );
            result.grid_damage += grid_loss as i32;
            board.grid_power = board.grid_power.saturating_sub(grid_loss);
        }
    }

    let terrain = board.tile(x, y).terrain;
    let preserve_ground_acid = terrain == Terrain::Ground && board.tile(x, y).acid();
    let tile = board.tile_mut(x, y);
    tile.set_smoke(false);
    tile.set_on_fire(false);
    tile.set_cracked(false);
    if terrain != Terrain::Mountain && !preserve_ground_acid {
        tile.terrain = Terrain::Sand;
        tile.building_hp = 0;
    }
    if terrain != Terrain::Mountain {
        tile.set_grass(false);
    }

    if let Some(idx) = board.unit_at(x, y) {
        board.units[idx].set_fire(false);
    }
}

fn sim_terraformer(board: &mut Board, ax: u8, ay: u8, tx: u8, ty: u8, result: &mut ActionResult) {
    let Some(tiles) = terraformer_sweep_tiles(ax, ay, tx, ty) else {
        result.events.push(format!("invalid_terraformer_target:{}:{}:from:{}:{}", tx, ty, ax, ay));
        return;
    };

    for (x, y) in tiles {
        apply_terraformer_tile(board, x, y, result);
    }
}

// ── Disposal A.C.I.D. Launcher ───────────────────────────────────────────────

fn apply_disposal_tile(board: &mut Board, x: u8, y: u8, result: &mut ActionResult) {
    if let Some(idx) = board.unit_at(x, y) {
        let hp_before = board.units[idx].hp.max(0) as i32;
        let was_enemy = board.units[idx].is_enemy();
        let was_player = board.units[idx].is_player();
        finish_instant_unit_death(board, idx, result, x, y);
        if hp_before > 0 && board.units[idx].hp <= 0 {
            if was_enemy {
                result.enemy_damage_dealt += hp_before;
            } else if was_player {
                result.mech_damage_taken += hp_before;
            }
        }
    }

    if board.tile(x, y).terrain == Terrain::Building && board.tile(x, y).building_hp > 0 {
        if thaw_frozen_building(board, x, y, result) {
            return;
        }
        let idx = xy_to_idx(x, y);
        let is_unique = (board.unique_buildings & (1u64 << idx)) != 0;
        let hp_lost = {
            let tile = board.tile_mut(x, y);
            let lost = tile.building_hp;
            tile.building_hp = 0;
            tile.set_shield(false);
            if !is_unique {
                tile.terrain = Terrain::Rubble;
            }
            lost
        };
        if hp_lost > 0 {
            result.buildings_damaged += hp_lost as i32;
            result.buildings_lost += 1;
            let grid_loss = settle_building_grid_loss(
                board,
                idx,
                hp_lost,
                true,
                is_unique,
                DamageSource::Weapon,
            );
            result.grid_damage += grid_loss as i32;
            board.grid_power = board.grid_power.saturating_sub(grid_loss);
        }
    }

    let tile = board.tile_mut(x, y);
    tile.set_acid(true);
    tile.set_cracked(false);
    tile.set_smoke(false);
    tile.set_on_fire(false);
    if tile.terrain == Terrain::Mountain {
        tile.terrain = Terrain::Ground;
        tile.building_hp = 0;
    }
}

fn sim_disposal(board: &mut Board, tx: u8, ty: u8, result: &mut ActionResult) {
    for (x, y) in disposal_cross_tiles(tx, ty) {
        apply_disposal_tile(board, x, y, result);
    }
}

// ── Cataclysm squad weapons ─────────────────────────────────────────────────

fn sim_hydraulic_lifter(
    board: &mut Board,
    wdef: &WeaponDef,
    ax: u8,
    ay: u8,
    tx: u8,
    ty: u8,
    attack_dir: Option<usize>,
    result: &mut ActionResult,
) {
    let Some(dir) = attack_dir else {
        result.events.push(format!("invalid_hydraulic_lifter_target:{}:{}:from:{}:{}", tx, ty, ax, ay));
        return;
    };
    let dist = (tx as i8 - ax as i8).unsigned_abs() + (ty as i8 - ay as i8).unsigned_abs();
    if dist < 2 {
        result.events.push(format!("invalid_hydraulic_lifter_target:{}:{}:from:{}:{}", tx, ty, ax, ay));
        return;
    }

    let (dx, dy) = DIRS[dir];
    let grab_x = ax as i8 + dx;
    let grab_y = ay as i8 + dy;
    if !in_bounds(grab_x, grab_y) || board.is_blocked(tx, ty, true) {
        return;
    }
    let gx = grab_x as u8;
    let gy = grab_y as u8;
    let Some(unit_idx) = board.unit_at(gx, gy) else { return; };
    if !board.units[unit_idx].pushable() && !board.units[unit_idx].is_mech() {
        return;
    }

    let landing_was_forest = board.tile(tx, ty).terrain == Terrain::Forest;
    board.units[unit_idx].x = tx;
    board.units[unit_idx].y = ty;
    apply_landing_effects(board, unit_idx, result);
    apply_direct_weapon_damage(board, tx, ty, wdef.damage, wdef, result);
    if landing_was_forest {
        apply_fire_tile_pickup(board, unit_idx, tx, ty);
    }
}

fn sim_tri_rocket(
    board: &mut Board,
    wdef: &WeaponDef,
    ax: u8,
    ay: u8,
    tx: u8,
    ty: u8,
    attack_dir: Option<usize>,
    result: &mut ActionResult,
) {
    let Some(dir) = attack_dir else {
        result.events.push(format!("invalid_tri_rocket_target:{}:{}:from:{}:{}", tx, ty, ax, ay));
        return;
    };
    let (dx, dy) = DIRS[dir];
    let mut vacated_kill_tiles: Vec<(u8, u8)> = Vec::new();
    let center_bombrock = board.unit_at(tx, ty).is_some_and(|idx| {
        board.units[idx].hp > 0 && board.units[idx].type_name_str() == "BombRock"
    });
    if center_bombrock {
        let center_idx = board.unit_at(tx, ty);
        apply_damage_core(board, tx, ty, wdef.damage, result, DamageSource::Weapon);
        if let Some(idx) = center_idx {
            if board.units[idx].hp <= 0 {
                // Ranged_Crack queues artillery impacts on three separate
                // tiles. Live Cataclysm captures show a BombRock destroyed by
                // the center rocket does not emit its normal four-way blast;
                // instead the killed boulder collides forward along the rocket
                // line before the front rocket's own hit resolves.
                let fx = tx as i8 + dx;
                let fy = ty as i8 + dy;
                if in_bounds(fx, fy) {
                    apply_damage(board, fx as u8, fy as u8, 1, result, DamageSource::Bump);
                }
            }
        }
    }
    for offset in [1i8, 0, -1] {
        if center_bombrock && offset == 0 {
            continue;
        }
        let px = tx as i8 + dx * offset;
        let py = ty as i8 + dy * offset;
        if !in_bounds(px, py) { continue; }
        let x = px as u8;
        let y = py as u8;
        let pre_hit_unit = board.unit_at(x, y).map(|idx| {
            (
                idx,
                board.units[idx].hp,
                board.units[idx].acid(),
                board.tile(x, y).acid(),
                board.units[idx].x,
                board.units[idx].y,
            )
        });
        let deferred_death_explosion = if wdef.building_immune()
            && board.tile(x, y).terrain == Terrain::Building
            && board.tile(x, y).building_hp > 0
        {
            None
        } else {
            apply_damage_defer_death_explosion(
                board,
                x,
                y,
                wdef.damage,
                result,
                DamageSource::Weapon,
            )
        };
        let killed_by_hit = pre_hit_unit
            .map(|(idx, _, _, _, _, _)| board.units[idx].hp <= 0)
            .unwrap_or(false);
        apply_push_with_policy(board, x, y, dir, result, TRI_ROCKET_PUSH_POLICY);
        if let Some((idx, pre_hp, was_acid, tile_had_acid, ox, oy)) = pre_hit_unit {
            let fx = board.units[idx].x;
            let fy = board.units[idx].y;
            let moved = (fx, fy) != (ox, oy);
            let died = board.units[idx].hp <= 0;
            if died && moved && killed_by_hit {
                // Tri-Rocket queues three individual SpaceDamage hits. Live
                // captures show a killed ACID unit leaves its pool at the
                // pushed corpse destination, not at the pre-push damage tile.
                vacated_kill_tiles.push((ox, oy));
                if was_acid {
                    if !tile_had_acid {
                        board.tile_mut(ox, oy).flags.remove(TileFlags::ACID);
                    }
                    leave_acid_pool_on_death(board, fx, fy);
                }
            } else if pre_hp > 0 && board.units[idx].hp > 0 && moved
                && vacated_kill_tiles.contains(&(fx, fy))
            {
                // The following rocket can shove a live unit into a tile that
                // an earlier killed target just vacated. The engine applies a
                // corpse-bump damage to the entering unit, but still lets it
                // occupy the tile after the corpse has been pushed onward.
                apply_damage(board, fx, fy, 1, result, DamageSource::Bump);
            }
        }
        if let Some(idx) = deferred_death_explosion {
            let ex = board.units[idx].x;
            let ey = board.units[idx].y;
            apply_death_explosion(board, ex, ey, result, 0);
        }
    }
}

fn create_crack(board: &mut Board, x: u8, y: u8, result: &mut ActionResult) {
    let tile = board.tile_mut(x, y);
    match tile.terrain {
        Terrain::Ground | Terrain::Ice if !tile.cracked() => {
            tile.set_cracked(true);
            result.events.push(format!("crack_created:{}:{}", x, y));
        }
        Terrain::Mountain if tile.building_hp > 0 => {
            tile.building_hp -= 1;
            result.events.push(format!("mountain_cracked:{}:{}", x, y));
            if tile.building_hp == 0 {
                tile.terrain = Terrain::Rubble;
            }
        }
        _ => {}
    }
}

fn create_adjacent_cracks(board: &mut Board, x: u8, y: u8, result: &mut ActionResult) {
    for &(dx, dy) in &DIRS {
        let nx = x as i8 + dx;
        let ny = y as i8 + dy;
        if in_bounds(nx, ny) {
            create_crack(board, nx as u8, ny as u8, result);
        }
    }
}

// ── Melee ────────────────────────────────────────────────────────────────────

fn sim_melee(board: &mut Board, wdef: &WeaponDef, ax: u8, ay: u8, tx: u8, ty: u8, attack_dir: Option<usize>, result: &mut ActionResult) {
    // path_size>1 melee (Prime_Spear: Lua scripts/weapons_prime.lua:792-846).
    // Lua SkillEffect damages every tile from attacker+1 .. attacker+distance
    // in order, with only the FURTHEST tile receiving Push and weapon status
    // (acid). Damage in-path tiles first so the closer-tile occupant resolves
    // before the target tile's push (matches Lua sequential SpaceDamage).
    if let Some(dir) = attack_dir {
        let (dxs, dys) = DIRS[dir];
        let dist_x = (tx as i8 - ax as i8).abs();
        let dist_y = (ty as i8 - ay as i8).abs();
        let distance = dist_x.max(dist_y); // cardinal => one axis is 0
        if distance > 1 {
            for i in 1..distance {
                let px = ax as i8 + dxs * i;
                let py = ay as i8 + dys * i;
                if !in_bounds(px, py) { break; }
                let pxu = px as u8;
                let pyu = py as u8;
                if wdef.burns_fire_targets() && wdef.fire() {
                    let mut path_dmg = wdef.damage;
                    if let Some(uid) = board.unit_at(pxu, pyu) {
                        if board.units[uid].fire() {
                            path_dmg = path_dmg.saturating_add(2);
                            path_dmg = path_dmg.saturating_add(wdef.boost_bonus);
                        }
                    }
                    let occupied_at_impact = board.unit_at(pxu, pyu).is_some();
                    apply_damage(board, pxu, pyu, path_dmg, result, DamageSource::Weapon);
                    apply_weapon_status_with_impact_occupancy(
                        board,
                        pxu,
                        pyu,
                        wdef,
                        occupied_at_impact,
                    );
                } else {
                    apply_damage(board, pxu, pyu, wdef.damage, result, DamageSource::Weapon);
                }
            }
        }
    }

    // Prime_Flamethrower "Damage units already on Fire" bonus. Lua applies
    // FireDamage (=2) on top of base Damage (=0) when the target tile's
    // pawn is on fire at firing time. The bonus must be evaluated BEFORE
    // damage is applied (so a flame-on-fire-pawn deals 2 even though the
    // pawn dies from this hit). Snapshot the pre-damage on_fire state.
    let mut target_dmg = wdef.damage;
    if wdef.burns_fire_targets() {
        if let Some(uid) = board.unit_at(tx, ty) {
            if board.units[uid].fire() {
                target_dmg = target_dmg.saturating_add(2);
                target_dmg = target_dmg.saturating_add(wdef.boost_bonus);
            }
        }
    }
    let target_occupied_at_impact = board.unit_at(tx, ty).is_some();
    let defer_target_death_explosion = !wdef.chain()
        && attack_dir.is_some()
        && target_dmg > 0
        && !matches!(wdef.push, PushDir::None | PushDir::Flip);
    let deferred_death_explosion = if defer_target_death_explosion {
        apply_damage_defer_death_explosion(
            board, tx, ty, target_dmg, result, DamageSource::Weapon,
        )
    } else if !wdef.chain() {
        apply_damage(board, tx, ty, target_dmg, result, DamageSource::Weapon);
        None
    } else {
        None
    };

    // Chain weapon (Electric Whip): BFS through adjacent pawns, and with
    // Building Chain powered, through live Grid Buildings as zero-damage
    // nodes. Lua's Prime_Lightning only emits SpaceDamage for pawns/building
    // chain nodes; it does not damage terrain such as Ice under the pawn.
    // Live captures show it still ignites Forest under a hit pawn.
    // The shooter's own tile is excluded from the graph.
    if wdef.chain() {
        let mut visited = 0u64;
        visited |= 1u64 << xy_to_idx(ax, ay);
        let mut queue: Vec<(u8, u8)> = vec![(tx, ty)];
        let mut head = 0;
        while head < queue.len() {
            let (cx, cy) = queue[head];
            head += 1;
            let bit = 1u64 << xy_to_idx(cx, cy);
            if visited & bit != 0 { continue; }
            visited |= bit;

            let has_pawn = board.unit_at(cx, cy).is_some();
            let chain_building = wdef.building_immune() && board.tile(cx, cy).is_building();
            if !has_pawn && !chain_building {
                continue;
            }

            if has_pawn {
                apply_damage(board, cx, cy, wdef.damage, result, DamageSource::ChainWhip);
            }

            for &(dx, dy) in &DIRS {
                let nx = cx as i8 + dx;
                let ny = cy as i8 + dy;
                if !in_bounds(nx, ny) { continue; }
                let next_bit = 1u64 << xy_to_idx(nx as u8, ny as u8);
                if visited & next_bit == 0 {
                    queue.push((nx as u8, ny as u8));
                }
            }
        }
    }

    if let Some(dir) = attack_dir {
        let flamethrower_push =
            wdef.burns_fire_targets() && wdef.fire() && matches!(wdef.push, PushDir::Forward);
        let flamethrower_target_at_impact = if flamethrower_push {
            board.unit_at(tx, ty)
        } else {
            None
        };
        let flamethrower_target_effectively_flying = flamethrower_target_at_impact
            .map(|idx| board.units[idx].effectively_flying())
            .unwrap_or(false);

        if flamethrower_push {
            // Live Prime_Flamethrower lights the struck tile, then pushes the
            // target. Grounded occupants catch the flame even if the push
            // moves them away; flying occupants only catch it if the push is
            // blocked and they remain on the struck tile, or if they land on
            // ordinary burning terrain.
            apply_fire_weapon_tile_status(board, tx, ty);
            if let Some(idx) = flamethrower_target_at_impact {
                if !flamethrower_target_effectively_flying {
                    apply_fire_weapon_unit_status(board, idx);
                }
            }
        } else {
            // Apply weapon status BEFORE push (unit still at target tile)
            apply_weapon_status_with_impact_occupancy(
                board, tx, ty, wdef, target_occupied_at_impact,
            );
        }

        match wdef.push {
            PushDir::Forward => {
                if wdef.burns_fire_targets() {
                    apply_push_with_policy(board, tx, ty, dir, result, FLAMETHROWER_PUSH_POLICY);
                } else {
                    apply_push(board, tx, ty, dir, result);
                }
            }
            PushDir::Flip => flip_queued_attack(board, tx, ty),
            PushDir::Backward => apply_push(board, tx, ty, opposite_dir(dir), result),
            PushDir::Perpendicular => apply_push(board, tx, ty, (dir + 1) % 4, result),
            PushDir::Outward => {
                apply_push(board, tx, ty, dir, result);
            }
            PushDir::Throw => apply_throw(board, ax, ay, tx, ty, dir, result),
            _ => {}
        }

        if flamethrower_push {
            if let Some(idx) = board.unit_at(tx, ty) {
                if flamethrower_target_at_impact == Some(idx)
                    && flamethrower_target_effectively_flying
                {
                    apply_fire_weapon_unit_status(board, idx);
                }
                apply_fire_tile_pickup(board, idx, tx, ty);
            }
        }

        if let Some(idx) = deferred_death_explosion {
            let ex = board.units[idx].x;
            let ey = board.units[idx].y;
            apply_death_explosion(board, ex, ey, result, 0);
        }

        // AoE behind: hit tile behind target
        if wdef.aoe_behind() {
            let (ddx, ddy) = DIRS[dir];
            let bx = tx as i8 + ddx;
            let by = ty as i8 + ddy;
            if in_bounds(bx, by) {
                apply_damage(board, bx as u8, by as u8, wdef.damage, result, DamageSource::Weapon);
            }
        }

        // AoE perpendicular: hit tiles beside target, push in attack direction
        if wdef.aoe_perpendicular() {
            for &perp in &[(dir + 1) % 4, (dir + 3) % 4] {
                let (pdx, pdy) = DIRS[perp];
                let px = tx as i8 + pdx;
                let py = ty as i8 + pdy;
                if in_bounds(px, py) {
                    apply_damage(board, px as u8, py as u8, wdef.damage, result, DamageSource::Weapon);
                    if wdef.push == PushDir::Forward {
                        apply_push(board, px as u8, py as u8, dir, result);
                    }
                }
            }
        }
    }
}

// ── Projectile ───────────────────────────────────────────────────────────────

/// Resolve projectile damage at the hit tile, honoring DAMAGE_SCALES_WITH_DIST.
/// Mirrors Brute_Sniper's Lua formula (weapons_brute.lua:969-991): damage =
/// max(0, min(MaxDamage, tile_distance - 1)). Adjacent target → 0 damage.
/// `wdef.damage` is the unscaled damage cap (== MaxDamage in Lua).
fn projectile_damage(wdef: &WeaponDef, ax: u8, ay: u8, hx: u8, hy: u8) -> u8 {
    if !wdef.damage_scales_with_dist() {
        return wdef.damage;
    }
    let tile_dist = (ax as i16 - hx as i16).unsigned_abs()
        + (ay as i16 - hy as i16).unsigned_abs();
    // Cardinal projectile, so one of (|dx|, |dy|) is 0 — Manhattan == Chebyshev.
    let scaled = tile_dist.saturating_sub(1) as u8;
    scaled.min(wdef.damage)
}

fn acid_projector_edge_block_suppresses_status(
    weapon_id: WId,
    wdef: &WeaponDef,
    hx: u8,
    hy: u8,
    dir: usize,
) -> bool {
    if weapon_id != WId::ScienceAcidShot || wdef.damage != 0 {
        return false;
    }
    let (dx, dy) = DIRS[dir];
    !in_bounds(hx as i8 + dx, hy as i8 + dy)
}

fn sim_projectile(
    board: &mut Board,
    ax: u8,
    ay: u8,
    weapon_id: WId,
    wdef: &WeaponDef,
    attack_dir: Option<usize>,
    result: &mut ActionResult,
) {
    let dir = match attack_dir {
        Some(d) => d,
        None => return,
    };

    let (dx, dy) = DIRS[dir];

    // Find first hit. Mountains stop the projectile AND take 1 damage
    // (2 HP → damaged → rubble), mirroring sim_laser's beam-hits-mountain
    // behavior. Without the damage call, Mirror Shot's backward arm
    // mispredicted "mountain blocks free" and we under-counted building
    // destruction when a bumped unit or pushed tile cascade followed.
    let mut hit_x: i8 = -1;
    let mut hit_y: i8 = -1;
    let mut mountain_hit: Option<(u8, u8)> = None;
    for i in 1..8i8 {
        let nx = ax as i8 + dx * i;
        let ny = ay as i8 + dy * i;
        if !in_bounds(nx, ny) { break; }
        let nxu = nx as u8;
        let nyu = ny as u8;

        let tile = board.tile(nxu, nyu);
        if tile.terrain == Terrain::Mountain {
            mountain_hit = Some((nxu, nyu));
            break;
        }
        if tile.is_building() && !wdef.phase() {
            hit_x = nx; hit_y = ny; break;
        }
        if board.unit_at(nxu, nyu).is_some() {
            hit_x = nx; hit_y = ny; break;
        }
    }

    if hit_x >= 0 {
        let hx = hit_x as u8;
        let hy = hit_y as u8;
        let dmg = projectile_damage(wdef, ax, ay, hx, hy);
        let occupied_at_impact = board.unit_at(hx, hy).is_some();
        let damage_source = if weapon_id == WId::BruteUnstable {
            DamageSource::WeaponNoAcidPool
        } else {
            DamageSource::Weapon
        };
        let skip_friendly_damage = wdef.friendly_immune()
            && board.unit_at(hx, hy)
                .map(|idx| board.units[idx].is_player())
                .unwrap_or(false);
        let defer_death_explosion = dmg > 0 && !matches!(wdef.push, PushDir::None | PushDir::Flip);
        let deferred_death_explosion = if skip_friendly_damage {
            None
        } else if defer_death_explosion {
            apply_damage_defer_death_explosion(
                board, hx, hy, dmg, result, damage_source,
            )
        } else {
            apply_damage(board, hx, hy, dmg, result, damage_source);
            None
        };
        let acid_projector_edge_suppressed =
            acid_projector_edge_block_suppresses_status(weapon_id, wdef, hx, hy, dir);
        if !acid_projector_edge_suppressed {
            apply_weapon_status_with_impact_occupancy(
                board, hx, hy, wdef, occupied_at_impact,
            ); // status BEFORE push (unit still here)
        }
        let suppress_direct_push = acid_projector_edge_suppressed;
        let policy = if wdef.no_edge_bump_direct_push() {
            NO_EDGE_BUMP_PUSH_POLICY
        } else if weapon_id == WId::BruteUnstable {
            BRUTE_UNSTABLE_TARGET_PUSH_POLICY
        } else if weapon_id == WId::BruteMirrorshot {
            TRI_ROCKET_PUSH_POLICY
        } else {
            DEFAULT_PUSH_POLICY
        };
        match wdef.push {
            PushDir::Forward if !suppress_direct_push => apply_push_with_policy(board, hx, hy, dir, result, policy),
            PushDir::Backward if !suppress_direct_push => apply_push_with_policy(board, hx, hy, opposite_dir(dir), result, policy),
            _ => {}
        }
        if let Some(idx) = deferred_death_explosion {
            let ex = board.units[idx].x;
            let ey = board.units[idx].y;
            apply_death_explosion(board, ex, ey, result, 0);
        }
    } else if let Some((mx, my)) = mountain_hit {
        // Projectile struck a mountain with no prior target — damage it.
        let dmg = projectile_damage(wdef, ax, ay, mx, my);
        apply_damage(board, mx, my, dmg, result, DamageSource::Weapon);
    }

    // Mirror shot (aoe_behind): also fire backward
    if wdef.aoe_behind() {
        let opp = opposite_dir(dir);
        let (odx, ody) = DIRS[opp];
        for i in 1..8i8 {
            let nx = ax as i8 + odx * i;
            let ny = ay as i8 + ody * i;
            if !in_bounds(nx, ny) { break; }
            let nxu = nx as u8;
            let nyu = ny as u8;

            let tile = board.tile(nxu, nyu);
            if tile.terrain == Terrain::Mountain {
                // Backward projectile stops at a mountain but damages it
                // (Janus Cannon / Mirror Shot rubbleizes mountains behind
                // the shooter, matching forward-projectile behavior).
                apply_damage(board, nxu, nyu, wdef.damage, result, DamageSource::Weapon);
                break;
            }
            if tile.is_building() {
                apply_damage(board, nxu, nyu, wdef.damage, result, DamageSource::Weapon);
                break;
            }
            if board.unit_at(nxu, nyu).is_some() {
                apply_damage(board, nxu, nyu, wdef.damage, result, DamageSource::Weapon);
                if wdef.push == PushDir::Forward {
                    apply_push(board, nxu, nyu, opp, result);
                }
                break;
            }
        }
    }
}

// ── Artillery ────────────────────────────────────────────────────────────────

fn sim_artillery(board: &mut Board, weapon_id: WId, wdef: &WeaponDef, ax: u8, ay: u8, tx: u8, ty: u8, attack_dir: Option<usize>, result: &mut ActionResult) {
    let center_occupied_at_impact = board.unit_at(tx, ty).is_some();
    let center_blocked_at_impact = board.is_blocked(tx, ty, false);
    let rockthrow_defer_center_death_effects = weapon_id == WId::RangedRockthrow
        && matches!(wdef.push, PushDir::Perpendicular);
    let center_volatile_idx = if rockthrow_defer_center_death_effects {
        board.unit_at(tx, ty).and_then(|idx| {
            let u = &board.units[idx];
            if u.is_enemy() && u.hp > 0 && u.is_volatile_vek() {
                Some(idx)
            } else {
                None
            }
        })
    } else {
        None
    };
    let center_blast_idx = if rockthrow_defer_center_death_effects
        && (board.blast_psion || board.boss_psion)
    {
        board.unit_at(tx, ty).and_then(|idx| {
            let u = &board.units[idx];
            let tname = u.type_name_str();
            if u.receives_psion_aura() && u.hp > 0
                && tname != "Jelly_Explode1"
                && tname != "Jelly_Boss"
            {
                Some(idx)
            } else {
                None
            }
        })
    } else {
        None
    };
    let mut deferred_center_volatile_decay = false;
    let mut deferred_center_blast_explosion = false;

    // Center damage
    if wdef.aoe_center() {
        if center_volatile_idx.is_some() || center_blast_idx.is_some() {
            apply_damage_core(board, tx, ty, wdef.damage, result, DamageSource::Weapon);
            deferred_center_volatile_decay = center_volatile_idx
                .map(|idx| board.units[idx].hp <= 0)
                .unwrap_or(false);
            deferred_center_blast_explosion = center_blast_idx
                .map(|idx| board.units[idx].hp <= 0)
                .unwrap_or(false);
        } else {
            apply_direct_weapon_damage(board, tx, ty, wdef.damage, wdef, result);
        }
    }

    // Apply status effects to center tile (fire, freeze, smoke, shield, acid)
    apply_weapon_status_with_impact_occupancy(
        board, tx, ty, wdef, center_occupied_at_impact,
    );

    // Smoke-behind-shooter: Rocket Artillery (Ranged_Rocket) places a single
    // smoke tile one step opposite the shot direction from the shooter's
    // position. If behind-tile is off-board (shooter on edge), skip silently —
    // not an error, just no smoke placed. Smoke replaces fire on the tile
    // (mirrors standard smoke semantics in apply_weapon_status).
    if wdef.smoke_behind_shooter() {
        if let Some(dir) = attack_dir {
            let (ddx, ddy) = DIRS[dir];
            let bx = ax as i8 - ddx;
            let by = ay as i8 - ddy;
            if in_bounds(bx, by) {
                place_smoke(board, bx as u8, by as u8);
            }
        }
    }

    // Fire-behind-shooter: Vulcan Artillery Backburn upgrade lights the tile
    // one step opposite the shot direction from the shooter's position.
    if wdef.fire_behind_shooter() {
        if let Some(dir) = attack_dir {
            let (ddx, ddy) = DIRS[dir];
            let bx = ax as i8 - ddx;
            let by = ay as i8 - ddy;
            if in_bounds(bx, by) {
                apply_weapon_status(board, bx as u8, by as u8, wdef);
            }
        }
    }

    // Center-tile push (mirrors projectile: status BEFORE push so the unit
    // picks up fire/smoke on the source tile before moving). Without this,
    // artillery with Forward/Backward push (e.g. Ranged_Rocket) fails to move
    // the center target, causing building-bump desyncs.
    //
    // PushDir::Perpendicular: artillery like the Rock Accelerator pushes the
    // two tiles adjacent to the destination perpendicular to the firing axis
    // (east+west when firing north, north+south when firing east). Previously
    // unhandled — the sim silently dropped both side pushes, predicting
    // static bystanders that actually got flung one tile.
    if let Some(dir) = attack_dir {
        match wdef.push {
            PushDir::Forward if wdef.aoe_center()  => {
                if is_rocket_artillery(weapon_id) {
                    apply_rocket_center_push(board, tx, ty, dir, result);
                } else if wdef.no_edge_bump_direct_push() {
                    apply_push_with_policy(board, tx, ty, dir, result, NO_EDGE_BUMP_PUSH_POLICY);
                } else {
                    apply_push(board, tx, ty, dir, result);
                }
            }
            PushDir::Backward if wdef.aoe_center() => {
                if wdef.no_edge_bump_direct_push() {
                    apply_push_with_policy(board, tx, ty, opposite_dir(dir), result, NO_EDGE_BUMP_PUSH_POLICY);
                } else {
                    apply_push(board, tx, ty, opposite_dir(dir), result);
                }
            }
            PushDir::Perpendicular => {
                // Two side tiles outward. Perpendicular directions are
                // (dir + 1) % 4 and (dir + 3) % 4; each side pushes outward
                // (away from the destination tile).
                let left = (dir + 1) % 4;
                let right = (dir + 3) % 4;
                let (ldx, ldy) = DIRS[left];
                let (rdx, rdy) = DIRS[right];
                let lx = tx as i8 + ldx;
                let ly = ty as i8 + ldy;
                let rx = tx as i8 + rdx;
                let ry = ty as i8 + rdy;
                if in_bounds(lx, ly) {
                    apply_push(board, lx as u8, ly as u8, left, result);
                }
                if in_bounds(rx, ry) {
                    apply_push(board, rx as u8, ry as u8, right, result);
                }
            }
            _ => {}
        }
    }

    if deferred_center_volatile_decay {
        apply_volatile_decay(board, tx, ty, result, 0);
    }
    if deferred_center_blast_explosion {
        apply_death_explosion(board, tx, ty, result, 0);
    }

    // Rock Accelerator leaves a neutral boulder on an empty target tile after
    // impact. The pre-impact blocked check prevents replacing mountains,
    // buildings, units, wrecks, or deadly terrain cleared by the shot.
    if weapon_id == WId::RangedRockthrow && !center_blocked_at_impact {
        spawn_rock_thrown(board, tx, ty);
    }

    // Behind tile damage (Old Earth Artillery)
    if wdef.aoe_behind() {
        if let Some(dir) = attack_dir {
            let (ddx, ddy) = DIRS[dir];
            let bx = tx as i8 + ddx;
            let by = ty as i8 + ddy;
            if in_bounds(bx, by) {
                let occupied_at_impact = board.unit_at(bx as u8, by as u8).is_some();
                apply_direct_weapon_damage(board, bx as u8, by as u8, wdef.damage, wdef, result);
                apply_weapon_status_with_impact_occupancy(
                    board, bx as u8, by as u8, wdef, occupied_at_impact,
                );
            }
        }
    }

    // Adjacent tile effects (push outward).
    //
    // Status effects (Fire/Smoke/Acid/Freeze/Shield) are applied to the
    // CENTER tile only — see the `apply_weapon_status(board, tx, ty, wdef)`
    // call earlier in this function. Adjacent tiles take damage_outer +
    // push only. Lua confirms this for Vulcan Artillery (Ranged_Ignite,
    // weapons_ranged.lua:305): the SkillEffect adds Fire (`iFire = 1`) at
    // the center tile and `iPush = dir, damage = 0` at each cardinal-
    // adjacent tile, with NO Fire status on the adjacents. In-game tooltip
    // for Vulcan reads "Light THE TARGET on Fire and push adjacent tiles" —
    // emphasis on "the target", not "5 tiles". Verified zero other Artillery
    // weapons combine AOE_ADJACENT with a status flag (FIRE/ACID/FREEZE/
    // SMOKE/SHIELD/WEB), so removing the call here has no other regressions.
    if wdef.aoe_adjacent() {
        for (i, &(dx, dy)) in DIRS.iter().enumerate() {
            let nx = tx as i8 + dx;
            let ny = ty as i8 + dy;
            if !in_bounds(nx, ny) { continue; }
            apply_direct_weapon_damage(board, nx as u8, ny as u8, wdef.damage_outer, wdef, result);
            if wdef.push == PushDir::Outward {
                if wdef.no_edge_bump_adjacent_push() && wdef.damage_outer == 0 {
                    let bx = nx + dx;
                    let by = ny + dy;
                    if !in_bounds(bx, by) { continue; }
                }
                apply_push(board, nx as u8, ny as u8, i, result);
            }
        }
    }

    // AoE perpendicular: hit two tiles flanking the target perpendicular to
    // firing direction. Used by SnowBossAtk / SnowartAtk family — Lua
    // SnowartAtk1:GetSkillEffect (weapons_snow.lua:120-135) damages
    // p2 + p2+DIR_VECTORS[(dir+1)%4] + p2+DIR_VECTORS[(dir-1)%4]. Each tile
    // takes `wdef.damage`. Status effects (apply_weapon_status) propagate to
    // the side tiles too. Mirrors the projectile-arm AOE_PERP handler in
    // enemy.rs:660-690 (Alpha Centipede's Corrosive Vomit).
    if wdef.aoe_perpendicular() {
        if let Some(dir) = attack_dir {
            for &perp in &[(dir + 1) % 4, (dir + 3) % 4] {
                let (pdx, pdy) = DIRS[perp];
                let px = tx as i8 + pdx;
                let py = ty as i8 + pdy;
                if !in_bounds(px, py) { continue; }
                let occupied_at_impact = board.unit_at(px as u8, py as u8).is_some();
                apply_direct_weapon_damage(board, px as u8, py as u8, wdef.damage, wdef, result);
                apply_weapon_status_with_impact_occupancy(
                    board, px as u8, py as u8, wdef, occupied_at_impact,
                );
            }
        }
    }
}

fn sim_arachnoid_injector(
    board: &mut Board,
    weapon_id: WId,
    wdef: &WeaponDef,
    ax: u8,
    ay: u8,
    tx: u8,
    ty: u8,
    attack_dir: Option<usize>,
    result: &mut ActionResult,
) {
    let target_before = board.unit_at(tx, ty);
    let spawn_allowed = target_before
        .map(|idx| !board.units[idx].is_mech())
        .unwrap_or(false);

    sim_artillery(board, weapon_id, wdef, ax, ay, tx, ty, attack_dir, result);

    if !spawn_allowed {
        return;
    }
    let Some(idx) = target_before else {
        return;
    };
    if board.units[idx].hp > 0 {
        return;
    }

    // The engine replaces the killed target with the Arachnoid pawn. Dead
    // units remain in Rust's fixed unit array for collision replay, so move
    // this corpse off-board before spawning or its wreck would falsely block
    // the new friendly unit and the vacated tile later in the same turn.
    board.units[idx].x = 8;
    board.units[idx].y = 8;
    let acid_attack = arachnoid_injector_spawns_acid_attack(weapon_id);
    spawn_arachnoid(board, tx, ty, acid_attack, result);
}

// ── Self AoE ─────────────────────────────────────────────────────────────────

fn apply_mass_shift_tile(
    board: &mut Board,
    x: u8,
    y: u8,
    dir: usize,
    is_self: bool,
    wdef: &WeaponDef,
    result: &mut ActionResult,
) {
    if let Some(idx) = board.unit_at(x, y) {
        if (is_self && wdef.shield_self())
            || (!is_self && wdef.shield_allies() && board.units[idx].is_player())
        {
            board.units[idx].set_shield(true);
        }
    }
    apply_damage(board, x, y, wdef.damage, result, DamageSource::Weapon);
    apply_push(board, x, y, dir, result);
}

fn sim_mass_shift(
    board: &mut Board,
    ax: u8,
    ay: u8,
    wdef: &WeaponDef,
    dir: usize,
    result: &mut ActionResult,
) {
    let (fdx, fdy) = DIRS[dir];
    let side_a = (dir + 1) % 4;
    let side_b = (dir + 3) % 4;
    let back = opposite_dir(dir);
    let (adx, ady) = DIRS[side_a];
    let (bdx, bdy) = DIRS[side_b];
    let (rdx, rdy) = DIRS[back];

    let front = (ax as i8 + fdx, ay as i8 + fdy);
    if in_bounds(front.0, front.1) {
        apply_mass_shift_tile(board, front.0 as u8, front.1 as u8, dir, false, wdef, result);
    }

    apply_mass_shift_tile(board, ax, ay, dir, true, wdef, result);

    let side_a_tile = (ax as i8 + adx, ay as i8 + ady);
    if in_bounds(side_a_tile.0, side_a_tile.1) {
        apply_mass_shift_tile(
            board,
            side_a_tile.0 as u8,
            side_a_tile.1 as u8,
            dir,
            false,
            wdef,
            result,
        );
    }

    let side_b_tile = (ax as i8 + bdx, ay as i8 + bdy);
    if in_bounds(side_b_tile.0, side_b_tile.1) {
        apply_mass_shift_tile(
            board,
            side_b_tile.0 as u8,
            side_b_tile.1 as u8,
            dir,
            false,
            wdef,
            result,
        );
    }

    let rear = (ax as i8 + rdx, ay as i8 + rdy);
    if in_bounds(rear.0, rear.1) {
        apply_mass_shift_tile(board, rear.0 as u8, rear.1 as u8, dir, false, wdef, result);
    }
}

fn self_aoe_target_in_area(ax: u8, ay: u8, target_x: u8, target_y: u8) -> bool {
    if target_x >= 8 || target_y >= 8 {
        return false;
    }
    let dx = (target_x as i8 - ax as i8).abs();
    let dy = (target_y as i8 - ay as i8).abs();
    dx + dy <= 1
}

fn sim_self_aoe(board: &mut Board, ax: u8, ay: u8, wdef: &WeaponDef, result: &mut ActionResult) {
    for (i, &(dx, dy)) in DIRS.iter().enumerate() {
        let nx = ax as i8 + dx;
        let ny = ay as i8 + dy;
        if !in_bounds(nx, ny) { continue; }
        let occupied_at_impact = board.unit_at(nx as u8, ny as u8).is_some();
        apply_damage(board, nx as u8, ny as u8, wdef.damage, result, DamageSource::Weapon);
        match wdef.push {
            PushDir::Outward => {
                let bx = nx + dx;
                let by = ny + dy;
                if !(wdef.no_edge_bump_adjacent_push() && wdef.damage == 0 && !in_bounds(bx, by)) {
                    apply_push(board, nx as u8, ny as u8, i, result);
                }
            }
            PushDir::Inward => apply_push(board, nx as u8, ny as u8, opposite_dir(i), result),
            _ => {}
        }
        apply_weapon_status_with_impact_occupancy(
            board, nx as u8, ny as u8, wdef, occupied_at_impact,
        );
    }
    if wdef.shield_self() {
        if let Some(idx) = board.unit_at(ax, ay) {
            board.units[idx].set_shield(true);
        }
    }
}

fn apply_trapped_death_damage(
    board: &mut Board,
    x: u8,
    y: u8,
    result: &mut ActionResult,
    damage_building: bool,
) {
    let mut killed_enemy_idx = None;
    let mut killed_enemy_uid = 0u16;
    let mut volatile = false;
    let mut death_explosion = false;

    if let Some(uidx) = board.unit_at(x, y) {
        let unit = &mut board.units[uidx];
        if unit.hp > 0 {
            let prev_hp = unit.hp;
            let tname = unit.type_name_str().to_string();
            let is_enemy = unit.is_enemy();
            let is_player_mech = unit.is_player() && unit.is_mech();
            let has_acid = unit.acid();
            volatile = is_enemy && unit.is_volatile_vek();
            death_explosion = is_enemy
                && (board.blast_psion || board.boss_psion)
                && unit.receives_psion_aura()
                && tname != "Jelly_Explode1"
                && tname != "Jelly_Boss";
            let mission_counted = is_enemy && !unit.minor();
            killed_enemy_uid = unit.uid;

            unit.hp = 0;
            unit.set_shield(false);
            unit.set_frozen(false);

            if is_enemy {
                result.record_enemy_kill(mission_counted);
                result.enemy_damage_dealt += prev_hp as i32;
                killed_enemy_idx = Some(uidx);
            } else if is_player_mech {
                result.mechs_killed += 1;
                result.mech_damage_taken += prev_hp as i32;
            }

            if has_acid {
                let terrain = board.tile(x, y).terrain;
                if !terrain.is_deadly_ground() || terrain == Terrain::Water {
                    leave_acid_pool_on_death(board, x, y);
                }
            }
        }
    }

    if let Some(idx) = killed_enemy_idx {
        on_enemy_death(board, idx, result);
        break_web_from(board, killed_enemy_uid);
        if volatile {
            apply_volatile_decay(board, x, y, result, 0);
        }
        if death_explosion {
            apply_death_explosion(board, x, y, result, 0);
        }
    }

    if board.tile(x, y).is_building() {
        if !damage_building {
            return;
        }
        if thaw_frozen_building(board, x, y, result) {
            return;
        }
        let idx = xy_to_idx(x, y) as u64;
        let is_unique = (board.unique_buildings & (1u64 << idx)) != 0;
        let tile = board.tile_mut(x, y);
        if tile.building_hp > 0 {
            let lost = tile.building_hp;
            tile.building_hp = 0;
            if !is_unique {
                tile.terrain = Terrain::Rubble;
            }
            result.buildings_damaged += lost as i32;
            result.grid_damage += lost as i32;
            result.buildings_lost += 1;
            board.grid_power = board.grid_power.saturating_sub(lost);
        }
        return;
    }

    let terrain = board.tile(x, y).terrain;
    match terrain {
        Terrain::Mountain => {
            let tile = board.tile_mut(x, y);
            if tile.building_hp > 0 {
                tile.building_hp = tile.building_hp.saturating_sub(1);
                if tile.building_hp == 0 {
                    tile.terrain = Terrain::Rubble;
                }
            }
        }
        Terrain::Ice => {
            if board.tile(x, y).cracked() {
                board.tile_mut(x, y).terrain = Terrain::Water;
                board.tile_mut(x, y).set_cracked(false);
            } else {
                board.tile_mut(x, y).set_cracked(true);
            }
        }
        Terrain::Ground => {
            if board.tile(x, y).cracked() {
                board.tile_mut(x, y).terrain = Terrain::Chasm;
                board.tile_mut(x, y).set_cracked(false);
            }
        }
        Terrain::Forest => {
            board.tile_mut(x, y).set_on_fire(true);
        }
        Terrain::Sand => {
            board.tile_mut(x, y).terrain = Terrain::Ground;
            board.tile_mut(x, y).set_smoke(true);
        }
        _ => {}
    }
}

fn sim_trapped_explode(board: &mut Board, attacker_idx: usize, result: &mut ActionResult) {
    let ax = board.units[attacker_idx].x;
    let ay = board.units[attacker_idx].y;
    apply_trapped_death_damage(board, ax, ay, result, true);

    for &(dx, dy) in &DIRS {
        let nx = ax as i8 + dx;
        let ny = ay as i8 + dy;
        if !in_bounds(nx, ny) { continue; }
        let tx = nx as u8;
        let ty = ny as u8;
        if board.tile(tx, ty).is_building() {
            continue;
        }
        apply_trapped_death_damage(board, tx, ty, result, false);
    }
}

// ── Pull / Swap ──────────────────────────────────────────────────────────────

fn sim_pull_or_swap(board: &mut Board, attacker_idx: usize, wdef: &WeaponDef, tx: u8, ty: u8, attack_dir: Option<usize>, result: &mut ActionResult) {
    if wdef.weapon_type == WeaponType::Swap {
        if tx >= 8 || ty >= 8 {
            return;
        }
        let (ax, ay) = (board.units[attacker_idx].x, board.units[attacker_idx].y);
        let dist = (tx as i8 - ax as i8).unsigned_abs()
            + (ty as i8 - ay as i8).unsigned_abs();
        let min_r = wdef.range_min.max(1);
        let max_r = if wdef.range_max == 0 { 8 } else { wdef.range_max };
        if dist < min_r
            || dist > max_r
            || cardinal_direction(ax, ay, tx, ty).is_none()
        {
            return;
        }
        if let Some(target_idx) = board.unit_at(tx, ty) {
            // Stable/Massive neutrals (e.g. Dam_Pawn) are immune to swap.
            // Mechs are always swap-eligible regardless of pushable flag.
            if !board.units[target_idx].pushable() && !board.units[target_idx].is_mech() {
                return;
            }
            // Swap positions
            board.units[target_idx].x = ax;
            board.units[target_idx].y = ay;
            board.units[attacker_idx].x = tx;
            board.units[attacker_idx].y = ty;
            // Landing effects on BOTH swapped units: terrain death (water/
            // lava/chasm), fire pickup, ACID pickup, mine triggers,
            // teleporter-pad relocation. Per Lua weapons_science.lua:216,
            // Science_Swap.GetSkillEffect routes through AddTeleport which
            // is move-classed: each swapped unit lands on its destination
            // and triggers the standard tile-landing pipeline. Without
            // this the solver was blind to the Swap Mech's primary kill
            // mode ("swap a Vek into water/chasm/lava for a free kill").
            // Order target→attacker matches push-chain ordering: the
            // "other" unit resolves landing first.
            apply_landing_effects(board, target_idx, result);
            apply_landing_effects(board, attacker_idx, result);
        } else {
            // Teleport to empty flyer-passable tile (no swap partner). Lua:
            // when destination has no pawn, AddTeleport fires once with the
            // attacker as the only relocated unit. Landing effects still
            // apply — useful for the Swap Mech (Flying) escaping ACID/fire
            // by teleporting to clear ground.
            board.units[attacker_idx].x = tx;
            board.units[attacker_idx].y = ty;
            apply_landing_effects(board, attacker_idx, result);
        }
        return;
    }

    // Pull: move target toward attacker.
    //
    // Two modes, distinguished by the FULL_PULL flag:
    //   - default (1-tile):   Science_Pullmech "Attraction Pulse" — apply_push
    //                         once toward the attacker.
    //   - FULL_PULL:          Brute_Grapple "Grappling Hook" and
    //                         Science_Gravwell "Grav Well" drag the target
    //                         all the way to the tile adjacent to the mech
    //                         (or until blocked: another unit, mountain,
    //                         building, edge, or a death by terrain mid-pull).
    //
    // The pull stops naturally at adjacency: the next push step would target
    // the mech's own tile, and the mech itself is a blocker — apply_push
    // would then deal bump damage to BOTH the target and the mech, which is
    // not what Grappling Hook / Grav Well do per the wiki ("not able to pull
    // enemies into the Gravity Mech for bump damage"). So FULL_PULL halts
    // BEFORE the adjacency step.
    let dir = match attack_dir {
        Some(d) => d,
        None => return,
    };
    let pull_dir = opposite_dir(dir);
    let target_idx = match board.unit_at(tx, ty) {
        Some(idx) => idx,
        None => {
            // No pawn at the target tile.
            //
            // Per Lua weapons_brute.lua:339-389 (Brute_Grapple:GetSkillEffect),
            // when the targeted tile has no pawn but IS PATH_PROJECTILE-blocked
            // (mountain or intact building), the mech itself charges along the
            // line and stops at the tile adjacent to the obstacle:
            //   ret:AddCharge(Board:GetSimplePath(p1, target - DIR_VECTORS[direction]), FULL_DELAY)
            // The path between mech and (target - dir) is guaranteed unblocked
            // because the projectile loop stopped at `target` as the FIRST
            // PATH_PROJECTILE blocker.
            //
            // This branch is FULL_PULL-only. Science_Pullmech (1-tile pull,
            // no FULL_PULL) and Science_Gravwell's Lua are not Brute_Grapple
            // and don't have a self-charge effect — Gravwell's Lua just
            // AddArtillery's an air-push at p2; if p2 is empty, it's a no-op.
            if !wdef.full_pull() {
                return;
            }
            let tile = board.tile(tx, ty);
            let is_blocker = tile.terrain == Terrain::Mountain || tile.is_building();
            if !is_blocker {
                // Empty tile (no pawn, no terrain block). Lua's targeting
                // predicate filters such tiles out (projectile loop only stops
                // at PATH_PROJECTILE-blocked tiles). If we somehow reached
                // here, no-op rather than self-charge into a vacant tile.
                return;
            }
            let (dx, dy) = DIRS[dir];
            let stop_x = tx as i8 - dx;
            let stop_y = ty as i8 - dy;
            // The stop tile is `target - dir`. If that's the mech's own tile
            // (target was at distance 1 from mech), nothing to do — the mech
            // is already there. Lua's GetTargetArea requires Manhattan > 1 so
            // this is an over-cautious guard.
            let (ax, ay) = (board.units[attacker_idx].x, board.units[attacker_idx].y);
            if stop_x as u8 == ax && stop_y as u8 == ay {
                return;
            }
            // Move the mech to the tile adjacent to the obstacle.
            board.units[attacker_idx].x = stop_x as u8;
            board.units[attacker_idx].y = stop_y as u8;
            // Teleporter pad: mech may land on a pad at the stop tile.
            apply_teleport_on_land(board, attacker_idx);
            let _ = result; // no damage from self-charge
            return;
        }
    };
    if !board.units[target_idx].pushable() {
        return;
    }

    if !wdef.full_pull() {
        // Single-step pull (Attraction Pulse): unchanged behavior.
        apply_push(board, tx, ty, pull_dir, result);
        return;
    }

    // FULL_PULL loop. Re-fetch target position each iteration since
    // apply_push mutates it. Stop when:
    //   - target is adjacent to the mech (next step would land on the mech),
    //   - the previous push didn't move the target (bumped into a blocker
    //     or died from terrain — apply_push handles bump damage / death
    //     internally, including frozen-thaw, web-break, fire/acid, mines),
    //   - target's HP fell to 0 mid-pull (water/chasm/lava/mine/bump kill).
    //
    // Bound the loop at 8 (board diameter) as a safety guard against any
    // future apply_push regression that doesn't move and doesn't bump.
    let (ax, ay) = (board.units[attacker_idx].x, board.units[attacker_idx].y);
    for _ in 0..8 {
        let (cx, cy) = (board.units[target_idx].x, board.units[target_idx].y);
        // Already adjacent to the mech → no further pull (no movement, no bump).
        if (cx as i16 - ax as i16).abs() + (cy as i16 - ay as i16).abs() <= 1 {
            break;
        }
        apply_push(board, cx, cy, pull_dir, result);
        // Bail if the target died (terrain kill, mine, bump fatal).
        if board.units[target_idx].hp <= 0 {
            break;
        }
        // Bail if the target didn't move (bumped against blocker / mountain /
        // building / edge — apply_push has already applied the bump damage).
        let (nx, ny) = (board.units[target_idx].x, board.units[target_idx].y);
        if nx == cx && ny == cy {
            break;
        }
    }
}

// ── Charge ───────────────────────────────────────────────────────────────────

fn sim_charge(board: &mut Board, attacker_idx: usize, weapon_id: WId, wdef: &WeaponDef, attack_dir: Option<usize>, result: &mut ActionResult) {
    let dir = match attack_dir {
        Some(d) => d,
        None => return,
    };

    let (dx, dy) = DIRS[dir];
    let ax = board.units[attacker_idx].x;
    let ay = board.units[attacker_idx].y;

    let mut last_free = (ax, ay);
    let mut hit: Option<(u8, u8)> = None;
    // Track tiles the charger passes through, in order. Used to apply the
    // FIRE-flag fire trail below (currently only BeetleAtkB Flaming
    // Abdomen has CHARGE+FIRE — Brute_Beetle Ramming Engines is FLYING_CHARGE
    // only, no fire). Final resting tile (== last_free) is excluded per the
    // in-game rule.
    let mut path: Vec<(u8, u8)> = Vec::new();

    for i in 1..8i8 {
        let nx = ax as i8 + dx * i;
        let ny = ay as i8 + dy * i;
        if !in_bounds(nx, ny) { break; }
        let nxu = nx as u8;
        let nyu = ny as u8;

        let tile = board.tile(nxu, nyu);
        if tile.terrain == Terrain::Mountain { break; }
        if tile.is_building() { hit = Some((nxu, nyu)); break; }
        if charge_terrain_blocks(weapon_id, wdef, tile.terrain) { break; }
        if board.unit_at(nxu, nyu).is_some() { hit = Some((nxu, nyu)); break; }

        path.push((nxu, nyu));
        last_free = (nxu, nyu);
    }

    // Move attacker to last free tile
    board.units[attacker_idx].x = last_free.0;
    board.units[attacker_idx].y = last_free.1;

    // FIRE-trail: charge weapons with the FIRE flag (BeetleAtkB Flaming
    // Abdomen — Beetle Leader boss) ignite every tile passed through,
    // EXCLUDING the final resting tile (where the charger ends up). The
    // hit tile gets fire via apply_weapon_status below; the start tile is
    // not "passed" (charger was already there).
    //
    // Mirrors the tile-effects pattern in apply_weapon_status: fire
    // replaces smoke. Charger's own tile never gets fire.
    if wdef.fire() && path.len() >= 2 {
        let trail_len = path.len() - 1; // exclude last_free
        for i in 0..trail_len {
            let (tx, ty) = path[i];
            let tile = board.tile_mut(tx, ty);
            tile.set_smoke(false);
            tile.set_on_fire(true);
        }
    }

    // Teleporter pad: the charger may land on a pad. Fire BEFORE applying
    // damage to the hit target, because the self-damage block below uses
    // the charger's post-teleport position (self_damage should hit where
    // the mech actually ends up).
    apply_teleport_on_land(board, attacker_idx);

    // Damage hit target. Self-damage is only taken on impact (empty-tile
    // charges deal no recoil — see outer simulate() for the Charge skip).
    if let Some((hx, hy)) = hit {
        let distance = (hx as i8 - ax as i8).unsigned_abs()
            + (hy as i8 - ay as i8).unsigned_abs();
        let kills_before = result.enemies_killed;
        let occupied_at_impact = board.unit_at(hx, hy).is_some();
        let defer_death_explosion = wdef.damage > 0 && wdef.push == PushDir::Forward;
        let deferred_death_explosion = if defer_death_explosion {
            apply_damage_defer_death_explosion(
                board, hx, hy, wdef.damage, result, DamageSource::Weapon,
            )
        } else {
            apply_damage(board, hx, hy, wdef.damage, result, DamageSource::Weapon);
            None
        };
        apply_weapon_status_with_impact_occupancy(
            board, hx, hy, wdef, occupied_at_impact,
        ); // status BEFORE push
        if wdef.push == PushDir::Forward {
            let policy = if matches!(weapon_id, WId::PrimePunchmechA | WId::PrimePunchmechAB) {
                DASH_PUNCH_PUSH_POLICY
            } else {
                DEFAULT_PUSH_POLICY
            };
            apply_push_with_policy(board, hx, hy, dir, result, policy);
        }
        if let Some(idx) = deferred_death_explosion {
            let ex = board.units[idx].x;
            let ey = board.units[idx].y;
            apply_death_explosion(board, ex, ey, result, 0);
        }
        if wdef.self_damage > 0 {
            let ax = board.units[attacker_idx].x;
            let ay = board.units[attacker_idx].y;
            apply_damage(board, ax, ay, wdef.self_damage, result, DamageSource::SelfDamage);
        }
        if matches!(weapon_id, WId::PrimePunchmechA | WId::PrimePunchmechAB)
            && distance >= 5
            && result.enemies_killed > kills_before
        {
            result.events.push(format!(
                "achievement_ramming_speed_dash_punch_kill:distance:{}:target:{}:{}",
                distance, hx, hy
            ));
        }
    }
}

fn charge_terrain_blocks(weapon_id: WId, wdef: &WeaponDef, terrain: Terrain) -> bool {
    if wdef.flying_charge() {
        return false;
    }
    if matches!(weapon_id, WId::PrimePunchmechA | WId::PrimePunchmechAB) {
        return terrain == Terrain::Chasm;
    }
    terrain.is_deadly_ground()
}

// ── Leap ─────────────────────────────────────────────────────────────────────

fn leap_landing_illegal_reason(
    board: &Board,
    attacker_idx: usize,
    weapon_id: WId,
    tx: u8,
    ty: u8,
) -> Option<&'static str> {
    if tx >= 8 || ty >= 8 {
        return Some("out_of_bounds");
    }
    if weapon_id == WId::PrimeLeap && board.units[attacker_idx].web() {
        return Some("webbed");
    }
    let old_x = board.units[attacker_idx].x;
    let old_y = board.units[attacker_idx].y;
    if tx != old_x && ty != old_y {
        return Some("off_axis");
    }

    let landing = board.tile(tx, ty);
    if landing.terrain == Terrain::Chasm {
        return Some("chasm");
    }
    if !board.units[attacker_idx].flying() && landing.terrain == Terrain::Water {
        return Some("water");
    }
    if !board.units[attacker_idx].flying() && landing.terrain == Terrain::Lava {
        return Some("lava");
    }
    let aerial_bombs = matches!(
        weapon_id,
        WId::BruteJetmech
            | WId::BruteJetmechA
            | WId::BruteJetmechB
            | WId::BruteJetmechAB
    );
    if aerial_bombs && landing.terrain == Terrain::Water {
        return Some("water");
    }
    if aerial_bombs && landing.terrain == Terrain::Lava {
        return Some("lava");
    }
    if landing.terrain == Terrain::Mountain {
        return Some("mountain");
    }
    if landing.terrain == Terrain::Building {
        return Some("building");
    }
    if board.wreck_at(tx, ty) {
        return Some("wreck");
    }

    let same_tile = tx == board.units[attacker_idx].x
        && ty == board.units[attacker_idx].y;
    if !same_tile && board.unit_at(tx, ty).is_some() {
        return Some("unit");
    }

    None
}

fn sim_leap(board: &mut Board, attacker_idx: usize, weapon_id: WId, wdef: &WeaponDef, tx: u8, ty: u8, result: &mut ActionResult) {
    let old_x = board.units[attacker_idx].x;
    let old_y = board.units[attacker_idx].y;

    // Target enumeration filters illegal leap landings during normal search,
    // but diagnostic callers (`score_plan`, replaying a hand-written plan)
    // can still pass an impossible landing. Treat it as an unfired action
    // instead of creating overlapping units in the projected board.
    if let Some(reason) = leap_landing_illegal_reason(board, attacker_idx, weapon_id, tx, ty) {
        result.events.push(format!(
            "illegal_leap_landing:{}:{}:{}",
            tx, ty, reason
        ));
        return;
    }

    board.units[attacker_idx].x = tx;
    board.units[attacker_idx].y = ty;

    // Apply status to landing tile. Exception: Jet_BombDrop (Aerial Bombs)
    // tooltip reads "Fly over a target, dropping an explosive smoke bomb" —
    // smoke lands on the TRANSIT tile(s), not on the landing tile. Jet_BombDrop
    // is the only SMOKE-flagged Leap weapon in the registry, so we gate on the
    // smoke flag: smoke-leaps emit smoke along the cardinal flight path
    // (tiles strictly between source and landing); other statuses, if ever
    // added to a Leap weapon, still apply at the landing tile.
    if wdef.smoke() {
        if let Some(dir) = cardinal_direction(old_x, old_y, tx, ty) {
            let (dx, dy) = DIRS[dir];
            let dist =
                (tx as i8 - old_x as i8).abs() + (ty as i8 - old_y as i8).abs();
            for step in 1..dist {
                let nx = old_x as i8 + dx * step;
                let ny = old_y as i8 + dy * step;
                if !in_bounds(nx, ny) { continue; }
                let tile = board.tile_mut(nx as u8, ny as u8);
                tile.set_on_fire(false); // smoke replaces fire (parity with apply_weapon_status)
                tile.set_smoke(true);
            }
        }
        // Note: deliberately do NOT call apply_weapon_status here — Jet_BombDrop
        // has no non-smoke status flags, and we do not want smoke at landing.
    } else {
        apply_weapon_status(board, tx, ty, wdef);
    }

    // Damage emission. Transit-damage leap weapons drop damage on each tile
    // along the cardinal flight path (strictly between source and landing),
    // not on landing-adjacent tiles:
    //   - Jet_BombDrop (Aerial Bombs): "Fly over a target, dropping an
    //     explosive smoke bomb." Uses SMOKE (damage + smoke on transit).
    //   - Brute_Bombrun (Bombing Run): "Leap over any distance dropping a
    //     bomb on each tile you pass." Uses DAMAGES_TRANSIT (damage only,
    //     no smoke).
    // Other leap weapons (Prime_Leap "Hydraulic Legs", whose tooltip reads
    // "damaging self and adjacent tiles") keep the legacy 4-cardinal-
    // neighbors-of-landing damage. Neither Jet_BombDrop nor Brute_Bombrun
    // has a push direction so the transit branch omits the push block.
    if wdef.smoke() || wdef.damages_transit() {
        if let Some(dir) = cardinal_direction(old_x, old_y, tx, ty) {
            let (dx, dy) = DIRS[dir];
            let dist =
                (tx as i8 - old_x as i8).abs() + (ty as i8 - old_y as i8).abs();
            for step in 1..dist {
                let nx = old_x as i8 + dx * step;
                let ny = old_y as i8 + dy * step;
                if !in_bounds(nx, ny) { continue; }
                if wdef.smoke() && board.tile(nx as u8, ny as u8).terrain == Terrain::Forest {
                    let tile = board.tile_mut(nx as u8, ny as u8);
                    tile.terrain = Terrain::Ground;
                    tile.set_on_fire(false);
                }
                let mut source = if wdef.smoke() && board.unit_at(nx as u8, ny as u8).is_some() {
                    // The bridge's adaptive Aerial Bombs workaround observes
                    // engine unit damage on occupied transit tiles and then
                    // applies only smoke, so terrain such as Sand is preserved.
                    DamageSource::WeaponUnitOnly
                } else {
                    DamageSource::Weapon
                };
                if wdef.smoke() && source == DamageSource::Weapon {
                    let ux = nx as u8;
                    let uy = ny as u8;
                    let idx = xy_to_idx(ux, uy);
                    let is_freeze_objective_tile =
                        board.mission_id == "Mission_FreezeBldg"
                        && (board.freeze_building_tiles & (1u64 << idx)) != 0;
                    {
                        let tile = board.tile_mut(ux, uy);
                        if is_freeze_objective_tile
                            && tile.terrain == Terrain::Building
                            && tile.building_hp > 0
                            && tile.frozen()
                        {
                            tile.set_frozen(false);
                            result.events.push(format!("building_thawed:{}:{}", ux, uy));
                            source = DamageSource::WeaponDeferredGrid;
                        }
                    }
                }
                apply_damage(board, nx as u8, ny as u8, wdef.damage, result, source);
            }
        }
    } else {
        // Damage adjacent tiles (skip source direction)
        let from_dir = direction_between(tx, ty, old_x, old_y);
        let push_policy = if weapon_id == WId::PrimeLeap {
            TRI_ROCKET_PUSH_POLICY
        } else {
            DEFAULT_PUSH_POLICY
        };
        for (i, &(dx, dy)) in DIRS.iter().enumerate() {
            if Some(i) == from_dir { continue; }
            let nx = tx as i8 + dx;
            let ny = ty as i8 + dy;
            if !in_bounds(nx, ny) { continue; }
            let hx = nx as u8;
            let hy = ny as u8;
            let pre_hit_unit = board.unit_at(hx, hy).map(|idx| {
                (
                    idx,
                    board.units[idx].hp,
                    board.units[idx].acid(),
                    board.tile(hx, hy).acid(),
                    board.units[idx].x,
                    board.units[idx].y,
                )
            });
            let damage_source = if weapon_id == WId::PrimeLeap {
                // Live Hydraulic Legs emits tile damage on landing-adjacent
                // cracked ground even when the hit kills the pawn occupying it.
                DamageSource::WeaponCracksOccupied
            } else {
                DamageSource::Weapon
            };
            apply_damage(board, hx, hy, wdef.damage, result, damage_source);
            let killed_by_hit = pre_hit_unit
                .map(|(idx, pre_hp, _, _, _, _)| pre_hp > 0 && board.units[idx].hp <= 0)
                .unwrap_or(false);
            if wdef.push == PushDir::Outward {
                apply_push_with_policy(board, hx, hy, i, result, push_policy);
            }
            if let Some((idx, _, was_acid, tile_had_acid, ox, oy)) = pre_hit_unit {
                let fx = board.units[idx].x;
                let fy = board.units[idx].y;
                if killed_by_hit && was_acid && (fx, fy) != (ox, oy) {
                    if !tile_had_acid {
                        board.tile_mut(ox, oy).flags.remove(TileFlags::ACID);
                    }
                    leave_acid_pool_on_death(board, fx, fy);
                }
            }
        }
    }

    // The wrapper resolves the landing pipeline after any Leap self-damage.
    // Live Hydraulic Legs strips Bethany's shield with recoil before ACID
    // pools on the landing tile apply, so landing effects cannot run here.
}

// ── Laser ────────────────────────────────────────────────────────────────────

fn sim_laser(board: &mut Board, ax: u8, ay: u8, wdef: &WeaponDef, attack_dir: Option<usize>, result: &mut ActionResult) {
    let dir = match attack_dir {
        Some(d) => d,
        None => return,
    };

    let (dx, dy) = DIRS[dir];
    let mut dmg = wdef.damage;

    for i in 1..8i8 {
        let nx = ax as i8 + dx * i;
        let ny = ay as i8 + dy * i;
        if !in_bounds(nx, ny) { break; }
        let nxu = nx as u8;
        let nyu = ny as u8;

        let tile = board.tile(nxu, nyu);
        // Beam stops at mountains (but hits them)
        if tile.terrain == Terrain::Mountain {
            apply_damage(board, nxu, nyu, dmg, result, DamageSource::Weapon);
            break;
        }
        // Beam stops at buildings (but hits them)
        if tile.is_building() {
            apply_damage(board, nxu, nyu, dmg, result, DamageSource::Weapon);
            break;
        }

        let skip_friendly = wdef.friendly_immune()
            && board.unit_at(nxu, nyu)
                .map(|idx| board.units[idx].is_player())
                .unwrap_or(false);
        if !skip_friendly {
            apply_damage(board, nxu, nyu, dmg, result, DamageSource::Weapon);
        }
        dmg = dmg.saturating_sub(1).max(1); // damage floor = 1
    }
}

// ── Heal All (Repair Drop) ───────────────────────────────────────────────────

/// Support_Repair (Repair Drop): ZONE_ALL heal. Restores every TEAM_PLAYER
/// pawn to max_hp, clears fire/acid/frozen, revives disabled mechs (hp<=0).
/// Multi-tile pawns (Dam_Pawn) emit one entry per occupied tile sharing a
/// uid — dedupe by uid so we heal each pawn once. Does not touch terrain
/// or buildings; a burning tile under a healed unit will re-ignite it at
/// the next turn tick.
fn sim_heal_all(board: &mut Board, _result: &mut ActionResult) {
    let mut seen: Vec<u16> = Vec::with_capacity(8);
    let storm_active = acid_storm_active(board);
    for i in 0..board.units.len() {
        let u = &board.units[i];
        if u.team != Team::Player || seen.contains(&u.uid) {
            continue;
        }
        seen.push(u.uid);
        let u = &mut board.units[i];
        u.hp = u.max_hp;
        u.set_fire(false);
        u.set_acid(false);
        u.set_frozen(false);
        if storm_active {
            u.set_acid(true);
        }
    }
}

// ── Global Push (Wind Torrent) ────────────────────────────────────────────────

/// Support_Wind (Wind Torrent): pushes every pawn one tile in the chosen
/// direction. Lua first records every initial pawn-space in direction-specific
/// scan order, then applies each `SpaceDamage(point, 0, dir)` sequentially.
/// Precomputing the target list matches that behavior: a pawn moved onto a
/// tile that was empty at cast time does not get a second, newly-created hit.
fn sim_global_push(board: &mut Board, direction: usize, result: &mut ActionResult) {
    let mut targets: Vec<(u8, u8)> = Vec::with_capacity(board.units.len());
    match direction {
        // DIR_LEFT: for i(row/y)=0..7, j(col/x)=0..7 -> Point(j,i)
        3 => {
            for y in 0..8u8 {
                for x in 0..8u8 {
                    if board.unit_at(x, y).is_some() {
                        targets.push((x, y));
                    }
                }
            }
        }
        // DIR_RIGHT: Point(7-j,i)
        1 => {
            for y in 0..8u8 {
                for x in (0..8u8).rev() {
                    if board.unit_at(x, y).is_some() {
                        targets.push((x, y));
                    }
                }
            }
        }
        // DIR_UP: Point(i,j)
        2 => {
            for x in 0..8u8 {
                for y in 0..8u8 {
                    if board.unit_at(x, y).is_some() {
                        targets.push((x, y));
                    }
                }
            }
        }
        // DIR_DOWN: Point(i,7-j)
        0 => {
            for x in 0..8u8 {
                for y in (0..8u8).rev() {
                    if board.unit_at(x, y).is_some() {
                        targets.push((x, y));
                    }
                }
            }
        }
        _ => return,
    }

    for (x, y) in targets {
        apply_push(board, x, y, direction, result);
    }
}

// ── Global Unit Effect (Detritus Contraption) ───────────────────────────────

/// Missiles_Shield / Missiles_OneDmg: affects every live non-source unit.
/// Lua's Support_Missiles:GetTargetArea excludes the source tile even when
/// FriendlyFire is true. FireWeapon also requires the clicked target to be in
/// that target area; clicking the source consumes the action but emits no
/// SpaceDamage. Lua builds the target list before applying each SpaceDamage,
/// so a unit killed by an earlier missile is not reselected and buildings are
/// untouched.
fn sim_global_unit_effect(
    board: &mut Board,
    wdef: &WeaponDef,
    source: (u8, u8),
    target: (u8, u8),
    result: &mut ActionResult,
) {
    let valid_target = board.unit_at(target.0, target.1)
        .map(|idx| {
            let unit = &board.units[idx];
            unit.hp > 0 && if wdef.targets_allies() {
                target != source
            } else {
                unit.is_enemy()
            }
        })
        .unwrap_or(false);
    if !valid_target {
        return;
    }

    let targets: Vec<(u8, u8)> = board.units.iter()
        .filter(|u| {
            u.hp > 0 && if wdef.targets_allies() {
                (u.x, u.y) != source
            } else {
                u.is_enemy()
            }
        })
        .map(|u| (u.x, u.y))
        .collect();

    for (x, y) in targets {
        if wdef.damage > 0 {
            apply_damage(board, x, y, wdef.damage, result, DamageSource::Weapon);
        }
        if wdef.shield() {
            if let Some(idx) = board.unit_at(x, y) {
                if board.units[idx].hp > 0 {
                    board.units[idx].set_shield(true);
                }
            }
        }
    }
}

// ── simulate_move / simulate_attack / simulate_action ───────────────────────
//
// Split into two phases so callers (replay.rs) can capture per-phase
// snapshots between them — the verify_action diff loop and cmd_auto_turn's
// per-sub-action verifier both consume both `post_move` and `post_attack`
// states. Existing combat-decision callers (`score_plan`, solver tree
// search, `turn_projection`) keep calling `simulate_action`, which is now
// a thin wrapper. Semantic behaviour is identical to the old monolithic
// `simulate_action`; this is purely structural.

/// Move phase only: position update, pod pickup, ACID transfer, mines,
/// fire-tile catch, teleporter pad swap, WebbEgg adjacency refresh.
pub fn simulate_move(
    board: &mut Board,
    mech_idx: usize,
    move_to: (u8, u8),
) -> ActionResult {
    let mut result = ActionResult::default();

    let old_pos = (board.units[mech_idx].x, board.units[mech_idx].y);
    board.units[mech_idx].x = move_to.0;
    board.units[mech_idx].y = move_to.1;

    apply_pod_on_land(board, mech_idx, &mut result);

    // ACID pool pickup: mech gains ACID, pool consumed
    {
        let tile = board.tile(move_to.0, move_to.1);
        if tile.acid() && tile.terrain != Terrain::Water {
            if !board.units[mech_idx].shield() {
                board.units[mech_idx].set_acid(true);
            }
            board.tile_mut(move_to.0, move_to.1).flags.remove(TileFlags::ACID);
        }
    }

    // Old Earth Mine: kills mech on arrival (bypasses shield), mine consumed
    if move_to != old_pos {
        let tile = board.tile(move_to.0, move_to.1);
        if tile.old_earth_mine() {
            board.units[mech_idx].hp = 0;
            result.mechs_killed += 1;
            board.tile_mut(move_to.0, move_to.1).set_old_earth_mine(false);
        }
    }

    // Freeze mine: freezes mech on arrival, mine consumed
    if move_to != old_pos {
        let tile = board.tile(move_to.0, move_to.1);
        if tile.freeze_mine() {
            if !board.units[mech_idx].shield() {
                board.units[mech_idx].set_frozen(true);
            } else {
                board.units[mech_idx].set_shield(false);
            }
            board.tile_mut(move_to.0, move_to.1).set_freeze_mine(false);
        }
    }

    // Fire tile: mech catches fire on arrival (if not shielded).
    // Mirrors apply_push's fire-catch logic so move and push paths agree.
    if move_to != old_pos {
        apply_fire_tile_pickup(board, mech_idx, move_to.0, move_to.1);
    }

    // Repair platform: generic Item_Repair_Mine tile. It heals by negative
    // damage and is consumed; unlike the Repair action, Lua does not set
    // explicit fire/acid/frozen removal flags.
    if move_to != old_pos {
        apply_repair_platform(board, mech_idx, &mut result);
    }

    // Teleporter pad: if the mech moved AND landed on a pad, swap with
    // partner. Only fires when move_to != old_pos — a mech that doesn't
    // move (already on a pad from deployment or prior turn) does NOT
    // re-trigger (game rule: "does not fire for units that START on a
    // pad"). Runs after mine/fire/acid so a mech that dies on a mine
    // doesn't teleport its corpse.
    if move_to != old_pos {
        apply_teleport_on_land(board, mech_idx);
    }

    board.refresh_webb_egg_grapples();

    result
}

/// Attack phase only: repair (with Frenzied Repair pushes), frozen-mech
/// early-return, weapon fire, set_active(false) on weapon use.
pub fn simulate_attack(
    board: &mut Board,
    mech_idx: usize,
    weapon_id: WId,
    target: (u8, u8),
    weapons: &WeaponTable,
) -> ActionResult {
    let mut result = ActionResult::default();

    // Smoke prevents attacks and repair. Solver enumeration normally filters
    // these out, but diagnostic score/replay can receive hand-written plans.
    if weapon_id != WId::None {
        let (sx, sy, ignores_smoke) = {
            let unit = &board.units[mech_idx];
            (unit.x, unit.y, unit.type_name_str() == "Trapped_Building")
        };
        if board.tile(sx, sy).smoke() && !ignores_smoke {
            result.events.push(format!("illegal_attack_smoke:{}:{}", sx, sy));
            return result;
        }
    }

    // Diagnostic callers can hand us targets the UI would not offer. Treat
    // them as no-ops with an explicit event instead of simulating impossible
    // effects (for example player artillery off-axis targets).
    if weapon_id != WId::None && weapon_id != WId::Repair {
        let (sx, sy) = (board.units[mech_idx].x, board.units[mech_idx].y);
        let legal_targets = crate::solver::get_weapon_targets(
            board,
            sx,
            sy,
            weapon_id,
            (sx, sy),
            weapons,
        );
        if !legal_targets.contains(&target) {
            result.events.push(format!(
                "illegal_weapon_target:{}:{}:{}",
                target.0,
                target.1,
                weapon_name(weapon_id),
            ));
            return result;
        }
    }

    // Repair
    if weapon_id == WId::Repair {
        let storm_active = acid_storm_active(board);
        let (is_repairman, rx, ry) = {
            let unit = &mut board.units[mech_idx];
            let heal: i8 = if unit.boosted() { 2 } else { 1 };
            unit.hp = unit.hp.min(unit.max_hp - heal) + heal;
            unit.set_fire(false);
            unit.set_acid(false);
            unit.set_frozen(false);
            clear_mites(unit);
            if storm_active {
                unit.set_acid(true);
            }
            unit.set_boosted(false);
            refresh_arrogant_boost(unit);
            unit.set_active(false);
            (unit.pilot_repairman(), unit.x, unit.y)
        };
        board.tile_mut(rx, ry).set_on_fire(false);
        // Harold Schmidt (Pilot_Repairman) — Frenzied Repair: push all four
        // cardinal neighbours outward. Uses `apply_push` so push chains,
        // bump-into-building damage, drown/lava kills, and terrain
        // interactions agree with every other push source in the sim.
        if is_repairman {
            for (i, &(dx, dy)) in DIRS.iter().enumerate() {
                let nx = rx as i8 + dx;
                let ny = ry as i8 + dy;
                if !in_bounds(nx, ny) { continue; }
                apply_push(board, nx as u8, ny as u8, i, &mut result);
            }
        }
        drain_pending_spider_eggs(board);
        return result;
    }

    // Frozen mech cannot attack — only repair (handled above) is allowed
    if board.units[mech_idx].frozen() {
        board.units[mech_idx].set_active(false);
        return result;
    }

    // Attack
    if weapon_id != WId::None {
        let attack_result = simulate_weapon_with(board, mech_idx, weapon_id, target.0, target.1, weapons);
        result.merge(&attack_result);
    }

    // Active flag: in-game, moving without firing leaves the mech READY
    // (the player can still attack later in the same turn). Only firing a
    // weapon consumes the mech's action. Previously we unconditionally
    // cleared active which made verify_action flag every move-only plan
    // as a desync on WallMech, pawn movement rounds, etc.
    if weapon_id != WId::None {
        board.units[mech_idx].set_active(false);
        let finisher_boost = board.units[mech_idx].pilot_chemical() && result.enemies_killed > 0;
        board.units[mech_idx].set_boosted(finisher_boost);
        refresh_arrogant_boost(&mut board.units[mech_idx]);
    }
    drain_pending_spider_eggs(board);
    result
}

/// Simulate a complete mech action: move + attack. Modifies board in-place.
/// Thin wrapper over `simulate_move` + `simulate_attack`. Existing callers
/// (score_plan, solver tree search, turn_projection) use this; replay.rs
/// uses the split helpers directly to capture mid-action snapshots.
pub fn simulate_action(
    board: &mut Board,
    mech_idx: usize,
    move_to: (u8, u8),
    weapon_id: WId,
    target: (u8, u8),
    weapons: &WeaponTable,
) -> ActionResult {
    let mut result = simulate_move(board, mech_idx, move_to);
    let attack_result = simulate_attack(board, mech_idx, weapon_id, target, weapons);
    result.merge(&attack_result);
    // Grid Defense: every grid point lost to PLAYER-phase building damage
    // (friendly fire, push-bump into building) had a `grid_defense_pct`/100
    // chance to resist. Mirrors enemy.rs::simulate_enemy_attacks line 1071,
    // but accumulates per-action because player actions are dispatched one
    // at a time through this entry point (solver.rs:853, lib.rs:110,
    // turn_projection.rs:131). Enemy phase damage is NOT routed through
    // simulate_action, so this can't double-count the enemy save.
    if result.grid_damage > 0 {
        let gd = board.grid_defense_pct as f32;
        board.player_grid_save_expected += (result.grid_damage as f32) * (gd / 100.0);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_test_board() -> Board {
        Board::default()
    }

    fn add_enemy(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8) -> usize {
        board.add_unit(Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        })
    }

    fn add_enemy_type(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8, type_name: &str) -> usize {
        let idx = add_enemy(board, uid, x, y, hp);
        board.units[idx].set_type_name(type_name);
        idx
    }

    fn add_mech(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8, weapon: WId) -> usize {
        board.add_unit(Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Player,
            weapon: crate::board::WeaponId(weapon as u16),
            flags: UnitFlags::IS_MECH | UnitFlags::ACTIVE | UnitFlags::PUSHABLE,
            move_speed: 3,
            ..Default::default()
        })
    }

    fn add_mission_ally(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8, weapon: WId, type_name: &str) -> usize {
        let idx = board.add_unit(Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Player,
            weapon: crate::board::WeaponId(weapon as u16),
            flags: UnitFlags::ACTIVE,
            move_speed: 0,
            base_move: 0,
            ..Default::default()
        });
        board.units[idx].set_type_name(type_name);
        idx
    }

    fn add_bombrock(board: &mut Board, uid: u16, x: u8, y: u8) -> usize {
        let idx = board.add_unit(Unit {
            uid,
            x,
            y,
            hp: 1,
            max_hp: 1,
            team: Team::Neutral,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });
        board.units[idx].set_type_name("BombRock");
        idx
    }

    #[test]
    fn test_viscera_nanobots_heals_unstable_self_damage_on_kill() {
        let mut board = make_test_board();
        board.viscera_nanobots_heal = 1;
        let mech = add_mech(&mut board, 1, 4, 4, 3, WId::BruteUnstable);
        let enemy = add_enemy(&mut board, 90, 4, 2, 2);

        let result = simulate_weapon(&mut board, mech, WId::BruteUnstable, 4, 2);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.units[enemy].hp, 0);
        assert_eq!(board.units[mech].hp, 3);
        assert!(result.events.iter().any(|e| e == "viscera_nanobots_heal:1:1:1"));
    }

    #[test]
    fn test_viscera_nanobots_revives_self_damaged_attacker_on_kill() {
        let mut board = make_test_board();
        board.viscera_nanobots_heal = 1;
        let mech = add_mech(&mut board, 1, 4, 4, 1, WId::BruteUnstable);
        board.units[mech].max_hp = 3;
        add_enemy(&mut board, 90, 4, 2, 2);

        let result = simulate_weapon(&mut board, mech, WId::BruteUnstable, 4, 2);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(result.mechs_killed, 0);
        assert_eq!(board.units[mech].hp, 1);
    }

    #[test]
    fn test_viscera_nanobots_no_passive_keeps_unstable_recoil_damage() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 4, 4, 3, WId::BruteUnstable);
        add_enemy(&mut board, 90, 4, 2, 2);

        let result = simulate_weapon(&mut board, mech, WId::BruteUnstable, 4, 2);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.units[mech].hp, 2);
    }

    #[test]
    fn test_unstable_cannon_direct_kill_does_not_create_acid_pool() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 4, 5, 3, WId::BruteUnstable);
        let shaman = add_enemy_type(&mut board, 422, 5, 5, 2, "Shaman1");
        board.units[shaman].set_acid(true);

        let result = simulate_weapon(&mut board, mech, WId::BruteUnstable, 5, 5);

        assert_eq!(result.enemies_killed, 1);
        assert!(board.units[shaman].hp <= 0);
        assert!(
            !board.tile(5, 5).acid(),
            "Unstable Cannon should not leave a corpse ACID pool on the direct-hit tile"
        );
    }

    #[test]
    fn test_viscera_nanobots_heals_unstable_pushback_bump_kill() {
        let mut board = make_test_board();
        board.viscera_nanobots_heal = 1;
        let mech = add_mech(&mut board, 1, 3, 3, 3, WId::BruteUnstable);
        let front = add_enemy(&mut board, 90, 3, 2, 2);
        let rear = add_enemy_type(&mut board, 91, 3, 4, 1, "Totem1");
        board.units[rear].set_acid(true);
        board.tile_mut(3, 4).terrain = Terrain::Sand;

        let result = simulate_weapon(&mut board, mech, WId::BruteUnstable, 3, 2);

        assert_eq!(result.enemies_killed, 2);
        assert_eq!(result.leech_credit_kills, 2);
        assert_eq!(board.units[front].hp, 0);
        assert_eq!(board.units[rear].hp, 0);
        assert_eq!(board.units[mech].hp, 3);
        assert!(board.tile(3, 4).acid());
        assert_eq!(board.tile(3, 4).terrain, Terrain::Ground);
        assert!(
            result.events.iter().any(|e| e == "viscera_nanobots_heal:1:2:2"),
            "pushback bump kill should add a second Nanobots heal credit"
        );
    }

    #[test]
    fn test_unstable_recoil_into_edge_does_not_bump_self_before_nanobots() {
        let mut board = make_test_board();
        board.viscera_nanobots_heal = 2;
        let mech = add_mech(&mut board, 1, 0, 5, 4, WId::BruteUnstable);
        board.units[mech].max_hp = 5;
        let enemy = add_enemy(&mut board, 90, 4, 5, 1);

        let result = simulate_weapon(&mut board, mech, WId::BruteUnstable, 1, 5);

        assert_eq!(result.enemies_killed, 1);
        assert!(board.units[enemy].hp <= 0);
        assert_eq!(
            board.units[mech].hp, 5,
            "edge recoil should not add a second self-damage event before Nanobots heals"
        );
        assert!(
            result.events.iter().any(|e| e == "viscera_nanobots_heal:1:1:2"),
            "the direct Unstable Cannon kill should produce one boosted Nanobots heal"
        );
    }

    #[test]
    fn test_unstable_killed_target_corpse_bumps_live_mech_blocker() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 2, 4, 3, WId::BruteUnstable);
        board.units[mech].max_hp = 5;
        let blob = add_enemy_type(&mut board, 890, 4, 4, 2, "BlobB");
        let nano = add_mech(&mut board, 2, 5, 4, 4, WId::ScienceAcidShot);

        let result = simulate_weapon(&mut board, mech, WId::BruteUnstable, 3, 4);

        assert_eq!(board.units[blob].hp, 0);
        assert_eq!(
            board.units[nano].hp, 3,
            "Unstable Cannon killed-target forward push should corpse-bump the live mech blocker"
        );
        assert_eq!(result.mech_damage_taken, 2);
    }

    #[test]
    fn test_unstable_dead_recoil_bumps_live_mech_before_nanobot_heal() {
        let mut board = make_test_board();
        board.viscera_nanobots_heal = 2;
        let blocker = add_mech(&mut board, 0, 6, 4, 1, WId::PrimeLeap);
        let mech = add_mech(&mut board, 1, 6, 5, 1, WId::BruteUnstable);
        board.units[mech].max_hp = 3;
        let enemy = add_enemy(&mut board, 90, 6, 6, 2);

        let result = simulate_weapon(&mut board, mech, WId::BruteUnstable, 6, 6);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.units[enemy].hp, 0);
        assert_eq!(
            board.units[blocker].hp, 0,
            "Unstable recoil still bumps the live rear blocker after self-damage drops the attacker to 0"
        );
        assert_eq!(
            board.units[mech].hp, 2,
            "Viscera Nanobots should revive/heal the attacker after the kill"
        );
        assert_eq!(
            result.mechs_killed, 1,
            "only the rear blocker remains disabled after the attacker is revived"
        );
        assert!(
            result.events.iter().any(|e| e == "viscera_nanobots_heal:1:1:2"),
            "the direct Unstable Cannon kill should produce one boosted Nanobots heal"
        );
    }

    #[test]
    fn test_viscera_nanobots_does_not_heal_hydraulic_legs_edge_bump_kill() {
        let mut board = make_test_board();
        board.viscera_nanobots_heal = 1;
        let mech = add_mech(&mut board, 1, 5, 3, 3, WId::PrimeLeap);
        board.tile_mut(6, 3).flags |= TileFlags::ACID;
        let enemy = add_enemy(&mut board, 90, 7, 3, 3);
        board.units[enemy].set_acid(true);

        let result = simulate_weapon(&mut board, mech, WId::PrimeLeap, 6, 3);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(result.leech_credit_kills, 0);
        assert_eq!(
            board.units[mech].hp, 2,
            "edge-bump kills do not count as Nanobots killing blows; only Leap recoil applies"
        );
        assert!(
            !result
                .events
                .iter()
                .any(|e| e.starts_with("viscera_nanobots_heal:")),
            "no heal event should be emitted for bump-only kills"
        );
    }

    #[test]
    fn test_hydraulic_lifter_throws_adjacent_unit_to_landing() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 3, 3, 3, WId::PrimeTcPunt);
        let enemy = add_enemy(&mut board, 90, 3, 2, 3);

        let result = simulate_weapon(&mut board, mech, WId::PrimeTcPunt, 3, 0);

        assert_eq!((board.units[enemy].x, board.units[enemy].y), (3, 0));
        assert_eq!(board.units[enemy].hp, 2);
        assert!(board.unit_at(3, 2).is_none());
        assert_eq!(result.enemy_damage_dealt, 1);
    }

    #[test]
    fn test_hydraulic_lifter_landing_damage_ignites_forest_target() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 5, 0, 4, WId::PrimeTcPuntAB);
        let enemy = add_enemy_type(&mut board, 1881, 5, 1, 5, "Firefly2");
        board.tile_mut(5, 3).terrain = Terrain::Forest;

        simulate_weapon(&mut board, mech, WId::PrimeTcPuntAB, 5, 3);

        assert_eq!((board.units[enemy].x, board.units[enemy].y), (5, 3));
        assert!(board.units[enemy].hp > 0, "target should survive to carry fire status");
        assert!(board.units[enemy].fire(), "thrown forest-landing target should catch fire");
        assert_eq!(board.tile(5, 3).terrain, Terrain::Ground);
        assert!(board.tile(5, 3).on_fire(), "landing Forest should become burning Ground");
    }

    #[test]
    fn test_tri_rocket_hits_three_tiles_in_order() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 3, 6, 3, WId::RangedCrack);
        let front = add_enemy(&mut board, 90, 3, 2, 2);
        let center = add_enemy(&mut board, 91, 3, 3, 2);
        let back = add_enemy(&mut board, 92, 3, 4, 2);

        simulate_weapon(&mut board, mech, WId::RangedCrack, 3, 3);

        assert_eq!((board.units[front].x, board.units[front].y, board.units[front].hp), (3, 1, 1));
        assert_eq!((board.units[center].x, board.units[center].y, board.units[center].hp), (3, 2, 1));
        assert_eq!((board.units[back].x, board.units[back].y, board.units[back].hp), (3, 3, 1));
    }

    #[test]
    fn test_tri_rocket_moves_acid_corpse_pool_and_bumps_following_unit() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 3, 6, 3, WId::RangedCrack);
        let center = add_enemy(&mut board, 91, 3, 3, 2);
        let back = add_enemy(&mut board, 92, 3, 4, 4);
        board.units[center].set_acid(true);

        simulate_weapon(&mut board, mech, WId::RangedCrack, 3, 3);

        assert_eq!((board.units[center].x, board.units[center].y, board.units[center].hp), (3, 2, 0));
        assert!(board.tile(3, 2).acid(), "acid corpse pool should follow the pushed corpse");
        assert!(!board.tile(3, 3).acid(), "vacated pre-push tile should not retain a new acid pool");
        assert_eq!((board.units[back].x, board.units[back].y, board.units[back].hp), (3, 3, 2));
        assert!(!board.units[back].acid(), "following unit should not pick up acid from the vacated tile");
    }

    #[test]
    fn test_tri_rocket_killed_adjacent_corpse_bumps_center_blocker() {
        let mut board = make_test_board();
        let shooter = add_mech(&mut board, 1, 0, 1, 2, WId::RangedCrack);
        let near = add_enemy(&mut board, 90, 2, 1, 1);
        let center = add_mech(&mut board, 0, 3, 1, 4, WId::PrimeTcPunt);
        let far = add_enemy(&mut board, 91, 4, 1, 3);
        let far_blocker = add_enemy(&mut board, 92, 5, 1, 3);

        simulate_weapon(&mut board, shooter, WId::RangedCrack, 3, 1);

        assert_eq!(board.units[near].hp, 0, "near missile target should die");
        assert_eq!(board.units[far].hp, 0, "far target should die after center bump");
        assert_eq!(board.units[far_blocker].hp, 2, "far blocker takes one bump");
        assert_eq!(
            (board.units[center].x, board.units[center].y, board.units[center].hp),
            (3, 1, 1),
            "center blocker takes direct, live-bump, and killed-corpse bump damage",
        );
    }

    #[test]
    fn test_tri_rocket_terrain_kill_vacated_tile_does_not_corpse_bump() {
        let mut board = make_test_board();
        let shooter = add_mech(&mut board, 1, 1, 6, 2, WId::RangedCrack);
        let center = add_enemy(&mut board, 90, 5, 6, 5);
        let back = add_enemy(&mut board, 91, 4, 6, 2);
        board.tile_mut(6, 6).set_cracked(true);

        simulate_weapon(&mut board, shooter, WId::RangedCrack, 5, 6);

        assert_eq!(board.tile(6, 6).terrain, Terrain::Chasm);
        assert_eq!(
            (board.units[center].x, board.units[center].y, board.units[center].hp),
            (6, 6, 0),
            "center target is killed after being pushed into the newly opened chasm",
        );
        assert_eq!(
            (board.units[back].x, board.units[back].y, board.units[back].hp),
            (5, 6, 1),
            "following target moves into the vacated tile without a corpse-bump from terrain death",
        );
    }

    #[test]
    fn test_tri_rocket_center_bombrock_bumps_front_without_side_explosion() {
        let mut board = make_test_board();
        let shooter = add_mech(&mut board, 1, 1, 6, 2, WId::RangedCrackB);
        let front = add_enemy_type(&mut board, 90, 5, 6, 4, "Dung2");
        let side = add_enemy_type(&mut board, 91, 4, 5, 4, "Scorpion2");
        let rock = add_bombrock(&mut board, 92, 4, 6);

        simulate_weapon(&mut board, shooter, WId::RangedCrackB, 4, 6);

        assert_eq!(
            (board.units[front].x, board.units[front].y, board.units[front].hp),
            (6, 6, 2),
            "front target takes the center BombRock corpse-bump, then the front rocket hit",
        );
        assert_eq!(
            board.units[side].hp, 4,
            "Tri-Rocket center BombRock collision should not emit a side blast",
        );
        assert!(board.units[rock].hp <= 0, "center BombRock is destroyed");
    }

    #[test]
    fn test_seismic_capacitor_cracks_adjacent_tiles_on_kill() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 3, 3, 3, WId::ScienceKoCrack);
        let enemy = add_enemy(&mut board, 90, 3, 2, 1);

        simulate_weapon(&mut board, mech, WId::ScienceKoCrack, 3, 2);

        assert!(board.units[enemy].hp <= 0);
        for (x, y) in [(3, 1), (4, 2), (3, 3), (2, 2)] {
            assert!(board.tile(x, y).cracked(), "expected crack at {},{}", x, y);
        }
        assert!(!board.tile(3, 2).cracked(), "center crack is not emitted by the live tooltip path");
    }

    #[test]
    fn test_seismic_capacitor_crack_damages_adjacent_mountain() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 5, 1, 3, WId::ScienceKoCrack);
        add_enemy(&mut board, 90, 6, 1, 1);
        board.tile_mut(6, 2).terrain = Terrain::Mountain;
        board.tile_mut(6, 2).building_hp = 2;

        simulate_weapon(&mut board, mech, WId::ScienceKoCrack, 6, 1);

        assert_eq!(board.tile(6, 2).terrain, Terrain::Mountain);
        assert_eq!(board.tile(6, 2).building_hp, 1);
    }

    #[test]
    fn test_arachnoid_injector_kill_spawns_active_arachnoid() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 10, 3, 1, 3, WId::RangedArachnoid);
        let target = add_enemy(&mut board, 11, 3, 3, 1);
        board.units[target].set_type_name("Leaper1");

        let result = simulate_weapon(&mut board, mech, WId::RangedArachnoid, 3, 3);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.units[target].hp, 0);
        assert_eq!((board.units[target].x, board.units[target].y), (8, 8));
        let spawned = board.unit_at(3, 3).expect("Arachnoid should spawn on kill tile");
        assert_eq!(board.units[spawned].team, Team::Player);
        assert_eq!(board.units[spawned].type_name_str(), "DeployUnit_Aracnoid");
        assert_eq!(board.units[spawned].weapon, WeaponId(WId::DeployUnitAracnoidAtk as u16));
        assert!(board.units[spawned].active());
        assert!(!board.wreck_at(3, 3));
    }

    #[test]
    fn test_spawned_arachnoid_attack_pushes_and_self_destructs_without_mech_loss() {
        let mut board = make_test_board();
        let arachnoid = board.add_unit(Unit {
            uid: 20,
            x: 3,
            y: 3,
            hp: 1,
            max_hp: 1,
            team: Team::Player,
            move_speed: 3,
            base_move: 3,
            flags: UnitFlags::ACTIVE | UnitFlags::PUSHABLE,
            weapon: WeaponId(WId::DeployUnitAracnoidAtk as u16),
            ..Default::default()
        });
        board.units[arachnoid].set_type_name("DeployUnit_Aracnoid");
        let target = add_enemy(&mut board, 21, 3, 4, 2);

        let result = simulate_weapon(&mut board, arachnoid, WId::DeployUnitAracnoidAtk, 3, 4);

        assert_eq!(board.units[target].hp, 1);
        assert_eq!((board.units[target].x, board.units[target].y), (3, 5));
        assert_eq!(board.units[arachnoid].hp, 0);
        assert_eq!(result.mechs_killed, 0);
    }

    #[test]
    fn test_area_shift_pushes_self_and_adjacent_tiles_in_clicked_direction() {
        let mut board = make_test_board();
        let slide = add_mech(&mut board, 30, 3, 3, 2, WId::ScienceMassShift);
        let front = add_enemy(&mut board, 31, 3, 4, 2);
        let right = add_enemy(&mut board, 32, 4, 3, 2);
        let left = add_enemy(&mut board, 33, 2, 3, 2);
        let rear = add_enemy(&mut board, 34, 3, 2, 2);

        simulate_weapon(&mut board, slide, WId::ScienceMassShift, 3, 4);

        assert_eq!((board.units[front].x, board.units[front].y), (3, 5));
        assert_eq!((board.units[slide].x, board.units[slide].y), (3, 4));
        assert_eq!((board.units[right].x, board.units[right].y), (4, 4));
        assert_eq!((board.units[left].x, board.units[left].y), (2, 4));
        assert_eq!((board.units[rear].x, board.units[rear].y), (3, 3));
    }

    #[test]
    fn test_terraformer_attack_kills_six_tile_sweep_and_sands_ground() {
        let mut board = make_test_board();
        let terraformer = add_mission_ally(&mut board, 245, 5, 3, 2, WId::TerraformerAttack, "Terraformer");
        let moth = add_enemy(&mut board, 246, 6, 3, 3);
        let blob = add_enemy(&mut board, 247, 7, 2, 1);
        let safe = add_enemy(&mut board, 248, 5, 5, 1);
        board.tile_mut(6, 3).set_smoke(true);
        board.tile_mut(6, 3).set_grass(true);
        board.tile_mut(7, 2).terrain = Terrain::Forest;
        board.tile_mut(7, 2).set_on_fire(true);
        board.tile_mut(7, 2).set_grass(true);
        board.tile_mut(7, 3).terrain = Terrain::Mountain;
        board.tile_mut(7, 3).building_hp = 2;
        board.tile_mut(7, 3).set_grass(true);

        let result = simulate_weapon(&mut board, terraformer, WId::TerraformerAttack, 6, 3);

        assert_eq!(result.enemies_killed, 2);
        assert_eq!(board.units[moth].hp, 0);
        assert_eq!(board.units[blob].hp, 0);
        assert_eq!(board.units[safe].hp, 1);
        assert_eq!(board.tile(6, 3).terrain, Terrain::Sand);
        assert!(!board.tile(6, 3).smoke());
        assert!(!board.tile(6, 3).grass());
        assert_eq!(board.tile(7, 2).terrain, Terrain::Sand);
        assert!(!board.tile(7, 2).on_fire());
        assert!(!board.tile(7, 2).grass());
        assert_eq!(board.tile(7, 3).terrain, Terrain::Mountain);
        assert!(board.tile(7, 3).grass());
    }

    #[test]
    fn test_terraformer_killing_web_source_releases_webbed_ally() {
        let mut board = make_test_board();
        let terraformer = add_mission_ally(&mut board, 245, 4, 5, 2, WId::TerraformerAttack, "Terraformer");
        let scorpion = add_enemy_type(&mut board, 302, 4, 4, 3, "Scorpion1");
        board.units[terraformer].set_web(true);
        board.units[terraformer].web_source_uid = board.units[scorpion].uid;

        let result = simulate_weapon(&mut board, terraformer, WId::TerraformerAttack, 4, 4);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.units[scorpion].hp, 0);
        assert!(!board.units[terraformer].web());
        assert_eq!(board.units[terraformer].web_source_uid, 0);
    }

    #[test]
    fn test_terraformer_clears_grass_but_preserves_acid_ground_tile() {
        let mut board = make_test_board();
        let terraformer = add_mission_ally(&mut board, 245, 4, 5, 2, WId::TerraformerAttack, "Terraformer");
        let acid_enemy = add_enemy(&mut board, 301, 5, 4, 2);
        board.units[acid_enemy].set_acid(true);
        board.tile_mut(5, 4).terrain = Terrain::Ground;
        board.tile_mut(5, 4).set_grass(true);
        board.tile_mut(4, 4).terrain = Terrain::Ground;
        board.tile_mut(4, 4).set_grass(true);

        let result = simulate_weapon(&mut board, terraformer, WId::TerraformerAttack, 4, 4);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.units[acid_enemy].hp, 0);
        assert!(board.tile(5, 4).acid());
        assert_eq!(board.tile(5, 4).terrain, Terrain::Ground);
        assert!(!board.tile(5, 4).grass());
        assert_eq!(board.tile(4, 4).terrain, Terrain::Sand);
        assert!(!board.tile(4, 4).grass());
    }

    #[test]
    fn test_disposal_attack_kills_acid_cross_and_clears_mountains() {
        let mut board = make_test_board();
        let launcher = add_mission_ally(&mut board, 260, 1, 1, 2, WId::DisposalAttack, "Disposal_Unit");
        let center = add_enemy(&mut board, 261, 4, 4, 2);
        let adjacent = add_enemy(&mut board, 262, 4, 5, 1);
        let diagonal_safe = add_enemy(&mut board, 263, 5, 5, 1);
        board.tile_mut(3, 4).terrain = Terrain::Mountain;
        board.tile_mut(3, 4).building_hp = 2;
        board.tile_mut(4, 3).terrain = Terrain::Building;
        board.tile_mut(4, 3).building_hp = 2;
        board.tile_mut(5, 4).terrain = Terrain::Forest;
        board.tile_mut(5, 4).set_on_fire(true);
        board.tile_mut(4, 3).set_smoke(true);

        let result = simulate_weapon(&mut board, launcher, WId::DisposalAttack, 4, 4);

        assert_eq!(result.enemies_killed, 2);
        assert_eq!(board.units[center].hp, 0);
        assert_eq!(board.units[adjacent].hp, 0);
        assert_eq!(board.units[diagonal_safe].hp, 1);
        assert_eq!(board.tile(3, 4).terrain, Terrain::Ground);
        assert_eq!(board.tile(3, 4).building_hp, 0);
        assert_eq!(board.tile(4, 3).terrain, Terrain::Rubble);
        assert_eq!(board.tile(4, 3).building_hp, 0);
        assert_eq!(result.buildings_lost, 1);
        assert_eq!(result.grid_damage, 2);
        assert_eq!(board.grid_power, 5);
        for (x, y) in disposal_cross_tiles(4, 4) {
            assert!(board.tile(x, y).acid(), "expected acid at ({},{})", x, y);
        }
        assert!(!board.tile(5, 4).on_fire());
        assert!(!board.tile(4, 3).smoke());
        assert!(!board.tile(5, 5).acid());
    }

    #[test]
    fn test_boosted_taurus_kills_pushed_hornet_and_explodes_from_final_tile() {
        // R.S.T. Corporate HQ, run 20260510_213059_819 m10 turn 4:
        // Fenrir/Kai's boosted Tank fired Taurus at a 2 HP Hornet. The live
        // game applied Boost (+1 damage), pushed the corpse, then resolved the
        // Psion Abomination death explosion from the corpse's final tile.
        let mut board = make_test_board();
        board.boss_psion = true;
        board.tile_mut(3, 2).terrain = Terrain::Building;
        board.tile_mut(3, 2).building_hp = 2;

        let tank = add_mech(&mut board, 1, 2, 4, 3, WId::BruteTankmech);
        board.units[tank].set_boosted(true);
        let hornet = add_enemy_type(&mut board, 710, 2, 3, 2, "Hornet1");
        let boss = add_enemy_type(&mut board, 706, 1, 2, 4, "Jelly_Boss");

        let _ = simulate_action(
            &mut board, tank, (2, 4), WId::BruteTankmech, (2, 3), &WEAPONS,
        );

        assert!(board.units[hornet].hp <= 0, "boosted Taurus kills 2 HP Hornet");
        assert_eq!((board.units[hornet].x, board.units[hornet].y), (2, 2),
            "dead pushable target is pushed before death explosion resolves");
        assert_eq!(board.units[boss].hp, 3, "death explosion hits Jelly_Boss at F7");
        assert_eq!(board.tile(3, 2).building_hp, 1, "death explosion damages F5 tower");
        assert!(!board.units[tank].boosted(), "Boost is consumed by the attack");
    }

    #[test]
    fn test_boosted_repair_heals_two_and_consumes_boost() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 3, 3, 3, WId::Repair);
        board.units[mech].hp = 1;
        board.units[mech].set_boosted(true);

        let _ = simulate_action(&mut board, mech, (3, 3), WId::Repair, (3, 3), &WEAPONS);

        assert_eq!(board.units[mech].hp, 3, "boosted Repair heals 2 HP");
        assert!(!board.units[mech].boosted(), "Boost is consumed by Repair");
    }

    #[test]
    fn test_repair_keeps_acid_during_active_acid_storm() {
        let mut board = make_test_board();
        board.mission_id = "Mission_AcidStorm".to_string();
        add_enemy_type(&mut board, 99, 2, 1, 3, "Storm_Generator");
        let mech = add_mech(&mut board, 1, 3, 3, 2, WId::Repair);
        board.units[mech].set_acid(true);

        let _ = simulate_action(&mut board, mech, (3, 3), WId::Repair, (3, 3), &WEAPONS);

        assert_eq!(board.units[mech].hp, 3, "Repair still heals in ACID Storm");
        assert!(
            board.units[mech].acid(),
            "active ACID Storm should immediately keep repaired units ACIDed"
        );
    }

    #[test]
    fn test_repulse_shield_self_upgrade_shields_pulse_after_pushes() {
        let mut board = make_test_board();
        let pulse = add_mech(&mut board, 2, 3, 3, 3, WId::ScienceRepulseA);
        let enemy = add_enemy(&mut board, 10, 2, 3, 1);

        let _ = simulate_weapon(&mut board, pulse, WId::ScienceRepulseA, 3, 3);

        assert!(board.units[pulse].shield(), "Shield Self should shield Pulse");
        assert_eq!(
            (board.units[enemy].x, board.units[enemy].y),
            (1, 3),
            "Repulse_A should keep base adjacent outward push behavior"
        );
        assert!(
            !board.units[enemy].shield(),
            "Shield Self should not shield adjacent enemies"
        );
    }

    #[test]
    fn test_repulse_invalid_diagonal_target_noops() {
        // Mission_Teleporter m23 turn 4: Pulse moved onto a pad at (4,4),
        // teleported to (5,3), then the stale target (4,4) was diagonal from
        // the actual source. pawn:FireWeapon accepted the command but produced
        // no Repulse effect, so the sim must not invent a push or Shield Self.
        let mut board = make_test_board();
        let pulse = add_mech(&mut board, 2, 5, 3, 3, WId::ScienceRepulseA);
        let enemy = add_enemy(&mut board, 10, 5, 2, 3);

        let result = simulate_weapon(&mut board, pulse, WId::ScienceRepulseA, 4, 4);

        assert_eq!(
            (board.units[enemy].x, board.units[enemy].y, board.units[enemy].hp),
            (5, 2, 3),
            "invalid diagonal Repulse target should not push or damage adjacent units"
        );
        assert!(
            !board.units[pulse].shield(),
            "invalid diagonal Repulse target should not apply Shield Self"
        );
        assert!(
            result.events.iter().any(|e| e.starts_with("invalid_self_aoe_target")),
            "invalid target should leave a replay/audit breadcrumb"
        );
    }

    #[test]
    fn test_repulse_edge_push_does_not_bump_off_board() {
        // Live regression: Easy Rusting Hulks run 20260508_134925_472,
        // Corporate HQ turn 3. PulseMech at D2 Repulsed a 1-HP Blobber at
        // D1 toward the board edge; the engine pushed nowhere and dealt no
        // phantom bump damage.
        let mut board = make_test_board();
        let pulse = add_mech(&mut board, 2, 6, 4, 3, WId::ScienceRepulse);
        let blobber = add_enemy_type(&mut board, 541, 7, 4, 1, "Blobber1");

        let result = simulate_weapon(&mut board, pulse, WId::ScienceRepulse, 6, 4);

        assert_eq!(
            (board.units[blobber].x, board.units[blobber].y, board.units[blobber].hp),
            (7, 4, 1),
            "zero-damage Repulse edge push should not add off-board bump damage"
        );
        assert_eq!(result.enemies_killed, 0);
    }

    #[test]
    fn test_repair_platform_overheal_cap_is_max_hp_plus_two() {
        let mut board = make_test_board();
        board.tile_mut(3, 3).set_repair_platform(true);
        let mech_idx = add_mech(&mut board, 1, 3, 2, 1, WId::PrimePunchmech);
        board.units[mech_idx].max_hp = 3;

        let result = simulate_move(&mut board, mech_idx, (3, 3));

        assert_eq!(board.units[mech_idx].hp, 5, "1/3 mech overheals to 5/3");
        assert_eq!(board.repair_platforms_used, 1);
        assert_eq!(result.repair_platforms_used, 1);
        assert!(
            !board.tile(3, 3).repair_platform(),
            "repair platform consumed on use"
        );
    }

    #[test]
    fn test_repair_platform_does_not_floor_two_hp_mech_to_five() {
        let mut board = make_test_board();
        board.tile_mut(3, 3).set_repair_platform(true);
        let mech_idx = add_mech(&mut board, 1, 3, 2, 4, WId::BruteJetmech);
        board.units[mech_idx].max_hp = 2;

        let _ = simulate_move(&mut board, mech_idx, (3, 3));

        assert_eq!(board.units[mech_idx].hp, 4, "4/2 Jet stays capped at 4/2");
    }

    #[test]
    fn test_repair_platform_full_health_mech_does_not_overheal() {
        let mut board = make_test_board();
        board.tile_mut(3, 3).set_repair_platform(true);
        let mech_idx = add_mech(&mut board, 1, 3, 2, 3, WId::ScienceRepulse);
        board.units[mech_idx].max_hp = 3;

        let result = simulate_move(&mut board, mech_idx, (3, 3));

        assert_eq!(board.units[mech_idx].hp, 3, "3/3 mech consumes platform without overheal");
        assert_eq!(board.repair_platforms_used, 1);
        assert_eq!(result.repair_platforms_used, 1);
        assert!(
            !board.tile(3, 3).repair_platform(),
            "repair platform consumed even when full-health mech gets no HP"
        );
    }

    #[test]
    fn test_flying_mech_move_onto_fire_tile_ignites() {
        // Live regression: Easy Rusting Hulks run 20260508_134925_472,
        // Mission_Final_Cave turn 4. An immediate verify sampled before the
        // fire status settled, but a fresh bridge read showed JetMech on fire.
        let mut board = make_test_board();
        board.tile_mut(3, 4).set_on_fire(true);
        let jet = add_mech(&mut board, 1, 3, 3, 2, WId::BruteJetmechB);
        board.units[jet].flags.insert(UnitFlags::FLYING);

        let _ = simulate_move(&mut board, jet, (3, 4));

        assert_eq!((board.units[jet].x, board.units[jet].y), (3, 4));
        assert!(
            board.units[jet].fire(),
            "Flying mech should catch fire from ordinary burning ground once status settles"
        );
        assert!(board.tile(3, 4).on_fire(), "Ordinary tile fire remains on the tile");
    }

    #[test]
    fn test_flame_shielding_does_not_protect_archive_tank_from_fire_tile() {
        // Regression: Flame Behemoths Perfect Strategy run 20260518_105028_125,
        // Mission_Tanks final turn. The live Archive Tank caught fire after
        // moving onto a burning tile; the sim had incorrectly treated every
        // player-team unit as Flame-Shielding immune.
        let mut board = make_test_board();
        board.flame_shielding = true;
        board.tile_mut(5, 1).set_on_fire(true);
        let tank = add_mission_ally(
            &mut board,
            5326,
            4,
            2,
            1,
            WId::DeployTankShot,
            "Archive_Tank",
        );

        let _ = simulate_move(&mut board, tank, (5, 1));

        assert_eq!((board.units[tank].x, board.units[tank].y), (5, 1));
        assert!(
            board.units[tank].fire(),
            "Flame Shielding applies to mechs, not allied mission tanks"
        );
    }

    fn add_decoy_building(board: &mut Board, uid: u16, x: u8, y: u8) -> usize {
        let idx = board.add_unit(Unit {
            uid, x, y, hp: 2, max_hp: 2,
            team: Team::Player,
            weapon: crate::board::WeaponId(WId::TrappedExplode as u16),
            flags: UnitFlags::ACTIVE,
            move_speed: 0,
            ..Default::default()
        });
        board.units[idx].set_type_name("Trapped_Building");
        idx
    }

    #[test]
    fn test_bouncer_boss_sweeping_horns_hits_t_pattern_and_bounces() {
        let mut board = make_test_board();
        let boss = add_enemy_type(&mut board, 10, 3, 3, 4, "BouncerBoss");
        let center = add_mech(&mut board, 20, 3, 4, 4, WId::None);
        let left = add_mech(&mut board, 21, 2, 4, 4, WId::None);
        let right = add_mech(&mut board, 22, 4, 4, 4, WId::None);

        let _ = simulate_weapon(&mut board, boss, WId::BouncerAtkB, 3, 4);

        assert_eq!((board.units[boss].x, board.units[boss].y), (3, 2), "boss bounced backward");
        assert_eq!((board.units[center].x, board.units[center].y), (3, 5));
        assert_eq!(board.units[center].hp, 2);
        assert_eq!((board.units[left].x, board.units[left].y), (2, 5));
        assert_eq!(board.units[left].hp, 2);
        assert_eq!((board.units[right].x, board.units[right].y), (4, 5));
        assert_eq!(board.units[right].hp, 2);
    }

    #[test]
    fn test_trapped_explode_kills_self_and_adjacent_units() {
        let mut board = make_test_board();
        let decoy = add_decoy_building(&mut board, 10, 3, 3);
        let enemy = add_enemy(&mut board, 20, 3, 4, 5);
        let mech = add_mech(&mut board, 30, 2, 3, 3, WId::PrimePunchmech);

        let result = simulate_weapon(&mut board, decoy, WId::TrappedExplode, 3, 3);

        assert_eq!(board.units[decoy].hp, 0);
        assert_eq!(board.units[enemy].hp, 0);
        assert_eq!(board.units[mech].hp, 0);
        assert_eq!(result.enemies_killed, 1);
        assert_eq!(result.mechs_killed, 1);
    }

    #[test]
    fn test_trapped_explode_skips_adjacent_buildings() {
        let mut board = make_test_board();
        let decoy = add_decoy_building(&mut board, 10, 3, 3);
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 2;
        board.tile_mut(4, 3).terrain = Terrain::Mountain;
        board.tile_mut(4, 3).building_hp = 2;

        let result = simulate_weapon(&mut board, decoy, WId::TrappedExplode, 3, 3);

        assert_eq!(board.tile(3, 4).building_hp, 2);
        assert_eq!(board.tile(3, 4).terrain, Terrain::Building);
        assert_eq!(board.grid_power, 7);
        assert_eq!(result.grid_damage, 0);
        assert_eq!(board.tile(4, 3).building_hp, 1);
    }

    #[test]
    fn test_push_into_water_kills() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Water;
        let idx = add_enemy(&mut board, 1, 3, 3, 2);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result); // push N into water
        assert_eq!(board.units[idx].hp, 0);
        assert_eq!(result.enemies_killed, 1);
    }

    #[test]
    fn test_push_enemy_onto_time_pod_destroys_without_collecting() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).set_has_pod(true);
        let idx = add_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);

        assert_eq!((board.units[idx].x, board.units[idx].y), (3, 4));
        assert!(!board.tile(3, 4).has_pod());
        assert_eq!(result.pods_collected, 0);
        assert!(result.events.iter().any(|e| e == "pod_destroyed_by_landing:3:4"));
    }

    #[test]
    fn test_push_mech_onto_time_pod_collects() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).set_has_pod(true);
        let idx = add_mech(&mut board, 1, 3, 3, 3, WId::PrimePunchmech);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);

        assert_eq!((board.units[idx].x, board.units[idx].y), (3, 4));
        assert!(!board.tile(3, 4).has_pod());
        assert_eq!(result.pods_collected, 1);
    }

    #[test]
    fn test_direct_damage_to_time_pod_destroys_without_collecting() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).set_has_pod(true);

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 4, 1, &mut result, DamageSource::Weapon);

        assert!(!board.tile(3, 4).has_pod());
        assert_eq!(result.pods_collected, 0);
        assert!(result.events.iter().any(|e| e == "pod_destroyed_by_damage:3:4"));
    }

    #[test]
    fn test_chain_whip_does_not_break_ice_under_target() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 0, 5, 3, 5, WId::PrimeLightning);
        board.tile_mut(4, 3).terrain = Terrain::Ice;
        board.tile_mut(4, 3).set_cracked(true);
        let starfish = add_enemy_type(&mut board, 2588, 4, 3, 4, "Starfish2");

        let result = simulate_attack(&mut board, mech, WId::PrimeLightning, (4, 3), &WEAPONS);

        assert_eq!(board.units[starfish].hp, 2);
        assert_eq!(board.tile(4, 3).terrain, Terrain::Ice);
        assert!(board.tile(4, 3).cracked());
        assert_eq!(result.enemies_killed, 0);
        assert!(
            !result.events.iter().any(|e| e.starts_with("illegal_weapon_target")),
            "adjacent pawn target should be legal"
        );
    }

    #[test]
    fn test_chain_whip_ignites_forest_under_hit_pawn() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 0, 5, 3, 5, WId::PrimeLightning);
        board.tile_mut(4, 3).terrain = Terrain::Forest;
        let enemy = add_enemy_type(&mut board, 2588, 4, 3, 4, "Starfish2");

        let result = simulate_attack(&mut board, mech, WId::PrimeLightning, (4, 3), &WEAPONS);

        assert_eq!(board.units[enemy].hp, 2);
        assert!(board.units[enemy].fire());
        assert_eq!(board.tile(4, 3).terrain, Terrain::Ground);
        assert!(board.tile(4, 3).on_fire());
        assert_eq!(result.enemies_killed, 0);
    }

    #[test]
    fn test_chain_whip_building_chain_uses_zero_damage_building_node() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 0, 4, 4, 5, WId::PrimeLightningA);
        board.tile_mut(4, 3).terrain = Terrain::Building;
        board.tile_mut(4, 3).building_hp = 1;
        board.grid_power = 4;
        let chained = add_enemy(&mut board, 2588, 4, 2, 4);

        let result = simulate_attack(&mut board, mech, WId::PrimeLightningA, (4, 3), &WEAPONS);

        assert_eq!(board.units[chained].hp, 2);
        assert_eq!(board.tile(4, 3).building_hp, 1);
        assert_eq!(board.grid_power, 4);
        assert_eq!(result.grid_damage, 0);
        assert!(
            !result.events.iter().any(|e| e.starts_with("illegal_weapon_target")),
            "Building Chain should make adjacent buildings legal targets"
        );
    }

    #[test]
    fn test_push_into_building_both_take_damage() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;
        let idx = add_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result); // push N into building
        assert_eq!(board.units[idx].hp, 2); // -1 bump
        assert_eq!(board.tile(3, 4).building_hp, 0); // building destroyed
        assert_eq!(result.grid_damage, 1);
        // 1-HP regular building destroyed → grid -1
        assert_eq!(board.grid_power, 6);
    }

    // Regression: snapshots grid_drop_20260421_161809_372_t02_a0 and t03_a1
    // plus the Ranged_Rocket bump trace from commit 2a86ca1.
    //
    // A bump that damages a non-unique multi-HP building but does NOT destroy
    // it must leave grid_power alone. If that same building later dies, the
    // delayed bump HP loss is charged then. Unique/objective buildings keep
    // immediate per-HP grid accounting.
    #[test]
    fn test_push_into_nonunique_2hp_building_preserves_grid() {
        let mut board = make_test_board();
        assert_eq!(board.grid_power, 7);
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 2;
        let idx = add_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result); // push N into building
        assert_eq!(board.units[idx].hp, 2); // -1 bump
        assert_eq!(board.tile(3, 4).building_hp, 1); // damaged, not destroyed
        assert_eq!(board.tile(3, 4).terrain, Terrain::Building);
        assert_eq!(result.grid_damage, 0);
        // CRITICAL: grid_power unchanged because the non-unique building
        // was damaged, not destroyed.
        assert_eq!(board.grid_power, 7);
    }

    #[test]
    fn test_deferred_nonunique_bump_debt_charged_on_later_destroy() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 2;
        let idx = add_enemy(&mut board, 1, 3, 3, 3);

        let mut first = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut first);
        assert_eq!(board.units[idx].hp, 2);
        assert_eq!(board.tile(3, 4).building_hp, 1);
        assert_eq!(first.grid_damage, 0);
        assert_eq!(board.grid_power, 7);

        let mut second = ActionResult::default();
        apply_damage(&mut board, 3, 4, 1, &mut second, DamageSource::Weapon);
        assert_eq!(board.tile(3, 4).building_hp, 0);
        assert_eq!(second.grid_damage, 2);
        assert_eq!(board.grid_power, 5);
    }

    #[test]
    fn test_deferred_nonunique_bump_debt_flushes_at_enemy_turn_start() {
        let mut board = make_test_board();
        board.grid_power = 4;
        board.tile_mut(4, 6).terrain = Terrain::Building;
        board.tile_mut(4, 6).building_hp = 2; // B4 visual
        let firefly = add_enemy_type(&mut board, 884, 4, 5, 5, "Firefly2");

        let mut first = ActionResult::default();
        apply_push(&mut board, 4, 5, 0, &mut first); // push into B4
        assert_eq!(board.units[firefly].hp, 4);
        assert_eq!(board.tile(4, 6).building_hp, 1);
        assert_eq!(first.grid_damage, 0);
        assert_eq!(board.grid_power, 4);

        let original_positions = [(0u8, 0u8); 16];
        crate::enemy::simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!(board.tile(4, 6).building_hp, 1, "B4 survives at 1 HP");
        assert_eq!(board.grid_power, 3, "deferred B4 grid debt is charged at enemy-turn start");
        assert_eq!(board.deferred_bump_grid_debt[xy_to_idx(4, 6)], 0);
    }

    #[test]
    fn test_deferred_nonunique_bump_debt_not_double_charged_after_destroy() {
        let mut board = make_test_board();
        board.grid_power = 7;
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 2;
        add_enemy(&mut board, 1, 3, 3, 3);

        let mut first = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut first);
        assert_eq!(board.grid_power, 7);
        assert_eq!(board.tile(3, 4).building_hp, 1);

        let mut second = ActionResult::default();
        apply_damage(&mut board, 3, 4, 1, &mut second, DamageSource::Weapon);
        assert_eq!(second.grid_damage, 2);
        assert_eq!(board.grid_power, 5);

        let original_positions = [(0u8, 0u8); 16];
        crate::enemy::simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);
        assert_eq!(board.grid_power, 5, "enemy-turn flush must not charge cleared debt twice");
    }

    #[test]
    fn test_second_bump_collects_deferred_nonunique_grid_debt() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 2;
        add_enemy(&mut board, 1, 3, 3, 3);

        let mut first = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut first);
        assert_eq!(board.tile(3, 4).building_hp, 1);
        assert_eq!(first.grid_damage, 0);
        assert_eq!(board.grid_power, 7);

        let mut second = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut second);
        assert_eq!(board.tile(3, 4).building_hp, 0);
        assert_eq!(second.grid_damage, 2);
        assert_eq!(board.grid_power, 5);
    }

    #[test]
    fn test_push_into_unique_2hp_building_drops_grid_per_hp() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 2;
        // Mark as a unique/objective-style building.
        let idx = xy_to_idx(3, 4) as u64;
        board.unique_buildings |= 1u64 << idx;
        let eidx = add_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        assert_eq!(board.units[eidx].hp, 2);
        assert_eq!(board.tile(3, 4).building_hp, 1);
        assert_eq!(board.tile(3, 4).terrain, Terrain::Building);
        // Unique/inferred objective building: each HP is worth 1 grid.
        assert_eq!(result.grid_damage, 1);
        assert_eq!(board.grid_power, 6);
    }

    #[test]
    fn test_push_into_grid_reward_2hp_building_drops_grid_per_hp() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 2;
        let idx = xy_to_idx(3, 4) as u64;
        board.unique_buildings |= 1u64 << idx;
        board.grid_reward_buildings |= 1u64 << idx;
        let eidx = add_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);

        assert_eq!(board.units[eidx].hp, 2);
        assert_eq!(board.tile(3, 4).building_hp, 1);
        assert_eq!(result.grid_damage, 1);
        assert_eq!(board.grid_power, 6);
    }

    #[test]
    fn test_push_destroys_nonunique_2hp_on_second_bump_drops_grid() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1; // already damaged once
        let idx = add_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        // Building destroyed (hp 1 → 0). Non-unique → rubble.
        assert_eq!(board.tile(3, 4).building_hp, 0);
        assert_eq!(board.tile(3, 4).terrain, Terrain::Rubble);
        assert_eq!(result.grid_damage, 1);
        // Destruction drops grid by 1 (the building's only grid contribution).
        assert_eq!(board.grid_power, 6);
        // Unit still took the bump.
        assert_eq!(board.units[idx].hp, 2);
    }

    #[test]
    fn test_weapon_damage_multi_hp_building_drops_grid_per_hp() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 2;

        let mut first = ActionResult::default();
        apply_damage(&mut board, 3, 4, 1, &mut first, DamageSource::Weapon);
        assert_eq!(board.tile(3, 4).building_hp, 1);
        assert_eq!(board.tile(3, 4).terrain, Terrain::Building);
        assert_eq!(first.grid_damage, 1);
        assert_eq!(board.grid_power, 6);

        let mut second = ActionResult::default();
        apply_damage(&mut board, 3, 4, 1, &mut second, DamageSource::Weapon);
        assert_eq!(board.tile(3, 4).building_hp, 0);
        assert_eq!(board.tile(3, 4).terrain, Terrain::Rubble);
        assert_eq!(second.grid_damage, 1);
        assert_eq!(board.grid_power, 5);
    }

    #[test]
    fn test_weapon_damage_grid_reward_building_drops_grid_per_hp() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 2;
        let idx = xy_to_idx(3, 4) as u64;
        board.unique_buildings |= 1u64 << idx;
        board.grid_reward_buildings |= 1u64 << idx;

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 4, 1, &mut result, DamageSource::Weapon);

        assert_eq!(board.tile(3, 4).building_hp, 1);
        assert_eq!(board.tile(3, 4).terrain, Terrain::Building);
        assert_eq!(result.grid_damage, 1);
        assert_eq!(board.grid_power, 6);
    }

    #[test]
    fn test_dead_unit_still_pushes_into_building() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;

        // Enemy at (3,3) with 0 HP (just killed)
        board.add_unit(Unit {
            uid: 1, x: 3, y: 3, hp: 0, max_hp: 2,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        // Dead unit corpse still bumps the building
        assert_eq!(board.tile(3, 4).building_hp, 0);
        assert_eq!(result.grid_damage, 1);
    }

    #[test]
    fn test_bump_ignores_armor() {
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 0, 0, 3);
        board.units[idx].flags |= UnitFlags::ARMOR;

        let mut result = ActionResult::default();
        apply_push(&mut board, 0, 0, 2, &mut result); // push S off edge
        // Bump damage ignores armor: should take 1, not 0
        assert_eq!(board.units[idx].hp, 2);
    }

    #[test]
    fn test_titan_fist_kill_and_push() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::PrimePunchmech);
        let enemy_idx = add_enemy(&mut board, 1, 3, 4, 2);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmech, 3, 4);
        // 2 damage kills 2HP hornet
        assert_eq!(result.enemies_killed, 1);
        // Dead unit pushed forward (simultaneous)
        assert_eq!(board.units[enemy_idx].y, 5); // moved from 4 to 5
    }

    #[test]
    fn test_minor_totem_kill_does_not_advance_mission_kill_counter() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::PrimePunchmech);
        let totem_idx = add_enemy_type(&mut board, 91, 3, 4, 1, "Totem1");
        board.units[totem_idx].flags.insert(UnitFlags::MINOR);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmech, 3, 4);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(result.mission_kills, 0);
    }

    // ── Prime_Spear path_size=2 stab (Lua weapons_prime.lua:792-846) ──────────
    //
    // Spear is Range=2, PathSize=2: GetTargetArea enumerates both +1 and +2
    // tiles; GetSkillEffect damages every tile from attacker+1 to target with
    // only the FURTHEST tile receiving Push.

    #[test]
    fn test_spear_range_2_stab_through_empty_tile_hits_far_enemy_only() {
        // Mech at (3,3), enemy at (3,5). Empty tile (3,4) is the in-path tile.
        // Lua damages (3,4) with 2 (no occupant → no effect on units, but
        // mountains/buildings would get hit) and damages (3,5) with 2 + push.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::PrimeSpear);
        let enemy_idx = add_enemy(&mut board, 1, 3, 5, 3);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimeSpear, 3, 5);
        // Far enemy (3,5) takes 2 damage (3hp → 1hp) and is pushed forward to (3,6).
        assert_eq!(result.enemies_killed, 0, "3hp enemy survives 2 damage");
        assert_eq!(board.units[enemy_idx].hp, 1, "Enemy HP: 3 - 2 = 1");
        assert_eq!(board.units[enemy_idx].x, 3);
        assert_eq!(board.units[enemy_idx].y, 6,
            "Far enemy pushed forward (Lua: push only on furthest tile)");
        // In-path tile (3,4) had no unit — it's just transit damage on empty
        // ground. Tile must not have spurious terrain change.
        assert_eq!(board.tile(3, 4).terrain, Terrain::Ground);
    }

    #[test]
    fn test_spear_range_2_stab_damages_tile_1_unit_when_targeting_tile_2() {
        // Mech at (3,3), enemy A at (3,4) (in-path), enemy B at (3,5) (target).
        // Spear damages BOTH tiles for 2 each — only B gets pushed.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::PrimeSpear);
        let near_idx = add_enemy(&mut board, 1, 3, 4, 3); // in-path, 3 hp
        let far_idx  = add_enemy(&mut board, 2, 3, 5, 3); // target,  3 hp

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeSpear, 3, 5);
        // Both alive (3 - 2 = 1) — neither dies.
        assert_eq!(board.units[near_idx].hp, 1, "Near enemy takes 2 transit damage");
        assert_eq!(board.units[far_idx].hp, 1, "Far enemy takes 2 weapon damage");
        // Near enemy NOT pushed (Lua: only furthest tile receives push).
        assert_eq!((board.units[near_idx].x, board.units[near_idx].y), (3, 4),
            "In-path enemy is NOT pushed");
        // Far enemy push attempt: destination (3,6) is empty → moves there.
        assert_eq!((board.units[far_idx].x, board.units[far_idx].y), (3, 6),
            "Far enemy pushed forward by 1 tile");
    }

    #[test]
    fn test_spear_range_1_stab_unchanged_legacy_behavior() {
        // Targeting the adjacent tile (distance=1) must behave exactly like a
        // 1-tile melee — single-tile damage + push, no in-path damage.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::PrimeSpear);
        let enemy_idx = add_enemy(&mut board, 1, 3, 4, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeSpear, 3, 4);
        // Enemy at (3,4) takes 2 damage (3 → 1) and is pushed to (3,5).
        assert_eq!(board.units[enemy_idx].hp, 1);
        assert_eq!(board.units[enemy_idx].x, 3);
        assert_eq!(board.units[enemy_idx].y, 5,
            "Range-1 stab still pushes target forward");
        // No spurious self-damage on attacker.
        assert_eq!(board.units[mech_idx].hp, 3);
    }

    #[test]
    fn test_spear_push_direction_is_along_path_away_from_mech() {
        // Verify the push direction is the spear's attack axis (mech → target),
        // not some other inferred axis. Mech at (5,3), target enemy at (3,3)
        // (distance 2, attack direction = west, dx=-1). Push must move enemy
        // further west to (2,3).
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 3, 3, WId::PrimeSpear);
        let enemy_idx = add_enemy(&mut board, 1, 3, 3, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeSpear, 3, 3);
        assert_eq!(board.units[enemy_idx].hp, 1, "Far enemy hit for 2");
        assert_eq!((board.units[enemy_idx].x, board.units[enemy_idx].y), (2, 3),
            "Push direction is mech → target (west), enemy moves further west");
        // In-path tile (4,3) had no unit; no terrain change.
        assert_eq!(board.tile(4, 3).terrain, Terrain::Ground);
        // Mech unchanged.
        assert_eq!(board.units[mech_idx].x, 5);
        assert_eq!(board.units[mech_idx].y, 3);
    }

    #[test]
    fn test_spear_target_enumeration_includes_range_2() {
        // Target enumeration must produce BOTH +1 and +2 tiles in each
        // cardinal direction (Lua GetTargetArea iterates k=1..PathSize and
        // breaks only at board edge).
        let mut board = make_test_board();
        let _mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::PrimeSpear);
        // Place an enemy at the +2 tile so the action is considered
        // effectful even if path tile is empty.
        add_enemy(&mut board, 1, 3, 5, 3);

        let targets = crate::solver::get_weapon_targets(
            &board, 3, 3, WId::PrimeSpear, (3, 3), &WEAPONS);
        assert!(targets.contains(&(3, 5)),
            "Spear must enumerate range-2 tile (3,5); got {:?}", targets);
        assert!(targets.contains(&(3, 4)),
            "Spear must enumerate range-1 tile (3,4); got {:?}", targets);
    }

    /// Regression: snapshot grid_drop_20260424_174047_323_t01_a3.
    /// Titan Fist (plain Melee, no AOE flags) targeting an empty tile with
    /// mountains at the perpendicular cardinal neighbors must NOT damage
    /// those mountains. Only AOE_PERP weapons (Sword, Janus Cannon, etc.)
    /// hit perpendicular tiles.
    #[test]
    fn test_titan_fist_does_not_damage_perpendicular_mountains() {
        let mut board = make_test_board();
        // PunchMech at (1,3) attacking (1,2) — direction is (0,-1).
        // Perpendicular tiles around target (1,2): (0,2) and (2,2).
        let mech_idx = add_mech(&mut board, 0, 1, 3, 3, WId::PrimePunchmech);
        // Place mountains (HP 2) at the perpendicular tiles.
        {
            let t = board.tile_mut(0, 2);
            t.terrain = Terrain::Mountain;
            t.building_hp = 2;
        }
        {
            let t = board.tile_mut(2, 2);
            t.terrain = Terrain::Mountain;
            t.building_hp = 2;
        }
        // Target tile (1,2) is empty ground — no unit, no terrain feature.

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmech, 1, 2);

        // Mountains MUST be untouched. Plain Melee with no AOE_PERP flag
        // should not splash to perpendicular tiles.
        assert_eq!(board.tile(0, 2).terrain, Terrain::Mountain,
            "(0,2) mountain should remain mountain");
        assert_eq!(board.tile(0, 2).building_hp, 2,
            "(0,2) mountain HP must be unchanged (was 2)");
        assert_eq!(board.tile(2, 2).terrain, Terrain::Mountain,
            "(2,2) mountain should remain mountain");
        assert_eq!(board.tile(2, 2).building_hp, 2,
            "(2,2) mountain HP must be unchanged (was 2)");
    }

    /// Reproduce the full board layout from snapshot
    /// grid_drop_20260424_174047_323_t01_a3 to ensure no neighbouring
    /// terrain or building interaction triggers stray perpendicular damage
    /// for plain Titan Fist.
    #[test]
    fn test_titan_fist_perp_mountains_with_full_neighbourhood() {
        let mut board = make_test_board();
        // PunchMech at (1,3) — same as snapshot.
        let mech_idx = add_mech(&mut board, 0, 1, 3, 5, WId::PrimePunchmech);
        // Snapshot terrain (relevant tiles near target):
        //   (0,2) mountain hp=2
        //   (1,1) building hp=1
        //   (1,2) ground (target — empty)
        //   (2,1) building hp=1
        //   (2,2) mountain hp=2
        //   (2,3) building hp=1
        for &(mx, my) in &[(0u8, 2u8), (2u8, 2u8)] {
            let t = board.tile_mut(mx, my);
            t.terrain = Terrain::Mountain;
            t.building_hp = 2;
        }
        for &(bx, by) in &[(1u8, 1u8), (2u8, 1u8), (2u8, 3u8)] {
            let t = board.tile_mut(bx, by);
            t.terrain = Terrain::Building;
            t.building_hp = 1;
        }

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmech, 1, 2);

        // Critical assertion: perpendicular mountains untouched.
        assert_eq!(board.tile(0, 2).terrain, Terrain::Mountain);
        assert_eq!(board.tile(0, 2).building_hp, 2);
        assert_eq!(board.tile(2, 2).terrain, Terrain::Mountain);
        assert_eq!(board.tile(2, 2).building_hp, 2);
        // Diagonally-adjacent buildings also untouched.
        assert_eq!(board.tile(2, 1).building_hp, 1);
        assert_eq!(board.tile(2, 3).building_hp, 1);
        // Mech HP unchanged (no self-damage on a plain Titan Fist hit on
        // empty ground).
        assert_eq!(board.units[mech_idx].hp, 5);
    }

    #[test]
    fn test_titan_fist_dash_punch_charges_to_target_and_records_ramming_speed() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 1, 3, 3, WId::PrimePunchmechA);
        let enemy_idx = add_enemy(&mut board, 1, 6, 3, 2);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmechA, 2, 3);

        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (5, 3));
        assert!(board.units[enemy_idx].hp <= 0, "Dash Punch should kill the 2 HP target");
        assert_eq!(result.enemies_killed, 1);
        assert!(
            result.events.iter().any(|e| {
                e == "achievement_ramming_speed_dash_punch_kill:distance:5:target:6:3"
            }),
            "Expected Ramming Speed event, got {:?}",
            result.events
        );
    }

    #[test]
    fn test_titan_fist_ab_dash_punch_uses_damage_upgrade() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 1, 3, 3, WId::PrimePunchmechAB);
        let enemy_idx = add_enemy(&mut board, 1, 6, 3, 4);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmechAB, 2, 3);

        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (5, 3));
        assert!(board.units[enemy_idx].hp <= 0, "AB Dash Punch should deal 4 damage");
        assert_eq!(result.enemies_killed, 1);
    }

    #[test]
    fn test_titan_fist_dash_crosses_water_before_first_blocker() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 2, 3, 3, WId::PrimePunchmechA);
        let enemy_idx = add_enemy(&mut board, 1, 6, 3, 2);
        board.tile_mut(4, 3).terrain = Terrain::Water;

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmechA, 3, 3);

        assert_eq!(
            (board.units[mech_idx].x, board.units[mech_idx].y),
            (5, 3),
            "Dash Punch should cross water instead of stopping before it"
        );
        assert!(board.units[enemy_idx].hp <= 0);
        assert_eq!(result.enemies_killed, 1);
    }

    #[test]
    fn test_titan_fist_dash_dead_target_bumps_live_blocker() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 1, 2, 3, WId::PrimePunchmechA);
        let blob_idx = add_enemy(&mut board, 1, 1, 1, 1);
        let arti_idx = add_mech(&mut board, 2, 1, 0, 2, WId::RangedArtillerymech);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmechA, 1, 1);

        assert!(board.units[blob_idx].hp <= 0, "Dash target dies from the punch");
        assert_eq!(
            board.units[arti_idx].hp, 1,
            "Dead Dash Punch target should still bump the live blocker behind it"
        );
        assert_eq!(result.mech_damage_taken, 1);
    }

    /// Reproduction via the bridge JSON path — the failing run actually
    /// dispatched through `replay_solution`, so verify the JSON pipeline
    /// (board_from_json → simulate_attack → snapshot serializer) reaches
    /// the same answer as the in-Rust unit test above.
    #[test]
    fn test_titan_fist_perp_via_bridge_replay() {
        // Bridge state matching snapshot grid_drop_20260424_174047_323_t01_a3
        // (see actual_board.json). Mech is at (1,3); target is empty (1,2);
        // mountains at (0,2) and (2,2); buildings at (1,1)/(2,1)/(2,3)/...
        let bridge = r#"{
          "tiles": [
            {"x":0,"y":2,"terrain":"mountain","building_hp":2},
            {"x":2,"y":2,"terrain":"mountain","building_hp":2},
            {"x":1,"y":1,"terrain":"building","building_hp":1},
            {"x":2,"y":1,"terrain":"building","building_hp":1},
            {"x":2,"y":3,"terrain":"building","building_hp":1}
          ],
          "units": [
            {"uid":0,"type":"PunchMech","x":1,"y":3,
             "hp":5,"max_hp":3,"team":1,"mech":true,
             "active":true,"move":4,"massive":true,
             "weapons":["Prime_Punchmech"]}
          ],
          "grid_power": 4,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "remaining_spawns": 0,
          "turn": 1,
          "total_turns": 5
        }"#;
        let plan = r#"[{"mech_uid":0,"move_to":[1,3],"weapon_id":"Prime_Punchmech","target":[1,2]}]"#;
        let raw = crate::replay::replay_solution(bridge, plan)
            .expect("replay should succeed");
        let v: serde_json::Value = serde_json::from_str(&raw).unwrap();
        // Walk tiles_changed in post_attack and assert the mountains kept HP=2.
        let post_attack = &v["predicted_states"][0]["post_attack"];
        let tiles = post_attack["tiles_changed"].as_array().unwrap();
        for t in tiles {
            let x = t["x"].as_u64().unwrap() as u8;
            let y = t["y"].as_u64().unwrap() as u8;
            if (x, y) == (0, 2) || (x, y) == (2, 2) {
                assert_eq!(t["terrain"].as_str().unwrap(), "mountain",
                    "({},{}) terrain", x, y);
                assert_eq!(t["building_hp"].as_u64().unwrap(), 2,
                    "({},{}) mountain HP via bridge replay", x, y);
            }
        }
        // Also assert mech HP unchanged.
        let units = post_attack["units"].as_array().unwrap();
        let mech = units.iter().find(|u| u["uid"].as_u64() == Some(0)).unwrap();
        assert_eq!(mech["hp"].as_i64().unwrap(), 5, "mech HP must be 5 (unchanged)");
    }

    /// Companion check: Sword (AOE_PERP melee) MUST still damage perpendicular
    /// mountains. Guards against an over-broad fix that strips the AOE_PERP
    /// path altogether.
    #[test]
    fn test_sword_damages_perpendicular_mountains() {
        let mut board = make_test_board();
        // Mech at (1,3), target (1,2), direction (0,-1).
        let mech_idx = add_mech(&mut board, 0, 1, 3, 3, WId::PrimeSword);
        for &(mx, my) in &[(0u8, 2u8), (2u8, 2u8)] {
            let t = board.tile_mut(mx, my);
            t.terrain = Terrain::Mountain;
            t.building_hp = 2;
        }

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeSword, 1, 2);

        // Sword has AOE_PERP — both perpendicular mountains lose 1 HP.
        assert_eq!(board.tile(0, 2).building_hp, 1,
            "(0,2) mountain should be damaged by Sword AOE_PERP");
        assert_eq!(board.tile(2, 2).building_hp, 1,
            "(2,2) mountain should be damaged by Sword AOE_PERP");
    }

    #[test]
    fn test_frozen_unit_invincible() {
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 3, 3, 2);
        board.units[idx].set_frozen(true);

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 5, &mut result, DamageSource::Weapon);
        // Damage unfreezes but deals 0
        assert_eq!(board.units[idx].hp, 2);
        assert!(!board.units[idx].frozen());
    }

    #[test]
    fn test_shield_absorbs_damage() {
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 3, 3, 2);
        board.units[idx].set_shield(true);

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 5, &mut result, DamageSource::Weapon);
        assert_eq!(board.units[idx].hp, 2); // no damage
        assert!(!board.units[idx].shield()); // shield consumed
    }

    #[test]
    fn test_shielded_building_absorbs_damage_before_grid_loss() {
        let mut board = make_test_board();
        board.grid_power = 4;
        {
            let tile = board.tile_mut(3, 3);
            tile.terrain = Terrain::Building;
            tile.building_hp = 1;
            tile.set_shield(true);
        }

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 1, &mut result, DamageSource::Weapon);

        assert_eq!(board.tile(3, 3).building_hp, 1);
        assert!(!board.tile(3, 3).shield());
        assert_eq!(board.grid_power, 4);
        assert_eq!(result.grid_damage, 0);
        assert_eq!(result.buildings_damaged, 0);

        apply_damage(&mut board, 3, 3, 1, &mut result, DamageSource::Weapon);
        assert_eq!(board.tile(3, 3).building_hp, 0);
        assert_eq!(board.grid_power, 3);
        assert_eq!(result.grid_damage, 1);
        assert_eq!(result.buildings_damaged, 1);
    }

    #[test]
    fn test_shield_projector_shields_building_target_and_line_tile() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 2, 5, 3, 2, WId::ScienceShield);
        for &(x, y) in &[(3, 3), (2, 3)] {
            let tile = board.tile_mut(x, y);
            tile.terrain = Terrain::Building;
            tile.building_hp = 1;
        }

        let result = simulate_attack(&mut board, mech_idx, WId::ScienceShield, (3, 3), &WEAPONS);

        assert!(
            !result.events.iter().any(|e| e.starts_with("illegal_weapon_target")),
            "building target should be legal for Shield Projector"
        );
        assert!(board.tile(3, 3).shield(), "target building should gain a shield");
        assert!(board.tile(2, 3).shield(), "second line tile should gain a shield");
        assert_eq!(board.tile(3, 3).building_hp, 1);
        assert_eq!(board.tile(2, 3).building_hp, 1);
    }

    #[test]
    fn test_laser_damage_decay() {
        let mut board = make_test_board();
        // Place enemies along a line
        add_enemy(&mut board, 1, 1, 0, 10);
        add_enemy(&mut board, 2, 2, 0, 10);
        add_enemy(&mut board, 3, 3, 0, 10);

        let mech_idx = add_mech(&mut board, 0, 0, 0, 3, WId::PrimeLasermech);
        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeLasermech, 1, 0);

        // Laser damage: 3, 2, 1 (decreasing, floor 1)
        // Enemies at indices 0,1,2; mech at index 3
        assert_eq!(board.units[0].hp, 7); // (1,0): 10-3
        assert_eq!(board.units[1].hp, 8); // (2,0): 10-2
        assert_eq!(board.units[2].hp, 9); // (3,0): 10-1
    }

    #[test]
    fn test_laser_ally_immune_skips_friendly_damage_but_decays() {
        let mut board = make_test_board();
        add_enemy(&mut board, 1, 1, 0, 10);
        let ally = add_mech(&mut board, 2, 2, 0, 3, WId::SciencePullmech);
        add_enemy(&mut board, 3, 3, 0, 10);

        let laser = add_mech(&mut board, 0, 0, 0, 3, WId::PrimeLasermechA);
        let _ = simulate_weapon(&mut board, laser, WId::PrimeLasermechA, 1, 0);

        assert_eq!(board.units[0].hp, 7, "first enemy takes 3 damage");
        assert_eq!(board.units[ally].hp, 3, "ally is not damaged by Ally Immune");
        assert_eq!(board.units[2].hp, 9, "beam still decays through ally tile");
    }

    #[test]
    fn test_acid_projector_applies_acid() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::ScienceAcidShot);
        let enemy_idx = add_enemy(&mut board, 1, 3, 4, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceAcidShot, 3, 4);
        // Acid Projector should apply ACID status to target
        assert!(board.units[enemy_idx].acid(), "Enemy should have ACID after Acid Projector");
        assert_eq!((board.units[enemy_idx].x, board.units[enemy_idx].y), (3, 5));
        assert!(
            !board.tile(3, 4).acid(),
            "Occupied ACID hits should not create an immediate ground pool"
        );
    }

    #[test]
    fn test_acid_projector_edge_block_noops_zero_damage_status() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 6, 2, WId::ScienceAcidShot);
        let enemy_idx = add_enemy(&mut board, 1, 3, 7, 1);

        let result = simulate_weapon(&mut board, mech_idx, WId::ScienceAcidShot, 3, 7);

        assert_eq!(board.units[enemy_idx].hp, 1);
        assert_eq!((board.units[enemy_idx].x, board.units[enemy_idx].y), (3, 7));
        assert!(!board.units[enemy_idx].acid());
        assert!(!board.tile(3, 7).acid());
        assert_eq!(result.enemies_killed, 0);
    }

    #[test]
    fn test_acid_projector_pushes_line_target_beyond_clicked_tile() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 1, 1, 2, WId::ScienceAcidShot);
        let enemy_idx = add_enemy(&mut board, 1, 1, 3, 6);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceAcidShot, 1, 2);

        assert_eq!((board.units[enemy_idx].x, board.units[enemy_idx].y), (1, 4));
        assert_eq!(board.units[enemy_idx].hp, 6);
        assert!(board.units[enemy_idx].acid());
    }

    #[test]
    fn test_acid_projector_pushes_already_acid_target_with_open_space() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 4, 4, 2, WId::ScienceAcidShot);
        let enemy_idx = add_enemy(&mut board, 1, 4, 1, 2);
        board.units[enemy_idx].set_acid(true);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceAcidShot, 4, 3);

        assert_eq!((board.units[enemy_idx].x, board.units[enemy_idx].y), (4, 0));
        assert_eq!(board.units[enemy_idx].hp, 2);
        assert!(board.units[enemy_idx].acid());
    }

    #[test]
    fn test_acid_projector_bump_on_occupied_cracked_ground_does_not_open_chasm() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 2, 5, 4, 2, WId::ScienceAcidShot);
        let shaman_idx = add_enemy_type(&mut board, 422, 5, 5, 3, "Shaman1");
        let bouncer_idx = add_enemy_type(&mut board, 448, 5, 6, 3, "Bouncer1");
        board.tile_mut(5, 6).set_cracked(true);

        let result = simulate_weapon(&mut board, mech_idx, WId::ScienceAcidShot, 5, 5);

        assert_eq!(board.units[shaman_idx].hp, 2);
        assert!(board.units[shaman_idx].acid(), "Acid Projector should acid the hit target before push");
        assert_eq!(board.units[bouncer_idx].hp, 2, "blocked push bumps the cracked-tile blocker for 1");
        assert_eq!(
            board.tile(5, 6).terrain,
            Terrain::Ground,
            "occupied cracked Ground should absorb bump damage without opening a chasm"
        );
        assert!(board.tile(5, 6).cracked());
        assert_eq!(result.enemies_killed, 0);
    }

    #[test]
    fn test_acid_tank_cannon_acids_unit_without_ground_pool() {
        let mut board = make_test_board();
        let tank_idx = add_mech(&mut board, 0, 3, 3, 1, WId::AcidTankAtk);
        let enemy_idx = add_enemy(&mut board, 1, 3, 4, 3);

        let _ = simulate_weapon(&mut board, tank_idx, WId::AcidTankAtk, 3, 4);

        assert!(board.units[enemy_idx].acid(), "A.C.I.D. Cannon should acidify the target unit");
        assert!(
            !board.tile(3, 4).acid(),
            "A.C.I.D. Cannon should not create a pool below a live target"
        );
    }

    #[test]
    fn test_lethal_acid_hit_on_non_acid_unit_does_not_create_pool() {
        let mut board = make_test_board();
        let centipede_weapon = add_mech(&mut board, 0, 3, 3, 3, WId::CentipedeAtk2);
        let enemy_idx = add_enemy(&mut board, 1, 3, 4, 1);

        let _ = simulate_weapon(&mut board, centipede_weapon, WId::CentipedeAtk2, 3, 4);

        assert!(board.units[enemy_idx].hp <= 0, "Centipede hit should kill the 1 HP target");
        assert!(
            !board.tile(3, 4).acid(),
            "A lethal ACID hit on a non-ACID live target should not synthesize a pool"
        );
    }

    #[test]
    fn test_cryo_launcher_freezes_target_and_self() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::RangedIce);
        let enemy_idx = add_enemy(&mut board, 1, 3, 6, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedIce, 3, 6);
        assert!(board.units[enemy_idx].frozen(), "Target should be frozen");
        assert!(board.units[mech_idx].frozen(), "Cryo-Launcher should self-freeze");
    }

    #[test]
    fn test_shield_blocks_status_without_consuming() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::ScienceAcidShot);
        let enemy_idx = add_enemy(&mut board, 1, 3, 4, 3);
        board.units[enemy_idx].set_shield(true);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceAcidShot, 3, 4);
        // Shield should block ACID but shield consumed by the 0-damage hit?
        // Acid Projector does 0 damage, so shield NOT consumed. Status also blocked.
        assert!(!board.units[enemy_idx].acid(), "Shield should block ACID status");
        assert!(board.units[enemy_idx].shield(), "Shield should NOT be consumed by 0 damage");
        assert!(
            board.tile(3, 4).acid(),
            "Blocked ACID should fall to the target's feet"
        );
    }

    #[test]
    fn test_acid_projector_frozen_target_falls_to_feet() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::ScienceAcidShot);
        let enemy_idx = add_enemy(&mut board, 1, 3, 4, 3);
        board.units[enemy_idx].set_frozen(true);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceAcidShot, 3, 4);

        assert!(!board.units[enemy_idx].acid(), "Frozen target should not receive ACID status");
        assert!(
            board.tile(3, 4).acid(),
            "ACID blocked by frozen status should fall to the tile"
        );
    }

    #[test]
    fn test_missile_barrage_excludes_source_and_requires_valid_target() {
        let mut board = make_test_board();
        let caster = add_mech(&mut board, 0, 3, 3, 2, WId::MissilesOneDmg);
        let ally = add_mech(&mut board, 1, 4, 3, 3, WId::None);
        let enemy = add_enemy(&mut board, 2, 5, 3, 3);

        let _ = simulate_weapon(&mut board, caster, WId::MissilesOneDmg, 5, 3);
        assert_eq!(board.units[caster].hp, 2, "source tile is excluded by Support_Missiles");
        assert_eq!(board.units[ally].hp, 2, "friendly non-source unit should be hit");
        assert_eq!(board.units[enemy].hp, 2, "enemy unit should be hit");

        let mut invalid = make_test_board();
        let invalid_caster = add_mech(&mut invalid, 10, 3, 3, 2, WId::MissilesOneDmg);
        let invalid_enemy = add_enemy(&mut invalid, 11, 5, 3, 3);
        let _ = simulate_weapon(&mut invalid, invalid_caster, WId::MissilesOneDmg, 3, 3);
        assert_eq!(invalid.units[invalid_caster].hp, 2, "source click should no-op");
        assert_eq!(invalid.units[invalid_enemy].hp, 3, "source click should emit no missiles");
    }

    #[test]
    fn test_push_onto_fire_tile() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).set_on_fire(true);
        let idx = add_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        assert!(board.units[idx].fire(), "Unit pushed onto fire tile should catch fire");
    }

    #[test]
    fn test_push_flying_unit_onto_fire_tile_ignites() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).set_on_fire(true);
        let idx = add_enemy(&mut board, 1, 3, 3, 3);
        board.units[idx].flags.insert(UnitFlags::FLYING);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);

        assert_eq!((board.units[idx].x, board.units[idx].y), (3, 4));
        assert!(
            board.units[idx].fire(),
            "Flying unit should catch fire from ordinary burning ground"
        );
    }

    // ── Ranged_Rocket smoke-behind-shooter ──────────────────────────────────
    // Tooltip: "Fires a pushing artillery and creates Smoke behind the shooter."
    // Smoke lands one tile opposite the shot direction from the attacker; NOT
    // on the target tile. Off-board behind-tile = no-op (shooter at edge).
    #[test]
    fn test_sim_artillery_rocket_smokes_behind_shooter() {
        // Rocket Mech at (3,3) fires east at (3,6). DIRS[0] = (0,1) so east is
        // dir=0; behind-shooter is (3,3) - (0,1) = (3,2). Target takes 2 dmg
        // and is pushed east to (3,7). Smoke lands at (3,2).
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::RangedRocket);
        let enemy_idx = add_enemy(&mut board, 1, 3, 6, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedRocket, 3, 6);

        assert_eq!(board.units[enemy_idx].hp, 1, "target took 2 damage (3 → 1)");
        assert_eq!(
            (board.units[enemy_idx].x, board.units[enemy_idx].y),
            (3, 7),
            "target pushed east (forward = attack dir)"
        );
        assert!(
            board.tile(3, 2).smoke(),
            "smoke placed one tile west of shooter (behind the attack direction)"
        );
        assert!(
            !board.tile(3, 6).smoke(),
            "target tile must NOT be smoked — Ranged_Rocket smokes behind the shooter, not the target"
        );
    }

    #[test]
    fn test_rock_accelerator_spawns_rock_on_empty_target() {
        // Live Blitzkrieg regression: RockartMech fired Rock Launcher at an
        // empty D2 and the bridge materialized a neutral RockThrown there.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 6, 7, 2, WId::RangedRockthrow);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedRockthrow, 6, 4);

        let rock = board.units[..board.unit_count as usize]
            .iter()
            .find(|u| u.type_name_str() == "RockThrown")
            .expect("Rock Accelerator should spawn a RockThrown on an empty target");
        assert_eq!((rock.x, rock.y), (6, 4));
        assert_eq!(rock.team, Team::Neutral);
        assert_eq!((rock.hp, rock.max_hp), (1, 1));
        assert_eq!(rock.move_speed, 0);
        assert!(rock.pushable());
    }

    #[test]
    fn test_rock_accelerator_does_not_spawn_on_preblocked_target() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 6, 7, 2, WId::RangedRockthrow);
        board.tile_mut(6, 4).terrain = Terrain::Mountain;

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedRockthrow, 6, 4);

        assert!(
            board.units[..board.unit_count as usize]
                .iter()
                .all(|u| u.type_name_str() != "RockThrown"),
            "Rock Accelerator should not replace a pre-impact blocker"
        );
    }

    #[test]
    fn test_rock_accelerator_defers_boom_bot_decay_until_after_side_pushes() {
        // Mission_BoomBots capture: Rock Launcher kills a center Boom Bot while
        // a second Boom Bot is on a perpendicular side tile. The side bot is
        // pushed out before Explosive Decay resolves, so it survives.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 2, 4, 2, WId::RangedRockthrow);
        let center = add_enemy_type(&mut board, 1, 4, 4, 1, "Snowlaser1_Boom");
        let side = add_enemy_type(&mut board, 2, 4, 3, 1, "Snowtank1_Boom");
        board.tile_mut(4, 5).terrain = Terrain::Building;
        board.tile_mut(4, 5).building_hp = 2;
        board.grid_power = 7;

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedRockthrow, 4, 4);

        assert_eq!(board.units[center].hp, -1, "center Boom Bot dies to Rock Launcher");
        assert_eq!(
            (board.units[side].x, board.units[side].y, board.units[side].hp),
            (4, 2, 1),
            "perpendicular side Boom Bot is pushed out of decay range before the center explosion"
        );
        assert_eq!(
            board.tile(4, 5).building_hp,
            1,
            "center Explosive Decay still damages adjacent buildings after the side push"
        );
        assert_eq!(board.grid_power, 6);
    }

    #[test]
    fn test_rock_accelerator_spawn_inherits_active_acid_storm() {
        let mut board = make_test_board();
        board.mission_id = "Mission_AcidStorm".to_string();
        add_enemy_type(&mut board, 99, 2, 1, 3, "Storm_Generator");
        let mech_idx = add_mech(&mut board, 0, 6, 7, 2, WId::RangedRockthrow);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedRockthrow, 6, 4);

        let rock = board.units[..board.unit_count as usize]
            .iter()
            .find(|u| u.type_name_str() == "RockThrown")
            .expect("Rock Accelerator should spawn a RockThrown on an empty target");
        assert!(
            rock.acid(),
            "ACID Storm should immediately acidify newly spawned RockThrown"
        );
    }

    #[test]
    fn test_smoking_web_source_breaks_current_grapple() {
        // Corporate HQ regression: Rocket smoke lands behind the shooter on a
        // Scorpion Leader's tile, cancelling its queued web and freeing Pulse.
        let mut board = make_test_board();
        let rocket = add_mech(&mut board, 0, 5, 3, 3, WId::RangedRocket);
        let pulse = add_mech(&mut board, 2, 4, 2, 3, WId::ScienceRepulse);
        let boss = add_enemy_type(&mut board, 744, 5, 2, 7, "ScorpionBoss");
        let target = add_enemy(&mut board, 747, 5, 6, 3);

        board.units[pulse].base_move = 3;
        board.units[pulse].set_web(true);
        board.units[pulse].web_source_uid = board.units[boss].uid;
        board.units[pulse].move_speed = 0;
        board.units[boss].weapon = crate::board::WeaponId(WId::ScorpionAtkB as u16);

        let _ = simulate_weapon(&mut board, rocket, WId::RangedRocket, 5, 6);

        assert_eq!(board.units[target].hp, 1, "rocket target should still take normal damage");
        assert!(board.tile(5, 2).smoke(), "Rocket smoke should land on the web source tile");
        assert!(!board.units[pulse].web(), "smoking the web source should release the grapple");
        assert_eq!(board.units[pulse].web_source_uid, 0);
        assert_eq!(board.units[pulse].move_speed, board.units[pulse].base_move);
    }

    #[test]
    fn test_web_break_clears_duplicate_train_segments() {
        let mut board = make_test_board();
        let webber_uid = 900;
        let main = board.add_unit(Unit {
            uid: 508,
            x: 4,
            y: 2,
            hp: 1,
            max_hp: 1,
            team: Team::Player,
            ..Default::default()
        });
        let extra = board.add_unit(Unit {
            uid: 508,
            x: 4,
            y: 3,
            hp: 1,
            max_hp: 1,
            team: Team::Player,
            ..Default::default()
        });
        board.units[main].set_type_name("Train_Pawn");
        board.units[extra].set_type_name("Train_Pawn");
        board.units[main].set_web(true);
        board.units[main].web_source_uid = webber_uid;
        board.units[extra].set_web(true);

        break_web_from(&mut board, webber_uid);

        assert!(!board.units[main].web());
        assert!(!board.units[extra].web());
        assert_eq!(board.units[main].web_source_uid, 0);
        assert_eq!(board.units[extra].web_source_uid, 0);
    }

    #[test]
    fn test_move_next_to_webb_egg_becomes_webbed() {
        // Live Rusting Hulks regression: JetMech moved next to a WebbEgg1 and
        // the engine immediately marked it webbed. The sim must refresh egg
        // adjacency after movement, not only trust bridge status at turn read.
        let mut board = make_test_board();
        let jet = add_mech(&mut board, 0, 6, 0, 2, WId::BruteJetmech);
        board.units[jet].flags.insert(UnitFlags::CAN_MOVE);
        let egg = add_enemy_type(&mut board, 674, 5, 2, 1, "WebbEgg1");

        let _ = simulate_move(&mut board, jet, (6, 2));

        assert!(board.units[jet].web(), "landing beside WebbEgg1 should web Jet");
        assert_eq!(board.units[jet].web_source_uid, board.units[egg].uid);
    }

    #[test]
    fn test_killing_webb_egg_releases_adjacency_web() {
        let mut board = make_test_board();
        let jet = add_mech(&mut board, 0, 6, 0, 2, WId::BruteJetmech);
        let egg = add_enemy_type(&mut board, 674, 5, 2, 1, "WebbEgg1");
        let _ = simulate_move(&mut board, jet, (6, 2));
        assert!(board.units[jet].web());

        let mut result = ActionResult::default();
        let egg_pos = (board.units[egg].x, board.units[egg].y);
        apply_damage(
            &mut board, egg_pos.0, egg_pos.1, 1,
            &mut result, DamageSource::Weapon,
        );

        assert!(!board.units[jet].web(), "dead egg should release adjacent web");
        assert_eq!(board.units[jet].web_source_uid, 0);
    }

    #[test]
    fn test_webb_egg_does_not_steal_active_scorpion_grapple() {
        // Live m11t2: Pulse was adjacent to a WebbEgg, but the active grapple
        // was from a Scorpion targeting Pulse. Killing the egg freed Jet but
        // did not free Pulse.
        let mut board = make_test_board();
        let pulse = add_mech(&mut board, 2, 5, 3, 3, WId::ScienceRepulse);
        let scorpion = add_enemy_type(&mut board, 626, 6, 3, 3, "Scorpion1");
        let egg = add_enemy_type(&mut board, 674, 5, 2, 1, "WebbEgg1");
        board.units[pulse].set_web(true);
        board.units[pulse].web_source_uid = board.units[scorpion].uid;
        board.units[scorpion].queued_target_x = board.units[pulse].x as i8;
        board.units[scorpion].queued_target_y = board.units[pulse].y as i8;

        board.refresh_webb_egg_grapples();
        assert_eq!(board.units[pulse].web_source_uid, board.units[scorpion].uid);

        let mut result = ActionResult::default();
        let egg_pos = (board.units[egg].x, board.units[egg].y);
        apply_damage(
            &mut board, egg_pos.0, egg_pos.1, 1,
            &mut result, DamageSource::Weapon,
        );

        assert!(board.units[pulse].web(), "Scorpion web should survive egg death");
        assert_eq!(board.units[pulse].web_source_uid, board.units[scorpion].uid);
    }

    #[test]
    fn test_sim_artillery_rocket_no_smoke_when_shooter_on_edge() {
        // Rocket Mech at (3,0) (west edge, y=0) fires east. Behind-shooter
        // would be (3,-1) which is off-board — smoke must be skipped silently
        // (no panic, no phantom smoke).
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 0, 3, WId::RangedRocket);
        let enemy_idx = add_enemy(&mut board, 1, 3, 3, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedRocket, 3, 3);

        // Target still takes damage + push.
        assert_eq!(board.units[enemy_idx].hp, 1, "target took 2 damage even on edge shot");
        assert_eq!(
            (board.units[enemy_idx].x, board.units[enemy_idx].y),
            (3, 4),
            "target pushed east"
        );
        // No smoke anywhere on row 3 — especially not at shooter's own tile,
        // and no spurious smoke on target or intermediate tiles.
        for y in 0..8u8 {
            assert!(
                !board.tile(3, y).smoke(),
                "edge-case shot produced phantom smoke at (3,{})",
                y
            );
        }
    }

    #[test]
    fn test_taurus_edge_push_does_not_add_bump_damage() {
        // Live regression: Easy Rift Walkers run 20260510_213059_819,
        // R.S.T. Mission_Cataclysm turn 1. Taurus hit a Scorpion already on
        // the west edge; the engine dealt weapon damage but no off-board bump.
        let mut board = make_test_board();
        let tank = add_mech(&mut board, 0, 4, 3, 3, WId::BruteTankmech);
        let scorpion = add_enemy_type(&mut board, 684, 4, 0, 2, "Scorpion1");

        let result = simulate_weapon(&mut board, tank, WId::BruteTankmech, 4, 0);

        assert_eq!(
            (board.units[scorpion].x, board.units[scorpion].y, board.units[scorpion].hp),
            (4, 0, 1),
            "Taurus edge hit should deal weapon damage only"
        );
        assert_eq!(result.enemies_killed, 0);
    }

    #[test]
    fn test_taurus_killed_bombrock_explodes_before_push_and_chains() {
        // Corporate HQ / Tumblebug Leader turn 2: Tank at C7 fired Taurus at a
        // C6 BombRock with another BombRock at C5. Live exploded from C6 before
        // any corpse push, damaging Tank C7 and D6, then chained through C5 to
        // damage D5.
        let mut board = make_test_board();
        let tank = add_mech(&mut board, 0, 1, 5, 3, WId::BruteTankmech);
        let rock_c6 = add_bombrock(&mut board, 1745, 2, 5);
        let rock_c5 = add_bombrock(&mut board, 1744, 3, 5);

        {
            let d6 = board.tile_mut(2, 4);
            d6.terrain = Terrain::Building;
            d6.building_hp = 1;
        }
        {
            let d5 = board.tile_mut(3, 4);
            d5.terrain = Terrain::Building;
            d5.building_hp = 2;
        }

        let _result = simulate_action(
            &mut board,
            tank,
            (1, 5),
            WId::BruteTankmech,
            (2, 5),
            &WEAPONS,
        );

        assert_eq!(board.units[tank].hp, 2, "C6 BombRock explosion hits Tank at C7");
        assert!(board.units[rock_c6].hp <= 0, "directly hit C6 BombRock dies");
        assert!(board.units[rock_c5].hp <= 0, "C5 BombRock dies from chain explosion");
        assert_eq!(
            (board.units[rock_c6].x, board.units[rock_c6].y),
            (2, 5),
            "dead BombRock should not be pushed as a corpse"
        );
        assert_eq!(board.tile(2, 4).building_hp, 0, "C6 explosion destroys D6 building");
        assert_eq!(board.tile(2, 4).terrain, Terrain::Rubble, "D6 becomes rubble");
        assert_eq!(board.tile(3, 4).building_hp, 1, "C5 chain explosion damages D5 building");
    }

    #[test]
    fn test_taurus_hits_stable_nonpushable_without_moving_target() {
        // Live regression: Easy Rift Walkers run 20260510_213059_819,
        // Final Cave turn 2. Taurus hit the B6 FireflyBoss for damage, but the
        // engine's Stable/guarding state prevented the predicted push to A6.
        let mut board = make_test_board();
        let tank = add_mech(&mut board, 0, 2, 4, 3, WId::BruteTankmech);
        let boss = board.add_unit(Unit {
            uid: 1143,
            x: 2,
            y: 6,
            hp: 6,
            max_hp: 6,
            team: Team::Enemy,
            flags: UnitFlags::MASSIVE,
            ..Default::default()
        });
        board.units[boss].set_type_name("FireflyBoss");

        let result = simulate_weapon(&mut board, tank, WId::BruteTankmech, 2, 6);

        assert_eq!(
            (board.units[boss].x, board.units[boss].y, board.units[boss].hp),
            (2, 6, 5),
            "Stable/non-pushable FireflyBoss should take Taurus damage without moving"
        );
        assert_eq!(result.enemies_killed, 0);
    }

    #[test]
    fn test_artemis_a_direct_building_damage_is_zero() {
        let mut board = make_test_board();
        board.grid_power = 5;
        board.tile_mut(3, 5).terrain = Terrain::Building;
        board.tile_mut(3, 5).building_hp = 1;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::RangedArtillerymechA);

        let result = simulate_weapon(&mut board, mech_idx, WId::RangedArtillerymechA, 3, 5);

        assert_eq!(board.tile(3, 5).building_hp, 1);
        assert_eq!(board.tile(3, 5).terrain, Terrain::Building);
        assert_eq!(board.grid_power, 5);
        assert_eq!(result.grid_damage, 0);
    }

    #[test]
    fn test_weapon_damage_thaws_frozen_building_without_grid_loss() {
        let mut board = make_test_board();
        board.grid_power = 6;
        let mech_idx = add_mech(&mut board, 1, 3, 3, 3, WId::PrimePunchmech);
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;
        board.tile_mut(3, 4).set_frozen(true);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmech, 3, 4);

        assert_eq!(board.tile(3, 4).building_hp, 1);
        assert_eq!(board.tile(3, 4).terrain, Terrain::Building);
        assert!(!board.tile(3, 4).frozen());
        assert_eq!(board.grid_power, 6);
        assert_eq!(result.grid_damage, 0);
        assert_eq!(result.buildings_damaged, 0);
        assert_eq!(result.buildings_lost, 0);
        assert!(result.events.iter().any(|e| e == "building_thawed:3:4"));
    }

    #[test]
    fn test_artemis_a_push_bump_can_still_damage_building() {
        let mut board = make_test_board();
        board.grid_power = 5;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::RangedArtillerymechA);
        add_enemy(&mut board, 1, 3, 6, 2);
        board.tile_mut(3, 7).terrain = Terrain::Building;
        board.tile_mut(3, 7).building_hp = 1;

        let result = simulate_weapon(&mut board, mech_idx, WId::RangedArtillerymechA, 3, 5);

        assert_eq!(board.tile(3, 7).building_hp, 0);
        assert_eq!(board.grid_power, 4);
        assert_eq!(result.grid_damage, 1);
        assert_eq!(result.buildings_bump_damaged, 1);
    }

    #[test]
    fn test_artemis_adjacent_edge_push_does_not_bump_off_board() {
        // Live regression: Easy Rift Walkers run 20260510_213059_819,
        // R.S.T. Mission_Crack turn 3. Artemis targeted B5, pushing a Hornet
        // on adjacent A5 into the edge; the engine left it alive at 1 HP.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::RangedArtillerymech);
        let hornet = add_enemy_type(&mut board, 689, 3, 7, 1, "Hornet1");
        board.units[hornet].flags.insert(UnitFlags::FLYING);

        let result = simulate_weapon(&mut board, mech_idx, WId::RangedArtillerymech, 3, 6);

        assert_eq!(
            (board.units[hornet].x, board.units[hornet].y, board.units[hornet].hp),
            (3, 7, 1),
            "Artemis adjacent edge push should not add off-board bump damage"
        );
        assert_eq!(result.enemies_killed, 0);
    }

    #[test]
    fn test_artemis_off_axis_target_is_illegal_noop() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 2, 2, 4, 2, WId::RangedArtillerymech);
        let firefly = add_enemy_type(&mut board, 2214, 6, 3, 5, "Firefly2");
        let crab = add_enemy_type(&mut board, 2217, 6, 2, 3, "Crab1");

        let result = simulate_attack(
            &mut board,
            mech_idx,
            WId::RangedArtillerymech,
            (6, 2),
            &WEAPONS,
        );

        assert!(
            result.events.iter().any(|e| e.starts_with("illegal_weapon_target")),
            "Artemis D6->F2 should be rejected as off-axis"
        );
        assert_eq!(board.units[crab].hp, 3);
        assert_eq!(
            (board.units[firefly].x, board.units[firefly].y),
            (6, 3),
            "off-axis Artemis no-op should not push the adjacent Firefly"
        );
    }

    // ── Ranged_Rocket: push-bump when target is killed by the rocket ─────────
    // Regression: snapshot grid_drop_20260423_131700_144_t02_a1. Shooter (3,5)
    // fires Rocket Artillery at (3,1). Target is killed by the 2 weapon
    // damage, but the Forward push must still move the corpse one tile
    // toward smaller x — which is a mountain at (3,0). The bump must damage
    // the mountain (HP 2 → 1). Actual game applies this; regression pins the
    // simulator agrees.
    //
    // Diagnostic note: when these tests were written both snapshots
    // already exercised the correct `apply_damage` → `apply_push` ordering
    // in `_sim_artillery` (added in commit 2a86ca1) and the `any_unit_at`
    // dead-corpse handling in `apply_push`. Running `replay_solution` on
    // the reconstructed boards now produces the correct mountain HP 1 /
    // building HP 1 outcome. Recorded `predicted.json` files with HP 2
    // trace back to pre-fix solver versions (snapshot 1 ran on solver
    // rust-0.1.0-1d06ac9, pre-commit 2a86ca1). The tests here pin the fix
    // so a regression would be caught as a unit-test failure.
    #[test]
    fn test_rocket_kills_target_still_bumps_mountain_behind() {
        let mut board = make_test_board();
        // Shooter at (3,5), target tile (3,1). Forward = toward smaller x.
        let mech_idx = add_mech(&mut board, 0, 3, 5, 3, WId::RangedRocket);
        // Target: 2-HP pushable enemy — dies on 2 weapon damage (no armor).
        let _enemy_idx = add_enemy(&mut board, 1, 3, 1, 2);
        // Push destination (3,0) = mountain (HP 2). Forward push is blocked.
        board.tile_mut(3, 0).terrain = Terrain::Mountain;
        board.tile_mut(3, 0).building_hp = 2;

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedRocket, 3, 1);

        // Mountain should be damaged (HP 2 → 1) by the bump from the pushed
        // (dead) corpse.
        assert_eq!(
            board.tile(3, 0).building_hp, 1,
            "mountain behind a killed Rocket target must take 1 bump damage"
        );
        assert_eq!(board.tile(3, 0).terrain, Terrain::Mountain);
    }

    // Regression: snapshot grid_drop_20260421_194613_599_t03_a2. Shooter (3,4)
    // fires at (3,2). Target Leaper1 (HP 1) is killed by 2 damage. The
    // dead-corpse push forward (toward smaller x) into the building at (3,1)
    // should bump both the building (HP 2 → 1) and (no-op) the dead corpse.
    #[test]
    fn test_rocket_kills_target_still_bumps_building_behind() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 4, 3, WId::RangedRocket);
        // 1-HP target — dies instantly.
        let _enemy_idx = add_enemy(&mut board, 1, 3, 2, 1);
        board.tile_mut(3, 1).terrain = Terrain::Building;
        board.tile_mut(3, 1).building_hp = 2;

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedRocket, 3, 2);

        assert_eq!(
            board.tile(3, 1).building_hp, 1,
            "building behind a killed Rocket target must take 1 bump damage"
        );
        assert_eq!(board.tile(3, 1).terrain, Terrain::Building);
    }

    #[test]
    fn test_upgraded_rocket_damage_plus_blocked_bump_kills_alpha_scorpion() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 4, 5, 3, WId::RangedRocketA);
        let scorpion = add_enemy_type(&mut board, 757, 2, 5, 4, "Scorpion2");
        board.tile_mut(1, 5).terrain = Terrain::Mountain;
        board.tile_mut(1, 5).building_hp = 2;

        let result = simulate_weapon(&mut board, mech_idx, WId::RangedRocketA, 2, 5);

        assert_eq!(board.units[scorpion].hp, 0);
        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.tile(1, 5).building_hp, 1);
        assert!(board.tile(5, 5).smoke(), "upgraded Rocket still smokes behind shooter");
    }

    #[test]
    fn test_rocket_live_edge_target_takes_damage_without_edge_bump() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 1, 1, 4, 3, WId::RangedRocket);
        let moth = add_enemy_type(&mut board, 337, 7, 4, 3, "Moth1");
        board.units[moth].flags.insert(UnitFlags::FLYING);

        let result = simulate_weapon(&mut board, mech_idx, WId::RangedRocket, 7, 4);

        assert_eq!(board.units[moth].hp, 1);
        assert_eq!((board.units[moth].x, board.units[moth].y), (7, 4));
        assert_eq!(result.enemies_killed, 0);
        assert!(board.tile(0, 4).smoke(), "Rocket still smokes behind the shooter");
    }

    #[test]
    fn test_rocket_killed_target_bumps_live_mech_blocker() {
        let mut board = make_test_board();
        // Shooter west of target; forward push moves target east into Pulse.
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::RangedRocket);
        let _target = add_enemy(&mut board, 1, 3, 5, 2);
        let pulse = add_mech(&mut board, 2, 3, 6, 1, WId::ScienceRepulse);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedRocket, 3, 5);

        assert_eq!(
            board.units[pulse].hp, 0,
            "Rocket center corpse should bump and kill a 1-HP mech blocker"
        );
    }

    #[test]
    fn test_rocket_killed_nonpushable_target_bumps_building() {
        let mut board = make_test_board();
        board.grid_power = 7;
        // Shooter south of target; forward push moves target north into a
        // two-HP building. Non-pushable live targets are immune, but Rocket's
        // killed center target still resolves the corpse bump.
        let mech_idx = add_mech(&mut board, 0, 7, 5, 3, WId::RangedRocket);
        let target = add_enemy_type(&mut board, 1, 5, 5, 2, "Jelly_Armor1");
        board.units[target].flags.remove(UnitFlags::PUSHABLE);
        board.tile_mut(4, 5).terrain = Terrain::Building;
        board.tile_mut(4, 5).building_hp = 2;

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedRocket, 5, 5);

        assert_eq!(
            board.tile(4, 5).building_hp, 1,
            "Rocket-killed non-pushable target should bump the building behind it"
        );
        assert_eq!(
            board.grid_power, 7,
            "damaging a non-unique 2-HP building should not drop grid until destroyed"
        );
    }

    #[test]
    fn test_arachnid_psion_player_kill_spawns_spiderling_egg_immediately() {
        // Live regression: Hard Rusting Hulks run 20260512_104120_903,
        // R.S.T. Corporate HQ turn 4. Rocket at D8 fired at Firefly on D4;
        // the corpse bumped the Arachnid Psion on D3, and the engine spawned
        // SpiderlingEgg1 uid 84 on D4 before the next mech acted.
        let mut board = make_test_board();
        board.spider_psion = true;
        let rocket = add_mech(&mut board, 1, 0, 4, 3, WId::RangedRocket);
        let _firefly = add_enemy_type(&mut board, 78, 4, 4, 3, "Firefly1");
        let psion = add_enemy_type(&mut board, 80, 5, 4, 2, "Jelly_Spider1");
        board.units[psion].flags.insert(UnitFlags::FLYING);
        let _hornet_a = add_enemy_type(&mut board, 82, 4, 5, 2, "Hornet1");
        let _hornet_b = add_enemy_type(&mut board, 83, 4, 2, 2, "Hornet1");

        let result = simulate_attack(&mut board, rocket, WId::RangedRocket, (4, 4), &WEAPONS);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.pending_spider_eggs.len(), 0);
        let egg = board.unit_at(4, 4).expect("Arachnid Psion egg should spawn on death tile");
        assert_eq!(board.units[egg].uid, 84);
        assert_eq!(board.units[egg].type_name_str(), "SpiderlingEgg1");
        assert_eq!(board.units[egg].hp, 1);
    }

    #[test]
    fn test_arachnid_psion_egg_follows_rocket_killed_corpse_push() {
        // Live regression: Hard Rusting Hulks run 20260513_144310_771,
        // R.S.T. Mission_Solar turn 3. Rocket at C6 fired at Leaper on C2;
        // the killed Leaper corpse moved to C1, and the engine spawned the
        // SpiderlingEgg1 on C1 before the next mech acted.
        let mut board = make_test_board();
        board.spider_psion = true;
        let rocket = add_mech(&mut board, 1, 2, 5, 3, WId::RangedRocket);
        let target = add_enemy_type(&mut board, 878, 6, 5, 2, "Leaper2");
        let psion = add_enemy_type(&mut board, 879, 5, 6, 2, "Jelly_Spider1");
        board.units[psion].flags.insert(UnitFlags::FLYING);

        let result = simulate_attack(&mut board, rocket, WId::RangedRocket, (6, 5), &WEAPONS);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!((board.units[target].x, board.units[target].y), (7, 5));
        assert_eq!(board.units[target].hp, 0);
        assert_eq!(board.pending_spider_eggs.len(), 0);
        assert!(board.unit_at(6, 5).is_none(), "C2 should be empty after the corpse push");
        let egg = board.unit_at(7, 5).expect("Arachnid Psion egg should follow the corpse to C1");
        assert_eq!(board.units[egg].uid, 880);
        assert_eq!(board.units[egg].type_name_str(), "SpiderlingEgg1");
        assert_eq!(board.units[egg].hp, 1);
    }

    #[test]
    fn test_blob_boss_death_spawns_two_medium_goos() {
        let mut board = make_test_board();
        let _boss = add_enemy_type(&mut board, 200, 4, 4, 1, "BlobBoss");
        board.units[0].flags.insert(UnitFlags::MASSIVE);
        let mut result = ActionResult::default();

        apply_damage(&mut board, 4, 4, 1, &mut result, DamageSource::Weapon);

        assert_eq!(result.enemies_killed, 1);
        let children: Vec<_> = board.units[..board.unit_count as usize]
            .iter()
            .filter(|u| u.hp > 0 && u.type_name_str() == "BlobBossMed")
            .collect();
        assert_eq!(children.len(), 2);
        assert_eq!((children[0].x, children[0].y), (4, 2));
        assert_eq!((children[1].x, children[1].y), (3, 3));
        for child in children {
            assert_eq!(child.hp, 2);
            assert_eq!(child.max_hp, 2);
            assert_eq!(child.move_speed, 3);
            assert_eq!(child.base_move, 3);
            assert!(child.massive());
            assert!(child.pushable());
            assert!(!child.has_queued_attack());
            assert_eq!(child.queued_target_x, -1);
            assert_eq!(child.weapon, WeaponId(WId::BlobBossAtkMed as u16));
        }
        assert!(result.events.iter().any(|e| e.contains("blob_split:200:BlobBoss")));
    }

    #[test]
    fn test_medium_goo_splits_and_small_goo_does_not() {
        let mut board = make_test_board();
        let _med = add_enemy_type(&mut board, 201, 4, 4, 1, "BlobBossMed");
        let mut result = ActionResult::default();

        apply_damage(&mut board, 4, 4, 1, &mut result, DamageSource::Weapon);

        let smalls = board.units[..board.unit_count as usize]
            .iter()
            .filter(|u| u.hp > 0 && u.type_name_str() == "BlobBossSmall")
            .count();
        assert_eq!(smalls, 2);

        let mut board = make_test_board();
        let _small = add_enemy_type(&mut board, 202, 4, 4, 1, "BlobBossSmall");
        let mut result = ActionResult::default();
        apply_damage(&mut board, 4, 4, 1, &mut result, DamageSource::Weapon);
        assert_eq!(board.unit_count, 1, "Small Goo should not split further");
    }

    #[test]
    fn test_blob_boss_split_uses_backup_radius_when_primary_blocked() {
        let mut board = make_test_board();
        for x in 0u8..8 {
            for y in 0u8..8 {
                let dist = (x as i8 - 4).unsigned_abs() + (y as i8 - 4).unsigned_abs();
                if (1..=2).contains(&dist) {
                    board.tile_mut(x, y).terrain = Terrain::Water;
                }
            }
        }
        let _boss = add_enemy_type(&mut board, 203, 4, 4, 1, "BlobBoss");
        let mut result = ActionResult::default();

        apply_damage(&mut board, 4, 4, 1, &mut result, DamageSource::Weapon);

        let children: Vec<_> = board.units[..board.unit_count as usize]
            .iter()
            .filter(|u| u.hp > 0 && u.type_name_str() == "BlobBossMed")
            .collect();
        assert_eq!(children.len(), 2);
        for child in children {
            let dist = (child.x as i8 - 4).unsigned_abs()
                + (child.y as i8 - 4).unsigned_abs();
            assert!(
                (3..=4).contains(&dist),
                "child at ({}, {}) should use backup radius",
                child.x,
                child.y
            );
        }
    }

    #[test]
    fn test_blob_boss_instant_death_still_splits() {
        let mut board = make_test_board();
        let _boss = add_enemy_type(&mut board, 204, 4, 4, 1, "BlobBoss");
        board.units[0].flags.insert(UnitFlags::MASSIVE);
        board.tile_mut(4, 5).terrain = Terrain::Chasm;
        let mut result = ActionResult::default();

        apply_push(&mut board, 4, 4, 0, &mut result);

        assert_eq!(result.enemies_killed, 1);
        let children = board.units[..board.unit_count as usize]
            .iter()
            .filter(|u| u.hp > 0 && u.type_name_str() == "BlobBossMed")
            .count();
        assert_eq!(children, 2);
    }

    #[test]
    fn test_jetmech_smokes_transit_base_range() {
        // Aerial Bombs tooltip: "Fly over a target, dropping an explosive
        // smoke bomb." Smoke goes on the TRANSIT tile(s), NOT landing or start.
        // Base range: S=(3,3) → T=(3,4) → L=(3,5). Smoke only on T=(3,4).
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteJetmech, 3, 5);
        assert!(
            board.tile(3, 4).smoke(),
            "Jetmech base-range leap: smoke should be on transit tile (3,4)"
        );
        assert!(
            !board.tile(3, 5).smoke(),
            "Jetmech base-range leap: smoke must NOT be on landing tile (3,5)"
        );
        assert!(
            !board.tile(3, 3).smoke(),
            "Jetmech base-range leap: smoke must NOT be on starting tile (3,3)"
        );
    }

    #[test]
    fn test_aerial_bombs_landing_on_time_pod_collects() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        board.tile_mut(3, 5).set_has_pod(true);

        let result = simulate_weapon(&mut board, mech_idx, WId::BruteJetmech, 3, 5);

        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (3, 5));
        assert!(!board.tile(3, 5).has_pod());
        assert_eq!(result.pods_collected, 1);
        assert!(result.events.iter().any(|e| e == "pod_collected:3:5"));
    }

    #[test]
    fn test_jetmech_smokes_transit_range_upgraded() {
        // Range-upgraded Aerial Bombs (e.g. +1 range power): S=(3,3) → T1=(3,4)
        // → T2=(3,5) → L=(3,6). Smoke on BOTH transit tiles, not on L or S.
        // We call sim_leap directly with a distance-3 cardinal leap to
        // exercise the multi-transit-tile branch; sim_leap itself performs
        // no range enforcement.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);

        // Clone the default def and expand range so the leap covers 3 tiles.
        let upgraded = WEAPONS[WId::BruteJetmech as usize];
        let mut result = ActionResult::default();
        sim_leap(&mut board, mech_idx, WId::BruteJetmech, &upgraded, 3, 6, &mut result);

        assert!(
            board.tile(3, 4).smoke(),
            "Jetmech range-upgraded leap: smoke should be on first transit tile (3,4)"
        );
        assert!(
            board.tile(3, 5).smoke(),
            "Jetmech range-upgraded leap: smoke should be on second transit tile (3,5)"
        );
        assert!(
            !board.tile(3, 6).smoke(),
            "Jetmech range-upgraded leap: smoke must NOT be on landing tile (3,6)"
        );
        assert!(
            !board.tile(3, 3).smoke(),
            "Jetmech range-upgraded leap: smoke must NOT be on starting tile (3,3)"
        );
    }

    #[test]
    fn test_aerial_bombs_damages_transit_tile_base_range() {
        // Aerial Bombs tooltip: "Fly over a target, dropping an explosive
        // smoke bomb." Base range (uid 17) is exactly distance 2 cardinal:
        // S=(3,3) → T=(3,4) (transit) → L=(3,5). Damage = 1 lands on the
        // TRANSIT tile only. Landing tile and all 4-neighbors of landing
        // (the legacy behavior) take NO damage.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);

        // Enemy on transit tile — takes 1 damage.
        let transit_enemy = add_enemy(&mut board, 10, 3, 4, 3);
        // Enemies on landing tile is illegal (enumerator blocks it), but we
        // can place enemies on 4-neighbors of the landing tile to assert
        // they are unaffected by the new damage emission.
        let north_of_land = add_enemy(&mut board, 11, 2, 5, 3); // (2,5) north of land
        let south_of_land = add_enemy(&mut board, 12, 4, 5, 3); // (4,5) south of land
        let east_of_land  = add_enemy(&mut board, 13, 3, 6, 3); // (3,6) east of land
        // West of land is (3,4) which IS the transit tile — already covered.

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteJetmech, 3, 5);

        assert_eq!(
            board.units[transit_enemy].hp, 2,
            "Transit tile (3,4) enemy should take 1 damage"
        );
        assert_eq!(
            board.units[north_of_land].hp, 3,
            "North-of-landing (2,5) enemy must take NO damage (was landing-neighbor under legacy behavior)"
        );
        assert_eq!(
            board.units[south_of_land].hp, 3,
            "South-of-landing (4,5) enemy must take NO damage"
        );
        assert_eq!(
            board.units[east_of_land].hp, 3,
            "East-of-landing (3,6) enemy must take NO damage"
        );
    }

    #[test]
    fn test_aerial_bombs_damages_both_transit_tiles_range_upgraded() {
        // Range-upgraded Aerial Bombs: S=(3,3) → T1=(3,4) → T2=(3,5) → L=(3,6).
        // Damage = 1 lands on BOTH transit tiles; landing tile is untouched.
        // Following the pattern of test_jetmech_smokes_transit_range_upgraded,
        // we call sim_leap directly (it performs no range enforcement).
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);

        let t1_enemy = add_enemy(&mut board, 20, 3, 4, 3);
        let t2_enemy = add_enemy(&mut board, 21, 3, 5, 3);

        let upgraded = WEAPONS[WId::BruteJetmech as usize];
        let mut result = ActionResult::default();
        sim_leap(&mut board, mech_idx, WId::BruteJetmech, &upgraded, 3, 6, &mut result);

        assert_eq!(
            board.units[t1_enemy].hp, 2,
            "First transit tile (3,4) enemy should take 1 damage"
        );
        assert_eq!(
            board.units[t2_enemy].hp, 2,
            "Second transit tile (3,5) enemy should take 1 damage"
        );
    }

    #[test]
    fn test_prime_leap_keeps_landing_adjacent_damage() {
        // Regression guard: Prime_Leap (Hydraulic Legs) tooltip reads
        // "Leap to a tile, damaging self and adjacent tiles (with push)."
        // It has no SMOKE flag, so it must retain the legacy
        // 4-cardinal-neighbors-of-landing damage. This locks in that the
        // smoke-gated transit-damage path does not regress Prime_Leap.
        //
        // Use an adjacent leap: S=(3,3) → L=(3,4). `direction_between` is
        // only defined for unit-vector adjacency, so from_dir is the
        // cardinal back at (3,3) and gets skipped cleanly. Landing-adjacents
        // are (2,4) (north), (4,4) (south), (3,5) (east); (3,3) (west, the
        // from_dir) is the skipped direction.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeLeap);

        let adj_n = add_enemy(&mut board, 30, 2, 4, 3); // north of landing
        let adj_s = add_enemy(&mut board, 31, 4, 4, 3); // south of landing
        let adj_e = add_enemy(&mut board, 32, 3, 5, 3); // east of landing

        let upgraded = WEAPONS[WId::PrimeLeap as usize];
        let mut result = ActionResult::default();
        sim_leap(&mut board, mech_idx, WId::PrimeLeap, &upgraded, 3, 4, &mut result);

        assert_eq!(board.units[adj_n].hp, 2, "Prime_Leap: landing-adjacent N must take 1 dmg");
        assert_eq!(board.units[adj_s].hp, 2, "Prime_Leap: landing-adjacent S must take 1 dmg");
        assert_eq!(board.units[adj_e].hp, 2, "Prime_Leap: landing-adjacent E must take 1 dmg");
    }

    #[test]
    fn test_prime_leap_ground_landing_on_water_is_unfired_action() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 3, 5, WId::PrimeLeap);
        board.tile_mut(4, 3).terrain = Terrain::Water;

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimeLeap, 4, 3);

        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (5, 3));
        assert_eq!(board.units[mech_idx].hp, 5);
        assert!(
            result.events.iter().any(|e| e == "illegal_leap_landing:4:3:water"),
            "invalid water landing should be recorded as an unfired leap"
        );
    }

    #[test]
    fn test_prime_leap_self_damage_strips_shield_before_acid_pool_pickup() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeLeap);
        board.units[mech_idx].set_shield(true);
        board.tile_mut(5, 3).set_acid(true);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeLeap, 5, 3);

        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (5, 3));
        assert_eq!(board.units[mech_idx].hp, 5, "shield absorbs the Leap recoil");
        assert!(!board.units[mech_idx].shield(), "Leap recoil should strip shield");
        assert!(board.units[mech_idx].acid(), "landing ACID should apply after shield is stripped");
        assert!(!board.tile(5, 3).acid(), "ACID pool should be consumed on landing");
    }

    #[test]
    fn test_prime_leap_nanobots_revive_before_fire_landing_pickup() {
        let mut board = make_test_board();
        board.viscera_nanobots_heal = 2;
        let mech_idx = add_mech(&mut board, 0, 5, 1, 1, WId::PrimeLeap);
        board.units[mech_idx].max_hp = 5;
        board.tile_mut(5, 3).set_on_fire(true);
        let firefly_idx = add_enemy(&mut board, 562, 5, 2, 1);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimeLeap, 5, 3);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.units[firefly_idx].hp, 0);
        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (5, 3));
        assert_eq!(
            board.units[mech_idx].hp, 2,
            "Nanobots should revive Leap after self-damage before landing fire applies"
        );
        assert!(
            board.units[mech_idx].fire(),
            "revived Hydraulic Legs mech should catch fire from the landing tile"
        );
        assert!(
            result.events.iter().any(|e| e == "viscera_nanobots_heal:0:1:2"),
            "the landing-adjacent kill should produce a boosted Nanobots heal"
        );
    }

    #[test]
    fn test_prime_leap_nanobots_revive_clears_existing_fire_before_landing() {
        let mut board = make_test_board();
        board.viscera_nanobots_heal = 2;
        let mech_idx = add_mech(&mut board, 0, 5, 1, 1, WId::PrimeLeap);
        board.units[mech_idx].max_hp = 5;
        board.units[mech_idx].set_fire(true);
        let spider_idx = add_enemy(&mut board, 563, 5, 2, 1);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimeLeap, 5, 3);

        assert_eq!(result.enemies_killed, 1);
        assert_eq!(board.units[spider_idx].hp, 0);
        assert_eq!(board.units[mech_idx].hp, 2);
        assert!(
            !board.units[mech_idx].fire(),
            "Nanobots revive should clear fire carried by the temporary mech death"
        );
        assert!(
            result.events.iter().any(|e| e == "viscera_nanobots_heal:0:1:2"),
            "the landing-adjacent kill should still produce a boosted Nanobots heal"
        );
    }

    #[test]
    fn test_prime_leap_cracked_landing_death_is_not_nanobot_revived() {
        let mut board = make_test_board();
        board.viscera_nanobots_heal = 2;
        let mech_idx = add_mech(&mut board, 0, 5, 0, 2, WId::PrimeLeap);
        board.units[mech_idx].max_hp = 3;
        board.tile_mut(5, 2).set_cracked(true);
        board.tile_mut(6, 2).set_cracked(true);
        let totem_idx = add_enemy_type(&mut board, 489, 6, 2, 1, "Totem1");
        board.units[totem_idx].flags |= UnitFlags::MINOR;

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimeLeap, 5, 2);

        assert_eq!(
            board.tile(5, 2).terrain,
            Terrain::Chasm,
            "self-damage opens the cracked landing tile"
        );
        assert_eq!(
            board.tile(6, 2).terrain,
            Terrain::Chasm,
            "Hydraulic Legs also cracks the occupied landing-adjacent target tile"
        );
        assert_eq!(board.units[totem_idx].hp, 0, "landing-adjacent Totem is killed");
        assert_eq!(
            board.units[mech_idx].hp,
            0,
            "Nanobots must not revive a mech that fell into a chasm"
        );
        assert_eq!(result.mechs_killed, 1);
        assert!(
            result
                .events
                .iter()
                .any(|e| e == "viscera_nanobots_blocked_by_terrain:0:1"),
            "terrain-blocked Nanobots revive should be explicit in replay events"
        );
    }

    #[test]
    fn test_prime_leap_moves_acid_pool_with_killed_pushed_target() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 2, 5, WId::PrimeLeap);
        let mosquito_idx = add_enemy_type(&mut board, 290, 6, 2, 2, "Mosquito1");
        board.units[mosquito_idx].set_acid(true);
        board.units[mosquito_idx].flags |= UnitFlags::FLYING;

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeLeap, 7, 2);

        assert_eq!(board.units[mosquito_idx].hp, 0);
        assert_eq!((board.units[mosquito_idx].x, board.units[mosquito_idx].y), (5, 2));
        assert!(!board.tile(6, 2).acid(), "vacated kill tile should not keep a new ACID pool");
        assert!(board.tile(5, 2).acid(), "ACID pool should follow the pushed corpse");
    }

    #[test]
    fn test_prime_leap_killed_target_corpse_bumps_live_blocker() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 3, 3, WId::PrimeLeap);
        let blocker_idx = add_mech(&mut board, 1, 3, 4, 3, WId::BruteUnstable);
        let leaper_idx = add_enemy_type(&mut board, 140, 4, 4, 1, "Leaper1");

        let wdef = WEAPONS[WId::PrimeLeap as usize];
        let mut result = ActionResult::default();
        sim_leap(&mut board, mech_idx, WId::PrimeLeap, &wdef, 5, 4, &mut result);

        assert_eq!(board.units[leaper_idx].hp, 0, "landing damage kills the Leaper");
        assert_eq!(board.units[blocker_idx].hp, 2, "killed Leaper corpse bumps the live blocker");
        assert_eq!((board.units[leaper_idx].x, board.units[leaper_idx].y), (4, 4));
    }

    #[test]
    fn test_prime_leap_push_into_disabled_mech_wreck_bumps_target() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 5, 3, WId::PrimeLeap);
        let boss_idx = add_enemy_type(&mut board, 137, 2, 5, 6, "BeetleBoss");
        board.units[boss_idx].set_acid(true);
        let wreck_idx = add_mech(&mut board, 2, 1, 5, 0, WId::ScienceAcidShot);
        board.units[wreck_idx].set_active(false);
        board.units[wreck_idx].set_type_name("NanoMech");
        board.units[wreck_idx].max_hp = 2;

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimeLeap, 3, 5);

        assert_eq!(board.units[boss_idx].hp, 3);
        assert_eq!((board.units[boss_idx].x, board.units[boss_idx].y), (2, 5));
        assert_eq!(board.units[wreck_idx].hp, 0);
        assert_eq!(result.enemy_damage_dealt, 3);
    }

    #[test]
    fn test_webbed_prime_leap_noops() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::PrimeLeap);
        board.units[mech_idx].set_web(true);
        board.units[mech_idx].web_source_uid = 99;
        let adj_n = add_enemy(&mut board, 30, 2, 4, 3);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimeLeap, 3, 4);

        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (3, 3));
        assert_eq!(board.units[mech_idx].hp, 3, "no-op Hydraulic Legs should not self-damage");
        assert!(board.units[mech_idx].web(), "no-op Hydraulic Legs should leave web intact");
        assert_eq!(board.units[adj_n].hp, 3, "no-op Hydraulic Legs should not damage landing-adjacent units");
        assert!(
            result.events.iter().any(|e| e == "illegal_leap_landing:3:4:webbed"),
            "expected webbed illegal-leap event, got {:?}",
            result.events
        );
    }

    #[test]
    fn test_off_axis_prime_leap_noops() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 3, 3, WId::PrimeLeap);
        let adj_n = add_enemy(&mut board, 30, 3, 1, 3);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimeLeap, 4, 1);

        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (5, 3));
        assert_eq!(board.units[mech_idx].hp, 3, "off-axis Hydraulic Legs should not self-damage");
        assert_eq!(board.units[adj_n].hp, 3, "off-axis Hydraulic Legs should not damage landing-adjacent units");
        assert!(
            result.events.iter().any(|e| e == "illegal_leap_landing:4:1:off_axis"),
            "expected off-axis illegal-leap event, got {:?}",
            result.events
        );
    }

    #[test]
    fn test_bombing_run_damages_every_transit_tile() {
        // Brute_Bombrun (Bombing Run) tooltip: "Leap over any distance
        // dropping a bomb on each tile you pass." Damage = 1 on each tile
        // along the cardinal flight path (strictly between source and
        // landing); landing tile and landing-neighbors take no damage.
        // Gated on DAMAGES_TRANSIT (not SMOKE — Bombing Run does not emit
        // smoke). sim_leap performs no range enforcement so we call it
        // directly for a long leap.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteBombrun);

        // Transit tiles on S=(3,3) → L=(3,6): (3,4) and (3,5). Each takes 1 dmg.
        let t1_enemy = add_enemy(&mut board, 40, 3, 4, 3);
        let t2_enemy = add_enemy(&mut board, 41, 3, 5, 3);
        // Landing-adjacents: (2,6) N, (4,6) S. Neither should take damage
        // under the DAMAGES_TRANSIT branch.
        let north_of_land = add_enemy(&mut board, 42, 2, 6, 3);
        let south_of_land = add_enemy(&mut board, 43, 4, 6, 3);

        let wdef = WEAPONS[WId::BruteBombrun as usize];
        let mut result = ActionResult::default();
        sim_leap(&mut board, mech_idx, WId::BruteBombrun, &wdef, 3, 6, &mut result);

        assert_eq!(
            board.units[t1_enemy].hp, 2,
            "Bombing Run transit tile (3,4) enemy should take 1 damage"
        );
        assert_eq!(
            board.units[t2_enemy].hp, 2,
            "Bombing Run transit tile (3,5) enemy should take 1 damage"
        );
        assert_eq!(
            board.units[north_of_land].hp, 3,
            "Landing-adjacent N (2,6) must take NO damage (legacy path is disabled)"
        );
        assert_eq!(
            board.units[south_of_land].hp, 3,
            "Landing-adjacent S (4,6) must take NO damage"
        );
        // Regression guard: Bombing Run must not emit smoke on transit tiles.
        assert!(
            !board.tile(3, 4).smoke(),
            "Bombing Run must not emit smoke on transit (SMOKE flag is off)"
        );
        assert!(
            !board.tile(3, 5).smoke(),
            "Bombing Run must not emit smoke on second transit either"
        );
    }

    #[test]
    fn test_freeze_water_creates_ice() {
        let mut board = make_test_board();
        board.tile_mut(3, 6).terrain = Terrain::Water;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::RangedIce);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedIce, 3, 6);
        assert_eq!(board.tile(3, 6).terrain, Terrain::Ice, "Freeze on water should create ice");
    }

    #[test]
    fn test_forest_consumed_on_weapon_damage() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Forest;
        add_enemy(&mut board, 1, 3, 4, 3);
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::PrimePunchmech);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmech, 3, 4);
        assert!(board.tile(3, 4).on_fire(), "Forest should ignite from weapon damage");
        assert_eq!(board.tile(3, 4).terrain, Terrain::Ground, "Burning forest should become Ground");
    }

    #[test]
    fn test_aerial_bombs_smoke_consumes_transit_forest_without_fire() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Forest;
        add_enemy(&mut board, 1, 3, 4, 1);
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);

        let _ = simulate_action(&mut board, mech_idx, (3, 3), WId::BruteJetmech, (3, 5), &WEAPONS);

        assert_eq!(board.tile(3, 4).terrain, Terrain::Ground, "Aerial Bombs consumes transit Forest");
        assert!(board.tile(3, 4).smoke(), "Aerial Bombs still leaves smoke on the transit tile");
        assert!(!board.tile(3, 4).on_fire(), "Aerial Bombs smoke prevents transit Forest ignition");
    }

    #[test]
    fn test_aerial_bombs_frozen_objective_building_damage_defers_grid() {
        // Rusting Hulks There Is No Try run 20260519_133059_179,
        // Mission_FreezeBldg turn 1: Aerial Bombs flew over a frozen objective
        // building. Live immediately thawed and damaged the building, but the
        // grid meter charged the HP loss only when the enemy turn began.
        let mut board = make_test_board();
        board.mission_id = "Mission_FreezeBldg".to_string();
        board.grid_power = 6;
        board.freeze_building_target = 5;
        let bidx = xy_to_idx(3, 4);
        board.freeze_building_tiles |= 1u64 << bidx;
        {
            let tile = board.tile_mut(3, 4);
            tile.terrain = Terrain::Building;
            tile.building_hp = 2;
            tile.set_frozen(true);
        }
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);

        let result = simulate_action(
            &mut board,
            mech_idx,
            (3, 3),
            WId::BruteJetmech,
            (3, 5),
            &WEAPONS,
        );

        assert!(!board.tile(3, 4).frozen(), "transit objective building should thaw");
        assert!(board.tile(3, 4).smoke(), "Aerial Bombs should smoke the transit building");
        assert_eq!(board.tile(3, 4).building_hp, 1, "transit objective building should lose HP");
        assert_eq!(board.grid_power, 6, "grid loss is deferred until enemy-turn settle");
        assert_eq!(result.grid_damage, 0, "per-action grid damage should not fire immediately");
        assert_eq!(result.buildings_damaged, 1);
        assert_eq!(board.deferred_bump_grid_debt[bidx], 1);

        let mut settle = ActionResult::default();
        flush_deferred_bump_grid_debt(&mut board, &mut settle);
        assert_eq!(board.grid_power, 5);
        assert_eq!(settle.grid_damage, 1);
    }

    #[test]
    fn test_aerial_bombs_landing_on_smoke_extinguishes_carried_fire() {
        // Hard Rusting Hulks run 20260513_230944_542, Mission_Airstrike turn 2:
        // Jet was on fire at H3 and Aerial-Bombed to an already-smoked F3.
        // The bridge reported Jet's fire cleared after landing.
        let mut board = make_test_board();
        let jet = add_mech(&mut board, 0, 5, 0, 3, WId::BruteJetmech);
        board.units[jet].set_fire(true);
        board.tile_mut(5, 2).set_smoke(true);

        let _ = simulate_action(&mut board, jet, (5, 0), WId::BruteJetmech, (5, 2), &WEAPONS);

        assert_eq!((board.units[jet].x, board.units[jet].y), (5, 2));
        assert!(!board.units[jet].fire(), "landing on smoke must extinguish carried fire");
        assert!(board.tile(5, 1).smoke(), "Aerial Bombs still smokes the transit tile");
        assert!(board.tile(5, 2).smoke(), "pre-existing landing smoke should remain");
    }

    #[test]
    fn test_aerial_bombs_landing_resolves_fire_and_breaks_web() {
        // Hard Rusting Hulks live run 20260512_181719_119, Mission_Survive
        // turn 3: Rocket ignited a Forest landing tile at F2, then JetMech
        // used Aerial Bombs while webbed and landed there at 1 HP. The engine
        // cleared the web and set Jet on fire, so the next fire tick killed it.
        let mut board = make_test_board();
        let jet = add_mech(&mut board, 0, 6, 4, 1, WId::BruteJetmech);
        board.units[jet].set_web(true);
        board.units[jet].web_source_uid = 99;
        board.units[jet].move_speed = 0;
        board.units[jet].base_move = 3;
        board.tile_mut(6, 2).terrain = Terrain::Forest;
        board.tile_mut(6, 2).set_on_fire(true);

        let _ = simulate_action(&mut board, jet, (6, 4), WId::BruteJetmech, (6, 2), &WEAPONS);

        assert_eq!((board.units[jet].x, board.units[jet].y), (6, 2));
        assert!(board.units[jet].fire(), "Aerial Bombs landing on fire must ignite Jet");
        assert!(!board.units[jet].web(), "Aerial Bombs tile change must break Jet's web");
        assert_eq!(board.units[jet].web_source_uid, 0);
        assert_eq!(board.units[jet].move_speed, 3);
        assert_eq!(board.tile(6, 2).terrain, Terrain::Ground, "burning Forest landing is consumed");
        assert!(board.tile(6, 2).on_fire(), "consumed landing tile remains on fire");
    }

    #[test]
    fn test_sand_becomes_smoke_on_weapon_damage() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Sand;
        add_enemy(&mut board, 1, 3, 4, 3);
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::PrimePunchmech);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmech, 3, 4);
        assert!(board.tile(3, 4).smoke(), "Sand should become smoke from weapon damage");
        assert_eq!(board.tile(3, 4).terrain, Terrain::Ground, "Sand should become ground");
    }

    #[test]
    fn test_aerial_bombs_occupied_sand_transit_preserves_sand() {
        // Hard Rusting Hulks live run 20260512_181719_119, Mission_Holes
        // turn 2: JetMech E3 -> C3 over shielded PulseMech on sandy D3.
        // Live consumed Pulse's shield and placed smoke, but D3 stayed Sand.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Sand;
        let jet = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        let pulse = add_mech(&mut board, 1, 3, 4, 3, WId::ScienceRepulse);
        board.units[pulse].set_shield(true);

        let _ = simulate_weapon(&mut board, jet, WId::BruteJetmech, 3, 5);

        assert_eq!(board.tile(3, 4).terrain, Terrain::Sand, "Occupied Aerial Bombs transit sand is preserved");
        assert!(board.tile(3, 4).smoke(), "Aerial Bombs still smokes occupied sand transit");
        assert!(!board.units[pulse].shield(), "Aerial Bombs transit damage consumes the shield");
        assert_eq!(board.units[pulse].hp, 3, "Shielded Pulse should not take HP damage");
    }

    #[test]
    fn test_charge_recoil_on_sand_creates_smoke() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Sand;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteBeetle);
        add_enemy(&mut board, 1, 3, 5, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteBeetle, 3, 5);

        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (3, 4));
        assert_eq!(board.tile(3, 4).terrain, Terrain::Ground, "Ramming recoil should consume sand");
        assert!(board.tile(3, 4).smoke(), "Ramming recoil on sand should create smoke");
    }

    #[test]
    fn test_frozen_unit_on_water_creates_ice() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Water;
        let idx = add_enemy(&mut board, 1, 3, 3, 3);
        board.units[idx].set_frozen(true);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        // Frozen unit on water → ice, unit survives
        assert_eq!(board.tile(3, 4).terrain, Terrain::Ice);
        assert!(board.units[idx].hp > 0, "Frozen unit should survive on newly-created ice");
    }

    #[test]
    fn test_acid_unit_death_creates_pool() {
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 3, 3, 1);
        board.units[idx].set_acid(true);

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 2, &mut result, DamageSource::Weapon);
        assert!(board.tile(3, 3).acid(), "ACID unit death should create acid pool");
    }

    // ── Vice Fist (Prime_Shift) Throw mechanic ────────────────────────────────

    #[test]
    fn test_vice_fist_throws_to_clear_tile_behind_attacker() {
        // JudoMech at (3,3) attacks east at Hornet at (4,3).
        // Throw destination = (2,3), behind attacker (opposite of attack dir).
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let enemy_idx = add_enemy(&mut board, 99, 4, 3, 2);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeShift, 4, 3);
        assert_eq!(board.units[mech_idx].x, 3, "JudoMech stays at (3,3)");
        assert_eq!(board.units[mech_idx].y, 3);
        assert_eq!(board.units[enemy_idx].x, 2, "Hornet thrown to (2,3) behind JudoMech");
        assert_eq!(board.units[enemy_idx].y, 3);
        assert_eq!(board.units[enemy_idx].hp, 1, "Hornet took 1 dmg from Vice Fist");
    }

    #[test]
    fn test_vice_fist_blocked_by_mountain_behind() {
        // Mountain at (2,3) blocks throw → enemy stays + bump.
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Mountain;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let enemy_idx = add_enemy(&mut board, 99, 4, 3, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeShift, 4, 3);
        assert_eq!(board.units[enemy_idx].x, 4, "Hornet stays at (4,3) — throw blocked");
        assert_eq!(board.units[enemy_idx].hp, 1, "3 HP - 1 weapon - 1 bump = 1");
    }

    #[test]
    fn test_vice_fist_throws_into_water_drowns() {
        // Water at (2,3); non-flying enemy thrown there → dies.
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Water;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let enemy_idx = add_enemy(&mut board, 99, 4, 3, 5);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeShift, 4, 3);
        assert_eq!(board.units[enemy_idx].x, 2, "Enemy moved to water tile");
        assert_eq!(board.units[enemy_idx].hp, 0, "Drowned in water (non-flying)");
    }

    #[test]
    fn test_vice_fist_blocked_by_edge_bumps() {
        // JudoMech at (0,3) facing east; throw destination (-1,3) is off-board.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 0, 3, 5, WId::PrimeShift);
        let enemy_idx = add_enemy(&mut board, 99, 1, 3, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeShift, 1, 3);
        assert_eq!(board.units[enemy_idx].x, 1, "Stays at (1,3) — off-board edge");
        assert_eq!(board.units[enemy_idx].hp, 1, "3 - 1 weapon - 1 bump = 1");
    }

    #[test]
    fn test_vice_fist_blocked_by_unit_behind() {
        // Unit already behind attacker → throw blocked, both bump.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let target_idx = add_enemy(&mut board, 99, 4, 3, 4);
        let blocker_idx = add_enemy(&mut board, 100, 2, 3, 4);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeShift, 4, 3);
        assert_eq!(board.units[target_idx].x, 4, "Target stays at (4,3) — blocked");
        assert_eq!(board.units[target_idx].hp, 2, "Target: 4 - 1 weapon - 1 bump = 2");
        assert_eq!(board.units[blocker_idx].hp, 3, "Blocker: 4 - 1 bump = 3");
    }

    // ── Vice Fist target-enumeration rejection ────────────────────────────────
    // The game surfaces a "no target available" error when the throw destination
    // is blocked, even though the sim's apply_throw fallback would resolve it as
    // a bump. The solver must match the game and skip those targets entirely.

    fn throw_targets(board: &Board, mech_pos: (u8, u8), mech_from: (u8, u8)) -> Vec<(u8, u8)> {
        crate::solver::get_weapon_targets(board, mech_pos.0, mech_pos.1, WId::PrimeShift, mech_from, &WEAPONS)
    }

    #[test]
    fn test_vice_fist_enum_rejects_enemy_behind() {
        // Enemy already on the destination tile → target not offered.
        let mut board = make_test_board();
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 4, 3, 3); // target east
        let _blocker = add_enemy(&mut board, 100, 2, 3, 3); // blocker west (throw dest)

        let targets = throw_targets(&board, (3, 3), (3, 3));
        assert!(!targets.contains(&(4, 3)), "East target must be rejected — (2,3) occupied");
    }

    #[test]
    fn test_vice_fist_enum_rejects_building_behind() {
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Building;
        board.tile_mut(2, 3).building_hp = 1;
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 4, 3, 3);

        let targets = throw_targets(&board, (3, 3), (3, 3));
        assert!(!targets.contains(&(4, 3)), "East target must be rejected — building at (2,3)");
    }

    #[test]
    fn test_vice_fist_enum_rejects_mountain_behind() {
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Mountain;
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 4, 3, 3);

        let targets = throw_targets(&board, (3, 3), (3, 3));
        assert!(!targets.contains(&(4, 3)), "East target must be rejected — mountain at (2,3)");
    }

    #[test]
    fn test_vice_fist_enum_rejects_wreck_behind() {
        let mut board = make_test_board();
        // Dead unit = wreck
        board.add_unit(Unit {
            uid: 200, x: 2, y: 3, hp: 0, max_hp: 3,
            team: Team::Enemy,
            ..Default::default()
        });
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 4, 3, 3);

        let targets = throw_targets(&board, (3, 3), (3, 3));
        assert!(!targets.contains(&(4, 3)), "East target must be rejected — wreck at (2,3)");
    }

    #[test]
    fn test_vice_fist_enum_rejects_edge_behind() {
        // Mech at column 0 facing east → throw dest (-1, 3) off-board.
        let mut board = make_test_board();
        let _mech = add_mech(&mut board, 0, 0, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 1, 3, 3);

        let targets = throw_targets(&board, (0, 3), (0, 3));
        assert!(!targets.contains(&(1, 3)), "East target must be rejected — off-board behind");
    }

    #[test]
    fn test_vice_fist_enum_allows_water_behind() {
        // Water at the destination IS a valid target — main strategic use.
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Water;
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 4, 3, 3);

        let targets = throw_targets(&board, (3, 3), (3, 3));
        assert!(targets.contains(&(4, 3)), "Water destination must be allowed");
    }

    #[test]
    fn test_vice_fist_enum_allows_chasm_behind() {
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Chasm;
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 4, 3, 3);

        let targets = throw_targets(&board, (3, 3), (3, 3));
        assert!(targets.contains(&(4, 3)), "Chasm destination must be allowed");
    }

    #[test]
    fn test_vice_fist_enum_allows_destination_is_mech_from() {
        // Mech originally at (3, 3), moves to (4, 3), attacks east at (5, 3).
        // Throw destination = (3, 3) = mech_from. After the move executes, (3, 3)
        // is vacated, so the throw must be allowed even though the stale board
        // still shows the mech there.
        let mut board = make_test_board();
        let _mech = add_mech(&mut board, 0, 3, 3, 5, WId::PrimeShift);
        let _target = add_enemy(&mut board, 99, 5, 3, 3);

        // Simulate post-move position at (4, 3), mech_from still (3, 3).
        let targets = throw_targets(&board, (4, 3), (3, 3));
        assert!(targets.contains(&(5, 3)), "Throw dest == mech_from must be allowed");
    }

    // ── Cluster Artillery (Ranged_Defensestrike) ──────────────────────────────
    // SiegeMech weapon: targets a CENTER tile (which is NOT damaged) and hits
    // the 4 cardinal-adjacent tiles with 1 damage + push outward. Used to
    // protect a building/objective by clearing enemies around it.

    #[test]
    fn test_ranged_ignite_adjacent_edge_push_does_not_bump() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 6, 0, 3, WId::RangedIgnite);
        let edge_enemy = add_enemy(&mut board, 1, 7, 2, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedIgnite, 6, 2);

        assert_eq!(board.units[edge_enemy].hp, 3, "zero-damage air push must not edge-bump");
        assert_eq!((board.units[edge_enemy].x, board.units[edge_enemy].y), (7, 2));
    }

    #[test]
    fn test_ranged_ignite_adjacent_non_edge_push_still_moves() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 4, 2, 3, WId::RangedIgnite);
        let enemy = add_enemy(&mut board, 1, 5, 4, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedIgnite, 4, 4);

        assert_eq!(board.units[enemy].hp, 3, "zero-damage adjacent push stays non-damaging");
        assert_eq!((board.units[enemy].x, board.units[enemy].y), (6, 4));
    }

    #[test]
    fn test_ranged_ignite_backburn_fires_behind_shooter_only() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::RangedIgniteA);
        let adjacent = add_enemy(&mut board, 1, 4, 5, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedIgniteA, 3, 5);

        assert!(board.tile(3, 5).on_fire(), "target tile catches fire");
        assert!(board.tile(3, 2).on_fire(), "Backburn lights tile behind shooter");
        assert!(
            !board.tile(4, 5).on_fire(),
            "adjacent pushed tiles do not inherit Vulcan's fire status"
        );
        assert_eq!(
            (board.units[adjacent].x, board.units[adjacent].y),
            (5, 5),
            "adjacent unit still gets pushed outward"
        );
    }

    #[test]
    fn test_ranged_ignite_backburn_lights_mountain_behind_shooter() {
        let mut board = make_test_board();
        board.tile_mut(3, 2).terrain = Terrain::Mountain;
        board.tile_mut(3, 2).building_hp = 2;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::RangedIgniteA);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedIgniteA, 3, 5);

        assert_eq!(board.tile(3, 2).terrain, Terrain::Mountain);
        assert_eq!(board.tile(3, 2).building_hp, 2);
        assert!(board.tile(3, 2).on_fire(), "Backburn lights intact mountains");
    }

    #[test]
    fn test_fire_weapon_on_sand_consumes_sand_to_burning_ground() {
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Sand;
        let mech_idx = add_mech(&mut board, 0, 2, 4, 3, WId::PrimeFlamethrower);
        let enemy = add_enemy(&mut board, 1, 3, 4, 2);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeFlamethrower, 3, 4);

        assert_eq!(board.tile(3, 4).terrain, Terrain::Ground);
        assert!(board.tile(3, 4).on_fire());
        assert_eq!(board.units[enemy].hp, 2, "base Flamethrower still deals no direct damage");
    }

    #[test]
    fn test_flamethrower_pushed_ground_target_catches_new_tile_fire() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 3, 3, WId::PrimeFlamethrower);
        let enemy = add_enemy(&mut board, 1, 5, 2, 2);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeFlamethrower, 5, 2);

        assert_eq!((board.units[enemy].x, board.units[enemy].y), (5, 1));
        assert!(board.tile(5, 2).on_fire(), "Flamethrower should ignite the struck tile");
        assert!(board.units[enemy].fire(), "Ground target should catch newly lit tile fire");
    }

    #[test]
    fn test_boosted_flamethrower_kills_three_hp_burning_target() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 3, 3, WId::PrimeFlamethrower);
        board.units[mech_idx].set_boosted(true);
        let enemy = add_enemy(&mut board, 1, 5, 2, 3);
        board.units[enemy].set_fire(true);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeFlamethrower, 5, 2);

        assert!(
            board.units[enemy].hp <= 0,
            "Boosted Flamethrower should deal FireDamage 2 + Boost 1 to burning targets"
        );
    }

    #[test]
    fn test_boosted_flamethrower_does_not_damage_non_burning_target() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 3, 3, WId::PrimeFlamethrower);
        board.units[mech_idx].set_boosted(true);
        let enemy = add_enemy(&mut board, 1, 5, 2, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeFlamethrower, 5, 2);

        assert_eq!(
            board.units[enemy].hp, 3,
            "Boost should not turn zero-damage Flamethrower into damage unless FireDamage triggers"
        );
        assert!(board.units[enemy].fire());
    }

    #[test]
    fn test_upgraded_flamethrower_damages_burning_units_in_path() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 3, 3, WId::PrimeFlamethrowerA);
        let enemy = add_enemy(&mut board, 1, 5, 2, 2);
        board.units[enemy].set_fire(true);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeFlamethrowerA, 5, 1);

        assert!(
            board.units[enemy].hp <= 0,
            "range-upgraded Flamethrower should apply FireDamage to burning units before the clicked tile"
        );
        assert!(board.tile(5, 2).on_fire());
        assert!(board.tile(5, 1).on_fire());
    }

    #[test]
    fn test_upgraded_flamethrower_ignites_building_path_without_damage() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 3, 3, WId::PrimeFlamethrowerA);
        {
            let tile = board.tile_mut(5, 2);
            tile.terrain = Terrain::Building;
            tile.building_hp = 2;
        }

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimeFlamethrowerA, 5, 1);

        assert!(board.tile(5, 2).on_fire());
        assert_eq!(board.tile(5, 2).building_hp, 2);
        assert_eq!(result.grid_damage, 0);
    }

    #[test]
    fn test_flamethrower_pushed_flying_target_does_not_carry_new_tile_fire() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 3, 3, WId::PrimeFlamethrower);
        let enemy = add_enemy(&mut board, 1, 5, 2, 2);
        board.units[enemy].flags.insert(UnitFlags::FLYING);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeFlamethrower, 5, 2);

        assert_eq!((board.units[enemy].x, board.units[enemy].y), (5, 1));
        assert!(board.tile(5, 2).on_fire(), "Flamethrower should ignite the struck tile");
        assert!(!board.units[enemy].fire(), "Flying target should not carry newly lit tile fire");
    }

    #[test]
    fn test_flamethrower_blocked_flying_target_on_water_catches_fire_but_water_does_not() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 6, 3, WId::PrimeFlamethrower);
        let enemy = add_enemy(&mut board, 1, 4, 6, 2);
        board.units[enemy].flags.insert(UnitFlags::FLYING);
        board.tile_mut(4, 6).terrain = Terrain::Water;
        board.tile_mut(3, 6).terrain = Terrain::Mountain;

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeFlamethrower, 4, 6);

        assert_eq!((board.units[enemy].x, board.units[enemy].y), (4, 6));
        assert!(board.units[enemy].fire(), "Blocked flying target should catch direct flame");
        assert!(
            !board.tile(4, 6).on_fire(),
            "Water under the target should not become a burning tile"
        );
    }

    #[test]
    fn test_science_swap_water_kill_triggers_blast_psion_explosion() {
        let mut board = make_test_board();
        board.blast_psion = true;
        add_enemy_type(&mut board, 90, 7, 7, 2, "Jelly_Explode1");
        board.tile_mut(2, 1).terrain = Terrain::Water;
        board.tile_mut(1, 1).terrain = Terrain::Building;
        board.tile_mut(1, 1).building_hp = 1;

        let mech_idx = add_mech(&mut board, 0, 2, 1, 2, WId::ScienceSwap);
        let enemy = add_enemy(&mut board, 1, 2, 2, 2);

        let result = simulate_weapon(&mut board, mech_idx, WId::ScienceSwap, 2, 2);

        assert_eq!(board.units[enemy].hp, 0, "swapped enemy drowns on the mech's old water tile");
        assert_eq!((board.units[enemy].x, board.units[enemy].y), (2, 1));
        assert_eq!(board.units[mech_idx].hp, 1, "Blast Psion explosion damages adjacent Swap Mech");
        assert_eq!(board.tile(1, 1).building_hp, 0, "Blast Psion explosion damages adjacent building");
        assert_eq!(result.enemies_killed, 1);
        assert_eq!(result.grid_damage, 1);
    }

    #[test]
    fn test_science_swap_diagonal_target_is_noop() {
        // Science_Swap.GetTargetArea only emits tiles in the four cardinal
        // lines. A diagonal bridge FireWeapon ACK should not be modeled as a
        // real swap/teleport.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 1, 4, 2, WId::ScienceSwapAB);
        let enemy = add_enemy(&mut board, 1, 2, 5, 2);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceSwapAB, 2, 5);

        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (1, 4));
        assert_eq!((board.units[enemy].x, board.units[enemy].y), (2, 5));
    }

    #[test]
    fn test_science_swap_range_upgrade_still_allows_cardinal_range_four() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 1, 4, 2, WId::ScienceSwapAB);
        let enemy = add_enemy(&mut board, 1, 1, 0, 2);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceSwapAB, 1, 0);

        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (1, 0));
        assert_eq!((board.units[enemy].x, board.units[enemy].y), (1, 4));
    }

    #[test]
    fn test_science_swap_breaks_web_on_swapped_target() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 5, 2, WId::ScienceSwapA);
        let enemy = add_enemy_type(&mut board, 731, 5, 3, 5, "Moth2");
        let egg = add_enemy_type(&mut board, 787, 4, 3, 1, "WebbEgg1");
        board.units[enemy].set_web(true);
        board.units[enemy].web_source_uid = board.units[egg].uid;

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceSwapA, 5, 3);

        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (5, 3));
        assert_eq!((board.units[enemy].x, board.units[enemy].y), (5, 5));
        assert!(!board.units[enemy].web(), "Science Swap target changed tiles and should break web");
        assert_eq!(board.units[enemy].web_source_uid, 0);
    }

    #[test]
    fn test_dam_flood_drowning_triggers_blast_psion_explosion() {
        let mut board = make_test_board();
        board.blast_psion = true;
        add_enemy_type(&mut board, 90, 7, 7, 2, "Jelly_Explode1");
        let drowned = add_enemy_type(&mut board, 91, 4, 4, 5, "Shaman2");
        board.tile_mut(5, 4).terrain = Terrain::Building;
        board.tile_mut(5, 4).building_hp = 2;
        board.unique_buildings |= 1u64 << xy_to_idx(5, 4);

        let mut result = ActionResult::default();
        flood_tile(&mut board, 4, 4, &mut result);

        assert_eq!(board.tile(4, 4).terrain, Terrain::Water);
        assert_eq!(board.units[drowned].hp, 0, "dam flood drowns grounded Vek");
        assert_eq!(
            board.tile(5, 4).building_hp,
            1,
            "drowned Vek must emit its Blast Psion aura explosion"
        );
        assert_eq!(result.enemies_killed, 1);
        assert_eq!(result.grid_damage, 1, "direct blast damage drains grid per building HP");
        assert_eq!(board.grid_power, 6);
    }

    #[test]
    fn test_dam_flood_extinguishes_forest_ignited_by_same_attack() {
        let mut board = make_test_board();
        let mut result = ActionResult::default();
        board.tile_mut(4, 3).terrain = Terrain::Forest;

        apply_damage(&mut board, 4, 3, 1, &mut result, DamageSource::Weapon);
        assert!(board.tile(4, 3).on_fire(), "weapon damage should ignite Forest first");

        flood_tile(&mut board, 4, 3, &mut result);

        assert_eq!(board.tile(4, 3).terrain, Terrain::Water);
        assert!(
            !board.tile(4, 3).on_fire(),
            "dam flood converts the tile to Water and extinguishes fire"
        );
    }

    #[test]
    fn test_dam_flood_minor_totem_does_not_receive_blast_psion_aura() {
        let mut board = make_test_board();
        board.grid_power = 7;
        board.dam_primary = Some((3, 0));
        board.blast_psion = true;
        add_enemy_type(&mut board, 90, 7, 7, 2, "Jelly_Explode1");

        let rocket = add_mech(&mut board, 1, 3, 4, 3, WId::None);
        let pulse = add_mech(&mut board, 2, 4, 2, 3, WId::None);
        board.units[rocket].flags.insert(UnitFlags::MASSIVE);
        board.units[pulse].flags.insert(UnitFlags::MASSIVE);
        board.units[pulse].set_shield(true);

        let totem = add_enemy_type(&mut board, 91, 4, 1, 1, "Totem2");
        board.units[totem].flags.insert(UnitFlags::MINOR);
        let burnbug = add_enemy_type(&mut board, 92, 4, 3, 4, "Burnbug2");
        let shaman = add_enemy_type(&mut board, 93, 4, 4, 5, "Shaman2");

        board.tile_mut(5, 4).terrain = Terrain::Building;
        board.tile_mut(5, 4).building_hp = 2;
        board.unique_buildings |= 1u64 << xy_to_idx(5, 4);

        let mut result = ActionResult::default();
        trigger_dam_flood(&mut board, &mut result);

        assert_eq!(board.units[totem].hp, 0);
        assert_eq!(board.units[burnbug].hp, 0);
        assert_eq!(board.units[shaman].hp, 0);
        assert_eq!(board.units[pulse].hp, 3, "only Burnbug's non-minor aura burst should pop Pulse shield");
        assert!(!board.units[pulse].shield());
        assert_eq!(board.units[rocket].hp, 2, "Shaman's non-minor aura burst damages Rocket");
        assert_eq!(board.tile(5, 4).building_hp, 1, "Shaman's burst damages the Robotics Lab-style building");
        assert_eq!(result.enemies_killed, 3);
        assert_eq!(result.mech_damage_taken, 1);
        assert_eq!(result.grid_damage, 1);
        assert_eq!(board.grid_power, 6);
    }

    #[test]
    fn test_blast_psion_explosion_chains_through_eligible_aura_deaths() {
        let mut board = make_test_board();
        board.blast_psion = true;
        add_enemy_type(&mut board, 90, 7, 7, 2, "Jelly_Explode1");
        let first = add_enemy(&mut board, 1, 3, 3, 1);
        let adjacent = add_enemy(&mut board, 2, 4, 3, 1);
        board.tile_mut(5, 3).terrain = Terrain::Building;
        board.tile_mut(5, 3).building_hp = 1;

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 1, &mut result, DamageSource::Weapon);

        assert_eq!(board.units[first].hp, 0, "initial weapon kill dies");
        assert_eq!(
            board.units[adjacent].hp, 0,
            "adjacent enemy dies to the first Blast Psion explosion"
        );
        assert_eq!(
            board.tile(5, 3).building_hp, 0,
            "enemy killed by Blast Psion explosion emits a second eligible aura explosion"
        );
        assert_eq!(result.enemies_killed, 2);
        assert_eq!(result.grid_damage, 1);
    }

    #[test]
    fn test_titan_fist_dash_blast_psion_chain_hits_secondary_building() {
        let mut board = make_test_board();
        board.blast_psion = true;
        add_enemy_type(&mut board, 90, 5, 1, 1, "Jelly_Explode1");
        let mech_idx = add_mech(&mut board, 0, 4, 2, 3, WId::PrimePunchmechA);
        let burnbug = add_enemy_type(&mut board, 1, 4, 5, 2, "Burnbug1");
        let moth = add_enemy_type(&mut board, 2, 4, 6, 1, "Moth1");
        let leaper = add_enemy_type(&mut board, 3, 5, 5, 1, "Leaper1");
        board.tile_mut(5, 6).terrain = Terrain::Building;
        board.tile_mut(5, 6).building_hp = 1;
        board.unique_buildings |= 1u64 << xy_to_idx(5, 6);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimePunchmechA, 4, 3);

        assert_eq!((board.units[mech_idx].x, board.units[mech_idx].y), (4, 4));
        assert!(board.units[burnbug].hp <= 0, "Dash Punch kills the first blocker at C4");
        assert!(board.units[moth].hp <= 0, "Burnbug's burst kills adjacent Moth at B4");
        assert!(board.units[leaper].hp <= 0, "Burnbug's burst kills adjacent Leaper at C3");
        assert_eq!(board.tile(5, 6).building_hp, 0, "secondary B4/C3 bursts damage B3");
        assert_eq!(result.grid_damage, 1);
    }

    #[test]
    fn test_flamethrower_kill_push_defers_blast_psion_explosion_to_final_tile() {
        let mut board = make_test_board();
        board.blast_psion = true;
        add_enemy_type(&mut board, 90, 7, 7, 2, "Jelly_Explode1");
        board.tile_mut(3, 6).terrain = Terrain::Building;
        board.tile_mut(3, 6).building_hp = 2;

        let mech_idx = add_mech(&mut board, 0, 2, 5, 5, WId::PrimeFlamethrower);
        let enemy = add_enemy(&mut board, 1, 2, 6, 1);
        board.units[enemy].set_fire(true);

        let result = simulate_weapon(&mut board, mech_idx, WId::PrimeFlamethrower, 2, 6);

        assert_eq!(board.units[enemy].hp, -1, "burning target dies to Flamethrower bonus damage");
        assert_eq!((board.units[enemy].x, board.units[enemy].y), (2, 7));
        assert_eq!(board.units[mech_idx].hp, 5, "pre-push adjacent mech should not eat the explosion");
        assert_eq!(board.tile(3, 6).building_hp, 2, "pre-push adjacent building should not eat the explosion");
        assert_eq!(result.grid_damage, 0);
    }

    #[test]
    fn test_flamethrower_killed_target_bumps_live_mech_blocker() {
        // Regression: Perfect Strategy run 20260517_175633_388,
        // Mission_Teleporter turn 4. FlameMech at D5 fires at burning
        // Scorpion1 on E5; the killed Scorpion corpse is still pushed into
        // TeleMech on F5, killing the 1-HP mech. This is Flamethrower-specific
        // and must not change Cluster Artillery's outer corpse absorption.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 4, 3, WId::PrimeFlamethrower);
        let scorpion = add_enemy_type(&mut board, 3088, 3, 3, 2, "Scorpion1");
        board.units[scorpion].set_fire(true);
        let tele = add_mech(&mut board, 2, 3, 2, 1, WId::ScienceSwap);

        let _ = simulate_weapon(&mut board, mech_idx, WId::PrimeFlamethrower, 3, 3);

        assert_eq!(board.units[scorpion].hp, 0, "burning target dies to Flamethrower bonus damage");
        assert_eq!(board.units[tele].hp, 0, "killed Flamethrower target should corpse-bump the live mech blocker");
    }

    #[test]
    fn test_cluster_artillery_no_damage_to_center() {
        // Center has an enemy — should NOT take damage.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 0, 0, 2, WId::RangedDefensestrike);
        let center_idx = add_enemy(&mut board, 99, 4, 4, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedDefensestrike, 4, 4);
        assert_eq!(board.units[center_idx].hp, 3, "Center tile NOT damaged");
        assert_eq!(board.units[center_idx].x, 4, "Center NOT pushed");
        assert_eq!(board.units[center_idx].y, 4);
    }

    #[test]
    fn test_cluster_artillery_damages_and_pushes_adjacent() {
        // 4 enemies adjacent to center (4,4) at N/S/E/W — each takes 1 damage
        // and is pushed OUTWARD (away from center).
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 0, 0, 2, WId::RangedDefensestrike);
        let n = add_enemy(&mut board, 1, 4, 5, 3); // north of center
        let s = add_enemy(&mut board, 2, 4, 3, 3); // south
        let e = add_enemy(&mut board, 3, 5, 4, 3); // east
        let w = add_enemy(&mut board, 4, 3, 4, 3); // west

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedDefensestrike, 4, 4);
        // Each enemy: 3 - 1 (weapon) = 2 HP, then pushed 1 tile outward
        assert_eq!(board.units[n].hp, 2);
        assert_eq!(board.units[n].y, 6, "N enemy pushed further north (5→6)");
        assert_eq!(board.units[s].hp, 2);
        assert_eq!(board.units[s].y, 2, "S enemy pushed further south (3→2)");
        assert_eq!(board.units[e].hp, 2);
        assert_eq!(board.units[e].x, 6, "E enemy pushed east (5→6)");
        assert_eq!(board.units[w].hp, 2);
        assert_eq!(board.units[w].x, 2, "W enemy pushed west (3→2)");
    }

    #[test]
    fn test_cluster_artillery_protects_building_in_center() {
        // Building in center, enemies around it. Building should NOT take damage.
        let mut board = make_test_board();
        board.tile_mut(4, 4).terrain = Terrain::Building;
        board.tile_mut(4, 4).building_hp = 1;
        let mech_idx = add_mech(&mut board, 0, 0, 0, 2, WId::RangedDefensestrike);
        let attacker = add_enemy(&mut board, 1, 4, 5, 3); // adjacent to building

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedDefensestrike, 4, 4);
        assert_eq!(board.tile(4, 4).building_hp, 1, "Building survives intact");
        assert_eq!(board.units[attacker].hp, 2, "Adjacent enemy damaged");
        // Adjacent enemy at (4,5) pushed north away from center → (4,6)
        assert_eq!(board.units[attacker].y, 6, "Pushed north (away from center)");
    }

    #[test]
    fn test_cluster_artillery_kills_outer_corpse_absorbed_by_blocker() {
        // Regression: snapshot grid_drop_20260421_131027_968_t03_a0.
        //
        // Cluster Artillery fires at (4,4). The outer tile (3,4) holds a
        // 1-HP enemy that dies to damage_outer=1; outward push from the
        // centre at (4,4) points (3,4) further west → (2,4), where a live
        // blocker sits. Previously the sim bumped both the dead pusher
        // (a no-op on apply_damage since damage 0 early-returns) AND the
        // live blocker for 1 HP. Game truth: dead corpse is consumed by
        // the live blocker, neither takes bump damage.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 0, 0, 2, WId::RangedDefensestrike);
        // Outer tile (3,4) has a 1-HP enemy that will die from damage_outer=1.
        let dying = add_enemy(&mut board, 1, 3, 4, 1);
        // Blocker at (2,4) — the push destination when (3,4) is pushed west.
        let blocker = add_enemy(&mut board, 2, 2, 4, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedDefensestrike, 4, 4);
        // Dying enemy killed by damage_outer, stayed at (3,4) as a corpse.
        assert_eq!(board.units[dying].hp, 0, "Outer enemy killed by damage_outer");
        // Critical: blocker UNHARMED — the dead pusher's corpse is absorbed.
        assert_eq!(board.units[blocker].hp, 3, "Live blocker takes no bump from corpse");
        assert_eq!(board.units[blocker].x, 2, "Blocker did not move");
        assert_eq!(board.units[blocker].y, 4, "Blocker did not move");
    }

    #[test]
    fn test_cluster_artillery_live_outer_unit_still_bumps_live_blocker() {
        // Parity check: when the outer unit SURVIVES damage_outer, it DOES
        // bump a live blocker. Only the dead-corpse case is special.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 0, 0, 2, WId::RangedDefensestrike);
        // 3-HP enemy survives damage_outer=1 (HP 2 after)
        let pusher = add_enemy(&mut board, 1, 3, 4, 3);
        let blocker = add_enemy(&mut board, 2, 2, 4, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::RangedDefensestrike, 4, 4);
        // Pusher: 3 − 1 (damage_outer) − 1 (bump) = 1
        assert_eq!(board.units[pusher].hp, 1, "Live pusher took damage + bump");
        assert_eq!(board.units[pusher].x, 3, "Pusher did not move");
        // Blocker: 3 − 1 (bump) = 2
        assert_eq!(board.units[blocker].hp, 2, "Live blocker took bump");
    }

    // ── Grav Well (Science_Gravwell) ───────────────────────────────────────────
    // Gravity Mech weapon: artillery (range ≥2) that pulls the targeted unit
    // ONE TILE toward the attacker. No damage on a clear pull; bump damage if
    // the destination is blocked. The Lua (weapons_science.lua:115-124) uses
    // SpaceDamage with a directional push, NOT AddCharge — so this is single
    // tile, unlike Brute_Grapple which is full-pull via AddCharge.

    #[test]
    fn test_grav_well_pulls_target_toward_attacker() {
        // GravMech at (3,3) pulls target at (3,6) one tile toward mech → (3,5).
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::ScienceGravwell);
        let enemy_idx = add_enemy(&mut board, 99, 3, 6, 4);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceGravwell, 3, 6);
        assert_eq!(board.units[enemy_idx].x, 3, "Stays in column");
        assert_eq!(board.units[enemy_idx].y, 5,
            "Single-tile pull (6→5, toward mech at y=3)");
        assert_eq!(board.units[enemy_idx].hp, 4, "No damage from Grav Well itself");
    }

    #[test]
    fn test_grav_well_no_pull_into_blocker() {
        // Unit blocking the destination → both bump. Target at (3,6), blocker
        // at (3,5). Pull tries 6→5 but (3,5) is blocked → both bump.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::ScienceGravwell);
        let blocker = add_enemy(&mut board, 1, 3, 5, 3);
        let target = add_enemy(&mut board, 2, 3, 6, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceGravwell, 3, 6);
        assert_eq!(board.units[target].y, 6, "Target stays — destination blocked");
        assert_eq!(board.units[target].hp, 2, "Bump damage");
        assert_eq!(board.units[blocker].hp, 2, "Blocker bumped too");
    }

    // ── Grav Well: live-game repro of m13 t03 desync ────────────────────────────
    // Failure_db rows from a 2026-04-27 Pinnacle Robotics run show pulled units
    // landing one tile FURTHER from the puller than the simulator predicted —
    // i.e., the actual game pulled them only ONE tile, not all the way to
    // mech-adjacent. Re-reading weapons_science.lua:115-124 confirms:
    //
    //   function Science_Gravwell:GetSkillEffect(p1,p2)
    //       local ret = SkillEffect()
    //       local damage = SpaceDamage(p2, self.Damage, GetDirection(p1 - p2))
    //       damage.sAnimation = "airpush_"..GetDirection(p1 - p2)
    //       ret:AddArtillery(damage,"effects/shot_pull_U.png")
    //       return ret
    //   end
    //
    // The Lua applies a single SpaceDamage with a directional push (toward the
    // mech) at p2. SpaceDamage's third arg is a 1-tile push — there is NO
    // AddCharge / GetSimplePath multi-tile drag here. Compare Brute_Grapple
    // (weapons_brute.lua:339-389) which DOES use AddCharge to drag the target
    // all the way to mech-adjacent.
    //
    // Wiki phrasing "pulls its target towards you" is ambiguous — the v20 fix
    // assumed "all the way" but the Lua says single-tile. failure_db evidence
    // (multiple push_dir / damage_amount desyncs on Science_Gravwell) confirms
    // the Lua reading. Gravwell should NOT have FULL_PULL.

    #[test]
    fn test_science_gravwell_is_single_tile_pull() {
        // Repro of failure_db m13 t03: GravMech at (5,3) fires at Hornet at
        // (1,3). Per Lua, the Hornet should move ONE tile toward the mech
        // (1,3 → 2,3) and take NO damage. Previously (v20-v25), FULL_PULL
        // dragged the Hornet all the way to (4,3) adjacent to mech.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 5, 3, 3, WId::ScienceGravwell);
        let target = add_enemy(&mut board, 143, 1, 3, 2);

        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceGravwell, 1, 3);
        assert_eq!(board.units[target].x, 2,
            "Single-tile pull: Hornet at x=1 moves +x once to x=2 (toward mech at x=5)");
        assert_eq!(board.units[target].y, 3, "Stays in row");
        assert_eq!(board.units[target].hp, 2,
            "No damage: Lua SpaceDamage has self.Damage=0 and the 1-tile push lands on empty ground");
    }

    #[test]
    fn test_science_gravwell_single_pull_long_distance() {
        // Mech at (3,3), target at (3,7). Single-tile pull means target moves
        // 7→6, not 7→4. No bump (lands on empty ground).
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::ScienceGravwell);
        let enemy_idx = add_enemy(&mut board, 99, 3, 7, 4);
        let _ = simulate_weapon(&mut board, mech_idx, WId::ScienceGravwell, 3, 7);
        assert_eq!(board.units[enemy_idx].y, 6,
            "Single-tile pull: target at y=7 moves to y=6, not all the way to y=4");
        assert_eq!(board.units[enemy_idx].hp, 4, "No damage");
    }

    // ── Grappling Hook (Brute_Grapple) ─────────────────────────────────────────
    // Hook Mech weapon: melee-pull (range 1..) that drags the target ALL the
    // way to the tile adjacent to the mech, or until a blocker stops the pull.
    // Per wiki: "Use a grapple to pull Mech towards objects, or units to the
    // Mech." Same FULL_PULL semantic as Grav Well.

    #[test]
    fn test_brute_grapple_pulls_to_adjacent() {
        // Hook Mech at (3,3) (= "A1"-style; bridge coords) targets enemy at
        // (3,6) ("A4"). After full-pull the enemy should sit at (3,4) ("A2"),
        // adjacent to the mech.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteGrapple);
        let enemy_idx = add_enemy(&mut board, 99, 3, 6, 4);

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteGrapple, 3, 6);
        assert_eq!(board.units[enemy_idx].x, 3, "Stays in column");
        assert_eq!(board.units[enemy_idx].y, 4,
            "Grappling Hook pulls all the way (6→4, stops adjacent to mech)");
        assert_eq!(board.units[enemy_idx].hp, 4, "No damage from Grappling Hook itself");
    }

    #[test]
    fn test_brute_grapple_blocked_by_unit() {
        // Mech (3,3); Vek blocker at (3,4); target at (3,6). The pull tries
        // step 1: target (3,6)→(3,5) — clear. Step 2: target (3,5)→(3,4) —
        // blocked by Vek. Both bump. Final: target at (3,5) with -1 HP, Vek
        // at (3,4) with -1 HP.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteGrapple);
        let blocker = add_enemy(&mut board, 1, 3, 4, 3);
        let target = add_enemy(&mut board, 2, 3, 6, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteGrapple, 3, 6);
        assert_eq!(board.units[target].y, 5, "Target moved one tile then bumped");
        assert_eq!(board.units[target].hp, 2, "Target took bump damage");
        assert_eq!(board.units[blocker].x, 3, "Blocker did not move");
        assert_eq!(board.units[blocker].y, 4, "Blocker did not move");
        assert_eq!(board.units[blocker].hp, 2, "Blocker took bump damage");
    }

    #[test]
    fn test_brute_grapple_blocked_by_mountain() {
        // Mountain at (3,4) blocks the chain. Target at (3,6) walks to (3,5),
        // then bumps the mountain on the next step. Mountain takes 1 HP.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Mountain;
        board.tile_mut(3, 4).building_hp = 2;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteGrapple);
        let target = add_enemy(&mut board, 2, 3, 6, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteGrapple, 3, 6);
        assert_eq!(board.units[target].y, 5, "Target stops one short of the mountain");
        assert_eq!(board.units[target].hp, 2, "Target bumped, took 1 damage");
        assert_eq!(board.tile(3, 4).building_hp, 1, "Mountain damaged but not destroyed");
        assert_eq!(board.tile(3, 4).terrain, Terrain::Mountain, "Mountain still there");
    }

    #[test]
    fn test_brute_grapple_target_already_adjacent_noop() {
        // Target already adjacent to mech: no movement, no bump damage.
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteGrapple);
        let target = add_enemy(&mut board, 2, 3, 4, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteGrapple, 3, 4);
        assert_eq!(board.units[target].x, 3, "No move");
        assert_eq!(board.units[target].y, 4, "No move");
        assert_eq!(board.units[target].hp, 3, "No bump damage on no-op pull");
    }

    #[test]
    fn test_science_pullmech_still_one_tile() {
        // REGRESSION GUARD: Science_Pullmech (Attraction Pulse) is correctly
        // 1-tile per wiki and MUST NOT be promoted to FULL_PULL. Pulse Mech
        // at (3,3) pulling target at (3,6) should leave target at (3,5).
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::SciencePullmech);
        let target = add_enemy(&mut board, 2, 3, 6, 4);

        let _ = simulate_weapon(&mut board, mech_idx, WId::SciencePullmech, 3, 6);
        assert_eq!(board.units[target].x, 3, "Stays in column");
        assert_eq!(board.units[target].y, 5,
            "Attraction Pulse pulls exactly 1 tile (6→5), NOT all the way");
        assert_eq!(board.units[target].hp, 4, "No damage");
    }

    #[test]
    fn test_brute_grapple_pulls_into_water_kills_target() {
        // Non-flying Vek pulled across a water tile mid-chain dies; the pull
        // chain stops because the target's HP went to 0. Mech at (3,3), water
        // at (3,5), target at (3,7). Step 1: (3,7)→(3,6). Step 2: (3,6)→(3,5)
        // — water → kill, hp=0 → loop bails.
        let mut board = make_test_board();
        board.tile_mut(3, 5).terrain = Terrain::Water;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteGrapple);
        let target = add_enemy(&mut board, 2, 3, 7, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteGrapple, 3, 7);
        assert_eq!(board.units[target].hp, 0, "Target drowned in water during pull");
        assert_eq!(board.units[target].y, 5, "Corpse rests on the water tile");
    }

    // ── Brute_Grapple no-pawn self-charge (mountain/building target) ──────────
    // Per Lua weapons_brute.lua:339-389, when Brute_Grapple targets a tile that
    // has no pawn but IS PATH_PROJECTILE-blocked (mountain or intact building),
    // the MECH charges toward the obstacle and ends at the tile adjacent to it
    // (target - dir). The pull branch is the pawn case; this is the obstruction
    // branch (`elseif Board:IsBlocked(target, Pawn:GetPathProf())`).

    #[test]
    fn test_brute_grapple_self_charge_into_mountain() {
        // Mech at (3,3); empty path (3,4)/(3,5); mountain at (3,6). The Lua
        // projectile loop stops at (3,6) (PATH_PROJECTILE-blocked). With no
        // pawn there, mech charges to (3,6 - dir) = (3,5).
        let mut board = make_test_board();
        board.tile_mut(3, 6).terrain = Terrain::Mountain;
        board.tile_mut(3, 6).building_hp = 2;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteGrapple);

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteGrapple, 3, 6);
        assert_eq!(board.units[mech_idx].x, 3, "Mech stays in column");
        assert_eq!(board.units[mech_idx].y, 5,
            "Mech charges to tile adjacent to mountain (target - dir)");
        assert_eq!(board.units[mech_idx].hp, 3, "No self-damage from self-charge");
        assert_eq!(board.tile(3, 6).terrain, Terrain::Mountain,
            "Mountain unaffected by self-charge");
        assert_eq!(board.tile(3, 6).building_hp, 2, "Mountain HP unchanged");
    }

    #[test]
    fn test_brute_grapple_self_charge_into_building() {
        // Mech at (3,3); empty path; intact building at (3,7). Mech ends at
        // (3,6). Building HP unchanged (no damage from self-charge — Lua only
        // applies AddCharge + shieldSelf, no SpaceDamage to the obstacle).
        let mut board = make_test_board();
        board.tile_mut(3, 7).terrain = Terrain::Building;
        board.tile_mut(3, 7).building_hp = 1;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteGrapple);
        let initial_grid = board.grid_power;

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteGrapple, 3, 7);
        assert_eq!(board.units[mech_idx].x, 3);
        assert_eq!(board.units[mech_idx].y, 6,
            "Mech charges to tile adjacent to building");
        assert_eq!(board.tile(3, 7).building_hp, 1,
            "Building takes no damage from self-charge");
        assert_eq!(board.grid_power, initial_grid,
            "Grid power unchanged — building intact");
    }

    #[test]
    fn test_brute_grapple_self_charge_target_enumerated_at_mountain() {
        // Solver target enumeration: with a mountain at (3,6) and no other
        // unit/blocker between, Brute_Grapple from (3,3) MUST enumerate (3,6)
        // as a valid target (per Lua's GetTargetArea — first PATH_PROJECTILE
        // blocker in each cardinal direction).
        use crate::solver::get_weapon_targets;
        use crate::weapons::WEAPONS;
        let mut board = make_test_board();
        board.tile_mut(3, 6).terrain = Terrain::Mountain;
        board.tile_mut(3, 6).building_hp = 2;
        let _mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteGrapple);

        let targets = get_weapon_targets(&board, 3, 3, WId::BruteGrapple, (3, 3), &WEAPONS);
        assert!(targets.contains(&(3, 6)),
            "Brute_Grapple enumerates the mountain at (3,6) as a target; got {:?}", targets);
    }

    #[test]
    fn test_brute_grapple_self_charge_does_not_apply_to_pullmech() {
        // REGRESSION GUARD: Science_Pullmech (Attraction Pulse) has no
        // FULL_PULL flag and no self-charge branch in its Lua. Targeting an
        // empty mountain tile must be a no-op for Pullmech, NOT a self-charge.
        // (Mountain tiles are still enumerated by the shared Pull target code,
        // so this guard prevents accidental over-correction.)
        let mut board = make_test_board();
        board.tile_mut(3, 6).terrain = Terrain::Mountain;
        board.tile_mut(3, 6).building_hp = 2;
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::SciencePullmech);

        let _ = simulate_weapon(&mut board, mech_idx, WId::SciencePullmech, 3, 6);
        assert_eq!(board.units[mech_idx].x, 3, "Pullmech mech stays put");
        assert_eq!(board.units[mech_idx].y, 3,
            "Attraction Pulse on empty mountain target = no-op (no self-charge)");
    }

    #[test]
    fn test_brute_grapple_display_name() {
        // The display name was previously "Vice Fist" (the name of
        // Prime_Shift). Per data/wiki_raw/Weapons.json, Brute_Grapple's
        // canonical name is "Grappling Hook".
        assert_eq!(weapon_name(WId::BruteGrapple), "Grappling Hook");
    }

    // ── Vek Hormones (Passive_FriendlyFire) ──────────────────────────────────
    // GravMech passive: enemies do +1 damage to OTHER enemies (not to mechs).
    // The board carries a vek_hormones flag set via the Lua bridge passive
    // detection. enemy_hit_damage() bumps damage when source AND target are Vek.

    fn add_enemy_with_attack(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8,
                              weapon: WId, dmg: u8, target_x: i8, target_y: i8) -> usize {
        board.add_unit(Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Enemy,
            weapon: crate::board::WeaponId(weapon as u16),
            weapon_damage: dmg,
            queued_target_x: target_x,
            queued_target_y: target_y,
            flags: UnitFlags::ACTIVE | UnitFlags::PUSHABLE,
            ..Default::default()
        })
    }

    #[test]
    fn test_vek_hormones_boosts_vek_vs_vek_damage() {
        // Hornet (1 dmg) attacks an adjacent enemy. With vek_hormones the hit
        // deals 2 damage; without it, 1. Verify by running an enemy-phase sim.
        use crate::enemy::simulate_enemy_attacks;
        let mut board = make_test_board();
        board.vek_hormones = true;
        // Hornet at (3,3) targets enemy at (3,4) — north (DIRS index 0)
        add_enemy_with_attack(&mut board, 1, 3, 3, 2, WId::HornetAtk1, 1, 3, 4);
        let target = add_enemy(&mut board, 2, 3, 4, 3);
        let original = [(255u8, 255u8); 16];

        simulate_enemy_attacks(&mut board, &original, &WEAPONS);
        assert_eq!(board.units[target].hp, 1,
            "Target Vek took 2 damage (1 base + 1 hormone bonus)");
    }

    #[test]
    fn test_vek_hormones_does_not_boost_vek_vs_mech() {
        // Same setup but target is a mech — base damage only.
        use crate::enemy::simulate_enemy_attacks;
        let mut board = make_test_board();
        board.vek_hormones = true;
        add_enemy_with_attack(&mut board, 1, 3, 3, 2, WId::HornetAtk1, 1, 3, 4);
        let mech_idx = add_mech(&mut board, 99, 3, 4, 3, WId::PrimePunchmech);
        let original = [(255u8, 255u8); 16];

        simulate_enemy_attacks(&mut board, &original, &WEAPONS);
        assert_eq!(board.units[mech_idx].hp, 2,
            "Mech took base 1 damage (hormones don't boost vs mechs)");
    }

    #[test]
    fn test_vek_hormones_off_no_boost() {
        // Sanity: with flag OFF, vek-on-vek is just base damage.
        use crate::enemy::simulate_enemy_attacks;
        let mut board = make_test_board();
        board.vek_hormones = false;
        add_enemy_with_attack(&mut board, 1, 3, 3, 2, WId::HornetAtk1, 1, 3, 4);
        let target = add_enemy(&mut board, 2, 3, 4, 3);
        let original = [(255u8, 255u8); 16];

        simulate_enemy_attacks(&mut board, &original, &WEAPONS);
        assert_eq!(board.units[target].hp, 2, "Base 1 damage only");
    }

    // ── PushDir::Flip semantics (Spartan Shield / Confusion Ray) ──────────────

    #[test]
    fn test_spartan_shield_deals_damage_and_flips_attack() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 3, 3, 3, WId::PrimeShieldBash);
        let enemy = add_enemy(&mut board, 2, 3, 2, 3);
        board.units[enemy].queued_target_x = 3;
        board.units[enemy].queued_target_y = 1;

        let result = simulate_weapon(&mut board, mech, WId::PrimeShieldBash, 3, 2);

        assert_eq!(board.units[enemy].hp, 1, "Spartan Shield deals base 2 damage");
        assert_eq!(
            (board.units[enemy].queued_target_x, board.units[enemy].queued_target_y),
            (3, 3),
            "Spartan Shield flips the queued attack around the target"
        );
        assert_eq!((board.units[enemy].x, board.units[enemy].y), (3, 2),
            "Flip does not push the target");
        assert_eq!(result.enemy_damage_dealt, 2);
    }

    #[test]
    fn test_flip_queued_attack_flips_180_around_unit_position() {
        // Enemy at (3,3) aimed NORTH at (3,0). Flip → aimed SOUTH at (3,6).
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 3, 3, 3);
        board.units[idx].queued_target_x = 3;
        board.units[idx].queued_target_y = 0;

        flip_queued_attack(&mut board, 3, 3);

        assert_eq!(board.units[idx].queued_target_x, 3);
        assert_eq!(board.units[idx].queued_target_y, 6,
            "Flipped target is mirror image around (3,3)");
        assert_eq!(board.units[idx].x, 3,
            "Unit position unchanged — Flip does NOT push the unit");
        assert_eq!(board.units[idx].y, 3);
    }

    #[test]
    fn test_flip_queued_attack_uses_recorded_origin_after_displacement() {
        // The enemy started at (1,4) aimed at (1,3), then was pushed to
        // (2,4) before Seismic Capacitor flipped its queued attack. The flip
        // must reverse the original attack vector around the current tile,
        // producing (2,5), not a diagonal stale-save mirror at (3,5).
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 2, 4, 3);
        board.units[idx].queued_target_x = 1;
        board.units[idx].queued_target_y = 3;
        board.units[idx].queued_origin_x = 1;
        board.units[idx].queued_origin_y = 4;
        board.units[idx].flags.insert(UnitFlags::QUEUED_ORIGIN_SET);

        flip_queued_attack(&mut board, 2, 4);

        assert_eq!(board.units[idx].queued_target_x, 2);
        assert_eq!(board.units[idx].queued_target_y, 5);
        assert_eq!(board.units[idx].queued_origin_x, 2);
        assert_eq!(board.units[idx].queued_origin_y, 4);
    }

    #[test]
    fn test_flip_queued_attack_cancels_when_off_board() {
        // Enemy at (1,1) aimed at (1,0). Flip → (1,2). On-board, fine.
        // Enemy at (0,0) aimed at (0,3). Flip → (0,-3). Off-board → cancel.
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 0, 0, 3);
        board.units[idx].queued_target_x = 0;
        board.units[idx].queued_target_y = 3;

        flip_queued_attack(&mut board, 0, 0);

        assert_eq!(board.units[idx].queued_target_x, -1,
            "Off-board flipped target → attack cancelled (sentinel -1)");
    }

    #[test]
    fn test_flip_queued_attack_ignores_no_queued_target() {
        // Unit with queued_target_x = -1 (no attack queued) → no-op.
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 3, 3, 3);
        board.units[idx].queued_target_x = -1;
        board.units[idx].queued_target_y = -1;

        flip_queued_attack(&mut board, 3, 3);

        assert_eq!(board.units[idx].queued_target_x, -1,
            "No queued attack → stays cleared");
    }

    #[test]
    fn test_flip_queued_attack_ignores_self_target() {
        // Unit queued at its own position (suicide bomber / egg spawn).
        // No attack vector to flip → no-op.
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 3, 3, 3);
        board.units[idx].queued_target_x = 3;
        board.units[idx].queued_target_y = 3;

        flip_queued_attack(&mut board, 3, 3);

        assert_eq!(board.units[idx].queued_target_x, 3,
            "Self-targeted attacks not flipped");
        assert_eq!(board.units[idx].queued_target_y, 3);
    }

    // ── Psion aura cleanup on lethal env_danger kill ──────────────────────────

    #[test]
    fn test_soldier_psion_aura_clears_on_lethal_env_kill() {
        // Soldier Psion on a lethal env tile (Air Strike / Cataclysm / Tidal).
        // After env tick, psion dies → aura must clear → all surviving Vek
        // lose their +1 HP. Pre-fix, apply_env_danger bypassed the shared
        // kill-cleanup path and left soldier_psion=true forever.
        use crate::enemy::simulate_enemy_attacks;
        let mut board = make_test_board();
        board.soldier_psion = true;
        // Soldier Psion at (2,2), lethal env on its tile.
        let psion_idx = add_enemy(&mut board, 1, 2, 2, 2);
        board.units[psion_idx].set_type_name("Jelly_Health1");
        // Buffed grunt at (5,5) — started with +1 HP from the aura.
        let grunt_idx = add_enemy(&mut board, 2, 5, 5, 3);
        board.units[grunt_idx].max_hp = 3;
        // Mark (2,2) as a lethal env tile.
        let tile_idx = 2 * 8 + 2;
        board.env_danger |= 1u64 << tile_idx;
        board.env_danger_kill |= 1u64 << tile_idx;

        let original = [(255u8, 255u8); 16];
        simulate_enemy_attacks(&mut board, &original, &WEAPONS);

        assert!(!board.soldier_psion,
            "soldier_psion flag must clear after env-kill");
        assert_eq!(board.units[psion_idx].hp, 0, "Psion killed by env");
        assert_eq!(board.units[grunt_idx].hp, 2,
            "Grunt loses +1 aura HP after Psion dies (3 -> 2)");
        assert_eq!(board.units[grunt_idx].max_hp, 2,
            "Grunt max_hp also reduced");
    }

    #[test]
    fn test_boost_psion_death_clears_boosted_status_on_surviving_vek() {
        // Detritus Mission_Disposal turn 1, run 20260516_120646_726:
        // Taurus killed Jelly_Boost1 at F4. Live immediately removed the
        // Boosted status from Spider E4 and Leapers F3/D4; pre-fix Rust only
        // cleared board.boost_psion and verify flagged a status desync.
        let mut board = make_test_board();
        board.boost_psion = true;
        let psion_idx = add_enemy_type(&mut board, 1, 4, 2, 2, "Jelly_Boost1");
        let spider_idx = add_enemy_type(&mut board, 2, 4, 3, 2, "Spider1");
        let leaper_idx = add_enemy_type(&mut board, 3, 5, 2, 2, "Leaper2");
        board.units[spider_idx].set_boosted(true);
        board.units[leaper_idx].set_boosted(true);

        let mut result = ActionResult::default();
        apply_damage_core(&mut board, 4, 2, 2, &mut result, DamageSource::Weapon);

        assert_eq!(board.units[psion_idx].hp, 0);
        assert!(!board.boost_psion);
        assert!(!board.units[spider_idx].boosted());
        assert!(!board.units[leaper_idx].boosted());
    }

    // ── Storm Generator (Passive_Electric — Rusting Hulks / Detritus) ─────────

    #[test]
    fn test_storm_generator_damages_enemies_in_smoke() {
        // Enemy standing on a smoke tile takes 1 damage at start of enemy
        // phase when storm_generator is active. Confirms enemy.rs:198-209.
        use crate::enemy::simulate_enemy_attacks;
        let mut board = make_test_board();
        board.storm_generator = true;
        board.tile_mut(3, 3).set_smoke(true);
        let target = add_enemy(&mut board, 1, 3, 3, 3);
        let original = [(255u8, 255u8); 16];

        simulate_enemy_attacks(&mut board, &original, &WEAPONS);
        assert_eq!(board.units[target].hp, 2,
            "Enemy in smoke took 1 Storm Generator damage");
    }

    #[test]
    fn test_storm_generator_skips_enemies_not_in_smoke() {
        use crate::enemy::simulate_enemy_attacks;
        let mut board = make_test_board();
        board.storm_generator = true;
        // No smoke on tile (3,4); enemy on it should be untouched.
        let target = add_enemy(&mut board, 1, 3, 4, 3);
        let original = [(255u8, 255u8); 16];

        simulate_enemy_attacks(&mut board, &original, &WEAPONS);
        assert_eq!(board.units[target].hp, 3,
            "Enemy not on smoke tile unaffected");
    }

    #[test]
    fn test_storm_generator_leaves_mechs_untouched() {
        // Smoke + Storm Generator should not damage mechs — mechs in smoke
        // are safe (and smoke cancels enemy attacks targeting them).
        use crate::enemy::simulate_enemy_attacks;
        let mut board = make_test_board();
        board.storm_generator = true;
        board.tile_mut(4, 4).set_smoke(true);
        let mech_idx = add_mech(&mut board, 99, 4, 4, 3, WId::PrimePunchmech);
        let original = [(255u8, 255u8); 16];

        simulate_enemy_attacks(&mut board, &original, &WEAPONS);
        assert_eq!(board.units[mech_idx].hp, 3,
            "Mech in smoke is unharmed by Storm Generator");
    }

    #[test]
    fn test_storm_generator_off_no_smoke_damage() {
        // Sanity: enemy on smoke, flag off — no damage.
        use crate::enemy::simulate_enemy_attacks;
        let mut board = make_test_board();
        board.storm_generator = false;
        board.tile_mut(3, 3).set_smoke(true);
        let target = add_enemy(&mut board, 1, 3, 3, 3);
        let original = [(255u8, 255u8); 16];

        simulate_enemy_attacks(&mut board, &original, &WEAPONS);
        assert_eq!(board.units[target].hp, 3,
            "Flag off: enemy unharmed even on smoke");
    }

    // ── Repair Drop (Support_Repair) ───────────────────────────────────────────

    #[test]
    fn test_support_repair_heals_damaged_mechs_and_clears_statuses() {
        let mut board = make_test_board();
        // Caster at full HP
        let caster = add_mech(&mut board, 1, 3, 3, 3, WId::SupportRepair);
        // Damaged + burning ally
        let ally1 = add_mech(&mut board, 2, 4, 3, 3, WId::None);
        board.units[ally1].hp = 1;
        board.units[ally1].set_fire(true);
        // Acid+frozen ally at full HP (still clears statuses)
        let ally2 = add_mech(&mut board, 3, 5, 3, 3, WId::None);
        board.units[ally2].set_acid(true);
        board.units[ally2].set_frozen(true);
        // Enemy — must not be touched
        let enemy = add_enemy(&mut board, 99, 6, 3, 2);
        board.units[enemy].set_fire(true);

        let _ = simulate_weapon(&mut board, caster, WId::SupportRepair, 3, 3);

        assert_eq!(board.units[ally1].hp, 3, "Damaged mech fully healed");
        assert!(!board.units[ally1].fire(), "Fire cleared");
        assert!(!board.units[ally2].acid(), "Acid cleared");
        assert!(!board.units[ally2].frozen(), "Frozen cleared");
        assert_eq!(board.units[enemy].hp, 2, "Enemy HP untouched");
        assert!(board.units[enemy].fire(), "Enemy fire untouched");
    }

    #[test]
    fn test_support_repair_revives_disabled_mech() {
        // Disabled mech (hp<=0) sits as a wreck. Another mech firing Repair
        // Drop brings it back to full HP. Matches the Steam-forum consensus
        // that a disabled mech cannot cast it itself but CAN be revived by
        // an ally's Repair Drop.
        let mut board = make_test_board();
        let caster = add_mech(&mut board, 1, 3, 3, 3, WId::SupportRepair);
        let disabled = add_mech(&mut board, 2, 4, 3, 3, WId::None);
        board.units[disabled].hp = 0;

        let _ = simulate_weapon(&mut board, caster, WId::SupportRepair, 3, 3);

        assert_eq!(board.units[disabled].hp, 3, "Disabled mech revived to full HP");
    }

    #[test]
    fn test_support_wind_pushes_every_unit_left() {
        let mut board = make_test_board();
        let caster = add_mech(&mut board, 1, 3, 3, 3, WId::SupportWind);
        let enemy = add_enemy(&mut board, 99, 5, 3, 2);

        let _ = simulate_weapon(&mut board, caster, WId::SupportWind, 1, 3);

        assert_eq!((board.units[caster].x, board.units[caster].y), (2, 3));
        assert_eq!((board.units[enemy].x, board.units[enemy].y), (4, 3));
        assert_eq!(board.units[enemy].hp, 2, "zero-damage push only");
    }

    #[test]
    fn test_support_wind_right_scan_order_moves_leading_unit_first() {
        let mut board = make_test_board();
        let caster = add_mech(&mut board, 1, 0, 0, 3, WId::SupportWind);
        let trailing = add_enemy(&mut board, 10, 5, 3, 2);
        let leading = add_enemy(&mut board, 11, 6, 3, 2);

        let _ = simulate_weapon(&mut board, caster, WId::SupportWind, 5, 3);

        assert_eq!((board.units[leading].x, board.units[leading].y), (7, 3));
        assert_eq!((board.units[trailing].x, board.units[trailing].y), (6, 3));
        assert_eq!(board.units[leading].hp, 2);
        assert_eq!(board.units[trailing].hp, 2);
        assert_eq!((board.units[caster].x, board.units[caster].y), (1, 0));
    }

    #[test]
    fn test_support_wind_bump_into_building_costs_grid() {
        let mut board = make_test_board();
        let caster = add_mech(&mut board, 1, 6, 6, 3, WId::SupportWind);
        let enemy = add_enemy(&mut board, 99, 3, 3, 2);
        board.tile_mut(2, 3).terrain = Terrain::Building;
        board.tile_mut(2, 3).building_hp = 1;
        let grid_before = board.grid_power;

        let result = simulate_weapon(&mut board, caster, WId::SupportWind, 1, 3);

        assert_eq!((board.units[enemy].x, board.units[enemy].y), (3, 3));
        assert_eq!(board.units[enemy].hp, 1);
        assert_eq!(board.tile(2, 3).building_hp, 0);
        assert_eq!(board.grid_power, grid_before - 1);
        assert_eq!(result.grid_damage, 1);
    }

    // ── Force Amp (Passive_ForceAmp) ──────────────────────────────────────────

    #[test]
    fn test_force_amp_amplifies_bump_damage_to_vek() {
        // Push a 2-HP Scorpion into a mountain: normally 1 bump damage → 1 HP.
        // With Force Amp, 2 bump damage → 0 HP (killed).
        let mut board = make_test_board();
        board.force_amp = true;
        board.tile_mut(3, 4).terrain = Terrain::Mountain;
        board.tile_mut(3, 4).building_hp = 2;
        let enemy = add_enemy(&mut board, 1, 3, 3, 2);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result); // push N into mountain
        assert_eq!(board.units[enemy].hp, 0, "Force Amp: 1+1=2 bump damage kills 2-HP Vek");
        assert_eq!(result.enemies_killed, 1);
    }

    #[test]
    fn test_force_amp_disabled_no_boost() {
        // Sanity: without Force Amp, the same push deals the usual 1 damage.
        let mut board = make_test_board();
        board.force_amp = false;
        board.tile_mut(3, 4).terrain = Terrain::Mountain;
        board.tile_mut(3, 4).building_hp = 2;
        let enemy = add_enemy(&mut board, 1, 3, 3, 2);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        assert_eq!(board.units[enemy].hp, 1, "No Force Amp: 1 bump damage");
    }

    #[test]
    fn test_force_amp_does_not_amplify_mech_bump() {
        // A mech being pushed into a mountain takes the normal 1 bump damage —
        // Force Amp only boosts damage RECEIVED BY Vek.
        let mut board = make_test_board();
        board.force_amp = true;
        board.tile_mut(3, 4).terrain = Terrain::Mountain;
        board.tile_mut(3, 4).building_hp = 2;
        let mech = add_mech(&mut board, 99, 3, 3, 3, WId::None);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        assert_eq!(board.units[mech].hp, 2, "Mech takes normal 1 bump, not amped");
    }

    #[test]
    fn test_force_amp_amplifies_spawn_blocking() {
        // Vek blocks emerging Vek on a spawn tile. Spawn-block damage routes
        // through DamageSource::Bump; Force Amp adds +1.
        use crate::enemy::apply_spawn_blocking;
        let mut board = make_test_board();
        board.force_amp = true;
        let enemy = add_enemy(&mut board, 1, 3, 3, 2);
        let spawn = [(3u8, 3u8)];

        apply_spawn_blocking(&mut board, &spawn);
        assert_eq!(board.units[enemy].hp, 0, "Force Amp: block-damage 1+1=2 kills 2-HP Vek");
    }

    #[test]
    fn test_force_amp_bot_leader_exempt() {
        // Sentient enemies (Bot Leader / BotBoss) are explicitly excluded from
        // Force Amp's bonus per the wiki. Bumping BotBoss deals normal 1 dmg.
        let mut board = make_test_board();
        board.force_amp = true;
        board.tile_mut(3, 4).terrain = Terrain::Mountain;
        board.tile_mut(3, 4).building_hp = 2;
        // Bot Leader pawn
        let idx = board.add_unit(Unit {
            uid: 1, x: 3, y: 3, hp: 5, max_hp: 5,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });
        board.units[idx].set_type_name("BotBoss");

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        assert_eq!(board.units[idx].hp, 4, "Bot Leader exempt: takes normal 1 bump damage");
    }

    #[test]
    fn test_support_repair_does_not_clear_terrain_fire() {
        // A tile that's on fire stays on fire — the healed mech will re-ignite
        // next turn when the tile tick applies. The weapon only clears unit
        // status, never terrain.
        let mut board = make_test_board();
        let caster = add_mech(&mut board, 1, 3, 3, 3, WId::SupportRepair);
        board.tile_mut(4, 3).set_on_fire(true);
        let ally = add_mech(&mut board, 2, 4, 3, 3, WId::None);
        board.units[ally].hp = 1;
        board.units[ally].set_fire(true);

        let _ = simulate_weapon(&mut board, caster, WId::SupportRepair, 3, 3);

        assert!(!board.units[ally].fire(), "Mech fire status cleared");
        assert!(board.tile(4, 3).on_fire(), "Burning terrain tile preserved");
    }

    // ── Pilot passive tests ─────────────────────────────────────────────────
    //
    // These tests use `apply_weapon_status` and the push/move fire-catch
    // helpers directly so the passive behavior is exercised at the hook
    // points, not through a specific mech/enemy weapon that happens to
    // route fire/web at the time the test was written. Call-site coverage
    // still matters (regression.sh exercises full solves), but isolating
    // the hook here keeps the tests from breaking when unrelated weapon
    // defs or enemy types change.

    fn wdef_fire() -> crate::weapons::WeaponDef {
        use crate::weapons::{WeaponDef, WeaponFlags};
        WeaponDef {
            weapon_type: WeaponType::Melee,
            damage: 0, damage_outer: 0,
            push: PushDir::None,
            self_damage: 0,
            range_min: 1, range_max: 1,
            limited: 0, path_size: 1,
            boost_bonus: 0,
            flags: WeaponFlags::FIRE,
        }
    }

    fn wdef_web() -> crate::weapons::WeaponDef {
        use crate::weapons::{WeaponDef, WeaponFlags};
        WeaponDef {
            weapon_type: WeaponType::Projectile,
            damage: 0, damage_outer: 0,
            push: PushDir::None,
            self_damage: 0,
            range_min: 1, range_max: 4,
            limited: 0, path_size: 1,
            boost_bonus: 0,
            flags: WeaponFlags::WEB,
        }
    }

    #[test]
    fn test_pilot_soldier_immune_to_web() {
        use crate::board::PilotFlags;
        let mut board = make_test_board();
        let camila = add_mech(&mut board, 1, 3, 3, 2, WId::None);
        board.units[camila].pilot_flags = PilotFlags::SOLDIER;
        apply_weapon_status(&mut board, 3, 3, &wdef_web());
        assert!(!board.units[camila].web(),
            "Pilot_Soldier (Camila) must not be webbed");
    }

    #[test]
    fn test_non_soldier_gets_webbed() {
        // Control: a mech without Pilot_Soldier DOES get webbed at the
        // same hook, proving the guard isn't unconditionally suppressing
        // the effect.
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 3, 3, 2, WId::None);
        apply_weapon_status(&mut board, 3, 3, &wdef_web());
        assert!(board.units[mech].web(),
            "Default-pilot mech must still be webbed (control)");
    }

    #[test]
    fn test_pilot_rock_immune_to_weapon_fire() {
        use crate::board::PilotFlags;
        let mut board = make_test_board();
        let ariadne = add_mech(&mut board, 1, 3, 3, 2, WId::None);
        board.units[ariadne].pilot_flags = PilotFlags::ROCK;
        apply_weapon_status(&mut board, 3, 3, &wdef_fire());
        assert!(!board.units[ariadne].fire(),
            "Pilot_Rock (Ariadne) must not catch fire from a weapon hit");
    }

    #[test]
    fn test_pilot_rock_immune_to_tile_fire_on_push() {
        use crate::board::PilotFlags;
        // Push Ariadne onto a burning tile — she still must not catch fire.
        let mut board = make_test_board();
        let ariadne = add_mech(&mut board, 1, 3, 3, 2, WId::None);
        board.units[ariadne].pilot_flags = PilotFlags::ROCK;
        board.tile_mut(3, 4).set_on_fire(true);
        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result); // push east: (3,3)->(3,4)
        assert_eq!(board.units[ariadne].y, 4,
            "Mech should have moved onto the fire tile");
        assert!(!board.units[ariadne].fire(),
            "Ariadne must stay fire-free on a burning tile");
    }

    #[test]
    fn test_pilot_repairman_pushes_adjacent_enemies() {
        use crate::board::PilotFlags;
        let mut board = make_test_board();
        let harold = add_mech(&mut board, 1, 3, 3, 2, WId::None);
        board.units[harold].max_hp = 4;
        board.units[harold].hp = 2; // damaged so Repair actually heals
        board.units[harold].pilot_flags = PilotFlags::REPAIRMAN;

        // Drop a Vek on each of the 4 cardinal neighbours.
        let e_e = add_enemy(&mut board, 10, 3, 4, 2);
        let e_s = add_enemy(&mut board, 11, 4, 3, 2);
        let e_w = add_enemy(&mut board, 12, 3, 2, 2);
        let e_n = add_enemy(&mut board, 13, 2, 3, 2);

        // Repair goes through simulate_action (the real solver call path —
        // WId::Repair isn't a WeaponType::Melee/Projectile/etc. so
        // simulate_weapon's match dispatcher no-ops on it).
        let _ = simulate_action(&mut board, harold, (3, 3), WId::Repair,
                                (3, 3), &WEAPONS);

        // Each enemy should have moved one tile further from Harold than
        // its starting adjacent position. DIRS = [(0,1),(1,0),(0,-1),(-1,0)].
        assert_eq!((board.units[e_e].x, board.units[e_e].y), (3, 5),
            "+y neighbour pushed further in +y");
        assert_eq!((board.units[e_s].x, board.units[e_s].y), (5, 3),
            "+x neighbour pushed further in +x");
        assert_eq!((board.units[e_w].x, board.units[e_w].y), (3, 1),
            "-y neighbour pushed further in -y");
        assert_eq!((board.units[e_n].x, board.units[e_n].y), (1, 3),
            "-x neighbour pushed further in -x");
        // Repair still heals.
        assert_eq!(board.units[harold].hp, 3, "Repair heals 1 HP");
    }

    #[test]
    fn test_pilot_chemical_gets_boost_after_enemy_kill() {
        use crate::board::PilotFlags;
        let mut board = make_test_board();
        let morgan = add_mech(&mut board, 1, 3, 3, 3, WId::PrimePunchmech);
        board.units[morgan].pilot_flags = PilotFlags::CHEMICAL;
        add_enemy(&mut board, 10, 3, 4, 1);

        let _ = simulate_action(&mut board, morgan, (3, 3), WId::PrimePunchmech, (3, 4), &WEAPONS);

        assert!(board.units[morgan].boosted(), "Morgan should be boosted after killing an enemy");
    }

    #[test]
    fn test_pilot_chemical_loses_existing_boost_without_kill() {
        use crate::board::PilotFlags;
        let mut board = make_test_board();
        let morgan = add_mech(&mut board, 1, 3, 3, 3, WId::PrimePunchmech);
        board.units[morgan].pilot_flags = PilotFlags::CHEMICAL;
        board.units[morgan].set_boosted(true);

        let _ = simulate_action(&mut board, morgan, (3, 3), WId::PrimePunchmech, (3, 4), &WEAPONS);

        assert!(!board.units[morgan].boosted(), "Morgan's boost should be consumed when no enemy dies");
    }

    #[test]
    fn test_pilot_arrogant_regains_boost_after_repair_to_full_hp() {
        use crate::board::PilotFlags;
        let mut board = make_test_board();
        let kai = add_mech(&mut board, 0, 3, 3, 2, WId::BruteJetmech);
        board.units[kai].pilot_flags = PilotFlags::ARROGANT;
        board.units[kai].hp = 1;
        board.units[kai].set_boosted(false);

        let _ = simulate_action(&mut board, kai, (3, 3), WId::Repair, (255, 255), &WEAPONS);

        assert_eq!(board.units[kai].hp, 2);
        assert!(board.units[kai].boosted(), "Kai should be boosted again once Repair restores full HP");
    }

    #[test]
    fn test_pilot_arrogant_stays_boosted_after_full_hp_attack() {
        use crate::board::PilotFlags;
        let mut board = make_test_board();
        let kai = add_mech(&mut board, 0, 3, 3, 2, WId::BruteJetmech);
        board.units[kai].pilot_flags = PilotFlags::ARROGANT;
        board.units[kai].set_boosted(true);

        let _ = simulate_action(&mut board, kai, (3, 3), WId::BruteJetmech, (3, 5), &WEAPONS);

        assert_eq!(board.units[kai].hp, 2);
        assert!(board.units[kai].boosted(), "Kai's Boost is state-based while full HP, not consumed like generic Boost");
    }

    #[test]
    fn test_pilot_arrogant_loses_boost_when_damaged() {
        use crate::board::PilotFlags;
        let mut board = make_test_board();
        let kai = add_mech(&mut board, 0, 3, 3, 2, WId::BruteJetmech);
        board.units[kai].pilot_flags = PilotFlags::ARROGANT;
        board.units[kai].set_boosted(true);
        let mut result = ActionResult::default();

        apply_damage(&mut board, 3, 3, 1, &mut result, DamageSource::Weapon);

        assert_eq!(board.units[kai].hp, 1);
        assert!(!board.units[kai].boosted(), "Kai should lose Boost below full HP");
    }

    // sim v32: Grid Defense expected save fires for player-phase building
    // damage too (per text.lua:122 "This building resisted damage!"). The
    // simulator still destroys the building deterministically — what changes
    // is `player_grid_save_expected` accumulating `grid_damage * gd / 100`
    // for the evaluator. Pre-v32, plans clipping a building over-predicted
    // grid loss by ~0.15 per friendly hit, biasing the solver against
    // perfectly-acceptable plays. Mirrors the enemy.rs:1071 accumulator.
    #[test]
    fn test_player_grid_save_expected_accumulates_on_friendly_fire() {
        let mut board = make_test_board();
        // Titan Fist (Prime_Punchmech) at melee range into a 1-HP building.
        // Routed through simulate_action so the wrapper's accumulator
        // observes `result.grid_damage = 1`.
        let mech = add_mech(&mut board, 1, 3, 3, 3, WId::PrimePunchmech);
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;
        assert_eq!(board.grid_power, 7);
        assert_eq!(board.player_grid_save_expected, 0.0);
        assert_eq!(board.grid_defense_pct, 15);

        let result = simulate_action(&mut board, mech, (3, 3),
                                     WId::PrimePunchmech, (3, 4), &WEAPONS);

        // Building destroyed → grid_damage 1, grid_power -1, expected save
        // accumulator gets exactly 0.15 (1 * 15/100).
        assert!(result.grid_damage >= 1,
                "expected ≥1 grid point lost, got {}", result.grid_damage);
        assert!(board.grid_power < 7, "deterministic decrement still fires");
        let expected = (result.grid_damage as f32) * 0.15;
        assert!((board.player_grid_save_expected - expected).abs() < 1e-4,
                "expected {} (= grid_damage {} × 0.15), got {}",
                expected, result.grid_damage, board.player_grid_save_expected);
        // Enemy-phase save is untouched by player actions.
        assert_eq!(board.enemy_grid_save_expected, 0.0);
    }

    // Same path, no friendly fire → accumulator stays at 0. Guard against
    // accidentally accumulating on every action regardless of grid_damage.
    #[test]
    fn test_player_grid_save_zero_when_no_friendly_fire() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 3, 3, 3, WId::PrimePunchmech);
        let _enemy = add_enemy(&mut board, 10, 3, 4, 3);

        let _ = simulate_action(&mut board, mech, (3, 3),
                                WId::PrimePunchmech, (3, 4), &WEAPONS);

        assert_eq!(board.player_grid_save_expected, 0.0,
                   "no building hit → no expected save accrual");
    }

    #[test]
    fn test_non_repairman_repair_does_not_push() {
        // Control: a non-Harold mech repairing next to an enemy does NOT
        // push the enemy. Guards against my push loop accidentally firing
        // on every repair.
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 3, 3, 2, WId::None);
        board.units[mech].max_hp = 4;
        board.units[mech].hp = 2;
        let enemy = add_enemy(&mut board, 10, 3, 4, 2);
        let _ = simulate_action(&mut board, mech, (3, 3), WId::Repair,
                                (3, 3), &WEAPONS);
        assert_eq!((board.units[enemy].x, board.units[enemy].y), (3, 4),
            "non-Repairman repair must not displace adjacent enemies");
        assert_eq!(board.units[mech].hp, 3, "Repair still heals 1 HP");
    }

    // ── Aerial Bombs (Brute_Jetmech) landing-tile legality gate ───────────────
    // In-game, Aerial Bombs is unfireable at a target whose landing tile is a
    // water, lava, chasm, mountain (any HP), or occupied by a unit, wreck, or
    // building. Rubble remains legal for Jet Mech. The filter lives in
    // solver::get_weapon_targets plus sim_leap's diagnostic no-op guard.
    // Regression anchor: Easy Rusting Hulks run 20260508_134925_472,
    // Mission_Cataclysm turn 3 JetMech B5 -> B3 click_miss, where B3 was
    // already Cataclysm chasm terrain.

    fn leap_targets(board: &Board, mech_pos: (u8, u8)) -> Vec<(u8, u8)> {
        crate::solver::get_weapon_targets(
            board, mech_pos.0, mech_pos.1, WId::BruteJetmech, mech_pos, &WEAPONS,
        )
    }

    #[test]
    fn test_aerial_bombs_enum_allows_empty_landing() {
        // Jet Mech at (3,3). Landing tile (3,5) is plain ground — legal.
        // Aerial Bombs has range_min=range_max=2, so valid targets sit on the
        // same row or column at Manhattan distance 2.
        let mut board = make_test_board();
        let _mech = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        let targets = leap_targets(&board, (3, 3));
        assert!(targets.contains(&(3, 5)),
            "Empty ground 2 tiles away must be a legal landing — got {:?}", targets);
    }

    #[test]
    fn test_aerial_bombs_enum_rejects_landing_on_friendly_mech() {
        // Friendly mech already occupies the landing tile → illegal.
        let mut board = make_test_board();
        let _jet = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        let _ally = add_mech(&mut board, 1, 3, 5, 3, WId::None);
        let targets = leap_targets(&board, (3, 3));
        assert!(!targets.contains(&(3, 5)),
            "Friendly mech on landing tile must make target illegal — got {:?}", targets);
    }

    #[test]
    fn test_aerial_bombs_enum_rejects_landing_on_enemy() {
        // Enemy on the landing tile → illegal (no "crush" mechanic).
        let mut board = make_test_board();
        let _jet = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        let _enemy = add_enemy(&mut board, 99, 3, 5, 3);
        let targets = leap_targets(&board, (3, 3));
        assert!(!targets.contains(&(3, 5)),
            "Enemy on landing tile must make target illegal — got {:?}", targets);
    }

    #[test]
    fn test_aerial_bombs_enum_rejects_landing_on_chasm() {
        // Cataclysm/seismic chasm landing tiles are not selectable for Aerial
        // Bombs, even though Jet Mech itself is flying.
        let mut board = make_test_board();
        board.tile_mut(3, 5).terrain = Terrain::Chasm;
        let _jet = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        let targets = leap_targets(&board, (3, 3));
        assert!(!targets.contains(&(3, 5)),
            "Chasm landing tile must make target illegal — got {:?}", targets);
    }

    #[test]
    fn test_aerial_bombs_sim_noops_illegal_enemy_landing() {
        // Diagnostic callers can bypass target enumeration with a hand-written
        // plan. Illegal leap landings must not stack Jet onto a live enemy or
        // apply transit smoke/damage from a shot that cannot fire in-game.
        let mut board = make_test_board();
        let jet = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        let transit_enemy = add_enemy(&mut board, 10, 3, 4, 3);
        let landing_enemy = add_enemy(&mut board, 11, 3, 5, 3);

        let result = simulate_weapon(&mut board, jet, WId::BruteJetmech, 3, 5);

        assert_eq!(
            (board.units[jet].x, board.units[jet].y),
            (3, 3),
            "illegal leap must leave Jet on its original tile"
        );
        assert_eq!(
            (board.units[landing_enemy].x, board.units[landing_enemy].y),
            (3, 5),
            "landing enemy must remain alone on the blocked tile"
        );
        assert_eq!(
            board.units[transit_enemy].hp, 3,
            "unfireable Aerial Bombs must not damage the transit tile"
        );
        assert!(
            result.events.iter().any(|e| e == "illegal_leap_landing:3:5:unit"),
            "illegal landing should be visible to replay diagnostics: {:?}",
            result.events
        );
    }

    #[test]
    fn test_aerial_bombs_sim_noops_chasm_landing() {
        // Diagnostic callers can bypass target enumeration. A chasm landing
        // should behave like the live click_miss: no leap, no transit damage,
        // and an explicit replay event.
        let mut board = make_test_board();
        let jet = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        let transit_enemy = add_enemy(&mut board, 10, 3, 4, 3);
        board.tile_mut(3, 5).terrain = Terrain::Chasm;

        let result = simulate_weapon(&mut board, jet, WId::BruteJetmech, 3, 5);

        assert_eq!(
            (board.units[jet].x, board.units[jet].y),
            (3, 3),
            "chasm leap must leave Jet on its original tile"
        );
        assert_eq!(
            board.units[transit_enemy].hp, 3,
            "unfireable chasm landing must not damage the transit tile"
        );
        assert!(
            result.events.iter().any(|e| e == "illegal_leap_landing:3:5:chasm"),
            "chasm landing should be visible to replay diagnostics: {:?}",
            result.events
        );
    }

    #[test]
    fn test_aerial_bombs_sim_noops_water_landing() {
        // Live regression: JetMech D7 -> B7 over a Blob at C7 click-missed
        // because B7 was water. The attack must not damage the transit tile.
        let mut board = make_test_board();
        let jet = add_mech(&mut board, 0, 1, 4, 3, WId::BruteJetmech);
        let transit_enemy = add_enemy(&mut board, 10, 1, 5, 1);
        board.tile_mut(1, 6).terrain = Terrain::Water;

        let result = simulate_weapon(&mut board, jet, WId::BruteJetmech, 1, 6);

        assert_eq!(
            (board.units[jet].x, board.units[jet].y),
            (1, 4),
            "water leap must leave Jet on its original tile"
        );
        assert_eq!(
            board.units[transit_enemy].hp, 1,
            "unfireable water landing must not damage the transit tile"
        );
        assert!(
            result.events.iter().any(|e| e == "illegal_leap_landing:1:6:water"),
            "water landing should be visible to replay diagnostics: {:?}",
            result.events
        );
    }

    #[test]
    fn test_aerial_bombs_enum_rejects_landing_on_full_mountain() {
        // Full-HP mountain (terrain=Mountain, hp=2) on the landing tile → illegal.
        let mut board = make_test_board();
        board.tile_mut(3, 5).terrain = Terrain::Mountain;
        board.tile_mut(3, 5).building_hp = 2;
        let _jet = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        let targets = leap_targets(&board, (3, 3));
        assert!(!targets.contains(&(3, 5)),
            "Full mountain on landing tile must make target illegal — got {:?}", targets);
    }

    #[test]
    fn test_aerial_bombs_enum_rejects_landing_on_damaged_mountain() {
        // Damaged mountain (terrain=Mountain, hp=1) still blocks — only
        // rubble (terrain=Rubble) is walkable.
        let mut board = make_test_board();
        board.tile_mut(3, 5).terrain = Terrain::Mountain;
        board.tile_mut(3, 5).building_hp = 1;
        let _jet = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        let targets = leap_targets(&board, (3, 3));
        assert!(!targets.contains(&(3, 5)),
            "Damaged mountain (1 HP) still blocks landing — got {:?}", targets);
    }

    #[test]
    fn test_aerial_bombs_enum_allows_landing_on_rubble() {
        // Rubble (destroyed mountain) is walkable terrain → legal landing.
        let mut board = make_test_board();
        board.tile_mut(3, 5).terrain = Terrain::Rubble;
        let _jet = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        let targets = leap_targets(&board, (3, 3));
        assert!(targets.contains(&(3, 5)),
            "Rubble must be a legal landing tile — got {:?}", targets);
    }

    #[test]
    fn test_aerial_bombs_enum_rejects_landing_on_water() {
        // Jet Mech can normally move over water, but Brute_Jetmech's
        // GetTargetArea rejects water landing tiles; live FireWeapon spends
        // the action as a no-op when forced via bridge.
        let mut board = make_test_board();
        board.tile_mut(3, 5).terrain = Terrain::Water;
        let _jet = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        let targets = leap_targets(&board, (3, 3));
        assert!(!targets.contains(&(3, 5)),
            "Water must make Aerial Bombs landing illegal — got {:?}", targets);
    }

    #[test]
    fn test_aerial_bombs_enum_rejects_landing_on_building() {
        // Buildings occupy their tile (terrain=Building) and block movement —
        // including for flying units. Jet Mech cannot land on a building.
        let mut board = make_test_board();
        board.tile_mut(3, 5).terrain = Terrain::Building;
        board.tile_mut(3, 5).building_hp = 1;
        let _jet = add_mech(&mut board, 0, 3, 3, 3, WId::BruteJetmech);
        let targets = leap_targets(&board, (3, 3));
        assert!(!targets.contains(&(3, 5)),
            "Building on landing tile must make target illegal — got {:?}", targets);
    }

    #[test]
    fn test_aerial_bombs_enum_rejects_out_of_bounds_landing() {
        // Jet Mech in column 0. A 2-tile cardinal leap east lands at (0,2) —
        // legal. A 2-tile cardinal leap west would go off-board; the target
        // enumerator never offers off-board tiles because it iterates 0..8.
        // This test pins that invariant via a mech at (0,0): the only legal
        // Aerial Bombs targets are (0,2) and (2,0) — NOT (-2,0) / (0,-2) /
        // (1,-1) / etc., which are all off-board or non-cardinal.
        let mut board = make_test_board();
        let _jet = add_mech(&mut board, 0, 0, 0, 3, WId::BruteJetmech);
        let targets = leap_targets(&board, (0, 0));
        // Only two cardinal distance-2 targets exist from (0,0).
        assert!(targets.contains(&(0, 2)),
            "(0,2) — east by 2 — should be legal; got {:?}", targets);
        assert!(targets.contains(&(2, 0)),
            "(2,0) — south by 2 — should be legal; got {:?}", targets);
        // Every produced target must be in bounds and cardinal at distance 2.
        for &(x, y) in &targets {
            assert!(x < 8 && y < 8, "Off-board target {:?} leaked through", (x, y));
            let dist = (x as i16 - 0).abs() + (y as i16 - 0).abs();
            assert_eq!(dist, 2, "Non-distance-2 target {:?} leaked through", (x, y));
            assert!(x == 0 || y == 0, "Non-cardinal target {:?} leaked through", (x, y));
        }
    }
    // ── Massive trait: drown-immunity is Water/Lava ONLY ───────────────────
    //
    // Ground truth (Fandom Traits wiki + community consensus):
    //   Massive prevents DROWNING in water/lava. It does NOT save from:
    //     • Chasm tiles (pit-fall is a destroy, not a drown)
    //     • Cataclysm / Seismic opening a chasm under the unit
    //     • Tidal Wave (unconditional destroy)
    //     • Pushes, bumps, or displacement (that's Stable, a different trait)

    fn add_massive_enemy(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8) -> usize {
        board.add_unit(Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE | UnitFlags::MASSIVE,
            ..Default::default()
        })
    }

    fn add_massive_flying_enemy(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8) -> usize {
        board.add_unit(Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE | UnitFlags::MASSIVE | UnitFlags::FLYING,
            ..Default::default()
        })
    }

    #[test]
    fn test_massive_pushed_into_water_survives() {
        // Baseline: Massive saves from drowning.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Water;
        let idx = add_massive_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result); // push into water

        assert_eq!(board.units[idx].hp, 3,
            "Massive unit pushed into water must survive (drown immunity)");
        assert_eq!((board.units[idx].x, board.units[idx].y), (3, 4),
            "Massive unit must still move to the water tile");
        assert_eq!(result.enemies_killed, 0);
    }

    #[test]
    fn test_massive_pushed_into_lava_survives() {
        // Parallel to water: Massive is drown-immune in lava too.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Lava;
        let idx = add_massive_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result); // push into lava

        assert_eq!(board.units[idx].hp, 3,
            "Massive unit pushed into lava must survive (drown immunity)");
        assert_eq!(result.enemies_killed, 0);
    }

    #[test]
    fn test_massive_pushed_into_chasm_dies() {
        // THE FIX: chasm ≠ drowning, Massive must not save here.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Chasm;
        let idx = add_massive_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result); // push into chasm

        assert_eq!(board.units[idx].hp, 0,
            "Massive non-flying unit pushed into chasm must die");
        assert_eq!(result.enemies_killed, 1);
    }

    #[test]
    fn test_massive_flying_pushed_into_chasm_survives() {
        // Flying exempts from chasm; Massive is redundant here, but
        // confirms we didn't wire Massive to also block flying-survival.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Chasm;
        let idx = add_massive_flying_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);

        assert_eq!(board.units[idx].hp, 3,
            "Flying Massive unit pushed into chasm must survive (Flying exempts)");
        assert_eq!((board.units[idx].x, board.units[idx].y), (3, 4));
    }

    #[test]
    fn test_massive_thrown_into_chasm_dies() {
        // Throw path (apply_throw) must agree with push path: Massive
        // does NOT save from chasm fall.
        // Vice-Fist-style throw: attacker at (3,3), target at (4,3).
        // Attack direction = +x = DIRS index 1. Destination = attacker +
        // opposite_dir(1) = (3,3) + DIRS[3] = (2,3) = the chasm tile.
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Chasm;
        let _attacker = add_mech(&mut board, 99, 3, 3, 3, WId::None);
        let idx = add_massive_enemy(&mut board, 1, 4, 3, 3);

        let mut result = ActionResult::default();
        apply_throw(&mut board, 3, 3, 4, 3, 1, &mut result);

        assert_eq!(board.units[idx].hp, 0,
            "Massive non-flying unit thrown into chasm must die");
    }

    #[test]
    fn test_massive_thrown_into_water_survives() {
        // Throw-path parity with push-path for drown immunity.
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Water;
        let _attacker = add_mech(&mut board, 99, 3, 3, 3, WId::None);
        let idx = add_massive_enemy(&mut board, 1, 4, 3, 3);

        let mut result = ActionResult::default();
        apply_throw(&mut board, 3, 3, 4, 3, 1, &mut result);

        assert_eq!(board.units[idx].hp, 3,
            "Massive unit thrown into water must survive");
        assert_eq!((board.units[idx].x, board.units[idx].y), (2, 3),
            "Massive unit must still land on the water tile");
    }

    #[test]
    fn test_massive_cataclysm_lethal_env_dies() {
        // Cataclysm opens a chasm under the unit; the env-danger tick
        // fires in enemy phase as a lethal (kill_int=1) event. Massive
        // must NOT save the unit from that.
        use crate::enemy::simulate_enemy_attacks;
        use crate::types::xy_to_idx;
        let mut board = make_test_board();
        let idx = add_massive_enemy(&mut board, 1, 3, 3, 3);
        let bit = 1u64 << xy_to_idx(3, 3);
        board.env_danger |= bit;
        board.env_danger_kill |= bit;

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let _ = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!(board.units[idx].hp, 0,
            "Massive unit on Cataclysm lethal env-danger tile must die");
    }

    #[test]
    fn test_massive_seismic_lethal_env_dies() {
        // Seismic Activity turns a tile into chasm under a unit; the
        // env-danger tile is tagged lethal (kill_int=1). Massive must die.
        use crate::enemy::simulate_enemy_attacks;
        use crate::types::xy_to_idx;
        let mut board = make_test_board();
        let idx = add_massive_enemy(&mut board, 42, 4, 2, 4);
        let bit = 1u64 << xy_to_idx(4, 2);
        board.env_danger |= bit;
        board.env_danger_kill |= bit;

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let _ = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!(board.units[idx].hp, 0,
            "Massive unit caught by Seismic lethal env-danger must die");
    }

    #[test]
    fn test_massive_tidal_wave_lethal_destroys() {
        // Tidal Wave is usually flagged lethal by the bridge (kill_int=1).
        // It's a destroy, not a drown — Massive does NOT save.
        use crate::enemy::simulate_enemy_attacks;
        use crate::types::xy_to_idx;
        let mut board = make_test_board();
        let idx = add_massive_enemy(&mut board, 7, 1, 1, 5);
        let bit = 1u64 << xy_to_idx(1, 1);
        board.env_danger |= bit;
        board.env_danger_kill |= bit;

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let _ = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!(board.units[idx].hp, 0,
            "Massive unit hit by lethal Tidal Wave must be destroyed");
    }

    // ── Flying immunity on terrain-conversion lethal env (sim v19+) ──────────
    //
    // Tidal Wave / Cataclysm / Seismic Activity convert tiles to water/chasm.
    // Effectively-flying units hover and survive. Air Strike / Lightning /
    // Satellite Rocket stay lethal even to flyers (bombs/lightning ignore
    // flight altitude). Pre-v19, apply_env_danger killed any unit on a
    // kill_int=1 tile regardless of flying — the bridge had no way to express
    // the distinction. v19 adds `env_danger_flying_immune` as a sibling bitset
    // (5th field on each environment_danger_v2 entry).

    #[test]
    fn test_tidal_wave_lethal_spares_flying() {
        // Flying enemy on a Tidal Wave tile: tile bit is lethal AND
        // flying_immune. Hornet hovers over the new water — must survive.
        use crate::enemy::simulate_enemy_attacks;
        use crate::types::xy_to_idx;
        let mut board = make_test_board();
        let idx = add_flying_enemy(&mut board, 1, 3, 3, 4);
        let bit = 1u64 << xy_to_idx(3, 3);
        board.env_danger |= bit;
        board.env_danger_kill |= bit;
        board.env_danger_flying_immune |= bit;

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let _ = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!(board.units[idx].hp, 4,
            "Flying enemy on Tidal Wave tile must survive (water hovers)");
    }

    #[test]
    fn test_tidal_wave_lethal_kills_grounded() {
        // Regression guard: non-flying units still die on Tidal Wave.
        use crate::enemy::simulate_enemy_attacks;
        use crate::types::xy_to_idx;
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 3, 3, 4);
        let bit = 1u64 << xy_to_idx(3, 3);
        board.env_danger |= bit;
        board.env_danger_kill |= bit;
        board.env_danger_flying_immune |= bit;

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let _ = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!(board.units[idx].hp, 0,
            "Non-flying enemy on Tidal Wave tile must drown");
    }

    #[test]
    fn test_cataclysm_lethal_spares_flying() {
        // Flying enemy on a Cataclysm tile (chasm-conversion): flyer hovers
        // over the new chasm and lives. Mirrors the Tidal Wave path — same
        // flying_immune flag.
        use crate::enemy::simulate_enemy_attacks;
        use crate::types::xy_to_idx;
        let mut board = make_test_board();
        let idx = add_flying_enemy(&mut board, 9, 5, 2, 3);
        let bit = 1u64 << xy_to_idx(5, 2);
        board.env_danger |= bit;
        board.env_danger_kill |= bit;
        board.env_danger_flying_immune |= bit;

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let _ = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!(board.units[idx].hp, 3,
            "Flying enemy on Cataclysm tile must survive (hovers over chasm)");
    }

    #[test]
    fn test_air_strike_lethal_kills_flying() {
        // Regression guard: Air Strike / Lightning have flying_immune=0 even
        // when kill_int=1. A flying unit on such a tile MUST die — bombs and
        // lightning hit anything in the air. This was the pre-fix behavior
        // for ALL lethal env; making sure we didn't over-spare.
        use crate::enemy::simulate_enemy_attacks;
        use crate::types::xy_to_idx;
        let mut board = make_test_board();
        let idx = add_flying_enemy(&mut board, 11, 2, 6, 3);
        let bit = 1u64 << xy_to_idx(2, 6);
        board.env_danger |= bit;
        board.env_danger_kill |= bit;
        // Crucially: env_danger_flying_immune NOT set on this tile.

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let _ = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!(board.units[idx].hp, 0,
            "Flying enemy on Air Strike tile must die (bombs ignore flight)");
    }

    #[test]
    fn test_tidal_wave_flying_immune_still_destroys_building() {
        // Even when a flyer survives, the env tick still wipes out any
        // building on the tile (water/chasm conversion deletes buildings).
        // This guards against an over-eager early-return that would skip the
        // building branch when the unit was spared.
        use crate::enemy::simulate_enemy_attacks;
        use crate::types::xy_to_idx;
        let mut board = make_test_board();
        let _flyer = add_flying_enemy(&mut board, 13, 4, 4, 3);
        // Place a building UNDER the flyer at (4,4)
        let tile = board.tile_mut(4, 4);
        tile.terrain = Terrain::Building;
        tile.building_hp = 1;
        let prev_grid = board.grid_power;
        let bit = 1u64 << xy_to_idx(4, 4);
        board.env_danger |= bit;
        board.env_danger_kill |= bit;
        board.env_danger_flying_immune |= bit;

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let _ = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!(board.tile(4, 4).terrain, Terrain::Rubble,
            "Building destroyed by Tidal Wave even when flyer is spared");
        assert!(board.grid_power < prev_grid,
            "Grid power drops from destroyed building");
    }

    #[test]
    fn test_massive_flying_tidal_wave_lethal_spares() {
        // Flying Massive on Tidal Wave: flying overrides Massive — flyer
        // hovers. (The non-flying Massive case still dies — see
        // test_massive_tidal_wave_lethal_destroys.)
        use crate::enemy::simulate_enemy_attacks;
        use crate::types::xy_to_idx;
        let mut board = make_test_board();
        let idx = add_massive_flying_enemy(&mut board, 17, 6, 3, 5);
        let bit = 1u64 << xy_to_idx(6, 3);
        board.env_danger |= bit;
        board.env_danger_kill |= bit;
        board.env_danger_flying_immune |= bit;

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let _ = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!(board.units[idx].hp, 5,
            "Massive flying unit on Tidal Wave tile must survive (flying immunity)");
    }

    #[test]
    fn test_env_danger_v2_deserializes_flying_immune_field() {
        // Wire-format check: the bridge emits a 5th element on each
        // environment_danger_v2 entry. Confirm board_from_json populates the
        // env_danger_flying_immune bitset accordingly.
        use crate::serde_bridge::board_from_json;
        let json = r#"{
          "tiles": [],
          "units": [],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "environment_danger_v2": [
            [3, 3, 1, 1, 1],
            [4, 4, 1, 1, 0],
            [5, 5, 1, 0, 0]
          ],
          "env_type": "tidal_or_cataclysm",
          "remaining_spawns": 0,
          "turn": 1,
          "total_turns": 5
        }"#;
        let (board, _, _, _, _, _) = board_from_json(json).expect("parse");
        assert!(board.is_env_danger(3, 3));
        assert!(board.is_env_danger_kill(3, 3));
        assert!(board.is_env_danger_flying_immune(3, 3),
            "5-elem entry with flying_immune=1 sets the bit");
        assert!(board.is_env_danger_kill(4, 4));
        assert!(!board.is_env_danger_flying_immune(4, 4),
            "5-elem entry with flying_immune=0 clears the bit");
        assert!(board.is_env_danger(5, 5));
        assert!(!board.is_env_danger_kill(5, 5),
            "kill_int=0 leaves env_danger_kill clear");
        assert!(!board.is_env_danger_flying_immune(5, 5),
            "non-lethal tile is never flying-immune");
    }

    #[test]
    fn test_mission_wind_markers_do_not_damage_buildings() {
        // Hard Rusting Hulks run 20260512_104120_903, Mission_Wind turn 1:
        // the bridge marked wind rows as non-lethal environment_danger_v2,
        // including buildings at F7/C7. Wind pushes; it is not direct 1 HP
        // building damage. Until WindDir is exported, keep these as
        // non-damaging markers so clean boards do not safety-block on phantom
        // grid loss.
        use crate::enemy::simulate_enemy_attacks;
        use crate::serde_bridge::board_from_json;
        use crate::types::xy_to_idx;

        let json = r#"{
          "mission_id": "Mission_Wind",
          "tiles": [
            {"x": 1, "y": 2, "terrain": "building", "terrain_id": 1, "building_hp": 1}
          ],
          "units": [],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "environment_danger_v2": [[1, 2, 1, 0, 0]],
          "env_type": "wind",
          "remaining_spawns": 0,
          "turn": 1,
          "total_turns": 5
        }"#;
        let (mut board, _, _, _, _, _) = board_from_json(json).expect("parse");
        let wind_bit = 1u64 << xy_to_idx(1, 2);
        assert_eq!(board.env_wind & wind_bit, wind_bit);
        assert!(!board.is_env_danger(1, 2),
            "Mission_Wind markers must not enter direct env damage");

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let _ = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);
        assert_eq!(board.grid_power, 7);
        assert_eq!(board.tile(1, 2).building_hp, 1);
    }

    #[test]
    fn test_mission_wind_dir_push_bumps_mech_into_building() {
        // Internal solver direction 0 pushes toward increasing bridge y.
        use crate::enemy::simulate_enemy_attacks;
        use crate::types::xy_to_idx;
        let mut board = make_test_board();
        let rocket = add_mech(&mut board, 1, 5, 5, 3, WId::RangedRocket);
        board.tile_mut(5, 6).terrain = Terrain::Building;
        board.tile_mut(5, 6).building_hp = 1;
        board.unique_buildings |= 1u64 << xy_to_idx(5, 6);
        board.env_wind = 1u64 << xy_to_idx(5, 5);
        board.env_wind_dir = 0;
        let grid_before = board.grid_power;

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let result = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        assert_eq!((board.units[rocket].x, board.units[rocket].y), (5, 5));
        assert_eq!(board.units[rocket].hp, 2, "blocked wind push bumps mech");
        assert_eq!(board.tile(5, 6).building_hp, 0, "wind bump destroys building");
        assert_eq!(board.grid_power, grid_before - 1);
        assert_eq!(result.grid_damage, 1);
    }

    #[test]
    fn test_mission_wind_raw_dir_two_pushes_egg_sack_out_of_burnbug_lane() {
        // Cataclysm Unfair live run 20260521_120049_468, Mission_Wind t1:
        // raw WindDir=2 pushed the marked E3 Vek egg sack into the D3 chasm,
        // clearing the F2 Alpha Burnbug projectile lane to kill Trimissile.
        // Pre-v177 treated raw dir 2 as solver dir 2, moved the egg to F3,
        // and incorrectly let the egg block the shot.
        use crate::enemy::simulate_enemy_attacks;
        use crate::serde_bridge::board_from_json;

        let json = r#"{
          "mission_id": "Mission_Wind",
          "tiles": [
            {"x": 5, "y": 4, "terrain": "chasm", "terrain_id": 9}
          ],
          "units": [
            {"uid": 1, "type": "TrimissileMech", "x": 4, "y": 2,
             "hp": 2, "max_hp": 2, "team": 1, "mech": true,
             "massive": true, "pushable": true, "weapons": ["Ranged_Crack_B"]},
            {"uid": 2, "type": "HydrantMech", "x": 4, "y": 3,
             "hp": 3, "max_hp": 3, "team": 1, "mech": true,
             "massive": true, "pushable": true, "weapons": ["Science_KO_Crack_A"]},
            {"uid": 1530, "type": "BonusDebris", "x": 5, "y": 3,
             "hp": 1, "max_hp": 1, "team": 6, "minor": true,
             "pushable": true, "weapons": []},
            {"uid": 1535, "type": "Burnbug2", "x": 6, "y": 2,
             "hp": 4, "max_hp": 4, "team": 6, "pushable": true,
             "ranged": 1, "weapons": ["BurnbugAtk2"],
             "has_queued_attack": true, "queued_target": [5, 2],
             "weapon_damage": 3}
          ],
          "grid_power": 6,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "environment_danger_v2": [[5, 3, 1, 0, 0]],
          "environment_wind_dir": 2,
          "env_type": "wind",
          "remaining_spawns": 0,
          "turn": 1,
          "total_turns": 4
        }"#;

        let (mut board, _, _, _, _, _) = board_from_json(json).expect("parse");
        let mut original_positions = [(0u8, 0u8); 16];
        for i in 0..board.unit_count as usize {
            original_positions[i] = (board.units[i].x, board.units[i].y);
        }
        let result = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);

        let trimissile = (0..board.unit_count as usize)
            .find(|&i| board.units[i].uid == 1)
            .unwrap();
        let hydrant = (0..board.unit_count as usize)
            .find(|&i| board.units[i].uid == 2)
            .unwrap();
        let egg = (0..board.unit_count as usize)
            .find(|&i| board.units[i].uid == 1530)
            .unwrap();

        assert!(board.units[egg].hp <= 0, "wind should push the egg sack into the chasm");
        assert!(board.units[trimissile].hp <= 0,
            "Alpha Burnbug should hit Trimissile after the egg leaves the lane");
        assert_eq!(board.units[hydrant].hp, 3,
            "raw WindDir=2 must not bump the adjacent Hydrant");
        assert_eq!(result.mechs_killed, 1);
    }

    #[test]
    fn test_final_cave_env_ignores_stale_flying_immune_field() {
        // Final Cave Env_Final marked tiles are falling-rock/tentacle death
        // effects. A stale bridge once misclassified them as
        // cataclysm_or_seismic with flying_immune=1, letting Prospero's
        // Combat Mech stand on C6 and die live after a "clean" solve.
        use crate::enemy::simulate_enemy_attacks;
        use crate::serde_bridge::board_from_json;
        let json = r#"{
          "mission_id": "Mission_Final_Cave",
          "tiles": [],
          "units": [
            {"uid":0,"type":"PunchMech","x":2,"y":5,
             "hp":3,"max_hp":3,"team":1,"mech":true,
             "active":true,"massive":true,"flying":true,
             "weapons":["Prime_Punchmech"]}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "environment_danger_v2": [[2, 5, 1, 1, 1]],
          "env_type": "cataclysm_or_seismic",
          "remaining_spawns": 0,
          "turn": 1,
          "total_turns": 4
        }"#;
        let (mut board, _, _, _, _, _) = board_from_json(json).expect("parse");
        assert!(board.is_env_danger_kill(2, 5));
        assert!(!board.is_env_danger_flying_immune(2, 5),
            "Mission_Final_Cave danger must not inherit flying immunity");

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let _ = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);
        assert_eq!(board.units[0].hp, 0,
            "Final Cave falling-rock danger kills flying mechs");
    }

    #[test]
    fn test_airstrike_env_ignores_stale_flying_immune_field() {
        // Archive Airstrike can expose StartEffect like terrain-conversion
        // envs. Mission ID wins: bombs kill flyers even if the bridge's 5th
        // env_danger_v2 field is stale flying_immune=1.
        use crate::enemy::simulate_enemy_attacks;
        use crate::serde_bridge::board_from_json;
        let json = r#"{
          "mission_id": "Mission_Airstrike",
          "tiles": [],
          "units": [
            {"uid":2,"type":"TeleMech","x":4,"y":3,
             "hp":2,"max_hp":2,"team":1,"mech":true,
             "active":true,"massive":true,"flying":true,
             "weapons":["Science_Swap"]}
          ],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "environment_danger_v2": [[4, 3, 1, 1, 1]],
          "env_type": "cataclysm_or_seismic",
          "remaining_spawns": 0,
          "turn": 4,
          "total_turns": 4
        }"#;
        let (mut board, _, _, _, _, _) = board_from_json(json).expect("parse");
        assert!(board.is_env_danger_kill(4, 3));
        assert!(!board.is_env_danger_flying_immune(4, 3),
            "Mission_Airstrike danger must not inherit flying immunity");

        let original_positions: [(u8, u8); 16] = [(0, 0); 16];
        let _ = simulate_enemy_attacks(&mut board, &original_positions, &WEAPONS);
        assert_eq!(board.units[0].hp, 0,
            "Airstrike danger kills flying mechs");
    }

    #[test]
    fn test_env_danger_v2_legacy_4field_falls_back_to_env_type() {
        // Older recordings emit only 4 fields. Fallback path: when 5th is
        // missing, derive flying_immune from `env_type`.
        use crate::serde_bridge::board_from_json;
        let json = r#"{
          "tiles": [],
          "units": [],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "environment_danger_v2": [[2, 2, 1, 1]],
          "env_type": "cataclysm_or_seismic",
          "remaining_spawns": 0,
          "turn": 1,
          "total_turns": 5
        }"#;
        let (board, _, _, _, _, _) = board_from_json(json).expect("parse");
        assert!(board.is_env_danger_kill(2, 2));
        assert!(board.is_env_danger_flying_immune(2, 2),
            "Missing 5th field falls back to env_type=cataclysm_or_seismic → flying-immune");
    }

    #[test]
    fn test_env_danger_v2_legacy_4field_lightning_not_immune() {
        // env_type=lightning_or_airstrike → flying NOT immune (Air Strike,
        // Lightning hit flyers).
        use crate::serde_bridge::board_from_json;
        let json = r#"{
          "tiles": [],
          "units": [],
          "grid_power": 7,
          "grid_power_max": 7,
          "spawning_tiles": [],
          "environment_danger": [],
          "environment_danger_v2": [[1, 1, 1, 1]],
          "env_type": "lightning_or_airstrike",
          "remaining_spawns": 0,
          "turn": 1,
          "total_turns": 5
        }"#;
        let (board, _, _, _, _, _) = board_from_json(json).expect("parse");
        assert!(board.is_env_danger_kill(1, 1));
        assert!(!board.is_env_danger_flying_immune(1, 1),
            "Air Strike / Lightning legacy entries must not set flying-immune");
    }

    // ── Frozen flying = grounded ─────────────────────────────────────────────
    //
    // Freezing a flying Vek (Hornet, Mosquito, Jet Mech) grounds it — frozen
    // overrides flight. Pushing it into water or chasm kills it: the ice
    // shell shears off and the ungrounded body drowns / falls. Key kill
    // pattern the solver was missing before this fix.
    //
    // The sim uses effectively_flying() = flying && !frozen in apply_push,
    // apply_throw, and apply_damage_core (ice-break drown). These tests lock
    // in each path.

    fn add_flying_enemy(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8) -> usize {
        board.add_unit(Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE | UnitFlags::FLYING,
            ..Default::default()
        })
    }

    #[test]
    fn test_unfrozen_flying_pushed_into_water_survives() {
        // Baseline: flying unit is exempt from drowning.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Water;
        let idx = add_flying_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);

        assert_eq!(board.units[idx].hp, 3,
            "Unfrozen flying unit pushed into water must survive");
    }

    #[test]
    fn test_frozen_flying_pushed_into_water_drowns() {
        // THE FIX: frozen cancels flight; pushed into water, drowns.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Water;
        let idx = add_flying_enemy(&mut board, 1, 3, 3, 3);
        board.units[idx].set_frozen(true);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);

        assert_eq!(board.units[idx].hp, 0,
            "Frozen flying unit pushed into water must drown");
        assert_eq!(result.enemies_killed, 1);
    }

    #[test]
    fn test_frozen_flying_pushed_into_chasm_dies() {
        // Chasm kill: no Massive guard even if it had Massive.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Chasm;
        let idx = add_flying_enemy(&mut board, 1, 3, 3, 3);
        board.units[idx].set_frozen(true);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);

        assert_eq!(board.units[idx].hp, 0,
            "Frozen flying unit pushed into chasm must fall");
        assert_eq!(result.enemies_killed, 1);
    }

    #[test]
    fn test_frozen_flying_thrown_into_water_drowns() {
        // Throw path parity: Vice Fist thrown frozen-flying into water drowns.
        let mut board = make_test_board();
        board.tile_mut(2, 3).terrain = Terrain::Water;
        let _attacker = add_mech(&mut board, 99, 3, 3, 3, WId::None);
        let idx = add_flying_enemy(&mut board, 1, 4, 3, 3);
        board.units[idx].set_frozen(true);

        let mut result = ActionResult::default();
        apply_throw(&mut board, 3, 3, 4, 3, 1, &mut result);

        assert_eq!(board.units[idx].hp, 0,
            "Frozen flying unit thrown into water must drown");
    }

    #[test]
    fn test_flying_ice_break_survives() {
        // apply_damage_core path: weapon damage melts cracked ice to water.
        // A unit on the tile drowns if not effectively_flying() && not massive.
        // The frozen case doesn't fire here in practice — any damage that
        // breaks the ice ALSO unfreezes the unit (frozen-takes-0-damage
        // unfreeze runs FIRST in apply_damage_core, before the tile effect),
        // so by the time the ice→water conversion happens the unit is already
        // un-frozen and re-flying. Test the baseline (damage-through-ice
        // survives for a flying unit) to lock in the effectively_flying-based
        // check in apply_damage_core.
        let mut board = make_test_board();
        board.tile_mut(3, 3).terrain = Terrain::Ice;
        board.tile_mut(3, 3).set_cracked(true);
        let idx = add_flying_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_damage_core(&mut board, 3, 3, 1, &mut result, DamageSource::Weapon);

        assert_eq!(board.units[idx].hp, 2,
            "Flying unit on melting ice must survive (took 1 weapon dmg)");
    }

    #[test]
    fn test_weapon_kill_on_occupied_cracked_ground_does_not_open_chasm() {
        let mut board = make_test_board();
        board.tile_mut(3, 3).terrain = Terrain::Ground;
        board.tile_mut(3, 3).set_cracked(true);
        let enemy = add_enemy(&mut board, 42, 3, 3, 1);

        let mut result = ActionResult::default();
        apply_damage_core(&mut board, 3, 3, 1, &mut result, DamageSource::Weapon);

        assert_eq!(board.units[enemy].hp, 0, "occupant should take the hit");
        assert_eq!(board.tile(3, 3).terrain, Terrain::Ground);
        assert!(board.tile(3, 3).cracked(), "crack remains for a later tile hit");
    }

    #[test]
    fn test_weapon_damage_on_empty_cracked_ground_opens_chasm() {
        let mut board = make_test_board();
        board.tile_mut(3, 3).terrain = Terrain::Ground;
        board.tile_mut(3, 3).set_cracked(true);

        let mut result = ActionResult::default();
        apply_damage_core(&mut board, 3, 3, 1, &mut result, DamageSource::Weapon);

        assert_eq!(board.tile(3, 3).terrain, Terrain::Chasm);
        assert!(!board.tile(3, 3).cracked());
    }

    #[test]
    fn test_self_damage_on_occupied_cracked_ground_opens_chasm() {
        let mut board = make_test_board();
        board.tile_mut(3, 3).terrain = Terrain::Ground;
        board.tile_mut(3, 3).set_cracked(true);
        let mech = add_mech(&mut board, 7, 3, 3, 5, WId::PrimeLeap);

        let mut result = ActionResult::default();
        apply_damage_core(&mut board, 3, 3, 1, &mut result, DamageSource::SelfDamage);

        assert_eq!(board.tile(3, 3).terrain, Terrain::Chasm);
        assert!(!board.tile(3, 3).cracked());
        assert_eq!(board.units[mech].hp, 0, "grounded mech falls into chasm");
    }

    // ── building_hp underflow regression tests ───────────────────────────
    //
    // Previously `apply_push` / `apply_throw` had:
    //
    //     if board.tile(nx, ny).building_hp > 0 {
    //         apply_damage(...);          // can mutate tile hp via volatile
    //                                     // decay / blast psion chains that
    //                                     // damage adjacent tiles
    //         let bt = board.tile_mut(nx, ny);
    //         bt.building_hp -= 1;        // stale guard: could underflow u8
    //     }
    //
    // If the intervening `apply_damage` drove the building at (nx, ny) to 0
    // (e.g., Volatile Vek death explosion chained into the building), the
    // `-= 1` would panic on debug builds and wrap to 255 on release. Both
    // sites now use saturating_sub.

    #[test]
    fn test_push_into_destroyed_objective_no_underflow() {
        // Simplest stub of the destroyed-but-still-blocking case:
        // terrain = Building, building_hp = 0 (e.g. Emergency Batteries
        // after destruction). Push a unit into it; the unit takes bump,
        // the tile stays at 0 hp, no panic.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 0;
        let idx = add_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result); // push N into destroyed bldg

        // Unit did not move — still at origin with -1 bump
        assert_eq!(board.units[idx].x, 3);
        assert_eq!(board.units[idx].y, 3);
        assert_eq!(board.units[idx].hp, 2, "pushed unit took 1 bump");
        // Building hp stays at 0, no underflow
        assert_eq!(board.tile(3, 4).building_hp, 0);
        // Destroyed stub shouldn't re-count as a new loss
        assert_eq!(result.buildings_lost, 0);
        assert_eq!(result.grid_damage, 0);
    }

    #[test]
    fn test_push_volatile_into_building_no_underflow() {
        // Exercises the real underflow path: the outer `building_hp > 0`
        // guard is satisfied (hp=1), but apply_damage on the pushed unit
        // kills a Volatile Vek whose decay explosion damages the building
        // at (nx, ny), dropping hp to 0 BEFORE the post-apply_damage
        // `bt.building_hp -= 1`. Without saturating_sub this panics in
        // debug builds.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;

        // 1-HP Volatile Vek at (3,3) — the bump will kill it, triggering
        // Explosive Decay (1 bump dmg to all 4 adjacent tiles, including
        // the building at (3,4)).
        let idx = board.add_unit(Unit {
            uid: 1, x: 3, y: 3, hp: 1, max_hp: 1,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });
        board.units[idx].set_type_name("Volatile_Vek");

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result); // push N into building

        // Volatile vek died from bump damage
        assert_eq!(board.units[idx].hp, 0);
        assert_eq!(result.enemies_killed, 1);
        // Building driven to 0 and converted to rubble (non-unique), no underflow
        assert_eq!(board.tile(3, 4).building_hp, 0);
        assert_eq!(board.tile(3, 4).terrain, Terrain::Rubble);
    }

    #[test]
    fn test_throw_into_destroyed_objective_no_underflow() {
        // Parallel case for apply_throw's building branch (line ~533).
        // apply_throw has the same stale-guard pattern; verify the hp=0
        // stub path stays safe (underflow-prone path is only reachable via
        // chain damage from apply_damage on the thrown unit).
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 0;
        // Target (the thrown unit) at (3, 2); attacker at (3, 3) attacking
        // dir=2 (y-). apply_throw's destination = attacker + opposite(dir)
        // = (3,3) + (0,1) = (3,4), the destroyed building.
        let idx = add_enemy(&mut board, 1, 3, 2, 3);

        let mut result = ActionResult::default();
        apply_throw(&mut board, 3, 3, 3, 2, 2, &mut result);

        // Target stayed at (3,2), took 1 bump, building still at 0
        assert_eq!(board.units[idx].x, 3);
        assert_eq!(board.units[idx].y, 2);
        assert_eq!(board.units[idx].hp, 2);
        assert_eq!(board.tile(3, 4).building_hp, 0);
    }

    // ── Brute_Mirrorshot (Janus Cannon) ─────────────────────────────────────
    // Mirror Shot fires two projectiles in opposite directions. Prior bug:
    // the backward arm stopped at a mountain without damaging it, and the
    // forward arm had the same gap. Reproduces the failure_db signature from
    // snapshots/grid_drop_20260421_135801_843_t02_a1 — attacker at (1,6),
    // target (2,6), mountain at (0,6) left sim at hp=2 while the game
    // rubble-tracked it at hp=1.

    #[test]
    fn test_mirrorshot_backward_arm_damages_mountain() {
        // Attacker at (1,6) shoots south toward (2,6). A ground enemy at
        // (2,6) absorbs the forward projectile. Backward arm travels north
        // from (1,6) and hits the mountain at (0,6), which must take 1
        // damage (2 HP → 1 HP), matching the game's behavior.
        let mut board = make_test_board();
        board.tile_mut(0, 6).terrain = Terrain::Mountain;
        board.tile_mut(0, 6).building_hp = 2;

        let mech_idx = add_mech(&mut board, 0, 1, 6, 3, WId::BruteMirrorshot);
        // Target for forward arm so the mirror's backward fire is the only
        // thing touching (0,6) — isolates the mountain-damage fix.
        let target_idx = add_enemy(&mut board, 1, 2, 6, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteMirrorshot, 2, 6);

        // Backward arm damaged the mountain: hp 2 → 1, still Mountain
        // terrain (rubble conversion only happens at hp=0).
        assert_eq!(
            board.tile(0, 6).building_hp, 1,
            "Mirror Shot backward arm should damage mountain at (0,6) by 1"
        );
        assert_eq!(board.tile(0, 6).terrain, Terrain::Mountain);
        // Forward arm still hit the enemy as expected.
        assert_eq!(board.units[target_idx].hp, 2);
    }

    #[test]
    fn test_mirrorshot_forward_arm_damages_mountain_when_no_target() {
        // If the forward path hits nothing but a mountain (no unit or
        // building in the line of fire), the projectile still damages the
        // mountain. Previously this was a silent miss — the forward loop
        // broke on mountain without damage, so weapons like Tank Cannon
        // shooting into an empty corridor that terminated in a mountain
        // also mispredicted.
        let mut board = make_test_board();
        board.tile_mut(1, 5).terrain = Terrain::Mountain;
        board.tile_mut(1, 5).building_hp = 2;

        let mech_idx = add_mech(&mut board, 0, 1, 0, 3, WId::BruteMirrorshot);
        // No units between shooter and mountain, and no mountain in the
        // backward direction — isolates forward-arm mountain damage.
        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteMirrorshot, 1, 5);

        assert_eq!(
            board.tile(1, 5).building_hp, 1,
            "Mirror Shot forward arm should damage mountain at end of line"
        );
        assert_eq!(board.tile(1, 5).terrain, Terrain::Mountain);
    }

    #[test]
    fn test_mirrorshot_backward_arm_rubbleizes_damaged_mountain() {
        // A mountain already at hp=1 (damaged) should be converted to
        // Rubble when the backward arm hits it. Reproduces the second-shot
        // scenario: Mirror Shot first run drops mountain 2→1, the next
        // turn's Mirror Shot should finish it off.
        let mut board = make_test_board();
        board.tile_mut(0, 6).terrain = Terrain::Mountain;
        board.tile_mut(0, 6).building_hp = 1;

        let mech_idx = add_mech(&mut board, 0, 1, 6, 3, WId::BruteMirrorshot);
        // Forward target to absorb the forward projectile.
        add_enemy(&mut board, 1, 2, 6, 3);

        let _ = simulate_weapon(&mut board, mech_idx, WId::BruteMirrorshot, 2, 6);

        // Mountain goes from hp=1 → hp=0 → Rubble terrain.
        assert_eq!(board.tile(0, 6).building_hp, 0);
        assert_eq!(
            board.tile(0, 6).terrain, Terrain::Rubble,
            "Mountain at hp=1 hit by Mirror Shot backward arm should become Rubble"
        );
    }

    #[test]
    fn test_mirrorshot_killed_forward_target_bumps_live_mech_blocker() {
        // Live regression: Frozen Titans Untouchable run
        // 20260521_223240_242, Mission_Airstrike turn 1. Mirror Mech at G6
        // fired Janus Cannon at the 1-HP egg/debris on F6 while Ice Mech
        // stood directly behind it on E6. The killed target still resolved
        // the forward push/bump into Ice Mech, invalidating Untouchable.
        let mut board = make_test_board();
        let mirror = add_mech(&mut board, 1, 2, 1, 3, WId::BruteMirrorshot);
        let debris = add_enemy_type(&mut board, 2272, 2, 2, 1, "BonusDebris");
        let ice = add_mech(&mut board, 2, 2, 3, 2, WId::RangedIce);

        let result = simulate_weapon(&mut board, mirror, WId::BruteMirrorshot, 2, 2);

        assert_eq!(board.units[debris].hp, 0);
        assert_eq!(
            board.units[ice].hp, 1,
            "Mirror Shot killed-target forward push should corpse-bump the live mech blocker"
        );
        assert_eq!(result.mech_damage_taken, 1);
    }

    // ── Teleporter pad swap (Mission_Teleporter) ──────────────────────────

    #[test]
    fn test_teleport_partner_lookup_both_directions() {
        let mut board = make_test_board();
        board.teleporter_pairs.push((1, 1, 5, 5));
        assert_eq!(board.teleport_partner(1, 1), Some((5, 5)));
        assert_eq!(board.teleport_partner(5, 5), Some((1, 1)));
        assert_eq!(board.teleport_partner(3, 3), None);
    }

    #[test]
    fn test_push_lands_on_pad_swaps_to_empty_partner() {
        // ScienceMech regression: mech moves/pushed to E3, pad partner C3 is
        // empty → mech teleports to C3. This was the exact failure seen on
        // run 20260423_131700_144 T1 (ScienceMech predicted E3, actual C3).
        let mut board = make_test_board();
        board.teleporter_pairs.push((5, 3, 5, 5)); // E3 <-> C3
        let idx = add_enemy(&mut board, 1, 4, 3, 3); // at (4,3), push +x → (5,3) pad

        let mut result = ActionResult::default();
        apply_push(&mut board, 4, 3, 1, &mut result); // push +x direction
        assert_eq!(
            (board.units[idx].x, board.units[idx].y),
            (5, 5),
            "Unit pushed onto empty pad should teleport to partner"
        );
    }

    #[test]
    fn test_push_lands_on_pad_swaps_with_occupant() {
        // Paired pads with occupants: the two units swap. Mech at pad-A
        // lands on pad-A's location; Vek on pad-B swaps to pad-A.
        let mut board = make_test_board();
        board.teleporter_pairs.push((3, 3, 6, 6));
        let mech = add_mech(&mut board, 0, 2, 3, 3, WId::PrimePunchmech);
        let vek  = add_enemy(&mut board, 1, 6, 6, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 2, 3, 1, &mut result); // push mech +x → (3,3) pad
        assert_eq!((board.units[mech].x, board.units[mech].y), (6, 6));
        assert_eq!((board.units[vek].x, board.units[vek].y), (3, 3));
    }

    #[test]
    fn test_corpse_does_not_teleport() {
        // Unit pushed onto pad over water dies first; the corpse doesn't
        // teleport. Pads in vanilla aren't on water, but the rule also
        // covers old-earth-mine kills on-pad.
        let mut board = make_test_board();
        board.teleporter_pairs.push((3, 3, 6, 6));
        board.tile_mut(3, 3).terrain = Terrain::Water;
        let idx = add_enemy(&mut board, 1, 2, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 2, 3, 1, &mut result); // push +x onto water-pad

        assert_eq!(board.units[idx].hp, 0, "Unit should drown before pad fires");
        // Drowned unit's position should stay on the killing tile (water),
        // not teleport to partner. The sim doesn't "undo" the move — the
        // corpse sinks where it fell. Check: the partner tile must be empty.
        assert!(board.unit_at(6, 6).is_none(), "Corpse must not teleport to partner");
    }

    #[test]
    fn test_mine_kill_on_pad_does_not_teleport() {
        let mut board = make_test_board();
        board.teleporter_pairs.push((3, 3, 6, 6));
        board.tile_mut(3, 3).set_old_earth_mine(true);
        let idx = add_enemy(&mut board, 1, 2, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 2, 3, 1, &mut result); // push onto mined pad
        assert_eq!(board.units[idx].hp, 0, "Mine kills before pad fires");
        assert!(board.unit_at(6, 6).is_none(), "Mined corpse does not teleport");
    }

    #[test]
    fn test_mech_move_onto_pad_teleports() {
        // simulate_action(move to pad) should land mech on partner.
        let mut board = make_test_board();
        board.teleporter_pairs.push((4, 4, 1, 1));
        let mech = add_mech(&mut board, 0, 3, 3, 3, WId::Repair);

        let _ = simulate_action(&mut board, mech, (4, 4), WId::Repair, (3, 3), &WEAPONS);
        assert_eq!(
            (board.units[mech].x, board.units[mech].y),
            (1, 1),
            "Mech move-end on pad swaps to partner"
        );
    }

    #[test]
    fn test_mech_starting_on_pad_does_not_trigger() {
        // Game rule: "does not fire for units that START on a pad".
        // simulate_action with move_to == old_pos is a no-move (mech
        // fires without moving); pad should NOT trigger.
        let mut board = make_test_board();
        board.teleporter_pairs.push((3, 3, 7, 7));
        let mech = add_mech(&mut board, 0, 3, 3, 3, WId::Repair);

        let _ = simulate_action(&mut board, mech, (3, 3), WId::Repair, (3, 3), &WEAPONS);
        assert_eq!(
            (board.units[mech].x, board.units[mech].y),
            (3, 3),
            "Mech that didn't move (move_to == old_pos) stays put on its pad"
        );
    }

    #[test]
    fn test_web_survives_pad_swap() {
        // Pad swap is NOT a push; webbed units stay webbed after teleporting.
        // Pad swap itself must not touch the web flag.
        let mut board = make_test_board();
        board.teleporter_pairs.push((3, 3, 6, 6));
        let idx = add_enemy(&mut board, 1, 3, 3, 3);
        board.units[idx].set_web(true);

        apply_teleport_on_land(&mut board, idx);
        assert_eq!((board.units[idx].x, board.units[idx].y), (6, 6));
        assert!(board.units[idx].web(), "Pad swap must not break web");
    }

    #[test]
    fn test_push_breaks_webbed_unit() {
        let mut board = make_test_board();
        let idx = add_mech(&mut board, 1, 3, 3, 3, WId::None);
        board.units[idx].set_web(true);
        board.units[idx].web_source_uid = 99;
        board.units[idx].move_speed = 0;
        board.units[idx].base_move = 3;

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 1, &mut result);

        assert_eq!((board.units[idx].x, board.units[idx].y), (4, 3));
        assert!(!board.units[idx].web(), "Push must break the pushed unit's web");
        assert_eq!(board.units[idx].web_source_uid, 0);
        assert_eq!(board.units[idx].move_speed, board.units[idx].base_move);
    }

    #[test]
    fn test_repair_extinguishes_current_tile_fire() {
        let mut board = make_test_board();
        let mech = add_mech(&mut board, 1, 3, 3, 3, WId::Repair);
        board.units[mech].hp = 1;
        board.units[mech].set_fire(true);
        board.tile_mut(3, 3).set_on_fire(true);

        let _ = simulate_action(&mut board, mech, (3, 3), WId::Repair, (3, 3), &WEAPONS);

        assert_eq!(board.units[mech].hp, 2);
        assert!(!board.units[mech].fire(), "Repair clears unit fire");
        assert!(!board.tile(3, 3).on_fire(), "Repair extinguishes the occupied tile");
    }

    #[test]
    fn test_empty_teleporter_pairs_is_noop() {
        // Sanity: non-teleporter missions have empty teleporter_pairs; the
        // linear scan must cost nothing observable.
        let mut board = make_test_board();
        let idx = add_enemy(&mut board, 1, 2, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 2, 3, 1, &mut result);
        assert_eq!((board.units[idx].x, board.units[idx].y), (3, 3));
    }

    // ── Volatile Vek Explosive Decay ─────────────────────────────────────
    //
    // Ported from tests/test_volatile_vek.py (Python sim removal, PR-C).
    // Behavior under test: when a Volatile Vek dies (any cause — weapon
    // damage, push to deadly terrain, etc.) it deals 1 bump-class damage
    // to all 4 adjacent tiles. Bump-class bypasses armor + ACID. Chains
    // through adjacent volatiles (depth-capped at 8).

    fn add_volatile(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8) -> usize {
        let idx = board.add_unit(Unit {
            uid, x, y, hp, max_hp: hp,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            ..Default::default()
        });
        board.units[idx].set_type_name("Volatile_Vek");
        idx
    }

    fn add_boom_bot(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8) -> usize {
        add_enemy_type(board, uid, x, y, hp, "Snowart1_Boom")
    }

    fn add_armored_mech(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8) -> usize {
        let idx = add_mech(board, uid, x, y, hp, WId::None);
        board.units[idx].flags.insert(UnitFlags::ARMOR);
        idx
    }

    fn add_acid_enemy(board: &mut Board, uid: u16, x: u8, y: u8, hp: i8) -> usize {
        let idx = add_enemy(board, uid, x, y, hp);
        board.units[idx].set_acid(true);
        idx
    }

    #[test]
    fn test_volatile_vek_death_damages_four_adjacent_mechs() {
        // Mechs N/S/E/W of the Volatile Vek. Kill the Vek → each loses 1 HP.
        let mut board = make_test_board();
        let v = add_volatile(&mut board, 1, 3, 3, 1);
        let n = add_mech(&mut board, 2, 3, 4, 3, WId::None);
        let s = add_mech(&mut board, 3, 3, 2, 3, WId::None);
        let e = add_mech(&mut board, 4, 4, 3, 3, WId::None);
        let w = add_mech(&mut board, 5, 2, 3, 3, WId::None);

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 1, &mut result, DamageSource::Weapon);

        assert_eq!(board.units[v].hp, 0, "volatile killed");
        assert_eq!(board.units[n].hp, 2);
        assert_eq!(board.units[s].hp, 2);
        assert_eq!(board.units[e].hp, 2);
        assert_eq!(board.units[w].hp, 2);
        assert_eq!(result.mech_damage_taken, 4);
    }

    #[test]
    fn test_boom_bot_death_uses_volatile_decay() {
        // Mission_BoomBots' Snow*1_Boom pawns have Explosive Decay. Killing
        // one by bump/Attract must splash adjacent buildings and mechs.
        let mut board = make_test_board();
        let v = add_boom_bot(&mut board, 1, 3, 3, 1);
        let mech = add_mech(&mut board, 2, 4, 3, 3, WId::None);
        board.tile_mut(3, 4).terrain = Terrain::Building;
        board.tile_mut(3, 4).building_hp = 1;
        board.grid_power = 4;

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 1, &mut result, DamageSource::Bump);

        assert_eq!(board.units[v].hp, 0, "boom bot killed");
        assert_eq!(board.units[mech].hp, 2, "adjacent mech takes decay splash");
        assert_eq!(board.tile(3, 4).building_hp, 0, "adjacent building takes decay splash");
        assert_eq!(board.grid_power, 3, "explosion building damage drains grid");
    }

    #[test]
    fn test_boom_bot_attract_death_matches_central_processor_capture() {
        let mut board = make_test_board();
        let boom = add_boom_bot(&mut board, 1, 4, 3, 1);
        let science = add_mech(&mut board, 2, 4, 4, 2, WId::SciencePullmech);
        let laser = add_mech(&mut board, 3, 5, 3, 3, WId::PrimeLasermech);
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 1;
        board.tile_mut(5, 3).terrain = Terrain::Forest;
        board.grid_power = 4;

        let mut result = ActionResult::default();
        apply_push(&mut board, 4, 3, 0, &mut result);

        assert_eq!(board.units[boom].hp, 0, "blocked pull kills the 1-HP Boom Bot");
        assert_eq!(board.units[science].hp, 0, "Science takes bump plus decay splash");
        assert_eq!(board.units[laser].hp, 2, "Laser takes adjacent decay splash");
        assert!(board.units[laser].fire(), "Laser catches fire from the ignited forest");
        assert_eq!(board.tile(3, 3).terrain, Terrain::Rubble);
        assert_eq!(board.tile(3, 3).building_hp, 0);
        assert_eq!(board.tile(5, 3).terrain, Terrain::Ground);
        assert!(board.tile(5, 3).on_fire(), "forest becomes a burning ground tile");
        assert_eq!(board.grid_power, 3);
    }

    #[test]
    fn test_volatile_vek_survives_when_not_killed() {
        // Vek HP > damage → no death → no explosion.
        let mut board = make_test_board();
        let v = add_volatile(&mut board, 1, 3, 3, 2);
        let neighbor = add_mech(&mut board, 2, 4, 3, 3, WId::None);

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 1, &mut result, DamageSource::Weapon);

        assert_eq!(board.units[v].hp, 1, "survived");
        assert_eq!(board.units[neighbor].hp, 3, "no splash");
        assert_eq!(result.mech_damage_taken, 0);
    }

    #[test]
    fn test_volatile_decay_ignores_armor_and_acid() {
        // Bump-class damage bypasses both, matching Explosive Decay rules.
        let mut board = make_test_board();
        let _v = add_volatile(&mut board, 1, 3, 3, 1);
        let armored = add_armored_mech(&mut board, 2, 4, 3, 3);
        let acid_enemy = add_acid_enemy(&mut board, 3, 2, 3, 3);

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 1, &mut result, DamageSource::Weapon);

        // Armor would normally reduce 1→0; bump damage ignores armor.
        assert_eq!(board.units[armored].hp, 2, "armor bypassed");
        // ACID doubles weapon damage; bump ignores ACID, so 1 not 2.
        assert_eq!(board.units[acid_enemy].hp, 2, "acid double bypassed");
    }

    #[test]
    fn test_volatile_decay_does_not_chain_on_non_volatile() {
        // Adjacent non-volatile dies from the 1 damage; no second explosion.
        let mut board = make_test_board();
        let _v = add_volatile(&mut board, 1, 3, 3, 1);
        let fragile = add_enemy(&mut board, 2, 4, 3, 1);
        let bystander = add_mech(&mut board, 3, 5, 3, 3, WId::None);

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 1, &mut result, DamageSource::Weapon);

        assert_eq!(board.units[fragile].hp, 0, "fragile killed by decay");
        assert_eq!(board.units[bystander].hp, 3,
                   "no second explosion from non-volatile death");
    }

    #[test]
    fn test_volatile_decay_chains_through_adjacent_volatile() {
        // A at (3,3) dies → hits B at (4,3) for 1 → B at 0 → B's decay
        // fires → hits mech at (5,3) for 1.
        let mut board = make_test_board();
        let a = add_volatile(&mut board, 1, 3, 3, 1);
        let b = add_volatile(&mut board, 2, 4, 3, 1);
        let mech = add_mech(&mut board, 3, 5, 3, 3, WId::None);

        let mut result = ActionResult::default();
        apply_damage(&mut board, 3, 3, 1, &mut result, DamageSource::Weapon);

        assert_eq!(board.units[a].hp, 0);
        assert_eq!(board.units[b].hp, 0);
        // Mech is adjacent to B, NOT to A — only B's chain explosion hits it.
        assert_eq!(board.units[mech].hp, 2);
    }

    #[test]
    fn test_volatile_vek_pushed_into_water_explodes() {
        // Non-flying volatile pushed into water: drowns AND explodes,
        // damaging the mech adjacent to the destination tile.
        let mut board = make_test_board();
        board.tile_mut(4, 3).terrain = Terrain::Water;
        let v = add_volatile(&mut board, 1, 3, 3, 3);
        let mech = add_mech(&mut board, 2, 5, 3, 3, WId::None);

        let mut result = ActionResult::default();
        // Push east: (3,3) -> (4,3) which is water. DIRS index 1 = east.
        apply_push(&mut board, 3, 3, 1, &mut result);

        assert_eq!(board.units[v].hp, 0, "drowned");
        // Mech at (5,3) is adjacent to (4,3); decay reaches it.
        assert_eq!(board.units[mech].hp, 2,
                   "mech took 1 from explosion at the drown tile");
    }

    // NOTE: test_volatile_decay_attribution_in_events from the Python
    // suite is intentionally NOT ported. Rust ActionResult.events is
    // never populated by any sim path (grep `events.push` across
    // rust_solver/src/* returns nothing). The Python convention of
    // pushing human-readable event strings was Python-specific; Rust
    // tracks state mutations directly via Board fields. If event
    // attribution is later useful for diagnose markdown body text,
    // wire it as a separate feature with its own tests.

    // ── Push mechanics — gap-filling cases from tests/test_push_mechanics.py ──
    //
    // The existing Rust corpus already covers push_into_water,
    // push_into_building, ignores_armor, etc. These add the rules that
    // weren't yet tested at the unit level: non-pushable immunity,
    // edge/mountain bumps, two-unit collision damage, chasm/lava
    // deadly-ground, flying immunity to deadly ground, and the
    // no-chain rule. Ported during PR-C of the Python-sim removal.

    #[test]
    fn test_non_pushable_non_mech_is_immune() {
        // Massive Vek without PUSHABLE flag doesn't move on push.
        let mut board = make_test_board();
        let v = board.add_unit(Unit {
            uid: 1, x: 3, y: 3, hp: 3, max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::MASSIVE,  // NO PUSHABLE
            ..Default::default()
        });

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);  // try to push N
        assert_eq!((board.units[v].x, board.units[v].y), (3, 3),
                   "non-pushable unit must not move");
    }

    #[test]
    fn test_bump_against_edge_takes_one_damage() {
        // Pushing a unit off the board (no destination) → 1 bump damage.
        let mut board = make_test_board();
        let v = add_enemy(&mut board, 1, 0, 3, 3);  // at west edge

        let mut result = ActionResult::default();
        apply_push(&mut board, 0, 3, 3, &mut result);  // DIRS index 3 = west
        assert_eq!((board.units[v].x, board.units[v].y), (0, 3),
                   "edge bump leaves unit in place");
        assert_eq!(board.units[v].hp, 2, "1 bump damage from edge");
    }

    #[test]
    fn test_bump_against_mountain_damages_both() {
        // Mountain stops the push; unit takes 1; mountain HP -1.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Mountain;
        board.tile_mut(3, 4).building_hp = 2;
        let v = add_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);  // push N into mountain
        assert_eq!((board.units[v].x, board.units[v].y), (3, 3),
                   "mountain blocks push");
        assert_eq!(board.units[v].hp, 2, "1 bump damage");
        assert_eq!(board.tile(3, 4).building_hp, 1, "mountain damaged");
        assert_eq!(board.tile(3, 4).terrain, Terrain::Mountain,
                   "mountain still standing at 1 HP");
    }

    #[test]
    fn test_two_unit_collision_both_take_one_damage() {
        // Push A into occupied B's tile → A stays put, both take 1.
        let mut board = make_test_board();
        let a = add_enemy(&mut board, 1, 3, 3, 3);
        let b = add_enemy(&mut board, 2, 3, 4, 3);  // N of A

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);  // push A north into B
        assert_eq!((board.units[a].x, board.units[a].y), (3, 3),
                   "A doesn't move into occupied B");
        assert_eq!(board.units[a].hp, 2, "A takes 1 bump");
        assert_eq!(board.units[b].hp, 2, "B takes 1 bump");
    }

    #[test]
    fn test_push_into_chasm_kills_ground_unit() {
        // Chasm is deadly to non-flying ground units.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Chasm;
        let v = add_enemy(&mut board, 1, 3, 3, 3);

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        assert_eq!(board.units[v].hp, 0, "chasm kills");
        assert_eq!(result.enemies_killed, 1);
    }

    #[test]
    fn test_flying_unit_survives_chasm_push() {
        // Flying units cross chasm/water/lava without dying.
        let mut board = make_test_board();
        board.tile_mut(3, 4).terrain = Terrain::Chasm;
        let f = board.add_unit(Unit {
            uid: 1, x: 3, y: 3, hp: 3, max_hp: 3,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE | UnitFlags::FLYING,
            ..Default::default()
        });

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);
        assert_eq!(board.units[f].hp, 3, "flying unit survives chasm");
        assert_eq!((board.units[f].x, board.units[f].y), (3, 4),
                   "flying unit landed on chasm tile");
    }

    // ── Brute_Sniper distance scaling (weapons_brute.lua:969-991) ────────
    // damage = max(0, min(MaxDamage, tile_distance - 1)). MaxDamage=2 at base.
    // Push (Forward) fires regardless of damage value.

    /// Adjacent target (tile_distance=1) → 0 damage; push still fires.
    #[test]
    fn test_brute_sniper_adjacent_target_zero_damage() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteSniper);
        let enemy_idx = add_enemy(&mut board, 1, 3, 4, 3);
        let result = simulate_weapon(&mut board, mech_idx, WId::BruteSniper, 3, 4);
        assert_eq!(board.units[enemy_idx].hp, 3, "adjacent shot deals 0 damage");
        assert_eq!(result.enemies_killed, 0);
        assert_eq!(board.units[enemy_idx].y, 5,
            "Forward push still fires at zero damage");
    }

    /// tile_distance=2 → 1 damage.
    #[test]
    fn test_brute_sniper_dist2_one_damage() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteSniper);
        let enemy_idx = add_enemy(&mut board, 1, 3, 5, 3);
        simulate_weapon(&mut board, mech_idx, WId::BruteSniper, 3, 5);
        assert_eq!(board.units[enemy_idx].hp, 2, "dist=2 shot deals 1 damage");
    }

    /// tile_distance=3 → 2 damage (== MaxDamage at base).
    #[test]
    fn test_brute_sniper_dist3_caps_at_max_damage() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 3, 3, 3, WId::BruteSniper);
        let enemy_idx = add_enemy(&mut board, 1, 3, 6, 3);
        simulate_weapon(&mut board, mech_idx, WId::BruteSniper, 3, 6);
        assert_eq!(board.units[enemy_idx].hp, 1, "dist=3 caps at MaxDamage=2");
    }

    /// Long-range target (tile_distance=4, with empty space behind so push
    /// doesn't bump-bonus the damage) → exactly MaxDamage=2.
    #[test]
    fn test_brute_sniper_long_range_exactly_max_damage() {
        let mut board = make_test_board();
        let mech_idx = add_mech(&mut board, 0, 0, 0, 3, WId::BruteSniper);
        // Shooter at (0,0), target at (0,4) → tile_distance=4, scaled=3,
        // capped at MaxDamage=2. Tile (0,5) is empty → unit pushes cleanly,
        // no bump damage.
        let enemy_idx = add_enemy(&mut board, 1, 0, 4, 5);
        simulate_weapon(&mut board, mech_idx, WId::BruteSniper, 0, 4);
        assert_eq!(board.units[enemy_idx].hp, 5 - 2,
            "dist=4 still caps at MaxDamage=2");
        assert_eq!(board.units[enemy_idx].y, 5,
            "Forward push moves target one tile (no bump)");
    }

    #[test]
    fn test_no_chain_push_collision_with_space_behind() {
        // A pushed into B doesn't transfer the push to B even with empty
        // space behind B. Both take collision damage; A stays put; B
        // stays put.
        let mut board = make_test_board();
        let a = add_enemy(&mut board, 1, 3, 3, 3);
        let b = add_enemy(&mut board, 2, 3, 4, 3);
        // Tile at (3,5) is empty Ground — would receive the chain if it existed.

        let mut result = ActionResult::default();
        apply_push(&mut board, 3, 3, 0, &mut result);  // push A north
        assert_eq!((board.units[a].x, board.units[a].y), (3, 3));
        assert_eq!((board.units[b].x, board.units[b].y), (3, 4),
                   "no chain — B doesn't move into the empty (3,5)");
        assert_eq!(board.units[a].hp, 2);
        assert_eq!(board.units[b].hp, 2);
    }
}
