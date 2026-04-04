"""Execute solver actions by clicking on the game.

Translates MechAction sequences into mouse clicks:
1. Click mech to select
2. Click destination to move
3. Click weapon, then click target
4. Wait for animations
5. Click End Turn when done

Uses the computer-use MCP tool for mouse control and screenshots.
"""

from __future__ import annotations

import time
import subprocess
from pathlib import Path
from src.capture.grid import GridConfig
from src.capture.detect_grid import detect_grid
from src.solver.solver import MechAction, Solution


def save_to_screen(grid: GridConfig, save_x: int, save_y: int) -> tuple[int, int]:
    """Convert save file coordinates (0-7) to screen pixel coordinates.

    Uses the grid's row/col steps directly as save_x/save_y axis vectors.
    The grid origin corresponds to save Point(0, 0).

    grid.row_dx/row_dy = screen step per save_x increment
    grid.col_dx/col_dy = screen step per save_y increment
    """
    px = grid.origin_x + save_x * grid.row_dx + save_y * grid.col_dx
    py = grid.origin_y + save_x * grid.row_dy + save_y * grid.col_dy
    return (int(px), int(py))


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


class GameExecutor:
    """Executes actions on the game via mouse clicks.

    Generates a click/key sequence for the MCP computer-use tool.

    Interaction model (verified via manual testing):
    1. Click mech PORTRAIT on left panel to select
    2. Click destination TILE CENTER to move
    3. Press '1' key to arm primary weapon
    4. Click target TILE CENTER to fire
    5. Wait for animation
    """

    # Mech portrait positions in MCP screenshot coordinates.
    # These are the left-panel portraits, top to bottom.
    # Order matches save file: PunchMech, TankMech, ArtiMech for Rift Walkers.
    PORTRAIT_POSITIONS = [
        (380, 200),  # First mech portrait
        (380, 260),  # Second mech portrait
        (380, 310),  # Third mech portrait
    ]

    # Mech type → portrait index mapping
    MECH_PORTRAIT = {
        "PunchMech": 0,
        "TankMech": 1,
        "ArtiMech": 2,
    }

    # End Turn button in MCP screenshot coordinates
    END_TURN_POS = (420, 143)

    def __init__(self, grid=None):
        # Grid config is kept for backward compatibility but
        # plan_clicks_mcp uses grid_to_mcp directly.
        self.grid = grid

    def plan_clicks(self, solution: Solution) -> list[dict]:
        """Convert a solver Solution into MCP click/key commands.

        Returns a list of dicts with:
          - "type": "click" | "key" | "wait" | "screenshot"
          - "x", "y": MCP screenshot coordinates (for clicks)
          - "text": key name (for key presses)
          - "duration": seconds (for waits)
          - "description": human-readable action
        """
        clicks = []

        for i, action in enumerate(solution.actions):
            clicks.extend(self._plan_mech_action(action, i))

        # End turn
        clicks.append({"type": "wait", "duration": 0.5,
                        "description": "Pause before end turn"})
        clicks.append({
            "type": "click",
            "x": self.END_TURN_POS[0], "y": self.END_TURN_POS[1],
            "description": "Click End Turn",
        })
        clicks.append({"type": "wait", "duration": 5.0,
                        "description": "Wait for enemy phase"})

        return clicks

    def _plan_mech_action(self, action: MechAction, index: int) -> list[dict]:
        """Plan clicks for a single mech action."""
        import re
        clicks = []
        desc = action.description
        moved = "move" in desc

        # Step 1: Select mech via Tab key (avoids pilot popup that
        # portrait clicks cause — the popup eats the next board click)
        clicks.append({
            "type": "key", "text": "tab",
            "description": f"Tab to select next mech ({action.mech_type})",
        })
        clicks.append({"type": "wait", "duration": 0.5, "description": "wait"})

        # Step 2: Attack FIRST (before moving — fires from known position)
        if action.weapon and action.target[0] >= 0:
            # Arm the primary weapon by pressing '1'
            clicks.append({
                "type": "key", "text": "1",
                "description": f"Arm {action.weapon}",
            })
            clicks.append({"type": "wait", "duration": 0.5, "description": "wait"})

            # Click target tile center to fire
            tx, ty = grid_to_mcp(action.target[0], action.target[1])
            clicks.append({
                "type": "click", "x": tx, "y": ty,
                "description": f"Fire {action.weapon} at ({action.target[0]},{action.target[1]})",
            })
            clicks.append({"type": "wait", "duration": 2.0,
                            "description": "Wait for attack animation"})

        # Step 3: Move (after attacking)
        if moved:
            m = re.search(r'move \((\d+),(\d+)\)->\((\d+),(\d+)\)', desc)
            if m:
                dest_x, dest_y = int(m.group(3)), int(m.group(4))
            else:
                dest_x, dest_y = action.move_to

            dx, dy = grid_to_mcp(dest_x, dest_y)
            clicks.append({
                "type": "click", "x": dx, "y": dy,
                "description": f"Move to ({dest_x},{dest_y})",
            })
            clicks.append({"type": "wait", "duration": 1.0,
                            "description": "Wait for move animation"})

        # If no attack and no move, skip the mech's turn
        if not (action.weapon and action.target[0] >= 0) and not moved:
            clicks.append({
                "type": "key", "text": "q",
                "description": "Skip action",
            })
            clicks.append({"type": "wait", "duration": 0.5, "description": "wait"})

        return clicks

    def print_plan(self, solution: Solution) -> None:
        """Print the click plan for debugging."""
        clicks = self.plan_clicks(solution)
        print(f"\n=== CLICK PLAN ({len(clicks)} steps) ===")
        for i, c in enumerate(clicks):
            if c["type"] == "click":
                print(f"  {i+1}. CLICK ({c['x']}, {c['y']}) — {c['description']}")
            elif c["type"] == "key":
                print(f"  {i+1}. KEY '{c['text']}' — {c['description']}")
            elif c["type"] == "wait":
                print(f"  {i+1}. WAIT {c['duration']}s — {c['description']}")
            elif c["type"] == "screenshot":
                print(f"  {i+1}. SCREENSHOT — {c['description']}")
