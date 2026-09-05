"""Conditional composition of failure dispatch, stores and return interfaces."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from src.observatory import native_assertion_helper_failure_dispatch as dispatch
from src.observatory import native_assertion_helper_failure_stores as stores
from src.observatory import native_assertion_helper_failure_return as returns
from src.observatory import native_assertion_helper_owner_composition as owner
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
ANALYSIS_KIND = "pe_native_assertion_helper_failure_composition"
SEALED_SHA256 = "c0355a6465a09de57f596c73594e93ce9dfd5cbc7bb3ad76ab44a06f6da31f6d"
SOURCE_PINS = {
    "dispatch": (dispatch.ANALYSIS_KIND, dispatch.SEALED_SHA256),
    "stores": (stores.ANALYSIS_KIND, stores.SEALED_SHA256),
    "returns": (
        returns.ANALYSIS_KIND,
        "0971cfa63e07affc80e0574319382099d9c41b29b5a380d1eb70a40e832a3444",
    ),
    "frontier": dispatch.SOURCE_PINS["frontier"],
    "owner": (owner.ANALYSIS_KIND, owner.SEALED_SHA256),
    "program_facts": dispatch.SOURCE_PINS["program_facts"],
}


class FailureCompositionError(RuntimeError):
    """A static partition, conditional interface or sealed source join differs."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise FailureCompositionError(message)


def _normalize(fn: Any) -> Any:
    try:
        return fn()
    except FailureCompositionError:
        raise
    except Exception as exc:
        raise FailureCompositionError(str(exc)) from exc


def coverage_spec() -> dict[str, Any]:
    return {
        "frontier_entry_rva": "0x00357b6a",
        "exclusive_end_rva": "0x00357c65",
        "static_bytes": 251,
        "static_instructions": 56,
        "modeled_instruction_union": 55,
        "unexecuted_boundary_instruction_rvas": ["0x00357b81"],
        "segments": [
            {
                "source": "dispatch",
                "start_rva": "0x00357b6a",
                "exclusive_end_rva": "0x00357b83",
                "bytes": 25,
                "static_nodes": 10,
                "modeled_nodes": 9,
            },
            {
                "source": "stores",
                "start_rva": "0x00357b83",
                "exclusive_end_rva": "0x00357c5c",
                "bytes": 217,
                "static_nodes": 42,
                "modeled_nodes": 42,
            },
            {
                "source": "returns",
                "start_rva": "0x00357c5c",
                "exclusive_end_rva": "0x00357c65",
                "bytes": 9,
                "static_nodes": 4,
                "modeled_nodes": 4,
            },
        ],
        "subsidiaries": [
            {
                "role": "wrapper",
                "start_rva": "0x00357b42",
                "exclusive_end_rva": "0x00357b6a",
                "bytes": 40,
                "nodes": 12,
                "counted_in_frontier": False,
            },
            {
                "role": "owner_continuation",
                "start_rva": "0x00379e5f",
                "exclusive_end_rva": "0x00379e63",
                "bytes": 4,
                "nodes": 3,
                "counted_in_frontier": False,
                "already_in_prior_owner_partition": True,
            },
        ],
    }


def failure_contract(
    query_return: int,
    final_import_return: int,
    outer_ebp_word: int,
    outer_return_word: int,
) -> dict[str, Any]:
    """Conditional boundary relation; outer words are current values, not originals."""
    _require(
        all(
            type(v) is int and 0 <= v <= 0xFFFFFFFF
            for v in (
                query_return,
                final_import_return,
                outer_ebp_word,
                outer_return_word,
            )
        ),
        "failure contract inputs require u32",
    )
    zero = query_return == 0
    return {
        "boundary": "conditional_outer_return" if zero else "before_interrupt",
        "eax": final_import_return if zero else query_return,
        "ecx_value": None if zero else 2,
        "ecx_edx_source": (
            "last wrapper import volatile outputs"
            if zero
            else "query output except ECX replaced with two"
        ),
        "ebp_value": outer_ebp_word if zero else None,
        "ebp_source": "current outer word at F" if zero else "new frame G",
        "instruction_pointer": outer_return_word if zero else BASE + 0x357B81,
        "esp_G_offset": 824 if zero else -804,
        "esp_F_offset": 8 if zero else -1620,
        "nonvolatile_source": "EBX ESI EDI at failure-entry boundary under import preservation premises",
        "query_normal_return_assumed": True,
        "wrapper_normal_returns_assumed": 4 if zero else 0,
        "interrupt_executed": False,
        "termination_guaranteed": False,
        "original_owner_words_guaranteed": False,
        "pair_and_record_contents": "unspecified after imports",
    }


