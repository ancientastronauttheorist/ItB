"""Evaluate a board state for the solver.

Scores a board position considering buildings saved, enemies killed,
mech safety, and strategic positioning. Higher is better.

Supports configurable weights via EvalWeights dataclass for
achievement-specific strategy adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from src.model.board import Board


@dataclass
class EvalWeights:
    """Configurable evaluation weights.

    Default values are tuned for general play (protect buildings,
    kill enemies, keep mechs alive). Achievement strategies modify
    specific weights to incentivize achievement-specific behavior.

    Synced with Rust EvalWeights in rust_solver/src/evaluate.rs.
    """
    # Core weights
    building_alive: float = 10000
    building_hp: float = 2000
    grid_power: float = 5000
    enemy_killed: float = 500
    enemy_hp_remaining: float = -100
    enemy_threat_remaining: float = -100
    mech_killed: float = -150000
    mech_hp: float = 100
    mech_centrality: float = -5      # penalizes distance from center
    spawn_blocked: float = 1000
    pod_uncollected: float = -100
    pod_proximity: float = 50         # bonus for mech within 2 tiles of pod
    enemy_on_danger: float = 800      # non-flying enemy on danger tile

    # Psion kill bonuses (scaled by future_factor)
    psion_blast: float = 2000
    psion_shell: float = 1500
    psion_soldier: float = 4000
    psion_blood: float = 1600
    psion_tyrant: float = 2500
    psion_boss: float = 5000     # Jelly_Boss (LEADER_BOSS) — bigger than soldier (3-in-1 aura)
    psion_boost: float = 3000    # Jelly_Boost1 (AE LEADER_BOOSTED)
    psion_fire: float = 2200     # Jelly_Fire1 (AE LEADER_FIRE)
    psion_spider: float = 2200   # Jelly_Spider1 (AE LEADER_SPIDER)

    # Status effect bonuses
    enemy_on_fire_bonus: float = 100  # enemy on fire (1 dmg/turn)
    mech_on_acid: float = -200        # mech on ACID pool (penalty)
    mech_low_hp_risk: float = -2000   # 1HP mech near active enemy (binary)
    friendly_npc_killed: float = -20000  # non-mech player unit killed (penalty)
    volatile_enemy_killed: float = -10000  # protected Volatile Vek killed
    # Renfield Bomb destruction in Mission_Final_Cave — mission-failure
    # penalty layered on top of friendly_npc_killed. The bomb's detonation
    # is the win condition; losing it ends the run. Mirrors Rust default.
    bigbomb_killed: float = -200000

    # Grid urgency multipliers (applied to building scores)
    grid_urgency_critical: float = 5.0  # grid_power <= 1
    grid_urgency_high: float = 3.0      # grid_power == 2
    grid_urgency_medium: float = 3.0    # grid_power == 3

    # Capacity-loss convex penalty: -(grid_power_max - eff_grid)^2 * coef.
    # Penalizes the gap between current and full grid quadratically, so the
    # 1st grid lost from full hurts moderately and each subsequent grid hurts
    # disproportionately more. Layered ON TOP of the linear grid_power reward
    # and the below-threshold urgency penalty — fixes the "flat plateau" at
    # grid 4-7 where each grid was only worth grid_power=5000 (less than a
    # single ⚡ first-turn kill), letting the solver bleed buffer for any
    # tactical gain >5k. Mirrors rust_solver/src/evaluate.rs.
    grid_capacity_penalty: float = 800.0

    # Achievement-specific (all default 0 — no effect in normal play)
    enemy_on_fire: float = 0
    enemy_pushed_into_enemy: float = 0
    chain_damage: float = 0
    smoke_placed: float = 0
    tiles_frozen: float = 0

    # Mission-specific bonus objectives (default 0; set via active.json).
    # Old Earth Dam: +1 Rep + 14-tile flood. Turn-aware scaling in evaluate.
    dam_destroyed: float = 0

    # "Kill at least N enemies" bonus (BONUS_KILL_FIVE). Fires as a step
    # function exactly once — on the plan that crosses the cumulative
    # target. Solver will route kills to whichever turn reaches N fastest.
    mission_kill_bonus: float = 15000

    # Building protection
    mech_self_frozen: float = -12000
    building_bump_damage: float = -8000
    building_objective_bonus: float = 8000
    # Objective buildings whose survival grants ⚡ +1 Grid Power (Coal Plant,
    # Emergency Batteries, Solar Farms). Scored with bld_mult (same pattern
    # as all other building scoring — goes DOWN at low grid to avoid the
    # inversion bug where a safely-out-of-reach grid-reward building
    # incentivizes the solver to drop grid just to inflate its bonus).
    # Higher base weight than rep-only (≈3×) reflects the mission-end +1
    # grid power versus +1 rep. See _GRID_REWARD_OBJECTIVE_NAMES for the
    # allowlist.
    grid_reward_building_bonus: float = 25000
    boss_killed_bonus: float = 8000
    bld_grid_floor: float = 0.6
    bld_grid_scale: float = 0.4
    bld_phase_floor: float = 1.0
    bld_phase_scale: float = 0.0
    building_preservation_threshold: float = 0.05

    # Flat danger penalty per queued Vek spawn still to emerge.
    # Covers the "surprise" damage from the next-turn materialize+attack
    # that the sim does NOT project. Scaled by future_factor so it
    # collapses to 0 on the final turn. Mirrors rust_solver/src/evaluate.rs.
    remaining_spawn_penalty: float = 10000

    # Turn+1 threat preview penalty — per surviving enemy whose taxicab
    # (move+range) envelope reaches any building on the post-mech board.
    # Proxy for 2-turn lookahead; collapses to 0 on the final turn via
    # future_factor. Must mirror rust_solver/src/evaluate.rs:160.
    next_turn_threat_penalty: float = 2500

    # Option-C pseudo-threat augmentation flag — when True, evaluate() also
    # penalizes surviving enemies that can reach a building within
    # move_speed + 4 Manhattan distance on projected boards (where queued
    # targets have been cleared). Off by default; enabled only by
    # project_plan's board_to_json output. Mirrors rust_solver/src/evaluate.rs.
    pseudo_threat_eval: bool = False

    # Phase 1 soft-disable penalty — per action in a plan that uses a
    # weapon in the session's disabled_actions mask. Must mirror
    # rust_solver/src/evaluate.rs:170.
    soft_disabled_penalty: float = 10000

    # Coverage / defensive posture rewards (all mirror Rust defaults).
    # threats_cleared: reward per building threat neutralized this turn.
    threats_cleared: float = 4000
    # body_block_bonus: reward per mech absorbing a building threat.
    body_block_bonus: float = 0
    # building_coverage: bonus per building within mech reach.
    building_coverage: float = 50
    # uncovered_building: penalty per building not near any mech (negative).
    uncovered_building: float = -500
    # perfect_defense_bonus: bonus when ALL building threats cleared.
    perfect_defense_bonus: float = 6000
    # mech_sacrifice_at_critical: reduces mech_killed penalty at grid<=2.
    # Currently 0 — prior 50000 value created perverse sacrifice incentive.
    mech_sacrifice_at_critical: float = 0
    # dam_damage_dealt: Old Earth Dam weight (bonus objective).
    dam_damage_dealt: float = 0

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage and Rust solver injection."""
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EvalWeights":
        """Deserialize from dict, ignoring unknown keys."""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in d.items() if k in field_names}
        return cls(**filtered)

    def content_hash(self) -> str:
        """Stable hash of all weight values for fast equality checking."""
        import hashlib, json
        data = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:12]


