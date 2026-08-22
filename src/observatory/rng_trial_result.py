"""Strict validation and comparison for untrusted Lua RNG trial results."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any


RESULT_SCHEMA_VERSION = 2
LEGACY_RANDOM_INT_RESULT_SCHEMA_VERSION = 1
RESULT_KIND = "observatory_rng_trial_result"
COMPARISON_KIND = "observatory_rng_trial_comparison"

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
        "capture_id",
        "checkpoint_seq",
        "status",
        "error",
        "probe",
        "rng_control",
        "runtime_before",
        "runtime_after",
        "controller_status",
        "raw_written",
        "target_restored",
    }
)
_RANDOM_INT_PROBE_FIELDS = frozenset({"kind", "upper_bound", "result"})
_RANDOM_BOOL_PROBE_FIELDS = frozenset({"kind", "argument", "result"})
_RNG_CONTROL_FIELDS = frozenset(
    {
        "kind",
        "seed",
        "expected_result",
        "helper_version",
        "helper_sha256",
        "seed_applied",
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
_CONTROLLER_STATUS_FIELDS = frozenset(
    {"consumed", "prepared", "activated", "written"}
)


class RngTrialResultError(RuntimeError):
    """Raised when a trial result is malformed, incomplete, or mismatched."""


def _exact_fields(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RngTrialResultError(f"{label} must be an object")
    missing = fields - set(value)
    unknown = set(value) - fields
    if missing:
        raise RngTrialResultError(
            f"{label} missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise RngTrialResultError(
            f"{label} has unknown fields: {', '.join(sorted(unknown))}"
        )
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise RngTrialResultError(f"{label} must be lowercase SHA-256")
    return value


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise RngTrialResultError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise RngTrialResultError(f"{label} must be >= {minimum}")
    return value


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise RngTrialResultError(f"{label} must be boolean")
    return value


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str or len(value.encode("utf-8")) > 256:
        raise RngTrialResultError(f"{label} must be bounded text")
    if not allow_empty and not value:
        raise RngTrialResultError(f"{label} must not be empty")
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
        raise RngTrialResultError(f"result is not canonical JSON: {exc}") from exc


def _validate_runtime(value: Any, label: str) -> dict[str, Any]:
    runtime = _exact_fields(value, _RUNTIME_FIELDS, label)
    _integer(runtime["now_epoch"], f"{label}.now_epoch", minimum=0)
    _text(runtime["mission_id"], f"{label}.mission_id")
    _integer(runtime["turn"], f"{label}.turn", minimum=0)
    if runtime["phase"] != "combat_enemy":
        raise RngTrialResultError(f"{label}.phase must be combat_enemy")
    _sha256(runtime["timeline_fingerprint"], f"{label}.timeline_fingerprint")
    _integer(runtime["master_seed"], f"{label}.master_seed")
    _text(runtime["region_id"], f"{label}.region_id")
    _sha256(runtime["ai_seed_fingerprint"], f"{label}.ai_seed_fingerprint")
    return _copy(runtime)


def _runtime_identity(runtime: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _copy(value) for key, value in runtime.items() if key != "now_epoch"}


def result_sha256(value: Mapping[str, Any]) -> str:
    validated = validate_rng_trial_result(value)
    encoded = json.dumps(
        validated,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256((encoded + "\n").encode("utf-8")).hexdigest()


def validate_rng_trial_result(
    value: Any,
    *,
    expected_condition: str | None = None,
    expected_capsule_sha256: str | None = None,
    expected_arm_packet_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate one complete result without trusting its condition labels."""
    result = _exact_fields(value, _RESULT_FIELDS, "result")
    schema_version = result["schema_version"]
    if schema_version not in {
        LEGACY_RANDOM_INT_RESULT_SCHEMA_VERSION,
        RESULT_SCHEMA_VERSION,
    }:
        raise RngTrialResultError("unsupported result schema")
    if result["kind"] != RESULT_KIND:
        raise RngTrialResultError("invalid result kind")
    if result["host_version"] != "observatory-rng-trial-host/2":
        raise RngTrialResultError("unsupported result host")
    if result["capture_track"] not in {
        "owner_local_modified",
        "pristine_reference",
    }:
        raise RngTrialResultError("result capture track is invalid")
    if result["condition"] not in {"control", "exact_hook"}:
        raise RngTrialResultError("result condition is invalid")
    if expected_condition is not None and result["condition"] != expected_condition:
        raise RngTrialResultError("result condition does not match expectation")
    capsule_sha = _sha256(result["capsule_sha256"], "result.capsule_sha256")
    arm_sha = _sha256(result["arm_packet_sha256"], "result.arm_packet_sha256")
    if expected_capsule_sha256 is not None and capsule_sha != _sha256(
        expected_capsule_sha256, "expected_capsule_sha256"
    ):
        raise RngTrialResultError("result capsule digest mismatch")
    if expected_arm_packet_sha256 is not None and arm_sha != _sha256(
        expected_arm_packet_sha256, "expected_arm_packet_sha256"
    ):
        raise RngTrialResultError("result arm digest mismatch")
    capture_id = _text(result["capture_id"], "result.capture_id", allow_empty=False)
    if _CAPTURE_ID_RE.fullmatch(capture_id) is None:
        raise RngTrialResultError("result.capture_id is invalid")
    _integer(result["checkpoint_seq"], "result.checkpoint_seq", minimum=0)
    if result["status"] != "complete" or result["error"] != "":
        raise RngTrialResultError("result did not complete cleanly")
    raw_probe = result["probe"]
    if not isinstance(raw_probe, Mapping):
        raise RngTrialResultError("result.probe must be an object")
    probe_kind = raw_probe.get("kind")
    if (
        schema_version == LEGACY_RANDOM_INT_RESULT_SCHEMA_VERSION
        and probe_kind != "random_int"
    ):
        raise RngTrialResultError("legacy result schema only supports random_int")
    if probe_kind == "random_int":
        probe = _exact_fields(
            raw_probe,
            _RANDOM_INT_PROBE_FIELDS,
            "result.probe",
        )
        probe_argument = _integer(
            probe["upper_bound"],
            "result.probe.upper_bound",
            minimum=2,
        )
        observed: int | bool = _integer(
            probe["result"],
            "result.probe.result",
            minimum=0,
        )
        if observed >= probe_argument:
            raise RngTrialResultError("result probe output exceeds its bound")
    elif probe_kind == "random_bool":
        probe = _exact_fields(
            raw_probe,
            _RANDOM_BOOL_PROBE_FIELDS,
            "result.probe",
        )
        probe_argument = _integer(
            probe["argument"],
            "result.probe.argument",
            minimum=1,
        )
        observed = _boolean(probe["result"], "result.probe.result")
    else:
        raise RngTrialResultError("result probe kind is invalid")
    if probe_argument > 0x7FFFFFFF:
        raise RngTrialResultError("result probe argument exceeds signed 32-bit range")
    rng_control = _exact_fields(
        result["rng_control"],
        _RNG_CONTROL_FIELDS,
        "result.rng_control",
    )
    if rng_control["kind"] != "build_keyed_seed":
        raise RngTrialResultError("result RNG control kind is invalid")
    seed = _integer(rng_control["seed"], "result.rng_control.seed", minimum=0)
    if seed > 0x7FFFFFFF:
        raise RngTrialResultError("result RNG seed exceeds signed 32-bit range")
    if probe_kind == "random_int":
        expected: int | bool = _integer(
            rng_control["expected_result"],
            "result.rng_control.expected_result",
            minimum=0,
        )
        if expected >= probe_argument:
            raise RngTrialResultError("result seeded expectation exceeds its bound")
    else:
        expected = _boolean(
            rng_control["expected_result"],
            "result.rng_control.expected_result",
        )
    if expected != observed:
        raise RngTrialResultError("result probe does not match its seeded expectation")
    draw = (((seed * 0x343FD + 0x269EC3) & 0xFFFFFFFF) >> 16) & 0x7FFF
    calculated: int | bool = draw % probe_argument
    if probe_kind == "random_bool":
        calculated = calculated == 0
    if expected != calculated:
        raise RngTrialResultError("result seeded RNG expectation is invalid")
    if rng_control["helper_version"] != "observatory-rng-seed-helper/1":
        raise RngTrialResultError("result RNG helper version is invalid")
    _sha256(rng_control["helper_sha256"], "result.rng_control.helper_sha256")
    if not _boolean(
        rng_control["seed_applied"],
        "result.rng_control.seed_applied",
    ):
        raise RngTrialResultError("result RNG seed was not applied")
    before = _validate_runtime(result["runtime_before"], "result.runtime_before")
    after = _validate_runtime(result["runtime_after"], "result.runtime_after")
    if after["now_epoch"] < before["now_epoch"]:
        raise RngTrialResultError("result runtime clock moved backward")
    if _runtime_identity(before) != _runtime_identity(after):
        raise RngTrialResultError("result runtime identity changed during probe")
    controller = _exact_fields(
        result["controller_status"],
        _CONTROLLER_STATUS_FIELDS,
        "result.controller_status",
    )
    for field in sorted(_CONTROLLER_STATUS_FIELDS):
        _boolean(controller[field], f"result.controller_status.{field}")
    raw_written = _boolean(result["raw_written"], "result.raw_written")
    _boolean(result["target_restored"], "result.target_restored")
    if not result["target_restored"]:
        raise RngTrialResultError("result target was not restored")
    if not controller["consumed"] or not controller["prepared"] or controller["activated"]:
        raise RngTrialResultError("result controller did not finish in a safe state")
    expected_written = result["condition"] == "exact_hook"
    if raw_written != expected_written or controller["written"] != expected_written:
        raise RngTrialResultError("result raw-write state contradicts its condition")
    return _copy(result)


