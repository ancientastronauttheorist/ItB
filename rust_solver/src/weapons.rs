/// Weapon definitions — all 78 weapons hardcoded as const data.
/// Lookup is a direct array index: O(1), zero allocation.

use crate::types::*;

// ── Weapon Flags (packed booleans) ───────────────────────────────────────────

use bitflags::bitflags;

bitflags! {
    #[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
    pub struct WeaponFlags: u32 {
        const FIRE            = 1 << 0;
        const ACID            = 1 << 1;
        const FREEZE          = 1 << 2;
        const SMOKE           = 1 << 3;
        const SHIELD          = 1 << 4;
        const WEB             = 1 << 5;
        const TARGETS_ALLIES  = 1 << 6;
        const BUILDING_DAMAGE = 1 << 7;
        const PHASE           = 1 << 8;
        const AOE_CENTER      = 1 << 9;
        const AOE_ADJACENT    = 1 << 10;
        const AOE_BEHIND      = 1 << 11;
        const AOE_PERP        = 1 << 12;
        const CHAIN           = 1 << 13;
        const CHARGE          = 1 << 14;
        const FLYING_CHARGE   = 1 << 15;
        const PUSH_SELF       = 1 << 16;
    }
}

// ── WeaponDef ────────────────────────────────────────────────────────────────

#[derive(Clone, Copy, Debug)]
pub struct WeaponDef {
    pub weapon_type: WeaponType,
    pub damage: u8,
    pub damage_outer: u8,
    pub push: PushDir,
    pub self_damage: u8,
    pub range_min: u8,
    pub range_max: u8,   // 0 = unlimited
    pub limited: u8,     // 0 = unlimited uses
    pub flags: WeaponFlags,
}

impl WeaponDef {
    pub fn fire(&self) -> bool { self.flags.contains(WeaponFlags::FIRE) }
    pub fn acid(&self) -> bool { self.flags.contains(WeaponFlags::ACID) }
    pub fn freeze(&self) -> bool { self.flags.contains(WeaponFlags::FREEZE) }
    pub fn smoke(&self) -> bool { self.flags.contains(WeaponFlags::SMOKE) }
    pub fn shield(&self) -> bool { self.flags.contains(WeaponFlags::SHIELD) }
    pub fn web(&self) -> bool { self.flags.contains(WeaponFlags::WEB) }
    pub fn targets_allies(&self) -> bool { self.flags.contains(WeaponFlags::TARGETS_ALLIES) }
    pub fn phase(&self) -> bool { self.flags.contains(WeaponFlags::PHASE) }
    pub fn aoe_center(&self) -> bool { self.flags.contains(WeaponFlags::AOE_CENTER) }
    pub fn aoe_adjacent(&self) -> bool { self.flags.contains(WeaponFlags::AOE_ADJACENT) }
    pub fn aoe_behind(&self) -> bool { self.flags.contains(WeaponFlags::AOE_BEHIND) }
    pub fn aoe_perpendicular(&self) -> bool { self.flags.contains(WeaponFlags::AOE_PERP) }
    pub fn chain(&self) -> bool { self.flags.contains(WeaponFlags::CHAIN) }
    pub fn flying_charge(&self) -> bool { self.flags.contains(WeaponFlags::FLYING_CHARGE) }
    pub fn push_self(&self) -> bool { self.flags.contains(WeaponFlags::PUSH_SELF) }
}

/// Default weapon def (no-op).
const DEF: WeaponDef = WeaponDef {
    weapon_type: WeaponType::Melee,
    damage: 0, damage_outer: 0,
    push: PushDir::None,
    self_damage: 0,
    range_min: 1, range_max: 1,
    limited: 0,
    flags: WeaponFlags::AOE_CENTER, // aoe_center defaults true
};

// Helper macro to reduce boilerplate
macro_rules! wdef {
    ($($field:ident : $val:expr),* $(,)?) => {
        WeaponDef { $($field: $val,)* ..DEF }
    };
}

// Shorthand for common flag combos
const C: WeaponFlags = WeaponFlags::AOE_CENTER; // aoe_center only (default)
const fn f(bits: u32) -> WeaponFlags { WeaponFlags::from_bits_truncate(bits | WeaponFlags::AOE_CENTER.bits()) }
const fn f_nc(bits: u32) -> WeaponFlags { WeaponFlags::from_bits_truncate(bits) } // no aoe_center

