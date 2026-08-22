"""Merge a create-only Lua spawn-span ledger into a native RNG checkpoint.

The native RNG observer owns the raw record sequence.  A Lua wrapper around
``Spawner:NextPawn`` can only observe the observer's record count immediately
before and after the original call.  This module turns those count boundaries
into synthetic ``span_marker`` records *after* the observer has restored its
patch.  It never edits a raw record or supplies an unobserved RNG result.
"""

from __future__ import annotations

import copy
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any

from src.observatory.native_checkpoint import (
    MAX_RECORDS,
    NativeCheckpointError,
    validate_native_checkpoint,
)


SCHEMA_VERSION = 1
LEDGER_KIND = "spawn_rng_span_ledger"
CONTROLLER_VERSION = "observatory-spawn-span-controller/1"
WRITE_MODE = "create_only"
SPAN_NAME = "spawner_next_pawn"
SPAWNER_SOURCE_SHA256 = "59e8b2946a99d7bf1ade58b2384cbf0cd02eff26d545af2ea2e8c7060370c301"
SPAWNER_SOURCE_SUFFIX = "scripts/spawner_backend.lua"
SPAWNER_SOURCE_LINE = 174
_ID = re.compile(r"[a-z][a-z0-9_.-]{0,95}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SELECTED_PAWN = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,95}\Z")


class SpawnSpanLedgerError(NativeCheckpointError):
    """Raised when count-only Lua span evidence cannot be safely merged."""


def _exact(value: Mapping[str, Any], fields: set[str], label: str) -> None:
    actual = set(value)
    if actual != fields:
        raise SpawnSpanLedgerError(
            f"{label} fields differ; "
            f"missing={sorted(fields - actual)}, unknown={sorted(actual - fields)}"
        )


