"""Squad-aware mission picker.

Layer-4 (Strategist) component. Given a squad's current weapons and an
``island_map`` payload from the bridge, scores each available mission
and returns a ranked recommendation list with rationale lines.

Pipeline:
    bridge state.island_map  --(score_island_map)-->  ranked list
    bridge state.units(mechs) --(derive_squad_tags)-->  set of tags

Scoring is intentionally simple and additive so rationales are easy to
read: ``total = sum(bonus_value, ...) + sum(penalty, ...)``. Bonus
values reward objectives we're likely to hit; penalties express
mission/squad-mismatch and grid-state hazards. Tweak the constants in
``score_mission`` rather than refactoring the structure.

Concrete failure this addresses (run 20260425_185532_218 m04→m05):
    A Lightning/Jet/Grav-Well squad on Detritus took Historic County
    (a train mission with High Threat ⚡) without a train_defender
    mech, lost a pilot, then wiped on Secondary Archives ("do not
    kill Volatile Vek") with no crowd-control. The picker here would
    have ranked Historic County far below alternatives because of
    `train` + `no train_defender` (-8) and `high_threat` + grid<5
    (-5), and Secondary Archives below alternatives because of
    `volatile_vek` + `no crowd_control` (-3).
"""
from __future__ import annotations

from typing import Any

# ----------------------------------------------------------------------
# BONUS objective enum (mirrors scripts/missions/missions.lua:32-40).
# Lua-side BonusObjs is a list of these int values.
# ----------------------------------------------------------------------
BONUS_ASSET = 1        # Save AssetId building (varies; pilot pod / corp asset)
BONUS_KILL = 2         # Kill all (deprecated; rarely surfaces)
BONUS_GRID = 3         # ⚡ Don't lose more than N grid power (defensive)
BONUS_MECHS = 4        # ★ Don't let any mech die
BONUS_BLOCK = 5        # Block emergence
BONUS_KILL_FIVE = 6    # Kill at least 7 enemies (Hard difficulty)
BONUS_DEBRIS = 7       # Destroy mountains/buildings to clear debris
BONUS_SELFDAMAGE = 8   # Take no self-damage
BONUS_PACIFIST = 9     # Don't kill any Vek (let buildings/terrain do it)

# Bonus → display symbol used in CLI rationale lines.
BONUS_SYMBOL = {
    BONUS_ASSET: "⊕",
    BONUS_KILL: "★",
    BONUS_GRID: "⚡",
    BONUS_MECHS: "★",
    BONUS_BLOCK: "★",
    BONUS_KILL_FIVE: "★",
    BONUS_DEBRIS: "★",
    BONUS_SELFDAMAGE: "★",
    BONUS_PACIFIST: "★",
}

