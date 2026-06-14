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


def _timer_sample_from_frame(frame: dict[str, Any], *, label: str) -> dict[str, Any]:
    frame_clock = frame.get("frame_clock")
    if not isinstance(frame_clock, dict):
        return {
            "status": frame.get("frame_clock_status") or "UNKNOWN",
            "label": label,
            "reason": "frame_clock_missing",
        }
    sample = {
        "status": frame_clock.get("status") or frame.get("frame_clock_status"),
        "label": label,
        "clock_source": frame.get("clock_source") or frame_clock.get("clock_source"),
        "source": "screenshot_frame_clock",
        "game_timer": frame.get("game_timer") or frame_clock.get("game_timer"),
        "game_seconds": frame.get("game_seconds") or frame_clock.get("game_seconds"),
        "game_timer_ms": frame.get("game_timer_ms") or frame_clock.get("game_timer_ms"),
        "pid": frame_clock.get("pid"),
        "address": frame_clock.get("address"),
        "raw": frame_clock.get("raw"),
        "timer_validation": frame_clock.get("timer_validation"),
        "reason": frame_clock.get("reason"),
    }
    return {key: value for key, value in sample.items() if value is not None}


def _timer_sample_from_recorder(
    screenshots: ScreenshotRecorder,
    *,
    label: str,
) -> dict[str, Any]:
    sampler = getattr(screenshots, "frame_clock_sampler", None)
    if not callable(sampler):
        return {
            "status": "UNAVAILABLE",
            "label": label,
            "reason": "frame_clock_sampler_unavailable",
        }
    sample = sampler()
    if not isinstance(sample, dict):
        return {
            "status": "UNKNOWN",
            "label": label,
            "reason": "frame_clock_sampler_returned_non_dict",
        }
    return {**sample, "label": label}


def _deployment_yellow_signal_from_frame(frame: dict[str, Any]) -> dict[str, Any]:
    path = frame.get("screenshot_path")
    if not path:
        return {
            "status": "UNKNOWN",
            "reason": "screenshot_path_missing",
            "deployment_visible": False,
        }
    try:
        from PIL import Image

        with Image.open(path) as image:
            image = image.convert("RGB")
            width, height = image.size
            crop = (
                int(width * 480 / 2560),
                int(height * 173 / 1440),
                int(width * 1960 / 2560),
                int(height * 1232 / 1440),
            )
            region = image.crop(crop)
            pixels = region.size[0] * region.size[1]
            yellow = sum(
                1
                for red, green, blue in region.getdata()
                if red >= 120
                and green >= 95
                and blue <= 95
                and red >= green * 0.8
                and red <= green * 1.8
            )
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": str(exc),
            "deployment_visible": False,
        }
    threshold = 5000
    return {
        "status": "OK",
        "yellow": yellow,
        "pixels": pixels,
        "threshold": threshold,
        "deployment_visible": yellow >= threshold,
        "crop": list(crop),
    }


def _profile_boundary_from_report(report: dict[str, Any]) -> dict[str, Any]:
    red_detection = report.get("red_detection") or {}
    selected = red_detection.get("selected_region") or {}
    in_game_timers = report.get("in_game_timers") or {}
    paired_red_timer = in_game_timers.get("red_map_detected")
    frame_red_timer = red_detection.get("detected_frame_timer")
    red_timer = (
        frame_red_timer
        if _timer_sample_seconds(frame_red_timer) is not None
        else paired_red_timer
    )
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
            "red_map_detected_paired_after_detection": _timer_sample_compact(
                paired_red_timer
            ),
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
    deploy = report.get("deploy_recommended") or {}
    deploy_compact = deploy.get("deploy_result_compact") or {}
    post_deploy_timer = in_game_timers.get("post_deploy_frame") or {}
    confirm = report.get("deploy_confirm") or {}
    confirm_click_timer = in_game_timers.get("deploy_confirm_click_before") or {}
    bridge_ready_timer = in_game_timers.get("opening_player_turn_bridge_ready") or {}
    ready_frame_timer = (
        in_game_timers.get("opening_player_turn_first_frame_after_bridge") or {}
    )
    lines = [
        "",
        f"## {report.get('run_id')}",
        "",
        f"- Result: {report.get('status')}",
        f"- Branch: {report.get('branch_label')}",
        f"- Boundary: {report.get('route_slice') or 'main_menu_to_archive_red_map'}",
        "- Primary time source: validated live numeric memory candidate when available; pause-menu `Timeline Playtime` addresses are only re-pause calibration oracles",
        f"- Red map detected in-game timer: {red_timer.get('game_timer') or 'n/a'}",
        f"- Red map timer source: {red_timer.get('clock_source') or 'n/a'}",
        f"- Red map paired post-detection timer: {(red_detection.get('paired_in_game_timer') or {}).get('game_timer') or 'n/a'}",
        f"- Archive click wall elapsed: {_seconds_text(report.get('marks', {}).get('archive_click'))}",
        f"- Intro continue wall elapsed: {_seconds_text(report.get('marks', {}).get('intro_continue'))}",
        f"- Red map detected wall elapsed: {_seconds_text(red_detection.get('detected_at_seconds'))}",
        f"- Red regions: {red_detection.get('region_count')}",
        f"- Contact sheet: {_repo_relative_text(frame_report.get('contact_sheet_path'))}",
        f"- Red map screenshot: {_repo_relative_text(red_detection.get('screenshot_path'))}",
        f"- Next patch: {report.get('next_patch')}",
    ]
    if deploy:
        lines.extend(
            [
                f"- Deploy recommended result: {deploy_compact.get('status') or 'n/a'}",
                f"- Deploy recommended placements: {deploy_compact.get('deployment_count')}",
                f"- Deploy recommended duration: {_seconds_text(deploy.get('deploy_duration_seconds'))}",
                f"- Post-deploy frame in-game timer: {post_deploy_timer.get('game_timer') or 'n/a'}",
            ]
        )
    if confirm:
        lines.extend(
            [
                f"- Deploy Confirm signal: {confirm.get('confirm_signal_source') or 'n/a'}",
                f"- Deploy Confirm click timer: {confirm_click_timer.get('game_timer') or 'n/a'}",
                f"- Opening player-turn signal: {confirm.get('player_turn_signal_source') or 'n/a'}",
                f"- Opening player-turn bridge timer: {bridge_ready_timer.get('game_timer') or 'n/a'}",
                f"- First frame after bridge-ready timer: {ready_frame_timer.get('game_timer') or 'n/a'}",
                f"- Post-confirm observed seconds: {_seconds_text(confirm.get('observed_seconds'))}",
            ]
        )
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
        frame_timer = _timer_sample_from_frame(frame, label="red_map_detected_frame")
        sample = {
            "timer_seconds": frame["timer_seconds"],
            "screenshot_path": screenshot_path,
            "detected_frame_timer": frame_timer,
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
                "detected_frame_timer": frame_timer,
                "paired_in_game_timer": paired_timer,
                "region_count": regions.get("region_count"),
                "selected_region": selected,
                "candidate_order": annotated.get("candidate_order"),
                "dialogue_clears": dialogue_clears,
                "samples": samples,
            }
        visible = fast._lightning_visible_ui_snapshot(include_ocr=False)
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


