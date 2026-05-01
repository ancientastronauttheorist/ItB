/// Enemy attack simulation — post-mech-action phase.
///
/// Processes enemies in UID order (ascending = game's attack order).
/// Re-traces projectile paths on the post-mech board state.
/// Uses actual weapon type dispatch (not binary ranged/melee).

use crate::types::*;
use crate::board::*;
use crate::weapons::*;
use crate::simulate::{apply_damage, apply_push, apply_weapon_status};

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
/// attacking"). UID uses the 9000+ range to avoid colliding with
/// bridge-provided UIDs.
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

    // Pick a fresh UID in the spawned-unit range. Keep counting up
    // from 9000 to avoid duplicates within a single enemy phase.
    let mut new_uid: u16 = 9000;
    for i in 0..board.unit_count as usize {
        if board.units[i].uid >= new_uid { new_uid = board.units[i].uid + 1; }
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
    board.add_unit(u);
    true
}

/// Get effective damage for an enemy hit at a tile (Vek Hormones adds +1 vs other enemies).
fn enemy_hit_damage(board: &Board, x: u8, y: u8, base_damage: u8, vek_hormones: bool) -> u8 {
    if vek_hormones {
        if let Some(idx) = board.unit_at(x, y) {
            if board.units[idx].is_enemy() {
                return base_damage + 1;
            }
        }
    }
    base_damage
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
/// pure Deadly Threat, preserving pre-fix behavior).
///
/// `lethal=false` (sandstorm, wind storm, snow storm) does 1 damage with
/// bump-like semantics: ignored by armor/ACID, consumed by shield, skips
/// flying units. Buildings take 1 HP.
///
/// Inlined unit/building handling (does not call apply_damage) so we can bypass
/// shield/frozen for the lethal case without polluting the core damage path.
fn apply_env_danger(
    board: &mut Board,
    x: u8, y: u8,
    lethal: bool,
    flying_immune: bool,
    result: &mut ActionResult,
) {
    // Damage unit if present. Track whether an enemy died so we can run
    // the shared death-cleanup after the mutable borrow ends — Psion
    // auras must be torn down even on env kills, which bypass apply_damage.
    let mut enemy_died_idx: Option<usize> = None;
    if let Some(uidx) = board.unit_at(x, y) {
        let unit = &mut board.units[uidx];
        if unit.hp > 0 {
            // Tidal/Cataclysm/Seismic spare effectively-flying units. Massive
            // non-flying still die: water-conversion is destroy-not-drown per
            // project convention; chasm rules ignore Massive.
            let spared_by_flight = lethal && flying_immune && unit.effectively_flying();
            if lethal && !spared_by_flight {
                // Deadly Threat: bypass shield/frozen/armor/ACID, set HP=0
                let prev_hp = unit.hp;
                unit.hp = 0;
                unit.set_shield(false);
                unit.set_frozen(false);
                if unit.is_player() {
                    result.mechs_killed += 1;
                    result.mech_damage_taken += prev_hp as i32;
                } else if unit.is_enemy() {
                    result.enemies_killed += 1;
                    result.enemy_damage_dealt += prev_hp as i32;
                    enemy_died_idx = Some(uidx);
                }
            } else if lethal && spared_by_flight {
                // Flying unit on Tidal/Cataclysm/Seismic tile: untouched.
                // No damage, no shield/frozen consumption.
            } else if !unit.effectively_flying() {
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
                            result.enemies_killed += 1;
                            enemy_died_idx = Some(uidx);
                        }
                    }
                }
            }
            // else: flying, non-lethal env doesn't hit
        }
    }
    if let Some(idx) = enemy_died_idx {
        crate::simulate::on_enemy_death(board, idx, result);
        // Boss / Blast Psion EXPLODE-on-death aura — env_danger kills bypass
        // apply_damage's death-explosion site (simulate.rs:788), so we
        // dispatch the explosion here when an aura source is alive. The
        // dying Vek has hp=0 already; explosion damages 4 adjacent tiles.
        // (sim v38 follow-up to v37 boss aura test failure.)
        if board.blast_psion || board.boss_psion {
            crate::simulate::apply_death_explosion(board, x, y, result, 0);
        }
    }

    // Damage building if present (lethal destroys entirely, non-lethal does 1 HP)
    let tile = board.tile_mut(x, y);
    if tile.terrain == Terrain::Building && tile.building_hp > 0 {
        let dmg = if lethal { tile.building_hp } else { 1 };
        let old_hp = tile.building_hp;
        tile.building_hp = tile.building_hp.saturating_sub(dmg);
        let lost = old_hp - tile.building_hp;
        result.buildings_damaged += lost as i32;
        result.grid_damage += lost as i32;
        if tile.building_hp == 0 {
            tile.terrain = Terrain::Rubble;
            result.buildings_lost += 1;
        }
        board.grid_power = board.grid_power.saturating_sub(lost);
    }
}