# ----------------------------------------------------------------------
# Squad weapon → capability tags. Bridge unit.weapons is a list of Lua
# weapon ids (e.g. "Prime_Lightning", "Science_Gravwell"). Each id maps
# to zero or more tags. Add new ids here as they appear in squads.
#
# Tag semantics:
#   burst         — multi-hit; useful for "kill 7" bonuses
#   aoe           — multi-tile damage (artillery splash, beam, etc.)
#   armor_pierce  — bypasses Armor (Burst Beam, Lightning chain)
#   flying        — passive that lets the mech fly (water/chasm immunity)
#   train_defender — can reliably stop or escort the train
#                    (push-source within 1-2 tiles of any column —
#                    melee/dash with reliable single-target push, OR
#                    pull-source like Grappling Hook)
#   crowd_control — can disable a Vek without killing it (freeze, web,
#                   smoke, push-into-mountain, swap, repulse). Critical
#                   for "do not kill X" missions where you must defend
#                   the protected enemy.
#   repair        — heals adjacent / self (Mass Repair, etc.)
#   push_chain    — multi-target push (Repulse, Vulcan adjacent,
#                   Cluster, Gravity Well)
# ----------------------------------------------------------------------
WEAPON_TAGS: dict[str, list[str]] = {
    # PRIME — single-target melee w/ push (good train defenders)
    "Prime_Punchmech":   ["train_defender"],          # Titan Fist
    "Prime_Lightning":   ["aoe", "armor_pierce", "burst"],  # multi-target chain
    "Prime_Lasermech":   ["aoe", "armor_pierce"],     # piercing line
    "Prime_ShieldBash":  ["train_defender"],
    "Prime_Shift":       ["crowd_control"],           # forced-move
    "Prime_Flamethrower": ["push_chain", "burst"],    # fire spreads
    "Prime_Areablast":   ["aoe", "push_chain"],
    "Prime_Leap":        ["aoe"],
    "Prime_Spear":       ["aoe", "armor_pierce"],
    "Prime_RocketPunch": ["train_defender"],
    "Prime_RightHook":   ["train_defender"],
    "Prime_SpinFist":    ["push_chain"],
    "Prime_Sword":       ["aoe", "burst"],
    "Prime_Smash":       ["train_defender", "aoe"],
    # BRUTE — ranged / dash
    "Brute_Tankmech":    ["train_defender"],          # Taurus Cannon (push)
    "Brute_Jetmech":     ["aoe", "burst", "flying"],  # Aerial Bombs
    "Brute_Mirrorshot":  ["aoe"],
    "Brute_Beetle":      ["train_defender"],
    "Brute_Grapple":     ["train_defender", "crowd_control"],  # pull
    "Brute_Heavyrocket": ["aoe", "burst"],
    "Brute_Sonic":       ["push_chain"],
    "Brute_Shockblast":  ["aoe", "push_chain"],
    "Brute_Sniper":      ["armor_pierce"],
    "Brute_Splitshot":   ["burst"],
    "Brute_Bombrun":     ["aoe", "burst"],
    "Brute_PhaseShot":   ["armor_pierce"],
    "Brute_Shrapnel":    ["aoe"],
    # RANGED — artillery
    "Ranged_Artillerymech": ["aoe", "push_chain"],    # Artemis Artillery
    "Ranged_Rocket":     ["aoe", "burst"],            # Rocket Artillery
    "Ranged_Rockthrow":  ["aoe", "push_chain"],
    "Ranged_Defensestrike": ["aoe"],
    "Ranged_Ignite":     ["aoe", "burst"],
    "Ranged_Ice":        ["crowd_control"],           # freeze
    "Ranged_ScatterShot": ["aoe", "burst"],
    "Ranged_BackShot":   ["aoe"],
    "Ranged_Wide":       ["aoe", "burst"],
    # SCIENCE — utility
    "Science_Pullmech":  ["crowd_control", "train_defender"],
    "Science_Gravwell":  ["crowd_control"],           # pull artillery
    "Science_Repulse":   ["push_chain", "crowd_control"],
    "Science_Swap":      ["crowd_control"],           # teleport swap
    "Science_AcidShot":  ["crowd_control"],           # ACID
    "Science_Shield":    ["repair"],                  # shield as defense
    "Science_Confuse":   ["crowd_control"],
    # SUPPORT
    "Support_Repair":    ["repair"],
    # PASSIVES
    "Passive_MassRepair": ["repair"],
    "Passive_HealingSmoke": ["repair", "crowd_control"],  # smoke disables Vek
    "Passive_Boosters":  ["flying"],
    "Passive_FlameImmune": [],
    "Passive_FriendlyFire": [],   # *enemy* tag — irrelevant to squad
    "Passive_Defenses":  [],
    "Passive_Electric":  ["aoe"],
}


def derive_squad_tags(units: list[dict[str, Any]]) -> set[str]:
    """Derive capability tags from the live squad's weapons.

    ``units`` is the bridge units list (or any list with `mech: True`
    + `weapons: [str, ...]`). Returns the union of WEAPON_TAGS for
    every weapon id on every living mech.
    """
    tags: set[str] = set()
    for u in units:
        if not u.get("mech"):
            continue
        if u.get("hp", 1) <= 0:
            continue
        for wid in u.get("weapons", []) or []:
            for t in WEAPON_TAGS.get(wid, []):
                tags.add(t)
    return tags


