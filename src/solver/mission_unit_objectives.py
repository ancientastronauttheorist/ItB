"""Per-mission destroy/protect unit-objective resolver.

Some objectives are represented as pawn units rather than objective
building tiles. Mission_Hacking is the first live example: the Hacking
Facility is a shielded enemy unit that must be destroyed, and the Cannon
Bot is reported as ``Snowtank1`` on enemy team until the facility falls.
This module injects explicit unit-objective lists into bridge data so the
Rust evaluator can score those goals without guessing from generic enemy
state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = REPO_ROOT / "data" / "mission_unit_objectives.json"
BONUS_SIMPLE_DEBRIS = 7
BONUS_DEBRIS_OBJECTIVE_TYPE = "BonusDebris"


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [s for s in value if isinstance(s, str) and s]


def load_mission_map(path: Path | None = None) -> dict[str, dict[str, list[str]]]:
    """Load mission_id -> {destroy, protect} from JSON.

    Bad or absent files return {} so objective metadata never breaks a solve.
    Underscore-prefixed keys are comments / schema hints.
    """
    if os.environ.get("ITB_LIGHTNING_SKIP_STATIC_OBJECTIVES") == "1":
        return {}
    p = path or DEFAULT_PATH
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}

    out: dict[str, dict[str, list[str]]] = {}
    for mission_id, value in raw.items():
        if not isinstance(mission_id, str) or mission_id.startswith("_"):
            continue
        if not isinstance(value, dict):
            continue
        destroy = _clean_list(value.get("destroy"))
        protect = _clean_list(value.get("protect"))
        if destroy or protect:
            out[mission_id] = {"destroy": destroy, "protect": protect}
    return out


def resolve_unit_objectives(
    mission_id: str,
    *,
    bridge_destroy_existing: list[str] | None = None,
    bridge_protect_existing: list[str] | None = None,
    path: Path | None = None,
) -> dict[str, list[str]]:
    """Resolve unit-objective lists for a mission.

    Future Lua bridge fields win over the static JSON map independently for
    destroy/protect lists. Empty lists mean no unit objectives of that kind.
    """
    mapping = load_mission_map(path)
    static = mapping.get(mission_id, {}) if mission_id else {}
    destroy = (
        list(bridge_destroy_existing)
        if bridge_destroy_existing
        else list(static.get("destroy", []))
    )
    protect = (
        list(bridge_protect_existing)
        if bridge_protect_existing
        else list(static.get("protect", []))
    )
    return {"destroy": destroy, "protect": protect}


def inject_into_bridge(
    bridge_data: dict[str, Any],
    path: Path | None = None,
) -> dict[str, list[str]]:
    """Inject unit objective lists into bridge_data and return them."""
    mission_id = bridge_data.get("mission_id") or ""
    existing_destroy = bridge_data.get("destroy_objective_unit_types")
    existing_protect = bridge_data.get("protect_objective_unit_types")
    resolved = resolve_unit_objectives(
        mission_id,
        bridge_destroy_existing=(
            existing_destroy if isinstance(existing_destroy, list) else None
        ),
        bridge_protect_existing=(
            existing_protect if isinstance(existing_protect, list) else None
        ),
        path=path,
    )
    bonus_ids = bridge_data.get("bonus_objective_ids") or []
    has_debris_bonus = (
        isinstance(bonus_ids, list)
        and BONUS_SIMPLE_DEBRIS in bonus_ids
    )
    has_bonus_debris_unit = any(
        isinstance(u, dict)
        and u.get("type") == BONUS_DEBRIS_OBJECTIVE_TYPE
        for u in bridge_data.get("units", []) or []
    )
    if (
        has_debris_bonus
        and has_bonus_debris_unit
        and BONUS_DEBRIS_OBJECTIVE_TYPE not in resolved["destroy"]
    ):
        resolved["destroy"].append(BONUS_DEBRIS_OBJECTIVE_TYPE)
    bridge_data["destroy_objective_unit_types"] = resolved["destroy"]
    bridge_data["protect_objective_unit_types"] = resolved["protect"]
    return resolved
