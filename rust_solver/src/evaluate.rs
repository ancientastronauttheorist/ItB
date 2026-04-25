/// Board evaluation function for the solver.
///
/// Scores a board position: buildings, grid power, enemies, mechs, spawns, pods.
/// Higher score = better for the player.
///
/// Turn-aware scoring: weights scale based on turns remaining.
/// Kills are worth MORE on early turns (prevent future attacks) and LESS on
/// the final turn (no future to protect). Buildings never scale (always critical).

use serde::Deserialize;
use crate::types::*;
use crate::board::*;

// ── Turn-aware scaling helpers ──────────────────────────────────────────────

/// Compute future_factor: 1.0 on first combat turn, 0.0 on final turn.
/// current_turn is 0-indexed from bridge (0 = deployment, 1 = first combat).
///
/// `remaining_spawns` collapses the factor to 0 when no more Vek will emerge
/// after this turn's enemy phase — this is the "victory in 1 turn" case where
/// bridge total_turns can report more turns than the mission actually lasts.
/// When remaining_spawns is 0 and the board has no live threats beyond the
/// queued attacks, there is no future to prepare for.
fn future_factor(current_turn: u8, total_turns: u8, remaining_spawns: u32) -> f64 {
    if remaining_spawns == 0 { return 0.0; }
    if total_turns <= 1 { return 0.0; }
    // Combat turn = current_turn - 1 (turn 0 is deployment)
    // But clamp so we don't go negative
    let combat_turn = if current_turn > 0 { current_turn - 1 } else { 0 };
    let remaining = total_turns.saturating_sub(combat_turn + 1) as f64;
    let max_remaining = (total_turns - 1) as f64;
    (remaining / max_remaining).clamp(0.0, 1.0)
}

/// Scale a weight: base * (floor + scale * future_factor).
/// On first combat turn (ff=1.0): base * (floor + scale)
/// On final turn (ff=0.0): base * floor
#[inline]
fn scaled(base: f64, ff: f64, floor: f64, scale: f64) -> f64 {
    base * (floor + scale * ff)
}

// ── EvalWeights ──────────────────────────────────────────────────────────────

#[derive(Clone, Debug, Deserialize)]
#[serde(default)]
pub struct EvalWeights {
    // Core weights
    pub building_alive: f64,
    pub building_hp: f64,
    pub grid_power: f64,
    pub enemy_killed: f64,
    pub enemy_hp_remaining: f64, // negative
    pub mech_killed: f64,        // negative
    pub mech_hp: f64,
    pub spawn_blocked: f64,
    pub pod_uncollected: f64,    // negative
    pub pod_proximity: f64,
    pub enemy_on_danger: f64,

    // Psion kill bonuses (scaled by future_factor)
    pub psion_blast: f64,
    pub psion_shell: f64,
    pub psion_soldier: f64,
    pub psion_blood: f64,
    pub psion_tyrant: f64,

    // Status effect bonuses
    pub enemy_on_fire_bonus: f64,    // enemy on fire (will take 1 dmg/turn)
    pub mech_on_acid: f64,           // mech standing on ACID pool (penalty)
    pub mech_self_frozen: f64,       // mech frozen by own move (freeze mine) — loses next turn
    pub mech_low_hp_risk: f64,       // 1HP mech near active enemy (binary, negative)
    pub friendly_npc_killed: f64,    // non-mech player unit killed (penalty)
    pub volatile_enemy_killed: f64,  // Volatile Vek killed (Weather Watch ⭐ bonus)

    // Grid urgency multipliers (applied to building scores)
    pub grid_urgency_critical: f64,  // grid_power <= 1
    pub grid_urgency_high: f64,      // grid_power == 2
    pub grid_urgency_medium: f64,    // grid_power == 3

    // Pro-strategy weights
    pub threats_cleared: f64,        // reward per building threat neutralized
    pub body_block_bonus: f64,       // reward per mech absorbing a building threat
    pub building_coverage: f64,      // bonus per building within mech reach
    pub uncovered_building: f64,     // penalty per building not near any mech (negative)
    pub perfect_defense_bonus: f64,  // bonus when ALL building threats cleared
    pub mech_sacrifice_at_critical: f64, // reduces mech_killed penalty at grid<=2 (positive)

    // Achievement-specific (all default 0 — no effect in normal play)
    pub enemy_on_fire: f64,
    pub enemy_pushed_into_enemy: f64,
    pub chain_damage: f64,
    pub smoke_placed: f64,
    pub tiles_frozen: f64,

    // Mission-specific bonus objectives (0 default; turn-aware via `scaled`).
    // Old Earth Dam: +1 Rep + 14-tile flood that drowns grounded Vek for rest
    // of mission. Active only when weights/active.json sets a non-zero value.
    pub dam_destroyed: f64,
    // Partial-credit reward per HP of damage dealt to Dam_Pawn this turn.
    // Lets the solver chip the Dam across multiple turns when it can't
    // finish in one — dam_destroyed only fires on the alive→dead transition,
    // so without this the solver sees no value in a 1-damage hit that
    // doesn't kill. Positive value ≈ dam_destroyed / 2.
    pub dam_damage_dealt: f64,

    // Building protection: penalty for push-bump collateral damage
    pub building_bump_damage: f64,

    // Objective building bonus (Coal Plant, Power Generator, Emergency Batteries)
    pub building_objective_bonus: f64,

    // ⚡ Grid-reward objective bonus (Str_Power / Str_Battery / Mission_Solar).
    // Survival grants +1 Grid Power at mission end. Scored with bld_mult
    // (NOT grid_multiplier) to match other building scoring and avoid the
    // inversion bug where a safely-out-of-reach grid-reward building would
    // pay out more as grid depletes, incentivizing the solver to drop grid
    // just to inflate its own bonus. Higher base weight (≈3× rep-only)
    // reflects the mission-end +1 grid vs +1 rep value.
    pub grid_reward_building_bonus: f64,

