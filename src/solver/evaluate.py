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

    # Status effect bonuses
    enemy_on_fire_bonus: float = 100  # enemy on fire (1 dmg/turn)
    mech_on_acid: float = -200        # mech on ACID pool (penalty)
    mech_low_hp_risk: float = -2000   # 1HP mech near active enemy (binary)
    friendly_npc_killed: float = -20000  # non-mech player unit killed (penalty)

    # Grid urgency multipliers (applied to building scores)
    grid_urgency_critical: float = 5.0  # grid_power <= 1
    grid_urgency_high: float = 3.0      # grid_power == 2
    grid_urgency_medium: float = 3.0    # grid_power == 3

    # Achievement-specific (all default 0 — no effect in normal play)
    enemy_on_fire: float = 0
    enemy_pushed_into_enemy: float = 0
    chain_damage: float = 0
    smoke_placed: float = 0
    tiles_frozen: float = 0

    # Mission-specific bonus objectives (default 0; set via active.json).
    # Old Earth Dam: +1 Rep + 14-tile flood. Turn-aware scaling in evaluate.
    dam_destroyed: float = 0

    # Building protection
    mech_self_frozen: float = -12000
    building_bump_damage: float = -8000
    bld_grid_floor: float = 0.6
    bld_grid_scale: float = 0.4
    bld_phase_floor: float = 1.0
    bld_phase_scale: float = 0.0
    building_preservation_threshold: float = 0.05

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

    # Game over: grid power depleted.
    # Graduated score: -500000 base + normal evaluation components.
    # Keeps all game-over states strictly below any non-game-over state
    # while letting the solver rank bad options (e.g. lose 1 vs 3 buildings).
    game_over = board.grid_power <= 0

    score = 0.0
    ff = _future_factor(current_turn, total_turns, remaining_spawns)

    # --- GRID POWER URGENCY (unchanged) ---
    grid_multiplier = 1.0
    if board.grid_power <= 1:
        grid_multiplier = 5.0
    elif board.grid_power <= 2:
        grid_multiplier = 3.0
    elif board.grid_power <= 3:
        grid_multiplier = 2.0

    # --- BUILDINGS: context-aware multiplier (bld_mult) ---
    grid_max = getattr(board, 'grid_power_max', 7) or 7
    grid_health = board.grid_power / max(grid_max, 1)
    mp = 0.0
    if total_turns > 1:
        mp = max(current_turn - 1, 0) / (total_turns - 1)
    grid_factor = w.bld_grid_floor + w.bld_grid_scale * grid_health
    phase_factor = w.bld_phase_floor + w.bld_phase_scale * (1.0 - mp)
    bld_mult = grid_factor * phase_factor

    buildings_alive = 0
    total_building_hp = 0
    for x in range(8):
        for y in range(8):
            t = board.tile(x, y)
            if t.terrain == "building" and t.building_hp > 0:
                buildings_alive += 1
                total_building_hp += t.building_hp

    score += buildings_alive * w.building_alive * bld_mult
    score += total_building_hp * w.building_hp * bld_mult

    # --- GRID POWER: urgency multiplier applied here ---
    # When grid is low, each grid point is worth more. Multiplier was
    # previously on buildings but caused inversion (fewer buildings at
    # critical scored higher than more buildings at normal).
    score += board.grid_power * w.grid_power * grid_multiplier

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

    # --- ENVIRONMENT DANGER: SCALED ---
    if hasattr(board, 'environment_danger') and board.environment_danger:
        v2 = getattr(board, 'environment_danger_v2', {})
        for e in board.enemies():
            if (e.x, e.y) in board.environment_danger and not e.flying:
                score += _scaled(w.enemy_on_danger, ff, 0.20, 1.60)
        for m in board.mechs():
            if m.hp > 0 and (m.x, m.y) in board.environment_danger and not m.flying:
                dmg, lethal = v2.get((m.x, m.y), (1, True))
                if lethal or m.hp <= dmg:
                    score += w.mech_killed
                else:
                    score += dmg * _scaled(w.mech_hp, ff, 0.20, 0.80) * -1

    # --- MECHS: SCALED ---
    mechs = board.mechs()
    for m in mechs:
        if m.hp <= 0:
            score += w.mech_killed
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

    # --- GRID POWER URGENCY ---
    grid_multiplier = 1.0
    if board.grid_power <= 1:
        grid_multiplier = 5.0
    elif board.grid_power <= 2:
        grid_multiplier = 3.0
    elif board.grid_power <= 3:
        grid_multiplier = 2.0

    # --- BUILDINGS (context-aware multiplier) ---
    grid_max = getattr(board, 'grid_power_max', 7) or 7
    grid_health = board.grid_power / max(grid_max, 1)
    mp = 0.0
    if total_turns > 1:
        mp = max(current_turn - 1, 0) / (total_turns - 1)
    grid_factor = w.bld_grid_floor + w.bld_grid_scale * grid_health
    phase_factor = w.bld_phase_floor + w.bld_phase_scale * (1.0 - mp)
    bld_mult = grid_factor * phase_factor

    buildings_alive = 0
    total_building_hp = 0
    for x in range(8):
        for y in range(8):
            t = board.tile(x, y)
            if t.terrain == "building" and t.building_hp > 0:
                buildings_alive += 1
                total_building_hp += t.building_hp

    buildings_score = buildings_alive * w.building_alive * bld_mult
    building_hp_score = total_building_hp * w.building_hp * bld_mult

    # --- GRID POWER: urgency multiplier applied here ---
    grid_power_score = board.grid_power * w.grid_power * grid_multiplier

    # --- ENEMIES ---
    enemies_killed_score = kills * _scaled(w.enemy_killed, ff, 0.20, 1.60)

    enemy_hp_total = 0
    for e in board.enemies():
        enemy_hp_total += e.hp
    enemy_hp_score = enemy_hp_total * _scaled(w.enemy_hp_remaining, ff, 0.10, 0.90)

    # --- ENVIRONMENT DANGER ---
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
            if m.hp > 0 and (m.x, m.y) in board.environment_danger and not m.flying:
                danger_mechs_on += 1
                dmg, lethal = v2.get((m.x, m.y), (1, True))
                if lethal or m.hp <= dmg:
                    danger_score += w.mech_killed
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
            mech_score += w.mech_killed
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

    total = (buildings_score + building_hp_score + grid_power_score
             + enemies_killed_score + enemy_hp_score + danger_score
             + mech_score + spawns_score + pods_score)

    # Note: sanity check removed — evaluate() now requires turn params.
    # Use evaluate_breakdown only for debugging, not during search.

    return {
        "total": total,
        "grid_multiplier": grid_multiplier,
        "bld_mult": bld_mult,
        "buildings_alive": {"count": buildings_alive, "score": buildings_score},
        "building_hp": {"total": total_building_hp, "score": building_hp_score},
        "grid_power": {"value": board.grid_power, "score": grid_power_score},
        "enemies_killed": {"count": kills, "score": enemies_killed_score},
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
