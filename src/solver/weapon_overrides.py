"""Phase 3 weapon-def override loader.

Reads curated per-field patches from ``data/weapon_overrides.json`` and
injects them into bridge JSON before a solve. Runtime patches can be
passed in alongside for one-off ephemeral overrides. Rust parses these
on the solve boundary (see ``rust_solver/src/serde_bridge.rs``) and
emits ``applied_overrides`` in the solution JSON for audit.
"""
from __future__ import annotations

import json
from dataclasses import replace as _dc_replace
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OVERRIDES_PATH = REPO_ROOT / "data" / "weapon_overrides.json"
DEFAULT_STAGED_PATH = REPO_ROOT / "data" / "weapon_overrides_staged.jsonl"

# Mismatch fields the auto-stager can translate into a concrete override
# patch. Other fields (unknown_weapon, footprint_size, push_arrows,
# passive_*) require human analysis — they get logged + soft-disabled
# but never auto-staged, because the right Rust patch isn't deterministic.
_STAGEABLE_FIELDS = {"damage"}

# Fields the Rust JsonWeaponOverride struct understands. Anything else is
# allowed in the JSON (e.g. free-form "note") but will not round-trip.
_PATCH_FIELDS = (
    "weapon_type", "damage", "damage_outer", "push",
    "self_damage", "range_min", "range_max", "limited", "path_size",
    "flags_set", "flags_clear",
)

_VALID_FLAGS = frozenset({
    "FIRE", "ACID", "FREEZE", "SMOKE", "SHIELD", "WEB",
    "TARGETS_ALLIES", "BUILDING_DAMAGE", "PHASE",
    "AOE_CENTER", "AOE_ADJACENT", "AOE_BEHIND", "AOE_PERP",
    "CHAIN", "CHARGE", "FLYING_CHARGE", "PUSH_SELF",
})


class OverrideSchemaError(ValueError):
    """Raised when an override entry fails structural validation."""


def _validate_entry(entry: dict, source: str) -> None:
    if not isinstance(entry, dict):
        raise OverrideSchemaError(f"{source}: entry must be an object, got {type(entry).__name__}")
    wid = entry.get("weapon_id")
    if not isinstance(wid, str) or not wid:
        raise OverrideSchemaError(f"{source}: weapon_id must be a non-empty string")
    has_patch = False
    for f in _PATCH_FIELDS:
        if f not in entry:
            continue
        has_patch = True
        if f in ("flags_set", "flags_clear"):
            val = entry[f]
            if not isinstance(val, list) or not all(isinstance(s, str) for s in val):
                raise OverrideSchemaError(f"{source}[{wid}]: {f} must be a list of strings")
            unknown = [s for s in val if s.upper() not in _VALID_FLAGS]
            if unknown:
                raise OverrideSchemaError(
                    f"{source}[{wid}]: unknown flag names {unknown!r}; "
                    f"valid flags are {sorted(_VALID_FLAGS)}"
                )
    if not has_patch:
        raise OverrideSchemaError(f"{source}[{wid}]: entry has no patchable fields")


def _sanitize(entry: dict) -> dict:
    """Keep only fields the Rust side parses. Drops free-form metadata
    (note, source_mismatch_ts, reviewer, …) that lives in the file for
    humans but would otherwise travel across the FFI boundary unused."""
    out = {"weapon_id": entry["weapon_id"]}
    for f in _PATCH_FIELDS:
        if f in entry:
            out[f] = entry[f]
    return out


def load_base_overrides(path: Path | str | None = None) -> list[dict]:
    """Load + validate the committed base override layer.

    Missing file → empty list (the common case on clean checkouts).
    Malformed JSON → raises. Any entry that fails validation raises.
    """
    p = Path(path) if path is not None else DEFAULT_OVERRIDES_PATH
    if not p.exists():
        return []
    with p.open() as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise OverrideSchemaError(
            f"{p}: top-level must be a JSON array of override entries"
        )
    entries = []
    for i, entry in enumerate(raw):
        _validate_entry(entry, source=f"{p.name}[{i}]")
        entries.append(_sanitize(entry))
    return entries


# ── Python parity overlay (src.solver.simulate) ──────────────────────────────
#
# Rust is the hot path; Python ``simulate`` is used by tuner replay and parity
# tests. These helpers let the same override entries patch the Python
# ``WEAPON_DEFS`` lookup so both engines agree on effective weapon stats.

# Mapping from Rust-side flag names (uppercase) → Python ``WeaponDef`` field.
_FLAG_FIELD_MAP = {
    "FIRE": "fire", "ACID": "acid", "FREEZE": "freeze", "SMOKE": "smoke",
    "SHIELD": "shield", "WEB": "web", "TARGETS_ALLIES": "targets_allies",
    "BUILDING_DAMAGE": "building_damage", "PHASE": "phase",
    "AOE_CENTER": "aoe_center", "AOE_ADJACENT": "aoe_adjacent",
    "AOE_BEHIND": "aoe_behind", "AOE_PERP": "aoe_perpendicular",
    "CHAIN": "chain", "CHARGE": "charge",
    "FLYING_CHARGE": "flying_charge", "PUSH_SELF": "push_self",
    "SMOKE_BEHIND_SHOOTER": "smoke_behind_shooter",
}


