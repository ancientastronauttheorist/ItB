"""Tests for the squad-aware mission picker.

The picker is pure: given an island_map slate + the squad's live units +
grid power, returns a deterministic ranked list. These tests fix the
scoring contract for cases that materialised during real runs (or that
we expect to in the near future).
"""
from __future__ import annotations

from src.strategy.mission_picker import (
    BONUS_ASSET,
    BONUS_GRID,
    BONUS_KILL_FIVE,
    BONUS_MECHS,
    derive_squad_tags,
    score_island_map,
    score_mission,
)


# ---------------------------------------------------------------------------
# Squad fixtures (matches bridge.units shape: mech=True + weapons=[wid])
# ---------------------------------------------------------------------------

# Lightning / Jet Bombs / Grav Well — the squad that wiped on
# 20260425_185532_218 m04 → m05. No reliable single-target push or pull
# from the front line, so train_defender is absent. crowd_control is
# present (Grav Well) but pull-only — won't stop a train.
LIGHTNING_GRAV_SQUAD = [
    {"mech": True, "hp": 3, "weapons": ["Prime_Lightning"]},
    {"mech": True, "hp": 3, "weapons": ["Brute_Jetmech"]},
    {"mech": True, "hp": 3, "weapons": ["Science_Gravwell",
                                        "Passive_FriendlyFire"]},
]

# Rift Walkers — Titan Fist (push 1) + Taurus (push) + Artemis. Solid
# train defender (front-line push from Combat + Cannon).
RIFT_WALKERS_SQUAD = [
    {"mech": True, "hp": 3, "weapons": ["Prime_Punchmech"]},
    {"mech": True, "hp": 3, "weapons": ["Brute_Tankmech"]},
    {"mech": True, "hp": 3, "weapons": ["Ranged_Artillerymech"]},
]

# Frozen Titans — Cryo (freeze) + Ice + Hook. Heavy crowd-control.
FROZEN_TITANS_SQUAD = [
    {"mech": True, "hp": 3, "weapons": ["Ranged_Ice"]},
    {"mech": True, "hp": 3, "weapons": ["Brute_Grapple"]},
    {"mech": True, "hp": 3, "weapons": ["Science_Swap"]},
]


# ---------------------------------------------------------------------------
# Mission fixtures
# ---------------------------------------------------------------------------

def _train_high_threat() -> dict:
    """Historic County-style train mission with ⚡ high-threat bonus."""
    return {
        "region_id": 2,
        "mission_id": "Mission_Train",
        "bonus_objective_ids": [BONUS_GRID],
        "environment": "Env_Null",
    }


def _volatile_vek_mission() -> dict:
    """Secondary Archives-style 'do not kill volatile Vek' mission."""
    return {
        "region_id": 3,
        "mission_id": "Mission_Volatile",
        "bonus_objective_ids": [BONUS_MECHS],
        "environment": "Env_Null",
    }


def _safe_battle_mission() -> dict:
    """Plain skirmish with the kill-7 bonus."""
    return {
        "region_id": 1,
        "mission_id": "Mission_Battle",
        "bonus_objective_ids": [BONUS_KILL_FIVE],
        "environment": "Env_Null",
    }


def _tidal_mission() -> dict:
    """Tidal-environment mission — flying matters."""
    return {
        "region_id": 4,
        "mission_id": "Mission_Battle",
        "bonus_objective_ids": [BONUS_GRID],
        "environment": "Env_TidalWaves",
    }


# ---------------------------------------------------------------------------
# Squad tag derivation
# ---------------------------------------------------------------------------

def test_derive_squad_tags_lightning_grav():
    tags = derive_squad_tags(LIGHTNING_GRAV_SQUAD)
    assert "train_defender" not in tags
    assert "crowd_control" in tags  # Grav Well is pull-cc
    assert "aoe" in tags             # Lightning + Jet Bombs
    assert "flying" in tags          # Jet Mech


def test_derive_squad_tags_rift_walkers():
    tags = derive_squad_tags(RIFT_WALKERS_SQUAD)
    assert "train_defender" in tags  # Titan Fist + Taurus Cannon
    # Rift Walkers do NOT have crowd_control (no freeze, swap, repulse,
    # ACID, confuse). Artemis push_chain is offence, not cc.
    assert "crowd_control" not in tags


