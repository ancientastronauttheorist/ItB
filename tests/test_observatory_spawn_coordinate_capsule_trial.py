from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import itb_observatory_spawn_coordinate_capsule_trial as trial
from src.loop import commands as loop_commands
from src.observatory import spawn_coordinate_capsule_turn as turn
from src.observatory.game_process_identity import GameProcessIdentityError
from src.observatory.start_state_proof import (
    MANIFEST_KIND,
    MANIFEST_SCHEMA_VERSION,
    PROOF_KIND,
    SCHEMA_VERSION as START_STATE_SCHEMA_VERSION,
    StartStateProofError,
    start_state_manifest_sha256,
    start_state_tree_sha256,
)
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
        executable=root.parent / "Breach.exe",
        start_state_proof=condition_root / "start_state_proof.json",
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


def _native_end_turn() -> dict:
    return {
        "status": "OK",
        "bridge": True,
        "ack": "OK END_TURN phase=combat_player method=observatory_native",
        "delivery_confirmation": "delivered_confirmed",
        "retry_allowed": False,
        "end_turn_plan_id": "plan-001",
        "end_turn_plan_source": "auto_turn",
        "end_turn_delivery_mode": "external",
    }


def _auto_result(boundary_summary: dict) -> dict:
    return {
        "status": "ok",
        "turn": 1,
        "actions_completed": 3,
        "desyncs_detected": 0,
        "post_phase": "combat_player",
        "grid_power": "2/7",
        "observatory_native_rng_boundary": boundary_summary,
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
    files = [
        {
            "relative_path": "profile_Alpha/saveData.lua",
            "size": 4,
            "sha256": "1" * 64,
        }
    ]
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "kind": MANIFEST_KIND,
        "capture_track": "owner_local_modified",
        "profile": "Alpha",
        "file_count": 1,
        "total_bytes": 4,
        "files": files,
        "tree_sha256": start_state_tree_sha256(files),
    }
    proof = {
        "schema_version": START_STATE_SCHEMA_VERSION,
        "kind": PROOF_KIND,
        "verified_at": "2024-12-31T23:59:59+00:00",
        "game_stopped": True,
        "save_root": str((tmp_path / "save").resolve()),
        "snapshot_root": str((tmp_path / "snapshot").resolve()),
        "manifest_sha256": start_state_manifest_sha256(manifest),
        "manifest": manifest,
    }
    for condition in ("control", "dormant", "armed"):
        condition_root = root / condition
        condition_root.mkdir()
        (condition_root / "start_state_proof.json").write_text(
            json.dumps(proof),
            encoding="utf-8",
        )
    monkeypatch.setenv("ITB_ARTIFACT_ROOT", str(root))
    monkeypatch.setenv("ITB_SESSION_FILE", str(root / "session.json"))
    (root / "session.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        trial,
        "validate_spawn_coordinate_capsule_build_identity",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        trial,
        "capture_windows_game_process_identity",
        lambda _path: {
            "schema_version": 1,
            "kind": "observatory_windows_game_process_identity",
            "pid": 4217,
            "creation_filetime": 133_800_000_000_000_000,
            "created_at": "2025-01-01T00:00:00+00:00",
            "executable_path": str((root.parent / "Breach.exe").resolve()),
            "executable_size": 5_530_112,
            "executable_sha256": (
                "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
            ),
        },
    )
    return root, receipt, module


