"""Exact, deliberately opaque static boundary for the native assertion helper."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_class_factory_chain import NativeLuaClassFactoryChainError, _validated_graphs
from src.observatory.native_lua_class_initializer_chain import ANALYSIS_KIND as CLASS_INITIALIZER_ANALYSIS_KIND, NativeLuaClassInitializerChainError
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError, _REGISTER_NAMES, _build_function_records,
    _canonical_bytes, _canonical_sha256, _expected_point_record,
    _expected_reference_scan as _base_expected_reference_scan,
    _normalized_declared_edge, _source_identity,
    _whole_atlas_reference_scan as _base_whole_atlas_reference_scan,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError, _array, _assert_publication_safe, _atlas_functions,
    _decode_range, _exact_keys, _hex, _mapping, _rva, _validate_json_tree,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_CALL_ANALYSIS_KIND, SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError, _decoder, _load_executable,
    validate_native_lua_direct_call_census, validate_native_lua_direct_call_structure,
)
from src.observatory.native_lua_property_factory_chain import NativeLuaPropertyFactoryChainError
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_assertion_helper_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS_SHA256 = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT_SHA256 = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_INITIALIZER_SHA256 = "799ab272966a317f27c0fbaf25df7d47821650a6f5e0b1a914c98eb40dcfece9"
_ENTRY, _INITIALIZER_ENTRY = 0x00379CC2, 0x002EACF0
_BODY_SHA256 = "1f55c49efcf686fecf491fc4ac23411e373af8d7c38c0f076b070a417e7ddf13"
_ATLAS_SHA256 = "0103f8a5b002b70e110ee0031538326b0eeb59da2cc798607a62a5603e04ac29"
_CFG_SHA256 = "95575ce84f0cfec966300ed6b457a5b148126f334fede1bc5c4459a895f095ed"
PE_SECTION_WRITABLE = 0x80000000

_POINTS = (
    ("hotpatch_nop", 0x379CC2, "8bff", {"operation": "register_copy", "destination": "EDI", "source": "EDI"}),
    ("frame_push", 0x379CC4, "55", {"operation": "push_register", "register": "EBP"}),
    ("frame_establish", 0x379CC5, "8bec", {"operation": "register_copy", "destination": "EBP", "source": "ESP"}),
    ("esi_push", 0x379CC7, "56", {"operation": "push_register", "register": "ESI"}),
    ("stack_relative_load", 0x379CC8, "8b7504", {"operation": "load_stack_relative", "base": "EBP", "offset": 4, "destination": "ESI"}),
    ("scalar_three", 0x379CCB, "6a03", {"operation": "push_immediate", "value": 3}),
    ("native_edge_one", 0x379CCD, "e8c0460100", {"operation": "direct_call", "target_rva": "0x0038e392"}),
    ("stack_pop", 0x379CD2, "59", {"operation": "pop_register", "register": "ECX"}),
    ("result_one_compare", 0x379CD3, "83f801", {"operation": "compare_immediate", "register": "EAX", "value": 1}),
    ("result_one_branch", 0x379CD6, "7423", {"operation": "branch_if_equal", "target_rva": "0x00379cfb"}),
    ("result_zero_test", 0x379CD8, "85c0", {"operation": "test_register", "register": "EAX"}),
    ("result_nonzero_branch", 0x379CDA, "750a", {"operation": "branch_if_not_equal", "target_rva": "0x00379ce6"}),
    ("native_edge_two", 0x379CDC, "e8be2b0100", {"operation": "direct_call", "target_rva": "0x0038c89f"}),
    ("result_two_compare", 0x379CE1, "83f801", {"operation": "compare_immediate", "register": "EAX", "value": 1}),
    ("result_two_branch", 0x379CE4, "7415", {"operation": "branch_if_equal", "target_rva": "0x00379cfb"}),
    ("argument_four_push", 0x379CE6, "56", {"operation": "push_register", "register": "ESI"}),
    ("argument_three_push", 0x379CE7, "ff7510", {"operation": "push_stack_relative", "base": "EBP", "offset": 16}),
    ("argument_two_push", 0x379CEA, "ff750c", {"operation": "push_stack_relative", "base": "EBP", "offset": 12}),
    ("argument_one_push", 0x379CED, "ff7508", {"operation": "push_stack_relative", "base": "EBP", "offset": 8}),
    ("native_edge_three", 0x379CF0, "e85bf8ffff", {"operation": "direct_call", "target_rva": "0x00379550"}),
    ("stack_cleanup", 0x379CF5, "83c410", {"operation": "add_stack_pointer", "value": 16}),
    ("esi_pop", 0x379CF8, "5e", {"operation": "pop_register", "register": "ESI"}),
    ("frame_pop", 0x379CF9, "5d", {"operation": "pop_register", "register": "EBP"}),
    ("return", 0x379CFA, "c3", {"operation": "return"}),
    ("alternate_argument_three_push", 0x379CFB, "ff7510", {"operation": "push_stack_relative", "base": "EBP", "offset": 16}),
    ("alternate_argument_two_push", 0x379CFE, "ff750c", {"operation": "push_stack_relative", "base": "EBP", "offset": 12}),
    ("alternate_argument_one_push", 0x379D01, "ff7508", {"operation": "push_stack_relative", "base": "EBP", "offset": 8}),
    ("native_edge_four", 0x379D04, "e828feffff", {"operation": "direct_call", "target_rva": "0x00379b31"}),
    ("post_call_trap", 0x379D09, "cc", {"operation": "trap", "termination_proof": False}),
)
_NATIVE_EDGES = tuple((rva, encoded, _rva(meaning["target_rva"], "native target")) for _, rva, encoded, meaning in _POINTS if meaning["operation"] == "direct_call")
_WINDOW = (
    ("classes_sentinel_compare", 0x2EAE64, "83780cfe", {"operation": "compare", "base": "EAX", "field_offset": 12, "value": -2}),
    ("classes_sentinel_branch", 0x2EAE68, "7517", {"operation": "branch_if_not_equal", "target_rva": "0x002eae81"}),
    ("assertion_line_push", 0x2EAE6A, "6a60", {"operation": "push_immediate", "value": 96}),
    ("assertion_source_pointer", 0x2EAE6C, "6880c68300", {"operation": "push_nonwritable_rdata_pointer", "literal_rva": "0x0043c680"}),
    ("assertion_condition_pointer", 0x2EAE71, "68b0c68300", {"operation": "push_nonwritable_rdata_pointer", "literal_rva": "0x0043c6b0"}),
    ("registry_classes_assertion", 0x2EAE76, "e847ee0800", {"operation": "direct_call", "target_rva": "0x00379cc2"}),
)
_SEMANTIC_FACTS = {"callee_behavior_opaque": True, "direct_lua_calls_absent": True, "staged_lua_dispatches_absent": True, "register_r32_calls_absent": True, "int3_after_last_direct_call_does_not_prove_termination": True, "source_semantic_names_assigned": False}
_METHOD = {"structural_boundary": "PE-free validation reconstructs only finite canonical-pinned records; exact bytes, operand traversal, and literal-section checks require an exact PE rebuild.", "not_claimed": ["runtime reachability, invocation, order, or frequency", "argument validity", "dialog or display behavior", "CRT identity or ownership", "normal return, abort, or termination", "source equivalence", "computed, indirect, data, un-atlased, or Lua-side references"]}


class NativeAssertionHelperStaticBoundaryError(RuntimeError):
    """Raised when the reviewed static boundary cannot be reproduced exactly."""


def _json_equal(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _facts_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    result = _source_identity(value, "pe_ghidra_program_facts", _FACTS_SHA256, "program facts")
    summary = _mapping(value.get("summary"), "program facts summary")
    return {**result, "function_count": summary.get("function_count"), "body_range_count": summary.get("body_range_count"), "function_body_bytes": summary.get("function_body_bytes")}


def _preflight(initializer: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    identity = _mapping(facts.get("identity"), "program facts identity")
    if identity.get("executable_sha256") != _EXE_SHA256:
        raise NativeAssertionHelperStaticBoundaryError("program facts are not the reviewed assertion profile")
    for label, value in (("class initializer", initializer), ("direct-call census", direct)):
        if not _json_equal(value.get("build_identity"), dict(identity)):
            raise NativeAssertionHelperStaticBoundaryError(f"{label} build identity differs")
    return (_facts_identity(facts), _source_identity(direct, DIRECT_CALL_ANALYSIS_KIND, _DIRECT_SHA256, "direct-call census"), _source_identity(initializer, CLASS_INITIALIZER_ANALYSIS_KIND, _INITIALIZER_SHA256, "class initializer"))


def _profile(facts: Mapping[str, Any]) -> dict[str, Any]:
    refs = []
    for raw in _array(facts.get("ghidra_declared_direct_calls"), "program facts direct calls"):
        edge = _mapping(raw, "program facts direct call")
        if _rva(edge.get("target_entry_rva"), "direct-call target") == _ENTRY:
            site = _rva(edge.get("instruction_rva"), "direct-call site")
            target = _rva(edge.get("target_rva"), "direct-call target RVA")
            owner = _rva(edge.get("source_entry_rva"), "direct-call owner")
            if target != _ENTRY:
                raise NativeAssertionHelperStaticBoundaryError("target entry and target RVA differ")
            refs.append({"instruction_rva": site, "owner_entry_rva": owner, "target_rva": target, "encoded": (b"\xe8" + int(target - (site + 5)).to_bytes(4, "little", signed=True)).hex(), "operand_index": 0})
    refs.sort(key=lambda item: item["instruction_rva"])
    if len(refs) != 881 or len({item["owner_entry_rva"] for item in refs}) != 660:
        raise NativeAssertionHelperStaticBoundaryError("assertion direct-call census differs")
    return {"executable_sha256": _EXE_SHA256, "functions": [{"role": "native_assertion_helper", "entry_rva": _ENTRY, "body_size": 72, "body_sha256": _BODY_SHA256, "cfg_canonical_sha256": _CFG_SHA256, "direct_calls": [], "staged_dispatches": [], "call_r32": {}, "points": [{"role": role, "rva": rva, "encoded": bytes.fromhex(encoded), "api": None, "meaning": meaning} for role, rva, encoded, meaning in _POINTS], "semantic_facts": _SEMANTIC_FACTS}], "literals": [], "native_edges": [], "target_references": refs}


def _reference_scan(scan: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(_mapping(scan, "reference scan"))
    aggregates = dict(_mapping(result.get("aggregates"), "reference aggregates"))
    aggregates.pop("returned_callback_reference_count", None)
    aggregates.pop("alternate_owner_reference_count", None)
    result["aggregates"] = aggregates
    refs = _array(result.get("references"), "references")
    owners: dict[str, list[Mapping[str, Any]]] = {}
    for raw in refs:
        record = _mapping(raw, "reference")
        if record.get("instruction_size") != 5 or record.get("operand_index") != 0 or record.get("operand_class") != "immediate" or record.get("use_class") != "direct_call" or record.get("call_form") != "x86_relative_near_call_e8":
            raise NativeAssertionHelperStaticBoundaryError("non-E8, alternate-operand, or non-call target reference observed")
        if record.get("ghidra_declared_direct_edge") is None:
            raise NativeAssertionHelperStaticBoundaryError("target reference lacks Ghidra direct-edge join")
        owners.setdefault(record["owner_entry_rva"], []).append(record)
    if len(refs) != 881 or len(owners) != 660:
        raise NativeAssertionHelperStaticBoundaryError("whole-atlas target reference partition differs")
    result["owner_partition"] = [{"owner_entry_rva": owner, "owner_atlas_record_sha256": group[0]["owner_atlas_record_sha256"], "reference_count": len(group)} for owner, group in sorted(owners.items())]
    return result


def _expected_reference_scan(facts: Mapping[str, Any], direct: Mapping[str, Any]) -> dict[str, Any]:
    return _reference_scan(_base_expected_reference_scan(facts, direct, _profile(facts)))


def _whole_atlas_reference_scan(data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any], direct: Mapping[str, Any]) -> dict[str, Any]:
    observed = _reference_scan(_base_whole_atlas_reference_scan(data, image, decoder, facts, direct, _profile(facts)))
    if not _json_equal(observed, _expected_reference_scan(facts, direct)):
        raise NativeAssertionHelperStaticBoundaryError("PE-wide target reference traversal differs from declared partition")
    return observed


def _initializer_edge(initializer: Mapping[str, Any]) -> dict[str, Any]:
    matches = [dict(_mapping(raw, "initializer native edge")) for raw in _array(initializer.get("native_edges"), "initializer native edges") if _rva(_mapping(raw, "initializer native edge").get("source_entry_rva"), "edge source") == _INITIALIZER_ENTRY and _rva(_mapping(raw, "initializer native edge").get("target_entry_rva"), "edge target") == _ENTRY]
    if len(matches) != 1 or matches[0].get("role") != "registry_classes_assertion_edge":
        raise NativeAssertionHelperStaticBoundaryError("initializer lacks exact assertion edge")
    return matches[0]


def _window_records() -> list[dict[str, Any]]:
    return [{"role": role, "rva": _hex(rva), "size": len(bytes.fromhex(encoded)), "sha256": hashlib.sha256(bytes.fromhex(encoded)).hexdigest(), "meaning": meaning} for role, rva, encoded, meaning in _WINDOW]


def _verify_window(data: bytes, image: Any, decoder: Any) -> list[dict[str, Any]]:
    instructions = _decode_range(data, image, _WINDOW[0][1], 23, decoder)
    if len(instructions) != len(_WINDOW):
        raise NativeAssertionHelperStaticBoundaryError("initializer predecessor instruction partition differs")
    for instruction, (_, rva, encoded, meaning) in zip(instructions, _WINDOW, strict=True):
        if instruction.address - image.image_base != rva or bytes(instruction.bytes) != bytes.fromhex(encoded):
            raise NativeAssertionHelperStaticBoundaryError("initializer predecessor bytes differ")
        literal = meaning.get("literal_rva")
        if literal is not None:
            offset = image.rva_to_file_offset(_rva(literal, "literal RVA"))
            section = None if offset is None else image.section_for_offset(offset)
            if section is None or section.name != ".rdata" or section.characteristics & PE_SECTION_WRITABLE:
                raise NativeAssertionHelperStaticBoundaryError("assertion call-site pointer is not non-writable rdata")
    return _window_records()


def _native_edges(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions = _atlas_functions(facts)
    source = functions.get(_ENTRY)
    if source is None or atlas_record_sha256(source) != _ATLAS_SHA256 or source.get("body_size") != 72 or source.get("body_sha256") != _BODY_SHA256:
        raise NativeAssertionHelperStaticBoundaryError("assertion source atlas identity differs")
    declared = {_rva(_mapping(raw, "declared direct edge").get("instruction_rva"), "edge site"): _mapping(raw, "declared direct edge") for raw in _array(facts.get("ghidra_declared_direct_calls"), "declared direct edges")}
    result = []
    for site, encoded_hex, target in _NATIVE_EDGES:
        edge, target_function = declared.get(site), functions.get(target)
        if edge is None or target_function is None or _rva(edge.get("source_entry_rva"), "edge source") != _ENTRY or _rva(edge.get("target_entry_rva"), "edge target entry") != target or _rva(edge.get("target_rva"), "edge target RVA") != target:
            raise NativeAssertionHelperStaticBoundaryError("native edge Ghidra/atlas join differs")
        encoded = bytes.fromhex(encoded_hex)
        result.append({"role": "opaque_native_direct_edge", "source_entry_rva": _hex(_ENTRY), "source_atlas_record_sha256": _ATLAS_SHA256, "source_body_size": 72, "source_body_sha256": _BODY_SHA256, "instruction": {"rva": _hex(site), "size": 5, "sha256": hashlib.sha256(encoded).hexdigest()}, "target_entry_rva": _hex(target), "target_rva": _hex(target), "target_atlas_record_sha256": atlas_record_sha256(target_function), "target_body_size": target_function.get("body_size"), "target_body_sha256": target_function.get("body_sha256"), "ghidra_declared_direct_edge": _normalized_declared_edge(edge), "label_source": "analysis_or_default", "callee_behavior_opaque": True})
    return result


def _decoder_contract() -> dict[str, Any]:
    return {"name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION, "architecture": "x86", "mode_bits": 32, "sealed_instruction_count": 29, "register_call_encoding_audit": [{"register": register, "encoding": f"ff{0xd0 + index:02x}"} for index, register in enumerate(_REGISTER_NAMES)]}


def _expected_body(facts: Mapping[str, Any]) -> dict[str, Any]:
    function = _atlas_functions(facts).get(_ENTRY)
    if function is None:
        raise NativeAssertionHelperStaticBoundaryError("assertion helper absent from atlas")
    return {"role": "native_assertion_helper", "entry_rva": _hex(_ENTRY), "atlas_record_sha256": _ATLAS_SHA256, "body_size": 72, "body_sha256": _BODY_SHA256, "range_start_rva": _hex(_ENTRY), "range_size": 72, "control_flow_graph_canonical_sha256": _CFG_SHA256, "reviewed_points": [_expected_point_record({"role": role, "rva": rva, "encoded": bytes.fromhex(encoded), "api": None, "meaning": meaning}) for role, rva, encoded, meaning in _POINTS], "direct_lua_calls": [], "staged_lua_dispatches": [], "call_r32_audit": [{"register": name, "call_rvas": []} for name in _REGISTER_NAMES], "register_call_partition_complete": True, "semantic_facts": _SEMANTIC_FACTS}


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    scan = _mapping(result.get("whole_atlas_reference_scan"), "reference scan")
    aggregates = _mapping(scan.get("aggregates"), "reference aggregates")
    return {"reviewed_assertion_helper_count": 1, "reviewed_assertion_helper_bytes": 72, "sealed_instruction_count": 29, "sealed_control_flow_graph_count": 1, "sealed_control_flow_graph_node_count": 29, "sealed_control_flow_graph_edge_count": 30, "direct_lua_call_count": 0, "staged_lua_dispatch_count": 0, "call_r32_count": 0, "literal_count": 0, "native_edge_count": 4, "initializer_predecessor_window_count": 6, "target_reference_count": len(_array(scan.get("references"), "references")), "target_reference_direct_call_count": aggregates["direct_call_count"], "target_reference_comparison_count": aggregates["comparison_count"], "target_reference_other_address_count": aggregates["other_address_count"], "target_reference_memory_operand_count": aggregates["memory_operand_count"], "target_reference_owner_count": len(_array(scan.get("owner_partition"), "owner partition")), "schema_violations": 0}


def _build(executable: Path, initializer: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    for value, label in ((initializer, "class initializer"), (direct, "direct calls"), (facts, "program facts"), (inventory, "inventory")):
        _validate_json_tree(value, label)
    receipt = validate_native_lua_direct_call_census(executable, direct, facts, inventory=inventory)
    if receipt.get("status") != "verified" or receipt.get("evidence_sha256") != _DIRECT_SHA256:
        raise NativeAssertionHelperStaticBoundaryError("direct-call prerequisite exact verification failed")
    atlas, direct_identity, initializer_identity = _preflight(initializer, direct, facts)
    data, image, digest = _load_executable(executable)
    identity = _mapping(facts.get("identity"), "program facts identity")
    if digest != _EXE_SHA256 or identity.get("executable_size") != len(data) or identity.get("architecture") != image.architecture:
        raise NativeAssertionHelperStaticBoundaryError("executable identity, size, or architecture differs")
    decoder, _ = _decoder()
    profile = _profile(facts)
    bodies, graphs = _build_function_records(data, image, decoder, facts, direct, profile)
    result = {"schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND, "build_identity": dict(identity), "atlas": atlas, "direct_call_census": direct_identity, "class_initializer_chain": initializer_identity, "decoder": _decoder_contract(), "initializer_assertion_edge": _initializer_edge(initializer), "initializer_predecessor_window": _verify_window(data, image, decoder), "function_bodies": bodies, "control_flow_graphs": graphs, "native_edges": _native_edges(facts), "whole_atlas_reference_scan": _whole_atlas_reference_scan(data, image, decoder, facts, direct), "method": _METHOD}
    result["summary"] = _summary(result)
    _assert_publication_safe(result)
    if _load_executable(executable)[2] != digest:
        raise NativeAssertionHelperStaticBoundaryError("executable changed during exact rebuild")
    validate_native_assertion_helper_static_boundary_structure(result, initializer, direct, facts)
    return result


def build_native_assertion_helper_static_boundary(executable: Path, class_initializer: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return _build(executable, class_initializer, direct_calls, program_facts, inventory=inventory)
    except NativeAssertionHelperStaticBoundaryError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassFactoryChainError, NativeLuaClassInitializerChainError, NativeLuaClassReturnHelperChainError, NativeLuaPropertyFactoryChainError, PEAnchorError, OSError) as exc:
        raise NativeAssertionHelperStaticBoundaryError(str(exc)) from exc


def validate_native_assertion_helper_static_boundary_structure(evidence: Mapping[str, Any], class_initializer: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any]) -> dict[str, Any]:
    try:
        for value, label in ((evidence, "evidence"), (class_initializer, "class initializer"), (direct_calls, "direct calls"), (program_facts, "program facts")):
            _validate_json_tree(value, label)
        receipt = validate_native_lua_direct_call_structure(direct_calls, program_facts)
        if receipt.get("status") != "structurally_verified" or receipt.get("evidence_sha256") != _DIRECT_SHA256:
            raise NativeAssertionHelperStaticBoundaryError("direct-call structural prerequisite failed")
        atlas, direct_identity, initializer_identity = _preflight(class_initializer, direct_calls, program_facts)
        evidence = _mapping(evidence, "evidence")
        _exact_keys(evidence, {"schema_version", "analysis_kind", "build_identity", "atlas", "direct_call_census", "class_initializer_chain", "decoder", "initializer_assertion_edge", "initializer_predecessor_window", "function_bodies", "control_flow_graphs", "native_edges", "whole_atlas_reference_scan", "method", "summary"}, "evidence")
        if type(evidence.get("schema_version")) is not int or evidence.get("schema_version") != SCHEMA_VERSION or type(evidence.get("analysis_kind")) is not str or evidence.get("analysis_kind") != ANALYSIS_KIND:
            raise NativeAssertionHelperStaticBoundaryError("unsupported schema or kind")
        if not all((_json_equal(evidence.get("build_identity"), dict(_mapping(program_facts.get("identity"), "identity"))), _json_equal(evidence.get("atlas"), atlas), _json_equal(evidence.get("direct_call_census"), direct_identity), _json_equal(evidence.get("class_initializer_chain"), initializer_identity), _json_equal(evidence.get("decoder"), _decoder_contract()), _json_equal(evidence.get("initializer_assertion_edge"), _initializer_edge(class_initializer)), _json_equal(evidence.get("initializer_predecessor_window"), _window_records()), _json_equal(evidence.get("method"), _METHOD))):
            raise NativeAssertionHelperStaticBoundaryError("pinned prerequisite, method, or initializer witness differs")
        bodies = _array(evidence.get("function_bodies"), "function bodies")
        if len(bodies) != 1 or not _json_equal(bodies[0], _expected_body(program_facts)):
            raise NativeAssertionHelperStaticBoundaryError("helper body record differs")
        graph_map = _validated_graphs({"control_flow_graphs": evidence.get("control_flow_graphs")}, _atlas_functions(program_facts))
        if set(graph_map) != {_ENTRY} or _canonical_sha256(graph_map[_ENTRY][0]) != _CFG_SHA256 or graph_map[_ENTRY][0].get("node_count") != 29 or graph_map[_ENTRY][0].get("edge_count") != 30:
            raise NativeAssertionHelperStaticBoundaryError("helper CFG differs")
        for point in _array(_mapping(bodies[0], "helper body").get("reviewed_points"), "reviewed points"):
            node = graph_map[_ENTRY][1].get(_rva(_mapping(point, "point").get("rva"), "point RVA"))
            if node is None or (node.get("size"), node.get("sha256")) != (_mapping(point, "point").get("size"), _mapping(point, "point").get("sha256")):
                raise NativeAssertionHelperStaticBoundaryError("sealed point does not join CFG")
        if not _json_equal(evidence.get("native_edges"), _native_edges(program_facts)) or not _json_equal(evidence.get("whole_atlas_reference_scan"), _expected_reference_scan(program_facts, direct_calls)) or not _json_equal(evidence.get("summary"), _summary(evidence)):
            raise NativeAssertionHelperStaticBoundaryError("native edge, reference, or summary partition differs")
        _assert_publication_safe(evidence)
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": STRUCTURE_VERIFICATION_KIND, "status": "structurally_verified", "build_identity": dict(evidence["build_identity"]), "evidence_sha256": _canonical_sha256(evidence), "summary": dict(evidence["summary"])}
    except NativeAssertionHelperStaticBoundaryError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassFactoryChainError, NativeLuaClassInitializerChainError, NativeLuaClassReturnHelperChainError, NativeLuaPropertyFactoryChainError) as exc:
        raise NativeAssertionHelperStaticBoundaryError(str(exc)) from exc


def validate_native_assertion_helper_static_boundary(executable: Path, evidence: Mapping[str, Any], class_initializer: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        _validate_json_tree(evidence, "evidence")
        rebuilt = build_native_assertion_helper_static_boundary(executable, class_initializer, direct_calls, program_facts, inventory=inventory)
        if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
            raise NativeAssertionHelperStaticBoundaryError("evidence differs from exact rebuild")
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": VERIFICATION_KIND, "status": "verified", "build_identity": dict(rebuilt["build_identity"]), "evidence_sha256": _canonical_sha256(rebuilt), "summary": dict(rebuilt["summary"])}
    except NativeAssertionHelperStaticBoundaryError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassFactoryChainError, NativeLuaClassInitializerChainError, NativeLuaClassReturnHelperChainError, NativeLuaPropertyFactoryChainError, PEAnchorError, OSError) as exc:
        raise NativeAssertionHelperStaticBoundaryError(str(exc)) from exc


def encode_native_assertion_helper_static_boundary(value: Mapping[str, Any]) -> str:
    try:
        _validate_json_tree(value)
        return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    except NativeLuaCClosurePublicationError as exc:
        raise NativeAssertionHelperStaticBoundaryError(str(exc)) from exc
