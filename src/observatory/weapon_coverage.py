"""Build-keyed lexical index of player-weapon Lua IDs in Rust.

The index deliberately measures only syntax and exact identifiers. It does not
infer weapon behavior, upgrade equivalence, simulator support, or conformance.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from src.observatory.provenance import is_player_weapon_source


SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = r"[A-Za-z][A-Za-z0-9_]*"
_LUA_CONSTRUCTOR_RE = re.compile(
    rf"^[ \t]*({_IDENTIFIER})[ \t]*=[ \t\r\n]*"
    rf"({_IDENTIFIER}):new[ \t\r\n]*"
    rf"(?:\{{|\([ \t\r\n]*({_IDENTIFIER})[ \t\r\n]*\))",
    re.MULTILINE,
)
_LUA_ALIAS_RE = re.compile(
    rf"^[ \t]*({_IDENTIFIER})[ \t]*=[ \t]*({_IDENTIFIER})"
    r"[ \t]*;?[ \t\r]*$",
    re.MULTILINE,
)
_LUA_METHOD_RE = re.compile(
    rf"^[ \t]*function[ \t]+({_IDENTIFIER}):"
    r"(GetTargetArea|GetSecondTargetArea|GetSkillEffect|GetFinalEffect)"
    r"[ \t]*\(",
    re.MULTILINE,
)
_LUA_BLOCK_TOKEN_RE = re.compile(
    r"\b(function|if|for|while|do|repeat|end|until)\b"
)
_RUST_ENUM_RE = re.compile(
    rf"^[ \t]*({_IDENTIFIER})[ \t]*=[ \t]*(\d+)[ \t]*,",
    re.MULTILINE,
)
_RUST_MAPPING_RE = re.compile(
    rf'^[ \t]*"([^"]+)"[ \t]*=>[ \t]*WId::({_IDENTIFIER}),',
    re.MULTILINE,
)
_RUST_RAW_STRING_START_RE = re.compile(r"(?:b?r)(#+)?\"")
_LUA_RESERVED = {
    "and",
    "break",
    "do",
    "else",
    "elseif",
    "end",
    "false",
    "for",
    "function",
    "goto",
    "if",
    "in",
    "local",
    "nil",
    "not",
    "or",
    "repeat",
    "return",
    "then",
    "true",
    "until",
    "while",
}


class WeaponCoverageError(RuntimeError):
    """Raised when lexical coverage inputs are stale or ambiguous."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WeaponCoverageError(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        raise WeaponCoverageError(f"{label} must be a non-empty string")
    return value


def _sha256(value: Any, label: str) -> str:
    text = _string(value, label)
    if not _SHA256_RE.fullmatch(text):
        raise WeaponCoverageError(f"{label} must be a lowercase SHA-256")
    return text


def _safe_path(value: Any, label: str) -> PurePosixPath:
    text = _string(value, label)
    if "\\" in text:
        raise WeaponCoverageError(f"{label} must use forward slashes")
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or path.as_posix() != text
    ):
        raise WeaponCoverageError(f"{label} must be a normalized relative path")
    return path


def _read_exact_inventory_file(
    content_root: Path,
    relative: PurePosixPath,
    *,
    expected_size: Any,
    expected_sha256: Any,
) -> str:
    if (
        type(expected_size) is not int
        or expected_size < 0
        or type(expected_sha256) is not str
        or not _SHA256_RE.fullmatch(expected_sha256)
    ):
        raise WeaponCoverageError(
            f"invalid inventory size/hash for {relative.as_posix()}"
        )
    root = content_root.resolve()
    candidate = content_root.joinpath(*relative.parts)
    resolved = candidate.resolve()
    if (
        candidate.is_symlink()
        or not resolved.is_relative_to(root)
        or not candidate.is_file()
    ):
        raise WeaponCoverageError(
            f"inventory source is not a contained regular file: {relative}"
        )
    before = candidate.stat()
    data = candidate.read_bytes()
    after = candidate.stat()
    stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if any(
        getattr(before, field) != getattr(after, field)
        for field in stable_fields
    ):
        raise WeaponCoverageError(
            f"source changed while being read: {relative.as_posix()}"
        )
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if len(data) != expected_size or actual_sha256 != expected_sha256:
        raise WeaponCoverageError(
            f"inventory source bytes are stale: {relative.as_posix()}"
        )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WeaponCoverageError(
            f"inventory source is not UTF-8: {relative.as_posix()}"
        ) from exc


