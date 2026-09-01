"""Exact seal for the small native helper reached by the class initializer.

The record deliberately reports only byte-level stores and a native-edge
witness.  It does not assign source-level container, ownership, allocation, or
success semantics to the helper.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_class_factory_chain import (
    NativeLuaClassFactoryChainError,
    _validated_graphs,
)
from src.observatory.native_lua_class_initializer_chain import (
    ANALYSIS_KIND as CLASS_INITIALIZER_ANALYSIS_KIND,
    NativeLuaClassInitializerChainError,
)
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError,
    _REGISTER_NAMES,
    _build_function_records,
    _canonical_bytes,
    _canonical_sha256,
    _direct_call_records,
    _expected_point_record,
    _graph_call_r32_audit,
    _helper_targets,
    _native_edges,
    _source_identity,
    _expected_reference_scan as _class_return_expected_reference_scan,
    _whole_atlas_reference_scan,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError,
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _decode_range,
    _exact_keys,
    _hex,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_CALL_ANALYSIS_KIND,
    SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
    validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_lua_property_factory_chain import NativeLuaPropertyFactoryChainError
from src.observatory.native_lua_super_rebinding import NativeLuaSuperRebindingError
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_self_linked_record_helper_chain"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS_SHA256 = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT_SHA256 = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_INITIALIZER_SHA256 = "799ab272966a317f27c0fbaf25df7d47821650a6f5e0b1a914c98eb40dcfece9"
_ENTRY = 0x0007C600
_INITIALIZER_ENTRY = 0x002EACF0


class NativeSelfLinkedRecordHelperChainError(RuntimeError):
    """Raised when the reviewed native helper profile cannot be reproduced."""


def _point(role: str, rva: int, encoded: str, **meaning: Any) -> dict[str, Any]:
    return {"role": role, "rva": rva, "encoded": bytes.fromhex(encoded), "api": None, "meaning": meaning}


_FUNCTION = {
    "role": "self_linked_record_helper",
    "entry_rva": _ENTRY,
    "body_size": 41,
    "body_sha256": "bf6d8eea868843a089fcc2b74af1426c5f71328fc018f028310cc48259f0dda1",
    "cfg_canonical_sha256": "ad0e30bf52543a6222f473c4a7f7740e9333fa05ad054256599f67d5bb35303b",
    "direct_calls": [],
    "staged_dispatches": [],
    "call_r32": {},
    "points": [
        _point("size_request_push", 0x0007C600, "6a18", operation="push_immediate", value=24),
        _point("native_size_request_edge", 0x0007C602, "e8d4ae2d00", operation="direct_call", target_rva="0x003574db"),
        _point("stack_cleanup", 0x0007C607, "83c404", operation="add_stack_pointer", value=4),
        _point("return_register_guard", 0x0007C60A, "85c0", operation="test", register="EAX"),
        _point("return_register_zero_branch", 0x0007C60C, "7402", operation="branch_if_zero", target_rva="0x0007c610"),
        _point("return_register_self_store", 0x0007C60E, "8900", operation="store_memory", base="EAX", field_offset=0, source="EAX"),
        _point("plus_4_address", 0x0007C610, "8d4804", operation="address", base="EAX", field_offset=4, destination="ECX"),
        _point("plus_4_guard", 0x0007C613, "85c9", operation="test", register="ECX"),
        _point("plus_4_zero_branch", 0x0007C615, "7402", operation="branch_if_zero", target_rva="0x0007c619"),
        _point("plus_4_return_store", 0x0007C617, "8901", operation="store_memory", base="ECX", field_offset=0, source="EAX"),
        _point("plus_8_address", 0x0007C619, "8d4808", operation="address", base="EAX", field_offset=8, destination="ECX"),
        _point("plus_8_guard", 0x0007C61C, "85c9", operation="test", register="ECX"),
        _point("plus_8_zero_branch", 0x0007C61E, "7402", operation="branch_if_zero", target_rva="0x0007c622"),
        _point("plus_8_return_store", 0x0007C620, "8901", operation="store_memory", base="ECX", field_offset=0, source="EAX"),
        _point("plus_0c_word_write", 0x0007C622, "66c7400c0101", operation="store_memory_immediate", base="EAX", field_offset=12, value="0x0101", width_bytes=2),
        _point("return", 0x0007C628, "c3", operation="return", register="EAX"),
    ],
    "semantic_facts": {
        "requested_size_bytes": 24,
        "conditional_store_guards": ["EAX", "EAX_plus_4", "EAX_plus_8"],
        "stores": {"0x0": "EAX", "0x4": "EAX", "0x8": "EAX", "0xc": "0x0101_word"},
        "return_register": "EAX",
        "source_semantic_names_assigned": False,
        "runtime_or_success_claimed": False,
    },
}

_PROFILE = {
    "executable_sha256": _EXE_SHA256,
    "functions": [_FUNCTION],
    "literals": [],
    "native_edges": [{
        "role": "symbol_labeled_native_size_request_edge", "instruction_rva": 0x0007C602,
        "source_entry_rva": _ENTRY, "target_entry_rva": 0x003574DB,
        "encoded": "e8d4ae2d00", "condition": None,
    }],
    "target_references": [
        {"instruction_rva": 0x0007A57D, "owner_entry_rva": 0x0007A460, "target_rva": _ENTRY, "encoded": "e87e200000", "operand_index": 0},
        {"instruction_rva": 0x0009C521, "owner_entry_rva": 0x0009C420, "target_rva": _ENTRY, "encoded": "e8da00feff", "operand_index": 0},
        {"instruction_rva": 0x0009D70D, "owner_entry_rva": 0x0009D6D0, "target_rva": _ENTRY, "encoded": "e8eeeefdff", "operand_index": 0},
        {"instruction_rva": 0x002E6A64, "owner_entry_rva": 0x002E6900, "target_rva": _ENTRY, "encoded": "e8975bd9ff", "operand_index": 0},
        {"instruction_rva": 0x002E77E3, "owner_entry_rva": 0x002E7790, "target_rva": _ENTRY, "encoded": "e8184ed9ff", "operand_index": 0},
        {"instruction_rva": 0x002E8D99, "owner_entry_rva": 0x002E8D20, "target_rva": _ENTRY, "encoded": "e86238d9ff", "operand_index": 0},
        {"instruction_rva": 0x002EAB1C, "owner_entry_rva": 0x002EAA80, "target_rva": _ENTRY, "encoded": "e8df1ad9ff", "operand_index": 0},
        {"instruction_rva": 0x002EAD8B, "owner_entry_rva": _INITIALIZER_ENTRY, "target_rva": _ENTRY, "encoded": "e87018d9ff", "operand_index": 0},
        {"instruction_rva": 0x002EBB48, "owner_entry_rva": 0x002EBB30, "target_rva": _ENTRY, "encoded": "e8b30ad9ff", "operand_index": 0},
    ],
}

_CALLER_WINDOWS = [
    (0x7A460, 0x7A569, "c70570c78b0000000000", 0x7A573, "c70574c78b0000000000", 0x7A57D, "e87e200000", 0x7A582, "a370c78b00", 0),
    (0x9C420, 0x9C514, "c70600000000", 0x9C51A, "c7460400000000", 0x9C521, "e8da00feff", 0x9C526, "8906", 0),
    (0x9D6D0, 0x9D700, "c70600000000", 0x9D706, "c7460400000000", 0x9D70D, "e8eeeefdff", 0x9D712, "8906", 0),
    (0x2E6900, 0x2E6A57, "c70000000000", 0x2E6A5D, "c7400400000000", 0x2E6A64, "e8975bd9ff", 0x2E6A6C, "8901", 1),
    (0x2E7790, 0x2E77D6, "c70600000000", 0x2E77DC, "c7460400000000", 0x2E77E3, "e8184ed9ff", 0x2E77E8, "8906", 0),
    (0x2E8D20, 0x2E8D85, "c705b0918d0000000000", 0x2E8D8F, "c705b4918d0000000000", 0x2E8D99, "e86238d9ff", 0x2E8DA3, "a3b0918d00", 1),
    (0x2EAA80, 0x2EAB0F, "c70600000000", 0x2EAB15, "c7460400000000", 0x2EAB1C, "e8df1ad9ff", 0x2EAB23, "8906", 1),
    (_INITIALIZER_ENTRY, 0x2EAD7E, "c70600000000", 0x2EAD84, "c7460400000000", 0x2EAD8B, "e87018d9ff", 0x2EAD92, "8906", 1),
    (0x2EBB30, 0x2EBB3B, "c70700000000", 0x2EBB41, "c7470400000000", 0x2EBB48, "e8b30ad9ff", 0x2EBB52, "8907", 2),
]

_METHOD = {
    "accepted_chain": "One canonical-pinned class-initializer opaque edge is joined to one exact native helper body, selected offset-only stores, one symbol-labeled native edge, and a complete all-operand atlas reference partition.",
    "native_abi_premise": "The reported return-register and conditional-store facts are syntactic x86 evidence; no runtime outcome is inferred.",
    "structural_boundary": "PE-free validation reconstructs every finite prerequisite, body, CFG, point, edge, and reference record. Exact bytes and all-atlas operand traversal require an exact PE rebuild.",
    "not_claimed": [
        "runtime reachability, invocation, order, frequency, state continuity, allocation success, throw behavior, or successful calls",
        "tree, container, sentinel, ownership, lifetime, allocation, or source-level type semantics",
        "semantic behavior of the symbol-labeled native callee",
        "behavior of the eight reference-only callers or arbitrary callee memory",
        "computed, indirect, data, un-atlased, or Lua-side consumers or references",
    ],
}


def _facts_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    result = _source_identity(value, "pe_ghidra_program_facts", _FACTS_SHA256, "program facts")
    summary = _mapping(value.get("summary"), "program facts summary")
    return {**result, "function_count": summary.get("function_count"), "body_range_count": summary.get("body_range_count"), "function_body_bytes": summary.get("function_body_bytes")}


def _direct_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    return _source_identity(value, DIRECT_CALL_ANALYSIS_KIND, _DIRECT_SHA256, "direct-call census")


def _initializer_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    return _source_identity(value, CLASS_INITIALIZER_ANALYSIS_KIND, _INITIALIZER_SHA256, "class initializer")


def _json_equal(left: Any, right: Any) -> bool:
    """Compare validated JSON values without Python's bool/int coercion."""

    return _canonical_bytes(left) == _canonical_bytes(right)


