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
    _lightning_visible_ui_text_parts,
    _lightning_live_snapshot,
    _lightning_observed_terminal_transition,
    _observe_end_turn_after_click,
    _lightning_visible_ui_snapshot,
    _lightning_wait_for_deploy_confirm_live_bridge,
    cmd_auto_turn,
    cmd_deploy_recommended,
    cmd_execute,
    cmd_read,
    cmd_solve,
    cmd_verify_action,
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


def click_dialogue_textbox_sweep() -> dict[str, Any]:
    """Dismiss result/advisor dialogue boxes whose active hitbox varies a bit."""
    points = [
        (875, 520),
        (1040, 520),
        (1280, 520),
        (1400, 520),
    ]
    clicks: list[dict[str, Any]] = []
    for index, (x, y) in enumerate(points, start=1):
        clicks.append(
            click_point(
                f"dialogue_textbox_sweep_{index}",
                x,
                y,
                settle_seconds=0.15,
                hold_seconds=0.16,
            )
        )
    return {"status": "OK", "control": "dialogue_textbox", "clicks": clicks}


def click_reward_continue_sweep() -> dict[str, Any]:
    """Click the two observed Region Secured / reward Continue button heights."""
    points = [
        (1647, 1018),
        (1647, 985),
    ]
    clicks: list[dict[str, Any]] = []
    for index, (x, y) in enumerate(points, start=1):
        clicks.append(
            click_point(
                f"reward_continue_sweep_{index}",
                x,
                y,
                settle_seconds=0.25,
                hold_seconds=0.18,
            )
        )
    return {"status": "OK", "control": "reward_continue", "clicks": clicks}


def click_transition_control(
    control: str,
    *,
    settle_seconds: float = 0.05,
    hold_seconds: float | None = None,
) -> dict[str, Any]:
    if control == "dialogue_textbox":
        return click_dialogue_textbox_sweep()
    if control == "reward_continue":
        return click_reward_continue_sweep()
    return click_control(
        control,
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )


