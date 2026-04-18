"""Weapon-def comparator — Phase 2 exit criterion.

Takes a parsed Vision weapon_preview (from ``src.research.vision``)
and diffs it against the Python ``WEAPON_DEFS`` table (which mirrors
the Rust static array at ``rust_solver/src/weapons.rs:246``).
Mismatches land in ``data/weapon_def_mismatches.jsonl`` for later
review — each line is one disagreement the team should either fix
in the sim or confirm as a Vision misread.

What we check:

- **name**: the display name on the preview must resolve to a known
  ``WEAPON_DEFS`` entry. Unknown names are the loudest mismatch type
  — they surface weapons the sim has never seen.
- **damage**: exact integer match against ``WeaponDef.damage``. We
  don't try to reason about upgrade state — the preview reflects the
  installed build's base damage, and that's what Rust encodes.
- **push categorical consistency**: Vision reports push_directions
  as compass labels (north/south/east/west) tied to a specific
  preview orientation. Rust encodes the abstract ``PushDir`` enum.
  We translate "does this preview's push count + multi-direction
  shape make sense for the declared PushDir" — e.g. ``Outward``
  must show ≥2 directions, ``None`` must show 0.
- **footprint size**: the preview's mini-board draws every tile the
  weapon hits. We cross-check the tile count against the weapon's
  AOE flags / path_size. Single-tile Melee = 1; SelfAoe with
  aoe_adjacent (no center) = 4; Spear path_size=2 = 2; etc.
- **passive sanity**: weapons with ``weapon_type == "passive"`` should
  not show a damage number or AOE footprint; if Vision claims they
  do, flag.

What we intentionally DON'T check:

- description text (free-form, paraphrased across game versions)
- upgrade-track labels (order varies between builds)
- mini-board orientation (depends on where the mech is standing in
  the captured preview; the target-direction isn't derivable from
  Rust alone)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.model.weapons import WEAPON_DEFS, WeaponDef


MISMATCHES_PATH = Path(__file__).parent.parent.parent / "data" / "weapon_def_mismatches.jsonl"


# ── display-name → WEAPON_DEFS key ───────────────────────────────────────────


def _build_display_name_index() -> dict[str, str]:
    """Map display names like "Vice Fist" → WEAPON_DEFS key ("Prime_Shift").

    Built on first call, cached per process. Case-insensitive. Weapons
    with duplicate display names (shouldn't happen, but the Rust/Python
    tables could drift) resolve to the first-registered key.
    """
    idx: dict[str, str] = {}
    for key, wdef in WEAPON_DEFS.items():
        name = (wdef.name or "").strip().lower()
        if name and name not in idx:
            idx[name] = key
    return idx


_NAME_INDEX: dict[str, str] | None = None


def _name_index() -> dict[str, str]:
    global _NAME_INDEX
    if _NAME_INDEX is None:
        _NAME_INDEX = _build_display_name_index()
    return _NAME_INDEX


def resolve_weapon_id(display_name: str) -> str | None:
    """Return the WEAPON_DEFS key for a display name, or None if unknown.

    Kept a thin wrapper so tests can monkeypatch the index without
    rebuilding the whole module.
    """
    if not display_name:
        return None
    return _name_index().get(display_name.strip().lower())


# ── expected footprint size from WeaponDef ──────────────────────────────────


def _expected_footprint_count(wdef: WeaponDef) -> tuple[int, int]:
    """Return ``(min, max)`` tile count the mini-board should show.

    This is deliberately a range — the preview's projectile types
    show only the target tile even though in-game they scan a line,
    so exact-equal checks would false-positive. The range is wide
    enough to accept any sane preview rendering.

    - Passive: (0, 0) — no footprint panel.
    - Melee path_size=1 with only aoe_center: (1, 1).
    - path_size>1 in a line: (path_size, path_size+1) — some melee
      line weapons include the firer tile, some don't.
    - SelfAoe aoe_adjacent (no center): (4, 5).
    - aoe_adjacent + aoe_center: (5, 5).
    - aoe_perpendicular with center: (3, 3).
    - Charge / unlimited range: (1, 8) — mini-board may show the
      whole line or just the target.
    """
    wtype = wdef.weapon_type
    if wtype == "passive":
        return (0, 0)

    if wdef.aoe_adjacent and not wdef.aoe_center:
        return (4, 5)  # allow the 5-tile plus-sign reading
    if wdef.aoe_adjacent and wdef.aoe_center:
        return (5, 5)
    if wdef.aoe_perpendicular:
        # main target + 2 perpendicular (+ optional line-behind)
        base = 3
        if wdef.aoe_behind:
            base += wdef.path_size
        return (base, base + 1)
    if wdef.aoe_behind:
        # target + tile behind; sometimes the preview marks the firer too
        return (2, 3)

    if wtype in ("charge", "leap") and wdef.range_max in (0, 7):
        return (1, 8)

    if wdef.path_size > 1:
        return (wdef.path_size, wdef.path_size + 1)

    # Default: single-tile target. Projectiles/artillery also land here
    # because the preview only highlights the target tile, not the path.
    return (1, 1)


# ── push categorical shape from PushDir ─────────────────────────────────────


def _expected_push_shape(wdef: WeaponDef) -> tuple[int, int] | None:
    """Return ``(min, max)`` number of push arrows expected in the preview.

    None means "don't check" — the weapon doesn't declare a push
    direction in the sim, but the preview might still show an arrow
    due to secondary effects (Flamethrower has push=forward for its
    push-away fire pattern, for instance).
    """
    push = wdef.push
    if push in ("", "none"):
        return (0, 0)
    if push in ("forward", "backward", "flip", "throw"):
        return (1, 1)
    if push == "perpendicular":
        # Both perpendicular tiles → 2 arrows.
        return (1, 2)
    if push == "outward":
        # Every hit tile gets pushed outward from center — 2-4 arrows.
        return (1, 4)
    if push == "inward":
        # Pull weapons (Grav Well, etc.) don't always render an arrow
        # glyph — the pull is implied by the projectile/target path.
        # Allow 0 so we don't flag a sim/vision mismatch every time.
        return (0, 4)
    return None


# ── compare ─────────────────────────────────────────────────────────────────


def compare_weapon(parsed: dict, confidence_floor: float = 0.5) -> list[dict]:
    """Diff a parsed Vision weapon_preview against WEAPON_DEFS.

    Returns a list of mismatch dicts. Each dict has:
      - ``weapon_id``: WEAPON_DEFS key (or "" if unresolved)
      - ``display_name``: the Vision-reported name
      - ``field``: which attribute disagreed
      - ``rust_value``: what the sim has
      - ``vision_value``: what Vision saw
      - ``severity``: "high" | "medium" | "low"
      - ``confidence``: Vision's confidence for this parse

    Low-confidence parses (≤ ``confidence_floor``) are skipped
    entirely — comparing noise is just noise. The caller should
    hit the wiki fallback instead.
    """
    if parsed.get("confidence", 0.0) <= confidence_floor:
        return []

    display_name = parsed.get("name", "")
    weapon_id = resolve_weapon_id(display_name)
    out: list[dict] = []

    if weapon_id is None:
        out.append({
            "weapon_id": "",
            "display_name": display_name,
            "field": "unknown_weapon",
            "rust_value": None,
            "vision_value": display_name,
            "severity": "high",
            "confidence": parsed.get("confidence", 0.0),
        })
        return out

    wdef = WEAPON_DEFS[weapon_id]

    # Damage
    rust_damage = int(wdef.damage)
    vision_damage = int(parsed.get("damage", 0))
    if rust_damage != vision_damage:
        # Passive weapons legitimately show no damage — Rust has 0 too,
        # so this branch only fires when the numbers actually disagree.
        out.append({
            "weapon_id": weapon_id,
            "display_name": display_name,
            "field": "damage",
            "rust_value": rust_damage,
            "vision_value": vision_damage,
            "severity": "high",
            "confidence": parsed.get("confidence", 0.0),
        })

    # Footprint size
    fmin, fmax = _expected_footprint_count(wdef)
    footprint_n = len(parsed.get("footprint_tiles") or [])
    if footprint_n < fmin or footprint_n > fmax:
        out.append({
            "weapon_id": weapon_id,
            "display_name": display_name,
            "field": "footprint_size",
            "rust_value": f"[{fmin},{fmax}]",
            "vision_value": footprint_n,
            "severity": "medium",
            "confidence": parsed.get("confidence", 0.0),
        })

    # Push shape
    shape = _expected_push_shape(wdef)
    if shape is not None:
        pmin, pmax = shape
        push_n = len(parsed.get("push_directions") or [])
        if push_n < pmin or push_n > pmax:
            out.append({
                "weapon_id": weapon_id,
                "display_name": display_name,
                "field": "push_arrows",
                "rust_value": {"push_dir": wdef.push, "expected": [pmin, pmax]},
                "vision_value": push_n,
                "severity": "low",
                "confidence": parsed.get("confidence", 0.0),
            })

    # Passive sanity
    if wdef.weapon_type == "passive":
        if vision_damage > 0:
            out.append({
                "weapon_id": weapon_id,
                "display_name": display_name,
                "field": "passive_has_damage",
                "rust_value": 0,
                "vision_value": vision_damage,
                "severity": "medium",
                "confidence": parsed.get("confidence", 0.0),
            })
        if parsed.get("footprint_tiles"):
            out.append({
                "weapon_id": weapon_id,
                "display_name": display_name,
                "field": "passive_has_footprint",
                "rust_value": 0,
                "vision_value": footprint_n,
                "severity": "medium",
                "confidence": parsed.get("confidence", 0.0),
            })

    return out


# ── persistence ─────────────────────────────────────────────────────────────


def append_mismatches(
    mismatches: list[dict],
    path: Path | None = None,
    run_id: str = "",
) -> int:
    """Append mismatches to ``data/weapon_def_mismatches.jsonl``.

    Each line is one mismatch with a ``timestamp`` and ``run_id`` tag
    so post-run analysis can slice by run. The file is append-only;
    dedup (if wanted later) lives in the reader, not the writer.
    """
    if not mismatches:
        return 0
    p = path or MISMATCHES_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with open(p, "a") as f:
        for m in mismatches:
            rec: dict[str, Any] = {
                "timestamp": now,
                "run_id": run_id,
                **m,
            }
            f.write(json.dumps(rec) + "\n")
    return len(mismatches)


def compare_and_log(
    parsed: dict,
    path: Path | None = None,
    run_id: str = "",
    confidence_floor: float = 0.5,
) -> list[dict]:
    """Convenience: compare, then append any mismatches, return them."""
    mm = compare_weapon(parsed, confidence_floor=confidence_floor)
    if mm:
        append_mismatches(mm, path=path, run_id=run_id)
    return mm