# ----------------------------------------------------------------------
# Mission ID → mission tags. Same idea: substring-match because the
# Lua mission.ID is a stable template name like "Mission_Train",
# "Mission_Volatile", "Mission_Lightning_Mech". New mission IDs land
# here as they're encountered.
# ----------------------------------------------------------------------
MISSION_ID_TAGS: dict[str, list[str]] = {
    # Train missions — must defend a Train_Pawn that walks 2 tiles/turn
    "Mission_Train":          ["train"],
    "Mission_Armored_Train":  ["train"],
    # Volatile Vek — bonus penalises killing a specific glowing Vek
    "Mission_Volatile":       ["volatile_vek"],
    "Mission_VolatileMine":   ["volatile_vek"],
    # Cataclysm / Seismic / Tidal — terrain-conversion env
    "Mission_Lightning_Mech": ["high_threat"],
    "Mission_LightningStorm": ["env_lightning"],
    "Mission_Tidal":          ["env_tidal"],
    "Mission_Cataclysm":      ["env_cataclysm"],
    # Survive / battle
    "Mission_Survive":        ["protect_buildings"],
    "Mission_Battle":         ["high_threat"],
    # Final / boss
    "Mission_Final":          ["high_threat", "boss"],
    # Critical buildings (Solar / Wind / Power) — protect 2 specific buildings
    "Mission_Solar":          ["protect_specific_building"],
    "Mission_Wind":           ["protect_specific_building"],
    "Mission_Power":          ["protect_specific_building"],
}

# Environment string → mission tags. Lua emits the class name like
# "Env_TidalWaves". Substring match (Env_Lava → tag "env_lava").
ENVIRONMENT_TAGS: dict[str, list[str]] = {
    "Env_Lava":         ["env_lava"],
    "Env_Tidal":        ["env_tidal"],
    "Env_TidalWaves":   ["env_tidal"],
    "Env_Conveyor":     ["conveyor"],
    "Env_ConveyorBelt": ["conveyor"],
    "Env_Sandstorm":    ["defensive_smoke"],
    "Env_AirStrike":    ["env_lightning"],
    "Env_Lightning":    ["env_lightning"],
    "Env_LightningStorm": ["env_lightning"],
    "Env_Cataclysm":    ["env_cataclysm"],
    "Env_Seismic":      ["env_cataclysm"],
    "Env_SnowStorm":    ["defensive_freeze"],
    "Env_IceStorm":     ["defensive_freeze"],
    "Env_Wind":         ["env_wind"],
    "Env_Null":         [],
}


def derive_mission_tags(
    mission_id: str,
    bonus_objective_ids: list[int],
    environment: str | None,
) -> set[str]:
    """Derive a flat set of mission tags from id + bonus + environment."""
    tags: set[str] = set()
    if mission_id:
        tags.update(MISSION_ID_TAGS.get(mission_id, []))
    if environment:
        tags.update(ENVIRONMENT_TAGS.get(environment, []))
    for b in bonus_objective_ids or []:
        if b == BONUS_GRID:
            tags.add("bonus_grid")
        elif b == BONUS_MECHS:
            tags.add("bonus_mechs")
        elif b == BONUS_KILL_FIVE:
            tags.add("bonus_kill_five")
        elif b == BONUS_DEBRIS:
            tags.add("bonus_debris")
        elif b == BONUS_SELFDAMAGE:
            tags.add("bonus_selfdamage")
        elif b == BONUS_PACIFIST:
            tags.add("bonus_pacifist")
        elif b == BONUS_BLOCK:
            tags.add("bonus_block")
        elif b == BONUS_ASSET:
            tags.add("bonus_asset")
    return tags


def _bonus_value(bonus_id: int, grid_power: int) -> tuple[int, str]:
    """Reward score + label for a single bonus objective."""
    sym = BONUS_SYMBOL.get(bonus_id, "·")
    if bonus_id == BONUS_GRID:
        if grid_power < 5:
            return 4, f"⚡ grid bonus + low grid ({grid_power}) → defensive"
        return 2, f"⚡ grid bonus (grid {grid_power})"
    if bonus_id == BONUS_MECHS:
        return 4, f"{sym} keep mechs alive"
    if bonus_id == BONUS_KILL_FIVE:
        return 2, f"{sym} kill 7 enemies"
    if bonus_id == BONUS_DEBRIS:
        return 2, f"{sym} destroy 5 debris"
    if bonus_id == BONUS_SELFDAMAGE:
        return 2, f"{sym} no self-damage"
    if bonus_id == BONUS_PACIFIST:
        return 2, f"{sym} pacifist"
    if bonus_id == BONUS_BLOCK:
        return 2, f"{sym} block emergence"
    if bonus_id == BONUS_ASSET:
        return 5, f"{sym} pilot/asset reward"
    return 1, f"bonus#{bonus_id}"


