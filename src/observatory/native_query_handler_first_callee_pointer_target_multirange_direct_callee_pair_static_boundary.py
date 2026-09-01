"""Static receipt for the two direct callees of the query-pointer target.

The receipt seals decoded layout, body-local control flow, typed PE syntax,
the two parent edges, and exhaustive atlas references.  It deliberately does
not assign source semantics or claim anything about runtime behavior.
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
from src.observatory.native_query_handler_first_callee_pointer_target_multirange_static_boundary import (
    ANALYSIS_KIND as MULTIRANGE_KIND,
    NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError,
    _canonical_sha256 as _multirange_canonical_sha256,
)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = (
    "pe_native_query_handler_first_callee_pointer_target_"
    "multirange_direct_callee_pair_static_boundary"
)
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_MULTIRANGE = "a19a16ff5b999872acba98381163dc7d67113864ff508454d63162aa719e1c4e"

_IMAGE_BASE = 0x400000
_PARENT_ENTRY = 0x39D580
_PARENT_BODY_SIZE = 164
_PARENT_BODY_SHA256 = (
    "1f4270f944215528deb2ae971345d562d784bd50acc000041cce365911b5ea67"
)
_PARENT_ATLAS_SHA256 = (
    "9342b71e2bf2b3ade0b42a2c6450ef8d8af9fc51448e504566955bffe36e5131"
)

_BODY_SPECS = (
    (
        0x39D530,
        67,
        "e2091fa15d6c96ccd134af2a889036e32422bcca28ff80076dc78453ad534f3b",
        "8bf9de6d5005bace77c5efac9dc74cf7c7189a6892d9c823af9a02a697eed765",
        (
            (0x39D530, "55"),
            (0x39D531, "8bec"),
            (0x39D533, "8b4508"),
            (0x39D536, "33d2"),
            (0x39D538, "53"),
            (0x39D539, "56"),
            (0x39D53A, "57"),
            (0x39D53B, "8b483c"),
            (0x39D53E, "03c8"),
            (0x39D540, "0fb74114"),
            (0x39D544, "0fb75906"),
            (0x39D548, "83c018"),
            (0x39D54B, "03c1"),
            (0x39D54D, "85db"),
            (0x39D54F, "741b"),
            (0x39D551, "8b7d0c"),
            (0x39D554, "8b700c"),
            (0x39D557, "3bfe"),
            (0x39D559, "7209"),
            (0x39D55B, "8b4808"),
            (0x39D55E, "03ce"),
            (0x39D560, "3bf9"),
            (0x39D562, "720a"),
            (0x39D564, "42"),
            (0x39D565, "83c028"),
            (0x39D568, "3bd3"),
            (0x39D56A, "72e8"),
            (0x39D56C, "33c0"),
            (0x39D56E, "5f"),
            (0x39D56F, "5e"),
            (0x39D570, "5b"),
            (0x39D571, "5d"),
            (0x39D572, "c3"),
        ),
        {
            0x39D54F: 0x39D56C,
            0x39D559: 0x39D564,
            0x39D562: 0x39D56E,
            0x39D56A: 0x39D554,
        },
        frozenset({0x39D572}),
    ),
    (
        0x39D640,
        49,
        "722744bdeb5185942d2f7905fe9b7988f786d2e7c22cf081747858f79cafea03",
        "e07de0003b517cac5faf02a21e32552db3980edb296719910d04db79d6e59597",
        (
            (0x39D640, "55"),
            (0x39D641, "8bec"),
            (0x39D643, "8b4508"),
            (0x39D646, "b94d5a0000"),
            (0x39D64B, "663908"),
            (0x39D64E, "7404"),
            (0x39D650, "33c0"),
            (0x39D652, "5d"),
            (0x39D653, "c3"),
            (0x39D654, "8b483c"),
            (0x39D657, "03c8"),
            (0x39D659, "33c0"),
            (0x39D65B, "813950450000"),
            (0x39D661, "750c"),
            (0x39D663, "ba0b010000"),
            (0x39D668, "66395118"),
            (0x39D66C, "0f94c0"),
            (0x39D66F, "5d"),
            (0x39D670, "c3"),
        ),
        {0x39D64E: 0x39D654, 0x39D661: 0x39D66F},
        frozenset({0x39D653, 0x39D670}),
    ),
)

_SPECS_BY_ENTRY = {spec[0]: spec for spec in _BODY_SPECS}
_TARGETS = frozenset(_SPECS_BY_ENTRY)
_PARENT_SITES = {0x39D5BF: 0x39D640, 0x39D5D9: 0x39D530}
_PARENT_INSTRUCTIONS = {
    0x39D5BF: "e87c000000",
    0x39D5D9: "e852ffffff",
}
_PE_OPERANDS = {
    0x39D54F: ("741b", 0x79D56C),
    0x39D559: ("7209", 0x79D564),
    0x39D562: ("720a", 0x79D56E),
    0x39D56A: ("72e8", 0x79D554),
    0x39D64E: ("7404", 0x79D654),
    0x39D661: ("750c", 0x79D66F),
}

_PAIR_OWNER_HASH = (
    "751468fb4a47b8885547c9880c5a755f2b225f6c2f8253acc56f8231830bb5d6"
)
_PAIR_TARGET_OWNER_HASH = (
    "73f08fc635b2768f2e4fad7baf1861126489488faf00af74b8ef36d9c86a3ce0"
)
_PAIR_TARGET_REF_HASH = (
    "4bc97f58b81bf1a9d3f70d3054f3df61718b7bed2d090b3cd63ac71f97716339"
)

_SUCCESSOR_POLICY = (
    "only successors within each declared single-range body appear in "
    "successor_rvas; terminal RET instructions have no successor"
)
_METHOD = {
    "structural_boundary": (
        "PE-free validation reconstructs both declared direct callees, every "
        "decoded point, both body-local CFGs, typed PE operands, empty local "
        "control partitions, the two parent edges, and both whole-atlas entry "
        "references. Exact reconstruction decodes the sealed executable and "
        "exhaustively traverses every declared atlas range."
    ),
    "body_local_successor_policy": _SUCCESSOR_POLICY,
    "not_claimed": [
        "semantic identity, analysis-label meaning, ABI, purpose, inputs, outputs, behavior, success, or normal return",
        "runtime reachability, invocation, ordering, frequency, state mutation, termination, or effect",
        "contents or runtime meaning of PE-address operands",
        "computed, indirect, data, un-atlased, dynamic, or Lua-side references",
    ],
}


class NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError(
    RuntimeError
):
    """Raised when the sealed direct-callee pair cannot be reproduced."""


def _error(message: str) -> None:
    raise NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError(
        message
    )


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return _canonical_json_sha256(value)


def _compact_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
        or instruction.size != len(raw)
        or bytes(instruction.bytes) != raw
    ):
        _error("decoded instruction point differs")
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
            _error("declared edge sites repeat")
        result[site] = edge
    return result


def _identity(
    value: Mapping[str, Any], kind: str, digest: str, label: str
) -> dict[str, Any]:
    return _source_identity(value, kind, digest, label)


def _preflight(
    multirange: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    identity = _mapping(program_facts.get("identity"), "program facts identity")
    if identity.get("executable_sha256") != _EXE:
        _error("program-facts executable identity differs")
    for prerequisite, label in (
        (multirange, "multirange static boundary"),
        (direct_calls, "direct calls"),
    ):
        if not _same(prerequisite.get("build_identity"), dict(identity)):
            _error(f"{label} build identity differs")
    if _multirange_canonical_sha256(multirange) != _MULTIRANGE:
        _error("multirange prerequisite differs")
    direct_receipt = validate_native_lua_direct_call_structure(
        direct_calls, program_facts
    )
    if (
        direct_receipt.get("status") != "structurally_verified"
        or direct_receipt.get("evidence_sha256") != _DIRECT
    ):
        _error("direct-call prerequisite differs")
    return {
        "program_facts": _identity(
            program_facts,
            "pe_ghidra_program_facts",
            _FACTS,
            "program facts",
        ),
        "multirange_static_boundary": _identity(
            multirange,
            MULTIRANGE_KIND,
            _MULTIRANGE,
            "multirange static boundary",
        ),
        "direct_call_census": _identity(
            direct_calls, DIRECT_KIND, _DIRECT, "direct calls"
        ),
    }


def _decoder_contract() -> dict[str, Any]:
    return {
        "name": "capstone",
        "version": SUPPORTED_CAPSTONE_VERSION,
        "architecture": "x86",
        "mode_bits": 32,
        "sealed_instruction_count": 52,
        "range_union_cfg_projection": "single_range_body_local_instruction_cfg_v1",
        "register_call_encoding_audit": [
            {"register": register, "encoding": f"ff{0xD0 + index:02x}"}
            for index, register in enumerate(_REGISTER_NAMES)
        ],
    }


def _expected_graph(spec: tuple[Any, ...]) -> dict[str, Any]:
    entry, size, _body, _atlas, points, branches, terminals = spec
    point_rvas = {rva for rva, _encoded in points}
    nodes: list[dict[str, Any]] = []
    edge_count = 0
    for rva, encoded in points:
        fact = _instruction_fact(rva, encoded)
        fallthrough = rva + fact["size"]
        if rva in branches:
            flow_kind = "direct_conditional_branch"
            successors = [_hex(fallthrough), _hex(branches[rva])]
        elif rva in terminals:
            flow_kind, successors = "terminal", []
        elif fallthrough in point_rvas:
            flow_kind, successors = "fallthrough", [_hex(fallthrough)]
        else:
            _error("expected body has an unreviewed range boundary")
        edge_count += len(successors)
        nodes.append(
            {**fact, "flow_kind": flow_kind, "successor_rvas": successors}
        )
    expected_shape = (33, 36) if entry == 0x39D530 else (19, 19)
    if (len(nodes), edge_count) != expected_shape:
        _error("expected body-local CFG shape differs")
    return {
        "entry_rva": _hex(entry),
        "projection_kind": "single_range_body_local_instruction_cfg_v1",
        "body_local_successor_policy": _SUCCESSOR_POLICY,
        "ranges": [{"start_rva": _hex(entry), "size": size}],
        "nodes": nodes,
        "node_count": len(nodes),
        "edge_count": edge_count,
    }


def _expected_graphs() -> list[dict[str, Any]]:
    return [_expected_graph(spec) for spec in _BODY_SPECS]


def _local_graph(
    spec: tuple[Any, ...], instructions: list[Any], image_base: int
) -> dict[str, Any]:
    import capstone
    import capstone.x86_const as x86

    entry, size, _body, _atlas, _points, _branches, _terminals = spec
    body_rvas = {instruction.address - image_base for instruction in instructions}
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
            if len(immediate_targets) != 1:
                _error("direct-call CFG syntax differs")
            flow_kind = "call_fallthrough"
            successors = [_hex(fallthrough)] if fallthrough in body_rvas else []
        elif instruction.group(capstone.CS_GRP_JUMP):
            if len(immediate_targets) != 1:
                _error("branch CFG syntax differs")
            target = immediate_targets[0]
            if instruction.id == x86.X86_INS_JMP:
                flow_kind = "direct_unconditional_branch"
                successors = [_hex(target)] if target in body_rvas else []
            else:
                flow_kind = "direct_conditional_branch"
                successors = [
                    *([_hex(fallthrough)] if fallthrough in body_rvas else []),
                    *([_hex(target)] if target in body_rvas else []),
                ]
        elif fallthrough in body_rvas:
            flow_kind, successors = "fallthrough", [_hex(fallthrough)]
        else:
            flow_kind, successors = "range_boundary", []
        edge_count += len(successors)
        nodes.append(
            {**fact, "flow_kind": flow_kind, "successor_rvas": successors}
        )
    graph = {
        "entry_rva": _hex(entry),
        "projection_kind": "single_range_body_local_instruction_cfg_v1",
        "body_local_successor_policy": _SUCCESSOR_POLICY,
        "ranges": [{"start_rva": _hex(entry), "size": size}],
        "nodes": nodes,
        "node_count": len(nodes),
        "edge_count": edge_count,
    }
    if not _same(graph, _expected_graph(spec)):
        _error("decoded body-local CFG differs")
    return graph


def _empty_call_r32_audit() -> list[dict[str, Any]]:
    return [
        {"register": register, "call_rvas": []}
        for register in _REGISTER_NAMES
    ]


def _direct_lua_partition(
    direct_calls: Mapping[str, Any], entry: int
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw_record in _array(direct_calls.get("records"), "direct-call records"):
        record = _mapping(raw_record, "direct-call record")
        if _rva(record.get("entry_rva"), "direct-call entry") != entry:
            continue
        result.extend(
            dict(_mapping(call, "direct Lua call"))
            for call in _array(
                record.get("direct_lua_import_calls"), "direct Lua calls"
            )
        )
    if result:
        _error("direct-callee direct-Lua-call partition differs")
    return result


def _expected_bodies(
    program_facts: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    reviewed_points: Mapping[int, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    functions = _functions(program_facts)
    result: list[dict[str, Any]] = []
    for spec in _BODY_SPECS:
        entry, size, body_sha256, atlas_sha256, points, _branches, _terminals = (
            spec
        )
        function = functions.get(entry)
        if function is None or (
            function.get("body_size"),
            function.get("body_sha256"),
            atlas_record_sha256(function),
        ) != (size, body_sha256, atlas_sha256):
            _error("direct-callee atlas body differs")
        body_points = (
            [_instruction_fact(rva, encoded) for rva, encoded in points]
            if reviewed_points is None
            else reviewed_points[entry]
        )
        graph = _expected_graph(spec)
        result.append(
            {
                "role": "multirange_direct_callee_opaque_static_boundary",
                "entry_rva": _hex(entry),
                "atlas_record_sha256": atlas_sha256,
                "body_size": size,
                "body_sha256": body_sha256,
                "ranges": [
                    {
                        "start_rva": _hex(entry),
                        "size": size,
                        "sha256": body_sha256,
                    }
                ],
                "control_flow_graph_canonical_sha256": _canonical_json_sha256(
                    graph
                ),
                "reviewed_points": body_points,
                "direct_lua_calls": _direct_lua_partition(direct_calls, entry),
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
        )
    return result


def _parent_rows(
    multirange: Mapping[str, Any], program_facts: Mapping[str, Any]
) -> list[dict[str, Any]]:
    rows = [
        dict(_mapping(row, "multirange outgoing edge"))
        for row in _array(
            _mapping(
                multirange.get("native_calls"), "multirange native calls"
            ).get("outgoing_direct"),
            "multirange outgoing edges",
        )
    ]
    rows.sort(
        key=lambda row: _rva(
            _mapping(row.get("instruction"), "parent instruction").get("rva"),
            "parent site",
        )
    )
    if len(rows) != 2:
        _error("multirange parent edge count differs")
    functions = _functions(program_facts)
    declared = _declared_edges(program_facts)
    parent_function = functions.get(_PARENT_ENTRY)
    if parent_function is None or (
        parent_function.get("body_size"),
        parent_function.get("body_sha256"),
        atlas_record_sha256(parent_function),
    ) != (_PARENT_BODY_SIZE, _PARENT_BODY_SHA256, _PARENT_ATLAS_SHA256):
        _error("multirange parent atlas identity differs")
    for row in rows:
        instruction = _mapping(row.get("instruction"), "parent instruction")
        site = _rva(instruction.get("rva"), "parent site")
        target = _rva(row.get("target_entry_rva"), "parent target")
        spec = _SPECS_BY_ENTRY.get(target)
        edge = declared.get(site)
        if spec is None or _PARENT_SITES.get(site) != target or edge is None:
            _error("multirange parent edge partition differs")
        _entry, size, body_sha256, atlas_sha256, _points, _branches, _terminals = (
            spec
        )
        expected_instruction = _instruction_fact(
            site, _PARENT_INSTRUCTIONS[site]
        )
        if (
            row.get("role") != "opaque_declared_direct_edge"
            or row.get("control_encoding") != "e8"
            or not _same(instruction, expected_instruction)
            or _rva(row.get("source_entry_rva"), "parent source")
            != _PARENT_ENTRY
            or row.get("source_body_size") != _PARENT_BODY_SIZE
            or row.get("source_body_sha256") != _PARENT_BODY_SHA256
            or row.get("source_atlas_record_sha256")
            != _PARENT_ATLAS_SHA256
            or row.get("target_body_size") != size
            or row.get("target_body_sha256") != body_sha256
            or row.get("target_atlas_record_sha256") != atlas_sha256
            or not _same(
                row.get("ghidra_declared_direct_edge"),
                _normalized_declared_edge(edge),
            )
        ):
            _error("multirange parent edge identity differs")
    return rows


def _outgoing_rows(program_facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for edge in _declared_edges(program_facts).values():
        source = _rva(edge.get("source_entry_rva"), "outgoing source")
        if source in _TARGETS:
            rows.append(dict(edge))
    if rows:
        _error("direct-callee outgoing direct-edge partition differs")
    return []


def _operand_access(value: int) -> str:
    names = {0: "none", 1: "read", 2: "write", 3: "read_write"}
    if value not in names:
        _error("unsupported operand access mask")
    return names[value]


def _expected_pe_address_operands() -> list[dict[str, Any]]:
    return [
        {
            "role": "typed_pe_address_operand",
            "instruction": _instruction_fact(site, encoded),
            "operand_class": "immediate",
            "operand_index": 0,
            "operand_access": "none",
            "operand_va": _hex(value),
            "operand_rva": _hex(value - _IMAGE_BASE),
            "control_syntax": "declared_conditional_branch_target",
            "section_name": ".text",
            "section_rva": "0x00001000",
            "section_characteristics": "0x60000020",
            "section_writable": False,
            "file_backed": True,
            "contents_or_runtime_behavior_opaque": True,
        }
        for site, (encoded, value) in sorted(_PE_OPERANDS.items())
    ]


def _expected_native_syntax(
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "outgoing_direct": _outgoing_rows(program_facts),
        "opaque_indirect_controls": [],
        "indirect_control_partition_complete": True,
        "pe_address_operands": _expected_pe_address_operands(),
        "pe_address_operand_partition_complete": True,
        "segment_qualified_memory_syntax": [],
        "segment_qualified_memory_partition_complete": True,
        "call_r32_audit": _empty_call_r32_audit(),
        "register_call_partition_complete": True,
    }


def _native_syntax(
    image: Any,
    instruction_sets: Mapping[int, list[Any]],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    import capstone.x86_const as x86

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
    call_r32_sites: dict[str, list[int]] = {
        register: [] for register in _REGISTER_NAMES
    }
    indirect_controls: list[dict[str, Any]] = []
    pe_operands: list[dict[str, Any]] = []
    segment_syntax: list[dict[str, Any]] = []
    for entry in sorted(instruction_sets):
        for instruction in instruction_sets[entry]:
            rva = instruction.address - image.image_base
            raw = bytes(instruction.bytes)
            fact = {
                "rva": _hex(rva),
                "size": instruction.size,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            if instruction.id in {x86.X86_INS_CALL, x86.X86_INS_JMP} and any(
                operand.type in {x86.X86_OP_REG, x86.X86_OP_MEM}
                for operand in instruction.operands
            ):
                indirect_controls.append({"instruction": fact})
            if instruction.id == x86.X86_INS_CALL:
                for operand in instruction.operands:
                    if operand.type != x86.X86_OP_REG:
                        continue
                    register = register_by_capstone.get(operand.reg)
                    if (
                        register is None
                        or len(raw) != 2
                        or raw[0] != 0xFF
                        or raw[1]
                        != 0xD0 + _REGISTER_NAMES.index(register)
                    ):
                        _error("unrecognized register-call encoding")
                    call_r32_sites[register].append(rva)
            for operand_index, operand in enumerate(instruction.operands):
                if (
                    operand.type == x86.X86_OP_MEM
                    and operand.mem.segment != x86.X86_REG_INVALID
                ):
                    segment_syntax.append(
                        {
                            "instruction": fact,
                            "operand_index": operand_index,
                        }
                    )
                    continue
                if operand.type == x86.X86_OP_IMM:
                    value = int(operand.imm) & 0xFFFFFFFF
                    operand_class = "immediate"
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
                section = next(
                    (
                        candidate
                        for candidate in image.sections
                        if candidate.virtual_address
                        <= target_rva
                        < candidate.virtual_address + candidate.virtual_size
                    ),
                    None,
                )
                if section is None:
                    continue
                expected = _PE_OPERANDS.get(rva)
                if expected is None:
                    _error("unreviewed PE-address operand")
                encoded, expected_value = expected
                if (
                    raw != bytes.fromhex(encoded)
                    or operand_class != "immediate"
                    or operand_index != 0
                    or value != expected_value
                ):
                    _error("reviewed PE-address operand syntax differs")
                pe_operands.append(
                    {
                        "role": "typed_pe_address_operand",
                        "instruction": fact,
                        "operand_class": operand_class,
                        "operand_index": operand_index,
                        "operand_access": _operand_access(operand.access),
                        "operand_va": _hex(value),
                        "operand_rva": _hex(target_rva),
                        "control_syntax": "declared_conditional_branch_target",
                        "section_name": section.name,
                        "section_rva": _hex(section.virtual_address),
                        "section_characteristics": _hex(
                            section.characteristics
                        ),
                        "section_writable": bool(
                            section.characteristics & 0x80000000
                        ),
                        "file_backed": image.rva_to_file_offset(target_rva)
                        is not None,
                        "contents_or_runtime_behavior_opaque": True,
                    }
                )
    if indirect_controls:
        _error("indirect-control partition differs")
    if segment_syntax:
        _error("segment-qualified memory partition differs")
    key = lambda row: (
        _rva(row["instruction"]["rva"], "syntax site"),
        row["operand_index"],
    )
    result = {
        "outgoing_direct": _outgoing_rows(program_facts),
        "opaque_indirect_controls": [],
        "indirect_control_partition_complete": True,
        "pe_address_operands": sorted(pe_operands, key=key),
        "pe_address_operand_partition_complete": True,
        "segment_qualified_memory_syntax": [],
        "segment_qualified_memory_partition_complete": True,
        "call_r32_audit": [
            {
                "register": register,
                "call_rvas": [
                    _hex(site) for site in call_r32_sites[register]
                ],
            }
            for register in _REGISTER_NAMES
        ],
        "register_call_partition_complete": True,
    }
    if not _same(result, _expected_native_syntax(program_facts)):
        _error("decoded native syntax partition differs")
    return result


def _reference_record(
    *,
    site: int,
    owner: int,
    target: int,
    raw: bytes,
    operand_index: int,
    functions: Mapping[int, Mapping[str, Any]],
    declared: Mapping[int, Mapping[str, Any]],
    image_base: int,
) -> dict[str, Any]:
    owner_function = functions.get(owner)
    target_function = functions.get(target)
    edge = declared.get(site)
    spec = _SPECS_BY_ENTRY.get(target)
    if (
        owner_function is None
        or target_function is None
        or edge is None
        or spec is None
    ):
        _error("reference atlas or declared-edge join differs")
    expected_raw = bytes((0xE8,)) + int(target - (site + 5)).to_bytes(
        4, "little", signed=True
    )
    if raw != expected_raw or operand_index != 0:
        _error("reference instruction syntax differs")
    if (
        _rva(edge.get("source_entry_rva"), "reference source") != owner
        or _rva(edge.get("target_entry_rva"), "reference target entry")
        != target
        or _rva(edge.get("target_rva"), "reference target") != target
    ):
        _error("reference declared edge differs")
    _entry, size, body_sha256, atlas_sha256, _points, _branches, _terminals = (
        spec
    )
    if (
        target_function.get("body_size"),
        target_function.get("body_sha256"),
        atlas_record_sha256(target_function),
    ) != (size, body_sha256, atlas_sha256):
        _error("reference target atlas identity differs")
    return {
        "instruction_rva": _hex(site),
        "instruction_size": len(raw),
        "instruction_sha256": hashlib.sha256(raw).hexdigest(),
        "owner_entry_rva": _hex(owner),
        "owner_atlas_record_sha256": atlas_record_sha256(owner_function),
        "target_rva": _hex(target),
        "target_atlas_record_sha256": atlas_sha256,
        "target_va": _hex(image_base + target),
        "operand_class": "immediate",
        "operand_index": operand_index,
        "use_class": "direct_call",
        "call_form": "x86_relative_near_call_e8",
        "ghidra_declared_direct_edge": _normalized_declared_edge(edge),
    }


def _scan_receipt(references: list[dict[str, Any]]) -> dict[str, Any]:
    references = sorted(
        references,
        key=lambda row: (
            _rva(row["instruction_rva"], "reference site"),
            row["operand_index"],
        ),
    )
    if len(references) != 2 or {
        _rva(row["target_rva"], "reference target") for row in references
    } != _TARGETS:
        _error("entry-reference partition differs")
    owner_counts: dict[tuple[str, str], int] = {}
    target_owner_counts: dict[tuple[str, str, str], int] = {}
    target_counts: dict[tuple[str, str], int] = {}
    target_owners: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for row in references:
        owner_key = (
            row["owner_entry_rva"],
            row["owner_atlas_record_sha256"],
        )
        target_key = (
            row["target_rva"],
            row["target_atlas_record_sha256"],
        )
        owner_counts[owner_key] = owner_counts.get(owner_key, 0) + 1
        target_counts[target_key] = target_counts.get(target_key, 0) + 1
        target_owners.setdefault(target_key, set()).add(owner_key)
        target_owner_key = (target_key[0], *owner_key)
        target_owner_counts[target_owner_key] = (
            target_owner_counts.get(target_owner_key, 0) + 1
        )
    owner_partition = [
        {
            "owner_entry_rva": owner,
            "owner_atlas_record_sha256": atlas,
            "reference_count": count,
        }
        for (owner, atlas), count in sorted(owner_counts.items())
    ]
    target_partition = [
        {
            "target_rva": target,
            "target_atlas_record_sha256": atlas,
            "reference_count": count,
            "owner_count": len(target_owners[(target, atlas)]),
        }
        for (target, atlas), count in sorted(target_counts.items())
    ]
    target_reference_partition = [
        {
            "target_rva": target,
            "target_atlas_record_sha256": atlas,
            "reference_count": count,
        }
        for (target, atlas), count in sorted(target_counts.items())
    ]
    target_owner_partition = [
        {
            "target_rva": target,
            "owner_entry_rva": owner,
            "owner_atlas_record_sha256": atlas,
            "reference_count": count,
        }
        for (target, owner, atlas), count in sorted(
            target_owner_counts.items()
        )
    ]
    partition_sha256 = {
        "owner_partition": _compact_sha256(owner_partition),
        "target_owner_partition": _compact_sha256(target_owner_partition),
        "target_reference_partition": _compact_sha256(
            target_reference_partition
        ),
    }
    if partition_sha256 != {
        "owner_partition": _PAIR_OWNER_HASH,
        "target_owner_partition": _PAIR_TARGET_OWNER_HASH,
        "target_reference_partition": _PAIR_TARGET_REF_HASH,
    }:
        _error("entry-reference partition identity differs")
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
            "reference_count": len(references),
            "target_count": len(target_partition),
            "owner_count": len(owner_partition),
            "target_owner_count": len(target_owner_partition),
            "direct_call_count": sum(
                row["use_class"] == "direct_call" for row in references
            ),
            "other_address_count": sum(
                row["use_class"] != "direct_call" for row in references
            ),
            "memory_operand_count": sum(
                row["operand_class"] == "absolute_memory"
                for row in references
            ),
        },
    }


def _expected_scan(program_facts: Mapping[str, Any]) -> dict[str, Any]:
    functions = _functions(program_facts)
    declared = _declared_edges(program_facts)
    references = []
    for site, target in sorted(_PARENT_SITES.items()):
        raw = bytes.fromhex(_PARENT_INSTRUCTIONS[site])
        references.append(
            _reference_record(
                site=site,
                owner=_PARENT_ENTRY,
                target=target,
                raw=raw,
                operand_index=0,
                functions=functions,
                declared=declared,
                image_base=_IMAGE_BASE,
            )
        )
    return _scan_receipt(references)


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
        _error("image-base identity differs")
    target_by_va = {image_base + target: target for target in _TARGETS}
    references: list[dict[str, Any]] = []
    range_count = byte_count = instruction_count = 0
    decoder.detail = True
    for owner, function in sorted(functions.items()):
        for raw_span in _array(function.get("ranges"), "atlas ranges"):
            span = _mapping(raw_span, "atlas range")
            start = _rva(span.get("start_rva"), "atlas range start")
            size = span.get("size")
            if type(size) is not int or size <= 0:
                _error("atlas range size differs")
            instructions = _decode_range(data, image, start, size, decoder)
            range_count += 1
            byte_count += size
            instruction_count += len(instructions)
            for instruction in instructions:
                for operand_index, operand in enumerate(instruction.operands):
                    if operand.type == x86.X86_OP_IMM:
                        value = int(operand.imm) & 0xFFFFFFFF
                        operand_class = "immediate"
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
                    target = target_by_va.get(value)
                    if target is None:
                        continue
                    raw = bytes(instruction.bytes)
                    if (
                        operand_class != "immediate"
                        or operand_index != 0
                        or instruction.id != x86.X86_INS_CALL
                        or len(raw) != 5
                        or raw[0] != 0xE8
                    ):
                        _error("unreviewed target-reference syntax")
                    references.append(
                        _reference_record(
                            site=instruction.address - image_base,
                            owner=owner,
                            target=target,
                            raw=raw,
                            operand_index=operand_index,
                            functions=functions,
                            declared=declared,
                            image_base=image_base,
                        )
                    )
    if (range_count, byte_count, instruction_count) != (
        25490,
        3735718,
        1153814,
    ):
        _error("whole-atlas scan scope differs")
    receipt = _scan_receipt(references)
    if not _same(receipt, _expected_scan(program_facts)):
        _error("whole-atlas entry-reference receipt differs")
    return receipt


def _parent_scan_join(
    parents: list[dict[str, Any]], scan: Mapping[str, Any]
) -> None:
    references = [
        _mapping(row, "entry reference")
        for row in _array(scan.get("references"), "entry references")
    ]
    parent_by_site = {
        _rva(
            _mapping(row.get("instruction"), "parent instruction").get(
                "rva"
            ),
            "parent site",
        ): row
        for row in parents
    }
    reference_by_site = {
        _rva(row.get("instruction_rva"), "reference site"): row
        for row in references
    }
    if set(parent_by_site) != set(_PARENT_SITES) or set(reference_by_site) != set(
        _PARENT_SITES
    ):
        _error("parent/reference site partition differs")
    for site in sorted(_PARENT_SITES):
        parent = parent_by_site[site]
        reference = reference_by_site[site]
        instruction = _mapping(parent.get("instruction"), "parent instruction")
        if (
            instruction.get("rva") != reference.get("instruction_rva")
            or instruction.get("size") != reference.get("instruction_size")
            or instruction.get("sha256")
            != reference.get("instruction_sha256")
            or parent.get("source_entry_rva")
            != reference.get("owner_entry_rva")
            or parent.get("source_atlas_record_sha256")
            != reference.get("owner_atlas_record_sha256")
            or parent.get("target_entry_rva") != reference.get("target_rva")
            or parent.get("target_atlas_record_sha256")
            != reference.get("target_atlas_record_sha256")
            or not _same(
                parent.get("ghidra_declared_direct_edge"),
                reference.get("ghidra_declared_direct_edge"),
            )
        ):
            _error("parent/reference join differs")


def _summary() -> dict[str, Any]:
    return {
        "reviewed_target_count": 2,
        "reviewed_target_bytes": 116,
        "sealed_instruction_count": 52,
        "sealed_control_flow_graph_count": 2,
        "sealed_control_flow_graph_node_count": 52,
        "sealed_control_flow_graph_edge_count": 55,
        "native_direct_edge_count": 0,
        "direct_lua_call_count": 0,
        "staged_lua_dispatch_count": 0,
        "call_r32_count": 0,
        "opaque_indirect_control_count": 0,
        "pe_address_operand_count": 6,
        "pe_immediate_operand_count": 6,
        "pe_absolute_memory_operand_count": 0,
        "segment_qualified_memory_syntax_count": 0,
        "multirange_parent_edge_count": 2,
        "target_reference_count": 2,
        "target_reference_target_count": 2,
        "target_reference_owner_count": 1,
        "target_reference_direct_call_count": 2,
        "target_reference_other_address_count": 0,
        "target_reference_memory_operand_count": 0,
        "schema_violations": 0,
    }


def _evidence(
    multirange: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    reviewed_points: Mapping[int, list[dict[str, Any]]] | None = None,
    graphs: list[dict[str, Any]] | None = None,
    native_syntax: Mapping[str, Any] | None = None,
    scan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prerequisites = _preflight(multirange, direct_calls, program_facts)
    expected_graphs = _expected_graphs()
    expected_native = _expected_native_syntax(program_facts)
    expected_scan = _expected_scan(program_facts)
    graph_value = expected_graphs if graphs is None else graphs
    native_value = expected_native if native_syntax is None else dict(native_syntax)
    scan_value = expected_scan if scan is None else dict(scan)
    if (
        not _same(graph_value, expected_graphs)
        or not _same(native_value, expected_native)
        or not _same(scan_value, expected_scan)
    ):
        _error("exact component differs from the sealed structural receipt")
    parents = _parent_rows(multirange, program_facts)
    _parent_scan_join(parents, scan_value)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(
            _mapping(program_facts.get("identity"), "program facts identity")
        ),
        "program_facts": prerequisites["program_facts"],
        "multirange_static_boundary": prerequisites[
            "multirange_static_boundary"
        ],
        "direct_call_census": prerequisites["direct_call_census"],
        "decoder": _decoder_contract(),
        "function_bodies": _expected_bodies(
            program_facts, direct_calls, reviewed_points
        ),
        "control_flow_graphs": graph_value,
        "multirange_parent_edges": parents,
        "native_calls": native_value,
        "whole_atlas_reference_scan": scan_value,
        "method": _METHOD,
        "summary": _summary(),
    }
    _assert_publication_safe(result)
    return result


_NORMALIZED_ERRORS = (
    NativeLuaCClosurePublicationError,
    NativeLuaDirectCallError,
    NativeLuaClassReturnHelperChainError,
    NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError,
    PEAnchorError,
)


def validate_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary_structure(
    evidence: Mapping[str, Any],
    multirange: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate every finite receipt field without opening the executable."""
    try:
        for item, label in (
            (evidence, "evidence"),
            (multirange, "multirange static boundary"),
            (direct_calls, "direct calls"),
            (program_facts, "program facts"),
        ):
            _validate_json_tree(item, label)
        value = _mapping(evidence, "evidence")
        expected = _evidence(multirange, direct_calls, program_facts)
        if not _same(value, expected):
            _error("direct-callee pair receipt differs")
        _assert_publication_safe(value)
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
            "build_identity": dict(value["build_identity"]),
            "evidence_sha256": _canonical_sha256(value),
            "summary": dict(value["summary"]),
        }
    except NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError:
        raise
    except _NORMALIZED_ERRORS as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError(
            str(exc)
        ) from exc


