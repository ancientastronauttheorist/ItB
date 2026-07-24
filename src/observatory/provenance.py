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
SOURCE_AUDIT_CATEGORIES = (
    (
        "spawn-selection",
        "Spawner selection and Advanced Edition spawn-count policy.",
    ),
    (
        "enemy-scoring",
        "Base and Advanced Edition enemy target-scoring policy.",
    ),
    (
        "enemy-weapons",
        "Base and Advanced Edition enemy weapon Lua.",
    ),
    (
        "player-weapons",
        "Base and Advanced Edition non-enemy weapon Lua.",
    ),
    (
        "missions",
        "Base and Advanced Edition mission Lua.",
    ),
    (
        "environments",
        "Global and mission-specific environment Lua.",
    ),
)
ENVIRONMENT_SOURCE_PATHS = {
    "scripts/environments.lua",
    "scripts/advanced/missions/acid/mission_acidstorm.lua",
    "scripts/advanced/missions/acid/mission_nanostorm.lua",
    "scripts/advanced/missions/sand/mission_terratide.lua",
    "scripts/advanced/missions/sand/mission_wind.lua",
    "scripts/missions/final/env_final.lua",
    "scripts/missions/final/env_volcano.lua",
    "scripts/missions/acid/mission_belt.lua",
    "scripts/missions/grass/mission_tides.lua",
    "scripts/missions/grass/mission_airstrike.lua",
    "scripts/missions/sand/mission_cataclysm.lua",
    "scripts/missions/sand/mission_lightning.lua",
    "scripts/missions/sand/mission_sandstorm.lua",
    "scripts/missions/sand/mission_wind.lua",
    "scripts/missions/snow/mission_snowstorm.lua",
}


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


def _literal_reference_symbol(symbol: str) -> bool:
    """Whether a repository symbol is intended as an exact textual anchor."""
    return "*" not in symbol and not any(
        character.isspace() for character in symbol
    )


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
        symbols = _string_list(reference["symbols"], f"{item_label}.symbols")
        if any(symbol != symbol.strip() for symbol in symbols):
            raise ProvenanceError(
                f"{item_label}.symbols entries must not have leading or "
                "trailing whitespace"
            )
        if repo_root is not None:
            resolved = _resolve_repo_file(
                repo_root,
                path,
                f"{item_label}.path",
            )
            text = resolved.read_text(encoding="utf-8", errors="replace")
            for symbol in symbols:
                if _literal_reference_symbol(symbol) and symbol not in text:
                    raise ProvenanceError(
                        f"{item_label}.symbols anchor is absent from "
                        f"{path}: {symbol}"
                    )
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


def _source_audit_category(path: str, category: str) -> bool:
    if category == "spawn-selection":
        return path in {
            "scripts/spawner.lua",
            "scripts/spawner_backend.lua",
            "scripts/advanced/ae_spawner_backend.lua",
        }
    if category == "enemy-scoring":
        return path in {
            "scripts/global.lua",
            "scripts/advanced/ae_global.lua",
        }
    if category == "enemy-weapons":
        return path in {
            "scripts/weapons_enemy.lua",
            "scripts/advanced/ae_weapons_enemy.lua",
        }
    if category == "player-weapons":
        return is_player_weapon_source(path)
    if category == "missions":
        return (
            path.startswith("scripts/missions/")
            or path.startswith("scripts/advanced/missions/")
        ) and path.endswith(".lua")
    if category == "environments":
        return path in ENVIRONMENT_SOURCE_PATHS
    raise ProvenanceError(f"unknown source audit category: {category}")


def is_player_weapon_source(path: str) -> bool:
    """Return whether an inventory path is selected for player-weapon audit."""
    base = (
        path.startswith("scripts/weapons_")
        and path.endswith(".lua")
        and path
        not in {
            "scripts/weapons_enemy.lua",
            "scripts/weapons_mission.lua",
        }
    )
    advanced = (
        path.startswith("scripts/advanced/ae_weapons")
        and path.endswith(".lua")
        and path != "scripts/advanced/ae_weapons_enemy.lua"
    )
    return base or advanced