// ── Weapon ID enum ───────────────────────────────────────────────────────────
// Index = position in WEAPONS array

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum WId {
    None = 0,
    // -- Prime --
    PrimePunchmech = 1,
    PrimeLightning = 2,
    PrimeLasermech = 3,
    PrimeShieldBash = 4,
    PrimeShift = 5,
    PrimeFlamethrower = 6,
    PrimeAreablast = 7,
    PrimeLeap = 8,
    PrimeSpear = 9,
    PrimeRockmech = 10,
    PrimeRocketPunch = 11,
    PrimeRightHook = 12,
    PrimeSpinFist = 13,
    PrimeSword = 14,
    PrimeSmash = 15,
    // -- Brute --
    BruteTankmech = 16,
    BruteJetmech = 17,
    BruteMirrorshot = 18,
    BruteBeetle = 19,
    BruteGrapple = 20,
    BruteUnstable = 21,
    BrutePhaseShot = 22,
    BruteShrapnel = 23,
    BruteHeavyrocket = 24,
    BruteSonic = 25,
    BruteShockblast = 26,
    BruteSniper = 27,
    BruteSplitshot = 28,
    BruteBombrun = 29,
    // -- Archive/Mission --
    ArchiveArtShot = 30,
    // -- Ranged --
    RangedArtillerymech = 31,
    RangedRockthrow = 32,
    RangedDefensestrike = 33,
    RangedRocket = 34,
    RangedIgnite = 35,
    RangedIce = 36,
    RangedScatterShot = 37,
    RangedBackShot = 38,
    RangedWide = 39,
    // -- Science --
    SciencePullmech = 40,
    ScienceGravwell = 41,
    ScienceRepulse = 42,
    ScienceSwap = 43,
    ScienceAcidShot = 44,
    ScienceShield = 45,
    ScienceConfuse = 46,
    // -- Enemy --
    ScorpionAtk1 = 47,
    ScorpionAtk2 = 48,
    HornetAtk1 = 49,
    HornetAtk2 = 50,
    LeaperAtk1 = 51,
    BeetleAtk1 = 52,
    BeetleAtk2 = 53,
    FireflyAtk1 = 54,
    FireflyAtk2 = 55,
    CentipedeAtk1 = 56,
    ScarabAtk1 = 57,
    ScarabAtk2 = 58,
    CrabAtk1 = 59,
    CrabAtk2 = 60,
    DiggerAtk1 = 61,
    BlobberAtk1 = 62,
    SpiderAtk1 = 63,
    SpiderlingAtk1 = 64,
    BlobAtk1 = 65,
    // -- Passives (no simulation needed) --
    PassiveElectric = 66,
    PassiveFlameImmune = 67,
    PassiveLeech = 68,
    PassiveFriendlyFire = 69,
    PassiveBoosters = 70,
    PassiveDefenses = 71,
    PassiveMassRepair = 72,
    PassiveBurrows = 73,
    PassivePsions = 74,
    PassiveAmmo = 75,
    PassiveHealingSmoke = 76,
    PassiveFireBoost = 77,
    PassiveForceAmp = 78,
    // Sentinel
    Repair = 79,
}

pub const WEAPON_COUNT: usize = 80;

// ── Weapon definitions table ─────────────────────────────────────────────────
// Indexed by WId as u8

