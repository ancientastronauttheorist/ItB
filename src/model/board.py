"""Lightweight board representation for the solver.

Optimized for fast copy and mutation during search.
Converts from the save_parser's MissionState into a flat, solver-friendly format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
from src.capture.save_parser import MissionState, Point
from src.model.pawn_stats import get_pawn_stats, get_effective_move_speed


# Terrain flags
TERRAIN_PASSABLE = {"ground", "forest", "sand", "ice", "fire", "rubble", "acid"}
TERRAIN_BLOCKS_GROUND = {"water", "chasm", "lava", "mountain"}
TERRAIN_BLOCKS_ALL = {"mountain"}  # blocks flying too (for projectiles)
TERRAIN_DEADLY_GROUND = {"water", "chasm", "lava"}


BRIDGE_TERRAIN_ID_MAP = {
    # Engine/map-file terrain constants. The Lua bridge also sends a terrain
    # string, but older bridge builds mislabeled id 5 as lava; id 5 is ice.
    0: "ground",
    1: "building",
    2: "rubble",
    3: "water",
    4: "mountain",
    5: "ice",
    6: "forest",
    7: "sand",
    9: "chasm",
    10: "acid",
}


# Pilot value lookup: multiplier on the mech_killed penalty reflecting
# how costly it is to lose this pilot permanently. Values are "extra
# penalty fraction of base mech_killed" — 0.5 means +50% penalty on top
# of the base mech_killed. Pilot IDs match the save-file format (read
# from saveData.lua via the bridge).
#
# - Pilot_Mech: default AI pilot (no ability, no XP). Easily replaced → 0.
# - Pilot_Original (Ralph Karlsson): "Reliable" ability (never stunned).
#   Available by default, but levels up like any pilot — add XP-earned
#   skills via level bonus below.
# - Other named pilots: default placeholder until we tune per-pilot.
#
# Level adds ~0.15 per pilot level (cumulative XP → unlocked skill slots
# → more valuable to keep alive). Max 2 skill slots in vanilla ITB so
# level usually caps at 2.
_PILOT_VALUE_TABLE = {
    "Pilot_Mech": 0.0,
    "Pilot_Original": 0.3,   # Ralph Karlsson — default corporate pilot
    "Pilot_Detritus": 0.3,   # Charlie Ferry
    "Pilot_Pinnacle": 0.3,   # Zera
    "Pilot_Rst": 0.3,        # Camila Vera
    "Pilot_Archive": 0.3,
    "Pilot_Leader": 0.4,     # FTL-found pilot
    "Pilot_Ralph": 0.3,      # fallback if game uses alt ID
}
_PILOT_VALUE_DEFAULT = 0.3  # unknown named pilot — assume some value
_PILOT_VALUE_PER_LEVEL = 0.15  # each pilot level adds this much


def _mech_base_hp(mech_type: str) -> int:
    """Base HP a mech type ships with (pre-pilot, pre-upgrade). Values
    match data/squads.json for common mechs; returns 0 for unknown so the
    HP-boost heuristic silently no-ops rather than triggering a false
    positive."""
    return {
        "JudoMech": 3, "DStrikeMech": 2, "GravMech": 3,
        "PunchMech": 3, "TankMech": 2, "ArtiMech": 2,
        "ChargeMech": 3, "IceMech": 2, "LeapMech": 2, "PierceMech": 2,
        "BeamMech": 2, "FireMech": 3, "MineMech": 3,
        "JetMech": 2, "RocketMech": 2, "PulseMech": 2, "GuardMech": 3,
        "LaserMech": 2, "ScienceMech": 2, "CannonMech": 3, "BoulderMech": 3,
        "SwapMech": 2, "WallMech": 2, "DamMech": 3, "ElectricMech": 2,
        "NanoMech": 2,
    }.get(mech_type, 0)


def _compute_pilot_value(pilot_id: str, pilot_skills, current_max_hp: int,
                         mech_type: str, pilot_level: int = 0) -> float:
    """Return a multiplier on the mech_killed penalty for this unit.

    Combines:
      1. Pilot lookup table (per-pilot baseline by identity).
      2. Pilot level — each XP-unlocked skill slot adds value (permanent
         loss if the pilot dies).
      3. HP-boost heuristic — current max_hp over mech base signals at
         least one +HP skill in play (squad-wide or pilot-earned) and
         makes the mech more survivable (more costly to lose).
    """
    if not pilot_id:
        return 0.0
    base = _PILOT_VALUE_TABLE.get(pilot_id, _PILOT_VALUE_DEFAULT)
    level_bonus = max(0, int(pilot_level)) * _PILOT_VALUE_PER_LEVEL
    hp_bonus = 0.0
    mech_base = _mech_base_hp(mech_type)
    if mech_base > 0 and current_max_hp > mech_base:
        hp_bonus = 0.25 * (current_max_hp - mech_base)
    return base + level_bonus + hp_bonus


@dataclass
class Unit:
    """A unit on the board (solver-friendly)."""
    uid: int
    type: str
    x: int
    y: int
    hp: int
    max_hp: int
    team: int          # 1=player, 2=neutral, 6=enemy
    is_mech: bool
    move_speed: int
    flying: bool
    massive: bool
    armor: bool
    pushable: bool
    weapon: str
    weapon2: str = ""
    active: bool = True  # can still act this turn
    # Base movement speed (used to restore move_speed when web breaks).
    # Defaults to move_speed if bridge omits base_move.
    base_move: int = 0
    # Status effects (populated by bridge; inferred by save parser)
    shield: bool = False
    acid: bool = False
    frozen: bool = False
    fire: bool = False
    web: bool = False
    # UID of the enemy currently webbing this unit. -1 = no web / unknown.
    # When that enemy is pushed or killed, web breaks and move_speed restores.
    web_source_uid: int = -1
    # Enemy intent
    target_x: int = -1
    target_y: int = -1
    # Enemy attack details (from bridge piQueuedShot + weapon globals)
    queued_target_x: int = -1  # piQueuedShot direction point
    queued_target_y: int = -1
    weapon_damage: int = 0
    weapon_target_behind: bool = False
    weapon_push: int = 0
    # True when Lua bridge reports GetSelectedWeapon() > 0 for this Vek.
    # Combined with queued_target_x < 0 it marks the phantom-attack state
    # that the enemy-phase simulator treats with a conservative fallback
    # instead of silently skipping. Default False for legacy callers.
    has_queued_attack: bool = False
    # Multi-tile pawn duplicate (bridge emits one entry per ExtraSpace tile
    # for Dam_Pawn). All entries share `uid`; damage to any entry mirrors
    # HP to the rest via apply_damage.
    is_extra_tile: bool = False
    # Pilot info (mechs only). `pilot_id` from bridge (e.g. "Pilot_Rocks")
    # drives the pilot_value lookup: a multiplier on the mech_killed penalty
    # reflecting how costly it is to lose this pilot (permanent death + lost
    # skills). Default 0.0 = no bonus (treat as AI/default pilot).
    pilot_id: str = ""
    pilot_value: float = 0.0

    @property
    def is_player(self) -> bool:
        return self.team == 1

    @property
    def is_enemy(self) -> bool:
        return self.team == 6


@dataclass
class BoardTile:
    """A single tile on the board."""
    terrain: str = "ground"
    building_hp: int = 0     # 0 = not a building
    population: int = 0
    on_fire: bool = False
    has_pod: bool = False
    smoke: bool = False
    acid: bool = False
    frozen: bool = False
    cracked: bool = False    # ice tile that's been hit once (next hit → water)
    conveyor: int = -1       # -1 = not conveyor, 0=right(+x), 1=down(+y), 2=left(-x), 3=up(-y)
    freeze_mine: bool = False  # freeze mine on this tile (freezes unit that stops here)
    old_earth_mine: bool = False  # old earth mine — kills any unit that stops here (bypasses shield)
    unique_building: bool = False  # objective building (Coal Plant / Batteries / Generator)
    # Specific objective tag when unique_building=True (e.g. "Str_Power",
    # "Str_Battery", "Mission_Solar" for ⚡ grid-reward; "Str_Clinic",
    # "Str_Nimbus", "Str_Tower" for ⭐ rep-only). Empty when not an objective
    # or when the bridge didn't resolve the tag.
    objective_name: str = ""


class Board:
    """8x8 game board for solver search."""

    def __init__(self):
        self.tiles: list[list[BoardTile]] = [
            [BoardTile() for _ in range(8)] for _ in range(8)
        ]
        self.units: list[Unit] = []
        self.grid_power: int = 0
        self.grid_power_max: int = 7
        # Grid Defense: % chance a building resists damage. Not exposed by
        # Lua API (C++-only), so we default to 15 (game baseline) and let
        # callers override if tuning suggests a different value.
        self.grid_defense_pct: int = 15
        # Expected grid power saved during enemy phase via Grid Defense,
        # accumulated as float (buildings_destroyed * grid_defense_pct/100).
        # Read by evaluator to offset pessimistic post-enemy grid count.
        self.enemy_grid_save_expected: float = 0.0
        # Mirror of enemy_grid_save_expected for player-phase friendly-fire
        # building damage (sim v32+). The Rust simulator accumulates this in
        # `simulate_action`; the Python evaluator (audit-only score_breakdown
        # path) surfaces it in `eff_grid` for parity. Pure-Python search is
        # gone — this field exists for breakdown reporting and unit tests.
        self.player_grid_save_expected: float = 0.0
        self.environment_danger: set[tuple[int, int]] = set()
        self.environment_danger_v2: dict[tuple[int, int], tuple[int, bool]] = {}
        # Maps (x,y) -> (damage, is_lethal)
        # Ice Storm freeze tiles (Env_SnowStorm Acid=false). At start of enemy
        # turn, units on these tiles get Frozen=true. Buildings/mountains are
        # unaffected — frozen is a unit status. Separate from environment_danger
        # so the evaluator can score "lose a turn" instead of "die".
        self.environment_freeze: set[tuple[int, int]] = set()
        self.env_type: str = "unknown"
        self.blast_psion_active: bool = False
        self.armor_psion_active: bool = False
        self.soldier_psion_active: bool = False
        # Sim v37: Psion Abomination + AE Psion auras. Tracked here for bridge
        # parity / breakdown reporting only — the authoritative simulation
        # lives in the Rust solver (rust_solver/src/{board,enemy,simulate,
        # evaluate}.rs). Python `simulate.py` is a partial mirror used by tests
        # and doesn't currently exercise these auras.
        self.boss_psion_active: bool = False    # Jelly_Boss (LEADER_BOSS): HEALTH+REGEN+EXPLODE
        self.boost_psion_active: bool = False   # Jelly_Boost1 (AE LEADER_BOOSTED)
        self.fire_psion_active: bool = False    # Jelly_Fire1 (AE LEADER_FIRE)
        self.spider_psion_active: bool = False  # Jelly_Spider1 (AE LEADER_SPIDER)
        # Passive_ForceAmp: any mech carrying this passive causes all Vek to
        # take +1 damage from bump-class sources (push collisions + spawn
        # blocking). Sentient enemies (Bot Leader) are exempt per the wiki.
        self.force_amp: bool = False
        # Passive_Medical ("Medical Supplies"): all pilots survive mech death.
        # The mech itself is still destroyed (grid/HP consequences unchanged);
        # only the permanent pilot-loss component of the mech-death penalty
        # is zeroed. Squad-wide — any mech carrying it covers all pilots.
        self.medical_supplies: bool = False
        # Mission metadata (from bridge mission.ID, e.g. "Mission_Dam").
        self.mission_id: str = ""
        # "Kill N enemies" bonus objective (BONUS_KILL_FIVE). 0 when the
        # mission doesn't have this bonus. Target is difficulty-scaled by
        # the game (5 on Easy, 7 on Normal/Hard). Used by the evaluator to
        # fire a step-function bonus when cumulative kills cross the target.
        self.mission_kill_target: int = 0
        # Cumulative enemy kills this mission (mission.KilledVek from Lua).
        # Combined with the simulated turn's kills to decide whether a plan
        # crosses the kill target threshold.
        self.mission_kills_done: int = 0
        # Unit-based mission objectives. Some bonus objectives are pawns
        # rather than objective building tiles (Mission_Hacking's Hacking
        # Facility and Cannon Bot are the live example).
        self.destroy_objective_unit_types: list[str] = []
        self.protect_objective_unit_types: list[str] = []
        # Old Earth Dam state — flipped to False exactly once when the last
        # Dam_Pawn tile dies; the transition triggers trigger_dam_flood.
        self.dam_alive: bool = False
        self.dam_primary: tuple[int, int] | None = None
        # Renfield Bomb state — Mission_Final_Cave win-condition NPC. True
        # while at least one BigBomb pawn has hp > 0. The alive→dead
        # transition pays `bigbomb_killed` in the evaluator (mission-failure
        # penalty layered on top of friendly_npc_killed). Always False on
        # missions without a bomb.
        self.bigbomb_alive: bool = False
        # Teleporter pad pairs (Mission_Teleporter overlay from
        # Board:AddTeleport in mission_teleport.lua). Each entry =
        # (x1, y1, x2, y2). Empty on non-teleporter missions. Rust is
        # the authoritative simulator for combat; this field mirrors the
        # Rust shape so test fixtures and `replay_solution` harness agree.
        self.teleporter_pairs: list[tuple[int, int, int, int]] = []
        # Sim v38: Spider Psion pending egg-spawn queue. Eggs queued by
        # `on_enemy_death` during the enemy phase are drained at the END
        # of the phase so they don't hatch in the same phase they spawn
        # (matches game's AddQueuedDamage hatch in weapons_enemy.lua:857).
        # Authoritative simulation lives in Rust; this field exists for
        # board-state round-tripping (to_dict / from_dict / copy parity).
        self.pending_spider_eggs: list[tuple[int, int]] = []

    def copy(self) -> Board:
        """Deep copy for search branching."""
        b = Board()
        b.tiles = [[deepcopy(self.tiles[x][y]) for y in range(8)] for x in range(8)]
        b.units = [deepcopy(u) for u in self.units]
        b.grid_power = self.grid_power
        b.grid_power_max = self.grid_power_max
        b.grid_defense_pct = self.grid_defense_pct
        b.enemy_grid_save_expected = self.enemy_grid_save_expected
        b.player_grid_save_expected = self.player_grid_save_expected
        b.environment_danger = set(self.environment_danger)
        b.environment_danger_v2 = dict(self.environment_danger_v2)
        b.environment_freeze = set(self.environment_freeze)
        b.env_type = self.env_type
        b.blast_psion_active = self.blast_psion_active
        b.armor_psion_active = self.armor_psion_active
        b.soldier_psion_active = self.soldier_psion_active
        b.boss_psion_active = self.boss_psion_active
        b.boost_psion_active = self.boost_psion_active
        b.fire_psion_active = self.fire_psion_active
        b.spider_psion_active = self.spider_psion_active
        b.force_amp = self.force_amp
        b.medical_supplies = self.medical_supplies
        b.mission_id = self.mission_id
        b.mission_kill_target = self.mission_kill_target
        b.mission_kills_done = self.mission_kills_done
        b.destroy_objective_unit_types = list(self.destroy_objective_unit_types)
        b.protect_objective_unit_types = list(self.protect_objective_unit_types)
        b.dam_alive = self.dam_alive
        b.dam_primary = self.dam_primary
        b.bigbomb_alive = self.bigbomb_alive
        b.teleporter_pairs = list(self.teleporter_pairs)
        b.pending_spider_eggs = list(self.pending_spider_eggs)
        return b

    def tile(self, x: int, y: int) -> BoardTile:
        return self.tiles[x][y]

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < 8 and 0 <= y < 8

    def unit_at(self, x: int, y: int) -> Unit | None:
        # Multi-tile pawns (Dam_Pawn ExtraSpaces): bridge emits one entry per
        # occupied tile with shared uid. This lookup returns the entry at the
        # specific (x,y), which is what push/damage sites want. HP is mirrored
        # across entries in apply_damage. New unconditional `for u in board.units`
        # loops that accumulate per-pawn state should add `not u.is_extra_tile`.
        for u in self.units:
            if u.x == x and u.y == y and u.hp > 0:
                return u
        return None

    def wreck_at(self, x: int, y: int) -> bool:
        """Check if a dead unit (wreck) occupies this tile.

        In ITB, destroyed mechs leave wrecks that block movement.
        """
        for u in self.units:
            if u.x == x and u.y == y and u.hp <= 0:
                return True
        return False

    def mechs(self) -> list[Unit]:
        return [u for u in self.units if u.is_player and u.hp > 0]

    def enemies(self) -> list[Unit]:
        return [u for u in self.units if u.is_enemy and u.hp > 0]

    def is_blocked(self, x: int, y: int, flying: bool = False) -> bool:
        """Check if a tile blocks movement."""
        if not self.in_bounds(x, y):
            return True
        t = self.tile(x, y)
        if t.terrain == "mountain":
            return True
        if not flying and t.terrain in TERRAIN_DEADLY_GROUND:
            return True
        if self.unit_at(x, y) is not None:
            return True
        if self.wreck_at(x, y):
            return True  # dead unit wrecks block movement
        if t.terrain == "building":
            # Regular buildings turn to rubble when destroyed (own terrain);
            # objective unique_buildings stay as terrain=building, hp=0 and
            # remain impassable (IsBlocked=true in-game). So any 'building'
            # terrain blocks movement regardless of HP.
            return True
        return False

    def is_passable(self, x: int, y: int, flying: bool = False) -> bool:
        return not self.is_blocked(x, y, flying)

    def get_threatened_buildings(self) -> list[tuple[int, int, Unit]]:
        """Return buildings that are targeted by enemy attacks."""
        threats = []
        for u in self.enemies():
            if u.target_x < 0:
                continue
            tx, ty = u.target_x, u.target_y
            # OOB guard: bridge can deliver off-board target_x/y after direction
            # normalization (M04 2026-04-28 — cx=7,ddx=+1 → x=8 → IndexError).
            if not self.in_bounds(tx, ty):
                continue
            t = self.tile(tx, ty)
            if t.terrain == "building" and t.building_hp > 0:
                threats.append((tx, ty, u))
        return threats

    @staticmethod
    def from_mission(mission: MissionState, grid_power: int = 0,
                     grid_power_max: int = 7) -> Board:
        """Convert a MissionState into a solver Board."""
        board = Board()
        board.grid_power = grid_power
        board.grid_power_max = grid_power_max

        # Set terrain
        for tile in mission.tiles:
            if 0 <= tile.x < 8 and 0 <= tile.y < 8:
                bt = board.tile(tile.x, tile.y)
                bt.terrain = tile.terrain
                bt.on_fire = tile.on_fire
                bt.has_pod = tile.has_pod
                if tile.terrain == "building":
                    bt.building_hp = tile.health_max
                    bt.population = tile.population

        # Add units
        for pawn in mission.pawns:
            if pawn.location.x < 0:
                continue
            stats = get_pawn_stats(pawn.type)
            move = get_effective_move_speed(pawn.type, pawn.move_power)

            u = Unit(
                uid=pawn.pawn_id,
                type=pawn.type,
                x=pawn.location.x,
                y=pawn.location.y,
                hp=pawn.health,
                max_hp=pawn.max_health,
                team=pawn.team_id,
                is_mech=pawn.is_mech,
                move_speed=move,
                base_move=stats.move_speed,
                flying=stats.flying,
                massive=stats.massive,
                armor=stats.armor,
                pushable=stats.pushable,
                weapon=pawn.primary_weapon,
                weapon2=pawn.secondary_weapon,
                active=pawn.active,
                target_x=pawn.queued_shot.x if pawn.queued_shot else -1,
                target_y=pawn.queued_shot.y if pawn.queued_shot else -1,
            )
            board.units.append(u)

        return board

    @staticmethod
    def from_bridge_data(data: dict) -> "Board":
        """Construct Board from Lua bridge JSON data.

        Richer than from_mission(): includes per-pawn status effects
        (flying, shield, acid, fire, frozen, web) and per-tile status
        (smoke, acid, frozen, cracked) directly from the game API.
        """
        board = Board()
        board.grid_power = data.get("grid_power", 0)
        board.grid_power_max = data.get("grid_power_max", 7)

        # Tiles
        for td in data.get("tiles", []):
            x, y = td["x"], td["y"]
            if 0 <= x < 8 and 0 <= y < 8:
                bt = board.tile(x, y)
                terrain_id = td.get("terrain_id")
                bt.terrain = BRIDGE_TERRAIN_ID_MAP.get(
                    terrain_id,
                    td.get("terrain", "ground"),
                )
                bt.on_fire = td.get("fire", False)
                bt.smoke = td.get("smoke", False)
                bt.acid = td.get("acid", False)
                bt.frozen = td.get("frozen", False)
                bt.cracked = td.get("cracked", False)
                bt.has_pod = td.get("pod", td.get("has_pod", False))
                bt.freeze_mine = td.get("freeze_mine", False)
                bt.old_earth_mine = td.get("old_earth_mine", False)
                if "conveyor" in td:
                    bt.conveyor = td["conveyor"]
                if bt.terrain == "building":
                    bt.unique_building = td.get("unique_building", False)
                    bt.objective_name = td.get("objective_name", "")
                    if "building_hp" in td:
                        bt.building_hp = td["building_hp"]
                    elif bt.unique_building:
                        bt.building_hp = 0
                    else:
                        bt.building_hp = 1
                    bt.population = td.get("population", 1)
                elif bt.terrain == "mountain":
                    # Mountains have 2 HP (bridge doesn't send mountain HP)
                    bt.building_hp = td.get("building_hp", 2)

        # Teleporter pad pairs (Mission_Teleporter). Bridge emits each
        # entry as [x1, y1, x2, y2]; normalize to tuples.
        for pair in data.get("teleporter_pairs", []) or []:
            if isinstance(pair, (list, tuple)) and len(pair) >= 4:
                board.teleporter_pairs.append(
                    (int(pair[0]), int(pair[1]), int(pair[2]), int(pair[3]))
                )

        # Environment danger: v2 format has per-tile lethality [x, y, damage, kill_int]
        board.env_type = data.get("env_type", "unknown")
        for dt in data.get("environment_danger_v2", []):
            if isinstance(dt, (list, tuple)) and len(dt) >= 4:
                board.environment_danger.add((dt[0], dt[1]))
                board.environment_danger_v2[(dt[0], dt[1])] = (dt[2], dt[3] != 0)
        # Backwards compat: v1 entries not in v2 default to lethal
        for dt in data.get("environment_danger", []):
            if isinstance(dt, (list, tuple)) and len(dt) >= 2:
                pos = (dt[0], dt[1])
                board.environment_danger.add(pos)
                if pos not in board.environment_danger_v2:
                    board.environment_danger_v2[pos] = (1, True)
        # Ice Storm freeze tiles (sim v25). Vanilla Env_SnowStorm bypasses
        # env_danger and lands here instead — applied as Frozen status by
        # the simulator at start of enemy turn.
        for ft in data.get("environment_freeze", []):
            if isinstance(ft, (list, tuple)) and len(ft) >= 2 and ft[0] < 8 and ft[1] < 8:
                board.environment_freeze.add((ft[0], ft[1]))

        # Units
        for ud in data.get("units", []):
            x, y = ud.get("x", -1), ud.get("y", -1)
            if x < 0:
                continue

            ptype = ud.get("type", "")
            stats = get_pawn_stats(ptype)

            # Weapons: bridge provides list, we need primary + secondary
            weapons = ud.get("weapons", [])
            primary = weapons[0] if len(weapons) > 0 else ""
            secondary = weapons[1] if len(weapons) > 1 else ""

            # Queued target (piQueuedShot direction point)
            qt = ud.get("queued_target")
            qt_x = qt[0] if qt else -1
            qt_y = qt[1] if qt else -1

            u = Unit(
                uid=ud.get("uid", 0),
                type=ptype,
                x=x, y=y,
                hp=ud.get("hp", 1),
                max_hp=ud.get("max_hp", ud.get("hp", 1)),
                team=ud.get("team", 6),
                is_mech=ud.get("mech", False),
                move_speed=ud.get("move", stats.move_speed),
                flying=ud.get("flying", stats.flying),
                massive=stats.massive,
                armor=ud.get("armor", stats.armor),
                pushable=stats.pushable,
                weapon=primary,
                weapon2=secondary,
                active=ud.get("active", True),
                base_move=ud.get("base_move", stats.move_speed),
                shield=ud.get("shield", False),
                acid=ud.get("acid", False),
                frozen=ud.get("frozen", False),
                fire=ud.get("fire", False),
                web=ud.get("web", False),
                web_source_uid=ud.get("web_source_uid", -1),
                target_x=qt_x,
                target_y=qt_y,
                queued_target_x=qt_x,
                queued_target_y=qt_y,
                weapon_damage=min(ud.get("weapon_damage", 0), 255),
                weapon_target_behind=ud.get("weapon_target_behind", False),
                weapon_push=ud.get("weapon_push", 0),
                has_queued_attack=bool(ud.get("has_queued_attack", False)),
                is_extra_tile=ud.get("is_extra_tile", False),
                pilot_id=ud.get("pilot_id", ""),
                pilot_value=_compute_pilot_value(
                    ud.get("pilot_id", ""), ud.get("pilot_skills", []),
                    ud.get("max_hp", 0), ud.get("type", ""),
                    ud.get("pilot_level", 0),
                ),
            )
            board.units.append(u)

        # Mission metadata — may be empty string if bridge couldn't resolve.
        board.mission_id = data.get("mission_id", "") or ""
        # Kill-N bonus objective fields. Both default 0, which makes the
        # evaluator's step-function check a no-op for missions without the
        # kill-N bonus. Emitted by the Lua bridge from mission.BonusObjs +
        # mission.KilledVek + mission:GetKillBonus(). Safe when the Lua side
        # hasn't been updated — int() wraps whatever the bridge sent.
        try:
            board.mission_kill_target = int(data.get("mission_kill_target", 0) or 0)
        except (TypeError, ValueError):
            board.mission_kill_target = 0
        try:
            board.mission_kills_done = int(data.get("mission_kills_done", 0) or 0)
        except (TypeError, ValueError):
            board.mission_kills_done = 0
        board.destroy_objective_unit_types = [
            s for s in data.get("destroy_objective_unit_types", []) or []
            if isinstance(s, str) and s
        ]
        board.protect_objective_unit_types = [
            s for s in data.get("protect_objective_unit_types", []) or []
            if isinstance(s, str) and s
        ]

        # Infer WEB status from Spider Egg adjacency.
        # Game rule (weapons_enemy.lua SpiderAtk1:GetSkillEffect):
        #     for dir = DIR_START, DIR_END do
        #         ret:AddGrapple(p2, p2 + DIR_VECTORS[dir], "hold")
        # i.e. a landed WebbEgg1 webs every unit in its 4 cardinal
        # adjacent tiles. Bridge's p:IsGrappled() unreliably misses this
        # (confirmed empirically: Cannon Mech shown as Webbed in-game
        # but bridge reports web=False). Infer it here so the solver
        # respects the movement restriction.
        for egg in board.units:
            if egg.type != "WebbEgg1" or egg.hp <= 0:
                continue
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nx, ny = egg.x + dx, egg.y + dy
                if not board.in_bounds(nx, ny):
                    continue
                neighbor = board.unit_at(nx, ny)
                if neighbor is None or neighbor.hp <= 0:
                    continue
                # Adjacent egg is the AUTHORITATIVE webber — override any
                # bridge-reported web_source_uid (Lua GetGrappler can return
                # the wrong enemy when a Scorpion is also nearby, which
                # lets the solver "break" the web by pushing the wrong
                # enemy and incorrectly conclude the mech can move).
                neighbor.web = True
                neighbor.web_source_uid = egg.uid

        # Detect Passive_ForceAmp / Passive_Medical on any friendly mech.
        # Mirrors the Rust serde_bridge detection. Bridge emits mech weapons
        # as a list of internal names in `unit.weapons`, so we re-scan here.
        # Both passives are squad-wide: any mech carrying them flips the flag.
        for ud in data.get("units", []):
            if ud.get("mech") or ud.get("is_mech"):
                weapons = ud.get("weapons", []) or []
                if "Passive_ForceAmp" in weapons:
                    board.force_amp = True
                if "Passive_Medical" in weapons:
                    board.medical_supplies = True

        # Detect Blast Psion: if alive on board, all Vek explode on death
        board.blast_psion_active = any(
            u.type == "Jelly_Explode1" and u.hp > 0 for u in board.units
        )

        # Detect Shell Psion: if alive on board, all Vek gain Armor
        board.armor_psion_active = any(
            u.type == "Jelly_Armor1" and u.hp > 0 for u in board.units
        )
        if board.armor_psion_active:
            # Hardened Carapace excludes the Psion itself — "all OTHER Vek
            # have incoming weapon damage reduced by 1."
            for u in board.units:
                if u.is_enemy and u.type != "Jelly_Armor1":
                    u.armor = True

        # Detect Old Earth Dam — record the primary tile (non-extra) for the
        # 14-tile flood offset. `dam_alive` flips when the last tile dies.
        for u in board.units:
            if u.type == "Dam_Pawn" and u.hp > 0 and not u.is_extra_tile:
                board.dam_alive = True
                board.dam_primary = (u.x, u.y)
                break

        # Detect Renfield Bomb (Mission_Final_Cave). BigBomb is a single-tile
        # friendly NPC (DefaultTeam=TEAM_PLAYER, Neutral=true) that the Vek
        # try to destroy; the win condition is keeping it alive until its
        # turn-limit detonation. Mirrors Rust serde_bridge.rs.
        for u in board.units:
            if u.type == "BigBomb" and u.hp > 0:
                board.bigbomb_alive = True
                break

        # Detect Soldier Psion: alive Jelly_Health1 buffs all Vek +1 HP
        board.soldier_psion_active = any(
            u.type == "Jelly_Health1" and u.hp > 0 for u in board.units
        )

        # Detect Psion Abomination (Jelly_Boss): combined HEALTH+REGEN+EXPLODE
        # aura. Includes the +1 HP buff that Soldier Psion provides — when
        # both are alive the buff applies ONCE (no double-stack).
        board.boss_psion_active = any(
            u.type == "Jelly_Boss" and u.hp > 0 for u in board.units
        )

        if board.soldier_psion_active or board.boss_psion_active:
            # Bridge sends hp already buffed but max_hp as base — adjust max_hp.
            # Exclude both psion sources from the buff (their HP is intrinsic).
            for u in board.units:
                if u.is_enemy and u.type not in ("Jelly_Health1", "Jelly_Boss"):
                    u.max_hp += 1

        # Detect AE Psions (sim v37). Flags tracked for parity / breakdown;
        # full simulation lives in Rust.
        board.boost_psion_active = any(
            u.type == "Jelly_Boost1" and u.hp > 0 for u in board.units
        )
        board.fire_psion_active = any(
            u.type == "Jelly_Fire1" and u.hp > 0 for u in board.units
        )
        board.spider_psion_active = any(
            u.type == "Jelly_Spider1" and u.hp > 0 for u in board.units
        )

        # Satellite rocket deadly threat: 4 adjacent tiles kill any unit on launch.
        # Detect by checking if adjacent tiles appear in targeted_tiles (= rocket is
        # queued to fire this turn). Board:IsEnvironmentDanger() misses these.
        targeted = set()
        for tt in data.get("targeted_tiles", []):
            if isinstance(tt, (list, tuple)) and len(tt) >= 2:
                targeted.add((tt[0], tt[1]))
        for u in board.units:
            if "Satellite" in u.type and u.hp > 0:
                adj = [(u.x-1, u.y), (u.x+1, u.y), (u.x, u.y-1), (u.x, u.y+1)]
                adj_on_board = [(x, y) for x, y in adj if 0 <= x < 8 and 0 <= y < 8]
                if any(t in targeted for t in adj_on_board):
                    for t in adj_on_board:
                        board.environment_danger.add(t)

        return board

    def print_board(self):
        """ASCII board with visual A1-H8 notation matching the game.

        Visual mapping: Row = 8 - bridge_x, Col = chr(72 - bridge_y).
        So the outer loop must iterate bridge_x (rows) and the inner loop
        iterates bridge_y (columns). Row 8 at top, Col H on left.
        """
        sym = {
            "ground": ".", "building": "B", "mountain": "M",
            "water": "~", "forest": "F", "sand": "S",
            "ice": "I", "lava": "L", "chasm": " ", "rubble": "R",
        }
        # x=0 → Row 8 (top), x=7 → Row 1 (bottom)
        for x in range(8):
            row = []
            # y=0 → Col H (left), y=7 → Col A (right)
            for y in range(8):
                u = self.unit_at(x, y)
                if u:
                    row.append("P" if u.is_player else ("E" if u.is_enemy else "N"))
                elif self.wreck_at(x, y):
                    row.append("X")  # dead unit wreck (blocks movement)
                else:
                    t = self.tile(x, y)
                    c = sym.get(t.terrain, "?")
                    if t.freeze_mine:
                        c = "!"
                    elif t.on_fire:
                        c = "*"
                    elif t.conveyor >= 0:
                        c = ["\u2192", "\u2193", "\u2190", "\u2191"][t.conveyor]  # →↓←↑
                    row.append(c)
            print(f"  {8 - x} {'  '.join(row)}")
        cols = [chr(72 - y) for y in range(8)]
        print(f"    {'  '.join(cols)}")
