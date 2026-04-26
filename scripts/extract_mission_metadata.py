#!/usr/bin/env python3
"""Derive authoritative mission metadata from the game's Lua sources.

Run: ``python3 scripts/extract_mission_metadata.py [--itb-root PATH] [--out PATH]``

This is intentionally a regex / line-walker — not a real Lua interpreter.
It targets the **literal table assignment** schema used by the mission
scripts:

    Mission_Train = Mission_Infinite:new{
        Environment = "Env_Null",
        BonusPool   = { BONUS_GRID, BONUS_MECHS },
        UseBonus    = false,
        TurnLimit   = 3,
    }

Inheritance (``Mission_Infinite``, ``Mission_Auto``, ``Mission_Boss``,
``Mission_Critical``, ``Mission_MineBase``, ``Mission_Train``,
``Mission_Boss``) is resolved by following the ``X = Y:new{...}`` chain
upward and merging field-by-field. Anything we can't statically resolve
(dynamic ``StartMission`` body, weapon ids built at runtime) is dropped
into ``forced_pawns`` only when it shows up as a literal
``"PawnName"`` argument to ``Board:AddPawn(...)`` or
``PAWN_FACTORY:CreatePawn("PawnName")`` inside that mission's file.

Outputs ``data/mission_metadata.json`` keyed by ``mission_id`` with:

    {
      "mission_id": "Mission_Train",
      "base_class": "Mission_Infinite",
      "environment": "Env_Null",
      "bonus_pool": [3, 4, 5, 6, 7, 9, 8],
      "use_bonus": false,
      "boss_mission": false,
      "infinite_spawn": true,
      "block_cracks": false,
      "turn_limit": 3,
      "train_mission": true,
      "boss_pawn": null,
      "forced_pawns": ["Train_Pawn"],
      "has_objective_building": true,
      "corps": ["Corp_Default", "Corp_Grass", ...],
      "tilesets": ["grass", "sand", ...],
      "source_file": "missions/mission_train.lua"
    }

Spot-check 5 entries against the Lua before trusting downstream.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Game-source layout. We search the missions tree under both the legacy
# "missions/" and the "advanced/missions/" (Advanced Edition) roots.
# ---------------------------------------------------------------------------
DEFAULT_ITB_ROOT = Path(
    os.path.expanduser(
        "~/Library/Application Support/Steam/steamapps/common/"
        "Into the Breach/Into the Breach.app/Contents/Resources/scripts"
    )
)

MISSION_DIRS = ["missions", "advanced/missions"]
CORP_FILE_REL = "corporations.lua"
ADVANCED_CORP_FILE_REL = "advanced/ae_corporations.lua"

# ---------------------------------------------------------------------------
# BONUS_* enum mirrors missions/missions.lua:32-40
# ---------------------------------------------------------------------------
BONUS_ENUM = {
    "BONUS_ASSET": 1,
    "BONUS_KILL": 2,
    "BONUS_GRID": 3,
    "BONUS_MECHS": 4,
    "BONUS_BLOCK": 5,
    "BONUS_KILL_FIVE": 6,
    "BONUS_DEBRIS": 7,
    "BONUS_SELFDAMAGE": 8,
    "BONUS_PACIFIST": 9,
}

# Default BonusPool from the base Mission table (missions.lua:64).
DEFAULT_BONUS_POOL = [
    BONUS_ENUM["BONUS_KILL_FIVE"],
    BONUS_ENUM["BONUS_GRID"],
    BONUS_ENUM["BONUS_MECHS"],
    BONUS_ENUM["BONUS_DEBRIS"],
    BONUS_ENUM["BONUS_PACIFIST"],
    BONUS_ENUM["BONUS_SELFDAMAGE"],
]

# ---------------------------------------------------------------------------
# Pattern: top-level mission/base-class assignment.
#
#     Mission_Foo = Mission_Bar:new{ ... }
#     Mission_Battle = Mission:new{ }
#
# We anchor at start-of-line so we don't grab inner ``X = Y:new{}`` calls
# from helper functions.
# ---------------------------------------------------------------------------
RE_MISSION_DEF = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*):new\s*(\{)",
    re.MULTILINE,
)

# Fields we extract from the literal table body. Quoted strings, numbers,
# booleans, and braced-list-of-identifiers are all we handle.
RE_FIELD_STRING = re.compile(
    r'(\b[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"', re.MULTILINE,
)
RE_FIELD_BOOL = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(true|false)\b", re.MULTILINE,
)
RE_FIELD_NUMBER = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?\d+(?:\.\d+)?)\b", re.MULTILINE,
)
RE_FIELD_BRACELIST = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{([^{}]*)\}", re.MULTILINE,
)

# Forced-pawn detection: literal "Pawn" arguments to Board:AddPawn() or
# PAWN_FACTORY:CreatePawn(). We accept them only when they appear inside
# the same .lua file as the mission def — close enough for the 80% case.
RE_BOARD_ADDPAWN = re.compile(r'Board:AddPawn\(\s*"([A-Za-z_][A-Za-z0-9_]*)"')
RE_FACTORY_CREATE = re.compile(
    r'PAWN_FACTORY:CreatePawn\(\s*"([A-Za-z_][A-Za-z0-9_]*)"'
)
RE_SPAWNPAWN = re.compile(r'Board:SpawnPawn\(\s*"([A-Za-z_][A-Za-z0-9_]*)"')
# Pattern: random_element({"Snowtank1_Boom","Snowlaser1_Boom","Snowart1_Boom"})
# captures all the literal pawn ids in the brace-list. Used by
# Mission_BoomBots / Mission_Final BossList drops etc.
RE_RANDOM_ELEMENT_LIST = re.compile(
    r'random_element\(\s*\{([^{}]*)\}', re.MULTILINE,
)
RE_QUOTED_TOKEN = re.compile(r'"([A-Za-z_][A-Za-z0-9_]*)"')
# Pattern: ``local potential_bots = {"Foo","Bar"}`` — Mission_BoomBots and
# similar use a named local for their drop pool. We don't track which
# variable feeds which AddPawn, but capturing every literal-string brace
# list assigned to a local is good enough for an over-approximation.
RE_LOCAL_BRACE_LIST = re.compile(
    r"\blocal\s+[A-Za-z_][A-Za-z0-9_]*\s*=\s*\{([^{}]*)\}", re.MULTILINE,
)

# Pawn ids the base Mission class uses for *bonus mechanics* (debris, etc.)
# rather than the mission-specific kit. Filter these out of forced_pawns
# so a mission's spawn signature isn't polluted by inherited bonus code.
INHERITED_BONUS_PAWNS = {
    "BonusDebris",  # base Mission:AddDebris → BONUS_DEBRIS only
}

# Train classes — anything inheriting Mission_Train (chain-resolved later)
TRAIN_BASE = "Mission_Train"
BOSS_BASE = "Mission_Boss"
INFINITE_BASE = "Mission_Infinite"
CRITICAL_BASE = "Mission_Critical"
MINEBASE_BASE = "Mission_MineBase"


def _find_block_end(text: str, open_idx: int) -> int:
    """Return index just past the matching '}' for the '{' at open_idx.

    Walks the string respecting nested braces and skipping over string
    literals so braces inside quotes don't confuse us. Returns ``-1``
    if unbalanced.
    """
    assert text[open_idx] == "{"
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            # skip the quoted string
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\":
                    i += 2
                    continue
                i += 1
            i += 1
            continue
        if c == "-" and i + 1 < n and text[i + 1] == "-":
            # skip lua line comment
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "{":
            depth += 1
            i += 1
            continue
        if c == "}":
            depth -= 1
            i += 1
            if depth == 0:
                return i
            continue
        i += 1
    return -1


def _strip_lua_comments(s: str) -> str:
    """Strip ``--`` line comments and ``--[[ ... ]]`` block comments."""
    # Block comments first
    s = re.sub(r"--\[\[.*?\]\]", "", s, flags=re.DOTALL)
    # Then line comments — be careful not to strip ``--`` inside strings.
    out_lines = []
    for line in s.splitlines():
        # crude: cut at the first `--` that isn't inside a string
        in_str = False
        cut_idx = -1
        for i, ch in enumerate(line):
            if ch == '"':
                in_str = not in_str
            elif (
                not in_str
                and ch == "-"
                and i + 1 < len(line)
                and line[i + 1] == "-"
            ):
                cut_idx = i
                break
        if cut_idx >= 0:
            line = line[:cut_idx]
        out_lines.append(line)
    return "\n".join(out_lines)


def _parse_brace_list(body: str) -> list[str]:
    """Parse ``{ A, B, "c", 1 }`` → list[str] of raw token strings.

    Quoted-string entries get their surrounding double-quotes stripped so
    consumers see the bare identifier (``"Foo"`` → ``Foo``). Tokens that
    aren't quoted are returned as-is (e.g. enum names like ``BONUS_GRID``).
    """
    body = body.strip()
    if not body:
        return []
    # Split on commas not inside nested braces (we don't expect any here).
    items = [it.strip() for it in body.split(",")]
    out: list[str] = []
    for it in items:
        if not it:
            continue
        if len(it) >= 2 and it[0] == '"' and it[-1] == '"':
            out.append(it[1:-1])
        else:
            out.append(it)
    return out


def _parse_table_body(body: str) -> dict[str, Any]:
    """Parse a Lua literal table body into a Python dict.

    Only the common shapes we care about:
      Field = "string"
      Field = number
      Field = true | false
      Field = { TOK, TOK, ... }   (no nesting)
    """
    fields: dict[str, Any] = {}
    cleaned = _strip_lua_comments(body)
    for m in RE_FIELD_STRING.finditer(cleaned):
        fields[m.group(1)] = m.group(2)
    for m in RE_FIELD_BOOL.finditer(cleaned):
        # string/number/bool can appear with the same key, last writer wins
        fields[m.group(1)] = m.group(2) == "true"
    for m in RE_FIELD_NUMBER.finditer(cleaned):
        v = m.group(2)
        try:
            fields[m.group(1)] = int(v)
        except ValueError:
            fields[m.group(1)] = float(v)
    for m in RE_FIELD_BRACELIST.finditer(cleaned):
        # avoid clobbering a string/number that happens to share the name
        if m.group(1) in fields and not isinstance(fields[m.group(1)], list):
            # a brace-list field is more specific, take it
            pass
        fields[m.group(1)] = _parse_brace_list(m.group(2))
    return fields


RE_MISSION_METHOD = re.compile(
    r"^function\s+([A-Za-z_][A-Za-z0-9_]*):([A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)


def _extract_method_blocks(text: str, name: str) -> str:
    """Return the concatenated body of every ``function NAME:Method() ... end``
    in ``text``.

    Used to scope forced-pawn detection to a single mission when its file
    defines several (e.g. ``missions/missions.lua`` houses Mission_Battle,
    Mission_Survive, Mission_Auto, Mission_Test all together — the base
    Mission methods would otherwise leak into every record).
    """
    parts: list[str] = []
    for m in RE_MISSION_METHOD.finditer(text):
        if m.group(1) != name:
            continue
        # Walk forward until we balance the next ``end`` against intermediate
        # ``function``/``do``/``if``/``while``/``for``/``repeat`` keywords.
        # Cheap-and-cheerful: count occurrences of opening keywords vs
        # ``end`` after the method header. Lua method bodies can nest.
        body_start = m.end()
        depth = 1
        i = body_start
        n = len(text)
        # Lua block-keyword nesting:
        #   ``function`` / ``if`` / ``while`` / ``for`` open a block that
        #     closes with ``end``.
        #   ``do`` standalone opens an ``end``-closed block, BUT after
        #     ``for`` / ``while`` the ``do`` is the trailing keyword of
        #     that already-open block — counting it again double-counts.
        #     Cheap fix: don't count ``do`` at all. The few places ITB
        #     uses bare ``do ... end`` blocks aren't in mission code.
        #   ``repeat`` opens a block that closes with ``until`` (not
        #     ``end``); we count both ``repeat`` open and ``until`` close.
        token_rx = re.compile(
            r"\b(function|if|while|for|repeat|end|until)\b|--[^\n]*"
        )
        while i < n and depth > 0:
            tm = token_rx.search(text, i)
            if not tm:
                break
            tok = tm.group(0)
            if tok.startswith("--"):
                i = tm.end()
                continue
            if tok in ("end", "until"):
                depth -= 1
                i = tm.end()
                if depth == 0:
                    parts.append(text[body_start:tm.start()])
                    break
                continue
            if tok in ("function", "if", "while", "for", "repeat"):
                depth += 1
                i = tm.end()
                continue
            i = tm.end()
        else:
            # didn't find a matching end; bail without appending partial
            pass
    return "\n".join(parts)


def _walk_mission_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for sub in MISSION_DIRS:
        d = root / sub
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*.lua")):
            out.append(f)
    return out


def _extract_defs_in_file(
    text: str,
    rel_path: str,
) -> list[dict[str, Any]]:
    """Return a list of {name, base, body, file_text} for each top-level
    ``X = Y:new{...}`` in this file.
    """
    out = []
    for m in RE_MISSION_DEF.finditer(text):
        name, base, _ = m.group(1), m.group(2), m.group(3)
        # block start = the '{' after :new
        open_idx = m.end() - 1
        end_idx = _find_block_end(text, open_idx)
        if end_idx < 0:
            continue
        body = text[open_idx + 1 : end_idx - 1]
        out.append(
            {
                "name": name,
                "base": base,
                "body": body,
                "fields": _parse_table_body(body),
                "source_file": rel_path,
            }
        )
    return out


def _resolve_chain(
    name: str,
    defs: dict[str, dict[str, Any]],
) -> tuple[list[str], dict[str, Any]]:
    """Walk inheritance chain and merge fields top-down.

    Returns (chain_from_root_to_self, merged_fields).
    """
    # First, collect the chain self → base → base.base → ...
    chain: list[str] = []
    cursor = name
    seen: set[str] = set()
    while cursor and cursor not in seen and cursor in defs:
        seen.add(cursor)
        chain.append(cursor)
        cursor = defs[cursor]["base"]
    # If we hit an unknown root (e.g. "Mission"), append it for context.
    if cursor and cursor not in seen:
        chain.append(cursor)

    # Merge from root down so child wins.
    merged: dict[str, Any] = {}
    for cls in reversed(chain):
        if cls in defs:
            for k, v in defs[cls]["fields"].items():
                merged[k] = v
    return chain, merged


def _resolve_bonus_pool_tokens(tokens: list[str]) -> list[int]:
    """Map ['BONUS_GRID', 'BONUS_MECHS', ...] → [3, 4, ...]."""
    out: list[int] = []
    for tok in tokens:
        tok = tok.strip()
        if tok in BONUS_ENUM:
            out.append(BONUS_ENUM[tok])
        elif tok.isdigit():
            out.append(int(tok))
        # else: silently skip — we only handle the enum names
    return out


def _detect_forced_pawns(file_text: str) -> list[str]:
    """All literal pawn ids passed to Board:AddPawn / PAWN_FACTORY:CreatePawn /
    Board:SpawnPawn / random_element({"a","b"}) within this file.

    We deduplicate but preserve first-seen order so the JSON is stable.
    Excludes ``BonusDebris`` (an inherited bonus-mechanic spawn, not part
    of any individual mission's roster).
    """
    seen: set[str] = set()
    order: list[str] = []

    def _add(tok: str) -> None:
        if tok in INHERITED_BONUS_PAWNS:
            return
        if tok not in seen:
            seen.add(tok)
            order.append(tok)

    for rx in (RE_BOARD_ADDPAWN, RE_FACTORY_CREATE, RE_SPAWNPAWN):
        for m in rx.finditer(file_text):
            _add(m.group(1))
    # random_element({"A","B","C"}) — pick up the whole list as a candidate
    # pool. We can't tell which one will be picked at runtime so all are
    # forced-possible.
    for m in RE_RANDOM_ELEMENT_LIST.finditer(file_text):
        body = m.group(1)
        for tm in RE_QUOTED_TOKEN.finditer(body):
            _add(tm.group(1))
    # Same for ``local foo = {"A","B"}`` — used as a drop pool below.
    for m in RE_LOCAL_BRACE_LIST.finditer(file_text):
        body = m.group(1)
        # Only consider lists that look like pawn ids (all members quoted).
        toks = [tm.group(1) for tm in RE_QUOTED_TOKEN.finditer(body)]
        if not toks:
            continue
        # Heuristic: skip lists that contain commas-separated unquoted
        # numbers/identifiers (we'd see fewer quoted tokens than items).
        item_count = len([s for s in body.split(",") if s.strip()])
        if len(toks) != item_count:
            continue
        for t in toks:
            _add(t)
    return order


def _read_corp_mappings(root: Path) -> dict[str, dict[str, Any]]:
    """corporations.lua → { Corp_Foo: {tileset, missions_high, missions_low,
    bosses, unique_bosses} }.

    Inheritance handled the same way as missions: ``Corp_X = Corp_Y:new{...}``.
    """
    parts: list[str] = []
    for rel in (CORP_FILE_REL, ADVANCED_CORP_FILE_REL):
        p = root / rel
        if p.is_file():
            parts.append(p.read_text(encoding="utf-8", errors="replace"))
    text = "\n".join(parts)
    if not text:
        return {}

    defs: dict[str, dict[str, Any]] = {}
    for m in RE_MISSION_DEF.finditer(text):
        name, base, _ = m.group(1), m.group(2), m.group(3)
        if not name.startswith("Corp_"):
            continue
        open_idx = m.end() - 1
        end_idx = _find_block_end(text, open_idx)
        if end_idx < 0:
            continue
        body = text[open_idx + 1 : end_idx - 1]
        defs[name] = {
            "base": base,
            "fields": _parse_table_body(body),
        }

    # Resolve inheritance per corp.
    out: dict[str, dict[str, Any]] = {}
    for corp, d in defs.items():
        chain: list[str] = []
        cursor = corp
        seen: set[str] = set()
        while cursor and cursor not in seen and cursor in defs:
            seen.add(cursor)
            chain.append(cursor)
            cursor = defs[cursor]["base"]
        merged: dict[str, Any] = {}
        for cls in reversed(chain):
            for k, v in defs[cls]["fields"].items():
                merged[k] = v
        out[corp] = {
            "tileset": merged.get("Tileset"),
            "missions_high": merged.get("Missions_High", []) or [],
            "missions_low": merged.get("Missions_Low", []) or [],
            "bosses": merged.get("Bosses", []) or [],
            "unique_bosses": merged.get("UniqueBosses", []) or [],
        }
    return out


def _classify(
    name: str,
    chain: list[str],
    merged: dict[str, Any],
    file_text: str,
    table_body: str,
) -> dict[str, Any]:
    """Build the final JSON record for one mission."""
    base_class = chain[1] if len(chain) > 1 else None
    boss_mission = bool(merged.get("BossMission")) or BOSS_BASE in chain
    train_mission = TRAIN_BASE in chain[1:] or name in (TRAIN_BASE,)
    infinite_spawn = bool(merged.get("InfiniteSpawn")) or INFINITE_BASE in chain
    bonus_pool_tokens = merged.get("BonusPool")
    if bonus_pool_tokens is None:
        bonus_pool = list(DEFAULT_BONUS_POOL)
    else:
        bonus_pool = _resolve_bonus_pool_tokens(bonus_pool_tokens)
    # Scope forced-pawn detection to (a) the mission's table body and (b)
    # functions defined ON this mission (``function Mission_Foo:Bar() ...``).
    # Falling back to whole-file text leaks base-class helpers (notably
    # the ``random_element({"Scorpion1","Firefly1","Leaper1"})`` debris
    # spawn inside ``Mission:MissionEnd``) into every record housed in
    # ``missions/missions.lua``.
    scoped_text = table_body + "\n" + _extract_method_blocks(file_text, name)
    forced_pawns = _detect_forced_pawns(scoped_text)
    # Lift static literal pawn fields (TrainPawn = "Train_Armored", etc.)
    # so train missions surface their train type even when the call site
    # uses a local variable.
    for fld in ("TrainPawn", "TrainDamaged", "BossPawn"):
        v = merged.get(fld)
        if isinstance(v, str) and v and v not in forced_pawns:
            forced_pawns.append(v)
    # BossList is a literal brace-list — surface every option.
    boss_list = merged.get("BossList") or []
    if isinstance(boss_list, list):
        for tok in boss_list:
            if isinstance(tok, str) and tok and tok not in forced_pawns:
                forced_pawns.append(tok)
    has_objective_building = (
        # Asset-bearing missions (AddAsset / AddDefended / objective bldg)
        bool(merged.get("AssetId")) and merged.get("AssetId") != ""
        or "AddAsset" in scoped_text
        or "AddDefended" in scoped_text
        or "AddUniqueBuilding" in scoped_text
        or CRITICAL_BASE in chain
        or boss_mission  # bosses always pin Str_Tower asset
        or train_mission  # train IS the objective unit
    )
    return {
        "mission_id": name,
        "base_class": base_class,
        "class_chain": chain,
        "environment": merged.get("Environment", "Env_Null"),
        "bonus_pool": bonus_pool,
        "use_bonus": bool(merged.get("UseBonus", True)),
        "boss_mission": boss_mission,
        "boss_pawn": merged.get("BossPawn") or None,
        "boss_list": boss_list if isinstance(boss_list, list) else [],
        "infinite_spawn": infinite_spawn,
        "block_cracks": bool(merged.get("BlockCracks", False)),
        "turn_limit": merged.get("TurnLimit"),
        "train_mission": train_mission,
        "forced_pawns": forced_pawns,
        "has_objective_building": has_objective_building,
        "map_tags": merged.get("MapTags") or [],
    }


def extract(root: Path) -> dict[str, dict[str, Any]]:
    files = _walk_mission_files(root)
    if not files:
        raise SystemExit(f"No mission .lua files found under {root}")

    # Pass 1: collect all top-level X=Y:new{} defs across files (so inheritance
    # works even when base class is in a different file).
    defs_global: dict[str, dict[str, Any]] = {}
    file_texts: dict[str, str] = {}  # mission_name → its source file text
    table_bodies: dict[str, str] = {}  # mission_name → just its {...} body
    for f in files:
        rel = str(f.relative_to(root))
        text = f.read_text(encoding="utf-8", errors="replace")
        for d in _extract_defs_in_file(text, rel):
            defs_global[d["name"]] = d
            file_texts[d["name"]] = text
            table_bodies[d["name"]] = d["body"]

    # Pass 2: for every Mission_* whose name does NOT end up purely as a
    # base-class shell, emit a record. We include all Mission_* (including
    # bases) since some are real picks (Mission_Battle, Mission_Survive).
    corp_map = _read_corp_mappings(root)

    records: dict[str, dict[str, Any]] = {}
    for name, d in defs_global.items():
        if not name.startswith("Mission_"):
            continue
        chain, merged = _resolve_chain(name, defs_global)
        rec = _classify(
            name,
            chain,
            merged,
            file_texts.get(name, ""),
            table_bodies.get(name, ""),
        )
        rec["source_file"] = d["source_file"]

        # Corp / tileset attribution — best-effort. A mission can appear in
        # multiple corps; emit all that reference it.
        corps: list[str] = []
        tilesets: list[str] = []
        for corp, info in corp_map.items():
            if name in info["missions_high"] or name in info["missions_low"]:
                corps.append(corp)
                if info.get("tileset") and info["tileset"] not in tilesets:
                    tilesets.append(info["tileset"])
        # Bosses are referenced via corp.Bosses
        for corp, info in corp_map.items():
            if name in info["bosses"] or name in info["unique_bosses"]:
                if corp not in corps:
                    corps.append(corp)
                if info.get("tileset") and info["tileset"] not in tilesets:
                    tilesets.append(info["tileset"])
        rec["corps"] = sorted(corps)
        rec["tilesets"] = sorted(tilesets)
        records[name] = rec

    return records


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument(
        "--itb-root",
        default=str(DEFAULT_ITB_ROOT),
        help=f"ITB scripts root (default: {DEFAULT_ITB_ROOT})",
    )
    p.add_argument(
        "--out",
        default=None,
        help="output JSON path (default: <repo>/data/mission_metadata.json)",
    )
    args = p.parse_args(argv)

    root = Path(args.itb_root).expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: ITB scripts root not found: {root}", file=sys.stderr)
        return 2

    out_path = Path(args.out) if args.out else (
        Path(__file__).resolve().parent.parent / "data" / "mission_metadata.json"
    )

    records = extract(root)
    payload = {
        "_schema_version": 1,
        "_generated_from": str(root),
        "_count": len(records),
        "missions": records,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"Wrote {len(records)} missions → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
