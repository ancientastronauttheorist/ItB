"""Synchronize local achievement metadata from Steam achievement status."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ACHIEVEMENTS_PATH = ROOT / "data" / "achievements_detailed.json"
STEAM_LIBRARYCACHE_ROOT = (
    Path.home() / "Library" / "Application Support" / "Steam" / "userdata"
)


_QUOTE_TRANSLATION = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
})


def canonical_achievement_name(name: str | None) -> str:
    """Normalize display names enough for Steam/local metadata matching."""
    text = (name or "").translate(_QUOTE_TRANSLATION).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def steam_display_name(entry: dict[str, Any]) -> str:
    """Return the human achievement name from a Steam API row."""
    return str(
        entry.get("name")
        or entry.get("displayName")
        or entry.get("apiname")
        or ""
    ).strip()


def _achievement_key(entry: dict[str, Any]) -> str:
    apiname = str(entry.get("apiname") or entry.get("strID") or "").strip()
    if apiname:
        return f"id:{apiname}"
    return f"name:{canonical_achievement_name(steam_display_name(entry))}"


def load_steam_client_achievement_cache(
    app_id: str = "590380",
    *,
    root: str | Path = STEAM_LIBRARYCACHE_ROOT,
) -> dict[str, Any]:
    """Read fresher achievement flags from Steam's local library cache.

    The public Steam Web API can lag immediately after an unlock. The local
    client cache updates quickly enough to confirm newly awarded achievements.
    """
    root = Path(root)
    paths = sorted(root.glob(f"*/config/librarycache/{app_id}.json"))
    if not paths:
        return {"path": None, "achievements": [], "n_total": 0, "n_achieved": 0}

    newest = max(paths, key=lambda p: p.stat().st_mtime)
    raw = json.loads(newest.read_text())
    sections = dict(raw) if isinstance(raw, list) else {}
    achievements_section = sections.get("achievements", {})
    data = achievements_section.get("data", {}) if isinstance(achievements_section, dict) else {}

    rows: list[dict[str, Any]] = []
    for source_key in ("vecHighlight", "vecUnachieved", "vecAchievedHidden"):
        for entry in data.get(source_key, []) or []:
            if not isinstance(entry, dict):
                continue
            rows.append({
                "apiname": entry.get("strID"),
                "name": entry.get("strName"),
                "achieved": 1 if entry.get("bAchieved") else 0,
                "unlocktime": entry.get("rtUnlocked", 0),
                "source": "steam_client_cache",
            })

    return {
        "path": str(newest),
        "achievements": rows,
        "n_total": int(data.get("nTotal") or 0),
        "n_achieved": int(data.get("nAchieved") or 0),
    }


def merge_steam_client_cache(
    steam_achievements: list[dict[str, Any]],
    client_cache: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge local Steam client achieved flags into Web API achievement rows."""
    merged = [dict(entry) for entry in steam_achievements]
    by_key = {_achievement_key(entry): entry for entry in merged}
    client_rows = client_cache.get("achievements") or []
    marked = 0

    for client in client_rows:
        if client.get("achieved") != 1:
            continue
        keys = [
            _achievement_key(client),
            f"name:{canonical_achievement_name(steam_display_name(client))}",
        ]
        target = next((by_key[key] for key in keys if key in by_key), None)
        if target is None:
            continue
        if target.get("achieved") != 1:
            marked += 1
        target["achieved"] = 1
        if client.get("unlocktime"):
            target["unlocktime"] = client["unlocktime"]
        if client.get("name") and not target.get("name"):
            target["name"] = client["name"]

    summary = {
        "path": client_cache.get("path"),
        "client_total": client_cache.get("n_total", 0),
        "client_achieved": client_cache.get("n_achieved", 0),
        "local_flags_promoted": marked,
    }
    return merged, summary


def sync_achievement_details(
    steam_achievements: list[dict[str, Any]],
    *,
    path: str | Path = ACHIEVEMENTS_PATH,
    synced_at: str | None = None,
) -> dict[str, Any]:
    """Update ``completed`` flags in achievements_detailed.json.

    Steam returns human display names when queried with ``l=en``. The local
    detailed achievement file is keyed by those same names inside squad/global
    groups, so display-name matching is the least brittle sync path.
    """
    path = Path(path)
    payload = json.loads(path.read_text())
    groups = payload.get("achievements", {})
    if not isinstance(groups, dict):
        raise ValueError(f"{path}: expected top-level achievements object")

    steam_by_name: dict[str, dict[str, Any]] = {}
    for entry in steam_achievements:
        key = canonical_achievement_name(steam_display_name(entry))
        if key:
            steam_by_name[key] = entry

    matched = 0
    status_changed = 0
    unmatched_local: list[str] = []

    for achievements in groups.values():
        if not isinstance(achievements, list):
            continue
        for local in achievements:
            if not isinstance(local, dict):
                continue
            name = str(local.get("name", "")).strip()
            key = canonical_achievement_name(name)
            steam = steam_by_name.get(key)
            if steam is None:
                if name:
                    unmatched_local.append(name)
                continue
            matched += 1
            completed = steam.get("achieved") == 1
            if bool(local.get("completed")) != completed:
                status_changed += 1
            local["completed"] = completed

    unlocked = sum(1 for a in steam_achievements if a.get("achieved") == 1)
    meta = payload.setdefault("meta", {})
    meta["last_steam_sync"] = synced_at or datetime.now().isoformat()
    meta["last_steam_total"] = len(steam_achievements)
    meta["last_steam_unlocked"] = unlocked

    tmp_path = path.parent / f".tmp.{os.getpid()}.{path.name}"
    with tmp_path.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    os.replace(tmp_path, path)

    completed_total = 0
    local_total = 0
    for achievements in groups.values():
        if not isinstance(achievements, list):
            continue
        for local in achievements:
            if isinstance(local, dict) and local.get("name"):
                local_total += 1
                completed_total += int(bool(local.get("completed")))

    return {
        "path": str(path),
        "steam_total": len(steam_achievements),
        "steam_unlocked": unlocked,
        "local_total": local_total,
        "local_completed": completed_total,
        "matched": matched,
        "status_changed": status_changed,
        "unmatched_local": unmatched_local,
    }