    // Boss kill bonus (mission objective: destroy the Hornet Leader, etc.)
    pub boss_killed_bonus: f64,

    // "Kill N enemies" bonus (BONUS_KILL_FIVE). Step function that fires
    // exactly once per mission — on the plan whose cumulative kills cross
    // board.mission_kill_target. See the scoring block below for the
    // pre-turn-below / post-turn-at-or-above check.
    pub mission_kill_bonus: f64,

    // Context-aware building multiplier knobs
    pub bld_grid_floor: f64,
    pub bld_grid_scale: f64,
    pub bld_phase_floor: f64,
    pub bld_phase_scale: f64,

    // Two-stage solver filter: prefer clean plans within this margin of best
    pub building_preservation_threshold: f64,

    // Flat danger penalty per queued Vek spawn still to emerge
    // (`board.remaining_spawns`). Covers the "surprise" damage from the
    // next-turn materialize+attack that the sim does NOT project — the
    // evaluator models spawn-blocking on current spawn tiles but never
    // instantiates the spawned Vek to simulate turn+1. Scaled by
    // future_factor so it collapses to 0 on the final turn.
    //
    // Magnitude rationale: a spawn that emerges into a Scarab/Hornet
    // typically costs ~1 building HP = 1 grid (≈25k points). ~40% of
    // spawns deal net building damage after accounting for kills on
    // emerge, blockable tiles, and weak variants (Alpha Scarab 1HP),
    // giving ~10k per spawn.
    pub remaining_spawn_penalty: f64,

    // Turn+1 threat preview: penalty per surviving enemy that can reach
    // a building within its taxicab move+range envelope on its next turn.
    // Mitigates the "solver kills 2 weak enemies and lets the grid bleed
    // turn+1" pattern observed on Pinnacle Ice Forest / Detritus CZD
    // where the 1-turn evaluator can't see that the REMAINING enemies
    // will destroy buildings next turn. Scaled by future_factor so it
    // collapses to 0 on the final turn.
    pub next_turn_threat_penalty: f64,

    // Phase 1 soft-disable penalty: subtracted once per action in a
    // candidate plan that uses a weapon in the session's disabled_actions
    // mask. Tuned to be large enough that the solver prefers any viable
    // alternative but small enough that a caged mech can still use the
    // weapon if nothing else scores above -penalty. Default sized to
    // roughly one building_alive: the solver will sacrifice a building
    // before using a soft-disabled weapon 10+ times in one turn, but
    // won't throw the mission for a single forced use.
    pub soft_disabled_penalty: f64,

    // Option C evaluator augmentation: "queueless threat" signal for projected
    // boards. When `true`, `evaluate` applies an extra 1.5× next_turn_threat_penalty
    // per alive enemy that has NO queued target (queued_target_x < 0) AND can
    // reach a building within `move_speed + 4` Manhattan distance. This
    // compensates for the fact that projected boards (from `project_plan`) have
    // cleared enemy targets — the normal `next_turn_threat_penalty` block only
    // fires for enemies WITH queued targets.
    //
    // Default: `false` — the augmentation does NOT run on the standard 1-turn
    // evaluation path, so it cannot alter regression scores. It must be explicitly
    // enabled by setting this to `true` (done by `project_plan`'s returned
    // `board_to_json` via `eval_weights.pseudo_threat_eval`). This gating ensures
    // no SIMULATOR_VERSION bump is required.
    #[serde(default)]
    pub pseudo_threat_eval: bool,
}

impl Default for EvalWeights {
    fn default() -> Self {
        EvalWeights {
            building_alive: 10000.0,
            building_hp: 2000.0,
            grid_power: 5000.0,
            enemy_killed: 500.0,
            enemy_hp_remaining: -100.0,
            mech_killed: -150000.0,
            mech_hp: 100.0,
            spawn_blocked: 1000.0,
            pod_uncollected: -100.0,
            pod_proximity: 50.0,
            enemy_on_danger: 800.0,
            // Psion kill bonuses
            psion_blast: 2000.0,
            psion_shell: 1500.0,
            psion_soldier: 4000.0,
            psion_blood: 1600.0,
            psion_tyrant: 2500.0,
            // Status bonuses
            enemy_on_fire_bonus: 100.0,
            mech_on_acid: -200.0,
            mech_self_frozen: -12000.0,
            mech_low_hp_risk: -2000.0,
            friendly_npc_killed: -20000.0,  // 2x building value — never sacrifice NPCs for kills
            volatile_enemy_killed: -10000.0, // Volatile Vek must not die (Weather Watch ⭐)
            // Pro-strategy
            threats_cleared: 4000.0,
            body_block_bonus: 0.0,
            building_coverage: 50.0,
            uncovered_building: -500.0,
            perfect_defense_bonus: 6000.0,
            mech_sacrifice_at_critical: 0.0,  // was 50000; created perverse incentive to sacrifice at low grid without body-block context (2026-04-17)
            // Grid urgency
            grid_urgency_critical: 5.0,
            grid_urgency_high: 3.0,
            grid_urgency_medium: 3.0,
            // Achievement (all zero by default)
            enemy_on_fire: 0.0,
            enemy_pushed_into_enemy: 0.0,
            chain_damage: 0.0,
            smoke_placed: 0.0,
            tiles_frozen: 0.0,
            // Mission-specific bonuses (zero by default; set via active.json)
            dam_destroyed: 0.0,
            dam_damage_dealt: 0.0,
            // Building protection
            building_bump_damage: -8000.0,
            building_objective_bonus: 8000.0,
            grid_reward_building_bonus: 25000.0,
            boss_killed_bonus: 8000.0,
            mission_kill_bonus: 15000.0,
            bld_grid_floor: 0.6,
            bld_grid_scale: 0.4,
            bld_phase_floor: 1.0,
            bld_phase_scale: 0.0,
            building_preservation_threshold: 0.05,
            soft_disabled_penalty: 10000.0,
            remaining_spawn_penalty: 10000.0,
            next_turn_threat_penalty: 2500.0,
            pseudo_threat_eval: false,
        }
    }
}

