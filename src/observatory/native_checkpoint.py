"""Strict validation for inert native Observatory diagnostic checkpoints.

This schema is intentionally separate from the authoritative Observatory trace
schema.  A valid checkpoint can support build-specific diagnostic claims, but
it is never promoted to semantic trace evidence by this module.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any


SCHEMA_VERSION = 1
CHECKPOINT_KIND = "native_diagnostic_checkpoint"
MAX_RECORDS = 4096
MAX_THREADS = 32
MAX_CALLERS = 256
MAX_QUEUE_ITEMS = 64

_ID = re.compile(r"[a-z][a-z0-9_.-]{0,95}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RECORD_KINDS = {
    "rng_core",
    "rng_seed",
    "phase_marker",
    "span_marker",
    "selected_record",
    "queue_snapshot",
}
_SPAN_NAMES = {"spawner_next_pawn"}
_SPAN_ACTIONS = {"enter", "exit"}
_SPAN_DETAILS = {"normal", "shortcut_no_draw", "cancelled"}
_QUEUE_STATES = {"queued", "cancelled", "executed", "retargeted"}


class NativeCheckpointError(ValueError):
    """Raised when diagnostic checkpoint evidence is malformed or incomplete."""


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NativeCheckpointError(f"{label} must be an object")
    return value


def _exact(value: Mapping[str, Any], fields: set[str], label: str) -> None:
    actual = set(value)
    if actual != fields:
        raise NativeCheckpointError(
            f"{label} fields differ; "
            f"missing={sorted(fields - actual)}, unknown={sorted(actual - fields)}"
        )


def _integer(value: Any, label: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise NativeCheckpointError(
            f"{label} must be an integer in [{low}, {high}]"
        )
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise NativeCheckpointError(f"{label} must be a canonical identifier")
    return value


def _digest(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise NativeCheckpointError(f"{label} must be lowercase SHA-256")
    return value


def _nullable_identifier(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, label)


def _point(value: Any, label: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        raise NativeCheckpointError(f"{label} must be a two-integer point")
    return [
        _integer(value[0], f"{label}[0]", -1, 7),
        _integer(value[1], f"{label}[1]", -1, 7),
    ]


def _identity(value: Any) -> None:
    item = _object(value, "identity")
    fields = {
        "platform",
        "architecture",
        "executable_sha256",
        "executable_size",
        "build_id",
        "inventory_sha256",
        "boundary_map_sha256",
        "rng_return_map_sha256",
        "helper_sha256",
        "hook_plan_sha256",
        "restore_manifest_sha256",
    }
    _exact(item, fields, "identity")
    if item["platform"] != "windows" or item["architecture"] != "x86":
        raise NativeCheckpointError("identity must name the Windows x86 build")
    for field in (
        "executable_sha256",
        "inventory_sha256",
        "boundary_map_sha256",
        "rng_return_map_sha256",
        "helper_sha256",
        "hook_plan_sha256",
        "restore_manifest_sha256",
    ):
        _digest(item[field], f"identity.{field}")
    _integer(item["executable_size"], "identity.executable_size", 1, 1 << 31)
    build_id = item["build_id"]
    if type(build_id) is not str or not build_id or len(build_id) > 96:
        raise NativeCheckpointError("identity.build_id must be non-empty text")


def validate_return_map_binding(
    checkpoint: Mapping[str, Any],
    return_map: Mapping[str, Any],
) -> dict[int, Mapping[str, Any]]:
    """Bind an in-memory caller catalog to the checkpoint's exact identity."""
    from src.observatory.rng_return_map import encode_rng_return_map

    if (
        return_map.get("schema_version") != 1
        or return_map.get("analysis_kind") != "native_rng_return_id_map"
    ):
        raise NativeCheckpointError("return map has an unsupported schema")
    actual_digest = hashlib.sha256(
        encode_rng_return_map(return_map).encode("utf-8")
    ).hexdigest()
    if actual_digest != checkpoint["identity"]["rng_return_map_sha256"]:
        raise NativeCheckpointError("return map digest does not match checkpoint")
    identity = return_map.get("identity")
    if not isinstance(identity, Mapping):
        raise NativeCheckpointError("return map identity must be an object")
    for field in (
        "platform",
        "architecture",
        "executable_sha256",
        "executable_size",
        "build_id",
    ):
        if identity.get(field) != checkpoint["identity"][field]:
            raise NativeCheckpointError(
                f"return map identity field does not match checkpoint: {field}"
            )
    callers = return_map.get("callers")
    if not isinstance(callers, list) or len(callers) > MAX_CALLERS - 1:
        raise NativeCheckpointError("return map callers must be a bounded array")
    result: dict[int, Mapping[str, Any]] = {}
    for caller_id, raw in enumerate(callers, start=1):
        if not isinstance(raw, Mapping) or raw.get("caller_id") != caller_id:
            raise NativeCheckpointError("return map caller IDs are not contiguous")
        classification = raw.get("classification")
        if not isinstance(classification, Mapping):
            raise NativeCheckpointError("return map classification must be an object")
        status = classification.get("status")
        source = classification.get("source_region")
        if status == "unclassified_raw_candidate":
            if source is not None:
                raise NativeCheckpointError(
                    "unclassified return-map caller names a source region"
                )
        elif status == "reviewed_direct_call":
            if type(source) is not str or not source:
                raise NativeCheckpointError(
                    "reviewed return-map caller lacks a source region"
                )
        else:
            raise NativeCheckpointError("return map classification is unsupported")
        result[caller_id] = classification
    return result


