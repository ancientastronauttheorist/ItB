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

  python game_loop.py new_run [squad] [--achieve X Y]  # Start new run
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


def _configure_output_encoding() -> None:
    """Keep CLI progress output printable under Windows cp1252 consoles."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


_configure_output_encoding()

from src.loop.commands import (
    cmd_read,
    cmd_solve,
    cmd_execute,
    cmd_verify,
    cmd_verify_action,
    cmd_diagnose,
    cmd_diagnose_apply_agent,
    cmd_diagnose_next,
    cmd_diagnose_queue,
    cmd_apply_diagnosis,
    cmd_reject_diagnosis,
    cmd_click_action,
    cmd_click_end_turn,
    cmd_click_balanced_roll,
    cmd_deploy_recommended,
    cmd_recommend_squad,
    cmd_recommend_mission,
    cmd_bridge_speed,
    cmd_lightning_preflight,
    cmd_lightning_ui,
    cmd_lightning_route_start,
    cmd_lightning_capture,
    cmd_lightning_mark,
    cmd_lightning_peek,
    cmd_lightning_map_regions,
    cmd_lightning_pause_guard,
    cmd_lightning_attempt,
    cmd_lightning_segment,
    cmd_lightning_start_run,
    cmd_lightning_loop,
    cmd_verify_setup_screen,
    cmd_research_attach_community,
    cmd_research_next,
    cmd_research_probe_mech,
    cmd_research_peek,
    cmd_research_resolve,
    cmd_research_submit,
    cmd_resolve_post_enemy_block,
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
from src.loop.lightning_conductor import cmd_lightning_autonomous


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
    p_solve.add_argument("--beam", type=int, default=0, choices=[0, 1, 2],
                         help="Beam depth. 0 (default) = single-turn top-1. "
                              "2 = depth-2 beam (solve_beam, K=5); picks the "
                              "plan whose chain_score (turn-1 + best turn-2) "
                              "is highest. 1 = depth-1 beam (skip the "
                              "clean-plan filter). Does not affect auto_turn.")
    p_solve.add_argument("--candidate-rank", type=int, default=None,
                         help="Select an exact solve_top_k candidate rank "
                              "after reviewing dirty frontier tradeoffs.")

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
    p_verify_action.add_argument(
        "--diagnose", action="store_true",
        help="On desync, append the failure to session.diagnosis_queue. "
             "The harness drains the queue between turns via "
             "`diagnose_next`. Also enabled by ITB_AUTO_DIAGNOSE=1."
    )

    # diagnose
    p_diagnose = sub.add_parser(
        "diagnose",
        help="Layer 2 of the diagnosis loop: rules + agent fallback prompt",
    )
    p_diagnose.add_argument("failure_id",
                            help="Failure_db.jsonl entry id (printed by verify_action)")
    p_diagnose.add_argument("--force", action="store_true",
                            help="Ignore the rejections + known_gaps suppression "
                                 "and run rule matching anyway")
    p_diagnose.add_argument("--out", default=None,
                            help="Override the markdown output directory "
                                 "(default: recordings/<run_id>/diagnoses/)")

    # diagnose_apply_agent
    p_dag = sub.add_parser(
        "diagnose_apply_agent",
        help="Submit an Explore-agent JSON response back into the diagnosis loop",
    )
    p_dag.add_argument("failure_id",
                       help="Failure_db.jsonl entry id (must match diagnose's)")
    p_dag.add_argument("payload",
                       help="Agent's JSON response — raw string OR path to a file")
    p_dag.add_argument("--out", default=None,
                       help="Override the markdown output directory")

    # reject_diagnosis
    p_rej = sub.add_parser(
        "reject_diagnosis",
        help="Mark a diagnosis proposal wrong so the same diff doesn't re-fire",
    )
    p_rej.add_argument("failure_id",
                       help="Failure_db.jsonl entry id")
    p_rej.add_argument("--reason", required=True,
                       help="One-line explanation of why the proposal was wrong")
    p_rej.add_argument("--out", default=None,
                       help="Override the markdown output directory")

    # diagnose_next
    p_dn = sub.add_parser(
        "diagnose_next",
        help="Drain the next pending entry from session.diagnosis_queue (Layer 3)",
    )
    p_dn.add_argument("--force", action="store_true",
                      help="Pass --force through to diagnose (skip rejections + known_gaps)")

    # diagnose_queue
    p_dq = sub.add_parser(
        "diagnose_queue",
        help="List session.diagnosis_queue entries",
    )
    p_dq.add_argument("--show", default="pending",
                      choices=["pending", "done", "failed", "all"],
                      help="Filter by status (default: pending)")

    # apply_diagnosis
    p_ad = sub.add_parser(
        "apply_diagnosis",
        help="Layer 4: apply an agent_proposed diagnosis to the codebase",
    )
    p_ad.add_argument("failure_id",
                      help="Failure_db.jsonl entry id (must have status=agent_proposed)")
    p_ad.add_argument("--dry-run", action="store_true",
                      help="Print the apply plan and exit without touching files")
    p_ad.add_argument("--skip-build", action="store_true",
                      help="Skip the maturin rebuild (use only when no Rust files changed)")
    p_ad.add_argument("--skip-regression", action="store_true",
                      help="Skip scripts/regression.sh — dangerous; you must run it before commit")

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

    # research_peek
    p_research_peek = sub.add_parser(
        "research_peek",
        help="Read-only view of the current research queue head",
    )
    p_research_peek.add_argument("--limit", type=int, default=5)

    # research_resolve
    p_research_resolve = sub.add_parser(
        "research_resolve",
        help="Mark stale research queue entries for a known target as done",
    )
    p_research_resolve.add_argument("target",
                                    help="Known type/terrain/weapon to resolve")
    p_research_resolve.add_argument("--profile", default="Alpha")
    p_research_resolve.add_argument("--kind", default=None,
                                    help="Optional queue kind filter")
    p_research_resolve.add_argument(
        "--reason",
        default="manual_resolved_known_type",
        help="Reason stored on the queue entry result",
    )

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

    # research_attach_community
    p_research_attach = sub.add_parser(
        "research_attach_community",
        help="Attach harness-supplied Steam forum + Reddit notes to a research record",
    )
    p_research_attach.add_argument(
        "research_id",
        help="ID returned by research_next / research_submit",
    )
    p_research_attach.add_argument(
        "notes_json",
        help="JSON dict keyed by source (steam_forum/reddit) with "
             "{url, excerpt, confidence} values. See community_fetch.normalize_notes.",
    )
    p_research_attach.add_argument("--profile", default="Alpha")

    # resolve_post_enemy_block
    p_resolve_post = sub.add_parser(
        "resolve_post_enemy_block",
        help="Clear an unresolved post-enemy investigation after review",
    )
    p_resolve_post.add_argument(
        "--reason",
        required=True,
        help="What was investigated/fixed; stored in the decision log",
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

    # click_balanced_roll
    sub.add_parser(
        "click_balanced_roll",
        help="Plan a click for Balanced Roll on squad-select",
    )

    # recommend_squad
    p_rec_squad = sub.add_parser(
        "recommend_squad",
        help="Recommend a squad/setup for achievement hunt vs solver eval",
    )
    p_rec_squad.add_argument(
        "squad",
        nargs="?",
        default=None,
        help="Optional explicit squad name, or 'auto' for strategy selection",
    )
    p_rec_squad.add_argument("--achieve", nargs="*", default=[],
                             help="Achievement targets")
    p_rec_squad.add_argument(
        "--mode",
        choices=["achievement_hunt", "solver_eval", "random_squad", "custom"],
        default=None,
        help="Run setup mode. Defaults from tags/targets.",
    )
    p_rec_squad.add_argument("--tags", nargs="*", default=[],
                             help="Run classification tags")

    p_deploy_recommended = sub.add_parser(
        "deploy_recommended",
        help="Deploy mechs to ranked deployment tiles via bridge",
    )
    p_deploy_recommended.add_argument("--profile", default="Alpha")

    # recommend_mission
    p_rec_mission = sub.add_parser(
        "recommend_mission",
        help="Score available missions on the current island, top 3 ranked.",
    )
    p_rec_mission.add_argument("--profile", default="Alpha")
    p_rec_mission.add_argument(
        "--island-map-json",
        default=None,
        help="Optional path to a JSON file containing {island_map, units, "
             "grid_power} (or a bare island_map list). When the bridge "
             "isn't on the corp map screen, use this to score offline.",
    )
    p_rec_mission.add_argument(
        "--routing",
        choices=["default", "lightning_war"],
        default="default",
        help="Mission routing profile. lightning_war favors fast Blitzkrieg "
             "missions over reputation.",
    )
    p_rec_mission.add_argument(
        "--no-save-region-filter",
        dest="use_save_region_filter",
        action="store_false",
        help="Do not reconcile bridge island_map entries with saveData regions",
    )
    p_rec_mission.add_argument(
        "--pause-map-peek",
        action="store_true",
        help="Briefly resume from pause to read bridge island_map, then pause",
    )
    p_rec_mission.set_defaults(use_save_region_filter=True)

    # bridge_speed
    p_bridge_speed = sub.add_parser(
        "bridge_speed",
        help="Set Lua bridge execution speed mode",
    )
    p_bridge_speed.add_argument(
        "mode",
        nargs="?",
        choices=["fast", "visual"],
        default="fast",
    )

    # lightning_preflight
    p_lightning_preflight = sub.add_parser(
        "lightning_preflight",
        help="Check Lightning War speed-run blockers before starting",
    )
    p_lightning_preflight.add_argument("--profile", default="Alpha")
    p_lightning_preflight.add_argument(
        "--set-bridge-fast",
        action="store_true",
        help="Also request fast mode from the Lua bridge if it is active",
    )
    p_lightning_preflight.add_argument(
        "--advanced-content",
        choices=["on", "off", "any"],
        default="any",
        help="Require the saved Advanced Content settings to match this state",
    )

    # lightning_ui
    p_lightning_ui = sub.add_parser(
        "lightning_ui",
        help="Click a calibrated Lightning War hot-path UI button",
    )
    p_lightning_ui.add_argument(
        "control",
        nargs="?",
        default=None,
        help="Known control name, such as pause, menu_continue, "
             "reward_continue, deploy_confirm, modal_understood, "
             "panel_continue, or end_turn. Special controls include "
             "ensure_pause, handle_screen, and named bursts. Use comma or + "
             "for a fast sequence.",
    )
    p_lightning_ui.add_argument("--dry-run", action="store_true")
    p_lightning_ui.add_argument("--list", action="store_true",
                                help="List calibrated controls")

    # lightning_pause_guard
    p_lightning_pause_guard = sub.add_parser(
        "lightning_pause_guard",
        help="Watch safe Lightning War UI states and click Pause when useful",
    )
    p_lightning_pause_guard.add_argument("--profile", default="Alpha")
    p_lightning_pause_guard.add_argument("--seconds", type=float, default=5.0)
    p_lightning_pause_guard.add_argument("--interval", type=float, default=0.25)
    p_lightning_pause_guard.add_argument(
        "--sample-seconds",
        type=float,
        default=0.25,
        help="Timer-growth probe duration when --require-timer-growth is used",
    )
    p_lightning_pause_guard.add_argument(
        "--require-timer-growth",
        action="store_true",
        help="Only click Pause after save/profile current.time advances",
    )
    p_lightning_pause_guard.add_argument("--dry-run", action="store_true")
    p_lightning_pause_guard.add_argument("--no-click", action="store_true")
    p_lightning_pause_guard.add_argument(
        "--once",
        action="store_true",
        help="Poll once instead of watching for the full duration",
    )

    # lightning_route_start
    p_lightning_route_start = sub.add_parser(
        "lightning_route_start",
        help="Preflight and start a selected map region in one Lightning burst",
    )
    p_lightning_route_start.add_argument("--profile", default="Alpha")
    p_lightning_route_start.add_argument("--window-x", type=int, default=None)
    p_lightning_route_start.add_argument("--window-y", type=int, default=None)
    p_lightning_route_start.add_argument(
        "--visual-region-index",
        type=int,
        default=None,
        help=(
            "Use a detected red-region index from lightning_route_start "
            "or lightning_attempt output instead of raw window coordinates"
        ),
    )
    p_lightning_route_start.add_argument("--start-window-x", type=int, default=None)
    p_lightning_route_start.add_argument("--start-window-y", type=int, default=None)
    p_lightning_route_start.add_argument(
        "--no-preflight",
        dest="run_preflight",
        action="store_false",
        help="Skip the preflight guard before clicking live UI",
    )
    p_lightning_route_start.add_argument(
        "--no-route-check",
        dest="verify_route",
        action="store_false",
        help="Skip recommend_mission before clicking the supplied region",
    )
    p_lightning_route_start.add_argument(
        "--no-save-region-filter",
        dest="use_save_region_filter",
        action="store_false",
        help="Do not reconcile bridge island_map entries with saveData regions",
    )
    p_lightning_route_start.add_argument(
        "--no-pause-map-peek",
        dest="allow_pause_map_peek",
        action="store_false",
        help="Do not briefly resume from pause to read bridge island_map",
    )
    p_lightning_route_start.add_argument(
        "--no-auto-pause",
        dest="auto_pause_if_needed",
        action="store_false",
        help="Do not click pause first when the map is visibly unpaused",
    )
    p_lightning_route_start.add_argument(
        "--preview-only",
        dest="include_start_click",
        action="store_false",
        help="Click only the region preview, not the mission preview board",
    )
    p_lightning_route_start.add_argument(
        "--expected-mission-id",
        dest="expected_route_mission_id",
        default=None,
        help=(
            "Before clicking Start Mission, require the opened preview to "
            "expose this bridge mission id"
        ),
    )
    p_lightning_route_start.add_argument(
        "--dismiss-dialogue",
        action="store_true",
        help="Dismiss an advisor dialogue before clicking the mission preview",
    )
    p_lightning_route_start.add_argument(
        "--start-mode",
        choices=[
            "preview-board",
            "preview-board-twice",
            "visible-text",
            "region-repeat",
            "dialogue-region-repeat-preview-board",
            "dialogue-region-repeat-preview-board-twice",
        ],
        default="dialogue-region-repeat-preview-board",
        help=(
            "How to commit the selected preview when no manual start point is "
            "supplied. Default clicks the calibrated mission preview board."
        ),
    )
    p_lightning_route_start.add_argument("--dry-run", action="store_true")
    p_lightning_route_start.set_defaults(
        run_preflight=True,
        verify_route=True,
        use_save_region_filter=True,
        allow_pause_map_peek=True,
        auto_pause_if_needed=True,
        include_start_click=True,
    )

    # lightning_capture
    p_lightning_capture = sub.add_parser(
        "lightning_capture",
        help="Capture the game window and append a Lightning War timing note",
    )
    p_lightning_capture.add_argument("label", help="Short screenshot label")
    p_lightning_capture.add_argument("--note", default="")
    p_lightning_capture.add_argument("--game-timer", default=None)
    p_lightning_capture.add_argument(
        "--clock-state",
        default="unknown",
        choices=["ticks", "paused", "unknown", "safe", "unsafe"],
    )
    p_lightning_capture.add_argument("--out-dir", default=None)
    p_lightning_capture.add_argument("--dry-run", action="store_true")

    # lightning_mark
    p_lightning_mark = sub.add_parser(
        "lightning_mark",
        help="Record a structured Lightning War timing event with deltas",
    )
    p_lightning_mark.add_argument("label", help="Short timing event label")
    p_lightning_mark.add_argument("--game-timer", default=None)
    p_lightning_mark.add_argument("--state", default=None)
    p_lightning_mark.add_argument("--note", default="")
    p_lightning_mark.add_argument("--out-dir", default=None)
    p_lightning_mark.add_argument(
        "--screenshot-path",
        default=None,
        help="Attach/copy an existing screenshot instead of capturing a new one",
    )
    p_lightning_mark.add_argument("--dry-run", action="store_true")

    # lightning_peek
    p_lightning_peek = sub.add_parser(
        "lightning_peek",
        help="Briefly unpause, screenshot, and return to pause for Lightning War",
    )
    p_lightning_peek.add_argument("label", nargs="?", default="peek")
    p_lightning_peek.add_argument("--note", default="")
    p_lightning_peek.add_argument("--game-timer", default=None)
    p_lightning_peek.add_argument("--out-dir", default=None)
    p_lightning_peek.add_argument("--dry-run", action="store_true")
    p_lightning_peek.add_argument("--settle-seconds", type=float, default=0.05)
    p_lightning_peek.add_argument("--pause-settle-seconds", type=float, default=0.08)
    p_lightning_peek.add_argument("--hold-seconds", type=float, default=0.06)
    p_lightning_peek.add_argument("--capture-timeout", type=float, default=2.0)
    p_lightning_peek.add_argument(
        "--allow-live-start",
        dest="require_paused",
        action="store_false",
        help="Allow capture from a non-paused screen, then try to pause",
    )
    p_lightning_peek.set_defaults(require_paused=True)

    # lightning_map_regions
    p_lightning_map_regions = sub.add_parser(
        "lightning_map_regions",
        help="Extract clickable red island-map regions from a screenshot",
    )
    p_lightning_map_regions.add_argument(
        "--screenshot-path",
        default=None,
        help="Analyze an existing screenshot, usually from lightning_peek",
    )
    p_lightning_map_regions.add_argument("--out-dir", default=None)
    p_lightning_map_regions.add_argument("--profile", default="Alpha")
    p_lightning_map_regions.add_argument(
        "--start-mode",
        choices=[
            "preview-board",
            "preview-board-twice",
            "visible-text",
            "region-repeat",
            "dialogue-region-repeat-preview-board",
            "dialogue-region-repeat-preview-board-twice",
        ],
        default="dialogue-region-repeat-preview-board",
        help="Start sequence to place in emitted route candidate commands",
    )
    p_lightning_map_regions.add_argument(
        "--no-save-route-plan",
        dest="use_save_route_plan",
        action="store_false",
        help="Do not rank detected red regions with the current saveData slate",
    )
    p_lightning_map_regions.add_argument(
        "--target-name",
        default=None,
        help="Optional save-region/visible district name to attach to candidates",
    )
    p_lightning_map_regions.add_argument(
        "--target-mission-id",
        default=None,
        help="Optional mission id to attach to candidates",
    )
    p_lightning_map_regions.add_argument(
        "--target-region-id",
        type=int,
        default=None,
        help="Optional bridge/save region id to attach to candidates",
    )
    p_lightning_map_regions.add_argument("--dry-run", action="store_true")
    p_lightning_map_regions.set_defaults(use_save_route_plan=True)

    # verify_setup
    p_verify_setup = sub.add_parser(
        "verify_setup",
        help="Verify new-run difficulty and Advanced Content toggles on screen",
    )
    p_verify_setup.add_argument("--difficulty", type=int, default=0)
    p_verify_setup.add_argument(
        "--advanced-content",
        choices=["on", "off", "any"],
        default=None,
        help="Require the visible Advanced Content rows to be on, off, or just present",
    )
    p_verify_setup.add_argument(
        "--allow-partial-advanced",
        action="store_true",
        help="Do not fail when some Advanced Content rows appear disabled",
    )

    # end_turn
    sub.add_parser("end_turn", help="Plan clicks for End Turn")

    # status
    p_status = sub.add_parser("status", help="Quick state summary")
    p_status.add_argument("--profile", default="Alpha")

    # new_run
    p_new = sub.add_parser("new_run", help="Initialize a new run session")
    p_new.add_argument(
        "squad",
        nargs="?",
        default=None,
        help="Squad name, or omit/use 'auto' to pick for achievement hunting",
    )
    p_new.add_argument("--achieve", nargs="*", default=[],
                       help="Achievement targets")
    p_new.add_argument("--difficulty", type=int, default=0)
    p_new.add_argument(
        "--mode",
        choices=["achievement_hunt", "solver_eval", "random_squad", "custom"],
        default=None,
        help="Run setup mode. Use solver_eval to keep Balanced Roll.",
    )
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
    p_achievements = sub.add_parser(
        "achievements",
        help="Query Steam for achievement progress",
    )
    p_achievements.add_argument(
        "--sync",
        action="store_true",
        help="Update data/achievements_detailed.json from Steam results",
    )

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
    p_auto_turn.add_argument("--max-wait", type=float, default=45.0,
                             help="Seconds to poll enemy→player transition "
                                  "(default: 45 — covers Hard-difficulty enemy animations)")
    p_auto_turn.add_argument("--allow-dirty-plan", action="store_true",
                             help="Override Solver 2.0 safety block and execute "
                                  "a plan that predicts grid/building loss")
    p_auto_turn.add_argument("--candidate-rank", type=int, default=None,
                             help="Execute an exact solve_top_k candidate rank "
                                  "after explicit dirty-line consent")
    p_auto_turn.add_argument("--dirty-consent-id", default=None,
                             help="Exact one-use token emitted by a safety block")
    p_auto_turn.add_argument("--allow-protected-objective-loss", action="store_true",
                             help="Stress-test escape hatch: with exact dirty consent, "
                                  "allow protected objective unit loss")
    p_auto_turn.add_argument("--allow-objective-loss", action="store_true",
                             help="Stress-test escape hatch: with exact dirty consent, "
                                  "allow objective loss/failure kinds")
    p_auto_turn.add_argument(
        "--pause-between-actions",
        action="store_true",
        help=(
            "Lightning-speed mode: pause after each bridge sub-action before "
            "verification reads, then resume for the next game command"
        ),
    )

    # auto_mission
    p_auto_mission = sub.add_parser("auto_mission",
                                    help="Execute a full mission via bridge")
    p_auto_mission.add_argument("--profile", default="Alpha")
    p_auto_mission.add_argument("--time-limit", type=float, default=10.0,
                                help="Solver time limit per turn (default: 10s)")
    p_auto_mission.add_argument("--max-turns", type=int, default=20,
                                help="Safety limit on turns (default: 20)")

    # lightning_loop
    p_lightning_loop = sub.add_parser(
        "lightning_loop",
        help="Lightning War combat loop: auto_turn + local End Turn clicks",
    )
    p_lightning_loop.add_argument("--profile", default="Alpha")
    p_lightning_loop.add_argument("--time-limit", type=float, default=2.0,
                                  help="Solver time limit per turn (default: 2s)")
    p_lightning_loop.add_argument("--max-turns", type=int, default=6,
                                  help="Safety limit on chained turns (default: 6)")
    p_lightning_loop.add_argument("--max-wait", type=float, default=45.0,
                                  help="Enemy/player transition wait (default: 45s)")
    p_lightning_loop.add_argument("--no-click", action="store_true",
                                  help="Stop after the first End Turn plan instead "
                                       "of clicking locally")
    p_lightning_loop.add_argument("--no-bridge-fast", action="store_true",
                                  help="Do not request bridge fast mode at start")
    p_lightning_loop.add_argument("--allow-hold-the-line", action="store_true",
                                  help="Bypass the Hold the Line target guard")
    p_lightning_loop.add_argument(
        "--quiet",
        action="store_true",
        help="Capture nested command stdout instead of printing during the live loop",
    )
    p_lightning_loop.add_argument(
        "--allow-dirty-plan",
        action="store_true",
        help="Pass exact reviewed dirty-plan consent to the first loop turn",
    )
    p_lightning_loop.add_argument(
        "--candidate-rank",
        type=int,
        default=None,
        help="Execute an exact solve_top_k candidate rank on the consented first turn",
    )
    p_lightning_loop.add_argument(
        "--dirty-consent-id",
        default=None,
        help="Exact one-use token emitted by a safety block",
    )
    p_lightning_loop.add_argument(
        "--allow-protected-objective-loss",
        action="store_true",
        help="With exact dirty consent, allow protected objective unit loss",
    )
    p_lightning_loop.add_argument(
        "--allow-objective-loss",
        action="store_true",
        help="With exact dirty consent, allow objective loss/failure kinds",
    )
    p_lightning_loop.add_argument(
        "--speed-loss-policy",
        action="store_true",
        help="Lightning War only: allow nonlethal speed losses and optional objective failures",
    )
    p_lightning_loop.add_argument(
        "--pause-before-solve",
        action="store_true",
        help="Pause as soon as each player turn is ready, then solve/execute while paused",
    )
    p_lightning_loop.add_argument(
        "--no-pause-between-actions",
        dest="pause_between_actions",
        action="store_false",
        help="Do not pause between combat sub-actions and verification reads",
    )
    p_lightning_loop.add_argument(
        "--pause-between-actions",
        dest="pause_between_actions",
        action="store_true",
        help="Pause between combat sub-actions and verification reads",
    )
    p_lightning_loop.set_defaults(pause_before_solve=True)
    p_lightning_loop.set_defaults(pause_between_actions=False)

    # lightning_attempt
    p_lightning_attempt = sub.add_parser(
        "lightning_attempt",
        help="Run the next safe Lightning War deployment/combat automation step",
    )
    p_lightning_attempt.add_argument("--profile", default="Alpha")
    p_lightning_attempt.add_argument("--time-limit", type=float, default=2.0,
                                     help="Solver time limit per turn")
    p_lightning_attempt.add_argument("--max-turns", type=int, default=6)
    p_lightning_attempt.add_argument("--max-wait", type=float, default=45.0)
    p_lightning_attempt.add_argument(
        "--no-click",
        action="store_true",
        help="Do not locally click calibrated UI buttons",
    )
    p_lightning_attempt.add_argument(
        "--no-bridge-fast",
        action="store_true",
        help="Do not request bridge fast mode during preflight",
    )
    p_lightning_attempt.add_argument(
        "--no-preflight",
        action="store_true",
        help="Skip Lightning War preflight checks",
    )
    p_lightning_attempt.add_argument("--dry-run", action="store_true")
    p_lightning_attempt.add_argument(
        "--max-wall-seconds",
        type=float,
        default=None,
        help="Optional conservative wall-clock budget guard",
    )
    p_lightning_attempt.add_argument("--allow-hold-the-line", action="store_true")
    p_lightning_attempt.add_argument(
        "--no-pause-on-stop",
        dest="pause_on_stop",
        action="store_false",
        help="Do not click the pause guard after this conductor step stops",
    )
    p_lightning_attempt.add_argument(
        "--verbose",
        dest="quiet",
        action="store_false",
        help="Print nested preflight/combat/routing command output before pausing",
    )
    p_lightning_attempt.add_argument(
        "--no-resume-if-paused",
        dest="resume_if_paused",
        action="store_false",
        help="Do not click Continue automatically when the pause menu is visible",
    )
    p_lightning_attempt.add_argument(
        "--no-auto-clear-panels",
        dest="auto_clear_panels",
        action="store_false",
        help="Do not auto-click safe Continue-style reward/promotion panels",
    )
    p_lightning_attempt.add_argument(
        "--allow-dirty-plan",
        action="store_true",
        help="Pass exact reviewed dirty-plan consent to the first combat loop turn",
    )
    p_lightning_attempt.add_argument(
        "--candidate-rank",
        type=int,
        default=None,
        help="Execute an exact solve_top_k candidate rank on the consented first turn",
    )
    p_lightning_attempt.add_argument(
        "--dirty-consent-id",
        default=None,
        help="Exact one-use token emitted by a safety block",
    )
    p_lightning_attempt.add_argument(
        "--allow-protected-objective-loss",
        action="store_true",
        help="With exact dirty consent, allow protected objective unit loss",
    )
    p_lightning_attempt.add_argument(
        "--allow-objective-loss",
        action="store_true",
        help="With exact dirty consent, allow objective loss/failure kinds",
    )
    p_lightning_attempt.add_argument(
        "--speed-loss-policy",
        action="store_true",
        help="Lightning War only: allow nonlethal speed losses and optional objective failures",
    )
    p_lightning_attempt.add_argument(
        "--no-pause-before-solve",
        dest="pause_before_solve",
        action="store_false",
        help="Do not pause before combat solves",
    )
    p_lightning_attempt.add_argument(
        "--pause-before-solve",
        dest="pause_before_solve",
        action="store_true",
        help="Pause on each ready player turn before solving/executing",
    )
    p_lightning_attempt.add_argument(
        "--no-pause-between-actions",
        dest="pause_between_actions",
        action="store_false",
        help="Do not pause between combat sub-actions and verification reads",
    )
    p_lightning_attempt.add_argument(
        "--pause-between-actions",
        dest="pause_between_actions",
        action="store_true",
        help="Pause between combat sub-actions and verification reads",
    )
    p_lightning_attempt.set_defaults(pause_on_stop=True)
    p_lightning_attempt.set_defaults(quiet=True)
    p_lightning_attempt.set_defaults(resume_if_paused=True)
    p_lightning_attempt.set_defaults(auto_clear_panels=True)
    p_lightning_attempt.set_defaults(pause_before_solve=True)
    p_lightning_attempt.set_defaults(pause_between_actions=False)

    # lightning_segment
    p_lightning_segment = sub.add_parser(
        "lightning_segment",
        help="Run repeated Lightning War conductor bursts to the next decision",
    )
    p_lightning_segment.add_argument("--profile", default="Alpha")
    p_lightning_segment.add_argument("--time-limit", type=float, default=2.0)
    p_lightning_segment.add_argument("--max-steps", type=int, default=8)
    p_lightning_segment.add_argument("--max-turns", type=int, default=6)
    p_lightning_segment.add_argument("--max-wait", type=float, default=45.0)
    p_lightning_segment.add_argument("--settle-seconds", type=float, default=0.25)
    p_lightning_segment.add_argument("--no-click", action="store_true")
    p_lightning_segment.add_argument("--no-bridge-fast", action="store_true")
    p_lightning_segment.add_argument("--no-preflight", action="store_true")
    p_lightning_segment.add_argument("--dry-run", action="store_true")
    p_lightning_segment.add_argument("--max-wall-seconds", type=float, default=None)
    p_lightning_segment.add_argument("--allow-hold-the-line", action="store_true")
    p_lightning_segment.add_argument(
        "--no-pause-on-stop",
        dest="pause_on_stop",
        action="store_false",
        help="Do not click the pause guard after the segment stops",
    )
    p_lightning_segment.add_argument(
        "--verbose",
        dest="quiet",
        action="store_false",
        help="Print nested conductor output instead of capturing it",
    )
    p_lightning_segment.add_argument(
        "--no-resume-if-paused",
        dest="resume_if_paused",
        action="store_false",
    )
    p_lightning_segment.add_argument(
        "--no-auto-clear-panels",
        dest="auto_clear_panels",
        action="store_false",
    )
    p_lightning_segment.add_argument("--allow-dirty-plan", action="store_true")
    p_lightning_segment.add_argument("--candidate-rank", type=int, default=None)
    p_lightning_segment.add_argument("--dirty-consent-id", default=None)
    p_lightning_segment.add_argument(
        "--allow-protected-objective-loss",
        action="store_true",
    )
    p_lightning_segment.add_argument("--allow-objective-loss", action="store_true")
    p_lightning_segment.add_argument(
        "--no-speed-loss-policy",
        dest="lightning_speed_loss_policy",
        action="store_false",
        help="Disable Lightning War speed-loss allowance for this segment",
    )
    p_lightning_segment.add_argument(
        "--no-pause-before-solve",
        dest="pause_before_solve",
        action="store_false",
        help="Do not pause before combat solves",
    )
    p_lightning_segment.add_argument(
        "--pause-before-solve",
        dest="pause_before_solve",
        action="store_true",
        help="Pause on each ready player turn before solving/executing",
    )
    p_lightning_segment.add_argument(
        "--no-pause-between-actions",
        dest="pause_between_actions",
        action="store_false",
        help="Do not pause between combat sub-actions and verification reads",
    )
    p_lightning_segment.add_argument(
        "--pause-between-actions",
        dest="pause_between_actions",
        action="store_true",
        help="Pause between combat sub-actions and verification reads",
    )
    p_lightning_segment.add_argument(
        "--route-visual-region-index",
        type=int,
        default=None,
        help=(
            "When the segment reaches a route-ready map, start the detected "
            "red-region index before continuing into deployment/combat"
        ),
    )
    p_lightning_segment.add_argument(
        "--route-target-mission-id",
        default=None,
        help=(
            "Expected mission id for --route-visual-region-index; deployment "
            "blocks if the live mission differs"
        ),
    )
    p_lightning_segment.add_argument(
        "--route-auto-start",
        action="store_true",
        help=(
            "At route-ready maps, automatically start the save-ranked primary "
            "red-region candidate when its Lightning score is high enough"
        ),
    )
    p_lightning_segment.add_argument(
        "--route-start-mode",
        choices=[
            "preview-board",
            "preview-board-twice",
            "visible-text",
            "region-repeat",
            "dialogue-region-repeat-preview-board",
            "dialogue-region-repeat-preview-board-twice",
        ],
        default="dialogue-region-repeat-preview-board",
        help="Start sequence to use with --route-visual-region-index",
    )
    p_lightning_segment.set_defaults(pause_on_stop=True)
    p_lightning_segment.set_defaults(quiet=True)
    p_lightning_segment.set_defaults(resume_if_paused=True)
    p_lightning_segment.set_defaults(auto_clear_panels=True)
    p_lightning_segment.set_defaults(lightning_speed_loss_policy=True)
    p_lightning_segment.set_defaults(pause_before_solve=True)
    p_lightning_segment.set_defaults(pause_between_actions=False)

    # lightning_start_run
    p_lightning_start = sub.add_parser(
        "lightning_start_run",
        help=(
            "Verify setup, click final Start, select the first island, "
            "pause, and hand off to the Lightning War segment conductor"
        ),
    )
    p_lightning_start.add_argument("--profile", default="Alpha")
    p_lightning_start.add_argument("--difficulty", type=int, default=0)
    p_lightning_start.add_argument(
        "--advanced-content",
        choices=["on", "off", "any"],
        default="on",
    )
    p_lightning_start.add_argument(
        "--first-island",
        default="archive",
        choices=["archive", "rst", "r.s.t.", "pinnacle", "detritus"],
    )
    p_lightning_start.add_argument("--time-limit", type=float, default=2.0)
    p_lightning_start.add_argument("--max-steps", type=int, default=8)
    p_lightning_start.add_argument("--max-turns", type=int, default=6)
    p_lightning_start.add_argument("--max-wait", type=float, default=45.0)
    p_lightning_start.add_argument("--max-wall-seconds", type=float, default=None)
    p_lightning_start.add_argument(
        "--no-route-auto-start",
        dest="route_auto_start",
        action="store_false",
        help="Stop at the first route-ready map instead of auto-starting it",
    )
    p_lightning_start.add_argument(
        "--no-segment",
        dest="run_segment",
        action="store_false",
        help="Stop after selecting the first island and verifying pause",
    )
    p_lightning_start.add_argument(
        "--no-allow-objective-loss",
        dest="allow_objective_loss",
        action="store_false",
        help="Disable Lightning War optional-objective speed losses",
    )
    p_lightning_start.add_argument("--dry-run", action="store_true")
    p_lightning_start.set_defaults(
        route_auto_start=True,
        run_segment=True,
        allow_objective_loss=True,
    )

    # lightning_autonomous
    p_lightning_auto = sub.add_parser(
        "lightning_autonomous",
        help="Run telemetry-backed autonomous Lightning War attempts",
    )
    p_lightning_auto.add_argument("--profile", default="Alpha")
    p_lightning_auto.add_argument("--achievement", default="Lightning War")
    p_lightning_auto.add_argument("--advanced-content", choices=["on", "off", "any"], default="off")
    p_lightning_auto.add_argument("--difficulty", type=int, default=0)
    p_lightning_auto.add_argument("--first-island", choices=["archive", "rst", "pinnacle", "detritus"], default="archive")
    p_lightning_auto.add_argument("--max-attempts", type=int, default=1)
    p_lightning_auto.add_argument("--max-segments", type=int, default=20)
    p_lightning_auto.add_argument("--segment-steps", type=int, default=12)
    p_lightning_auto.add_argument("--time-limit", type=float, default=2.0)
    p_lightning_auto.add_argument("--max-wall-seconds", type=float, default=None)
    p_lightning_auto.add_argument("--segment-timeout", type=float, default=420.0)
    p_lightning_auto.add_argument("--abandon-seconds", type=float, default=29 * 60)
    p_lightning_auto.add_argument("--first-island-gate-seconds", type=float, default=15 * 60)
    p_lightning_auto.add_argument("--second-island-start-gate-seconds", type=float, default=16.75 * 60)
    p_lightning_auto.add_argument("--screenshot-cadence", type=float, default=2.0)
    p_lightning_auto.add_argument("--no-screenshots", action="store_true")
    p_lightning_auto.add_argument("--route-auto-start", action="store_true")
    p_lightning_auto.add_argument("--start-from-verified-setup", action="store_true")
    p_lightning_auto.add_argument("--no-achievement-sync", action="store_true")
    p_lightning_auto.add_argument("--dry-run", action="store_true")

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
    p_tune.add_argument("--accept-version-change", action="store_true",
                        help="Allow tuning when failure_db spans "
                             "multiple simulator_version values. "
                             "Only use after archiving the old corpus.")

    p_mission_end = sub.add_parser("mission_end",
                                   help="Record mission outcome (win/loss) on the active run")
    p_mission_end.add_argument("outcome", choices=["win", "loss"],
                               help="Mission result")
    p_mission_end.add_argument("--notes", default=None,
                               help="Optional free-text context")
    p_mission_end.add_argument(
        "--no-commit",
        action="store_true",
        help="Skip the default auto-commit + push of mission artifacts",
    )

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
        cmd_solve(profile=args.profile, time_limit=args.time_limit,
                  beam=args.beam, candidate_rank=args.candidate_rank)
    elif args.command == "execute":
        cmd_execute(args.index, profile=args.profile)
    elif args.command == "verify":
        cmd_verify(args.index, profile=args.profile)
    elif args.command == "verify_action":
        cmd_verify_action(args.index, auto_diagnose=args.diagnose)
    elif args.command == "diagnose":
        cmd_diagnose(args.failure_id, force=args.force, out_path=args.out)
    elif args.command == "diagnose_apply_agent":
        cmd_diagnose_apply_agent(args.failure_id, args.payload, out_path=args.out)
    elif args.command == "diagnose_next":
        cmd_diagnose_next(force=args.force)
    elif args.command == "diagnose_queue":
        cmd_diagnose_queue(show=args.show)
    elif args.command == "apply_diagnosis":
        cmd_apply_diagnosis(args.failure_id,
                            dry_run=args.dry_run,
                            skip_regression=args.skip_regression,
                            skip_build=args.skip_build)
    elif args.command == "reject_diagnosis":
        cmd_reject_diagnosis(args.failure_id, args.reason, out_path=args.out)
    elif args.command == "click_action":
        cmd_click_action(args.index)
    elif args.command == "click_end_turn":
        cmd_click_end_turn()
    elif args.command == "click_balanced_roll":
        cmd_click_balanced_roll()
    elif args.command == "deploy_recommended":
        cmd_deploy_recommended(profile=args.profile)
    elif args.command == "recommend_squad":
        cmd_recommend_squad(
            args.squad,
            args.achieve,
            tags=args.tags,
            mode=args.mode,
        )
    elif args.command == "recommend_mission":
        cmd_recommend_mission(
            profile=args.profile,
            island_map_json=args.island_map_json,
            routing=args.routing,
            use_save_region_filter=args.use_save_region_filter,
            pause_map_peek=args.pause_map_peek,
        )
    elif args.command == "bridge_speed":
        cmd_bridge_speed(args.mode)
    elif args.command == "lightning_preflight":
        cmd_lightning_preflight(
            profile=args.profile,
            set_fast_bridge=args.set_bridge_fast,
            advanced_content=args.advanced_content,
        )
    elif args.command == "lightning_ui":
        cmd_lightning_ui(
            args.control,
            dry_run=args.dry_run,
            list_controls=args.list,
        )
    elif args.command == "lightning_pause_guard":
        cmd_lightning_pause_guard(
            profile=args.profile,
            seconds=args.seconds,
            interval=args.interval,
            sample_seconds=args.sample_seconds,
            require_timer_growth=args.require_timer_growth,
            dry_run=args.dry_run,
            click_ui=not args.no_click,
            once=args.once,
        )
    elif args.command == "lightning_route_start":
        cmd_lightning_route_start(
            profile=args.profile,
            region_window_x=args.window_x,
            region_window_y=args.window_y,
            visual_region_index=args.visual_region_index,
            run_preflight=args.run_preflight,
            verify_route=args.verify_route,
            use_save_region_filter=args.use_save_region_filter,
            allow_pause_map_peek=args.allow_pause_map_peek,
            auto_pause_if_needed=args.auto_pause_if_needed,
            include_start_click=args.include_start_click,
            dismiss_dialogue=args.dismiss_dialogue,
            start_mode=args.start_mode,
            start_window_x=args.start_window_x,
            start_window_y=args.start_window_y,
            expected_route_mission_id=args.expected_route_mission_id,
            dry_run=args.dry_run,
        )
    elif args.command == "lightning_capture":
        cmd_lightning_capture(
            args.label,
            note=args.note,
            game_timer=args.game_timer,
            clock_state=args.clock_state,
            out_dir=args.out_dir,
            dry_run=args.dry_run,
        )
    elif args.command == "lightning_mark":
        cmd_lightning_mark(
            args.label,
            game_timer=args.game_timer,
            state=args.state,
            note=args.note,
            out_dir=args.out_dir,
            screenshot_path=args.screenshot_path,
            dry_run=args.dry_run,
        )
    elif args.command == "lightning_peek":
        cmd_lightning_peek(
            args.label,
            note=args.note,
            game_timer=args.game_timer,
            out_dir=args.out_dir,
            dry_run=args.dry_run,
            settle_seconds=args.settle_seconds,
            pause_settle_seconds=args.pause_settle_seconds,
            hold_seconds=args.hold_seconds,
            capture_timeout=args.capture_timeout,
            require_paused=args.require_paused,
        )
    elif args.command == "lightning_map_regions":
        cmd_lightning_map_regions(
            screenshot_path=args.screenshot_path,
            out_dir=args.out_dir,
            dry_run=args.dry_run,
            start_mode=args.start_mode,
            profile=args.profile,
            use_save_route_plan=args.use_save_route_plan,
            target_name=args.target_name,
            target_mission_id=args.target_mission_id,
            target_region_id=args.target_region_id,
        )
    elif args.command == "verify_setup":
        advanced_content = args.advanced_content
        if advanced_content is None and args.allow_partial_advanced:
            advanced_content = "any"
        cmd_verify_setup_screen(
            expected_difficulty=args.difficulty,
            require_all_advanced=not args.allow_partial_advanced,
            advanced_content=advanced_content,
        )
    elif args.command == "research_next":
        cmd_research_next(profile=args.profile)
    elif args.command == "research_peek":
        cmd_research_peek(limit=args.limit)
    elif args.command == "research_resolve":
        cmd_research_resolve(
            args.target, kind=args.kind, reason=args.reason,
            profile=args.profile,
        )
    elif args.command == "research_submit":
        cmd_research_submit(args.research_id, args.vision_json,
                            profile=args.profile,
                            wiki_fallback=not args.no_wiki)
    elif args.command == "research_probe_mech":
        cmd_research_probe_mech(args.tile, args.slot, profile=args.profile)
    elif args.command == "research_attach_community":
        cmd_research_attach_community(
            args.research_id, args.notes_json, profile=args.profile,
        )
    elif args.command == "resolve_post_enemy_block":
        cmd_resolve_post_enemy_block(args.reason)
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
        cmd_new_run(
            args.squad,
            args.achieve,
            args.difficulty,
            tags=args.tags,
            mode=args.mode,
        )
    elif args.command == "snapshot":
        cmd_snapshot(args.label, profile=args.profile)
    elif args.command == "log":
        cmd_log(" ".join(args.message))
    elif args.command == "calibrate":
        cmd_calibrate()
    elif args.command == "achievements":
        cmd_achievements(sync_local=args.sync)
    elif args.command == "replay":
        cmd_replay(args.run_id, args.turn, args.time_limit, mission=args.mission,
                   use_rust=not args.no_rust)
    elif args.command == "auto_turn":
        cmd_auto_turn(profile=args.profile, time_limit=args.time_limit,
                      wait_for_turn=not args.no_wait, max_wait=args.max_wait,
                      allow_dirty_plan=args.allow_dirty_plan,
                      candidate_rank=args.candidate_rank,
                      dirty_consent_id=args.dirty_consent_id,
                      allow_protected_objective_loss=args.allow_protected_objective_loss,
                      allow_objective_loss=args.allow_objective_loss,
                      pause_between_actions=args.pause_between_actions)
    elif args.command == "auto_mission":
        cmd_auto_mission(profile=args.profile, time_limit=args.time_limit,
                         max_turns=args.max_turns)
    elif args.command == "lightning_loop":
        cmd_lightning_loop(
            profile=args.profile,
            time_limit=args.time_limit,
            max_turns=args.max_turns,
            max_wait=args.max_wait,
            click_end_turn=not args.no_click,
            set_fast_bridge=not args.no_bridge_fast,
            allow_hold_the_line=args.allow_hold_the_line,
            quiet=args.quiet,
            allow_dirty_plan=args.allow_dirty_plan,
            candidate_rank=args.candidate_rank,
            dirty_consent_id=args.dirty_consent_id,
            allow_protected_objective_loss=args.allow_protected_objective_loss,
            allow_objective_loss=args.allow_objective_loss,
            lightning_speed_loss_policy=args.speed_loss_policy,
            pause_before_solve=args.pause_before_solve,
            pause_between_actions=args.pause_between_actions,
        )
    elif args.command == "lightning_attempt":
        cmd_lightning_attempt(
            profile=args.profile,
            time_limit=args.time_limit,
            max_turns=args.max_turns,
            max_wait=args.max_wait,
            click_ui=not args.no_click,
            set_fast_bridge=not args.no_bridge_fast,
            run_preflight=not args.no_preflight,
            dry_run=args.dry_run,
            max_wall_seconds=args.max_wall_seconds,
            allow_hold_the_line=args.allow_hold_the_line,
            pause_on_stop=args.pause_on_stop,
            quiet=args.quiet,
            resume_if_paused=args.resume_if_paused,
            auto_clear_panels=args.auto_clear_panels,
            allow_dirty_plan=args.allow_dirty_plan,
            candidate_rank=args.candidate_rank,
            dirty_consent_id=args.dirty_consent_id,
            allow_protected_objective_loss=args.allow_protected_objective_loss,
            allow_objective_loss=args.allow_objective_loss,
            lightning_speed_loss_policy=args.speed_loss_policy,
            pause_before_solve=args.pause_before_solve,
            pause_between_actions=args.pause_between_actions,
        )
    elif args.command == "lightning_segment":
        cmd_lightning_segment(
            profile=args.profile,
            time_limit=args.time_limit,
            max_steps=args.max_steps,
            max_turns=args.max_turns,
            max_wait=args.max_wait,
            click_ui=not args.no_click,
            set_fast_bridge=not args.no_bridge_fast,
            run_preflight=not args.no_preflight,
            dry_run=args.dry_run,
            max_wall_seconds=args.max_wall_seconds,
            allow_hold_the_line=args.allow_hold_the_line,
            pause_on_stop=args.pause_on_stop,
            quiet=args.quiet,
            resume_if_paused=args.resume_if_paused,
            auto_clear_panels=args.auto_clear_panels,
            allow_dirty_plan=args.allow_dirty_plan,
            candidate_rank=args.candidate_rank,
            dirty_consent_id=args.dirty_consent_id,
            allow_protected_objective_loss=args.allow_protected_objective_loss,
            allow_objective_loss=args.allow_objective_loss,
            lightning_speed_loss_policy=args.lightning_speed_loss_policy,
            pause_before_solve=args.pause_before_solve,
            pause_between_actions=args.pause_between_actions,
            settle_seconds=args.settle_seconds,
            route_visual_region_index=args.route_visual_region_index,
            route_target_mission_id=args.route_target_mission_id,
            route_start_mode=args.route_start_mode,
            route_auto_start=args.route_auto_start,
        )
    elif args.command == "lightning_autonomous":
        cmd_lightning_autonomous(
            profile=args.profile,
            achievement=args.achievement,
            advanced_content=args.advanced_content,
            difficulty=args.difficulty,
            first_island=args.first_island,
            max_attempts=args.max_attempts,
            max_segments=args.max_segments,
            segment_steps=args.segment_steps,
            time_limit=args.time_limit,
            max_wall_seconds=args.max_wall_seconds,
            segment_timeout=args.segment_timeout,
            abandon_seconds=args.abandon_seconds,
            first_island_gate_seconds=args.first_island_gate_seconds,
            second_island_start_gate_seconds=args.second_island_start_gate_seconds,
            screenshot_cadence=args.screenshot_cadence,
            screenshots=not args.no_screenshots,
            route_auto_start=args.route_auto_start,
            start_from_verified_setup=args.start_from_verified_setup,
            achievement_sync=not args.no_achievement_sync,
            dry_run=args.dry_run,
        )
    elif args.command == "lightning_start_run":
        cmd_lightning_start_run(
            profile=args.profile,
            difficulty=args.difficulty,
            advanced_content=args.advanced_content,
            first_island=args.first_island,
            time_limit=args.time_limit,
            max_steps=args.max_steps,
            max_turns=args.max_turns,
            max_wait=args.max_wait,
            max_wall_seconds=args.max_wall_seconds,
            route_auto_start=args.route_auto_start,
            run_segment=args.run_segment,
            allow_objective_loss=args.allow_objective_loss,
            dry_run=args.dry_run,
        )
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
                 since=args.since, no_cutoff=args.no_cutoff,
                 accept_version_change=args.accept_version_change)
    elif args.command == "mission_end":
        cmd_mission_end(args.outcome, notes=args.notes, no_commit=args.no_commit)
    elif args.command == "annotate":
        cmd_annotate(args.run_id, args.turn, args.notes, mission=args.mission)


if __name__ == "__main__":
    main()
