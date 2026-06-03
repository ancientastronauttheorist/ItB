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
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULT_MARKER = "--- Result ---"
LIGHTNING_WAR = "Lightning War"


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    result: dict[str, Any] | None


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


def ensure_pause() -> CommandResult:
    return run_game_loop(["lightning_ui", "ensure_pause"], timeout=45)


def guard_status() -> CommandResult:
    return run_game_loop(["lightning_ui", "guard_status"], timeout=20)


def run_conductor(args: argparse.Namespace) -> int:
    print("Lightning War conductor starting")

    sync = run_game_loop(["achievements", "--sync"], timeout=120)
    print_command_result("achievements", sync)
    if achievement_unlocked(sync.result):
        print("Lightning War already unlocked.")
        return 0

    preflight = run_game_loop(["lightning_preflight"], timeout=120)
    print_command_result("preflight", preflight)
    if preflight.returncode != 0 or result_status(preflight.result) != "PASS":
        parked = ensure_pause()
        print_command_result("ensure_pause", parked)
        return 2

    best_timer = safe_timer(preflight.result)[0] or 0.0
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
        if args.no_pause_before_solve:
            segment_args.append("--no-pause-before-solve")
        if args.no_pause_between_actions:
            segment_args.append("--no-pause-between-actions")

        segment = run_game_loop(segment_args, timeout=args.segment_timeout)
        print_command_result(f"segment {step}", segment)

        timer_seconds, _ = safe_timer(segment.result)
        if timer_seconds is not None:
            best_timer = max(best_timer, timer_seconds)
        if best_timer >= args.abandon_seconds:
            print(
                f"[segment {step}] budget stop: timer {best_timer:.1f}s "
                f">= abandon threshold {args.abandon_seconds:.1f}s"
            )
            parked = ensure_pause()
            print_command_result("ensure_pause", parked)
            return 3

        sync = run_game_loop(["achievements", "--sync"], timeout=120)
        print_command_result(f"sync {step}", sync)
        if achievement_unlocked(sync.result):
            print("Lightning War confirmed unlocked.")
            return 0

        if segment.returncode != 0:
            parked = ensure_pause()
            print_command_result("ensure_pause", parked)
            return 4

        route_args = route_command_from_segment(segment.result)
        if route_args and not args.route_auto_start:
            print(f"[segment {step}] running recommended route: {route_args}")
            route = run_game_loop(route_args, timeout=args.segment_timeout)
            print_command_result(f"route {step}", route)
            if route.returncode != 0:
                parked = ensure_pause()
                print_command_result("ensure_pause", parked)
                return 5
            continue

        status = result_status(segment.result)
        reason = str((segment.result or {}).get("reason") or "")
        if status in {"PASS", "OK"} or reason in {
            "route_ready",
            "lightning_attempt_route_ready",
            "segment_continue",
        }:
            time.sleep(args.settle_seconds)
            continue

        if "ACHIEVEMENT" in status.upper():
            sync = run_game_loop(["achievements", "--sync"], timeout=120)
            print_command_result("final_sync", sync)
            return 0 if achievement_unlocked(sync.result) else 6

        parked = ensure_pause()
        print_command_result("ensure_pause", parked)
        guard = guard_status()
        print_command_result("guard_status", guard)
        return 7

    parked = ensure_pause()
    print_command_result("ensure_pause", parked)
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    return run_conductor(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
