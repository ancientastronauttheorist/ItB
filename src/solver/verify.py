"""Per-action diff engine for the post-action verification loop.

Compares a predicted board snapshot (captured inside ``replay_solution``
after each ``simulate_action`` call) against the actual game state read
back from the bridge. Used by ``cmd_verify_action`` to detect desyncs
between solver predictions and reality without ever re-solving mid-turn.

Design notes:
  - Snapshots are JSON-friendly dicts so they live in solve recordings.
  - The diff only inspects units present in either snapshot, plus tiles
    that the action's events touched. We never scan all 64 tiles.
  - Dead-mech equivalence: a unit dead in both snapshots collapses to a
    single "dead" state — we don't false-positive on its ``active`` flag.
  - The Python sim has known model gaps (ACID transfer, Tyrant Psion,
    Vek spawns). Diffs originating from those are tagged
    ``model_gap_known`` so the tuner can filter them out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# Solve-record schema version. Bump when the shape of the ``data`` block
# written by cmd_solve changes in a way readers must adapt to.
#
#   version 1 (current): flat top-1 plan. ``data.predicted_states`` holds
#     a list of per-action snapshots for the single chosen plan.
#   version 2 (reserved, beam lands in Task #10): ``data.beam`` carries
#     top-K plans and per-depth projections; ``data.predicted_states``
#     stays populated with the chosen plan's states for backward reads.
#
# Readers must route through ``predicted_states_from_solve_record`` so
# the adapter can evolve centrally.
SOLVE_RECORD_SCHEMA_VERSION = 1
_KNOWN_SOLVE_SCHEMA_VERSIONS = {1}


# Simulator semantic version. Bump every time the Rust or Python simulator
# changes behavior in a way that would make pre-bump predictions invalid
# for post-bump corpus analysis. Examples that require a bump:
#   - Storm Generator passive implemented (was silent)
#   - Psion regen actually applied (was a no-op)
#   - Spartan Shield damage + flip semantics fixed
#   - Any PushDir::Flip change
#   - Any change to simulate_enemy_attacks, apply_damage, apply_push paths
# Weight-tuning changes do NOT require a bump; this is semantic, not scoring.
#
# The tuner and analysis tools pin their corpus to a simulator_version so
# pre-bump failure_db rows don't contaminate post-bump optimization.
# v3 (2026-04-23): pilot passives wired into the simulator
#   - Pilot_Soldier (Camila Vera): web immunity at the apply_weapon_status /
#     enemy web hooks
#   - Pilot_Rock (Ariadne): fire immunity at every fire-apply site (weapon,
#     tile catch on push/move/throw, enemy weapon fire) + fire-tick skip
#   - Pilot_Repairman (Harold Schmidt): Repair pushes all 4 adjacent tiles
# Any board with one of these pilots can now produce a different predicted
# state than v2. Pre-v3 rows archived to failure_db_snapshot_sim_v2.jsonl.
#
# v4 (2026-04-23, Rift Walkers simulator pass):
#   - Ranged_Rocket places smoke on the tile directly behind the shooter
#     (new SMOKE_BEHIND_SHOOTER weapon flag).
#   - Jet_BombDrop (Aerial Bombs) places smoke on transit tile(s), not
#     the landing tile.
#   - Sim now enforces Jet_BombDrop landing-tile legality (mountain or
#     occupied landing = target rejected at enumeration time). Behavior
#     was correct in production via Board::is_blocked; debug_assert added
#     to guard against regressions.
#   - effectively_flying() = flying && !frozen is now used in
#     apply_damage_core, apply_throw, and apply_push deadly-terrain checks:
#     frozen flying Vek pushed/thrown into water drown (they were
#     previously predicted to survive).
#   - Massive trait's drown-immunity is now correctly scoped to Water/Lava
#     only — Massive units die in chasms (Seismic/Cataclysm/push) and from
#     lethal Tidal Wave. Previously apply_push/apply_throw killed Massive
#     units on ALL deadly ground (over-killing in Water/Lava).
# Pre-v4 rows archived to failure_db_snapshot_sim_v3.jsonl.
#
# v5 (2026-04-23, Rift Walkers follow-up fixes):
#   - Jet_BombDrop (Aerial Bombs) now damages the transit tile(s) only, not
#     the 4 cardinal neighbors of the landing tile. Gated on wdef.smoke() so
#     other leap weapons (Prime_Leap, Brute_Bombrun) are unchanged.
#   - apply_push / apply_throw building-bump branches now use saturating_sub
#     on building_hp to prevent u8 underflow when a Volatile Vek / Blast
#     Psion death chain drops the bumped building to 0 before the post-
#     apply_damage decrement. Previously panicked in debug and wrapped to
#     255 in release. Latent on observed boards but corrects the underlying
#     arithmetic. Python-side _sim_leap gained smoke parity with Rust
#     (non-scoring, but keeps replay_solution output consistent).
# Pre-v5 rows archived to failure_db_snapshot_sim_v4.jsonl.
#
# v6 (2026-04-23):
#   - Brute_Bombrun (Bombing Run) damage now lands on every transit tile
#     along the cardinal flight path, not on the 4 cardinal neighbors of
#     the landing tile. New DAMAGES_TRANSIT weapon flag gates this (mirrors
#     how SMOKE gates Jet_BombDrop's transit-damage). Alters predictions on
#     any board where Bombing Run is fired; current failure corpus has no
#     Bombing Run entries (grep -c Bombrun = 0) so regression is clean, but
#     the semantic change still warrants a bump per CLAUDE.md rule 22.
# Pre-v6 rows archived to failure_db_snapshot_sim_v5.jsonl.
#
# v7 (2026-04-23, grid-drop deep dive):
#   - Brute_Mirrorshot: sim_projectile now calls apply_damage when an arm
#     stops on a Mountain tile (previously silently skipped, under-counting
#     terrain loss on both arms of Mirror Shot).
#   - Ranged_Defensestrike & all push-driven weapons: dead-pusher no longer
#     deals spurious bump damage to live blocker in apply_push. Corpse
#     still bumps static obstacles (building/mountain/edge) — only the
#     live-unit blocker branch is gated on pusher.hp > 0.
#   - Non-unique multi-HP buildings preserve grid_power on bump: previously
#     apply_push/apply_throw decremented board.grid_power by 1 on every
#     bump regardless of whether the building survived; now only drops on
#     full destruction. Unique objective buildings keep per-HP accounting.
#   - Python _sim_leap now emits transit-tile damage for Aerial Bombs +
#     Bombing Run (closes the parity gap from PR #11/#12; Python is
#     non-scoring so this alone would not require a bump, but ships with
#     the Rust changes above).
#   - Python apply_damage now ignites forest on weapon damage (parity with
#     Rust — previously Python replay missed the forest-fire transition).
# Pre-v7 rows archived to failure_db_snapshot_sim_v6.jsonl.
#
# v8 (2026-04-23, Mission_Teleporter):
#   - Bridge extracts teleporter-pad pairs via a Board.AddTeleport hook
#     (modloader.lua) and emits `teleporter_pairs`.
#   - Rust Board carries `teleporter_pairs: Vec<(u8,u8,u8,u8)>` and
#     `apply_teleport_on_land` fires at every move-end site (apply_push,
#     apply_throw, sim_charge, sim_leap, Swap weapon, mech move) AFTER
#     terrain-kill / mines resolve — corpses don't teleport, web survives
#     (pad swap is not a push).
#   - Python Board mirrors the field for test-fixture parity; the live
#     Rust solver is authoritative for combat decisions.
#   - Closes the silent position desync observed on run 20260423_131700_144
#     Disposal Site C: ScienceMech moved to E3 (a pad), predicted post-enemy
#     at E3, actually swapped to C3 — a canonical 2-tile pad swap the sim
#     was blind to. Similar drift on Judo/Science across T2/T3.
# Pre-v8 rows archived to failure_db_snapshot_sim_v7.jsonl.
#
# v13 (2026-04-24, Python-sim removal):
#   - replay_solution now calls itb_solver.replay_solution (Rust) instead
#     of Python's simulate_move/simulate_attack. predicted_states in
#     solve.json reflect the same Rust simulator that drives solve()
#     decisions, closing the prediction-vs-decision sim mismatch (see
#     run 20260423_131700_144 m00_t02 acid-tile-pickup miss).
#   - simulate_action split into pub fn simulate_move + pub fn
#     simulate_attack on the Rust side; behavior unchanged but the
#     split lets replay capture per-phase snapshots.
#   - score_breakdown still computed by Python evaluate_breakdown on the
#     post-enemy board round-tripped via board_to_json.
# Pre-v13 rows archived to failure_db_snapshot_sim_v12.jsonl.
# v14: Cluster Artillery (Ranged_Defensestrike) center-tile damage
# corrected 0 → 1 in rust_solver/src/weapons.rs:365. Surfaced by
# grid_drop investigation on run 20260424_011517_057 t03.
# Pre-v14 rows archived to failure_db_snapshot_sim_v13.jsonl.
# v15: Cracked-ground → Chasm on damage (simulate.rs) + volatile_enemy_killed
# penalty to preserve Volatile Vek / GlowingScorpion. Weather Watch mission.
# Pre-v15 rows archived to failure_db_snapshot_sim_v14.jsonl.
# v16: Unit::is_volatile_vek() helper matches both "Volatile_Vek" and
# "GlowingScorpion"; all 4 decay-firing simulate.rs sites + the
# evaluate.rs penalty now use it. Pre-v16 rows archived to
# failure_db_snapshot_sim_v15.jsonl.
# v17: Non-unique 2-HP building damage is now incremental in
# rust_solver/src/simulate.rs::apply_damage_core — previously non-
# unique buildings were all-or-nothing (any damage destroyed the
# whole HP pool), which over-predicted HP loss against 2-HP non-
# objective buildings. Aerial Bombs transit-damage against a 2-HP
# building predicted destruction (hp 2→0) vs actual hp 2→1.
# Surfaced by grid_drop investigation on run 20260424_144237_364
# (snapshots/grid_drop_20260424_144237_364_t01_a1). Pre-v17 rows
# archived to failure_db_snapshot_sim_v16.jsonl.
# v18: sim_charge now applies the FIRE-trail. Charge weapons with the
# FIRE flag (BeetleAtkB Flaming Abdomen) ignite every tile passed
# through, EXCLUDING the final resting tile, matching the in-game rule.
# Previously sim_charge dropped the FIRE flag on intermediate tiles —
# only the impact tile got fire via apply_weapon_status. Surfaced by
# diagnosing the 2026-04-24 Rift Walkers Corporate HQ finale defeat
# (recordings/20260424_210640_742). Pre-v18 rows archived to
# failure_db_snapshot_sim_v17.jsonl.
# v19 (2026-04-25): apply_env_danger now spares effectively-flying
# units on terrain-conversion lethal hazards (Tidal Wave, Cataclysm,
# Seismic). Air Strike / Lightning / Satellite Rocket continue to kill
# flyers. New per-tile bit `env_danger_flying_immune` carries the
# distinction; bridge emits a 5th element on each
# `environment_danger_v2` entry, with an `env_type`-based fallback for
# older recordings. Closes the silent "Hornet on Tidal" desync
# (m04 Artifact Vaults, run 20260425_005049_742) where the solver
# projected a flying enemy dead and wasted a turn, letting the live
# Hornet destroy the Power Generator. Pre-v19 rows archived to
# failure_db_snapshot_sim_v18.jsonl.
# v20 (2026-04-25, full-pull pull weapons): Brute_Grapple "Grappling Hook"
# and Science_Gravwell "Grav Well" now drag the target ALL the way to the
# tile adjacent to the mech, matching the wiki ("pull units to the Mech" /
# "pulls its target towards you... not able to pull enemies into the
# Gravity Mech for bump damage"). Previously both shared the 1-tile path
# with Science_Pullmech (Attraction Pulse), under-predicting destination
# by ≥1 tile every cast. New WeaponFlags::FULL_PULL bit; sim_pull_or_swap
# loops apply_push until adjacency, death, or blocker. Science_Pullmech
# remains 1-tile (correctly per wiki). Also fixes BruteGrapple display
# name (was "Vice Fist", which is actually Prime_Shift). Pre-v20 rows
# archived to failure_db_snapshot_sim_v19.jsonl.
# v21 (2026-04-25, mission-aware "do not kill X" bonus penalty):
#   The Rust `volatile_enemy_killed` evaluator term is now gated by
#   `Board::bonus_dont_kill_types`, populated from the new
#   `JsonInput::bonus_objective_unit_types` field. Python resolves the
#   mission_id → protected types via
#   `src/solver/mission_bonus_objectives.py` reading
#   `data/mission_bonus_objectives.json`. Lua-bridge precedence path
#   is wired (bridge populates the field directly when modloader
#   gains BONUS_PROTECT_X exposure — TODO in modloader.lua). Empty
#   list on missions without a "do not kill" bonus = penalty no-ops,
#   matching pre-fix behavior on those boards but removing the
#   false-positive on missions where a Volatile spawned without
#   BONUS_PROTECT_X. Pre-v21 rows archived to
#   failure_db_snapshot_sim_v20.jsonl.
# v22 (2026-04-25, WebbEgg → Spiderling hatch simulation):
#   `simulate_enemy_attacks` now runs a hatch step at the start of the
#   enemy phase (after fire tick + env_danger so dead eggs don't
#   resurrect): WebbEgg1/SpiderlingEgg1 → Spiderling1,
#   WebbEgg2 → Spiderling2. Pre-fix, the predicted post-enemy state
#   showed an egg while the live game showed a Spiderling — every
#   spider-bonus mission produced a verify_action desync, and turn
#   3-4 board states diverged after eggs piled up across turns.
#   Hatchlings have no queued attack on their hatch turn (real game:
#   bite is turn after hatch); the attack loop's phantom-attack guard
#   handles the cleared queued_target. Surfaced by the
#   20260425_185532_218 Archive Inc loss. Pre-v22 rows archived to
#   failure_db_snapshot_sim_v21.jsonl.
# v23 (2026-04-25, hatch-table corrected against game Lua source):
#   v22 hatch table came from data/ref_vek_bestiary.md; validating
#   against the actual scripts revealed:
#     pawns.lua has NO WebbEgg2. Spider1 and Spider2 (Alpha) both
#     lay a WebbEgg1 — weapons_enemy.lua:760 sets MyPawn="WebbEgg1"
#     on SpiderAtk1, and SpiderAtk2 = SpiderAtk1:new{...} does not
#     override it (the Alpha description even says "hatches into a
#     Spiderling", singular). WebeggHatch1.SpiderType="Spiderling1".
#   So every vanilla spider egg hatches into a regular Spiderling1
#   (1 HP, 1 dmg melee), NOT a Spiderling2 Alpha. The dead
#   `WebbEgg2 → Spiderling2` branch was unreachable on real boards
#   (bridge never surfaces a non-existent type) but is removed for
#   correctness. SpiderlingEgg1 → Spiderling1 retained as a
#   defensive alias. No behavior change predicted for live runs;
#   version bumped because the hatch-mapping table changed. Pre-v23
#   rows archived to failure_db_snapshot_sim_v22.jsonl.
# v24 (2026-04-25, three player-weapon fixes after Lua audit):
#   - Prime_Spear: Range/PathSize 1 -> 2 per weapons_prime.lua:792-846.
#     Range-2 stabs enumerated; in-path damage before final-tile push.
#   - Brute_Sniper: damage = max(0, min(MaxDamage, dist-1)) per
#     weapons_brute.lua:969-991. Adjacent shots now 0 damage.
#   - Brute_Grapple: self-charge into mountain/building per
#     weapons_brute.lua:339-389. Mech stops at target-dir; no obstacle
#     damage. Previously the no-pawn branch silently exited.
#   Pre-v24 rows archived to failure_db_snapshot_sim_v23.jsonl.
# v25 (2026-04-27, Ice Storm freeze application):
#   Bridge: class-metatable check now runs BEFORE field-signature heuristic
#   in modloader.lua, so Env_SnowStorm no longer collides with
#   Lightning/Air Strike on the shared `LiveEnvironment.Locations` field.
#   Vanilla Ice Storm tiles (Acid=false) route into a new
#   `environment_freeze` JSON channel; NanoStorm (Acid=true) takes the
#   existing non-lethal env_danger path. New `Board.environment_freeze`
#   set in Python and `Board::env_freeze: u64` bitset in Rust.
#
#   Simulator: at start of enemy turn (after env_danger), units on freeze
#   tiles get Frozen=true. Shield blocks + consumed; already-frozen
#   idempotent; buildings/mountains untouched. Frozen Vek skip their
#   attacks (existing `if e.frozen()` guard), so damage prevention is
#   captured automatically in the post-enemy state.
#
#   Evaluator: small forward-looking `enemy_on_danger`-magnitude reward
#   for non-flying enemies on freeze tiles. Mech-on-freeze rides the
#   existing `mech_self_frozen` cost (one lost turn, far less than
#   `mech_killed`).
#
#   Pre-v25 rows archived to failure_db_snapshot_sim_v24.jsonl.
#
# v26 (2026-04-27, Science_Gravwell single-tile pull):
#   v20 erroneously added FULL_PULL to Science_Gravwell based on wiki
#   phrasing. Game Lua (weapons_science.lua:115-124) only does a single
#   SpaceDamage with directional push — no AddCharge — so Gravwell pulls
#   ONE tile, not all the way. Brute_Grapple (which DOES use AddCharge)
#   keeps FULL_PULL. See rust_solver/src/lib.rs v26 block for full detail.
#   Pre-v26 rows archived to failure_db_snapshot_sim_v25.jsonl.
#
# v27 (2026-04-28, queued_target OOB guard):
#   M04 (Old Town) crashed mid-turn with `index out of bounds: the len is 64
#   but the index is 69` from rust_solver/src/enemy.rs apply_damage path.
#   Index 69 = 8*8 + 5 unambiguously identifies tile (x=8, y=5). Root cause:
#   a Vek at cx=7 with normalized direction ddx=+1 produced queued_target.x=8
#   in `_normalize_queued_targets`, off-board on an 8×8 grid. The bogus
#   state also tripped Python `board.tile()` IndexErrors in
#   `get_threatened_buildings` and `cmd_read`'s telegraphed-attack scan,
#   crashing `cmd_read` after restart. Fix: bridge reader nulls the
#   queued_target when normalization yields an off-board coord; Rust Melee
#   + catch-all attack arms gain `if qtx<0||qty<0||qtx>=8||qty>=8 {continue;}`
#   guards matching the existing phantom-attack bail; Python sites
#   bounds-check before `self.tile()`. Behavior change: enemies with bogus
#   normalized queued targets now skip their attack instead of panicking.
#   Defensive fix; affected boards previously crashed before predictions
#   could be compared, so no failure_db rows are invalidated. Snapshot
#   kept regardless per CLAUDE.md rule 22.
#
# v28 (2026-04-28, infinite-spawn future_factor floor):
#   Corp HQ M05 (boss-style finale) loss: solver picked a no-attack
#   "JudoMech G3→G7" plan on the bridge-reported "final" turn because
#   `evaluate::future_factor` collapsed to 0 (enemy_killed × 0 = 0). On
#   boss / Mission_Infinite missions the bridge reports
#   total_turns = current_turn every turn (turn_limit=null in
#   data/mission_metadata.json). Fix: bridge reader (src/bridge/reader.py)
#   stamps `is_infinite_spawn=true` on bridge_data for those missions;
#   the Rust solver floors future_factor at 0.5 when set so kills stay
#   meaningful. remaining_spawns=0 still triggers the genuine "no future"
#   path. Rationale: feedback_grid_management.md.
#   Pre-v28 corpus archived as failure_db_snapshot_sim_v27.jsonl.
#
# v29 (2026-04-28, BlobBoss queued-damage persists):
#   M13 turn 4 (Mission_BlobBoss) defeat: WallMech's Grappling Hook pulled
#   BlobBoss D6→E6 and the simulator predicted no D5 hit (Melee handler
#   cancels when curr_dist>1). Real game still applied 4 damage at D5 —
#   the 2-HP Corp Tower fell, grid 2→0, run lost. Per Lua
#   `scripts/missions/bosses/goo.lua:172-187`,
#   `BlobBossAtk:GetSkillEffect` calls
#   `AddQueuedDamage(SpaceDamage(p2, 4))` BEFORE optionally adding the
#   move; queued damage at p2 fires regardless of attacker position. Fix
#   (rust): new `WeaponFlags::QUEUED_DAMAGE_PERSISTS`; new weapon defs
#   `BlobBossAtk` / `BlobBossAtkMed` / `BlobBossAtkSmall` (all 4-damage
#   Melee with the persists flag); `enemy_weapon_for_type` maps the
#   BlobBoss family to them; `apply_enemy_attacks` Melee arm skips its
#   adjacency cancel when the flag is set. Smaller variants confirmed
#   identical via Lua inheritance (`BlobBossAtkMed = BlobBossAtk:new{}`).
#   Pre-v29 corpus archived as failure_db_snapshot_sim_v28.jsonl.
# v30 (2026-04-28) — Mission_Reactivation thaw. Lua mission file
#   `scripts/missions/snow/mission_reactivation.lua` thaws 2 frozen Vek
#   per enemy turn (`Mission_Reactivation:NextTurn` lines 50-66). Rust
#   sim now mirrors this in `simulate_reactivation_thaw` called at the
#   top of `simulate_enemy_attacks` (rust_solver/src/enemy.rs). Pre-fix
#   the solver under-priced threats on Lifeless Basin / any
#   Mission_Reactivation board because frozen Vek looked permanently
#   inert — caused 4-grid leak documented at run 20260425_185532_218.
# v31 (2026-04-28) — Pinnacle Bot Leader weapon defs (SnowBossAtk +
#   BossHeal). `scripts/missions/bosses/bot.lua`:
#     • `SnowBossAtk = SnowartAtk1:new{Damage = 2}` (line 67) —
#       3-tile T artillery (target + both perpendicular tiles for
#       2 damage each) per `weapons_snow.lua:120-135`.
#       `SnowBossAtk2 = same with damage 4` for BotBoss2.
#     • `BossHeal = SelfTarget:new{...}` (lines 28-41) — when the boss
#       is damaged at end of player turn, queues this skill instead of
#       SnowBossAtk; applies Shield IMMEDIATELY and queues +5 HP /
#       remove-shield for the FOLLOWING enemy turn.
#   Pre-v31 the sim fell through to the Boss/Leader unknown-enemy
#   fallback (3-dmg single-target Alpha melee) — plans against Bot
#   Leader mispredicted "deal 3 dmg = boss almost dead" while the real
#   game did 2 dmg × 3-tile splash + auto-shield. Rust changes:
#     1. Three new WIds (SnowBossAtk=119, SnowBossAtk2=120, BossHeal=121).
#     2. `enemy_weapon_for_type`: BotBoss → SnowBossAtk, BotBoss2 →
#        SnowBossAtk2.
#     3. `sim_artillery` (rust_solver/src/simulate.rs) and the enemy.rs
#        Artillery arm now honor `WeaponFlags::AOE_PERP` for the 3-tile
#        T pattern (previously only `sim_melee` + Projectile arm did).
#     4. enemy.rs enemy-attack loop special-cases BossHeal: when the
#        firing unit is BotBoss/BotBoss2, has BossHeal as weapon2, and
#        is damaged (`hp < max_hp`), the dispatch wid is overridden to
#        BossHeal and `apply_weapon_status` is called on the boss's own
#        tile to set the SHIELD flag. Mirrors the Lua `BotBoss:GetWeapon`
#        decision (skill index 2 vs 1).
#   Out of scope: the queued next-turn +5 heal — outside the 1-turn
#   solver horizon. Single-turn prediction now correctly models damage
#   AND end-of-turn shield; multi-turn lookahead can later add the
#   pending-heal as a unit flag.
#   Pre-v31 corpus archived as failure_db_snapshot_sim_v30.jsonl.
SIMULATOR_VERSION = 31


def predicted_states_from_solve_record(record: dict) -> list:
    """Return the per-action predicted_states list from a solve recording.

    Handles both pre-versioning recordings (missing schema_version, treat
    as v1) and current recordings (schema_version=1). Future beam-shape
    records (v2) will also expose predicted_states for the chosen plan;
    this helper is the single extension point.

    Returns an empty list if the record is malformed or the schema is
    unknown — callers should check length before indexing.
    """
    if not isinstance(record, dict):
        return []
    data = record.get("data") or {}
    if not isinstance(data, dict):
        return []
    version = data.get("schema_version", 1)
    if version not in _KNOWN_SOLVE_SCHEMA_VERSIONS:
        # Unknown future version — return what's present so readers can
        # at least attempt a diff, but they'll see a truncated list if
        # the new shape moved predicted_states elsewhere.
        return data.get("predicted_states") or []
    return data.get("predicted_states") or []

# Matches "(x,y)" with optional whitespace, e.g. "Killed Hornet at (3, 5)".
_COORD_RE = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")


def parse_tiles_from_events(events: list[str]) -> list[tuple[int, int]]:
    """Extract every (x, y) coordinate mentioned in event strings.

    Returns a sorted list of unique on-board coordinates.
    """
    tiles: set[tuple[int, int]] = set()
    for ev in events:
        for m in _COORD_RE.finditer(ev):
            x, y = int(m.group(1)), int(m.group(2))
            if 0 <= x < 8 and 0 <= y < 8:
                tiles.add((x, y))
    return sorted(tiles)


def snapshot_after_move(
    board,
    action_index: int,
    mech_uid: int,
    move_events: list[str],
) -> dict:
    """Capture board snapshot after only the move phase.

    Lighter than snapshot_after_action — captures the mech's new position
    and any tile effects from moving (pod collection). Used by the
    verify-after-every-sub-action loop to check the move landed correctly
    before proceeding to the attack phase.
    """
    touched: set[tuple[int, int]] = set(parse_tiles_from_events(move_events))

    for u in board.units:
        if u.uid == mech_uid:
            touched.add((u.x, u.y))
            break

    expanded: set[tuple[int, int]] = set()
    for tx, ty in touched:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = tx + dx, ty + dy
                if 0 <= nx < 8 and 0 <= ny < 8:
                    expanded.add((nx, ny))

    units_snapshot = []
    for u in board.units:
        units_snapshot.append({
            "uid": u.uid,
            "type": u.type,
            "pos": [u.x, u.y],
            "hp": u.hp,
            "max_hp": u.max_hp,
            "alive": u.hp > 0,
            "active": getattr(u, "active", True),
            "is_mech": u.is_mech,
            "team": u.team,
            "status": {
                "fire": u.fire,
                "acid": u.acid,
                "frozen": u.frozen,
                "shield": u.shield,
                "web": u.web,
            },
        })

    tiles_snapshot = []
    for (x, y) in sorted(expanded):
        t = board.tile(x, y)
        tiles_snapshot.append({
            "x": x,
            "y": y,
            "terrain": t.terrain,
            "building_hp": t.building_hp,
            "fire": t.on_fire,
            "acid": t.acid,
            "smoke": t.smoke,
            "has_pod": t.has_pod,
        })

    return {
        "action_index": action_index,
        "mech_uid": mech_uid,
        "snapshot_phase": "after_move",
        "units": units_snapshot,
        "tiles_changed": tiles_snapshot,
        "grid_power": board.grid_power,
    }


def snapshot_after_action(
    board,
    action_index: int,
    mech_uid: int,
    events: list[str],
) -> dict:
    """Capture a JSON-friendly board snapshot after a mech action mutates it.

    Captures EVERY unit (alive or dead) so diff_states can detect
    death/spawn mismatches, but only the tiles touched by the action's
    events (parsed from the events strings, plus a 1-tile buffer for
    chain effects). The mech's current tile is always included.
    """
    touched: set[tuple[int, int]] = set(parse_tiles_from_events(events))

    # Always capture the mech's current tile (move-only actions emit no
    # events but we still want the destination).
    for u in board.units:
        if u.uid == mech_uid:
            touched.add((u.x, u.y))
            break

    # 1-tile buffer for chain effects (Blast Psion explosions, push cascades).
    expanded: set[tuple[int, int]] = set()
    for tx, ty in touched:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = tx + dx, ty + dy
                if 0 <= nx < 8 and 0 <= ny < 8:
                    expanded.add((nx, ny))

    units_snapshot = []
    for u in board.units:
        units_snapshot.append({
            "uid": u.uid,
            "type": u.type,
            "pos": [u.x, u.y],
            "hp": u.hp,
            "max_hp": u.max_hp,
            "alive": u.hp > 0,
            "active": getattr(u, "active", True),
            "is_mech": u.is_mech,
            "team": u.team,
            "status": {
                "fire": u.fire,
                "acid": u.acid,
                "frozen": u.frozen,
                "shield": u.shield,
                "web": u.web,
            },
        })

    tiles_snapshot = []
    for (x, y) in sorted(expanded):
        t = board.tile(x, y)
        tiles_snapshot.append({
            "x": x,
            "y": y,
            "terrain": t.terrain,
            "building_hp": t.building_hp,
            "fire": t.on_fire,
            "acid": t.acid,
            "smoke": t.smoke,
            "has_pod": t.has_pod,
        })

    return {
        "action_index": action_index,
        "mech_uid": mech_uid,
        "snapshot_phase": "after_mech_action",
        "units": units_snapshot,
        "tiles_changed": tiles_snapshot,
        "grid_power": board.grid_power,
    }


@dataclass
class DiffResult:
    """Aggregated diff between a predicted snapshot and an actual Board."""

    unit_diffs: list[dict] = field(default_factory=list)
    tile_diffs: list[dict] = field(default_factory=list)
    scalar_diffs: list[dict] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.unit_diffs or self.tile_diffs or self.scalar_diffs)

    def total_count(self) -> int:
        return (
            len(self.unit_diffs)
            + len(self.tile_diffs)
            + len(self.scalar_diffs)
        )

    def to_dict(self) -> dict:
        return {
            "unit_diffs": self.unit_diffs,
            "tile_diffs": self.tile_diffs,
            "scalar_diffs": self.scalar_diffs,
            "total_count": self.total_count(),
        }


def diff_states(predicted: dict, actual_board) -> DiffResult:
    """Diff a predicted snapshot dict against an actual Board object.

    The actual Board is the live game state from ``read_bridge_state``.
    Only units in either snapshot are inspected, and only tiles in
    ``predicted.tiles_changed`` are checked (no full 64-tile scan).
    """
    result = DiffResult()

    pred_units = {u["uid"]: u for u in predicted.get("units", [])}
    actual_units = {u.uid: u for u in actual_board.units}

    for uid in set(pred_units) | set(actual_units):
        pu = pred_units.get(uid)
        au = actual_units.get(uid)

        if pu is None and au is None:
            continue

        # Unit only in actual: a Vek that spawned mid-turn. Per-action
        # snapshots are pre-end-turn, so this should be rare; flag it.
        if pu is None:
            result.unit_diffs.append({
                "uid": uid,
                "type": au.type,
                "field": "missing_in_predicted",
                "predicted": "absent",
                "actual": "present",
            })
            continue

        # Unit only in predicted: removed by the actual game.
        # Dead enemies are expected to be absent from the bridge —
        # the game engine removes dead Vek entirely (only mech wrecks persist).
        if au is None:
            pu_alive = pu.get("alive", True)
            pu_hp = pu.get("hp", 1)
            if not pu_alive or pu_hp <= 0:
                continue  # expected: dead enemy gone from bridge
            result.unit_diffs.append({
                "uid": uid,
                "type": pu.get("type"),
                "field": "missing_in_actual",
                "predicted": "present",
                "actual": "absent",
            })
            continue

        # Dead-mech equivalence: if both report dead, ignore everything else.
        pu_alive = pu.get("alive", True)
        au_alive = au.hp > 0
        if not pu_alive and not au_alive:
            continue

        if pu_alive != au_alive:
            result.unit_diffs.append({
                "uid": uid,
                "type": au.type,
                "field": "alive",
                "predicted": pu_alive,
                "actual": au_alive,
            })
            # Other field diffs are noise once alive status diverges.
            continue

        if pu.get("hp") != au.hp:
            result.unit_diffs.append({
                "uid": uid,
                "type": au.type,
                "field": "hp",
                "predicted": pu.get("hp"),
                "actual": au.hp,
            })

        pu_pos = tuple(pu.get("pos", [-1, -1]))
        if pu_pos != (au.x, au.y):
            result.unit_diffs.append({
                "uid": uid,
                "type": au.type,
                "field": "pos",
                "predicted": list(pu_pos),
                "actual": [au.x, au.y],
            })

        # Active flag is only meaningful for mechs.
        if au.is_mech:
            pu_active = pu.get("active", True)
            au_active = getattr(au, "active", True)
            if pu_active != au_active:
                result.unit_diffs.append({
                    "uid": uid,
                    "type": au.type,
                    "field": "active",
                    "predicted": pu_active,
                    "actual": au_active,
                })

        pu_status = pu.get("status", {})
        for sf in ("fire", "acid", "frozen", "shield", "web"):
            pv = pu_status.get(sf, False)
            av = getattr(au, sf, False)
            if pv != av:
                result.unit_diffs.append({
                    "uid": uid,
                    "type": au.type,
                    "field": f"status.{sf}",
                    "predicted": pv,
                    "actual": av,
                })

    for pt in predicted.get("tiles_changed", []):
        x, y = pt["x"], pt["y"]
        if not (0 <= x < 8 and 0 <= y < 8):
            continue
        at = actual_board.tile(x, y)

        if pt.get("terrain") != at.terrain:
            result.tile_diffs.append({
                "x": x, "y": y,
                "field": "terrain",
                "predicted": pt.get("terrain"),
                "actual": at.terrain,
            })
        if pt.get("building_hp", 0) != at.building_hp:
            result.tile_diffs.append({
                "x": x, "y": y,
                "field": "building_hp",
                "predicted": pt.get("building_hp", 0),
                "actual": at.building_hp,
            })
        for pred_field, actual_attr in (
            ("fire", "on_fire"),
            ("acid", "acid"),
            ("smoke", "smoke"),
            ("has_pod", "has_pod"),
        ):
            pv = pt.get(pred_field, False)
            av = getattr(at, actual_attr, False)
            if pv != av:
                result.tile_diffs.append({
                    "x": x, "y": y,
                    "field": pred_field,
                    "predicted": pv,
                    "actual": av,
                })

    if predicted.get("grid_power") != actual_board.grid_power:
        result.scalar_diffs.append({
            "field": "grid_power",
            "predicted": predicted.get("grid_power"),
            "actual": actual_board.grid_power,
        })

    return result


# Top-label priority — set by Phase 2's plan, see plan §2C.
_CATEGORY_PRIORITY = [
    "click_miss",
    "mech_position_wrong",
    "move_blocked",
    "death",
    "damage_amount",
    "push_dir",
    "grid_power",
    "status",
    "terrain",
    "tile_status",
    "spawn",
    "pod",
]


def classify_diff(diff: DiffResult, mech_uid: int = None, phase: str = "action") -> dict:
    """Classify a diff into a top category, all categories, and a subcategory.

    Args:
        diff: The DiffResult to classify.
        mech_uid: UID of the acting mech (for mech-specific classification).
        phase: "move", "attack", or "action" (combined). Controls category
               selection for mech position diffs.

    Returns a dict with:
        top_category: str — single label by priority order
        categories:   sorted list[str] — every category that fired
        subcategory:  str | None — e.g. "model_gap_known" for ACID transfer
        model_gap:    bool — true if any diff matches a known sim gap
    """
    categories: set[str] = set()

    for ud in diff.unit_diffs:
        f = ud["field"]
        utype = ud.get("type", "") or ""
        is_mech_diff = mech_uid is not None and ud["uid"] == mech_uid

        if f == "pos":
            if is_mech_diff or "Mech" in utype:
                if phase == "move":
                    categories.add("mech_position_wrong")
                else:
                    categories.add("click_miss")
            else:
                categories.add("push_dir")
        elif f == "active" and is_mech_diff:
            categories.add("click_miss")
        elif f == "alive":
            categories.add("death")
        elif f == "hp":
            categories.add("damage_amount")
        elif f.startswith("status."):
            categories.add("status")
        elif f in ("missing_in_actual", "missing_in_predicted"):
            categories.add("spawn")

    for td in diff.tile_diffs:
        f = td["field"]
        if f == "terrain":
            categories.add("terrain")
        elif f == "building_hp":
            categories.add("grid_power")
        elif f == "has_pod":
            categories.add("pod")
        elif f in ("fire", "acid", "smoke"):
            categories.add("tile_status")

    for sd in diff.scalar_diffs:
        if sd["field"] == "grid_power":
            categories.add("grid_power")
        elif sd["field"] == "spawning_tiles":
            categories.add("spawn")

    # Click_miss subsumes everything: if the mech never moved, nothing
    # downstream of it should have happened either.
    if "click_miss" in categories:
        categories = {"click_miss"}

    top = next((c for c in _CATEGORY_PRIORITY if c in categories), "unknown")

    # Model-gap detection — diffs the Python sim is known to miss.
    subcategory = None
    model_gap = False
    for td in diff.tile_diffs:
        if td["field"] == "acid":
            # ACID tile transfer (when an ACID Vek dies on a tile) is
            # not modeled in Python sim. Tag it so the tuner ignores it.
            subcategory = "model_gap_known"
            model_gap = True
            break

    return {
        "top_category": top,
        "categories": sorted(categories),
        "subcategory": subcategory,
        "model_gap": model_gap,
    }


# Bridge (x,y) → visual A1-H8 (Row=8-x, Col=chr(72-y)).
# CLAUDE.md rule 10: visual notation primary in all communication.
def visual_coord(x: int, y: int) -> str:
    if not (0 <= x < 8 and 0 <= y < 8):
        return f"({x},{y})"
    return f"{chr(72 - y)}{8 - x}"


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_KNOWN_GAPS_CACHE: list[dict] | None = None


def load_known_gaps(path: Path | None = None) -> list[dict]:
    """Load diagnoses/known_gaps.yaml. Returns [] if missing or PyYAML absent.

    Each gap entry is a dict with at minimum:
      id: short slug
      reason: one-line human explanation
      match: dict of diff-shape constraints (diff_kind/field/predicted/actual)
    """
    global _KNOWN_GAPS_CACHE
    if path is None and _KNOWN_GAPS_CACHE is not None:
        return _KNOWN_GAPS_CACHE
    p = path or (_REPO_ROOT / "diagnoses" / "known_gaps.yaml")
    if not p.exists():
        if path is None:
            _KNOWN_GAPS_CACHE = []
        return []
    try:
        import yaml  # type: ignore
    except ImportError:
        if path is None:
            _KNOWN_GAPS_CACHE = []
        return []
    try:
        with open(p) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        if path is None:
            _KNOWN_GAPS_CACHE = []
        return []
    gaps = data.get("known_gaps") or []
    if path is None:
        _KNOWN_GAPS_CACHE = gaps
    return gaps


def _match_gap(diff_entry: dict, kind: str, gaps: list[dict]) -> dict | None:
    """Return first matching known-gap entry, or None."""
    for gap in gaps:
        m = gap.get("match") or {}
        if m.get("diff_kind") and m["diff_kind"] != kind:
            continue
        if "field" in m and diff_entry.get("field") != m["field"]:
            continue
        if "predicted" in m and diff_entry.get("predicted") != m["predicted"]:
            continue
        if "actual" in m and diff_entry.get("actual") != m["actual"]:
            continue
        return gap
    return None


def _diff_signature(kind: str, entry: dict) -> str:
    """Stable signature for dedup against cached diagnoses."""
    if kind == "unit_diff":
        return (
            f"unit:{entry.get('type','?')}:{entry.get('field','?')}:"
            f"{entry.get('predicted')}->{entry.get('actual')}"
        )
    if kind == "tile_diff":
        return (
            f"tile:({entry.get('x')},{entry.get('y')}):{entry.get('field','?')}:"
            f"{entry.get('predicted')}->{entry.get('actual')}"
        )
    return f"scalar:{entry.get('field','?')}:{entry.get('predicted')}->{entry.get('actual')}"


def _load_cached_signatures(run_id: str | None) -> dict[str, str]:
    """Scan recordings/<run_id>/diagnoses/*.md for previously-diagnosed signatures.

    Returns a map of diff_signature → failure_id. Only the current run's
    diagnoses are considered (cross-run reuse is PR3 territory).
    """
    if not run_id:
        return {}
    diag_dir = _REPO_ROOT / "recordings" / run_id / "diagnoses"
    if not diag_dir.exists():
        return {}
    out: dict[str, str] = {}
    for md in diag_dir.glob("*.md"):
        try:
            text = md.read_text()
        except OSError:
            continue
        # Frontmatter is YAML between leading "---" lines; bail if missing.
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end < 0:
            continue
        try:
            import yaml  # type: ignore
            fm = yaml.safe_load(text[3:end]) or {}
        except Exception:
            continue
        fid = fm.get("failure_id") or fm.get("id")
        for sig in (fm.get("diff_signatures") or []):
            if sig and fid and sig not in out:
                out[sig] = fid
    return out


_WEAPON_DESC_HINTS = ("at ", "fire ", "move ")


def _action_summary(action: dict | None) -> str:
    """One-line description for the diff header."""
    if not action:
        return "(action unknown)"
    desc = action.get("description")
    if desc:
        return desc
    parts = []
    mt = action.get("mech_type")
    if mt:
        parts.append(mt)
    weapon = action.get("weapon")
    if weapon and weapon != "Unknown":
        parts.append(weapon)
    target = action.get("target")
    if target and target != [255, 255]:
        parts.append(f"at {visual_coord(target[0], target[1])}")
    return " ".join(parts) if parts else "(action unknown)"


def format_diff_for_log(
    diff: DiffResult,
    action_index: int,
    action: dict | None = None,
    failure_id: str | None = None,
    run_id: str | None = None,
    known_gaps: list[dict] | None = None,
    cached_sigs: dict[str, str] | None = None,
) -> str:
    """Pretty-print a DiffResult for terminal display + log file.

    Tags each diff line with one of:
      [novel]                  — no prior knowledge of this signature
      [known-gap: <id>]        — matches an entry in diagnoses/known_gaps.yaml
      [cached: <failure_id>]   — already diagnosed in this run

    Visual A1-H8 coords primary, bridge (x,y) secondary (CLAUDE.md rule 10).
    """
    if diff.is_empty():
        return f"=== VERIFY {action_index}: PASS (no diffs) ==="

    if known_gaps is None:
        known_gaps = load_known_gaps()
    if cached_sigs is None:
        cached_sigs = _load_cached_signatures(run_id)

    summary = _action_summary(action)
    total = diff.total_count()
    lines: list[str] = []
    header = f"=== DESYNC: Action {action_index} ({summary}) — {total} diffs ==="
    if failure_id:
        header += f" [failure_id={failure_id}]"
    lines.append(header)

    known_gap_count = 0
    cached_count = 0

    def tag(kind: str, entry: dict) -> str:
        nonlocal known_gap_count, cached_count
        sig = _diff_signature(kind, entry)
        gap = _match_gap(entry, kind, known_gaps)
        if gap is not None:
            known_gap_count += 1
            return f"[known-gap: {gap.get('id', 'unknown')}]"
        cached_id = cached_sigs.get(sig)
        if cached_id:
            cached_count += 1
            return f"[cached: {cached_id}]"
        return "[novel]"

    if diff.unit_diffs:
        lines.append("")
        lines.append("UNITS:")
        for ud in diff.unit_diffs:
            utype = str(ud.get("type", "?"))
            uid = str(ud.get("uid", "?"))
            field_name = str(ud.get("field", "?"))
            pred = ud.get("predicted")
            actual = ud.get("actual")
            t = tag("unit_diff", ud)
            lines.append(
                f"  {utype:<14}  uid={uid:<4}  {field_name:<18}  "
                f"pred={str(pred):<12}  actual={str(actual):<12}  {t}"
            )

    if diff.tile_diffs:
        lines.append("")
        lines.append("TILES:")
        for td in diff.tile_diffs:
            x = td.get("x", 0)
            y = td.get("y", 0)
            vc = visual_coord(x, y)
            field_name = str(td.get("field", "?"))
            pred = td.get("predicted")
            actual = td.get("actual")
            t = tag("tile_diff", td)
            lines.append(
                f"  {vc:<4} ({x},{y})    {field_name:<18}  "
                f"pred={str(pred):<12}  actual={str(actual):<12}  {t}"
            )

    if diff.scalar_diffs:
        lines.append("")
        lines.append("SCALARS:")
        for sd in diff.scalar_diffs:
            field_name = str(sd.get("field", "?"))
            pred = sd.get("predicted")
            actual = sd.get("actual")
            t = tag("scalar_diff", sd)
            lines.append(
                f"  {field_name:<18}  pred={str(pred):<12}  "
                f"actual={str(actual):<12}  {t}"
            )

    classification = classify_diff(
        diff,
        mech_uid=(action or {}).get("mech_uid"),
    )
    cats = classification.get("categories") or []
    if cats:
        from collections import Counter
        per_cat = Counter()
        for ud in diff.unit_diffs:
            f = ud.get("field", "")
            if f == "pos":
                per_cat["push_dir/pos"] += 1
            elif f == "active":
                per_cat["active"] += 1
            elif f == "alive":
                per_cat["death"] += 1
            elif f == "hp":
                per_cat["damage_amount"] += 1
            elif f.startswith("status."):
                per_cat["status"] += 1
            elif f in ("missing_in_actual", "missing_in_predicted"):
                per_cat["spawn"] += 1
            else:
                per_cat[f or "unknown"] += 1
        for td in diff.tile_diffs:
            f = td.get("field", "")
            if f == "terrain":
                per_cat["terrain"] += 1
            elif f == "building_hp":
                per_cat["grid_power"] += 1
            elif f == "has_pod":
                per_cat["pod"] += 1
            else:
                per_cat["tile_status"] += 1
        for sd in diff.scalar_diffs:
            per_cat[sd.get("field", "scalar")] += 1
        cat_str = ", ".join(f"{k} × {v}" for k, v in per_cat.most_common())
        lines.append("")
        lines.append(f"CATEGORIES:  {cat_str}")

    novel_count = total - known_gap_count - cached_count
    lines.append("")
    lines.append(f"Known gaps folded: {known_gap_count} of {total} diffs")
    lines.append(f"Cached prior:      {cached_count} of {total} diffs")
    lines.append(f"Novel diffs:       {novel_count} of {total} diffs")

    if novel_count > 0:
        lines.append("")
        if failure_id:
            lines.append(
                f"Run `python3 game_loop.py diagnose {failure_id}` to "
                "produce a fix proposal."
            )
        else:
            lines.append(
                "Run `python3 game_loop.py diagnose <failure_id>` to "
                "produce a fix proposal."
            )

    return "\n".join(lines)
