"""Pawn-stats coverage for Mission_Final_Cave & boss-mission enemies.

Sim v36 batch landed `BigBomb` and known_types entries for the Final_Cave
boss roster, but several boss/Psion pawn types were still missing from
`src/model/pawn_stats.py` so they fell through to the default `PawnStats()`
(move_speed=3, ranged=0, no flags). That meant:

  - HornetBoss (Hornet Leader): treated as 3-move melee instead of
    5-tile-equivalent flying boss with Super Stinger artillery.
  - SpiderBoss / BlobBoss / ShamanBoss / Jelly_Boss: missing massive +
    flying flags led to wrong reachability + push predictions.
  - Crab1/Crab2 / Hornet1/Hornet2 / Blob1/Blobber1 family: ALREADY
    correctly registered (sanity-check tests guard against regressions
    if the table is renamed/restructured).

Canonical stats sourced from the game's lua scripts under
`Into the Breach.app/Contents/Resources/scripts/`:
  - `pawns.lua` (Hornet1/2, Crab1/2, Blob1/2, Blobber1/2, Jelly_Lava1)
  - `missions/bosses/hornet.lua` (HornetBoss)
  - `missions/bosses/spider.lua` (SpiderBoss)
  - `missions/bosses/goo.lua` (BlobBoss / BlobBossMed / BlobBossSmall)
  - `missions/bosses/psion.lua` (Jelly_Boss)
  - `advanced/bosses/shaman.lua` (ShamanBoss)
"""
from __future__ import annotations

from src.model.pawn_stats import (
    ALL_PAWN_STATS,
    VEK_STATS,
    get_pawn_stats,
)


# ── Mission_Final_Cave boss roster (post-v36) ────────────────────────────


def test_hornet_boss_has_canonical_stats() -> None:
    """HornetBoss (Hornet Leader) per `missions/bosses/hornet.lua:11-25`:
    Health=6, MoveSpeed=3, Massive=true, Flying=true, Ranged=1,
    SkillList={"HornetAtkB"} (Super Stinger). Massive lets it walk over
    water-killed terrain; Flying lets it cross chasms; default_weapon must
    be "HornetAtkB" so the bridge can resolve the Super Stinger when the
    queued attack is missing.
    """
    s = get_pawn_stats("HornetBoss")
    assert s.move_speed == 3
    assert s.massive is True
    assert s.flying is True
    assert s.ranged == 1
    assert s.default_weapon == "HornetAtkB"


def test_spider_boss_has_canonical_stats() -> None:
    """SpiderBoss per `missions/bosses/spider.lua:50-67`:
    Health=6, MoveSpeed=2, Massive, Jumper, IgnoreSmoke, Ranged=1.
    The `Jumper` flag is critical for movement modeling — the boss leaps
    over units/terrain rather than pathing around them.
    """
    s = get_pawn_stats("SpiderBoss")
    assert s.move_speed == 2
    assert s.massive is True
    assert s.jumper is True
    assert s.ignore_smoke is True
    assert s.ranged == 1


def test_blob_boss_chain_has_canonical_stats() -> None:
    """Large Goo chain per `missions/bosses/goo.lua`:
    BlobBoss → BlobBossMed (DeathSpawn) → BlobBossSmall (DeathSpawn).
    All three: Move=3, Massive, Ranged=0, melee skill.
    """
    big = get_pawn_stats("BlobBoss")
    med = get_pawn_stats("BlobBossMed")
    sml = get_pawn_stats("BlobBossSmall")
    for s in (big, med, sml):
        assert s.move_speed == 3
        assert s.massive is True
        assert s.ranged == 0
    assert big.default_weapon == "BlobBossAtk"
    assert med.default_weapon == "BlobBossAtkMed"
    assert sml.default_weapon == "BlobBossAtkSmall"


def test_shaman_boss_has_canonical_stats() -> None:
    """ShamanBoss per `advanced/bosses/shaman.lua:17-31`:
    Health=5, MoveSpeed=2, Massive, Ranged=1, VoidShockImmune,
    SkillList={"ShamanAtkB"} (drops TotemB minion).
    """
    s = get_pawn_stats("ShamanBoss")
    assert s.move_speed == 2
    assert s.massive is True
    assert s.ranged == 1
    assert s.default_weapon == "ShamanAtkB"


def test_jelly_boss_has_canonical_stats() -> None:
    """Jelly_Boss (Psion Abomination) per `missions/bosses/psion.lua:14-27`:
    Health=5, MoveSpeed=3, Flying, Leader=LEADER_BOSS, NO offensive
    SkillList (passive aura only — Overpowered tooltip stacks +1 HP +
    Regen + Explode-on-death across all OTHER Vek). Pushable per game.
    """
    s = get_pawn_stats("Jelly_Boss")
    assert s.move_speed == 3
    assert s.flying is True
    assert s.leader == "LEADER_BOSS"
    assert s.pushable is True
    # No offensive default_weapon — Jelly_Boss is purely passive and the
    # bridge sends queued_target_x=-1, which the rust dispatcher's
    # passive-Vek skip handles at enemy.rs:514.
    assert s.default_weapon == ""


