"""Exact residual table grammar for the native Lua ``property`` initializer.

This compact artifact depends on the sealed property-consumer chain.  It
promotes only the initializer's marker field, zero-upvalue ``__gc`` closure,
and ordered thirteen-entry two-upvalue wrapper loop.
"""

from __future__ import annotations

import copy
import hashlib
import json
import struct
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
    _hex,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_direct_calls import (
    NativeLuaDirectCallError,
    _load_executable,
)
from src.observatory.native_lua_property_consumer_chain import (
    ANALYSIS_KIND as CONSUMER_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as CONSUMER_STRUCTURE_VERIFICATION_KIND,
    VERIFICATION_KIND as CONSUMER_VERIFICATION_KIND,
    NativeLuaPropertyConsumerChainError,
    validate_native_lua_property_consumer_chain,
    validate_native_lua_property_consumer_chain_structure,
)
from src.observatory.native_lua_property_factory_chain import (
    PE_SECTION_WRITABLE,
    NativeLuaPropertyFactoryChainError,
    _expected_literal_record,
    _literal_record,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_property_initializer_chain"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"


class NativeLuaPropertyInitializerChainError(RuntimeError):
    """Raised when the residual property initializer chain is stale."""


_OPERATOR_ROWS = [
    ("__add", 0x00420730, False),
    ("__sub", 0x00420738, False),
    ("__mul", 0x00420748, False),
    ("__div", 0x0043C404, False),
    ("__pow", 0x0043C41C, False),
    ("__lt", 0x0043C424, False),
    ("__le", 0x0043C40C, False),
    ("__eq", 0x00420740, False),
    ("__call", 0x0043C414, False),
    ("__unm", 0x0043C440, True),
    ("__tostring", 0x0043C448, False),
    ("__concat", 0x0043C42C, False),
    ("__len", 0x0043C438, True),
]


def _literal(
    role: str, text: str, rva: int, digest: str
) -> dict[str, Any]:
    return {
        "role": role,
        "text": text,
        "rva": rva,
        "byte_length_excluding_nul": len(text),
        "nul_terminated_bytes_sha256": digest,
        "section_name": ".rdata",
        "section_rva": 0x003D6000,
        "section_characteristics": 0x40000040,
    }


_PROFILE: dict[str, Any] = {
    "executable_sha256": "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9",
    "consumer_canonical_sha256": "2c6569177595cbdc8abdbe4ba1bdc3d09f4bb0d15dac5d280c16ba3dfcc2d3b9",
    "source_body": {
        "role": "consumer_initializer",
        "entry_rva": 0x002EA2D0,
        "body_sha256": "87e765ce2290b8320efb30cb7e110e8ae67783793b968aecd01827f6bd00d9c1",
        "cfg_sha256": "3901fcde5bfae4be68f67fa1af3cd5e2831443d3af26d16f85c90576d781a843",
    },
    "literals": [
        _literal("marker_key", "__luabind_class", 0x0043C524, "7820ddb1dbf79226b867dd156f8b7cb7f8faa8c6700fa20c66e3f4c1dbd47e20"),
        _literal("cleanup_key", "__gc", 0x0043BF84, "6b3cc554d45a56ed43995cc307f4481a80680a993cd06b4ecfef70986c17997e"),
        _literal("wrapper_key_00", "__add", 0x00420730, "7770dea3424b13123f622499bd66fbf8db67d9d8578f0fa935f191dae20500d2"),
        _literal("wrapper_key_01", "__sub", 0x00420738, "1d2b99e1f0f2da0e7f94ded3b7d87321064aad5c0ce381ec06756d71f47c235b"),
        _literal("wrapper_key_02", "__mul", 0x00420748, "14377c3bce6808214bfd059809eaaa89d9170a83d4ca4477515437e317e99a7d"),
        _literal("wrapper_key_03", "__div", 0x0043C404, "1712782c00d0cda343d0f61e69be1ac240d244aa28d2c28d323e0720b66daa43"),
        _literal("wrapper_key_04", "__pow", 0x0043C41C, "d55e294cbd1fd0703fad73fe68bb960a15ac960c8a57cf6af5e5490253ea050f"),
        _literal("wrapper_key_05", "__lt", 0x0043C424, "6407309dcfb9ff4d9054e4ad4eb6395437ab19db7711825b4d82af739f6eefcd"),
        _literal("wrapper_key_06", "__le", 0x0043C40C, "fad4197df7be10c06dab2c5aa63eef5d2edf753540288cb111184fd977bd30f3"),
        _literal("wrapper_key_07", "__eq", 0x00420740, "111e3403e88d4dd95cee6384bced7cef421f3f1b10587ee58e2a6598575f8bab"),
        _literal("wrapper_key_08", "__call", 0x0043C414, "1cea8272f322970cd93777f034854f50b36d885299be13748cd250df0394cec1"),
        _literal("wrapper_key_09", "__unm", 0x0043C440, "14249c4da69aef228ccbb60ee3bc68c235cde97dbf36283e686107b5d1998d48"),
        _literal("wrapper_key_10", "__tostring", 0x0043C448, "07935749fbd362d25b93c3b694bc26d22587897bb6de1e2f09e4247488152454"),
        _literal("wrapper_key_11", "__concat", 0x0043C42C, "f7e780c81fcdb1357cb1c2679213bae3077485d556f2cfbce3ea4c8598e00c15"),
        _literal("wrapper_key_12", "__len", 0x0043C438, "bbe6627c87567654b62416113010c4e0cdeb8f6816f656fed62e224b4f33fb4c"),
    ],
    "pointer_array": {
        "rva": 0x0043C53C,
        "size": 52,
        "sha256": "95c565ed90ed86b684d214cb95b79de28ecb376e05f58852f091dec49bd6766c",
        "section_name": ".rdata",
        "section_rva": 0x003D6000,
        "section_characteristics": 0x40000040,
    },
    "points": [
        ("create_table", 0x002EA2DA, "lua_createtable"),
        ("push_marker_true", 0x002EA2E3, "lua_pushboolean"),
        ("marker_key_pointer", 0x002EA2EF, None),
        ("marker_table_index_minus_two", 0x002EA2F4, None),
        ("set_marker_field", 0x002EA2F7, "lua_setfield"),
        ("cleanup_upvalue_count_zero", 0x002EA329, None),
        ("cleanup_callback_target", 0x002EA32B, None),
        ("create_cleanup_closure", 0x002EA331, "lua_pushcclosure"),
        ("cleanup_key_pointer", 0x002EA333, None),
        ("cleanup_table_index_minus_two", 0x002EA338, None),
        ("set_cleanup_field", 0x002EA33B, "lua_setfield"),
        ("loop_index_zero", 0x002EA36B, None),
        ("indexed_key_pointer_load", 0x002EA370, None),
        ("push_wrapper_key", 0x002EA378, "lua_pushstring"),
        ("copy_wrapper_key_index_minus_one", 0x002EA37E, None),
        ("copy_wrapper_key", 0x002EA381, "lua_pushvalue"),
        ("compare_index_nine", 0x002EA38A, None),
        ("index_nine_true_branch", 0x002EA38D, None),
        ("compare_index_twelve", 0x002EA38F, None),
        ("index_twelve_true_branch", 0x002EA392, None),
        ("false_value_zero", 0x002EA394, None),
        ("false_to_join", 0x002EA396, None),
        ("true_value_one", 0x002EA398, None),
        ("push_wrapper_boolean", 0x002EA39F, "lua_pushboolean"),
        ("wrapper_upvalue_count_two", 0x002EA3A5, None),
        ("wrapper_callback_target", 0x002EA3A7, None),
        ("create_wrapper_closure", 0x002EA3AD, "lua_pushcclosure"),
        ("wrapper_table_index_minus_three", 0x002EA3AF, None),
        ("set_wrapper_entry", 0x002EA3B2, "lua_settable"),
        ("increment_loop_index", 0x002EA3B8, None),
        ("compare_loop_bound_thirteen", 0x002EA3BC, None),
        ("loop_back_branch", 0x002EA3BF, None),
        ("return", 0x002EA3C4, None),
    ],
}


_METHOD = {
    "accepted_chain": (
        "One verified property-consumer initializer body is reduced to a marker "
        "field, one zero-upvalue cleanup-key closure placement, and an ordered "
        "thirteen-entry two-upvalue wrapper loop."
    ),
    "structural_boundary": (
        "PE-free validation recursively verifies the consumer artifact and rejoins "
        "every declared point to its sealed CFG and Lua-call partitions. Exact "
        "validation additionally rereads all literals and the pointer array."
    ),
    "not_claimed": [
        "runtime reachability, execution order across calls, frequency, or persistence",
        "that the created table is installed as a metatable or class descriptor",
        "runtime cleanup dispatch, finalization, destruction, freeing, ownership, or lifetime",
        "wrapper callback behavior, lookup success, returned-value callability, or invocation",
        "source-level class, property, operator, or metamethod equivalence",
        "successful allocation, closure creation, field writes, table writes, or calls",
        "computed, indirect, data, un-atlased, or Lua-side consumers",
    ],
}


def _consumer_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "analysis_kind": CONSUMER_ANALYSIS_KIND,
        "canonical_sha256": _canonical_sha256(value),
    }


