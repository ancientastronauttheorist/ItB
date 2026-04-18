"""Claude Vision prompt templates + parsers for Phase 2 research.

The orchestrator (Claude running the loop) is the one that actually
reads the image. Python's job is:

1. Hand Claude the right instruction per crop type (``PROMPT_*``).
2. Validate and normalize whatever JSON Claude emits into a typed
   dict the downstream comparator (#P2-5) can diff.
3. Emit a confidence score so low-confidence extractions fall back
   to the Fandom wiki (#P2-6).

Why parsers instead of raw dicts: Claude Vision on small pixel-art
crops sometimes returns the structured fields embedded in prose,
misses a key, or returns a mini-board description that's close but
not canonically ordered. The parsers are the contract boundary —
they guarantee a predictable shape to the comparator regardless of
Vision output quirks.

Confidence score semantics:

- 1.0 = all required fields populated AND internally consistent
  (e.g. footprint_tiles non-empty for a weapon that has AOE).
- 0.6 = most fields present; comparator can diff but should flag.
- <0.4 = too sparse to trust; caller should hit the wiki fallback.

See ``docs/self_healing_loop_design.md#claude-vision-miss`` for the
escalation rules when confidence drops.
"""

from __future__ import annotations

import json
import re
from typing import Any


CONFIDENCE_WIKI_FALLBACK = 0.5  # at or below: consult wiki before shipping


# ── prompt templates ─────────────────────────────────────────────────────────

PROMPT_NAME_TAG = (
    "This is an Into the Breach name-tag crop for a selected unit. "
    "Return JSON with these keys:\n"
    "  name (string): the unit's displayed name (e.g. \"Judo Mech\", "
    "\"Firefly Leader\").\n"
    "  hp (integer): HP count if explicitly shown beside the name (pip "
    "icons). Use 0 if not shown — many enemies show only move here.\n"
    "  move (integer|null): movement range shown (number inside the "
    "green diamond badge). null if no movement badge is visible. Both "
    "mechs and enemies can display this.\n"
    "  class_icons (array of strings): names of small class icons to "
    "the right of the name/move/hp cluster, left to right. Use short "
    "descriptive snake_case labels like \"damages_mountain\", "
    "\"destroys_buildings\", \"death_effect\", \"boss\". Empty array "
    "if none are visible.\n"
    "Respond with ONLY the JSON object, no prose."
)

PROMPT_UNIT_STATUS = (
    "This is an Into the Breach UNIT STATUS panel crop. For an enemy "
    "this shows the unit portrait only. For a mech it's a horizontal "
    "rail: leftmost tile is the mech portrait with pilot nameplate, "
    "followed by 1-2 weapon icons. Return JSON:\n"
    "  kind (\"mech\"|\"enemy\"): guess from whether a pilot nameplate "
    "is visible.\n"
    "  pilot_name (string|null): pilot name under the portrait, or null.\n"
    "  weapon_slot_count (integer): number of weapon icons visible "
    "(0-2). 0 for enemies.\n"
    "Respond with ONLY the JSON object, no prose."
)

PROMPT_WEAPON_PREVIEW = (
    "This is an Into the Breach weapon preview panel. It shows a "
    "weapon's name, a short description, a rendered mini-board (an "
    "8×8 iso grid showing the weapon's targeting and AOE), a damage "
    "number, and upgrade tracks. Return JSON:\n"
    "  name (string): weapon name at the top.\n"
    "  weapon_class (string|null): tag below the name (e.g. \"Prime "
    "Class Weapon\").\n"
    "  description (string): the one-to-two sentence blurb above the "
    "mini-board.\n"
    "  damage (integer): the Damage number. 0 if \"none\" / not shown.\n"
    "  footprint_tiles (array of [dx, dy]): every tile the weapon "
    "visibly marks on the mini-board, relative to the firing mech "
    "at [0,0]. dx is east+, dy is south+. Include the target tile "
    "and any splash. EMPTY array means \"single-tile target, firer's "
    "tile only\" is NOT a valid reading — re-check the image first.\n"
    "  push_directions (array of strings): any push arrows shown. "
    "One of \"north\"/\"south\"/\"east\"/\"west\" per arrow, in any "
    "order.\n"
    "  upgrades (array of strings): upgrade-track labels (e.g. "
    "\"+2 Damage\", \"Ally Immune\").\n"
    "Respond with ONLY the JSON object, no prose."
)