pub static WEAPONS: [WeaponDef; WEAPON_COUNT] = {
    let mut w = [DEF; WEAPON_COUNT];

    // 0: None — no weapon
    // Already DEF

    // 1: Prime_Punchmech — Titan Fist
    w[1] = WeaponDef { weapon_type: WeaponType::Melee, damage: 2, push: PushDir::Forward, flags: C, ..DEF };
    // 2: Prime_Lightning — Chain Whip
    w[2] = WeaponDef { weapon_type: WeaponType::Melee, damage: 2, flags: f(WeaponFlags::CHAIN.bits() | WeaponFlags::TARGETS_ALLIES.bits()), ..DEF };
    // 3: Prime_Lasermech — Burst Beam
    w[3] = WeaponDef { weapon_type: WeaponType::Laser, damage: 3, range_max: 0, flags: f(WeaponFlags::TARGETS_ALLIES.bits()), ..DEF };
    // 4: Prime_ShieldBash — Shield Bash
    w[4] = WeaponDef { weapon_type: WeaponType::Melee, damage: 2, push: PushDir::Flip, flags: C, ..DEF };
    // 5: Prime_Shift — Vice Fist
    w[5] = WeaponDef { weapon_type: WeaponType::Melee, damage: 1, push: PushDir::Backward, flags: f(WeaponFlags::TARGETS_ALLIES.bits()), ..DEF };
    // 6: Prime_Flamethrower — Flamethrower
    w[6] = WeaponDef { weapon_type: WeaponType::Melee, damage: 0, push: PushDir::Forward, flags: f(WeaponFlags::FIRE.bits()), ..DEF };
    // 7: Prime_Areablast — Area Blast
    w[7] = WeaponDef { weapon_type: WeaponType::SelfAoe, damage: 1, push: PushDir::Outward, flags: f_nc(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 8: Prime_Leap — Hydraulic Legs
    w[8] = WeaponDef { weapon_type: WeaponType::Leap, damage: 1, push: PushDir::Outward, self_damage: 1, range_max: 7, flags: f_nc(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 9: Prime_Spear — Spear
    w[9] = WeaponDef { weapon_type: WeaponType::Melee, damage: 2, push: PushDir::Forward, flags: C, ..DEF };
    // 10: Prime_Rockmech — Rock Throw
    w[10] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 2, range_max: 0, flags: C, ..DEF };
    // 11: Prime_RocketPunch — Rocket Fist
    w[11] = WeaponDef { weapon_type: WeaponType::Melee, damage: 2, push: PushDir::Forward, flags: f(WeaponFlags::PUSH_SELF.bits()), ..DEF };
    // 12: Prime_RightHook — Right Hook
    w[12] = WeaponDef { weapon_type: WeaponType::Melee, damage: 2, push: PushDir::Perpendicular, flags: C, ..DEF };
    // 13: Prime_SpinFist — Spin Fist
    w[13] = WeaponDef { weapon_type: WeaponType::SelfAoe, damage: 2, push: PushDir::Perpendicular, self_damage: 1, flags: f_nc(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 14: Prime_Sword — Sword
    w[14] = WeaponDef { weapon_type: WeaponType::Melee, damage: 2, push: PushDir::Forward, limited: 1, flags: f(WeaponFlags::AOE_PERP.bits()), ..DEF };
    // 15: Prime_Smash — Ground Smash
    w[15] = WeaponDef { weapon_type: WeaponType::Melee, damage: 4, push: PushDir::Outward, limited: 1, flags: f(WeaponFlags::AOE_PERP.bits()), ..DEF };

    // 16: Brute_Tankmech — Taurus Cannon
    w[16] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 1, push: PushDir::Forward, range_max: 0, flags: C, ..DEF };
    // 17: Brute_Jetmech — Aerial Bombs
    w[17] = WeaponDef { weapon_type: WeaponType::Leap, damage: 1, range_min: 2, range_max: 2, flags: f_nc(WeaponFlags::SMOKE.bits()), ..DEF };
    // 18: Brute_Mirrorshot — Mirror Shot
    w[18] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 1, push: PushDir::Forward, range_max: 0, flags: f(WeaponFlags::AOE_BEHIND.bits()), ..DEF };
    // 19: Brute_Beetle — Ramming Engines
    w[19] = WeaponDef { weapon_type: WeaponType::Charge, damage: 2, push: PushDir::Forward, self_damage: 1, range_max: 0,
        flags: f(WeaponFlags::CHARGE.bits() | WeaponFlags::FLYING_CHARGE.bits()), ..DEF };
    // 20: Brute_Grapple — Vice Fist (Pull)
    w[20] = WeaponDef { weapon_type: WeaponType::Pull, damage: 0, push: PushDir::Inward, range_max: 0, flags: C, ..DEF };
    // 21: Brute_Unstable — Unstable Cannon
    w[21] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 2, push: PushDir::Forward, self_damage: 1, range_max: 0,
        flags: f(WeaponFlags::PUSH_SELF.bits()), ..DEF };
    // 22: Brute_PhaseShot — Phase Cannon
    w[22] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 1, push: PushDir::Forward, range_max: 0,
        flags: f(WeaponFlags::PHASE.bits()), ..DEF };
    // 23: Brute_Shrapnel — Defensive Shrapnel
    w[23] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 0, push: PushDir::Outward, range_max: 0,
        flags: f(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 24: Brute_Heavyrocket — Heavy Rocket
    w[24] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 3, push: PushDir::Outward, range_max: 0, limited: 1,
        flags: f(WeaponFlags::AOE_PERP.bits()), ..DEF };
    // 25: Brute_Sonic — Sonic Dash
    w[25] = WeaponDef { weapon_type: WeaponType::Charge, damage: 0, push: PushDir::Perpendicular, range_max: 0,
        flags: f(WeaponFlags::CHARGE.bits()), ..DEF };
    // 26: Brute_Shockblast — Shock Cannon
    w[26] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 1, push: PushDir::Backward, range_max: 0,
        flags: f(WeaponFlags::AOE_BEHIND.bits()), ..DEF };
    // 27: Brute_Sniper — Sniper Rifle
    w[27] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 2, push: PushDir::Forward, range_max: 0, flags: C, ..DEF };
    // 28: Brute_Splitshot — Split Shot
    w[28] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 2, push: PushDir::Outward, range_max: 0, limited: 1,
        flags: f(WeaponFlags::AOE_PERP.bits()), ..DEF };
    // 29: Brute_Bombrun — Bombing Run
    w[29] = WeaponDef { weapon_type: WeaponType::Leap, damage: 1, range_min: 2, range_max: 8, limited: 1, flags: f_nc(0), ..DEF };

    // 30: Archive_ArtShot — Old Earth Artillery
    w[30] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 2, range_min: 2,
        flags: f(WeaponFlags::AOE_BEHIND.bits()), ..DEF };

    // 31: Ranged_Artillerymech — Artemis Artillery
    w[31] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 1, push: PushDir::Outward, range_min: 2,
        flags: f(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 32: Ranged_Rockthrow — Rock Launcher
    w[32] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 2, push: PushDir::Perpendicular, range_min: 2, flags: C, ..DEF };
    // 33: Ranged_Defensestrike — Cluster Artillery
    w[33] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 0, damage_outer: 1, push: PushDir::Outward, range_min: 2,
        flags: f_nc(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 34: Ranged_Rocket — Rocket Artillery
    w[34] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 2, push: PushDir::Forward, range_min: 2, flags: C, ..DEF };
    // 35: Ranged_Ignite — Ignite
    w[35] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 0, push: PushDir::Outward, range_min: 2,
        flags: f(WeaponFlags::FIRE.bits() | WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 36: Ranged_Ice — Cryo-Launcher
    w[36] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 0, range_min: 2,
        flags: f(WeaponFlags::FREEZE.bits()), ..DEF };
    // 37: Ranged_ScatterShot — Scatter Shot
    w[37] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 1, push: PushDir::Forward, range_min: 2, flags: C, ..DEF };
    // 38: Ranged_BackShot — Back Shot
    w[38] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 1, push: PushDir::Backward, range_min: 2,
        flags: f(WeaponFlags::AOE_BEHIND.bits()), ..DEF };
    // 39: Ranged_Wide — Overpower
    w[39] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 2, range_min: 2, limited: 1,
        flags: f(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };

    // 40: Science_Pullmech — Attract Shot
    w[40] = WeaponDef { weapon_type: WeaponType::Pull, damage: 0, push: PushDir::Inward, range_max: 0, flags: C, ..DEF };
    // 41: Science_Gravwell — Grav Well
    w[41] = WeaponDef { weapon_type: WeaponType::Pull, damage: 0, push: PushDir::Inward, range_min: 2, flags: C, ..DEF };
    // 42: Science_Repulse — Repulse
    w[42] = WeaponDef { weapon_type: WeaponType::SelfAoe, damage: 0, push: PushDir::Outward, flags: f_nc(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 43: Science_Swap — Teleporter
    w[43] = WeaponDef { weapon_type: WeaponType::Swap, damage: 0, range_max: 1, flags: C, ..DEF };
    // 44: Science_AcidShot — Acid Projector
    w[44] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 0, push: PushDir::Forward, range_max: 0,
        flags: f(WeaponFlags::ACID.bits()), ..DEF };
    // 45: Science_Shield — Shield Projector
    w[45] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 0, range_min: 2, limited: 2,
        flags: f(WeaponFlags::SHIELD.bits()), ..DEF };
    // 46: Science_Confuse — Confusion Ray
    w[46] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 0, push: PushDir::Flip, range_max: 0, flags: C, ..DEF };

    // -- Enemy Weapons --
    // 47: ScorpionAtk1
    w[47] = WeaponDef { weapon_type: WeaponType::Melee, damage: 1, flags: f(WeaponFlags::WEB.bits()), ..DEF };
    // 48: ScorpionAtk2
    w[48] = WeaponDef { weapon_type: WeaponType::Melee, damage: 3, flags: f(WeaponFlags::WEB.bits()), ..DEF };
    // 49: HornetAtk1
    w[49] = WeaponDef { weapon_type: WeaponType::Melee, damage: 1, flags: C, ..DEF };
    // 50: HornetAtk2 — Alpha Hornet (aoe_behind!)
    w[50] = WeaponDef { weapon_type: WeaponType::Melee, damage: 2, flags: f(WeaponFlags::AOE_BEHIND.bits()), ..DEF };
    // 51: LeaperAtk1
    w[51] = WeaponDef { weapon_type: WeaponType::Melee, damage: 3, flags: f(WeaponFlags::WEB.bits()), ..DEF };
    // 52: BeetleAtk1
    w[52] = WeaponDef { weapon_type: WeaponType::Charge, damage: 1, flags: f(WeaponFlags::CHARGE.bits()), ..DEF };
    // 53: BeetleAtk2
    w[53] = WeaponDef { weapon_type: WeaponType::Charge, damage: 3, flags: f(WeaponFlags::CHARGE.bits()), ..DEF };
    // 54: FireflyAtk1
    w[54] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 1, range_max: 0, flags: C, ..DEF };
    // 55: FireflyAtk2
    w[55] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 3, range_max: 0, flags: C, ..DEF };
    // 56: CentipedeAtk1 — acid + aoe_perpendicular
    w[56] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 1, range_max: 0,
        flags: f(WeaponFlags::ACID.bits() | WeaponFlags::AOE_PERP.bits()), ..DEF };
    // 57: ScarabAtk1
    w[57] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 1, range_min: 2, flags: C, ..DEF };
    // 58: ScarabAtk2
    w[58] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 3, range_min: 2, flags: C, ..DEF };
    // 59: CrabAtk1
    w[59] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 1, range_min: 2, flags: C, ..DEF };
    // 60: CrabAtk2
    w[60] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 3, range_min: 2, flags: C, ..DEF };
    // 61: DiggerAtk1 — self_aoe, adjacent only
    w[61] = WeaponDef { weapon_type: WeaponType::SelfAoe, damage: 1, flags: f_nc(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 62: BlobberAtk1 — spawns Blob1
    w[62] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 0, flags: C, ..DEF };
    // 63: SpiderAtk1 — spawns WebbEgg1
    w[63] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 0, flags: C, ..DEF };
    // 64: SpiderlingAtk1
    w[64] = WeaponDef { weapon_type: WeaponType::Melee, damage: 1, flags: C, ..DEF };
    // 65: BlobAtk1 — self_aoe, center + adjacent
    w[65] = WeaponDef { weapon_type: WeaponType::SelfAoe, damage: 1, flags: f(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };

    // 66-78: Passive weapons — no simulation needed, all DEF
    // Already initialized as DEF

    // 79: Repair sentinel
    // Already DEF

    w
};

