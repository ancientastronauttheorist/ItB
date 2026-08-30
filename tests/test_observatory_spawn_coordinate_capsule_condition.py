from __future__ import annotations

import argparse
import json

import pytest

from scripts import itb_observatory_spawn_coordinate_capsule_condition as condition


def _args(tmp_path) -> argparse.Namespace:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    save_root = tmp_path / "save"
    save_root.mkdir()
    snapshot_root = tmp_path / "snapshot"
    snapshot_root.mkdir()
    source_session = tmp_path / "active_session.json"
    source_session.write_text('{"mission_index": 0}', encoding="utf-8")
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(b"exe")
    module = tmp_path / "observer.dll"
    module.write_bytes(b"dll")
    build_receipt = tmp_path / "receipt.json"
    build_receipt.write_text("{}", encoding="utf-8")
    return argparse.Namespace(
        artifact_root=artifact_root,
        pair_id="spawn-capsule-pair001",
        condition="control",
        save_root=save_root,
        snapshot_root=snapshot_root,
        source_session=source_session,
        executable=executable,
        build_receipt=build_receipt,
        module=module,
        profile="Alpha",
        time_limit=10.0,
        max_wait=5.0,
        process_wait=5.0,
        bridge_wait=5.0,
        close_wait=5.0,
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


def _proof(tmp_path) -> dict:
    manifest = {
        "tree_sha256": "1" * 64,
        "file_count": 1,
        "total_bytes": 4,
    }
    return {
        "verified_at": "2026-08-29T12:00:00+00:00",
        "manifest_sha256": "2" * 64,
        "manifest": manifest,
        "game_stopped": True,
    }


def _runtime_modules(tmp_path) -> dict:
    return {
        role: {
            "path": str((tmp_path / f"{role}.dll").resolve()),
            "size": index,
            "sha256": str(index) * 64,
        }
        for index, role in enumerate(
            ("capsule_observer", "continue_helper", "rng_seed_helper"),
            start=1,
        )
    }


def _patch_success(tmp_path, monkeypatch, calls: list[str]) -> None:
    continue_request = tmp_path / "native-continue.request"
    monkeypatch.setattr(
        condition.bridge_protocol,
        "NATIVE_CONTINUE_REQUEST_FILE",
        continue_request,
    )
    monkeypatch.setattr(
        condition.bridge_protocol,
        "NATIVE_CONTINUE_REQUEST_BYTES",
        b"continue\n",
    )
    monkeypatch.setattr(
        condition.bridge_protocol,
        "ACK_FILE",
        tmp_path / "itb-ack.txt",
    )
    monkeypatch.setattr(
        condition,
        "validate_windows_game_executable",
        lambda path: {
            "path": str(path.resolve()),
            "size": 5_530_112,
            "sha256": "3" * 64,
        },
    )
    monkeypatch.setattr(
        condition,
        "validate_spawn_coordinate_capsule_build_identity",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        condition,
        "validate_capsule_runtime_modules",
        lambda *_args, **_kwargs: _runtime_modules(tmp_path),
    )
    monkeypatch.setattr(
        condition.pair_state,
        "restore_state",
        lambda _args: calls.append("restore") or 0,
    )
    monkeypatch.setattr(
        condition.pair_state,
        "_load_manifest",
        lambda _path: {
            "tree_sha256": "1" * 64,
            "file_count": 1,
            "total_bytes": 4,
        },
    )
    monkeypatch.setattr(
        condition.pair_state,
        "build_start_state_verification_proof",
        lambda *_args: calls.append("prove") or _proof(tmp_path),
    )

    def sandbox(args):
        calls.append("sandbox")
        args.output_session.write_text("{}", encoding="utf-8")
        return 0

    monkeypatch.setattr(condition.pair_state, "sandbox_session", sandbox)

    def arm():
        calls.append("arm")
        continue_request.write_bytes(b"continue\n")
        return continue_request

    monkeypatch.setattr(
        condition.bridge_protocol,
        "arm_observatory_native_continue_startup",
        arm,
    )
    monkeypatch.setattr(
        condition,
        "launch_exact_windows_game",
        lambda _path: calls.append("launch")
        or {"launcher_pid": 4217, "requested_at": "now"},
    )
    process_identity = {
        "pid": 4217,
        "creation_filetime": 133_800_000_000_000_000,
    }
    monkeypatch.setattr(
        condition,
        "wait_for_exact_windows_game_process",
        lambda *_args, **_kwargs: calls.append("process") or process_identity,
    )
    monkeypatch.setattr(
        condition,
        "_wait_for_native_continue_ack",
        lambda *_args, **_kwargs: calls.append("continue-ack")
        or condition.NATIVE_CONTINUE_ACK,
    )

    def bridge(*_args, **_kwargs):
        calls.append("bridge")
        continue_request.unlink()
        return {
            "mission_id": "Mission_Power",
            "phase": "combat_player",
            "turn": 1,
            "active_mechs": 3,
        }

    monkeypatch.setattr(condition, "_wait_for_bridge_start", bridge)

    def run_trial(args):
        calls.append("trial")
        value = {"status": "complete", "valid_trial": True}
        args.trial_output.write_text(json.dumps(value), encoding="utf-8")
        args.outcome_output.write_text("{}", encoding="utf-8")
        return 0, value

    monkeypatch.setattr(condition.trial_runner, "run", run_trial)
    monkeypatch.setattr(
        condition,
        "gracefully_close_exact_windows_game",
        lambda *_args, **_kwargs: calls.append("close")
        or {"exited": True, "forced_termination": False},
    )


def test_condition_runs_restore_to_graceful_close_in_exact_order(
    tmp_path,
    monkeypatch,
):
    args = _args(tmp_path)
    calls: list[str] = []
    _patch_success(tmp_path, monkeypatch, calls)

    code, receipt = condition.run(args)

    assert code == 0
    assert receipt["valid_lifecycle"] is True
    assert receipt["native_continue"]["consumed"] is True
    assert receipt["close"]["forced_termination"] is False
    assert calls == [
        "restore",
        "prove",
        "sandbox",
        "arm",
        "launch",
        "process",
        "continue-ack",
        "bridge",
        "trial",
        "close",
    ]
    lifecycle_path = (
        args.artifact_root / "pair001" / "control" / "lifecycle.json"
    )
    assert lifecycle_path.is_file()


def test_condition_closes_process_when_trial_rejects(tmp_path, monkeypatch):
    args = _args(tmp_path)
    calls: list[str] = []
    _patch_success(tmp_path, monkeypatch, calls)

    def reject(args):
        calls.append("trial-rejected")
        value = {"status": "rejected", "valid_trial": False}
        args.trial_output.write_text(json.dumps(value), encoding="utf-8")
        return 2, value

    monkeypatch.setattr(condition.trial_runner, "run", reject)

    code, receipt = condition.run(args)

    assert code == 2
    assert receipt["valid_lifecycle"] is False
    assert receipt["errors"]["trial"] == "capsule trial was rejected"
    assert calls[-2:] == ["trial-rejected", "close"]


def test_condition_recovers_exact_launched_identity_for_close_when_wait_fails(
    tmp_path,
    monkeypatch,
):
    args = _args(tmp_path)
    calls: list[str] = []
    _patch_success(tmp_path, monkeypatch, calls)
    recovered = {
        "pid": 4217,
        "creation_filetime": 133_800_000_000_000_000,
    }
    monkeypatch.setattr(
        condition,
        "wait_for_exact_windows_game_process",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("wait failed")),
    )
    monkeypatch.setattr(
        condition,
        "capture_windows_game_process_identity",
        lambda _path: calls.append("recover-process") or recovered,
    )

    code, receipt = condition.run(args)

    assert code == 2
    assert receipt["errors"]["process"] == "wait failed"
    assert receipt["process_identity"] == recovered
    assert calls[-2:] == ["recover-process", "close"]


