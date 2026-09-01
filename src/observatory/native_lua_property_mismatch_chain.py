"""Normalized mismatch paths for native Lua ``property`` consumers.

The artifact is a compact semantic derivation from the exact property-consumer
chain. Exact rebuild recursively verifies that prerequisite against the pinned
executable; structural validation replays the same derivation from its sealed
CFG nodes, direct-call points, and staged-register dispatch records.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError,
    _array,
    _assert_publication_safe,
    _canonical_bytes,
    _canonical_sha256,
    _exact_keys,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_property_consumer_chain import (
    ANALYSIS_KIND as CONSUMER_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as CONSUMER_STRUCTURE_VERIFICATION_KIND,
    VERIFICATION_KIND as CONSUMER_VERIFICATION_KIND,
    NativeLuaPropertyConsumerChainError,
    validate_native_lua_property_consumer_chain,
    validate_native_lua_property_consumer_chain_structure,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_property_mismatch_chain"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"


class NativeLuaPropertyMismatchChainError(RuntimeError):
    """Raised when the normalized property mismatch chain is stale."""


_METHOD = {
    "accepted_chain": (
        "One exact property-consumer artifact is reduced to two sealed source "
        "body identities, declared CFG-node witnesses, and deterministic Lua 5.1 "
        "stack traces for both callback-identity mismatch arms."
    ),
    "lua51_abi_premises": [
        "positive Lua stack indices are absolute",
        "negative Lua stack indices are relative to the current top",
        "lua_type value zero denotes nil",
        "lua_rawget and lua_rawset bypass table metamethod dispatch",
        "a false lua_getmetatable result pushes no Lua value",
        "lua_replace moves the top value to its index and pops the top",
        "lua_settop with index minus two pops one Lua value",
    ],
    "derivation_boundary": (
        "Exact rebuild first exact-verifies the complete property-consumer chain. "
        "PE-free validation recursively structure-verifies it and rejoins every "
        "declared path point to one sealed CFG node and its proven direct or staged "
        "Lua API identity."
    ),
    "normal_return_boundary": (
        "The traces model only normal Lua C API returns and the native function's "
        "declared C result count; error and nonreturning paths remain outside scope."
    ),
    "not_claimed": [
        "runtime reachability, invocation arity, execution order across calls, or persistence",
        "successful allocation, API calls, environment mutation, or metatable mutation",
        "factory provenance from callback identity alone",
        "candidate, input, environment, metatable, key, or value source types",
        "callability, descriptor ownership, reference validity, or lifetime",
        "dynamic metamethod attachment, later lookup, invocation, or durable read-only enforcement",
        "computed, indirect, data, un-atlased, or Lua-side references",
        "source-level property equivalence or complete program semantics",
    ],
}


_LUA51_ABI = {
    "symbols": {
        "S": "entry_stack_[I1..IN]",
        "F": "value_pushed_by_lua_getfenv_of_I1",
        "D": "raw_F_at_I2",
        "M": "metatable_of_F",
        "W": "raw_M_at_I2",
        "C": "topmost_selected_candidate",
        "X": "absolute_Lua_stack_slot_four_after_candidate_removal",
        "T": "fresh_table_created_on_the_no_metatable_storage_arm",
    },
    "stack_index_model": {
        "positive_indices_are_absolute": True,
        "negative_indices_are_top_relative": True,
        "native_machine_stack_is_distinct": True,
    },
    "normal_return_stack_effects": {
        "lua_getfenv": "pushes_environment_F",
        "lua_pushvalue": "pushes_copy_of_indexed_value",
        "lua_rawget": "pops_key_and_pushes_raw_value",
        "lua_type": "stack_neutral",
        "lua_getmetatable_false": "pushes_nothing",
        "lua_getmetatable_true": "pushes_metatable",
        "lua_replace": "moves_top_to_index_then_pops_top",
        "lua_settop_minus_two": "pops_one_value",
        "lua_tocfunction": "stack_neutral",
        "lua_createtable": "pushes_fresh_table_T",
        "lua_setfenv": "pops_environment",
        "lua_setmetatable": "pops_metatable",
        "lua_rawset": "pops_key_and_value",
    },
    "result_rule": "the_declared_C_result_count_selects_topmost_Lua_stack_values",
    "normal_return_only": True,
}


_PROFILE: dict[str, Any] = {
    "executable_sha256": "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9",
    "consumer_canonical_sha256": "2c6569177595cbdc8abdbe4ba1bdc3d09f4bb0d15dac5d280c16ba3dfcc2d3b9",
    "property_tag_entry_rva": "0x002eaa50",
    "bodies": [
        {
            "role": "setter_like_consumer",
            "entry_rva": 0x002E9FD0,
            "body_sha256": "89dcd9a4a320eb36f3c9d96c3bd24dc0c27c48b7c15dfb78fbd6ad6a59191c68",
            "cfg_sha256": "e8e40b27127b5089c437dc21970c5a239b6e67e76aa779dbd9a680047887dda4",
        },
        {
            "role": "getter_like_consumer",
            "entry_rva": 0x002EA110,
            "body_sha256": "af02593b529264569e721d6dd2e401afd5d5b2b5d8aea67ee623226bfe3584a2",
            "cfg_sha256": "bf0b0d9be19d193c9fa79b582566a9d696d73eb98d466459e0e548a5bddf1c55",
        },
    ],
    "getter_points": [
        ("getfenv_index_one", 0x002EA118, None),
        ("lua_getfenv", 0x002EA11B, "lua_getfenv"),
        ("copy_key_index_two", 0x002EA127, None),
        ("lua_pushvalue_key", 0x002EA12A, "lua_pushvalue"),
        ("rawget_environment_index", 0x002EA12C, None),
        ("lua_rawget_environment", 0x002EA12F, "lua_rawget"),
        ("type_candidate_index", 0x002EA135, None),
        ("lua_type_candidate", 0x002EA138, "lua_type"),
        ("candidate_nil_test", 0x002EA141, None),
        ("candidate_nonnil_branch", 0x002EA143, None),
        ("getmetatable_environment_index", 0x002EA145, None),
        ("lua_getmetatable_environment", 0x002EA148, "lua_getmetatable"),
        ("metatable_present_test", 0x002EA151, None),
        ("metatable_absent_branch", 0x002EA153, None),
        ("fallback_copy_key_index_two", 0x002EA155, None),
        ("fallback_lua_pushvalue_key", 0x002EA158, "lua_pushvalue"),
        ("fallback_rawget_metatable_index", 0x002EA15A, None),
        ("fallback_lua_rawget", 0x002EA15D, "lua_rawget"),
        ("tocfunction_candidate_index", 0x002EA166, None),
        ("lua_tocfunction", 0x002EA169, "lua_tocfunction"),
        ("property_tag_identity_compare", 0x002EA172, None),
        ("identity_mismatch_branch", 0x002EA177, None),
        ("result_count_one", 0x002EA198, None),
        ("return", 0x002EA19F, None),
    ],
    "setter_points": [
        ("getfenv_index_one", 0x002E9FD9, None),
        ("lua_getfenv", 0x002E9FDC, "lua_getfenv"),
        ("copy_key_index_two", 0x002E9FE8, None),
        ("lua_pushvalue_key", 0x002E9FEB, "lua_pushvalue"),
        ("rawget_environment_index", 0x002E9FED, None),
        ("lua_rawget_environment", 0x002E9FF0, "lua_rawget"),
        ("type_candidate_index", 0x002E9FF6, None),
        ("lua_type_candidate", 0x002E9FF9, "lua_type"),
        ("candidate_nil_test", 0x002EA008, None),
        ("candidate_nonnil_branch", 0x002EA00A, None),
        ("getmetatable_environment_index", 0x002EA00C, None),
        ("lua_getmetatable_environment", 0x002EA00F, "lua_getmetatable"),
        ("metatable_present_test", 0x002EA018, None),
        ("metatable_absent_branch", 0x002EA01A, None),
        ("fallback_copy_key_index_two", 0x002EA01C, None),
        ("fallback_lua_pushvalue_key", 0x002EA01F, "lua_pushvalue"),
        ("fallback_rawget_metatable_index", 0x002EA021, None),
        ("fallback_lua_rawget", 0x002EA024, "lua_rawget"),
        ("replace_candidate_index", 0x002EA02A, None),
        ("lua_replace_candidate", 0x002EA02D, "lua_replace"),
        ("settop_pop_metatable_index", 0x002EA033, None),
        ("lua_settop_pop_metatable", 0x002EA036, "lua_settop"),
        ("tocfunction_candidate_index", 0x002EA03B, None),
        ("lua_tocfunction", 0x002EA03E, "lua_tocfunction"),
        ("property_tag_identity_compare", 0x002EA047, None),
        ("identity_mismatch_branch", 0x002EA04C, None),
        ("pop_candidate_index", 0x002EA0A9, None),
        ("lua_settop_pop_candidate", 0x002EA0AC, "lua_settop"),
        ("absolute_slot_four", 0x002EA0AE, None),
        ("lua_getmetatable_slot_four", 0x002EA0B1, "lua_getmetatable"),
        ("slot_four_metatable_test", 0x002EA0BA, None),
        ("slot_four_has_metatable_branch", 0x002EA0BC, None),
        ("zero_array_size", 0x002EA0BE, None),
        ("zero_record_size", 0x002EA0BF, None),
        ("lua_createtable", 0x002EA0C1, "lua_createtable"),
        ("duplicate_fresh_table_index", 0x002EA0C7, None),
        ("lua_pushvalue_fresh_table", 0x002EA0CA, "lua_pushvalue"),
        ("setfenv_input_index_one", 0x002EA0CC, None),
        ("lua_setfenv", 0x002EA0CF, "lua_setfenv"),
        ("copy_absolute_slot_four", 0x002EA0D5, None),
        ("lua_pushvalue_slot_four", 0x002EA0D8, "lua_pushvalue"),
        ("setmetatable_fresh_table_index", 0x002EA0DA, None),
        ("lua_setmetatable", 0x002EA0DD, "lua_setmetatable"),
        ("fresh_table_to_common_tail", 0x002EA0E6, None),
        ("pop_slot_four_metatable_index", 0x002EA0E8, None),
        ("lua_settop_pop_slot_four_metatable", 0x002EA0EB, "lua_settop"),
        ("copy_store_key_index_two", 0x002EA0F0, None),
        ("lua_pushvalue_store_key", 0x002EA0F3, "lua_pushvalue"),
        ("copy_store_value_index_three", 0x002EA0F5, None),
        ("lua_pushvalue_store_value", 0x002EA0F8, "lua_pushvalue"),
        ("rawset_destination_index", 0x002EA0FA, None),
        ("lua_rawset", 0x002EA0FD, "lua_rawset"),
        ("result_count_zero", 0x002EA106, None),
        ("return", 0x002EA10C, None),
    ],
}


_GETTER_SEMANTICS = {
    "entry_contract": {
        "minimum_input_count": 2,
        "minimum_is_analysis_premise": True,
        "input_count_checked_by_binary": False,
        "exact_input_count_proven": False,
        "input_stack_symbol": "S=[I1..IN]",
    },
    "candidate_sources": [
        {
            "source_class": "environment_rawget_nonnil",
            "conditions": ["D_type_is_nonzero"],
            "internal_stack": ["S", "F", "D"],
            "candidate_symbol": "D",
        },
        {
            "source_class": "environment_rawget_nil_without_environment_metatable",
            "conditions": ["D_type_is_zero", "F_has_no_metatable"],
            "internal_stack": ["S", "F", "nil"],
            "candidate_symbol": "nil",
        },
        {
            "source_class": "environment_metatable_rawget",
            "conditions": ["D_type_is_zero", "F_has_metatable"],
            "internal_stack": ["S", "F", "nil", "M", "W"],
            "candidate_symbol": "W",
        },
    ],
    "mismatch_condition": {
        "conversion": "lua_tocfunction_of_top_candidate",
        "comparison_target_rva": "0x002eaa50",
        "relation": "not_equal",
        "type_or_provenance_classification_claimed": False,
        "comparison_instruction_rva": "0x002ea172",
        "branch_instruction_rva": "0x002ea177",
        "mismatch_successor_rva": "0x002ea197",
    },
    "terminal_paths": [
        {"source_class": "environment_rawget_nonnil", "internal_stack": ["S", "F", "D"], "selected_result": "D"},
        {"source_class": "environment_rawget_nil_without_environment_metatable", "internal_stack": ["S", "F", "nil"], "selected_result": "nil"},
        {"source_class": "environment_metatable_rawget", "internal_stack": ["S", "F", "nil", "M", "W"], "selected_result": "W"},
    ],
    "lua_api_calls_after_mismatch_branch": 0,
    "normal_result_count": 1,
    "returns_top_candidate": True,
    "common_terminal_internal_stack_claimed": False,
    "normal_return_only": True,
}


_SETTER_SEMANTICS = {
    "entry_contract": {
        "minimum_input_count": 3,
        "minimum_is_analysis_premise": True,
        "input_count_checked_by_binary": False,
        "exact_input_count_proven": False,
        "input_stack_symbol": "S=[I1..IN]",
    },
    "candidate_sources": [
        {"source_class": "environment_rawget_nonnil", "conditions": ["D_type_is_nonzero"], "normalized_stack": ["S", "F", "D"], "candidate_symbol": "D"},
        {"source_class": "environment_rawget_nil_without_environment_metatable", "conditions": ["D_type_is_zero", "F_has_no_metatable"], "normalized_stack": ["S", "F", "nil"], "candidate_symbol": "nil"},
        {
            "source_class": "environment_metatable_rawget",
            "conditions": ["D_type_is_zero", "F_has_metatable"],
            "pre_normalization_stack": ["S", "F", "nil", "M", "W"],
            "after_lua_replace_minus_three": ["S", "F", "W", "M"],
            "normalized_stack": ["S", "F", "W"],
            "candidate_symbol": "W",
        },
    ],
    "mismatch_condition": {
        "conversion": "lua_tocfunction_of_top_candidate",
        "comparison_target_rva": "0x002eaa50",
        "relation": "not_equal",
        "type_or_provenance_classification_claimed": False,
        "comparison_instruction_rva": "0x002ea047",
        "branch_instruction_rva": "0x002ea04c",
        "mismatch_successor_rva": "0x002ea0a9",
    },
    "post_mismatch_candidate_removal": {
        "lua_settop_index": -2,
        "before": ["S", "F", "C"],
        "after": ["S", "F"],
    },
    "absolute_slot_four_partition": [
        {
            "entry_input_count": 3,
            "slot_four_symbol": "F",
            "slot_four_is_appended_environment_slot": True,
        },
        {
            "minimum_entry_input_count": 4,
            "slot_four_symbol": "I4",
            "slot_four_is_appended_environment_slot": False,
        },
    ],
    "storage_paths": [
        {
            "path_class": "slot_four_has_metatable",
            "guard": "lua_getmetatable_of_X_returns_true",
            "tested_symbol": "X",
            "raw_store_destination": "F",
            "raw_store_key": "I2",
            "raw_store_value": "I3",
            "terminal_internal_stack": ["S", "F"],
        },
        {
            "path_class": "slot_four_has_no_metatable",
            "guard": "lua_getmetatable_of_X_returns_false",
            "tested_symbol": "X",
            "fresh_table_symbol": "T",
            "setfenv_attempt": {"target_input_index": 1, "environment_symbol": "T", "return_checked": False},
            "setmetatable_attempt": {"table_symbol": "T", "metatable_symbol": "X", "return_checked": False},
            "raw_store_destination": "T",
            "raw_store_key": "I2",
            "raw_store_value": "I3",
            "terminal_internal_stack": ["S", "F", "T"],
        },
    ],
    "exactly_three_input_summary": {
        "premise": "entry_input_count_equals_three",
        "premise_locally_proven": False,
        "slot_four_symbol": "F",
        "has_metatable_destination": "F",
        "no_metatable_fresh_table_metatable_symbol": "F",
    },
    "normal_result_count": 0,
    "setfenv_return_checked": False,
    "setmetatable_return_checked": False,
    "normal_return_only": True,
}


def _consumer_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "analysis_kind": CONSUMER_ANALYSIS_KIND,
        "canonical_sha256": _canonical_sha256(value),
    }


def _body_index(consumer: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for raw in _array(consumer.get("function_bodies"), "consumer function_bodies"):
        body = _mapping(raw, "consumer function body")
        entry = _rva(body.get("entry_rva"), "consumer body entry")
        if entry in result:
            raise NativeLuaPropertyMismatchChainError("consumer body entries repeat")
        result[entry] = body
    return result


def _graph_index(consumer: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for raw in _array(consumer.get("control_flow_graphs"), "consumer CFGs"):
        graph = _mapping(raw, "consumer CFG")
        entry = _rva(graph.get("caller_entry_rva"), "consumer CFG entry")
        if entry in result:
            raise NativeLuaPropertyMismatchChainError("consumer CFG entries repeat")
        result[entry] = graph
    return result


def _lua_call_index(body: Mapping[str, Any]) -> dict[int, tuple[str, str]]:
    result: dict[int, tuple[str, str]] = {}
    for raw in _array(body.get("reviewed_points"), "reviewed_points"):
        point = _mapping(raw, "reviewed point")
        api = point.get("direct_lua_import")
        if api is not None:
            result[_rva(point.get("rva"), "direct call RVA")] = (api, "direct_import")
    for raw in _array(body.get("staged_lua_dispatches"), "staged dispatches"):
        dispatch = _mapping(raw, "staged dispatch")
        api = dispatch.get("api_name")
        for raw_site in _array(dispatch.get("call_sites"), "staged call_sites"):
            site = _mapping(raw_site, "staged call site")
            call = _mapping(site.get("call"), "staged call fact")
            rva = _rva(call.get("rva"), "staged call RVA")
            if rva in result:
                raise NativeLuaPropertyMismatchChainError("Lua call RVAs overlap")
            result[rva] = (api, "staged_register")
    return result


def _point_records(
    graph: Mapping[str, Any],
    body: Mapping[str, Any],
    specifications: list[tuple[str, int, str | None]],
) -> list[dict[str, Any]]:
    nodes = {
        _rva(_mapping(raw, "CFG node").get("rva"), "CFG node RVA"): _mapping(raw, "CFG node")
        for raw in _array(graph.get("nodes"), "CFG nodes")
    }
    calls = _lua_call_index(body)
    records: list[dict[str, Any]] = []
    seen: set[int] = set()
    for role, rva, expected_api in specifications:
        node = nodes.get(rva)
        if node is None or rva in seen:
            raise NativeLuaPropertyMismatchChainError("declared path point is absent or repeated")
        seen.add(rva)
        observed = calls.get(rva)
        if expected_api is None:
            if observed is not None:
                raise NativeLuaPropertyMismatchChainError("non-call path point became a Lua call")
            api = dispatch = None
        else:
            if observed is None or observed[0] != expected_api:
                raise NativeLuaPropertyMismatchChainError("path Lua API identity changed")
            api, dispatch = observed
        records.append(
            {
                "role": role,
                "rva": node["rva"],
                "size": node["size"],
                "sha256": node["sha256"],
                "flow_kind": node["flow_kind"],
                "successor_rvas": list(node["successor_rvas"]),
                "lua_api": api,
                "lua_dispatch_kind": dispatch,
            }
        )
    return records


def _source_body_record(
    expected: Mapping[str, Any], body: Mapping[str, Any], graph: Mapping[str, Any]
) -> dict[str, Any]:
    if (
        body.get("role") != expected["role"]
        or body.get("body_sha256") != expected["body_sha256"]
        or body.get("control_flow_graph_canonical_sha256") != expected["cfg_sha256"]
        or _canonical_sha256(graph) != expected["cfg_sha256"]
    ):
        raise NativeLuaPropertyMismatchChainError("sealed consumer body identity changed")
    return {
        "role": body["role"],
        "entry_rva": body["entry_rva"],
        "atlas_record_sha256": body["atlas_record_sha256"],
        "body_size": body["body_size"],
        "body_sha256": body["body_sha256"],
        "control_flow_graph_canonical_sha256": body[
            "control_flow_graph_canonical_sha256"
        ],
        "control_flow_graph_node_count": graph["node_count"],
        "control_flow_graph_edge_count": graph["edge_count"],
    }


def _summary(value: Mapping[str, Any]) -> dict[str, Any]:
    getter = _mapping(value["getter_mismatch_path"], "getter path")
    setter = _mapping(value["setter_mismatch_path"], "setter path")
    source_bodies = _array(value["source_bodies"], "source bodies")
    return {
        "consumer_prerequisite_count": 1,
        "source_body_count": len(source_bodies),
        "source_cfg_count": len(source_bodies),
        "source_cfg_node_count": sum(
            item["control_flow_graph_node_count"] for item in source_bodies
        ),
        "source_cfg_edge_count": sum(
            item["control_flow_graph_edge_count"] for item in source_bodies
        ),
        "declared_path_point_count": len(getter["path_points"]) + len(setter["path_points"]),
        "getter_path_point_count": len(getter["path_points"]),
        "setter_path_point_count": len(setter["path_points"]),
        "candidate_source_count": len(getter["semantics"]["candidate_sources"]) + len(setter["semantics"]["candidate_sources"]),
        "getter_terminal_path_count": len(getter["semantics"]["terminal_paths"]),
        "setter_storage_path_count": len(setter["semantics"]["storage_paths"]),
        "mismatch_trace_count": 2,
        "normalized_setter_candidate_stack_count": 1,
        "non_normalized_getter_candidate_stack_count": 1,
        "conditional_entry_arity_partition_count": len(setter["semantics"]["absolute_slot_four_partition"]),
        "schema_violations": 0,
    }


def _derive_native_lua_property_mismatch_chain(
    consumer: Mapping[str, Any], program_facts: Mapping[str, Any]
) -> dict[str, Any]:
    _validate_json_tree(consumer, "consumer")
    _validate_json_tree(program_facts, "program_facts")
    if (
        consumer.get("analysis_kind") != CONSUMER_ANALYSIS_KIND
        or _canonical_sha256(consumer) != _PROFILE["consumer_canonical_sha256"]
    ):
        raise NativeLuaPropertyMismatchChainError("consumer prerequisite identity changed")
    identity = _mapping(program_facts.get("identity"), "program_facts.identity")
    if (
        identity.get("executable_sha256") != _PROFILE["executable_sha256"]
        or consumer.get("build_identity") != dict(identity)
    ):
        raise NativeLuaPropertyMismatchChainError("consumer and atlas build identities differ")
    tag = _mapping(consumer.get("property_tag_source"), "property_tag_source")
    if tag.get("tag_callback_entry_rva") != _PROFILE["property_tag_entry_rva"]:
        raise NativeLuaPropertyMismatchChainError("property tag identity changed")
    bodies = _body_index(consumer)
    graphs = _graph_index(consumer)
    expected_by_entry = {item["entry_rva"]: item for item in _PROFILE["bodies"]}
    selected: dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    source_records: list[dict[str, Any]] = []
    for entry in sorted(expected_by_entry):
        body = bodies.get(entry)
        graph = graphs.get(entry)
        if body is None or graph is None:
            raise NativeLuaPropertyMismatchChainError("required source body or CFG is absent")
        selected[entry] = (body, graph)
        source_records.append(_source_body_record(expected_by_entry[entry], body, graph))
    setter_body, setter_graph = selected[0x002E9FD0]
    getter_body, getter_graph = selected[0x002EA110]
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(identity),
        "consumer_chain": _consumer_identity(consumer),
        "lua51_abi": copy.deepcopy(_LUA51_ABI),
        "source_bodies": source_records,
        "getter_mismatch_path": {
            "entry_rva": "0x002ea110",
            "path_points": _point_records(
                getter_graph, getter_body, _PROFILE["getter_points"]
            ),
            "semantics": copy.deepcopy(_GETTER_SEMANTICS),
        },
        "setter_mismatch_path": {
            "entry_rva": "0x002e9fd0",
            "path_points": _point_records(
                setter_graph, setter_body, _PROFILE["setter_points"]
            ),
            "semantics": copy.deepcopy(_SETTER_SEMANTICS),
        },
        "method": copy.deepcopy(_METHOD),
    }
    result["summary"] = _summary(result)
    _assert_publication_safe(result)
    return result


def build_native_lua_property_mismatch_chain(
    executable: Path,
    consumer: Mapping[str, Any],
    property_factory_chain: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any],
    table_key_provenance: Mapping[str, Any],
    terminal_dispositions: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build exact mismatch evidence after recursively verifying the consumer."""
    try:
        receipt = validate_native_lua_property_consumer_chain(
            executable,
            consumer,
            property_factory_chain,
            direct_calls,
            callback_census,
            setfield_publications,
            direct_table_setter_publications,
            indirect_settable_publications,
            table_key_provenance,
            terminal_dispositions,
            program_facts,
            inventory=inventory,
        )
        if (
            receipt.get("schema_version") != SCHEMA_VERSION
            or receipt.get("analysis_kind") != CONSUMER_VERIFICATION_KIND
            or receipt.get("status") != "verified"
            or receipt.get("evidence_sha256")
            != _PROFILE["consumer_canonical_sha256"]
            or receipt.get("build_identity") != consumer.get("build_identity")
        ):
            raise NativeLuaPropertyMismatchChainError(
                "consumer exact verifier returned another result"
            )
        return _derive_native_lua_property_mismatch_chain(consumer, program_facts)
    except NativeLuaPropertyMismatchChainError:
        raise
    except (NativeLuaPropertyConsumerChainError, NativeLuaCClosurePublicationError) as exc:
        raise NativeLuaPropertyMismatchChainError(
            f"property mismatch prerequisite failed exact verification: {exc}"
        ) from exc


