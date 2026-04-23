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

    Calibrated 2026-04-23 from data/grid_reference.json's measured corners
    at window (215, 32). Empirically verified: grid_to_mcp(F5) = (740, 412)
    hovers the water tile the JetMech flies over — correct terrain per the
    bridge state and ItB's mouse-hover tooltip.

    Historical note: the 2026-04-07 constants (494, 56, 46.21, 34.57) were
    off — step_y was 26% too large and the Y origin was ~187 px too high.
    `auto_turn` (Lua bridge, no MCP clicks) masked the bug for 12 days. First
    `click_action` use on 2026-04-11 failed 50% immediately and was silently
    abandoned. See docs/investigation_grid_calibration_broken.md.
    """
    win = _get_window()

    # Derivation from grid_reference.json corners at window (215, 32):
    #   H8 absolute image-pixel  = (690, 275)
    #   A1 absolute image-pixel  = (690, 660)
    #   H1 absolute image-pixel  = (1040, 467)
    #   A8 absolute image-pixel  = (340, 467)
    #
    # Window-relative origin (H8) = (690-215, 275-32) = (475, 243)
    # Step sizes (constant across window moves):
    #   step_x = (H1_x - H8_x) / 7 = (1040-690)/7 = 50.0
    #   step_y = (A1_y - H8_y) / 14 = (660-275)/14 = 27.5

    sx = win.width / 1280.0
    sy = win.height / 748.0

    ox = win.x + 475.0 * sx
    oy = win.y + 243.0 * sy

    step_x = 50.0 * sx
    step_y = 27.5 * sy

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
# Weapon/repair slot offsets re-calibrated 2026-04-23. Old values (191/255/111, 528)
# missed the icons by ~25 px in Y and ~10 px in X. Empirical hover-verify
# on Pinnacle Frozen Plains placed the Aerial Bombs icon center at image
# (396, 585) with window at (215, 32), giving window-relative (181, 553).
_UI_WEAPON_SLOT_1 = (181, 553)
_UI_WEAPON_SLOT_2 = (245, 553)
_UI_REPAIR_BUTTON = (105, 553)

# Squad-select screen. Calibrated 2026-04-21 via hover-verify: cursor at
# MCP (1006, 562) with window at Quartz (215, 32, 1280, 748) triggered
# the Balanced Roll tooltip → offset (1006-215, 562-32) = (791, 530).
_UI_BALANCED_ROLL = (791, 530)


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


def _ui_balanced_roll() -> tuple[int, int]:
    return _ui_pos(_UI_BALANCED_ROLL)


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
    if wdef.weapon_type == "heal_all":
        # ZONE_ALL: click weapon icon, then click any tile on the board.
        # The "normal" flow already does select → optional move → arm weapon
        # → click target, so heal_all flows through the same path. The solver
        # picks the firing mech's own tile as the target (see Rust
        # get_weapon_targets WeaponType::HealAll), which is always clickable.
        return "normal"
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

    # Step 1: select the mech by clicking its SPRITE position, not the tile
    # center. Mech sprites render ~150 px above the tile they occupy. For
    # flying mechs (e.g., JetMech over water), the tile beneath the sprite
    # is water — clicking the water tile highlights the tile but does NOT
    # select the flying unit hovering above it. Clicking the sprite position
    # selects correctly for both flying and grounded mechs since the sprite
    # always sits on the mech's body.  Empirically verified 2026-04-23 on
    # F5 (grid_to_mcp → (740, 412); sprite at (740, 262) selected JetMech).
    _SPRITE_OFFSET_Y = -150
    tx, ty = grid_to_mcp(mech.x, mech.y)
    plan: list[dict] = [{
        "type": "left_click",
        "x": tx, "y": ty + _SPRITE_OFFSET_Y,
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


def plan_balanced_roll() -> list[dict]:
    """Plan a click for the Balanced Roll button on the squad-select screen."""
    bx, by = _ui_balanced_roll()
    return [{
        "type": "left_click",
        "x": bx, "y": by,
        "description": "Click Balanced Roll",
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
