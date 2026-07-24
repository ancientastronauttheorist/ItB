"""Bounded, deterministic codecs for future ITB engine traces.

This module is deliberately independent of the live bridge. It defines the
side-band evidence contract and exercises caps/error isolation without
installing Lua hooks, writing game files, or touching an achievement session.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


SCHEMA_VERSION = 1
HARD_MAX_BUNDLE_BYTES = 64 * 1024 * 1024
KNOWN_PHASES = frozenset({"combat_enemy", "combat_player"})
KNOWN_PLATFORMS = frozenset({"windows", "macos", "linux"})
KNOWN_ARCHITECTURES = frozenset(
    {"x86", "x86_64", "arm", "armv7", "arm64", "universal", "unknown"}
)
KNOWN_ARCHITECTURE_SLICES = KNOWN_ARCHITECTURES - {"universal", "unknown"}
BUILD_EVIDENCE_KINDS = frozenset(
    {"local_appmanifest", "public_depot_listing", "unavailable"}
)
EVENT_KINDS = frozenset(
    {
        "random_int",
        "random_bool",
        "enemy_candidate",
        "enemy_target_score",
        "score_positioning",
        "get_target_area",
        "get_skill_effect",
        "enemy_action_selected",
    }
)
BUILD_IDENTITY_FIELDS = frozenset(
    {
        "platform",
        "architecture",
        "architectures",
        "executable_sha256",
        "build_id",
        "depot_manifest",
        "build_evidence",
        "scripts_revision_sha256",
        "maps_revision_sha256",
    }
)
CONFIG_FIELDS = frozenset(
    {
        "enabled",
        "allowed_phases",
        "max_events",
        "max_events_per_turn",
        "max_event_bytes",
        "max_total_event_bytes",
        "max_bundle_bytes",
    }
)
EVENT_FIELDS = frozenset(
    {"seq", "kind", "phase", "mission_id", "turn", "context", "payload"}
)
SUMMARY_FIELDS = frozenset(
    {
        "accepted_events",
        "event_bytes",
        "dropped_events",
        "filtered_events",
        "serialization_errors",
        "truncated",
        "truncation_reasons",
    }
)
TOP_LEVEL_FIELDS = frozenset(
    {"schema_version", "build_identity", "config", "events", "summary"}
)
TRUNCATION_REASONS = frozenset(
    {
        "max_events",
        "max_events_per_turn",
        "max_event_bytes",
        "max_total_event_bytes",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DIGITS_RE = re.compile(r"^[0-9]+$")


class TraceCodecError(RuntimeError):
    """Raised for malformed or internally inconsistent trace evidence."""


@dataclass(frozen=True)
class TraceConfig:
    """Hard bounds and phase filter for an opt-in trace."""

    enabled: bool = False
    allowed_phases: tuple[str, ...] = ("combat_enemy",)
    max_events: int = 4096
    max_events_per_turn: int = 1024
    max_event_bytes: int = 64 * 1024
    max_total_event_bytes: int = 4 * 1024 * 1024
    max_bundle_bytes: int = 8 * 1024 * 1024

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be boolean")
        phases = self.allowed_phases
        if isinstance(phases, (str, bytes)) or not isinstance(
            phases, Sequence
        ):
            raise ValueError("allowed_phases must be a tuple or list")
        phases = tuple(phases)
        if (
            not phases
            or any(type(phase) is not str for phase in phases)
            or any(phase not in KNOWN_PHASES for phase in phases)
            or len(set(phases)) != len(phases)
        ):
            raise ValueError(
                "allowed_phases must contain unique known phase names"
            )
        object.__setattr__(self, "allowed_phases", phases)
        for name in (
            "max_events",
            "max_events_per_turn",
            "max_event_bytes",
            "max_total_event_bytes",
            "max_bundle_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_bundle_bytes > HARD_MAX_BUNDLE_BYTES:
            raise ValueError(
                f"max_bundle_bytes exceeds hard limit "
                f"{HARD_MAX_BUNDLE_BYTES}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "allowed_phases": sorted(self.allowed_phases),
            "max_events": self.max_events,
            "max_events_per_turn": self.max_events_per_turn,
            "max_event_bytes": self.max_event_bytes,
            "max_total_event_bytes": self.max_total_event_bytes,
            "max_bundle_bytes": self.max_bundle_bytes,
        }


def _canonical_line(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _json_copy(value: Any) -> Any:
    return json.loads(_canonical_line(value))


def _require_exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    label: str,
) -> None:
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise TraceCodecError(
            f"{label} missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise TraceCodecError(
            f"{label} has unknown fields: {', '.join(sorted(unknown))}"
        )


def _validate_sha256(value: Any, label: str) -> str:
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise TraceCodecError(f"{label} must be lowercase SHA-256")
    return value


def _validate_build_identity(identity: Any) -> dict[str, Any]:
    if not isinstance(identity, Mapping):
        raise TraceCodecError("build_identity must be an object")
    _require_exact_fields(identity, BUILD_IDENTITY_FIELDS, "build_identity")
    result = dict(identity)
    if (
        type(result["platform"]) is not str
        or result["platform"] not in KNOWN_PLATFORMS
    ):
        raise TraceCodecError("invalid build_identity.platform")
    if (
        type(result["architecture"]) is not str
        or result["architecture"] not in KNOWN_ARCHITECTURES
    ):
        raise TraceCodecError("invalid build_identity.architecture")
    slices = result["architectures"]
    if result["architecture"] == "universal":
        if (
            not isinstance(slices, list)
            or not slices
            or any(
                type(item) is not str
                or item not in KNOWN_ARCHITECTURE_SLICES
                for item in slices
            )
            or slices != sorted(set(slices))
        ):
            raise TraceCodecError(
                "universal build identity requires sorted unique architectures"
            )
    elif slices is not None:
        raise TraceCodecError(
            "non-universal build identity requires null architectures"
        )
    _validate_sha256(
        result["executable_sha256"],
        "build_identity.executable_sha256",
    )
    _validate_sha256(
        result["scripts_revision_sha256"],
        "build_identity.scripts_revision_sha256",
    )
    _validate_sha256(
        result["maps_revision_sha256"],
        "build_identity.maps_revision_sha256",
    )
    evidence = result["build_evidence"]
    if type(evidence) is not str or evidence not in BUILD_EVIDENCE_KINDS:
        raise TraceCodecError("invalid build_identity.build_evidence")
    build_id = result["build_id"]
    manifest = result["depot_manifest"]
    if evidence == "unavailable":
        if build_id is not None or manifest is not None:
            raise TraceCodecError(
                "unavailable build evidence requires null build/manifest"
            )
    elif not (
        type(build_id) is str
        and _DIGITS_RE.fullmatch(build_id)
        and type(manifest) is str
        and _DIGITS_RE.fullmatch(manifest)
    ):
        raise TraceCodecError(
            "known build evidence requires numeric build/manifest strings"
        )
    return _json_copy(result)


def _coordinate(value: Any, label: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(part) is not int or part < 0 or part > 7 for part in value)
    ):
        raise TraceCodecError(f"{label} must be an [x, y] board coordinate")


def _integer(value: Any, label: str, *, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise TraceCodecError(f"{label} must be an integer >= {minimum}")


def _number(value: Any, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise TraceCodecError(f"{label} must be a finite number")


def _text(value: Any, label: str) -> None:
    if type(value) is not str or not value:
        raise TraceCodecError(f"{label} must be a non-empty string")


def _validate_actor_fields(payload: Mapping[str, Any], prefix: str) -> None:
    _integer(payload["pawn_uid"], f"{prefix}.pawn_uid")
    _text(payload["skill_id"], f"{prefix}.skill_id")
    _coordinate(payload["origin"], f"{prefix}.origin")
    _coordinate(payload["destination"], f"{prefix}.destination")
    _coordinate(payload["target"], f"{prefix}.target")


def _validate_payload(kind: str, payload: Any) -> None:
    if type(kind) is not str:
        raise TraceCodecError("event kind must be text")
    if not isinstance(payload, Mapping):
        raise TraceCodecError("payload must be an object")
    label = f"{kind} payload"
    if kind == "random_int":
        fields = frozenset({"upper_bound", "result"})
        _require_exact_fields(payload, fields, label)
        _integer(payload["upper_bound"], f"{label}.upper_bound", minimum=1)
        _integer(payload["result"], f"{label}.result")
        if payload["result"] >= payload["upper_bound"]:
            raise TraceCodecError(
                f"{label}.result must be below upper_bound"
            )
    elif kind == "random_bool":
        fields = frozenset({"argument", "result"})
        _require_exact_fields(payload, fields, label)
        _integer(payload["argument"], f"{label}.argument", minimum=1)
        if type(payload["result"]) is not bool:
            raise TraceCodecError(f"{label}.result must be boolean")
    elif kind in {
        "enemy_candidate",
        "enemy_target_score",
        "enemy_action_selected",
    }:
        fields = {
            "pawn_uid",
            "skill_id",
            "origin",
            "destination",
            "target",
        }
        if kind != "enemy_action_selected":
            fields.add("candidate_order")
        if kind == "enemy_target_score":
            fields.add("target_score")
        _require_exact_fields(payload, frozenset(fields), label)
        _validate_actor_fields(payload, label)
        if "candidate_order" in fields:
            _integer(
                payload["candidate_order"],
                f"{label}.candidate_order",
            )
        if "target_score" in fields:
            _number(payload["target_score"], f"{label}.target_score")
    elif kind == "score_positioning":
        fields = frozenset(
            {"pawn_uid", "candidate_order", "position", "score"}
        )
        _require_exact_fields(payload, fields, label)
        _integer(payload["pawn_uid"], f"{label}.pawn_uid")
        _integer(
            payload["candidate_order"],
            f"{label}.candidate_order",
        )
        _coordinate(payload["position"], f"{label}.position")
        _number(payload["score"], f"{label}.score")
    elif kind == "get_target_area":
        fields = frozenset(
            {
                "payload_version",
                "representation",
                "pawn_uid",
                "skill_id",
                "origin",
                "target_area",
            }
        )
        _require_exact_fields(payload, fields, label)
        if (
            type(payload["payload_version"]) is not int
            or payload["payload_version"] != 1
        ):
            raise TraceCodecError(f"{label}.payload_version must be 1")
        if payload["representation"] != "coordinate_list":
            raise TraceCodecError(
                f"{label}.representation must be coordinate_list"
            )
        _integer(payload["pawn_uid"], f"{label}.pawn_uid")
        _text(payload["skill_id"], f"{label}.skill_id")
        _coordinate(payload["origin"], f"{label}.origin")
        area = payload["target_area"]
        if not isinstance(area, list):
            raise TraceCodecError(f"{label}.target_area must be an array")
        for index, point in enumerate(area):
            _coordinate(point, f"{label}.target_area[{index}]")
    elif kind == "get_skill_effect":
        fields = frozenset(
            {
                "payload_version",
                "representation",
                "pawn_uid",
                "skill_id",
                "origin",
                "target",
                "primitive_count",
                "summary_sha256",
            }
        )
        _require_exact_fields(payload, fields, label)
        if (
            type(payload["payload_version"]) is not int
            or payload["payload_version"] != 1
        ):
            raise TraceCodecError(f"{label}.payload_version must be 1")
        if payload["representation"] != "opaque_primitive_summary":
            raise TraceCodecError(
                f"{label}.representation must be "
                "opaque_primitive_summary"
            )
        _integer(payload["pawn_uid"], f"{label}.pawn_uid")
        _text(payload["skill_id"], f"{label}.skill_id")
        _coordinate(payload["origin"], f"{label}.origin")
        _coordinate(payload["target"], f"{label}.target")
        _integer(payload["primitive_count"], f"{label}.primitive_count")
        _validate_sha256(
            payload["summary_sha256"],
            f"{label}.summary_sha256",
        )
    else:
        raise TraceCodecError(f"unknown event kind: {kind!r}")


def _validate_context(context: Any) -> None:
    if not isinstance(context, Mapping):
        raise TraceCodecError("context must be an object")
    allowed = frozenset({"call_site", "source"})
    unknown = set(context) - allowed
    if unknown:
        raise TraceCodecError(
            f"context has unknown fields: {', '.join(sorted(unknown))}"
        )
    for key, value in context.items():
        _text(value, f"context.{key}")


class TraceBuffer:
    """Collect events with fail-closed bounds and fail-open observation.

    ``record_lazy`` does not call its payload factory while tracing is disabled,
    filtered by phase, or already capped. Payload/serialization failures are
    counted and swallowed so observation cannot affect the caller's behavior.
    """

    def __init__(
        self,
        build_identity: Mapping[str, Any],
        config: TraceConfig | None = None,
    ) -> None:
        self.build_identity = _validate_build_identity(build_identity)
        self.config = config or TraceConfig()
        self.events: list[dict[str, Any]] = []
        self._turn_counts: Counter[tuple[str, int]] = Counter()
        self._event_bytes = 0
        self._dropped = 0
        self._filtered = 0
        self._serialization_errors = 0
        self._truncation_reasons: Counter[str] = Counter()

    def _drop(self, reason: str) -> bool:
        self._dropped += 1
        self._truncation_reasons[reason] += 1
        return False

    def record_lazy(
        self,
        kind: str,
        *,
        phase: str,
        mission_id: str,
        turn: int,
        payload_factory: Callable[[], Mapping[str, Any]],
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        """Record one event, invoking ``payload_factory`` only when eligible."""
        if not self.config.enabled:
            return False
        if type(phase) is not str or phase not in KNOWN_PHASES:
            self._serialization_errors += 1
            return False
        if phase not in self.config.allowed_phases:
            self._filtered += 1
            return False
        if type(kind) is not str or kind not in EVENT_KINDS:
            self._serialization_errors += 1
            return False
        if (
            type(mission_id) is not str
            or not mission_id
            or type(turn) is not int
            or turn < 0
        ):
            self._serialization_errors += 1
            return False
        if len(self.events) >= self.config.max_events:
            return self._drop("max_events")
        if self._event_bytes >= self.config.max_total_event_bytes:
            return self._drop("max_total_event_bytes")

        turn_key = (mission_id, turn)
        if self._turn_counts[turn_key] >= self.config.max_events_per_turn:
            return self._drop("max_events_per_turn")

        try:
            payload = payload_factory()
            normalized_context = {} if context is None else context
            _validate_context(normalized_context)
            _validate_payload(kind, payload)
            event = {
                "seq": len(self.events),
                "kind": kind,
                "phase": phase,
                "mission_id": mission_id,
                "turn": turn,
                "context": dict(normalized_context),
                "payload": dict(payload),
            }
            rendered = _canonical_line(event)
        except Exception:
            self._serialization_errors += 1
            return False

        byte_count = len(rendered.encode("utf-8")) + 1
        if byte_count > self.config.max_event_bytes:
            return self._drop("max_event_bytes")
        if self._event_bytes + byte_count > self.config.max_total_event_bytes:
            return self._drop("max_total_event_bytes")

        self.events.append(json.loads(rendered))
        self._event_bytes += byte_count
        self._turn_counts[turn_key] += 1
        return True

    def record(
        self,
        kind: str,
        *,
        phase: str,
        mission_id: str,
        turn: int,
        payload: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        return self.record_lazy(
            kind,
            phase=phase,
            mission_id=mission_id,
            turn=turn,
            payload_factory=lambda: payload,
            context=context,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "build_identity": _json_copy(self.build_identity),
            "config": self.config.to_dict(),
            "events": _json_copy(self.events),
            "summary": {
                "accepted_events": len(self.events),
                "event_bytes": self._event_bytes,
                "dropped_events": self._dropped,
                "filtered_events": self._filtered,
                "serialization_errors": self._serialization_errors,
                "truncated": bool(self._truncation_reasons),
                "truncation_reasons": dict(
                    sorted(self._truncation_reasons.items())
                ),
            },
        }


def _render_trace(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def encode_trace(trace: Mapping[str, Any] | TraceBuffer) -> str:
    """Serialize a valid trace deterministically for atomic persistence."""
    value = trace.to_dict() if isinstance(trace, TraceBuffer) else dict(trace)
    rendered = _render_trace(value)
    validated = parse_trace(rendered)
    # ``parse_trace`` checks the actual UTF-8 bytes against the configured cap.
    if validated != value:
        raise TraceCodecError("trace changed during validation")
    return rendered


class _DuplicateKeyError(ValueError):
    pass


def _object_without_duplicates(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _parse_config(config: Any) -> TraceConfig:
    if not isinstance(config, dict):
        raise TraceCodecError("config must be an object")
    _require_exact_fields(config, CONFIG_FIELDS, "config")
    try:
        return TraceConfig(
            enabled=config["enabled"],
            allowed_phases=config["allowed_phases"],
            max_events=config["max_events"],
            max_events_per_turn=config["max_events_per_turn"],
            max_event_bytes=config["max_event_bytes"],
            max_total_event_bytes=config["max_total_event_bytes"],
            max_bundle_bytes=config["max_bundle_bytes"],
        )
    except (TypeError, ValueError) as exc:
        raise TraceCodecError(f"invalid trace config: {exc}") from exc


def parse_trace(text: str) -> dict[str, Any]:
    """Parse and strictly validate a trace bundle."""
    if type(text) is not str:
        raise TraceCodecError("trace input must be text")
    actual_bundle_bytes = len(text.encode("utf-8"))
    if actual_bundle_bytes > HARD_MAX_BUNDLE_BYTES:
        raise TraceCodecError("trace exceeds hard bundle limit")
    try:
        trace = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, _DuplicateKeyError, ValueError) as exc:
        raise TraceCodecError(f"invalid trace JSON: {exc}") from exc
    if not isinstance(trace, dict):
        raise TraceCodecError("trace must be an object")
    _require_exact_fields(trace, TOP_LEVEL_FIELDS, "trace")
    if (
        type(trace["schema_version"]) is not int
        or trace["schema_version"] != SCHEMA_VERSION
    ):
        raise TraceCodecError(
            f"unsupported trace schema: {trace['schema_version']!r}"
        )

    _validate_build_identity(trace["build_identity"])
    parsed_config = _parse_config(trace["config"])
    if actual_bundle_bytes > parsed_config.max_bundle_bytes:
        raise TraceCodecError("trace exceeds max_bundle_bytes")

    events = trace["events"]
    if not isinstance(events, list):
        raise TraceCodecError("events must be an array")
    if not parsed_config.enabled and events:
        raise TraceCodecError("disabled trace cannot contain events")
    if len(events) > parsed_config.max_events:
        raise TraceCodecError("events exceed max_events")
    turn_counts: Counter[tuple[str, int]] = Counter()
    event_bytes = 0
    for expected_seq, event in enumerate(events):
        if not isinstance(event, dict):
            raise TraceCodecError(
                f"events[{expected_seq}] must be an object"
            )
        _require_exact_fields(
            event, EVENT_FIELDS, f"events[{expected_seq}]"
        )
        if type(event["seq"]) is not int or event["seq"] != expected_seq:
            raise TraceCodecError(
                f"non-contiguous event sequence at {expected_seq}"
            )
        kind = event["kind"]
        if type(kind) is not str or kind not in EVENT_KINDS:
            raise TraceCodecError(f"unknown event kind at {expected_seq}")
        if (
            type(event["phase"]) is not str
            or event["phase"] not in parsed_config.allowed_phases
        ):
            raise TraceCodecError(
                f"event phase is outside trace config at {expected_seq}"
            )
        mission_id = event["mission_id"]
        turn = event["turn"]
        if type(mission_id) is not str or not mission_id:
            raise TraceCodecError(
                f"invalid mission_id at {expected_seq}"
            )
        if type(turn) is not int or turn < 0:
            raise TraceCodecError(f"invalid turn at {expected_seq}")
        _validate_context(event["context"])
        _validate_payload(kind, event["payload"])
        try:
            rendered_bytes = (
                len(_canonical_line(event).encode("utf-8")) + 1
            )
        except (TypeError, ValueError) as exc:
            raise TraceCodecError(
                f"event is not canonical JSON at {expected_seq}: {exc}"
            ) from exc
        if rendered_bytes > parsed_config.max_event_bytes:
            raise TraceCodecError(
                f"event exceeds max_event_bytes at {expected_seq}"
            )
        event_bytes += rendered_bytes
        turn_counts[(mission_id, turn)] += 1
        if (
            turn_counts[(mission_id, turn)]
            > parsed_config.max_events_per_turn
        ):
            raise TraceCodecError(
                f"turn exceeds max_events_per_turn at {expected_seq}"
            )
    if event_bytes > parsed_config.max_total_event_bytes:
        raise TraceCodecError("events exceed max_total_event_bytes")

    summary = trace["summary"]
    if not isinstance(summary, dict):
        raise TraceCodecError("summary must be an object")
    _require_exact_fields(summary, SUMMARY_FIELDS, "summary")
    if (
        type(summary["accepted_events"]) is not int
        or summary["accepted_events"] != len(events)
    ):
        raise TraceCodecError("summary accepted_events mismatch")
    if (
        type(summary["event_bytes"]) is not int
        or summary["event_bytes"] != event_bytes
    ):
        raise TraceCodecError("summary event_bytes mismatch")
    for field in (
        "dropped_events",
        "filtered_events",
        "serialization_errors",
    ):
        if type(summary[field]) is not int or summary[field] < 0:
            raise TraceCodecError(f"invalid summary.{field}")
    reasons = summary["truncation_reasons"]
    if not isinstance(reasons, dict) or not all(
        key in TRUNCATION_REASONS
        and type(value) is int
        and value > 0
        for key, value in reasons.items()
    ):
        raise TraceCodecError("invalid summary.truncation_reasons")
    if type(summary["truncated"]) is not bool:
        raise TraceCodecError("summary truncated must be boolean")
    if summary["truncated"] is not bool(reasons):
        raise TraceCodecError("summary truncated flag mismatch")
    if summary["dropped_events"] != sum(reasons.values()):
        raise TraceCodecError("summary dropped_events mismatch")
    return trace
