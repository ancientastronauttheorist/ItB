"""Bounded, deterministic codecs for future ITB engine traces.

This module is deliberately independent of the live bridge. It defines the
side-band evidence contract and exercises caps/error isolation without
installing Lua hooks, writing game files, or touching an achievement session.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = 2
HARD_MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_CAPTURE_WINDOW_SECONDS = 15 * 60
MAX_OBSERVATIONS_PER_KIND = 9_999_999
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
CAPTURE_IDENTITY_FIELDS = frozenset(
    {
        "capture_id",
        "arm_nonce",
        "controller_version",
        "controller_sha256",
        "installed_modloader_sha256",
        "expected_mission_id",
        "expected_turn",
        "timeline_fingerprint",
        "master_seed",
        "region_id",
        "ai_seed_fingerprint",
        "expected_phase",
        "config_sha256",
        "hook_coverage_sha256",
        "activated_at_utc",
        "expires_at_utc",
    }
)
CHECKPOINT_FIELDS = frozenset(
    {
        "seq",
        "reason",
        "mission_id",
        "turn",
        "phase",
        "attempted_calls",
        "started_at_utc",
        "completed_at_utc",
    }
)
HOOK_COVERAGE_FIELDS = frozenset(
    {"event_kind", "target", "target_kind", "status", "source_sha256"}
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
    {
        "schema_version",
        "build_identity",
        "capture_identity",
        "checkpoint",
        "hook_coverage",
        "config",
        "events",
        "summary",
    }
)
TRUNCATION_REASONS = frozenset(
    {
        "max_events",
        "max_events_per_turn",
        "max_event_bytes",
        "max_total_event_bytes",
        "max_bundle_bytes",
        "max_observations_per_kind",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DIGITS_RE = re.compile(r"^[0-9]+$")
_CAPTURE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,127})$")
_NONCE_RE = re.compile(r"^[0-9a-f]{32,64}$")
_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
CHECKPOINT_REASONS = frozenset(
    {"turn_boundary", "mission_end", "explicit"}
)
HOOK_TARGET_KINDS = frozenset(
    {"lua_global", "lua_method", "native_boundary"}
)
HOOK_STATUSES = frozenset({"installed", "unavailable", "disabled"})


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


def trace_config_sha256(config: TraceConfig) -> str:
    """Return the arm-manifest digest for one exact trace policy."""
    return hashlib.sha256(
        _canonical_line(config.to_dict()).encode("utf-8")
    ).hexdigest()


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


def validate_build_identity(identity: Any) -> dict[str, Any]:
    """Return a validated, detached build identity."""
    return _validate_build_identity(identity)


def _validate_utc(value: Any, label: str) -> datetime:
    if type(value) is not str or not _UTC_RE.fullmatch(value):
        raise TraceCodecError(f"{label} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise TraceCodecError(
            f"{label} must be an ISO-8601 UTC timestamp"
        ) from exc
    if parsed.tzinfo != timezone.utc:
        raise TraceCodecError(f"{label} must use UTC")
    return parsed


def _validate_capture_identity(identity: Any) -> dict[str, Any]:
    if not isinstance(identity, Mapping):
        raise TraceCodecError("capture_identity must be an object")
    _require_exact_fields(
        identity,
        CAPTURE_IDENTITY_FIELDS,
        "capture_identity",
    )
    result = dict(identity)
    if (
        type(result["capture_id"]) is not str
        or not _CAPTURE_ID_RE.fullmatch(result["capture_id"])
    ):
        raise TraceCodecError("invalid capture_identity.capture_id")
    if (
        type(result["arm_nonce"]) is not str
        or not _NONCE_RE.fullmatch(result["arm_nonce"])
    ):
        raise TraceCodecError("invalid capture_identity.arm_nonce")
    _text(
        result["controller_version"],
        "capture_identity.controller_version",
    )
    for field in (
        "controller_sha256",
        "installed_modloader_sha256",
        "timeline_fingerprint",
        "ai_seed_fingerprint",
    ):
        _validate_sha256(
            result[field],
            f"capture_identity.{field}",
        )
    _text(
        result["expected_mission_id"],
        "capture_identity.expected_mission_id",
    )
    _integer(
        result["expected_turn"],
        "capture_identity.expected_turn",
    )
    _integer(
        result["master_seed"],
        "capture_identity.master_seed",
        minimum=None,
    )
    _text(result["region_id"], "capture_identity.region_id")
    if (
        type(result["expected_phase"]) is not str
        or result["expected_phase"] not in KNOWN_PHASES
    ):
        raise TraceCodecError("invalid capture_identity.expected_phase")
    _validate_sha256(
        result["config_sha256"],
        "capture_identity.config_sha256",
    )
    _validate_sha256(
        result["hook_coverage_sha256"],
        "capture_identity.hook_coverage_sha256",
    )
    activated = _validate_utc(
        result["activated_at_utc"],
        "capture_identity.activated_at_utc",
    )
    expires = _validate_utc(
        result["expires_at_utc"],
        "capture_identity.expires_at_utc",
    )
    if expires <= activated:
        raise TraceCodecError(
            "capture_identity expiry must follow activation"
        )
    if (
        expires - activated
    ).total_seconds() > MAX_CAPTURE_WINDOW_SECONDS:
        raise TraceCodecError(
            "capture_identity window exceeds the maximum duration"
        )
    return _json_copy(result)


def _validate_checkpoint(
    checkpoint: Any,
    capture_identity: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(checkpoint, Mapping):
        raise TraceCodecError("checkpoint must be an object")
    _require_exact_fields(checkpoint, CHECKPOINT_FIELDS, "checkpoint")
    result = dict(checkpoint)
    _integer(result["seq"], "checkpoint.seq")
    if (
        type(result["reason"]) is not str
        or result["reason"] not in CHECKPOINT_REASONS
    ):
        raise TraceCodecError("invalid checkpoint.reason")
    _text(result["mission_id"], "checkpoint.mission_id")
    _integer(result["turn"], "checkpoint.turn")
    if (
        result["mission_id"] != capture_identity["expected_mission_id"]
        or result["turn"] != capture_identity["expected_turn"]
    ):
        raise TraceCodecError(
            "checkpoint mission/turn does not match capture identity"
        )
    if (
        type(result["phase"]) is not str
        or result["phase"] not in KNOWN_PHASES
    ):
        raise TraceCodecError("invalid checkpoint.phase")
    if result["phase"] != capture_identity["expected_phase"]:
        raise TraceCodecError(
            "checkpoint phase does not match capture identity"
        )
    attempted = result["attempted_calls"]
    if not isinstance(attempted, Mapping):
        raise TraceCodecError("checkpoint.attempted_calls must be an object")
    _require_exact_fields(
        attempted,
        EVENT_KINDS,
        "checkpoint.attempted_calls",
    )
    for kind, count in attempted.items():
        _integer(count, f"checkpoint.attempted_calls.{kind}")
    started = _validate_utc(
        result["started_at_utc"],
        "checkpoint.started_at_utc",
    )
    completed = _validate_utc(
        result["completed_at_utc"],
        "checkpoint.completed_at_utc",
    )
    activated = _validate_utc(
        capture_identity["activated_at_utc"],
        "capture_identity.activated_at_utc",
    )
    expires = _validate_utc(
        capture_identity["expires_at_utc"],
        "capture_identity.expires_at_utc",
    )
    if started < activated or completed < started or completed > expires:
        raise TraceCodecError(
            "checkpoint timestamps fall outside the armed capture window"
        )
    return _json_copy(result)


def _validate_hook_coverage(coverage: Any) -> list[dict[str, Any]]:
    if not isinstance(coverage, list):
        raise TraceCodecError("hook_coverage must be an array")
    result: list[dict[str, Any]] = []
    seen_targets: set[tuple[str, str]] = set()
    covered_kinds: set[str] = set()
    for index, entry in enumerate(coverage):
        label = f"hook_coverage[{index}]"
        if not isinstance(entry, Mapping):
            raise TraceCodecError(f"{label} must be an object")
        _require_exact_fields(entry, HOOK_COVERAGE_FIELDS, label)
        normalized = dict(entry)
        kind = normalized["event_kind"]
        if type(kind) is not str or kind not in EVENT_KINDS:
            raise TraceCodecError(f"invalid {label}.event_kind")
        _text(normalized["target"], f"{label}.target")
        target_kind = normalized["target_kind"]
        if (
            type(target_kind) is not str
            or target_kind not in HOOK_TARGET_KINDS
        ):
            raise TraceCodecError(f"invalid {label}.target_kind")
        status = normalized["status"]
        if type(status) is not str or status not in HOOK_STATUSES:
            raise TraceCodecError(f"invalid {label}.status")
        source_hash = normalized["source_sha256"]
        if source_hash is not None:
            _validate_sha256(source_hash, f"{label}.source_sha256")
        if status == "installed" and source_hash is None:
            raise TraceCodecError(
                f"{label}.source_sha256 is required when installed"
            )
        if status == "unavailable" and source_hash is not None:
            raise TraceCodecError(
                f"{label}.source_sha256 must be null when unavailable"
            )
        target_key = (kind, normalized["target"])
        if target_key in seen_targets:
            raise TraceCodecError(f"duplicate hook coverage target: {target_key}")
        seen_targets.add(target_key)
        covered_kinds.add(kind)
        result.append(normalized)
    expected_order = sorted(
        result,
        key=lambda item: (item["event_kind"], item["target"]),
    )
    if result != expected_order:
        raise TraceCodecError("hook_coverage must use canonical order")
    missing = EVENT_KINDS - covered_kinds
    if missing:
        raise TraceCodecError(
            "hook_coverage missing event kinds: "
            + ", ".join(sorted(missing))
        )
    return _json_copy(result)


def hook_coverage_sha256(coverage: Any) -> str:
    """Return the arm-manifest digest for canonical hook coverage."""
    validated = _validate_hook_coverage(coverage)
    return hashlib.sha256(
        _canonical_line(validated).encode("utf-8")
    ).hexdigest()


def _coordinate(value: Any, label: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(part) is not int or part < 0 or part > 7 for part in value)
    ):
        raise TraceCodecError(f"{label} must be an [x, y] board coordinate")


def _integer(
    value: Any,
    label: str,
    *,
    minimum: int | None = 0,
) -> None:
    if type(value) is not int or (
        minimum is not None and value < minimum
    ):
        suffix = (
            "an integer"
            if minimum is None
            else f"an integer >= {minimum}"
        )
        raise TraceCodecError(f"{label} must be {suffix}")


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
        fields = frozenset({"call_order", "upper_bound", "result"})
        _require_exact_fields(payload, fields, label)
        _integer(payload["call_order"], f"{label}.call_order")
        _integer(payload["upper_bound"], f"{label}.upper_bound", minimum=1)
        _integer(payload["result"], f"{label}.result")
        if payload["result"] >= payload["upper_bound"]:
            raise TraceCodecError(
                f"{label}.result must be below upper_bound"
            )
    elif kind == "random_bool":
        fields = frozenset({"call_order", "argument", "result"})
        _require_exact_fields(payload, fields, label)
        _integer(payload["call_order"], f"{label}.call_order")
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


def _validate_context(kind: str, context: Any) -> None:
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
    if kind in {"random_int", "random_bool"} and "call_site" not in context:
        raise TraceCodecError("RNG context requires call_site")


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
        *,
        capture_identity: Mapping[str, Any],
        checkpoint: Mapping[str, Any],
        hook_coverage: Sequence[Mapping[str, Any]],
    ) -> None:
        self.build_identity = _validate_build_identity(build_identity)
        self.capture_identity = _validate_capture_identity(capture_identity)
        self.checkpoint = _validate_checkpoint(
            checkpoint,
            self.capture_identity,
        )
        self.hook_coverage = _validate_hook_coverage(list(hook_coverage))
        self.config = config or TraceConfig()
        if (
            self.capture_identity["config_sha256"]
            != trace_config_sha256(self.config)
        ):
            raise ValueError(
                "trace config does not match armed capture identity"
            )
        if (
            self.capture_identity["hook_coverage_sha256"]
            != hook_coverage_sha256(self.hook_coverage)
        ):
            raise ValueError(
                "hook coverage does not match armed capture identity"
            )
        if (
            self.capture_identity["expected_phase"]
            != self.checkpoint["phase"]
        ):
            raise ValueError(
                "checkpoint phase does not match armed capture identity"
            )
        if self.checkpoint["phase"] not in self.config.allowed_phases:
            raise ValueError(
                "checkpoint phase must be included in allowed_phases"
            )
        installed_kinds = {
            entry["event_kind"]
            for entry in self.hook_coverage
            if entry["status"] == "installed"
        }
        self._installed_targets = {
            kind: {
                entry["target"]
                for entry in self.hook_coverage
                if entry["event_kind"] == kind
                and entry["status"] == "installed"
            }
            for kind in EVENT_KINDS
        }
        if any(self.checkpoint["attempted_calls"].values()):
            raise ValueError(
                "new trace buffer requires zero attempted calls"
            )
        if not self.config.enabled:
            if installed_kinds:
                raise ValueError(
                    "disabled trace cannot report installed hooks"
                )
        self._installed_kinds = installed_kinds
        self._attempted_calls: Counter[str] = Counter()
        self.events: list[dict[str, Any]] = []
        self._turn_counts: Counter[tuple[str, int]] = Counter()
        self._event_bytes = 0
        self._dropped = 0
        self._filtered = 0
        self._serialization_errors = 0
        self._truncation_reasons: Counter[str] = Counter()
        self._sealed = False
        self._counter_reserve_bytes = 0
        empty_bundle_bytes = len(
            _render_trace(self.to_dict()).encode("utf-8")
        )
        if empty_bundle_bytes > self.config.max_bundle_bytes:
            raise ValueError(
                "max_bundle_bytes cannot fit the empty trace envelope"
            )
        if self.config.enabled and installed_kinds:
            reserved = self.to_dict()
            for kind in installed_kinds:
                reserved["checkpoint"]["attempted_calls"][kind] = (
                    MAX_OBSERVATIONS_PER_KIND
                )
            max_outcomes = (
                len(installed_kinds) * MAX_OBSERVATIONS_PER_KIND
            )
            reserved["summary"].update(
                accepted_events=self.config.max_events,
                event_bytes=self.config.max_total_event_bytes,
                dropped_events=max_outcomes,
                filtered_events=max_outcomes,
                serialization_errors=max_outcomes,
                truncated=True,
                truncation_reasons={
                    reason: max_outcomes
                    for reason in sorted(TRUNCATION_REASONS)
                },
            )
            reserved_bytes = len(
                _render_trace(reserved).encode("utf-8")
            )
            if reserved_bytes > self.config.max_bundle_bytes:
                raise ValueError(
                    "max_bundle_bytes cannot fit the counter reserve envelope"
                )
            self._counter_reserve_bytes = (
                reserved_bytes - empty_bundle_bytes
            )

    def _drop(self, reason: str) -> bool:
        self._dropped += 1
        self._truncation_reasons[reason] += 1
        if reason in {
            "max_events",
            "max_events_per_turn",
            "max_total_event_bytes",
            "max_bundle_bytes",
            "max_observations_per_kind",
        }:
            self._sealed = True
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
        if self._sealed:
            return False
        if type(kind) is not str or kind not in EVENT_KINDS:
            return False
        if kind not in self._installed_kinds:
            return False
        if (
            self._attempted_calls[kind]
            >= MAX_OBSERVATIONS_PER_KIND - 1
        ):
            self._attempted_calls[kind] += 1
            return self._drop("max_observations_per_kind")
        self._attempted_calls[kind] += 1
        if type(phase) is not str or phase not in KNOWN_PHASES:
            self._serialization_errors += 1
            return False
        if phase not in self.config.allowed_phases:
            self._filtered += 1
            return False
        if (
            type(mission_id) is not str
            or not mission_id
            or type(turn) is not int
            or turn < 0
        ):
            self._serialization_errors += 1
            return False
        if (
            mission_id != self.capture_identity["expected_mission_id"]
            or turn != self.capture_identity["expected_turn"]
            or phase != self.checkpoint["phase"]
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
            _validate_context(kind, normalized_context)
            if (
                kind in {"random_int", "random_bool"}
                and normalized_context["call_site"]
                not in self._installed_targets[kind]
            ):
                raise TraceCodecError(
                    "RNG call_site is absent from installed hook coverage"
                )
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
        normalized_event = json.loads(rendered)
        projected = self.to_dict()
        projected["events"].append(normalized_event)
        projected["summary"]["accepted_events"] += 1
        projected["summary"]["event_bytes"] += byte_count
        if (
            len(_render_trace(projected).encode("utf-8"))
            + self._counter_reserve_bytes
            > self.config.max_bundle_bytes
        ):
            return self._drop("max_bundle_bytes")

        self.events.append(normalized_event)
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
        checkpoint = _json_copy(self.checkpoint)
        checkpoint["attempted_calls"] = {
            kind: self._attempted_calls[kind]
            for kind in sorted(EVENT_KINDS)
        }
        return {
            "schema_version": SCHEMA_VERSION,
            "build_identity": _json_copy(self.build_identity),
            "capture_identity": _json_copy(self.capture_identity),
            "checkpoint": checkpoint,
            "hook_coverage": _json_copy(self.hook_coverage),
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
    capture_identity = _validate_capture_identity(trace["capture_identity"])
    checkpoint = _validate_checkpoint(
        trace["checkpoint"],
        capture_identity,
    )
    hook_coverage = _validate_hook_coverage(trace["hook_coverage"])
    parsed_config = _parse_config(trace["config"])
    if actual_bundle_bytes > parsed_config.max_bundle_bytes:
        raise TraceCodecError("trace exceeds max_bundle_bytes")
    if (
        capture_identity["config_sha256"]
        != trace_config_sha256(parsed_config)
    ):
        raise TraceCodecError(
            "trace config does not match capture identity"
        )
    if (
        capture_identity["hook_coverage_sha256"]
        != hook_coverage_sha256(hook_coverage)
    ):
        raise TraceCodecError(
            "hook coverage does not match capture identity"
        )
    if checkpoint["phase"] != capture_identity["expected_phase"]:
        raise TraceCodecError(
            "checkpoint phase does not match capture identity"
        )
    if checkpoint["phase"] not in parsed_config.allowed_phases:
        raise TraceCodecError(
            "checkpoint phase is outside trace config"
        )
    installed_kinds = {
        entry["event_kind"]
        for entry in hook_coverage
        if entry["status"] == "installed"
    }
    installed_targets = {
        kind: {
            entry["target"]
            for entry in hook_coverage
            if entry["event_kind"] == kind
            and entry["status"] == "installed"
        }
        for kind in EVENT_KINDS
    }
    if not parsed_config.enabled:
        if installed_kinds:
            raise TraceCodecError(
                "disabled trace cannot report installed hooks"
            )
        if any(checkpoint["attempted_calls"].values()):
            raise TraceCodecError(
                "disabled trace cannot report attempted calls"
            )
    for kind, attempts in checkpoint["attempted_calls"].items():
        if attempts and kind not in installed_kinds:
            raise TraceCodecError(
                f"attempted calls require an installed {kind} hook"
            )

    events = trace["events"]
    if not isinstance(events, list):
        raise TraceCodecError("events must be an array")
    if not parsed_config.enabled and events:
        raise TraceCodecError("disabled trace cannot contain events")
    if len(events) > parsed_config.max_events:
        raise TraceCodecError("events exceed max_events")
    turn_counts: Counter[tuple[str, int]] = Counter()
    accepted_by_kind: Counter[str] = Counter()
    event_bytes = 0
    last_rng_call_order = -1
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
        if kind not in installed_kinds:
            raise TraceCodecError(
                f"event kind lacks installed hook at {expected_seq}"
            )
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
        if (
            mission_id != capture_identity["expected_mission_id"]
            or turn != capture_identity["expected_turn"]
            or event["phase"] != checkpoint["phase"]
        ):
            raise TraceCodecError(
                f"event does not match checkpoint identity at {expected_seq}"
            )
        _validate_context(kind, event["context"])
        if (
            kind in {"random_int", "random_bool"}
            and event["context"]["call_site"] not in installed_targets[kind]
        ):
            raise TraceCodecError(
                f"RNG call_site lacks installed hook at {expected_seq}"
            )
        _validate_payload(kind, event["payload"])
        if kind in {"random_int", "random_bool"}:
            call_order = event["payload"]["call_order"]
            if call_order <= last_rng_call_order:
                raise TraceCodecError(
                    f"non-increasing RNG call_order at {expected_seq}"
                )
            last_rng_call_order = call_order
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
        accepted_by_kind[kind] += 1
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
    attempted_calls = checkpoint["attempted_calls"]
    for kind, accepted in accepted_by_kind.items():
        if attempted_calls[kind] < accepted:
            raise TraceCodecError(
                f"checkpoint attempted count is below accepted {kind} events"
            )
    rng_attempts = (
        attempted_calls["random_int"]
        + attempted_calls["random_bool"]
    )
    if last_rng_call_order >= rng_attempts:
        raise TraceCodecError(
            "RNG call_order exceeds attempted RNG calls"
        )

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
    total_outcomes = (
        len(events)
        + summary["dropped_events"]
        + summary["filtered_events"]
        + summary["serialization_errors"]
    )
    if sum(attempted_calls.values()) != total_outcomes:
        raise TraceCodecError(
            "checkpoint attempted calls do not reconcile with outcomes"
        )
    return trace
