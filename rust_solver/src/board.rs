/// Board, Tile, and Unit data structures.
///
/// Designed for fast Clone (memcpy of ~800 bytes). No heap allocation.
/// All boolean flags packed into bitflags for cache efficiency.

use bitflags::bitflags;
use crate::types::*;
use std::collections::{BTreeMap, BTreeSet};

// ── Tile Flags ───────────────────────────────────────────────────────────────

bitflags! {
    #[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
    pub struct TileFlags: u16 {
        const ON_FIRE         = 0b0000_0000_0001;
        const SMOKE           = 0b0000_0000_0010;
        const ACID            = 0b0000_0000_0100;
        const FROZEN          = 0b0000_0000_1000;
        const CRACKED         = 0b0000_0001_0000;
        const HAS_POD         = 0b0000_0010_0000;
        const FREEZE_MINE     = 0b0000_0100_0000;
        const OLD_EARTH_MINE  = 0b0000_1000_0000;
        const REPAIR_PLATFORM = 0b0001_0000_0000;
        const SHIELD          = 0b0010_0000_0000;
        const GRASS           = 0b0100_0000_0000;
    }
}

// ── Tile ─────────────────────────────────────────────────────────────────────

#[derive(Clone, Copy, Debug)]
pub struct Tile {
    pub terrain: Terrain,
    pub building_hp: u8,
    pub population: u8,
    pub flags: TileFlags,
    pub conveyor_dir: i8, // -1 = none, 0-3 = direction (matches DIRS)
}

impl Default for Tile {
    fn default() -> Self {
        Tile {
            terrain: Terrain::Ground,
            building_hp: 0,
            population: 0,
            flags: TileFlags::empty(),
            conveyor_dir: -1,
        }
    }
}

impl Tile {
    pub fn on_fire(&self) -> bool { self.flags.contains(TileFlags::ON_FIRE) }
    pub fn smoke(&self) -> bool { self.flags.contains(TileFlags::SMOKE) }
    pub fn acid(&self) -> bool { self.flags.contains(TileFlags::ACID) }
    pub fn frozen(&self) -> bool { self.flags.contains(TileFlags::FROZEN) }
    pub fn cracked(&self) -> bool { self.flags.contains(TileFlags::CRACKED) }
    pub fn has_pod(&self) -> bool { self.flags.contains(TileFlags::HAS_POD) }
    pub fn freeze_mine(&self) -> bool { self.flags.contains(TileFlags::FREEZE_MINE) }
    pub fn old_earth_mine(&self) -> bool { self.flags.contains(TileFlags::OLD_EARTH_MINE) }
    pub fn repair_platform(&self) -> bool { self.flags.contains(TileFlags::REPAIR_PLATFORM) }
    pub fn shield(&self) -> bool { self.flags.contains(TileFlags::SHIELD) }
    pub fn grass(&self) -> bool { self.flags.contains(TileFlags::GRASS) }

    pub fn set_on_fire(&mut self, v: bool) { self.flags.set(TileFlags::ON_FIRE, v); }
    pub fn set_smoke(&mut self, v: bool) { self.flags.set(TileFlags::SMOKE, v); }
    pub fn set_acid(&mut self, v: bool) { self.flags.set(TileFlags::ACID, v); }
    pub fn set_frozen(&mut self, v: bool) { self.flags.set(TileFlags::FROZEN, v); }
    pub fn set_cracked(&mut self, v: bool) { self.flags.set(TileFlags::CRACKED, v); }
    pub fn set_has_pod(&mut self, v: bool) { self.flags.set(TileFlags::HAS_POD, v); }
    pub fn set_freeze_mine(&mut self, v: bool) { self.flags.set(TileFlags::FREEZE_MINE, v); }
    pub fn set_old_earth_mine(&mut self, v: bool) { self.flags.set(TileFlags::OLD_EARTH_MINE, v); }
    pub fn set_repair_platform(&mut self, v: bool) { self.flags.set(TileFlags::REPAIR_PLATFORM, v); }
    pub fn set_shield(&mut self, v: bool) { self.flags.set(TileFlags::SHIELD, v); }
    pub fn set_grass(&mut self, v: bool) { self.flags.set(TileFlags::GRASS, v); }

    pub fn is_building(&self) -> bool {
        self.terrain == Terrain::Building && self.building_hp > 0
    }
}

// ── Unit Flags ───────────────────────────────────────────────────────────────

// ── Pilot Flags ──────────────────────────────────────────────────────────────
//
// Persistent combat-affecting pilot passives. Each bit maps to one pilot_id
// the Lua bridge reports for mechs (enemies/neutrals have no bits set). Set
// in `serde_bridge::board_from_json` via `pilot_flags_from_id`.
//
// Passives that are already reflected in bridge state (Bethany's starting
// shield via `shield=true`, Abe's Armored via `armor=true`, Lily's +3 move
// via the bridge's `move` field, Ariadne's +3 HP via `max_hp`) do NOT need
// a bit here — only passives that change simulator predictions on a given
// board do.
bitflags! {
    #[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
    pub struct PilotFlags: u8 {
        /// Camila Vera (Pilot_Soldier) — Evasion: web + smoke immune.
        /// Web branch: `apply_weapon_status` skips `set_web` on this unit.
        /// Smoke branch: no-op today (the simulator does not currently
        /// cancel mech attacks when the mech stands on a smoke tile), but
        /// the flag is wired so any future fix to that base mechanic will
        /// automatically honor Camila.
        const SOLDIER   = 0b0000_0001;
        /// Ariadne (Pilot_Rock) — Rockman: fire immune. The +3 HP half of
        /// the passive is already folded into `max_hp` by the Python bridge's
        /// `_compute_pilot_value` HP-boost heuristic, so only fire needs
        /// a simulator hook.
        const ROCK      = 0b0000_0010;
        /// Harold Schmidt (Pilot_Repairman) — Frenzied Repair: the mech's
        /// Repair action also pushes all four adjacent tiles outward.
        const REPAIRMAN = 0b0000_0100;
        /// Morgan Lejeune (Pilot_Chemical) — Finisher: killing an enemy boosts
        /// this mech for its next action.
        const CHEMICAL  = 0b0000_1000;
        /// Kai Miller (Pilot_Arrogant) — Opener: this mech is Boosted while
        /// at full HP, and loses 1 Move while damaged.
        const ARROGANT  = 0b0001_0000;
    }
}

