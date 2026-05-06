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
        /// Weapon places a smoke tile directly behind the shooter (one tile
        /// opposite the attack direction, from the shooter's position).
        /// Ranged_Rocket (Rocket Artillery) is the only mech weapon with this
        /// behavior per in-game tooltip: "Fires a pushing artillery and creates
        /// Smoke behind the shooter." Mutually independent from SMOKE (which
        /// smokes the target tile).
        const SMOKE_BEHIND_SHOOTER = 1 << 17;
        /// Leap-weapon damage lands on the transit tile(s) along the cardinal
        /// flight path (strictly between source and landing), NOT on the 4
        /// cardinal neighbors of the landing tile. Jet_BombDrop (Aerial Bombs)
        /// expresses this via SMOKE + transit-damage in one; Brute_Bombrun
        /// (Bombing Run) tooltip reads "Leap over any distance dropping a bomb
        /// on each tile you pass" — per-transit damage but NO smoke. This flag
        /// lets Brute_Bombrun opt into transit-damage without gaining smoke.
        /// `sim_leap` applies transit-damage when SMOKE || DAMAGES_TRANSIT.
        const DAMAGES_TRANSIT = 1 << 18;
        /// Pull weapon drags target ALL THE WAY to the tile adjacent to the
        /// attacker (or until a blocker stops the pull early). Default Pull
        /// behavior is 1-tile (Science_Pullmech "Attraction Pulse"). Per wiki,
        /// Brute_Grapple "Grappling Hook" and Science_Gravwell "Grav Well"
        /// pull until adjacent — handled in `sim_pull_or_swap` by looping
        /// `apply_push` rather than calling it once.
        const FULL_PULL = 1 << 19;
        /// Projectile damage scales with shot distance: dealt damage =
        /// max(0, min(wdef.damage, tile_distance_from_shooter - 1)).
        /// Mirrors Brute_Sniper's Lua formula (weapons_brute.lua:969-991):
        ///     local damage = SpaceDamage(target, math.min(self.MaxDamage, dist), dir)
        /// where Lua's `dist` counter is initialized at 0 with the projectile
        /// pre-stepped one tile, so `dist` increments to (tile_distance - 1).
        /// Adjacent target → 0 damage; dist=2 → 1 damage; dist≥MaxDamage+1 →
        /// MaxDamage. `wdef.damage` plays the role of MaxDamage. Push still
        /// fires regardless of damage value.
        const DAMAGE_SCALES_WITH_DIST = 1 << 20;
        /// Queued damage at the queued target tile (p2) fires regardless of
        /// the attacker's current position. Mirrors Lua skills like
        /// `BlobBossAtk:GetSkillEffect` (scripts/missions/bosses/goo.lua:172-187)
        /// where `AddQueuedDamage(SpaceDamage(p2, 4))` is appended to the
        /// SkillEffect *before* the optional move; the engine evaluates the
        /// queued damage on the next enemy turn at p2 even if the boss has
        /// since been pushed/pulled out of adjacency. Used for goo bosses
        /// (BlobBoss / BlobBossMed / BlobBossSmall) — without this, pulling
        /// the boss with Grappling Hook silently nullifies a 4-damage
        /// building hit and the solver mispredicts grid_power loss.
        const QUEUED_DAMAGE_PERSISTS = 1 << 21;
        /// Weapon deals bonus damage to a target unit that is already on
        /// Fire at firing time. Mirrors Lua Prime_Flamethrower's two-stage
        /// damage: `Damage` (0 base) is dealt unconditionally, plus
        /// `FireDamage` (2) if the target tile's pawn `IsFire()` BEFORE the
        /// flame is applied. In-game tooltip: "Damage units already on
        /// Fire". `sim_melee` adds 2 to the target-tile damage roll when
        /// this flag is set and the unit at the target tile is on fire.
        /// Currently only Prime_Flamethrower; upgraded multi-tile mode
        /// (PathSize=2/3) is not modelled — base equip uses PathSize=1.
        const BURNS_FIRE_TARGETS = 1 << 22;
        /// Zero-damage adjacent artillery pushes do not deal edge-bump damage
        /// when the destination is off-board. Confirmed for Vulcan Artillery.
        const NO_EDGE_BUMP_ADJACENT_PUSH = 1 << 23;
        /// Weapon lights the tile directly behind the shooter on fire.
        /// Ranged_Ignite_A (Vulcan Artillery Backburn upgrade) uses this;
        /// independent from FIRE, which still applies to the target tile.
        const FIRE_BEHIND_SHOOTER = 1 << 24;
        /// Gastropod/Burnbug hook projectile. The shot travels like a normal
        /// projectile to the first blocker, then either pulls a hit pawn toward
        /// the attacker or pulls the attacker toward an object.
        const PROJECTILE_GRAPPLE = 1 << 25;
        /// Artillery also damages every cardinal tile strictly between the
        /// shooter and target. Crab Leader's "Raining Expulsions" deals 2 to
        /// the target and 1 to the projectile path; normal Crab Artillery's
        /// extra tile is behind the target and remains `path_size`.
        const PATH_DAMAGE = 1 << 26;
        /// Direct weapon damage from this weapon does not reduce Grid Building
        /// HP. Used by Artemis Artillery's Buildings Immune upgrade; push/bump
        /// damage remains physical collision damage and is handled separately.
        const BUILDING_IMMUNE = 1 << 27;
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
    pub path_size: u8,   // tiles hit in line (1 = default, 2 = Crab dual artillery)
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
    pub fn smoke_behind_shooter(&self) -> bool { self.flags.contains(WeaponFlags::SMOKE_BEHIND_SHOOTER) }
    pub fn damages_transit(&self) -> bool { self.flags.contains(WeaponFlags::DAMAGES_TRANSIT) }
    pub fn full_pull(&self) -> bool { self.flags.contains(WeaponFlags::FULL_PULL) }
    pub fn damage_scales_with_dist(&self) -> bool { self.flags.contains(WeaponFlags::DAMAGE_SCALES_WITH_DIST) }
    pub fn queued_damage_persists(&self) -> bool { self.flags.contains(WeaponFlags::QUEUED_DAMAGE_PERSISTS) }
    pub fn burns_fire_targets(&self) -> bool { self.flags.contains(WeaponFlags::BURNS_FIRE_TARGETS) }
    pub fn no_edge_bump_adjacent_push(&self) -> bool { self.flags.contains(WeaponFlags::NO_EDGE_BUMP_ADJACENT_PUSH) }
    pub fn fire_behind_shooter(&self) -> bool { self.flags.contains(WeaponFlags::FIRE_BEHIND_SHOOTER) }
    pub fn projectile_grapple(&self) -> bool { self.flags.contains(WeaponFlags::PROJECTILE_GRAPPLE) }
    pub fn path_damage(&self) -> bool { self.flags.contains(WeaponFlags::PATH_DAMAGE) }
    pub fn building_immune(&self) -> bool { self.flags.contains(WeaponFlags::BUILDING_IMMUNE) }
}

