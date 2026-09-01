"""Exact native initializer reached by the sealed Lua ``class`` factory.

This deliberately records byte-level field offsets, Lua registry/ref traffic, and
the single factory witness.  It does not attach source-level C++ class, vtable,
container, ownership, or runtime semantics to those offsets.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_class_factory_chain import (
    ANALYSIS_KIND as CLASS_FACTORY_ANALYSIS_KIND,
    NativeLuaClassFactoryChainError,
    _validated_graphs,
)
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError,
    _REGISTER_NAMES,
    _build_function_records,
    _canonical_bytes,
    _canonical_sha256,
    _expected_literal_record,
    _expected_point_record,
    _expected_reference_scan as _class_return_expected_reference_scan,
    _direct_call_records,
    _dispatch_records,
    _graph_call_r32_audit,
    _helper_targets,
    _literal_record,
    _native_edges,
    _source_identity,
    _whole_atlas_reference_scan as _class_return_whole_atlas_reference_scan,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError,
    _array,
    _assert_publication_safe,
    _atlas_functions,
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
from src.observatory.native_lua_super_rebinding import NativeLuaSuperRebindingError, _lua_import_map


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_class_initializer_chain"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS_SHA256 = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT_SHA256 = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_FACTORY_SHA256 = "824883dddbf0573c26c556d19501027c01b3031d1723ac8a493374bbf63204fc"
_ENTRY = 0x002EACF0
_FACTORY_ENTRY = 0x002EC220


class NativeLuaClassInitializerChainError(RuntimeError):
    """Raised when the exact native Lua class-initializer profile changes."""


def _point(role: str, rva: int, encoded: str, **meaning: Any) -> dict[str, Any]:
    return {"role": role, "rva": rva, "encoded": bytes.fromhex(encoded), "api": meaning.pop("api", None), "meaning": meaning}


_FUNCTION = {
    "role": "class_initializer",
    "entry_rva": _ENTRY,
    "body_size": 612,
    "body_sha256": "b681567bb998cd2c86267435483c7763394bd4df7843dcd8be7ecfb9e326d712",
    "cfg_canonical_sha256": "e4a45cf178c29548ae0a5fcd3ce59c70f97f723bf17458cc913898a0a3d1ede0",
    "direct_calls": [
        (0x002EADA1, "lua_createtable"), (0x002EADAA, "lua_pushvalue"),
        (0x002EADB6, "luaL_ref"), (0x002EADEB, "lua_createtable"),
        (0x002EADF4, "lua_pushvalue"), (0x002EAE00, "luaL_ref"),
        (0x002EAE3B, "lua_pushstring"), (0x002EAE47, "lua_gettable"),
        (0x002EAE50, "lua_touserdata"), (0x002EAE8A, "lua_rawgeti"),
        (0x002EAE93, "lua_setmetatable"), (0x002EAE9C, "lua_pushvalue"),
        (0x002EAEBB, "luaL_unref"), (0x002EAED4, "luaL_ref"),
        (0x002EAEEC, "lua_pushstring"), (0x002EAEF8, "lua_gettable"),
        (0x002EAF01, "lua_touserdata"), (0x002EAF15, "lua_pushstring"),
        (0x002EAF21, "lua_gettable"), (0x002EAF2A, "lua_touserdata"),
    ],
    "staged_dispatches": [
        {"api_name": "luaL_unref", "register": "ebx", "stage_rva": 0x002EADC2, "call_rvas": [0x002EADE1, 0x002EAE25]},
        {"api_name": "lua_settop", "register": "ebx", "stage_rva": 0x002EAE2A, "call_rvas": [0x002EAE33, 0x002EAE5C, 0x002EAF0D, 0x002EAF39]},
    ],
    "call_r32": {"EBX": [0x002EADE1, 0x002EAE25, 0x002EAE33, 0x002EAE5C, 0x002EAF0D, 0x002EAF39]},
    "points": [
        _point("ecx_to_edi", 0x002EAD16, "8bf9", operation="register_copy", source="ECX", destination="EDI"),
        _point("field_plus_0_fixed_write", 0x002EAD1B, "c707d4d18900", operation="store_memory_immediate", base="EDI", field_offset=0, value="0x0089d1d4"),
        _point("field_plus_4_zero", 0x002EAD21, "c7470400000000", operation="store_memory_immediate", base="EDI", field_offset=4, value=0),
        _point("field_plus_8_zero", 0x002EAD28, "c7470800000000", operation="store_memory_immediate", base="EDI", field_offset=8, value=0),
        _point("field_plus_0c_zero", 0x002EAD2F, "c7470c00000000", operation="store_memory_immediate", base="EDI", field_offset=12, value=0),
        _point("argument_two_load", 0x002EAD36, "8b450c", operation="load", source="argument_2", destination="EAX"),
        _point("argument_two_to_plus_10", 0x002EAD40, "894710", operation="store_memory", base="EDI", field_offset=16, source="argument_2"),
        _point("field_plus_14_zero", 0x002EAD43, "c7471400000000", operation="store_memory_immediate", base="EDI", field_offset=20, value=0),
        _point("field_plus_18_minus_two", 0x002EAD4A, "c74718feffffff", operation="store_memory_immediate", base="EDI", field_offset=24, value=-2),
        _point("field_plus_1c_zero", 0x002EAD51, "c7471c00000000", operation="store_memory_immediate", base="EDI", field_offset=28, value=0),
        _point("field_plus_20_minus_two", 0x002EAD58, "c74720feffffff", operation="store_memory_immediate", base="EDI", field_offset=32, value=-2),
        _point("field_plus_24_zero", 0x002EAD5F, "c7472400000000", operation="store_memory_immediate", base="EDI", field_offset=36, value=0),
        _point("field_plus_28_minus_two", 0x002EAD66, "c74728feffffff", operation="store_memory_immediate", base="EDI", field_offset=40, value=-2),
        _point("field_plus_2c_one", 0x002EAD74, "c7472c01000000", operation="store_memory_immediate", base="EDI", field_offset=44, value=1),
        _point("plus_34_zero", 0x002EAD7E, "c70600000000", operation="store_memory_immediate", base="EDI", field_offset=52, value=0),
        _point("plus_38_zero", 0x002EAD84, "c7460400000000", operation="store_memory_immediate", base="EDI", field_offset=56, value=0),
        _point("native_helper_call", 0x002EAD8B, "e87018d9ff", operation="direct_call", target_rva="0x0007c600"),
        _point("native_return_to_plus_34", 0x002EAD92, "8906", operation="store_memory", base="EDI", field_offset=52, source="EAX"),
        _point("plus_3c_zero", 0x002EAD9A, "c7473c00000000", operation="store_memory_immediate", base="EDI", field_offset=60, value=0),
        _point("first_ref_state_store", 0x002EADC8, "89771c", operation="store_memory", base="EDI", field_offset=28, source="lua_state"),
        _point("first_old_state_load", 0x002EADBC, "8b571c", operation="load_memory", base="EDI", field_offset=28, destination="EDX"),
        _point("first_old_ref_load", 0x002EADCB, "8b4f20", operation="load_memory", base="EDI", field_offset=32, destination="ECX"),
        _point("first_ref_value_store", 0x002EADCE, "894720", operation="store_memory", base="EDI", field_offset=32, source="luaL_ref_return"),
        _point("first_prior_ref_guard", 0x002EADD1, "85d2", operation="test", source="old_plus_1c"),
        _point("first_prior_state_skip_branch", 0x002EADD3, "7411", operation="branch_if_zero", target_rva="0x002eade6"),
        _point("first_prior_ref_minus_two_guard", 0x002EADD5, "83f9fe", operation="compare", source="old_plus_20", value=-2),
        _point("first_prior_ref_skip_branch", 0x002EADD8, "740c", operation="branch_if_equal", target_rva="0x002eade6"),
        _point("first_prior_unref_call", 0x002EADE1, "ffd3", operation="register_call", register="EBX", api_name="luaL_unref"),
        _point("second_old_state_load", 0x002EAE06, "8b5724", operation="load_memory", base="EDI", field_offset=36, destination="EDX"),
        _point("second_old_ref_load", 0x002EAE0F, "8b4f28", operation="load_memory", base="EDI", field_offset=40, destination="ECX"),
        _point("second_ref_state_store", 0x002EAE0C, "897724", operation="store_memory", base="EDI", field_offset=36, source="lua_state"),
        _point("second_ref_value_store", 0x002EAE12, "894728", operation="store_memory", base="EDI", field_offset=40, source="luaL_ref_return"),
        _point("second_prior_ref_guard", 0x002EAE15, "85d2", operation="test", source="old_plus_24"),
        _point("second_prior_state_skip_branch", 0x002EAE17, "7411", operation="branch_if_zero", target_rva="0x002eae2a"),
        _point("second_prior_ref_minus_two_guard", 0x002EAE19, "83f9fe", operation="compare", source="old_plus_28", value=-2),
        _point("second_prior_ref_skip_branch", 0x002EAE1C, "740c", operation="branch_if_equal", target_rva="0x002eae2a"),
        _point("second_prior_unref_call", 0x002EAE25, "ffd3", operation="register_call", register="EBX", api_name="luaL_unref"),
        _point("settop_ebx_stage", 0x002EAE2A, "8b1d10657d00", operation="iat_load", api_name="lua_settop", destination="EBX"),
        _point("table_pair_cleanup", 0x002EAE33, "ffd3", operation="register_call", register="EBX", api_name="lua_settop", index=-3),
        _point("classes_key_push", 0x002EAE35, "6818bf8300", operation="push_literal", literal_rva="0x0043bf18"),
        _point("classes_gettable", 0x002EAE47, "ff15bc647d00", api="lua_gettable", operation="direct_lua_call"),
        _point("classes_touserdata", 0x002EAE50, "ff159c647d00", api="lua_touserdata", operation="direct_lua_call", index=-1),
        _point("classes_local_save", 0x002EAE59, "89450c", operation="store", destination="stack_argument_slot", source="EAX"),
        _point("classes_lookup_cleanup", 0x002EAE5C, "ffd3", operation="register_call", register="EBX", api_name="lua_settop", index=-2),
        _point("classes_guard", 0x002EAE64, "83780cfe", operation="compare_memory_immediate", base="EAX", field_offset=12, value=-2),
        _point("classes_guard_nonminus_two_branch", 0x002EAE68, "7517", operation="branch_if_not_equal", target_rva="0x002eae81"),
        _point("registry_classes_assertion", 0x002EAE76, "e847ee0800", operation="direct_call", target_rva="0x00379cc2"),
        _point("classes_reference_offset_push", 0x002EAE81, "ff7010", operation="push_memory", base="EAX", field_offset=16),
        _point("classes_reference_rawgeti", 0x002EAE8A, "ff15c0647d00", api="lua_rawgeti", operation="direct_lua_call"),
        _point("classes_metatable_set", 0x002EAE93, "ff1530657d00", api="lua_setmetatable", operation="direct_lua_call", index=-2),
        _point("prior_plus_14_unref_guard", 0x002EAEA8, "85c9", operation="test", source="old_plus_14"),
        _point("old_plus_14_load", 0x002EAEA2, "8b4f14", operation="load_memory", base="EDI", field_offset=20, destination="ECX"),
        _point("old_plus_14_skip_branch", 0x002EAEAA, "7418", operation="branch_if_zero", target_rva="0x002eaec4"),
        _point("old_plus_18_load", 0x002EAEAC, "8b4718", operation="load_memory", base="EDI", field_offset=24, destination="EAX"),
        _point("old_plus_18_minus_two_guard", 0x002EAEAF, "83f8fe", operation="compare", source="old_plus_18", value=-2),
        _point("old_plus_18_skip_branch", 0x002EAEB2, "7410", operation="branch_if_equal", target_rva="0x002eaec4"),
        _point("old_plus_14_direct_unref", 0x002EAEBB, "ff15ec647d00", api="luaL_unref", operation="direct_lua_call"),
        _point("plus_18_reset", 0x002EAECA, "c74718feffffff", operation="store_memory_immediate", base="EDI", field_offset=24, value=-2),
        _point("plus_14_state_store", 0x002EAED1, "897714", operation="store_memory", base="EDI", field_offset=20, source="lua_state"),
        _point("plus_18_ref_store", 0x002EAEDA, "894718", operation="store_memory", base="EDI", field_offset=24, source="luaL_ref_return"),
        _point("classes_plus_8_to_plus_30", 0x002EAEE9, "894730", operation="store_memory", base="EDI", field_offset=48, source="classes_lookup_result_plus_8"),
        _point("cast_graph_key_push", 0x002EAEE0, "686cbf8300", operation="push_literal", literal_rva="0x0043bf6c"),
        _point("cast_graph_gettable", 0x002EAEF8, "ff15bc647d00", api="lua_gettable", operation="direct_lua_call"),
        _point("cast_graph_touserdata", 0x002EAF01, "ff159c647d00", api="lua_touserdata", operation="direct_lua_call", index=-1),
        _point("cast_graph_cleanup", 0x002EAF0D, "ffd3", operation="register_call", register="EBX", api_name="lua_settop", index=-2),
        _point("cast_graph_to_plus_40", 0x002EAF0A, "894740", operation="store_memory", base="EDI", field_offset=64, source="cast_graph_lookup_result"),
        _point("class_id_map_key_push", 0x002EAF0F, "686ca88200", operation="push_literal", literal_rva="0x0042a86c"),
        _point("class_id_map_gettable", 0x002EAF21, "ff15bc647d00", api="lua_gettable", operation="direct_lua_call"),
        _point("class_id_map_touserdata", 0x002EAF2A, "ff159c647d00", api="lua_touserdata", operation="direct_lua_call", index=-1),
        _point("class_id_map_cleanup", 0x002EAF39, "ffd3", operation="register_call", register="EBX", api_name="lua_settop", index=-2),
        _point("class_id_map_to_plus_44", 0x002EAF33, "894744", operation="store_memory", base="EDI", field_offset=68, source="class_id_map_lookup_result"),
        _point("return_edi", 0x002EAF3E, "8bc7", operation="register_copy", source="EDI", destination="EAX"),
    ],
    "semantic_facts": {
        "receiver_register_transition": "ECX_to_EDI", "source_semantic_names_assigned": False,
        "fixed_offset_writes": {"0x0": "0x0089d1d4", "0x4": 0, "0x8": 0, "0xc": 0, "0x10": "argument_2", "0x14": 0, "0x18": -2, "0x1c": 0, "0x20": -2, "0x24": 0, "0x28": -2, "0x2c": 1, "0x34": "native_0x0007c600_return_after_zero", "0x38": 0, "0x3c": 0, "0x30": "classes_lookup_result_plus_8", "0x40": "cast_graph_lookup_result", "0x44": "class_id_map_lookup_result"},
        "registry_index": -10000, "reference_sentinel": -2,
        "first_ref_pair_offsets": [28, 32], "second_ref_pair_offsets": [36, 40], "third_ref_pair_offsets": [20, 24],
        "prior_ref_unreference_condition": "old_state_nonzero_and_old_ref_not_minus_2",
        "classes_guard_condition": "registry_classes_result_plus_0x0c_equals_minus_2", "classes_reference_offset": 16,
        "registry_key_lookup_api": "lua_gettable", "registry_key_lookup_raw_claimed": False,
        "assertion_helper_termination_claimed": False,
        "return_register": "EDI", "runtime_or_success_claimed": False,
    },
}

_PROFILE = {"executable_sha256": _EXE_SHA256, "functions": [_FUNCTION],
    "literals": [
        {"role":"classes_registry_key","text":"__luabind_classes","rva":0x0043BF18,"byte_length_excluding_nul":17,"nul_terminated_bytes_sha256":"d9b53c957a9924e6583d6b1931dfc280dfff360c1a81042f6264b3d285d355fa","section_name":".rdata","section_rva":0x003D6000,"section_characteristics":0x40000040},
        {"role":"cast_graph_registry_key","text":"__luabind_cast_graph","rva":0x0043BF6C,"byte_length_excluding_nul":20,"nul_terminated_bytes_sha256":"2c6601dedc983c9694b1c556740cbe937c23189effa02a9d6129090e336f8800","section_name":".rdata","section_rva":0x003D6000,"section_characteristics":0x40000040},
        {"role":"class_id_map_registry_key","text":"__luabind_class_id_map","rva":0x0042A86C,"byte_length_excluding_nul":22,"nul_terminated_bytes_sha256":"9ff3832e39fd8abb51ed203f64ef8a5b9c518d8f72156c942d3b99e7a056cd61","section_name":".rdata","section_rva":0x003D6000,"section_characteristics":0x40000040},
    ],
    "native_edges": [
        {"role":"opaque_native_helper_edge","instruction_rva":0x002EAD8B,"source_entry_rva":_ENTRY,"target_entry_rva":0x0007C600,"encoded":"e87018d9ff","condition":None},
        {"role":"registry_classes_assertion_edge","instruction_rva":0x002EAE76,"source_entry_rva":_ENTRY,"target_entry_rva":0x00379CC2,"encoded":"e847ee0800","condition":"registry_classes_result_plus_0x0c_equals_minus_2"},
    ],
    "target_references": [{"instruction_rva":0x002EC302,"owner_entry_rva":_FACTORY_ENTRY,"target_rva":_ENTRY,"encoded":"e8e9e9ffff","operand_index":0}],
}

_METHOD = {"accepted_chain": "One canonical-pinned class-factory edge is joined to one exact native initializer body, direct and register-staged Lua calls, selected offset-only writes, literals, native edges, and a complete atlas reference partition.", "lua51_abi_premises": ["Lua stack pseudo-indices use the Lua 5.1 negative-index model", "lua_settop with a negative index retains top + index + 1 entries"], "native_abi_premise": "32-bit Windows cdecl preserves EBX, ESI, and EDI across calls; staged-register and retained-state proofs are syntactic binary proofs under that premise.", "structural_boundary": "PE-free validation reconstructs prerequisite identities and every sealed finite record; exact bytes and full operand traversal require an exact PE rebuild.", "not_claimed": ["runtime reachability, invocation, order, frequency, state continuity, or successful calls", "input pointer, registry lookup, userdata, table, reference, ownership, or lifetime validity", "raw lua_gettable lookups or absence of registry-table metamethod effects", "source-level class, vtable, container, ownership, relationship, or lifetime names", "semantic behavior of native callee 0x0007c600 or termination behavior of the assertion helper", "computed, indirect, data, un-atlased, or Lua-side references"]}


def _direct_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    return _source_identity(value, DIRECT_CALL_ANALYSIS_KIND, _DIRECT_SHA256, "direct-call census")


def _factory_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    return _source_identity(value, CLASS_FACTORY_ANALYSIS_KIND, _FACTORY_SHA256, "class factory")


def _facts_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    identity = _source_identity(value, "pe_ghidra_program_facts", _FACTS_SHA256, "program facts")
    summary = _mapping(value.get("summary"), "program facts summary")
    return {**identity, "function_count":summary.get("function_count"), "body_range_count":summary.get("body_range_count"), "function_body_bytes":summary.get("function_body_bytes")}


def _preflight(factory: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    identity = _mapping(facts.get("identity"), "program facts identity")
    if identity.get("executable_sha256") != _EXE_SHA256:
        raise NativeLuaClassInitializerChainError("program facts have no reviewed initializer profile")
    for label, value in (("class factory",factory),("direct census",direct)):
        if value.get("build_identity") != dict(identity):
            raise NativeLuaClassInitializerChainError(f"{label} build identity differs from program facts")
    return _facts_identity(facts), _direct_identity(direct), _factory_identity(factory)


def _initializer_edge(factory: Mapping[str, Any]) -> list[dict[str, Any]]:
    found = []
    for raw in _array(factory.get("native_edges"), "factory native edges"):
        edge = _mapping(raw, "factory native edge")
        if _rva(edge.get("source_entry_rva"), "edge source") == _FACTORY_ENTRY and _rva(edge.get("target_entry_rva"), "edge target") == _ENTRY:
            found.append(dict(edge))
    if len(found) != 1 or found[0].get("role") != "conditional_initializer_edge":
        raise NativeLuaClassInitializerChainError("class factory lacks the exact conditional initializer edge")
    return found


def _decoder_contract() -> dict[str, Any]:
    return {"name":"capstone", "version":SUPPORTED_CAPSTONE_VERSION, "architecture":"x86", "mode_bits":32, "operand_classes":["absolute_memory","immediate"], "cfg_register_write_fields":["writes_ebx","writes_esi","writes_edi","writes_esp"], "register_call_encoding_audit":[{"register":r,"encoding":f"ff{0xd0+i:02x}"} for i,r in enumerate(_REGISTER_NAMES)]}


def _initializer_reference_scan(scan: Mapping[str, Any]) -> dict[str, Any]:
    """Remove callback-specific aggregate labels from the reused exact scanner."""
    normalized = dict(_mapping(scan, "initializer reference scan"))
    aggregates = dict(
        _mapping(normalized.get("aggregates"), "initializer reference aggregates")
    )
    aggregates.pop("returned_callback_reference_count", None)
    aggregates.pop("alternate_owner_reference_count", None)
    normalized["aggregates"] = aggregates
    return normalized


def _expected_reference_scan(
    program_facts: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    return _initializer_reference_scan(
        _class_return_expected_reference_scan(program_facts, direct_calls, profile)
    )


def _whole_atlas_reference_scan(
    data: bytes,
    image: Any,
    decoder: Any,
    program_facts: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    return _initializer_reference_scan(
        _class_return_whole_atlas_reference_scan(
            data, image, decoder, program_facts, direct_calls, profile
        )
    )


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    body = _array(result.get("function_bodies"), "function bodies")[0]
    graphs = _array(result.get("control_flow_graphs"), "control-flow graphs")
    dispatches = _array(_mapping(body, "body").get("staged_lua_dispatches"), "dispatches")
    calls = sum(len(_array(_mapping(x, "dispatch").get("call_sites"), "call sites")) for x in dispatches)
    scan = _mapping(result.get("whole_atlas_reference_scan"), "scan")
    agg = _mapping(scan.get("aggregates"), "scan aggregates")
    direct_count = len(_array(_mapping(body,"body").get("direct_lua_calls"),"direct calls"))
    native_edges = _array(result.get("native_edges"), "native edges")
    return {"reviewed_initializer_count":1,"reviewed_initializer_bytes":body["body_size"],"sealed_control_flow_graph_count":len(graphs),"sealed_control_flow_graph_node_count":sum(graph["node_count"] for graph in graphs),"sealed_control_flow_graph_edge_count":sum(graph["edge_count"] for graph in graphs),"direct_lua_call_count":direct_count,"staged_lua_dispatch_count":len(dispatches),"staged_lua_call_count":calls,"total_lua_call_count":direct_count+calls,"call_r32_count":sum(len(item["call_rvas"]) for item in body["call_r32_audit"]),"literal_count":len(_array(result.get("literals"), "literals")),"selected_native_edge_count":len(native_edges),"unique_native_edge_target_count":len({edge["target_entry_rva"] for edge in native_edges}),"initializer_target_count":len(_array(result.get("initializer_targets"), "initializer targets")),"class_factory_initializer_edge_count":len(_array(result.get("conditional_initializer_edge"), "initializer edges")),"target_reference_count":agg["reference_count"],"target_reference_direct_call_count":agg["direct_call_count"],"target_reference_comparison_count":agg["comparison_count"],"target_reference_other_address_count":agg["other_address_count"],"target_reference_memory_operand_count":agg["memory_operand_count"],"target_reference_owner_count":agg["owner_count"],"schema_violations":0}


def _build(executable: Path, factory: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    for value,label in ((factory,"class factory"),(direct,"direct calls"),(facts,"program facts"),(inventory,"inventory")):
        _validate_json_tree(value,label)
    receipt = validate_native_lua_direct_call_census(executable,direct,facts,inventory=inventory)
    if receipt.get("status") != "verified" or receipt.get("evidence_sha256") != _DIRECT_SHA256:
        raise NativeLuaClassInitializerChainError("direct-call prerequisite exact verification failed")
    atlas,direct_identity,factory_identity = _preflight(factory,direct,facts)
    data,image,digest = _load_executable(executable)
    identity = _mapping(facts.get("identity"), "facts identity")
    if digest != _EXE_SHA256 or identity.get("executable_size") != len(data) or identity.get("architecture") != image.architecture:
        raise NativeLuaClassInitializerChainError("executable identity differs from reviewed facts")
    decoder,_ = _decoder()
    bodies,graphs = _build_function_records(data,image,decoder,facts,direct,_PROFILE)
    result = {"schema_version":SCHEMA_VERSION,"analysis_kind":ANALYSIS_KIND,"build_identity":dict(identity),"atlas":atlas,"direct_call_census":direct_identity,"class_factory_chain":factory_identity,"decoder":_decoder_contract(),"conditional_initializer_edge":_initializer_edge(factory),"initializer_targets":_helper_targets(bodies,_PROFILE,image.image_base),"literals":[_literal_record(data,image,x) for x in _PROFILE["literals"]],"function_bodies":bodies,"control_flow_graphs":graphs,"native_edges":_native_edges(_PROFILE,facts),"whole_atlas_reference_scan":_whole_atlas_reference_scan(data,image,decoder,facts,direct,_PROFILE),"method":_METHOD}
    result["summary"] = _summary(result)
    _assert_publication_safe(result)
    if _load_executable(executable)[2] != digest: raise NativeLuaClassInitializerChainError("executable changed during exact rebuild")
    validate_native_lua_class_initializer_chain_structure(result,factory,direct,facts)
    return result


def build_native_lua_class_initializer_chain(executable: Path, class_factory: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try: return _build(executable,class_factory,direct_calls,program_facts,inventory=inventory)
    except NativeLuaClassInitializerChainError: raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassFactoryChainError,NativeLuaClassReturnHelperChainError,NativeLuaSuperRebindingError,NativeLuaPropertyFactoryChainError,OSError) as exc: raise NativeLuaClassInitializerChainError(str(exc)) from exc


def validate_native_lua_class_initializer_chain_structure(evidence: Mapping[str, Any], class_factory: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any]) -> dict[str, Any]:
    try:
        for value,label in ((evidence,"evidence"),(class_factory,"class factory"),(direct_calls,"direct calls"),(program_facts,"program facts")): _validate_json_tree(value,label)
        direct_receipt = validate_native_lua_direct_call_structure(direct_calls,program_facts)
        if direct_receipt.get("status") != "structurally_verified" or direct_receipt.get("evidence_sha256") != _DIRECT_SHA256: raise NativeLuaClassInitializerChainError("direct-call structural prerequisite failed")
        atlas,direct_identity,factory_identity = _preflight(class_factory,direct_calls,program_facts)
        identity = dict(_mapping(program_facts.get("identity"),"facts identity"))
        _exact_keys(_mapping(evidence,"evidence"), {"schema_version","analysis_kind","build_identity","atlas","direct_call_census","class_factory_chain","decoder","conditional_initializer_edge","initializer_targets","literals","function_bodies","control_flow_graphs","native_edges","whole_atlas_reference_scan","method","summary"}, "evidence")
        if evidence.get("schema_version") != SCHEMA_VERSION or evidence.get("analysis_kind") != ANALYSIS_KIND: raise NativeLuaClassInitializerChainError("unsupported initializer schema or kind")
        if evidence.get("build_identity") != identity or evidence.get("atlas") != atlas or evidence.get("direct_call_census") != direct_identity or evidence.get("class_factory_chain") != factory_identity: raise NativeLuaClassInitializerChainError("prerequisite identity differs")
        if evidence.get("decoder") != _decoder_contract() or evidence.get("method") != _METHOD or evidence.get("conditional_initializer_edge") != _initializer_edge(class_factory): raise NativeLuaClassInitializerChainError("contract or factory edge differs")
        if evidence.get("literals") != [_expected_literal_record(x) for x in _PROFILE["literals"]]: raise NativeLuaClassInitializerChainError("literal profile differs")
        functions = _atlas_functions(program_facts); function = functions.get(_ENTRY)
        body = _array(evidence.get("function_bodies"),"function bodies")
        if len(body)!=1 or not isinstance(function,Mapping) or function.get("body_size") != 612 or function.get("body_sha256") != _FUNCTION["body_sha256"]: raise NativeLuaClassInitializerChainError("initializer body partition differs")
        raw = _mapping(body[0],"initializer body")
        _exact_keys(raw, {"role","entry_rva","atlas_record_sha256","body_size","body_sha256","range_start_rva","range_size","control_flow_graph_canonical_sha256","reviewed_points","direct_lua_calls","staged_lua_dispatches","call_r32_audit","register_call_partition_complete","semantic_facts"}, "initializer body")
        expected = {"role":"class_initializer","entry_rva":_hex(_ENTRY),"atlas_record_sha256":atlas_record_sha256(function),"body_size":612,"body_sha256":_FUNCTION["body_sha256"],"range_start_rva":_hex(_ENTRY),"range_size":612,"control_flow_graph_canonical_sha256":_FUNCTION["cfg_canonical_sha256"],"register_call_partition_complete":True,"semantic_facts":_FUNCTION["semantic_facts"]}
        for key,value in expected.items():
            if raw.get(key) != value: raise NativeLuaClassInitializerChainError(f"initializer body {key} differs")
        if raw.get("reviewed_points") != [_expected_point_record(x) for x in _FUNCTION["points"]]: raise NativeLuaClassInitializerChainError("reviewed point partition differs")
        if raw.get("direct_lua_calls") != _direct_call_records(_FUNCTION,direct_calls): raise NativeLuaClassInitializerChainError("direct Lua-call partition differs")
        if raw.get("call_r32_audit") != [{"register":r,"call_rvas":[_hex(x) for x in _FUNCTION["call_r32"].get(r,[])]} for r in _REGISTER_NAMES]: raise NativeLuaClassInitializerChainError("call-r32 audit differs")
        try:
            graph_map = _validated_graphs({"control_flow_graphs": evidence.get("control_flow_graphs")}, functions)
        except NativeLuaClassFactoryChainError as exc:
            raise NativeLuaClassInitializerChainError(f"initializer CFG validation failed: {exc}") from exc
        if set(graph_map) != {_ENTRY}: raise NativeLuaClassInitializerChainError("initializer CFG partition differs")
        graph,nodes,_edges = graph_map[_ENTRY]
        if _canonical_sha256(graph) != _FUNCTION["cfg_canonical_sha256"]: raise NativeLuaClassInitializerChainError("initializer CFG identity differs")
        for point in raw["reviewed_points"]:
            node = nodes.get(_rva(point["rva"], "reviewed point RVA"))
            if node is None or (node.get("size"),node.get("sha256")) != (point["size"],point["sha256"]): raise NativeLuaClassInitializerChainError("reviewed point does not join initializer CFG")
        for direct in raw["direct_lua_calls"]:
            node = nodes.get(_rva(direct["call_rva"], "direct Lua call RVA"))
            if node is None or (node.get("size"),node.get("sha256")) != (direct["instruction_size"],direct["instruction_sha256"]): raise NativeLuaClassInitializerChainError("direct Lua call does not join initializer CFG")
        image_base = _rva(_mapping(program_facts.get("ghidra"), "ghidra").get("image_base"), "image base")
        if evidence.get("initializer_targets") != _helper_targets([raw],_PROFILE,image_base): raise NativeLuaClassInitializerChainError("initializer target records differ")
        if raw.get("staged_lua_dispatches") != _dispatch_records(_FUNCTION,graph,image_base,_lua_import_map(direct_calls),program_facts,functions): raise NativeLuaClassInitializerChainError("staged Lua dispatch proof differs")
        if raw.get("call_r32_audit") != _graph_call_r32_audit(nodes): raise NativeLuaClassInitializerChainError("call-r32 graph partition differs")
        expected_native_edges = _native_edges(_PROFILE,program_facts)
        if evidence.get("native_edges") != expected_native_edges: raise NativeLuaClassInitializerChainError("native edge partition differs")
        for edge in expected_native_edges:
            instruction = _mapping(edge.get("instruction"), "native edge instruction")
            node = nodes.get(_rva(instruction.get("rva"), "native edge RVA"))
            if node is None or (node.get("size"),node.get("sha256")) != (instruction.get("size"),instruction.get("sha256")): raise NativeLuaClassInitializerChainError("native edge does not join initializer CFG")
        if evidence.get("whole_atlas_reference_scan") != _expected_reference_scan(program_facts,direct_calls,_PROFILE): raise NativeLuaClassInitializerChainError("reference partition differs")
        if evidence.get("summary") != _summary(evidence): raise NativeLuaClassInitializerChainError("summary differs")
        _assert_publication_safe(evidence)
        return {"schema_version":SCHEMA_VERSION,"analysis_kind":STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","build_identity":identity,"evidence_sha256":_canonical_sha256(evidence),"summary":dict(evidence["summary"])}
    except NativeLuaClassInitializerChainError: raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassFactoryChainError,NativeLuaClassReturnHelperChainError,NativeLuaSuperRebindingError,NativeLuaPropertyFactoryChainError) as exc: raise NativeLuaClassInitializerChainError(str(exc)) from exc


def validate_native_lua_class_initializer_chain(executable: Path, evidence: Mapping[str, Any], class_factory: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        _validate_json_tree(evidence,"evidence")
        rebuilt = build_native_lua_class_initializer_chain(executable,class_factory,direct_calls,program_facts,inventory=inventory)
        if _canonical_bytes(evidence) != _canonical_bytes(rebuilt): raise NativeLuaClassInitializerChainError("initializer evidence differs from exact rebuild")
        return {"schema_version":SCHEMA_VERSION,"analysis_kind":VERIFICATION_KIND,"status":"verified","build_identity":dict(rebuilt["build_identity"]),"evidence_sha256":_canonical_sha256(rebuilt),"summary":dict(rebuilt["summary"])}
    except NativeLuaClassInitializerChainError: raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassFactoryChainError,NativeLuaClassReturnHelperChainError,NativeLuaSuperRebindingError,NativeLuaPropertyFactoryChainError,OSError) as exc: raise NativeLuaClassInitializerChainError(str(exc)) from exc


def encode_native_lua_class_initializer_chain(value: Mapping[str, Any]) -> str:
    try:
        _validate_json_tree(value)
        return json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2,sort_keys=True)+"\n"
    except NativeLuaCClosurePublicationError as exc: raise NativeLuaClassInitializerChainError(str(exc)) from exc
