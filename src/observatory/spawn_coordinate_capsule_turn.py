"""Fail-closed boundary around one locally dispatched capsule trial End Turn.

The ordinary ``auto_turn`` flow emits an End Turn plan before the guarded UI
click is consumed.  A native selector observer must therefore remain armed
across the later local dispatcher, not merely across plan creation.  This state
machine prepares only after the solver has spent every player actor and issued
an opaque local reservation, then restores immediately after the dispatcher
has delivered the click and the caller observes the next player turn.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from src.bridge.protocol import (
    abort_observatory_spawn_coordinate_capsule,
    finish_observatory_spawn_coordinate_capsule,
    prepare_observatory_spawn_coordinate_capsule,
)


_CAPTURE_ID = re.compile(r"[a-z][a-z0-9_.-]{0,95}\Z")


class SpawnCoordinateCapsuleTurnError(RuntimeError):
    """Raised when a capsule trial cannot prove bounded dispatch/restoration."""


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SpawnCoordinateCapsuleTurnBoundary:
    """Seed, optionally arm, dispatch once, and restore one capsule observer."""

    def __init__(self, *, condition: str, capture_id: str) -> None:
        if condition not in {"control", "dormant", "armed"}:
            raise SpawnCoordinateCapsuleTurnError(
                "spawn-coordinate capsule condition must be control, dormant, or armed"
            )
        if type(capture_id) is not str or _CAPTURE_ID.fullmatch(capture_id) is None:
            raise SpawnCoordinateCapsuleTurnError(
                "spawn-coordinate capsule capture ID is invalid"
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

    def before_dispatch(self) -> dict[str, Any]:
        """Prepare after an opaque local End Turn reservation already exists."""
        if self.state != "ready":
            raise SpawnCoordinateCapsuleTurnError(
                f"spawn-coordinate capsule cannot prepare from state {self.state}"
            )
        self.state = "prepare_pending"
        try:
            self.prepare_ack = prepare_observatory_spawn_coordinate_capsule(
                self.condition,
                self.capture_id,
            )
            self.state = "prepared"
        except Exception as exc:
            restore_error = self._abort_if_prepared()
            message = f"spawn-coordinate capsule pre-dispatch boundary failed: {exc}"
            if restore_error is not None:
                message += f"; observer restore also failed: {restore_error}"
            raise SpawnCoordinateCapsuleTurnError(message) from exc
        return self.summary()

    def after_dispatch(self, dispatch_result: object) -> dict[str, Any]:
        """Restore after confirmed dispatch and the caller's transition wait."""
        if self.state != "prepared":
            raise SpawnCoordinateCapsuleTurnError(
                f"spawn-coordinate capsule cannot finish from state {self.state}"
            )
        status = (
            dispatch_result.get("status")
            if isinstance(dispatch_result, Mapping)
            else None
        )
        delivery = (
            dispatch_result.get("delivery_confirmation")
            if isinstance(dispatch_result, Mapping)
            else None
        )
        try:
            self.finish_ack, self.snapshot = (
                finish_observatory_spawn_coordinate_capsule(
                    self.condition,
                    self.capture_id,
                )
            )
        except Exception as exc:
            self.state = "finish_failed"
            restore_error = self._abort_if_prepared(force=True)
            message = f"spawn-coordinate capsule observer restore failed: {exc}"
            if restore_error is not None:
                message += f"; abort restore also failed: {restore_error}"
            raise SpawnCoordinateCapsuleTurnError(message) from exc
        accepted = status == "OK" and delivery == "delivered_confirmed"
        self.state = "complete" if accepted else "rejected"
        return self.summary(
            dispatch_status=status,
            delivery_confirmation=delivery,
        )

    def abort(self) -> dict[str, Any]:
        """Restore a prepared boundary without dispatching or publishing evidence."""
        restore_error = self._abort_if_prepared()
        if restore_error is not None:
            raise SpawnCoordinateCapsuleTurnError(
                f"spawn-coordinate capsule abort restore failed: {restore_error}"
            ) from restore_error
        if self.state not in {"complete", "rejected", "finish_failed"}:
            self.state = "aborted"
        return self.summary()

    def _abort_if_prepared(self, *, force: bool = False) -> Exception | None:
        if not force and self.state not in {"prepare_pending", "prepared"}:
            return None
        try:
            self.abort_ack = abort_observatory_spawn_coordinate_capsule(
                self.capture_id
            )
            self.state = "rejected"
            return None
        except Exception as exc:  # pragma: no cover - process-stop fallback
            self.state = "restore_failed"
            return exc

    def summary(
        self,
        *,
        dispatch_status: object = None,
        delivery_confirmation: object = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "condition": self.condition,
            "capture_id": self.capture_id,
            "state": self.state,
            "prepare_ack": self.prepare_ack,
            "finish_ack": self.finish_ack,
            "abort_ack": self.abort_ack,
        }
        if dispatch_status is not None:
            result["dispatch_status"] = dispatch_status
        if delivery_confirmation is not None:
            result["delivery_confirmation"] = delivery_confirmation
        if self.snapshot is not None:
            summary = self.snapshot.get("summary")
            integrity = self.snapshot.get("integrity")
            result.update(
                {
                    "snapshot_sha256": _canonical_sha256(self.snapshot),
                    "draw_record_count": (
                        summary.get("draw_record_count")
                        if isinstance(summary, Mapping)
                        else None
                    ),
                    "scheduler_count": (
                        summary.get("scheduler_count")
                        if isinstance(summary, Mapping)
                        else None
                    ),
                    "selector_count": (
                        summary.get("selector_count")
                        if isinstance(summary, Mapping)
                        else None
                    ),
                    "capsule_count": (
                        summary.get("capsule_count")
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
                    "addresses_or_pointers_published": (
                        integrity.get("addresses_or_pointers_published")
                        if isinstance(integrity, Mapping)
                        else None
                    ),
                }
            )
        return result
