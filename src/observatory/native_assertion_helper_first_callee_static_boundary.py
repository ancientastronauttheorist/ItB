"""Fail-closed static receipt for assertion-helper callee ``0x0038e392``.

This is a finite syntactic boundary.  The Ghidra name ``__set_error_mode`` is
retained as metadata only; it does not establish source identity or behaviour.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_setfield_publications import (
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _decode_range,
    _hex,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_class_return_helper_chain import (
    _REGISTER_NAMES,
    _canonical_bytes,
    _canonical_sha256,
    _enhanced_cfg,
    _source_identity,
    _with_edi_writes,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_KIND,
    SUPPORTED_CAPSTONE_VERSION,
    _decoder,
    _load_executable,
    validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_assertion_helper_static_boundary import (
    ANALYSIS_KIND as PREDECESSOR_KIND,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_assertion_helper_first_callee_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_PREDECESSOR = "beeebb2dadd0ef2a77742f9296760fd09afe5c566c7b46bf36d2dd3cf8e441b4"
_BASE, _ENTRY, _SIZE = 0x400000, 0x38E392, 63
_RAW = "8bff558bec8b4d0885c9781e83f9027e0c83f9037514a134758b005dc3a134758b00890d34758b005dc3e80b78ffffc70016000000e826bbfeff83c8ff5dc3"
_BODY = "9ccce0d1b341bdf834edec2dc6c9626c73f97a7e4df7917e4c7d202ae906039d"
_ATLAS = "4608b7afb2563887aeb78c99d4dfddc8af5cb60e146f46104b94c6dc919d7efd"
_CFG = "f47565f73f6bf3721d4d6a4bc73dfafbe570574da654e0bed72ea49d39368843"
_PARENT = (
    0x379CCD,
    0x379CC2,
    "e8c0460100",
    "0103f8a5b002b70e110ee0031538326b0eeb59da2cc798607a62a5603e04ac29",
)
_OUTGOING = ((0x38E3BC, 0x385BCC, "e80b78ffff"), (0x38E3C7, 0x379EF2, "e826bbfeff"))
_RELOCATION_DIRECTORY = (
    0x539000,
    0x35618,
    0x510A00,
    "06630f9047636fb68afba81d89dbc1ef2f21c459b684d57d1d2bcaeb3750dfa3",
)
_SCOPE = {
    "atlas_function_count": 25312,
    "atlas_body_range_count": 25490,
    "decoded_bytes": 3735718,
    "decoded_instructions": 1153814,
    "all_declared_ranges_decoded": True,
    "operand_classes": ["absolute_memory", "immediate"],
}


class NativeAssertionHelperFirstCalleeStaticBoundaryError(RuntimeError):
    """Raised when the finite first-callee receipt cannot be reproduced."""


def _bad(message: str) -> None:
    raise NativeAssertionHelperFirstCalleeStaticBoundaryError(message)


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _compact(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _instruction(rva: int, encoded: str) -> dict[str, Any]:
    raw = bytes.fromhex(encoded)
    return {
        "rva": _hex(rva),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _empty_register_calls() -> list[dict[str, Any]]:
    return [{"register": register, "call_rvas": []} for register in _REGISTER_NAMES]


def _edges(facts: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for raw in _array(
        facts.get("ghidra_declared_direct_calls"), "declared direct calls"
    ):
        edge = _mapping(raw, "declared direct edge")
        site = _rva(edge.get("instruction_rva"), "declared direct site")
        if site in result:
            _bad("duplicate declared direct-call site")
        result[site] = edge
    return result


def _normalized_edge(edge: Mapping[str, Any]) -> dict[str, Any]:
    name = edge.get("target_name")
    if type(name) is not str:
        _bad("declared direct edge lacks analysis label")
    return {
        "instruction_rva": _hex(_rva(edge.get("instruction_rva"), "edge site")),
        "source_entry_rva": _hex(_rva(edge.get("source_entry_rva"), "edge source")),
        "target_entry_rva": _hex(
            _rva(edge.get("target_entry_rva"), "edge target entry")
        ),
        "target_rva": _hex(_rva(edge.get("target_rva"), "edge target")),
        "target_name_sha256": hashlib.sha256(name.encode()).hexdigest(),
    }


def _decode(raw: bytes = bytes.fromhex(_RAW)) -> list[Any]:
    decoder, _ = _decoder()
    decoder.detail = True
    rows = list(decoder.disasm(raw, _BASE + _ENTRY))
    if len(rows) != 23 or b"".join(bytes(row.bytes) for row in rows) != raw:
        _bad("sealed target bytes do not decode exactly")
    return rows


def _points(rows: list[Any]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        _, writes = row.regs_access()
        names = {row.reg_name(register).lower() for register in writes}
        raw = bytes(row.bytes)
        result.append(
            {
                "rva": _hex(row.address - _BASE),
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "writes_ebx": "ebx" in names,
                "writes_esi": "esi" in names,
                "writes_edi": "edi" in names,
                "writes_esp": "esp" in names,
            }
        )
    return result


def _graph(rows: list[Any] | None = None) -> dict[str, Any]:
    import capstone
    import capstone.x86_const as x86

    decoded = _decode() if rows is None else rows
    graph = _with_edi_writes(
        _enhanced_cfg(decoded, _BASE, (_ENTRY, _SIZE), capstone, x86), decoded, x86
    )
    graph["caller_entry_rva"] = _hex(_ENTRY)
    if (graph.get("node_count"), graph.get("edge_count"), _canonical_sha256(graph)) != (
        23,
        23,
        _CFG,
    ):
        _bad("sealed target control-flow graph differs")
    return graph


def _preflight(
    predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]
) -> dict[str, Any]:
    identity = dict(_mapping(facts.get("identity"), "program facts identity"))
    if identity.get("executable_sha256") != _EXE:
        _bad("program facts executable differs")
    if not _same(predecessor.get("build_identity"), identity) or not _same(
        direct.get("build_identity"), identity
    ):
        _bad("prerequisite build identity differs")
    if (
        predecessor.get("analysis_kind") != PREDECESSOR_KIND
        or _canonical_sha256(predecessor) != _PREDECESSOR
    ):
        _bad("assertion-helper predecessor receipt differs")
    summary = _mapping(facts.get("summary"), "program facts summary")
    return {
        "program_facts": {
            **_source_identity(
                facts, "pe_ghidra_program_facts", _FACTS, "program facts"
            ),
            "function_count": summary.get("function_count"),
            "body_range_count": summary.get("body_range_count"),
            "function_body_bytes": summary.get("function_body_bytes"),
        },
        "predecessor_static_boundary": _source_identity(
            predecessor, PREDECESSOR_KIND, _PREDECESSOR, "assertion-helper predecessor"
        ),
        "direct_call_census": _source_identity(
            direct, DIRECT_KIND, _DIRECT, "direct-call census"
        ),
    }


def _target_function(facts: Mapping[str, Any]) -> Mapping[str, Any]:
    function = _atlas_functions(facts).get(_ENTRY)
    if function is None or (
        function.get("body_size"),
        function.get("body_sha256"),
        atlas_record_sha256(function),
    ) != (_SIZE, _BODY, _ATLAS):
        _bad("target atlas record differs")
    return function


def _parent_edge(predecessor: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        dict(_mapping(raw, "predecessor direct edge"))
        for raw in _array(predecessor.get("native_edges"), "predecessor native edges")
    ]
    matches = [
        row
        for row in rows
        if _rva(
            _mapping(row.get("instruction"), "parent instruction").get("rva"),
            "parent site",
        )
        == _PARENT[0]
        and _rva(row.get("source_entry_rva"), "parent source") == _PARENT[1]
        and _rva(row.get("target_entry_rva"), "parent target") == _ENTRY
    ]
    if len(rows) != 4 or len(matches) != 1:
        _bad("assertion-helper parent edge differs")
    parent = matches[0]
    if parent.get("source_atlas_record_sha256") != _PARENT[3] or not _same(
        parent.get("instruction"), _instruction(_PARENT[0], _PARENT[2])
    ):
        _bad("assertion-helper parent instruction differs")
    return matches


def _native_calls(facts: Mapping[str, Any], image: Any | None = None) -> dict[str, Any]:
    """Account exactly for target calls, PE operands, and non-PE literals."""
    _target_function(facts)
    edges = _edges(facts)
    outgoing = []
    for site, target, encoded in _OUTGOING:
        edge = edges.get(site)
        if edge is None or (
            _rva(edge.get("source_entry_rva"), "outgoing source"),
            _rva(edge.get("target_entry_rva"), "outgoing target entry"),
            _rva(edge.get("target_rva"), "outgoing target"),
        ) != (_ENTRY, target, target):
            _bad("outgoing native direct-edge partition differs")
        function = _atlas_functions(facts).get(target)
        if function is None:
            _bad("outgoing target atlas record missing")
        outgoing.append(
            {
                "role": "opaque_native_direct_edge",
                "instruction": _instruction(site, encoded),
                "source_entry_rva": _hex(_ENTRY),
                "target_entry_rva": _hex(target),
                "target_rva": _hex(target),
                "target_atlas_record_sha256": atlas_record_sha256(function),
                "callee_behavior_opaque": True,
                "ghidra_declared_direct_edge": _normalized_edge(edge),
            }
        )
    source_sites = {
        site
        for site, edge in edges.items()
        if _rva(edge.get("source_entry_rva"), "declared direct source") == _ENTRY
    }
    if source_sites != {site for site, _, _ in _OUTGOING}:
        _bad("outgoing native direct edge census differs")
    pe_operands = []
    for site, encoded, access in (
        (0x38E3A8, "a134758b00", "read"),
        (0x38E3AF, "a134758b00", "read"),
        (0x38E3B4, "890d34758b00", "write"),
    ):
        pe_operands.append(
            {
                "role": "opaque_absolute_memory_" + access + "_syntax",
                "instruction": _instruction(site, encoded),
                "operand_class": "absolute_memory",
                "operand_index": 1 if site != 0x38E3B4 else 0,
                "operand_access": access,
                "operand_va": "0x008b7534",
                "operand_rva": "0x004b7534",
                "section_name": ".data",
                "section_rva": "0x00492000",
                "section_characteristics": "0xc0000040",
                "section_writable": True,
                "section_virtual_size": "0x000471cc",
                "section_raw_size": "0x00024800",
                "section_raw_offset": "0x00490200",
                "file_backed": False,
                "file_offset": None,
                "contents_or_runtime_behavior_opaque": True,
            }
        )
    if image is not None:
        rva = 0x4B7534
        section = next(
            (
                row
                for row in image.sections
                if row.virtual_address <= rva < row.virtual_address + row.virtual_size
            ),
            None,
        )
        if section is None or (
            section.name,
            section.virtual_address,
            section.characteristics,
            section.virtual_size,
            section.raw_size,
            section.raw_offset,
        ) != (".data", 0x492000, 0xC0000040, 0x471CC, 0x24800, 0x490200):
            _bad("virtual-only PE-address section binding differs")
        if image.rva_to_file_offset(rva) is not None:
            _bad("virtual-only PE-address unexpectedly has file offset")
        directory_rva, directory_size, directory_offset, directory_sha256 = (
            _RELOCATION_DIRECTORY
        )
        if (
            image.bits != 32
            or len(image.data_directories) <= 5
            or image.data_directories[5] != (directory_rva, directory_size)
        ):
            _bad("base-relocation directory differs")
        if (
            image.rva_span_to_file_offset(directory_rva, directory_size)
            != directory_offset
            or hashlib.sha256(
                image.data[directory_offset : directory_offset + directory_size]
            ).hexdigest()
            != directory_sha256
        ):
            _bad("base-relocation directory backing differs")
        sites, cursor, end = [], directory_offset, directory_offset + directory_size
        while cursor < end:
            page, size = struct.unpack_from("<II", image.data, cursor)
            if size < 8 or cursor + size > end:
                _bad("base-relocation block malformed")
            for at in range(cursor + 8, cursor + size, 2):
                entry = struct.unpack_from("<H", image.data, at)[0]
                if entry >> 12 == 3:
                    site = page + (entry & 0xFFF)
                    if _ENTRY <= site < _ENTRY + _SIZE:
                        file_offset = image.rva_span_to_file_offset(site, 4)
                        if file_offset is None:
                            _bad("HIGHLOW relocation site is not file-backed")
                        sites.append(
                            (
                                site,
                                at,
                                file_offset,
                                struct.unpack_from("<I", image.data, file_offset)[0],
                                image.data[at : at + 2].hex(),
                            )
                        )
            cursor += size
        if cursor != end or sites != [
            (0x38E3A9, 0x5334CE, 0x38D7A9, 0x8B7534, "a933"),
            (0x38E3B0, 0x5334D0, 0x38D7B0, 0x8B7534, "b033"),
            (0x38E3B6, 0x5334D2, 0x38D7B6, 0x8B7534, "b633"),
        ]:
            _bad("base-relocation operand frontier differs")
    literals = [
        {
            "role": "opaque_comparison_literal",
            "instruction": _instruction(0x38E39E, "83f902"),
            "operand_index": 1,
            "value_u32": "0x00000002",
        },
        {
            "role": "opaque_comparison_literal",
            "instruction": _instruction(0x38E3A3, "83f903"),
            "operand_index": 1,
            "value_u32": "0x00000003",
        },
        {
            "role": "opaque_data_literal",
            "instruction": _instruction(0x38E3C1, "c70016000000"),
            "operand_index": 1,
            "value_u32": "0x00000016",
        },
        {
            "role": "opaque_data_literal",
            "instruction": _instruction(0x38E3CC, "83c8ff"),
            "operand_index": 1,
            "value_u32": "0xffffffff",
        },
    ]
    return {
        "outgoing_direct": outgoing,
        "outgoing_direct_partition_complete": True,
        "direct_lua_calls": [],
        "direct_lua_partition_complete": True,
        "staged_lua_dispatches": [],
        "staged_lua_dispatch_partition_complete": True,
        "opaque_indirect_controls": [],
        "indirect_control_partition_complete": True,
        "pe_address_operands": pe_operands,
        "pe_address_operand_partition_complete": True,
        "non_pe_immediate_literals": literals,
        "non_pe_immediate_literal_partition_complete": True,
        "segment_qualified_memory_syntax": [],
        "segment_qualified_memory_partition_complete": True,
        "bnd_prefixed_control_syntax": [],
        "bnd_prefixed_control_partition_complete": True,
        "opaque_interrupt_syntax": [],
        "opaque_interrupt_partition_complete": True,
        "call_r32_audit": _empty_register_calls(),
        "register_call_partition_complete": True,
        "base_relocation_scan": {
            "directory": {
                "rva": _hex(_RELOCATION_DIRECTORY[0]),
                "size": _RELOCATION_DIRECTORY[1],
                "file_offset": _hex(_RELOCATION_DIRECTORY[2]),
                "sha256": _RELOCATION_DIRECTORY[3],
            },
            "highlow_site_count_inside_body": 3,
            "highlow_sites": [
                {
                    "site_rva": _hex(site),
                    "file_offset": _hex(file),
                    "entry_file_offset": _hex(entry),
                    "entry_raw": raw,
                    "type": "HIGHLOW",
                    "value_va": _hex(value),
                    "value_rva": _hex(value - _BASE),
                }
                for site, entry, file, value, raw in [
                    (0x38E3A9, 0x5334CE, 0x38D7A9, 0x8B7534, "a933"),
                    (0x38E3B0, 0x5334D0, 0x38D7B0, 0x8B7534, "b033"),
                    (0x38E3B6, 0x5334D2, 0x38D7B6, 0x8B7534, "b633"),
                ]
            ],
        },
    }


def _expected_scan(facts: Mapping[str, Any]) -> dict[str, Any]:
    functions, edges = _atlas_functions(facts), _edges(facts)
    edge, owner = edges.get(_PARENT[0]), functions.get(_PARENT[1])
    if (
        edge is None
        or owner is None
        or (
            _rva(edge.get("source_entry_rva"), "reference source"),
            _rva(edge.get("target_entry_rva"), "reference target"),
            _rva(edge.get("target_rva"), "reference target"),
        )
        != (_PARENT[1], _ENTRY, _ENTRY)
    ):
        _bad("incoming frontier facts differ")
    records = [
        {
            "instruction_rva": _hex(_PARENT[0]),
            "instruction_size": 5,
            "instruction_sha256": hashlib.sha256(bytes.fromhex(_PARENT[2])).hexdigest(),
            "owner_entry_rva": _hex(_PARENT[1]),
            "owner_atlas_record_sha256": atlas_record_sha256(owner),
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "target_va": _hex(_BASE + _ENTRY),
            "operand_class": "immediate",
            "operand_index": 0,
            "use_class": "direct_call",
            "call_form": "x86_relative_near_call_e8",
            "ghidra_declared_direct_edge": _normalized_edge(edge),
        }
    ]
    target_partition = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 1,
            "owner_count": 1,
        }
    ]
    owners = [
        {
            "owner_entry_rva": _hex(_PARENT[1]),
            "owner_atlas_record_sha256": atlas_record_sha256(owner),
            "reference_count": 1,
        }
    ]
    target_owner = [{"target_rva": _hex(_ENTRY), **owners[0]}]
    target_reference = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 1,
        }
    ]
    hashes = {
        "target_partition": _compact(target_partition),
        "owner_partition": _compact(owners),
        "target_owner_partition": _compact(target_owner),
        "target_reference_partition": _compact(target_reference),
    }
    return {
        "target_rvas": [_hex(_ENTRY)],
        "target_vas": [_hex(_BASE + _ENTRY)],
        "scope": dict(_SCOPE),
        "references": records,
        "target_partition": target_partition,
        "owner_partition": owners,
        "target_owner_partition": target_owner,
        "target_reference_partition": target_reference,
        "partition_sha256": hashes,
        "references_canonical_sha256": _compact(records),
        "aggregates": {
            "reference_count": 1,
            "target_count": 1,
            "owner_count": 1,
            "target_owner_count": 1,
            "direct_call_count": 1,
            "comparison_count": 0,
            "other_address_count": 0,
            "memory_operand_count": 0,
        },
    }


def _whole_atlas_reference_scan(
    data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]
) -> dict[str, Any]:
    import capstone.x86_const as x86

    found, totals, target_va = [], [0, 0, 0], image.image_base + _ENTRY
    decoder.detail = True
    for owner, function in sorted(_atlas_functions(facts).items()):
        for raw_range in _array(function.get("ranges"), "atlas range"):
            span = _mapping(raw_range, "atlas range")
            start, size = _rva(span.get("start_rva"), "range start"), span.get("size")
            if type(size) is not int or size <= 0:
                _bad("invalid atlas range")
            rows = _decode_range(data, image, start, size, decoder)
            totals[0] += 1
            totals[1] += size
            totals[2] += len(rows)
            for row in rows:
                for index, operand in enumerate(row.operands):
                    kind = value = None
                    if operand.type == x86.X86_OP_IMM:
                        kind, value = "immediate", int(operand.imm) & 0xFFFFFFFF
                    elif (
                        operand.type == x86.X86_OP_MEM
                        and operand.mem.segment == x86.X86_REG_INVALID
                        and operand.mem.base == x86.X86_REG_INVALID
                        and operand.mem.index == x86.X86_REG_INVALID
                    ):
                        kind, value = (
                            "absolute_memory",
                            int(operand.mem.disp) & 0xFFFFFFFF,
                        )
                    if value == target_va:
                        found.append(
                            (
                                row.address - image.image_base,
                                owner,
                                index,
                                bytes(row.bytes),
                                kind,
                            )
                        )
    if tuple(totals) != (25490, 3735718, 1153814) or found != [
        (_PARENT[0], _PARENT[1], 0, bytes.fromhex(_PARENT[2]), "immediate")
    ]:
        _bad("all-operand target reference traversal differs")
    return _expected_scan(facts)


def _evidence(
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    rows: list[Any] | None = None,
    image: Any | None = None,
    scan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prerequisites = _preflight(predecessor, direct, facts)
    decoded = _decode() if rows is None else rows
    raw = b"".join(bytes(row.bytes) for row in decoded)
    if raw != bytes.fromhex(_RAW) or hashlib.sha256(raw).hexdigest() != _BODY:
        _bad("target body bytes differ")
    _target_function(facts)
    expected = _expected_scan(facts)
    supplied = expected if scan is None else dict(scan)
    if not _same(supplied, expected):
        _bad("target reference receipt differs")
    parent = _parent_edge(predecessor)
    if not any(
        row["instruction_rva"] == parent[0]["instruction"]["rva"]
        for row in supplied["references"]
    ):
        _bad("parent edge does not join exhaustive reference scan")
    body = {
        "role": "relationship_defined_assertion_helper_first_callee_static_boundary",
        "entry_rva": _hex(_ENTRY),
        "atlas_record_sha256": _ATLAS,
        "body_size": _SIZE,
        "body_sha256": _BODY,
        "range_start_rva": _hex(_ENTRY),
        "range_size": _SIZE,
        "control_flow_graph_canonical_sha256": _CFG,
        "reviewed_points": _points(decoded),
        "direct_lua_calls": [],
        "staged_lua_dispatches": [],
        "call_r32_audit": _empty_register_calls(),
        "register_call_partition_complete": True,
        "ghidra_analysis_metadata": {
            "name": "__set_error_mode",
            "namespace": "Global",
            "name_source": "ANALYSIS",
            "thunk": False,
            "metadata_only": True,
        },
        "semantic_facts": {
            "relationship_defined_only": True,
            "analysis_labels_opaque": True,
            "source_semantic_names_assigned": False,
            "runtime_or_success_claimed": False,
        },
    }
    calls = _native_calls(facts, image)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(
            _mapping(facts.get("identity"), "program facts identity")
        ),
        **prerequisites,
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "sealed_instruction_count": 23,
            "register_call_encoding_audit": [
                {"register": register, "encoding": f"ff{0xD0 + index:02x}"}
                for index, register in enumerate(_REGISTER_NAMES)
            ],
        },
        "function_body": body,
        "control_flow_graph": _graph(decoded),
        "predecessor_parent_edges": parent,
        "native_calls": calls,
        "whole_atlas_reference_scan": supplied,
        "method": {
            "structural_boundary": "The receipt seals 63 decoded PE bytes, three virtual-only .data address operands, two opaque direct callee edges, one predecessor edge, and the all-atlas finite reference partition.",
            "not_claimed": [
                "analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return",
                "runtime reachability, invocation, ordering, frequency, or effects",
                "contents or runtime meaning of the virtual-only PE-address operands",
                "computed, indirect, data, un-atlased, dynamic, or Lua-side references",
            ],
        },
        "summary": {
            "reviewed_target_count": 1,
            "reviewed_target_bytes": _SIZE,
            "sealed_instruction_count": 23,
            "sealed_control_flow_graph_count": 1,
            "sealed_control_flow_graph_node_count": 23,
            "sealed_control_flow_graph_edge_count": 23,
            "native_direct_edge_count": 2,
            "direct_lua_call_count": 0,
            "staged_lua_dispatch_count": 0,
            "call_r32_count": 0,
            "opaque_indirect_control_count": 0,
            "bnd_prefixed_control_syntax_count": 0,
            "segment_qualified_memory_syntax_count": 0,
            "opaque_interrupt_syntax_count": 0,
            "non_pe_immediate_literal_count": 4,
            "pe_address_operand_count": 3,
            "target_reference_count": 1,
            "target_reference_owner_count": 1,
            "target_reference_direct_call_count": 1,
            "target_reference_memory_operand_count": 0,
            "target_reference_other_address_count": 0,
            "schema_violations": 0,
        },
    }


def _normalize(operation: Any) -> Any:
    try:
        return operation()
    except NativeAssertionHelperFirstCalleeStaticBoundaryError:
        raise
    except Exception as exc:
        raise NativeAssertionHelperFirstCalleeStaticBoundaryError(str(exc)) from exc


def build_native_assertion_helper_first_callee_static_boundary(
    executable: Path,
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        for value, label in (
            (predecessor, "predecessor"),
            (direct, "direct"),
            (facts, "facts"),
            (inventory, "inventory"),
        ):
            _validate_json_tree(value, label)
        prerequisite = validate_native_lua_direct_call_census(
            executable, direct, facts, inventory=inventory
        )
        if (
            prerequisite.get("status") != "verified"
            or prerequisite.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct-call exact prerequisite failed")
        data, image, digest = _load_executable(executable)
        if digest != _EXE or image.image_base != _BASE:
            _bad("executable identity or image base differs")
        offset = image.rva_to_file_offset(_ENTRY)
        if offset is None or data[offset : offset + _SIZE] != bytes.fromhex(_RAW):
            _bad("executable target bytes differ")
        decoder, _ = _decoder()
        result = _evidence(
            predecessor,
            direct,
            facts,
            rows=_decode(data[offset : offset + _SIZE]),
            image=image,
            scan=_whole_atlas_reference_scan(data, image, decoder, facts),
        )
        replay, replay_image, replay_digest = _load_executable(executable)
        if (
            replay_digest != digest
            or replay != data
            or replay_image.image_base != _BASE
        ):
            _bad("executable changed during exact rebuild")
        _assert_publication_safe(result)
        validate_native_assertion_helper_first_callee_static_boundary_structure(
            result, predecessor, direct, facts
        )
        return result

    return _normalize(run)


def encode_native_assertion_helper_first_callee_static_boundary(
    value: Mapping[str, Any],
) -> str:
    def run() -> str:
        _validate_json_tree(value)
        return (
            json.dumps(
                _mapping(value, "encoded evidence"),
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        )

    return _normalize(run)


def validate_native_assertion_helper_first_callee_static_boundary_structure(
    evidence: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence)
        prerequisite = validate_native_lua_direct_call_structure(direct, facts)
        if (
            prerequisite.get("status") != "structurally_verified"
            or prerequisite.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct-call structural prerequisite failed")
        expected = _evidence(predecessor, direct, facts)
        if not _same(evidence, expected):
            _bad("evidence structure differs")
        _assert_publication_safe(evidence)
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
            "build_identity": dict(evidence["build_identity"]),
            "evidence_sha256": _canonical_sha256(evidence),
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def validate_native_assertion_helper_first_callee_static_boundary(
    executable: Path,
    evidence: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        rebuilt = build_native_assertion_helper_first_callee_static_boundary(
            executable, predecessor, direct, facts, inventory=inventory
        )
        if not _same(evidence, rebuilt):
            _bad("evidence differs from exact rebuild")
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": VERIFICATION_KIND,
            "status": "verified",
            "build_identity": dict(rebuilt["build_identity"]),
            "evidence_sha256": _canonical_sha256(rebuilt),
            "summary": dict(rebuilt["summary"]),
        }

    return _normalize(run)
