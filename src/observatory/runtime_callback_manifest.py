"""Validate and join bounded runtime Lua callback identities.

The game-side enumerator emits only capture-local function IDs and bounded
``debug.getinfo`` metadata.  This module treats that manifest as untrusted,
validates it strictly, and joins exact ``@scripts/...`` source/line identities
to an already build-keyed lexical callback index.  Missing, dynamic, C,
truncated, unmatched, and ambiguous identities remain explicit.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
RUNTIME_VERSION = "observatory-callback-manifest/1"
METHOD_ORDER = (
    "GetTargetArea",
    "GetTargetScore",
    "GetSkillEffect",
    "ScorePositioning",
)
STATUSES = frozenset(
    {
        "resolved",
        "c_function",
        "debug_unavailable",
        "missing",
        "function_index",
        "index_cycle",
        "depth_exceeded",
        "invalid_index",
        "protected_metatable",
        "non_function",
        "function_cap",
    }
)
JOIN_STATUSES = frozenset(
    {
        "matched",
        "ambiguous",
        "unmatched",
        "c_function",
        "debug_unavailable",
        "truncated_source",
        "unresolved_source",
        "unresolved_line",
    }
)
HARD_LIMITS = {
    "max_roots": 256,
    "max_depth": 32,
    "max_functions": 1024,
    "max_text_bytes": 1024,
}

TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "runtime_version",
        "method_order",
        "limits",
        "roots",
        "functions",
        "summary",
    }
)
LIMIT_FIELDS = frozenset(HARD_LIMITS)
ROOT_FIELDS = frozenset({"root_id", "methods"})
METHOD_FIELDS = frozenset(
    {
        "method",
        "status",
        "replaced",
        "resolution_depth",
        "function_id",
        "expected_function_id",
        "expected_truncated",
    }
)
FUNCTION_FIELDS = frozenset(
    {
        "function_id",
        "debug_status",
        "source",
        "source_truncated",
        "short_src",
        "short_src_truncated",
        "linedefined",
        "lastlinedefined",
        "what",
        "what_truncated",
        "name",
        "name_truncated",
        "namewhat",
        "namewhat_truncated",
    }
)
SUMMARY_FIELDS = frozenset(
    {
        "root_count",
        "method_count",
        "function_count",
        "replaced_count",
        "status_counts",
    }
)
CALLBACK_FIELDS = frozenset(
    {
        "symbol",
        "source_path",
        "source_sha256",
        "line",
        "column",
        "syntax",
        "categories",
        "status",
        "indexed_by",
    }
)
BUILD_IDENTITY_FIELDS = frozenset(
    {
        "platform",
        "architecture",
        "executable_sha256",
        "build_id",
        "depot_manifest",
        "scripts_revision_sha256",
        "maps_revision_sha256",
    }
)

_ROOT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class RuntimeCallbackManifestError(RuntimeError):
    """Raised when runtime callback evidence cannot be trusted or joined."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeCallbackManifestError(f"{label} must be an object")
    return value