// ── evaluate ─────────────────────────────────────────────────────────────────

/// Score a board state. Higher = better.
///
/// Turn-aware: weights for kills, damage, spawns, and mechs scale with
/// `future_factor` (1.0 on first combat turn, 0.0 on final turn).
/// Building and grid_power weights never scale (always critical).
///
/// Snapshot of Psion state before mech actions.
#[derive(Clone, Debug, Default)]
pub struct PsionState {
    pub blast: bool,
    pub armor: bool,
    pub soldier: bool,
    pub regen: bool,
    pub tyrant: bool,
    pub boss: bool,
    /// Not a Psion — but captured alongside Psion state for the same
    /// before→after transition-scoring pattern used by psion_* bonuses.
    pub dam: bool,
    /// Max HP across any Dam_Pawn tile at snapshot time (tiles share HP via
    /// uid mirroring, so any alive tile's hp is the Dam's hp). Used for
    /// partial-credit dam_damage_dealt scoring.
    pub dam_hp: i8,
}

impl PsionState {
    pub fn capture(board: &Board) -> Self {
        PsionState {
            blast: board.blast_psion,
            armor: board.armor_psion,
            soldier: board.soldier_psion,
            regen: board.regen_psion,
            tyrant: board.tyrant_psion,
            boss: board.boss_alive,
            dam: board.dam_alive,
            dam_hp: dam_hp(board),
        }
    }
}

/// Read the current Dam HP (any Dam_Pawn tile, since HP is mirrored).
/// Returns 0 if no Dam_Pawn is alive.
fn dam_hp(board: &Board) -> i8 {
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.type_name_str() == "Dam_Pawn" && u.hp > 0 {
            return u.hp;
        }
    }
    0
}