def _read_stable_utf8(path: Path, label: str) -> str:
    try:
        if not path.is_file():
            raise OSError("not a regular file")
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise WeaponCoverageError(f"cannot read {label}: {path}") from exc
    stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if any(
        getattr(before, field) != getattr(after, field)
        for field in stable_fields
    ):
        raise WeaponCoverageError(f"{label} changed while being read")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WeaponCoverageError(f"{label} is not UTF-8") from exc


def _inventory_identity(inventory: Mapping[str, Any]) -> dict[str, Any]:
    executable = _mapping(inventory.get("executable"), "inventory.executable")
    steam = _mapping(inventory.get("steam"), "inventory.steam")
    content = _mapping(inventory.get("content"), "inventory.content")
    scripts = _mapping(content.get("scripts"), "inventory.content.scripts")
    maps = _mapping(content.get("maps"), "inventory.content.maps")
    depots = steam.get("installed_depots")
    if not isinstance(depots, list) or not depots:
        raise WeaponCoverageError(
            "inventory.steam.installed_depots must be a non-empty array"
        )
    depot = _mapping(depots[0], "inventory.steam.installed_depots[0]")
    return {
        "platform": _string(inventory.get("platform"), "inventory.platform"),
        "architecture": _string(
            executable.get("architecture"),
            "inventory.executable.architecture",
        ),
        "executable_sha256": _sha256(
            executable.get("sha256"), "inventory.executable.sha256"
        ),
        "build_id": _string(steam.get("build_id"), "inventory.steam.build_id"),
        "depot_manifest": _string(
            depot.get("manifest"),
            "inventory.steam.installed_depots[0].manifest",
        ),
        "scripts_revision_sha256": _sha256(
            scripts.get("revision_sha256"),
            "inventory.content.scripts.revision_sha256",
        ),
        "maps_revision_sha256": _sha256(
            maps.get("revision_sha256"),
            "inventory.content.maps.revision_sha256",
        ),
    }


def _long_bracket_open(text: str, index: int) -> tuple[str, int] | None:
    if index >= len(text) or text[index] != "[":
        return None
    cursor = index + 1
    while cursor < len(text) and text[cursor] == "=":
        cursor += 1
    if cursor >= len(text) or text[cursor] != "[":
        return None
    equals = text[index + 1 : cursor]
    return f"]{equals}]", cursor + 1


def _blank(masked: list[str], start: int, end: int) -> None:
    for index in range(start, end):
        if masked[index] not in "\r\n":
            masked[index] = " "


def _mask_lua_opaque(text: str) -> str:
    """Blank Lua comments and strings while preserving offsets/newlines."""
    masked = list(text)
    index = 0
    while index < len(text):
        if text.startswith("--", index):
            long_open = _long_bracket_open(text, index + 2)
            if long_open:
                delimiter, body_start = long_open
                close = text.find(delimiter, body_start)
                if close < 0:
                    raise WeaponCoverageError("unterminated Lua long comment")
                end = close + len(delimiter)
            else:
                newline = text.find("\n", index + 2)
                end = len(text) if newline < 0 else newline
            _blank(masked, index, end)
            index = end
            continue
        if text[index] in {"'", '"'}:
            quote = text[index]
            cursor = index + 1
            while cursor < len(text):
                if text[cursor] == "\\":
                    cursor += 2
                    continue
                if text[cursor] == quote:
                    cursor += 1
                    break
                cursor += 1
            else:
                raise WeaponCoverageError("unterminated Lua short string")
            _blank(masked, index, cursor)
            index = cursor
            continue
        long_open = _long_bracket_open(text, index)
        if long_open:
            delimiter, body_start = long_open
            close = text.find(delimiter, body_start)
            if close < 0:
                raise WeaponCoverageError("unterminated Lua long string")
            end = close + len(delimiter)
            _blank(masked, index, end)
            index = end
            continue
        index += 1
    return "".join(masked)


