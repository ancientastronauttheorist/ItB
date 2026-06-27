"""Read game state from the Lua bridge and construct a Board.

Replaces save_parser.py as the state source when the bridge is active.
"""

from __future__ import annotations

import json
import os
import re

from src.capture.save_parser import Point, parse_save_file
from src.model.board import Board
from src.bridge.protocol import read_state
from src.itb_paths import get_profile_dir, get_save_file


def _read_save_text(filename: str, profile: str = "Alpha") -> str | None:
    path = get_save_file(filename, profile)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


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
    """Return True iff `mission_id` has `infinite_spawn: true`, is a
    boss mission with turn_limit=null per data/mission_metadata.json, or
    is a missing-metadata Boss mission id.

    Boss missions and Mission_Infinite subclasses have no fixed turn
    limit; the bridge reports total_turns = current_turn so the solver
    sees "final turn" forever and ignores future enemies.
    """
    if not mission_id:
        return False
    md = _load_mission_metadata()
    rec = md.get(mission_id)
    if not isinstance(rec, dict):
        return mission_id.endswith("Boss")
    if rec.get("infinite_spawn"):
        return True
    # Boss missions also have turn_limit=null and grind for many turns.
    if rec.get("boss_mission") and rec.get("turn_limit") is None:
        return True
    return False


def _satellite_launch_danger_tiles(data: dict) -> set[tuple[int, int]]:
    """Return Mission_Satellite launch blast tiles.

    Launch blasts resolve before Vek attacks, but they spare flying pawns.
    Older/current Lua bridge builds expose their adjacent death tiles with
    ``flying_immune=0``. Normalize that bit before solver/audit use.
    """
    if data.get("mission_id") != "Mission_Satellite":
        return set()

    tiles: set[tuple[int, int]] = set()
    for unit in data.get("units", []) or []:
        if not isinstance(unit, dict):
            continue
        if "Satellite" not in str(unit.get("type", "")):
            continue
        if unit.get("hp", 0) <= 0 or not unit.get("queued_launch"):
            continue
        x, y = unit.get("x"), unit.get("y")
        if not isinstance(x, int) or not isinstance(y, int):
            continue
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < 8 and 0 <= ny < 8:
                tiles.add((nx, ny))
    return tiles


def _mark_satellite_launch_danger_flying_immune(data: dict) -> None:
    """Mark satellite launch danger as lethal terrain that spares flyers."""
    launch_tiles = _satellite_launch_danger_tiles(data)
    if not launch_tiles:
        return

    danger = [
        list(entry) if isinstance(entry, tuple) else entry
        for entry in (data.get("environment_danger", []) or [])
    ]
    danger_v2 = [
        list(entry) if isinstance(entry, tuple) else entry
        for entry in (data.get("environment_danger_v2", []) or [])
    ]
    seen_v1 = {
        (entry[0], entry[1])
        for entry in danger
        if isinstance(entry, list) and len(entry) >= 2
    }
    seen_v2: set[tuple[int, int]] = set()

    for entry in danger_v2:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        pos = (entry[0], entry[1])
        seen_v2.add(pos)
        if pos not in launch_tiles:
            continue
        while len(entry) < 5:
            entry.append(0)
        entry[2] = entry[2] if entry[2] else 1
        entry[3] = 1
        entry[4] = 1

    for x, y in sorted(launch_tiles):
        if (x, y) not in seen_v1:
            danger.append([x, y])
        if (x, y) not in seen_v2:
            danger_v2.append([x, y, 1, 1, 1])

    data["environment_danger"] = danger
    data["environment_danger_v2"] = danger_v2


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
    content = _read_save_text("saveData.lua")
    if content is None:
        return {}
    return _parse_conveyor_belts_from_save_text(content)


def _read_active_save_mission() -> dict | None:
    """Return the active mission record from saveData.lua, if resolvable.

    The Lua bridge emits the full island map only between missions. During
    combat, RegionData tells us which GAME.Missions slot is currently being
    fought. SaveData does not update every sub-action, so callers should only
    use static mission metadata or fields where save staleness is acceptable.
    """
    save_path = get_save_file("saveData.lua")
    if not save_path.exists():
        return None
    try:
        data = parse_save_file(save_path)
    except Exception:
        return None

    region_data = data.get("RegionData", {})
    if not isinstance(region_data, dict):
        return None
    battle_region = region_data.get("iBattleRegion", -1)
    if not isinstance(battle_region, int) or battle_region < 0:
        return None
    region = region_data.get(f"region{battle_region}", {})
    if not isinstance(region, dict):
        return None
    mission_slot = region.get("mission", "")
    if not isinstance(mission_slot, str):
        return None
    match = re.fullmatch(r"Mission(\d+)", mission_slot)
    if not match:
        return None

    missions = data.get("GAME", {}).get("Missions", {})
    if not isinstance(missions, dict):
        return None
    mission = missions.get(int(match.group(1)), {})
    return mission if isinstance(mission, dict) else None


