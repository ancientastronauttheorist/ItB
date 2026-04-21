"""Cross-run weapon penalty log.

``session.failure_events_this_run`` only tracks desyncs within a single run;
``new_run()`` wipes it. That's correct for terrain-specific artifacts (acid
pools, pawn-specific bugs that only surface on one island) but too aggressive
for solver-wide sim bugs that will keep resurfacing.

This module persists a count of confirmed weapon-drift signatures across
runs, keyed by the fuzzy-detector signature (e.g. ``death|Prime_ShieldBash|attack``).
When a new run starts, ``synthetic_prior_events`` lets ``fuzzy_detector.evaluate``
see the historical count as if those desyncs had already fired this run, so
frequency-based soft-disable fires on the FIRST occurrence in the new run
instead of waiting for two more.

The file is a flat JSON dict; small, append-only, safe to delete if it gets
noisy (fresh-start rediscovers bugs in ≤2 turns).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "weapon_penalty_log.json"


def _load() -> dict:
    if not _LOG_PATH.exists():
        return {"version": 1, "signatures": {}}
    try:
        with _LOG_PATH.open() as f:
            data = json.load(f)
        data.setdefault("version", 1)
        data.setdefault("signatures", {})
        return data
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "signatures": {}}


def _save(data: dict) -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _LOG_PATH.with_suffix(".json.tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    tmp.replace(_LOG_PATH)


def record_soft_disable(signature: str, weapon_id: str, run_id: str) -> None:
    """Bump the cross-run count for ``signature`` after a soft-disable fires."""
    if not signature:
        return
    data = _load()
    entry = data["signatures"].setdefault(
        signature,
        {"weapon_id": weapon_id, "count": 0, "last_run_id": ""},
    )
    entry["weapon_id"] = weapon_id or entry.get("weapon_id", "")
    entry["count"] = int(entry.get("count", 0)) + 1
    entry["last_run_id"] = run_id
    _save(data)


def synthetic_prior_events(current_signature_sample_count: int = 0) -> list[dict]:
    """Return synthetic fuzzy-event records that ``_count_matching`` can sum.

    Each recorded signature expands to one dict per historical firing. The
    detector only reads the ``signature`` key, so the dicts are minimal.
    Capped to keep the list bounded even if the log grows unexpectedly.
    """
    data = _load()
    out: list[dict] = []
    for sig, entry in data["signatures"].items():
        count = int(entry.get("count", 0))
        # Cap at 20 per signature so a runaway counter can't blow up memory.
        for _ in range(min(count, 20)):
            out.append({"signature": sig, "cross_run": True})
    return out


def summary() -> dict:
    """Return the log contents for debug / inspection."""
    return _load()
