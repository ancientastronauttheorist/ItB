"""Fail-closed contracts for paired disposable Observatory trials.

This module is deliberately offline-only.  It records the evidence required to
compare an unhooked control run with a run using one exact reviewed hook; it
does not launch a game, install a hook, or inspect a live process.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


MATCHED_TRIAL_SCHEMA_VERSION = 1
SUITE_KIND = "observatory_matched_trial_suite"
RECEIPT_KIND = "observatory_matched_trial_receipt"
COMPARISON_KIND = "observatory_matched_trial_comparison"
MAX_CONTRACT_BYTES = 1024 * 1024

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SUITE_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "suite_id",
        "pair_nonce",
        "artifact_hashes",
        "scenario_sha256",
        "start_state_sha256",
        "restore_expected_sha256",
    }
)
_ARTIFACT_HASH_FIELDS = frozenset(
    {
        "build_identity_sha256",
        "inventory_sha256",
        "controller_sha256",
        "helper_sha256",
        "hook_sha256",
    }
)
_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "suite",
        "condition",
        "receipt_nonce",
        "preflight",
        "completion",
        "restore",
        "post_bytes",
        "output",
    }
)
_PREFLIGHT_FIELDS = frozenset(
    {
        "ready",
        "build_identity_sha256",
        "inventory_sha256",
        "start_state_sha256",
    }
)
_COMPLETION_FIELDS = frozenset({"scenario_complete", "receipt_complete"})
_RESTORE_FIELDS = frozenset({"attempted", "succeeded", "restored_sha256"})
_POST_BYTES_FIELDS = frozenset({"verified", "sha256"})
_OUTPUT_FIELDS = frozenset(
    {"outcome", "seed", "queue", "spawn", "crash", "counters", "timing"}
)
_CRASH_FIELDS = frozenset({"observed", "signature_sha256"})
_COUNTER_FIELDS = frozenset(
    {"mission_ticks", "enemy_decisions", "queued_actions", "spawn_events"}
)
_TIMING_FIELDS = frozenset({"wall_duration_ms", "max_tick_ms", "total_ticks"})
_OUTCOMES = frozenset({"completed", "aborted", "failed"})
_CONDITIONS = frozenset({"control", "exact_hook"})


class MatchedTrialError(RuntimeError):
    """Raised when a matched-trial contract is malformed or unsafe to compare."""


class _DuplicateKeyError(ValueError):
    pass


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise MatchedTrialError(f"contract is not canonical JSON: {exc}") from exc


def _copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def contract_sha256(value: Mapping[str, Any]) -> str:
    """Return the canonical content digest for one validated JSON contract."""
    return hashlib.sha256((_canonical_json(value) + "\n").encode("utf-8")).hexdigest()


def _exact_fields(value: Any, expected: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MatchedTrialError(f"{label} must be an object")
    missing = expected - set(value)
    unknown = set(value) - expected
    if missing:
        raise MatchedTrialError(f"{label} missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise MatchedTrialError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    return value


def _sha256(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise MatchedTrialError(f"{label} must be lowercase SHA-256")
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or not _IDENTIFIER_RE.fullmatch(value):
        raise MatchedTrialError(f"{label} must be a lowercase identifier")
    return value


def _nonnegative_integer(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise MatchedTrialError(f"{label} must be an integer >= 0")
    return value


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise MatchedTrialError(f"{label} must be boolean")
    return value


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


def validate_suite_contract(value: Any) -> dict[str, Any]:
    """Validate and canonicalize the shared immutable matched-trial contract."""
    suite = _exact_fields(value, _SUITE_FIELDS, "suite")
    if suite["schema_version"] != MATCHED_TRIAL_SCHEMA_VERSION:
        raise MatchedTrialError("unsupported matched-trial suite schema")
    if suite["kind"] != SUITE_KIND:
        raise MatchedTrialError("invalid matched-trial suite kind")
    _identifier(suite["suite_id"], "suite.suite_id")
    _sha256(suite["pair_nonce"], "suite.pair_nonce")
    artifact_hashes = _exact_fields(
        suite["artifact_hashes"], _ARTIFACT_HASH_FIELDS, "suite.artifact_hashes"
    )
    for field in sorted(_ARTIFACT_HASH_FIELDS):
        _sha256(artifact_hashes[field], f"suite.artifact_hashes.{field}")
    for field in (
        "scenario_sha256",
        "start_state_sha256",
        "restore_expected_sha256",
    ):
        _sha256(suite[field], f"suite.{field}")
    return _copy(suite)


def _validate_preflight(value: Any, suite: Mapping[str, Any]) -> dict[str, Any]:
    preflight = _exact_fields(value, _PREFLIGHT_FIELDS, "receipt.preflight")
    _boolean(preflight["ready"], "receipt.preflight.ready")
    expected = suite["artifact_hashes"]
    for field in ("build_identity_sha256", "inventory_sha256"):
        if preflight[field] != expected[field]:
            raise MatchedTrialError(f"receipt.preflight.{field} mismatch")
    if preflight["start_state_sha256"] != suite["start_state_sha256"]:
        raise MatchedTrialError("receipt.preflight.start_state_sha256 mismatch")
    return _copy(preflight)


def _validate_output(value: Any) -> dict[str, Any]:
    output = _exact_fields(value, _OUTPUT_FIELDS, "receipt.output")
    if type(output["outcome"]) is not str or output["outcome"] not in _OUTCOMES:
        raise MatchedTrialError("receipt.output.outcome is invalid")
    for field in ("seed", "queue", "spawn"):
        _sha256(output[field], f"receipt.output.{field}")
    crash = _exact_fields(output["crash"], _CRASH_FIELDS, "receipt.output.crash")
    observed = _boolean(crash["observed"], "receipt.output.crash.observed")
    signature = _sha256(
        crash["signature_sha256"], "receipt.output.crash.signature_sha256", nullable=True
    )
    if observed != (signature is not None):
        raise MatchedTrialError("receipt.output.crash signature does not match observed")
    counters = _exact_fields(output["counters"], _COUNTER_FIELDS, "receipt.output.counters")
    timing = _exact_fields(output["timing"], _TIMING_FIELDS, "receipt.output.timing")
    for field in sorted(_COUNTER_FIELDS):
        _nonnegative_integer(counters[field], f"receipt.output.counters.{field}")
    for field in sorted(_TIMING_FIELDS):
        _nonnegative_integer(timing[field], f"receipt.output.timing.{field}")
    return _copy(output)


def validate_trial_receipt(
    value: Any,
    *,
    expected_suite: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one sealed control or exact-hook receipt without comparison."""
    receipt = _exact_fields(value, _RECEIPT_FIELDS, "receipt")
    if receipt["schema_version"] != MATCHED_TRIAL_SCHEMA_VERSION:
        raise MatchedTrialError("unsupported matched-trial receipt schema")
    if receipt["kind"] != RECEIPT_KIND:
        raise MatchedTrialError("invalid matched-trial receipt kind")
    suite = validate_suite_contract(receipt["suite"])
    if expected_suite is not None and not _type_safe_equal(
        suite, validate_suite_contract(expected_suite)
    ):
        raise MatchedTrialError("receipt suite does not match the expected suite")
    if receipt["condition"] not in _CONDITIONS:
        raise MatchedTrialError("receipt condition must be control or exact_hook")
    _sha256(receipt["receipt_nonce"], "receipt.receipt_nonce")
    _validate_preflight(receipt["preflight"], suite)
    completion = _exact_fields(receipt["completion"], _COMPLETION_FIELDS, "receipt.completion")
    for field in sorted(_COMPLETION_FIELDS):
        _boolean(completion[field], f"receipt.completion.{field}")
    restore = _exact_fields(receipt["restore"], _RESTORE_FIELDS, "receipt.restore")
    _boolean(restore["attempted"], "receipt.restore.attempted")
    _boolean(restore["succeeded"], "receipt.restore.succeeded")
    if restore["restored_sha256"] != suite["restore_expected_sha256"]:
        raise MatchedTrialError("receipt.restore.restored_sha256 mismatch")
    post_bytes = _exact_fields(receipt["post_bytes"], _POST_BYTES_FIELDS, "receipt.post_bytes")
    _boolean(post_bytes["verified"], "receipt.post_bytes.verified")
    if post_bytes["sha256"] != suite["restore_expected_sha256"]:
        raise MatchedTrialError("receipt.post_bytes.sha256 mismatch")
    _validate_output(receipt["output"])
    return _copy(receipt)


