"""Exact Windows process identity for fresh-process Observatory campaigns."""

from __future__ import annotations

import csv
import ctypes
import hashlib
import os
import subprocess
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
IDENTITY_KIND = "observatory_windows_game_process_identity"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
_WINDOWS_EPOCH_FILETIME = 116_444_736_000_000_000


class GameProcessIdentityError(RuntimeError):
    """Raised when a unique exact-build game process cannot be proven."""


def _stable_file_identity(path: Path) -> dict[str, Any]:
    candidate = Path(os.path.abspath(path))
    if candidate.is_symlink() or not candidate.is_file():
        raise GameProcessIdentityError(
            f"game executable is not a regular file: {candidate}"
        )
    before = candidate.stat()
    data = candidate.read_bytes()
    after = candidate.stat()
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise GameProcessIdentityError("game executable changed while read")
    return {
        "path": str(candidate.resolve()),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _tasklist_process_ids() -> list[int]:
    if os.name != "nt":
        raise GameProcessIdentityError("game process identity requires Windows")
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Breach.exe", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GameProcessIdentityError(f"cannot enumerate Breach.exe: {exc}") from exc
    if result.returncode != 0:
        raise GameProcessIdentityError("tasklist failed while enumerating Breach.exe")
    pids: set[int] = set()
    for row in csv.reader(result.stdout.splitlines()):
        if not row or row[0].casefold() != "breach.exe":
            continue
        if len(row) < 2 or not row[1].replace(",", "").isdigit():
            raise GameProcessIdentityError("tasklist returned an invalid Breach.exe PID")
        pids.add(int(row[1].replace(",", "")))
    return sorted(pids)


def _windows_process_details(pid: int) -> dict[str, Any]:
    if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
        raise GameProcessIdentityError("game process identity requires Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        raise GameProcessIdentityError(f"cannot open Breach.exe process {pid}")
    try:
        size = wintypes.DWORD(32_768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(size),
        ):
            raise GameProcessIdentityError(
                f"cannot read Breach.exe process path for {pid}"
            )
        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise GameProcessIdentityError(
                f"cannot read Breach.exe process time for {pid}"
            )
    finally:
        kernel32.CloseHandle(handle)
    creation_filetime = (
        int(created.dwHighDateTime) << 32
    ) + int(created.dwLowDateTime)
    if creation_filetime <= _WINDOWS_EPOCH_FILETIME:
        raise GameProcessIdentityError("Breach.exe process creation time is invalid")
    created_unix = (
        creation_filetime - _WINDOWS_EPOCH_FILETIME
    ) / 10_000_000.0
    return {
        "pid": pid,
        "creation_filetime": creation_filetime,
        "created_at": datetime.fromtimestamp(
            created_unix,
            tz=timezone.utc,
        ).isoformat(),
        "executable_path": str(Path(buffer.value).resolve()),
    }


def capture_windows_game_process_identity(executable: Path) -> dict[str, Any]:
    """Require one running exact-build Breach.exe and return its stable identity."""
    expected = validate_windows_game_executable(executable)
    pids = _tasklist_process_ids()
    if len(pids) != 1:
        raise GameProcessIdentityError(
            f"expected exactly one Breach.exe process, found {len(pids)}"
        )
    details = _windows_process_details(pids[0])
    process_path = Path(details["executable_path"])
    if os.path.normcase(str(process_path)) != os.path.normcase(str(expected["path"])):
        raise GameProcessIdentityError(
            "running Breach.exe path differs from the expected executable"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": IDENTITY_KIND,
        "pid": details["pid"],
        "creation_filetime": details["creation_filetime"],
        "created_at": details["created_at"],
        "executable_path": expected["path"],
        "executable_size": expected["size"],
        "executable_sha256": expected["sha256"],
    }


def validate_windows_game_executable(executable: Path) -> dict[str, Any]:
    """Return the stable identity of the exact accepted build 13725832 image."""
    expected = _stable_file_identity(executable)
    if (
        expected["size"] != EXPECTED_EXECUTABLE_SIZE
        or expected["sha256"] != EXPECTED_EXECUTABLE_SHA256
    ):
        raise GameProcessIdentityError("game executable differs from build 13725832")
    return expected
