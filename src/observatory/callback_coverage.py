"""Build-keyed lexical coverage of high-value shipped Lua callbacks.

This module answers a deliberately narrow question: which active top-level
Lua function declarations are named exactly by the mechanics provenance index?
It does not infer inheritance, runtime reachability, Rust behavior, or
conformance.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from src.observatory.provenance import (
    source_audit_categories,
    validate_provenance,
)
from src.observatory.weapon_coverage import (
    WeaponCoverageError,
    lua_brace_depths,
    lua_function_spans,
    mask_lua_opaque,
    read_exact_inventory_file,
    source_position,
)


SCHEMA_VERSION = 1
_IDENTIFIER = r"[A-Za-z][A-Za-z0-9_]*"
_DECLARATION_NAME = rf"{_IDENTIFIER}(?:\.{_IDENTIFIER})*(?::{_IDENTIFIER})?"
_ASSIGNMENT_NAME = rf"{_IDENTIFIER}(?:\.{_IDENTIFIER})*"
_FUNCTION_DECL_RE = re.compile(
    rf"^[ \t]*function[ \t\r\n]+({_DECLARATION_NAME})[ \t\r\n]*\(",
    re.MULTILINE,
)
_FUNCTION_ASSIGN_RE = re.compile(
    rf"^[ \t]*({_ASSIGNMENT_NAME})[ \t]*="
    rf"[ \t\r\n]*function[ \t\r\n]*\(",
    re.MULTILINE,
)


class CallbackCoverageError(RuntimeError):
    """Raised when exact callback coverage inputs cannot be trusted."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CallbackCoverageError(f"{label} must be an object")
    return value


def _safe_inventory_path(value: Any, label: str) -> PurePosixPath:
    if type(value) is not str or not value or "\\" in value:
        raise CallbackCoverageError(
            f"{label} must be a normalized relative path"
        )
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or path.as_posix() != value
    ):
        raise CallbackCoverageError(
            f"{label} must be a normalized relative path"
        )
    return path


def _inside_outer_function(
    offset: int,
    spans: list[tuple[int, int]],
) -> bool:
    return any(start < offset < end for start, end in spans)


def _preceded_by_local(masked: str, offset: int) -> bool:
    match = re.search(r"([A-Za-z][A-Za-z0-9_]*)[ \t\r\n]*$", masked[:offset])
    return bool(match and match.group(1) == "local")


def _extract_callbacks(
    path: str,
    sha256: str,
    text: str,
    categories: list[str],
) -> list[dict[str, Any]]:
    try:
        masked = mask_lua_opaque(text)
        spans = lua_function_spans(masked)
        brace_depths = lua_brace_depths(masked)
    except WeaponCoverageError as exc:
        raise CallbackCoverageError(f"{path}: {exc}") from exc

    callbacks = []
    occupied: set[tuple[int, str]] = set()
    for syntax, pattern in (
        ("declaration", _FUNCTION_DECL_RE),
        ("assignment", _FUNCTION_ASSIGN_RE),
    ):
        for match in pattern.finditer(masked):
            symbol = match.group(1)
            key = (match.start(1), symbol)
            if key in occupied:
                continue
            if (
                brace_depths[match.start()] != 0
                or _inside_outer_function(match.start(), spans)
                or _preceded_by_local(masked, match.start())
            ):
                continue
            occupied.add(key)
            line, column = source_position(text, match.start(1))
            callbacks.append(
                {
                    "symbol": symbol,
                    "source_path": path,
                    "source_sha256": sha256,
                    "line": line,
                    "column": column,
                    "syntax": syntax,
                    "categories": list(categories),
                }
            )
    callbacks.sort(
        key=lambda item: (
            item["line"],
            item["column"],
            item["symbol"],
            item["syntax"],
        )
    )
    return callbacks