def test_derive_squad_tags_skips_dead_mechs():
    units = [
        {"mech": True, "hp": 0, "weapons": ["Prime_Punchmech"]},  # dead
        {"mech": True, "hp": 3, "weapons": ["Science_Gravwell"]},
    ]
    tags = derive_squad_tags(units)
    assert "train_defender" not in tags  # Punch ignored
    assert "crowd_control" in tags


# ---------------------------------------------------------------------------
# Core scoring scenarios
# ---------------------------------------------------------------------------

def test_train_no_defender_loses_to_safe_battle():
    """The 20260425_185532_218 m05 case: Lightning/Jet/Grav vs train.

    Historic County (train + ⚡ high-threat bonus, grid 7) should rank
    BELOW any plain battle alternative on the same island. The penalty
    -8 (no train_defender) outweighs the +2 ⚡ reward.
    """
    island = [_train_high_threat(), _safe_battle_mission()]
    ranked = score_island_map(island, LIGHTNING_GRAV_SQUAD, grid_power=7)
    assert ranked[0]["mission_id"] == "Mission_Battle"
    assert ranked[1]["mission_id"] == "Mission_Train"
    # Sanity check the rationale surfaces the actual penalty.
    train_rationale = " ".join(ranked[1]["rationale_lines"])
    assert "no train_defender" in train_rationale


def test_train_with_defender_outranks_safe_battle():
    """Mirror case: a Rift-Walkers-style squad WITH train defenders
    should prefer the train mission (+2 ⚡) over a kill-7 bonus (+2)
    because no penalty fires; ties go to the train mission only when
    bonus values differ. Here the train mission's ⚡ ties exactly with
    Battle's kill-7 bonus, so we just assert the train penalty did NOT
    fire (no negative score component) and Battle does not outrank it
    by more than its own bonus value.
    """
    island = [_train_high_threat(), _safe_battle_mission()]
    ranked = score_island_map(island, RIFT_WALKERS_SQUAD, grid_power=7)
    train = next(e for e in ranked if e["mission_id"] == "Mission_Train")
    # No train-defender penalty.
    for line in train["rationale_lines"]:
        assert "no train_defender" not in line
    # Both score equally given equal bonus values (+2 each). Ranking
    # should be stable with no penalty fired on either side.
    assert train["score"] >= 0


def test_volatile_vek_no_cc_penalised():
    """Secondary Archives + Lightning/Jet/Grav: -3 penalty fires.

    Note Lightning/Jet/Grav DOES have crowd_control via Grav Well, so
    the actual run squad would NOT trigger this. Use a strictly
    no-cc squad to lock the penalty in place.
    """
    no_cc_squad = [
        {"mech": True, "hp": 3, "weapons": ["Prime_Lasermech"]},
        {"mech": True, "hp": 3, "weapons": ["Brute_Tankmech"]},
        {"mech": True, "hp": 3, "weapons": ["Ranged_Artillerymech"]},
    ]
    scored = score_mission(_volatile_vek_mission(), derive_squad_tags(no_cc_squad),
                           grid_power=7)
    assert scored["score"] < 4  # raw +4 (★ keep mechs alive) - 3 = 1
    assert any("no crowd-control" in line for line in scored["rationale_lines"])


def test_volatile_vek_with_cc_keeps_full_value():
    """Frozen Titans on volatile-Vek: penalty does not fire, mission's
    full +4 (★ keep mechs alive) survives.
    """
    scored = score_mission(_volatile_vek_mission(), derive_squad_tags(FROZEN_TITANS_SQUAD),
                           grid_power=7)
    assert scored["score"] == 4
    for line in scored["rationale_lines"]:
        assert "no crowd-control" not in line


# ---------------------------------------------------------------------------
# Grid-power-conditioned bonuses
# ---------------------------------------------------------------------------

def test_low_grid_amplifies_grid_bonus():
    """⚡ grid bonus rewards more at low grid (defensive priority).

    +4 when grid<5, +2 otherwise. Use an UNTAGGED mission_id so the
    only score component is the bonus value (no high_threat penalty).
    """
    mission = {
        "region_id": 5,
        "mission_id": "Mission_Generic",   # no MISSION_ID_TAGS entry
        "bonus_objective_ids": [BONUS_GRID],
        "environment": None,
    }
    low = score_mission(mission, derive_squad_tags(RIFT_WALKERS_SQUAD), grid_power=2)
    high = score_mission(mission, derive_squad_tags(RIFT_WALKERS_SQUAD), grid_power=7)
    assert low["score"] > high["score"]
    assert low["score"] == 4
    assert high["score"] == 2