def build_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary(
    executable: Path,
    multirange: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact receipt from the sealed Windows executable."""
    try:
        for item, label in (
            (multirange, "multirange static boundary"),
            (direct_calls, "direct calls"),
            (program_facts, "program facts"),
            (inventory, "inventory"),
        ):
            _validate_json_tree(item, label)
        direct_receipt = validate_native_lua_direct_call_census(
            executable,
            direct_calls,
            program_facts,
            inventory=inventory,
        )
        if (
            direct_receipt.get("status") != "verified"
            or direct_receipt.get("evidence_sha256") != _DIRECT
        ):
            _error("direct-call exact prerequisite differs")
        _preflight(multirange, direct_calls, program_facts)
        data, image, executable_sha256 = _load_executable(executable)
        if executable_sha256 != _EXE:
            _error("sealed executable differs")
        image_base = _rva(
            _mapping(program_facts.get("ghidra"), "ghidra").get(
                "image_base"
            ),
            "image base",
        )
        if image.image_base != image_base or image_base != _IMAGE_BASE:
            _error("image-base identity differs")
        decoder, _call_id = _decoder()
        decoder.detail = True
        instruction_sets: dict[int, list[Any]] = {}
        reviewed_points: dict[int, list[dict[str, Any]]] = {}
        graphs: list[dict[str, Any]] = []
        for spec in _BODY_SPECS:
            entry, size, body_sha256, _atlas, points, _branches, _terminals = (
                spec
            )
            instructions = _decode_range(data, image, entry, size, decoder)
            raw = b"".join(bytes(instruction.bytes) for instruction in instructions)
            if (
                len(raw) != size
                or hashlib.sha256(raw).hexdigest() != body_sha256
                or len(instructions) != len(points)
            ):
                _error("direct-callee body bytes differ")
            reviewed_points[entry] = [
                _decoded_point(
                    instruction,
                    image_base,
                    expected_rva,
                    encoded,
                )
                for instruction, (expected_rva, encoded) in zip(
                    instructions, points
                )
            ]
            instruction_sets[entry] = instructions
            graphs.append(_local_graph(spec, instructions, image_base))
        native_syntax = _native_syntax(
            image, instruction_sets, program_facts
        )
        scan = _scan(data, image, decoder, program_facts)
        result = _evidence(
            multirange,
            direct_calls,
            program_facts,
            reviewed_points=reviewed_points,
            graphs=graphs,
            native_syntax=native_syntax,
            scan=scan,
        )
        if _load_executable(executable)[2] != executable_sha256:
            _error("executable changed during exact reconstruction")
        validate_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary_structure(
            result, multirange, direct_calls, program_facts
        )
        return result
    except NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError:
        raise
    except (*_NORMALIZED_ERRORS, OSError) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError(
            str(exc)
        ) from exc


def validate_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary(
    executable: Path,
    evidence: Mapping[str, Any],
    multirange: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and verify the exact receipt."""
    try:
        _validate_json_tree(evidence, "evidence")
        rebuilt = build_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary(
            executable,
            multirange,
            direct_calls,
            program_facts,
            inventory=inventory,
        )
        if not _same(evidence, rebuilt):
            _error("evidence differs from exact reconstruction")
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": VERIFICATION_KIND,
            "status": "verified",
            "build_identity": dict(rebuilt["build_identity"]),
            "evidence_sha256": _canonical_sha256(rebuilt),
            "summary": dict(rebuilt["summary"]),
        }
    except NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError:
        raise
    except (*_NORMALIZED_ERRORS, OSError) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError(
            str(exc)
        ) from exc


def encode_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary(
    value: Mapping[str, Any],
) -> str:
    try:
        _validate_json_tree(value, "encoded value")
        document = _mapping(value, "encoded value")
        return json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        ) + "\n"
    except NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError:
        raise
    except (*_NORMALIZED_ERRORS, TypeError, ValueError) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError(
            str(exc)
        ) from exc
