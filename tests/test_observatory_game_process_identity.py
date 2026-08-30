from __future__ import annotations

import pytest

from src.observatory import game_process_identity as process_identity


def _file_identity(tmp_path) -> dict:
    return {
        "path": str((tmp_path / "Breach.exe").resolve()),
        "size": process_identity.EXPECTED_EXECUTABLE_SIZE,
        "sha256": process_identity.EXPECTED_EXECUTABLE_SHA256,
    }


def test_process_identity_binds_unique_pid_creation_time_and_exact_executable(
    tmp_path,
    monkeypatch,
):
    expected = _file_identity(tmp_path)
    monkeypatch.setattr(
        process_identity,
        "_stable_file_identity",
        lambda _path: expected,
    )
    monkeypatch.setattr(process_identity, "_tasklist_process_ids", lambda: [4217])
    monkeypatch.setattr(
        process_identity,
        "_windows_process_details",
        lambda pid: {
            "pid": pid,
            "creation_filetime": 133_800_000_000_000_000,
            "created_at": "2025-01-01T00:00:00+00:00",
            "executable_path": expected["path"],
        },
    )

    result = process_identity.capture_windows_game_process_identity(
        tmp_path / "Breach.exe"
    )

    assert result["pid"] == 4217
    assert result["creation_filetime"] == 133_800_000_000_000_000
    assert result["executable_sha256"] == process_identity.EXPECTED_EXECUTABLE_SHA256


def test_process_identity_rejects_multiple_processes_or_different_path(
    tmp_path,
    monkeypatch,
):
    expected = _file_identity(tmp_path)
    monkeypatch.setattr(
        process_identity,
        "_stable_file_identity",
        lambda _path: expected,
    )
    monkeypatch.setattr(
        process_identity,
        "_tasklist_process_ids",
        lambda: [100, 101],
    )
    with pytest.raises(process_identity.GameProcessIdentityError, match="exactly one"):
        process_identity.capture_windows_game_process_identity(
            tmp_path / "Breach.exe"
        )

    monkeypatch.setattr(process_identity, "_tasklist_process_ids", lambda: [100])
    monkeypatch.setattr(
        process_identity,
        "_windows_process_details",
        lambda pid: {
            "pid": pid,
            "creation_filetime": 133_800_000_000_000_000,
            "created_at": "2025-01-01T00:00:00+00:00",
            "executable_path": str((tmp_path / "other" / "Breach.exe").resolve()),
        },
    )
    with pytest.raises(process_identity.GameProcessIdentityError, match="path differs"):
        process_identity.capture_windows_game_process_identity(
            tmp_path / "Breach.exe"
        )


def test_process_identity_rejects_wrong_executable_before_process_enumeration(
    tmp_path,
    monkeypatch,
):
    expected = _file_identity(tmp_path)
    expected["sha256"] = "0" * 64
    calls: list[str] = []
    monkeypatch.setattr(
        process_identity,
        "_stable_file_identity",
        lambda _path: expected,
    )
    monkeypatch.setattr(
        process_identity,
        "_tasklist_process_ids",
        lambda: calls.append("tasklist") or [100],
    )

    with pytest.raises(process_identity.GameProcessIdentityError, match="build 13725832"):
        process_identity.capture_windows_game_process_identity(
            tmp_path / "Breach.exe"
        )

    assert calls == []


def test_exact_executable_validation_returns_stable_identity(tmp_path, monkeypatch):
    expected = _file_identity(tmp_path)
    monkeypatch.setattr(
        process_identity,
        "_stable_file_identity",
        lambda _path: expected,
    )

    assert process_identity.validate_windows_game_executable(
        tmp_path / "Breach.exe"
    ) == expected