def validate_native_lua_property_mismatch_chain_structure(
    evidence: Mapping[str, Any],
    consumer: Mapping[str, Any],
    property_factory_chain: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any],
    table_key_provenance: Mapping[str, Any],
    terminal_dispositions: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Replay mismatch derivation after recursive PE-free validation."""
    try:
        _validate_json_tree(evidence, "evidence")
        receipt = validate_native_lua_property_consumer_chain_structure(
            consumer,
            property_factory_chain,
            direct_calls,
            callback_census,
            setfield_publications,
            direct_table_setter_publications,
            indirect_settable_publications,
            table_key_provenance,
            terminal_dispositions,
            program_facts,
        )
    except (NativeLuaPropertyConsumerChainError, NativeLuaCClosurePublicationError) as exc:
        raise NativeLuaPropertyMismatchChainError(
            f"property mismatch structural prerequisite failed: {exc}"
        ) from exc
    if (
        receipt.get("schema_version") != SCHEMA_VERSION
        or receipt.get("analysis_kind") != CONSUMER_STRUCTURE_VERIFICATION_KIND
        or receipt.get("status") != "structurally_verified"
        or receipt.get("evidence_sha256")
        != _PROFILE["consumer_canonical_sha256"]
        or receipt.get("build_identity") != consumer.get("build_identity")
    ):
        raise NativeLuaPropertyMismatchChainError(
            "consumer structural verifier returned another result"
        )
    try:
        expected = _derive_native_lua_property_mismatch_chain(consumer, program_facts)
        evidence = _mapping(evidence, "evidence")
        _exact_keys(evidence, set(expected), "evidence")
        if _canonical_bytes(evidence) != _canonical_bytes(expected):
            raise NativeLuaPropertyMismatchChainError(
                "property mismatch evidence differs from structural replay"
            )
    except NativeLuaPropertyMismatchChainError:
        raise
    except NativeLuaCClosurePublicationError as exc:
        raise NativeLuaPropertyMismatchChainError(
            f"property mismatch structural replay failed: {exc}"
        ) from exc
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": STRUCTURE_VERIFICATION_KIND,
        "status": "structurally_verified",
        "build_identity": dict(expected["build_identity"]),
        "evidence_sha256": _canonical_sha256(expected),
        "summary": dict(expected["summary"]),
    }


def validate_native_lua_property_mismatch_chain(
    executable: Path,
    evidence: Mapping[str, Any],
    consumer: Mapping[str, Any],
    property_factory_chain: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any],
    table_key_provenance: Mapping[str, Any],
    terminal_dispositions: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and canonical-byte-compare exact mismatch evidence."""
    try:
        _validate_json_tree(evidence, "evidence")
    except NativeLuaCClosurePublicationError as exc:
        raise NativeLuaPropertyMismatchChainError(
            f"property mismatch evidence is invalid: {exc}"
        ) from exc
    rebuilt = build_native_lua_property_mismatch_chain(
        executable,
        consumer,
        property_factory_chain,
        direct_calls,
        callback_census,
        setfield_publications,
        direct_table_setter_publications,
        indirect_settable_publications,
        table_key_provenance,
        terminal_dispositions,
        program_facts,
        inventory=inventory,
    )
    if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
        raise NativeLuaPropertyMismatchChainError(
            "native Lua property mismatch evidence differs from exact rebuild"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": dict(rebuilt["build_identity"]),
        "evidence_sha256": _canonical_sha256(rebuilt),
        "summary": dict(rebuilt["summary"]),
    }


def encode_native_lua_property_mismatch_chain(value: Mapping[str, Any]) -> str:
    """Return deterministic pretty JSON for evidence or a receipt."""
    _validate_json_tree(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
