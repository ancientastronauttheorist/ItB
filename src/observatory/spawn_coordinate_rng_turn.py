"""Fail-closed composition of the RNG-core and spawn-coordinate boundaries.

The coordinate observer uses read-only hardware breakpoints while the existing
RNG-core observer temporarily patches one build-pinned RNG prologue.  The two
observers have separate modules and output files, so they can safely surround
the same synchronous End Turn.  Preparation deliberately arms the coordinate
observer first and seeds/arms the RNG-core observer last; the latter's atomic
seed is therefore the final RNG state transition before native game flow.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.observatory.native_rng_turn import NativeRngTurnBoundary
from src.observatory.spawn_coordinate_turn import SpawnCoordinateTurnBoundary


class SpawnCoordinateRngTurnBoundaryError(RuntimeError):
    """Raised when the combined boundary cannot restore both observers."""


class SpawnCoordinateRngTurnBoundary:
    """Capture the complete RNG stream and exact coordinate draw together."""

    def __init__(self, *, capture_id: str) -> None:
        self.capture_id = capture_id
        self.coordinate = SpawnCoordinateTurnBoundary(
            condition="armed", capture_id=capture_id
        )
        self.rng_core = NativeRngTurnBoundary(
            condition="exact_hook", capture_id=capture_id
        )
        self.state = "ready"

    @property
    def coordinate_snapshot(self) -> dict[str, Any] | None:
        return self.coordinate.snapshot

    @property
    def rng_snapshot(self) -> dict[str, Any] | None:
        return self.rng_core.snapshot

    @property
    def armed(self) -> bool:
        return self.state in {
            "coordinate_prepare_pending",
            "rng_prepare_pending",
            "armed",
        }

    def before_end_turn(self) -> dict[str, Any]:
        if self.state != "ready":
            raise SpawnCoordinateRngTurnBoundaryError(
                f"combined boundary cannot start from state {self.state}"
            )
        try:
            self.state = "coordinate_prepare_pending"
            self.coordinate.before_end_turn()
            self.state = "rng_prepare_pending"
            self.rng_core.before_end_turn()
            self.state = "armed"
        except Exception as exc:
            restore_errors = self._restore_both()
            message = f"combined pre-End-Turn boundary failed: {exc}"
            if restore_errors:
                message += "; restore failures: " + "; ".join(restore_errors)
            raise SpawnCoordinateRngTurnBoundaryError(message) from exc
        return self.summary()

    def after_end_turn(self, end_turn_result: object) -> dict[str, Any]:
        if self.state != "armed":
            raise SpawnCoordinateRngTurnBoundaryError(
                f"combined boundary cannot finish from state {self.state}"
            )
        status = (
            end_turn_result.get("status")
            if isinstance(end_turn_result, Mapping)
            else None
        )
        errors: list[str] = []

        # Remove the hardware breakpoints before restoring the patched RNG
        # prologue.  Both attempts always run so one publication/validation
        # failure cannot strand the other observer in memory.
        try:
            self.coordinate.after_end_turn(end_turn_result)
        except Exception as exc:
            errors.append(f"coordinate finish failed: {exc}")
        try:
            self.rng_core.after_end_turn(end_turn_result)
        except Exception as exc:
            errors.append(f"RNG-core finish failed: {exc}")

        if errors:
            errors.extend(self._restore_both())
            self.state = (
                "restore_failed"
                if self.coordinate.state == "restore_failed"
                or self.rng_core.state == "restore_failed"
                else "rejected"
            )
            raise SpawnCoordinateRngTurnBoundaryError("; ".join(errors))

        self.state = "complete" if status == "OK" else "rejected"
        return self.summary(end_turn_status=status)

    def abort(self) -> dict[str, Any]:
        restore_errors = self._restore_both()
        if restore_errors:
            self.state = "restore_failed"
            raise SpawnCoordinateRngTurnBoundaryError(
                "combined abort restore failed: " + "; ".join(restore_errors)
            )
        if self.state not in {"complete", "rejected", "restore_failed"}:
            self.state = "aborted"
        return self.summary()

    def _restore_both(self) -> list[str]:
        errors: list[str] = []
        # Reverse preparation order: restore the patched RNG core, then clear
        # the coordinate observer's debug registers/VEH.
        for label, boundary in (
            ("RNG-core abort", self.rng_core),
            ("coordinate abort", self.coordinate),
        ):
            try:
                boundary.abort()
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        return errors

    def summary(self, *, end_turn_status: object = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "condition": "combined_exact_hook_and_coordinate_hw",
            "capture_id": self.capture_id,
            "state": self.state,
            "coordinate": self.coordinate.summary(),
            "rng_core": self.rng_core.summary(),
        }
        if end_turn_status is not None:
            result["end_turn_status"] = end_turn_status
        return result