/// Default weapon def (no-op).
const DEF: WeaponDef = WeaponDef {
    weapon_type: WeaponType::Melee,
    damage: 0, damage_outer: 0,
    push: PushDir::None,
    self_damage: 0,
    range_min: 1, range_max: 1,
    limited: 0,
    path_size: 1,
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
    // -- Advanced Edition Enemy Weapons --
    BouncerAtk1 = 66,
    BouncerAtk2 = 67,
    MothAtk1 = 68,
    MothAtk2 = 69,
    MosquitoAtk1 = 70,
    MosquitoAtk2 = 71,
    BurnbugAtk1 = 72,
    BurnbugAtk2 = 73,
    SnowtankAtk1 = 74,
    SnowartAtk1 = 75,
    SnowartAtk2 = 76,
    LeaperAtk2 = 77,
    CentipedeAtk2 = 78,
    DiggerAtk2 = 79,
    BlobberAtk2 = 80,
    SpiderAtk2 = 81,
    BurrowerAtk1 = 82,
    BurrowerAtk2 = 83,
    GastropodAtk1 = 84,
    GastropodAtk2 = 85,
    StarfishAtk1 = 86,
    StarfishAtk2 = 87,
    TumblebugAtk1 = 88,
    TumblebugAtk2 = 89,
    PlasmodiaAtk1 = 90,
    PlasmodiaAtk2 = 91,
    FireflyAtkB = 92,
    // -- Passives (no simulation needed) --
    PassiveElectric = 93,
    PassiveFlameImmune = 94,
    PassiveLeech = 95,
    PassiveFriendlyFire = 96,
    PassiveBoosters = 97,
    PassiveDefenses = 98,
    PassiveMassRepair = 99,
    PassiveBurrows = 100,
    PassivePsions = 101,
    PassiveAmmo = 102,
    PassiveHealingSmoke = 103,
    PassiveFireBoost = 104,
    PassiveForceAmp = 105,
    // Sentinel
    Repair = 106,
    // -- Boss weapons --
    /// Scorpion Leader's "Massive Spinneret": hits all 4 cardinal adjacent
    /// tiles for 2 damage, pushes outward, webs each target. Implemented as
    /// SelfAoe with push=Outward + WEB flag.
    ScorpionAtkB = 107,
    // -- Pinnacle Robotics additional bot weapons --
    /// Cannon-Mech's "Cannon 8R Mark II": projectile, 3 damage, sets target on fire.
    SnowtankAtk2 = 108,
    /// Laser-Bot's "BKR Beam Mark I": piercing laser, 2 damage (decays to 1).
    SnowlaserAtk1 = 109,
    /// Laser-Mech's "BKR Beam Mark II": piercing laser, 4 damage (decays to 1).
    SnowlaserAtk2 = 110,
    /// Hornet Leader's "Super Stinger": stab three tiles in a line, 2 damage each.
    HornetAtkB = 111,
    /// Beetle Leader's "Flaming Abdomen": charges in a line, 3 damage + push
    /// to target, lights every passed tile on Fire (final resting tile
    /// excluded per wiki).
    BeetleAtkB = 112,
    // -- Any-class / support weapons --
    /// Repair Drop: ZONE_ALL heal. Heals every TEAM_PLAYER pawn to full HP,
    /// clears fire/acid/frozen, revives disabled mechs. Single-use.
    SupportRepair = 113,
    /// Alpha Blob's Unstable Guts: self_aoe, 2 damage to center + 4 cardinal adjacent.
    /// Inner damage is DAMAGE_DEATH in-game (kills the Blob) — we represent as 2 since
    /// Blob HP is always 1; effect is identical.
    BlobAtk2 = 114,

    /// A.C.I.D. Cannon — "Any Class Weapon" on the A.C.I.D. Tank NPC
    /// deployable. 0-damage cardinal projectile (infinite range, first
    /// blocker is the target) that applies A.C.I.D. to the hit unit. Base
    /// has NO push — the Push upgrade (1 core) adds 1-tile forward push
    /// but upgrade flags aren't tracked yet. Distinct from Science_AcidShot
    /// (Nano Mech's A.C.I.D. Projector) which has built-in forward push.
    AcidTankAtk = 115,
    /// BlobBoss "Goo Attack" (Large Goo): adjacent melee, 4 damage to the
    /// queued target. Per scripts/missions/bosses/goo.lua:172-187, the
    /// SkillEffect first calls `AddQueuedDamage(SpaceDamage(p2, 4))`, then
    /// optionally adds a move toward p2. The queued damage is registered
    /// before any move and fires next enemy turn regardless of the boss's
    /// current position — confirmed in m13_turn_04 where WallMech's
    /// Grappling Hook pulled BlobBoss D6→E6 and the queued D5 hit still
    /// landed (4 dmg → 2-HP Corp Tower destroyed → grid 2→0).
    BlobBossAtk = 116,
    /// BlobBossMed "Goo Attack" (Medium Goo): same queued-damage pattern
    /// as BlobBossAtk per goo.lua:189-197 (`BlobBossAtkMed = BlobBossAtk:new{...}`).
    BlobBossAtkMed = 117,
    /// BlobBossSmall "Goo Attack" (Small Goo): same queued-damage pattern
    /// as BlobBossAtk per goo.lua:198-206 (`BlobBossAtkSmall = BlobBossAtk:new{...}`).
    BlobBossAtkSmall = 118,

    /// Bot Leader (BotBoss) — Vk8 Rockets Mark III: 3-tile artillery T-pattern,
    /// 2 damage to target + both perpendicular tiles. No push.
    /// Per `scripts/missions/bosses/bot.lua:67`, `SnowBossAtk = SnowartAtk1:new{Damage = 2}`,
    /// inheriting the 3-tile pattern from `SnowartAtk1:GetSkillEffect`
    /// (weapons_snow.lua:120-135) which damages p2 + p2+(dir+1)%4 + p2+(dir-1)%4.
    SnowBossAtk = 119,
    /// Bot Leader Mk2 (BotBoss2) — Vk8 Rockets Mark IV: same 3-tile T-pattern,
    /// 4 damage. Per `bot.lua:79`, `SnowBossAtk2 = SnowartAtk1:new{Damage = 4}`.
    SnowBossAtk2 = 120,
    /// Bot Leader's "Self-Repairing" passive — `BossHeal = SelfTarget:new{...}`
    /// per `bot.lua:28-41`. When the boss is damaged at end of player turn, it
    /// telegraphs BossHeal instead of SnowBossAtk (decided by `BotBoss:GetWeapon()`
    /// returning skill index 2 vs 1 via `Pawn:IsDamaged()`). On the resolving
    /// enemy turn the SkillEffect:
    ///   • applies Shield to self IMMEDIATELY (`AddDamage` with iShield=1),
    ///   • queues +5 HP + remove-shield for the FOLLOWING enemy turn
    ///     (`AddQueuedDamage` with damage=-5 and iShield=-1).
    /// This sim implements the immediate self-shield (sim v31). The queued
    /// next-turn heal is outside the 1-turn horizon — see lib.rs sim v31 notes
    /// for the design rationale.
    BossHeal = 121,
    /// Freeze Cannon — Freeze_Tank (Pinnacle Robotics friendly NPC) skill.
    /// Per `scripts/missions/snow/snow_helper.lua:16-31`,
    /// `Pinnacle_FreezeTank = TankDefault:new{ Damage=0, Push=0, Freeze=1 }`.
    /// TankDefault inherits `Range = RANGE_PROJECTILE` (cardinal projectile,
    /// hits first blocker), so this is a 0-damage projectile that freezes
    /// the target. Used by the Freeze Tank to defend against enemies on
    /// Mission_FreezeBots ("Pinnacle Garden"). Mirrors Filler_Pawn's
    /// Filler_Attack pattern (friendly NPC default weapon).
    PinnacleFreezeTank = 122,
    /// Burnbug Leader (BurnbugBoss / "Gastropod Leader") — Flaming Proboscis.
    /// Archive Inc Corp HQ finale boss. Per
    /// `scripts/advanced/bosses/burnbug.lua:28-38`,
    /// `BurnbugAtkB = BurnbugAtk1:new{ Damage = 3, BossFire = true, ... }`.
    /// Inherits the BurnbugAtk1 grapple SkillEffect from
    /// `scripts/advanced/ae_weapons_enemy.lua:261-309`: a cardinal projectile
    /// that walks toward p2 until it hits a PATH_PROJECTILE blocker, deals
    /// `Damage` to that tile, then either drags the hit pawn to the tile
    /// adjacent to the boss OR self-charges the boss to the obstacle if the
    /// blocker is impassable. We mirror the existing simplification used by
    /// `BurnbugAtk1` / `BurnbugAtk2` (Melee + FIRE) — a 1-tile melee with
    /// `Damage` and FIRE on the target. The boss-only `BossFire = true` adds
    /// fire to the 4 cardinal tiles around the boss itself when it fires
    /// (Lua loop at lines 278-285); this around-self fire trail is NOT
    /// modeled in sim v34 because no existing weapon can express
    /// "primary attack + around-self status" in one def. Out of scope and
    /// noted as a deferred improvement (the mech-on-fire damage from the
    /// trail is at most 1/turn while the mech is on a trail tile and is
    /// dwarfed by the boss's 3-dmg primary attack).
    BurnbugAtkB = 123,
    /// Wind Torrent (`Support_Wind`): AE any-class support weapon. Targeting
    /// uses four fixed 2x2 zones near the board edges; the clicked zone chooses
    /// one global push direction and applies `SpaceDamage(point, 0, dir)` to
    /// every pawn in scan order. Base weapon is single-use.
    SupportWind = 124,
    /// Vulcan Artillery with Backburn upgrade: base center fire + adjacent
    /// outward pushes, plus fire on the tile directly behind the shooter.
    RangedIgniteA = 125,
    /// Crab Leader's "Raining Expulsions": 2 damage artillery target plus 1
    /// damage to each tile in the projectile path before the target.
    CrabAtkB = 126,
    /// Artemis Artillery with Buildings Immune: same center damage and
    /// adjacent outward pushes, but direct damage to Grid Buildings is zero.
    RangedArtillerymechA = 127,
    /// Archive / deployable tank Stock Cannon: projectile, 0 damage, pushes
    /// the first blocker forward. Controllable friendly non-mech units use it.
    DeployTankShot = 128,
    /// Upgraded deployable tank Stock Cannon: same push, 2 direct damage.
    DeployTankShot2 = 129,
    /// Decoy Building Area Blast (Mission_Trapped): self-destructs, killing
    /// itself and every adjacent non-building tile.
    TrappedExplode = 130,
    /// Bouncer Leader's "Sweeping Horns": adjacent melee T-pattern, 2 damage
    /// and forward push on target plus the two perpendicular tiles, then the
    /// boss bounces backward.
    BouncerAtkB = 131,
    /// Archive Armored Train objective: moves forward two tiles and destroys
    /// blockers in the entered path. Simulated by enemy train-advance logic.
    ArmoredTrainMove = 132,
}

