from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts import itb_observatory_spawn_coordinate_capsule_trial as trial
from src.observatory import spawn_coordinate_capsule_turn as turn
from src.observatory.spawn_coordinate_capsule_hw import SpawnCoordinateCapsuleHwError


def _args(
    root: Path,
    receipt: Path,
    module: Path,
    *,
    condition: str,
) -> argparse.Namespace:
    condition_root = root / condition
    return argparse.Namespace(
        pair_id="spawn-capsule-pair001",
        condition=condition,
        capture_id=f"spawn-capsule-pair001-{condition}",
        build_receipt=receipt,
        module=module,
        trial_output=condition_root / "trial.json",
        outcome_output=condition_root / "outcome.json",
        snapshot_output=(condition_root / "snapshot.json" if condition == "armed" else None),
        analysis_output=(condition_root / "analysis.json" if condition == "armed" else None),
        profile="Alpha",
        time_limit=10.0,
        max_wait=5.0,
        wait_poll_interval=0.05,
        candidate_rank=None,
        allow_dirty_plan=False,
        dirty_consent_id=None,
        allow_protected_objective_loss=False,
        allow_objective_loss=False,
        allow_timeline_collapse=False,
        allow_mech_loss=False,
        frontier_diagnostics=True,
    )


def _reservation() -> dict:
    return {
        "status": "PLAN",
        "turn": 1,
        "actions_completed": 3,
        "desyncs_detected": 0,
        "local_end_turn_reserved": True,
        "end_turn_plan_id": "plan-001",
        "end_turn_plan_source": "lightning_loop",
        "end_turn_delivery_mode": "local",
    }


def _dispatch() -> dict:
    return {
        "status": "DISPATCHED",
        "dispatch": {"delivery_confirmation": "delivered_confirmed"},
    }


def _state(turn_number: int) -> dict:
    return {
        "mission_id": "Mission_Power",
        "phase": "combat_player",
        "turn": turn_number,
        "in_active_mission": True,
        "spawning_tiles": [[5, 2]],
    }


def _inputs(tmp_path: Path, monkeypatch):
    root = tmp_path / "artifacts"
    root.mkdir()
    receipt = tmp_path / "build-receipt.json"
    module = tmp_path / "observer.dll"
    receipt.write_text("{}", encoding="utf-8")
    module.write_bytes(b"capsule-module")
    monkeypatch.setenv("ITB_ARTIFACT_ROOT", str(root))
    monkeypatch.setenv("ITB_SESSION_FILE", str(root / "session.json"))
    monkeypatch.setattr(
        trial,
        "validate_spawn_coordinate_capsule_build_identity",
        lambda *_args, **_kwargs: {},
    )
    return root, receipt, module


def test_control_trial_prepares_only_after_reservation_and_finishes_before_pause(
    tmp_path,
    monkeypatch,
):
    root, receipt, module = _inputs(tmp_path, monkeypatch)
    calls: list[str] = []
    states = iter([_state(1), _state(2)])
    monkeypatch.setattr(
        trial,
        "_reserve_with_auto_turn",
        lambda _args: calls.append("reserve") or _reservation(),
    )
    monkeypatch.setattr(
        trial,
        "_fresh_state",
        lambda **_kwargs: calls.append("fresh") or next(states),
    )
    monkeypatch.setattr(
        turn,
        "prepare_observatory_spawn_coordinate_capsule",
        lambda *_args: calls.append("prepare") or "prepared",
    )
    monkeypatch.setattr(
        turn,
        "finish_observatory_spawn_coordinate_capsule",
        lambda *_args: calls.append("finish") or ("finished", None),
    )
    monkeypatch.setattr(
        trial,
        "cmd_dispatch_end_turn",
        lambda **_kwargs: calls.append("dispatch") or _dispatch(),
    )
    monkeypatch.setattr(
        trial,
        "cmd_lightning_snap_pause",
        lambda *_args, **_kwargs: calls.append("pause")
        or {"status": "OK", "pause_verified": True, "safe_to_think": True},
    )

    code, result = trial.run(
        _args(root, receipt, module, condition="control")
    )

    assert code == 0
    assert result["valid_trial"] is True
    assert result["boundary"]["state"] == "complete"
    assert calls == [
        "reserve",
        "fresh",
        "prepare",
        "dispatch",
        "fresh",
        "finish",
        "pause",
    ]
    assert json.loads((root / "control" / "outcome.json").read_text())["turn"] == 2