/// `kills` is passed explicitly because dead enemies are filtered from iteration.
/// `spawn_points` are next turn's Vek spawn locations.
/// `psion_before`: snapshot of Psion state before mech actions — used to detect kills.
pub fn evaluate(
    board: &Board,
    spawn_points: &[(u8, u8)],
    weights: &EvalWeights,
    kills: i32,
    building_bumps: i32,
    psion_before: &PsionState,
    initial_building_threats: u64,
) -> f64 {
    // Effective grid = deterministic grid_power + expected Grid Defense
    // save (fractional grid saved by the 15%-ish resist-chance). Used for
    // urgency/game_over/scoring so the solver isn't pessimistic about
    // buildings the game will actually save.
    let eff_grid = board.grid_power as f64 + board.enemy_grid_save_expected as f64;

    // Game over: expected grid below half a point (≈ ≤0 actual).
    // Instead of flat -999999, use -500000 + normal score so the solver
    // can rank bad options (e.g. "lose 1 building" > "lose 3 buildings").
    // -500000 keeps all game-over states strictly below any non-game-over
    // (worst non-game-over is ~-275000 with 2 dead mechs at -150000 each).
    let game_over = eff_grid < 0.5;

    let mut score = 0.0;
    let ff = future_factor(board.current_turn, board.total_turns, board.remaining_spawns);

    // Grid power urgency multiplier — gate on RAW grid_power so the 15%
    // defense's expected-save (which inflates eff_grid by ~0.15 per hit)
    // can't push grid=3 above the `<= 3` medium threshold.
    let grid_multiplier = if board.grid_power <= 1 {
        weights.grid_urgency_critical
    } else if board.grid_power <= 2 {
        weights.grid_urgency_high
    } else if board.grid_power <= 3 {
        weights.grid_urgency_medium
    } else { 1.0 };

    // ── Buildings: context-aware multiplier, NO urgency multiplier ───────
    // bld_mult scales building value by grid health and mission phase.
    // Goes DOWN at low grid (opposite of urgency), so more-buildings always
    // beats fewer — avoids the old inversion bug.
    let grid_health = eff_grid / board.grid_power_max.max(1) as f64;
    let mission_phase = if board.total_turns > 1 {
        (board.current_turn.saturating_sub(1) as f64) / (board.total_turns - 1) as f64
    } else { 0.0 };
    let grid_factor = weights.bld_grid_floor + weights.bld_grid_scale * grid_health;
    let phase_factor = weights.bld_phase_floor + weights.bld_phase_scale * (1.0 - mission_phase);
    let bld_mult = grid_factor * phase_factor;

    let mut buildings_alive = 0i32;
    let mut total_building_hp = 0i32;
    let mut objective_rep_alive = 0i32;
    let mut objective_grid_alive = 0i32;
    for (idx, tile) in board.tiles.iter().enumerate() {
        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
            buildings_alive += 1;
            total_building_hp += tile.building_hp as i32;
            if (board.unique_buildings & (1u64 << idx)) != 0 {
                if (board.grid_reward_buildings & (1u64 << idx)) != 0 {
                    objective_grid_alive += 1;
                } else {
                    objective_rep_alive += 1;
                }
            }
        }
    }
    score += buildings_alive as f64 * weights.building_alive * bld_mult;
    score += total_building_hp as f64 * weights.building_hp * bld_mult;
    // ⭐ rep-only (Clinic/Nimbus/Tower): flat bonus × bld_mult.
    score += objective_rep_alive as f64 * weights.building_objective_bonus * bld_mult;
    // ⚡ grid-reward (Power/Battery/Solar): higher base weight but SAME
    // bld_mult pattern as other buildings — using grid_multiplier here
    // would invert: at low grid, an untouchable grid-reward building would
    // pay out more, and the solver would intentionally drop grid to
    // inflate its own bonus. bld_mult (goes DOWN at low grid) avoids that.
    score += objective_grid_alive as f64 * weights.grid_reward_building_bonus * bld_mult;

    // ── Bump penalty: extra cost for push-chain collateral to buildings ──
    score += building_bumps as f64 * weights.building_bump_damage;

    // ── Grid power: monotonic reward + below-threshold urgency penalty ─
    // Previous version multiplied `remaining_grid * weight * grid_multiplier`,
    // which made end-state grid=3 (1.0 multiplier → 3.0) score HIGHER than
    // end-state grid=5 (1.0 multiplier) — a perverse incentive that
    // let Turn 2 on Ice Forest (2026-04-24) choose a plan ending at grid=3
    // over plans preserving grid=5. Fix: linear monotonic base reward, plus
    // a below-threshold penalty that scales with (multiplier - 1.0) so urgency
    // still disincentivizes slipping toward 0 without breaking monotonicity.
    // The urgency multiplier continues to scale enemy_urgency + env_danger
    // terms below — only the direct grid_power reward needed this fix.
    score += eff_grid * weights.grid_power;
    let crisis_threshold: f64 = 4.0;
    if eff_grid < crisis_threshold {
        let gap = crisis_threshold - eff_grid;
        score -= gap * weights.grid_power * (grid_multiplier - 1.0);
    }

    // ── Enemies: SCALED (kills worth more early, less on final turn) ────
    // kill_value = 500 * (0.20 + 1.60 * ff) → turn 1: 900, mid: 500, final: 100
    // At low grid, kills and leftover HP matter more: a 1-turn lookahead
    // solver can't anticipate turn N+1 threats, so we approximate "future
    // grid risk" by scaling both the kill bonus and the hp-remaining penalty
    // with grid_multiplier. Gated to multipliers > 1.0 so normal-grid play
    // isn't distorted.
    let enemy_urgency = if grid_multiplier > 1.0 { grid_multiplier } else { 1.0 };
    score += kills as f64 * scaled(weights.enemy_killed, ff, 0.20, 1.60) * enemy_urgency;
    let mut volatile_dead = 0i32;
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.is_enemy() && u.alive() {
            // damage_value = -50 * (0.10 + 0.90 * ff) → final: -5
            score += u.hp as f64 * scaled(weights.enemy_hp_remaining, ff, 0.10, 0.90) * enemy_urgency;
        }
        // Weather Watch ⭐ bonus: "Don't let the Volatile Vek die." Count
        // dead Volatile-type enemies on the post-state board — solver clones
        // the initial board each plan, so dead-at-end = killed-this-turn.
        // Shares the Unit::is_volatile_vek() helper used by the decay sim
        // so the penalty and the explosion trigger always agree.
        if u.is_enemy() && !u.alive() && u.is_volatile_vek() {
            volatile_dead += 1;
        }
    }
    score += volatile_dead as f64 * weights.volatile_enemy_killed;

    // ── Threats cleared: reward neutralizing building threats ─────────
    // Compare initial building_threats bitset against post-attack survival.
    // Any threatened building that survived = a cleared threat (push, kill,
    // freeze, smoke, body-block — all count).
    // NOTE: No grid_multiplier here — applying it caused an inversion where
    // letting buildings die (dropping GP) gave the REMAINING cleared-threat
    // scores a 4x boost, which made destruction score higher than defense.
    if initial_building_threats != 0 {
        let mut all_cleared = true;
        let mut bits = initial_building_threats;
        while bits != 0 {
            let bit_idx = bits.trailing_zeros() as usize;
            bits &= bits - 1; // clear lowest set bit
            let (tx, ty) = idx_to_xy(bit_idx);
            let tile = board.tile(tx, ty);
            if tile.terrain == Terrain::Building && tile.building_hp > 0 {
                // Building survived — this threat was cleared
                score += scaled(weights.threats_cleared, ff, 0.30, 0.70);
                // Body-block bonus: mech standing on this threat tile absorbed the hit
                if let Some(idx) = board.unit_at(tx, ty) {
                    if board.units[idx].is_player() && board.units[idx].is_mech() {
                        score += scaled(weights.body_block_bonus, ff, 0.20, 0.80);
                    }
                }
            } else {
                all_cleared = false;
            }
        }
        // Perfect defense bonus: ALL initially-threatened buildings survived
        if all_cleared {
            score += weights.perfect_defense_bonus;
        }
    }

    // ── Psion kill bonuses: SCALED by future_factor (from weights) ──────
    if psion_before.blast && !board.blast_psion {
        score += weights.psion_blast * ff;
    }
    if psion_before.armor && !board.armor_psion {
        score += weights.psion_shell * ff;
    }
    if psion_before.soldier && !board.soldier_psion {
        score += weights.psion_soldier * ff;
    }
    if psion_before.regen && !board.regen_psion {
        score += weights.psion_blood * ff;
    }
    if psion_before.boss && !board.boss_alive {
        score += weights.boss_killed_bonus * ff;
    }
    if psion_before.tyrant && !board.tyrant_psion {
        score += weights.psion_tyrant * ff;
    }

    // ── Mission bonus: Old Earth Dam destroyed ──
    // Turn-aware (unlike building_alive): a destroyed dam is worth ~1 rep
    // regardless of turn, but the 14-tile flood's tactical value scales with
    // turns remaining. scaled() floor=0.10 keeps the +1 Rep base value on
    // the final turn while giving earlier turns the full flood-denial reward.
    if psion_before.dam && !board.dam_alive {
        score += scaled(weights.dam_destroyed, ff, 0.10, 0.90);
    }

    // Partial-credit chip damage on the Dam (Dam still alive after turn).
    // Without this, a 1-damage hit that doesn't kill scores 0 from dam_destroyed,
    // so the solver never chips across turns. Only credit while Dam is still
    // alive — the full dam_destroyed bonus covers the killing blow.
    if psion_before.dam && board.dam_alive {
        let hp_after = dam_hp(board);
        let damage_dealt = (psion_before.dam_hp - hp_after).max(0) as f64;
        if damage_dealt > 0.0 {
            score += weights.dam_damage_dealt * damage_dealt;
        }
    }

    // ── Mission bonus: "Kill N enemies" threshold cross ─────────────────
    // Step function — fires exactly once per mission on the plan that
    // pushes cumulative kills across the target. Pre-turn < target AND
    // post-turn ≥ target is the cross condition. scaled() floor=0.25
    // leaves a meaningful bonus even on the final turn since unlocking
    // the rep star still matters.
    let kt = board.mission_kill_target as i32;
    if kt > 0 {
        let kd = board.mission_kills_done as i32;
        if kd < kt && kd + kills >= kt {
            score += scaled(weights.mission_kill_bonus, ff, 0.25, 0.75);
        }
    }

    // ── Environment danger: enemy scaled like kills, mech like mech_killed ─
    //
    // This branch fires for LIVE units still on a danger tile at scoring time.
    // `simulate_enemy_attacks` has already applied env_danger damage before
    // reaching here, so most deaths are counted in the main mech-death branch
    // below. This loop catches the remaining cases:
    //   - Non-lethal env survivors (shield consumed, frozen unfrozen): unit is
    //     still alive but sitting on a danger tile — soft penalty for the tile.
    //   - Enemies on danger tiles: partial-credit reward toward enemy_killed
    //     (assumes the hazard will finish them next turn).
    //
    // IMPORTANT: Most lethal env (kill_int=1, Air Strike / Lightning / Satellite)
    // bypasses flying, so a flying mech on such a tile IS killed by the simulator
    // (enemy.rs::apply_env_danger). Tidal Wave / Cataclysm / Seismic — flagged
    // env_danger_flying_immune — skip flyers; the simulator leaves them alive.
    // The flying skip here is correct for NON-lethal branches (wind/sand/snow
    // don't affect flying) AND for flying_immune-lethal branches; we explicitly
    // penalize flying mechs sitting on non-flying-immune kill_int=1 tiles as
    // belt-and-suspenders in case the simulator order changes or a search branch
    // evaluates pre-enemy-phase (e.g. a push chain that lands a mech on the tile
    // AFTER env_danger already ticked).
    if board.env_danger != 0 {
        for i in 0..board.unit_count as usize {
            let u = &board.units[i];
            if !u.alive() { continue; }
            if !board.is_env_danger(u.x, u.y) { continue; }

            let on_kill_tile = board.is_env_danger_kill(u.x, u.y);
            let on_flying_immune_kill = on_kill_tile
                && board.is_env_danger_flying_immune(u.x, u.y);

            if u.is_player() && on_kill_tile {
                // Flying mech on Tidal/Cataclysm/Seismic tile survives —
                // skip the defensive death penalty (the simulator agrees).
                if u.effectively_flying() && on_flying_immune_kill {
                    continue;
                }
                // Defensive penalty: a player mech on a kill_int=1 tile is a
                // pending death regardless of flying status. The simulator
                // should already have killed it (firing the main mech-death
                // branch), but this guards against off-sequence scoring.
                let base = scaled(weights.mech_killed, ff, 0.05, 0.95);
                let pilot_penalty = if board.medical_supplies {
                    0.0
                } else {
                    weights.mech_killed * u.pilot_value as f64
                };
                score += base + pilot_penalty;
                continue;
            }

            if u.flying() { continue; }

            if u.is_enemy() {
                score += scaled(weights.enemy_on_danger, ff, 0.20, 1.60);
            } else if u.is_player() {
                // Non-lethal env: soft penalty for a mech taking the hit next
                // enemy phase (1 dmg). Matches the mech-loss magnitude for
                // consistency with the existing tuner corpus. Medical Supplies
                // still zeroes the pilot-loss component — if the 1 dmg kills
                // a low-HP mech (shouldn't happen on non-lethal env, but
                // conservative), the pilot still revives.
                let base = scaled(weights.mech_killed, ff, 0.05, 0.95);
                let pilot_penalty = if board.medical_supplies {
                    0.0
                } else {
                    weights.mech_killed * u.pilot_value as f64
                };
                score += base + pilot_penalty;
            }
        }
    }

    // ── Enemies on fire: SCALED (will take 1 damage next turn) ─────────
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if u.is_enemy() && u.alive() && u.fire() {
            score += scaled(weights.enemy_on_fire_bonus, ff, 0.5, 0.5);
        }
    }

    // ── Mechs: SCALED (mech loss/HP matters less on final turn) ─────────
    for i in 0..board.unit_count as usize {
        let u = &board.units[i];
        if !u.is_player() { continue; }

        if !u.is_mech() {
            // Non-mech player units (ArchiveArtillery, Filler_Pawn, etc.)
            // Killing them loses a body-blocker and often involves pushing
            // them into buildings. Penalize to prevent sacrifice.
            if u.hp <= 0 {
                score += weights.friendly_npc_killed;
            }
            continue;
        }

        if u.hp <= 0 {
            // Scale mech loss by future_factor: a pilot lost on the final
            // turn can't contribute further this mission, so the penalty
            // drops to 5% of base. Early turns still keep mechs precious
            // (ff≈1 → full penalty). floor=0.05, scale=0.95.
            //
            // Pilot value adds a permanent-loss component that DOES NOT
            // scale with ff: a veteran pilot is lost forever (no XP/skills
            // for remaining missions) and its cost applies regardless of
            // how many turns remain in this mission.
            //
            // Passive_Medical ("Medical Supplies") revives all pilots on
            // death — the pilot is NOT permanently lost, so the pilot-value
            // component is zeroed. The mech itself is still destroyed, so
            // base_penalty (grid/HP consequences) still applies.
            let base_penalty = scaled(weights.mech_killed, ff, 0.05, 0.95);
            let pilot_penalty = if board.medical_supplies {
                0.0
            } else {
                weights.mech_killed * u.pilot_value as f64
            };
            let mut penalty = base_penalty + pilot_penalty;
            // At critical grid, reduce mech death penalty — losing a mech is
            // preferable to losing the game from undefended buildings
            if board.grid_power <= 2 {
                penalty += weights.mech_sacrifice_at_critical;
            }
            score += penalty;
        } else {
            score += u.hp as f64 * scaled(weights.mech_hp, ff, 0.20, 0.80);

            // ACID tile avoidance: penalize mech on ACID pool
            let tile = board.tile(u.x, u.y);
            if tile.acid() && tile.terrain != Terrain::Water {
                score += scaled(weights.mech_on_acid, ff, 0.50, 0.50);
            }

            // Frozen mech: loses entire next turn of actions
            if u.frozen() {
                score += scaled(weights.mech_self_frozen, ff, 0.30, 0.70);
            }

            // Low-HP risk: penalize 1HP mech near active (non-frozen/smoked) enemies
            if u.hp == 1 {
                let dominated = (0..board.unit_count as usize).any(|j| {
                    let e = &board.units[j];
                    e.is_enemy() && e.hp > 0
                        && !e.frozen() && !e.web()
                        && !board.tile(e.x, e.y).smoke()
                        && ((u.x as i32 - e.x as i32).abs()
                          + (u.y as i32 - e.y as i32).abs()) <= 3
                });
                if dominated {
                    score += scaled(weights.mech_low_hp_risk, ff, 0.0, 1.0);
                }
            }
        }
    }

    // ── Building coverage: reward mechs positioned near buildings ──────
    // Pro strategy: distribute mechs for comprehensive coverage.
    // For each building, check if any alive mech can reach it (within move+1).
    // Penalize uncovered buildings — no mech nearby means no defense.
    // Building coverage: at low grid, ensure coverage still fires even on final turn
    let coverage_ff = if grid_multiplier > 1.0 { ff.max(0.5) } else { ff };
    if coverage_ff > 0.01 {
        let mut mech_pos: [(u8, u8, u8); 4] = [(0, 0, 0); 4]; // (x, y, move_speed)
        let mut mc = 0usize;
        for i in 0..board.unit_count as usize {
            let u = &board.units[i];
            if u.is_player() && u.is_mech() && u.alive() && mc < 4 {
                mech_pos[mc] = (u.x, u.y, u.move_speed);
                mc += 1;
            }
        }
        for idx in 0..64 {
            let tile = &board.tiles[idx];
            if tile.terrain != Terrain::Building || tile.building_hp == 0 { continue; }
            let (bx, by) = idx_to_xy(idx);
            let mut covered = false;
            for m in 0..mc {
                let (mx, my, ms) = mech_pos[m];
                let dist = (mx as i32 - bx as i32).abs() + (my as i32 - by as i32).abs();
                if dist <= (ms as i32 + 1) {
                    score += weights.building_coverage * coverage_ff;
                    covered = true;
                }
            }
            if !covered {
                // Scale by grid_multiplier: uncovered buildings are more dangerous at low grid
                score += weights.uncovered_building * coverage_ff * grid_multiplier;
            }
        }
    }

    // ── Spawns blocked: SCALED (zero on final turn — no next-turn spawns) ─
    for &(sx, sy) in spawn_points {
        if board.unit_at(sx, sy).is_some() {
            score += weights.spawn_blocked * ff;
        }
    }

    // ── Remaining spawn danger: flat penalty per queued Vek ─────────────
    // `apply_spawn_blocking` charges damage to mechs sitting on spawn tiles,
    // but the evaluator never materializes the newly-spawned Vek or
    // simulates its turn+1 attack. This penalty captures that unmodeled
    // danger. Scaled by ff so it collapses to 0 on the final turn (nothing
    // to prepare for). Cap at 8 spawns so a bogus u32::MAX from an
    // un-bridged board doesn't blow up the score — real values are 0–4.
    if board.remaining_spawns > 0 && board.remaining_spawns != u32::MAX {
        let capped = board.remaining_spawns.min(8) as f64;
        score -= weights.remaining_spawn_penalty * capped * ff;
    }

    // ── Turn+1 threat preview ──────────────────────────────────────────
    // For each surviving, unhindered enemy, count it as a threat if any
    // building tile lies within its taxicab (move_speed + range_envelope)
    // on the post-turn-1 board. Collapses to 0 on final turn via `ff`.
    //
    // We use a generous range envelope of +4 tiles (covers adjacent-melee
    // through most artillery/ranged weapons on an 8×8 board) because the
    // goal is to TILT action selection toward clearing threat-adjacent
    // enemies, not to precisely simulate turn+2. Precise enemy AI would
    // require a much larger module and the 1-turn solver can't act on it
    // anyway — a tilt is what helps it pick "kill the Hornet next to the
    // Coal Plant" over "kill two far-side scouts" when scores are close.
    if weights.next_turn_threat_penalty > 0.0 && ff > 0.01 {
        let mut threatening_enemies = 0i32;
        for i in 0..board.unit_count as usize {
            let e = &board.units[i];
            if !e.is_enemy() || !e.alive() { continue; }
            if e.frozen() || e.web() { continue; }
            if board.tile(e.x, e.y).smoke() { continue; }
            let reach = e.move_speed as i32 + 4;
            let mut can_reach_building = false;
            for idx in 0..64 {
                let tile = &board.tiles[idx];
                if tile.terrain != Terrain::Building || tile.building_hp == 0 { continue; }
                let (bx, by) = idx_to_xy(idx);
                let dist = (e.x as i32 - bx as i32).abs() + (e.y as i32 - by as i32).abs();
                if dist <= reach {
                    can_reach_building = true;
                    break;
                }
            }
            if can_reach_building {
                threatening_enemies += 1;
            }
        }
        if threatening_enemies > 0 {
            score -= weights.next_turn_threat_penalty * threatening_enemies as f64 * ff * grid_multiplier;
        }
    }

    // ── Option C: Queueless threat (projected boards only) ────────────────
    // Alive enemies that have NO queued target (queued_target_x < 0) but can
    // still reach a building within `move_speed + 4` Manhattan are penalised
    // at 1.5× next_turn_threat_penalty. This compensates for the fact that
    // `project_plan` (Option C) clears all enemy queued targets: without this
    // extra signal the evaluator would see no threats and prefer "kill
    // everything to exhaustion" over "protect buildings" — the same failure
    // mode Option A exhibits.
    //
    // Gated behind `pseudo_threat_eval` (default false) so it fires ONLY when
    // the caller explicitly sets it — i.e., on projected boards from
    // `project_plan`. Normal 1-turn evaluation is unchanged, so no
    // SIMULATOR_VERSION bump is needed.
    //
    // Filters: same as the existing `next_turn_threat_penalty` block — skip
    // Frozen, Webbed, and enemies on Smoke.
    if weights.pseudo_threat_eval && weights.next_turn_threat_penalty > 0.0 && ff > 0.01 {
        let mut queueless_threatening = 0i32;
        for i in 0..board.unit_count as usize {
            let e = &board.units[i];
            if !e.is_enemy() || !e.alive() { continue; }
            if e.queued_target_x >= 0 { continue; } // already has a target — don't double-count
            if e.frozen() || e.web() { continue; }
            if board.tile(e.x, e.y).smoke() { continue; }
            let reach = e.move_speed as i32 + 4;
            let mut can_reach_building = false;
            for idx in 0..64 {
                let tile = &board.tiles[idx];
                if tile.terrain != Terrain::Building || tile.building_hp == 0 { continue; }
                let (bx, by) = idx_to_xy(idx);
                let dist = (e.x as i32 - bx as i32).abs() + (e.y as i32 - by as i32).abs();
                if dist <= reach {
                    can_reach_building = true;
                    break;
                }
            }
            if can_reach_building {
                queueless_threatening += 1;
            }
        }
        if queueless_threatening > 0 {
            // 1.5× penalty: queueless enemies are harder to defend against
            // (no specific tile to body-block) so their threat is slightly
            // amplified vs. the standard queued-target case.
            score -= 1.5 * weights.next_turn_threat_penalty
                * queueless_threatening as f64
                * ff
                * grid_multiplier;
        }
    }

    // ── Pods: NO turn scaling ──────────────────────────────────────────
    for idx in 0..64 {
        let tile = &board.tiles[idx];
        if tile.has_pod() {
            score += weights.pod_uncollected;
            let (px, py) = idx_to_xy(idx);
            for i in 0..board.unit_count as usize {
                let u = &board.units[i];
                if u.is_player() && u.is_mech() && u.alive() {
                    let dist = (u.x as i32 - px as i32).abs() + (u.y as i32 - py as i32).abs();
                    if dist <= 2 {
                        score += weights.pod_proximity;
                    }
                }
            }
        }
    }

    if game_over {
        score -= 500000.0;
    }

    score
}

