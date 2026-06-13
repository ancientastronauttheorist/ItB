#!/usr/bin/env python
"""Narrow Lightning War UI timing lab runner.

The lab runner is intentionally smaller than the fast walkthrough. It measures
one UI boundary from the main menu route and stops as soon as the requested
milestone has evidence.
"""

from __future__ import annotations

import argparse
import json
import os
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
from src.loop.commands import _lightning_read_save_game_timer

from scripts import lightning_war_fast_walkthrough as fast
from scripts import itb_timer_memory_probe as memory_probe


PROFILE_PATH = ROOT / "data" / "lightning_war_timing_profile.json"
NOTEBOOK_PATH = ROOT / "docs" / "agent" / "lightning-war-timing-profile.md"
REPORT_DIR = ROOT / "run_notes" / "lightning_ui_timing_loop"
LIGHTNING_TIMER_LIMIT_SECONDS = 30 * 60
TRUSTED_MEMORY_CLOCK_SOURCES = {
    "memory_live_numeric_candidate",
}


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


def _parse_optional_timer_address(value: str | None) -> int | None:
    if not value:
        return None
    return int(str(value), 0)


def _read_memory_in_game_timer(
    *,
    label: str,
    timer_address: int | None = None,
    live_timer_address: int | None = None,
    live_timer_kind: str | None = None,
) -> dict[str, Any]:
    if os.name != "nt":
        return {
            "status": "UNAVAILABLE",
            "reason": "memory timer probe is Windows-only",
            "label": label,
            "clock_source": (
                "memory_live_numeric_candidate"
                if live_timer_address is not None
                else "memory_timeline_playtime_address"
                if timer_address is not None
                else "memory_visible_timer_context"
            ),
        }
    pid = memory_probe._find_breach_pid()
    if pid is None:
        return {
            "status": "UNAVAILABLE",
            "reason": "Breach.exe not found",
            "label": label,
            "clock_source": (
                "memory_live_numeric_candidate"
                if live_timer_address is not None
                else "memory_timeline_playtime_address"
                if timer_address is not None
                else "memory_visible_timer_context"
            ),
        }
    try:
        with memory_probe.WindowsProcessReader(pid) as reader:
            if live_timer_address is not None and live_timer_kind:
                direct = memory_probe.read_numeric_timer_address(
                    reader,
                    live_timer_address,
                    live_timer_kind,
                )
                return _live_numeric_timer_result(
                    label=label,
                    pid=pid,
                    direct=direct,
                    kind=live_timer_kind,
                )
            if timer_address is not None:
                direct = memory_probe.read_timeline_playtime_address(
                    reader,
                    timer_address,
                )
                return _timeline_address_timer_result(
                    label=label,
                    pid=pid,
                    direct=direct,
                )
            context = memory_probe.scan_context_timers(
                reader,
                max_region_size=32 * 1024 * 1024,
                max_hits=8000,
            )
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": str(exc),
            "label": label,
            "clock_source": (
                "memory_live_numeric_candidate"
                if live_timer_address is not None
                else "memory_timeline_playtime_address"
                if timer_address is not None
                else "memory_visible_timer_context"
            ),
        }
    top = memory_probe.select_visible_timer_context(
        context,
        max_visible_seconds=LIGHTNING_TIMER_LIMIT_SECONDS,
    )
    if not top:
        return {
            "status": "UNAVAILABLE",
            "reason": "no visible timer-like context found",
            "label": label,
            "clock_source": "memory_visible_timer_context",
            "context_count": len(context),
        }
    try:
        seconds = float(top.get("seconds"))
    except (TypeError, ValueError):
        seconds = None
    if seconds is None:
        return {
            "status": "REJECTED",
            "reason": "selected memory timer did not include numeric seconds",
            "label": label,
            "clock_source": "memory_visible_timer_context",
            "context_count": len(context),
            "selected_timer": top,
        }
    if seconds > LIGHTNING_TIMER_LIMIT_SECONDS:
        return {
            "status": "REJECTED",
            "reason": "selected memory timer exceeds Lightning War 30 minute achievement limit",
            "label": label,
            "clock_source": "memory_visible_timer_context",
            "game_timer": top.get("game_timer"),
            "game_seconds": seconds,
            "context_count": len(context),
            "selected_timer": top,
        }
    return {
        "status": "OK",
        "label": label,
        "clock_source": "memory_visible_timer_context",
        "source": next(iter((top.get("sources") or {"visible_timer_string": 1}).keys())),
        "pid": pid,
        "game_timer": top.get("game_timer"),
        "game_seconds": seconds,
        "context_count": len(context),
        "source_counts": top.get("sources"),
        "raw_values": top.get("raw_values"),
        "regions": top.get("regions"),
        "timer_validation": "range_checked_lightning_limit",
        "selected_timer": top,
    }


