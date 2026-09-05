"""Finite reference-to-abstract Lua helper contract projections, without execution."""

from __future__ import annotations
import json
from collections.abc import Mapping
from typing import Any
from src.observatory import native_lua_class_marker_semantics as marker
from src.observatory import native_lua_filtered_assignment_semantics as assignment
from src.observatory import lua51_marker_reference as marker_reference
from src.observatory import lua51_filtered_assignment_reference as assignment_reference
from src.observatory.native_assertion_helper_fill_conformance import (
    _canonical_bytes,
    _canonical_sha256,
    _source_identity,
    _validate_json_tree,
    _assert_publication_safe,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "lua_helper_reference_contracts"
SEALED_SHA256 = "a7c0b4544d1263bf6bcfcf9c2cae613eddd86b1367c1e9fb7d23d2075e545ebf"
SOURCE_PINS = {
    "marker_native": (
        marker.ANALYSIS_KIND,
        "fb30c2feb6bcbc4583ee415585405a130b1219952d23c9aecdf56103158a7c7d",
    ),
    "marker_reference": (
        marker_reference.ANALYSIS_KIND,
        "e6212ef1dc1f91861a894dfafca844607c8e4a2aecf9e95dd4fea8c565ef9a34",
    ),
    "assignment_native": (
        assignment.ANALYSIS_KIND,
        "b62b6409f2f3f3a003732bc106f5e4e3f0eaf543d2b246984a6513cc658a1b27",
    ),
    "assignment_reference": (
        assignment_reference.ANALYSIS_KIND,
        "7d82034b09049dd4eefa96cb02f004dfc15661e8572d4a2267ec4e0473185b35",
    ),
    **marker.SOURCE_PINS,
}


class ContractError(RuntimeError):
    """A sealed source or finite normal-contract comparison differs."""


def _require(ok, message):
    if not ok:
        raise ContractError(message)


def _normalize(fn):
    try:
        return fn()
    except ContractError:
        raise
    except Exception as exc:
        raise ContractError(str(exc)) from exc


def marker_projection(row: list[int]) -> dict[str, Any]:
    _require(
        type(row) is list and len(row) == 10 and all(type(v) is int for v in row),
        "invalid marker row",
    )
    (
        mode,
        value,
        negative,
        status,
        result,
        before,
        after,
        prefix,
        calls,
        protected_top,
    ) = row
    _require(
        0 <= mode < 5 and 0 <= value < 7 and negative in (0, 1),
        "invalid marker reference coordinates",
    )
    _require(status == 0 and mode != 4, "marker row is outside normal contract")
    present = mode != 0
    # Reference value labels map to Lua false values, not Python truthiness.
    truth = value not in (0, 1)
    expected = marker.marker_spec(present, truth)
    _require(
        result == expected["al"]
        and after - before == expected["lua_stack_delta"]
        and prefix == 1
        and expected["lua_stack_prefix_restored"],
        "marker normal projection differs",
    )
    _require(
        before == 3 and after == 3 and protected_top == 1,
        "marker reference wrapper shape differs",
    )
    return {
        "path": expected["path"],
        "reference_result": result,
        "native_contract_al": expected["al"],
        "lua_stack_delta": after - before,
        "prefix_restored": prefix == 1,
        "compared": [
            "Boolean result against AL predicate",
            "Lua stack delta",
            "Entry prefix preservation",
        ],
    }


def assignment_projection(row: list[int]) -> dict[str, Any]:
    _require(
        type(row) is list and len(row) == 12 and all(type(v) is int for v in row),
        "invalid assignment row",
    )
    (
        mode,
        pattern,
        prefix_pair,
        status,
        requests,
        callbacks,
        before,
        after,
        prefix,
        eqcalls,
        destination_match,
        destination_entries,
    ) = row
    _require(
        0 <= mode < 4 and 0 <= pattern < 6 and prefix_pair in (0, 1),
        "invalid assignment reference coordinates",
    )
    _require(status == 0, "assignment row is outside normal contract")
    mask = (0, 1, 2, 4, 7, 255)[pattern]
    inventory = {
        "init": int(bool(mask & 1)),
        "finalize": int(bool(mask & 2)),
        "other": sum(bool(mask & (1 << i)) for i in range(2, 8)),
    }
    # This constructed list computes permutation-invariant counts only. It is
    # never emitted as an observed transcript or used to select a native trace.
    classes = (
        ["init"] * inventory["init"]
        + ["finalize"] * inventory["finalize"]
        + ["other"] * inventory["other"]
    )
    expected = assignment.assignment_spec(classes)
    _require(
        requests == expected["assignment_requests"]
        and after - before == expected["lua_stack_delta"]
        and prefix == 1
        and expected["entry_stack_values_restored"],
        "assignment normal projection differs",
    )
    _require(
        before == 2 + 2 * prefix_pair and after == before,
        "assignment reference wrapper stack shape differs",
    )
    _require(mode != 3 or requests == 0, "error destination returned after a request")
    return {
        "key_class_inventory": inventory,
        "reference_assignment_requests": requests,
        "native_contract_assignment_requests": expected["assignment_requests"],
        "lua_stack_delta": after - before,
        "entry_values_restored": prefix == 1,
        "compared": [
            "Assignment request count independent of order",
            "Lua stack delta",
            "Entry values preservation",
        ],
        "reference_next_order_observed": False,
    }


def _preflight(sources: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        isinstance(sources, Mapping) and set(sources) == set(SOURCE_PINS),
        "source partition differs",
    )
    ids = {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }
    support = {k: sources[k] for k in marker.SOURCE_PINS}
    marker.validate_structure(sources["marker_native"], support)
    assignment.validate_structure(sources["assignment_native"], support)
    marker_reference.validate_structure(sources["marker_reference"])
    assignment_reference.validate_structure(sources["assignment_reference"])
    return ids


def _build_unsealed(sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    comparisons = []
    excluded = []
    marker_counts = {k: 0 for k in ("no_metatable", "false_marker", "truthy_marker")}
    request_sum = 0
    for family, reference, project in (
        ("marker", sources["marker_reference"], marker_projection),
        ("assignment", sources["assignment_reference"], assignment_projection),
    ):
        for index, row in enumerate(reference["experiment"]["rows"]):
            if row[3]:
                _require(row[3] == 2, "unexpected protected reference status")
                excluded.append(
                    {
                        "family": family,
                        "reference_row_index": index,
                        "protected_status": row[3],
                        "normal_contract_applied": False,
                    }
                )
                continue
            projection = project(row)
            if family == "marker":
                marker_counts[projection["path"]] += 1
            else:
                request_sum += projection["reference_assignment_requests"]
            comparisons.append(
                {
                    "family": family,
                    "reference_row_index": index,
                    "projection": projection,
                    "matched": True,
                }
            )
    _require(
        marker_counts == {"no_metatable": 14, "false_marker": 12, "truthy_marker": 30}
        and request_sum == 48,
        "independent finite partition differs",
    )
    _require(
        len(comparisons) == 98 and len(excluded) == 20,
        "finite reference partition differs",
    )
    controls = []
    for name, project, row, column in (
        (
            "wrong_marker_result",
            marker_projection,
            list(sources["marker_reference"]["experiment"]["rows"][0]),
            4,
        ),
        (
            "wrong_assignment_request_count",
            assignment_projection,
            list(sources["assignment_reference"]["experiment"]["rows"][0]),
            4,
        ),
        (
            "wrong_assignment_stack_delta",
            assignment_projection,
            list(sources["assignment_reference"]["experiment"]["rows"][0]),
            7,
        ),
    ):
        row[column] += 1
        try:
            project(row)
        except ContractError:
            controls.append({"name": name, "rejected": True})
        else:
            raise ContractError("projection mutation accepted")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "source_receipts": ids,
        "comparisons": comparisons,
        "excluded_protected_errors": excluded,
        "negative_controls": controls,
        "projection_contract": {
            "marker": "Compare reference Boolean result to the abstract native AL predicate and normal Lua stack restoration",
            "assignment": "Compare reference request counts to the permutation-invariant abstract filter count and normal Lua stack restoration",
            "assignment_inventory_order": "No iteration order is recorded, reconstructed or compared",
            "not_compared": [
                "Native EAX upper bits, native return registers or native stack behavior",
                "Native instruction traces or byte execution",
                "Destination heap effects beyond assignment requests",
                "Normal cleanup on protected error paths",
            ],
        },
        "proof_domains": {
            "marker_native": {
                "finite_model_cases": sources["marker_native"]["summary"]["cases"],
                "kind": "Exact integer and abstract Lua stack model",
            },
            "marker_reference": {
                "reference_cases": 70,
                "normal_comparisons": 56,
                "excluded_errors": 14,
                "kind": "Statically linked upstream Lua 5.1.5 reference experiment",
            },
            "assignment_native": {
                "finite_model_cases": sources["assignment_native"]["summary"]["cases"],
                "kind": "Exact integer and abstract finite next-transcript model",
            },
            "assignment_reference": {
                "reference_cases": 48,
                "normal_comparisons": 42,
                "excluded_errors": 6,
                "kind": "Statically linked upstream Lua 5.1.5 reference experiment",
            },
            "all_reference_vectors_executed_by_native_model": False,
            "upstream_matrices_rerun": False,
            "reference_sources_recompiled": False,
        },
        "summary": {
            "normal_comparisons": 98,
            "marker_normal_comparisons": 56,
            "assignment_normal_comparisons": 42,
            "excluded_protected_errors": 20,
            "marker_path_counts": marker_counts,
            "assignment_request_sum": request_sum,
            "new_native_executions": 0,
            "new_reference_executions": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "finite_reference_to_abstract_API_contract_projection",
            "conditions": [
                "All seven source receipts retain exact sealed identities and existing source validators pass",
                "Only the recorded normal reference rows enter the normal abstract contracts",
                "Native and reference component domains remain separate; projections compare only common semantic observations",
            ],
            "not_claimed": [
                "Identity or equivalence of the installed Lua DLL with upstream reference sources",
                "Native helper execution by the reference C experiments, byte conformance or end-to-end native Lua execution",
                "Observed or predicted next order, all reference vectors covered by the native finite matrices, or unconditional termination",
                "Normal helper cleanup after errors, preserved heap or globals, or generic metamethod behavior",
                "Whole-game recreation or atlas accounting promotion",
            ],
        },
    }
    _assert_publication_safe(result)
    return result


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run():
        _validate_json_tree(evidence, "evidence")
        _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256,
            "sealed reference contracts differ",
        )
        actual = _build_unsealed(sources)
        _require(
            _canonical_bytes(actual) == _canonical_bytes(evidence),
            "reference contract projections differ",
        )
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_contracts(sources: Mapping[str, Any]) -> dict[str, Any]:
    def run():
        result = _build_unsealed(sources)
        _require(
            _canonical_sha256(result) == SEALED_SHA256,
            "built reference contracts differ from seal",
        )
        return result

    return _normalize(run)


def encode_contracts(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
