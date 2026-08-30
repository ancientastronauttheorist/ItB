from __future__ import annotations

import pytest

from src.observatory import spawn_coordinate_capsule_turn as turn


def _snapshot() -> dict:
    return {
        "summary": {
            "draw_record_count": 3,
            "scheduler_count": 1,
            "selector_count": 2,
            "capsule_count": 2,
        },
        "integrity": {
            "seam_bytes_unchanged": True,
            "debug_registers_cleared": True,
            "addresses_or_pointers_published": False,
        },
    }


def _native_end_turn(**overrides) -> dict:
    result = {
        "status": "OK",
        "bridge": True,
        "ack": "OK END_TURN phase=combat_player method=observatory_native",
        "delivery_confirmation": "delivered_confirmed",
        "retry_allowed": False,
        "end_turn_plan_id": "plan-001",
        "end_turn_plan_source": "auto_turn",
        "end_turn_delivery_mode": "external",
    }
    result.update(overrides)
    return result


def test_armed_boundary_stays_prepared_until_confirmed_native_end_turn(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        turn,
        "prepare_observatory_spawn_coordinate_capsule",
        lambda condition, capture_id: calls.append(("prepare", condition, capture_id))
        or "prepared",
    )
    monkeypatch.setattr(
        turn,
        "finish_observatory_spawn_coordinate_capsule",
        lambda condition, capture_id: calls.append(("finish", condition, capture_id))
        or ("finished", _snapshot()),
    )
    boundary = turn.SpawnCoordinateCapsuleTurnBoundary(
        condition="armed",
        capture_id="spawn-capsule-armed-01",
    )

    prepared = boundary.before_end_turn()
    assert prepared["state"] == "prepared"
    assert boundary.armed is True
    summary = boundary.after_end_turn(_native_end_turn())

    assert calls == [
        ("prepare", "armed", "spawn-capsule-armed-01"),
        ("finish", "armed", "spawn-capsule-armed-01"),
    ]
    assert summary["state"] == "complete"
    assert summary["draw_record_count"] == 3
    assert summary["selector_count"] == summary["capsule_count"] == 2
    assert summary["addresses_or_pointers_published"] is False
    assert summary["end_turn_ack"].endswith("method=observatory_native")
    assert boundary.abort()["state"] == "complete"


@pytest.mark.parametrize("condition", ["control", "dormant"])
def test_unarmed_boundaries_require_no_snapshot(condition, monkeypatch):
    monkeypatch.setattr(
        turn,
        "prepare_observatory_spawn_coordinate_capsule",
        lambda *_args: "prepared",
    )
    monkeypatch.setattr(
        turn,
        "finish_observatory_spawn_coordinate_capsule",
        lambda *_args: ("finished", None),
    )
    boundary = turn.SpawnCoordinateCapsuleTurnBoundary(
        condition=condition,
        capture_id=f"spawn-capsule-{condition}-01",
    )

    boundary.before_end_turn()
    summary = boundary.after_end_turn(_native_end_turn())

    assert summary["state"] == "complete"
    assert boundary.snapshot is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"delivery_confirmation": "delivered_unconfirmed"},
        {"ack": "OK END_TURN phase=combat_player method=EndTurn"},
        {"bridge": False},
        {"retry_allowed": True},
        {"end_turn_plan_source": "lightning_loop"},
        {"end_turn_delivery_mode": "local"},
    ],
)
def test_nonexact_native_delivery_restores_but_rejects_trial(
    overrides,
    monkeypatch,
):
    monkeypatch.setattr(
        turn,
        "prepare_observatory_spawn_coordinate_capsule",
        lambda *_args: "prepared",
    )
    monkeypatch.setattr(
        turn,
        "finish_observatory_spawn_coordinate_capsule",
        lambda *_args: ("finished", _snapshot()),
    )
    boundary = turn.SpawnCoordinateCapsuleTurnBoundary(
        condition="armed",
        capture_id="spawn-capsule-unconfirmed-01",
    )
    boundary.before_end_turn()

    summary = boundary.after_end_turn(_native_end_turn(**overrides))

    assert summary["state"] == "rejected"
    assert summary["debug_registers_cleared"] is True


def test_abort_restores_a_prepared_boundary(monkeypatch):
    monkeypatch.setattr(
        turn,
        "prepare_observatory_spawn_coordinate_capsule",
        lambda *_args: "prepared",
    )
    monkeypatch.setattr(
        turn,
        "abort_observatory_spawn_coordinate_capsule",
        lambda capture_id: f"aborted {capture_id}",
    )
    boundary = turn.SpawnCoordinateCapsuleTurnBoundary(
        condition="armed",
        capture_id="spawn-capsule-abort-01",
    )
    boundary.before_end_turn()

    summary = boundary.abort()

    assert summary["state"] == "rejected"
    assert summary["abort_ack"] == "aborted spawn-capsule-abort-01"


def test_invalid_condition_capture_id_and_state_fail_closed():
    with pytest.raises(turn.SpawnCoordinateCapsuleTurnError, match="condition"):
        turn.SpawnCoordinateCapsuleTurnBoundary(
            condition="exact",
            capture_id="valid-id",
        )
    with pytest.raises(turn.SpawnCoordinateCapsuleTurnError, match="capture ID"):
        turn.SpawnCoordinateCapsuleTurnBoundary(
            condition="armed",
            capture_id="Bad ID",
        )

    boundary = turn.SpawnCoordinateCapsuleTurnBoundary(
        condition="armed",
        capture_id="spawn-capsule-state-01",
    )
    with pytest.raises(turn.SpawnCoordinateCapsuleTurnError, match="finish"):
        boundary.after_end_turn(_native_end_turn())
