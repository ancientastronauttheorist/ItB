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
    # Enemy intent
    target_x: int = -1
    target_y: int = -1

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


class Board:
    """8x8 game board for solver search."""

    def __init__(self):
        self.tiles: list[list[BoardTile]] = [
            [BoardTile() for _ in range(8)] for _ in range(8)
        ]
        self.units: list[Unit] = []
        self.grid_power: int = 0
        self.grid_power_max: int = 7

    def copy(self) -> Board:
        """Deep copy for search branching."""
        b = Board()
        b.tiles = [[deepcopy(self.tiles[x][y]) for y in range(8)] for x in range(8)]
        b.units = [deepcopy(u) for u in self.units]
        b.grid_power = self.grid_power
        b.grid_power_max = self.grid_power_max
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

    def print_board(self):
        """ASCII board for debugging."""
        sym = {
            "ground": ".", "building": "B", "mountain": "M",
            "water": "~", "forest": "F", "sand": "S",
            "ice": "I", "lava": "L", "chasm": " ", "rubble": "R",
        }
        for y in range(7, -1, -1):
            row = []
            for x in range(8):
                u = self.unit_at(x, y)
                if u:
                    row.append("P" if u.is_player else ("E" if u.is_enemy else "N"))
                else:
                    t = self.tile(x, y)
                    c = sym.get(t.terrain, "?")
                    if t.on_fire:
                        c = "*"
                    row.append(c)
            print(f"  {y} {'  '.join(row)}")
        print(f"    {'  '.join(str(x) for x in range(8))}")
