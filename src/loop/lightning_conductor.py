"""In-process autonomous Lightning War conductor."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from src.loop.lightning_telemetry import (
    ScreenshotRecorder,
    TelemetryRecorder,
    generate_frame_delta_report,
)


LIGHTNING_WAR = "Lightning War"
HARD_STOP_TOKENS = (
    "RESEARCH_REQUIRED",
    "INVESTIGATE",
    "THREAT_AUDIT",
    "POST_ENEMY",
    "DESYNC",
    "BUDGET_EXCEEDED",
    "BRIDGE_SNAPSHOT_UNAVAILABLE",
    "MISSION_PREVIEW_REQUIRES_ROUTE_VALIDATION",
)
RESTARTABLE_ATTEMPT_STOP_TOKENS = (
    "RESEARCH_REQUIRED",
    "INVESTIGATE",
    "THREAT_AUDIT",
    "POST_ENEMY_AUDIT_MISSED_WINDOW",
    "POST_ENEMY",
    "SAFETY_BLOCKED",
    "DESYNC",
    "BRIDGE_SNAPSHOT_UNAVAILABLE",
    "DEPLOYMENT_VISIBLE_UI_NOT_DEPLOYMENT",
    "VISUAL_REGION_INDEX_NOT_FOUND",
    "STALE_ACTIVE_COMBAT_VISIBLE_ISLAND_MAP",
    "BUDGET_EXCEEDED",
)
RESTART_RECOVERY_SAFE_CONTROLS = {
    "kia_understood",
    "modal_understood",
}


@dataclass
class AutonomousLightningConfig:
    profile: str = "Alpha"
    achievement: str = LIGHTNING_WAR
    mode: str = "baseline"
    target_islands: int = 2
    advanced_content: str = "off"
    difficulty: int = 0
    first_island: str = "archive"
    max_attempts: int = 1
    max_segments: int = 20
    segment_steps: int = 12
    time_limit: float | None = None
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

    def __post_init__(self) -> None:
        if self.mode not in {"baseline", "speed"}:
            raise ValueError(f"unsupported Lightning War mode: {self.mode}")
        self.target_islands = max(1, int(self.target_islands))
        if self.time_limit is None:
            self.time_limit = 2.0 if self.mode == "speed" else 10.0


class AutonomousLightningConductor:
    def __init__(self, config: AutonomousLightningConfig) -> None:
        self.config = config
        self.telemetry: TelemetryRecorder | None = None
        self.screenshots: ScreenshotRecorder | None = None

    def run(self) -> dict[str, Any]:
        from src.loop import commands

        session = _load_current_session(commands)
        run_id = _telemetry_run_id(session)
        self.telemetry = TelemetryRecorder(run_id)
        self.telemetry.write_manifest(self._manifest_payload(session))
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
            if _safe_to_finalize(result):
                report = generate_frame_delta_report(self.telemetry.run_dir)
            else:
                report = {
                    "status": "SKIPPED",
                    "reason": "unsafe_to_generate_frame_deltas",
                    "final_status": status,
                    "final_reason": reason,
                }
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
            self._rehome_telemetry_if_session_changed(
                commands,
                reason="fresh_lightning_start_run",
            )

        preflight = self._span(
            "lightning_preflight",
            commands.cmd_lightning_preflight,
            profile=cfg.profile,
            set_fast_bridge=False,
            advanced_content=cfg.advanced_content,
        )
        if str(preflight.get("status")) == "FAIL":
            restart_reason = _restartable_preflight_failure(preflight)
            if restart_reason is not None:
                return self._finish(
                    "RESTART_RECOMMENDED",
                    restart_reason,
                    ensure_pause=self._ensure_pause(commands),
                    preflight=_compact(preflight),
                )
            return self._finish(
                "BLOCKED",
                "preflight_failed",
                preflight=_compact(preflight),
            )

        best_timer = _timer_seconds(preflight)
        session = _load_current_session(commands)
        pace_gate = self._pace_gate(session, best_timer)
        if pace_gate is not None:
            pace_payload = dict(pace_gate)
            pace_reason = str(pace_payload.pop("reason"))
            return self._finish(
                "RESTART_RECOMMENDED",
                pace_reason,
                ensure_pause=self._ensure_pause(commands),
                **pace_payload,
            )
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
                    route_speed_vetoes=(cfg.mode == "speed"),
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
                session = _load_current_session(commands)
                pace_gate = self._pace_gate(session, best_timer)
                if pace_gate is not None:
                    self.telemetry.event(
                        "pace_gate",
                        status="RESTART_RECOMMENDED",
                        **pace_gate,
                    )
                    pace_payload = dict(pace_gate)
                    pace_reason = str(pace_payload.pop("reason"))
                    return self._finish(
                        "RESTART_RECOMMENDED",
                        pace_reason,
                        ensure_pause=self._ensure_pause(commands),
                        **pace_payload,
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
                restart_reason = _restartable_attempt_stop(segment)
                if restart_reason is not None:
                    return self._finish(
                        "RESTART_RECOMMENDED",
                        restart_reason,
                        ensure_pause=self._ensure_pause(commands),
                        segment=_compact(segment),
                    )
                if _hard_stop(segment):
                    return self._finish(
                        "BLOCKED",
                        "hard_gate",
                        ensure_pause=self._ensure_pause(commands),
                        segment=_compact(segment),
                    )
                if best_timer is not None and best_timer >= cfg.abandon_seconds:
                    return self._finish(
                        "RESTART_RECOMMENDED",
                        "timer_abandon_gate",
                        ensure_pause=self._ensure_pause(commands),
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

        ensure_pause = self._ensure_pause(commands)
        if not _safe_to_think(ensure_pause):
            return self._finish(
                "RESTART_RECOMMENDED",
                "attempt_dead_unpausable",
                ensure_pause=ensure_pause,
                telemetry_dir=str(self.telemetry.telemetry_dir),
            )
        return self._finish(
            "PARKED_SAFE",
            "max_attempts_reached",
            ensure_pause=ensure_pause,
            telemetry_dir=str(self.telemetry.telemetry_dir),
        )

    def _pace_gate(self, session: Any, game_seconds: float | None) -> dict[str, Any] | None:
        cfg = self.config
        if game_seconds is None:
            return None
        completed = list(getattr(session, "islands_completed", []) or [])
        if not completed and float(game_seconds) >= float(cfg.first_island_gate_seconds):
            return {
                "reason": "first_island_pace_gate",
                "game_seconds": round(float(game_seconds), 3),
                "game_timer": _lightning_format_seconds(game_seconds),
                "gate_seconds": float(cfg.first_island_gate_seconds),
                "gate_timer": _lightning_format_seconds(cfg.first_island_gate_seconds),
                "islands_completed": completed,
            }
        if len(completed) == 1 and float(game_seconds) >= float(
            cfg.second_island_start_gate_seconds
        ):
            return {
                "reason": "second_island_start_pace_gate",
                "game_seconds": round(float(game_seconds), 3),
                "game_timer": _lightning_format_seconds(game_seconds),
                "gate_seconds": float(cfg.second_island_start_gate_seconds),
                "gate_timer": _lightning_format_seconds(
                    cfg.second_island_start_gate_seconds
                ),
                "islands_completed": completed,
            }
        return None

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

    def _ensure_pause(self, commands: Any) -> dict[str, Any]:
        return commands.cmd_lightning_ui("ensure_pause")

    def _manifest_payload(self, session: Any) -> dict[str, Any]:
        return {
            "achievement": self.config.achievement,
            "profile": self.config.profile,
            "squad": getattr(session, "squad", None),
            "difficulty": self.config.difficulty,
            "advanced_content": self.config.advanced_content,
            "mode": self.config.mode,
            "target_islands": self.config.target_islands,
            "time_limit": self.config.time_limit,
            "first_island_gate_seconds": self.config.first_island_gate_seconds,
            "second_island_start_gate_seconds": (
                self.config.second_island_start_gate_seconds
            ),
        }

    def _rehome_telemetry_if_session_changed(self, commands: Any, *, reason: str) -> None:
        """Move serious-attempt telemetry to the run id created by Start Run."""
        assert self.telemetry is not None
        session = _load_current_session(commands)
        new_run_id = _concrete_session_run_id(session)
        old_run_id = getattr(self.telemetry, "run_id", None)
        if not new_run_id or new_run_id == old_run_id:
            return

        old_telemetry = self.telemetry
        if self.screenshots is not None:
            self.screenshots.stop()
            self.screenshots = None
        old_telemetry.event(
            "telemetry_rehome",
            status="REHOMING",
            reason=reason,
            old_run_id=old_run_id,
            new_run_id=new_run_id,
        )
        old_telemetry.summary(
            status="REHOMED",
            reason=reason,
            extra={"new_telemetry_run_id": new_run_id},
        )

        self.telemetry = TelemetryRecorder(new_run_id)
        self.telemetry.write_manifest(self._manifest_payload(session))
        self.telemetry.event(
            "telemetry_rehome",
            status="OK",
            reason=reason,
            previous_run_id=old_run_id,
        )
        if self.config.screenshots:
            self.screenshots = ScreenshotRecorder(
                self.telemetry,
                cadence_seconds=self.config.screenshot_cadence,
            )
            self.screenshots.start()

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
        "ensure_pause",
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
    candidates = _timer_candidates(result)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[0]


def _timer_label(result: dict[str, Any] | None) -> str | None:
    candidates = _timer_candidates(result)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _timer_candidates(result: dict[str, Any] | None) -> list[tuple[float, str | None]]:
    if not isinstance(result, dict):
        return []
    candidates: list[tuple[float, str | None]] = []
    for container in (
        result.get("game_budget"),
        result.get("effective_timer"),
        result.get("budget"),
        result.get("visible_timer_budget"),
    ):
        if isinstance(container, dict) and container.get("game_seconds") is not None:
            try:
                seconds = float(container["game_seconds"])
            except (TypeError, ValueError):
                continue
            label = (
                str(container["game_timer"])
                if container.get("game_timer") is not None
                else None
            )
            candidates.append((seconds, label))
    for key in ("last_attempt", "guard", "pause_guard", "resume_guard"):
        nested = result.get(key)
        if isinstance(nested, dict):
            candidates.extend(_timer_candidates(nested))
    return candidates


def _load_current_session(commands: Any) -> Any:
    loader = getattr(commands, "_load_session", None)
    if callable(loader):
        return loader()

    class SessionView:
        islands_completed: list[str] = []

    return SessionView()


def _telemetry_run_id(session: Any) -> str:
    concrete = _concrete_session_run_id(session)
    if concrete:
        return concrete
    now = datetime.now()
    return now.strftime("lightning_%Y%m%d_%H%M%S") + f"_{now.microsecond // 1000:03d}"


def _concrete_session_run_id(session: Any) -> str | None:
    raw = str(getattr(session, "run_id", "") or "").strip()
    if raw and raw.lower() not in {"default", "lw", "none", "null"}:
        return raw
    return None


def _lightning_format_seconds(total_seconds: int | float | None) -> str:
    if total_seconds is None:
        return "unknown"
    seconds = max(0, int(float(total_seconds)))
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def _achievement_unlocked(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    return LIGHTNING_WAR in (result.get("unlocked_list") or [])


def _hard_stop(result: dict[str, Any] | None) -> bool:
    if _restartable_attempt_stop(result) is not None:
        return False
    return _find_stop_token(result, HARD_STOP_TOKENS) is not None


def _restartable_attempt_stop(result: dict[str, Any] | None) -> str | None:
    token = _find_stop_token(result, RESTARTABLE_ATTEMPT_STOP_TOKENS)
    if token is None:
        return None
    if (
        token == "VISUAL_REGION_INDEX_NOT_FOUND"
        and isinstance(result, dict)
        and result.get("route_visual_region_index_pending") is not None
    ):
        return None
    return f"{token.lower()}_attempt_restart"


def _restartable_preflight_failure(result: dict[str, Any] | None) -> str | None:
    if not isinstance(result, dict):
        return None
    issues = result.get("issues") or []
    if not isinstance(issues, list):
        return None
    normalized = " ".join(str(issue).lower() for issue in issues)
    if "persistent post-enemy block is active" in normalized:
        return "persistent_post_enemy_block_attempt_restart"
    return None


def _find_stop_token(value: Any, tokens: tuple[str, ...]) -> str | None:
    if isinstance(value, dict):
        status_reason = f"{value.get('status') or ''} {value.get('reason') or ''}".upper()
        for token in tokens:
            if token in status_reason:
                return token
        for nested in value.values():
            found = _find_stop_token(nested, tokens)
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for nested in value:
            found = _find_stop_token(nested, tokens)
            if found is not None:
                return found
    return None


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
    if result.get("pause_verified") or result.get("timer_stop_verified"):
        return True
    last_poll = result.get("last_poll")
    if isinstance(last_poll, dict) and _safe_to_think(last_poll):
        return True
    visible = result.get("visible_ui") or result.get("pause_verify")
    if isinstance(visible, dict) and visible.get("visible_ui") == "pause_menu":
        return True
    for key in ("guard", "pause_guard", "resume_guard"):
        guard = result.get(key)
        if isinstance(guard, dict):
            if guard.get("pause_verified") or guard.get("timer_stop_verified"):
                return True
            visible = guard.get("visible_ui") or guard.get("pause_verify")
            if isinstance(visible, dict) and visible.get("visible_ui") == "pause_menu":
                return True
    ensure_pause = result.get("ensure_pause")
    if isinstance(ensure_pause, dict) and _safe_to_think(ensure_pause):
        return True
    if result.get("status") in {"PARKED_SAFE", "SUCCESS"}:
        return True
    return False


def _safe_to_finalize(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("status") == "SUCCESS":
        return True
    if _visible_ui_name(result) == "new_game_setup":
        return True
    if result.get("pause_verified") or result.get("timer_stop_verified"):
        return True
    last_poll = result.get("last_poll")
    if isinstance(last_poll, dict) and _safe_to_finalize(last_poll):
        return True
    visible = result.get("visible_ui") or result.get("pause_verify")
    if isinstance(visible, dict) and visible.get("visible_ui") == "pause_menu":
        return True
    for key in ("ensure_pause", "guard", "pause_guard", "resume_guard"):
        nested = result.get(key)
        if isinstance(nested, dict) and _safe_to_finalize(nested):
            return True
    return False


def _visible_ui_name(result: dict[str, Any] | None) -> str | None:
    if not isinstance(result, dict):
        return None
    visible = result.get("visible_ui")
    if isinstance(visible, str) and visible:
        return visible
    if isinstance(visible, dict) and visible.get("visible_ui"):
        return str(visible["visible_ui"])
    last_poll = result.get("last_poll")
    if isinstance(last_poll, dict):
        nested = _visible_ui_name(last_poll)
        if nested:
            return nested
    for key in ("guard", "pause_guard", "resume_guard", "ensure_pause"):
        nested_result = result.get(key)
        if isinstance(nested_result, dict):
            nested = _visible_ui_name(nested_result)
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


def _restart_dead_timeline(commands: Any, previous_result: dict[str, Any]) -> dict[str, Any]:
    """Abandon a dead Lightning timeline and verify the setup screen."""
    steps: list[dict[str, Any]] = []
    needs_abandon_clicks = True

    def ui(control: str) -> dict[str, Any]:
        result = commands.cmd_lightning_ui(control)
        steps.append({"control": control, "result": _compact(result)})
        return result

    previous_visible = _visible_ui_name(previous_result)
    if previous_visible == "new_game_setup" and not _active_mission_clue(previous_result):
        return {
            "status": "OK",
            "reason": "already_at_setup",
            "steps": steps,
        }

    if not _pause_menu_proven(previous_result):
        if not _safe_to_think(previous_result):
            pause_guard = getattr(commands, "cmd_lightning_pause_guard", None)
            if callable(pause_guard):
                pause = pause_guard(seconds=5.0, interval=0.25, once=True)
                steps.append({"control": "pause_guard", "result": _compact(pause)})
            else:
                pause = ui("ensure_pause")
        else:
            pause = ui("ensure_pause")
        pause_visible = _visible_ui_name(pause)
        if pause_visible == "new_game_setup":
            if _active_mission_clue(previous_result) or _active_mission_clue(pause):
                return {
                    "status": "BLOCKED",
                    "reason": "restart_setup_visibility_conflicts_with_active_mission",
                    "steps": steps,
                }
            return {
                "status": "OK",
                "reason": "already_at_setup",
                "steps": steps,
            }
        if pause_visible != "pause_menu" and not _pause_menu_proven(pause):
            if _restart_recovery_panel_safe(pause):
                needs_abandon_clicks = False
            else:
                return {
                    "status": "BLOCKED_UNPAUSED_CLOCK_TICKING",
                    "reason": "restart_pause_not_verified",
                    "steps": steps,
                }

    if needs_abandon_clicks:
        for control in ("abandon_timeline", "abandon_confirm_yes"):
            result = ui(control)
            if result.get("status") != "OK":
                return {
                    "status": "BLOCKED",
                    "reason": f"{control}_failed",
                    "steps": steps,
                }
        result = ui("abandon_pilot_available")
        if result.get("status") != "OK":
            return {
                "status": "BLOCKED",
                "reason": "abandon_pilot_available_failed",
                "steps": steps,
            }
        for control in (
            "abandon_pilot_slot_two_left",
            "abandon_pilot_slot_two_right",
            "abandon_pilot_slot",
            "abandon_pilot_slot_wide",
            "abandon_pilot_slot_right",
        ):
            result = ui(control)
            if result.get("status") != "OK":
                return {
                    "status": "BLOCKED",
                    "reason": f"{control}_failed",
                    "steps": steps,
                }
            visible = ui("classify")
            if _visible_ui_name(visible) == "new_game_setup":
                return {
                    "status": "OK",
                    "reason": "abandoned_to_setup",
                    "steps": steps,
                }
            recovery_control = _restart_recovery_control(visible)
            if recovery_control:
                cleared = ui(recovery_control)
                if cleared.get("status") != "OK":
                    return {
                        "status": "BLOCKED",
                        "reason": f"{recovery_control}_failed",
                        "steps": steps,
                    }
                visible = ui("classify")
                if _visible_ui_name(visible) == "new_game_setup":
                    return {
                        "status": "OK",
                        "reason": "abandoned_to_setup_after_panel",
                        "steps": steps,
                    }

    for _ in range(4):
        visible = ui("classify")
        if _visible_ui_name(visible) == "new_game_setup":
            return {
                "status": "OK",
                "reason": "abandoned_to_setup",
                "steps": steps,
            }
        recovery_control = _restart_recovery_control(visible)
        if recovery_control:
            cleared = ui(recovery_control)
            if cleared.get("status") != "OK":
                return {
                    "status": "BLOCKED",
                    "reason": f"{recovery_control}_failed",
                    "steps": steps,
                }
            continue
        handled = ui("handle_screen")
        if _visible_ui_name(handled) == "new_game_setup":
            return {
                "status": "OK",
                "reason": "abandoned_to_setup_after_panel",
                "steps": steps,
            }

    return {
        "status": "BLOCKED",
        "reason": "abandon_final_state_unverified",
        "steps": steps,
    }


def _restart_recovery_panel_safe(result: dict[str, Any]) -> bool:
    if _visible_ui_name(result) != "kia_panel":
        return False
    return _recommended_control_name(result) in RESTART_RECOVERY_SAFE_CONTROLS


def _restart_recovery_control(result: dict[str, Any]) -> str | None:
    if _visible_ui_name(result) == "kia_panel":
        return "abandon_pilot_slot"
    recommended = _recommended_control_name(result)
    if recommended in RESTART_RECOVERY_SAFE_CONTROLS:
        return recommended
    return None


def _pause_menu_proven(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("pause_verified") or result.get("timer_stop_verified"):
        return True
    visible = result.get("visible_ui") or result.get("pause_verify")
    if isinstance(visible, dict) and visible.get("visible_ui") == "pause_menu":
        return True
    if visible == "pause_menu":
        return True
    for key in ("last_poll", "pause_guard", "ensure_pause"):
        nested = result.get(key)
        if isinstance(nested, dict) and _pause_menu_proven(nested):
            return True
    return False


def _active_mission_clue(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("in_active_mission") is True:
            return True
        try:
            deployment_zones = int(value.get("deployment_zone_count") or 0)
        except (TypeError, ValueError):
            deployment_zones = 0
        if deployment_zones > 0 and value.get("mission_id"):
            return True
        for nested in value.values():
            if _active_mission_clue(nested):
                return True
        return False
    if isinstance(value, list):
        return any(_active_mission_clue(nested) for nested in value)
    return False


def _recommended_control_name(result: dict[str, Any] | None) -> str | None:
    if not isinstance(result, dict):
        return None
    direct = result.get("recommended_control")
    if isinstance(direct, str) and direct:
        return direct
    visible = result.get("visible_ui") or result.get("pause_verify")
    if isinstance(visible, dict):
        nested = visible.get("recommended_control")
        if isinstance(nested, str) and nested:
            return nested
    last_poll = result.get("last_poll")
    if isinstance(last_poll, dict):
        nested = _recommended_control_name(last_poll)
        if nested:
            return nested
    return None


def cmd_lightning_autonomous(**kwargs: Any) -> dict[str, Any]:
    """CLI entry point for the telemetry-backed autonomous conductor."""
    from src.loop import commands

    max_attempts = max(1, int(kwargs.get("max_attempts") or 1))
    run_kwargs = dict(kwargs)
    run_kwargs["max_attempts"] = 1
    history: list[dict[str, Any]] = []

    for attempt_index in range(1, max_attempts + 1):
        config = AutonomousLightningConfig(**run_kwargs)
        conductor = AutonomousLightningConductor(config)
        result = conductor.run()
        result["timeline_attempt_index"] = attempt_index
        history.append(_compact(result))

        if result.get("status") != "RESTART_RECOMMENDED":
            if history:
                result["timeline_attempt_history"] = history
            commands._print_result(result)
            return result
        if attempt_index >= max_attempts:
            result["timeline_attempt_history"] = history
            commands._print_result(result)
            return result

        recovery = _restart_dead_timeline(commands, result)
        history[-1]["restart_recovery"] = _compact(recovery)
        if recovery.get("status") != "OK":
            blocked = {
                "status": "BLOCKED",
                "reason": "restart_recovery_failed",
                "last_result": _compact(result),
                "restart_recovery": recovery,
                "timeline_attempt_history": history,
            }
            commands._print_result(blocked)
            return blocked

    result = {
        "status": "BLOCKED",
        "reason": "autonomous_attempt_loop_exhausted",
        "timeline_attempt_history": history,
    }
    commands._print_result(result)
    return result
