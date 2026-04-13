"""Main bot loop for Into the Breach.

Flow:
1. Read game state from save files
2. Run solver to find optimal mech actions
3. Execute actions via mouse clicks
4. Wait for enemy phase
5. Repeat

Usage:
  python -m src.main              # Plan mode (show solution, don't click)
  python -m src.main --execute    # Execute the solution via clicks
"""

from __future__ import annotations

import sys
import time
from src.capture.save_parser import load_game_state
from src.model.board import Board
from src.model.weapons import get_weapon_name
# Python solver removed — Rust solver (itb_solver) is the only solver.
# This legacy entry point is kept for backward compatibility.
from src.control.executor import GameExecutor


def read_state():
    """Read current game state from save files."""
    state = load_game_state()
    if state is None:
        print("ERROR: No save data found. Is a game in progress?")
        return None, None
    if state.active_mission is None:
        print("ERROR: No active mission found.")
        return None, None

    m = state.active_mission
    board = Board.from_mission(m, state.grid_power, state.grid_power_max)
    spawns = [(p.x, p.y) for p in m.spawn_points]
    return board, spawns


def solve(board, spawns):
    """Run the solver on the current board state."""
    raise RuntimeError("Python solver removed. Use game_loop.py solve (Rust solver).")


def display_state(board):
    """Show the current board state."""
    print("\n" + "=" * 50)
    print("BOARD STATE")
    print("=" * 50)
    board.print_board()

    print(f"\nGrid Power: {board.grid_power}/{board.grid_power_max}")

    print("\nMechs:")
    for m in board.mechs():
        weapon_name = get_weapon_name(m.weapon)
        status = "READY" if m.active else "DONE"
        print(f"  [{status}] {m.type} at ({m.x},{m.y}) "
              f"HP={m.hp}/{m.max_hp} weapon={weapon_name}")

    print("\nEnemies:")
    for e in board.enemies():
        target = f" → ({e.target_x},{e.target_y})" if e.target_x >= 0 else ""
        print(f"  {e.type} at ({e.x},{e.y}) HP={e.hp}/{e.max_hp}{target}")

    threats = board.get_threatened_buildings()
    if threats:
        print(f"\n⚠ {len(threats)} building(s) threatened:")
        for x, y, u in threats:
            print(f"  Building at ({x},{y}) by {u.type} at ({u.x},{u.y})")


def display_solution(solution):
    """Show the solver's solution."""
    print("\n" + "=" * 50)
    print(f"SOLUTION (score: {solution.score:.0f})")
    print("=" * 50)
    for i, action in enumerate(solution.actions):
        print(f"  {i+1}. {action.description}")


def main():
    execute = "--execute" in sys.argv

    print("Into the Breach Bot")
    print("Reading game state from save files...")

    board, spawns = read_state()
    if board is None:
        return

    display_state(board)

    active = [m for m in board.mechs() if m.active]
    if not active:
        print("\nNo active mechs — all have acted this turn.")
        return

    print(f"\nSolving ({len(active)} mechs to move)...")
    solution = solve(board, spawns)
    display_solution(solution)

    # Show click plan
    executor = GameExecutor()
    executor.print_plan(solution)

    if execute:
        print("\n>>> EXECUTING in 3 seconds... <<<")
        time.sleep(3)
        # The actual execution would use the computer-use MCP tool.
        # For now, print what we would do.
        clicks = executor.plan_clicks(solution)
        for click in clicks:
            if click["type"] == "click":
                print(f"  CLICK ({click['x']}, {click['y']})")
                # mcp__computer-use__left_click(coordinate=[click['x'], click['y']])
                time.sleep(0.1)
            elif click["type"] == "wait":
                print(f"  WAIT {click['duration']}s")
                time.sleep(click["duration"])
        print("\nExecution complete.")
    else:
        print("\nRun with --execute to play the solution.")


if __name__ == "__main__":
    main()
