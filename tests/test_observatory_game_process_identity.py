from __future__ import annotations

import ctypes

import pytest

from src.observatory import game_process_identity as process_identity


def _file_identity(tmp_path) -> dict:
    return {
        "path": str((tmp_path / "Breach.exe").resolve()),
        "size": process_identity.EXPECTED_EXECUTABLE_SIZE,
        "sha256": process_identity.EXPECTED_EXECUTABLE_SHA256,
    }


class _FakeWindowsCall:
    def __init__(self, function):
        self.function = function
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.function(*args)


def test_native_process_snapshot_enumerates_only_breach_pids(monkeypatch):
    last_error = {"value": 0}
    rows = [(4, "System"), (4217, "Breach.exe"), (5000, "python.exe")]

    class Kernel32:
        def __init__(self):
            self.index = -1
            self.closed: list[int] = []
            self.CreateToolhelp32Snapshot = _FakeWindowsCall(lambda *_args: 9001)
            self.Process32FirstW = _FakeWindowsCall(self.first)
            self.Process32NextW = _FakeWindowsCall(self.next)
            self.CloseHandle = _FakeWindowsCall(self.close)

        def write_row(self, pointer) -> None:
            pid, name = rows[self.index]
            pointer._obj.th32ProcessID = pid
            pointer._obj.szExeFile = name

        def first(self, _snapshot, pointer) -> int:
            self.index = 0
            self.write_row(pointer)
            return 1

        def next(self, _snapshot, pointer) -> int:
            self.index += 1
            if self.index >= len(rows):
                last_error["value"] = process_identity._ERROR_NO_MORE_FILES
                return 0
            self.write_row(pointer)
            return 1

        def close(self, snapshot) -> int:
            self.closed.append(snapshot)
            return 1

    kernel32 = Kernel32()
    monkeypatch.setattr(process_identity.os, "name", "nt")
    monkeypatch.setattr(
        process_identity.ctypes,
        "WinDLL",
        lambda *_args, **_kwargs: kernel32,
        raising=False,
    )
    monkeypatch.setattr(
        process_identity.ctypes,
        "set_last_error",
        lambda value: last_error.__setitem__("value", value),
        raising=False,
    )
    monkeypatch.setattr(
        process_identity.ctypes,
        "get_last_error",
        lambda: last_error["value"],
        raising=False,
    )

    assert process_identity.windows_breach_process_ids() == [4217]
    assert kernel32.closed == [9001]


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
    monkeypatch.setattr(
        process_identity,
        "windows_breach_process_ids",
        lambda: [4217],
    )
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
        "windows_breach_process_ids",
        lambda: [100, 101],
    )
    with pytest.raises(process_identity.GameProcessIdentityError, match="exactly one"):
        process_identity.capture_windows_game_process_identity(
            tmp_path / "Breach.exe"
        )

    monkeypatch.setattr(
        process_identity,
        "windows_breach_process_ids",
        lambda: [100],
    )
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
        "windows_breach_process_ids",
        lambda: calls.append("enumerate") or [100],
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
