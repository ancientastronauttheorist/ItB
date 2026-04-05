"""Execute solver actions by clicking on the game.

Translates MechAction sequences into mouse clicks for the MCP
computer-use tool. Supports per-mech execution with verification
gaps between each mech (Claude-as-the-loop pattern).

Mech selection uses portrait clicks (not Tab) for reliability when
executing non-consecutively with verify steps between mechs.

Coordinate systems:
  - Save file coordinates: (0-7, 0-7) — from saveData.lua
  - MCP screenshot coordinates: pixel positions in MCP screenshots
  - Use grid_to_mcp() to convert between them
"""

from __future__ import annotations

from src.solver.solver import MechAction, Solution
from src.model.board import Board


# --- Coordinate Conversion ---

# MCP screenshot coordinate system calibration.
# Calibrated by zooming into row labels "1"/"8" and column labels "A"/"H"
# in MCP screenshots and solving the isometric grid transform.
# Verified against hover info: building (5,2) at (710,437), building (3,6) at (980,371).
_MCP_ORIGIN_X = 858.0
_MCP_ORIGIN_Y = 675.6
_MCP_AX = -47.14   # save_x step (upper-left direction in screen)
_MCP_AY = -34.29
_MCP_BX = 43.86    # save_y step (upper-right direction in screen)
_MCP_BY = -33.57


def grid_to_mcp(save_x: int, save_y: int) -> tuple[int, int]:
    """Convert save file coordinates to MCP screenshot pixel coordinates.

    This is the coordinate system used by the computer-use MCP tool.
    Calibrated directly from visual measurements in MCP screenshots.
    """
    px = _MCP_ORIGIN_X + save_x * _MCP_AX + save_y * _MCP_BX
    py = _MCP_ORIGIN_Y + save_x * _MCP_AY + save_y * _MCP_BY
    return (int(round(px)), int(round(py)))


# --- Portrait Positions ---

# Mech portrait Y positions in MCP screenshot coordinates (left panel).
# These are consistent across all squads — always 3 portraits, top to bottom.
PORTRAIT_X = 380
PORTRAIT_Y = [200, 260, 310]

# End Turn button in MCP screenshot coordinates
END_TURN_POS = (420, 143)

# Board center for dismissing popups
BOARD_CENTER = (700, 400)


def get_mech_portraits(board: Board) -> dict[str, int]:
    """Build mech_type → portrait_index mapping from board state.

    Mechs appear in portrait order (top to bottom) matching their
    order in the save file's pawn list. This function returns the
    mapping so plan_single_mech can click the right portrait.
    """
    # Mechs are ordered by UID (save file order = portrait order)
    mechs = sorted(
        [u for u in board.units if u.is_mech and u.hp > 0],
        key=lambda u: u.uid
    )
    return {m.type: i for i, m in enumerate(mechs)}


def _get_weapon_key(action: MechAction, board: Board) -> str:
    """Return '1' for primary weapon, '2' for secondary.

    Looks up which weapon the solver chose and compares it to
    the mech's primary vs secondary weapon assignment.
    """
    if not action.weapon:
        return "1"

    # Find the mech in the board to check its weapons
    mech = None
    for u in board.units:
        if u.uid == action.mech_uid:
            mech = u
            break

    if mech is None:
        return "1"  # fallback

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

    Args:
        action: The solver's MechAction for this mech.
        portrait_index: Which portrait to click (0, 1, or 2).
        board: Board state, used for primary/secondary weapon detection.

    Returns:
        List of click/key/wait commands for MCP execution.
    """
    clicks = []

    # Step 1: Click portrait to select mech
    clicks.append({
        "type": "click",
        "x": PORTRAIT_X, "y": PORTRAIT_Y[portrait_index],
        "description": f"Click portrait to select {action.mech_type}",
    })
    clicks.append({"type": "wait", "duration": 0.3,
                    "description": "Wait for portrait response"})

    # Step 2: Click board center to dismiss pilot popup
    clicks.append({
        "type": "click",
        "x": BOARD_CENTER[0], "y": BOARD_CENTER[1],
        "description": "Dismiss pilot popup",
    })
    clicks.append({"type": "wait", "duration": 0.3,
                    "description": "Wait for popup dismiss"})

    # Step 3: Re-click portrait (now selects mech properly)
    clicks.append({
        "type": "click",
        "x": PORTRAIT_X, "y": PORTRAIT_Y[portrait_index],
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
        # Check if the mech is actually moving somewhere different
        # (The solver includes move_to even when staying in place)
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

    # If no attack and no move, skip (press 'q' to deselect)
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
    return [
        {"type": "wait", "duration": 0.5,
         "description": "Pause before end turn"},
        {"type": "click",
         "x": END_TURN_POS[0], "y": END_TURN_POS[1],
         "description": "Click End Turn"},
    ]


# --- Backward-Compatible Full-Solution Planning ---

class GameExecutor:
    """Executes actions on the game via mouse clicks.

    Generates a click/key sequence for the MCP computer-use tool.
    Kept for backward compatibility with main.py.
    """

    def __init__(self, board: Board = None):
        self.board = board

    def plan_clicks(self, solution: Solution) -> list[dict]:
        """Convert a solver Solution into MCP click/key commands.

        Backward-compatible: plans all mechs + end turn as one sequence.
        For the game loop, use plan_single_mech() + plan_end_turn() instead.
        """
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