bitflags! {
    #[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
    pub struct UnitFlags: u32 {
        const IS_MECH  = 0b0000_0000_0001;
        const FLYING   = 0b0000_0000_0010;
        const MASSIVE  = 0b0000_0000_0100;
        const ARMOR    = 0b0000_0000_1000;
        const PUSHABLE = 0b0000_0001_0000;
        const ACTIVE   = 0b0000_0010_0000;
        const SHIELD   = 0b0000_0100_0000;
        const ACID     = 0b0000_1000_0000;
        const FROZEN   = 0b0001_0000_0000;
        const FIRE     = 0b0010_0000_0000;
        const WEB      = 0b0100_0000_0000;
        const RANGED   = 0b1000_0000_0000;
        /// False for MID_ACTION mechs that moved but haven't attacked yet.
        /// Solver skips move enumeration when this is unset.
        const CAN_MOVE = 0b0001_0000_0000_0000;
        /// Duplicate unit-entry emitted for a pawn's ExtraSpaces tile
        /// (Dam_Pawn occupies H3+H4 as one Lua Pawn). Damage is mirrored
        /// across all entries sharing the same uid.
        const EXTRA_TILE = 0b0010_0000_0000_0000;
        /// Vek has a queued attack this turn (Lua bridge set
        /// has_queued_attack=true). When this is set but queued_target_x
        /// is -1, the simulator applies conservative phantom damage
        /// instead of silently skipping the attack.
        const HAS_QUEUED_ATTACK = 0b0100_0000_0000_0000;
        /// Minor Vek spawned by other Vek. Minor units are enemies for threat
        /// and collision purposes, but the engine does not apply Psion aura
        /// bonuses to them.
        const MINOR = 0b1000_0000_0000_0000;
        /// Boosted status: the unit's next ability gets +1 weapon damage, and
        /// Repair heals +1 extra HP. Consumed on attack or repair.
        const BOOSTED = 0b0001_0000_0000_0000_0000;
        /// Vek Mites attached to a mech. Mission objective state from
        /// `bInfected`; cleared by repair/status/damage effects.
        const INFECTED = 0b0010_0000_0000_0000_0000;
        /// Enemy queued-target origin is explicitly recorded. This lets
        /// player-phase retarget effects preserve the original attack vector
        /// after the attacker has been pushed.
        const QUEUED_ORIGIN_SET = 0b0100_0000_0000_0000_0000;
        /// Bridge provided the raw, pre-normalization queued target. Used as
        /// a direction fallback when normalized targets collapse to origin.
        const QUEUED_RAW_TARGET_SET = 0b1000_0000_0000_0000_0000;
    }
}

// ── WeaponId placeholder ─────────────────────────────────────────────────────
// Full enum defined in weapons.rs; re-exported. Using u16 for now.

/// Compact weapon identifier. 0 = no weapon.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub struct WeaponId(pub u16);

impl WeaponId {
    pub const NONE: WeaponId = WeaponId(0);
    pub const REPAIR: WeaponId = WeaponId(0xFFFF);

    pub fn is_none(self) -> bool { self.0 == 0 }
}

// ── PawnType placeholder ─────────────────────────────────────────────────────

/// Compact pawn type identifier.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub struct PawnType(pub u16);

// ── Unit ─────────────────────────────────────────────────────────────────────

#[derive(Clone, Copy, Debug, Default)]
pub struct Unit {
    pub uid: u16,
    pub pawn_type: PawnType,
    /// Pawn type name bytes (null-terminated, max 20 chars). Avoids heap allocation.
    pub type_name: [u8; 20],
    pub x: u8,
    pub y: u8,
    pub hp: i8,
    pub max_hp: i8,
    pub team: Team,
    pub move_speed: u8,
    /// Base movement speed; used to restore move_speed when web breaks
    /// (push/kill of webber). Defaults to move_speed when bridge omits it.
    pub base_move: u8,
    pub flags: UnitFlags,
    pub weapon: WeaponId,
    pub weapon2: WeaponId,
    // Enemy intent
    pub queued_target_x: i8, // -1 = no target
    pub queued_target_y: i8,
    pub queued_target_raw_x: i8,
    pub queued_target_raw_y: i8,
    pub queued_origin_x: i8,
    pub queued_origin_y: i8,
    pub weapon_damage: u8,
    pub weapon_push: u8,
    pub weapon_target_behind: bool,
    /// UID of the enemy currently webbing this unit (0 = none/unknown).
    /// When that enemy is pushed or killed, the web breaks and move_speed
    /// is restored to base_move.
    pub web_source_uid: u16,
    /// Pilot value: multiplier on mech_killed penalty reflecting the
    /// permanent cost of losing this mech's pilot (skills + XP). Mechs
    /// only; enemies and neutrals stay at 0. Computed by Python's
    /// `_compute_pilot_value` from pilot_id + current max_hp.
    pub pilot_value: f32,
    /// Combat-affecting pilot passives (see `PilotFlags` above). Empty
    /// for enemies, neutrals, and mechs with no recognized pilot.
    pub pilot_flags: PilotFlags,
}

impl Unit {
    // Flag accessors
    pub fn is_mech(&self) -> bool { self.flags.contains(UnitFlags::IS_MECH) }
    pub fn flying(&self) -> bool { self.flags.contains(UnitFlags::FLYING) }
    pub fn massive(&self) -> bool { self.flags.contains(UnitFlags::MASSIVE) }
    pub fn armor(&self) -> bool { self.flags.contains(UnitFlags::ARMOR) }
    pub fn pushable(&self) -> bool { self.flags.contains(UnitFlags::PUSHABLE) }
    pub fn active(&self) -> bool { self.flags.contains(UnitFlags::ACTIVE) }
    pub fn shield(&self) -> bool { self.flags.contains(UnitFlags::SHIELD) }
    pub fn acid(&self) -> bool { self.flags.contains(UnitFlags::ACID) }
    pub fn frozen(&self) -> bool { self.flags.contains(UnitFlags::FROZEN) }
    pub fn fire(&self) -> bool { self.flags.contains(UnitFlags::FIRE) }
    pub fn web(&self) -> bool { self.flags.contains(UnitFlags::WEB) }
    pub fn ranged(&self) -> bool { self.flags.contains(UnitFlags::RANGED) }
    pub fn can_move(&self) -> bool { self.flags.contains(UnitFlags::CAN_MOVE) }
    pub fn is_extra_tile(&self) -> bool { self.flags.contains(UnitFlags::EXTRA_TILE) }
    pub fn has_queued_attack(&self) -> bool { self.flags.contains(UnitFlags::HAS_QUEUED_ATTACK) }
    pub fn minor(&self) -> bool { self.flags.contains(UnitFlags::MINOR) }
    pub fn boosted(&self) -> bool { self.flags.contains(UnitFlags::BOOSTED) }
    pub fn infected(&self) -> bool { self.flags.contains(UnitFlags::INFECTED) }

