"""Exact semantic comparison for post-trial ITB bridge states."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any


OUTCOME_SCHEMA_VERSION = 1
OUTCOME_KIND = "observatory_rng_trial_outcome_comparison"
IGNORED_TOP_LEVEL_FIELDS = frozenset({"timestamp"})
MAX_DIFFERENCES = 128

_CAPTURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


class RngTrialOutcomeError(RuntimeError):
    """Raised when a post-trial bridge state is malformed or unbounded."""


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
        raise RngTrialOutcomeError(f"bridge state is not canonical JSON: {exc}") from exc


def _canonical_bytes(value: Any) -> bytes:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (encoded + "\n").encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _validated_state(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RngTrialOutcomeError(f"{label} must be an object")
    state = _copy(value)
    required = {
        "timestamp": int,
        "mission_id": str,
        "phase": str,
        "turn": int,
        "grid_power": int,
        "units": list,
        "tiles": list,
        "spawning_tiles": list,
    }
    for field, expected_type in required.items():
        current = state.get(field)
        if type(current) is not expected_type:
            raise RngTrialOutcomeError(
                f"{label}.{field} must be {expected_type.__name__}"
            )
    if not state["mission_id"] or state["turn"] < 0 or state["timestamp"] < 0:
        raise RngTrialOutcomeError(f"{label} has an invalid mission identity")
    if state["phase"] not in {"combat_player", "combat_enemy"}:
        raise RngTrialOutcomeError(f"{label}.phase is invalid")
    return state


def _semantic_state(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: _copy(value)
        for key, value in state.items()
        if key not in IGNORED_TOP_LEVEL_FIELDS
    }


def _bounded_value(value: Any) -> Any:
    if value is None or type(value) in {bool, int, float}:
        return value
    if isinstance(value, str):
        return value if len(value) <= 256 else value[:253] + "..."
    if isinstance(value, list):
        return {"type": "array", "length": len(value)}
    if isinstance(value, dict):
        return {"type": "object", "field_count": len(value)}
    return {"type": type(value).__name__}


def _differences(
    control: Any,
    exact: Any,
    path: str = "",
) -> tuple[list[dict[str, Any]], bool]:
    found: list[dict[str, Any]] = []
    truncated = False

    def add(kind: str, current_path: str, left: Any, right: Any) -> None:
        nonlocal truncated
        if len(found) >= MAX_DIFFERENCES:
            truncated = True
            return
        found.append(
            {
                "path": current_path or "/",
                "kind": kind,
                "control": _bounded_value(left),
                "exact_hook": _bounded_value(right),
            }
        )

    def walk(left: Any, right: Any, current_path: str) -> None:
        if truncated:
            return
        if type(left) is not type(right):
            add("type", current_path, left, right)
            return
        if isinstance(left, dict):
            for key in sorted(set(left) | set(right)):
                child_path = f"{current_path}/{key}"
                if key not in left:
                    add("missing_control", child_path, None, right[key])
                elif key not in right:
                    add("missing_exact_hook", child_path, left[key], None)
                else:
                    walk(left[key], right[key], child_path)
            return
        if isinstance(left, list):
            if len(left) != len(right):
                add("length", current_path, left, right)
            for index, (left_child, right_child) in enumerate(zip(left, right)):
                walk(left_child, right_child, f"{current_path}/{index}")
            return
        if left != right:
            add("value", current_path, left, right)

    walk(control, exact, path)
    return found, truncated


def compare_rng_trial_outcomes(
    control_state: Mapping[str, Any],
    exact_hook_state: Mapping[str, Any],
    *,
    capture_id: str,
) -> dict[str, Any]:
    """Compare every bridge field except the explicitly non-semantic timestamp."""
    if type(capture_id) is not str or _CAPTURE_ID_RE.fullmatch(capture_id) is None:
        raise RngTrialOutcomeError("capture_id is invalid")
    control = _validated_state(control_state, "control_state")
    exact = _validated_state(exact_hook_state, "exact_hook_state")
    control_semantic = _semantic_state(control)
    exact_semantic = _semantic_state(exact)
    differences, truncated = _differences(control_semantic, exact_semantic)
    return {
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "kind": OUTCOME_KIND,
        "status": "matched" if not differences else "mismatched",
        "capture_id": capture_id,
        "ignored_top_level_fields": sorted(IGNORED_TOP_LEVEL_FIELDS),
        "control_state_sha256": _sha256(control),
        "exact_hook_state_sha256": _sha256(exact),
        "control_semantic_sha256": _sha256(control_semantic),
        "exact_hook_semantic_sha256": _sha256(exact_semantic),
        "difference_count": len(differences),
        "differences_truncated": truncated,
        "differences": differences,
    }