def dispatch_click_plan(clicks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dispatched: list[dict[str, Any]] = []
    for index, op in enumerate(clicks):
        op_type = op.get("type")
        if op_type == "wait":
            duration = float(op.get("duration") or 0.0)
            time.sleep(max(0.0, duration))
            dispatched.append({"index": index, "type": "wait", "duration": duration})
            continue
        if op_type != "left_click":
            dispatched.append({"index": index, "type": op_type, "status": "SKIPPED"})
            continue
        x = op.get("window_x", op.get("x"))
        y = op.get("window_y", op.get("y"))
        if x is None or y is None:
            raise FastRunError(f"click plan op missing coordinates: {op}")
        click = click_point(
            str(op.get("description") or f"click_plan_{index}"),
            int(x),
            int(y),
            settle_seconds=0.05,
            hold_seconds=0.18,
        )
        dispatched.append({"index": index, "type": "left_click", "click": click})
    return dispatched


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


def click_mission_preview_until_deployment(
    *,
    settle_seconds: float,
    max_attempts: int = 3,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for attempt_index in range(1, max_attempts + 1):
        click = click_control("mission_preview_board", settle_seconds=settle_seconds)
        time.sleep(0.5)
        visible = _lightning_visible_ui_snapshot(include_ocr=False)
        attempt = {
            "attempt": attempt_index,
            "click": click,
            "visible_ui": compact_visible_ui(visible),
        }
        attempts.append(attempt)
        if visible.get("visible_ui") == "deployment_screen":
            return {"status": "OK", "attempts": attempts}
    raise FastRunError(
        json.dumps(
            {
                "status": "MISSION_PREVIEW_DID_NOT_OPEN_DEPLOYMENT",
                "attempts": attempts,
            },
            default=str,
        )
    )


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


def parse_grid_power(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.split("/", 1)[0])
        except (TypeError, ValueError):
            return None
    return None


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


def visible_text_lower(visible: dict[str, Any]) -> str:
    try:
        parts = _lightning_visible_ui_text_parts(visible)
    except Exception:
        parts = []
    return "\n".join(str(part) for part in parts).lower()


def clear_control_for_visible_ui(
    visible: dict[str, Any],
    *,
    previous_control: str | None = None,
) -> str:
    visible_name = visible.get("visible_ui")
    text = visible_text_lower(visible)

    if "leave island" in text and "continue" in text and "yes" in text:
        return "leave_confirm_yes"
    if "spend reputation" in text and "leave island" in text:
        return "leave_island"
    if "head office" in text and "continue" in text:
        return "bottom_continue"
    if "promoted" in text or "new skill unlocked" in text:
        return "modal_understood"
    if "pod recovered" in text and "open door" in text:
        return "pod_open_door"
    if ("pod contents" in text or "reactor core" in text) and "continue" in text:
        return "reward_continue"
    if "perfect island" in text and "select one free reward" in text:
        if "wait" in text or previous_control in {"panel_continue", "bottom_continue"}:
            return "perfect_reward_grid"
        return "panel_continue"
    if "region secured" in text:
        return "reward_continue"

    if visible_name == "island_complete_leave":
        return "leave_island"
    if visible_name == "pause_menu":
        return "menu_continue"
    if visible_name == "promotion_panel":
        return "modal_understood"
    if visible_name == "kia_panel" and visible.get("recommended_control") == "kia_understood":
        return "modal_understood"
    if visible_name == "pod_open_panel":
        return "pod_open_door"
    if visible_name == "perfect_island_panel":
        return "panel_continue"
    if visible_name == "perfect_reward_choice":
        if previous_control in {"panel_continue", "bottom_continue"}:
            return "perfect_reward_grid"
        return "reward_continue"
    if visible_name == "island_map" and previous_control == "reward_continue":
        return "leave_island"
    if visible_name == "island_map_or_unknown" and previous_control == "reward_continue":
        return "modal_understood"
    if previous_control == "leave_island":
        return "leave_confirm_yes"
    if previous_control == "leave_confirm_yes":
        return "island_rst"
    if previous_control == "island_rst":
        return "bottom_continue"
    if visible_name in TERMINAL_OR_CLEAR_UIS or visible_name in {
        "combat_screen",
        "island_map_or_unknown",
        "reward_panel",
    }:
        return "reward_continue"
    return visible.get("recommended_control") or "reward_continue"


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


def paused_solve_execute_and_end_turn(
    *,
    turn_index: int,
    timer_start: float,
    args: argparse.Namespace,
) -> dict[str, Any]:
    log(f"paused solve turn={turn_index}")
    paused_read = cmd_read()
    paused_read_mark = elapsed(timer_start)
    solve = cmd_solve(time_limit=args.time_limit)
    paused_solve_done_mark = elapsed(timer_start)
    if solve.get("error"):
        raise FastRunError(f"paused solve failed on turn {turn_index}: {solve}")
    actions = solve.get("actions") or []
    if not actions:
        raise FastRunError(f"paused solve returned no actions on turn {turn_index}: {solve}")

    click_control("menu_continue", settle_seconds=0.15)
    unpaused_mark = elapsed(timer_start)
    heartbeat = wait_for_fresh_heartbeat(
        label=f"turn_{turn_index}_after_paused_solve_menu_continue",
    )
    heartbeat_mark = elapsed(timer_start)

    executions: list[dict[str, Any]] = []
    for action in actions:
        action_index = int(action["index"])
        log(f"execute stored paused action {action_index}")
        executed = cmd_execute(action_index)
        click_dispatch = None
        if executed.get("clicks"):
            log(f"dispatch stored action {action_index} click plan")
            click_dispatch = dispatch_click_plan(list(executed.get("clicks") or []))
        verified = cmd_verify_action(action_index)
        delayed_verify_retry = None
        retryable_delayed_categories = {"terrain", "death"}
        if (
            verified.get("status") != "PASS"
            and set(verified.get("categories") or []) <= retryable_delayed_categories
        ):
            log(
                f"delayed terrain/death verify lag on action {action_index}; "
                f"retrying after {args.terrain_verify_retry_seconds:.1f}s live tick"
            )
            time.sleep(args.terrain_verify_retry_seconds)
            refresh_read = cmd_read()
            retry_verify = cmd_verify_action(action_index)
            delayed_verify_retry = {
                "delay_seconds": args.terrain_verify_retry_seconds,
                "refresh_read": {
                    "phase": refresh_read.get("phase"),
                    "turn": refresh_read.get("turn"),
                    "active_mechs": refresh_read.get("active_mechs"),
                    "grid_power": refresh_read.get("grid_power"),
                },
                "verify": retry_verify,
            }
            verified = retry_verify
        executions.append(
            {
                "action_index": action_index,
                "execute": executed,
                "click_dispatch": click_dispatch,
                "verify": verified,
                "delayed_verify_retry": delayed_verify_retry,
            }
        )
        if verified.get("status") != "PASS":
            raise FastRunError(
                json.dumps(
                    {
                        "status": "PAUSED_STORED_ACTION_VERIFY_FAILED",
                        "turn_index": turn_index,
                        "action_index": action_index,
                        "execute": executed,
                        "click_dispatch": click_dispatch,
                        "verify": verified,
                    },
                    default=str,
                )
            )
    stored_actions_done_mark = elapsed(timer_start)

    post_action_read = cmd_read()
    post_action_mark = elapsed(timer_start)
    threatened = int(post_action_read.get("threatened_buildings") or 0)
    grid_power = parse_grid_power(post_action_read.get("grid_power"))
    speed_building_damage_allowed = (
        bool(args.allow_lightning_speed_building_damage)
        and grid_power is not None
        and grid_power - threatened > 0
    )
    if threatened > 0 and speed_building_damage_allowed:
        log(
            "allowing ordinary building threat for Lightning War speed: "
            f"threatened={threatened} grid={post_action_read.get('grid_power')}"
        )
    if threatened > 0 and not speed_building_damage_allowed:
        raise FastRunError(
            json.dumps(
                {
                    "status": "PAUSED_STORED_PLAN_THREAT_AUDIT_BLOCKED",
                    "turn_index": turn_index,
                    "threatened_buildings": threatened,
                    "threats": post_action_read.get("threats"),
                    "allow_lightning_speed_building_damage": (
                        args.allow_lightning_speed_building_damage
                    ),
                    "post_action_read": post_action_read,
                    "solve": {
                        "score": solve.get("score"),
                        "num_actions": solve.get("num_actions"),
                        "actions": solve.get("actions"),
                        "plan_safety": solve.get("plan_safety"),
                    },
                    "executions": executions,
                },
                default=str,
            )
        )

    click_control("end_turn", settle_seconds=0.0)
    end_turn_mark = elapsed(timer_start)
    observed = _observe_end_turn_after_click(
        {"status": "OK", "actions_completed": len(actions)},
        timeout=2.0,
        poll_interval=0.2,
    )
    retry_click = None
    retry_observed = None
    if _lightning_end_turn_retryable(observed, {"status": "OK"}):
        retry_click = click_control("end_turn", settle_seconds=0.0)
        retry_observed = _observe_end_turn_after_click(
            {"status": "OK", "actions_completed": len(actions)},
            timeout=4.0,
            poll_interval=0.2,
        )
        observed = retry_observed

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
        raise FastRunError(
            json.dumps(
                {
                    "status": "PAUSED_STORED_END_TURN_NOT_OBSERVED",
                    "turn_index": turn_index,
                    "observed": observed,
                    "retry_click": retry_click,
                    "retry_observed": retry_observed,
                },
                default=str,
            )
        )

    return {
        "turn_index": turn_index,
        "mode": "paused_solve_execute",
        "marks": {
            "paused_read_done": paused_read_mark,
            "paused_solve_done": paused_solve_done_mark,
            "unpaused_for_stored_execute": unpaused_mark,
            "heartbeat_fresh_for_stored_execute": heartbeat_mark,
            "stored_actions_done": stored_actions_done_mark,
            "post_action_read_done": post_action_mark,
            "end_turn_click": end_turn_mark,
            "post_end_observed": elapsed(timer_start),
        },
        "paused_read": {
            "phase": paused_read.get("phase"),
            "turn": paused_read.get("turn"),
            "active_mechs": paused_read.get("active_mechs"),
            "grid_power": paused_read.get("grid_power"),
        },
        "heartbeat": heartbeat,
        "solve_status": solve.get("status") or ("OK" if not solve.get("error") else "ERROR"),
        "actions_completed": len(executions),
        "executions": executions,
        "post_action_read": {
            "phase": post_action_read.get("phase"),
            "turn": post_action_read.get("turn"),
            "active_mechs": post_action_read.get("active_mechs"),
            "grid_power": post_action_read.get("grid_power"),
            "threatened_buildings": post_action_read.get("threatened_buildings"),
            "threats": post_action_read.get("threats"),
            "speed_building_damage_allowed": speed_building_damage_allowed,
        },
        "end_turn_observed": observed,
        "end_turn_retry_click": retry_click,
        "end_turn_retry_observed": retry_observed,
        "post_end_turn": post_end,
    }


def run_current_mission_from_island_map(
    *,
    mission_index: int,
    timer_start: float,
    args: argparse.Namespace,
    preview_already_open: bool = False,
) -> dict[str, Any]:
    marks: dict[str, float] = {}
    region = None
    if not preview_already_open:
        time.sleep(args.red_wait_seconds)
        region = click_largest_red_mission()
        marks["red_mission_click"] = elapsed(timer_start)

    preview = click_mission_preview_until_deployment(
        settle_seconds=args.preview_settle_seconds,
    )
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
            "mission_index": mission_index,
            "marks": marks,
            "red_region": region,
            "deploy": deploy,
            "pause": pause,
        }

    turns: list[dict[str, Any]] = []
    turn_runner = (
        paused_solve_execute_and_end_turn
        if args.paused_solve_execute
        else solve_execute_and_end_turn
    )
    for turn_index in range(1, args.max_mission_turns + 1):
        turn_record = turn_runner(
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
                "mission_index": mission_index,
                "terminal_turn_index": turn_index,
                "marks": marks,
                "red_region": region,
                "preview": preview,
                "deploy": deploy,
                "turns": turns,
            }
    final_visible = _lightning_visible_ui_snapshot(include_ocr=True)
    return {
        "status": "MAX_TURNS_REACHED",
        "mission_index": mission_index,
        "marks": marks,
        "red_region": region,
        "preview": preview,
        "deploy": deploy,
        "turns": turns,
        "final_visible_ui": compact_visible_ui(final_visible),
    }


def clear_mission_result_to_island_map(
    *,
    mission_index: int,
    timer_start: float,
    continue_after_island: bool = False,
    max_steps: int = 12,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    previous_control: str | None = None
    for step_index in range(max_steps):
        visible = _lightning_visible_ui_snapshot(include_ocr=True)
        visible_name = visible.get("visible_ui")
        step: dict[str, Any] = {
            "step": step_index + 1,
            "visible_ui": compact_visible_ui(visible),
            "game_timer_seconds": elapsed(timer_start),
        }
        if visible_name == "island_complete_leave" and not continue_after_island:
            return {
                "status": "ISLAND_COMPLETE_LEAVE_VISIBLE",
                "mission_index": mission_index,
                "steps": steps + [step],
            }
        control = clear_control_for_visible_ui(
            visible,
            previous_control=previous_control,
        )
        try:
            click = click_transition_control(control, settle_seconds=1.2)
            step["control"] = control
            step["click"] = click
        except Exception as exc:
            step["control"] = control
            step["error"] = str(exc)
            steps.append(step)
            break
        previous_control = control
        steps.append(step)
        time.sleep(0.6)
        if control == "leave_confirm_yes" and mission_index >= 10:
            return {
                "status": "SECOND_ISLAND_COMPLETE",
                "mission_index": mission_index,
                "steps": steps,
            }
        try:
            probe = click_largest_red_mission()
        except Exception as exc:
            steps[-1]["red_probe_error"] = str(exc)
            continue
        steps[-1]["red_probe_clicked"] = probe
        return {
            "status": "MISSION_PREVIEW_OPENED",
            "mission_index": mission_index + 1,
            "steps": steps,
            "red_region": probe,
        }
    return {
        "status": "RESULT_CLEAR_INCOMPLETE",
        "mission_index": mission_index,
        "steps": steps,
        "visible_ui": visible_ui_name(),
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

    if args.island_loop:
        missions: list[dict[str, Any]] = []
        transitions: list[dict[str, Any]] = []
        for mission_index in range(1, args.max_island_missions + 1):
            if mission_index == 1:
                mission = run_current_mission_from_island_map(
                    mission_index=mission_index,
                    timer_start=timer_start,
                    args=args,
                )
            else:
                mission = run_current_mission_from_island_map(
                    mission_index=mission_index,
                    timer_start=timer_start,
                    args=args,
                    preview_already_open=True,
                )
            missions.append(mission)
            if mission.get("status") not in {"OK", "STOPPED_AFTER_PAUSE"}:
                return {
                    "status": "ISLAND_LOOP_STOPPED",
                    "reason": "mission_runner_stopped",
                    "marks": marks,
                    "missions": missions,
                    "transitions": transitions,
                }
            transition = clear_mission_result_to_island_map(
                mission_index=mission_index,
                timer_start=timer_start,
                continue_after_island=args.continue_after_island,
            )
            transitions.append(transition)
            if transition.get("status") == "ISLAND_COMPLETE_LEAVE_VISIBLE":
                return {
                    "status": "ISLAND_COMPLETE_LEAVE_VISIBLE",
                    "marks": marks,
                    "missions": missions,
                    "transitions": transitions,
                }
            if transition.get("status") == "SECOND_ISLAND_COMPLETE":
                return {
                    "status": "SECOND_ISLAND_COMPLETE",
                    "marks": marks,
                    "missions": missions,
                    "transitions": transitions,
                }
            if transition.get("status") != "MISSION_PREVIEW_OPENED":
                return {
                    "status": "ISLAND_LOOP_STOPPED",
                    "reason": "transition_stopped",
                    "marks": marks,
                    "missions": missions,
                    "transitions": transitions,
                }
        return {
            "status": "MAX_ISLAND_MISSIONS_REACHED",
            "marks": marks,
            "missions": missions,
            "transitions": transitions,
        }

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
    turn_runner = (
        paused_solve_execute_and_end_turn
        if args.paused_solve_execute
        else solve_execute_and_end_turn
    )
    first_turn = turn_runner(
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
        turn_record = turn_runner(
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
    parser.add_argument("--terrain-verify-retry-seconds", type=float, default=1.0)
    parser.add_argument("--max-mission-turns", type=int, default=6)
    parser.add_argument("--confirm-retries", type=int, default=2)
    parser.add_argument("--time-limit", type=float, default=30.0)
    parser.add_argument("--auto-turn-max-wait", type=float, default=5.0)
    parser.add_argument(
        "--full-mission",
        action="store_true",
        help="Continue combat turns until a mission-end/reward panel is visible.",
    )
    parser.add_argument(
        "--island-loop",
        action="store_true",
        help=(
            "Continue clearing missions on the first island until the island "
            "completion transition appears."
        ),
    )
    parser.add_argument(
        "--continue-after-island",
        action="store_true",
        help=(
            "After the island-complete menu appears, leave the island, confirm "
            "unspent reputation loss, clear the next HQ intro, and open the "
            "next island's first mission preview when possible."
        ),
    )
    parser.add_argument("--max-island-missions", type=int, default=5)
    parser.add_argument(
        "--paused-solve-execute",
        action="store_true",
        help=(
            "Experimental: solve while paused, then unpause only to execute "
            "the stored plan and click End Turn."
        ),
    )
    parser.add_argument(
        "--allow-lightning-speed-building-damage",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Allow ordinary post-action building threats when grid power would "
            "survive; useful for Lightning War speed."
        ),
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
