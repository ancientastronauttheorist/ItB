"""Read game state from the Lua bridge and construct a Board.

Replaces save_parser.py as the state source when the bridge is active.
"""

from __future__ import annotations

from src.model.board import Board
from src.bridge.protocol import read_state


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
        return board, data
    except Exception as e:
        print(f"Bridge reader error: {e}")
        return None, None
