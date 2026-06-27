"""Auto-detect the 8x8 isometric grid position in any screenshot.

Uses the game window bounds (via Quartz) and a fixed relationship between
the window content area and the grid origin. The grid position within the
game window is constant for a given window size and board scale.

This replaces hardcoded screen coordinates with dynamic detection.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from src.capture.grid import GridConfig


@dataclass
class WindowInfo:
    """Game window position and size in screen logical coordinates."""
    x: int
    y: int
    width: int
    height: int
    window_id: int = 0


def find_game_window() -> WindowInfo | None:
    """Find the Into the Breach window."""
    if os.name == "nt":
        return _find_game_window_windows()

    try:
        import Quartz
        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID
        )
        for w in windows:
            name = w.get('kCGWindowOwnerName', '')
            if 'Breach' in name:
                bounds = w.get('kCGWindowBounds', {})
                return WindowInfo(
                    x=int(bounds.get('X', 0)),
                    y=int(bounds.get('Y', 0)),
                    width=int(bounds.get('Width', 0)),
                    height=int(bounds.get('Height', 0)),
                    window_id=int(w.get('kCGWindowNumber', 0)),
                )
    except ImportError:
        pass

    # Fallback: AppleScript
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
                return WindowInfo(x=x, y=y, width=w, height=h)
    except (subprocess.TimeoutExpired, ValueError):
        pass

    return None


def _find_game_window_windows() -> WindowInfo | None:
    """Find the Into the Breach window via the Windows user32 API."""
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None

    user32 = ctypes.windll.user32
    matches: list[WindowInfo] = []
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
        matches.append(WindowInfo(
            x=int(rect.left),
            y=int(rect.top),
            width=int(rect.right - rect.left),
            height=int(rect.bottom - rect.top),
            window_id=int(hwnd),
        ))
        return True

    user32.EnumWindows(enum_proc_type(enum_proc), 0)
    return matches[0] if matches else None


# Grid position relative to the game window content area.
# These are fractional positions within the window, independent of
# window position on screen. Calibrated for window size 1280x748
# at Max Board Scale 5x.
#
# The grid origin (tile 1,A center) is at:
#   x = window_left + GRID_ORIGIN_X_FRAC * window_width
#   y = window_top + GRID_ORIGIN_Y_FRAC * window_height
#
# Tile step sizes scale proportionally with window size.

# Reference calibration: window 1280x748.
_REF_W = 1280
_REF_H = 748
# Refit on Windows during a live Mist Eaters run (2026-06-27) after Control
# Shot visible-click execution missed by a full board row/column. The hover-
# verified points were bridge (1,4) D7 at window-local (511,326), bridge
# (1,3) E7 at (568,285), and bridge (6,4) D2 at (725,530).
#
# These constants are bridge-coordinate direct: row step is save_x, col step is
# save_y. Do not convert bridge coords to visual row/letter before using them.
_REF_ORIGIN_X = 687.60
_REF_ORIGIN_Y = 119.45
# Tile step per save_x increment: screen down-right.
_REF_AX = 42.27
_REF_AY = 40.21
# Tile step per save_y increment: screen down-left.
_REF_BX = -56.30
_REF_BY = 40.41


def grid_from_window(win: WindowInfo) -> GridConfig:
    """Create a GridConfig calibrated to the current window position.

    The grid uses a non-standard isometric projection where the two
    axes have different angles. The transform was solved empirically
    from 3 reference points.

    Args:
        win: Current game window bounds.

    Returns:
        GridConfig with screen-logical coordinates for the current layout.
    """
    # Scale factor relative to reference window size
    sx = win.width / _REF_W
    sy = win.height / _REF_H

    # Grid origin in screen logical coordinates
    origin_x = win.x + _REF_ORIGIN_X * sx
    origin_y = win.y + _REF_ORIGIN_Y * sy

    # The isometric axes: save_x step and save_y step
    # These are NOT symmetric — the game uses a non-standard projection
    return GridConfig(
        origin_x=origin_x,
        origin_y=origin_y,
        row_dx=_REF_AX * sx,   # save_x step (upper-left direction)
        row_dy=_REF_AY * sy,
        col_dx=_REF_BX * sx,   # save_y step (upper-right direction)
        col_dy=_REF_BY * sy,
        tile_half_width=abs(_REF_AX) * sx,
        tile_half_height=abs(_REF_AY) * sy,
    )


def detect_grid() -> GridConfig | None:
    """Auto-detect the grid configuration from the current game window.

    Returns:
        GridConfig if the game window is found, else None.
    """
    win = find_game_window()
    if win is None:
        return None
    return grid_from_window(win)


if __name__ == "__main__":
    win = find_game_window()
    if win is None:
        print("Game window not found")
    else:
        print(f"Window: x={win.x}, y={win.y}, w={win.width}, h={win.height}")
        grid = grid_from_window(win)
        print(f"Grid origin (1,A): ({grid.origin_x:.1f}, {grid.origin_y:.1f})")
        print(f"Tile half-width: {grid.tile_half_width:.1f}")
        print(f"Tile half-height: {grid.tile_half_height:.1f}")
        print()
        # Print corners
        for name, r, c in [("1A", 1, 1), ("8A", 8, 1), ("1H", 1, 8), ("8H", 8, 8)]:
            x, y = grid.tile_to_pixel(r, c)
            print(f"  {name}: ({x:.1f}, {y:.1f})")