def _patch_weapon_def(base, entry: dict):
    """Apply one override entry onto a ``WeaponDef`` via ``dataclasses.replace``.

    Scalar fields (damage, push, …) map 1:1. ``flags_set`` / ``flags_clear``
    expand into per-field booleans via ``_FLAG_FIELD_MAP``; unknown flag
    names are dropped silently (same policy as Rust).
    """
    updates: dict[str, Any] = {}
    for f in ("weapon_type", "damage", "damage_outer", "push",
              "self_damage", "range_min", "range_max", "limited", "path_size"):
        if f in entry:
            updates[f] = entry[f]
    for name in entry.get("flags_set") or []:
        field = _FLAG_FIELD_MAP.get(name.upper())
        if field is not None:
            updates[field] = True
    for name in entry.get("flags_clear") or []:
        field = _FLAG_FIELD_MAP.get(name.upper())
        if field is not None:
            updates[field] = False
    return _dc_replace(base, **updates)


def apply_runtime(bridge_data: dict) -> None:
    """Install Python-side overlay matching what Rust will see for this solve.

    Reads ``weapon_overrides`` then ``weapon_overrides_runtime`` from
    ``bridge_data`` (base applied first so runtime wins precedence ties)
    and updates ``src.model.weapons._RUNTIME_OVERRIDES`` in place.
    """
    from src.model.weapons import (
        WEAPON_DEFS, ENEMY_WEAPON_DEFS, set_runtime_overrides,
    )
    merged: dict[str, Any] = {}
    for layer in ("weapon_overrides", "weapon_overrides_runtime"):
        for entry in bridge_data.get(layer) or []:
            wid = entry.get("weapon_id")
            if not wid:
                continue
            base = merged.get(wid)
            if base is None:
                base = WEAPON_DEFS.get(wid) or ENEMY_WEAPON_DEFS.get(wid)
            if base is None:
                continue
            merged[wid] = _patch_weapon_def(base, entry)
    set_runtime_overrides(merged)


def clear_runtime() -> None:
    from src.model.weapons import clear_runtime_overrides
    clear_runtime_overrides()


# ── Staging comparator mismatches as override candidates ────────────────────


def _mismatch_to_candidate(mismatch: dict, run_id: str) -> dict | None:
    """Convert one comparator mismatch into a staged-override candidate.

    Only the fields in ``_STAGEABLE_FIELDS`` translate cleanly into a
    Rust patch; anything else returns ``None`` so the caller can skip
    it. ``P3-6``'s CLI promotes these into ``data/weapon_overrides.json``
    entries after a human reviews them.
    """
    field = mismatch.get("field")
    if field not in _STAGEABLE_FIELDS:
        return None
    wid = mismatch.get("weapon_id") or ""
    if not wid:
        return None
    vision_value = mismatch.get("vision_value")
    rust_value = mismatch.get("rust_value")
    try:
        vision_int = int(vision_value)
    except (TypeError, ValueError):
        return None
    return {
        "weapon_id": wid,
        field: vision_int,
        "note": (
            f"comparator: {field} rust={rust_value} vision={vision_value} "
            f"(severity={mismatch.get('severity')}, "
            f"confidence={mismatch.get('confidence')})"
        ),
        "source_run_id": run_id,
        "source_mismatch": {
            "field": field,
            "rust_value": rust_value,
            "vision_value": vision_value,
            "severity": mismatch.get("severity"),
            "confidence": mismatch.get("confidence"),
            "display_name": mismatch.get("display_name"),
        },
    }


def stage_candidates(
    mismatches: Iterable[dict],
    *,
    run_id: str = "",
    path: Path | str | None = None,
    severity_threshold: str = "high",
) -> list[dict]:
    """Append override candidates to ``data/weapon_overrides_staged.jsonl``.

    Only mismatches at or above ``severity_threshold`` with a
    stageable field translate — non-stageable entries (push_arrows,
    footprint_size, unknown_weapon, …) are intentionally skipped
    since there's no deterministic Rust patch to propose.

    Returns the list of candidates that were written so callers can
    surface them in their log line. Zero-writes return an empty list
    and do not touch the file.
    """
    severity_order = {"low": 0, "medium": 1, "high": 2}
    threshold = severity_order.get(severity_threshold, 2)

    staged: list[dict] = []
    for mm in mismatches:
        sev = severity_order.get(mm.get("severity", "low"), 0)
        if sev < threshold:
            continue
        candidate = _mismatch_to_candidate(mm, run_id=run_id)
        if candidate is None:
            continue
        staged.append(candidate)
    if not staged:
        return []

    p = Path(path) if path is not None else DEFAULT_STAGED_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        for c in staged:
            f.write(json.dumps(c) + "\n")
    return staged


def inject_into_bridge(
    bridge_data: dict,
    *,
    base: Iterable[dict] | None = None,
    runtime: Iterable[dict] | None = None,
) -> None:
    """Attach override entries to ``bridge_data`` in place.

    Only fields expected by the Rust deserializer are forwarded; any
    free-form metadata in ``base``/``runtime`` entries is stripped.
    Empty / all-None inputs leave the bridge dict untouched so the
    fast path (no ``applied_overrides`` in the solution) kicks in.
    """
    def _collect(entries: Iterable[dict] | None, source: str) -> list[dict]:
        if entries is None:
            return []
        out: list[dict] = []
        for i, e in enumerate(entries):
            _validate_entry(e, source=f"{source}[{i}]")
            out.append(_sanitize(e))
        return out

    base_entries = _collect(base, "base")
    runtime_entries = _collect(runtime, "runtime")
    if base_entries:
        bridge_data["weapon_overrides"] = base_entries
    if runtime_entries:
        bridge_data["weapon_overrides_runtime"] = runtime_entries
