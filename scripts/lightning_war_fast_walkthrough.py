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
    _windows_activate_app_window,
    click_known_window_control,
    click_title_new_game_dynamic,
    click_window_point,
    press_key,
)
from src.loop.commands import (
    _lightning_assign_visual_route_options,
    _lightning_ensure_pause_state,
    _lightning_end_turn_retryable,
    _lightning_extract_red_regions_from_image,
    _lightning_recommend_save_routes,
    _lightning_route_start_candidates,
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
    cmd_verify_setup_screen,
    cmd_verify_action,
)
from src.solver.plan_safety import POD_LOSS_DIRTY_KINDS


APP_NAME = "Into the Breach"
LIGHTNING_UI_BASE_SIZE = (1280, 748)
TIMING_SCREENSHOT_DIR = ROOT / "run_notes" / "lightning_war_walkthrough" / "timing_screenshots"
STARTUP_SCREENSHOT_DIR = (
    ROOT / "run_notes" / "lightning_war_fast_walkthrough" / "startup_screenshots"
)
STARTUP_REVIEW_DIR = (
    ROOT / "run_notes" / "lightning_war_fast_walkthrough" / "startup_reviews"
)
STARTUP_REFERENCE_SCREENSHOT = (
    ROOT / "run_notes" / "lightning_war_fast_walkthrough" / "reference_title_screen.png"
)
STARTUP_LATEST_REVIEW_FILE = STARTUP_REVIEW_DIR / "latest_startup_visual_review.json"
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
MECH_DAMAGE_WARNING_KINDS = {"mech_hp_loss", "mech_status_debt"}
LIGHTNING_SPEED_LOSS_DIRTY_KINDS = {
    "building_destroyed",
    "building_hp_loss",
    "grid_damage",
    "objective_building_destroyed",
    "objective_building_targeted_final",
    "protected_objective_unit_lost",
    "protected_objective_unit_unfrozen",
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


def click_scaled_point(
    name: str,
    base_x: float,
    base_y: float,
    *,
    settle_seconds: float = 0.05,
    hold_seconds: float = 0.3,
) -> dict[str, Any]:
    """Click a point calibrated against ``LIGHTNING_UI_BASE_SIZE``."""
    bounds = get_window_bounds()
    if bounds is None:
        raise FastRunError("could not find Into the Breach window bounds")
    base_w, base_h = LIGHTNING_UI_BASE_SIZE
    x = int(round(base_x * bounds["width"] / base_w))
    y = int(round(base_y * bounds["height"] / base_h))
    return click_point(
        name,
        x,
        y,
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )


def hover_window_point(
    name: str,
    x: int,
    y: int,
    *,
    hover_seconds: float = 0.25,
) -> dict[str, Any]:
    """Move the cursor over a window point before a Windows SendInput click."""
    bounds = get_window_bounds()
    if bounds is None:
        raise FastRunError("could not find Into the Breach window bounds")
    if not sys.platform.startswith("win"):
        return {
            "status": "SKIPPED",
            "reason": "hover pre-positioning is only needed on Windows",
            "name": name,
            "window_x": x,
            "window_y": y,
        }

    import ctypes

    focus_result = _windows_activate_app_window(APP_NAME)
    time.sleep(0.05)
    screen_x = int(bounds["x"] + int(x))
    screen_y = int(bounds["y"] + int(y))
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = ctypes.c_int
    if not user32.SetCursorPos(screen_x, screen_y):
        raise FastRunError(f"hover {name} failed: WinError {ctypes.get_last_error()}")
    time.sleep(max(0.0, hover_seconds))
    return {
        "status": "OK",
        "name": name,
        "window_x": int(x),
        "window_y": int(y),
        "screen_x": screen_x,
        "screen_y": screen_y,
        "hover_seconds": hover_seconds,
        "focus": focus_result,
    }


def click_hovered_point(
    name: str,
    x: int,
    y: int,
    *,
    hover_seconds: float = 0.25,
    settle_seconds: float = 0.05,
    hold_seconds: float = 0.3,
) -> dict[str, Any]:
    hover = hover_window_point(name, x, y, hover_seconds=hover_seconds)
    click = click_point(
        name,
        x,
        y,
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )
    click["pre_hover"] = hover
    return click


def click_scaled_hovered_point(
    name: str,
    base_x: float,
    base_y: float,
    *,
    hover_seconds: float = 0.25,
    settle_seconds: float = 0.05,
    hold_seconds: float = 0.3,
) -> dict[str, Any]:
    bounds = get_window_bounds()
    if bounds is None:
        raise FastRunError("could not find Into the Breach window bounds")
    base_w, base_h = LIGHTNING_UI_BASE_SIZE
    x = int(round(base_x * bounds["width"] / base_w))
    y = int(round(base_y * bounds["height"] / base_h))
    return click_hovered_point(
        name,
        x,
        y,
        hover_seconds=hover_seconds,
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )


def click_setup_start_control(
    *,
    settle_seconds: float = 0.05,
    hold_seconds: float = 0.3,
) -> dict[str, Any]:
    if sys.platform.startswith("win"):
        return click_hovered_point(
            "setup_start",
            1712,
            477,
            hover_seconds=0.28,
            settle_seconds=settle_seconds,
            hold_seconds=hold_seconds,
        )
    return click_control(
        "setup_start",
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )


def click_setup_modal_start_control(
    *,
    settle_seconds: float = 0.05,
    hold_seconds: float = 0.3,
) -> dict[str, Any]:
    if sys.platform.startswith("win"):
        return click_hovered_point(
            "setup_modal_start",
            1704,
            974,
            hover_seconds=0.28,
            settle_seconds=settle_seconds,
            hold_seconds=hold_seconds,
        )
    return click_control(
        "setup_modal_start",
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )


WINDOWS_HOVER_CONTROL_POINTS: dict[str, tuple[int, int]] = {
    "bottom_continue": (1633, 1009),
    "island_archive": (600, 430),
    "mission_preview_board": (1450, 790),
    "panel_continue": (1500, 900),
    "reward_continue": (1647, 985),
}


def click_ui_control(
    control: str,
    *,
    settle_seconds: float = 0.05,
    hold_seconds: float | None = None,
) -> dict[str, Any]:
    if sys.platform.startswith("win") and control in WINDOWS_HOVER_CONTROL_POINTS:
        x, y = WINDOWS_HOVER_CONTROL_POINTS[control]
        return click_hovered_point(
            control,
            x,
            y,
            hover_seconds=0.25,
            settle_seconds=settle_seconds,
            hold_seconds=0.35 if hold_seconds is None else hold_seconds,
        )
    return click_control(
        control,
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )


def startup_setup_screen_name(ui_name: str | None) -> bool:
    """Return whether a startup-only UI label is compatible with setup screen.

    The generic lightning UI detector is tuned for combat/reward flow and can
    call the Blitzkrieg loadout screen ``pause_menu`` on Windows because the
    top setup buttons are lower than its historical crop.
    """
    return ui_name in {"new_game_setup", "pause_menu", "mission_preview_panel"}


def deployment_snapshot_ready(snapshot: dict[str, Any]) -> bool:
    if not isinstance(snapshot, dict) or snapshot.get("status") != "OK":
        return False
    if snapshot.get("in_active_mission") is not True:
        return False
    try:
        turn = int(snapshot.get("turn") if snapshot.get("turn") is not None else -1)
        deployment_zones = int(snapshot.get("deployment_zone_count") or 0)
    except (TypeError, ValueError):
        return False
    return turn == 0 and deployment_zones > 0


def deployment_snapshot_fresh_ready(snapshot: dict[str, Any]) -> bool:
    return (
        deployment_snapshot_ready(snapshot)
        and snapshot.get("bridge_heartbeat_alive") is not False
        and snapshot.get("bridge_heartbeat_stale") is not True
    )


def visible_route_dialogue(visible: dict[str, Any]) -> bool:
    scores = visible.get("scores") or {}
    try:
        dialogue_score = float(
            (scores.get("mission_preview_dialogue") or {}).get("score") or 0.0
        )
    except (TypeError, ValueError):
        dialogue_score = 0.0
    text = visible_text_lower(visible)
    return dialogue_score >= 0.55 or (
        "continue" in text
        and any(
            needle in text
            for needle in (
                "head office",
                "we'll assist",
                "protect the refugees",
                "corporate hq",
            )
        )
    )


def visible_startable_mission_preview(visible: dict[str, Any]) -> bool:
    """True for an island preview that appears to be a real mission card."""
    text = visible_text_lower(visible)
    if "no vek detected" in text:
        return False
    if visible.get("visible_ui") == "mission_preview_panel":
        return True
    return "bonus objectives" in text and (
        "vek detected" in text or "start mission" in text
    )


def visible_deployment_screen(visible: dict[str, Any]) -> bool:
    """Detect deployment even when the generic classifier names it unknown."""
    if visible.get("visible_ui") == "deployment_screen":
        return True
    text = visible_text_lower(visible)
    if "deploying" in text and "drop zone" in text:
        return True
    scores = visible.get("scores") or {}
    deployment = scores.get("deployment_screen") or {}
    try:
        yellow = int(deployment.get("yellow") or 0)
    except (TypeError, ValueError):
        yellow = 0
    return yellow >= 5000


def red_region_key(region: dict[str, Any]) -> str:
    index = region.get("index")
    if index is not None:
        return f"index:{index}"
    try:
        x = int(region.get("window_x"))
        y = int(region.get("window_y"))
    except (TypeError, ValueError):
        return f"object:{id(region)}"
    return f"xy:{round(x / 8) * 8},{round(y / 8) * 8}"


def compact_save_route_recommendation(
    recommendation: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(recommendation, dict):
        return None
    return {
        "status": recommendation.get("status"),
        "source": recommendation.get("source"),
        "routing": recommendation.get("routing"),
        "available": recommendation.get("available"),
        "grid_power": recommendation.get("grid_power"),
        "top3": recommendation.get("top3"),
        "speed_route_status": recommendation.get("speed_route_status"),
    }


def ranked_red_region_candidates(
    regions: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Prefer save-ranked route candidates; fall back to stable visual order."""
    annotated: dict[str, Any] = dict(regions)
    recommendation: dict[str, Any] | None = None
    try:
        recommendation = _lightning_recommend_save_routes(
            "Alpha",
            routing="lightning_war",
        )
        assigned = _lightning_assign_visual_route_options(regions, recommendation)
        if isinstance(assigned, dict):
            annotated = assigned
    except Exception as exc:
        annotated["route_recommendation_error"] = str(exc)

    route_candidates: list[dict[str, Any]] = []
    try:
        raw_candidates = _lightning_route_start_candidates(
            annotated,
            start_mode="region-then-board",
            recommendation=recommendation,
        )
        route_candidates = [
            dict(candidate)
            for candidate in (raw_candidates or [])
            if isinstance(candidate, dict)
        ]
    except Exception as exc:
        annotated["route_candidate_error"] = str(exc)

    regions_by_key = {
        red_region_key(region): dict(region)
        for region in (annotated.get("regions") or [])
        if isinstance(region, dict)
    }
    ordered: list[dict[str, Any]] = []
    used: set[str] = set()

    for candidate in route_candidates:
        key = red_region_key(candidate)
        region = dict(regions_by_key.get(key) or {})
        region.update(
            {
                field: candidate.get(field)
                for field in (
                    "index",
                    "window_x",
                    "window_y",
                    "mission_id",
                    "save_region_index",
                    "save_region_name",
                    "score",
                    "auto_route_allowed",
                    "auto_route_block_reason",
                    "route_option",
                )
                if candidate.get(field) is not None
            }
        )
        if "window_x" not in region or "window_y" not in region:
            continue
        key = red_region_key(region)
        if key in used:
            continue
        ordered.append(region)
        used.add(key)

    fallback_regions = [
        dict(region)
        for region in (annotated.get("regions") or [])
        if isinstance(region, dict)
    ]
    fallback_regions.sort(
        key=lambda item: (
            int(item.get("window_y") or 0),
            int(item.get("window_x") or 0),
            -float(item.get("area_window") or item.get("area_px") or 0),
        )
    )
    for region in fallback_regions:
        key = red_region_key(region)
        if key in used:
            continue
        ordered.append(region)
        used.add(key)

    annotated["save_route_recommendation_compact"] = compact_save_route_recommendation(
        recommendation
    )
    annotated["route_start_candidates_compact"] = [
        {
            key: candidate.get(key)
            for key in (
                "index",
                "window_x",
                "window_y",
                "mission_id",
                "save_region_index",
                "save_region_name",
                "score",
                "auto_route_allowed",
                "auto_route_block_reason",
            )
            if candidate.get(key) is not None
        }
        for candidate in route_candidates
    ]
    annotated["candidate_order"] = [
        {
            key: candidate.get(key)
            for key in (
                "index",
                "window_x",
                "window_y",
                "mission_id",
                "save_region_name",
                "score",
                "auto_route_allowed",
                "auto_route_block_reason",
            )
            if candidate.get(key) is not None
        }
        for candidate in ordered
    ]
    return ordered, annotated


def select_red_region_candidate(
    regions: dict[str, Any],
    *,
    tried_keys: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates, annotated = ranked_red_region_candidates(regions)
    tried = tried_keys or set()
    for candidate in candidates:
        if red_region_key(candidate) not in tried:
            return candidate, annotated
    raise FastRunError(
        "no untried red mission candidates remained: "
        + json.dumps(
            {
                "tried_region_keys": sorted(tried),
                "regions": annotated,
            },
            default=str,
        )
    )


def click_red_region_from_extracted(region: dict[str, Any]) -> dict[str, Any]:
    bounds = get_window_bounds()
    if bounds is None:
        raise FastRunError("could not find Into the Breach window bounds")
    base_w, base_h = LIGHTNING_UI_BASE_SIZE
    scale_x = bounds["width"] / base_w
    scale_y = bounds["height"] / base_h
    live_x = int(round(float(region["window_x"]) * scale_x))
    live_y = int(round(float(region["window_y"]) * scale_y))
    region["live_window_x"] = live_x
    region["live_window_y"] = live_y
    region["live_coordinate_scale"] = {"x": scale_x, "y": scale_y}
    click_hovered_point(
        "red_mission",
        live_x,
        live_y,
        hover_seconds=0.2,
        settle_seconds=0.2,
        hold_seconds=0.35,
    )
    return region


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
    return click_ui_control(
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


def capture_startup_context() -> Path:
    bounds = get_window_bounds()
    if bounds is None:
        raise FastRunError("could not find Into the Breach window bounds")
    STARTUP_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = STARTUP_SCREENSHOT_DIR / f"startup_context_{int(time.time() * 1000)}.png"
    take_screenshot(path, bounds=bounds)
    return path


def visible_ui_name() -> str:
    try:
        return str(_lightning_visible_ui_snapshot().get("visible_ui") or "unknown")
    except Exception as exc:
        return f"unknown:{exc}"


def wait_for_visible_ui(
    expected: set[str],
    *,
    label: str,
    max_seconds: float = 2.0,
    poll_seconds: float = 0.15,
) -> dict[str, Any]:
    """Wait briefly for a click to produce the expected visible UI state."""
    start = time.perf_counter()
    attempts: list[dict[str, Any]] = []
    while True:
        visible = _lightning_visible_ui_snapshot(include_ocr=False)
        compact = compact_visible_ui(visible)
        attempts.append({"elapsed_seconds": elapsed(start), "visible_ui": compact})
        if visible.get("visible_ui") in expected:
            return {
                "status": "OK",
                "label": label,
                "visible_ui": compact,
                "attempts": attempts,
            }
        if time.perf_counter() - start >= max_seconds:
            raise FastRunError(
                json.dumps(
                    {
                        "status": "VISIBLE_UI_TRANSITION_TIMEOUT",
                        "label": label,
                        "expected": sorted(expected),
                        "last_visible_ui": compact,
                        "attempts": attempts,
                    },
                    default=str,
                )
            )
        time.sleep(max(0.01, poll_seconds))


def verify_lightning_setup_modal(*, raise_on_fail: bool = True) -> dict[str, Any]:
    """Verify the Difficulty Setup modal for a Lightning War attempt."""
    result = cmd_verify_setup_screen(
        expected_difficulty=0,
        require_all_advanced=False,
        advanced_content="off",
    )
    if result.get("status") != "PASS" and raise_on_fail:
        raise FastRunError(
            json.dumps(
                {
                    "status": "SETUP_VERIFICATION_FAILED",
                    "verify_setup": result,
                },
                default=str,
            )
        )
    return result


def click_mission_preview_until_deployment(
    *,
    settle_seconds: float,
    max_attempts: int = 3,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for attempt_index in range(1, max_attempts + 1):
        click = click_control("mission_preview_board", settle_seconds=settle_seconds)
        time.sleep(0.15)
        visible = _lightning_visible_ui_snapshot(include_ocr=False)
        snapshot = _lightning_live_snapshot()
        attempt = {
            "attempt": attempt_index,
            "click": click,
            "visible_ui": compact_visible_ui(visible),
            "snapshot": {
                "status": snapshot.get("status"),
                "phase": snapshot.get("phase"),
                "turn": snapshot.get("turn"),
                "in_active_mission": snapshot.get("in_active_mission"),
                "mission_id": snapshot.get("mission_id"),
                "deployment_zone_count": snapshot.get("deployment_zone_count"),
                "bridge_heartbeat_alive": snapshot.get("bridge_heartbeat_alive"),
                "bridge_heartbeat_stale": snapshot.get("bridge_heartbeat_stale"),
            },
        }
        attempts.append(attempt)
        turn = snapshot.get("turn")
        bridge_deployment_ready = (
            snapshot.get("status") == "OK"
            and snapshot.get("in_active_mission") is True
            and int(turn if turn is not None else -1) == 0
            and int(snapshot.get("deployment_zone_count") or 0) > 0
            and snapshot.get("bridge_heartbeat_alive") is not False
            and snapshot.get("bridge_heartbeat_stale") is not True
        )
        if visible.get("visible_ui") == "deployment_screen" or bridge_deployment_ready:
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


def wait_for_title_screen(
    *,
    label: str,
    max_seconds: float = 2.5,
    poll_seconds: float = 0.2,
) -> dict[str, Any]:
    start = time.perf_counter()
    attempts: list[dict[str, Any]] = []
    while True:
        visible = _lightning_visible_ui_snapshot(include_ocr=False)
        compact = compact_visible_ui(visible)
        attempts.append({"elapsed_seconds": elapsed(start), "visible_ui": compact})
        if visible.get("visible_ui") == "title_screen":
            return {
                "status": "OK",
                "label": label,
                "visible_ui": compact,
                "attempts": attempts,
            }
        if time.perf_counter() - start >= max_seconds:
            return {
                "status": "TIMEOUT",
                "label": label,
                "visible_ui": compact,
                "attempts": attempts,
            }
        time.sleep(max(0.01, poll_seconds))


def write_startup_visual_review_request(
    *,
    current_screenshot: Path,
    visible: dict[str, Any],
    attempt_index: int,
) -> dict[str, Any]:
    """Write a Codex-facing startup review request and return its payload."""
    if not STARTUP_REFERENCE_SCREENSHOT.exists():
        raise FastRunError(
            json.dumps(
                {
                    "status": "STARTUP_REFERENCE_SCREENSHOT_MISSING",
                    "expected_path": str(STARTUP_REFERENCE_SCREENSHOT),
                    "current_screenshot_path": str(current_screenshot),
                },
                default=str,
            )
        )

    STARTUP_REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time() * 1000)
    request_path = STARTUP_REVIEW_DIR / f"startup_visual_review_{stamp}.json"
    approval_path = STARTUP_REVIEW_DIR / f"startup_visual_approval_{stamp}.json"
    payload: dict[str, Any] = {
        "status": "PENDING_CODEX_VISUAL_REVIEW",
        "attempt": attempt_index,
        "created_at_unix": time.time(),
        "request_path": str(request_path),
        "latest_request_path": str(STARTUP_LATEST_REVIEW_FILE),
        "approval_path": str(approval_path),
        "reference_screenshot_path": str(STARTUP_REFERENCE_SCREENSHOT),
        "current_screenshot_path": str(current_screenshot),
        "initial_visible_ui": compact_visible_ui(visible),
        "instructions": (
            "Codex should visually compare reference_screenshot_path and "
            "current_screenshot_path. If the current screen is acceptable for "
            "starting from the title/main menu, write approval_path with "
            "{\"action\":\"approve\",\"approved\":true}. If recovery is needed, "
            "write {\"action\":\"recover_to_main_menu\"}. To stop, write "
            "{\"action\":\"abort\"}."
        ),
        "allowed_actions": ["approve", "recover_to_main_menu", "abort"],
    }
    text = json.dumps(payload, default=str, indent=2) + "\n"
    request_path.write_text(text, encoding="utf-8")
    STARTUP_LATEST_REVIEW_FILE.write_text(text, encoding="utf-8")
    log(
        "startup visual review pending: "
        f"reference={STARTUP_REFERENCE_SCREENSHOT} current={current_screenshot} "
        f"approval={approval_path}"
    )
    return payload


def normalize_startup_visual_action(payload: dict[str, Any]) -> str:
    raw = str(payload.get("action") or "").strip().lower().replace("-", "_")
    approved = payload.get("approved")
    if approved is True and not raw:
        raw = "approve"
    if raw in {"approve", "approved", "ok", "go"}:
        return "approve"
    if raw in {"recover", "recover_to_main_menu", "main_menu", "title_screen"}:
        return "recover_to_main_menu"
    if raw in {"abort", "stop", "blocked"} or approved is False:
        return "abort"
    raise FastRunError(
        json.dumps(
            {
                "status": "UNKNOWN_STARTUP_VISUAL_APPROVAL_ACTION",
                "approval": payload,
                "allowed_actions": ["approve", "recover_to_main_menu", "abort"],
            },
            default=str,
        )
    )


def wait_for_startup_visual_approval(
    request: dict[str, Any],
    *,
    timeout_seconds: float,
    poll_seconds: float,
) -> dict[str, Any]:
    approval_path = Path(str(request["approval_path"]))
    start = time.perf_counter()
    last_error: str | None = None
    while True:
        if approval_path.exists():
            try:
                payload = json.loads(approval_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                last_error = str(exc)
            else:
                if not isinstance(payload, dict):
                    raise FastRunError(
                        json.dumps(
                            {
                                "status": "INVALID_STARTUP_VISUAL_APPROVAL",
                                "reason": "approval JSON must be an object",
                                "approval_path": str(approval_path),
                            },
                            default=str,
                        )
                    )
                action = normalize_startup_visual_action(payload)
                payload["action"] = action
                payload["approval_path"] = str(approval_path)
                payload["elapsed_seconds"] = elapsed(start)
                log(f"startup visual review action={action}")
                return payload
        if time.perf_counter() - start >= timeout_seconds:
            raise FastRunError(
                json.dumps(
                    {
                        "status": "STARTUP_VISUAL_REVIEW_TIMEOUT",
                        "timeout_seconds": timeout_seconds,
                        "request": request,
                        "last_error": last_error,
                    },
                    default=str,
                )
            )
        time.sleep(max(0.05, poll_seconds))


def recover_to_title_screen_for_startup(visible: dict[str, Any]) -> dict[str, Any]:
    """Attempt a conservative return to the title screen before another review."""
    result: dict[str, Any] = {
        "status": "STARTED",
        "initial_visible_ui": compact_visible_ui(visible),
    }
    visible_name = visible.get("visible_ui")

    if visible_name == "new_game_setup":
        log("startup recovery on setup screen; clicking Back to main menu")
        result["setup_back"] = click_control("setup_back", settle_seconds=0.8)
        result["title_after_setup_back"] = wait_for_title_screen(
            label="after_setup_back",
            max_seconds=1.5,
        )
        result["status"] = "ATTEMPTED"
        result["reason"] = "clicked_setup_back"
        return result

    log("startup recovery opening pause menu")
    pause = _lightning_ensure_pause_state(reason="fast_walkthrough_startup_main_menu")
    result["pause"] = pause
    pause_visible = None
    pause_verify = pause.get("pause_verify")
    if isinstance(pause_verify, dict):
        pause_visible = pause_verify.get("visible_ui")
    if pause_visible is None and isinstance(pause.get("visible_ui"), dict):
        pause_visible = pause["visible_ui"].get("visible_ui")
    if pause.get("status") != "OK" or pause_visible != "pause_menu":
        result["status"] = "BLOCKED"
        result["reason"] = "could_not_open_pause_menu"
        return result

    log("startup recovery clicking pause menu Main Menu")
    result["pause_main_menu"] = click_control("pause_main_menu", settle_seconds=0.8)
    result["title_after_pause_main_menu"] = wait_for_title_screen(
        label="after_pause_main_menu",
        max_seconds=1.2,
    )

    log("startup recovery confirming Main Menu prompt if present")
    result["main_menu_confirm_yes"] = click_control(
        "abandon_confirm_yes",
        settle_seconds=0.9,
    )
    result["title_after_confirm"] = wait_for_title_screen(
        label="after_main_menu_confirm",
        max_seconds=2.0,
    )
    result["status"] = "ATTEMPTED"
    result["reason"] = "clicked_pause_main_menu"
    return result


def automated_title_screen_preflight(visible: dict[str, Any]) -> dict[str, Any]:
    """Legacy detector-based preflight for explicitly ungated test runs."""
    result: dict[str, Any] = {
        "status": "STARTED",
        "initial_visible_ui": compact_visible_ui(visible),
    }

    if visible.get("visible_ui") == "title_screen":
        result["status"] = "OK"
        result["reason"] = "detector_saw_title_screen"
        return result

    recovery = recover_to_title_screen_for_startup(visible)
    result["recovery"] = recovery
    final_title = wait_for_title_screen(label="after_automated_startup_recovery")
    result["final_title_check"] = final_title
    if final_title.get("status") == "OK":
        result["status"] = "OK"
        result["reason"] = "automated_recovery_verified_title"
        return result

    result["status"] = "BLOCKED"
    result["reason"] = "automated_startup_preflight_not_verified"
    raise FastRunError(json.dumps(result, default=str))


def ensure_title_screen_before_start(args: argparse.Namespace) -> dict[str, Any]:
    """Capture start evidence and normalize to the title screen before timing."""
    result: dict[str, Any] = {
        "status": "STARTED",
        "visual_check_enabled": bool(args.startup_codex_visual_check),
        "reviews": [],
        "recoveries": [],
    }
    max_attempts = max(1, int(args.startup_visual_max_attempts))

    for attempt_index in range(1, max_attempts + 1):
        screenshot = capture_startup_context()
        visible = _lightning_visible_ui_snapshot(include_ocr=True)
        attempt: dict[str, Any] = {
            "attempt": attempt_index,
            "screenshot_path": str(screenshot),
            "visible_ui": compact_visible_ui(visible),
        }
        log(f"startup screenshot={screenshot}")

        if not args.startup_codex_visual_check:
            attempt["automated_preflight"] = automated_title_screen_preflight(visible)
            result["reviews"].append(attempt)
            result["status"] = "OK"
            result["reason"] = "automated_startup_preflight"
            return result

        request = write_startup_visual_review_request(
            current_screenshot=screenshot,
            visible=visible,
            attempt_index=attempt_index,
        )
        approval = wait_for_startup_visual_approval(
            request,
            timeout_seconds=float(args.startup_visual_approval_timeout_seconds),
            poll_seconds=float(args.startup_visual_approval_poll_seconds),
        )
        attempt["visual_review_request"] = request
        attempt["visual_review_approval"] = approval
        result["reviews"].append(attempt)

        action = approval["action"]
        if action == "approve":
            result["status"] = "OK"
            result["reason"] = "codex_approved_start_screen"
            return result
        if action == "abort":
            result["status"] = "BLOCKED"
            result["reason"] = "codex_aborted_startup_visual_review"
            raise FastRunError(json.dumps(result, default=str))

        recovery = recover_to_title_screen_for_startup(visible)
        result["recoveries"].append(recovery)
        if recovery.get("status") == "BLOCKED":
            result["status"] = "BLOCKED"
            result["reason"] = "startup_recovery_blocked"
            raise FastRunError(json.dumps(result, default=str))

    result["status"] = "BLOCKED"
    result["reason"] = "startup_visual_review_attempts_exhausted"
    raise FastRunError(json.dumps(result, default=str))


def click_title_new_game() -> dict[str, Any]:
    log("click title_new_game")
    # The dynamic detector can confuse the title rows with the dimmed Options
    # overlay on this Windows layout. The title menu rows are stable here.
    return click_hovered_point(
        "title_new_game",
        170,
        359,
        hover_seconds=0.25,
        settle_seconds=0.6,
        hold_seconds=0.35,
    )


def click_overwrite_yes_if_present() -> dict[str, Any]:
    """Click the new-run overwrite YES position.

    This occurs before the game timer starts. If no overwrite modal is present,
    this coordinate is harmless on the loadout screen in the tested layout.
    """
    attempts: list[dict[str, Any]] = []
    time.sleep(0.25)
    for attempt_index, hold_seconds in enumerate((0.35, 0.7, 0.7, 0.9), start=1):
        before_ui = visible_ui_name()
        if startup_setup_screen_name(before_ui):
            return {
                "status": "OK",
                "reason": "setup_screen_already_visible",
                "attempts": attempts,
                "visible_ui": before_ui,
            }
        click = click_hovered_point(
            f"overwrite_yes_optional_{attempt_index}",
            1208,
            795,
            hover_seconds=0.25,
            settle_seconds=0.45,
            hold_seconds=hold_seconds,
        )
        time.sleep(0.35)
        after_ui = visible_ui_name()
        attempt = {
            "attempt": attempt_index,
            "hold_seconds": hold_seconds,
            "before_ui": before_ui,
            "click": click,
            "after_ui": after_ui,
        }
        attempts.append(attempt)
        if startup_setup_screen_name(after_ui):
            return {
                "status": "OK",
                "reason": "overwrite_confirmed_to_setup",
                "attempts": attempts,
                "visible_ui": after_ui,
            }
    raise FastRunError(
        json.dumps(
            {
                "status": "OVERWRITE_CONFIRM_DID_NOT_REACH_SETUP",
                "attempts": attempts,
                "visible_ui": visible_ui_name(),
            },
            default=str,
        )
    )


def ensure_blitzkrieg_squad_selected() -> dict[str, Any]:
    """Open squad selection and select Blitzkrieg before the setup modal."""
    steps: list[dict[str, Any]] = []
    for attempt_index, hold_seconds in enumerate((0.35, 0.7), start=1):
        click = click_scaled_hovered_point(
            "change_squad",
            807.5,
            558.3,
            settle_seconds=0.8,
            hold_seconds=hold_seconds,
        )
        ui = visible_ui_name()
        steps.append(
            {
                "phase": "change_squad",
                "attempt": attempt_index,
                "hold_seconds": hold_seconds,
                "click": click,
                "visible_ui": ui,
            }
        )
        if ui != "new_game_setup":
            break
    time.sleep(0.25)
    for attempt_index, hold_seconds in enumerate((0.35, 0.7, 0.7), start=1):
        click = click_scaled_hovered_point(
            "select_blitzkrieg_squad",
            805.0,
            370.2,
            settle_seconds=0.9,
            hold_seconds=hold_seconds,
        )
        time.sleep(0.35)
        ui = visible_ui_name()
        steps.append(
            {
                "phase": "select_blitzkrieg",
                "attempt": attempt_index,
                "hold_seconds": hold_seconds,
                "click": click,
                "visible_ui": ui,
            }
        )
        if startup_setup_screen_name(ui):
            return {"status": "OK", "steps": steps, "visible_ui": ui}
    raise FastRunError(
        json.dumps(
            {
                "status": "BLITZKRIEG_SELECTION_DID_NOT_COMMIT",
                "steps": steps,
                "visible_ui": visible_ui_name(),
            },
            default=str,
        )
    )


def open_lightning_setup_modal_from_squad_screen() -> dict[str, Any]:
    """Click setup Start until the Easy/AE-off modal is really visible."""
    attempts: list[dict[str, Any]] = []
    for attempt_index, hold_seconds in enumerate((0.35, 0.7, 0.7, 0.7), start=1):
        click = click_setup_start_control(
            settle_seconds=0.75,
            hold_seconds=hold_seconds,
        )
        verify = verify_lightning_setup_modal(raise_on_fail=False)
        attempt = {
            "attempt": attempt_index,
            "hold_seconds": hold_seconds,
            "click": click,
            "verify_setup": verify,
            "visible_ui": visible_ui_name(),
        }
        attempts.append(attempt)
        if verify.get("status") == "PASS":
            return {"status": "OK", "attempts": attempts}
    raise FastRunError(
        json.dumps(
            {
                "status": "SETUP_MODAL_DID_NOT_OPEN",
                "attempts": attempts,
            },
            default=str,
        )
    )


def click_setup_modal_start_until_committed() -> dict[str, Any]:
    """Click final modal Start until the Difficulty Setup modal disappears."""
    attempts: list[dict[str, Any]] = []
    for attempt_index, hold_seconds in enumerate((0.35, 0.7, 0.7, 0.7), start=1):
        click = click_setup_modal_start_control(
            settle_seconds=0.45,
            hold_seconds=hold_seconds,
        )
        time.sleep(0.35)
        verify = verify_lightning_setup_modal(raise_on_fail=False)
        attempt = {
            "attempt": attempt_index,
            "hold_seconds": hold_seconds,
            "click": click,
            "verify_setup": verify,
            "visible_ui": visible_ui_name(),
        }
        attempts.append(attempt)
        if verify.get("status") != "PASS":
            return {"status": "OK", "attempts": attempts}
    raise FastRunError(
        json.dumps(
            {
                "status": "SETUP_MODAL_START_DID_NOT_COMMIT",
                "attempts": attempts,
            },
            default=str,
        )
    )


def click_largest_red_mission() -> dict[str, Any]:
    last_regions: dict[str, Any] | None = None
    last_visible: dict[str, Any] | None = None
    for scan_attempt in range(1, 5):
        visible = _lightning_visible_ui_snapshot(include_ocr=True)
        last_visible = visible
        visible_name = visible.get("visible_ui")
        if visible_name in {"title_screen", "new_game_setup"}:
            raise FastRunError(
                json.dumps(
                    {
                        "status": "ROUTE_SCREEN_NOT_REACHED",
                        "visible_ui": compact_visible_ui(visible),
                    },
                    default=str,
                )
            )
        if visible_route_dialogue(visible):
            click = click_transition_control("bottom_continue", settle_seconds=0.35)
            log(
                "cleared route dialogue during red mission scan: "
                + json.dumps(
                    {
                        "attempt": scan_attempt,
                        "visible_ui": compact_visible_ui(visible),
                        "click": click,
                    },
                    default=str,
                )
            )
            time.sleep(0.35)
            continue

        shot = capture("lw_red")
        bounds = get_window_bounds()
        if bounds is None:
            raise FastRunError("could not find Into the Breach window bounds")
        regions = _lightning_extract_red_regions_from_image(shot)
        last_regions = regions
        log(f"red mission regions={regions.get('region_count')} screenshot={shot}")
        candidates = [
            region
            for region in (regions.get("regions") or [])
            if isinstance(region, dict)
        ]
        if candidates:
            region, annotated = select_red_region_candidate(regions)
            break
        time.sleep(0.25)
    else:
        raise FastRunError(
            "no red mission regions detected: "
            + json.dumps(
                {
                    "regions": last_regions,
                    "visible_ui": compact_visible_ui(last_visible or {}),
                },
                default=str,
            )
        )

    region["selection"] = {
        "strategy": "ranked_route_candidate",
        "candidate_order": annotated.get("candidate_order"),
        "route_assignment": annotated.get("route_assignment"),
        "save_route_recommendation": annotated.get(
            "save_route_recommendation_compact"
        ),
    }
    return click_red_region_from_extracted(region)


def _red_region_signature(regions: list[dict[str, Any]]) -> tuple[tuple[int, int], ...]:
    """Compact map-region signature for waiting out island-map animations."""
    points: list[tuple[int, int]] = []
    for region in regions:
        try:
            x = int(region.get("window_x"))
            y = int(region.get("window_y"))
        except (TypeError, ValueError):
            continue
        points.append((round(x / 8) * 8, round(y / 8) * 8))
    return tuple(sorted(points))


def wait_for_red_mission_regions_stable(
    *,
    min_wait_seconds: float = 2.0,
    max_wait_seconds: float = 5.0,
    interval_seconds: float = 0.75,
) -> dict[str, Any]:
    """Wait for the island map's red mission candidates to settle.

    Region Secured and Hive Leader transitions can temporarily leave old red
    regions visible. Sampling until the candidate signature stops changing
    avoids clicking a mission from the transitional frame.
    """
    started = time.perf_counter()
    last_signature: tuple[tuple[int, int], ...] | None = None
    stable_samples = 0
    latest: dict[str, Any] | None = None
    samples: list[dict[str, Any]] = []

    while True:
        shot = capture("lw_red_settle")
        regions = _lightning_extract_red_regions_from_image(shot)
        candidates = [
            region
            for region in (regions.get("regions") or [])
            if isinstance(region, dict)
        ]
        signature = _red_region_signature(candidates)
        elapsed_seconds = time.perf_counter() - started
        sample = {
            "t": round(elapsed_seconds, 3),
            "screenshot": str(shot),
            "region_count": regions.get("region_count"),
            "signature": signature,
            "status": regions.get("status"),
        }
        samples.append(sample)
        latest = {"regions": regions, "screenshot": shot, "samples": samples}

        if signature and signature == last_signature:
            stable_samples += 1
        else:
            stable_samples = 1 if signature else 0
            last_signature = signature

        if (
            signature
            and elapsed_seconds >= min_wait_seconds
            and stable_samples >= 2
        ):
            latest["status"] = "OK"
            latest["stable_signature"] = signature
            latest["stable_samples"] = stable_samples
            return latest
        if elapsed_seconds >= max_wait_seconds:
            if candidates:
                latest["status"] = "TIMEOUT_WITH_REGIONS"
                latest["stable_signature"] = signature
                latest["stable_samples"] = stable_samples
                return latest
            raise FastRunError(
                "no red mission regions detected after settle wait: "
                + json.dumps(samples, default=str)
            )
        time.sleep(max(0.05, interval_seconds))


def click_stable_red_mission_after_result() -> dict[str, Any]:
    visible = _lightning_visible_ui_snapshot(include_ocr=False)
    visible_name = visible.get("visible_ui")
    if visible_name in {"title_screen", "new_game_setup"}:
        raise FastRunError(
            json.dumps(
                {
                    "status": "ROUTE_SCREEN_NOT_REACHED",
                    "visible_ui": compact_visible_ui(visible),
                },
                default=str,
            )
        )
    settled = wait_for_red_mission_regions_stable()
    regions = settled.get("regions") or {}
    candidates = regions.get("regions") or []
    if not candidates:
        raise FastRunError(f"no red mission regions detected: {regions}")
    region, annotated = select_red_region_candidate(regions)
    region["settle"] = {
        "status": settled.get("status"),
        "stable_signature": settled.get("stable_signature"),
        "stable_samples": settled.get("stable_samples"),
        "samples": settled.get("samples"),
        "candidate_order": annotated.get("candidate_order"),
        "route_assignment": annotated.get("route_assignment"),
        "save_route_recommendation": annotated.get(
            "save_route_recommendation_compact"
        ),
    }
    log(
        "settled red mission regions="
        f"{regions.get('region_count')} status={settled.get('status')}"
    )
    return click_red_region_from_extracted(region)


def deploy_and_confirm(*, confirm_retries: int) -> dict[str, Any]:
    log("deploy_recommended")
    deploy = cmd_deploy_recommended(ui_fallback=False, verify_after=False)
    deploy_retries: list[dict[str, Any]] = []

    def deploy_acceptable(result: dict[str, Any]) -> bool:
        return result.get("status") == "OK"

    def compact_deploy(result: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": result.get("status"),
            "reason": result.get("reason"),
            "deployment_count": len(result.get("deployments") or []),
            "phase": result.get("phase"),
            "ui_fallback_status": (
                result.get("ui_fallback", {}) or {}
            ).get("status"),
        }

    if not deploy_acceptable(deploy):
        raise FastRunError(f"deploy_recommended failed: {deploy}")
    if deploy.get("status") != "OK":
        log(f"deploy accepted warning: {deploy.get('reason')}")

    attempts: list[dict[str, Any]] = []
    for attempt in range(1, max(1, confirm_retries) + 1):
        click_control("deploy_confirm", settle_seconds=0.05)
        wait = _lightning_wait_for_deploy_confirm_live_bridge(
            max_seconds=2.0,
            interval_seconds=0.15,
        )
        attempts.append(wait)
        log(
            "confirm attempt "
            f"{attempt}: {wait.get('status')} {wait.get('reason')} "
            f"phase={wait.get('snapshot', {}).get('phase')}"
        )
        if wait.get("status") == "OK":
            snapshot = wait.get("snapshot") or {}
            visible_name = visible_ui_name()
            confirm_still_pending = (
                visible_name == "deployment_screen"
                and snapshot.get("phase") == "combat_enemy"
                and int(snapshot.get("active_mechs") or 0) > 0
                and int(snapshot.get("deployment_zone_count") or 0) > 0
            )
            if confirm_still_pending:
                attempts[-1]["confirm_still_pending"] = True
                attempts[-1]["visible_ui"] = visible_name
                log("confirm still pending; retrying deployment for missing units")
                redeploy = cmd_deploy_recommended(
                    ui_fallback=False,
                    verify_after=False,
                )
                deploy_retries.append(redeploy)
                attempts[-1]["redeploy_after_pending_confirm"] = (
                    compact_deploy(redeploy)
                )
                if not deploy_acceptable(redeploy):
                    log(
                        "redeploy after pending confirm failed: "
                        f"{compact_deploy(redeploy)}"
                    )
                    continue
                if redeploy.get("status") != "OK":
                    log(
                        "redeploy accepted warning: "
                        f"{redeploy.get('reason')}"
                    )
                continue
            return {
                "status": "OK",
                "deploy": deploy,
                "deploy_retries": deploy_retries,
                "confirm_attempts": attempts,
                "snapshot": snapshot,
            }
    raise FastRunError(
        json.dumps(
            {
                "status": "DEPLOY_CONFIRM_BLOCKED",
                "deploy": compact_deploy(deploy),
                "deploy_retries": [compact_deploy(item) for item in deploy_retries],
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
    control_history: list[str] | None = None,
) -> str:
    visible_name = visible.get("visible_ui")
    text = visible_text_lower(visible)
    history = control_history or []
    scores = visible.get("scores") or {}
    dialogue_score = float(
        (scores.get("mission_preview_dialogue") or {}).get("score") or 0.0
    )
    bridge_refine = visible.get("bridge_refine_snapshot") or {}
    inactive_terminal_screen = (
        bridge_refine.get("status") == "OK"
        and bridge_refine.get("in_active_mission") is False
        and int(bridge_refine.get("active_mechs") or 0) == 0
    )
    try:
        bridge_turn = int(bridge_refine.get("turn"))
    except (TypeError, ValueError):
        bridge_turn = -1
    turn_zero_deployment_dialogue = (
        bridge_refine.get("status") == "OK"
        and bridge_refine.get("in_active_mission") is True
        and bridge_turn == 0
        and int(bridge_refine.get("deployment_zone_count") or 0) > 0
        and dialogue_score >= 0.5
    )

    if "leave island" in text and "continue" in text and "yes" in text:
        return "leave_confirm_yes"
    if "spend reputation" in text and "leave island" in text:
        return "leave_island"
    if "head office" in text and "continue" in text:
        return "bottom_continue"
    if turn_zero_deployment_dialogue:
        return "bottom_continue"
    if visible_name == "mission_preview_panel" and dialogue_score >= 0.5:
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
        scores = visible.get("scores") or {}
        choice_score = float(
            (scores.get("perfect_reward_choice") or {}).get("score") or 0.0
        )
        dark_overlay = float(visible.get("dark_overlay_fraction") or 0.0)
        if inactive_terminal_screen:
            return "reward_continue"
        if dark_overlay >= 0.85 and dialogue_score >= 0.5 and choice_score >= 0.25:
            return "reward_continue"
        if dark_overlay >= 0.85 and choice_score >= 0.25:
            if {"panel_continue", "bottom_continue"} & set(history):
                return "perfect_reward_grid"
            return "panel_continue"
        return "menu_continue"
    if (
        inactive_terminal_screen
        and dialogue_score >= 0.5
        and "dialogue_textbox" not in history
    ):
        return "dialogue_textbox"
    if visible_name == "promotion_panel":
        return "modal_understood"
    if visible_name == "kia_panel" and previous_control == "pod_open_door":
        return "reward_continue"
    if visible_name == "kia_panel" and visible.get("recommended_control") == "kia_understood":
        return "modal_understood"
    if visible_name == "pod_open_panel":
        return "pod_open_door"
    if visible_name == "perfect_island_panel":
        if previous_control == "panel_continue" or "panel_continue" in history:
            return "leave_island"
        return "panel_continue"
    if visible_name == "perfect_reward_choice":
        if previous_control in {"panel_continue", "bottom_continue"}:
            return "perfect_reward_grid"
        return "reward_continue"
    if visible_name == "island_map" and previous_control == "reward_continue":
        return "leave_island"
    if previous_control == "pod_open_door":
        return "reward_continue"
    if (
        visible_name == "island_map_or_unknown"
        and previous_control == "modal_understood"
        and "pod_open_door" not in history
    ):
        return "pod_open_door"
    if visible_name == "island_map_or_unknown" and previous_control == "reward_continue":
        modal_count = history.count("modal_understood")
        if modal_count == 0:
            return "modal_understood"
        if "pod_open_door" not in history:
            return "pod_open_door"
        if modal_count < 2:
            return "modal_understood"
        return "reward_continue"
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
    record_timing_screenshots: bool = False,
    ocr_result_audit: bool = False,
) -> dict[str, Any]:
    log(f"wait at least {min_wait_seconds:.1f}s after Turn {turn_index} End Turn")
    start = time.perf_counter()
    time.sleep(max(0.0, min_wait_seconds))
    samples: list[dict[str, Any]] = []
    first_bridge_terminal_elapsed: float | None = None
    while True:
        elapsed_after_end = round(time.perf_counter() - start, 3)
        sample_shot = (
            capture_timing(f"turn_{turn_index}_post_end")
            if record_timing_screenshots
            else None
        )
        visible = _lightning_visible_ui_snapshot(include_ocr=False)
        try:
            snapshot = _lightning_live_snapshot()
        except Exception as exc:
            snapshot = {"status": "ERROR", "error": str(exc)}
        sample = {
            "elapsed_after_end_turn_seconds": elapsed_after_end,
            "game_timer_seconds": elapsed(timer_start),
            "screenshot_path": str(sample_shot) if sample_shot else None,
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
            f"shot={sample_shot or 'off'}"
        )
        if visible.get("status") == "OK" and visible_name in TERMINAL_OR_CLEAR_UIS:
            audited_visible = (
                _lightning_visible_ui_snapshot(include_ocr=True)
                if ocr_result_audit
                else visible
            )
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
                audited_visible = (
                    _lightning_visible_ui_snapshot(include_ocr=True)
                    if ocr_result_audit
                    else _lightning_visible_ui_snapshot(include_ocr=False)
                )
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


def _lightning_investigation_diff_is_non_worse(diff: Any) -> bool:
    if not isinstance(diff, dict):
        return False
    try:
        predicted = int(diff.get("predicted"))
        actual = int(diff.get("actual"))
    except (TypeError, ValueError):
        return False
    return actual >= predicted


def _lightning_investigate_is_allowed_speed_trade(turn: dict[str, Any]) -> bool:
    """True when an INVESTIGATE result only found benign allowed-loss diffs."""
    if turn.get("status") != "INVESTIGATE":
        return False
    if not turn.get("pending_end_turn_batch"):
        return False
    threat_audit = turn.get("threat_audit") or {}
    if threat_audit.get("status") not in {None, "OK"}:
        return False
    if int(threat_audit.get("still_threatened_count") or 0) > 0:
        return False

    investigations = turn.get("investigations") or []
    if not investigations:
        return False
    for investigation in investigations:
        if not isinstance(investigation, dict):
            return False
        snapshot_path = investigation.get("snapshot_path")
        if not snapshot_path:
            return False
        context_path = Path(snapshot_path) / "context.json"
        try:
            context = json.loads(context_path.read_text())
        except (OSError, json.JSONDecodeError):
            return False

        grid_diff = context.get("grid_power_diff")
        if grid_diff is not None and not _lightning_investigation_diff_is_non_worse(
            grid_diff
        ):
            return False

        building_diffs = context.get("building_hp_diffs") or []
        if not isinstance(building_diffs, list):
            return False
        for diff in building_diffs:
            if not _lightning_investigation_diff_is_non_worse(diff):
                return False
    return True


def plan_safety_violation_kinds(
    plan_safety: dict[str, Any] | None,
    *,
    blocking: bool | None = None,
) -> set[str]:
    if not isinstance(plan_safety, dict):
        return set()
    kinds: set[str] = set()
    for violation in plan_safety.get("violations", []) or []:
        if not isinstance(violation, dict):
            continue
        if blocking is not None and bool(violation.get("blocking")) != blocking:
            continue
        kind = violation.get("kind")
        if kind:
            kinds.add(str(kind))
    return kinds


def _int_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def lightning_speed_loss_policy(
    plan_safety: dict[str, Any] | None,
    *,
    blocking_kinds: set[str],
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    if not blocking_kinds:
        return None

    allowed = set()
    if bool(args.ignore_lightning_time_pod):
        allowed |= set(POD_LOSS_DIRTY_KINDS)
    if bool(args.allow_lightning_speed_building_damage):
        allowed |= LIGHTNING_SPEED_LOSS_DIRTY_KINDS
    if not blocking_kinds <= allowed:
        return None

    predicted_grid = _int_value((plan_safety or {}).get("predicted", {}).get("grid_power"))
    if predicted_grid is None or predicted_grid <= 0:
        return None

    return {
        "status": "ALLOWED",
        "reason": "lightning_speed_loss_policy",
        "blocking_kinds": sorted(blocking_kinds),
        "predicted_grid_power": predicted_grid,
    }


def lightning_speed_frontier_rank(
    solve: dict[str, Any],
    *,
    args: argparse.Namespace,
) -> int | None:
    if not bool(args.allow_lightning_speed_building_damage):
        return None
    plan_safety = solve.get("plan_safety") or {}
    current_grid = _int_value(plan_safety.get("current", {}).get("grid_power"))
    if current_grid is None:
        return None

    allowed = set(LIGHTNING_SPEED_LOSS_DIRTY_KINDS)
    if bool(args.ignore_lightning_time_pod):
        allowed |= set(POD_LOSS_DIRTY_KINDS)

    entries = [
        entry
        for entry in (solve.get("dirty_frontier") or [])
        if isinstance(entry, dict) and isinstance(entry.get("best_rank"), int)
    ]
    entries.sort(key=lambda entry: int(entry.get("best_rank") or 0))

    for entry in entries:
        violations = [
            v for v in (entry.get("violations") or [])
            if isinstance(v, dict) and v.get("kind")
        ]
        kinds = {str(v.get("kind")) for v in violations}
        if not kinds or not kinds <= allowed:
            continue
        losses = entry.get("losses") or {}
        grid_loss = _int_value(losses.get("grid_power")) or 0
        if current_grid - grid_loss <= 0:
            continue
        return int(entry["best_rank"])
    return None


def select_lightning_fast_solve(
    solve: dict[str, Any],
    *,
    turn_index: int,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    blocking_kinds = plan_safety_violation_kinds(
        solve.get("plan_safety"),
        blocking=True,
    )
    if not blocking_kinds:
        return solve, None
    if lightning_speed_loss_policy(
        solve.get("plan_safety"),
        blocking_kinds=blocking_kinds,
        args=args,
    ):
        return solve, None

    rank = lightning_speed_frontier_rank(solve, args=args)
    if rank is None:
        return solve, None

    log(f"selecting Lightning speed-loss candidate rank {rank}")
    selected = cmd_solve(time_limit=args.time_limit, candidate_rank=rank)
    if selected.get("error"):
        raise FastRunError(
            f"paused solve failed for Lightning speed candidate rank {rank} "
            f"on turn {turn_index}: {selected}"
        )
    return selected, {
        "status": "SELECTED",
        "candidate_rank": rank,
        "reason": "lightning_speed_frontier_rank",
    }


def check_lightning_fast_solve_policy(
    solve: dict[str, Any],
    *,
    turn_index: int,
    args: argparse.Namespace,
) -> dict[str, Any]:
    plan_safety = solve.get("plan_safety")
    blocking_kinds = plan_safety_violation_kinds(plan_safety, blocking=True)
    warning_kinds = plan_safety_violation_kinds(plan_safety, blocking=False)

    if blocking_kinds:
        if (
            bool(args.ignore_lightning_time_pod)
            and blocking_kinds <= set(POD_LOSS_DIRTY_KINDS)
        ):
            return {
                "status": "ALLOWED",
                "reason": "lightning_time_pod_ignored",
                "blocking_kinds": sorted(blocking_kinds),
            }
        speed_loss = lightning_speed_loss_policy(
            plan_safety,
            blocking_kinds=blocking_kinds,
            args=args,
        )
        if speed_loss is not None:
            return speed_loss
        raise FastRunError(
            json.dumps(
                {
                    "status": "PAUSED_SOLVE_SAFETY_BLOCKED",
                    "turn_index": turn_index,
                    "blocking_kinds": sorted(blocking_kinds),
                    "warning_kinds": sorted(warning_kinds),
                    "ignore_lightning_time_pod": args.ignore_lightning_time_pod,
                    "plan_safety": plan_safety,
                    "dirty_frontier": solve.get("dirty_frontier"),
                    "actions": solve.get("actions"),
                },
                default=str,
            )
        )

    mech_warning_kinds = warning_kinds & MECH_DAMAGE_WARNING_KINDS
    if mech_warning_kinds and not bool(args.allow_lightning_speed_mech_damage):
        raise FastRunError(
            json.dumps(
                {
                    "status": "PAUSED_SOLVE_MECH_DAMAGE_BLOCKED",
                    "turn_index": turn_index,
                    "warning_kinds": sorted(mech_warning_kinds),
                    "allow_lightning_speed_mech_damage": (
                        args.allow_lightning_speed_mech_damage
                    ),
                    "plan_safety": plan_safety,
                    "dirty_frontier": solve.get("dirty_frontier"),
                    "actions": solve.get("actions"),
                },
                default=str,
            )
        )

    return {
        "status": "OK",
        "blocking_kinds": sorted(blocking_kinds),
        "warning_kinds": sorted(warning_kinds),
    }


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
    empty_solution_fallback = None
    allowed_investigate_speed_trade = (
        args.allow_lightning_speed_building_damage
        and _lightning_investigate_is_allowed_speed_trade(turn)
    )
    if allowed_investigate_speed_trade:
        log(
            "auto_turn INVESTIGATE only found non-worse grid/building diffs; "
            "continuing under Lightning speed policy"
        )
        turn_plan_ready = True

    if turn.get("status") not in {"OK", "PASS"} and not turn_plan_ready:
        error_text = str(turn.get("error") or turn.get("warning") or "")
        if "Empty solution" in error_text:
            fallback_read = cmd_read()
            empty_solution_fallback = {
                "reason": "empty_solution_no_buildings_threatened",
                "read": fallback_read,
            }
            if (
                args.allow_lightning_speed_building_damage
                and fallback_read.get("phase") == "combat_player"
                and int(fallback_read.get("active_mechs") or 0) >= 0
                and int(fallback_read.get("threatened_buildings") or 0) == 0
            ):
                log(
                    "auto_turn empty solution; no buildings threatened, "
                    "clicking End Turn under Lightning speed policy"
                )
                turn = {
                    "status": "LIGHTNING_EMPTY_SOLUTION_END_TURN",
                    "turn": fallback_read.get("turn", turn.get("turn")),
                    "actions_completed": 0,
                    "original_auto_turn": turn,
                    "fallback_read": fallback_read,
                }
                turn_plan_ready = True
            else:
                raise FastRunError(
                    f"auto_turn failed on turn {turn_index}: {turn}; "
                    f"fallback_read={fallback_read}"
                )
        else:
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
            record_timing_screenshots=args.record_timing_screenshots,
            ocr_result_audit=args.ocr_result_audit,
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
        "empty_solution_fallback": empty_solution_fallback,
        "turn": turn.get("turn"),
        "end_turn_observed": observed,
        "end_turn_retry_click": retry_click,
        "end_turn_retry_observed": retry_observed,
        "post_end_turn": post_end,
    }


def refresh_bridge_before_paused_solve(*, turn_index: int) -> dict[str, Any]:
    """Make the bridge fresh before solving from an otherwise paused turn."""
    visible = _lightning_visible_ui_snapshot(include_ocr=False)
    if visible.get("visible_ui") != "pause_menu":
        heartbeat = wait_for_fresh_heartbeat(
            label=f"turn_{turn_index}_live_before_solve",
            max_seconds=2.0,
        )
        return {
            "status": "ALREADY_LIVE",
            "visible_ui": compact_visible_ui(visible),
            "heartbeat": heartbeat,
        }

    click = click_control("menu_continue", settle_seconds=0.15)
    heartbeat = wait_for_fresh_heartbeat(
        label=f"turn_{turn_index}_refresh_before_paused_solve",
        max_seconds=3.0,
    )
    pause = press_key(
        "esc",
        description=f"pause after bridge refresh before turn {turn_index} solve",
        app_name=APP_NAME,
        settle_seconds=0.25,
    )
    return {
        "status": "REFRESHED_AND_PAUSED",
        "visible_ui": compact_visible_ui(visible),
        "menu_continue": click,
        "heartbeat": heartbeat,
        "pause": pause,
    }


def paused_solve_execute_and_end_turn(
    *,
    turn_index: int,
    timer_start: float,
    args: argparse.Namespace,
) -> dict[str, Any]:
    log(f"paused solve turn={turn_index}")
    bridge_refresh = refresh_bridge_before_paused_solve(turn_index=turn_index)
    refresh_mark = elapsed(timer_start)
    paused_read = cmd_read()
    paused_read_mark = elapsed(timer_start)
    solve = cmd_solve(time_limit=args.time_limit)
    paused_solve_done_mark = elapsed(timer_start)
    if solve.get("error"):
        raise FastRunError(f"paused solve failed on turn {turn_index}: {solve}")
    speed_candidate_selection = None
    solve, speed_candidate_selection = select_lightning_fast_solve(
        solve,
        turn_index=turn_index,
        args=args,
    )
    actions = solve.get("actions") or []
    if not actions:
        raise FastRunError(f"paused solve returned no actions on turn {turn_index}: {solve}")
    solve_safety_policy = check_lightning_fast_solve_policy(
        solve,
        turn_index=turn_index,
        args=args,
    )

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
        execution_record = {
            "action_index": action_index,
            "execute": executed,
            "click_dispatch": click_dispatch,
            "verify": verified,
            "delayed_verify_retry": delayed_verify_retry,
        }
        executions.append(execution_record)
        if verified.get("status") != "PASS":
            if (
                bool(args.ignore_verify_desyncs)
                and verified.get("status") == "DESYNC"
            ):
                execution_record["ignored_verify_desync"] = True
                log(
                    "ignoring verify desync under Lightning fast policy: "
                    f"action={action_index} "
                    f"categories={verified.get('categories')} "
                    f"failure_id={verified.get('failure_id')}"
                )
                continue
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
            record_timing_screenshots=args.record_timing_screenshots,
            ocr_result_audit=args.ocr_result_audit,
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
            "bridge_refresh_for_solve": refresh_mark,
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
            "source": paused_read.get("source"),
        },
        "bridge_refresh": bridge_refresh,
        "heartbeat": heartbeat,
        "solve_status": solve.get("status") or ("OK" if not solve.get("error") else "ERROR"),
        "speed_candidate_selection": speed_candidate_selection,
        "solve_safety_policy": solve_safety_policy,
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


def route_to_deployment(
    *,
    timer_start: float,
    args: argparse.Namespace,
    mission_index: int,
    preview_already_open: bool = False,
    max_steps: int = 14,
) -> dict[str, Any]:
    """Advance route UI until turn-zero deployment is visible or bridge-proven."""
    steps: list[dict[str, Any]] = []
    region: dict[str, Any] | None = None
    preview: dict[str, Any] | None = None
    preview_open = bool(preview_already_open)
    tried_region_keys: set[str] = set()

    if not preview_open:
        time.sleep(args.red_wait_seconds)

    for step_index in range(1, max_steps + 1):
        visible = _lightning_visible_ui_snapshot(include_ocr=True)
        try:
            snapshot = _lightning_live_snapshot()
        except Exception as exc:
            snapshot = {"status": "ERROR", "error": str(exc)}
        visible_name = visible.get("visible_ui")
        dialogue_visible = visible_route_dialogue(visible)
        startable_preview_visible = visible_startable_mission_preview(visible)
        if isinstance(snapshot, dict):
            visible["bridge_refine_snapshot"] = snapshot
        step: dict[str, Any] = {
            "step": step_index,
            "game_timer_seconds": elapsed(timer_start),
            "preview_open": preview_open,
            "dialogue_visible": dialogue_visible,
            "startable_preview_visible": startable_preview_visible,
            "tried_region_keys": sorted(tried_region_keys),
            "visible_ui": compact_visible_ui(visible),
            "live_snapshot": compact_live_snapshot(snapshot),
        }

        if visible_deployment_screen(visible) or (
            deployment_snapshot_fresh_ready(snapshot) and not dialogue_visible
        ):
            step["result"] = "deployment_ready"
            steps.append(step)
            return {
                "status": "DEPLOYMENT_READY",
                "mission_index": mission_index,
                "steps": steps,
                "red_region": region,
                "preview": preview
                or {
                    "status": "ALREADY_DEPLOYMENT",
                    "reason": "route_state_machine",
                },
            }

        if visible_name == "pause_menu":
            step["control"] = "menu_continue"
            step["reason"] = "route_unpause_before_transition"
            step["click"] = click_transition_control(
                "menu_continue",
                settle_seconds=0.35,
            )
            steps.append(step)
            time.sleep(0.25)
            continue

        if dialogue_visible:
            control = clear_control_for_visible_ui(
                visible,
                previous_control=(
                    str(steps[-1].get("control")) if steps and steps[-1].get("control") else None
                ),
                control_history=[
                    str(item.get("control"))
                    for item in steps
                    if item.get("control")
                ],
            )
            if control not in {
                "bottom_continue",
                "dialogue_textbox",
                "mission_preview_board",
                "panel_continue",
                "reward_continue",
            }:
                control = "bottom_continue"
            step["control"] = control
            step["click"] = click_transition_control(control, settle_seconds=0.35)
            steps.append(step)
            time.sleep(0.25)
            continue

        if preview_open or startable_preview_visible:
            try:
                preview = click_mission_preview_until_deployment(
                    settle_seconds=args.preview_settle_seconds,
                )
            except FastRunError as exc:
                step["preview_error"] = str(exc)
                preview_open = False
                steps.append(step)
                time.sleep(0.35)
                continue
            step["preview"] = preview
            steps.append(step)
            return {
                "status": "DEPLOYMENT_READY",
                "mission_index": mission_index,
                "steps": steps,
                "red_region": region,
                "preview": preview,
            }

        if deployment_snapshot_ready(snapshot):
            step["control"] = "bottom_continue"
            step["reason"] = "deployment_bridge_visible_not_ready"
            step["click"] = click_transition_control("bottom_continue", settle_seconds=0.35)
            steps.append(step)
            time.sleep(0.25)
            continue

        if not preview_open:
            shot = capture(f"lw_route_m{mission_index}_step{step_index}")
            regions = _lightning_extract_red_regions_from_image(shot)
            candidates = [
                item
                for item in (regions.get("regions") or [])
                if isinstance(item, dict)
            ]
            step["red_scan"] = {
                "screenshot_path": str(shot),
                "status": regions.get("status"),
                "region_count": regions.get("region_count"),
                "candidate_count": len(candidates),
            }
            if candidates:
                region, annotated = select_red_region_candidate(
                    regions,
                    tried_keys=tried_region_keys,
                )
                tried_region_keys.add(red_region_key(region))
                step["red_scan"]["candidate_order"] = annotated.get("candidate_order")
                step["red_scan"]["route_assignment"] = annotated.get(
                    "route_assignment"
                )
                step["red_scan"]["save_route_recommendation"] = annotated.get(
                    "save_route_recommendation_compact"
                )
                step["red_region"] = click_red_region_from_extracted(region)
                step["control"] = "red_mission"
                step["preview_open_after_click"] = True
                preview_open = True
                steps.append(step)
                time.sleep(args.preview_settle_seconds)
                continue

        step["wait_seconds"] = 0.35
        steps.append(step)
        time.sleep(0.35)

    raise FastRunError(
        json.dumps(
            {
                "status": "ROUTE_TO_DEPLOYMENT_UNRESOLVED",
                "mission_index": mission_index,
                "preview_already_open": preview_already_open,
                "steps": steps,
            },
            default=str,
        )
    )


def clear_route_dialogue_before_red_scan(
    *,
    timer_start: float,
    max_clicks: int = 4,
) -> list[dict[str, Any]]:
    clears: list[dict[str, Any]] = []
    for attempt in range(1, max_clicks + 1):
        visible = _lightning_visible_ui_snapshot(include_ocr=True)
        if not visible_route_dialogue(visible):
            break
        click = click_transition_control(
            "bottom_continue",
            settle_seconds=0.35,
        )
        record = {
            "attempt": attempt,
            "at_seconds": elapsed(timer_start),
            "visible_ui": compact_visible_ui(visible),
            "click": click,
        }
        clears.append(record)
        log("cleared route dialogue before red mission scan: " + json.dumps(record, default=str))
        time.sleep(0.35)
    return clears


def run_current_mission_from_island_map(
    *,
    mission_index: int,
    timer_start: float,
    args: argparse.Namespace,
    preview_already_open: bool = False,
    full_mission: bool = True,
) -> dict[str, Any]:
    marks: dict[str, float] = {}
    region = None
    if not preview_already_open:
        time.sleep(args.red_wait_seconds)
        route_dialogue_clears = clear_route_dialogue_before_red_scan(
            timer_start=timer_start,
        )
        if route_dialogue_clears:
            marks["route_dialogue_clear"] = elapsed(timer_start)
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
        if turn_index == 1 and not full_mission:
            return {
                "status": "OK",
                "mission_index": mission_index,
                "marks": marks,
                "red_region": region,
                "preview": preview,
                "deploy": deploy,
                "heartbeat": turn_record.get("heartbeat"),
                "auto_turn_status": turn_record.get("auto_turn_status"),
                "post_end_turn": turn_record.get("post_end_turn"),
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
    terminal_bridge_snapshot: dict[str, Any] | None = None
    for step_index in range(max_steps):
        visible = _lightning_visible_ui_snapshot(include_ocr=False)
        visible_name = visible.get("visible_ui")
        if visible_name in {"pause_menu", "island_map_or_unknown"}:
            visible = _lightning_visible_ui_snapshot(include_ocr=True)
            visible_name = visible.get("visible_ui")
        try:
            bridge_snapshot = _lightning_live_snapshot()
        except Exception as exc:
            bridge_snapshot = {"status": "ERROR", "error": str(exc)}
        if (
            isinstance(bridge_snapshot, dict)
            and bridge_snapshot.get("status") == "OK"
            and bridge_snapshot.get("in_active_mission") is False
            and int(bridge_snapshot.get("active_mechs") or 0) == 0
        ):
            terminal_bridge_snapshot = dict(bridge_snapshot)
        elif (
            terminal_bridge_snapshot
            and visible_name == "pause_menu"
            and bridge_snapshot.get("status") in {"NO_BRIDGE", "ERROR"}
        ):
            bridge_snapshot = {
                **terminal_bridge_snapshot,
                "stale_for_result_clear": True,
            }
        visible["bridge_refine_snapshot"] = bridge_snapshot
        step: dict[str, Any] = {
            "step": step_index + 1,
            "visible_ui": compact_visible_ui(visible),
            "live_snapshot": compact_live_snapshot(bridge_snapshot),
            "game_timer_seconds": elapsed(timer_start),
        }
        if visible_name == "island_map":
            try:
                probe = click_stable_red_mission_after_result()
            except Exception as exc:
                step["red_probe_error"] = str(exc)
                steps.append(step)
                time.sleep(0.2)
                continue
            step["red_probe_clicked"] = probe
            steps.append(step)
            return {
                "status": "MISSION_PREVIEW_OPENED",
                "mission_index": mission_index + 1,
                "steps": steps,
                "red_region": probe,
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
            control_history=[
                str(item.get("control"))
                for item in steps
                if item.get("control")
            ],
        )
        try:
            click = click_transition_control(control, settle_seconds=0.25)
            step["control"] = control
            step["click"] = click
        except Exception as exc:
            step["control"] = control
            step["error"] = str(exc)
            steps.append(step)
            break
        previous_control = control
        steps.append(step)
        time.sleep(0.2)
        if control == "leave_confirm_yes" and mission_index >= 10:
            return {
                "status": "SECOND_ISLAND_COMPLETE",
                "mission_index": mission_index,
                "steps": steps,
            }
        post_click_visible = _lightning_visible_ui_snapshot(include_ocr=False)
        steps[-1]["post_click_visible_ui"] = compact_visible_ui(post_click_visible)
        if post_click_visible.get("visible_ui") not in {
            "island_map",
            "island_map_or_unknown",
        }:
            continue
        try:
            probe = click_stable_red_mission_after_result()
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
    startup: dict[str, Any] = {}
    run_start = time.perf_counter()

    startup["main_menu_preflight"] = ensure_title_screen_before_start(args)
    marks["main_menu_preflight"] = elapsed(run_start)

    setup_visible = verify_lightning_setup_modal(raise_on_fail=False)
    if setup_visible.get("status") == "PASS":
        log("setup modal already visible")
        marks["setup_modal_visible"] = elapsed(run_start)
        startup["setup_visible"] = setup_visible
    else:
        startup["title_new_game"] = click_title_new_game()
        startup["overwrite_yes"] = click_overwrite_yes_if_present()
        startup["blitzkrieg"] = ensure_blitzkrieg_squad_selected()
        startup["setup_modal_open"] = open_lightning_setup_modal_from_squad_screen()
        setup_visible = startup["setup_modal_open"]["attempts"][-1]["verify_setup"]
        marks["setup_modal_visible"] = elapsed(run_start)
    log(f"pre-timer visible={visible_ui_name()}")

    timer_start = time.perf_counter()
    startup["setup_modal_start"] = click_setup_modal_start_until_committed()
    marks["timer_start"] = elapsed(run_start)

    sleep_until(timer_start, args.island_click_seconds)
    click_ui_control("island_archive", settle_seconds=0.0)
    marks["archive_click"] = elapsed(timer_start)

    sleep_until(timer_start, args.continue_click_seconds)
    click_ui_control("bottom_continue", settle_seconds=0.0)
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
                    "startup": startup,
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
                    "startup": startup,
                    "missions": missions,
                    "transitions": transitions,
                }
            if transition.get("status") == "SECOND_ISLAND_COMPLETE":
                return {
                    "status": "SECOND_ISLAND_COMPLETE",
                    "marks": marks,
                    "startup": startup,
                    "missions": missions,
                    "transitions": transitions,
                }
            if transition.get("status") != "MISSION_PREVIEW_OPENED":
                return {
                    "status": "ISLAND_LOOP_STOPPED",
                    "reason": "transition_stopped",
                    "marks": marks,
                    "startup": startup,
                    "missions": missions,
                    "transitions": transitions,
                }
        return {
            "status": "MAX_ISLAND_MISSIONS_REACHED",
            "marks": marks,
            "startup": startup,
            "missions": missions,
            "transitions": transitions,
        }

    mission = run_current_mission_from_island_map(
        mission_index=1,
        timer_start=timer_start,
        args=args,
        full_mission=args.full_mission,
    )
    mission["startup"] = startup
    mission["top_level_marks"] = marks
    return mission


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
    parser.add_argument("--deploy-ready-wait-seconds", type=float, default=0.0)
    parser.add_argument("--opening-enemy-wait-seconds", type=float, default=7.0)
    parser.add_argument("--opening-enemy-max-wait-seconds", type=float, default=28.0)
    parser.add_argument("--post-end-turn-wait-seconds", type=float, default=0.5)
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
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Solve while paused, then unpause only to execute the stored plan "
            "and click End Turn. Enabled by default for fast-mode."
        ),
    )
    parser.add_argument(
        "--record-timing-screenshots",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Write every post-End-Turn timing screenshot. Useful for timing "
            "probes, but disabled by default for real fast-mode."
        ),
    )
    parser.add_argument(
        "--ocr-result-audit",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Run OCR-backed result-panel audits before returning from combat. "
            "Useful for diagnosis; disabled by default for speed."
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
        "--ignore-verify-desyncs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Log and continue after per-action verify DESYNC results. "
            "Enabled by default for this fast walkthrough; use "
            "--no-ignore-verify-desyncs for solver-diagnosis runs."
        ),
    )
    parser.add_argument(
        "--ignore-lightning-time-pod",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Allow pod_lost / pod_unrecovered_final safety dirt in this "
            "Lightning War fast path to avoid pod reward UI."
        ),
    )
    parser.add_argument(
        "--allow-lightning-speed-mech-damage",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Allow non-blocking mech damage warnings. Enabled by default for "
            "this fast walkthrough; use --no-allow-lightning-speed-mech-damage "
            "for solver-diagnosis runs."
        ),
    )
    parser.add_argument(
        "--startup-codex-visual-check",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "At launch, write a current screenshot plus reference screenshot "
            "review request and wait for Codex approval before starting."
        ),
    )
    parser.add_argument(
        "--startup-visual-approval-timeout-seconds",
        type=float,
        default=600.0,
        help="Seconds to wait for Codex to write the startup approval JSON.",
    )
    parser.add_argument(
        "--startup-visual-approval-poll-seconds",
        type=float,
        default=0.5,
        help="Polling interval while waiting for startup visual approval.",
    )
    parser.add_argument(
        "--startup-visual-max-attempts",
        type=int,
        default=3,
        help=(
            "Maximum Codex visual review/recovery attempts before blocking "
            "the run."
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