def _read_active_bonus_objective_ids_from_save() -> list[int]:
    """Return active mission BonusObjs from saveData.lua."""
    mission = _read_active_save_mission()
    if not isinstance(mission, dict):
        return []
    bonus_objs = mission.get("BonusObjs", {})
    out: list[int] = []
    if isinstance(bonus_objs, dict):
        items = sorted(
            (int(k), v) for k, v in bonus_objs.items()
            if isinstance(k, int) or (isinstance(k, str) and k.isdigit())
        )
        values = [v for _k, v in items]
    elif isinstance(bonus_objs, list):
        values = bonus_objs
    else:
        values = []
    for value in values:
        if isinstance(value, int):
            out.append(value)
    return out


def _read_mission_force_progress_from_save() -> dict:
    """Return Mission_Force mountain-objective progress from saveData.

    Mission_Force stores its visible "Destroy 2 mountains" counter as
    ``mission.Mountains`` and the target as ``mission.MountainsGoal``.
    The bridge may not expose these fields until the game is restarted with a
    newer modloader, so the reader supplements them from saveData at player
    turn boundaries. The live bridge tiles remain authoritative for current
    mountain HP and for same-turn projections.
    """
    mission = _read_active_save_mission()
    if not isinstance(mission, dict):
        return {}
    mission_id = mission.get("ID") or mission.get("Class")
    if mission_id != "Mission_Force":
        return {}
    out: dict = {}
    target = mission.get("MountainsGoal")
    if isinstance(target, int) and target > 0:
        out["mission_mountain_target"] = target
    destroyed = mission.get("Mountains")
    if isinstance(destroyed, int) and destroyed >= 0:
        out["mission_mountains_destroyed"] = destroyed
    return out


def _read_mission_wind_dir_from_save() -> int | None:
    """Return Mission_Wind's live WindDir from saveData, if available."""
    mission = _read_active_save_mission()
    if not isinstance(mission, dict):
        return None
    mission_id = mission.get("ID") or mission.get("Class")
    if mission_id != "Mission_Wind":
        return None
    live_env = mission.get("LiveEnvironment")
    if not isinstance(live_env, dict):
        return None
    wind_dir = live_env.get("WindDir")
    if isinstance(wind_dir, int) and 0 <= wind_dir <= 3:
        return wind_dir
    return None


def _read_freeze_building_objective_tiles_from_save() -> set[tuple[int, int]]:
    """Read Mission_FreezeBldg's static frozen-building objective tiles.

    Live bridge tile.frozen flags tell us which buildings remain frozen after
    each action. SaveData supplies the mission's original Buildings list, which
    is stable enough to use mid-turn and avoids requiring a modloader restart.
    """
    mission = _read_active_save_mission()
    if not isinstance(mission, dict):
        return set()
    mission_id = mission.get("ID") or mission.get("Class")
    if mission_id != "Mission_FreezeBldg":
        return set()
    buildings = mission.get("Buildings", {})
    out: set[tuple[int, int]] = set()
    if isinstance(buildings, dict):
        values = buildings.values()
    elif isinstance(buildings, (list, tuple)):
        values = buildings
    else:
        return out
    for point in values:
        if isinstance(point, Point):
            x, y = point.x, point.y
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            x, y = point[0], point[1]
        else:
            continue
        if isinstance(x, int) and isinstance(y, int) and 0 <= x < 8 and 0 <= y < 8:
            out.add((x, y))
    return out


def _read_freeze_mines_from_save() -> set[tuple[int, int]]:
    """Read freeze mine locations from the save file.

    Fallback for when the bridge modloader hasn't been restarted.
    Returns set of (x, y) bridge coordinates with freeze mines.
    """
    mines = set()
    content = _read_save_text("saveData.lua")
    if content is None:
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
    content = _read_save_text("saveData.lua")
    if content is None:
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

        infected_m = re.search(r'\["bInfected"\]\s*=\s*(true|false)', body)
        if infected_m:
            rec["infected"] = infected_m.group(1) == "true"

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
    for filename in ("saveData.lua", "undoSave.lua"):
        try:
            content = get_save_file(filename, "Alpha").read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        records = _parse_mech_stat_overlays_from_save_text(content)
        if records:
            return records
    return {}


