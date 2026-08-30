"""Fail-closed boundary around one native capsule-trial End Turn.

The condition launcher loads the exact-build game-flow helper while entering
the restored timeline.  ``auto_turn`` invokes this boundary only after every
player actor is spent.  The boundary then seeds and optionally arms the capsule
observer, requires one synchronous reviewed native End Turn, and restores the
observer before control returns to the ordinary post-turn read.
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
_NATIVE_END_TURN_ACK = (
    "OK END_TURN phase=combat_player method=observatory_native"
)


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
    """Seed, optionally arm, deliver once natively, and restore the observer."""

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
        self.end_turn_status: object = None
        self.end_turn_bridge: object = None
        self.end_turn_ack: object = None
        self.delivery_confirmation: object = None
        self.retry_allowed: object = None
        self.end_turn_plan_id: object = None
        self.end_turn_plan_source: object = None
        self.end_turn_delivery_mode: object = None

    @property
    def armed(self) -> bool:
        return self.condition == "armed" and self.state in {
            "prepare_pending",
            "prepared",
        }

    def before_end_turn(self) -> dict[str, Any]:
        """Prepare immediately before ``auto_turn`` authorizes End Turn."""
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
            message = f"spawn-coordinate capsule pre-End-Turn boundary failed: {exc}"
            if restore_error is not None:
                message += f"; observer restore also failed: {restore_error}"
            raise SpawnCoordinateCapsuleTurnError(message) from exc
        return self.summary()

    def after_end_turn(self, end_turn_result: object) -> dict[str, Any]:
        """Restore after the synchronous native player/enemy/player cycle."""
        if self.state != "prepared":
            raise SpawnCoordinateCapsuleTurnError(
                f"spawn-coordinate capsule cannot finish from state {self.state}"
            )
        result = end_turn_result if isinstance(end_turn_result, Mapping) else {}
        self.end_turn_status = result.get("status")
        self.end_turn_bridge = result.get("bridge")
        self.end_turn_ack = result.get("ack")
        self.delivery_confirmation = result.get("delivery_confirmation")
        self.retry_allowed = result.get("retry_allowed")
        self.end_turn_plan_id = result.get("end_turn_plan_id")
        self.end_turn_plan_source = result.get("end_turn_plan_source")
        self.end_turn_delivery_mode = result.get("end_turn_delivery_mode")
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
        accepted = bool(
            self.end_turn_status == "OK"
            and self.end_turn_bridge is True
            and self.end_turn_ack == _NATIVE_END_TURN_ACK
            and self.delivery_confirmation == "delivered_confirmed"
            and self.retry_allowed is False
            and isinstance(self.end_turn_plan_id, str)
            and self.end_turn_plan_id
            and self.end_turn_plan_source == "auto_turn"
            and self.end_turn_delivery_mode == "external"
        )
        self.state = "complete" if accepted else "rejected"
        return self.summary()

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

    def summary(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "condition": self.condition,
            "capture_id": self.capture_id,
            "state": self.state,
            "prepare_ack": self.prepare_ack,
            "finish_ack": self.finish_ack,
            "abort_ack": self.abort_ack,
            "end_turn_status": self.end_turn_status,
            "end_turn_bridge": self.end_turn_bridge,
            "end_turn_ack": self.end_turn_ack,
            "delivery_confirmation": self.delivery_confirmation,
            "retry_allowed": self.retry_allowed,
            "end_turn_plan_id": self.end_turn_plan_id,
            "end_turn_plan_source": self.end_turn_plan_source,
            "end_turn_delivery_mode": self.end_turn_delivery_mode,
        }
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