pub const WEAPON_COUNT: usize = 133;

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
    // 4: Prime_ShieldBash — Spartan Shield (passive self-effect).
    // Empirically does 0 damage and no push: bridge dispatches it with target
    // (255,255) = no-target sentinel, and every desync shows target alive +
    // attacker HP unchanged (see recordings/failure_db.jsonl). Kept as Melee so
    // adjacency constraints still hold, but effectively a no-op for enemies.
    w[4] = WeaponDef { weapon_type: WeaponType::Melee, damage: 0, push: PushDir::None, flags: C, ..DEF };
    // 5: Prime_Shift — Vice Fist (grab and toss target to tile behind attacker)
    w[5] = WeaponDef { weapon_type: WeaponType::Melee, damage: 1, push: PushDir::Throw, flags: f(WeaponFlags::TARGETS_ALLIES.bits()), ..DEF };
    // 6: Prime_Flamethrower — Flamethrower.
    // Lua weapons_prime.lua:653 — Damage=0, FireDamage=2, Push=1, PathSize=1
    // (base equip; +1 per A/B upgrade — not modelled). The target tile gets
    // Fire status and the end-of-line push; if the target's pawn is already
    // on Fire AT firing time, the tile's damage becomes 0+FireDamage=2 (per
    // BURNS_FIRE_TARGETS). In-game tooltip: "Push target tile and light
    // tiles on Fire. Damage units already on Fire."
    w[6] = WeaponDef { weapon_type: WeaponType::Melee, damage: 0, push: PushDir::Forward,
        flags: f(WeaponFlags::FIRE.bits() | WeaponFlags::BURNS_FIRE_TARGETS.bits()), ..DEF };
    // 7: Prime_Areablast — Area Blast
    w[7] = WeaponDef { weapon_type: WeaponType::SelfAoe, damage: 1, push: PushDir::Outward, flags: f_nc(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 8: Prime_Leap — Hydraulic Legs
    w[8] = WeaponDef { weapon_type: WeaponType::Leap, damage: 1, push: PushDir::Outward, self_damage: 1, range_max: 7, flags: f_nc(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 9: Prime_Spear — Spear
    // Lua scripts/weapons_prime.lua:792-846 (Range=2, PathSize=2). The spear
    // stabs EVERY tile from attacker forward to the targeted tile, taking
    // self.Damage on each (transit damage on tile 1 when firing at tile 2).
    // Only the FURTHEST tile (the target) receives the Forward push.
    // GetTargetArea enumerates tiles +1 and +2 in each cardinal direction,
    // breaking only at the board edge — units along the path do NOT stop
    // target enumeration, they just take the in-path damage.
    w[9] = WeaponDef { weapon_type: WeaponType::Melee, damage: 2, push: PushDir::Forward, range_max: 2, path_size: 2, flags: C, ..DEF };
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
    // 20: Brute_Grapple — Grappling Hook (Hook Mech, Blitzkrieg).
    // Per wiki: "Use a grapple to pull Mech towards objects, or units to the
    // Mech." Pulls the target ALL the way to the tile adjacent to the
    // attacker, or until a blocker stops the chain (in which case the target
    // bumps into the blocker). FULL_PULL flag distinguishes it from
    // Science_Pullmech (Attraction Pulse, 1-tile-only).
    //
    // No-pawn-at-target case (Lua weapons_brute.lua:374-385): when the
    // PATH_PROJECTILE blocker is a mountain or intact building, the mech
    // charges along the line and stops at `target - dir`. Handled in
    // sim_pull_or_swap's None-branch under the FULL_PULL guard.
    w[20] = WeaponDef { weapon_type: WeaponType::Pull, damage: 0, push: PushDir::Inward, range_max: 0,
        flags: f(WeaponFlags::FULL_PULL.bits()), ..DEF };
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
    // Lua scripts/weapons_brute.lua:969-991: damage = min(MaxDamage, dist),
    // where Lua's `dist` counter increments to (tile_distance - 1). With
    // MaxDamage=2: adjacent target → 0 dmg, dist=2 → 1 dmg, dist≥3 → 2 dmg.
    // Push still fires regardless. Distance-scaling is encoded via the
    // DAMAGE_SCALES_WITH_DIST flag and consumed in `sim_projectile`.
    w[27] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 2, push: PushDir::Forward, range_max: 0,
        flags: f(WeaponFlags::DAMAGE_SCALES_WITH_DIST.bits()), ..DEF };
    // 28: Brute_Splitshot — Split Shot
    w[28] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 2, push: PushDir::Outward, range_max: 0, limited: 1,
        flags: f(WeaponFlags::AOE_PERP.bits()), ..DEF };
    // 29: Brute_Bombrun — Bombing Run
    // Tooltip: "Leap over any distance dropping a bomb on each tile you pass."
    // Damage lands on every transit tile along the flight path, NOT on the
    // landing-adjacent tiles. Uses DAMAGES_TRANSIT (not SMOKE — Bombing Run
    // does not emit smoke).
    w[29] = WeaponDef { weapon_type: WeaponType::Leap, damage: 1, range_min: 2, range_max: 8, limited: 1,
        flags: f_nc(WeaponFlags::DAMAGES_TRANSIT.bits()), ..DEF };

    // 30: Archive_ArtShot — Old Earth Artillery
    w[30] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 2, range_min: 2,
        flags: f(WeaponFlags::AOE_BEHIND.bits()), ..DEF };

    // 31: Ranged_Artillerymech — Artemis Artillery
    w[31] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 1, push: PushDir::Outward, range_min: 2,
        flags: f(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 127: Ranged_Artillerymech_A — Artemis Artillery with Buildings Immune
    w[127] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 1, push: PushDir::Outward, range_min: 2,
        flags: f(WeaponFlags::AOE_ADJACENT.bits() | WeaponFlags::BUILDING_IMMUNE.bits()), ..DEF };
    // 128: Deploy_TankShot — Stock Cannon
    w[128] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 0, push: PushDir::Forward, range_max: 0,
        flags: C, ..DEF };
    // 129: Deploy_TankShot2 — upgraded Stock Cannon
    w[129] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 2, push: PushDir::Forward, range_max: 0,
        flags: C, ..DEF };
    // 130: Trapped_Explode — Decoy Building Area Blast.
    // Bespoke DAMAGE_DEATH semantics live in simulate.rs; this SelfAoe def gives
    // targeting/enumeration a single "click self" target.
    w[130] = WeaponDef { weapon_type: WeaponType::SelfAoe, damage: 1,
        flags: f(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 32: Ranged_Rockthrow — Rock Launcher
    w[32] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 2, push: PushDir::Perpendicular, range_min: 2, flags: C, ..DEF };
    // 33: Ranged_Defensestrike — Cluster Artillery
    w[33] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 1, damage_outer: 1, push: PushDir::Outward, range_min: 2,
        flags: f_nc(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 34: Ranged_Rocket — Rocket Artillery
    // Tooltip: "Fires a pushing artillery and creates Smoke behind the shooter."
    // Smoke lands ONE tile opposite the shot direction, at the shooter's row/col —
    // NOT on the target tile. Use SMOKE_BEHIND_SHOOTER (handled in sim_artillery),
    // not SMOKE (which would smoke the target tile).
    w[34] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 2, push: PushDir::Forward, range_min: 2,
        flags: f(WeaponFlags::SMOKE_BEHIND_SHOOTER.bits()), ..DEF };
    // 35: Ranged_Ignite — Ignite
    w[35] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 0, push: PushDir::Outward, range_min: 2,
        flags: f(WeaponFlags::FIRE.bits() | WeaponFlags::AOE_ADJACENT.bits() | WeaponFlags::NO_EDGE_BUMP_ADJACENT_PUSH.bits()), ..DEF };
    // 125: Ranged_Ignite_A — Ignite with Backburn
    w[125] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 0, push: PushDir::Outward, range_min: 2,
        flags: f(WeaponFlags::FIRE.bits() | WeaponFlags::AOE_ADJACENT.bits() | WeaponFlags::NO_EDGE_BUMP_ADJACENT_PUSH.bits() | WeaponFlags::FIRE_BEHIND_SHOOTER.bits()), ..DEF };
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
    // 41: Science_Gravwell — Grav Well (Gravity Mech, Steel Judoka).
    // range_max: 0 = unlimited (Pull fires axis-aligned any distance from range_min out).
    // Without this override, DEF's default range_max=1 makes the range (2..=1) empty
    // and Grav Well enumerates zero targets — solver would never fire it.
    //
    // Single-tile pull (NOT FULL_PULL). Per weapons_science.lua:115-124:
    //   local damage = SpaceDamage(p2, self.Damage, GetDirection(p1 - p2))
    //   ret:AddArtillery(damage,"effects/shot_pull_U.png")
    // SpaceDamage's third arg is a 1-tile push toward the mech; there is no
    // AddCharge / GetSimplePath multi-tile drag. Gravwell pulls the targeted
    // unit ONE tile toward the mech, period. Compare Brute_Grapple
    // (weapons_brute.lua:339-389) which DOES use AddCharge to drag all the
    // way — that's why Brute_Grapple has FULL_PULL and Gravwell does not.
    // The v20 reading of the wiki ("pulls all the way") was wrong; the Lua
    // is authoritative. Surfaced by 2026-04-27 Pinnacle run desyncs (m13 t03
    // and many earlier rows: predicted pull-distance was systematically too
    // large, often by N-1 tiles).
    w[41] = WeaponDef { weapon_type: WeaponType::Pull, damage: 0, push: PushDir::Inward, range_min: 2, range_max: 0,
        flags: C, ..DEF };
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
    // 59: CrabAtk1 — hits 2 tiles in line
    w[59] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 1, range_min: 2, path_size: 2, flags: C, ..DEF };
    // 60: CrabAtk2 — hits 2 tiles in line
    w[60] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 3, range_min: 2, path_size: 2, flags: C, ..DEF };
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

    // -- Advanced Edition Enemy Weapons --
    // 66: BouncerAtk1 — melee, 1 dmg, pushes target forward + pushes self backward
    w[66] = WeaponDef { weapon_type: WeaponType::Melee, damage: 1, push: PushDir::Forward,
        flags: f(WeaponFlags::PUSH_SELF.bits()), ..DEF };
    // 67: BouncerAtk2 — alpha, 3 dmg
    w[67] = WeaponDef { weapon_type: WeaponType::Melee, damage: 3, push: PushDir::Forward,
        flags: f(WeaponFlags::PUSH_SELF.bits()), ..DEF };
    // 68: MothAtk1 — artillery, 1 dmg, pushes target + pushes self backward (flying)
    w[68] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 1, push: PushDir::Forward, range_min: 2,
        flags: f(WeaponFlags::PUSH_SELF.bits()), ..DEF };
    // 69: MothAtk2 — alpha artillery, 3 dmg
    w[69] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 3, push: PushDir::Forward, range_min: 2,
        flags: f(WeaponFlags::PUSH_SELF.bits()), ..DEF };
    // 70: MosquitoAtk1 — melee, 1 dmg, applies smoke (flying)
    w[70] = WeaponDef { weapon_type: WeaponType::Melee, damage: 1,
        flags: f(WeaponFlags::SMOKE.bits()), ..DEF };
    // 71: MosquitoAtk2 — alpha melee, 3 dmg, applies smoke
    w[71] = WeaponDef { weapon_type: WeaponType::Melee, damage: 3,
        flags: f(WeaponFlags::SMOKE.bits()), ..DEF };
    // 72: BurnbugAtk1 — Gastropod Hooked Proboscis: projectile grapple, 1 dmg.
    w[72] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 1, range_max: 0,
        flags: f(WeaponFlags::PROJECTILE_GRAPPLE.bits()), ..DEF };
    // 73: BurnbugAtk2 — Alpha Gastropod Barbed Proboscis: projectile grapple, 3 dmg.
    w[73] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 3, range_max: 0,
        flags: f(WeaponFlags::PROJECTILE_GRAPPLE.bits()), ..DEF };
    // 74: SnowtankAtk1 — Pinnacle bot, melee, 1 dmg
    w[74] = WeaponDef { weapon_type: WeaponType::Melee, damage: 1, flags: C, ..DEF };
    // 75: SnowartAtk1 — Pinnacle bot, artillery, 1 dmg
    w[75] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 1, range_min: 2, flags: C, ..DEF };
    // 76: SnowartAtk2 — Pinnacle bot, alpha artillery, 3 dmg
    w[76] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 3, range_min: 2, flags: C, ..DEF };
    // 77: LeaperAtk2 — alpha leaper, 5 dmg, web
    w[77] = WeaponDef { weapon_type: WeaponType::Melee, damage: 5, flags: f(WeaponFlags::WEB.bits()), ..DEF };
    // 78: CentipedeAtk2 — alpha centipede, 2 dmg, acid + aoe_perp
    w[78] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 2, range_max: 0,
        flags: f(WeaponFlags::ACID.bits() | WeaponFlags::AOE_PERP.bits()), ..DEF };
    // 79: DiggerAtk2 — alpha digger, 2 dmg, self_aoe
    w[79] = WeaponDef { weapon_type: WeaponType::SelfAoe, damage: 2, flags: f_nc(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };
    // 80: BlobberAtk2 — alpha blobber, spawns alpha blob
    w[80] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 0, flags: C, ..DEF };
    // 81: SpiderAtk2 — alpha spider, spawns eggs
    w[81] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 0, flags: C, ..DEF };
    // 82: BurrowerAtk1 — melee, 1 dmg, hits 3 tiles in a row
    w[82] = WeaponDef { weapon_type: WeaponType::Melee, damage: 1, path_size: 3, flags: C, ..DEF };
    // 83: BurrowerAtk2 — alpha burrower, 2 dmg
    w[83] = WeaponDef { weapon_type: WeaponType::Melee, damage: 2, path_size: 3, flags: C, ..DEF };
    // 84: GastropodAtk1 — ranged grapple, 1 dmg
    w[84] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 1, range_max: 0,
        flags: f(WeaponFlags::PROJECTILE_GRAPPLE.bits()), ..DEF };
    // 85: GastropodAtk2 — alpha ranged grapple, 3 dmg
    w[85] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 3, range_max: 0,
        flags: f(WeaponFlags::PROJECTILE_GRAPPLE.bits()), ..DEF };
    // 86: StarfishAtk1 — melee, 1 dmg (diagonal attack in-game, solver treats as melee)
    w[86] = WeaponDef { weapon_type: WeaponType::Melee, damage: 1, flags: C, ..DEF };
    // 87: StarfishAtk2 — alpha, 2 dmg
    w[87] = WeaponDef { weapon_type: WeaponType::Melee, damage: 2, flags: C, ..DEF };
    // 88: TumblebugAtk1 — melee, 1 dmg (creates boulder + attacks it)
    w[88] = WeaponDef { weapon_type: WeaponType::Melee, damage: 1, flags: C, ..DEF };
    // 89: TumblebugAtk2 — alpha, 3 dmg
    w[89] = WeaponDef { weapon_type: WeaponType::Melee, damage: 3, flags: C, ..DEF };
    // 90: PlasmodiaAtk1 — artillery, spawns spore
    w[90] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 0, flags: C, ..DEF };
    // 91: PlasmodiaAtk2 — alpha, spawns alpha spore
    w[91] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 0, flags: C, ..DEF };
    // 92: FireflyAtkB — Firefly Boss, projectile, 4 dmg
    w[92] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 4, range_max: 0, flags: C, ..DEF };

    // 107: ScorpionAtkB — Scorpion Leader's Massive Spinneret.
    // Self-AOE: 2 damage to all 4 cardinal adjacent tiles, pushes outward,
    // webs each target. Game Lua: scripts/missions/bosses/scorpion.lua
    // iterates DIR_START..DIR_END with AddQueuedMelee + AddGrapple "hold".
    // Needs AOE_ADJACENT for the 4-tile hit and WEB for the grapple;
    // f_nc() excludes the center tile (the boss itself).
    w[107] = WeaponDef {
        weapon_type: WeaponType::SelfAoe,
        damage: 2,
        push: PushDir::Outward,
        flags: f_nc(WeaponFlags::AOE_ADJACENT.bits() | WeaponFlags::WEB.bits()),
        ..DEF
    };

    // 108: SnowtankAtk2 — Cannon-Mech's Cannon 8R Mark II: projectile 3 dmg + fire
    w[108] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 3, range_max: 0,
        flags: f(WeaponFlags::FIRE.bits()), ..DEF };
    // 109: SnowlaserAtk1 — Laser-Bot's BKR Beam Mark I: piercing laser 2 dmg (decays to 1)
    w[109] = WeaponDef { weapon_type: WeaponType::Laser, damage: 2, range_max: 0, flags: C, ..DEF };
    // 110: SnowlaserAtk2 — Laser-Mech's BKR Beam Mark II: piercing laser 4 dmg (decays to 1)
    w[110] = WeaponDef { weapon_type: WeaponType::Laser, damage: 4, range_max: 0, flags: C, ..DEF };
    // 111: HornetAtkB — Hornet Leader's Super Stinger: 3 tiles in a line, 2 dmg each
    // Modeled as Artillery with range_min=1 + path_size=3. The artillery handler
    // damages target + path_size-1 extra tiles in attack direction, which matches
    // the game's 3-tile line (p2, p2+dir, p2+2*dir).
    w[111] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 2, range_min: 1, range_max: 0, path_size: 3, flags: C, ..DEF };
    // 112: BeetleAtkB — Beetle Leader's Flaming Abdomen: charges in a line,
    // 3 damage + forward push on target, sets every passed tile on fire
    // (final resting tile excluded). Charge handler reads CHARGE + FIRE
    // flags + push=Forward to apply these three effects.
    w[112] = WeaponDef { weapon_type: WeaponType::Charge, damage: 3, push: PushDir::Forward, range_max: 0,
        flags: f(WeaponFlags::CHARGE.bits() | WeaponFlags::FIRE.bits()), ..DEF };

    // 113: Support_Repair — Repair Drop (any-class, single-use). ZONE_ALL
    // heal of every TEAM_PLAYER pawn. Sim reads weapon_type=HealAll and
    // ignores damage/push/range. TARGETS_ALLIES flag is set so any future
    // "skip ally targets" logic treats it like Shaman buffs rather than a
    // hostile attack. BUILDING_DAMAGE is deliberately cleared.
    w[113] = WeaponDef {
        weapon_type: WeaponType::HealAll,
        damage: 0, damage_outer: 0,
        push: PushDir::None,
        self_damage: 0,
        range_min: 0, range_max: 0,
        limited: 1,
        path_size: 1,
        flags: f_nc(WeaponFlags::TARGETS_ALLIES.bits()),
    };

    // 114: BlobAtk2 — alpha blob explode, 2 dmg center + 4 cardinal adjacent
    w[114] = WeaponDef { weapon_type: WeaponType::SelfAoe, damage: 2, flags: f(WeaponFlags::AOE_ADJACENT.bits()), ..DEF };

    // 115: Acid_Tank_Attack — A.C.I.D. Cannon (NPC tank deployable).
    // 0-damage cardinal projectile, infinite range (range_max=0), applies
    // A.C.I.D. to hit target. Base has no push (upgrade adds Forward push,
    // not modelled until we track tank upgrade flags).
    w[115] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 0, push: PushDir::None, range_max: 0,
        flags: f(WeaponFlags::ACID.bits()), ..DEF };

    // 116-118: BlobBoss family — "Goo Attack". Single-tile melee at the
    // queued target with 4 damage. The Lua skill registers the queued
    // damage on p2 BEFORE any optional move (goo.lua:172-187), so the
    // damage fires regardless of whether the boss is adjacent at the time
    // of attack — modelled via the QUEUED_DAMAGE_PERSISTS flag.
    // Empirically all three sizes deal 4 damage (BlobBossAtk:GetSkillEffect
    // is shared by Med/Small via Skill:new{} inheritance).
    w[116] = WeaponDef { weapon_type: WeaponType::Melee, damage: 4, push: PushDir::None,
        flags: f(WeaponFlags::QUEUED_DAMAGE_PERSISTS.bits()), ..DEF };
    w[117] = WeaponDef { weapon_type: WeaponType::Melee, damage: 4, push: PushDir::None,
        flags: f(WeaponFlags::QUEUED_DAMAGE_PERSISTS.bits()), ..DEF };
    w[118] = WeaponDef { weapon_type: WeaponType::Melee, damage: 4, push: PushDir::None,
        flags: f(WeaponFlags::QUEUED_DAMAGE_PERSISTS.bits()), ..DEF };

    // 119: SnowBossAtk — Bot Leader's Vk8 Rockets Mark III. Per
    // `bot.lua:67`, `SnowBossAtk = SnowartAtk1:new{Damage = 2}`. The
    // SnowartAtk1 SkillEffect (weapons_snow.lua:120-135) damages 3 tiles in a
    // T-pattern around p2: p2 (the targeted tile, AOE_CENTER from helper `f`)
    // + the two perpendicular tiles to firing direction (AOE_PERP). Each tile
    // takes `Damage` (2 here). No push, no status effects. range_min=2 so the
    // boss can't fire at adjacent tiles.
    w[119] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 2, damage_outer: 2,
        range_min: 2, flags: f(WeaponFlags::AOE_PERP.bits()), ..DEF };
    // 120: SnowBossAtk2 — Bot Leader Mk2's Vk8 Rockets Mark IV. Per
    // `bot.lua:79`, `SnowBossAtk2 = SnowartAtk1:new{Damage = 4}`. Same shape
    // as SnowBossAtk, just 4 damage instead of 2.
    w[120] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 4, damage_outer: 4,
        range_min: 2, flags: f(WeaponFlags::AOE_PERP.bits()), ..DEF };
    // 121: BossHeal — Bot Leader's Self-Repairing skill. Per `bot.lua:28-41`,
    // `BossHeal = SelfTarget:new{Name = "Boss Heal"}` with a SkillEffect that
    // applies Shield (iShield=1) immediately to p1 (=self) AND queues a -5
    // damage / iShield=-1 (heal 5 + remove shield) for the FOLLOWING enemy
    // turn. Modeled as a no-damage SelfAoe with only AOE_CENTER + SHIELD —
    // the enemy-phase dispatch path special-cases BotBoss/BotBoss2 firing
    // BossHeal (queued_target == self) to call `apply_weapon_status` on the
    // boss's own tile, which sets the SHIELD flag. The next-turn heal is
    // outside the 1-turn solver horizon and is intentionally NOT simulated;
    // see lib.rs sim v31 notes.
    w[121] = WeaponDef { weapon_type: WeaponType::SelfAoe, damage: 0, push: PushDir::None,
        flags: f_nc(WeaponFlags::SHIELD.bits()), ..DEF };

    // 122: Pinnacle_FreezeTank — Freeze Cannon. Per
    // `scripts/missions/snow/snow_helper.lua:16-31`, a TankDefault projectile
    // (Range=RANGE_PROJECTILE, fires axis-aligned, hits first blocker) with
    // Damage=0, Push=0, Freeze=1. Friendly NPC defensive weapon that freezes
    // the target without damaging it. range_max=0 (unlimited — projectile
    // travels to first blocker). No self-freeze (that's a RangedIce-only
    // hardcode in `sim_projectile`).
    w[122] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 0, push: PushDir::None, range_max: 0,
        flags: f(WeaponFlags::FREEZE.bits()), ..DEF };

    // 123: BurnbugAtkB — Burnbug Leader's Flaming Proboscis. Per
    // `scripts/advanced/bosses/burnbug.lua:28-38`,
    // `BurnbugAtkB = BurnbugAtk1:new{ Damage = 3, BossFire = true, ... }`.
    // The cardinal-line grapple is modeled via PROJECTILE_GRAPPLE. The
    // `BossFire` around-self fire trail (4 cardinal tiles ignited around
    // the boss when it fires) is still intentionally not modeled here; see
    // WId::BurnbugAtkB doc comment for rationale.
    w[123] = WeaponDef { weapon_type: WeaponType::Projectile, damage: 3, range_max: 0,
        flags: f(WeaponFlags::PROJECTILE_GRAPPLE.bits()), ..DEF };

    // 124: Support_Wind — Wind Torrent. Per scripts/weapons_support.lua:434-537:
    // ZoneTargeting=ZONE_CUSTOM with fixed edge-zone targets; clicked zone sets
    // DIR_LEFT/RIGHT/UP/DOWN, then every current pawn receives zero damage plus
    // a directional push in Lua scan order. No building damage except via bump.
    w[124] = WeaponDef {
        weapon_type: WeaponType::GlobalPush,
        damage: 0, damage_outer: 0,
        push: PushDir::Forward,
        self_damage: 0,
        range_min: 0, range_max: 0,
        limited: 1,
        path_size: 1,
        flags: f_nc(WeaponFlags::TARGETS_ALLIES.bits()),
    };

    // 126: CrabAtkB — Crab Leader's Raining Expulsions. Per AE boss tooltip:
    // 2 damage to the artillery target and 1 damage to every tile in the
    // projectile path before that target.
    w[126] = WeaponDef { weapon_type: WeaponType::Artillery, damage: 2, damage_outer: 1,
        range_min: 2, flags: f(WeaponFlags::PATH_DAMAGE.bits()), ..DEF };

    // 131: BouncerAtkB — Bouncer Leader's Sweeping Horns. Per
    // scripts/advanced/bosses/bouncer.lua:46-58: target tile + two
    // perpendicular side tiles take 2 damage and PushDir::Forward, while the
    // boss receives a zero-damage push backward.
    w[131] = WeaponDef { weapon_type: WeaponType::Melee, damage: 2, push: PushDir::Forward,
        flags: f(WeaponFlags::PUSH_SELF.bits() | WeaponFlags::AOE_PERP.bits()), ..DEF };

    // 93-105: Passive weapons — no simulation needed, all DEF
    // Already initialized as DEF

    // 106: Repair sentinel
    // Already DEF

    w
};