def score_mission(
    entry: dict[str, Any],
    squad_tags: set[str],
    grid_power: int,
) -> dict[str, Any]:
    """Score one ``island_map`` entry against the squad.

    Returns the input entry augmented with ``score`` and
    ``rationale_lines`` (a list of strings — first line per bonus
    award, then per fired penalty).
    """
    mission_id = entry.get("mission_id", "")
    bonus_ids = entry.get("bonus_objective_ids", []) or []
    env = entry.get("environment")
    diff_mod = entry.get("diff_mod", 0) or 0

    mission_tags = derive_mission_tags(mission_id, bonus_ids, env)
    rationale: list[str] = []
    score = 0

    # Star bonuses + ⚡ rewards.
    for b in bonus_ids:
        v, label = _bonus_value(b, grid_power)
        score += v
        rationale.append(f"+{v}  {label}")
    # Two-star double bonus (rare; some missions stack).
    if len(bonus_ids) >= 2:
        score += 2
        rationale.append("+2  ★★ double-bonus mission")

    # Penalties: squad/mission mismatch.
    if "train" in mission_tags and "train_defender" not in squad_tags:
        score -= 8
        rationale.append("-8  train mission, no train_defender in squad")
    if "high_threat" in mission_tags and grid_power < 5:
        score -= 5
        rationale.append(f"-5  high-threat + low grid ({grid_power})")
    if "volatile_vek" in mission_tags and "crowd_control" not in squad_tags:
        score -= 3
        rationale.append("-3  volatile-Vek mission, no crowd-control in squad")
    if "env_tidal" in mission_tags and "flying" not in squad_tags:
        score -= 2
        rationale.append("-2  Tidal Waves env, no flying mech")
    if "env_cataclysm" in mission_tags and "flying" not in squad_tags:
        score -= 2
        rationale.append("-2  Cataclysm/Seismic env, no flying mech")
    if "env_lightning" in mission_tags and grid_power < 4:
        score -= 3
        rationale.append(f"-3  Lightning/AirStrike env + grid {grid_power}")
    if "conveyor" in mission_tags and grid_power < 4:
        score -= 2
        rationale.append(f"-2  conveyor mission + low grid ({grid_power})")
    if "boss" in mission_tags and grid_power < 4:
        score -= 4
        rationale.append(f"-4  boss + low grid ({grid_power})")
    if "protect_specific_building" in mission_tags and "crowd_control" not in squad_tags:
        score -= 2
        rationale.append("-2  protect-specific + no crowd-control")

    # Difficulty modifier (set in createIncidents:302).
    if diff_mod == 1:  # DIFF_MOD_HARD
        score -= 1
        rationale.append("-1  marked HARD by engine")
    elif diff_mod == -1:  # DIFF_MOD_EASY
        score += 1
        rationale.append("+1  marked EASY by engine")

    out = dict(entry)
    out["score"] = score
    out["mission_tags"] = sorted(mission_tags)
    out["rationale_lines"] = rationale
    return out


def score_island_map(
    island_map: list[dict[str, Any]] | None,
    squad_units: list[dict[str, Any]],
    grid_power: int,
) -> list[dict[str, Any]]:
    """Score every entry of an island_map; return descending by score.

    ``island_map`` may be None or empty (combat / between-states); this
    returns []. ``squad_units`` is the bridge units list. ``grid_power``
    is the current ⚡ count (used for the low-grid weighting).
    """
    if not island_map:
        return []
    squad_tags = derive_squad_tags(squad_units)
    scored = [score_mission(e, squad_tags, grid_power) for e in island_map]
    scored.sort(key=lambda e: e["score"], reverse=True)
    return scored