def test_native_continue_ack_requires_a_fresh_exact_generation(tmp_path, monkeypatch):
    ack = tmp_path / "itb-ack.txt"
    ack.write_text("old ACK", encoding="utf-8")
    monkeypatch.setattr(condition.bridge_protocol, "ACK_FILE", ack)
    previous = condition._ack_fingerprint()
    ack.write_text(condition.NATIVE_CONTINUE_ACK, encoding="utf-8")

    assert condition._wait_for_native_continue_ack(
        previous,
        max_wait=0.5,
        poll_interval=0.02,
    ) == condition.NATIVE_CONTINUE_ACK
    assert not ack.exists()


def test_native_continue_ack_rejects_an_error_generation(tmp_path, monkeypatch):
    ack = tmp_path / "itb-ack.txt"
    monkeypatch.setattr(condition.bridge_protocol, "ACK_FILE", ack)
    ack.write_text("ERROR: Continue failed", encoding="utf-8")

    with pytest.raises(condition.CapsuleConditionError, match="ACK differs"):
        condition._wait_for_native_continue_ack(
            None,
            max_wait=0.5,
            poll_interval=0.02,
        )
    assert not ack.exists()


def test_active_player_actor_count_derives_missing_raw_summary_field():
    state = {
        "units": [
            {
                "team": 1,
                "hp": 3,
                "active": True,
                "mech": True,
                "weapons": [],
            },
            {
                "team": 1,
                "hp": 2,
                "active": True,
                "mech": False,
                "weapons": ["ArchiveArtillery"],
            },
            {
                "team": 1,
                "hp": 2,
                "active": False,
                "mech": True,
                "weapons": ["Prime_Punchmech"],
            },
            {
                "team": 6,
                "hp": 3,
                "active": True,
                "mech": False,
                "weapons": ["FireflyAtk1"],
            },
        ]
    }

    assert condition._active_player_actor_count(state) == 2
    assert condition._active_player_actor_count(
        {"active_mechs": 3, "units": []}
    ) == 3