def audit_provenance_sources(
    provenance: Mapping[str, Any],
    inventory: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Report high-value shipped Lua files absent from the provenance index.

    A file being indexed is not a claim that its behavior is implemented or
    verified. Coverage status remains record-level evidence in the provenance
    document.
    """
    validate_provenance(
        provenance,
        inventory,
        repo_root=repo_root,
    )
    indexed_by: dict[str, list[str]] = {}
    for record in provenance["records"]:
        for source in record["sources"]:
            indexed_by.setdefault(source["path"], []).append(record["id"])

    inventory_scripts = inventory["content"]["scripts"]["files"]
    script_entries: list[dict[str, str]] = []
    for index, raw_entry in enumerate(inventory_scripts):
        entry = _require_mapping(
            raw_entry, f"inventory script file {index}"
        )
        path = _safe_repo_path(
            entry.get("path"), f"inventory script file {index}.path"
        ).as_posix()
        sha256 = entry.get("sha256")
        if (
            type(sha256) is not str
            or not _SHA256_RE.fullmatch(sha256)
        ):
            raise ProvenanceError(
                f"inventory script file {index}.sha256 is invalid"
            )
        script_entries.append({"path": path, "sha256": sha256})

    categories = []
    all_candidate_paths: set[str] = set()
    all_indexed_paths: set[str] = set()
    for category, scope in SOURCE_AUDIT_CATEGORIES:
        files = []
        for entry in script_entries:
            if not _source_audit_category(entry["path"], category):
                continue
            records = sorted(indexed_by.get(entry["path"], []))
            files.append(
                {
                    "path": entry["path"],
                    "sha256": entry["sha256"],
                    "status": "indexed" if records else "unindexed",
                    "indexed_by": records,
                }
            )
            all_candidate_paths.add(entry["path"])
            if records:
                all_indexed_paths.add(entry["path"])
        files.sort(key=lambda item: item["path"])
        indexed_count = sum(item["status"] == "indexed" for item in files)
        categories.append(
            {
                "category": category,
                "scope": scope,
                "candidate_files": len(files),
                "indexed_files": indexed_count,
                "unindexed_files": len(files) - indexed_count,
                "files": files,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": "provenance_source_index_audit",
        "build_identity": dict(provenance["build_identity"]),
        "method": {
            "indexed_means": (
                "the exact file hash appears in at least one provenance record"
            ),
            "indexed_does_not_mean": (
                "the Lua behavior is implemented, conformant, or verified"
            ),
            "summary_counts": (
                "unique file paths across potentially overlapping categories"
            ),
        },
        "categories": categories,
        "summary": {
            "candidate_files": len(all_candidate_paths),
            "indexed_files": len(all_indexed_paths),
            "unindexed_files": len(all_candidate_paths - all_indexed_paths),
        },
    }


def audit_provenance_gaps(
    provenance: Mapping[str, Any],
    inventory: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Return a deterministic, build-keyed queue of open provenance gaps."""
    coverage = validate_provenance(
        provenance,
        inventory,
        repo_root=repo_root,
    )
    records = []
    known_gap_items = 0
    open_evidence_items = 0
    for record in provenance["records"]:
        open_evidence = [
            {
                "classification": item["classification"],
                "statement": item["statement"],
            }
            for item in record["evidence"]
            if item["classification"] in {"hypothesis", "unresolved"}
        ]
        gaps = list(record["known_gaps"])
        if record["coverage"] == "verified" and not open_evidence:
            continue
        known_gap_items += len(gaps)
        open_evidence_items += len(open_evidence)
        records.append(
            {
                "id": record["id"],
                "coverage": record["coverage"],
                "sources": sorted(
                    source["path"] for source in record["sources"]
                ),
                "known_gaps": gaps,
                "open_evidence": open_evidence,
            }
        )
    records.sort(key=lambda item: item["id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": "provenance_gap_audit",
        "build_identity": dict(provenance["build_identity"]),
        "method": {
            "included_records": (
                "non-verified coverage, plus any verified record that still "
                "contains hypothesis or unresolved evidence"
            ),
            "ordering": "record id; source paths are sorted",
            "known_gaps": "verbatim record-level limitations",
            "open_evidence": (
                "hypothesis and unresolved evidence with classification "
                "preserved"
            ),
        },
        "records": records,
        "summary": {
            "records_total": len(provenance["records"]),
            "open_records": len(records),
            "known_gap_items": known_gap_items,
            "records_with_open_evidence": sum(
                bool(record["open_evidence"]) for record in records
            ),
            "open_evidence_items": open_evidence_items,
            "coverage": coverage,
        },
    }


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