    pub fn set_active(&mut self, v: bool) { self.flags.set(UnitFlags::ACTIVE, v); }
    pub fn set_shield(&mut self, v: bool) { self.flags.set(UnitFlags::SHIELD, v); }
    pub fn set_frozen(&mut self, v: bool) { self.flags.set(UnitFlags::FROZEN, v); }
    pub fn set_fire(&mut self, v: bool) { self.flags.set(UnitFlags::FIRE, v); }
    pub fn set_acid(&mut self, v: bool) { self.flags.set(UnitFlags::ACID, v); }
    pub fn set_web(&mut self, v: bool) { self.flags.set(UnitFlags::WEB, v); }
    pub fn set_boosted(&mut self, v: bool) { self.flags.set(UnitFlags::BOOSTED, v); }
    pub fn set_infected(&mut self, v: bool) { self.flags.set(UnitFlags::INFECTED, v); }

    pub fn is_player(&self) -> bool { self.team == Team::Player }
    pub fn is_enemy(&self) -> bool { self.team == Team::Enemy }
    pub fn is_player_action_unit(&self) -> bool {
        self.is_player() && self.alive() && self.active() && !self.is_extra_tile()
            && (
                self.is_mech()
                || !self.weapon.is_none()
                || !self.weapon2.is_none()
                || (self.move_speed > 0 && self.type_name_str() == "VIP_Truck")
            )
    }
    pub fn is_pinnacle_bot(&self) -> bool {
        let name = self.type_name_str();
        name.starts_with("Snowtank")
            || name.starts_with("Snowart")
            || name.starts_with("Snowlaser")
            || name.starts_with("Snowmine")
            || name == "BotBoss"
            || name == "BotBoss2"
    }
    pub fn receives_psion_aura(&self) -> bool {
        self.is_enemy() && !self.minor() && !self.is_pinnacle_bot()
    }
    pub fn alive(&self) -> bool { self.hp > 0 }

    // Pilot-passive accessors. Enemies and neutrals never have these bits,
    // so there's no team check needed at call sites — a raw pilot_flags
    // read is 0 for any non-piloted unit.
    pub fn pilot_soldier(&self) -> bool { self.pilot_flags.contains(PilotFlags::SOLDIER) }
    pub fn pilot_rock(&self) -> bool { self.pilot_flags.contains(PilotFlags::ROCK) }
    pub fn pilot_repairman(&self) -> bool { self.pilot_flags.contains(PilotFlags::REPAIRMAN) }
    pub fn pilot_chemical(&self) -> bool { self.pilot_flags.contains(PilotFlags::CHEMICAL) }
    pub fn pilot_arrogant(&self) -> bool { self.pilot_flags.contains(PilotFlags::ARROGANT) }

    /// Can this unit catch fire? False for Ariadne (Pilot_Rock). Squad-wide
    /// Flame Shielding is handled at call sites because it needs board state,
    /// and it applies only to player mechs, not controllable mission allies.
    pub fn can_catch_fire(&self) -> bool { !self.pilot_rock() }

    /// Get pawn type name as string (from stored bytes).
    pub fn type_name_str(&self) -> &str {
        let len = self.type_name.iter().position(|&b| b == 0).unwrap_or(self.type_name.len());
        std::str::from_utf8(&self.type_name[..len]).unwrap_or("Unknown")
    }

    /// Is this unit an intrinsic Explosive Decay unit? Matches the canonical
    /// `Volatile_Vek` marker (test fixtures, data/vek.json #262), the
    /// live-game `GlowingScorpion` class name used in Weather Watch, and
    /// Pinnacle `*_Boom` bots from Mission_BoomBots. These all trigger the
    /// same 1-damage four-adjacent-tile death splash. Keeping this as one
    /// helper guarantees every decay-firing callsite uses the same set of
    /// type names.
    pub fn is_volatile_vek(&self) -> bool {
        let name = self.type_name_str();
        name.contains("Volatile_Vek") || name.contains("GlowingScorpion") || name.ends_with("_Boom")
    }

    /// Set type name from string.
    pub fn set_type_name(&mut self, name: &str) {
        let bytes = name.as_bytes();
        let len = bytes.len().min(self.type_name.len());
        self.type_name[..len].copy_from_slice(&bytes[..len]);
        if len < self.type_name.len() {
            self.type_name[len] = 0;
        }
    }

    /// Effectively flying: flying AND not frozen (frozen flying = grounded)
    pub fn effectively_flying(&self) -> bool {
        self.flying() && !self.frozen()
    }

    pub fn has_target(&self) -> bool {
        self.queued_target_x >= 0
    }
}

// ── Board ────────────────────────────────────────────────────────────────────