def compare_rng_trial_results(
    control_result: Mapping[str, Any],
    exact_hook_result: Mapping[str, Any],
    *,
    expected_capsule_sha256: str,
    expected_arm_packet_sha256: str,
) -> dict[str, Any]:
    """Fail closed unless control and exact-hook probe semantics match."""
    control = validate_rng_trial_result(
        control_result,
        expected_condition="control",
        expected_capsule_sha256=expected_capsule_sha256,
        expected_arm_packet_sha256=expected_arm_packet_sha256,
    )
    exact = validate_rng_trial_result(
        exact_hook_result,
        expected_condition="exact_hook",
        expected_capsule_sha256=expected_capsule_sha256,
        expected_arm_packet_sha256=expected_arm_packet_sha256,
    )
    for field in (
        "schema_version",
        "host_version",
        "capture_track",
        "capsule_sha256",
        "arm_packet_sha256",
        "capture_id",
        "checkpoint_seq",
        "probe",
        "rng_control",
    ):
        if control[field] != exact[field]:
            raise RngTrialResultError(f"paired result {field} mismatch")
    for boundary in ("runtime_before", "runtime_after"):
        if _runtime_identity(control[boundary]) != _runtime_identity(exact[boundary]):
            raise RngTrialResultError(f"paired {boundary} identity mismatch")
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "kind": COMPARISON_KIND,
        "status": "matched",
        "capture_track": control["capture_track"],
        "capture_id": control["capture_id"],
        "checkpoint_seq": control["checkpoint_seq"],
        "capsule_sha256": control["capsule_sha256"],
        "arm_packet_sha256": control["arm_packet_sha256"],
        "control_result_sha256": result_sha256(control),
        "exact_hook_result_sha256": result_sha256(exact),
        "probe": _copy(control["probe"]),
        "rng_control": _copy(control["rng_control"]),
        "runtime_identity": _runtime_identity(control["runtime_before"]),
        "timing": {
            "control_duration_seconds": (
                control["runtime_after"]["now_epoch"]
                - control["runtime_before"]["now_epoch"]
            ),
            "exact_hook_duration_seconds": (
                exact["runtime_after"]["now_epoch"]
                - exact["runtime_before"]["now_epoch"]
            ),
        },
    }
