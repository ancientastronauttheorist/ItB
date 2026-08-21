"""Strict validation and lexical joins for runtime callback identities."""

from __future__ import annotations

from copy import deepcopy

import pytest

from src.observatory.runtime_callback_manifest import (
    JOIN_STATUSES,
    METHOD_ORDER,
    STATUSES,
    RuntimeCallbackManifestError,
    join_runtime_callback_manifest,
    validate_runtime_callback_manifest,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64


def _function(
    index: int,
    *,
    source: str = "@scripts/global.lua",
    line: int = 10,
    what: str = "Lua",
    debug_status: str = "available",
    source_truncated: bool = False,
) -> dict:
    if debug_status == "unavailable":
        source = ""
        line = -1
        what = ""
    return {
        "function_id": f"fn-{index:04d}",
        "debug_status": debug_status,
        "source": source,
        "source_truncated": source_truncated,
        "short_src": source[1:] if source.startswith("@") else source,
        "short_src_truncated": False,
        "linedefined": line,
        "lastlinedefined": line + 2 if line >= 0 else -1,
        "what": what,
        "what_truncated": False,
        "name": "",
        "name_truncated": False,
        "namewhat": "",
        "namewhat_truncated": False,
    }


def _method(
    method: str,
    status: str,
    function_id: str = "",
    *,
    depth: int = 0,
    expected_function_id: str = "",
    replaced: bool = False,
    expected_truncated: bool = False,
) -> dict:
    return {
        "method": method,
        "status": status,
        "replaced": replaced,
        "resolution_depth": depth,
        "function_id": function_id,
        "expected_function_id": expected_function_id,
        "expected_truncated": expected_truncated,
    }


def _manifest() -> dict:
    functions = [
        _function(1, line=10),
        _function(2, source="=[C]", line=-1, what="C"),
        _function(3, debug_status="unavailable"),
        _function(4, source="@scripts/global.lua", line=30, source_truncated=True),
        _function(5, source="@scripts/not_in_inventory.lua", line=5),
        _function(6, source='=[string "generated"]', line=4),
        _function(7, source="@scripts/global.lua", line=0),
        _function(8, source="@scripts/global.lua", line=20),
    ]
    roots = [
        {
            "root_id": "enemy.1.skill.1",
            "methods": [
                _method(METHOD_ORDER[0], "resolved", "fn-0001"),
                _method(METHOD_ORDER[1], "c_function", "fn-0002"),
                _method(METHOD_ORDER[2], "debug_unavailable", "fn-0003"),
                _method(METHOD_ORDER[3], "resolved", "fn-0004"),
            ],
        },
        {
            "root_id": "enemy.2.skill.1",
            "methods": [
                _method(METHOD_ORDER[0], "resolved", "fn-0005"),
                _method(METHOD_ORDER[1], "resolved", "fn-0006"),
                _method(METHOD_ORDER[2], "resolved", "fn-0007"),
                _method(METHOD_ORDER[3], "missing"),
            ],
        },
        {
            "root_id": "enemy.3.skill.1",
            "methods": [
                _method(METHOD_ORDER[0], "resolved", "fn-0008"),
                _method(METHOD_ORDER[1], "missing"),
                _method(METHOD_ORDER[2], "missing"),
                _method(METHOD_ORDER[3], "missing"),
            ],
        },
    ]
    counts = {status: 0 for status in sorted(STATUSES)}
    for root in roots:
        for method in root["methods"]:
            counts[method["status"]] += 1
    return {
        "schema_version": 1,
        "runtime_version": "observatory-callback-manifest/1",
        "method_order": list(METHOD_ORDER),
        "limits": {
            "max_roots": 16,
            "max_depth": 8,
            "max_functions": 32,
            "max_text_bytes": 512,
        },
        "roots": roots,
        "functions": functions,
        "summary": {
            "root_count": len(roots),
            "method_count": len(roots) * len(METHOD_ORDER),
            "function_count": len(functions),
            "replaced_count": 0,
            "status_counts": counts,
        },
    }


def _identity() -> dict:
    return {
        "platform": "windows",
        "architecture": "x86",
        "executable_sha256": HASH_A,
        "build_id": "13725832",
        "depot_manifest": "8335438558621014449",
        "scripts_revision_sha256": HASH_B,
        "maps_revision_sha256": HASH_C,
    }


def _inventory() -> dict:
    return {
        "platform": "windows",
        "executable": {"architecture": "x86", "sha256": HASH_A},
        "steam": {
            "build_id": "13725832",
            "installed_depots": [
                {
                    "depot_id": "590381",
                    "manifest": "8335438558621014449",
                }
            ],
        },
        "content": {
            "scripts": {
                "revision_sha256": HASH_B,
                "files": [
                    {
                        "path": "scripts/global.lua",
                        "size": 100,
                        "sha256": HASH_D,
                    }
                ],
            },
            "maps": {"revision_sha256": HASH_C},
        },
    }


def _callback(
    symbol: str,
    line: int,
    column: int,
) -> dict:
    return {
        "symbol": symbol,
        "source_path": "scripts/global.lua",
        "source_sha256": HASH_D,
        "line": line,
        "column": column,
        "syntax": "declaration",
        "categories": ["enemy_scoring"],
        "status": "indexed",
        "indexed_by": ["enemy-scoring"],
    }


def _callback_index() -> dict:
    return {
        "schema_version": 1,
        "analysis_kind": "lua_callback_provenance_index",
        "build_identity": _identity(),
        "method": {},
        "files": [],
        "callbacks": [
            _callback("Skill:GetTargetArea", 10, 1),
            _callback("First:GetTargetArea", 20, 1),
            _callback("Second:GetTargetArea", 20, 30),
        ],
        "categories": [],
        "provenance_records": [],
        "summary": {},
    }


def test_validate_manifest_is_strict_reconciled_and_detached():
    original = _manifest()
    validated = validate_runtime_callback_manifest(original)
    assert validated == original
    original["roots"][0]["root_id"] = "mutated"
    assert validated["roots"][0]["root_id"] == "enemy.1.skill.1"


def test_validate_manifest_preserves_exact_lua_symbol_case_in_root_ids():
    manifest = _manifest()
    manifest["roots"][0]["root_id"] = "enemy.skill.ScorpionAtk1_A"
    validated = validate_runtime_callback_manifest(manifest)
    assert validated["roots"][0]["root_id"] == (
        "enemy.skill.ScorpionAtk1_A"
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update({"unknown": True}), "unknown fields"),
        (
            lambda value: value["functions"][1].update({"what": "Lua"}),
            "C status contradicts metadata",
        ),
        (
            lambda value: value["functions"][0].update(
                {"function_id": "fn-9999"}
            ),
            "must be fn-0001",
        ),
        (
            lambda value: value["summary"]["status_counts"].update(
                {"missing": 99}
            ),
            "do not reconcile",
        ),
        (
            lambda value: value["roots"][0]["methods"][0].update(
                {"replaced": True}
            ),
            "without an expected callback",
        ),
    ],
)
def test_validate_manifest_rejects_malformed_or_contradictory_data(
    mutation,
    message,
):
    manifest = _manifest()
    mutation(manifest)
    with pytest.raises(RuntimeCallbackManifestError, match=message):
        validate_runtime_callback_manifest(manifest)


