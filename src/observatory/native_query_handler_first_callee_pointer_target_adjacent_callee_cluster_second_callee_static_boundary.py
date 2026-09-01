"""Fail-closed, relationship-only receipt for the 0x00378a15 boundary.

Decoded names, the pointed-to .data bytes, and all runtime effects are opaque.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capstone import CsError

from src.observatory.native_function_accounting import atlas_record_sha256
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
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError,
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
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
    validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary import (
    ANALYSIS_KIND as PARENT_KIND,
)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_PARENT = "1385ca599a7442b2b18a45206619d520b19db1b5a2fa9c0ba5b54908831462a5"
_BASE, _ENTRY, _SIZE = 0x400000, 0x378A15, 31
_RAW = "5351bb104089008b4c240c894b08894304896b0c55515058595d595bc20400"
_BODY = "bfc32dca1a2879c053683385362acc34071b244f56f0724b2ec96d15f6660f29"
_ATLAS = "6bf2ee0e68ff7a0c12250248e928bae616b939421135f8b679081c4903dedb81"
_CFG = "9fec8dae3918120b17c438e6c896f550f702743cb60aa00d0739d8d07eee19c8"
_SCOPE = {
    "atlas_function_count": 25312,
    "atlas_body_range_count": 25490,
    "decoded_bytes": 3735718,
    "decoded_instructions": 1153814,
    "all_declared_ranges_decoded": True,
    "operand_classes": ["absolute_memory", "immediate"],
}
_REFS = (
    (
        0x3788CA,
        0x378840,
        "e846010000",
        "fb7ccdd6763c0e720899e85d14807536fed151f65b66ce0bb2a7aa4f91ff767b",
    ),
    (
        0x3789C7,
        0x378965,
        "e849000000",
        "0a78954b488836ef11c4da3d936c0b1092ab9512612c03eabf47f90f9846a7fd",
    ),
    (
        0x378AAE,
        0x378A40,
        "e862ffffff",
        "e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6",
    ),
    (
        0x378B5D,
        0x378B55,
        "e8b3feffff",
        "0bf347712ab1049e562b947e0a83c7669425e76e910aab6096bb42c8a45f2c46",
    ),
)
_PARTITION_HASHES = {
    "owner_partition": "4ec747cbb3416a336274ee482913be42cf18ad433eabcfc7339b48bce34cbd01",
    "target_partition": "ddab461107301c99db244447800a5e59ff9faaa2bf42dee1446cd2655b134095",
    "target_owner_partition": "5ab926089665f431ff6ab1230d0ef65977150b1eae6313b7b32880fc4dda77e9",
    "target_reference_partition": "e8bd69844e27c8a19fee57414069e0a41aa753c154329b2763dd6ce1f91a682e",
}
_REFERENCE_HASH = "710293d9580c982b95f0f00095fc0b51478ba10710dcbc72c6ab48fdc4eb2912"


class NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterSecondCalleeStaticBoundaryError(
    RuntimeError
):
    """Raised when this bounded static receipt cannot be reproduced."""


def _bad(message: str) -> None:
    raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterSecondCalleeStaticBoundaryError(
        message
    )


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _compact(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _instruction(rva: int, raw: str) -> dict[str, Any]:
    blob = bytes.fromhex(raw)
    return {
        "rva": _hex(rva),
        "size": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
    }


def _audit() -> list[dict[str, Any]]:
    return [{"register": r, "call_rvas": []} for r in _REGISTER_NAMES]


def _edges(facts: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result = {}
    for raw in _array(
        facts.get("ghidra_declared_direct_calls"), "declared direct calls"
    ):
        edge = _mapping(raw, "declared direct call")
        site = _rva(edge.get("instruction_rva"), "direct site")
        if site in result:
            _bad("duplicate declared direct-call site")
        result[site] = edge
    return result


def _normalized_edge(edge: Mapping[str, Any]) -> dict[str, Any]:
    name = edge.get("target_name")
    if type(name) is not str:
        _bad("direct edge lacks analysis label")
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
    if len(rows) != 16 or b"".join(bytes(row.bytes) for row in rows) != raw:
        _bad("sealed target bytes do not decode exactly")
    return rows


def _points(rows: list[Any]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        _, writes = row.regs_access()
        names = {row.reg_name(reg).lower() for reg in writes}
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
        16,
        15,
        _CFG,
    ):
        _bad("sealed target control-flow graph differs")
    return graph


def _preflight(
    parent: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]
) -> dict[str, Any]:
    identity = dict(_mapping(facts.get("identity"), "program facts identity"))
    if (
        identity.get("executable_sha256") != _EXE
        or not _same(parent.get("build_identity"), identity)
        or not _same(direct.get("build_identity"), identity)
    ):
        _bad("prerequisite build identity differs")
    if (
        parent.get("analysis_kind") != PARENT_KIND
        or _canonical_sha256(parent) != _PARENT
    ):
        _bad("adjacent-cluster parent receipt differs")
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
            parent, PARENT_KIND, _PARENT, "adjacent-callee cluster parent"
        ),
        "direct_call_census": _source_identity(
            direct, DIRECT_KIND, _DIRECT, "direct-call census"
        ),
    }


def _target(facts: Mapping[str, Any]) -> Mapping[str, Any]:
    value = _atlas_functions(facts).get(_ENTRY)
    if value is None or (
        value.get("body_size"),
        value.get("body_sha256"),
        atlas_record_sha256(value),
        value.get("name"),
        value.get("namespace"),
        value.get("name_source"),
        value.get("thunk"),
    ) != (_SIZE, _BODY, _ATLAS, "__NLG_Notify", "Global", "ANALYSIS", False):
        _bad("target atlas record differs")
    if not _same(value.get("ranges"), [{"start_rva": _hex(_ENTRY), "size": _SIZE}]):
        _bad("target atlas range differs")
    return value


def _adjacent_atlas_boundaries(facts: Mapping[str, Any]) -> dict[str, Any]:
    functions = _atlas_functions(facts)
    expected = (
        (
            "left_neighbor",
            0x378A0C,
            9,
            "3adaebd7a6e3333191b0d25f6af32460be67c90b5766d097d07a0e3b448c01aa",
            "da5650027fe8f4b49d9bd6fed0fbe3022c9335833f0e0f7883963ecb782b5a78",
            "__NLG_Notify1",
            "ANALYSIS",
        ),
        (
            "right_neighbor",
            0x378A34,
            3,
            "94abb6fadbcdb595e2ba8c9a673e591fec8944a2eb04edee55a9ecc56b893047",
            "28e6f200d780328c2667ced90607e5aa26165fa2b59903ba8ae560419766abd1",
            "FUN_00778a34",
            "DEFAULT",
        ),
    )
    result: dict[str, Any] = {
        "layout_only": True,
        "semantic_kinship_claimed": False,
        "left_ends_at_target": True,
        "target_ends_at_right": True,
    }
    for role, entry, size, body_sha256, atlas_sha256, name, name_source in expected:
        function = functions.get(entry)
        if function is None or (
            function.get("body_size"),
            function.get("body_sha256"),
            atlas_record_sha256(function),
            function.get("name"),
            function.get("namespace"),
            function.get("name_source"),
            function.get("thunk"),
        ) != (size, body_sha256, atlas_sha256, name, "Global", name_source, False):
            _bad("adjacent atlas boundary differs")
        if not _same(
            function.get("ranges"), [{"start_rva": _hex(entry), "size": size}]
        ):
            _bad("adjacent atlas range differs")
        result[role] = {
            "entry_rva": _hex(entry),
            "body_size": size,
            "body_sha256": body_sha256,
            "atlas_record_sha256": atlas_sha256,
            "range_start_rva": _hex(entry),
            "range_end_rva_exclusive": _hex(entry + size),
            "ghidra_analysis_metadata": {
                "name": name,
                "namespace": "Global",
                "name_source": name_source,
                "thunk": False,
                "metadata_only": True,
            },
        }
    if (
        result["left_neighbor"]["range_end_rva_exclusive"] != _hex(_ENTRY)
        or _ENTRY + _SIZE != 0x378A34
    ):
        _bad("adjacent atlas layout differs")
    return result


def _target_pe_backing(image: Any | None = None) -> dict[str, Any]:
    backing = {
        "section_name": ".text",
        "section_rva": "0x00001000",
        "section_virtual_size": "0x003d4b4e",
        "section_raw_size": "0x003d4c00",
        "section_raw_offset": "0x00000400",
        "section_characteristics": "0x60000020",
        "section_writable": False,
        "file_backed": True,
        "file_offset": "0x00377e15",
    }
    if image is not None:
        section = next(
            (
                row
                for row in image.sections
                if row.virtual_address
                <= _ENTRY
                < row.virtual_address + row.virtual_size
            ),
            None,
        )
        offset = image.rva_span_to_file_offset(_ENTRY, _SIZE)
        if section is None or (
            section.name,
            section.virtual_address,
            section.virtual_size,
            section.raw_size,
            section.raw_offset,
            section.characteristics,
            offset,
        ) != (".text", 0x1000, 0x3D4B4E, 0x3D4C00, 0x400, 0x60000020, 0x377E15):
            _bad("target PE backing differs")
        if image.data[offset : offset + _SIZE] != bytes.fromhex(_RAW):
            _bad("target PE bytes differ")
    return backing


def _parent_edge(parent: Mapping[str, Any]) -> list[dict[str, Any]]:
    calls = _mapping(parent.get("native_calls"), "parent native calls")
    rows = [
        dict(_mapping(row, "parent direct edge"))
        for row in _array(calls.get("direct"), "parent direct edges")
    ]
    matches = [
        row
        for row in rows
        if _rva(
            _mapping(row.get("instruction"), "parent instruction").get("rva"),
            "parent site",
        )
        == 0x378B5D
        and _rva(row.get("source_entry_rva"), "parent source") == 0x378B55
        and _rva(row.get("target_entry_rva"), "parent target") == _ENTRY
    ]
    if len(rows) != 3 or len(matches) != 1:
        _bad("parent direct-edge rejoin differs")
    match = matches[0]
    declared = _mapping(
        match.get("ghidra_declared_direct_edge"), "parent declared edge"
    )
    if (
        match.get("source_body_size"),
        match.get("source_body_sha256"),
        match.get("source_atlas_record_sha256"),
        match.get("target_body_size"),
        match.get("target_body_sha256"),
        match.get("target_atlas_record_sha256"),
        declared.get("target_name_sha256"),
    ) != (
        25,
        "c60b762b740ca702e7dd2f96ac96f31c9122758f9c0bf0b518a54cda2986dfe7",
        "0bf347712ab1049e562b947e0a83c7669425e76e910aab6096bb42c8a45f2c46",
        _SIZE,
        _BODY,
        _ATLAS,
        "33d0a0b292db5172dcfbbedd49defac7eae926baee9e8797494a74a90f3aee97",
    ) or not _same(
        match.get("instruction"), _instruction(0x378B5D, "e8b3feffff")
    ):
        _bad("parent direct-edge cross-join differs")
    return matches


def _native_calls(facts: Mapping[str, Any], image: Any | None = None) -> dict[str, Any]:
    _target(facts)
    if any(
        _rva(edge.get("source_entry_rva"), "direct source") == _ENTRY
        for edge in _edges(facts).values()
    ):
        _bad("outgoing native direct-edge partition differs")
    operand = {
        "role": "opaque_absolute_immediate_operand",
        "instruction": _instruction(0x378A17, "bb10408900"),
        "operand_class": "immediate",
        "operand_index": 1,
        "operand_access": "none",
        "operand_va": "0x00894010",
        "operand_rva": "0x00494010",
        "section_name": ".data",
        "section_rva": "0x00492000",
        "section_characteristics": "0xc0000040",
        "section_writable": True,
        "virtual_size": "0x000471cc",
        "raw_size": "0x00024800",
        "raw_offset": "0x00490200",
        "file_backed": True,
        "file_offset": "0x00492210",
        "opaque_file_bytes_size": 4,
        "opaque_file_bytes_sha256": "f0a19effaf081c6247b43afd3bc9f70ea771353137f4cce3ac38833893543af1",
        "contents_or_runtime_behavior_opaque": True,
    }
    if image is not None:
        rva = _rva(operand["operand_rva"], "operand rva")
        section = next(
            (
                s
                for s in image.sections
                if s.virtual_address <= rva < s.virtual_address + s.virtual_size
            ),
            None,
        )
        offset = image.rva_span_to_file_offset(rva, 4)
        raw = image.data[offset : offset + 4]
        if section is None or (
            section.name,
            section.virtual_address,
            section.virtual_size,
            section.raw_size,
            section.raw_offset,
            section.characteristics,
            offset,
        ) != (
            ".data",
            0x492000,
            0x471CC,
            0x24800,
            0x490200,
            0xC0000040,
            0x492210,
        ):
            _bad("PE immediate binding differs")
        if (
            raw != bytes.fromhex("20059319")
            or len(raw) != operand["opaque_file_bytes_size"]
            or hashlib.sha256(raw).hexdigest() != operand["opaque_file_bytes_sha256"]
        ):
            _bad("opaque PE immediate bytes differ")
    return {
        "outgoing_direct": [],
        "outgoing_direct_partition_complete": True,
        "direct_lua_calls": [],
        "direct_lua_partition_complete": True,
        "staged_lua_dispatches": [],
        "staged_lua_partition_complete": True,
        "opaque_indirect_controls": [],
        "indirect_control_partition_complete": True,
        "pe_address_operands": [operand],
        "pe_address_operand_partition_complete": True,
        "non_pe_immediate_literals": [
            {
                "instruction_rva": "0x00378a31",
                "operand_index": 0,
                "value": "0x00000004",
                "syntax": "x86_ret_imm16",
            }
        ],
        "non_pe_immediate_literal_partition_complete": True,
        "segment_qualified_memory_syntax": [],
        "segment_qualified_memory_partition_complete": True,
        "bnd_prefixed_control_syntax": [],
        "bnd_prefixed_control_partition_complete": True,
        "opaque_interrupt_syntax": [],
        "opaque_interrupt_partition_complete": True,
        "call_r32_audit": _audit(),
        "register_call_partition_complete": True,
    }


def _expected_scan(facts: Mapping[str, Any]) -> dict[str, Any]:
    functions, edges = _atlas_functions(facts), _edges(facts)
    observed_sites = {
        site
        for site, edge in edges.items()
        if _rva(edge.get("target_entry_rva"), "reference target") == _ENTRY
    }
    if observed_sites != {site for site, _owner, _raw, _atlas in _REFS}:
        _bad("declared incoming frontier differs")
    records = []
    for site, owner, raw, atlas in _REFS:
        edge, owner_row = edges.get(site), functions.get(owner)
        if (
            edge is None
            or owner_row is None
            or (
                _rva(edge.get("source_entry_rva"), "reference source"),
                _rva(edge.get("target_entry_rva"), "reference target"),
                _rva(edge.get("target_rva"), "reference target"),
                atlas_record_sha256(owner_row),
            )
            != (owner, _ENTRY, _ENTRY, atlas)
        ):
            _bad("incoming frontier facts differ")
        records.append(
            {
                "instruction_rva": _hex(site),
                "instruction_size": 5,
                "instruction_sha256": hashlib.sha256(bytes.fromhex(raw)).hexdigest(),
                "owner_entry_rva": _hex(owner),
                "owner_atlas_record_sha256": atlas,
                "target_rva": _hex(_ENTRY),
                "target_atlas_record_sha256": _ATLAS,
                "target_va": _hex(_BASE + _ENTRY),
                "operand_class": "immediate",
                "operand_index": 0,
                "use_class": "direct_call",
                "call_form": "x86_relative_near_call_e8",
                "ghidra_declared_direct_edge": _normalized_edge(edge),
            }
        )
    owner_partition = [
        {
            "owner_entry_rva": row["owner_entry_rva"],
            "owner_atlas_record_sha256": row["owner_atlas_record_sha256"],
            "reference_count": 1,
        }
        for row in records
    ]
    target_partition = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 4,
            "owner_count": 4,
        }
    ]
    target_owner_partition = [
        {"target_rva": _hex(_ENTRY), **row} for row in owner_partition
    ]
    target_reference_partition = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 4,
        }
    ]
    hashes = {
        "owner_partition": _compact(owner_partition),
        "target_partition": _compact(target_partition),
        "target_owner_partition": _compact(target_owner_partition),
        "target_reference_partition": _compact(target_reference_partition),
    }
    if hashes != _PARTITION_HASHES or _compact(records) != _REFERENCE_HASH:
        _bad("target-reference hash differs")
    return {
        "target_rvas": [_hex(_ENTRY)],
        "target_vas": [_hex(_BASE + _ENTRY)],
        "scope": dict(_SCOPE),
        "references": records,
        "target_partition": target_partition,
        "owner_partition": owner_partition,
        "target_owner_partition": target_owner_partition,
        "target_reference_partition": target_reference_partition,
        "partition_sha256": hashes,
        "references_canonical_sha256": _REFERENCE_HASH,
        "aggregates": {
            "reference_count": 4,
            "target_count": 1,
            "owner_count": 4,
            "target_owner_count": 4,
            "direct_call_count": 4,
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
                    kind = None
                    value = None
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
    expected = [
        (site, owner, 0, bytes.fromhex(raw), "immediate")
        for site, owner, raw, _ in _REFS
    ]
    if tuple(totals) != (25490, 3735718, 1153814) or found != expected:
        _bad("all-operand target reference traversal differs")
    return _expected_scan(facts)


def _evidence(
    parent: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    rows: list[Any] | None = None,
    image: Any | None = None,
    scan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prerequisite = _preflight(parent, direct, facts)
    decoded = _decode() if rows is None else rows
    body = b"".join(bytes(row.bytes) for row in decoded)
    if body != bytes.fromhex(_RAW) or hashlib.sha256(body).hexdigest() != _BODY:
        _bad("target body bytes differ")
    _target(facts)
    expected = _expected_scan(facts)
    receipt = expected if scan is None else dict(scan)
    if not _same(receipt, expected):
        _bad("target reference receipt differs")
    parent_edges = _parent_edge(parent)
    parent_reference = receipt["references"][-1]
    if (
        parent_reference["instruction_rva"] != parent_edges[0]["instruction"]["rva"]
        or parent_reference["instruction_sha256"]
        != parent_edges[0]["instruction"]["sha256"]
        or parent_reference["owner_atlas_record_sha256"]
        != parent_edges[0]["source_atlas_record_sha256"]
        or parent_reference["target_atlas_record_sha256"]
        != parent_edges[0]["target_atlas_record_sha256"]
        or not _same(
            parent_reference["ghidra_declared_direct_edge"],
            parent_edges[0]["ghidra_declared_direct_edge"],
        )
    ):
        _bad("parent edge does not rejoin reference scan")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(
            _mapping(facts.get("identity"), "program facts identity")
        ),
        **prerequisite,
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "sealed_instruction_count": 16,
            "register_call_encoding_audit": [
                {"register": r, "encoding": f"ff{0xd0+i:02x}"}
                for i, r in enumerate(_REGISTER_NAMES)
            ],
        },
        "function_body": {
            "role": "relationship_defined_adjacent_cluster_second_callee_static_boundary",
            "entry_rva": _hex(_ENTRY),
            "atlas_record_sha256": _ATLAS,
            "body_size": _SIZE,
            "body_sha256": _BODY,
            "range_start_rva": _hex(_ENTRY),
            "range_size": _SIZE,
            "target_pe_backing": _target_pe_backing(image),
            "adjacent_atlas_boundaries": _adjacent_atlas_boundaries(facts),
            "control_flow_graph_canonical_sha256": _CFG,
            "reviewed_points": _points(decoded),
            "direct_lua_calls": [],
            "staged_lua_dispatches": [],
            "call_r32_audit": _audit(),
            "register_call_partition_complete": True,
            "ghidra_analysis_metadata": {
                "name": "__NLG_Notify",
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
        },
        "control_flow_graph": _graph(decoded),
        "predecessor_parent_edges": parent_edges,
        "native_calls": _native_calls(facts, image),
        "whole_atlas_reference_scan": receipt,
        "method": {
            "structural_boundary": "The receipt seals 31 decoded bytes, exact neighboring atlas boundaries and target PE backing, one opaque PE immediate, the exact parent rejoin, and a finite all-atlas target-reference traversal.",
            "not_claimed": [
                "analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return",
                "runtime reachability, invocation, ordering, frequency, or effects",
                "contents or runtime meaning of the .data operand",
                "computed, indirect, data, un-atlased, dynamic, or Lua-side references",
            ],
        },
        "summary": {
            "reviewed_target_count": 1,
            "reviewed_target_bytes": _SIZE,
            "sealed_adjacent_boundary_count": 2,
            "sealed_target_pe_backing_count": 1,
            "sealed_instruction_count": 16,
            "sealed_control_flow_graph_count": 1,
            "sealed_control_flow_graph_node_count": 16,
            "sealed_control_flow_graph_edge_count": 15,
            "native_direct_edge_count": 0,
            "direct_lua_call_count": 0,
            "staged_lua_dispatch_count": 0,
            "call_r32_count": 0,
            "opaque_indirect_control_count": 0,
            "pe_address_operand_count": 1,
            "pe_immediate_operand_count": 1,
            "pe_absolute_memory_operand_count": 0,
            "non_pe_immediate_literal_count": 1,
            "segment_qualified_memory_syntax_count": 0,
            "bnd_prefixed_control_syntax_count": 0,
            "opaque_interrupt_syntax_count": 0,
            "predecessor_parent_edge_count": 1,
            "target_reference_count": 4,
            "target_reference_target_count": 1,
            "target_reference_owner_count": 4,
            "target_reference_direct_call_count": 4,
            "target_reference_other_address_count": 0,
            "target_reference_memory_operand_count": 0,
            "schema_violations": 0,
        },
    }
    return result


def _normalize(operation):
    try:
        return operation()
    except NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterSecondCalleeStaticBoundaryError:
        raise
    except Exception as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterSecondCalleeStaticBoundaryError(
            str(exc)
        ) from exc


def validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary_structure(
    evidence: Mapping[str, Any],
    adjacent_callee_cluster_static_boundary: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    def run():
        evidence_object = _mapping(evidence, "evidence")
        parent_object = _mapping(
            adjacent_callee_cluster_static_boundary, "cluster parent"
        )
        direct_object = _mapping(direct_calls, "direct calls")
        facts_object = _mapping(program_facts, "program facts")
        for value, label in (
            (evidence_object, "evidence"),
            (parent_object, "cluster parent"),
            (direct_object, "direct calls"),
            (facts_object, "program facts"),
        ):
            _validate_json_tree(value, label)
        prerequisite = validate_native_lua_direct_call_structure(
            direct_object, facts_object
        )
        if (
            prerequisite.get("status") != "structurally_verified"
            or prerequisite.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct-call structural prerequisite differs")
        expected = _evidence(parent_object, direct_object, facts_object)
        if not _same(evidence_object, expected):
            _bad("structure receipt differs from finite reconstruction")
        _assert_publication_safe(evidence_object)
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
            "build_identity": dict(evidence_object["build_identity"]),
            "evidence_sha256": _canonical_sha256(evidence_object),
            "summary": dict(evidence_object["summary"]),
        }

    return _normalize(run)


def build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary(
    executable: Path,
    adjacent_callee_cluster_static_boundary: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run():
        parent_object = _mapping(
            adjacent_callee_cluster_static_boundary, "cluster parent"
        )
        direct_object = _mapping(direct_calls, "direct calls")
        facts_object = _mapping(program_facts, "program facts")
        inventory_object = _mapping(inventory, "inventory")
        for value, label in (
            (parent_object, "cluster parent"),
            (direct_object, "direct calls"),
            (facts_object, "program facts"),
            (inventory_object, "inventory"),
        ):
            _validate_json_tree(value, label)
        prerequisite = validate_native_lua_direct_call_census(
            executable, direct_object, facts_object, inventory=inventory_object
        )
        if (
            prerequisite.get("status") != "verified"
            or prerequisite.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct-call exact prerequisite differs")
        data, image, digest = _load_executable(executable)
        if digest != _EXE or image.image_base != _BASE:
            _bad("exact executable identity differs")
        decoder, _ = _decoder()
        decoder.detail = True
        rows = _decode_range(data, image, _ENTRY, _SIZE, decoder)
        scan = _whole_atlas_reference_scan(data, image, decoder, facts_object)
        result = _evidence(
            parent_object,
            direct_object,
            facts_object,
            rows=rows,
            image=image,
            scan=scan,
        )
        replay, replay_image, replay_digest = _load_executable(executable)
        if (
            replay_digest != digest
            or replay != data
            or replay_image.image_base != _BASE
        ):
            _bad("executable changed during exact rebuild")
        _assert_publication_safe(result)
        validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary_structure(
            result, parent_object, direct_object, facts_object
        )
        return result

    return _normalize(run)


def validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary(
    executable: Path,
    evidence: Mapping[str, Any],
    adjacent_callee_cluster_static_boundary: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run():
        evidence_object = _mapping(evidence, "evidence")
        parent_object = _mapping(
            adjacent_callee_cluster_static_boundary, "cluster parent"
        )
        direct_object = _mapping(direct_calls, "direct calls")
        facts_object = _mapping(program_facts, "program facts")
        inventory_object = _mapping(inventory, "inventory")
        _validate_json_tree(evidence_object, "evidence")
        rebuilt = build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary(
            executable,
            parent_object,
            direct_object,
            facts_object,
            inventory=inventory_object,
        )
        if not _same(evidence_object, rebuilt):
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


def encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary(
    value: Mapping[str, Any],
) -> str:
    def run() -> str:
        value_object = _mapping(value, "encoded value")
        _validate_json_tree(value_object, "encoded value")
        return (
            json.dumps(
                value_object,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )

    return _normalize(run)
