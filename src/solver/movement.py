"""Movement range computation for mechs and Vek.

Uses BFS on the 8x8 grid, respecting terrain and unit blocking.
"""

from __future__ import annotations

from collections import deque
from src.model.board import Board, Unit

# Cardinal directions: (dx, dy)
DIRS = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # N, E, S, W
DIR_NAMES = ["N", "E", "S", "W"]


def get_reachable_tiles(
    board: Board,
    unit: Unit,
    include_current: bool = True,
) -> list[tuple[int, int]]:
    """Compute all tiles a unit can move to.

    Uses BFS with move_speed steps. Units block movement but
    flying units can pass over water/chasms.

    Returns:
        List of (x, y) coordinates the unit can reach.
    """
    reachable = []
    if include_current:
        reachable.append((unit.x, unit.y))

    visited = {(unit.x, unit.y): 0}
    queue = deque([(unit.x, unit.y, 0)])

    while queue:
        x, y, cost = queue.popleft()

        for dx, dy in DIRS:
            nx, ny = x + dx, y + dy

            if not board.in_bounds(nx, ny):
                continue
            if (nx, ny) in visited:
                continue

            new_cost = cost + 1
            if new_cost > unit.move_speed:
                continue

            tile = board.tile(nx, ny)

            # Mountains always block
            if tile.terrain == "mountain":
                continue

            # Buildings block
            if tile.terrain == "building" and tile.building_hp > 0:
                continue

            # Ground units can't cross water/chasm/lava
            if not unit.flying and tile.terrain in ("water", "chasm", "lava"):
                continue

            # Other units block (can't move through them)
            blocker = board.unit_at(nx, ny)
            if blocker is not None and blocker.uid != unit.uid:
                visited[(nx, ny)] = new_cost
                continue  # can't stop here but mark visited

            visited[(nx, ny)] = new_cost
            reachable.append((nx, ny))
            queue.append((nx, ny, new_cost))

    return reachable


def get_adjacent(x: int, y: int) -> list[tuple[int, int, int]]:
    """Get valid adjacent tiles with direction index.

    Returns: [(nx, ny, dir_idx), ...]
    """
    result = []
    for i, (dx, dy) in enumerate(DIRS):
        nx, ny = x + dx, y + dy
        if 0 <= nx < 8 and 0 <= ny < 8:
            result.append((nx, ny, i))
    return result


def direction_between(from_x: int, from_y: int, to_x: int, to_y: int) -> int | None:
    """Get the cardinal direction index from one tile to an adjacent tile.

    Returns: direction index (0=N, 1=E, 2=S, 3=W) or None if not adjacent.
    """
    dx, dy = to_x - from_x, to_y - from_y
    try:
        return DIRS.index((dx, dy))
    except ValueError:
        return None


def opposite_dir(d: int) -> int:
    """Get the opposite direction (N<->S, E<->W)."""
    return (d + 2) % 4


def push_destination(x: int, y: int, direction: int, board: Board) -> tuple[int, int] | None:
    """Predict where a unit ends up after being pushed in a direction.

    Returns (new_x, new_y) if the push succeeds (unit moves), or None if
    the push is blocked (edge, mountain, building, or another unit).

    Note: In Into the Breach, there is NO chain pushing. If destination
    is occupied by any unit, the push is blocked (bump damage to both).
    The unit may die if pushed into deadly terrain (water/chasm/lava).
    """
    dx, dy = DIRS[direction]
    nx, ny = x + dx, y + dy

    if not board.in_bounds(nx, ny):
        return None  # blocked by map edge

    tile = board.tile(nx, ny)
    if tile.terrain == "mountain":
        return None  # blocked by mountain

    if tile.terrain == "building" and tile.building_hp > 0:
        return None  # blocked by building

    # Any unit blocks the push (no chain pushing)
    if board.unit_at(nx, ny) is not None:
        return None  # blocked by unit — both take bump

    return (nx, ny)
