"""Execute solver actions by clicking on the game.

Translates MechAction objects into mouse-only click sequences for the
MCP ``computer_batch`` tool. The Claude-as-the-loop pattern: each call
returns a plan, the parent process dispatches the batch, then calls
``verify_action`` before moving to the next mech.

Mech selection is by board click — no portraits, no keyboard. Weapon
type is read from ``WEAPON_DEFS`` to choose the right click sequence:
normal weapons need an explicit move click, dash/leap weapons don't,
Repair uses its own button, passives are no-ops.

Coordinate systems:
  - Bridge coordinates: (0-7, 0-7) from the Lua bridge.
  - MCP coordinates: Quartz logical screen pixels.
  - ``grid_to_mcp`` auto-detects the game window and produces MCP coords
    for any tile center, calibrated <2px against all 4 corners.
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

    Calibrated 2026-04-07 against all 4 grid corners (A1, A8, H1, H8)
    with user-verified cursor placement. Max error <2px across all corners.
    """
    win = _get_window()

    # Calibrated from 4 corner tiles at 1280x748 window:
    #   H8 = save(0,0) → pixel (694, 193)  [origin]
    #   A8 = save(0,7) → pixel (369, 436)
    #   H1 = save(7,0) → pixel (1016, 435)
    #   A1 = save(7,7) → pixel (694, 677)

    sx = win.width / 1280.0
    sy = win.height / 748.0

    # Origin in MCP coords (tile 0,0 center, adjusted for window position)
    ox = win.x + 494 * sx
    oy = win.y + 56 * sy

    # Isometric step sizes in MCP pixels
    step_x = 46.21 * sx
    step_y = 34.57 * sy

    px = ox + step_x * (save_x - save_y)
    py = oy + step_y * (save_x + save_y)

    return (int(round(px)), int(round(py)))


def recalibrate():
    """Force re-detection of game window position.

    Call this when the window may have moved (e.g., at the start of each
    turn or before each click_action). The next grid_to_mcp() call will
    re-detect the window.
    """
    global _cached_grid, _cached_window
    _cached_grid = None
    _cached_window = None


# --- Window-Relative UI Positions ---

# These are pixel offsets from the game window's top-left corner at
# 1280x748 window size. _ui_pos() scales them to the live window size.
#
# Live-calibrated 2026-04-11 against Rift Walkers combat mech panel.
# Slot 2 mirrors slot 1 horizontally inside the same weapon box; it
# activates only when a mech has a second weapon (time pod upgrade).
_UI_END_TURN = (95, 78)
_UI_WEAPON_SLOT_1 = (191, 528)
_UI_WEAPON_SLOT_2 = (255, 528)
_UI_REPAIR_BUTTON = (111, 528)


def _ui_pos(offset: tuple[int, int]) -> tuple[int, int]:
    """Scale a window-relative UI offset to MCP coordinates."""
    win = _get_window()
    sx = win.width / 1280.0
    sy = win.height / 748.0
    return (
        int(round(win.x + offset[0] * sx)),
        int(round(win.y + offset[1] * sy)),
    )


def _ui_weapon_slot_1() -> tuple[int, int]:
    return _ui_pos(_UI_WEAPON_SLOT_1)


def _ui_weapon_slot_2() -> tuple[int, int]:
    return _ui_pos(_UI_WEAPON_SLOT_2)


def _ui_repair_button() -> tuple[int, int]:
    return _ui_pos(_UI_REPAIR_BUTTON)


def _ui_end_turn() -> tuple[int, int]:
    return _ui_pos(_UI_END_TURN)


# --- Weapon-type classifier ---

def classify_weapon(weapon_id: str) -> str:
    """Map a weapon ID to a UI click flow:

    - "normal":  optional move click → arm weapon → click target
    - "dash":    arm weapon → click destination tile (no separate move)
    - "repair":  optional move click → click Repair button (no target)
    - "passive": no click flow at all
    """
    if not weapon_id:
        return "normal"
    if weapon_id == "_REPAIR" or weapon_id == "Repair":
        return "repair"
    if weapon_id.startswith("Passive_"):
        return "passive"

    # Look up the weapon definition. WEAPON_DEFS keys are internal IDs.
    from src.model.weapons import get_weapon_def
    wdef = get_weapon_def(weapon_id)
    if wdef is None:
        return "normal"
    if wdef.weapon_type in ("charge", "leap"):
        return "dash"
    if wdef.weapon_type == "passive":
        return "passive"
    return "normal"


def _weapon_icon_pos(weapon_id: str, mech) -> tuple[int, int]:
    """Return MCP coords for the weapon's icon slot.

    The mech object has ``weapon`` (primary) and ``weapon2`` (secondary)
    fields. Anything that matches ``weapon2`` goes to slot 2, otherwise
    slot 1.
    """
    if mech is not None and getattr(mech, "weapon2", None) and weapon_id == mech.weapon2:
        return _ui_weapon_slot_2()
    return _ui_weapon_slot_1()


# --- Per-Mech Click Planning ---

_WAIT_AFTER_SELECT = 0.3
_WAIT_AFTER_MOVE = 0.5
_WAIT_AFTER_ARM = 0.3


