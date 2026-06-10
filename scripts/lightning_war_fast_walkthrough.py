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
    _lightning_end_turn_retryable,
    _lightning_extract_red_regions_from_image,
    _lightning_live_snapshot,
    _lightning_observed_terminal_transition,
    _observe_end_turn_after_click,
    _lightning_visible_ui_snapshot,
    _lightning_wait_for_deploy_confirm_live_bridge,
    cmd_auto_turn,
    cmd_deploy_recommended,
    cmd_read,
)


APP_NAME = "Into the Breach"
LIGHTNING_UI_BASE_SIZE = (1280, 748)
TIMING_SCREENSHOT_DIR = ROOT / "run_notes" / "lightning_war_walkthrough" / "timing_screenshots"
TERMINAL_OR_CLEAR_UIS = {
    "bottom_continue_panel",
    "island_complete_leave",
    "kia_panel",
    "perfect_island_panel",
    "perfect_reward_choice",
    "pod_open_panel",
    "promotion_panel",
    "reward_panel",
}


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


def capture_timing(prefix: str) -> Path:
    bounds = get_window_bounds()
    if bounds is None:
        raise FastRunError("could not find Into the Breach window bounds")
    TIMING_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = TIMING_SCREENSHOT_DIR / f"{prefix}_{int(time.time() * 1000)}.png"
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


def compact_live_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": snapshot.get("status"),
        "phase": snapshot.get("phase"),
        "turn": snapshot.get("turn"),
        "active_mechs": snapshot.get("active_mechs"),
        "grid_power": snapshot.get("grid_power"),
        "in_active_mission": snapshot.get("in_active_mission"),
        "bridge_heartbeat_alive": snapshot.get("bridge_heartbeat_alive"),
        "bridge_heartbeat_stale": snapshot.get("bridge_heartbeat_stale"),
    }


def compact_visible_ui(visible: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": visible.get("status"),
        "visible_ui": visible.get("visible_ui"),
        "recommended_control": visible.get("recommended_control"),
        "confidence": visible.get("confidence"),
        "screenshot_path": visible.get("screenshot_path"),
        "ocr_text": visible.get("ocr_text"),
        "terminal_outcome": visible.get("terminal_outcome"),
        "terminal_outcome_visible": visible.get("terminal_outcome_visible"),
        "region_secured_visible": visible.get("region_secured_visible"),
    }