/// Look up weapon definition by WId.
#[inline]
pub fn weapon_def(id: WId) -> &'static WeaponDef {
    &WEAPONS[id as usize]
}

// ── String-to-WId mapping ────────────────────────────────────────────────────

pub fn wid_from_str(s: &str) -> WId {
    match s {
        "Prime_Punchmech" => WId::PrimePunchmech,
        "Prime_Lightning" => WId::PrimeLightning,
        "Prime_Lasermech" => WId::PrimeLasermech,
        "Prime_ShieldBash" => WId::PrimeShieldBash,
        "Prime_Shift" => WId::PrimeShift,
        "Prime_Flamethrower" => WId::PrimeFlamethrower,
        "Prime_Areablast" => WId::PrimeAreablast,
        "Prime_Leap" => WId::PrimeLeap,
        "Prime_Spear" => WId::PrimeSpear,
        "Prime_Rockmech" => WId::PrimeRockmech,
        "Prime_RocketPunch" => WId::PrimeRocketPunch,
        "Prime_RightHook" => WId::PrimeRightHook,
        "Prime_SpinFist" => WId::PrimeSpinFist,
        "Prime_Sword" => WId::PrimeSword,
        "Prime_Smash" => WId::PrimeSmash,
        "Brute_Tankmech" => WId::BruteTankmech,
        "Brute_Jetmech" => WId::BruteJetmech,
        "Brute_Mirrorshot" => WId::BruteMirrorshot,
        "Brute_Beetle" => WId::BruteBeetle,
        "Brute_Grapple" => WId::BruteGrapple,
        "Brute_Unstable" => WId::BruteUnstable,
        "Brute_PhaseShot" => WId::BrutePhaseShot,
        "Brute_Shrapnel" => WId::BruteShrapnel,
        "Brute_Heavyrocket" => WId::BruteHeavyrocket,
        "Brute_Sonic" => WId::BruteSonic,
        "Brute_Shockblast" => WId::BruteShockblast,
        "Brute_Sniper" => WId::BruteSniper,
        "Brute_Splitshot" => WId::BruteSplitshot,
        "Brute_Bombrun" => WId::BruteBombrun,
        "Archive_ArtShot" => WId::ArchiveArtShot,
        "Ranged_Artillerymech" => WId::RangedArtillerymech,
        "Ranged_Rockthrow" => WId::RangedRockthrow,
        "Ranged_Defensestrike" => WId::RangedDefensestrike,
        "Ranged_Rocket" => WId::RangedRocket,
        "Ranged_Ignite" => WId::RangedIgnite,
        "Ranged_Ice" => WId::RangedIce,
        "Ranged_ScatterShot" => WId::RangedScatterShot,
        "Ranged_BackShot" => WId::RangedBackShot,
        "Ranged_Wide" => WId::RangedWide,
        "Science_Pullmech" => WId::SciencePullmech,
        "Science_Gravwell" => WId::ScienceGravwell,
        "Science_Repulse" => WId::ScienceRepulse,
        "Science_Swap" => WId::ScienceSwap,
        "Science_AcidShot" => WId::ScienceAcidShot,
        "Science_Shield" => WId::ScienceShield,
        "Science_Confuse" => WId::ScienceConfuse,
        "ScorpionAtk1" => WId::ScorpionAtk1,
        "ScorpionAtk2" => WId::ScorpionAtk2,
        "HornetAtk1" => WId::HornetAtk1,
        "HornetAtk2" => WId::HornetAtk2,
        "LeaperAtk1" => WId::LeaperAtk1,
        "BeetleAtk1" => WId::BeetleAtk1,
        "BeetleAtk2" => WId::BeetleAtk2,
        "FireflyAtk1" => WId::FireflyAtk1,
        "FireflyAtk2" => WId::FireflyAtk2,
        "CentipedeAtk1" => WId::CentipedeAtk1,
        "ScarabAtk1" => WId::ScarabAtk1,
        "ScarabAtk2" => WId::ScarabAtk2,
        "CrabAtk1" => WId::CrabAtk1,
        "CrabAtk2" => WId::CrabAtk2,
        "DiggerAtk1" => WId::DiggerAtk1,
        "BlobberAtk1" => WId::BlobberAtk1,
        "SpiderAtk1" => WId::SpiderAtk1,
        "SpiderlingAtk1" => WId::SpiderlingAtk1,
        "BlobAtk1" => WId::BlobAtk1,
        "Acid_Tank_Attack" => WId::ScorpionAtk1, // Reuse melee/1dmg — NPC controllable unit
        _ => WId::None,
    }
}

