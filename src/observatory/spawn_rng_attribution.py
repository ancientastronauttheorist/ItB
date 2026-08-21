"""Attribute native RNG draws to explicitly bounded spawn-selection spans."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.observatory.native_checkpoint import (
    validate_native_checkpoint,
    validate_return_map_binding,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "spawn_rng_attribution"


def _bound_caller_origins(
    checkpoint: Mapping[str, Any],
    return_map: Mapping[str, Any] | None,
) -> dict[int, str] | None:
    if return_map is None:
        return None
    callers = validate_return_map_binding(checkpoint, return_map)
    result: dict[int, str] = {}
    for index, classification in callers.items():
        status = classification.get("status")
        source = classification.get("source_region")
        if status == "unclassified_raw_candidate":
            result[index] = "unclassified_native"
        elif status == "reviewed_direct_call" and source in {
            "random_int_1",
            "random_int_2",
            "random_bool_1",
            "random_bool_2",
        }:
            result[index] = "lua_random_leaf"
        elif status == "reviewed_direct_call" and type(source) is str:
            result[index] = "reviewed_native"
    return result


def _caller_origin(caller_id: int, origins: Mapping[int, str] | None) -> str:
    if caller_id == 0:
        return "unknown"
    if origins is None:
        return "catalog_not_supplied"
    return origins.get(caller_id, "catalog_missing")


def analyze_spawn_rng(
    checkpoint: Mapping[str, Any],
    *,
    return_map: Mapping[str, Any] | None = None,
    expected_identity: Mapping[str, Any] | None = None,
    expected_restore_hashes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Join RNG records to ``Spawner:NextPawn`` enter/exit markers.

    The result stays unresolved for nesting, reseeding, missing markers, or a
    normal path with no observed draw.  A no-draw result is affirmative only
    when both markers explicitly classify the path as ``shortcut_no_draw``.
    """
    validate_native_checkpoint(checkpoint)
    bound_origins = _bound_caller_origins(checkpoint, return_map)
    verification = validate_native_checkpoint(
        checkpoint,
        expected_identity=expected_identity,
        return_map=return_map,
        expected_restore_hashes=expected_restore_hashes,
    )
    records = checkpoint["records"]
    marker_groups: dict[int, list[Mapping[str, Any]]] = {}
    for record in records:
        if record["kind"] == "span_marker" and record["name"] == "spawner_next_pawn":
            marker_groups.setdefault(record["span_id"], []).append(record)

    parsed: dict[int, tuple[Mapping[str, Any], Mapping[str, Any]] | None] = {}
    base_reasons: dict[int, str | None] = {}
    for span_id, markers in marker_groups.items():
        enters = [item for item in markers if item["action"] == "enter"]
        exits = [item for item in markers if item["action"] == "exit"]
        if len(enters) != 1 or len(exits) != 1:
            parsed[span_id] = None
            base_reasons[span_id] = "unmatched_or_duplicate_markers"
            continue
        enter, exit_marker = enters[0], exits[0]
        reason = None
        if enter["thread_slot"] != exit_marker["thread_slot"]:
            reason = "cross_thread_markers"
        elif enter["seq"] >= exit_marker["seq"]:
            reason = "non_forward_span"
        elif enter["detail"] != exit_marker["detail"]:
            reason = "marker_detail_mismatch"
        parsed[span_id] = (enter, exit_marker)
        base_reasons[span_id] = reason

    ambiguous: set[int] = set()
    valid_pairs = [
        (span_id, pair)
        for span_id, pair in parsed.items()
        if pair is not None and base_reasons[span_id] is None
    ]
    for index, (left_id, left) in enumerate(valid_pairs):
        assert left is not None
        for right_id, right in valid_pairs[index + 1 :]:
            assert right is not None
            if left[0]["thread_slot"] != right[0]["thread_slot"]:
                continue
            left_start, left_end = left[0]["seq"], left[1]["seq"]
            right_start, right_end = right[0]["seq"], right[1]["seq"]
            if max(left_start, right_start) < min(left_end, right_end):
                ambiguous.update({left_id, right_id})

    results: list[dict[str, Any]] = []
    for span_id in sorted(marker_groups):
        pair = parsed[span_id]
        reason = base_reasons[span_id]
        if pair is None:
            markers = marker_groups[span_id]
            start = min(item["seq"] for item in markers)
            end = max(item["seq"] for item in markers)
            thread = markers[0]["thread_slot"]
            detail = markers[0]["detail"]
            draws: list[Mapping[str, Any]] = []
        else:
            enter, exit_marker = pair
            start, end = enter["seq"], exit_marker["seq"]
            thread = enter["thread_slot"]
            detail = enter["detail"]
            draws = [
                record
                for record in records
                if record["kind"] == "rng_core"
                and record["thread_slot"] == thread
                and start < record["seq"] < end
            ]
            reseeded = any(
                record["kind"] == "rng_seed"
                and record["thread_slot"] == thread
                and start < record["seq"] < end
                for record in records
            )
            if reseeded:
                reason = reason or "rng_reseed_inside_span"
        if span_id in ambiguous:
            reason = reason or "overlapping_or_nested_spawn_spans"
        if not verification["diagnostic_complete"]:
            reason = reason or "checkpoint_incomplete"
        if reason is None and detail == "cancelled":
            reason = "cancelled_spawn_path"
        if reason is None and detail == "shortcut_no_draw" and draws:
            reason = "shortcut_unexpected_rng_draw"
        if reason is None and detail == "normal" and not draws:
            reason = "no_rng_draw_observed"
        caller_origins = [
            _caller_origin(item["caller_id"], bound_origins) for item in draws
        ]
        if reason is None and "catalog_missing" in caller_origins:
            reason = "caller_id_absent_from_catalog"

        if reason is not None:
            status = "unresolved"
        elif detail == "shortcut_no_draw":
            status = "resolved_no_draw"
        else:
            status = "resolved_with_draws"
        results.append(
            {
                "span_id": span_id,
                "thread_slot": thread,
                "enter_sequence": start,
                "exit_sequence": end,
                "detail": detail,
                "status": status,
                "reason": reason,
                "draw_sequences": [item["seq"] for item in draws],
                "caller_ids": [item["caller_id"] for item in draws],
                "caller_origins": caller_origins,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "capture_id": checkpoint["capture_id"],
        "diagnostic_complete": verification["diagnostic_complete"],
        "spans": results,
        "summary": {
            "span_count": len(results),
            "resolved_with_draws": sum(
                item["status"] == "resolved_with_draws" for item in results
            ),
            "resolved_no_draw": sum(
                item["status"] == "resolved_no_draw" for item in results
            ),
            "unresolved": sum(item["status"] == "unresolved" for item in results),
        },
    }
