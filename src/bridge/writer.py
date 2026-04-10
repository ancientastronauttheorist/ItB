"""Write commands to the Lua bridge for action execution.

Replaces MCP mouse clicks as the action execution method when the
bridge is active.
"""

from __future__ import annotations

from src.solver.solver import MechAction
from src.model.board import Board
from src.bridge.protocol import write_command, wait_for_ack


def execute_bridge_action(action: MechAction, board: Board) -> str:
    """Execute a single mech action via the Lua bridge.

    Converts MechAction to bridge command(s) and sends them.
    Returns the final ACK string from the game.

    Command mapping:
      - Move + attack → MOVE_ATTACK (single command, deactivates)
      - Attack only   → ATTACK (deactivates)
      - Move + repair → MOVE then REPAIR (two commands, REPAIR deactivates)
      - Repair only   → REPAIR (deactivates)
      - Move only     → MOVE then SKIP (MOVE doesn't deactivate, SKIP does)
      - Nothing       → SKIP (deactivates)
    """
    has_move = action.move_to and action.move_to != (-1, -1)
    is_repair = action.weapon == "_REPAIR"
    has_attack = action.weapon and action.target[0] >= 0 and not is_repair

    # Check if the mech is actually moving (not staying in place)
    if has_move:
        mech = None
        for u in board.units:
            if u.uid == action.mech_uid:
                mech = u
                break
        if mech and action.move_to == (mech.x, mech.y):
            has_move = False  # staying in place, not a real move

    # Repair: move first if needed, then repair (which deactivates)
    if is_repair:
        if has_move:
            write_command(
                f"MOVE {action.mech_uid} "
                f"{action.move_to[0]} {action.move_to[1]}"
            )
            wait_for_ack(timeout=10.0)
        write_command(f"REPAIR {action.mech_uid}")
        return wait_for_ack(timeout=10.0)

    # Move + attack: single MOVE_ATTACK command (deactivates)
    if has_move and has_attack:
        cmd = (f"MOVE_ATTACK {action.mech_uid} "
               f"{action.move_to[0]} {action.move_to[1]} "
               f"{action.weapon} "
               f"{action.target[0]} {action.target[1]}")
        write_command(cmd)
        return wait_for_ack(timeout=10.0)

    # Attack only (deactivates)
    if has_attack:
        cmd = (f"ATTACK {action.mech_uid} {action.weapon} "
               f"{action.target[0]} {action.target[1]}")
        write_command(cmd)
        return wait_for_ack(timeout=10.0)

    # Move only: MOVE then SKIP (MOVE doesn't deactivate, SKIP does)
    if has_move:
        write_command(
            f"MOVE {action.mech_uid} "
            f"{action.move_to[0]} {action.move_to[1]}"
        )
        wait_for_ack(timeout=10.0)
        write_command(f"SKIP {action.mech_uid}")
        return wait_for_ack(timeout=10.0)

    # No move, no attack — skip
    write_command(f"SKIP {action.mech_uid}")
    return wait_for_ack(timeout=10.0)


def execute_bridge_end_turn() -> str:
    """Send END_TURN command via bridge.

    Uses longer timeout since END_TURN waits for enemy phase to complete.
    """
    write_command("END_TURN")
    return wait_for_ack(timeout=30.0)


def deploy_mech(uid: int, x: int, y: int) -> str:
    """Deploy a mech at the given tile during deployment phase."""
    write_command(f"DEPLOY {uid} {x} {y}")
    return wait_for_ack(timeout=10.0)


def set_bridge_speed(mode: str) -> str:
    """Set bridge speed mode: 'fast' or 'visual'."""
    write_command(f"SET_SPEED {mode}")
    return wait_for_ack(timeout=5.0)