def _initializer_sources(
    consumer: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    expected = _PROFILE["source_body"]
    bodies = [
        _mapping(raw, "consumer function body")
        for raw in _array(consumer.get("function_bodies"), "consumer function_bodies")
        if isinstance(raw, Mapping)
        and _rva(raw.get("entry_rva"), "consumer body entry") == expected["entry_rva"]
    ]
    graphs = [
        _mapping(raw, "consumer CFG")
        for raw in _array(consumer.get("control_flow_graphs"), "consumer CFGs")
        if isinstance(raw, Mapping)
        and _rva(raw.get("caller_entry_rva"), "consumer CFG entry") == expected["entry_rva"]
    ]
    if len(bodies) != 1 or len(graphs) != 1:
        raise NativeLuaPropertyInitializerChainError(
            "initializer body or CFG is not unique"
        )
    body, graph = bodies[0], graphs[0]
    if (
        body.get("role") != expected["role"]
        or body.get("body_sha256") != expected["body_sha256"]
        or body.get("control_flow_graph_canonical_sha256") != expected["cfg_sha256"]
        or _canonical_sha256(graph) != expected["cfg_sha256"]
    ):
        raise NativeLuaPropertyInitializerChainError(
            "sealed initializer identity changed"
        )
    return body, graph


def _lua_call_index(body: Mapping[str, Any]) -> dict[int, tuple[str, str]]:
    result: dict[int, tuple[str, str]] = {}
    for raw in _array(body.get("reviewed_points"), "reviewed points"):
        point = _mapping(raw, "reviewed point")
        api = point.get("direct_lua_import")
        if api is not None:
            result[_rva(point.get("rva"), "direct call RVA")] = (
                api,
                "direct_import",
            )
    for raw in _array(body.get("staged_lua_dispatches"), "staged dispatches"):
        dispatch = _mapping(raw, "staged dispatch")
        api = dispatch.get("api_name")
        for raw_site in _array(dispatch.get("call_sites"), "staged call sites"):
            site = _mapping(raw_site, "staged call site")
            call = _mapping(site.get("call"), "staged call")
            rva = _rva(call.get("rva"), "staged call RVA")
            if rva in result:
                raise NativeLuaPropertyInitializerChainError(
                    "initializer Lua call RVAs overlap"
                )
            result[rva] = (api, "staged_register")
    return result


def _point_records(
    body: Mapping[str, Any], graph: Mapping[str, Any]
) -> list[dict[str, Any]]:
    nodes = {
        _rva(_mapping(raw, "CFG node").get("rva"), "CFG node RVA"): _mapping(
            raw, "CFG node"
        )
        for raw in _array(graph.get("nodes"), "CFG nodes")
    }
    calls = _lua_call_index(body)
    result: list[dict[str, Any]] = []
    seen: set[int] = set()
    for role, rva, expected_api in _PROFILE["points"]:
        node = nodes.get(rva)
        if node is None or rva in seen:
            raise NativeLuaPropertyInitializerChainError(
                "declared initializer point is absent or repeated"
            )
        seen.add(rva)
        observed = calls.get(rva)
        if expected_api is None:
            if observed is not None:
                raise NativeLuaPropertyInitializerChainError(
                    "non-call initializer point became a Lua call"
                )
            api = dispatch = None
        else:
            if observed is None or observed[0] != expected_api:
                raise NativeLuaPropertyInitializerChainError(
                    "initializer Lua API identity changed"
                )
            api, dispatch = observed
        result.append(
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
    return result


def _expected_pointer_array_record() -> dict[str, Any]:
    expected = _PROFILE["pointer_array"]
    entries = []
    for index, (key, rva, flag) in enumerate(_OPERATOR_ROWS):
        entries.append(
            {
                "index": index,
                "key": key,
                "literal_rva": _hex(rva),
                "pointer_va": _hex(0x00400000 + rva),
                "boolean_upvalue": flag,
            }
        )
    return {
        "rva": _hex(expected["rva"]),
        "size": expected["size"],
        "sha256": expected["sha256"],
        "section_name": expected["section_name"],
        "section_rva": _hex(expected["section_rva"]),
        "section_characteristics": _hex(expected["section_characteristics"]),
        "section_writable": False,
        "entries": entries,
    }


def _pointer_array_record(data: bytes, image: Any) -> dict[str, Any]:
    expected = _PROFILE["pointer_array"]
    offset = image.rva_span_to_file_offset(expected["rva"], expected["size"])
    if offset is None:
        raise NativeLuaPropertyInitializerChainError(
            "wrapper pointer array is not contiguous file-backed data"
        )
    raw = data[offset : offset + expected["size"]]
    section = image.section_for_offset(offset)
    if (
        len(raw) != expected["size"]
        or section is None
        or section.characteristics & PE_SECTION_WRITABLE
        or image.section_for_offset(offset + expected["size"] - 1) != section
    ):
        raise NativeLuaPropertyInitializerChainError(
            "wrapper pointer array section changed"
        )
    pointers = list(struct.unpack("<13I", raw))
    expected_pointers = [image.image_base + row[1] for row in _OPERATOR_ROWS]
    result = _expected_pointer_array_record()
    if (
        image.image_base != 0x00400000
        or pointers != expected_pointers
        or hashlib.sha256(raw).hexdigest() != result["sha256"]
        or section.name != result["section_name"]
        or _hex(section.virtual_address) != result["section_rva"]
        or _hex(section.characteristics) != result["section_characteristics"]
    ):
        raise NativeLuaPropertyInitializerChainError(
            "wrapper pointer array identity changed"
        )
    return result


def _semantics() -> dict[str, Any]:
    rows = [
        {
            "index": index,
            "key": key,
            "literal_rva": _hex(rva),
            "boolean_upvalue": flag,
        }
        for index, (key, rva, flag) in enumerate(_OPERATOR_ROWS)
    ]
    return {
        "table_symbol": "T",
        "marker_placement": {
            "key": "__luabind_class",
            "value": True,
            "setter": "lua_setfield",
            "table_index": -2,
            "stack_before_value": ["S", "T"],
            "stack_after_setter": ["S", "T"],
        },
        "cleanup_placement": {
            "key": "__gc",
            "callback_entry_rva": "0x002e9f40",
            "closure_upvalue_count": 0,
            "setter": "lua_setfield",
            "table_index": -2,
            "callback_behavior_normalized": False,
        },
        "wrapper_loop": {
            "initial_index": 0,
            "exclusive_upper_bound": 13,
            "iteration_count": 13,
            "ordered_rows": rows,
            "true_boolean_indices": [9, 12],
            "false_boolean_indices": [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11],
            "callback_entry_rva": "0x002ea1a0",
            "closure_upvalue_count": 2,
            "upvalue_order": ["K", "B"],
            "setter": "lua_settable",
            "table_index": -3,
            "per_iteration_stack_trace": [
                ["S", "T"],
                ["S", "T", "K"],
                ["S", "T", "K", "K"],
                ["S", "T", "K", "K", "B"],
                ["S", "T", "K", "C"],
                ["S", "T"],
            ],
            "wrapper_callback_behavior_normalized": False,
        },
    }


def _summary(value: Mapping[str, Any]) -> dict[str, Any]:
    points = _array(value["path_points"], "path points")
    rows = value["semantics"]["wrapper_loop"]["ordered_rows"]
    return {
        "consumer_prerequisite_count": 1,
        "source_body_count": 1,
        "source_cfg_node_count": value["source_body"]["control_flow_graph_node_count"],
        "source_cfg_edge_count": value["source_body"]["control_flow_graph_edge_count"],
        "literal_count": len(value["literals"]),
        "pointer_array_entry_count": len(value["pointer_array"]["entries"]),
        "declared_path_point_count": len(points),
        "direct_lua_path_point_count": sum(
            point["lua_dispatch_kind"] == "direct_import" for point in points
        ),
        "staged_lua_path_point_count": sum(
            point["lua_dispatch_kind"] == "staged_register" for point in points
        ),
        "marker_placement_count": 1,
        "cleanup_closure_placement_count": 1,
        "wrapper_closure_placement_count": len(rows),
        "wrapper_true_boolean_count": sum(row["boolean_upvalue"] for row in rows),
        "wrapper_false_boolean_count": sum(not row["boolean_upvalue"] for row in rows),
        "schema_violations": 0,
    }


def _derive(
    consumer: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    literals: list[dict[str, Any]],
    pointer_array: dict[str, Any],
) -> dict[str, Any]:
    _validate_json_tree(consumer, "consumer")
    _validate_json_tree(program_facts, "program facts")
    if (
        consumer.get("analysis_kind") != CONSUMER_ANALYSIS_KIND
        or _canonical_sha256(consumer) != _PROFILE["consumer_canonical_sha256"]
    ):
        raise NativeLuaPropertyInitializerChainError(
            "consumer prerequisite identity changed"
        )
    identity = _mapping(program_facts.get("identity"), "program facts identity")
    if (
        identity.get("executable_sha256") != _PROFILE["executable_sha256"]
        or consumer.get("build_identity") != dict(identity)
    ):
        raise NativeLuaPropertyInitializerChainError(
            "consumer and atlas build identities differ"
        )
    body, graph = _initializer_sources(consumer)
    source_body = {
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
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(identity),
        "consumer_chain": _consumer_identity(consumer),
        "source_body": source_body,
        "literals": copy.deepcopy(literals),
        "pointer_array": copy.deepcopy(pointer_array),
        "path_points": _point_records(body, graph),
        "semantics": _semantics(),
        "method": copy.deepcopy(_METHOD),
    }
    result["summary"] = _summary(result)
    _assert_publication_safe(result)
    return result


def build_native_lua_property_initializer_chain(
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
    """Build exact residual initializer evidence."""
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
            raise NativeLuaPropertyInitializerChainError(
                "consumer exact verifier returned another result"
            )
        data, image, executable_sha256 = _load_executable(executable)
        if executable_sha256 != _PROFILE["executable_sha256"]:
            raise NativeLuaPropertyInitializerChainError(
                "initializer executable identity changed"
            )
        literals = [_literal_record(data, image, item) for item in _PROFILE["literals"]]
        pointer_array = _pointer_array_record(data, image)
        return _derive(consumer, program_facts, literals, pointer_array)
    except NativeLuaPropertyInitializerChainError:
        raise
    except (
        NativeLuaPropertyConsumerChainError,
        NativeLuaPropertyFactoryChainError,
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        PEAnchorError,
    ) as exc:
        raise NativeLuaPropertyInitializerChainError(
            f"property initializer prerequisite failed exact verification: {exc}"
        ) from exc


def validate_native_lua_property_initializer_chain_structure(
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
    """Replay initializer derivation without reopening the executable."""
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
    except (
        NativeLuaPropertyConsumerChainError,
        NativeLuaCClosurePublicationError,
    ) as exc:
        raise NativeLuaPropertyInitializerChainError(
            f"property initializer structural prerequisite failed: {exc}"
        ) from exc
    if (
        receipt.get("schema_version") != SCHEMA_VERSION
        or receipt.get("analysis_kind") != CONSUMER_STRUCTURE_VERIFICATION_KIND
        or receipt.get("status") != "structurally_verified"
        or receipt.get("evidence_sha256")
        != _PROFILE["consumer_canonical_sha256"]
        or receipt.get("build_identity") != consumer.get("build_identity")
    ):
        raise NativeLuaPropertyInitializerChainError(
            "consumer structural verifier returned another result"
        )
    try:
        literals = [_expected_literal_record(item) for item in _PROFILE["literals"]]
        expected = _derive(
            consumer,
            program_facts,
            literals,
            _expected_pointer_array_record(),
        )
        evidence = _mapping(evidence, "evidence")
        _exact_keys(evidence, set(expected), "evidence")
        if _canonical_bytes(evidence) != _canonical_bytes(expected):
            raise NativeLuaPropertyInitializerChainError(
                "property initializer evidence differs from structural replay"
            )
    except NativeLuaPropertyInitializerChainError:
        raise
    except (NativeLuaPropertyFactoryChainError, NativeLuaCClosurePublicationError) as exc:
        raise NativeLuaPropertyInitializerChainError(
            f"property initializer structural replay failed: {exc}"
        ) from exc
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": STRUCTURE_VERIFICATION_KIND,
        "status": "structurally_verified",
        "build_identity": dict(expected["build_identity"]),
        "evidence_sha256": _canonical_sha256(expected),
        "summary": dict(expected["summary"]),
    }


def validate_native_lua_property_initializer_chain(
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
    """Rebuild and canonical-byte-compare exact initializer evidence."""
    try:
        _validate_json_tree(evidence, "evidence")
    except NativeLuaCClosurePublicationError as exc:
        raise NativeLuaPropertyInitializerChainError(
            f"property initializer evidence is invalid: {exc}"
        ) from exc
    rebuilt = build_native_lua_property_initializer_chain(
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
        raise NativeLuaPropertyInitializerChainError(
            "native Lua property initializer evidence differs from exact rebuild"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": dict(rebuilt["build_identity"]),
        "evidence_sha256": _canonical_sha256(rebuilt),
        "summary": dict(rebuilt["summary"]),
    }


def encode_native_lua_property_initializer_chain(value: Mapping[str, Any]) -> str:
    """Return deterministic pretty JSON for evidence or a receipt."""
    _validate_json_tree(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
