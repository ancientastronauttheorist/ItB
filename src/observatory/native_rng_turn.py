"""Fail-closed pre-End-Turn controller for the native RNG observer.

The controller is intentionally small and stateful.  It does not solve or
execute combat; ``cmd_auto_turn`` calls it only after all player actors are
spent and immediately around the already-authorized synchronous End Turn.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from src.bridge.writer import (
    bridge_observatory_native_rng_finish,
    bridge_observatory_native_rng_seed,
    bridge_observatory_native_rng_seed_and_arm,
)


_CAPTURE_ID = re.compile(r"[a-z][a-z0-9_.-]{0,95}\Z")


class NativeRngTurnBoundaryError(RuntimeError):
    """Raised when a native RNG turn-boundary trial cannot remain safe."""


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class NativeRngTurnBoundary:
    """Arm/seed/restore one control or exact native RNG turn trial."""

    def __init__(self, *, condition: str, capture_id: str) -> None:
        if condition not in {"control", "exact_hook"}:
            raise NativeRngTurnBoundaryError(
                "native RNG condition must be control or exact_hook"
            )
        if type(capture_id) is not str or _CAPTURE_ID.fullmatch(capture_id) is None:
            raise NativeRngTurnBoundaryError("native RNG capture ID is invalid")
        self.condition = condition
        self.capture_id = capture_id
        self.state = "ready"
        self.arm_ack: str | None = None
        self.seed_ack: str | None = None
        self.seed_and_arm_ack: str | None = None
        self.finish_ack: str | None = None
        self.snapshot: dict[str, Any] | None = None

    @property
    def armed(self) -> bool:
        return self.state in {"arm_pending", "armed"}

    def before_end_turn(self) -> dict[str, Any]:
        if self.state != "ready":
            raise NativeRngTurnBoundaryError(
                f"native RNG boundary cannot start from state {self.state}"
            )
        try:
            if self.condition == "exact_hook":
                # One bridge command loads both pinned modules while the RNG
                # bytes are pristine, seeds, and arms without yielding a game
                # tick.  Mark the arm as pending before delivery because a
                # lost ACK is ambiguous and must trigger a restore attempt.
                self.state = "arm_pending"
                self.seed_and_arm_ack = (
                    bridge_observatory_native_rng_seed_and_arm(self.capture_id)
                )
                self.state = "armed"
            else:
                self.seed_ack = bridge_observatory_native_rng_seed()
                self.state = "seeded"
        except Exception as exc:
            restore_error = self._restore_if_armed()
            message = f"native RNG pre-End-Turn boundary failed: {exc}"
            if restore_error is not None:
                message += f"; observer restore also failed: {restore_error}"
            raise NativeRngTurnBoundaryError(message) from exc
        return self.summary()

    def after_end_turn(self, end_turn_result: object) -> dict[str, Any]:
        expected_state = "armed" if self.condition == "exact_hook" else "seeded"
        if self.state != expected_state:
            raise NativeRngTurnBoundaryError(
                f"native RNG boundary cannot finish from state {self.state}"
            )
        status = (
            end_turn_result.get("status")
            if isinstance(end_turn_result, Mapping)
            else None
        )
        if self.condition == "exact_hook":
            try:
                self.finish_ack, self.snapshot = (
                    bridge_observatory_native_rng_finish(self.capture_id)
                )
            except Exception as exc:
                self.state = "restore_failed"
                raise NativeRngTurnBoundaryError(
                    f"native RNG observer restore failed: {exc}"
                ) from exc
        self.state = "complete" if status == "OK" else "rejected"
        return self.summary(end_turn_status=status)

    def abort(self) -> dict[str, Any]:
        restore_error = self._restore_if_armed()
        if restore_error is not None:
            raise NativeRngTurnBoundaryError(
                f"native RNG observer abort restore failed: {restore_error}"
            ) from restore_error
        if self.state not in {"complete", "rejected", "restore_failed"}:
            self.state = "aborted"
        return self.summary()

    def _restore_if_armed(self) -> Exception | None:
        if self.condition != "exact_hook" or self.state not in {
            "arm_pending",
            "armed",
        }:
            return None
        try:
            self.finish_ack, self.snapshot = (
                bridge_observatory_native_rng_finish(self.capture_id)
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
            "arm_ack": self.arm_ack,
            "seed_ack": self.seed_ack,
            "seed_and_arm_ack": self.seed_and_arm_ack,
            "finish_ack": self.finish_ack,
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
                    "hook_bytes_restored": (
                        integrity.get("hook_bytes_restored")
                        if isinstance(integrity, Mapping)
                        else None
                    ),
                }
            )
        return result