#[cfg(test)]
mod tests {
    use super::*;

    fn no_psion() -> PsionState { PsionState::default() }

    #[test]
    fn test_empty_board_score() {
        let board = Board::default();
        let w = EvalWeights::default();
        let score = evaluate(&board, &[], &w, 0, 0, &no_psion(), 0);
        assert!((score - 35000.0).abs() < 0.01);
    }

    #[test]
    fn test_building_score() {
        let mut board = Board::default();
        board.tile_mut(3, 3).terrain = Terrain::Building;
        board.tile_mut(3, 3).building_hp = 1;
        let w = EvalWeights::default();
        let score = evaluate(&board, &[], &w, 0, 0, &no_psion(), 0);
        // 35000 grid + 10000 building + 2000 hp - 500 uncovered_building = 46500
        assert!((score - 46500.0).abs() < 0.01);
    }

    #[test]
    fn test_kill_scales_with_turn() {
        let w = EvalWeights::default();
        let p = no_psion();
        let mut b1 = Board::default();
        b1.current_turn = 1;
        b1.total_turns = 5;
        let s0 = evaluate(&b1, &[], &w, 0, 0, &p, 0);
        let s1 = evaluate(&b1, &[], &w, 2, 0, &p, 0);
        assert!((s1 - s0 - 1800.0).abs() < 1.0);

        let mut b5 = Board::default();
        b5.current_turn = 5;
        b5.total_turns = 5;
        let s0 = evaluate(&b5, &[], &w, 0, 0, &p, 0);
        let s1 = evaluate(&b5, &[], &w, 2, 0, &p, 0);
        assert!((s1 - s0 - 200.0).abs() < 1.0);
    }