def test_replaced_identity_is_preserved_separately_from_resolution_status():
    manifest = _manifest()
    method = manifest["roots"][0]["methods"][0]
    method["expected_function_id"] = "fn-0002"
    method["replaced"] = True
    manifest["summary"]["replaced_count"] = 1
    validated = validate_runtime_callback_manifest(manifest)
    assert validated["roots"][0]["methods"][0]["status"] == "resolved"
    assert validated["roots"][0]["methods"][0]["replaced"] is True


def test_join_preserves_every_match_and_unresolved_classification():
    result = join_runtime_callback_manifest(
        _manifest(), _callback_index(), _inventory()
    )
    by_id = {entry["function_id"]: entry for entry in result["function_joins"]}
    assert by_id["fn-0001"]["join_status"] == "matched"
    assert by_id["fn-0001"]["matches"][0]["symbol"] == (
        "Skill:GetTargetArea"
    )
    assert by_id["fn-0001"]["source_sha256"] == HASH_D
    assert by_id["fn-0002"]["join_status"] == "c_function"
    assert by_id["fn-0003"]["join_status"] == "debug_unavailable"
    assert by_id["fn-0004"]["join_status"] == "truncated_source"
    assert by_id["fn-0005"]["join_status"] == "unmatched"
    assert by_id["fn-0006"]["join_status"] == "unresolved_source"
    assert by_id["fn-0007"]["join_status"] == "unresolved_line"
    assert by_id["fn-0008"]["join_status"] == "ambiguous"
    assert len(by_id["fn-0008"]["matches"]) == 2
    assert result["summary"]["join_status_counts"] == {
        status: 1 for status in sorted(JOIN_STATUSES)
    }


def test_join_rejects_build_or_inventory_hash_drift():
    callback_index = _callback_index()
    callback_index["build_identity"]["build_id"] = "other"
    with pytest.raises(
        RuntimeCallbackManifestError,
        match="build identity does not match",
    ):
        join_runtime_callback_manifest(
            _manifest(), callback_index, _inventory()
        )

    callback_index = _callback_index()
    callback_index["callbacks"][0]["source_sha256"] = "e" * 64
    with pytest.raises(
        RuntimeCallbackManifestError,
        match="does not match the exact inventory file",
    ):
        join_runtime_callback_manifest(
            _manifest(), callback_index, _inventory()
        )
