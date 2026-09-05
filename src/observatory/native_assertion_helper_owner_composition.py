"""Whole-owner coverage and conditional interface composition of sealed tranches."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import capstone.x86_const as x86
from src.observatory import native_assertion_helper_caller_fill as caller
from src.observatory import native_assertion_helper_import_handoff as handoff
from src.observatory import native_assertion_helper_import_arguments as arguments
from src.observatory import native_assertion_helper_return_tail as tail
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
ANALYSIS_KIND = "pe_native_assertion_helper_owner_composition"
SEALED_SHA256 = "62844b54a1fdbc5b3c466bf9a20e87a1ec91c6f18c0cf5e1f26379fd8fe01dbe"
OWNER, END = 0x379D28, 0x379E63
SOURCE_PINS = {
    "pair": arguments.SOURCE_PINS["pair"],
    "program_facts": arguments.SOURCE_PINS["program_facts"],
    "caller": (caller.ANALYSIS_KIND, caller.SEALED_SHA256),
    "handoff": (handoff.ANALYSIS_KIND, handoff.SEALED_SHA256),
    "arguments": (arguments.ANALYSIS_KIND, arguments.SEALED_SHA256),
    "tail": (tail.ANALYSIS_KIND, tail.SEALED_SHA256),
    "failure_frontier": (
        "pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary",
        "0d8bb3aecc53090dc5282844885ed327e79541ebaad4b7ca928e0494f86b08a9",
    ),
}


class OwnerError(RuntimeError):
    """A complete partition, sealed interface join, or conditional relation differs."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise OwnerError(message)


def _normalize(fn: Any) -> Any:
    try:
        return fn()
    except OwnerError:
        raise
    except Exception as exc:
        raise OwnerError(str(exc)) from exc


def coverage_spec() -> dict[str, Any]:
    return {
        "owner_entry_rva": "0x00379d28",
        "exclusive_end_rva": "0x00379e63",
        "bytes": 315,
        "instructions": 78,
        "segments": [
            {
                "source": "handoff",
                "start_rva": "0x00379d28",
                "exclusive_end_rva": "0x00379e20",
                "bytes": 248,
                "instructions": 55,
            },
            {
                "source": "arguments",
                "start_rva": "0x00379e20",
                "exclusive_end_rva": "0x00379e37",
                "bytes": 23,
                "instructions": 6,
            },
            {
                "source": "tail",
                "start_rva": "0x00379e37",
                "exclusive_end_rva": "0x00379e63",
                "bytes": 44,
                "instructions": 17,
            },
        ],
    }


def owner_contract(
    first_return: int, third_return: int, selector: int, compare_equal: bool = True
) -> dict[str, Any]:
    """Conditional relation; prefix realization requires its separate finite domain."""
    _require(
        all(
            type(v) is int and 0 <= v <= 0xFFFFFFFF
            for v in (first_return, third_return, selector)
        ),
        "owner relation inputs require u32",
    )
    _require(type(compare_equal) is bool, "comparison equality requires bool")
    pre = selector != 0xFFFFFFFF
    post = pre and first_return == 0 and third_return == 0
    return {
        "prefix_selector_sampled": selector in (0, 0xFFFFFFFF),
        "pre_helper_called": pre,
        "post_helper_called": post,
        "helper_call_count": int(pre) + int(post),
        "modeled_boundary": (
            "direct_caller_return" if compare_equal else "open_external_transfer"
        ),
        "eax": third_return,
        "ecx_source": "prefix_cookie_seed",
        "ebx_source": "owner_entry_ebx",
        "esi_source": "owner_entry_esi",
        "edi_source": "owner_entry_edi",
        "ebp_source": "owner_entry_ebp" if compare_equal else "established_frame",
        "esp_owner_entry_delta": 4 if compare_equal else -816,
        "instruction_target": (
            "owner_entry_return_word" if compare_equal else "0x00357b6a"
        ),
        "global_clear_word_at_modeled_boundary": 0 if post else None,
        "record_contents_after_third_import": "unspecified",
        "mismatch_future_behavior": "unproved beyond the external transfer boundary",
    }