def _preflight(initializer: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    identity = _mapping(facts.get("identity"), "program facts identity")
    if identity.get("executable_sha256") != _EXE_SHA256:
        raise NativeSelfLinkedRecordHelperChainError("program facts have no reviewed self-linked helper profile")
    for label, value in (("class initializer", initializer), ("direct census", direct)):
        if not _json_equal(value.get("build_identity"), dict(identity)):
            raise NativeSelfLinkedRecordHelperChainError(f"{label} build identity differs from program facts")
    return _facts_identity(facts), _direct_identity(direct), _initializer_identity(initializer)


def _initializer_opaque_edge(initializer: Mapping[str, Any]) -> list[dict[str, Any]]:
    matches = []
    for raw in _array(initializer.get("native_edges"), "initializer native edges"):
        edge = _mapping(raw, "initializer native edge")
        if _rva(edge.get("source_entry_rva"), "initializer edge source") == _INITIALIZER_ENTRY and _rva(edge.get("target_entry_rva"), "initializer edge target") == _ENTRY:
            matches.append(dict(edge))
    if len(matches) != 1 or matches[0].get("role") != "opaque_native_helper_edge":
        raise NativeSelfLinkedRecordHelperChainError("class initializer lacks the exact opaque helper edge")
    return matches


def _decoder_contract() -> dict[str, Any]:
    return {"name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION, "architecture": "x86", "mode_bits": 32, "operand_classes": ["absolute_memory", "immediate"], "cfg_register_write_fields": ["writes_ebx", "writes_esi", "writes_edi", "writes_esp"], "register_call_encoding_audit": [{"register": name, "encoding": f"ff{0xd0 + index:02x}"} for index, name in enumerate(_REGISTER_NAMES)]}


def _reference_scan(scan: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(_mapping(scan, "reference scan"))
    aggregates = dict(_mapping(normalized.get("aggregates"), "reference aggregates"))
    for key in ("returned_callback_reference_count", "alternate_owner_reference_count"):
        aggregates.pop(key, None)
    normalized["aggregates"] = aggregates
    return normalized


def _window_instruction(role: str, rva: int, encoded_hex: str, **meaning: Any) -> dict[str, Any]:
    encoded = bytes.fromhex(encoded_hex)
    return {"role": role, "rva": _hex(rva), "size": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest(), "meaning": meaning}


def _expected_caller_grammar(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions = _atlas_functions(facts)
    witnesses = []
    for owner, zero0_rva, zero0, zero4_rva, zero4, call_rva, call, store_rva, store, between in _CALLER_WINDOWS:
        function = functions.get(owner)
        if function is None:
            raise NativeSelfLinkedRecordHelperChainError("caller grammar owner is absent from atlas")
        witnesses.append({
            "owner_entry_rva": _hex(owner), "owner_atlas_record_sha256": atlas_record_sha256(function),
            "zero_offset_0": _window_instruction("zero_offset_0", zero0_rva, zero0, operation="store_memory_immediate", relative_offset=0, value=0),
            "zero_offset_4": _window_instruction("zero_offset_4", zero4_rva, zero4, operation="store_memory_immediate", relative_offset=4, value=0),
            "helper_call": _window_instruction("helper_call", call_rva, call, operation="direct_call", target_rva=_hex(_ENTRY)),
            "return_to_offset_0": _window_instruction("return_to_offset_0", store_rva, store, operation="store_memory", relative_offset=0, source="EAX"),
            "zero_pair_and_call_are_contiguous_decoded_instructions": True,
            "call_to_return_store_intervening_instruction_count": between,
            "caller_body_or_cfg_sealed": False,
        })
    return witnesses


def _caller_grammar_witnesses(data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    expected = _expected_caller_grammar(facts)
    for raw in expected:
        points = [raw["zero_offset_0"], raw["zero_offset_4"], raw["helper_call"], raw["return_to_offset_0"]]
        first = _rva(points[0]["rva"], "caller grammar first RVA")
        last = _rva(points[-1]["rva"], "caller grammar last RVA") + points[-1]["size"]
        decoded = _decode_range(data, image, first, last - first, decoder)
        by_rva = {instruction.address - image.image_base: bytes(instruction.bytes) for instruction in decoded}
        decoded_rvas = [instruction.address - image.image_base for instruction in decoded]
        point_rvas = [_rva(point["rva"], "caller grammar point RVA") for point in points]
        if [index for index, rva in enumerate(decoded_rvas) if rva in point_rvas[:3]] != list(range(3)):
            raise NativeSelfLinkedRecordHelperChainError("zero pair and helper call no longer form a contiguous decoded window")
        call_index, store_index = decoded_rvas.index(point_rvas[2]), decoded_rvas.index(point_rvas[3])
        if store_index - call_index - 1 != raw["call_to_return_store_intervening_instruction_count"]:
            raise NativeSelfLinkedRecordHelperChainError("helper-call return-store adjacency changed")
        for point in points:
            actual = by_rva.get(_rva(point["rva"], "caller grammar point RVA"))
            if actual is None or len(actual) != point["size"] or hashlib.sha256(actual).hexdigest() != point["sha256"]:
                raise NativeSelfLinkedRecordHelperChainError("caller grammar instruction changed")
    return expected


def _expected_reference_scan(facts: Mapping[str, Any], direct: Mapping[str, Any]) -> dict[str, Any]:
    return _reference_scan(_class_return_expected_reference_scan(facts, direct, _PROFILE))


def _whole_scan(data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any], direct: Mapping[str, Any]) -> dict[str, Any]:
    return _reference_scan(_whole_atlas_reference_scan(data, image, decoder, facts, direct, _PROFILE))


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    body = _array(result.get("function_bodies"), "function bodies")[0]
    graphs = _array(result.get("control_flow_graphs"), "control flow graphs")
    aggregate = _mapping(_mapping(result.get("whole_atlas_reference_scan"), "reference scan").get("aggregates"), "reference aggregates")
    witnesses = _array(result.get("caller_grammar_witnesses"), "caller grammar witnesses")
    return {"reviewed_helper_count": 1, "reviewed_helper_bytes": body["body_size"], "sealed_control_flow_graph_count": len(graphs), "sealed_control_flow_graph_node_count": sum(graph["node_count"] for graph in graphs), "sealed_control_flow_graph_edge_count": sum(graph["edge_count"] for graph in graphs), "direct_lua_call_count": 0, "staged_lua_dispatch_count": 0, "staged_lua_call_count": 0, "total_lua_call_count": 0, "call_r32_count": sum(len(item["call_rvas"]) for item in body["call_r32_audit"]), "literal_count": 0, "selected_native_edge_count": len(_array(result.get("native_edges"), "native edges")), "unique_native_edge_target_count": len({edge["target_entry_rva"] for edge in _array(result.get("native_edges"), "native edges")}), "helper_target_count": len(_array(result.get("helper_targets"), "helper targets")), "class_initializer_opaque_edge_count": len(_array(result.get("initializer_opaque_edge"), "initializer opaque edge")), "caller_grammar_witness_count": len(witnesses), "caller_grammar_zero_pair_count": len(witnesses), "caller_grammar_return_store_count": len(witnesses), "target_reference_count": aggregate["reference_count"], "target_reference_direct_call_count": aggregate["direct_call_count"], "target_reference_comparison_count": aggregate["comparison_count"], "target_reference_other_address_count": aggregate["other_address_count"], "target_reference_memory_operand_count": aggregate["memory_operand_count"], "target_reference_owner_count": aggregate["owner_count"], "schema_violations": 0}


def _build(executable: Path, initializer: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    for value, label in ((initializer, "class initializer"), (direct, "direct calls"), (facts, "program facts"), (inventory, "inventory")):
        _validate_json_tree(value, label)
    receipt = validate_native_lua_direct_call_census(executable, direct, facts, inventory=inventory)
    if receipt.get("status") != "verified" or receipt.get("evidence_sha256") != _DIRECT_SHA256:
        raise NativeSelfLinkedRecordHelperChainError("direct-call prerequisite exact verification failed")
    atlas, direct_identity, initializer_identity = _preflight(initializer, direct, facts)
    data, image, digest = _load_executable(executable)
    identity = _mapping(facts.get("identity"), "program facts identity")
    if digest != _EXE_SHA256 or identity.get("executable_size") != len(data) or identity.get("architecture") != image.architecture:
        raise NativeSelfLinkedRecordHelperChainError("executable identity differs from reviewed program facts")
    decoder, _ = _decoder()
    bodies, graphs = _build_function_records(data, image, decoder, facts, direct, _PROFILE)
    result = {"schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND, "build_identity": dict(identity), "atlas": atlas, "direct_call_census": direct_identity, "class_initializer_chain": initializer_identity, "decoder": _decoder_contract(), "initializer_opaque_edge": _initializer_opaque_edge(initializer), "helper_targets": _helper_targets(bodies, _PROFILE, image.image_base), "literals": [], "function_bodies": bodies, "control_flow_graphs": graphs, "native_edges": _native_edges(_PROFILE, facts), "caller_grammar_witnesses": _caller_grammar_witnesses(data, image, decoder, facts), "whole_atlas_reference_scan": _whole_scan(data, image, decoder, facts, direct), "method": _METHOD}
    result["summary"] = _summary(result)
    _assert_publication_safe(result)
    if _load_executable(executable)[2] != digest:
        raise NativeSelfLinkedRecordHelperChainError("executable changed during exact rebuild")
    validate_native_self_linked_record_helper_chain_structure(result, initializer, direct, facts)
    return result


def build_native_self_linked_record_helper_chain(executable: Path, class_initializer: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return _build(executable, class_initializer, direct_calls, program_facts, inventory=inventory)
    except NativeSelfLinkedRecordHelperChainError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassFactoryChainError, NativeLuaClassInitializerChainError, NativeLuaClassReturnHelperChainError, NativeLuaSuperRebindingError, NativeLuaPropertyFactoryChainError, PEAnchorError, OSError) as exc:
        raise NativeSelfLinkedRecordHelperChainError(str(exc)) from exc


def validate_native_self_linked_record_helper_chain_structure(evidence: Mapping[str, Any], class_initializer: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any]) -> dict[str, Any]:
    try:
        for value, label in ((evidence, "evidence"), (class_initializer, "class initializer"), (direct_calls, "direct calls"), (program_facts, "program facts")):
            _validate_json_tree(value, label)
        receipt = validate_native_lua_direct_call_structure(direct_calls, program_facts)
        if receipt.get("status") != "structurally_verified" or receipt.get("evidence_sha256") != _DIRECT_SHA256:
            raise NativeSelfLinkedRecordHelperChainError("direct-call structural prerequisite failed")
        atlas, direct_identity, initializer_identity = _preflight(class_initializer, direct_calls, program_facts)
        identity = dict(_mapping(program_facts.get("identity"), "program facts identity"))
        evidence = _mapping(evidence, "evidence")
        _exact_keys(evidence, {"schema_version", "analysis_kind", "build_identity", "atlas", "direct_call_census", "class_initializer_chain", "decoder", "initializer_opaque_edge", "helper_targets", "literals", "function_bodies", "control_flow_graphs", "native_edges", "caller_grammar_witnesses", "whole_atlas_reference_scan", "method", "summary"}, "evidence")
        if type(evidence.get("schema_version")) is not int or evidence.get("schema_version") != SCHEMA_VERSION or type(evidence.get("analysis_kind")) is not str or evidence.get("analysis_kind") != ANALYSIS_KIND:
            raise NativeSelfLinkedRecordHelperChainError("unsupported helper schema or kind")
        if not all((
            _json_equal(evidence.get("build_identity"), identity),
            _json_equal(evidence.get("atlas"), atlas),
            _json_equal(evidence.get("direct_call_census"), direct_identity),
            _json_equal(evidence.get("class_initializer_chain"), initializer_identity),
        )):
            raise NativeSelfLinkedRecordHelperChainError("prerequisite identity differs")
        if not all((
            _json_equal(evidence.get("decoder"), _decoder_contract()),
            _json_equal(evidence.get("method"), _METHOD),
            _json_equal(evidence.get("initializer_opaque_edge"), _initializer_opaque_edge(class_initializer)),
        )):
            raise NativeSelfLinkedRecordHelperChainError("contract or initializer edge differs")
        if not _json_equal(evidence.get("literals"), []):
            raise NativeSelfLinkedRecordHelperChainError("helper literal partition differs")
        functions = _atlas_functions(program_facts)
        function = functions.get(_ENTRY)
        bodies = _array(evidence.get("function_bodies"), "function bodies")
        if len(bodies) != 1 or not isinstance(function, Mapping) or function.get("body_size") != _FUNCTION["body_size"] or function.get("body_sha256") != _FUNCTION["body_sha256"]:
            raise NativeSelfLinkedRecordHelperChainError("helper body partition differs")
        body = _mapping(bodies[0], "helper body")
        _exact_keys(body, {"role", "entry_rva", "atlas_record_sha256", "body_size", "body_sha256", "range_start_rva", "range_size", "control_flow_graph_canonical_sha256", "reviewed_points", "direct_lua_calls", "staged_lua_dispatches", "call_r32_audit", "register_call_partition_complete", "semantic_facts"}, "helper body")
        expected_body = {"role": _FUNCTION["role"], "entry_rva": "0x0007c600", "atlas_record_sha256": atlas_record_sha256(function), "body_size": _FUNCTION["body_size"], "body_sha256": _FUNCTION["body_sha256"], "range_start_rva": "0x0007c600", "range_size": _FUNCTION["body_size"], "control_flow_graph_canonical_sha256": _FUNCTION["cfg_canonical_sha256"], "reviewed_points": [_expected_point_record(item) for item in _FUNCTION["points"]], "direct_lua_calls": _direct_call_records(_FUNCTION, direct_calls), "staged_lua_dispatches": [], "call_r32_audit": [{"register": r, "call_rvas": []} for r in _REGISTER_NAMES], "register_call_partition_complete": True, "semantic_facts": _FUNCTION["semantic_facts"]}
        for key, expected in expected_body.items():
            if not _json_equal(body.get(key), expected):
                raise NativeSelfLinkedRecordHelperChainError(f"helper body {key} differs")
        try:
            graph_map = _validated_graphs({"control_flow_graphs": evidence.get("control_flow_graphs")}, functions)
        except NativeLuaClassFactoryChainError as exc:
            raise NativeSelfLinkedRecordHelperChainError(f"helper CFG validation failed: {exc}") from exc
        if set(graph_map) != {_ENTRY}:
            raise NativeSelfLinkedRecordHelperChainError("helper CFG partition differs")
        graph, nodes, _ = graph_map[_ENTRY]
        if _canonical_sha256(graph) != _FUNCTION["cfg_canonical_sha256"]:
            raise NativeSelfLinkedRecordHelperChainError("helper CFG identity differs")
        for point in body["reviewed_points"]:
            node = nodes.get(_rva(point["rva"], "reviewed point RVA"))
            if node is None or (node.get("size"), node.get("sha256")) != (point["size"], point["sha256"]):
                raise NativeSelfLinkedRecordHelperChainError("reviewed point does not join helper CFG")
        if not _json_equal(body.get("call_r32_audit"), _graph_call_r32_audit(nodes)):
            raise NativeSelfLinkedRecordHelperChainError("call-r32 graph partition differs")
        image_base = _rva(_mapping(program_facts.get("ghidra"), "program facts ghidra").get("image_base"), "image base")
        if not _json_equal(evidence.get("helper_targets"), _helper_targets([body], _PROFILE, image_base)):
            raise NativeSelfLinkedRecordHelperChainError("helper target records differ")
        edges = _native_edges(_PROFILE, program_facts)
        if not _json_equal(evidence.get("native_edges"), edges):
            raise NativeSelfLinkedRecordHelperChainError("native edge partition differs")
        for edge in edges:
            instruction = _mapping(edge.get("instruction"), "native edge instruction")
            node = nodes.get(_rva(instruction.get("rva"), "native edge RVA"))
            if node is None or (node.get("size"), node.get("sha256")) != (instruction["size"], instruction["sha256"]):
                raise NativeSelfLinkedRecordHelperChainError("native edge does not join helper CFG")
        if not _json_equal(evidence.get("caller_grammar_witnesses"), _expected_caller_grammar(program_facts)):
            raise NativeSelfLinkedRecordHelperChainError("caller grammar witnesses differ")
        if not _json_equal(evidence.get("whole_atlas_reference_scan"), _expected_reference_scan(program_facts, direct_calls)):
            raise NativeSelfLinkedRecordHelperChainError("reference partition differs")
        if not _json_equal(evidence.get("summary"), _summary(evidence)):
            raise NativeSelfLinkedRecordHelperChainError("summary differs")
        _assert_publication_safe(evidence)
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": STRUCTURE_VERIFICATION_KIND, "status": "structurally_verified", "build_identity": identity, "evidence_sha256": _canonical_sha256(evidence), "summary": dict(evidence["summary"])}
    except NativeSelfLinkedRecordHelperChainError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassFactoryChainError, NativeLuaClassInitializerChainError, NativeLuaClassReturnHelperChainError, NativeLuaSuperRebindingError, NativeLuaPropertyFactoryChainError) as exc:
        raise NativeSelfLinkedRecordHelperChainError(str(exc)) from exc


def validate_native_self_linked_record_helper_chain(executable: Path, evidence: Mapping[str, Any], class_initializer: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        _validate_json_tree(evidence, "evidence")
        rebuilt = build_native_self_linked_record_helper_chain(executable, class_initializer, direct_calls, program_facts, inventory=inventory)
        if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
            raise NativeSelfLinkedRecordHelperChainError("self-linked record helper evidence differs from exact rebuild")
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": VERIFICATION_KIND, "status": "verified", "build_identity": dict(rebuilt["build_identity"]), "evidence_sha256": _canonical_sha256(rebuilt), "summary": dict(rebuilt["summary"])}
    except NativeSelfLinkedRecordHelperChainError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassFactoryChainError, NativeLuaClassInitializerChainError, NativeLuaClassReturnHelperChainError, NativeLuaSuperRebindingError, NativeLuaPropertyFactoryChainError, PEAnchorError, OSError) as exc:
        raise NativeSelfLinkedRecordHelperChainError(str(exc)) from exc


def encode_native_self_linked_record_helper_chain(value: Mapping[str, Any]) -> str:
    try:
        _validate_json_tree(value)
        return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    except NativeLuaCClosurePublicationError as exc:
        raise NativeSelfLinkedRecordHelperChainError(str(exc)) from exc
