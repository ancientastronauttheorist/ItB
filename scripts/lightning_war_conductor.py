#!/usr/bin/env python
"""Outer conductor for Blitzkrieg Lightning War attempts.

This script deliberately stays thin: it does not duplicate combat solving,
screen classification, route scoring, deployment, or panel handling. It runs
the existing game_loop.py Lightning War commands one at a time and uses their
structured results to decide whether to continue, route-start, sync
achievements, or stop safely.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULT_MARKER = "--- Result ---"
LIGHTNING_WAR = "Lightning War"
SAFE_PAUSE_REASONS = {
    "already_paused",
    "pause_clicked",
    "pause_clicked_timer_stopped",
}
MUST_ACT_REASONS = {
    "visible_ui_is_not_pauseable",
    "deployment_phase",
    "live_combat_phase",
    "pause_not_verified",
    "screen_classification_failed",
}
PROVEN_NON_LIVE_UIS = {
    "title_screen",
    "main_menu",
    "new_game_setup",
    "achievement_popup",
}


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    result: dict[str, Any] | None


@dataclass
class WatchdogState:
    label: str
    status: str
    safe_to_think: bool
    must_act_now: bool
    reason: str
    timer_seconds: float | None = None
    timer: str | None = None
    timer_delta: float | None = None
    visible_ui: str | None = None
    guard_status: str | None = None
    clock_state: str = "ambiguous"


class ConductorJournal:
    """Append compact watchdog evidence for later Lightning War refinement."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, payload: dict[str, Any]) -> None:
        if self.path is None:
            return
        row = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


class TimerWatchdog:
    """Track whether it is safe for the slow outer conductor to think."""

    def __init__(self) -> None:
        self.highest_timer_seconds: float | None = None
        self.samples: list[WatchdogState] = []

    def observe(
        self,
        label: str,
        result: dict[str, Any] | None,
    ) -> WatchdogState:
        timer_seconds, timer = safe_timer(result)
        timer_delta = None
        if timer_seconds is not None:
            if self.highest_timer_seconds is not None:
                timer_delta = timer_seconds - self.highest_timer_seconds
            self.highest_timer_seconds = max(
                self.highest_timer_seconds or timer_seconds,
                timer_seconds,
            )

        guard = guard_payload(result)
        visible_ui = visible_ui_name(guard) or visible_ui_name(result)
        guard_status = str(guard.get("status")) if guard else None
        reason = str(
            (guard.get("reason") if guard else None)
            or (result or {}).get("reason")
            or (result or {}).get("status")
            or "unknown"
        )
        timer_running = timer_probe_running(guard) or timer_probe_running(result)
        if timer_delta is not None and timer_delta > 0.05:
            timer_running = True

        safe = pause_verified(guard) or pause_verified(result)
        if not safe and visible_ui in PROVEN_NON_LIVE_UIS:
            safe = True
        must_act = not safe and (
            timer_running
            or reason in MUST_ACT_REASONS
            or visible_ui == "deployment_screen"
        )
        if safe:
            status = "SAFE_TO_THINK"
            clock_state = "verified_pause_or_non_live"
        elif must_act:
            status = "MUST_ACT_NOW"
            clock_state = "live_or_unpauseable"
        else:
            status = "AMBIGUOUS"
            clock_state = "ambiguous"

        state = WatchdogState(
            label=label,
            status=status,
            safe_to_think=safe,
            must_act_now=must_act,
            reason=reason,
            timer_seconds=timer_seconds,
            timer=timer,
            timer_delta=timer_delta,
            visible_ui=visible_ui,
            guard_status=guard_status,
            clock_state=clock_state,
        )
        self.samples.append(state)
        return state


def extract_result_json(output: str) -> dict[str, Any] | None:
    """Extract the JSON object printed after the game_loop result marker."""
    if not output:
        return None
    if RESULT_MARKER not in output:
        return None
    tail = output.rsplit(RESULT_MARKER, 1)[1].strip()
    if not tail:
        return None
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(tail)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def game_loop_args(args: list[str]) -> list[str]:
    return [sys.executable, str(ROOT / "game_loop.py"), *args]


def run_game_loop(args: list[str], *, timeout: float | None = None) -> CommandResult:
    command = game_loop_args(args)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    result = extract_result_json(completed.stdout)
    return CommandResult(
        args=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        result=result,
    )


