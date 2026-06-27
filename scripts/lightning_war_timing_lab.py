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
from src.control.mac_click import list_known_window_controls

from scripts import lightning_war_fast_walkthrough as fast
from scripts import itb_timer_memory_probe as memory_probe


PROFILE_PATH = ROOT / "data" / "lightning_war_timing_profile.json"
NOTEBOOK_PATH = ROOT / "docs" / "agent" / "lightning-war-timing-profile.md"
REPORT_DIR = ROOT / "run_notes" / "lightning_ui_timing_loop"
LIGHTNING_TIMER_LIMIT_SECONDS = 30 * 60
TRUSTED_MEMORY_CLOCK_SOURCES = {
    "memory_live_numeric_candidate",
}
DEFAULT_SPEED_EXPECTED_PLAYER_TURNS = 3
DEFAULT_SPEED_FINAL_TURN_VISIBLE_POLL_SECONDS = 0.2
LIGHTNING_WAR_ACHIEVEMENT = "Lightning War"
LIGHTNING_WAR_SQUAD = "Blitzkrieg"
LIGHTNING_WAR_TIMING_TAGS = ["achievement", "lightning_war_timing_lab"]


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


def _stamp_lightning_war_timing_session(path: Path | None = None) -> dict[str, Any]:
    """Align live solver policy with the timing lab's UI-selected run."""
    from src.loop.session import RunSession

    session = RunSession.new_run(
        LIGHTNING_WAR_SQUAD,
        [LIGHTNING_WAR_ACHIEVEMENT],
        difficulty=0,
        tags=list(LIGHTNING_WAR_TIMING_TAGS),
    )
    if path is None:
        session.save()
    else:
        session.save(path)
    return {
        "status": "OK",
        "run_id": session.run_id,
        "squad": session.squad,
        "achievement_targets": list(session.achievement_targets),
        "difficulty": session.difficulty,
        "tags": list(session.tags),
        "path": str(path) if path is not None else "default",
    }


def _repo_relative_text(value: Any) -> Any:
    if not value:
        return value
    path = Path(str(value))
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(value)


def _mission_timer_sample(
    mission_timers: dict[str, Any],
    key: str,
) -> dict[str, Any] | None:
    value = mission_timers.get(key)
    return value if isinstance(value, dict) else None


def _mission_status(
    *,
    red_detection: dict[str, Any] | None,
    mission_preview: dict[str, Any] | None,
    start_mission: dict[str, Any] | None,
    deployment_result: dict[str, Any] | None,
    confirm_result: dict[str, Any] | None,
    combat_region_result: dict[str, Any] | None,
) -> str:
    if not isinstance(red_detection, dict) or red_detection.get("status") != "PASS":
        return "FAIL"
    if not isinstance(mission_preview, dict) or mission_preview.get("status") != "OK":
        return "FAIL"
    if not isinstance(start_mission, dict) or start_mission.get("status") != "PASS":
        return "FAIL"
    if not isinstance(deployment_result, dict) or deployment_result.get("status") != "PASS":
        return "FAIL"
    if not isinstance(confirm_result, dict) or confirm_result.get("status") != "PASS":
        return "FAIL"
    if not isinstance(combat_region_result, dict) or combat_region_result.get("status") != "PASS":
        return "FAIL"
    return "PASS"


