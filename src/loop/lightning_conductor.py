"""In-process autonomous Lightning War conductor."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from src.loop.lightning_telemetry import (
    ScreenshotRecorder,
    TelemetryRecorder,
    generate_frame_delta_report,
)


LIGHTNING_WAR = "Lightning War"
HARD_STOP_TOKENS = (
    "SAFETY_BLOCKED",
    "RESEARCH_REQUIRED",
    "INVESTIGATE",
    "THREAT_AUDIT",
    "POST_ENEMY",
    "DESYNC",
    "ROUTE_MISSION_MISMATCH",
    "BUDGET_EXCEEDED",
    "BRIDGE_SNAPSHOT_UNAVAILABLE",
)


@dataclass
class AutonomousLightningConfig:
    profile: str = "Alpha"
    achievement: str = LIGHTNING_WAR
    advanced_content: str = "off"
    difficulty: int = 0
    first_island: str = "archive"
    max_attempts: int = 1
    max_segments: int = 20
    segment_steps: int = 12
    time_limit: float = 2.0
    max_wall_seconds: float | None = None
    segment_timeout: float = 420.0
    abandon_seconds: float = 29 * 60
    first_island_gate_seconds: float = 15 * 60
    second_island_start_gate_seconds: float = 16.75 * 60
    screenshot_cadence: float = 2.0
    screenshots: bool = True
    route_auto_start: bool = False
    start_from_verified_setup: bool = False
    achievement_sync: bool = True
    dry_run: bool = False


class AutonomousLightningConductor:
    def __init__(self, config: AutonomousLightningConfig) -> None:
        self.config = config
        self.telemetry: TelemetryRecorder | None = None
        self.screenshots: ScreenshotRecorder | None = None

    def run(self) -> dict[str, Any]:
        from src.loop import commands

        session = commands._load_session()
        run_id = str(session.run_id or f"lightning_{int(time.time())}")
        self.telemetry = TelemetryRecorder(run_id)
        self.telemetry.write_manifest(
            {
                "achievement": self.config.achievement,
                "profile": self.config.profile,
                "squad": session.squad,
                "difficulty": self.config.difficulty,
                "advanced_content": self.config.advanced_content,
                "mode": "hybrid_theory",
                "first_island_gate_seconds": self.config.first_island_gate_seconds,
                "second_island_start_gate_seconds": (
                    self.config.second_island_start_gate_seconds
                ),
            }
        )
        self.telemetry.event(
            "autonomous_start",
            status="STARTED",
            session={
                "run_id": session.run_id,
                "squad": session.squad,
                "difficulty": session.difficulty,
                "achievement_targets": session.achievement_targets,
            },
        )
        if self.config.screenshots:
            self.screenshots = ScreenshotRecorder(
                self.telemetry,
                cadence_seconds=self.config.screenshot_cadence,
            )
            self.screenshots.start()

        status = "BLOCKED"
        reason = "unknown"
        result: dict[str, Any] = {}
        try:
            result = self._run_inner(commands)
            status = str(result.get("status") or status)
            reason = str(result.get("reason") or reason)
            return result
        finally:
            if self.screenshots is not None:
                self.screenshots.stop()
                self.screenshots.capture_once(clock_state="final", note=reason)
            report = generate_frame_delta_report(self.telemetry.run_dir)
            self.telemetry.event("frame_delta_report", **report)
            self.telemetry.summary(
                status=status,
                reason=reason,
                extra={
                    "telemetry_dir": str(self.telemetry.telemetry_dir),
                    "frame_report": report.get("status"),
                },
            )

    def _run_inner(self, commands: Any) -> dict[str, Any]:
        cfg = self.config
        assert self.telemetry is not None

        if cfg.achievement.lower() != LIGHTNING_WAR.lower():
            return self._finish(
                "BLOCKED",
                "unsupported_achievement",
                achievement=cfg.achievement,
            )

        guard = self._span(
            "pause_guard_initial",
            commands.cmd_lightning_pause_guard,
            profile=cfg.profile,
            seconds=5.0,
            interval=0.25,
            once=True,
        )
        if _must_act_now(guard):
            self.telemetry.event(
                "codex_handoff",
                status="BLOCKED_UNPAUSED_CLOCK_TICKING",
                guard=_compact(guard),
            )
            return self._finish(
                "BLOCKED_UNPAUSED_CLOCK_TICKING",
                "initial_state_not_safe_to_think",
                guard=_compact(guard),
            )

        if cfg.achievement_sync:
            sync = self._span(
                "achievements_initial",
                commands.cmd_achievements,
                sync_local=True,
            )
            if _achievement_unlocked(sync):
                return self._finish("SUCCESS", "achievement_already_unlocked", sync=_compact(sync))

        initial_visible_ui = _visible_ui_name(guard)
        if cfg.start_from_verified_setup or initial_visible_ui == "new_game_setup":
            if initial_visible_ui == "new_game_setup":
                setup_start = self._span(
                    "setup_start",
                    commands.cmd_lightning_ui,
                    control="setup_start",
                )
                if setup_start.get("status") != "OK":
                    return self._finish(
                        "BLOCKED",
                        "setup_start_failed",
                        setup_start=_compact(setup_start),
                    )
            setup = self._prepare_setup(commands)
            if setup.get("status") != "PASS":
                return self._finish(
                    "BLOCKED",
                    "setup_not_verified",
                    setup=_compact(setup),
                )
            start = self._span(
                "lightning_start_run",
                commands.cmd_lightning_start_run,
                profile=cfg.profile,
                difficulty=cfg.difficulty,
                advanced_content=cfg.advanced_content,
                first_island=cfg.first_island,
                time_limit=cfg.time_limit,
                max_steps=cfg.segment_steps,
                max_turns=6,
                max_wait=45.0,
                max_wall_seconds=cfg.max_wall_seconds,
                route_auto_start=cfg.route_auto_start,
                run_segment=False,
                allow_objective_loss=True,
                dry_run=cfg.dry_run,
            )
            if str(start.get("status")) not in {"OK", "DRY_RUN"}:
                return self._finish("BLOCKED", "start_run_failed", start=_compact(start))

        preflight = self._span(
            "lightning_preflight",
            commands.cmd_lightning_preflight,
            profile=cfg.profile,
            set_fast_bridge=False,
            advanced_content=cfg.advanced_content,
        )
        if str(preflight.get("status")) == "FAIL":
            return self._finish(
                "BLOCKED",
                "preflight_failed",
                preflight=_compact(preflight),
            )

        best_timer = _timer_seconds(preflight)
        for attempt_index in range(1, max(1, cfg.max_attempts) + 1):
            self.telemetry.event(
                "attempt_start",
                attempt_index=attempt_index,
                best_timer_seconds=best_timer,
            )
            for segment_index in range(1, max(1, cfg.max_segments) + 1):
                segment = self._span(
                    "lightning_segment",
                    commands.cmd_lightning_segment,
                    profile=cfg.profile,
                    time_limit=cfg.time_limit,
                    max_steps=cfg.segment_steps,
                    max_turns=6,
                    max_wait=45.0,
                    click_ui=True,
                    set_fast_bridge=True,
                    run_preflight=(segment_index == 1),
                    dry_run=cfg.dry_run,
                    max_wall_seconds=(
                        cfg.max_wall_seconds
                        if cfg.max_wall_seconds is not None
                        else cfg.segment_timeout
                    ),
                    pause_on_stop=True,
                    quiet=True,
                    resume_if_paused=True,
                    auto_clear_panels=True,
                    allow_objective_loss=True,
                    lightning_speed_loss_policy=True,
                    route_auto_start=cfg.route_auto_start,
                )
                timer = _timer_seconds(segment)
                if timer is not None:
                    best_timer = max(best_timer or 0.0, timer)
                    self.telemetry.event(
                        "clock_sample",
                        game_seconds=timer,
                        game_timer=_timer_label(segment),
                        attempt_index=attempt_index,
                        segment_index=segment_index,
                    )
                if cfg.achievement_sync and _safe_to_think(segment):
                    sync = self._span(
                        "achievements_segment",
                        commands.cmd_achievements,
                        sync_local=True,
                    )
                    if _achievement_unlocked(sync):
                        return self._finish(
                            "SUCCESS",
                            "achievement_confirmed_sync",
                            sync=_compact(sync),
                        )
                if _hard_stop(segment):
                    commands.cmd_lightning_ui("ensure_pause")
                    return self._finish(
                        "BLOCKED",
                        "hard_gate",
                        segment=_compact(segment),
                    )
                if best_timer is not None and best_timer >= cfg.abandon_seconds:
                    commands.cmd_lightning_ui("ensure_pause")
                    return self._finish(
                        "RESTART_RECOMMENDED",
                        "timer_abandon_gate",
                        game_seconds=best_timer,
                    )
                if not _safe_to_think(segment) and _must_act_now(segment):
                    self.telemetry.event(
                        "guard_sample",
                        status="MUST_ACT_NOW",
                        segment=_compact(segment),
                    )
                    continue
                if _route_ready(segment) and not cfg.route_auto_start:
                    return self._finish(
                        "PARKED_SAFE",
                        "route_ready_requires_autostart_or_safe_policy",
                        primary_next_command=segment.get("primary_next_command"),
                        telemetry_dir=str(self.telemetry.telemetry_dir),
                    )
                if str(segment.get("reason")) in {"max_steps_reached", "repeated_progress_state"}:
                    break
            self.telemetry.event(
                "restart_decision",
                attempt_index=attempt_index,
                status="retry_without_code_change",
                reason="attempt_loop_exhausted",
            )

        commands.cmd_lightning_ui("ensure_pause")
        return self._finish(
            "PARKED_SAFE",
            "max_attempts_reached",
            telemetry_dir=str(self.telemetry.telemetry_dir),
        )

    def _prepare_setup(self, commands: Any) -> dict[str, Any]:
        cfg = self.config
        setup = self._span(
            "verify_setup",
            commands.cmd_verify_setup_screen,
            expected_difficulty=cfg.difficulty,
            advanced_content=cfg.advanced_content,
        )
        if setup.get("status") == "PASS" or cfg.dry_run:
            return setup
        clicks = setup.get("click_plan") or []
        if not clicks:
            return setup
        from src.control.mac_click import click_window_point

        for click in clicks:
            click_result = click_window_point(
                int(click["x"]),
                int(click["y"]),
                description=str(click.get("description") or "setup adjustment"),
                dry_run=cfg.dry_run,
            )
            self.telemetry.event(
                "setup_click",
                click=click,
                click_result=click_result,
            )
            if click_result.get("status") != "OK":
                return {
                    "status": "FAIL",
                    "reason": "setup_click_failed",
                    "click": click,
                    "click_result": click_result,
                }
        return self._span(
            "verify_setup_after_clicks",
            commands.cmd_verify_setup_screen,
            expected_difficulty=cfg.difficulty,
            advanced_content=cfg.advanced_content,
        )

    def _span(
        self,
        label: str,
        fn: Callable[..., dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        assert self.telemetry is not None
        span_id = f"span_{label}_{int(time.monotonic() * 1000)}"
        start = time.monotonic()
        self.telemetry.event("command_span", span_id=span_id, label=label, status="start")
        try:
            result = fn(**kwargs)
        except Exception as exc:
            elapsed = round(time.monotonic() - start, 3)
            self.telemetry.event(
                "command_span",
                span_id=span_id,
                label=label,
                status="exception",
                wall_duration_seconds=elapsed,
                error=str(exc),
            )
            raise
        elapsed = round(time.monotonic() - start, 3)
        self.telemetry.event(
            "command_span",
            span_id=span_id,
            label=label,
            status="finish",
            wall_duration_seconds=elapsed,
            result_status=result.get("status"),
            result_reason=result.get("reason"),
            game_timer=_timer_label(result),
            game_seconds=_timer_seconds(result),
        )
        return result

    def _finish(self, status: str, reason: str, **payload: Any) -> dict[str, Any]:
        assert self.telemetry is not None
        result = {
            "status": status,
            "reason": reason,
            "telemetry_dir": str(self.telemetry.telemetry_dir),
            **payload,
        }
        self.telemetry.event("autonomous_finish", **result)
        return result


def _compact(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    keep = {}
    for key in (
        "status",
        "reason",
        "next_step",
        "game_budget",
        "effective_timer",
        "pause_guard",
        "issues",
        "warnings",
        "primary_next_command",
        "primary_route_candidate_index",
        "last_attempt_summary",
    ):
        if key in value:
            keep[key] = value[key]
    return keep


def _timer_seconds(result: dict[str, Any] | None) -> float | None:
    if not isinstance(result, dict):
        return None
    for container in (result.get("game_budget"), result.get("effective_timer")):
        if isinstance(container, dict) and container.get("game_seconds") is not None:
            try:
                return float(container["game_seconds"])
            except (TypeError, ValueError):
                return None
    last_attempt = result.get("last_attempt")
    if isinstance(last_attempt, dict):
        return _timer_seconds(last_attempt)
    return None


def _timer_label(result: dict[str, Any] | None) -> str | None:
    if not isinstance(result, dict):
        return None
    for container in (result.get("game_budget"), result.get("effective_timer")):
        if isinstance(container, dict) and container.get("game_timer") is not None:
            return str(container["game_timer"])
    return None


def _achievement_unlocked(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    return LIGHTNING_WAR in (result.get("unlocked_list") or [])


def _hard_stop(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    text = f"{result.get('status') or ''} {result.get('reason') or ''}".upper()
    return any(token in text for token in HARD_STOP_TOKENS)


def _route_ready(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    return result.get("reason") in {"route_ready", "visible_island_map_without_bridge"} or bool(
        result.get("primary_next_command")
    )


def _safe_to_think(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    if _visible_ui_name(result) == "new_game_setup":
        return True
    guard = result.get("pause_guard")
    if isinstance(guard, dict):
        if guard.get("pause_verified") or guard.get("timer_stop_verified"):
            return True
        visible = guard.get("visible_ui") or guard.get("pause_verify")
        if isinstance(visible, dict) and visible.get("visible_ui") == "pause_menu":
            return True
    if result.get("status") in {"PARKED_SAFE", "SUCCESS"}:
        return True
    return False


def _visible_ui_name(result: dict[str, Any] | None) -> str | None:
    if not isinstance(result, dict):
        return None
    visible = result.get("visible_ui")
    if isinstance(visible, dict) and visible.get("visible_ui"):
        return str(visible["visible_ui"])
    last_poll = result.get("last_poll")
    if isinstance(last_poll, dict):
        nested = _visible_ui_name(last_poll)
        if nested:
            return nested
    pause_guard = result.get("pause_guard")
    if isinstance(pause_guard, dict):
        nested = _visible_ui_name(pause_guard)
        if nested:
            return nested
    return None


def _must_act_now(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    if _safe_to_think(result):
        return False
    text = f"{result.get('status') or ''} {result.get('reason') or ''}".lower()
    return (
        "live" in text
        or "deployment" in text
        or "pause_not_verified" in text
        or "unpauseable" in text
    )


def cmd_lightning_autonomous(**kwargs: Any) -> dict[str, Any]:
    """CLI entry point for the telemetry-backed autonomous conductor."""
    from src.loop.commands import _print_result

    config = AutonomousLightningConfig(**kwargs)
    conductor = AutonomousLightningConductor(config)
    result = conductor.run()
    _print_result(result)
    return result
