"""Exact native Lua ``property`` factory and returned-callback chain.

This build-keyed artifact composes one proven global ``property`` publication,
its proven single-result returned closure, and the returned callback's separate
registry-holder producer.  It seals the two callback bodies and the complete
direct target-operand partition over the declared atlas.  Consumer behavior
and source-level property semantics remain outside this narrow artifact.
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
    _callback_targets,
    _direct_call_map,
    _expected_point_record,
    _expected_prerequisites,
    _function_profiles,
    _point,
    _point_record,
    _returned_closure,
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
from src.observatory.native_lua_cclosure_table_key_provenance import (
    STRUCTURE_VERIFICATION_KIND as TABLE_KEY_STRUCTURE_VERIFICATION_KIND,
    NativeLuaCClosureTableKeyProvenanceError,
    _enhanced_cfg,
    validate_native_lua_cclosure_table_key_provenance_census,
    validate_native_lua_cclosure_table_key_provenance_structure,
)
from src.observatory.native_lua_cclosure_terminal_dispositions import (
    STRUCTURE_VERIFICATION_KIND as TERMINAL_STRUCTURE_VERIFICATION_KIND,
    NativeLuaCClosureTerminalDispositionError,
    validate_native_lua_cclosure_terminal_disposition_census,
    validate_native_lua_cclosure_terminal_disposition_structure,
)
from src.observatory.native_lua_direct_calls import (
    CALL_FORM as DIRECT_CALL_FORM,
    SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_property_factory_chain"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
LUA_LIBRARY = "lua5.1.dll"
LUA_GLOBALSINDEX = -10002
LUA_REGISTRYINDEX = -10000
PE_SECTION_WRITABLE = 0x80000000
MAX_LITERAL_BYTES = 256


class NativeLuaPropertyFactoryChainError(RuntimeError):
    """Raised when the exact property-factory chain is stale or malformed."""


_METHOD = {
    "accepted_chain": (
        "Exactly one table-key row for property is joined to one returned "
        "single-result closure row, the returned callback's separate registry-holder "
        "producer, two sealed callback bodies, finite instruction and stack facts, "
        "and a complete direct target-operand partition."
    ),
    "lua51_abi_premises": [
        "LUA_GLOBALSINDEX is -10002",
        "LUA_REGISTRYINDEX is -10000",
        "lua_error does not return normally",
    ],
    "target_scan_boundary": (
        "Every instruction in every file-backed program-facts atlas range is decoded "
        "with operand detail. Only immediate and absolute-memory operands equal to "
        "either exact callback VA are retained."
    ),
    "structural_boundary": (
        "PE-free validation proves prerequisite joins, sealed profile and full-CFG "
        "identities, complete direct-import and dynamic-register-call partitions, "
        "finite producer classes, target references, and aggregates. Instruction and "
        "literal bytes plus exhaustive atlas decoding require exact rebuild validation."
    ),
    "not_claimed": [
        "runtime reachability, execution order, frequency, state continuity, or persistence",
        "a raw or durable global export or absence of settable metamethod effects",
        "successful allocation, calls, closure creation, or error propagation",
        "that callback identity proves factory origin or a particular upvalue schema",
        "argument or upvalue types, callability, registry validity, lifetime, or ownership",
        "getter, setter, descriptor, metatable, class, or source-level property semantics",
        "behavior or placement of the two direct callback-identity consumers",
        "computed, indirect, data, un-atlased, or Lua-side references",
        "source equivalence or a complete runtime call graph",
    ],
}


_SEALED_PROFILE: dict[str, Any] = {
    "executable_sha256": "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9",
    "publication": {
        "constructor_entry_rva": 0x002E6900,
        "callback_call_rva": 0x002E6BC2,
        "callback_entry_rva": 0x002E67B0,
        "setter_call_rva": 0x002E6BD1,
        "closure_effective_upvalue_count": 0,
    },
    "returned_closure": {
        "caller_entry_rva": 0x002E67B0,
        "callback_call_rva": 0x002E67FA,
        "callback_entry_rva": 0x002EAA50,
        "literal_upvalue_count": 2,
        "result_count": 1,
    },
    "alternate_producer": {
        "caller_entry_rva": 0x00057970,
        "callback_call_rva": 0x000579A2,
        "callback_entry_rva": 0x002EAA50,
        "literal_upvalue_count": 2,
        "registry_index": LUA_REGISTRYINDEX,
    },
    "literals": [
        {
            "role": "global_key_property",
            "text": "property",
            "rva": 0x0043BF8C,
            "byte_length_excluding_nul": 8,
            "nul_terminated_bytes_sha256": "e0d753a813d3d803fae7d2aa3f4f35384d2e18d4671c88af256ea5834b595010",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
        {
            "role": "wrong_argument_count_message",
            "text": "make_property() called with wrong number of arguments.",
            "rva": 0x0043BE24,
            "byte_length_excluding_nul": 54,
            "nul_terminated_bytes_sha256": "a5cfaa776573b35f0c3701aaad43a4331e8603e83b07cb38aa0e6e3a0a8b9956",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
        {
            "role": "returned_callback_error_message",
            "text": "luabind: property_tag function can't be called",
            "publish_text": False,
            "rva": 0x0043C5D4,
            "byte_length_excluding_nul": 46,
            "nul_terminated_bytes_sha256": "571afe6269d164266ab1c841d2e07b422b7224f100e9c5a3953b4cdad5e68bc5",
            "section_name": ".rdata",
            "section_rva": 0x003D6000,
            "section_characteristics": 0x40000040,
        },
    ],
    "functions": [
        {
            "role": "published_factory_callback",
            "entry_rva": 0x002E67B0,
            "body_size": 92,
            "body_sha256": "c93226f0c1ca1e6afb2be4498dddb966b3bc052a7fc71bdad123772adee83303",
            "cfg_canonical_sha256": "76d55921e73a9b3bf5d98fba3a0a57d020c91e6855e0fd3f417198f2ed3a690d",
            "points": [
                _point("lua_gettop", 0x002E67B9, "ff150c657d00", "lua_gettop"),
                _point("argument_count_zero_test", 0x002E67C4, "85ff"),
                _point("zero_argument_error_branch", 0x002E67C6, "7405"),
                _point("argument_count_compare_two", 0x002E67C8, "83ff02"),
                _point("at_most_two_success_branch", 0x002E67CB, "7e16"),
                _point("wrong_count_literal_push", 0x002E67CD, "6824be8300"),
                _point("wrong_count_pushstring", 0x002E67D3, "ff1594647d00", "lua_pushstring"),
                _point("wrong_count_lua_error", 0x002E67DA, "ff1598647d00", "lua_error"),
                _point("argument_count_compare_one", 0x002E67E3, "83ff01"),
                _point("two_argument_closure_branch", 0x002E67E6, "750a"),
                _point("one_argument_state_push", 0x002E67E8, "56"),
                _point("one_argument_nil_padding", 0x002E67E9, "ff15b8647d00", "lua_pushnil"),
                _point("returned_upvalue_count_two", 0x002E67F2, "6a02"),
                _point("returned_callback_target_push", 0x002E67F4, "6850aa6e00"),
                _point("returned_closure_state_push", 0x002E67F9, "56"),
                _point("returned_lua_pushcclosure", 0x002E67FA, "ff15a0647d00", "lua_pushcclosure"),
                _point("closure_argument_cleanup", 0x002E6800, "83c40c"),
                _point("normal_result_count_one", 0x002E6803, "b801000000"),
                _point("return", 0x002E680B, "c3"),
            ],
            "semantic_facts": {
                "accepted_argument_counts": [1, 2],
                "error_argument_count_partition": ["zero", "greater_than_two"],
                "one_argument_nil_padding": True,
                "returned_closure_upvalue_count": 2,
                "normal_result_count": 1,
                "lua51_vm_stack_traces": [
                    {
                        "input_argument_count": 1,
                        "before_padding": ["A1"],
                        "before_closure": ["A1", "nil"],
                        "selected_result": ["C"],
                    },
                    {
                        "input_argument_count": 2,
                        "before_closure": ["A1", "A2"],
                        "selected_result": ["C"],
                    },
                ],
            },
        },
        {
            "role": "returned_callback",
            "entry_rva": 0x002EAA50,
            "body_size": 33,
            "body_sha256": "0b8d87b0ad0d6a1535a67f930c0b4fe9960a099bd5ad08b13c3d30cbf41b223f",
            "cfg_canonical_sha256": "2f02c6895ea6ce37037c9d477bcf06da7058ab27feb4ef820985f91e91770b1b",
            "points": [
                _point("error_literal_push", 0x002EAA53, "68d4c58300"),
                _point("pushstring_state_push", 0x002EAA58, "ff7508"),
                _point("lua_pushstring", 0x002EAA5B, "ff1594647d00", "lua_pushstring"),
                _point("error_state_push", 0x002EAA61, "ff7508"),
                _point("lua_error", 0x002EAA64, "ff1598647d00", "lua_error"),
                _point("fallback_cleanup", 0x002EAA6A, "83c40c"),
                _point("fallback_result_count_zero", 0x002EAA6D, "33c0"),
                _point("return", 0x002EAA70, "c3"),
            ],
            "semantic_facts": {
                "normal_abi_outcome": "lua_error_does_not_return",
                "binary_fallback_result_count": 0,
                "fallback_reachability_claimed": False,
            },
        },
    ],
    "target_references": [
        {
            "instruction_rva": 0x0005799C,
            "owner_entry_rva": 0x00057970,
            "target_rva": 0x002EAA50,
            "encoded": "6850aa6e00",
            "operand_index": 0,
            "use_class": "alternate_registry_holder_closure_producer",
        },
        {
            "instruction_rva": 0x002E67F4,
            "owner_entry_rva": 0x002E67B0,
            "target_rva": 0x002EAA50,
            "encoded": "6850aa6e00",
            "operand_index": 0,
            "use_class": "factory_returned_closure_producer",
        },
        {
            "instruction_rva": 0x002E6BBC,
            "owner_entry_rva": 0x002E6900,
            "target_rva": 0x002E67B0,
            "encoded": "68b0676e00",
            "operand_index": 0,
            "use_class": "global_factory_closure_producer",
        },
        {
            "instruction_rva": 0x002EA047,
            "owner_entry_rva": 0x002E9FD0,
            "target_rva": 0x002EAA50,
            "encoded": "3d50aa6e00",
            "operand_index": 1,
            "use_class": "callback_identity_comparison",
        },
        {
            "instruction_rva": 0x002EA172,
            "owner_entry_rva": 0x002EA110,
            "target_rva": 0x002EAA50,
            "encoded": "3d50aa6e00",
            "operand_index": 1,
            "use_class": "callback_identity_comparison",
        },
    ],
}


_PROFILES = {_SEALED_PROFILE["executable_sha256"]: _SEALED_PROFILE}
_REGISTER_CALL_ENCODINGS = tuple(f"ffd{register:x}" for register in range(8))
_REGISTER_CALL_HASHES = {
    hashlib.sha256(bytes.fromhex(encoded)).hexdigest()
    for encoded in _REGISTER_CALL_ENCODINGS
}


def _expected_literal_record(expected: Mapping[str, Any]) -> dict[str, Any]:
    publish_text = expected.get("publish_text", True)
    result = {
        "role": expected["role"],
        "text": expected["text"] if publish_text else None,
        "rva": _hex(expected["rva"]),
        "byte_length_excluding_nul": expected["byte_length_excluding_nul"],
        "nul_terminated_bytes_sha256": expected[
            "nul_terminated_bytes_sha256"
        ],
        "section_name": expected["section_name"],
        "section_rva": _hex(expected["section_rva"]),
        "section_characteristics": _hex(expected["section_characteristics"]),
        "section_writable": False,
    }
    if not publish_text:
        result["text_published"] = False
    return result


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
            raise NativeLuaPropertyFactoryChainError(
                "literal is not bounded file-backed data"
            )
        if first_offset is None:
            first_offset = offset
        if prior_offset is not None and offset != prior_offset + 1:
            raise NativeLuaPropertyFactoryChainError(
                "literal bytes are not contiguous"
            )
        prior_offset = offset
        byte = data[offset]
        raw.append(byte)
        if byte == 0:
            break
        if byte < 0x20 or byte > 0x7E:
            raise NativeLuaPropertyFactoryChainError(
                "literal is not printable ASCII"
            )
    else:
        raise NativeLuaPropertyFactoryChainError(
            "literal exceeds bounded length"
        )
    if len(raw) < 2 or raw[-1] != 0 or first_offset is None or prior_offset is None:
        raise NativeLuaPropertyFactoryChainError(
            "literal lacks a NUL terminator"
        )
    section = image.section_for_offset(first_offset)
    if (
        section is None
        or section.characteristics & PE_SECTION_WRITABLE
        or image.section_for_offset(prior_offset) != section
    ):
        raise NativeLuaPropertyFactoryChainError(
            "literal is not in one non-writable section"
        )
    observed = bytes(raw[:-1]).decode("ascii")
    if observed != expected["text"]:
        raise NativeLuaPropertyFactoryChainError(
            f"{expected['role']} literal text changed"
        )
    record = _expected_literal_record(expected)
    if (
        record["byte_length_excluding_nul"] != len(raw) - 1
        or record["nul_terminated_bytes_sha256"]
        != hashlib.sha256(bytes(raw)).hexdigest()
        or record["section_name"] != section.name
        or record["section_rva"] != _hex(section.virtual_address)
        or record["section_characteristics"] != _hex(section.characteristics)
    ):
        raise NativeLuaPropertyFactoryChainError(
            f"{expected['role']} literal identity changed"
        )
    return record


def _property_publication(
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
        and raw["key"].get("text") == "property"
    ]
    if len(matches) != 1:
        raise NativeLuaPropertyFactoryChainError(
            "property publication is not unique"
        )
    source = matches[0]
    expected = profile["publication"]
    for key, value in {
        "caller_entry_rva": expected["constructor_entry_rva"],
        "callback_call_rva": expected["callback_call_rva"],
        "callback_entry_rva": expected["callback_entry_rva"],
        "setter_call_rva": expected["setter_call_rva"],
    }.items():
        if _rva(source.get(key), key) != value:
            raise NativeLuaPropertyFactoryChainError(
                f"property publication {key} changed"
            )
    key = _mapping(source.get("key"), "property publication key")
    expected_key = _expected_literal_record(profile["literals"][0])
    expected_key.pop("role")
    destination = _mapping(
        source.get("destination"), "property publication destination"
    )
    if (
        source.get("closure_effective_upvalue_count")
        != expected["closure_effective_upvalue_count"]
        or source.get("setter_import_name") != "lua_settable"
        or source.get("table_index") != LUA_GLOBALSINDEX
        or destination.get("class")
        != "lua51_global_environment_pseudo_index"
        or destination.get("lua_table_index") != LUA_GLOBALSINDEX
        or destination.get("stable_export_claimed") is not False
        or key != expected_key
    ):
        raise NativeLuaPropertyFactoryChainError(
            "property publication grammar changed"
        )
    return {
        "source_record_sha256": _canonical_sha256(source),
        "constructor_entry_rva": source["caller_entry_rva"],
        "constructor_atlas_record_sha256": source[
            "caller_atlas_record_sha256"
        ],
        "callback_call_rva": source["callback_call_rva"],
        "callback_entry_rva": source["callback_entry_rva"],
        "callback_atlas_record_sha256": source[
            "callback_atlas_record_sha256"
        ],
        "closure_effective_upvalue_count": source[
            "closure_effective_upvalue_count"
        ],
        "grammar_family": source["grammar_family"],
        "key": dict(key),
        "destination": dict(destination),
        "setter_import_name": source["setter_import_name"],
        "setter_call_rva": source["setter_call_rva"],
        "source_publication_kind": source["source_publication_kind"],
        "vm_stack_trace": dict(
            _mapping(source.get("vm_stack_trace"), "VM stack trace")
        ),
    }


def _alternate_producer(
    terminal_dispositions: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    expected = profile["alternate_producer"]
    matches = [
        _mapping(raw, "terminal disposition")
        for raw in _array(
            terminal_dispositions.get("dispositions"),
            "terminal_dispositions.dispositions",
        )
        if isinstance(raw, Mapping)
        and _rva(raw.get("callback_call_rva"), "alternate callback call")
        == expected["callback_call_rva"]
    ]
    if len(matches) != 1:
        raise NativeLuaPropertyFactoryChainError(
            "alternate returned-callback producer is not unique"
        )
    source = matches[0]
    if (
        _rva(source.get("caller_entry_rva"), "alternate caller")
        != expected["caller_entry_rva"]
        or _rva(source.get("callback_entry_rva"), "alternate target")
        != expected["callback_entry_rva"]
        or source.get("literal_upvalue_count")
        != expected["literal_upvalue_count"]
        or source.get("registry_index") != expected["registry_index"]
        or source.get("disposition_kind") != "registry_reference_holder"
        or source.get("upvalue_argument_kind") != "immediate"
        or source.get("state_register") != "edi"
        or source.get("holder_register") != "ebx"
        or source.get("returned_register") != "ebx"
        or source.get("initial_reference_sentinel") != -2
    ):
        raise NativeLuaPropertyFactoryChainError(
            "alternate returned-callback producer changed"
        )
    return {
        "source_record_sha256": _canonical_sha256(source),
        "caller_entry_rva": source["caller_entry_rva"],
        "caller_atlas_record_sha256": source["caller_atlas_record_sha256"],
        "callback_call_rva": source["callback_call_rva"],
        "callback_call_instruction_sha256": source[
            "callback_call_instruction_sha256"
        ],
        "callback_entry_rva": source["callback_entry_rva"],
        "callback_atlas_record_sha256": source[
            "callback_atlas_record_sha256"
        ],
        "literal_upvalue_count": source["literal_upvalue_count"],
        "disposition_kind": source["disposition_kind"],
        "upvalue_argument_kind": source["upvalue_argument_kind"],
        "registry_index": source["registry_index"],
        "state_register": source["state_register"],
        "holder_register": source["holder_register"],
        "returned_register": source["returned_register"],
        "initial_reference_sentinel": source["initial_reference_sentinel"],
        "factory_origin_claimed": False,
        "reviewed_sequence": [
            dict(_mapping(item, "alternate reviewed sequence"))
            for item in _array(
                source.get("reviewed_sequence"), "alternate reviewed_sequence"
            )
        ],
    }


def _direct_call_rvas_for_entry(
    call_map: Mapping[int, tuple[Mapping[str, Any], Mapping[str, Any]]],
    entry_rva: int,
) -> list[int]:
    entry = _hex(entry_rva)
    return sorted(
        rva for rva, (record, _call) in call_map.items() if record.get("entry_rva") == entry
    )


def _dynamic_register_call_rvas(graph: Mapping[str, Any]) -> list[str]:
    return [
        node["rva"]
        for node in _array(graph.get("nodes"), "CFG nodes")
        if isinstance(node, Mapping)
        and node.get("size") == 2
        and node.get("sha256") in _REGISTER_CALL_HASHES
    ]


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
    body_records: list[dict[str, Any]] = []
    graphs: list[dict[str, Any]] = []
    decoder.detail = True
    for expected in _function_profiles(profile):
        entry = expected["entry_rva"]
        function = functions.get(entry)
        if function is None or function.get("thunk") is not False:
            raise NativeLuaPropertyFactoryChainError(
                "reviewed callback is absent or a thunk"
            )
        if (
            function.get("body_size") != expected["body_size"]
            or function.get("body_sha256") != expected["body_sha256"]
        ):
            raise NativeLuaPropertyFactoryChainError(
                "reviewed callback body changed"
            )
        ranges = _array(function.get("ranges"), "function ranges")
        if len(ranges) != 1:
            raise NativeLuaPropertyFactoryChainError(
                "reviewed callback no longer has one atlas range"
            )
        raw_range = _mapping(ranges[0], "function range")
        start = _rva(raw_range.get("start_rva"), "range start")
        size = raw_range.get("size")
        if start != entry or type(size) is not int or size != expected["body_size"]:
            raise NativeLuaPropertyFactoryChainError(
                "reviewed callback range changed"
            )
        instructions = _decode_range(data, image, start, size, decoder)
        graph = _with_edi_writes(
            _enhanced_cfg(
                instructions,
                image.image_base,
                (start, size),
                capstone,
                x86,
            ),
            instructions,
            x86,
        )
        graph["caller_entry_rva"] = _hex(entry)
        graph_sha256 = _canonical_sha256(graph)
        if graph_sha256 != expected["cfg_canonical_sha256"]:
            raise NativeLuaPropertyFactoryChainError(
                "reviewed callback CFG changed"
            )
        if _dynamic_register_call_rvas(graph):
            raise NativeLuaPropertyFactoryChainError(
                "reviewed callback gained a dynamic register call"
            )
        graphs.append(graph)
        by_rva = {
            instruction.address - image.image_base: instruction
            for instruction in instructions
        }
        points: list[dict[str, Any]] = []
        profiled_direct_calls: list[int] = []
        for profile_point in expected["points"]:
            instruction = by_rva.get(profile_point[1])
            if instruction is None:
                raise NativeLuaPropertyFactoryChainError(
                    "reviewed instruction is absent from callback body"
                )
            point = _point_record(
                instruction,
                image.image_base,
                profile_point,
            )
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
                    raise NativeLuaPropertyFactoryChainError(
                        f"reviewed {api} call does not join direct-call census"
                    )
            points.append(point)
        if sorted(profiled_direct_calls) != _direct_call_rvas_for_entry(
            call_map, entry
        ):
            raise NativeLuaPropertyFactoryChainError(
                "reviewed direct Lua-call partition is incomplete"
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
                "direct_lua_call_partition_complete": True,
                "dynamic_register_call_rvas": [],
                "dynamic_register_call_partition_complete": True,
                "semantic_facts": dict(expected["semantic_facts"]),
            }
        )
    return body_records, graphs


def _expected_reference(
    raw: Mapping[str, Any],
    image_base: int,
    functions: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    encoded = bytes.fromhex(raw["encoded"])
    owner = functions.get(raw["owner_entry_rva"])
    if owner is None:
        raise NativeLuaPropertyFactoryChainError(
            "target-reference owner is absent from atlas"
        )
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


def _reference_aggregates(
    references: list[Mapping[str, Any]],
) -> dict[str, Any]:
    classes = [item["use_class"] for item in references]
    return {
        "reference_count": len(references),
        "producer_count": sum(value.endswith("closure_producer") for value in classes),
        "factory_producer_count": classes.count("global_factory_closure_producer"),
        "factory_returned_producer_count": classes.count(
            "factory_returned_closure_producer"
        ),
        "alternate_producer_count": classes.count(
            "alternate_registry_holder_closure_producer"
        ),
        "direct_call_count": classes.count("direct_call"),
        "comparison_count": classes.count("callback_identity_comparison"),
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
    declared = {
        (
            item["instruction_rva"],
            item["target_rva"],
            item["operand_index"],
        ): item["use_class"]
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
                raise NativeLuaPropertyFactoryChainError(
                    "atlas range size is invalid"
                )
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
                    use_class = declared.get(
                        (instruction_rva, target_rva, operand_index)
                    )
                    if use_class is None:
                        if instruction.id == x86.X86_INS_CALL:
                            use_class = "direct_call"
                        elif instruction.id in {x86.X86_INS_CMP, x86.X86_INS_TEST}:
                            use_class = "callback_identity_comparison"
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
        for item in sorted(
            profile["target_references"],
            key=lambda item: (item["instruction_rva"], item["operand_index"]),
        )
    ]
    if references != expected:
        raise NativeLuaPropertyFactoryChainError(
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
        raise NativeLuaPropertyFactoryChainError(
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


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    bodies = _array(result["function_bodies"], "function_bodies")
    target_aggregates = _mapping(
        _mapping(result["target_reference_scan"], "target scan").get(
            "aggregates"
        ),
        "target aggregates",
    )
    return {
        "publication_count": 1,
        "returned_closure_count": 1,
        "alternate_producer_count": 1,
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
        "direct_lua_call_count": sum(
            sum(
                point["direct_lua_import"] is not None
                for point in item["reviewed_points"]
            )
            for item in bodies
        ),
        "dynamic_register_call_count": sum(
            len(item["dynamic_register_call_rvas"]) for item in bodies
        ),
        "target_reference_count": target_aggregates["reference_count"],
        "target_reference_producer_count": target_aggregates["producer_count"],
        "target_reference_comparison_count": target_aggregates[
            "comparison_count"
        ],
        "target_reference_direct_call_count": target_aggregates[
            "direct_call_count"
        ],
        "target_reference_other_address_count": target_aggregates[
            "other_address_count"
        ],
        "target_reference_memory_operand_count": target_aggregates[
            "memory_operand_count"
        ],
        "factory_normal_result_count": 1,
        "returned_callback_binary_fallback_result_count": 0,
        "schema_violations": 0,
    }


def _build_native_lua_property_factory_chain(
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
    for value, label in (
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
        raise NativeLuaPropertyFactoryChainError(
            f"property-factory prerequisite failed exact verification: {exc}"
        ) from exc
    profile = _PROFILES.get(executable_sha256)
    if profile is None:
        raise NativeLuaPropertyFactoryChainError(
            "executable has no reviewed property-factory profile"
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
        raise NativeLuaPropertyFactoryChainError(
            "executable or prerequisite identity changed"
        )
    publication = _property_publication(table_key_provenance, profile)
    returned = _returned_closure(
        terminal_dispositions,
        publication,
        profile,
    )
    alternate = _alternate_producer(terminal_dispositions, profile)
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
            "dynamic_register_call_encodings": list(_REGISTER_CALL_ENCODINGS),
            "cfg_register_write_fields": [
                "writes_ebx",
                "writes_esi",
                "writes_edi",
                "writes_esp",
            ],
        },
        "publication_chain": {
            "property_publication": publication,
            "factory_returned_closure": returned,
            "alternate_registry_holder_producer": alternate,
        },
        "callback_targets": _callback_targets(
            body_records, profile, image.image_base
        ),
        "literals": literals,
        "function_bodies": body_records,
        "control_flow_graphs": graphs,
        "target_reference_scan": target_scan,
        "method": _METHOD,
    }
    result["summary"] = _summary(result)
    _assert_publication_safe(result)
    return result


_FOREIGN_ERRORS = (
    NativeLuaClassFactoryChainError,
    NativeLuaCClosureTableKeyProvenanceError,
    NativeLuaCClosureTerminalDispositionError,
    NativeLuaCClosurePublicationError,
    NativeLuaDirectCallError,
    PEAnchorError,
)


def build_native_lua_property_factory_chain(
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
    """Build the exact build-keyed native Lua property-factory chain."""
    try:
        return _build_native_lua_property_factory_chain(
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
    except NativeLuaPropertyFactoryChainError:
        raise
    except _FOREIGN_ERRORS as exc:
        raise NativeLuaPropertyFactoryChainError(
            f"property-factory exact reconstruction failed: {exc}"
        ) from exc


def _validate_native_lua_property_factory_chain_structure(
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
        raise NativeLuaPropertyFactoryChainError(
            f"property-factory structural prerequisite failed: {exc}"
        ) from exc
    if (
        table_receipt.get("analysis_kind")
        != TABLE_KEY_STRUCTURE_VERIFICATION_KIND
        or table_receipt.get("status") != "structurally_verified"
        or terminal_receipt.get("analysis_kind")
        != TERMINAL_STRUCTURE_VERIFICATION_KIND
        or terminal_receipt.get("status") != "structurally_verified"
    ):
        raise NativeLuaPropertyFactoryChainError(
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
        "target_reference_scan",
        "method",
        "summary",
    }
    _exact_keys(evidence, top_keys, "evidence")
    if (
        evidence.get("schema_version") != SCHEMA_VERSION
        or evidence.get("analysis_kind") != ANALYSIS_KIND
    ):
        raise NativeLuaPropertyFactoryChainError(
            "unsupported property-factory schema or analysis kind"
        )
    identity = _mapping(program_facts.get("identity"), "program_facts.identity")
    if evidence.get("build_identity") != dict(identity):
        raise NativeLuaPropertyFactoryChainError(
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
            raise NativeLuaPropertyFactoryChainError(
                "prerequisite build identities differ"
            )
    profile = _PROFILES.get(identity.get("executable_sha256"))
    if profile is None:
        raise NativeLuaPropertyFactoryChainError(
            "build identity has no reviewed property-factory profile"
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
            raise NativeLuaPropertyFactoryChainError(
                f"{key} prerequisite identity differs"
            )
    expected_decoder = {
        "name": "capstone",
        "version": SUPPORTED_CAPSTONE_VERSION,
        "architecture": "x86",
        "mode_bits": 32,
        "operand_classes": ["absolute_memory", "immediate"],
        "dynamic_register_call_encodings": list(_REGISTER_CALL_ENCODINGS),
        "cfg_register_write_fields": [
            "writes_ebx",
            "writes_esi",
            "writes_edi",
            "writes_esp",
        ],
    }
    if evidence.get("decoder") != expected_decoder or evidence.get("method") != _METHOD:
        raise NativeLuaPropertyFactoryChainError(
            "decoder or method contract differs"
        )
    publication = _property_publication(table_key_provenance, profile)
    returned = _returned_closure(
        terminal_dispositions,
        publication,
        profile,
    )
    alternate = _alternate_producer(terminal_dispositions, profile)
    expected_chain = {
        "property_publication": publication,
        "factory_returned_closure": returned,
        "alternate_registry_holder_producer": alternate,
    }
    if evidence.get("publication_chain") != expected_chain:
        raise NativeLuaPropertyFactoryChainError("publication chain differs")
    expected_literals = [
        _expected_literal_record(item) for item in profile["literals"]
    ]
    if evidence.get("literals") != expected_literals:
        raise NativeLuaPropertyFactoryChainError("literal profile differs")
    functions = _atlas_functions(program_facts)
    call_map = _direct_call_map(direct_calls)
    body_records = _array(evidence.get("function_bodies"), "function_bodies")
    profiles = _function_profiles(profile)
    if len(body_records) != len(profiles):
        raise NativeLuaPropertyFactoryChainError(
            "reviewed callback partition differs"
        )
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
                "dynamic_register_call_rvas",
                "dynamic_register_call_partition_complete",
                "semantic_facts",
            },
            label,
        )
        function = functions.get(expected["entry_rva"])
        if function is None:
            raise NativeLuaPropertyFactoryChainError(
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
            "direct_lua_call_partition_complete": True,
            "dynamic_register_call_rvas": [],
            "dynamic_register_call_partition_complete": True,
            "semantic_facts": expected["semantic_facts"],
        }
        for key, value in expected_base.items():
            if body.get(key) != value:
                raise NativeLuaPropertyFactoryChainError(f"{label}.{key} differs")
        expected_points = [
            _expected_point_record(item) for item in expected["points"]
        ]
        if body.get("reviewed_points") != expected_points:
            raise NativeLuaPropertyFactoryChainError(
                f"{label} reviewed instruction facts differ"
            )
        profiled_direct_calls: list[int] = []
        for point in expected_points:
            api = point["direct_lua_import"]
            if api is None:
                continue
            rva = _rva(point["rva"], "point RVA")
            profiled_direct_calls.append(rva)
            joined = call_map.get(rva)
            if (
                joined is None
                or joined[0].get("entry_rva") != body["entry_rva"]
                or joined[1].get("import_name") != api
                or joined[1].get("library") != LUA_LIBRARY
                or joined[1].get("call_form") != DIRECT_CALL_FORM
                or joined[1].get("instruction_sha256") != point["sha256"]
            ):
                raise NativeLuaPropertyFactoryChainError(
                    f"{label} direct-call join differs"
                )
        if sorted(profiled_direct_calls) != _direct_call_rvas_for_entry(
            call_map, expected["entry_rva"]
        ):
            raise NativeLuaPropertyFactoryChainError(
                f"{label} direct-call partition differs"
            )
    graph_map = _validated_graphs(
        {"control_flow_graphs": evidence.get("control_flow_graphs")},
        functions,
    )
    if set(graph_map) != {item["entry_rva"] for item in profiles}:
        raise NativeLuaPropertyFactoryChainError(
            "reviewed CFG partition differs"
        )
    for body, expected in zip(normalized_bodies, profiles):
        graph, nodes, _edges = graph_map[expected["entry_rva"]]
        graph_sha256 = _canonical_sha256(graph)
        if (
            graph_sha256 != expected["cfg_canonical_sha256"]
            or body.get("control_flow_graph_canonical_sha256") != graph_sha256
        ):
            raise NativeLuaPropertyFactoryChainError("sealed CFG identity differs")
        if _dynamic_register_call_rvas(graph):
            raise NativeLuaPropertyFactoryChainError(
                "dynamic register-call partition differs"
            )
        for point in body["reviewed_points"]:
            rva = _rva(point["rva"], "point RVA")
            node = nodes.get(rva)
            if node is None or (node.get("size"), node.get("sha256")) != (
                point["size"],
                point["sha256"],
            ):
                raise NativeLuaPropertyFactoryChainError(
                    "reviewed point does not join its CFG node"
                )
    image_base = _rva(
        _mapping(program_facts.get("ghidra"), "program_facts.ghidra").get(
            "image_base"
        ),
        "image base",
    )
    expected_targets = _callback_targets(
        normalized_bodies, profile, image_base
    )
    if evidence.get("callback_targets") != expected_targets:
        raise NativeLuaPropertyFactoryChainError(
            "callback target records differ"
        )
    scan = _mapping(
        evidence.get("target_reference_scan"), "target_reference_scan"
    )
    _exact_keys(
        scan,
        {"target_rvas", "target_vas", "scope", "references", "aggregates"},
        "target_reference_scan",
    )
    expected_references = [
        _expected_reference(item, image_base, functions)
        for item in sorted(
            profile["target_references"],
            key=lambda item: (item["instruction_rva"], item["operand_index"]),
        )
    ]
    if scan.get("references") != expected_references:
        raise NativeLuaPropertyFactoryChainError(
            "target-reference records differ"
        )
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
        raise NativeLuaPropertyFactoryChainError(
            "target scan identities differ"
        )
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
        raise NativeLuaPropertyFactoryChainError("target scan scope differs")
    if scan.get("aggregates") != _reference_aggregates(expected_references):
        raise NativeLuaPropertyFactoryChainError(
            "target-reference aggregates differ"
        )
    expected_summary = _summary(evidence)
    if evidence.get("summary") != expected_summary:
        raise NativeLuaPropertyFactoryChainError("summary differs")
    _assert_publication_safe(evidence)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": STRUCTURE_VERIFICATION_KIND,
        "status": "structurally_verified",
        "build_identity": dict(identity),
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": dict(expected_summary),
    }


def validate_native_lua_property_factory_chain_structure(
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
    """Validate finite property-factory evidence without loading the executable."""
    try:
        return _validate_native_lua_property_factory_chain_structure(
            evidence,
            direct_calls,
            callback_census,
            setfield_publications,
            direct_table_setter_publications,
            indirect_settable_publications,
            table_key_provenance,
            terminal_dispositions,
            program_facts,
        )
    except NativeLuaPropertyFactoryChainError:
        raise
    except _FOREIGN_ERRORS as exc:
        raise NativeLuaPropertyFactoryChainError(
            f"property-factory structural validation failed: {exc}"
        ) from exc


def validate_native_lua_property_factory_chain(
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
    """Rebuild and canonical-byte-compare exact property-factory evidence."""
    _validate_json_tree(evidence, "evidence")
    rebuilt = build_native_lua_property_factory_chain(
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
        raise NativeLuaPropertyFactoryChainError(
            "native Lua property-factory evidence differs from exact rebuild"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": dict(rebuilt["build_identity"]),
        "evidence_sha256": _canonical_sha256(rebuilt),
        "summary": dict(rebuilt["summary"]),
    }


def encode_native_lua_property_factory_chain(value: Mapping[str, Any]) -> str:
    """Return deterministic pretty JSON for evidence or a verification receipt."""
    _validate_json_tree(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
