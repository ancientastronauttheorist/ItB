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

        return board, data
    except Exception as e:
        print(f"Bridge reader error: {e}")
        return None, None