    #[test]
    fn test_grid_urgency_multiplier() {
        let mut board = Board::default();
        board.grid_power = 1;
        board.tile_mut(0, 0).terrain = Terrain::Building;
        board.tile_mut(0, 0).building_hp = 1;
        let w = EvalWeights::default();
        let score = evaluate(&board, &[], &w, 0, 0, &no_psion(), 0);
        // grid_power=1 * 5000 * 5.0(critical) + 1 building(10000*bld_mult) + 1 HP(2000*bld_mult) - 2500 uncovered(500*5.0)
        // bld_mult = 0.6 + 0.4*(1/7) = 0.6571... → building: 6571 + 1314 = 7886, total: 25000 + 7886 - 2500 = 30386
        assert!((score - 30386.0).abs() < 1.0);
    }

    #[test]
    fn test_spawn_blocked_zero_on_final_turn() {
        let w = EvalWeights::default();
        let mut board = Board::default();
        board.current_turn = 5;
        board.total_turns = 5;
        board.add_unit(Unit {
            uid: 0, x: 3, y: 3, hp: 3, max_hp: 3,
            team: Team::Player, move_speed: 3,
            flags: UnitFlags::IS_MECH | UnitFlags::PUSHABLE | UnitFlags::ACTIVE,
            ..Unit::default()
        });
        let with_spawn = evaluate(&board, &[(3, 3)], &w, 0, 0, &no_psion(), 0);
        let without_spawn = evaluate(&board, &[], &w, 0, 0, &no_psion(), 0);
        assert!((with_spawn - without_spawn).abs() < 1.0);
    }

