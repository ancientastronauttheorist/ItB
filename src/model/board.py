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
TERRAIN_PASSABLE = {"ground", "forest", "sand", "ice", "fire", "rubble"}
TERRAIN_BLOCKS_GROUND = {"water", "chasm", "lava", "mountain"}
TERRAIN_BLOCKS_ALL = {"mountain"}  # blocks flying too (for projectiles)
TERRAIN_DEADLY_GROUND = {"water", "chasm", "lava"}


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
    # Status effects (populated by bridge; inferred by save parser)
    shield: bool = False
    acid: bool = False
    frozen: bool = False
    fire: bool = False
    web: bool = False
    # Enemy intent
    target_x: int = -1
    target_y: int = -1
    # Enemy attack details (from bridge piQueuedShot + weapon globals)
    queued_target_x: int = -1  # piQueuedShot direction point
    queued_target_y: int = -1
    weapon_damage: int = 0
    weapon_target_behind: bool = False
    weapon_push: int = 0

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


class Board:
    """8x8 game board for solver search."""

    def __init__(self):
        self.tiles: list[list[BoardTile]] = [
            [BoardTile() for _ in range(8)] for _ in range(8)
        ]
        self.units: list[Unit] = []
        self.grid_power: int = 0
        self.grid_power_max: int = 7
        self.environment_danger: set[tuple[int, int]] = set()
        self.environment_danger_v2: dict[tuple[int, int], tuple[int, bool]] = {}
        # Maps (x,y) -> (damage, is_lethal)
        self.env_type: str = "unknown"
        self.blast_psion_active: bool = False
        self.armor_psion_active: bool = False
        self.soldier_psion_active: bool = False

    def copy(self) -> Board:
        """Deep copy for search branching."""
        b = Board()
        b.tiles = [[deepcopy(self.tiles[x][y]) for y in range(8)] for x in range(8)]
        b.units = [deepcopy(u) for u in self.units]
        b.grid_power = self.grid_power
        b.grid_power_max = self.grid_power_max
        b.environment_danger = set(self.environment_danger)
        b.environment_danger_v2 = dict(self.environment_danger_v2)
        b.env_type = self.env_type
        b.blast_psion_active = self.blast_psion_active
        b.armor_psion_active = self.armor_psion_active
        b.soldier_psion_active = self.soldier_psion_active
        return b

    def tile(self, x: int, y: int) -> BoardTile:
        return self.tiles[x][y]

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < 8 and 0 <= y < 8

    def unit_at(self, x: int, y: int) -> Unit | None:
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
        if t.terrain == "building" and t.building_hp > 0:
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
                bt.terrain = td.get("terrain", "ground")
                bt.on_fire = td.get("fire", False)
                bt.smoke = td.get("smoke", False)
                bt.acid = td.get("acid", False)
                bt.frozen = td.get("frozen", False)
                bt.cracked = td.get("cracked", False)
                bt.has_pod = td.get("pod", False)
                bt.freeze_mine = td.get("freeze_mine", False)
                bt.old_earth_mine = td.get("old_earth_mine", False)
                if "conveyor" in td:
                    bt.conveyor = td["conveyor"]
                if bt.terrain == "building":
                    bt.building_hp = td.get("building_hp", 1)
                    bt.population = td.get("population", 1)
                elif bt.terrain == "mountain":
                    # Mountains have 2 HP (bridge doesn't send mountain HP)
                    bt.building_hp = td.get("building_hp", 2)

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
                shield=ud.get("shield", False),
                acid=ud.get("acid", False),
                frozen=ud.get("frozen", False),
                fire=ud.get("fire", False),
                web=ud.get("web", False),
                target_x=qt_x,
                target_y=qt_y,
                queued_target_x=qt_x,
                queued_target_y=qt_y,
                weapon_damage=min(ud.get("weapon_damage", 0), 255),
                weapon_target_behind=ud.get("weapon_target_behind", False),
                weapon_push=ud.get("weapon_push", 0),
            )
            board.units.append(u)

        # Detect Blast Psion: if alive on board, all Vek explode on death
        board.blast_psion_active = any(
            u.type == "Jelly_Explode1" and u.hp > 0 for u in board.units
        )

        # Detect Shell Psion: if alive on board, all Vek gain Armor
        board.armor_psion_active = any(
            u.type == "Jelly_Armor1" and u.hp > 0 for u in board.units
        )
        if board.armor_psion_active:
            for u in board.units:
                if u.is_enemy:
                    u.armor = True

        # Detect Soldier Psion: alive Jelly_Health1 buffs all Vek +1 HP
        board.soldier_psion_active = any(
            u.type == "Jelly_Health1" and u.hp > 0 for u in board.units
        )
        if board.soldier_psion_active:
            # Bridge sends hp already buffed but max_hp as base — adjust max_hp
            for u in board.units:
                if u.is_enemy and u.type != "Jelly_Health1":
                    u.max_hp += 1

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
