"""Validation for build-keyed Lua-to-Rust mechanics provenance records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
ALLOWED_COVERAGE = {"verified", "partial", "gap", "native_dependency"}
ALLOWED_EVIDENCE = {"fact", "inference", "hypothesis", "unresolved"}


class ProvenanceError(RuntimeError):
    """Raised when provenance is ambiguous, stale, or structurally invalid."""


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProvenanceError(f"{label} must be an object")
    return value


def _inventory_identity(inventory: Mapping[str, Any]) -> dict[str, Any]:
    steam = inventory.get("steam") or {}
    depots = steam.get("installed_depots") or []
    depot_manifest = depots[0].get("manifest") if depots else None
    return {
        "platform": inventory.get("platform"),
        "architecture": (inventory.get("executable") or {}).get("architecture"),
        "executable_sha256": (inventory.get("executable") or {}).get("sha256"),
        "build_id": steam.get("build_id"),
        "depot_manifest": depot_manifest,
        "scripts_revision_sha256": (
            inventory.get("content", {}).get("scripts", {}).get("revision_sha256")
        ),
        "maps_revision_sha256": (
            inventory.get("content", {}).get("maps", {}).get("revision_sha256")
        ),
    }


def validate_provenance(
    provenance: Mapping[str, Any],
    inventory: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, int]:
    """Validate provenance against the exact inventory it claims to describe."""
    if provenance.get("schema_version") != SCHEMA_VERSION:
        raise ProvenanceError(
            f"unsupported provenance schema: {provenance.get('schema_version')!r}"
        )
    claimed_identity = _require_mapping(
        provenance.get("build_identity"),
        "build_identity",
    )
    actual_identity = _inventory_identity(inventory)
    for key, actual in actual_identity.items():
        if claimed_identity.get(key) != actual:
            raise ProvenanceError(
                f"build_identity.{key} does not match inventory: "
                f"{claimed_identity.get(key)!r} != {actual!r}"
            )

    source_entries = {
        entry["path"]: entry
        for entry in inventory.get("content", {}).get("scripts", {}).get("files", [])
        if isinstance(entry, Mapping) and "path" in entry
    }
    records = provenance.get("records")
    if not isinstance(records, list) or not records:
        raise ProvenanceError("records must be a non-empty array")

    seen_ids: set[str] = set()
    counts = {status: 0 for status in sorted(ALLOWED_COVERAGE)}
    for index, raw_record in enumerate(records):
        record = _require_mapping(raw_record, f"records[{index}]")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise ProvenanceError(f"records[{index}].id must be a non-empty string")
        if record_id in seen_ids:
            raise ProvenanceError(f"duplicate provenance id: {record_id}")
        seen_ids.add(record_id)

        coverage = record.get("coverage")
        if coverage not in ALLOWED_COVERAGE:
            raise ProvenanceError(f"{record_id}: invalid coverage {coverage!r}")
        counts[str(coverage)] += 1

        sources = record.get("sources")
        if not isinstance(sources, list) or not sources:
            raise ProvenanceError(f"{record_id}: sources must be non-empty")
        for source in sources:
            source = _require_mapping(source, f"{record_id}.source")
            path = source.get("path")
            if path not in source_entries:
                raise ProvenanceError(f"{record_id}: source is absent from inventory: {path}")
            actual_hash = source_entries[path].get("sha256")
            if source.get("sha256") != actual_hash:
                raise ProvenanceError(
                    f"{record_id}: stale source hash for {path}: "
                    f"{source.get('sha256')!r} != {actual_hash!r}"
                )
            symbols = source.get("symbols")
            if not isinstance(symbols, list) or not symbols or not all(
                isinstance(symbol, str) and symbol for symbol in symbols
            ):
                raise ProvenanceError(f"{record_id}: source symbols must be strings")

        evidence = record.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ProvenanceError(f"{record_id}: evidence must be non-empty")
        for item in evidence:
            item = _require_mapping(item, f"{record_id}.evidence")
            if item.get("classification") not in ALLOWED_EVIDENCE:
                raise ProvenanceError(
                    f"{record_id}: invalid evidence classification "
                    f"{item.get('classification')!r}"
                )
            if not isinstance(item.get("statement"), str) or not item["statement"]:
                raise ProvenanceError(f"{record_id}: empty evidence statement")

        implementations = record.get("implementations", [])
        tests = record.get("tests", [])
        if not isinstance(implementations, list) or not isinstance(tests, list):
            raise ProvenanceError(f"{record_id}: implementations/tests must be arrays")
        if coverage == "verified" and (not implementations or not tests):
            raise ProvenanceError(
                f"{record_id}: verified coverage requires implementations and tests"
            )
        if coverage == "verified" and not any(
            item.get("classification") == "fact" for item in evidence
        ):
            raise ProvenanceError(
                f"{record_id}: verified coverage requires fact-classified evidence"
            )
        if repo_root is not None:
            for reference in (*implementations, *tests):
                reference = _require_mapping(reference, f"{record_id}.repo_reference")
                path = reference.get("path")
                if not isinstance(path, str) or not (repo_root / path).is_file():
                    raise ProvenanceError(f"{record_id}: missing repo path: {path}")

        gaps = record.get("known_gaps")
        if not isinstance(gaps, list) or not all(
            isinstance(gap, str) and gap for gap in gaps
        ):
            raise ProvenanceError(f"{record_id}: known_gaps must be a string array")
        if coverage != "verified" and not gaps:
            raise ProvenanceError(f"{record_id}: non-verified coverage requires known_gaps")
    return counts


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProvenanceError(f"{path} must contain a JSON object")
    return data