def relation_partitions() -> list[dict[str, Any]]:
    result = []
    for first_zero in (False, True):
        for third_zero in (False, True):
            for marker in (False, True):
                for equal in (False, True):
                    outcome = owner_contract(
                        0 if first_zero else 1,
                        0 if third_zero else 1,
                        0xFFFFFFFF if marker else 0,
                        equal,
                    )
                    del outcome["eax"]
                    outcome["eax_source"] = "third_import_return"
                    result.append(
                        {
                            "first_return_zero": first_zero,
                            "third_return_zero": third_zero,
                            "selector_marker": marker,
                            "current_compare_equal": equal,
                            "selector_representative": 0xFFFFFFFF if marker else 0,
                            "relation": outcome,
                        }
                    )
    return result


def interface_spec() -> dict[str, Any]:
    return {
        "frame_relation": "Established EBP equals owner entry ESP minus four",
        "entry_to_first_import": {
            "boundary_rva": "0x00379e20",
            "esp_frame_offset": -812,
            "ebp_frame_offset": 0,
            "saved_edi_frame_offset": -812,
            "protected_cookie_frame_offset": -4,
            "saved_ebp_frame_offset": 0,
            "return_word_frame_offset": 4,
            "selector_frame_offset": 8,
            "record_frame_regions": [[-808, -800], [-800, -720], [-720, -4]],
            "cookie_value_relation": "Protected slot equals prefix cookie seed XOR frame",
        },
        "first_two_imports": {
            "first_arguments": [],
            "second_arguments": [0],
            "normal_return_assumed": True,
            "callee_argument_cleanup_bytes": [0, 4],
            "preserved_nonvolatile_registers": ["ebx", "esi", "edi", "ebp"],
            "caller_memory_preserved_from_frame_offset": -812,
            "first_return_provenance": "Copied from EAX into EDI before second import",
            "second_return_use": "Discarded when EAX is replaced by pointer-pair address",
        },
        "third_import_entry": {
            "boundary_rva": "0x00379e37",
            "esp_frame_offset": -816,
            "argument_at_pre_call_esp": {"frame_offset": -808},
            "edi_source": "first_import_return",
        },
        "third_import_return": {
            "normal_return_assumed": True,
            "callee_argument_cleanup_bytes": 4,
            "esp_frame_offset": -812,
            "preserved_nonvolatile_registers": ["ebx", "esi", "edi", "ebp"],
            "protected_word_frame_offsets": [-812, -4, 0, 4, 8],
            "record_memory_preservation_claimed": False,
            "global_memory_preservation_claimed": False,
        },
        "tail_to_modeled_boundary": {
            "recovered_word": "Protected slot XOR frame equals prefix cookie seed",
            "direct_return_condition": "Recovered word equals current global comparison word",
            "mismatch_boundary": "0x00357b6a with caller continuation still on stack",
            "saved_edi_slot_final_preservation_claimed": False,
            "saved_edi_slot_note": "The equality-check CALL overwrites this slot after its old value has been restored to EDI",
        },
        "all_import_returns_are_premises": True,
        "prefix_specific_architectural_diversion_excluded": True,
    }


def _preflight(sources: Mapping[str, Any]) -> dict[str, Any]:
    _validate_json_tree(sources, "sources")
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
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
        "source build identity differs",
    )
    return ids