def wait_for_post_end_turn_ready_or_terminal(
    *,
    turn_index: int,
    timer_start: float,
    min_wait_seconds: float,
    max_wait_seconds: float,
    terminal_visual_settle_seconds: float,
    poll_seconds: float = 0.5,
) -> dict[str, Any]:
    log(f"wait at least {min_wait_seconds:.1f}s after Turn {turn_index} End Turn")
    start = time.perf_counter()
    time.sleep(max(0.0, min_wait_seconds))
    samples: list[dict[str, Any]] = []
    first_bridge_terminal_elapsed: float | None = None
    while True:
        elapsed_after_end = round(time.perf_counter() - start, 3)
        sample_shot = capture_timing(f"turn_{turn_index}_post_end")
        visible = _lightning_visible_ui_snapshot(include_ocr=False)
        try:
            snapshot = _lightning_live_snapshot()
        except Exception as exc:
            snapshot = {"status": "ERROR", "error": str(exc)}
        sample = {
            "elapsed_after_end_turn_seconds": elapsed_after_end,
            "game_timer_seconds": elapsed(timer_start),
            "screenshot_path": str(sample_shot),
            "visible_ui": compact_visible_ui(visible),
            "live_snapshot": compact_live_snapshot(snapshot),
        }
        samples.append(sample)
        visible_name = visible.get("visible_ui")
        phase = snapshot.get("phase") if isinstance(snapshot, dict) else None
        active = snapshot.get("active_mechs") if isinstance(snapshot, dict) else None
        log(
            "post-end sample "
            f"turn={turn_index} +{elapsed_after_end:.1f}s "
            f"ui={visible_name} phase={phase} active={active} "
            f"shot={sample_shot}"
        )
        if visible.get("status") == "OK" and visible_name in TERMINAL_OR_CLEAR_UIS:
            audited_visible = _lightning_visible_ui_snapshot(include_ocr=True)
            return {
                "status": "TERMINAL_OR_CLEAR_UI",
                "reason": "visible_terminal_or_clear_panel",
                "turn_index": turn_index,
                "elapsed_seconds": elapsed_after_end,
                "game_timer_seconds": elapsed(timer_start),
                "samples": samples,
                "visible_ui": compact_visible_ui(audited_visible),
                "snapshot": compact_live_snapshot(snapshot),
            }
        bridge_terminal = (
            isinstance(snapshot, dict)
            and snapshot.get("status") == "OK"
            and (
                snapshot.get("in_active_mission") is False
                or snapshot.get("phase") in {"between_missions", "mission_ending"}
                or (
                    snapshot.get("phase") == "unknown"
                    and int(snapshot.get("active_mechs") or 0) == 0
                    and int(snapshot.get("deployment_zone_count") or 0) == 0
                )
            )
        )
        if bridge_terminal:
            if first_bridge_terminal_elapsed is None:
                first_bridge_terminal_elapsed = elapsed_after_end
                log(
                    "bridge terminal state seen; settling visible result "
                    f"for {terminal_visual_settle_seconds:.1f}s"
                )
            if elapsed_after_end - first_bridge_terminal_elapsed >= terminal_visual_settle_seconds:
                audited_visible = _lightning_visible_ui_snapshot(include_ocr=True)
                return {
                    "status": "TERMINAL_OR_CLEAR_UI",
                    "reason": "bridge_terminal_visual_settled",
                    "turn_index": turn_index,
                    "elapsed_seconds": elapsed_after_end,
                    "game_timer_seconds": elapsed(timer_start),
                    "samples": samples,
                    "visible_ui": compact_visible_ui(audited_visible),
                    "snapshot": compact_live_snapshot(snapshot),
                    "first_bridge_terminal_elapsed_seconds": first_bridge_terminal_elapsed,
                    "terminal_visual_settle_seconds": terminal_visual_settle_seconds,
                }
        if (
            isinstance(snapshot, dict)
            and snapshot.get("status") == "OK"
            and snapshot.get("phase") == "combat_player"
            and int(snapshot.get("active_mechs") or 0) > 0
            and snapshot.get("bridge_heartbeat_alive") is not False
            and snapshot.get("bridge_heartbeat_stale") is not True
        ):
            pause = press_key(
                "esc",
                description=f"pause after Turn {turn_index} enemy turn",
                app_name=APP_NAME,
                settle_seconds=0.25,
            )
            return {
                "status": "PLAYER_TURN_READY",
                "reason": "post_end_turn_player_ready",
                "turn_index": turn_index,
                "elapsed_seconds": elapsed_after_end,
                "game_timer_seconds": elapsed(timer_start),
                "samples": samples,
                "snapshot": compact_live_snapshot(snapshot),
                "pause": pause,
            }
        if time.perf_counter() - start >= max_wait_seconds:
            raise FastRunError(
                json.dumps(
                    {
                        "status": "POST_END_TURN_TIMEOUT",
                        "turn_index": turn_index,
                        "max_wait_seconds": max_wait_seconds,
                        "samples": samples,
                    },
                    default=str,
                )
            )
        time.sleep(max(0.05, poll_seconds))


