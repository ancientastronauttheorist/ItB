"""Threat coverage audit helpers for live turn execution.

The solver's safety score is authoritative for action choice. This module is
an operator-facing audit layer: it records which pre-turn building threats were
still present just before the End Turn click and why each one appears covered.
"""

from __future__ import annotations

from typing import Any

from src.model.board import Board, Unit
from src.model.pawn_stats import get_pawn_stats
from src.model.weapons import get_weapon_def


DIRS: tuple[tuple[int, int], ...] = ((0, 1), (1, 0), (0, -1), (-1, 0))
ENGINE_DIR_TO_SOLVER_DIR = {
    0: 2,
    1: 1,
    2: 0,
    3: 3,
}


def _visual(x: int, y: int) -> str:
    return f"{chr(72 - y)}{8 - x}"


def _unit_record(u: Unit) -> dict[str, Any]:
    return {
        "uid": int(u.uid),
        "type": u.type,
        "pos": [int(u.x), int(u.y)],
        "visual": _visual(int(u.x), int(u.y)),
        "hp": int(u.hp),
        "max_hp": int(u.max_hp),
        "weapon_id": u.weapon,
        "target": [int(u.target_x), int(u.target_y)],
        "target_visual": (
            _visual(int(u.target_x), int(u.target_y))
            if u.target_x >= 0 and u.target_y >= 0 else None
        ),
        "queued_target": [int(u.queued_target_x), int(u.queued_target_y)],
        "has_queued_attack": bool(getattr(u, "has_queued_attack", False)),
    }


def _hatch_destination(board: Board, x: int, y: int) -> tuple[int, int] | None:
    """Mirror Rust's live-style spider-egg sPawn fallback order."""
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        hx, hy = x + dx, y + dy
        if not board.in_bounds(hx, hy):
            continue
        if board.unit_at(hx, hy) is not None or board.wreck_at(hx, hy):
            continue
        tile = board.tile(hx, hy)
        if tile.terrain == "building" and tile.building_hp > 0:
            return hx, hy
        if tile.terrain in {"ground", "sand", "forest", "rubble", "fire", "ice"}:
            return hx, hy
    return None


