"""Scan the game board by hovering over each tile and reading the tooltip.

Uses the computer-use MCP tool to hover over tile centers and capture
the tooltip text to build ground truth. This is the authoritative way
to identify what's on each tile — the game itself tells us.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum


class Terrain(str, Enum):
    GROUND = "ground"
    FOREST = "forest"
    SAND = "sand"
    WATER = "water"
    ICE = "ice"
    LAVA = "lava"
    MOUNTAIN = "mountain"
    CHASM = "chasm"
    BUILDING = "building"
    UNKNOWN = "unknown"


class Team(str, Enum):
    PLAYER = "player"  # mechs
    ENEMY = "enemy"    # Vek
    NEUTRAL = "neutral"
    NONE = "none"


@dataclass
class TileState:
    """State of a single tile."""
    row: int
    col: int
    terrain: str = "unknown"
    occupant: str = ""        # unit name (e.g. "Cannon Mech", "Leaper")
    team: str = "none"
    hp: int = 0
    on_fire: bool = False
    has_smoke: bool = False
    has_acid: bool = False
    is_frozen: bool = False
    is_shielded: bool = False
    attack_direction: str = ""  # "", "N", "S", "E", "W"
    attack_damage: int = 0
    is_emerging: bool = False   # Vek about to emerge


@dataclass
class BoardState:
    """Full board state for a single turn."""
    tiles: list[TileState] = field(default_factory=list)
    grid_power: int = 0
    grid_defense_pct: int = 0
    turn_number: int = 0
    victory_turns: int = 0

    def get_tile(self, row: int, col: int) -> TileState | None:
        for t in self.tiles:
            if t.row == row and t.col == col:
                return t
        return None

    def to_json(self, path: str | Path) -> None:
        data = asdict(self)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def from_json(cls, path: str | Path) -> BoardState:
        with open(path) as f:
            data = json.load(f)
        tiles = [TileState(**t) for t in data.pop('tiles', [])]
        return cls(tiles=tiles, **data)


def parse_tooltip(terrain_text: str, unit_text: str = "") -> dict:
    """Parse game tooltip text into terrain type and unit info.

    Args:
        terrain_text: The tile type text (e.g., "Ground Tile", "Forest Tile")
        unit_text: The unit name if hovering over a unit

    Returns:
        Dict with terrain, occupant, team fields
    """
    terrain_map = {
        "ground": Terrain.GROUND,
        "forest": Terrain.FOREST,
        "sand": Terrain.SAND,
        "water": Terrain.WATER,
        "ice": Terrain.ICE,
        "lava": Terrain.LAVA,
        "mountain": Terrain.MOUNTAIN,
        "chasm": Terrain.CHASM,
        "building": Terrain.BUILDING,
    }

    terrain = Terrain.UNKNOWN
    text_lower = terrain_text.lower()
    for key, value in terrain_map.items():
        if key in text_lower:
            terrain = value
            break

    # Detect team from unit name
    team = Team.NONE
    mech_keywords = ["mech", "tank", "artillery", "cannon"]
    vek_keywords = ["vek", "leaper", "firefly", "hornet", "scorpion",
                    "beetle", "spider", "blob", "centipede", "burrower",
                    "digger", "scarab"]

    if unit_text:
        name_lower = unit_text.lower()
        if any(k in name_lower for k in mech_keywords):
            team = Team.PLAYER
        elif any(k in name_lower for k in vek_keywords):
            team = Team.ENEMY
        else:
            team = Team.NEUTRAL

    return {
        "terrain": terrain.value,
        "occupant": unit_text,
        "team": team.value,
    }