def _active_pilot_skill_values(level: object, skill1: object, skill2: object) -> list[int]:
    """Return level-gated pilot perk IDs from saveData.

    The game uses zero as a real perk ID (``+2 Mech HP``), so slot presence
    must be inferred from pilot level rather than by treating ``0`` as empty.
    """
    try:
        lvl = int(level)
    except (TypeError, ValueError):
        lvl = 0
    values: list[int] = []
    for required_level, skill in ((1, skill1), (2, skill2)):
        if lvl < required_level:
            continue
        try:
            values.append(int(skill))
        except (TypeError, ValueError):
            continue
    return values


def _pilot_skill_max_hp_bonus(skills: list[int]) -> int:
    """Return HP granted by leveled pilot skills visible in saveData.

    Into the Breach stores pilot perks as numeric IDs. The base-game
    ``+2 Mech HP`` perk is 0, and AE ``Skilled`` is 8 (+1 Move, +2 HP).
    """
    bonus = 0
    for skill in skills:
        if skill in {0, 8}:
            bonus += 2
    return bonus


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
        if "infected" in rec:
            unit["infected"] = rec["infected"]

        raw_skills = list(unit.get("pilot_skills", []) or [])
        active_skills = _active_pilot_skill_values(
            rec.get("pilot_level"),
            rec.get("pilot_skill1"),
            rec.get("pilot_skill2"),
        )
        hp_skill_bonus = _pilot_skill_max_hp_bonus(active_skills)
        for label, val in zip(("skill1", "skill2"), active_skills):
            if isinstance(val, int):
                token = f"{label}={val}"
                if token not in raw_skills:
                    raw_skills.append(token)
        if raw_skills:
            unit["pilot_skills"] = raw_skills

        save_max = rec.get("max_hp")
        if not isinstance(save_max, int) or save_max <= 0:
            continue
        old_max = unit.get("max_hp")
        try:
            bridge_max_for_repair = int(old_max or 0)
        except (TypeError, ValueError):
            bridge_max_for_repair = 0
        if (
            data.get("mission_id") == "Mission_Repair"
            and bridge_max_for_repair > 0
            and save_max > bridge_max_for_repair
            and int(rec.get("health_power") or 0) <= 0
        ):
            continue
        if hp_skill_bonus:
            try:
                bridge_max = int(unit.get("max_hp", 0) or 0)
            except (TypeError, ValueError):
                bridge_max = 0
            save_max = max(save_max, bridge_max + hp_skill_bonus)
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

    for filename in ("saveData.lua", "undoSave.lua"):
        content = _read_save_text(filename)
        if content is None:
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
    profile_dir = get_profile_dir("Alpha")
    # saveData.lua first (live), undoSave.lua as fallback (post-restart
    # state where saveData.lua may be absent — observed 2026-04-25).
    for filename in ("saveData.lua", "undoSave.lua"):
        try:
            content = (profile_dir / filename).read_text(
                encoding="utf-8", errors="replace",
            )
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
    content = _read_save_text("saveData.lua")
    if content is None:
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
        u["queued_origin"] = [ox, oy]
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


def _reconcile_flipped_queued_targets_with_targeted_tiles(data: dict) -> None:
    """Trust live attack markers when save-backed queued targets are stale.

    After effects such as Seismic Capacitor's ``DIR_FLIP``, saveData can keep
    the old per-pawn ``piQueuedShot`` even though the visible attack marker has
    already flipped. The bridge also reports Board:IsTargeted() tiles, which are
    live marker data. If a unit's old target is gone from those markers and the
    exact 180-degree mirror is present, rewrite the unit target to that mirror.
    """
    targeted = {
        (int(t[0]), int(t[1]))
        for t in data.get("targeted_tiles", []) or []
        if isinstance(t, (list, tuple)) and len(t) >= 2
    }
    if not targeted:
        return

    for u in data.get("units", []) or []:
        if u.get("team") != 6 or int(u.get("hp") or 0) <= 0:
            continue
        if not u.get("has_queued_attack"):
            continue
        qt = u.get("queued_target")
        if not isinstance(qt, list) or len(qt) < 2:
            continue
        qx, qy = int(qt[0]), int(qt[1])
        if (qx, qy) in targeted:
            continue
        cx, cy = int(u.get("x", -1)), int(u.get("y", -1))
        if not (0 <= cx < 8 and 0 <= cy < 8):
            continue
        fx, fy = 2 * cx - qx, 2 * cy - qy
        if 0 <= fx < 8 and 0 <= fy < 8 and (fx, fy) in targeted:
            u["queued_target_stale_save"] = [qx, qy]
            u["queued_target"] = [fx, fy]
            u["queued_origin"] = [cx, cy]
            u["queued_target_reconciled_via_targeted_tiles"] = True