def test_active_player_actor_count_fails_closed_on_malformed_player_unit():
    assert condition._active_player_actor_count(
        {
            "units": [
                {
                    "team": 1,
                    "hp": 3,
                    "active": True,
                    "mech": True,
                }
            ]
        }
    ) is None


def test_bridge_start_derives_active_actors_from_raw_bridge_units(
    tmp_path,
    monkeypatch,
):
    identity = {
        "pid": 4217,
        "creation_filetime": 133_800_000_000_000_000,
        "executable_path": str(tmp_path / "Breach.exe"),
    }
    monkeypatch.setattr(
        condition,
        "capture_windows_game_process_identity",
        lambda _path: identity,
    )
    monkeypatch.setattr(
        condition.bridge_protocol,
        "refresh_bridge_state_fresh",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        condition.bridge_protocol,
        "read_state",
        lambda: {
            "mission_id": "Mission_Power",
            "phase": "combat_player",
            "turn": 1,
            "in_active_mission": True,
            "units": [
                {
                    "team": 1,
                    "hp": 3,
                    "active": True,
                    "mech": True,
                    "weapons": ["Prime_Punchmech"],
                }
            ],
        },
    )
    monkeypatch.setattr(
        condition.bridge_protocol,
        "NATIVE_CONTINUE_REQUEST_FILE",
        tmp_path / "consumed.request",
    )

    result = condition._wait_for_bridge_start(
        identity,
        max_wait=0.5,
        poll_interval=0.01,
    )

    assert result["active_mechs"] == 1


def test_condition_support_module_preflight_blocks_before_restore(
    tmp_path,
    monkeypatch,
):
    args = _args(tmp_path)
    calls: list[str] = []
    _patch_success(tmp_path, monkeypatch, calls)
    monkeypatch.setattr(
        condition,
        "validate_capsule_runtime_modules",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            condition.CapsuleRuntimeModuleError("continue helper is missing")
        ),
    )

    with pytest.raises(
        condition.CapsuleRuntimeModuleError,
        match="continue helper is missing",
    ):
        condition.run(args)
    assert calls == []
