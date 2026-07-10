/// JSON serialization/deserialization bridge.
///
/// Converts bridge JSON (from /tmp/itb_state.json) into Board struct,
/// and Solution back to JSON for Python consumption.

use serde::{Deserialize, Serialize};
use crate::types::*;
use crate::board::*;
use crate::evaluate::EvalWeights;
use crate::weapons::*;
use crate::solver::{Solution, MechAction};

// ── Input JSON schema ────────────────────────────────────────────────────────

#[derive(Deserialize)]
pub struct JsonInput {
    pub tiles: Option<Vec<JsonTile>>,
    pub units: Option<Vec<JsonUnit>>,
    pub attack_order: Option<Vec<u16>>,
    pub grid_power: Option<u8>,
    pub grid_power_max: Option<u8>,
    pub turn: Option<u8>,
    pub total_turns: Option<u8>,
    pub remaining_spawns: Option<u32>,
    /// Set by Python `src/bridge/reader.py` when `mission_id` matches a
    /// `Mission_Infinite` subclass / boss mission (turn_limit=null in
    /// `data/mission_metadata.json`). On those missions the bridge
    /// reports total_turns = current_turn each turn, which would
    /// collapse `future_factor` to 0 and tell the solver kills are
    /// worthless. Floored at 0.5 in `evaluate::future_factor` instead.
    pub is_infinite_spawn: Option<bool>,
    pub spawning_tiles: Option<Vec<Vec<u8>>>,
    pub environment_danger: Option<Vec<Vec<u8>>>,
    pub environment_danger_v2: Option<Vec<Vec<u8>>>, // [[x, y, damage, kill_int, flying_immune?], ...]
    /// Ice Storm freeze tiles (sim v25). List of [x, y]. Vanilla Env_SnowStorm
    /// (Acid=false) routes here instead of `environment_danger`. Applied as
    /// `Status::Frozen=true` on units at start of enemy turn — non-lethal.
    /// NanoStorm (Env_NanoStorm = Env_SnowStorm:new{Acid=true}) does not use
    /// this field; its 1-damage acid effect rides the existing non-lethal
    /// `environment_danger_v2` path with kill_int=0.
    pub environment_freeze: Option<Vec<Vec<u8>>>,
    /// Top-level env type tag from the bridge (e.g. "tidal_or_cataclysm",
    /// "cataclysm_or_seismic", "lightning_or_airstrike", "wind", "sandstorm",
    /// "snow"). Used as a back-compat fallback when v2 entries lack the 5th
    /// `flying_immune` field — older recordings + boards stamped before
    /// SIMULATOR_VERSION 19 only have 4 fields. Never authoritative when the
    /// per-tile field is present.
    pub env_type: Option<String>,
    /// Mission_Wind live push direction as exported from the engine's DIR_*
    /// constants. Convert with `engine_dir_to_solver_dir` before storing on
    /// `Board`; the solver's internal DIRS use bridge-coordinate deltas.
    pub environment_wind_dir: Option<i8>,
    pub eval_weights: Option<EvalWeights>,
    pub mission_id: Option<String>,
    /// "Kill at least N enemies" target. Generic kill bonuses come from
    /// mission:GetKillBonus(); Mission_AcidTank is fixed at 4 acid kills.
    /// Missing / 0 -> no kill target on this mission; evaluator's step-function
    /// scoring is a no-op in that case.
    pub mission_kill_target: Option<u8>,
    /// "Kill N or fewer enemies" bonus cap (mission:GetPacifistCount(),
    /// difficulty-scaled). Missing / 0 → no cap on this mission.
    pub mission_kill_limit: Option<u8>,
    /// Cumulative this-mission kill counter (mission.KilledVek, or
    /// mission.AcidKills for Mission_AcidTank). Combined with simulated turn
    /// kills to decide whether a plan crosses or exceeds a kill-count objective.
    pub mission_kills_done: Option<u8>,
    /// Mission_Force "Destroy 2 mountains" objective progress.
    pub mission_mountain_target: Option<u8>,
    pub mission_mountains_destroyed: Option<u8>,
    pub mission_mountain_tiles: Option<Vec<Vec<u8>>>,
    /// Mission_Repair objective target/progress. Repair platforms are
    /// generic Item_Repair_Mine tiles; the game counts EVENT_REPAIR_PICKUP
    /// from any unit toward this progress.
    pub repair_platform_target: Option<u8>,
    pub repair_platforms_used: Option<u8>,
    /// Mission_FreezeBldg objective metadata. The bridge already marks each
    /// tile's live `frozen` flag; Python supplements this static objective tile
    /// list from saveData so the evaluator can distinguish objective buildings
    /// from incidental frozen terrain without a modloader restart.
    pub freeze_building_target: Option<u8>,
    pub freeze_building_tiles: Option<Vec<Vec<u8>>>,
    /// Phase 1 soft-disable blocklist — weapons the Python detector has
    /// flagged as drifting. Each entry's ``weapon_id`` becomes a bit in
    /// the ``disabled_mask`` returned by ``board_from_json``. Other
    /// fields (``expires_turn``, ``cause_pattern``, etc.) are tolerated
    /// but unused here — Python enforces expiry by filtering before the
    /// solve call.
    pub disabled_actions: Option<Vec<JsonDisabledAction>>,
    /// Phase 3 base overlay — per-field patches from
    /// ``data/weapon_overrides.json`` (human-reviewed + committed).
    /// Applied first, so runtime entries win precedence ties.
    pub weapon_overrides: Option<Vec<JsonWeaponOverride>>,
    /// Phase 3 runtime overlay — ephemeral per-solve patches that the
    /// loop may stage without a commit (Tier-3 hot-patch hook). Applied
    /// last, highest precedence.
    pub weapon_overrides_runtime: Option<Vec<JsonWeaponOverride>>,
    /// Teleporter pad pairs on Mission_Teleporter (Detritus disposal
    /// missions). Each entry = [x1, y1, x2, y2]. Bridge populates via the
    /// Board.AddTeleport hook in modloader.lua. Parsed into
    /// `Board::teleporter_pairs` only when `mission_id` is Mission_Teleporter
    /// (or absent on legacy recordings); stale pairs on other missions are
    /// ignored.
    pub teleporter_pairs: Option<Vec<Vec<u8>>>,
    /// Per-mission "do not kill X" bonus objective unit-type list. When
    /// non-empty, the evaluator's `volatile_enemy_killed` penalty fires
    /// only for kills whose `type_name` matches one of these strings —
    /// previously the penalty applied unconditionally to every Volatile
    /// Vek / GlowingScorpion kill regardless of the active mission's
    /// bonus objective. Source order:
    ///   1. Lua bridge (when modloader exposes the live mission's
    ///      bonus-objective unit type — e.g. BONUS_PROTECT_<X>),
    ///   2. Python-side `data/mission_bonus_objectives.json` keyed by
    ///      `mission_id`.
    /// Empty / missing on missions without a "do not kill" bonus → the
    /// penalty is a no-op (matches pre-fix behavior on those boards but
    /// removes the false-positive on Weather Watch boards where Volatiles
    /// aren't actually a protected objective).
    pub bonus_objective_unit_types: Option<Vec<String>>,
    /// Unit objectives that should be destroyed for mission bonus credit.
    /// Example: Mission_Hacking's Hacked_Building is a shielded enemy pawn,
    /// not an objective building tile.
    pub destroy_objective_unit_types: Option<Vec<String>>,
    /// Unit objectives that should survive for mission bonus credit, even
    /// when the bridge reports them as enemy-team before conversion.
    /// Example: Mission_Hacking's Cannon Bot appears as Snowtank1.
    pub protect_objective_unit_types: Option<Vec<String>>,
}

#[derive(Deserialize)]
pub struct JsonDisabledAction {
    pub weapon_id: String,
}

/// Per-field weapon-def patch, as emitted by the Python override loader.
/// Any field left as ``null`` (serde default) is not touched. ``flags_set``
/// / ``flags_clear`` take case-insensitive flag names (``FIRE``, ``acid``…);
/// unknown flag names are skipped silently so a typo can't brick a solve.
#[derive(Deserialize, Default)]
pub struct JsonWeaponOverride {
    pub weapon_id: String,
    pub weapon_type: Option<String>,
    pub damage: Option<u8>,
    pub damage_outer: Option<u8>,
    pub push: Option<String>,
    pub self_damage: Option<u8>,
    pub range_min: Option<u8>,
    pub range_max: Option<u8>,
    pub limited: Option<u8>,
    pub path_size: Option<u8>,
    pub flags_set: Option<Vec<String>>,
    pub flags_clear: Option<Vec<String>>,
}