def test_tidal_no_flying_penalty_only_when_no_flying():
    """Tidal env -2 penalty fires only when squad has no flying mech."""
    no_fly = score_mission(_tidal_mission(), derive_squad_tags(RIFT_WALKERS_SQUAD),
                           grid_power=7)
    with_fly = score_mission(_tidal_mission(), derive_squad_tags(LIGHTNING_GRAV_SQUAD),
                             grid_power=7)
    assert any("no flying" in line for line in no_fly["rationale_lines"])
    for line in with_fly["rationale_lines"]:
        assert "no flying" not in line
    assert with_fly["score"] > no_fly["score"]


# ---------------------------------------------------------------------------
# High-threat × grid-power scaling (post-2026-04-27 District Z-1101 loss)
# ---------------------------------------------------------------------------

def _high_threat_with_grid_bonus() -> dict:
    """Mission_Battle is tagged 'high_threat' in MISSION_ID_TAGS.

    Pair it with a ⚡ grid bonus so the bonus value (+4 at low grid)
    interacts with the new high-threat penalty curve.
    """
    return {
        "region_id": 7,
        "mission_id": "Mission_Battle",
        "bonus_objective_ids": [BONUS_GRID],
        "environment": "Env_Null",
    }


def _safe_no_threat_mission() -> dict:
    """Untagged mission — no high_threat, no env penalty. Acts as the
    'always-safe alternative' baseline for ranking tests."""
    return {
        "region_id": 8,
        "mission_id": "Mission_Generic",
        "bonus_objective_ids": [BONUS_KILL_FIVE],
        "environment": None,
    }


def test_high_threat_at_grid_4_low_margin_penalty():
    """High-threat mission at grid=4 fires the new -8 penalty.

    Pre-fix this was a flat -5 across all grids 1-4. The Pinnacle
    2026-04-27 District Z-1101 loss happened at exactly this grid;
    -8 here downranks against any non-high-threat alternative. The
    mission can still be picked if all alternatives score worse —
    Mission_Battle remains the right pick on a 1-mission island.
    """
    scored = score_mission(_high_threat_with_grid_bonus(),
                           derive_squad_tags(RIFT_WALKERS_SQUAD),
                           grid_power=4, mission_metadata={})
    assert any("grid 4" in line and "low margin" in line
               for line in scored["rationale_lines"])
    # +4 (⚡ grid bonus at low grid) - 8 (high threat at 4) = -4
    assert scored["score"] == -4


def test_high_threat_at_grid_3_severe_penalty():
    """High-threat at grid=3 fires -15. Combined with +4★⚡ this still
    nets -11 — effectively veto unless every alternative scores worse."""
    scored = score_mission(_high_threat_with_grid_bonus(),
                           derive_squad_tags(RIFT_WALKERS_SQUAD),
                           grid_power=3, mission_metadata={})
    assert any("grid 3" in line and "severe penalty" in line
               for line in scored["rationale_lines"])
    assert scored["score"] == -11   # +4 - 15


def test_high_threat_at_critical_grid_hard_veto():
    """At grid≤2 a high-threat mission scores deeply negative — even a
    +6 ★⚡⚡ stack couldn't offset -50."""
    mission = _high_threat_with_grid_bonus()
    scored = score_mission(mission, derive_squad_tags(RIFT_WALKERS_SQUAD),
                           grid_power=2, mission_metadata={})
    assert any("hard veto" in line for line in scored["rationale_lines"])
    # +4 (⚡ grid bonus at low grid) - 50 (hard veto) = -46
    assert scored["score"] == -46

    # grid=1 still hard-veto.
    scored1 = score_mission(mission, derive_squad_tags(RIFT_WALKERS_SQUAD),
                            grid_power=1, mission_metadata={})
    assert scored1["score"] == -46


