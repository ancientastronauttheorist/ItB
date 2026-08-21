"""Correlate native selected AI records with bridge-visible queued actions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from src.observatory.native_checkpoint import validate_native_checkpoint


SCHEMA_VERSION = 1
ANALYSIS_KIND = "selected_record_queue_correlation"


def correlate_selected_records(
    checkpoint: Mapping[str, Any],
    *,
    expected_identity: Mapping[str, Any] | None = None,
    return_map: Mapping[str, Any] | None = None,
    expected_restore_hashes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare selected ``aiDest``/``aiTarget`` fields to the next queue state."""
    verification = validate_native_checkpoint(
        checkpoint,
        expected_identity=expected_identity,
        return_map=return_map,
        expected_restore_hashes=expected_restore_hashes,
    )
    records = checkpoint["records"]
    selected = [record for record in records if record["kind"] == "selected_record"]
    snapshots = [record for record in records if record["kind"] == "queue_snapshot"]
    selection_counts = Counter(record["turn"] for record in selected)

    results: list[dict[str, Any]] = []
    for record in selected:
        reason: str | None = None
        snapshot_seq: int | None = None
        if not verification["diagnostic_complete"]:
            reason = "checkpoint_incomplete"
        elif selection_counts[record["turn"]] != 1:
            reason = "multiple_selected_records"
        elif record["skill_id"] is None:
            reason = "selected_skill_unavailable"

        next_index = record["seq"] + 1
        if next_index >= len(records) or records[next_index]["kind"] != (
            "queue_snapshot"
        ):
            reason = reason or "queue_snapshot_not_immediate"
            matches: list[Mapping[str, Any]] = []
            later: list[Mapping[str, Any]] = []
        else:
            snapshot = records[next_index]
            later = [
                item
                for item in snapshots
                if item["turn"] == record["turn"] and item["seq"] > snapshot["seq"]
            ]
            snapshot_seq = snapshot["seq"]
            if snapshot["turn"] != record["turn"]:
                reason = reason or "queue_snapshot_turn_mismatch"
            elif snapshot["phase"] != "enemy_planning":
                reason = reason or "late_queue_snapshot"
            elif len(snapshot["queue"]) != 1:
                reason = reason or "queue_snapshot_not_single_enemy"
            matches = [
                item
                for item in snapshot["queue"]
                if item["enemy_id"] == record["enemy_id"]
            ]
            if len(matches) == 0:
                reason = reason or "selected_enemy_missing_from_queue"
            elif len(matches) > 1:
                reason = reason or "ambiguous_queue_entries"

        if len(matches) == 1:
            queued = matches[0]
            if queued["state"] != "queued":
                reason = reason or f"queue_state_{queued['state']}"
            elif queued["destination"] != record["ai_dest"]:
                reason = reason or "destination_mismatch"
            elif queued["target"] != record["ai_target"]:
                reason = reason or "target_mismatch"
            elif (
                record["skill_id"] is not None
                and queued["skill_id"] != record["skill_id"]
            ):
                reason = reason or "skill_mismatch"

            if reason is None:
                for later_snapshot in later:
                    later_matches = [
                        item
                        for item in later_snapshot["queue"]
                        if item["enemy_id"] == record["enemy_id"]
                    ]
                    if len(later_matches) > 1:
                        reason = "later_ambiguous_queue_entries"
                        break
                    if (
                        not later_matches
                        and later_snapshot["phase"] == "enemy_planning"
                    ):
                        reason = "later_queue_entry_missing"
                        break
                    if any(
                        item["state"] in {"cancelled", "retargeted"}
                        for item in later_matches
                    ):
                        reason = "later_cancel_or_retarget"
                        break
                    if any(
                        item["destination"] != queued["destination"]
                        or item["target"] != queued["target"]
                        or item["skill_id"] != queued["skill_id"]
                        for item in later_matches
                    ):
                        reason = "later_queue_field_drift"
                        break

        results.append(
            {
                "selected_sequence": record["seq"],
                "queue_snapshot_sequence": snapshot_seq,
                "turn": record["turn"],
                "enemy_id": record["enemy_id"],
                "status": "correlated" if reason is None else "unresolved",
                "reason": reason,
                "ai_dest": record["ai_dest"],
                "ai_target": record["ai_target"],
                "skill_id": record["skill_id"],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "capture_id": checkpoint["capture_id"],
        "diagnostic_complete": verification["diagnostic_complete"],
        "correlations": results,
        "summary": {
            "selected_record_count": len(results),
            "correlated": sum(item["status"] == "correlated" for item in results),
            "unresolved": sum(item["status"] == "unresolved" for item in results),
        },
    }
