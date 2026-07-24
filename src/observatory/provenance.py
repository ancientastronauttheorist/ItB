"""Validation for build-keyed Lua-to-Rust mechanics provenance records."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
ALLOWED_COVERAGE = {"verified", "partial", "gap", "native_dependency"}
ALLOWED_EVIDENCE = {"fact", "inference", "hypothesis", "unresolved"}
TOP_LEVEL_FIELDS = {
    "schema_version",
    "build_identity",
    "inventory",
    "records",
}
IDENTITY_FIELDS = {
    "platform",
    "architecture",
    "executable_sha256",
    "build_id",
    "depot_manifest",
    "scripts_revision_sha256",
    "maps_revision_sha256",
}
RECORD_FIELDS = {
    "id",
    "coverage",
    "sources",
    "implementations",
    "tests",
    "evidence",
    "known_gaps",
}
SOURCE_FIELDS = {"path", "sha256", "symbols"}
REPO_REFERENCE_FIELDS = {"path", "symbols"}
EVIDENCE_FIELDS = {"classification", "statement"}
_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProvenanceError(RuntimeError):
    """Raised when provenance is ambiguous, stale, or structurally invalid."""


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProvenanceError(f"{label} must be an object")
    return value


def _exact_fields(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise ProvenanceError(
            f"{label} missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise ProvenanceError(
            f"{label} has unknown fields: {', '.join(sorted(unknown))}"
        )


def _string_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(type(item) is not str or not item for item in value)
        or len(set(value)) != len(value)
    ):
        qualifier = "possibly empty " if allow_empty else "non-empty "
        raise ProvenanceError(f"{label} must be a {qualifier}string array")
    return value


def _safe_repo_path(value: Any, label: str) -> PurePosixPath:
    if type(value) is not str or not value or "\\" in value:
        raise ProvenanceError(f"{label} must be a normalized relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ProvenanceError(f"{label} must stay within the repository")
    if path.as_posix() != value:
        raise ProvenanceError(f"{label} must be slash-normalized")
    return path


def _resolve_repo_file(repo_root: Path, path: PurePosixPath, label: str) -> Path:
    root = repo_root.resolve()
    resolved = root.joinpath(*path.parts).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ProvenanceError(f"{label} is not a repository file: {path}")
    return resolved


def _same_json_value(left: Any, right: Any) -> bool:
    """Compare parsed JSON values without Python's bool/int coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        if (
            len(left) != len(right)
            or any(type(key) is not str for key in left)
            or any(type(key) is not str for key in right)
            or set(left) != set(right)
        ):
            return False
        return all(_same_json_value(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same_json_value(a, b) for a, b in zip(left, right)
        )
    return left == right


def _inventory_identity(inventory: Mapping[str, Any]) -> dict[str, Any]:
    steam = _require_mapping(inventory.get("steam"), "inventory.steam")
    executable = _require_mapping(
        inventory.get("executable"), "inventory.executable"
    )
    content = _require_mapping(inventory.get("content"), "inventory.content")
    scripts = _require_mapping(
        content.get("scripts"), "inventory.content.scripts"
    )
    maps = _require_mapping(content.get("maps"), "inventory.content.maps")
    depots = steam.get("installed_depots")
    if not isinstance(depots, list) or not depots:
        raise ProvenanceError(
            "inventory.steam.installed_depots must be non-empty"
        )
    first_depot = _require_mapping(
        depots[0], "inventory.steam.installed_depots[0]"
    )
    return {
        "platform": inventory.get("platform"),
        "architecture": executable.get("architecture"),
        "executable_sha256": executable.get("sha256"),
        "build_id": steam.get("build_id"),
        "depot_manifest": first_depot.get("manifest"),
        "scripts_revision_sha256": scripts.get("revision_sha256"),
        "maps_revision_sha256": maps.get("revision_sha256"),
    }


def _validate_identity(identity: Mapping[str, Any], label: str) -> None:
    _exact_fields(identity, IDENTITY_FIELDS, label)
    for key in (
        "platform",
        "architecture",
    ):
        if type(identity[key]) is not str or not identity[key]:
            raise ProvenanceError(f"{label}.{key} must be non-empty text")
    for key in ("build_id", "depot_manifest"):
        if type(identity[key]) is not str or not identity[key].isdigit():
            raise ProvenanceError(f"{label}.{key} must be numeric text")
    for key in (
        "executable_sha256",
        "scripts_revision_sha256",
        "maps_revision_sha256",
    ):
        if (
            type(identity[key]) is not str
            or not _SHA256_RE.fullmatch(identity[key])
        ):
            raise ProvenanceError(f"{label}.{key} must be lowercase SHA-256")


def _validate_repo_references(
    references: Any,
    *,
    label: str,
    repo_root: Path | None,
) -> list[Mapping[str, Any]]:
    if not isinstance(references, list):
        raise ProvenanceError(f"{label} must be an array")
    result = []
    for index, raw_reference in enumerate(references):
        item_label = f"{label}[{index}]"
        reference = _require_mapping(raw_reference, item_label)
        _exact_fields(reference, REPO_REFERENCE_FIELDS, item_label)
        path = _safe_repo_path(reference["path"], f"{item_label}.path")
        _string_list(reference["symbols"], f"{item_label}.symbols")
        if repo_root is not None:
            _resolve_repo_file(repo_root, path, f"{item_label}.path")
        result.append(reference)
    return result


def validate_provenance(
    provenance: Mapping[str, Any],
    inventory: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, int]:
    """Validate provenance against the exact inventory it claims to describe."""
    provenance = _require_mapping(provenance, "provenance")
    inventory = _require_mapping(inventory, "inventory")
    _exact_fields(provenance, TOP_LEVEL_FIELDS, "provenance")
    if (
        type(provenance["schema_version"]) is not int
        or provenance["schema_version"] != SCHEMA_VERSION
    ):
        raise ProvenanceError(
            f"unsupported provenance schema: "
            f"{provenance['schema_version']!r}"
        )
    claimed_identity = _require_mapping(
        provenance["build_identity"],
        "build_identity",
    )
    _validate_identity(claimed_identity, "build_identity")
    actual_identity = _inventory_identity(inventory)
    _validate_identity(actual_identity, "inventory identity")
    for key, actual in actual_identity.items():
        if claimed_identity[key] != actual:
            raise ProvenanceError(
                f"build_identity.{key} does not match inventory: "
                f"{claimed_identity[key]!r} != {actual!r}"
            )

    inventory_reference = _safe_repo_path(
        provenance["inventory"], "provenance.inventory"
    )
    if repo_root is not None:
        referenced_path = _resolve_repo_file(
            repo_root,
            inventory_reference,
            "provenance.inventory",
        )
        referenced_inventory = load_json_object(referenced_path)
        if not _same_json_value(referenced_inventory, dict(inventory)):
            raise ProvenanceError(
                "provenance.inventory content differs from supplied inventory"
            )

    inventory_content = _require_mapping(
        inventory.get("content"), "inventory.content"
    )
    inventory_scripts = _require_mapping(
        inventory_content.get("scripts"),
        "inventory.content.scripts",
    )
    inventory_files = inventory_scripts.get("files")
    if not isinstance(inventory_files, list):
        raise ProvenanceError("inventory scripts files must be an array")
    source_entries: dict[str, Mapping[str, Any]] = {}
    for index, entry in enumerate(inventory_files):
        entry = _require_mapping(entry, f"inventory script file {index}")
        path = entry.get("path")
        if type(path) is not str or path in source_entries:
            raise ProvenanceError(
                "inventory script paths must be unique strings"
            )
        source_entries[path] = entry

    records = provenance["records"]
    if not isinstance(records, list) or not records:
        raise ProvenanceError("records must be a non-empty array")

    seen_ids: set[str] = set()
    counts = {status: 0 for status in sorted(ALLOWED_COVERAGE)}
    for index, raw_record in enumerate(records):
        record = _require_mapping(raw_record, f"records[{index}]")
        _exact_fields(record, RECORD_FIELDS, f"records[{index}]")
        record_id = record["id"]
        if type(record_id) is not str or not _ID_RE.fullmatch(record_id):
            raise ProvenanceError(
                f"records[{index}].id must be lowercase kebab-case"
            )
        if record_id in seen_ids:
            raise ProvenanceError(f"duplicate provenance id: {record_id}")
        seen_ids.add(record_id)

        coverage = record["coverage"]
        if type(coverage) is not str or coverage not in ALLOWED_COVERAGE:
            raise ProvenanceError(
                f"{record_id}: invalid coverage {coverage!r}"
            )
        counts[str(coverage)] += 1

        sources = record["sources"]
        if not isinstance(sources, list) or not sources:
            raise ProvenanceError(f"{record_id}: sources must be non-empty")
        seen_sources: set[str] = set()
        for source_index, raw_source in enumerate(sources):
            label = f"{record_id}.sources[{source_index}]"
            source = _require_mapping(raw_source, label)
            _exact_fields(source, SOURCE_FIELDS, label)
            path = _safe_repo_path(source["path"], f"{label}.path").as_posix()
            if not path.startswith("scripts/"):
                raise ProvenanceError(
                    f"{record_id}: source must be under scripts/: {path}"
                )
            if path in seen_sources:
                raise ProvenanceError(
                    f"{record_id}: duplicate source path: {path}"
                )
            seen_sources.add(path)
            if path not in source_entries:
                raise ProvenanceError(
                    f"{record_id}: source is absent from inventory: {path}"
                )
            actual_hash = source_entries[path].get("sha256")
            if (
                type(source["sha256"]) is not str
                or not _SHA256_RE.fullmatch(source["sha256"])
                or source["sha256"] != actual_hash
            ):
                raise ProvenanceError(
                    f"{record_id}: stale source hash for {path}: "
                    f"{source['sha256']!r} != {actual_hash!r}"
                )
            _string_list(source["symbols"], f"{label}.symbols")

        evidence = record["evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise ProvenanceError(f"{record_id}: evidence must be non-empty")
        for evidence_index, raw_item in enumerate(evidence):
            label = f"{record_id}.evidence[{evidence_index}]"
            item = _require_mapping(raw_item, label)
            _exact_fields(item, EVIDENCE_FIELDS, label)
            if (
                type(item["classification"]) is not str
                or item["classification"] not in ALLOWED_EVIDENCE
            ):
                raise ProvenanceError(
                    f"{record_id}: invalid evidence classification "
                    f"{item['classification']!r}"
                )
            if type(item["statement"]) is not str or not item["statement"]:
                raise ProvenanceError(f"{record_id}: empty evidence statement")

        implementations = _validate_repo_references(
            record["implementations"],
            label=f"{record_id}.implementations",
            repo_root=repo_root,
        )
        tests = _validate_repo_references(
            record["tests"],
            label=f"{record_id}.tests",
            repo_root=repo_root,
        )
        if coverage == "verified" and (not implementations or not tests):
            raise ProvenanceError(
                f"{record_id}: verified coverage requires "
                "implementations and tests"
            )
        if coverage == "verified" and not any(
            item["classification"] == "fact" for item in evidence
        ):
            raise ProvenanceError(
                f"{record_id}: verified coverage requires "
                "fact-classified evidence"
            )

        gaps = _string_list(
            record["known_gaps"],
            f"{record_id}.known_gaps",
            allow_empty=True,
        )
        if coverage != "verified" and not gaps:
            raise ProvenanceError(
                f"{record_id}: non-verified coverage requires known_gaps"
            )
        if coverage == "verified" and gaps:
            raise ProvenanceError(
                f"{record_id}: verified coverage cannot declare known_gaps"
            )
    return counts


class _DuplicateKeyError(ValueError):
    pass


def _object_without_duplicates(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, _DuplicateKeyError, ValueError) as exc:
        raise ProvenanceError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProvenanceError(f"{path} must contain a JSON object")
    return data