def _mask_rust_comments(text: str) -> str:
    """Blank nested Rust comments while preserving strings and offsets."""
    masked = list(text)
    index = 0
    while index < len(text):
        raw = _RUST_RAW_STRING_START_RE.match(text, index)
        if raw:
            hashes = raw.group(1) or ""
            body_start = raw.end()
            delimiter = f'"{hashes}'
            close = text.find(delimiter, body_start)
            if close < 0:
                raise WeaponCoverageError("unterminated Rust raw string")
            end = close + len(delimiter)
            _blank(masked, index, end)
            index = end
            continue
        if text[index] == '"':
            cursor = index + 1
            while cursor < len(text):
                if text[cursor] == "\\":
                    cursor += 2
                    continue
                if text[cursor] == '"':
                    cursor += 1
                    break
                cursor += 1
            else:
                raise WeaponCoverageError("unterminated Rust string")
            if "\n" in text[index:cursor]:
                _blank(masked, index, cursor)
            index = cursor
            continue
        if text.startswith("//", index):
            newline = text.find("\n", index + 2)
            end = len(text) if newline < 0 else newline
            _blank(masked, index, end)
            index = end
            continue
        if text.startswith("/*", index):
            cursor = index + 2
            depth = 1
            while cursor < len(text) and depth:
                if text.startswith("/*", cursor):
                    depth += 1
                    cursor += 2
                elif text.startswith("*/", cursor):
                    depth -= 1
                    cursor += 2
                else:
                    cursor += 1
            if depth:
                raise WeaponCoverageError("unterminated Rust block comment")
            _blank(masked, index, cursor)
            index = cursor
            continue
        index += 1
    return "".join(masked)


def _lua_function_spans(masked: str) -> list[tuple[int, int]]:
    """Return function regions using Lua block keywords outside opaque text."""
    stack: list[dict[str, Any]] = []
    spans: list[tuple[int, int]] = []
    for match in _LUA_BLOCK_TOKEN_RE.finditer(masked):
        token = match.group(1)
        if token == "function":
            stack.append(
                {"kind": token, "start": match.start(), "pending_do": False}
            )
        elif token in {"if", "repeat"}:
            stack.append(
                {"kind": token, "start": match.start(), "pending_do": False}
            )
        elif token in {"for", "while"}:
            stack.append(
                {"kind": token, "start": match.start(), "pending_do": True}
            )
        elif token == "do":
            if (
                stack
                and stack[-1]["kind"] in {"for", "while"}
                and stack[-1]["pending_do"]
            ):
                stack[-1]["pending_do"] = False
            else:
                stack.append(
                    {"kind": token, "start": match.start(), "pending_do": False}
                )
        elif token == "until":
            if not stack or stack[-1]["kind"] != "repeat":
                raise WeaponCoverageError("unbalanced Lua until block")
            stack.pop()
        elif token == "end":
            if not stack or stack[-1]["kind"] == "repeat":
                raise WeaponCoverageError("unbalanced Lua end block")
            block = stack.pop()
            if block["kind"] == "function":
                spans.append((block["start"], match.end()))
    if stack:
        raise WeaponCoverageError("unterminated Lua block")
    return sorted(spans)


def _inside_spans(offset: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= offset < end for start, end in spans)


def _lua_brace_depths(masked: str) -> list[int]:
    depths = [0] * (len(masked) + 1)
    depth = 0
    for index, character in enumerate(masked):
        depths[index] = depth
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth < 0:
                raise WeaponCoverageError("unbalanced Lua table brace")
    depths[len(masked)] = depth
    if depth:
        raise WeaponCoverageError("unterminated Lua table brace")
    return depths


def _position(text: str, offset: int) -> tuple[int, int]:
    line_start = text.rfind("\n", 0, offset) + 1
    return text.count("\n", 0, offset) + 1, offset - line_start + 1


def _line_suffix_is_clean(masked: str, offset: int) -> bool:
    newline = masked.find("\n", offset)
    end = len(masked) if newline < 0 else newline
    return bool(re.fullmatch(r"[ \t\r]*;?[ \t\r]*", masked[offset:end]))


