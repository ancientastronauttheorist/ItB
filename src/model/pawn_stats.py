"""Static pawn stats from the game's pawns.lua script.

These values are NOT in save files — they must be looked up by pawn type.
The solver needs these to compute movement range, determine if a unit
can fly over water, etc.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PawnStats:
    """Static properties of a pawn type."""
    move_speed: int = 3
    flying: bool = False
    jumper: bool = False
    teleporter: bool = False
    armor: bool = False
    massive: bool = False
    minor: bool = False
    leader: str = ""         # Psion type: LEADER_HEALTH, etc.
    ranged: int = 0          # 0=melee, 1=ranged
    pushable: bool = True
    ignore_smoke: bool = False
    ignore_fire: bool = False
    default_weapon: str = ""
    class_type: str = ""     # Prime, Brute, Ranged, Science


# Mechs
MECH_STATS = {
    "PunchMech":     PawnStats(move_speed=3, massive=True, class_type="Prime", default_weapon="Prime_Punchmech"),
    "TankMech":      PawnStats(move_speed=3, massive=True, class_type="Brute", default_weapon="Brute_Tankmech"),
    "ArtiMech":      PawnStats(move_speed=3, massive=True, class_type="Ranged", default_weapon="Ranged_Artillerymech"),
    "JudoMech":      PawnStats(move_speed=4, massive=True, armor=True, class_type="Prime", default_weapon="Prime_Shift"),
    "DStrikeMech":   PawnStats(move_speed=3, massive=True, class_type="Ranged", default_weapon="Ranged_Defensestrike"),
    "GravMech":      PawnStats(move_speed=4, massive=True, class_type="Science", default_weapon="Science_Gravwell"),
    "RocketMech":    PawnStats(move_speed=3, massive=True, class_type="Ranged", default_weapon="Ranged_Rocket"),
    "JetMech":       PawnStats(move_speed=4, massive=True, flying=True, class_type="Brute", default_weapon="Brute_Jetmech"),
    "PulseMech":     PawnStats(move_speed=4, massive=True, class_type="Science", default_weapon="Science_Repulse"),
    "FlameMech":     PawnStats(move_speed=3, massive=True, ignore_fire=True, class_type="Prime", default_weapon="Prime_Flamethrower"),
    "IgniteMech":    PawnStats(move_speed=3, massive=True, class_type="Ranged", default_weapon="Ranged_Ignite"),
    "TeleMech":      PawnStats(move_speed=4, massive=True, flying=True, teleporter=True, class_type="Science", default_weapon="Science_Swap"),
    "LaserMech":     PawnStats(move_speed=3, massive=True, class_type="Prime", default_weapon="Prime_Lasermech"),
    "ChargeMech":    PawnStats(move_speed=3, massive=True, class_type="Brute", default_weapon="Brute_Beetle"),
    "ScienceMech":   PawnStats(move_speed=4, massive=True, flying=True, class_type="Science", default_weapon="Science_Pullmech"),
    "GuardMech":     PawnStats(move_speed=4, massive=True, class_type="Prime", default_weapon="Prime_ShieldBash"),
    "MirrorMech":    PawnStats(move_speed=3, massive=True, class_type="Brute", default_weapon="Brute_Mirrorshot"),
    "IceMech":       PawnStats(move_speed=3, massive=True, flying=True, class_type="Ranged", default_weapon="Ranged_Ice"),
    "ElectricMech":  PawnStats(move_speed=3, massive=True, class_type="Prime", default_weapon="Prime_Lightning"),
    "WallMech":      PawnStats(move_speed=3, massive=True, armor=True, class_type="Brute", default_weapon="Brute_Grapple"),
    "RockartMech":   PawnStats(move_speed=3, massive=True, class_type="Ranged", default_weapon="Ranged_Rockthrow"),
    "LeapMech":      PawnStats(move_speed=4, massive=True, class_type="Prime", default_weapon="Prime_Leap"),
    "UnstableTank":  PawnStats(move_speed=3, massive=True, class_type="Brute", default_weapon="Brute_Unstable"),
    "NanoMech":      PawnStats(move_speed=4, massive=True, flying=True, class_type="Science", default_weapon="Science_AcidShot"),
    # Advanced Edition mechs
    "BeetleMech":    PawnStats(move_speed=3, massive=True, class_type="Prime", default_weapon="Prime_Beetle"),
    "HydroMech":     PawnStats(move_speed=4, massive=True, class_type="Science", default_weapon="Science_Hydro"),
    "BottleMech":    PawnStats(move_speed=3, massive=True, class_type="Ranged", default_weapon="Ranged_RocketShower"),
}

# Vek (enemies)
VEK_STATS = {
    "Scorpion1":     PawnStats(move_speed=3, ranged=0),
    "Scorpion2":     PawnStats(move_speed=3, ranged=0),
    "Firefly1":      PawnStats(move_speed=2, ranged=1),
    "Firefly2":      PawnStats(move_speed=2, ranged=1),
    "Hornet1":       PawnStats(move_speed=5, flying=True, ranged=0),
    "Hornet2":       PawnStats(move_speed=5, flying=True, ranged=0),
    "Leaper1":       PawnStats(move_speed=4, jumper=True, minor=True, ranged=0),
    "Leaper2":       PawnStats(move_speed=4, jumper=True, ranged=0),
    "Beetle1":       PawnStats(move_speed=2, ranged=0, massive=True),
    "Beetle2":       PawnStats(move_speed=2, ranged=0, massive=True),
    "Scarab1":       PawnStats(move_speed=3, ranged=1),
    "Scarab2":       PawnStats(move_speed=3, ranged=1),
    "Crab1":         PawnStats(move_speed=3, ranged=1),
    "Crab2":         PawnStats(move_speed=3, ranged=1),
    "Centipede1":    PawnStats(move_speed=2, ranged=1),
    "Centipede2":    PawnStats(move_speed=2, ranged=1),
    "Digger1":       PawnStats(move_speed=3, ranged=0),
    "Digger2":       PawnStats(move_speed=3, ranged=0),
    "Spider1":       PawnStats(move_speed=2, ranged=0, pushable=False),
    "Spider2":       PawnStats(move_speed=2, ranged=0, pushable=False),
    "Blobber1":      PawnStats(move_speed=2, ranged=1, pushable=False),
    "Blobber2":      PawnStats(move_speed=2, ranged=1, pushable=False),
    # Psions
    "Jelly_Health1": PawnStats(move_speed=2, flying=True, leader="LEADER_HEALTH", pushable=False),
    "Jelly_Armor1":  PawnStats(move_speed=2, flying=True, leader="LEADER_ARMOR", pushable=False),
    "Jelly_Regen1":  PawnStats(move_speed=2, flying=True, leader="LEADER_REGEN", pushable=False),
    "Jelly_Explode1":PawnStats(move_speed=2, flying=True, leader="LEADER_EXPLODE", pushable=False),
    "Jelly_Lava1":   PawnStats(move_speed=2, flying=True, leader="LEADER_TENTACLE", pushable=False),
    # Bosses
    "Moth1":         PawnStats(move_speed=5, flying=True, massive=True, ranged=0),
    "Moth2":         PawnStats(move_speed=5, flying=True, massive=True, ranged=0),
    # Minor enemies
    "Spiderling1":   PawnStats(move_speed=3, minor=True, ranged=0),
    "BlobMini":      PawnStats(move_speed=0, minor=True, ranged=0),
    "ShellPsion1":   PawnStats(move_speed=2, flying=True, minor=True, leader="LEADER_TENTACLE"),
}

# Neutral / environmental pawns
NEUTRAL_STATS = {
    "Dam_Pawn":          PawnStats(move_speed=0, massive=True, pushable=False),
    "Train_Pawn":        PawnStats(move_speed=0, massive=True, pushable=False),
    "SatelliteRocket":   PawnStats(move_speed=0, massive=True, pushable=False),
    "ArchiveArtillery":  PawnStats(move_speed=0, ranged=1),
    "Archive_Tank":      PawnStats(move_speed=0, ranged=1),
}

# Combined lookup
ALL_PAWN_STATS: dict[str, PawnStats] = {}
ALL_PAWN_STATS.update(MECH_STATS)
ALL_PAWN_STATS.update(VEK_STATS)
ALL_PAWN_STATS.update(NEUTRAL_STATS)


def get_pawn_stats(pawn_type: str) -> PawnStats:
    """Look up static stats for a pawn type.

    Returns default stats if type is unknown.
    """
    return ALL_PAWN_STATS.get(pawn_type, PawnStats())


def get_effective_move_speed(pawn_type: str, move_power: int = 0) -> int:
    """Get actual move speed including reactor upgrades."""
    base = get_pawn_stats(pawn_type).move_speed
    return base + move_power