PROMPT_TERRAIN_TOOLTIP = (
    "This is an Into the Breach terrain/status tooltip (bottom-right "
    "panel). Return JSON:\n"
    "  terrain (string): terrain name (e.g. \"Ground Tile\", \"Water\", "
    "\"Mountain\", \"Chasm\", \"Lava\", \"Sand\", \"Ice\", \"Forest\", "
    "\"Smoke\", \"Fire\"). Empty string if no terrain is shown.\n"
    "  effect (string): the one-line description shown below the "
    "terrain name.\n"
    "  status_effects (array of strings): if a unit occupies the tile "
    "and has status effects, list them (e.g. [\"Fire\", \"ACID\", "
    "\"Shield\"]).\n"
    "Respond with ONLY the JSON object, no prose."
)


PROMPTS: dict[str, str] = {
    "name_tag": PROMPT_NAME_TAG,
    "unit_status": PROMPT_UNIT_STATUS,
    "weapon_preview": PROMPT_WEAPON_PREVIEW,
    "terrain_tooltip": PROMPT_TERRAIN_TOOLTIP,
}


# ── parsers ──────────────────────────────────────────────────────────────────


def _extract_json(text: str) -> dict | None:
    """Find the first JSON object in ``text`` and parse it.

    Claude sometimes wraps JSON in a markdown fence or adds a
    sentence of prose. This picks out the first ``{...}`` block
    greedily (matching balanced braces) and tries to decode it.
    Returns None on total failure.
    """
    if not text:
        return None
    # Strip markdown fences first.
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```", "", text)

    # Balanced-brace scan (naive but works for Vision-sized payloads).
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                blob = text[start : i + 1]
                try:
                    return json.loads(blob)
                except json.JSONDecodeError:
                    return None
    return None


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        if isinstance(v, str):
            m = re.search(r"-?\d+", v)
            if m:
                return int(m.group(0))
        return default


def parse_name_tag(text_or_dict: str | dict) -> dict:
    """Normalize a name_tag Vision response.

    Output shape: ``{name, hp, move, class_icons, confidence}``.
    """
    raw = text_or_dict if isinstance(text_or_dict, dict) else _extract_json(text_or_dict)
    if raw is None:
        return {
            "name": "",
            "hp": 0,
            "move": None,
            "class_icons": [],
            "confidence": 0.0,
        }

    name = str(raw.get("name", "")).strip()
    hp = _to_int(raw.get("hp", 0))
    move_raw = raw.get("move")
    move = None if move_raw in (None, "null", "") else _to_int(move_raw, default=-1)
    if move == -1:
        move = None
    icons = raw.get("class_icons") or []
    if not isinstance(icons, list):
        icons = []
    icons = [str(i) for i in icons if i]

    # Confidence: name is required; hp/move are secondary.
    confidence = 0.0
    if name:
        confidence += 0.7
    if hp > 0:
        confidence += 0.2
    if move is not None or icons:
        confidence += 0.1
    return {
        "name": name,
        "hp": hp,
        "move": move,
        "class_icons": icons,
        "confidence": round(min(confidence, 1.0), 2),
    }


def parse_unit_status(text_or_dict: str | dict) -> dict:
    """Normalize a unit_status Vision response."""
    raw = text_or_dict if isinstance(text_or_dict, dict) else _extract_json(text_or_dict)
    if raw is None:
        return {
            "kind": "unknown",
            "pilot_name": None,
            "weapon_slot_count": 0,
            "confidence": 0.0,
        }

    kind = str(raw.get("kind", "")).lower().strip()
    if kind not in ("mech", "enemy"):
        kind = "unknown"
    pilot = raw.get("pilot_name")
    pilot = str(pilot).strip() if pilot else None
    if pilot == "":
        pilot = None
    slot_count = _to_int(raw.get("weapon_slot_count", 0))
    slot_count = max(0, min(slot_count, 2))

    confidence = 0.0
    if kind != "unknown":
        confidence += 0.6
    if kind == "mech" and pilot:
        confidence += 0.2
    if kind == "mech" and slot_count > 0:
        confidence += 0.2
    if kind == "enemy":
        confidence += 0.4  # enemies have fewer required fields
    return {
        "kind": kind,
        "pilot_name": pilot,
        "weapon_slot_count": slot_count,
        "confidence": round(min(confidence, 1.0), 2),
    }


_DIRECTIONS = ("north", "south", "east", "west")


def _norm_dir(s: Any) -> str | None:
    if not isinstance(s, str):
        return None
    s = s.strip().lower()
    # Map short forms and synonyms to canonical.
    aliases = {
        "n": "north", "s": "south", "e": "east", "w": "west",
        "up": "north", "down": "south", "right": "east", "left": "west",
    }
    s = aliases.get(s, s)
    return s if s in _DIRECTIONS else None


def parse_weapon_preview(text_or_dict: str | dict) -> dict:
    """Normalize a weapon_preview Vision response.

    The heart of the regression harness. footprint_tiles must be a
    list of ``[dx, dy]`` integer pairs. Anything else gets coerced or
    dropped; coercion drops confidence.
    """
    raw = text_or_dict if isinstance(text_or_dict, dict) else _extract_json(text_or_dict)
    if raw is None:
        return {
            "name": "",
            "weapon_class": None,
            "description": "",
            "damage": 0,
            "footprint_tiles": [],
            "push_directions": [],
            "upgrades": [],
            "confidence": 0.0,
        }

    name = str(raw.get("name", "")).strip()
    wclass = raw.get("weapon_class")
    wclass = str(wclass).strip() if wclass else None
    if wclass == "":
        wclass = None
    description = str(raw.get("description", "")).strip()
    damage = _to_int(raw.get("damage", 0))

    footprint: list[tuple[int, int]] = []
    coerced = 0
    for entry in raw.get("footprint_tiles") or []:
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            try:
                footprint.append((int(entry[0]), int(entry[1])))
                continue
            except (TypeError, ValueError):
                pass
        if isinstance(entry, dict):
            dx = entry.get("dx", entry.get("x"))
            dy = entry.get("dy", entry.get("y"))
            if dx is not None and dy is not None:
                try:
                    footprint.append((int(dx), int(dy)))
                    coerced += 1
                    continue
                except (TypeError, ValueError):
                    pass
        # unparseable entry — ignored, drops confidence
        coerced += 1

    pushes: list[str] = []
    for p in raw.get("push_directions") or []:
        d = _norm_dir(p)
        if d is not None:
            pushes.append(d)

    upgrades = [str(u).strip() for u in (raw.get("upgrades") or []) if u]

    confidence = 0.0
    if name:
        confidence += 0.4
    if description:
        confidence += 0.15
    if damage > 0 or "passive" in description.lower():
        confidence += 0.1
    if footprint:
        confidence += 0.25
    if wclass:
        confidence += 0.05
    if upgrades:
        confidence += 0.05
    # Coercion penalty — Vision output was structurally off.
    if coerced:
        confidence -= min(0.2, 0.05 * coerced)
    confidence = max(0.0, min(confidence, 1.0))

    return {
        "name": name,
        "weapon_class": wclass,
        "description": description,
        "damage": damage,
        "footprint_tiles": footprint,
        "push_directions": pushes,
        "upgrades": upgrades,
        "confidence": round(confidence, 2),
    }


def parse_terrain_tooltip(text_or_dict: str | dict) -> dict:
    """Normalize a terrain_tooltip Vision response."""
    raw = text_or_dict if isinstance(text_or_dict, dict) else _extract_json(text_or_dict)
    if raw is None:
        return {
            "terrain": "",
            "effect": "",
            "status_effects": [],
            "confidence": 0.0,
        }

    terrain = str(raw.get("terrain", "")).strip()
    effect = str(raw.get("effect", "")).strip()
    status = [str(s).strip() for s in (raw.get("status_effects") or []) if s]

    confidence = 0.0
    if terrain:
        confidence += 0.7
    if effect:
        confidence += 0.3
    return {
        "terrain": terrain,
        "effect": effect,
        "status_effects": status,
        "confidence": round(min(confidence, 1.0), 2),
    }


PARSERS: dict[str, Any] = {
    "name_tag": parse_name_tag,
    "unit_status": parse_unit_status,
    "weapon_preview": parse_weapon_preview,
    "terrain_tooltip": parse_terrain_tooltip,
}


def should_fall_back_to_wiki(parsed: dict) -> bool:
    """Whether the extraction is too low-confidence to trust without the wiki."""
    return float(parsed.get("confidence", 0.0)) <= CONFIDENCE_WIKI_FALLBACK
