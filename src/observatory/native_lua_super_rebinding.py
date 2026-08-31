"""Exact native Lua ``super`` publication and rebinding chain.

The artifact produced here is deliberately build keyed.  It composes the
already exact table-key publication census with four reviewed native bodies,
three bounded literals, and a whole-atlas direct target-operand partition.
It does not claim runtime reachability or source-level inheritance semantics.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_callbacks import (
    ANALYSIS_KIND as CALLBACK_ANALYSIS_KIND,
)
from src.observatory.native_lua_cclosure_indirect_settable_publications import (
    ANALYSIS_KIND as INDIRECT_SETTABLE_ANALYSIS_KIND,
    _dominators,
    _entry_audit,
    _graph_maps,
    _path_nodes,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    ANALYSIS_KIND as SETFIELD_ANALYSIS_KIND,
    NativeLuaCClosurePublicationError,
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _canonical_bytes,
    _canonical_sha256,
    _containing_range,
    _decode_range,
    _exact_keys,
    _hex,
    _instruction_fact,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_cclosure_table_key_provenance import (
    ANALYSIS_KIND as TABLE_KEY_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as TABLE_KEY_STRUCTURE_VERIFICATION_KIND,
    NativeLuaCClosureTableKeyProvenanceError,
    _enhanced_cfg,
    _validated_graphs,
    validate_native_lua_cclosure_table_key_provenance_census,
    validate_native_lua_cclosure_table_key_provenance_structure,
)
from src.observatory.native_lua_cclosure_table_setter_publications import (
    ANALYSIS_KIND as DIRECT_TABLE_SETTER_ANALYSIS_KIND,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_CALL_ANALYSIS_KIND,
    CALL_FORM as DIRECT_CALL_FORM,
    SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_super_rebinding_chain"
VERIFICATION_KIND = "pe_native_lua_super_rebinding_chain_verification"
STRUCTURE_VERIFICATION_KIND = (
    "pe_native_lua_super_rebinding_chain_structure_verification"
)
LUA_LIBRARY = "lua5.1.dll"
LUA_GLOBALSINDEX = -10002
PE_SECTION_WRITABLE = 0x80000000
MAX_LITERAL_BYTES = 512
_REGISTER_STAGE_PREFIX = {
    "ebx": b"\x8b\x1d",
    "esi": b"\x8b\x35",
    "edi": b"\x8b\x3d",
}
_REGISTER_CALL_BYTES = {
    "ebx": b"\xff\xd3",
    "esi": b"\xff\xd6",
    "edi": b"\xff\xd7",
}
_REGISTER_WRITE_FIELD = {
    "ebx": "writes_ebx",
    "esi": "writes_esi",
    "edi": "writes_edi",
}


_METHOD = {
    "accepted_chain": (
        "Exactly three table-key-provenance rows whose key is super are joined "
        "to reviewed native bodies, instruction points, literals, and a complete "
        "direct target-operand partition of the declared atlas ranges."
    ),
    "lua51_abi_premises": [
        "LUA_GLOBALSINDEX is -10002",
        "lua_upvalueindex one is -10003 and lua_upvalueindex two is -10004",
        "lua_error does not return normally",
    ],
    "target_scan_boundary": (
        "Every instruction in every file-backed program-facts atlas range is "
        "decoded with operand detail. Only immediate operands and absolute "
        "memory displacements equal to either exact callback VA are retained."
    ),
    "native_register_provenance": (
        "Every retained call through EBX or ESI has one exact mov register,[IAT] "
        "stage for its named Lua import. The stage dominates every grouped call "
        "in the sealed caller CFG, no stage-to-call path writes the register, and "
        "the proof uses the explicit 32-bit Windows cdecl nonvolatile-register premise."
    ),
    "structural_boundary": (
        "PE-free validation proves prerequisite joins, exact profile identities, "
        "finite instruction hashes, sealed complete CFG identities, staged-register "
        "dominance and path proofs, partitions, and aggregates. Actual instruction "
        "bytes, literal bytes, decoded register-write classifications, and exhaustive "
        "decoding require exact rebuild validation."
    ),
    "not_claimed": [
        "runtime reachability, execution order, frequency, or persistence",
        "a raw or metamethod-free global store",
        "successful lua_call or cleanup after a Lua error or long jump",
        "native object types, ownership, or field meanings",
        "computed pointers, indirect calls, data references, or Lua-side consumers",
        "source-level inheritance or source equivalence",
        "binary-only proof that arbitrary callees obey the Windows cdecl nonvolatile-register premise",
    ],
}


def _point(role: str, rva: int, encoded: str, api: str | None = None) -> tuple[str, int, str, str | None]:
    return role, rva, encoded, api


_SEALED_PROFILE: dict[str, Any] = {
    "executable_sha256": "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9",
    "publication_sites": [
        {
            "callback_call_rva": 0x002E6C01,
            "caller_entry_rva": 0x002E6900,
            "callback_entry_rva": 0x002E6810,
            "closure_effective_upvalue_count": 0,
            "setter_call_rva": 0x002E6C10,
            "capture_facts": [],
        },
        {
            "callback_call_rva": 0x002EB086,
            "caller_entry_rva": 0x002EB020,
            "callback_entry_rva": 0x002EB230,
            "closure_effective_upvalue_count": 2,
            "setter_call_rva": 0x002EB092,
            "capture_facts": [
                {"upvalue_index": 1, "source": "lua_stack_index_1"},
                {
                    "upvalue_index": 2,
                    "source": "lua_stack_index_minus_3_after_key_and_first_capture",
                },
            ],
        },
        {
            "callback_call_rva": 0x002EB2A5,
            "caller_entry_rva": 0x002EB230,
            "callback_entry_rva": 0x002EB230,
            "closure_effective_upvalue_count": 2,
            "setter_call_rva": 0x002EB2B1,
            "capture_facts": [
                {"upvalue_index": 1, "source": "lightuserdata_from_esi"},
                {"upvalue_index": 2, "source": "lua_upvalueindex_2"},
            ],
        },
    ],
    "literals": [
        {
            "role": "global_key_super",
            "publish_text": True,
            "text": "super",
            "rva": 0x0043BFA0,
            "byte_length_excluding_nul": 5,
            "nul_terminated_bytes_sha256": "d4d1c249a1a435e59c999c3e262163b1022292c314e450419e8edf29fc79e024",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
        {
            "role": "deprecation_message",
            "publish_text": False,
            "text": "DEPRECATION: 'super' has been deprecated in favor of directly calling the base class __init() function. This error can be disabled by calling 'luabind::disable_super_deprecation()'.",
            "rva": 0x0043BE60,
            "byte_length_excluding_nul": 181,
            "nul_terminated_bytes_sha256": "d3f573ecb939aff704f2a7399593c472ecfd189eff5cce8c646ccdeebded29c6",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
        {
            "role": "init_key",
            "publish_text": True,
            "text": "__init",
            "rva": 0x00420F68,
            "byte_length_excluding_nul": 6,
            "nul_terminated_bytes_sha256": "bbd60ce6705e249e0cffaa2e7e02fb2a3915650144e2faba59b0188a89895185",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
    ],
    "functions": [
        {
            "role": "bootstrap_error_callback",
            "entry_rva": 0x002E6810,
            "body_size": 33,
            "body_sha256": "b2047ad08a7ffc19a210f5001f66ba53c9c1f6e8674e7af0cd51b661fd66f82e",
            "cfg_canonical_sha256": "78345f46317b62d42e76a4b88a9bc9a38fff1cc76fca1e4e20f9b13533be9f90",
            "staged_dispatches": [],
            "points": [
                _point("deprecation_literal_push", 0x002E6813, "6860be8300"),
                _point("lua_pushstring", 0x002E681B, "ff1594647d00", "lua_pushstring"),
                _point("lua_error", 0x002E6824, "ff1598647d00", "lua_error"),
                _point("fallback_result_zero", 0x002E682D, "33c0"),
                _point("return", 0x002E6830, "c3"),
            ],
            "semantic_facts": {
                "reads_lua_arguments": False,
                "reads_upvalues": False,
                "normal_effect_under_lua51_premise": "lua_error_nonreturn",
                "binary_fallback_result_count": 0,
            },
        },
        {
            "role": "userdata_environment_helper",
            "entry_rva": 0x002EA430,
            "body_size": 113,
            "body_sha256": "d58bfdfd55ab243032d5f5c0b5c3718f1d96951aa3e6868e5c174e2a4e2a6611",
            "cfg_canonical_sha256": "172d8e6a193b458a765b963a51f5d46370572068998c20e9fd84aaa938415387",
            "staged_dispatches": [
                {
                    "api_name": "lua_rawgeti",
                    "register": "esi",
                    "stage_rva": 0x002EA467,
                    "call_rvas": [0x002EA473, 0x002EA48A],
                }
            ],
            "points": [
                _point("userdata_size_48", 0x002EA43B, "6a30"),
                _point("lua_newuserdata", 0x002EA441, "ff1528657d00", "lua_newuserdata"),
                _point("store_argument_pointer_offset_40", 0x002EA456, "897728"),
                _point("store_zero_offset_44", 0x002EA459, "c7472c00000000"),
                _point("first_registry_reference_offset_32", 0x002EA464, "ff7620"),
                _point("lua_rawgeti_esi_stage", 0x002EA467, "8b35c0647d00"),
                _point("first_lua_rawgeti", 0x002EA473, "ffd6"),
                _point("lua_setfenv", 0x002EA478, "ff154c657d00", "lua_setfenv"),
                _point("second_registry_reference_offset_48", 0x002EA481, "ff7030"),
                _point("second_lua_rawgeti", 0x002EA48A, "ffd6"),
                _point("lua_setmetatable", 0x002EA48F, "ff1530657d00", "lua_setmetatable"),
                _point("return_native_pointer", 0x002EA498, "8bc7"),
            ],
            "semantic_facts": {
                "lua_userdata_bytes": 48,
                "argument_pointer_offset": 40,
                "zero_field_offset": 44,
                "registry_reference_offsets": [32, 48],
                "lua_stack_effect": "one_userdata_left_on_stack",
                "native_return_register": "eax",
            },
        },
        {
            "role": "guarded_dynamic_publisher",
            "entry_rva": 0x002EB020,
            "body_size": 273,
            "body_sha256": "cce4ab6d208cbdcbe5316c73acc1ecc3f621e931d349cd759889d8c5aced0e1b",
            "cfg_canonical_sha256": "530d4e59e6d1b126ab976172ed1d1935c5b458e28a19dfb818e3421ad88b0d33",
            "staged_dispatches": [
                {
                    "api_name": "lua_pushvalue",
                    "register": "ebx",
                    "stage_rva": 0x002EB052,
                    "call_rvas": [0x002EB077, 0x002EB07C, 0x002EB09E],
                },
                {
                    "api_name": "lua_insert",
                    "register": "esi",
                    "stage_rva": 0x002EB0CF,
                    "call_rvas": [0x002EB0D8, 0x002EB0E9],
                },
            ],
            "points": [
                _point("argument_one", 0x002EB02A, "6a01"),
                _point("lua_touserdata", 0x002EB02D, "ff159c647d00", "lua_touserdata"),
                _point("lua_gettop", 0x002EB036, "ff150c657d00", "lua_gettop"),
                _point("userdata_helper_call", 0x002EB046, "e8e5f3ffff"),
                _point("guard_byte_compare", 0x002EB04B, "803d9f9e8b0000"),
                _point("lua_pushvalue_ebx_stage", 0x002EB052, "8b1de4647d00"),
                _point("guard_byte_zero_branch", 0x002EB058, "7441"),
                _point("field_44_compare_one", 0x002EB05A, "837e2c01"),
                _point("field_44_mismatch_branch", 0x002EB05E, "753b"),
                _point("load_field_4", 0x002EB060, "8b4604"),
                _point("compare_field_8", 0x002EB063, "3b4608"),
                _point("equal_fields_branch", 0x002EB066, "7433"),
                _point("super_key_push", 0x002EB068, "68a0bf8300"),
                _point("lua_pushstring", 0x002EB06E, "ff1594647d00", "lua_pushstring"),
                _point("capture_one_index_1", 0x002EB074, "6a01"),
                _point("capture_one_pushvalue", 0x002EB077, "ffd3"),
                _point("capture_two_index_minus_3", 0x002EB079, "6afd"),
                _point("capture_two_pushvalue", 0x002EB07C, "ffd3"),
                _point("upvalue_count_2", 0x002EB07E, "6a02"),
                _point("callback_target_push", 0x002EB080, "6830b26e00"),
                _point("lua_pushcclosure", 0x002EB086, "ff15a0647d00", "lua_pushcclosure"),
                _point("global_index", 0x002EB08C, "68eed8ffff"),
                _point("publication_settable", 0x002EB092, "ff1550657d00", "lua_settable"),
                _point("top_copy_pushvalue", 0x002EB09E, "ffd3"),
                _point("replace_stack_index_1", 0x002EB0A3, "ff1554657d00", "lua_replace"),
                _point("registry_reference_offset_32", 0x002EB0A9, "ff7620"),
                _point("lua_rawgeti", 0x002EB0B2, "ff15c0647d00", "lua_rawgeti"),
                _point("init_length_6", 0x002EB0B8, "6a06"),
                _point("init_literal_push", 0x002EB0BA, "68680f8200"),
                _point("lua_pushlstring", 0x002EB0C0, "ff1508657d00", "lua_pushlstring"),
                _point("lua_gettable", 0x002EB0C9, "ff15bc647d00", "lua_gettable"),
                _point("lua_insert_esi_stage", 0x002EB0CF, "8b3514657d00"),
                _point("first_lua_insert", 0x002EB0D8, "ffd6"),
                _point("lua_settop", 0x002EB0DD, "ff1510657d00", "lua_settop"),
                _point("second_lua_insert", 0x002EB0E9, "ffd6"),
                _point("lua_call_nresults_0", 0x002EB0EB, "6a00"),
                _point("lua_call_saved_nargs", 0x002EB0ED, "ff75fc"),
                _point("lua_call", 0x002EB0F1, "ff1540657d00", "lua_call"),
                _point("cleanup_guard_compare", 0x002EB0FA, "803d9f9e8b0000"),
                _point("cleanup_guard_zero_branch", 0x002EB101, "7422"),
                _point("cleanup_super_key_push", 0x002EB103, "68a0bf8300"),
                _point("cleanup_lua_pushstring", 0x002EB109, "ff1594647d00", "lua_pushstring"),
                _point("cleanup_lua_pushnil", 0x002EB110, "ff15b8647d00", "lua_pushnil"),
                _point("cleanup_global_index", 0x002EB116, "68eed8ffff"),
                _point("cleanup_lua_settable", 0x002EB11C, "ff1550657d00", "lua_settable"),
                _point("normal_result_count_1", 0x002EB127, "b801000000"),
                _point("return", 0x002EB130, "c3"),
            ],
            "semantic_facts": {
                "guard_byte_rva": "0x004b9e9f",
                "required_field_44_value": 1,
                "compared_field_offsets": [4, 8],
                "publication_capture_stack_indices": [1, -3],
                "publication_upvalue_count": 2,
                "registry_reference_offset": 32,
                "init_call_argument_count": "saved_initial_lua_gettop",
                "init_call_result_count": 0,
                "normal_result_count": 1,
                "post_call_clear_condition": "guard_byte_nonzero",
            },
        },
        {
            "role": "self_rebinding_callback",
            "entry_rva": 0x002EB230,
            "body_size": 263,
            "body_sha256": "55323a8ca497f78c3e6e1bfe995113b3071c6a164d239df4cc6b045a63be6e98",
            "cfg_canonical_sha256": "09d9791edcb19acf76325ba58aa58e736b9f87cf1b05c278cefcd338b53fed53",
            "staged_dispatches": [
                {
                    "api_name": "lua_pushstring",
                    "register": "ebx",
                    "stage_rva": 0x002EB250,
                    "call_rvas": [0x002EB26D, 0x002EB287, 0x002EB2CF, 0x002EB316],
                },
                {
                    "api_name": "lua_insert",
                    "register": "esi",
                    "stage_rva": 0x002EB2DA,
                    "call_rvas": [0x002EB2E3, 0x002EB2FD],
                },
            ],
            "points": [
                _point("lua_gettop", 0x002EB23B, "ff150c657d00", "lua_gettop"),
                _point("upvalue_one_index", 0x002EB241, "68edd8ffff"),
                _point("lua_touserdata", 0x002EB24A, "ff159c647d00", "lua_touserdata"),
                _point("lua_pushstring_ebx_stage", 0x002EB250, "8b1d94647d00"),
                _point("first_pointer_offset_4", 0x002EB259, "8b4804"),
                _point("second_pointer_offset_4", 0x002EB262, "8b7104"),
                _point("load_field_4", 0x002EB265, "8b4604"),
                _point("compare_field_8", 0x002EB268, "3b4608"),
                _point("nonempty_branch", 0x002EB26B, "751a"),
                _point("alternate_pushstring", 0x002EB26D, "ffd3"),
                _point("alternate_lua_pushnil", 0x002EB270, "ff15b8647d00", "lua_pushnil"),
                _point("alternate_global_index", 0x002EB276, "68eed8ffff"),
                _point("alternate_lua_settable", 0x002EB27C, "ff1550657d00", "lua_settable"),
                _point("alternate_jump", 0x002EB285, "eb33"),
                _point("publication_pushstring", 0x002EB287, "ffd3"),
                _point("capture_one_lightuserdata_source", 0x002EB289, "56"),
                _point("lua_pushlightuserdata", 0x002EB28B, "ff151c657d00", "lua_pushlightuserdata"),
                _point("capture_two_upvalue_index", 0x002EB291, "68ecd8ffff"),
                _point("lua_pushvalue", 0x002EB297, "ff15e4647d00", "lua_pushvalue"),
                _point("upvalue_count_2", 0x002EB29D, "6a02"),
                _point("self_callback_target_push", 0x002EB29F, "6830b26e00"),
                _point("lua_pushcclosure", 0x002EB2A5, "ff15a0647d00", "lua_pushcclosure"),
                _point("publication_global_index", 0x002EB2AB, "68eed8ffff"),
                _point("publication_lua_settable", 0x002EB2B1, "ff1550657d00", "lua_settable"),
                _point("registry_reference_offset_32", 0x002EB2BA, "ff7620"),
                _point("lua_rawgeti", 0x002EB2C3, "ff15c0647d00", "lua_rawgeti"),
                _point("init_literal_push", 0x002EB2C9, "68680f8200"),
                _point("init_lua_pushstring", 0x002EB2CF, "ffd3"),
                _point("lua_gettable", 0x002EB2D4, "ff15bc647d00", "lua_gettable"),
                _point("lua_insert_esi_stage", 0x002EB2DA, "8b3514657d00"),
                _point("first_lua_insert", 0x002EB2E3, "ffd6"),
                _point("lua_settop", 0x002EB2E8, "ff1510657d00", "lua_settop"),
                _point("upvalue_two_index", 0x002EB2EE, "68ecd8ffff"),
                _point("lua_pushvalue_upvalue_two", 0x002EB2F4, "ff15e4647d00", "lua_pushvalue"),
                _point("second_lua_insert", 0x002EB2FD, "ffd6"),
                _point("lua_call_nresults_0", 0x002EB302, "6a00"),
                _point("lua_call_saved_nargs_plus_1", 0x002EB304, "40"),
                _point("lua_call", 0x002EB307, "ff1540657d00", "lua_call"),
                _point("cleanup_super_key_push", 0x002EB310, "68a0bf8300"),
                _point("cleanup_pushstring", 0x002EB316, "ffd3"),
                _point("cleanup_lua_pushnil", 0x002EB319, "ff15b8647d00", "lua_pushnil"),
                _point("cleanup_global_index", 0x002EB31F, "68eed8ffff"),
                _point("cleanup_lua_settable", 0x002EB325, "ff1550657d00", "lua_settable"),
                _point("normal_result_count_0", 0x002EB32E, "33c0"),
                _point("return", 0x002EB336, "c3"),
            ],
            "semantic_facts": {
                "upvalue_one_index": -10003,
                "upvalue_two_index": -10004,
                "pointer_walk_offsets": [4, 4],
                "compared_field_offsets": [4, 8],
                "alternate_equal_fields_effect": "global_super_nil_assignment_request",
                "self_capture_order": ["lightuserdata_from_esi", "lua_upvalueindex_2"],
                "publication_upvalue_count": 2,
                "registry_reference_offset": 32,
                "init_call_argument_count": "saved_initial_lua_gettop_plus_one",
                "init_call_result_count": 0,
                "post_call_effect": "global_super_nil_assignment_request",
                "normal_result_count": 0,
            },
        },
    ],
    "target_references": [
        {
            "instruction_rva": 0x002E6BFB,
            "owner_entry_rva": 0x002E6900,
            "target_rva": 0x002E6810,
            "encoded": "6810686e00",
            "operand_index": 0,
        },
        {
            "instruction_rva": 0x002EB080,
            "owner_entry_rva": 0x002EB020,
            "target_rva": 0x002EB230,
            "encoded": "6830b26e00",
            "operand_index": 0,
        },
        {
            "instruction_rva": 0x002EB29F,
            "owner_entry_rva": 0x002EB230,
            "target_rva": 0x002EB230,
            "encoded": "6830b26e00",
            "operand_index": 0,
        },
    ],
}


_PROFILES = {_SEALED_PROFILE["executable_sha256"]: _SEALED_PROFILE}


class NativeLuaSuperRebindingError(RuntimeError):
    """Raised when the exact rebinding-chain contract is stale or malformed."""


def _source_identity(value: Mapping[str, Any], kind: str) -> dict[str, Any]:
    if value.get("analysis_kind") != kind:
        raise NativeLuaSuperRebindingError("prerequisite analysis kind differs")
    return {"analysis_kind": kind, "canonical_sha256": _canonical_sha256(value)}


def _atlas_identity(program_facts: Mapping[str, Any]) -> dict[str, Any]:
    summary = _mapping(program_facts.get("summary"), "program_facts.summary")
    return {
        "analysis_kind": program_facts.get("analysis_kind"),
        "canonical_sha256": _canonical_sha256(program_facts),
        "function_count": summary.get("function_count"),
        "body_range_count": summary.get("body_range_count"),
        "function_body_bytes": summary.get("function_body_bytes"),
    }


def _direct_call_map(direct_calls: Mapping[str, Any]) -> dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]]:
    result: dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    for raw_record in _array(direct_calls.get("records"), "direct_calls.records"):
        record = _mapping(raw_record, "direct call record")
        for raw_call in _array(record.get("direct_lua_import_calls"), "direct calls"):
            call = _mapping(raw_call, "direct call")
            rva = _rva(call.get("call_rva"), "direct call RVA")
            if rva in result:
                raise NativeLuaSuperRebindingError("direct call RVAs are not unique")
            result[rva] = (record, call)
    return result


def _lua_import_map(direct_calls: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(
        _array(direct_calls.get("lua_imports"), "direct_calls.lua_imports")
    ):
        item = _mapping(raw, f"direct_calls.lua_imports[{index}]")
        name = item.get("name")
        if (
            type(name) is not str
            or item.get("library") != LUA_LIBRARY
            or name in result
        ):
            raise NativeLuaSuperRebindingError("Lua import identities disagree")
        result[name] = item
    required = {"lua_insert", "lua_pushstring", "lua_pushvalue", "lua_rawgeti"}
    if not required <= set(result):
        raise NativeLuaSuperRebindingError("required staged Lua imports are absent")
    return result


def _expected_instruction_fact(rva: int, encoded: bytes) -> dict[str, Any]:
    return {
        "rva": _hex(rva),
        "size": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _node_instruction_fact(
    nodes: Mapping[int, Mapping[str, Any]],
    rva: int,
    encoded: bytes,
    label: str,
) -> dict[str, Any]:
    node = nodes.get(rva)
    expected = _expected_instruction_fact(rva, encoded)
    if node is None or (node.get("size"), node.get("sha256")) != (
        expected["size"],
        expected["sha256"],
    ):
        raise NativeLuaSuperRebindingError(f"{label} does not join the sealed CFG")
    return expected


def _staged_dispatch_records(
    expected_function: Mapping[str, Any],
    graph: Mapping[str, Any],
    image_base: int,
    imports: Mapping[str, Mapping[str, Any]],
    program_facts: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    caller_entry = expected_function["entry_rva"]
    nodes, edges = _graph_maps(graph)
    dominators = _dominators(edges, caller_entry)
    specs = expected_function["staged_dispatches"]
    expected_partition: list[tuple[int, str]] = []
    records: list[dict[str, Any]] = []
    for spec in specs:
        api_name = spec["api_name"]
        register = spec["register"]
        imported = imports.get(api_name)
        if imported is None or register not in _REGISTER_CALL_BYTES:
            raise NativeLuaSuperRebindingError("staged Lua dispatch profile is invalid")
        iat_rva = _rva(imported.get("iat_rva"), f"{api_name} IAT RVA")
        iat_va = image_base + iat_rva
        if iat_va > 0xFFFFFFFF:
            raise NativeLuaSuperRebindingError("staged Lua import VA overflows x86")
        stage_encoded = _REGISTER_STAGE_PREFIX[register] + struct.pack("<I", iat_va)
        call_encoded = _REGISTER_CALL_BYTES[register]
        stage_rva = spec["stage_rva"]
        call_rvas = spec["call_rvas"]
        if (
            call_rvas != sorted(set(call_rvas))
            or not call_rvas
            or stage_rva not in nodes
        ):
            raise NativeLuaSuperRebindingError("staged Lua dispatch site partition is invalid")
        stage = _node_instruction_fact(
            nodes, stage_rva, stage_encoded, f"{api_name} {register} stage"
        )
        matching_stages = [
            rva
            for rva, node in sorted(nodes.items())
            if (node.get("size"), node.get("sha256"))
            == (len(stage_encoded), hashlib.sha256(stage_encoded).hexdigest())
            and all(rva in dominators.get(call_rva, set()) for call_rva in call_rvas)
        ]
        if matching_stages != [stage_rva]:
            raise NativeLuaSuperRebindingError(
                f"{api_name} calls lack one exact dominating {register.upper()} stage"
            )
        call_sites: list[dict[str, Any]] = []
        for call_rva in call_rvas:
            call = _node_instruction_fact(
                nodes, call_rva, call_encoded, f"{api_name} {register} call"
            )
            path = _path_nodes(edges, stage_rva, call_rva)
            writer_field = _REGISTER_WRITE_FIELD[register]
            writers = sorted(
                rva
                for rva in path - {stage_rva}
                if nodes[rva].get(writer_field) is True
            )
            if stage_rva not in dominators.get(call_rva, set()) or call_rva not in path or writers:
                raise NativeLuaSuperRebindingError(
                    f"{api_name} {register.upper()} provenance is clobbered"
                )
            call_sites.append(
                {
                    "call": call,
                    "stage_dominates_call": True,
                    "stage_to_call_path_rvas": [_hex(rva) for rva in sorted(path)],
                    "stage_to_call_path_node_count": len(path),
                    "post_stage_register_writers": [],
                }
            )
            expected_partition.append((call_rva, register))
        dominated_region = {
            node for node, values in dominators.items() if stage_rva in values
        }
        atlas_entries, declared_entries = _entry_audit(
            program_facts, functions, caller_entry, dominated_region
        )
        if atlas_entries or declared_entries:
            raise NativeLuaSuperRebindingError(
                f"{api_name} staged proof region has an alternate modeled entry"
            )
        records.append(
            {
                "api_name": api_name,
                "library": LUA_LIBRARY,
                "iat_rva": imported["iat_rva"],
                "register": register,
                "stage": stage,
                "matching_dominating_stage_rvas": [_hex(stage_rva)],
                "stage_dominates_all_calls": True,
                "call_sites": call_sites,
                "alternate_atlas_entry_rvas": atlas_entries,
                "declared_direct_call_entries": declared_entries,
                "abi_premise": f"x86_windows_cdecl_nonvolatile_{register}",
            }
        )
    observed_partition = sorted(
        (rva, register)
        for rva, node in nodes.items()
        for register, encoded in _REGISTER_CALL_BYTES.items()
        if (node.get("size"), node.get("sha256"))
        == (len(encoded), hashlib.sha256(encoded).hexdigest())
    )
    if observed_partition != sorted(expected_partition):
        raise NativeLuaSuperRebindingError(
            "staged EBX/ESI/EDI Lua-call partition is incomplete"
        )
    return records


def _literal_record(data: bytes, image: Any, expected: Mapping[str, Any]) -> dict[str, Any]:
    rva = expected["rva"]
    raw = bytearray()
    first_offset: int | None = None
    prior_offset: int | None = None
    for delta in range(MAX_LITERAL_BYTES + 1):
        offset = image.rva_to_file_offset(rva + delta)
        if offset is None or offset >= len(data):
            raise NativeLuaSuperRebindingError("literal is not bounded file-backed data")
        if first_offset is None:
            first_offset = offset
        if prior_offset is not None and offset != prior_offset + 1:
            raise NativeLuaSuperRebindingError("literal bytes are not contiguous")
        prior_offset = offset
        byte = data[offset]
        raw.append(byte)
        if byte == 0:
            break
        if byte < 0x20 or byte > 0x7E:
            raise NativeLuaSuperRebindingError("literal is not printable ASCII")
    else:
        raise NativeLuaSuperRebindingError("literal exceeds bounded length")
    if len(raw) < 2 or raw[-1] != 0:
        raise NativeLuaSuperRebindingError("literal lacks a NUL terminator")
    section = image.section_for_offset(first_offset)
    if (
        section is None
        or section.characteristics & PE_SECTION_WRITABLE
        or image.section_for_offset(prior_offset) != section
    ):
        raise NativeLuaSuperRebindingError("literal is not in one non-writable section")
    observed_text = bytes(raw[:-1]).decode("ascii")
    if observed_text != expected["text"]:
        raise NativeLuaSuperRebindingError(f"{expected['role']} literal text changed")
    record = {
        "role": expected["role"],
        "text": observed_text if expected["publish_text"] else None,
        "text_published": expected["publish_text"],
        "rva": _hex(rva),
        "byte_length_excluding_nul": len(raw) - 1,
        "nul_terminated_bytes_sha256": hashlib.sha256(bytes(raw)).hexdigest(),
        "section_name": section.name,
        "section_rva": _hex(section.virtual_address),
        "section_characteristics": _hex(section.characteristics),
        "section_writable": False,
    }
    if record != _expected_literal_record(expected):
        raise NativeLuaSuperRebindingError(f"{expected['role']} literal identity changed")
    return record


def _expected_literal_record(expected: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "role": expected["role"],
        "text": expected["text"] if expected["publish_text"] else None,
        "text_published": expected["publish_text"],
        "rva": _hex(expected["rva"]),
        "byte_length_excluding_nul": expected["byte_length_excluding_nul"],
        "nul_terminated_bytes_sha256": expected["nul_terminated_bytes_sha256"],
        "section_name": expected["section_name"],
        "section_rva": _hex(expected["section_rva"]),
        "section_characteristics": _hex(expected["section_characteristics"]),
        "section_writable": False,
    }


def _publication_sources(table_keys: Mapping[str, Any], profile: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sources = [
        _mapping(raw, "table-key publication")
        for raw in _array(table_keys.get("publications"), "table_keys.publications")
        if isinstance(raw, Mapping)
        and isinstance(raw.get("key"), Mapping)
        and raw["key"].get("text") == "super"
    ]
    sources.sort(key=lambda item: _rva(item.get("callback_call_rva"), "callback call"))
    expected_calls = [item["callback_call_rva"] for item in profile["publication_sites"]]
    observed_calls = [_rva(item.get("callback_call_rva"), "callback call") for item in sources]
    if observed_calls != expected_calls:
        raise NativeLuaSuperRebindingError("super publication partition changed")
    return sources


def _publication_record(source: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, Any]:
    for key in (
        "callback_call_rva",
        "caller_entry_rva",
        "callback_entry_rva",
        "closure_effective_upvalue_count",
        "setter_call_rva",
    ):
        observed = _rva(source.get(key), key) if key.endswith("_rva") else source.get(key)
        if observed != expected[key]:
            raise NativeLuaSuperRebindingError(f"super publication {key} changed")
    key = _mapping(source.get("key"), "super publication key")
    destination = _mapping(source.get("destination"), "super publication destination")
    if (
        key.get("text") != "super"
        or source.get("setter_import_name") != "lua_settable"
        or source.get("table_index") != LUA_GLOBALSINDEX
        or destination.get("class") != "lua51_global_environment_pseudo_index"
        or destination.get("lua_table_index") != LUA_GLOBALSINDEX
        or destination.get("stable_export_claimed") is not False
    ):
        raise NativeLuaSuperRebindingError("super publication destination or setter changed")
    return {
        "source_record_sha256": _canonical_sha256(source),
        "caller_entry_rva": source["caller_entry_rva"],
        "caller_atlas_record_sha256": source["caller_atlas_record_sha256"],
        "callback_call_rva": source["callback_call_rva"],
        "callback_entry_rva": source["callback_entry_rva"],
        "callback_atlas_record_sha256": source["callback_atlas_record_sha256"],
        "closure_effective_upvalue_count": source["closure_effective_upvalue_count"],
        "grammar_family": source["grammar_family"],
        "key": dict(key),
        "destination": dict(destination),
        "table_index": source["table_index"],
        "setter_call_rva": source["setter_call_rva"],
        "setter_import_name": source["setter_import_name"],
        "source_publication_kind": source["source_publication_kind"],
        "capture_facts": [dict(item) for item in expected["capture_facts"]],
        "vm_stack_trace": dict(_mapping(source.get("vm_stack_trace"), "VM stack trace")),
        "alternate_global_clear_present": source.get("alternate_global_clear") is not None,
    }


def _point_record(instruction: Any, image_base: int, profile_point: tuple[str, int, str, str | None]) -> dict[str, Any]:
    role, rva, encoded_hex, api = profile_point
    encoded = bytes.fromhex(encoded_hex)
    if instruction.address - image_base != rva or bytes(instruction.bytes) != encoded:
        raise NativeLuaSuperRebindingError(f"reviewed instruction {role} changed")
    return {
        "role": role,
        **_instruction_fact(instruction, image_base),
        "direct_lua_import": api,
    }


def _expected_point_record(profile_point: tuple[str, int, str, str | None]) -> dict[str, Any]:
    role, rva, encoded_hex, api = profile_point
    encoded = bytes.fromhex(encoded_hex)
    return {
        "role": role,
        "rva": _hex(rva),
        "size": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "direct_lua_import": api,
    }


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
    imports = _lua_import_map(direct_calls)
    body_records: list[dict[str, Any]] = []
    graphs: list[dict[str, Any]] = []
    decoder.detail = True
    for expected in profile["functions"]:
        entry = expected["entry_rva"]
        function = functions.get(entry)
        if function is None or function.get("thunk") is not False:
            raise NativeLuaSuperRebindingError("reviewed function is absent or a thunk")
        if (
            function.get("body_size") != expected["body_size"]
            or function.get("body_sha256") != expected["body_sha256"]
        ):
            raise NativeLuaSuperRebindingError("reviewed function body identity changed")
        ranges = _array(function.get("ranges"), "function ranges")
        if len(ranges) != 1:
            raise NativeLuaSuperRebindingError("reviewed function no longer has one atlas range")
        raw_range = _mapping(ranges[0], "function range")
        start = _rva(raw_range.get("start_rva"), "range start")
        size = raw_range.get("size")
        if start != entry or type(size) is not int or size != expected["body_size"]:
            raise NativeLuaSuperRebindingError("reviewed function range changed")
        instructions = _decode_range(data, image, start, size, decoder)
        graph = _enhanced_cfg(instructions, image.image_base, (start, size), capstone, x86)
        graph["caller_entry_rva"] = _hex(entry)
        graph_sha256 = _canonical_sha256(graph)
        if graph_sha256 != expected["cfg_canonical_sha256"]:
            raise NativeLuaSuperRebindingError("reviewed function CFG identity changed")
        graphs.append(graph)
        by_rva = {instruction.address - image.image_base: instruction for instruction in instructions}
        points: list[dict[str, Any]] = []
        for profile_point in expected["points"]:
            instruction = by_rva.get(profile_point[1])
            if instruction is None:
                raise NativeLuaSuperRebindingError("reviewed instruction is absent from body")
            point = _point_record(instruction, image.image_base, profile_point)
            api = point["direct_lua_import"]
            if api is not None:
                joined = call_map.get(profile_point[1])
                if (
                    joined is None
                    or joined[0].get("entry_rva") != _hex(entry)
                    or joined[1].get("import_name") != api
                    or joined[1].get("library") != LUA_LIBRARY
                    or joined[1].get("call_form") != DIRECT_CALL_FORM
                    or joined[1].get("instruction_sha256") != point["sha256"]
                ):
                    raise NativeLuaSuperRebindingError(f"reviewed {api} call does not join direct-call census")
            points.append(point)
        staged_dispatches = _staged_dispatch_records(
            expected,
            graph,
            image.image_base,
            imports,
            program_facts,
            functions,
        )
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
                "staged_lua_dispatches": staged_dispatches,
                "staged_register_call_partition_complete": True,
                "semantic_facts": dict(expected["semantic_facts"]),
            }
        )
    return body_records, graphs


def _target_reference_scan(
    data: bytes,
    image: Any,
    decoder: Any,
    program_facts: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    publications: list[Mapping[str, Any]],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    import capstone.x86_const as x86

    decoder.detail = True
    functions = _atlas_functions(program_facts)
    targets = sorted({item["callback_entry_rva"] for item in profile["publication_sites"]})
    target_vas = {image.image_base + rva: rva for rva in targets}
    producer_sites = {
        (_rva(item["callback_call_rva"], "publication call") - 6, _rva(item["callback_entry_rva"], "callback target"))
        for item in publications
    }
    references: list[dict[str, Any]] = []
    decoded_ranges = 0
    decoded_bytes = 0
    decoded_instructions = 0
    for entry, function in sorted(functions.items()):
        owner_hash = atlas_record_sha256(function)
        for raw_range in _array(function.get("ranges"), "atlas ranges"):
            mapped = _mapping(raw_range, "atlas range")
            start = _rva(mapped.get("start_rva"), "range start")
            size = mapped.get("size")
            if type(size) is not int or size <= 0:
                raise NativeLuaSuperRebindingError("atlas range size is invalid")
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
                    if (instruction_rva, target_rva) in producer_sites:
                        use_class = "closure_producer"
                    elif instruction.id == x86.X86_INS_CALL:
                        use_class = "direct_call"
                    elif instruction.id in {x86.X86_INS_CMP, x86.X86_INS_TEST}:
                        use_class = "comparison"
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
    references.sort(
        key=lambda item: (
            _rva(item["instruction_rva"], "reference instruction"),
            item["operand_index"],
        )
    )
    expected_refs = [_expected_reference(item, image.image_base, functions) for item in profile["target_references"]]
    if references != expected_refs:
        raise NativeLuaSuperRebindingError("callback target-reference partition changed")
    summary = _mapping(program_facts.get("summary"), "program_facts.summary")
    direct_summary = _mapping(direct_calls.get("summary"), "direct_calls.summary")
    if (
        decoded_ranges != summary.get("body_range_count")
        or decoded_bytes != summary.get("function_body_bytes")
        or decoded_ranges != direct_summary.get("decoded_ranges")
        or decoded_bytes != direct_summary.get("decoded_bytes")
        or decoded_instructions != direct_summary.get("decoded_instructions")
    ):
        raise NativeLuaSuperRebindingError("target scan did not cover the declared atlas ranges")
    aggregates = _reference_aggregates(references)
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
        "aggregates": aggregates,
    }


def _expected_reference(raw: Mapping[str, Any], image_base: int, functions: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
    encoded = bytes.fromhex(raw["encoded"])
    owner = functions.get(raw["owner_entry_rva"])
    if owner is None:
        raise NativeLuaSuperRebindingError("target-reference owner is absent from atlas")
    target_va = image_base + raw["target_rva"]
    return {
        "instruction_rva": _hex(raw["instruction_rva"]),
        "instruction_size": len(encoded),
        "instruction_sha256": hashlib.sha256(encoded).hexdigest(),
        "owner_entry_rva": _hex(raw["owner_entry_rva"]),
        "owner_atlas_record_sha256": atlas_record_sha256(owner),
        "target_rva": _hex(raw["target_rva"]),
        "target_va": _hex(target_va),
        "operand_class": "immediate",
        "operand_index": raw["operand_index"],
        "use_class": "closure_producer",
    }


def _reference_aggregates(references: list[Mapping[str, Any]]) -> dict[str, Any]:
    classes = [item["use_class"] for item in references]
    return {
        "reference_count": len(references),
        "producer_count": classes.count("closure_producer"),
        "direct_call_count": classes.count("direct_call"),
        "comparison_count": classes.count("comparison"),
        "other_address_count": classes.count("other_address"),
        "memory_operand_count": sum(item["operand_class"] == "absolute_memory" for item in references),
    }


def _callback_targets(
    profile: Mapping[str, Any],
    function_records: list[Mapping[str, Any]],
    image_base: int,
) -> list[dict[str, Any]]:
    by_entry = {_rva(item["entry_rva"], "function entry"): item for item in function_records}
    result = []
    for entry in sorted({item["callback_entry_rva"] for item in profile["publication_sites"]}):
        function = by_entry.get(entry)
        if function is None:
            raise NativeLuaSuperRebindingError("callback target body is absent")
        result.append(
            {
                "entry_rva": function["entry_rva"],
                "entry_va": _hex(image_base + entry),
                "atlas_record_sha256": function["atlas_record_sha256"],
                "body_size": function["body_size"],
                "body_sha256": function["body_sha256"],
            }
        )
    return result


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    scan = _mapping(result["target_reference_scan"], "target scan")
    aggregates = _mapping(scan["aggregates"], "target scan aggregates")
    publications = _array(result["publications"], "publications")
    functions = _array(result["function_bodies"], "function_bodies")
    dispatches = [
        dispatch
        for function in functions
        for dispatch in _array(
            _mapping(function, "function body").get("staged_lua_dispatches"),
            "staged_lua_dispatches",
        )
    ]
    return {
        "publication_count": len(publications),
        "unique_callback_target_count": len(result["callback_targets"]),
        "reviewed_function_count": len(result["function_bodies"]),
        "sealed_control_flow_graph_count": len(result["control_flow_graphs"]),
        "staged_lua_dispatch_count": len(dispatches),
        "staged_lua_call_count": sum(
            len(_array(_mapping(item, "staged dispatch").get("call_sites"), "call_sites"))
            for item in dispatches
        ),
        "literal_count": len(result["literals"]),
        "target_reference_count": aggregates["reference_count"],
        "target_reference_producer_count": aggregates["producer_count"],
        "target_reference_direct_call_count": aggregates["direct_call_count"],
        "target_reference_comparison_count": aggregates["comparison_count"],
        "target_reference_other_address_count": aggregates["other_address_count"],
        "target_reference_memory_operand_count": aggregates["memory_operand_count"],
        "alternate_clear_publication_count": sum(item["alternate_global_clear_present"] for item in publications),
        "schema_violations": 0,
    }


def build_native_lua_super_rebinding_chain(
    executable: Path,
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any],
    table_key_provenance: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact build-keyed native Lua ``super`` chain."""
    inputs = (
        (direct_calls, "direct_calls"),
        (callback_census, "callback_census"),
        (setfield_publications, "setfield_publications"),
        (direct_table_setter_publications, "direct_table_setter_publications"),
        (indirect_settable_publications, "indirect_settable_publications"),
        (table_key_provenance, "table_key_provenance"),
        (program_facts, "program_facts"),
        (inventory, "inventory"),
    )
    for value, label in inputs:
        _validate_json_tree(value, label)
    try:
        prerequisite = validate_native_lua_cclosure_table_key_provenance_census(
            executable,
            table_key_provenance,
            direct_calls,
            callback_census,
            setfield_publications,
            direct_table_setter_publications,
            indirect_settable_publications,
            program_facts,
            inventory=inventory,
        )
        data, image, executable_sha256 = _load_executable(executable)
        decoder, _ = _decoder()
    except (
        NativeLuaCClosureTableKeyProvenanceError,
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        PEAnchorError,
    ) as exc:
        raise NativeLuaSuperRebindingError(f"table-key prerequisite failed exact verification: {exc}") from exc
    profile = _PROFILES.get(executable_sha256)
    if profile is None:
        raise NativeLuaSuperRebindingError("executable has no reviewed super-rebinding profile")
    identity = _mapping(program_facts.get("identity"), "program_facts.identity")
    if (
        identity.get("executable_sha256") != executable_sha256
        or identity.get("executable_size") != len(data)
        or identity.get("architecture") != image.architecture
        or prerequisite.get("evidence_sha256") != _canonical_sha256(table_key_provenance)
    ):
        raise NativeLuaSuperRebindingError("executable or prerequisite identity changed")
    sources = _publication_sources(table_key_provenance, profile)
    publications = [
        _publication_record(source, expected)
        for source, expected in zip(sources, profile["publication_sites"])
    ]
    function_bodies, graphs = _build_function_records(
        data, image, decoder, program_facts, direct_calls, profile
    )
    literals = [_literal_record(data, image, expected) for expected in profile["literals"]]
    target_scan = _target_reference_scan(
        data, image, decoder, program_facts, direct_calls, publications, profile
    )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(identity),
        "atlas": _atlas_identity(program_facts),
        "direct_call_census": _source_identity(direct_calls, DIRECT_CALL_ANALYSIS_KIND),
        "callback_census": _source_identity(callback_census, CALLBACK_ANALYSIS_KIND),
        "setfield_publication_census": _source_identity(setfield_publications, SETFIELD_ANALYSIS_KIND),
        "direct_table_setter_publication_census": _source_identity(
            direct_table_setter_publications, DIRECT_TABLE_SETTER_ANALYSIS_KIND
        ),
        "indirect_settable_publication_census": _source_identity(
            indirect_settable_publications, INDIRECT_SETTABLE_ANALYSIS_KIND
        ),
        "table_key_provenance_census": _source_identity(
            table_key_provenance, TABLE_KEY_ANALYSIS_KIND
        ),
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "operand_classes": ["absolute_memory", "immediate"],
        },
        "callback_targets": _callback_targets(profile, function_bodies, image.image_base),
        "literals": literals,
        "publications": publications,
        "function_bodies": function_bodies,
        "control_flow_graphs": graphs,
        "target_reference_scan": target_scan,
        "method": _METHOD,
    }
    result["summary"] = _summary(result)
    _assert_publication_safe(result)
    return result


