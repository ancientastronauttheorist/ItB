"""Strict trust boundary for dormant Lua Observatory checkpoints.

Lua checkpoints are intentionally untrusted and non-authoritative.  This
module binds one checkpoint to separately trusted build/capture inputs,
recomputes canonical byte counts, and emits only a normal schema-v2 trace that
passes the existing codec.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from src.observatory.trace_codec import (
    EVENT_KINDS,
    HARD_MAX_BUNDLE_BYTES,
    MAX_CAPTURE_WINDOW_SECONDS,
    TraceCodecError,
    build_identity_sha256,
    encode_trace,
    hook_coverage_sha256,
    parse_trace,
    trace_config_sha256,
    validate_build_identity,
    validate_capture_identity,
    validate_hook_coverage,
    validate_trace_config,
)


RAW_SCHEMA_VERSION = 1
RUNTIME_VERSION = "observatory-lua/1"
RNG_CONTROLLER_VERSION = "observatory-controller/1"
CALLBACK_CONTROLLER_VERSION = "observatory-callback-controller/1"
CONTROLLER_VERSIONS = frozenset(
    {RNG_CONTROLLER_VERSION, CALLBACK_CONTROLLER_VERSION}
)
HARD_MAX_EVENTS = 4096
HARD_MAX_EVENTS_PER_TURN = 1024
HARD_MAX_EVENT_BYTES = 64 * 1024
HARD_MAX_TOTAL_EVENT_BYTES = 4 * 1024 * 1024
HARD_MAX_ATTEMPTS = 16 * 1024
HARD_BUNDLE_RESERVE_BYTES = 2 * 1024 * 1024
LUA_MAX_EXACT_INTEGER = (2**53) - 1
RNG_CONTROLLER_KINDS = frozenset({"random_int", "random_bool"})
CALLBACK_CONTROLLER_KINDS = frozenset(
    {
        "enemy_target_score",
        "get_skill_effect",
        "get_target_area",
        "score_positioning",
    }
)
CALLBACK_METHOD_KINDS = {
    "GetTargetArea": "get_target_area",
    "GetTargetScore": "enemy_target_score",
    "GetSkillEffect": "get_skill_effect",
    "ScorePositioning": "score_positioning",
}
_CALLBACK_TARGET_RE = re.compile(
    r"^runtime\.callback\.(slot-[0-9]{4})\."
    r"(GetTargetArea|GetTargetScore|GetSkillEffect|ScorePositioning)\."
    r"(fn-[0-9]{4})$"
)

RAW_FIELDS = frozenset(
    {
        "raw_schema_version",
        "runtime_version",
        "capture_id",
        "checkpoint_seq",
        "arm_nonce",
        "controller_version",
        "controller_sha256",
        "installed_modloader_sha256",
        "build_identity_sha256",
        "expected_mission_id",
        "expected_turn",
        "expected_phase",
        "timeline_fingerprint",
        "master_seed",
        "region_id",
        "ai_seed_fingerprint",
        "config_sha256",
        "hook_coverage_sha256",
        "config",
        "hook_coverage",
        "activated_epoch",
        "expires_epoch",
        "started_epoch",
        "completed_epoch",
        "checkpoint_reason",
        "attempted_calls",
        "events",
        "summary",
    }
)
RAW_SUMMARY_FIELDS = frozenset(
    {
        "accepted_events",
        "event_byte_upper_bound",
        "dropped_events",
        "filtered_events",
        "serialization_errors",
        "truncation_reasons",
        "stop_reasons",
        "restore_conflicts",
    }
)
SAFE_STOP_REASONS = frozenset(
    {
        "max_attempts",
        "max_events",
        "max_events_per_turn",
        "max_total_event_bytes",
    }
)
TRUNCATION_REASONS = frozenset(
    {
        "max_events_per_turn",
        "max_event_bytes",
        "max_total_event_bytes",
    }
)
CHECKPOINT_REASONS = frozenset(
    {"turn_boundary", "mission_end", "explicit"}
)
HOOK_PLAN_FIELDS = frozenset(
    {
        "hook_id",
        "event_kind",
        "target",
        "target_kind",
        "status",
        "source_sha256",
    }
)
ARM_PACKET_FIELDS = frozenset(
    {
        "arm_packet_schema_version",
        "build_identity",
        "manifest",
        "trusted",
        "policy",
        "hook_plan",
    }
)
_CAPTURE_RAW_FIELDS = (
    "capture_id",
    "arm_nonce",
    "controller_version",
    "controller_sha256",
    "installed_modloader_sha256",
    "expected_mission_id",
    "expected_turn",
    "expected_phase",
    "timeline_fingerprint",
    "master_seed",
    "region_id",
    "ai_seed_fingerprint",
    "config_sha256",
    "hook_coverage_sha256",
)

_RAW_EVENT_FIELDS = frozenset(
    {"seq", "kind", "phase", "mission_id", "turn", "context", "payload"}
)
_CALLBACK_EFFECT_SUMMARY_FIELDS = frozenset({"effect", "q_effect"})
_CALLBACK_EFFECT_RECORD_FIELDS = frozenset({"index", "fields"})
_CALLBACK_EFFECT_FIELD_FIELDS = frozenset({"name", "value"})
_CALLBACK_EFFECT_FIELD_ORDER = (
    "bEvacuate",
    "bHide",
    "bHideIcon",
    "bHidePath",
    "bKO_Effect",
    "bSimpleMark",
    "fDelay",
    "iAcid",
    "iCrack",
    "iDamage",
    "iFire",
    "iFrozen",
    "iInjure",
    "iPawnTeam",
    "iPush",
    "iShield",
    "iSmoke",
    "iTerrain",
    "sAnimation",
    "sImageMark",
    "sItem",
    "sPawn",
    "sScript",
    "sSound",
    "loc",
    "piOrigin",
    "piTarget",
)
_CALLBACK_EFFECT_POINT_FIELDS = frozenset({"loc", "piOrigin", "piTarget"})
_CALLBACK_EFFECT_FIELD_RANK = {
    name: index for index, name in enumerate(_CALLBACK_EFFECT_FIELD_ORDER)
}


class RawTraceError(RuntimeError):
    """Raised when an arm packet or raw checkpoint fails closed."""


def _canonical_line(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _copy(value: Any) -> Any:
    return json.loads(_canonical_line(value))


def _exact_fields(
    value: Any,
    expected: frozenset[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RawTraceError(f"{label} must be an object")
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise RawTraceError(
            f"{label} missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise RawTraceError(
            f"{label} has unknown fields: {', '.join(sorted(unknown))}"
        )
    return value


def _nonnegative_integer(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise RawTraceError(f"{label} must be an integer >= 0")
    return value


def _bounded_utf8(value: Any, limit: int, label: str) -> None:
    if type(value) is not str or not value:
        raise RawTraceError(f"{label} must be non-empty text")
    try:
        byte_count = len(value.encode("utf-8", errors="strict"))
    except UnicodeEncodeError as exc:
        raise RawTraceError(f"{label} is not valid UTF-8") from exc
    if byte_count > limit:
        raise RawTraceError(f"{label} exceeds the Lua runtime byte limit")


def _lua_integer(
    value: Any,
    label: str,
    *,
    minimum: int | None = None,
) -> int:
    if (
        type(value) is not int
        or abs(value) > LUA_MAX_EXACT_INTEGER
        or (minimum is not None and value < minimum)
    ):
        raise RawTraceError(
            f"{label} is outside the exact Lua integer range"
        )
    return value


def _positive_counts(
    value: Any,
    *,
    allowed: frozenset[str],
    label: str,
) -> dict[str, int]:
    # The in-game Lua JSON encoder has no table shape metadata and serializes
    # an empty key/value table as ``[]``. Accept only that empty transport
    # sentinel; a non-empty array can never represent a trusted reason map.
    if value == []:
        return {}
    if not isinstance(value, Mapping):
        raise RawTraceError(f"{label} must be an object")
    result: dict[str, int] = {}
    for key, count in value.items():
        if type(key) is not str or key not in allowed:
            raise RawTraceError(f"invalid {label} key: {key!r}")
        if type(count) is not int or count <= 0:
            raise RawTraceError(f"{label}.{key} must be an integer > 0")
        result[key] = count
    return dict(sorted(result.items()))


def _event_bytes(events: Sequence[Any]) -> int:
    try:
        return sum(
            len(_canonical_line(event).encode("utf-8")) + 1
            for event in events
        )
    except (TypeError, ValueError) as exc:
        raise RawTraceError(f"raw events are not canonical JSON: {exc}") from exc


def _parse_utc_epoch(value: str, label: str) -> int:
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except (TypeError, ValueError) as exc:
        raise RawTraceError(f"{label} is not a UTC timestamp") from exc
    try:
        timestamp = parsed.timestamp()
    except (OverflowError, OSError, ValueError) as exc:
        raise RawTraceError(f"{label} is outside the supported range") from exc
    if timestamp != int(timestamp):
        raise RawTraceError(
            f"{label} must use whole seconds for the Lua runtime"
        )
    return int(timestamp)


def _format_epoch(value: int) -> str:
    try:
        return datetime.fromtimestamp(value, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (OverflowError, OSError, ValueError) as exc:
        raise RawTraceError("epoch is outside the supported UTC range") from exc


def _type_safe_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(
            _type_safe_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _type_safe_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def _validated_inputs(
    build_identity: Mapping[str, Any],
    capture_identity: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        build = validate_build_identity(build_identity)
        capture = validate_capture_identity(capture_identity)
    except TraceCodecError as exc:
        raise RawTraceError(f"invalid trusted identity: {exc}") from exc
    if build["build_evidence"] == "unavailable":
        raise RawTraceError(
            "authoritative Observatory evidence requires build/manifest proof"
        )
    return build, capture


def _validate_lua_config(config: Any) -> None:
    if not config.enabled:
        raise RawTraceError("Lua capture config must be enabled")
    if config.allowed_phases != ("combat_enemy",):
        raise RawTraceError("Lua captures require only combat_enemy")
    if config.max_events > HARD_MAX_EVENTS:
        raise RawTraceError("max_events exceeds the Lua runtime limit")
    if config.max_events_per_turn > HARD_MAX_EVENTS_PER_TURN:
        raise RawTraceError(
            "max_events_per_turn exceeds the Lua runtime limit"
        )
    if config.max_events_per_turn > config.max_events:
        raise RawTraceError("max_events_per_turn exceeds max_events")
    if config.max_event_bytes > HARD_MAX_EVENT_BYTES:
        raise RawTraceError("max_event_bytes exceeds the Lua runtime limit")
    if config.max_total_event_bytes > HARD_MAX_TOTAL_EVENT_BYTES:
        raise RawTraceError(
            "max_total_event_bytes exceeds the Lua runtime limit"
        )
    if config.max_event_bytes > config.max_total_event_bytes:
        raise RawTraceError("max_event_bytes exceeds max_total_event_bytes")
    if (
        config.max_bundle_bytes
        < config.max_total_event_bytes + HARD_BUNDLE_RESERVE_BYTES
    ):
        raise RawTraceError(
            "max_bundle_bytes lacks the Lua checkpoint reserve"
        )


def _validate_hook_plan(
    hook_plan: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if (
        isinstance(hook_plan, (str, bytes))
        or not isinstance(hook_plan, Sequence)
        or not hook_plan
        or len(hook_plan) > 256
    ):
        raise RawTraceError("hook_plan must contain 1 to 256 entries")
    normalized: list[dict[str, Any]] = []
    hook_ids: set[str] = set()
    for index, entry in enumerate(hook_plan):
        item = _exact_fields(
            entry, HOOK_PLAN_FIELDS, f"hook_plan[{index}]"
        )
        hook_id = item["hook_id"]
        if (
            type(hook_id) is not str
            or not hook_id
            or hook_id[0] not in "abcdefghijklmnopqrstuvwxyz0123456789"
            or any(
                character
                not in "abcdefghijklmnopqrstuvwxyz0123456789._:-"
                for character in hook_id
            )
            or hook_id in hook_ids
        ):
            raise RawTraceError(f"invalid hook_plan[{index}].hook_id")
        _bounded_utf8(hook_id, 128, f"hook_plan[{index}].hook_id")
        _bounded_utf8(item["target"], 256, f"hook_plan[{index}].target")
        hook_ids.add(hook_id)
        normalized.append(dict(item))
    expected = sorted(
        normalized,
        key=lambda item: (item["event_kind"], item["target"]),
    )
    if normalized != expected:
        raise RawTraceError("hook_plan must use canonical order")
    coverage = [
        {key: item[key] for key in item if key != "hook_id"}
        for item in normalized
    ]
    try:
        validated_coverage = validate_hook_coverage(coverage)
    except TraceCodecError as exc:
        raise RawTraceError(f"invalid hook_plan coverage: {exc}") from exc
    if any(entry["status"] == "unavailable" for entry in validated_coverage):
        raise RawTraceError(
            "Lua arm plans must use installed or disabled status"
        )
    if any(entry["source_sha256"] is None for entry in validated_coverage):
        raise RawTraceError(
            "Lua arm plans require source_sha256 for every entry"
        )
    return _copy(normalized), validated_coverage


def build_arm_packet(
    *,
    build_identity: Mapping[str, Any],
    capture_identity: Mapping[str, Any],
    config: Mapping[str, Any],
    hook_plan: Sequence[Mapping[str, Any]],
    max_attempts: int,
    checkpoint_seq: int,
) -> dict[str, Any]:
    """Build the exact inert data packet consumed by the Lua controller.

    Bindings and observers are deliberately absent: game-side integration must
    provide already-proven function bindings and cannot smuggle them through
    JSON.
    """
    build, capture = _validated_inputs(build_identity, capture_identity)
    _lua_integer(checkpoint_seq, "checkpoint_seq", minimum=0)
    for field, limit in (
        ("controller_version", 128),
        ("expected_mission_id", 256),
        ("region_id", 128),
    ):
        _bounded_utf8(
            capture[field], limit, f"capture_identity.{field}"
        )
    _lua_integer(
        capture["expected_turn"],
        "capture_identity.expected_turn",
        minimum=0,
    )
    _lua_integer(capture["master_seed"], "capture_identity.master_seed")
    try:
        parsed_config = validate_trace_config(config)
    except TraceCodecError as exc:
        raise RawTraceError(f"invalid trace config: {exc}") from exc
    if capture["expected_phase"] != "combat_enemy":
        raise RawTraceError("Lua Observatory captures require combat_enemy")
    controller_version = capture["controller_version"]
    if controller_version not in CONTROLLER_VERSIONS:
        raise RawTraceError("unsupported Observatory controller version")
    _validate_lua_config(parsed_config)
    if (
        type(max_attempts) is not int
        or max_attempts < 1
        or max_attempts > HARD_MAX_ATTEMPTS
    ):
        raise RawTraceError("max_attempts is outside the Lua runtime limit")

    normalized_plan, coverage = _validate_hook_plan(hook_plan)
    installed_kinds = sorted(
        {
            entry["event_kind"]
            for entry in coverage
            if entry["status"] == "installed"
        }
    )
    if not installed_kinds:
        raise RawTraceError("arm packet requires at least one installed hook")
    installed_entries = [
        entry for entry in coverage if entry["status"] == "installed"
    ]
    if controller_version == RNG_CONTROLLER_VERSION:
        if (
            len(installed_entries) != 1
            or installed_entries[0]["event_kind"] not in RNG_CONTROLLER_KINDS
        ):
            raise RawTraceError(
                "RNG controller requires exactly one installed RNG hook"
            )
        installed = installed_entries[0]
        expected_target = f"_G.{installed['event_kind']}"
        if (
            installed["target"] != expected_target
            or installed["target_kind"] != "lua_global"
        ):
            raise RawTraceError(
                "RNG controller requires the exact Lua global RNG target"
            )
    else:
        if len(installed_kinds) != 1 or installed_kinds[0] not in (
            CALLBACK_CONTROLLER_KINDS
        ):
            raise RawTraceError(
                "callback controller requires exactly one installed family"
            )
        installed_kind = installed_kinds[0]
        callback_entries = []
        for entry in normalized_plan:
            match = _CALLBACK_TARGET_RE.fullmatch(entry["target"])
            if match is None:
                if entry["status"] == "installed":
                    raise RawTraceError(
                        "callback controller accepts only exact callback slots"
                    )
                continue
            callback_entries.append(entry)
            slot_id, method, _function_id = match.groups()
            expected_kind = CALLBACK_METHOD_KINDS[method]
            expected_target_kind = (
                "lua_global" if method == "ScorePositioning" else "lua_method"
            )
            if (
                entry["hook_id"] != f"callback.{slot_id}"
                or entry["event_kind"] != expected_kind
                or entry["target_kind"] != expected_target_kind
                or (entry["status"] == "installed")
                != (entry["event_kind"] == installed_kind)
            ):
                raise RawTraceError(
                    "callback controller hook plan is not family-complete"
                )
        if not callback_entries or not installed_entries:
            raise RawTraceError("callback controller has no resolved slots")
    config_digest = trace_config_sha256(parsed_config)
    coverage_digest = hook_coverage_sha256(coverage)
    if capture["config_sha256"] != config_digest:
        raise RawTraceError("capture identity config digest mismatch")
    if capture["hook_coverage_sha256"] != coverage_digest:
        raise RawTraceError("capture identity hook coverage digest mismatch")
    activated_epoch = _parse_utc_epoch(
        capture["activated_at_utc"],
        "capture_identity.activated_at_utc",
    )
    expires_epoch = _parse_utc_epoch(
        capture["expires_at_utc"],
        "capture_identity.expires_at_utc",
    )
    if (
        activated_epoch < 0
        or expires_epoch < 0
        or expires_epoch <= activated_epoch
        or expires_epoch - activated_epoch > MAX_CAPTURE_WINDOW_SECONDS
    ):
        raise RawTraceError("capture window is invalid")

    policy = {
        "expected_phase": capture["expected_phase"],
        "max_events": parsed_config.max_events,
        "max_events_per_turn": parsed_config.max_events_per_turn,
        "max_event_bytes": parsed_config.max_event_bytes,
        "max_total_event_bytes": parsed_config.max_total_event_bytes,
        "max_attempts": max_attempts,
        "max_bundle_bytes": parsed_config.max_bundle_bytes,
        "allowed_kinds": installed_kinds,
    }
    trusted = {
        "controller_sha256": capture["controller_sha256"],
        "installed_modloader_sha256": capture[
            "installed_modloader_sha256"
        ],
        "build_identity_sha256": build_identity_sha256(build),
        "config_sha256": config_digest,
        "hook_coverage_sha256": coverage_digest,
    }
    manifest = {
        "schema_version": RAW_SCHEMA_VERSION,
        "checkpoint_seq": checkpoint_seq,
        **{
            field: capture[field]
            for field in _CAPTURE_RAW_FIELDS
            if field not in {"config_sha256", "hook_coverage_sha256"}
        },
        "build_identity_sha256": trusted["build_identity_sha256"],
        "config_sha256": config_digest,
        "hook_coverage_sha256": coverage_digest,
        "activated_epoch": activated_epoch,
        "expires_epoch": expires_epoch,
        **{
            field: policy[field]
            for field in (
                "max_events",
                "max_events_per_turn",
                "max_event_bytes",
                "max_total_event_bytes",
                "max_attempts",
                "max_bundle_bytes",
                "allowed_kinds",
            )
        },
    }
    packet = {
        "arm_packet_schema_version": 1,
        "build_identity": build,
        "manifest": manifest,
        "trusted": trusted,
        "policy": policy,
        "hook_plan": normalized_plan,
    }
    _exact_fields(packet, ARM_PACKET_FIELDS, "arm packet")
    return _copy(packet)


def _callback_coordinate(value: Any, label: str) -> list[int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(part) is not int or part < 0 or part > 7 for part in value)
    ):
        raise RawTraceError(f"{label} must be an [x, y] board coordinate")
    return list(value)


def _callback_finite_number(value: Any, label: str) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise RawTraceError(f"{label} must be a finite number")
    return value


def _callback_text(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        raise RawTraceError(f"{label} must be non-empty text")
    return value


def _validate_callback_effect_summary(
    value: Any,
) -> tuple[dict[str, Any], int]:
    summary = _exact_fields(
        value,
        _CALLBACK_EFFECT_SUMMARY_FIELDS,
        "raw GetSkillEffect primitive_summary",
    )
    normalized: dict[str, list[dict[str, Any]]] = {}
    primitive_count = 0
    for list_name in ("effect", "q_effect"):
        raw_records = summary[list_name]
        if not isinstance(raw_records, list) or len(raw_records) > 128:
            raise RawTraceError(
                f"raw GetSkillEffect {list_name} exceeds its record cap"
            )
        records: list[dict[str, Any]] = []
        for record_index, raw_record in enumerate(raw_records):
            record = _exact_fields(
                raw_record,
                _CALLBACK_EFFECT_RECORD_FIELDS,
                f"raw GetSkillEffect {list_name}[{record_index}]",
            )
            if type(record["index"]) is not int or record["index"] != record_index:
                raise RawTraceError(
                    f"raw GetSkillEffect {list_name} record index mismatch"
                )
            raw_fields = record["fields"]
            if not isinstance(raw_fields, list) or len(raw_fields) > len(
                _CALLBACK_EFFECT_FIELD_ORDER
            ):
                raise RawTraceError("raw GetSkillEffect field list is invalid")
            fields: list[dict[str, Any]] = []
            previous_rank = -1
            for field_index, raw_field in enumerate(raw_fields):
                field = _exact_fields(
                    raw_field,
                    _CALLBACK_EFFECT_FIELD_FIELDS,
                    (
                        f"raw GetSkillEffect {list_name}[{record_index}]"
                        f".fields[{field_index}]"
                    ),
                )
                name = field["name"]
                if type(name) is not str or name not in _CALLBACK_EFFECT_FIELD_RANK:
                    raise RawTraceError("raw GetSkillEffect field name is invalid")
                rank = _CALLBACK_EFFECT_FIELD_RANK[name]
                if rank <= previous_rank:
                    raise RawTraceError(
                        "raw GetSkillEffect fields are not canonical"
                    )
                previous_rank = rank
                field_value = field["value"]
                if name in _CALLBACK_EFFECT_POINT_FIELDS:
                    normalized_value: Any = _callback_coordinate(
                        field_value,
                        f"raw GetSkillEffect field {name}",
                    )
                elif type(field_value) in {bool, str}:
                    normalized_value = field_value
                else:
                    normalized_value = _callback_finite_number(
                        field_value,
                        f"raw GetSkillEffect field {name}",
                    )
                fields.append({"name": name, "value": normalized_value})
                primitive_count += 1
            records.append({"index": record_index, "fields": fields})
        normalized[list_name] = records
    return normalized, primitive_count


def _promote_callback_events(
    events: Sequence[Any],
    *,
    controller_version: str,
    installed_kinds: Sequence[str],
) -> list[dict[str, Any]]:
    if controller_version == RNG_CONTROLLER_VERSION:
        return _copy(list(events))
    if (
        controller_version != CALLBACK_CONTROLLER_VERSION
        or len(installed_kinds) != 1
        or installed_kinds[0] not in CALLBACK_CONTROLLER_KINDS
    ):
        raise RawTraceError("raw callback event controller identity is invalid")
    installed_kind = installed_kinds[0]
    promoted: list[dict[str, Any]] = []
    for event_index, raw_event in enumerate(events):
        event = dict(
            _exact_fields(raw_event, _RAW_EVENT_FIELDS, f"raw event[{event_index}]")
        )
        if event["seq"] != event_index or event["kind"] != installed_kind:
            raise RawTraceError("raw callback event sequence or family mismatch")
        payload = event["payload"]
        if installed_kind == "score_positioning":
            promoted_payload = _copy(payload)
        elif installed_kind == "get_target_area":
            raw_payload = _exact_fields(
                payload,
                frozenset(
                    {
                        "payload_version",
                        "representation",
                        "pawn_uid",
                        "skill_id",
                        "origin",
                        "target_area",
                        "call_order",
                    }
                ),
                "raw GetTargetArea payload",
            )
            _nonnegative_integer(
                raw_payload["call_order"], "raw GetTargetArea call_order"
            )
            promoted_payload = {
                key: _copy(raw_payload[key])
                for key in (
                    "payload_version",
                    "representation",
                    "pawn_uid",
                    "skill_id",
                    "origin",
                    "target_area",
                )
            }
        elif installed_kind == "enemy_target_score":
            raw_payload = _exact_fields(
                payload,
                frozenset(
                    {
                        "payload_version",
                        "representation",
                        "pawn_uid",
                        "skill_id",
                        "pawn_space",
                        "p1",
                        "p2",
                        "call_order",
                        "score",
                    }
                ),
                "raw GetTargetScore payload",
            )
            if (
                raw_payload["payload_version"] != 1
                or raw_payload["representation"]
                != "get_target_score_arguments"
            ):
                raise RawTraceError("raw GetTargetScore representation is invalid")
            promoted_payload = {
                "pawn_uid": _nonnegative_integer(
                    raw_payload["pawn_uid"], "raw GetTargetScore pawn_uid"
                ),
                "skill_id": _callback_text(
                    raw_payload["skill_id"], "raw GetTargetScore skill_id"
                ),
                # The shipped Lua contract names p1/p2 as the attack source
                # and target. The live Pawn space remains separate in raw
                # evidence and is promoted as the actor's pre-choice origin.
                "origin": _callback_coordinate(
                    raw_payload["pawn_space"], "raw GetTargetScore pawn_space"
                ),
                "destination": _callback_coordinate(
                    raw_payload["p1"], "raw GetTargetScore p1"
                ),
                "target": _callback_coordinate(
                    raw_payload["p2"], "raw GetTargetScore p2"
                ),
                "candidate_order": _nonnegative_integer(
                    raw_payload["call_order"], "raw GetTargetScore call_order"
                ),
                "target_score": _callback_finite_number(
                    raw_payload["score"], "raw GetTargetScore score"
                ),
            }
        elif installed_kind == "get_skill_effect":
            raw_payload = _exact_fields(
                payload,
                frozenset(
                    {
                        "payload_version",
                        "representation",
                        "pawn_uid",
                        "skill_id",
                        "origin",
                        "target",
                        "call_order",
                        "primitive_count",
                        "primitive_summary",
                    }
                ),
                "raw GetSkillEffect payload",
            )
            if (
                raw_payload["payload_version"] != 1
                or raw_payload["representation"] != "raw_opaque_primitives"
            ):
                raise RawTraceError("raw GetSkillEffect representation is invalid")
            _nonnegative_integer(
                raw_payload["call_order"], "raw GetSkillEffect call_order"
            )
            summary, primitive_count = _validate_callback_effect_summary(
                raw_payload["primitive_summary"]
            )
            if raw_payload["primitive_count"] != primitive_count:
                raise RawTraceError("raw GetSkillEffect primitive_count mismatch")
            summary_sha256 = hashlib.sha256(
                (_canonical_line(summary) + "\n").encode("utf-8")
            ).hexdigest()
            promoted_payload = {
                "payload_version": 1,
                "representation": "opaque_primitive_summary",
                "pawn_uid": _nonnegative_integer(
                    raw_payload["pawn_uid"], "raw GetSkillEffect pawn_uid"
                ),
                "skill_id": _callback_text(
                    raw_payload["skill_id"], "raw GetSkillEffect skill_id"
                ),
                "origin": _callback_coordinate(
                    raw_payload["origin"], "raw GetSkillEffect origin"
                ),
                "target": _callback_coordinate(
                    raw_payload["target"], "raw GetSkillEffect target"
                ),
                "primitive_count": primitive_count,
                "summary_sha256": summary_sha256,
            }
        else:  # pragma: no cover - guarded by the controller kind set.
            raise RawTraceError("unsupported raw callback event kind")
        event["payload"] = promoted_payload
        promoted.append(_copy(event))
    return promoted


def finalize_raw_checkpoint(
    raw_checkpoint: Mapping[str, Any],
    *,
    build_identity: Mapping[str, Any],
    capture_identity: Mapping[str, Any],
    arm_packet: Mapping[str, Any],
    expected_arm_packet_sha256: str,
) -> dict[str, Any]:
    """Convert one exact raw checkpoint into authoritative schema-v2 data."""
    raw = _exact_fields(raw_checkpoint, RAW_FIELDS, "raw checkpoint")
    build, capture = _validated_inputs(build_identity, capture_identity)
    if (
        type(expected_arm_packet_sha256) is not str
        or len(expected_arm_packet_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in expected_arm_packet_sha256
        )
    ):
        raise RawTraceError(
            "expected arm packet digest must be lowercase SHA-256"
        )
    if arm_packet_sha256(arm_packet) != expected_arm_packet_sha256:
        raise RawTraceError("arm packet content digest mismatch")
    packet = _exact_fields(arm_packet, ARM_PACKET_FIELDS, "arm packet")
    if packet["arm_packet_schema_version"] != 1:
        raise RawTraceError("unsupported arm packet schema")
    if not _type_safe_equal(packet["build_identity"], build):
        raise RawTraceError("arm packet build identity mismatch")
    if not isinstance(packet["manifest"], Mapping):
        raise RawTraceError("arm packet manifest must be an object")
    if not isinstance(packet["policy"], Mapping):
        raise RawTraceError("arm packet policy must be an object")
    checkpoint_seq = packet["manifest"].get("checkpoint_seq")
    max_attempts = packet["policy"].get("max_attempts")
    rebuilt_packet = build_arm_packet(
        build_identity=build,
        capture_identity=capture,
        config=raw["config"],
        hook_plan=packet["hook_plan"],
        max_attempts=max_attempts,
        checkpoint_seq=checkpoint_seq,
    )
    if not _type_safe_equal(packet, rebuilt_packet):
        raise RawTraceError("arm packet does not match trusted inputs")
    if raw["raw_schema_version"] != RAW_SCHEMA_VERSION:
        raise RawTraceError("unsupported raw checkpoint schema")
    if raw["runtime_version"] != RUNTIME_VERSION:
        raise RawTraceError("unsupported Lua trace runtime")
    if not _type_safe_equal(raw["checkpoint_seq"], checkpoint_seq):
        raise RawTraceError("raw checkpoint sequence mismatch")
    for field in _CAPTURE_RAW_FIELDS:
        if not _type_safe_equal(raw[field], capture[field]):
            raise RawTraceError(f"raw {field} does not match trusted capture")
    if raw["build_identity_sha256"] != build_identity_sha256(build):
        raise RawTraceError("raw build identity digest mismatch")

    try:
        config = validate_trace_config(raw["config"])
        coverage = validate_hook_coverage(raw["hook_coverage"])
    except TraceCodecError as exc:
        raise RawTraceError(f"invalid raw policy or coverage: {exc}") from exc
    _validate_lua_config(config)
    if capture["expected_phase"] != "combat_enemy":
        raise RawTraceError("Lua Observatory captures require combat_enemy")
    if trace_config_sha256(config) != capture["config_sha256"]:
        raise RawTraceError("raw config digest mismatch")
    if hook_coverage_sha256(coverage) != capture["hook_coverage_sha256"]:
        raise RawTraceError("raw hook coverage digest mismatch")
    packet_coverage = [
        {key: value for key, value in entry.items() if key != "hook_id"}
        for entry in packet["hook_plan"]
    ]
    if not _type_safe_equal(raw["config"], config.to_dict()):
        raise RawTraceError("raw config is not canonical")
    if not _type_safe_equal(coverage, packet_coverage):
        raise RawTraceError("raw hook coverage does not match arm packet")
    if any(entry["status"] == "unavailable" for entry in coverage):
        raise RawTraceError("Lua checkpoint cannot report unavailable hooks")
    installed_kinds = sorted(
        {
            entry["event_kind"]
            for entry in coverage
            if entry["status"] == "installed"
        }
    )

    activated_epoch = _nonnegative_integer(
        raw["activated_epoch"], "raw activated_epoch"
    )
    expires_epoch = _nonnegative_integer(
        raw["expires_epoch"], "raw expires_epoch"
    )
    completed_epoch = _nonnegative_integer(
        raw["completed_epoch"], "raw completed_epoch"
    )
    started_epoch = _nonnegative_integer(
        raw["started_epoch"], "raw started_epoch"
    )
    if activated_epoch != _parse_utc_epoch(
        capture["activated_at_utc"],
        "capture_identity.activated_at_utc",
    ):
        raise RawTraceError("raw activation time mismatch")
    if expires_epoch != _parse_utc_epoch(
        capture["expires_at_utc"],
        "capture_identity.expires_at_utc",
    ):
        raise RawTraceError("raw expiry time mismatch")
    if not activated_epoch <= started_epoch <= completed_epoch <= expires_epoch:
        raise RawTraceError("raw checkpoint times fall outside capture window")
    reason = raw["checkpoint_reason"]
    if type(reason) is not str or reason not in CHECKPOINT_REASONS:
        raise RawTraceError("invalid raw checkpoint reason")

    attempted = _exact_fields(
        raw["attempted_calls"], EVENT_KINDS, "raw attempted_calls"
    )
    attempted_calls = {
        kind: _nonnegative_integer(
            attempted[kind], f"raw attempted_calls.{kind}"
        )
        for kind in sorted(EVENT_KINDS)
    }
    events = raw["events"]
    if not isinstance(events, list):
        raise RawTraceError("raw events must be an array")
    summary = _exact_fields(raw["summary"], RAW_SUMMARY_FIELDS, "raw summary")
    accepted = _nonnegative_integer(
        summary["accepted_events"], "raw summary.accepted_events"
    )
    upper_bound = _nonnegative_integer(
        summary["event_byte_upper_bound"],
        "raw summary.event_byte_upper_bound",
    )
    dropped = _nonnegative_integer(
        summary["dropped_events"], "raw summary.dropped_events"
    )
    filtered = _nonnegative_integer(
        summary["filtered_events"], "raw summary.filtered_events"
    )
    serialization_errors = _nonnegative_integer(
        summary["serialization_errors"],
        "raw summary.serialization_errors",
    )
    restore_conflicts = _nonnegative_integer(
        summary["restore_conflicts"], "raw summary.restore_conflicts"
    )
    if restore_conflicts:
        raise RawTraceError("raw checkpoint reports hook restore conflicts")
    reasons = _positive_counts(
        summary["truncation_reasons"],
        allowed=TRUNCATION_REASONS,
        label="raw summary.truncation_reasons",
    )
    stop_reasons = _positive_counts(
        summary["stop_reasons"],
        allowed=SAFE_STOP_REASONS,
        label="raw summary.stop_reasons",
    )
    if stop_reasons:
        raise RawTraceError(
            "stopped Lua captures are not authoritative final evidence"
        )
    if accepted != len(events):
        raise RawTraceError("raw accepted_events mismatch")
    if dropped != sum(reasons.values()):
        raise RawTraceError("raw dropped_events mismatch")
    unsafe_reasons = set(reasons) - {"max_event_bytes"}
    if unsafe_reasons:
        raise RawTraceError(
            "raw truncation reason implies a stopped capture"
        )
    if filtered:
        raise RawTraceError(
            "filtered Lua events are not authoritative final evidence"
        )
    outcomes = accepted + dropped + filtered + serialization_errors
    if sum(attempted_calls.values()) != outcomes:
        raise RawTraceError(
            "raw attempted calls do not reconcile with outcomes"
        )
    raw_event_bytes = _event_bytes(events)
    if raw_event_bytes > upper_bound:
        raise RawTraceError(
            "raw event byte upper bound is below canonical event bytes"
        )
    if upper_bound >= config.max_total_event_bytes:
        raise RawTraceError(
            "raw event byte bound reached the runtime stop threshold"
        )
    if outcomes >= max_attempts:
        raise RawTraceError("raw attempt count reached the runtime stop threshold")
    if accepted >= config.max_events:
        raise RawTraceError("raw event count reached the runtime stop threshold")
    if accepted > config.max_events_per_turn:
        raise RawTraceError(
            "raw turn event count reached the runtime stop threshold"
        )
    try:
        raw_bytes = len(
            (
                json.dumps(
                    raw,
                    ensure_ascii=False,
                    allow_nan=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise RawTraceError(
            f"raw checkpoint is not canonical JSON: {exc}"
        ) from exc
    if raw_bytes > config.max_bundle_bytes:
        raise RawTraceError("raw checkpoint exceeds max_bundle_bytes")

    promoted_events = _promote_callback_events(
        events,
        controller_version=capture["controller_version"],
        installed_kinds=installed_kinds,
    )
    final_event_bytes = _event_bytes(promoted_events)

    final_trace = {
        "schema_version": 2,
        "build_identity": build,
        "capture_identity": capture,
        "checkpoint": {
            "seq": checkpoint_seq,
            "reason": reason,
            "mission_id": capture["expected_mission_id"],
            "turn": capture["expected_turn"],
            "phase": capture["expected_phase"],
            "attempted_calls": attempted_calls,
            "started_at_utc": _format_epoch(started_epoch),
            "completed_at_utc": _format_epoch(completed_epoch),
        },
        "hook_coverage": coverage,
        "config": config.to_dict(),
        "events": promoted_events,
        "summary": {
            "accepted_events": accepted,
            "event_bytes": final_event_bytes,
            "dropped_events": dropped,
            "filtered_events": filtered,
            "serialization_errors": serialization_errors,
            "truncated": bool(reasons),
            "truncation_reasons": reasons,
        },
    }
    try:
        rendered = encode_trace(final_trace)
        if len(rendered.encode("utf-8")) > HARD_MAX_BUNDLE_BYTES:
            raise RawTraceError("final trace exceeds the hard bundle limit")
        return parse_trace(rendered)
    except TraceCodecError as exc:
        raise RawTraceError(f"raw checkpoint cannot be finalized: {exc}") from exc


def arm_packet_sha256(packet: Mapping[str, Any]) -> str:
    """Digest a generated arm packet for out-of-band operator comparison."""
    _exact_fields(packet, ARM_PACKET_FIELDS, "arm packet")
    return hashlib.sha256(
        (_canonical_line(packet) + "\n").encode("utf-8")
    ).hexdigest()