def read_in_game_timer(
    profile: str,
    *,
    label: str,
    use_memory: bool = True,
    timer_address: int | None = None,
    live_timer_address: int | None = None,
    live_timer_kind: str | None = None,
) -> dict[str, Any]:
    """Read the achievement clock used by Lightning War."""
    memory = (
        _read_memory_in_game_timer(
            label=label,
            timer_address=timer_address,
            live_timer_address=live_timer_address,
            live_timer_kind=live_timer_kind,
        )
        if use_memory
        else None
    )
    save = dict(_lightning_read_save_game_timer(profile))
    save["label"] = label
    save["clock_source"] = "save_current_time"
    save["timer_validation"] = "fallback_not_top_right_validated"
    if memory and memory.get("status") == "OK" and _timer_sample_seconds(memory) is not None:
        result = dict(memory)
        result["fallback_save_timer"] = save
        return result
    result = save
    if memory:
        result["memory_timer_probe"] = memory
    return result


def _timeline_address_timer_result(
    *,
    label: str,
    pid: int,
    direct: dict[str, Any],
) -> dict[str, Any]:
    if direct.get("status") != "OK":
        return {
            **direct,
            "label": label,
            "pid": pid,
            "clock_source": "memory_timeline_playtime_address",
            "timer_validation": "calibrated_pause_menu_timeline_playtime_address",
            "live_clock_usable": False,
        }
    seconds = float(direct["seconds"])
    if seconds > LIGHTNING_TIMER_LIMIT_SECONDS:
        return {
            "status": "REJECTED",
            "reason": "calibrated memory timer exceeds Lightning War 30 minute achievement limit",
            "label": label,
            "clock_source": "memory_timeline_playtime_address",
            "source": direct.get("source"),
            "pid": pid,
            "address": direct.get("address"),
            "raw": direct.get("raw"),
            "game_timer": direct.get("game_timer"),
            "game_seconds": seconds,
            "timer_validation": "calibrated_pause_menu_timeline_playtime_address",
            "live_clock_usable": False,
            "selected_timer": direct,
        }
    return {
        "status": "OK",
        "label": label,
        "clock_source": "memory_timeline_playtime_address",
        "source": direct.get("source"),
        "pid": pid,
        "address": direct.get("address"),
        "raw": direct.get("raw"),
        "game_timer": direct.get("game_timer"),
        "game_seconds": seconds,
        "timer_validation": "pause_menu_render_cache_not_live_clock",
        "live_clock_usable": False,
        "selected_timer": direct,
    }


def _live_numeric_timer_result(
    *,
    label: str,
    pid: int,
    direct: dict[str, Any],
    kind: str,
) -> dict[str, Any]:
    if not direct.get("read_ok"):
        return {
            **direct,
            "status": "ERROR",
            "label": label,
            "pid": pid,
            "clock_source": "memory_live_numeric_candidate",
            "kind": kind,
            "timer_validation": "validated_live_numeric_cycle",
            "live_clock_usable": True,
        }
    seconds = float(direct["seconds"])
    if seconds > LIGHTNING_TIMER_LIMIT_SECONDS:
        return {
            "status": "REJECTED",
            "reason": "live numeric memory timer exceeds Lightning War 30 minute achievement limit",
            "label": label,
            "clock_source": "memory_live_numeric_candidate",
            "source": "validated_live_numeric_cycle",
            "pid": pid,
            "address": direct.get("address"),
            "kind": kind,
            "raw": direct.get("raw_value"),
            "game_timer": direct.get("game_timer"),
            "game_seconds": seconds,
            "timer_validation": "validated_live_numeric_cycle",
            "live_clock_usable": True,
            "selected_timer": direct,
        }
    return {
        "status": "OK",
        "label": label,
        "clock_source": "memory_live_numeric_candidate",
        "source": "validated_live_numeric_cycle",
        "pid": pid,
        "address": direct.get("address"),
        "kind": kind,
        "raw": direct.get("raw_value"),
        "game_timer": direct.get("game_timer"),
        "game_seconds": seconds,
        "timer_validation": "validated_live_numeric_cycle",
        "live_clock_usable": True,
        "selected_timer": direct,
    }