def solve_execute_and_end_turn(
    *,
    turn_index: int,
    timer_start: float,
    args: argparse.Namespace,
) -> dict[str, Any]:
    click_control("menu_continue", settle_seconds=0.15)
    unpaused_mark = elapsed(timer_start)
    heartbeat = wait_for_fresh_heartbeat(label=f"turn_{turn_index}_after_menu_continue")
    heartbeat_mark = elapsed(timer_start)

    log(f"auto_turn solve+execute turn={turn_index}")
    turn = cmd_auto_turn(
        time_limit=args.time_limit,
        max_wait=args.auto_turn_max_wait,
        resume_before_execute=False,
        lightning_speed_loss_policy=True,
    )
    turn_plan_ready = (
        turn.get("status") == "PLAN"
        and int(turn.get("actions_completed") or 0) > 0
        and turn.get("bridge_ack")
    )
    if turn.get("status") not in {"OK", "PASS"} and not turn_plan_ready:
        raise FastRunError(f"auto_turn failed on turn {turn_index}: {turn}")
    auto_turn_done_mark = elapsed(timer_start)

    click_control("end_turn", settle_seconds=0.0)
    end_turn_mark = elapsed(timer_start)
    observed = _observe_end_turn_after_click(turn, timeout=2.0, poll_interval=0.2)
    retry_click = None
    retry_observed = None
    if _lightning_end_turn_retryable(observed, turn):
        retry_click = click_control("end_turn", settle_seconds=0.0)
        retry_observed = _observe_end_turn_after_click(
            turn,
            timeout=4.0,
            poll_interval=0.2,
        )
        observed = retry_observed
    observed_status = observed.get("status")
    observer_missed_possible_terminal = observed_status != "OK"
    if observer_missed_possible_terminal:
        log(
            "End Turn observer did not see a clean transition; "
            "continuing into terminal/player-turn watcher"
        )
    if observed_status == "OK" and _lightning_observed_terminal_transition(observed):
        log("bridge terminal transition observed; sampling visible result panel")
    try:
        post_end = wait_for_post_end_turn_ready_or_terminal(
            turn_index=turn_index,
            timer_start=timer_start,
            min_wait_seconds=args.post_end_turn_wait_seconds,
            max_wait_seconds=args.post_end_turn_max_wait_seconds,
            terminal_visual_settle_seconds=args.terminal_visual_settle_seconds,
            poll_seconds=args.result_screenshot_cadence,
        )
    except FastRunError:
        if observer_missed_possible_terminal:
            raise FastRunError(
                json.dumps(
                    {
                        "status": "END_TURN_CLICK_NOT_OBSERVED",
                        "turn_index": turn_index,
                        "observed": observed,
                        "retry_click": retry_click,
                        "retry_observed": retry_observed,
                    },
                    default=str,
                )
            )
        raise
    return {
        "turn_index": turn_index,
        "marks": {
            "unpaused_for_auto_turn": unpaused_mark,
            "heartbeat_fresh_for_auto_turn": heartbeat_mark,
            "auto_turn_done": auto_turn_done_mark,
            "end_turn_click": end_turn_mark,
            "post_end_observed": elapsed(timer_start),
        },
        "heartbeat": heartbeat,
        "auto_turn_status": turn.get("status") or turn.get("error"),
        "actions_completed": turn.get("actions_completed"),
        "turn": turn.get("turn"),
        "end_turn_observed": observed,
        "end_turn_retry_click": retry_click,
        "end_turn_retry_observed": retry_observed,
        "post_end_turn": post_end,
    }


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

    turns: list[dict[str, Any]] = []
    first_turn = solve_execute_and_end_turn(
        turn_index=1,
        timer_start=timer_start,
        args=args,
    )
    turns.append(first_turn)
    marks["turn_1_end_turn_click"] = first_turn["marks"]["end_turn_click"]
    marks["turn_1_post_end_observed"] = first_turn["marks"]["post_end_observed"]
    if first_turn["post_end_turn"].get("status") != "PLAYER_TURN_READY":
        return {
            "status": "OK",
            "reason": "stopped_after_turn_1_terminal_or_clear",
            "marks": marks,
            "red_region": region,
            "deploy": deploy,
            "turns": turns,
        }
    if not args.full_mission:
        return {
            "status": "OK",
            "marks": marks,
            "red_region": region,
            "deploy": deploy,
            "heartbeat": first_turn.get("heartbeat"),
            "auto_turn_status": first_turn.get("auto_turn_status"),
            "post_end_turn": first_turn.get("post_end_turn"),
            "turns": turns,
        }
    for turn_index in range(2, args.max_mission_turns + 1):
        turn_record = solve_execute_and_end_turn(
            turn_index=turn_index,
            timer_start=timer_start,
            args=args,
        )
        turns.append(turn_record)
        marks[f"turn_{turn_index}_end_turn_click"] = (
            turn_record["marks"]["end_turn_click"]
        )
        marks[f"turn_{turn_index}_post_end_observed"] = (
            turn_record["marks"]["post_end_observed"]
        )
        if turn_record["post_end_turn"].get("status") != "PLAYER_TURN_READY":
            return {
                "status": "OK",
                "reason": "terminal_or_clear_after_end_turn",
                "terminal_turn_index": turn_index,
                "marks": marks,
                "red_region": region,
                "deploy": deploy,
                "turns": turns,
            }
    final_visible = _lightning_visible_ui_snapshot(include_ocr=True)
    return {
        "status": "MAX_TURNS_REACHED",
        "marks": marks,
        "red_region": region,
        "deploy": deploy,
        "turns": turns,
        "final_visible_ui": compact_visible_ui(final_visible),
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
    parser.add_argument("--opening-enemy-wait-seconds", type=float, default=7.0)
    parser.add_argument("--opening-enemy-max-wait-seconds", type=float, default=28.0)
    parser.add_argument("--post-end-turn-wait-seconds", type=float, default=8.0)
    parser.add_argument("--post-end-turn-max-wait-seconds", type=float, default=25.0)
    parser.add_argument("--result-screenshot-cadence", type=float, default=0.5)
    parser.add_argument("--terminal-visual-settle-seconds", type=float, default=2.5)
    parser.add_argument("--max-mission-turns", type=int, default=6)
    parser.add_argument("--confirm-retries", type=int, default=2)
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--auto-turn-max-wait", type=float, default=5.0)
    parser.add_argument(
        "--full-mission",
        action="store_true",
        help="Continue combat turns until a mission-end/reward panel is visible.",
    )
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