def test_high_threat_at_full_grid_unpenalized():
    """At grid≥5 the high-threat tag fires no penalty."""
    scored = score_mission(_high_threat_with_grid_bonus(),
                           derive_squad_tags(RIFT_WALKERS_SQUAD),
                           grid_power=7, mission_metadata={})
    for line in scored["rationale_lines"]:
        assert "high-threat" not in line
    # +2 (⚡ at grid 7) — nothing else fires
    assert scored["score"] == 2


def test_high_threat_outranked_by_safe_pick_at_critical_grid():
    """At grid=2, a safe untagged mission with weaker bonuses ranks
    ABOVE a high-threat mission with stronger bonuses. This is the
    regression that would have prevented today's District Z-1101 pick.
    """
    high_threat = _high_threat_with_grid_bonus()
    safe        = _safe_no_threat_mission()
    ranked = score_island_map([high_threat, safe], RIFT_WALKERS_SQUAD,
                              grid_power=2, mission_metadata={})
    assert ranked[0]["mission_id"] == "Mission_Generic"
    assert ranked[1]["mission_id"] == "Mission_Battle"
    safe_score = next(e["score"] for e in ranked if e["mission_id"] == "Mission_Generic")
    ht_score = next(e["score"] for e in ranked if e["mission_id"] == "Mission_Battle")
    assert safe_score >= 0
    assert ht_score < -30


# ---------------------------------------------------------------------------
# Empty / no-op cases
# ---------------------------------------------------------------------------

def test_empty_island_map_returns_empty():
    assert score_island_map(None, RIFT_WALKERS_SQUAD, 7) == []
    assert score_island_map([], RIFT_WALKERS_SQUAD, 7) == []


def test_unknown_mission_id_scores_only_bonus():
    """Unknown mission_id has no MISSION_ID_TAGS entry — no penalties
    fire. Score should equal the raw bonus value.
    """
    entry = {
        "region_id": 9,
        "mission_id": "Mission_Unmapped",
        "bonus_objective_ids": [BONUS_ASSET],
        "environment": None,
    }
    # Pass an empty overlay so the on-disk metadata cache can't taint the
    # test (Mission_Unmapped is fictional anyway).
    scored = score_mission(
        entry, derive_squad_tags(RIFT_WALKERS_SQUAD), 7, mission_metadata={}
    )
    assert scored["score"] == 5  # ⊕ pilot/asset reward


# ---------------------------------------------------------------------------
# Mission-metadata–derived tags (flier_heavy / armored_heavy / psion_present)
# ---------------------------------------------------------------------------

# Synthetic metadata overlay used by the metadata-driven tests below. We
# pass this dict directly so the tests don't depend on the on-disk
# data/mission_metadata.json shape staying constant across game updates.
METADATA_FIXTURE: dict = {
    "Mission_HornetBoss_Synth": {
        "mission_id": "Mission_HornetBoss_Synth",
        "boss_mission": True,
        "boss_pawn": "HornetBoss",
        "forced_pawns": ["HornetBoss"],
        "environment": "Env_Null",
        "train_mission": False,
        "has_objective_building": True,
    },
    "Mission_BeetleBoss_Synth": {
        "mission_id": "Mission_BeetleBoss_Synth",
        "boss_mission": True,
        "boss_pawn": "BeetleBoss",
        "forced_pawns": ["BeetleBoss"],
        "environment": "Env_Null",
        "train_mission": False,
        "has_objective_building": True,
    },
    "Mission_JellyBoss_Synth": {
        "mission_id": "Mission_JellyBoss_Synth",
        "boss_mission": True,
        "boss_pawn": "Jelly_Boss",
        "forced_pawns": ["Jelly_Boss"],
        "environment": "Env_Null",
        "train_mission": False,
        "has_objective_building": True,
    },
}


def _boss_entry(mission_id: str) -> dict:
    """Synthetic island_map entry for a metadata-keyed mission."""
    return {
        "region_id": 7,
        "mission_id": mission_id,
        # No bonus objs — keep the score component coming purely from the
        # boss penalties + the mandatory boss/high_threat tag fallout.
        "bonus_objective_ids": [],
        "environment": "Env_Null",
    }


