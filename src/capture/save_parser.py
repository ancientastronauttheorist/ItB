"""Parse Into the Breach save files to extract complete game state.

The game writes Lua table literals to save files. We parse these into
Python dicts, then extract structured game state. This replaces computer
vision for state extraction — faster, 100% accurate, complete.

Save file locations (macOS):
  ~/Library/Application Support/IntoTheBreach/profile_<name>/saveData.lua
  ~/Library/Application Support/IntoTheBreach/profile_<name>/undoSave.lua
"""

from __future__ import annotations

import re
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

# Save directory
SAVE_DIR = Path.home() / "Library" / "Application Support" / "IntoTheBreach"

# Terrain type mapping from save file integers
TERRAIN_MAP = {
    0: "ground",
    1: "building",
    2: "rubble",
    3: "mountain",
    4: "water",
    5: "lava",
    6: "forest",
    7: "sand",
    8: "ice",
    9: "chasm",
}


@dataclass
class Point:
    x: int
    y: int

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.x, self.y))

    def __repr__(self):
        return f"({self.x},{self.y})"


@dataclass
class Pawn:
    """A unit on the board (mech, Vek, or neutral)."""
    pawn_id: int
    type: str
    location: Point
    health: int
    max_health: int
    team_id: int  # 1=player, 2=neutral, 6=enemy
    is_mech: bool
    primary_weapon: str = ""
    pilot_name: str = ""
    pilot_id: str = ""
    is_corpse: bool = False
    # Attack intent
    target: Point | None = None      # piTarget - where they're aiming
    queued_shot: Point | None = None  # piQueuedShot - confirmed attack target
    queued_skill: int = -1            # iQueuedSkill - which weapon

    @property
    def is_player(self) -> bool:
        return self.team_id == 1

    @property
    def is_enemy(self) -> bool:
        return self.team_id == 6

    @property
    def is_alive(self) -> bool:
        # is_corpse in save files means "has undo state", not actually dead
        return self.health > 0


@dataclass
class Tile:
    """A single board tile."""
    x: int
    y: int
    terrain: str = "ground"
    terrain_id: int = 0
    populated: bool = False
    population: int = 0
    health_max: int = 0
    health_min: int = 0
    on_fire: bool = False
    has_pod: bool = False
    unique: str = ""  # special building ID


@dataclass
class MissionState:
    """Complete state of the active mission."""
    mission_name: str = ""
    map_name: str = ""
    current_turn: int = 0
    team_turn: int = 0  # 1=player, 6=enemy
    victory_turns: int = 0
    tiles: list[Tile] = field(default_factory=list)
    pawns: list[Pawn] = field(default_factory=list)
    spawns: list[str] = field(default_factory=list)
    spawn_points: list[Point] = field(default_factory=list)

    def get_tile(self, x: int, y: int) -> Tile:
        for t in self.tiles:
            if t.x == x and t.y == y:
                return t
        # Tiles not in map data default to ground
        return Tile(x=x, y=y, terrain="ground", terrain_id=0)

    def get_pawn_at(self, x: int, y: int) -> Pawn | None:
        for p in self.pawns:
            if p.location.x == x and p.location.y == y and p.is_alive:
                return p
        return None

    def get_mechs(self) -> list[Pawn]:
        return [p for p in self.pawns if p.is_player and p.is_alive]

    def get_enemies(self) -> list[Pawn]:
        return [p for p in self.pawns if p.is_enemy and p.is_alive]

    def get_threatened_tiles(self) -> list[tuple[Point, Pawn]]:
        """Return tiles that enemies are targeting."""
        threats = []
        for p in self.get_enemies():
            if p.queued_shot and p.queued_shot.x >= 0:
                threats.append((p.queued_shot, p))
        return threats

    def print_board(self) -> None:
        """Print ASCII representation of the board."""
        symbols = {
            "ground": ".", "building": "B", "mountain": "M",
            "water": "~", "forest": "F", "sand": "S",
            "ice": "I", "lava": "L", "chasm": " ", "rubble": "R",
        }
        for y in range(7, -1, -1):
            row = []
            for x in range(8):
                tile = self.get_tile(x, y)
                pawn = self.get_pawn_at(x, y)
                if pawn:
                    if pawn.is_player:
                        row.append("P")
                    elif pawn.is_enemy:
                        row.append("E")
                    else:
                        row.append("N")
                else:
                    row.append(symbols.get(tile.terrain, "?"))
            print(f"  {y} {'  '.join(row)}")
        print(f"    {'  '.join(str(x) for x in range(8))}")


@dataclass
class GameState:
    """Top-level game state from save file."""
    grid_power: int = 0
    grid_power_max: int = 0
    difficulty: int = 0
    squad_name: str = ""
    mechs: list[str] = field(default_factory=list)
    active_mission: MissionState | None = None


