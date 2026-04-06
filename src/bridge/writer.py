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

    Converts MechAction to a command string and sends it.
    Returns the ACK string from the game.
    """
    has_move = action.move_to and action.move_to != (-1, -1)
    has_attack = action.weapon and action.target[0] >= 0

    # Check if the mech is actually moving (not staying in place)
    if has_move:
        mech = None
        for u in board.units:
            if u.uid == action.mech_uid:
                mech = u
                break
        if mech and action.move_to == (mech.x, mech.y):
            has_move = False  # staying in place, not a real move

    if has_move and has_attack:
        cmd = (f"MOVE_ATTACK {action.mech_uid} "
               f"{action.move_to[0]} {action.move_to[1]} "
               f"{action.weapon} "
               f"{action.target[0]} {action.target[1]}")
    elif has_attack:
        cmd = (f"ATTACK {action.mech_uid} {action.weapon} "
               f"{action.target[0]} {action.target[1]}")
    elif has_move:
        cmd = f"MOVE {action.mech_uid} {action.move_to[0]} {action.move_to[1]}"
    else:
        # No move, no attack — skip (do nothing)
        return "OK SKIP"

    write_command(cmd)
    return wait_for_ack(timeout=10.0)


def execute_bridge_end_turn() -> str:
    """Send END_TURN command via bridge."""
    write_command("END_TURN")
    return wait_for_ack(timeout=10.0)