def _constructor_end(masked: str, match: re.Match[str]) -> int | None:
    """Return the direct constructor expression end, or None for a suffix."""
    if match.group(3):
        return match.end() if _line_suffix_is_clean(masked, match.end()) else None
    open_brace = match.end() - 1
    depth = 0
    for index in range(open_brace, len(masked)):
        if masked[index] == "{":
            depth += 1
        elif masked[index] == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                return end if _line_suffix_is_clean(masked, end) else None
    raise WeaponCoverageError("unterminated Lua constructor table")


def _lua_candidates(path: str, sha256: str, text: str) -> list[dict[str, Any]]:
    masked = _mask_lua_opaque(text)
    spans = _lua_function_spans(masked)
    brace_depths = _lua_brace_depths(masked)
    methods: dict[str, set[str]] = defaultdict(set)
    for match in _LUA_METHOD_RE.finditer(masked):
        if brace_depths[match.start()] != 0 or any(
            start < match.start() < end for start, end in spans
        ):
            continue
        methods[match.group(1)].add(match.group(2))

    candidates = []
    occupied: list[tuple[int, int]] = []
    for match in _LUA_CONSTRUCTOR_RE.finditer(masked):
        if (
            _inside_spans(match.start(1), spans)
            or brace_depths[match.start(1)] != 0
        ):
            continue
        constructor_end = _constructor_end(masked, match)
        if constructor_end is None:
            continue
        lua_id, parent, constructor_argument = match.groups()
        line, column = _position(text, match.start(1))
        candidates.append(
            {
                "lua_id": lua_id,
                "source_path": path,
                "source_sha256": sha256,
                "line": line,
                "column": column,
                "definition_kind": (
                    "constructor-reference"
                    if constructor_argument
                    else "constructor-table"
                ),
                "declared_parent": parent,
                "constructor_argument": constructor_argument,
                "methods": sorted(methods.get(lua_id, set())),
            }
        )
        occupied.append((match.start(), constructor_end))
    for match in _LUA_ALIAS_RE.finditer(masked):
        if (
            _inside_spans(match.start(1), spans)
            or brace_depths[match.start(1)] != 0
        ):
            continue
        if any(start <= match.start() < end for start, end in occupied):
            continue
        lua_id, target = match.groups()
        if target in _LUA_RESERVED:
            continue
        line, column = _position(text, match.start(1))
        candidates.append(
            {
                "lua_id": lua_id,
                "source_path": path,
                "source_sha256": sha256,
                "line": line,
                "column": column,
                "definition_kind": "alias",
                "declared_parent": target,
                "constructor_argument": None,
                "methods": sorted(methods.get(lua_id, set())),
            }
        )
    return candidates


def _rust_id_index(text: str) -> tuple[dict[str, int], dict[str, str]]:
    masked = _mask_rust_comments(text)
    enum_start = masked.find("pub enum WId")
    mapping_start = masked.find("pub fn wid_from_str")
    mapping_end = masked.find("pub fn wid_to_str", mapping_start + 1)
    if min(enum_start, mapping_start, mapping_end) < 0:
        raise WeaponCoverageError("Rust source lacks WId/wid_from_str boundaries")
    enum_end = masked.find("\n}", enum_start)
    if enum_end < 0 or enum_end >= mapping_start:
        raise WeaponCoverageError("Rust WId enum boundary is invalid")
    if "#[repr(u8)]" not in masked[max(0, enum_start - 200) : enum_start]:
        raise WeaponCoverageError("Rust WId enum must use repr(u8)")

    variants: dict[str, int] = {}
    discriminants: dict[int, str] = {}
    for match in _RUST_ENUM_RE.finditer(masked[enum_start:enum_end]):
        variant, raw_value = match.groups()
        value = int(raw_value)
        if value > 255:
            raise WeaponCoverageError(f"WId discriminant is out of range: {value}")
        if variant in variants or value in discriminants:
            raise WeaponCoverageError("duplicate Rust WId variant/discriminant")
        variants[variant] = value
        discriminants[value] = variant
    if not variants:
        raise WeaponCoverageError("Rust WId enum contains no explicit variants")

    body = masked[mapping_start:mapping_end]
    mappings: dict[str, str] = {}
    for match in _RUST_MAPPING_RE.finditer(body):
        lua_id, rust_wid = match.groups()
        if lua_id in mappings:
            raise WeaponCoverageError(
                f"duplicate Rust wid_from_str Lua ID: {lua_id}"
            )
        if rust_wid not in variants:
            raise WeaponCoverageError(
                f"wid_from_str references missing WId variant: {rust_wid}"
            )
        mappings[lua_id] = rust_wid
    for line in body.splitlines():
        if "=> WId::" not in line or re.match(r"^[ \t]*_[ \t]*=>", line):
            continue
        if not _RUST_MAPPING_RE.match(line):
            raise WeaponCoverageError(
                f"unsupported wid_from_str mapping arm: {line.strip()}"
            )
    if not mappings:
        raise WeaponCoverageError("Rust wid_from_str contains no direct mappings")
    return variants, mappings