/// Which layer a particular override came from. Emitted in
/// ``applied_overrides`` for audit.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OverlaySource { Base, Runtime }

impl OverlaySource {
    pub fn as_str(&self) -> &'static str {
        match self { Self::Base => "base", Self::Runtime => "runtime" }
    }
}

#[derive(Clone, Debug)]
pub struct OverlayEntry {
    pub wid: WId,
    pub patch: PartialWeaponDef,
    pub source: OverlaySource,
    /// Field names actually populated on this entry. Used for
    /// ``applied_overrides`` audit output.
    pub fields: Vec<&'static str>,
}

fn flag_from_name(name: &str) -> Option<WeaponFlags> {
    match name.to_ascii_uppercase().as_str() {
        "FIRE" => Some(WeaponFlags::FIRE),
        "ACID" => Some(WeaponFlags::ACID),
        "FREEZE" => Some(WeaponFlags::FREEZE),
        "SMOKE" => Some(WeaponFlags::SMOKE),
        "SHIELD" => Some(WeaponFlags::SHIELD),
        "WEB" => Some(WeaponFlags::WEB),
        "TARGETS_ALLIES" => Some(WeaponFlags::TARGETS_ALLIES),
        "BUILDING_DAMAGE" => Some(WeaponFlags::BUILDING_DAMAGE),
        "PHASE" => Some(WeaponFlags::PHASE),
        "AOE_CENTER" => Some(WeaponFlags::AOE_CENTER),
        "AOE_ADJACENT" => Some(WeaponFlags::AOE_ADJACENT),
        "AOE_BEHIND" => Some(WeaponFlags::AOE_BEHIND),
        "AOE_PERP" => Some(WeaponFlags::AOE_PERP),
        "CHAIN" => Some(WeaponFlags::CHAIN),
        "CHARGE" => Some(WeaponFlags::CHARGE),
        "FLYING_CHARGE" => Some(WeaponFlags::FLYING_CHARGE),
        "PUSH_SELF" => Some(WeaponFlags::PUSH_SELF),
        "FRIENDLY_IMMUNE" => Some(WeaponFlags::FRIENDLY_IMMUNE),
        "PATH_DAMAGE" => Some(WeaponFlags::PATH_DAMAGE),
        _ => None,
    }
}

fn parse_overlay_list(list: &[JsonWeaponOverride], source: OverlaySource) -> Vec<OverlayEntry> {
    let mut out = Vec::with_capacity(list.len());
    for jo in list {
        let wid = wid_from_str(&jo.weapon_id);
        if wid == WId::None { continue; }
        let mut patch = PartialWeaponDef::default();
        let mut fields: Vec<&'static str> = Vec::new();
        if let Some(s) = &jo.weapon_type { patch.weapon_type = Some(WeaponType::from_str(s)); fields.push("weapon_type"); }
        if let Some(v) = jo.damage { patch.damage = Some(v); fields.push("damage"); }
        if let Some(v) = jo.damage_outer { patch.damage_outer = Some(v); fields.push("damage_outer"); }
        if let Some(s) = &jo.push { patch.push = Some(PushDir::from_str(s)); fields.push("push"); }
        if let Some(v) = jo.self_damage { patch.self_damage = Some(v); fields.push("self_damage"); }
        if let Some(v) = jo.range_min { patch.range_min = Some(v); fields.push("range_min"); }
        if let Some(v) = jo.range_max { patch.range_max = Some(v); fields.push("range_max"); }
        if let Some(v) = jo.limited { patch.limited = Some(v); fields.push("limited"); }
        if let Some(v) = jo.path_size { patch.path_size = Some(v); fields.push("path_size"); }
        if let Some(names) = &jo.flags_set {
            let mut any = false;
            for n in names {
                if let Some(bit) = flag_from_name(n) { patch.flags_set |= bit; any = true; }
            }
            if any { fields.push("flags_set"); }
        }
        if let Some(names) = &jo.flags_clear {
            let mut any = false;
            for n in names {
                if let Some(bit) = flag_from_name(n) { patch.flags_clear |= bit; any = true; }
            }
            if any { fields.push("flags_clear"); }
        }
        if patch.is_empty() { continue; }
        out.push(OverlayEntry { wid, patch, source, fields });
    }
    out
}

#[derive(Deserialize)]
pub struct JsonTile {
    pub x: u8,
    pub y: u8,
    pub terrain_id: Option<u8>,
    pub terrain: Option<String>,
    pub fire: Option<bool>,
    pub smoke: Option<bool>,
    pub acid: Option<bool>,
    pub shield: Option<bool>,
    pub frozen: Option<bool>,
    pub cracked: Option<bool>,
    pub pod: Option<bool>,
    pub has_pod: Option<bool>,
    pub item: Option<String>,
    pub freeze_mine: Option<bool>,
    pub old_earth_mine: Option<bool>,
    pub repair_platform: Option<bool>,
    pub grass: Option<bool>,
    pub custom: Option<String>,
    pub building_hp: Option<u8>,
    pub population: Option<u8>,
    pub conveyor: Option<i8>,
    pub unique_building: Option<bool>,
    // Bridge's specific objective tag. "Str_Power" / "Str_Battery" /
    // "Mission_Solar" → ⚡ grid-reward. "Str_Clinic" / "Str_Nimbus" /
    // "Str_Tower" → ⭐ rep-only. Empty / unknown → rep-only fallback.
    pub objective_name: Option<String>,
}

#[derive(Deserialize)]
pub struct JsonWebProbes {
    #[serde(rename = "IsGrappled")]
    pub is_grappled: Option<bool>,
}

#[derive(Deserialize)]
pub struct JsonUnit {
    pub uid: Option<u16>,
    #[serde(rename = "type")]
    pub unit_type: String,
    pub x: u8,
    pub y: u8,
    pub hp: Option<i8>,
    pub max_hp: Option<i8>,
    pub team: Option<u8>,
    pub mech: Option<bool>,
    #[serde(rename = "move")]
    pub move_speed: Option<u8>,
    pub flying: Option<bool>,
    pub armor: Option<bool>,
    pub massive: Option<bool>,
    pub minor: Option<bool>,
    pub pushable: Option<bool>,
    pub active: Option<bool>,
    pub shield: Option<bool>,
    pub acid: Option<bool>,
    pub frozen: Option<bool>,
    pub fire: Option<bool>,
    pub infected: Option<bool>,
    pub web: Option<bool>,
    pub web_probes: Option<JsonWebProbes>,
    pub boosted: Option<bool>,
    pub web_source_uid: Option<u16>,
    pub has_queued_attack: Option<bool>,
    pub base_move: Option<u8>,
    pub weapons: Option<Vec<String>>,
    pub queued_target: Option<Vec<i8>>,
    pub queued_target_raw: Option<Vec<i8>>,
    pub queued_origin: Option<Vec<i8>>,
    pub queued_target_normalized: Option<bool>,
    pub weapon_damage: Option<u16>,
    pub weapon_target_behind: Option<bool>,
    pub weapon_push: Option<u8>,
    pub ranged: Option<u8>,
    pub can_move: Option<bool>,
    pub is_extra_tile: Option<bool>,
    pub pilot_value: Option<f64>,
    /// Lua bridge `pilot.id` (e.g. "Pilot_Soldier"). Maps to `PilotFlags`
    /// via `pilot_flags_from_id` for the combat-affecting passives the
    /// solver actually models (Camila / Ariadne / Harold today).
    pub pilot_id: Option<String>,
}

