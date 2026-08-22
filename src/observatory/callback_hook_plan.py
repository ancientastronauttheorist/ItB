"""Build exact one-family hook plans from runtime callback-slot evidence."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from src.observatory.runtime_callback_bindings import (
    callback_binding_manifest_sha256,
    validate_runtime_callback_bindings,
)
from src.observatory.trace_codec import EVENT_KINDS, validate_hook_coverage


CALLBACK_CONTROLLER_VERSION = "observatory-callback-controller/1"
METHOD_TO_KIND = {
    "GetTargetArea": "get_target_area",
    "GetTargetScore": "enemy_target_score",
    "GetSkillEffect": "get_skill_effect",
    "ScorePositioning": "score_positioning",
}
KIND_TO_METHOD = {kind: method for method, kind in METHOD_TO_KIND.items()}
CALLBACK_KINDS = frozenset(KIND_TO_METHOD)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_JOIN_FIELDS = frozenset(
    {
        "schema_version",
        "analysis_kind",
        "build_identity",
        "runtime_manifest",
        "function_joins",
        "summary",
    }
)
_FUNCTION_JOIN_FIELDS = frozenset(
    {"function_id", "join_status", "source_path", "source_sha256", "matches"}
)


class CallbackHookPlanError(RuntimeError):
    """Raised when callback evidence cannot form an exact hook plan."""


def _exact(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CallbackHookPlanError(f"{label} must be an object")
    missing = fields - set(value)
    unknown = set(value) - fields
    if missing or unknown:
        raise CallbackHookPlanError(
            f"{label} fields mismatch; missing={sorted(missing)}, "
            f"unknown={sorted(unknown)}"
        )
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
        raise CallbackHookPlanError(f"value is not strict JSON: {exc}") from exc


def _type_safe_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(
            _type_safe_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _type_safe_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def _source_hashes(
    manifest: Mapping[str, Any], runtime_join: Any
) -> tuple[dict[str, str], dict[str, Any]]:
    join = _exact(runtime_join, _JOIN_FIELDS, "runtime callback join")
    if (
        join["schema_version"] != 1
        or join["analysis_kind"] != "runtime_callback_identity_join"
        or not _type_safe_equal(join["runtime_manifest"], manifest["identity_manifest"])
    ):
        raise CallbackHookPlanError(
            "runtime callback join does not bind the slot identity manifest"
        )
    raw_joins = join["function_joins"]
    if not isinstance(raw_joins, list):
        raise CallbackHookPlanError("runtime callback function_joins must be an array")
    expected_ids = {
        function["function_id"]
        for function in manifest["identity_manifest"]["functions"]
    }
    source_hashes: dict[str, str] = {}
    for index, raw in enumerate(raw_joins):
        item = _exact(raw, _FUNCTION_JOIN_FIELDS, f"function_joins[{index}]")
        function_id = item["function_id"]
        digest = item["source_sha256"]
        matches = item["matches"]
        exact_match = matches[0] if isinstance(matches, list) and len(matches) == 1 else None
        if (
            type(function_id) is not str
            or function_id in source_hashes
            or function_id not in expected_ids
            or item["join_status"] != "matched"
            or type(item["source_path"]) is not str
            or not item["source_path"]
            or type(digest) is not str
            or _SHA256_RE.fullmatch(digest) is None
            or not isinstance(exact_match, Mapping)
            or exact_match.get("source_path") != item["source_path"]
            or exact_match.get("source_sha256") != digest
        ):
            raise CallbackHookPlanError(
                "every callback slot function requires one exact source join"
            )
        source_hashes[function_id] = digest
    if set(source_hashes) != expected_ids:
        raise CallbackHookPlanError("runtime callback join has incomplete coverage")
    return source_hashes, _copy(join["build_identity"])


def _slot_target(slot: Mapping[str, Any]) -> str:
    return (
        f"runtime.callback.{slot['slot_id']}."
        f"{slot['method']}.{slot['function_id']}"
    )


def _slot_target_kind(slot: Mapping[str, Any]) -> str:
    if slot["method"] == "ScorePositioning" and slot["root_ids"] == [
        "global.ScorePositioning"
    ]:
        return "lua_global"
    return "lua_method"


def build_callback_hook_plan(
    binding_manifest: Any,
    runtime_join: Any,
    *,
    installed_kind: str,
    disabled_source_sha256: str | None = None,
) -> list[dict[str, Any]]:
    """Return complete canonical coverage with exactly one callback family armed.

    All 65 resolved slots remain explicit. Shared inherited functions therefore
    appear once at their actual defining table, while every slot outside the
    selected method family is present with ``disabled`` status.
    """
    manifest = validate_runtime_callback_bindings(binding_manifest)
    if installed_kind not in CALLBACK_KINDS:
        raise CallbackHookPlanError("installed_kind is not a callback family")
    source_hashes, _ = _source_hashes(manifest, runtime_join)
    disabled_digest = disabled_source_sha256 or callback_binding_manifest_sha256(
        manifest
    )
    if (
        type(disabled_digest) is not str
        or _SHA256_RE.fullmatch(disabled_digest) is None
    ):
        raise CallbackHookPlanError("disabled_source_sha256 must be lowercase SHA-256")

    plan: list[dict[str, Any]] = []
    covered_kinds: set[str] = set()
    for slot in manifest["slots"]:
        event_kind = METHOD_TO_KIND[slot["method"]]
        covered_kinds.add(event_kind)
        plan.append(
            {
                "hook_id": f"callback.{slot['slot_id']}",
                "event_kind": event_kind,
                "target": _slot_target(slot),
                "target_kind": _slot_target_kind(slot),
                "status": "installed" if event_kind == installed_kind else "disabled",
                "source_sha256": source_hashes[slot["function_id"]],
            }
        )

    for kind in sorted(EVENT_KINDS - covered_kinds):
        target_kind = "lua_global" if kind in {"random_int", "random_bool"} else (
            "native_boundary"
        )
        plan.append(
            {
                "hook_id": f"disabled.{kind}",
                "event_kind": kind,
                "target": f"disabled.{kind}",
                "target_kind": target_kind,
                "status": "disabled",
                "source_sha256": disabled_digest,
            }
        )
    plan.sort(key=lambda item: (item["event_kind"], item["target"]))
    try:
        validate_hook_coverage(
            [{key: value for key, value in item.items() if key != "hook_id"} for item in plan]
        )
    except Exception as exc:
        raise CallbackHookPlanError(f"generated callback hook plan is invalid: {exc}") from exc
    return _copy(plan)


def validate_callback_hook_plan(
    plan: Any,
    binding_manifest: Any,
    runtime_join: Any,
    *,
    installed_kind: str,
    disabled_source_sha256: str | None = None,
) -> list[dict[str, Any]]:
    if isinstance(plan, (str, bytes)) or not isinstance(plan, Sequence):
        raise CallbackHookPlanError("callback hook plan must be an array")
    expected = build_callback_hook_plan(
        binding_manifest,
        runtime_join,
        installed_kind=installed_kind,
        disabled_source_sha256=disabled_source_sha256,
    )
    supplied = _copy(list(plan))
    if not _type_safe_equal(supplied, expected):
        raise CallbackHookPlanError(
            "callback hook plan does not exactly match the bound slot evidence"
        )
    return expected