class CalibratedTimelineFrameClockSampler:
    def __init__(self, timer_address: int) -> None:
        self.timer_address = timer_address
        self.pid: int | None = None
        self.reader: memory_probe.WindowsProcessReader | None = None

    def __call__(self) -> dict[str, Any]:
        if os.name != "nt":
            return {
                "status": "UNAVAILABLE",
                "reason": "memory timer probe is Windows-only",
                "label": "screenshot_frame",
                "clock_source": "memory_timeline_playtime_address",
            }
        reader = self._reader()
        if reader is None or self.pid is None:
            return {
                "status": "UNAVAILABLE",
                "reason": "Breach.exe not found",
                "label": "screenshot_frame",
                "clock_source": "memory_timeline_playtime_address",
            }
        direct = memory_probe.read_timeline_playtime_address(
            reader,
            self.timer_address,
        )
        return _timeline_address_timer_result(
            label="screenshot_frame",
            pid=self.pid,
            direct=direct,
        )

    def close(self) -> None:
        if self.reader is not None:
            self.reader.close()
            self.reader = None

    def _reader(self) -> memory_probe.WindowsProcessReader | None:
        if self.reader is not None:
            return self.reader
        pid = memory_probe._find_breach_pid()
        if pid is None:
            self.close()
            self.pid = None
            return None
        self.pid = pid
        self.reader = memory_probe.WindowsProcessReader(pid)
        return self.reader


class LiveNumericFrameClockSampler:
    def __init__(self, timer_address: int, timer_kind: str) -> None:
        self.timer_address = timer_address
        self.timer_kind = timer_kind
        self.pid: int | None = None
        self.reader: memory_probe.WindowsProcessReader | None = None

    def __call__(self) -> dict[str, Any]:
        if os.name != "nt":
            return {
                "status": "UNAVAILABLE",
                "reason": "memory timer probe is Windows-only",
                "label": "screenshot_frame",
                "clock_source": "memory_live_numeric_candidate",
            }
        reader = self._reader()
        if reader is None or self.pid is None:
            return {
                "status": "UNAVAILABLE",
                "reason": "Breach.exe not found",
                "label": "screenshot_frame",
                "clock_source": "memory_live_numeric_candidate",
            }
        direct = memory_probe.read_numeric_timer_address(
            reader,
            self.timer_address,
            self.timer_kind,
        )
        return _live_numeric_timer_result(
            label="screenshot_frame",
            pid=self.pid,
            direct=direct,
            kind=self.timer_kind,
        )

    def close(self) -> None:
        if self.reader is not None:
            self.reader.close()
            self.reader = None

    def _reader(self) -> memory_probe.WindowsProcessReader | None:
        if self.reader is not None:
            return self.reader
        pid = memory_probe._find_breach_pid()
        if pid is None:
            self.close()
            self.pid = None
            return None
        self.pid = pid
        self.reader = memory_probe.WindowsProcessReader(pid)
        return self.reader


def make_frame_clock_sampler(
    *,
    use_memory: bool,
    timer_address: int | None,
    live_timer_address: int | None = None,
    live_timer_kind: str | None = None,
) -> Any:
    if use_memory and live_timer_address is not None and live_timer_kind:
        return LiveNumericFrameClockSampler(live_timer_address, live_timer_kind)
    return None


def _timer_sample_seconds(sample: dict[str, Any] | None) -> float | None:
    if not isinstance(sample, dict) or sample.get("status") != "OK":
        return None
    if sample.get("clock_source") not in TRUSTED_MEMORY_CLOCK_SOURCES:
        return None
    try:
        return float(sample.get("game_seconds"))
    except (TypeError, ValueError):
        return None