def _seconds_text(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{value}s"


def _timer_game_seconds(timer: Any) -> float | None:
    if not isinstance(timer, dict):
        return None
    value = timer.get("game_seconds")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timer_game_text(timer: Any) -> str | None:
    if not isinstance(timer, dict):
        return None
    text = timer.get("game_timer")
    return str(text) if text else None


def _sample_timer(sample: Any, key: str = "bridge_timer") -> dict[str, Any]:
    if not isinstance(sample, dict):
        return {}
    timer = sample.get(key)
    return timer if isinstance(timer, dict) else {}


def _delta_seconds(start: Any, end: Any) -> float | None:
    start_seconds = _timer_game_seconds(start)
    end_seconds = _timer_game_seconds(end)
    if start_seconds is None or end_seconds is None:
        return None
    return round(end_seconds - start_seconds, 3)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def _format_sequence_token(phase: str, index: int | None = None) -> str:
    if phase == "opening_enemy":
        return "enemy(opening)"
    if phase == "player":
        return f"us{index}" if index is not None else "us"
    if phase == "enemy":
        return f"enemy{index}" if index is not None else "enemy"
    if phase == "terminal_enemy":
        return f"enemy{index}->done" if index is not None else "enemy->done"
    return phase


def expected_speed_sequence_text(player_turns: int) -> str:
    tokens = [_format_sequence_token("opening_enemy")]
    for index in range(1, max(1, int(player_turns)) + 1):
        tokens.append(_format_sequence_token("player", index))
        if index == player_turns:
            tokens.append(_format_sequence_token("terminal_enemy", index))
        else:
            tokens.append(_format_sequence_token("enemy", index))
    return " -> ".join(tokens)


def evaluate_speed_sequence_expectation(
    audit: dict[str, Any],
    *,
    expected_player_turns: int | None,
) -> dict[str, Any]:
    if expected_player_turns is None or expected_player_turns <= 0:
        return {
            "status": "DISABLED",
            "reason": "no_expected_player_turn_count",
        }
    expected_sequence = expected_speed_sequence_text(expected_player_turns)
    observed_sequence = audit.get("sequence_text")
    status = "MATCH" if observed_sequence == expected_sequence else "MISMATCH"
    return {
        "status": status,
        "expected_player_turn_count": expected_player_turns,
        "expected_enemy_phase_count": expected_player_turns + 1,
        "expected_sequence": expected_sequence,
        "observed_player_turn_count": audit.get("player_turn_count"),
        "observed_enemy_phase_count": audit.get("enemy_phase_count"),
        "observed_sequence": observed_sequence,
        "speed_assumption": (
            "short_route_terminal_after_expected_final_player_turn"
        ),
        "fallback": (
            "continue_dynamic_loop_if_expected_terminal_turn_returns_player_ready"
        ),
    }


def build_turn_timing_audit(report: dict[str, Any]) -> dict[str, Any]:
    """Summarize bridge/UI turn boundaries on the in-game timer."""
    in_game_timers = report.get("in_game_timers") or {}
    confirm = report.get("deploy_confirm") or {}
    region_loop = report.get("combat_until_region_secured") or {}
    turns = region_loop.get("turns") or []

    phases: list[dict[str, Any]] = []
    sequence_tokens: list[str] = []

    confirm_click_timer = (
        in_game_timers.get("deploy_confirm_click_before")
        or confirm.get("before_in_game_timer")
        or {}
    )
    opening_ready_sample = confirm.get("first_player_ready_bridge") or {}
    opening_ready_timer = (
        _sample_timer(opening_ready_sample)
        or in_game_timers.get("opening_player_turn_bridge_ready")
        or {}
    )
    opening_ready_frame_timer = (
        _sample_timer(
            confirm.get("first_player_ready_frame_after_bridge"),
            "frame_timer",
        )
        or in_game_timers.get("opening_player_turn_first_frame_after_bridge")
        or {}
    )
    if confirm_click_timer or opening_ready_timer:
        phases.append(
            {
                "phase": "opening_enemy",
                "start_event": "deploy_confirm_click",
                "end_event": "opening_player_turn_bridge_ready",
                "start_game_timer": _timer_game_text(confirm_click_timer),
                "end_game_timer": _timer_game_text(opening_ready_timer),
                "duration_game_seconds": _delta_seconds(
                    confirm_click_timer,
                    opening_ready_timer,
                ),
                "bridge_to_first_frame_seconds": _delta_seconds(
                    opening_ready_timer,
                    opening_ready_frame_timer,
                ),
                "bridge_elapsed_wall_seconds": opening_ready_sample.get(
                    "elapsed_after_confirm_seconds"
                )
                if isinstance(opening_ready_sample, dict)
                else None,
            }
        )
        sequence_tokens.append(_format_sequence_token("opening_enemy"))

    post_end_to_player: list[float] = []
    enemy_animation: list[float] = []
    end_to_enemy: list[float] = []
    end_to_enemy_visual: list[float] = []
    ready_frame_lags: list[float] = []
    ready_pause_lags: list[float] = []
    player_turns = 0
    enemy_phases_after_player = 0
    terminal_phase: dict[str, Any] | None = None

    for fallback_index, turn in enumerate(turns, start=1):
        if not isinstance(turn, dict):
            continue
        index = int(turn.get("loop_turn_index") or fallback_index)
        player_turns += 1
        turn_start_timer = turn.get("before_in_game_timer") or {}
        auto_done_timer = turn.get("auto_turn_done_timer") or {}
        end_turn_timer = turn.get("end_turn_before_in_game_timer") or {}
        phases.append(
            {
                "phase": "player",
                "index": index,
                "start_game_timer": _timer_game_text(turn_start_timer),
                "auto_turn_done_game_timer": _timer_game_text(auto_done_timer),
                "end_turn_click_game_timer": _timer_game_text(end_turn_timer),
                "start_to_end_turn_game_seconds": _delta_seconds(
                    turn_start_timer,
                    end_turn_timer,
                ),
                "auto_turn_duration_wall_seconds": turn.get(
                    "auto_turn_duration_seconds"
                ),
                "actions_completed": (
                    (turn.get("auto_turn_summary") or {}).get("actions_completed")
                ),
                "boundary": turn.get("boundary"),
            }
        )
        sequence_tokens.append(_format_sequence_token("player", index))

        left_sample = turn.get("first_non_player_bridge") or {}
        visual_left_sample = turn.get("first_non_player_visual") or {}
        ready_sample = turn.get("first_player_ready_bridge") or {}
        terminal_visible = turn.get("first_region_secured_visible") or {}
        left_timer = _sample_timer(left_sample)
        visual_left_timer = _sample_timer(visual_left_sample, "frame_timer")
        ready_timer = _sample_timer(ready_sample)
        terminal_timer = _sample_timer(terminal_visible, "visible_timer")
        ready_frame_timer = _sample_timer(
            turn.get("first_player_ready_frame_after_bridge"),
            "frame_timer",
        )
        after_pause_timer = turn.get("after_pause_timer") or {}

        if ready_timer:
            enemy_phases_after_player += 1
            end_to_enemy_delta = _delta_seconds(end_turn_timer, left_timer)
            end_to_enemy_visual_delta = _delta_seconds(
                end_turn_timer,
                visual_left_timer,
            )
            enemy_animation_delta = _delta_seconds(left_timer, ready_timer)
            post_end_delta = _delta_seconds(end_turn_timer, ready_timer)
            frame_lag = _delta_seconds(ready_timer, ready_frame_timer)
            pause_lag = _delta_seconds(ready_timer, after_pause_timer)
            for collection, value in (
                (end_to_enemy, end_to_enemy_delta),
                (end_to_enemy_visual, end_to_enemy_visual_delta),
                (enemy_animation, enemy_animation_delta),
                (post_end_to_player, post_end_delta),
                (ready_frame_lags, frame_lag),
                (ready_pause_lags, pause_lag),
            ):
                if value is not None:
                    collection.append(value)
            phases.append(
                {
                    "phase": "enemy",
                    "after_player_turn_index": index,
                    "end_turn_click_game_timer": _timer_game_text(end_turn_timer),
                    "left_player_bridge_game_timer": _timer_game_text(left_timer),
                    "left_player_visual_game_timer": _timer_game_text(
                        visual_left_timer
                    ),
                    "next_player_ready_game_timer": _timer_game_text(ready_timer),
                    "end_turn_to_left_player_seconds": end_to_enemy_delta,
                    "end_turn_to_left_player_visual_seconds": (
                        end_to_enemy_visual_delta
                    ),
                    "left_player_to_next_player_seconds": enemy_animation_delta,
                    "end_turn_to_next_player_seconds": post_end_delta,
                    "ready_bridge_to_first_frame_seconds": frame_lag,
                    "ready_bridge_to_pause_seconds": pause_lag,
                    "bridge_turn": (ready_sample.get("snapshot") or {}).get("turn")
                    if isinstance(ready_sample, dict)
                    else None,
                }
            )
            sequence_tokens.append(_format_sequence_token("enemy", index))
            continue

        if terminal_timer:
            enemy_phases_after_player += 1
            terminal_delta = _delta_seconds(end_turn_timer, terminal_timer)
            terminal_visual_left_delta = _delta_seconds(
                end_turn_timer,
                visual_left_timer,
            )
            terminal_phase = {
                "phase": "terminal_enemy",
                "after_player_turn_index": index,
                "end_turn_click_game_timer": _timer_game_text(end_turn_timer),
                "left_player_visual_game_timer": _timer_game_text(
                    visual_left_timer
                ),
                "region_secured_visible_game_timer": _timer_game_text(
                    terminal_timer
                ),
                "end_turn_to_left_player_visual_seconds": (
                    terminal_visual_left_delta
                ),
                "end_turn_to_region_secured_visible_seconds": terminal_delta,
                "visible_elapsed_after_end_turn_wall_seconds": terminal_visible.get(
                    "elapsed_after_end_turn_seconds"
                )
                if isinstance(terminal_visible, dict)
                else None,
            }
            phases.append(terminal_phase)
            sequence_tokens.append(_format_sequence_token("terminal_enemy", index))

    return {
        "status": "OK" if phases else "NO_DATA",
        "player_turn_count": player_turns,
        "enemy_phase_count": (
            (1 if opening_ready_timer else 0) + enemy_phases_after_player
        ),
        "enemy_phase_count_after_players": enemy_phases_after_player,
        "sequence": sequence_tokens,
        "sequence_text": " -> ".join(sequence_tokens),
        "phases": phases,
        "post_end_turn_to_next_player_seconds": {
            "values": post_end_to_player,
            "average": _mean(post_end_to_player),
            "max": max(post_end_to_player) if post_end_to_player else None,
        },
        "end_turn_to_enemy_bridge_seconds": {
            "values": end_to_enemy,
            "average": _mean(end_to_enemy),
            "max": max(end_to_enemy) if end_to_enemy else None,
        },
        "end_turn_to_enemy_visual_seconds": {
            "values": end_to_enemy_visual,
            "average": _mean(end_to_enemy_visual),
            "max": max(end_to_enemy_visual) if end_to_enemy_visual else None,
        },
        "enemy_bridge_to_next_player_seconds": {
            "values": enemy_animation,
            "average": _mean(enemy_animation),
            "max": max(enemy_animation) if enemy_animation else None,
        },
        "ready_bridge_to_first_frame_seconds": {
            "values": ready_frame_lags,
            "average": _mean(ready_frame_lags),
            "max": max(ready_frame_lags) if ready_frame_lags else None,
        },
        "ready_bridge_to_pause_seconds": {
            "values": ready_pause_lags,
            "average": _mean(ready_pause_lags),
            "max": max(ready_pause_lags) if ready_pause_lags else None,
        },
        "terminal_phase": terminal_phase,
    }


def _parse_optional_timer_address(value: str | None) -> int | None:
    if not value:
        return None
    return int(str(value), 0)


def _resolve_live_timer_from_proof(
    proof_path: str | None,
    *,
    proof_selection: str = "explicit",
    pause_stability_seconds: float = 0.0,
) -> tuple[int | None, str | None, dict[str, Any] | None]:
    if not proof_path:
        return None, None, None
    path = Path(proof_path)
    proof = json.loads(path.read_text(encoding="utf-8"))
    validation = memory_probe.validate_session_clock_proof(
        proof,
        pause_stability_seconds=pause_stability_seconds,
    )
    validation["proof_path"] = str(path)
    if validation.get("status") != "OK":
        raise RuntimeError(
            "memory live timer proof invalid: "
            f"{validation.get('reason') or validation.get('status')}"
        )
    validation["proof_selection"] = proof_selection
    address = validation.get("address")
    kind = validation.get("kind")
    if not address or not kind:
        raise RuntimeError("memory live timer proof missing address/kind")
    return int(str(address), 16), str(kind), validation


def _default_memory_live_timer_proof_path() -> Path:
    return ROOT / memory_probe.DEFAULT_SESSION_CLOCK_PROOF_PATH


def _selected_memory_live_timer_proof_path(
    args: argparse.Namespace,
) -> tuple[str | None, str | None]:
    explicit = getattr(args, "memory_live_timer_proof", None)
    if explicit:
        return str(explicit), "explicit"
    if not getattr(args, "auto_memory_live_timer_proof", True):
        return None, None
    default_path = _default_memory_live_timer_proof_path()
    if default_path.exists():
        return str(default_path), "auto_default"
    return None, None


def _resolve_live_timer_config(
    args: argparse.Namespace,
    *,
    pause_stability_seconds: float = 0.0,
) -> tuple[int | None, str | None, dict[str, Any] | None]:
    proof_path, proof_selection = _selected_memory_live_timer_proof_path(args)
    if (
        proof_path is None
        and getattr(args, "require_memory_live_timer_proof", False)
    ):
        raise RuntimeError(
            "memory live timer proof required but missing; create "
            f"{_default_memory_live_timer_proof_path()} with "
            "`python scripts/itb_timer_memory_probe.py session-clock-proof "
            "--score <score.json> --output recordings/lightning_session_clock_proof.json`"
        )
    proof_address, proof_kind, proof_validation = _resolve_live_timer_from_proof(
        proof_path,
        proof_selection=proof_selection or "explicit",
        pause_stability_seconds=pause_stability_seconds,
    )
    if proof_address is not None:
        raw_address = _parse_optional_timer_address(args.memory_live_timer_address)
        if raw_address is not None and raw_address != proof_address:
            raise RuntimeError(
                "memory live timer proof address conflicts with "
                "--memory-live-timer-address"
            )
        return proof_address, proof_kind, proof_validation
    return (
        _parse_optional_timer_address(args.memory_live_timer_address),
        args.memory_live_timer_kind,
        None,
    )


def _read_memory_in_game_timer(
    *,
    label: str,
    timer_address: int | None = None,
    live_timer_address: int | None = None,
    live_timer_kind: str | None = None,
) -> dict[str, Any]:
    if os.name != "nt" and sys.platform != "darwin":
        return {
            "status": "UNAVAILABLE",
            "reason": f"memory timer probe is unsupported on {sys.platform}",
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
        with memory_probe.open_process_reader(pid) as reader:
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
        self.reader: Any | None = None

    def __call__(self) -> dict[str, Any]:
        if os.name != "nt" and sys.platform != "darwin":
            return {
                "status": "UNAVAILABLE",
                "reason": f"memory timer probe is unsupported on {sys.platform}",
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

    def _reader(self) -> Any | None:
        if self.reader is not None:
            return self.reader
        pid = memory_probe._find_breach_pid()
        if pid is None:
            self.close()
            self.pid = None
            return None
        self.pid = pid
        self.reader = memory_probe.open_process_reader(pid)
        return self.reader


class LiveNumericFrameClockSampler:
    def __init__(self, timer_address: int, timer_kind: str) -> None:
        self.timer_address = timer_address
        self.timer_kind = timer_kind
        self.pid: int | None = None
        self.reader: Any | None = None

    def __call__(self) -> dict[str, Any]:
        if os.name != "nt" and sys.platform != "darwin":
            return {
                "status": "UNAVAILABLE",
                "reason": f"memory timer probe is unsupported on {sys.platform}",
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

    def _reader(self) -> Any | None:
        if self.reader is not None:
            return self.reader
        pid = memory_probe._find_breach_pid()
        if pid is None:
            self.close()
            self.pid = None
            return None
        self.pid = pid
        self.reader = memory_probe.open_process_reader(pid)
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
    threshold = 4500
    return {
        "status": "OK",
        "yellow": yellow,
        "pixels": pixels,
        "threshold": threshold,
        "deployment_visible": yellow >= threshold,
        "crop": list(crop),
    }


def _post_end_turn_transition_banner_from_frame(frame: dict[str, Any]) -> dict[str, Any]:
    """Detect the central ENEMY/PLAYER TURN transition banner without OCR."""
    path = frame.get("screenshot_path")
    if not path:
        return {
            "status": "UNKNOWN",
            "reason": "screenshot_path_missing",
            "transition_visible": False,
        }
    try:
        from PIL import Image

        with Image.open(path) as image:
            image = image.convert("RGB")
            width, height = image.size
            text_crop = (
                int(width * 0.42),
                int(height * 0.48),
                int(width * 0.58),
                int(height * 0.535),
            )
            band_crop = (
                0,
                int(height * 0.47),
                width,
                int(height * 0.56),
            )
            text_region = image.crop(text_crop)
            band_region = image.crop(band_crop)
            text_pixels = list(text_region.getdata())
            band_pixels = list(band_region.getdata())
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": str(exc),
            "transition_visible": False,
        }

    def fraction(count: int, total: int) -> float:
        return round(count / total, 4) if total else 0.0

    text_total = len(text_pixels)
    band_total = len(band_pixels)
    text_bright = sum(
        1 for red, green, blue in text_pixels
        if red >= 180 and green >= 180 and blue >= 180
    )
    text_dark = sum(
        1 for red, green, blue in text_pixels
        if red <= 35 and green <= 45 and blue <= 60
    )
    band_dark = sum(
        1 for red, green, blue in band_pixels
        if red <= 35 and green <= 45 and blue <= 60
    )
    text_bright_fraction = fraction(text_bright, text_total)
    text_dark_fraction = fraction(text_dark, text_total)
    band_dark_fraction = fraction(band_dark, band_total)
    transition_visible = (
        text_bright_fraction >= 0.06
        and text_dark_fraction >= 0.45
        and band_dark_fraction >= 0.55
    )
    return {
        "status": "OK",
        "transition_visible": transition_visible,
        "text_bright_fraction": text_bright_fraction,
        "text_dark_fraction": text_dark_fraction,
        "band_dark_fraction": band_dark_fraction,
        "text_crop": list(text_crop),
        "band_crop": list(band_crop),
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
    combat = report.get("combat_turn") or {}
    combat_auto_done_timer = in_game_timers.get("combat_auto_turn_done") or {}
    combat_end_click_timer = in_game_timers.get("combat_end_turn_click_before") or {}
    combat_left_player_timer = (
        in_game_timers.get("combat_end_turn_bridge_left_player") or {}
    )
    combat_ready_timer = in_game_timers.get("combat_post_end_turn_player_ready") or {}
    combat_ready_frame_timer = (
        in_game_timers.get("combat_post_end_turn_first_frame_after_bridge") or {}
    )
    region_loop = report.get("combat_until_region_secured") or {}
    region_visible_timer = in_game_timers.get("region_secured_visible") or {}
    region_hover_timer = (
        in_game_timers.get("region_secured_continue_hover_frame") or {}
    )
    region_click_before_timer = (
        in_game_timers.get("region_secured_continue_click_before") or {}
    )
    region_click_after_timer = (
        in_game_timers.get("region_secured_continue_click_after") or {}
    )
    timing_audit = report.get("turn_timing_audit") or {}
    speed_expectation = report.get("speed_sequence_expectation") or {}
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
    if combat:
        combat_summary = combat.get("auto_turn_summary") or {}
        safety_stop = combat.get("safety_stop_reason")
        if isinstance(safety_stop, dict):
            safety_stop_text = (
                safety_stop.get("signature")
                or safety_stop.get("reason")
                or json.dumps(safety_stop, sort_keys=True)
            )
        else:
            safety_stop_text = safety_stop
        lines.extend(
            [
                f"- Combat solver/action signal: {combat.get('solver_action_signal_source') or 'n/a'}",
                f"- Combat auto_turn status: {combat_summary.get('status') or 'n/a'}",
                f"- Combat actions completed: {combat_summary.get('actions_completed')}",
                f"- Combat safety stop: {safety_stop_text or 'n/a'}",
                f"- Combat fuzzy block speedrun skip: {'yes' if combat.get('auto_turn_block_skipped') else 'no'}",
                f"- Combat End Turn signal: {combat.get('end_turn_signal_source') or 'n/a'}",
                f"- Combat auto_turn duration: {_seconds_text(combat.get('auto_turn_duration_seconds'))}",
                f"- Combat auto_turn done timer: {combat_auto_done_timer.get('game_timer') or 'n/a'}",
                f"- Combat End Turn click timer: {combat_end_click_timer.get('game_timer') or 'n/a'}",
                f"- Combat bridge left player timer: {combat_left_player_timer.get('game_timer') or 'n/a'}",
                f"- Combat next player-turn bridge timer: {combat_ready_timer.get('game_timer') or 'n/a'}",
                f"- Combat first frame after bridge-ready timer: {combat_ready_frame_timer.get('game_timer') or 'n/a'}",
                f"- Combat post-End-Turn observed seconds: {_seconds_text(combat.get('observed_seconds'))}",
            ]
        )
    if region_loop:
        region = region_loop.get("region_secured") or {}
        hover = region_loop.get("continue_hover") or {}
        hover_control = hover.get("control") or {}
        hover_result = hover.get("hover") or {}
        click = region_loop.get("continue_click") or {}
        click_control = click.get("control") or {}
        click_result = click.get("click") or {}
        post_continue = click.get("post_continue_observe") or {}
        post_continue_next = (
            post_continue.get("first_non_region_visible")
            or post_continue.get("first_visible_sample")
            or {}
        )
        post_continue_visible = post_continue_next.get("visible_ui") or {}
        post_continue_timer = post_continue_next.get("visible_timer") or {}
        last_turn = region_loop.get("last_end_turn") or {}
        lines.extend(
            [
                f"- Region Secured loop status: {region_loop.get('status') or 'n/a'}",
                f"- Region Secured turns attempted: {region_loop.get('turns_attempted')}",
                f"- Last End Turn click timer: {((last_turn.get('end_turn_before_in_game_timer') or {}).get('game_timer')) or 'n/a'}",
                f"- Region Secured visible timer: {region_visible_timer.get('game_timer') or 'n/a'}",
                f"- Region Secured visible elapsed after End Turn: {_seconds_text(region.get('elapsed_after_end_turn_seconds'))}",
                f"- Continue hover control: {hover_control.get('name') or 'reward_continue'} @ ({hover_control.get('window_x')}, {hover_control.get('window_y')})",
                f"- Continue hover result: {hover_result.get('status') or 'n/a'} screen=({hover_result.get('screen_x')}, {hover_result.get('screen_y')})",
                f"- Continue hover frame timer: {region_hover_timer.get('game_timer') or 'n/a'}",
                f"- Continue click control: {click_control.get('name') or 'reward_continue'} @ ({click_control.get('window_x')}, {click_control.get('window_y')})",
                f"- Continue click result: {click_result.get('status') or 'n/a'}",
                f"- Continue click before timer: {region_click_before_timer.get('game_timer') or 'n/a'}",
                f"- Continue click after frame timer: {region_click_after_timer.get('game_timer') or 'n/a'}",
                f"- Post-Continue observed seconds: {_seconds_text(post_continue.get('observed_seconds'))}",
                f"- Post-Continue next visible UI: {post_continue_visible.get('visible_ui') or 'n/a'}",
                f"- Post-Continue next visible timer: {post_continue_timer.get('game_timer') or 'n/a'}",
            ]
        )
    if timing_audit:
        post_end = timing_audit.get("post_end_turn_to_next_player_seconds") or {}
        end_to_enemy = timing_audit.get("end_turn_to_enemy_bridge_seconds") or {}
        enemy_to_player = timing_audit.get("enemy_bridge_to_next_player_seconds") or {}
        ready_frame = timing_audit.get("ready_bridge_to_first_frame_seconds") or {}
        ready_pause = timing_audit.get("ready_bridge_to_pause_seconds") or {}
        terminal = timing_audit.get("terminal_phase") or {}
        lines.extend(
            [
                f"- Turn sequence: {timing_audit.get('sequence_text') or 'n/a'}",
                f"- Player turns observed: {timing_audit.get('player_turn_count')}",
                f"- Enemy phases observed: {timing_audit.get('enemy_phase_count')}",
                f"- End Turn -> enemy bridge avg/max: {_seconds_text(end_to_enemy.get('average'))} / {_seconds_text(end_to_enemy.get('max'))}",
                f"- Enemy bridge -> next player avg/max: {_seconds_text(enemy_to_player.get('average'))} / {_seconds_text(enemy_to_player.get('max'))}",
                f"- End Turn -> next player avg/max: {_seconds_text(post_end.get('average'))} / {_seconds_text(post_end.get('max'))}",
                f"- Ready bridge -> first audit frame avg/max: {_seconds_text(ready_frame.get('average'))} / {_seconds_text(ready_frame.get('max'))}",
                f"- Ready bridge -> pause avg/max: {_seconds_text(ready_pause.get('average'))} / {_seconds_text(ready_pause.get('max'))}",
                f"- Terminal End Turn -> Region Secured: {_seconds_text(terminal.get('end_turn_to_region_secured_visible_seconds'))}",
            ]
        )
    if speed_expectation:
        lines.extend(
            [
                f"- Speed sequence expectation: {speed_expectation.get('status') or 'n/a'}",
                f"- Expected speed sequence: {speed_expectation.get('expected_sequence') or 'n/a'}",
                f"- Observed speed sequence: {speed_expectation.get('observed_sequence') or 'n/a'}",
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

    startable_visible = fast._lightning_visible_ui_snapshot(include_ocr=True)
    startable_preview_visible = fast.visible_startable_mission_preview(startable_visible)
    telemetry.event(
        "mission_preview_startable_probe",
        timer_seconds=_elapsed(timer_start),
        visible_ui=fast.compact_visible_ui(startable_visible),
        startable_preview_visible=startable_preview_visible,
    )
    explicit_non_startable = (
        "no vek detected" in fast.visible_text_lower(startable_visible)
    )
    if not startable_preview_visible and explicit_non_startable:
        return {
            "status": "FAIL",
            "reason": "mission_preview_not_startable",
            "dialogue_observation": dialogue_observation,
            "startable_probe": {
                "visible_ui": fast.compact_visible_ui(startable_visible),
                "startable_preview_visible": startable_preview_visible,
                "explicit_non_startable": explicit_non_startable,
            },
            "before_in_game_timer": None,
            "click": None,
            "click_wall_seconds": None,
            "samples": [],
            "first_bridge_deployment_sample": None,
            "pause": None,
            "after_pause_timer": None,
        }

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
        "total_turns": snapshot.get("total_turns"),
        "remaining_spawns": snapshot.get("remaining_spawns"),
        "is_infinite_spawn": snapshot.get("is_infinite_spawn"),
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


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bridge_final_turn_signal(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(snapshot, dict) or snapshot.get("status") != "OK":
        return {
            "expected_final_turn": False,
            "countdown_available": False,
            "source": "no_valid_bridge_snapshot",
        }

    turn = _int_or_none(snapshot.get("turn"))
    total_turns = _int_or_none(snapshot.get("total_turns"))
    remaining_spawns = _int_or_none(snapshot.get("remaining_spawns"))
    is_infinite_spawn = snapshot.get("is_infinite_spawn")
    if turn is None or total_turns is None or total_turns <= 0:
        return {
            "expected_final_turn": False,
            "countdown_available": remaining_spawns is not None,
            "source": (
                "bridge_turn_countdown_missing_remaining_spawns_present"
                if remaining_spawns is not None
                else "bridge_turn_countdown_missing"
            ),
            "turn": turn,
            "total_turns": total_turns,
            "remaining_spawns": remaining_spawns,
            "is_infinite_spawn": is_infinite_spawn,
        }

    expected = turn >= total_turns
    return {
        "expected_final_turn": expected,
        "countdown_available": True,
        "source": (
            "bridge_turn_reached_total_turns"
            if expected
            else "bridge_turn_before_total_turns"
        ),
        "turn": turn,
        "total_turns": total_turns,
        "remaining_spawns": remaining_spawns,
        "is_infinite_spawn": is_infinite_spawn,
    }


def _snapshot_left_player_turn_after_end_turn(snapshot: dict[str, Any]) -> bool:
    if not isinstance(snapshot, dict) or snapshot.get("status") != "OK":
        return False
    if snapshot.get("bridge_heartbeat_alive") is False:
        return False
    if snapshot.get("bridge_heartbeat_stale") is True:
        return False
    phase = snapshot.get("phase")
    return isinstance(phase, str) and phase != "combat_player"


def _snapshot_terminal_or_clear_after_end_turn(snapshot: dict[str, Any]) -> bool:
    if not isinstance(snapshot, dict) or snapshot.get("status") != "OK":
        return False
    if snapshot.get("in_active_mission") is False:
        return True
    phase = snapshot.get("phase")
    if phase in {"between_missions", "mission_ending"}:
        return True
    if snapshot.get("bridge_heartbeat_alive") is False:
        return False
    if snapshot.get("bridge_heartbeat_stale") is True:
        return False
    if phase == "unknown":
        try:
            active_mechs = int(snapshot.get("active_mechs") or 0)
            zones = int(snapshot.get("deployment_zone_count") or 0)
        except (TypeError, ValueError):
            return False
        return active_mechs == 0 and zones == 0
    return False


def _compact_visible_snapshot(visible: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(visible, dict):
        return {"status": "ERROR", "error": "visible_snapshot_not_dict"}
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


def _visible_text_lower(visible: dict[str, Any] | None) -> str:
    try:
        parts = fast._lightning_visible_ui_text_parts(visible)
    except Exception:
        parts = []
    return "\n".join(str(part) for part in parts).lower()


def _visible_region_secured(visible: dict[str, Any] | None) -> bool:
    if not isinstance(visible, dict) or visible.get("status") != "OK":
        return False
    if visible.get("region_secured_visible") is True:
        return True
    visible_name = visible.get("visible_ui")
    if visible_name in {"island_complete_leave", "bottom_continue_panel"}:
        return True
    text = _visible_text_lower(visible)
    if "region secured" in text:
        return True
    outcome = str(visible.get("terminal_outcome") or "").lower()
    return "region secured" in outcome


def _visible_terminal_or_clear(visible: dict[str, Any] | None) -> bool:
    if not isinstance(visible, dict) or visible.get("status") != "OK":
        return False
    visible_name = visible.get("visible_ui")
    if visible_name in fast.TERMINAL_OR_CLEAR_UIS:
        return True
    return _visible_region_secured(visible)


def hover_region_secured_continue(
    *,
    timer_start: float,
    telemetry: TelemetryRecorder,
    screenshots: ScreenshotRecorder,
    hover_seconds: float,
) -> dict[str, Any]:
    controls = list_known_window_controls()
    control = controls.get("reward_continue") or {
        "name": "reward_continue",
        "window_x": 1647,
        "window_y": 985,
    }
    x = int(control["window_x"])
    y = int(control["window_y"])
    before_timer = _timer_sample_from_recorder(
        screenshots,
        label="region_secured_continue_hover_before",
    )
    hover = fast.hover_window_point(
        "region_secured_continue",
        x,
        y,
        hover_seconds=hover_seconds,
    )
    proof_frame = screenshots.capture_once(
        clock_state="region_secured_continue_hover",
        note="hover_region_secured_continue",
    )
    proof_frame["timer_seconds"] = _elapsed(timer_start)
    proof_timer = _timer_sample_from_frame(
        proof_frame,
        label="region_secured_continue_hover_frame",
    )
    telemetry.event(
        "region_secured_continue_hover",
        timer_seconds=_elapsed(timer_start),
        control=control,
        hover=hover,
        before_in_game_timer=before_timer,
        screenshot_path=proof_frame.get("screenshot_path"),
        proof_frame_timer=proof_timer,
    )
    return {
        "status": "OK" if hover.get("status") == "OK" else "FAIL",
        "control": control,
        "hover": hover,
        "before_in_game_timer": before_timer,
        "proof_frame": proof_frame,
        "proof_frame_timer": proof_timer,
    }


def click_region_secured_continue(
    *,
    timer_start: float,
    telemetry: TelemetryRecorder,
    screenshots: ScreenshotRecorder,
    settle_seconds: float,
    post_observe_seconds: float = 0.0,
    screenshot_cadence: float = 0.5,
    post_visible_poll_seconds: float = 0.25,
) -> dict[str, Any]:
    controls = list_known_window_controls()
    control = controls.get("reward_continue") or {
        "name": "reward_continue",
        "window_x": 1647,
        "window_y": 985,
    }
    before_timer = _timer_sample_from_recorder(
        screenshots,
        label="region_secured_continue_click_before",
    )
    click_started = time.perf_counter()
    click = fast.click_ui_control("reward_continue", settle_seconds=settle_seconds)
    click_duration = round(time.perf_counter() - click_started, 3)
    after_frame = screenshots.capture_once(
        clock_state="region_secured_continue_click_after",
        note="click_region_secured_continue",
    )
    after_frame["timer_seconds"] = _elapsed(timer_start)
    after_timer = _timer_sample_from_frame(
        after_frame,
        label="region_secured_continue_click_after",
    )
    telemetry.event(
        "region_secured_continue_click",
        timer_seconds=_elapsed(timer_start),
        control=control,
        before_in_game_timer=before_timer,
        click=click,
        duration_seconds=click_duration,
        screenshot_path=after_frame.get("screenshot_path"),
        after_frame_timer=after_timer,
    )
    post_continue_observe = observe_after_region_secured_continue(
        timer_start=timer_start,
        telemetry=telemetry,
        screenshots=screenshots,
        observe_seconds=post_observe_seconds,
        screenshot_cadence=screenshot_cadence,
        visible_poll_seconds=post_visible_poll_seconds,
    )
    return {
        "status": "OK" if click.get("status") == "OK" else "FAIL",
        "control": control,
        "click": click,
        "duration_seconds": click_duration,
        "before_in_game_timer": before_timer,
        "after_frame": after_frame,
        "after_frame_timer": after_timer,
        "post_continue_observe": post_continue_observe,
    }


def observe_after_region_secured_continue(
    *,
    timer_start: float,
    telemetry: TelemetryRecorder,
    screenshots: ScreenshotRecorder,
    observe_seconds: float,
    screenshot_cadence: float,
    visible_poll_seconds: float,
) -> dict[str, Any]:
    if observe_seconds <= 0:
        return {
            "status": "SKIPPED",
            "reason": "post_continue_observe_seconds_zero",
            "observe_seconds_requested": observe_seconds,
        }

    started = time.perf_counter()
    next_frame_at = started
    next_visible_at = started
    frames: list[dict[str, Any]] = []
    visible_samples: list[dict[str, Any]] = []
    first_visible_sample: dict[str, Any] | None = None
    first_non_region_visible: dict[str, Any] | None = None

    while True:
        now = time.perf_counter()
        elapsed = now - started
        if elapsed >= max(0.0, observe_seconds):
            break

        did_work = False
        if now >= next_frame_at:
            frame = screenshots.capture_once(
                clock_state="post_region_secured_continue_observe",
                note="after_region_secured_continue",
            )
            frame["timer_seconds"] = _elapsed(timer_start)
            frame_timer = _timer_sample_from_frame(
                frame,
                label="post_region_secured_continue_frame",
            )
            frame_sample = {
                "timer_seconds": frame["timer_seconds"],
                "elapsed_after_continue_seconds": round(now - started, 3),
                "screenshot_path": frame.get("screenshot_path"),
                "frame_timer": frame_timer,
            }
            frames.append(frame_sample)
            telemetry.event("post_region_secured_continue_frame", **frame_sample)
            next_frame_at = max(
                next_frame_at + max(0.1, screenshot_cadence),
                time.perf_counter() + 0.01,
            )
            did_work = True

        now = time.perf_counter()
        if now >= next_visible_at:
            visible = fast._lightning_visible_ui_snapshot(include_ocr=False)
            compact = _compact_visible_snapshot(visible)
            visible_timer = _timer_sample_from_recorder(
                screenshots,
                label="post_region_secured_continue_visible",
            )
            visible_sample = {
                "timer_seconds": _elapsed(timer_start),
                "elapsed_after_continue_seconds": round(now - started, 3),
                "visible_ui": compact,
                "region_secured": _visible_region_secured(visible),
                "visible_timer": visible_timer,
            }
            if first_visible_sample is None:
                first_visible_sample = visible_sample
            if (
                first_non_region_visible is None
                and not visible_sample["region_secured"]
                and compact.get("status") == "OK"
            ):
                first_non_region_visible = visible_sample
            visible_samples.append(visible_sample)
            telemetry.event("post_region_secured_continue_visible_probe", **visible_sample)
            next_visible_at = max(
                next_visible_at + max(0.1, visible_poll_seconds),
                time.perf_counter() + 0.01,
            )
            did_work = True

        if not did_work:
            next_due = min(next_frame_at, next_visible_at)
            time.sleep(max(0.01, min(0.05, next_due - time.perf_counter())))

    return {
        "status": "OK",
        "observe_seconds_requested": observe_seconds,
        "observed_seconds": round(time.perf_counter() - started, 3),
        "frames": frames,
        "visible_samples": visible_samples,
        "first_visible_sample": first_visible_sample,
        "first_non_region_visible": first_non_region_visible,
    }


def _combat_fuzzy_block_skip_decision(
    turn: dict[str, Any],
    *,
    enabled: bool,
    min_actions_completed: int,
) -> dict[str, Any]:
    if not enabled:
        return {"skip": False, "reason": "policy_disabled"}
    if not isinstance(turn, dict):
        return {"skip": False, "reason": "turn_result_not_dict"}
    auto_status = turn.get("status")
    if auto_status != "FUZZY_INVESTIGATE_BLOCKED":
        return {"skip": False, "reason": "auto_turn_status_not_fuzzy_block"}
    held_batch = turn.get("held_end_turn_batch") or turn.get(
        "held_end_turn_codex_computer_use_batch"
    )
    if not held_batch:
        return {"skip": False, "reason": "missing_held_end_turn_batch"}
    try:
        actions_completed = int(turn.get("actions_completed") or 0)
    except (TypeError, ValueError):
        actions_completed = 0
    if actions_completed < int(min_actions_completed):
        return {
            "skip": False,
            "reason": "insufficient_completed_actions",
            "actions_completed": actions_completed,
            "min_actions_completed": int(min_actions_completed),
        }
    block = turn.get("block_reason") or {}
    return {
        "skip": True,
        "reason": "lightning_war_speedrun_fuzzy_block_skip",
        "auto_turn_status": auto_status,
        "actions_completed": actions_completed,
        "min_actions_completed": int(min_actions_completed),
        "block_reason": block,
        "signature": block.get("signature") if isinstance(block, dict) else None,
    }


def _auto_turn_time_pod_left_alive_block(auto_turn: dict[str, Any] | None) -> bool:
    if not isinstance(auto_turn, dict):
        return False
    if auto_turn.get("status") != "SAFETY_BLOCKED":
        return False
    plan_safety = auto_turn.get("plan_safety")
    if not isinstance(plan_safety, dict):
        return False
    blocking_kinds = [
        violation.get("kind")
        for violation in plan_safety.get("violations", []) or []
        if isinstance(violation, dict) and violation.get("blocking")
    ]
    return bool(blocking_kinds) and set(blocking_kinds) <= {"pod_unrecovered_final"}


def _combat_safety_block_auto_consent_decision(
    turn: dict[str, Any],
    *,
    enabled: bool,
) -> dict[str, Any]:
    if not enabled:
        return {"consent": False, "reason": "policy_disabled"}
    if not isinstance(turn, dict):
        return {"consent": False, "reason": "turn_result_not_dict"}
    if turn.get("status") != "SAFETY_BLOCKED":
        return {"consent": False, "reason": "auto_turn_status_not_safety_blocked"}
    if _auto_turn_time_pod_left_alive_block(turn):
        return {
            "consent": False,
            "reason": "time_pod_left_alive_speed_policy_block",
        }
    dirty_consent_id = turn.get("dirty_consent_id")
    if not dirty_consent_id:
        return {"consent": False, "reason": "missing_dirty_consent_id"}
    if turn.get("final_cave_resist_gamble"):
        return {"consent": False, "reason": "final_cave_resist_requires_review"}
    plan_safety = turn.get("plan_safety") or {}
    blocking_kinds = sorted(
        {
            str(violation.get("kind"))
            for violation in plan_safety.get("violations", []) or []
            if isinstance(violation, dict)
            and violation.get("blocking")
            and violation.get("kind")
        }
    )
    return {
        "consent": True,
        "reason": "lightning_war_timing_lab_speed_auto_consent",
        "dirty_consent_id": dirty_consent_id,
        "candidate_rank": turn.get("selected_candidate_rank"),
        "blocking_kinds": blocking_kinds,
    }


def _wait_for_deployment_bridge_ready(
    *,
    timer_start: float,
    telemetry: TelemetryRecorder,
    max_seconds: float,
    interval_seconds: float,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    started = time.perf_counter()
    while True:
        snapshot = fast._lightning_live_snapshot()
        sample = {
            "timer_seconds": _elapsed(timer_start),
            "ready": fast.deployment_snapshot_ready(snapshot),
            "snapshot": _compact_bridge_snapshot(snapshot),
        }
        samples.append(sample)
        telemetry.event("deployment_bridge_ready_wait", **sample)
        if sample["ready"]:
            return {
                "status": "OK",
                "ready_sample": sample,
                "samples": samples,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
        if time.perf_counter() - started >= max(0.0, max_seconds):
            return {
                "status": "TIMEOUT",
                "ready_sample": None,
                "samples": samples,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
        time.sleep(max(0.01, interval_seconds))


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
    bridge_ready_wait_seconds: float = 1.5,
    bridge_ready_poll_seconds: float = 0.05,
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

    bridge_ready_wait = _wait_for_deployment_bridge_ready(
        timer_start=timer_start,
        telemetry=telemetry,
        max_seconds=bridge_ready_wait_seconds,
        interval_seconds=bridge_ready_poll_seconds,
    )
    if bridge_ready_wait.get("status") != "OK":
        return {
            "status": "FAIL",
            "reason": "deployment_bridge_not_ready",
            "before_in_game_timer": before_timer,
            "bridge_ready_wait": bridge_ready_wait,
            "deploy_duration_seconds": 0.0,
            "deploy_result": None,
            "deploy_result_compact": {
                "status": "ERROR",
                "reason": "deployment_bridge_not_ready",
                "deployment_count": 0,
                "existing_deployment_count": 0,
                "phase": None,
                "ui_fallback_status": None,
                "accepted": False,
            },
            "post_deploy_frame": None,
            "post_deploy_frame_timer": None,
            "after_in_game_timer": None,
            "pause": None,
            "after_pause_timer": None,
        }

    deploy_started = time.perf_counter()
    deploy = fast.cmd_deploy_recommended(
        profile=profile,
        ui_fallback=False,
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
        "bridge_ready_wait": bridge_ready_wait,
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


def solve_execute_end_turn_and_observe_next_turn(
    *,
    timer_start: float,
    telemetry: TelemetryRecorder,
    screenshots: ScreenshotRecorder,
    auto_turn_time_limit: float,
    auto_turn_max_wait: float,
    observe_seconds: float,
    screenshot_cadence: float,
    bridge_poll_seconds: float,
    extra_ready_frames: int,
    pause_after_ready: bool,
    retry_after_seconds: float,
    continue_after_fuzzy_block: bool,
    fuzzy_block_min_actions: int,
    auto_consent_safety_block: bool = True,
    destroy_time_pods: bool = True,
    stop_on_region_secured: bool = False,
    visible_poll_seconds: float = 0.5,
    terminal_visual_settle_seconds: float = 1.0,
    hover_region_continue: bool = False,
    region_continue_hover_seconds: float = 1.0,
    click_region_continue: bool = False,
    region_continue_click_settle_seconds: float = 0.35,
    region_continue_post_observe_seconds: float = 0.0,
    region_continue_post_visible_poll_seconds: float = 0.25,
    refresh_paused_bridge_before_auto_turn: bool = False,
) -> dict[str, Any]:
    bridge_refresh_before_auto_turn: dict[str, Any] | None = None
    if refresh_paused_bridge_before_auto_turn:
        bridge_refresh_before_auto_turn = fast.refresh_bridge_before_paused_solve(
            turn_index=0
        )
        telemetry.event(
            "combat_auto_turn_bridge_refresh",
            timer_seconds=_elapsed(timer_start),
            refresh=bridge_refresh_before_auto_turn,
        )
    before_timer = _timer_sample_from_recorder(
        screenshots,
        label="combat_auto_turn_before",
    )
    telemetry.event(
        "combat_auto_turn_start",
        timer_seconds=_elapsed(timer_start),
        before_in_game_timer=before_timer,
        signal_source="opening_player_turn_bridge_ready_pause",
        note=(
            "auto_turn solves and verifies the combat actions; "
            "resume_before_execute keeps solver thinking out of live timer"
        ),
    )
    def summarize_turn(turn_result: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": turn_result.get("status") or turn_result.get("error"),
            "turn": turn_result.get("turn"),
            "actions_completed": turn_result.get("actions_completed"),
            "score": turn_result.get("score"),
            "re_solves": turn_result.get("re_solves"),
            "wait_entry_seconds": turn_result.get("wait_entry_seconds"),
            "selected_candidate_rank": turn_result.get("selected_candidate_rank"),
            "dirty_consent_id": turn_result.get("dirty_consent_id"),
            "has_end_turn_batch": bool(
                turn_result.get("batch")
                or turn_result.get("pending_end_turn_batch")
                or turn_result.get("held_end_turn_batch")
                or turn_result.get("held_end_turn_codex_computer_use_batch")
            ),
            "next_step": turn_result.get("next_step"),
        }

    auto_started = time.perf_counter()
    attempt_started = time.perf_counter()
    turn = fast.cmd_auto_turn(
        time_limit=auto_turn_time_limit,
        max_wait=auto_turn_max_wait,
        wait_poll_interval=0.2,
        resume_before_execute=True,
        lightning_speed_loss_policy=True,
        destroy_time_pods=destroy_time_pods,
    )
    first_auto_duration = round(time.perf_counter() - attempt_started, 3)
    auto_done_timer = _timer_sample_from_recorder(
        screenshots,
        label="combat_auto_turn_done",
    )
    turn_summary = summarize_turn(turn)
    auto_turn_attempts = [
        {
            "attempt": 1,
            "kind": "initial",
            "duration_seconds": first_auto_duration,
            "done_timer": auto_done_timer,
            "summary": turn_summary,
        }
    ]
    telemetry.event(
        "combat_auto_turn_result",
        timer_seconds=_elapsed(timer_start),
        duration_seconds=first_auto_duration,
        after_in_game_timer=auto_done_timer,
        result=turn_summary,
    )
    safety_auto_consent = _combat_safety_block_auto_consent_decision(
        turn,
        enabled=auto_consent_safety_block,
    )
    if safety_auto_consent.get("consent"):
        telemetry.event(
            "combat_auto_turn_safety_block_auto_consented",
            timer_seconds=_elapsed(timer_start),
            decision=safety_auto_consent,
            blocked_result=turn_summary,
        )
        retry_started = time.perf_counter()
        turn = fast.cmd_auto_turn(
            time_limit=auto_turn_time_limit,
            max_wait=auto_turn_max_wait,
            wait_poll_interval=0.2,
            resume_before_execute=True,
            lightning_speed_loss_policy=True,
            destroy_time_pods=destroy_time_pods,
            allow_dirty_plan=True,
            candidate_rank=safety_auto_consent.get("candidate_rank"),
            dirty_consent_id=safety_auto_consent.get("dirty_consent_id"),
            allow_protected_objective_loss=True,
            allow_objective_loss=True,
        )
        retry_duration = round(time.perf_counter() - retry_started, 3)
        auto_done_timer = _timer_sample_from_recorder(
            screenshots,
            label="combat_auto_turn_dirty_consent_done",
        )
        turn_summary = summarize_turn(turn)
        auto_turn_attempts.append(
            {
                "attempt": 2,
                "kind": "dirty_consent",
                "duration_seconds": retry_duration,
                "done_timer": auto_done_timer,
                "summary": turn_summary,
                "decision": safety_auto_consent,
            }
        )
        telemetry.event(
            "combat_auto_turn_dirty_consent_result",
            timer_seconds=_elapsed(timer_start),
            duration_seconds=retry_duration,
            after_in_game_timer=auto_done_timer,
            result=turn_summary,
            decision=safety_auto_consent,
        )
    auto_duration = round(time.perf_counter() - auto_started, 3)
    fuzzy_skip = _combat_fuzzy_block_skip_decision(
        turn,
        enabled=continue_after_fuzzy_block,
        min_actions_completed=fuzzy_block_min_actions,
    )
    pod_left_alive_block = _auto_turn_time_pod_left_alive_block(turn)
    if turn.get("status") != "PLAN" and not fuzzy_skip.get("skip"):
        return {
            "status": "FAIL",
            "reason": (
                "time_pod_left_alive_speed_policy_block"
                if pod_left_alive_block
                else "auto_turn_did_not_return_end_turn_plan"
            ),
            "solver_action_signal_source": "cmd_auto_turn",
            "end_turn_signal_source": (
                "not_clicked_time_pod_left_alive_speed_policy"
                if pod_left_alive_block
                else "not_clicked_auto_turn_safety_stop"
            ),
            "player_turn_signal_source": None,
            "visual_evidence_role": "2hz_screenshots_before_solver_stop_only",
            "safety_stop_reason": turn.get("block_reason") or turn.get("next_step"),
            "speed_policy_stop": (
                {
                    "kind": "time_pod_left_alive",
                    "required_resolution": "destroy_time_pod_or_reroute",
                    "dirty_consent_allowed": False,
                }
                if pod_left_alive_block
                else None
            ),
            "before_in_game_timer": before_timer,
            "auto_turn_duration_seconds": auto_duration,
            "auto_turn_done_timer": auto_done_timer,
            "bridge_refresh_before_auto_turn": bridge_refresh_before_auto_turn,
            "auto_turn": turn,
            "auto_turn_summary": turn_summary,
            "auto_turn_attempts": auto_turn_attempts,
            "auto_turn_safety_block_auto_consent": safety_auto_consent,
            "auto_turn_block_skip_decision": fuzzy_skip,
        }
    if fuzzy_skip.get("skip"):
        telemetry.event(
            "combat_auto_turn_fuzzy_block_skipped",
            timer_seconds=_elapsed(timer_start),
            decision=fuzzy_skip,
            safety_stop_reason=turn.get("block_reason") or turn.get("next_step"),
        )

    end_turn_before_timer = _timer_sample_from_recorder(
        screenshots,
        label="combat_end_turn_click_before",
    )
    click_started = time.perf_counter()
    end_turn_click = fast.click_control("end_turn", settle_seconds=0.0)
    end_turn_click_duration = round(time.perf_counter() - click_started, 3)
    end_turn_click_wall = _elapsed(timer_start)
    telemetry.event(
        "combat_end_turn_click",
        timer_seconds=end_turn_click_wall,
        before_in_game_timer=end_turn_before_timer,
        duration_seconds=end_turn_click_duration,
        click=end_turn_click,
    )

    started = time.perf_counter()
    next_frame_at = started
    next_bridge_at = started
    next_visible_at = started
    frames: list[dict[str, Any]] = []
    bridge_samples: list[dict[str, Any]] = []
    visible_samples: list[dict[str, Any]] = []
    first_non_player_bridge: dict[str, Any] | None = None
    first_terminal_bridge: dict[str, Any] | None = None
    first_terminal_visible: dict[str, Any] | None = None
    first_region_secured_visible: dict[str, Any] | None = None
    first_player_ready_bridge: dict[str, Any] | None = None
    first_non_player_visual: dict[str, Any] | None = None
    ready_frames_seen = 0
    ready_frame: dict[str, Any] | None = None
    retry_click: dict[str, Any] | None = None
    retry_timer: dict[str, Any] | None = None
    retry_elapsed_after_end_turn: float | None = None
    retry_bridge_sample_count: int | None = None

    while True:
        now = time.perf_counter()
        elapsed = now - started
        if elapsed >= max(0.0, observe_seconds):
            break

        did_work = False
        if now >= next_bridge_at:
            snapshot = fast._lightning_live_snapshot()
            compact = _compact_bridge_snapshot(snapshot)
            sample = {
                "timer_seconds": _elapsed(timer_start),
                "elapsed_after_end_turn_seconds": round(now - started, 3),
                "snapshot": compact,
                "left_player_turn": _snapshot_left_player_turn_after_end_turn(
                    snapshot
                ),
                "terminal_or_clear": _snapshot_terminal_or_clear_after_end_turn(
                    snapshot
                ),
                "player_ready": _snapshot_actionable_player_turn(snapshot),
            }
            if first_non_player_bridge is None and sample["left_player_turn"]:
                sample["bridge_timer"] = _timer_sample_from_recorder(
                    screenshots,
                    label="combat_end_turn_bridge_left_player",
                )
                first_non_player_bridge = sample
            if first_terminal_bridge is None and sample["terminal_or_clear"]:
                sample["bridge_timer"] = _timer_sample_from_recorder(
                    screenshots,
                    label="combat_end_turn_bridge_terminal",
                )
                first_terminal_bridge = sample
            if first_player_ready_bridge is None and sample["player_ready"]:
                sample["bridge_timer"] = _timer_sample_from_recorder(
                    screenshots,
                    label="combat_post_end_turn_player_ready",
                )
                first_player_ready_bridge = sample
            bridge_samples.append(sample)
            telemetry.event("post_end_turn_bridge_probe", **sample)
            next_bridge_at = max(
                next_bridge_at + max(0.05, bridge_poll_seconds),
                time.perf_counter() + 0.01,
            )
            did_work = True

        now = time.perf_counter()
        elapsed = now - started
        if (
            retry_click is None
            and first_non_player_bridge is None
            and first_non_player_visual is None
            and elapsed >= max(0.1, retry_after_seconds)
        ):
            observed = {
                "status": "END_TURN_CLICK_NOT_OBSERVED",
                "reason": "bridge_still_player_turn",
                "samples": [
                    sample.get("snapshot") or {}
                    for sample in bridge_samples
                    if isinstance(sample, dict)
                ],
            }
            if fast._lightning_end_turn_retryable(observed, turn):
                retry_elapsed_after_end_turn = round(elapsed, 3)
                retry_bridge_sample_count = len(observed["samples"])
                retry_timer = _timer_sample_from_recorder(
                    screenshots,
                    label="combat_end_turn_retry_before",
                )
                retry_click = fast.click_control("end_turn", settle_seconds=0.0)
                telemetry.event(
                    "combat_end_turn_retry_click",
                    timer_seconds=_elapsed(timer_start),
                    elapsed_after_end_turn_seconds=retry_elapsed_after_end_turn,
                    bridge_sample_count=retry_bridge_sample_count,
                    before_in_game_timer=retry_timer,
                    click=retry_click,
                )
                did_work = True

        now = time.perf_counter()
        if now >= next_frame_at:
            frame = screenshots.capture_once(
                clock_state="post_end_turn_observe",
                note="after_combat_end_turn",
            )
            frame["timer_seconds"] = _elapsed(timer_start)
            frame_timer = _timer_sample_from_frame(
                frame,
                label="post_end_turn_observe_frame",
            )
            frame_sample = {
                "timer_seconds": frame["timer_seconds"],
                "screenshot_path": frame.get("screenshot_path"),
                "frame_timer": frame_timer,
                "after_player_ready_bridge": first_player_ready_bridge is not None,
            }
            transition_banner = _post_end_turn_transition_banner_from_frame(frame)
            frame_sample["post_end_turn_transition_banner"] = transition_banner
            if (
                first_non_player_visual is None
                and transition_banner.get("transition_visible")
            ):
                first_non_player_visual = {
                    "timer_seconds": frame["timer_seconds"],
                    "elapsed_after_end_turn_seconds": round(
                        time.perf_counter() - started,
                        3,
                    ),
                    "screenshot_path": frame.get("screenshot_path"),
                    "frame_timer": frame_timer,
                    "transition_banner": transition_banner,
                }
            frames.append(frame_sample)
            telemetry.event("post_end_turn_frame", **frame_sample)
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
        if (
            first_player_ready_bridge is not None
            and first_terminal_bridge is None
            and ready_frames_seen >= max(0, int(extra_ready_frames))
        ):
            break

        if stop_on_region_secured and now >= next_visible_at:
            include_ocr = (
                first_terminal_bridge is not None
                and now - started
                >= float(first_terminal_bridge.get("elapsed_after_end_turn_seconds") or 0.0)
                + max(0.0, terminal_visual_settle_seconds)
            )
            visible = fast._lightning_visible_ui_snapshot(include_ocr=include_ocr)
            compact_visible = _compact_visible_snapshot(visible)
            visible_sample = {
                "timer_seconds": _elapsed(timer_start),
                "elapsed_after_end_turn_seconds": round(now - started, 3),
                "visible_ui": compact_visible,
                "terminal_or_clear": _visible_terminal_or_clear(visible),
                "region_secured": _visible_region_secured(visible),
                "include_ocr": include_ocr,
            }
            if (
                first_terminal_visible is None
                and visible_sample["terminal_or_clear"]
            ):
                visible_sample["visible_timer"] = _timer_sample_from_recorder(
                    screenshots,
                    label="combat_end_turn_visible_terminal",
                )
                first_terminal_visible = visible_sample
            if (
                first_region_secured_visible is None
                and visible_sample["region_secured"]
            ):
                visible_sample["visible_timer"] = _timer_sample_from_recorder(
                    screenshots,
                    label="combat_region_secured_visible",
                )
                first_region_secured_visible = visible_sample
            visible_samples.append(visible_sample)
            telemetry.event("post_end_turn_visible_probe", **visible_sample)
            next_visible_at = max(
                next_visible_at + max(0.1, visible_poll_seconds),
                time.perf_counter() + 0.01,
            )
            did_work = True

        if first_region_secured_visible is not None:
            break

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
            description="pause after combat post-end-turn player ready",
            app_name=fast.APP_NAME,
            settle_seconds=0.05,
        )
        after_pause_timer = _timer_sample_from_recorder(
            screenshots,
            label="combat_post_end_turn_after_pause",
        )
        telemetry.event(
            "combat_post_end_turn_pause",
            timer_seconds=_elapsed(timer_start),
            click=pause,
            after_pause_timer=after_pause_timer,
        )

    region_continue_hover: dict[str, Any] | None = None
    if hover_region_continue and first_region_secured_visible is not None:
        region_continue_hover = hover_region_secured_continue(
            timer_start=timer_start,
            telemetry=telemetry,
            screenshots=screenshots,
            hover_seconds=region_continue_hover_seconds,
        )

    region_continue_click: dict[str, Any] | None = None
    if click_region_continue and first_region_secured_visible is not None:
        region_continue_click = click_region_secured_continue(
            timer_start=timer_start,
            telemetry=telemetry,
            screenshots=screenshots,
            settle_seconds=region_continue_click_settle_seconds,
            post_observe_seconds=region_continue_post_observe_seconds,
            screenshot_cadence=screenshot_cadence,
            post_visible_poll_seconds=region_continue_post_visible_poll_seconds,
        )

    boundary = (
        "region_secured"
        if first_region_secured_visible is not None
        else "player_turn_ready"
        if first_player_ready_bridge is not None
        else "unknown"
    )
    status = (
        "PASS"
        if (
            end_turn_click.get("status") == "OK"
            and (
                first_region_secured_visible is not None
                or first_player_ready_bridge is not None
            )
        )
        else "FAIL"
    )
    return {
        "status": status,
        "reason": (
            "combat_region_secured_visible"
            if first_region_secured_visible is not None
            else
            "combat_post_end_turn_player_ready"
            if first_player_ready_bridge is not None
            and not fuzzy_skip.get("skip")
            else "combat_post_end_turn_player_ready_after_fuzzy_block_skip"
            if first_player_ready_bridge is not None
            else "combat_post_end_turn_not_detected"
        ),
        "boundary": boundary,
        "solver_action_signal_source": "cmd_auto_turn",
        "end_turn_signal_source": (
            "fuzzy_block_held_end_turn_speedrun_skip"
            if fuzzy_skip.get("skip")
            else "auto_turn_end_turn_plan_then_ui_click"
        ),
        "player_turn_signal_source": "bridge_lua_live_snapshot",
        "visual_evidence_role": "2hz_screenshots_for_audit_not_primary_signal",
        "auto_turn_block_skipped": bool(fuzzy_skip.get("skip")),
        "auto_turn_block_skip_decision": fuzzy_skip,
        "auto_turn_safety_block_auto_consent": safety_auto_consent,
        "safety_stop_reason": (
            turn.get("block_reason") or turn.get("next_step")
            if fuzzy_skip.get("skip")
            else None
        ),
        "before_in_game_timer": before_timer,
        "auto_turn": turn,
        "auto_turn_summary": turn_summary,
        "auto_turn_attempts": auto_turn_attempts,
        "bridge_refresh_before_auto_turn": bridge_refresh_before_auto_turn,
        "auto_turn_duration_seconds": auto_duration,
        "auto_turn_done_timer": auto_done_timer,
        "end_turn_before_in_game_timer": end_turn_before_timer,
        "end_turn_click": end_turn_click,
        "end_turn_click_wall_seconds": end_turn_click_wall,
        "end_turn_click_duration_seconds": end_turn_click_duration,
        "end_turn_retry_click": retry_click,
        "end_turn_retry_before_in_game_timer": retry_timer,
        "end_turn_retry_elapsed_after_end_turn_seconds": (
            retry_elapsed_after_end_turn
        ),
        "end_turn_retry_bridge_sample_count": retry_bridge_sample_count,
        "observe_seconds_requested": observe_seconds,
        "observed_seconds": round(time.perf_counter() - started, 3),
        "frames": frames,
        "bridge_samples": bridge_samples,
        "visible_samples": visible_samples,
        "first_non_player_bridge": first_non_player_bridge,
        "first_non_player_visual": first_non_player_visual,
        "first_terminal_bridge": first_terminal_bridge,
        "first_terminal_visible": first_terminal_visible,
        "first_region_secured_visible": first_region_secured_visible,
        "region_secured_continue_hover": region_continue_hover,
        "region_secured_continue_click": region_continue_click,
        "first_player_ready_bridge": first_player_ready_bridge,
        "first_player_ready_frame_after_bridge": ready_frame,
        "pause": pause,
        "after_pause_timer": after_pause_timer,
    }


def _combat_next_patch(combat_turn_result: dict[str, Any] | None) -> str:
    if not isinstance(combat_turn_result, dict):
        return "Fix combat auto_turn startup before End Turn timing."
    auto_turn = combat_turn_result.get("auto_turn") or {}
    if _auto_turn_time_pod_left_alive_block(auto_turn):
        return (
            "Force a Time Pod destruction line or reroute; do not "
            "dirty-consent pod_unrecovered_final because a surviving Time Pod "
            "is recovered and adds post-mission UI."
        )
    auto_summary = combat_turn_result.get("auto_turn_summary") or {}
    auto_status = auto_summary.get("status")
    if auto_status and auto_status != "PLAN":
        stop = combat_turn_result.get("safety_stop_reason")
        if not isinstance(stop, dict):
            stop = auto_turn.get("block_reason")
        signature = stop.get("signature") if isinstance(stop, dict) else None
        suffix = f" ({signature})" if signature else ""
        return (
            "Diagnose combat auto_turn safety block before End Turn timing"
            f"{suffix}."
        )
    if not combat_turn_result.get("end_turn_click"):
        return "Fix combat End Turn click before post-End-Turn timing."
    return "Fix combat post-End-Turn player-ready detection."


def solve_until_region_secured(
    *,
    timer_start: float,
    telemetry: TelemetryRecorder,
    screenshots: ScreenshotRecorder,
    max_turns: int,
    auto_turn_time_limit: float,
    auto_turn_max_wait: float,
    observe_seconds: float,
    screenshot_cadence: float,
    bridge_poll_seconds: float,
    visible_poll_seconds: float,
    terminal_visual_settle_seconds: float,
    extra_ready_frames: int,
    pause_after_ready: bool,
    retry_after_seconds: float,
    continue_after_fuzzy_block: bool,
    fuzzy_block_min_actions: int,
    hover_region_continue: bool,
    region_continue_hover_seconds: float,
    click_region_continue: bool,
    region_continue_click_settle_seconds: float,
    auto_consent_safety_block: bool = True,
    region_continue_post_observe_seconds: float = 0.0,
    region_continue_post_visible_poll_seconds: float = 0.25,
    destroy_time_pods: bool = True,
    expected_terminal_after_turn: int | None = None,
    expected_terminal_visible_poll_seconds: float | None = None,
    refresh_paused_bridge_before_auto_turn: bool = False,
    initial_player_ready_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    turns: list[dict[str, Any]] = []
    player_ready_snapshot = (
        _compact_bridge_snapshot(initial_player_ready_snapshot)
        if isinstance(initial_player_ready_snapshot, dict)
        else None
    )
    for turn_index in range(1, max(1, int(max_turns)) + 1):
        final_turn_signal = _bridge_final_turn_signal(player_ready_snapshot)
        fallback_expected_final_turn = (
            expected_terminal_after_turn is not None
            and turn_index >= int(expected_terminal_after_turn)
        )
        expected_final_turn = bool(
            final_turn_signal.get("expected_final_turn")
            or (
                not final_turn_signal.get("countdown_available")
                and fallback_expected_final_turn
            )
        )
        expected_final_turn_source = (
            final_turn_signal.get("source")
            if final_turn_signal.get("expected_final_turn")
            or final_turn_signal.get("countdown_available")
            else (
                "fallback_expected_turn_index"
                if fallback_expected_final_turn
                else final_turn_signal.get("source")
            )
        )
        turn_visible_poll_seconds = visible_poll_seconds
        if expected_final_turn and expected_terminal_visible_poll_seconds is not None:
            turn_visible_poll_seconds = min(
                visible_poll_seconds,
                max(0.05, float(expected_terminal_visible_poll_seconds)),
            )
        telemetry.event(
            "combat_region_loop_turn_start",
            timer_seconds=_elapsed(timer_start),
            loop_turn_index=turn_index,
            expected_final_turn=expected_final_turn,
            expected_final_turn_source=expected_final_turn_source,
            final_turn_signal=final_turn_signal,
            player_ready_snapshot=player_ready_snapshot,
        )
        turn_result = solve_execute_end_turn_and_observe_next_turn(
            timer_start=timer_start,
            telemetry=telemetry,
            screenshots=screenshots,
            auto_turn_time_limit=auto_turn_time_limit,
            auto_turn_max_wait=auto_turn_max_wait,
            destroy_time_pods=destroy_time_pods,
            observe_seconds=observe_seconds,
            screenshot_cadence=screenshot_cadence,
            bridge_poll_seconds=bridge_poll_seconds,
            extra_ready_frames=extra_ready_frames,
            pause_after_ready=pause_after_ready,
            retry_after_seconds=retry_after_seconds,
            continue_after_fuzzy_block=continue_after_fuzzy_block,
            fuzzy_block_min_actions=fuzzy_block_min_actions,
            auto_consent_safety_block=auto_consent_safety_block,
            stop_on_region_secured=True,
            visible_poll_seconds=turn_visible_poll_seconds,
            terminal_visual_settle_seconds=terminal_visual_settle_seconds,
            hover_region_continue=hover_region_continue,
            region_continue_hover_seconds=region_continue_hover_seconds,
            click_region_continue=click_region_continue,
            region_continue_click_settle_seconds=(
                region_continue_click_settle_seconds
            ),
            region_continue_post_observe_seconds=(
                region_continue_post_observe_seconds
            ),
            region_continue_post_visible_poll_seconds=(
                region_continue_post_visible_poll_seconds
            ),
            refresh_paused_bridge_before_auto_turn=(
                refresh_paused_bridge_before_auto_turn
            ),
        )
        turn_result["loop_turn_index"] = turn_index
        turn_result["expected_final_turn"] = expected_final_turn
        turn_result["expected_final_turn_source"] = expected_final_turn_source
        turn_result["final_turn_signal"] = final_turn_signal
        turn_result["pre_turn_player_ready_snapshot"] = player_ready_snapshot
        turn_result["visible_poll_seconds_used"] = turn_visible_poll_seconds
        turns.append(turn_result)
        telemetry.event(
            "combat_region_loop_turn_result",
            timer_seconds=_elapsed(timer_start),
            loop_turn_index=turn_index,
            status=turn_result.get("status"),
            reason=turn_result.get("reason"),
            boundary=turn_result.get("boundary"),
            auto_turn_summary=turn_result.get("auto_turn_summary"),
            expected_final_turn=expected_final_turn,
            expected_final_turn_source=expected_final_turn_source,
            final_turn_signal=final_turn_signal,
        )
        if expected_final_turn and turn_result.get("boundary") == "player_turn_ready":
            telemetry.event(
                "combat_region_loop_expected_sequence_mismatch",
                timer_seconds=_elapsed(timer_start),
                loop_turn_index=turn_index,
                expected_terminal_after_turn=expected_terminal_after_turn,
                expected_final_turn_source=expected_final_turn_source,
                final_turn_signal=final_turn_signal,
                observed_boundary=turn_result.get("boundary"),
                fallback="continuing_dynamic_region_loop",
            )
        if (
            turn_result.get("status") == "PASS"
            and turn_result.get("boundary") == "region_secured"
        ):
            continue_click = turn_result.get("region_secured_continue_click")
            return {
                "status": "PASS",
                "reason": (
                    "region_secured_visible_continue_clicked"
                    if continue_click
                    else "region_secured_visible_continue_hovered"
                ),
                "turns": turns,
                "turns_attempted": turn_index,
                "last_end_turn": turn_result,
                "region_secured": turn_result.get("first_region_secured_visible"),
                "continue_hover": turn_result.get("region_secured_continue_hover"),
                "continue_click": continue_click,
            }
        if turn_result.get("status") != "PASS":
            return {
                "status": "FAIL",
                "reason": "combat_turn_failed_before_region_secured",
                "turns": turns,
                "turns_attempted": turn_index,
                "last_turn": turn_result,
            }
        next_ready = turn_result.get("first_player_ready_bridge") or {}
        next_snapshot = next_ready.get("snapshot")
        player_ready_snapshot = (
            _compact_bridge_snapshot(next_snapshot)
            if isinstance(next_snapshot, dict)
            else None
        )
    return {
        "status": "FAIL",
        "reason": "region_secured_not_seen_before_max_turns",
        "turns": turns,
        "turns_attempted": len(turns),
        "max_turns": max_turns,
    }


def _region_loop_next_patch(region_loop: dict[str, Any] | None) -> str:
    if not isinstance(region_loop, dict):
        return "Fix combat-to-Region-Secured timing loop startup."
    if region_loop.get("status") == "PASS":
        click = region_loop.get("continue_click") or {}
        if click.get("status") == "OK":
            return "Learn the next post-Region-Secured island-map route step."
        return "Review Region Secured Continue hover coordinates, then append safe Continue click."
    if region_loop.get("reason") == "region_secured_not_seen_before_max_turns":
        return "Increase combat loop max turns or inspect why Region Secured did not appear."
    last_turn = region_loop.get("last_turn") or region_loop.get("last_end_turn")
    if isinstance(last_turn, dict):
        return _combat_next_patch(last_turn)
    return "Fix combat-to-Region-Secured timing loop."


def run_current_combat_region_secured(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or _now_run_id()
    memory_timer_address = _parse_optional_timer_address(args.memory_timer_address)
    (
        memory_live_timer_address,
        memory_live_timer_kind,
        memory_live_timer_proof_validation,
    ) = _resolve_live_timer_config(args)
    telemetry = TelemetryRecorder(run_id=run_id, root=ROOT / "recordings")
    route_slice = (
        "current_combat_to_region_secured_continue_click"
        if args.region_secured_click_continue
        else "current_combat_to_region_secured_continue_hover"
    )
    telemetry.write_manifest(
        {
            "achievement": "Lightning War",
            "route_slice": route_slice,
            "screenshot_cadence_seconds": args.screenshot_cadence,
            "starting_anchor": "current_combat_state",
            "memory_live_timer_address": (
                f"0x{memory_live_timer_address:016x}"
                if memory_live_timer_address is not None
                else None
            ),
            "memory_live_timer_kind": memory_live_timer_kind,
            "memory_live_timer_proof": _repo_relative_text(
                (memory_live_timer_proof_validation or {}).get("proof_path")
                or args.memory_live_timer_proof
            ),
            "auto_memory_live_timer_proof": args.auto_memory_live_timer_proof,
            "require_memory_live_timer_proof": args.require_memory_live_timer_proof,
            "memory_live_timer_proof_validation": memory_live_timer_proof_validation,
            "combat_loop_max_turns": args.combat_loop_max_turns,
            "region_secured_hover_continue": args.region_secured_hover_continue,
            "region_secured_click_continue": args.region_secured_click_continue,
            "combat_auto_consent_safety_block": (
                getattr(args, "combat_auto_consent_safety_block", True)
            ),
        }
    )
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
    initial_visible = fast._lightning_visible_ui_snapshot(include_ocr=False)
    initial_bridge = fast._lightning_live_snapshot()
    in_game_timers: dict[str, Any] = {
        "pre_timer": read_in_game_timer(
            args.profile,
            label="pre_timer",
            use_memory=args.memory_timer_probe,
            timer_address=memory_timer_address,
            live_timer_address=memory_live_timer_address,
            live_timer_kind=memory_live_timer_kind,
        )
    }
    telemetry.event(
        "current_combat_region_loop_start",
        timer_seconds=0.0,
        visible_ui=_compact_visible_snapshot(initial_visible),
        bridge_snapshot=_compact_bridge_snapshot(initial_bridge),
    )
    if _visible_terminal_or_clear(initial_visible):
        visible_timer = _timer_sample_from_recorder(
            screenshots,
            label="region_secured_visible",
        )
        visible_sample = {
            "timer_seconds": _elapsed(timer_start),
            "elapsed_after_end_turn_seconds": None,
            "visible_ui": _compact_visible_snapshot(initial_visible),
            "terminal_or_clear": True,
            "region_secured": _visible_region_secured(initial_visible),
            "include_ocr": False,
            "visible_timer": visible_timer,
            "note": "terminal_continue_panel_already_visible_at_entry",
        }
        continue_hover = (
            hover_region_secured_continue(
                timer_start=timer_start,
                telemetry=telemetry,
                screenshots=screenshots,
                hover_seconds=args.region_secured_continue_hover_seconds,
            )
            if args.region_secured_hover_continue
            else None
        )
        continue_click = (
            click_region_secured_continue(
                timer_start=timer_start,
                telemetry=telemetry,
                screenshots=screenshots,
                settle_seconds=args.region_secured_continue_click_settle_seconds,
                post_observe_seconds=(
                    args.region_secured_post_continue_observe_seconds
                ),
                screenshot_cadence=args.screenshot_cadence,
                post_visible_poll_seconds=(
                    args.region_secured_post_continue_visible_poll_seconds
                ),
            )
            if args.region_secured_click_continue
            else None
        )
        region_loop = {
            "status": "PASS",
            "reason": (
                "terminal_continue_panel_already_visible_clicked"
                if continue_click
                else "terminal_continue_panel_already_visible"
            ),
            "turns": [],
            "turns_attempted": 0,
            "region_secured": visible_sample,
            "continue_hover": continue_hover,
            "continue_click": continue_click,
            "initial_visible_terminal": True,
        }
    else:
        region_loop = solve_until_region_secured(
            timer_start=timer_start,
            telemetry=telemetry,
            screenshots=screenshots,
            max_turns=args.combat_loop_max_turns,
            auto_turn_time_limit=args.combat_auto_turn_time_limit,
            auto_turn_max_wait=args.combat_auto_turn_max_wait,
            destroy_time_pods=args.destroy_time_pods,
            observe_seconds=args.post_end_turn_observe_seconds,
            screenshot_cadence=args.screenshot_cadence,
            bridge_poll_seconds=args.post_end_turn_bridge_poll_seconds,
            visible_poll_seconds=args.region_secured_visible_poll_seconds,
            terminal_visual_settle_seconds=args.region_secured_terminal_settle_seconds,
            extra_ready_frames=args.post_end_turn_extra_ready_frames,
            pause_after_ready=args.pause_after_combat_player_turn,
            retry_after_seconds=args.end_turn_retry_after_seconds,
            continue_after_fuzzy_block=args.combat_continue_after_fuzzy_block,
            fuzzy_block_min_actions=args.combat_fuzzy_block_min_actions,
            auto_consent_safety_block=getattr(
                args,
                "combat_auto_consent_safety_block",
                True,
            ),
            hover_region_continue=args.region_secured_hover_continue,
            region_continue_hover_seconds=args.region_secured_continue_hover_seconds,
            click_region_continue=args.region_secured_click_continue,
            region_continue_click_settle_seconds=(
                args.region_secured_continue_click_settle_seconds
            ),
            region_continue_post_observe_seconds=(
                args.region_secured_post_continue_observe_seconds
            ),
            region_continue_post_visible_poll_seconds=(
                args.region_secured_post_continue_visible_poll_seconds
            ),
            expected_terminal_after_turn=None,
            expected_terminal_visible_poll_seconds=None,
            refresh_paused_bridge_before_auto_turn=True,
            initial_player_ready_snapshot=_compact_bridge_snapshot(initial_bridge),
        )
    region_secured = region_loop.get("region_secured") or {}
    continue_hover = region_loop.get("continue_hover") or {}
    continue_click = region_loop.get("continue_click") or {}
    in_game_timers["region_secured_visible"] = region_secured.get("visible_timer")
    in_game_timers["region_secured_continue_hover_before"] = continue_hover.get(
        "before_in_game_timer"
    )
    in_game_timers["region_secured_continue_hover_frame"] = continue_hover.get(
        "proof_frame_timer"
    )
    in_game_timers["region_secured_continue_click_before"] = continue_click.get(
        "before_in_game_timer"
    )
    in_game_timers["region_secured_continue_click_after"] = continue_click.get(
        "after_frame_timer"
    )
    post_continue_observe = continue_click.get("post_continue_observe") or {}
    post_continue_next = (
        post_continue_observe.get("first_non_region_visible")
        or post_continue_observe.get("first_visible_sample")
        or {}
    )
    in_game_timers["region_secured_post_continue_next_visible"] = (
        post_continue_next.get("visible_timer")
    )
    frame_report = generate_frame_delta_report(telemetry.run_dir)
    status = "PASS" if region_loop.get("status") == "PASS" else "FAIL"
    next_patch = _region_loop_next_patch(region_loop)
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "branch_label": "current_combat",
        "route_slice": route_slice,
        "marks": {"timer_zero": 0.0},
        "in_game_timers": in_game_timers,
        "initial_visible_ui": _compact_visible_snapshot(initial_visible),
        "initial_bridge_snapshot": _compact_bridge_snapshot(initial_bridge),
        "combat_until_region_secured": region_loop,
        "frame_delta_report": frame_report,
        "next_patch": next_patch,
    }
    report["turn_timing_audit"] = build_turn_timing_audit(report)
    report["speed_sequence_expectation"] = evaluate_speed_sequence_expectation(
        report["turn_timing_audit"],
        expected_player_turns=None,
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"{run_id}_region_secured_report.json"
    report["report_path"] = str(report_path)
    report_path.write_text(
        json.dumps(report, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    append_notebook_report(report)
    telemetry.summary(
        status=status,
        reason=next_patch,
        extra={
            "report_path": str(report_path),
            "branch_label": "current_combat",
            "turns_attempted": region_loop.get("turns_attempted"),
        },
    )
    return report


def run_followup_mission_from_island_map(
    *,
    mission_index: int,
    timer_start: float,
    telemetry: TelemetryRecorder,
    screenshots: ScreenshotRecorder,
    args: argparse.Namespace,
    memory_timer_address: int | None,
    memory_live_timer_address: int | None,
    memory_live_timer_kind: str | None,
    deployment_trigger_source: str,
    preview_transition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    telemetry.event(
        "followup_mission_start",
        timer_seconds=_elapsed(timer_start),
        mission_index=mission_index,
    )
    mission_preview: dict[str, Any] | None = None
    mission_timers: dict[str, Any] = {}
    if preview_transition is not None:
        preview_timer = read_in_game_timer(
            profile=args.profile,
            label="mission_preview_after_result_clear",
            use_memory=args.memory_timer_probe,
            timer_address=memory_timer_address,
            live_timer_address=memory_live_timer_address,
            live_timer_kind=memory_live_timer_kind,
        )
        red_region = preview_transition.get("red_region")
        red_detection = {
            "status": "PASS",
            "reason": "mission_preview_opened_by_result_clear",
            "region_count": 1 if isinstance(red_region, dict) else None,
            "selected_region": red_region,
            "result_clear_transition": preview_transition,
        }
        mission_preview = {
            "status": "OK",
            "reason": "mission_preview_opened_by_result_clear",
            "selected_region": red_region,
            "after_preview_timer": preview_timer,
            "result_clear_transition": preview_transition,
        }
        mission_timers["mission_preview_after_result_clear"] = preview_timer
        telemetry.event(
            "followup_mission_preview_opened_by_result_clear",
            timer_seconds=_elapsed(timer_start),
            mission_index=mission_index,
            preview_timer=preview_timer,
            transition_status=preview_transition.get("status"),
        )
    else:
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
            mission_timers["red_map_detected_frame"] = detected_frame_timer
        mission_timers["red_map_detected"] = (
            detected_frame_timer
            if _timer_sample_seconds(detected_frame_timer) is not None
            else red_detection.get("paired_in_game_timer")
        )

    if red_detection.get("status") == "PASS" and mission_preview is None:
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
            pause_after_click=False,
        )
        mission_timers["mission_preview_frame"] = mission_preview.get(
            "preview_frame_timer"
        )
        mission_timers["mission_preview_after_click"] = mission_preview.get(
            "after_preview_timer"
        )

    start_mission: dict[str, Any] | None = None
    if isinstance(mission_preview, dict) and mission_preview.get("status") == "OK":
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
            pause_after_click=False,
            pre_start_visible_probe=args.start_mission_pre_click_probe,
            deployment_trigger_source=deployment_trigger_source,
        )
        mission_timers["start_mission_click_before"] = start_mission.get(
            "before_in_game_timer"
        )
        deployment_visible_samples = [
            sample
            for sample in start_mission.get("samples", [])
            if isinstance(sample, dict) and sample.get("deployment_visible")
        ]
        if deployment_visible_samples:
            mission_timers["deployment_visible_frame"] = deployment_visible_samples[
                0
            ].get("frame_timer")

    deployment_result: dict[str, Any] | None = None
    if isinstance(start_mission, dict) and start_mission.get("status") == "PASS":
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
            pause_after_deploy=False,
            trigger_frame_timer=deployment_trigger_frame_timer,
            capture_post_deploy_probe=False,
        )
        mission_timers["deploy_recommended_before"] = deployment_result.get(
            "before_in_game_timer"
        )
        mission_timers["deploy_recommended_after"] = deployment_result.get(
            "after_in_game_timer"
        )

    confirm_result: dict[str, Any] | None = None
    if isinstance(deployment_result, dict) and deployment_result.get("status") == "PASS":
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
        mission_timers["deploy_confirm_click_before"] = confirm_result.get(
            "before_in_game_timer"
        )
        first_player_ready = confirm_result.get("first_player_ready_bridge") or {}
        mission_timers["opening_player_turn_bridge_ready"] = first_player_ready.get(
            "bridge_timer"
        )

    combat_region_result: dict[str, Any] | None = None
    if isinstance(confirm_result, dict) and confirm_result.get("status") == "PASS":
        combat_region_result = solve_until_region_secured(
            timer_start=timer_start,
            telemetry=telemetry,
            screenshots=screenshots,
            max_turns=args.combat_loop_max_turns,
            auto_turn_time_limit=args.combat_auto_turn_time_limit,
            auto_turn_max_wait=args.combat_auto_turn_max_wait,
            destroy_time_pods=args.destroy_time_pods,
            observe_seconds=args.post_end_turn_observe_seconds,
            screenshot_cadence=args.screenshot_cadence,
            bridge_poll_seconds=args.post_end_turn_bridge_poll_seconds,
            visible_poll_seconds=args.region_secured_visible_poll_seconds,
            terminal_visual_settle_seconds=args.region_secured_terminal_settle_seconds,
            extra_ready_frames=args.post_end_turn_extra_ready_frames,
            pause_after_ready=args.pause_after_combat_player_turn,
            retry_after_seconds=args.end_turn_retry_after_seconds,
            continue_after_fuzzy_block=args.combat_continue_after_fuzzy_block,
            fuzzy_block_min_actions=args.combat_fuzzy_block_min_actions,
            auto_consent_safety_block=getattr(
                args,
                "combat_auto_consent_safety_block",
                True,
            ),
            hover_region_continue=args.region_secured_hover_continue,
            region_continue_hover_seconds=args.region_secured_continue_hover_seconds,
            click_region_continue=args.region_secured_click_continue,
            region_continue_click_settle_seconds=(
                args.region_secured_continue_click_settle_seconds
            ),
            region_continue_post_observe_seconds=(
                args.region_secured_post_continue_observe_seconds
            ),
            region_continue_post_visible_poll_seconds=(
                args.region_secured_post_continue_visible_poll_seconds
            ),
            expected_terminal_after_turn=(
                args.speed_expected_player_turns
                if args.speed_expected_player_turns > 0
                else None
            ),
            expected_terminal_visible_poll_seconds=(
                args.speed_final_turn_visible_poll_seconds
            ),
            refresh_paused_bridge_before_auto_turn=False,
            initial_player_ready_snapshot=(
                (confirm_result.get("first_player_ready_bridge") or {}).get(
                    "snapshot"
                )
            ),
        )
        region_secured = combat_region_result.get("region_secured") or {}
        continue_click = combat_region_result.get("continue_click") or {}
        mission_timers["region_secured_visible"] = region_secured.get(
            "visible_timer"
        )
        mission_timers["region_secured_continue_click_before"] = (
            continue_click.get("before_in_game_timer")
        )
        mission_timers["region_secured_continue_click_after"] = (
            continue_click.get("after_frame_timer")
        )

    status = _mission_status(
        red_detection=red_detection,
        mission_preview=mission_preview,
        start_mission=start_mission,
        deployment_result=deployment_result,
        confirm_result=confirm_result,
        combat_region_result=combat_region_result,
    )
    result = {
        "mission_index": mission_index,
        "status": status,
        "in_game_timers": mission_timers,
        "red_detection": red_detection,
        "mission_preview": mission_preview,
        "start_mission": start_mission,
        "deploy_recommended": deployment_result,
        "deploy_confirm": confirm_result,
        "combat_until_region_secured": combat_region_result,
        "turn_timing_audit": build_turn_timing_audit(
            {
                "in_game_timers": mission_timers,
                "deploy_confirm": confirm_result,
                "combat_until_region_secured": combat_region_result,
            }
        ),
    }
    telemetry.event(
        "followup_mission_result",
        timer_seconds=_elapsed(timer_start),
        mission_index=mission_index,
        status=status,
        reason=(
            (combat_region_result or {}).get("reason")
            if isinstance(combat_region_result, dict)
            else None
        ),
    )
    return result


def run_opening_milestone(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or _now_run_id()
    memory_timer_address = _parse_optional_timer_address(args.memory_timer_address)
    (
        memory_live_timer_address,
        memory_live_timer_kind,
        memory_live_timer_proof_validation,
    ) = _resolve_live_timer_config(args)
    combat_until_region_secured = bool(args.combat_until_region_secured)
    combat_turn_after_confirm = bool(
        args.combat_turn_after_confirm or combat_until_region_secured
    )
    mission_count = max(1, int(args.mission_count or 1))
    confirm_after_deploy = bool(args.confirm_after_deploy or combat_turn_after_confirm)
    deploy_after_visible_deployment = bool(
        args.deploy_after_visible_deployment or confirm_after_deploy
    )
    deployment_trigger_source = str(args.deployment_trigger_source).replace("-", "_")
    if deploy_after_visible_deployment:
        deployment_trigger_source = "screenshot_yellow"
    click_start_mission = bool(args.click_start_mission or deploy_after_visible_deployment)
    click_red_mission = bool(args.click_red_mission or click_start_mission)
    route_slice = (
        (
            f"main_menu_to_archive_red_map_to_{mission_count}_missions"
            if mission_count > 1
            else
            "main_menu_to_archive_red_map_to_region_secured_continue_click"
            if args.region_secured_click_continue
            else "main_menu_to_archive_red_map_to_region_secured_continue_hover"
        )
        if combat_until_region_secured
        else
        "main_menu_to_archive_red_map_to_combat_turn_2_player_ready"
        if combat_turn_after_confirm
        else
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
            "memory_live_timer_proof": _repo_relative_text(
                (memory_live_timer_proof_validation or {}).get("proof_path")
                or args.memory_live_timer_proof
            ),
            "auto_memory_live_timer_proof": args.auto_memory_live_timer_proof,
            "require_memory_live_timer_proof": args.require_memory_live_timer_proof,
            "memory_live_timer_proof_validation": memory_live_timer_proof_validation,
            "click_red_mission": click_red_mission,
            "click_start_mission": click_start_mission,
            "deploy_after_visible_deployment": deploy_after_visible_deployment,
            "confirm_after_deploy": confirm_after_deploy,
            "combat_turn_after_confirm": combat_turn_after_confirm,
            "combat_until_region_secured": combat_until_region_secured,
            "mission_count": mission_count if combat_until_region_secured else None,
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
            "combat_auto_turn_time_limit": (
                args.combat_auto_turn_time_limit
                if combat_turn_after_confirm
                else None
            ),
            "post_end_turn_observe_seconds": (
                args.post_end_turn_observe_seconds
                if combat_turn_after_confirm
                else None
            ),
            "post_end_turn_bridge_poll_seconds": (
                args.post_end_turn_bridge_poll_seconds
                if combat_turn_after_confirm
                else None
            ),
            "combat_continue_after_fuzzy_block": (
                args.combat_continue_after_fuzzy_block
                if combat_turn_after_confirm
                else None
            ),
            "combat_auto_consent_safety_block": (
                getattr(args, "combat_auto_consent_safety_block", True)
                if combat_turn_after_confirm
                else None
            ),
            "destroy_time_pods": (
                args.destroy_time_pods
                if combat_turn_after_confirm
                else None
            ),
            "combat_fuzzy_block_min_actions": (
                args.combat_fuzzy_block_min_actions
                if combat_turn_after_confirm
                else None
            ),
            "combat_loop_max_turns": (
                args.combat_loop_max_turns if combat_until_region_secured else None
            ),
            "region_secured_hover_continue": (
                args.region_secured_hover_continue
                if combat_until_region_secured
                else None
            ),
            "region_secured_click_continue": (
                args.region_secured_click_continue
                if combat_until_region_secured
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
    session_stamp = _stamp_lightning_war_timing_session()
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
        session_stamp=session_stamp,
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
    combat_turn_result: dict[str, Any] | None = None
    combat_region_result: dict[str, Any] | None = None
    additional_missions: list[dict[str, Any]] = []
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
    if (
        combat_until_region_secured
        and isinstance(confirm_result, dict)
        and confirm_result.get("status") == "PASS"
    ):
        combat_region_result = solve_until_region_secured(
            timer_start=timer_start,
            telemetry=telemetry,
            screenshots=screenshots,
            max_turns=args.combat_loop_max_turns,
            auto_turn_time_limit=args.combat_auto_turn_time_limit,
            auto_turn_max_wait=args.combat_auto_turn_max_wait,
            destroy_time_pods=args.destroy_time_pods,
            observe_seconds=args.post_end_turn_observe_seconds,
            screenshot_cadence=args.screenshot_cadence,
            bridge_poll_seconds=args.post_end_turn_bridge_poll_seconds,
            visible_poll_seconds=args.region_secured_visible_poll_seconds,
            terminal_visual_settle_seconds=args.region_secured_terminal_settle_seconds,
            extra_ready_frames=args.post_end_turn_extra_ready_frames,
            pause_after_ready=args.pause_after_combat_player_turn,
            retry_after_seconds=args.end_turn_retry_after_seconds,
            continue_after_fuzzy_block=args.combat_continue_after_fuzzy_block,
            fuzzy_block_min_actions=args.combat_fuzzy_block_min_actions,
            auto_consent_safety_block=getattr(
                args,
                "combat_auto_consent_safety_block",
                True,
            ),
            hover_region_continue=args.region_secured_hover_continue,
            region_continue_hover_seconds=args.region_secured_continue_hover_seconds,
            click_region_continue=args.region_secured_click_continue,
            region_continue_click_settle_seconds=(
                args.region_secured_continue_click_settle_seconds
            ),
            region_continue_post_observe_seconds=(
                args.region_secured_post_continue_observe_seconds
            ),
            region_continue_post_visible_poll_seconds=(
                args.region_secured_post_continue_visible_poll_seconds
            ),
            expected_terminal_after_turn=(
                args.speed_expected_player_turns
                if args.speed_expected_player_turns > 0
                else None
            ),
            expected_terminal_visible_poll_seconds=(
                args.speed_final_turn_visible_poll_seconds
            ),
            refresh_paused_bridge_before_auto_turn=False,
            initial_player_ready_snapshot=(
                (confirm_result.get("first_player_ready_bridge") or {}).get(
                    "snapshot"
                )
            ),
        )
        region_secured = combat_region_result.get("region_secured") or {}
        continue_hover = combat_region_result.get("continue_hover") or {}
        continue_click = combat_region_result.get("continue_click") or {}
        in_game_timers["region_secured_visible"] = region_secured.get(
            "visible_timer"
        )
        in_game_timers["region_secured_continue_hover_before"] = (
            continue_hover.get("before_in_game_timer")
        )
        in_game_timers["region_secured_continue_hover_frame"] = (
            continue_hover.get("proof_frame_timer")
        )
        in_game_timers["region_secured_continue_click_before"] = (
            continue_click.get("before_in_game_timer")
        )
        in_game_timers["region_secured_continue_click_after"] = (
            continue_click.get("after_frame_timer")
        )
        post_continue_observe = continue_click.get("post_continue_observe") or {}
        post_continue_next = (
            post_continue_observe.get("first_non_region_visible")
            or post_continue_observe.get("first_visible_sample")
            or {}
        )
        in_game_timers["region_secured_post_continue_next_visible"] = (
            post_continue_next.get("visible_timer")
        )
    elif (
        combat_turn_after_confirm
        and isinstance(confirm_result, dict)
        and confirm_result.get("status") == "PASS"
    ):
        combat_turn_result = solve_execute_end_turn_and_observe_next_turn(
            timer_start=timer_start,
            telemetry=telemetry,
            screenshots=screenshots,
            auto_turn_time_limit=args.combat_auto_turn_time_limit,
            auto_turn_max_wait=args.combat_auto_turn_max_wait,
            destroy_time_pods=args.destroy_time_pods,
            observe_seconds=args.post_end_turn_observe_seconds,
            screenshot_cadence=args.screenshot_cadence,
            bridge_poll_seconds=args.post_end_turn_bridge_poll_seconds,
            extra_ready_frames=args.post_end_turn_extra_ready_frames,
            pause_after_ready=args.pause_after_combat_player_turn,
            retry_after_seconds=args.end_turn_retry_after_seconds,
            continue_after_fuzzy_block=args.combat_continue_after_fuzzy_block,
            fuzzy_block_min_actions=args.combat_fuzzy_block_min_actions,
            auto_consent_safety_block=getattr(
                args,
                "combat_auto_consent_safety_block",
                True,
            ),
        )
        in_game_timers["combat_auto_turn_before"] = combat_turn_result.get(
            "before_in_game_timer"
        )
        in_game_timers["combat_auto_turn_done"] = combat_turn_result.get(
            "auto_turn_done_timer"
        )
        in_game_timers["combat_end_turn_click_before"] = combat_turn_result.get(
            "end_turn_before_in_game_timer"
        )
        first_left_player = combat_turn_result.get("first_non_player_bridge") or {}
        in_game_timers["combat_end_turn_bridge_left_player"] = first_left_player.get(
            "bridge_timer"
        )
        first_combat_player = combat_turn_result.get("first_player_ready_bridge") or {}
        in_game_timers["combat_post_end_turn_player_ready"] = (
            first_combat_player.get("bridge_timer")
        )
        ready_frame = (
            combat_turn_result.get("first_player_ready_frame_after_bridge") or {}
        )
        in_game_timers["combat_post_end_turn_first_frame_after_bridge"] = (
            ready_frame.get("frame_timer")
        )
        in_game_timers["combat_post_end_turn_after_pause"] = (
            combat_turn_result.get("after_pause_timer")
        )
    if (
        combat_until_region_secured
        and mission_count > 1
        and isinstance(combat_region_result, dict)
        and combat_region_result.get("status") == "PASS"
    ):
        for mission_index in range(2, mission_count + 1):
            result_clear = fast.clear_mission_result_to_island_map(
                mission_index=mission_index - 1,
                timer_start=timer_start,
                continue_after_island=False,
            )
            telemetry.event(
                "followup_mission_result_clear",
                timer_seconds=_elapsed(timer_start),
                mission_index=mission_index,
                status=result_clear.get("status"),
            )
            if result_clear.get("status") != "MISSION_PREVIEW_OPENED":
                additional_missions.append(
                    {
                        "mission_index": mission_index,
                        "status": "FAIL",
                        "reason": "result_clear_did_not_open_mission_preview",
                        "result_clear": result_clear,
                    }
                )
                break
            mission_result = run_followup_mission_from_island_map(
                mission_index=mission_index,
                timer_start=timer_start,
                telemetry=telemetry,
                screenshots=screenshots,
                args=args,
                memory_timer_address=memory_timer_address,
                memory_live_timer_address=memory_live_timer_address,
                memory_live_timer_kind=memory_live_timer_kind,
                deployment_trigger_source=deployment_trigger_source,
                preview_transition=result_clear,
            )
            additional_missions.append(mission_result)
            if mission_result.get("status") != "PASS":
                break
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
    if combat_turn_after_confirm:
        if combat_until_region_secured:
            status = (
                "PASS"
                if status == "PASS"
                and isinstance(combat_region_result, dict)
                and combat_region_result.get("status") == "PASS"
                else "FAIL"
            )
        else:
            status = (
                "PASS"
                if status == "PASS"
                and isinstance(combat_turn_result, dict)
                and combat_turn_result.get("status") == "PASS"
                else "FAIL"
            )
    if status == "PASS" and additional_missions:
        status = (
            "PASS"
            if all(mission.get("status") == "PASS" for mission in additional_missions)
            else "FAIL"
        )
    if status != "PASS":
        next_patch = (
            _region_loop_next_patch(combat_region_result)
            if combat_until_region_secured
            else
            _combat_next_patch(combat_turn_result)
            if combat_turn_after_confirm
            else
            "Fix Confirm click or opening enemy-turn/player-turn detection."
            if confirm_after_deploy
            else
            "Fix deployment placement trigger after deployment-visible screenshot."
            if deploy_after_visible_deployment
            else "Improve Archive intro wait/dismissal or red-region detector."
        )
    elif combat_until_region_secured and mission_count > 1:
        next_patch = (
            f"Learn the next post-mission-{mission_count} island-map route step."
        )
    elif combat_until_region_secured:
        next_patch = _region_loop_next_patch(combat_region_result)
    elif combat_turn_after_confirm:
        next_patch = "Compare combat-turn bridge timing with screenshots; then measure the next combat turn or mission-clear branch."
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
        "combat_turn": combat_turn_result,
        "combat_until_region_secured": combat_region_result,
        "missions": [
            {
                "mission_index": 1,
                "status": _mission_status(
                    red_detection=red_detection,
                    mission_preview=mission_preview,
                    start_mission=start_mission,
                    deployment_result=deployment_result,
                    confirm_result=confirm_result,
                    combat_region_result=combat_region_result,
                ),
                "in_game_timers": in_game_timers,
                "red_detection": red_detection,
                "mission_preview": mission_preview,
                "start_mission": start_mission,
                "deploy_recommended": deployment_result,
                "deploy_confirm": confirm_result,
                "combat_until_region_secured": combat_region_result,
                "turn_timing_audit": build_turn_timing_audit(
                    {
                        "in_game_timers": in_game_timers,
                        "deploy_confirm": confirm_result,
                        "combat_until_region_secured": combat_region_result,
                    }
                ),
            }
        ] + additional_missions,
        "frame_delta_report": frame_report,
        "next_patch": next_patch,
    }
    report["turn_timing_audit"] = build_turn_timing_audit(report)
    report["speed_sequence_expectation"] = evaluate_speed_sequence_expectation(
        report["turn_timing_audit"],
        expected_player_turns=(
            args.speed_expected_player_turns
            if combat_until_region_secured and args.speed_expected_player_turns > 0
            else None
        ),
    )
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
        "--memory-live-timer-proof",
        help=(
            "Session clock proof JSON created by "
            "`itb_timer_memory_probe.py session-clock-proof`; when provided, "
            "the lab validates process identity and uses its address/kind."
        ),
    )
    parser.add_argument(
        "--auto-memory-live-timer-proof",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Automatically use recordings/lightning_session_clock_proof.json "
            "when it exists and --memory-live-timer-proof is not set."
        ),
    )
    parser.add_argument(
        "--require-memory-live-timer-proof",
        action="store_true",
        help=(
            "Fail at startup when neither --memory-live-timer-proof nor the "
            "auto-discovered default proof file is available."
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
    parser.add_argument("--post-confirm-extra-ready-frames", type=int, default=0)
    parser.add_argument(
        "--pause-after-opening-player-turn",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Pause once the bridge reports the first actionable player turn. "
            "Default is on so bridge-ready pauses the in-game clock before "
            "solver thinking."
        ),
    )
    parser.add_argument(
        "--combat-turn-after-confirm",
        action="store_true",
        help=(
            "After the opening player turn is ready, run auto_turn, click End "
            "Turn, and observe the enemy turn back to the next player turn."
        ),
    )
    parser.add_argument(
        "--combat-until-region-secured",
        action="store_true",
        help=(
            "After opening combat, repeat auto_turn + End Turn until the "
            "Region Secured panel appears, hover its Continue button, then "
            "click it unless --no-region-secured-click-continue is set."
        ),
    )
    parser.add_argument(
        "--mission-count",
        type=int,
        default=1,
        help=(
            "When running the full Region Secured route from the main menu, "
            "continue from the island map until this many missions are cleared."
        ),
    )
    parser.add_argument(
        "--current-combat-until-region-secured",
        action="store_true",
        help=(
            "Start from the current live combat/player-turn state instead of "
            "the main menu, and run until Region Secured Continue is handled."
        ),
    )
    parser.add_argument("--combat-auto-turn-time-limit", type=float, default=10.0)
    parser.add_argument("--combat-auto-turn-max-wait", type=float, default=8.0)
    parser.add_argument("--combat-loop-max-turns", type=int, default=6)
    parser.add_argument(
        "--speed-expected-player-turns",
        type=int,
        default=DEFAULT_SPEED_EXPECTED_PLAYER_TURNS,
        help=(
            "Expected player-turn count for the Lightning War short route. "
            "The lab uses this as a speed assumption/report check and falls "
            "back to the dynamic loop if the sequence mismatches."
        ),
    )
    parser.add_argument(
        "--speed-final-turn-visible-poll-seconds",
        type=float,
        default=DEFAULT_SPEED_FINAL_TURN_VISIBLE_POLL_SECONDS,
        help=(
            "Region Secured visible-UI poll cadence on the expected final "
            "player turn."
        ),
    )
    parser.add_argument("--post-end-turn-observe-seconds", type=float, default=30.0)
    parser.add_argument("--post-end-turn-bridge-poll-seconds", type=float, default=0.2)
    parser.add_argument("--post-end-turn-extra-ready-frames", type=int, default=0)
    parser.add_argument("--end-turn-retry-after-seconds", type=float, default=0.75)
    parser.add_argument("--region-secured-visible-poll-seconds", type=float, default=0.5)
    parser.add_argument("--region-secured-terminal-settle-seconds", type=float, default=1.0)
    parser.add_argument("--region-secured-continue-hover-seconds", type=float, default=1.0)
    parser.add_argument(
        "--region-secured-continue-click-settle-seconds",
        type=float,
        default=0.35,
    )
    parser.add_argument(
        "--region-secured-post-continue-observe-seconds",
        type=float,
        default=8.0,
        help=(
            "After clicking Region Secured Continue, passively capture "
            "screenshots and visible UI samples for this many seconds."
        ),
    )
    parser.add_argument(
        "--region-secured-post-continue-visible-poll-seconds",
        type=float,
        default=0.25,
        help="Visible-UI probe cadence during the post-Continue observation.",
    )
    parser.add_argument(
        "--region-secured-hover-continue",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Hover the Region Secured Continue button before any click.",
    )
    parser.add_argument(
        "--region-secured-click-continue",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Click the Region Secured Continue button after the proven hover.",
    )
    parser.add_argument(
        "--combat-continue-after-fuzzy-block",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Lightning War timing-lab policy: if auto_turn completed the full "
            "opening squad action count and only holds End Turn because of a "
            "FUZZY_INVESTIGATE_BLOCKED safety stop, click End Turn anyway and "
            "keep timing the route."
        ),
    )
    parser.add_argument(
        "--combat-fuzzy-block-min-actions",
        type=int,
        default=3,
        help="Minimum completed actions required before the fuzzy-block speedrun skip.",
    )
    parser.add_argument(
        "--combat-auto-consent-safety-block",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Lightning War timing-lab policy: rerun an auto_turn "
            "SAFETY_BLOCKED result with its exact dirty consent token so the "
            "best available action line is executed for speed. Default is on; "
            "Time Pod unrecovered-final blocks still stop."
        ),
    )
    parser.add_argument(
        "--destroy-time-pods",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Enable the Chronophobia pod-destruction combat policy during "
            "Lightning War timing attempts. Default is on to avoid Time Pod "
            "reward/recovery UI."
        ),
    )
    parser.add_argument(
        "--pause-after-combat-player-turn",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Pause once the bridge reports the post-End-Turn player turn. "
            "Default is on so the next solve starts from a paused player turn."
        ),
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
        if args.current_combat_until_region_secured:
            report = run_current_combat_region_secured(args)
        else:
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
