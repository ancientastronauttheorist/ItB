"""Static receipt for the deferred two-range query-pointer callee.

The receipt seals decoded layout and PE syntax only. It does not turn Ghidra
analysis labels, the two calls, or the segment-qualified memory syntax into a
claim about purpose, ABI, runtime behavior, or successful return.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError,
    _REGISTER_NAMES,
    _canonical_bytes,
    _canonical_sha256 as _canonical_json_sha256,
    _normalized_declared_edge,
    _source_identity,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError,
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _decode_range,
    _hex,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_KIND,
    SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
    validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary import (
    ANALYSIS_KIND as RESIDUAL_KIND,
    _canonical_sha256 as _residual_canonical_sha256,
    _compact_sha256,
)
from src.observatory.native_query_handler_first_callee_pointer_target_static_boundary import (
    ANALYSIS_KIND as POINTER_KIND,
    _canonical_sha256 as _pointer_canonical_sha256,
)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = (
    "pe_native_query_handler_first_callee_pointer_target_"
    "multirange_static_boundary"
)
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_POINTER = "41ee47debe789243dfe9fd9566958846cd79cb82549acb99eafc9e2b5cfd9349"
_RESIDUAL = "0783fffcd973eca3937ce01faa4d4f93b974540cfdaf004a301ce7ef0198fd5d"

_ENTRY = 0x39D580
_IMAGE_BASE = 0x400000
_RANGES = (
    (
        0x39D580,
        137,
        "98edd5e264a7f1418f99230107c71b0b73b6548eb6fe58ef8fc2a1109206a995",
    ),
    (
        0x39D61F,
        27,
        "ab46e67da4115aebf6a5313ddc6cb66c1c70f6ddaf8e4cf5951e10f55f884990",
    ),
)
_BODY = "1f4270f944215528deb2ae971345d562d784bd50acc000041cce365911b5ea67"
_ATLAS = "9342b71e2bf2b3ade0b42a2c6450ef8d8af9fc51448e504566955bffe36e5131"

_POINTS = (
    (0x39D580, "55"),
    (0x39D581, "8bec"),
    (0x39D583, "6afe"),
    (0x39D585, "6810e98800"),
    (0x39D58A, "68b0297700"),
    (0x39D58F, "64a100000000"),
    (0x39D595, "50"),
    (0x39D596, "83ec08"),
    (0x39D599, "53"),
    (0x39D59A, "56"),
    (0x39D59B, "57"),
    (0x39D59C, "a1283f8900"),
    (0x39D5A1, "3145f8"),
    (0x39D5A4, "33c5"),
    (0x39D5A6, "50"),
    (0x39D5A7, "8d45f0"),
    (0x39D5AA, "64a300000000"),
    (0x39D5B0, "8965e8"),
    (0x39D5B3, "c745fc00000000"),
    (0x39D5BA, "6800004000"),
    (0x39D5BF, "e87c000000"),
    (0x39D5C4, "83c404"),
    (0x39D5C7, "85c0"),
    (0x39D5C9, "7454"),
    (0x39D5CB, "8b4508"),
    (0x39D5CE, "2d00004000"),
    (0x39D5D3, "50"),
    (0x39D5D4, "6800004000"),
    (0x39D5D9, "e852ffffff"),
    (0x39D5DE, "83c408"),
    (0x39D5E1, "85c0"),
    (0x39D5E3, "743a"),
    (0x39D5E5, "8b4024"),
    (0x39D5E8, "c1e81f"),
    (0x39D5EB, "f7d0"),
    (0x39D5ED, "83e001"),
    (0x39D5F0, "c745fcfeffffff"),
    (0x39D5F7, "8b4df0"),
    (0x39D5FA, "64890d00000000"),
    (0x39D601, "59"),
    (0x39D602, "5f"),
    (0x39D603, "5e"),
    (0x39D604, "5b"),
    (0x39D605, "8be5"),
    (0x39D607, "5d"),
    (0x39D608, "c3"),
    (0x39D61F, "c745fcfeffffff"),
    (0x39D626, "33c0"),
    (0x39D628, "8b4df0"),
    (0x39D62B, "64890d00000000"),
    (0x39D632, "59"),
    (0x39D633, "5f"),
    (0x39D634, "5e"),
    (0x39D635, "5b"),
    (0x39D636, "8be5"),
    (0x39D638, "5d"),
    (0x39D639, "c3"),
)

_OUTGOING = (
    (
        0x39D5BF,
        0x39D640,
        "722744bdeb5185942d2f7905fe9b7988f786d2e7c22cf081747858f79cafea03",
        "e07de0003b517cac5faf02a21e32552db3980edb296719910d04db79d6e59597",
        49,
    ),
    (
        0x39D5D9,
        0x39D530,
        "e2091fa15d6c96ccd134af2a889036e32422bcca28ff80076dc78453ad534f3b",
        "8bf9de6d5005bace77c5efac9dc74cf7c7189a6892d9c823af9a02a697eed765",
        67,
    ),
)
_SUCCESSOR_POLICY = (
    "only targets within the union of declared atlas ranges appear in "
    "successor_rvas; no fallthrough crosses an undeclared atlas gap"
)
_OWNER_PARTITION_SHA256 = (
    "48a52d8519a9fcf7342f56530716af793f15fc620eddf0b856c0f303f37b93b6"
)
_TARGET_OWNER_PARTITION_SHA256 = (
    "99510bf1ab711cd75f2eae4ec0f11de440eeb945b4d792956e64debdff48a1b2"
)
_TARGET_REFERENCE_PARTITION_SHA256 = (
    "82cbfb9dd0e25c2b8393c971ab66eb3c4de7b419718b89c1036ae18a164698c9"
)

_METHOD = {
    "structural_boundary": (
        "PE-free validation reconstructs both declared ranges, all decoded "
        "points, the in-union CFG, the parent and outgoing edges, typed PE "
        "operands, segment-qualified syntax, register-call audit, and the "
        "single whole-atlas entry reference. Exact reconstruction decodes "
        "the sealed executable and exhaustively traverses every atlas range."
    ),
    "body_local_successor_policy": _SUCCESSOR_POLICY,
    "not_claimed": [
        "semantic identity, analysis-label meaning, ABI, purpose, inputs, outputs, behavior, success, or normal return",
        "runtime reachability, invocation, ordering, frequency, state mutation, termination, or effect",
        "contents or runtime meaning of PE-address operands or segment-qualified memory",
        "computed, indirect, data, un-atlased, dynamic, or Lua-side references",
    ],
}


class NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
    RuntimeError
):
    """Raised when the sealed multi-range receipt cannot be reproduced."""


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return _canonical_json_sha256(value)


def _instruction_fact(rva: int, encoded: str) -> dict[str, Any]:
    raw = bytes.fromhex(encoded)
    return {
        "rva": _hex(rva),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _decoded_point(
    instruction: Any, image_base: int, expected_rva: int, encoded: str
) -> dict[str, Any]:
    raw = bytes.fromhex(encoded)
    if (
        instruction.address - image_base != expected_rva
        or bytes(instruction.bytes) != raw
        or instruction.size != len(raw)
    ):
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "decoded instruction point differs"
        )
    return _instruction_fact(expected_rva, encoded)


def _functions(program_facts: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    return _atlas_functions(program_facts)


def _declared_edges(
    program_facts: Mapping[str, Any],
) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for raw_edge in _array(
        program_facts.get("ghidra_declared_direct_calls"),
        "declared direct calls",
    ):
        edge = _mapping(raw_edge, "declared direct edge")
        site = _rva(edge.get("instruction_rva"), "declared edge site")
        if site in result:
            raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                "declared edge sites repeat"
            )
        result[site] = edge
    return result


def _identity(
    value: Mapping[str, Any], kind: str, digest: str, label: str
) -> dict[str, Any]:
    return _source_identity(value, kind, digest, label)


def _preflight(
    pointer: Mapping[str, Any],
    residual: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    identity = _mapping(program_facts.get("identity"), "program facts identity")
    if identity.get("executable_sha256") != _EXE:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "program-facts executable identity differs"
        )
    for prerequisite, label in (
        (pointer, "pointer target"),
        (residual, "residual target set"),
        (direct_calls, "direct calls"),
    ):
        if not _same(prerequisite.get("build_identity"), dict(identity)):
            raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                f"{label} build identity differs"
            )
    if _pointer_canonical_sha256(pointer) != _POINTER:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "pointer-target prerequisite differs"
        )
    if _residual_canonical_sha256(residual) != _RESIDUAL:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "residual-target-set prerequisite differs"
        )
    return {
        "program_facts": _identity(
            program_facts, "pe_ghidra_program_facts", _FACTS, "program facts"
        ),
        "pointer_target": _identity(pointer, POINTER_KIND, _POINTER, "pointer target"),
        "residual_target_set": _identity(
            residual, RESIDUAL_KIND, _RESIDUAL, "residual target set"
        ),
        "direct_calls": _identity(
            direct_calls, DIRECT_KIND, _DIRECT, "direct calls"
        ),
    }


def _decoder_contract() -> dict[str, Any]:
    return {
        "name": "capstone",
        "version": SUPPORTED_CAPSTONE_VERSION,
        "architecture": "x86",
        "mode_bits": 32,
        "sealed_instruction_count": 57,
        "range_union_cfg_projection": "multi_range_body_local_instruction_cfg_v1",
        "register_call_encoding_audit": [
            {"register": register, "encoding": f"ff{0xD0 + index:02x}"}
            for index, register in enumerate(_REGISTER_NAMES)
        ],
    }


def _expected_graph() -> dict[str, Any]:
    conditional_targets = {0x39D5C9: 0x39D61F, 0x39D5E3: 0x39D61F}
    call_sites = {0x39D5BF, 0x39D5D9}
    terminal_sites = {0x39D608, 0x39D639}
    union = {rva for rva, _encoded in _POINTS}
    nodes: list[dict[str, Any]] = []
    edge_count = 0
    for rva, encoded in _POINTS:
        fact = _instruction_fact(rva, encoded)
        fallthrough = rva + fact["size"]
        if rva in conditional_targets:
            successors = [_hex(fallthrough), _hex(conditional_targets[rva])]
            flow_kind = "direct_conditional_branch"
        elif rva in call_sites:
            successors = [_hex(fallthrough)]
            flow_kind = "call_fallthrough"
        elif rva in terminal_sites:
            successors = []
            flow_kind = "terminal"
        elif fallthrough in union:
            successors = [_hex(fallthrough)]
            flow_kind = "fallthrough"
        else:
            successors = []
            flow_kind = "gap_boundary"
        edge_count += len(successors)
        nodes.append({**fact, "flow_kind": flow_kind, "successor_rvas": successors})
    graph = {
        "caller_entry_rva": _hex(_ENTRY),
        "projection_kind": "multi_range_body_local_instruction_cfg_v1",
        "body_local_successor_policy": _SUCCESSOR_POLICY,
        "ranges": [
            {"start_rva": _hex(start), "size": size}
            for start, size, _sha256 in _RANGES
        ],
        "nodes": nodes,
        "node_count": len(nodes),
        "edge_count": edge_count,
    }
    if len(nodes) != 57 or edge_count != 57:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "expected multi-range CFG shape differs"
        )
    return graph


def _local_cfg(
    instructions_by_range: list[list[Any]], image_base: int
) -> dict[str, Any]:
    import capstone
    import capstone.x86_const as x86

    instructions = [
        instruction
        for range_instructions in instructions_by_range
        for instruction in range_instructions
    ]
    union = {instruction.address - image_base for instruction in instructions}
    nodes: list[dict[str, Any]] = []
    edge_count = 0
    for instruction in instructions:
        rva = instruction.address - image_base
        raw = bytes(instruction.bytes)
        fact = {
            "rva": _hex(rva),
            "size": instruction.size,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        fallthrough = rva + instruction.size
        immediate_targets = [
            int(operand.imm) - image_base
            for operand in instruction.operands
            if operand.type == x86.X86_OP_IMM
        ]
        if instruction.id == x86.X86_INS_RET:
            flow_kind, successors = "terminal", []
        elif instruction.id == x86.X86_INS_CALL:
            if len(immediate_targets) != 1 or fallthrough not in union:
                raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                    "direct-call CFG syntax differs"
                )
            flow_kind, successors = "call_fallthrough", [_hex(fallthrough)]
        elif instruction.group(capstone.CS_GRP_JUMP):
            if instruction.id == x86.X86_INS_JMP or len(immediate_targets) != 1:
                raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                    "multi-range branch syntax differs"
                )
            target = immediate_targets[0]
            if fallthrough not in union or target not in union:
                raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                    "conditional branch leaves the declared range union"
                )
            flow_kind = "direct_conditional_branch"
            successors = [_hex(fallthrough), _hex(target)]
        elif fallthrough in union:
            flow_kind, successors = "fallthrough", [_hex(fallthrough)]
        else:
            flow_kind, successors = "gap_boundary", []
        edge_count += len(successors)
        nodes.append({**fact, "flow_kind": flow_kind, "successor_rvas": successors})
    graph = {
        "caller_entry_rva": _hex(_ENTRY),
        "projection_kind": "multi_range_body_local_instruction_cfg_v1",
        "body_local_successor_policy": _SUCCESSOR_POLICY,
        "ranges": [
            {"start_rva": _hex(start), "size": size}
            for start, size, _sha256 in _RANGES
        ],
        "nodes": nodes,
        "node_count": len(nodes),
        "edge_count": edge_count,
    }
    if not _same(graph, _expected_graph()):
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "decoded multi-range CFG differs"
        )
    return graph


def _direct_lua_partition(direct_calls: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw_record in _array(direct_calls.get("records"), "direct-call records"):
        record = _mapping(raw_record, "direct-call record")
        if _rva(record.get("entry_rva"), "direct-call entry") == _ENTRY:
            result.extend(
                dict(_mapping(call, "direct Lua call"))
                for call in _array(
                    record.get("direct_lua_import_calls"), "direct Lua calls"
                )
            )
    if result:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "multi-range direct-Lua-call partition differs"
        )
    return result


def _empty_call_r32_audit() -> list[dict[str, Any]]:
    return [{"register": register, "call_rvas": []} for register in _REGISTER_NAMES]


def _expected_body(program_facts: Mapping[str, Any]) -> dict[str, Any]:
    function = _functions(program_facts).get(_ENTRY)
    if function is None or (
        function.get("body_size"),
        function.get("body_sha256"),
        atlas_record_sha256(function),
    ) != (164, _BODY, _ATLAS):
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "multi-range atlas body differs"
        )
    return {
        "role": "pointer_target_deferred_multirange_opaque_static_boundary",
        "entry_rva": _hex(_ENTRY),
        "atlas_record_sha256": _ATLAS,
        "body_size": 164,
        "body_sha256": _BODY,
        "ranges": [
            {"start_rva": _hex(start), "size": size, "sha256": sha256}
            for start, size, sha256 in _RANGES
        ],
        "control_flow_graph_canonical_sha256": _canonical_json_sha256(
            _expected_graph()
        ),
        "reviewed_points": [
            _instruction_fact(rva, encoded) for rva, encoded in _POINTS
        ],
        "direct_lua_calls": [],
        "staged_lua_dispatches": [],
        "call_r32_audit": _empty_call_r32_audit(),
        "register_call_partition_complete": True,
        "semantic_facts": {
            "relationship_defined_only": True,
            "analysis_labels_opaque": True,
            "source_semantic_names_assigned": False,
            "runtime_or_success_claimed": False,
        },
    }


def _parent_rows(
    pointer: Mapping[str, Any], residual: Mapping[str, Any]
) -> list[dict[str, Any]]:
    pointer_rows = _array(
        _mapping(pointer.get("native_calls"), "pointer native calls").get("direct"),
        "pointer direct rows",
    )
    pointer_hits = [
        dict(_mapping(row, "pointer parent row"))
        for row in pointer_rows
        if _rva(
            _mapping(
                _mapping(row, "pointer parent row").get("instruction"),
                "pointer parent instruction",
            ).get("rva"),
            "pointer parent site",
        )
        == 0x372A53
    ]
    deferred = [
        dict(_mapping(row, "residual deferred parent row"))
        for row in _array(
            residual.get("deferred_multirange_parent_rows"),
            "residual deferred parent rows",
        )
    ]
    if (
        len(pointer_hits) != 1
        or len(deferred) != 1
        or not _same(pointer_hits, deferred)
        or _rva(pointer_hits[0].get("source_entry_rva"), "parent source")
        != 0x3729B0
        or _rva(pointer_hits[0].get("target_entry_rva"), "parent target")
        != _ENTRY
    ):
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "multi-range parent join differs"
        )
    return pointer_hits


def _outgoing_rows(program_facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions = _functions(program_facts)
    declared = _declared_edges(program_facts)
    source = functions.get(_ENTRY)
    if source is None:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "multi-range source atlas record is absent"
        )
    points = dict(_POINTS)
    result: list[dict[str, Any]] = []
    for site, target, body_sha, atlas_sha, body_size in _OUTGOING:
        edge, target_function = declared.get(site), functions.get(target)
        if (
            edge is None
            or target_function is None
            or (
                _rva(edge.get("source_entry_rva"), "outgoing source"),
                _rva(edge.get("target_entry_rva"), "outgoing target entry"),
                _rva(edge.get("target_rva"), "outgoing target"),
            )
            != (_ENTRY, target, target)
            or (
                target_function.get("body_size"),
                target_function.get("body_sha256"),
                atlas_record_sha256(target_function),
            )
            != (body_size, body_sha, atlas_sha)
        ):
            raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                "outgoing edge or target atlas record differs"
            )
        result.append(
            {
                "role": "opaque_declared_direct_edge",
                "instruction": _instruction_fact(site, points[site]),
                "source_entry_rva": _hex(_ENTRY),
                "source_atlas_record_sha256": atlas_record_sha256(source),
                "source_body_size": 164,
                "source_body_sha256": _BODY,
                "target_entry_rva": _hex(target),
                "target_atlas_record_sha256": atlas_sha,
                "target_body_size": body_size,
                "target_body_sha256": body_sha,
                "ghidra_declared_direct_edge": _normalized_declared_edge(edge),
                "control_encoding": "e8",
            }
        )
    return result


def _operand_access(value: int) -> str:
    names = {0: "none", 1: "read", 2: "write", 3: "read_write"}
    if value not in names:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "unsupported operand access mask"
        )
    return names[value]


def _expected_pe_address_operands() -> list[dict[str, Any]]:
    specs = (
        (0x39D585, "6810e98800", "immediate", 0, "none", 0x88E910, "noncontrol_immediate", ".rdata", 0x3D6000, 0x40000040),
        (0x39D58A, "68b0297700", "immediate", 0, "none", 0x7729B0, "noncontrol_immediate", ".text", 0x1000, 0x60000020),
        (0x39D59C, "a1283f8900", "absolute_memory", 1, "read", 0x893F28, "noncontrol_absolute_memory", ".data", 0x492000, 0xC0000040),
        (0x39D5BF, "e87c000000", "immediate", 0, "none", 0x79D640, "declared_direct_call_target", ".text", 0x1000, 0x60000020),
        (0x39D5C9, "7454", "immediate", 0, "none", 0x79D61F, "declared_conditional_branch_target", ".text", 0x1000, 0x60000020),
        (0x39D5D9, "e852ffffff", "immediate", 0, "none", 0x79D530, "declared_direct_call_target", ".text", 0x1000, 0x60000020),
        (0x39D5E3, "743a", "immediate", 0, "none", 0x79D61F, "declared_conditional_branch_target", ".text", 0x1000, 0x60000020),
    )
    return [
        {
            "role": "typed_pe_address_operand",
            "instruction": _instruction_fact(site, encoded),
            "operand_class": operand_class,
            "operand_index": operand_index,
            "operand_access": access,
            "operand_va": _hex(value),
            "operand_rva": _hex(value - _IMAGE_BASE),
            "control_syntax": control_syntax,
            "section_name": section_name,
            "section_rva": _hex(section_rva),
            "section_characteristics": _hex(characteristics),
            "section_writable": bool(characteristics & 0x80000000),
            "file_backed": True,
            "contents_or_runtime_behavior_opaque": True,
        }
        for (
            site,
            encoded,
            operand_class,
            operand_index,
            access,
            value,
            control_syntax,
            section_name,
            section_rva,
            characteristics,
        ) in specs
    ]


def _expected_segment_syntax() -> list[dict[str, Any]]:
    specs = (
        (0x39D58F, "64a100000000", 1, "read"),
        (0x39D5AA, "64a300000000", 0, "write"),
        (0x39D5FA, "64890d00000000", 0, "write"),
        (0x39D62B, "64890d00000000", 0, "write"),
    )
    return [
        {
            "role": "opaque_segment_qualified_memory_syntax",
            "instruction": _instruction_fact(site, encoded),
            "operand_index": operand_index,
            "operand_access": access,
            "segment": "fs",
            "displacement": "0x00000000",
            "absolute_memory_class_excluded": True,
            "contents_or_runtime_behavior_opaque": True,
        }
        for site, encoded, operand_index, access in specs
    ]


def _expected_native_syntax() -> dict[str, Any]:
    key = lambda row: (
        _rva(row["instruction"]["rva"], "operand site"),
        row["operand_index"],
    )
    return {
        "opaque_indirect_controls": [],
        "indirect_control_partition_complete": True,
        "pe_address_operands": sorted(_expected_pe_address_operands(), key=key),
        "pe_address_operand_partition_complete": True,
        "segment_qualified_memory_syntax": sorted(_expected_segment_syntax(), key=key),
        "segment_qualified_memory_partition_complete": True,
        "call_r32_audit": _empty_call_r32_audit(),
        "register_call_partition_complete": True,
    }


def _native_syntax(
    image: Any, instructions_by_range: list[list[Any]]
) -> dict[str, Any]:
    import capstone.x86_const as x86

    instructions = [
        instruction
        for range_instructions in instructions_by_range
        for instruction in range_instructions
    ]
    call_r32_sites: dict[str, list[int]] = {
        register: [] for register in _REGISTER_NAMES
    }
    indirect_controls: list[dict[str, Any]] = []
    pe_operands: list[dict[str, Any]] = []
    segment_syntax: list[dict[str, Any]] = []
    role_by_site = {
        0x39D585: "noncontrol_immediate",
        0x39D58A: "noncontrol_immediate",
        0x39D59C: "noncontrol_absolute_memory",
        0x39D5BF: "declared_direct_call_target",
        0x39D5C9: "declared_conditional_branch_target",
        0x39D5D9: "declared_direct_call_target",
        0x39D5E3: "declared_conditional_branch_target",
    }
    register_by_capstone = {
        x86.X86_REG_EAX: "EAX",
        x86.X86_REG_ECX: "ECX",
        x86.X86_REG_EDX: "EDX",
        x86.X86_REG_EBX: "EBX",
        x86.X86_REG_ESP: "ESP",
        x86.X86_REG_EBP: "EBP",
        x86.X86_REG_ESI: "ESI",
        x86.X86_REG_EDI: "EDI",
    }
    for instruction in instructions:
        rva = instruction.address - image.image_base
        raw = bytes(instruction.bytes)
        if instruction.id in {x86.X86_INS_CALL, x86.X86_INS_JMP} and any(
            operand.type in {x86.X86_OP_REG, x86.X86_OP_MEM}
            for operand in instruction.operands
        ):
            indirect_controls.append({"instruction": {
                "rva": _hex(rva),
                "size": instruction.size,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }})
        if instruction.id == x86.X86_INS_CALL:
            for operand in instruction.operands:
                if operand.type != x86.X86_OP_REG:
                    continue
                register = register_by_capstone.get(operand.reg)
                if (
                    register is None
                    or len(raw) != 2
                    or raw[0] != 0xFF
                    or raw[1] != 0xD0 + _REGISTER_NAMES.index(register)
                ):
                    raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                        "unrecognized register-call encoding"
                    )
                call_r32_sites[register].append(rva)
        for operand_index, operand in enumerate(instruction.operands):
            if operand.type == x86.X86_OP_MEM and operand.mem.segment != x86.X86_REG_INVALID:
                if (
                    operand.mem.segment != x86.X86_REG_FS
                    or operand.mem.base != x86.X86_REG_INVALID
                    or operand.mem.index != x86.X86_REG_INVALID
                    or (int(operand.mem.disp) & 0xFFFFFFFF) != 0
                ):
                    raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                        "unreviewed segment-qualified memory syntax"
                    )
                segment_syntax.append({
                    "role": "opaque_segment_qualified_memory_syntax",
                    "instruction": {
                        "rva": _hex(rva),
                        "size": instruction.size,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    },
                    "operand_index": operand_index,
                    "operand_access": _operand_access(operand.access),
                    "segment": "fs",
                    "displacement": "0x00000000",
                    "absolute_memory_class_excluded": True,
                    "contents_or_runtime_behavior_opaque": True,
                })
                continue
            if operand.type == x86.X86_OP_IMM:
                value, operand_class = int(operand.imm) & 0xFFFFFFFF, "immediate"
            elif (
                operand.type == x86.X86_OP_MEM
                and operand.mem.segment == x86.X86_REG_INVALID
                and operand.mem.base == x86.X86_REG_INVALID
                and operand.mem.index == x86.X86_REG_INVALID
            ):
                value = int(operand.mem.disp) & 0xFFFFFFFF
                operand_class = "absolute_memory"
            else:
                continue
            target_rva = value - image.image_base
            section = next((
                candidate
                for candidate in image.sections
                if candidate.virtual_address <= target_rva < candidate.virtual_address + candidate.virtual_size
            ), None)
            if section is None:
                continue
            if rva not in role_by_site:
                raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                    "unreviewed PE-address operand"
                )
            pe_operands.append({
                "role": "typed_pe_address_operand",
                "instruction": {
                    "rva": _hex(rva),
                    "size": instruction.size,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                },
                "operand_class": operand_class,
                "operand_index": operand_index,
                "operand_access": _operand_access(operand.access),
                "operand_va": _hex(value),
                "operand_rva": _hex(target_rva),
                "control_syntax": role_by_site[rva],
                "section_name": section.name,
                "section_rva": _hex(section.virtual_address),
                "section_characteristics": _hex(section.characteristics),
                "section_writable": bool(section.characteristics & 0x80000000),
                "file_backed": image.rva_to_file_offset(target_rva) is not None,
                "contents_or_runtime_behavior_opaque": True,
            })
    if indirect_controls:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "indirect-control partition differs"
        )
    key = lambda row: (
        _rva(row["instruction"]["rva"], "syntax site"),
        row["operand_index"],
    )
    result = {
        "opaque_indirect_controls": [],
        "indirect_control_partition_complete": True,
        "pe_address_operands": sorted(pe_operands, key=key),
        "pe_address_operand_partition_complete": True,
        "segment_qualified_memory_syntax": sorted(segment_syntax, key=key),
        "segment_qualified_memory_partition_complete": True,
        "call_r32_audit": [
            {"register": register, "call_rvas": [_hex(site) for site in call_r32_sites[register]]}
            for register in _REGISTER_NAMES
        ],
        "register_call_partition_complete": True,
    }
    if not _same(result, _expected_native_syntax()):
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "decoded native syntax partition differs"
        )
    return result


def _reference_record(
    *,
    site: int,
    owner: int,
    raw: bytes,
    operand_index: int,
    functions: Mapping[int, Mapping[str, Any]],
    declared: Mapping[int, Mapping[str, Any]],
    image_base: int,
) -> dict[str, Any]:
    function, edge = functions.get(owner), declared.get(site)
    if function is None or edge is None:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "reference atlas or declared-edge join differs"
        )
    if (
        len(raw) != 5
        or raw[0] != 0xE8
        or operand_index != 0
        or int.from_bytes(raw[1:], "little", signed=True) + site + 5 != _ENTRY
        or (
            _rva(edge.get("source_entry_rva"), "reference source"),
            _rva(edge.get("target_entry_rva"), "reference target entry"),
            _rva(edge.get("target_rva"), "reference target"),
        ) != (owner, _ENTRY, _ENTRY)
    ):
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "entry reference syntax or declared edge differs"
        )
    return {
        "instruction_rva": _hex(site),
        "instruction_size": len(raw),
        "instruction_sha256": hashlib.sha256(raw).hexdigest(),
        "owner_entry_rva": _hex(owner),
        "owner_atlas_record_sha256": atlas_record_sha256(function),
        "target_rva": _hex(_ENTRY),
        "target_atlas_record_sha256": _ATLAS,
        "target_va": _hex(image_base + _ENTRY),
        "operand_class": "immediate",
        "operand_index": 0,
        "use_class": "direct_call",
        "call_form": "x86_relative_near_call_e8",
        "ghidra_declared_direct_edge": _normalized_declared_edge(edge),
    }


def _scan_receipt(references: list[dict[str, Any]]) -> dict[str, Any]:
    references = sorted(references, key=lambda row: (row["instruction_rva"], row["operand_index"]))
    if len(references) != 1:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "entry-reference count differs"
        )
    owner_counts: dict[tuple[str, str], int] = {}
    target_owner_counts: dict[tuple[str, str, str], int] = {}
    for row in references:
        owner_key = row["owner_entry_rva"], row["owner_atlas_record_sha256"]
        owner_counts[owner_key] = owner_counts.get(owner_key, 0) + 1
        target_owner_key = row["target_rva"], *owner_key
        target_owner_counts[target_owner_key] = target_owner_counts.get(target_owner_key, 0) + 1
    owner_partition = [
        {"owner_entry_rva": owner, "owner_atlas_record_sha256": atlas, "reference_count": count}
        for (owner, atlas), count in sorted(owner_counts.items())
    ]
    target_owner_partition = [
        {"target_rva": target, "owner_entry_rva": owner, "owner_atlas_record_sha256": atlas, "reference_count": count}
        for (target, owner, atlas), count in sorted(target_owner_counts.items())
    ]
    target_partition = [{
        "target_rva": _hex(_ENTRY),
        "target_atlas_record_sha256": _ATLAS,
        "reference_count": 1,
        "owner_count": 1,
    }]
    target_reference_partition = [{
        "target_rva": _hex(_ENTRY),
        "target_atlas_record_sha256": _ATLAS,
        "reference_count": 1,
    }]
    partition_sha256 = {
        "owner_partition": _compact_sha256(owner_partition),
        "target_owner_partition": _compact_sha256(target_owner_partition),
        "target_reference_partition": _compact_sha256(target_reference_partition),
    }
    if partition_sha256 != {
        "owner_partition": _OWNER_PARTITION_SHA256,
        "target_owner_partition": _TARGET_OWNER_PARTITION_SHA256,
        "target_reference_partition": _TARGET_REFERENCE_PARTITION_SHA256,
    }:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "entry-reference partition identity differs"
        )
    return {
        "scope": {
            "atlas_function_count": 25312,
            "atlas_body_range_count": 25490,
            "decoded_bytes": 3735718,
            "decoded_instructions": 1153814,
            "all_declared_ranges_decoded": True,
            "operand_classes": ["absolute_memory", "immediate"],
        },
        "references": references,
        "target_partition": target_partition,
        "target_reference_partition": target_reference_partition,
        "owner_partition": owner_partition,
        "target_owner_partition": target_owner_partition,
        "partition_sha256": partition_sha256,
        "aggregates": {
            "reference_count": 1,
            "target_count": 1,
            "owner_count": 1,
            "target_owner_count": 1,
            "direct_call_count": 1,
            "other_address_count": 0,
            "memory_operand_count": 0,
        },
    }


def _expected_scan(program_facts: Mapping[str, Any]) -> dict[str, Any]:
    functions = _functions(program_facts)
    declared = _declared_edges(program_facts)
    site, owner = 0x372A53, 0x3729B0
    raw = bytes((0xE8,)) + int(_ENTRY - (site + 5)).to_bytes(4, "little", signed=True)
    return _scan_receipt([_reference_record(
        site=site,
        owner=owner,
        raw=raw,
        operand_index=0,
        functions=functions,
        declared=declared,
        image_base=_IMAGE_BASE,
    )])


def _scan(
    data: bytes,
    image: Any,
    decoder: Any,
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    import capstone.x86_const as x86

    functions = _functions(program_facts)
    declared = _declared_edges(program_facts)
    image_base = _rva(
        _mapping(program_facts.get("ghidra"), "ghidra").get("image_base"),
        "image base",
    )
    if image_base != image.image_base or image_base != _IMAGE_BASE:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "image-base identity differs"
        )
    target_va = image_base + _ENTRY
    references: list[dict[str, Any]] = []
    range_count = byte_count = instruction_count = 0
    decoder.detail = True
    for owner, function in sorted(functions.items()):
        for raw_span in _array(function.get("ranges"), "atlas ranges"):
            span = _mapping(raw_span, "atlas range")
            start = _rva(span.get("start_rva"), "atlas range start")
            size = span.get("size")
            if type(size) is not int or size <= 0:
                raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                    "atlas range size differs"
                )
            instructions = _decode_range(data, image, start, size, decoder)
            range_count += 1
            byte_count += size
            instruction_count += len(instructions)
            for instruction in instructions:
                for operand_index, operand in enumerate(instruction.operands):
                    if operand.type == x86.X86_OP_IMM:
                        value = int(operand.imm) & 0xFFFFFFFF
                    elif (
                        operand.type == x86.X86_OP_MEM
                        and operand.mem.segment == x86.X86_REG_INVALID
                        and operand.mem.base == x86.X86_REG_INVALID
                        and operand.mem.index == x86.X86_REG_INVALID
                    ):
                        value = int(operand.mem.disp) & 0xFFFFFFFF
                    else:
                        continue
                    if value != target_va:
                        continue
                    references.append(_reference_record(
                        site=instruction.address - image_base,
                        owner=owner,
                        raw=bytes(instruction.bytes),
                        operand_index=operand_index,
                        functions=functions,
                        declared=declared,
                        image_base=image_base,
                    ))
    if (range_count, byte_count, instruction_count) != (25490, 3735718, 1153814):
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "whole-atlas scan scope differs"
        )
    receipt = _scan_receipt(references)
    if not _same(receipt, _expected_scan(program_facts)):
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "whole-atlas entry-reference receipt differs"
        )
    return receipt


def _parent_scan_join(
    parent_rows: list[dict[str, Any]], scan: Mapping[str, Any]
) -> None:
    references = _array(scan.get("references"), "entry references")
    if len(parent_rows) != 1 or len(references) != 1:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "parent/reference cardinality differs"
        )
    parent, reference = parent_rows[0], _mapping(references[0], "entry reference")
    instruction = _mapping(parent.get("instruction"), "parent instruction")
    if (
        instruction.get("rva") != reference.get("instruction_rva")
        or instruction.get("size") != reference.get("instruction_size")
        or instruction.get("sha256") != reference.get("instruction_sha256")
        or parent.get("source_entry_rva") != reference.get("owner_entry_rva")
        or parent.get("source_atlas_record_sha256") != reference.get("owner_atlas_record_sha256")
        or parent.get("target_entry_rva") != reference.get("target_rva")
        or parent.get("target_atlas_record_sha256") != reference.get("target_atlas_record_sha256")
        or not _same(parent.get("ghidra_declared_direct_edge"), reference.get("ghidra_declared_direct_edge"))
    ):
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "parent/reference join differs"
        )


def _summary(_: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "reviewed_target_count": 1,
        "reviewed_target_bytes": 164,
        "sealed_instruction_count": 57,
        "sealed_control_flow_graph_count": 1,
        "sealed_control_flow_graph_node_count": 57,
        "sealed_control_flow_graph_edge_count": 57,
        "native_direct_edge_count": 2,
        "direct_lua_call_count": 0,
        "staged_lua_dispatch_count": 0,
        "call_r32_count": 0,
        "opaque_indirect_control_count": 0,
        "pe_address_operand_count": 7,
        "pe_immediate_operand_count": 6,
        "pe_absolute_memory_operand_count": 1,
        "segment_qualified_memory_syntax_count": 4,
        "pointer_target_parent_edge_count": 1,
        "target_reference_count": 1,
        "target_reference_target_count": 1,
        "target_reference_owner_count": 1,
        "target_reference_direct_call_count": 1,
        "target_reference_other_address_count": 0,
        "target_reference_memory_operand_count": 0,
        "schema_violations": 0,
    }


def _evidence(
    pointer: Mapping[str, Any],
    residual: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    graph: Mapping[str, Any] | None = None,
    native_syntax: Mapping[str, Any] | None = None,
    scan: Mapping[str, Any] | None = None,
    reviewed_points: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    direct_receipt = validate_native_lua_direct_call_structure(direct_calls, program_facts)
    if (
        direct_receipt.get("status") != "structurally_verified"
        or direct_receipt.get("evidence_sha256") != _DIRECT
    ):
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "direct-call prerequisite differs"
        )
    prerequisites = _preflight(pointer, residual, direct_calls, program_facts)
    _direct_lua_partition(direct_calls)
    body = _expected_body(program_facts)
    if reviewed_points is not None:
        body["reviewed_points"] = reviewed_points
    expected_graph = _expected_graph()
    expected_native = _expected_native_syntax()
    expected_scan = _expected_scan(program_facts)
    graph = expected_graph if graph is None else dict(graph)
    native_syntax = expected_native if native_syntax is None else dict(native_syntax)
    scan = expected_scan if scan is None else dict(scan)
    if (
        not _same(graph, expected_graph)
        or not _same(native_syntax, expected_native)
        or not _same(scan, expected_scan)
    ):
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "exact component differs from the sealed structural receipt"
        )
    parents = _parent_rows(pointer, residual)
    _parent_scan_join(parents, scan)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(_mapping(program_facts.get("identity"), "program facts identity")),
        "program_facts": prerequisites["program_facts"],
        "pointer_target_static_boundary": prerequisites["pointer_target"],
        "residual_target_set_static_boundary": prerequisites["residual_target_set"],
        "direct_call_census": prerequisites["direct_calls"],
        "decoder": _decoder_contract(),
        "function_body": body,
        "control_flow_graph": graph,
        "pointer_target_parent_edges": parents,
        "native_calls": {"outgoing_direct": _outgoing_rows(program_facts), **native_syntax},
        "whole_atlas_reference_scan": scan,
        "method": _METHOD,
    }
    result["summary"] = _summary(result)
    _assert_publication_safe(result)
    return result


def validate_native_query_handler_first_callee_pointer_target_multirange_static_boundary_structure(
    evidence: Mapping[str, Any],
    pointer: Mapping[str, Any],
    residual: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate every finite receipt field without opening the executable."""
    try:
        for item, label in (
            (evidence, "evidence"),
            (pointer, "pointer target"),
            (residual, "residual target set"),
            (direct_calls, "direct calls"),
            (program_facts, "program facts"),
        ):
            _validate_json_tree(item, label)
        value = _mapping(evidence, "evidence")
        expected = _evidence(pointer, residual, direct_calls, program_facts)
        if not _same(value, expected):
            raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                "multi-range receipt differs"
            )
        _assert_publication_safe(value)
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
            "build_identity": dict(value["build_identity"]),
            "evidence_sha256": _canonical_sha256(value),
            "summary": dict(value["summary"]),
        }
    except NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError:
        raise
    except (
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        NativeLuaClassReturnHelperChainError,
        PEAnchorError,
    ) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(str(exc)) from exc


