"""Read game state from the Lua bridge and construct a Board.

Replaces save_parser.py as the state source when the bridge is active.
"""

from __future__ import annotations

import json
import os
import re

from src.model.board import Board
from src.bridge.protocol import read_state


# data/mission_metadata.json — used to flag infinite-spawn missions so the
# Rust solver doesn't collapse future_factor to 0 on the bridge-reported
# "final" turn (boss / Mission_Infinite have turn_limit=null and the
# bridge sets total_turns = current_turn). See feedback_grid_management.md
# / Corp HQ M05 Defeat 2026-04-28.
_MISSION_METADATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "mission_metadata.json",
)
_MISSION_METADATA_CACHE: dict | None = None


def _load_mission_metadata() -> dict:
    global _MISSION_METADATA_CACHE
    if _MISSION_METADATA_CACHE is not None:
        return _MISSION_METADATA_CACHE
    try:
        with open(_MISSION_METADATA_PATH) as f:
            payload = json.load(f)
        missions = payload.get("missions", {}) if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        missions = {}
    _MISSION_METADATA_CACHE = missions
    return missions


def _is_infinite_spawn_mission(mission_id: str) -> bool:
    """Return True iff `mission_id` has `infinite_spawn: true` (or is a
    boss mission with turn_limit=null) per data/mission_metadata.json.

    Boss missions and Mission_Infinite subclasses have no fixed turn
    limit; the bridge reports total_turns = current_turn so the solver
    sees "final turn" forever and ignores future enemies.
    """
    if not mission_id:
        return False
    md = _load_mission_metadata()
    rec = md.get(mission_id)
    if not isinstance(rec, dict):
        return False
    if rec.get("infinite_spawn"):
        return True
    # Boss missions also have turn_limit=null and grind for many turns.
    if rec.get("boss_mission") and rec.get("turn_limit") is None:
        return True
    return False


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


def _read_repair_pickups_from_save() -> int | None:
    """Read Mission_Repair progress when the running modloader is older.

    Lua bridge v48 emits this directly from mission.RepairPickups. This
    fallback is intentionally conservative: if multiple completed missions
    in the save contain RepairPickups, return None instead of guessing which
    one is live.
    """
    save_path = os.path.expanduser(
        "~/Library/Application Support/IntoTheBreach/profile_Alpha/saveData.lua"
    )
    try:
        with open(save_path) as f:
            content = f.read()
    except OSError:
        return None

    matches = re.findall(r'\["RepairPickups"\]\s*=\s*(\d+)', content)
    if len(matches) != 1:
        return None
    return int(matches[0])


def _read_teleporter_pads_from_save() -> list[tuple[int, int, int, int]]:
    """Recover Mission_Teleporter pad pairs from the save file.

    The Lua wrap in modloader.lua only captures pads when
    Mission_Teleporter:StartMission fires fresh. If the modloader was
    installed mid-mission, or the player quit and the game restored the
    save mid-mission, StartMission never re-fires and `_ITB_TELEPORT_PAIRS`
    stays empty — leaving the solver blind to swap mechanics.

    The engine persists pad coords in `RegionData.region<N>.player.teleports`
    as 4 sequential Points. Pairing is `array[1]↔array[2] + array[3]↔array[4]`
    — verified 2026-04-25 against in-game pad colors (RED↔RED + BLUE↔BLUE)
    on a live Mission_Teleporter board, matching how
    Mission_Teleporter:StartMission iterates `for i=1,2 do
    Board:AddTeleport(random_removal(t), random_removal(t)) end`.

    Returns up to 2 pairs as [(x1,y1,x2,y2), ...]; empty list if no pads
    found (saves on non-teleporter missions have no `["teleports"]` array).
    """
    pairs: list[tuple[int, int, int, int]] = []
    profile_dir = os.path.expanduser(
        "~/Library/Application Support/IntoTheBreach/profile_Alpha"
    )
    # saveData.lua first (live), undoSave.lua as fallback (post-restart
    # state where saveData.lua may be absent — observed 2026-04-25).
    for filename in ("saveData.lua", "undoSave.lua"):
        try:
            with open(os.path.join(profile_dir, filename)) as f:
                content = f.read()
        except OSError:
            continue

        m = re.search(r'\["teleports"\]\s*=\s*\{([^}]*)\}', content)
        if not m:
            continue
        pts = re.findall(
            r'Point\(\s*(\d+)\s*,\s*(\d+)\s*\)', m.group(1)
        )
        if len(pts) >= 4:
            c = [(int(x), int(y)) for x, y in pts[:4]]
            return [
                (c[0][0], c[0][1], c[1][0], c[1][1]),
                (c[2][0], c[2][1], c[3][0], c[3][1]),
            ]
    return pairs


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
        nx, ny = cx + ddx, cy + ddy
        # Guard against off-board normalized targets (M04 OOB bug 2026-04-28:
        # Vek at cx=7,ddx=+1 produced queued_target.x=8 → Rust tile_mut OOB
        # panic at enemy.rs:883/889 and Python IndexError in board.tile()).
        if 0 <= nx < 8 and 0 <= ny < 8:
            u["queued_target"] = [nx, ny]
        else:
            u["queued_target"] = None


