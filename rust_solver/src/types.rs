/// Core type definitions for the Into the Breach solver.
///
/// All string-typed fields from the Python version become compact enums here.
/// This eliminates heap allocation and enables fast comparison/matching.

// ── Terrain ──────────────────────────────────────────────────────────────────

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
#[repr(u8)]
pub enum Terrain {
    #[default]
    Ground = 0,
    Building = 1,
    Mountain = 2,
    Water = 3,
    Chasm = 4,
    Lava = 5,
    Forest = 6,
    Sand = 7,
    Ice = 8,
    Rubble = 9,
    Fire = 10,
}

impl Terrain {
    pub fn from_str(s: &str) -> Self {
        match s {
            "ground" => Terrain::Ground,
            "building" => Terrain::Building,
            "mountain" => Terrain::Mountain,
            "water" => Terrain::Water,
            "chasm" => Terrain::Chasm,
            "lava" => Terrain::Lava,
            "forest" => Terrain::Forest,
            "sand" => Terrain::Sand,
            "ice" => Terrain::Ice,
            "rubble" => Terrain::Rubble,
            "fire" => Terrain::Fire,
            _ => Terrain::Ground,
        }
    }

    /// Is this terrain deadly to non-flying ground units?
    pub fn is_deadly_ground(self) -> bool {
        matches!(self, Terrain::Water | Terrain::Chasm | Terrain::Lava)
    }

    /// Does this terrain block all movement?
    pub fn blocks_all(self) -> bool {
        matches!(self, Terrain::Mountain)
    }
}

// ── Team ─────────────────────────────────────────────────────────────────────

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
#[repr(u8)]
pub enum Team {
    Player = 1,
    Neutral = 2,
    #[default]
    Enemy = 6,
}

impl Team {
    pub fn from_int(i: u8) -> Self {
        match i {
            1 => Team::Player,
            2 => Team::Neutral,
            _ => Team::Enemy,
        }
    }
}

// ── Direction (cardinal) ─────────────────────────────────────────────────────

/// Cardinal directions: indices into DIRS array.
/// DIRS = [(0,1), (1,0), (0,-1), (-1,0)] matching Python's movement.py
pub const DIRS: [(i8, i8); 4] = [(0, 1), (1, 0), (0, -1), (-1, 0)];

pub fn opposite_dir(d: usize) -> usize {
    (d + 2) % 4
}

// ── Weapon Type ──────────────────────────────────────────────────────────────

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
#[repr(u8)]
pub enum WeaponType {
    #[default]
    Melee = 0,
    Projectile = 1,
    Artillery = 2,
    Laser = 3,
    Leap = 4,
    Charge = 5,
    SelfAoe = 6,
    Swap = 7,
    Pull = 8,
    Deploy = 9,
    Passive = 10,
    TwoClick = 11,
}

impl WeaponType {
    pub fn from_str(s: &str) -> Self {
        match s {
            "melee" => WeaponType::Melee,
            "projectile" => WeaponType::Projectile,
            "artillery" => WeaponType::Artillery,
            "laser" => WeaponType::Laser,
            "leap" => WeaponType::Leap,
            "charge" => WeaponType::Charge,
            "self_aoe" => WeaponType::SelfAoe,
            "swap" => WeaponType::Swap,
            "pull" => WeaponType::Pull,
            "deploy" => WeaponType::Deploy,
            "passive" => WeaponType::Passive,
            "two_click" => WeaponType::TwoClick,
            _ => WeaponType::Melee,
        }
    }
}

// ── Push Direction ───────────────────────────────────────────────────────────

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
#[repr(u8)]
pub enum PushDir {
    #[default]
    None = 0,
    Forward = 1,
    Backward = 2,
    Perpendicular = 3,
    Outward = 4,
    Inward = 5,
    Flip = 6,
    /// Throw: target is removed from front of attacker and placed on the tile
    /// BEHIND the attacker (opposite side). Vice Fist (Prime_Shift). If the
    /// destination tile is blocked, target stays in place and takes bump damage.
    Throw = 7,
}

impl PushDir {
    pub fn from_str(s: &str) -> Self {
        match s {
            "forward" => PushDir::Forward,
            "backward" => PushDir::Backward,
            "perpendicular" => PushDir::Perpendicular,
            "outward" => PushDir::Outward,
            "inward" => PushDir::Inward,
            "flip" => PushDir::Flip,
            "throw" => PushDir::Throw,
            _ => PushDir::None,
        }
    }
}

// ── Damage Source ────────────────────────────────────────────────────────────

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
#[repr(u8)]
pub enum DamageSource {
    #[default]
    Weapon = 0,
    Bump = 1,
    Fire = 2,
    SelfDamage = 3,
}

// ── Coordinate helpers ───────────────────────────────────────────────────────

/// Convert flat index to (x, y). Board is 8x8.
#[inline]
pub fn idx_to_xy(idx: usize) -> (u8, u8) {
    ((idx / 8) as u8, (idx % 8) as u8)
}

/// Convert (x, y) to flat index.
#[inline]
pub fn xy_to_idx(x: u8, y: u8) -> usize {
    (x as usize) * 8 + (y as usize)
}

/// Check if (x, y) is within 8x8 bounds.
#[inline]
pub fn in_bounds(x: i8, y: i8) -> bool {
    (0..8).contains(&x) && (0..8).contains(&y)
}

/// Bridge (x,y) to visual notation (e.g., "C5").
pub fn bridge_to_visual(x: u8, y: u8) -> String {
    let col = (b'H' - y) as char;
    let row = 8 - x;
    format!("{}{}", col, row)
}
