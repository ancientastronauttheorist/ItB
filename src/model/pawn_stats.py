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
    # Base game Vek
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
    "CrabBoss":      PawnStats(move_speed=3, ranged=1, massive=True),
    "Centipede1":    PawnStats(move_speed=2, ranged=1),
    "Centipede2":    PawnStats(move_speed=2, ranged=1),
    "Digger1":       PawnStats(move_speed=3, ranged=0),
    "Digger2":       PawnStats(move_speed=3, ranged=0),
    "Burrower1":     PawnStats(move_speed=4, ranged=0, pushable=False),
    "Burrower2":     PawnStats(move_speed=4, ranged=0, pushable=False),
    "Spider1":       PawnStats(move_speed=2, ranged=0, pushable=False),
    "Spider2":       PawnStats(move_speed=2, ranged=0, pushable=False),
    "Blobber1":      PawnStats(move_speed=2, ranged=1),
    "Blobber2":      PawnStats(move_speed=2, ranged=1),
    # Advanced Edition Vek
    "Bouncer1":      PawnStats(move_speed=3, ranged=0),
    "Bouncer2":      PawnStats(move_speed=3, ranged=0),
    "BouncerBoss":   PawnStats(move_speed=3, ranged=0, armor=True, massive=True, default_weapon="BouncerAtkB"),
    "Moth1":         PawnStats(move_speed=3, flying=True, ranged=1),
    "Moth2":         PawnStats(move_speed=3, flying=True, ranged=1),
    "Mosquito1":     PawnStats(move_speed=4, flying=True, ranged=0),
    "Mosquito2":     PawnStats(move_speed=4, flying=True, ranged=0),
    "Gastropod1":    PawnStats(move_speed=2, ranged=1),
    "Gastropod2":    PawnStats(move_speed=3, ranged=1),
    "Starfish1":     PawnStats(move_speed=3, ranged=0),
    "Starfish2":     PawnStats(move_speed=3, ranged=0),
    "Tumblebug1":    PawnStats(move_speed=3, ranged=0),
    "Tumblebug2":    PawnStats(move_speed=3, ranged=0),
    "Plasmodia1":    PawnStats(move_speed=2, ranged=1),
    "Plasmodia2":    PawnStats(move_speed=2, ranged=1),
    # Objective / special Vek
    "GlowingScorpion": PawnStats(move_speed=3, ranged=0),
    # Vek Bosses (Hive Leaders): Massive + water-immune per Hive Leader trait.
    "ScorpionBoss":  PawnStats(move_speed=3, massive=True, ranged=0),
    # Pinnacle bots
    "Snowtank1":     PawnStats(move_speed=3, ranged=0),
    "Snowtank2":     PawnStats(move_speed=3, ranged=0),
    "Snowart1":      PawnStats(move_speed=3, ranged=1),
    "Snowart2":      PawnStats(move_speed=3, ranged=1),
    "Burnbug1":      PawnStats(move_speed=2, ranged=1),
    "Burnbug2":      PawnStats(move_speed=2, ranged=1),
    # Burnbug Leader (a.k.a. Gastropod Leader) — Archive Inc Corp HQ finale boss.
    # Per `scripts/advanced/bosses/burnbug.lua`: Health=6, MoveSpeed=3, Ranged=1,
    # Massive=true, Tier=BOSS, SkillList={"BurnbugAtkB"}.
    "BurnbugBoss":   PawnStats(move_speed=3, ranged=1, massive=True,
                               default_weapon="BurnbugAtkB"),
    # Pinnacle Bot Leader (Mission_BotBoss / Pinnacle Robotics finale).
    # Per `scripts/missions/bosses/bot.lua`:
    #   BotBoss: Health=5, MoveSpeed=3, Massive, SelfHeal, SkillList=
    #     {"SnowBossAtk", "BossHeal"}. Skill 1 fires when full HP, skill 2
    #     ("BossHeal") fires when damaged (`Pawn:IsDamaged()` branch in
    #     BotBoss:GetWeapon). Bridge dispatch logic at
    #     `rust_solver/src/enemy.rs:599-607` mirrors the lua selection.
    #   BotBoss2: BotBoss:new{Health=6, SkillList={"SnowBossAtk2", "BossHeal"}}.
    #     Phase-2 form with stronger Vk8 Rockets Mk IV.
    "BotBoss":       PawnStats(move_speed=3, massive=True,
                               default_weapon="SnowBossAtk"),
    "BotBoss2":      PawnStats(move_speed=3, massive=True,
                               default_weapon="SnowBossAtk2"),
    # Psions
    "Jelly_Health1": PawnStats(move_speed=2, flying=True, leader="LEADER_HEALTH", pushable=False),
    "Jelly_Armor1":  PawnStats(move_speed=2, flying=True, leader="LEADER_ARMOR", pushable=False),
    "Jelly_Regen1":  PawnStats(move_speed=2, flying=True, leader="LEADER_REGEN", pushable=False),
    "Jelly_Explode1":PawnStats(move_speed=2, flying=True, leader="LEADER_EXPLODE", pushable=False),
    "Jelly_Lava1":   PawnStats(move_speed=2, flying=True, leader="LEADER_TENTACLE", pushable=False),
    # Advanced Edition Psions
    "Jelly_Boost1":  PawnStats(move_speed=2, flying=True, leader="LEADER_BOOST", pushable=False),
    "Jelly_Fire1":   PawnStats(move_speed=2, flying=True, leader="LEADER_FIRE", pushable=False),
    "Jelly_Spider1": PawnStats(move_speed=2, flying=True, leader="LEADER_SPIDER", pushable=False),
    # Bosses
    "FireflyBoss":   PawnStats(move_speed=3, ranged=1, massive=True),
    "BeetleBoss":    PawnStats(move_speed=3, ranged=0, massive=True),
    # Hornet Leader — Mission_HornetBoss (Hive Leader corp HQ) + appears in
    # Mission_Final / Mission_Final_Cave BossList. Per
    # `scripts/missions/bosses/hornet.lua:11-25`: Health=6, MoveSpeed=3,
    # Massive, Flying, Ranged=1, SkillList={"HornetAtkB"} (Super Stinger:
    # 3-tile line, 2 dmg per tile). Without this entry the engine treated
    # HornetBoss as a default 3-move melee Vek instead of a 5-move-equivalent
    # flying massive boss, mispredicting reachable threats every Final_Cave
    # turn that spawned the Hornet Leader.
    "HornetBoss":    PawnStats(move_speed=3, ranged=1, massive=True, flying=True,
                               default_weapon="HornetAtkB"),
    # Spider Leader — Mission_SpiderBoss. Per
    # `scripts/missions/bosses/spider.lua:50-67`: Health=6, MoveSpeed=2,
    # Massive, Jumper, IgnoreSmoke, Ranged=1, SkillList={} (passive — its
    # SpiderBoss_Tooltip runs `Mission:FlyingSpawns(...,"SpiderlingEgg1")` to
    # drop 3 eggs each turn). Already mapped to WId::SpiderAtk2 in
    # rust_solver/src/weapons.rs::enemy_weapon_for_type.
    "SpiderBoss":    PawnStats(move_speed=2, ranged=1, massive=True,
                               jumper=True, ignore_smoke=True,
                               default_weapon="SpiderAtk2"),
    # Large Goo — Mission_BlobBoss. Per `scripts/missions/bosses/goo.lua`:
    # BlobBoss: HP=3, Move=3, Massive, Ranged=0, SkillList={"BlobBossAtk"}
    # (4-dmg adjacent squish). DeathSpawn=BlobBossMed (HP=2) → BlobBossSmall
    # (HP=1) chain.
    "BlobBoss":      PawnStats(move_speed=3, ranged=0, massive=True,
                               default_weapon="BlobBossAtk"),
    "BlobBossMed":   PawnStats(move_speed=3, ranged=0, massive=True,
                               default_weapon="BlobBossAtkMed"),
    "BlobBossSmall": PawnStats(move_speed=3, ranged=0, massive=True,
                               default_weapon="BlobBossAtkSmall"),
    # Shaman / Slug Leader — Mission_ShamanBoss. Per
    # `scripts/advanced/bosses/shaman.lua:17-31`: Health=5, MoveSpeed=2,
    # Massive, Ranged=1, VoidShockImmune, SkillList={"ShamanAtkB"} (drops a
    # TotemB minion). Mapped to BeetleAtkB in rust enemy_weapon_for_type as
    # the closest 4-dmg melee approximation.
    "ShamanBoss":    PawnStats(move_speed=2, ranged=1, massive=True,
                               default_weapon="ShamanAtkB"),
    # Psion Abomination — Mission_JellyBoss (R.S.T. Corporate HQ finale).
    # Per `scripts/missions/bosses/psion.lua:14-27`: Health=5, MoveSpeed=3,
    # Flying, Leader=LEADER_BOSS, no offensive SkillList (Tooltip "Overpowered"
    # is purely passive: all OTHER Vek gain +1 HP, Regeneration, and explode
    # on death — i.e. stacks LEADER_HEALTH + LEADER_REGEN + LEADER_EXPLODE
    # auras simultaneously). Pushable per game (no Pushable=false flag on
    # the lua def). The Psion-aura combination is not yet wired in
    # rust_solver — the boss is only registered to gate the unknown-pawn
    # fallback. Aura simulation is a follow-up sim-version bump.
    "Jelly_Boss":    PawnStats(move_speed=3, flying=True, leader="LEADER_BOSS",
                               pushable=True),
    # Minor enemies
    "Spiderling1":   PawnStats(move_speed=3, minor=True, ranged=0),
    "Spiderling2":   PawnStats(move_speed=3, minor=True, ranged=0),
    "Blob1":         PawnStats(move_speed=0, minor=True, ranged=0),
    "Blob2":         PawnStats(move_speed=0, minor=True, ranged=0),
    "BlobMini":      PawnStats(move_speed=0, minor=True, ranged=0),  # legacy alias
    "ShellPsion1":   PawnStats(move_speed=2, flying=True, minor=True, leader="LEADER_TENTACLE"),
}