/// Look up weapon definition by WId.
#[inline]
pub fn weapon_def(id: WId) -> &'static WeaponDef {
    &WEAPONS[id as usize]
}

// ── Runtime weapon-def overrides ─────────────────────────────────────────────
//
// Compile-time `WEAPONS` is the default table. The Phase 3 self-healing loop
// (see docs/self_healing_loop_design.md) may apply per-field patches to a
// cloned table so solver behaviour can be corrected between solves without a
// Rust rebuild. Production call sites thread `&WeaponTable` through the search
// — when no overrides are active they receive `&WEAPONS` directly (no alloc).

pub type WeaponTable = [WeaponDef; WEAPON_COUNT];

/// Representative target tiles for Support_Wind's four custom target zones.
/// Lua accepts any tile in each 2x2 zone; one per direction keeps search small.
pub const SUPPORT_WIND_TARGETS: [(u8, u8); 4] = [
    (1, 3), // left zone  -> DIR_LEFT
    (5, 3), // right zone -> DIR_RIGHT
    (3, 1), // upper zone -> DIR_UP
    (3, 5), // lower zone -> DIR_DOWN
];

/// Convert a Support_Wind target-zone tile into the Rust direction index.
///
/// Game Lua:
///   x in {1,2} => DIR_LEFT,  x in {5,6} => DIR_RIGHT,
///   y in {1,2} => DIR_UP,    y in {5,6} => DIR_DOWN.
/// Rust DIRS are [(0,1), (1,0), (0,-1), (-1,0)], so right/left are 1/3
/// and down/up are 0/2.
pub fn support_wind_dir_from_target(x: u8, y: u8) -> Option<usize> {
    if x == 1 || x == 2 {
        Some(3)
    } else if x == 5 || x == 6 {
        Some(1)
    } else if y == 1 || y == 2 {
        Some(2)
    } else if y == 5 || y == 6 {
        Some(0)
    } else {
        None
    }
}

