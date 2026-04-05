"""Execute solver actions by clicking on the game.

Translates MechAction sequences into mouse clicks for the MCP
computer-use tool. Supports per-mech execution with verification
gaps between each mech (Claude-as-the-loop pattern).

Mech selection uses portrait clicks (not Tab) for reliability when
executing non-consecutively with verify steps between mechs.

Coordinate systems:
  - Save file coordinates: (0-7, 0-7) — from saveData.lua
  - MCP screenshot coordinates: = Quartz logical screen coordinates
  - grid_to_mcp() auto-detects the game window via Quartz and computes
    the correct MCP coordinates dynamically. No hardcoded offsets.
"""

from __future__ import annotations

from src.solver.solver import MechAction, Solution
from src.model.board import Board
from src.capture.detect_grid import detect_grid, find_game_window, grid_from_window


# --- Dynamic Coordinate Detection ---

# Cached grid config and window info — invalidated by recalibrate()
_cached_grid = None
_cached_window = None


def _get_grid():
    """Get cached GridConfig, detecting game window if needed."""
    global _cached_grid
    if _cached_grid is None:
        _cached_grid = detect_grid()
        if _cached_grid is None:
            raise RuntimeError(
                "Game window not found — is Into the Breach running and visible?"
            )
    return _cached_grid


def _get_window():
    """Get cached WindowInfo, detecting game window if needed."""
    global _cached_window
    if _cached_window is None:
        _cached_window = find_game_window()
        if _cached_window is None:
            raise RuntimeError(
                "Game window not found — is Into the Breach running and visible?"
            )
    return _cached_window


def grid_to_mcp(save_x: int, save_y: int) -> tuple[int, int]:
    """Convert save file coordinates to MCP screenshot coordinates.

    Uses the game's isometric projection formula:
      mcp_x = OX + STEP_X * (save_x - save_y)
      mcp_y = OY + STEP_Y * (save_x + save_y)

    The origin (OX, OY) is computed from the game window position
    (auto-detected via Quartz). STEP_X and STEP_Y are the half-tile
    dimensions in MCP pixel space, derived from the window size.

    Verified against 4 known tile positions (Coal Plant, 2 Scorpions,
    Volatile Vek) — all matched exactly.
    """
    win = _get_window()

    # The game's internal isometric formula (from grid_reference.json):
    #   game_x = 690 + (col - row) * 50      (at 1280x748 window)
    #   game_y = 660 - (col + row - 2) * 27.5
    # where row = save_x + 1, col = save_y + 1
    #
    # Simplifies to:
    #   game_x = 690 + (save_y - save_x) * 50
    #   game_y = 660 - (save_x + save_y) * 27.5
    #
    # The MCP coordinate is: win_pos + game_coord * (mcp_window_size / game_size)
    # But empirically, the scale factor from game coords to MCP coords
    # was measured as: step_x = 42 pixels per (save_y - save_x) unit
    #                  step_y = 25 pixels per (save_x + save_y) unit
    #
    # These scale factors are proportional to window size:
    #   step_x = 42 * (win.width / 1280)
    #   step_y = 25 * (win.height / 748)
    #
    # The origin (where save_x == save_y, sum == 0, i.e. tile 0,0) was
    # measured at MCP x=556 with window at x=0, width=1280. That's
    # game_x=690 scaled: 556 = win.x + 690 * (win.width / 1280) * scale_factor
    # Empirically: OX = win.x + 556 (at width 1280)
    #              OY = win.y + 138 (at height 748)

    sx = win.width / 1280.0
    sy = win.height / 748.0

    # Origin in MCP coords (tile 0,0 center, adjusted for window position)
    ox = win.x + 556 * sx
    oy = win.y + 138 * sy

    # Isometric step sizes in MCP pixels
    step_x = 42.0 * sx   # per (save_x - save_y) unit
    step_y = 25.0 * sy   # per (save_x + save_y) unit

    px = ox + step_x * (save_x - save_y)
    py = oy + step_y * (save_x + save_y)

    return (int(round(px)), int(round(py)))


def recalibrate():
    """Force re-detection of game window position.

    Call this when the window may have moved (e.g., at the start of each turn).
    The next grid_to_mcp() call will re-detect the window.
    """
    global _cached_grid, _cached_window
    _cached_grid = None
    _cached_window = None


# --- Window-Relative UI Positions ---

# These are pixel offsets from the game window's top-left corner.
# They're constant within the game regardless of window position.
# Calibrated for 1280x748 window at Max Board Scale 5x.
_UI_PORTRAIT_X = 50
_UI_PORTRAIT_Y = [135, 195, 245]  # Top, middle, bottom mech portraits
_UI_END_TURN = (95, 78)
_UI_BOARD_CENTER = (500, 350)


def _portrait_pos(index: int) -> tuple[int, int]:
    """Get MCP coordinates for a mech portrait (0, 1, or 2)."""
    win = _get_window()
    return (win.x + _UI_PORTRAIT_X, win.y + _UI_PORTRAIT_Y[index])


def _end_turn_pos() -> tuple[int, int]:
    """Get MCP coordinates for the End Turn button."""
    win = _get_window()
    return (win.x + _UI_END_TURN[0], win.y + _UI_END_TURN[1])


def _board_center() -> tuple[int, int]:
    """Get MCP coordinates for the board center (for dismissing popups)."""
    win = _get_window()
    return (win.x + _UI_BOARD_CENTER[0], win.y + _UI_BOARD_CENTER[1])


# --- Mech Portrait Mapping ---