def achievement_unlocked(result: dict[str, Any] | None) -> bool:
    if not result:
        return False
    unlocked = result.get("unlocked_list") or []
    return LIGHTNING_WAR in unlocked


def result_status(result: dict[str, Any] | None) -> str:
    if not result:
        return "NO_JSON"
    return str(result.get("status") or result.get("reason") or "UNKNOWN")


def safe_timer(result: dict[str, Any] | None) -> tuple[float | None, str | None]:
    if not result:
        return None, None
    budget = result.get("game_budget") or {}
    seconds = budget.get("game_seconds")
    timer = budget.get("game_timer")
    if seconds is None:
        effective = result.get("effective_timer") or {}
        seconds = effective.get("game_seconds")
        timer = effective.get("game_timer")
    try:
        return float(seconds), str(timer) if timer is not None else None
    except (TypeError, ValueError):
        return None, str(timer) if timer is not None else None


def visible_ui_name(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    visible = payload.get("visible_ui")
    if isinstance(visible, dict):
        name = visible.get("visible_ui")
        return str(name) if name is not None else None
    if isinstance(visible, str):
        return visible
    for key in ("pause_verify", "evidence_ui"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            name = nested.get("visible_ui")
            if name is not None:
                return str(name)
    decision = payload.get("decision")
    if isinstance(decision, dict):
        name = decision.get("visible_ui")
        if name is not None:
            return str(name)
    return None


def guard_payload(result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    guard = result.get("pause_guard")
    if isinstance(guard, dict):
        return guard
    if (
        "pause_verified" in result
        or "timer_stop_verified" in result
        or result.get("reason") in SAFE_PAUSE_REASONS
        or visible_ui_name(result) == "pause_menu"
    ):
        return result
    guard = result.get("guard")
    return guard if isinstance(guard, dict) else {}


def pause_verified(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("pause_verified") is True:
        return True
    if payload.get("timer_stop_verified") is True:
        return True
    if visible_ui_name(payload) == "pause_menu":
        return True
    return (
        payload.get("status") == "OK"
        and payload.get("reason") in SAFE_PAUSE_REASONS
    )


def timer_probe_running(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    for key in ("timer_probe", "stop_probe"):
        probe = payload.get(key)
        if isinstance(probe, dict) and probe.get("running") is True:
            return True
    return False


def normalize_game_loop_command(command: str) -> list[str] | None:
    """Turn a recommended `python3 game_loop.py ...` command into argv."""
    try:
        parts = shlex.split(command, posix=os.name != "nt")
    except ValueError:
        return None
    if len(parts) < 2:
        return None
    exe = Path(parts[0]).name.lower()
    script = Path(parts[1]).name.lower()
    if exe not in {"python", "python3", "py"} or script != "game_loop.py":
        return None
    return parts[2:]


def route_command_from_segment(result: dict[str, Any] | None) -> list[str] | None:
    if not result:
        return None
    for key in ("primary_next_command", "route_start_command", "command"):
        value = result.get(key)
        if isinstance(value, str):
            parsed = normalize_game_loop_command(value)
            if parsed:
                return parsed
    candidates = result.get("route_start_candidates") or []
    if candidates and isinstance(candidates[0], dict):
        value = candidates[0].get("command")
        if isinstance(value, str):
            return normalize_game_loop_command(value)
    return None


def print_command_result(label: str, command: CommandResult) -> None:
    status = result_status(command.result)
    print(f"[{label}] status={status} returncode={command.returncode}")
    if command.result:
        reason = command.result.get("reason")
        next_step = command.result.get("next_step")
        timer_seconds, timer = safe_timer(command.result)
        if timer is not None:
            print(f"[{label}] timer={timer} seconds={timer_seconds}")
        if reason:
            print(f"[{label}] reason={reason}")
        if next_step:
            print(f"[{label}] next_step={next_step}")
    if command.returncode != 0 and command.stderr:
        print(command.stderr.strip())


def print_watchdog_state(state: WatchdogState) -> None:
    print(
        f"[watchdog:{state.label}] {state.status} "
        f"clock={state.clock_state} reason={state.reason}"
    )
    if state.visible_ui:
        print(f"[watchdog:{state.label}] visible_ui={state.visible_ui}")
    if state.timer is not None:
        print(
            f"[watchdog:{state.label}] timer={state.timer} "
            f"delta={state.timer_delta}"
        )


def journal_path(enabled: bool) -> Path | None:
    if not enabled:
        return None
    date = datetime.now().strftime("%Y-%m-%d")
    return ROOT / "run_notes" / f"lightning_war_conductor_{date}.jsonl"


def run_observed(
    label: str,
    args: list[str],
    *,
    watchdog: TimerWatchdog,
    journal: ConductorJournal,
    timeout: float | None = None,
) -> CommandResult:
    command = run_game_loop(args, timeout=timeout)
    print_command_result(label, command)
    state = watchdog.observe(label, command.result)
    print_watchdog_state(state)
    journal.write(
        "command",
        {
            "label": label,
            "args": args,
            "returncode": command.returncode,
            "result_status": result_status(command.result),
            "watchdog": state.__dict__,
        },
    )
    return command


def ensure_pause(
    *,
    watchdog: TimerWatchdog | None = None,
    journal: ConductorJournal | None = None,
) -> CommandResult:
    if watchdog is None or journal is None:
        return run_game_loop(["lightning_ui", "ensure_pause"], timeout=45)
    return run_observed(
        "ensure_pause",
        ["lightning_ui", "ensure_pause"],
        watchdog=watchdog,
        journal=journal,
        timeout=45,
    )


def pause_guard_once(
    *,
    watchdog: TimerWatchdog,
    journal: ConductorJournal,
    timeout: float = 45,
) -> CommandResult:
    return run_observed(
        "pause_guard",
        ["lightning_pause_guard", "--once"],
        watchdog=watchdog,
        journal=journal,
        timeout=timeout,
    )


def guard_status(
    *,
    watchdog: TimerWatchdog | None = None,
    journal: ConductorJournal | None = None,
) -> CommandResult:
    if watchdog is None or journal is None:
        return run_game_loop(["lightning_ui", "guard_status"], timeout=20)
    return run_observed(
        "guard_status",
        ["lightning_ui", "guard_status"],
        watchdog=watchdog,
        journal=journal,
        timeout=20,
    )


def safe_for_slow_step(
    label: str,
    command: CommandResult,
    *,
    watchdog: TimerWatchdog,
    journal: ConductorJournal,
    try_pause: bool = True,
) -> bool:
    state = watchdog.samples[-1] if watchdog.samples else watchdog.observe(label, command.result)
    if state.safe_to_think:
        return True
    if state.must_act_now:
        print(
            f"[{label}] live-clock risk detected; skipping slow work "
            "and continuing deterministic automation."
        )
        return False
    if not try_pause:
        return False
    parked = pause_guard_once(watchdog=watchdog, journal=journal)
    state = watchdog.samples[-1]
    if state.safe_to_think:
        return True
    if not state.must_act_now:
        ensure_pause(watchdog=watchdog, journal=journal)
        return bool(watchdog.samples and watchdog.samples[-1].safe_to_think)
    return False


def run_conductor(args: argparse.Namespace) -> int:
    print("Lightning War conductor starting")
    watchdog = TimerWatchdog()
    journal = ConductorJournal(journal_path(not args.no_journal))

    pause_guard_once(
        watchdog=watchdog,
        journal=journal,
        timeout=args.pause_guard_timeout,
    )
    initial_state = watchdog.samples[-1] if watchdog.samples else None
    initial_safe = bool(initial_state and initial_state.safe_to_think)
    initial_must_act = bool(initial_state and initial_state.must_act_now)

    if initial_safe and not args.no_achievement_sync:
        sync = run_observed(
            "achievements",
            ["achievements", "--sync"],
            watchdog=watchdog,
            journal=journal,
            timeout=120,
        )
        if achievement_unlocked(sync.result):
            print("Lightning War already unlocked.")
            return 0
    elif not args.no_achievement_sync:
        print(
            "[achievements] skipped initial sync because pause/non-live state "
            "was not verified."
        )

    best_timer = 0.0
    if initial_safe:
        preflight = run_observed(
            "preflight",
            ["lightning_preflight"],
            watchdog=watchdog,
            journal=journal,
            timeout=120,
        )
        if preflight.returncode != 0 or result_status(preflight.result) != "PASS":
            ensure_pause(watchdog=watchdog, journal=journal)
            return 2
        best_timer = safe_timer(preflight.result)[0] or 0.0
    else:
        print("[preflight] deferred to lightning_segment hot path.")

    for step in range(1, args.max_segments + 1):
        print(f"[segment {step}] starting")
        segment_args = [
            "lightning_segment",
            "--time-limit",
            str(args.time_limit),
            "--max-wall-seconds",
            str(args.max_wall_seconds),
            "--max-steps",
            str(args.segment_steps),
        ]
        if args.route_auto_start:
            segment_args.append("--route-auto-start")
        if initial_must_act and step == 1:
            segment_args.append("--no-preflight")
        if args.no_pause_before_solve:
            segment_args.append("--no-pause-before-solve")
        if args.no_pause_between_actions:
            segment_args.append("--no-pause-between-actions")

        segment = run_observed(
            f"segment {step}",
            segment_args,
            watchdog=watchdog,
            journal=journal,
            timeout=args.segment_timeout,
        )
        initial_safe = True

        timer_seconds, _ = safe_timer(segment.result)
        if timer_seconds is not None:
            best_timer = max(best_timer, timer_seconds)
        if best_timer >= args.abandon_seconds:
            print(
                f"[segment {step}] budget stop: timer {best_timer:.1f}s "
                f">= abandon threshold {args.abandon_seconds:.1f}s"
            )
            ensure_pause(watchdog=watchdog, journal=journal)
            return 3

        route_args = route_command_from_segment(segment.result)
        safe_now = safe_for_slow_step(
            f"post_segment {step}",
            segment,
            watchdog=watchdog,
            journal=journal,
            try_pause=not bool(route_args),
        )
        if safe_now and not args.no_achievement_sync:
            sync = run_observed(
                f"sync {step}",
                ["achievements", "--sync"],
                watchdog=watchdog,
                journal=journal,
                timeout=120,
            )
            if achievement_unlocked(sync.result):
                print("Lightning War confirmed unlocked.")
                return 0

        if segment.returncode != 0:
            ensure_pause(watchdog=watchdog, journal=journal)
            return 4

        if route_args and not args.route_auto_start:
            print(f"[segment {step}] running recommended route: {route_args}")
            route = run_observed(
                f"route {step}",
                route_args,
                watchdog=watchdog,
                journal=journal,
                timeout=args.segment_timeout,
            )
            if route.returncode != 0:
                ensure_pause(watchdog=watchdog, journal=journal)
                return 5
            continue

        status = result_status(segment.result)
        reason = str((segment.result or {}).get("reason") or "")
        if status in {"PASS", "OK"} or reason in {
            "route_ready",
            "lightning_attempt_route_ready",
            "segment_continue",
        }:
            if safe_now and args.settle_seconds > 0:
                time.sleep(args.settle_seconds)
            continue

        if "ACHIEVEMENT" in status.upper():
            if not safe_now:
                ensure_pause(watchdog=watchdog, journal=journal)
            sync = run_observed(
                "final_sync",
                ["achievements", "--sync"],
                watchdog=watchdog,
                journal=journal,
                timeout=120,
            )
            return 0 if achievement_unlocked(sync.result) else 6

        ensure_pause(watchdog=watchdog, journal=journal)
        guard_status(watchdog=watchdog, journal=journal)
        return 7

    ensure_pause(watchdog=watchdog, journal=journal)
    print("Max segment count reached before achievement confirmation.")
    return 8


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the high-level Lightning War conductor.",
    )
    parser.add_argument("--max-segments", type=int, default=20)
    parser.add_argument("--segment-steps", type=int, default=12)
    parser.add_argument("--time-limit", type=float, default=2.0)
    parser.add_argument("--max-wall-seconds", type=float, default=240.0)
    parser.add_argument("--segment-timeout", type=float, default=420.0)
    parser.add_argument("--settle-seconds", type=float, default=0.5)
    parser.add_argument("--pause-guard-timeout", type=float, default=45.0)
    parser.add_argument(
        "--abandon-seconds",
        type=float,
        default=29 * 60,
        help="Park and stop once the reliable game timer reaches this value.",
    )
    parser.add_argument(
        "--route-auto-start",
        action="store_true",
        help="Let lightning_segment auto-start high-confidence route choices.",
    )
    parser.add_argument("--no-pause-before-solve", action="store_true")
    parser.add_argument("--no-pause-between-actions", action="store_true")
    parser.add_argument("--no-achievement-sync", action="store_true")
    parser.add_argument("--no-journal", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    return run_conductor(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
