/// Board, Tile, and Unit data structures.
///
/// Designed for fast Clone (memcpy of ~800 bytes). No heap allocation.
/// All boolean flags packed into bitflags for cache efficiency.

use bitflags::bitflags;
use crate::types::*;

// ── Tile Flags ───────────────────────────────────────────────────────────────

bitflags! {
    #[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
    pub struct TileFlags: u8 {
        const ON_FIRE     = 0b0000_0001;
        const SMOKE       = 0b0000_0010;
        const ACID        = 0b0000_0100;
        const FROZEN      = 0b0000_1000;
        const CRACKED     = 0b0001_0000;
        const HAS_POD     = 0b0010_0000;
        const FREEZE_MINE = 0b0100_0000;
        const OLD_EARTH_MINE = 0b1000_0000;
    }
}

// ── Tile ─────────────────────────────────────────────────────────────────────

#[derive(Clone, Copy, Debug, Default)]
pub struct Tile {
    pub terrain: Terrain,
    pub building_hp: u8,
    pub population: u8,
    pub flags: TileFlags,
    pub conveyor_dir: i8, // -1 = none, 0-3 = direction (matches DIRS)
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

    pub fn set_on_fire(&mut self, v: bool) { self.flags.set(TileFlags::ON_FIRE, v); }
    pub fn set_smoke(&mut self, v: bool) { self.flags.set(TileFlags::SMOKE, v); }
    pub fn set_acid(&mut self, v: bool) { self.flags.set(TileFlags::ACID, v); }
    pub fn set_cracked(&mut self, v: bool) { self.flags.set(TileFlags::CRACKED, v); }
    pub fn set_has_pod(&mut self, v: bool) { self.flags.set(TileFlags::HAS_POD, v); }
    pub fn set_freeze_mine(&mut self, v: bool) { self.flags.set(TileFlags::FREEZE_MINE, v); }
    pub fn set_old_earth_mine(&mut self, v: bool) { self.flags.set(TileFlags::OLD_EARTH_MINE, v); }

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
    }
}