def parse_lua_value(text: str, pos: int = 0) -> tuple[Any, int]:
    """Parse a Lua value from text starting at pos.

    Returns (value, new_pos).
    """
    # Skip whitespace
    while pos < len(text) and text[pos] in ' \t\n\r,':
        pos += 1

    if pos >= len(text):
        return None, pos

    ch = text[pos]

    # String
    if ch == '"':
        end = text.index('"', pos + 1)
        return text[pos + 1:end], end + 1

    # Table
    if ch == '{':
        return parse_lua_table(text, pos)

    # Point(x, y)
    if text[pos:pos + 5] == 'Point':
        m = re.match(r'Point\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)', text[pos:])
        if m:
            return Point(int(m.group(1)), int(m.group(2))), pos + m.end()

    # CreateEffect({...})
    if text[pos:pos + 12] == 'CreateEffect':
        # Skip to matching closing paren
        depth = 0
        i = pos
        while i < len(text):
            if text[i] == '(':
                depth += 1
            elif text[i] == ')':
                depth -= 1
                if depth == 0:
                    return None, i + 1
            i += 1
        return None, len(text)

    # Boolean
    if text[pos:pos + 4] == 'true':
        return True, pos + 4
    if text[pos:pos + 5] == 'false':
        return False, pos + 5

    # Number (int or float)
    m = re.match(r'-?\d+\.?\d*', text[pos:])
    if m:
        s = m.group()
        val = float(s) if '.' in s else int(s)
        return val, pos + m.end()

    # nil
    if text[pos:pos + 3] == 'nil':
        return None, pos + 3

    return None, pos + 1


def parse_lua_table(text: str, pos: int = 0) -> tuple[dict | list, int]:
    """Parse a Lua table literal {...} into a Python dict or list."""
    if text[pos] != '{':
        return {}, pos

    pos += 1  # skip '{'
    result = {}
    array_items = []
    array_index = 1

    while pos < len(text):
        # Skip whitespace and commas
        while pos < len(text) and text[pos] in ' \t\n\r,':
            pos += 1

        if pos >= len(text) or text[pos] == '}':
            pos += 1
            break

        # ["key"] = value
        if text[pos] == '[':
            if text[pos + 1] == '"':
                key_end = text.index('"', pos + 2)
                key = text[pos + 2:key_end]
                pos = key_end + 1
                while pos < len(text) and text[pos] in ' \t\n\r]':
                    pos += 1
                if pos < len(text) and text[pos] == '=':
                    pos += 1
                val, pos = parse_lua_value(text, pos)
                result[key] = val
            else:
                # [number] = value
                m = re.match(r'\[(\d+)\]\s*=\s*', text[pos:])
                if m:
                    idx = int(m.group(1))
                    pos += m.end()
                    val, pos = parse_lua_value(text, pos)
                    result[idx] = val
                else:
                    pos += 1

        # Bare value (array element)
        elif text[pos] == '{' or text[pos] == '"' or text[pos:pos + 5] == 'Point':
            val, pos = parse_lua_value(text, pos)
            array_items.append(val)

        # key = value (without brackets)
        elif text[pos].isalpha() or text[pos] == '_':
            m = re.match(r'(\w+)\s*=\s*', text[pos:])
            if m:
                key = m.group(1)
                pos += m.end()
                val, pos = parse_lua_value(text, pos)
                result[key] = val
            else:
                pos += 1
        else:
            pos += 1

    # If we have array items but no dict keys, return as list
    if array_items and not result:
        return array_items, pos
    # If we have both, merge arrays into dict
    if array_items:
        for i, item in enumerate(array_items):
            result[i] = item

    return result, pos


def parse_save_file(path: Path) -> dict[str, Any]:
    """Parse a complete save file into top-level variable assignments.

    Returns dict mapping variable names to parsed values.
    """
    text = path.read_text(encoding='utf-8', errors='replace')
    result = {}

    # Find top-level assignments: VarName = { ... }
    pattern = re.compile(r'^(\w+)\s*=\s*\{', re.MULTILINE)
    for m in pattern.finditer(text):
        var_name = m.group(1)
        start = m.start() + len(m.group()) - 1  # position of '{'
        try:
            val, _ = parse_lua_table(text, start)
            result[var_name] = val
        except (ValueError, IndexError):
            continue

    return result


