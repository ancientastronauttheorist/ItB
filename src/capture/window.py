"""Game window detection and screenshot capture for Into the Breach."""

from __future__ import annotations

import os
import json
import subprocess
import time
from pathlib import Path

BUNDLE_ID = "subset.Into-the-Breach"
APP_PATH = (
    "/Users/aircow/Library/Application Support/Steam/steamapps/common/"
    "Into the Breach/Into the Breach.app"
)


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
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) == 4:
                x, y, w, h = [int(p) for p in parts]
                return {"x": x, "y": y, "width": w, "height": h}
    except (subprocess.TimeoutExpired, ValueError):
        pass
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
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return False
    if result.returncode != 0:
        return False
    return result.stdout.strip() == "Into the Breach"


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

    if bounds:
        region = (
            f"{bounds['x']},{bounds['y']},"
            f"{bounds['width']},{bounds['height']}"
        )
        subprocess.run(
            ["screencapture", "-x", "-R", region, str(output_path)],
            timeout=10,
        )
    else:
        # Fallback: capture entire screen if accessibility window bounds fail.
        subprocess.run(["screencapture", "-x", str(output_path)], timeout=10)

    return output_path


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
    matches: list[dict] = []

    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

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
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        matches.append({
            "hwnd": int(hwnd),
            "title": title.value,
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
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return False
    title = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, title, length + 1)
    return "Into the Breach" in title.value


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