def click_selected_red_mission_preview(
    *,
    timer_start: float,
    telemetry: TelemetryRecorder,
    screenshots: ScreenshotRecorder,
    red_detection: dict[str, Any],
    profile: str,
    use_memory_timer: bool,
    memory_timer_address: int | None,
    memory_live_timer_address: int | None,
    memory_live_timer_kind: str | None,
    hover_seconds: float,
    settle_seconds: float,
    hold_seconds: float,
    pause_after_click: bool,
) -> dict[str, Any]:
    selected = red_detection.get("selected_region")
    if not isinstance(selected, dict):
        return {
            "status": "SKIPPED",
            "reason": "no_selected_red_region",
        }
    try:
        x = int(selected["window_x"])
        y = int(selected["window_y"])
    except (KeyError, TypeError, ValueError):
        return {
            "status": "BLOCKED",
            "reason": "selected_region_missing_click_coordinates",
            "selected_region": selected,
        }

    before_timer = read_in_game_timer(
        profile,
        label="red_mission_click_before",
        use_memory=use_memory_timer,
        timer_address=memory_timer_address,
        live_timer_address=memory_live_timer_address,
        live_timer_kind=memory_live_timer_kind,
    )
    click = fast.click_hovered_point(
        "red_mission_region",
        x,
        y,
        hover_seconds=hover_seconds,
        settle_seconds=settle_seconds,
        hold_seconds=hold_seconds,
    )
    click_wall_seconds = _elapsed(timer_start)
    telemetry.event(
        "red_mission_region_click",
        timer_seconds=click_wall_seconds,
        selected_region={
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
        before_in_game_timer=before_timer,
        click=click,
    )

    preview_frame = screenshots.capture_once(
        clock_state="mission_preview_probe",
        note="after_red_mission_click",
    )
    preview_frame["timer_seconds"] = _elapsed(timer_start)
    preview_timer = _timer_sample_from_frame(
        preview_frame,
        label="mission_preview_frame",
    )
    after_preview_timer = read_in_game_timer(
        profile,
        label="mission_preview_after_click",
        use_memory=use_memory_timer,
        timer_address=memory_timer_address,
        live_timer_address=memory_live_timer_address,
        live_timer_kind=memory_live_timer_kind,
    )
    telemetry.event(
        "mission_preview_probe",
        timer_seconds=preview_frame["timer_seconds"],
        screenshot_path=preview_frame.get("screenshot_path"),
        preview_frame_timer=preview_timer,
        after_preview_timer=after_preview_timer,
    )

    pause: dict[str, Any] | None = None
    after_pause_timer: dict[str, Any] | None = None
    if pause_after_click:
        pause = fast.click_hovered_point(
            "pause",
            38,
            28,
            hover_seconds=0.0,
            settle_seconds=0.05,
            hold_seconds=0.12,
        )
        after_pause_timer = read_in_game_timer(
            profile,
            label="mission_preview_after_pause",
            use_memory=use_memory_timer,
            timer_address=memory_timer_address,
            live_timer_address=memory_live_timer_address,
            live_timer_kind=memory_live_timer_kind,
        )
        telemetry.event(
            "mission_preview_pause",
            timer_seconds=_elapsed(timer_start),
            click=pause,
            after_pause_timer=after_pause_timer,
        )

    return {
        "status": "OK",
        "selected_region": selected,
        "before_in_game_timer": before_timer,
        "click": click,
        "click_wall_seconds": click_wall_seconds,
        "preview_frame": preview_frame,
        "preview_frame_timer": preview_timer,
        "after_preview_timer": after_preview_timer,
        "pause": pause,
        "after_pause_timer": after_pause_timer,
    }


def click_start_mission_from_preview(
    *,
    timer_start: float,
    telemetry: TelemetryRecorder,
    screenshots: ScreenshotRecorder,
    profile: str,
    use_memory_timer: bool,
    memory_timer_address: int | None,
    memory_live_timer_address: int | None,
    memory_live_timer_kind: str | None,
    settle_seconds: float,
    hover_seconds: float,
    hold_seconds: float,
    max_seconds: float,
    interval_seconds: float,
    pause_after_click: bool,
    pre_start_visible_probe: bool,
    deployment_trigger_source: str,
) -> dict[str, Any]:
    if pre_start_visible_probe:
        visible = fast._lightning_visible_ui_snapshot(include_ocr=False)
        dialogue_visible = fast.visible_route_dialogue(visible)
        telemetry.event(
            "mission_preview_pre_start_visible_probe",
            timer_seconds=_elapsed(timer_start),
            visible_ui=fast.compact_visible_ui(visible),
            route_dialogue_visible=dialogue_visible,
        )
        dialogue_observation = {
            "timer_seconds": _elapsed(timer_start),
            "visible_ui": fast.compact_visible_ui(visible),
            "route_dialogue_visible": dialogue_visible,
            "action": "click_start_thumbnail_directly",
        }
        if dialogue_visible:
            telemetry.event("mission_preview_dialogue_observed", **dialogue_observation)
    else:
        dialogue_observation = {
            "timer_seconds": _elapsed(timer_start),
            "visible_ui": None,
            "route_dialogue_visible": None,
            "action": "click_start_thumbnail_directly",
            "pre_start_visible_probe": "skipped_after_proven_hover_target",
        }
        telemetry.event("mission_preview_pre_start_probe_skipped", **dialogue_observation)

    before_timer = read_in_game_timer(
        profile,
        label="start_mission_click_before",
        use_memory=use_memory_timer,
        timer_address=memory_timer_address,
        live_timer_address=memory_live_timer_address,
        live_timer_kind=memory_live_timer_kind,
    )
    if sys.platform.startswith("win"):
        x, y = fast.WINDOWS_HOVER_CONTROL_POINTS.get(
            "mission_preview_board",
            (1450, 790),
        )
        click = fast.click_hovered_point(
            "mission_preview_board",
            x,
            y,
            hover_seconds=hover_seconds,
            settle_seconds=settle_seconds,
            hold_seconds=hold_seconds,
        )
    else:
        click = fast.click_ui_control(
            "mission_preview_board",
            settle_seconds=settle_seconds,
            hold_seconds=hold_seconds,
        )
    click_wall_seconds = _elapsed(timer_start)
    telemetry.event(
        "start_mission_click",
        timer_seconds=click_wall_seconds,
        before_in_game_timer=before_timer,
        click=click,
    )

    samples: list[dict[str, Any]] = []
    first_bridge_deployment_sample: dict[str, Any] | None = None
    started = time.perf_counter()
    result_status = "FAIL"
    result_reason = "deployment_not_detected"
    while time.perf_counter() - started <= max_seconds:
        frame = screenshots.capture_once(
            clock_state="deployment_probe",
            note="after_start_mission_click",
        )
        frame["timer_seconds"] = _elapsed(timer_start)
        frame_timer = _timer_sample_from_frame(frame, label="deployment_probe_frame")
        visible: dict[str, Any] | None = None
        snapshot: dict[str, Any] = {}
        deployment_yellow_signal: dict[str, Any] | None = None
        if deployment_trigger_source == "screenshot_yellow":
            deployment_yellow_signal = _deployment_yellow_signal_from_frame(frame)
            deployment_visible = bool(
                deployment_yellow_signal.get("deployment_visible")
            )
            snapshot = {}
        else:
            visible = fast._lightning_visible_ui_snapshot(include_ocr=False)
            snapshot = fast._lightning_live_snapshot()
            deployment_visible = fast.visible_deployment_screen(visible)
        bridge_deployment_ready = fast.deployment_snapshot_ready(snapshot)
        sample = {
            "timer_seconds": frame["timer_seconds"],
            "screenshot_path": frame.get("screenshot_path"),
            "frame_timer": frame_timer,
            "trigger_source": deployment_trigger_source,
            "visible_ui": (
                fast.compact_visible_ui(visible)
                if isinstance(visible, dict)
                else None
            ),
            "deployment_yellow_signal": deployment_yellow_signal,
            "deployment_visible": deployment_visible,
            "bridge_deployment_ready": bridge_deployment_ready,
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
        if bridge_deployment_ready and first_bridge_deployment_sample is None:
            first_bridge_deployment_sample = sample
        samples.append(sample)
        telemetry.event("deployment_probe", **sample)
        if deployment_visible:
            result_status = "PASS"
            result_reason = (
                "deployment_yellow_screenshot"
                if deployment_trigger_source == "screenshot_yellow"
                else "deployment_visible"
            )
            break
        time.sleep(max(0.05, interval_seconds))
    if result_status != "PASS" and first_bridge_deployment_sample is not None:
        result_status = "PARTIAL"
        result_reason = "bridge_deployment_ready_only"

    pause: dict[str, Any] | None = None
    after_pause_timer: dict[str, Any] | None = None
    if pause_after_click:
        pause = fast._lightning_ensure_pause_state(
            reason="timing_lab_start_mission_deployment_probe",
        )
        after_pause_timer = read_in_game_timer(
            profile,
            label="deployment_after_pause",
            use_memory=use_memory_timer,
            timer_address=memory_timer_address,
            live_timer_address=memory_live_timer_address,
            live_timer_kind=memory_live_timer_kind,
        )
        telemetry.event(
            "deployment_pause",
            timer_seconds=_elapsed(timer_start),
            click=pause,
            after_pause_timer=after_pause_timer,
        )

    return {
        "status": result_status,
        "reason": result_reason,
        "dialogue_observation": dialogue_observation,
        "before_in_game_timer": before_timer,
        "click": click,
        "click_wall_seconds": click_wall_seconds,
        "samples": samples,
        "first_bridge_deployment_sample": first_bridge_deployment_sample,
        "pause": pause,
        "after_pause_timer": after_pause_timer,
    }


def _deploy_recommended_status_ok(result: dict[str, Any]) -> bool:
    status = result.get("status")
    if status == "OK":
        return True
    deployments = result.get("deployments") or []
    ui_fallback = result.get("ui_fallback") or {}
    return (
        status == "WARN"
        and ui_fallback.get("status") == "OK"
        and len(deployments) >= 1
    )


def _compact_deploy_recommended_result(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"status": "UNKNOWN", "reason": "non_dict_result"}
    ui_fallback = result.get("ui_fallback") or {}
    return {
        "status": result.get("status") or ("ERROR" if result.get("error") else None),
        "reason": result.get("reason") or result.get("error"),
        "deployment_count": len(result.get("deployments") or []),
        "existing_deployment_count": len(result.get("existing_deployments") or {}),
        "phase": result.get("phase"),
        "ui_fallback_status": ui_fallback.get("status"),
        "accepted": _deploy_recommended_status_ok(result),
    }


def _compact_bridge_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": snapshot.get("status"),
        "phase": snapshot.get("phase"),
        "turn": snapshot.get("turn"),
        "active_mechs": snapshot.get("active_mechs"),
        "mech_count": snapshot.get("mech_count"),
        "deployment_zone_count": snapshot.get("deployment_zone_count"),
        "grid_power": snapshot.get("grid_power"),
        "in_active_mission": snapshot.get("in_active_mission"),
        "mission_id": snapshot.get("mission_id"),
        "bridge_heartbeat_alive": snapshot.get("bridge_heartbeat_alive"),
        "bridge_heartbeat_stale": snapshot.get("bridge_heartbeat_stale"),
    }


def _snapshot_after_deploy_confirm_live(snapshot: dict[str, Any]) -> bool:
    if not isinstance(snapshot, dict) or snapshot.get("status") != "OK":
        return False
    if snapshot.get("bridge_heartbeat_alive") is False:
        return False
    if snapshot.get("bridge_heartbeat_stale") is True:
        return False
    return snapshot.get("phase") in {"combat_enemy", "combat_player"}


def _snapshot_actionable_player_turn(snapshot: dict[str, Any]) -> bool:
    if not isinstance(snapshot, dict) or snapshot.get("status") != "OK":
        return False
    if snapshot.get("phase") != "combat_player":
        return False
    try:
        active_mechs = int(snapshot.get("active_mechs") or 0)
    except (TypeError, ValueError):
        active_mechs = 0
    return (
        active_mechs > 0
        and snapshot.get("bridge_heartbeat_alive") is not False
        and snapshot.get("bridge_heartbeat_stale") is not True
    )


def deploy_recommended_after_visible_deployment(
    *,
    timer_start: float,
    telemetry: TelemetryRecorder,
    screenshots: ScreenshotRecorder,
    profile: str,
    use_memory_timer: bool,
    memory_timer_address: int | None,
    memory_live_timer_address: int | None,
    memory_live_timer_kind: str | None,
    pause_after_deploy: bool,
    trigger_frame_timer: dict[str, Any] | None = None,
    capture_post_deploy_probe: bool = True,
) -> dict[str, Any]:
    if isinstance(trigger_frame_timer, dict):
        before_timer = {
            **trigger_frame_timer,
            "label": "deploy_recommended_trigger_frame",
        }
    else:
        before_timer = read_in_game_timer(
            profile,
            label="deploy_recommended_before",
            use_memory=use_memory_timer,
            timer_address=memory_timer_address,
            live_timer_address=memory_live_timer_address,
            live_timer_kind=memory_live_timer_kind,
        )
    telemetry.event(
        "deploy_recommended_start",
        timer_seconds=_elapsed(timer_start),
        before_in_game_timer=before_timer,
    )

    deploy_started = time.perf_counter()
    deploy = fast.cmd_deploy_recommended(
        profile=profile,
        ui_fallback=True,
        verify_after=False,
    )
    deploy_duration = round(time.perf_counter() - deploy_started, 3)
    compact_deploy = _compact_deploy_recommended_result(deploy)
    telemetry.event(
        "deploy_recommended_result",
        timer_seconds=_elapsed(timer_start),
        duration_seconds=deploy_duration,
        result=compact_deploy,
    )

    post_frame: dict[str, Any] | None = None
    post_frame_timer: dict[str, Any] | None = None
    after_timer: dict[str, Any] | None = None
    if capture_post_deploy_probe:
        post_frame = screenshots.capture_once(
            clock_state="post_deploy_probe",
            note="after_deploy_recommended",
        )
        post_frame["timer_seconds"] = _elapsed(timer_start)
        post_frame_timer = _timer_sample_from_frame(
            post_frame,
            label="post_deploy_frame",
        )
        after_timer = read_in_game_timer(
            profile,
            label="deploy_recommended_after",
            use_memory=use_memory_timer,
            timer_address=memory_timer_address,
            live_timer_address=memory_live_timer_address,
            live_timer_kind=memory_live_timer_kind,
        )
        telemetry.event(
            "post_deploy_probe",
            timer_seconds=post_frame["timer_seconds"],
            screenshot_path=post_frame.get("screenshot_path"),
            frame_timer=post_frame_timer,
            after_in_game_timer=after_timer,
        )
    else:
        telemetry.event(
            "post_deploy_probe_skipped",
            timer_seconds=_elapsed(timer_start),
            reason="confirm_after_deploy_hot_path",
        )

    pause: dict[str, Any] | None = None
    after_pause_timer: dict[str, Any] | None = None
    if pause_after_deploy:
        pause = fast._lightning_ensure_pause_state(
            reason="timing_lab_after_deploy_recommended",
        )
        after_pause_timer = read_in_game_timer(
            profile,
            label="deploy_recommended_after_pause",
            use_memory=use_memory_timer,
            timer_address=memory_timer_address,
            live_timer_address=memory_live_timer_address,
            live_timer_kind=memory_live_timer_kind,
        )
        telemetry.event(
            "deploy_recommended_pause",
            timer_seconds=_elapsed(timer_start),
            click=pause,
            after_pause_timer=after_pause_timer,
        )

    return {
        "status": "PASS" if compact_deploy.get("accepted") else "FAIL",
        "reason": "deploy_recommended_accepted"
        if compact_deploy.get("accepted")
        else "deploy_recommended_failed",
        "before_in_game_timer": before_timer,
        "deploy_duration_seconds": deploy_duration,
        "deploy_result": deploy,
        "deploy_result_compact": compact_deploy,
        "post_deploy_frame": post_frame,
        "post_deploy_frame_timer": post_frame_timer,
        "after_in_game_timer": after_timer,
        "pause": pause,
        "after_pause_timer": after_pause_timer,
    }


def confirm_deployment_and_observe_opening_turn(
    *,
    timer_start: float,
    telemetry: TelemetryRecorder,
    screenshots: ScreenshotRecorder,
    observe_seconds: float,
    screenshot_cadence: float,
    bridge_poll_seconds: float,
    extra_ready_frames: int,
    pause_after_ready: bool,
) -> dict[str, Any]:
    before_timer = _timer_sample_from_recorder(
        screenshots,
        label="deploy_confirm_click_before",
    )
    telemetry.event(
        "deploy_confirm_signal",
        timer_seconds=_elapsed(timer_start),
        signal_source="deploy_recommended_result",
        before_in_game_timer=before_timer,
        conclusion=(
            "deployment helper return is the fastest confirm-click signal; "
            "screenshots are retained as evidence only"
        ),
    )
    click_started = time.perf_counter()
    click = fast.click_control("deploy_confirm", settle_seconds=0.05)
    click_duration = round(time.perf_counter() - click_started, 3)
    confirm_click_wall = _elapsed(timer_start)
    telemetry.event(
        "deploy_confirm_click",
        timer_seconds=confirm_click_wall,
        before_in_game_timer=before_timer,
        duration_seconds=click_duration,
        click=click,
    )

    started = time.perf_counter()
    next_frame_at = started
    next_bridge_at = started
    frames: list[dict[str, Any]] = []
    bridge_samples: list[dict[str, Any]] = []
    first_confirm_live_bridge: dict[str, Any] | None = None
    first_player_ready_bridge: dict[str, Any] | None = None
    ready_frames_seen = 0
    ready_frame: dict[str, Any] | None = None

    while True:
        now = time.perf_counter()
        elapsed = now - started
        if elapsed >= max(0.0, observe_seconds):
            break

        did_work = False
        if now >= next_frame_at:
            frame = screenshots.capture_once(
                clock_state="post_confirm_observe",
                note="after_deploy_confirm",
            )
            frame["timer_seconds"] = _elapsed(timer_start)
            frame_timer = _timer_sample_from_frame(
                frame,
                label="post_confirm_observe_frame",
            )
            frame_sample = {
                "timer_seconds": frame["timer_seconds"],
                "screenshot_path": frame.get("screenshot_path"),
                "frame_timer": frame_timer,
                "after_player_ready_bridge": first_player_ready_bridge is not None,
            }
            frames.append(frame_sample)
            telemetry.event("post_confirm_frame", **frame_sample)
            if first_player_ready_bridge is not None:
                ready_frames_seen += 1
                if ready_frame is None:
                    ready_frame = frame_sample
            next_frame_at = max(
                next_frame_at + max(0.1, screenshot_cadence),
                time.perf_counter() + 0.01,
            )
            did_work = True

        now = time.perf_counter()
        if now >= next_bridge_at:
            snapshot = fast._lightning_live_snapshot()
            sample = {
                "timer_seconds": _elapsed(timer_start),
                "elapsed_after_confirm_seconds": round(now - started, 3),
                "snapshot": _compact_bridge_snapshot(snapshot),
                "confirm_live": _snapshot_after_deploy_confirm_live(snapshot),
                "player_ready": _snapshot_actionable_player_turn(snapshot),
            }
            if first_confirm_live_bridge is None and sample["confirm_live"]:
                sample["bridge_timer"] = _timer_sample_from_recorder(
                    screenshots,
                    label="deploy_confirm_bridge_live",
                )
                first_confirm_live_bridge = sample
            if first_player_ready_bridge is None and sample["player_ready"]:
                sample["bridge_timer"] = _timer_sample_from_recorder(
                    screenshots,
                    label="opening_player_turn_bridge_ready",
                )
                first_player_ready_bridge = sample
            bridge_samples.append(sample)
            telemetry.event("post_confirm_bridge_probe", **sample)
            next_bridge_at = max(
                next_bridge_at + max(0.05, bridge_poll_seconds),
                time.perf_counter() + 0.01,
            )
            did_work = True

        if (
            first_player_ready_bridge is not None
            and ready_frames_seen >= max(0, int(extra_ready_frames))
        ):
            break

        if not did_work:
            next_due = min(next_frame_at, next_bridge_at)
            time.sleep(max(0.01, min(0.05, next_due - time.perf_counter())))

    pause: dict[str, Any] | None = None
    after_pause_timer: dict[str, Any] | None = None
    if pause_after_ready and first_player_ready_bridge is not None:
        pause = fast.press_key(
            "esc",
            description="pause after opening player turn",
            app_name=fast.APP_NAME,
            settle_seconds=0.05,
        )
        after_pause_timer = _timer_sample_from_recorder(
            screenshots,
            label="opening_player_turn_after_pause",
        )
        telemetry.event(
            "opening_player_turn_pause",
            timer_seconds=_elapsed(timer_start),
            click=pause,
            after_pause_timer=after_pause_timer,
        )

    status = (
        "PASS"
        if click.get("status") == "OK" and first_player_ready_bridge is not None
        else "FAIL"
    )
    return {
        "status": status,
        "reason": (
            "opening_player_turn_bridge_ready"
            if first_player_ready_bridge is not None
            else "opening_player_turn_not_detected"
        ),
        "confirm_signal_source": "deploy_recommended_result",
        "player_turn_signal_source": "bridge_lua_live_snapshot",
        "visual_evidence_role": "2hz_screenshots_for_audit_not_primary_signal",
        "before_in_game_timer": before_timer,
        "click": click,
        "click_wall_seconds": confirm_click_wall,
        "click_duration_seconds": click_duration,
        "observe_seconds_requested": observe_seconds,
        "observed_seconds": round(time.perf_counter() - started, 3),
        "frames": frames,
        "bridge_samples": bridge_samples,
        "first_confirm_live_bridge": first_confirm_live_bridge,
        "first_player_ready_bridge": first_player_ready_bridge,
        "first_player_ready_frame_after_bridge": ready_frame,
        "pause": pause,
        "after_pause_timer": after_pause_timer,
    }


def run_opening_milestone(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or _now_run_id()
    memory_timer_address = _parse_optional_timer_address(args.memory_timer_address)
    memory_live_timer_address = _parse_optional_timer_address(args.memory_live_timer_address)
    memory_live_timer_kind = args.memory_live_timer_kind
    confirm_after_deploy = bool(args.confirm_after_deploy)
    deploy_after_visible_deployment = bool(
        args.deploy_after_visible_deployment or confirm_after_deploy
    )
    deployment_trigger_source = str(args.deployment_trigger_source).replace("-", "_")
    if deploy_after_visible_deployment:
        deployment_trigger_source = "screenshot_yellow"
    click_start_mission = bool(args.click_start_mission or deploy_after_visible_deployment)
    click_red_mission = bool(args.click_red_mission or click_start_mission)
    route_slice = (
        "main_menu_to_archive_red_map_to_opening_player_turn"
        if confirm_after_deploy
        else
        "main_menu_to_archive_red_map_to_deployed_mechs"
        if deploy_after_visible_deployment
        else "main_menu_to_archive_red_map_to_deployment"
        if click_start_mission
        else "main_menu_to_archive_red_map_to_preview"
        if click_red_mission
        else "main_menu_to_archive_red_map"
    )
    telemetry = TelemetryRecorder(run_id=run_id, root=ROOT / "recordings")
    telemetry.write_manifest(
        {
            "achievement": "Lightning War",
            "route_slice": route_slice,
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
            "click_red_mission": click_red_mission,
            "click_start_mission": click_start_mission,
            "deploy_after_visible_deployment": deploy_after_visible_deployment,
            "confirm_after_deploy": confirm_after_deploy,
            "deployment_trigger_source": deployment_trigger_source,
            "pause_after_red_mission_click": (
                bool(args.pause_after_red_mission_click)
                if click_red_mission and not click_start_mission
                else None
            ),
            "pause_after_start_mission_click": (
                bool(args.pause_after_start_mission_click)
                and not deploy_after_visible_deployment
                if click_start_mission
                else None
            ),
            "pause_after_deploy_recommended": (
                bool(args.pause_after_deploy_recommended)
                and not confirm_after_deploy
                if deploy_after_visible_deployment
                else None
            ),
            "post_confirm_observe_seconds": (
                args.post_confirm_observe_seconds if confirm_after_deploy else None
            ),
            "post_confirm_bridge_poll_seconds": (
                args.post_confirm_bridge_poll_seconds
                if confirm_after_deploy
                else None
            ),
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
    detected_frame_timer = red_detection.get("detected_frame_timer")
    if isinstance(detected_frame_timer, dict):
        in_game_timers["red_map_detected_frame"] = detected_frame_timer
    paired_red_timer = (
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
    in_game_timers["red_map_detected_paired_after_detection"] = paired_red_timer
    in_game_timers["red_map_detected"] = (
        detected_frame_timer
        if _timer_sample_seconds(detected_frame_timer) is not None
        else paired_red_timer
    )
    mission_preview: dict[str, Any] | None = None
    if click_red_mission and red_detection.get("status") == "PASS":
        mission_preview = click_selected_red_mission_preview(
            timer_start=timer_start,
            telemetry=telemetry,
            screenshots=screenshots,
            red_detection=red_detection,
            profile=args.profile,
            use_memory_timer=args.memory_timer_probe,
            memory_timer_address=memory_timer_address,
            memory_live_timer_address=memory_live_timer_address,
            memory_live_timer_kind=memory_live_timer_kind,
            hover_seconds=args.red_mission_click_hover_seconds,
            settle_seconds=args.red_mission_click_settle_seconds,
            hold_seconds=args.red_mission_click_hold_seconds,
            pause_after_click=(
                bool(args.pause_after_red_mission_click)
                and not click_start_mission
            ),
        )
        in_game_timers["mission_preview_frame"] = (
            mission_preview.get("preview_frame_timer")
            if isinstance(mission_preview, dict)
            else None
        )
        in_game_timers["mission_preview_after_click"] = (
            mission_preview.get("after_preview_timer")
            if isinstance(mission_preview, dict)
            else None
        )
        in_game_timers["mission_preview_after_pause"] = (
            mission_preview.get("after_pause_timer")
            if isinstance(mission_preview, dict)
            else None
        )
    start_mission: dict[str, Any] | None = None
    deployment_result: dict[str, Any] | None = None
    confirm_result: dict[str, Any] | None = None
    if click_start_mission and isinstance(mission_preview, dict):
        start_mission = click_start_mission_from_preview(
            timer_start=timer_start,
            telemetry=telemetry,
            screenshots=screenshots,
            profile=args.profile,
            use_memory_timer=args.memory_timer_probe,
            memory_timer_address=memory_timer_address,
            memory_live_timer_address=memory_live_timer_address,
            memory_live_timer_kind=memory_live_timer_kind,
            settle_seconds=args.start_mission_click_settle_seconds,
            hover_seconds=args.start_mission_click_hover_seconds,
            hold_seconds=args.start_mission_click_hold_seconds,
            max_seconds=args.deployment_timeout_seconds,
            interval_seconds=args.deployment_probe_interval_seconds,
            pause_after_click=(
                bool(args.pause_after_start_mission_click)
                and not deploy_after_visible_deployment
            ),
            pre_start_visible_probe=args.start_mission_pre_click_probe,
            deployment_trigger_source=deployment_trigger_source,
        )
        in_game_timers["start_mission_click_before"] = start_mission.get(
            "before_in_game_timer"
        )
        if start_mission.get("samples"):
            first_deployment_sample = start_mission["samples"][0]
            in_game_timers["deployment_first_probe_frame"] = (
                first_deployment_sample.get("frame_timer")
                if isinstance(first_deployment_sample, dict)
                else None
            )
            deployment_visible_samples = [
                sample
                for sample in start_mission["samples"]
                if isinstance(sample, dict) and sample.get("deployment_visible")
            ]
            if deployment_visible_samples:
                in_game_timers["deployment_visible_frame"] = deployment_visible_samples[
                    0
                ].get("frame_timer")
        in_game_timers["deployment_after_pause"] = start_mission.get(
            "after_pause_timer"
        )
    if (
        deploy_after_visible_deployment
        and isinstance(start_mission, dict)
        and start_mission.get("status") == "PASS"
    ):
        deployment_visible_samples = [
            sample
            for sample in start_mission.get("samples", [])
            if isinstance(sample, dict) and sample.get("deployment_visible")
        ]
        deployment_trigger_frame_timer = (
            deployment_visible_samples[0].get("frame_timer")
            if deployment_visible_samples
            else None
        )
        deployment_result = deploy_recommended_after_visible_deployment(
            timer_start=timer_start,
            telemetry=telemetry,
            screenshots=screenshots,
            profile=args.profile,
            use_memory_timer=args.memory_timer_probe,
            memory_timer_address=memory_timer_address,
            memory_live_timer_address=memory_live_timer_address,
            memory_live_timer_kind=memory_live_timer_kind,
            pause_after_deploy=(
                bool(args.pause_after_deploy_recommended)
                and not confirm_after_deploy
            ),
            trigger_frame_timer=deployment_trigger_frame_timer,
            capture_post_deploy_probe=not confirm_after_deploy,
        )
        in_game_timers["deploy_recommended_before"] = deployment_result.get(
            "before_in_game_timer"
        )
        in_game_timers["deploy_recommended_after"] = deployment_result.get(
            "after_in_game_timer"
        )
        in_game_timers["post_deploy_frame"] = deployment_result.get(
            "post_deploy_frame_timer"
        )
        in_game_timers["deploy_recommended_after_pause"] = deployment_result.get(
            "after_pause_timer"
        )
    if (
        confirm_after_deploy
        and isinstance(deployment_result, dict)
        and deployment_result.get("status") == "PASS"
    ):
        confirm_result = confirm_deployment_and_observe_opening_turn(
            timer_start=timer_start,
            telemetry=telemetry,
            screenshots=screenshots,
            observe_seconds=args.post_confirm_observe_seconds,
            screenshot_cadence=args.screenshot_cadence,
            bridge_poll_seconds=args.post_confirm_bridge_poll_seconds,
            extra_ready_frames=args.post_confirm_extra_ready_frames,
            pause_after_ready=args.pause_after_opening_player_turn,
        )
        in_game_timers["deploy_confirm_click_before"] = confirm_result.get(
            "before_in_game_timer"
        )
        first_confirm_live = confirm_result.get("first_confirm_live_bridge") or {}
        in_game_timers["deploy_confirm_bridge_live"] = first_confirm_live.get(
            "bridge_timer"
        )
        first_player_ready = confirm_result.get("first_player_ready_bridge") or {}
        in_game_timers["opening_player_turn_bridge_ready"] = first_player_ready.get(
            "bridge_timer"
        )
        ready_frame = confirm_result.get("first_player_ready_frame_after_bridge") or {}
        in_game_timers["opening_player_turn_first_frame_after_bridge"] = (
            ready_frame.get("frame_timer")
        )
        in_game_timers["opening_player_turn_after_pause"] = confirm_result.get(
            "after_pause_timer"
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
    if deploy_after_visible_deployment:
        status = (
            "PASS"
            if status == "PASS"
            and isinstance(deployment_result, dict)
            and deployment_result.get("status") == "PASS"
            else "FAIL"
        )
    if confirm_after_deploy:
        status = (
            "PASS"
            if status == "PASS"
            and isinstance(confirm_result, dict)
            and confirm_result.get("status") == "PASS"
            else "FAIL"
        )
    if status != "PASS":
        next_patch = (
            "Fix Confirm click or opening enemy-turn/player-turn detection."
            if confirm_after_deploy
            else
            "Fix deployment placement trigger after deployment-visible screenshot."
            if deploy_after_visible_deployment
            else "Improve Archive intro wait/dismissal or red-region detector."
        )
    elif confirm_after_deploy:
        next_patch = "Compare bridge/player-turn timing with screenshot evidence; then measure first combat action."
    elif deploy_after_visible_deployment:
        next_patch = "Measure deploy Confirm click after user review."
    elif click_start_mission:
        next_patch = "Measure deployment placement and confirm click after user review."
    elif click_red_mission:
        next_patch = "Measure preview-to-deployment click after user review."
    else:
        next_patch = "Extend to red_map_to_mission_preview after user review."
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "branch_label": branch_label,
        "route_slice": route_slice,
        "startup": startup,
        "marks": marks,
        "in_game_timers": in_game_timers,
        "red_detection": red_detection,
        "mission_preview": mission_preview,
        "start_mission": start_mission,
        "deploy_recommended": deployment_result,
        "deploy_confirm": confirm_result,
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
        "--click-red-mission",
        action="store_true",
        help="After detecting red regions, click the selected red mission immediately.",
    )
    parser.add_argument("--red-mission-click-hover-seconds", type=float, default=0.05)
    parser.add_argument("--red-mission-click-settle-seconds", type=float, default=0.25)
    parser.add_argument("--red-mission-click-hold-seconds", type=float, default=0.12)
    parser.add_argument(
        "--pause-after-red-mission-click",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Pause immediately after capturing the post-click mission preview frame.",
    )
    parser.add_argument(
        "--click-start-mission",
        action="store_true",
        help=(
            "After opening the selected mission preview, clear preview dialogue, "
            "click Start Mission via the preview board, capture deployment probes, "
            "and pause."
        ),
    )
    parser.add_argument("--start-mission-click-settle-seconds", type=float, default=0.25)
    parser.add_argument("--start-mission-click-hover-seconds", type=float, default=0.05)
    parser.add_argument("--start-mission-click-hold-seconds", type=float, default=0.12)
    parser.add_argument(
        "--start-mission-pre-click-probe",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Run the slower visible-UI probe before clicking Start Mission. "
            "Default is off after the thumbnail hover target was proven."
        ),
    )
    parser.add_argument("--deployment-timeout-seconds", type=float, default=8.0)
    parser.add_argument("--deployment-probe-interval-seconds", type=float, default=0.5)
    parser.add_argument(
        "--deployment-trigger-source",
        choices=("visible-ui", "screenshot-yellow"),
        default="visible-ui",
        help=(
            "Detection source for Start Mission -> deployment. The deploy "
            "extension forces screenshot-yellow so the trigger is the timing "
            "lab frame itself."
        ),
    )
    parser.add_argument(
        "--pause-after-start-mission-click",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Pause after the deployment probe window completes.",
    )
    parser.add_argument(
        "--deploy-after-visible-deployment",
        action="store_true",
        help=(
            "After the screenshot probe first detects deployment squares, run "
            "deploy_recommended without clicking Confirm."
        ),
    )
    parser.add_argument(
        "--pause-after-deploy-recommended",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Pause after deploy_recommended and the post-deploy screenshot.",
    )
    parser.add_argument(
        "--confirm-after-deploy",
        action="store_true",
        help=(
            "After deploy_recommended accepts placements, click Deploy Confirm "
            "immediately and observe the opening enemy turn."
        ),
    )
    parser.add_argument("--post-confirm-observe-seconds", type=float, default=30.0)
    parser.add_argument("--post-confirm-bridge-poll-seconds", type=float, default=0.2)
    parser.add_argument("--post-confirm-extra-ready-frames", type=int, default=1)
    parser.add_argument(
        "--pause-after-opening-player-turn",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Pause once the bridge reports the first actionable player turn.",
    )
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