def relation_partitions() -> list[dict[str, Any]]:
    result = []
    for zero in (False, True):
        row = failure_contract(0 if zero else 1, 0x11223344, 0x22334455, 0x33445566)
        del row["eax"]
        row["eax_source"] = "final wrapper import return" if zero else "query return"
        if zero:
            del row["ebp_value"]
            row["ebp_value_source"] = "current outer word at F"
            del row["instruction_pointer"]
            row["instruction_pointer_source"] = "current outer word at F plus four"
        result.append({"query_return_zero": zero, "relation": row})
    return result


def interface_spec() -> dict[str, Any]:
    return {
        "frames": {"G_F_offset": -816, "H_G_offset": -816, "F_G_offset": 816},
        "dispatch_to_stores": {
            "boundary_rva": "0x00357b83",
            "eax": 0,
            "esp_G_offset": -804,
            "ebp_source": "G",
            "flags_image_known_mask": 0x308C7,
            "flags_image_known_value": 0x46,
            "unknown_memory": "Only G header words were protected across query; globals, records and other stack words are unspecified",
        },
        "stores_to_returns": {
            "boundary_rva": "0x00357c5c",
            "eax": 4,
            "ecx_source": "current global word at RVA 0x00493f24",
            "esp_G_offset": -808,
            "argument_address_rva": "0x003f19f8",
            "runtime_pair_contents_proved": False,
        },
        "new_return_memory_premises": {
            "protected_G_intervals": [[-816, -804], [0, 8], [816, 824]],
            "pending_status_during_handle_query_G_interval": [-820, -816],
            "outer_words": "Values at return-tranche entry after the earlier query; not necessarily original owner words",
            "earlier_query_protects_outer_words": False,
        },
        "normal_import_return_counts": {"query": 1, "wrapper_on_zero_branch": 4},
        "return_interface": {
            "esp_G_offset": 824,
            "esp_F_offset": 8,
            "ebp_source": "current outer word at F",
            "target_source": "current outer word at F plus four",
            "eax_source": "last wrapper import return",
        },
        "global_preservation_across_wrapper_claimed": False,
        "concrete_upstream_vectors_concatenated": False,
        "interface_domain": "Symbolic frame offsets and explicit memory contracts; component synthetic matrices remain separate",
    }


def _preflight(sources: Mapping[str, Any]) -> dict[str, Any]:
    _validate_json_tree(sources, "sources")
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    _require(
        SOURCE_PINS["returns"][1] != "AWAIT_RETURN", "return receipt not sealed yet"
    )
    ids = {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }
    identity = sources["program_facts"]["identity"]
    _require(
        identity["executable_sha256"] == EXE_SHA256
        and all(
            _canonical_bytes(sources[k]["build_identity"]) == _canonical_bytes(identity)
            for k in sources
            if k != "program_facts"
        ),
        "source build differs",
    )
    return ids