/// Map a Lua pilot_id string to the bitflags the solver uses at call sites.
/// Unknown or empty pilot_ids return an empty set (no simulator effect);
/// the mech still gets its `pilot_value` penalty via the Python-side
/// `_PILOT_VALUE_TABLE` lookup regardless.
fn pilot_flags_from_id(pilot_id: &str) -> crate::board::PilotFlags {
    use crate::board::PilotFlags;
    match pilot_id {
        "Pilot_Soldier"   => PilotFlags::SOLDIER,    // Camila Vera — Evasion
        "Pilot_Rock"      => PilotFlags::ROCK,       // Ariadne — Rockman
        "Pilot_Repairman" => PilotFlags::REPAIRMAN,  // Harold Schmidt — Frenzied Repair
        "Pilot_Chemical"  => PilotFlags::CHEMICAL,   // Morgan Lejeune — Finisher
        "Pilot_Arrogant"  => PilotFlags::ARROGANT,   // Kai Miller — Opener
        _ => PilotFlags::empty(),
    }
}

fn known_minor_type(type_name: &str) -> bool {
    matches!(
        type_name,
        "Blob1"
            | "Blob2"
            | "BlobB"
            | "BlobMini"
            | "MantisEgg"
            | "WebbEgg1"
            | "Spiderling1"
            | "Spiderling2"
            | "Totem1"
            | "Totem2"
            | "TotemB"
            | "SlugEgg1"
            | "Shield_Building"
            | "Hacked_Building"
            | "Storm_Generator"
            | "AcidVat"
            | "BombRock"
            | "BonusDebris"
    )
}

fn is_totem_attack(wid: WeaponId) -> bool {
    wid == WeaponId(WId::TotemAtk1 as u16)
        || wid == WeaponId(WId::TotemAtk2 as u16)
        || wid == WeaponId(WId::TotemAtkB as u16)
}

fn fixed_projectile_end(board: &Board, ox: u8, oy: u8, qtx: i8, qty: i8) -> Option<(u8, u8)> {
    if qtx < 0 || qty < 0 {
        return None;
    }
    let dx = (qtx - ox as i8).signum();
    let dy = (qty - oy as i8).signum();
    if (dx != 0 && dy != 0) || (dx == 0 && dy == 0) {
        return None;
    }

    let mut last_valid = None;
    for step in 1..8i8 {
        let nx = ox as i8 + dx * step;
        let ny = oy as i8 + dy * step;
        if !in_bounds(nx, ny) {
            break;
        }
        let nxu = nx as u8;
        let nyu = ny as u8;
        let tile = board.tile(nxu, nyu);
        if tile.terrain == Terrain::Mountain {
            return Some((nxu, nyu));
        }
        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
            return Some((nxu, nyu));
        }
        if board.unit_at(nxu, nyu).is_some() {
            return Some((nxu, nyu));
        }
        last_valid = Some((nxu, nyu));
    }
    last_valid
}

fn rewrite_totem_fixed_projectile_targets(board: &mut Board) {
    for idx in 0..board.unit_count as usize {
        let unit = board.units[idx];
        if !is_totem_attack(unit.weapon) || unit.queued_target_x < 0 || unit.queued_target_y < 0 {
            continue;
        }
        let (ox, oy) = if unit.queued_origin_x >= 0 && unit.queued_origin_y >= 0 {
            (unit.queued_origin_x as u8, unit.queued_origin_y as u8)
        } else {
            (unit.x, unit.y)
        };
        if let Some((tx, ty)) = fixed_projectile_end(
            board,
            ox,
            oy,
            unit.queued_target_x,
            unit.queued_target_y,
        ) {
            board.units[idx].queued_target_x = tx as i8;
            board.units[idx].queued_target_y = ty as i8;
        }
    }
}

fn engine_dir_to_solver_dir(dir: i8) -> Option<i8> {
    match dir {
        // Engine DIR_UP / DIR_DOWN are vertically opposite the solver's
        // bridge-coordinate direction order. Mission_Wind live capture
        // 20260521_120049_468 m08 t01 and Mission_BeltRandom live capture
        // 20260521_232056_112 m00 t01 both show raw dir=2 pushes through
        // solver dir 0.
        0 => Some(2),
        1 => Some(1),
        2 => Some(0),
        3 => Some(3),
        _ => None,
    }
}

// ── Deserialize Board from JSON ──────────────────────────────────────────────