WEB_SOURCE_WEAPONS = {
    "ScorpionAtk1",
    "ScorpionAtk2",
    "ScorpionAtkB",
    "LeaperAtk1",
    "LeaperAtk2",
    "MosquitoAtkB",
}


def _is_grapple_probe_active(unit: dict) -> bool:
    probes = unit.get("web_probes")
    return isinstance(probes, dict) and probes.get("IsGrappled") is True


def _recover_grapple_probe_webs(bridge_units: list) -> None:
    """Recover current-turn grapples that old bridge fallback code cleared.

    The live Lua bridge probes `IsGrappled()` correctly, but older fallback
    source detection cleared `unit.web` when it did not know a web weapon, which
    missed Mosquito Leader's `MosquitoAtkB`. Preserve the engine probe and infer
    ownership from an alive queued web attack targeting the unit's tile.
    """
    if not bridge_units:
        return

    web_sources_by_target: dict[tuple[int, int], list[dict]] = {}
    for unit in bridge_units:
        if unit.get("team") != 6 or unit.get("hp", 0) <= 0:
            continue
        weapons = unit.get("weapons") or []
        if not weapons or weapons[0] not in WEB_SOURCE_WEAPONS:
            continue
        target = unit.get("queued_target")
        if not isinstance(target, list) or len(target) < 2:
            continue
        web_sources_by_target.setdefault((target[0], target[1]), []).append(unit)

    for unit in bridge_units:
        if not _is_grapple_probe_active(unit):
            continue
        unit["web"] = True
        candidates = web_sources_by_target.get((unit.get("x"), unit.get("y")), [])
        if candidates:
            current_uid = unit.get("web_source_uid")
            if current_uid and any(c.get("uid") == current_uid for c in candidates):
                continue
            unit["web_source_uid"] = candidates[0].get("uid", 0)


def _derive_attack_order_from_units(data: dict) -> None:
    """Prefer the bridge's live unit-list order for queued enemy attacks."""
    order: list[int] = []
    for unit in data.get("units", []) or []:
        if unit.get("team") != 6 or not unit.get("has_queued_attack"):
            continue
        uid = unit.get("uid")
        if isinstance(uid, int):
            order.append(uid)
    if order:
        data["attack_order"] = order


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

    if "bonus_objective_ids" not in data:
        bonus_ids = _read_active_bonus_objective_ids_from_save()
        if bonus_ids:
            data["bonus_objective_ids"] = bonus_ids

    # Rewrite queued_target on each unit using piOrigin from the save file.
    # Bridge modloader currently emits piQueuedShot raw, which gives a
    # non-cardinal delta if the attacker moved after queueing. Fix before
    # constructing the Board so downstream solvers see the right direction.
    if "units" in data:
        _normalize_queued_targets(data["units"])
        _reconcile_flipped_queued_targets_with_targeted_tiles(data)
        _recover_grapple_probe_webs(data["units"])
        _derive_attack_order_from_units(data)
        _mark_satellite_launch_danger_flying_immune(data)

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

    if data.get("mission_id") == "Mission_FreezeBldg":
        freeze_building_tiles = _read_freeze_building_objective_tiles_from_save()
        if freeze_building_tiles:
            data.setdefault("freeze_building_target", 5)
            data["freeze_building_tiles"] = [
                [x, y] for x, y in sorted(freeze_building_tiles)
            ]

    if data.get("mission_id") == "Mission_Force":
        progress = _read_mission_force_progress_from_save()
        if progress:
            data.setdefault(
                "mission_mountain_target",
                progress.get("mission_mountain_target", 2),
            )
            data.setdefault(
                "mission_mountains_destroyed",
                progress.get("mission_mountains_destroyed", 0),
            )
        else:
            data.setdefault("mission_mountain_target", 2)
        mountain_tiles = []
        for td in data.get("tiles", []) or []:
            if not isinstance(td, dict):
                continue
            if td.get("terrain") != "mountain" and td.get("terrain_id") != 4:
                continue
            x, y = td.get("x"), td.get("y")
            if isinstance(x, int) and isinstance(y, int) and 0 <= x < 8 and 0 <= y < 8:
                mountain_tiles.append([x, y])
        data["mission_mountain_tiles"] = mountain_tiles

    if data.get("mission_id") == "Mission_Wind":
        wind_dir = data.get("environment_wind_dir")
        if not isinstance(wind_dir, int) or not (0 <= wind_dir <= 3):
            wind_dir = _read_mission_wind_dir_from_save()
        if isinstance(wind_dir, int) and 0 <= wind_dir <= 3:
            data["environment_wind_dir"] = wind_dir

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
