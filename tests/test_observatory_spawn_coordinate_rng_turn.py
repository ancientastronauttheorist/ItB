from __future__ import annotations

import pytest

from src.observatory import spawn_coordinate_rng_turn as turn


class _Boundary:
    def __init__(self, label: str, calls: list[str], *, fail: str = "") -> None:
        self.label = label
        self.calls = calls
        self.fail = fail
        self.state = "ready"
        self.snapshot = {"source": label}

    def before_end_turn(self):
        self.calls.append(f"{self.label}:before")
        if self.fail == "before":
            raise RuntimeError(f"{self.label} before")
        self.state = "armed"

    def after_end_turn(self, _result):
        self.calls.append(f"{self.label}:after")
        if self.fail == "after":
            self.state = "restore_failed"
            raise RuntimeError(f"{self.label} after")
        self.state = "complete"

    def abort(self):
        self.calls.append(f"{self.label}:abort")
        if self.fail == "abort":
            self.state = "restore_failed"
            raise RuntimeError(f"{self.label} abort")
        if self.state != "complete":
            self.state = "rejected"

    def summary(self):
        return {"source": self.label, "state": self.state}


def _combined(monkeypatch, *, coordinate_fail="", rng_fail=""):
    calls: list[str] = []
    coordinate = _Boundary("coordinate", calls, fail=coordinate_fail)
    rng = _Boundary("rng", calls, fail=rng_fail)
    monkeypatch.setattr(
        turn,
        "SpawnCoordinateTurnBoundary",
        lambda **_kwargs: coordinate,
    )
    monkeypatch.setattr(
        turn,
        "NativeRngTurnBoundary",
        lambda **_kwargs: rng,
    )
    return turn.SpawnCoordinateRngTurnBoundary(capture_id="combined-001"), calls


def test_combined_boundary_orders_prepare_and_reverse_restore(monkeypatch):
    boundary, calls = _combined(monkeypatch)

    boundary.before_end_turn()
    summary = boundary.after_end_turn({"status": "OK"})
    boundary.abort()

    assert calls == [
        "coordinate:before",
        "rng:before",
        "coordinate:after",
        "rng:after",
        "rng:abort",
        "coordinate:abort",
    ]
    assert summary["state"] == "complete"
    assert summary["end_turn_status"] == "OK"
    assert boundary.coordinate_snapshot == {"source": "coordinate"}
    assert boundary.rng_snapshot == {"source": "rng"}


def test_rng_prepare_failure_restores_both_observers(monkeypatch):
    boundary, calls = _combined(monkeypatch, rng_fail="before")

    with pytest.raises(
        turn.SpawnCoordinateRngTurnBoundaryError,
        match="combined pre-End-Turn boundary failed",
    ):
        boundary.before_end_turn()

    assert calls == [
        "coordinate:before",
        "rng:before",
        "rng:abort",
        "coordinate:abort",
    ]


def test_coordinate_finish_failure_still_finishes_rng_core(monkeypatch):
    boundary, calls = _combined(monkeypatch, coordinate_fail="after")
    boundary.before_end_turn()

    with pytest.raises(
        turn.SpawnCoordinateRngTurnBoundaryError,
        match="coordinate finish failed",
    ):
        boundary.after_end_turn({"status": "OK"})

    assert calls[:4] == [
        "coordinate:before",
        "rng:before",
        "coordinate:after",
        "rng:after",
    ]
    assert "rng:abort" in calls
    assert "coordinate:abort" in calls


def test_abort_reports_either_restore_failure(monkeypatch):
    boundary, calls = _combined(monkeypatch, coordinate_fail="abort")

    with pytest.raises(
        turn.SpawnCoordinateRngTurnBoundaryError,
        match="coordinate abort",
    ):
        boundary.abort()

    assert calls == ["rng:abort", "coordinate:abort"]
    assert boundary.state == "restore_failed"
