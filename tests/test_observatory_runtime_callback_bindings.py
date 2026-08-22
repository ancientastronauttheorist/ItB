from __future__ import annotations

from copy import deepcopy

import pytest

from src.observatory.runtime_callback_bindings import (
    RuntimeCallbackBindingError,
    callback_binding_manifest_sha256,
    validate_runtime_callback_bindings,
)


def _identity_manifest() -> dict:
    status_counts = {
        "resolved": 2,
        "c_function": 0,
        "debug_unavailable": 0,
        "missing": 6,
        "function_index": 0,
        "index_cycle": 0,
        "depth_exceeded": 0,
        "invalid_index": 0,
        "protected_metatable": 0,
        "non_function": 0,
        "function_cap": 0,
    }
    methods = ["GetTargetArea", "GetTargetScore", "GetSkillEffect", "ScorePositioning"]
    roots = []
    for root_id, resolved_method, function_id in (
        ("enemy.skill.Atk", "GetTargetArea", "fn-0001"),
        ("global.ScorePositioning", "ScorePositioning", "fn-0002"),
    ):
        root_methods = []
        for method in methods:
            resolved = method == resolved_method
            root_methods.append(
                {
                    "method": method,
                    "status": "resolved" if resolved else "missing",
                    "replaced": False,
                    "resolution_depth": 0,
                    "function_id": function_id if resolved else "",
                    "expected_function_id": "",
                    "expected_truncated": False,
                }
            )
        roots.append({"root_id": root_id, "methods": root_methods})
    functions = []
    for index in (1, 2):
        functions.append(
            {
                "function_id": f"fn-{index:04d}",
                "debug_status": "available",
                "source": "@scripts/test.lua",
                "source_truncated": False,
                "short_src": "scripts/test.lua",
                "short_src_truncated": False,
                "linedefined": index,
                "lastlinedefined": index,
                "what": "Lua",
                "what_truncated": False,
                "name": "",
                "name_truncated": False,
                "namewhat": "",
                "namewhat_truncated": False,
            }
        )
    return {
        "schema_version": 1,
        "runtime_version": "observatory-callback-manifest/1",
        "method_order": methods,
        "limits": {
            "max_roots": 16,
            "max_depth": 8,
            "max_functions": 32,
            "max_text_bytes": 256,
        },
        "roots": roots,
        "functions": functions,
        "summary": {
            "root_count": 2,
            "method_count": 8,
            "function_count": 2,
            "replaced_count": 0,
            "status_counts": status_counts,
        },
    }


def _binding_manifest() -> dict:
    identity = _identity_manifest()
    roots = []
    slots = [
        {
            "slot_id": "slot-0001",
            "method": "GetTargetArea",
            "function_id": "fn-0001",
            "root_ids": ["enemy.skill.Atk"],
        },
        {
            "slot_id": "slot-0002",
            "method": "ScorePositioning",
            "function_id": "fn-0002",
            "root_ids": ["global.ScorePositioning"],
        },
    ]
    for identity_root in identity["roots"]:
        methods = []
        for identity_method in identity_root["methods"]:
            slot_id = ""
            if identity_method["function_id"] == "fn-0001":
                slot_id = "slot-0001"
            elif identity_method["function_id"] == "fn-0002":
                slot_id = "slot-0002"
            methods.append(
                {
                    "method": identity_method["method"],
                    "status": identity_method["status"],
                    "resolution_depth": identity_method["resolution_depth"],
                    "function_id": identity_method["function_id"],
                    "slot_id": slot_id,
                }
            )
        roots.append({"root_id": identity_root["root_id"], "methods": methods})
    return {
        "schema_version": 1,
        "runtime_version": "observatory-callback-bindings/1",
        "method_order": identity["method_order"],
        "identity_manifest": identity,
        "roots": roots,
        "slots": slots,
        "summary": {
            "root_count": 2,
            "method_count": 8,
            "function_count": 2,
            "slot_count": 2,
        },
    }


def test_binding_manifest_validates_and_hashes_deterministically():
    manifest = _binding_manifest()
    assert validate_runtime_callback_bindings(manifest) == manifest
    assert callback_binding_manifest_sha256(manifest) == callback_binding_manifest_sha256(
        deepcopy(manifest)
    )


def test_binding_manifest_rejects_slot_coverage_drift():
    manifest = _binding_manifest()
    manifest["slots"][0]["root_ids"] = ["global.ScorePositioning"]
    with pytest.raises(RuntimeCallbackBindingError, match="slot root coverage"):
        validate_runtime_callback_bindings(manifest)


def test_binding_manifest_rejects_identity_disagreement():
    manifest = _binding_manifest()
    manifest["roots"][0]["methods"][0]["function_id"] = "fn-0002"
    with pytest.raises(RuntimeCallbackBindingError, match="disagrees"):
        validate_runtime_callback_bindings(manifest)