def get_mech_portraits(board: Board) -> dict[str, int]:
    """Build mech_type → portrait_index mapping from board state.

    Mechs appear in portrait order (top to bottom) matching their
    order in the save file's pawn list (by UID).
    """
    mechs = sorted(
        [u for u in board.units if u.is_mech and u.hp > 0],
        key=lambda u: u.uid
    )
    return {m.type: i for i, m in enumerate(mechs)}


def _get_weapon_key(action: MechAction, board: Board) -> str:
    """Return '1' for primary weapon, '2' for secondary."""
    if not action.weapon:
        return "1"

    mech = None
    for u in board.units:
        if u.uid == action.mech_uid:
            mech = u
            break

    if mech is None:
        return "1"

    if mech.weapon2 and action.weapon == mech.weapon2:
        return "2"
    return "1"


# --- Per-Mech Click Planning ---

def plan_single_mech(action: MechAction, portrait_index: int,
                     board: Board = None) -> list[dict]:
    """Plan clicks for ONE mech action.

    Uses portrait clicks for reliable mech selection (not Tab,
    which is unreliable with verify gaps between executions).

    Portrait click shows a pilot popup — we dismiss it by clicking
    the board, then re-click the portrait to select the mech.
    """
    clicks = []

    # Get UI positions (window-relative, auto-detected)
    px, py = _portrait_pos(portrait_index)
    bx, by = _board_center()

    # Step 1: Click portrait to select mech
    clicks.append({
        "type": "click", "x": px, "y": py,
        "description": f"Click portrait to select {action.mech_type}",
    })
    clicks.append({"type": "wait", "duration": 0.3,
                    "description": "Wait for portrait response"})

    # Step 2: Click board center to dismiss pilot popup
    clicks.append({
        "type": "click", "x": bx, "y": by,
        "description": "Dismiss pilot popup",
    })
    clicks.append({"type": "wait", "duration": 0.3,
                    "description": "Wait for popup dismiss"})

    # Step 3: Re-click portrait (now selects mech properly)
    clicks.append({
        "type": "click", "x": px, "y": py,
        "description": f"Re-select {action.mech_type}",
    })
    clicks.append({"type": "wait", "duration": 0.5,
                    "description": "Wait for mech selection"})

    # Step 4: Attack (before moving — fires from current known position)
    has_attack = action.weapon and action.target[0] >= 0
    if has_attack:
        weapon_key = _get_weapon_key(action, board) if board else "1"
        clicks.append({
            "type": "key", "text": weapon_key,
            "description": f"Arm {action.weapon} (key '{weapon_key}')",
        })
        clicks.append({"type": "wait", "duration": 0.5,
                        "description": "Wait for weapon arm"})

        tx, ty = grid_to_mcp(action.target[0], action.target[1])
        clicks.append({
            "type": "click", "x": tx, "y": ty,
            "description": f"Fire {action.weapon} at ({action.target[0]},{action.target[1]})",
        })
        clicks.append({"type": "wait", "duration": 2.0,
                        "description": "Wait for attack animation"})

    # Step 5: Move (after attacking)
    has_move = action.move_to and action.move_to != (-1, -1)
    if has_move:
        mech = None
        if board:
            mech = next((u for u in board.units if u.uid == action.mech_uid), None)
        current_pos = (mech.x, mech.y) if mech else None

        if current_pos is None or action.move_to != current_pos:
            dx, dy = grid_to_mcp(action.move_to[0], action.move_to[1])
            clicks.append({
                "type": "click", "x": dx, "y": dy,
                "description": f"Move to ({action.move_to[0]},{action.move_to[1]})",
            })
            clicks.append({"type": "wait", "duration": 1.0,
                            "description": "Wait for move animation"})

    # If no attack and no move, skip
    if not has_attack and not has_move:
        clicks.append({
            "type": "key", "text": "q",
            "description": "Skip action (no attack or move)",
        })
        clicks.append({"type": "wait", "duration": 0.3,
                        "description": "Wait for skip"})

    return clicks


def plan_end_turn() -> list[dict]:
    """Plan clicks for the End Turn button."""
    ex, ey = _end_turn_pos()
    return [
        {"type": "wait", "duration": 0.5,
         "description": "Pause before end turn"},
        {"type": "click", "x": ex, "y": ey,
         "description": "Click End Turn"},
    ]


# --- Backward-Compatible Full-Solution Planning ---

class GameExecutor:
    """Backward-compatible executor for main.py."""

    def __init__(self, board: Board = None):
        self.board = board

    def plan_clicks(self, solution: Solution) -> list[dict]:
        """Convert a Solution into MCP click/key commands."""
        clicks = []
        portraits = get_mech_portraits(self.board) if self.board else {}

        for i, action in enumerate(solution.actions):
            idx = portraits.get(action.mech_type, i)
            clicks.extend(plan_single_mech(action, idx, self.board))

        clicks.extend(plan_end_turn())
        clicks.append({"type": "wait", "duration": 5.0,
                        "description": "Wait for enemy phase"})
        return clicks

    def print_plan(self, solution: Solution) -> None:
        """Print the click plan for debugging."""
        clicks = self.plan_clicks(solution)
        print(f"\n=== CLICK PLAN ({len(clicks)} steps) ===")
        for i, c in enumerate(clicks):
            if c["type"] == "click":
                print(f"  {i+1}. CLICK ({c['x']}, {c['y']}) -- {c['description']}")
            elif c["type"] == "key":
                print(f"  {i+1}. KEY '{c['text']}' -- {c['description']}")
            elif c["type"] == "wait":
                print(f"  {i+1}. WAIT {c['duration']}s -- {c['description']}")