def test_bigbomb_is_immobile_but_pushable() -> None:
    """Renfield Bomb cannot move on its own, but live final-cave evidence
    showed it can be pushed/bumped by player weapons such as Vulcan Artillery.
    """
    s = get_pawn_stats("BigBomb")
    assert s.move_speed == 0
    assert s.pushable is True
    assert s.ignore_fire is True


# ── Already-registered Mission_Final_Cave enemies (regression guards) ────


def test_hornet1_hornet2_already_registered() -> None:
    """Hornet1/Hornet2 per `pawns.lua:925-957`: HP=2/4, MoveSpeed=5,
    Flying, melee. The 5-tile flying move is critical for threat reach.
    """
    h1 = get_pawn_stats("Hornet1")
    h2 = get_pawn_stats("Hornet2")
    for h in (h1, h2):
        assert h.move_speed == 5
        assert h.flying is True
        assert h.ranged == 0


def test_crab1_crab2_already_registered() -> None:
    """Crab1/Crab2 per `pawns.lua:824-855`: HP=3/5, MoveSpeed=3,
    Ranged=1 (Crab Artillery — fires AOE_BEHIND projectile).
    """
    c1 = get_pawn_stats("Crab1")
    c2 = get_pawn_stats("Crab2")
    for c in (c1, c2):
        assert c.move_speed == 3
        assert c.ranged == 1


def test_blob1_blob2_already_registered() -> None:
    """Blob1/Blob2 per `pawns.lua:608-636`: HP=1, MoveSpeed=0, Minor.
    Self-detonating: uses BlobAtk1 (1 dmg AoE_CENTER) / BlobAtk2 (alpha
    2 dmg + 4-cardinal). Move=0 means they sit until detonation.
    """
    b1 = get_pawn_stats("Blob1")
    b2 = get_pawn_stats("Blob2")
    for b in (b1, b2):
        assert b.move_speed == 0
        assert b.minor is True


def test_blobber1_blobber2_already_registered() -> None:
    """Blobber1/Blobber2 per `pawns.lua:573-603`: HP=3/4, MoveSpeed=2,
    Ranged=1 (artillery that spawns Blob1/Blob2 at target tile).
    """
    bb1 = get_pawn_stats("Blobber1")
    bb2 = get_pawn_stats("Blobber2")
    for bb in (bb1, bb2):
        assert bb.move_speed == 2
        assert bb.ranged == 1


def test_jelly_lava1_already_registered() -> None:
    """Jelly_Lava1 (Psion Tyrant) per `pawns.lua:1014-1018`: HP=2,
    MoveSpeed=2, Flying, Leader=LEADER_TENTACLE (passive: 1 dmg/turn
    to ALL player units — terrain-piercing, ignores smoke). The
    `tyrant_psion` Board flag is set by `serde_bridge.rs:634-640` and
    the aura damage is applied by `enemy.rs:1031-1052`.
    """
    s = get_pawn_stats("Jelly_Lava1")
    assert s.move_speed == 2
    assert s.flying is True
    assert s.leader == "LEADER_TENTACLE"
    assert s.pushable is False


# ── Combined-table integrity guard ───────────────────────────────────────


def test_no_boss_falls_through_to_default_pawnstats() -> None:
    """All pawn types ending in 'Boss' that the rust simulator references
    via enemy_weapon_for_type MUST also exist in pawn_stats.py — otherwise
    Python movement/threat planning falls back to the default-3-move-melee
    template even though the rust sim has the right weapon mapping.

    The rust mappings are at `rust_solver/src/weapons.rs::enemy_weapon_for_type`.
    """
    # Bosses currently mapped on the rust side. Any future addition there
    # MUST be mirrored in pawn_stats.py — this test guards against the
    # reverse drift.
    rust_mapped_bosses = [
        "ScorpionBoss", "FireflyBoss", "BeetleBoss", "HornetBoss",
        "SpiderBoss", "ShamanBoss",
        "BlobBoss", "BlobBossMed", "BlobBossSmall",
        "BurnbugBoss",
        "BotBoss", "BotBoss2",  # Pinnacle Bot Leader phase 1 / 2
    ]
    missing = [b for b in rust_mapped_bosses if b not in ALL_PAWN_STATS]
    assert not missing, (
        f"Rust-mapped bosses missing from pawn_stats.py: {missing}. "
        "Without an entry the boss falls through to default PawnStats() "
        "(move_speed=3, ranged=0, not massive/flying), corrupting reach "
        "predictions and grid-defense heuristics."
    )


def test_jelly_psion_family_complete() -> None:
    """All Jelly_* Psion variants (vanilla + Advanced Edition + boss)
    MUST live in VEK_STATS so movement/threat code resolves their flying
    flag. Drift here causes Psions to be treated as ground units and
    blocks the solver from telegraphing-tile reasoning over chasm/water.
    """
    expected = [
        # Vanilla
        "Jelly_Health1", "Jelly_Armor1", "Jelly_Regen1",
        "Jelly_Explode1", "Jelly_Lava1",
        # Advanced Edition
        "Jelly_Boost1", "Jelly_Fire1", "Jelly_Spider1",
        # Psion Abomination
        "Jelly_Boss",
    ]
    for j in expected:
        assert j in VEK_STATS, f"Missing {j} from VEK_STATS"
        s = VEK_STATS[j]
        assert s.flying is True, f"{j} should be Flying per game lua"