def capture_building_threats(board: Board) -> list[dict[str, Any]]:
    """Capture enemy threats aimed at live buildings in A1-H8 terms."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[int, tuple[int, int]]] = set()
    direct_threat_uids: set[int] = set()
    for tx, ty, attacker in board.get_threatened_buildings():
        tile = board.tile(tx, ty)
        out.append({
            "target": [int(tx), int(ty)],
            "target_visual": _visual(int(tx), int(ty)),
            "target_hp": int(tile.building_hp),
            "attacker": _unit_record(attacker),
        })
        seen.add((int(attacker.uid), (int(tx), int(ty))))
        direct_threat_uids.add(int(attacker.uid))
    for attacker in board.units:
        if attacker.hp <= 0 or attacker.type not in {"WebbEgg1", "SpiderlingEgg1"}:
            continue
        dest = _hatch_destination(board, int(attacker.x), int(attacker.y))
        if dest is None:
            continue
        tx, ty = dest
        tile = board.tile(tx, ty)
        if tile.terrain != "building" or tile.building_hp <= 0:
            continue
        out.append({
            "threat_kind": "hatch_projected_building",
            "target": [int(tx), int(ty)],
            "target_visual": _visual(int(tx), int(ty)),
            "target_hp": int(tile.building_hp),
            "attacker": _unit_record(attacker),
        })
        seen.add((int(attacker.uid), (int(tx), int(ty))))
    for attacker in board.units:
        if attacker.team != 6 or attacker.hp <= 0:
            continue
        if int(attacker.uid) in direct_threat_uids:
            continue
        projected, wind_pos, wind_building = _projected_attack_building_after_wind_for_attacker(
            board, attacker
        )
        if not projected or wind_pos is None or wind_building is None:
            continue
        tx, ty = wind_building
        key = (int(attacker.uid), (tx, ty))
        if key in seen:
            continue
        tile = board.tile(tx, ty)
        out.append({
            "threat_kind": "wind_projected_building",
            "target": [int(tx), int(ty)],
            "target_visual": _visual(int(tx), int(ty)),
            "target_hp": int(tile.building_hp),
            "attacker": _unit_record(attacker),
            "projected_attacker_pos": [int(wind_pos[0]), int(wind_pos[1])],
            "projected_attacker_visual": _visual(int(wind_pos[0]), int(wind_pos[1])),
        })
        seen.add(key)
    return out


def _threat_key(threat: dict[str, Any]) -> tuple[str, int, tuple[int, int]]:
    attacker = threat.get("attacker") or {}
    target = threat.get("target") or [-1, -1]
    try:
        tx, ty = int(target[0]), int(target[1])
    except (TypeError, ValueError, IndexError):
        tx, ty = -1, -1
    try:
        uid = int(attacker.get("uid", -1))
    except (TypeError, ValueError):
        uid = -1
    return (
        str(threat.get("threat_kind") or "building"),
        uid,
        (tx, ty),
    )


def _tile_smoke(board: Board, x: int, y: int) -> bool:
    return board.in_bounds(x, y) and bool(getattr(board.tile(x, y), "smoke", False))


def _live_building(board: Board, x: int, y: int) -> bool:
    if not board.in_bounds(x, y):
        return False
    tile = board.tile(x, y)
    return tile.terrain == "building" and tile.building_hp > 0


def _frozen_building(board: Board, x: int, y: int) -> bool:
    if not _live_building(board, x, y):
        return False
    return bool(getattr(board.tile(x, y), "frozen", False))


def _will_die_to_fire_before_attack(board: Board, attacker: Unit) -> bool:
    """True when the enemy-phase fire tick should kill this attacker first."""
    if not getattr(attacker, "fire", False) or attacker.hp > 1:
        return False
    if getattr(attacker, "shield", False) or getattr(attacker, "frozen", False):
        return False
    if get_pawn_stats(attacker.type).ignore_fire:
        return False
    if (
        attacker.team == 6
        and getattr(board, "fire_psion_active", False)
        and attacker.type != "Jelly_Fire1"
    ):
        return False
    return True


def _unit_takes_fire_tick(board: Board, unit: Unit) -> bool:
    if not getattr(unit, "fire", False):
        return False
    if getattr(unit, "shield", False) or getattr(unit, "frozen", False):
        return False
    if get_pawn_stats(unit.type).ignore_fire:
        return False
    if (
        unit.team == 6
        and getattr(board, "fire_psion_active", False)
        and unit.type != "Jelly_Fire1"
    ):
        return False
    return True


def _fire_tick_kills_unit(board: Board, unit: Unit) -> bool:
    return _unit_takes_fire_tick(board, unit) and unit.hp <= 1


_HEALTH_AURA_SOURCE_TYPES = {"Jelly_Health1", "Jelly_Boss"}


def _health_psion_aura_will_drop_to_fire(board: Board) -> bool:
    live_sources = [
        u for u in board.units
        if u.type in _HEALTH_AURA_SOURCE_TYPES and u.hp > 0
    ]
    if not live_sources:
        return False

    any_source_dies = False
    for source in live_sources:
        if _fire_tick_kills_unit(board, source):
            any_source_dies = True
            continue
        return False
    return any_source_dies


def _will_die_to_soldier_psion_fire_teardown(board: Board, attacker: Unit) -> bool:
    """True when fire drops the health aura and teardown kills attacker."""
    if not _health_psion_aura_will_drop_to_fire(board):
        return False
    if not attacker.receives_psion_aura or attacker.type in _HEALTH_AURA_SOURCE_TYPES:
        return False

    hp_after_fire = attacker.hp - 1 if _unit_takes_fire_tick(board, attacker) else attacker.hp
    return hp_after_fire <= 1


def _will_be_frozen_by_environment_before_attack(board: Board, attacker: Unit) -> bool:
    """True when vanilla Ice Storm should freeze this attacker before it fires."""
    if (int(attacker.x), int(attacker.y)) not in getattr(board, "environment_freeze", set()):
        return False
    if getattr(attacker, "shield", False) or getattr(attacker, "frozen", False):
        return False
    return True


def _lethal_environment_resolves_after_attacks(board: Board) -> bool:
    return getattr(board, "mission_id", "") in {"Mission_Tides", "Mission_Satellite"}


def _will_die_to_lethal_environment_before_attack(board: Board, attacker: Unit) -> bool:
    """True when enemy-phase lethal environment resolves before this attack."""
    if _lethal_environment_resolves_after_attacks(board):
        return False
    pos = (int(attacker.x), int(attacker.y))
    v2 = getattr(board, "environment_danger_v2", {}) or {}
    if pos in v2:
        _damage, lethal = v2[pos]
        flying_immune = pos in (
            getattr(board, "environment_danger_flying_immune", set()) or set()
        )
        if lethal and flying_immune and getattr(attacker, "flying", False):
            return False
        return bool(lethal)
    return pos in (getattr(board, "environment_danger", set()) or set())


def _sign(n: int) -> int:
    return 1 if n > 0 else -1 if n < 0 else 0


def _active_conveyor_mission(board: Board) -> bool:
    return getattr(board, "mission_id", "") in {"Mission_Belt", "Mission_BeltRandom"}


def _conveyor_delta(board: Board, unit: Unit) -> tuple[int, int] | None:
    if not _active_conveyor_mission(board):
        return None
    if not board.in_bounds(int(unit.x), int(unit.y)):
        return None
    raw_dir = int(getattr(board.tile(int(unit.x), int(unit.y)), "conveyor", -1))
    solver_dir = ENGINE_DIR_TO_SOLVER_DIR.get(raw_dir)
    if solver_dir is None:
        return None
    return DIRS[solver_dir]


def _wind_delta(board: Board) -> tuple[int, int] | None:
    if getattr(board, "mission_id", "") != "Mission_Wind":
        return None
    raw_dir = getattr(board, "environment_wind_dir", None)
    if not isinstance(raw_dir, int):
        return None
    solver_dir = ENGINE_DIR_TO_SOLVER_DIR.get(raw_dir)
    if solver_dir is None:
        return None
    return DIRS[solver_dir]


def _unit_can_conveyor_move_to(board: Board, unit: Unit, x: int, y: int) -> bool:
    if not board.in_bounds(x, y):
        return False
    if board.unit_at(x, y) is not None or board.wreck_at(x, y):
        return False
    return board.tile(x, y).terrain not in {"mountain", "building"}


def _unit_clears_before_wind(board: Board, unit: Unit) -> bool:
    return (
        _will_die_to_fire_before_attack(board, unit)
        or _will_die_to_soldier_psion_fire_teardown(board, unit)
        or _will_die_to_lethal_environment_before_attack(board, unit)
    )


def _unit_can_wind_move_to(board: Board, unit: Unit, x: int, y: int) -> bool:
    if not board.in_bounds(x, y):
        return False
    blocker = board.unit_at(x, y)
    if blocker is not None and not _unit_clears_before_wind(board, blocker):
        return False
    if blocker is None and board.wreck_at(x, y):
        return False
    return board.tile(x, y).terrain not in {"mountain", "building"}


def _first_projectile_building_on_line(
    board: Board,
    x: int,
    y: int,
    dx: int,
    dy: int,
) -> tuple[int, int] | None:
    x += dx
    y += dy
    while board.in_bounds(x, y):
        if board.unit_at(x, y) is not None or board.wreck_at(x, y):
            return None
        tile = board.tile(x, y)
        if tile.terrain == "building" and tile.building_hp > 0:
            return x, y
        if tile.terrain == "mountain":
            return None
        x += dx
        y += dy
    return None


def _attack_direction_from_target(
    attacker: Unit,
    old_pos: tuple[int, int] | None = None,
    old_target: tuple[int, int] | None = None,
) -> tuple[int, int] | None:
    ox, oy = old_pos or (int(attacker.x), int(attacker.y))
    if old_target is None:
        tx = int(attacker.queued_target_x)
        ty = int(attacker.queued_target_y)
        if tx < 0 or ty < 0:
            tx = int(attacker.target_x)
            ty = int(attacker.target_y)
    else:
        tx, ty = old_target
    dx = _sign(tx - ox)
    dy = _sign(ty - oy)
    if (dx != 0) == (dy != 0):
        return None
    return dx, dy


def _projected_attack_building_after_wind_for_attacker(
    board: Board,
    attacker: Unit,
    old_pos: tuple[int, int] | None = None,
    old_target: tuple[int, int] | None = None,
) -> tuple[bool, tuple[int, int] | None, tuple[int, int] | None]:
    if (int(attacker.x), int(attacker.y)) not in (
        getattr(board, "environment_danger", set()) or set()
    ):
        return False, None, None
    wind_delta = _wind_delta(board)
    if wind_delta is None:
        return False, None, None

    wx, wy = wind_delta
    nx = int(attacker.x) + wx
    ny = int(attacker.y) + wy
    if not _unit_can_wind_move_to(board, attacker, nx, ny):
        return False, None, None

    attack_delta = _attack_direction_from_target(attacker, old_pos, old_target)
    if attack_delta is None:
        return False, (nx, ny), None
    dx, dy = attack_delta

    wdef = get_weapon_def(attacker.weapon)
    if wdef is None:
        return False, (nx, ny), None

    projected_building: tuple[int, int] | None = None
    if wdef.weapon_type == "projectile":
        projected_building = _first_projectile_building_on_line(board, nx, ny, dx, dy)
    elif wdef.weapon_type == "melee":
        tx, ty = nx + dx, ny + dy
        if _live_building(board, tx, ty):
            projected_building = (tx, ty)
    else:
        return False, (nx, ny), None

    return True, (nx, ny), projected_building


def _projected_attack_building_after_wind(
    threat: dict[str, Any],
    board: Board,
    attacker: Unit,
) -> tuple[bool, tuple[int, int] | None, tuple[int, int] | None]:
    attacker_info = threat.get("attacker") or {}
    old_pos = attacker_info.get("pos") or [-1, -1]
    old_target = attacker_info.get("target") or [-1, -1]
    return _projected_attack_building_after_wind_for_attacker(
        board,
        attacker,
        (int(old_pos[0]), int(old_pos[1])),
        (int(old_target[0]), int(old_target[1])),
    )


def _projected_attack_building_after_conveyor(
    threat: dict[str, Any],
    board: Board,
    attacker: Unit,
) -> tuple[bool, tuple[int, int] | None, tuple[int, int] | None]:
    if getattr(board, "mission_id", "") == "Mission_BeltRandom":
        return False, None, None

    conveyor_delta = _conveyor_delta(board, attacker)
    if conveyor_delta is None:
        return False, None, None

    nx = int(attacker.x) + conveyor_delta[0]
    ny = int(attacker.y) + conveyor_delta[1]
    if not _unit_can_conveyor_move_to(board, attacker, nx, ny):
        return False, None, None

    attacker_info = threat.get("attacker") or {}
    old_pos = attacker_info.get("pos") or [-1, -1]
    old_target = attacker_info.get("target") or [-1, -1]
    dx = _sign(int(old_target[0]) - int(old_pos[0]))
    dy = _sign(int(old_target[1]) - int(old_pos[1]))
    if (dx != 0) == (dy != 0):
        return False, (nx, ny), None

    wdef = get_weapon_def(attacker.weapon)
    if wdef is None:
        return False, (nx, ny), None

    projected_building: tuple[int, int] | None = None
    if wdef.weapon_type == "projectile":
        projected_building = _first_projectile_building_on_line(board, nx, ny, dx, dy)
    elif wdef.weapon_type == "melee":
        tx, ty = nx + dx, ny + dy
        if _live_building(board, tx, ty):
            projected_building = (tx, ty)
    else:
        return False, (nx, ny), None

    return True, (nx, ny), projected_building


def _ordered_prior_enemies(board: Board, attacker: Unit) -> list[Unit]:
    """Return enemies whose queued attacks resolve before ``attacker``."""
    enemies = [u for u in board.units if u.team == 6 and u.hp > 0]
    order = getattr(board, "attack_order", []) or []
    if order:
        positions = {int(uid): i for i, uid in enumerate(order)}
        fallback = len(positions) + 10000
        attacker_pos = positions.get(int(attacker.uid), fallback + int(attacker.uid))
        return [
            u for u in enemies
            if int(u.uid) != int(attacker.uid)
            and positions.get(int(u.uid), fallback + int(u.uid)) < attacker_pos
        ]
    return [u for u in sorted(enemies, key=lambda u: int(u.uid))
            if int(u.uid) < int(attacker.uid)]


def _attacker_can_fire_before_prior_attack(board: Board, other: Unit) -> bool:
    if other.team != 6 or other.hp <= 0:
        return False
    if not getattr(other, "has_queued_attack", False):
        return False
    if other.target_x < 0 or other.target_y < 0:
        return False
    if getattr(other, "frozen", False):
        return False
    if _tile_smoke(board, int(other.x), int(other.y)):
        return False
    if _will_die_to_fire_before_attack(board, other):
        return False
    if _will_die_to_soldier_psion_fire_teardown(board, other):
        return False
    if _will_be_frozen_by_environment_before_attack(board, other):
        return False
    if _will_die_to_lethal_environment_before_attack(board, other):
        return False
    return True


def _weapon_damage_kills_unit(damage: int, unit: Unit) -> bool:
    if damage <= 0:
        return False
    if getattr(unit, "shield", False) or getattr(unit, "frozen", False):
        return False
    actual = int(damage)
    if getattr(unit, "armor", False):
        actual = max(0, actual - 1)
    if getattr(unit, "acid", False):
        actual *= 2
    return actual >= int(unit.hp)


def _projectile_hits_unit_first(
    board: Board,
    shooter: Unit,
    target: Unit,
    dx: int,
    dy: int,
) -> bool:
    x, y = int(shooter.x) + dx, int(shooter.y) + dy
    while board.in_bounds(x, y):
        unit = board.unit_at(x, y)
        if unit is not None:
            return int(unit.uid) == int(target.uid)
        if board.wreck_at(x, y):
            return False
        tile = board.tile(x, y)
        if tile.terrain in {"mountain", "building"} and getattr(tile, "building_hp", 0) > 0:
            return False
        x += dx
        y += dy
    return False


def _will_die_to_prior_projectile_before_attack(board: Board, attacker: Unit) -> tuple[bool, str]:
    """True when an earlier enemy projectile kills this attacker first."""
    for other in _ordered_prior_enemies(board, attacker):
        if not _attacker_can_fire_before_prior_attack(board, other):
            continue
        wdef = get_weapon_def(other.weapon)
        if wdef is None or wdef.weapon_type != "projectile":
            continue

        dx = _sign(int(other.target_x) - int(other.x))
        dy = _sign(int(other.target_y) - int(other.y))
        if (dx != 0) == (dy != 0):
            continue

        dirs = [(dx, dy)]
        if other.weapon == "FireflyAtkB":
            dirs.append((-dx, -dy))
        for pdx, pdy in dirs:
            if not _projectile_hits_unit_first(board, other, attacker, pdx, pdy):
                continue
            if _weapon_damage_kills_unit(int(wdef.damage), attacker):
                return (
                    True,
                    f"earlier {other.type} uid={int(other.uid)} projectile "
                    f"hits attacker before it fires",
                )

    return False, ""


def _will_die_to_prior_melee_before_attack(board: Board, attacker: Unit) -> tuple[bool, str]:
    """True when an earlier enemy melee attack kills this attacker first."""
    for other in _ordered_prior_enemies(board, attacker):
        if not _attacker_can_fire_before_prior_attack(board, other):
            continue
        wdef = get_weapon_def(other.weapon)
        if wdef is None or wdef.weapon_type != "melee":
            continue
        if getattr(other, "weapon_target_behind", False):
            continue

        dx = _sign(int(other.target_x) - int(other.x))
        dy = _sign(int(other.target_y) - int(other.y))
        if (dx != 0) == (dy != 0):
            continue

        tx = int(other.x) + dx
        ty = int(other.y) + dy
        if (tx, ty) != (int(attacker.x), int(attacker.y)):
            continue

        damage = int(getattr(other, "weapon_damage", 0) or 0) or int(wdef.damage)
        if _weapon_damage_kills_unit(damage, attacker):
            return (
                True,
                f"earlier {other.type} uid={int(other.uid)} melee "
                f"hits attacker before it fires",
            )

    return False, ""


def _will_die_to_prior_artillery_before_attack(board: Board, attacker: Unit) -> tuple[bool, str]:
    """True when an earlier enemy artillery shot lands on this attacker."""
    for other in _ordered_prior_enemies(board, attacker):
        if not _attacker_can_fire_before_prior_attack(board, other):
            continue
        wdef = get_weapon_def(other.weapon)
        if wdef is None or wdef.weapon_type != "artillery":
            continue
        if [int(other.target_x), int(other.target_y)] != [
            int(attacker.x), int(attacker.y)
        ]:
            continue
        if _weapon_damage_kills_unit(int(wdef.damage), attacker):
            return (
                True,
                f"earlier {other.type} uid={int(other.uid)} artillery "
                f"hits attacker before it fires",
            )

    return False, ""


def _push_destination_is_open(board: Board, unit: Unit, x: int, y: int) -> bool:
    if not board.in_bounds(x, y):
        return False
    if board.unit_at(x, y) is not None or board.wreck_at(x, y):
        return False
    terrain = board.tile(x, y).terrain
    return terrain not in {"mountain", "building"}


def _will_die_to_prior_bump_before_attack(board: Board, attacker: Unit) -> tuple[bool, str]:
    """True when an earlier enemy attack should bump-kill this attacker.

    This is intentionally narrow. It covers the live Bouncer self-push case:
    a lower-UID Bouncer attacks, jumps backward one tile, bumps into a 1 HP
    later attacker, and kills it before that later attacker can hit a building.
    """
    if attacker.hp > 1 or getattr(attacker, "shield", False) or getattr(attacker, "frozen", False):
        return False, ""

    for other in _ordered_prior_enemies(board, attacker):
        if other.weapon not in {"BouncerAtk1", "BouncerAtk2"}:
            continue
        if not _attacker_can_fire_before_prior_attack(board, other):
            continue

        dx = _sign(int(other.target_x) - int(other.x))
        dy = _sign(int(other.target_y) - int(other.y))
        if (dx != 0) == (dy != 0):
            continue

        # BouncerAtk1/2 self-pushes one tile opposite the queued attack dir.
        bx = int(other.x) - dx
        by = int(other.y) - dy
        if bx == int(attacker.x) and by == int(attacker.y):
            return (
                True,
                f"earlier {other.type} uid={int(other.uid)} self-bumps into attacker",
            )

    return False, ""


def _will_be_moved_by_prior_attack_before_attack(board: Board, attacker: Unit) -> tuple[bool, str]:
    """True when an earlier enemy attack pushes this attacker before it fires."""
    if (
        not getattr(attacker, "pushable", True)
        or getattr(attacker, "shield", False)
        or getattr(attacker, "frozen", False)
    ):
        return False, ""

    push_weapons = {
        "MothAtk1": "earlier Moth artillery pushes attacker before its attack",
        "MothAtk2": "earlier Moth artillery pushes attacker before its attack",
        "BouncerAtk1": "earlier Bouncer horn pushes attacker before its attack",
        "BouncerAtk2": "earlier Bouncer horn pushes attacker before its attack",
    }
    for other in _ordered_prior_enemies(board, attacker):
        detail = push_weapons.get(other.weapon)
        if detail is None:
            continue
        if [int(other.target_x), int(other.target_y)] != [int(attacker.x), int(attacker.y)]:
            continue
        if not _attacker_can_fire_before_prior_attack(board, other):
            continue

        dx = _sign(int(other.target_x) - int(other.x))
        dy = _sign(int(other.target_y) - int(other.y))
        if (dx != 0) == (dy != 0):
            continue
        nx = int(attacker.x) + dx
        ny = int(attacker.y) + dy
        if _push_destination_is_open(board, attacker, nx, ny):
            return True, f"{detail} to {_visual(nx, ny)}"

    return False, ""


def _coverage_reason(threat: dict[str, Any], board: Board) -> tuple[str, str]:
    attacker_info = threat.get("attacker") or {}
    uid = attacker_info.get("uid")
    target = threat.get("target") or [-1, -1]
    tx, ty = int(target[0]), int(target[1])
    attacker = next((u for u in board.units if int(u.uid) == uid), None)

    if attacker is None or attacker.hp <= 0:
        return "attacker_killed", "attacker is dead or absent"
    if getattr(attacker, "frozen", False):
        return "attacker_frozen", "attacker is frozen"
    if _tile_smoke(board, int(attacker.x), int(attacker.y)):
        return "attacker_smoked", "attacker is standing in smoke"
    if _will_die_to_fire_before_attack(board, attacker):
        return "attacker_will_die_to_fire", "attacker will burn before attacking"
    if _will_die_to_soldier_psion_fire_teardown(board, attacker):
        return (
            "attacker_will_die_to_soldier_psion_teardown",
            "Soldier Psion burns before attacks and HP-aura teardown kills attacker",
        )
    if _will_be_frozen_by_environment_before_attack(board, attacker):
        return (
            "attacker_will_be_frozen_by_environment",
            "Ice Storm freezes attacker before enemy attacks",
        )
    if _will_die_to_lethal_environment_before_attack(board, attacker):
        return (
            "attacker_will_die_to_environment",
            "lethal environment kills attacker before enemy attacks",
        )
    if not _live_building(board, tx, ty):
        return "target_no_longer_building", "original target is no longer a live building"

    if threat.get("threat_kind") == "hatch_projected_building":
        if attacker.type not in {"WebbEgg1", "SpiderlingEgg1"}:
            return "attacker_transformed", "egg already hatched or changed type"
        dest = _hatch_destination(board, int(attacker.x), int(attacker.y))
        if dest == (tx, ty):
            return "still_threatened_hatch", "egg still hatches onto the building"
        return "hatch_retargeted", "egg hatch fallback no longer selects the building"

    bumped, bump_detail = _will_die_to_prior_bump_before_attack(board, attacker)
    if bumped:
        return "attacker_will_die_to_prior_bump", bump_detail
    projectile_kill, projectile_detail = _will_die_to_prior_projectile_before_attack(
        board, attacker
    )
    if projectile_kill:
        return "attacker_will_die_to_prior_projectile", projectile_detail
    melee_kill, melee_detail = _will_die_to_prior_melee_before_attack(
        board, attacker
    )
    if melee_kill:
        return "attacker_will_die_to_prior_melee", melee_detail
    artillery_kill, artillery_detail = _will_die_to_prior_artillery_before_attack(
        board, attacker
    )
    if artillery_kill:
        return "attacker_will_die_to_prior_artillery", artillery_detail
    moved_by_prior, moved_detail = _will_be_moved_by_prior_attack_before_attack(board, attacker)
    if moved_by_prior:
        return "attacker_will_be_moved_by_prior_attack", moved_detail

    wind_projected, wind_pos, wind_building = (
        _projected_attack_building_after_wind(threat, board, attacker)
    )
    if wind_projected:
        assert wind_pos is not None
        if wind_building is None:
            return (
                "attacker_will_be_moved_by_wind",
                "Mission_Wind pushes attacker to "
                f"{_visual(wind_pos[0], wind_pos[1])} before attacks",
            )
        return (
            "still_threatened_after_wind",
            "Mission_Wind pushes attacker to "
            f"{_visual(wind_pos[0], wind_pos[1])}, still hitting "
            f"{_visual(wind_building[0], wind_building[1])}",
        )

    conveyor_projected, conveyor_pos, conveyor_building = (
        _projected_attack_building_after_conveyor(threat, board, attacker)
    )
    if conveyor_projected:
        assert conveyor_pos is not None
        if conveyor_building is None:
            return (
                "attacker_will_be_moved_by_conveyor",
                "conveyor moves attacker to "
                f"{_visual(conveyor_pos[0], conveyor_pos[1])} before attacks",
            )
        if _frozen_building(board, conveyor_building[0], conveyor_building[1]):
            return (
                "target_frozen_building_after_conveyor",
                "conveyor moves attacker to "
                f"{_visual(conveyor_pos[0], conveyor_pos[1])}, but target "
                f"{_visual(conveyor_building[0], conveyor_building[1])} is frozen",
            )
        return (
            "still_threatened_after_conveyor",
            "conveyor moves attacker to "
            f"{_visual(conveyor_pos[0], conveyor_pos[1])}, still hitting "
            f"{_visual(conveyor_building[0], conveyor_building[1])}",
        )

    old_pos = attacker_info.get("pos") or [-1, -1]
    moved = [int(attacker.x), int(attacker.y)] != [int(old_pos[0]), int(old_pos[1])]
    current_target = [int(attacker.target_x), int(attacker.target_y)]
    if current_target == [tx, ty]:
        if _frozen_building(board, tx, ty):
            return "target_frozen_building", "target building is frozen and will thaw"
        if moved:
            return "still_threatened_after_move", "attacker moved but still targets the building"
        return "still_threatened", "attacker still targets the building"

    if attacker.target_x < 0 or attacker.target_y < 0:
        return "attack_cleared", "attacker has no queued building target"
    if not _live_building(board, int(attacker.target_x), int(attacker.target_y)):
        return "retargeted_nonbuilding", "attacker target is no longer a live building"
    if moved:
        return "attacker_moved", "attacker moved and no longer targets the original building"
    return "retargeted_building", "attacker now targets a different live building"


def audit_threat_coverage(
    initial_threats: list[dict[str, Any]] | None,
    board: Board,
) -> dict[str, Any]:
    """Explain coverage for solve-time threats and block new live threats."""
    threats = initial_threats or []
    entries: list[dict[str, Any]] = []
    still_threatened = 0
    seen_threats: set[tuple[str, int, tuple[int, int]]] = set()
    for threat in threats:
        seen_threats.add(_threat_key(threat))
        reason, detail = _coverage_reason(threat, board)
        if reason.startswith("still_threatened"):
            still_threatened += 1
        entry = dict(threat)
        entry["coverage"] = {
            "reason": reason,
            "detail": detail,
        }
        entries.append(entry)

    current_threats = capture_building_threats(board)
    new_current_threats = [
        threat for threat in current_threats if _threat_key(threat) not in seen_threats
    ]
    for threat in new_current_threats:
        reason, detail = _coverage_reason(threat, board)
        if reason.startswith("still_threatened"):
            still_threatened += 1
            reason = "still_threatened_current"
            detail = (
                "current live building threat was not in the solve-time audit set"
            )
        entry = dict(threat)
        entry["coverage"] = {
            "reason": reason,
            "detail": detail,
        }
        entries.append(entry)

    return {
        "status": "WARN" if still_threatened else "OK",
        "initial_threat_count": len(threats),
        "current_threat_count": len(current_threats),
        "new_current_threat_count": len(new_current_threats),
        "still_threatened_count": still_threatened,
        "entries": entries,
    }