def read_bridge_state() -> tuple[Board, dict] | tuple[None, None]:
    """Read bridge state and return (Board, raw_data) or (None, None).

    The raw_data dict contains extra fields not in the Board:
    - targeted_tiles: [[x,y], ...]
    - spawning_tiles: [[x,y], ...]
    - environment_danger: [[x,y], ...]
    - deployment_zone: [[x,y], ...] (available during deployment phase, turn 0)
    - phase: "combat_player" | "combat_enemy" | "unknown"
    - turn: int
    - island_map: [{region_id, mission_id, bonus_objective_ids, environment,
                    diff_mod?, asset_id?, boss?}, ...] OR None — populated
      when the player is between missions on the corp island map (so the
      mission picker can score available missions). None inside an active
      mission. Source: GAME.Missions in the Lua bridge (modloader.lua).
    - island_index: int — 1-based current island slot, when island_map
      is non-null.
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

    # Mission_Repair progress (Use 3 Repair Platforms). Old live modloader
    # builds already emit tile.item="Item_Repair_Mine" but not the progress
    # scalar; supplement it from saveData.lua until the game is restarted with
    # the updated bridge.
    if data.get("mission_id") == "Mission_Repair":
        data.setdefault("repair_platform_target", 3)
        if "repair_platforms_used" not in data:
            pickups = _read_repair_pickups_from_save()
            if pickups is not None:
                data["repair_platforms_used"] = pickups

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

        # Teleporter pads: the Lua wrap only fires on a fresh
        # Mission_Teleporter:StartMission. If the modloader installed
        # mid-mission or the game restored from save, _ITB_TELEPORT_PAIRS
        # stays empty. Recover from the save file (engine persists pad
        # coords in region.player.teleports across save/load).
        if (not board.teleporter_pairs
                and data.get("mission_id") == "Mission_Teleporter"):
            recovered = _read_teleporter_pads_from_save()
            if recovered:
                board.teleporter_pairs = list(recovered)
                data["teleporter_pairs"] = [list(p) for p in recovered]
                data["teleporter_pairs_source"] = "save_fallback"

        # Infinite-spawn / boss-mission flag for the Rust solver. Bridge
        # reports total_turns = current_turn on these missions (turn_limit
        # is null in mission_metadata), which collapses future_factor to 0
        # and tells the solver kills are worth nothing. Pass the flag so
        # evaluate.rs::future_factor can floor at 0.5 when set. See
        # feedback_grid_management.md / Corp HQ M05 Defeat 2026-04-28.
        data["is_infinite_spawn"] = _is_infinite_spawn_mission(
            data.get("mission_id") or ""
        )

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