/// Fixed-size board state. ~800 bytes, Clone is a memcpy.
#[derive(Clone, Debug)]
pub struct Board {
    pub tiles: [Tile; 64],
    pub units: [Unit; 16],
    pub unit_count: u8,
    /// Live enemy attack order from bridge JSON. Empty means legacy payloads
    /// should fall back to UID order.
    pub attack_order: Vec<u16>,
    pub grid_power: u8,
    pub grid_power_max: u8,
    // Grid Defense: % chance any building resists damage. Not exposed by
    // ITB's Lua API (C++-only), so default to 15 (game baseline). Set
    // higher when reputation upgrades it. Read by evaluator for expected
    // grid offset.
    pub grid_defense_pct: u8,
    // Expected grid power saved during the simulated enemy phase via Grid
    // Defense (buildings_destroyed * grid_defense_pct / 100). f32 because
    // it's a fractional expected value. Evaluator adds to grid_power.
    pub enemy_grid_save_expected: f32,
    // Expected grid power saved during the simulated PLAYER phase via Grid
    // Defense — i.e., the 15% resist roll fires on friendly-fire building
    // damage too (per text.lua:122 "This building resisted damage!"). Pre-
    // sim-v32 the simulator only modeled the enemy-phase save; plans that
    // clipped buildings with Cluster Artillery / Ranged_Defensestrike etc.
    // over-predicted grid loss by ~0.15 per friendly hit, biasing the solver
    // toward grid-conservative plans that the actual game would survive.
    // Accumulated in `simulate_action` (each player action's
    // `result.grid_damage * gd / 100`); cleared on Board construction and
    // never reset mid-search — solver.rs clones `board` per branch so each
    // search subtree carries its own running total. Surfaces in evaluate.rs
    // `eff_grid` alongside `enemy_grid_save_expected`.
    pub player_grid_save_expected: f32,
    pub env_danger: u64,        // bitset: bit i = tile i is danger
    pub env_danger_kill: u64,   // bitset: bit i = tile i is lethal env (Deadly Threat: air strike, lightning, etc.)
    /// Bitset: bit i = tile i is a TERRAIN-CONVERSION lethal env (Tidal Wave →
    /// water, Cataclysm/Seismic → chasm). Effectively-flying units stand on
    /// these without dying — water rules let flyers hover, chasm rules let
    /// flyers hover. Massive non-flying still die per existing tests
    /// (water-conversion is treated as a destroy, not a drown, and chasm
    /// always kills non-flying including Massive).
    ///
    /// Air Strike / Lightning / Satellite Rocket / Final Cave falling rocks
    /// are NOT in this set — those bypass flight (bombs / lightning / rocks
    /// hit anything in the air).
    /// Subset of `env_danger_kill`. When a kill tile is NOT in this set,
    /// flying offers no protection.
    pub env_danger_flying_immune: u64,
    /// Bitset: bit i = tile i is the next Mission_Terratide Sandstorm lane.
    /// The bridge reports these warning tiles through
    /// `environment_danger_v2`, but the live effect is smoke only: no damage,
    /// terrain death, or building loss. Applied before queued Vek attacks so
    /// an attacker caught by the wave is smoke-cancelled.
    ///
    /// Disjoint from `env_danger`; keeping a separate channel prevents the
    /// evaluator from assigning phantom damage/death to Terratide tiles.
    pub env_smoke: u64,
    /// Bitset: bit i = tile i is affected by Mission_Wind. Wind is a push
    /// effect, not direct 1 HP environment damage.
    pub env_wind: u64,
    /// Mission_Wind push direction, matching engine DIR_* constants and Rust
    /// DIRS. -1 means older bridge/recording without WindDir export.
    pub env_wind_dir: i8,
    /// Bitset: bit i = tile i is an Ice Storm freeze tile (vanilla
    /// Env_SnowStorm). At start of enemy turn the simulator applies
    /// Frozen=true to any alive unit standing on these tiles. Buildings
    /// and mountains are unaffected (Frozen is a unit status). Shield
    /// blocks the freeze and is consumed (per ITB shield rule:
    /// "blocks one instance of damage + negative effects"). Already-
    /// frozen units no-op (idempotent).
    ///
    /// Disjoint from `env_danger` — freeze tiles route here instead, so
    /// the evaluator scores "lose a turn" via `mech_self_frozen` rather
    /// than the "instant-kill or 1 dmg" branches that fire for env_danger.
    /// NanoStorm (Acid=true SnowStorm subclass) is NOT here; it uses
    /// env_danger with kill_int=0 since it deals 1 damage instead of
    /// freezing.
    pub env_freeze: u64,
    pub unique_buildings: u64,  // bitset: bit i = tile i is a mission objective building (Coal Plant, Power Generator, Emergency Batteries)
    pub grid_reward_buildings: u64, // bitset: subset of unique_buildings whose survival restores +1 Grid Power at mission end (Str_Power / Str_Battery / Mission_Solar). See evaluate.rs.
    pub freeze_building_tiles: u64, // bitset: Mission_FreezeBldg buildings that start frozen and count toward "Break 5 buildings out of the ice"
    pub freeze_building_target: u8, // Mission_FreezeBldg thaw target (normally 5); 0 when inactive.
    /// Per-tile grid debt from non-unique multi-HP buildings damaged by
    /// bump/push collision or Aerial Bombs thaw damage on Mission_FreezeBldg
    /// objective buildings. Live grid can remain unchanged at first HP loss,
    /// then charge the earlier damage at enemy-turn settle or if the same
    /// building is later destroyed.
    pub deferred_bump_grid_debt: [u8; 64],
    pub blast_psion: bool,   // Blast Psion (Jelly_Explode1): all Vek explode on death
    pub armor_psion: bool,   // Shell Psion (Jelly_Armor1): all Vek gain Armor
    pub soldier_psion: bool, // Soldier Psion (Jelly_Health1): all Vek +1 HP
    pub regen_psion: bool,   // Blood Psion (Jelly_Regen1): all Vek regen 1 HP/turn
    pub tyrant_psion: bool,  // Psion Tyrant (Jelly_Lava1): 1 dmg to all player units/turn
    pub boss_psion: bool,    // Psion Abomination (Jelly_Boss): combined HEALTH + REGEN + EXPLODE aura
    pub boost_psion: bool,   // Boost Psion (Jelly_Boost1, AE): +1 dmg to all Vek weapon attacks
    pub fire_psion: bool,    // Fire Psion (Jelly_Fire1, AE): Vek immune to fire + Vek leave fire on tile when killed
    pub spider_psion: bool,  // Spider Psion (Jelly_Spider1, AE): Vek leave a SpiderlingEgg1 on tile when killed
    pub boss_alive: bool,    // True when a Boss-type enemy is alive (mission objective)
    pub storm_generator: bool,  // Passive_Electric: enemies in smoke take 1 dmg
    pub flame_shielding: bool,  // Passive_FlameImmune: mechs immune to fire
    /// Passive_FireBoost / Heat Engines: player mechs standing on fire consume
    /// the fire and gain Boost instead of catching fire.
    pub heat_engines: bool,
    /// Passive_HealingSmoke / Nanofilter Mending: player mechs standing on
    /// smoke heal 1 HP and consume the smoke.
    pub healing_smoke: bool,
    /// Passive_Leech / Viscera Nanobots heal amount for player mechs that
    /// deal killing blows. 0 means the passive is not currently available.
    pub viscera_nanobots_heal: u8,
    pub vek_hormones: bool,     // Passive_FriendlyFire: enemy attacks +1 to other enemies
    pub force_amp: bool,        // Passive_ForceAmp: Vek take +1 from bump/spawn-block
                                // damage. Excludes sentient enemies (Bot Leader).
    pub medical_supplies: bool, // Passive_Medical: all pilots survive mech death (no
                                // permanent pilot loss). The mech is still destroyed —
                                // grid/HP/threat consequences unchanged; only the
                                // pilot_value permanent-loss component is zeroed in
                                // evaluate.rs.
    pub current_turn: u8,       // 0-indexed (0 = deployment, 1 = first combat turn)
    pub total_turns: u8,        // Mission length (typically 5, train/tidal = 4)
    pub remaining_spawns: u32,  // Queued Vek spawns still to emerge (from bridge
                                // mission.EnemyList etc). 0 = no more reinforcements
                                // after current turn, treat as final turn for scoring.
    pub infinite_spawn: bool,   // True on boss / Mission_Infinite missions where
                                // `turn_limit` is null and the bridge reports
                                // total_turns = current_turn every turn. Used by
                                // `evaluate::future_factor` to floor at 0.5 instead
                                // of 0.0 so kills aren't valued at zero on the
                                // bridge-reported "final" turn. See
                                // feedback_grid_management.md / Corp HQ M05 defeat
                                // 2026-04-28.
    pub mission_id: String,     // Mission class name from bridge (e.g. "Mission_Dam").
                                // Empty when the bridge couldn't resolve it.
    pub mission_kill_target: u8,   // "Kill at least N enemies" target. Generic
                                // BONUS_KILL_FIVE comes from mission:GetKillBonus();
                                // Mission_AcidTank is fixed at 4 acid kills.
    pub mission_kill_limit: u8,    // "Kill N or fewer enemies" bonus cap from
                                // mission:GetPacifistCount(). 0 when the mission
                                // doesn't have BONUS_PACIFIST in its BonusObjs.
    pub mission_kills_done: u8,    // Cumulative this-mission kill counter
                                // (mission.KilledVek, or mission.AcidKills for
                                // Mission_AcidTank). Combined with simulated turn
                                // kills to decide target/cap outcomes.
    pub mission_mountain_target: u8, // Mission_Force "Destroy 2 mountains" target.
    pub mission_mountains_destroyed: u8, // Cumulative EVENT_MOUNTAIN_DESTROYED count.
    pub mission_mountain_tiles: u64, // bitset: current mountain tiles at solve input.
    pub repair_platform_target: u8, // Mission_Repair objective target (normally 3).
    pub repair_platforms_used: u8,  // Cumulative EVENT_REPAIR_PICKUP count.
    pub dam_alive: bool,        // True while at least one Dam_Pawn has hp > 0. Flips
                                // false exactly once when the last tile is destroyed —
                                // the transition triggers trigger_dam_flood().
    pub dam_primary: Option<(u8, u8)>, // Coords of the Dam_Pawn's primary tile (the
                                // one WITHOUT the EXTRA_TILE flag). Used to compute
                                // the 14-tile flood offsets.
    pub bigbomb_alive: bool,    // True while the Renfield Bomb (BigBomb) is on-board
                                // with hp > 0. Mission_Final_Cave win-condition NPC —
                                // losing it fails the mission. The transition
                                // alive→dead is scored by `bigbomb_killed` in the
                                // evaluator, on top of the standard friendly_npc
                                // penalty. False on missions without a bomb.
    // Teleporter pad pairs for Mission_Teleporter (Detritus disposal missions).
    // Each entry = (x1, y1, x2, y2) — the two paired pads swap any unit that
    // ends movement on one of them. Bridge populates via the Board.AddTeleport
    // hook (see modloader.lua). Typical Disposal Site C map has 2 pairs across
    // 4 pads; other missions usually have 0. Iterated linearly in
    // `teleport_partner()` — stays cheap at this size.
    pub teleporter_pairs: Vec<(u8, u8, u8, u8)>,
    /// Per-mission "do not kill X" bonus objective unit-type list. When
    /// empty, the evaluator's `volatile_enemy_killed` penalty is a no-op
    /// (no protected types this mission). When non-empty, the penalty
    /// fires only on kills whose `type_name` is in this list. Populated
    /// via `JsonInput::bonus_objective_unit_types` (Lua bridge or Python
    /// `data/mission_bonus_objectives.json`). Replaces the previous
    /// hardcoded "always penalize Volatile_Vek / GlowingScorpion" gate
    /// which fired on every Weather Watch kill regardless of whether the
    /// current mission's BonusObjs actually included BONUS_PROTECT_X.
    pub bonus_dont_kill_types: Vec<String>,
    /// Unit-based mission objectives to destroy (e.g. Mission_Hacking's
    /// Hacked_Building). Matched by type-name substring.
    pub destroy_objective_unit_types: Vec<String>,
    /// Unit-based mission objectives to protect even when they start on
    /// enemy team before conversion (e.g. Mission_Hacking's Cannon Bot).
    pub protect_objective_unit_types: Vec<String>,
    /// Queued Spider Psion egg spawns produced by `on_enemy_death` during
    /// the current phase. Player-phase kills drain immediately after the
    /// action so replay snapshots and partial re-solves see the egg. Enemy-
    /// phase kills drain at the END of `simulate_enemy_attacks` so eggs
    /// spawned mid-enemy-phase do NOT hatch in the same phase (matching the
    /// game's `AddQueuedDamage`-driven hatch in weapons_enemy.lua:857).
    /// Each entry = (x, y) of the Vek that just died. Cleared on Board
    /// construction; the queue is short-lived (always drained before the
    /// turn returns).
    pub pending_spider_eggs: Vec<(u8, u8)>,
}