/// Per-field patch applied on top of a base `WeaponDef`. Any `None` field is
/// left untouched; flag bits set in `flags_set` are OR'd in and bits set in
/// `flags_clear` are removed. Flags are deltas so two independent fixes on the
/// same weapon (e.g. one sets `FIRE`, another clears `SMOKE`) don't conflict.
#[derive(Clone, Debug, Default)]
pub struct PartialWeaponDef {
    pub weapon_type: Option<WeaponType>,
    pub damage: Option<u8>,
    pub damage_outer: Option<u8>,
    pub push: Option<PushDir>,
    pub self_damage: Option<u8>,
    pub range_min: Option<u8>,
    pub range_max: Option<u8>,
    pub limited: Option<u8>,
    pub path_size: Option<u8>,
    pub flags_set: WeaponFlags,
    pub flags_clear: WeaponFlags,
}

impl PartialWeaponDef {
    pub fn is_empty(&self) -> bool {
        self.weapon_type.is_none()
            && self.damage.is_none()
            && self.damage_outer.is_none()
            && self.push.is_none()
            && self.self_damage.is_none()
            && self.range_min.is_none()
            && self.range_max.is_none()
            && self.limited.is_none()
            && self.path_size.is_none()
            && self.flags_set.is_empty()
            && self.flags_clear.is_empty()
    }

