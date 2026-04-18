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
    cmd_verify_action,
    cmd_click_action,
    cmd_click_end_turn,
    cmd_research_next,
    cmd_research_probe_mech,
    cmd_research_submit,
    cmd_review_overrides,
    cmd_mine_overrides,
    cmd_end_turn,
    cmd_status,
    cmd_new_run,
    cmd_snapshot,
    cmd_log,
    cmd_calibrate,
    cmd_achievements,
    cmd_replay,
    cmd_auto_turn,
    cmd_auto_mission,
    cmd_analyze,
    cmd_validate,
    cmd_tune,
    cmd_mission_end,
    cmd_annotate,
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

    # verify_action
    p_verify_action = sub.add_parser(
        "verify_action",
        help="Per-action diff: predicted vs actual board state",
    )
    p_verify_action.add_argument("index", type=int,
                                 help="Action index from solution")

    # click_action
    p_click_action = sub.add_parser(
        "click_action",
        help="Plan clicks for ONE mech action (mouse-only, computer_batch ready)",
    )
    p_click_action.add_argument("index", type=int,
                                help="Action index from solution")

    # research_next
    p_research_next = sub.add_parser(
        "research_next",
        help="Pick next research queue entry → emit capture plan",
    )
    p_research_next.add_argument("--profile", default="Alpha")

    # research_submit
    p_research_submit = sub.add_parser(
        "research_submit",
        help="Submit Vision JSON response for an in-progress research entry",
    )
    p_research_submit.add_argument("research_id",
                                   help="ID returned by `research_next`")
    p_research_submit.add_argument("vision_json",
                                   help="JSON dict keyed by crop name (name_tag/"
                                        "unit_status/weapon_preview/terrain_tooltip) "
                                        "with Vision JSON string values")
    p_research_submit.add_argument("--profile", default="Alpha")
    p_research_submit.add_argument(
        "--no-wiki",
        action="store_true",
        help="Disable wiki fallback on low-confidence parses (offline mode)",
    )

    # research_probe_mech
    p_research_probe_mech = sub.add_parser(
        "research_probe_mech",
        help="Probe one weapon slot on a mech → emit capture plan + research_id",
    )
    p_research_probe_mech.add_argument(
        "tile",
        help="Mech tile in A1-H8 notation (or 'x,y' bridge coords)",
    )
    p_research_probe_mech.add_argument(
        "slot",
        type=int,
        nargs="?",
        default=0,
        help="Weapon slot index (0=secondary/repair, 1=prime). Default 0.",
    )
    p_research_probe_mech.add_argument("--profile", default="Alpha")

    # review_overrides
    p_review = sub.add_parser(
        "review_overrides",
        help="List / accept / reject staged weapon override candidates",
    )
    p_review.add_argument(
        "sub_action",
        nargs="?",
        default="list",
        choices=["list", "accept", "reject"],
        help="Subaction (default: list)",
    )
    p_review.add_argument(
        "index",
        type=int,
        nargs="?",
        default=None,
        help="Staged candidate index (required for accept/reject)",
    )
    p_review.add_argument(
        "--force",
        action="store_true",
        help="Accept without a regression board at tests/weapon_overrides/"
             "<weapon_id>_<case>.json (not recommended)",
    )

    # mine_overrides
    p_mine = sub.add_parser(
        "mine_overrides",
        help="P4-1d: pattern-mine override candidates from failure_db "
             "+ weapon_def_mismatches.jsonl, report or stage them",
    )
    p_mine.add_argument(
        "--execute",
        action="store_true",
        help="Write fixtures to tests/weapon_overrides/ and append "
             "staged entries. Default is a report-only dry run.",
    )
    p_mine.add_argument(
        "--max-stage",
        type=int,
        default=3,
        help="Cap on how many candidates to stage in one run "
             "(keeps review loads sane). Default: 3.",
    )
    p_mine.add_argument(
        "--time-limit",
        type=float,
        default=2.0,
        help="Per-solve time limit for the observable-change verifier "
             "(seconds). Default: 2.0.",
    )
    p_mine.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip the P4-1c observable-change verifier. Useful when "
             "the itb_solver wheel isn't installed. Drafts still go "
             "through the P3-7 gate when accepted.",
    )
    p_mine.add_argument(
        "--since",
        type=str,
        default=None,
        help="ISO timestamp; failure_db rows older than this are "
             "ignored. Overrides data/mining_cutoff.json. Use when "
             "bisecting which fix retired which cluster.",
    )
    p_mine.add_argument(
        "--no-cutoff",
        action="store_true",
        help="Disable the mining cutoff entirely (count every "
             "failure_db row regardless of age). For historical "
             "audits only — the default cutoff exists to keep stale "
             "signal out of live mining.",
    )

    # click_end_turn
    sub.add_parser(
        "click_end_turn",
        help="Plan clicks for the End Turn button",
    )

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
    p_new.add_argument("--tags", nargs="*", default=[],
                       help="Run classification tags (e.g. 'audit' to exclude "
                            "from tuner training corpus)")

    # snapshot
    p_snap = sub.add_parser("snapshot", help="Save state for regression")
    p_snap.add_argument("label", help="Snapshot label")
    p_snap.add_argument("--profile", default="Alpha")

    # log
    p_log = sub.add_parser("log", help="Append to decision log")
    p_log.add_argument("message", nargs="+", help="Log message")

    # calibrate
    sub.add_parser("calibrate", help="Show detected window position and grid coordinates")

    # achievements
    sub.add_parser("achievements", help="Query Steam for achievement progress")

    # replay
    p_replay = sub.add_parser("replay",
                              help="Re-run solver on a recorded board state")
    p_replay.add_argument("run_id", help="Run ID (directory name in recordings/)")
    p_replay.add_argument("turn", type=int, help="Turn number to replay")
    p_replay.add_argument("--time-limit", type=float, default=30.0,
                          help="Solver time limit (default: 30s)")
    p_replay.add_argument("--mission", type=int, default=None,
                          help="Mission index (for m00_ prefixed files)")
    p_replay.add_argument("--no-rust", action="store_true",
                          help="Use Python solver instead of Rust")

    # auto_turn
    p_auto_turn = sub.add_parser("auto_turn",
                                 help="Execute a full combat turn via bridge")
    p_auto_turn.add_argument("--profile", default="Alpha")
    p_auto_turn.add_argument("--time-limit", type=float, default=10.0,
                             help="Solver time limit (default: 10s)")
    p_auto_turn.add_argument("--no-wait", action="store_true",
                             help="Don't poll bridge for combat_player at entry")
    p_auto_turn.add_argument("--max-wait", type=float, default=20.0,
                             help="Seconds to poll enemy→player transition (default: 20)")

    # auto_mission
    p_auto_mission = sub.add_parser("auto_mission",
                                    help="Execute a full mission via bridge")
    p_auto_mission.add_argument("--profile", default="Alpha")
    p_auto_mission.add_argument("--time-limit", type=float, default=10.0,
                                help="Solver time limit per turn (default: 10s)")
    p_auto_mission.add_argument("--max-turns", type=int, default=20,
                                help="Safety limit on turns (default: 20)")

    # analyze
    p_analyze = sub.add_parser("analyze",
                               help="Analyze failure database for patterns")
    p_analyze.add_argument("--min-samples", type=int, default=30,
                           help="Minimum samples for gated analysis (default: 30)")

    # validate
    p_validate = sub.add_parser("validate",
                                help="Compare weight versions across recorded boards")
    p_validate.add_argument("old_weights", help="Path to old weights JSON")
    p_validate.add_argument("new_weights", help="Path to new weights JSON")
    p_validate.add_argument("--time-limit", type=float, default=10.0,
                            help="Solver time limit per board (default: 10s)")
    p_validate.add_argument("--solver-version", default=None,
                            help="Only test boards from this solver version")
    p_validate.add_argument("--failures-only", action="store_true",
                            help="Only test boards from the failure database, "
                                 "scored under stricter Fixed/Regressed/Neutral rules")

    # tune
    p_tune = sub.add_parser("tune",
                            help="Auto-tune solver weights via recorded boards")
    p_tune.add_argument("--iterations", type=int, default=100,
                        help="Total optimization iterations (default: 100)")
    p_tune.add_argument("--min-boards", type=int, default=50,
                        help="Minimum boards required (default: 50)")
    p_tune.add_argument("--time-limit", type=float, default=5.0,
                        help="Solver time limit per board (default: 5s)")
    p_tune.add_argument("--since", type=str, default=None,
                        help="ISO timestamp; failure-corpus rows older "
                             "than this are ignored. Overrides "
                             "data/mining_cutoff.json.")
    p_tune.add_argument("--no-cutoff", action="store_true",
                        help="Disable the failure-corpus cutoff "
                             "entirely (count every row regardless "
                             "of age).")

    p_mission_end = sub.add_parser("mission_end",
                                   help="Record mission outcome (win/loss) on the active run")
    p_mission_end.add_argument("outcome", choices=["win", "loss"],
                               help="Mission result")
    p_mission_end.add_argument("--notes", default=None,
                               help="Optional free-text context")

    p_annotate = sub.add_parser("annotate",
                                help="Add a notes field to a recorded board (regression context)")
    p_annotate.add_argument("run_id", help="Run directory name")
    p_annotate.add_argument("turn", type=int, help="Turn number (1-indexed)")
    p_annotate.add_argument("notes", help="Context string")
    p_annotate.add_argument("--mission", type=int, default=0,
                            help="Mission index (default: 0)")

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
    elif args.command == "verify_action":
        cmd_verify_action(args.index)
    elif args.command == "click_action":
        cmd_click_action(args.index)
    elif args.command == "click_end_turn":
        cmd_click_end_turn()
    elif args.command == "research_next":
        cmd_research_next(profile=args.profile)
    elif args.command == "research_submit":
        cmd_research_submit(args.research_id, args.vision_json,
                            profile=args.profile,
                            wiki_fallback=not args.no_wiki)
    elif args.command == "research_probe_mech":
        cmd_research_probe_mech(args.tile, args.slot, profile=args.profile)
    elif args.command == "review_overrides":
        cmd_review_overrides(args.sub_action, args.index, force=args.force)
    elif args.command == "mine_overrides":
        cmd_mine_overrides(
            execute=args.execute,
            max_stage=args.max_stage,
            time_limit=args.time_limit,
            verify=not args.no_verify,
            since=args.since,
            no_cutoff=args.no_cutoff,
        )
    elif args.command == "end_turn":
        cmd_end_turn()
    elif args.command == "status":
        cmd_status(profile=args.profile)
    elif args.command == "new_run":
        cmd_new_run(args.squad, args.achieve, args.difficulty, tags=args.tags)
    elif args.command == "snapshot":
        cmd_snapshot(args.label, profile=args.profile)
    elif args.command == "log":
        cmd_log(" ".join(args.message))
    elif args.command == "calibrate":
        cmd_calibrate()
    elif args.command == "achievements":
        cmd_achievements()
    elif args.command == "replay":
        cmd_replay(args.run_id, args.turn, args.time_limit, mission=args.mission,
                   use_rust=not args.no_rust)
    elif args.command == "auto_turn":
        cmd_auto_turn(profile=args.profile, time_limit=args.time_limit,
                      wait_for_turn=not args.no_wait, max_wait=args.max_wait)
    elif args.command == "auto_mission":
        cmd_auto_mission(profile=args.profile, time_limit=args.time_limit,
                         max_turns=args.max_turns)
    elif args.command == "analyze":
        cmd_analyze(min_samples=args.min_samples)
    elif args.command == "validate":
        cmd_validate(args.old_weights, args.new_weights,
                     time_limit=args.time_limit,
                     solver_version=args.solver_version,
                     failures_only=args.failures_only)
    elif args.command == "tune":
        cmd_tune(iterations=args.iterations, min_boards=args.min_boards,
                 time_limit=args.time_limit,
                 since=args.since, no_cutoff=args.no_cutoff)
    elif args.command == "mission_end":
        cmd_mission_end(args.outcome, notes=args.notes)
    elif args.command == "annotate":
        cmd_annotate(args.run_id, args.turn, args.notes, mission=args.mission)


if __name__ == "__main__":
    main()
