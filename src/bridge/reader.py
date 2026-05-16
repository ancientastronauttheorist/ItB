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


def _parse_conveyor_belts_from_save_text(content: str) -> dict[tuple[int, int], int]:
    """Parse conveyor sprites without crossing serialized tile entries."""
    belts = {}
    loc_re = re.compile(r'\["loc"\]\s*=\s*Point\(\s*(\d+)\s*,\s*(\d+)\s*\)')
    custom_re = re.compile(r'\["custom"\]\s*=\s*"conveyor(\d+)\.png"')
    for line in content.splitlines():
        loc = loc_re.search(line)
        custom = custom_re.search(line)
        if not loc or not custom:
            continue
        x, y, d = int(loc.group(1)), int(loc.group(2)), int(custom.group(1))
        belts[(x, y)] = d
    return belts


def _read_conveyor_belts_from_save() -> dict[tuple[int, int], int]:
    """Read conveyor belt data directly from the save file.

    Returns {(x, y): direction} where direction is 0-3.
    Direction: 0=right(+x), 1=down(+y), 2=left(-x), 3=up(-y).
    """
    save_path = os.path.expanduser(
        "~/Library/Application Support/IntoTheBreach/profile_Alpha/saveData.lua"
    )
    try:
        with open(save_path) as f:
            content = f.read()
    except OSError:
        return {}
    return _parse_conveyor_belts_from_save_text(content)


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


def _parse_mech_stat_overlays_from_save_text(content: str) -> dict[int, dict]:
    """Return save-backed mech stat records keyed by pawn uid.

    The live Lua bridge can report a pawn definition's base max HP while the
    save file already has the effective in-mission max_health from pilot perks
    and powered +Health upgrades. Parse only narrow scalar fields here; never
    use save health for live HP because it can lag after bridge actions.
    """
    records: dict[int, dict] = {}
    pawn_re = re.compile(
        r'\["pawn\d+"\]\s*=\s*\{(?P<body>.*?)(?=\n\n\["pawn\d+"\]|\n\n\["blocked"|\n\n\["spawn|\n\n\["zones"|\n\n\["tags"|$)',
        re.S,
    )
    for match in pawn_re.finditer(content):
        body = match.group("body")
        if '["mech"] = true' not in body:
            continue

        uid_m = re.search(r'\["id"\]\s*=\s*(-?\d+)', body)
        if not uid_m:
            continue
        uid = int(uid_m.group(1))
        rec: dict = {}

        type_m = re.search(r'\["type"\]\s*=\s*"([^"]*)"', body)
        if type_m:
            rec["type"] = type_m.group(1)

        max_hp_m = re.search(r'\["max_health"\]\s*=\s*(-?\d+)', body)
        if max_hp_m:
            rec["max_hp"] = int(max_hp_m.group(1))

        health_power_m = re.search(r'\["healthPower"\]\s*=\s*\{\s*(-?\d+)', body)
        if health_power_m:
            rec["health_power"] = int(health_power_m.group(1))

        pilot_m = re.search(r'\["pilot"\]\s*=\s*\{(?P<pilot>.*?)\},', body, re.S)
        if pilot_m:
            pilot = pilot_m.group("pilot")
            for save_key, out_key in (
                ("id", "pilot_id"),
                ("name", "pilot_name"),
                ("name_id", "pilot_name_id"),
            ):
                val_m = re.search(
                    rf'\["{save_key}"\]\s*=\s*"([^"]*)"', pilot,
                )
                if val_m:
                    rec[out_key] = val_m.group(1)
            for save_key, out_key in (
                ("skill1", "pilot_skill1"),
                ("skill2", "pilot_skill2"),
                ("level", "pilot_level"),
            ):
                val_m = re.search(rf'\["{save_key}"\]\s*=\s*(-?\d+)', pilot)
                if val_m:
                    rec[out_key] = int(val_m.group(1))

        records[uid] = rec
    return records


def _read_mech_stat_overlays_from_save() -> dict[int, dict]:
    save_path = os.path.expanduser(
        "~/Library/Application Support/IntoTheBreach/profile_Alpha/saveData.lua"
    )
    try:
        with open(save_path) as f:
            content = f.read()
    except OSError:
        return {}
    return _parse_mech_stat_overlays_from_save_text(content)


def _visual_coord(x: int, y: int) -> str:
    if 0 <= x < 8 and 0 <= y < 8:
        return f"{chr(ord('H') - y)}{8 - x}"
    return "??"