    #[test]
    fn test_future_factor() {
        let inf = u32::MAX;
        assert!((future_factor(0, 5, inf) - 1.0).abs() < 0.01);
        assert!((future_factor(1, 5, inf) - 1.0).abs() < 0.01);
        assert!((future_factor(3, 5, inf) - 0.5).abs() < 0.01);
        assert!((future_factor(5, 5, inf) - 0.0).abs() < 0.01);
        // No more spawns → treat as final turn regardless of total_turns
        assert!((future_factor(1, 5, 0) - 0.0).abs() < 0.01);
        assert!((future_factor(4, 5, 0) - 0.0).abs() < 0.01);
    }

    #[test]
    fn test_psion_kill_bonus() {
        let w = EvalWeights::default();
        let mut board = Board::default();
        board.current_turn = 1;
        board.total_turns = 5;
        // Blast Psion was active before, now dead
        let p_blast = PsionState { blast: true, ..Default::default() };
        let with_bonus = evaluate(&board, &[], &w, 0, 0, &p_blast, 0);
        let without_bonus = evaluate(&board, &[], &w, 0, 0, &no_psion(), 0);
        assert!((with_bonus - without_bonus - 2000.0).abs() < 1.0);
    }

    #[test]
    fn test_remaining_spawn_penalty_matches_per_spawn_magnitude() {
        // Matches tests/test_solver_spawn_penalty.py. On turn 1 of 5 (ff=1.0),
        // remaining_spawns=2 should score ~2 * remaining_spawn_penalty less
        // than remaining_spawns=0.
        let w = EvalWeights::default();
        let p = no_psion();
        let mut b = Board::default();
        b.current_turn = 1;
        b.total_turns = 5;
        b.remaining_spawns = 0;
        let s0 = evaluate(&b, &[], &w, 0, 0, &p, 0);
        b.remaining_spawns = 2;
        let s2 = evaluate(&b, &[], &w, 0, 0, &p, 0);
        let expected = 2.0 * w.remaining_spawn_penalty;
        assert!((s0 - s2 - expected).abs() < 1.0,
            "expected s0-s2 ~= {}, got {} (s0={}, s2={})",
            expected, s0 - s2, s0, s2);
    }

