"""Small macOS click helpers for trusted UI buttons.

This module is intentionally narrow: it clicks already-calibrated screen
coordinates such as the End Turn button. Combat tile clicks still flow through
the bridge or Computer Use planners.
"""

from __future__ import annotations

import subprocess
import time


def click_screen_point(
    x: int,
    y: int,
    *,
    description: str = "",
    app_name: str = "Into the Breach",
    dry_run: bool = False,
    settle_seconds: float = 0.15,
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
        return {
            "status": "ERROR",
            "error": f"osascript timed out: {exc}",
            "x": x,
            "y": y,
            "description": description,
        }

    if proc.returncode != 0:
        return {
            "status": "ERROR",
            "error": proc.stderr.strip() or proc.stdout.strip() or "click failed",
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
    }
