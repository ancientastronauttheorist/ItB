#!/usr/bin/env python3
"""Regenerate ``data/known_types.json`` — the Phase 0 novelty baseline.

Pulls five sources together:

1. Wiki filenames from ``data/wiki_raw/`` (dropping the ``.html``/``.json``
   extension). These are the canonical unit names from Fandom.
2. Rust enum variants from ``rust_solver/src/weapons.rs`` (``WId``) and
   ``rust_solver/src/types.rs`` (``Terrain``).
3. Bridge-observed ``unit.type`` strings scanned from recordings under
   ``recordings/``. These look like ``Firefly1``/``Firefly2`` — they don't
   match the wiki naming, but they're the exact strings ``unknown_detector``
   will see at runtime, so we seed them here to avoid a wave of false-positive
   "unknown" flags on Phase 0 rollout.
4. Bridge-observed weapon IDs scanned from the same recordings. Rust exposes
   them as underscore-free enum variants (``PrimePunchmech``); the bridge
   emits the underscored form (``Prime_Punchmech``). We store both —
   ``unknown_detector`` normalizes at comparison time.
5. Known phase strings for the screen-novelty check. These are enumerated
   from ``src/bridge/reader.py`` (bridge-side) and ``src/capture/save_parser.py``
   (save-parser side). When either module grows new phase values, update the
   ``KNOWN_PHASES`` list below.

The ``unknown_detector`` treats:
- wiki_pages + observed_pawn_types → "known pawns"
- terrain_enum (lowercased) + terrain_ids → "known terrain"
- weapon_enum + observed_weapons → "known weapons" (normalized)
- known_phases → "known screens"

Re-run whenever wiki_raw/ grows, Rust enums change, phase strings drift, or
you want to fold in new observed data. Run:
``python3 scripts/regenerate_known_types.py``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WIKI_RAW = REPO / "data" / "wiki_raw"
WEAPONS_RS = REPO / "rust_solver" / "src" / "weapons.rs"
TYPES_RS = REPO / "rust_solver" / "src" / "types.rs"
RECORDINGS = REPO / "recordings"
OUT = REPO / "data" / "known_types.json"


def wiki_pages() -> list[str]:
    if not WIKI_RAW.is_dir():
        return []
    names: set[str] = set()
    for p in WIKI_RAW.iterdir():
        if p.suffix in (".html", ".json"):
            names.add(p.stem)
    return sorted(names)


_WID_RE = re.compile(r"^\s*([A-Z][A-Za-z0-9]*)\s*=\s*\d+,\s*$")


def weapon_enum() -> list[str]:
    if not WEAPONS_RS.is_file():
        return []
    found: list[str] = []
    in_wid = False
    for line in WEAPONS_RS.read_text().splitlines():
        if "pub enum WId" in line:
            in_wid = True
            continue
        if in_wid:
            if line.strip().startswith("}"):
                break
            m = _WID_RE.match(line)
            if m:
                found.append(m.group(1))
    return sorted(set(found))


_TERRAIN_RE = re.compile(r"^\s*([A-Z][A-Za-z]*)\s*=\s*\d+,\s*$")


def terrain_enum() -> list[str]:
    if not TYPES_RS.is_file():
        return []
    found: list[str] = []
    in_terrain = False
    for line in TYPES_RS.read_text().splitlines():
        if "pub enum Terrain" in line:
            in_terrain = True
            continue
        if in_terrain:
            if line.strip().startswith("}"):
                break
            stripped = line.strip()
            # Handle "#[default]" attribute line — skip, next line is the variant.
            if stripped.startswith("#"):
                continue
            m = _TERRAIN_RE.match(line)
            if m:
                found.append(m.group(1))
    return sorted(set(found))


def observed_pawn_types() -> list[str]:
    if not RECORDINGS.is_dir():
        return []
    types: set[str] = set()
    for board_file in RECORDINGS.glob("*/m*_turn_*_board.json"):
        try:
            with open(board_file) as f:
                rec = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        units = rec.get("data", {}).get("bridge_state", {}).get("units", [])
        for u in units:
            t = u.get("type", "")
            if t:
                types.add(t)
    return sorted(types)


def observed_weapons() -> list[str]:
    """Scan recordings for every weapon id seen on any unit.

    Mirror of ``observed_pawn_types``. Captures the underscored bridge
    form (e.g. ``Prime_Punchmech``) which the Rust enum variant form
    (``PrimePunchmech``) can't cover by itself.
    """
    if not RECORDINGS.is_dir():
        return []
    weapons: set[str] = set()
    for board_file in RECORDINGS.glob("*/m*_turn_*_board.json"):
        try:
            with open(board_file) as f:
                rec = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        units = rec.get("data", {}).get("bridge_state", {}).get("units", [])
        for u in units:
            for w in u.get("weapons", []) or []:
                if w:
                    weapons.add(w)
    return sorted(weapons)


# Phase strings enumerated by the bridge reader and save parser.
# When either module grows a new phase value, append it here so it
# doesn't trip a false-positive screen novelty flag.
# Sources:
#   - src/bridge/reader.py    (combat_player, combat_enemy, unknown)
#   - src/capture/save_parser.py (no_save, between_missions, mission_ending,
#                                 combat_player, combat_enemy)
KNOWN_PHASES: list[str] = [
    "between_missions",
    "combat_enemy",
    "combat_player",
    "mission_ending",
    "no_save",
    "unknown",
]


def main() -> int:
    wiki = wiki_pages()
    weapons = weapon_enum()
    terrain = terrain_enum()
    observed = observed_pawn_types()
    obs_weapons = observed_weapons()

    terrain_lc = sorted({t.lower() for t in terrain})

    doc = {
        "_comment": (
            "Regenerate with scripts/regenerate_known_types.py. "
            "Used by src/solver/unknown_detector.py to flag novel "
            "pawn types / terrain / weapons / phases during cmd_read."
        ),
        "wiki_pages": wiki,
        "weapon_enum": weapons,
        "terrain_enum": terrain,
        "terrain_ids": terrain_lc,
        "observed_pawn_types": observed,
        "observed_weapons": obs_weapons,
        "known_phases": list(KNOWN_PHASES),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=2, sort_keys=False)
        f.write("\n")

    print(f"wrote {OUT.relative_to(REPO)}")
    print(f"  wiki_pages:          {len(wiki)}")
    print(f"  weapon_enum:         {len(weapons)}")
    print(f"  terrain_enum:        {len(terrain)} → terrain_ids {len(terrain_lc)}")
    print(f"  observed_pawn_types: {len(observed)}")
    print(f"  observed_weapons:    {len(obs_weapons)}")
    print(f"  known_phases:        {len(KNOWN_PHASES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
