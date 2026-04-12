"""Write commands to the Lua bridge for action execution.

Replaces MCP mouse clicks as the action execution method when the
bridge is active.
"""

from __future__ import annotations

from src.solver.solver import MechAction
from src.model.board import Board
from src.bridge.protocol import write_command, wait_for_ack


def _resolve_weapon_slot(action: MechAction, board: Board) -> int:
    """Resolve weapon name to 0-based slot index by matching against the mech's weapons.

    Returns 0 for primary weapon, 1 for secondary weapon.
    Falls back to 0 if the weapon can't be matched (better than failing with 'Unknown').
    """
    mech = None
    for u in board.units:
        if u.uid == action.mech_uid:
            mech = u
            break

    if mech is None:
        return 0

    if action.weapon == mech.weapon:
        return 0
    if action.weapon == mech.weapon2:
        return 1

    # Fallback: weapon name didn't match either slot exactly.
    # Default to slot 0 (primary) — this is more likely correct than failing.
    return 0


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

    # Action ACK timeout must accommodate the coroutine-based wait_for_board
    # in modloader.lua. For complex animations (conveyor interactions, chain
    # pushes, tidal waves) Board:IsBusy() can stay true for the full 15 s
    # Lua timeout — and MOVE_ATTACK has TWO back-to-back waits (post-move,
    # post-attack), so the bridge may take up to 30 s wall to write the
    # ACK even on a successful action. Python must be longer than that.
    # 60 s gives a 2x margin; a healthy turn still ACKs in <2 s.
    _ACTION_TIMEOUT = 60.0

    # Repair: move first if needed, then repair (which deactivates)
    if is_repair:
        if has_move:
            write_command(
                f"MOVE {action.mech_uid} "
                f"{action.move_to[0]} {action.move_to[1]}"
            )
            wait_for_ack(timeout=_ACTION_TIMEOUT)
        write_command(f"REPAIR {action.mech_uid}")
        return wait_for_ack(timeout=_ACTION_TIMEOUT)

    # Move + attack: single MOVE_ATTACK command (deactivates)
    if has_move and has_attack:
        weapon_slot = _resolve_weapon_slot(action, board)
        cmd = (f"MOVE_ATTACK {action.mech_uid} "
               f"{action.move_to[0]} {action.move_to[1]} "
               f"{weapon_slot} "
               f"{action.target[0]} {action.target[1]}")
        write_command(cmd)
        return wait_for_ack(timeout=_ACTION_TIMEOUT)

    # Attack only (deactivates)
    if has_attack:
        weapon_slot = _resolve_weapon_slot(action, board)
        cmd = (f"ATTACK {action.mech_uid} {weapon_slot} "
               f"{action.target[0]} {action.target[1]}")
        write_command(cmd)
        return wait_for_ack(timeout=_ACTION_TIMEOUT)

    # Move only: MOVE then SKIP (MOVE doesn't deactivate, SKIP does)
    if has_move:
        write_command(
            f"MOVE {action.mech_uid} "
            f"{action.move_to[0]} {action.move_to[1]}"
        )
        wait_for_ack(timeout=_ACTION_TIMEOUT)
        write_command(f"SKIP {action.mech_uid}")
        return wait_for_ack(timeout=_ACTION_TIMEOUT)

    # No move, no attack — skip
    write_command(f"SKIP {action.mech_uid}")
    return wait_for_ack(timeout=_ACTION_TIMEOUT)


_ACTION_TIMEOUT = 60.0


def move_mech(uid: int, x: int, y: int) -> str:
    """Move a mech to (x, y) without deactivating.

    The Lua MOVE handler calls pawn:Move() and waits for the board to
    settle, but does NOT call SetActive(false). The mech remains active
    for a subsequent attack_mech or skip_mech call.
    """
    write_command(f"MOVE {uid} {x} {y}")
    return wait_for_ack(timeout=_ACTION_TIMEOUT)


def attack_mech(uid: int, weapon_slot: int, target_x: int, target_y: int) -> str:
    """Fire a mech's weapon at the target tile, then deactivate.

    weapon_slot is 0-based (0=primary, 1=secondary).
    The Lua ATTACK handler fires and calls SetActive(false).
    """
    write_command(f"ATTACK {uid} {weapon_slot} {target_x} {target_y}")
    return wait_for_ack(timeout=_ACTION_TIMEOUT)


def skip_mech(uid: int) -> str:
    """Deactivate a mech without attacking (after move, or no-op)."""
    write_command(f"SKIP {uid}")
    return wait_for_ack(timeout=_ACTION_TIMEOUT)


def repair_mech(uid: int) -> str:
    """Repair a mech at its current position and deactivate."""
    write_command(f"REPAIR {uid}")
    return wait_for_ack(timeout=_ACTION_TIMEOUT)


def execute_bridge_end_turn() -> str:
    """Send END_TURN command via bridge.

    On this ITB build the Lua handler can only SetActive all player pawns —
    it cannot advance the turn. It ACKs immediately with NEEDS_MCP_CLICK and
    Python's cmd_end_turn routes through plan_end_turn for the actual click.
    SetActive iteration is sub-second; 10 s is plenty of headroom.
    """
    write_command("END_TURN")
    return wait_for_ack(timeout=10.0)


def deploy_mech(uid: int, x: int, y: int) -> str:
    """Deploy a mech at the given tile during deployment phase."""
    write_command(f"DEPLOY {uid} {x} {y}")
    return wait_for_ack(timeout=10.0)


def set_bridge_speed(mode: str) -> str:
    """Set bridge speed mode: 'fast' or 'visual'."""
    write_command(f"SET_SPEED {mode}")
    return wait_for_ack(timeout=5.0)
