"""Strict validation and matched-pair comparison for callback trial results."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any


RESULT_SCHEMA_VERSION = 1
RESULT_KIND = "observatory_callback_trial_result"
HOST_VERSION = "observatory-callback-trial-host/2"
CALLBACK_FAMILIES = frozenset(
    {"get_target_area", "enemy_target_score", "get_skill_effect", "score_positioning"}
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CAPTURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "host_version",
        "capture_track",
        "condition",
        "capsule_sha256",
        "arm_packet_sha256",
        "binding_manifest_sha256",
        "callback_join_sha256",
        "capture_id",
        "checkpoint_seq",
        "callback_family",
        "status",
        "error",
        "runtime_before",
        "runtime_after",
        "controller_status",
        "raw_written",
        "raw_event_count",
        "attempted_calls",
        "serialization_errors",
        "slot_count",
        "slots_restored",
    }
)
_RUNTIME_FIELDS = frozenset(
    {
        "now_epoch",
        "mission_id",
        "turn",
        "phase",
        "timeline_fingerprint",
        "master_seed",
        "region_id",
        "ai_seed_fingerprint",
    }
)
_CONTROLLER_FIELDS = frozenset({"consumed", "prepared", "activated", "written"})
_PAIR_IDENTITY_FIELDS = (
    "capsule_sha256",
    "arm_packet_sha256",
    "binding_manifest_sha256",
    "callback_join_sha256",
    "capture_id",
    "checkpoint_seq",
    "callback_family",
    "capture_track",
    "slot_count",
)
_RUNTIME_IDENTITY_FIELDS = tuple(sorted(_RUNTIME_FIELDS - {"now_epoch"}))
_RUNTIME_STABLE_FIELDS = tuple(
    sorted(_RUNTIME_FIELDS - {"now_epoch", "turn", "phase"})
)


class CallbackTrialResultError(RuntimeError):
    """Raised when callback results cannot support a matched experiment."""


def _exact(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise CallbackTrialResultError(f"{label} fields are invalid")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CallbackTrialResultError(f"{label} must be an integer >= {minimum}")
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise CallbackTrialResultError(f"{label} must be lowercase SHA-256")
    return value


def _copy(value: Any) -> Any:
    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    except (TypeError, ValueError) as exc:
        raise CallbackTrialResultError(f"result is not strict JSON: {exc}") from exc


def _runtime(value: Any, label: str) -> dict[str, Any]:
    runtime = _exact(value, _RUNTIME_FIELDS, label)
    _integer(runtime["now_epoch"], f"{label}.now_epoch")
    _integer(runtime["turn"], f"{label}.turn")
    _integer(runtime["master_seed"], f"{label}.master_seed", minimum=-(1 << 53))
    for field in ("mission_id", "phase", "region_id"):
        if type(runtime[field]) is not str or not runtime[field]:
            raise CallbackTrialResultError(f"{label}.{field} must be non-empty text")
    for field in ("timeline_fingerprint", "ai_seed_fingerprint"):
        _sha256(runtime[field], f"{label}.{field}")
    return _copy(runtime)


def validate_callback_trial_result(
    value: Any,
    *,
    expected_condition: str | None = None,
    expected_capsule_sha256: str | None = None,
    expected_arm_packet_sha256: str | None = None,
) -> dict[str, Any]:
    """Return one normalized, complete, restore-proven callback result."""
    result = _exact(value, _RESULT_FIELDS, "callback result")
    if (
        result["schema_version"] != RESULT_SCHEMA_VERSION
        or result["kind"] != RESULT_KIND
        or result["host_version"] != HOST_VERSION
        or result["capture_track"] not in {"owner_local_modified", "pristine_reference"}
        or result["condition"] not in {"control", "exact_hook"}
        or result["callback_family"] not in CALLBACK_FAMILIES
        or result["status"] != "complete"
        or result["error"] != ""
        or type(result["slots_restored"]) is not bool
        or not result["slots_restored"]
    ):
        raise CallbackTrialResultError("callback result is not complete and restored")
    if expected_condition is not None and result["condition"] != expected_condition:
        raise CallbackTrialResultError("callback result condition mismatch")
    for field in (
        "capsule_sha256",
        "arm_packet_sha256",
        "binding_manifest_sha256",
        "callback_join_sha256",
    ):
        _sha256(result[field], f"callback result.{field}")
    if expected_capsule_sha256 is not None and result["capsule_sha256"] != _sha256(
        expected_capsule_sha256, "expected capsule digest"
    ):
        raise CallbackTrialResultError("callback result capsule digest mismatch")
    if expected_arm_packet_sha256 is not None and result["arm_packet_sha256"] != _sha256(
        expected_arm_packet_sha256, "expected arm packet digest"
    ):
        raise CallbackTrialResultError("callback result arm digest mismatch")
    if type(result["capture_id"]) is not str or _CAPTURE_ID_RE.fullmatch(
        result["capture_id"]
    ) is None:
        raise CallbackTrialResultError("callback result capture_id is invalid")
    for field in (
        "checkpoint_seq",
        "raw_event_count",
        "attempted_calls",
        "serialization_errors",
        "slot_count",
    ):
        _integer(result[field], f"callback result.{field}")
    if result["slot_count"] < 1 or type(result["raw_written"]) is not bool:
        raise CallbackTrialResultError("callback result counters are invalid")
    before = _runtime(result["runtime_before"], "runtime_before")
    after = _runtime(result["runtime_after"], "runtime_after")
    if any(before[field] != after[field] for field in _RUNTIME_STABLE_FIELDS):
        raise CallbackTrialResultError("runtime identity changed inside callback window")
    if (
        before["phase"] != "combat_enemy"
        or after["phase"] != "combat_player"
        or after["turn"] != before["turn"] + 1
    ):
        raise CallbackTrialResultError(
            "callback window did not cover exactly one enemy decision cycle"
        )
    controller = _exact(result["controller_status"], _CONTROLLER_FIELDS, "controller_status")
    if any(type(controller[field]) is not bool for field in _CONTROLLER_FIELDS):
        raise CallbackTrialResultError("controller status flags must be booleans")
    if not controller["consumed"] or not controller["prepared"] or controller["activated"]:
        raise CallbackTrialResultError("controller did not finish in a safe state")
    if result["condition"] == "control":
        if (
            result["raw_written"]
            or result["raw_event_count"] != 0
            or result["attempted_calls"] != 0
            or result["serialization_errors"] != 0
            or controller["written"]
        ):
            raise CallbackTrialResultError("control callback result contains hook output")
    else:
        if not result["raw_written"] or not controller["written"]:
            raise CallbackTrialResultError("exact-hook callback result lacks raw output")
        if result["raw_event_count"] > result["attempted_calls"]:
            raise CallbackTrialResultError("accepted callback events exceed attempts")
    return _copy(result)


def compare_callback_trial_results(
    control: Any,
    exact_hook: Any,
    *,
    expected_capsule_sha256: str,
    expected_arm_packet_sha256: str,
) -> dict[str, Any]:
    """Prove a useful matched pair; zero-event exact trials are insufficient."""
    left = validate_callback_trial_result(
        control,
        expected_condition="control",
        expected_capsule_sha256=expected_capsule_sha256,
        expected_arm_packet_sha256=expected_arm_packet_sha256,
    )
    right = validate_callback_trial_result(
        exact_hook,
        expected_condition="exact_hook",
        expected_capsule_sha256=expected_capsule_sha256,
        expected_arm_packet_sha256=expected_arm_packet_sha256,
    )
    if any(left[field] != right[field] for field in _PAIR_IDENTITY_FIELDS):
        raise CallbackTrialResultError("callback pair identity mismatch")
    for boundary in ("runtime_before", "runtime_after"):
        if any(
            left[boundary][field] != right[boundary][field]
            for field in _RUNTIME_IDENTITY_FIELDS
        ):
            raise CallbackTrialResultError("callback pair runtime identity mismatch")
    if right["attempted_calls"] < 1 or right["raw_event_count"] < 1:
        raise CallbackTrialResultError("exact-hook callback run observed no usable calls")
    if right["serialization_errors"] != 0:
        raise CallbackTrialResultError("exact-hook callback run had adapter errors")
    return {
        "schema_version": 1,
        "kind": "observatory_callback_trial_result_comparison",
        "status": "matched",
        "capture_id": right["capture_id"],
        "callback_family": right["callback_family"],
        "capsule_sha256": right["capsule_sha256"],
        "arm_packet_sha256": right["arm_packet_sha256"],
        "binding_manifest_sha256": right["binding_manifest_sha256"],
        "callback_join_sha256": right["callback_join_sha256"],
        "checkpoint_seq": right["checkpoint_seq"],
        "slot_count": right["slot_count"],
        "exact_hook_attempted_calls": right["attempted_calls"],
        "exact_hook_event_count": right["raw_event_count"],
        "serialization_errors": right["serialization_errors"],
        "both_restored": True,
    }