bitflags! {
    #[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
    pub struct UnitFlags: u16 {
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

    pub fn set_active(&mut self, v: bool) { self.flags.set(UnitFlags::ACTIVE, v); }
    pub fn set_shield(&mut self, v: bool) { self.flags.set(UnitFlags::SHIELD, v); }
    pub fn set_frozen(&mut self, v: bool) { self.flags.set(UnitFlags::FROZEN, v); }
    pub fn set_fire(&mut self, v: bool) { self.flags.set(UnitFlags::FIRE, v); }
    pub fn set_acid(&mut self, v: bool) { self.flags.set(UnitFlags::ACID, v); }
    pub fn set_web(&mut self, v: bool) { self.flags.set(UnitFlags::WEB, v); }

    pub fn is_player(&self) -> bool { self.team == Team::Player }
    pub fn is_enemy(&self) -> bool { self.team == Team::Enemy }
    pub fn alive(&self) -> bool { self.hp > 0 }

    // Pilot-passive accessors. Enemies and neutrals never have these bits,
    // so there's no team check needed at call sites — a raw pilot_flags
    // read is 0 for any non-piloted unit.
    pub fn pilot_soldier(&self) -> bool { self.pilot_flags.contains(PilotFlags::SOLDIER) }
    pub fn pilot_rock(&self) -> bool { self.pilot_flags.contains(PilotFlags::ROCK) }
    pub fn pilot_repairman(&self) -> bool { self.pilot_flags.contains(PilotFlags::REPAIRMAN) }

    /// Can this unit catch fire? False for Ariadne (Pilot_Rock) and for
    /// any player unit when the squad has Flame Shielding (checked at the
    /// call site by passing `board.flame_shielding`). Keeping this on
    /// `Unit` alone avoids threading `board` through every fire-apply
    /// callsite — squad-wide Flame Shielding is handled separately at
    /// each hook (`!(board.flame_shielding && u.is_player())`).
    pub fn can_catch_fire(&self) -> bool { !self.pilot_rock() }

    /// Get pawn type name as string (from stored bytes).
    pub fn type_name_str(&self) -> &str {
        let len = self.type_name.iter().position(|&b| b == 0).unwrap_or(self.type_name.len());
        std::str::from_utf8(&self.type_name[..len]).unwrap_or("Unknown")
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
    pub env_danger: u64,        // bitset: bit i = tile i is danger
    pub env_danger_kill: u64,   // bitset: bit i = tile i is lethal env (Deadly Threat: air strike, lightning, etc.)
    pub unique_buildings: u64,  // bitset: bit i = tile i is a mission objective building (Coal Plant, Power Generator, Emergency Batteries)
    pub grid_reward_buildings: u64, // bitset: subset of unique_buildings whose survival restores +1 Grid Power at mission end (Str_Power / Str_Battery / Mission_Solar). See evaluate.rs.
    pub blast_psion: bool,   // Blast Psion (Jelly_Explode1): all Vek explode on death
    pub armor_psion: bool,   // Shell Psion (Jelly_Armor1): all Vek gain Armor
    pub soldier_psion: bool, // Soldier Psion (Jelly_Health1): all Vek +1 HP
    pub regen_psion: bool,   // Blood Psion (Jelly_Regen1): all Vek regen 1 HP/turn
    pub tyrant_psion: bool,  // Psion Tyrant (Jelly_Lava1): 1 dmg to all player units/turn
    pub boss_alive: bool,    // True when a Boss-type enemy is alive (mission objective)
    pub storm_generator: bool,  // Passive_Electric: enemies in smoke take 1 dmg
    pub flame_shielding: bool,  // Passive_FlameImmune: mechs immune to fire
    pub vek_hormones: bool,     // Passive_FriendlyFire: enemy attacks +1 to other enemies
    pub force_amp: bool,        // Passive_ForceAmp: Vek take +1 from bump/spawn-block
                                // damage. Excludes sentient enemies (Bot Leader).
    pub current_turn: u8,       // 0-indexed (0 = deployment, 1 = first combat turn)
    pub total_turns: u8,        // Mission length (typically 5, train/tidal = 4)
    pub remaining_spawns: u32,  // Queued Vek spawns still to emerge (from bridge
                                // mission.EnemyList etc). 0 = no more reinforcements
                                // after current turn, treat as final turn for scoring.
    pub mission_id: String,     // Mission class name from bridge (e.g. "Mission_Dam").
                                // Empty when the bridge couldn't resolve it.
    pub mission_kill_target: u8,   // "Kill N enemies" bonus target from mission:GetKillBonus()
                                // (7 on Normal/Hard, 5 on Easy). 0 when the mission
                                // doesn't have BONUS_KILL_FIVE in its BonusObjs.
    pub mission_kills_done: u8,    // Cumulative this-mission kills (mission.KilledVek).
                                // Combined with the simulated turn's kills to decide
                                // whether a plan crosses the kill target threshold.
    pub dam_alive: bool,        // True while at least one Dam_Pawn has hp > 0. Flips
                                // false exactly once when the last tile is destroyed —
                                // the transition triggers trigger_dam_flood().
    pub dam_primary: Option<(u8, u8)>, // Coords of the Dam_Pawn's primary tile (the
                                // one WITHOUT the EXTRA_TILE flag). Used to compute
                                // the 14-tile flood offsets.
}

impl Default for Board {
    fn default() -> Self {
        Board {
            tiles: [Tile::default(); 64],
            units: [Unit::default(); 16],
            unit_count: 0,
            grid_power: 7,
            grid_power_max: 7,
            grid_defense_pct: 15,
            enemy_grid_save_expected: 0.0,
            env_danger: 0,
            env_danger_kill: 0,
            unique_buildings: 0,
            grid_reward_buildings: 0,
            blast_psion: false,
            armor_psion: false,
            soldier_psion: false,
            regen_psion: false,
            tyrant_psion: false,
            boss_alive: false,
            storm_generator: false,
            flame_shielding: false,
            vek_hormones: false,
            force_amp: false,
            current_turn: 0,
            total_turns: 5,
            remaining_spawns: u32::MAX, // Unknown → treat as "plenty of future"
            mission_id: String::new(),
            mission_kill_target: 0,
            mission_kills_done: 0,
            dam_alive: false,
            dam_primary: None,
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

    /// Is tile on the env_danger_kill bitset (Deadly Threat / kill_int=1)?
    #[inline]
    pub fn is_env_danger_kill(&self, x: u8, y: u8) -> bool {
        let bit = 1u64 << xy_to_idx(x, y);
        self.env_danger_kill & bit != 0
    }

    /// Iterate alive player units (mechs + friendly controllable).
    pub fn active_mechs(&self) -> Vec<usize> {
        let mut result = Vec::new();
        for i in 0..self.unit_count as usize {
            let u = &self.units[i];
            if u.is_player() && u.alive() && u.active()
                && (u.is_mech() || !u.weapon.is_none())
            {
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
    pub enemy_damage_dealt: i32,
    pub mech_damage_taken: i32,
    pub mechs_killed: i32,
    pub pods_collected: i32,
    pub spawns_blocked: i32,
    pub events: Vec<String>,
}

impl ActionResult {
    pub fn merge(&mut self, other: &ActionResult) {
        self.buildings_lost += other.buildings_lost;
        self.buildings_damaged += other.buildings_damaged;
        self.buildings_bump_damaged += other.buildings_bump_damaged;
        self.grid_damage += other.grid_damage;
        self.enemies_killed += other.enemies_killed;
        self.enemy_damage_dealt += other.enemy_damage_dealt;
        self.mech_damage_taken += other.mech_damage_taken;
        self.mechs_killed += other.mechs_killed;
        self.pods_collected += other.pods_collected;
        self.spawns_blocked += other.spawns_blocked;
        self.events.extend_from_slice(&other.events);
    }
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
    fn test_board_size() {
        // Soft sanity bound: Board stays small enough that Clone is cheap.
        // Pilot_flags (u8 + alignment) on 16 Units added ~40 bytes, still
        // well under any hot-path concern — memcpy bandwidth on M-series
        // is ~60GB/s, so 1.3kB copies are sub-nanosecond.
        let size = std::mem::size_of::<Board>();
        println!("Board size: {} bytes", size);
        assert!(size <= 1280, "Board too large: {} bytes", size);
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