pub fn board_from_json(json_str: &str)
    -> Result<(Board, Vec<(u8, u8)>, Vec<(u8, u8)>, EvalWeights, DisabledMask, Vec<OverlayEntry>), String>
{
    let input: JsonInput = serde_json::from_str(json_str)
        .map_err(|e| format!("JSON parse error: {}", e))?;
    let weights = input.eval_weights.clone().unwrap_or_default();

    // Weapon-def overlay: base (committed) applied first, runtime (ephemeral)
    // applied last so runtime wins precedence ties inside the same field.
    let mut overlay_entries: Vec<OverlayEntry> = Vec::new();
    if let Some(list) = &input.weapon_overrides {
        overlay_entries.extend(parse_overlay_list(list, OverlaySource::Base));
    }
    if let Some(list) = &input.weapon_overrides_runtime {
        overlay_entries.extend(parse_overlay_list(list, OverlaySource::Runtime));
    }

    let mut board = Board::default();
    if let Some(order) = &input.attack_order {
        board.attack_order = order.clone();
    }

    // Grid power
    board.grid_power = input.grid_power.unwrap_or(7);
    board.grid_power_max = input.grid_power_max.unwrap_or(7);

    // Tiles
    if let Some(tiles) = &input.tiles {
        for jt in tiles {
            if jt.x >= 8 || jt.y >= 8 { continue; }
            let tile = board.tile_mut(jt.x, jt.y);
            tile.terrain = Terrain::from_bridge_id(jt.terrain_id, jt.terrain.as_deref());
            // Mountains default to 2 HP if not specified (bridge doesn't send mountain HP)
            let default_hp = if tile.terrain == Terrain::Mountain { 2 } else { 0 };
            tile.building_hp = jt.building_hp.unwrap_or(default_hp);
            tile.population = jt.population.unwrap_or(0);

            let mut flags = TileFlags::empty();
            if jt.fire.unwrap_or(false) { flags |= TileFlags::ON_FIRE; }
            if jt.smoke.unwrap_or(false) { flags |= TileFlags::SMOKE; }
            if jt.acid.unwrap_or(false) { flags |= TileFlags::ACID; }
            if jt.shield.unwrap_or(false) { flags |= TileFlags::SHIELD; }
            if jt.frozen.unwrap_or(false) { flags |= TileFlags::FROZEN; }
            if jt.cracked.unwrap_or(false) { flags |= TileFlags::CRACKED; }
            if jt.pod.unwrap_or(false) || jt.has_pod.unwrap_or(false) { flags |= TileFlags::HAS_POD; }
            if jt.freeze_mine.unwrap_or(false) { flags |= TileFlags::FREEZE_MINE; }
            if jt.old_earth_mine.unwrap_or(false) { flags |= TileFlags::OLD_EARTH_MINE; }
            if jt.repair_platform.unwrap_or(false)
                || jt.item.as_deref() == Some("Item_Repair_Mine")
            {
                flags |= TileFlags::REPAIR_PLATFORM;
            }
            if jt.grass.unwrap_or(false)
                || jt.custom.as_deref() == Some("ground_grass.png")
            {
                flags |= TileFlags::GRASS;
            }
            tile.flags = flags;
            tile.conveyor_dir = jt
                .conveyor
                .and_then(engine_dir_to_solver_dir)
                .unwrap_or(-1);

            // Objective buildings (Coal Plant, Power Generator, Batteries,
            // Clinic, Nimbus, Tower, Solar Farms). `unique_buildings` is the
            // full set; `grid_reward_buildings` is the ⚡ subset whose
            // survival restores +1 Grid Power at mission end. See
            // evaluate.rs for why the two are scored differently.
            // Mission_Trapped ("Protect the Coal Plant") exposes its 2-HP
            // Coal Plant structures as plain building tiles in the bridge.
            // Live engine still treats each HP lost as grid-power loss, so
            // infer objective-style grid accounting for those tiles.
            let inferred_unique = input.mission_id.as_deref() == Some("Mission_Trapped")
                && tile.terrain == Terrain::Building
                && tile.building_hp > 1;
            if jt.unique_building.unwrap_or(false) || inferred_unique {
                let idx = (jt.x as usize) * 8 + (jt.y as usize);
                board.unique_buildings |= 1u64 << idx;
                let grid_reward_name = jt.objective_name.as_deref()
                    .map(|name| matches!(name, "Str_Power" | "Str_Battery" | "Mission_Solar"))
                    .unwrap_or(false);
                if inferred_unique || grid_reward_name {
                    board.grid_reward_buildings |= 1u64 << idx;
                }
            }
        }
    }

    // Environment danger (legacy v1: bitset of dangerous tiles)
    let mut env_danger = 0u64;
    let mut danger_tiles = Vec::new();
    if let Some(danger) = &input.environment_danger {
        for d in danger {
            if d.len() >= 2 && d[0] < 8 && d[1] < 8 {
                env_danger |= 1u64 << xy_to_idx(d[0], d[1]);
                danger_tiles.push((d[0], d[1]));
            }
        }
    }

    // Environment danger v2: per-tile {damage, kill, flying_immune} metadata.
    // Each entry is [x, y, damage, kill_int, flying_immune?] where:
    //   kill_int != 0      → Deadly Threat (bypasses shield/frozen/armor/ACID)
    //   flying_immune != 0 → terrain-conversion lethal (Tidal Wave/Cataclysm/
    //                        Seismic): effectively-flying units survive.
    //                        Air Strike / Lightning / Satellite Rocket /
    //                        Final Cave falling rocks leave this field 0 —
    //                        they bypass flight.
    // The 5th field is an optional addition introduced at SIMULATOR_VERSION 19
    // (Lua bridge 2026-04-25). Older recordings only have 4 fields; we infer
    // flying_immune from the top-level `env_type` tag when present, else
    // leave it 0 (preserves pre-fix "kill everything" behavior).
    // v2 entries implicitly populate the v1 bitset too.
    // If v2 is missing entirely (older bridge), conservatively treat ALL
    // existing env_danger tiles as lethal — over-pessimistic on tidal waves
    // but never under-predicts air strike deaths.
    let mut env_danger_kill = 0u64;
    let mut env_danger_flying_immune = 0u64;
    // Final Cave's marked tiles are Env_Final falling-rock/tentacle death
    // effects, not ordinary chasm conversion. Treat stale bridge payloads that
    // say flying_immune=1 as lethal to flyers anyway.
    let mission_id = input.mission_id.as_deref();
    let final_cave_env = mission_id == Some("Mission_Final_Cave");
    let deadly_threat_env = matches!(mission_id,
        Some("Mission_Airstrike")
        | Some("Mission_Lightning")
        | Some("Mission_LightningStorm")
    );
    let terrain_conversion_env = matches!(mission_id,
        Some("Mission_Tides")
        | Some("Mission_Cataclysm")
        | Some("Mission_Crack")
    );
    // Back-compat fallback: when the 5th element is missing, look at the
    // top-level env_type to decide whether the lethal hazard is terrain-
    // conversion (flying_immune=true) or Deadly Threat (false).
    let env_type_flying_immune: Option<bool> = input.env_type.as_deref().map(|t| {
        !final_cave_env && !deadly_threat_env && (terrain_conversion_env || matches!(t,
            "tidal_or_cataclysm"
            | "cataclysm_or_seismic"
            | "tidal"
            | "cataclysm"
            | "seismic"
        ))
    });
    if let Some(v2) = &input.environment_danger_v2 {
        for entry in v2 {
            if entry.len() >= 4 && entry[0] < 8 && entry[1] < 8 {
                let bit = 1u64 << xy_to_idx(entry[0], entry[1]);
                env_danger |= bit;  // v2 entry is also a v1 danger tile
                if entry[3] != 0 {
                    env_danger_kill |= bit;
                    let flying_immune = if final_cave_env || deadly_threat_env {
                        false
                    } else if terrain_conversion_env {
                        true
                    } else if entry.len() >= 5 {
                        entry[4] != 0
                    } else {
                        // 4-field legacy entry — fall back to env_type
                        env_type_flying_immune.unwrap_or(false)
                    };
                    if flying_immune {
                        env_danger_flying_immune |= bit;
                    }
                }
            }
        }
    } else if env_danger != 0 {
        // Backwards compat: no v2 → assume all dangers are lethal. Use
        // env_type if available to populate flying_immune; otherwise the
        // pre-fix conservative default (no flying immunity) holds.
        env_danger_kill = env_danger;
        if env_type_flying_immune.unwrap_or(false) {
            env_danger_flying_immune = env_danger;
        }
    }
    // Mission_Terratide reuses Env_Tides' warning machinery, so its smoke
    // wave arrives in the same `environment_danger(_v2)` fields as lethal
    // water. The live Env_Terratide effect is `SpaceDamage.iSmoke = 1`, not
    // HP damage or terrain death. Mission id is authoritative because the
    // bridge may classify the inherited class as `tidal_or_cataclysm`.
    // Do not route generic Env_Sandstorm here: that separate mission also
    // removes old smoke and converts ROAD/WATER/SAND terrain.
    let env_smoke = if mission_id == Some("Mission_Terratide") {
        env_danger
    } else {
        0
    };
    let env_wind = if env_smoke == 0 && input.env_type.as_deref() == Some("wind") {
        env_danger
    } else {
        0
    };
    let non_damage_env = env_smoke | env_wind;
    if non_damage_env != 0 {
        env_danger &= !non_damage_env;
        env_danger_kill &= !non_damage_env;
        env_danger_flying_immune &= !non_damage_env;
    }
    board.env_danger = env_danger;
    board.env_danger_kill = env_danger_kill;
    board.env_danger_flying_immune = env_danger_flying_immune;
    board.env_smoke = env_smoke;
    board.env_wind = env_wind;
    board.env_wind_dir = if env_wind != 0 {
        input.environment_wind_dir
            .and_then(engine_dir_to_solver_dir)
            .unwrap_or(-1)
    } else {
        -1
    };

    // Ice Storm freeze tiles. Separate channel from env_danger — these tiles
    // apply Frozen=true to units at start of enemy turn, no HP damage.
    let mut env_freeze = 0u64;
    if let Some(freeze) = &input.environment_freeze {
        for f in freeze {
            if f.len() >= 2 && f[0] < 8 && f[1] < 8 {
                env_freeze |= 1u64 << xy_to_idx(f[0], f[1]);
            }
        }
    }
    board.env_freeze = env_freeze;

    // Mission_FreezeBldg frozen-building objective tiles.
    if let Some(target) = input.freeze_building_target {
        board.freeze_building_target = target;
    }
    if let Some(tiles) = &input.freeze_building_tiles {
        for entry in tiles {
            if entry.len() >= 2 && entry[0] < 8 && entry[1] < 8 {
                board.freeze_building_tiles |= 1u64 << xy_to_idx(entry[0], entry[1]);
            }
        }
    }

    // Teleporter pad pairs (Mission_Teleporter overlay from Board:AddTeleport).
    // Legacy recordings may lack mission_id, so preserve pairs when the
    // mission is unknown. Live non-teleporter missions must not inherit stale
    // pad pairs from a previous Mission_Teleporter capture.
    let allow_teleporter_pairs = input
        .mission_id
        .as_deref()
        .map_or(true, |id| id == "Mission_Teleporter");
    if allow_teleporter_pairs {
        if let Some(pairs) = &input.teleporter_pairs {
            for p in pairs {
                if p.len() >= 4 && p[0] < 8 && p[1] < 8 && p[2] < 8 && p[3] < 8 {
                    board.teleporter_pairs.push((p[0], p[1], p[2], p[3]));
                }
            }
        }
    }

    // Mission-aware bonus-objective protected types ("do not kill X").
    // Empty list → no protection this mission, evaluator's volatile-kill
    // penalty no-ops. See Board::bonus_dont_kill_types and JsonInput field.
    if let Some(types) = &input.bonus_objective_unit_types {
        board.bonus_dont_kill_types = types.iter().cloned().collect();
    }
    if let Some(types) = &input.destroy_objective_unit_types {
        board.destroy_objective_unit_types = types.iter().cloned().collect();
    }
    if let Some(types) = &input.protect_objective_unit_types {
        board.protect_objective_unit_types = types.iter().cloned().collect();
    }

    // Spawn points
    let mut spawn_points = Vec::new();
    if let Some(spawns) = &input.spawning_tiles {
        for s in spawns {
            if s.len() >= 2 && s[0] < 8 && s[1] < 8 {
                spawn_points.push((s[0], s[1]));
            }
        }
    }

    // Units
    if let Some(units) = &input.units {
        for ju in units {
            if board.unit_count >= 16 { break; }

            let is_mech = ju.mech.unwrap_or(false);
            let team = Team::from_int(ju.team.unwrap_or(if is_mech { 1 } else { 6 }));
            let hp = ju.hp.unwrap_or(1);

            let mut flags = UnitFlags::empty();
            if is_mech { flags |= UnitFlags::IS_MECH; }
            if ju.flying.unwrap_or(false) { flags |= UnitFlags::FLYING; }
            if ju.massive.unwrap_or(false) { flags |= UnitFlags::MASSIVE; }
            if ju.minor.unwrap_or_else(|| known_minor_type(&ju.unit_type)) { flags |= UnitFlags::MINOR; }
            if ju.armor.unwrap_or(false) { flags |= UnitFlags::ARMOR; }
            if ju.pushable.unwrap_or(true) { flags |= UnitFlags::PUSHABLE; }
            if ju.ranged.unwrap_or(0) > 0 { flags |= UnitFlags::RANGED; }
            if ju.active.unwrap_or(true) { flags |= UnitFlags::ACTIVE; }
            if ju.can_move.unwrap_or(true) { flags |= UnitFlags::CAN_MOVE; }
            if ju.is_extra_tile.unwrap_or(false) { flags |= UnitFlags::EXTRA_TILE; }
            if ju.shield.unwrap_or(false) { flags |= UnitFlags::SHIELD; }
            if ju.acid.unwrap_or(false) { flags |= UnitFlags::ACID; }
            if ju.frozen.unwrap_or(false) { flags |= UnitFlags::FROZEN; }
            if ju.fire.unwrap_or(false) { flags |= UnitFlags::FIRE; }
            if ju.infected.unwrap_or(false) { flags |= UnitFlags::INFECTED; }
            let probe_web = ju.web_probes
                .as_ref()
                .and_then(|p| p.is_grappled)
                .unwrap_or(false);
            if ju.web.unwrap_or(false) || probe_web { flags |= UnitFlags::WEB; }
            if ju.boosted.unwrap_or(false) { flags |= UnitFlags::BOOSTED; }
            if ju.has_queued_attack.unwrap_or(false) { flags |= UnitFlags::HAS_QUEUED_ATTACK; }
            if ju.unit_type == "Disposal_Unit" {
                flags.remove(UnitFlags::PUSHABLE);
                flags |= UnitFlags::RANGED;
            }

            // Weapons
            let mut weapon = crate::board::WeaponId::NONE;
            let mut weapon2 = crate::board::WeaponId::NONE;
            if let Some(weapons) = &ju.weapons {
                if !weapons.is_empty() {
                    weapon = crate::board::WeaponId(wid_from_str(&weapons[0]) as u16);
                }
                if weapons.len() > 1 {
                    weapon2 = crate::board::WeaponId(wid_from_str(&weapons[1]) as u16);
                }
            }
            if ju.unit_type == "Disposal_Unit" && weapon.0 == 0 {
                weapon = crate::board::WeaponId(WId::DisposalAttack as u16);
            }

            // Queued target
            let (qtx, qty) = if let Some(qt) = &ju.queued_target {
                if qt.len() >= 2 { (qt[0], qt[1]) } else { (-1, -1) }
            } else {
                (-1, -1)
            };
            let (raw_qtx, raw_qty) = if let Some(qt) = &ju.queued_target_raw {
                if qt.len() >= 2 { (qt[0], qt[1]) } else { (-1, -1) }
            } else {
                (-1, -1)
            };
            let (qox, qoy) = if let Some(qo) = &ju.queued_origin {
                if qo.len() >= 2 { (qo[0], qo[1]) } else { (-1, -1) }
            } else if qtx >= 0 && qty >= 0 {
                (ju.x as i8, ju.y as i8)
            } else {
                (-1, -1)
            };
            if qtx >= 0 && qty >= 0 {
                flags |= UnitFlags::QUEUED_ORIGIN_SET;
            }
            if raw_qtx >= 0 && raw_qty >= 0 {
                flags |= UnitFlags::QUEUED_RAW_TARGET_SET;
            }
            if qtx < 0 && ju.queued_target_normalized.unwrap_or(false) {
                flags.remove(UnitFlags::HAS_QUEUED_ATTACK);
            }

            let move_speed = ju.move_speed.or(ju.base_move).unwrap_or(3);
            let mut unit = Unit {
                uid: ju.uid.unwrap_or(board.unit_count as u16),
                pawn_type: PawnType(0),
                type_name: [0u8; 20],
                x: ju.x,
                y: ju.y,
                hp,
                max_hp: ju.max_hp.unwrap_or(hp),
                team,
                move_speed,
                base_move: ju.base_move.unwrap_or(move_speed),
                flags,
                weapon,
                weapon2,
                queued_target_x: qtx,
                queued_target_y: qty,
                queued_target_raw_x: raw_qtx,
                queued_target_raw_y: raw_qty,
                queued_origin_x: if qtx >= 0 && qty >= 0 { qox } else { -1 },
                queued_origin_y: if qtx >= 0 && qty >= 0 { qoy } else { -1 },
                weapon_damage: ju.weapon_damage.unwrap_or(0).min(u8::MAX as u16) as u8,
                weapon_push: ju.weapon_push.unwrap_or(0),
                weapon_target_behind: ju.weapon_target_behind.unwrap_or(false),
                web_source_uid: ju.web_source_uid.unwrap_or(0),
                pilot_value: ju.pilot_value.unwrap_or(0.0) as f32,
                pilot_flags: if is_mech {
                    pilot_flags_from_id(ju.pilot_id.as_deref().unwrap_or(""))
                } else {
                    crate::board::PilotFlags::empty()
                },
            };

            unit.set_type_name(&ju.unit_type);
            board.add_unit(unit);
        }
    }

    rewrite_totem_fixed_projectile_targets(&mut board);

    // Fill missing/stale web ownership from alive queued web attacks. Older
    // bridge fallback code cleared Mosquito Leader grapples because
    // `MosquitoAtkB` was absent from its source table, and GetGrappledSource()
    // can also preserve a stale source after enemies retarget. Prefer the
    // queued web attack that currently targets the webbed unit's tile.
    for idx in 0..board.unit_count as usize {
        if !board.units[idx].web() {
            continue;
        }
        let (ux, uy) = (board.units[idx].x, board.units[idx].y);
        let current_uid = board.units[idx].web_source_uid;
        let mut source_uid = 0;
        for src_idx in 0..board.unit_count as usize {
            let src = board.units[src_idx];
            if src.team != Team::Enemy || src.hp <= 0 {
                continue;
            }
            if src.queued_target_x != ux as i8 || src.queued_target_y != uy as i8 {
                continue;
            }
            if WEAPONS[src.weapon.0 as usize].web() {
                if src.uid == current_uid {
                    source_uid = current_uid;
                    break;
                }
                if source_uid != 0 {
                    continue;
                }
                source_uid = src.uid;
            }
        }
        if source_uid != 0 && source_uid != current_uid {
            board.units[idx].web_source_uid = source_uid;
        }
    }

    // Apply tile-borne A.C.I.D. to grounded units standing on ACID pools.
    // The bridge reports tile.acid correctly but sometimes does NOT propagate
    // it to grounded unit.acid — surfaced on Disposal Site boards where Scarab2
    // on D4 (ACID pool) should take 4-dmg Chain Whip hits but the sim predicted
    // 2-dmg survival. Flying units can hover over acid pools without carrying
    // A.C.I.D.; trusting the bridge status for them avoids phantom damage.
    // Applied after unit population so late-join mechs (tanks) pick it up too.
    for i in 0..board.unit_count as usize {
        let (ux, uy) = (board.units[i].x, board.units[i].y);
        if ux < 8
            && uy < 8
            && board.tile(ux, uy).acid()
            && !board.units[i].acid()
            && !board.units[i].effectively_flying()
        {
            board.units[i].set_acid(true);
        }
    }

    // Bridge `IsGrappled()` can miss or misattribute Spider Egg webs.
    // Mirror Python's `_infer_webb_egg_adjacency` so direct Rust solves and
    // replay/score_plan calls receive the same authoritative egg source.
    board.refresh_webb_egg_grapples();

    // Turn info
    board.current_turn = input.turn.unwrap_or(0);
    board.total_turns = input.total_turns.unwrap_or(5);
    board.remaining_spawns = input.remaining_spawns.unwrap_or(u32::MAX);
    board.infinite_spawn = input.is_infinite_spawn.unwrap_or(false);
    board.mission_id = input.mission_id.clone().unwrap_or_default();
    board.mission_kill_target = input.mission_kill_target.unwrap_or(0);
    board.mission_kill_limit = input.mission_kill_limit.unwrap_or(0);
    board.mission_kills_done = input.mission_kills_done.unwrap_or(0);
    board.mission_mountain_target = input.mission_mountain_target.unwrap_or(0);
    board.mission_mountains_destroyed = input.mission_mountains_destroyed.unwrap_or(0);
    if let Some(tiles) = &input.mission_mountain_tiles {
        for entry in tiles {
            if entry.len() >= 2 && entry[0] < 8 && entry[1] < 8 {
                board.mission_mountain_tiles |= 1u64 << xy_to_idx(entry[0], entry[1]);
            }
        }
    }
    board.repair_platform_target = input.repair_platform_target.unwrap_or(0);
    board.repair_platforms_used = input.repair_platforms_used.unwrap_or(0);

    // Detect Old Earth Dam: populate dam_alive + dam_primary from the primary
    // tile entry (the one without EXTRA_TILE). Used by trigger_dam_flood at
    // damage time. Must run AFTER unit population above so board.units is full.
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.type_name_str() == "Dam_Pawn" && u.hp > 0 && !u.is_extra_tile() {
            board.dam_alive = true;
            board.dam_primary = Some((u.x, u.y));
            break;
        }
    }

    // Detect Renfield Bomb (Mission_Final_Cave win-condition NPC). Single
    // BigBomb pawn at (live HP > 0). Per mission_final_two.lua:179-188:
    // Health=4, Neutral=true, Corpse=false, IgnoreFire=true, MoveSpeed=0,
    // DefaultTeam=TEAM_PLAYER. Bridge surfaces it with team=Player, mech=false,
    // so the friendly_npc_killed penalty already fires on death. The
    // bigbomb_alive flag layers a much larger explicit kill penalty in the
    // evaluator since losing the bomb fails the entire run.
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.type_name_str() == "BigBomb" && u.hp > 0 {
            board.bigbomb_alive = true;
            break;
        }
    }

    // Detect Blast Psion: if Jelly_Explode1 is alive, all non-minor Vek explode on death
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Explode1" && board.units[i].hp > 0 {
            board.blast_psion = true;
            break;
        }
    }

    // Detect Shell Psion: if Jelly_Armor1 is alive, all non-minor Vek gain Armor
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Armor1" && board.units[i].hp > 0 {
            board.armor_psion = true;
            break;
        }
    }
    if board.armor_psion {
        // Hardened Carapace: "ALL OTHER Vek have incoming weapon damage
        // reduced by 1." Explicitly excludes the Psion itself — Titan Fist
        // deals full damage to Jelly_Armor1.
        for i in 0..board.unit_count as usize {
            if board.units[i].receives_psion_aura() && board.units[i].type_name_str() != "Jelly_Armor1" {
                board.units[i].flags.set(UnitFlags::ARMOR, true);
            }
        }
    }

    // Detect Soldier Psion (Jelly_Health1): all non-minor Vek +1 HP
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Health1" && board.units[i].hp > 0 {
            board.soldier_psion = true;
            break;
        }
    }

    // Detect Psion Abomination (Jelly_Boss): combined HEALTH + REGEN + EXPLODE
    // aura. We set the flag here BEFORE the +1 HP application so the soldier
    // branch can gate against double-stacking.
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Boss" && board.units[i].hp > 0 {
            board.boss_psion = true;
            break;
        }
    }

    // Apply the HEALTH part of the aura: +1 max_hp to all OTHER non-minor Vek when
    // either Soldier Psion or Boss Psion is alive. Both auras grant the same
    // +1 HP buff, so when both are present the buff applies ONCE — not twice.
    // The Lua source treats LEADER_HEALTH as a binary tag (Pawn:HasLeader):
    // a Vek either has the buff or not. Mirror that here. Also exclude the
    // boss itself from the buff (its base HP is already 5).
    if board.soldier_psion || board.boss_psion {
        for i in 0..board.unit_count as usize {
            let tname = board.units[i].type_name_str();
            if board.units[i].receives_psion_aura()
                && tname != "Jelly_Health1"
                && tname != "Jelly_Boss"
            {
                board.units[i].max_hp += 1;
            }
        }
    }

    // Detect Blood Psion (Jelly_Regen1): all Vek regen 1 HP/turn
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Regen1" && board.units[i].hp > 0 {
            board.regen_psion = true;
            break;
        }
    }

    // Detect Psion Tyrant (Jelly_Lava1): 1 dmg to all player units/turn
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Lava1" && board.units[i].hp > 0 {
            board.tyrant_psion = true;
            break;
        }
    }

    // Detect Boost Psion (Jelly_Boost1, AE): +1 damage to all Vek weapon attacks
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Boost1" && board.units[i].hp > 0 {
            board.boost_psion = true;
            break;
        }
    }

    // Detect Fire Psion (Jelly_Fire1, AE): Vek fire-immune + leave fire on death
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Fire1" && board.units[i].hp > 0 {
            board.fire_psion = true;
            break;
        }
    }

    // Detect Spider Psion (Jelly_Spider1, AE): Vek leave SpiderEgg on death
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Spider1" && board.units[i].hp > 0 {
            board.spider_psion = true;
            break;
        }
    }

    // Detect any Boss-type enemy (mission objective: destroy the boss)
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.is_enemy() && u.hp > 0 && u.type_name_str().contains("Boss") {
            board.boss_alive = true;
            break;
        }
    }

    // Detect passive abilities from mech weapon names
    if let Some(units) = &input.units {
        for ju in units {
            if ju.mech.unwrap_or(false) {
                if let Some(weapons) = &ju.weapons {
                    for wname in weapons {
                        match wname.as_str() {
                            "Passive_Electric" => board.storm_generator = true,
                            "Passive_FlameImmune" => board.flame_shielding = true,
                            "Passive_FireBoost" => board.heat_engines = true,
                            "Passive_HealingSmoke" => board.healing_smoke = true,
                            "Passive_Leech" => {
                                board.viscera_nanobots_heal = board.viscera_nanobots_heal.max(1);
                            }
                            "Passive_Leech_A" => {
                                board.viscera_nanobots_heal = board.viscera_nanobots_heal.max(2);
                            }
                            "Passive_FriendlyFire" => board.vek_hormones = true,
                            "Passive_ForceAmp" => board.force_amp = true,
                            "Passive_Medical" => board.medical_supplies = true,
                            _ => {}
                        }
                    }
                }
            }
        }
    }

    // Build the soft-disable bitmask: 1 bit per WId variant.
    // Python-side ``session.disabled_actions`` is the source of truth —
    // we only consume the ``weapon_id`` string here. Unknown strings
    // resolve to ``WId::None`` via ``wid_from_str`` and are silently
    // ignored (a typo in a weapon id can't brick the solve).
    let mut disabled_mask: DisabledMask = [0; 2];
    if let Some(list) = &input.disabled_actions {
        for entry in list {
            let wid = wid_from_str(&entry.weapon_id);
            let bit = wid as usize;
            if wid != WId::None && bit < disabled_mask.len() * 128 {
                disabled_mask[bit / 128] |= 1u128 << (bit % 128);
            }
        }
    }

    Ok((board, spawn_points, danger_tiles, weights, disabled_mask, overlay_entries))
}