def _timer_sample_compact(sample: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(sample, dict):
        return {"status": "UNKNOWN"}
    compact = {
        key: sample.get(key)
        for key in (
            "status",
            "label",
            "clock_source",
            "source",
            "game_timer",
            "game_seconds",
            "game_timer_ms",
            "pid",
            "address",
            "raw",
            "context_count",
            "timer_validation",
            "reason",
        )
        if sample.get(key) is not None
    }
    if sample.get("fallback_save_timer"):
        compact["fallback_save_timer"] = _timer_sample_compact(
            sample.get("fallback_save_timer")
        )
    if sample.get("memory_timer_probe"):
        compact["memory_timer_probe"] = _timer_sample_compact(
            sample.get("memory_timer_probe")
        )
    return compact


def _profile_boundary_from_report(report: dict[str, Any]) -> dict[str, Any]:
    red_detection = report.get("red_detection") or {}
    selected = red_detection.get("selected_region") or {}
    in_game_timers = report.get("in_game_timers") or {}
    red_timer = in_game_timers.get("red_map_detected")
    trusted_red_seconds = _timer_sample_seconds(red_timer)
    return {
        "status": report.get("status"),
        "branch_label": report.get("branch_label"),
        "timer_zero": "lower difficulty setup Start click",
        "primary_time_source": "validated_memory_live_numeric_candidate_when_available",
        "fallback_time_source": "save_profile_current_time_not_top_right_validated",
        "archive_click_wall_seconds": report.get("marks", {}).get("archive_click"),
        "intro_continue_wall_seconds": report.get("marks", {}).get("intro_continue"),
        "red_map_detected_wall_seconds": red_detection.get("detected_at_seconds"),
        "in_game_timer": {
            "red_map_detected": _timer_sample_compact(red_timer),
            "all_samples": {
                key: _timer_sample_compact(value)
                for key, value in in_game_timers.items()
            },
        },
        "red_map_detected_game_seconds": trusted_red_seconds,
        "red_map_detected_game_timer": (
            red_timer.get("game_timer")
            if trusted_red_seconds is not None and isinstance(red_timer, dict)
            else None
        ),
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
    previous_game_time = previous.get("red_map_detected_game_seconds")
    promoted_game_time = promoted.get("red_map_detected_game_seconds")
    previous_wall_time = previous.get(
        "red_map_detected_wall_seconds",
        previous.get("red_map_detected_seconds"),
    )
    promoted_wall_time = promoted.get("red_map_detected_wall_seconds")
    should_promote = previous.get("status") != "PASS"
    if not should_promote:
        if promoted_game_time is not None and previous_game_time is None:
            should_promote = True
        elif promoted_game_time is not None and previous_game_time is not None:
            should_promote = float(promoted_game_time) <= float(previous_game_time)
        elif previous_game_time is None and previous_wall_time is not None and promoted_wall_time is not None:
            should_promote = float(promoted_wall_time) <= float(previous_wall_time)
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
    in_game_timers = report.get("in_game_timers") or {}
    red_timer = in_game_timers.get("red_map_detected") or {}
    lines = [
        "",
        f"## {report.get('run_id')}",
        "",
        f"- Result: {report.get('status')}",
        f"- Branch: {report.get('branch_label')}",
        "- Boundary: main menu -> lower Start timer zero -> Archive -> red map",
        "- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles",
        f"- Red map detected in-game timer: {red_timer.get('game_timer') or 'n/a'}",
        f"- Red map timer source: {red_timer.get('clock_source') or 'n/a'}",
        f"- Archive click wall elapsed: {_seconds_text(report.get('marks', {}).get('archive_click'))}",
        f"- Intro continue wall elapsed: {_seconds_text(report.get('marks', {}).get('intro_continue'))}",
        f"- Red map detected wall elapsed: {_seconds_text(red_detection.get('detected_at_seconds'))}",
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
    profile: str,
    use_memory_timer: bool,
    memory_timer_address: int | None,
    memory_live_timer_address: int | None,
    memory_live_timer_kind: str | None,
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
            paired_timer = read_in_game_timer(
                profile,
                label="red_map_detected_screenshot_pair",
                use_memory=use_memory_timer,
                timer_address=memory_timer_address,
                live_timer_address=memory_live_timer_address,
                live_timer_kind=memory_live_timer_kind,
            )
            selected, annotated = fast.select_red_region_candidate(regions)
            return {
                "status": "PASS",
                "detected_at_seconds": frame["timer_seconds"],
                "screenshot_path": screenshot_path,
                "paired_in_game_timer": paired_timer,
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
    memory_timer_address = _parse_optional_timer_address(args.memory_timer_address)
    memory_live_timer_address = _parse_optional_timer_address(args.memory_live_timer_address)
    memory_live_timer_kind = args.memory_live_timer_kind
    telemetry = TelemetryRecorder(run_id=run_id, root=ROOT / "recordings")
    telemetry.write_manifest(
        {
            "achievement": "Lightning War",
            "route_slice": "main_menu_to_archive_red_map",
            "screenshot_cadence_seconds": args.screenshot_cadence,
            "timer_zero": "lower difficulty setup Start click",
            "memory_timer_address": (
                f"0x{memory_timer_address:016x}"
                if memory_timer_address is not None
                else None
            ),
            "memory_live_timer_address": (
                f"0x{memory_live_timer_address:016x}"
                if memory_live_timer_address is not None
                else None
            ),
            "memory_live_timer_kind": memory_live_timer_kind,
            "screenshot_filename_timer_source": (
                "memory_live_numeric_candidate"
                if memory_live_timer_address is not None and args.memory_timer_probe
                else None
            ),
        }
    )
    startup = prepare_from_main_menu(args)
    fast.log(f"timing lab pre-timer visible={fast.visible_ui_name()}")
    in_game_timers: dict[str, Any] = {
        "pre_timer": read_in_game_timer(
            args.profile,
        label="pre_timer",
        use_memory=args.memory_timer_probe,
        timer_address=memory_timer_address,
        live_timer_address=memory_live_timer_address,
        live_timer_kind=memory_live_timer_kind,
    ),
    }

    timer_start = time.perf_counter()
    screenshots = ScreenshotRecorder(
        telemetry,
        cadence_seconds=args.screenshot_cadence,
        max_retained_frames=args.max_retained_frames,
        max_retained_clock_states=None,
        frame_clock_sampler=make_frame_clock_sampler(
            use_memory=args.memory_timer_probe,
            timer_address=memory_timer_address,
            live_timer_address=memory_live_timer_address,
            live_timer_kind=memory_live_timer_kind,
        ),
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
    in_game_timers["timer_zero_click"] = read_in_game_timer(
        args.profile,
        label="timer_zero_click",
        use_memory=args.memory_timer_probe,
        timer_address=memory_timer_address,
        live_timer_address=memory_live_timer_address,
        live_timer_kind=memory_live_timer_kind,
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
    in_game_timers["archive_click"] = read_in_game_timer(
        args.profile,
        label="archive_click",
        use_memory=args.memory_timer_probe,
        timer_address=memory_timer_address,
        live_timer_address=memory_live_timer_address,
        live_timer_kind=memory_live_timer_kind,
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
        in_game_timers["intro_continue"] = read_in_game_timer(
            args.profile,
            label="intro_continue",
            use_memory=args.memory_timer_probe,
            timer_address=memory_timer_address,
            live_timer_address=memory_live_timer_address,
            live_timer_kind=memory_live_timer_kind,
        )

    red_detection = wait_for_archive_red_map(
        timer_start=timer_start,
        telemetry=telemetry,
        screenshots=screenshots,
        profile=args.profile,
        use_memory_timer=args.memory_timer_probe,
        memory_timer_address=memory_timer_address,
        memory_live_timer_address=memory_live_timer_address,
        memory_live_timer_kind=memory_live_timer_kind,
        max_seconds=args.red_map_timeout_seconds,
        interval_seconds=args.red_probe_interval_seconds,
    )
    in_game_timers["red_map_detected"] = (
        red_detection.get("paired_in_game_timer")
        if isinstance(red_detection.get("paired_in_game_timer"), dict)
        else read_in_game_timer(
            args.profile,
            label="red_map_detected",
            use_memory=args.memory_timer_probe,
            timer_address=memory_timer_address,
            live_timer_address=memory_live_timer_address,
            live_timer_kind=memory_live_timer_kind,
        )
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
        "in_game_timers": in_game_timers,
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
    parser.add_argument("--profile", default="Alpha")
    parser.add_argument(
        "--memory-timer-probe",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--memory-timer-address",
        help=(
            "Process-local calibrated pause-menu Timeline Playtime string "
            "address, for example 0x00000000138a5900."
        ),
    )
    parser.add_argument(
        "--memory-live-timer-address",
        help=(
            "Process-local validated live numeric timer address, for example "
            "0x00000000122e5dbc."
        ),
    )
    parser.add_argument(
        "--memory-live-timer-kind",
        default="f32_seconds",
        help="Numeric timer representation for --memory-live-timer-address.",
    )
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
