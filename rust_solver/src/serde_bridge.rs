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
    pub eval_weights: Option<EvalWeights>,
    pub mission_id: Option<String>,
    /// "Kill N enemies" bonus target (mission:GetKillBonus(), difficulty-scaled).
    /// Missing / 0 → no bonus on this mission; evaluator's step-function
    /// scoring is a no-op in that case.
    pub mission_kill_target: Option<u8>,
    /// Cumulative this-mission kills (mission.KilledVek). Combined with the
    /// simulated turn's kills to decide whether a plan crosses the target.
    pub mission_kills_done: Option<u8>,
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
    /// `Board::teleporter_pairs`. Missing / empty on non-teleporter
    /// missions.
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
    pub terrain: Option<String>,
    pub fire: Option<bool>,
    pub smoke: Option<bool>,
    pub acid: Option<bool>,
    pub frozen: Option<bool>,
    pub cracked: Option<bool>,
    pub pod: Option<bool>,
    pub has_pod: Option<bool>,
    pub freeze_mine: Option<bool>,
    pub old_earth_mine: Option<bool>,
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
    pub pushable: Option<bool>,
    pub active: Option<bool>,
    pub shield: Option<bool>,
    pub acid: Option<bool>,
    pub frozen: Option<bool>,
    pub fire: Option<bool>,
    pub web: Option<bool>,
    pub web_source_uid: Option<u16>,
    pub has_queued_attack: Option<bool>,
    pub base_move: Option<u8>,
    pub weapons: Option<Vec<String>>,
    pub queued_target: Option<Vec<i8>>,
    pub weapon_damage: Option<u8>,
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
        _ => PilotFlags::empty(),
    }
}

// ── Deserialize Board from JSON ──────────────────────────────────────────────

