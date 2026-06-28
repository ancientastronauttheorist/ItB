"""Game window detection and screenshot capture for Into the Breach."""

from __future__ import annotations

import os
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

BUNDLE_ID = "subset.Into-the-Breach"
APP_PATH = (
    "/Users/aircow/Library/Application Support/Steam/steamapps/common/"
    "Into the Breach/Into the Breach.app"
)
_LAST_WINDOW_BOUNDS: dict | None = None
_LAST_ACTIVATE_AT: float = 0.0
_DEFAULT_MAC_WINDOW_BOUNDS = {"x": 215, "y": 32, "width": 1280, "height": 748}


def _run_screencapture(args: list[str], timeout: float) -> None:
    """Run macOS screencapture with a hard deadline.

    Python's subprocess timeout can occasionally sit in the wait path when
    macOS screen capture is blocked behind a system prompt. Polling and killing
    the process group keeps Lightning runs from stalling while safely paused.
    """
    process = subprocess.Popen(
        ["screencapture", *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + max(0.1, timeout)
    while True:
        returncode = process.poll()
        if returncode is not None:
            if returncode != 0:
                raise RuntimeError(f"screencapture failed with code {returncode}")
            return
        if time.monotonic() >= deadline:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except Exception:
                try:
                    process.terminate()
                except Exception:
                    pass
            try:
                process.wait(timeout=0.2)
            except Exception:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
                try:
                    process.wait(timeout=0.2)
                except Exception:
                    pass
            raise RuntimeError(f"screencapture timed out after {timeout:.1f}s")
        time.sleep(0.02)


def _run_command_hard_timeout(
    command: list[str],
    timeout: float,
    *,
    text: bool = False,
) -> subprocess.CompletedProcess:
    """Run a short macOS helper command with a process-group deadline."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        start_new_session=True,
    )
    deadline = time.monotonic() + max(0.1, timeout)
    while True:
        returncode = process.poll()
        if returncode is not None:
            stdout, stderr = process.communicate()
            return subprocess.CompletedProcess(
                command,
                returncode,
                stdout=stdout,
                stderr=stderr,
            )
        if time.monotonic() >= deadline:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except Exception:
                try:
                    process.terminate()
                except Exception:
                    pass
            try:
                stdout, stderr = process.communicate(timeout=0.2)
            except Exception:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
                try:
                    stdout, stderr = process.communicate(timeout=0.2)
                except Exception:
                    stdout, stderr = ("", "") if text else (b"", b"")
            raise subprocess.TimeoutExpired(
                command,
                timeout,
                output=stdout,
                stderr=stderr,
            )
        time.sleep(0.02)


def _fallback_window_bounds() -> dict | None:
    raw = os.environ.get("ITB_WINDOW_BOUNDS_FALLBACK", "").strip()
    if raw:
        try:
            x, y, width, height = [int(part.strip()) for part in raw.split(",", 3)]
        except ValueError:
            return None
        return {"x": x, "y": y, "width": width, "height": height}
    if os.environ.get("ITB_DISABLE_DEFAULT_WINDOW_BOUNDS", "0") not in {"1", "true", "TRUE"}:
        return dict(_DEFAULT_MAC_WINDOW_BOUNDS)
    return None


def is_game_running() -> bool:
    """Check if Into the Breach is currently running."""
    if os.name == "nt":
        return bool(_windows_breach_windows())

    result = subprocess.run(
        ["pgrep", "-f", "Into the Breach"],
        capture_output=True, text=True
    )
    return result.returncode == 0


def launch_game() -> None:
    """Launch Into the Breach via its app bundle."""
    subprocess.run(["open", APP_PATH])


def get_window_bounds() -> dict | None:
    """Get the game window position and size.

    Returns:
        Dict with 'x', 'y', 'width', 'height' in screen logical coordinates,
        or None if the window can't be found.
    """
    if os.name == "nt":
        return _windows_window_bounds()

    global _LAST_WINDOW_BOUNDS
    fast_cached = os.environ.get("ITB_FAST_CACHED_WINDOW_BOUNDS", "1")
    if fast_cached not in {"0", "false", "FALSE"}:
        if _LAST_WINDOW_BOUNDS is not None:
            return dict(_LAST_WINDOW_BOUNDS)
        fallback = _fallback_window_bounds()
        if fallback is not None:
            _LAST_WINDOW_BOUNDS = dict(fallback)
            return fallback

    script = '''
    tell application "System Events"
        tell process "Into the Breach"
            set winPos to position of window 1
            set winSize to size of window 1
            return (item 1 of winPos as text) & "," & (item 2 of winPos as text) & "," & (item 1 of winSize as text) & "," & (item 2 of winSize as text)
        end tell
    end tell
    '''
    try:
        timeout = float(os.environ.get("ITB_WINDOW_BOUNDS_TIMEOUT", "1.5"))
    except ValueError:
        timeout = 1.5
    try:
        result = _run_command_hard_timeout(
            ["osascript", "-e", script],
            max(0.25, timeout),
            text=True,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) == 4:
                x, y, w, h = [int(p) for p in parts]
                _LAST_WINDOW_BOUNDS = {"x": x, "y": y, "width": w, "height": h}
                return dict(_LAST_WINDOW_BOUNDS)
    except (subprocess.TimeoutExpired, ValueError):
        if _LAST_WINDOW_BOUNDS is not None:
            return dict(_LAST_WINDOW_BOUNDS)
        fallback = _fallback_window_bounds()
        if fallback is not None:
            _LAST_WINDOW_BOUNDS = dict(fallback)
            return fallback
    return None


def is_game_frontmost() -> bool:
    """Return true when Into the Breach is the current frontmost app/window."""
    if os.name == "nt":
        return _windows_game_is_frontmost()

    script = '''
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
        return frontApp
    end tell
    '''
    try:
        timeout = float(os.environ.get("ITB_FRONTMOST_TIMEOUT", "2.0"))
    except ValueError:
        timeout = 2.0
    try:
        result = _run_command_hard_timeout(
            ["osascript", "-e", script],
            max(0.1, timeout),
            text=True,
        )
    except subprocess.TimeoutExpired:
        return False
    if result.returncode != 0:
        return False
    return result.stdout.strip() == "Into the Breach"


def activate_game_window() -> None:
    """Best-effort raise of the game window before screen-region capture."""
    if os.name == "nt":
        return
    global _LAST_ACTIVATE_AT
    now = time.monotonic()
    try:
        min_interval = float(os.environ.get("ITB_WINDOW_ACTIVATE_MIN_INTERVAL", "5"))
    except ValueError:
        min_interval = 5.0
    if now - _LAST_ACTIVATE_AT < max(0.0, min_interval):
        return
    try:
        timeout = float(os.environ.get("ITB_WINDOW_ACTIVATE_TIMEOUT", "0.75"))
    except ValueError:
        timeout = 0.75
    try:
        _run_command_hard_timeout(
            ["osascript", "-e", 'tell application "Into the Breach" to activate'],
            max(0.1, timeout),
            text=True,
        )
        _LAST_ACTIVATE_AT = time.monotonic()
        time.sleep(0.03)
    except Exception:
        pass


def take_screenshot(
    output_path: str | Path,
    *,
    bounds: dict | None = None,
) -> Path:
    """Capture a screenshot of the game window.

    Args:
        output_path: Where to save the PNG screenshot.
        bounds: Optional window bounds already proven by the caller. When
            provided, the screenshot uses these bounds instead of re-querying.

    Returns:
        Path to the saved screenshot.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if bounds is None:
        bounds = get_window_bounds()
    if os.name == "nt":
        from PIL import ImageGrab

        if bounds:
            bbox = (
                bounds["x"],
                bounds["y"],
                bounds["x"] + bounds["width"],
                bounds["y"] + bounds["height"],
            )
            ImageGrab.grab(bbox=bbox).save(output_path)
        else:
            ImageGrab.grab().save(output_path)
        return output_path

    backend = os.environ.get("ITB_SCREENSHOT_BACKEND", "quartz").strip().lower()
    if backend in {"", "quartz", "auto"}:
        try:
            _take_quartz_screenshot_guarded(output_path, bounds=bounds)
            return output_path
        except Exception:
            if backend != "auto" or os.environ.get(
                "ITB_SCREENSHOT_ALLOW_SCREENCAPTURE_FALLBACK",
                "0",
            ) not in {"1", "true", "TRUE"}:
                raise

    try:
        timeout = float(os.environ.get("ITB_SCREENSHOT_TIMEOUT", "4.0"))
    except ValueError:
        timeout = 4.0
    timeout = max(0.5, timeout)

    if bounds:
        activate_game_window()
        region = (
            f"{bounds['x']},{bounds['y']},"
            f"{bounds['width']},{bounds['height']}"
        )
        _run_screencapture(["-x", "-R", region, str(output_path)], timeout)
    else:
        # Fallback: capture entire screen if accessibility window bounds fail.
        _run_screencapture(["-x", str(output_path)], timeout)

    return output_path


def take_fullscreen_screenshot(output_path: str | Path) -> Path:
    """Capture the full display without querying the game window first."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        from PIL import ImageGrab

        ImageGrab.grab().save(output_path)
        return output_path

    backend = os.environ.get("ITB_SCREENSHOT_BACKEND", "quartz").strip().lower()
    if backend in {"", "quartz", "auto"}:
        try:
            _take_quartz_screenshot_guarded(output_path, bounds=None)
            return output_path
        except Exception:
            if backend != "auto" or os.environ.get(
                "ITB_SCREENSHOT_ALLOW_SCREENCAPTURE_FALLBACK",
                "0",
            ) not in {"1", "true", "TRUE"}:
                raise

    try:
        timeout = float(os.environ.get("ITB_SCREENSHOT_TIMEOUT", "4.0"))
    except ValueError:
        timeout = 4.0
    _run_screencapture(["-x", str(output_path)], max(0.5, timeout))
    return output_path


def _take_quartz_screenshot_guarded(
    output_path: Path,
    *,
    bounds: dict | None = None,
) -> None:
    """Run Quartz capture with a hard deadline on macOS."""
    mode = os.environ.get("ITB_QUARTZ_CAPTURE_MODE", "subprocess").strip().lower()
    if mode in {"inprocess", "inline", "direct"}:
        _take_quartz_screenshot(output_path, bounds=bounds)
        return
    try:
        timeout = float(os.environ.get("ITB_QUARTZ_CAPTURE_TIMEOUT", "3.0"))
    except ValueError:
        timeout = 3.0
    timeout = max(0.25, timeout)
    encoded_bounds = json.dumps(bounds) if bounds else ""
    code = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "from src.capture.window import _take_quartz_screenshot\n"
        "bounds = json.loads(sys.argv[2]) if sys.argv[2] else None\n"
        "_take_quartz_screenshot(Path(sys.argv[1]), bounds=bounds)\n"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code, str(output_path), encoded_bounds],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Quartz screenshot timed out after {timeout:.1f}s") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if detail:
            raise RuntimeError(f"Quartz screenshot failed: {detail}")
        raise RuntimeError(f"Quartz screenshot failed with code {proc.returncode}")


def _take_quartz_screenshot(output_path: Path, *, bounds: dict | None = None) -> None:
    """Capture the screen/window using Quartz without spawning screencapture."""
    try:
        import Quartz
        from PIL import Image
    except Exception as exc:
        raise RuntimeError(f"Quartz screenshot backend unavailable: {exc}") from exc

    if bounds:
        rect = Quartz.CGRectMake(
            int(bounds["x"]),
            int(bounds["y"]),
            int(bounds["width"]),
            int(bounds["height"]),
        )
    else:
        rect = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
    image_ref = Quartz.CGWindowListCreateImage(
        rect,
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
        Quartz.kCGWindowImageDefault,
    )
    if image_ref is None:
        raise RuntimeError("Quartz screenshot returned no image")
    width = int(Quartz.CGImageGetWidth(image_ref))
    height = int(Quartz.CGImageGetHeight(image_ref))
    bytes_per_row = int(Quartz.CGImageGetBytesPerRow(image_ref))
    provider = Quartz.CGImageGetDataProvider(image_ref)
    data = Quartz.CGDataProviderCopyData(provider)
    if not data or width <= 0 or height <= 0:
        raise RuntimeError("Quartz screenshot returned empty image data")
    pil = Image.frombuffer(
        "RGBA",
        (width, height),
        bytes(data),
        "raw",
        "BGRA",
        bytes_per_row,
        1,
    ).convert("RGB")
    pil.save(output_path)


def _windows_breach_windows() -> list[dict]:
    """Return visible Windows HWND bounds for Into the Breach."""
    if os.name != "nt":
        return []
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return []

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    matches: list[dict] = []

    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    def process_path_for(hwnd) -> str:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        handle = kernel32.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(1024)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return buffer.value
            return ""
        finally:
            kernel32.CloseHandle(handle)

    def enum_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        if "Into the Breach" not in title.value:
            return True
        process_path = process_path_for(hwnd)
        process_name = Path(process_path).name.lower()
        if process_name != "breach.exe":
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        matches.append({
            "hwnd": int(hwnd),
            "title": title.value,
            "process_path": process_path,
            "x": int(rect.left),
            "y": int(rect.top),
            "width": int(rect.right - rect.left),
            "height": int(rect.bottom - rect.top),
        })
        return True

    user32.EnumWindows(enum_proc_type(enum_proc), 0)
    return matches


def _windows_window_bounds() -> dict | None:
    windows = _windows_breach_windows()
    if not windows:
        return None
    first = windows[0]
    return {
        "x": first["x"],
        "y": first["y"],
        "width": first["width"],
        "height": first["height"],
    }


def _windows_game_is_frontmost() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    return any(win.get("hwnd") == int(hwnd) for win in _windows_breach_windows())


if __name__ == "__main__":
    if is_game_running():
        print("Game is running.")
        bounds = get_window_bounds()
        if bounds:
            print(f"Window bounds: {bounds}")
        else:
            print("Could not get window bounds.")
    else:
        print("Game is not running.")
