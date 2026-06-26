"""Reliable autonomous Lightning War runner.

This runner is intentionally more conservative than the original speedrun
conductor.  It keeps Python in charge of observable UI transitions, delegates
combat to the existing bridge-backed Lightning segment helper, and stops on
any unresolved safety gate instead of abandoning or making tactical decisions
outside the solver.
"""

from __future__ import annotations

import json
import re
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.capture.save_parser import load_game_state
from src.loop.lightning_conductor import (
    HARD_STOP_TOKENS,
    LIGHTNING_WAR,
    LIGHTNING_WAR_PROFILE_KEY,
    LIGHTNING_WAR_STEAM_KEY,
    RESTARTABLE_ATTEMPT_STOP_TOKENS,
    _achievement_unlocked,
    _compact as _conductor_compact,
    _concrete_session_run_id,
    _load_current_session,
    _must_act_now,
    _safe_to_finalize,
    _safe_to_think,
    _telemetry_run_id,
    _timer_label,
    _timer_seconds,
    _visible_ui_name,
)
from src.loop.lightning_telemetry import (
    ScreenshotRecorder,
    TelemetryRecorder,
    generate_frame_delta_report,
)


BASELINE_STOP_TOKENS = tuple(
    dict.fromkeys(
        HARD_STOP_TOKENS
        + RESTARTABLE_ATTEMPT_STOP_TOKENS
        + (
            "SAFETY_BLOCKED",
            "FAILED_OBJECTIVE",
            "KIA",
            "TIMELINE_COLLAPSE",
            "ROUTE_MISSION_MISMATCH",
            "STALE_HEARTBEAT",
            "STALE_BRIDGE",
            "RESEARCH_REQUIRED",
            "ROUTE_AUTO_START_NOT_ALLOWED",
            "REPEATED_PROGRESS_STATE",
            "EXTERNAL_SYSTEM_PROMPT",
            "DEPLOYMENT_BRIDGE_STATE_UNCERTAIN",
            "VISIBLE_ISLAND_MAP_WITHOUT_BRIDGE",
            "VISIBLE_ISLAND_MAP_WITH_STALE_DEPLOYMENT_BRIDGE",
            "ROUTE_PREVIEW_ACTIVE_MISSION_BEFORE_REGION_CLICK",
            "AMBIGUOUS_ROUTE_START_REGION",
        )
    )
)

DEFAULT_LIGHTNING_MAX_ATTEMPTS = 20
DEFAULT_LIGHTNING_MAX_SEGMENTS = 40
DEFAULT_LIGHTNING_SPEED_SEGMENT_TIMEOUT = 45.0
DEFAULT_LIGHTNING_SPEED_SEGMENT_MAX_WAIT = 18.0
DEFAULT_LIGHTNING_FIRST_ISLAND_SEQUENCE = ("archive", "rst", "pinnacle", "detritus")
DEFAULT_LIGHTNING_SPEED_FIRST_ISLAND_SEQUENCE = ("archive", "detritus", "pinnacle")
_LIGHTNING_FIRST_ISLAND_ALIASES = {
    "archive": "archive",
    "rst": "rst",
    "r.s.t.": "rst",
    "pinnacle": "pinnacle",
    "detritus": "detritus",
}
_LIGHTNING_RESTART_START_REASON_PASSTHROUGH = {
    "external_system_prompt_visible",
    "first_island_selected_mismatch",
    "first_island_selected_unverified",
    "first_mission_start_timer_not_reset",
    "first_mission_start_timer_unverified",
}


def _restart_start_failure_reason(started: dict[str, Any]) -> str:
    start_reason = str(started.get("reason") or "")
    if start_reason in _LIGHTNING_RESTART_START_REASON_PASSTHROUGH:
        return start_reason
    return "restart_start_from_setup_failed"


TERMINAL_UIS = {
    "kia_panel",
}
TERMINAL_OUTCOME_FLAG_KEYS = {
    "defeat_visible",
    "failed_objective_visible",
    "game_over_visible",
    "kia_visible",
    "objective_failure_visible",
    "run_failed_visible",
    "terminal_outcome",
    "terminal_outcome_visible",
    "timeline_lost_visible",
}
TERMINAL_OUTCOME_TEXT_KEYS = {
    "message",
    "objective_text",
    "objective_texts",
    "ocr_text",
    "ocr_texts",
    "panel_text",
    "reward_text",
    "screen_text",
    "subtitle",
    "summary_text",
    "text",
    "title",
    "visible_text",
}
TERMINAL_OUTCOME_PHRASES = (
    "timeline lost",
    "timeline collapse",
    "objective failed",
    "failed objective",
    "(failed)",
    "mission failed",
    "failed mission",
    "killed in action",
    "pilot killed",
    "pilot lost",
    "mech destroyed",
    "mech lost",
    "kia",
)
STOP_SIGN_NEXT_STEPS = {
    "failed_objective_detected": (
        "Stop before more UI or combat commands. The nested segment evidence "
        "reports a failed objective; inspect the screenshot/log evidence and "
        "treat the Lightning War timeline as failed unless a diagnosis proves "
        "the evidence is stale or misclassified."
    ),
    "kia_detected": (
        "Stop before more UI or combat commands. The nested segment evidence "
        "reports KIA/mech-loss terminal state; inspect the visible screen and "
        "session evidence before any recovery click."
    ),
    "bridge_snapshot_unavailable": (
        "Stop before more combat commands. The nested evidence says the bridge "
        "snapshot is unavailable; recover the bridge/window state, then resume "
        "only from a fresh read plus solve."
    ),
    "deployment_bridge_state_uncertain": (
        "Stop before Confirm Deployment or combat commands. Bridge deployment "
        "state is uncertain; preserve the visible/bridge evidence and regain a "
        "verified deployment or map state before clicking."
    ),
    "research_required": (
        "Stop before more live commands. Follow the research gate protocol: "
        "snapshot, run research_next, collect the requested evidence, resolve "
        "the known type, then resume only after the gate is clear."
    ),
    "timeline_collapse_detected": (
        "Stop before more UI or combat commands. The nested segment evidence "
        "reports timeline collapse or timeline lost; inspect the terminal "
        "screen evidence before any recovery click."
    ),
    "repeated_progress_state": (
        "Stop before more UI or combat commands. The lower-level segment "
        "reported repeated progress state; inspect visible/bridge evidence and "
        "resume only after proving the next state from a fresh read/classify."
    ),
    "post_enemy_blocked": (
        "Stop before more combat commands or End Turn clicks. Inspect the "
        "post-enemy evidence, record the cause/fix, and clear the persistent "
        "post-enemy block only after it is understood."
    ),
    "threat_audit_blocked": (
        "Stop before End Turn. Inspect the threat-audit evidence and rerun "
        "from fresh state only after the unresolved threat is understood."
    ),
    "safety_blocked": (
        "Stop before more combat commands. Review the safety/dirty-frontier "
        "evidence; do not continue with dirty-plan consent unless the exact "
        "documented line has been reviewed and authorized."
    ),
    "investigation_required": (
        "Stop before more live commands. Run the investigation or diagnosis "
        "protocol requested by the nested evidence, then resume only after it "
        "is resolved."
    ),
    "mission_preview_requires_route_validation": (
        "Stop before any Start Mission click. A mission-preview board is visible "
        "without verified route proof; regain a verified island-map route "
        "candidate or bridge preview mission id before starting deployment."
    ),
    "stale_bridge_heartbeat": (
        "Stop before more combat commands. Recover the bridge, then resume "
        "from a fresh read plus solve; do not reuse the old partial-turn "
        "solution."
    ),
    "visible_island_map_without_bridge": (
        "Stop before Start Mission. CV sees an island-map-like screen without "
        "live bridge route proof; use fresh classify/save route evidence before "
        "choosing or starting a mission."
    ),
    "visible_island_map_with_stale_deployment_bridge": (
        "Stop before deployment or route clicks. CV sees the island map while "
        "the bridge still looks like deployment; treat the bridge state as "
        "stale and regain fresh classify plus bridge/save route proof."
    ),
    "route_preview_active_mission_before_region_click": (
        "Stop before more route, deployment, or combat commands. The route "
        "preview guard found turn-zero deployment before the region click; "
        "abandon/restart only from verified setup, or inspect the route preview "
        "evidence if no safe retry remains."
    ),
    "ambiguous_route_start_region": (
        "Stop before Start Mission. The visual route region could not be "
        "matched to a verified mission candidate; inspect the map screenshot "
        "and rerun route detection from a fresh paused/classified map."
    ),
}
OBJECTIVE_FAILURE_CONTEXT_WORDS = (
    "block",
    "defend",
    "destroy",
    "evacuate",
    "freeze",
    "kill",
    "knock",
    "mission",
    "protect",
    "rescue",
    "survive",
    "terraform",
)

UNEXPECTED_MENU_UIS = {
    "title_screen",
    "new_game_setup",
    "mech_loadout_screen",
}

RECOVERABLE_PRECOMBAT_ROUTE_GATE_TOKENS = {
    "DEPLOYMENT_BRIDGE_STATE_UNCERTAIN",
    "ROUTE_PREVIEW_ACTIVE_MISSION_BEFORE_REGION_CLICK",
    "VISIBLE_ISLAND_MAP_WITH_STALE_DEPLOYMENT_BRIDGE",
}
RECOVERABLE_PRECOMBAT_ROUTE_GATE_OVERRIDABLE_TOKENS = {
    "BRIDGE_SNAPSHOT_UNAVAILABLE",
    "DEPLOYMENT_BRIDGE_STATE_UNCERTAIN",
    "MISSION_PREVIEW_REQUIRES_ROUTE_VALIDATION",
    "ROUTE_AUTO_START_NOT_ALLOWED",
    "STALE_BRIDGE",
    "STALE_HEARTBEAT",
    "VISIBLE_ISLAND_MAP_WITHOUT_BRIDGE",
    "VISIBLE_ISLAND_MAP_WITH_STALE_DEPLOYMENT_BRIDGE",
}

SYSTEM_BLOCKING_UIS = {
    "system_privacy_prompt",
}

POST_LEAVE_HANDOFF_UIS = {
    "island_map",
    "island_map_or_unknown",
    "bottom_continue_panel",
    "pause_menu",
}
FIRST_ISLAND_PENDING_TAG_PREFIX = "lightning_first_island_clicked:"
FIRST_ISLAND_RESUME_PASSTHROUGH_REASONS = {
    "external_system_prompt_visible",
    "first_island_already_recorded",
    "first_island_click_failed",
    "first_island_pending_save_failed",
    "first_island_selection_pending_unverified",
    "first_island_selection_screen_unverified",
    "first_island_save_state_unverified",
    "first_island_session_index_unreadable",
    "first_island_session_save_failed",
    "first_island_session_unverified",
    "pause_after_first_island_not_verified",
}

COMPLETION_PROOF_UIS = {
    "island_map",
    "island_complete_leave",
    "reward_panel",
    "bottom_continue_panel",
    "pod_open_panel",
    "promotion_panel",
    "perfect_reward_choice",
    "perfect_island_panel",
}

EXPECTED_BLITZKRIEG_MECHS = {
    "ElectricMech",
    "WallMech",
    "RockartMech",
}
EXPECTED_BLITZKRIEG_WEAPONS = {
    "Prime_Lightning",
    "Brute_Grapple",
    "Ranged_Rockthrow",
}

SAFE_PANEL_UIS = {
    "reward_panel",
    "bottom_continue_panel",
    "pod_open_panel",
    "promotion_panel",
    "perfect_reward_choice",
    "perfect_island_panel",
}

STARTUP_HIDDEN_PANEL_UIS = (SAFE_PANEL_UIS - {"mission_preview_panel"}) | {
    "island_complete_leave",
}


OCR_AUDIT_PANEL_UIS = (
    TERMINAL_UIS
    | SAFE_PANEL_UIS
    | SYSTEM_BLOCKING_UIS
    | {
        "island_complete_leave",
        "mission_preview_panel",
    }
)


SEGMENT_SAFE_PANEL_RECOVERY_REASONS = {
    "deployment_visible_ui_not_deployment",
}


def _contains_stale_bridge_heartbeat(value: Any) -> bool:
    return _stale_bridge_heartbeat_evidence(value) is not None