impl Default for Board {
    fn default() -> Self {
        Board {
            tiles: [Tile::default(); 64],
            units: [Unit::default(); 16],
            unit_count: 0,
            attack_order: Vec::new(),
            grid_power: 7,
            grid_power_max: 7,
            grid_defense_pct: 15,
            enemy_grid_save_expected: 0.0,
            player_grid_save_expected: 0.0,
            env_danger: 0,
            env_danger_kill: 0,
            env_danger_flying_immune: 0,
            env_smoke: 0,
            env_wind: 0,
            env_wind_dir: -1,
            env_freeze: 0,
            unique_buildings: 0,
            grid_reward_buildings: 0,
            freeze_building_tiles: 0,
            freeze_building_target: 0,
            deferred_bump_grid_debt: [0; 64],
            blast_psion: false,
            armor_psion: false,
            soldier_psion: false,
            regen_psion: false,
            tyrant_psion: false,
            boss_psion: false,
            boost_psion: false,
            fire_psion: false,
            spider_psion: false,
            boss_alive: false,
            storm_generator: false,
            flame_shielding: false,
            heat_engines: false,
            healing_smoke: false,
            viscera_nanobots_heal: 0,
            vek_hormones: false,
            force_amp: false,
            medical_supplies: false,
            current_turn: 0,
            total_turns: 5,
            remaining_spawns: u32::MAX, // Unknown → treat as "plenty of future"
            infinite_spawn: false,
            mission_id: String::new(),
            mission_kill_target: 0,
            mission_kill_limit: 0,
            mission_kills_done: 0,
            mission_mountain_target: 0,
            mission_mountains_destroyed: 0,
            mission_mountain_tiles: 0,
            repair_platform_target: 0,
            repair_platforms_used: 0,
            dam_alive: false,
            dam_primary: None,
            bigbomb_alive: false,
            teleporter_pairs: Vec::new(),
            bonus_dont_kill_types: Vec::new(),
            destroy_objective_unit_types: Vec::new(),
            protect_objective_unit_types: Vec::new(),
            pending_spider_eggs: Vec::new(),
        }
    }
}

