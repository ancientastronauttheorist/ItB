#!/usr/bin/env python
"""Narrow Lightning War UI timing lab runner.

The lab runner is intentionally smaller than the fast walkthrough. It measures
one UI boundary from the main menu route and stops as soon as the requested
milestone has evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.loop.lightning_telemetry import (
    ScreenshotRecorder,
    TelemetryRecorder,
    generate_frame_delta_report,
)

from scripts import lightning_war_fast_walkthrough as fast


PROFILE_PATH = ROOT / "data" / "lightning_war_timing_profile.json"
NOTEBOOK_PATH = ROOT / "docs" / "agent" / "lightning-war-timing-profile.md"
REPORT_DIR = ROOT / "run_notes" / "lightning_ui_timing_loop"


def _now_run_id() -> str:
    return "lightning_ui_timing_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def _elapsed(start: float) -> float:
    return round(time.perf_counter() - start, 3)


def _load_profile() -> dict[str, Any]:
    if not PROFILE_PATH.exists():
        return {
            "schema_version": 1,
            "updated_at": None,
            "current_milestone": "main_menu_to_archive_red_map",
            "boundaries": {},
        }
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _repo_relative_text(value: Any) -> Any:
    if not value:
        return value
    path = Path(str(value))
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(value)


def _seconds_text(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{value}s"


def _profile_boundary_from_report(report: dict[str, Any]) -> dict[str, Any]:
    red_detection = report.get("red_detection") or {}
    selected = red_detection.get("selected_region") or {}
    return {
        "status": report.get("status"),
        "branch_label": report.get("branch_label"),
        "timer_zero": "lower difficulty setup Start click",
        "archive_click_seconds": report.get("marks", {}).get("archive_click"),
        "intro_continue_seconds": report.get("marks", {}).get("intro_continue"),
        "red_map_detected_seconds": red_detection.get("detected_at_seconds"),
        "region_count": red_detection.get("region_count"),
        "chosen_probe_region": {
            key: selected.get(key)
            for key in (
                "index",
                "window_x",
                "window_y",
                "area_window",
                "coordinate_space",
            )
            if selected.get(key) is not None
        },
        "evidence": {
            "run_id": report.get("run_id"),
            "report_path": _repo_relative_text(report.get("report_path")),
            "contact_sheet_path": _repo_relative_text(
                (report.get("frame_delta_report") or {}).get("contact_sheet_path")
            ),
            "red_map_screenshot": _repo_relative_text(
                red_detection.get("screenshot_path")
            ),
        },
    }


def update_profile(report: dict[str, Any]) -> dict[str, Any]:
    profile = _load_profile()
    boundaries = profile.setdefault("boundaries", {})
    key = "main_menu_to_archive_red_map"
    previous = boundaries.get(key) or {}
    promoted = _profile_boundary_from_report(report)
    previous_time = previous.get("red_map_detected_seconds")
    promoted_time = promoted.get("red_map_detected_seconds")
    should_promote = previous.get("status") != "PASS"
    if not should_promote and previous_time is not None and promoted_time is not None:
        should_promote = float(promoted_time) <= float(previous_time)
    if should_promote:
        profile["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        boundaries[key] = promoted
    _atomic_write_json(PROFILE_PATH, profile)
    return profile


def append_notebook_report(report: dict[str, Any]) -> None:
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if NOTEBOOK_PATH.exists():
        existing = NOTEBOOK_PATH.read_text(encoding="utf-8").rstrip()
    else:
        existing = "\n".join(
            [
                "# Lightning War Timing Profile",
                "",
                "This notebook explains the executable timings stored in "
                "`data/lightning_war_timing_profile.json`.",
            ]
        )
    red_detection = report.get("red_detection") or {}
    frame_report = report.get("frame_delta_report") or {}
    lines = [
        "",
        f"## {report.get('run_id')}",
        "",
        f"- Result: {report.get('status')}",
        f"- Branch: {report.get('branch_label')}",
        "- Boundary: main menu -> lower Start timer zero -> Archive -> red map",
        f"- Archive click: {_seconds_text(report.get('marks', {}).get('archive_click'))}",
        f"- Intro continue: {_seconds_text(report.get('marks', {}).get('intro_continue'))}",
        f"- Red map detected: {_seconds_text(red_detection.get('detected_at_seconds'))}",
        f"- Red regions: {red_detection.get('region_count')}",
        f"- Contact sheet: {_repo_relative_text(frame_report.get('contact_sheet_path'))}",
        f"- Red map screenshot: {_repo_relative_text(red_detection.get('screenshot_path'))}",
        f"- Next patch: {report.get('next_patch')}",
    ]
    NOTEBOOK_PATH.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")


def _capture_probe_frame(
    screenshots: ScreenshotRecorder,
    *,
    timer_start: float,
    note: str,
) -> dict[str, Any]:
    frame = screenshots.capture_once(clock_state="opening_probe", note=note)
    frame["timer_seconds"] = _elapsed(timer_start)
    return frame


def capture_until(
    *,
    timer_start: float,
    screenshots: ScreenshotRecorder,
    target_seconds: float,
    cadence_seconds: float,
    clock_state: str,
) -> None:
    """Sleep toward a target while preserving serialized 2 Hz evidence."""
    next_frame_at = time.perf_counter()
    target_at = timer_start + max(0.0, target_seconds)
    while True:
        now = time.perf_counter()
        if now >= target_at:
            return
        if now >= next_frame_at:
            screenshots.capture_once(
                clock_state=clock_state,
                note=f"waiting_for_{target_seconds:.3f}s",
            )
            next_frame_at = max(
                next_frame_at + max(0.1, cadence_seconds),
                time.perf_counter() + max(0.1, cadence_seconds),
            )
            continue
        time.sleep(min(0.05, target_at - now, next_frame_at - now))


def wait_for_archive_red_map(
    *,
    timer_start: float,
    telemetry: TelemetryRecorder,
    screenshots: ScreenshotRecorder,
    max_seconds: float,
    interval_seconds: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    samples: list[dict[str, Any]] = []
    dialogue_clears: list[dict[str, Any]] = []

    while time.perf_counter() - started <= max_seconds:
        visible = fast._lightning_visible_ui_snapshot(include_ocr=True)
        telemetry.event(
            "opening_visible_ui_probe",
            timer_seconds=_elapsed(timer_start),
            visible_ui=fast.compact_visible_ui(visible),
        )
        if fast.visible_route_dialogue(visible):
            click = fast.click_ui_control("bottom_continue", settle_seconds=0.0)
            clear = {
                "timer_seconds": _elapsed(timer_start),
                "visible_ui": fast.compact_visible_ui(visible),
                "click": click,
            }
            dialogue_clears.append(clear)
            telemetry.event("opening_dialogue_continue", **clear)
            time.sleep(0.25)
            continue

        frame = _capture_probe_frame(
            screenshots,
            timer_start=timer_start,
            note="red_map_probe",
        )
        screenshot_path = frame.get("screenshot_path")
        if not screenshot_path:
            samples.append(
                {
                    "timer_seconds": frame["timer_seconds"],
                    "status": "NO_SCREENSHOT",
                    "frame": frame,
                }
            )
            time.sleep(max(0.05, interval_seconds))
            continue
        regions = fast._lightning_extract_red_regions_from_image(screenshot_path)
        candidates = [
            region
            for region in (regions.get("regions") or [])
            if isinstance(region, dict)
        ]
        sample = {
            "timer_seconds": frame["timer_seconds"],
            "screenshot_path": screenshot_path,
            "region_count": regions.get("region_count"),
            "status": regions.get("status"),
            "candidate_order": [
                {
                    key: region.get(key)
                    for key in (
                        "index",
                        "window_x",
                        "window_y",
                        "area_window",
                        "coordinate_space",
                    )
                    if region.get(key) is not None
                }
                for region in candidates
            ],
        }
        samples.append(sample)
        telemetry.event("opening_red_region_probe", **sample)
        if candidates:
            selected, annotated = fast.select_red_region_candidate(regions)
            return {
                "status": "PASS",
                "detected_at_seconds": frame["timer_seconds"],
                "screenshot_path": screenshot_path,
                "region_count": regions.get("region_count"),
                "selected_region": selected,
                "candidate_order": annotated.get("candidate_order"),
                "dialogue_clears": dialogue_clears,
                "samples": samples,
            }
        time.sleep(max(0.05, interval_seconds))

    return {
        "status": "FAIL",
        "reason": "red_mission_regions_not_detected",
        "dialogue_clears": dialogue_clears,
        "samples": samples,
    }


def prepare_from_main_menu(args: argparse.Namespace) -> dict[str, Any]:
    startup: dict[str, Any] = {}
    if args.hot_main_menu_start:
        startup["main_menu_preflight"] = {
            "status": "SKIPPED",
            "reason": "hot_main_menu_start",
        }
        startup["title_new_game"] = fast.click_title_new_game_hot(args)
        if args.hot_overwrite_yes:
            startup["overwrite_yes"] = fast.click_overwrite_yes_hot(args)
        if not args.hot_skip_squad_select:
            startup["blitzkrieg"] = fast.ensure_blitzkrieg_squad_selected()
        startup["setup_modal_open"] = fast.click_setup_start_hot(args)
        return startup

    startup["main_menu_preflight"] = fast.ensure_title_screen_before_start(args)
    setup_visible = fast.verify_lightning_setup_modal(raise_on_fail=False)
    if setup_visible.get("status") == "PASS":
        startup["setup_visible"] = setup_visible
        return startup
    startup["title_new_game"] = fast.click_title_new_game()
    startup["overwrite_yes"] = fast.click_overwrite_yes_if_present()
    startup["blitzkrieg"] = fast.ensure_blitzkrieg_squad_selected()
    startup["setup_modal_open"] = fast.open_lightning_setup_modal_from_squad_screen()
    return startup


def run_opening_milestone(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or _now_run_id()
    telemetry = TelemetryRecorder(run_id=run_id, root=ROOT / "recordings")
    telemetry.write_manifest(
        {
            "achievement": "Lightning War",
            "route_slice": "main_menu_to_archive_red_map",
            "screenshot_cadence_seconds": args.screenshot_cadence,
            "timer_zero": "lower difficulty setup Start click",
        }
    )
    startup = prepare_from_main_menu(args)
    fast.log(f"timing lab pre-timer visible={fast.visible_ui_name()}")

    timer_start = time.perf_counter()
    screenshots = ScreenshotRecorder(
        telemetry,
        cadence_seconds=args.screenshot_cadence,
        max_retained_frames=args.max_retained_frames,
        max_retained_clock_states=None,
    )
    marks: dict[str, Any] = {"timer_zero": 0.0}
    telemetry.event(
        "timer_zero",
        timer_seconds=0.0,
        control="setup_modal_start",
        meaning="lower difficulty setup Start click",
    )
    startup["setup_modal_start"] = fast.click_setup_modal_start_control(
        settle_seconds=args.modal_start_settle_seconds,
        hold_seconds=args.modal_start_hold_seconds,
    )

    capture_until(
        timer_start=timer_start,
        screenshots=screenshots,
        target_seconds=args.island_click_seconds,
        cadence_seconds=args.screenshot_cadence,
        clock_state="wait_archive_click",
    )
    archive_click = fast.click_ui_control("island_archive", settle_seconds=0.0)
    marks["archive_click"] = _elapsed(timer_start)
    telemetry.event(
        "archive_island_click",
        timer_seconds=marks["archive_click"],
        click=archive_click,
    )

    if args.continue_click_seconds >= 0:
        capture_until(
            timer_start=timer_start,
            screenshots=screenshots,
            target_seconds=args.continue_click_seconds,
            cadence_seconds=args.screenshot_cadence,
            clock_state="wait_intro_continue",
        )
        intro_continue = fast.click_ui_control("bottom_continue", settle_seconds=0.0)
        marks["intro_continue"] = _elapsed(timer_start)
        telemetry.event(
            "archive_intro_continue_click",
            timer_seconds=marks["intro_continue"],
            click=intro_continue,
        )

    red_detection = wait_for_archive_red_map(
        timer_start=timer_start,
        telemetry=telemetry,
        screenshots=screenshots,
        max_seconds=args.red_map_timeout_seconds,
        interval_seconds=args.red_probe_interval_seconds,
    )
    frame_report = generate_frame_delta_report(telemetry.run_dir)

    branch_label = (
        "archive_intro.extra_dialogue"
        if red_detection.get("dialogue_clears")
        else "archive_intro.default"
    )
    status = (
        "PASS"
        if red_detection.get("status") == "PASS"
        and int(red_detection.get("region_count") or 0) >= 1
        else "FAIL"
    )
    next_patch = (
        "Extend to red_map_to_mission_preview after user review."
        if status == "PASS"
        else "Improve Archive intro wait/dismissal or red-region detector."
    )
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "branch_label": branch_label,
        "route_slice": "main_menu_to_archive_red_map",
        "startup": startup,
        "marks": marks,
        "red_detection": red_detection,
        "frame_delta_report": frame_report,
        "next_patch": next_patch,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"{run_id}_opening_red_map_report.json"
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    if status == "PASS":
        update_profile(report)
    append_notebook_report(report)
    telemetry.summary(
        status=status,
        reason=next_patch,
        extra={
            "report_path": str(report_path),
            "branch_label": branch_label,
            "region_count": red_detection.get("region_count"),
        },
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the first Lightning War UI timing lab milestone.",
    )
    parser.add_argument("--run-id")
    parser.add_argument("--screenshot-cadence", type=float, default=0.5)
    parser.add_argument("--max-retained-frames", type=int, default=360)
    parser.add_argument("--island-click-seconds", type=float, default=7.0)
    parser.add_argument("--continue-click-seconds", type=float, default=9.5)
    parser.add_argument("--red-map-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--red-probe-interval-seconds", type=float, default=0.5)
    parser.add_argument("--modal-start-settle-seconds", type=float, default=0.05)
    parser.add_argument("--modal-start-hold-seconds", type=float, default=0.35)
    parser.add_argument("--hot-main-menu-start", action="store_true")
    parser.add_argument(
        "--hot-skip-squad-select",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--hot-overwrite-yes",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument("--hot-click-hold-seconds", type=float, default=0.12)
    parser.add_argument("--hot-click-settle-seconds", type=float, default=0.08)
    parser.add_argument("--hot-title-settle-seconds", type=float, default=0.35)
    parser.add_argument("--hot-setup-start-settle-seconds", type=float, default=1.0)
    parser.add_argument("--hot-modal-start-settle-seconds", type=float, default=0.35)
    parser.add_argument(
        "--startup-codex-visual-check",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--startup-visual-approval-timeout-seconds",
        type=float,
        default=600.0,
    )
    parser.add_argument(
        "--startup-visual-approval-poll-seconds",
        type=float,
        default=0.5,
    )
    parser.add_argument("--startup-visual-max-attempts", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_opening_milestone(args)
    except Exception as exc:
        parked = fast.park_on_error()
        print("---LIGHTNING_TIMING_LAB_ERROR---")
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
    print("---LIGHTNING_TIMING_LAB_REPORT---")
    print(json.dumps(report, default=str, indent=2))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