// ── Serialize Solution to JSON ───────────────────────────────────────────────

#[derive(Serialize)]
struct JsonOutput {
    actions: Vec<JsonAction>,
    score: f64,
    stats: JsonStats,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    applied_overrides: Vec<JsonAppliedOverride>,
}

#[derive(Serialize)]
struct JsonAppliedOverride {
    weapon_id: String,
    fields: Vec<&'static str>,
    source: &'static str,
}

#[derive(Serialize)]
struct JsonAction {
    mech_uid: u16,
    mech_type: String,
    move_to: [u8; 2],
    weapon: String,
    weapon_id: String,
    target: [u8; 2],
    #[serde(skip_serializing_if = "Option::is_none")]
    target2: Option<[u8; 2]>,
    description: String,
}

#[derive(Serialize)]
struct JsonStats {
    elapsed: f64,
    timed_out: bool,
    permutations_tried: usize,
    total_permutations: usize,
}

pub fn solution_to_json(solution: &Solution, applied_overrides: &[OverlayEntry]) -> String {
    let actions: Vec<JsonAction> = solution.actions.iter().map(|a| {
        JsonAction {
            mech_uid: a.mech_uid,
            mech_type: a.mech_type.clone(),
            move_to: [a.move_to.0, a.move_to.1],
            weapon: weapon_name(a.weapon).to_string(),
            weapon_id: wid_to_str(a.weapon).to_string(),
            target: [a.target.0, a.target.1],
            target2: a.target2.map(|(x, y)| [x, y]),
            description: a.description.clone(),
        }
    }).collect();

    let applied_overrides: Vec<JsonAppliedOverride> = applied_overrides.iter().map(|e| {
        JsonAppliedOverride {
            weapon_id: wid_to_str(e.wid).to_string(),
            fields: e.fields.clone(),
            source: e.source.as_str(),
        }
    }).collect();

    let output = JsonOutput {
        actions,
        score: solution.score,
        stats: JsonStats {
            elapsed: solution.elapsed_secs,
            timed_out: solution.timed_out,
            permutations_tried: solution.permutations_tried,
            total_permutations: solution.total_permutations,
        },
        applied_overrides,
    };

    serde_json::to_string(&output).unwrap_or_else(|_| "{}".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::Terrain;

    #[test]
    fn test_bridge_terrain_id_5_overrides_stale_lava_name_to_ice() {
        let input = r#"{
            "tiles": [
                {"x": 5, "y": 5, "terrain": "lava", "terrain_id": 5}
            ],
            "units": [],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert_eq!(board.tile(5, 5).terrain, Terrain::Ice);
    }

    #[test]
    fn test_terratide_danger_routes_to_smoke_not_damage() {
        let input = r#"{
            "mission_id": "Mission_Terratide",
            "env_type": "tidal_or_cataclysm",
            "tiles": [],
            "units": [],
            "grid_power": 7,
            "spawning_tiles": [],
            "environment_danger_v2": [[5, 3, 1, 1, 1]]
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert!(board.is_env_smoke(5, 3));
        assert_eq!(board.env_danger, 0);
        assert_eq!(board.env_danger_kill, 0);
        assert_eq!(board.env_danger_flying_immune, 0);
    }

    #[test]
    fn test_bridge_grass_custom_sets_tile_flag() {
        let input = r#"{
            "mission_id": "Mission_Terraform",
            "tiles": [
                {"x": 3, "y": 3, "terrain": "ground", "grass": true},
                {"x": 4, "y": 4, "terrain": "water", "custom": "ground_grass.png"}
            ],
            "units": [],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert!(board.tile(3, 3).grass());
        assert!(board.tile(4, 4).grass());
    }

    #[test]
    fn test_disabled_nano_mech_still_enables_viscera_nanobots() {
        let input = r#"{
            "tiles": [],
            "units": [
                {
                    "uid": 2,
                    "type": "NanoMech",
                    "x": 1,
                    "y": 5,
                    "hp": 0,
                    "max_hp": 2,
                    "team": 1,
                    "mech": true,
                    "active": false,
                    "weapons": ["Science_AcidShot", "Passive_Leech_A"]
                }
            ],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert_eq!(board.viscera_nanobots_heal, 2);
    }

    #[test]
    fn test_smog_mech_enables_healing_smoke() {
        let input = r#"{
            "tiles": [],
            "units": [
                {
                    "uid": 1,
                    "type": "SmokeMech",
                    "x": 2,
                    "y": 2,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 1,
                    "mech": true,
                    "active": true,
                    "weapons": ["Ranged_SmokeFire", "Passive_HealingSmoke"]
                }
            ],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert!(board.healing_smoke);
    }

    #[test]
    fn test_conveyor_engine_dirs_normalized_to_solver_dirs() {
        let input = r#"{
            "mission_id": "Mission_BeltRandom",
            "tiles": [
                {"x": 1, "y": 1, "terrain": "ground", "conveyor": 0},
                {"x": 2, "y": 2, "terrain": "ground", "conveyor": 1},
                {"x": 3, "y": 3, "terrain": "ground", "conveyor": 2},
                {"x": 4, "y": 4, "terrain": "ground", "conveyor": 3}
            ],
            "units": [],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert_eq!(board.tile(1, 1).conveyor_dir, 2);
        assert_eq!(board.tile(2, 2).conveyor_dir, 1);
        assert_eq!(board.tile(3, 3).conveyor_dir, 0);
        assert_eq!(board.tile(4, 4).conveyor_dir, 3);
    }

    #[test]
    fn test_known_minor_types_inferred_for_old_recordings() {
        let input = r#"{
            "tiles": [],
            "units": [
                {"uid": 1, "type": "Totem2", "x": 4, "y": 1, "hp": 1, "max_hp": 1, "team": 6},
                {"uid": 2, "type": "Leaper1", "x": 4, "y": 2, "hp": 1, "max_hp": 1, "team": 6}
            ],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert!(board.units[0].minor(), "Totem2 old recordings should infer Minor=true");
        assert!(!board.units[1].minor(), "ordinary Leaper1 is not a Minor Vek");
    }

    #[test]
    fn test_totem_queued_target_rewritten_to_fixed_projectile_endpoint() {
        let input = r#"{
            "tiles": [
                {"x": 2, "y": 1, "terrain": "building", "building_hp": 1}
            ],
            "units": [
                {
                    "uid": 711,
                    "type": "Totem1",
                    "x": 4,
                    "y": 1,
                    "hp": 1,
                    "max_hp": 1,
                    "team": 6,
                    "ranged": 1,
                    "weapons": ["TotemAtk1"],
                    "has_queued_attack": true,
                    "queued_origin": [4, 1],
                    "queued_target": [3, 1],
                    "weapon_damage": 1
                }
            ],
            "grid_power": 2,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert_eq!(board.units[0].weapon, WeaponId(WId::TotemAtk1 as u16));
        assert_eq!((board.units[0].queued_origin_x, board.units[0].queued_origin_y), (4, 1));
        assert_eq!((board.units[0].queued_target_x, board.units[0].queued_target_y), (2, 1));
    }

    #[test]
    fn test_live_pushable_false_overrides_static_default() {
        let input = r#"{
            "tiles": [],
            "units": [
                {"uid": 1143, "type": "FireflyBoss", "x": 2, "y": 6, "hp": 1, "max_hp": 6, "team": 6, "massive": true, "pushable": false}
            ],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert!(
            !board.units[0].pushable(),
            "live bridge pushable=false should make a Stable FireflyBoss immune to Taurus push"
        );
    }

    #[test]
    fn test_mission_trapped_two_hp_buildings_use_unique_grid_accounting() {
        let input = r#"{
            "mission_id": "Mission_Trapped",
            "tiles": [
                {"x": 4, "y": 4, "terrain": "building", "terrain_id": 1, "building_hp": 2},
                {"x": 1, "y": 1, "terrain": "building", "terrain_id": 1, "building_hp": 1}
            ],
            "units": [],
            "grid_power": 6,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");
        let coal_idx = (4usize * 8) + 4;
        let normal_idx = (1usize * 8) + 1;

        assert_ne!(board.unique_buildings & (1u64 << coal_idx), 0,
            "Mission_Trapped 2-HP Coal Plant tiles need per-HP grid accounting");
        assert_eq!(board.unique_buildings & (1u64 << normal_idx), 0,
            "Regular 1-HP buildings on the same map should not be inferred unique");
    }

    #[test]
    fn test_unit_move_speed_falls_back_to_base_move() {
        let input = r#"{
            "tiles": [],
            "units": [
                {
                    "uid": 1,
                    "type": "JetMech",
                    "x": 2,
                    "y": 4,
                    "hp": 2,
                    "max_hp": 2,
                    "team": 1,
                    "mech": true,
                    "active": true,
                    "base_move": 4,
                    "weapons": ["Brute_Jetmech"]
                },
                {
                    "uid": 2,
                    "type": "PulseMech",
                    "x": 3,
                    "y": 2,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 1,
                    "mech": true,
                    "active": true,
                    "move": 0,
                    "base_move": 4,
                    "weapons": ["Science_Repulse"]
                }
            ],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert_eq!(board.units[0].move_speed, 4);
        assert_eq!(board.units[0].base_move, 4);
        assert_eq!(board.units[1].move_speed, 0);
        assert_eq!(board.units[1].base_move, 4);
    }

    #[test]
    fn test_bridge_load_infers_webb_egg_adjacency_source_when_stale() {
        let input = r#"{
            "tiles": [],
            "units": [
                {
                    "uid": 2,
                    "type": "PulseMech",
                    "x": 5,
                    "y": 3,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 1,
                    "mech": true,
                    "web": true,
                    "web_source_uid": 626,
                    "weapons": ["Science_Repulse"]
                },
                {
                    "uid": 674,
                    "type": "WebbEgg1",
                    "x": 5,
                    "y": 2,
                    "hp": 1,
                    "max_hp": 1,
                    "team": 6
                }
            ],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert!(board.units[0].web());
        assert_eq!(
            board.units[0].web_source_uid, 674,
            "adjacent WebbEgg1 should override stale/misattributed bridge web source"
        );
    }

    #[test]
    fn test_bridge_load_preserves_active_non_egg_web_source() {
        let input = r#"{
            "tiles": [],
            "units": [
                {
                    "uid": 2,
                    "type": "PulseMech",
                    "x": 5,
                    "y": 3,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 1,
                    "mech": true,
                    "web": true,
                    "web_source_uid": 626,
                    "weapons": ["Science_Repulse"]
                },
                {
                    "uid": 626,
                    "type": "Scorpion1",
                    "x": 6,
                    "y": 3,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 6,
                    "has_queued_attack": true,
                    "queued_target": [5, 3]
                },
                {
                    "uid": 674,
                    "type": "WebbEgg1",
                    "x": 5,
                    "y": 2,
                    "hp": 1,
                    "max_hp": 1,
                    "team": 6
                }
            ],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert!(board.units[0].web());
        assert_eq!(
            board.units[0].web_source_uid, 626,
            "active Scorpion grapple targeting the mech should keep ownership"
        );
    }

    #[test]
    fn test_bridge_load_replaces_stale_non_egg_web_source() {
        let input = r#"{
            "tiles": [],
            "units": [
                {
                    "uid": 2,
                    "type": "PulseMech",
                    "x": 5,
                    "y": 5,
                    "hp": 4,
                    "max_hp": 5,
                    "team": 1,
                    "mech": true,
                    "web": true,
                    "web_source_uid": 776,
                    "weapons": ["Science_Repulse_A"]
                },
                {
                    "uid": 776,
                    "type": "Scorpion1",
                    "x": 5,
                    "y": 6,
                    "hp": 2,
                    "max_hp": 3,
                    "team": 6,
                    "weapons": ["ScorpionAtk1"],
                    "has_queued_attack": true,
                    "queued_target": [4, 6]
                },
                {
                    "uid": 799,
                    "type": "Scorpion1",
                    "x": 5,
                    "y": 4,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 6,
                    "weapons": ["ScorpionAtk1"],
                    "has_queued_attack": true,
                    "queued_target": [5, 5]
                }
            ],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert!(board.units[0].web());
        assert_eq!(
            board.units[0].web_source_uid, 799,
            "alive queued web source targeting the mech should replace stale bridge ownership"
        );
    }

    #[test]
    fn test_bridge_load_recovers_grapple_probe_web_source() {
        let input = r#"{
            "tiles": [],
            "units": [
                {
                    "uid": 2,
                    "type": "RockartMech",
                    "x": 3,
                    "y": 6,
                    "hp": 2,
                    "max_hp": 2,
                    "team": 1,
                    "mech": true,
                    "web": false,
                    "web_probes": {"IsGrappled": true},
                    "weapons": ["Ranged_Rockthrow"]
                },
                {
                    "uid": 2791,
                    "type": "MosquitoBoss",
                    "x": 4,
                    "y": 6,
                    "hp": 5,
                    "max_hp": 5,
                    "team": 6,
                    "weapons": ["MosquitoAtkB"],
                    "has_queued_attack": true,
                    "queued_target": [3, 6]
                }
            ],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert!(board.units[0].web());
        assert_eq!(
            board.units[0].web_source_uid, 2791,
            "queued Mosquito Leader grapple should own the recovered web"
        );
    }

    #[test]
    fn test_normalized_offboard_queued_target_clears_attack() {
        let input = r#"{
            "tiles": [],
            "units": [
                {
                    "uid": 4766,
                    "type": "Moth1",
                    "x": 1,
                    "y": 2,
                    "hp": 3,
                    "max_hp": 3,
                    "team": 6,
                    "weapons": ["MothAtk1"],
                    "has_queued_attack": true,
                    "queued_origin": [5, 5],
                    "queued_target": null,
                    "queued_target_normalized": true
                }
            ],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert!(
            !board.units[0].has_queued_attack(),
            "a normalized off-board queued shot is canceled, not unknown"
        );
        assert_eq!(board.units[0].queued_target_x, -1);
        assert_eq!(board.units[0].queued_origin_x, -1);
    }

    #[test]
    fn test_disabled_mask_covers_high_weapon_ids() {
        let input = r#"{
            "tiles": [],
            "units": [],
            "grid_power": 7,
            "spawning_tiles": [],
            "disabled_actions": [
                {"weapon_id": "Missiles_OneDmg"}
            ]
        }"#;

        let (_board, _spawns, _danger, _weights, disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");
        let bit = WId::MissilesOneDmg as usize;

        assert_ne!(
            disabled[bit / 128] & (1u128 << (bit % 128)),
            0,
            "WId 135 must be represented in the high disabled-mask word"
        );
    }

    #[test]
    fn test_non_teleporter_mission_ignores_stale_pad_pairs() {
        let input = r#"{
            "mission_id": "Mission_AcidTank",
            "tiles": [],
            "units": [],
            "grid_power": 7,
            "spawning_tiles": [],
            "teleporter_pairs": [[2, 3, 2, 5]]
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert!(
            board.teleporter_pairs.is_empty(),
            "stale Mission_Teleporter pad pairs must not affect other missions"
        );
    }

    #[test]
    fn test_teleporter_mission_keeps_pad_pairs() {
        let input = r#"{
            "mission_id": "Mission_Teleporter",
            "tiles": [],
            "units": [],
            "grid_power": 7,
            "spawning_tiles": [],
            "teleporter_pairs": [[2, 3, 2, 5]]
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        assert_eq!(board.teleporter_pairs, vec![(2, 3, 2, 5)]);
    }

    #[test]
    fn test_acid_pool_import_respects_flying_units() {
        let input = r#"{
            "mission_id": "Mission_Acid",
            "tiles": [
                {"x": 1, "y": 3, "terrain": "ground", "acid": true},
                {"x": 2, "y": 2, "terrain": "ground", "acid": true}
            ],
            "units": [
                {
                    "uid": 660,
                    "type": "Hornet1",
                    "x": 1,
                    "y": 3,
                    "hp": 2,
                    "max_hp": 2,
                    "team": 6,
                    "flying": true,
                    "acid": false
                },
                {
                    "uid": 661,
                    "type": "Scarab1",
                    "x": 2,
                    "y": 2,
                    "hp": 2,
                    "max_hp": 2,
                    "team": 6,
                    "acid": false
                }
            ],
            "grid_power": 7,
            "spawning_tiles": []
        }"#;

        let (board, _spawns, _danger, _weights, _disabled, _overrides) =
            board_from_json(input).expect("bridge json parses");

        let hornet = board.units.iter().find(|u| u.uid == 660).expect("hornet");
        let scarab = board.units.iter().find(|u| u.uid == 661).expect("scarab");

        assert!(!hornet.acid(), "flying unit hovering over acid pool stays clean");
        assert!(scarab.acid(), "grounded unit on acid pool inherits A.C.I.D.");
    }
}