def _unit_visual_coord(unit: dict) -> str:
    try:
        return _visual_coord(int(unit.get("x", -1)), int(unit.get("y", -1)))
    except (TypeError, ValueError):
        return "??"


def _apply_save_mech_stat_overlays(data: dict) -> list[dict]:
    """Patch bridge mech max_hp with saveData effective max_health.

    This is intentionally Python-side so it helps immediately without a game
    restart. It also records calibration requests for pilot screenshots when a
    bridge/base stat disagrees with save-backed effective stats.
    """
    if not isinstance(data, dict):
        return []
    overlays = _read_mech_stat_overlays_from_save()
    if not overlays:
        return []

    updates: list[dict] = []
    calibration: list[dict] = []
    for unit in data.get("units", []) or []:
        if not isinstance(unit, dict) or not unit.get("mech"):
            continue
        try:
            uid = int(unit.get("uid", -1))
        except (TypeError, ValueError):
            continue
        rec = overlays.get(uid)
        if not rec:
            continue
        rec_type = rec.get("type")
        if rec_type and unit.get("type") and rec_type != unit.get("type"):
            continue

        for key in ("pilot_id", "pilot_name", "pilot_name_id", "pilot_level"):
            if rec.get(key) not in (None, ""):
                unit.setdefault(key, rec[key])

        raw_skills = list(unit.get("pilot_skills", []) or [])
        for save_key, label in (
            ("pilot_skill1", "skill1"),
            ("pilot_skill2", "skill2"),
        ):
            val = rec.get(save_key)
            if isinstance(val, int) and val != 0:
                token = f"{label}={val}"
                if token not in raw_skills:
                    raw_skills.append(token)
        if raw_skills:
            unit["pilot_skills"] = raw_skills

        save_max = rec.get("max_hp")
        if not isinstance(save_max, int) or save_max <= 0:
            continue
        old_max = unit.get("max_hp")
        if old_max == save_max:
            continue
        unit["bridge_reported_max_hp"] = old_max
        unit["max_hp"] = save_max
        update = {
            "uid": uid,
            "type": unit.get("type", ""),
            "pos": _unit_visual_coord(unit),
            "bridge_max_hp": old_max,
            "save_max_hp": save_max,
            "pilot_id": unit.get("pilot_id", ""),
            "pilot_name": unit.get("pilot_name", ""),
            "pilot_skills": list(unit.get("pilot_skills", []) or []),
            "health_power": rec.get("health_power"),
        }
        updates.append(update)
        calibration.append({
            **update,
            "reason": "bridge max_hp differed from saveData max_health",
            "capture_hint": "hover/select the visible pilot panel when tactically safe",
        })

    if updates:
        data["mech_stat_overlays"] = updates
    if calibration:
        data["pilot_calibration_requests"] = calibration
    return updates


def _active_region_keys(data: dict) -> list[str]:
    """Return save-region keys that look like the currently live mission."""
    seeds = data.get("mission_seeds") or {}
    if not isinstance(seeds, dict):
        return []
    current_turn = data.get("turn")
    exact: list[str] = []
    active: list[str] = []
    for key, info in seeds.items():
        if not isinstance(info, dict):
            continue
        if info.get("state") != 0:
            continue
        active.append(key)
        if current_turn is None or info.get("turn") == current_turn:
            exact.append(key)
    return exact or active


def _region_blocks(content: str) -> dict[str, str]:
    """Slice saveData.lua into RegionData.regionN blocks."""
    matches = list(re.finditer(r'\["(region\d+)"\]\s*=\s*\{', content))
    blocks: dict[str, str] = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        blocks[match.group(1)] = content[match.start():end]
    return blocks


def _grass_tiles_from_region_blocks(
    blocks: dict[str, str],
    region_keys: set[str],
) -> set[tuple[int, int]]:
    tiles: set[tuple[int, int]] = set()
    for key in region_keys:
        block = blocks.get(key, "")
        for line in block.splitlines():
            loc = re.search(
                r'\["loc"\]\s*=\s*Point\(\s*(\d+)\s*,\s*(\d+)\s*\)',
                line,
            )
            custom = re.search(r'\["custom"\]\s*=\s*"([^"]+)"', line)
            if not loc or not custom:
                continue
            if custom.group(1) == "ground_grass.png":
                tiles.add((int(loc.group(1)), int(loc.group(2))))
    return tiles


