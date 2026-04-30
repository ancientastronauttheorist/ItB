"""Small predicates for interpreting solver actions.

Rust emits move-only actions with sentinel weapons/targets such as
``"None"`` or ``"Unknown"`` and ``(255, 255)``. Execution paths must agree
that those are not attacks, otherwise the bridge can fire slot 0 by mistake.
"""

from __future__ import annotations

from typing import Any


NO_ATTACK_WEAPONS = {"", "None", "Unknown"}
BOARD_SIZE = 8


def is_repair_action(action: Any) -> bool:
    """Return True when an action is the explicit repair command."""
    return getattr(action, "weapon", None) == "_REPAIR"


def is_board_target(target: Any) -> bool:
    """Return True when ``target`` names an on-board tile."""
    if not isinstance(target, (list, tuple)) or len(target) < 2:
        return False
    x, y = target[0], target[1]
    if isinstance(x, bool) or isinstance(y, bool):
        return False
    if not isinstance(x, int) or not isinstance(y, int):
        return False
    return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE


def action_has_attack(action: Any) -> bool:
    """Return True only when an action should fire a weapon at a board tile."""
    if is_repair_action(action):
        return False
    weapon = getattr(action, "weapon", None)
    if weapon is None or str(weapon) in NO_ATTACK_WEAPONS:
        return False
    return is_board_target(getattr(action, "target", None))