def _stale_bridge_heartbeat_evidence(
    value: Any,
    *,
    path: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    if isinstance(value, str):
        text = value.lower()
        if "bridge heartbeat stale" in text or "lua stopped ticking" in text:
            return {
                "kind": "stale_bridge_heartbeat",
                "path": ".".join(path),
                "text": value[:240],
            }
        return None
    if isinstance(value, dict):
        for key, nested in value.items():
            found = _stale_bridge_heartbeat_evidence(
                nested,
                path=path + (str(key),),
            )
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for index, nested in enumerate(value):
            found = _stale_bridge_heartbeat_evidence(
                nested,
                path=path + (str(index),),
            )
            if found is not None:
                return found
    return None


def _contains_external_system_prompt(value: Any) -> bool:
    return _external_system_prompt_evidence(value) is not None


def _successful_system_prompt_allow_result(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    status = str(value.get("status") or "").upper()
    reason = str(value.get("reason") or "")
    control = str(value.get("control") or "")
    return status == "OK" and (
        reason.startswith("system_privacy_prompt_allow_clicked")
        or control == "macos_privacy_prompt_allow"
    )


def _pause_after_system_prompt_verified(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if str(value.get("status") or "").upper() != "OK":
        return False
    if _safe_to_think(value):
        return True
    if value.get("pause_verified") or value.get("timer_stop_verified"):
        return True
    if value.get("already_paused") is True:
        return True
    if str(value.get("reason") or "") == "already_paused":
        return True
    if str(value.get("reason") or "") == "pause_clicked":
        return value.get("pause_verified") is True
    return _visible_ui_name(value) == "pause_menu"


def _external_system_prompt_evidence(
    value: Any,
    *,
    path: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    if isinstance(value, str):
        if _external_system_prompt_text(value):
            return {
                "kind": "external_system_prompt",
                "path": ".".join(path),
                "text": value[:240],
            }
        return None
    if isinstance(value, dict):
        if _successful_system_prompt_allow_result(value):
            post_click = value.get("post_click_visible_ui")
            if isinstance(post_click, dict):
                return _external_system_prompt_evidence(
                    post_click,
                    path=path + ("post_click_visible_ui",),
                )
            return None
        if (
            value.get("kind") == "macos_screen_audio_privacy_prompt"
            and value.get("matched") is not True
        ):
            return None
        external_prompt = value.get("external_prompt")
        if value.get("requires_user_authorization") is True:
            result = {
                "kind": "external_system_prompt",
                "path": ".".join(path),
                "requires_user_authorization": True,
                "visible_ui": _compact(value),
            }
            if isinstance(external_prompt, dict):
                result["external_prompt"] = _compact_external_prompt(external_prompt)
            return result
        if (
            isinstance(external_prompt, dict)
            and external_prompt.get("matched") is True
        ):
            return {
                "kind": "external_system_prompt",
                "path": ".".join(path + ("external_prompt",)),
                "external_prompt": _compact_external_prompt(external_prompt),
            }
        nested_visible = value.get("visible_ui")
        if (
            isinstance(nested_visible, dict)
            and nested_visible.get("visible_ui") in SYSTEM_BLOCKING_UIS
        ):
            return {
                "kind": "external_system_prompt",
                "path": ".".join(path + ("visible_ui",)),
                "visible_name": str(nested_visible.get("visible_ui")),
                "visible_ui": _compact(nested_visible),
            }
        visible_name = _direct_visible_ui_name(value)
        if visible_name in SYSTEM_BLOCKING_UIS:
            return {
                "kind": "external_system_prompt",
                "path": ".".join(path),
                "visible_name": visible_name,
                "visible_ui": _compact(value),
            }
        for key, nested in value.items():
            if isinstance(nested, str):
                continue
            found = _external_system_prompt_evidence(
                nested,
                path=path + (str(key),),
            )
            if found is not None:
                return found
        for key, nested in value.items():
            if not isinstance(nested, str):
                continue
            found = _external_system_prompt_evidence(
                nested,
                path=path + (str(key),),
            )
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for index, nested in enumerate(value):
            if isinstance(nested, str):
                continue
            found = _external_system_prompt_evidence(
                nested,
                path=path + (str(index),),
            )
            if found is not None:
                return found
        for index, nested in enumerate(value):
            if not isinstance(nested, str):
                continue
            found = _external_system_prompt_evidence(
                nested,
                path=path + (str(index),),
            )
            if found is not None:
                return found
    return None


def _external_system_prompt_visible_ui(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if (
            value.get("kind") == "macos_screen_audio_privacy_prompt"
            and value.get("matched") is not True
        ):
            return None
        external_prompt = value.get("external_prompt")
        if (
            value.get("requires_user_authorization") is True
            or (
                isinstance(external_prompt, dict)
                and external_prompt.get("matched") is True
            )
            or _direct_visible_ui_name(value) in SYSTEM_BLOCKING_UIS
        ):
            return value
        nested_visible = value.get("visible_ui")
        if isinstance(nested_visible, dict):
            found = _external_system_prompt_visible_ui(nested_visible)
            if found is not None:
                return found
        for key, nested in value.items():
            if key == "visible_ui":
                continue
            if isinstance(nested, (dict, list)):
                found = _external_system_prompt_visible_ui(nested)
                if found is not None:
                    return found
    elif isinstance(value, list):
        for nested in value:
            found = _external_system_prompt_visible_ui(nested)
            if found is not None:
                return found
    return None


def _external_system_prompt_text(text: str) -> bool:
    normalized = str(text or "").lower()
    phrases = (
        "macos privacy prompt",
        "macos system prompt",
        "macos screen recording prompt",
        "privacy prompt is covering",
    )
    return any(phrase in normalized for phrase in phrases)


def _solver_or_combat_timeout_evidence(
    value: Any,
    *,
    path: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    if isinstance(value, dict):
        status = str(value.get("status") or "").upper()
        reason = str(value.get("reason") or "")
        if status == "TIMEOUT" and _combat_timeout_reason(reason):
            return {
                "kind": "combat_timeout",
                "path": ".".join(path + ("status",)),
                "status": status,
                "reason": reason,
            }
        for key in ("error", "warning", "message", "next_step"):
            nested = value.get(key)
            if isinstance(nested, str):
                found = _solver_or_combat_timeout_text(
                    nested,
                    path=path + (key,),
                )
                if found is not None:
                    return found
        for key, nested in value.items():
            found = _solver_or_combat_timeout_evidence(
                nested,
                path=path + (str(key),),
            )
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for index, nested in enumerate(value):
            found = _solver_or_combat_timeout_evidence(
                nested,
                path=path + (str(index),),
            )
            if found is not None:
                return found
        return None
    if isinstance(value, str):
        return _solver_or_combat_timeout_text(value, path=path)
    return None


def _solver_or_combat_timeout_text(
    text: str,
    *,
    path: tuple[str, ...],
) -> dict[str, Any] | None:
    lowered = text.lower()
    if "solver returned empty solution" in lowered and "timeout" in lowered:
        return {
            "kind": "solver_timeout",
            "path": ".".join(path),
            "text": text[:240],
        }
    if "empty solution" in lowered and "manual play" in lowered:
        return {
            "kind": "solver_empty_solution",
            "path": ".".join(path),
            "text": text[:240],
        }
    if "solve:" in lowered and "timeout" in lowered:
        return {
            "kind": "solver_timeout",
            "path": ".".join(path),
            "text": text[:240],
        }
    if "player_turn_not_ready" in lowered or "player turn not ready" in lowered:
        return {
            "kind": "combat_timeout",
            "path": ".".join(path),
            "text": text[:240],
        }
    return None


def _lightning_subcall_timeout_evidence(
    value: Any,
    *,
    path: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    timeout_reasons = {
        "attempt_subcall_timeout",
        "lightning_subcall_timeout",
        "route_start_subcall_timeout",
    }
    if isinstance(value, dict):
        reason = str(value.get("reason") or "")
        error = str(value.get("error") or "")
        if reason in timeout_reasons or any(item in error for item in timeout_reasons):
            return {
                "kind": "lightning_subcall_timeout",
                "path": ".".join(path) or "",
                "reason": reason,
                "error": error[:240],
            }
        for key, nested in value.items():
            found = _lightning_subcall_timeout_evidence(
                nested,
                path=path + (str(key),),
            )
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for index, nested in enumerate(value):
            found = _lightning_subcall_timeout_evidence(
                nested,
                path=path + (str(index),),
            )
            if found is not None:
                return found
        return None
    if isinstance(value, str):
        if any(item in value for item in timeout_reasons):
            return {
                "kind": "lightning_subcall_timeout",
                "path": ".".join(path) or "",
                "text": value[:240],
            }
    return None


def _combat_timeout_reason(reason: str) -> bool:
    lowered = reason.lower()
    return (
        "player_turn_not_ready" in lowered
        or "player turn not ready" in lowered
        or "combat" in lowered
        or "solver" in lowered
    )


def _unexpected_menu_evidence(
    value: Any,
    *,
    path: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    if isinstance(value, dict):
        for key in ("visible_ui", "visible_name"):
            nested = value.get(key)
            if isinstance(nested, str) and nested in UNEXPECTED_MENU_UIS:
                return {
                    "kind": "unexpected_menu",
                    "path": ".".join(path + (key,)),
                    "visible_name": nested,
                }
            if isinstance(nested, dict):
                nested_name = nested.get("visible_ui")
                if isinstance(nested_name, str) and nested_name in UNEXPECTED_MENU_UIS:
                    return {
                        "kind": "unexpected_menu",
                        "path": ".".join(path + (key, "visible_ui")),
                        "visible_name": nested_name,
                    }
        for key, nested in value.items():
            found = _unexpected_menu_evidence(nested, path=path + (str(key),))
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for index, nested in enumerate(value):
            found = _unexpected_menu_evidence(nested, path=path + (str(index),))
            if found is not None:
                return found
    return None


def _current_unexpected_menu_evidence(
    value: Any,
    *,
    path: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    """Return menu/setup evidence only from fields that describe the live screen."""
    found = _direct_unexpected_menu_evidence(value, path=path)
    if found is not None:
        return found
    if not isinstance(value, dict):
        return None

    for key in (
        "visible_ui",
        "snapshot",
        "live_snapshot",
        "pause_guard",
        "guard",
        "ensure_pause",
        "pause_verify",
        "last_poll",
    ):
        nested = value.get(key)
        if not isinstance(nested, dict):
            continue
        if key == "pause_guard" and _has_newer_non_menu_visible_evidence(value):
            continue
        found = _current_unexpected_menu_evidence(nested, path=path + (key,))
        if found is not None:
            return found
    return None


def _has_newer_non_menu_visible_evidence(value: dict[str, Any]) -> bool:
    for path in (
        ("resume_guard", "post_click_visible_ui"),
        ("last_attempt", "resume_guard", "post_click_visible_ui"),
    ):
        nested: Any = value
        for key in path:
            if not isinstance(nested, dict):
                nested = None
                break
            nested = nested.get(key)
        visible_name = _direct_visible_ui_name(nested)
        if visible_name is not None and visible_name not in UNEXPECTED_MENU_UIS:
            return True
    return False


def _direct_unexpected_menu_evidence(
    value: Any,
    *,
    path: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    for key in ("visible_ui", "visible_name"):
        nested = value.get(key)
        if isinstance(nested, str) and nested in UNEXPECTED_MENU_UIS:
            return {
                "kind": "unexpected_menu",
                "path": ".".join(path + (key,)),
                "visible_name": nested,
            }
        if isinstance(nested, dict):
            nested_name = nested.get("visible_ui")
            if isinstance(nested_name, str) and nested_name in UNEXPECTED_MENU_UIS:
                return {
                    "kind": "unexpected_menu",
                    "path": ".".join(path + (key, "visible_ui")),
                    "visible_name": nested_name,
                }
    return None


def _stop_token_evidence(
    value: Any,
    tokens: tuple[str, ...],
    *,
    path: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    if isinstance(value, str):
        if _stop_token_string_path_is_ignored(path, value):
            return None
        token = _matching_stop_token(tokens, value)
        if token is not None:
            return {
                "token": token,
                "path": ".".join(path),
                "text": value[:240],
            }
        return None
    if isinstance(value, dict):
        candidates: list[dict[str, Any]] = []
        status = str(value.get("status") or "")
        reason = str(value.get("reason") or "")
        status_reason = f"{status} {reason}".upper()
        if not _stop_token_status_reason_is_ignored(status, reason):
            token = _matching_stop_token(tokens, status_reason)
            if token is not None:
                candidates.append(
                    {
                        "token": token,
                        "path": ".".join(path),
                        "status": status,
                        "reason": reason,
                    }
                )
        for key, nested in value.items():
            found = _stop_token_evidence(
                nested,
                tokens,
                path=path + (str(key),),
            )
            if found is not None:
                candidates.append(found)
        return _best_stop_token_evidence(candidates)
    if isinstance(value, list):
        candidates: list[dict[str, Any]] = []
        for index, nested in enumerate(value):
            found = _stop_token_evidence(
                nested,
                tokens,
                path=path + (str(index),),
            )
            if found is not None:
                candidates.append(found)
        return _best_stop_token_evidence(candidates)
    return None


def _stop_token_string_path_is_ignored(path: tuple[str, ...], value: str) -> bool:
    if not path:
        return False
    if str(path[-1]) in {
        "control",
        "kind",
        "recommended_control",
        "visible_name",
        "visible_ui",
    }:
        return True
    if (
        str(path[-1]) == "reason"
        and str(value) == "stale_bridge_preview_ignored_for_route_scoring"
    ):
        return True
    return False


def _stop_token_status_reason_is_ignored(status: str, reason: str) -> bool:
    return str(reason) == "stale_bridge_preview_ignored_for_route_scoring"


def _best_stop_token_evidence(
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_rank: int | None = None
    best_detail_score = 0
    best_kind_rank = 0
    best_depth = 0
    for candidate in candidates:
        rank = _stop_token_rank(str(candidate.get("token") or ""))
        detail_score = _stop_evidence_detail_score(candidate)
        kind_rank = _stop_evidence_kind_rank(candidate)
        depth = _stop_evidence_path_depth(candidate)
        if best is None or best_rank is None or rank < best_rank:
            best = candidate
            best_rank = rank
            best_detail_score = detail_score
            best_kind_rank = kind_rank
            best_depth = depth
            continue
        if rank != best_rank:
            continue
        if detail_score > best_detail_score:
            best = candidate
            best_detail_score = detail_score
            best_kind_rank = kind_rank
            best_depth = depth
            continue
        if detail_score != best_detail_score:
            continue
        if kind_rank < best_kind_rank:
            best = candidate
            best_kind_rank = kind_rank
            best_depth = depth
            continue
        if kind_rank == best_kind_rank and detail_score > 0 and depth > best_depth:
            best = candidate
            best_depth = depth
    return best


def _stop_evidence_kind_rank(candidate: dict[str, Any]) -> int:
    if "status" in candidate or "reason" in candidate:
        return 0
    if "text" in candidate:
        return 1
    return 2


def _stop_evidence_detail_score(candidate: dict[str, Any]) -> int:
    token = str(candidate.get("token") or "")
    score = 0
    for key in ("reason", "text", "status"):
        value = str(candidate.get(key) or "")
        if _stop_evidence_value_is_detail(token, value):
            score += 1
    return score


def _stop_evidence_value_is_detail(token: str, value: str) -> bool:
    normalized = _normalize_stop_token_text(value)
    if not normalized:
        return False
    if normalized in _GENERIC_STOP_EVIDENCE_VALUES:
        return False
    aliases = set(_stop_token_aliases(token))
    if normalized in aliases:
        return False
    for alias in aliases:
        suffix = f"{alias}_"
        if normalized.startswith(suffix):
            remainder = normalized[len(suffix) :]
            return remainder not in _GENERIC_STOP_EVIDENCE_SUFFIXES
    return True


def _stop_evidence_path_depth(candidate: dict[str, Any]) -> int:
    path = str(candidate.get("path") or "")
    if not path:
        return 0
    return len([part for part in path.split(".") if part])


def _matching_stop_token(tokens: tuple[str, ...], text: str) -> str | None:
    matches = [token for token in tokens if _stop_token_in_text(token, text)]
    if not matches:
        return None
    for token in _STOP_TOKEN_SPECIFIC_PRIORITY:
        if token in matches:
            return token
    return matches[0]


_STOP_TOKEN_SPECIFIC_PRIORITY = (
    "FAILED_OBJECTIVE",
    "KIA",
    "TIMELINE_COLLAPSE",
    "POST_ENEMY",
    "THREAT_AUDIT",
    "SAFETY_BLOCKED",
    "RESEARCH_REQUIRED",
    "DESYNC",
    "STALE_HEARTBEAT",
    "STALE_BRIDGE",
    "BRIDGE_SNAPSHOT_UNAVAILABLE",
    "MISSION_PREVIEW_REQUIRES_ROUTE_VALIDATION",
    "DEPLOYMENT_BRIDGE_STATE_UNCERTAIN",
    "VISIBLE_ISLAND_MAP_WITHOUT_BRIDGE",
    "VISIBLE_ISLAND_MAP_WITH_STALE_DEPLOYMENT_BRIDGE",
    "ROUTE_PREVIEW_ACTIVE_MISSION_BEFORE_REGION_CLICK",
    "AMBIGUOUS_ROUTE_START_REGION",
    "INVESTIGATE",
)


_GENERIC_STOP_EVIDENCE_VALUES = {
    "BLOCKED",
    "ERROR",
    "FAIL",
    "FAILED",
    "LIGHTNING_SEGMENT_STOPPED",
    "SEGMENT_STOPPED",
}

_GENERIC_STOP_EVIDENCE_SUFFIXES = {
    "BLOCKED",
    "DETECTED",
    "VISIBLE",
}


def _stop_token_rank(token: str) -> int:
    normalized = _normalize_stop_token_text(token)
    try:
        return _STOP_TOKEN_SPECIFIC_PRIORITY.index(normalized)
    except ValueError:
        return len(_STOP_TOKEN_SPECIFIC_PRIORITY)


def _stop_token_in_text(token: str, text: str) -> bool:
    aliases = _stop_token_aliases(token)
    if not aliases:
        return False
    variants = {
        str(text or "").upper(),
        _normalize_stop_token_text(text),
    }
    for alias in aliases:
        for variant in variants:
            if re.search(
                rf"(?<![A-Z0-9]){re.escape(alias)}(?![A-Z0-9])",
                variant,
            ):
                return True
    return False


def _stop_token_aliases(token: str) -> tuple[str, ...]:
    normalized_token = _normalize_stop_token_text(token)
    if not normalized_token:
        return ()
    aliases = [normalized_token]
    aliases_by_token = {
        "FAILED_OBJECTIVE": ("OBJECTIVE_FAILED",),
        "KIA": ("K_I_A", "KILLED_IN_ACTION", "PILOT_LOST", "MECH_LOST"),
        "RESEARCH_REQUIRED": ("REQUIRES_RESEARCH",),
        "TIMELINE_COLLAPSE": ("TIMELINE_LOST",),
    }
    aliases.extend(aliases_by_token.get(normalized_token, ()))
    return tuple(dict.fromkeys(aliases))


def _normalize_stop_token_text(text: Any) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", str(text or "").upper())
    return normalized.strip("_")


def _stop_sign_block_reason(
    token: str | None,
    warning: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> str | None:
    parts = [token or "", warning or ""]
    if isinstance(evidence, dict):
        parts.append(str(evidence.get("status") or ""))
        parts.append(str(evidence.get("reason") or ""))
        parts.append(str(evidence.get("text") or ""))
    text = " ".join(parts).lower().replace("-", "_")
    if "failed_objective" in text or "objective loss" in text:
        return "failed_objective_detected"
    if (
        "timeline_collapse" in text
        or "timeline collapse" in text
        or "timeline_lost" in text
        or "timeline lost" in text
    ):
        return "timeline_collapse_detected"
    if (
        re.search(r"(?<![a-z0-9])kia(?![a-z0-9])", text)
        or "killed_in_action" in text
        or "killed in action" in text
        or "pilot killed" in text
        or "pilot_lost" in text
        or "pilot lost" in text
        or "mech destroyed" in text
        or "mech_lost" in text
        or "mech lost" in text
    ):
        return "kia_detected"
    if "bridge_snapshot_unavailable" in text:
        return "bridge_snapshot_unavailable"
    if "repeated_progress_state" in text:
        return "repeated_progress_state"
    if "mission_preview_requires_route_validation" in text:
        return "mission_preview_requires_route_validation"
    if "stale_heartbeat" in text or "stale_bridge" in text:
        return "stale_bridge_heartbeat"
    if "deployment_bridge_state_uncertain" in text:
        return "deployment_bridge_state_uncertain"
    if "visible_island_map_with_stale_deployment_bridge" in text:
        return "visible_island_map_with_stale_deployment_bridge"
    if "visible_island_map_without_bridge" in text:
        return "visible_island_map_without_bridge"
    if "route_preview_active_mission_before_region_click" in text:
        return "route_preview_active_mission_before_region_click"
    if "ambiguous_route_start_region" in text:
        return "ambiguous_route_start_region"
    if "research_required" in text or "requires_research" in text:
        return "research_required"
    if "post_enemy" in text:
        return "post_enemy_blocked"
    if "threat_audit" in text:
        return "threat_audit_blocked"
    if "safety_blocked" in text:
        return "safety_blocked"
    if "investigate" in text:
        return "investigation_required"
    return None


def _stop_sign_next_step(reason: str) -> str | None:
    return STOP_SIGN_NEXT_STEPS.get(reason)


def _segment_failure_evidence(segment: Any) -> dict[str, Any] | None:
    if not isinstance(segment, dict):
        return {
            "status": "ERROR",
            "reason": "segment_returned_non_dict",
            "value_type": type(segment).__name__,
        }
    status = str(segment.get("status") or "")
    normalized = status.upper()
    if normalized not in {"ERROR", "FAIL", "FAILED", "BLOCKED"}:
        return None
    evidence = {
        "status": status,
        "reason": str(segment.get("reason") or ""),
    }
    for key in (
        "error",
        "message",
        "visible_ui",
        "screenshot_path",
        "span",
        "value_type",
        "value_repr",
    ):
        if key in segment:
            evidence[key] = _compact(segment[key])
    return evidence


def _terminal_outcome_evidence(
    value: Any,
    *,
    path: tuple[str, ...] = (),
    text_context: bool = False,
) -> dict[str, Any] | None:
    """Find explicit terminal/failure evidence in CV/OCR payloads."""
    if isinstance(value, dict):
        structured_failure = _structured_objective_failure_evidence(
            value,
            path=path,
        )
        if structured_failure is not None:
            return structured_failure
        split_failure = _split_objective_failure_evidence(value, path=path)
        if split_failure is not None:
            return split_failure
        for key in TERMINAL_OUTCOME_FLAG_KEYS:
            flag_evidence = _terminal_flag_value_evidence(
                key,
                value.get(key),
                path=path + (key,),
            )
            if flag_evidence is not None:
                return flag_evidence
        for key, nested in value.items():
            key_text = str(key)
            child_text_context = (
                text_context
                or key_text in TERMINAL_OUTCOME_TEXT_KEYS
                or key_text.endswith("_text")
                or key_text.endswith("_texts")
                or _terminal_generic_text_key_has_context(
                    key_text,
                    path=path,
                    container=value,
                )
            )
            found = _terminal_outcome_evidence(
                nested,
                path=path + (key_text,),
                text_context=child_text_context,
            )
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for index, nested in enumerate(value):
            found = _terminal_outcome_evidence(
                nested,
                path=path + (str(index),),
                text_context=text_context,
            )
            if found is not None:
                return found
        return None
    if isinstance(value, str) and text_context:
        text = value.strip()
        match = _terminal_outcome_text_match(text)
        if match is not None:
            return {
                "kind": "terminal_text",
                "path": ".".join(path),
                **match,
                "text": text[:240],
            }
    return None


def _terminal_visible_ui_evidence(
    value: Any,
    *,
    path: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    visible_name = value.get("visible_ui")
    if not isinstance(visible_name, str) or visible_name not in TERMINAL_UIS:
        return None
    if value.get("terminal_panel_false_positive") is True:
        return None
    if _terminal_visible_ui_has_clean_text_audit(value):
        return None
    return {
        "kind": "terminal_visible_ui",
        "path": ".".join(path + ("visible_ui",)),
        "visible_ui": visible_name,
    }


def _terminal_visible_ui_has_clean_text_audit(value: dict[str, Any]) -> bool:
    ocr = value.get("ocr")
    if isinstance(ocr, dict):
        return ocr.get("status") == "OK"
    if "ocr" in value:
        return True
    return any(
        key in value
        for key in (
            "ocr_text",
            "ocr_texts",
            "panel_text",
            "reward_text",
            "screen_text",
            "text",
            "visible_text",
        )
    )


def _terminal_generic_text_key_has_context(
    key_text: str,
    *,
    path: tuple[str, ...],
    container: dict[str, Any],
) -> bool:
    if key_text.lower() not in {"texts", "lines"}:
        return False
    parent_hints = {"ocr", "vision", "visible_text", "screen_text", "panel_text"}
    if any(str(part).lower() in parent_hints for part in path):
        return True
    visible_name = container.get("visible_ui")
    if isinstance(visible_name, str) and visible_name in (
        SAFE_PANEL_UIS | {"island_map", "island_map_or_unknown", "kia_panel"}
    ):
        return True
    return False


def _terminal_flag_value_evidence(
    key: str,
    value: Any,
    *,
    path: tuple[str, ...],
) -> dict[str, Any] | None:
    if value is True:
        return {
            "kind": "terminal_flag",
            "path": ".".join(path),
            "flag": key,
        }
    if value is False or value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 0:
            return None
        return {
            "kind": "terminal_flag",
            "path": ".".join(path),
            "flag": key,
            "value": value,
        }
    if not isinstance(value, str):
        return None
    text = value.strip()
    normalized = _normalize_stop_token_text(text).lower()
    if normalized in _NEGATIVE_TERMINAL_FLAG_VALUES:
        return None
    match = _terminal_outcome_text_match(text) or _terminal_outcome_text_match(
        normalized.replace("_", " ")
    )
    evidence: dict[str, Any] = {
        "kind": "terminal_flag",
        "path": ".".join(path),
        "flag": key,
        "value": text[:240],
    }
    if match is not None:
        evidence.update(match)
        return evidence
    if normalized in _AFFIRMATIVE_TERMINAL_FLAG_VALUES or key == "terminal_outcome":
        return evidence
    return None


_NEGATIVE_TERMINAL_FLAG_VALUES = {
    "",
    "0",
    "false",
    "none",
    "no",
    "not_visible",
    "ok",
    "clean",
    "clear",
}

_AFFIRMATIVE_TERMINAL_FLAG_VALUES = {
    "1",
    "true",
    "yes",
    "visible",
    "detected",
    "present",
    "blocked",
}


def _split_objective_failure_evidence(
    value: dict[str, Any],
    *,
    path: tuple[str, ...],
) -> dict[str, Any] | None:
    for key, nested in value.items():
        key_text = str(key)
        if not isinstance(nested, list):
            continue
        if not (
            key_text in TERMINAL_OUTCOME_TEXT_KEYS
            or key_text.endswith("_texts")
            or "objective" in key_text.lower()
            or _terminal_generic_text_key_has_context(
                key_text,
                path=path,
                container=value,
            )
        ):
            continue
        text_rows = [str(item).strip() if isinstance(item, str) else "" for item in nested]
        for index, text in enumerate(text_rows):
            if not _standalone_failure_marker(text):
                continue
            context = _nearest_failure_context(text_rows, index)
            if context is None:
                continue
            context_index, context_text = context
            if "objective" not in key_text.lower() and not _objective_context_text(
                context_text
            ):
                continue
            return {
                "kind": "split_objective_failure_text",
                "path": ".".join(path + (key_text, str(index))),
                "phrase": "failed",
                "context": "split_objective_text",
                "context_path": ".".join(path + (key_text, str(context_index))),
                "context_text": context_text[:240],
                "text": text[:240],
            }
    return None


def _standalone_failure_marker(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "").strip()).lower()
    normalized = normalized.strip(" \t\r\n:;,.![]{}")
    return normalized in {"failed", "(failed)", "failure", "(failure)"}


def _nearest_failure_context(
    text_rows: list[str],
    index: int,
) -> tuple[int, str] | None:
    for offset in (1, 2):
        for context_index in (index - offset, index + offset):
            if context_index < 0 or context_index >= len(text_rows):
                continue
            context_text = text_rows[context_index].strip()
            if not context_text or _standalone_failure_marker(context_text):
                continue
            return context_index, context_text
    return None


def _objective_context_text(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(word in lowered for word in OBJECTIVE_FAILURE_CONTEXT_WORDS)


def _structured_objective_failure_evidence(
    value: dict[str, Any],
    *,
    path: tuple[str, ...],
) -> dict[str, Any] | None:
    if not _objective_path_context(path):
        return None
    for key, nested in value.items():
        key_text = str(key)
        key_lower = key_text.lower()
        if (
            key_lower in {"failed", "objective_failed"}
            or key_lower.endswith("_failed")
        ) and nested is True:
            return {
                "kind": "objective_failure_field",
                "path": ".".join(path + (key_text,)),
                "field": key_text,
            }
        if (
            key_lower in {"status", "state", "result", "outcome"}
            and isinstance(nested, str)
            and nested.strip().lower() in {"failed", "failure", "lost"}
        ):
            return {
                "kind": "objective_failure_field",
                "path": ".".join(path + (key_text,)),
                "field": key_text,
                "value": nested,
            }
    return None


def _objective_path_context(path: tuple[str, ...]) -> bool:
    return any(
        "objective" in part.lower() or part.lower() == "objectives"
        for part in path
    )


def _terminal_outcome_text_match(text: str) -> dict[str, str] | None:
    lowered = text.lower()
    for phrase in TERMINAL_OUTCOME_PHRASES:
        if _terminal_phrase_in_text(lowered, phrase):
            return {"phrase": phrase}
    if "failed" not in lowered:
        return None
    if _objective_context_text(lowered):
        return {"phrase": "failed", "context": "objective_text"}
    return None


def _terminal_phrase_in_text(lowered_text: str, phrase: str) -> bool:
    if phrase == "kia":
        return bool(re.search(r"(?<![a-z0-9])k\.?i\.?a\.?(?![a-z0-9])", lowered_text))
    return phrase in lowered_text


def _live_snapshot_is_actionable_combat(snapshot: Any) -> bool:
    if not isinstance(snapshot, dict) or snapshot.get("status") != "OK":
        return False
    if snapshot.get("phase") != "combat_player":
        return False
    if snapshot.get("in_active_mission") is not True:
        return False
    try:
        return int(snapshot.get("active_mechs") or 0) > 0
    except (TypeError, ValueError):
        return False


def _guard_is_hot_combat_start(guard: dict[str, Any] | None) -> bool:
    if not isinstance(guard, dict):
        return False
    candidates = [guard]
    last_poll = guard.get("last_poll")
    if isinstance(last_poll, dict):
        candidates.append(last_poll)
    for candidate in candidates:
        if candidate.get("reason") != "live_combat_phase":
            continue
        if _live_snapshot_is_actionable_combat(candidate.get("live_snapshot")):
            return True
        decision = candidate.get("decision")
        if isinstance(decision, dict) and decision.get("reason") == "live_combat_phase":
            visible = candidate.get("visible_ui")
            if _visible_refines_to_live_combat(visible):
                return True
    return False


def _visible_refines_to_live_combat(visible: Any) -> bool:
    if not isinstance(visible, dict) or visible.get("status") != "OK":
        return False
    if visible.get("visible_ui") == "combat_screen":
        return True
    refine = visible.get("bridge_refine_snapshot")
    if isinstance(refine, dict) and _live_snapshot_is_actionable_combat(refine):
        return True
    return False


def _direct_visible_ui_name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    visible = value.get("visible_ui")
    if isinstance(visible, str) and visible:
        return visible
    if isinstance(visible, dict) and visible.get("visible_ui"):
        return str(visible["visible_ui"])
    return None


def _safe_panel_evidence_visible_name(value: Any) -> str | None:
    if isinstance(value, dict):
        visible_name = _direct_visible_ui_name(value)
        if visible_name in SAFE_PANEL_UIS or visible_name == "island_complete_leave":
            return visible_name
        for key, nested in value.items():
            if key in {"pause_guard", "guard", "ensure_pause", "resume_guard"}:
                continue
            found = _safe_panel_evidence_visible_name(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _safe_panel_evidence_visible_name(nested)
            if found:
                return found
    return None


def _has_verified_pause_resting_state(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("pause_verified") or value.get("timer_stop_verified"):
        return True
    for key in ("pause_verify", "visible_ui"):
        visible = value.get(key)
        if isinstance(visible, dict) and visible.get("visible_ui") == "pause_menu":
            return True
    for key in ("guard", "pause_guard", "resume_guard", "ensure_pause", "last_poll"):
        if _has_verified_pause_resting_state(value.get(key)):
            return True
    return False


def _iter_nested_dicts(value: Any):
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            yield item
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)


def _has_pause_timer_or_menu_evidence(value: Any) -> bool:
    if _has_verified_pause_resting_state(value):
        return True
    for item in _iter_nested_dicts(value):
        if item.get("source") == "visible_pause_menu_timer":
            return True
        if item.get("timeline_label_seen") is True:
            return True
        visible = item.get("visible_ui") or item.get("pause_verify")
        if isinstance(visible, dict) and visible.get("visible_ui") == "pause_menu":
            return True
        scores = item.get("scores")
        if isinstance(scores, dict):
            pause_score = scores.get("pause_menu")
            if isinstance(pause_score, dict) and _safe_float(pause_score.get("score")) >= 0.35:
                return True
    return False


def _has_active_mission_deployment_evidence(value: Any) -> bool:
    for item in _iter_nested_dicts(value):
        if (
            item.get("in_active_mission") is True
            and _safe_int(item.get("deployment_zone_count")) > 0
            and _safe_int(item.get("active_mechs")) <= 0
        ):
            return True
        underlay = item.get("paused_deployment_underlay")
        if isinstance(underlay, dict) and (
            underlay.get("active_mission_under_pause") is True
            and _safe_int(underlay.get("signal_count")) >= 3
        ):
            return True
        if (
            item.get("active_mission_under_pause") is True
            and _safe_int(item.get("signal_count")) >= 3
        ):
            return True
    return False


def _paused_active_mission_deployment_handoff(value: Any) -> bool:
    return _has_pause_timer_or_menu_evidence(value) and _has_active_mission_deployment_evidence(value)


def _segment_visible_deployment_handoff(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return (
        str(value.get("reason") or "") == "deployment_visible_ui_not_deployment"
        and str(value.get("visible_ui") or "") == "deployment_screen"
    )


def _startup_hidden_panel_name(guard: dict[str, Any] | None) -> str | None:
    visible_name = _direct_visible_ui_name(guard)
    if visible_name not in STARTUP_HIDDEN_PANEL_UIS:
        return None
    if not _has_verified_pause_resting_state(guard):
        return None
    return visible_name


def _needs_first_island_selection_resume(
    session: Any,
    visible_name: str | None,
    *,
    hot_combat_start: bool,
) -> bool:
    """Detect a post-setup-start run that stopped before the first island click."""
    if hot_combat_start or visible_name != "island_map_or_unknown":
        return False
    if str(getattr(session, "current_island", "") or "").strip():
        return False
    if str(getattr(session, "current_mission", "") or "").strip():
        return False
    if _completed_islands(session):
        return False
    try:
        mission_index = int(getattr(session, "mission_index", 0) or 0)
    except (TypeError, ValueError):
        return False
    return mission_index == 0


def _needs_recorded_first_island_selection_confirm(
    session: Any,
    visible_name: str | None,
    *,
    hot_combat_start: bool,
) -> bool:
    """Detect a save-recorded island that still needs a visible picker confirm."""
    if hot_combat_start or visible_name != "island_map_or_unknown":
        return False
    if str(getattr(session, "current_mission", "") or "").strip():
        return False
    if _completed_islands(session):
        return False
    try:
        mission_index = int(getattr(session, "mission_index", 0) or 0)
    except (TypeError, ValueError):
        return False
    return mission_index == 0


def _has_pending_first_island_click(session: Any) -> bool:
    return any(
        str(tag).startswith(FIRST_ISLAND_PENDING_TAG_PREFIX)
        for tag in (getattr(session, "tags", []) or [])
    )


def _needs_pending_first_island_confirmation(
    session: Any,
    *,
    hot_combat_start: bool,
) -> bool:
    if hot_combat_start or not _has_pending_first_island_click(session):
        return False
    if str(getattr(session, "current_island", "") or "").strip():
        return False
    if str(getattr(session, "current_mission", "") or "").strip():
        return False
    if _completed_islands(session):
        return False
    try:
        mission_index = int(getattr(session, "mission_index", 0) or 0)
    except (TypeError, ValueError):
        return False
    return mission_index == 0


def _first_island_resume_finish_reason(result: dict[str, Any]) -> str:
    reason = str(result.get("reason") or "")
    if reason in FIRST_ISLAND_RESUME_PASSTHROUGH_REASONS:
        return reason
    return "first_island_selection_failed"


@dataclass
class LightningRunnerConfig:
    profile: str = "Alpha"
    achievement: str = LIGHTNING_WAR
    mode: str = "baseline"
    target_islands: int = 2
    advanced_content: str = "off"
    difficulty: int = 0
    first_island: str = "archive"
    max_attempts: int = DEFAULT_LIGHTNING_MAX_ATTEMPTS
    max_segments: int = DEFAULT_LIGHTNING_MAX_SEGMENTS
    segment_steps: int = 12
    time_limit: float | None = None
    max_wall_seconds: float | None = None
    segment_timeout: float = 420.0
    abandon_seconds: float = 29 * 60
    mission_segment_gate_seconds: float = 3 * 60
    first_mission_route_start_gate_seconds: float = 45
    first_island_gate_seconds: float = 15 * 60
    second_island_start_gate_seconds: float = 16.75 * 60
    screenshot_cadence: float = 2.0
    collect_screenshot_cadence: float = 2.0
    race_screenshot_cadence: float = 5.0
    iteration_mode: str = "flipflop"
    screenshots: bool = True
    route_auto_start: bool = True
    route_start_mode: str = "preview-board"
    route_speed_vetoes: bool | None = None
    allow_objective_loss: bool = False
    lightning_speed_loss_policy: bool = False
    pause_before_solve: bool = True
    pause_between_actions: bool = False
    start_from_verified_setup: bool = False
    achievement_sync: bool = True
    dry_run: bool = False

    @property
    def speed_mode(self) -> bool:
        return self.mode == "speed" or bool(self.lightning_speed_loss_policy)

    @property
    def combat_time_limit(self) -> float:
        if self.time_limit is not None:
            return float(self.time_limit)
        return 2.0 if self.speed_mode else 10.0

    @property
    def segment_max_wait(self) -> float:
        return DEFAULT_LIGHTNING_SPEED_SEGMENT_MAX_WAIT if self.speed_mode else 45.0

    @property
    def segment_wall_timeout(self) -> float:
        if self.max_wall_seconds is not None:
            return float(self.max_wall_seconds)
        if self.speed_mode and float(self.segment_timeout) == 420.0:
            return DEFAULT_LIGHTNING_SPEED_SEGMENT_TIMEOUT
        return float(self.segment_timeout)

    @property
    def route_routing(self) -> str:
        return "lightning_war" if self.speed_mode else "lightning_baseline"

    @property
    def effective_route_speed_vetoes(self) -> bool:
        if self.route_speed_vetoes is None:
            return False
        return bool(self.route_speed_vetoes)

    @property
    def auto_clear_panels(self) -> bool:
        # The baseline owns panel clearing so it can enforce grid-first shop.
        # Speed mode keeps the same shop interception by default; this can be
        # relaxed only after timing evidence shows it is safe.
        return False


class LightningWarRunner:
    def __init__(self, config: LightningRunnerConfig) -> None:
        self.config = config
        self.telemetry: TelemetryRecorder | None = None
        self.screenshots: ScreenshotRecorder | None = None
        self.telemetry_event_errors: list[dict[str, Any]] = []
        self._active_iteration_phase: str | None = None
        self._active_iteration_attempt: int | None = None
        self.route_probe_cache: list[dict[str, Any]] = []
        self._route_probe_cache_rehydrated = False

    def _iteration_phase_for_attempt(self, attempt_index: int) -> str:
        mode = str(self.config.iteration_mode or "manual").strip().lower()
        if mode == "flipflop":
            return "collect" if int(attempt_index) % 2 == 1 else "race"
        if mode in {"collect", "race"}:
            return mode
        return "manual"

    def _screenshot_cadence_for_phase(self, phase: str) -> float:
        if phase == "collect":
            return float(self.config.collect_screenshot_cadence)
        if phase == "race":
            return float(self.config.race_screenshot_cadence)
        return float(self.config.screenshot_cadence)

    def _activate_iteration_phase(self, attempt_index: int) -> str:
        phase = self._iteration_phase_for_attempt(attempt_index)
        if (
            phase == self._active_iteration_phase
            and int(attempt_index) == self._active_iteration_attempt
        ):
            return phase
        self._active_iteration_phase = phase
        self._active_iteration_attempt = int(attempt_index)
        cadence = self._screenshot_cadence_for_phase(phase)
        if self.screenshots is not None:
            self.screenshots.set_cadence(cadence)
        event_error = self._best_effort_event(
            "iteration_phase",
            attempt_index=attempt_index,
            phase=phase,
            iteration_mode=self.config.iteration_mode,
            screenshot_cadence=cadence,
            mode=self.config.mode,
            speed_mode=self.config.speed_mode,
        )
        if event_error is not None:
            self.telemetry_event_errors.append(event_error)
        return phase

    def _current_screenshot_cadence(self) -> float:
        phase = self._active_iteration_phase or self._iteration_phase_for_attempt(
            self._active_iteration_attempt or 1,
        )
        return self._screenshot_cadence_for_phase(phase)

    def _click_system_prompt_allow(
        self,
        guard: dict[str, Any],
        *,
        commands: Any | None = None,
    ) -> dict[str, Any]:
        visible_ui = _external_system_prompt_visible_ui(guard)
        if visible_ui is None:
            return {
                "status": "ERROR",
                "reason": "system_prompt_visible_ui_missing",
            }
        nested_visible_ui = visible_ui.get("visible_ui")
        if isinstance(nested_visible_ui, dict):
            visible_ui = nested_visible_ui
        try:
            helper = getattr(commands, "_lightning_click_system_privacy_prompt_allow", None)
            if helper is None:
                if commands is not None:
                    return {
                        "status": "ERROR",
                        "reason": "system_prompt_allow_helper_missing",
                    }
                from src.loop import commands as commands_module

                helper = commands_module._lightning_click_system_privacy_prompt_allow
        except Exception as exc:
            return {
                "status": "ERROR",
                "reason": "system_prompt_allow_helper_import_failed",
                "exception_type": type(exc).__name__,
                "error": str(exc),
            }
        try:
            return helper(
                visible_ui,
                dry_run=self.config.dry_run,
            )
        except Exception as exc:
            return {
                "status": "ERROR",
                "reason": "system_prompt_allow_helper_exception",
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }

    def run(self) -> dict[str, Any]:
        from src.loop import commands

        startup_session_block: dict[str, Any] | None = None
        try:
            session = _load_current_session(commands)
            telemetry_run_id = _telemetry_run_id(session)
        except Exception as exc:
            session = None
            telemetry_run_id = "lightning_war_session_load_failed"
            startup_session_block = {
                "status": "BLOCKED",
                "reason": "session_load_exception",
                "stage": "run_start",
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The Lightning runner could not read active session state "
                    "at startup. Preserve the traceback and visible evidence; "
                    "do not trust stale island progress until the session read "
                    "succeeds."
                ),
            }
        try:
            self.telemetry = TelemetryRecorder(telemetry_run_id)
            self.telemetry.write_manifest(self._manifest_payload(session))
            self.telemetry.event(
                "runner_start",
                status="STARTED",
                session=_session_summary(session),
            )
        except Exception as exc:
            self.telemetry = None
            return {
                "status": "BLOCKED",
                "reason": "telemetry_start_exception",
                "mode": self.config.mode,
                "target_islands": self.config.target_islands,
                "telemetry_run_id": telemetry_run_id,
                "session": _session_summary(session),
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The Lightning runner could not initialize telemetry "
                    "before taking live actions. Fix the recorder/path issue "
                    "or explicitly rerun after deciding what evidence source "
                    "will replace the missing telemetry."
                ),
            }
        result: dict[str, Any] = {}
        status = "BLOCKED"
        reason = "unknown"
        if startup_session_block is not None:
            event_error = self._best_effort_event(
                "session_load_exception",
                **startup_session_block,
            )
            if event_error is not None:
                startup_session_block.setdefault(
                    "telemetry_event_errors",
                    [],
                ).append(event_error)
            result = self._finish(
                "BLOCKED",
                "session_load_exception",
                session_load=startup_session_block,
            )
            status = str(result.get("status") or status)
            reason = str(result.get("reason") or reason)
            self._write_final_telemetry(result, status=status, reason=reason)
            return result
        try:
            if self.config.screenshots:
                try:
                    self.screenshots = ScreenshotRecorder(
                        self.telemetry,
                        cadence_seconds=self._current_screenshot_cadence(),
                    )
                    self.screenshots.start()
                except Exception as exc:
                    self.screenshots = None
                    block = {
                        "span": "screenshot_start",
                        "exception_type": type(exc).__name__,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                        "next_step": (
                            "The background screenshot recorder failed before "
                            "any live runner action. Inspect the traceback and "
                            "recording path; rerun with screenshots disabled "
                            "only after accepting the weaker evidence trail."
                        ),
                    }
                    self.telemetry.event(
                        "screenshot_start_exception",
                        status="BLOCKED",
                        reason="screenshot_start_exception",
                        **block,
                    )
                    result = self._finish(
                        "BLOCKED",
                        "screenshot_start_exception",
                        **block,
                    )
                    status = str(result.get("status") or status)
                    reason = str(result.get("reason") or reason)
                    return result
            result = self._run_inner(commands)
            status = str(result.get("status") or status)
            reason = str(result.get("reason") or reason)
            return result
        except Exception as exc:
            result = self._finish(
                "BLOCKED",
                "runner_exception",
                exception_type=type(exc).__name__,
                error=str(exc),
                traceback=traceback.format_exc(),
            )
            status = str(result.get("status") or status)
            reason = str(result.get("reason") or reason)
            return result
        finally:
            if self.screenshots is not None:
                try:
                    self.screenshots.stop()
                    self.screenshots.capture_once(clock_state="final", note=reason)
                except Exception as exc:
                    if self.telemetry is not None:
                        try:
                            self.telemetry.event(
                                "screenshot_finalization_exception",
                                status="ERROR",
                                reason="screenshot_finalization_exception",
                                exception_type=type(exc).__name__,
                                error=str(exc),
                                traceback=traceback.format_exc(),
                                final_status=status,
                                final_reason=reason,
                            )
                        except Exception:
                            pass
            if self.telemetry is not None:
                self._write_final_telemetry(result, status=status, reason=reason)

    def _run_inner(self, commands: Any) -> dict[str, Any]:
        cfg = self.config
        assert self.telemetry is not None

        if cfg.achievement.lower() != LIGHTNING_WAR.lower():
            return self._finish(
                "BLOCKED",
                "unsupported_achievement",
                achievement=cfg.achievement,
            )
        if cfg.mode not in {"baseline", "speed"}:
            return self._finish("BLOCKED", "unsupported_mode", mode=cfg.mode)

        try:
            guard = self._span(
                "pause_guard_initial",
                commands.cmd_lightning_pause_guard,
                profile=cfg.profile,
                seconds=5.0,
                interval=0.25,
                once=True,
            )
        except Exception as exc:
            result = {
                "span": "pause_guard_initial",
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The initial pause/visible-state guard raised. Inspect the "
                    "traceback/window evidence before starting, resuming, or "
                    "clicking any Lightning War timeline."
                ),
            }
            self._record_result_event("pause_guard_initial_exception", result)
            return self._finish(
                "BLOCKED",
                "pause_guard_initial_exception",
                **result,
            )
        initial_visible_ui = _visible_ui_name(guard)
        hot_combat_start = _guard_is_hot_combat_start(guard)
        startup_hidden_panel = _startup_hidden_panel_name(guard)
        if initial_visible_ui in SYSTEM_BLOCKING_UIS:
            prompt_click = self._click_system_prompt_allow(guard, commands=commands)
            event_error = self._best_effort_event(
                "system_prompt_allow",
                visible_name=initial_visible_ui,
                click=_compact(prompt_click),
            )
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)
            if prompt_click.get("status") == "OK":
                try:
                    guard = self._span(
                        "pause_guard_after_system_prompt_allow",
                        commands.cmd_lightning_pause_guard,
                        profile=cfg.profile,
                        seconds=5.0,
                        interval=0.25,
                        once=True,
                    )
                except Exception as exc:
                    result = {
                        "span": "pause_guard_after_system_prompt_allow",
                        "system_prompt_allow": prompt_click,
                        "exception_type": type(exc).__name__,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                        "next_step": (
                            "The macOS Allow prompt was clicked, but the "
                            "follow-up guard raised. Inspect the visible "
                            "screen before any game input."
                        ),
                    }
                    self._record_result_event(
                        "pause_guard_after_system_prompt_allow_exception",
                        result,
                    )
                    return self._finish(
                        "BLOCKED",
                        "pause_guard_after_system_prompt_allow_exception",
                        **result,
                    )
                initial_visible_ui = _visible_ui_name(guard)
                hot_combat_start = _guard_is_hot_combat_start(guard)
                startup_hidden_panel = _startup_hidden_panel_name(guard)
            if initial_visible_ui in SYSTEM_BLOCKING_UIS:
                return self._finish(
                    "BLOCKED",
                    "external_system_prompt_visible",
                    visible_name=initial_visible_ui,
                    guard=_compact(guard),
                    system_prompt_allow=_compact(prompt_click),
                    next_step=(
                        "A macOS prompt is covering the game, but the Allow "
                        "button was not OCR-clickable or the prompt remained "
                        "after clicking. Inspect before any game input."
                    ),
                )
        if _must_act_now(guard) and initial_visible_ui != "new_game_setup":
            if hot_combat_start:
                event_error = self._best_effort_event(
                    "hot_combat_start",
                    status="OK",
                    reason="initial_guard_live_combat_phase",
                    guard=_compact(guard),
                )
                if event_error is not None:
                    self.telemetry_event_errors.append(event_error)
            else:
                return self._finish(
                    "BLOCKED_UNPAUSED_CLOCK_TICKING",
                    "initial_state_not_safe_to_think",
                    guard=_compact(guard),
                )

        if hot_combat_start:
            event_error = self._best_effort_event(
                "startup_checks_deferred",
                reason="hot_combat_start",
                skipped=[
                    "achievement_sync",
                    "verify_run_setup",
                    "preflight_initial",
                ],
            )
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)
        elif cfg.achievement_sync:
            try:
                sync = self._span(
                    "achievements_initial",
                    commands.cmd_achievements,
                    sync_local=True,
                )
            except Exception as exc:
                result = {
                    "span": "achievements_initial",
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "next_step": (
                        "The initial achievement sync helper raised. Inspect "
                        "the traceback/output evidence before trusting "
                        "achievement state or starting a new timeline."
                    ),
                }
                self._record_result_event("achievement_sync_exception", result)
                return self._finish(
                    "BLOCKED",
                    "achievement_sync_exception",
                    **result,
                )
            if _achievement_unlocked(sync):
                sync_session, session_block = self._load_session_or_block(
                    commands,
                    "initial_achievement_success_session",
                )
                if session_block is not None:
                    return self._finish(
                        "BLOCKED",
                        "session_load_exception",
                        session_load=session_block,
                        sync=_compact(sync),
                    )
                completion_block = self._completion_screen_block(
                    commands,
                    completed=_completed_islands(sync_session),
                    label="classify_before_initial_achievement_success",
                    allow_menu_setup=True,
                )
                if completion_block is not None:
                    return self._finish(
                        "BLOCKED",
                        str(completion_block["reason"]),
                        completion_block=completion_block,
                        sync=_compact(sync),
                    )
                return self._finish(
                    "SUCCESS",
                    "achievement_already_unlocked",
                    sync=_compact(sync),
                )

        if initial_visible_ui == "title_screen":
            try:
                title = self._span(
                    "title_new_game",
                    commands.cmd_lightning_ui,
                    control="title_new_game",
                    dry_run=cfg.dry_run,
                )
            except Exception as exc:
                result = {
                    "span": "title_new_game",
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "next_step": (
                        "The title-screen New Game helper raised. Inspect the "
                        "traceback/window evidence and regain a visible title "
                        "or setup screen before any more timeline clicks."
                    ),
                }
                self._record_result_event("title_new_game_exception", result)
                return self._finish(
                    "BLOCKED",
                    "title_new_game_exception",
                    **result,
                )
            if title.get("status") not in {"OK", "DRY_RUN"}:
                return self._finish(
                    "BLOCKED",
                    "title_new_game_failed",
                    title=_compact(title),
                )
            try:
                after_title = self._span(
                    "classify_after_title_new_game",
                    commands.cmd_lightning_ui,
                    control="classify",
                    include_ocr=True,
                )
            except Exception as exc:
                result = {
                    "span": "classify_after_title_new_game",
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "title": _compact(title),
                    "next_step": (
                        "The post-title classifier raised after New Game was "
                        "clicked. Inspect the traceback/window evidence and "
                        "rerun visual setup proof before starting a timeline."
                    ),
                }
                self._record_result_event(
                    "classify_after_title_new_game_exception",
                    result,
                )
                return self._finish(
                    "BLOCKED",
                    "classify_after_title_new_game_exception",
                    **result,
                )
            initial_visible_ui = _visible_ui_name(after_title)
            if initial_visible_ui != "new_game_setup":
                title_confirm = self._span(
                    "title_new_game_confirm_yes",
                    commands.cmd_lightning_ui,
                    control="title_new_game_confirm_yes",
                    dry_run=cfg.dry_run,
                )
                after_title_confirm = self._span(
                    "classify_after_title_new_game_confirm_yes",
                    commands.cmd_lightning_ui,
                    control="classify",
                    include_ocr=True,
                )
                confirmed_visible_ui = _visible_ui_name(after_title_confirm)
                if confirmed_visible_ui == "new_game_setup":
                    initial_visible_ui = confirmed_visible_ui
                    event_error = self._best_effort_event(
                        "title_new_game_overwrite_confirmed",
                        title=_compact(title),
                        after_title=_compact(after_title),
                        title_confirm=_compact(title_confirm),
                        after_title_confirm=_compact(after_title_confirm),
                    )
                    if event_error is not None:
                        self.telemetry_event_errors.append(event_error)
                else:
                    return self._finish(
                        "BLOCKED",
                        "title_new_game_did_not_reach_setup",
                        title=_compact(title),
                        after_title=_compact(after_title),
                        title_confirm=_compact(title_confirm),
                        after_title_confirm=_compact(after_title_confirm),
                    )
            if initial_visible_ui != "new_game_setup":
                return self._finish(
                    "BLOCKED",
                    "title_new_game_did_not_reach_setup",
                    title=_compact(title),
                    after_title=_compact(after_title),
                )

        if cfg.start_from_verified_setup or initial_visible_ui == "new_game_setup":
            started = self._start_from_setup(
                commands,
                initial_visible_ui,
                first_island=_first_island_for_attempt(
                    cfg.first_island,
                    1,
                    speed_mode=cfg.speed_mode,
                ),
            )
            if started.get("status") not in {"OK", "DRY_RUN"}:
                finish_reason = (
                    str(started.get("reason") or "")
                    if str(started.get("reason") or "")
                    in _LIGHTNING_RESTART_START_REASON_PASSTHROUGH
                    else "start_from_setup_failed"
                )
                return self._finish(
                    "BLOCKED",
                    finish_reason,
                    start=started,
                )

        session, session_block = self._load_session_or_block(
            commands,
            "after_startup_setup",
        )
        if session_block is not None:
            return self._finish(
                "BLOCKED",
                "session_load_exception",
                session_load=session_block,
            )
        reconcile = self._reconcile_stale_completion_session(
            commands,
            session,
            label="startup",
            visible=guard,
        )
        if reconcile is not None:
            if reconcile.get("status") == "BLOCKED":
                return self._finish(
                    "BLOCKED",
                    str(reconcile.get("reason")),
                    stale_completion_reconcile=reconcile,
                    session=_session_summary(session),
                )
            session, session_block = self._load_session_or_block(
                commands,
                "after_startup_completion_reconcile",
            )
            if session_block is not None:
                return self._finish(
                    "BLOCKED",
                    "session_load_exception",
                    session_load=session_block,
                    stale_completion_reconcile=reconcile,
                )
        if not hot_combat_start:
            setup_proof = self._verify_run_setup(commands)
            if setup_proof.get("status") == "BLOCKED":
                if setup_proof.get("reason") == "session_load_exception":
                    return self._finish(
                        "BLOCKED",
                        "session_load_exception",
                        session_load=setup_proof,
                    )
                return self._finish(
                    "BLOCKED",
                    "setup_state_unverified",
                    setup_proof=setup_proof,
                    session=_session_summary(session),
                )

        first_island_resume_needed = _needs_pending_first_island_confirmation(
            session,
            hot_combat_start=hot_combat_start,
        ) or _needs_first_island_selection_resume(
            session,
            initial_visible_ui,
            hot_combat_start=hot_combat_start,
        )
        if first_island_resume_needed:
            try:
                first_island_resume = self._span(
                    "select_first_island_resume",
                    commands.cmd_lightning_select_first_island,
                    profile=cfg.profile,
                    first_island=cfg.first_island,
                    advanced_content=cfg.advanced_content,
                    dry_run=cfg.dry_run,
                )
            except Exception as exc:
                result = {
                    "span": "select_first_island_resume",
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "visible_name": initial_visible_ui,
                    "session": _session_summary(session),
                    "next_step": (
                        "The first-island resume helper raised. Inspect the "
                        "traceback/window evidence and recover to verified "
                        "setup or a recorded current_island before any more "
                        "island clicks."
                    ),
                }
                self._record_result_event(
                    "select_first_island_resume_exception",
                    result,
                )
                return self._finish(
                    "BLOCKED",
                    "select_first_island_resume_exception",
                    **result,
                )
            if first_island_resume.get("status") not in {"OK", "DRY_RUN"}:
                return self._finish(
                    "BLOCKED",
                    _first_island_resume_finish_reason(first_island_resume),
                    first_island_resume=first_island_resume,
                    session=_session_summary(session),
                )
            session, session_block = self._load_session_or_block(
                commands,
                "after_first_island_selection_resume",
            )
            if session_block is not None:
                return self._finish(
                    "BLOCKED",
                    "session_load_exception",
                    session_load=session_block,
                    first_island_resume=first_island_resume,
                )

        completed = _completed_islands(session)
        if len(completed) >= cfg.target_islands:
            completion_block = self._completion_screen_block(
                commands,
                completed=completed,
                label="classify_before_initial_success",
            )
            if completion_block is not None:
                return self._finish(
                    "BLOCKED",
                    str(completion_block["reason"]),
                    completion_block=completion_block,
                    session=_session_summary(session),
                )
            return self._finish(
                "SUCCESS",
                "target_islands_already_completed",
                islands_completed=completed,
                session=_session_summary(session),
            )

        attempt_index = 1
        best_timer = None
        self._activate_iteration_phase(attempt_index)
        if not hot_combat_start:
            initial_preflight = self._run_preflight(commands, label="preflight_initial")
            if initial_preflight.get("status") == "BLOCKED":
                restart = self._restart_after_initial_preflight_if_safe(
                    commands,
                    preflight=initial_preflight,
                    session=session,
                    attempt_index=attempt_index,
                )
                if restart is not None:
                    if restart.get("status") in {"OK", "DRY_RUN"}:
                        attempt_index = int(
                            restart.get("next_attempt_index") or attempt_index + 1
                        )
                        self._activate_iteration_phase(attempt_index)
                    else:
                        finish_reason = (
                            "external_system_prompt_visible"
                            if restart.get("reason") == "external_system_prompt_visible"
                            else "preflight_restart_failed"
                        )
                        return self._finish(
                            "BLOCKED",
                            finish_reason,
                            restart=restart,
                            preflight=initial_preflight,
                        )
                else:
                    return self._finish(
                        "BLOCKED",
                        str(initial_preflight.get("reason") or "preflight_failed"),
                        preflight=initial_preflight,
                    )
            if initial_preflight.get("status") != "BLOCKED":
                best_timer = _timer_seconds(initial_preflight.get("result"))
                pace_session, session_block = self._load_session_or_block(
                    commands,
                    "initial_pace_gate",
                )
                if session_block is not None:
                    return self._finish(
                        "BLOCKED",
                        "session_load_exception",
                        session_load=session_block,
                    )
                pace_gate = self._pace_gate(
                    pace_session,
                    best_timer,
                    context=initial_preflight.get("result"),
                )
                if pace_gate is not None:
                    restart = self._restart_after_initial_pace_gate_if_safe(
                        commands,
                        pace_gate=pace_gate,
                        session=pace_session,
                        attempt_index=attempt_index,
                    )
                    if restart is not None:
                        if restart.get("status") in {"OK", "DRY_RUN"}:
                            attempt_index = int(
                                restart.get("next_attempt_index")
                                or attempt_index + 1
                            )
                            best_timer = None
                            self._activate_iteration_phase(attempt_index)
                        else:
                            restart_reason = str(restart.get("reason") or "")
                            finish_reason = (
                                "external_system_prompt_visible"
                                if restart.get("reason") == "external_system_prompt_visible"
                                else restart_reason
                                if restart_reason
                                in {
                                    "first_mission_start_timer_not_reset",
                                    "first_mission_start_timer_unverified",
                                }
                                else "pace_gate_restart_failed"
                            )
                            return self._finish(
                                "BLOCKED",
                                finish_reason,
                                restart=restart,
                                pace_gate=pace_gate,
                            )
                    else:
                        event_error = self._best_effort_event(
                            "pace_gate",
                            status="BLOCKED",
                            **pace_gate,
                        )
                        if event_error is not None:
                            pace_gate.setdefault("telemetry_event_errors", []).append(event_error)
                        return self._finish(
                            "BLOCKED",
                            str(pace_gate["reason"]),
                            pace_gate=pace_gate,
                            ensure_pause=self._ensure_pause(commands),
                        )
        no_progress_counts: dict[tuple[Any, ...], int] = {}
        pending_route_visual_region_index: int | None = None
        pending_route_start_context: dict[str, Any] | None = None
        skip_visible_panel_once_reason: str | None = None
        deployment_handoff_grace_segments = 0
        for segment_index in range(1, max(1, int(cfg.max_segments)) + 1):
            iteration_phase = self._activate_iteration_phase(attempt_index)
            session, session_block = self._load_session_or_block(
                commands,
                "segment_loop_start",
                segment_index=segment_index,
                attempt_index=attempt_index,
            )
            if session_block is not None:
                return self._finish(
                    "BLOCKED",
                    "session_load_exception",
                    session_load=session_block,
                )
            reconcile = self._reconcile_stale_completion_session(
                commands,
                session,
                label=f"segment_{segment_index}",
                visible=guard if segment_index == 1 else None,
            )
            if reconcile is not None:
                if reconcile.get("status") == "BLOCKED":
                    return self._finish(
                        "BLOCKED",
                        str(reconcile.get("reason")),
                        stale_completion_reconcile=reconcile,
                        session=_session_summary(session),
                    )
                session, session_block = self._load_session_or_block(
                    commands,
                    "after_loop_completion_reconcile",
                    segment_index=segment_index,
                )
                if session_block is not None:
                    return self._finish(
                        "BLOCKED",
                        "session_load_exception",
                        session_load=session_block,
                        stale_completion_reconcile=reconcile,
                    )
            completed = _completed_islands(session)
            event_error = self._best_effort_event(
                "runner_progress",
                segment_index=segment_index,
                attempt_index=attempt_index,
                iteration_phase=iteration_phase,
                max_attempts=cfg.max_attempts,
                islands_completed=completed,
                session=_session_summary(session),
            )
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)
            if len(completed) >= cfg.target_islands:
                completion_block = self._completion_screen_block(
                    commands,
                    completed=completed,
                    label="classify_before_loop_success",
                )
                if completion_block is not None:
                    return self._finish(
                        "BLOCKED",
                        str(completion_block["reason"]),
                        completion_block=completion_block,
                        session=_session_summary(session),
                    )
                return self._finish(
                    "SUCCESS",
                    "target_islands_completed",
                    islands_completed=completed,
                    session=_session_summary(session),
                    best_timer_seconds=best_timer,
                    best_timer=_format_seconds(best_timer),
                )

            if startup_hidden_panel is not None:
                panel = self._handle_paused_segment_panel(
                    commands,
                    segment_index=segment_index,
                    expected_visible_name=startup_hidden_panel,
                    paused_panel={
                        "status": "OK",
                        "reason": "startup_guard_hidden_panel",
                        "visible_name": "pause_menu",
                        "guard": _compact(guard),
                    },
                )
                startup_hidden_panel = None
                event_error = self._best_effort_event(
                    "startup_hidden_panel_handled",
                    segment_index=segment_index,
                    status=panel.get("status"),
                    reason=panel.get("reason"),
                    visible_name=panel.get("visible_name") or _visible_ui_name(panel),
                    expected_visible_name=panel.get("expected_visible_name"),
                )
                if event_error is not None:
                    panel.setdefault("telemetry_event_errors", []).append(event_error)
                if panel.get("status") in {"BLOCKED", "ERROR"}:
                    finish_reason = (
                        "external_system_prompt_visible"
                        if panel.get("reason") == "external_system_prompt_visible"
                        else "startup_hidden_panel_blocked"
                    )
                    return self._finish(
                        "BLOCKED",
                        finish_reason,
                        panel=panel,
                    )
                if panel.get("handled"):
                    if panel.get("status") not in {"OK", "NO_ACTION", "DRY_RUN"}:
                        return self._finish(
                            "BLOCKED",
                            "startup_hidden_panel_handling_failed",
                            panel=panel,
                        )
                    continue

            if skip_visible_panel_once_reason:
                event_error = self._best_effort_event(
                    "visible_panel_skipped",
                    segment_index=segment_index,
                    attempt_index=attempt_index,
                    reason=skip_visible_panel_once_reason,
                )
                if event_error is not None:
                    self.telemetry_event_errors.append(event_error)
                skip_visible_panel_once_reason = None
            else:
                panel = self._handle_visible_panel(commands, segment_index=segment_index)
                if panel.get("handled"):
                    if panel.get("status") not in {"OK", "NO_ACTION", "DRY_RUN"}:
                        finish_reason = (
                            "external_system_prompt_visible"
                            if panel.get("reason") == "external_system_prompt_visible"
                            else "visible_panel_handling_failed"
                        )
                        return self._finish(
                            "BLOCKED",
                            finish_reason,
                            panel=panel,
                        )
                    continue
                if panel.get("status") in {"BLOCKED", "ERROR"}:
                    finish_reason = (
                        "external_system_prompt_visible"
                        if panel.get("reason") == "external_system_prompt_visible"
                        else "visible_panel_blocked"
                    )
                    return self._finish(
                        "BLOCKED",
                        finish_reason,
                        panel=panel,
                    )

            if hot_combat_start and segment_index == 1:
                event_error = self._best_effort_event(
                    "preflight_skipped",
                    segment_index=segment_index,
                    reason="hot_combat_start",
                )
                if event_error is not None:
                    self.telemetry_event_errors.append(event_error)
            elif cfg.mode == "baseline" or segment_index == 1:
                preflight = self._run_preflight(
                    commands,
                    label=f"preflight_segment_{segment_index}",
                )
                if preflight.get("status") == "BLOCKED":
                    return self._finish(
                        "BLOCKED",
                        str(preflight.get("reason") or "preflight_failed"),
                        preflight=preflight,
                    )

            pending_route_region_window_x = None
            pending_route_region_window_y = None
            pending_route_target_mission_id = None
            pending_route_start_verify_route = None
            pending_route_close_existing_preview = False
            if isinstance(pending_route_start_context, dict):
                try:
                    pending_route_visual_region_index = int(
                        pending_route_start_context["visual_region_index"],
                    )
                except (KeyError, TypeError, ValueError):
                    pending_route_visual_region_index = None
                try:
                    pending_route_region_window_x = int(
                        pending_route_start_context["region_window_x"],
                    )
                    pending_route_region_window_y = int(
                        pending_route_start_context["region_window_y"],
                    )
                except (KeyError, TypeError, ValueError):
                    pending_route_region_window_x = None
                    pending_route_region_window_y = None
                target = str(
                    pending_route_start_context.get("target_mission_id") or "",
                ).strip()
                pending_route_target_mission_id = target or None
                verify_route = pending_route_start_context.get("verify_route")
                if isinstance(verify_route, bool):
                    pending_route_start_verify_route = verify_route
                pending_route_close_existing_preview = bool(
                    pending_route_start_context.get(
                        "close_existing_preview_before_region_click",
                    )
                )

            try:
                segment = self._span(
                    "lightning_segment",
                    commands.cmd_lightning_segment,
                    profile=cfg.profile,
                    time_limit=cfg.combat_time_limit,
                    max_steps=cfg.segment_steps,
                    max_turns=6,
                    max_wait=cfg.segment_max_wait,
                    click_ui=True,
                    set_fast_bridge=True,
                    run_preflight=False,
                    dry_run=cfg.dry_run,
                    max_wall_seconds=cfg.segment_wall_timeout,
                    pause_on_stop=True,
                    quiet=True,
                    resume_if_paused=True,
                    auto_clear_panels=cfg.auto_clear_panels,
                    allow_dirty_plan=False,
                    candidate_rank=None,
                    dirty_consent_id=None,
                    allow_protected_objective_loss=False,
                    allow_objective_loss=cfg.allow_objective_loss,
                    lightning_speed_loss_policy=cfg.speed_mode,
                    pause_before_solve=cfg.pause_before_solve,
                    pause_between_actions=cfg.pause_between_actions,
                    route_routing=cfg.route_routing,
                    route_auto_start=cfg.route_auto_start,
                    route_visual_region_index=pending_route_visual_region_index,
                    route_target_mission_id=pending_route_target_mission_id,
                    route_region_window_x=pending_route_region_window_x,
                    route_region_window_y=pending_route_region_window_y,
                    route_start_verify_route=pending_route_start_verify_route,
                    route_close_existing_preview=(
                        pending_route_close_existing_preview
                    ),
                    route_start_mode=cfg.route_start_mode,
                    route_probe_offset=_route_probe_offset_for_segment(
                        session,
                        attempt_index,
                        speed_mode=cfg.speed_mode,
                    ),
                    route_speed_vetoes=cfg.effective_route_speed_vetoes,
                    route_strict_mismatch=not cfg.speed_mode,
                    route_probe_cache=self._route_probe_cache_for_segment(session),
                    route_probe_cache_first_island=str(
                        getattr(session, "current_island", "") or "",
                    )
                    or None,
                    route_probe_cache_mission_index=_safe_int(
                        getattr(session, "mission_index", 0) or 0,
                    ),
                    first_mission_route_start_gate_seconds=(
                        cfg.first_mission_route_start_gate_seconds
                    ),
                )
            except Exception as exc:
                result = {
                    "span": "lightning_segment",
                    "segment_index": segment_index,
                    "attempt_index": attempt_index,
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "session": _session_summary(session),
                    "next_step": (
                        "The Lightning segment helper raised during the "
                        "start-to-next-decision burst. Stop before more UI or "
                        "combat commands; recover visible/bridge state, then "
                        "resume only from a fresh read plus solve or from "
                        "fresh setup proof."
                    ),
                }
                self._record_result_event("lightning_segment_exception", result)
                return self._finish(
                    "BLOCKED",
                    "lightning_segment_exception",
                    **result,
                )
            telemetry_event_errors: list[dict[str, Any]] = []
            try:
                self._record_segment_result(commands, segment_index, segment)
            except Exception as exc:
                telemetry_event_errors.append(
                    _telemetry_event_error(
                        "record_segment_result",
                        exc,
                        traceback_text=traceback.format_exc(),
                    )
                )
            timer = _timer_seconds(segment)
            if timer is not None:
                best_timer = max(best_timer or 0.0, timer)
                event_error = self._best_effort_event(
                    "clock_sample",
                    game_seconds=timer,
                    game_timer=_timer_label(segment),
                    segment_index=segment_index,
                )
                if event_error is not None:
                    telemetry_event_errors.append(event_error)

            immediate_stop = self._segment_immediate_stop(
                segment,
                commands=commands,
                segment_index=segment_index,
                session=session,
                telemetry_event_errors=telemetry_event_errors,
            )
            if immediate_stop is not None:
                if immediate_stop.get("status") == "RETRY_SEGMENT":
                    event_error = self._best_effort_event(
                        "segment_interruption_recovered",
                        segment_index=segment_index,
                        attempt_index=attempt_index,
                        recovery=_compact(immediate_stop),
                    )
                    if event_error is not None:
                        self.telemetry_event_errors.append(event_error)
                    no_progress_counts.clear()
                    continue
                return immediate_stop

            unexpected_menu = _current_unexpected_menu_evidence(segment)
            if (
                cfg.speed_mode
                and isinstance(unexpected_menu, dict)
                and unexpected_menu.get("visible_name") == "mech_loadout_screen"
            ):
                route_click_miss_gate = {
                    "reason": "mech_loadout_route_click_miss",
                    "game_seconds": _timer_seconds(segment),
                    "game_timer": _timer_label(segment),
                    "gate_seconds": float(cfg.first_mission_route_start_gate_seconds),
                    "gate_timer": _format_seconds(
                        cfg.first_mission_route_start_gate_seconds,
                    ),
                    "menu_evidence": unexpected_menu,
                    "islands_completed": _completed_islands(session),
                    "current_mission": str(
                        getattr(session, "current_mission", "") or "",
                    ),
                    "mission_index": _safe_int(
                        getattr(session, "mission_index", 0) or 0,
                    ),
                }
                restart = self._restart_after_initial_pace_gate_if_safe(
                    commands,
                    pace_gate=route_click_miss_gate,
                    session=session,
                    attempt_index=attempt_index,
                )
                if restart is not None and restart.get("status") in {"OK", "DRY_RUN"}:
                    attempt_index = int(
                        restart.get("next_attempt_index") or attempt_index + 1
                    )
                    best_timer = None
                    pending_route_visual_region_index = None
                    pending_route_start_context = None
                    no_progress_counts.clear()
                    continue
                return self._finish(
                    "BLOCKED",
                    "mech_loadout_route_click_miss_restart_failed",
                    restart=restart,
                    pace_gate=route_click_miss_gate,
                    segment=_compact(segment),
                    session=_session_summary(session),
                        **_telemetry_errors_payload(telemetry_event_errors),
                    )

            session, session_block = self._load_session_or_block(
                commands,
                "after_lightning_segment_pre_panel",
                segment_index=segment_index,
                attempt_index=attempt_index,
                segment=_compact(segment),
            )
            if session_block is not None:
                return self._finish(
                    "BLOCKED",
                    "session_load_exception",
                    session_load=session_block,
                    segment=_compact(segment),
                )
            pace_gate = self._segment_initial_pace_gate(
                session,
                segment,
            ) or self._pace_gate(session, best_timer, context=segment)
            if (
                deployment_handoff_grace_segments > 0
                and pace_gate is not None
                and str(pace_gate.get("reason") or "")
                in {
                    "first_mission_route_start_pace_gate",
                    "first_island_pace_gate",
                }
            ):
                deployment_handoff_grace_segments -= 1
                event_error = self._best_effort_event(
                    "pace_gate_suppressed_after_deployment_handoff",
                    segment_index=segment_index,
                    attempt_index=attempt_index,
                    pace_gate=pace_gate,
                    game_seconds=best_timer,
                    game_timer=_format_seconds(best_timer),
                )
                if event_error is not None:
                    self.telemetry_event_errors.append(event_error)
                pace_gate = None
            if pace_gate is not None:
                restart = self._restart_after_initial_pace_gate_if_safe(
                    commands,
                    pace_gate=pace_gate,
                    session=session,
                    attempt_index=attempt_index,
                )
                if restart is not None:
                    if restart.get("status") in {"OK", "DRY_RUN"}:
                        attempt_index = int(
                            restart.get("next_attempt_index")
                            or attempt_index + 1
                        )
                        best_timer = None
                        pending_route_visual_region_index = None
                        pending_route_start_context = None
                        no_progress_counts.clear()
                        continue
                    restart_reason = str(restart.get("reason") or "")
                    finish_reason = (
                        "external_system_prompt_visible"
                        if restart.get("reason") == "external_system_prompt_visible"
                        else restart_reason
                        if restart_reason
                        in {
                            "first_mission_start_timer_not_reset",
                            "first_mission_start_timer_unverified",
                        }
                        else "pace_gate_restart_failed"
                    )
                    return self._finish(
                        "BLOCKED",
                        finish_reason,
                        restart=restart,
                        pace_gate=pace_gate,
                        segment=_compact(segment),
                    )
                event_error = self._best_effort_event(
                    "pace_gate",
                    status="BLOCKED",
                    **pace_gate,
                )
                if event_error is not None:
                    pace_gate.setdefault("telemetry_event_errors", []).append(event_error)
                return self._finish(
                    "BLOCKED",
                    str(pace_gate["reason"]),
                    pace_gate=pace_gate,
                    segment=_compact(segment),
                    **_telemetry_errors_payload(telemetry_event_errors),
                )

            post_panel = self._handle_post_segment_panel(
                commands,
                segment=segment,
                segment_index=segment_index,
            )
            if post_panel is not None:
                if post_panel.get("status") in {"BLOCKED", "ERROR"}:
                    finish_reason = (
                        "external_system_prompt_visible"
                        if post_panel.get("reason") == "external_system_prompt_visible"
                        else "post_segment_panel_blocked"
                    )
                    return self._finish(
                        "BLOCKED",
                        finish_reason,
                        panel=post_panel,
                        segment=_compact(segment),
                    )
                if post_panel.get("status") not in {"OK", "NO_ACTION", "DRY_RUN"}:
                    return self._finish(
                        "BLOCKED",
                        "post_segment_panel_handling_failed",
                        panel=post_panel,
                        segment=_compact(segment),
                    )
                if post_panel.get("handled"):
                    no_progress_counts.clear()
                    continue

            block_evidence = self._blocking_stop_evidence(segment)
            preview_route_gate_evidence = _segment_preview_only_route_gate_evidence(
                segment,
            )
            if preview_route_gate_evidence is not None and (
                block_evidence is None
                or _normalize_stop_token_text(block_evidence.get("token"))
                in RECOVERABLE_PRECOMBAT_ROUTE_GATE_OVERRIDABLE_TOKENS
            ):
                block_evidence = preview_route_gate_evidence
            recoverable_route_gate_evidence = (
                _segment_recoverable_precombat_route_gate_evidence(
                    segment,
                    (
                        str(block_evidence.get("token"))
                        if block_evidence is not None
                        else None
                    ),
                )
            )
            if recoverable_route_gate_evidence is not None:
                block_evidence = recoverable_route_gate_evidence
            block = block_evidence.get("token") if block_evidence is not None else None
            if block is not None:
                route_probe_cache_record = self._record_route_probe_cache_entry(
                    commands,
                    segment=segment,
                    session=session,
                )
                restart = self._restart_after_route_gate_if_safe(
                    commands,
                    block=block,
                    segment=segment,
                    session=session,
                    segment_index=segment_index,
                    attempt_index=attempt_index,
                )
                if restart is not None:
                    if restart.get("status") in {"OK", "DRY_RUN"}:
                        attempt_index += 1
                        pending_route_visual_region_index = None
                        pending_route_start_context = None
                        no_progress_counts.clear()
                        continue
                    finish_reason = (
                        "external_system_prompt_visible"
                        if restart.get("reason") == "external_system_prompt_visible"
                        else "route_gate_restart_failed"
                    )
                    return self._finish(
                        "BLOCKED",
                        finish_reason,
                        restart=restart,
                        stop_token=block,
                        stop_evidence=block_evidence,
                        route_probe_cache_record=route_probe_cache_record,
                        segment=_compact(segment),
                        **_telemetry_errors_payload(telemetry_event_errors),
                    )
                if block == "ROUTE_AUTO_START_NOT_ALLOWED":
                    event_error = self._best_effort_event(
                        "route_auto_start_not_allowed",
                        status="BLOCKED",
                        segment_index=segment_index,
                        attempt_index=attempt_index,
                        max_attempts=cfg.max_attempts,
                        stop_token=block,
                        stop_evidence=block_evidence,
                        segment=_compact(segment),
                    )
                    if event_error is not None:
                        telemetry_event_errors.append(event_error)
                    return self._finish(
                        "BLOCKED",
                        "route_auto_start_not_allowed",
                        stop_token=block,
                        stop_evidence=block_evidence,
                        attempt_index=attempt_index,
                        max_attempts=cfg.max_attempts,
                        route_probe_cache_record=route_probe_cache_record,
                        segment=_compact(segment),
                        session=_session_summary(session),
                        next_step=(
                            "Stop before any Start Mission click. Route "
                            "auto-start did not prove a safe mission handoff "
                            "and no safe retry remains; inspect route evidence "
                            "or restart only from verified setup."
                        ),
                        **_telemetry_errors_payload(telemetry_event_errors),
                    )
                stop_sign_reason = _stop_sign_block_reason(
                    str(block),
                    evidence=block_evidence,
                )
                if stop_sign_reason is not None:
                    event_error = self._best_effort_event(
                        stop_sign_reason,
                        status="BLOCKED",
                        segment_index=segment_index,
                        attempt_index=attempt_index,
                        max_attempts=cfg.max_attempts,
                        stop_token=block,
                        stop_evidence=block_evidence,
                        segment=_compact(segment),
                    )
                    if event_error is not None:
                        telemetry_event_errors.append(event_error)
                    return self._finish(
                        "BLOCKED",
                        stop_sign_reason,
                        stop_token=block,
                        stop_evidence=block_evidence,
                        attempt_index=attempt_index,
                        max_attempts=cfg.max_attempts,
                        segment=_compact(segment),
                        session=_session_summary(session),
                        next_step=_stop_sign_next_step(stop_sign_reason),
                        **_telemetry_errors_payload(telemetry_event_errors),
                    )
                if block == "ROUTE_MISSION_MISMATCH":
                    event_error = self._best_effort_event(
                        "route_mission_mismatch_after_start",
                        status="BLOCKED",
                        segment_index=segment_index,
                        attempt_index=attempt_index,
                        max_attempts=cfg.max_attempts,
                        stop_token=block,
                        stop_evidence=block_evidence,
                        route_mismatch_warning=_segment_route_mismatch_warning(segment),
                        segment=_compact(segment),
                    )
                    if event_error is not None:
                        telemetry_event_errors.append(event_error)
                    return self._finish(
                        "BLOCKED",
                        "route_mission_mismatch_after_start",
                        stop_token=block,
                        stop_evidence=block_evidence,
                        attempt_index=attempt_index,
                        max_attempts=cfg.max_attempts,
                        route_mismatch_warning=_segment_route_mismatch_warning(segment),
                        segment=_compact(segment),
                        session=_session_summary(session),
                        next_step=(
                            "Stop before any deployment or combat command. The "
                            "route click started a different mission than the "
                            "verified preview; restart only from verified setup "
                            "or investigate the route preview evidence."
                        ),
                        **_telemetry_errors_payload(telemetry_event_errors),
                    )
                return self._finish(
                    "BLOCKED",
                    "hard_gate",
                    stop_token=block,
                    stop_evidence=block_evidence,
                    attempt_index=attempt_index,
                    ensure_pause=self._ensure_pause(commands),
                    segment=_compact(segment),
                    **_telemetry_errors_payload(telemetry_event_errors),
                )

            session, session_block = self._load_session_or_block(
                commands,
                "after_lightning_segment",
                segment_index=segment_index,
                attempt_index=attempt_index,
                segment=_compact(segment),
            )
            if session_block is not None:
                return self._finish(
                    "BLOCKED",
                    "session_load_exception",
                    session_load=session_block,
                    segment=_compact(segment),
                )
            pace_gate = self._segment_initial_pace_gate(
                session,
                segment,
            ) or self._pace_gate(session, best_timer, context=segment)
            if (
                deployment_handoff_grace_segments > 0
                and pace_gate is not None
                and str(pace_gate.get("reason") or "")
                in {
                    "first_mission_route_start_pace_gate",
                    "first_island_pace_gate",
                }
            ):
                deployment_handoff_grace_segments -= 1
                event_error = self._best_effort_event(
                    "pace_gate_suppressed_after_deployment_handoff",
                    segment_index=segment_index,
                    attempt_index=attempt_index,
                    pace_gate=pace_gate,
                    game_seconds=best_timer,
                    game_timer=_format_seconds(best_timer),
                )
                if event_error is not None:
                    self.telemetry_event_errors.append(event_error)
                pace_gate = None
            if pace_gate is not None:
                restart = self._restart_after_initial_pace_gate_if_safe(
                    commands,
                    pace_gate=pace_gate,
                    session=session,
                    attempt_index=attempt_index,
                )
                if restart is not None:
                    if restart.get("status") in {"OK", "DRY_RUN"}:
                        attempt_index = int(
                            restart.get("next_attempt_index")
                            or attempt_index + 1
                        )
                        best_timer = None
                        pending_route_visual_region_index = None
                        pending_route_start_context = None
                        no_progress_counts.clear()
                        continue
                    restart_reason = str(restart.get("reason") or "")
                    finish_reason = (
                        "external_system_prompt_visible"
                        if restart.get("reason") == "external_system_prompt_visible"
                        else restart_reason
                        if restart_reason
                        in {
                            "first_mission_start_timer_not_reset",
                            "first_mission_start_timer_unverified",
                        }
                        else "pace_gate_restart_failed"
                    )
                    return self._finish(
                        "BLOCKED",
                        finish_reason,
                        restart=restart,
                        pace_gate=pace_gate,
                        segment=_compact(segment),
                    )
                event_error = self._best_effort_event(
                    "pace_gate",
                    status="BLOCKED",
                    **pace_gate,
                )
                if event_error is not None:
                    pace_gate.setdefault("telemetry_event_errors", []).append(event_error)
                return self._finish(
                    "BLOCKED",
                    str(pace_gate["reason"]),
                    pace_gate=pace_gate,
                    ensure_pause=self._ensure_pause(commands),
                    segment=_compact(segment),
                )

            if cfg.speed_mode and best_timer is not None and best_timer >= cfg.abandon_seconds:
                return self._finish(
                    "BLOCKED",
                    "lightning_timer_budget_exceeded",
                    game_seconds=best_timer,
                    game_timer=_format_seconds(best_timer),
                    ensure_pause=self._ensure_pause(commands),
                    segment=_compact(segment),
                )

            completed = _completed_islands(session)
            if len(completed) >= cfg.target_islands:
                completion_block = self._completion_screen_block(
                    commands,
                    completed=completed,
                    label="classify_before_completed_success",
                )
                if completion_block is not None:
                    return self._finish(
                        "BLOCKED",
                        str(completion_block["reason"]),
                        completion_block=completion_block,
                        segment=_compact(segment),
                        session=_session_summary(session),
                    )
                return self._finish(
                    "SUCCESS",
                    "target_islands_completed",
                    islands_completed=completed,
                    session=_session_summary(session),
                    best_timer_seconds=best_timer,
                    best_timer=_format_seconds(best_timer),
                )

            pending_route_visual_region_index = None
            pending_context = segment.get("route_start_pending_context")
            if isinstance(pending_context, dict):
                has_pending_context = False
                try:
                    pending_route_visual_region_index = int(
                        pending_context["visual_region_index"],
                    )
                    has_pending_context = True
                except (KeyError, TypeError, ValueError):
                    pending_route_visual_region_index = None
                try:
                    int(pending_context["region_window_x"])
                    int(pending_context["region_window_y"])
                    has_pending_context = True
                except (KeyError, TypeError, ValueError):
                    pass
                if has_pending_context:
                    pending_route_start_context = dict(pending_context)
                    route_probe_cache_record = self._record_route_probe_cache_entry(
                        commands,
                        segment=segment,
                        session=session,
                    )
                    event_error = self._best_effort_event(
                        "route_auto_start_pending_retry",
                        segment_index=segment_index,
                        attempt_index=attempt_index,
                        visual_region_index=pending_route_visual_region_index,
                        route_start_pending_context=pending_route_start_context,
                        route_probe_cache_record=route_probe_cache_record,
                        segment=_compact(segment),
                    )
                    if event_error is not None:
                        self.telemetry_event_errors.append(event_error)
                    no_progress_counts.clear()
                    continue

            pending_route_start_context = None
            pending_region = segment.get("route_visual_region_index_pending")
            if pending_region is not None:
                try:
                    pending_route_visual_region_index = int(pending_region)
                except (TypeError, ValueError):
                    pending_route_visual_region_index = None
                if pending_route_visual_region_index is not None:
                    pending_route_start_context = {
                        "visual_region_index": pending_route_visual_region_index,
                    }
                    route_probe_cache_record = self._record_route_probe_cache_entry(
                        commands,
                        segment=segment,
                        session=session,
                    )
                    event_error = self._best_effort_event(
                        "route_auto_start_pending_retry",
                        segment_index=segment_index,
                        attempt_index=attempt_index,
                        visual_region_index=pending_route_visual_region_index,
                        route_start_pending_context=pending_route_start_context,
                        route_probe_cache_record=route_probe_cache_record,
                        segment=_compact(segment),
                    )
                    if event_error is not None:
                        self.telemetry_event_errors.append(event_error)
                    no_progress_counts.clear()
                    continue

            if (
                segment.get("status") == "LIGHTNING_SEGMENT_STOPPED"
                and (
                    str(segment.get("reason") or "")
                    in {
                        "deployment_confirmed_paused",
                        "deployment_waiting_for_ui_settle",
                    }
                    or _segment_visible_deployment_handoff(segment)
                )
            ):
                deployment_handoff_grace_segments = max(
                    deployment_handoff_grace_segments,
                    2,
                )
                skip_visible_panel_once_reason = str(segment.get("reason") or "")
                event_error = self._best_effort_event(
                    "deployment_confirmed_fast_handoff",
                    segment_index=segment_index,
                    attempt_index=attempt_index,
                    game_seconds=_timer_seconds(segment),
                    game_timer=_timer_label(segment),
                )
                if event_error is not None:
                    self.telemetry_event_errors.append(event_error)
                no_progress_counts.clear()
                continue

            if cfg.achievement_sync and _safe_to_think(segment):
                try:
                    sync = self._span(
                        "achievements_segment",
                        commands.cmd_achievements,
                        sync_local=True,
                    )
                except Exception as exc:
                    result = {
                        "span": "achievements_segment",
                        "segment_index": segment_index,
                        "exception_type": type(exc).__name__,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                        "segment": _compact(segment),
                        "session": _session_summary(session),
                        "next_step": (
                            "The post-segment achievement sync helper raised. "
                            "Inspect the traceback/output evidence before "
                            "trusting achievement state or continuing the "
                            "timeline."
                        ),
                    }
                    self._record_result_event("achievement_sync_exception", result)
                    return self._finish(
                        "BLOCKED",
                        "achievement_sync_exception",
                        **result,
                    )
                if _achievement_unlocked(sync):
                    completion_block = self._completion_screen_block(
                        commands,
                        completed=completed,
                        label="classify_before_achievement_sync_success",
                    )
                    if completion_block is not None:
                        return self._finish(
                            "BLOCKED",
                            str(completion_block["reason"]),
                            completion_block=completion_block,
                            segment=_compact(segment),
                            sync=_compact(sync),
                            session=_session_summary(session),
                        )
                    return self._finish(
                        "SUCCESS",
                        "achievement_confirmed_sync",
                        sync=_compact(sync),
                        islands_completed=completed,
                    )

            post_panel = self._handle_post_segment_panel(
                commands,
                segment=segment,
                segment_index=segment_index,
            )
            if post_panel is not None:
                if post_panel.get("status") in {"BLOCKED", "ERROR"}:
                    finish_reason = (
                        "external_system_prompt_visible"
                        if post_panel.get("reason") == "external_system_prompt_visible"
                        else "post_segment_panel_blocked"
                    )
                    return self._finish(
                        "BLOCKED",
                        finish_reason,
                        panel=post_panel,
                        segment=_compact(segment),
                    )
                if post_panel.get("status") not in {"OK", "NO_ACTION", "DRY_RUN"}:
                    return self._finish(
                        "BLOCKED",
                        "post_segment_panel_handling_failed",
                        panel=post_panel,
                        segment=_compact(segment),
                    )
                continue

            segment_reason = str(segment.get("reason") or "")
            visible_segment_name = _visible_ui_name(segment)
            if (
                segment_reason == "first_island_selection_map_without_route_context"
                and _needs_first_island_selection_resume(
                    session,
                    visible_segment_name,
                    hot_combat_start=hot_combat_start,
                )
            ) or (
                segment_reason == "recorded_first_island_selection_map_requires_confirm"
                and _needs_recorded_first_island_selection_confirm(
                    session,
                    visible_segment_name,
                    hot_combat_start=hot_combat_start,
                )
            ):
                resume_first_island = _first_island_for_attempt(
                    cfg.first_island,
                    attempt_index,
                    speed_mode=cfg.speed_mode,
                )
                try:
                    first_island_resume = self._span(
                        "select_first_island_from_segment",
                        commands.cmd_lightning_select_first_island,
                        profile=cfg.profile,
                        first_island=resume_first_island,
                        advanced_content=cfg.advanced_content,
                        dry_run=cfg.dry_run,
                    )
                except Exception as exc:
                    result = {
                        "span": "select_first_island_from_segment",
                        "exception_type": type(exc).__name__,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                        "segment": _compact(segment),
                        "session": _session_summary(session),
                        "next_step": (
                            "The first-island selector raised after a segment "
                            "exposed the corporation picker. Inspect the "
                            "traceback/window evidence and recover to verified "
                            "pause or setup before any more island clicks."
                        ),
                    }
                    self._record_result_event(
                        "select_first_island_from_segment_exception",
                        result,
                    )
                    return self._finish(
                        "BLOCKED",
                        "select_first_island_from_segment_exception",
                        **result,
                    )
                if first_island_resume.get("status") not in {"OK", "DRY_RUN"}:
                    return self._finish(
                        "BLOCKED",
                        _first_island_resume_finish_reason(first_island_resume),
                        first_island_resume=first_island_resume,
                        segment=_compact(segment),
                        session=_session_summary(session),
                    )
                session, session_block = self._load_session_or_block(
                    commands,
                    "after_segment_first_island_selection_resume",
                    segment_index=segment_index,
                    attempt_index=attempt_index,
                    first_island_resume=_compact(first_island_resume),
                )
                if session_block is not None:
                    return self._finish(
                        "BLOCKED",
                        "session_load_exception",
                        session_load=session_block,
                        first_island_resume=_compact(first_island_resume),
                        segment=_compact(segment),
                    )
                event_error = self._best_effort_event(
                    "segment_first_island_selection_resumed",
                    segment_index=segment_index,
                    attempt_index=attempt_index,
                    first_island=resume_first_island,
                    first_island_resume=_compact(first_island_resume),
                    session=_session_summary(session),
                )
                if event_error is not None:
                    self.telemetry_event_errors.append(event_error)
                pending_route_visual_region_index = None
                pending_route_start_context = None
                no_progress_counts.clear()
                continue

            if _must_act_now(segment):
                event_error = self._best_effort_event(
                    "segment_requires_immediate_continuation",
                    segment_index=segment_index,
                    segment=_compact(segment),
                )
                if event_error is not None:
                    self.telemetry_event_errors.append(event_error)
                continue

            progress_key = self._progress_key(session, segment)
            no_progress_counts[progress_key] = no_progress_counts.get(progress_key, 0) + 1
            if no_progress_counts[progress_key] > 3:
                return self._finish(
                    "BLOCKED",
                    "repeated_no_progress_state",
                    progress_key=list(progress_key),
                    segment=_compact(segment),
                    session=_session_summary(session),
                    ensure_pause=self._ensure_pause(commands),
                )

        final_session, final_session_block = self._load_session_or_block(
            commands,
            "max_segments_reached",
        )
        final_payload: dict[str, Any] = {
            "ensure_pause": self._ensure_pause(commands),
            "max_segments": cfg.max_segments,
        }
        if final_session_block is not None:
            final_payload["session_load"] = final_session_block
            final_payload["islands_completed"] = []
        else:
            final_payload["islands_completed"] = _completed_islands(final_session)
            final_payload["session"] = _session_summary(final_session)
        return self._finish(
            "BLOCKED",
            "max_segments_reached",
            **final_payload,
        )

    def _segment_immediate_stop(
        self,
        segment: dict[str, Any],
        *,
        commands: Any,
        segment_index: int,
        session: Any,
        telemetry_event_errors: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        telemetry_errors = list(telemetry_event_errors or [])
        heartbeat_evidence = _stale_bridge_heartbeat_evidence(segment)
        if heartbeat_evidence is not None:
            event_error = self._best_effort_event(
                "stale_bridge_heartbeat",
                status="BLOCKED",
                segment_index=segment_index,
                heartbeat_evidence=heartbeat_evidence,
                segment=_compact(segment),
            )
            if event_error is not None:
                telemetry_errors.append(event_error)
            return self._finish(
                "BLOCKED",
                "stale_bridge_heartbeat",
                heartbeat_evidence=heartbeat_evidence,
                segment=_compact(segment),
                session=_session_summary(session),
                next_step=(
                    "Stop before more combat commands. Recover the bridge, then "
                    "resume from a fresh read plus solve; do not reuse the old "
                    "partial-turn solution."
                ),
                **_telemetry_errors_payload(telemetry_errors),
            )

        external_prompt_evidence = _external_system_prompt_evidence(segment)
        if external_prompt_evidence is not None:
            prompt_click = self._click_system_prompt_allow(
                external_prompt_evidence,
                commands=commands,
            )
            pause_after_prompt = None
            if prompt_click.get("status") == "OK":
                pause_after_prompt = self._ensure_pause(commands)
                if _pause_after_system_prompt_verified(pause_after_prompt):
                    event_error = self._best_effort_event(
                        "external_system_prompt_recovered",
                        status="OK",
                        reason="system_prompt_cleared_pause_verified",
                        segment_index=segment_index,
                        external_prompt_evidence=external_prompt_evidence,
                        system_prompt_allow=_compact(prompt_click),
                        pause_after_prompt=_compact(pause_after_prompt),
                    )
                    if event_error is not None:
                        telemetry_errors.append(event_error)
                    return {
                        "status": "RETRY_SEGMENT",
                        "reason": "external_system_prompt_cleared_retry",
                        "external_prompt_evidence": external_prompt_evidence,
                        "system_prompt_allow": _compact(prompt_click),
                        "pause_after_prompt": _compact(pause_after_prompt),
                        "segment": _compact(segment),
                        "session": _session_summary(session),
                        **_telemetry_errors_payload(telemetry_errors),
                    }
            event_error = self._best_effort_event(
                "external_system_prompt_visible",
                status="BLOCKED",
                segment_index=segment_index,
                external_prompt_evidence=external_prompt_evidence,
                system_prompt_allow=_compact(prompt_click),
                pause_after_prompt=_compact(pause_after_prompt),
                segment=_compact(segment),
            )
            if event_error is not None:
                telemetry_errors.append(event_error)
            return self._finish(
                "BLOCKED",
                "external_system_prompt_visible",
                external_prompt_evidence=external_prompt_evidence,
                system_prompt_allow=_compact(prompt_click),
                pause_after_prompt=_compact(pause_after_prompt),
                segment=_compact(segment),
                session=_session_summary(session),
                next_step=(
                    "A macOS privacy prompt interrupted the segment. If the "
                    "standing-approved Allow clear succeeded, the runner also "
                    "attempted to restore a safe pause/setup state before "
                    "blocking for a clean retry."
                ),
                **_telemetry_errors_payload(telemetry_errors),
            )

        terminal_evidence = _terminal_outcome_evidence(segment)
        if terminal_evidence is not None:
            event_error = self._best_effort_event(
                "terminal_outcome_visible",
                status="BLOCKED",
                segment_index=segment_index,
                terminal_evidence=terminal_evidence,
                segment=_compact(segment),
            )
            if event_error is not None:
                telemetry_errors.append(event_error)
            return self._finish(
                "BLOCKED",
                "terminal_outcome_visible",
                terminal_evidence=terminal_evidence,
                segment=_compact(segment),
                session=_session_summary(session),
                next_step=(
                    "Stop before clearing UI, syncing achievements, or "
                    "continuing combat. The lower-level segment evidence "
                    "already contains KIA, timeline-lost, or failed-objective "
                    "text/flags; inspect the screenshot and treat the "
                    "Lightning War timeline as failed unless the evidence "
                    "is proven stale or misclassified."
                ),
                **_telemetry_errors_payload(telemetry_errors),
            )

        timeout_evidence = _solver_or_combat_timeout_evidence(segment)
        if timeout_evidence is not None:
            event_error = self._best_effort_event(
                "solver_or_combat_timeout",
                status="BLOCKED",
                segment_index=segment_index,
                timeout_evidence=timeout_evidence,
                segment=_compact(segment),
            )
            if event_error is not None:
                telemetry_errors.append(event_error)
            return self._finish(
                "BLOCKED",
                "solver_or_combat_timeout",
                timeout_evidence=timeout_evidence,
                segment=_compact(segment),
                session=_session_summary(session),
                next_step=(
                    "Stop before more combat commands. Treat this like a "
                    "solver/combat wait timeout: recover the visible/bridge "
                    "state, then resume only from a fresh read plus solve."
                ),
                **_telemetry_errors_payload(telemetry_errors),
            )

        block_evidence = self._blocking_stop_evidence(segment)
        block = block_evidence.get("token") if block_evidence is not None else None
        if block == "DESYNC":
            event_error = self._best_effort_event(
                "combat_desync",
                status="BLOCKED",
                segment_index=segment_index,
                stop_evidence=block_evidence,
                segment=_compact(segment),
            )
            if event_error is not None:
                telemetry_errors.append(event_error)
            return self._finish(
                "BLOCKED",
                "combat_desync",
                stop_token=block,
                stop_evidence=block_evidence,
                segment=_compact(segment),
                session=_session_summary(session),
                next_step=(
                    "Stop before more combat commands or End Turn "
                    "clicks. Recover the visible/bridge state, then "
                    "resume only from a fresh read plus solve; do not "
                    "reuse the old partial-turn solution."
                ),
                **_telemetry_errors_payload(telemetry_errors),
            )

        stop_sign_reason = _stop_sign_block_reason(
            str(block) if block is not None else None,
            evidence=block_evidence,
        )
        if (
            _segment_preview_only_route_gate(segment)
            and (
                block is None
                or _normalize_stop_token_text(str(block))
                in RECOVERABLE_PRECOMBAT_ROUTE_GATE_OVERRIDABLE_TOKENS
            )
        ):
            return None
        if (
            self.config.speed_mode
            and _segment_mission_preview_route_validation_gate(segment)
        ):
            return None
        recoverable_route_gate_evidence = (
            _segment_recoverable_precombat_route_gate_evidence(
                segment,
                str(block) if block is not None else None,
            )
        )
        if recoverable_route_gate_evidence is not None:
            return None
        if _segment_recoverable_precombat_route_gate(segment, str(block or "")):
            return None
        if block == "ROUTE_MISSION_MISMATCH" and _segment_route_mismatch_after_start_gate(
            segment,
        ):
            return None
        if stop_sign_reason is not None:
            event_error = self._best_effort_event(
                stop_sign_reason,
                status="BLOCKED",
                segment_index=segment_index,
                stop_token=block,
                stop_evidence=block_evidence,
                segment=_compact(segment),
            )
            if event_error is not None:
                telemetry_errors.append(event_error)
            return self._finish(
                "BLOCKED",
                stop_sign_reason,
                stop_token=block,
                stop_evidence=block_evidence,
                segment=_compact(segment),
                session=_session_summary(session),
                next_step=_stop_sign_next_step(stop_sign_reason),
                **_telemetry_errors_payload(telemetry_errors),
            )

        unexpected_menu = _current_unexpected_menu_evidence(segment)
        if unexpected_menu is not None:
            if (
                self.config.speed_mode
                and unexpected_menu.get("visible_name") == "mech_loadout_screen"
            ):
                return None
            event_error = self._best_effort_event(
                "reload_or_main_menu_visible",
                status="BLOCKED",
                segment_index=segment_index,
                menu_evidence=unexpected_menu,
                segment=_compact(segment),
            )
            if event_error is not None:
                telemetry_errors.append(event_error)
            return self._finish(
                "BLOCKED",
                "reload_or_main_menu_visible",
                menu_evidence=unexpected_menu,
                segment=_compact(segment),
                session=_session_summary(session),
                next_step=(
                    "The game appears to have returned to title/setup "
                    "during an active Lightning War run. Inspect the "
                    "visible screen and session state before starting or "
                    "continuing any timeline. Do not trust stale session "
                    "progress; resume an existing combat timeline only "
                    "after a fresh read plus solve, or restart only after "
                    "fresh setup verification."
                ),
                **_telemetry_errors_payload(telemetry_errors),
            )

        segment_failure = _segment_failure_evidence(segment)
        if segment_failure is not None:
            if self._segment_initial_pace_gate(session, segment) is not None:
                return None
            event_error = self._best_effort_event(
                "segment_failed",
                status="BLOCKED",
                segment_index=segment_index,
                segment_failure=segment_failure,
                segment=_compact(segment),
            )
            if event_error is not None:
                telemetry_errors.append(event_error)
            return self._finish(
                "BLOCKED",
                "segment_failed",
                segment_failure=segment_failure,
                segment=_compact(segment),
                session=_session_summary(session),
                next_step=(
                    "A lower-level Lightning segment helper failed without "
                    "a recognized stop token. Inspect the segment failure "
                    "evidence and visible state before rerunning; do not "
                    "loop the same helper result."
                ),
                **_telemetry_errors_payload(telemetry_errors),
            )
        return None

    def _segment_initial_pace_gate(
        self,
        session: Any,
        segment: dict[str, Any],
    ) -> dict[str, Any] | None:
        cfg = self.config
        if not cfg.speed_mode or not isinstance(segment, dict):
            return None
        reason = str(segment.get("reason") or "")
        timeout_evidence = _lightning_subcall_timeout_evidence(segment)
        first_route_timeout = (
            timeout_evidence is not None
            and not bool(segment.get("route_start_performed"))
            and not _segment_entered_combat(segment)
        )
        if (
            reason
            not in {
                "first_mission_start_timer_not_reset",
                "first_mission_route_start_pace_gate",
            }
            and not first_route_timeout
        ):
            return None

        completed = _completed_islands(session)
        current_mission = str(getattr(session, "current_mission", "") or "").strip()
        mission_index = _safe_int(getattr(session, "mission_index", 0) or 0)
        if completed or current_mission or mission_index > 0:
            return None

        guard = segment.get("first_mission_start_timer_guard")
        if not isinstance(guard, dict):
            guard = {}
        visible_timer = guard.get("visible_timer")
        if not isinstance(visible_timer, dict):
            visible_timer = {}
        budget = guard.get("game_budget")
        if not isinstance(budget, dict):
            budget = {}

        game_seconds = _timer_seconds(segment)
        if game_seconds is None and visible_timer.get("game_seconds") is not None:
            game_seconds = _safe_float(visible_timer.get("game_seconds"))
        if game_seconds is None and budget.get("game_seconds") is not None:
            game_seconds = _safe_float(budget.get("game_seconds"))
        if game_seconds is None:
            return None

        gate_seconds = None
        for candidate in (
            budget.get("max_game_seconds"),
            guard.get("gate_seconds"),
            cfg.first_mission_route_start_gate_seconds,
        ):
            if candidate is None:
                continue
            gate_seconds = _safe_float(candidate)
            break

        return {
            "reason": (
                "first_mission_route_start_pace_gate"
                if first_route_timeout
                or reason == "first_mission_route_start_pace_gate"
                else reason
            ),
            "game_seconds": round(float(game_seconds), 3),
            "game_timer": _timer_label(segment) or _format_seconds(game_seconds),
            "gate_seconds": float(gate_seconds) if gate_seconds is not None else None,
            "gate_timer": _format_seconds(gate_seconds),
            "islands_completed": completed,
            "current_mission": current_mission,
            "mission_index": mission_index,
            "trigger": "first_route_subcall_timeout" if first_route_timeout else None,
            "timeout_evidence": _compact(timeout_evidence) if first_route_timeout else None,
            "visible_timer": _compact(visible_timer) if visible_timer else None,
            "first_mission_start_timer_guard": _compact(guard) if guard else None,
        }

    def _start_from_setup(
        self,
        commands: Any,
        initial_visible_ui: str | None,
        *,
        first_island: str | None = None,
    ) -> dict[str, Any]:
        cfg = self.config
        chosen_first_island = first_island or _first_island_for_attempt(
            cfg.first_island,
            1,
            speed_mode=cfg.speed_mode,
        )
        setup: dict[str, Any] | None = None
        if initial_visible_ui == "new_game_setup":
            setup = self._prepare_setup(commands)
            if setup.get("status") == "PASS" or cfg.dry_run:
                self.telemetry.event(
                    "setup_start_skipped",
                    reason="setup_modal_already_verified",
                    setup=_compact(setup),
                )
            else:
                setup = None
        if initial_visible_ui == "new_game_setup" and setup is None:
            try:
                setup_start = self._span(
                    "setup_start",
                    commands.cmd_lightning_ui,
                    control="setup_start",
                    dry_run=cfg.dry_run,
                )
            except Exception as exc:
                assert self.telemetry is not None
                result = {
                    "status": "BLOCKED",
                    "reason": "setup_start_exception",
                    "span": "setup_start",
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "next_step": (
                        "The setup-start UI helper raised before setup proof. "
                        "Inspect the traceback/window evidence and rerun from "
                        "a visible title or setup screen before starting a "
                        "Lightning War timeline."
                    ),
                }
                self._record_result_event("setup_start_exception", result)
                return result
            if setup_start.get("status") not in {"OK", "DRY_RUN"}:
                return {
                    "status": "BLOCKED",
                    "reason": "setup_start_failed",
                    "setup_start": _compact(setup_start),
                }

        if setup is None:
            setup = self._prepare_setup(commands)
        if setup.get("status") != "PASS" and not cfg.dry_run:
            return {
                "status": "BLOCKED",
                "reason": "setup_not_verified",
                "setup": _compact(setup),
            }

        try:
            start = self._span(
                "lightning_start_run",
                commands.cmd_lightning_start_run,
                profile=cfg.profile,
                difficulty=cfg.difficulty,
                advanced_content=cfg.advanced_content,
                first_island=chosen_first_island,
                time_limit=cfg.combat_time_limit,
                max_steps=cfg.segment_steps,
                max_turns=6,
                    max_wait=cfg.segment_max_wait,
                max_wall_seconds=cfg.max_wall_seconds,
                route_auto_start=False,
                run_segment=False,
                allow_objective_loss=False,
                lightning_speed_loss_policy=cfg.speed_mode,
                pause_before_solve=cfg.pause_before_solve,
                pause_between_actions=cfg.pause_between_actions,
                dry_run=cfg.dry_run,
            )
        except Exception as exc:
            assert self.telemetry is not None
            result = {
                "status": "BLOCKED",
                "reason": "lightning_start_run_exception",
                "span": "lightning_start_run",
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The start-run helper raised after setup proof. Inspect "
                    "the traceback/window evidence, then rerun visible setup "
                    "proof before accepting or starting the timeline."
                ),
            }
            self._record_result_event("lightning_start_run_exception", result)
            return result
        if str(start.get("status")) not in {"OK", "DRY_RUN"}:
            external_prompt_evidence = _external_system_prompt_evidence(start)
            start_reason = str(start.get("reason") or "")
            pause_recovery = self._recover_start_failure_to_pause(commands, start)
            result = {
                "status": "BLOCKED",
                "reason": (
                    "external_system_prompt_visible"
                    if external_prompt_evidence is not None
                    else start_reason
                    if start_reason
                    in _LIGHTNING_RESTART_START_REASON_PASSTHROUGH
                    else "lightning_start_run_failed"
                ),
                "start": _compact(start),
                "pause_recovery": _compact(pause_recovery),
            }
            if external_prompt_evidence is not None:
                result["external_prompt_evidence"] = external_prompt_evidence
            return result
        self._rehome_telemetry_if_session_changed(commands, reason="lightning_start_run")
        return {
            "status": "OK",
            "reason": "started_from_setup",
            "first_island": chosen_first_island,
            "start": _compact(start),
        }

    def _recover_start_failure_to_pause(
        self,
        commands: Any,
        start: dict[str, Any],
    ) -> dict[str, Any]:
        """Bounded recovery for failed setup starts before returning to the LLM."""
        attempts: list[dict[str, Any]] = []
        if self.config.dry_run:
            return {"status": "DRY_RUN", "reason": "dry_run_start_failure_recovery"}

        for index in range(2):
            try:
                pause = self._span(
                    f"start_failure_ensure_pause_{index}",
                    commands.cmd_lightning_ui,
                    control="ensure_pause",
                    dry_run=self.config.dry_run,
                )
            except Exception as exc:
                return {
                    "status": "BLOCKED",
                    "reason": "start_failure_pause_exception",
                    "attempts": attempts,
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "start": _compact(start),
                }
            attempts.append({"step": "ensure_pause", "result": _compact(pause)})
            if pause.get("status") == "OK":
                return {
                    "status": "OK",
                    "reason": "start_failure_paused",
                    "attempts": attempts,
                }
            if pause.get("reason") != "visible_panel_should_be_cleared_first":
                return {
                    "status": "BLOCKED",
                    "reason": "start_failure_pause_blocked",
                    "attempts": attempts,
                    "start": _compact(start),
                }
            try:
                handled = self._span(
                    f"start_failure_handle_screen_{index}",
                    commands.cmd_lightning_ui,
                    control="handle_screen",
                    dry_run=self.config.dry_run,
                )
            except Exception as exc:
                return {
                    "status": "BLOCKED",
                    "reason": "start_failure_handle_screen_exception",
                    "attempts": attempts,
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "start": _compact(start),
                }
            attempts.append({"step": "handle_screen", "result": _compact(handled)})
            if handled.get("status") not in {"OK", "DRY_RUN"}:
                return {
                    "status": "BLOCKED",
                    "reason": "start_failure_handle_screen_failed",
                    "attempts": attempts,
                    "start": _compact(start),
                }

        return {
            "status": "BLOCKED",
            "reason": "start_failure_pause_recovery_exhausted",
            "attempts": attempts,
            "start": _compact(start),
        }

    def _verify_run_setup(self, commands: Any) -> dict[str, Any]:
        cfg = self.config
        session, session_block = self._load_session_or_block(
            commands,
            "verify_run_setup",
        )
        if session_block is not None:
            return session_block
        if cfg.dry_run:
            return {
                "status": "OK",
                "reason": "dry_run_setup_state_not_mutated",
                "session": _session_summary(session),
            }

        issues: list[str] = []
        warnings: list[str] = []
        session_squad = str(getattr(session, "squad", "") or "").strip()
        if session_squad.lower() != "blitzkrieg":
            issues.append(f"active session squad is {session_squad!r}, not Blitzkrieg")
        try:
            session_difficulty = int(getattr(session, "difficulty", 0) or 0)
        except (TypeError, ValueError):
            session_difficulty = -1
        if session_difficulty != int(cfg.difficulty):
            issues.append(
                f"active session difficulty is {session_difficulty}, "
                f"not expected {cfg.difficulty}"
            )
        targets = {
            str(target).strip().lower()
            for target in (getattr(session, "achievement_targets", []) or [])
            if str(target).strip()
        }
        if LIGHTNING_WAR.lower() not in targets:
            issues.append("active achievement targets do not include Lightning War")

        try:
            state = load_game_state(cfg.profile)
            save_state = _save_state_summary(state)
        except Exception as exc:
            state = None
            save_state = {
                "status": "ERROR",
                "reason": "setup_save_state_reader_exception",
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            issues.append("save state reader raised during setup proof")
        advanced_proof = _advanced_content_proof(commands, cfg.profile)
        if cfg.advanced_content in {"on", "off"}:
            desired_value = 1 if cfg.advanced_content == "on" else 0
            advanced_state = advanced_proof.get("state")
            if advanced_proof.get("status") == "UNAVAILABLE":
                warnings.append("advanced content reader unavailable for setup proof")
            elif advanced_proof.get("status") != "OK" or not isinstance(
                advanced_state,
                dict,
            ):
                issues.append("advanced content state unavailable for setup proof")
            else:
                mismatched = [
                    key
                    for key, value in advanced_state.items()
                    if value != desired_value
                ]
                if mismatched:
                    issues.append(
                        "advanced content state mismatch for "
                        + ", ".join(mismatched)
                        + f"; expected {cfg.advanced_content.upper()}"
                    )
        if state is None:
            issues.append("save state unavailable for setup proof")
        else:
            if int(getattr(state, "difficulty", -1)) != int(cfg.difficulty):
                issues.append(
                    f"save difficulty is {getattr(state, 'difficulty', None)}, "
                    f"not expected {cfg.difficulty}"
                )
            mechs = set(_state_mechs(state))
            missing_mechs = sorted(EXPECTED_BLITZKRIEG_MECHS - mechs)
            if missing_mechs:
                issues.append(
                    "save loadout missing Blitzkrieg mech id(s): "
                    + ", ".join(missing_mechs)
                )
            weapons = _state_weapons(state)
            missing_weapons = [
                weapon
                for weapon in sorted(EXPECTED_BLITZKRIEG_WEAPONS)
                if not _weapon_or_upgrade_present(weapons, weapon)
            ]
            if missing_weapons:
                issues.append(
                    "save loadout missing Blitzkrieg weapon id(s): "
                    + ", ".join(missing_weapons)
                )
            if len(mechs) > len(EXPECTED_BLITZKRIEG_MECHS):
                warnings.append(
                    "save loadout has extra mech ids: "
                    + ", ".join(sorted(mechs - EXPECTED_BLITZKRIEG_MECHS))
                )

        status = "BLOCKED" if issues else "OK"
        proof = {
            "status": status,
            "reason": "lightning_setup_state_verified" if status == "OK" else "setup_state_mismatch",
            "issues": issues,
            "warnings": warnings,
            "session": _session_summary(session),
            "save_state": save_state,
            "expected": {
                "squad": "Blitzkrieg",
                "difficulty": cfg.difficulty,
                "achievement": LIGHTNING_WAR,
                "advanced_content": cfg.advanced_content,
                "mechs": sorted(EXPECTED_BLITZKRIEG_MECHS),
                "weapons": sorted(EXPECTED_BLITZKRIEG_WEAPONS),
            },
            "advanced_content": advanced_proof,
        }
        assert self.telemetry is not None
        event_error = self._best_effort_event("setup_state_proof", **proof)
        if event_error is not None:
            proof.setdefault("telemetry_event_errors", []).append(event_error)
        return proof

    def _prepare_setup(self, commands: Any) -> dict[str, Any]:
        cfg = self.config
        def _focus_retry_warranted(result: dict[str, Any]) -> bool:
            if not isinstance(result, dict):
                return False
            if result.get("status") == "PASS":
                return False
            if not result.get("setup_screen_detected"):
                return False
            if result.get("click_plan"):
                return False
            if result.get("actual_difficulty") != cfg.difficulty:
                return False
            advanced = result.get("advanced")
            if not isinstance(advanced, list) or not advanced:
                return False
            desired_on = str(cfg.advanced_content or "").lower() not in {"off", "false", "0", "no"}
            if any(bool(item.get("enabled")) != desired_on for item in advanced if isinstance(item, dict)):
                return False
            return result.get("window_focus_verified") is False

        try:
            setup = self._span(
                "verify_setup",
                commands.cmd_verify_setup_screen,
                expected_difficulty=cfg.difficulty,
                advanced_content=cfg.advanced_content,
            )
        except Exception as exc:
            assert self.telemetry is not None
            result = {
                "status": "FAIL",
                "reason": "setup_verification_exception",
                "span": "verify_setup",
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The setup verifier raised before Start. Inspect the "
                    "traceback/window evidence and rerun verify_setup before "
                    "starting a Lightning War timeline."
                ),
            }
            self._record_result_event("setup_verification_exception", result)
            return result
        if setup.get("status") == "PASS" or cfg.dry_run:
            return setup
        if _focus_retry_warranted(setup):
            time.sleep(0.6)
            try:
                setup = self._span(
                    "verify_setup_focus_retry",
                    commands.cmd_verify_setup_screen,
                    expected_difficulty=cfg.difficulty,
                    advanced_content=cfg.advanced_content,
                )
            except Exception as exc:
                assert self.telemetry is not None
                result = {
                    "status": "FAIL",
                    "reason": "setup_verification_exception",
                    "span": "verify_setup_focus_retry",
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "next_step": (
                        "The setup verifier raised during focus retry. Inspect "
                        "the traceback/window evidence and rerun verify_setup "
                        "before starting a Lightning War timeline."
                    ),
                }
                self._record_result_event("setup_verification_exception", result)
                return result
            if setup.get("status") == "PASS":
                return setup
        clicks = setup.get("click_plan") or []
        if not clicks:
            return setup

        from src.control.mac_click import click_window_point

        for click in clicks:
            try:
                click_result = click_window_point(
                    int(click["x"]),
                    int(click["y"]),
                    description=str(click.get("description") or "setup adjustment"),
                    dry_run=cfg.dry_run,
                )
            except Exception as exc:
                assert self.telemetry is not None
                result = {
                    "status": "FAIL",
                    "reason": "setup_click_exception",
                    "click": click,
                    "setup": _compact(setup),
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "next_step": (
                        "A setup adjustment click raised before visual setup "
                        "could be reverified. Inspect the traceback/window "
                        "evidence and rerun verify_setup before starting a "
                        "Lightning War timeline."
                    ),
                }
                self._record_result_event("setup_click_exception", result)
                return result
            assert self.telemetry is not None
            event_error = self._best_effort_event(
                "setup_click",
                click=click,
                click_result=click_result,
            )
            if event_error is not None:
                setup.setdefault("telemetry_event_errors", []).append(event_error)
            if click_result.get("status") != "OK":
                failure = {
                    "status": "FAIL",
                    "reason": "setup_click_failed",
                    "click": click,
                    "click_result": click_result,
                }
                if event_error is not None:
                    failure.setdefault("telemetry_event_errors", []).append(event_error)
                return failure
        try:
            setup = self._span(
                "verify_setup_after_clicks",
                commands.cmd_verify_setup_screen,
                expected_difficulty=cfg.difficulty,
                advanced_content=cfg.advanced_content,
            )
        except Exception as exc:
            assert self.telemetry is not None
            result = {
                "status": "FAIL",
                "reason": "setup_verification_exception",
                "span": "verify_setup_after_clicks",
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The setup verifier raised after setup adjustments. Inspect "
                    "the traceback/window evidence and rerun verify_setup before "
                    "starting a Lightning War timeline."
                ),
            }
            self._record_result_event("setup_verification_exception", result)
            return result
        if setup.get("status") == "PASS" or cfg.dry_run:
            return setup
        if _focus_retry_warranted(setup):
            time.sleep(0.6)
            try:
                return self._span(
                    "verify_setup_after_clicks_focus_retry",
                    commands.cmd_verify_setup_screen,
                    expected_difficulty=cfg.difficulty,
                    advanced_content=cfg.advanced_content,
                )
            except Exception as exc:
                assert self.telemetry is not None
                result = {
                    "status": "FAIL",
                    "reason": "setup_verification_exception",
                    "span": "verify_setup_after_clicks_focus_retry",
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "next_step": (
                        "The setup verifier raised during post-click focus "
                        "retry. Inspect the traceback/window evidence and "
                        "rerun verify_setup before starting a Lightning War "
                        "timeline."
                    ),
                }
                self._record_result_event("setup_verification_exception", result)
                return result
        return setup

    def _run_preflight(self, commands: Any, *, label: str) -> dict[str, Any]:
        try:
            result = self._span(
                label,
                commands.cmd_lightning_preflight,
                profile=self.config.profile,
                set_fast_bridge=False,
                advanced_content=self.config.advanced_content,
            )
        except Exception as exc:
            assert self.telemetry is not None
            blocked = {
                "status": "BLOCKED",
                "reason": "preflight_exception",
                "span": label,
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The Lightning preflight helper raised before a combat "
                    "burst. Inspect the traceback/output evidence and rerun "
                    "preflight before continuing the timeline."
                ),
            }
            self._record_result_event("preflight_exception", blocked)
            return blocked
        stop_evidence = self._blocking_stop_evidence(result)
        stop_token = stop_evidence.get("token") if stop_evidence is not None else None
        blocking_warning = _blocking_preflight_warning(result)
        if result.get("status") == "FAIL" or stop_token or blocking_warning:
            reason = (
                _stop_sign_block_reason(
                    stop_token,
                    blocking_warning,
                    stop_evidence,
                )
                or "preflight_failed"
            )
            return {
                "status": "BLOCKED",
                "reason": reason,
                "stop_token": stop_token,
                "stop_evidence": stop_evidence,
                "blocking_warning": blocking_warning,
                "next_step": _stop_sign_next_step(reason),
                "result": _compact(result),
            }
        return {"status": "OK", "result": result}

    def _handle_visible_panel(
        self,
        commands: Any,
        *,
        segment_index: int,
    ) -> dict[str, Any]:
        try:
            visible = self._span(
                "classify_visible",
                commands.cmd_lightning_ui,
                control="classify",
                include_ocr=False,
            )
        except Exception as exc:
            assert self.telemetry is not None
            result = {
                "status": "BLOCKED",
                "reason": "screen_classification_exception",
                "span": "classify_visible",
                "handled": False,
                "segment_index": segment_index,
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The visible-screen classifier raised before panel "
                    "handling. Preserve the traceback/window evidence and "
                    "rerun classification before any UI click or combat burst."
                ),
            }
            self._record_result_event("screen_classification_exception", result)
            return result
        visible_name = _visible_ui_name(visible)
        if visible_name in OCR_AUDIT_PANEL_UIS:
            try:
                visible = self._span(
                    "classify_visible_ocr_audit",
                    commands.cmd_lightning_ui,
                    control="classify",
                    include_ocr=True,
                )
            except Exception as exc:
                assert self.telemetry is not None
                result = {
                    "status": "BLOCKED",
                    "reason": "screen_ocr_audit_exception",
                    "span": "classify_visible_ocr_audit",
                    "handled": False,
                    "visible_name": visible_name,
                    "visible_ui": _compact(visible),
                    "segment_index": segment_index,
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "next_step": (
                        "A terminal, reward, mission-preview, or system-prompt "
                        "screen needed an OCR safety audit, but the audit "
                        "classifier raised. Inspect the visible screen before "
                        "any UI click or combat burst."
                    ),
                }
                self._record_result_event("screen_ocr_audit_exception", result)
                return result
            visible_name = _visible_ui_name(visible)

        def panel_exception_block(
            reason: str,
            *,
            label: str,
            exc: Exception,
            handled: bool,
            next_step: str,
        ) -> dict[str, Any]:
            result = {
                "status": "BLOCKED",
                "reason": reason,
                "span": label,
                "handled": handled,
                "visible_name": visible_name,
                "visible_ui": _compact(visible),
                "segment_index": segment_index,
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": next_step,
            }
            assert self.telemetry is not None
            self._record_result_event(reason, result)
            return result

        if _visible_refines_to_live_combat(visible):
            return {
                "status": "NO_ACTION",
                "reason": "bridge_refined_live_combat",
                "handled": False,
                "visible_ui": _compact(visible),
                "visible_name": visible_name,
            }
        if not isinstance(visible, dict) or visible.get("status") != "OK":
            return {
                "status": "BLOCKED",
                "reason": "screen_classification_failed",
                "handled": False,
                "visible_name": visible_name,
                "visible_ui": _compact(visible),
                "segment_index": segment_index,
                "next_step": (
                    "The screen classifier failed. Stop before clicking or "
                    "starting a combat burst, preserve the screenshot/error "
                    "evidence, and rerun only after the visible state is known."
                ),
            }
        if _paused_active_mission_deployment_handoff(visible):
            return {
                "status": "NO_ACTION",
                "reason": "paused_active_mission_deployment_handoff",
                "handled": False,
                "visible_name": visible_name,
                "visible_ui": _compact(visible),
                "segment_index": segment_index,
            }
        terminal_evidence = _terminal_outcome_evidence(visible)
        if terminal_evidence is not None:
            return {
                "status": "BLOCKED",
                "reason": "terminal_outcome_visible",
                "visible_name": visible_name,
                "terminal_evidence": terminal_evidence,
                "visible_ui": _compact(visible),
                "next_step": (
                    "Stop before clearing this panel. Inspect the visible "
                    "terminal/failed-objective evidence and decide whether "
                    "the Lightning War timeline must be abandoned."
                ),
            }
        terminal_ui_evidence = _terminal_visible_ui_evidence(visible)
        if terminal_ui_evidence is not None:
            return {
                "status": "BLOCKED",
                "reason": "terminal_visible_ui",
                "visible_name": visible_name,
                "terminal_evidence": terminal_ui_evidence,
                "visible_ui": _compact(visible),
                "next_step": (
                    "A terminal-looking panel is visible without a clean OCR "
                    "audit. Inspect the screenshot before clearing it or "
                    "continuing the Lightning War timeline."
                ),
            }
        if visible_name in SYSTEM_BLOCKING_UIS:
            prompt_click = self._click_system_prompt_allow(
                visible,
                commands=commands,
            )
            if prompt_click.get("status") == "OK":
                try:
                    post_visible = self._span(
                        "classify_after_system_prompt_allow",
                        commands.cmd_lightning_ui,
                        control="classify",
                        include_ocr=True,
                    )
                except Exception as exc:
                    return panel_exception_block(
                        "system_prompt_allow_post_classify_exception",
                        label="classify_after_system_prompt_allow",
                        exc=exc,
                        handled=True,
                        next_step=(
                            "The macOS Allow prompt was clicked, but the "
                            "follow-up classifier raised. Inspect the visible "
                            "screen before any game input."
                        ),
                    )
                return {
                    "status": "OK",
                    "reason": "external_system_prompt_allowed",
                    "handled": True,
                    "visible_name": visible_name,
                    "visible_ui": _compact(visible),
                    "system_prompt_allow": _compact(prompt_click),
                    "post_visible_ui": _compact(post_visible),
                    "segment_index": segment_index,
                }
            return {
                "status": "BLOCKED",
                "reason": "external_system_prompt_visible",
                "visible_name": visible_name,
                "visible_ui": _compact(visible),
                "system_prompt_allow": _compact(prompt_click),
                "next_step": (
                    "A macOS privacy prompt is covering the game, but the "
                    "Allow button was not OCR-clickable or the prompt remained "
                    "after clicking. Inspect before any game input."
                ),
            }
        if visible_name in UNEXPECTED_MENU_UIS:
            return {
                "status": "BLOCKED",
                "reason": "unexpected_menu_or_setup_visible_mid_run",
                "visible_name": visible_name,
                "visible_ui": _compact(visible),
                "next_step": (
                    "Inspect the screen and session state before restarting. "
                    "The runner will not click title/setup controls after a "
                    "Lightning War session is underway."
                ),
            }
        if visible_name == "island_complete_leave":
            handled = self._handle_shop_then_leave(commands, visible)
            handled["handled"] = True
            handled["segment_index"] = segment_index
            return handled
        if visible_name == "mission_preview_panel":
            recommended = str(visible.get("recommended_control") or "")
            if recommended == "dialogue_textbox":
                try:
                    handled = self._span(
                        "clear_mission_preview_dialogue",
                        commands.cmd_lightning_ui,
                        control="dialogue_textbox",
                        dry_run=self.config.dry_run,
                    )
                except Exception as exc:
                    return panel_exception_block(
                        "mission_preview_dialogue_clear_exception",
                        label="clear_mission_preview_dialogue",
                        exc=exc,
                        handled=False,
                        next_step=(
                            "The mission-preview dialogue clear helper raised. "
                            "Do not click Start Mission from this preview; "
                            "inspect the visible panel and route evidence first."
                        ),
                    )
                result = {
                    "status": handled.get("status", "ERROR"),
                    "reason": handled.get("reason", "mission_preview_dialogue_cleared"),
                    "handled": True,
                    "visible_ui": _compact(visible),
                    "handle_result": _compact(handled),
                    "segment_index": segment_index,
                }
                if handled.get("status") == "DRY_RUN":
                    return result
                if handled.get("status") != "OK":
                    return result
                try:
                    post_visible = self._span(
                        "classify_after_mission_preview_dialogue",
                        commands.cmd_lightning_ui,
                        control="classify",
                        include_ocr=True,
                    )
                except Exception as exc:
                    exception_block = panel_exception_block(
                        "mission_preview_dialogue_post_classify_exception",
                        label="classify_after_mission_preview_dialogue",
                        exc=exc,
                        handled=True,
                        next_step=(
                            "The classifier raised after clearing mission-preview "
                            "dialogue. Preserve the visible evidence and do not "
                            "confirm deployment or Start Mission until the route "
                            "handoff is reverified."
                        ),
                    )
                    exception_block["handle_result"] = _compact(handled)
                    return exception_block
                result["post_visible_ui"] = _compact(post_visible)
                post_name = _visible_ui_name(post_visible)
                post_terminal_evidence = _terminal_outcome_evidence(post_visible)
                if post_name in SYSTEM_BLOCKING_UIS:
                    result.update(
                        {
                            "status": "BLOCKED",
                            "reason": "external_system_prompt_visible",
                        }
                    )
                elif post_terminal_evidence is not None:
                    result.update(
                        {
                            "status": "BLOCKED",
                            "reason": "terminal_outcome_visible",
                            "terminal_evidence": post_terminal_evidence,
                        }
                    )
                elif post_visible.get("status") != "OK":
                    result.update(
                        {
                            "status": "BLOCKED",
                            "reason": "mission_preview_dialogue_post_classify_failed",
                        }
                    )
                elif (
                    terminal_ui_evidence := _terminal_visible_ui_evidence(post_visible)
                ) is not None:
                    result.update(
                        {
                            "status": "BLOCKED",
                            "reason": "terminal_visible_ui",
                            "terminal_evidence": terminal_ui_evidence,
                        }
                    )
                elif post_name in UNEXPECTED_MENU_UIS:
                    result.update(
                        {
                            "status": "BLOCKED",
                            "reason": "mission_preview_dialogue_unexpected_screen",
                        }
                    )
                elif post_name == "deployment_screen":
                    result.update(
                        {
                            "status": "BLOCKED",
                            "reason": "mission_preview_dialogue_started_mission",
                            "next_step": (
                                "Dialogue clearing unexpectedly reached deployment. "
                                "Inspect route evidence before confirming deployment."
                            ),
                        }
                    )
                return result
            return {
                "status": "BLOCKED",
                "reason": "mission_preview_requires_route_validation",
                "handled": False,
                "visible_name": visible_name,
                "visible_ui": _compact(visible),
                "recommended_control": recommended or None,
                "segment_index": segment_index,
                "next_step": (
                    "Do not click Start Mission from an already-visible preview "
                    "without route proof. Let lightning_segment route auto-start "
                    "from a verified island map, or inspect route evidence first."
                ),
            }
        if visible_name in SAFE_PANEL_UIS:
            try:
                handled = self._span(
                    "handle_visible_panel",
                    commands.cmd_lightning_ui,
                    control="handle_screen",
                    dry_run=self.config.dry_run,
                )
            except Exception as exc:
                return panel_exception_block(
                    "visible_panel_handle_exception",
                    label="handle_visible_panel",
                    exc=exc,
                    handled=False,
                    next_step=(
                        "The safe-panel handler raised before the panel was "
                        "cleared. Preserve the visible evidence and rerun "
                        "classification before any more UI or combat commands."
                    ),
                )
            return {
                "status": handled.get("status", "ERROR"),
                "reason": handled.get("reason", "visible_panel_handled"),
                "handled": True,
                "visible_ui": _compact(visible),
                "handle_result": _compact(handled),
                "segment_index": segment_index,
            }
        return {
            "status": "NO_ACTION",
            "reason": "no_known_panel_visible",
            "handled": False,
            "visible_ui": _compact(visible),
            "visible_name": visible_name,
        }

    def _handle_post_segment_panel(
        self,
        commands: Any,
        *,
        segment: dict[str, Any],
        segment_index: int,
    ) -> dict[str, Any] | None:
        status = str(segment.get("status") or "")
        reason = str(segment.get("reason") or "")
        visible_name = _visible_ui_name(segment)
        expected_panel_name = (
            visible_name
            if visible_name in SAFE_PANEL_UIS or visible_name == "island_complete_leave"
            else _safe_panel_evidence_visible_name(segment)
        )
        if not (
            "PANEL" in status.upper()
            or "PANEL" in reason.upper()
            or reason in {"visible_panel_not_auto_clearable"}
            or reason in SEGMENT_SAFE_PANEL_RECOVERY_REASONS
            or expected_panel_name in SAFE_PANEL_UIS
            or expected_panel_name == "island_complete_leave"
        ):
            return None
        if _must_act_now(segment):
            return None

        panel = self._handle_visible_panel(commands, segment_index=segment_index)
        if panel.get("status") in {"BLOCKED", "ERROR"}:
            assert self.telemetry is not None
            event_error = self._best_effort_event(
                "post_segment_panel_blocked",
                segment_index=segment_index,
                status=panel.get("status"),
                reason=panel.get("reason"),
                visible_name=panel.get("visible_name") or _visible_ui_name(panel),
            )
            if event_error is not None:
                panel.setdefault("telemetry_event_errors", []).append(event_error)
            return panel
        if not panel.get("handled"):
            if (
                panel.get("visible_name") == "pause_menu"
                and expected_panel_name is not None
                and (
                    expected_panel_name in SAFE_PANEL_UIS
                    or expected_panel_name == "island_complete_leave"
                )
            ):
                panel = self._handle_paused_segment_panel(
                    commands,
                    segment_index=segment_index,
                    expected_visible_name=expected_panel_name,
                    paused_panel=panel,
                )
                if panel.get("status") in {"BLOCKED", "ERROR"}:
                    assert self.telemetry is not None
                    event_error = self._best_effort_event(
                        "post_segment_panel_blocked",
                        segment_index=segment_index,
                        status=panel.get("status"),
                        reason=panel.get("reason"),
                        visible_name=panel.get("visible_name") or _visible_ui_name(panel),
                    )
                    if event_error is not None:
                        panel.setdefault("telemetry_event_errors", []).append(event_error)
                    return panel
                if not panel.get("handled"):
                    return None
            else:
                return None
        assert self.telemetry is not None
        event_error = self._best_effort_event(
            "post_segment_panel_handled",
            segment_index=segment_index,
            status=panel.get("status"),
            reason=panel.get("reason"),
            visible_name=panel.get("visible_name") or _visible_ui_name(panel),
        )
        if event_error is not None:
            panel.setdefault("telemetry_event_errors", []).append(event_error)
        return panel

    def _handle_paused_segment_panel(
        self,
        commands: Any,
        *,
        segment_index: int,
        expected_visible_name: str,
        paused_panel: dict[str, Any],
    ) -> dict[str, Any]:
        resume_control = "menu_continue"
        try:
            resume = self._span(
                "resume_paused_segment_panel",
                commands.cmd_lightning_ui,
                control=resume_control,
                dry_run=self.config.dry_run,
            )
        except Exception as exc:
            assert self.telemetry is not None
            result = {
                "status": "BLOCKED",
                "reason": "resume_paused_segment_panel_exception",
                "span": "resume_paused_segment_panel",
                "handled": False,
                "visible_name": "pause_menu",
                "expected_visible_name": expected_visible_name,
                "paused_panel": _compact(paused_panel),
                "resume_control": resume_control,
                "segment_index": segment_index,
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The pause-menu resume helper raised before revealing the "
                    "expected post-segment panel. Inspect the traceback/window "
                    "evidence and regain a verified pause or panel state before "
                    "any more UI clicks."
                ),
            }
            self._record_result_event(
                "resume_paused_segment_panel_exception",
                result,
            )
            return result
        if resume.get("status") not in {"OK", "DRY_RUN"}:
            return {
                "status": "BLOCKED",
                "reason": "resume_paused_segment_panel_failed",
                "handled": False,
                "visible_name": "pause_menu",
                "expected_visible_name": expected_visible_name,
                "paused_panel": _compact(paused_panel),
                "resume_control": resume_control,
                "resume_result": _compact(resume),
                "segment_index": segment_index,
            }
        if resume.get("status") == "DRY_RUN":
            return {
                "status": "DRY_RUN",
                "reason": "would_resume_paused_segment_panel",
                "handled": True,
                "visible_name": expected_visible_name,
                "expected_visible_name": expected_visible_name,
                "paused_panel": _compact(paused_panel),
                "resume_control": resume_control,
                "resume_result": _compact(resume),
                "segment_index": segment_index,
            }

        panel_chain: list[dict[str, Any]] = []
        panel = self._handle_visible_panel(commands, segment_index=segment_index)
        for chain_index in range(6):
            panel["expected_visible_name"] = expected_visible_name
            panel["paused_panel"] = _compact(paused_panel)
            panel["resume_control"] = resume_control
            panel["resume_result"] = _compact(resume)
            panel["panel_chain_index"] = chain_index
            panel_chain.append(_compact(panel))
            if panel.get("status") in {"BLOCKED", "ERROR"}:
                panel["panel_chain"] = panel_chain
                return panel
            if not panel.get("handled"):
                ensure_pause = self._ensure_pause(commands)
                if panel.get("visible_name") == "combat_screen" or _visible_refines_to_live_combat(
                    panel.get("visible_ui")
                ):
                    return {
                        "status": "NO_ACTION",
                        "reason": "paused_segment_panel_revealed_combat_screen",
                        "handled": False,
                        "visible_name": panel.get("visible_name") or _visible_ui_name(panel),
                        "expected_visible_name": expected_visible_name,
                        "paused_panel": _compact(paused_panel),
                        "resume_control": resume_control,
                        "resume_result": _compact(resume),
                        "panel": _compact(panel),
                        "panel_chain": panel_chain,
                        "ensure_pause": _compact(ensure_pause),
                        "segment_index": segment_index,
                    }
                return {
                    "status": "BLOCKED",
                    "reason": "expected_segment_panel_not_visible_after_resume",
                    "handled": False,
                    "visible_name": panel.get("visible_name") or _visible_ui_name(panel),
                    "expected_visible_name": expected_visible_name,
                    "paused_panel": _compact(paused_panel),
                    "resume_control": resume_control,
                    "resume_result": _compact(resume),
                    "panel": _compact(panel),
                    "panel_chain": panel_chain,
                    "ensure_pause": _compact(ensure_pause),
                    "segment_index": segment_index,
                }

            ensure_pause = self._ensure_pause(commands)
            panel["ensure_pause"] = _compact(ensure_pause)
            panel_chain[-1] = _compact(panel)
            if ensure_pause.get("status") in {"OK", "DRY_RUN"}:
                panel["reason"] = "paused_segment_panel_handled"
                panel["panel_chain"] = panel_chain
                return panel
            if ensure_pause.get("reason") == "visible_panel_should_be_cleared_first":
                panel = self._handle_visible_panel(
                    commands,
                    segment_index=segment_index,
                )
                continue
            return {
                "status": "BLOCKED",
                "reason": "pause_after_segment_panel_failed",
                "handled": True,
                "visible_name": panel.get("visible_name") or _visible_ui_name(panel),
                "expected_visible_name": expected_visible_name,
                "paused_panel": _compact(paused_panel),
                "resume_control": resume_control,
                "resume_result": _compact(resume),
                "panel": _compact(panel),
                "panel_chain": panel_chain,
                "ensure_pause": _compact(ensure_pause),
                "segment_index": segment_index,
            }
        return {
            "status": "BLOCKED",
            "reason": "post_segment_panel_chain_not_cleared",
            "handled": True,
            "visible_name": panel.get("visible_name") or _visible_ui_name(panel),
            "expected_visible_name": expected_visible_name,
            "paused_panel": _compact(paused_panel),
            "resume_control": resume_control,
            "resume_result": _compact(resume),
            "panel": _compact(panel),
            "panel_chain": panel_chain,
            "segment_index": segment_index,
            "next_step": (
                "A safe-looking post-segment panel chain exceeded the automatic "
                "clear limit. Inspect the visible screen before clicking more "
                "continues."
            ),
        }

    def _handle_shop_then_leave(self, commands: Any, visible: dict[str, Any]) -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        before = _grid_state(self.config.profile)
        if before.get("status") != "OK":
            return {
                "status": "BLOCKED",
                "reason": "grid_state_unavailable_before_shop",
                "visible_ui": _compact(visible),
                "grid_state": before,
                "steps": steps,
            }

        def shop_exception_block(
            reason: str,
            *,
            label: str,
            step_control: str,
            grid_snapshot: dict[str, Any],
            exc: Exception,
        ) -> dict[str, Any]:
            exception_evidence = {
                "status": "EXCEPTION",
                "span": label,
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            steps.append({"control": step_control, "result": exception_evidence})
            block = _shop_block(
                reason,
                grid_snapshot,
                steps,
                visible,
                exception_evidence=exception_evidence,
            )
            assert self.telemetry is not None
            self._record_result_event(reason, block)
            return block

        def shop_ui(
            *,
            label: str,
            ui_control: str,
            step_control: str,
            grid_snapshot: dict[str, Any],
            exception_reason: str,
            include_ocr: bool = False,
        ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
            try:
                kwargs: dict[str, Any] = {"control": ui_control}
                if include_ocr:
                    kwargs["include_ocr"] = True
                else:
                    kwargs["dry_run"] = self.config.dry_run
                result = self._span(label, commands.cmd_lightning_ui, **kwargs)
            except Exception as exc:
                return None, shop_exception_block(
                    exception_reason,
                    label=label,
                    step_control=step_control,
                    grid_snapshot=grid_snapshot,
                    exc=exc,
                )
            steps.append({"control": step_control, "result": _compact(result)})
            return result, None

        grid = int(before["grid_power"])
        grid_max = int(before["grid_power_max"])
        if grid < grid_max:
            spend, block = shop_ui(
                label="shop_spend_reputation",
                ui_control="spend_reputation",
                step_control="spend_reputation",
                grid_snapshot=before,
                exception_reason="spend_reputation_exception",
            )
            if block is not None:
                return block
            assert spend is not None
            if spend.get("status") != "OK":
                return _shop_block("spend_reputation_failed", before, steps, visible)

            purchases = 0
            max_purchases = max(1, grid_max - grid)
            while purchases < max_purchases:
                current = _grid_state(self.config.profile)
                if current.get("status") == "OK" and int(current["grid_power"]) >= int(
                    current["grid_power_max"]
                ):
                    break
                if current.get("status") != "OK":
                    return _shop_block(
                        "grid_state_unavailable_during_shop",
                        current,
                        steps,
                        visible,
                    )
                try:
                    buy = self._span(
                        "shop_buy_grid_power",
                        commands.cmd_lightning_ui,
                        control="shop_grid_power",
                        dry_run=self.config.dry_run,
                    )
                except Exception as exc:
                    return shop_exception_block(
                        "shop_grid_power_click_exception",
                        label="shop_buy_grid_power",
                        step_control="shop_grid_power",
                        grid_snapshot=current,
                        exc=exc,
                    )
                purchases += 1
                time.sleep(0.2)
                after = _grid_state(self.config.profile)
                step = {
                    "control": "shop_grid_power",
                    "result": _compact(buy),
                    "before": current,
                    "after": after,
                }
                steps.append(step)
                if buy.get("status") != "OK":
                    return _shop_block("shop_grid_power_click_failed", after, steps, visible)
                if after.get("status") != "OK":
                    return _shop_block("grid_state_unavailable_after_buy", after, steps, visible)
                if int(after["grid_power"]) <= int(current["grid_power"]):
                    return _shop_block("shop_grid_purchase_unverified", after, steps, visible)

            final_grid = _grid_state(self.config.profile)
            if final_grid.get("status") != "OK" or int(final_grid["grid_power"]) < int(
                final_grid["grid_power_max"]
            ):
                return _shop_block("grid_not_full_after_shop", final_grid, steps, visible)

            shop_continue, block = shop_ui(
                label="shop_continue",
                ui_control="shop_continue",
                step_control="shop_continue",
                grid_snapshot=final_grid,
                exception_reason="shop_continue_exception",
            )
            if block is not None:
                return block
            assert shop_continue is not None
            if shop_continue.get("status") != "OK":
                return _shop_block("shop_continue_failed", final_grid, steps, visible)
            leave_screen, block = shop_ui(
                label="classify_after_shop_continue",
                ui_control="classify",
                step_control="classify_after_shop_continue",
                grid_snapshot=final_grid,
                exception_reason="shop_exit_classification_exception",
                include_ocr=True,
            )
            if block is not None:
                return block
            assert leave_screen is not None
            leave_visible_name = _visible_ui_name(leave_screen)
            leave_terminal_evidence = _terminal_outcome_evidence(leave_screen)
            if leave_visible_name in SYSTEM_BLOCKING_UIS:
                return _shop_block(
                    "external_system_prompt_visible",
                    final_grid,
                    steps,
                    visible,
                    observed_visible_ui=_compact(leave_screen),
                )
            if leave_terminal_evidence is not None:
                return _shop_block(
                    "shop_exit_terminal_outcome_visible",
                    final_grid,
                    steps,
                    visible,
                    observed_visible_ui=_compact(leave_screen),
                    terminal_evidence=leave_terminal_evidence,
                )
            if leave_screen.get("status") != "OK":
                return _shop_block(
                    "shop_exit_classification_failed",
                    final_grid,
                    steps,
                    visible,
                    observed_visible_ui=_compact(leave_screen),
                )
            if leave_visible_name != "island_complete_leave":
                return _shop_block(
                    "shop_exit_not_at_leave_screen",
                    final_grid,
                    steps,
                    visible,
                    observed_visible_ui=_compact(leave_screen),
                )
        else:
            final_grid = before

        leave, block = shop_ui(
            label="leave_island",
            ui_control="leave_island",
            step_control="leave_island",
            grid_snapshot=final_grid,
            exception_reason="leave_island_exception",
        )
        if block is not None:
            return block
        assert leave is not None
        if leave.get("status") != "OK":
            return _shop_block("leave_island_failed", final_grid, steps, visible)
        confirm, block = shop_ui(
            label="leave_confirm_yes",
            ui_control="leave_confirm_yes",
            step_control="leave_confirm_yes",
            grid_snapshot=final_grid,
            exception_reason="leave_confirm_exception",
        )
        if block is not None:
            return block
        assert confirm is not None
        if confirm.get("status") != "OK":
            return _shop_block("leave_confirm_failed", final_grid, steps, visible)

        session, session_block = self._load_session_or_block(
            commands,
            "post_leave_confirm_session",
        )
        if session_block is not None:
            return _shop_block(
                "post_leave_confirm_session_load_exception",
                final_grid,
                steps,
                visible,
                exception_evidence=session_block,
            )
        completion_record = _record_island_completion_after_leave_confirm(session)
        steps.append({
            "control": "record_island_completion_after_leave_confirm",
            "result": completion_record,
        })
        if completion_record.get("status") != "OK":
            return _shop_block(
                "post_leave_completion_record_failed",
                final_grid,
                steps,
                visible,
                exception_evidence=completion_record,
            )
        completed_after_leave = list(completion_record.get("islands_completed") or [])
        if len(completed_after_leave) >= int(self.config.target_islands):
            snap_fn = getattr(commands, "cmd_lightning_snap_pause", None)
            post_leave_pause = None
            if callable(snap_fn):
                try:
                    post_leave_pause = self._span(
                        "post_target_leave_confirm_snap_pause",
                        snap_fn,
                        label="post_target_leave_confirm",
                        note=(
                            "Lightning War target islands completed after "
                            "leave_confirm_yes; capture proof and pause before "
                            "any further map navigation"
                        ),
                        dry_run=self.config.dry_run,
                        run_seconds=0.0,
                        include_ocr=True,
                    )
                except Exception as exc:
                    post_leave_pause = {
                        "status": "EXCEPTION",
                        "exception_type": type(exc).__name__,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                steps.append({
                    "control": "post_target_leave_confirm_snap_pause",
                    "result": _compact(post_leave_pause),
                })
                if isinstance(post_leave_pause, dict) and post_leave_pause.get("status") not in {
                    "OK",
                    "DRY_RUN",
                }:
                    return _shop_block(
                        "post_target_leave_confirm_pause_failed",
                        final_grid,
                        steps,
                        visible,
                        observed_visible_ui=_compact(post_leave_pause),
                    )
            return {
                "status": "OK",
                "reason": "target_islands_completed_after_leave_confirm",
                "visible_ui": _compact(visible),
                "initial_grid": before,
                "final_grid": final_grid,
                "islands_completed": completed_after_leave,
                "session_completion": completion_record,
                "post_leave_pause": _compact(post_leave_pause),
                "achievement_proof_keys": {
                    "steam_or_log": LIGHTNING_WAR_STEAM_KEY,
                    "profile": LIGHTNING_WAR_PROFILE_KEY,
                },
                "steps": steps,
            }

        handoff, block = shop_ui(
            label="classify_after_leave_confirm",
            ui_control="classify",
            step_control="classify_after_leave_confirm",
            grid_snapshot=final_grid,
            exception_reason="post_leave_classification_exception",
            include_ocr=True,
        )
        if block is not None:
            return block
        assert handoff is not None
        handoff_name = _visible_ui_name(handoff)
        handoff_terminal_evidence = _terminal_outcome_evidence(handoff)
        if handoff_name in SYSTEM_BLOCKING_UIS:
            return _shop_block(
                "external_system_prompt_visible",
                final_grid,
                steps,
                visible,
                observed_visible_ui=_compact(handoff),
            )
        if handoff_terminal_evidence is not None:
            return _shop_block(
                "post_leave_terminal_outcome_visible",
                final_grid,
                steps,
                visible,
                observed_visible_ui=_compact(handoff),
                terminal_evidence=handoff_terminal_evidence,
            )
        handoff_terminal_ui_evidence = _terminal_visible_ui_evidence(handoff)
        if handoff_terminal_ui_evidence is not None:
            return _shop_block(
                "post_leave_terminal_visible_ui",
                final_grid,
                steps,
                visible,
                observed_visible_ui=_compact(handoff),
                terminal_evidence=handoff_terminal_ui_evidence,
            )
        if handoff.get("status") != "OK":
            return _shop_block(
                "post_leave_classification_failed",
                final_grid,
                steps,
                visible,
                observed_visible_ui=_compact(handoff),
            )
        if handoff_name in UNEXPECTED_MENU_UIS:
            return _shop_block(
                "post_leave_unexpected_terminal_or_menu",
                final_grid,
                steps,
                visible,
                observed_visible_ui=_compact(handoff),
            )
        session, session_block = self._load_session_or_block(
            commands,
            "post_leave_handoff_session",
            observed_visible_ui=_compact(handoff),
        )
        if session_block is not None:
            return _shop_block(
                "post_leave_session_load_exception",
                final_grid,
                steps,
                visible,
                observed_visible_ui=_compact(handoff),
                exception_evidence=session_block,
            )
        completed = _completed_islands(session)
        if handoff_name == "island_map_or_unknown" and len(completed) < int(
            self.config.target_islands
        ):
            return _shop_block(
                "post_leave_handoff_ambiguous_before_target",
                final_grid,
                steps,
                visible,
                observed_visible_ui=_compact(handoff),
            )
        if handoff_name not in POST_LEAVE_HANDOFF_UIS:
            return _shop_block(
                "post_leave_handoff_unverified",
                final_grid,
                steps,
                visible,
                observed_visible_ui=_compact(handoff),
            )

        return {
            "status": "OK",
            "reason": "grid_first_shop_then_leave",
            "visible_ui": _compact(visible),
            "initial_grid": before,
            "final_grid": final_grid,
            "post_leave_visible_ui": _compact(handoff),
            "steps": steps,
        }

    def _blocking_stop(self, result: dict[str, Any] | None) -> str | None:
        evidence = self._blocking_stop_evidence(result)
        if evidence is not None:
            return str(evidence["token"])
        return None

    def _blocking_stop_evidence(
        self,
        result: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        return _stop_token_evidence(result, BASELINE_STOP_TOKENS)

    def _pace_gate(
        self,
        session: Any,
        game_seconds: float | None,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        cfg = self.config
        if not cfg.speed_mode or game_seconds is None:
            return None
        deployment_handoff_context = (
            _paused_active_mission_deployment_handoff(context)
            or _segment_visible_deployment_handoff(context)
        )
        route_gate_context = _segment_preview_only_route_gate(context or {})
        completed = _completed_islands(session)
        current_mission = str(getattr(session, "current_mission", "") or "").strip()
        try:
            mission_index = int(getattr(session, "mission_index", 0) or 0)
        except (TypeError, ValueError):
            mission_index = 0
        try:
            current_turn = int(getattr(session, "current_turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        try:
            actions_executed = int(getattr(session, "actions_executed", 0) or 0)
        except (TypeError, ValueError):
            actions_executed = 0
        phase = str(getattr(session, "phase", "") or "").strip()
        mission_gate = float(cfg.mission_segment_gate_seconds)
        mission_number = max(1, mission_index + 1)
        mission_deadline = mission_number * mission_gate
        if (
            not deployment_handoff_context
            and not route_gate_context
            and not completed
            and current_mission
            and mission_index <= 0
            and current_turn <= 1
            and actions_executed <= 0
            and phase in {"combat_player", "combat_enemy", "deployment", "unknown"}
            and float(game_seconds)
            >= float(cfg.first_mission_route_start_gate_seconds)
        ):
            return {
                "reason": "first_mission_deployment_handoff_pace_gate",
                "game_seconds": round(float(game_seconds), 3),
                "game_timer": _format_seconds(game_seconds),
                "gate_seconds": float(cfg.first_mission_route_start_gate_seconds),
                "gate_timer": _format_seconds(
                    cfg.first_mission_route_start_gate_seconds,
                ),
                "islands_completed": completed,
                "current_mission": current_mission,
                "mission_index": mission_index,
                "current_turn": current_turn,
                "actions_executed": actions_executed,
                "phase": phase,
            }
        if (
            current_mission
            and not route_gate_context
            and mission_gate > 0
            and float(game_seconds) >= float(mission_deadline)
        ):
            return {
                "reason": "mission_segment_pace_gate",
                "game_seconds": round(float(game_seconds), 3),
                "game_timer": _format_seconds(game_seconds),
                "gate_seconds": float(mission_deadline),
                "gate_timer": _format_seconds(mission_deadline),
                "mission_gate_seconds": float(mission_gate),
                "mission_gate_timer": _format_seconds(mission_gate),
                "islands_completed": completed,
                "current_mission": current_mission,
                "mission_index": mission_index,
                "mission_number": mission_number,
            }
        if (
            not deployment_handoff_context
            and not completed
            and not current_mission
            and mission_index <= 0
            and float(game_seconds) >= float(cfg.mission_segment_gate_seconds)
        ):
            return {
                "reason": "first_mission_start_pace_gate",
                "game_seconds": round(float(game_seconds), 3),
                "game_timer": _format_seconds(game_seconds),
                "gate_seconds": float(cfg.mission_segment_gate_seconds),
                "gate_timer": _format_seconds(cfg.mission_segment_gate_seconds),
                "islands_completed": completed,
                "current_mission": current_mission,
                "mission_index": mission_index,
            }
        if (
            not deployment_handoff_context
            and not completed
            and not current_mission
            and mission_index <= 0
            and float(game_seconds)
            >= float(cfg.first_mission_route_start_gate_seconds)
        ):
            return {
                "reason": "first_mission_route_start_pace_gate",
                "game_seconds": round(float(game_seconds), 3),
                "game_timer": _format_seconds(game_seconds),
                "gate_seconds": float(cfg.first_mission_route_start_gate_seconds),
                "gate_timer": _format_seconds(
                    cfg.first_mission_route_start_gate_seconds,
                ),
                "islands_completed": completed,
                "current_mission": current_mission,
                "mission_index": mission_index,
            }
        if not completed and float(game_seconds) >= float(cfg.first_island_gate_seconds):
            return {
                "reason": "first_island_pace_gate",
                "game_seconds": round(float(game_seconds), 3),
                "game_timer": _format_seconds(game_seconds),
                "gate_seconds": float(cfg.first_island_gate_seconds),
                "gate_timer": _format_seconds(cfg.first_island_gate_seconds),
                "islands_completed": completed,
                "current_mission": current_mission,
            }
        if (
            len(completed) == 1
            and not current_mission
            and float(game_seconds) >= float(cfg.second_island_start_gate_seconds)
        ):
            return {
                "reason": "second_island_start_pace_gate",
                "game_seconds": round(float(game_seconds), 3),
                "game_timer": _format_seconds(game_seconds),
                "gate_seconds": float(cfg.second_island_start_gate_seconds),
                "gate_timer": _format_seconds(cfg.second_island_start_gate_seconds),
                "islands_completed": completed,
                "current_mission": current_mission,
            }
        return None

    def _record_segment_result(
        self,
        commands: Any,
        segment_index: int,
        segment: dict[str, Any],
    ) -> None:
        assert self.telemetry is not None
        session, session_block = self._load_session_or_block(
            commands,
            "record_segment_result",
            segment_index=segment_index,
        )
        session_summary = (
            _session_summary(session)
            if session_block is None
            else {"status": "ERROR", "session_load": session_block}
        )
        steps = _segment_steps_summary(segment)
        event_error = self._best_effort_event(
            "segment_result",
            segment_index=segment_index,
            mode=self.config.mode,
            status=segment.get("status"),
            reason=segment.get("reason"),
            wall_seconds=segment.get("wall_seconds"),
            steps_attempted=segment.get("steps_attempted"),
            steps=steps,
            game_timer=_timer_label(segment),
            game_seconds=_timer_seconds(segment),
            visible_ui=_visible_ui_name(segment),
            speed_loss_policy=self.config.speed_mode,
            session=session_summary,
        )
        if event_error is not None:
            self.telemetry_event_errors.append(event_error)
        if self.config.speed_mode:
            event_error = self._best_effort_event(
                "speed_phase_timing",
                segment_index=segment_index,
                phase=_speed_phase_label(
                    session,
                    segment,
                    target_islands=self.config.target_islands,
                ),
                island_number=_speed_island_number(
                    session,
                    target_islands=self.config.target_islands,
                ),
                completed_island_count=len(_completed_islands(session)),
                current_island=getattr(session, "current_island", None),
                current_mission=getattr(session, "current_mission", None),
                mission_index=getattr(session, "mission_index", None),
                status=segment.get("status"),
                reason=segment.get("reason"),
                wall_seconds=segment.get("wall_seconds"),
                steps_attempted=segment.get("steps_attempted"),
                game_timer=_timer_label(segment),
                game_seconds=_timer_seconds(segment),
                visible_ui=_visible_ui_name(segment),
                combat_turns=_segment_combat_timing_summary(segment),
            )
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)

    @staticmethod
    def _route_probe_cache_key(entry: dict[str, Any]) -> str:
        signature = entry.get("signature")
        if not isinstance(signature, dict):
            signature = entry
        return repr(sorted((str(key), repr(value)) for key, value in signature.items()))

    @staticmethod
    def _normalize_route_probe_cache_entry(entry: dict[str, Any]) -> dict[str, Any]:
        out = dict(entry)
        signature = out.get("signature")
        if isinstance(signature, dict):
            signature = dict(signature)
            out["signature"] = signature
        else:
            signature = {
                key: out.get(key)
                for key in (
                    "index",
                    "first_island",
                    "route_routing",
                    "mission_index",
                    "label_key",
                    "route_click_source",
                    "window_x",
                    "window_y",
                    "visual_region_window_x",
                    "visual_region_window_y",
                )
                if out.get(key) is not None
            }
            out["signature"] = signature
        if (
            not signature.get("route_routing")
            and not out.get("route_routing")
            and signature.get("first_island")
            and signature.get("mission_index") is not None
        ):
            signature["route_routing"] = "lightning_war"
            out["route_routing"] = "lightning_war"
        return out

    @classmethod
    def _merge_route_probe_cache_entry(
        cls,
        cache: list[dict[str, Any]],
        entry: dict[str, Any],
        *,
        cap: int = 12,
    ) -> list[dict[str, Any]]:
        entry = cls._normalize_route_probe_cache_entry(entry)
        key = cls._route_probe_cache_key(entry)
        merged = [
            cls._normalize_route_probe_cache_entry(item)
            for item in cache
            if isinstance(item, dict)
        ]
        for existing in merged:
            if cls._route_probe_cache_key(existing) == key:
                existing_signature = existing.get("signature")
                entry_signature = entry.get("signature")
                if isinstance(existing_signature, dict) and isinstance(entry_signature, dict):
                    existing_signature.update(
                        {
                            key: value
                            for key, value in entry_signature.items()
                            if value is not None
                        }
                    )
                existing["hits"] = int(existing.get("hits") or 1) + int(
                    entry.get("hits") or 1,
                )
                for field in (
                    "last_seen_run_id",
                    "visible_preview_ocr_reason",
                    "auto_route_block_reason",
                    "actual_preview_mission_id",
                    "visible_label",
                    "label_key",
                    "window_x",
                    "window_y",
                    "visual_region_window_x",
                    "visual_region_window_y",
                    "route_click_source",
                ):
                    if entry.get(field) is not None:
                        existing[field] = entry.get(field)
                return merged[:cap]
        merged.insert(0, dict(entry))
        return merged[:cap]

    def _route_probe_cache_for_segment(self, session: Any) -> list[dict[str, Any]]:
        self._rehydrate_recent_route_probe_cache()
        cache: list[dict[str, Any]] = []
        session_cache = getattr(session, "lightning_route_probe_cache", None)
        if isinstance(session_cache, list):
            cache.extend(
                self._normalize_route_probe_cache_entry(item)
                for item in session_cache
                if isinstance(item, dict)
            )
        for entry in reversed(self.route_probe_cache):
            cache = self._merge_route_probe_cache_entry(cache, entry)
        current_run_id = str(getattr(session, "run_id", "") or "").strip()
        if current_run_id:
            cache.sort(
                key=lambda entry: (
                    0
                    if str(entry.get("last_seen_run_id") or "") == current_run_id
                    or str(entry.get("first_seen_run_id") or "") == current_run_id
                    else 1
                ),
            )
        return cache

    def _rehydrate_recent_route_probe_cache(self, *, force: bool = False) -> None:
        if self._route_probe_cache_rehydrated and not force:
            return
        self._route_probe_cache_rehydrated = True
        root = Path(getattr(TelemetryRecorder, "root", Path("recordings")))
        if not root.exists():
            return
        try:
            run_dirs = sorted(
                [path for path in root.iterdir() if path.is_dir()],
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )[:10]
        except OSError:
            return
        loaded = 0
        sources: list[str] = []
        for run_dir in reversed(run_dirs):
            events_path = run_dir / "telemetry" / "events.jsonl"
            try:
                lines = events_path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                if "route_probe_cache_recorded" not in line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("event_type") != "route_probe_cache_recorded":
                    continue
                entry = row.get("entry")
                if not isinstance(entry, dict):
                    continue
                entry = self._normalize_route_probe_cache_entry(entry)
                self.route_probe_cache = self._merge_route_probe_cache_entry(
                    self.route_probe_cache,
                    entry,
                )
                loaded += 1
                sources.append(str(events_path))
        if loaded and self.telemetry is not None:
            event_error = self._best_effort_event(
                "route_probe_cache_rehydrated",
                loaded_entries=loaded,
                cache_size=len(self.route_probe_cache),
                source_count=len(set(sources)),
            )
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)

    def _record_route_probe_cache_entry(
        self,
        commands: Any,
        *,
        segment: dict[str, Any],
        session: Any,
    ) -> dict[str, Any] | None:
        attempts: list[dict[str, Any]] = []
        builder = getattr(commands, "_lightning_route_probe_cache_entry_from_segment", None)
        fallback_builder = None
        if not callable(builder):
            try:
                from src.loop.commands import (
                    _lightning_route_probe_cache_entry_from_segment as fallback_builder,
                )
            except Exception as exc:
                return {
                    "status": "ERROR",
                    "reason": "route_probe_cache_builder_unavailable",
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            builder = fallback_builder
            if not callable(builder):
                return {
                    "status": "ERROR",
                    "reason": "route_probe_cache_builder_unavailable",
                }
        elif fallback_builder is None:
            try:
                from src.loop.commands import (
                    _lightning_route_probe_cache_entry_from_segment as fallback_builder,
                )
            except Exception:
                fallback_builder = None

        compact_segment = _compact(segment)
        segment_inputs: list[tuple[str, Any]] = [("raw", segment)]
        if compact_segment is not segment:
            segment_inputs.append(("compact", compact_segment))

        builder_inputs: list[tuple[str, Any]] = [("commands", builder)]
        if callable(fallback_builder) and fallback_builder is not builder:
            builder_inputs.append(("import", fallback_builder))

        entry: dict[str, Any] | None = None
        for builder_source, candidate_builder in builder_inputs:
            if not callable(candidate_builder):
                continue
            for segment_source, candidate_segment in segment_inputs:
                try:
                    candidate_entry = candidate_builder(candidate_segment, session=session)
                except Exception as exc:
                    attempts.append(
                        {
                            "builder": builder_source,
                            "segment": segment_source,
                            "status": "ERROR",
                            "exception_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    )
                    continue
                attempts.append(
                    {
                        "builder": builder_source,
                        "segment": segment_source,
                        "status": (
                            "OK"
                            if isinstance(candidate_entry, dict)
                            else "NO_ENTRY"
                        ),
                    }
                )
                if isinstance(candidate_entry, dict):
                    entry = candidate_entry
                    break
            if isinstance(entry, dict):
                break
        if not isinstance(entry, dict):
            record = {
                "status": "SKIPPED",
                "reason": "route_probe_cache_entry_not_built",
                "attempts": attempts,
            }
            if self.telemetry is not None:
                event_error = self._best_effort_event(
                    "route_probe_cache_not_recorded",
                    **record,
                )
                if event_error is not None:
                    record.setdefault("telemetry_event_errors", []).append(event_error)
            return record
        self.route_probe_cache = self._merge_route_probe_cache_entry(
            self.route_probe_cache,
            entry,
        )
        save_status: dict[str, Any] = {"status": "SKIPPED"}
        try:
            session.lightning_route_probe_cache = self._merge_route_probe_cache_entry(
                getattr(session, "lightning_route_probe_cache", []) or [],
                entry,
            )
            save = getattr(session, "save", None)
            if callable(save):
                save()
                save_status = {"status": "OK"}
        except Exception as exc:
            save_status = {
                "status": "ERROR",
                "reason": "route_probe_cache_session_save_failed",
                "exception_type": type(exc).__name__,
                "error": str(exc),
            }
        event_error = self._best_effort_event(
            "route_probe_cache_recorded",
            entry=_compact(entry),
            entry_summary=_route_probe_cache_entry_summary(entry),
            cache_size=len(self.route_probe_cache),
            session_save=save_status,
        )
        if event_error is not None:
            self.telemetry_event_errors.append(event_error)
        return {
            "status": "OK",
            "entry": _compact(entry),
            "entry_summary": _route_probe_cache_entry_summary(entry),
            "cache_size": len(self.route_probe_cache),
            "session_save": save_status,
        }

    def _restart_after_initial_preflight_if_safe(
        self,
        commands: Any,
        *,
        preflight: dict[str, Any],
        session: Any,
        attempt_index: int,
    ) -> dict[str, Any] | None:
        cfg = self.config
        if attempt_index >= max(1, int(cfg.max_attempts)):
            return None
        if not _preflight_timer_exceeded(preflight):
            return None
        if not _session_is_lightning_war(session):
            return None

        assert self.telemetry is not None

        def attempt_event(**payload: Any) -> None:
            event_error = self._best_effort_event("attempt_restart", **payload)
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)

        attempt_event(
            status="STARTED",
            reason="preflight_timer_exceeded",
            attempt_index=attempt_index,
            next_attempt_index=attempt_index + 1,
            max_attempts=cfg.max_attempts,
            preflight=_compact(preflight),
        )
        try:
            abandon = self._span(
                "abandon_to_setup",
                commands.cmd_lightning_abandon_to_setup,
                profile=cfg.profile,
                reason=f"preflight_timer_exceeded_attempt_{attempt_index}",
                dry_run=cfg.dry_run,
            )
        except Exception as exc:
            result = {
                "status": "BLOCKED",
                "reason": "abandon_to_setup_exception",
                "attempt_index": attempt_index,
                "span": "abandon_to_setup",
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The abandon-to-setup helper raised while replacing an "
                    "over-budget Lightning War timeline. Inspect the "
                    "traceback/window evidence and regain a verified setup "
                    "or pause-safe state before any more UI clicks."
                ),
            }
            attempt_event(
                status="BLOCKED",
                reason="abandon_to_setup_exception",
                attempt_index=attempt_index,
                exception_type=result["exception_type"],
                error=result["error"],
            )
            return result
        if abandon.get("status") not in {"OK", "DRY_RUN"}:
            attempt_event(
                status="BLOCKED",
                reason="abandon_to_setup_failed",
                attempt_index=attempt_index,
                abandon=_compact(abandon),
            )
            return {
                "status": "BLOCKED",
                "reason": "abandon_to_setup_failed",
                "attempt_index": attempt_index,
                "abandon": _compact(abandon),
            }

        started = self._start_from_setup(commands, "new_game_setup")
        if started.get("status") not in {"OK", "DRY_RUN"}:
            restart_reason = _restart_start_failure_reason(started)
            attempt_event(
                status="BLOCKED",
                reason=restart_reason,
                attempt_index=attempt_index,
                abandon=_compact(abandon),
                start=started,
            )
            return {
                "status": "BLOCKED",
                "reason": restart_reason,
                "attempt_index": attempt_index,
                "abandon": _compact(abandon),
                "start": started,
            }

        setup_proof = self._verify_run_setup(commands)
        if setup_proof.get("status") == "BLOCKED":
            restart_reason = (
                "restart_session_load_exception"
                if setup_proof.get("reason") == "session_load_exception"
                else "restart_setup_state_unverified"
            )
            attempt_event(
                status="BLOCKED",
                reason=restart_reason,
                attempt_index=attempt_index,
                abandon=_compact(abandon),
                start=started,
                setup_proof=setup_proof,
            )
            return {
                "status": "BLOCKED",
                "reason": restart_reason,
                "attempt_index": attempt_index,
                "abandon": _compact(abandon),
                "start": started,
                "setup_proof": setup_proof,
            }

        attempt_event(
            status="OK",
            reason="preflight_timer_attempt_restarted",
            attempt_index=attempt_index,
            next_attempt_index=attempt_index + 1,
            abandon=_compact(abandon),
            start=started,
            setup_proof_status=setup_proof.get("status"),
        )
        return {
            "status": "OK",
            "reason": "preflight_timer_attempt_restarted",
            "attempt_index": attempt_index,
            "next_attempt_index": attempt_index + 1,
            "abandon": _compact(abandon),
            "start": started,
            "setup_proof": setup_proof,
        }

    def _restart_after_initial_pace_gate_if_safe(
        self,
        commands: Any,
        *,
        pace_gate: dict[str, Any],
        session: Any,
        attempt_index: int,
    ) -> dict[str, Any] | None:
        cfg = self.config
        pace_reason = str(pace_gate.get("reason") or "")
        if pace_reason not in {
            "mission_segment_pace_gate",
            "first_mission_start_timer_not_reset",
            "first_mission_start_pace_gate",
            "first_mission_route_start_pace_gate",
            "first_mission_deployment_handoff_pace_gate",
            "first_island_pace_gate",
            "mech_loadout_route_click_miss",
        }:
            return None
        if attempt_index >= max(1, int(cfg.max_attempts)):
            return None
        if not _session_is_lightning_war(session):
            return None

        assert self.telemetry is not None
        next_attempt_index = attempt_index + 1
        next_first_island = _first_island_for_attempt(
            cfg.first_island,
            next_attempt_index,
            speed_mode=cfg.speed_mode,
        )

        def attempt_event(**payload: Any) -> None:
            event_error = self._best_effort_event("attempt_restart", **payload)
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)

        attempt_event(
            status="STARTED",
            reason=pace_reason,
            attempt_index=attempt_index,
            next_attempt_index=next_attempt_index,
            max_attempts=cfg.max_attempts,
            current_first_island=getattr(session, "current_island", None),
            next_first_island=next_first_island,
            pace_gate=pace_gate,
        )
        try:
            abandon = self._span(
                "abandon_to_setup",
                commands.cmd_lightning_abandon_to_setup,
                profile=cfg.profile,
                reason=f"{pace_reason}_attempt_{attempt_index}",
                dry_run=cfg.dry_run,
            )
        except Exception as exc:
            result = {
                "status": "BLOCKED",
                "reason": "abandon_to_setup_exception",
                "attempt_index": attempt_index,
                "span": "abandon_to_setup",
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The abandon-to-setup helper raised while replacing a "
                    "pre-mission Lightning War segment that was already over "
                    "the speed gate. Inspect the traceback/window evidence "
                    "and regain a verified setup or pause-safe state before "
                    "any more UI clicks."
                ),
            }
            attempt_event(
                status="BLOCKED",
                reason="abandon_to_setup_exception",
                attempt_index=attempt_index,
                exception_type=result["exception_type"],
                error=result["error"],
            )
            return result
        if abandon.get("status") not in {"OK", "DRY_RUN"}:
            attempt_event(
                status="BLOCKED",
                reason="abandon_to_setup_failed",
                attempt_index=attempt_index,
                abandon=_compact(abandon),
            )
            return {
                "status": "BLOCKED",
                "reason": "abandon_to_setup_failed",
                "attempt_index": attempt_index,
                "abandon": _compact(abandon),
            }

        started = self._start_from_setup(
            commands,
            "new_game_setup",
            first_island=next_first_island,
        )
        if started.get("status") not in {"OK", "DRY_RUN"}:
            restart_reason = _restart_start_failure_reason(started)
            attempt_event(
                status="BLOCKED",
                reason=restart_reason,
                attempt_index=attempt_index,
                abandon=_compact(abandon),
                start=started,
            )
            return {
                "status": "BLOCKED",
                "reason": restart_reason,
                "attempt_index": attempt_index,
                "abandon": _compact(abandon),
                "start": started,
            }

        setup_proof = self._verify_run_setup(commands)
        if setup_proof.get("status") == "BLOCKED":
            restart_reason = (
                "restart_session_load_exception"
                if setup_proof.get("reason") == "session_load_exception"
                else "restart_setup_state_unverified"
            )
            attempt_event(
                status="BLOCKED",
                reason=restart_reason,
                attempt_index=attempt_index,
                abandon=_compact(abandon),
                start=started,
                setup_proof=setup_proof,
            )
            return {
                "status": "BLOCKED",
                "reason": restart_reason,
                "attempt_index": attempt_index,
                "abandon": _compact(abandon),
                "start": started,
                "setup_proof": setup_proof,
            }

        restarted_reason = f"{pace_reason}_attempt_restarted"
        attempt_event(
            status="OK",
            reason=restarted_reason,
            attempt_index=attempt_index,
            next_attempt_index=next_attempt_index,
            next_first_island=next_first_island,
            abandon=_compact(abandon),
            start=started,
            setup_proof_status=setup_proof.get("status"),
        )
        return {
            "status": "OK",
            "reason": restarted_reason,
            "attempt_index": attempt_index,
            "next_attempt_index": next_attempt_index,
            "next_first_island": next_first_island,
            "abandon": _compact(abandon),
            "start": started,
            "setup_proof": setup_proof,
        }

    def _restart_after_route_gate_if_safe(
        self,
        commands: Any,
        *,
        block: str,
        segment: dict[str, Any],
        session: Any,
        segment_index: int,
        attempt_index: int,
    ) -> dict[str, Any] | None:
        cfg = self.config
        recoverable_stale_map_gate = _segment_recoverable_precombat_route_gate(
            segment,
            block,
        )
        recoverable_deploy_confirm_gate = _segment_has_step_action(
            segment,
            "deploy_confirm_bridge_not_live",
        )
        mission_preview_validation_gate = (
            _segment_mission_preview_route_validation_gate(segment)
        )
        restartable_blocks = {
            "MISSION_PREVIEW_REQUIRES_ROUTE_VALIDATION",
            "ROUTE_AUTO_START_NOT_ALLOWED",
            "ROUTE_MISSION_MISMATCH",
            *RECOVERABLE_PRECOMBAT_ROUTE_GATE_TOKENS,
        }
        if block not in restartable_blocks:
            return None
        if (
            block == "MISSION_PREVIEW_REQUIRES_ROUTE_VALIDATION"
            and not (cfg.speed_mode and mission_preview_validation_gate)
        ):
            return None
        if block in RECOVERABLE_PRECOMBAT_ROUTE_GATE_TOKENS and not recoverable_stale_map_gate:
            return None
        preview_only_gate = _segment_preview_only_route_gate(segment)
        entered_combat = _segment_entered_combat(segment)
        timeout_evidence = _lightning_subcall_timeout_evidence(segment)
        route_start_timeout_gate = (
            timeout_evidence is not None
            and str(timeout_evidence.get("reason") or "")
            == "route_start_subcall_timeout"
            and preview_only_gate
        )
        if timeout_evidence is not None and not route_start_timeout_gate:
            return None
        route_mismatch_warning = _segment_route_mismatch_warning(segment)
        route_mismatch_after_start_gate = (
            block == "ROUTE_MISSION_MISMATCH"
            and _segment_route_mismatch_after_start_gate(segment)
        )
        route_auto_start_gate = block == "ROUTE_AUTO_START_NOT_ALLOWED"
        restartable = (
            cfg.route_auto_start
            and attempt_index < max(1, int(cfg.max_attempts))
            and (
                recoverable_stale_map_gate
                or mission_preview_validation_gate
                or route_auto_start_gate
                or not bool(segment.get("route_start_performed"))
                or preview_only_gate
                or route_mismatch_after_start_gate
            )
            and (
                not entered_combat
                or preview_only_gate
                or route_mismatch_after_start_gate
            )
        )
        if not restartable:
            return None

        assert self.telemetry is not None
        blocked_candidate = _segment_route_auto_start_blocked_candidate(segment)
        next_attempt_index = attempt_index + 1
        next_first_island = _first_island_for_attempt(
            cfg.first_island,
            next_attempt_index,
            speed_mode=cfg.speed_mode,
        )
        def attempt_event(**payload: Any) -> None:
            event_error = self._best_effort_event("attempt_restart", **payload)
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)

        restart_reason = (
            "route_mission_mismatch_after_start"
            if block == "ROUTE_MISSION_MISMATCH"
            else (
                "route_preview_active_mission_before_region_click"
                if block == "ROUTE_PREVIEW_ACTIVE_MISSION_BEFORE_REGION_CLICK"
                else (
                    "mission_preview_requires_route_validation"
                    if block == "MISSION_PREVIEW_REQUIRES_ROUTE_VALIDATION"
                    else (
                    "stale_deploy_confirm_bridge_state"
                    if recoverable_deploy_confirm_gate
                    else "stale_map_deployment_bridge_state"
                    if recoverable_stale_map_gate
                    else "route_auto_start_not_allowed"
                    )
                )
            )
        )
        attempt_event(
            status="STARTED",
            reason=restart_reason,
            attempt_index=attempt_index,
            next_attempt_index=next_attempt_index,
            max_attempts=cfg.max_attempts,
            segment_index=segment_index,
            current_first_island=getattr(session, "current_island", None),
            next_first_island=next_first_island,
            blocked_candidate=blocked_candidate,
            route_mismatch_warning=route_mismatch_warning,
        )
        try:
            abandon = self._span(
                "abandon_to_setup",
                commands.cmd_lightning_abandon_to_setup,
                profile=cfg.profile,
                reason=f"route_gate_attempt_{attempt_index}",
                dry_run=cfg.dry_run,
            )
        except Exception as exc:
            result = {
                "status": "BLOCKED",
                "reason": "abandon_to_setup_exception",
                "attempt_index": attempt_index,
                "span": "abandon_to_setup",
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The abandon-to-setup helper raised while retrying a "
                    "pre-combat route gate. Inspect the traceback/window "
                    "evidence and regain a verified setup or pause-safe state "
                    "before any more UI clicks."
                ),
            }
            attempt_event(
                status="BLOCKED",
                reason="abandon_to_setup_exception",
                attempt_index=attempt_index,
                exception_type=result["exception_type"],
                error=result["error"],
            )
            return result
        if abandon.get("status") not in {"OK", "DRY_RUN"}:
            attempt_event(
                status="BLOCKED",
                reason="abandon_to_setup_failed",
                attempt_index=attempt_index,
                abandon=_compact(abandon),
            )
            return {
                "status": "BLOCKED",
                "reason": "abandon_to_setup_failed",
                "attempt_index": attempt_index,
                "abandon": _compact(abandon),
            }

        started = self._start_from_setup(
            commands,
            "new_game_setup",
            first_island=next_first_island,
        )
        if started.get("status") not in {"OK", "DRY_RUN"}:
            restart_reason = _restart_start_failure_reason(started)
            attempt_event(
                status="BLOCKED",
                reason=restart_reason,
                attempt_index=attempt_index,
                abandon=_compact(abandon),
                start=started,
            )
            return {
                "status": "BLOCKED",
                "reason": restart_reason,
                "attempt_index": attempt_index,
                "abandon": _compact(abandon),
                "start": started,
            }

        setup_proof = self._verify_run_setup(commands)
        if setup_proof.get("status") == "BLOCKED":
            restart_reason = (
                "restart_session_load_exception"
                if setup_proof.get("reason") == "session_load_exception"
                else "restart_setup_state_unverified"
            )
            attempt_event(
                status="BLOCKED",
                reason=restart_reason,
                attempt_index=attempt_index,
                abandon=_compact(abandon),
                start=started,
                setup_proof=setup_proof,
            )
            return {
                "status": "BLOCKED",
                "reason": restart_reason,
                "attempt_index": attempt_index,
                "abandon": _compact(abandon),
                "start": started,
                "setup_proof": setup_proof,
            }

        attempt_event(
            status="OK",
            reason="route_gate_attempt_restarted",
            attempt_index=attempt_index,
            next_attempt_index=next_attempt_index,
            next_first_island=next_first_island,
            abandon=_compact(abandon),
            start=started,
            setup_proof_status=setup_proof.get("status"),
        )
        return {
            "status": "OK",
            "reason": "route_gate_attempt_restarted",
            "attempt_index": attempt_index,
            "next_attempt_index": next_attempt_index,
            "next_first_island": next_first_island,
            "abandon": _compact(abandon),
            "start": started,
            "setup_proof": setup_proof,
        }

    def _progress_key(self, session: Any, segment: dict[str, Any]) -> tuple[Any, ...]:
        return (
            tuple(_completed_islands(session)),
            getattr(session, "mission_index", None),
            getattr(session, "current_mission", None),
            segment.get("status"),
            segment.get("reason"),
            _visible_ui_name(segment),
        )

    def _completion_screen_block(
        self,
        commands: Any,
        *,
        completed: list[str],
        label: str,
        allow_menu_setup: bool = False,
    ) -> dict[str, Any] | None:
        assert self.telemetry is not None

        def proof_event(
            name: str,
            *,
            block: dict[str, Any] | None = None,
            **payload: Any,
        ) -> None:
            event_error = self._best_effort_event(name, **payload)
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)
                if block is not None:
                    block.setdefault("telemetry_event_errors", []).append(event_error)

        try:
            visible = self._span(
                label,
                commands.cmd_lightning_ui,
                control="classify",
                include_ocr=True,
            )
        except Exception as exc:
            block = {
                "reason": "completion_screen_classification_exception",
                "visible_name": None,
                "islands_completed": completed,
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "Session progress says the target island count is complete, "
                    "but the final screen classifier raised. Inspect the "
                    "traceback and visible game state before accepting success."
                ),
            }
            proof_event(
                "completion_screen_proof",
                block=block,
                label=label,
                source="classify",
                status="BLOCKED",
                visible_name=None,
                reason="completion_screen_classification_exception",
                islands_completed=completed,
                exception_type=type(exc).__name__,
                error=str(exc),
            )
            return block
        visible_block = _completion_visible_screen_block(
            visible,
            completed=completed,
            allow_menu_setup=allow_menu_setup,
        )
        proof_event(
            "completion_screen_proof",
            block=visible_block,
            label=label,
            source="classify",
            status="OK" if visible_block is None else "BLOCKED",
            visible_name=_visible_ui_name(visible),
            reason=None if visible_block is None else visible_block.get("reason"),
            islands_completed=completed,
            visible_ui=_compact(visible),
        )
        if visible_block is None:
            proof_block = self._achievement_proof_block(
                commands,
                completed=completed,
                label=label,
                source="classify",
                visible=visible,
            )
            if proof_block is not None:
                return proof_block
            return None
        if visible_block.get("reason") != "completion_pause_menu_visible":
            return visible_block

        peek_fn = getattr(commands, "cmd_lightning_peek", None)
        if not callable(peek_fn):
            visible_block["reason"] = "completion_pause_peek_unavailable"
            visible_block["next_step"] = (
                "Session progress says the target island count is complete, "
                "but the pause menu hides the proof screen and no pause-peek "
                "helper is available. Reveal and classify the underlying "
                "screen before accepting success."
            )
            proof_event(
                "completion_screen_proof",
                block=visible_block,
                label=label,
                source="completion_pause_peek",
                status="BLOCKED",
                visible_name="pause_menu",
                reason=visible_block["reason"],
                islands_completed=completed,
                visible_ui=_compact(visible),
            )
            return visible_block

        def run_completion_peek(**kwargs: Any) -> dict[str, Any]:
            return peek_fn(label=f"{label}_completion", **kwargs)

        try:
            peek = self._span(
                f"{label}_pause_peek",
                run_completion_peek,
                note="completion proof peek before Lightning War success",
                dry_run=self.config.dry_run,
                require_paused=True,
                include_ocr=True,
            )
        except Exception as exc:
            block = {
                "reason": "completion_pause_peek_exception",
                "visible_name": "pause_menu",
                "visible_ui": _compact(visible),
                "islands_completed": completed,
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "Session progress says the target island count is complete, "
                    "but the pause-menu proof helper raised. Inspect the "
                    "traceback and visible pause state before accepting success."
                ),
            }
            proof_event(
                "completion_screen_proof",
                block=block,
                label=label,
                source="completion_pause_peek",
                status="BLOCKED",
                visible_name="pause_menu",
                reason="completion_pause_peek_exception",
                islands_completed=completed,
                visible_ui=_compact(visible),
                exception_type=type(exc).__name__,
                error=str(exc),
            )
            return block
        if peek.get("status") != "OK":
            block = {
                "reason": "completion_pause_peek_failed",
                "visible_name": "pause_menu",
                "visible_ui": _compact(visible),
                "peek": _compact(peek),
                "islands_completed": completed,
                "next_step": (
                    "Session progress says the target island count is complete, "
                    "but the pause-menu peek did not produce a verified paused "
                    "screenshot. Inspect the peek evidence before accepting "
                    "success."
                ),
            }
            proof_event(
                "completion_screen_proof",
                block=block,
                label=label,
                source="completion_pause_peek",
                status="BLOCKED",
                visible_name=_visible_ui_name(peek.get("evidence_ui")) or "pause_menu",
                reason="completion_pause_peek_failed",
                islands_completed=completed,
                visible_ui=_compact(visible),
                peek=_compact(peek),
            )
            return block

        evidence_ui = peek.get("evidence_ui")
        evidence_block = _completion_visible_screen_block(
            evidence_ui,
            completed=completed,
            allow_menu_setup=allow_menu_setup,
            source="completion_pause_peek",
        )
        assert self.telemetry is not None
        proof_event(
            "completion_pause_peek",
            block=evidence_block,
            status="OK" if evidence_block is None else "BLOCKED",
            visible_name=_visible_ui_name(evidence_ui),
            reason=None if evidence_block is None else evidence_block.get("reason"),
            peek=_compact(peek),
        )
        proof_event(
            "completion_screen_proof",
            block=evidence_block,
            label=label,
            source="completion_pause_peek",
            status="OK" if evidence_block is None else "BLOCKED",
            visible_name=_visible_ui_name(evidence_ui),
            reason=None if evidence_block is None else evidence_block.get("reason"),
            islands_completed=completed,
            peek=_compact(peek),
        )
        if evidence_block is not None:
            if evidence_block.get("reason") == "completion_pause_menu_visible":
                evidence_block["reason"] = "completion_pause_peek_unverified"
                evidence_block["next_step"] = (
                    "The pause-menu completion peek still saw a pause menu. "
                    "Inspect the screenshot and regain a visible proof screen "
                    "before accepting success."
                )
            evidence_block["peek"] = _compact(peek)
            return evidence_block
        proof_block = self._achievement_proof_block(
            commands,
            completed=completed,
            label=label,
            source="completion_pause_peek",
            visible=evidence_ui,
            peek=peek,
        )
        if proof_block is not None:
            return proof_block
        return None

    def _reconcile_stale_completion_session(
        self,
        commands: Any,
        session: Any,
        *,
        label: str,
        visible: Any | None,
    ) -> dict[str, Any] | None:
        completed = _completed_islands(session)
        if len(completed) >= int(self.config.target_islands):
            return None
        inferred_count = _inferred_completed_island_count_from_mission_index(session)
        if inferred_count < int(self.config.target_islands):
            return None

        proof_visible = visible
        proof_source = "guard" if visible is not None else "classify"
        proof_peek = None
        if proof_visible is None:
            try:
                proof_visible = self._span(
                    f"{label}_stale_completion_classify",
                    commands.cmd_lightning_ui,
                    control="classify",
                    include_ocr=True,
                )
            except Exception as exc:
                return {
                    "status": "BLOCKED",
                    "reason": "stale_completion_classification_exception",
                    "islands_completed": completed,
                    "inferred_island_count": inferred_count,
                    "session": _session_summary(session),
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "next_step": (
                        "Mission index implies the Lightning War target may "
                        "already be complete, but visible classification raised. "
                        "Inspect the paused screen before any route clicks."
                    ),
                }

        proof_name = _visible_ui_name(proof_visible)
        if proof_name == "pause_menu":
            peek_fn = getattr(commands, "cmd_lightning_peek", None)
            if not callable(peek_fn):
                return {
                    "status": "BLOCKED",
                    "reason": "stale_completion_pause_peek_unavailable",
                    "visible_name": proof_name,
                    "visible_ui": _compact(proof_visible),
                    "islands_completed": completed,
                    "inferred_island_count": inferred_count,
                    "session": _session_summary(session),
                    "next_step": (
                        "Mission index implies the target may be complete, "
                        "but the pause menu hides the proof screen and no peek "
                        "helper is available. Inspect before any map clicks."
                    ),
                }

            def run_completion_peek(**kwargs: Any) -> dict[str, Any]:
                return peek_fn(label=f"{label}_stale_completion", **kwargs)

            try:
                proof_peek = self._span(
                    f"{label}_stale_completion_pause_peek",
                    run_completion_peek,
                    note="stale session completion reconcile before route clicks",
                    dry_run=self.config.dry_run,
                    require_paused=True,
                    include_ocr=True,
                )
            except Exception as exc:
                return {
                    "status": "BLOCKED",
                    "reason": "stale_completion_pause_peek_exception",
                    "visible_name": proof_name,
                    "visible_ui": _compact(proof_visible),
                    "islands_completed": completed,
                    "inferred_island_count": inferred_count,
                    "session": _session_summary(session),
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            if proof_peek.get("status") != "OK":
                return {
                    "status": "BLOCKED",
                    "reason": "stale_completion_pause_peek_failed",
                    "visible_name": proof_name,
                    "visible_ui": _compact(proof_visible),
                    "peek": _compact(proof_peek),
                    "islands_completed": completed,
                    "inferred_island_count": inferred_count,
                    "session": _session_summary(session),
                }
            proof_visible = proof_peek.get("evidence_ui")
            proof_source = "pause_peek"
            proof_name = _visible_ui_name(proof_visible)

        if proof_name in SYSTEM_BLOCKING_UIS:
            return {
                "status": "BLOCKED",
                "reason": "external_system_prompt_visible",
                "visible_name": proof_name,
                "visible_ui": _compact(proof_visible),
                "islands_completed": completed,
                "inferred_island_count": inferred_count,
                "session": _session_summary(session),
            }
        terminal_evidence = _terminal_outcome_evidence(proof_visible)
        if terminal_evidence is not None:
            return {
                "status": "BLOCKED",
                "reason": "stale_completion_terminal_outcome_visible",
                "visible_name": proof_name,
                "visible_ui": _compact(proof_visible),
                "terminal_evidence": terminal_evidence,
                "islands_completed": completed,
                "inferred_island_count": inferred_count,
                "session": _session_summary(session),
            }
        terminal_ui_evidence = _terminal_visible_ui_evidence(proof_visible)
        if terminal_ui_evidence is not None:
            return {
                "status": "BLOCKED",
                "reason": "stale_completion_terminal_visible_ui",
                "visible_name": proof_name,
                "visible_ui": _compact(proof_visible),
                "terminal_evidence": terminal_ui_evidence,
                "islands_completed": completed,
                "inferred_island_count": inferred_count,
                "session": _session_summary(session),
            }
        if proof_name not in COMPLETION_PROOF_UIS and proof_name != "island_map_or_unknown":
            return None

        record = _record_island_completion_after_leave_confirm(
            session,
            reason="stale_completion_reconciled_from_visible_proof",
        )
        record["visible_name"] = proof_name
        record["visible_ui"] = _compact(proof_visible)
        record["source"] = proof_source
        if proof_peek is not None:
            record["peek"] = _compact(proof_peek)
        if record.get("status") != "OK":
            record["status"] = "BLOCKED"
            record["reason"] = "stale_completion_record_failed"
            return record
        self._best_effort_event(
            "stale_completion_reconciled",
            status="OK",
            label=label,
            visible_name=proof_name,
            inferred_island_count=inferred_count,
            record=_compact(record),
        )
        return record

    def _achievement_proof_block(
        self,
        commands: Any,
        *,
        completed: list[str],
        label: str,
        source: str,
        visible: Any,
        peek: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        proof_fn = getattr(commands, "cmd_lightning_proof", None)
        if not callable(proof_fn):
            self._best_effort_event(
                "lightning_war_achievement_proof",
                status="SKIPPED",
                reason="proof_helper_unavailable",
                label=label,
                source=source,
                islands_completed=completed,
            )
            return None
        try:
            proof = self._span(
                f"{label}_achievement_proof",
                proof_fn,
                profile=self.config.profile,
                sync_steam_api=False,
            )
        except Exception as exc:
            block = {
                "reason": "achievement_proof_exception",
                "source": source,
                "visible_name": _visible_ui_name(visible),
                "visible_ui": _compact(visible),
                "islands_completed": completed,
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The visible completion screen looked acceptable, but the "
                    "Lightning War proof command raised. Inspect the profile, "
                    "log, and Steam cache before accepting success."
                ),
            }
            if peek is not None:
                block["peek"] = _compact(peek)
            self._best_effort_event(
                "lightning_war_achievement_proof",
                status="BLOCKED",
                reason="achievement_proof_exception",
                label=label,
                source=source,
                islands_completed=completed,
                exception_type=type(exc).__name__,
                error=str(exc),
            )
            return block
        proven = proof.get("proven") is True or proof.get("status") == "PROVEN"
        self._best_effort_event(
            "lightning_war_achievement_proof",
            status="OK" if proven else "BLOCKED",
            reason=None if proven else "achievement_proof_unproven",
            label=label,
            source=source,
            islands_completed=completed,
            proof=_compact(proof),
        )
        if proven:
            return None
        block = {
            "reason": "achievement_proof_unproven",
            "source": source,
            "visible_name": _visible_ui_name(visible),
            "visible_ui": _compact(visible),
            "islands_completed": completed,
            "proof": _compact(proof),
            "next_step": (
                "Two islands are recorded complete and the visible screen is "
                "acceptable, but local durable proof does not show Lightning "
                "War unlocked. Do not declare success; start a new attempt or "
                "inspect the proof sources."
            ),
        }
        if peek is not None:
            block["peek"] = _compact(peek)
        return block

    def _span(
        self,
        label: str,
        fn: Callable[..., dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        assert self.telemetry is not None
        span_id = f"span_{label}_{int(time.monotonic() * 1000)}"
        started_at = time.monotonic()
        start_event_error = self._best_effort_event(
            "command_span",
            span_id=span_id,
            label=label,
            status="start",
        )
        if start_event_error is not None:
            self.telemetry_event_errors.append(start_event_error)
        try:
            result = fn(**kwargs)
        except Exception as exc:
            elapsed = round(time.monotonic() - started_at, 3)
            event_error = self._best_effort_event(
                "command_span",
                span_id=span_id,
                label=label,
                status="exception",
                wall_duration_seconds=elapsed,
                error=str(exc),
            )
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)
            raise
        elapsed = round(time.monotonic() - started_at, 3)
        if not isinstance(result, dict):
            result = {
                "status": "ERROR",
                "reason": "command_returned_non_dict",
                "span": label,
                "value_type": type(result).__name__,
                "value_repr": repr(result)[:500],
            }
        prompt_click: dict[str, Any] | None = None
        if (
            not self.config.dry_run
            and _contains_external_system_prompt(result)
        ):
            prompt_click = self._authorize_external_system_prompt(
                label,
                result,
            )
            result["system_prompt_allow_click"] = _compact(prompt_click)
            if prompt_click.get("status") == "OK":
                try:
                    retry_result = fn(**kwargs)
                except Exception as exc:
                    elapsed = round(time.monotonic() - started_at, 3)
                    event_error = self._best_effort_event(
                        "command_span",
                        span_id=span_id,
                        label=label,
                        status="retry_exception_after_system_prompt_allow",
                        wall_duration_seconds=elapsed,
                        error=str(exc),
                    )
                    if event_error is not None:
                        self.telemetry_event_errors.append(event_error)
                    raise
                if not isinstance(retry_result, dict):
                    retry_result = {
                        "status": "ERROR",
                        "reason": "command_retry_returned_non_dict",
                        "span": label,
                        "value_type": type(retry_result).__name__,
                        "value_repr": repr(retry_result)[:500],
                    }
                retry_result["system_prompt_auto_authorized"] = True
                retry_result["system_prompt_allow_click"] = _compact(prompt_click)
                result = retry_result
                elapsed = round(time.monotonic() - started_at, 3)
        if start_event_error is not None:
            result["command_span_start_event_exception_type"] = (
                start_event_error["exception_type"]
            )
            result["command_span_start_event_error"] = start_event_error["error"]
        try:
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
                system_prompt_auto_authorized=(
                    prompt_click is not None
                    and prompt_click.get("status") == "OK"
                ),
            )
        except Exception as exc:
            result["command_span_finish_event_exception_type"] = type(exc).__name__
            result["command_span_finish_event_error"] = str(exc)
        return result

    def _authorize_external_system_prompt(
        self,
        label: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        visible_ui = _external_system_prompt_visible_ui(result)
        if visible_ui is None:
            return {
                "status": "ERROR",
                "reason": "external_system_prompt_visible_ui_missing",
                "label": label,
            }
        nested_visible_ui = visible_ui.get("visible_ui")
        if isinstance(nested_visible_ui, dict):
            visible_ui = nested_visible_ui
        try:
            from src.loop import commands as commands_module

            click = commands_module._lightning_click_system_privacy_prompt_allow(
                visible_ui,
                dry_run=self.config.dry_run,
            )
        except Exception as exc:
            click = {
                "status": "ERROR",
                "reason": "privacy_prompt_allow_helper_exception",
                "label": label,
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        click["label"] = label
        event_error = self._best_effort_event(
            "system_prompt_allow_click",
            label=label,
            click=_compact(click),
        )
        if event_error is not None:
            self.telemetry_event_errors.append(event_error)
        return click

    def _ensure_pause(self, commands: Any) -> dict[str, Any]:
        try:
            return self._span(
                "ensure_pause",
                commands.cmd_lightning_ui,
                control="ensure_pause",
                dry_run=self.config.dry_run,
            )
        except Exception as exc:
            assert self.telemetry is not None
            result = {
                "status": "BLOCKED",
                "reason": "ensure_pause_exception",
                "span": "ensure_pause",
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The pause-recovery helper raised while the runner was "
                    "already stopping or restoring a safe thinking state. "
                    "Preserve the original block evidence and inspect the "
                    "visible screen before any more UI or combat commands."
                ),
            }
            self._record_result_event("ensure_pause_exception", result)
            return result

    def _load_session_or_block(
        self,
        commands: Any,
        stage: str,
        **context: Any,
    ) -> tuple[Any | None, dict[str, Any] | None]:
        try:
            return _load_current_session(commands), None
        except Exception as exc:
            result = {
                "status": "BLOCKED",
                "reason": "session_load_exception",
                "stage": stage,
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "next_step": (
                    "The Lightning runner could not read active session state. "
                    "Preserve the traceback and visible evidence; do not trust "
                    "stale island progress until the session read succeeds."
                ),
            }
            if context:
                result["context"] = {
                    key: _compact(value)
                    for key, value in context.items()
                }
            if self.telemetry is not None:
                event_error = self._best_effort_event(
                    "session_load_exception",
                    **result,
                )
                if event_error is not None:
                    result.setdefault("telemetry_event_errors", []).append(event_error)
            return None, result

    def _load_session_or_none(self, commands: Any, stage: str, **context: Any) -> Any | None:
        session, _block = self._load_session_or_block(commands, stage, **context)
        return session

    def _best_effort_event(self, name: str, **payload: Any) -> dict[str, Any] | None:
        assert self.telemetry is not None
        try:
            self.telemetry.event(name, **payload)
        except Exception as exc:
            return _telemetry_event_error(name, exc)
        return None

    def _record_result_event(self, name: str, result: dict[str, Any]) -> None:
        if self.telemetry is None:
            return
        event_error = self._best_effort_event(name, **result)
        if event_error is not None:
            result.setdefault("telemetry_event_errors", []).append(event_error)

    def _finish(self, status: str, reason: str, **payload: Any) -> dict[str, Any]:
        assert self.telemetry is not None
        result = {
            "status": status,
            "reason": reason,
            "mode": self.config.mode,
            "target_islands": self.config.target_islands,
            "telemetry_dir": str(self.telemetry.telemetry_dir),
            **payload,
        }
        if self.telemetry_event_errors:
            existing_errors = list(result.get("telemetry_event_errors") or [])
            result["telemetry_event_errors"] = existing_errors + [
                error
                for error in self.telemetry_event_errors
                if error not in existing_errors
            ]
        try:
            self.telemetry.event("runner_finish", **result)
        except Exception as exc:
            result["runner_finish_event_exception_type"] = type(exc).__name__
            result["runner_finish_event_error"] = str(exc)
        return result

    def _write_final_telemetry(
        self,
        result: dict[str, Any],
        *,
        status: str,
        reason: str,
    ) -> None:
        telemetry = self.telemetry
        if telemetry is None:
            return
        try:
            if _safe_to_finalize(result):
                report = generate_frame_delta_report(telemetry.run_dir)
            else:
                report = {
                    "status": "SKIPPED",
                    "reason": "unsafe_to_generate_frame_deltas",
                    "final_status": status,
                    "final_reason": reason,
                }
        except Exception as exc:
            report = {
                "status": "ERROR",
                "reason": "frame_delta_report_exception",
                "exception_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "final_status": status,
                "final_reason": reason,
            }
        summary_extra = {
            "mode": self.config.mode,
            "target_islands": self.config.target_islands,
            "telemetry_dir": str(telemetry.telemetry_dir),
            "frame_report": report.get("status"),
        }
        try:
            telemetry.event("frame_delta_report", **report)
        except Exception as exc:
            summary_extra["frame_report_event_exception_type"] = type(exc).__name__
            summary_extra["frame_report_event_error"] = str(exc)
        try:
            telemetry.summary(status=status, reason=reason, extra=summary_extra)
        except Exception:
            pass

    def _manifest_payload(self, session: Any) -> dict[str, Any]:
        cfg = self.config
        return {
            "achievement": cfg.achievement,
            "profile": cfg.profile,
            "squad": getattr(session, "squad", None),
            "difficulty": cfg.difficulty,
            "advanced_content": cfg.advanced_content,
            "mode": cfg.mode,
            "target_islands": cfg.target_islands,
            "combat_time_limit": cfg.combat_time_limit,
            "route_routing": cfg.route_routing,
            "route_auto_start": cfg.route_auto_start,
            "route_speed_vetoes": cfg.effective_route_speed_vetoes,
            "auto_clear_panels": cfg.auto_clear_panels,
            "max_attempts": cfg.max_attempts,
            "iteration_mode": cfg.iteration_mode,
            "screenshot_cadence": cfg.screenshot_cadence,
            "collect_screenshot_cadence": cfg.collect_screenshot_cadence,
            "race_screenshot_cadence": cfg.race_screenshot_cadence,
        }

    def _rehome_telemetry_if_session_changed(self, commands: Any, *, reason: str) -> None:
        assert self.telemetry is not None
        session, session_block = self._load_session_or_block(
            commands,
            "telemetry_rehome",
            reason=reason,
        )
        if session_block is not None:
            event_error = self._best_effort_event(
                "telemetry_rehome_skipped",
                status="BLOCKED",
                reason="session_load_exception",
                session_load=session_block,
            )
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)
            return
        new_run_id = _concrete_session_run_id(session)
        old_run_id = getattr(self.telemetry, "run_id", None)
        if not new_run_id or new_run_id == old_run_id:
            return

        old_telemetry = self.telemetry
        try:
            if self.screenshots is not None:
                self.screenshots.stop()
                self.screenshots = None
            event_error = self._best_effort_event(
                "telemetry_rehome",
                status="REHOMING",
                reason=reason,
                old_run_id=old_run_id,
                new_run_id=new_run_id,
            )
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)
            try:
                old_telemetry.summary(
                    status="REHOMED",
                    reason=reason,
                    extra={"new_telemetry_run_id": new_run_id},
                )
            except Exception as exc:
                self.telemetry_event_errors.append(
                    _telemetry_event_error("telemetry_rehome_summary", exc)
                )

            self.telemetry = TelemetryRecorder(new_run_id)
            self.telemetry.write_manifest(self._manifest_payload(session))
            event_error = self._best_effort_event(
                "telemetry_rehome",
                status="OK",
                reason=reason,
                previous_run_id=old_run_id,
            )
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)
            if self.config.screenshots:
                self.screenshots = ScreenshotRecorder(
                    self.telemetry,
                    cadence_seconds=self._current_screenshot_cadence(),
                )
                self.screenshots.start()
        except Exception as exc:
            self.telemetry = old_telemetry
            event_error = self._best_effort_event(
                "telemetry_rehome_exception",
                status="ERROR",
                reason="telemetry_rehome_exception",
                old_run_id=old_run_id,
                new_run_id=new_run_id,
                exception_type=type(exc).__name__,
                error=str(exc),
                traceback=traceback.format_exc(),
                next_step=(
                    "Telemetry rehome failed after starting a new Lightning "
                    "timeline. The run can continue using the existing "
                    "telemetry directory; inspect this event if recordings "
                    "need to be reconciled later."
                ),
            )
            if event_error is not None:
                self.telemetry_event_errors.append(event_error)


def _telemetry_event_error(
    event_name: str,
    exc: Exception,
    *,
    traceback_text: str | None = None,
) -> dict[str, Any]:
    result = {
        "event_name": event_name,
        "exception_type": type(exc).__name__,
        "error": str(exc),
    }
    if traceback_text is not None:
        result["traceback"] = traceback_text
    return result


def _telemetry_errors_payload(errors: list[dict[str, Any]]) -> dict[str, Any]:
    if not errors:
        return {}
    return {"telemetry_event_errors": errors}


def _route_probe_cache_entry_summary(entry: dict[str, Any]) -> dict[str, Any]:
    summary = {
        key: entry.get(key)
        for key in (
            "index",
            "visible_label",
            "label_key",
            "window_x",
            "window_y",
            "visual_region_window_x",
            "visual_region_window_y",
            "auto_route_block_reason",
            "actual_preview_mission_id",
            "visible_preview_ocr_reason",
            "retry_policy",
            "hits",
            "first_seen_run_id",
            "last_seen_run_id",
        )
        if entry.get(key) is not None
    }
    signature = entry.get("signature")
    if isinstance(signature, dict):
        summary["signature"] = {
            key: signature.get(key)
            for key in (
                "index",
                "first_island",
                "route_routing",
                "mission_index",
                "label_key",
                "route_click_source",
                "window_x",
                "window_y",
                "visual_region_window_x",
                "visual_region_window_y",
            )
            if signature.get(key) is not None
        }
    return summary


def _compact(value: Any) -> Any:
    if isinstance(value, dict):
        compact = _conductor_compact(value)
        for key in (
            "visible_ui",
            "visible_name",
            "recommended_control",
            "control",
            "click_result",
            "grid_power",
            "grid_power_max",
            "last_attempt",
            "screenshot_path",
            "error",
            "confidence",
            "dark_overlay_fraction",
            "requires_user_authorization",
            "unlocked_list",
            "ocr_text",
            "ocr_texts",
            "visible_text",
            "label",
            "notes_path",
            "note_written",
            "live_burst_seconds",
            "include_ocr",
            "span",
            "exception_type",
            "traceback",
            "click",
            "setup",
            "value_type",
            "value_repr",
        ):
            if key in value and key not in compact:
                if key == "visible_ui" and isinstance(value[key], dict):
                    compact[key] = _compact_visible_ui(value[key])
                elif key in {"click", "click_result"} and isinstance(value[key], dict):
                    compact[key] = _compact(value[key])
                else:
                    compact[key] = value[key]
        if "external_prompt" in value and "external_prompt" not in compact:
            compact["external_prompt"] = _compact_external_prompt(
                value.get("external_prompt")
            )
        for key in (
            "guard",
            "pause_guard",
            "resume_guard",
            "ensure_pause",
            "pause_verify",
            "capture_result",
        ):
            if key in value and key not in compact and isinstance(value[key], dict):
                compact[key] = _compact(value[key])
        if "evidence_ui" in value and "evidence_ui" not in compact:
            compact["evidence_ui"] = _compact(value.get("evidence_ui"))
        if isinstance(value.get("steps"), list) and "steps" not in compact:
            compact["steps"] = _segment_steps_summary(value)
        return compact
    return value


def _compact_visible_ui(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    keep: dict[str, Any] = {}
    for key in (
        "status",
        "visible_ui",
        "recommended_control",
        "confidence",
        "dark_overlay_fraction",
        "requires_user_authorization",
        "screenshot_path",
        "visible_text",
        "ocr_text",
        "ocr_texts",
    ):
        if key in value:
            if key in {"visible_text", "ocr_text"} and isinstance(value[key], str):
                keep[key] = value[key][:800]
            elif key == "ocr_texts" and isinstance(value[key], list):
                keep[key] = [str(item)[:160] for item in value[key][:40]]
            else:
                keep[key] = value[key]
    if "external_prompt" in value:
        keep["external_prompt"] = _compact_external_prompt(
            value.get("external_prompt")
        )
    game_focus = value.get("game_focus_proof")
    if isinstance(game_focus, dict):
        keep["game_focus_proof"] = {
            key: game_focus.get(key)
            for key in (
                "status",
                "frontmost",
                "window_bounds",
                "screenshot_image_size",
                "expected_app",
            )
            if key in game_focus
        }
    return keep


def _completion_visible_screen_block(
    visible: Any,
    *,
    completed: list[str],
    allow_menu_setup: bool = False,
    source: str = "classify",
) -> dict[str, Any] | None:
    visible_name = _visible_ui_name(visible)
    terminal_evidence = _terminal_outcome_evidence(visible)
    if not isinstance(visible, dict) or visible.get("status") != "OK":
        return {
            "reason": "completion_screen_classification_failed",
            "visible_name": visible_name,
            "visible_ui": _compact(visible),
            "islands_completed": completed,
            "source": source,
            "next_step": (
                "Session progress says the target island count is complete, "
                "but the final screen classifier failed. Inspect the "
                "screenshot/error evidence before accepting success."
            ),
        }
    if visible_name in SYSTEM_BLOCKING_UIS:
        return {
            "reason": "external_system_prompt_visible",
            "visible_name": visible_name,
            "visible_ui": _compact(visible),
            "islands_completed": completed,
            "source": source,
        }
    if terminal_evidence is not None:
        return {
            "reason": "terminal_outcome_visible_before_success",
            "visible_name": visible_name,
            "terminal_evidence": terminal_evidence,
            "visible_ui": _compact(visible),
            "islands_completed": completed,
            "source": source,
            "next_step": (
                "Session progress says the target island count is complete, "
                "but the visible screen carries terminal/failed-objective "
                "evidence. Inspect the screenshot before accepting success."
            ),
        }
    terminal_ui_evidence = _terminal_visible_ui_evidence(visible)
    if terminal_ui_evidence is not None:
        return {
            "reason": "terminal_visible_ui_before_success",
            "visible_name": visible_name,
            "terminal_evidence": terminal_ui_evidence,
            "visible_ui": _compact(visible),
            "islands_completed": completed,
            "source": source,
        }
    if visible_name in UNEXPECTED_MENU_UIS:
        if allow_menu_setup:
            return None
        return {
            "reason": "unexpected_menu_or_setup_visible_before_success",
            "visible_name": visible_name,
            "visible_ui": _compact(visible),
            "islands_completed": completed,
            "source": source,
            "next_step": (
                "Session progress says the target island count is complete, "
                "but the game is on title/setup. Inspect stale session state "
                "before declaring the Lightning War baseline complete."
            ),
        }
    if visible_name == "pause_menu":
        return {
            "reason": "completion_pause_menu_visible",
            "visible_name": visible_name,
            "visible_ui": _compact(visible),
            "islands_completed": completed,
            "source": source,
        }
    if visible_name not in COMPLETION_PROOF_UIS:
        return {
            "reason": "completion_screen_unverified",
            "visible_name": visible_name,
            "visible_ui": _compact(visible),
            "islands_completed": completed,
            "source": source,
            "next_step": (
                "Session progress says the target island count is complete, "
                "but the final classifier did not show a known completion "
                "proof screen. Regain a visible reward, island-complete, or "
                "island-map screen before accepting success."
            ),
        }
    return None


def _record_island_completion_after_leave_confirm(
    session: Any,
    *,
    reason: str = "recorded_after_leave_confirm",
) -> dict[str, Any]:
    existing = _completed_islands(session)
    current = str(getattr(session, "current_island", "") or "").strip()
    mission_index = _safe_int(getattr(session, "mission_index", 0) or 0)
    inferred_from_index = _inferred_completed_island_count_from_mission_index(session)

    completed = list(existing)
    if current and current not in completed:
        completed.append(current)
    elif not completed:
        completed.append("island_1")

    target_len = max(len(completed), inferred_from_index)
    while len(completed) < target_len:
        completed.append(f"island_{len(completed) + 1}")

    result = {
        "status": "OK",
        "reason": reason,
        "before_islands_completed": existing,
        "current_island": current,
        "mission_index": mission_index,
        "inferred_island_count_from_mission_index": inferred_from_index,
        "islands_completed": completed,
    }
    try:
        setattr(session, "islands_completed", completed)
        setattr(session, "current_mission", "")
        setattr(session, "phase", "between_missions")
        setattr(session, "current_turn", 0)
        setattr(session, "actions_executed", 0)
        setattr(session, "active_solution", None)
        save = getattr(session, "save", None)
        if callable(save):
            save()
            result["session_saved"] = True
        else:
            result["session_saved"] = False
            result["session_save_reason"] = "save_method_unavailable"
    except Exception as exc:
        result["status"] = "ERROR"
        result["reason"] = "record_after_leave_confirm_save_exception"
        result["session_saved"] = False
        result["exception_type"] = type(exc).__name__
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
    return result


def _inferred_completed_island_count_from_mission_index(session: Any) -> int:
    mission_index = _safe_int(getattr(session, "mission_index", 0) or 0)
    if mission_index < 4:
        return 0
    return max(1, (mission_index + 1) // 5)


def _compact_external_prompt(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    keep: dict[str, Any] = {}
    for key in ("status", "matched", "score", "kind", "checks"):
        if key in value:
            keep[key] = value[key]
    return keep


def _completed_islands(session: Any) -> list[str]:
    return list(getattr(session, "islands_completed", []) or [])


def _session_summary(session: Any) -> dict[str, Any]:
    return {
        "run_id": getattr(session, "run_id", None),
        "squad": getattr(session, "squad", None),
        "difficulty": getattr(session, "difficulty", None),
        "achievement_targets": list(getattr(session, "achievement_targets", []) or []),
        "current_island": getattr(session, "current_island", None),
        "current_mission": getattr(session, "current_mission", None),
        "mission_index": getattr(session, "mission_index", None),
        "islands_completed": _completed_islands(session),
    }


def _preflight_timer_exceeded(preflight: dict[str, Any]) -> bool:
    result = preflight.get("result")
    if not isinstance(result, dict):
        return False
    budget = result.get("game_budget")
    if not isinstance(budget, dict) or budget.get("game_status") != "EXCEEDED":
        return False
    issues = [str(issue).lower() for issue in (result.get("issues") or [])]
    return bool(issues) and all("timer" in issue for issue in issues)


def _session_is_lightning_war(session: Any) -> bool:
    squad = str(getattr(session, "squad", "") or "").strip().lower()
    if squad != "blitzkrieg":
        return False
    try:
        difficulty = int(getattr(session, "difficulty", -1))
    except (TypeError, ValueError):
        return False
    if difficulty != 0:
        return False
    targets = {
        str(target).strip().lower()
        for target in (getattr(session, "achievement_targets", []) or [])
        if str(target).strip()
    }
    return LIGHTNING_WAR.lower() in targets


def _speed_island_number(session: Any, *, target_islands: int) -> int:
    completed = len(_completed_islands(session))
    target = max(1, int(target_islands))
    if completed >= target:
        return target
    return completed + 1


def _speed_phase_label(
    session: Any,
    segment: dict[str, Any],
    *,
    target_islands: int,
) -> str:
    completed = len(_completed_islands(session))
    if completed >= max(1, int(target_islands)):
        return "target_complete"
    visible_name = _visible_ui_name(segment)
    if visible_name in {"island_complete_leave", "reward_panel", "bottom_continue_panel"}:
        return "reward_shop"
    reason = str(segment.get("reason") or "")
    if reason in {"route_ready", "visible_island_map_without_bridge"}:
        return "route"
    if visible_name in {"island_map", "island_map_or_unknown"}:
        return "route"
    current_mission = str(getattr(session, "current_mission", "") or "").strip()
    if current_mission:
        return "mission"
    return "between_missions"


def _segment_combat_timing_summary(segment: dict[str, Any]) -> dict[str, Any]:
    timed_turn_count = 0
    attempted_turn_count = 0
    end_turn_clicks = 0
    last_turn: Any = None
    total_turn_wall = 0.0
    for step in segment.get("steps") or []:
        if not isinstance(step, dict):
            continue
        attempted_turn_count += _safe_int(step.get("combat_turns_attempted"))
        end_turn_clicks += _safe_int(step.get("combat_end_turn_clicks"))
        for turn in step.get("combat_turn_timings") or []:
            if not isinstance(turn, dict):
                continue
            timed_turn_count += 1
            if turn.get("turn") is not None:
                last_turn = turn.get("turn")
            total_turn_wall += _safe_float(turn.get("turn_wall_seconds"))
    return {
        "attempted_turn_count": attempted_turn_count,
        "timed_turn_count": timed_turn_count,
        "last_turn": last_turn,
        "end_turn_clicks": end_turn_clicks,
        "turn_wall_seconds_total": round(total_turn_wall, 3),
    }


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _segment_steps_summary(segment: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for step in segment.get("steps") or []:
        if not isinstance(step, dict):
            continue
        row = {
            key: step[key]
            for key in (
                "step",
                "phase",
                "status",
                "reason",
                "action",
                "combat_loop_reason",
                "deploy_status",
                "deployments",
                "top_mission",
                "top_region_id",
                "route_auto_start_index",
                "route_auto_start_mission",
                "route_auto_start_rejected_candidate",
                "route_auto_start_blocked_candidate",
                "route_auto_start_veto_ignored",
                "route_auto_start_retry_index",
                "route_auto_start_retry_mission",
                "route_auto_start_retry_probe",
                "route_auto_start_retry_probe_offset",
                "route_auto_start_retry_reason",
                "route_auto_start_alternate_click_candidate",
                "route_auto_start_retry_suppressed",
                "route_probe_cache",
                "step_wall_seconds",
                "segment_elapsed_seconds",
                "combat_loop_wall_seconds",
                "combat_turns_attempted",
                "combat_end_turn_clicks",
                "panel_clear_status",
                "panel_clear_steps",
            )
            if key in step
        }
        turn_timings = step.get("combat_turn_timings")
        if isinstance(turn_timings, list) and turn_timings:
            row["combat_turn_timings"] = [
                {
                    key: turn[key]
                    for key in (
                        "loop_index",
                        "turn",
                        "status",
                        "auto_turn_wall_seconds",
                        "turn_wall_seconds",
                    )
                    if isinstance(turn, dict) and key in turn
                }
                for turn in turn_timings[:6]
                if isinstance(turn, dict)
            ]
        visible_ui = step.get("visible_ui")
        if isinstance(visible_ui, dict):
            row["visible_ui"] = _compact(visible_ui)
        out.append(row)
    return out


def _segment_entered_combat(segment: dict[str, Any]) -> bool:
    for step in segment.get("steps") or []:
        if not isinstance(step, dict):
            continue
        if step.get("combat_loop_reason") or step.get("combat_turns_attempted"):
            return True
        if str(step.get("action") or "") in {
            "combat_loop",
            "deploy_then_combat",
            "finish_deployment_then_combat",
            "wait_then_combat_loop",
        }:
            return True
    return False


_PRE_START_ROUTE_GATE_REASONS = {
    "bridge_snapshot_unavailable_paused_island_map",
    "bridge_snapshot_unavailable_visible_island_map",
    "route_preview_auto_start_vetoed_before_start",
    "route_preview_bridge_stale_before_start",
    "route_preview_bridge_stale_after_dialogue",
    "route_preview_mission_unverified_before_start",
    "route_preview_mission_mismatch_before_start",
    "route_preview_mission_unverified_after_dialogue",
    "route_preview_mission_mismatch_after_dialogue",
    "route_preview_not_opened_before_start",
    "route_preview_unassigned_multi_region_before_start",
    "start_mission_text_not_found",
    "route_preview_start_text_missing_before_start",
    "route_preview_start_text_missing_after_dialogue",
    "route_start_subcall_timeout",
    "route_preview_baseline_start_button_missing_before_start",
    "route_preview_unassigned_multi_region_start_button_missing_before_start",
}

_PRE_START_ROUTE_GATE_CONTAINER_REASONS = {
    "",
    "route_auto_start_not_allowed",
    "segment_wall_seconds_exceeded",
    "max_steps_reached",
}


def _segment_preview_only_route_gate_evidence(
    segment: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(segment, dict) or _segment_entered_combat(segment):
        return None
    top_reason = str(segment.get("reason") or "")
    if top_reason in _PRE_START_ROUTE_GATE_REASONS:
        return {
            "token": "ROUTE_AUTO_START_NOT_ALLOWED",
            "path": "reason",
            "status": str(segment.get("status") or ""),
            "reason": top_reason,
            "source": "preview_only_route_gate",
        }
    if top_reason not in _PRE_START_ROUTE_GATE_CONTAINER_REASONS:
        return None
    for step in segment.get("steps") or []:
        if not isinstance(step, dict):
            continue
        if (
            step.get("reason") in _PRE_START_ROUTE_GATE_REASONS
            and (
                step.get("phase") == "route_start"
                or step.get("status") in {"BLOCKED", "LIGHTNING_ATTEMPT_NEEDS_UI"}
            )
        ):
            return {
                "token": "ROUTE_AUTO_START_NOT_ALLOWED",
                "path": f"steps.{step.get('step', '?')}.reason",
                "status": str(step.get("status") or ""),
                "reason": str(step.get("reason") or ""),
                "source": "preview_only_route_gate",
            }
    return None


def _segment_preview_only_route_gate(segment: dict[str, Any]) -> bool:
    return _segment_preview_only_route_gate_evidence(segment) is not None


def _segment_mission_preview_route_validation_gate(segment: dict[str, Any]) -> bool:
    if not isinstance(segment, dict) or _segment_entered_combat(segment):
        return False
    if str(segment.get("reason") or "") == "mission_preview_requires_route_validation":
        return True
    return _segment_has_step_reason(
        segment,
        "mission_preview_requires_route_validation",
    )


def _segment_recoverable_precombat_route_gate(
    segment: dict[str, Any],
    block: str,
) -> bool:
    if block not in RECOVERABLE_PRECOMBAT_ROUTE_GATE_TOKENS:
        return False
    if not isinstance(segment, dict) or _segment_entered_combat(segment):
        return False
    if block == "ROUTE_PREVIEW_ACTIVE_MISSION_BEFORE_REGION_CLICK":
        if not (
            segment.get("reason") == "route_preview_active_mission_before_region_click"
            or _segment_has_step_reason(
                segment,
                "route_preview_active_mission_before_region_click",
            )
            or _first_nested_dict_with_field(
                segment,
                "reason",
                "route_preview_active_mission_before_region_click",
            )
            is not None
        ):
            return False
        snapshot = _first_nested_turn_zero_deployment_snapshot(segment)
        return snapshot is not None
    if block == "VISIBLE_ISLAND_MAP_WITH_STALE_DEPLOYMENT_BRIDGE":
        warning = _first_nested_dict_with_field(
            segment,
            "reason",
            "visible_map_overrides_stale_active_mission",
        )
        if warning is None:
            return False
        snapshot = _first_nested_turn_zero_deployment_snapshot(segment)
        return snapshot is not None
    if not _segment_has_step_reason(segment, "deployment_bridge_state_uncertain"):
        return False
    if _segment_has_step_action(segment, "deploy_confirm_bridge_not_live"):
        return True
    warning = _first_nested_dict_with_field(
        segment,
        "reason",
        "visible_map_overrides_stale_active_mission",
    )
    cleanup = _first_nested_stale_map_deployment_cleanup(segment)
    if warning is None and cleanup is None:
        return False
    snapshot = (
        _first_nested_snapshot_with_visible_map(segment)
        or _first_nested_turn_zero_deployment_snapshot(segment)
    )
    if snapshot is None:
        return False
    if _int_field(snapshot, "active_mechs") > 0 or _int_field(snapshot, "mech_count") > 0:
        return False
    return (
        snapshot.get("in_active_mission") is True
        and _int_field(snapshot, "deployment_zone_count") > 0
    )


def _segment_recoverable_precombat_route_gate_evidence(
    segment: dict[str, Any],
    existing_block: str | None = None,
) -> dict[str, Any] | None:
    if not isinstance(segment, dict) or _segment_entered_combat(segment):
        return None
    if existing_block:
        normalized = _normalize_stop_token_text(existing_block)
        if normalized not in RECOVERABLE_PRECOMBAT_ROUTE_GATE_OVERRIDABLE_TOKENS:
            return None
    for token in (
        "ROUTE_PREVIEW_ACTIVE_MISSION_BEFORE_REGION_CLICK",
        "VISIBLE_ISLAND_MAP_WITH_STALE_DEPLOYMENT_BRIDGE",
        "DEPLOYMENT_BRIDGE_STATE_UNCERTAIN",
    ):
        if _segment_recoverable_precombat_route_gate(segment, token):
            return {
                "token": token,
                "path": "recoverable_precombat_route_gate",
                "status": str(segment.get("status") or ""),
                "reason": str(segment.get("reason") or ""),
                "source": "recoverable_precombat_route_gate",
            }
    return None


def _first_nested_turn_zero_deployment_snapshot(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        status = value.get("status")
        reason = value.get("reason")
        if (
            (
                status == "OK"
                or reason == "route_preview_active_mission_before_region_click"
            )
            and value.get("in_active_mission") is True
            and _int_field(value, "turn") == 0
            and _int_field(value, "deployment_zone_count") > 0
            and _int_field(value, "active_mechs") == 0
            and _int_field(value, "mech_count") == 0
        ):
            return value
        for key in ("snapshot", "live_snapshot", "post_preview_snapshot"):
            nested = value.get(key)
            found = _first_nested_turn_zero_deployment_snapshot(nested)
            if found is not None:
                return found
        for nested in value.values():
            found = _first_nested_turn_zero_deployment_snapshot(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _first_nested_turn_zero_deployment_snapshot(nested)
            if found is not None:
                return found
    return None


def _segment_has_step_reason(segment: dict[str, Any], reason: str) -> bool:
    for step in segment.get("steps") or []:
        if isinstance(step, dict) and step.get("reason") == reason:
            return True
    return False


def _segment_has_step_action(segment: dict[str, Any], action: str) -> bool:
    for step in segment.get("steps") or []:
        if isinstance(step, dict) and step.get("action") == action:
            return True
    return False


def _first_nested_stale_map_deployment_cleanup(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        reason = value.get("reason")
        policy = value.get("policy")
        if (
            reason
            in {
                "stale_active_mission_visible_map_before_deploy",
                "stale_active_mission_visible_map_blocks_deployment",
                "visible_map_route_ready_stale_deployment_bridge",
            }
            or policy == "visible_map_route_discards_stale_combat_bridge_files"
        ):
            snapshot = value.get("snapshot")
            if _first_nested_turn_zero_deployment_snapshot(snapshot) is not None:
                return value
        for nested in value.values():
            found = _first_nested_stale_map_deployment_cleanup(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _first_nested_stale_map_deployment_cleanup(nested)
            if found is not None:
                return found
    return None


def _first_nested_dict_with_field(
    value: Any,
    field: str,
    expected: Any,
) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if value.get(field) == expected:
            return value
        for nested in value.values():
            found = _first_nested_dict_with_field(nested, field, expected)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _first_nested_dict_with_field(nested, field, expected)
            if found is not None:
                return found
    return None


def _first_nested_snapshot_with_visible_map(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        visible = value.get("visible_ui")
        if (
            isinstance(visible, dict)
            and visible.get("visible_ui") in {"island_map", "island_map_or_unknown"}
            and value.get("status") == "OK"
            and "deployment_zone_count" in value
        ):
            return value
        for key in ("snapshot", "live_snapshot"):
            nested = value.get(key)
            found = _first_nested_snapshot_with_visible_map(nested)
            if found is not None:
                return found
        for nested in value.values():
            found = _first_nested_snapshot_with_visible_map(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _first_nested_snapshot_with_visible_map(nested)
            if found is not None:
                return found
    return None


def _int_field(value: dict[str, Any], key: str) -> int:
    try:
        return int(value.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _route_probe_offset(session: Any, attempt_index: int) -> int:
    """Rotate unlabeled map probes across safe rerolls and route progress."""
    try:
        attempt_offset = max(0, int(attempt_index) - 1)
    except (TypeError, ValueError):
        attempt_offset = 0
    try:
        mission_offset = max(0, int(getattr(session, "mission_index", 0) or 0))
    except (TypeError, ValueError):
        mission_offset = 0
    return attempt_offset + mission_offset + len(_completed_islands(session))


def _route_probe_offset_for_segment(
    session: Any,
    attempt_index: int,
    *,
    speed_mode: bool,
) -> int:
    """Choose probe rotation for a live segment.

    Speed Lightning runs should not burn the first-mission clock rotating
    unlabeled previews across restarts.  Keep mission/island progress in the
    offset so later maps still vary, but drop the attempt component.
    """
    if not speed_mode:
        return _route_probe_offset(session, attempt_index)
    try:
        mission_offset = max(0, int(getattr(session, "mission_index", 0) or 0))
    except (TypeError, ValueError):
        mission_offset = 0
    return mission_offset + len(_completed_islands(session))


def _first_island_for_attempt(
    preferred: str,
    attempt_index: int,
    *,
    speed_mode: bool = False,
) -> str:
    """Return the preferred first island, then rotate through safe alternatives."""
    preferred_key = _LIGHTNING_FIRST_ISLAND_ALIASES.get(
        str(preferred or "archive").strip().lower(),
        "archive",
    )
    if speed_mode and preferred_key != "archive":
        return preferred_key
    base_sequence = (
        DEFAULT_LIGHTNING_SPEED_FIRST_ISLAND_SEQUENCE
        if speed_mode
        else DEFAULT_LIGHTNING_FIRST_ISLAND_SEQUENCE
    )
    sequence = [preferred_key]
    sequence.extend(
        island
        for island in base_sequence
        if island != preferred_key
    )
    try:
        offset = max(0, int(attempt_index) - 1)
    except (TypeError, ValueError):
        offset = 0
    return sequence[offset % len(sequence)]


def _segment_route_mismatch_after_start_gate(segment: dict[str, Any]) -> bool:
    if str(segment.get("reason") or "") in {
        "route_mission_mismatch_after_start",
        "route_mission_mismatch_after_start_playable",
        "route_mission_mismatch_after_start_recovered",
    }:
        return True
    for step in segment.get("steps") or []:
        if not isinstance(step, dict):
            continue
        reason = str(step.get("reason") or "")
        if step.get("phase") != "route_start":
            continue
        if reason in {
            "route_mission_mismatch_after_start",
            "route_mission_mismatch_after_start_playable",
            "route_mission_mismatch_after_start_recovered",
        }:
            return True
        for key in ("route_mismatch_warning", "route_mismatch_block"):
            warning = step.get(key)
            if isinstance(warning, dict) and str(warning.get("actual_mission_id") or ""):
                return True
            if (
                isinstance(warning, dict)
                and isinstance(warning.get("route_mismatch_block"), dict)
            ):
                return True
        last_route_start = step.get("last_route_start")
        click_result = (
            last_route_start.get("click_result")
            if isinstance(last_route_start, dict)
            else None
        )
        if isinstance(click_result, dict) and _segment_route_start_click_has_mismatch(
            click_result,
        ):
            return True
    return False


def _segment_route_start_click_has_mismatch(click_result: dict[str, Any]) -> bool:
    for key in ("route_mismatch_warning", "route_mismatch_block"):
        warning = click_result.get(key)
        if isinstance(warning, dict):
            return True
    return str(click_result.get("reason") or "") in {
        "route_mission_mismatch_after_start",
        "route_mission_mismatch_after_start_playable",
        "route_mission_mismatch_after_start_recovered",
    }


def _segment_route_mismatch_warning(segment: dict[str, Any]) -> dict[str, Any] | None:
    for step in segment.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for key in ("route_mismatch_warning", "route_mismatch_block"):
            warning = step.get(key)
            if isinstance(warning, dict):
                return warning
    last_route_start = segment.get("last_route_start")
    if isinstance(last_route_start, dict):
        click_result = last_route_start.get("click_result")
        if isinstance(click_result, dict):
            for key in ("route_mismatch_warning", "route_mismatch_block"):
                warning = click_result.get(key)
                if isinstance(warning, dict):
                    return warning
    return None


def _segment_route_auto_start_blocked_candidate(
    segment: dict[str, Any],
) -> dict[str, Any] | None:
    for step in segment.get("steps") or []:
        if not isinstance(step, dict):
            continue
        candidate = step.get("route_auto_start_blocked_candidate")
        if isinstance(candidate, dict):
            return candidate
    return None


def _grid_state(profile: str) -> dict[str, Any]:
    try:
        state = load_game_state(profile)
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": "grid_state_reader_exception",
            "exception_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    if state is None:
        return {"status": "ERROR", "reason": "save_state_unavailable"}
    return {
        "status": "OK",
        "grid_power": int(state.grid_power),
        "grid_power_max": int(state.grid_power_max or 7),
    }


def _save_state_summary(state: Any) -> dict[str, Any]:
    if state is None:
        return {"status": "ERROR", "reason": "save_state_unavailable"}
    return {
        "status": "OK",
        "difficulty": getattr(state, "difficulty", None),
        "grid_power": getattr(state, "grid_power", None),
        "grid_power_max": getattr(state, "grid_power_max", None),
        "mechs": _state_mechs(state),
        "weapons": _state_weapons(state),
    }


def _advanced_content_proof(commands: Any, profile: str) -> dict[str, Any]:
    reader = getattr(commands, "_read_save_advanced_content", None)
    if not callable(reader):
        return {
            "status": "UNAVAILABLE",
            "reason": "advanced_content_reader_unavailable",
        }
    try:
        proof = reader(profile)
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": "advanced_content_reader_error",
            "error": str(exc),
        }
    if not isinstance(proof, dict):
        return {
            "status": "ERROR",
            "reason": "advanced_content_reader_returned_non_dict",
            "value": repr(proof),
        }
    return proof


def _state_mechs(state: Any) -> list[str]:
    mechs = [str(mech) for mech in (getattr(state, "mechs", []) or []) if mech]
    if mechs:
        return mechs
    mission = getattr(state, "active_mission", None)
    getter = getattr(mission, "get_mechs", None)
    if not callable(getter):
        return []
    return [
        str(getattr(pawn, "type", ""))
        for pawn in getter()
        if str(getattr(pawn, "type", ""))
    ]


def _state_weapons(state: Any) -> list[str]:
    weapons = [
        str(weapon)
        for weapon in (getattr(state, "weapons", []) or [])
        if str(weapon or "")
    ]
    if weapons:
        return weapons
    mission = getattr(state, "active_mission", None)
    getter = getattr(mission, "get_mechs", None)
    if not callable(getter):
        return []
    out: list[str] = []
    for pawn in getter():
        for attr in ("primary_weapon", "secondary_weapon"):
            weapon = str(getattr(pawn, attr, "") or "")
            if weapon:
                out.append(weapon)
    return out


def _weapon_or_upgrade_present(weapons: list[str], base_weapon: str) -> bool:
    prefix = f"{base_weapon}_"
    return any(weapon == base_weapon or weapon.startswith(prefix) for weapon in weapons)


def _shop_block(
    reason: str,
    grid_state: dict[str, Any],
    steps: list[dict[str, Any]],
    visible: dict[str, Any],
    *,
    observed_visible_ui: dict[str, Any] | None = None,
    terminal_evidence: dict[str, Any] | None = None,
    exception_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "status": "BLOCKED",
        "reason": reason,
        "grid_state": grid_state,
        "steps": steps,
        "visible_ui": _compact(visible),
        "next_step": (
            "Inspect the shop/reward screen before any more island-exit clicks. "
            "Grid-first shopping did not verify cleanly."
        ),
    }
    if observed_visible_ui is not None:
        result["observed_visible_ui"] = observed_visible_ui
    if terminal_evidence is not None:
        result["terminal_evidence"] = terminal_evidence
    if exception_evidence is not None:
        result["exception_evidence"] = exception_evidence
    return result


def _blocking_preflight_warning(result: dict[str, Any]) -> str | None:
    warnings = result.get("warnings") or []
    issues = result.get("issues") or []
    text = " ".join(str(item).lower() for item in list(warnings) + list(issues))
    blocking_snippets = (
        "active achievement targets do not include",
        "diagnosis",
        "save difficulty",
        "session difficulty",
        "advanced content state",
        "hold the line",
        "persistent post-enemy block",
        "post_enemy_block",
        "requires_research",
        "research_required",
        "safety_blocked",
        "threat_audit_blocked",
    )
    for snippet in blocking_snippets:
        if snippet in text:
            return snippet
    return None


def _format_seconds(total_seconds: float | None) -> str | None:
    if total_seconds is None:
        return None
    seconds = max(0, int(float(total_seconds)))
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def cmd_lightning_autonomous(**kwargs: Any) -> dict[str, Any]:
    """CLI entry point for the reliable Lightning War runner."""
    from src.loop import commands

    run_kwargs = dict(kwargs)
    # Backward compatibility: old callers passed no mode and expected a
    # Lightning War conductor.  The new command defaults to the safe baseline.
    run_kwargs.setdefault("mode", "baseline")
    config = LightningRunnerConfig(**run_kwargs)
    runner = LightningWarRunner(config)
    result = runner.run()
    commands._print_result(result)
    return result
