"""Exact native Lua ``property`` consumer and placement chain.

This build-keyed artifact extends the normalized property-factory evidence with
the two direct callback-identity consumers and the initializer that installs
them.  It seals all three bodies, their complete direct and register-staged Lua
call partitions, exact match branches, the setter's read-only arm, and three
distinct getter/setter placements.  Wider mismatch and initializer behavior is
kept explicit but opaque.
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
    _direct_call_map,
    _expected_point_record,
    _expected_prerequisites,
    _function_profiles,
    _point,
    _point_record,
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
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_cclosure_table_key_provenance import _enhanced_cfg
from src.observatory.native_lua_direct_calls import (
    CALL_FORM as DIRECT_CALL_FORM,
    SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
)
from src.observatory.native_lua_property_factory_chain import (
    ANALYSIS_KIND as PROPERTY_FACTORY_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as PROPERTY_FACTORY_STRUCTURE_VERIFICATION_KIND,
    NativeLuaPropertyFactoryChainError,
    validate_native_lua_property_factory_chain,
    validate_native_lua_property_factory_chain_structure,
)
from src.observatory.native_lua_super_rebinding import (
    NativeLuaSuperRebindingError,
    _lua_import_map,
    _staged_dispatch_records,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_property_consumer_chain"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
LUA_LIBRARY = "lua5.1.dll"
PE_SECTION_WRITABLE = 0x80000000
MAX_LITERAL_BYTES = 256


class NativeLuaPropertyConsumerChainError(RuntimeError):
    """Raised when the exact property-consumer chain is stale or malformed."""


_METHOD = {
    "accepted_chain": (
        "One exact property-factory artifact is joined to its two direct tag-identity "
        "consumers, one native initializer, three distinct closure placements, sealed "
        "function bodies, and a complete direct target-operand partition."
    ),
    "lua51_abi_premises": [
        "Lua stack indices used by the reviewed calls have Lua 5.1 meanings",
        "lua_type value zero denotes nil",
        "lua_error does not return normally",
        "lua_pushcclosure consumes the declared upvalue count",
    ],
    "native_register_provenance": (
        "Every retained EBX, ESI, or EDI Lua call has one exact import stage that "
        "dominates every grouped call in the sealed caller CFG. No stage-to-call "
        "path writes that register under the explicit 32-bit Windows cdecl premise. "
        "The full eight-encoding x86 call-r32 partition is checked independently."
    ),
    "target_scan_boundary": (
        "Every instruction in every file-backed program-facts atlas range is decoded "
        "with operand detail. Only immediate and absolute-memory operands equal to "
        "one of the three exact consumer and initializer VAs are retained."
    ),
    "normalized_semantic_boundary": (
        "The getter and setter identity-match arms, the setter nil and read-only arm, and "
        "the three declared initializer placements are normalized. Identity-mismatch "
        "arms and all remaining initializer helper and loop behavior stay explicitly opaque "
        "even though their enclosing bodies and complete Lua-call partitions are sealed."
    ),
    "structural_boundary": (
        "PE-free validation proves prerequisite joins, sealed profiles and full-CFG "
        "identities, direct and staged-register call partitions, branch and placement "
        "records, target references, and aggregates. Instruction, literal, and constant bytes, "
        "decoded register writes, and exhaustive atlas decoding require exact rebuild."
    ),
    "not_claimed": [
        "runtime reachability, execution order, frequency, state continuity, or persistence",
        "dynamic metatable attachment, recipient identity, later lookup, or invocation",
        "factory provenance from callback identity alone",
        "successful upvalue retrieval, callability, argument types, or call success",
        "registry validity, reference lifetime, ownership, or source-level descriptor semantics",
        "normalized semantics for either callback-identity mismatch branch",
        "normalized semantics for residual initializer helpers, keys, loop entries, or closures",
        "absence of computed, indirect, data, un-atlased, or Lua-side references",
        "source equivalence or a complete runtime call graph",
    ],
}


_SEALED_PROFILE: dict[str, Any] = {
    "executable_sha256": "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9",
    "property_factory_canonical_sha256": "aef6475375ce31da7d089eb819bf4b3a42228332892aa2bb8645668fe2db3b5e",
    "property_tag_entry_rva": 0x002EAA50,
    "literals": [
        {
            "role": "read_only_error_format",
            "text": "property '%s' is read only",
            "rva": 0x0043C488,
            "byte_length_excluding_nul": 26,
            "nul_terminated_bytes_sha256": "b83cdf75ce91828d07eb594c987ee462333675b0b761914ac215a5712f93aeea",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
        {
            "role": "newindex_metamethod_key",
            "text": "__newindex",
            "rva": 0x0043C518,
            "byte_length_excluding_nul": 10,
            "nul_terminated_bytes_sha256": "e84e40a532eac289fd4cb0b893ed0c407fee00ee1f5d2036f638f9dc6af9273e",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
        {
            "role": "index_metamethod_key",
            "text": "__index",
            "rva": 0x0043C534,
            "byte_length_excluding_nul": 7,
            "nul_terminated_bytes_sha256": "89dfaf29ae22fb9d8fe3a5d35e57e4333d41a029db1133d12bf82eed91890c79",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
    ],
    "constants": [
        {
            "role": "numeric_getter_rawset_key_binary64",
            "rva": 0x0043CBE0,
            "byte_length": 8,
            "bytes_hex": "000000000000f03f",
            "sha256": "6c3c396ed6b5c36dcae172271f462051b1266b851e92df3deea8ac65478fd712",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
            "interpretation": "little_endian_ieee754_binary64_1.0",
        }
    ],
    "functions": [
        {
            "role": "setter_like_consumer",
            "entry_rva": 0x002E9FD0,
            "body_size": 317,
            "body_sha256": "89dcd9a4a320eb36f3c9d96c3bd24dc0c27c48b7c15dfb78fbd6ad6a59191c68",
            "cfg_canonical_sha256": "e8e40b27127b5089c437dc21970c5a239b6e67e76aa779dbd9a680047887dda4",
            "points": [
                _point("lua_getfenv", 0x002E9FDC, "ff1538657d00", "lua_getfenv"),
                _point("lua_rawget_primary", 0x002E9FF0, "ff1584647d00", "lua_rawget"),
                _point("lua_type_candidate", 0x002E9FF9, "ff15fc647d00", "lua_type"),
                _point("lua_getmetatable_primary", 0x002EA00F, "ff1534657d00", "lua_getmetatable"),
                _point("lua_rawget_metatable", 0x002EA024, "ff1584647d00", "lua_rawget"),
                _point("lua_replace_candidate", 0x002EA02D, "ff1554657d00", "lua_replace"),
                _point("tocfunction_index_minus_one", 0x002EA03B, "6aff"),
                _point("lua_tocfunction", 0x002EA03E, "ff153c657d00", "lua_tocfunction"),
                _point("property_tag_identity_compare", 0x002EA047, "3d50aa6e00"),
                _point("identity_mismatch_branch", 0x002EA04C, "755b"),
                _point("getupvalue_index_two", 0x002EA04E, "6a02"),
                _point("getupvalue_closure_index_minus_one", 0x002EA050, "6aff"),
                _point("lua_getupvalue", 0x002EA053, "ff1548657d00", "lua_getupvalue"),
                _point("type_upvalue_index_minus_one", 0x002EA059, "6aff"),
                _point("lua_type_upvalue_two", 0x002EA05C, "ff15fc647d00", "lua_type"),
                _point("nil_type_test", 0x002EA065, "85c0"),
                _point("non_nil_branch", 0x002EA067, "7521"),
                _point("tolstring_null_length_pointer", 0x002EA069, "50"),
                _point("tolstring_name_index_two", 0x002EA06A, "6a02"),
                _point("lua_tolstring", 0x002EA06D, "ff1500657d00", "lua_tolstring"),
                _point("read_only_format_pointer", 0x002EA074, "6888c48300"),
                _point("lua_pushfstring", 0x002EA07A, "ff1544657d00", "lua_pushfstring"),
                _point("lua_error", 0x002EA081, "ff1598647d00", "lua_error"),
                _point("push_original_index_one", 0x002EA08A, "6a01"),
                _point("push_original_index_three", 0x002EA08F, "6a03"),
                _point("lua_call_results_zero", 0x002EA094, "6a00"),
                _point("lua_call_arguments_two", 0x002EA096, "6a02"),
                _point("lua_call_setter", 0x002EA099, "ff1540657d00", "lua_call"),
                _point("match_result_count_zero", 0x002EA0A2, "33c0"),
                _point("match_return", 0x002EA0A8, "c3"),
                _point("lua_getmetatable_mismatch", 0x002EA0B1, "ff1534657d00", "lua_getmetatable"),
                _point("lua_createtable_mismatch", 0x002EA0C1, "ff1518657d00", "lua_createtable"),
                _point("lua_setfenv_mismatch", 0x002EA0CF, "ff154c657d00", "lua_setfenv"),
                _point("lua_setmetatable_mismatch", 0x002EA0DD, "ff1530657d00", "lua_setmetatable"),
                _point("lua_rawset_mismatch", 0x002EA0FD, "ff152c657d00", "lua_rawset"),
                _point("mismatch_result_count_zero", 0x002EA106, "33c0"),
                _point("mismatch_return", 0x002EA10C, "c3"),
            ],
            "staged_dispatches": [
                {
                    "api_name": "lua_pushvalue",
                    "register": "edi",
                    "stage_rva": 0x002E9FE2,
                    "call_rvas": [
                        0x002E9FEB,
                        0x002EA01F,
                        0x002EA08D,
                        0x002EA092,
                        0x002EA0CA,
                        0x002EA0D8,
                        0x002EA0F3,
                        0x002EA0F8,
                    ],
                },
                {
                    "api_name": "lua_settop",
                    "register": "ebx",
                    "stage_rva": 0x002E9FFF,
                    "call_rvas": [0x002EA036, 0x002EA0AC, 0x002EA0EB],
                },
            ],
            "semantic_facts": {
                "identity_test": {
                    "candidate_stack_index": -1,
                    "conversion_api": "lua_tocfunction",
                    "compared_callback_entry_rva": "0x002eaa50",
                    "comparison_rva": "0x002ea047",
                },
                "identity_match_arm": {
                    "retrieved_upvalue_index": 2,
                    "getupvalue_native_result_checked": False,
                    "nil_type_value": 0,
                    "nil_arm": "read_only_lua_error",
                    "non_nil_original_argument_indices": [1, 3],
                    "non_nil_lua_call_argument_count": 2,
                    "non_nil_lua_call_result_count": 0,
                    "non_nil_value_callability_proven": False,
                    "normal_result_count": 0,
                },
                "identity_mismatch_arm": {
                    "entry_rva": "0x002ea0a9",
                    "semantics_normalized": False,
                    "enclosing_body_and_lua_calls_sealed": True,
                    "terminal_result_count": 0,
                },
            },
        },
        {
            "role": "getter_like_consumer",
            "entry_rva": 0x002EA110,
            "body_size": 144,
            "body_sha256": "af02593b529264569e721d6dd2e401afd5d5b2b5d8aea67ee623226bfe3584a2",
            "cfg_canonical_sha256": "bf0b0d9be19d193c9fa79b582566a9d696d73eb98d466459e0e548a5bddf1c55",
            "points": [
                _point("lua_getfenv", 0x002EA11B, "ff1538657d00", "lua_getfenv"),
                _point("lua_rawget_primary", 0x002EA12F, "ff1584647d00", "lua_rawget"),
                _point("lua_type_candidate", 0x002EA138, "ff15fc647d00", "lua_type"),
                _point("lua_getmetatable", 0x002EA148, "ff1534657d00", "lua_getmetatable"),
                _point("lua_rawget_metatable", 0x002EA15D, "ff1584647d00", "lua_rawget"),
                _point("tocfunction_index_minus_one", 0x002EA166, "6aff"),
                _point("lua_tocfunction", 0x002EA169, "ff153c657d00", "lua_tocfunction"),
                _point("property_tag_identity_compare", 0x002EA172, "3d50aa6e00"),
                _point("identity_mismatch_branch", 0x002EA177, "751e"),
                _point("getupvalue_index_one", 0x002EA179, "6a01"),
                _point("getupvalue_closure_index_minus_one", 0x002EA17B, "6aff"),
                _point("lua_getupvalue", 0x002EA17E, "ff1548657d00", "lua_getupvalue"),
                _point("push_original_index_one", 0x002EA184, "6a01"),
                _point("lua_call_results_one", 0x002EA189, "6a01"),
                _point("lua_call_arguments_one", 0x002EA18B, "6a01"),
                _point("lua_call_getter", 0x002EA18E, "ff1540657d00", "lua_call"),
                _point("shared_result_count_one", 0x002EA198, "b801000000"),
                _point("return", 0x002EA19F, "c3"),
            ],
            "staged_dispatches": [
                {
                    "api_name": "lua_pushvalue",
                    "register": "edi",
                    "stage_rva": 0x002EA121,
                    "call_rvas": [0x002EA12A, 0x002EA158, 0x002EA187],
                }
            ],
            "semantic_facts": {
                "identity_test": {
                    "candidate_stack_index": -1,
                    "conversion_api": "lua_tocfunction",
                    "compared_callback_entry_rva": "0x002eaa50",
                    "comparison_rva": "0x002ea172",
                },
                "identity_match_arm": {
                    "retrieved_upvalue_index": 1,
                    "getupvalue_native_result_checked": False,
                    "original_argument_indices": [1],
                    "lua_call_argument_count": 1,
                    "lua_call_result_count": 1,
                    "retrieved_value_callability_proven": False,
                    "normal_result_count": 1,
                },
                "identity_mismatch_arm": {
                    "entry_rva": "0x002ea197",
                    "semantics_normalized": False,
                    "enclosing_body_and_lua_calls_sealed": True,
                    "shared_terminal_result_count": 1,
                },
            },
        },
        {
            "role": "consumer_initializer",
            "entry_rva": 0x002EA2D0,
            "body_size": 245,
            "body_sha256": "87e765ce2290b8320efb30cb7e110e8ae67783793b968aecd01827f6bd00d9c1",
            "cfg_canonical_sha256": "3901fcde5bfae4be68f67fa1af3cd5e2831443d3af26d16f85c90576d781a843",
            "points": [
                _point("lua_createtable", 0x002EA2DA, "ff1518657d00", "lua_createtable"),
                _point("lua_pushboolean", 0x002EA2E3, "ff15a4647d00", "lua_pushboolean"),
                _point("numeric_key_constant_load", 0x002EA2F9, "f20f1005e0cb8300"),
                _point("numeric_key_stack_copy", 0x002EA304, "f20f110424"),
                _point("lua_pushnumber", 0x002EA30A, "ff1588647d00", "lua_pushnumber"),
                _point("numeric_getter_upvalue_count_zero", 0x002EA316, "6a00"),
                _point("numeric_getter_target_push", 0x002EA318, "6810a16e00"),
                _point("numeric_rawset_table_index_minus_three", 0x002EA320, "6afd"),
                _point("lua_rawset_numeric_getter", 0x002EA323, "ff152c657d00", "lua_rawset"),
                _point("residual_gc_target_push", 0x002EA32B, "68409f6e00"),
                _point("index_getter_upvalue_count_zero", 0x002EA33D, "6a00"),
                _point("index_getter_target_push", 0x002EA33F, "6810a16e00"),
                _point("index_key_pointer", 0x002EA34A, "6834c58300"),
                _point("index_table_index_minus_two", 0x002EA34F, "6afe"),
                _point("newindex_setter_upvalue_count_zero", 0x002EA354, "6a00"),
                _point("newindex_setter_target_push", 0x002EA356, "68d09f6e00"),
                _point("newindex_key_pointer", 0x002EA35E, "6818c58300"),
                _point("newindex_table_index_minus_two", 0x002EA363, "6afe"),
                _point("lua_pushstring_loop", 0x002EA378, "ff1594647d00", "lua_pushstring"),
                _point("lua_pushvalue_loop", 0x002EA381, "ff15e4647d00", "lua_pushvalue"),
                _point("lua_pushboolean_loop", 0x002EA39F, "ff15a4647d00", "lua_pushboolean"),
                _point("residual_loop_target_push", 0x002EA3A7, "68a0a16e00"),
                _point("lua_settable_loop", 0x002EA3B2, "ff1550657d00", "lua_settable"),
                _point("return", 0x002EA3C4, "c3"),
            ],
            "staged_dispatches": [
                {
                    "api_name": "lua_setfield",
                    "register": "esi",
                    "stage_rva": 0x002EA2E9,
                    "call_rvas": [0x002EA2F7, 0x002EA33B, 0x002EA352, 0x002EA366],
                },
                {
                    "api_name": "lua_pushcclosure",
                    "register": "ebx",
                    "stage_rva": 0x002EA310,
                    "call_rvas": [0x002EA31E, 0x002EA331, 0x002EA345, 0x002EA35C, 0x002EA3AD],
                },
            ],
            "semantic_facts": {
                "declared_property_consumer_placement_count": 3,
                "numeric_getter_rawset_is_index_metamethod_placement": False,
                "residual_initializer_semantics_normalized": False,
                "enclosing_body_and_lua_calls_sealed": True,
            },
        },
    ],
    "placements": [
        {
            "role": "numeric_getter_rawset",
            "callback_entry_rva": 0x002EA110,
            "target_push_rva": 0x002EA318,
            "closure_call_rva": 0x002EA31E,
            "upvalue_count": 0,
            "destination_api": "lua_rawset",
            "destination_call_rva": 0x002EA323,
            "lua_table_index": -3,
            "key_kind": "lua_number_from_sealed_binary64_constant",
            "key_record_role": "numeric_getter_rawset_key_binary64",
            "metamethod_name": None,
            "metamethod_placement_claimed": False,
        },
        {
            "role": "index_getter_setfield",
            "callback_entry_rva": 0x002EA110,
            "target_push_rva": 0x002EA33F,
            "closure_call_rva": 0x002EA345,
            "upvalue_count": 0,
            "destination_api": "lua_setfield",
            "destination_call_rva": 0x002EA352,
            "lua_table_index": -2,
            "key_kind": "non_writable_ascii_literal",
            "key_record_role": "index_metamethod_key",
            "metamethod_name": "__index",
            "metamethod_placement_claimed": True,
        },
        {
            "role": "newindex_setter_setfield",
            "callback_entry_rva": 0x002E9FD0,
            "target_push_rva": 0x002EA356,
            "closure_call_rva": 0x002EA35C,
            "upvalue_count": 0,
            "destination_api": "lua_setfield",
            "destination_call_rva": 0x002EA366,
            "lua_table_index": -2,
            "key_kind": "non_writable_ascii_literal",
            "key_record_role": "newindex_metamethod_key",
            "metamethod_name": "__newindex",
            "metamethod_placement_claimed": True,
        },
    ],
    "target_references": [
        {
            "instruction_rva": 0x002EA1E6,
            "owner_entry_rva": 0x002EA1A0,
            "target_rva": 0x002EA110,
            "encoded": "3d10a16e00",
            "operand_index": 1,
            "use_class": "getter_identity_comparison",
        },
        {
            "instruction_rva": 0x002EA318,
            "owner_entry_rva": 0x002EA2D0,
            "target_rva": 0x002EA110,
            "encoded": "6810a16e00",
            "operand_index": 0,
            "use_class": "numeric_rawset_getter_closure_producer",
        },
        {
            "instruction_rva": 0x002EA33F,
            "owner_entry_rva": 0x002EA2D0,
            "target_rva": 0x002EA110,
            "encoded": "6810a16e00",
            "operand_index": 0,
            "use_class": "index_getter_closure_producer",
        },
        {
            "instruction_rva": 0x002EA356,
            "owner_entry_rva": 0x002EA2D0,
            "target_rva": 0x002E9FD0,
            "encoded": "68d09f6e00",
            "operand_index": 0,
            "use_class": "newindex_setter_closure_producer",
        },
        {
            "instruction_rva": 0x002EA40D,
            "owner_entry_rva": 0x002EA3D0,
            "target_rva": 0x002EA110,
            "encoded": "3d10a16e00",
            "operand_index": 1,
            "use_class": "getter_identity_comparison",
        },
        {
            "instruction_rva": 0x002EBB68,
            "owner_entry_rva": 0x002EBB30,
            "target_rva": 0x002EA2D0,
            "encoded": "e863e7ffff",
            "operand_index": 0,
            "use_class": "initializer_direct_call",
        },
    ],
}


_PROFILES = {_SEALED_PROFILE["executable_sha256"]: _SEALED_PROFILE}
_REGISTER_NAMES = ("eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi")
_REGISTER_CALL_ENCODINGS = tuple(f"ffd{index:x}" for index in range(8))
_REGISTER_CALL_HASH_TO_NAME = {
    hashlib.sha256(bytes.fromhex(encoded)).hexdigest(): register
    for register, encoded in zip(_REGISTER_NAMES, _REGISTER_CALL_ENCODINGS)
}


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


def _literal_record(data: bytes, image: Any, expected: Mapping[str, Any]) -> dict[str, Any]:
    raw = bytearray()
    first_offset: int | None = None
    prior_offset: int | None = None
    for delta in range(MAX_LITERAL_BYTES + 1):
        offset = image.rva_to_file_offset(expected["rva"] + delta)
        if offset is None or offset >= len(data):
            raise NativeLuaPropertyConsumerChainError("literal is not bounded file-backed data")
        if first_offset is None:
            first_offset = offset
        if prior_offset is not None and offset != prior_offset + 1:
            raise NativeLuaPropertyConsumerChainError("literal bytes are not contiguous")
        prior_offset = offset
        value = data[offset]
        raw.append(value)
        if value == 0:
            break
        if value < 0x20 or value > 0x7E:
            raise NativeLuaPropertyConsumerChainError("literal is not printable ASCII")
    else:
        raise NativeLuaPropertyConsumerChainError("literal exceeds bounded length")
    if len(raw) < 2 or raw[-1] != 0 or first_offset is None or prior_offset is None:
        raise NativeLuaPropertyConsumerChainError("literal lacks a NUL terminator")
    section = image.section_for_offset(first_offset)
    if (
        section is None
        or section.characteristics & PE_SECTION_WRITABLE
        or image.section_for_offset(prior_offset) != section
    ):
        raise NativeLuaPropertyConsumerChainError("literal is not in one non-writable section")
    observed = bytes(raw[:-1]).decode("ascii")
    record = {
        "role": expected["role"],
        "text": observed,
        "rva": _hex(expected["rva"]),
        "byte_length_excluding_nul": len(raw) - 1,
        "nul_terminated_bytes_sha256": hashlib.sha256(bytes(raw)).hexdigest(),
        "section_name": section.name,
        "section_rva": _hex(section.virtual_address),
        "section_characteristics": _hex(section.characteristics),
        "section_writable": False,
    }
    if record != _expected_literal_record(expected):
        raise NativeLuaPropertyConsumerChainError(f"{expected['role']} literal identity changed")
    return record


def _expected_constant_record(expected: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "role": expected["role"],
        "rva": _hex(expected["rva"]),
        "byte_length": expected["byte_length"],
        "bytes_sha256": expected["sha256"],
        "section_name": expected["section_name"],
        "section_rva": _hex(expected["section_rva"]),
        "section_characteristics": _hex(expected["section_characteristics"]),
        "section_writable": False,
        "interpretation": expected["interpretation"],
    }


def _constant_record(data: bytes, image: Any, expected: Mapping[str, Any]) -> dict[str, Any]:
    offset = image.rva_span_to_file_offset(expected["rva"], expected["byte_length"])
    if offset is None:
        raise NativeLuaPropertyConsumerChainError("constant is not contiguous file-backed data")
    raw = data[offset : offset + expected["byte_length"]]
    section = image.section_for_offset(offset)
    if (
        raw.hex() != expected["bytes_hex"]
        or hashlib.sha256(raw).hexdigest() != expected["sha256"]
        or section is None
        or section.characteristics & PE_SECTION_WRITABLE
        or image.section_for_offset(offset + len(raw) - 1) != section
    ):
        raise NativeLuaPropertyConsumerChainError("numeric getter key constant changed")
    record = {
        "role": expected["role"],
        "rva": _hex(expected["rva"]),
        "byte_length": len(raw),
        "bytes_sha256": hashlib.sha256(raw).hexdigest(),
        "section_name": section.name,
        "section_rva": _hex(section.virtual_address),
        "section_characteristics": _hex(section.characteristics),
        "section_writable": False,
        "interpretation": expected["interpretation"],
    }
    if record != _expected_constant_record(expected):
        raise NativeLuaPropertyConsumerChainError("numeric getter key record changed")
    return record


def _direct_call_rvas_for_entry(
    call_map: Mapping[int, tuple[Mapping[str, Any], Mapping[str, Any]]],
    entry_rva: int,
) -> list[int]:
    entry = _hex(entry_rva)
    return sorted(
        rva for rva, (record, _call) in call_map.items() if record.get("entry_rva") == entry
    )


def _dynamic_register_calls(graph: Mapping[str, Any]) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for raw in _array(graph.get("nodes"), "CFG nodes"):
        node = _mapping(raw, "CFG node")
        register = _REGISTER_CALL_HASH_TO_NAME.get(node.get("sha256"))
        if node.get("size") == 2 and register is not None:
            result.append((_rva(node.get("rva"), "dynamic call RVA"), register))
    return sorted(result)


def _expected_dynamic_partition(expected: Mapping[str, Any]) -> list[tuple[int, str]]:
    return sorted(
        (rva, spec["register"])
        for spec in expected["staged_dispatches"]
        for rva in spec["call_rvas"]
    )


def _dispatch_records(
    expected: Mapping[str, Any],
    graph: Mapping[str, Any],
    image_base: int,
    imports: Mapping[str, Mapping[str, Any]],
    program_facts: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    try:
        result = _staged_dispatch_records(
            expected, graph, image_base, imports, program_facts, functions
        )
    except NativeLuaSuperRebindingError as exc:
        raise NativeLuaPropertyConsumerChainError(
            f"staged Lua dispatch proof failed: {exc}"
        ) from exc
    if _dynamic_register_calls(graph) != _expected_dynamic_partition(expected):
        raise NativeLuaPropertyConsumerChainError(
            "complete eight-encoding dynamic register-call partition changed"
        )
    return result


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
        raise NativeLuaPropertyConsumerChainError(f"Lua import map failed: {exc}") from exc
    bodies: list[dict[str, Any]] = []
    graphs: list[dict[str, Any]] = []
    decoder.detail = True
    for expected in _function_profiles(profile):
        entry = expected["entry_rva"]
        function = functions.get(entry)
        if function is None or function.get("thunk") is not False:
            raise NativeLuaPropertyConsumerChainError("reviewed function is absent or a thunk")
        if (
            function.get("body_size") != expected["body_size"]
            or function.get("body_sha256") != expected["body_sha256"]
        ):
            raise NativeLuaPropertyConsumerChainError("reviewed function body changed")
        ranges = _array(function.get("ranges"), "function ranges")
        if len(ranges) != 1:
            raise NativeLuaPropertyConsumerChainError("reviewed function no longer has one range")
        raw_range = _mapping(ranges[0], "function range")
        start = _rva(raw_range.get("start_rva"), "range start")
        size = raw_range.get("size")
        if start != entry or type(size) is not int or size != expected["body_size"]:
            raise NativeLuaPropertyConsumerChainError("reviewed function range changed")
        instructions = _decode_range(data, image, start, size, decoder)
        graph = _with_edi_writes(
            _enhanced_cfg(instructions, image.image_base, (start, size), capstone, x86),
            instructions,
            x86,
        )
        graph["caller_entry_rva"] = _hex(entry)
        graph_sha256 = _canonical_sha256(graph)
        if graph_sha256 != expected["cfg_canonical_sha256"]:
            raise NativeLuaPropertyConsumerChainError("reviewed function CFG changed")
        graphs.append(graph)
        by_rva = {item.address - image.image_base: item for item in instructions}
        points: list[dict[str, Any]] = []
        profiled_direct_calls: list[int] = []
        for profile_point in expected["points"]:
            instruction = by_rva.get(profile_point[1])
            if instruction is None:
                raise NativeLuaPropertyConsumerChainError("reviewed instruction is absent")
            point = _point_record(instruction, image.image_base, profile_point)
            api = point["direct_lua_import"]
            if api is not None:
                profiled_direct_calls.append(profile_point[1])
                joined = call_map.get(profile_point[1])
                if (
                    joined is None
                    or joined[0].get("entry_rva") != _hex(entry)
                    or joined[1].get("import_name") != api
                    or joined[1].get("library") != LUA_LIBRARY
                    or joined[1].get("call_form") != DIRECT_CALL_FORM
                    or joined[1].get("instruction_sha256") != point["sha256"]
                ):
                    raise NativeLuaPropertyConsumerChainError(
                        f"reviewed {api} call does not join direct-call census"
                    )
            points.append(point)
        if sorted(profiled_direct_calls) != _direct_call_rvas_for_entry(call_map, entry):
            raise NativeLuaPropertyConsumerChainError("direct Lua-call partition is incomplete")
        staged = _dispatch_records(
            expected, graph, image.image_base, imports, program_facts, functions
        )
        bodies.append(
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
                "direct_lua_call_partition_complete": True,
                "staged_lua_dispatches": staged,
                "dynamic_register_call_rvas": [
                    _hex(rva) for rva, _register in _dynamic_register_calls(graph)
                ],
                "all_eight_register_call_encodings_checked": True,
                "staged_register_call_partition_complete": True,
                "semantic_facts": dict(expected["semantic_facts"]),
            }
        )
    return bodies, graphs


def _property_factory_source(
    property_factory_chain: Mapping[str, Any], profile: Mapping[str, Any]
) -> dict[str, Any]:
    canonical = _canonical_sha256(property_factory_chain)
    if (
        property_factory_chain.get("analysis_kind") != PROPERTY_FACTORY_ANALYSIS_KIND
        or canonical != profile["property_factory_canonical_sha256"]
    ):
        raise NativeLuaPropertyConsumerChainError("property-factory prerequisite identity changed")
    chain = _mapping(property_factory_chain.get("publication_chain"), "publication_chain")
    returned = _mapping(chain.get("factory_returned_closure"), "factory returned closure")
    if (
        _rva(returned.get("callback_entry_rva"), "property tag callback")
        != profile["property_tag_entry_rva"]
        or returned.get("literal_upvalue_count") != 2
    ):
        raise NativeLuaPropertyConsumerChainError("property tag source changed")
    wanted = {0x002EA047: 0x002E9FD0, 0x002EA172: 0x002EA110}
    scan = _mapping(property_factory_chain.get("target_reference_scan"), "property target scan")
    matches: list[dict[str, Any]] = []
    for raw in _array(scan.get("references"), "property target references"):
        item = _mapping(raw, "property target reference")
        instruction = _rva(item.get("instruction_rva"), "tag comparison RVA")
        if instruction not in wanted:
            continue
        if (
            _rva(item.get("owner_entry_rva"), "tag comparison owner") != wanted[instruction]
            or _rva(item.get("target_rva"), "tag comparison target")
            != profile["property_tag_entry_rva"]
            or item.get("use_class") != "callback_identity_comparison"
            or item.get("operand_class") != "immediate"
        ):
            raise NativeLuaPropertyConsumerChainError("property tag comparison changed")
        matches.append(
            {
                "consumer_entry_rva": item["owner_entry_rva"],
                "comparison_instruction_rva": item["instruction_rva"],
                "source_reference_record_sha256": _canonical_sha256(item),
            }
        )
    if [item["comparison_instruction_rva"] for item in matches] != [
        "0x002ea047",
        "0x002ea172",
    ]:
        raise NativeLuaPropertyConsumerChainError("property tag comparison partition changed")
    return {
        "analysis_kind": PROPERTY_FACTORY_ANALYSIS_KIND,
        "canonical_sha256": canonical,
        "factory_callback_entry_rva": returned["caller_entry_rva"],
        "tag_callback_entry_rva": returned["callback_entry_rva"],
        "factory_closure_upvalue_count": returned["literal_upvalue_count"],
        "identity_comparison_witnesses": matches,
        "callback_identity_establishes_factory_origin": False,
    }


def _placement_records(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "role": item["role"],
            "initializer_entry_rva": "0x002ea2d0",
            "callback_entry_rva": _hex(item["callback_entry_rva"]),
            "target_push_rva": _hex(item["target_push_rva"]),
            "closure_call_rva": _hex(item["closure_call_rva"]),
            "closure_upvalue_count": item["upvalue_count"],
            "destination_api": item["destination_api"],
            "destination_call_rva": _hex(item["destination_call_rva"]),
            "lua_table_index": item["lua_table_index"],
            "key_kind": item["key_kind"],
            "key_record_role": item["key_record_role"],
            "metamethod_name": item["metamethod_name"],
            "metamethod_placement_claimed": item["metamethod_placement_claimed"],
            "dynamic_recipient_identity_claimed": False,
            "runtime_invocation_claimed": False,
        }
        for item in profile["placements"]
    ]


def _expected_reference(
    raw: Mapping[str, Any], image_base: int, functions: Mapping[int, Mapping[str, Any]]
) -> dict[str, Any]:
    owner = functions.get(raw["owner_entry_rva"])
    if owner is None:
        raise NativeLuaPropertyConsumerChainError("target-reference owner is absent")
    encoded = bytes.fromhex(raw["encoded"])
    return {
        "instruction_rva": _hex(raw["instruction_rva"]),
        "instruction_size": len(encoded),
        "instruction_sha256": hashlib.sha256(encoded).hexdigest(),
        "owner_entry_rva": _hex(raw["owner_entry_rva"]),
        "owner_atlas_record_sha256": atlas_record_sha256(owner),
        "target_rva": _hex(raw["target_rva"]),
        "target_va": _hex(image_base + raw["target_rva"]),
        "operand_class": "immediate",
        "operand_index": raw["operand_index"],
        "use_class": raw["use_class"],
    }


def _reference_aggregates(references: list[Mapping[str, Any]]) -> dict[str, Any]:
    classes = [item["use_class"] for item in references]
    targets = [item["target_rva"] for item in references]
    return {
        "reference_count": len(references),
        "closure_producer_count": sum(value.endswith("closure_producer") for value in classes),
        "direct_call_count": classes.count("initializer_direct_call"),
        "comparison_count": sum(value.endswith("identity_comparison") for value in classes),
        "other_address_count": sum(
            not value.endswith("closure_producer")
            and value != "initializer_direct_call"
            and not value.endswith("identity_comparison")
            for value in classes
        ),
        "memory_operand_count": sum(item["operand_class"] == "absolute_memory" for item in references),
        "getter_target_reference_count": targets.count("0x002ea110"),
        "setter_target_reference_count": targets.count("0x002e9fd0"),
        "initializer_target_reference_count": targets.count("0x002ea2d0"),
    }


def _target_reference_scan(
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
    targets = sorted(item["entry_rva"] for item in profile["functions"])
    target_vas = {image.image_base + rva: rva for rva in targets}
    declared = {
        (item["instruction_rva"], item["target_rva"], item["operand_index"]): item["use_class"]
        for item in profile["target_references"]
    }
    references: list[dict[str, Any]] = []
    decoded_ranges = decoded_bytes = decoded_instructions = 0
    for entry, function in sorted(functions.items()):
        owner_hash = atlas_record_sha256(function)
        for raw_range in _array(function.get("ranges"), "atlas ranges"):
            mapped = _mapping(raw_range, "atlas range")
            start = _rva(mapped.get("start_rva"), "range start")
            size = mapped.get("size")
            if type(size) is not int or size <= 0:
                raise NativeLuaPropertyConsumerChainError("atlas range size is invalid")
            instructions = _decode_range(data, image, start, size, decoder)
            decoded_ranges += 1
            decoded_bytes += size
            decoded_instructions += len(instructions)
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
                    use_class = declared.get((instruction_rva, target_rva, operand_index))
                    if use_class is None:
                        if instruction.id == x86.X86_INS_CALL:
                            use_class = "direct_call"
                        elif instruction.id in {x86.X86_INS_CMP, x86.X86_INS_TEST}:
                            use_class = "identity_comparison"
                        else:
                            use_class = "other_address"
                    references.append(
                        {
                            "instruction_rva": _hex(instruction_rva),
                            "instruction_size": instruction.size,
                            "instruction_sha256": hashlib.sha256(bytes(instruction.bytes)).hexdigest(),
                            "owner_entry_rva": _hex(entry),
                            "owner_atlas_record_sha256": owner_hash,
                            "target_rva": _hex(target_rva),
                            "target_va": _hex(value),
                            "operand_class": operand_class,
                            "operand_index": operand_index,
                            "use_class": use_class,
                        }
                    )
    references.sort(key=lambda item: (_rva(item["instruction_rva"], "reference RVA"), item["operand_index"]))
    expected = [
        _expected_reference(item, image.image_base, functions)
        for item in sorted(profile["target_references"], key=lambda item: (item["instruction_rva"], item["operand_index"]))
    ]
    if references != expected:
        raise NativeLuaPropertyConsumerChainError("consumer target-reference partition changed")
    fact_summary = _mapping(program_facts.get("summary"), "program_facts.summary")
    direct_summary = _mapping(direct_calls.get("summary"), "direct_calls.summary")
    if (
        decoded_ranges != fact_summary.get("body_range_count")
        or decoded_bytes != fact_summary.get("function_body_bytes")
        or decoded_ranges != direct_summary.get("decoded_ranges")
        or decoded_bytes != direct_summary.get("decoded_bytes")
        or decoded_instructions != direct_summary.get("decoded_instructions")
    ):
        raise NativeLuaPropertyConsumerChainError("target scan did not cover declared atlas")
    return {
        "target_rvas": [_hex(value) for value in targets],
        "target_vas": [_hex(image.image_base + value) for value in targets],
        "scope": {
            "atlas_function_count": len(functions),
            "atlas_body_range_count": decoded_ranges,
            "decoded_bytes": decoded_bytes,
            "decoded_instructions": decoded_instructions,
            "all_declared_ranges_decoded": True,
            "operand_classes": ["absolute_memory", "immediate"],
        },
        "references": references,
        "aggregates": _reference_aggregates(references),
    }


def _consumer_targets(
    bodies: list[Mapping[str, Any]], profile: Mapping[str, Any], image_base: int
) -> list[dict[str, Any]]:
    by_entry = {_rva(item["entry_rva"], "body entry"): item for item in bodies}
    result: list[dict[str, Any]] = []
    for expected in _function_profiles(profile):
        body = by_entry.get(expected["entry_rva"])
        if body is None:
            raise NativeLuaPropertyConsumerChainError("consumer target body is absent")
        result.append(
            {
                "role": body["role"],
                "entry_rva": body["entry_rva"],
                "entry_va": _hex(image_base + expected["entry_rva"]),
                "atlas_record_sha256": body["atlas_record_sha256"],
                "body_size": body["body_size"],
                "body_sha256": body["body_sha256"],
            }
        )
    return result


def _property_prerequisite_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "analysis_kind": PROPERTY_FACTORY_ANALYSIS_KIND,
        "canonical_sha256": _canonical_sha256(value),
    }


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    bodies = _array(result["function_bodies"], "function_bodies")
    dispatches = [
        item
        for body in bodies
        for item in _array(_mapping(body, "function body").get("staged_lua_dispatches"), "staged dispatches")
    ]
    aggregates = _mapping(
        _mapping(result["target_reference_scan"], "target scan").get("aggregates"),
        "target aggregates",
    )
    return {
        "property_factory_prerequisite_count": 1,
        "property_tag_identity_comparison_count": 2,
        "reviewed_function_count": len(bodies),
        "reviewed_function_bytes": sum(item["body_size"] for item in bodies),
        "sealed_control_flow_graph_count": len(result["control_flow_graphs"]),
        "sealed_control_flow_graph_node_count": sum(item["node_count"] for item in result["control_flow_graphs"]),
        "sealed_control_flow_graph_edge_count": sum(item["edge_count"] for item in result["control_flow_graphs"]),
        "literal_count": len(result["literals"]),
        "constant_count": len(result["constants"]),
        "direct_lua_call_count": sum(
            sum(point["direct_lua_import"] is not None for point in body["reviewed_points"])
            for body in bodies
        ),
        "staged_lua_dispatch_count": len(dispatches),
        "staged_lua_call_count": sum(len(item["call_sites"]) for item in dispatches),
        "placement_count": len(result["placements"]),
        "metamethod_placement_count": sum(item["metamethod_placement_claimed"] for item in result["placements"]),
        "numeric_rawset_placement_count": sum(item["role"] == "numeric_getter_rawset" for item in result["placements"]),
        "target_reference_count": aggregates["reference_count"],
        "target_reference_closure_producer_count": aggregates["closure_producer_count"],
        "target_reference_direct_call_count": aggregates["direct_call_count"],
        "target_reference_comparison_count": aggregates["comparison_count"],
        "target_reference_other_address_count": aggregates["other_address_count"],
        "target_reference_memory_operand_count": aggregates["memory_operand_count"],
        "normalized_identity_match_arm_count": 2,
        "normalized_read_only_arm_count": 1,
        "opaque_identity_mismatch_arm_count": 2,
        "schema_violations": 0,
    }


def _build_native_lua_property_consumer_chain(
    executable: Path,
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
    for value, label in (
        (property_factory_chain, "property_factory_chain"),
        (direct_calls, "direct_calls"),
        (callback_census, "callback_census"),
        (setfield_publications, "setfield_publications"),
        (direct_table_setter_publications, "direct_table_setter_publications"),
        (indirect_settable_publications, "indirect_settable_publications"),
        (table_key_provenance, "table_key_provenance"),
        (terminal_dispositions, "terminal_dispositions"),
        (program_facts, "program_facts"),
        (inventory, "inventory"),
    ):
        _validate_json_tree(value, label)
    validate_native_lua_property_factory_chain(
        executable,
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
    data, image, executable_sha256 = _load_executable(executable)
    decoder, _ = _decoder()
    profile = _PROFILES.get(executable_sha256)
    if profile is None:
        raise NativeLuaPropertyConsumerChainError("executable has no reviewed consumer profile")
    identity = _mapping(program_facts.get("identity"), "program_facts.identity")
    if (
        identity.get("executable_sha256") != executable_sha256
        or identity.get("executable_size") != len(data)
        or identity.get("architecture") != image.architecture
    ):
        raise NativeLuaPropertyConsumerChainError("executable or atlas identity changed")
    source = _property_factory_source(property_factory_chain, profile)
    bodies, graphs = _build_function_records(
        data, image, decoder, program_facts, direct_calls, profile
    )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(identity),
        **_expected_prerequisites(
            direct_calls,
            callback_census,
            setfield_publications,
            direct_table_setter_publications,
            indirect_settable_publications,
            table_key_provenance,
            terminal_dispositions,
            program_facts,
        ),
        "property_factory_chain": _property_prerequisite_identity(property_factory_chain),
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "operand_classes": ["absolute_memory", "immediate"],
            "dynamic_register_call_encodings": list(_REGISTER_CALL_ENCODINGS),
            "cfg_register_write_fields": ["writes_ebx", "writes_esi", "writes_edi", "writes_esp"],
        },
        "property_tag_source": source,
        "consumer_targets": _consumer_targets(bodies, profile, image.image_base),
        "literals": [_literal_record(data, image, item) for item in profile["literals"]],
        "constants": [_constant_record(data, image, item) for item in profile["constants"]],
        "function_bodies": bodies,
        "control_flow_graphs": graphs,
        "placements": _placement_records(profile),
        "target_reference_scan": _target_reference_scan(
            data, image, decoder, program_facts, direct_calls, profile
        ),
        "method": _METHOD,
    }
    result["summary"] = _summary(result)
    _assert_publication_safe(result)
    return result


_FOREIGN_ERRORS = (
    NativeLuaClassFactoryChainError,
    NativeLuaPropertyFactoryChainError,
    NativeLuaSuperRebindingError,
    NativeLuaCClosurePublicationError,
    NativeLuaDirectCallError,
    PEAnchorError,
)


def build_native_lua_property_consumer_chain(
    executable: Path,
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
    """Build the exact build-keyed native Lua property-consumer chain."""
    try:
        return _build_native_lua_property_consumer_chain(
            executable,
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
    except NativeLuaPropertyConsumerChainError:
        raise
    except _FOREIGN_ERRORS as exc:
        raise NativeLuaPropertyConsumerChainError(
            f"property-consumer exact reconstruction failed: {exc}"
        ) from exc


def _validate_native_lua_property_consumer_chain_structure(
    evidence: Mapping[str, Any],
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
    for value, label in (
        (evidence, "evidence"),
        (property_factory_chain, "property_factory_chain"),
        (direct_calls, "direct_calls"),
        (callback_census, "callback_census"),
        (setfield_publications, "setfield_publications"),
        (direct_table_setter_publications, "direct_table_setter_publications"),
        (indirect_settable_publications, "indirect_settable_publications"),
        (table_key_provenance, "table_key_provenance"),
        (terminal_dispositions, "terminal_dispositions"),
        (program_facts, "program_facts"),
    ):
        _validate_json_tree(value, label)
    property_receipt = validate_native_lua_property_factory_chain_structure(
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
    if (
        property_receipt.get("analysis_kind")
        != PROPERTY_FACTORY_STRUCTURE_VERIFICATION_KIND
        or property_receipt.get("status") != "structurally_verified"
    ):
        raise NativeLuaPropertyConsumerChainError(
            "property-factory structural verifier returned another result"
        )
    evidence = _mapping(evidence, "evidence")
    top_keys = {
        "schema_version",
        "analysis_kind",
        "build_identity",
        "atlas",
        "direct_call_census",
        "callback_census",
        "setfield_publication_census",
        "direct_table_setter_publication_census",
        "indirect_settable_publication_census",
        "table_key_provenance_census",
        "terminal_disposition_census",
        "property_factory_chain",
        "decoder",
        "property_tag_source",
        "consumer_targets",
        "literals",
        "constants",
        "function_bodies",
        "control_flow_graphs",
        "placements",
        "target_reference_scan",
        "method",
        "summary",
    }
    _exact_keys(evidence, top_keys, "evidence")
    if evidence.get("schema_version") != SCHEMA_VERSION or evidence.get("analysis_kind") != ANALYSIS_KIND:
        raise NativeLuaPropertyConsumerChainError("unsupported consumer schema or analysis kind")
    identity = _mapping(program_facts.get("identity"), "program_facts.identity")
    if evidence.get("build_identity") != dict(identity):
        raise NativeLuaPropertyConsumerChainError("build identity differs from program facts")
    profile = _PROFILES.get(identity.get("executable_sha256"))
    if profile is None:
        raise NativeLuaPropertyConsumerChainError("build identity has no reviewed consumer profile")
    expected_prerequisites = _expected_prerequisites(
        direct_calls,
        callback_census,
        setfield_publications,
        direct_table_setter_publications,
        indirect_settable_publications,
        table_key_provenance,
        terminal_dispositions,
        program_facts,
    )
    expected_prerequisites["property_factory_chain"] = _property_prerequisite_identity(property_factory_chain)
    for key, expected in expected_prerequisites.items():
        if evidence.get(key) != expected:
            raise NativeLuaPropertyConsumerChainError(f"{key} prerequisite identity differs")
    expected_decoder = {
        "name": "capstone",
        "version": SUPPORTED_CAPSTONE_VERSION,
        "architecture": "x86",
        "mode_bits": 32,
        "operand_classes": ["absolute_memory", "immediate"],
        "dynamic_register_call_encodings": list(_REGISTER_CALL_ENCODINGS),
        "cfg_register_write_fields": ["writes_ebx", "writes_esi", "writes_edi", "writes_esp"],
    }
    if evidence.get("decoder") != expected_decoder or evidence.get("method") != _METHOD:
        raise NativeLuaPropertyConsumerChainError("decoder or method contract differs")
    if evidence.get("property_tag_source") != _property_factory_source(property_factory_chain, profile):
        raise NativeLuaPropertyConsumerChainError("property tag source differs")
    if evidence.get("literals") != [_expected_literal_record(item) for item in profile["literals"]]:
        raise NativeLuaPropertyConsumerChainError("literal profile differs")
    if evidence.get("constants") != [_expected_constant_record(item) for item in profile["constants"]]:
        raise NativeLuaPropertyConsumerChainError("constant profile differs")
    functions = _atlas_functions(program_facts)
    call_map = _direct_call_map(direct_calls)
    try:
        imports = _lua_import_map(direct_calls)
    except NativeLuaSuperRebindingError as exc:
        raise NativeLuaPropertyConsumerChainError(f"Lua import map failed: {exc}") from exc
    body_records = _array(evidence.get("function_bodies"), "function_bodies")
    profiles = _function_profiles(profile)
    if len(body_records) != len(profiles):
        raise NativeLuaPropertyConsumerChainError("reviewed function partition differs")
    normalized_bodies: list[Mapping[str, Any]] = []
    for index, (raw_body, expected) in enumerate(zip(body_records, profiles)):
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
                "direct_lua_call_partition_complete",
                "staged_lua_dispatches",
                "dynamic_register_call_rvas",
                "all_eight_register_call_encodings_checked",
                "staged_register_call_partition_complete",
                "semantic_facts",
            },
            label,
        )
        function = functions.get(expected["entry_rva"])
        if function is None:
            raise NativeLuaPropertyConsumerChainError("reviewed function is absent from atlas")
        expected_base = {
            "role": expected["role"],
            "entry_rva": _hex(expected["entry_rva"]),
            "atlas_record_sha256": atlas_record_sha256(function),
            "body_size": expected["body_size"],
            "body_sha256": expected["body_sha256"],
            "range_start_rva": _hex(expected["entry_rva"]),
            "range_size": expected["body_size"],
            "control_flow_graph_canonical_sha256": expected["cfg_canonical_sha256"],
            "direct_lua_call_partition_complete": True,
            "dynamic_register_call_rvas": [_hex(rva) for rva, _register in _expected_dynamic_partition(expected)],
            "all_eight_register_call_encodings_checked": True,
            "staged_register_call_partition_complete": True,
            "semantic_facts": expected["semantic_facts"],
        }
        for key, value in expected_base.items():
            if body.get(key) != value:
                raise NativeLuaPropertyConsumerChainError(f"{label}.{key} differs")
        expected_points = [_expected_point_record(item) for item in expected["points"]]
        if body.get("reviewed_points") != expected_points:
            raise NativeLuaPropertyConsumerChainError(f"{label} reviewed points differ")
        profiled_direct: list[int] = []
        for point in expected_points:
            api = point["direct_lua_import"]
            if api is None:
                continue
            rva = _rva(point["rva"], "point RVA")
            profiled_direct.append(rva)
            joined = call_map.get(rva)
            if (
                joined is None
                or joined[0].get("entry_rva") != body["entry_rva"]
                or joined[1].get("import_name") != api
                or joined[1].get("library") != LUA_LIBRARY
                or joined[1].get("call_form") != DIRECT_CALL_FORM
                or joined[1].get("instruction_sha256") != point["sha256"]
            ):
                raise NativeLuaPropertyConsumerChainError(f"{label} direct-call join differs")
        if sorted(profiled_direct) != _direct_call_rvas_for_entry(call_map, expected["entry_rva"]):
            raise NativeLuaPropertyConsumerChainError(f"{label} direct-call partition differs")
    graph_map = _validated_graphs(
        {"control_flow_graphs": evidence.get("control_flow_graphs")}, functions
    )
    if set(graph_map) != {item["entry_rva"] for item in profiles}:
        raise NativeLuaPropertyConsumerChainError("reviewed CFG partition differs")
    image_base = _rva(_mapping(program_facts.get("ghidra"), "program_facts.ghidra").get("image_base"), "image base")
    for body, expected in zip(normalized_bodies, profiles):
        graph, nodes, _edges = graph_map[expected["entry_rva"]]
        graph_sha256 = _canonical_sha256(graph)
        if graph_sha256 != expected["cfg_canonical_sha256"] or body.get("control_flow_graph_canonical_sha256") != graph_sha256:
            raise NativeLuaPropertyConsumerChainError("sealed CFG identity differs")
        staged = _dispatch_records(expected, graph, image_base, imports, program_facts, functions)
        if body.get("staged_lua_dispatches") != staged:
            raise NativeLuaPropertyConsumerChainError("staged Lua dispatch records differ")
        for point in body["reviewed_points"]:
            rva = _rva(point["rva"], "point RVA")
            node = nodes.get(rva)
            if node is None or (node.get("size"), node.get("sha256")) != (point["size"], point["sha256"]):
                raise NativeLuaPropertyConsumerChainError("reviewed point does not join CFG")
    expected_targets = _consumer_targets(normalized_bodies, profile, image_base)
    if evidence.get("consumer_targets") != expected_targets:
        raise NativeLuaPropertyConsumerChainError("consumer target records differ")
    expected_placements = _placement_records(profile)
    if evidence.get("placements") != expected_placements:
        raise NativeLuaPropertyConsumerChainError("placement records differ")
    scan = _mapping(evidence.get("target_reference_scan"), "target_reference_scan")
    _exact_keys(scan, {"target_rvas", "target_vas", "scope", "references", "aggregates"}, "target_reference_scan")
    expected_references = [
        _expected_reference(item, image_base, functions)
        for item in sorted(profile["target_references"], key=lambda item: (item["instruction_rva"], item["operand_index"]))
    ]
    targets = sorted(item["entry_rva"] for item in profile["functions"])
    fact_summary = _mapping(program_facts.get("summary"), "program_facts.summary")
    direct_summary = _mapping(direct_calls.get("summary"), "direct_calls.summary")
    expected_scope = {
        "atlas_function_count": fact_summary.get("function_count"),
        "atlas_body_range_count": fact_summary.get("body_range_count"),
        "decoded_bytes": fact_summary.get("function_body_bytes"),
        "decoded_instructions": direct_summary.get("decoded_instructions"),
        "all_declared_ranges_decoded": True,
        "operand_classes": ["absolute_memory", "immediate"],
    }
    if (
        scan.get("target_rvas") != [_hex(value) for value in targets]
        or scan.get("target_vas") != [_hex(image_base + value) for value in targets]
        or scan.get("scope") != expected_scope
        or scan.get("references") != expected_references
        or scan.get("aggregates") != _reference_aggregates(expected_references)
    ):
        raise NativeLuaPropertyConsumerChainError("target-reference scan differs")
    expected_summary = _summary(evidence)
    if evidence.get("summary") != expected_summary:
        raise NativeLuaPropertyConsumerChainError("summary differs")
    _assert_publication_safe(evidence)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": STRUCTURE_VERIFICATION_KIND,
        "status": "structurally_verified",
        "build_identity": dict(identity),
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": dict(expected_summary),
    }


def validate_native_lua_property_consumer_chain_structure(
    evidence: Mapping[str, Any],
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
    """Validate finite consumer evidence without loading the executable."""
    try:
        return _validate_native_lua_property_consumer_chain_structure(
            evidence,
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
    except NativeLuaPropertyConsumerChainError:
        raise
    except _FOREIGN_ERRORS as exc:
        raise NativeLuaPropertyConsumerChainError(
            f"property-consumer structural validation failed: {exc}"
        ) from exc


def validate_native_lua_property_consumer_chain(
    executable: Path,
    evidence: Mapping[str, Any],
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
    """Rebuild and canonical-byte-compare exact property-consumer evidence."""
    _validate_json_tree(evidence, "evidence")
    rebuilt = build_native_lua_property_consumer_chain(
        executable,
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
        raise NativeLuaPropertyConsumerChainError(
            "native Lua property-consumer evidence differs from exact rebuild"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": dict(rebuilt["build_identity"]),
        "evidence_sha256": _canonical_sha256(rebuilt),
        "summary": dict(rebuilt["summary"]),
    }


def encode_native_lua_property_consumer_chain(value: Mapping[str, Any]) -> str:
    """Return deterministic pretty JSON for evidence or a verification receipt."""
    _validate_json_tree(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
