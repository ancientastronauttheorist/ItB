#!/usr/bin/env python3
"""Into the Breach game loop CLI.

Stateless CLI tool for the Claude-as-the-loop architecture.
Each invocation: load session -> compute -> output -> save session.
Claude calls these commands sequentially via computer-use MCP.

Usage:
  python game_loop.py read              # Parse save file, show board + phase
  python game_loop.py solve             # Run solver, store solution
  python game_loop.py execute <index>   # Plan clicks for mech action <index>
  python game_loop.py verify [index]    # Verify last action (or end-turn if no index)
  python game_loop.py end_turn          # Plan clicks for End Turn button
  python game_loop.py status            # Quick state summary

  python game_loop.py new_run <squad> [--achieve X Y]  # Start new run
  python game_loop.py snapshot <label>  # Save state for regression
  python game_loop.py log <message>     # Append to decision log

Combat turn protocol:
  1. read          -> confirm combat_player phase
  2. solve         -> get solution with N actions
  3. execute 0     -> get click plan, execute via MCP
  4. verify 0      -> confirm mech acted
  5. execute 1     -> repeat for each action
  6. verify 1
  7. ...
  8. end_turn      -> click End Turn
  9. verify        -> confirm turn advanced
  10. -> back to 1
"""

import argparse
import sys

from src.loop.commands import (
    cmd_read,
    cmd_solve,
    cmd_execute,
    cmd_verify,
    cmd_end_turn,
    cmd_status,
    cmd_new_run,
    cmd_snapshot,
    cmd_log,
    cmd_calibrate,
)


def main():
    parser = argparse.ArgumentParser(
        description="Into the Breach game loop CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # read
    p_read = sub.add_parser("read", help="Parse save file, show board state")
    p_read.add_argument("--profile", default="Alpha", help="Save profile name")

    # solve
    p_solve = sub.add_parser("solve", help="Run solver, store solution")
    p_solve.add_argument("--profile", default="Alpha")
    p_solve.add_argument("--time-limit", type=float, default=10.0,
                         help="Solver time limit in seconds")

    # execute
    p_exec = sub.add_parser("execute", help="Plan clicks for one mech action")
    p_exec.add_argument("index", type=int, help="Action index from solution")
    p_exec.add_argument("--profile", default="Alpha")

    # verify
    p_verify = sub.add_parser("verify", help="Verify last action succeeded")
    p_verify.add_argument("index", type=int, nargs="?", default=-1,
                          help="Action index to verify (-1 for end-turn check)")
    p_verify.add_argument("--profile", default="Alpha")

    # end_turn
    sub.add_parser("end_turn", help="Plan clicks for End Turn")

    # status
    p_status = sub.add_parser("status", help="Quick state summary")
    p_status.add_argument("--profile", default="Alpha")

    # new_run
    p_new = sub.add_parser("new_run", help="Initialize a new run session")
    p_new.add_argument("squad", help="Squad name")
    p_new.add_argument("--achieve", nargs="*", default=[],
                       help="Achievement targets")
    p_new.add_argument("--difficulty", type=int, default=0)

    # snapshot
    p_snap = sub.add_parser("snapshot", help="Save state for regression")
    p_snap.add_argument("label", help="Snapshot label")
    p_snap.add_argument("--profile", default="Alpha")

    # log
    p_log = sub.add_parser("log", help="Append to decision log")
    p_log.add_argument("message", nargs="+", help="Log message")

    # calibrate
    sub.add_parser("calibrate", help="Show detected window position and grid coordinates")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "read":
        cmd_read(profile=args.profile)
    elif args.command == "solve":
        cmd_solve(profile=args.profile, time_limit=args.time_limit)
    elif args.command == "execute":
        cmd_execute(args.index, profile=args.profile)
    elif args.command == "verify":
        cmd_verify(args.index, profile=args.profile)
    elif args.command == "end_turn":
        cmd_end_turn()
    elif args.command == "status":
        cmd_status(profile=args.profile)
    elif args.command == "new_run":
        cmd_new_run(args.squad, args.achieve, args.difficulty)
    elif args.command == "snapshot":
        cmd_snapshot(args.label, profile=args.profile)
    elif args.command == "log":
        cmd_log(" ".join(args.message))
    elif args.command == "calibrate":
        cmd_calibrate()


if __name__ == "__main__":
    main()
