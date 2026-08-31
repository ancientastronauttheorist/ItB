"""Exact native Lua ``class`` factory and returned-callback chain.

This build-keyed artifact composes one proven global ``class`` publication
with one proven single-result returned closure.  It seals the two callback
bodies, their finite Lua-facing grammar, exact internal native edges, staged
Lua-import dispatches, and the complete direct target-operand partition over
the declared atlas.  It does not assign source-level class semantics.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_callbacks import (
    ANALYSIS_KIND as CALLBACK_ANALYSIS_KIND,
)
from src.observatory.native_lua_cclosure_indirect_settable_publications import (
    ANALYSIS_KIND as INDIRECT_SETTABLE_ANALYSIS_KIND,
    _graph_maps,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    ANALYSIS_KIND as SETFIELD_ANALYSIS_KIND,
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
from src.observatory.native_lua_cclosure_table_key_provenance import (
    ANALYSIS_KIND as TABLE_KEY_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as TABLE_KEY_STRUCTURE_VERIFICATION_KIND,
    NativeLuaCClosureTableKeyProvenanceError,
    _enhanced_cfg,
    validate_native_lua_cclosure_table_key_provenance_census,
    validate_native_lua_cclosure_table_key_provenance_structure,
)
from src.observatory.native_lua_cclosure_table_setter_publications import (
    ANALYSIS_KIND as DIRECT_TABLE_SETTER_ANALYSIS_KIND,
)
from src.observatory.native_lua_cclosure_terminal_dispositions import (
    ANALYSIS_KIND as TERMINAL_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as TERMINAL_STRUCTURE_VERIFICATION_KIND,
    NativeLuaCClosureTerminalDispositionError,
    validate_native_lua_cclosure_terminal_disposition_census,
    validate_native_lua_cclosure_terminal_disposition_structure,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_CALL_ANALYSIS_KIND,
    CALL_FORM as DIRECT_CALL_FORM,
    SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
)
from src.observatory.native_lua_super_rebinding import (
    NativeLuaSuperRebindingError,
    _lua_import_map,
    _staged_dispatch_records,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_class_factory_chain"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
LUA_LIBRARY = "lua5.1.dll"
LUA_GLOBALSINDEX = -10002
LUA_REGISTRYINDEX = -10000
LUA_UPVALUEINDEX_ONE = -10003
PE_SECTION_WRITABLE = 0x80000000
MAX_LITERAL_BYTES = 256


class NativeLuaClassFactoryChainError(RuntimeError):
    """Raised when the exact class-factory chain is stale or malformed."""


def _point(
    role: str,
    rva: int,
    encoded: str,
    api: str | None = None,
) -> tuple[str, int, str, str | None]:
    return role, rva, encoded, api


_METHOD = {
    "accepted_chain": (
        "Exactly one table-key row for class is joined to exactly one returned "
        "single-result closure row, two sealed callback bodies, finite instruction "
        "and stack facts, selected native edges, and a complete direct target-operand partition."
    ),
    "lua51_abi_premises": [
        "LUA_GLOBALSINDEX is -10002",
        "LUA_REGISTRYINDEX is -10000",
        "lua_upvalueindex one is -10003",
        "lua_error does not return normally",
    ],
    "native_register_provenance": (
        "Every retained EBX, ESI, or EDI Lua call has one exact import stage that "
        "dominates every grouped call in the sealed caller CFG. No stage-to-call "
        "path writes that register under the explicit 32-bit Windows cdecl premise."
    ),
    "target_scan_boundary": (
        "Every instruction in every file-backed program-facts atlas range is decoded "
        "with operand detail. Only immediate and absolute-memory operands equal to "
        "either exact callback VA are retained."
    ),
    "structural_boundary": (
        "PE-free validation proves prerequisite joins, sealed profile and full-CFG "
        "identities, staged-register graph proofs, direct-edge joins, finite partitions, "
        "and aggregates. Instruction bytes, literal bytes, decoded register writes, "
        "and exhaustive atlas decoding require exact rebuild validation."
    ),
    "not_claimed": [
        "runtime reachability, execution order, frequency, state continuity, or persistence",
        "a raw or durable global export or absence of settable metamethod effects",
        "allocation, initializer, helper, registry lookup, assertion, or error-path success",
        "valid registry references or proof that returned registry values are tables",
        "native type, container, relationship, ownership, or field semantic names",
        "source-level class, base, derivation, inheritance, or source equivalence",
        "identity or callability of any eventual returned-closure consumer",
        "computed, indirect, data, un-atlased, or Lua-side references",
        "binary-only proof that arbitrary callees obey the Windows cdecl nonvolatile-register premise",
    ],
}


_SEALED_PROFILE: dict[str, Any] = {
    "executable_sha256": "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9",
    "publication": {
        "constructor_entry_rva": 0x002E6900,
        "callback_call_rva": 0x002E6BA1,
        "callback_entry_rva": 0x002EC220,
        "setter_call_rva": 0x002E6BB0,
        "closure_effective_upvalue_count": 0,
    },
    "returned_closure": {
        "caller_entry_rva": 0x002EC220,
        "callback_call_rva": 0x002EC328,
        "callback_entry_rva": 0x002EC110,
        "literal_upvalue_count": 1,
        "result_count": 1,
    },
    "literals": [
        {
            "role": "global_key_class",
            "text": "class",
            "rva": 0x0043BF98,
            "byte_length_excluding_nul": 5,
            "nul_terminated_bytes_sha256": "ac29f1a6000f3a79fef892ab36fe5c9596147e552f455748bc122c4e6975d463",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
        {
            "role": "invalid_construct_message",
            "text": "invalid construct, expected class name",
            "rva": 0x0043CA60,
            "byte_length_excluding_nul": 38,
            "nul_terminated_bytes_sha256": "83b518a181f1b69fa42c84f341b27ad69428d57fca472f82d13cf838436820a6",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
        {
            "role": "embedded_nul_message",
            "text": "luabind does not support class names with extra nulls",
            "rva": 0x0043CA88,
            "byte_length_excluding_nul": 53,
            "nul_terminated_bytes_sha256": "b5218c39e396ace20c4b730d22ec34d91ec5de38f4a8de7cc03a7db3370386dc",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
        {
            "role": "returned_callback_error_message",
            "text": "expected class to derive from or a newline",
            "rva": 0x0043C99C,
            "byte_length_excluding_nul": 42,
            "nul_terminated_bytes_sha256": "385b64f3a5b446ca3567f5a8e53d0339498e26f514bf7dc6e0cf026c0a00bf16",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
    ],
    "functions": [
        {
            "role": "published_factory_callback",
            "entry_rva": 0x002EC220,
            "body_size": 296,
            "body_sha256": "8a9c01de90919d67efa728e4ed9e41e9f9d68fa7f0faf0e8abbdd809cce91f9e",
            "cfg_canonical_sha256": "715e31330f98e4d66d65a9e726092f5e6a4467dc2117a2976c30b1b872a5dfb6",
            "staged_dispatches": [
                {
                    "api_name": "lua_pushstring",
                    "register": "ebx",
                    "stage_rva": 0x002EC252,
                    "call_rvas": [0x002EC287, 0x002EC2C5, 0x002EC309],
                }
            ],
            "points": [
                _point("lua_gettop", 0x002EC24C, "ff150c657d00", "lua_gettop"),
                _point("lua_pushstring_ebx_stage", 0x002EC252, "8b1d94647d00"),
                _point("argument_count_compare_one", 0x002EC25B, "83f801"),
                _point("argument_count_mismatch_branch", 0x002EC25E, "7521"),
                _point("argument_one_for_type", 0x002EC260, "6a01"),
                _point("lua_type", 0x002EC263, "ff15fc647d00", "lua_type"),
                _point("type_compare_string_code_four", 0x002EC26C, "83f804"),
                _point("type_mismatch_branch", 0x002EC26F, "7510"),
                _point("argument_one_for_isnumber", 0x002EC271, "6a01"),
                _point("lua_isnumber", 0x002EC274, "ff1580647d00", "lua_isnumber"),
                _point("numeric_result_test", 0x002EC27D, "85c0"),
                _point("nonnumeric_fallthrough_branch", 0x002EC27F, "7412"),
                _point("invalid_construct_literal_push", 0x002EC281, "6860ca8300"),
                _point("invalid_construct_pushstring", 0x002EC287, "ffd3"),
                _point("invalid_construct_lua_error", 0x002EC28A, "ff1598647d00", "lua_error"),
                _point("null_length_output", 0x002EC293, "6a00"),
                _point("argument_one_for_tolstring", 0x002EC295, "6a01"),
                _point("lua_tolstring_first", 0x002EC298, "ff1500657d00", "lua_tolstring"),
                _point("strlen_start", 0x002EC2A3, "8d4701"),
                _point("strlen_byte_load", 0x002EC2A6, "8a0f"),
                _point("strlen_byte_test", 0x002EC2A9, "84c9"),
                _point("strlen_loop_branch", 0x002EC2AB, "75f9"),
                _point("lua_objlen", 0x002EC2B2, "ff15a8647d00", "lua_objlen"),
                _point("strlen_objlen_compare", 0x002EC2BB, "3bf8"),
                _point("equal_lengths_branch", 0x002EC2BD, "7412"),
                _point("embedded_nul_literal_push", 0x002EC2BF, "6888ca8300"),
                _point("embedded_nul_pushstring", 0x002EC2C5, "ffd3"),
                _point("embedded_nul_lua_error", 0x002EC2C8, "ff1598647d00", "lua_error"),
                _point("second_null_length_output", 0x002EC2D1, "6a00"),
                _point("second_argument_one", 0x002EC2D3, "6a01"),
                _point("lua_tolstring_second", 0x002EC2D6, "ff1500657d00", "lua_tolstring"),
                _point("userdata_size_72", 0x002EC2E1, "6a48"),
                _point("lua_newuserdata", 0x002EC2E4, "ff1528657d00", "lua_newuserdata"),
                _point("newuserdata_null_branch", 0x002EC2FC, "7409"),
                _point("initializer_name_pointer_push", 0x002EC2FE, "57"),
                _point("initializer_state_push", 0x002EC2FF, "56"),
                _point("initializer_userdata_this", 0x002EC300, "8bc8"),
                _point("initializer_call", 0x002EC302, "e8e9e9ffff"),
                _point("validated_name_pointer_push", 0x002EC307, "57"),
                _point("validated_name_pushstring", 0x002EC309, "ffd3"),
                _point("userdata_duplicate_index_minus_two", 0x002EC30B, "6afe"),
                _point("lua_pushvalue", 0x002EC30E, "ff15e4647d00", "lua_pushvalue"),
                _point("global_table_index", 0x002EC314, "68eed8ffff"),
                _point("lua_settable", 0x002EC31A, "ff1550657d00", "lua_settable"),
                _point("returned_closure_upvalue_count_one", 0x002EC320, "6a01"),
                _point("returned_callback_target_push", 0x002EC322, "6810c16e00"),
                _point("returned_lua_pushcclosure", 0x002EC328, "ff15a0647d00", "lua_pushcclosure"),
                _point("normal_result_count_one", 0x002EC331, "b801000000"),
                _point("return", 0x002EC347, "c3"),
            ],
            "semantic_facts": {
                "required_argument_count": 1,
                "required_lua_type_code": 4,
                "lua_isnumber_required_result": 0,
                "accepted_length_relation": "nul_terminated_length_equals_lua_objlen",
                "userdata_allocation_request_bytes": 72,
                "initializer_edge_condition": "newuserdata_result_nonzero",
                "global_table_index": LUA_GLOBALSINDEX,
                "userdata_duplicate_stack_index": -2,
                "returned_closure_upvalue_count": 1,
                "normal_result_count": 1,
                "lua51_vm_stack_trace": [
                    {"step": "after_userdata", "stack": ["A", "U"]},
                    {"step": "after_name", "stack": ["A", "U", "N"]},
                    {"step": "after_userdata_duplicate", "stack": ["A", "U", "N", "U"]},
                    {"step": "after_global_settable", "stack": ["A", "U"]},
                    {"step": "after_one_upvalue_closure", "stack": ["A", "C"]},
                    {"step": "selected_normal_result", "stack": ["C"]},
                ],
            },
        },
        {
            "role": "returned_callback",
            "entry_rva": 0x002EC110,
            "body_size": 269,
            "body_sha256": "a138a00ca47281aa3b4fb0db11a3aa5e875616a57b3684f7598e4b0517b900e3",
            "cfg_canonical_sha256": "c1212e08e59965211c3691fc52551f88f3441ba801bcfa7fe599afcb775dd55b",
            "staged_dispatches": [
                {
                    "api_name": "lua_touserdata",
                    "register": "edi",
                    "stage_rva": 0x002EC126,
                    "call_rvas": [0x002EC132, 0x002EC1A1],
                },
                {
                    "api_name": "lua_rawgeti",
                    "register": "esi",
                    "stage_rva": 0x002EC1C0,
                    "call_rvas": [0x002EC1CC, 0x002EC1D7, 0x002EC1EC, 0x002EC1F7],
                },
            ],
            "points": [
                _point("lua_touserdata_edi_stage", 0x002EC126, "8b3d9c647d00"),
                _point("upvalue_one_index", 0x002EC12C, "68edd8ffff"),
                _point("upvalue_one_touserdata", 0x002EC132, "ffd7"),
                _point("upvalue_pointer_null_test", 0x002EC13C, "85f6"),
                _point("upvalue_pointer_nonnull_branch", 0x002EC13E, "7514"),
                _point("first_assertion_call", 0x002EC14C, "e871db0800"),
                _point("first_helper_index_upvalue_one", 0x002EC154, "baedd8ffff"),
                _point("first_helper_call", 0x002EC15B, "e800f4ffff"),
                _point("first_helper_result_test", 0x002EC160, "84c0"),
                _point("first_helper_success_branch", 0x002EC162, "7514"),
                _point("second_assertion_call", 0x002EC170, "e84ddb0800"),
                _point("second_helper_index_argument_one", 0x002EC178, "ba01000000"),
                _point("second_helper_call", 0x002EC17F, "e8dcf3ffff"),
                _point("second_helper_result_test", 0x002EC184, "84c0"),
                _point("second_helper_success_branch", 0x002EC186, "7516"),
                _point("returned_error_literal_push", 0x002EC188, "689cc98300"),
                _point("returned_error_pushstring", 0x002EC18E, "ff1594647d00", "lua_pushstring"),
                _point("returned_lua_error", 0x002EC195, "ff1598647d00", "lua_error"),
                _point("argument_one_for_touserdata", 0x002EC19E, "6a01"),
                _point("argument_one_touserdata", 0x002EC1A1, "ffd7"),
                _point("local_first_word_zero", 0x002EC1A6, "c745f000000000"),
                _point("local_second_word_argument_pointer", 0x002EC1B4, "897df4"),
                _point("mutation_helper_call", 0x002EC1B8, "e883efffff"),
                _point("first_upvalue_reference_offset_32", 0x002EC1BD, "ff7620"),
                _point("lua_rawgeti_esi_stage", 0x002EC1C0, "8b35c0647d00"),
                _point("first_upvalue_rawgeti", 0x002EC1CC, "ffd6"),
                _point("first_argument_reference_offset_32", 0x002EC1CE, "ff7720"),
                _point("first_argument_rawgeti", 0x002EC1D7, "ffd6"),
                _point("first_pair_helper_call", 0x002EC1DB, "e870feffff"),
                _point("reload_upvalue_pointer", 0x002EC1E0, "8b45ec"),
                _point("second_upvalue_reference_offset_40", 0x002EC1E3, "ff7028"),
                _point("second_upvalue_rawgeti", 0x002EC1EC, "ffd6"),
                _point("second_argument_reference_offset_40", 0x002EC1EE, "ff7728"),
                _point("second_argument_rawgeti", 0x002EC1F7, "ffd6"),
                _point("second_pair_helper_call", 0x002EC1FE, "e84dfeffff"),
                _point("final_destination_pointer_reload", 0x002EC203, "8b4dec"),
                _point("final_source_word_load", 0x002EC206, "8b07"),
                _point("final_word_store", 0x002EC20A, "8901"),
                _point("normal_result_count_zero", 0x002EC20C, "33c0"),
                _point("return", 0x002EC21C, "c3"),
            ],
            "semantic_facts": {
                "upvalue_one_index": LUA_UPVALUEINDEX_ONE,
                "native_helper_inputs": [
                    {"call_rva": "0x002ec15b", "lua_index": LUA_UPVALUEINDEX_ONE},
                    {"call_rva": "0x002ec17f", "lua_index": 1},
                ],
                "registry_lookup_pairs": [
                    {
                        "registry_index": LUA_REGISTRYINDEX,
                        "reference_sources": ["upvalue_pointer_plus_32", "argument_pointer_plus_32"],
                        "subsequent_helper_call_rva": "0x002ec1db",
                    },
                    {
                        "registry_index": LUA_REGISTRYINDEX,
                        "reference_sources": ["upvalue_pointer_plus_40", "argument_pointer_plus_40"],
                        "subsequent_helper_call_rva": "0x002ec1fe",
                    },
                ],
                "final_word_copy": {
                    "source": "argument_pointer_offset_zero",
                    "destination": "upvalue_pointer_offset_zero",
                    "byte_width": 4,
                },
                "normal_result_count": 0,
            },
        },
    ],
    "native_edges": [
        {
            "role": "conditional_initializer_edge",
            "source_entry_rva": 0x002EC220,
            "instruction_rva": 0x002EC302,
            "target_entry_rva": 0x002EACF0,
            "encoded": "e8e9e9ffff",
            "condition": "newuserdata_result_nonzero",
        },
        {
            "role": "returned_helper_upvalue_index",
            "source_entry_rva": 0x002EC110,
            "instruction_rva": 0x002EC15B,
            "target_entry_rva": 0x002EB560,
            "encoded": "e800f4ffff",
            "condition": None,
        },
        {
            "role": "returned_helper_argument_one",
            "source_entry_rva": 0x002EC110,
            "instruction_rva": 0x002EC17F,
            "target_entry_rva": 0x002EB560,
            "encoded": "e8dcf3ffff",
            "condition": None,
        },
        {
            "role": "returned_mutation_helper",
            "source_entry_rva": 0x002EC110,
            "instruction_rva": 0x002EC1B8,
            "target_entry_rva": 0x002EB140,
            "encoded": "e883efffff",
            "condition": None,
        },
        {
            "role": "first_registry_pair_helper",
            "source_entry_rva": 0x002EC110,
            "instruction_rva": 0x002EC1DB,
            "target_entry_rva": 0x002EC050,
            "encoded": "e870feffff",
            "condition": None,
        },
        {
            "role": "second_registry_pair_helper",
            "source_entry_rva": 0x002EC110,
            "instruction_rva": 0x002EC1FE,
            "target_entry_rva": 0x002EC050,
            "encoded": "e84dfeffff",
            "condition": None,
        },
    ],
    "target_references": [
        {
            "instruction_rva": 0x002E6B9B,
            "owner_entry_rva": 0x002E6900,
            "target_rva": 0x002EC220,
            "encoded": "6820c26e00",
            "operand_index": 0,
        },
        {
            "instruction_rva": 0x002EC322,
            "owner_entry_rva": 0x002EC220,
            "target_rva": 0x002EC110,
            "encoded": "6810c16e00",
            "operand_index": 0,
        },
    ],
}


_PROFILES = {_SEALED_PROFILE["executable_sha256"]: _SEALED_PROFILE}


def _source_identity(value: Mapping[str, Any], kind: str) -> dict[str, Any]:
    if value.get("analysis_kind") != kind:
        raise NativeLuaClassFactoryChainError("prerequisite analysis kind differs")
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


def _direct_call_map(
    direct_calls: Mapping[str, Any],
) -> dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]]:
    result: dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    for record_index, raw_record in enumerate(
        _array(direct_calls.get("records"), "direct_calls.records")
    ):
        record = _mapping(raw_record, f"direct_calls.records[{record_index}]")
        for raw_call in _array(
            record.get("direct_lua_import_calls"), "direct Lua calls"
        ):
            call = _mapping(raw_call, "direct Lua call")
            rva = _rva(call.get("call_rva"), "direct Lua call RVA")
            if rva in result:
                raise NativeLuaClassFactoryChainError("direct Lua call RVAs repeat")
            result[rva] = (record, call)
    return result


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
    data: bytes,
    image: Any,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    rva = expected["rva"]
    raw = bytearray()
    first_offset: int | None = None
    prior_offset: int | None = None
    for delta in range(MAX_LITERAL_BYTES + 1):
        offset = image.rva_to_file_offset(rva + delta)
        if offset is None or offset >= len(data):
            raise NativeLuaClassFactoryChainError("literal is not bounded file-backed data")
        if first_offset is None:
            first_offset = offset
        if prior_offset is not None and offset != prior_offset + 1:
            raise NativeLuaClassFactoryChainError("literal bytes are not contiguous")
        prior_offset = offset
        byte = data[offset]
        raw.append(byte)
        if byte == 0:
            break
        if byte < 0x20 or byte > 0x7E:
            raise NativeLuaClassFactoryChainError("literal is not printable ASCII")
    else:
        raise NativeLuaClassFactoryChainError("literal exceeds bounded length")
    if len(raw) < 2 or raw[-1] != 0 or first_offset is None or prior_offset is None:
        raise NativeLuaClassFactoryChainError("literal lacks a NUL terminator")
    section = image.section_for_offset(first_offset)
    if (
        section is None
        or section.characteristics & PE_SECTION_WRITABLE
        or image.section_for_offset(prior_offset) != section
    ):
        raise NativeLuaClassFactoryChainError("literal is not in one non-writable section")
    observed = bytes(raw[:-1]).decode("ascii")
    record = {
        "role": expected["role"],
        "text": observed,
        "rva": _hex(rva),
        "byte_length_excluding_nul": len(raw) - 1,
        "nul_terminated_bytes_sha256": hashlib.sha256(bytes(raw)).hexdigest(),
        "section_name": section.name,
        "section_rva": _hex(section.virtual_address),
        "section_characteristics": _hex(section.characteristics),
        "section_writable": False,
    }
    if record != _expected_literal_record(expected):
        raise NativeLuaClassFactoryChainError(f"{expected['role']} literal identity changed")
    return record


def _class_publication(
    table_key_provenance: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    matches = [
        _mapping(raw, "table-key publication")
        for raw in _array(
            table_key_provenance.get("publications"),
            "table_key_provenance.publications",
        )
        if isinstance(raw, Mapping)
        and isinstance(raw.get("key"), Mapping)
        and raw["key"].get("text") == "class"
    ]
    if len(matches) != 1:
        raise NativeLuaClassFactoryChainError("class publication is not unique")
    source = matches[0]
    expected = profile["publication"]
    checks = {
        "caller_entry_rva": expected["constructor_entry_rva"],
        "callback_call_rva": expected["callback_call_rva"],
        "callback_entry_rva": expected["callback_entry_rva"],
        "setter_call_rva": expected["setter_call_rva"],
    }
    for key, value in checks.items():
        if _rva(source.get(key), key) != value:
            raise NativeLuaClassFactoryChainError(f"class publication {key} changed")
    key = _mapping(source.get("key"), "class publication key")
    destination = _mapping(source.get("destination"), "class publication destination")
    expected_key = _expected_literal_record(profile["literals"][0])
    expected_key.pop("role")
    if (
        source.get("closure_effective_upvalue_count")
        != expected["closure_effective_upvalue_count"]
        or source.get("setter_import_name") != "lua_settable"
        or source.get("table_index") != LUA_GLOBALSINDEX
        or destination.get("class") != "lua51_global_environment_pseudo_index"
        or destination.get("lua_table_index") != LUA_GLOBALSINDEX
        or destination.get("stable_export_claimed") is not False
        or key != expected_key
    ):
        raise NativeLuaClassFactoryChainError("class publication grammar changed")
    return {
        "source_record_sha256": _canonical_sha256(source),
        "constructor_entry_rva": source["caller_entry_rva"],
        "constructor_atlas_record_sha256": source["caller_atlas_record_sha256"],
        "callback_call_rva": source["callback_call_rva"],
        "callback_entry_rva": source["callback_entry_rva"],
        "callback_atlas_record_sha256": source["callback_atlas_record_sha256"],
        "closure_effective_upvalue_count": source["closure_effective_upvalue_count"],
        "grammar_family": source["grammar_family"],
        "key": dict(key),
        "destination": dict(destination),
        "setter_import_name": source["setter_import_name"],
        "setter_call_rva": source["setter_call_rva"],
        "source_publication_kind": source["source_publication_kind"],
        "vm_stack_trace": dict(_mapping(source.get("vm_stack_trace"), "VM stack trace")),
    }


def _returned_closure(
    terminal_dispositions: Mapping[str, Any],
    publication: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    expected = profile["returned_closure"]
    matches = [
        _mapping(raw, "terminal disposition")
        for raw in _array(
            terminal_dispositions.get("dispositions"),
            "terminal_dispositions.dispositions",
        )
        if isinstance(raw, Mapping)
        and _rva(raw.get("callback_call_rva"), "terminal callback call")
        == expected["callback_call_rva"]
    ]
    if len(matches) != 1:
        raise NativeLuaClassFactoryChainError("returned closure disposition is not unique")
    source = matches[0]
    witness = _mapping(
        source.get("caller_callback_target_witness"),
        "returned closure caller witness",
    )
    if (
        _rva(source.get("caller_entry_rva"), "returned caller")
        != expected["caller_entry_rva"]
        or _rva(source.get("callback_entry_rva"), "returned target")
        != expected["callback_entry_rva"]
        or source.get("literal_upvalue_count") != expected["literal_upvalue_count"]
        or source.get("result_count") != expected["result_count"]
        or source.get("disposition_kind") != "lua_callback_single_result"
        or source.get("upvalue_argument_kind") != "immediate"
        or witness.get("callback_target_entry_rva")
        != publication["callback_entry_rva"]
        or witness.get("construction_call_rva") != publication["callback_call_rva"]
        or witness.get("constructor_entry_rva")
        != publication["constructor_entry_rva"]
    ):
        raise NativeLuaClassFactoryChainError("returned closure chain changed")
    return {
        "source_record_sha256": _canonical_sha256(source),
        "caller_entry_rva": source["caller_entry_rva"],
        "caller_atlas_record_sha256": source["caller_atlas_record_sha256"],
        "callback_call_rva": source["callback_call_rva"],
        "callback_call_instruction_sha256": source["callback_call_instruction_sha256"],
        "callback_entry_rva": source["callback_entry_rva"],
        "callback_atlas_record_sha256": source["callback_atlas_record_sha256"],
        "literal_upvalue_count": source["literal_upvalue_count"],
        "result_count": source["result_count"],
        "disposition_kind": source["disposition_kind"],
        "epilogue_kind": source["epilogue_kind"],
        "caller_callback_target_witness": dict(witness),
        "reviewed_sequence": [
            dict(_mapping(item, "returned reviewed sequence"))
            for item in _array(source.get("reviewed_sequence"), "reviewed_sequence")
        ],
    }


def _point_record(
    instruction: Any,
    image_base: int,
    profile_point: tuple[str, int, str, str | None],
) -> dict[str, Any]:
    role, rva, encoded_hex, api = profile_point
    encoded = bytes.fromhex(encoded_hex)
    if instruction.address - image_base != rva or bytes(instruction.bytes) != encoded:
        raise NativeLuaClassFactoryChainError(f"reviewed instruction {role} changed")
    return {
        "role": role,
        **_instruction_fact(instruction, image_base),
        "direct_lua_import": api,
    }


def _expected_point_record(
    profile_point: tuple[str, int, str, str | None],
) -> dict[str, Any]:
    role, rva, encoded_hex, api = profile_point
    encoded = bytes.fromhex(encoded_hex)
    return {
        "role": role,
        "rva": _hex(rva),
        "size": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "direct_lua_import": api,
    }


def _with_edi_writes(
    graph: dict[str, Any],
    instructions: list[Any],
    x86: Any,
) -> dict[str, Any]:
    if len(graph["nodes"]) != len(instructions):
        raise NativeLuaClassFactoryChainError("CFG and decoder instruction counts differ")
    for node, instruction in zip(graph["nodes"], instructions):
        try:
            _reads, writes = instruction.regs_access()
        except Exception as exc:
            raise NativeLuaClassFactoryChainError(
                "Capstone could not classify EDI writes"
            ) from exc
        node["writes_edi"] = x86.X86_REG_EDI in writes
    return graph


_FLOW_KINDS = {
    "fallthrough",
    "call_fallthrough",
    "direct_conditional_branch",
    "direct_unconditional_branch",
    "terminal",
    "indirect_jump",
}


def _validated_graphs(
    evidence: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
) -> dict[int, tuple[Mapping[str, Any], dict[int, Mapping[str, Any]], dict[int, set[int]]]]:
    result: dict[
        int,
        tuple[Mapping[str, Any], dict[int, Mapping[str, Any]], dict[int, set[int]]],
    ] = {}
    previous = -1
    graph_keys = {
        "caller_entry_rva",
        "range_start_rva",
        "range_size",
        "nodes",
        "node_count",
        "edge_count",
    }
    node_keys = {
        "rva",
        "size",
        "sha256",
        "writes_esi",
        "writes_ebx",
        "writes_edi",
        "writes_esp",
        "flow_kind",
        "successor_rvas",
    }
    for index, raw_graph in enumerate(
        _array(evidence.get("control_flow_graphs"), "control_flow_graphs")
    ):
        label = f"control_flow_graphs[{index}]"
        graph = _mapping(raw_graph, label)
        _exact_keys(graph, graph_keys, label)
        entry = _rva(graph.get("caller_entry_rva"), f"{label}.caller_entry_rva")
        start = _rva(graph.get("range_start_rva"), f"{label}.range_start_rva")
        size = graph.get("range_size")
        if (
            entry <= previous
            or entry in result
            or type(size) is not int
            or size <= 0
            or entry not in functions
        ):
            raise NativeLuaClassFactoryChainError("CFG identities are not canonical")
        previous = entry
        ranges = [
            (_rva(item.get("start_rva"), "atlas range start"), item.get("size"))
            for item in _array(functions[entry].get("ranges"), "atlas ranges")
            if isinstance(item, Mapping)
        ]
        if (start, size) not in ranges:
            raise NativeLuaClassFactoryChainError("CFG does not join one exact atlas range")
        nodes: dict[int, Mapping[str, Any]] = {}
        edges: dict[int, set[int]] = {}
        ordered: list[int] = []
        for node_index, raw_node in enumerate(
            _array(graph.get("nodes"), f"{label}.nodes")
        ):
            node_label = f"{label}.nodes[{node_index}]"
            node = _mapping(raw_node, node_label)
            _exact_keys(node, node_keys, node_label)
            rva = _rva(node.get("rva"), f"{node_label}.rva")
            node_size = node.get("size")
            sha = node.get("sha256")
            successors = [
                _rva(item, f"{node_label}.successor")
                for item in _array(
                    node.get("successor_rvas"), f"{node_label}.successors"
                )
            ]
            if (
                rva in nodes
                or type(node_size) is not int
                or not 0 < node_size <= 15
                or type(sha) is not str
                or len(sha) != 64
                or any(character not in "0123456789abcdef" for character in sha)
                or any(
                    type(node.get(field)) is not bool
                    for field in (
                        "writes_esi",
                        "writes_ebx",
                        "writes_edi",
                        "writes_esp",
                    )
                )
                or node.get("flow_kind") not in _FLOW_KINDS
                or successors != sorted(set(successors))
            ):
                raise NativeLuaClassFactoryChainError("CFG node is malformed")
            nodes[rva] = node
            edges[rva] = set(successors)
            ordered.append(rva)
        if (
            not ordered
            or ordered[0] != start
            or ordered != sorted(ordered)
            or any(
                left + nodes[left]["size"] != right
                for left, right in zip(ordered, ordered[1:])
            )
            or ordered[-1] + nodes[ordered[-1]]["size"] != start + size
            or set().union(*edges.values(), set()) - set(nodes)
        ):
            raise NativeLuaClassFactoryChainError(
                "CFG nodes are not one exact contiguous range"
            )
        for rva, node in nodes.items():
            flow = node["flow_kind"]
            expected_count = (
                0
                if flow in {"terminal", "indirect_jump"}
                else 2
                if flow == "direct_conditional_branch"
                else 1
            )
            if len(edges[rva]) != expected_count:
                raise NativeLuaClassFactoryChainError(
                    "CFG successor count differs from flow kind"
                )
            fallthrough = rva + node["size"]
            if (
                flow in {"fallthrough", "call_fallthrough"}
                and edges[rva] != {fallthrough}
            ) or (
                flow == "direct_conditional_branch"
                and fallthrough not in edges[rva]
            ):
                raise NativeLuaClassFactoryChainError(
                    "CFG fallthrough edge differs from instruction layout"
                )
        if graph.get("node_count") != len(nodes) or graph.get("edge_count") != sum(
            map(len, edges.values())
        ):
            raise NativeLuaClassFactoryChainError("CFG aggregate counts differ")
        result[entry] = (graph, nodes, edges)
    return result


def _function_profiles(profile: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return sorted(profile["functions"], key=lambda item: item["entry_rva"])


def _dispatch_records(
    expected_function: Mapping[str, Any],
    graph: Mapping[str, Any],
    image_base: int,
    imports: Mapping[str, Mapping[str, Any]],
    program_facts: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    try:
        return _staged_dispatch_records(
            expected_function,
            graph,
            image_base,
            imports,
            program_facts,
            functions,
        )
    except NativeLuaSuperRebindingError as exc:
        raise NativeLuaClassFactoryChainError(
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
        raise NativeLuaClassFactoryChainError(f"Lua import map failed: {exc}") from exc
    body_records: list[dict[str, Any]] = []
    graphs: list[dict[str, Any]] = []
    decoder.detail = True
    for expected in _function_profiles(profile):
        entry = expected["entry_rva"]
        function = functions.get(entry)
        if function is None or function.get("thunk") is not False:
            raise NativeLuaClassFactoryChainError(
                "reviewed callback is absent or a thunk"
            )
        if (
            function.get("body_size") != expected["body_size"]
            or function.get("body_sha256") != expected["body_sha256"]
        ):
            raise NativeLuaClassFactoryChainError("reviewed callback body changed")
        ranges = _array(function.get("ranges"), "function ranges")
        if len(ranges) != 1:
            raise NativeLuaClassFactoryChainError(
                "reviewed callback no longer has one atlas range"
            )
        raw_range = _mapping(ranges[0], "function range")
        start = _rva(raw_range.get("start_rva"), "range start")
        size = raw_range.get("size")
        if start != entry or type(size) is not int or size != expected["body_size"]:
            raise NativeLuaClassFactoryChainError("reviewed callback range changed")
        instructions = _decode_range(data, image, start, size, decoder)
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
            raise NativeLuaClassFactoryChainError("reviewed callback CFG changed")
        graphs.append(graph)
        by_rva = {
            instruction.address - image.image_base: instruction
            for instruction in instructions
        }
        points: list[dict[str, Any]] = []
        for profile_point in expected["points"]:
            instruction = by_rva.get(profile_point[1])
            if instruction is None:
                raise NativeLuaClassFactoryChainError(
                    "reviewed instruction is absent from callback body"
                )
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
                    raise NativeLuaClassFactoryChainError(
                        f"reviewed {api} call does not join direct-call census"
                    )
            points.append(point)
        staged = _dispatch_records(
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
                "staged_lua_dispatches": staged,
                "staged_register_call_partition_complete": True,
                "semantic_facts": dict(expected["semantic_facts"]),
            }
        )
    return body_records, graphs


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
        item = _mapping(raw, f"ghidra_declared_direct_calls[{index}]")
        rva = _rva(item.get("instruction_rva"), "declared call RVA")
        if rva in result:
            raise NativeLuaClassFactoryChainError("declared call RVAs repeat")
        result[rva] = item
    return result


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
        raise NativeLuaClassFactoryChainError("native edge lacks an exact atlas join")
    if (
        _rva(declared.get("source_entry_rva"), "declared source")
        != expected["source_entry_rva"]
        or _rva(declared.get("target_entry_rva"), "declared target")
        != expected["target_entry_rva"]
        or _rva(declared.get("target_rva"), "declared target RVA")
        != expected["target_entry_rva"]
    ):
        raise NativeLuaClassFactoryChainError("native edge declaration changed")
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
    }


def _native_edges(
    profile: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> list[dict[str, Any]]:
    functions = _atlas_functions(program_facts)
    return [
        _native_edge_record(expected, program_facts, functions)
        for expected in sorted(
            profile["native_edges"], key=lambda item: item["instruction_rva"]
        )
    ]


def _expected_reference(
    raw: Mapping[str, Any],
    image_base: int,
    functions: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    encoded = bytes.fromhex(raw["encoded"])
    owner = functions.get(raw["owner_entry_rva"])
    if owner is None:
        raise NativeLuaClassFactoryChainError(
            "target-reference owner is absent from atlas"
        )
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


def _reference_aggregates(
    references: list[Mapping[str, Any]],
) -> dict[str, Any]:
    classes = [item["use_class"] for item in references]
    return {
        "reference_count": len(references),
        "producer_count": classes.count("closure_producer"),
        "direct_call_count": classes.count("direct_call"),
        "comparison_count": classes.count("comparison"),
        "other_address_count": classes.count("other_address"),
        "memory_operand_count": sum(
            item["operand_class"] == "absolute_memory" for item in references
        ),
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
    targets = sorted(
        {
            profile["publication"]["callback_entry_rva"],
            profile["returned_closure"]["callback_entry_rva"],
        }
    )
    target_vas = {image.image_base + rva: rva for rva in targets}
    producer_sites = {
        (item["instruction_rva"], item["target_rva"])
        for item in profile["target_references"]
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
                raise NativeLuaClassFactoryChainError("atlas range size is invalid")
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
                            "instruction_sha256": hashlib.sha256(
                                bytes(instruction.bytes)
                            ).hexdigest(),
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
    expected = [
        _expected_reference(item, image.image_base, functions)
        for item in profile["target_references"]
    ]
    if references != expected:
        raise NativeLuaClassFactoryChainError(
            "callback target-reference partition changed"
        )
    summary = _mapping(program_facts.get("summary"), "program_facts.summary")
    direct_summary = _mapping(direct_calls.get("summary"), "direct_calls.summary")
    if (
        decoded_ranges != summary.get("body_range_count")
        or decoded_bytes != summary.get("function_body_bytes")
        or decoded_ranges != direct_summary.get("decoded_ranges")
        or decoded_bytes != direct_summary.get("decoded_bytes")
        or decoded_instructions != direct_summary.get("decoded_instructions")
    ):
        raise NativeLuaClassFactoryChainError(
            "target scan did not cover the declared atlas ranges"
        )
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


def _callback_targets(
    body_records: list[Mapping[str, Any]],
    profile: Mapping[str, Any],
    image_base: int,
) -> list[dict[str, Any]]:
    bodies = {_rva(item["entry_rva"], "body entry"): item for item in body_records}
    targets = sorted(
        {
            profile["publication"]["callback_entry_rva"],
            profile["returned_closure"]["callback_entry_rva"],
        }
    )
    result: list[dict[str, Any]] = []
    for entry in targets:
        body = bodies.get(entry)
        if body is None:
            raise NativeLuaClassFactoryChainError("callback target body is absent")
        result.append(
            {
                "entry_rva": body["entry_rva"],
                "entry_va": _hex(image_base + entry),
                "atlas_record_sha256": body["atlas_record_sha256"],
                "body_size": body["body_size"],
                "body_sha256": body["body_sha256"],
            }
        )
    return result


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    bodies = _array(result["function_bodies"], "function_bodies")
    dispatches = [
        dispatch
        for body in bodies
        for dispatch in _array(
            _mapping(body, "function body").get("staged_lua_dispatches"),
            "staged_lua_dispatches",
        )
    ]
    target_aggregates = _mapping(
        _mapping(result["target_reference_scan"], "target scan").get("aggregates"),
        "target aggregates",
    )
    edges = _array(result["native_edges"], "native_edges")
    return {
        "publication_count": 1,
        "returned_closure_count": 1,
        "unique_callback_target_count": len(result["callback_targets"]),
        "reviewed_function_count": len(bodies),
        "reviewed_function_bytes": sum(item["body_size"] for item in bodies),
        "sealed_control_flow_graph_count": len(result["control_flow_graphs"]),
        "sealed_control_flow_graph_node_count": sum(
            item["node_count"] for item in result["control_flow_graphs"]
        ),
        "sealed_control_flow_graph_edge_count": sum(
            item["edge_count"] for item in result["control_flow_graphs"]
        ),
        "literal_count": len(result["literals"]),
        "selected_native_edge_count": len(edges),
        "unique_native_edge_target_count": len(
            {item["target_entry_rva"] for item in edges}
        ),
        "staged_lua_dispatch_count": len(dispatches),
        "staged_lua_call_count": sum(
            len(_array(item.get("call_sites"), "dispatch call sites"))
            for item in dispatches
        ),
        "target_reference_count": target_aggregates["reference_count"],
        "target_reference_producer_count": target_aggregates["producer_count"],
        "target_reference_direct_call_count": target_aggregates["direct_call_count"],
        "target_reference_comparison_count": target_aggregates["comparison_count"],
        "target_reference_other_address_count": target_aggregates["other_address_count"],
        "target_reference_memory_operand_count": target_aggregates["memory_operand_count"],
        "factory_normal_result_count": 1,
        "returned_callback_normal_result_count": 0,
        "schema_violations": 0,
    }


def _expected_prerequisites(
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any],
    table_key_provenance: Mapping[str, Any],
    terminal_dispositions: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "atlas": _atlas_identity(program_facts),
        "direct_call_census": _source_identity(direct_calls, DIRECT_CALL_ANALYSIS_KIND),
        "callback_census": _source_identity(callback_census, CALLBACK_ANALYSIS_KIND),
        "setfield_publication_census": _source_identity(
            setfield_publications, SETFIELD_ANALYSIS_KIND
        ),
        "direct_table_setter_publication_census": _source_identity(
            direct_table_setter_publications, DIRECT_TABLE_SETTER_ANALYSIS_KIND
        ),
        "indirect_settable_publication_census": _source_identity(
            indirect_settable_publications, INDIRECT_SETTABLE_ANALYSIS_KIND
        ),
        "table_key_provenance_census": _source_identity(
            table_key_provenance, TABLE_KEY_ANALYSIS_KIND
        ),
        "terminal_disposition_census": _source_identity(
            terminal_dispositions, TERMINAL_ANALYSIS_KIND
        ),
    }


def build_native_lua_class_factory_chain(
    executable: Path,
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
    """Build the exact build-keyed native Lua class-factory chain."""
    inputs = (
        (direct_calls, "direct_calls"),
        (callback_census, "callback_census"),
        (setfield_publications, "setfield_publications"),
        (direct_table_setter_publications, "direct_table_setter_publications"),
        (indirect_settable_publications, "indirect_settable_publications"),
        (table_key_provenance, "table_key_provenance"),
        (terminal_dispositions, "terminal_dispositions"),
        (program_facts, "program_facts"),
        (inventory, "inventory"),
    )
    for value, label in inputs:
        _validate_json_tree(value, label)
    try:
        table_receipt = validate_native_lua_cclosure_table_key_provenance_census(
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
        terminal_receipt = validate_native_lua_cclosure_terminal_disposition_census(
            executable,
            terminal_dispositions,
            direct_calls,
            callback_census,
            setfield_publications,
            direct_table_setter_publications,
            program_facts,
            inventory=inventory,
        )
        data, image, executable_sha256 = _load_executable(executable)
        decoder, _ = _decoder()
    except (
        NativeLuaCClosureTableKeyProvenanceError,
        NativeLuaCClosureTerminalDispositionError,
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        PEAnchorError,
    ) as exc:
        raise NativeLuaClassFactoryChainError(
            f"class-factory prerequisite failed exact verification: {exc}"
        ) from exc
    profile = _PROFILES.get(executable_sha256)
    if profile is None:
        raise NativeLuaClassFactoryChainError(
            "executable has no reviewed class-factory profile"
        )
    identity = _mapping(program_facts.get("identity"), "program_facts.identity")
    if (
        identity.get("executable_sha256") != executable_sha256
        or identity.get("executable_size") != len(data)
        or identity.get("architecture") != image.architecture
        or table_receipt.get("evidence_sha256")
        != _canonical_sha256(table_key_provenance)
        or terminal_receipt.get("evidence_sha256")
        != _canonical_sha256(terminal_dispositions)
    ):
        raise NativeLuaClassFactoryChainError(
            "executable or prerequisite identity changed"
        )
    publication = _class_publication(table_key_provenance, profile)
    returned = _returned_closure(
        terminal_dispositions,
        publication,
        profile,
    )
    body_records, graphs = _build_function_records(
        data,
        image,
        decoder,
        program_facts,
        direct_calls,
        profile,
    )
    literals = [
        _literal_record(data, image, expected) for expected in profile["literals"]
    ]
    target_scan = _target_reference_scan(
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
        "decoder": {
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
        },
        "publication_chain": {
            "class_publication": publication,
            "returned_closure": returned,
        },
        "callback_targets": _callback_targets(body_records, profile, image.image_base),
        "literals": literals,
        "function_bodies": body_records,
        "control_flow_graphs": graphs,
        "native_edges": _native_edges(profile, program_facts),
        "target_reference_scan": target_scan,
        "method": _METHOD,
    }
    result["summary"] = _summary(result)
    _assert_publication_safe(result)
    return result


def validate_native_lua_class_factory_chain_structure(
    evidence: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any],
    table_key_provenance: Mapping[str, Any],
    terminal_dispositions: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate finite class-factory evidence without loading the executable."""
    for value, label in (
        (evidence, "evidence"),
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
    try:
        table_receipt = validate_native_lua_cclosure_table_key_provenance_structure(
            table_key_provenance,
            direct_calls,
            callback_census,
            setfield_publications,
            direct_table_setter_publications,
            indirect_settable_publications,
            program_facts,
        )
        terminal_receipt = validate_native_lua_cclosure_terminal_disposition_structure(
            terminal_dispositions,
            direct_calls,
            callback_census,
            setfield_publications,
            direct_table_setter_publications,
            program_facts,
        )
    except (
        NativeLuaCClosureTableKeyProvenanceError,
        NativeLuaCClosureTerminalDispositionError,
        NativeLuaCClosurePublicationError,
    ) as exc:
        raise NativeLuaClassFactoryChainError(
            f"class-factory structural prerequisite failed: {exc}"
        ) from exc
    if (
        table_receipt.get("analysis_kind")
        != TABLE_KEY_STRUCTURE_VERIFICATION_KIND
        or table_receipt.get("status") != "structurally_verified"
        or terminal_receipt.get("analysis_kind")
        != TERMINAL_STRUCTURE_VERIFICATION_KIND
        or terminal_receipt.get("status") != "structurally_verified"
    ):
        raise NativeLuaClassFactoryChainError(
            "structural prerequisite verifier returned another result"
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
        "decoder",
        "publication_chain",
        "callback_targets",
        "literals",
        "function_bodies",
        "control_flow_graphs",
        "native_edges",
        "target_reference_scan",
        "method",
        "summary",
    }
    _exact_keys(evidence, top_keys, "evidence")
    if (
        evidence.get("schema_version") != SCHEMA_VERSION
        or evidence.get("analysis_kind") != ANALYSIS_KIND
    ):
        raise NativeLuaClassFactoryChainError(
            "unsupported class-factory schema or analysis kind"
        )
    identity = _mapping(program_facts.get("identity"), "program_facts.identity")
    if evidence.get("build_identity") != dict(identity):
        raise NativeLuaClassFactoryChainError(
            "build identity differs from program facts"
        )
    for document in (
        direct_calls,
        callback_census,
        setfield_publications,
        direct_table_setter_publications,
        indirect_settable_publications,
        table_key_provenance,
        terminal_dispositions,
    ):
        if document.get("build_identity") != evidence.get("build_identity"):
            raise NativeLuaClassFactoryChainError(
                "prerequisite build identities differ"
            )
    profile = _PROFILES.get(identity.get("executable_sha256"))
    if profile is None:
        raise NativeLuaClassFactoryChainError(
            "build identity has no reviewed class-factory profile"
        )
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
    for key, expected in expected_prerequisites.items():
        if evidence.get(key) != expected:
            raise NativeLuaClassFactoryChainError(
                f"{key} prerequisite identity differs"
            )
    expected_decoder = {
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
    }
    if evidence.get("decoder") != expected_decoder or evidence.get("method") != _METHOD:
        raise NativeLuaClassFactoryChainError("decoder or method contract differs")
    publication = _class_publication(table_key_provenance, profile)
    returned = _returned_closure(
        terminal_dispositions,
        publication,
        profile,
    )
    expected_chain = {
        "class_publication": publication,
        "returned_closure": returned,
    }
    if evidence.get("publication_chain") != expected_chain:
        raise NativeLuaClassFactoryChainError("publication chain differs")
    expected_literals = [
        _expected_literal_record(item) for item in profile["literals"]
    ]
    if evidence.get("literals") != expected_literals:
        raise NativeLuaClassFactoryChainError("literal profile differs")
    functions = _atlas_functions(program_facts)
    body_records = _array(evidence.get("function_bodies"), "function_bodies")
    profiles = _function_profiles(profile)
    if len(body_records) != len(profiles):
        raise NativeLuaClassFactoryChainError("reviewed callback partition differs")
    call_map = _direct_call_map(direct_calls)
    normalized_bodies: list[Mapping[str, Any]] = []
    for index, (raw_body, expected) in enumerate(zip(body_records, profiles)):
        label = f"function_bodies[{index}]"
        body = _mapping(raw_body, label)
        normalized_bodies.append(body)
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
            raise NativeLuaClassFactoryChainError(
                "reviewed callback is absent from atlas"
            )
        expected_base = {
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
            "staged_register_call_partition_complete": True,
            "semantic_facts": expected["semantic_facts"],
        }
        for key, value in expected_base.items():
            if body.get(key) != value:
                raise NativeLuaClassFactoryChainError(f"{label}.{key} differs")
        expected_points = [
            _expected_point_record(item) for item in expected["points"]
        ]
        if body.get("reviewed_points") != expected_points:
            raise NativeLuaClassFactoryChainError(
                f"{label} reviewed instruction facts differ"
            )
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
                or joined[1].get("library") != LUA_LIBRARY
                or joined[1].get("call_form") != DIRECT_CALL_FORM
                or joined[1].get("instruction_sha256") != point["sha256"]
            ):
                raise NativeLuaClassFactoryChainError(
                    f"{label} direct-call join differs"
                )
    graph_map = _validated_graphs(
        {"control_flow_graphs": evidence.get("control_flow_graphs")},
        functions,
    )
    if set(graph_map) != {item["entry_rva"] for item in profiles}:
        raise NativeLuaClassFactoryChainError("reviewed CFG partition differs")
    try:
        imports = _lua_import_map(direct_calls)
    except NativeLuaSuperRebindingError as exc:
        raise NativeLuaClassFactoryChainError(f"Lua import map failed: {exc}") from exc
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
            raise NativeLuaClassFactoryChainError("sealed CFG identity differs")
        for point in body["reviewed_points"]:
            rva = _rva(point["rva"], "point RVA")
            node = nodes.get(rva)
            if node is None or (node.get("size"), node.get("sha256")) != (
                point["size"],
                point["sha256"],
            ):
                raise NativeLuaClassFactoryChainError(
                    "reviewed point does not join its CFG node"
                )
        expected_dispatches = _dispatch_records(
            expected,
            graph,
            image_base,
            imports,
            program_facts,
            functions,
        )
        if body.get("staged_lua_dispatches") != expected_dispatches:
            raise NativeLuaClassFactoryChainError(
                "staged Lua dispatch proof differs"
            )
    expected_edges = _native_edges(profile, program_facts)
    if evidence.get("native_edges") != expected_edges:
        raise NativeLuaClassFactoryChainError("selected native edges differ")
    for edge in expected_edges:
        source_rva = _rva(edge["source_entry_rva"], "native edge source")
        instruction = _mapping(edge["instruction"], "native edge instruction")
        instruction_rva = _rva(instruction["rva"], "native edge instruction RVA")
        graph = graph_map.get(source_rva)
        node = None if graph is None else graph[1].get(instruction_rva)
        if node is None or (node.get("size"), node.get("sha256")) != (
            instruction["size"],
            instruction["sha256"],
        ):
            raise NativeLuaClassFactoryChainError(
                "native edge does not join its source CFG"
            )
    expected_targets = _callback_targets(normalized_bodies, profile, image_base)
    if evidence.get("callback_targets") != expected_targets:
        raise NativeLuaClassFactoryChainError("callback target records differ")
    scan = _mapping(evidence.get("target_reference_scan"), "target_reference_scan")
    _exact_keys(
        scan,
        {"target_rvas", "target_vas", "scope", "references", "aggregates"},
        "target_reference_scan",
    )
    expected_references = [
        _expected_reference(item, image_base, functions)
        for item in profile["target_references"]
    ]
    if scan.get("references") != expected_references:
        raise NativeLuaClassFactoryChainError("target-reference records differ")
    targets = sorted(
        {
            profile["publication"]["callback_entry_rva"],
            profile["returned_closure"]["callback_entry_rva"],
        }
    )
    if (
        scan.get("target_rvas") != [_hex(value) for value in targets]
        or scan.get("target_vas")
        != [_hex(image_base + value) for value in targets]
    ):
        raise NativeLuaClassFactoryChainError("target scan identities differ")
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
    if scan.get("scope") != expected_scope:
        raise NativeLuaClassFactoryChainError("target scan scope differs")
    if scan.get("aggregates") != _reference_aggregates(expected_references):
        raise NativeLuaClassFactoryChainError(
            "target-reference aggregates differ"
        )
    expected_summary = _summary(evidence)
    if evidence.get("summary") != expected_summary:
        raise NativeLuaClassFactoryChainError("summary differs")
    _assert_publication_safe(evidence)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": STRUCTURE_VERIFICATION_KIND,
        "status": "structurally_verified",
        "build_identity": dict(identity),
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": dict(expected_summary),
    }


def validate_native_lua_class_factory_chain(
    executable: Path,
    evidence: Mapping[str, Any],
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
    """Rebuild and canonical-byte-compare exact class-factory evidence."""
    _validate_json_tree(evidence, "evidence")
    rebuilt = build_native_lua_class_factory_chain(
        executable,
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
        raise NativeLuaClassFactoryChainError(
            "native Lua class-factory evidence differs from exact rebuild"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": dict(rebuilt["build_identity"]),
        "evidence_sha256": _canonical_sha256(rebuilt),
        "summary": dict(rebuilt["summary"]),
    }


def encode_native_lua_class_factory_chain(value: Mapping[str, Any]) -> str:
    """Return deterministic pretty JSON for evidence or a verification receipt."""
    _validate_json_tree(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
