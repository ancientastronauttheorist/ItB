"""Conditional whole-vector-allocation join of sealed decision and nested protocols."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from src.observatory import native_lua_vector_allocation_semantics as allocation
from src.observatory import native_lua_vector_allocation_return_semantics as returns
from src.observatory import native_allocation_retry_semantics as retry
from src.observatory import native_heap_allocation_protocol as heap
from src.observatory import native_heap_allocation_handoff as handoff
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _canonical_bytes,
    _canonical_sha256,
    _source_identity,
    _validate_json_tree,
    _assert_publication_safe,
    _load_executable,
    _decode_body,
    _point,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_vector_allocation_composition"
SEALED_SHA256 = "a63d7ef54e07f8aa63449136988a237592704708ab35cbefb203ec843e8e5507"
SOURCE_PINS = {
    "program_facts": allocation.SOURCE_PINS["program_facts"],
    "allocation": (allocation.ANALYSIS_KIND, allocation.SEALED_SHA256),
    "returns": (returns.ANALYSIS_KIND, returns.SEALED_SHA256),
    "retry": (retry.ANALYSIS_KIND, retry.SEALED_SHA256),
    "heap_protocol": (heap.ANALYSIS_KIND, heap.SEALED_SHA256),
    "handoff": (handoff.ANALYSIS_KIND, handoff.SEALED_SHA256),
}
U32 = 0xFFFFFFFF
OWNER, END = 0x8A920, 0x8A97B
FRAME_BASE = 0x30001000
MAX_RECORDS = 64


class VectorAllocationCompositionError(RuntimeError):
    """A sealed partition, nested finite law or new frame join differs."""


def _require(ok, message):
    if not ok:
        raise VectorAllocationCompositionError(message)


def _normalize(fn):
    try:
        return fn()
    except VectorAllocationCompositionError:
        raise
    except Exception as exc:
        raise VectorAllocationCompositionError(str(exc)) from exc


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)
    return value


def frame_join(entry_esp=FRAME_BASE):
    _u32(entry_esp, "entry ESP")
    _require(48 <= entry_esp <= U32 - 8, "composed frame arithmetic wraps")
    a = entry_esp
    # Each offset is derived by the indicated frame transition, not a reused child fixture.
    outer_frame = a - 4
    retry_entry = outer_frame - 4 - 4
    retry_frame = retry_entry - 4
    candidate_entry = retry_frame - 4 - 4
    heap_frame = candidate_entry - 4
    heap_entry = heap_frame - 4 - 12 - 4
    after_heap = heap_entry + 4 + 12
    after_candidate = after_heap + 4 + 4 + 4
    after_retry = after_candidate + 4 + 4 + 4
    after_owner = after_retry + 4 + 4 + 4 + 4
    _require(
        (
            retry_entry,
            retry_frame,
            candidate_entry,
            heap_frame,
            heap_entry,
            after_heap,
            after_candidate,
            after_retry,
            after_owner,
        )
        == (a - 12, a - 16, a - 24, a - 28, a - 48, a - 32, a - 20, a - 8, a + 8),
        "derived frame join differs",
    )
    return {
        "owner_entry": a,
        "owner_frame": outer_frame,
        "retry_entry": retry_entry,
        "retry_frame": retry_frame,
        "candidate_entry": candidate_entry,
        "heap_frame": heap_frame,
        "heap_callee_entry": heap_entry,
        "after_heap_stdcall12": after_heap,
        "after_candidate_cdecl": after_candidate,
        "after_retry_cdecl": after_retry,
        "after_owner_ret4": after_owner,
        "heap_argument_slots": {"heap": a - 44, "flags": a - 40, "size": a - 36},
        "saved_ebp_slots": [
            {"address": a - 4, "value_source": "owner entry EBP"},
            {"address": a - 16, "value": outer_frame},
            {"address": a - 28, "value": retry_frame},
        ],
        "saved_esi_slot": a - 32,
        "continuation_slots": {
            "heap": a - 48,
            "candidate": a - 24,
            "retry": a - 12,
            "owner": a,
        },
        "continuations": {
            "heap": BASE + 0x389463,
            "candidate": BASE + 0x357507,
            "retry_large": BASE + 0x8A950,
            "retry_small": BASE + 0x8A968,
        },
        "protected_stack_interval": [a - 48, a + 8],
    }


def _protected_intervals(entry_esp):
    frame = frame_join(entry_esp)
    return [
        frame["protected_stack_interval"],
        *[
            [address, address + 4]
            for address in (heap.HEAP_WORD, heap.RETRY_WORD, heap.IAT_SLOT)
        ],
    ]


def _disjoint_storage(pointer, length, entry_esp, label):
    _u32(pointer, label)
    _require(
        type(length) is int and length > 0 and pointer + length <= 2**32,
        "storage extent wraps",
    )
    _require(
        all(
            pointer + length <= start or end <= pointer
            for start, end in _protected_intervals(entry_esp)
        ),
        label + " overlaps composed ancestor frame or protected global",
    )


def compositional_spec(n, returned_pointer=None, entry_esp=FRAME_BASE):
    """Clean conditional success relation; opaque nested behavior is not inferred."""
    _u32(n, "element count")
    frame = frame_join(entry_esp)
    if returned_pointer is not None:
        _u32(returned_pointer, "returned block pointer")
    if n == 0:
        _require(returned_pointer is None, "zero count does not call the allocator")
        return {
            "outcome": "zero_return",
            "request": None,
            "result": 0,
            "ecx": 0,
            "esp": entry_esp + 8,
            "ebp_source": "owner entry EBP",
            "metadata_write": None,
        }
    if n > 0x1FFFFFFF or n >= 0x1FFFFFFC:
        _require(
            returned_pointer is None, "open failure call has no normal pointer contract"
        )
        return {
            "outcome": (
                "size_failure_frontier"
                if n > 0x1FFFFFFF
                else "padding_failure_frontier"
            ),
            "request": None,
            "result": None,
            "stop_rva": 0x8A971 if n > 0x1FFFFFFF else 0x8A976,
            "esp": frame["owner_frame"],
            "metadata_write": None,
        }
    large = n >= 512
    request = n * 8 + (35 if large else 0)
    reachable = request <= 0xFFFFFFE0
    if returned_pointer is None:
        return {
            "outcome": "retry_entry_frontier",
            "request": request,
            "result": None,
            "stop_rva": 0x8A94B if large else 0x8A963,
            "esp": entry_esp - 8,
            "nested_first_branch": "heap" if reachable else "error",
            "positive_candidate_possible_under_normal_stable_protocol": reachable,
            "metadata_write": None,
        }
    _require(
        reachable, "stable joined candidate cannot return positive for this request"
    )
    _require(
        returned_pointer > 0,
        "normal composed block premise requires a positive pointer",
    )
    _disjoint_storage(returned_pointer, request, entry_esp, "returned block")
    if large:
        layout = returns.storage_layout_spec(returned_pointer, n * 8)
        result = layout["aligned_pointer"]
        metadata = {"address": layout["metadata_address"], "value": returned_pointer}
        final_flags = {
            "cf": 0,
            "zf": int(result == 0),
            "sf": result >> 31,
            "of": 0,
            "af": None,
            "pf": int((result & 255).bit_count() % 2 == 0),
        }
    else:
        result = returned_pointer
        metadata = None
        left, right = entry_esp - 8, 4
        value = left + right
        final_flags = {
            "cf": 0,
            "zf": int(value == 0),
            "sf": value >> 31,
            "of": ((~(left ^ right)) & (left ^ value) & U32) >> 31,
            "af": ((left ^ right ^ value) >> 4) & 1,
            "pf": int((value & 255).bit_count() % 2 == 0),
        }
    return {
        "outcome": "conditional_normal_return",
        "request": request,
        "result": result,
        "ecx": result,
        "esp": frame["after_owner_ret4"],
        "ebp_source": "owner entry EBP",
        "preserved_registers": ["ebx", "esi", "edi"],
        "edx_source": "last successful inner heap response",
        "metadata_write": metadata,
        "arithmetic_flags": final_flags,
        "block_interval": [returned_pointer, returned_pointer + request],
    }


def nested_protocol_spec(
    n, retry_flag, transcript, allow_frontier=False, entry_esp=FRAME_BASE
):
    """Nested finite contracts: an inner zero resumes the outer retry protocol."""
    _u32(n, "element count")
    _u32(retry_flag, "retry flag")
    _require(type(allow_frontier) is bool, "invalid frontier permission")
    _require(
        type(transcript) is list and len(transcript) <= MAX_RECORDS,
        "invalid finite nested transcript",
    )
    initial = compositional_spec(n, entry_esp=entry_esp)
    if initial["outcome"] != "retry_entry_frontier":
        _require(not transcript, "unreached nested records")
        return {
            "outcome": initial["outcome"],
            "owner": initial,
            "outer_calls": [],
            "candidates": [],
        }
    request = initial["request"]
    state = "candidate"
    flat = []
    candidates = []
    frame = frame_join(entry_esp)
    for index in range(len(transcript) + 1):
        if index == len(transcript):
            _require(allow_frontier, "missing outer retry record")
            law = retry.retry_spec(request, flat, True)
            _require(law["frontier_kind"] == state, "outer retry law join differs")
            return {
                "outcome": "outer_retry_frontier",
                "frontier_kind": state,
                "stop_rva": retry.CALLS[state][0],
                "esp": frame["retry_frame"]
                - (4 if state in ("candidate", "handler") else 0),
                "outer_calls": flat,
                "candidates": candidates,
                "owner": None,
            }
        record = transcript[index]
        _require(
            isinstance(record, Mapping) and record.get("kind") == state,
            "nested record kind differs",
        )
        if state == "candidate":
            _require(
                set(record) == {"kind", "responses", "allow_frontier"},
                "invalid candidate record",
            )
            law = _normalize(
                lambda: heap.heap_protocol_spec(
                    request, retry_flag, record["responses"], record["allow_frontier"]
                )
            )
            for response in law["calls"]:
                if response["kind"] == "error":
                    _disjoint_storage(
                        response["eax"], 4, entry_esp, "nested error cell"
                    )
            candidates.append(law)
            if law["outcome"] == "frontier":
                _require(
                    index + 1 == len(transcript), "unused records after inner frontier"
                )
                outer = retry.retry_spec(request, flat, True)
                _require(
                    outer["frontier_kind"] == "candidate",
                    "candidate entry join differs",
                )
                kind = law["frontier_kind"]
                return {
                    "outcome": "inner_candidate_frontier",
                    "frontier_kind": kind,
                    "stop_rva": heap.CALLS[kind],
                    "esp": frame["heap_frame"]
                    - ({"heap": 16, "handler": 8, "error": 4}[kind]),
                    "outer_calls": flat,
                    "candidates": candidates,
                    "owner": None,
                }
            value = law["result"]
            flat.append({"kind": "candidate", "eax": value})
            if value:
                _require(
                    index + 1 == len(transcript),
                    "unused records after successful allocation",
                )
                outer = retry.retry_spec(request, flat)
                _require(outer["result"] == value, "candidate to retry return differs")
                owner = compositional_spec(n, value, entry_esp)
                return {
                    "outcome": "conditional_normal_return",
                    "owner": owner,
                    "outer_calls": flat,
                    "candidates": candidates,
                }
            state = "handler"
        else:
            _require(set(record) == {"kind", "eax"}, "invalid outer opaque record")
            _u32(record["eax"], "outer opaque result")
            flat.append(dict(record))
            if state == "handler":
                state = "candidate" if record["eax"] else "failure"
            else:
                state = "candidate"
    raise VectorAllocationCompositionError("unreachable nested transcript state")


def coverage_spec(sources):
    points = sources["allocation"]["body"]["points"]
    decision = sources["allocation"]["model_evidence"]["instruction_union_rvas"]
    tails = sources["returns"]["model_evidence"]["instruction_union_rvas"]
    composed = ["0x0008a94b", "0x0008a963"]
    opened = ["0x0008a971", "0x0008a976"]
    groups = {
        "decision": decision,
        "return_tails": tails,
        "joined_retry_calls": composed,
        "open_failure_calls": opened,
    }
    flattened = [p for values in groups.values() for p in values]
    _require(
        len(flattened) == len(set(flattened)) == 34
        and sorted(flattened) == [p["rva"] for p in points],
        "owner partition is not complete and disjoint",
    )
    _require(
        len(decision) == 19 and len(tails) == 11, "component coverage sizes differ"
    )
    return {
        "entry_rva": f"0x{OWNER:08x}",
        "exclusive_end_rva": f"0x{END:08x}",
        "bytes": 91,
        "nodes": 34,
        "groups": [
            {
                "source": name,
                "nodes": len(values),
                "bytes": sum(p["size"] for p in points if p["rva"] in values),
                "instruction_rvas": values,
            }
            for name, values in groups.items()
        ],
    }


def _preflight(sources):
    _require(
        isinstance(sources, Mapping) and set(sources) == set(SOURCE_PINS),
        "source partition differs",
    )
    ids = {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }
    _require(
        sources["allocation"]["body"] == sources["returns"]["body"],
        "allocation-tail body join differs",
    )
    _require(
        sources["heap_protocol"]["bodies"][:2] == sources["handoff"]["bodies"],
        "heap-handoff body join differs",
    )
    _require(
        sources["heap_protocol"]["import_boundary"]["iat_rva"]
        == sources["handoff"]["import_boundary"]["iat_rva"],
        "heap import boundary join differs",
    )
    edge = next(e for e in sources["retry"]["opaque_calls"] if e["kind"] == "candidate")
    _require(
        edge["target_rva"] == sources["handoff"]["bodies"][0]["entry_rva"],
        "retry-candidate target join differs",
    )
    _require(
        {e["instruction"]["rva"] for e in sources["retry"]["incoming_edges"]}
        == {"0x0008a94b", "0x0008a963"},
        "allocation-retry call join differs",
    )
    return ids


def _profiles(n, flag):
    initial = compositional_spec(n)
    if initial["outcome"] != "retry_entry_frontier":
        return [([], False)]

    def candidate(responses, frontier=False):
        return {"kind": "candidate", "responses": responses, "allow_frontier": frontier}

    error = {"kind": "error", "eax": 0x11000040}
    good = candidate([{"kind": "heap", "eax": 0x10000020}])
    if initial["nested_first_branch"] == "error":
        failed = candidate([error])
    else:
        failed = candidate(
            [
                {"kind": "heap", "eax": 0},
                *([{"kind": "handler", "eax": 0}] if flag else []),
                error,
            ]
        )
    profiles = [
        ([], True),
        ([candidate([], True)], False),
        ([failed], True),
        ([failed, {"kind": "handler", "eax": 0}, {"kind": "failure", "eax": 1}], True),
    ]
    if n <= 4096:
        profiles.extend(
            [
                ([good], False),
                ([failed, {"kind": "handler", "eax": 1}, good], False),
                (
                    [
                        failed,
                        {"kind": "handler", "eax": 0},
                        {"kind": "failure", "eax": 1},
                        good,
                    ],
                    False,
                ),
            ]
        )
    return profiles


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    coverage = coverage_spec(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    witnesses = [
        sources["allocation"]["body"],
        sources["retry"]["body"],
        *sources["heap_protocol"]["bodies"],
    ]
    for witness in witnesses:
        rows = _decode_body(
            data, image, sources["program_facts"], int(witness["entry_rva"], 16)
        )
        _require(
            [_point(r) for r in rows] == witness["points"]
            and hashlib.sha256(b"".join(bytes(r.bytes) for r in rows)).hexdigest()
            == witness["sha256"],
            "exact composed witness differs",
        )
    frames = [frame_join(FRAME_BASE + a) for a in (0, 1, 7, 15)]
    n_values = [
        0,
        1,
        2,
        511,
        512,
        513,
        4096,
        0x1FFFFFF7,
        0x1FFFFFF8,
        0x1FFFFFFB,
        0x1FFFFFFC,
        0x1FFFFFFF,
        0x20000000,
        U32,
    ]
    contracts = [
        compositional_spec(n, entry_esp=FRAME_BASE + a)
        for n in n_values
        for a in (0, 1, 7, 15)
    ]
    normal = [
        compositional_spec(n, p, FRAME_BASE + a)
        for n in (1, 511, 512, 513, 4096)
        for p in (0x10000001, 0x10000020, 0x1000003F)
        for a in (0, 1, 7, 15)
    ]
    nested = [
        nested_protocol_spec(n, flag, records, frontier, FRAME_BASE + a)
        for n in n_values
        for flag in (0, 1)
        for records, frontier in _profiles(n, flag)
        for a in (0, 1, 7, 15)
    ]
    # Cross-check pure component laws only. No graph model, native replay or component build is rerun.
    for n in n_values:
        part = allocation.allocation_spec(n)
        ours = compositional_spec(n)
        _require(
            part["requested"] == ours["request"],
            "independent request partition differs",
        )
    controls = []
    checks = [
        ("zero_block_pointer", lambda: compositional_spec(512, 0)),
        ("wrapped_block_extent", lambda: compositional_spec(512, 0xFFFFFFE0)),
        ("ancestor_frame_block_alias", lambda: compositional_spec(1, FRAME_BASE - 12)),
        (
            "impossible_high_request_success",
            lambda: compositional_spec(0x1FFFFFF8, 0x10000020),
        ),
        (
            "ancestor_error_cell_alias",
            lambda: nested_protocol_spec(
                1,
                0,
                [
                    {
                        "kind": "candidate",
                        "responses": [
                            {"kind": "heap", "eax": 0},
                            {"kind": "error", "eax": FRAME_BASE - 12},
                        ],
                        "allow_frontier": False,
                    }
                ],
                True,
            ),
        ),
        (
            "collapsed_inner_zero",
            lambda: nested_protocol_spec(
                1,
                0,
                [
                    {
                        "kind": "candidate",
                        "responses": [
                            {"kind": "heap", "eax": 0},
                            {"kind": "error", "eax": 0x11000040},
                        ],
                        "allow_frontier": False,
                    }
                ],
                False,
            ),
        ),
    ]
    for name, fn in checks:
        try:
            fn()
        except VectorAllocationCompositionError:
            controls.append(
                {"name": name, "kind": "semantic_domain_rejection", "rejected": True}
            )
        else:
            raise VectorAllocationCompositionError(
                "negative composition control accepted: " + name
            )
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "owner_body": dict(sources["allocation"]["body"]),
        "coverage": coverage,
        "frame_joins": frames,
        "count_partition": [
            {"minimum": 0, "maximum": 0, "outcome": "zero_return"},
            {"minimum": 1, "maximum": 511, "outcome": "small_request"},
            {
                "minimum": 512,
                "maximum": 0x1FFFFFF7,
                "outcome": "large_request_reaches_heap",
            },
            {
                "minimum": 0x1FFFFFF8,
                "maximum": 0x1FFFFFFB,
                "outcome": "candidate_error_then_outer_retry",
            },
            {
                "minimum": 0x1FFFFFFC,
                "maximum": 0x1FFFFFFF,
                "outcome": "padding_failure_frontier",
            },
            {"minimum": 0x20000000, "maximum": U32, "outcome": "size_failure_frontier"},
        ],
        "model_evidence": {
            "contract_cases_sha256": _canonical_sha256(contracts),
            "normal_cases_sha256": _canonical_sha256(normal),
            "nested_cases_sha256": _canonical_sha256(nested),
            "negative_controls": controls,
        },
        "summary": {
            "owner_bytes": 91,
            "owner_nodes": 34,
            "decision_nodes": 19,
            "return_tail_nodes": 11,
            "joined_call_sites": 2,
            "open_failure_call_sites": 2,
            "frame_joins": len(frames),
            "contract_cases": len(contracts),
            "normal_cases": len(normal),
            "nested_cases": len(nested),
            "component_model_reruns": 0,
            "actual_native_executions": 0,
            "actual_import_calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "conditional_sealed_component_composition_with_new_nested_frame_and_storage_joins",
            "premises": [
                "All supplied opaque responses return normally with the component calling conventions, twelve heap argument bytes removed and no cdecl argument cleanup",
                "Callees preserve nonvolatile registers and every composed ancestor frame, request, continuation, global and IAT word, including pushed arguments",
                "Heap, retry-flag and IAT words remain stable; finite transcripts distinguish inner heap handlers from outer retry handlers",
                "Each inner error cell is mapped writable and disjoint from the complete composed ancestor stack and protected globals",
                "A successful candidate supplies a positive pointer to an existing nonwrapping block of requested bytes disjoint from all composed frame and global storage; no allocation success is inferred",
            ],
            "normal_relation": "Zero returns zero directly; conditional small success returns its block pointer, large success returns its aligned payload pointer after writing original pointer metadata; EAX and ECX agree, EDX is the last successful inner heap volatile output, nonvolatiles are restored and owner entry ESP advances eight",
            "nested_error_relation": "An inner error writes twelve and returns zero only to the outer retry protocol; its handler and possible failure response determine later retry or a finite frontier, never an inferred owner zero return",
            "high_count_relation": "Four counts immediately below the padding-overflow interval always enter the expanded candidate error path under stable requests and cannot produce positive candidate success through supplied normal returns",
            "coverage_policy": "All thirty-four owner sites are partitioned into nineteen decision sites, eleven return sites, two joined retry calls and two unresolved failure-call boundaries",
            "projection_policy": "Pure nested protocol comparisons project control outcomes and EAX results; standalone sampled volatile outputs are not equated. Register source labels express conditional preservation, while new symbolic frame offsets rebase the component interfaces without rerunning their graph fixtures",
            "not_claimed": [
                "Universal termination, failure-callee nonreturn or a normal result past unresolved failure calls",
                "Actual HeapAlloc execution, mapped storage validity without premises or complete allocator-library behavior",
                "Standalone native re-execution, full vector resize behavior, whole-program equivalence or accounting promotion",
            ],
        },
    }
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed during build",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run():
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and evidence["source_receipts"] == ids,
            "sealed allocation composition differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_composition(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    def run():
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_composition(
    executable: Path, evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run():
        validate_structure(evidence, sources)
        actual = build_composition(executable, sources)
        _require(
            _canonical_bytes(actual) == _canonical_bytes(evidence),
            "exact allocation composition differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(actual["summary"]),
        }

    return _normalize(run)


def encode_composition(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
