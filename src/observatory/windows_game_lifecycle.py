"""Exact-build Windows launch and graceful-close helpers for Observatory trials."""

from __future__ import annotations

import ctypes
import os
import subprocess
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.observatory.game_process_identity import (
    GameProcessIdentityError,
    capture_windows_game_process_identity,
    validate_windows_game_executable,
    windows_breach_process_ids,
)


class WindowsGameLifecycleError(RuntimeError):
    """Raised when a fresh exact process cannot be launched or closed safely."""


def launch_exact_windows_game(executable: Path) -> dict[str, Any]:
    """Launch the exact accepted Breach.exe only when no copy is running."""
    if os.name != "nt":
        raise WindowsGameLifecycleError("Windows game launch requires Windows")
    identity = validate_windows_game_executable(executable)
    existing = windows_breach_process_ids()
    if existing:
        raise WindowsGameLifecycleError(
            f"refusing to launch while Breach.exe is already running: {existing}"
        )
    launched_at = datetime.now(timezone.utc).isoformat()
    try:
        process = subprocess.Popen(
            [identity["path"]],
            cwd=str(Path(identity["path"]).parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        raise WindowsGameLifecycleError(f"could not launch Breach.exe: {exc}") from exc
    if type(process.pid) is not int or process.pid <= 0:
        raise WindowsGameLifecycleError("Breach.exe launch returned an invalid PID")
    return {
        "requested_at": launched_at,
        "launcher_pid": process.pid,
        "executable_path": identity["path"],
        "executable_size": identity["size"],
        "executable_sha256": identity["sha256"],
    }


def wait_for_exact_windows_game_process(
    executable: Path,
    *,
    expected_pid: int,
    timeout: float = 30.0,
    poll_interval: float = 0.10,
) -> dict[str, Any]:
    """Wait for the launched PID to become the sole exact Breach.exe process."""
    if os.name != "nt":
        raise WindowsGameLifecycleError("Windows process wait requires Windows")
    if type(expected_pid) is not int or expected_pid <= 0:
        raise WindowsGameLifecycleError("expected Breach.exe PID is invalid")
    validate_windows_game_executable(executable)
    deadline = time.monotonic() + max(0.1, float(timeout))
    interval = max(0.02, float(poll_interval))
    while time.monotonic() < deadline:
        pids = windows_breach_process_ids()
        if not pids:
            time.sleep(interval)
            continue
        if pids != [expected_pid]:
            raise WindowsGameLifecycleError(
                f"launched Breach.exe process set differs: {pids}"
            )
        try:
            identity = capture_windows_game_process_identity(executable)
        except GameProcessIdentityError as exc:
            if "found 0" in str(exc):
                time.sleep(interval)
                continue
            raise WindowsGameLifecycleError(str(exc)) from exc
        if identity.get("pid") != expected_pid:
            raise WindowsGameLifecycleError("captured Breach.exe PID differs")
        return identity
    raise WindowsGameLifecycleError(
        f"Breach.exe process did not appear within {float(timeout):.1f}s"
    )


def _windows_game_window_handles(pid: int) -> list[int]:
    if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
        raise WindowsGameLifecycleError("Windows window enumeration requires Windows")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetWindowTextW.restype = ctypes.c_int
    handles: list[int] = []

    def visit(hwnd: int, _lparam: int) -> bool:
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        if "Into the Breach" in title.value:
            handles.append(int(hwnd))
        return True

    callback = callback_type(visit)
    if not user32.EnumWindows(callback, 0):
        raise WindowsGameLifecycleError("could not enumerate Breach.exe windows")
    return sorted(set(handles))


def _post_close_message(hwnd: int) -> None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.PostMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.PostMessageW.restype = wintypes.BOOL
    if not user32.PostMessageW(hwnd, 0x0010, 0, 0):
        raise WindowsGameLifecycleError(
            f"WM_CLOSE was rejected for Breach.exe window {hwnd}"
        )


def gracefully_close_exact_windows_game(
    executable: Path,
    process_identity: Mapping[str, Any],
    *,
    timeout: float = 30.0,
    poll_interval: float = 0.10,
) -> dict[str, Any]:
    """Post WM_CLOSE to the exact captured process and require clean exit."""
    if os.name != "nt":
        raise WindowsGameLifecycleError("Windows game close requires Windows")
    current = capture_windows_game_process_identity(executable)
    expected_key = (
        process_identity.get("pid"),
        process_identity.get("creation_filetime"),
    )
    current_key = (current.get("pid"), current.get("creation_filetime"))
    if expected_key != current_key:
        raise WindowsGameLifecycleError(
            "refusing to close a different Breach.exe process identity"
        )
    pid = int(current["pid"])
    handles = _windows_game_window_handles(pid)
    if not handles:
        raise WindowsGameLifecycleError(
            "exact Breach.exe process has no visible Into the Breach window"
        )
    requested_at = datetime.now(timezone.utc).isoformat()
    for hwnd in handles:
        _post_close_message(hwnd)
    deadline = time.monotonic() + max(0.1, float(timeout))
    interval = max(0.02, float(poll_interval))
    while time.monotonic() < deadline:
        pids = windows_breach_process_ids()
        if pid not in pids:
            if pids:
                raise WindowsGameLifecycleError(
                    f"a different Breach.exe appeared during close: {pids}"
                )
            return {
                "method": "WM_CLOSE",
                "requested_at": requested_at,
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "pid": pid,
                "creation_filetime": current["creation_filetime"],
                "window_handles": handles,
                "exited": True,
                "forced_termination": False,
            }
        time.sleep(interval)
    raise WindowsGameLifecycleError(
        f"Breach.exe did not exit after WM_CLOSE within {float(timeout):.1f}s"
    )