def _join_sources(sources: Mapping[str, Any]) -> dict[str, Any]:
    spec = interface_spec()
    _require(
        sources["caller"]["setup"]["layout"] == caller.frame_layout(),
        "original frame layout differs",
    )
    _require(
        sources["handoff"]["source_receipts"]["caller"]["canonical_sha256"]
        == caller.SEALED_SHA256,
        "caller to handoff identity differs",
    )
    _require(
        all(
            b["values"]["esp"] - b["values"]["ebp"] == -812
            for b in sources["handoff"]["boundary_observations"]
        ),
        "handoff frame position differs",
    )
    transfer = sources["arguments"]["symbolic_transfer"]
    _require(
        transfer == arguments.argument_transfer_spec(), "argument relation differs"
    )
    _require(
        transfer["entry_esp_offset"] == -812
        and transfer["final_registers"]["esp"]
        == {"kind": "frame_relative", "offset": -816}
        and transfer["final_registers"]["edi"]
        == {"kind": "opaque_u32", "name": "call_0_eax"}
        and transfer["unexecuted_call_argument"]["value"]
        == {"kind": "frame_relative", "offset": -808},
        "argument to tail state differs",
    )
    first_two = sources["arguments"]["assumed_call_summaries"]
    _require(
        [s["callee_argument_cleanup_bytes"] for s in first_two] == [0, 4]
        and all(
            s["caller_owned_memory_preserved_from_frame_offset"] == -812
            for s in first_two
        ),
        "first two call assumptions differ",
    )
    third = sources["tail"]["assumed_import_summary"]
    _require(
        third == tail.call_summary_spec()
        and third["pre_call_esp_frame_offset"] == -816
        and third["return_esp_frame_offset"] == -812
        and [w["frame_offset"] for w in third["protected_words"]]
        == [-812, -4, 0, 4, 8],
        "third call protection or stack join differs",
    )
    _require(
        sources["tail"]["checker"] == tail.checker_spec(), "checker contract differs"
    )
    for row in relation_partitions():
        f, t, m, e = (
            row[k]
            for k in (
                "first_return_zero",
                "third_return_zero",
                "selector_marker",
                "current_compare_equal",
            )
        )
        local = tail.tail_spec(0 if f else 1, 0 if t else 1, 0xFFFFFFFF if m else 0, e)
        whole = row["relation"]
        _require(
            whole["post_helper_called"] == local["small_helper_called"]
            and whole["esp_owner_entry_delta"] == local["esp_frame_offset"] - 4,
            "whole-owner tail projection differs",
        )
    return spec


def _coverage(sources: Mapping[str, Any]) -> dict[str, Any]:
    spec = coverage_spec()
    descriptions = {
        "handoff": sources["handoff"]["prefix"],
        "arguments": sources["arguments"]["slice"],
        "tail": sources["tail"]["tail"],
    }
    points = []
    segments = []
    for segment in spec["segments"]:
        data = descriptions[segment["source"]]
        chunk = data["points"]
        start = int(segment["start_rva"], 16)
        end = int(segment["exclusive_end_rva"], 16)
        at = start
        for point in chunk:
            _require(
                int(point["rva"], 16) == at
                and type(point["size"]) is int
                and point["size"] > 0,
                "instruction coverage has a gap or overlap",
            )
            at += point["size"]
        _require(
            at == end
            and len(chunk) == segment["instructions"]
            and data["size"] == segment["bytes"],
            "segment coverage differs",
        )
        points.extend(chunk)
        segments.append(
            dict(segment)
            | {
                "instruction_points_sha256": _canonical_sha256(chunk),
                "body_sha256": data["sha256"],
            }
        )
    body = sources["pair"]["bodies"][0]
    _require(
        points == body["points"]
        and body["entry_rva"] == spec["owner_entry_rva"]
        and body["body_size"] == spec["bytes"]
        and len(points) == 78
        and len({p["rva"] for p in points}) == 78,
        "whole body coverage differs",
    )
    return {
        **spec,
        "segments": segments,
        "body_sha256": body["body_sha256"],
        "instruction_points_sha256": _canonical_sha256(points),
        "disjoint_complete_partition": True,
    }