    #[test]
    fn test_remaining_spawn_penalty_zero_on_final_turn() {
        // ff=0 on final turn collapses the penalty regardless of spawn count.
        let w = EvalWeights::default();
        let p = no_psion();
        let mut b = Board::default();
        b.current_turn = 5;
        b.total_turns = 5;
        b.remaining_spawns = 0;
        let s0 = evaluate(&b, &[], &w, 0, 0, &p, 0);
        b.remaining_spawns = 3;
        let s3 = evaluate(&b, &[], &w, 0, 0, &p, 0);
        assert!((s0 - s3).abs() < 1.0,
            "final turn should zero the penalty, got delta={}", s0 - s3);
    }

    #[test]
    fn test_remaining_spawn_penalty_sentinel_skipped() {
        // u32::MAX means "unknown / un-bridged" — must NOT apply penalty.
        let w = EvalWeights::default();
        let p = no_psion();
        let mut b = Board::default();
        b.current_turn = 1;
        b.total_turns = 5;
        b.remaining_spawns = u32::MAX;
        let s_sent = evaluate(&b, &[], &w, 0, 0, &p, 0);
        b.remaining_spawns = 0;
        let s_zero = evaluate(&b, &[], &w, 0, 0, &p, 0);
        assert!((s_sent - s_zero).abs() < 1.0,
            "sentinel should match zero-spawn score, got delta={}", s_sent - s_zero);
    }

    #[test]
    fn test_tyrant_psion_kill_bonus() {
        let w = EvalWeights::default();
        let mut board = Board::default();
        board.current_turn = 1;
        board.total_turns = 5;
        let p_tyrant = PsionState { tyrant: true, ..Default::default() };
        let with = evaluate(&board, &[], &w, 0, 0, &p_tyrant, 0);
        let without = evaluate(&board, &[], &w, 0, 0, &no_psion(), 0);
        assert!((with - without - 2500.0).abs() < 1.0);
    }
}