def _interfaces(sources: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        sources["owner"]["open_failure_frontier"]["entry_rva"] == "0x00357b6a",
        "owner frontier join differs",
    )
    ds = sources["dispatch"]
    ss = sources["stores"]
    rs = sources["returns"]
    _require(
        ds["frame"] == dispatch.frame_spec()
        and ds["assumed_query_summary"] == dispatch.query_summary_spec(),
        "dispatch frame or query contract differs",
    )
    _require(
        ds["exclusive_stops"]["zero_query"]["rva"]
        == ss["slice"]["start_rva"]
        == "0x00357b83"
        and ds["frame"]["query_return_esp_G_offset"]
        == ss["transfer"]["entry_esp_G_offset"]
        == -804
        and ss["transfer"]["entry_eax"] == 0,
        "dispatch to stores interface differs",
    )
    _require(
        ss["transfer"] == stores.transfer_spec()
        and ss["slice"]["exclusive_stop_rva"] == "0x00357c5c"
        and ss["transfer"]["final_esp_G_offset"] == -808
        and ss["transfer"]["final_eax"] == 4
        and ss["transfer"]["argument_at_final_esp"]["value_rva"] == "0x003f19f8",
        "stores to return interface differs",
    )
    summary = rs["assumed_import_summaries"]
    _require(
        summary == returns.call_summary_spec()
        and summary["protected_memory_G_intervals"]
        == [[-816, -804], [0, 8], [816, 824]]
        and summary["get_current_process_additional_protected_G_interval"]
        == [-820, -816],
        "stronger return memory premises differ",
    )
    _require(
        rs["relation"]["final_esp_F_offset"] == 8
        and rs["relation"]["original_owner_words_not_assumed"] is True,
        "current outer word relation differs",
    )
    _require(
        all(
            w["G_offset"] + 4 <= 816 or w["G_offset"] >= 824 for w in ss["stack_writes"]
        ),
        "store slice overlaps current outer words",
    )
    # Cross-check the independently authored interface against the already
    # specified relations; this does not run any prior model matrix.
    for q in (0, 1, 0xFFFFFFFF):
        whole = failure_contract(q, 0x11223344, 0x22334455, 0x33445566)
        if q:
            local = dispatch.dispatch_spec(q)
            _require(
                whole["eax"] == local["eax"]
                and whole["ecx_value"] == local["ecx_value"]
                and whole["esp_G_offset"] == local["esp_G_offset"],
                "nonzero contract projection differs",
            )
        else:
            local = returns.return_spec(0x11223344, 0x22334455, 0x33445566)
            _require(
                whole["eax"] == local["eax"]
                and whole["ebp_value"] == local["ebp"]
                and whole["instruction_pointer"] == local["instruction_pointer"]
                and whole["esp_G_offset"] == local["esp_G_offset"],
                "zero contract projection differs",
            )
    return interface_spec()


