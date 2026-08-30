from __future__ import annotations

import pytest

from src.observatory import windows_game_lifecycle as lifecycle


def _identity(pid: int = 4217, creation: int = 133_800_000_000_000_000) -> dict:
    return {
        "pid": pid,
        "creation_filetime": creation,
        "created_at": "2025-01-01T00:00:00+00:00",
    }


def test_launch_requires_empty_process_set_and_exact_executable(tmp_path, monkeypatch):
    executable = tmp_path / "Breach.exe"
    expected = {
        "path": str(executable.resolve()),
        "size": 5_530_112,
        "sha256": "1" * 64,
    }
    calls: list[tuple] = []

    class Process:
        pid = 4217

    monkeypatch.setattr(lifecycle.os, "name", "nt")
    monkeypatch.setattr(
        lifecycle,
        "validate_windows_game_executable",
        lambda _path: expected,
    )
    monkeypatch.setattr(lifecycle, "_tasklist_process_ids", lambda: [])
    monkeypatch.setattr(
        lifecycle.subprocess,
        "Popen",
        lambda *args, **kwargs: calls.append((args, kwargs)) or Process(),
    )

    result = lifecycle.launch_exact_windows_game(executable)

    assert result["launcher_pid"] == 4217
    assert calls[0][0][0] == [expected["path"]]


def test_launch_rejects_an_existing_game_before_popen(tmp_path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(lifecycle.os, "name", "nt")
    monkeypatch.setattr(
        lifecycle,
        "validate_windows_game_executable",
        lambda _path: {"path": str(tmp_path / "Breach.exe")},
    )
    monkeypatch.setattr(lifecycle, "_tasklist_process_ids", lambda: [99])
    monkeypatch.setattr(
        lifecycle.subprocess,
        "Popen",
        lambda *_args, **_kwargs: calls.append("popen"),
    )

    with pytest.raises(lifecycle.WindowsGameLifecycleError, match="already running"):
        lifecycle.launch_exact_windows_game(tmp_path / "Breach.exe")

    assert calls == []


def test_wait_binds_the_launched_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle.os, "name", "nt")
    monkeypatch.setattr(
        lifecycle,
        "validate_windows_game_executable",
        lambda _path: {},
    )
    process_sets = iter(([], [4217]))
    monkeypatch.setattr(
        lifecycle,
        "_tasklist_process_ids",
        lambda: next(process_sets),
    )
    monkeypatch.setattr(
        lifecycle,
        "capture_windows_game_process_identity",
        lambda _path: _identity(),
    )

    assert lifecycle.wait_for_exact_windows_game_process(
        tmp_path / "Breach.exe",
        expected_pid=4217,
        timeout=1.0,
        poll_interval=0.02,
    )["creation_filetime"] == 133_800_000_000_000_000


def test_graceful_close_targets_exact_identity_without_force(tmp_path, monkeypatch):
    posted: list[int] = []
    monkeypatch.setattr(lifecycle.os, "name", "nt")
    monkeypatch.setattr(
        lifecycle,
        "capture_windows_game_process_identity",
        lambda _path: _identity(),
    )
    monkeypatch.setattr(
        lifecycle,
        "_windows_game_window_handles",
        lambda _pid: [1001],
    )
    monkeypatch.setattr(
        lifecycle,
        "_post_close_message",
        lambda hwnd: posted.append(hwnd),
    )
    monkeypatch.setattr(lifecycle, "_tasklist_process_ids", lambda: [])

    result = lifecycle.gracefully_close_exact_windows_game(
        tmp_path / "Breach.exe",
        _identity(),
        timeout=1.0,
    )

    assert posted == [1001]
    assert result["exited"] is True
    assert result["forced_termination"] is False


def test_graceful_close_refuses_a_replaced_process(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle.os, "name", "nt")
    monkeypatch.setattr(
        lifecycle,
        "capture_windows_game_process_identity",
        lambda _path: _identity(creation=133_900_000_000_000_000),
    )

    with pytest.raises(lifecycle.WindowsGameLifecycleError, match="different"):
        lifecycle.gracefully_close_exact_windows_game(
            tmp_path / "Breach.exe",
            _identity(),
        )