/// Get the internal string ID for a weapon (for Python bridge interop).
/// This is the reverse of wid_from_str() and matches the keys in Python's WEAPON_DEFS.
pub fn wid_to_str(id: WId) -> &'static str {
    match id {
        WId::None => "",
        WId::PrimePunchmech => "Prime_Punchmech",
        WId::PrimeLightning => "Prime_Lightning",
        WId::PrimeLasermech => "Prime_Lasermech",
        WId::PrimeShieldBash => "Prime_ShieldBash",
        WId::PrimeShift => "Prime_Shift",
        WId::PrimeFlamethrower => "Prime_Flamethrower",
        WId::PrimeAreablast => "Prime_Areablast",
        WId::PrimeLeap => "Prime_Leap",
        WId::PrimeSpear => "Prime_Spear",
        WId::PrimeRockmech => "Prime_Rockmech",
        WId::PrimeRocketPunch => "Prime_RocketPunch",
        WId::PrimeRightHook => "Prime_RightHook",
        WId::PrimeSpinFist => "Prime_SpinFist",
        WId::PrimeSword => "Prime_Sword",
        WId::PrimeSmash => "Prime_Smash",
        WId::BruteTankmech => "Brute_Tankmech",
        WId::BruteJetmech => "Brute_Jetmech",
        WId::BruteMirrorshot => "Brute_Mirrorshot",
        WId::BruteBeetle => "Brute_Beetle",
        WId::BruteGrapple => "Brute_Grapple",
        WId::BruteUnstable => "Brute_Unstable",
        WId::BrutePhaseShot => "Brute_PhaseShot",
        WId::BruteShrapnel => "Brute_Shrapnel",
        WId::BruteHeavyrocket => "Brute_Heavyrocket",
        WId::BruteSonic => "Brute_Sonic",
        WId::BruteShockblast => "Brute_Shockblast",
        WId::BruteSniper => "Brute_Sniper",
        WId::BruteSplitshot => "Brute_Splitshot",
        WId::BruteBombrun => "Brute_Bombrun",
        WId::ArchiveArtShot => "Archive_ArtShot",
        WId::RangedArtillerymech => "Ranged_Artillerymech",
        WId::RangedRockthrow => "Ranged_Rockthrow",
        WId::RangedDefensestrike => "Ranged_Defensestrike",
        WId::RangedRocket => "Ranged_Rocket",
        WId::RangedIgnite => "Ranged_Ignite",
        WId::RangedIce => "Ranged_Ice",
        WId::RangedScatterShot => "Ranged_ScatterShot",
        WId::RangedBackShot => "Ranged_BackShot",
        WId::RangedWide => "Ranged_Wide",
        WId::SciencePullmech => "Science_Pullmech",
        WId::ScienceGravwell => "Science_Gravwell",
        WId::ScienceRepulse => "Science_Repulse",
        WId::ScienceSwap => "Science_Swap",
        WId::ScienceAcidShot => "Science_AcidShot",
        WId::ScienceShield => "Science_Shield",
        WId::ScienceConfuse => "Science_Confuse",
        WId::ScorpionAtk1 => "ScorpionAtk1",
        WId::ScorpionAtk2 => "ScorpionAtk2",
        WId::HornetAtk1 => "HornetAtk1",
        WId::HornetAtk2 => "HornetAtk2",
        WId::LeaperAtk1 => "LeaperAtk1",
        WId::BeetleAtk1 => "BeetleAtk1",
        WId::BeetleAtk2 => "BeetleAtk2",
        WId::FireflyAtk1 => "FireflyAtk1",
        WId::FireflyAtk2 => "FireflyAtk2",
        WId::CentipedeAtk1 => "CentipedeAtk1",
        WId::ScarabAtk1 => "ScarabAtk1",
        WId::ScarabAtk2 => "ScarabAtk2",
        WId::CrabAtk1 => "CrabAtk1",
        WId::CrabAtk2 => "CrabAtk2",
        WId::DiggerAtk1 => "DiggerAtk1",
        WId::BlobberAtk1 => "BlobberAtk1",
        WId::SpiderAtk1 => "SpiderAtk1",
        WId::SpiderlingAtk1 => "SpiderlingAtk1",
        WId::BlobAtk1 => "BlobAtk1",
        WId::Repair => "_REPAIR",
        _ => "",
    }
}