def test_control_trial_wraps_exact_native_end_turn_and_captures_next_turn(
    tmp_path,
    monkeypatch,
):
    root, receipt, module = _inputs(tmp_path, monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(
        trial,
        "_fresh_state",
        lambda **_kwargs: calls.append("fresh") or _state(2),
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

    def auto_turn(**kwargs):
        calls.append("auto_turn")
        boundary = kwargs["_observatory_native_rng_boundary"]
        boundary.before_end_turn()
        calls.append("native_end_turn")
        summary = boundary.after_end_turn(_native_end_turn())
        return _auto_result(summary)

    monkeypatch.setattr(trial, "cmd_auto_turn", auto_turn)

    code, result = trial.run(
        _args(root, receipt, module, condition="control")
    )

    assert code == 0
    assert result["valid_trial"] is True
    assert result["process_identity"]["pid"] == 4217
    assert len(result["start_state"]["tree_sha256"]) == 64
    assert result["boundary"]["state"] == "complete"
    assert calls == [
        "auto_turn",
        "prepare",
        "native_end_turn",
        "finish",
        "fresh",
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
    calls: list[str] = []
    monkeypatch.setattr(trial, "_fresh_state", lambda **_kwargs: _state(2))
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

    def auto_turn(**kwargs):
        boundary = kwargs["_observatory_native_rng_boundary"]
        boundary.before_end_turn()
        summary = boundary.after_end_turn(_native_end_turn())
        return _auto_result(summary)

    monkeypatch.setattr(trial, "cmd_auto_turn", auto_turn)
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


def test_rejected_auto_turn_never_prepares_native_boundary(
    tmp_path,
    monkeypatch,
):
    root, receipt, module = _inputs(tmp_path, monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(
        trial,
        "cmd_auto_turn",
        lambda **_kwargs: calls.append("auto_turn")
        or {"status": "SAFETY_BLOCKED", "blocking": True},
    )
    monkeypatch.setattr(
        turn,
        "prepare_observatory_spawn_coordinate_capsule",
        lambda *_args: calls.append("prepare"),
    )

    code, result = trial.run(
        _args(root, receipt, module, condition="dormant")
    )

    assert code == 2
    assert result["status"] == "rejected"
    assert result["errors"]["runner"]
    assert calls == ["auto_turn"]
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
        "_run_with_native_boundary",
        lambda *_args: calls.append("run"),
    )

    with pytest.raises(SpawnCoordinateCapsuleHwError, match="wrong capsule build"):
        trial.run(_args(root, receipt, module, condition="control"))

    assert calls == []


def test_process_identity_preflight_blocks_before_any_session_action(
    tmp_path,
    monkeypatch,
):
    root, receipt, module = _inputs(tmp_path, monkeypatch)
    calls: list[str] = []

    def reject(_path):
        raise GameProcessIdentityError("stale game process")

    monkeypatch.setattr(trial, "capture_windows_game_process_identity", reject)
    monkeypatch.setattr(
        trial,
        "_run_with_native_boundary",
        lambda *_args: calls.append("run"),
    )

    with pytest.raises(GameProcessIdentityError, match="stale game process"):
        trial.run(_args(root, receipt, module, condition="control"))

    assert calls == []


def test_start_state_preflight_blocks_before_any_session_action(
    tmp_path,
    monkeypatch,
):
    root, receipt, module = _inputs(tmp_path, monkeypatch)
    calls: list[str] = []

    def reject(*_args, **_kwargs):
        raise StartStateProofError("wrong restored tree")

    monkeypatch.setattr(trial, "validate_start_state_verification_proof", reject)
    monkeypatch.setattr(
        trial,
        "_run_with_native_boundary",
        lambda *_args: calls.append("run"),
    )

    with pytest.raises(StartStateProofError, match="wrong restored tree"):
        trial.run(_args(root, receipt, module, condition="control"))

    assert calls == []


def test_imported_trial_isolates_local_delivery_env_and_passes_native_boundary(
    monkeypatch,
):
    calls: list[str] = []
    args = SimpleNamespace(
        profile="Alpha",
        time_limit=10.0,
        max_wait=5.0,
        allow_dirty_plan=False,
        candidate_rank=None,
        dirty_consent_id=None,
        allow_protected_objective_loss=False,
        allow_objective_loss=False,
        allow_timeline_collapse=False,
        allow_mech_loss=False,
        frontier_diagnostics=True,
    )
    boundary = object()
    monkeypatch.setenv("ITB_LIGHTNING_LOCAL_END_TURN", "inherited")
    monkeypatch.setattr(
        trial,
        "_configure_utf8_stdio",
        lambda: calls.append("utf8"),
    )
    def auto_turn(**kwargs):
        calls.append("auto_turn")
        assert "ITB_LIGHTNING_LOCAL_END_TURN" not in trial.os.environ
        assert kwargs["_observatory_native_rng_boundary"] is boundary
        return {"status": "SAFETY_BLOCKED"}

    monkeypatch.setattr(trial, "cmd_auto_turn", auto_turn)

    assert trial._run_with_native_boundary(args, boundary) == {
        "status": "SAFETY_BLOCKED"
    }
    assert calls == ["utf8", "auto_turn"]
    assert trial.os.environ["ITB_LIGHTNING_LOCAL_END_TURN"] == "inherited"


def test_utf8_stdio_configuration_reconfigures_supported_streams():
    class Stream:
        def __init__(self):
            self.calls: list[dict] = []

        def reconfigure(self, **kwargs) -> None:
            self.calls.append(kwargs)

    stdout = Stream()
    stderr = Stream()

    trial._configure_utf8_stdio((stdout, stderr, object()))

    expected = [{"encoding": "utf-8", "errors": "replace"}]
    assert stdout.calls == expected
    assert stderr.calls == expected


def test_late_artifact_root_redirects_imported_recording_directory(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("ITB_ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setattr(
        loop_commands,
        "RECORDING_DIR",
        loop_commands._IMPORTED_RECORDING_DIR,
    )

    result = loop_commands._recording_dir(
        SimpleNamespace(run_id="spawn-capsule-pair001-control")
    )

    assert result == tmp_path / "recordings" / "spawn-capsule-pair001-control"
    assert result.is_dir()