# Neutral / environmental pawns
NEUTRAL_STATS = {
    "Dam_Pawn":          PawnStats(move_speed=0, massive=True, pushable=False),
    "Train_Pawn":        PawnStats(move_speed=0, massive=True, pushable=False),
    "Train_Armored":     PawnStats(move_speed=0, massive=True, armor=True,
                                   pushable=False, ignore_fire=True,
                                   ignore_smoke=True,
                                   default_weapon="Armored_Train_Move"),
    "Train_Armored_Damaged": PawnStats(move_speed=0, massive=True, armor=True,
                                       pushable=False, ignore_fire=True),
    "Filler_Pawn":       PawnStats(move_speed=0, pushable=False),
    # Digger rock wall: bridge exposes the spawned rock as a neutral "Wall"
    # pawn (1 HP, Move 0, no weapon) rather than terrain.
    "Wall":              PawnStats(move_speed=0),
    # Freeze Tank (Pinnacle Robotics) — friendly NPC on Mission_FreezeBots
    # ("Pinnacle Garden"). Per scripts/missions/snow/snow_helper.lua:
    #   Health=1, MoveSpeed=4, SkillList={"Pinnacle_FreezeTank"},
    #   DefaultTeam=TEAM_PLAYER, Corpse=false, Corporate=true.
    # Wanders the board firing freeze projectiles at enemies. Mirrors the
    # Filler_Pawn pattern (player-team NPC, not is_mech) so the evaluator
    # applies the friendly_npc_killed (-20000) penalty rather than the
    # mech_killed (-150000) one. Pushable per game (no Pushable=false flag).
    "Freeze_Tank":       PawnStats(move_speed=4, ranged=1, pushable=True,
                                   default_weapon="Pinnacle_FreezeTank"),
    "SatelliteRocket":   PawnStats(move_speed=0, massive=True, pushable=False),
    "ArchiveArtillery":  PawnStats(move_speed=0, ranged=1),
    "Archive_Tank":      PawnStats(move_speed=0, ranged=1),
    # Mission_Trapped Decoy Building: player-team, 2 HP, immobile,
    # non-grid, non-pushable, self-destruct weapon.
    "Trapped_Building":  PawnStats(move_speed=0, ranged=1, pushable=False,
                                   ignore_smoke=True,
                                   default_weapon="Trapped_Explode"),
    # A.C.I.D. Tank: single-use deployable NPC (time-pod / shop reward).
    # 1 HP base (3 with +2 HP upgrade), Move 3, Normal mass, pushable.
    # Player-controlled same as a mech.
    "Acid_Tank":         PawnStats(move_speed=3, ranged=1),
    # Renfield Bomb (Mission_Final_Cave / final caverns): friendly objective
    # NPC that explodes on a fixed countdown to clear all enemies on the map.
    # Per `scripts/missions/final/mission_final_two.lua:179-188`:
    #   Health = 4, Neutral = true, Corpse = false, IgnoreFire = true,
    #   MoveSpeed = 0, DefaultTeam = TEAM_PLAYER, IsPortrait = false.
    # The bomb is the win-condition objective — defending it until detonation
    # ends the mission. No SkillList: it never attacks, only sits and ticks
    # down a turn-limit counter (`Mission_Final_Cave.TurnLimit + 2` per drop).
    # Mirrors the Filler_Pawn pattern (player-team NPC, not is_mech) so the
    # evaluator's `friendly_npc_killed` (-20000) penalty fires on death.
    # `bigbomb_alive` (Rust Board) layers a much larger survival bonus on top
    # since losing the bomb fails the mission. Despite being immobile, live
    # final-cave evidence showed it can be pushed/bumped by Vulcan Artillery.
    "BigBomb":           PawnStats(move_speed=0, pushable=True, ignore_fire=True),
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