def _prehelper_grammar(rows: Mapping[int, Any]) -> None:
    def reg(o: Any, name: int) -> bool:
        return o.type == x86.X86_OP_REG and o.reg == name

    r = rows[0x379D3D]
    _require(
        r.id == x86.X86_INS_CMP and len(r.operands) == 2,
        "prefix selector comparison differs",
    )
    m, i = r.operands
    _require(
        m.type == x86.X86_OP_MEM
        and m.size == 4
        and m.mem.base == x86.X86_REG_EBP
        and m.mem.index == m.mem.segment == 0
        and m.mem.disp == 8
        and i.type == x86.X86_OP_IMM
        and i.imm == -1,
        "prefix selector operands differ",
    )
    r = rows[0x379D41]
    _require(
        r.id == x86.X86_INS_PUSH
        and len(r.operands) == 1
        and reg(r.operands[0], x86.X86_REG_EDI),
        "selector flags intervening instruction differs",
    )
    r = rows[0x379D42]
    _require(
        r.id == x86.X86_INS_JE
        and len(r.operands) == 1
        and r.operands[0].type == x86.X86_OP_IMM
        and r.operands[0].imm == BASE + 0x379D4D,
        "prefix selector branch differs",
    )
    r = rows[0x379D47]
    _require(
        r.id == x86.X86_INS_CALL
        and r.operands[0].type == x86.X86_OP_IMM
        and r.operands[0].imm == BASE + 0x3586B6,
        "prefix helper call differs",
    )


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    coverage = _coverage(sources)
    interfaces = _join_sources(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    decoded = _decode_body(data, image, sources["program_facts"], OWNER)
    points = [_point(r) for r in decoded]
    _require(
        points == sources["pair"]["bodies"][0]["points"], "fresh owner decode differs"
    )
    by = {r.address - BASE: r for r in decoded}
    _prehelper_grammar(by)
    payload = b"".join(bytes(r.bytes) for r in decoded)
    _require(
        len(payload) == 315
        and hashlib.sha256(payload).hexdigest() == coverage["body_sha256"],
        "fresh complete owner body differs",
    )
    for segment in coverage["segments"]:
        start, end = int(segment["start_rva"], 16), int(
            segment["exclusive_end_rva"], 16
        )
        chunk = b"".join(
            bytes(r.bytes) for r in decoded if start <= r.address - BASE < end
        )
        _require(
            hashlib.sha256(chunk).hexdigest() == segment["body_sha256"],
            "fresh segment bytes differ",
        )
    frontier = sources["failure_frontier"]
    _require(
        frontier["function_body"]["entry_rva"] == "0x00357b6a"
        and frontier["summary"]["reviewed_target_bytes"] == 251
        and frontier["summary"]["sealed_instruction_count"] == 56,
        "failure frontier differs",
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
            "handoff": {
                "kind": "finite exact same-instance prefix emulation",
                "cases": 256,
                "matrix": sources["handoff"]["matrix"],
                "matrix_rerun": False,
            },
            "arguments": {
                "kind": "exact static grammar and conditional symbolic import transfer",
                "matrix_rerun": False,
            },
            "tail": {
                "kind": "exact grammar and conditional finite integer model",
                "cases": 1728,
                "matrix": sources["tail"]["matrix"],
                "matrix_rerun": False,
            },
            "composition": "Disjoint full-owner instruction coverage and explicit interface compatibility; these evidence domains remain distinct",
        },
        "open_failure_frontier": {
            "entry_rva": "0x00357b6a",
            "prior_structural_bytes": 251,
            "prior_structural_nodes": 56,
            "semantics": "Open beyond the transfer; eventual return, failure behavior and external effects are not established",
            "source_canonical_sha256": SOURCE_PINS["failure_frontier"][1],
        },
        "summary": {
            "owner_bytes": 315,
            "owner_instructions": 78,
            "segments": 3,
            "relation_partitions": 16,
            "new_dynamic_executions": 0,
            "transitive_matrices_rerun": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "whole_owner_conditional_composition_without_accounting_promotion",
            "conditions": [
                "All imported calls return normally under the separately stated stack and protection assumptions",
                "The prefix uses its declared finite matrix; relation values outside that matrix do not acquire prefix execution proof",
                "The current comparison global is independent of prefix seed; equality closes the direct modeled return path only",
                "Ordinary nonwrapping integer and stack semantics; no prefix-specific architectural diversion",
            ],
            "not_claimed": [
                "All inputs, CPU states, addresses or imported implementation effects",
                "Unchanged records or global memory across the third imported call",
                "Mismatch target never returns or has any specific failure semantics",
                "Real game execution, whole-game recreation, authentic context capture or native hardware correctness",
                "Atlas level three or level six semantic promotion or global accounting changes",
            ],
            "source_validation": "Canonical sealed source identities, complete disjoint point coverage and interface joins plus fresh full-owner PE decode and per-segment body hashes; dependent matrices and SDK probe are not rerun",
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
            "sealed owner composition differs",
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["coverage"] == _coverage(sources)
            and evidence["interfaces"] == _join_sources(sources)
            and evidence["relation_partitions"] == relation_partitions(),
            "owner relation or joins differ",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_owner(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_owner(
    executable: Path, evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        actual = build_owner(executable, sources)
        _require(
            _canonical_bytes(evidence) == _canonical_bytes(actual),
            "exact owner composition differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(actual["summary"]),
        }

    return _normalize(run)


def encode_owner(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
