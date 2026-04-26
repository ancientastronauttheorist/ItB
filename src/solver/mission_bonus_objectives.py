"""Per-mission 'do not kill X' bonus-objective resolver.

Loads ``data/mission_bonus_objectives.json`` and resolves a list of
protected pawn-type substrings for the current mission. Injected into
the Rust solver via ``bridge_data['bonus_objective_unit_types']`` so
the Rust evaluator's mission-aware volatile-kill penalty fires only
when the active mission actually has a 'do not kill X' bonus.

Source-of-truth precedence (highest first):
    1. Bridge data already populated by the Lua modloader (when the
       in-game mission JSON exposes BONUS_PROTECT_X-style entries).
    2. Python-side ``data/mission_bonus_objectives.json`` keyed by
       Lua mission.ID (e.g. 'Mission_VolatileMine').
    3. Empty list = no protection on this mission, evaluator no-ops.

Keeping the resolver here (and OUT of commands.py) means tests can
import it standalone, and unrelated solver call sites
(replay/score_plan) get the same injection logic for free.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = REPO_ROOT / "data" / "mission_bonus_objectives.json"


def load_mission_map(path: Path | None = None) -> dict[str, list[str]]:
    """Load the mission_id -> [protected_type, ...] mapping.

    Keys starting with '_' are treated as comments / metadata and skipped.
    Missing file or malformed JSON returns {} so absence never breaks
    a solve. Values must be lists of non-empty strings; bad entries are
    silently dropped (logged-by-omission).
    """
    p = path or DEFAULT_PATH
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or k.startswith("_"):
            continue
        if not isinstance(v, list):
            continue
        clean = [s for s in v if isinstance(s, str) and s]
        if clean:
            out[k] = clean
    return out


def resolve_bonus_types(
    mission_id: str,
    bridge_data_existing: list[str] | None = None,
    path: Path | None = None,
) -> list[str]:
    """Resolve the list of protected pawn-type substrings for a mission.

    Empty list = no protection (evaluator's volatile_enemy_killed penalty
    no-ops on this mission). The Rust evaluator gates the penalty on a
    non-empty list, so an empty return is correctly treated as 'this
    mission has no do-not-kill bonus'.

    `bridge_data_existing` lets a future Lua-side population win over
    the static Python file. Currently the modloader doesn't emit the
    field, so this is effectively always None and the JSON file is the
    only source — but the precedence is wired now so a later modloader
    bump doesn't need to touch the resolver.
    """
    if bridge_data_existing:
        return list(bridge_data_existing)
    if not mission_id:
        return []
    mapping = load_mission_map(path)
    return list(mapping.get(mission_id, []))


def inject_into_bridge(
    bridge_data: dict[str, Any],
    path: Path | None = None,
) -> list[str]:
    """Resolve and inject `bonus_objective_unit_types` into bridge_data.

    Returns the resolved list (also stored on bridge_data). Idempotent:
    if the bridge already populated the key with a non-empty list, that
    list is preserved (Lua wins over the Python static map).
    """
    existing = bridge_data.get("bonus_objective_unit_types")
    mission_id = bridge_data.get("mission_id") or ""
    resolved = resolve_bonus_types(
        mission_id,
        bridge_data_existing=existing if isinstance(existing, list) else None,
        path=path,
    )
    bridge_data["bonus_objective_unit_types"] = resolved
    return resolved
