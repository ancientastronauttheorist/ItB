"""Exact callback-side helper chain for the native Lua ``class`` factory.

The artifact seals the three native helpers reached by the returned callback,
their complete Lua-call partitions, selected field/control-flow facts, and the
complete atlas reference frontier for the helper entry points.  It deliberately
leaves the factory-side initializer and source-level class semantics separate.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_class_factory_chain import (
    ANALYSIS_KIND as CLASS_FACTORY_ANALYSIS_KIND,
    NativeLuaClassFactoryChainError,
    _validated_graphs,
    _with_edi_writes,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError,
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _canonical_bytes,
    _canonical_sha256,
    _decode_range,
    _exact_keys,
    _hex,
    _instruction_fact,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_cclosure_table_key_provenance import _enhanced_cfg
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_CALL_ANALYSIS_KIND,
    CALL_FORM as DIRECT_CALL_FORM,
    SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
    validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_lua_super_rebinding import (
    NativeLuaSuperRebindingError,
    _lua_import_map,
    _staged_dispatch_records,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_class_return_helper_chain"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

LUA_LIBRARY = "lua5.1.dll"
PE_SECTION_WRITABLE = 0x80000000
MAX_LITERAL_BYTES = 128

_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS_SHA256 = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT_SHA256 = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_CLASS_FACTORY_SHA256 = "824883dddbf0573c26c556d19501027c01b3031d1723ac8a493374bbf63204fc"
_RETURNED_CALLBACK = 0x002EC110

_REGISTER_NAMES = ("EAX", "ECX", "EDX", "EBX", "ESP", "EBP", "ESI", "EDI")


class NativeLuaClassReturnHelperChainError(RuntimeError):
    """Raised when the sealed callback-helper profile cannot be reproduced."""


def _point(
    role: str,
    rva: int,
    encoded_hex: str,
    *,
    api: str | None = None,
    **meaning: Any,
) -> dict[str, Any]:
    return {
        "role": role,
        "rva": rva,
        "encoded": bytes.fromhex(encoded_hex),
        "api": api,
        "meaning": meaning,
    }


_METHOD = {
    "accepted_chain": (
        "One canonical-pinned exact class-factory artifact is joined to the three "
        "callback-side helper bodies, their complete direct and register-staged Lua "
        "call partitions, selected native edges, literals, and a complete all-operand "
        "atlas reference partition for the helper entry points."
    ),
    "lua51_abi_premises": [
        "Lua stack pseudo-indices use the Lua 5.1 negative-index model",
        "lua_settop with a negative index retains top + index + 1 entries",
        "lua_next consumes the current key and conditionally pushes the next key and value pair",
        "lua_equal does not consume its compared stack values",
        "lua_settable may invoke metamethod behavior",
    ],
    "native_abi_premise": (
        "32-bit Windows cdecl preserves EBX and EDI across calls; the staged-register "
        "proofs are syntactic binary proofs under that premise."
    ),
    "structural_boundary": (
        "PE-free validation reconstructs every prerequisite-derived record, sealed "
        "body and CFG identity, instruction fact, direct and staged call join, native edge, "
        "literal profile, target reference, method field, and aggregate. PE bytes, "
        "decoded operands and register writes, and exhaustive traversal require exact rebuild."
    ),
    "not_claimed": [
        "runtime reachability, invocation, order, frequency, state continuity, or successful calls",
        "a raw metatable lookup, a type proof, or absence of gettable, equality, or settable metamethod effects",
        "input userdata, table, pointer, iterator, or registry-reference validity",
        "native class, base, derivation, inheritance, container, relationship, ownership, or lifetime names",
        "semantic behavior of native callees reached by the mutation helper",
        "identity or behavior of the alternate 0x002e7970 caller beyond its one exact reference",
        "computed, indirect, data, un-atlased, or Lua-side consumers or references",
        "factory-side initializer behavior or source-level C++ or Lua equivalence",
    ],
}


_SEALED_PROFILE: dict[str, Any] = {
    "executable_sha256": _EXE_SHA256,
    "functions": [
        {
            "role": "field_mutation_helper",
            "entry_rva": 0x002EB140,
            "body_size": 237,
            "body_sha256": "2184616f615a261d2b3781fe7f0840780afd79150544323341f668f58f9b821b",
            "cfg_canonical_sha256": "35a614bfa3a596d4fce54d2a77a50547fa6e01ea79520c2c33c264307c7413b2",
            "direct_calls": [],
            "staged_dispatches": [],
            "call_r32": {},
            "points": [
                _point("argument_load", 0x002EB153, "8b7d08", operation="load", source="argument_1", destination="EDI"),
                _point("receiver_save", 0x002EB156, "894df4", operation="store", source="ECX", destination="stack_local_minus_0x0c"),
                _point("argument_plus_4_guard", 0x002EB159, "837f0400", operation="compare_memory_immediate", base="EDI", field_offset=4, value=0),
                _point("argument_plus_4_nonzero_branch", 0x002EB15D, "751a", operation="branch_if_not_equal", target_rva="0x002eb179"),
                _point("assertion_edge", 0x002EB16E, "e84feb0800", operation="direct_call", target_rva="0x00379cc2"),
                _point("argument_plus_4_load", 0x002EB179, "8b5f04", operation="load_memory", base="EDI", field_offset=4, destination="EBX"),
                _point("traversal_root_plus_0x34", 0x002EB17C, "8b4334", operation="load_memory", base="EBX", field_offset=52, destination="EAX"),
                _point("traversal_first_node", 0x002EB17F, "8b30", operation="load_memory", base="EAX", field_offset=0, destination="ESI"),
                _point("traversal_empty_compare", 0x002EB184, "3bf0", operation="compare_registers", left="ESI", right="EAX"),
                _point("traversal_empty_branch", 0x002EB186, "7433", operation="branch_if_equal", target_rva="0x002eb1bb"),
                _point("receiver_plus_0x34", 0x002EB188, "8d7934", operation="address", base="ECX", field_offset=52, destination="EDI"),
                _point("node_plus_0x10", 0x002EB190, "8d4610", operation="address", base="ESI", field_offset=16, destination="EAX"),
                _point("per_node_helper_one", 0x002EB19A, "e851d0ffff", operation="direct_call", target_rva="0x002e81f0"),
                _point("node_plus_0x14_load", 0x002EB1A2, "8b4e14", operation="load_memory", base="ESI", field_offset=20, destination="ECX"),
                _point("node_plus_0x14_copy", 0x002EB1A5, "894814", operation="store_memory", base="EAX", field_offset=20, source="ECX"),
                _point("per_node_helper_two", 0x002EB1AB, "e8802dd8ff", operation="direct_call", target_rva="0x0006df30"),
                _point("traversal_next_compare", 0x002EB1B3, "3b7334", operation="compare_register_memory", register="ESI", base="EBX", field_offset=52),
                _point("traversal_loop_branch", 0x002EB1B6, "75d8", operation="branch_if_not_equal", target_rva="0x002eb190"),
                _point("append_end_load", 0x002EB1BE, "8b4608", operation="load_memory", base="ESI", field_offset=8, destination="EAX"),
                _point("input_alias_upper_compare", 0x002EB1C1, "3bf8", operation="unsigned_compare", left="EDI", right="EAX"),
                _point("external_input_branch", 0x002EB1C3, "7332", operation="branch_if_above_or_equal", target_rva="0x002eb1f7"),
                _point("append_begin_load", 0x002EB1C5, "8b4e04", operation="load_memory", base="ESI", field_offset=4, destination="ECX"),
                _point("input_alias_lower_compare", 0x002EB1C8, "3bcf", operation="unsigned_compare", left="ECX", right="EDI"),
                _point("external_input_second_branch", 0x002EB1CA, "772b", operation="branch_if_above", target_rva="0x002eb1f7"),
                _point("eight_byte_index_delta", 0x002EB1CC, "2bf9", operation="subtract", destination="EDI", source="ECX"),
                _point("eight_byte_index_scale", 0x002EB1CE, "c1ff03", operation="arithmetic_shift_right", register="EDI", bits=3),
                _point("alias_capacity_compare", 0x002EB1D1, "3b460c", operation="compare_register_memory", register="EAX", base="ESI", field_offset=12),
                _point("alias_capacity_helper", 0x002EB1DA, "e841040000", operation="direct_call", target_rva="0x002eb620"),
                _point("alias_destination_load", 0x002EB1DF, "8b5608", operation="load_memory", base="ESI", field_offset=8, destination="EDX"),
                _point("alias_first_word_copy", 0x002EB1E9, "8b04f9", operation="indexed_load", base="ECX", index="EDI", scale=8, field_offset=0),
                _point("alias_first_word_store", 0x002EB1EC, "8902", operation="store_memory", base="EDX", field_offset=0, source="EAX"),
                _point("alias_second_word_copy", 0x002EB1EE, "8b44f904", operation="indexed_load", base="ECX", index="EDI", scale=8, field_offset=4),
                _point("alias_second_word_store", 0x002EB1F2, "894204", operation="store_memory", base="EDX", field_offset=4, source="EAX"),
                _point("external_capacity_compare", 0x002EB1F7, "3b460c", operation="compare_register_memory", register="EAX", base="ESI", field_offset=12),
                _point("external_capacity_helper", 0x002EB200, "e81b040000", operation="direct_call", target_rva="0x002eb620"),
                _point("external_destination_load", 0x002EB205, "8b4e08", operation="load_memory", base="ESI", field_offset=8, destination="ECX"),
                _point("external_first_word_load", 0x002EB20C, "8b07", operation="load_memory", base="EDI", field_offset=0, destination="EAX"),
                _point("external_first_word_store", 0x002EB20E, "8901", operation="store_memory", base="ECX", field_offset=0, source="EAX"),
                _point("external_second_word_load", 0x002EB210, "8b4704", operation="load_memory", base="EDI", field_offset=4, destination="EAX"),
                _point("external_second_word_store", 0x002EB213, "894104", operation="store_memory", base="ECX", field_offset=4, source="EAX"),
                _point("append_end_advance", 0x002EB216, "83460808", operation="add_memory_immediate", base="ESI", field_offset=8, value=8),
                _point("security_cookie_edge", 0x002EB222, "e8a3c20600", operation="direct_call", target_rva="0x003574ca"),
            ],
            "semantic_facts": {
                "argument_plus_4_nonzero_assertion_arm": True,
                "traversal_root_expression": "[argument_1+4]+0x34",
                "per_node_native_call_rvas": ["0x002eb19a", "0x002eb1ab"],
                "per_node_word_copy_offset": 20,
                "append_receiver_field_offsets": [4, 8, 12],
                "append_record_width_bytes": 8,
                "append_input_cases": ["internal_alias", "external_input"],
                "capacity_helper_call_rvas": ["0x002eb1da", "0x002eb200"],
                "source_semantic_names_assigned": False,
            },
        },
        {
            "role": "metatable_marker_truth_helper",
            "entry_rva": 0x002EB560,
            "body_size": 84,
            "body_sha256": "6f1c89224988d0fbcb9d3ded8b5c49f5652a871da1b7acb850dac37d75604bec",
            "cfg_canonical_sha256": "a468d1e0ea4bf5d3dc30bdd09b92be3aab731bddf256b6ddc176c5874c1b542e",
            "direct_calls": [
                (0x002EB565, "lua_getmetatable"),
                (0x002EB578, "lua_pushstring"),
                (0x002EB581, "lua_gettable"),
                (0x002EB58A, "lua_toboolean"),
                (0x002EB59A, "lua_settop"),
                (0x002EB5A7, "lua_settop"),
            ],
            "staged_dispatches": [],
            "call_r32": {},
            "points": [
                _point("lua_state_from_ecx", 0x002EB561, "8bf1", operation="register_copy", source="ECX", destination="ESI"),
                _point("input_index_argument", 0x002EB563, "52", operation="push", source="EDX"),
                _point("getmetatable_call", 0x002EB565, "ff1534657d00", api="lua_getmetatable", operation="direct_lua_call"),
                _point("no_metatable_test", 0x002EB56E, "85c0", operation="zero_test", register="EAX"),
                _point("no_metatable_branch", 0x002EB570, "743e", operation="branch_if_zero", target_rva="0x002eb5b0"),
                _point("marker_literal_argument", 0x002EB572, "6838c78300", operation="push_literal", literal_rva="0x0043c738"),
                _point("push_marker_call", 0x002EB578, "ff1594647d00", api="lua_pushstring", operation="direct_lua_call"),
                _point("metatable_index", 0x002EB57E, "6afe", operation="push_immediate", value=-2),
                _point("gettable_call", 0x002EB581, "ff15bc647d00", api="lua_gettable", operation="direct_lua_call", metamethod_capable=True),
                _point("field_value_index", 0x002EB587, "6aff", operation="push_immediate", value=-1),
                _point("toboolean_call", 0x002EB58A, "ff15f8647d00", api="lua_toboolean", operation="direct_lua_call"),
                _point("cleanup_index", 0x002EB593, "6afd", operation="push_immediate", value=-3),
                _point("false_field_branch", 0x002EB598, "740d", operation="branch_if_zero", target_rva="0x002eb5a7"),
                _point("truthy_cleanup_call", 0x002EB59A, "ff1510657d00", api="lua_settop", operation="direct_lua_call"),
                _point("truthy_result", 0x002EB5A3, "b001", operation="set_return_byte", value=1),
                _point("false_cleanup_call", 0x002EB5A7, "ff1510657d00", api="lua_settop", operation="direct_lua_call"),
                _point("false_result", 0x002EB5B0, "32c0", operation="zero_return_byte"),
            ],
            "semantic_facts": {
                "calling_convention_inputs": {"lua_state_register": "ECX", "stack_index_register": "EDX"},
                "marker_literal": "__luabind_classrep",
                "marker_lookup_api": "lua_gettable",
                "marker_lookup_raw_claimed": False,
                "no_metatable_result": False,
                "metatable_field_truth_conversion": "lua_toboolean",
                "metatable_arms_cleanup_index": -3,
                "pre_helper_stack_restored_on_normal_return": True,
                "native_type_or_class_identity_claimed": False,
            },
        },
        {
            "role": "two_table_filtered_assignment_helper",
            "entry_rva": 0x002EC050,
            "body_size": 180,
            "body_sha256": "858858c41d39d402bbe07a163aa922c44453c99e6cae68c8b14437ee9d41328e",
            "cfg_canonical_sha256": "2526d722ddf55499d0bb401fd37cc060e45d3fc8897bbd1cd0115b1807d83c86",
            "direct_calls": [
                (0x002EC054, "lua_pushnil"),
                (0x002EC05D, "lua_next"),
                (0x002EC08D, "lua_equal"),
                (0x002EC0B6, "lua_equal"),
                (0x002EC0D5, "lua_pushvalue"),
                (0x002EC0DE, "lua_insert"),
                (0x002EC0E7, "lua_settable"),
                (0x002EC0F3, "lua_next"),
            ],
            "staged_dispatches": [
                {
                    "api_name": "lua_pushstring",
                    "register": "ebx",
                    "stage_rva": 0x002EC06F,
                    "call_rvas": [0x002EC086, 0x002EC0AF],
                },
                {
                    "api_name": "lua_settop",
                    "register": "edi",
                    "stage_rva": 0x002EC076,
                    "call_rvas": [0x002EC09D, 0x002EC0A7, 0x002EC0C6, 0x002EC0D0],
                },
            ],
            "call_r32": {
                "EBX": [0x002EC086, 0x002EC0AF],
                "EDI": [0x002EC09D, 0x002EC0A7, 0x002EC0C6, 0x002EC0D0],
            },
            "points": [
                _point("lua_state_from_ecx", 0x002EC051, "8bf1", operation="register_copy", source="ECX", destination="ESI"),
                _point("iterator_seed_call", 0x002EC054, "ff15b8647d00", api="lua_pushnil", operation="direct_lua_call"),
                _point("second_entry_table_index", 0x002EC05A, "6afe", operation="push_immediate", value=-2),
                _point("first_next_call", 0x002EC05D, "ff15b4647d00", api="lua_next", operation="direct_lua_call"),
                _point("first_next_result_test", 0x002EC066, "85c0", operation="zero_test", register="EAX"),
                _point("empty_iteration_branch", 0x002EC068, "0f8494000000", operation="branch_if_zero", target_rva="0x002ec102"),
                _point("pushstring_ebx_stage", 0x002EC06F, "8b1d94647d00", operation="iat_load", api_name="lua_pushstring", destination="EBX"),
                _point("settop_edi_stage", 0x002EC076, "8b3d10657d00", operation="iat_load", api_name="lua_settop", destination="EDI"),
                _point("init_literal_argument", 0x002EC080, "68680f8200", operation="push_literal", literal_rva="0x00420f68"),
                _point("init_pushstring_call", 0x002EC086, "ffd3", operation="register_call", register="EBX", api_name="lua_pushstring"),
                _point("current_key_compare_index", 0x002EC088, "6afd", operation="push_immediate", value=-3),
                _point("init_literal_compare_index", 0x002EC08A, "6aff", operation="push_immediate", value=-1),
                _point("init_equal_call", 0x002EC08D, "ff15c4647d00", api="lua_equal", operation="direct_lua_call"),
                _point("init_equal_test", 0x002EC096, "85c0", operation="zero_test", register="EAX"),
                _point("init_not_equal_branch", 0x002EC098, "740a", operation="branch_if_zero", target_rva="0x002ec0a4"),
                _point("init_skip_cleanup_index", 0x002EC09A, "6afd", operation="push_immediate", value=-3),
                _point("init_skip_settop_call", 0x002EC09D, "ffd7", operation="register_call", register="EDI", api_name="lua_settop"),
                _point("comparison_literal_cleanup_index", 0x002EC0A4, "6afe", operation="push_immediate", value=-2),
                _point("comparison_literal_cleanup_call", 0x002EC0A7, "ffd7", operation="register_call", register="EDI", api_name="lua_settop"),
                _point("finalize_literal_argument", 0x002EC0A9, "680cc58300", operation="push_literal", literal_rva="0x0043c50c"),
                _point("finalize_pushstring_call", 0x002EC0AF, "ffd3", operation="register_call", register="EBX", api_name="lua_pushstring"),
                _point("finalize_equal_call", 0x002EC0B6, "ff15c4647d00", api="lua_equal", operation="direct_lua_call"),
                _point("finalize_equal_test", 0x002EC0BF, "85c0", operation="zero_test", register="EAX"),
                _point("finalize_not_equal_branch", 0x002EC0C1, "740a", operation="branch_if_zero", target_rva="0x002ec0cd"),
                _point("finalize_skip_cleanup_index", 0x002EC0C3, "6afd", operation="push_immediate", value=-3),
                _point("finalize_skip_settop_call", 0x002EC0C6, "ffd7", operation="register_call", register="EDI", api_name="lua_settop"),
                _point("second_comparison_cleanup_index", 0x002EC0CD, "6afe", operation="push_immediate", value=-2),
                _point("second_comparison_cleanup_call", 0x002EC0D0, "ffd7", operation="register_call", register="EDI", api_name="lua_settop"),
                _point("key_duplicate_index", 0x002EC0D2, "6afe", operation="push_immediate", value=-2),
                _point("key_duplicate_call", 0x002EC0D5, "ff15e4647d00", api="lua_pushvalue", operation="direct_lua_call"),
                _point("key_insert_index", 0x002EC0DB, "6afe", operation="push_immediate", value=-2),
                _point("key_insert_call", 0x002EC0DE, "ff1514657d00", api="lua_insert", operation="direct_lua_call"),
                _point("first_entry_destination_index", 0x002EC0E4, "6afb", operation="push_immediate", value=-5),
                _point("assignment_call", 0x002EC0E7, "ff1550657d00", api="lua_settable", operation="direct_lua_call", metamethod_capable=True),
                _point("loop_second_entry_table_index", 0x002EC0F0, "6afe", operation="push_immediate", value=-2),
                _point("loop_next_call", 0x002EC0F3, "ff15b4647d00", api="lua_next", operation="direct_lua_call"),
                _point("loop_result_test", 0x002EC0FC, "85c0", operation="zero_test", register="EAX"),
                _point("loop_back_branch", 0x002EC0FE, "7580", operation="branch_if_not_zero", target_rva="0x002ec080"),
            ],
            "semantic_facts": {
                "entry_stack_roles": ["first_entry_value", "second_entry_value"],
                "iteration_api": "lua_next",
                "iteration_table_entry_position": 2,
                "filtered_exact_keys": ["__init", "__finalize"],
                "comparison_api": "lua_equal",
                "equal_key_action": "retain_iterator_key_and_skip_assignment",
                "nonmatching_key_action": "request_lua_settable_into_first_entry_value",
                "assignment_destination_index_at_call": -5,
                "assignment_raw_claimed": False,
                "normal_exhaustion_retains_entry_values": 2,
            },
        },
    ],
    "literals": [
        {
            "role": "metatable_marker_key",
            "text": "__luabind_classrep",
            "rva": 0x0043C738,
            "byte_length_excluding_nul": 18,
            "nul_terminated_bytes_sha256": "5fa36f996468bb3565904a71089b4b7625279e0b4ef434b62c1c5f19b4762663",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
        {
            "role": "filtered_init_key",
            "text": "__init",
            "rva": 0x00420F68,
            "byte_length_excluding_nul": 6,
            "nul_terminated_bytes_sha256": "bbd60ce6705e249e0cffaa2e7e02fb2a3915650144e2faba59b0188a89895185",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
        {
            "role": "filtered_finalize_key",
            "text": "__finalize",
            "rva": 0x0043C50C,
            "byte_length_excluding_nul": 10,
            "nul_terminated_bytes_sha256": "2da9eac9965b6b70aa210a588888733805c3214ecd627e37afd1aa1909b100b7",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
    ],
    "native_edges": [
        {"role": "argument_nonzero_assertion", "instruction_rva": 0x002EB16E, "source_entry_rva": 0x002EB140, "target_entry_rva": 0x00379CC2, "encoded": "e84feb0800", "condition": "argument_plus_4_zero"},
        {"role": "per_node_helper_one", "instruction_rva": 0x002EB19A, "source_entry_rva": 0x002EB140, "target_entry_rva": 0x002E81F0, "encoded": "e851d0ffff", "condition": "each_traversed_node"},
        {"role": "per_node_helper_two", "instruction_rva": 0x002EB1AB, "source_entry_rva": 0x002EB140, "target_entry_rva": 0x0006DF30, "encoded": "e8802dd8ff", "condition": "each_traversed_node"},
        {"role": "alias_capacity_helper", "instruction_rva": 0x002EB1DA, "source_entry_rva": 0x002EB140, "target_entry_rva": 0x002EB620, "encoded": "e841040000", "condition": "internal_alias_and_end_equals_capacity"},
        {"role": "external_capacity_helper", "instruction_rva": 0x002EB200, "source_entry_rva": 0x002EB140, "target_entry_rva": 0x002EB620, "encoded": "e81b040000", "condition": "external_input_and_end_equals_capacity"},
        {"role": "security_cookie_helper", "instruction_rva": 0x002EB222, "source_entry_rva": 0x002EB140, "target_entry_rva": 0x003574CA, "encoded": "e8a3c20600", "condition": None},
    ],
    "target_references": [
        {"instruction_rva": 0x002E7CE0, "owner_entry_rva": 0x002E7970, "target_rva": 0x002EB140, "encoded": "e85b340000", "operand_index": 0},
        {"instruction_rva": 0x002EC15B, "owner_entry_rva": 0x002EC110, "target_rva": 0x002EB560, "encoded": "e800f4ffff", "operand_index": 0},
        {"instruction_rva": 0x002EC17F, "owner_entry_rva": 0x002EC110, "target_rva": 0x002EB560, "encoded": "e8dcf3ffff", "operand_index": 0},
        {"instruction_rva": 0x002EC1B8, "owner_entry_rva": 0x002EC110, "target_rva": 0x002EB140, "encoded": "e883efffff", "operand_index": 0},
        {"instruction_rva": 0x002EC1DB, "owner_entry_rva": 0x002EC110, "target_rva": 0x002EC050, "encoded": "e870feffff", "operand_index": 0},
        {"instruction_rva": 0x002EC1FE, "owner_entry_rva": 0x002EC110, "target_rva": 0x002EC050, "encoded": "e84dfeffff", "operand_index": 0},
    ],
}

_PROFILES = {_SEALED_PROFILE["executable_sha256"]: _SEALED_PROFILE}


def _source_identity(
    value: Mapping[str, Any], kind: str, expected_sha256: str, label: str
) -> dict[str, Any]:
    if value.get("analysis_kind") != kind:
        raise NativeLuaClassReturnHelperChainError(f"{label} analysis kind differs")
    digest = _canonical_sha256(value)
    if digest != expected_sha256:
        raise NativeLuaClassReturnHelperChainError(f"{label} canonical identity differs")
    return {"analysis_kind": kind, "canonical_sha256": digest}


def _atlas_identity(program_facts: Mapping[str, Any]) -> dict[str, Any]:
    source = _source_identity(
        program_facts,
        "pe_ghidra_program_facts",
        _FACTS_SHA256,
        "program facts",
    )
    summary = _mapping(program_facts.get("summary"), "program_facts.summary")
    return {
        **source,
        "function_count": summary.get("function_count"),
        "body_range_count": summary.get("body_range_count"),
        "function_body_bytes": summary.get("function_body_bytes"),
    }


def _class_factory_identity(class_factory: Mapping[str, Any]) -> dict[str, Any]:
    return _source_identity(
        class_factory,
        CLASS_FACTORY_ANALYSIS_KIND,
        _CLASS_FACTORY_SHA256,
        "class factory",
    )


def _direct_identity(direct_calls: Mapping[str, Any]) -> dict[str, Any]:
    return _source_identity(
        direct_calls,
        DIRECT_CALL_ANALYSIS_KIND,
        _DIRECT_SHA256,
        "direct-call census",
    )


def _expected_literal_record(expected: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "role": expected["role"],
        "text": expected["text"],
        "rva": _hex(expected["rva"]),
        "byte_length_excluding_nul": expected["byte_length_excluding_nul"],
        "nul_terminated_bytes_sha256": expected["nul_terminated_bytes_sha256"],
        "section_name": expected["section_name"],
        "section_rva": _hex(expected["section_rva"]),
        "section_characteristics": _hex(expected["section_characteristics"]),
        "section_writable": False,
    }


def _literal_record(
    data: bytes, image: Any, expected: Mapping[str, Any]
) -> dict[str, Any]:
    rva = expected["rva"]
    raw = bytearray()
    first_offset: int | None = None
    prior_offset: int | None = None
    for delta in range(MAX_LITERAL_BYTES + 1):
        offset = image.rva_to_file_offset(rva + delta)
        if offset is None or offset >= len(data):
            raise NativeLuaClassReturnHelperChainError(
                "literal is not bounded file-backed data"
            )
        if first_offset is None:
            first_offset = offset
        if prior_offset is not None and offset != prior_offset + 1:
            raise NativeLuaClassReturnHelperChainError(
                "literal bytes are not contiguous"
            )
        prior_offset = offset
        byte = data[offset]
        raw.append(byte)
        if byte == 0:
            break
        if byte < 0x20 or byte > 0x7E:
            raise NativeLuaClassReturnHelperChainError(
                "literal is not printable ASCII"
            )
    else:
        raise NativeLuaClassReturnHelperChainError("literal exceeds bounded length")
    if (
        len(raw) < 2
        or raw[-1] != 0
        or first_offset is None
        or prior_offset is None
    ):
        raise NativeLuaClassReturnHelperChainError("literal lacks a NUL terminator")
    section = image.section_for_offset(first_offset)
    if (
        section is None
        or section.characteristics & PE_SECTION_WRITABLE
        or image.section_for_offset(prior_offset) != section
    ):
        raise NativeLuaClassReturnHelperChainError(
            "literal is not in one non-writable section"
        )
    try:
        text = bytes(raw[:-1]).decode("ascii")
    except UnicodeDecodeError as exc:  # pragma: no cover - guarded above
        raise NativeLuaClassReturnHelperChainError("literal is not ASCII") from exc
    observed = {
        "role": expected["role"],
        "text": text,
        "rva": _hex(rva),
        "byte_length_excluding_nul": len(raw) - 1,
        "nul_terminated_bytes_sha256": hashlib.sha256(bytes(raw)).hexdigest(),
        "section_name": section.name,
        "section_rva": _hex(section.virtual_address),
        "section_characteristics": _hex(section.characteristics),
        "section_writable": False,
    }
    if observed != _expected_literal_record(expected):
        raise NativeLuaClassReturnHelperChainError(
            f"{expected['role']} literal identity changed"
        )
    return observed


def _direct_call_map(
    direct_calls: Mapping[str, Any],
) -> dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]]:
    result: dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    for record_index, raw_record in enumerate(
        _array(direct_calls.get("records"), "direct_calls.records")
    ):
        record = _mapping(raw_record, f"direct_calls.records[{record_index}]")
        for raw_call in _array(
            record.get("direct_lua_import_calls"),
            f"direct_calls.records[{record_index}].direct_lua_import_calls",
        ):
            call = _mapping(raw_call, "direct Lua call")
            rva = _rva(call.get("call_rva"), "direct Lua call RVA")
            if rva in result:
                raise NativeLuaClassReturnHelperChainError(
                    "direct Lua call RVAs repeat"
                )
            result[rva] = record, call
    return result


def _direct_call_records(
    expected: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
) -> list[dict[str, Any]]:
    entry = expected["entry_rva"]
    call_map = _direct_call_map(direct_calls)
    expected_specs = expected["direct_calls"]
    observed_for_entry = sorted(
        (
            rva,
            joined[1].get("import_name"),
        )
        for rva, joined in call_map.items()
        if joined[0].get("entry_rva") == _hex(entry)
    )
    if observed_for_entry != sorted(expected_specs):
        raise NativeLuaClassReturnHelperChainError(
            f"{_hex(entry)} direct Lua-call partition changed"
        )
    result: list[dict[str, Any]] = []
    for rva, api_name in expected_specs:
        record, call = call_map[rva]
        if (
            call.get("import_name") != api_name
            or call.get("library") != LUA_LIBRARY
            or call.get("call_form") != DIRECT_CALL_FORM
            or record.get("atlas_record_sha256") is None
        ):
            raise NativeLuaClassReturnHelperChainError(
                f"{_hex(rva)} direct Lua-call identity changed"
            )
        result.append(dict(call))
    return result


def _expected_point_record(spec: Mapping[str, Any]) -> dict[str, Any]:
    encoded = spec["encoded"]
    return {
        "role": spec["role"],
        "rva": _hex(spec["rva"]),
        "size": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "direct_lua_import": spec["api"],
        "meaning": dict(spec["meaning"]),
    }


def _point_record(
    instruction: Any, image_base: int, spec: Mapping[str, Any]
) -> dict[str, Any]:
    if (
        instruction.address - image_base != spec["rva"]
        or bytes(instruction.bytes) != spec["encoded"]
    ):
        raise NativeLuaClassReturnHelperChainError(
            f"reviewed instruction {spec['role']} changed"
        )
    return {
        "role": spec["role"],
        **_instruction_fact(instruction, image_base),
        "direct_lua_import": spec["api"],
        "meaning": dict(spec["meaning"]),
    }


def _expected_call_r32_audit(expected: Mapping[str, Any]) -> list[dict[str, Any]]:
    retained = expected["call_r32"]
    return [
        {
            "register": register,
            "call_rvas": [_hex(rva) for rva in retained.get(register, [])],
        }
        for register in _REGISTER_NAMES
    ]


def _call_r32_audit(
    instructions: list[Any], expected: Mapping[str, Any]
) -> list[dict[str, Any]]:
    import capstone.x86_const as x86

    for instruction in instructions:
        encoded = bytes(instruction.bytes)
        if len(encoded) == 2 and encoded[0] == 0xFF and 0xD0 <= encoded[1] <= 0xD7:
            register = _REGISTER_NAMES[encoded[1] - 0xD0]
            if (
                instruction.id != x86.X86_INS_CALL
                or len(instruction.operands) != 1
                or instruction.operands[0].type != x86.X86_OP_REG
                or instruction.reg_name(instruction.operands[0].reg).upper()
                != register
            ):
                raise NativeLuaClassReturnHelperChainError(
                    "call-r32 bytes do not decode as the expected register call"
                )
    if not instructions:
        raise NativeLuaClassReturnHelperChainError("reviewed helper decoded empty")
    image_base = instructions[0].address - expected["entry_rva"]
    observed = []
    for register in _REGISTER_NAMES:
        rvas = []
        for instruction in instructions:
            encoded = bytes(instruction.bytes)
            if (
                len(encoded) == 2
                and encoded[0] == 0xFF
                and encoded[1] == 0xD0 + _REGISTER_NAMES.index(register)
            ):
                rvas.append(_hex(instruction.address - image_base))
        observed.append({"register": register, "call_rvas": rvas})
    if observed != _expected_call_r32_audit(expected):
        raise NativeLuaClassReturnHelperChainError(
            f"{_hex(expected['entry_rva'])} call-r32 partition changed"
        )
    return observed


def _function_profiles(profile: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return sorted(profile["functions"], key=lambda item: item["entry_rva"])


def _dispatch_records(
    expected: Mapping[str, Any],
    graph: Mapping[str, Any],
    image_base: int,
    imports: Mapping[str, Mapping[str, Any]],
    program_facts: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    try:
        return _staged_dispatch_records(
            expected,
            graph,
            image_base,
            imports,
            program_facts,
            functions,
        )
    except NativeLuaSuperRebindingError as exc:
        raise NativeLuaClassReturnHelperChainError(
            f"staged Lua dispatch proof failed: {exc}"
        ) from exc


def _build_function_records(
    data: bytes,
    image: Any,
    decoder: Any,
    program_facts: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import capstone
    import capstone.x86_const as x86

    functions = _atlas_functions(program_facts)
    call_map = _direct_call_map(direct_calls)
    try:
        imports = _lua_import_map(direct_calls)
    except NativeLuaSuperRebindingError as exc:
        raise NativeLuaClassReturnHelperChainError(
            f"Lua import map failed: {exc}"
        ) from exc
    body_records: list[dict[str, Any]] = []
    graphs: list[dict[str, Any]] = []
    decoder.detail = True
    for expected in _function_profiles(profile):
        entry = expected["entry_rva"]
        function = functions.get(entry)
        if function is None or function.get("thunk") is not False:
            raise NativeLuaClassReturnHelperChainError(
                "reviewed helper is absent or a thunk"
            )
        if (
            function.get("body_size") != expected["body_size"]
            or function.get("body_sha256") != expected["body_sha256"]
        ):
            raise NativeLuaClassReturnHelperChainError("reviewed helper body changed")
        ranges = _array(function.get("ranges"), "helper ranges")
        if len(ranges) != 1:
            raise NativeLuaClassReturnHelperChainError(
                "reviewed helper no longer has one atlas range"
            )
        raw_range = _mapping(ranges[0], "helper range")
        start = _rva(raw_range.get("start_rva"), "helper range start")
        size = raw_range.get("size")
        if start != entry or type(size) is not int or size != expected["body_size"]:
            raise NativeLuaClassReturnHelperChainError(
                "reviewed helper range changed"
            )
        instructions = _decode_range(data, image, start, size, decoder)
        encoded_body = b"".join(bytes(instruction.bytes) for instruction in instructions)
        if (
            len(encoded_body) != size
            or hashlib.sha256(encoded_body).hexdigest() != expected["body_sha256"]
        ):
            raise NativeLuaClassReturnHelperChainError(
                "reviewed helper PE body hash changed"
            )
        graph = _enhanced_cfg(
            instructions,
            image.image_base,
            (start, size),
            capstone,
            x86,
        )
        graph = _with_edi_writes(graph, instructions, x86)
        graph["caller_entry_rva"] = _hex(entry)
        graph_sha256 = _canonical_sha256(graph)
        if graph_sha256 != expected["cfg_canonical_sha256"]:
            raise NativeLuaClassReturnHelperChainError("reviewed helper CFG changed")
        by_rva = {
            instruction.address - image.image_base: instruction
            for instruction in instructions
        }
        points = []
        for spec in expected["points"]:
            instruction = by_rva.get(spec["rva"])
            if instruction is None:
                raise NativeLuaClassReturnHelperChainError(
                    "reviewed instruction is absent from helper body"
                )
            point = _point_record(instruction, image.image_base, spec)
            api = point["direct_lua_import"]
            if api is not None:
                joined = call_map.get(spec["rva"])
                if (
                    joined is None
                    or joined[0].get("entry_rva") != _hex(entry)
                    or joined[1].get("import_name") != api
                    or joined[1].get("library") != LUA_LIBRARY
                    or joined[1].get("call_form") != DIRECT_CALL_FORM
                    or joined[1].get("instruction_sha256") != point["sha256"]
                ):
                    raise NativeLuaClassReturnHelperChainError(
                        f"reviewed {api} call does not join direct-call census"
                    )
            points.append(point)
        direct_records = _direct_call_records(expected, direct_calls)
        for direct in direct_records:
            instruction = by_rva.get(_rva(direct["call_rva"], "direct call RVA"))
            if instruction is None or (
                instruction.size,
                hashlib.sha256(bytes(instruction.bytes)).hexdigest(),
            ) != (
                direct["instruction_size"],
                direct["instruction_sha256"],
            ):
                raise NativeLuaClassReturnHelperChainError(
                    "direct Lua call does not join helper body"
                )
        staged = _dispatch_records(
            expected,
            graph,
            image.image_base,
            imports,
            program_facts,
            functions,
        )
        call_r32 = _call_r32_audit(instructions, expected)
        graphs.append(graph)
        body_records.append(
            {
                "role": expected["role"],
                "entry_rva": _hex(entry),
                "atlas_record_sha256": atlas_record_sha256(function),
                "body_size": function["body_size"],
                "body_sha256": function["body_sha256"],
                "range_start_rva": _hex(start),
                "range_size": size,
                "control_flow_graph_canonical_sha256": graph_sha256,
                "reviewed_points": points,
                "direct_lua_calls": direct_records,
                "staged_lua_dispatches": staged,
                "call_r32_audit": call_r32,
                "register_call_partition_complete": True,
                "semantic_facts": dict(expected["semantic_facts"]),
            }
        )
    return body_records, graphs


def _returned_callback_edges(
    class_factory: Mapping[str, Any], profile: Mapping[str, Any]
) -> list[dict[str, Any]]:
    targets = {item["entry_rva"] for item in profile["functions"]}
    matches = [
        dict(_mapping(raw, "class-factory native edge"))
        for raw in _array(class_factory.get("native_edges"), "class_factory.native_edges")
        if isinstance(raw, Mapping)
        and _rva(raw.get("source_entry_rva"), "class-factory edge source")
        == _RETURNED_CALLBACK
        and _rva(raw.get("target_entry_rva"), "class-factory edge target")
        in targets
    ]
    matches.sort(
        key=lambda item: _rva(
            _mapping(item.get("instruction"), "class-factory edge instruction").get(
                "rva"
            ),
            "class-factory edge instruction RVA",
        )
    )
    expected_pairs = [
        (item["instruction_rva"], item["target_rva"])
        for item in profile["target_references"]
        if item["owner_entry_rva"] == _RETURNED_CALLBACK
    ]
    observed_pairs = [
        (
            _rva(
                _mapping(item.get("instruction"), "class-factory edge instruction").get(
                    "rva"
                ),
                "class-factory edge instruction RVA",
            ),
            _rva(item.get("target_entry_rva"), "class-factory edge target"),
        )
        for item in matches
    ]
    if observed_pairs != expected_pairs:
        raise NativeLuaClassReturnHelperChainError(
            "returned-callback helper edge partition changed"
        )
    return matches


def _helper_targets(
    bodies: list[Mapping[str, Any]], profile: Mapping[str, Any], image_base: int
) -> list[dict[str, Any]]:
    by_entry = {_rva(body["entry_rva"], "helper body entry"): body for body in bodies}
    result = []
    for expected in _function_profiles(profile):
        entry = expected["entry_rva"]
        body = by_entry.get(entry)
        if body is None:
            raise NativeLuaClassReturnHelperChainError(
                "helper target lacks a sealed body"
            )
        result.append(
            {
                "role": expected["role"],
                "entry_rva": body["entry_rva"],
                "entry_va": _hex(image_base + entry),
                "atlas_record_sha256": body["atlas_record_sha256"],
                "body_size": body["body_size"],
                "body_sha256": body["body_sha256"],
            }
        )
    return result


def _declared_direct_call_map(
    program_facts: Mapping[str, Any],
) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for index, raw in enumerate(
        _array(
            program_facts.get("ghidra_declared_direct_calls"),
            "program_facts.ghidra_declared_direct_calls",
        )
    ):
        edge = _mapping(raw, f"ghidra_declared_direct_calls[{index}]")
        rva = _rva(edge.get("instruction_rva"), "declared call RVA")
        if rva in result:
            raise NativeLuaClassReturnHelperChainError(
                "declared direct call RVAs repeat"
            )
        result[rva] = edge
    return result


def _normalized_declared_edge(edge: Mapping[str, Any]) -> dict[str, Any]:
    target_name = edge.get("target_name")
    if type(target_name) is not str:
        raise NativeLuaClassReturnHelperChainError(
            "declared direct edge target name is malformed"
        )
    return {
        "instruction_rva": edge.get("instruction_rva"),
        "source_entry_rva": edge.get("source_entry_rva"),
        "target_entry_rva": edge.get("target_entry_rva"),
        "target_rva": edge.get("target_rva"),
        "target_name_sha256": hashlib.sha256(target_name.encode("utf-8")).hexdigest(),
    }


def _native_edge_record(
    expected: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    source = functions.get(expected["source_entry_rva"])
    target = functions.get(expected["target_entry_rva"])
    declared = _declared_direct_call_map(program_facts).get(
        expected["instruction_rva"]
    )
    if source is None or target is None or declared is None:
        raise NativeLuaClassReturnHelperChainError(
            "native edge lacks an exact atlas/Ghidra join"
        )
    if (
        _rva(declared.get("source_entry_rva"), "declared source")
        != expected["source_entry_rva"]
        or _rva(declared.get("target_entry_rva"), "declared target entry")
        != expected["target_entry_rva"]
        or _rva(declared.get("target_rva"), "declared target")
        != expected["target_entry_rva"]
    ):
        raise NativeLuaClassReturnHelperChainError(
            "native edge declaration changed"
        )
    encoded = bytes.fromhex(expected["encoded"])
    return {
        "role": expected["role"],
        "source_entry_rva": _hex(expected["source_entry_rva"]),
        "source_atlas_record_sha256": atlas_record_sha256(source),
        "instruction": {
            "rva": _hex(expected["instruction_rva"]),
            "size": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        },
        "target_entry_rva": _hex(expected["target_entry_rva"]),
        "target_atlas_record_sha256": atlas_record_sha256(target),
        "target_body_size": target["body_size"],
        "target_body_sha256": target["body_sha256"],
        "condition": expected["condition"],
        "ghidra_declared_direct_edge": _normalized_declared_edge(declared),
    }


def _native_edges(
    profile: Mapping[str, Any], program_facts: Mapping[str, Any]
) -> list[dict[str, Any]]:
    functions = _atlas_functions(program_facts)
    return [
        _native_edge_record(expected, program_facts, functions)
        for expected in sorted(
            profile["native_edges"], key=lambda item: item["instruction_rva"]
        )
    ]


def _expected_reference(
    expected: Mapping[str, Any],
    image_base: int,
    functions: Mapping[int, Mapping[str, Any]],
    declared: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    owner = functions.get(expected["owner_entry_rva"])
    target = functions.get(expected["target_rva"])
    edge = declared.get(expected["instruction_rva"])
    if owner is None or target is None or edge is None:
        raise NativeLuaClassReturnHelperChainError(
            "helper reference lacks an atlas/Ghidra join"
        )
    if (
        _rva(edge.get("source_entry_rva"), "reference source")
        != expected["owner_entry_rva"]
        or _rva(edge.get("target_entry_rva"), "reference target entry")
        != expected["target_rva"]
        or _rva(edge.get("target_rva"), "reference target")
        != expected["target_rva"]
    ):
        raise NativeLuaClassReturnHelperChainError(
            "helper reference Ghidra edge changed"
        )
    encoded = bytes.fromhex(expected["encoded"])
    return {
        "instruction_rva": _hex(expected["instruction_rva"]),
        "instruction_size": len(encoded),
        "instruction_sha256": hashlib.sha256(encoded).hexdigest(),
        "owner_entry_rva": _hex(expected["owner_entry_rva"]),
        "owner_atlas_record_sha256": atlas_record_sha256(owner),
        "target_rva": _hex(expected["target_rva"]),
        "target_atlas_record_sha256": atlas_record_sha256(target),
        "target_va": _hex(image_base + expected["target_rva"]),
        "operand_class": "immediate",
        "operand_index": expected["operand_index"],
        "use_class": "direct_call",
        "call_form": "x86_relative_near_call_e8",
        "ghidra_declared_direct_edge": _normalized_declared_edge(edge),
    }


def _reference_aggregates(references: list[Mapping[str, Any]]) -> dict[str, Any]:
    owners = {item["owner_entry_rva"] for item in references}
    classes = [item["use_class"] for item in references]
    return {
        "reference_count": len(references),
        "direct_call_count": classes.count("direct_call"),
        "comparison_count": classes.count("comparison"),
        "other_address_count": classes.count("other_address"),
        "memory_operand_count": sum(
            item["operand_class"] == "absolute_memory" for item in references
        ),
        "owner_count": len(owners),
        "returned_callback_reference_count": sum(
            item["owner_entry_rva"] == _hex(_RETURNED_CALLBACK)
            for item in references
        ),
        "alternate_owner_reference_count": sum(
            item["owner_entry_rva"] != _hex(_RETURNED_CALLBACK)
            for item in references
        ),
    }


def _expected_reference_scan(
    program_facts: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    functions = _atlas_functions(program_facts)
    declared = _declared_direct_call_map(program_facts)
    image_base = _rva(
        _mapping(program_facts.get("ghidra"), "program_facts.ghidra").get(
            "image_base"
        ),
        "image base",
    )
    references = [
        _expected_reference(item, image_base, functions, declared)
        for item in profile["target_references"]
    ]
    fact_summary = _mapping(program_facts.get("summary"), "program_facts.summary")
    direct_summary = _mapping(direct_calls.get("summary"), "direct_calls.summary")
    targets = sorted(item["entry_rva"] for item in profile["functions"])
    return {
        "target_rvas": [_hex(value) for value in targets],
        "target_vas": [_hex(image_base + value) for value in targets],
        "scope": {
            "atlas_function_count": fact_summary.get("function_count"),
            "atlas_body_range_count": fact_summary.get("body_range_count"),
            "decoded_bytes": fact_summary.get("function_body_bytes"),
            "decoded_instructions": direct_summary.get("decoded_instructions"),
            "all_declared_ranges_decoded": True,
            "operand_classes": ["absolute_memory", "immediate"],
        },
        "references": references,
        "aggregates": _reference_aggregates(references),
    }


def _whole_atlas_reference_scan(
    data: bytes,
    image: Any,
    decoder: Any,
    program_facts: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    import capstone.x86_const as x86

    decoder.detail = True
    functions = _atlas_functions(program_facts)
    declared = _declared_direct_call_map(program_facts)
    target_vas = {
        image.image_base + item["entry_rva"]: item["entry_rva"]
        for item in profile["functions"]
    }
    references: list[dict[str, Any]] = []
    range_count = 0
    byte_count = 0
    instruction_count = 0
    for owner, function in sorted(functions.items()):
        owner_hash = atlas_record_sha256(function)
        for raw_range in _array(function.get("ranges"), "atlas ranges"):
            span = _mapping(raw_range, "atlas range")
            start = _rva(span.get("start_rva"), "atlas range start")
            size = span.get("size")
            if type(size) is not int or size <= 0:
                raise NativeLuaClassReturnHelperChainError(
                    "atlas range size is invalid"
                )
            instructions = _decode_range(data, image, start, size, decoder)
            range_count += 1
            byte_count += size
            instruction_count += len(instructions)
            for instruction in instructions:
                instruction_rva = instruction.address - image.image_base
                for operand_index, operand in enumerate(instruction.operands):
                    operand_class: str | None = None
                    value: int | None = None
                    if operand.type == x86.X86_OP_IMM:
                        operand_class = "immediate"
                        value = int(operand.imm) & 0xFFFFFFFF
                    elif (
                        operand.type == x86.X86_OP_MEM
                        and operand.mem.base == x86.X86_REG_INVALID
                        and operand.mem.index == x86.X86_REG_INVALID
                    ):
                        operand_class = "absolute_memory"
                        value = int(operand.mem.disp) & 0xFFFFFFFF
                    if value not in target_vas:
                        continue
                    target_rva = target_vas[value]
                    if instruction.id == x86.X86_INS_CALL:
                        use_class = "direct_call"
                    elif instruction.id in {x86.X86_INS_CMP, x86.X86_INS_TEST}:
                        use_class = "comparison"
                    else:
                        use_class = "other_address"
                    encoded = bytes(instruction.bytes)
                    edge = declared.get(instruction_rva)
                    references.append(
                        {
                            "instruction_rva": _hex(instruction_rva),
                            "instruction_size": instruction.size,
                            "instruction_sha256": hashlib.sha256(encoded).hexdigest(),
                            "owner_entry_rva": _hex(owner),
                            "owner_atlas_record_sha256": owner_hash,
                            "target_rva": _hex(target_rva),
                            "target_atlas_record_sha256": atlas_record_sha256(
                                functions[target_rva]
                            ),
                            "target_va": _hex(value),
                            "operand_class": operand_class,
                            "operand_index": operand_index,
                            "use_class": use_class,
                            "call_form": (
                                "x86_relative_near_call_e8"
                                if len(encoded) == 5 and encoded[0] == 0xE8
                                else None
                            ),
                            "ghidra_declared_direct_edge": (
                                None
                                if edge is None
                                else _normalized_declared_edge(edge)
                            ),
                        }
                    )
    references.sort(
        key=lambda item: (
            _rva(item["instruction_rva"], "reference instruction"),
            item["operand_index"],
        )
    )
    observed = {
        "target_rvas": [_hex(value) for value in sorted(target_vas.values())],
        "target_vas": [_hex(value) for value in sorted(target_vas)],
        "scope": {
            "atlas_function_count": len(functions),
            "atlas_body_range_count": range_count,
            "decoded_bytes": byte_count,
            "decoded_instructions": instruction_count,
            "all_declared_ranges_decoded": True,
            "operand_classes": ["absolute_memory", "immediate"],
        },
        "references": references,
        "aggregates": _reference_aggregates(references),
    }
    expected = _expected_reference_scan(program_facts, direct_calls, profile)
    if observed != expected:
        raise NativeLuaClassReturnHelperChainError(
            "complete helper target-reference partition changed"
        )
    return observed


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    bodies = _array(result.get("function_bodies"), "function_bodies")
    graphs = _array(result.get("control_flow_graphs"), "control_flow_graphs")
    direct_count = sum(
        len(_array(_mapping(body, "helper body").get("direct_lua_calls"), "direct calls"))
        for body in bodies
    )
    dispatches = [
        dispatch
        for body in bodies
        for dispatch in _array(
            _mapping(body, "helper body").get("staged_lua_dispatches"),
            "staged dispatches",
        )
    ]
    staged_count = sum(
        len(_array(_mapping(item, "staged dispatch").get("call_sites"), "call sites"))
        for item in dispatches
    )
    native_edges = _array(result.get("native_edges"), "native_edges")
    scan = _mapping(result.get("whole_atlas_reference_scan"), "reference scan")
    aggregates = _mapping(scan.get("aggregates"), "reference aggregates")
    return {
        "reviewed_helper_count": len(bodies),
        "reviewed_helper_bytes": sum(body["body_size"] for body in bodies),
        "sealed_control_flow_graph_count": len(graphs),
        "sealed_control_flow_graph_node_count": sum(
            graph["node_count"] for graph in graphs
        ),
        "sealed_control_flow_graph_edge_count": sum(
            graph["edge_count"] for graph in graphs
        ),
        "direct_lua_call_count": direct_count,
        "staged_lua_dispatch_count": len(dispatches),
        "staged_lua_call_count": staged_count,
        "total_lua_call_count": direct_count + staged_count,
        "call_r32_count": sum(
            len(item["call_rvas"])
            for body in bodies
            for item in body["call_r32_audit"]
        ),
        "literal_count": len(_array(result.get("literals"), "literals")),
        "selected_native_edge_count": len(native_edges),
        "unique_native_edge_target_count": len(
            {edge["target_entry_rva"] for edge in native_edges}
        ),
        "helper_target_count": len(
            _array(result.get("helper_targets"), "helper_targets")
        ),
        "class_factory_helper_edge_count": len(
            _array(
                result.get("returned_callback_edges"), "returned_callback_edges"
            )
        ),
        "target_reference_count": aggregates["reference_count"],
        "target_reference_direct_call_count": aggregates["direct_call_count"],
        "target_reference_comparison_count": aggregates["comparison_count"],
        "target_reference_other_address_count": aggregates["other_address_count"],
        "target_reference_memory_operand_count": aggregates[
            "memory_operand_count"
        ],
        "target_reference_owner_count": aggregates["owner_count"],
        "alternate_owner_reference_count": aggregates[
            "alternate_owner_reference_count"
        ],
        "schema_violations": 0,
    }


def _decoder_contract() -> dict[str, Any]:
    return {
        "name": "capstone",
        "version": SUPPORTED_CAPSTONE_VERSION,
        "architecture": "x86",
        "mode_bits": 32,
        "operand_classes": ["absolute_memory", "immediate"],
        "cfg_register_write_fields": [
            "writes_ebx",
            "writes_esi",
            "writes_edi",
            "writes_esp",
        ],
        "register_call_encoding_audit": [
            {"register": register, "encoding": f"ff{0xd0 + index:02x}"}
            for index, register in enumerate(_REGISTER_NAMES)
        ],
    }


def _preflight_identities(
    class_factory: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> tuple[
    Mapping[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    identity = _mapping(program_facts.get("identity"), "program_facts.identity")
    profile = _PROFILES.get(identity.get("executable_sha256"))
    if profile is None:
        raise NativeLuaClassReturnHelperChainError(
            "build identity has no reviewed class-return helper profile"
        )
    for label, document in (
        ("class factory", class_factory),
        ("direct-call census", direct_calls),
    ):
        if document.get("build_identity") != dict(identity):
            raise NativeLuaClassReturnHelperChainError(
                f"{label} build identity differs from program facts"
            )
    return (
        profile,
        _atlas_identity(program_facts),
        _direct_identity(direct_calls),
        _class_factory_identity(class_factory),
    )


def _build_native_lua_class_return_helper_chain_impl(
    executable: Path,
    class_factory: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact callback-side class-return helper artifact."""
    for value, label in (
        (class_factory, "class_factory"),
        (direct_calls, "direct_calls"),
        (program_facts, "program_facts"),
        (inventory, "inventory"),
    ):
        _validate_json_tree(value, label)
    try:
        receipt = validate_native_lua_direct_call_census(
            executable,
            direct_calls,
            program_facts,
            inventory=inventory,
        )
        profile, atlas, direct_identity, class_identity = _preflight_identities(
            class_factory, direct_calls, program_facts
        )
        if (
            receipt.get("status") != "verified"
            or receipt.get("evidence_sha256") != _DIRECT_SHA256
        ):
            raise NativeLuaClassReturnHelperChainError(
                "direct-call prerequisite exact verification failed"
            )
        data, image, executable_sha256 = _load_executable(executable)
        decoder, _ = _decoder()
        identity = _mapping(program_facts.get("identity"), "program_facts.identity")
        if (
            executable_sha256 != profile["executable_sha256"]
            or identity.get("executable_sha256") != executable_sha256
            or identity.get("executable_size") != len(data)
            or identity.get("architecture") != image.architecture
        ):
            raise NativeLuaClassReturnHelperChainError(
                "executable identity differs from reviewed program facts"
            )
        bodies, graphs = _build_function_records(
            data,
            image,
            decoder,
            program_facts,
            direct_calls,
            profile,
        )
        result: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": ANALYSIS_KIND,
            "build_identity": dict(identity),
            "atlas": atlas,
            "direct_call_census": direct_identity,
            "class_factory_chain": class_identity,
            "decoder": _decoder_contract(),
            "returned_callback_edges": _returned_callback_edges(
                class_factory, profile
            ),
            "helper_targets": _helper_targets(bodies, profile, image.image_base),
            "literals": [
                _literal_record(data, image, expected)
                for expected in profile["literals"]
            ],
            "function_bodies": bodies,
            "control_flow_graphs": graphs,
            "native_edges": _native_edges(profile, program_facts),
            "whole_atlas_reference_scan": _whole_atlas_reference_scan(
                data,
                image,
                decoder,
                program_facts,
                direct_calls,
                profile,
            ),
            "method": _METHOD,
        }
        result["summary"] = _summary(result)
        _assert_publication_safe(result)
        if _load_executable(executable)[2] != executable_sha256:
            raise NativeLuaClassReturnHelperChainError(
                "executable changed during exact rebuild"
            )
        validate_native_lua_class_return_helper_chain_structure(
            result,
            class_factory,
            direct_calls,
            program_facts,
        )
        return result
    except NativeLuaClassReturnHelperChainError:
        raise
    except (
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        NativeLuaClassFactoryChainError,
        NativeLuaSuperRebindingError,
        PEAnchorError,
        OSError,
    ) as exc:
        raise NativeLuaClassReturnHelperChainError(str(exc)) from exc


