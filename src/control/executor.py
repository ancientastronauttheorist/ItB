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

    Save file: Point(x, y) where x=col(0-7), y=row(0-7)
    Grid config: tile_to_pixel(row=1-8, col=1-8)
    """
    row = save_y + 1  # 0-indexed -> 1-indexed
    col = save_x + 1
    px, py = grid.tile_to_pixel(row, col)
    return (int(px), int(py))


class GameExecutor:
    """Executes actions on the game via mouse clicks.

    This class generates click coordinates but does NOT directly call
    the computer-use MCP tool. Instead, it produces a click sequence
    that the main bot loop feeds to the MCP tool.
    """

    def __init__(self, grid: GridConfig | None = None):
        self.grid = grid or detect_grid()
        if self.grid is None:
            raise RuntimeError("Could not detect game window")

    def plan_clicks(self, solution: Solution) -> list[dict]:
        """Convert a solver Solution into a sequence of click commands.

        Returns a list of dicts, each with:
          - "type": "click", "wait", "screenshot"
          - "x", "y": screen coordinates (for clicks)
          - "duration": seconds (for waits)
          - "description": human-readable action
        """
        clicks = []

        for i, action in enumerate(solution.actions):
            clicks.extend(self._plan_mech_action(action, i))

        # End turn
        clicks.append({"type": "wait", "duration": 0.5,
                        "description": "Pause before end turn"})
        clicks.append(self._end_turn_click())
        clicks.append({"type": "wait", "duration": 3.0,
                        "description": "Wait for enemy phase"})

        return clicks

    def _plan_mech_action(self, action: MechAction, index: int) -> list[dict]:
        """Plan clicks for a single mech action."""
        clicks = []

        # We need the mech's current position to click-select it.
        # The solver stores move_to, but we need the ORIGINAL position
        # before the move. That's in the board state, keyed by mech_uid.
        # For now, we'll rely on the action having a description that
        # includes the original position, or we track it separately.
        # The simplest approach: the solver already knows the mech position.

        # Step 1: Click on the mech to select it
        # We need the mech's position BEFORE this action.
        # In the solver, mech starts at its board position.
        # Since we execute actions in order, after each action the mech
        # has moved to action.move_to. So for action N, the mech is at
        # whatever position it was before action N.
        #
        # For the first action of each mech, the position comes from
        # the save file. We pass this through from the board state.
        #
        # For simplicity, we'll just click the move_to position
        # (since the solver plans actions in sequence and knows positions).
        # Actually - we need to click the mech's CURRENT position first.
        # Let's extract it from the action description or pass it explicitly.

        # Parse original position from description if available
        # Format: "MechType, move (x1,y1)->(x2,y2), fire Weapon at (tx,ty)"
        # or: "MechType, fire Weapon at (tx,ty)" (no move)
        desc = action.description
        moved = "move" in desc

        # For now, hardcode the click sequence
        # The game expects: click mech -> click move dest -> click weapon -> click target

        if moved:
            # Click mech current position (inferred from the move description)
            # Parse "move (x1,y1)->(x2,y2)" to get (x1,y1)
            import re
            m = re.search(r'move \((\d+),(\d+)\)->\((\d+),(\d+)\)', desc)
            if m:
                orig_x, orig_y = int(m.group(1)), int(m.group(2))
                dest_x, dest_y = int(m.group(3)), int(m.group(4))
            else:
                # No move info, use move_to as both origin and dest
                orig_x, orig_y = action.move_to
                dest_x, dest_y = action.move_to

            # Click mech to select
            sx, sy = save_to_screen(self.grid, orig_x, orig_y)
            clicks.append({
                "type": "click", "x": sx, "y": sy,
                "description": f"Select {action.mech_type} at ({orig_x},{orig_y})",
            })
            clicks.append({"type": "wait", "duration": 0.3, "description": "wait"})

            # Click destination to move
            dx, dy = save_to_screen(self.grid, dest_x, dest_y)
            clicks.append({
                "type": "click", "x": dx, "y": dy,
                "description": f"Move to ({dest_x},{dest_y})",
            })
            clicks.append({"type": "wait", "duration": 0.8,
                            "description": "Wait for move animation"})
        else:
            # No move, just click mech to select
            mx, my = action.move_to
            sx, sy = save_to_screen(self.grid, mx, my)
            clicks.append({
                "type": "click", "x": sx, "y": sy,
                "description": f"Select {action.mech_type} at ({mx},{my})",
            })
            clicks.append({"type": "wait", "duration": 0.3, "description": "wait"})

        # Step 2: Attack (if weapon specified)
        if action.weapon and action.target[0] >= 0:
            # After moving, the mech is selected and weapon options appear.
            # In ITB, after moving the mech shows weapon targeting automatically
            # for the primary weapon. We click the target tile.
            #
            # For now, assume primary weapon is auto-selected after move.
            # TODO: handle weapon button clicks for secondary weapons.

            tx, ty = save_to_screen(self.grid, action.target[0], action.target[1])
            clicks.append({
                "type": "click", "x": tx, "y": ty,
                "description": f"Fire {action.weapon} at ({action.target[0]},{action.target[1]})",
            })
            clicks.append({"type": "wait", "duration": 1.0,
                            "description": "Wait for attack animation"})
        else:
            # No attack, just confirm move (click the mech again or wait)
            # In ITB, if you move without attacking, you need to click
            # "Confirm" or the end-action button
            clicks.append({"type": "wait", "duration": 0.5, "description": "wait"})

        return clicks

    def _end_turn_click(self) -> dict:
        """Return click coordinates for the End Turn button.

        The End Turn button is in the top-left area of the game window.
        Position is relative to window and consistent.
        """
        # End Turn button center (relative position within game window)
        # From our screenshots: approximately at window_x + 260, window_y + 145
        # Using the grid's origin to estimate window position
        # The grid origin (1,A) is at a known offset from the window
        # Window is ~479px right of window left for the grid origin
        # End Turn is ~260px right of window left, ~145px below window top
        #
        # More robust: End Turn button is always at approximately the same
        # fraction of the window. For 1280x748 window:
        # End Turn center: roughly x=260, y=145 from window top-left

        # Compute from grid reference
        # Grid origin is at (grid.origin_x, grid.origin_y) on screen
        # Grid origin is ~479px from window left, ~549px from window top
        # So window left ≈ grid.origin_x - 479
        # Window top ≈ grid.origin_y - 549
        win_left = self.grid.origin_x - 479
        win_top = self.grid.origin_y - 549

        btn_x = int(win_left + 340)
        btn_y = int(win_top + 145)
        return {
            "type": "click", "x": btn_x, "y": btn_y,
            "description": "Click End Turn",
        }

    def print_plan(self, solution: Solution) -> None:
        """Print the click plan for debugging."""
        clicks = self.plan_clicks(solution)
        print(f"\n=== CLICK PLAN ({len(clicks)} steps) ===")
        for i, c in enumerate(clicks):
            if c["type"] == "click":
                print(f"  {i+1}. CLICK ({c['x']}, {c['y']}) — {c['description']}")
            elif c["type"] == "wait":
                print(f"  {i+1}. WAIT {c['duration']}s — {c['description']}")
            elif c["type"] == "screenshot":
                print(f"  {i+1}. SCREENSHOT — {c['description']}")