def _wait_op(duration: float, note: str) -> dict:
    return {"type": "wait", "duration": duration, "description": note}


def plan_single_mech(action: MechAction, board: Board = None) -> list[dict]:
    """Plan clicks for ONE mech action.

    Returns a list of ops compatible with mcp computer_batch. Click ops
    are ``{"type": "left_click", "x": int, "y": int, "description": str}``
    and wait ops are ``{"type": "wait", "duration": float,
    "description": str}``. Waits are inserted between clicks so the game
    UI has time to animate the previous step (move slide, weapon arm)
    before the next click lands — without them rapid batches eat clicks.
    Mouse only — no portraits, no keyboard.

    Returns an empty list if the mech can't be located on the board.
    """
    if board is None:
        return []

    mech = next((u for u in board.units if u.uid == action.mech_uid), None)
    if mech is None:
        return []

    # Step 1: select the mech by clicking its current tile.
    sx, sy = grid_to_mcp(mech.x, mech.y)
    plan: list[dict] = [{
        "type": "left_click",
        "x": sx, "y": sy,
        "description": f"Select {action.mech_type} at ({mech.x},{mech.y})",
    }]

    weapon_type = classify_weapon(action.weapon)

    # Passive weapons have no clickable target — just selecting the mech
    # is enough to "consume" the action from the Claude perspective.
    if weapon_type == "passive":
        return plan

    # Repair: optional move, then click the Repair button.
    if weapon_type == "repair":
        plan.append(_wait_op(_WAIT_AFTER_SELECT, "wait for selection highlight"))
        if action.move_to and action.move_to != (mech.x, mech.y):
            mx, my = grid_to_mcp(action.move_to[0], action.move_to[1])
            plan.append({
                "type": "left_click",
                "x": mx, "y": my,
                "description": f"Move to ({action.move_to[0]},{action.move_to[1]})",
            })
            plan.append(_wait_op(_WAIT_AFTER_MOVE, "wait for move animation"))
        rx, ry = _ui_repair_button()
        plan.append({
            "type": "left_click",
            "x": rx, "y": ry,
            "description": "Click Repair button",
        })
        return plan

    # Dash/leap weapons: arm the weapon, then click the destination.
    # The dash IS the move — there's no separate move click.
    if weapon_type == "dash":
        plan.append(_wait_op(_WAIT_AFTER_SELECT, "wait for selection highlight"))
        wx, wy = _weapon_icon_pos(action.weapon, mech)
        plan.append({
            "type": "left_click",
            "x": wx, "y": wy,
            "description": f"Arm {action.weapon}",
        })
        if action.target and action.target[0] >= 0:
            plan.append(_wait_op(_WAIT_AFTER_ARM, "wait for weapon arm"))
            tx, ty = grid_to_mcp(action.target[0], action.target[1])
            plan.append({
                "type": "left_click",
                "x": tx, "y": ty,
                "description": f"Dash to ({action.target[0]},{action.target[1]})",
            })
        return plan

    # Normal: optional move first, then arm weapon, then click target.
    plan.append(_wait_op(_WAIT_AFTER_SELECT, "wait for selection highlight"))
    if action.move_to and action.move_to != (mech.x, mech.y):
        mx, my = grid_to_mcp(action.move_to[0], action.move_to[1])
        plan.append({
            "type": "left_click",
            "x": mx, "y": my,
            "description": f"Move to ({action.move_to[0]},{action.move_to[1]})",
        })
        plan.append(_wait_op(_WAIT_AFTER_MOVE, "wait for move animation"))

    if action.weapon and action.target and action.target[0] >= 0:
        wx, wy = _weapon_icon_pos(action.weapon, mech)
        plan.append({
            "type": "left_click",
            "x": wx, "y": wy,
            "description": f"Arm {action.weapon}",
        })
        plan.append(_wait_op(_WAIT_AFTER_ARM, "wait for weapon arm"))
        tx, ty = grid_to_mcp(action.target[0], action.target[1])
        plan.append({
            "type": "left_click",
            "x": tx, "y": ty,
            "description": f"Fire at ({action.target[0]},{action.target[1]})",
        })

    return plan


def plan_end_turn() -> list[dict]:
    """Plan a click for the End Turn button."""
    ex, ey = _ui_end_turn()
    return [{
        "type": "left_click",
        "x": ex, "y": ey,
        "description": "Click End Turn",
    }]


# --- Backward-Compatible Full-Solution Planning ---

class GameExecutor:
    """Backward-compatible executor for main.py."""

    def __init__(self, board: Board = None):
        self.board = board

    def plan_clicks(self, solution: Solution) -> list[dict]:
        """Convert a Solution into MCP click commands."""
        clicks: list[dict] = []
        for action in solution.actions:
            clicks.extend(plan_single_mech(action, self.board))
        clicks.extend(plan_end_turn())
        return clicks

    def print_plan(self, solution: Solution) -> None:
        """Print the click plan for debugging."""
        clicks = self.plan_clicks(solution)
        print(f"\n=== CLICK PLAN ({len(clicks)} steps) ===")
        for i, c in enumerate(clicks):
            print(f"  {i+1}. {c['type']} ({c['x']}, {c['y']}) -- {c['description']}")