def build_native_lua_class_return_helper_chain(
    executable: Path,
    class_factory: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact callback-side class-return helper artifact."""
    try:
        return _build_native_lua_class_return_helper_chain_impl(
            executable,
            class_factory,
            direct_calls,
            program_facts,
            inventory=inventory,
        )
    except NativeLuaClassReturnHelperChainError:
        raise
    except (
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        NativeLuaClassFactoryChainError,
        NativeLuaSuperRebindingError,
        PEAnchorError,
        OSError,
    ) as exc:
        raise NativeLuaClassReturnHelperChainError(str(exc)) from exc


def _graph_call_r32_audit(
    graph_nodes: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for index, register in enumerate(_REGISTER_NAMES):
        encoded = bytes((0xFF, 0xD0 + index))
        size_sha = (len(encoded), hashlib.sha256(encoded).hexdigest())
        result.append(
            {
                "register": register,
                "call_rvas": [
                    _hex(rva)
                    for rva, node in sorted(graph_nodes.items())
                    if (node.get("size"), node.get("sha256")) == size_sha
                ],
            }
        )
    return result


def _validate_native_lua_class_return_helper_chain_structure_impl(
    evidence: Mapping[str, Any],
    class_factory: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate every finite helper-chain field without reading the PE."""
    for value, label in (
        (evidence, "evidence"),
        (class_factory, "class_factory"),
        (direct_calls, "direct_calls"),
        (program_facts, "program_facts"),
    ):
        _validate_json_tree(value, label)
    try:
        direct_receipt = validate_native_lua_direct_call_structure(
            direct_calls, program_facts
        )
    except NativeLuaDirectCallError as exc:
        raise NativeLuaClassReturnHelperChainError(
            f"direct-call structural prerequisite failed: {exc}"
        ) from exc
    if (
        direct_receipt.get("status") != "structurally_verified"
        or direct_receipt.get("evidence_sha256") != _DIRECT_SHA256
    ):
        raise NativeLuaClassReturnHelperChainError(
            "direct-call structural verifier returned another result"
        )
    profile, atlas, direct_identity, class_identity = _preflight_identities(
        class_factory, direct_calls, program_facts
    )
    evidence = _mapping(evidence, "evidence")
    _exact_keys(
        evidence,
        {
            "schema_version",
            "analysis_kind",
            "build_identity",
            "atlas",
            "direct_call_census",
            "class_factory_chain",
            "decoder",
            "returned_callback_edges",
            "helper_targets",
            "literals",
            "function_bodies",
            "control_flow_graphs",
            "native_edges",
            "whole_atlas_reference_scan",
            "method",
            "summary",
        },
        "evidence",
    )
    if (
        evidence.get("schema_version") != SCHEMA_VERSION
        or evidence.get("analysis_kind") != ANALYSIS_KIND
    ):
        raise NativeLuaClassReturnHelperChainError(
            "unsupported helper-chain schema or analysis kind"
        )
    identity = _mapping(program_facts.get("identity"), "program_facts.identity")
    if evidence.get("build_identity") != dict(identity):
        raise NativeLuaClassReturnHelperChainError(
            "build identity differs from program facts"
        )
    if (
        evidence.get("atlas") != atlas
        or evidence.get("direct_call_census") != direct_identity
        or evidence.get("class_factory_chain") != class_identity
    ):
        raise NativeLuaClassReturnHelperChainError(
            "prerequisite identity differs"
        )
    if evidence.get("decoder") != _decoder_contract() or evidence.get(
        "method"
    ) != _METHOD:
        raise NativeLuaClassReturnHelperChainError(
            "decoder or method contract differs"
        )
    expected_returned_edges = _returned_callback_edges(class_factory, profile)
    if evidence.get("returned_callback_edges") != expected_returned_edges:
        raise NativeLuaClassReturnHelperChainError(
            "returned-callback edge witnesses differ"
        )
    expected_literals = [
        _expected_literal_record(item) for item in profile["literals"]
    ]
    if evidence.get("literals") != expected_literals:
        raise NativeLuaClassReturnHelperChainError("literal profile differs")

    functions = _atlas_functions(program_facts)
    profiles = _function_profiles(profile)
    bodies = _array(evidence.get("function_bodies"), "function_bodies")
    if len(bodies) != len(profiles):
        raise NativeLuaClassReturnHelperChainError("helper body partition differs")
    normalized_bodies: list[Mapping[str, Any]] = []
    for index, (raw_body, expected) in enumerate(zip(bodies, profiles)):
        label = f"function_bodies[{index}]"
        body = _mapping(raw_body, label)
        normalized_bodies.append(body)
        _exact_keys(
            body,
            {
                "role",
                "entry_rva",
                "atlas_record_sha256",
                "body_size",
                "body_sha256",
                "range_start_rva",
                "range_size",
                "control_flow_graph_canonical_sha256",
                "reviewed_points",
                "direct_lua_calls",
                "staged_lua_dispatches",
                "call_r32_audit",
                "register_call_partition_complete",
                "semantic_facts",
            },
            label,
        )
        function = functions.get(expected["entry_rva"])
        if function is None or function.get("thunk") is not False:
            raise NativeLuaClassReturnHelperChainError(
                "reviewed helper is absent or a thunk"
            )
        base = {
            "role": expected["role"],
            "entry_rva": _hex(expected["entry_rva"]),
            "atlas_record_sha256": atlas_record_sha256(function),
            "body_size": expected["body_size"],
            "body_sha256": expected["body_sha256"],
            "range_start_rva": _hex(expected["entry_rva"]),
            "range_size": expected["body_size"],
            "control_flow_graph_canonical_sha256": expected[
                "cfg_canonical_sha256"
            ],
            "reviewed_points": [
                _expected_point_record(spec) for spec in expected["points"]
            ],
            "direct_lua_calls": _direct_call_records(expected, direct_calls),
            "call_r32_audit": _expected_call_r32_audit(expected),
            "register_call_partition_complete": True,
            "semantic_facts": dict(expected["semantic_facts"]),
        }
        for key, value in base.items():
            if body.get(key) != value:
                raise NativeLuaClassReturnHelperChainError(f"{label}.{key} differs")

    try:
        graph_map = _validated_graphs(
            {"control_flow_graphs": evidence.get("control_flow_graphs")},
            functions,
        )
    except NativeLuaClassFactoryChainError as exc:
        raise NativeLuaClassReturnHelperChainError(
            f"helper CFG validation failed: {exc}"
        ) from exc
    if set(graph_map) != {item["entry_rva"] for item in profiles}:
        raise NativeLuaClassReturnHelperChainError("helper CFG partition differs")
    try:
        imports = _lua_import_map(direct_calls)
    except NativeLuaSuperRebindingError as exc:
        raise NativeLuaClassReturnHelperChainError(
            f"Lua import map failed: {exc}"
        ) from exc
    image_base = _rva(
        _mapping(program_facts.get("ghidra"), "program_facts.ghidra").get(
            "image_base"
        ),
        "image base",
    )
    for body, expected in zip(normalized_bodies, profiles):
        graph, nodes, _edges = graph_map[expected["entry_rva"]]
        graph_sha256 = _canonical_sha256(graph)
        if (
            graph_sha256 != expected["cfg_canonical_sha256"]
            or body.get("control_flow_graph_canonical_sha256") != graph_sha256
        ):
            raise NativeLuaClassReturnHelperChainError(
                "sealed helper CFG identity differs"
            )
        for point in body["reviewed_points"]:
            rva = _rva(point["rva"], "reviewed point RVA")
            node = nodes.get(rva)
            if node is None or (node.get("size"), node.get("sha256")) != (
                point["size"],
                point["sha256"],
            ):
                raise NativeLuaClassReturnHelperChainError(
                    "reviewed point does not join its helper CFG"
                )
        for direct in body["direct_lua_calls"]:
            rva = _rva(direct["call_rva"], "direct call RVA")
            node = nodes.get(rva)
            if node is None or (node.get("size"), node.get("sha256")) != (
                direct["instruction_size"],
                direct["instruction_sha256"],
            ):
                raise NativeLuaClassReturnHelperChainError(
                    "direct Lua call does not join its helper CFG"
                )
        staged = _dispatch_records(
            expected,
            graph,
            image_base,
            imports,
            program_facts,
            functions,
        )
        if body.get("staged_lua_dispatches") != staged:
            raise NativeLuaClassReturnHelperChainError(
                "staged Lua dispatch proof differs"
            )
        graph_audit = _graph_call_r32_audit(nodes)
        if body.get("call_r32_audit") != graph_audit:
            raise NativeLuaClassReturnHelperChainError(
                "call-r32 graph partition differs"
            )

    expected_targets = _helper_targets(normalized_bodies, profile, image_base)
    if evidence.get("helper_targets") != expected_targets:
        raise NativeLuaClassReturnHelperChainError("helper target records differ")
    expected_native_edges = _native_edges(profile, program_facts)
    if evidence.get("native_edges") != expected_native_edges:
        raise NativeLuaClassReturnHelperChainError("selected native edges differ")
    for edge in expected_native_edges:
        source = _rva(edge["source_entry_rva"], "native edge source")
        instruction = _mapping(edge["instruction"], "native edge instruction")
        rva = _rva(instruction["rva"], "native edge instruction RVA")
        graph = graph_map.get(source)
        node = None if graph is None else graph[1].get(rva)
        if node is None or (node.get("size"), node.get("sha256")) != (
            instruction["size"],
            instruction["sha256"],
        ):
            raise NativeLuaClassReturnHelperChainError(
                "native edge does not join its source helper CFG"
            )
    expected_scan = _expected_reference_scan(program_facts, direct_calls, profile)
    if evidence.get("whole_atlas_reference_scan") != expected_scan:
        raise NativeLuaClassReturnHelperChainError(
            "whole-atlas helper reference scan differs"
        )
    expected_summary = _summary(evidence)
    if evidence.get("summary") != expected_summary:
        raise NativeLuaClassReturnHelperChainError("summary differs")
    _assert_publication_safe(evidence)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": STRUCTURE_VERIFICATION_KIND,
        "status": "structurally_verified",
        "build_identity": dict(identity),
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": dict(expected_summary),
    }


