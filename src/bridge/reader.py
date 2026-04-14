"""Read game state from the Lua bridge and construct a Board.

Replaces save_parser.py as the state source when the bridge is active.
"""

from __future__ import annotations

import os
import re

from src.model.board import Board
from src.bridge.protocol import read_state


def _read_conveyor_belts_from_save() -> dict[tuple[int, int], int]:
    """Read conveyor belt data directly from the save file.

    Returns {(x, y): direction} where direction is 0-3.
    Direction: 0=right(+x), 1=down(+y), 2=left(-x), 3=up(-y).
    """
    belts = {}
    save_path = os.path.expanduser(
        "~/Library/Application Support/IntoTheBreach/profile_Alpha/saveData.lua"
    )
    try:
        with open(save_path) as f:
            content = f.read()
    except OSError:
        return belts

    # Match: ["loc"] = Point( x, y ), ... ["custom"] = "conveyorN.png"
    pattern = re.compile(
        r'\["loc"\]\s*=\s*Point\(\s*(\d+)\s*,\s*(\d+)\s*\)'
        r'.*?\["custom"\]\s*=\s*"conveyor(\d+)\.png"'
    )
    for m in pattern.finditer(content):
        x, y, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        belts[(x, y)] = d
    return belts


def _read_freeze_mines_from_save() -> set[tuple[int, int]]:
    """Read freeze mine locations from the save file.

    Fallback for when the bridge modloader hasn't been restarted.
    Returns set of (x, y) bridge coordinates with freeze mines.
    """
    mines = set()
    save_path = os.path.expanduser(
        "~/Library/Application Support/IntoTheBreach/profile_Alpha/saveData.lua"
    )
    try:
        with open(save_path) as f:
            content = f.read()
    except OSError:
        return mines

    # Match: ["loc"] = Point( x, y ), ... ["item"] = "Freeze_Mine"
    pattern = re.compile(
        r'\["loc"\]\s*=\s*Point\(\s*(\d+)\s*,\s*(\d+)\s*\)'
        r'[^}]*?\["item"\]\s*=\s*"Freeze_Mine[^"]*"'
    )
    for m in pattern.finditer(content):
        x, y = int(m.group(1)), int(m.group(2))
        mines.add((x, y))
    return mines


def _read_old_earth_mines_from_save() -> set[tuple[int, int]]:
    """Read Old Earth Mine locations from the save file.

    Fallback for when the bridge modloader hasn't been restarted.
    Returns set of (x, y) bridge coordinates with old earth mines.
    """
    mines = set()
    save_path = os.path.expanduser(
        "~/Library/Application Support/IntoTheBreach/profile_Alpha/saveData.lua"
    )
    try:
        with open(save_path) as f:
            content = f.read()
    except OSError:
        return mines

    # Match: ["loc"] = Point( x, y ), ... ["item"] = "Item_Mine"
    pattern = re.compile(
        r'\["loc"\]\s*=\s*Point\(\s*(\d+)\s*,\s*(\d+)\s*\)'
        r'[^}]*?\["item"\]\s*=\s*"Item_Mine"'
    )
    for m in pattern.finditer(content):
        x, y = int(m.group(1)), int(m.group(2))
        mines.add((x, y))
    return mines


def read_bridge_state() -> tuple[Board, dict] | tuple[None, None]:
    """Read bridge state and return (Board, raw_data) or (None, None).

    The raw_data dict contains extra fields not in the Board:
    - targeted_tiles: [[x,y], ...]
    - spawning_tiles: [[x,y], ...]
    - environment_danger: [[x,y], ...]
    - deployment_zone: [[x,y], ...] (available during deployment phase, turn 0)
    - phase: "combat_player" | "combat_enemy" | "unknown"
    - turn: int
    """
    data = read_state()
    if data is None:
        return None, None

    try:
        board = Board.from_bridge_data(data)

        # Supplement with conveyor belt data from save file
        # (Python-side fallback until Lua modloader restart picks up native support)
        conveyor_belts = _read_conveyor_belts_from_save()
        if conveyor_belts:
            for (x, y), direction in conveyor_belts.items():
                if 0 <= x < 8 and 0 <= y < 8:
                    board.tile(x, y).conveyor = direction

        # Supplement with freeze mine data from save file
        # (fallback until bridge modloader reports items natively)
        has_bridge_mines = any(
            board.tile(x, y).freeze_mine
            for x in range(8) for y in range(8)
        )
        if not has_bridge_mines:
            freeze_mines = _read_freeze_mines_from_save()
            for (x, y) in freeze_mines:
                if 0 <= x < 8 and 0 <= y < 8:
                    board.tile(x, y).freeze_mine = True

        # Supplement with old earth mine data from save file
        has_bridge_oe_mines = any(
            board.tile(x, y).old_earth_mine
            for x in range(8) for y in range(8)
        )
        if not has_bridge_oe_mines:
            oe_mines = _read_old_earth_mines_from_save()
            for (x, y) in oe_mines:
                if 0 <= x < 8 and 0 <= y < 8:
                    board.tile(x, y).old_earth_mine = True

        # Infer deployment zone from tile data when Lua GetZone fails
        # (Board:GetZone("deployment") has never returned tiles on this build)
        if data.get("turn", -1) == 0 and not data.get("deployment_zone"):
            deploy_tiles = _infer_deployment_zone(board)
            if deploy_tiles:
                data["deployment_zone"] = deploy_tiles

        return board, data
    except Exception as e:
        print(f"Bridge reader error: {e}")
        return None, None


# Terrain types that block deployment
_DEPLOY_BLOCKED = {"mountain", "water", "acid", "lava", "chasm", "ice"}


def _infer_deployment_zone(board: Board) -> list[list[int, int]]:
    """Infer deployment zone from board state on turn 0.

    Best-effort fallback when Board:GetZone("deployment") returns empty
    (typically because phase isn't deployment yet). In ITB the zone is
    usually the top 3 rows; Mission_Dam and a few others use rows 5-7
    instead. Without game-API ground truth we can't tell them apart,
    so this returns the top 3 rows (bridge x 0-2) excluding blocked
    terrain, buildings, occupied tiles, and acid pools. Forest IS
    deployable. Water-adjacent tiles are NOT filtered (Mission_Dam
    explicitly allows them).

    Caller MUST treat this as a hint — real source of truth is the
    live Board:GetZone("deployment") from modloader.lua.
    """
    occupied = {(u.x, u.y) for u in board.units}
    tiles = []
    for x in range(3):  # bridge x 0-2 = visual rows 8-6
        for y in range(8):
            t = board.tiles[x][y]
            if t.terrain in _DEPLOY_BLOCKED:
                continue
            if t.terrain == "building" and t.building_hp > 0:
                continue
            if t.acid:
                continue
            if (x, y) in occupied:
                continue
            tiles.append([x, y])
    return tiles