impl Board {
    /// Get tile at (x, y). Panics if out of bounds.
    #[inline]
    pub fn tile(&self, x: u8, y: u8) -> &Tile {
        &self.tiles[xy_to_idx(x, y)]
    }

    /// Get mutable tile at (x, y).
    #[inline]
    pub fn tile_mut(&mut self, x: u8, y: u8) -> &mut Tile {
        &mut self.tiles[xy_to_idx(x, y)]
    }

    /// Find alive unit at (x, y). Returns index into units array.
    ///
    /// NOTE ON MULTI-TILE PAWNS (Dam_Pawn): a single pawn may appear as
    /// multiple entries with the same `uid` at different (x,y) — one per
    /// `ExtraSpaces` tile. This lookup correctly returns the entry at the
    /// specific tile queried, which is what push/damage call sites want.
    /// HP is mirrored across entries in `apply_damage_core` (simulate.rs)
    /// so either entry reflects the pawn's real HP. Any new iteration
    /// over `board.units` without a team/is_enemy/is_player filter should
    /// add `!u.is_extra_tile()` if it accumulates per-pawn state.
    pub fn unit_at(&self, x: u8, y: u8) -> Option<usize> {
        for i in 0..self.unit_count as usize {
            let u = &self.units[i];
            if u.x == x && u.y == y && u.hp > 0 {
                return Some(i);
            }
        }
        None
    }

    /// Find ANY unit at (x, y), including dead (hp <= 0).
    /// Used by apply_push: damage and push are simultaneous.
    pub fn any_unit_at(&self, x: u8, y: u8) -> Option<usize> {
        for i in 0..self.unit_count as usize {
            let u = &self.units[i];
            if u.x == x && u.y == y {
                return Some(i);
            }
        }
        None
    }

    /// Infer Spider/Web Egg grapples from adjacency.
    ///
    /// The live bridge can miss or misattribute `IsGrappled()` for WebbEgg1
    /// holds. The engine rule is tile-based: a living WebbEgg1 webs every
    /// living unit in the four cardinal adjacent tiles. Keep this helper
    /// authoritative so bridge loading and simulated landings agree.
    pub fn refresh_webb_egg_grapples(&mut self) {
        let mut eggs: [(u8, u8, u16); 16] = [(0, 0, 0); 16];
        let mut egg_count = 0usize;
        for i in 0..self.unit_count as usize {
            let u = &self.units[i];
            if u.hp > 0 && u.type_name_str() == "WebbEgg1" && egg_count < eggs.len() {
                eggs[egg_count] = (u.x, u.y, u.uid);
                egg_count += 1;
            }
        }

        for &(ex, ey, egg_uid) in eggs[..egg_count].iter() {
            for &(dx, dy) in &DIRS {
                let nx = ex as i8 + dx;
                let ny = ey as i8 + dy;
                if !in_bounds(nx, ny) { continue; }
                if let Some(idx) = self.unit_at(nx as u8, ny as u8) {
                    if self.existing_web_source_still_holds(idx) {
                        continue;
                    }
                    self.units[idx].set_web(true);
                    self.units[idx].web_source_uid = egg_uid;
                }
            }
        }
    }

    fn existing_web_source_still_holds(&self, unit_idx: usize) -> bool {
        let unit = &self.units[unit_idx];
        if !unit.web() || unit.web_source_uid == 0 {
            return false;
        }

        let source_idx = (0..self.unit_count as usize).find(|&i| {
            let src = &self.units[i];
            src.uid == unit.web_source_uid && src.hp > 0
        });
        let Some(source_idx) = source_idx else {
            return false;
        };
        let source = &self.units[source_idx];
        if source.type_name_str() == "WebbEgg1" {
            return false;
        }

        source.queued_target_x == unit.x as i8
            && source.queued_target_y == unit.y as i8
    }

    /// Teleporter partner: if (x, y) is a pad, return the coords of its
    /// paired pad. None if not a pad or no pairs on this board.
    ///
    /// Pads are an overlay added by `Board:AddTeleport(p1, p2)` during
    /// mission setup — stored on the Board, not the Tile. See
    /// `apply_teleport_on_land` (simulate.rs) for when this fires.
    #[inline]
    pub fn teleport_partner(&self, x: u8, y: u8) -> Option<(u8, u8)> {
        for &(ax, ay, bx, by) in &self.teleporter_pairs {
            if ax == x && ay == y { return Some((bx, by)); }
            if bx == x && by == y { return Some((ax, ay)); }
        }
        None
    }

    /// Check if dead unit wreck at (x, y). Wrecks block movement.
    pub fn wreck_at(&self, x: u8, y: u8) -> bool {
        for i in 0..self.unit_count as usize {
            let u = &self.units[i];
            if u.x == x && u.y == y && u.hp <= 0 {
                return true;
            }
        }
        false
    }