def _read_terraform_grass_tiles_from_save(data: dict) -> set[tuple[int, int]]:
    """Read active Mission_Terraform custom grassland tiles from saveData.lua.

    The engine stores grassland as ordinary terrain plus the custom sprite
    ``ground_grass.png``. The bridge terrain id alone reports this as generic
    ground/water/sand, so we supplement the live payload from the active save
    region only.
    """
    if data.get("mission_id") != "Mission_Terraform":
        return set()
    region_keys = set(_active_region_keys(data))
    if not region_keys:
        return set()

    base = os.path.expanduser(
        "~/Library/Application Support/IntoTheBreach/profile_Alpha"
    )
    for filename in ("saveData.lua", "undoSave.lua"):
        try:
            with open(os.path.join(base, filename)) as f:
                content = f.read()
        except OSError:
            continue
        blocks = _region_blocks(content)
        tiles = _grass_tiles_from_region_blocks(blocks, region_keys)
        if tiles:
            return tiles
    return set()


def _safe_to_overlay_save_grass(data: dict) -> bool:
    """Only use save grass at a fresh player-turn boundary.

    saveData.lua does not update after every bridge action. If we overlaid
    save-derived grass mid-turn, a partial re-solve after the Terraformer fired
    could see already-cleared grass as still present.
    """
    if data.get("phase") != "combat_player":
        return False
    actors = [
        u for u in data.get("units", []) or []
        if u.get("team") == 1
        and int(u.get("hp", 0) or 0) > 0
        and u.get("weapons")
    ]
    if not actors:
        return False
    active_count = data.get("active_mechs")
    if active_count is not None:
        try:
            if int(active_count) != len(actors):
                return False
        except (TypeError, ValueError):
            return False
    return all(bool(u.get("active", False)) for u in actors)


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
    queued_target (= piQueuedShot) gives a stale absolute tile. Pair it
    with piOrigin to recover the attack offset: offset = piQueuedShot -
    piOrigin.

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

    Invariant: ``queued_target`` is the tile the attack will hit from the
    unit's current position. The raw bridge value can be piQueuedShot,
    which is relative to piOrigin (attacker's position when queued), not
    current position. If the attacker moved between queueing and firing,
    the target shifts by the same displacement.

    For each unit with a queued_target: look up piOrigin from the save
    file, compute offset = piQueuedShot - piOrigin, then rewrite
    queued_target = current_position + offset. Mutates bridge_units
    in place.
    """
    origins: dict[int, tuple[int, int]] | None = None
    for u in bridge_units:
        if u.get("queued_target_normalized"):
            continue
        qt = u.get("queued_target")
        if not qt or len(qt) != 2:
            continue
        qx, qy = qt[0], qt[1]
        if qx < 0 or qy < 0:
            continue
        origin_payload = u.get("queued_origin")
        origin = None
        if origin_payload and len(origin_payload) == 2:
            origin = (origin_payload[0], origin_payload[1])
        else:
            if origins is None:
                origins = _read_queued_origins_from_save()
            uid = u.get("uid")
            origin = origins.get(uid)
        if origin is None:
            continue
        ox, oy = origin
        # Offset from piOrigin to piQueuedShot. It may be a full same-axis
        # distance for artillery/projectiles; only diagonal offsets are not
        # valid queued line attacks here.
        ddx = qx - ox
        ddy = qy - oy
        if ddx != 0 and ddy != 0:
            continue  # shouldn't happen per game rules
        cx, cy = u.get("x", -1), u.get("y", -1)
        if cx < 0 or cy < 0:
            continue
        # Normalize to the current target tile so solver/replay offset
        # computations match the live board.
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

    if (data.get("mission_id") == "Mission_Terraform"
            and _safe_to_overlay_save_grass(data)):
        grass_tiles = _read_terraform_grass_tiles_from_save(data)
        if grass_tiles:
            data["terraform_grass_tiles"] = [
                [x, y] for x, y in sorted(grass_tiles)
            ]
            for td in data.get("tiles", []):
                pos = (td.get("x"), td.get("y"))
                if pos in grass_tiles:
                    td["grass"] = True
                    td.setdefault("custom", "ground_grass.png")

    # SaveData carries effective mech max_health after pilot perks and powered
    # +Health upgrades. Overlay before Board construction so live reads,
    # verification, and Rust solver payloads agree on true max HP.
    _apply_save_mech_stat_overlays(data)

    try:
        board = Board.from_bridge_data(data)

        # Supplement with conveyor belt data from save file
        # (Python-side fallback until Lua modloader restart picks up native support)
        conveyor_belts = _read_conveyor_belts_from_save()
        if conveyor_belts:
            for x in range(8):
                for y in range(8):
                    board.tile(x, y).conveyor = -1
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