def _expected_prerequisites(
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any],
    table_key_provenance: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "atlas": _atlas_identity(program_facts),
        "direct_call_census": _source_identity(direct_calls, DIRECT_CALL_ANALYSIS_KIND),
        "callback_census": _source_identity(callback_census, CALLBACK_ANALYSIS_KIND),
        "setfield_publication_census": _source_identity(setfield_publications, SETFIELD_ANALYSIS_KIND),
        "direct_table_setter_publication_census": _source_identity(
            direct_table_setter_publications, DIRECT_TABLE_SETTER_ANALYSIS_KIND
        ),
        "indirect_settable_publication_census": _source_identity(
            indirect_settable_publications, INDIRECT_SETTABLE_ANALYSIS_KIND
        ),
        "table_key_provenance_census": _source_identity(
            table_key_provenance, TABLE_KEY_ANALYSIS_KIND
        ),
    }


def validate_native_lua_super_rebinding_structure(
    evidence: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any],
    table_key_provenance: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate joins and finite reviewed facts without loading the executable."""
    for value, label in (
        (evidence, "evidence"),
        (direct_calls, "direct_calls"),
        (callback_census, "callback_census"),
        (setfield_publications, "setfield_publications"),
        (direct_table_setter_publications, "direct_table_setter_publications"),
        (indirect_settable_publications, "indirect_settable_publications"),
        (table_key_provenance, "table_key_provenance"),
        (program_facts, "program_facts"),
    ):
        _validate_json_tree(value, label)
    try:
        prerequisite = validate_native_lua_cclosure_table_key_provenance_structure(
            table_key_provenance,
            direct_calls,
            callback_census,
            setfield_publications,
            direct_table_setter_publications,
            indirect_settable_publications,
            program_facts,
        )
    except (NativeLuaCClosureTableKeyProvenanceError, NativeLuaCClosurePublicationError) as exc:
        raise NativeLuaSuperRebindingError(f"table-key structural prerequisite failed: {exc}") from exc
    if (
        prerequisite.get("analysis_kind") != TABLE_KEY_STRUCTURE_VERIFICATION_KIND
        or prerequisite.get("status") != "structurally_verified"
    ):
        raise NativeLuaSuperRebindingError("table-key structural verifier returned another result")
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
        "decoder",
        "callback_targets",
        "literals",
        "publications",
        "function_bodies",
        "control_flow_graphs",
        "target_reference_scan",
        "method",
        "summary",
    }
    _exact_keys(evidence, top_keys, "evidence")
    if evidence.get("schema_version") != SCHEMA_VERSION or evidence.get("analysis_kind") != ANALYSIS_KIND:
        raise NativeLuaSuperRebindingError("unsupported super-rebinding schema or analysis kind")
    identity = _mapping(program_facts.get("identity"), "program_facts.identity")
    if evidence.get("build_identity") != dict(identity):
        raise NativeLuaSuperRebindingError("build identity differs from program facts")
    for document in (
        direct_calls,
        callback_census,
        setfield_publications,
        direct_table_setter_publications,
        indirect_settable_publications,
        table_key_provenance,
    ):
        if document.get("build_identity") != evidence.get("build_identity"):
            raise NativeLuaSuperRebindingError("prerequisite build identities differ")
    profile = _PROFILES.get(identity.get("executable_sha256"))
    if profile is None:
        raise NativeLuaSuperRebindingError("build identity has no reviewed profile")
    expected_prerequisites = _expected_prerequisites(
        direct_calls,
        callback_census,
        setfield_publications,
        direct_table_setter_publications,
        indirect_settable_publications,
        table_key_provenance,
        program_facts,
    )
    for key, expected in expected_prerequisites.items():
        if evidence.get(key) != expected:
            raise NativeLuaSuperRebindingError(f"{key} prerequisite identity differs")
    expected_decoder = {
        "name": "capstone",
        "version": SUPPORTED_CAPSTONE_VERSION,
        "architecture": "x86",
        "mode_bits": 32,
        "operand_classes": ["absolute_memory", "immediate"],
    }
    if evidence.get("decoder") != expected_decoder or evidence.get("method") != _METHOD:
        raise NativeLuaSuperRebindingError("decoder or method contract differs")
    sources = _publication_sources(table_key_provenance, profile)
    expected_publications = [
        _publication_record(source, expected)
        for source, expected in zip(sources, profile["publication_sites"])
    ]
    if evidence.get("publications") != expected_publications:
        raise NativeLuaSuperRebindingError("publication projection differs")
    expected_literals = [_expected_literal_record(item) for item in profile["literals"]]
    if evidence.get("literals") != expected_literals:
        raise NativeLuaSuperRebindingError("literal records differ from reviewed profile")
    functions = _atlas_functions(program_facts)
    body_records = _array(evidence.get("function_bodies"), "function_bodies")
    if len(body_records) != len(profile["functions"]):
        raise NativeLuaSuperRebindingError("reviewed function partition differs")
    call_map = _direct_call_map(direct_calls)
    for index, (raw_body, expected) in enumerate(zip(body_records, profile["functions"])):
        label = f"function_bodies[{index}]"
        body = _mapping(raw_body, label)
        body_keys = {
            "role",
            "entry_rva",
            "atlas_record_sha256",
            "body_size",
            "body_sha256",
            "range_start_rva",
            "range_size",
            "control_flow_graph_canonical_sha256",
            "reviewed_points",
            "staged_lua_dispatches",
            "staged_register_call_partition_complete",
            "semantic_facts",
        }
        _exact_keys(body, body_keys, label)
        function = functions.get(expected["entry_rva"])
        if function is None:
            raise NativeLuaSuperRebindingError("reviewed function is absent from atlas")
        expected_base = {
            "role": expected["role"],
            "entry_rva": _hex(expected["entry_rva"]),
            "atlas_record_sha256": atlas_record_sha256(function),
            "body_size": expected["body_size"],
            "body_sha256": expected["body_sha256"],
            "range_start_rva": _hex(expected["entry_rva"]),
            "range_size": expected["body_size"],
            "control_flow_graph_canonical_sha256": expected["cfg_canonical_sha256"],
            "staged_register_call_partition_complete": True,
            "semantic_facts": expected["semantic_facts"],
        }
        for key, value in expected_base.items():
            if body.get(key) != value:
                raise NativeLuaSuperRebindingError(f"{label}.{key} differs")
        expected_points = [_expected_point_record(item) for item in expected["points"]]
        if body.get("reviewed_points") != expected_points:
            raise NativeLuaSuperRebindingError(f"{label} reviewed instruction facts differ")
        for point in expected_points:
            api = point["direct_lua_import"]
            if api is None:
                continue
            rva = _rva(point["rva"], "point RVA")
            joined = call_map.get(rva)
            if (
                joined is None
                or joined[0].get("entry_rva") != body["entry_rva"]
                or joined[1].get("import_name") != api
                or joined[1].get("instruction_sha256") != point["sha256"]
            ):
                raise NativeLuaSuperRebindingError(f"{label} direct-call join differs")
    graph_map = _validated_graphs(
        {"control_flow_graphs": evidence.get("control_flow_graphs")}, functions
    )
    if set(graph_map) != {item["entry_rva"] for item in profile["functions"]}:
        raise NativeLuaSuperRebindingError("reviewed CFG partition differs")
    imports = _lua_import_map(direct_calls)
    image_base = _rva(
        _mapping(program_facts.get("ghidra"), "program_facts.ghidra").get("image_base"),
        "image base",
    )
    for body, expected in zip(body_records, profile["functions"]):
        graph, nodes, _edges = graph_map[expected["entry_rva"]]
        graph_sha256 = _canonical_sha256(graph)
        if (
            graph_sha256 != expected["cfg_canonical_sha256"]
            or body.get("control_flow_graph_canonical_sha256") != graph_sha256
        ):
            raise NativeLuaSuperRebindingError("sealed CFG identity differs")
        for point in body["reviewed_points"]:
            rva = _rva(point["rva"], "point RVA")
            node = nodes.get(rva)
            if node is None or (node.get("size"), node.get("sha256")) != (
                point["size"],
                point["sha256"],
            ):
                raise NativeLuaSuperRebindingError("reviewed point does not join its CFG node")
        expected_dispatches = _staged_dispatch_records(
            expected,
            graph,
            image_base,
            imports,
            program_facts,
            functions,
        )
        if body.get("staged_lua_dispatches") != expected_dispatches:
            raise NativeLuaSuperRebindingError("staged Lua dispatch proof differs")
    expected_targets = _callback_targets(profile, body_records, image_base)
    if evidence.get("callback_targets") != expected_targets:
        raise NativeLuaSuperRebindingError("callback target records differ")
    scan = _mapping(evidence.get("target_reference_scan"), "target_reference_scan")
    _exact_keys(scan, {"target_rvas", "target_vas", "scope", "references", "aggregates"}, "target_reference_scan")
    expected_references = [
        _expected_reference(item, image_base, functions)
        for item in profile["target_references"]
    ]
    if scan.get("references") != expected_references:
        raise NativeLuaSuperRebindingError("target-reference records differ")
    targets = sorted({item["callback_entry_rva"] for item in profile["publication_sites"]})
    if scan.get("target_rvas") != [_hex(value) for value in targets] or scan.get("target_vas") != [_hex(image_base + value) for value in targets]:
        raise NativeLuaSuperRebindingError("target scan identities differ")
    summary = _mapping(program_facts.get("summary"), "program_facts.summary")
    direct_summary = _mapping(direct_calls.get("summary"), "direct_calls.summary")
    scope = _mapping(scan.get("scope"), "target scan scope")
    expected_scope = {
        "atlas_function_count": summary.get("function_count"),
        "atlas_body_range_count": summary.get("body_range_count"),
        "decoded_bytes": summary.get("function_body_bytes"),
        "decoded_instructions": direct_summary.get("decoded_instructions"),
        "all_declared_ranges_decoded": True,
        "operand_classes": ["absolute_memory", "immediate"],
    }
    if scope != expected_scope or type(scope.get("decoded_instructions")) is not int or scope["decoded_instructions"] <= 0:
        raise NativeLuaSuperRebindingError("target scan scope differs")
    expected_aggregates = _reference_aggregates(expected_references)
    if scan.get("aggregates") != expected_aggregates:
        raise NativeLuaSuperRebindingError("target-reference aggregates differ")
    expected_summary = _summary(evidence)
    if evidence.get("summary") != expected_summary:
        raise NativeLuaSuperRebindingError("summary differs")
    _assert_publication_safe(evidence)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": STRUCTURE_VERIFICATION_KIND,
        "status": "structurally_verified",
        "build_identity": dict(identity),
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": dict(expected_summary),
    }


def validate_native_lua_super_rebinding_chain(
    executable: Path,
    evidence: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any],
    table_key_provenance: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and canonical-byte-compare exact super-rebinding evidence."""
    _validate_json_tree(evidence, "evidence")
    rebuilt = build_native_lua_super_rebinding_chain(
        executable,
        direct_calls,
        callback_census,
        setfield_publications,
        direct_table_setter_publications,
        indirect_settable_publications,
        table_key_provenance,
        program_facts,
        inventory=inventory,
    )
    if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
        raise NativeLuaSuperRebindingError("native Lua super-rebinding evidence differs from exact rebuild")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": dict(rebuilt["build_identity"]),
        "evidence_sha256": _canonical_sha256(rebuilt),
        "summary": dict(rebuilt["summary"]),
    }


def encode_native_lua_super_rebinding_chain(value: Mapping[str, Any]) -> str:
    """Return deterministic pretty JSON for evidence or a verification receipt."""
    _validate_json_tree(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