    /// Is tile blocked for movement?
    pub fn is_blocked(&self, x: u8, y: u8, flying: bool) -> bool {
        let t = self.tile(x, y);
        if t.terrain.blocks_all() { return true; }
        if !flying && t.terrain.is_deadly_ground() { return true; }
        if self.unit_at(x, y).is_some() { return true; }
        if self.wreck_at(x, y) { return true; }
        // Any Building terrain blocks: live buildings (hp>0) and destroyed
        // objective unique_buildings (stay as terrain=Building with hp=0 and
        // remain IsBlocked in-game). Regular buildings collapse to Rubble
        // terrain when destroyed, so terrain=Building implies "still blocks".
        if t.terrain == Terrain::Building { return true; }
        false
    }

    /// Is tile on the env_danger bitset?
    #[inline]
    pub fn is_env_danger(&self, x: u8, y: u8) -> bool {
        let bit = 1u64 << xy_to_idx(x, y);
        self.env_danger & bit != 0
    }

    /// Is tile on the env_freeze bitset (Ice Storm)? Units standing here at
    /// the start of the enemy turn get Frozen=true (shield blocks + consumed,
    /// already-frozen idempotent, buildings/mountains unaffected).
    #[inline]
    pub fn is_env_freeze(&self, x: u8, y: u8) -> bool {
        let bit = 1u64 << xy_to_idx(x, y);
        self.env_freeze & bit != 0
    }

    /// Is tile on the env_danger_kill bitset (Deadly Threat / kill_int=1)?
    #[inline]
    pub fn is_env_danger_kill(&self, x: u8, y: u8) -> bool {
        let bit = 1u64 << xy_to_idx(x, y);
        self.env_danger_kill & bit != 0
    }

    /// Is the lethal env on this tile a terrain-conversion event whose
    /// kill effect skips flying units (Tidal Wave, Cataclysm, Seismic)?
    /// Always false for Air Strike / Lightning style "Deadly Threat"
    /// hazards — those hit flyers too.
    #[inline]
    pub fn is_env_danger_flying_immune(&self, x: u8, y: u8) -> bool {
        let bit = 1u64 << xy_to_idx(x, y);
        self.env_danger_flying_immune & bit != 0
    }

    /// Is this tile in the next Terratide/Sandstorm smoke lane?
    #[inline]
    pub fn is_env_smoke(&self, x: u8, y: u8) -> bool {
        let bit = 1u64 << xy_to_idx(x, y);
        self.env_smoke & bit != 0
    }

    /// Iterate alive player units (mechs + friendly controllable).
    pub fn active_mechs(&self) -> Vec<usize> {
        let mut result = Vec::new();
        for i in 0..self.unit_count as usize {
            let u = &self.units[i];
            if u.is_player_action_unit() {
                result.push(i);
            }
        }
        result
    }

    /// Iterate alive enemies.
    pub fn enemies(&self) -> Vec<usize> {
        let mut result = Vec::new();
        for i in 0..self.unit_count as usize {
            let u = &self.units[i];
            if u.is_enemy() && u.alive() {
                result.push(i);
            }
        }
        result
    }

    /// Add a unit to the board. Returns its index.
    pub fn add_unit(&mut self, unit: Unit) -> usize {
        let idx = self.unit_count as usize;
        assert!(idx < 16, "Board unit capacity exceeded");
        self.units[idx] = unit;
        self.unit_count += 1;
        idx
    }

    pub fn add_mission_kills(&mut self, kills: i32) {
        if kills <= 0 {
            return;
        }
        self.mission_kills_done = self
            .mission_kills_done
            .saturating_add(kills.min(u8::MAX as i32) as u8);
    }

    pub fn projected_mountains_destroyed(&self) -> u8 {
        if self.mission_mountain_target == 0 {
            return self.mission_mountains_destroyed;
        }
        let mut destroyed = self.mission_mountains_destroyed;
        let mut bits = self.mission_mountain_tiles;
        while bits != 0 {
            let idx = bits.trailing_zeros() as usize;
            bits &= bits - 1;
            let tile = &self.tiles[idx];
            if tile.terrain != Terrain::Mountain || tile.building_hp == 0 {
                destroyed = destroyed.saturating_add(1);
            }
        }
        destroyed
    }
}

pub fn unit_counts_for_mission_kill(mission_id: &str, unit: &Unit) -> bool {
    if !unit.is_enemy() || unit.minor() {
        return false;
    }
    if mission_id == "Mission_AcidTank" {
        return unit.acid();
    }
    true
}

// ── Action Result ────────────────────────────────────────────────────────────

/// Tracks simulation outcomes for a single action.
#[derive(Clone, Debug, Default)]
pub struct ActionResult {
    pub buildings_lost: i32,
    pub buildings_damaged: i32,
    pub buildings_bump_damaged: i32,
    pub grid_damage: i32,
    pub enemies_killed: i32,
    pub mission_kills: i32,
    pub unit_deaths: i32,
    pub leech_credit_kills: i32,
    pub leech_uncapped_kills: i32,
    pub enemy_damage_dealt: i32,
    pub mech_damage_taken: i32,
    pub mech_hp_repaired: i32,
    pub mechs_killed: i32,
    pub pods_collected: i32,
    pub repair_platforms_used: i32,
    pub spawns_blocked: i32,
    pub events: Vec<String>,
}

impl ActionResult {
    pub fn record_enemy_kill(&mut self, mission_counted: bool) {
        self.record_enemy_kill_with_leech_credit(mission_counted, false);
    }

    pub fn record_enemy_kill_with_leech_credit(
        &mut self,
        mission_counted: bool,
        leech_credit: bool,
    ) {
        self.enemies_killed += 1;
        if mission_counted {
            self.mission_kills += 1;
        }
        if leech_credit {
            self.leech_credit_kills += 1;
        }
    }

