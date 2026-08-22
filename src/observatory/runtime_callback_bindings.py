"""Strict validation for inert runtime callback-slot manifests."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from src.observatory.runtime_callback_manifest import (
    METHOD_ORDER,
    validate_runtime_callback_manifest,
)


BINDING_SCHEMA_VERSION = 1
BINDING_RUNTIME_VERSION = "observatory-callback-bindings/1"
MAX_SLOTS = 512
_SLOT_RE = re.compile(r"^slot-[0-9]{4}$")
_ROOT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FUNCTION_RE = re.compile(r"^fn-[0-9]{4}$")


class RuntimeCallbackBindingError(RuntimeError):
    """Raised when an untrusted callback-slot manifest is malformed."""


def _exact(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeCallbackBindingError(f"{label} must be an object")
    missing = fields - set(value)
    unknown = set(value) - fields
    if missing or unknown:
        raise RuntimeCallbackBindingError(
            f"{label} fields mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
    return value


def _integer(value: Any, label: str, *, maximum: int | None = None) -> int:
    if type(value) is not int or value < 0:
        raise RuntimeCallbackBindingError(f"{label} must be a nonnegative integer")
    if maximum is not None and value > maximum:
        raise RuntimeCallbackBindingError(f"{label} exceeds its cap")
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
        raise RuntimeCallbackBindingError(f"manifest is not canonical JSON: {exc}") from exc


def callback_binding_manifest_sha256(value: Mapping[str, Any]) -> str:
    validated = validate_runtime_callback_bindings(value)
    encoded = json.dumps(
        validated,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256((encoded + "\n").encode("utf-8")).hexdigest()


def validate_runtime_callback_bindings(value: Any) -> dict[str, Any]:
    """Validate a slot manifest and its complete nested identity manifest."""
    manifest = _exact(
        value,
        frozenset(
            {
                "schema_version",
                "runtime_version",
                "method_order",
                "identity_manifest",
                "roots",
                "slots",
                "summary",
            }
        ),
        "binding manifest",
    )
    if manifest["schema_version"] != BINDING_SCHEMA_VERSION:
        raise RuntimeCallbackBindingError("unsupported binding schema")
    if manifest["runtime_version"] != BINDING_RUNTIME_VERSION:
        raise RuntimeCallbackBindingError("unsupported binding runtime")
    if manifest["method_order"] != list(METHOD_ORDER):
        raise RuntimeCallbackBindingError("binding method order mismatch")
    identity = validate_runtime_callback_manifest(manifest["identity_manifest"])
    roots = manifest["roots"]
    slots = manifest["slots"]
    if not isinstance(roots, list) or len(roots) != len(identity["roots"]):
        raise RuntimeCallbackBindingError("binding roots do not cover identity roots")
    if not isinstance(slots, list) or not 1 <= len(slots) <= MAX_SLOTS:
        raise RuntimeCallbackBindingError("binding slots violate their cap")

    slot_by_id: dict[str, dict[str, Any]] = {}
    slot_roots: dict[str, list[str]] = {}
    for index, raw_slot in enumerate(slots, start=1):
        slot = _exact(
            raw_slot,
            frozenset({"slot_id", "method", "function_id", "root_ids"}),
            f"slots[{index - 1}]",
        )
        expected_id = f"slot-{index:04d}"
        if slot["slot_id"] != expected_id or _SLOT_RE.fullmatch(expected_id) is None:
            raise RuntimeCallbackBindingError("binding slot IDs are not contiguous")
        if slot["method"] not in METHOD_ORDER:
            raise RuntimeCallbackBindingError("binding slot method is invalid")
        if type(slot["function_id"]) is not str or _FUNCTION_RE.fullmatch(
            slot["function_id"]
        ) is None:
            raise RuntimeCallbackBindingError("binding slot function_id is invalid")
        root_ids = slot["root_ids"]
        if (
            not isinstance(root_ids, list)
            or not root_ids
            or root_ids != sorted(root_ids)
            or len(root_ids) != len(set(root_ids))
            or any(type(root) is not str or _ROOT_RE.fullmatch(root) is None for root in root_ids)
        ):
            raise RuntimeCallbackBindingError("binding slot root_ids are invalid")
        copied_slot = _copy(slot)
        slot_by_id[expected_id] = copied_slot
        slot_roots[expected_id] = []

    copied_roots: list[dict[str, Any]] = []
    previous_root = ""
    for root_index, (raw_root, identity_root) in enumerate(
        zip(roots, identity["roots"], strict=True)
    ):
        root = _exact(
            raw_root,
            frozenset({"root_id", "methods"}),
            f"roots[{root_index}]",
        )
        root_id = root["root_id"]
        if (
            type(root_id) is not str
            or _ROOT_RE.fullmatch(root_id) is None
            or root_id <= previous_root
            or root_id != identity_root["root_id"]
        ):
            raise RuntimeCallbackBindingError("binding root identity/order mismatch")
        previous_root = root_id
        methods = root["methods"]
        if not isinstance(methods, list) or len(methods) != len(METHOD_ORDER):
            raise RuntimeCallbackBindingError("binding root methods are incomplete")
        copied_methods: list[dict[str, Any]] = []
        for method_index, (raw_method, identity_method) in enumerate(
            zip(methods, identity_root["methods"], strict=True)
        ):
            method = _exact(
                raw_method,
                frozenset(
                    {
                        "method",
                        "status",
                        "resolution_depth",
                        "function_id",
                        "slot_id",
                    }
                ),
                f"roots[{root_index}].methods[{method_index}]",
            )
            for field in ("method", "status", "resolution_depth", "function_id"):
                if method[field] != identity_method[field]:
                    raise RuntimeCallbackBindingError(
                        f"binding method {field} disagrees with identity manifest"
                    )
            function_id = method["function_id"]
            slot_id = method["slot_id"]
            if function_id:
                if type(slot_id) is not str or slot_id not in slot_by_id:
                    raise RuntimeCallbackBindingError("resolved method lacks a known slot")
                slot = slot_by_id[slot_id]
                if slot["method"] != method["method"] or slot["function_id"] != function_id:
                    raise RuntimeCallbackBindingError("method-to-slot identity mismatch")
                slot_roots[slot_id].append(root_id)
            elif slot_id != "":
                raise RuntimeCallbackBindingError("unresolved method names a slot")
            copied_methods.append(_copy(method))
        copied_roots.append({"root_id": root_id, "methods": copied_methods})

    for slot_id, observed_roots in slot_roots.items():
        if observed_roots != slot_by_id[slot_id]["root_ids"]:
            raise RuntimeCallbackBindingError("slot root coverage mismatch")

    summary = _exact(
        manifest["summary"],
        frozenset({"root_count", "method_count", "function_count", "slot_count"}),
        "binding summary",
    )
    expected_summary = {
        "root_count": len(copied_roots),
        "method_count": len(copied_roots) * len(METHOD_ORDER),
        "function_count": identity["summary"]["function_count"],
        "slot_count": len(slots),
    }
    for field, expected in expected_summary.items():
        _integer(summary[field], f"binding summary.{field}", maximum=100_000)
        if summary[field] != expected:
            raise RuntimeCallbackBindingError(f"binding summary {field} mismatch")

    return {
        "schema_version": BINDING_SCHEMA_VERSION,
        "runtime_version": BINDING_RUNTIME_VERSION,
        "method_order": list(METHOD_ORDER),
        "identity_manifest": identity,
        "roots": copied_roots,
        "slots": [slot_by_id[f"slot-{index:04d}"] for index in range(1, len(slots) + 1)],
        "summary": expected_summary,
    }
