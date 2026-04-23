"""Weapon definitions for Into the Breach.

Static lookup table extracted from the game's Lua weapon scripts.
The solver needs these to simulate weapon effects (damage, push, AoE, status).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class WeaponType(str, Enum):
    MELEE = "melee"           # PathSize=1, adjacent tile
    PROJECTILE = "projectile" # Fires in line, hits first obstacle
    ARTILLERY = "artillery"   # Arcs over obstacles, hits target tile
    LASER = "laser"           # Beam, hits all tiles in line until blocked
    LEAP = "leap"             # Jump to target, AoE on landing
    CHARGE = "charge"         # Rush forward until hitting something
    DEPLOY = "deploy"         # Spawn a unit
    SELF_AOE = "self_aoe"     # Centered on self, hits adjacent
    SWAP = "swap"             # Swap positions with target
    PULL = "pull"             # Pull target toward self
    TWO_CLICK = "two_click"   # Two-step targeting
    HEAL_ALL = "heal_all"     # Heals every player-team unit on the board
    PASSIVE = "passive"       # Always-on effect


class PushDir(str, Enum):
    FORWARD = "forward"       # Push in attack direction
    BACKWARD = "backward"     # Push toward attacker
    PERPENDICULAR = "perpendicular"  # Push left+right of attack line
    OUTWARD = "outward"       # Push away from center (AoE)
    INWARD = "inward"         # Pull toward center
    FLIP = "flip"             # Reverse target's facing
    NONE = "none"


@dataclass(frozen=True)
class WeaponDef:
    """Static weapon definition."""
    name: str                          # Display name
    weapon_type: str                   # WeaponType value
    damage: int = 0                    # Base damage to primary target
    damage_outer: int = 0              # Damage to adjacent/secondary tiles
    push: str = "none"                 # PushDir value
    push_tiles: int = 1               # Number of tiles pushed
    self_damage: int = 0               # Damage to self
    push_self: bool = False            # Whether self is pushed backward
    range_min: int = 1                 # Minimum range (artillery start)
    range_max: int = 1                 # Maximum range (0 = unlimited)
    path_size: int = 1                 # Tiles affected in line
    # Status effects
    fire: bool = False
    acid: bool = False
    freeze: bool = False
    smoke: bool = False
    smoke_behind_shooter: bool = False  # smoke lands one tile opposite attack_dir from shooter (Ranged_Rocket)
    shield: bool = False
    web: bool = False
    # Targeting
    targets_allies: bool = False       # FriendlyDamage
    building_damage: bool = True       # Whether it damages buildings
    phase: bool = False                # Passes through obstacles
    # AoE shape
    aoe_center: bool = True            # Hits center tile
    aoe_adjacent: bool = False         # Hits 4 cardinal adjacent tiles
    aoe_behind: bool = False           # Hits tiles behind target
    aoe_perpendicular: bool = False    # Hits tiles beside target
    # Special
    limited: int = 0                   # 0 = unlimited uses
    chain: bool = False                # Chains through adjacent occupied tiles
    charge: bool = False               # Charges forward
    flying_charge: bool = False        # Charge ignores terrain
    spawns: str = ""                   # Unit type spawned
    # Upgrade info (what changes with upgrades)
    upgrade_a: str = ""
    upgrade_b: str = ""


# ============================================================
# MECH WEAPONS — Default squad weapons
# ============================================================

WEAPON_DEFS: dict[str, WeaponDef] = {

    # --- PRIME CLASS ---

    "Prime_Punchmech": WeaponDef(
        name="Titan Fist", weapon_type="melee",
        damage=2, push="forward",
        upgrade_a="+dash (charge before punch)",
        upgrade_b="+2 damage (total 4)",
    ),
    "Prime_Lightning": WeaponDef(
        name="Chain Whip", weapon_type="melee",
        damage=2, chain=True, targets_allies=True,
        upgrade_a="chains through buildings safely",
        upgrade_b="+1 damage (total 3)",
    ),
    "Prime_Lasermech": WeaponDef(
        name="Burst Beam", weapon_type="laser",
        damage=3, range_max=0, targets_allies=True,
        upgrade_a="no friendly damage",
        upgrade_b="+1 starting damage (total 4)",
    ),
    "Prime_ShieldBash": WeaponDef(
        name="Spartan Shield", weapon_type="melee",
        damage=0, push="none",
        upgrade_a="shield self before attack",
        upgrade_b="+1 damage (total 1)",
    ),
    "Prime_Shift": WeaponDef(
        name="Vice Fist", weapon_type="melee",
        damage=1, push="throw", targets_allies=True,
        upgrade_a="no friendly damage",
        upgrade_b="+2 damage (total 3)",
    ),
    "Prime_Flamethrower": WeaponDef(
        name="Flamethrower", weapon_type="melee",
        damage=0, push="forward", fire=True, path_size=1,
        upgrade_a="+1 range (2 tiles)",
        upgrade_b="+1 range (2 tiles)",
    ),
    "Prime_Areablast": WeaponDef(
        name="Area Blast", weapon_type="self_aoe",
        damage=1, push="outward", aoe_adjacent=True, aoe_center=False,
        upgrade_a="+1 damage (total 2)",
        upgrade_b="+1 damage (total 2)",
    ),
    "Prime_Leap": WeaponDef(
        name="Hydraulic Legs", weapon_type="leap",
        damage=1, push="outward", self_damage=1, range_max=7,
        aoe_adjacent=True, aoe_center=False,
        upgrade_a="+1 damage, +1 self damage",
        upgrade_b="+1 damage",
    ),
    "Prime_Spear": WeaponDef(
        name="Spear", weapon_type="melee",
        damage=2, push="forward", path_size=2,
        upgrade_a="+acid on last tile",
        upgrade_b="+1 range (3 tiles)",
    ),
    "Prime_Rockmech": WeaponDef(
        name="Rock Throw", weapon_type="projectile",
        damage=2, range_max=0,
        upgrade_a="+1 damage (total 3)",
        upgrade_b="+1 damage (total 3)",
    ),
    "Prime_RocketPunch": WeaponDef(
        name="Rocket Fist", weapon_type="melee",
        damage=2, push="forward", push_self=True,
        upgrade_a="becomes projectile (unlimited range)",
        upgrade_b="+2 damage (total 4)",
    ),
    "Prime_RightHook": WeaponDef(
        name="Right Hook", weapon_type="melee",
        damage=2, push="perpendicular",
        upgrade_a="+1 damage (total 3)",
        upgrade_b="+1 damage (total 3)",
    ),
    "Prime_SpinFist": WeaponDef(
        name="Spin Fist", weapon_type="self_aoe",
        damage=2, push="perpendicular", self_damage=1,
        aoe_adjacent=True, aoe_center=False,
        upgrade_a="no self damage",
        upgrade_b="+1 damage (total 3)",
    ),
    "Prime_Sword": WeaponDef(
        name="Sword", weapon_type="melee",
        damage=2, push="forward", aoe_perpendicular=True, limited=1,
        upgrade_a="+1 use (total 2)",
        upgrade_b="+2 damage (total 4)",
    ),
    "Prime_Smash": WeaponDef(
        name="Ground Smash", weapon_type="melee",
        damage=4, push="outward", aoe_perpendicular=True, limited=1,
        upgrade_a="+1 use (total 2)",
        upgrade_b="+1 damage (total 5)",
    ),

    # --- BRUTE CLASS ---

    "Brute_Tankmech": WeaponDef(
        name="Taurus Cannon", weapon_type="projectile",
        damage=1, push="forward", range_max=0,
        upgrade_a="+1 damage (total 2)",
        upgrade_b="+1 damage (total 2)",
    ),
    "Brute_Jetmech": WeaponDef(
        name="Aerial Bombs", weapon_type="leap",
        damage=1, smoke=True, range_min=2, range_max=2,
        aoe_center=False,
        upgrade_a="+1 damage (total 2)",
        upgrade_b="+1 range (total 3)",
    ),
    "Brute_Mirrorshot": WeaponDef(
        name="Mirror Shot", weapon_type="projectile",
        damage=1, push="forward", range_max=0, aoe_behind=True,
        upgrade_a="+1 damage (total 2)",
        upgrade_b="+1 damage (total 2)",
    ),
    "Brute_Beetle": WeaponDef(
        name="Ramming Engines", weapon_type="charge",
        damage=2, push="forward", self_damage=1,
        charge=True, flying_charge=True, range_max=0,
        upgrade_a="+1 damage, +1 self damage",
        upgrade_b="+1 damage (total 3)",
    ),
    "Brute_Grapple": WeaponDef(
        name="Vice Fist", weapon_type="pull",
        damage=0, push="inward", range_max=0,
        upgrade_a="shield pulled allies",
        upgrade_b="",
    ),
    "Brute_Unstable": WeaponDef(
        name="Unstable Cannon", weapon_type="projectile",
        damage=2, push="forward", self_damage=1, push_self=True, range_max=0,
        upgrade_a="+1 damage, +1 self damage",
        upgrade_b="+1 damage (total 3)",
    ),
    "Brute_PhaseShot": WeaponDef(
        name="Phase Cannon", weapon_type="projectile",
        damage=1, push="forward", phase=True, range_max=0,
        upgrade_a="shield phased buildings",
        upgrade_b="+1 damage (total 2)",
    ),
    "Brute_Shrapnel": WeaponDef(
        name="Defensive Shrapnel", weapon_type="projectile",
        damage=0, push="outward", range_max=0, aoe_adjacent=True,
    ),
    "Brute_Heavyrocket": WeaponDef(
        name="Heavy Rocket", weapon_type="projectile",
        damage=3, push="outward", range_max=0, limited=1,
        aoe_perpendicular=True,
        upgrade_a="+1 use (total 2)",
        upgrade_b="+2 damage (total 5)",
    ),
    "Brute_Sonic": WeaponDef(
        name="Sonic Dash", weapon_type="charge",
        damage=0, push="perpendicular", charge=True, range_max=0,
    ),
    "Brute_Shockblast": WeaponDef(
        name="Shock Cannon", weapon_type="projectile",
        damage=1, push="backward", range_max=0, aoe_behind=True,
        upgrade_a="+1 damage (total 2)",
        upgrade_b="+1 damage (total 2)",
    ),
    "Brute_Sniper": WeaponDef(
        name="Sniper Rifle", weapon_type="projectile",
        damage=2, push="forward", range_max=0,
        upgrade_a="+1 max damage (total 3)",
        upgrade_b="+2 max damage (total 4)",
    ),
    "Brute_Splitshot": WeaponDef(
        name="Split Shot", weapon_type="projectile",
        damage=2, push="outward", range_max=0, limited=1,
        aoe_perpendicular=True,
        upgrade_a="+1 use (total 2)",
        upgrade_b="+1 damage (total 3)",
    ),
    "Brute_Bombrun": WeaponDef(
        name="Bombing Run", weapon_type="leap",
        damage=1, range_min=2, range_max=8, limited=1,
        aoe_center=False,
        upgrade_a="+1 use (total 2)",
        upgrade_b="+2 damage (total 3)",
    ),

    # --- MISSION-SPECIFIC ---

    "Archive_ArtShot": WeaponDef(
        name="Old Earth Artillery", weapon_type="artillery",
        damage=2, push="none", range_min=2,
        aoe_behind=True,  # hits target + tile behind in firing direction
    ),

    # --- RANGED CLASS ---

    "Ranged_Artillerymech": WeaponDef(
        name="Artemis Artillery", weapon_type="artillery",
        damage=1, damage_outer=0, push="outward", range_min=2,
        aoe_adjacent=True,
        upgrade_a="no building damage",
        upgrade_b="+2 damage (total 3)",
    ),
    "Ranged_Rockthrow": WeaponDef(
        name="Rock Launcher", weapon_type="artillery",
        damage=2, push="perpendicular", range_min=2,
        upgrade_a="+1 damage (total 3)",
        upgrade_b="",
    ),
    "Ranged_Defensestrike": WeaponDef(
        name="Cluster Artillery", weapon_type="artillery",
        damage=0, damage_outer=1, push="outward", range_min=2,
        aoe_adjacent=True, aoe_center=False,
        upgrade_a="no building damage",
        upgrade_b="+1 outer damage (total 2)",
    ),
    "Ranged_Rocket": WeaponDef(
        name="Rocket Artillery", weapon_type="artillery",
        damage=2, push="forward", smoke_behind_shooter=True, range_min=2,
        upgrade_a="+1 damage (total 3)",
        upgrade_b="+1 damage (total 3)",
    ),
    "Ranged_Ignite": WeaponDef(
        name="Ignite", weapon_type="artillery",
        damage=0, push="outward", fire=True, range_min=2,
        aoe_adjacent=True,
        upgrade_a="fire behind mech too",
        upgrade_b="+2 damage to center",
    ),
    "Ranged_Ice": WeaponDef(
        name="Cryo-Launcher", weapon_type="artillery",
        damage=0, freeze=True, range_min=2, self_damage=0,
        upgrade_a="no self-freeze",
        upgrade_b="",
    ),
    "Ranged_ScatterShot": WeaponDef(
        name="Scatter Shot", weapon_type="artillery",
        damage=1, push="forward", range_min=2,
        upgrade_a="+perpendicular hits",
        upgrade_b="+1 damage (total 2)",
    ),
    "Ranged_BackShot": WeaponDef(
        name="Back Shot", weapon_type="artillery",
        damage=1, push="backward", range_min=2, aoe_behind=True,
        upgrade_a="+1 damage (total 2)",
        upgrade_b="+1 damage (total 2)",
    ),
    "Ranged_Wide": WeaponDef(
        name="Overpower", weapon_type="artillery",
        damage=2, range_min=2, limited=1,
        aoe_adjacent=True, aoe_center=True,
        upgrade_a="+1 use (total 2)",
        upgrade_b="+1 damage (total 3)",
    ),

    # --- SCIENCE CLASS ---

    "Science_Pullmech": WeaponDef(
        name="Attract Shot", weapon_type="pull",
        damage=0, push="inward", range_max=0,
    ),
    "Science_Gravwell": WeaponDef(
        name="Grav Well", weapon_type="pull",
        damage=0, push="inward", range_min=2,
    ),
    "Science_Repulse": WeaponDef(
        name="Repulse", weapon_type="self_aoe",
        damage=0, push="outward", aoe_adjacent=True, aoe_center=False,
        upgrade_a="shield self",
        upgrade_b="shield allies in range",
    ),
    "Science_Swap": WeaponDef(
        name="Teleporter", weapon_type="swap",
        damage=0, range_max=1,
        upgrade_a="+1 range (total 2)",
        upgrade_b="+2 range (total 3)",
    ),
    "Science_AcidShot": WeaponDef(
        name="Acid Projector", weapon_type="projectile",
        damage=0, push="forward", acid=True, range_max=0,
    ),
    "Science_Shield": WeaponDef(
        name="Shield Projector", weapon_type="artillery",
        damage=0, shield=True, limited=2, range_min=2,
        upgrade_a="+1 use (total 3)",
        upgrade_b="shield 5-tile cross",
    ),
    "Science_Confuse": WeaponDef(
        name="Confusion Ray", weapon_type="projectile",
        damage=0, push="flip", range_max=0,
    ),

    # --- ANY CLASS / SUPPORT ---

    # Heals every TEAM_PLAYER pawn (mechs + allied NPCs like Train Pawn,
    # Satellite Rocket, Acid Vat, Dam) to full HP and clears fire/acid/frozen.
    # Revives disabled mechs from 0 HP. Does NOT damage buildings and does
    # NOT extinguish the burning tile under a healed unit. Single-use per
    # battle; the Lua source marks Limited=1 but the solver does not yet
    # enforce cross-turn use counts (see the other limited=1 weapons above).
    "Support_Repair": WeaponDef(
        name="Repair Drop", weapon_type="heal_all",
        damage=0, range_max=0, limited=1,
        targets_allies=True, building_damage=False,
    ),

    # --- PASSIVE ABILITIES ---

    "Passive_Electric": WeaponDef(
        name="Storm Generator", weapon_type="passive",
        upgrade_a="smoke deals 2 damage",
    ),
    "Passive_FlameImmune": WeaponDef(
        name="Flame Shielding", weapon_type="passive",
    ),
    "Passive_Leech": WeaponDef(
        name="Viscera Nanobots", weapon_type="passive",
        upgrade_a="heal 2 on kill",
    ),
    "Passive_FriendlyFire": WeaponDef(
        name="Vek Hormones", weapon_type="passive",
    ),
    "Passive_Boosters": WeaponDef(
        name="Kickoff Boosters", weapon_type="passive",
    ),
    "Passive_Defenses": WeaponDef(
        name="Networked Armor", weapon_type="passive",
    ),
    "Passive_MassRepair": WeaponDef(
        name="Repair Field", weapon_type="passive",
    ),
    "Passive_Burrows": WeaponDef(
        name="Stabilizers", weapon_type="passive",
    ),
    "Passive_Psions": WeaponDef(
        name="Psion Dampener", weapon_type="passive",
    ),
    "Passive_Ammo": WeaponDef(
        name="Supply Drop", weapon_type="passive",
    ),
    "Passive_HealingSmoke": WeaponDef(
        name="Healing Fog", weapon_type="passive",
    ),
    "Passive_FireBoost": WeaponDef(
        name="Flame Boost", weapon_type="passive",
    ),
    "Passive_ForceAmp": WeaponDef(
        name="Force Amplifier", weapon_type="passive",
    ),
}

# ============================================================
# ENEMY WEAPONS
# ============================================================

ENEMY_WEAPON_DEFS: dict[str, WeaponDef] = {
    # ── Base Game Melee ──────────────────────────────────────────────
    "ScorpionAtk1": WeaponDef(
        name="Scorpion Strike", weapon_type="melee",
        damage=1, web=True,
    ),
    "ScorpionAtk2": WeaponDef(
        name="Alpha Scorpion Strike", weapon_type="melee",
        damage=3, web=True,
    ),
    "HornetAtk1": WeaponDef(
        name="Hornet Sting", weapon_type="melee",
        damage=1,
    ),
    "HornetAtk2": WeaponDef(
        name="Alpha Hornet Sting", weapon_type="melee",
        damage=2, aoe_behind=True,
    ),
    "LeaperAtk1": WeaponDef(
        name="Leaper Strike", weapon_type="melee",
        damage=3, web=True,
    ),
    "LeaperAtk2": WeaponDef(
        name="Alpha Leaper Strike", weapon_type="melee",
        damage=5, web=True,
    ),
    "BeetleAtk1": WeaponDef(
        name="Beetle Charge", weapon_type="charge",
        damage=1, charge=True,
    ),
    "BeetleAtk2": WeaponDef(
        name="Alpha Beetle Charge", weapon_type="charge",
        damage=3, charge=True,
    ),
    "BurrowerAtk1": WeaponDef(
        name="Burrower Slam", weapon_type="melee",
        damage=1, path_size=3,
    ),
    "BurrowerAtk2": WeaponDef(
        name="Alpha Burrower Slam", weapon_type="melee",
        damage=2, path_size=3,
    ),

    # ── Base Game Ranged ─────────────────────────────────────────────
    "FireflyAtk1": WeaponDef(
        name="Firefly Shot", weapon_type="projectile",
        damage=1, range_max=0,
    ),
    "FireflyAtk2": WeaponDef(
        name="Alpha Firefly Shot", weapon_type="projectile",
        damage=3, range_max=0,
    ),
    "CentipedeAtk1": WeaponDef(
        name="Centipede Spit", weapon_type="projectile",
        damage=1, acid=True, aoe_perpendicular=True, range_max=0,
    ),
    "CentipedeAtk2": WeaponDef(
        name="Alpha Centipede Spit", weapon_type="projectile",
        damage=2, acid=True, aoe_perpendicular=True, range_max=0,
    ),

    # ── Base Game Artillery ──────────────────────────────────────────
    "ScarabAtk1": WeaponDef(
        name="Scarab Shot", weapon_type="artillery",
        damage=1, range_min=2,
    ),
    "ScarabAtk2": WeaponDef(
        name="Alpha Scarab Shot", weapon_type="artillery",
        damage=3, range_min=2,
    ),
    "CrabAtk1": WeaponDef(
        name="Crab Artillery", weapon_type="artillery",
        damage=1, range_min=2, path_size=2,
    ),
    "CrabAtk2": WeaponDef(
        name="Alpha Crab Artillery", weapon_type="artillery",
        damage=3, range_min=2, path_size=2,
    ),

    # ── Base Game Special ────────────────────────────────────────────
    "DiggerAtk1": WeaponDef(
        name="Digger Smash", weapon_type="self_aoe",
        damage=1, aoe_adjacent=True, aoe_center=False,
    ),
    "DiggerAtk2": WeaponDef(
        name="Alpha Digger Smash", weapon_type="self_aoe",
        damage=2, aoe_adjacent=True, aoe_center=False,
    ),
    "BlobberAtk1": WeaponDef(
        name="Blobber Launch", weapon_type="artillery",
        damage=0, spawns="Blob1",
    ),
    "BlobberAtk2": WeaponDef(
        name="Alpha Blobber Launch", weapon_type="artillery",
        damage=0, spawns="Blob2",
    ),
    "SpiderAtk1": WeaponDef(
        name="Spider Egg", weapon_type="artillery",
        damage=0, spawns="WebbEgg1",
    ),
    "SpiderAtk2": WeaponDef(
        name="Alpha Spider Egg", weapon_type="artillery",
        damage=0, spawns="WebbEgg1",
    ),
    "SpiderlingAtk1": WeaponDef(
        name="Spiderling Bite", weapon_type="melee",
        damage=1,
    ),
    "BlobAtk1": WeaponDef(
        name="Blob Explode", weapon_type="self_aoe",
        damage=1, aoe_adjacent=True, aoe_center=True,
    ),
    "BlobAtk2": WeaponDef(
        name="Alpha Blob Explode", weapon_type="self_aoe",
        damage=2, aoe_adjacent=True, aoe_center=True,
    ),

    # ── Advanced Edition Melee ───────────────────────────────────────
    "BouncerAtk1": WeaponDef(
        name="Energized Horns", weapon_type="melee",
        damage=1, push="forward", push_self=True,
    ),
    "BouncerAtk2": WeaponDef(
        name="Alpha Energized Horns", weapon_type="melee",
        damage=3, push="forward", push_self=True,
    ),
    "MosquitoAtk1": WeaponDef(
        name="Smokescreen Whip", weapon_type="melee",
        damage=1, smoke=True,
    ),
    "MosquitoAtk2": WeaponDef(
        name="Alpha Smokescreen Whip", weapon_type="melee",
        damage=3, smoke=True,
    ),
    "StarfishAtk1": WeaponDef(
        name="Starfish Slash", weapon_type="melee",
        damage=1,
    ),
    "StarfishAtk2": WeaponDef(
        name="Alpha Starfish Slash", weapon_type="melee",
        damage=2,
    ),
    "TumblebugAtk1": WeaponDef(
        name="Tumblebug Boulder", weapon_type="melee",
        damage=1,
    ),
    "TumblebugAtk2": WeaponDef(
        name="Alpha Tumblebug Boulder", weapon_type="melee",
        damage=3,
    ),

    # ── Advanced Edition Artillery ───────────────────────────────────
    "MothAtk1": WeaponDef(
        name="Repulsive Pellets", weapon_type="artillery",
        damage=1, push="forward", push_self=True, range_min=2,
    ),
    "MothAtk2": WeaponDef(
        name="Alpha Repulsive Pellets", weapon_type="artillery",
        damage=3, push="forward", push_self=True, range_min=2,
    ),
    "PlasmodiaAtk1": WeaponDef(
        name="Plasmodia Spore", weapon_type="artillery",
        damage=0, spawns="Spore1",
    ),
    "PlasmodiaAtk2": WeaponDef(
        name="Alpha Plasmodia Spore", weapon_type="artillery",
        damage=0, spawns="Spore2",
    ),

    # ── Advanced Edition Ranged ──────────────────────────────────────
    "GastropodAtk1": WeaponDef(
        name="Gastropod Grapple", weapon_type="projectile",
        damage=1, range_max=0,
    ),
    "GastropodAtk2": WeaponDef(
        name="Alpha Gastropod Grapple", weapon_type="projectile",
        damage=3, range_max=0,
    ),

    # ── Pinnacle Bots ────────────────────────────────────────────────
    "SnowtankAtk1": WeaponDef(
        name="Snowtank Attack", weapon_type="melee",
        damage=1,
    ),
    "SnowartAtk1": WeaponDef(
        name="Snowart Shot", weapon_type="artillery",
        damage=1, range_min=2,
    ),
    "SnowartAtk2": WeaponDef(
        name="Alpha Snowart Shot", weapon_type="artillery",
        damage=3, range_min=2,
    ),
    "BurnbugAtk1": WeaponDef(
        name="Burnbug Strike", weapon_type="melee",
        damage=1, fire=True,
    ),
    "BurnbugAtk2": WeaponDef(
        name="Alpha Burnbug Strike", weapon_type="melee",
        damage=3, fire=True,
    ),

    # ── Bosses ───────────────────────────────────────────────────────
    "FireflyAtkB": WeaponDef(
        name="Firefly Boss Shot", weapon_type="projectile",
        damage=4, range_max=0,
    ),
    # Scorpion Leader: Massive Spinneret. Self-AOE — 2 dmg to all 4
    # cardinal adjacent tiles, push outward, web each target (grapple
    # "hold" in Lua = immobilizes until pushed away).
    "ScorpionAtkB": WeaponDef(
        name="Massive Spinneret", weapon_type="self_aoe",
        damage=2, push="outward", web=True,
        aoe_adjacent=True, aoe_center=False,
    ),
    # Beetle Leader: Flaming Abdomen. Charges in a line, 3 damage +
    # forward push to target, lights every passed tile on Fire
    # (final resting tile excluded per wiki).
    "BeetleAtkB": WeaponDef(
        name="Flaming Abdomen", weapon_type="charge",
        damage=3, push="forward", fire=True, charge=True,
    ),

    # ── Shamans (support/buff — no direct damage) ───────────────────
    "ShamanAtk1": WeaponDef(
        name="Shaman Buff", weapon_type="support",
        damage=0, targets_allies=True,
    ),
    "ShamanAtk2": WeaponDef(
        name="Alpha Shaman Buff", weapon_type="support",
        damage=0, targets_allies=True,
    ),
    "ShamanAtkB": WeaponDef(
        name="Shaman Boss Attack", weapon_type="support",
        damage=0, targets_allies=True,
    ),
}


# Phase 3 parity overlay. Populated by
# ``src.solver.weapon_overrides.apply_runtime`` so the dead-code Python
# simulate path mirrors whatever the Rust solver is running with. Empty
# dict = no overlay → ``get_weapon_def`` reads straight from the static
# tables, preserving the pre-Phase-3 behaviour.
_RUNTIME_OVERRIDES: dict[str, "WeaponDef"] = {}


def set_runtime_overrides(overrides: dict[str, "WeaponDef"]) -> None:
    """Replace the runtime override set. Empty mapping clears it."""
    _RUNTIME_OVERRIDES.clear()
    _RUNTIME_OVERRIDES.update(overrides)


def clear_runtime_overrides() -> None:
    _RUNTIME_OVERRIDES.clear()


def get_weapon_def(weapon_id: str) -> WeaponDef | None:
    """Look up weapon definition by ID, honoring any runtime overlay."""
    override = _RUNTIME_OVERRIDES.get(weapon_id)
    if override is not None:
        return override
    return WEAPON_DEFS.get(weapon_id) or ENEMY_WEAPON_DEFS.get(weapon_id)


def get_weapon_name(weapon_id: str) -> str:
    """Get human-readable weapon name."""
    w = get_weapon_def(weapon_id)
    return w.name if w else weapon_id


# Reverse lookup: display name -> internal weapon ID.
# Built lazily on first call. Used when Rust solver output only has display names.
_NAME_TO_ID: dict[str, str] | None = None


def weapon_name_to_id(display_name: str) -> str:
    """Convert a weapon display name (e.g. 'Titan Fist') to its internal ID
    (e.g. 'Prime_Punchmech').

    Falls back to the input string if no match is found.
    Also handles 'Repair' -> '_REPAIR' mapping.
    """
    global _NAME_TO_ID
    if _NAME_TO_ID is None:
        _NAME_TO_ID = {}
        for wid, wdef in WEAPON_DEFS.items():
            _NAME_TO_ID[wdef.name] = wid
        for wid, wdef in ENEMY_WEAPON_DEFS.items():
            _NAME_TO_ID[wdef.name] = wid
        _NAME_TO_ID["Repair"] = "_REPAIR"
    return _NAME_TO_ID.get(display_name, display_name)