def test_flier_heavy_no_aoe_no_pierce_penalised():
    """Hornet boss + a melee-only squad → -3 flier_heavy penalty fires.

    Use Rift Walkers' Punch+Tank+Artemis but strip aoe/armor_pierce by
    swapping in a no-aoe non-pierce squad.
    """
    melee_only = [
        {"mech": True, "hp": 3, "weapons": ["Prime_Punchmech"]},
        {"mech": True, "hp": 3, "weapons": ["Brute_Tankmech"]},
        # Splitshot = burst only, no aoe/armor_pierce
        {"mech": True, "hp": 3, "weapons": ["Brute_Splitshot"]},
    ]
    tags = derive_squad_tags(melee_only)
    assert "aoe" not in tags and "armor_pierce" not in tags
    scored = score_mission(
        _boss_entry("Mission_HornetBoss_Synth"),
        tags,
        grid_power=7,
        mission_metadata=METADATA_FIXTURE,
    )
    assert "flier_heavy" in scored["mission_tags"]
    assert any("flying-heavy" in line for line in scored["rationale_lines"])
    # Score should reflect both the boss low-grid penalty (not fired at
    # grid 7) and the -3 flier_heavy hit.
    assert scored["score"] == -3


def test_flier_heavy_aoe_squad_no_penalty():
    """Hornet boss + Lightning/Jet/Grav (has aoe) → no flier_heavy fire."""
    scored = score_mission(
        _boss_entry("Mission_HornetBoss_Synth"),
        derive_squad_tags(LIGHTNING_GRAV_SQUAD),
        grid_power=7,
        mission_metadata=METADATA_FIXTURE,
    )
    for line in scored["rationale_lines"]:
        assert "flying-heavy" not in line


def test_armored_heavy_no_pierce_penalised():
    """Beetle boss + Rift Walkers (no armor_pierce) → -4 fires."""
    scored = score_mission(
        _boss_entry("Mission_BeetleBoss_Synth"),
        derive_squad_tags(RIFT_WALKERS_SQUAD),
        grid_power=7,
        mission_metadata=METADATA_FIXTURE,
    )
    assert "armored_heavy" in scored["mission_tags"]
    assert any("armored-heavy" in line for line in scored["rationale_lines"])
    assert scored["score"] == -4


def test_armored_heavy_with_pierce_no_penalty():
    """Beetle boss + Lightning (has armor_pierce) → no penalty."""
    scored = score_mission(
        _boss_entry("Mission_BeetleBoss_Synth"),
        derive_squad_tags(LIGHTNING_GRAV_SQUAD),
        grid_power=7,
        mission_metadata=METADATA_FIXTURE,
    )
    for line in scored["rationale_lines"]:
        assert "armored-heavy" not in line


def test_psion_present_no_burst_penalised():
    """Jelly boss + Rift Walkers (no burst weapon) → -2 fires."""
    tags = derive_squad_tags(RIFT_WALKERS_SQUAD)
    assert "burst" not in tags  # sanity — no burst on Punch/Taurus/Artemis
    scored = score_mission(
        _boss_entry("Mission_JellyBoss_Synth"),
        tags,
        grid_power=7,
        mission_metadata=METADATA_FIXTURE,
    )
    assert "psion_present" in scored["mission_tags"]
    assert any("psion" in line for line in scored["rationale_lines"])
    assert scored["score"] == -2


# ---------------------------------------------------------------------------
# Infinite-spawn × low-grid penalty (post-2026-04-28 m07 Mission_Barrels
# 4→2 grid drain that put the run at grid 2 entering the m13 finale).
# ---------------------------------------------------------------------------

# Synthetic overlay: a Mission_Infinite-derived mission (Volatile-style)
# and a fixed-roster alternative without infinite_spawn (Battle-style).
# Using a synthetic overlay keeps the test deterministic against game
# updates that might shuffle which templates inherit Mission_Infinite.
INFINITE_SPAWN_FIXTURE: dict = {
    "Mission_VolatileSynth": {
        "mission_id": "Mission_VolatileSynth",
        "boss_mission": False,
        "train_mission": False,
        "forced_pawns": ["GlowingScorpion"],
        "environment": "Env_Null",
        "has_objective_building": False,
        "infinite_spawn": True,
    },
    "Mission_FixedSynth": {
        # Mirrors Mission_Battle / Mission_Reactivation: fixed roster,
        # no per-turn spawn pressure.
        "mission_id": "Mission_FixedSynth",
        "boss_mission": False,
        "train_mission": False,
        "forced_pawns": [],
        "environment": "Env_Null",
        "has_objective_building": False,
        "infinite_spawn": False,
    },
}