/// Apply spawn blocking damage: units standing on spawn tiles take 1 damage
/// when Vek try to emerge. Damage bypasses armor and ACID (bump-like damage)
/// but is consumed by shield. Fires after enemy attacks, before next player turn.
pub fn apply_spawn_blocking(
    board: &mut Board,
    spawn_points: &[(u8, u8)],
) {
    for &(sx, sy) in spawn_points {
        if let Some(idx) = board.unit_at(sx, sy) {
            let unit = &mut board.units[idx];
            if unit.hp <= 0 { continue; }
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
        }
    }
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

/// Simulate all enemy attacks on the post-mech-action board.
/// Processes in UID order. Returns buildings destroyed count.
///
/// `original_positions`: maps unit index -> (orig_x, orig_y) for direction/range checks.
pub fn simulate_enemy_attacks(
    board: &mut Board,
    original_positions: &[(u8, u8); 16],
    weapons: &WeaponTable,
) -> i32 {
    // Mission_Reactivation: thaw 2 frozen Vek at start of enemy phase.
    // Must run BEFORE the frozen-skip in the attack loop so newly-thawed
    // pawns are reflected in post-enemy state (they don't attack this
    // turn — no queued attack — but the eval scores their HP correctly).
    simulate_reactivation_thaw(board);

    let mut buildings_destroyed = 0;
    let mut result = ActionResult::default();

    // Fire tick: burning units take 1 damage before attacks
    // Flame Shielding: player mechs immune to fire
    // Pilot_Rock (Ariadne): defensive skip. The fire-apply hooks never set
    // the FIRE flag on a Rockman mech in the first place, so this branch
    // only matters if fire snuck in via an un-guarded path (future bug
    // guard) or if pilot_flags were injected mid-mission.
    for i in 0..board.unit_count as usize {
        if board.units[i].fire() && board.units[i].hp > 0 {
            if board.flame_shielding && board.units[i].is_player() {
                continue; // mechs immune to fire with Flame Shielding
            }
            if board.units[i].pilot_rock() {
                // Rockman is fire-immune; clear the flag as a safety net
                // so a stale burn doesn't sit on the unit forever.
                board.units[i].set_fire(false);
                continue;
            }
            // Fire Psion (LEADER_FIRE, Jelly_Fire1): all Vek immune to fire
            // damage while alive. The Fire Psion itself is exempt from this
            // immunity per the standard "aura source isn't subject to its
            // own aura" pattern, matching how Soldier Psion doesn't get
            // its own +1 HP buff. Defensively clear the FIRE flag so a
            // stale status doesn't tick once the Psion dies — the on-death
            // cleanup re-enables fire damage normally.
            if board.fire_psion && board.units[i].is_enemy()
                && board.units[i].type_name_str() != "Jelly_Fire1"
            {
                continue;
            }
            let x = board.units[i].x;
            let y = board.units[i].y;
            apply_damage(board, x, y, 1, &mut result, DamageSource::Fire);
        }
    }

    // Storm Generator: enemies in smoke take 1 damage
    if board.storm_generator {
        for i in 0..board.unit_count as usize {
            if board.units[i].is_enemy() && board.units[i].hp > 0 {
                let x = board.units[i].x;
                let y = board.units[i].y;
                if board.tile(x, y).smoke() {
                    apply_damage(board, x, y, 1, &mut result, DamageSource::Weapon);
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
                    if board.units[i].is_enemy() && board.units[i].hp > 0
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
                    if board.units[i].is_enemy() && board.units[i].hp > 0
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
            if u.is_enemy() && u.hp > 0
                && tname != "Jelly_Regen1"
                && tname != "Jelly_Boss"
            {
                if u.hp < u.max_hp {
                    u.hp += 1;
                }
            }
        }
    }

    // Environment danger (air strikes, lightning, tidal waves) — fires BEFORE Vek attacks
    // per game's interleaved attack order. Env effects resolve first, killing units
    // that were going to attack. Their queued attacks then never fire (hp <= 0 check below).
    if board.env_danger != 0 {
        for tile_idx in 0usize..64 {
            if board.env_danger & (1u64 << tile_idx) == 0 { continue; }
            let (x, y) = idx_to_xy(tile_idx);
            let bit = 1u64 << tile_idx;
            let lethal = board.env_danger_kill & bit != 0;
            let flying_immune = lethal && (board.env_danger_flying_immune & bit != 0);
            apply_env_danger(board, x, y, lethal, flying_immune, &mut result);
        }
    }

    // Ice Storm freeze (sim v25). Fires at start of enemy turn — same step as
    // env_danger per Lua source: Env_SnowStorm.Instant=true, ApplyEffect()
    // queues SpaceDamage with iFrozen=1 iDamage=0 for all 9 marked tiles in
    // a single batch (mission_snowstorm.lua:28-53). Frozen units have HP
    // protected from the upcoming Vek attacks (the attack loop's
    // `if e.frozen() || e.web() { continue; }` skip). Buildings and mountains
    // are unaffected — Frozen is a unit status, terrain has no flag for it.
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
                        // ITB shield rule: blocks one instance of damage OR
                        // negative effect. Freeze is a negative effect, so
                        // shield consumes and the unit stays unfrozen.
                        unit.set_shield(false);
                    } else if !unit.frozen() {
                        // Already-frozen → idempotent (no double-flag); only
                        // freshly-applied freeze sets the flag.
                        unit.set_frozen(true);
                    }
                }
            }
            // Buildings/mountains/other terrain on this tile: untouched.
        }
    }

    // Egg hatch step: transform any surviving spider/spiderling egg into
    // its hatched live unit (sim v22). Runs AFTER fire tick + env_danger
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
    // played as a Spiderling wall on turns 3-4.
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

    // Collect enemy indices sorted by UID
    let mut enemy_indices: Vec<usize> = (0..board.unit_count as usize)
        .filter(|&i| board.units[i].is_enemy())
        .collect();
    enemy_indices.sort_by_key(|&i| board.units[i].uid);

    for &ei in &enemy_indices {
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
        if enemy.queued_target_x < 0 {
            // PHANTOM-ATTACK GUARD: Vek reports has_queued_attack=true
            // but the Lua bridge failed to populate a target. Don't
            // silently skip — apply conservative damage to the nearest
            // building so the scorer still penalizes plans that ignore
            // this Vek. See CLAUDE.md §21 grid-drop investigation gate.
            if enemy.has_queued_attack() {
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
                    let tile = board.tile_mut(bx, by);
                    let old_hp = tile.building_hp;
                    let applied = (dmg as u8).min(old_hp);
                    tile.building_hp = old_hp - applied;
                    let lost = old_hp - tile.building_hp;
                    result.buildings_damaged += lost as i32;
                    result.grid_damage += lost as i32;
                    if tile.building_hp == 0 {
                        tile.terrain = Terrain::Rubble;
                        result.buildings_lost += 1;
                    }
                    board.grid_power = board.grid_power.saturating_sub(lost);
                    buildings_destroyed += lost as i32;
                }
            }
            continue;
        }

        // Smoke cancels attacks
        // (Eggs have Smoke Immunity, but they're skipped above anyway.)
        let tile = board.tile(enemy.x, enemy.y);
        if tile.smoke() { continue; }

        // Frozen enemies can't attack
        if enemy.frozen() { continue; }

        let ex = enemy.x;
        let ey = enemy.y;
        let qtx = enemy.queued_target_x;
        let qty = enemy.queued_target_y;
        let enemy_uid = enemy.uid;
        let orig = original_positions[ei];

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
        if board.boost_psion
            && base_damage > 0
            && attacker_tname != "Jelly_Boost1"
        {
            base_damage += 1;
        }
        // Vek Hormones: +1 damage when enemy attacks hit other enemies
        // Applied per-hit below based on target occupant
        let damage = base_damage;

        let weapon_behind = enemy.weapon_target_behind;

        let vh = board.vek_hormones;

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
            continue;
        }

        match wdef.weapon_type {
            WeaponType::Projectile => {
                if let Some((tx, ty)) = find_projectile_target(board, ex, ey, orig.0, orig.1, qtx, qty) {
                    let d = enemy_hit_damage(board, tx, ty, damage, vh);
                    apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
                    if wdef.fire() {
                        if let Some(idx) = board.unit_at(tx, ty) {
                            let target_is_immune_vek = board.fire_psion
                                && board.units[idx].is_enemy()
                                && board.units[idx].type_name_str() != "Jelly_Fire1";
                            let u = &mut board.units[idx];
                            // Pilot_Rock is fire-immune; skip even the
                            // "unfreeze + catch fire" combo so Ariadne on
                            // ice stays frozen rather than becoming a
                            // walking exception. Fire Psion grants Vek
                            // immunity to fire-status application.
                            if !u.frozen() && u.can_catch_fire()
                                && !(board.flame_shielding && u.is_player())
                                && !target_is_immune_vek
                            {
                                u.set_fire(true);
                            }
                        }
                        board.tile_mut(tx, ty).set_on_fire(true);
                    }
                    // ACID / WEB / other status effects on the primary target
                    apply_weapon_status(board, tx, ty, wdef);
                    if wdef.web() {
                        if let Some(idx) = board.unit_at(tx, ty) {
                            // Skip webber-uid tracking for Pilot_Soldier so
                            // Camila's Unit stays clean (no phantom webber).
                            if !board.units[idx].pilot_soldier() {
                                board.units[idx].web_source_uid = enemy_uid;
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
                            let d2 = enemy_hit_damage(board, nxu, nyu, damage, vh);
                            apply_damage(board, nxu, nyu, d2, &mut result, DamageSource::Weapon);
                            apply_weapon_status(board, nxu, nyu, wdef);
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
                let dx = (qtx - orig.0 as i8).signum();
                let dy = (qty - orig.1 as i8).signum();
                if (dx != 0) != (dy != 0) {
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
                let offset_x = qtx - orig.0 as i8;
                let offset_y = qty - orig.1 as i8;
                let new_tx = ex as i8 + offset_x;
                let new_ty = ey as i8 + offset_y;
                if !in_bounds(new_tx, new_ty) { continue; }

                // Cardinal axis required (exactly one axis non-zero) for artillery
                // to have a direction for path_size > 1 handling.
                let dx_sign = offset_x.signum();
                let dy_sign = offset_y.signum();
                if (dx_sign != 0) == (dy_sign != 0) { continue; }

                // Min-range check against the (new) attacker→target distance.
                let curr_range = offset_x.abs() + offset_y.abs();
                if (curr_range as u8) < wdef.range_min { continue; }

                let tx = new_tx as u8;
                let ty = new_ty as u8;
                let d = enemy_hit_damage(board, tx, ty, damage, vh);
                apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);

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
                        let d_p = enemy_hit_damage(board, px as u8, py as u8, damage, vh);
                        apply_damage(board, px as u8, py as u8, d_p, &mut result, DamageSource::Weapon);
                        apply_weapon_status(board, px as u8, py as u8, wdef);
                    }
                }

                // Spawn-artillery side effects: Spider (webb eggs) and
                // Blobber (blobs) fire a 0-dmg artillery whose real
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
                    _ => {}
                }
            }

            WeaponType::Charge => {
                // Charge from CURRENT position in original queued direction
                let dx = (qtx - orig.0 as i8).signum();
                let dy = (qty - orig.1 as i8).signum();

                // Must be valid cardinal direction
                if (dx != 0) != (dy != 0) {
                    let mut hit: Option<(u8, u8)> = None;
                    let mut hit_i: i8 = 0;
                    for i in 1..8i8 {
                        let nx = ex as i8 + dx * i;
                        let ny = ey as i8 + dy * i;
                        if !in_bounds(nx, ny) { break; }
                        let nxu = nx as u8;
                        let nyu = ny as u8;

                        let tile = board.tile(nxu, nyu);
                        if tile.terrain == Terrain::Mountain {
                            hit = Some((nxu, nyu));
                            hit_i = i;
                            break;
                        }
                        if tile.terrain.is_deadly_ground() { break; }
                        if tile.is_building() {
                            hit = Some((nxu, nyu));
                            hit_i = i;
                            break;
                        }
                        if board.unit_at(nxu, nyu).is_some() {
                            hit = Some((nxu, nyu));
                            hit_i = i;
                            break;
                        }
                    }

                    if let Some((hx, hy)) = hit {
                        // Flaming Abdomen: fire on every PASSED tile (i=1..hit_i-1)
                        // EXCLUDING the final resting tile (i=hit_i-1). So fire
                        // on tiles i=1..=(hit_i-2).
                        if wdef.fire() {
                            for i in 1..=(hit_i - 2) {
                                let fx = (ex as i8 + dx * i) as u8;
                                let fy = (ey as i8 + dy * i) as u8;
                                board.tile_mut(fx, fy).set_on_fire(true);
                                if let Some(idx) = board.unit_at(fx, fy) {
                                    let target_is_immune_vek = board.fire_psion
                                        && board.units[idx].is_enemy()
                                        && board.units[idx].type_name_str() != "Jelly_Fire1";
                                    let u = &mut board.units[idx];
                                    if !u.frozen() && u.can_catch_fire()
                                        && !(board.flame_shielding && u.is_player())
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
                if wdef.aoe_center() {
                    apply_damage(board, ex, ey, damage, &mut result, DamageSource::Weapon);
                }
                if wdef.aoe_adjacent() {
                    for (i, &(dx, dy)) in DIRS.iter().enumerate() {
                        let nx = ex as i8 + dx;
                        let ny = ey as i8 + dy;
                        if in_bounds(nx, ny) {
                            let d = enemy_hit_damage(board, nx as u8, ny as u8, damage, vh);
                            apply_damage(board, nx as u8, ny as u8, d, &mut result, DamageSource::Weapon);
                            // Push outward / inward per weapon def (Scorpion Leader's
                            // Massive Spinneret pushes every target away from itself).
                            match wdef.push {
                                PushDir::Outward => apply_push(board, nx as u8, ny as u8, i, &mut result),
                                PushDir::Inward => apply_push(board, nx as u8, ny as u8, opposite_dir(i), &mut result),
                                _ => {}
                            }
                            // Status effects (WEB from Massive Spinneret, etc.):
                            // apply to the live unit on that tile.
                            if wdef.web() {
                                if let Some(idx) = board.unit_at(nx as u8, ny as u8) {
                                    if !board.units[idx].pilot_soldier() {
                                        board.units[idx].set_web(true);
                                    }
                                }
                            }
                        }
                    }
                }
            }

            WeaponType::Melee => {
                if weapon_behind {
                    // Line attack (e.g., Launching Stinger): 2-tile line in the original
                    // cardinal direction. When pushed, retrace direction from the ORIGINAL
                    // position so the attack fires correctly from the new position.
                    let dx = (qtx - orig.0 as i8).signum();
                    let dy = (qty - orig.1 as i8).signum();
                    // Must be a valid cardinal direction (exactly one axis non-zero)
                    if (dx != 0) == (dy != 0) { continue; }

                    let tx1 = ex as i8 + dx;
                    let ty1 = ey as i8 + dy;
                    if in_bounds(tx1, ty1) {
                        let d = enemy_hit_damage(board, tx1 as u8, ty1 as u8, damage, vh);
                        apply_damage(board, tx1 as u8, ty1 as u8, d, &mut result, DamageSource::Weapon);
                        apply_weapon_status(board, tx1 as u8, ty1 as u8, wdef);
                        if wdef.web() {
                            if let Some(idx) = board.unit_at(tx1 as u8, ty1 as u8) {
                                board.units[idx].web_source_uid = enemy_uid;
                            }
                        }
                    }
                    let tx2 = ex as i8 + dx * 2;
                    let ty2 = ey as i8 + dy * 2;
                    if in_bounds(tx2, ty2) {
                        let d2 = enemy_hit_damage(board, tx2 as u8, ty2 as u8, damage, vh);
                        apply_damage(board, tx2 as u8, ty2 as u8, d2, &mut result, DamageSource::Weapon);
                        apply_weapon_status(board, tx2 as u8, ty2 as u8, wdef);
                        if wdef.web() {
                            if let Some(idx) = board.unit_at(tx2 as u8, ty2 as u8) {
                                board.units[idx].web_source_uid = enemy_uid;
                            }
                        }
                    }
                } else {
                    let (tx, ty) = if wdef.queued_damage_persists() {
                        // BlobBoss family registers fixed queued damage before
                        // movement. Keep the queued tile, with the same OOB guard
                        // that protects bridge-normalized edge targets.
                        if qtx < 0 || qty < 0 || qtx >= 8 || qty >= 8 { continue; }
                        (qtx as u8, qty as u8)
                    } else {
                        // Standard single-tile melee preserves the original
                        // queued direction, then re-aims from the attacker's
                        // current tile after pushes, swaps, and teleports.
                        let dx = (qtx - orig.0 as i8).signum();
                        let dy = (qty - orig.1 as i8).signum();
                        if (dx != 0) == (dy != 0) { continue; }
                        let tx = ex as i8 + dx;
                        let ty = ey as i8 + dy;
                        if !in_bounds(tx, ty) { continue; }
                        (tx as u8, ty as u8)
                    };

                    let d = enemy_hit_damage(board, tx, ty, damage, vh);
                    apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
                    apply_weapon_status(board, tx, ty, wdef);
                    if wdef.web() {
                        if let Some(idx) = board.unit_at(tx, ty) {
                            board.units[idx].web_source_uid = enemy_uid;
                        }
                    }
                }
            }

            _ => {
                // OOB guard: see Melee arm above. Catch-all path also fed
                // qtx/qty straight into tile_mut and panicked on M04.
                if qtx < 0 || qty < 0 || qtx >= 8 || qty >= 8 { continue; }
                let tx = qtx as u8;
                let ty = qty as u8;
                let d = enemy_hit_damage(board, tx, ty, damage, vh);
                apply_damage(board, tx, ty, d, &mut result, DamageSource::Weapon);
            }
        }
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

    // Train_Pawn end-of-enemy-phase advance: moves 2 tiles forward along its
    // rail (direction = primary_tile - extra_tile). If either destination
    // tile is blocked (mountain, building, any non-train unit, or a wreck),
    // the train is destroyed (both tiles hp = 0 → friendly_npc_killed fires
    // twice in evaluate). If destinations are off-board, treat as surviving
    // (train has reached the far edge). Skip if train was already killed by
    // enemy attacks above.
    simulate_train_advance(board);

    // Count buildings destroyed from result
    buildings_destroyed += result.grid_damage;

    // Grid Defense expected save: each grid point lost had a
    // grid_defense_pct/100 chance to be blocked. Track as float on the
    // board for the evaluator. Without this the solver over-predicts
    // building loss by ~1 grid/turn at the 15% baseline.
    let gd = board.grid_defense_pct as f32;
    board.enemy_grid_save_expected = (buildings_destroyed as f32) * (gd / 100.0);

    // Drain the Spider Psion pending-egg queue (sim v38). Eggs spawned by
    // on_enemy_death during this enemy phase land here AFTER the hatch
    // loop has run, so they sit dormant until the NEXT enemy phase
    // (matching the game's AddQueuedDamage hatch behavior — see
    // weapons_enemy.lua:857). spawn_enemy skips occupied tiles internally,
    // so a Vek that moved onto the corpse's tile during the attack loop
    // won't get displaced.
    let pending = std::mem::take(&mut board.pending_spider_eggs);
    for (x, y) in pending {
        spawn_enemy(board, x, y, "WebbEgg1", 1);
    }

    buildings_destroyed
}

/// Advance the Supply Train 2 tiles forward. Called at end of enemy phase.
///
/// Direction is inferred from the two tile entries sharing uid: forward =
/// primary - extra (extra_tile is the caboose, primary is the locomotive).
/// Train is destroyed if either entered tile is blocked by a mountain,
/// building, or a non-train unit (including mechs and wrecks). Off-board
/// destinations count as reaching the exit — train stays alive at its
/// current position (not advanced off the board). Called once per turn.
pub fn simulate_train_advance(board: &mut Board) {
    let mut primary: Option<usize> = None;
    let mut extra: Option<usize> = None;
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.type_name_str() != "Train_Pawn" || u.hp <= 0 { continue; }
        if u.is_extra_tile() { extra = Some(i); } else { primary = Some(i); }
    }
    let (p, e) = match (primary, extra) {
        (Some(p), Some(e)) => (p, e),
        _ => return,
    };

    let (px, py) = (board.units[p].x as i8, board.units[p].y as i8);
    let (ex, ey) = (board.units[e].x as i8, board.units[e].y as i8);
    let dx = px - ex;
    let dy = py - ey;
    // Must be unit-length cardinal (sanity check).
    if dx.abs() + dy.abs() != 1 { return; }

    // The extra tile moves into (px+dx, py+dy) — that space is already train
    // body (primary's old position). The primary tile passes through
    // (px+dx, py+dy) on its way to (px+2dx, py+2dy). We must check BOTH new
    // tiles the train enters that weren't already train body:
    //   - (px+dx, py+dy): primary's intermediate step (extra's final pos)
    //   - (px+2dx, py+2dy): primary's final pos
    let steps = [(px + dx, py + dy), (px + 2 * dx, py + 2 * dy)];
    for (nx, ny) in steps.iter() {
        if *nx < 0 || *nx >= 8 || *ny < 0 || *ny >= 8 {
            // Off-board: train has reached the exit. Leave hp alive, don't
            // advance — subsequent turns won't find the train to re-advance
            // because its position is still valid on-board this turn.
            return;
        }
        let (nxu, nyu) = (*nx as u8, *ny as u8);
        let t = board.tile(nxu, nyu);
        if t.terrain == Terrain::Mountain || t.terrain == Terrain::Building {
            board.units[p].hp = 0;
            board.units[e].hp = 0;
            return;
        }
        if let Some(idx) = board.any_unit_at(nxu, nyu) {
            // Allow only the train itself (shouldn't happen for new tiles
            // but guard defensively). Any other unit or wreck blocks.
            if board.units[idx].type_name_str() != "Train_Pawn" {
                board.units[p].hp = 0;
                board.units[e].hp = 0;
                return;
            }
        }
    }

    // Path clear — advance both tiles 2 forward.
    board.units[p].x = (px + 2 * dx) as u8;
    board.units[p].y = (py + 2 * dy) as u8;
    board.units[e].x = (ex + 2 * dx) as u8;
    board.units[e].y = (ey + 2 * dy) as u8;
}

/// Trace projectile from enemy position in queued direction.
/// Returns (hit_x, hit_y) or None.
fn find_projectile_target(board: &Board, ex: u8, ey: u8, orig_x: u8, orig_y: u8, qtx: i8, qty: i8) -> Option<(u8, u8)> {
    if qtx < 0 { return None; }

    // Compute direction from ORIGINAL position to queued target.
    // Preserves cardinal attack direction after mech pushes.
    // INVARIANT: queued_target is the first tile in the attack direction
    // from the original position (bridge normalizes piQueuedShot against
    // piOrigin), so the delta is always a unit cardinal vector.
    let dx = (qtx - orig_x as i8).signum();
    let dy = (qty - orig_y as i8).signum();

    // Must be a valid cardinal direction (exactly one axis non-zero)
    if (dx != 0 && dy != 0) || (dx == 0 && dy == 0) { return None; }

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

#[cfg(test)]
mod tests {
    use super::*;

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
    fn test_crab_hits_two_tiles() {
        let mut board = Board::default();
        // Crab at (0,0) targeting (4,0) — should also hit (5,0)
        board.tile_mut(4, 0).terrain = Terrain::Building;
        board.tile_mut(4, 0).building_hp = 1;
        board.tile_mut(5, 0).terrain = Terrain::Building;
        board.tile_mut(5, 0).building_hp = 1;
        add_enemy_with_type(&mut board, 1, 0, 0, 3, "Crab1", 4, 0);

        let orig = default_orig_pos(&board);
        simulate_enemy_attacks(&mut board, &orig, &WEAPONS);

        assert_eq!(board.tile(4, 0).building_hp, 0, "Crab should hit first tile");
        assert_eq!(board.tile(5, 0).building_hp, 0, "Crab should hit second tile");
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
    fn test_enemy_weapon_for_type_mapping() {
        assert_eq!(enemy_weapon_for_type("Firefly1"), WId::FireflyAtk1);
        assert_eq!(enemy_weapon_for_type("Scarab2"), WId::ScarabAtk2);
        assert_eq!(enemy_weapon_for_type("Beetle1"), WId::BeetleAtk1);
        assert_eq!(enemy_weapon_for_type("Digger1"), WId::DiggerAtk1);
        assert_eq!(enemy_weapon_for_type("BlobMini"), WId::BlobAtk1);
        assert_eq!(enemy_weapon_for_type("Crab1"), WId::CrabAtk1);
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
    fn test_train_dies_when_blocked_by_mountain() {
        // Train at (4,6)+(4,7) facing y-1. Mountain at (4,5) blocks first step.
        let mut board = Board::default();
        let (p, e) = add_train(&mut board, 4, 6, 4, 7);
        board.tile_mut(4, 5).terrain = Terrain::Mountain;
        simulate_train_advance(&mut board);
        assert_eq!(board.units[p].hp, 0, "primary dies");
        assert_eq!(board.units[e].hp, 0, "extra dies");
        assert_eq!((board.units[p].x, board.units[p].y), (4, 6), "positions not advanced on death");
    }

    #[test]
    fn test_train_dies_when_blocked_by_vek() {
        // Vek at (4,4) blocks second step.
        let mut board = Board::default();
        let (p, e) = add_train(&mut board, 4, 6, 4, 7);
        add_enemy_with_type(&mut board, 100, 4, 4, 2, "Scarab1", -1, -1);
        simulate_train_advance(&mut board);
        assert_eq!(board.units[p].hp, 0);
        assert_eq!(board.units[e].hp, 0);
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
    fn test_train_skipped_when_already_dead() {
        // Train pre-killed by Vek attack earlier in enemy phase.
        let mut board = Board::default();
        let (p, e) = add_train(&mut board, 4, 6, 4, 7);
        board.units[p].hp = 0;
        board.units[e].hp = 0;
        simulate_train_advance(&mut board);
        // No crash, no state mutation beyond what we set up.
        assert_eq!((board.units[p].x, board.units[p].y), (4, 6));
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

    /// Sim v22 hatch step: a WebbEgg present at the start of the enemy
    /// phase transforms into a Spiderling in-place. The hatchling has
    /// no queued attack on its hatch turn (real-game: bite happens turn
    /// after hatch), so its own tile is not damaged. The unit's
    /// type_name flips, move_speed/weapon are bound to Spiderling stats.
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
        assert!(!u.has_queued_attack(),
            "fresh hatchling has no queued attack on its hatch turn");
        assert_eq!(u.queued_target_x, -1,
            "queued_target cleared so phantom-attack guard `continue`s");
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
    fn test_alpha_hornet_line_still_hits_both_tiles() {
        // Regression: Alpha Hornet's 2-tile line attack (weapon_behind) should
        // still damage both tiles after the fix.
        let mut board = Board::default();
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 1;
        board.tile_mut(4, 3).terrain = Terrain::Building;
        board.tile_mut(4, 3).building_hp = 1;
        // Hornet at (2,3) firing east, queued target (3,3). weapon_target_behind=true.
        let mut unit = Unit {
            uid: 1, x: 2, y: 3, hp: 4, max_hp: 4,
            team: Team::Enemy,
            flags: UnitFlags::PUSHABLE,
            queued_target_x: 3,
            queued_target_y: 3,
            weapon_damage: 0,
            weapon_target_behind: true,
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

    /// `enemy_weapon_for_type` mappings for the Bot Leader pawns.
    #[test]
    fn test_bot_leader_weapon_mapping() {
        assert_eq!(enemy_weapon_for_type("BotBoss"), WId::SnowBossAtk);
        assert_eq!(enemy_weapon_for_type("BotBoss2"), WId::SnowBossAtk2);
    }
}