def _sequence(value: Any, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RuntimeCallbackManifestError(f"{label} must be an array")
    return value


def _exact_fields(
    value: Any,
    expected: frozenset[str],
    label: str,
) -> Mapping[str, Any]:
    item = _mapping(value, label)
    actual = set(item)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise RuntimeCallbackManifestError(
            f"{label} missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise RuntimeCallbackManifestError(
            f"{label} has unknown fields: {', '.join(sorted(unknown))}"
        )
    return item


def _integer(
    value: Any,
    label: str,
    *,
    minimum: int = 0,
) -> int:
    if type(value) is not int or value < minimum:
        raise RuntimeCallbackManifestError(
            f"{label} must be an integer >= {minimum}"
        )
    return value


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise RuntimeCallbackManifestError(f"{label} must be boolean")
    return value


def _text(value: Any, label: str, *, allow_empty: bool = True) -> str:
    if type(value) is not str or (not allow_empty and not value):
        suffix = "text" if allow_empty else "non-empty text"
        raise RuntimeCallbackManifestError(f"{label} must be {suffix}")
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise RuntimeCallbackManifestError(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _json_copy(value: Any) -> Any:
    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeCallbackManifestError(
            f"manifest is not strict JSON data: {exc}"
        ) from exc


def _validate_function(
    raw: Any,
    index: int,
    *,
    max_text_bytes: int,
) -> dict[str, Any]:
    label = f"functions[{index}]"
    item = dict(_exact_fields(raw, FUNCTION_FIELDS, label))
    expected_id = f"fn-{index + 1:04d}"
    if item["function_id"] != expected_id:
        raise RuntimeCallbackManifestError(
            f"{label}.function_id must be {expected_id}"
        )
    debug_status = item["debug_status"]
    if debug_status not in {"available", "unavailable"}:
        raise RuntimeCallbackManifestError(
            f"invalid {label}.debug_status"
        )
    for field in ("source", "short_src", "what", "name", "namewhat"):
        value = _text(item[field], f"{label}.{field}")
        if len(value.encode("utf-8")) > max_text_bytes:
            raise RuntimeCallbackManifestError(
                f"{label}.{field} exceeds max_text_bytes"
            )
        _boolean(item[f"{field}_truncated"], f"{label}.{field}_truncated")
    for field in ("linedefined", "lastlinedefined"):
        if type(item[field]) is not int or item[field] < -1:
            raise RuntimeCallbackManifestError(
                f"{label}.{field} must be an integer >= -1"
            )
    if debug_status == "unavailable":
        if any(
            item[field]
            for field in ("source", "short_src", "what", "name", "namewhat")
        ) or any(
            item[field]
            for field in (
                "source_truncated",
                "short_src_truncated",
                "what_truncated",
                "name_truncated",
                "namewhat_truncated",
            )
        ) or item["linedefined"] != -1 or item["lastlinedefined"] != -1:
            raise RuntimeCallbackManifestError(
                f"{label} unavailable debug metadata must use empty sentinels"
            )
    elif item["what"] not in {"Lua", "C", "main"}:
        raise RuntimeCallbackManifestError(f"invalid {label}.what")
    return item


def validate_runtime_callback_manifest(manifest: Any) -> dict[str, Any]:
    """Return a detached, strictly validated runtime callback manifest."""
    root = dict(_exact_fields(manifest, TOP_LEVEL_FIELDS, "manifest"))
    if root["schema_version"] != SCHEMA_VERSION:
        raise RuntimeCallbackManifestError("unsupported manifest schema")
    if root["runtime_version"] != RUNTIME_VERSION:
        raise RuntimeCallbackManifestError("unsupported manifest runtime")
    method_order = list(_sequence(root["method_order"], "method_order"))
    if method_order != list(METHOD_ORDER):
        raise RuntimeCallbackManifestError("method_order is not canonical")

    limits_raw = _exact_fields(root["limits"], LIMIT_FIELDS, "limits")
    limits: dict[str, int] = {}
    for field, hard_limit in HARD_LIMITS.items():
        value = _integer(limits_raw[field], f"limits.{field}", minimum=1)
        if value > hard_limit:
            raise RuntimeCallbackManifestError(
                f"limits.{field} exceeds the hard limit"
            )
        limits[field] = value

    functions_raw = list(_sequence(root["functions"], "functions"))
    if len(functions_raw) > limits["max_functions"]:
        raise RuntimeCallbackManifestError("function catalog exceeds its cap")
    functions = [
        _validate_function(
            value,
            index,
            max_text_bytes=limits["max_text_bytes"],
        )
        for index, value in enumerate(functions_raw)
    ]
    by_function_id = {entry["function_id"]: entry for entry in functions}

    roots_raw = list(_sequence(root["roots"], "roots"))
    if not roots_raw or len(roots_raw) > limits["max_roots"]:
        raise RuntimeCallbackManifestError("roots violate their cap")
    seen_roots: set[str] = set()
    roots: list[dict[str, Any]] = []
    referenced: set[str] = set()
    actual_status_counts: Counter[str] = Counter()
    replaced_count = 0
    for root_index, raw_root in enumerate(roots_raw):
        label = f"roots[{root_index}]"
        item = _exact_fields(raw_root, ROOT_FIELDS, label)
        root_id = item["root_id"]
        if (
            type(root_id) is not str
            or _ROOT_ID_RE.fullmatch(root_id) is None
            or root_id in seen_roots
        ):
            raise RuntimeCallbackManifestError(f"invalid {label}.root_id")
        seen_roots.add(root_id)
        methods_raw = list(_sequence(item["methods"], f"{label}.methods"))
        if len(methods_raw) != len(METHOD_ORDER):
            raise RuntimeCallbackManifestError(
                f"{label}.methods must cover every known method"
            )
        methods: list[dict[str, Any]] = []
        for method_index, raw_method in enumerate(methods_raw):
            method_label = f"{label}.methods[{method_index}]"
            method = dict(
                _exact_fields(raw_method, METHOD_FIELDS, method_label)
            )
            if method["method"] != METHOD_ORDER[method_index]:
                raise RuntimeCallbackManifestError(
                    f"{method_label}.method is not canonical"
                )
            status = method["status"]
            if type(status) is not str or status not in STATUSES:
                raise RuntimeCallbackManifestError(
                    f"invalid {method_label}.status"
                )
            replaced = _boolean(
                method["replaced"], f"{method_label}.replaced"
            )
            expected_truncated = _boolean(
                method["expected_truncated"],
                f"{method_label}.expected_truncated",
            )
            depth = _integer(
                method["resolution_depth"],
                f"{method_label}.resolution_depth",
            )
            if depth > limits["max_depth"]:
                raise RuntimeCallbackManifestError(
                    f"{method_label}.resolution_depth exceeds its cap"
                )
            function_id = _text(
                method["function_id"], f"{method_label}.function_id"
            )
            expected_id = _text(
                method["expected_function_id"],
                f"{method_label}.expected_function_id",
            )
            for field, candidate in (
                ("function_id", function_id),
                ("expected_function_id", expected_id),
            ):
                if candidate and candidate not in by_function_id:
                    raise RuntimeCallbackManifestError(
                        f"{method_label}.{field} is not cataloged"
                    )
                if candidate:
                    referenced.add(candidate)
            if status in {"resolved", "c_function", "debug_unavailable"}:
                if not function_id:
                    raise RuntimeCallbackManifestError(
                        f"{method_label} resolved status requires function_id"
                    )
                metadata = by_function_id[function_id]
                if status == "resolved" and (
                    metadata["debug_status"] != "available"
                    or metadata["what"] == "C"
                ):
                    raise RuntimeCallbackManifestError(
                        f"{method_label} resolved status contradicts metadata"
                    )
                if status == "c_function" and (
                    metadata["debug_status"] != "available"
                    or metadata["what"] != "C"
                ):
                    raise RuntimeCallbackManifestError(
                        f"{method_label} C status contradicts metadata"
                    )
                if status == "debug_unavailable" and (
                    metadata["debug_status"] != "unavailable"
                ):
                    raise RuntimeCallbackManifestError(
                        f"{method_label} debug status contradicts metadata"
                    )
            elif function_id:
                raise RuntimeCallbackManifestError(
                    f"{method_label} unresolved status cannot name a function"
                )
            if not expected_truncated:
                if not expected_id and replaced:
                    raise RuntimeCallbackManifestError(
                        f"{method_label} cannot be replaced without an "
                        "expected callback"
                    )
                if expected_id and replaced != (function_id != expected_id):
                    raise RuntimeCallbackManifestError(
                        f"{method_label}.replaced contradicts function identity"
                    )
            replaced_count += int(replaced)
            actual_status_counts[status] += 1
            methods.append(method)
        roots.append({"root_id": root_id, "methods": methods})

    if referenced != set(by_function_id):
        raise RuntimeCallbackManifestError(
            "function catalog contains unreferenced identities"
        )

    summary = dict(_exact_fields(root["summary"], SUMMARY_FIELDS, "summary"))
    expected_counts = {
        status: actual_status_counts[status] for status in sorted(STATUSES)
    }
    counts_raw = _exact_fields(
        summary["status_counts"], frozenset(STATUSES), "summary.status_counts"
    )
    counts = {
        status: _integer(
            counts_raw[status], f"summary.status_counts.{status}"
        )
        for status in sorted(STATUSES)
    }
    expected_summary = {
        "root_count": len(roots),
        "method_count": len(roots) * len(METHOD_ORDER),
        "function_count": len(functions),
        "replaced_count": replaced_count,
    }
    for field, expected in expected_summary.items():
        if summary[field] != expected:
            raise RuntimeCallbackManifestError(
                f"summary.{field} does not reconcile"
            )
    if counts != expected_counts:
        raise RuntimeCallbackManifestError(
            "summary.status_counts do not reconcile"
        )

    validated = {
        "schema_version": SCHEMA_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "method_order": list(METHOD_ORDER),
        "limits": limits,
        "roots": roots,
        "functions": functions,
        "summary": {**expected_summary, "status_counts": counts},
    }
    return _json_copy(validated)


def _safe_inventory_path(value: Any, label: str) -> str:
    if type(value) is not str or not value or "\\" in value:
        raise RuntimeCallbackManifestError(
            f"{label} must be a normalized relative path"
        )
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or path.as_posix() != value
    ):
        raise RuntimeCallbackManifestError(
            f"{label} must be a normalized relative path"
        )
    return value


def _inventory_identity_and_scripts(
    inventory: Any,
) -> tuple[dict[str, Any], dict[str, str]]:
    root = _mapping(inventory, "inventory")
    executable = _mapping(root.get("executable"), "inventory.executable")
    steam = _mapping(root.get("steam"), "inventory.steam")
    content = _mapping(root.get("content"), "inventory.content")
    scripts = _mapping(content.get("scripts"), "inventory.content.scripts")
    maps = _mapping(content.get("maps"), "inventory.content.maps")
    depots = steam.get("installed_depots")
    if not isinstance(depots, list) or len(depots) != 1:
        raise RuntimeCallbackManifestError(
            "inventory must name exactly one installed depot"
        )
    depot = _mapping(depots[0], "inventory.steam.installed_depots[0]")
    identity = {
        "platform": root.get("platform"),
        "architecture": executable.get("architecture"),
        "executable_sha256": executable.get("sha256"),
        "build_id": steam.get("build_id"),
        "depot_manifest": depot.get("manifest"),
        "scripts_revision_sha256": scripts.get("revision_sha256"),
        "maps_revision_sha256": maps.get("revision_sha256"),
    }
    _exact_fields(identity, BUILD_IDENTITY_FIELDS, "inventory build identity")
    for field in (
        "executable_sha256",
        "scripts_revision_sha256",
        "maps_revision_sha256",
    ):
        _sha256(identity[field], f"inventory build identity.{field}")
    for field in ("platform", "architecture", "build_id", "depot_manifest"):
        _text(
            identity[field],
            f"inventory build identity.{field}",
            allow_empty=False,
        )
    files = scripts.get("files")
    if not isinstance(files, list):
        raise RuntimeCallbackManifestError(
            "inventory.content.scripts.files must be an array"
        )
    by_path: dict[str, str] = {}
    for index, raw_file in enumerate(files):
        label = f"inventory.content.scripts.files[{index}]"
        entry = _mapping(raw_file, label)
        path = _safe_inventory_path(entry.get("path"), f"{label}.path")
        digest = _sha256(entry.get("sha256"), f"{label}.sha256")
        _integer(entry.get("size"), f"{label}.size")
        if path in by_path:
            raise RuntimeCallbackManifestError(
                f"duplicate inventory script path: {path}"
            )
        by_path[path] = digest
    return _json_copy(identity), by_path


def _validate_callback_index(
    callback_index: Any,
    *,
    expected_identity: Mapping[str, Any],
    inventory_scripts: Mapping[str, str],
) -> list[dict[str, Any]]:
    root = _mapping(callback_index, "callback index")
    if root.get("schema_version") != 1 or root.get("analysis_kind") != (
        "lua_callback_provenance_index"
    ):
        raise RuntimeCallbackManifestError("unsupported callback index")
    identity = dict(
        _exact_fields(
            root.get("build_identity"),
            BUILD_IDENTITY_FIELDS,
            "callback index build_identity",
        )
    )
    if type(identity) is not type(expected_identity) or identity != dict(
        expected_identity
    ):
        raise RuntimeCallbackManifestError(
            "callback index build identity does not match inventory"
        )
    callbacks_raw = root.get("callbacks")
    if not isinstance(callbacks_raw, list):
        raise RuntimeCallbackManifestError("callback index callbacks must be an array")
    callbacks: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for index, raw in enumerate(callbacks_raw):
        label = f"callback index callbacks[{index}]"
        item = dict(_exact_fields(raw, CALLBACK_FIELDS, label))
        path = _safe_inventory_path(item["source_path"], f"{label}.source_path")
        digest = _sha256(item["source_sha256"], f"{label}.source_sha256")
        if inventory_scripts.get(path) != digest:
            raise RuntimeCallbackManifestError(
                f"{label} does not match the exact inventory file"
            )
        _text(item["symbol"], f"{label}.symbol", allow_empty=False)
        _integer(item["line"], f"{label}.line", minimum=1)
        _integer(item["column"], f"{label}.column", minimum=1)
        if item["syntax"] not in {"declaration", "assignment"}:
            raise RuntimeCallbackManifestError(f"invalid {label}.syntax")
        for field in ("categories", "indexed_by"):
            values = list(_sequence(item[field], f"{label}.{field}"))
            if any(type(value) is not str or not value for value in values):
                raise RuntimeCallbackManifestError(
                    f"{label}.{field} must contain non-empty text"
                )
            item[field] = values
        if item["status"] not in {"indexed", "unindexed"}:
            raise RuntimeCallbackManifestError(f"invalid {label}.status")
        key = (
            path,
            digest,
            item["line"],
            item["column"],
            item["symbol"],
            item["syntax"],
        )
        if key in seen:
            raise RuntimeCallbackManifestError(
                f"duplicate callback index identity: {key}"
            )
        seen.add(key)
        callbacks.append(item)
    return callbacks


def _debug_source_path(metadata: Mapping[str, Any]) -> tuple[str | None, str]:
    if metadata["source_truncated"]:
        return None, "truncated_source"
    source = metadata["source"]
    if not source.startswith("@"):
        return None, "unresolved_source"
    candidate = source[1:]
    try:
        return _safe_inventory_path(candidate, "runtime debug source"), ""
    except RuntimeCallbackManifestError:
        return None, "unresolved_source"


def join_runtime_callback_manifest(
    manifest: Any,
    callback_index: Any,
    inventory: Any,
) -> dict[str, Any]:
    """Join runtime function metadata to exact lexical callback identities."""
    validated = validate_runtime_callback_manifest(manifest)
    identity, scripts = _inventory_identity_and_scripts(inventory)
    callbacks = _validate_callback_index(
        callback_index,
        expected_identity=identity,
        inventory_scripts=scripts,
    )
    callbacks_by_location: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for callback in callbacks:
        callbacks_by_location.setdefault(
            (callback["source_path"], callback["line"]), []
        ).append(callback)

    joins: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for metadata in validated["functions"]:
        path = ""
        digest = ""
        matches: list[dict[str, Any]] = []
        if metadata["debug_status"] == "unavailable":
            status = "debug_unavailable"
        elif metadata["what"] == "C":
            status = "c_function"
        else:
            normalized, path_error = _debug_source_path(metadata)
            if normalized is None:
                status = path_error
            elif metadata["linedefined"] < 1:
                path = normalized
                digest = scripts.get(path, "")
                status = "unresolved_line"
            else:
                path = normalized
                digest = scripts.get(path, "")
                if not digest:
                    status = "unmatched"
                else:
                    matches = [
                        _json_copy(item)
                        for item in callbacks_by_location.get(
                            (path, metadata["linedefined"]), []
                        )
                    ]
                    if len(matches) == 1:
                        status = "matched"
                    elif len(matches) > 1:
                        status = "ambiguous"
                    else:
                        status = "unmatched"
        if status not in JOIN_STATUSES:
            raise RuntimeCallbackManifestError(
                f"internal invalid join status: {status}"
            )
        counts[status] += 1
        joins.append(
            {
                "function_id": metadata["function_id"],
                "join_status": status,
                "source_path": path,
                "source_sha256": digest,
                "matches": matches,
            }
        )

    result = {
        "schema_version": 1,
        "analysis_kind": "runtime_callback_identity_join",
        "build_identity": identity,
        "runtime_manifest": validated,
        "function_joins": joins,
        "summary": {
            "function_count": len(joins),
            "join_status_counts": {
                status: counts[status] for status in sorted(JOIN_STATUSES)
            },
        },
    }
    return _json_copy(result)