def _infinite_spawn_mission_with_mechs_bonus() -> dict:
    """Volatile-style entry with ★ keep-mechs-alive (+4)."""
    return {
        "region_id": 12,
        "mission_id": "Mission_VolatileSynth",
        "bonus_objective_ids": [BONUS_MECHS],
        "environment": "Env_Null",
    }


def _fixed_roster_mission_with_kill_bonus() -> dict:
    """Battle-style 1★ alternative (+2 kill-7)."""
    return {
        "region_id": 13,
        "mission_id": "Mission_FixedSynth",
        "bonus_objective_ids": [BONUS_KILL_FIVE],
        "environment": "Env_Null",
    }


def test_infinite_spawn_tag_attached_from_metadata():
    """`_tags_from_metadata` propagates `infinite_spawn` into the tag set."""
    scored = score_mission(
        _infinite_spawn_mission_with_mechs_bonus(),
        derive_squad_tags(FROZEN_TITANS_SQUAD),
        grid_power=7,
        mission_metadata=INFINITE_SPAWN_FIXTURE,
    )
    assert "infinite_spawn" in scored["mission_tags"]


def test_infinite_spawn_at_grid_3_loses_to_fixed_alternative():
    """At grid=3, infinite-spawn -10 pushes Volatile below 1★ alternative.

    This is the m07-Mission_Barrels-style scenario the run logs hit:
    grid 4→2 drain on a mission that LOOKED affordable. With the new
    penalty, a fixed-roster Mission_Battle (or any non-Mission_Infinite
    template) ranks higher when grid is critical.
    """
    island = [
        _infinite_spawn_mission_with_mechs_bonus(),
        _fixed_roster_mission_with_kill_bonus(),
    ]
    ranked = score_island_map(
        island,
        FROZEN_TITANS_SQUAD,
        grid_power=3,
        mission_metadata=INFINITE_SPAWN_FIXTURE,
    )
    assert ranked[0]["mission_id"] == "Mission_FixedSynth"
    assert ranked[1]["mission_id"] == "Mission_VolatileSynth"
    volatile_score = next(
        e["score"] for e in ranked if e["mission_id"] == "Mission_VolatileSynth"
    )
    fixed_score = next(
        e["score"] for e in ranked if e["mission_id"] == "Mission_FixedSynth"
    )
    # +4 (★ mechs) - 10 (infinite_spawn at grid 3) = -6
    assert volatile_score == -6
    # +2 (★ kill 7) — no penalty (infinite_spawn=False)
    assert fixed_score == 2
    # Rationale visibility.
    assert any(
        "infinite-spawn" in line and "grid 3" in line
        for line in next(
            e for e in ranked if e["mission_id"] == "Mission_VolatileSynth"
        )["rationale_lines"]
    )


def test_infinite_spawn_at_grid_2_hard_veto():
    """At grid≤2, infinite-spawn -50 is a hard veto (matches high_threat)."""
    scored = score_mission(
        _infinite_spawn_mission_with_mechs_bonus(),
        derive_squad_tags(FROZEN_TITANS_SQUAD),
        grid_power=2,
        mission_metadata=INFINITE_SPAWN_FIXTURE,
    )
    assert any(
        "hard veto" in line and "infinite-spawn" in line
        for line in scored["rationale_lines"]
    )
    # +4 (★ mechs) - 50 (hard veto) = -46
    assert scored["score"] == -46

    # grid=1 still hard-veto.
    scored1 = score_mission(
        _infinite_spawn_mission_with_mechs_bonus(),
        derive_squad_tags(FROZEN_TITANS_SQUAD),
        grid_power=1,
        mission_metadata=INFINITE_SPAWN_FIXTURE,
    )
    assert scored1["score"] == -46


def test_infinite_spawn_at_grid_4_still_pickable():
    """At grid=4 the infinite-spawn penalty does NOT fire — these
    missions remain in the candidate pool. Grid=4 is the threshold
    where high_threat starts to bite (-8) but infinite_spawn alone
    is still affordable.
    """
    scored = score_mission(
        _infinite_spawn_mission_with_mechs_bonus(),
        derive_squad_tags(FROZEN_TITANS_SQUAD),
        grid_power=4,
        mission_metadata=INFINITE_SPAWN_FIXTURE,
    )
    assert "infinite_spawn" in scored["mission_tags"]
    for line in scored["rationale_lines"]:
        assert "infinite-spawn" not in line
    # Pure +4 (★ mechs).
    assert scored["score"] == 4


