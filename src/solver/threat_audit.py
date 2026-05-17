"""Threat coverage audit helpers for live turn execution.

The solver's safety score is authoritative for action choice. This module is
an operator-facing audit layer: it records which pre-turn building threats were
still present just before the End Turn click and why each one appears covered.
"""

from __future__ import annotations

from typing import Any

from src.model.board import Board, Unit
from src.model.pawn_stats import get_pawn_stats


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
    for tx, ty, attacker in board.get_threatened_buildings():
        tile = board.tile(tx, ty)
        out.append({
            "target": [int(tx), int(ty)],
            "target_visual": _visual(int(tx), int(ty)),
            "target_hp": int(tile.building_hp),
            "attacker": _unit_record(attacker),
        })
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
    return out


def _tile_smoke(board: Board, x: int, y: int) -> bool:
    return board.in_bounds(x, y) and bool(getattr(board.tile(x, y), "smoke", False))


def _live_building(board: Board, x: int, y: int) -> bool:
    if not board.in_bounds(x, y):
        return False
    tile = board.tile(x, y)
    return tile.terrain == "building" and tile.building_hp > 0


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
    if not _live_building(board, tx, ty):
        return "target_no_longer_building", "original target is no longer a live building"

    if threat.get("threat_kind") == "hatch_projected_building":
        if attacker.type not in {"WebbEgg1", "SpiderlingEgg1"}:
            return "attacker_transformed", "egg already hatched or changed type"
        dest = _hatch_destination(board, int(attacker.x), int(attacker.y))
        if dest == (tx, ty):
            return "still_threatened_hatch", "egg still hatches onto the building"
        return "hatch_retargeted", "egg hatch fallback no longer selects the building"

    old_pos = attacker_info.get("pos") or [-1, -1]
    moved = [int(attacker.x), int(attacker.y)] != [int(old_pos[0]), int(old_pos[1])]
    current_target = [int(attacker.target_x), int(attacker.target_y)]
    if current_target == [tx, ty]:
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
    """Explain coverage for every initial building threat."""
    threats = initial_threats or []
    entries: list[dict[str, Any]] = []
    still_threatened = 0
    for threat in threats:
        reason, detail = _coverage_reason(threat, board)
        if reason.startswith("still_threatened"):
            still_threatened += 1
        entry = dict(threat)
        entry["coverage"] = {
            "reason": reason,
            "detail": detail,
        }
        entries.append(entry)

    return {
        "status": "WARN" if still_threatened else "OK",
        "initial_threat_count": len(threats),
        "still_threatened_count": still_threatened,
        "entries": entries,
    }