def extract_mission_state(
    player_data: dict,
    map_data: dict,
) -> MissionState:
    """Extract MissionState from parsed player/map data."""
    mission = MissionState(
        mission_name=player_data.get('sMission', ''),
        map_name=map_data.get('name', ''),
        current_turn=player_data.get('iCurrentTurn', 0),
        team_turn=player_data.get('iTeamTurn', 0),
        victory_turns=player_data.get('victory', 0),
    )

    # Parse map tiles
    for tile_data in map_data.get('map', []):
        if not isinstance(tile_data, dict):
            continue
        loc = tile_data.get('loc')
        if not isinstance(loc, Point):
            continue

        terrain_id = tile_data.get('terrain', 0)
        tile = Tile(
            x=loc.x, y=loc.y,
            terrain=TERRAIN_MAP.get(terrain_id, "unknown"),
            terrain_id=terrain_id,
            populated=bool(tile_data.get('populated', 0)),
            population=tile_data.get('people1', 0),
            health_max=tile_data.get('health_max', 0),
            health_min=tile_data.get('health_min', 0),
            on_fire=bool(tile_data.get('fire', 0)),
            has_pod=bool(tile_data.get('pod', 0)),
            unique=tile_data.get('unique', ''),
        )
        mission.tiles.append(tile)

    # Parse spawns
    spawns = map_data.get('spawns', [])
    if isinstance(spawns, list):
        mission.spawns = [s for s in spawns if isinstance(s, str)]

    spawn_pts = map_data.get('spawn_points', [])
    if isinstance(spawn_pts, list):
        mission.spawn_points = [p for p in spawn_pts if isinstance(p, Point)]

    # Parse pawns
    pawn_count = map_data.get('pawn_count', 0)
    for i in range(1, pawn_count + 1):
        key = f'pawn{i}'
        pd = map_data.get(key, {})
        if not isinstance(pd, dict):
            continue

        loc = pd.get('location', Point(-1, -1))
        target = pd.get('piTarget', Point(-1, -1))
        queued = pd.get('piQueuedShot', Point(-1, -1))

        pilot = pd.get('pilot', {})
        if not isinstance(pilot, dict):
            pilot = {}

        pawn = Pawn(
            pawn_id=pd.get('id', 0),
            type=pd.get('type', ''),
            location=loc if isinstance(loc, Point) else Point(-1, -1),
            health=pd.get('health', 0),
            max_health=pd.get('max_health', 0),
            team_id=pd.get('iTeamId', 0),
            is_mech=bool(pd.get('mech', False)),
            primary_weapon=pd.get('primary', ''),
            pilot_name=pilot.get('name', ''),
            pilot_id=pilot.get('id', ''),
            is_corpse=bool(pd.get('is_corpse', False)),
            target=target if isinstance(target, Point) and target.x >= 0 else None,
            queued_shot=queued if isinstance(queued, Point) and queued.x >= 0 else None,
            queued_skill=pd.get('iQueuedSkill', -1),
        )
        mission.pawns.append(pawn)

    return mission


def load_active_mission(profile: str = "Alpha") -> MissionState | None:
    """Load the active mission state from save files.

    Tries saveData.lua first (written during battle), falls back to
    undoSave.lua (previous turn state).
    """
    profile_dir = SAVE_DIR / f"profile_{profile}"

    for filename in ['saveData.lua', 'undoSave.lua']:
        path = profile_dir / filename
        if not path.exists():
            continue

        data = parse_save_file(path)
        region_data = data.get('RegionData', {})

        # Find the active battle region
        battle_region = region_data.get('iBattleRegion', -1)
        if battle_region < 0:
            continue

        region_key = f'region{battle_region}'
        region = region_data.get(region_key, {})
        player = region.get('player', {})
        map_data = player.get('map_data', {})

        if not map_data:
            continue

        return extract_mission_state(player, map_data)

    return None


def load_game_state(profile: str = "Alpha") -> GameState | None:
    """Load complete game state from save files."""
    profile_dir = SAVE_DIR / f"profile_{profile}"

    for filename in ['saveData.lua', 'undoSave.lua']:
        path = profile_dir / filename
        if not path.exists():
            continue

        data = parse_save_file(path)
        game_data = data.get('GameData', {})

        state = GameState(
            grid_power=game_data.get('network', 0),
            grid_power_max=game_data.get('networkMax', 7),
            difficulty=game_data.get('difficulty', 0),
        )

        current = game_data.get('current', {})
        if isinstance(current, dict):
            mechs = current.get('mechs', [])
            if isinstance(mechs, list):
                state.mechs = [m for m in mechs if isinstance(m, str)]

        state.active_mission = load_active_mission(profile)
        return state

    return None


if __name__ == "__main__":
    print("Loading game state from save files...")
    state = load_game_state()

    if state is None:
        print("No save data found")
    else:
        print(f"Grid Power: {state.grid_power}/{state.grid_power_max}")
        print(f"Difficulty: {state.difficulty}")
        print(f"Mechs: {state.mechs}")

        if state.active_mission:
            m = state.active_mission
            print(f"\nActive Mission: {m.mission_name} ({m.map_name})")
            print(f"Turn: {m.current_turn}")
            print(f"Pawns: {len(m.pawns)}")

            print("\nBoard:")
            m.print_board()

            print("\nMechs:")
            for p in m.get_mechs():
                print(f"  {p.type} at {p.location} HP={p.health}/{p.max_health} "
                      f"weapon={p.primary_weapon} pilot={p.pilot_name}")

            print("\nEnemies:")
            for p in m.get_enemies():
                target = f" -> {p.queued_shot}" if p.queued_shot else ""
                print(f"  {p.type} at {p.location} HP={p.health}/{p.max_health}{target}")

            print("\nThreats:")
            for tile, pawn in m.get_threatened_tiles():
                print(f"  {tile} threatened by {pawn.type} at {pawn.location}")

            print(f"\nSpawns next turn: {m.spawns} at {m.spawn_points}")
