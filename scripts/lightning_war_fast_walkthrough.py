#!/usr/bin/env python
"""Fast manual-walkthrough driver for the Lightning War opening loop.

This script is intentionally narrower than ``lightning_war_conductor.py``. It
codifies the timings learned in the live walkthrough and avoids spawning a new
``game_loop.py`` process for every click.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from src.capture.window import get_window_bounds, take_screenshot
from src.bridge.protocol import HEARTBEAT_FILE, is_bridge_alive
from src.control.mac_click import (
    click_known_window_control,
    click_title_new_game_dynamic,
    click_window_point,
    press_key,
)
from src.loop.commands import (
    _lightning_ensure_pause_state,
    _lightning_extract_red_regions_from_image,
    _lightning_live_snapshot,
    _lightning_visible_ui_snapshot,
    _lightning_wait_for_deploy_confirm_live_bridge,
    cmd_auto_turn,
    cmd_deploy_recommended,
    cmd_read,
)


APP_NAME = "Into the Breach"
LIGHTNING_UI_BASE_SIZE = (1280, 748)


class FastRunError(RuntimeError):
    """Raised when the fast walkthrough must stop safely."""


def log(message: str) -> None:
    print(f"[lightning-fast] {message}", flush=True)


def elapsed(start: float) -> float:
    return round(time.perf_counter() - start, 3)


def sleep_until(start: float, target_seconds: float) -> None:
    remaining = float(target_seconds) - (time.perf_counter() - start)
    if remaining > 0:
        time.sleep(remaining)


def click_control(
    control: str,
    *,
    settle_seconds: float = 0.05,
    hold_seconds: float | None = None,
) -> dict[str, Any]:
    log(f"click {control}")
    result = click_known_window_control(
        control,
        app_name=APP_NAME,
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )
    if result.get("status") != "OK":
        raise FastRunError(f"click {control} failed: {result}")
    return result


def click_point(
    name: str,
    x: int,
    y: int,
    *,
    settle_seconds: float = 0.05,
    hold_seconds: float = 0.3,
) -> dict[str, Any]:
    log(f"click {name} @ ({x},{y})")
    result = click_window_point(
        x,
        y,
        description=name,
        app_name=APP_NAME,
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )
    if result.get("status") != "OK":
        raise FastRunError(f"click {name} failed: {result}")
    return result


def capture(prefix: str) -> Path:
    bounds = get_window_bounds()
    if bounds is None:
        raise FastRunError("could not find Into the Breach window bounds")
    path = Path(tempfile.gettempdir()) / f"{prefix}_{int(time.time() * 1000)}.png"
    take_screenshot(path, bounds=bounds)
    return path


def visible_ui_name() -> str:
    try:
        return str(_lightning_visible_ui_snapshot().get("visible_ui") or "unknown")
    except Exception as exc:
        return f"unknown:{exc}"


def wait_for_fresh_heartbeat(
    *,
    label: str,
    max_seconds: float = 2.5,
    poll_seconds: float = 0.05,
) -> dict[str, Any]:
    """Wait for the Lua BaseUpdate heartbeat to prove the game is ticking."""
    start = time.perf_counter()
    attempts: list[dict[str, Any]] = []
    while True:
        age: float | None = None
        try:
            if HEARTBEAT_FILE.exists():
                age = time.time() - HEARTBEAT_FILE.stat().st_mtime
        except OSError:
            age = None
        alive = is_bridge_alive(max_stale_sec=1.0)
        attempt = {
            "elapsed_seconds": elapsed(start),
            "heartbeat_age_sec": None if age is None else round(age, 3),
            "alive_1s": alive,
        }
        attempts.append(attempt)
        if alive:
            return {
                "status": "OK",
                "label": label,
                "elapsed_seconds": elapsed(start),
                "attempts": attempts,
            }
        if time.perf_counter() - start >= max_seconds:
            raise FastRunError(
                json.dumps(
                    {
                        "status": "HEARTBEAT_STALE_AFTER_FOCUS",
                        "label": label,
                        "max_seconds": max_seconds,
                        "attempts": attempts,
                    },
                    default=str,
                )
            )
        time.sleep(max(0.01, poll_seconds))


def click_title_new_game() -> dict[str, Any]:
    log("click title_new_game")
    result = click_title_new_game_dynamic(
        app_name=APP_NAME,
        settle_seconds=0.15,
        hold_seconds=0.3,
    )
    if result.get("status") != "OK":
        raise FastRunError(f"title_new_game failed: {result}")
    return result


def click_overwrite_yes_if_present() -> None:
    """Click the new-run overwrite YES position.

    This occurs before the game timer starts. If no overwrite modal is present,
    this coordinate is harmless on the loadout screen in the tested layout.
    """
    time.sleep(0.25)
    click_point("overwrite_yes_optional", 1208, 795, settle_seconds=0.45)


def click_largest_red_mission() -> dict[str, Any]:
    shot = capture("lw_red")
    bounds = get_window_bounds()
    if bounds is None:
        raise FastRunError("could not find Into the Breach window bounds")
    regions = _lightning_extract_red_regions_from_image(shot)
    log(f"red mission regions={regions.get('region_count')} screenshot={shot}")
    candidates = regions.get("regions") or []
    if not candidates:
        raise FastRunError(f"no red mission regions detected: {regions}")
    region = max(
        candidates,
        key=lambda item: item.get("area_window", item.get("area_px", 0)),
    )
    base_w, base_h = LIGHTNING_UI_BASE_SIZE
    scale_x = bounds["width"] / base_w
    scale_y = bounds["height"] / base_h
    live_x = int(round(float(region["window_x"]) * scale_x))
    live_y = int(round(float(region["window_y"]) * scale_y))
    region["live_window_x"] = live_x
    region["live_window_y"] = live_y
    region["live_coordinate_scale"] = {"x": scale_x, "y": scale_y}
    click_point(
        "red_mission",
        live_x,
        live_y,
        settle_seconds=0.15,
    )
    return region


def deploy_and_confirm(*, confirm_retries: int) -> dict[str, Any]:
    log("deploy_recommended")
    deploy = cmd_deploy_recommended(ui_fallback=True)
    deploy_status = deploy.get("status")
    deployments = deploy.get("deployments") or []
    if deploy_status != "OK":
        fallback_ok = (
            deploy_status == "WARN"
            and deploy.get("ui_fallback", {}).get("status") == "OK"
            and len(deployments) >= 3
        )
        if not fallback_ok:
            raise FastRunError(f"deploy_recommended failed: {deploy}")
        log(f"deploy accepted warning: {deploy.get('reason')}")

    attempts: list[dict[str, Any]] = []
    for attempt in range(1, max(1, confirm_retries) + 1):
        click_control("deploy_confirm", settle_seconds=0.05)
        wait = _lightning_wait_for_deploy_confirm_live_bridge(
            max_seconds=4.0,
            interval_seconds=0.3,
        )
        attempts.append(wait)
        log(
            "confirm attempt "
            f"{attempt}: {wait.get('status')} {wait.get('reason')} "
            f"phase={wait.get('snapshot', {}).get('phase')}"
        )
        if wait.get("status") == "OK":
            return {
                "status": "OK",
                "deploy": deploy,
                "confirm_attempts": attempts,
                "snapshot": wait.get("snapshot"),
            }
    raise FastRunError(
        json.dumps(
            {
                "status": "DEPLOY_CONFIRM_BLOCKED",
                "deploy_status": deploy_status,
                "confirm_attempts": attempts,
                "visible_ui": visible_ui_name(),
            },
            default=str,
        )
    )


def wait_for_actionable_player_turn(
    *,
    min_wait_seconds: float,
    max_wait_seconds: float,
    poll_seconds: float = 0.35,
) -> dict[str, Any]:
    log(f"wait at least {min_wait_seconds:.1f}s opening enemy turn")
    start = time.perf_counter()
    time.sleep(max(0.0, min_wait_seconds))
    attempts: list[dict[str, Any]] = []
    while True:
        snapshot = _lightning_live_snapshot()
        attempt = {
            "elapsed_seconds": round(time.perf_counter() - start, 3),
            "status": snapshot.get("status"),
            "phase": snapshot.get("phase"),
            "turn": snapshot.get("turn"),
            "active_mechs": snapshot.get("active_mechs"),
            "mech_count": snapshot.get("mech_count"),
            "bridge_heartbeat_alive": snapshot.get("bridge_heartbeat_alive"),
            "bridge_heartbeat_stale": snapshot.get("bridge_heartbeat_stale"),
        }
        attempts.append(attempt)
        log(
            "opening poll "
            f"{attempt['elapsed_seconds']:.1f}s "
            f"phase={attempt['phase']} active={attempt['active_mechs']}"
        )
        if (
            snapshot.get("status") == "OK"
            and snapshot.get("phase") == "combat_player"
            and int(snapshot.get("active_mechs") or 0) > 0
            and snapshot.get("bridge_heartbeat_alive") is not False
            and snapshot.get("bridge_heartbeat_stale") is not True
        ):
            return {
                "status": "OK",
                "reason": "actionable_player_turn",
                "elapsed_seconds": round(time.perf_counter() - start, 3),
                "attempts": attempts,
                "snapshot": snapshot,
            }
        if time.perf_counter() - start >= max_wait_seconds:
            raise FastRunError(
                json.dumps(
                    {
                        "status": "OPENING_PLAYER_TURN_TIMEOUT",
                        "max_wait_seconds": max_wait_seconds,
                        "attempts": attempts,
                        "snapshot": snapshot,
                    },
                    default=str,
                )
            )
        time.sleep(max(0.05, poll_seconds))


def pause_after_opening(
    *,
    min_wait_seconds: float,
    max_wait_seconds: float,
) -> dict[str, Any]:
    readiness = wait_for_actionable_player_turn(
        min_wait_seconds=min_wait_seconds,
        max_wait_seconds=max_wait_seconds,
    )
    log("pause with Escape")
    result = press_key(
        "esc",
        description="pause after opening enemy turn",
        app_name=APP_NAME,
        settle_seconds=0.25,
    )
    if result.get("status") != "OK":
        raise FastRunError(f"pause failed: {result}")
    return {"status": "OK", "readiness": readiness, "pause": result}


def wait_for_post_end_turn_player_turn(
    *,
    min_wait_seconds: float,
    max_wait_seconds: float,
    poll_seconds: float = 0.5,
) -> dict[str, Any]:
    log(f"wait at least {min_wait_seconds:.1f}s after End Turn")
    start = time.perf_counter()
    time.sleep(max(0.0, min_wait_seconds))
    attempts: list[dict[str, Any]] = []
    while True:
        snapshot = _lightning_live_snapshot()
        attempt = {
            "elapsed_seconds": round(time.perf_counter() - start, 3),
            "status": snapshot.get("status"),
            "phase": snapshot.get("phase"),
            "turn": snapshot.get("turn"),
            "active_mechs": snapshot.get("active_mechs"),
            "grid_power": snapshot.get("grid_power"),
            "bridge_heartbeat_alive": snapshot.get("bridge_heartbeat_alive"),
            "bridge_heartbeat_stale": snapshot.get("bridge_heartbeat_stale"),
        }
        attempts.append(attempt)
        log(
            "post-end poll "
            f"{attempt['elapsed_seconds']:.1f}s "
            f"phase={attempt['phase']} active={attempt['active_mechs']}"
        )
        if (
            snapshot.get("status") == "OK"
            and snapshot.get("phase") == "combat_player"
            and int(snapshot.get("active_mechs") or 0) > 0
            and snapshot.get("bridge_heartbeat_alive") is not False
            and snapshot.get("bridge_heartbeat_stale") is not True
        ):
            pause = press_key(
                "esc",
                description="pause after post-end-turn player ready",
                app_name=APP_NAME,
                settle_seconds=0.25,
            )
            return {
                "status": "OK",
                "reason": "post_end_turn_player_ready",
                "elapsed_seconds": round(time.perf_counter() - start, 3),
                "attempts": attempts,
                "snapshot": snapshot,
                "pause": pause,
            }
        if time.perf_counter() - start >= max_wait_seconds:
            raise FastRunError(
                json.dumps(
                    {
                        "status": "POST_END_TURN_TIMEOUT",
                        "max_wait_seconds": max_wait_seconds,
                        "attempts": attempts,
                        "snapshot": snapshot,
                    },
                    default=str,
                )
            )
        time.sleep(max(0.05, poll_seconds))


def run_from_main_menu(args: argparse.Namespace) -> dict[str, Any]:
    marks: dict[str, float] = {}
    run_start = time.perf_counter()

    click_title_new_game()
    click_overwrite_yes_if_present()
    click_control("setup_start", settle_seconds=0.45)
    log(f"pre-timer visible={visible_ui_name()}")

    timer_start = time.perf_counter()
    click_control("setup_modal_start", settle_seconds=0.0)
    marks["timer_start"] = elapsed(run_start)

    sleep_until(timer_start, args.island_click_seconds)
    click_control("island_archive", settle_seconds=0.0)
    marks["archive_click"] = elapsed(timer_start)

    sleep_until(timer_start, args.continue_click_seconds)
    click_control("bottom_continue", settle_seconds=0.0)
    marks["intro_continue"] = elapsed(timer_start)

    time.sleep(args.red_wait_seconds)
    region = click_largest_red_mission()
    marks["red_mission_click"] = elapsed(timer_start)

    click_control("mission_preview_board", settle_seconds=args.preview_settle_seconds)
    marks["preview_board_click"] = elapsed(timer_start)

    time.sleep(args.deploy_ready_wait_seconds)
    deploy = deploy_and_confirm(confirm_retries=args.confirm_retries)
    marks["deploy_confirm_live"] = elapsed(timer_start)

    pause = pause_after_opening(
        min_wait_seconds=args.opening_enemy_wait_seconds,
        max_wait_seconds=args.opening_enemy_max_wait_seconds,
    )
    marks["paused_after_opening"] = elapsed(timer_start)

    if args.stop_after_pause:
        return {
            "status": "STOPPED_AFTER_PAUSE",
            "marks": marks,
            "red_region": region,
            "deploy": deploy,
            "pause": pause,
        }

    click_control("menu_continue", settle_seconds=0.15)
    marks["unpaused_for_auto_turn"] = elapsed(timer_start)
    heartbeat = wait_for_fresh_heartbeat(label="after_menu_continue")
    marks["heartbeat_fresh_for_auto_turn"] = elapsed(timer_start)

    log("auto_turn solve+execute")
    turn = cmd_auto_turn(
        time_limit=args.time_limit,
        max_wait=args.auto_turn_max_wait,
        resume_before_execute=False,
        lightning_speed_loss_policy=True,
    )
    turn_status = turn.get("status") or turn.get("error")
    turn_plan_ready = (
        turn.get("status") == "PLAN"
        and int(turn.get("actions_completed") or 0) > 0
        and turn.get("bridge_ack")
    )
    if turn.get("status") not in {"OK", "PASS"} and not turn_plan_ready:
        raise FastRunError(f"auto_turn failed: {turn}")
    marks["auto_turn_done"] = elapsed(timer_start)

    click_control("end_turn", settle_seconds=0.0)
    marks["end_turn_click"] = elapsed(timer_start)

    post_end = wait_for_post_end_turn_player_turn(
        min_wait_seconds=args.post_end_turn_wait_seconds,
        max_wait_seconds=args.post_end_turn_max_wait_seconds,
    )
    marks["post_end_turn_read"] = elapsed(timer_start)
    return {
        "status": "OK",
        "marks": marks,
        "red_region": region,
        "deploy": deploy,
        "heartbeat": heartbeat,
        "auto_turn_status": turn_status,
        "post_end_turn": post_end,
    }


def park_on_error() -> dict[str, Any]:
    """Best-effort pause after a fast-path failure."""
    try:
        pause = _lightning_ensure_pause_state(
            reason="fast_walkthrough_error",
        )
    except Exception as exc:
        pause = {"status": "ERROR", "error": str(exc)}
    try:
        snapshot = _lightning_live_snapshot()
    except Exception as exc:
        snapshot = {"status": "ERROR", "error": str(exc)}
    return {"pause": pause, "snapshot": snapshot, "visible_ui": visible_ui_name()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the fast Lightning War walkthrough opening loop.",
    )
    parser.add_argument("--island-click-seconds", type=float, default=7.0)
    parser.add_argument("--continue-click-seconds", type=float, default=9.5)
    parser.add_argument("--red-wait-seconds", type=float, default=0.5)
    parser.add_argument("--preview-settle-seconds", type=float, default=0.5)
    parser.add_argument("--deploy-ready-wait-seconds", type=float, default=0.5)
    parser.add_argument("--opening-enemy-wait-seconds", type=float, default=16.0)
    parser.add_argument("--opening-enemy-max-wait-seconds", type=float, default=28.0)
    parser.add_argument("--post-end-turn-wait-seconds", type=float, default=8.0)
    parser.add_argument("--post-end-turn-max-wait-seconds", type=float, default=25.0)
    parser.add_argument("--confirm-retries", type=int, default=2)
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--auto-turn-max-wait", type=float, default=5.0)
    parser.add_argument(
        "--stop-after-pause",
        action="store_true",
        help="Stop after deployment, opening enemy turn, and pause.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_from_main_menu(args)
    except Exception as exc:
        parked = park_on_error()
        print("---FAST_WALKTHROUGH_ERROR---")
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error": str(exc),
                    "parked": parked,
                },
                default=str,
                indent=2,
            )
        )
        return 1
    print("---FAST_WALKTHROUGH_RESULT---")
    print(json.dumps(result, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