def test_armed_trial_publishes_analysis_then_consumes_exact_bridge_snapshot(
    tmp_path,
    monkeypatch,
):
    root, receipt, module = _inputs(tmp_path, monkeypatch)
    snapshot = {
        "summary": {"draw_record_count": 1, "capsule_count": 1},
        "integrity": {"complete": True},
    }
    states = iter([_state(1), _state(2)])
    calls: list[str] = []
    monkeypatch.setattr(trial, "_reserve_with_auto_turn", lambda _args: _reservation())
    monkeypatch.setattr(trial, "_fresh_state", lambda **_kwargs: next(states))
    monkeypatch.setattr(
        turn,
        "prepare_observatory_spawn_coordinate_capsule",
        lambda *_args: "prepared",
    )
    monkeypatch.setattr(
        turn,
        "finish_observatory_spawn_coordinate_capsule",
        lambda *_args: ("finished", snapshot),
    )
    monkeypatch.setattr(trial, "cmd_dispatch_end_turn", lambda **_kwargs: _dispatch())
    monkeypatch.setattr(
        trial,
        "cmd_lightning_snap_pause",
        lambda *_args, **_kwargs: {
            "status": "OK",
            "pause_verified": True,
            "safe_to_think": True,
        },
    )
    monkeypatch.setattr(
        trial,
        "correlate_spawn_coordinate_capsule_snapshot",
        lambda *_args, **_kwargs: {
            "kind": "spawn_coordinate_capsule_hw_correlation",
            "status": "correlated",
        },
    )
    monkeypatch.setattr(
        trial,
        "consume_observatory_spawn_coordinate_capsule_snapshot",
        lambda observed: calls.append("consume") if observed is snapshot else None,
    )

    code, result = trial.run(_args(root, receipt, module, condition="armed"))

    assert code == 0
    assert result["valid_trial"] is True
    assert result["snapshot_consumed_from_bridge"] is True
    assert calls == ["consume"]
    assert (root / "armed" / "snapshot.json").is_file()
    assert (root / "armed" / "analysis.json").is_file()


def test_rejected_reservation_never_prepares_or_dispatches_and_still_pauses(
    tmp_path,
    monkeypatch,
):
    root, receipt, module = _inputs(tmp_path, monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(
        trial,
        "_reserve_with_auto_turn",
        lambda _args: {"status": "SAFETY_BLOCKED", "blocking": True},
    )
    monkeypatch.setattr(
        trial,
        "cmd_dispatch_end_turn",
        lambda **_kwargs: calls.append("dispatch"),
    )
    monkeypatch.setattr(
        turn,
        "prepare_observatory_spawn_coordinate_capsule",
        lambda *_args: calls.append("prepare"),
    )
    monkeypatch.setattr(
        trial,
        "cmd_lightning_snap_pause",
        lambda *_args, **_kwargs: calls.append("pause")
        or {"status": "OK", "pause_verified": True, "safe_to_think": True},
    )

    code, result = trial.run(
        _args(root, receipt, module, condition="dormant")
    )

    assert code == 2
    assert result["status"] == "rejected"
    assert result["errors"]["reservation"]
    assert calls == ["pause"]
    assert not (root / "dormant" / "outcome.json").exists()


def test_build_identity_preflight_blocks_before_any_session_action(
    tmp_path,
    monkeypatch,
):
    root, receipt, module = _inputs(tmp_path, monkeypatch)
    calls: list[str] = []

    def reject(*_args, **_kwargs):
        raise SpawnCoordinateCapsuleHwError("wrong capsule build")

    monkeypatch.setattr(
        trial,
        "validate_spawn_coordinate_capsule_build_identity",
        reject,
    )
    monkeypatch.setattr(
        trial,
        "_reserve_with_auto_turn",
        lambda _args: calls.append("reserve"),
    )
    monkeypatch.setattr(
        trial,
        "cmd_lightning_snap_pause",
        lambda *_args, **_kwargs: calls.append("pause"),
    )

    with pytest.raises(SpawnCoordinateCapsuleHwError, match="wrong capsule build"):
        trial.run(_args(root, receipt, module, condition="control"))

    assert calls == []