def validate_native_lua_class_return_helper_chain_structure(
    evidence: Mapping[str, Any],
    class_factory: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate every finite helper-chain field without reading the PE."""
    try:
        return _validate_native_lua_class_return_helper_chain_structure_impl(
            evidence,
            class_factory,
            direct_calls,
            program_facts,
        )
    except NativeLuaClassReturnHelperChainError:
        raise
    except (
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        NativeLuaClassFactoryChainError,
        NativeLuaSuperRebindingError,
    ) as exc:
        raise NativeLuaClassReturnHelperChainError(str(exc)) from exc


def validate_native_lua_class_return_helper_chain(
    executable: Path,
    evidence: Mapping[str, Any],
    class_factory: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and canonical-byte-compare exact callback-helper evidence."""
    try:
        _validate_json_tree(evidence, "evidence")
        rebuilt = build_native_lua_class_return_helper_chain(
            executable,
            class_factory,
            direct_calls,
            program_facts,
            inventory=inventory,
        )
        if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
            raise NativeLuaClassReturnHelperChainError(
                "native Lua class-return helper evidence differs from exact rebuild"
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": VERIFICATION_KIND,
            "status": "verified",
            "build_identity": dict(rebuilt["build_identity"]),
            "evidence_sha256": _canonical_sha256(rebuilt),
            "summary": dict(rebuilt["summary"]),
        }
    except NativeLuaClassReturnHelperChainError:
        raise
    except (
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        NativeLuaClassFactoryChainError,
        NativeLuaSuperRebindingError,
        PEAnchorError,
        OSError,
    ) as exc:
        raise NativeLuaClassReturnHelperChainError(str(exc)) from exc


def encode_native_lua_class_return_helper_chain(value: Mapping[str, Any]) -> str:
    """Return deterministic pretty JSON for evidence or verification receipts."""
    try:
        _validate_json_tree(value)
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
    except NativeLuaCClosurePublicationError as exc:
        raise NativeLuaClassReturnHelperChainError(str(exc)) from exc