DEFAULT_WEIGHTS = EvalWeights()


# Objective buildings whose bridge objective_name tag maps to ⚡ +1 Grid
# Power on survival. Anything not in this set falls back to the ⭐ rep-only
# path (scored by building_objective_bonus). Unknown / new tags are treated
# as rep-only for safety; add here after wiki/game confirmation.
_GRID_REWARD_OBJECTIVE_NAMES: set[str] = {
    "Str_Power",     # Coal Plant, Power Generator
    "Str_Battery",   # Emergency Batteries
    "Mission_Solar", # Solar Farms (Mission_Critical variant)
}


def _future_factor(current_turn: int, total_turns: int, remaining_spawns: int = 2**31 - 1) -> float:
    """Compute future_factor: 1.0 on first combat turn, 0.0 on final turn.

    current_turn is 0-indexed from bridge (0 = deployment, 1 = first combat).

    remaining_spawns collapses the factor to 0 when no more Vek will emerge
    after this turn's enemy phase — the "victory in 1 turn" case where bridge
    total_turns can exceed actual mission play length.
    """
    if remaining_spawns == 0:
        return 0.0
    if total_turns <= 1:
        return 0.0
    combat_turn = max(0, current_turn - 1)
    remaining = max(0, total_turns - combat_turn - 1)
    max_remaining = total_turns - 1
    return min(1.0, remaining / max_remaining)


