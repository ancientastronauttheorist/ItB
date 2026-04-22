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


def _read_queued_origins_from_save() -> dict[int, tuple[int, int]]:
    """Read ``piOrigin`` per unit uid from the save file.

    piQueuedShot is stored relative to piOrigin (the attacker's position
    when the attack was queued), not the attacker's current position. If
    the attacker moved between queueing and firing, the bridge's raw
    queued_target (= piQueuedShot) gives a bogus non-cardinal vector from
    the current position. Pair it with piOrigin to recover the true
    cardinal direction: direction = piQueuedShot - piOrigin.

    Returns {uid: (piOrigin_x, piOrigin_y)}.
    """
    origins: dict[int, tuple[int, int]] = {}
    save_path = os.path.expanduser(
        "~/Library/Application Support/IntoTheBreach/profile_Alpha/saveData.lua"
    )
    try:
        with open(save_path) as f:
            content = f.read()
    except OSError:
        return origins

    # Match blocks that have iOwner + piOrigin + piQueuedShot. Filter to
    # entries where piQueuedShot is an actual queued attack (not -1, -1).
    pattern = re.compile(
        r'\["iOwner"\]\s*=\s*(-?\d+),'
        r'.*?\["piOrigin"\]\s*=\s*Point\((-?\d+)\s*,\s*(-?\d+)\)'
        r'.*?\["piQueuedShot"\]\s*=\s*Point\((-?\d+)\s*,\s*(-?\d+)\)',
        re.DOTALL,
    )
    for m in pattern.finditer(content):
        owner = int(m.group(1))
        ox, oy = int(m.group(2)), int(m.group(3))
        qx, qy = int(m.group(4)), int(m.group(5))
        if qx < 0 or qy < 0:
            continue  # no queued shot
        if ox < 0 or oy < 0:
            continue
        origins[owner] = (ox, oy)
    return origins


def _normalize_queued_targets(bridge_units: list) -> None:
    """Rewrite ``queued_target`` on each unit so the solver invariant holds.

    Invariant: ``queued_target - current_position`` yields a unit cardinal
    vector. The raw bridge value is piQueuedShot, which is relative to
    piOrigin (attacker's position when queued), not current position. If
    the attacker moved between queueing and firing, the delta becomes
    non-cardinal (e.g. Centipede at E8 with piQueuedShot C7 after moving
    from D7: raw delta (+1, +2)).

    For each unit with a queued_target: look up piOrigin from the save
    file, compute direction = piQueuedShot - piOrigin, then rewrite
    queued_target = current_position + direction. Mutates bridge_units
    in place.
    """
    origins = _read_queued_origins_from_save()
    if not origins:
        return
    for u in bridge_units:
        qt = u.get("queued_target")
        if not qt or len(qt) != 2:
            continue
        qx, qy = qt[0], qt[1]
        if qx < 0 or qy < 0:
            continue
        uid = u.get("uid")
        origin = origins.get(uid)
        if origin is None:
            continue
        ox, oy = origin
        # Direction from piOrigin to piQueuedShot. Expected to be a unit
        # cardinal vector; if not, leave alone (modloader bug to fix).
        ddx = qx - ox
        ddy = qy - oy
        if ddx != 0 and ddy != 0:
            continue  # shouldn't happen per game rules
        if ddx == 0 and ddy == 0:
            continue  # self-target (e.g. WebbEgg hatch); leave as is
        cx, cy = u.get("x", -1), u.get("y", -1)
        if cx < 0 or cy < 0:
            continue
        # Normalize to one-step-in-direction so the solver's standard
        # direction computation (queued_target - current_pos) works.
        u["queued_target"] = [cx + ddx, cy + ddy]


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

    # Rewrite queued_target on each unit using piOrigin from the save file.
    # Bridge modloader currently emits piQueuedShot raw, which gives a
    # non-cardinal delta if the attacker moved after queueing. Fix before
    # constructing the Board so downstream solvers see the right direction.
    if "units" in data:
        _normalize_queued_targets(data["units"])

    try:
        board = Board.from_bridge_data(data)

        # Supplement with conveyor belt data from save file
        # (Python-side fallback until Lua modloader restart picks up native support)
        conveyor_belts = _read_conveyor_belts_from_save()
        if conveyor_belts:
            for (x, y), direction in conveyor_belts.items():
                if 0 <= x < 8 and 0 <= y < 8:
                    board.tile(x, y).conveyor = direction

        # Supplement mines from save file ONLY on turn 0 (mission start).
        # After turn 0 the Lua bridge is authoritative for mine presence —
        # the save file can contain stale mines that were consumed in-game
        # but not cleared from the save region, and injecting those produces
        # phantom mines that cause the solver to predict non-existent kills
        # (run 20260421_211617_239 m02 t01 a2: Scorpion "killed" by phantom
        # Old Earth Mine at C4 that the bridge correctly did not emit).
        turn = data.get("turn", -1)
        if turn <= 0:
            has_bridge_freeze_mines = any(
                board.tile(x, y).freeze_mine
                for x in range(8) for y in range(8)
            )
            if not has_bridge_freeze_mines:
                freeze_mines = _read_freeze_mines_from_save()
                for (x, y) in freeze_mines:
                    if 0 <= x < 8 and 0 <= y < 8:
                        board.tile(x, y).freeze_mine = True

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

    Fallback when Board:GetZone("deployment") returns empty (which is
    what happens for every non-final mission — the engine only fills
    that zone for special maps like mission_final.lua).

    The rectangle is visual B–G × rows 5–7 (bridge x=1..3, y=1..6),
    minus blocked terrain / buildings / occupied / acid tiles. This
    mirrors the wiki-documented spawn rule ("Vek prioritize columns
    B–G, rows 1–3") and matches empirical observation of the yellow
    drop zone across missions. Edge columns A/H and rows 8/1–4 are
    never yellow in regular missions.
    """
    occupied = {(u.x, u.y) for u in board.units}
    tiles = []
    for x in (1, 2, 3):  # bridge x=1..3 = visual rows 7, 6, 5
        for y in range(1, 7):  # bridge y=1..6 = visual columns G..B
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