def analyze_lua_callback_provenance(
    provenance: Mapping[str, Any],
    inventory: Mapping[str, Any],
    *,
    content_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    """Join exact Lua callback declarations to exact provenance symbols."""
    validate_provenance(provenance, inventory, repo_root=repo_root)
    scripts = _mapping(
        _mapping(inventory.get("content"), "inventory.content").get("scripts"),
        "inventory.content.scripts",
    )
    entries = scripts.get("files")
    if not isinstance(entries, list):
        raise CallbackCoverageError(
            "inventory.content.scripts.files must be an array"
        )

    indexed_by: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    record_details = {}
    for record in provenance["records"]:
        record_details[record["id"]] = {
            "id": record["id"],
            "coverage": record["coverage"],
            "implementations": record["implementations"],
            "tests": record["tests"],
        }
        for source in record["sources"]:
            for symbol in source["symbols"]:
                if "*" in symbol or any(
                    character.isspace() for character in symbol
                ):
                    continue
                indexed_by[
                    (source["path"], source["sha256"], symbol)
                ].add(record["id"])

    seen_paths: set[str] = set()
    files = []
    callbacks = []
    for index, raw_entry in enumerate(entries):
        entry = _mapping(
            raw_entry,
            f"inventory.content.scripts.files[{index}]",
        )
        relative = _safe_inventory_path(
            entry.get("path"),
            f"inventory.content.scripts.files[{index}].path",
        )
        path = relative.as_posix()
        if path in seen_paths:
            raise CallbackCoverageError(
                f"duplicate inventory script path: {path}"
            )
        seen_paths.add(path)
        categories = source_audit_categories(path)
        if not categories:
            continue
        try:
            text = read_exact_inventory_file(
                content_root,
                relative,
                expected_size=entry.get("size"),
                expected_sha256=entry.get("sha256"),
            )
        except WeaponCoverageError as exc:
            raise CallbackCoverageError(str(exc)) from exc
        file_callbacks = _extract_callbacks(
            path,
            entry["sha256"],
            text,
            categories,
        )
        indexed_count = 0
        for callback in file_callbacks:
            records = sorted(
                indexed_by.get(
                    (
                        callback["source_path"],
                        callback["source_sha256"],
                        callback["symbol"],
                    ),
                    (),
                )
            )
            callback["status"] = "indexed" if records else "unindexed"
            callback["indexed_by"] = records
            indexed_count += bool(records)
        files.append(
            {
                "path": path,
                "size": entry["size"],
                "sha256": entry["sha256"],
                "categories": categories,
                "callbacks": len(file_callbacks),
                "indexed_callbacks": indexed_count,
                "unindexed_callbacks": len(file_callbacks) - indexed_count,
            }
        )
        callbacks.extend(file_callbacks)

    files.sort(key=lambda item: item["path"])
    callbacks.sort(
        key=lambda item: (
            item["source_path"],
            item["line"],
            item["column"],
            item["symbol"],
        )
    )
    category_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for callback in callbacks:
        for category in callback["categories"]:
            category_counts[category]["callbacks"] += 1
            category_counts[category][callback["status"]] += 1
    categories = [
        {
            "category": category,
            "callbacks": counts["callbacks"],
            "indexed_callbacks": counts["indexed"],
            "unindexed_callbacks": counts["unindexed"],
        }
        for category, counts in sorted(category_counts.items())
    ]
    used_record_ids = sorted(
        {
            record_id
            for callback in callbacks
            for record_id in callback["indexed_by"]
        }
    )
    indexed_callbacks = sum(
        callback["status"] == "indexed" for callback in callbacks
    )
    unique_path_symbols = len(
        {
            (callback["source_path"], callback["symbol"])
            for callback in callbacks
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": "lua_callback_provenance_index",
        "build_identity": dict(provenance["build_identity"]),
        "method": {
            "indexed_means": (
                "the exact top-level Lua callback path, source hash, and "
                "symbol appear in at least one validated provenance record"
            ),
            "unindexed_does_not_mean": (
                "unsupported, unimplemented, or behaviorally incorrect"
            ),
            "not_claimed": [
                "runtime reachability",
                "inheritance coverage",
                "Rust implementation equivalence",
                "test adequacy",
                "native helper semantics",
                "behavioral conformance",
            ],
            "callback_scope": (
                "active top-level named function declarations and assignments "
                "in high-value source-audit files"
            ),
            "category_totals": (
                "categories overlap; mission-environment callback definitions "
                "contribute to both applicable category totals"
            ),
        },
        "files": files,
        "callbacks": callbacks,
        "categories": categories,
        "provenance_records": [
            record_details[record_id] for record_id in used_record_ids
        ],
        "summary": {
            "source_files": len(files),
            "callback_definitions": len(callbacks),
            "unique_path_symbols": unique_path_symbols,
            "indexed_callbacks": indexed_callbacks,
            "unindexed_callbacks": len(callbacks) - indexed_callbacks,
            "provenance_records_used": len(used_record_ids),
        },
    }