def _scaled(base: float, ff: float, floor: float, scale: float) -> float:
    """Scale a weight: base * (floor + scale * future_factor)."""
    return base * (floor + scale * ff)


def evaluate(
    board: Board,
    spawn_points: list[tuple[int, int]] = None,
    weights: EvalWeights = None,
    kills: int = 0,
    blast_psion_was_active: bool = False,
    soldier_psion_was_active: bool = False,
    dam_was_alive: bool = False,
    bigbomb_was_alive: bool = False,
    current_turn: int = 0,
    total_turns: int = 5,
    remaining_spawns: int = 2**31 - 1,
) -> float:
    """Score a board state. Higher = better for the player.

    Turn-aware: weights for kills, damage, spawns, and mechs scale with
    future_factor (1.0 on first combat turn, 0.0 on final turn).
    Building and grid_power weights never scale (always critical).

    Args:
        board: The board state to evaluate.
        spawn_points: Next turn's Vek spawn locations.
        weights: Evaluation weights (uses DEFAULT_WEIGHTS if None).
        kills: Number of enemies killed during simulation.
        blast_psion_was_active: True if Blast Psion was alive before mech
            actions but is now dead (killed this turn).
        soldier_psion_was_active: True if Soldier Psion was alive before mech
            actions but is now dead (killed this turn).
        current_turn: 0-indexed turn number from bridge.
        total_turns: Mission length (typically 5).
        remaining_spawns: Queued Vek spawns still to emerge. 0 = no future
            reinforcements, treat as final turn regardless of total_turns.
    """
    w = weights or DEFAULT_WEIGHTS

    # Effective grid = deterministic grid_power + expected save from Grid
    # Defense (fraction of buildings hit that the 15%-ish resist-chance
    # blocks). Both phases contribute (sim v32+):
    #   • enemy_grid_save_expected: enemy-phase building hits
    #   • player_grid_save_expected: player-phase friendly-fire hits
    # Use this for urgency/game_over/scoring so the solver isn't pessimistic
    # about buildings the game will actually save.
    eff_grid = (
        board.grid_power
        + getattr(board, "enemy_grid_save_expected", 0.0)
        + getattr(board, "player_grid_save_expected", 0.0)
    )

    # Game over: expected grid power below half a point (≈ ≤0 actual).
    # Graduated score: -500000 base + normal evaluation components.
    # Keeps all game-over states strictly below any non-game-over state
    # while letting the solver rank bad options (e.g. lose 1 vs 3 buildings).
    game_over = eff_grid < 0.5

    score = 0.0
    ff = _future_factor(current_turn, total_turns, remaining_spawns)

    # --- GRID POWER URGENCY ---
    # Gate on the RAW grid_power so the 15% defense's expected-save (which
    # inflates eff_grid by ~0.15 per expected hit) can't push grid=3 above
    # the `<= 3` medium-urgency threshold. Weights come from EvalWeights
    # (not hardcoded) so active.json tuning takes effect.
    grid_multiplier = 1.0
    if board.grid_power <= 1:
        grid_multiplier = w.grid_urgency_critical
    elif board.grid_power <= 2:
        grid_multiplier = w.grid_urgency_high
    elif board.grid_power <= 3:
        grid_multiplier = w.grid_urgency_medium

    # --- BUILDINGS: context-aware multiplier (bld_mult) ---
    grid_max = getattr(board, 'grid_power_max', 7) or 7
    grid_health = eff_grid / max(grid_max, 1)
    mp = 0.0
    if total_turns > 1:
        mp = max(current_turn - 1, 0) / (total_turns - 1)
    grid_factor = w.bld_grid_floor + w.bld_grid_scale * grid_health
    phase_factor = w.bld_phase_floor + w.bld_phase_scale * (1.0 - mp)
    bld_mult = grid_factor * phase_factor

    buildings_alive = 0
    total_building_hp = 0
    objective_rep_buildings_alive = 0
    objective_grid_buildings_alive = 0
    for x in range(8):
        for y in range(8):
            t = board.tile(x, y)
            if t.terrain == "building" and t.building_hp > 0:
                buildings_alive += 1
                total_building_hp += t.building_hp
                if t.unique_building:
                    if t.objective_name in _GRID_REWARD_OBJECTIVE_NAMES:
                        objective_grid_buildings_alive += 1
                    else:
                        # Rep-only (Clinic/Nimbus/Tower) and unknown tags.
                        objective_rep_buildings_alive += 1

    score += buildings_alive * w.building_alive * bld_mult
    score += total_building_hp * w.building_hp * bld_mult
    # ⭐ rep-only objectives: flat bonus scaled by bld_mult (unchanged).
    score += objective_rep_buildings_alive * w.building_objective_bonus * bld_mult
    # ⚡ grid-reward objectives: higher base weight but SAME bld_mult pattern
    # as other buildings. Using grid_multiplier here would invert: at low
    # grid an untouchable grid-reward building would pay out more, and the
    # solver would drop grid to inflate its own bonus. bld_mult (goes DOWN
    # at low grid) prevents that.
    score += objective_grid_buildings_alive * w.grid_reward_building_bonus * bld_mult

    # --- GRID POWER: monotonic reward + below-threshold urgency penalty ---
    # Previous `eff_grid * weight * multiplier` was non-monotonic in grid_power
    # (grid=3 could score higher than grid=5). Mirrors Rust evaluate.rs fix:
    # linear base + penalty for sliding below the crisis_threshold.
    score += eff_grid * w.grid_power
    crisis_threshold = 4.0
    if eff_grid < crisis_threshold:
        gap = crisis_threshold - eff_grid
        score -= gap * w.grid_power * (grid_multiplier - 1.0)
    # Capacity-loss penalty: convex in (grid_power_max - eff_grid). Adds
    # early-warning sting to the previously-flat 4..=max plateau where each
    # grid was only worth `grid_power=5000` (less than a single ⚡ first-turn
    # kill), letting buffer bleed unchecked at high grid. Quadratic shape:
    # 1-grid bleed mild, 2-grid bleed bites, 3-grid bleed strongly defensive.
    # At full grid (gap=0) the term is 0; derivative is always positive so
    # monotonicity in grid_power is preserved.
    cap_gap = max(0.0, grid_max - eff_grid)
    score -= (cap_gap ** 2) * w.grid_capacity_penalty

    # --- ENEMIES: SCALED (kills worth more early, less on final turn) ---
    # kill_value = 500 * (0.20 + 1.60 * ff) → turn 1: 900, mid: 500, final: 100
    score += kills * _scaled(w.enemy_killed, ff, 0.20, 1.60)

    for e in board.enemies():
        # damage_value = -50 * (0.10 + 0.90 * ff) → final: -5
        score += e.hp * _scaled(w.enemy_hp_remaining, ff, 0.10, 0.90)

    # --- BLAST PSION KILL BONUS: SCALED by future_factor ---
    if blast_psion_was_active and not board.blast_psion_active:
        score += 2000.0 * ff

    # --- SOLDIER PSION KILL BONUS: SCALED by future_factor ---
    if soldier_psion_was_active and not getattr(board, 'soldier_psion_active', False):
        score += w.psion_soldier * ff

    # --- OLD EARTH DAM DESTROYED: turn-aware (floor=0.10 keeps +1 Rep
    # value on final turn; early turns get full flood-denial reward) ---
    if dam_was_alive and not getattr(board, 'dam_alive', False):
        score += _scaled(w.dam_destroyed, ff, 0.10, 0.90)

    # --- RENFIELD BOMB DESTROYED: mission-failure penalty ---
    # NOT scaled by future_factor — losing the bomb fails the run regardless
    # of which turn the loss happens. Mirrors rust_solver/src/evaluate.rs.
    if bigbomb_was_alive and not getattr(board, 'bigbomb_alive', False):
        score += w.bigbomb_killed

    # --- "KILL N ENEMIES" BONUS: step function on threshold cross ---
    # Fires exactly once per mission, on the plan whose simulated kills push
    # cumulative count to the target. Pre-turn < target AND post-turn ≥
    # target is the cross condition. Scaled by future_factor so the bonus
    # decays toward final turn (matches dam_destroyed pattern).
    kt = getattr(board, 'mission_kill_target', 0)
    if kt > 0:
        kd = getattr(board, 'mission_kills_done', 0)
        if kd < kt and kd + kills >= kt:
            score += _scaled(w.mission_kill_bonus, ff, 0.25, 0.75)

    # --- ENVIRONMENT DANGER: SCALED ---
    # Lethal env (kill_int=1: Air Strike, Lightning, Cataclysm→chasm, Seismic,
    # Tidal) bypasses flying — mirrors rust_solver/src/evaluate.rs and
    # rust_solver/src/enemy.rs::apply_env_danger. Non-lethal env (wind, sand,
    # snow) skips flying.
    if hasattr(board, 'environment_danger') and board.environment_danger:
        v2 = getattr(board, 'environment_danger_v2', {})
        for e in board.enemies():
            pos = (e.x, e.y)
            if pos not in board.environment_danger:
                continue
            dmg, lethal = v2.get(pos, (1, True))
            # Lethal env kills flying enemies too (already dead if sim ran),
            # but partial-credit scoring only makes sense for ground units
            # about to eat the telegraphed damage. Keep the flying skip for
            # enemies (flying-enemy kills handled by main death branch).
            if not e.flying:
                score += _scaled(w.enemy_on_danger, ff, 0.20, 1.60)
        for m in board.mechs():
            if m.hp <= 0:
                continue
            pos = (m.x, m.y)
            if pos not in board.environment_danger:
                continue
            dmg, lethal = v2.get(pos, (1, True))
            # Lethal env: always applies — flying or ground, shield/frozen
            # bypassed. The simulator should have already set hp=0, but guard
            # here so scoring still penalizes off-sequence branches.
            if lethal:
                if m.is_mech:
                    score += _scaled(w.mech_killed, ff, 0.05, 0.95)
                    if not board.medical_supplies:
                        score += w.mech_killed * m.pilot_value
                else:
                    score += w.friendly_npc_killed
                continue
            # Non-lethal env: skip flying (they don't take the hit).
            if m.flying:
                continue
            if m.hp <= dmg:
                if m.is_mech:
                    score += _scaled(w.mech_killed, ff, 0.05, 0.95)
                    if not board.medical_supplies:
                        score += w.mech_killed * m.pilot_value
                else:
                    score += w.friendly_npc_killed
            else:
                score += dmg * _scaled(w.mech_hp, ff, 0.20, 0.80) * -1

    # --- MECHS + FRIENDLY NPCs: SCALED ---
    # board.mechs() returns all player-team units (is_player) including
    # non-mech NPCs like Filler_Pawn and Train_Pawn. Mirrors Rust evaluate:
    # real mechs get the full mech_killed penalty + pilot_value, NPCs get
    # the smaller friendly_npc_killed penalty (no pilot_value).
    for m in board.mechs():
        if not m.is_mech:
            # Non-mech player unit (Filler_Pawn, ArchiveArtillery, etc.)
            if m.hp <= 0:
                score += w.friendly_npc_killed
            continue
        if m.hp <= 0:
            score += _scaled(w.mech_killed, ff, 0.05, 0.95)
            # Passive_Medical revives the pilot — no permanent-loss cost.
            # Mech itself is still destroyed (base mech_killed still applies).
            if not board.medical_supplies:
                score += w.mech_killed * m.pilot_value
        else:
            score += m.hp * _scaled(w.mech_hp, ff, 0.20, 0.80)
            cx = abs(m.x - 3.5)
            cy = abs(m.y - 3.5)
            score += (cx + cy) * w.mech_centrality * ff
            # Low-HP risk: penalize 1HP mech near active enemies
            if m.hp == 1:
                for e in board.enemies():
                    if e.hp <= 0 or e.frozen or e.web:
                        continue
                    t = board.tile(e.x, e.y)
                    if t.smoke:
                        continue
                    if abs(m.x - e.x) + abs(m.y - e.y) <= 3:
                        score += _scaled(w.mech_low_hp_risk, ff, 0.0, 1.0)
                        break  # binary: once per mech

    # --- SPAWNS BLOCKED: SCALED (zero on final turn) ---
    if spawn_points:
        for sx, sy in spawn_points:
            if board.unit_at(sx, sy) is not None:
                score += w.spawn_blocked * ff

    # --- REMAINING SPAWN DANGER: flat penalty per queued Vek ---
    # apply_spawn_blocking charges damage to mechs on spawn tiles, but the
    # evaluator never materializes the newly-spawned Vek or simulates its
    # turn+1 attack. This penalty captures the unmodeled danger. Scaled by
    # ff so it collapses to 0 on the final turn. Cap at 8 so a sentinel
    # default (2**31-1) doesn't blow up the score — real values are 0–4.
    _SPAWN_SENTINEL = 2**31 - 1
    if 0 < remaining_spawns < _SPAWN_SENTINEL:
        capped = min(remaining_spawns, 8)
        score -= w.remaining_spawn_penalty * capped * ff

    # --- PODS: NO turn scaling ---
    for x in range(8):
        for y in range(8):
            if board.tile(x, y).has_pod:
                score += w.pod_uncollected
                for m in mechs:
                    dist = abs(m.x - x) + abs(m.y - y)
                    if dist <= 2:
                        score += w.pod_proximity

    if game_over:
        score -= 500000.0

    return score