def _require_complete(receipt: Mapping[str, Any], label: str) -> None:
    if not receipt["preflight"]["ready"]:
        raise MatchedTrialError(f"{label} receipt failed preflight")
    if not all(receipt["completion"].values()):
        raise MatchedTrialError(f"{label} receipt is torn or incomplete")
    if not receipt["restore"]["attempted"] or not receipt["restore"]["succeeded"]:
        raise MatchedTrialError(f"{label} receipt reports restore failure")
    if not receipt["post_bytes"]["verified"]:
        raise MatchedTrialError(f"{label} receipt lacks post-byte verification")
    output = receipt["output"]
    if output["outcome"] != "completed":
        raise MatchedTrialError(f"{label} receipt did not complete")
    if output["crash"]["observed"]:
        raise MatchedTrialError(f"{label} receipt reports a crash")


def _semantic_output(output: Mapping[str, Any]) -> dict[str, Any]:
    semantic = {
        field: _copy(output[field])
        for field in ("outcome", "seed", "queue", "spawn", "crash", "counters")
    }
    # Durations are observational, but a different number of ticks is semantic
    # drift even though the field travels in the timing envelope.
    semantic["total_ticks"] = output["timing"]["total_ticks"]
    return semantic


def compare_matched_receipts(
    control_receipt: Mapping[str, Any],
    exact_hook_receipt: Mapping[str, Any],
    *,
    expected_suite: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed unless a control/exact-hook pair has identical semantics.

    Only the condition, per-receipt nonce, and output envelope may differ.  The
    output's duration measurements are reported separately. Tick count and all
    non-timing output fields are semantic evidence and must match exactly.
    """
    control = validate_trial_receipt(control_receipt, expected_suite=expected_suite)
    exact_hook = validate_trial_receipt(exact_hook_receipt, expected_suite=expected_suite)
    if control["condition"] != "control":
        raise MatchedTrialError("first receipt must be the control condition")
    if exact_hook["condition"] != "exact_hook":
        raise MatchedTrialError("second receipt must be the exact_hook condition")
    if control["receipt_nonce"] == exact_hook["receipt_nonce"]:
        raise MatchedTrialError("paired receipts must use distinct receipt nonces")
    _require_complete(control, "control")
    _require_complete(exact_hook, "exact_hook")

    def static_portion(receipt: Mapping[str, Any]) -> dict[str, Any]:
        return {
            field: _copy(receipt[field])
            for field in receipt
            if field not in {"condition", "receipt_nonce", "output"}
        }

    if not _type_safe_equal(static_portion(control), static_portion(exact_hook)):
        raise MatchedTrialError("paired receipts drift outside condition, nonce, or output")
    control_semantic = _semantic_output(control["output"])
    hook_semantic = _semantic_output(exact_hook["output"])
    if not _type_safe_equal(control_semantic, hook_semantic):
        raise MatchedTrialError("paired receipts have semantic output drift")
    control_timing = control["output"]["timing"]
    hook_timing = exact_hook["output"]["timing"]
    return {
        "schema_version": MATCHED_TRIAL_SCHEMA_VERSION,
        "kind": COMPARISON_KIND,
        "status": "matched",
        "suite_id": control["suite"]["suite_id"],
        "pair_nonce": control["suite"]["pair_nonce"],
        "control_receipt_sha256": contract_sha256(control),
        "exact_hook_receipt_sha256": contract_sha256(exact_hook),
        "semantic_output": control_semantic,
        "timing": {
            "control": _copy(control_timing),
            "exact_hook": _copy(hook_timing),
            "wall_duration_delta_ms": (
                hook_timing["wall_duration_ms"] - control_timing["wall_duration_ms"]
            ),
            "max_tick_delta_ms": hook_timing["max_tick_ms"] - control_timing["max_tick_ms"],
        },
    }


def load_json_contract(path: Path, label: str) -> dict[str, Any]:
    """Read one small stable contract without following symlinks."""
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise MatchedTrialError(f"{label} must be a regular file")
    before = candidate.stat()
    if before.st_size > MAX_CONTRACT_BYTES:
        raise MatchedTrialError(f"{label} exceeds the contract byte limit")
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise MatchedTrialError(f"cannot read {label}: {exc}") from exc
    after = candidate.stat()
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise MatchedTrialError(f"{label} changed while being read")
    if len(raw) > MAX_CONTRACT_BYTES:
        raise MatchedTrialError(f"{label} exceeds the contract byte limit")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError, _DuplicateKeyError) as exc:
        raise MatchedTrialError(f"invalid {label} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise MatchedTrialError(f"{label} must be a JSON object")
    return value