def _coverage(sources: Mapping[str, Any]) -> dict[str, Any]:
    spec = coverage_spec()
    chunks = {
        "dispatch": sources["dispatch"]["static_prefix"]["instruction_points"],
        "stores": sources["stores"]["slice"]["points"],
        "returns": sources["returns"]["parent_tail"]["points"],
    }
    all_points = []
    segments = []
    for segment in spec["segments"]:
        points = chunks[segment["source"]]
        at = int(segment["start_rva"], 16)
        for point in points:
            _require(
                type(point["size"]) is int
                and point["size"] > 0
                and int(point["rva"], 16) == at,
                "frontier partition gap or overlap",
            )
            at += point["size"]
        _require(
            at == int(segment["exclusive_end_rva"], 16)
            and len(points) == segment["static_nodes"],
            "frontier segment size differs",
        )
        all_points.extend(points)
        segments.append(dict(segment) | {"points_sha256": _canonical_sha256(points)})
    expected = [
        {k: p[k] for k in ("rva", "size", "sha256")}
        for p in sources["frontier"]["function_body"]["reviewed_points"]
    ]
    _require(
        all_points == expected and len({p["rva"] for p in all_points}) == 56,
        "full frontier coverage differs",
    )
    subsidiaries = []
    for sub in spec["subsidiaries"]:
        section = sources["returns"][sub["role"]]
        points = section["points"]
        at = int(sub["start_rva"], 16)
        for point in points:
            _require(int(point["rva"], 16) == at, "subsidiary point partition differs")
            at += point["size"]
        _require(
            at == int(sub["exclusive_end_rva"], 16)
            and len(points) == sub["nodes"]
            and section["bytes"] == sub["bytes"],
            "subsidiary coverage differs",
        )
        subsidiaries.append(dict(sub) | {"points_sha256": _canonical_sha256(points)})
    return {
        **spec,
        "segments": segments,
        "subsidiaries": subsidiaries,
        "points_sha256": _canonical_sha256(all_points),
        "body_sha256": sources["frontier"]["function_body"]["body_sha256"],
        "disjoint_complete_static_partition": True,
    }


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    coverage = _coverage(sources)
    interfaces = _interfaces(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    frontier = _decode_body(data, image, sources["program_facts"], 0x357B6A)
    wrapper = _decode_body(data, image, sources["program_facts"], 0x357B42)
    outer = _decode_body(data, image, sources["program_facts"], 0x379D28)
    _require(
        _canonical_sha256([_point(r) for r in frontier]) == coverage["points_sha256"]
        and hashlib.sha256(b"".join(bytes(r.bytes) for r in frontier)).hexdigest()
        == coverage["body_sha256"],
        "fresh full frontier body differs",
    )
    _require(
        [_point(r) for r in wrapper] == sources["returns"]["wrapper"]["points"]
        and hashlib.sha256(b"".join(bytes(r.bytes) for r in wrapper)).hexdigest()
        == sources["returns"]["wrapper"]["sha256"],
        "fresh wrapper body differs",
    )
    continuation = [r for r in outer if r.address - BASE >= 0x379E5F]
    _require(
        [_point(r) for r in continuation]
        == sources["returns"]["owner_continuation"]["points"]
        and _canonical_sha256([_point(r) for r in outer])
        == sources["owner"]["coverage"]["instruction_points_sha256"],
        "fresh owner continuation differs",
    )
    for lo, hi, expected in (
        (0x357B6A, 0x357B83, sources["dispatch"]["static_prefix"]["sha256"]),
        (0x357B83, 0x357C5C, sources["stores"]["slice"]["sha256"]),
    ):
        payload = b"".join(
            bytes(r.bytes) for r in frontier if lo <= r.address - BASE < hi
        )
        _require(
            hashlib.sha256(payload).hexdigest() == expected,
            "fresh component slice hash differs",
        )
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed during composition",
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "coverage": coverage,
        "interfaces": interfaces,
        "relation_partitions": relation_partitions(),
        "proof_domains": {
            "dispatch": {
                "evidence": "conditional integer model of query and exclusive branch stops",
                "cases": sources["dispatch"]["summary"]["model_cases"],
            },
            "stores": {
                "evidence": "independent arbitrary-memory overlays and ordered events on synthetic boundaries",
                "cases": sources["stores"]["summary"]["cases"],
            },
            "returns": {
                "evidence": "conditional integer model with stronger header and current outer word protection",
                "cases": sources["returns"]["summary"]["model_cases"],
            },
            "upstream_model_matrices_rerun": False,
            "all_concrete_vectors_composed": False,
        },
        "summary": {
            "frontier_static_bytes": 251,
            "frontier_static_nodes": 56,
            "modeled_frontier_union_nodes": 55,
            "unexecuted_interrupt_nodes": 1,
            "subsidiary_wrapper_bytes": 40,
            "subsidiary_wrapper_nodes": 12,
            "reused_owner_continuation_bytes": 4,
            "reused_owner_continuation_nodes": 3,
            "new_model_executions": 0,
            "actual_import_executions": 0,
            "interrupt_executions": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "conditional_failure_frontier_interface_composition",
            "conditions": [
                "Query returns normally; its zero branch reaches stores under mapped read and arbitrary-memory premises",
                "On the zero branch all four wrapper imports return normally under new stronger frame-header and current outer-word protection premises",
                "Current outer words need not equal original owner words because the earlier query did not protect them",
                "Component finite domains remain distinct; only static partitions and explicit symbolic interfaces are composed",
            ],
            "not_claimed": [
                "Interrupt effects or execution, imported implementation behavior, actual process termination or nonreturn",
                "Original owner EBP or return word preservation across the earlier query",
                "Runtime pair validity or preserved record contents after wrapper imports",
                "A single end-to-end emulation or validity of every Cartesian product of component vectors",
                "Unconditional complete failure semantics, real game recreation or atlas accounting promotion",
            ],
            "source_validation": "Canonical sealed component identities plus full frontier, wrapper and owner-continuation decode and partition checks; upstream models and SDK probes are not rerun",
        },
    }
    _assert_publication_safe(result)
    return result


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256,
            "sealed failure composition differs",
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["coverage"] == _coverage(sources)
            and evidence["interfaces"] == _interfaces(sources)
            and evidence["relation_partitions"] == relation_partitions(),
            "failure composition specification differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_composition(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_composition(
    executable: Path, evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        actual = build_composition(executable, sources)
        _require(
            _canonical_bytes(evidence) == _canonical_bytes(actual),
            "exact failure composition differs",
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