def build_native_query_handler_first_callee_pointer_target_multirange_static_boundary(
    executable: Path,
    pointer: Mapping[str, Any],
    residual: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact multi-range receipt from the sealed executable."""
    try:
        for item, label in (
            (pointer, "pointer target"),
            (residual, "residual target set"),
            (direct_calls, "direct calls"),
            (program_facts, "program facts"),
            (inventory, "inventory"),
        ):
            _validate_json_tree(item, label)
        direct_receipt = validate_native_lua_direct_call_census(
            executable, direct_calls, program_facts, inventory=inventory
        )
        if (
            direct_receipt.get("status") != "verified"
            or direct_receipt.get("evidence_sha256") != _DIRECT
        ):
            raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                "direct-call exact prerequisite differs"
            )
        _preflight(pointer, residual, direct_calls, program_facts)
        data, image, executable_sha256 = _load_executable(executable)
        if executable_sha256 != _EXE:
            raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                "sealed executable differs"
            )
        decoder, _call_id = _decoder()
        decoder.detail = True
        instructions_by_range: list[list[Any]] = []
        reviewed_points: list[dict[str, Any]] = []
        point_offset = 0
        joined_body = bytearray()
        for start, size, range_sha256 in _RANGES:
            instructions = _decode_range(data, image, start, size, decoder)
            raw = b"".join(bytes(instruction.bytes) for instruction in instructions)
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != range_sha256:
                raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                    "multi-range body bytes differ"
                )
            expected_points = _POINTS[point_offset : point_offset + len(instructions)]
            if len(expected_points) != len(instructions):
                raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                    "multi-range point partition differs"
                )
            reviewed_points.extend(
                _decoded_point(instruction, image.image_base, expected_rva, encoded)
                for instruction, (expected_rva, encoded) in zip(instructions, expected_points)
            )
            point_offset += len(instructions)
            joined_body.extend(raw)
            instructions_by_range.append(instructions)
        if point_offset != len(_POINTS) or hashlib.sha256(joined_body).hexdigest() != _BODY:
            raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                "multi-range aggregate body identity differs"
            )
        graph = _local_cfg(instructions_by_range, image.image_base)
        native_syntax = _native_syntax(image, instructions_by_range)
        scan = _scan(data, image, decoder, program_facts)
        result = _evidence(
            pointer,
            residual,
            direct_calls,
            program_facts,
            graph=graph,
            native_syntax=native_syntax,
            scan=scan,
            reviewed_points=reviewed_points,
        )
        if _load_executable(executable)[2] != executable_sha256:
            raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
                "executable changed during exact reconstruction"
            )
        validate_native_query_handler_first_callee_pointer_target_multirange_static_boundary_structure(
            result, pointer, residual, direct_calls, program_facts
        )
        return result
    except NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError:
        raise
    except (
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        NativeLuaClassReturnHelperChainError,
        PEAnchorError,
        OSError,
    ) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(str(exc)) from exc


def validate_native_query_handler_first_callee_pointer_target_multirange_static_boundary(
    executable: Path,
    evidence: Mapping[str, Any],
    pointer: Mapping[str, Any],
    residual: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and verify the exact multi-range receipt."""
    rebuilt = build_native_query_handler_first_callee_pointer_target_multirange_static_boundary(
        executable,
        pointer,
        residual,
        direct_calls,
        program_facts,
        inventory=inventory,
    )
    if not _same(evidence, rebuilt):
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError(
            "evidence differs from exact reconstruction"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": dict(rebuilt["build_identity"]),
        "evidence_sha256": _canonical_sha256(rebuilt),
        "summary": dict(rebuilt["summary"]),
    }


def encode_native_query_handler_first_callee_pointer_target_multirange_static_boundary(
    value: Mapping[str, Any],
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