    pub fn apply_to(&self, base: &mut WeaponDef) {
        if let Some(v) = self.weapon_type { base.weapon_type = v; }
        if let Some(v) = self.damage { base.damage = v; }
        if let Some(v) = self.damage_outer { base.damage_outer = v; }
        if let Some(v) = self.push { base.push = v; }
        if let Some(v) = self.self_damage { base.self_damage = v; }
        if let Some(v) = self.range_min { base.range_min = v; }
        if let Some(v) = self.range_max { base.range_max = v; }
        if let Some(v) = self.limited { base.limited = v; }
        if let Some(v) = self.path_size { base.path_size = v; }
        base.flags |= self.flags_set;
        base.flags.remove(self.flags_clear);
    }
}

/// Build a fresh `WeaponTable` with all `overrides` merged in, or return
/// `None` when the effective override set is empty so callers can pass
/// `&WEAPONS` directly and skip the allocation + copy.
pub fn build_overlay_table(overrides: &[(WId, PartialWeaponDef)]) -> Option<Box<WeaponTable>> {
    if overrides.iter().all(|(_, p)| p.is_empty()) {
        return None;
    }
    let mut table: Box<WeaponTable> = Box::new(WEAPONS);
    for (wid, patch) in overrides {
        if !patch.is_empty() {
            patch.apply_to(&mut table[*wid as usize]);
        }
    }
    Some(table)
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
        "Ranged_Artillerymech_A" => WId::RangedArtillerymechA,
        "RangedArtillerymechA" => WId::RangedArtillerymechA,
        "Deploy_TankShot" => WId::DeployTankShot,
        "DeployTankShot" => WId::DeployTankShot,
        "Deploy_TankShot2" => WId::DeployTankShot2,
        "DeployTankShot2" => WId::DeployTankShot2,
        "Trapped_Explode" => WId::TrappedExplode,
        "TrappedExplode" => WId::TrappedExplode,
        "Ranged_Rockthrow" => WId::RangedRockthrow,
        "Ranged_Defensestrike" => WId::RangedDefensestrike,
        "Ranged_Rocket" => WId::RangedRocket,
        "Ranged_Ignite" => WId::RangedIgnite,
        "Ranged_Ignite_A" => WId::RangedIgniteA,
        "RangedIgniteA" => WId::RangedIgniteA,
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
        "HornetAtkB" => WId::HornetAtkB,
        "BeetleAtkB" => WId::BeetleAtkB,
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
        "CrabAtkB" => WId::CrabAtkB,
        "DiggerAtk1" => WId::DiggerAtk1,
        "BlobberAtk1" => WId::BlobberAtk1,
        "SpiderAtk1" => WId::SpiderAtk1,
        "SpiderlingAtk1" => WId::SpiderlingAtk1,
        "BlobAtk1" => WId::BlobAtk1,
        "BouncerAtk1" => WId::BouncerAtk1,
        "BouncerAtk2" => WId::BouncerAtk2,
        "MothAtk1" => WId::MothAtk1,
        "MothAtk2" => WId::MothAtk2,
        "MosquitoAtk1" => WId::MosquitoAtk1,
        "MosquitoAtk2" => WId::MosquitoAtk2,
        "BurnbugAtk1" => WId::BurnbugAtk1,
        "BurnbugAtk2" => WId::BurnbugAtk2,
        "SnowtankAtk1" => WId::SnowtankAtk1,
        "SnowtankAtk2" => WId::SnowtankAtk2,
        "SnowlaserAtk1" => WId::SnowlaserAtk1,
        "SnowlaserAtk2" => WId::SnowlaserAtk2,
        "SnowartAtk1" => WId::SnowartAtk1,
        "SnowartAtk2" => WId::SnowartAtk2,
        "LeaperAtk2" => WId::LeaperAtk2,
        "CentipedeAtk2" => WId::CentipedeAtk2,
        "DiggerAtk2" => WId::DiggerAtk2,
        "BlobberAtk2" => WId::BlobberAtk2,
        "SpiderAtk2" => WId::SpiderAtk2,
        "BurrowerAtk1" => WId::BurrowerAtk1,
        "BurrowerAtk2" => WId::BurrowerAtk2,
        "GastropodAtk1" => WId::GastropodAtk1,
        "GastropodAtk2" => WId::GastropodAtk2,
        "StarfishAtk1" => WId::StarfishAtk1,
        "StarfishAtk2" => WId::StarfishAtk2,
        "TumblebugAtk1" => WId::TumblebugAtk1,
        "TumblebugAtk2" => WId::TumblebugAtk2,
        "PlasmodiaAtk1" => WId::PlasmodiaAtk1,
        "PlasmodiaAtk2" => WId::PlasmodiaAtk2,
        "FireflyAtkB" => WId::FireflyAtkB,
        "ScorpionAtkB" => WId::ScorpionAtkB,
        "BouncerAtkB" => WId::BouncerAtkB,
        "Armored_Train_Move" => WId::ArmoredTrainMove,
        "Acid_Tank_Attack" => WId::AcidTankAtk,
        "Support_Repair" => WId::SupportRepair,
        "BlobAtk2" => WId::BlobAtk2,
        "BlobBossAtk" => WId::BlobBossAtk,
        "BlobBossAtkMed" => WId::BlobBossAtkMed,
        "BlobBossAtkSmall" => WId::BlobBossAtkSmall,
        "SnowBossAtk" => WId::SnowBossAtk,
        "SnowBossAtk2" => WId::SnowBossAtk2,
        "BossHeal" => WId::BossHeal,
        "Pinnacle_FreezeTank" => WId::PinnacleFreezeTank,
        "BurnbugAtkB" => WId::BurnbugAtkB,
        "Support_Wind" => WId::SupportWind,
        // Upgraded Wind Torrent removes the use limit but keeps identical
        // board effects. Treat it as the same simulator primitive.
        "Support_Wind_A" => WId::SupportWind,
        // Repair sentinel — Python emits "_REPAIR" (matches wid_to_str inverse).
        // Without this case, replay_solution / score_plan / project_plan all
        // saw weapon_id="_REPAIR" plans as WId::None, skipping simulate_attack's
        // Repair branch entirely (no heal, no set_active, no fire/acid clear).
        // That predicted-vs-actual mismatch produced 24+ click_miss|_REPAIR|attack
        // entries in failure_db.jsonl with predicted hp/active < actual.
        "_REPAIR" => WId::Repair,
        // Also accept "Repair" for symmetry with the executor's classify_weapon
        // (which treats both as the repair flow).
        "Repair" => WId::Repair,
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
        WId::RangedArtillerymechA => "Ranged_Artillerymech_A",
        WId::DeployTankShot => "Deploy_TankShot",
        WId::DeployTankShot2 => "Deploy_TankShot2",
        WId::TrappedExplode => "Trapped_Explode",
        WId::RangedRockthrow => "Ranged_Rockthrow",
        WId::RangedDefensestrike => "Ranged_Defensestrike",
        WId::RangedRocket => "Ranged_Rocket",
        WId::RangedIgnite => "Ranged_Ignite",
        WId::RangedIgniteA => "Ranged_Ignite_A",
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
        WId::HornetAtkB => "HornetAtkB",
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
        WId::CrabAtkB => "CrabAtkB",
        WId::DiggerAtk1 => "DiggerAtk1",
        WId::BlobberAtk1 => "BlobberAtk1",
        WId::SpiderAtk1 => "SpiderAtk1",
        WId::SpiderlingAtk1 => "SpiderlingAtk1",
        WId::BlobAtk1 => "BlobAtk1",
        WId::BouncerAtk1 => "BouncerAtk1",
        WId::BouncerAtk2 => "BouncerAtk2",
        WId::MothAtk1 => "MothAtk1",
        WId::MothAtk2 => "MothAtk2",
        WId::MosquitoAtk1 => "MosquitoAtk1",
        WId::MosquitoAtk2 => "MosquitoAtk2",
        WId::BurnbugAtk1 => "BurnbugAtk1",
        WId::BurnbugAtk2 => "BurnbugAtk2",
        WId::SnowtankAtk1 => "SnowtankAtk1",
        WId::SnowtankAtk2 => "SnowtankAtk2",
        WId::SnowlaserAtk1 => "SnowlaserAtk1",
        WId::SnowlaserAtk2 => "SnowlaserAtk2",
        WId::SnowartAtk1 => "SnowartAtk1",
        WId::SnowartAtk2 => "SnowartAtk2",
        WId::LeaperAtk2 => "LeaperAtk2",
        WId::CentipedeAtk2 => "CentipedeAtk2",
        WId::DiggerAtk2 => "DiggerAtk2",
        WId::BlobberAtk2 => "BlobberAtk2",
        WId::SpiderAtk2 => "SpiderAtk2",
        WId::BurrowerAtk1 => "BurrowerAtk1",
        WId::BurrowerAtk2 => "BurrowerAtk2",
        WId::GastropodAtk1 => "GastropodAtk1",
        WId::GastropodAtk2 => "GastropodAtk2",
        WId::StarfishAtk1 => "StarfishAtk1",
        WId::StarfishAtk2 => "StarfishAtk2",
        WId::TumblebugAtk1 => "TumblebugAtk1",
        WId::TumblebugAtk2 => "TumblebugAtk2",
        WId::PlasmodiaAtk1 => "PlasmodiaAtk1",
        WId::PlasmodiaAtk2 => "PlasmodiaAtk2",
        WId::FireflyAtkB => "FireflyAtkB",
        WId::ScorpionAtkB => "ScorpionAtkB",
        WId::BeetleAtkB => "BeetleAtkB",
        WId::Repair => "_REPAIR",
        WId::SupportRepair => "Support_Repair",
        WId::BlobAtk2 => "BlobAtk2",
        WId::AcidTankAtk => "Acid_Tank_Attack",
        WId::BlobBossAtk => "BlobBossAtk",
        WId::BlobBossAtkMed => "BlobBossAtkMed",
        WId::BlobBossAtkSmall => "BlobBossAtkSmall",
        WId::SnowBossAtk => "SnowBossAtk",
        WId::SnowBossAtk2 => "SnowBossAtk2",
        WId::BossHeal => "BossHeal",
        WId::PinnacleFreezeTank => "Pinnacle_FreezeTank",
        WId::BurnbugAtkB => "BurnbugAtkB",
        WId::BouncerAtkB => "BouncerAtkB",
        WId::ArmoredTrainMove => "Armored_Train_Move",
        WId::SupportWind => "Support_Wind",
        _ => "",
    }
}