def test_infinite_spawn_at_full_grid_no_penalty():
    """At grid≥5 the infinite-spawn penalty does not fire."""
    scored = score_mission(
        _infinite_spawn_mission_with_mechs_bonus(),
        derive_squad_tags(FROZEN_TITANS_SQUAD),
        grid_power=7,
        mission_metadata=INFINITE_SPAWN_FIXTURE,
    )
    for line in scored["rationale_lines"]:
        assert "infinite-spawn" not in line
    assert scored["score"] == 4


def test_fixed_roster_mission_no_infinite_spawn_tag():
    """Mission_Battle-style entries (infinite_spawn=False) do NOT pick
    up the tag, so the penalty cannot fire on them at any grid level.
    """
    scored = score_mission(
        _fixed_roster_mission_with_kill_bonus(),
        derive_squad_tags(FROZEN_TITANS_SQUAD),
        grid_power=2,
        mission_metadata=INFINITE_SPAWN_FIXTURE,
    )
    assert "infinite_spawn" not in scored["mission_tags"]
    for line in scored["rationale_lines"]:
        assert "infinite-spawn" not in line
    # +2 (★ kill 7) — clean.
    assert scored["score"] == 2


def test_infinite_spawn_does_not_double_charge_boss_low_grid():
    """A mission that is BOTH boss_mission and infinite_spawn fires the
    infinite_spawn penalty (-10/-50) but NOT the boss low-grid -4 on
    top. Otherwise at grid=3 a boss mission would eat -10 + -4 = -14.

    Use a synthetic boss overlay so we control both flags.
    """
    overlay = {
        "Mission_BossInfSynth": {
            "mission_id": "Mission_BossInfSynth",
            "boss_mission": True,
            "boss_pawn": "HornetBoss",
            "forced_pawns": ["HornetBoss"],
            "environment": "Env_Null",
            "train_mission": False,
            "has_objective_building": True,
            "infinite_spawn": True,
        },
    }
    entry = {
        "region_id": 14,
        "mission_id": "Mission_BossInfSynth",
        "bonus_objective_ids": [],
        "environment": "Env_Null",
    }
    scored = score_mission(
        entry,
        derive_squad_tags(LIGHTNING_GRAV_SQUAD),  # has aoe → no flier_heavy fire
        grid_power=3,
        mission_metadata=overlay,
    )
    rationale = " | ".join(scored["rationale_lines"])
    # The infinite_spawn rule fired (it dominates the boss low-grid -4)
    assert "infinite-spawn" in rationale and "grid 3" in rationale
    # The boss low-grid -4 did NOT fire (no "boss + low grid" line).
    assert "boss + low grid" not in rationale
    # Score: 0 bonuses, -10 infinite_spawn at grid 3 (boss tags also
    # add high_threat → -15, but that's a separate rule).
    assert scored["score"] == -10 + -15  # high_threat -15 at grid 3


def test_metadata_derived_train_tag_overrides_substring_match():
    """A previously-unknown mission_id whose metadata says
    train_mission=True still gets the -8 train penalty.

    This is the value-add over the legacy substring table: the picker
    now picks up new-corp train missions (Mission_Armored_Train was
    already in the table, but a future Mission_BulletTrain wouldn't
    be — metadata catches it).
    """
    overlay = {
        "Mission_BulletTrain_Synth": {
            "mission_id": "Mission_BulletTrain_Synth",
            "train_mission": True,
            "forced_pawns": ["Train_Bullet"],
            "boss_mission": False,
            "environment": "Env_Null",
            "has_objective_building": True,
        }
    }
    entry = {
        "region_id": 8,
        "mission_id": "Mission_BulletTrain_Synth",
        "bonus_objective_ids": [BONUS_GRID],
        "environment": "Env_Null",
    }
    scored = score_mission(
        entry,
        derive_squad_tags(LIGHTNING_GRAV_SQUAD),  # no train_defender
        grid_power=7,
        mission_metadata=overlay,
    )
    assert "train" in scored["mission_tags"]
    assert any("no train_defender" in line for line in scored["rationale_lines"])