pub fn board_from_json(json_str: &str)
    -> Result<(Board, Vec<(u8, u8)>, Vec<(u8, u8)>, EvalWeights, u128, Vec<OverlayEntry>), String>
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

    // Grid power
    board.grid_power = input.grid_power.unwrap_or(7);
    board.grid_power_max = input.grid_power_max.unwrap_or(7);

    // Tiles
    if let Some(tiles) = &input.tiles {
        for jt in tiles {
            if jt.x >= 8 || jt.y >= 8 { continue; }
            let tile = board.tile_mut(jt.x, jt.y);
            tile.terrain = Terrain::from_str(jt.terrain.as_deref().unwrap_or("ground"));
            // Mountains default to 2 HP if not specified (bridge doesn't send mountain HP)
            let default_hp = if tile.terrain == Terrain::Mountain { 2 } else { 0 };
            tile.building_hp = jt.building_hp.unwrap_or(default_hp);
            tile.population = jt.population.unwrap_or(0);

            let mut flags = TileFlags::empty();
            if jt.fire.unwrap_or(false) { flags |= TileFlags::ON_FIRE; }
            if jt.smoke.unwrap_or(false) { flags |= TileFlags::SMOKE; }
            if jt.acid.unwrap_or(false) { flags |= TileFlags::ACID; }
            if jt.frozen.unwrap_or(false) { flags |= TileFlags::FROZEN; }
            if jt.cracked.unwrap_or(false) { flags |= TileFlags::CRACKED; }
            if jt.pod.unwrap_or(false) || jt.has_pod.unwrap_or(false) { flags |= TileFlags::HAS_POD; }
            if jt.freeze_mine.unwrap_or(false) { flags |= TileFlags::FREEZE_MINE; }
            if jt.old_earth_mine.unwrap_or(false) { flags |= TileFlags::OLD_EARTH_MINE; }
            tile.flags = flags;
            tile.conveyor_dir = jt.conveyor.unwrap_or(-1);

            // Objective buildings (Coal Plant, Power Generator, Batteries,
            // Clinic, Nimbus, Tower, Solar Farms). `unique_buildings` is the
            // full set; `grid_reward_buildings` is the ⚡ subset whose
            // survival restores +1 Grid Power at mission end. See
            // evaluate.rs for why the two are scored differently.
            if jt.unique_building.unwrap_or(false) {
                let idx = (jt.x as usize) * 8 + (jt.y as usize);
                board.unique_buildings |= 1u64 << idx;
                if let Some(name) = jt.objective_name.as_deref() {
                    if matches!(name, "Str_Power" | "Str_Battery" | "Mission_Solar") {
                        board.grid_reward_buildings |= 1u64 << idx;
                    }
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
    //                        Air Strike / Lightning / Satellite Rocket leave
    //                        this field 0 — they bypass flight.
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
    // Back-compat fallback: when the 5th element is missing, look at the
    // top-level env_type to decide whether the lethal hazard is terrain-
    // conversion (flying_immune=true) or Deadly Threat (false).
    let env_type_flying_immune: Option<bool> = input.env_type.as_deref().map(|t| {
        matches!(t,
            "tidal_or_cataclysm"
            | "cataclysm_or_seismic"
            | "tidal"
            | "cataclysm"
            | "seismic"
        )
    });
    if let Some(v2) = &input.environment_danger_v2 {
        for entry in v2 {
            if entry.len() >= 4 && entry[0] < 8 && entry[1] < 8 {
                let bit = 1u64 << xy_to_idx(entry[0], entry[1]);
                env_danger |= bit;  // v2 entry is also a v1 danger tile
                if entry[3] != 0 {
                    env_danger_kill |= bit;
                    let flying_immune = if entry.len() >= 5 {
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
    board.env_danger = env_danger;
    board.env_danger_kill = env_danger_kill;
    board.env_danger_flying_immune = env_danger_flying_immune;

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

    // Teleporter pad pairs (Mission_Teleporter overlay from Board:AddTeleport)
    if let Some(pairs) = &input.teleporter_pairs {
        for p in pairs {
            if p.len() >= 4 && p[0] < 8 && p[1] < 8 && p[2] < 8 && p[3] < 8 {
                board.teleporter_pairs.push((p[0], p[1], p[2], p[3]));
            }
        }
    }

    // Mission-aware bonus-objective protected types ("do not kill X").
    // Empty list → no protection this mission, evaluator's volatile-kill
    // penalty no-ops. See Board::bonus_dont_kill_types and JsonInput field.
    if let Some(types) = &input.bonus_objective_unit_types {
        board.bonus_dont_kill_types = types.iter().cloned().collect();
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
            if ju.web.unwrap_or(false) { flags |= UnitFlags::WEB; }
            if ju.has_queued_attack.unwrap_or(false) { flags |= UnitFlags::HAS_QUEUED_ATTACK; }

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

            // Queued target
            let (qtx, qty) = if let Some(qt) = &ju.queued_target {
                if qt.len() >= 2 { (qt[0], qt[1]) } else { (-1, -1) }
            } else {
                (-1, -1)
            };

            let move_speed = ju.move_speed.unwrap_or(3);
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
                weapon_damage: ju.weapon_damage.unwrap_or(0),
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

    // Apply tile-borne A.C.I.D. to units standing on ACID pools.
    // Game rule: a unit on an A.C.I.D. tile carries the A.C.I.D. status,
    // doubling weapon damage taken. The bridge reports tile.acid correctly
    // but often does NOT propagate that to unit.acid — surfaced on
    // Disposal Site boards where Scarab2 on D4 (ACID pool) should take
    // 4-dmg Chain Whip hits but the sim predicted 2-dmg survival. Applied
    // after unit population so late-join mechs (tanks) pick it up too.
    for i in 0..board.unit_count as usize {
        let (ux, uy) = (board.units[i].x, board.units[i].y);
        if ux < 8 && uy < 8 && board.tile(ux, uy).acid() && !board.units[i].acid() {
            board.units[i].set_acid(true);
        }
    }

    // Turn info
    board.current_turn = input.turn.unwrap_or(0);
    board.total_turns = input.total_turns.unwrap_or(5);
    board.remaining_spawns = input.remaining_spawns.unwrap_or(u32::MAX);
    board.infinite_spawn = input.is_infinite_spawn.unwrap_or(false);
    board.mission_id = input.mission_id.clone().unwrap_or_default();
    board.mission_kill_target = input.mission_kill_target.unwrap_or(0);
    board.mission_kills_done = input.mission_kills_done.unwrap_or(0);

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

    // Detect Blast Psion: if Jelly_Explode1 is alive, all Vek explode on death
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Explode1" && board.units[i].hp > 0 {
            board.blast_psion = true;
            break;
        }
    }

    // Detect Shell Psion: if Jelly_Armor1 is alive, all Vek gain Armor
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
            if board.units[i].is_enemy() && board.units[i].type_name_str() != "Jelly_Armor1" {
                board.units[i].flags.set(UnitFlags::ARMOR, true);
            }
        }
    }

    // Detect Soldier Psion (Jelly_Health1): all Vek +1 HP
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Health1" && board.units[i].hp > 0 {
            board.soldier_psion = true;
            break;
        }
    }
    if board.soldier_psion {
        // Bridge sends HP already buffed but max_hp as base — adjust max_hp to match
        for i in 0..board.unit_count as usize {
            if board.units[i].is_enemy() && board.units[i].type_name_str() != "Jelly_Health1" {
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

    // Build the soft-disable bitmask: 1 bit per WId variant up to 127.
    // Python-side ``session.disabled_actions`` is the source of truth —
    // we only consume the ``weapon_id`` string here. Unknown strings
    // resolve to ``WId::None`` via ``wid_from_str`` and are silently
    // ignored (a typo in a weapon id can't brick the solve).
    let mut disabled_mask: u128 = 0;
    if let Some(list) = &input.disabled_actions {
        for entry in list {
            let wid = wid_from_str(&entry.weapon_id);
            if wid != WId::None {
                disabled_mask |= 1u128 << (wid as u8);
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