/// Get the display name for a weapon (for solution descriptions).
pub fn weapon_name(id: WId) -> &'static str {
    match id {
        WId::PrimePunchmech => "Titan Fist",
        WId::PrimeLightning => "Chain Whip",
        WId::PrimeLasermech => "Burst Beam",
        WId::PrimeShieldBash => "Shield Bash",
        WId::PrimeShift => "Vice Fist",
        WId::PrimeFlamethrower => "Flamethrower",
        WId::PrimeAreablast => "Area Blast",
        WId::PrimeLeap => "Hydraulic Legs",
        WId::PrimeSpear => "Spear",
        WId::PrimeRockmech => "Rock Throw",
        WId::PrimeRocketPunch => "Rocket Fist",
        WId::PrimeRightHook => "Right Hook",
        WId::PrimeSpinFist => "Spin Fist",
        WId::PrimeSword => "Sword",
        WId::PrimeSmash => "Ground Smash",
        WId::BruteTankmech => "Taurus Cannon",
        WId::BruteJetmech => "Aerial Bombs",
        WId::BruteMirrorshot => "Mirror Shot",
        WId::BruteBeetle => "Ramming Engines",
        WId::BruteGrapple => "Vice Fist",
        WId::BruteUnstable => "Unstable Cannon",
        WId::BrutePhaseShot => "Phase Cannon",
        WId::BruteShrapnel => "Defensive Shrapnel",
        WId::BruteHeavyrocket => "Heavy Rocket",
        WId::BruteSonic => "Sonic Dash",
        WId::BruteShockblast => "Shock Cannon",
        WId::BruteSniper => "Sniper Rifle",
        WId::BruteSplitshot => "Split Shot",
        WId::BruteBombrun => "Bombing Run",
        WId::ArchiveArtShot => "Old Earth Artillery",
        WId::RangedArtillerymech => "Artemis Artillery",
        WId::RangedRockthrow => "Rock Launcher",
        WId::RangedDefensestrike => "Cluster Artillery",
        WId::RangedRocket => "Rocket Artillery",
        WId::RangedIgnite => "Ignite",
        WId::RangedIce => "Cryo-Launcher",
        WId::RangedScatterShot => "Scatter Shot",
        WId::RangedBackShot => "Back Shot",
        WId::RangedWide => "Overpower",
        WId::SciencePullmech => "Attract Shot",
        WId::ScienceGravwell => "Grav Well",
        WId::ScienceRepulse => "Repulse",
        WId::ScienceSwap => "Teleporter",
        WId::ScienceAcidShot => "Acid Projector",
        WId::ScienceShield => "Shield Projector",
        WId::ScienceConfuse => "Confusion Ray",
        WId::Repair => "Repair",
        WId::ScorpionAtk1 => "Acid Tank Attack",  // reused for Acid_Tank_Attack
        _ => "Unknown",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_titan_fist() {
        let w = weapon_def(WId::PrimePunchmech);
        assert_eq!(w.weapon_type, WeaponType::Melee);
        assert_eq!(w.damage, 2);
        assert_eq!(w.push, PushDir::Forward);
    }

    #[test]
    fn test_taurus_cannon() {
        let w = weapon_def(WId::BruteTankmech);
        assert_eq!(w.weapon_type, WeaponType::Projectile);
        assert_eq!(w.damage, 1);
        assert_eq!(w.push, PushDir::Forward);
        assert_eq!(w.range_max, 0); // unlimited
    }

    #[test]
    fn test_artemis_artillery() {
        let w = weapon_def(WId::RangedArtillerymech);
        assert_eq!(w.weapon_type, WeaponType::Artillery);
        assert_eq!(w.damage, 1);
        assert_eq!(w.push, PushDir::Outward);
        assert!(w.aoe_adjacent());
        assert_eq!(w.range_min, 2);
    }

    #[test]
    fn test_alpha_hornet_has_aoe_behind() {
        let w = weapon_def(WId::HornetAtk2);
        assert!(w.aoe_behind());
        assert_eq!(w.damage, 2);
    }

    #[test]
    fn test_ramming_engines_flying_charge() {
        let w = weapon_def(WId::BruteBeetle);
        assert!(w.flying_charge());
        assert_eq!(w.self_damage, 1);
    }

    #[test]
    fn test_phase_cannon() {
        let w = weapon_def(WId::BrutePhaseShot);
        assert!(w.phase());
    }

    #[test]
    fn test_string_to_wid_roundtrip() {
        assert_eq!(wid_from_str("Prime_Punchmech"), WId::PrimePunchmech);
        assert_eq!(wid_from_str("Ranged_Artillerymech"), WId::RangedArtillerymech);
        assert_eq!(wid_from_str("unknown_weapon"), WId::None);
    }

    #[test]
    fn test_wid_to_str_roundtrip() {
        // Every wid_from_str input should roundtrip through wid_to_str
        let pairs = [
            ("Prime_Punchmech", WId::PrimePunchmech),
            ("Brute_Tankmech", WId::BruteTankmech),
            ("Ranged_Artillerymech", WId::RangedArtillerymech),
            ("Science_Pullmech", WId::SciencePullmech),
            ("ScorpionAtk1", WId::ScorpionAtk1),
            ("FireflyAtk1", WId::FireflyAtk1),
        ];
        for (s, wid) in pairs {
            assert_eq!(wid_from_str(s), wid, "wid_from_str({}) failed", s);
            assert_eq!(wid_to_str(wid), s, "wid_to_str({:?}) failed", wid);
        }
        // Repair maps to _REPAIR (Python convention)
        assert_eq!(wid_to_str(WId::Repair), "_REPAIR");
        // None maps to empty string
        assert_eq!(wid_to_str(WId::None), "");
    }

    #[test]
    fn test_all_active_weapons_have_valid_type() {
        for i in 1..=65 {
            let w = &WEAPONS[i];
            assert_ne!(w.weapon_type, WeaponType::Passive,
                "Weapon {} should not be passive (slots 66+ are passive)", i);
        }
    }
}
