"""Small macOS click helpers for trusted UI buttons.

This module is intentionally narrow: it clicks already-calibrated screen
coordinates such as the End Turn button. Combat tile clicks still flow through
the bridge or Computer Use planners.
"""

from __future__ import annotations

import subprocess
import time


def _pyautogui_click(x: int, y: int, *, hold_seconds: float = 0.3) -> dict:
    """Click a global screen point with PyAutoGUI, if available."""
    try:
        import pyautogui
    except Exception as exc:
        return {"status": "ERROR", "error": f"pyautogui unavailable: {exc}"}
    try:
        pyautogui.moveTo(int(x), int(y), duration=0.05)
        pyautogui.mouseDown(int(x), int(y))
        time.sleep(max(0.0, hold_seconds))
        pyautogui.mouseUp(int(x), int(y))
    except Exception as exc:
        return {"status": "ERROR", "error": f"pyautogui click failed: {exc}"}
    return {"status": "OK", "hold_seconds": hold_seconds}


def _applescript_click(
    x: int,
    y: int,
    *,
    app_name: str,
) -> dict:
    """Click a global screen point via System Events."""
    script = f'''
    tell application "{app_name}" to activate
    delay 0.05
    tell application "System Events"
        click at {{{x}, {y}}}
    end tell
    '''
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired as exc:
        return {"status": "ERROR", "error": f"osascript timed out: {exc}"}

    if proc.returncode != 0:
        return {
            "status": "ERROR",
            "error": proc.stderr.strip() or proc.stdout.strip() or "click failed",
        }
    return {"status": "OK"}


def _get_window_bounds(app_name: str) -> dict | None:
    """Return the front window bounds for ``app_name`` via System Events."""
    script = f'''
    tell application "{app_name}" to activate
    delay 0.05
    tell application "System Events"
        tell process "{app_name}"
            set frontmost to true
            set winPos to position of window 1
            set winSize to size of window 1
            return (item 1 of winPos as text) & "," & (item 2 of winPos as text) & "," & (item 1 of winSize as text) & "," & (item 2 of winSize as text)
        end tell
    end tell
    '''
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    try:
        x, y, width, height = [
            int(part.strip()) for part in proc.stdout.strip().split(",", 3)
        ]
    except ValueError:
        return None
    return {"x": x, "y": y, "width": width, "height": height}


def click_screen_point(
    x: int,
    y: int,
    *,
    description: str = "",
    app_name: str = "Into the Breach",
    dry_run: bool = False,
    settle_seconds: float = 0.15,
    hold_seconds: float = 0.3,
) -> dict:
    """Activate the game and click a screen-coordinate point via AppleScript."""
    x = int(x)
    y = int(y)
    if dry_run:
        return {
            "status": "DRY_RUN",
            "x": x,
            "y": y,
            "description": description,
        }

    click_result = _pyautogui_click(x, y, hold_seconds=hold_seconds)
    backend = "pyautogui"
    fallback_error = None
    if click_result.get("status") != "OK":
        fallback_error = click_result.get("error")
        click_result = _applescript_click(x, y, app_name=app_name)
        backend = "applescript"

    if click_result.get("status") != "OK":
        return {
            "status": "ERROR",
            "error": click_result.get("error", "click failed"),
            "pyautogui_error": fallback_error,
            "x": x,
            "y": y,
            "description": description,
        }

    if settle_seconds > 0:
        time.sleep(settle_seconds)

    return {
        "status": "OK",
        "x": x,
        "y": y,
        "description": description,
        "backend": backend,
        "hold_seconds": click_result.get("hold_seconds"),
    }


def click_window_point(
    x: int,
    y: int,
    *,
    description: str = "",
    app_name: str = "Into the Breach",
    dry_run: bool = False,
    settle_seconds: float = 0.15,
    hold_seconds: float = 0.3,
) -> dict:
    """Click a point relative to the game window's top-left corner."""
    x = int(x)
    y = int(y)
    if dry_run:
        return {
            "status": "DRY_RUN",
            "window_x": x,
            "window_y": y,
            "description": description,
        }

    bounds = _get_window_bounds(app_name)
    if bounds is None:
        return {
            "status": "ERROR",
            "error": "could not read app window bounds",
            "window_x": x,
            "window_y": y,
            "description": description,
        }

    screen_x = int(bounds["x"] + x)
    screen_y = int(bounds["y"] + y)
    result = click_screen_point(
        screen_x,
        screen_y,
        description=description,
        app_name=app_name,
        dry_run=False,
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )
    result["window_x"] = x
    result["window_y"] = y
    result["window_bounds"] = bounds
    return result