def _family(lua_id: str, candidate_ids: set[str]) -> tuple[str, str | None]:
    for suffix, variant in (("_AB", "AB"), ("_A", "A"), ("_B", "B")):
        if lua_id.endswith(suffix):
            base = lua_id[: -len(suffix)]
            if base in candidate_ids:
                return base, variant
    return lua_id, None


def analyze_player_weapon_ids(
    inventory: Mapping[str, Any],
    *,
    content_root: Path,
    rust_source: Path,
    rust_source_label: str | None = None,
) -> dict[str, Any]:
    """Compare exact inventoried Lua candidates with Rust parser mappings."""
    identity = _inventory_identity(inventory)
    rust_label = _safe_path(
        rust_source_label or rust_source.name,
        "rust_source_label",
    ).as_posix()
    rust_text = _read_stable_utf8(rust_source, "Rust source")
    normalized_rust_text = rust_text.replace("\r\n", "\n").replace("\r", "\n")
    variants, mappings = _rust_id_index(normalized_rust_text)

    scripts = _mapping(
        _mapping(inventory.get("content"), "inventory.content").get("scripts"),
        "inventory.content.scripts",
    )
    entries = scripts.get("files")
    if not isinstance(entries, list):
        raise WeaponCoverageError(
            "inventory.content.scripts.files must be an array"
        )

    seen_paths: set[str] = set()
    files = []
    definitions = []
    for index, raw_entry in enumerate(entries):
        entry = _mapping(
            raw_entry, f"inventory.content.scripts.files[{index}]"
        )
        relative = _safe_path(
            entry.get("path"),
            f"inventory.content.scripts.files[{index}].path",
        )
        path = relative.as_posix()
        if path in seen_paths:
            raise WeaponCoverageError(f"duplicate inventory script path: {path}")
        seen_paths.add(path)
        if not is_player_weapon_source(path):
            continue
        sha256 = entry.get("sha256")
        text = _read_exact_inventory_file(
            content_root,
            relative,
            expected_size=entry.get("size"),
            expected_sha256=sha256,
        )
        candidates = _lua_candidates(path, sha256, text)
        files.append(
            {
                "path": path,
                "size": entry["size"],
                "sha256": sha256,
            }
        )
        definitions.extend(candidates)
    if not files:
        raise WeaponCoverageError(
            "inventory contains no selected player-weapon Lua sources"
        )

    constructor_ids = {
        item["lua_id"]
        for item in definitions
        if item["definition_kind"].startswith("constructor")
    }
    rooted_ids = set(constructor_ids)
    aliases = [
        item for item in definitions if item["definition_kind"] == "alias"
    ]
    changed = True
    while changed:
        changed = False
        for alias in aliases:
            if (
                alias["declared_parent"] in rooted_ids
                and alias["lua_id"] not in rooted_ids
            ):
                rooted_ids.add(alias["lua_id"])
                changed = True
    definitions = [
        item
        for item in definitions
        if item["definition_kind"].startswith("constructor")
        or (
            item["lua_id"] in rooted_ids
            and item["declared_parent"] in rooted_ids
        )
    ]
    counts_by_path: dict[str, Counter[str]] = defaultdict(Counter)
    for item in definitions:
        kind = (
            "constructor_candidates"
            if item["definition_kind"].startswith("constructor")
            else "aliases"
        )
        counts_by_path[item["source_path"]][kind] += 1
    for file_record in files:
        counts = counts_by_path[file_record["path"]]
        file_record["constructor_candidates"] = counts[
            "constructor_candidates"
        ]
        file_record["aliases"] = counts["aliases"]
    files.sort(key=lambda item: item["path"])
    occurrence_counts = Counter(item["lua_id"] for item in definitions)
    candidate_ids = set(occurrence_counts)
    for item in definitions:
        lua_id = item["lua_id"]
        family_id, variant = _family(lua_id, candidate_ids)
        item["family_id"] = family_id
        item["variant"] = variant
        rust_wid = mappings.get(lua_id)
        if occurrence_counts[lua_id] > 1:
            status = "ambiguous-lua-definition"
        elif rust_wid:
            status = "exact"
        else:
            status = "absent"
        item["rust_mapping"] = {
            "status": status,
            "wid_variant": rust_wid,
            "discriminant": variants[rust_wid] if rust_wid else None,
        }
    definitions.sort(
        key=lambda item: (
            item["lua_id"],
            item["source_path"],
            item["line"],
            item["column"],
            item["definition_kind"],
        )
    )

    reverse_mappings: dict[str, list[str]] = defaultdict(list)
    for lua_id, rust_wid in mappings.items():
        reverse_mappings[rust_wid].append(lua_id)
    many_to_one = [
        {
            "wid_variant": rust_wid,
            "discriminant": variants[rust_wid],
            "lua_ids": sorted(lua_ids),
        }
        for rust_wid, lua_ids in reverse_mappings.items()
        if len(lua_ids) > 1
    ]
    many_to_one.sort(key=lambda item: item["wid_variant"])
    rust_only = [
        {
            "lua_id": lua_id,
            "wid_variant": rust_wid,
            "discriminant": variants[rust_wid],
        }
        for lua_id, rust_wid in mappings.items()
        if lua_id not in candidate_ids
    ]
    rust_only.sort(key=lambda item: item["lua_id"])
    exact_ids = {
        item["lua_id"]
        for item in definitions
        if item["rust_mapping"]["status"] == "exact"
    }
    ambiguous_ids = {
        item["lua_id"]
        for item in definitions
        if item["rust_mapping"]["status"] == "ambiguous-lua-definition"
    }
    constructor_count = sum(
        item["definition_kind"].startswith("constructor")
        for item in definitions
    )
    alias_count = len(definitions) - constructor_count
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": "lua_rust_weapon_id_index",
        "build_identity": identity,
        "inventory": {
            "selected_content_sha256": hashlib.sha256(
                json.dumps(
                    {
                        "build_identity": identity,
                        "files": [
                            {
                                "path": item["path"],
                                "size": item["size"],
                                "sha256": item["sha256"],
                            }
                            for item in files
                        ],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
        },
        "method": {
            "indexed_means": (
                "an active lexical Lua constructor/alias candidate with an "
                "optional exact direct wid_from_str arm"
            ),
            "no_exact_mapping_does_not_mean": (
                "unsupported or unimplemented; aliases, overlays, and runtime "
                "handling require review"
            ),
            "not_claimed": [
                "weapon behavior",
                "target legality",
                "upgrade equivalence",
                "WEAPONS population",
                "simulator support",
                "native helper semantics",
                "runtime load order",
            ],
        },
        "rust_source": {
            "path": rust_label,
            "normalized_utf8_sha256": hashlib.sha256(
                normalized_rust_text.encode("utf-8")
            ).hexdigest(),
            "wid_variants": len(variants),
            "wid_from_str_mappings": len(mappings),
        },
        "files": files,
        "definitions": definitions,
        "rust_only_mappings": rust_only,
        "many_to_one_wid_mappings": many_to_one,
        "summary": {
            "source_files": len(files),
            "constructor_candidates": constructor_count,
            "aliases": alias_count,
            "definition_instances": len(definitions),
            "unique_lua_ids": len(candidate_ids),
            "exact_wid_mapped_unique_ids": len(exact_ids),
            "absent_wid_mapping_unique_ids": len(
                candidate_ids - exact_ids - ambiguous_ids
            ),
            "ambiguous_lua_ids": len(ambiguous_ids),
            "rust_only_mappings": len(rust_only),
            "many_to_one_wid_variants": len(many_to_one),
        },
    }
