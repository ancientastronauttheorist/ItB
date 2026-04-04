"""Game window detection and screenshot capture for Into the Breach on macOS."""

import subprocess
import json
import time
from pathlib import Path

BUNDLE_ID = "subset.Into-the-Breach"
APP_PATH = (
    "/Users/aircow/Library/Application Support/Steam/steamapps/common/"
    "Into the Breach/Into the Breach.app"
)


def is_game_running() -> bool:
    """Check if Into the Breach is currently running."""
    result = subprocess.run(
        ["pgrep", "-f", "Into the Breach"],
        capture_output=True, text=True
    )
    return result.returncode == 0


def launch_game() -> None:
    """Launch Into the Breach via its app bundle."""
    subprocess.run(["open", APP_PATH])


def get_window_bounds() -> dict | None:
    """Get the game window position and size via AppleScript.

    Returns:
        Dict with 'x', 'y', 'width', 'height' in screen logical coordinates,
        or None if the window can't be found.
    """
    script = '''
    tell application "System Events"
        tell process "Into the Breach"
            set winPos to position of window 1
            set winSize to size of window 1
            return (item 1 of winPos) & "," & (item 2 of winPos) & "," & (item 1 of winSize) & "," & (item 2 of winSize)
        end tell
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            if len(parts) == 4:
                x, y, w, h = [int(p) for p in parts]
                return {"x": x, "y": y, "width": w, "height": h}
    except (subprocess.TimeoutExpired, ValueError):
        pass
    return None


def take_screenshot(output_path: str | Path) -> Path:
    """Capture a screenshot of the game window using screencapture.

    Args:
        output_path: Where to save the PNG screenshot.

    Returns:
        Path to the saved screenshot.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use screencapture with window selection by title
    # -l flag captures a specific window by ID
    # First, get window ID
    script = '''
    tell application "System Events"
        tell process "Into the Breach"
            return id of window 1
        end tell
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=5
    )

    if result.returncode == 0:
        window_id = result.stdout.strip()
        subprocess.run(
            ["screencapture", "-l", window_id, "-x", str(output_path)],
            timeout=10
        )
    else:
        # Fallback: capture entire screen
        subprocess.run(
            ["screencapture", "-x", str(output_path)],
            timeout=10
        )

    return output_path


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