def _hash_map(value: Any, label: str, *, allow_empty: bool = False) -> dict[str, str]:
    item = _object(value, label)
    if (not allow_empty and not item) or len(item) > 64:
        raise NativeCheckpointError(f"{label} must contain 1..64 hooks")
    result: dict[str, str] = {}
    for hook_id, digest in item.items():
        key = _identifier(hook_id, f"{label} hook id")
        result[key] = _digest(digest, f"{label}.{key}")
    return result


def restore_hash_manifest_sha256(value: Mapping[str, Any]) -> str:
    """Hash the canonical externally trusted hook restore manifest."""
    hashes = _hash_map(value, "restore_hash_manifest")
    encoded = json.dumps(
        hashes,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _queue_item(value: Any, label: str) -> None:
    item = _object(value, label)
    _exact(
        item,
        {
            "enemy_id",
            "position",
            "destination",
            "target",
            "skill_id",
            "state",
        },
        label,
    )
    _identifier(item["enemy_id"], f"{label}.enemy_id")
    _point(item["position"], f"{label}.position")
    _point(item["destination"], f"{label}.destination")
    _point(item["target"], f"{label}.target")
    _nullable_identifier(item["skill_id"], f"{label}.skill_id")
    if item["state"] not in _QUEUE_STATES:
        raise NativeCheckpointError(f"{label}.state is unsupported")


def _record(value: Any, index: int) -> tuple[str, int]:
    label = f"records[{index}]"
    item = _object(value, label)
    common = {"kind", "seq", "thread_slot"}
    kind = item.get("kind")
    if kind not in _RECORD_KINDS:
        raise NativeCheckpointError(f"{label}.kind is unsupported")
    seq = _integer(item.get("seq"), f"{label}.seq", 0, MAX_RECORDS - 1)
    thread = _integer(
        item.get("thread_slot"),
        f"{label}.thread_slot",
        0,
        MAX_THREADS - 1,
    )

    if kind == "rng_core":
        _exact(item, common | {"caller_id", "result"}, label)
        _integer(item["caller_id"], f"{label}.caller_id", 0, MAX_CALLERS - 1)
        _integer(item["result"], f"{label}.result", 0, 32767)
    elif kind == "rng_seed":
        _exact(item, common | {"seed"}, label)
        _integer(item["seed"], f"{label}.seed", 0, 0xFFFFFFFF)
    elif kind == "phase_marker":
        _exact(item, common | {"phase", "action"}, label)
        _identifier(item["phase"], f"{label}.phase")
        if item["action"] not in _SPAN_ACTIONS:
            raise NativeCheckpointError(f"{label}.action is unsupported")
    elif kind == "span_marker":
        _exact(item, common | {"span_id", "name", "action", "detail"}, label)
        _integer(item["span_id"], f"{label}.span_id", 1, 0x7FFFFFFF)
        if item["name"] not in _SPAN_NAMES:
            raise NativeCheckpointError(f"{label}.name is unsupported")
        if item["action"] not in _SPAN_ACTIONS:
            raise NativeCheckpointError(f"{label}.action is unsupported")
        if item["detail"] not in _SPAN_DETAILS:
            raise NativeCheckpointError(f"{label}.detail is unsupported")
    elif kind == "selected_record":
        _exact(
            item,
            common | {"turn", "enemy_id", "ai_dest", "ai_target", "skill_id"},
            label,
        )
        _integer(item["turn"], f"{label}.turn", 0, 999)
        _identifier(item["enemy_id"], f"{label}.enemy_id")
        _point(item["ai_dest"], f"{label}.ai_dest")
        _point(item["ai_target"], f"{label}.ai_target")
        _nullable_identifier(item["skill_id"], f"{label}.skill_id")
    else:
        _exact(item, common | {"turn", "phase", "queue"}, label)
        _integer(item["turn"], f"{label}.turn", 0, 999)
        _identifier(item["phase"], f"{label}.phase")
        queue = item["queue"]
        if not isinstance(queue, list) or len(queue) > MAX_QUEUE_ITEMS:
            raise NativeCheckpointError(
                f"{label}.queue must contain at most {MAX_QUEUE_ITEMS} entries"
            )
        for queue_index, entry in enumerate(queue):
            _queue_item(entry, f"{label}.queue[{queue_index}]")
    return str(kind), thread


def validate_native_checkpoint(
    value: Mapping[str, Any],
    *,
    expected_identity: Mapping[str, Any] | None = None,
    return_map: Mapping[str, Any] | None = None,
    expected_restore_hashes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one diagnostic checkpoint and return a compact verification."""
    checkpoint = _object(value, "checkpoint")
    _exact(
        checkpoint,
        {
            "schema_version",
            "kind",
            "identity",
            "capture_id",
            "integrity",
            "records",
            "summary",
        },
        "checkpoint",
    )
    if checkpoint["schema_version"] != SCHEMA_VERSION:
        raise NativeCheckpointError("unsupported native checkpoint schema version")
    if checkpoint["kind"] != CHECKPOINT_KIND:
        raise NativeCheckpointError("unexpected native checkpoint kind")
    _identity(checkpoint["identity"])
    identity_verified = expected_identity is not None
    if identity_verified and checkpoint["identity"] != expected_identity:
        raise NativeCheckpointError("checkpoint identity does not match expectation")
    _identifier(checkpoint["capture_id"], "capture_id")

    records = checkpoint["records"]
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise NativeCheckpointError(
            f"records must contain at most {MAX_RECORDS} entries"
        )
    kinds: Counter[str] = Counter()
    threads: set[int] = set()
    unknown_callers = 0
    for index, raw in enumerate(records):
        kind, thread = _record(raw, index)
        if raw["seq"] != index:
            raise NativeCheckpointError("record sequences must be contiguous from zero")
        kinds[kind] += 1
        threads.add(thread)
        if kind == "rng_core" and raw["caller_id"] == 0:
            unknown_callers += 1

    integrity = _object(checkpoint["integrity"], "integrity")
    _exact(
        integrity,
        {
            "overflow_count",
            "unknown_caller_count",
            "torn_record_count",
            "restore_conflict",
            "hook_bytes_restored",
            "post_restore_hashes",
            "stopped_reason",
            "complete",
        },
        "integrity",
    )
    overflow = _integer(integrity["overflow_count"], "integrity.overflow_count", 0, 1 << 31)
    unknown = _integer(
        integrity["unknown_caller_count"],
        "integrity.unknown_caller_count",
        0,
        MAX_RECORDS,
    )
    torn = _integer(integrity["torn_record_count"], "integrity.torn_record_count", 0, MAX_RECORDS)
    if unknown != unknown_callers:
        raise NativeCheckpointError("unknown caller count does not match records")
    for field in ("restore_conflict", "hook_bytes_restored", "complete"):
        if type(integrity[field]) is not bool:
            raise NativeCheckpointError(f"integrity.{field} must be boolean")
    hashes = _hash_map(
        integrity["post_restore_hashes"],
        "integrity.post_restore_hashes",
    )
    stopped = integrity["stopped_reason"]
    if stopped is not None:
        _identifier(stopped, "integrity.stopped_reason")
    reported_complete = (
        overflow == 0
        and unknown == 0
        and torn == 0
        and not integrity["restore_conflict"]
        and integrity["hook_bytes_restored"]
        and stopped is None
    )
    if integrity["complete"] is not reported_complete:
        raise NativeCheckpointError("integrity.complete does not match diagnostics")

    caller_catalog = (
        validate_return_map_binding(checkpoint, return_map)
        if return_map is not None
        else None
    )
    observed_caller_ids = {
        record["caller_id"]
        for record in records
        if record["kind"] == "rng_core" and record["caller_id"] != 0
    }
    caller_catalog_verified = (
        not observed_caller_ids
        or (
            caller_catalog is not None
            and observed_caller_ids <= set(caller_catalog)
        )
    )
    restore_hashes_verified = False
    if expected_restore_hashes is not None:
        expected_hashes = _hash_map(
            expected_restore_hashes,
            "expected_restore_hashes",
        )
        if restore_hash_manifest_sha256(expected_hashes) != checkpoint[
            "identity"
        ]["restore_manifest_sha256"]:
            raise NativeCheckpointError(
                "expected restore hashes do not match the trusted identity"
            )
        restore_hashes_verified = hashes == expected_hashes
    diagnostic_complete = (
        reported_complete
        and identity_verified
        and caller_catalog_verified
        and restore_hashes_verified
    )

    expected_summary = {
        "record_count": len(records),
        "rng_core_count": kinds["rng_core"],
        "rng_seed_count": kinds["rng_seed"],
        "phase_marker_count": kinds["phase_marker"],
        "span_marker_count": kinds["span_marker"],
        "selected_record_count": kinds["selected_record"],
        "queue_snapshot_count": kinds["queue_snapshot"],
        "thread_count": len(threads),
        "last_sequence": len(records) - 1,
        "capture_complete": reported_complete,
    }
    summary = _object(checkpoint["summary"], "summary")
    _exact(summary, set(expected_summary), "summary")
    if dict(summary) != expected_summary:
        raise NativeCheckpointError("checkpoint summary is inconsistent")

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": CHECKPOINT_KIND,
        "status": "verified",
        "capture_id": checkpoint["capture_id"],
        "identity_verified": identity_verified,
        "caller_catalog_verified": caller_catalog_verified,
        "restore_hashes_verified": restore_hashes_verified,
        "reported_complete": reported_complete,
        "diagnostic_complete": diagnostic_complete,
        "summary": expected_summary,
        "authority": "build_specific_diagnostic_only",
    }


def encode_native_checkpoint(value: Mapping[str, Any]) -> str:
    """Encode a checkpoint or verification deterministically."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