    pub fn merge(&mut self, other: &ActionResult) {
        self.buildings_lost += other.buildings_lost;
        self.buildings_damaged += other.buildings_damaged;
        self.buildings_bump_damaged += other.buildings_bump_damaged;
        self.grid_damage += other.grid_damage;
        self.enemies_killed += other.enemies_killed;
        self.mission_kills += other.mission_kills;
        self.unit_deaths += other.unit_deaths;
        self.leech_credit_kills += other.leech_credit_kills;
        self.leech_uncapped_kills += other.leech_uncapped_kills;
        self.enemy_damage_dealt += other.enemy_damage_dealt;
        self.mech_damage_taken += other.mech_damage_taken;
        self.mech_hp_repaired += other.mech_hp_repaired;
        self.mechs_killed += other.mechs_killed;
        self.pods_collected += other.pods_collected;
        self.repair_platforms_used += other.repair_platforms_used;
        self.spawns_blocked += other.spawns_blocked;
        self.events.extend_from_slice(&other.events);
    }
}

/// Count unique unit deaths across a board transition.
///
/// No Survivors counts deaths from any team. Several vanilla pawns serialize
/// multiple board entries with the same uid (for example train/dam extra
/// spaces), so this uses uid-level alive state rather than raw entry count.
pub fn count_unit_deaths_between(before: &Board, after: &Board) -> i32 {
    let mut before_alive: BTreeMap<u16, bool> = BTreeMap::new();
    let mut before_present: BTreeSet<u16> = BTreeSet::new();
    for i in 0..before.unit_count as usize {
        let u = &before.units[i];
        before_present.insert(u.uid);
        let entry = before_alive.entry(u.uid).or_insert(false);
        *entry |= u.hp > 0;
    }

    let mut after_alive: BTreeMap<u16, bool> = BTreeMap::new();
    let mut new_dead_after: BTreeSet<u16> = BTreeSet::new();
    for i in 0..after.unit_count as usize {
        let u = &after.units[i];
        let entry = after_alive.entry(u.uid).or_insert(false);
        *entry |= u.hp > 0;
        if !before_present.contains(&u.uid) && u.hp <= 0 {
            new_dead_after.insert(u.uid);
        }
    }

    let mut deaths = 0;
    for (uid, was_alive) in before_alive {
        if was_alive && !after_alive.get(&uid).copied().unwrap_or(false) {
            deaths += 1;
        }
    }
    deaths + new_dead_after.len() as i32
}

// ── Size assertions ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tile_size() {
        assert!(std::mem::size_of::<Tile>() <= 6, "Tile too large: {} bytes", std::mem::size_of::<Tile>());
    }

    #[test]
    fn test_tile_default_has_no_conveyor() {
        assert_eq!(Tile::default().conveyor_dir, -1);
        assert_eq!(Board::default().tile(0, 0).conveyor_dir, -1);
    }

    #[test]
    fn test_count_unit_deaths_between_counts_unique_uids() {
        let mut before = Board::default();
        before.unit_count = 4;
        before.units[0] = Unit { uid: 10, hp: 1, max_hp: 1, ..Default::default() };
        before.units[1] = Unit { uid: 20, hp: 1, max_hp: 1, ..Default::default() };
        before.units[2] = Unit { uid: 30, hp: 1, max_hp: 1, ..Default::default() };
        before.units[3] = Unit { uid: 30, hp: 1, max_hp: 1, ..Default::default() };

        let mut after = before.clone();
        after.units[0].hp = 0;
        after.units[1].hp = 0;
        after.units[2].hp = 0;
        after.units[3].hp = 0;

        assert_eq!(count_unit_deaths_between(&before, &after), 3);
    }

    #[test]
    fn test_board_size() {
        // Soft sanity bound: Board stays small enough that Clone is cheap.
        // Pilot_flags (u8 + alignment) on 16 Units added ~40 bytes, still
        // well under any hot-path concern — memcpy bandwidth on M-series
        // is ~60GB/s, so 1.3kB copies are sub-nanosecond.
        // Sim v21: bonus_dont_kill_types: Vec<String> added 24 bytes
        // (Vec header). Empty Vec doesn't allocate, so Clone is still
        // a memcpy on the common path; only missions with populated
        // objective/projection lists pay heap-clone costs (1× per branch).
        // Sim v32+ added grid-defense expectation, unit-objective Vecs, and
        // the Spider Psion egg queue; 1.6kB is still comfortably cheap.
        let size = std::mem::size_of::<Board>();
        println!("Board size: {} bytes", size);
        assert!(size <= 1700, "Board too large: {} bytes", size);
    }

    #[test]
    fn test_board_clone() {
        let mut board = Board::default();
        board.grid_power = 5;
        board.tiles[0].terrain = Terrain::Building;
        board.tiles[0].building_hp = 1;

        let board2 = board.clone();
        assert_eq!(board2.grid_power, 5);
        assert_eq!(board2.tiles[0].terrain, Terrain::Building);
        assert_eq!(board2.tiles[0].building_hp, 1);
    }

    #[test]
    fn test_unit_at() {
        let mut board = Board::default();
        board.add_unit(Unit {
            uid: 1,
            x: 3, y: 4,
            hp: 2, max_hp: 2,
            team: Team::Enemy,
            ..Default::default()
        });

        assert!(board.unit_at(3, 4).is_some());
        assert!(board.unit_at(0, 0).is_none());
    }

    #[test]
    fn test_pinnacle_bots_do_not_receive_psion_auras() {
        let mut bot = Unit {
            uid: 1,
            hp: 1,
            max_hp: 1,
            team: Team::Enemy,
            ..Default::default()
        };
        bot.set_type_name("Snowtank1");

        let mut vek = Unit {
            uid: 2,
            hp: 1,
            max_hp: 1,
            team: Team::Enemy,
            ..Default::default()
        };
        vek.set_type_name("Leaper1");

        assert!(!bot.receives_psion_aura());
        assert!(vek.receives_psion_aura());
    }

    #[test]
    fn test_dead_unit_invisible_to_unit_at() {
        let mut board = Board::default();
        board.add_unit(Unit {
            uid: 1,
            x: 3, y: 4,
            hp: 0, max_hp: 2,
            team: Team::Enemy,
            ..Default::default()
        });

        // unit_at skips dead units
        assert!(board.unit_at(3, 4).is_none());
        // any_unit_at finds them
        assert!(board.any_unit_at(3, 4).is_some());
        // wreck_at reports them
        assert!(board.wreck_at(3, 4));
    }

    #[test]
    fn test_env_danger_bitset() {
        let mut board = Board::default();
        // Set tile (2, 3) as danger
        board.env_danger |= 1u64 << xy_to_idx(2, 3);
        assert!(board.is_env_danger(2, 3));
        assert!(!board.is_env_danger(0, 0));
    }
}
