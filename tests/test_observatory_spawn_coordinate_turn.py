from __future__ import annotations

import pytest

from src.observatory import spawn_coordinate_turn as turn


def _snapshot() -> dict:
    return {
        "summary": {"record_count": 2, "selector_count": 1},
        "integrity": {
            "seam_bytes_unchanged": True,
            "debug_registers_cleared": True,
        },
    }


def test_armed_boundary_wraps_end_turn_and_retains_restored_snapshot(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        turn,
        "bridge_observatory_spawn_coordinate_prepare",
        lambda condition, capture_id: calls.append(("prepare", condition, capture_id))
        or "prepared",
    )
    monkeypatch.setattr(
        turn,
        "bridge_observatory_spawn_coordinate_finish",
        lambda condition, capture_id: calls.append(("finish", condition, capture_id))
        or ("finished", _snapshot()),
    )
    boundary = turn.SpawnCoordinateTurnBoundary(
        condition="armed", capture_id="spawn-coordinate-armed-01"
    )

    boundary.before_end_turn()
    summary = boundary.after_end_turn({"status": "OK"})

    assert calls == [
        ("prepare", "armed", "spawn-coordinate-armed-01"),
        ("finish", "armed", "spawn-coordinate-armed-01"),
    ]
    assert boundary.state == "complete"
    assert summary["record_count"] == 2
    assert summary["selector_count"] == 1
    assert summary["seam_bytes_unchanged"] is True
    assert boundary.abort()["state"] == "complete"


@pytest.mark.parametrize("condition", ["control", "dormant"])
def test_unarmed_boundaries_require_no_snapshot(condition, monkeypatch):
    monkeypatch.setattr(
        turn,
        "bridge_observatory_spawn_coordinate_prepare",
        lambda *_args: "prepared",
    )
    monkeypatch.setattr(
        turn,
        "bridge_observatory_spawn_coordinate_finish",
        lambda *_args: ("finished", None),
    )
    boundary = turn.SpawnCoordinateTurnBoundary(
        condition=condition, capture_id=f"spawn-coordinate-{condition}-01"
    )

    boundary.before_end_turn()
    boundary.after_end_turn({"status": "OK"})

    assert boundary.state == "complete"
    assert boundary.snapshot is None


def test_abort_restores_a_prepared_armed_boundary(monkeypatch):
    monkeypatch.setattr(
        turn,
        "bridge_observatory_spawn_coordinate_prepare",
        lambda *_args: "prepared",
    )
    monkeypatch.setattr(
        turn,
        "bridge_observatory_spawn_coordinate_abort",
        lambda capture_id: f"aborted {capture_id}",
    )
    boundary = turn.SpawnCoordinateTurnBoundary(
        condition="armed", capture_id="spawn-coordinate-abort-01"
    )
    boundary.before_end_turn()

    summary = boundary.abort()

    assert boundary.state == "rejected"
    assert summary["abort_ack"] == "aborted spawn-coordinate-abort-01"


def test_invalid_condition_and_capture_id_fail_closed():
    with pytest.raises(turn.SpawnCoordinateTurnBoundaryError, match="condition"):
        turn.SpawnCoordinateTurnBoundary(condition="exact", capture_id="valid-id")
    with pytest.raises(turn.SpawnCoordinateTurnBoundaryError, match="capture ID"):
        turn.SpawnCoordinateTurnBoundary(condition="armed", capture_id="Bad ID")