def _integer(value: Any, label: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise SpawnSpanLedgerError(
            f"{label} must be an integer in [{low}, {high}]"
        )
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise SpawnSpanLedgerError(f"{label} must be a canonical identifier")
    return value


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise SpawnSpanLedgerError(f"{label} must be boolean")
    return value


def _selected_pawn(value: Any, label: str) -> str:
    if type(value) is not str or _SELECTED_PAWN.fullmatch(value) is None:
        raise SpawnSpanLedgerError(f"{label} must be a canonical selected pawn")
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise SpawnSpanLedgerError(f"{label} must be lowercase SHA-256")
    return value


def _source_identity(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise SpawnSpanLedgerError("spawn span ledger.source_identity must be an object")
    _exact(
        value,
        {
            "expected_sha256",
            "expected_source_suffix",
            "expected_linedefined",
            "runtime_source",
            "runtime_linedefined",
            "source_location_verified",
        },
        "spawn span ledger.source_identity",
    )
    if value["expected_sha256"] != SPAWNER_SOURCE_SHA256 or _SHA256.fullmatch(
        value["expected_sha256"]
    ) is None:
        raise SpawnSpanLedgerError("spawn span ledger source SHA-256 differs")
    if value["expected_source_suffix"] != SPAWNER_SOURCE_SUFFIX:
        raise SpawnSpanLedgerError("spawn span ledger source suffix differs")
    if value["expected_linedefined"] != SPAWNER_SOURCE_LINE:
        raise SpawnSpanLedgerError("spawn span ledger source line differs")
    runtime_source = value["runtime_source"]
    if (
        type(runtime_source) is not str
        or not runtime_source
        or len(runtime_source) > 1024
        or "\\" in runtime_source
        or not runtime_source.endswith(SPAWNER_SOURCE_SUFFIX)
    ):
        raise SpawnSpanLedgerError("spawn span ledger runtime source differs")
    if value["runtime_linedefined"] != SPAWNER_SOURCE_LINE:
        raise SpawnSpanLedgerError("spawn span ledger runtime source line differs")
    if _boolean(
        value["source_location_verified"],
        "spawn span ledger source location verified",
    ) is not True:
        raise SpawnSpanLedgerError("spawn span ledger source location is unverified")


def _integrity(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise SpawnSpanLedgerError("spawn span ledger.integrity must be an object")
    _exact(
        value,
        {
            "complete",
            "wrapper_restored",
            "restore_conflict",
            "nested_call_count",
            "observer_status_error_count",
            "span_overflow_count",
            "count_regression_count",
            "active_depth",
        },
        "spawn span ledger.integrity",
    )
    if _boolean(value["complete"], "spawn span ledger.integrity.complete") is not True:
        raise SpawnSpanLedgerError("spawn span ledger is incomplete")
    if _boolean(
        value["wrapper_restored"], "spawn span ledger.integrity.wrapper_restored"
    ) is not True:
        raise SpawnSpanLedgerError("spawn span ledger wrapper was not restored")
    if _boolean(
        value["restore_conflict"], "spawn span ledger.integrity.restore_conflict"
    ) is not False:
        raise SpawnSpanLedgerError("spawn span ledger has a restore conflict")
    for field in (
        "nested_call_count",
        "observer_status_error_count",
        "span_overflow_count",
        "count_regression_count",
        "active_depth",
    ):
        _integer(value[field], f"spawn span ledger.integrity.{field}", 0, 0)


def validate_spawn_span_ledger(
    value: Mapping[str, Any],
    *,
    capture_id: str,
    raw_record_count: int,
    expected_controller_sha256: str,
) -> list[dict[str, Any]]:
    """Validate and normalize a count-only, append-only Lua ledger.

    ``entry_count`` and ``exit_count`` are half-open boundaries in the raw
    observer record array: a span encloses raw records ``[entry_count,
    exit_count)``.  The source ledger is chronological and may contain
    adjacent or zero-draw spans, but cannot overlap or nest.
    """
    if not isinstance(value, Mapping):
        raise SpawnSpanLedgerError("spawn span ledger must be an object")
    _exact(
        value,
        {
            "schema_version",
            "kind",
            "controller_version",
            "controller_sha256",
            "capture_id",
            "write_mode",
            "raw_record_count",
            "source_identity",
            "integrity",
            "spans",
            "summary",
        },
        "spawn span ledger",
    )
    if value["schema_version"] != SCHEMA_VERSION:
        raise SpawnSpanLedgerError("unsupported spawn span ledger schema version")
    if value["kind"] != LEDGER_KIND:
        raise SpawnSpanLedgerError("unexpected spawn span ledger kind")
    if value["controller_version"] != CONTROLLER_VERSION:
        raise SpawnSpanLedgerError("spawn span ledger controller version differs")
    expected_controller = _sha256(
        expected_controller_sha256, "expected controller SHA-256"
    )
    if _sha256(
        value["controller_sha256"], "spawn span ledger.controller_sha256"
    ) != expected_controller:
        raise SpawnSpanLedgerError("spawn span ledger controller SHA-256 differs")
    if value["write_mode"] != WRITE_MODE:
        raise SpawnSpanLedgerError("spawn span ledger is not create-only")
    if _identifier(value["capture_id"], "spawn span ledger.capture_id") != capture_id:
        raise SpawnSpanLedgerError("spawn span ledger capture ID differs from snapshot")
    observed_count = _integer(
        value["raw_record_count"],
        "spawn span ledger.raw_record_count",
        0,
        MAX_RECORDS,
    )
    if observed_count != raw_record_count:
        raise SpawnSpanLedgerError("spawn span ledger raw record count drift")
    _source_identity(value["source_identity"])
    _integrity(value["integrity"])
    raw_spans = value["spans"]
    if not isinstance(raw_spans, list) or len(raw_spans) > MAX_RECORDS // 2:
        raise SpawnSpanLedgerError("spawn span ledger spans must be a bounded array")

    normalized: list[dict[str, Any]] = []
    previous_exit = 0
    for index, raw_span in enumerate(raw_spans):
        label = f"spawn span ledger.spans[{index}]"
        if not isinstance(raw_span, Mapping):
            raise SpawnSpanLedgerError(f"{label} must be an object")
        _exact(
            raw_span,
            {
                "span_id",
                "name",
                "entry_count",
                "exit_count",
                "detail",
                "selected_pawn",
            },
            label,
        )
        span_id = _integer(raw_span["span_id"], f"{label}.span_id", 1, 0x7FFFFFFF)
        if span_id != index + 1:
            raise SpawnSpanLedgerError("spawn span ledger span IDs must be contiguous")
        if raw_span["name"] != SPAN_NAME:
            raise SpawnSpanLedgerError(f"{label}.name is unsupported")
        if raw_span["detail"] != "normal":
            raise SpawnSpanLedgerError(f"{label}.detail must be normal")
        detail = "normal"
        selected_pawn = _selected_pawn(
            raw_span["selected_pawn"], f"{label}.selected_pawn"
        )
        entry = _integer(raw_span["entry_count"], f"{label}.entry_count", 0, raw_record_count)
        exit_count = _integer(raw_span["exit_count"], f"{label}.exit_count", 0, raw_record_count)
        if entry > exit_count:
            raise SpawnSpanLedgerError(f"{label} exits before it enters")
        if entry < previous_exit:
            raise SpawnSpanLedgerError("spawn spans overlap or nest")
        previous_exit = exit_count
        normalized.append(
            {
                "span_id": span_id,
                "name": SPAN_NAME,
                "detail": detail,
                "selected_pawn": selected_pawn,
                "entry_count": entry,
                "exit_count": exit_count,
            }
        )
    summary = value["summary"]
    if not isinstance(summary, Mapping):
        raise SpawnSpanLedgerError("spawn span ledger.summary must be an object")
    _exact(summary, {"span_count", "complete"}, "spawn span ledger.summary")
    if _integer(summary["span_count"], "spawn span ledger.summary.span_count", 0, MAX_RECORDS // 2) != len(normalized):
        raise SpawnSpanLedgerError("spawn span ledger summary span count differs")
    if _boolean(summary["complete"], "spawn span ledger.summary.complete") is not True:
        raise SpawnSpanLedgerError("spawn span ledger summary is incomplete")
    return normalized


def _summary(records: list[dict[str, Any]], capture_complete: bool) -> dict[str, Any]:
    kinds = Counter(record["kind"] for record in records)
    return {
        "record_count": len(records),
        "rng_core_count": kinds["rng_core"],
        "rng_seed_count": kinds["rng_seed"],
        "phase_marker_count": kinds["phase_marker"],
        "span_marker_count": kinds["span_marker"],
        "selected_record_count": kinds["selected_record"],
        "queue_snapshot_count": kinds["queue_snapshot"],
        "thread_count": len({record["thread_slot"] for record in records}),
        "last_sequence": len(records) - 1,
        "capture_complete": capture_complete,
    }


def merge_spawn_span_ledger(
    checkpoint: Mapping[str, Any],
    ledger: Mapping[str, Any],
    *,
    expected_controller_sha256: str,
    expected_identity: Mapping[str, Any] | None = None,
    return_map: Mapping[str, Any] | None = None,
    expected_restore_hashes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert ledger-derived markers without changing raw native observations.

    A complete native snapshot with exactly one observed thread is required.
    The output keeps identity and integrity byte-for-byte equivalent to the
    input and deterministically recomputes only record sequences and summary.
    """
    verification = validate_native_checkpoint(
        checkpoint,
        expected_identity=expected_identity,
        return_map=return_map,
        expected_restore_hashes=expected_restore_hashes,
    )
    if not verification["reported_complete"]:
        raise SpawnSpanLedgerError(
            "raw native snapshot is incomplete or restoration failed"
        )
    raw_records = checkpoint["records"]
    if any(record["kind"] != "rng_core" for record in raw_records):
        raise SpawnSpanLedgerError(
            "raw native snapshot must contain only unmodified RNG-core records"
        )
    threads = {record["thread_slot"] for record in raw_records}
    if len(threads) != 1:
        raise SpawnSpanLedgerError(
            "raw native snapshot must contain exactly one observed thread"
        )
    thread_slot = next(iter(threads))
    spans = validate_spawn_span_ledger(
        ledger,
        capture_id=checkpoint["capture_id"],
        raw_record_count=len(raw_records),
        expected_controller_sha256=expected_controller_sha256,
    )
    if len(raw_records) + 2 * len(spans) > MAX_RECORDS:
        raise SpawnSpanLedgerError("merged spawn span checkpoint exceeds record capacity")

    merged_records: list[dict[str, Any]] = []
    cursor = 0
    for span in spans:
        entry = span["entry_count"]
        exit_count = span["exit_count"]
        merged_records.extend(copy.deepcopy(raw_records[cursor:entry]))
        merged_records.append(
            {
                "kind": "span_marker",
                "seq": 0,
                "thread_slot": thread_slot,
                "span_id": span["span_id"],
                "name": SPAN_NAME,
                "action": "enter",
                "detail": span["detail"],
            }
        )
        merged_records.extend(copy.deepcopy(raw_records[entry:exit_count]))
        merged_records.append(
            {
                "kind": "span_marker",
                "seq": 0,
                "thread_slot": thread_slot,
                "span_id": span["span_id"],
                "name": SPAN_NAME,
                "action": "exit",
                "detail": span["detail"],
            }
        )
        cursor = exit_count
    merged_records.extend(copy.deepcopy(raw_records[cursor:]))
    for sequence, record in enumerate(merged_records):
        record["seq"] = sequence

    result = copy.deepcopy(dict(checkpoint))
    result["records"] = merged_records
    result["summary"] = _summary(merged_records, result["integrity"]["complete"])
    # Keep the output self-validating even when the caller chose not to supply
    # the external identity/catalog/restore bindings above.
    validate_native_checkpoint(
        result,
        expected_identity=expected_identity,
        return_map=return_map,
        expected_restore_hashes=expected_restore_hashes,
    )
    return result