def evaluate_breakdown(
    board: Board,
    spawn_points: list[tuple[int, int]] = None,
    weights: EvalWeights = None,
    kills: int = 0,
    current_turn: int = 0,
    total_turns: int = 5,
    remaining_spawns: int = 2**31 - 1,
) -> dict:
    """Score a board state and return per-component breakdown.

    Same logic as evaluate(), but returns a dict with each scoring
    component separated. Uses _scaled() for turn-aware weights,
    matching evaluate(). Only call on the final solution (not during
    search) since it builds a dict instead of a bare float.
    """
    w = weights or DEFAULT_WEIGHTS
    ff = _future_factor(current_turn, total_turns, remaining_spawns)

    # Effective grid = deterministic + expected Grid Defense save (both
    # enemy-phase and player-phase friendly-fire saves; sim v32+).
    eff_grid = (
        board.grid_power
        + getattr(board, "enemy_grid_save_expected", 0.0)
        + getattr(board, "player_grid_save_expected", 0.0)
    )

    # --- GRID POWER URGENCY --- (raw grid, EvalWeights — see evaluate())
    grid_multiplier = 1.0
    if board.grid_power <= 1:
        grid_multiplier = w.grid_urgency_critical
    elif board.grid_power <= 2:
        grid_multiplier = w.grid_urgency_high
    elif board.grid_power <= 3:
        grid_multiplier = w.grid_urgency_medium

    # --- BUILDINGS (context-aware multiplier) ---
    grid_max = getattr(board, 'grid_power_max', 7) or 7
    grid_health = eff_grid / max(grid_max, 1)
    mp = 0.0
    if total_turns > 1:
        mp = max(current_turn - 1, 0) / (total_turns - 1)
    grid_factor = w.bld_grid_floor + w.bld_grid_scale * grid_health
    phase_factor = w.bld_phase_floor + w.bld_phase_scale * (1.0 - mp)
    bld_mult = grid_factor * phase_factor

    buildings_alive = 0
    total_building_hp = 0
    objective_rep_alive = 0
    objective_grid_alive = 0
    for x in range(8):
        for y in range(8):
            t = board.tile(x, y)
            if t.terrain == "building" and t.building_hp > 0:
                buildings_alive += 1
                total_building_hp += t.building_hp
                if t.unique_building:
                    if t.objective_name in _GRID_REWARD_OBJECTIVE_NAMES:
                        objective_grid_alive += 1
                    else:
                        objective_rep_alive += 1

    buildings_score = buildings_alive * w.building_alive * bld_mult
    building_hp_score = total_building_hp * w.building_hp * bld_mult
    objective_rep_score = objective_rep_alive * w.building_objective_bonus * bld_mult
    # See evaluate() for why bld_mult (not grid_multiplier) — avoids inversion.
    objective_grid_score = objective_grid_alive * w.grid_reward_building_bonus * bld_mult

    # --- GRID POWER: monotonic reward + below-threshold urgency penalty ---
    # See evaluate() for the formula + why.
    grid_power_score = eff_grid * w.grid_power
    crisis_threshold = 4.0
    if eff_grid < crisis_threshold:
        gap = crisis_threshold - eff_grid
        grid_power_score -= gap * w.grid_power * (grid_multiplier - 1.0)
    # Capacity-loss penalty mirrors evaluate(); see comment there.
    cap_gap = max(0.0, grid_max - eff_grid)
    grid_power_score -= (cap_gap ** 2) * w.grid_capacity_penalty

    # --- ENEMIES ---
    enemies_killed_score = kills * _scaled(w.enemy_killed, ff, 0.20, 1.60)

    enemy_hp_total = 0
    for e in board.enemies():
        enemy_hp_total += e.hp
    enemy_hp_score = enemy_hp_total * _scaled(w.enemy_hp_remaining, ff, 0.10, 0.90)

    # --- ENVIRONMENT DANGER ---
    # Lethal env (kill_int=1) bypasses flying — mirrors main evaluate() fix.
    danger_enemies_on = 0
    danger_mechs_on = 0
    danger_score = 0.0
    if hasattr(board, 'environment_danger') and board.environment_danger:
        v2 = getattr(board, 'environment_danger_v2', {})
        for e in board.enemies():
            if (e.x, e.y) in board.environment_danger and not e.flying:
                danger_enemies_on += 1
                danger_score += _scaled(w.enemy_on_danger, ff, 0.20, 1.60)
        for m in board.mechs():
            if m.hp <= 0:
                continue
            pos = (m.x, m.y)
            if pos not in board.environment_danger:
                continue
            dmg, lethal = v2.get(pos, (1, True))
            if lethal:
                # Lethal env hits flying too (air strike, lightning)
                danger_mechs_on += 1
                danger_score += _scaled(w.mech_killed, ff, 0.05, 0.95)
            elif not m.flying:
                danger_mechs_on += 1
                if m.hp <= dmg:
                    danger_score += _scaled(w.mech_killed, ff, 0.05, 0.95)
                else:
                    danger_score += dmg * _scaled(w.mech_hp, ff, 0.20, 0.80) * -1

    # --- MECHS ---
    mechs = board.mechs()
    mechs_alive = 0
    mechs_dead = 0
    total_mech_hp = 0
    mech_score = 0.0
    for m in mechs:
        if m.hp <= 0:
            mechs_dead += 1
            mech_score += _scaled(w.mech_killed, ff, 0.05, 0.95)
        else:
            mechs_alive += 1
            total_mech_hp += m.hp
            mech_score += m.hp * _scaled(w.mech_hp, ff, 0.20, 0.80)
            cx = abs(m.x - 3.5)
            cy = abs(m.y - 3.5)
            mech_score += (cx + cy) * w.mech_centrality * ff

    # --- SPAWNS BLOCKED ---
    spawns_blocked = 0
    if spawn_points:
        for sx, sy in spawn_points:
            if board.unit_at(sx, sy) is not None:
                spawns_blocked += 1
    spawns_score = spawns_blocked * w.spawn_blocked * ff

    # --- REMAINING SPAWN DANGER: flat penalty per queued Vek ---
    _SPAWN_SENTINEL = 2**31 - 1
    remaining_spawn_score = 0.0
    remaining_spawn_count = 0
    if 0 < remaining_spawns < _SPAWN_SENTINEL:
        remaining_spawn_count = min(remaining_spawns, 8)
        remaining_spawn_score = -w.remaining_spawn_penalty * remaining_spawn_count * ff

    # --- PODS ---
    pods_uncollected = 0
    pods_proximity = 0
    pods_score = 0.0
    for x in range(8):
        for y in range(8):
            if board.tile(x, y).has_pod:
                pods_uncollected += 1
                pods_score += w.pod_uncollected
                for m in mechs:
                    dist = abs(m.x - x) + abs(m.y - y)
                    if dist <= 2:
                        pods_proximity += 1
                        pods_score += w.pod_proximity

    # Kill-N bonus: step function on cumulative-kill cross. See evaluate().
    kill_n_score = 0.0
    kt = getattr(board, 'mission_kill_target', 0)
    kd = getattr(board, 'mission_kills_done', 0)
    if kt > 0 and kd < kt and kd + kills >= kt:
        kill_n_score = _scaled(w.mission_kill_bonus, ff, 0.25, 0.75)

    total = (buildings_score + building_hp_score
             + objective_rep_score + objective_grid_score
             + grid_power_score
             + enemies_killed_score + enemy_hp_score + danger_score
             + mech_score + spawns_score + remaining_spawn_score
             + pods_score + kill_n_score)

    # Note: sanity check removed — evaluate() now requires turn params.
    # Use evaluate_breakdown only for debugging, not during search.

    return {
        "total": total,
        "grid_multiplier": grid_multiplier,
        "bld_mult": bld_mult,
        "buildings_alive": {"count": buildings_alive, "score": buildings_score},
        "building_hp": {"total": total_building_hp, "score": building_hp_score},
        "objective_rep": {
            "count": objective_rep_alive,
            "score": objective_rep_score,
        },
        "objective_grid": {
            "count": objective_grid_alive,
            "score": objective_grid_score,
        },
        "grid_power": {
            "value": board.grid_power,
            "effective": eff_grid,
            "expected_save": getattr(board, "enemy_grid_save_expected", 0.0),
            "expected_save_player": getattr(board, "player_grid_save_expected", 0.0),
            "score": grid_power_score,
        },
        "enemies_killed": {"count": kills, "score": enemies_killed_score},
        "mission_kill_bonus": {
            "target": kt,
            "done_pre_turn": kd,
            "kills_this_turn": kills,
            "score": kill_n_score,
        },
        "enemy_hp_remaining": {"total": enemy_hp_total, "score": enemy_hp_score},
        "environment_danger": {
            "enemies_on": danger_enemies_on,
            "mechs_on": danger_mechs_on,
            "score": danger_score,
        },
        "mechs": {
            "alive": mechs_alive,
            "dead": mechs_dead,
            "total_hp": total_mech_hp,
            "score": mech_score,
        },
        "spawns_blocked": {"count": spawns_blocked, "score": spawns_score},
        "remaining_spawns": {"count": remaining_spawn_count, "score": remaining_spawn_score},
        "pods": {
            "uncollected": pods_uncollected,
            "proximity": pods_proximity,
            "score": pods_score,
        },
    }


def evaluate_threats(board: Board) -> dict:
    """Analyze what threats remain on the board.

    Returns a summary of threatened buildings and unresolved attacks.
    Note: damage values are approximate (TODO: look up actual weapon damage).
    """
    threats = board.get_threatened_buildings()
    enemy_attacks = []
    for u in board.enemies():
        if u.hp > 0 and u.target_x >= 0:
            enemy_attacks.append({
                "enemy": u.type,
                "at": (u.x, u.y),
                "target": (u.target_x, u.target_y),
                "damage": 1,  # TODO: look up actual weapon damage from pawn_stats
            })

    return {
        "threatened_buildings": len(threats),
        "enemy_attacks": len(enemy_attacks),
        "details": enemy_attacks,
    }
