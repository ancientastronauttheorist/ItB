from __future__ import annotations

import pytest

from src.loop.commands import _end_turn_with_observatory_boundary
from src.observatory import native_rng_turn as mod


class _Boundary:
    def __init__(self, *, fail: str | None = None):
        self.calls = []
        self.fail = fail

    def before_end_turn(self):
        self.calls.append("before")
        if self.fail == "before":
            raise RuntimeError("before failed")

    def after_end_turn(self, result):
        self.calls.append(("after", result))
        if self.fail == "after":
            raise RuntimeError("after failed")
        return {"sealed": True}

    def abort(self):
        self.calls.append("abort")


def test_end_turn_boundary_orders_pre_delivery_and_post_restore():
    boundary = _Boundary()

    result, evidence = _end_turn_with_observatory_boundary(
        boundary, lambda: {"status": "OK"}
    )

    assert result == {"status": "OK"}
    assert evidence == {"sealed": True}
    assert boundary.calls == [
        "before",
        ("after", {"status": "OK"}),
    ]


@pytest.mark.parametrize("failure", ["before", "after"])
def test_end_turn_boundary_aborts_on_diagnostic_failure(failure):
    boundary = _Boundary(fail=failure)

    with pytest.raises(RuntimeError, match=f"{failure} failed"):
        _end_turn_with_observatory_boundary(
            boundary, lambda: {"status": "OK"}
        )

    assert boundary.calls[-1] == "abort"


def test_native_rng_exact_boundary_restores_after_success(monkeypatch):
    calls = []
    snapshot = {
        "summary": {"record_count": 3},
        "integrity": {"hook_bytes_restored": True},
    }
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_seed_and_arm",
        lambda capture_id: calls.append(("seed_and_arm", capture_id))
        or "SEED_AND_ARM",
    )
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_finish",
        lambda capture_id: (
            calls.append(("finish", capture_id)) or ("FINISH", snapshot)
        ),
    )
    boundary = mod.NativeRngTurnBoundary(
        condition="exact_hook", capture_id="native-rng-pair-001-exact"
    )

    boundary.before_end_turn()
    summary = boundary.after_end_turn({"status": "OK"})

    assert calls == [
        ("seed_and_arm", "native-rng-pair-001-exact"),
        ("finish", "native-rng-pair-001-exact"),
    ]
    assert summary["state"] == "complete"
    assert summary["record_count"] == 3
    assert summary["hook_bytes_restored"] is True


def test_native_rng_spawn_span_boundary_restores_both_layers(monkeypatch):
    calls = []
    snapshot = {
        "summary": {"record_count": 9},
        "integrity": {"hook_bytes_restored": True},
    }
    ledger = {
        "summary": {"span_count": 2},
        "integrity": {"wrapper_restored": True},
    }
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_seed_and_arm_spawn_span",
        lambda capture_id: calls.append(("arm_span", capture_id)) or "ARM",
    )
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_finish_spawn_span",
        lambda capture_id: (
            calls.append(("finish_span", capture_id))
            or ("FINISH", snapshot, ledger)
        ),
    )
    boundary = mod.NativeRngTurnBoundary(
        condition="spawn_span", capture_id="native-rng-spawn-001"
    )

    boundary.before_end_turn()
    summary = boundary.after_end_turn({"status": "OK"})

    assert calls == [
        ("arm_span", "native-rng-spawn-001"),
        ("finish_span", "native-rng-spawn-001"),
    ]
    assert summary["state"] == "complete"
    assert summary["spawn_span_count"] == 2
    assert summary["spawn_wrapper_restored"] is True


def test_native_rng_spawn_replay_boundary_is_natural_and_restores_both_slots(
    monkeypatch,
):
    calls = []
    snapshot = {
        "summary": {"record_count": 7},
        "integrity": {"hook_bytes_restored": True},
    }
    ledger = {
        "summary": {"span_count": 1},
        "integrity": {
            "next_wrapper_restored": True,
            "random_wrapper_restored": True,
        },
    }
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_arm_spawn_replay",
        lambda capture_id: calls.append(("arm_replay", capture_id)) or "ARM",
    )
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_finish_spawn_replay",
        lambda capture_id: (
            calls.append(("finish_replay", capture_id))
            or ("FINISH", snapshot, ledger)
        ),
    )
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_seed",
        lambda: calls.append("unexpected_seed"),
    )
    boundary = mod.NativeRngTurnBoundary(
        condition="spawn_replay", capture_id="native-rng-replay-001"
    )

    boundary.before_end_turn()
    summary = boundary.after_end_turn({"status": "OK"})

    assert calls == [
        ("arm_replay", "native-rng-replay-001"),
        ("finish_replay", "native-rng-replay-001"),
    ]
    assert summary["state"] == "complete"
    assert summary["spawn_replay_span_count"] == 1
    assert summary["spawn_replay_wrappers_restored"] is True


def test_spawn_replay_control_loads_dormant_artifacts_without_seed_or_finish(
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        mod,
        "bridge_observatory_spawn_replay_control",
        lambda capture_id: calls.append(("control", capture_id)) or "CONTROL",
    )
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_seed",
        lambda: calls.append("unexpected_seed"),
    )
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_finish",
        lambda capture_id: calls.append("unexpected_finish"),
    )
    boundary = mod.NativeRngTurnBoundary(
        condition="spawn_replay_control",
        capture_id="native-rng-replay-control-001",
    )

    boundary.before_end_turn()
    summary = boundary.after_end_turn({"status": "OK"})

    assert calls == [("control", "native-rng-replay-control-001")]
    assert summary["state"] == "complete"


def test_native_rng_control_boundary_never_arms_or_finishes(monkeypatch):
    calls = []
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_seed_and_arm",
        lambda capture_id: calls.append("seed_and_arm"),
    )
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_seed",
        lambda: calls.append("seed") or "SEED",
    )
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_finish",
        lambda capture_id: calls.append("finish"),
    )
    boundary = mod.NativeRngTurnBoundary(
        condition="control", capture_id="native-rng-pair-001-control"
    )

    boundary.before_end_turn()
    summary = boundary.after_end_turn({"status": "OK"})

    assert calls == ["seed"]
    assert summary["state"] == "complete"


def test_native_rng_control_seed_failure_never_arms_the_hook(monkeypatch):
    calls = []
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_seed_and_arm",
        lambda capture_id: calls.append("seed_and_arm") or "SEED_AND_ARM",
    )
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_seed",
        lambda: (_ for _ in ()).throw(RuntimeError("seed failed")),
    )
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_finish",
        lambda capture_id: calls.append("finish") or ("FINISH", {}),
    )
    boundary = mod.NativeRngTurnBoundary(
        condition="control", capture_id="native-rng-pair-001-control"
    )

    with pytest.raises(mod.NativeRngTurnBoundaryError, match="seed failed"):
        boundary.before_end_turn()

    assert calls == []
    assert boundary.state == "ready"


def test_native_rng_seed_and_arm_failure_attempts_fail_closed_restore(monkeypatch):
    calls = []
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_seed_and_arm",
        lambda capture_id: (_ for _ in ()).throw(RuntimeError("arm failed")),
    )
    monkeypatch.setattr(
        mod,
        "bridge_observatory_native_rng_finish",
        lambda capture_id: calls.append("finish") or ("FINISH", {}),
    )
    boundary = mod.NativeRngTurnBoundary(
        condition="exact_hook", capture_id="native-rng-pair-001-exact"
    )

    with pytest.raises(mod.NativeRngTurnBoundaryError, match="arm failed"):
        boundary.before_end_turn()

    assert calls == ["finish"]
    assert boundary.state == "rejected"
