"""Fail-closed pre-End-Turn controller for the spawn-coordinate observer."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from src.bridge.writer import (
    bridge_observatory_spawn_coordinate_abort,
    bridge_observatory_spawn_coordinate_finish,
    bridge_observatory_spawn_coordinate_prepare,
)


_CAPTURE_ID = re.compile(r"[a-z][a-z0-9_.-]{0,95}\Z")


class SpawnCoordinateTurnBoundaryError(RuntimeError):
    """Raised when a coordinate trial cannot remain safely bounded."""


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SpawnCoordinateTurnBoundary:
    """Seed, optionally arm, and restore one coordinate capture around End Turn."""

    def __init__(self, *, condition: str, capture_id: str) -> None:
        if condition not in {"control", "dormant", "armed"}:
            raise SpawnCoordinateTurnBoundaryError(
                "spawn-coordinate condition must be control, dormant, or armed"
            )
        if type(capture_id) is not str or _CAPTURE_ID.fullmatch(capture_id) is None:
            raise SpawnCoordinateTurnBoundaryError(
                "spawn-coordinate capture ID is invalid"
            )
        self.condition = condition
        self.capture_id = capture_id
        self.state = "ready"
        self.prepare_ack: str | None = None
        self.finish_ack: str | None = None
        self.abort_ack: str | None = None
        self.snapshot: dict[str, Any] | None = None

    @property
    def armed(self) -> bool:
        return self.condition == "armed" and self.state in {
            "prepare_pending",
            "prepared",
        }

    def before_end_turn(self) -> dict[str, Any]:
        if self.state != "ready":
            raise SpawnCoordinateTurnBoundaryError(
                f"spawn-coordinate boundary cannot start from state {self.state}"
            )
        self.state = "prepare_pending"
        try:
            self.prepare_ack = bridge_observatory_spawn_coordinate_prepare(
                self.condition, self.capture_id
            )
            self.state = "prepared"
        except Exception as exc:
            restore_error = self._abort_if_prepared()
            message = f"spawn-coordinate pre-End-Turn boundary failed: {exc}"
            if restore_error is not None:
                message += f"; observer restore also failed: {restore_error}"
            raise SpawnCoordinateTurnBoundaryError(message) from exc
        return self.summary()

    def after_end_turn(self, end_turn_result: object) -> dict[str, Any]:
        if self.state != "prepared":
            raise SpawnCoordinateTurnBoundaryError(
                f"spawn-coordinate boundary cannot finish from state {self.state}"
            )
        status = (
            end_turn_result.get("status")
            if isinstance(end_turn_result, Mapping)
            else None
        )
        try:
            self.finish_ack, self.snapshot = (
                bridge_observatory_spawn_coordinate_finish(
                    self.condition, self.capture_id
                )
            )
        except Exception as exc:
            self.state = "finish_failed"
            restore_error = self._abort_if_prepared(force=True)
            message = f"spawn-coordinate observer restore failed: {exc}"
            if restore_error is not None:
                message += f"; abort restore also failed: {restore_error}"
            raise SpawnCoordinateTurnBoundaryError(message) from exc
        self.state = "complete" if status == "OK" else "rejected"
        return self.summary(end_turn_status=status)

    def abort(self) -> dict[str, Any]:
        restore_error = self._abort_if_prepared()
        if restore_error is not None:
            raise SpawnCoordinateTurnBoundaryError(
                f"spawn-coordinate observer abort restore failed: {restore_error}"
            ) from restore_error
        if self.state not in {"complete", "rejected", "finish_failed"}:
            self.state = "aborted"
        return self.summary()

    def _abort_if_prepared(self, *, force: bool = False) -> Exception | None:
        if not force and self.state not in {"prepare_pending", "prepared"}:
            return None
        try:
            self.abort_ack = bridge_observatory_spawn_coordinate_abort(
                self.capture_id
            )
            self.state = "rejected"
            return None
        except Exception as exc:  # pragma: no cover - process-stop fallback
            self.state = "restore_failed"
            return exc

    def summary(self, *, end_turn_status: object = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "condition": self.condition,
            "capture_id": self.capture_id,
            "state": self.state,
            "prepare_ack": self.prepare_ack,
            "finish_ack": self.finish_ack,
            "abort_ack": self.abort_ack,
        }
        if end_turn_status is not None:
            result["end_turn_status"] = end_turn_status
        if self.snapshot is not None:
            summary = self.snapshot.get("summary")
            integrity = self.snapshot.get("integrity")
            result.update(
                {
                    "snapshot_sha256": _canonical_sha256(self.snapshot),
                    "record_count": (
                        summary.get("record_count")
                        if isinstance(summary, Mapping)
                        else None
                    ),
                    "selector_count": (
                        summary.get("selector_count")
                        if isinstance(summary, Mapping)
                        else None
                    ),
                    "seam_bytes_unchanged": (
                        integrity.get("seam_bytes_unchanged")
                        if isinstance(integrity, Mapping)
                        else None
                    ),
                    "debug_registers_cleared": (
                        integrity.get("debug_registers_cleared")
                        if isinstance(integrity, Mapping)
                        else None
                    ),
                }
            )
        return result