/// Map enemy pawn type name to its weapon WId.
/// Used by enemy attack simulation for proper weapon type dispatch.
pub fn enemy_weapon_for_type(type_name: &str) -> WId {
    match type_name {
        // Base game Vek
        "Scorpion1" => WId::ScorpionAtk1,
        "Scorpion2" => WId::ScorpionAtk2,
        "Hornet1" => WId::HornetAtk1,
        "Hornet2" => WId::HornetAtk2,
        "HornetBoss" => WId::HornetAtkB,
        "Leaper1" => WId::LeaperAtk1,
        "Leaper2" => WId::LeaperAtk2,
        "Beetle1" => WId::BeetleAtk1,
        "Beetle2" => WId::BeetleAtk2,
        "Firefly1" => WId::FireflyAtk1,
        "Firefly2" => WId::FireflyAtk2,
        "Centipede1" => WId::CentipedeAtk1,
        "Centipede2" => WId::CentipedeAtk2,
        "Scarab1" => WId::ScarabAtk1,
        "Scarab2" => WId::ScarabAtk2,
        "Crab1" => WId::CrabAtk1,
        "Crab2" => WId::CrabAtk2,
        "CrabBoss" => WId::CrabAtkB,
        "Digger1" => WId::DiggerAtk1,
        "Digger2" => WId::DiggerAtk2,
        "Blobber1" => WId::BlobberAtk1,
        "Blobber2" => WId::BlobberAtk2,
        "Spider1" => WId::SpiderAtk1,
        "Spider2" => WId::SpiderAtk2,
        "Burrower1" => WId::BurrowerAtk1,
        "Burrower2" => WId::BurrowerAtk2,
        // Advanced Edition Vek
        "Bouncer1" => WId::BouncerAtk1,
        "Bouncer2" => WId::BouncerAtk2,
        "BouncerBoss" => WId::BouncerAtkB,
        "Moth1" => WId::MothAtk1,
        "Moth2" => WId::MothAtk2,
        "Mosquito1" => WId::MosquitoAtk1,
        "Mosquito2" => WId::MosquitoAtk2,
        "Gastropod1" => WId::GastropodAtk1,
        "Gastropod2" => WId::GastropodAtk2,
        "Starfish1" => WId::StarfishAtk1,
        "Starfish2" => WId::StarfishAtk2,
        "Tumblebug1" => WId::TumblebugAtk1,
        "Tumblebug2" => WId::TumblebugAtk2,
        "Plasmodia1" => WId::PlasmodiaAtk1,
        "Plasmodia2" => WId::PlasmodiaAtk2,
        // Pinnacle bots
        "Snowtank1" => WId::SnowtankAtk1,
        "Snowtank2" => WId::SnowtankAtk2,
        "Snowlaser1" => WId::SnowlaserAtk1,
        "Snowlaser2" => WId::SnowlaserAtk2,
        "Snowart1" => WId::SnowartAtk1,
        "Snowart2" => WId::SnowartAtk2,
        "Burnbug1" => WId::BurnbugAtk1,
        "Burnbug2" => WId::BurnbugAtk2,
        // Pinnacle finale boss — Bot Leader. Skill selection (SnowBossAtk vs
        // BossHeal) is decided by Lua `BotBoss:GetWeapon()` based on
        // `Pawn:IsDamaged()`; the bridge serializes the *selected* skill into
        // the unit's weapon[0]/weapon[1] slots, but our `weapon_damage` always
        // reflects weapons[0]'s Damage (=2 / =4) for both. The enemy-phase
        // dispatcher disambiguates BossHeal vs SnowBossAtk by inspecting
        // `unit.weapon` (=BossHeal when boss is damaged) — see enemy.rs.
        // The default mapping points at the offensive skill; the BossHeal
        // arm overrides via the dedicated detection block before
        // weapon-type dispatch.
        "BotBoss" => WId::SnowBossAtk,
        "BotBoss2" => WId::SnowBossAtk2,
        // Minions
        "Spiderling1" | "Spiderling2" => WId::SpiderlingAtk1,
        s if s.starts_with("BlobMini") => WId::BlobAtk1,
        s if s.starts_with("Blob1") => WId::BlobAtk1,
        s if s.starts_with("Blob2") => WId::BlobAtk2,
        // Objective / special Vek
        "GlowingScorpion" => WId::ScorpionAtk1,
        // Bosses
        "FireflyBoss" => WId::FireflyAtkB,
        "ScorpionBoss" => WId::ScorpionAtkB,
        "BeetleBoss" => WId::BeetleAtkB,
        // Spider Leader (bridge: SpiderBoss) — "Plentiful Offspring":
        // spawns 2-3 Spiderling eggs at telegraphed tiles. No direct damage.
        // Reuse Alpha Spider's spawn-eggs template (Artillery, 0 damage).
        "SpiderBoss" => WId::SpiderAtk2,
        // Shaman / Large Goo Leader — "Goo Attack": 4-damage adjacent
        // squish. Closest existing template is BeetleAtkB (boss beetle
        // melee); underestimates damage vs 4 but still multi-dmg melee.
        "ShamanBoss" => WId::BeetleAtkB,
        // BlobBoss family — Mission_BlobBoss "Large Goo" boss. Per
        // scripts/missions/bosses/goo.lua:172-187, BlobBossAtk:GetSkillEffect
        // calls AddQueuedDamage(SpaceDamage(p2, 4)) BEFORE any optional
        // move; queued damage at p2 fires regardless of attacker position.
        // BlobBossMed and BlobBossSmall inherit the same skill (via
        // Skill:new{}). Without the QUEUED_DAMAGE_PERSISTS flag the boss
        // would silently no-op when pulled out of adjacency by Grappling
        // Hook / Grav Well — see m13 turn 4 grid_power 2→0 desync.
        "BlobBoss" => WId::BlobBossAtk,
        "BlobBossMed" => WId::BlobBossAtkMed,
        "BlobBossSmall" => WId::BlobBossAtkSmall,
        // Burnbug Leader (a.k.a. Gastropod Leader) — Archive Inc Corp HQ
        // finale boss. SkillList = {"BurnbugAtkB"} per
        // `scripts/advanced/bosses/burnbug.lua:17`.
        "BurnbugBoss" => WId::BurnbugAtkB,
        _ => WId::None,
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
        WId::BruteGrapple => "Grappling Hook",
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
        WId::RangedArtillerymechA => "Artemis Artillery",
        WId::DeployTankShot => "Stock Cannon",
        WId::DeployTankShot2 => "Stock Cannon",
        WId::RangedRockthrow => "Rock Launcher",
        WId::RangedDefensestrike => "Cluster Artillery",
        WId::RangedRocket => "Rocket Artillery",
        WId::RangedIgnite => "Ignite",
        WId::RangedIgniteA => "Ignite",
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
        WId::ScorpionAtk1 => "Scorpion Strike",
        WId::ScorpionAtk2 => "Alpha Scorpion Strike",
        WId::HornetAtk1 => "Hornet Sting",
        WId::HornetAtk2 => "Alpha Hornet Sting",
        WId::HornetAtkB => "Super Stinger",
        WId::LeaperAtk1 => "Leaper Strike",
        WId::LeaperAtk2 => "Alpha Leaper Strike",
        WId::BeetleAtk1 => "Beetle Charge",
        WId::BeetleAtk2 => "Alpha Beetle Charge",
        WId::FireflyAtk1 => "Firefly Shot",
        WId::FireflyAtk2 => "Alpha Firefly Shot",
        WId::CentipedeAtk1 => "Centipede Spit",
        WId::CentipedeAtk2 => "Alpha Centipede Spit",
        WId::ScarabAtk1 => "Scarab Shot",
        WId::ScarabAtk2 => "Alpha Scarab Shot",
        WId::CrabAtk1 => "Crab Artillery",
        WId::CrabAtk2 => "Alpha Crab Artillery",
        WId::CrabAtkB => "Raining Expulsions",
        WId::DiggerAtk1 => "Digger Smash",
        WId::DiggerAtk2 => "Alpha Digger Smash",
        WId::BlobberAtk1 => "Blobber Launch",
        WId::BlobberAtk2 => "Alpha Blobber Launch",
        WId::SpiderAtk1 => "Spider Egg",
        WId::SpiderAtk2 => "Alpha Spider Egg",
        WId::SpiderlingAtk1 => "Spiderling Bite",
        WId::BlobAtk1 => "Blob Explode",
        WId::BlobAtk2 => "Alpha Blob Explode",
        WId::BouncerAtk1 => "Energized Horns",
        WId::BouncerAtk2 => "Alpha Energized Horns",
        WId::MothAtk1 => "Repulsive Pellets",
        WId::MothAtk2 => "Alpha Repulsive Pellets",
        WId::MosquitoAtk1 => "Smokescreen Whip",
        WId::MosquitoAtk2 => "Alpha Smokescreen Whip",
        WId::BurnbugAtk1 => "Burnbug Strike",
        WId::BurnbugAtk2 => "Alpha Burnbug Strike",
        WId::SnowtankAtk1 => "Snowtank Attack",
        WId::SnowtankAtk2 => "Cannon 8R Mark II",
        WId::SnowlaserAtk1 => "BKR Beam Mark I",
        WId::SnowlaserAtk2 => "BKR Beam Mark II",
        WId::SnowartAtk1 => "Snowart Shot",
        WId::SnowartAtk2 => "Alpha Snowart Shot",
        WId::BurrowerAtk1 => "Burrower Slam",
        WId::BurrowerAtk2 => "Alpha Burrower Slam",
        WId::GastropodAtk1 => "Gastropod Grapple",
        WId::GastropodAtk2 => "Alpha Gastropod Grapple",
        WId::StarfishAtk1 => "Starfish Slash",
        WId::StarfishAtk2 => "Alpha Starfish Slash",
        WId::TumblebugAtk1 => "Tumblebug Boulder",
        WId::TumblebugAtk2 => "Alpha Tumblebug Boulder",
        WId::PlasmodiaAtk1 => "Plasmodia Spore",
        WId::PlasmodiaAtk2 => "Alpha Plasmodia Spore",
        WId::FireflyAtkB => "Firefly Boss Shot",
        WId::ScorpionAtkB => "Massive Spinneret",
        WId::BouncerAtkB => "Sweeping Horns",
        WId::ArmoredTrainMove => "Armored Charge",
        WId::BeetleAtkB => "Flaming Abdomen",
        WId::SupportRepair => "Repair Drop",
        WId::AcidTankAtk => "A.C.I.D. Cannon",
        WId::BlobBossAtk => "Goo Attack",
        WId::BlobBossAtkMed => "Goo Attack (Med)",
        WId::BlobBossAtkSmall => "Goo Attack (Small)",
        WId::SnowBossAtk => "Vk8 Rockets Mark III",
        WId::SnowBossAtk2 => "Vk8 Rockets Mark IV",
        WId::BossHeal => "Self-Repairing",
        WId::BurnbugAtkB => "Flaming Proboscis",
        WId::SupportWind => "Wind Torrent",
        WId::TrappedExplode => "Area Blast",
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
    fn test_artemis_artillery_buildings_immune_upgrade() {
        let w = weapon_def(WId::RangedArtillerymechA);
        assert_eq!(w.weapon_type, WeaponType::Artillery);
        assert_eq!(w.damage, 1);
        assert_eq!(w.push, PushDir::Outward);
        assert!(w.aoe_center());
        assert!(w.aoe_adjacent());
        assert!(w.building_immune());
        assert_eq!(w.range_min, 2);
    }

    #[test]
    fn test_deploy_tank_stock_cannon() {
        let w = weapon_def(WId::DeployTankShot);
        assert_eq!(w.weapon_type, WeaponType::Projectile);
        assert_eq!(w.damage, 0);
        assert_eq!(w.push, PushDir::Forward);
        assert_eq!(w.range_max, 0);

        let upgraded = weapon_def(WId::DeployTankShot2);
        assert_eq!(upgraded.damage, 2);
        assert_eq!(upgraded.push, PushDir::Forward);
    }

    #[test]
    fn test_bouncer_boss_sweeping_horns_def() {
        let w = weapon_def(WId::BouncerAtkB);
        assert_eq!(w.weapon_type, WeaponType::Melee);
        assert_eq!(w.damage, 2);
        assert_eq!(w.push, PushDir::Forward);
        assert!(w.push_self());
        assert!(w.aoe_perpendicular());
        assert_eq!(wid_from_str("BouncerAtkB"), WId::BouncerAtkB);
        assert_eq!(enemy_weapon_for_type("BouncerBoss"), WId::BouncerAtkB);
        assert_eq!(weapon_name(WId::BouncerAtkB), "Sweeping Horns");
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
        assert_eq!(wid_from_str("Ranged_Artillerymech_A"), WId::RangedArtillerymechA);
        assert_eq!(wid_from_str("Deploy_TankShot"), WId::DeployTankShot);
        assert_eq!(wid_from_str("Deploy_TankShot2"), WId::DeployTankShot2);
        assert_eq!(wid_from_str("Trapped_Explode"), WId::TrappedExplode);
        assert_eq!(wid_from_str("BouncerAtkB"), WId::BouncerAtkB);
        assert_eq!(wid_from_str("Armored_Train_Move"), WId::ArmoredTrainMove);
        assert_eq!(wid_from_str("unknown_weapon"), WId::None);
    }

    #[test]
    fn test_wid_to_str_roundtrip() {
        // Every wid_from_str input should roundtrip through wid_to_str
        let pairs = [
            ("Prime_Punchmech", WId::PrimePunchmech),
            ("Brute_Tankmech", WId::BruteTankmech),
            ("Ranged_Artillerymech", WId::RangedArtillerymech),
            ("Ranged_Artillerymech_A", WId::RangedArtillerymechA),
            ("Deploy_TankShot", WId::DeployTankShot),
            ("Trapped_Explode", WId::TrappedExplode),
            ("BouncerAtkB", WId::BouncerAtkB),
            ("Armored_Train_Move", WId::ArmoredTrainMove),
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
        // ...and the inverse must round-trip — without this case, replay /
        // score_plan / project_plan silently turn Repair plans into WId::None
        // and predict the mech does nothing (no heal, stays active).
        assert_eq!(wid_from_str("_REPAIR"), WId::Repair);
        // "Repair" alias accepted for symmetry with the executor's
        // classify_weapon (which treats both as the repair flow).
        assert_eq!(wid_from_str("Repair"), WId::Repair);
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

    #[test]
    fn test_support_repair_def() {
        let w = weapon_def(WId::SupportRepair);
        assert_eq!(w.weapon_type, WeaponType::HealAll);
        assert_eq!(w.damage, 0);
        assert_eq!(w.limited, 1);
        assert!(w.targets_allies());
        assert_eq!(wid_from_str("Support_Repair"), WId::SupportRepair);
        assert_eq!(wid_to_str(WId::SupportRepair), "Support_Repair");
        assert_eq!(weapon_name(WId::SupportRepair), "Repair Drop");
    }

    #[test]
    fn test_support_wind_def_and_target_zones() {
        let w = weapon_def(WId::SupportWind);
        assert_eq!(w.weapon_type, WeaponType::GlobalPush);
        assert_eq!(w.damage, 0);
        assert_eq!(w.push, PushDir::Forward);
        assert_eq!(w.limited, 1);
        assert!(w.targets_allies());
        assert_eq!(wid_from_str("Support_Wind"), WId::SupportWind);
        assert_eq!(wid_from_str("Support_Wind_A"), WId::SupportWind);
        assert_eq!(wid_to_str(WId::SupportWind), "Support_Wind");
        assert_eq!(weapon_name(WId::SupportWind), "Wind Torrent");
        assert_eq!(support_wind_dir_from_target(1, 3), Some(3));
        assert_eq!(support_wind_dir_from_target(5, 3), Some(1));
        assert_eq!(support_wind_dir_from_target(3, 1), Some(2));
        assert_eq!(support_wind_dir_from_target(3, 5), Some(0));
        assert_eq!(support_wind_dir_from_target(3, 3), None);
    }

    #[test]
    fn test_overlay_empty_returns_none() {
        // No entries → no allocation, callers use &WEAPONS directly.
        assert!(build_overlay_table(&[]).is_none());
        // Only-empty patches collapse to None as well.
        let entries = vec![(WId::PrimePunchmech, PartialWeaponDef::default())];
        assert!(build_overlay_table(&entries).is_none());
    }

    #[test]
    fn test_overlay_applies_per_field_and_preserves_others() {
        // Patch Cluster Artillery damage to an upgraded value; verify the
        // overlay affects only the patched field and leaves unrelated
        // weapons untouched.
        let base_ranged = weapon_def(WId::RangedDefensestrike);
        let base_titan = *weapon_def(WId::PrimePunchmech);

        let patch = PartialWeaponDef { damage: Some(2), ..Default::default() };
        let table = build_overlay_table(&[(WId::RangedDefensestrike, patch)])
            .expect("non-empty overlay should allocate a table");

        let patched = &table[WId::RangedDefensestrike as usize];
        assert_eq!(patched.damage, 2, "damage patched");
        assert_eq!(patched.weapon_type, base_ranged.weapon_type, "weapon_type preserved");
        assert_eq!(patched.push, base_ranged.push, "push preserved");
        assert_eq!(patched.range_max, base_ranged.range_max, "range preserved");
        // Unrelated weapon untouched.
        assert_eq!(table[WId::PrimePunchmech as usize].damage, base_titan.damage);
        assert_eq!(table[WId::PrimePunchmech as usize].push, base_titan.push);
    }

    #[test]
    fn test_overlay_flag_set_and_clear() {
        // Start from a weapon without FIRE, add it via flags_set; also
        // clear AOE_CENTER to prove bit-level deltas work.
        let base = *weapon_def(WId::PrimePunchmech);
        assert!(!base.fire());
        assert!(base.aoe_center());

        let patch = PartialWeaponDef {
            flags_set: WeaponFlags::FIRE,
            flags_clear: WeaponFlags::AOE_CENTER,
            ..Default::default()
        };
        let table = build_overlay_table(&[(WId::PrimePunchmech, patch)]).unwrap();
        let w = &table[WId::PrimePunchmech as usize];
        assert!(w.fire(), "FIRE set by overlay");
        assert!(!w.aoe_center(), "AOE_CENTER cleared by overlay");
    }
}
