"""Proof that ordinary pytest cannot bind to live ITB runtime paths."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.bridge import protocol, reader
from src.itb_paths import (
    get_artifact_path,
    get_artifact_root,
    get_bridge_dir,
    get_save_dir,
)
from src.loop import commands, lightning_telemetry, logger, weapon_penalty_log
from src.research import comparator, pattern_miner, wiki_client
from src.solver import analysis, diagnosis, weapon_overrides
from src.strategy import achievement_sync, run_planner
from src.loop.session import (
    DEFAULT_SESSION_FILE,
    LIVE_SESSION_FILE,
    SESSION_DIR,
    RunSession,
    configured_default_session_file,
    resolve_session_file,
)


def test_default_session_save_is_process_isolated():
    repo_root = Path(__file__).resolve().parents[1]
    live_session = (repo_root / "sessions" / "active_session.json").resolve()
    configured = Path(os.environ["ITB_SESSION_FILE"]).resolve()

    assert DEFAULT_SESSION_FILE.resolve() == configured
    assert DEFAULT_SESSION_FILE.resolve() != live_session
    assert not DEFAULT_SESSION_FILE.resolve().is_relative_to(repo_root)
    assert RunSession.save.__defaults__ == (None,)
    assert RunSession.load.__func__.__defaults__ == (None,)

    session = RunSession()
    session.save()
    assert DEFAULT_SESSION_FILE.is_file()
    assert RunSession.load().to_dict() == session.to_dict()


def test_save_and_bridge_roots_are_process_isolated():
    repo_root = Path(__file__).resolve().parents[1]
    expected_save = Path(os.environ["ITB_SAVE_DIR"]).resolve()
    expected_bridge = Path(os.environ["ITB_BRIDGE_DIR"]).resolve()

    assert get_save_dir().resolve() == expected_save
    assert get_bridge_dir().resolve() == expected_bridge
    assert protocol.BRIDGE_DIR.resolve() == expected_bridge
    assert not expected_save.is_relative_to(repo_root)
    assert not expected_bridge.is_relative_to(repo_root)


def test_mutable_artifacts_are_process_isolated():
    repo_root = Path(__file__).resolve().parents[1]
    artifact_root = Path(os.environ["ITB_ARTIFACT_ROOT"]).resolve()
    paths = (
        commands.RECORDING_DIR,
        commands.SNAPSHOT_DIR,
        logger.LOG_DIR,
        lightning_telemetry.DEFAULT_RECORDINGS_ROOT,
        lightning_telemetry.DEFAULT_RUN_NOTES_ROOT,
        weapon_penalty_log._LOG_PATH,
        analysis.FAILURE_DB_PATH,
        diagnosis.FAILURE_DB_PATH,
        diagnosis.REJECTIONS_PATH,
        comparator.MISMATCHES_PATH,
        pattern_miner.DEFAULT_FAILURE_PATH,
        pattern_miner.DEFAULT_DENY_PATH,
        pattern_miner.DEFAULT_RECORDINGS_ROOT,
        wiki_client.WIKI_CACHE_DIR,
        weapon_overrides.DEFAULT_OVERRIDES_PATH,
        weapon_overrides.DEFAULT_STAGED_PATH,
        achievement_sync.ACHIEVEMENTS_PATH,
        run_planner.ACHIEVEMENTS_PATH,
    )

    assert get_artifact_root().resolve() == artifact_root
    assert not artifact_root.is_relative_to(repo_root)
    assert all(path.resolve().is_relative_to(artifact_root) for path in paths)


def test_repair_pickup_fallback_reads_isolated_save_root():
    save_file = get_save_dir() / "profile_Alpha" / "saveData.lua"
    save_file.parent.mkdir(parents=True, exist_ok=True)
    save_file.write_text(
        '{["Mission"] = {["RepairPickups"] = 2,},}',
        encoding="utf-8",
    )

    assert reader._read_repair_pickups_from_save() == 2


def test_session_override_requires_an_absolute_path():
    assert configured_default_session_file({}) == (
        SESSION_DIR / "active_session.json"
    )
    with pytest.raises(ValueError, match="absolute"):
        configured_default_session_file({"ITB_SESSION_FILE": "relative.json"})


def test_artifact_override_requires_an_absolute_path():
    repo_root = Path(__file__).resolve().parents[1]
    isolated_root = get_artifact_root().resolve()
    with pytest.raises(ValueError, match="absolute"):
        get_artifact_root({"ITB_ARTIFACT_ROOT": "relative"})
    with pytest.raises(RuntimeError, match="refused"):
        get_artifact_root({"ITB_PYTEST_RUNTIME_GUARD": "1"})
    for unsafe_root in (repo_root / "pytest-artifacts", repo_root.parent):
        with pytest.raises(RuntimeError, match="overlapping"):
            get_artifact_root({
                "ITB_ARTIFACT_ROOT": str(unsafe_root),
                "ITB_PYTEST_RUNTIME_GUARD": "1",
            })
    with pytest.raises(ValueError, match="escapes"):
        get_artifact_path("..", "escaped.json")
    with pytest.raises(ValueError, match="escapes"):
        get_artifact_path(str(isolated_root.parent / "absolute-escape.json"))
    assert get_artifact_path(
        "recordings",
        "failure_db.jsonl",
    ).resolve().is_relative_to(isolated_root)


def test_no_argument_session_path_is_resolved_at_call_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    monkeypatch.setenv("ITB_SESSION_FILE", str(first))
    RunSession(run_id="first").save()
    monkeypatch.setenv("ITB_SESSION_FILE", str(second))
    RunSession(run_id="second").save()

    assert RunSession.load().run_id == "second"
    monkeypatch.setenv("ITB_SESSION_FILE", str(first))
    assert RunSession.load().run_id == "first"


def test_pytest_guard_rejects_live_session_before_io(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("ITB_SESSION_FILE", str(LIVE_SESSION_FILE))
    monkeypatch.setenv("ITB_PYTEST_SESSION_GUARD", "1")

    with pytest.raises(RuntimeError, match="refused"):
        resolve_session_file()
    with pytest.raises(RuntimeError, match="refused"):
        RunSession.load()
    with pytest.raises(RuntimeError, match="refused"):
        RunSession().save(LIVE_SESSION_FILE)
