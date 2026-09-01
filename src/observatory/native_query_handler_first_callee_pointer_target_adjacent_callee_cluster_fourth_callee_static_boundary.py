"""Fail-closed, relationship-only receipt for the 0x00378a40 boundary.

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
from src.observatory.native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary import (
    ANALYSIS_KIND as SECOND_KIND,
)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_PARENT = "1385ca599a7442b2b18a45206619d520b19db1b5a2fa9c0ba5b54908831462a5"
_SECOND = "ec66ae66eb932cb59f52ca3ad9095c31bb887723ed7647aef4eeeb0aaa64389d"
_BASE, _ENTRY, _SIZE = 0x400000, 0x378A40, 144
_RAW = (
    "5356578b5424108b4424148b4c2418555250515168d08a770064ff3500000000"
    "a1283f890033c489442408648925000000008b4424308b58088b4c242c33198b"
    "700c83fefe743b8b54243483fafe74043bf2762e8d34768d5cb3108b0b89480c"
    "837b040075cc68010100008b4308e862ffffffb9010000008b4308e874ffffff"
    "ebb0648f050000000083c4185f5e5bc3"
)
_BODY = "c75af58d5bf56eae591044575adab9c6c3a2861576a9524fa38e4854960c99da"
_ATLAS = "e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6"
_CFG = "3dbfa70a1195e11c64f0856fb189dd662b8740f445e2b2a00d3fd36c5044e9e1"
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
        0x378B92,
        0x378B87,
        "e8a9feffff",
        "6cb344ca1b46add4cfae6c7a40acda49140fff99365b33a5d0f572e8047fc5b3",
    ),
    (
        0x386E8F,
        0x386DC7,
        "e8ac1bffff",
        "cb17425f767d67c8ea596207d7e10b9be12c9a910d00338984846401c01f6ead",
    ),
    (
        0x386FB7,
        0x386EF2,
        "e8841affff",
        "af029ba5558fd31620ece7a45c418d0e05b6cbdcba6dfd0e6c2b4a4a3a412522",
    ),
)
_PARTITION_HASHES = {
    "owner_partition": "f96dccd7388a995798cb87008ce45c03ba4b3a1133aefdb6421a2a290e2dc139",
    "target_partition": "1858a6f61db83c671601af9c0c1300ca962cba95ac64fb257d3a8660a157e02f",
    "target_owner_partition": "d61e598c8e392c6e905d24dd219a011d4af269d0a8c277e20fe45ab7f2d50c39",
    "target_reference_partition": "4bb16440b1e01f8de8f935ca7a98041eee1890ff1aafdcd6200252eb77015511",
}
_REFERENCE_HASH = "9b5a891fbb8636c7848e7370b886ae3388986310f50ab7f998c9cb85a933beb4"
_ENDPOINT = 0x378AD0
_ENDPOINT_PARTITION_HASHES = {
    "owner_partition": "440be2af21a71fc5f2984b2d60f2da7ecdad1b5b88499efb28ee36d591d2a28b",
    "target_partition": "f56f4da87465da8362261b0fd66fd4960f27be8c220041c021f91f074ee97845",
    "target_owner_partition": "45b076de44a32dec6074aceee5dc165265da871538498414ba84c7c98b8ac115",
    "target_reference_partition": "780373015d234ba91a043ef678b28b3d3399a120079e39a68a5d6136bcf7c706",
}
_ENDPOINT_REFERENCE_HASH = (
    "48ed8f067c8d1fac9217dff84c769f96fbf9e1900b3bf0ed64741f6dc9aef9c8"
)


class NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeStaticBoundaryError(
    RuntimeError
):
    """Raised when this bounded static receipt cannot be reproduced."""


def _bad(message: str) -> None:
    raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeStaticBoundaryError(
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
    if len(rows) != 48 or b"".join(bytes(row.bytes) for row in rows) != raw:
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
    if (graph.get("node_count"), graph.get("edge_count")) != (48, 51) or (
        _CFG and _canonical_sha256(graph) != _CFG
    ):
        _bad("sealed target control-flow graph differs")
    return graph


def _preflight(
    parent: Mapping[str, Any],
    second: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    identity = dict(_mapping(facts.get("identity"), "program facts identity"))
    if (
        identity.get("executable_sha256") != _EXE
        or not _same(parent.get("build_identity"), identity)
        or not _same(second.get("build_identity"), identity)
        or not _same(direct.get("build_identity"), identity)
    ):
        _bad("prerequisite build identity differs")
    if (
        parent.get("analysis_kind") != PARENT_KIND
        or _canonical_sha256(parent) != _PARENT
    ):
        _bad("adjacent-cluster parent receipt differs")
    if (
        second.get("analysis_kind") != SECOND_KIND
        or _canonical_sha256(second) != _SECOND
    ):
        _bad("adjacent-cluster second-callee receipt differs")
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
        "second_callee_static_boundary": _source_identity(
            second,
            SECOND_KIND,
            _SECOND,
            "adjacent-callee cluster second callee",
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
    ) != (_SIZE, _BODY, _ATLAS, "__local_unwind4", "Global", "ANALYSIS", False):
        _bad("target atlas record differs")
    if not _same(value.get("ranges"), [{"start_rva": _hex(_ENTRY), "size": _SIZE}]):
        _bad("target atlas range differs")
    return value


def _adjacent_atlas_boundaries(
    facts: Mapping[str, Any], image: Any | None = None
) -> dict[str, Any]:
    functions = _atlas_functions(facts)
    expected = (
        (
            "left_neighbor",
            0x378A34,
            3,
            "94abb6fadbcdb595e2ba8c9a673e591fec8944a2eb04edee55a9ecc56b893047",
            "28e6f200d780328c2667ced90607e5aa26165fa2b59903ba8ae560419766abd1",
            "FUN_00778a34",
            "DEFAULT",
        ),
        (
            "right_neighbor",
            0x378B3E,
            23,
            "6e2b3bd553f0ffdd43df815cf3341fce2e76a73e8f9b243867c06b12310701fb",
            "21bfa842aaa26c0306ff5b8da85ba63bc13daaa71cd930aaa24b91da1e34ed6c",
            "_EH4_CallFilterFunc",
            "ANALYSIS",
        ),
    )
    result: dict[str, Any] = {
        "layout_only": True,
        "semantic_kinship_claimed": False,
        "left_neighbor_ends_at_left_gap": True,
        "left_gap_ends_at_target": True,
        "target_ends_at_right_un_atlased_gap": True,
        "right_gap_ends_at_right_neighbor": True,
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
        result["left_neighbor"]["range_end_rva_exclusive"] != "0x00378a37"
        or result["right_neighbor"]["range_start_rva"] != "0x00378b3e"
    ):
        _bad("adjacent atlas layout differs")

    ranges = []
    for owner, function in functions.items():
        for raw_range in _array(function.get("ranges"), "atlas range"):
            span = _mapping(raw_range, "atlas range")
            start = _rva(span.get("start_rva"), "range start")
            size = span.get("size")
            if type(size) is not int or size <= 0:
                _bad("invalid atlas range")
            ranges.append((start, start + size, owner))
    overlaps = [row for row in ranges if row[0] < _ENTRY + _SIZE and _ENTRY < row[1]]
    predecessors = [row for row in ranges if row[1] <= _ENTRY]
    successors = [row for row in ranges if row[0] >= _ENTRY + _SIZE]
    if (
        overlaps != [(_ENTRY, _ENTRY + _SIZE, _ENTRY)]
        or max(predecessors, key=lambda row: (row[1], row[0]))
        != (0x378A34, 0x378A37, 0x378A34)
        or min(successors, key=lambda row: (row[0], row[1]))
        != (0x378B3E, 0x378B55, 0x378B3E)
    ):
        _bad("nearest atlas boundary partition differs")

    left_raw = bytes.fromhex("cccccccccccccccccc")
    right_raw = bytes.fromhex(
        "8b4c2404f7410406000000b80100000074338b4424088b480833c8e8dae9fdff"
        "558b6818ff700cff7010ff7014e83effffff83c40c5d8b4424088b5424108902"
        "b803000000c355ff742408e850f3c8ff83c4048b4c24088b29ff711cff7118"
        "ff7128e809ffffff83c40c5dc20400"
    )
    result["left_gap"] = {
        "start_rva": "0x00378a37",
        "end_rva_exclusive": "0x00378a40",
        "size": 9,
        "section_name": ".text",
        "file_offset": "0x00377e37",
        "bytes_sha256": hashlib.sha256(left_raw).hexdigest(),
        "atlas_owned": False,
        "contents_or_runtime_behavior_opaque": True,
    }
    result["right_un_atlased_gap"] = {
        "start_rva": "0x00378ad0",
        "end_rva_exclusive": "0x00378b3e",
        "size": 110,
        "section_name": ".text",
        "file_offset": "0x00377ed0",
        "bytes_sha256": hashlib.sha256(right_raw).hexdigest(),
        "atlas_owned": False,
        "contents_or_runtime_behavior_opaque": True,
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
        if section is None or (
            section.name,
            section.virtual_address,
            section.virtual_size,
            section.raw_size,
            section.raw_offset,
            section.characteristics,
        ) != (".text", 0x1000, 0x3D4B4E, 0x3D4C00, 0x400, 0x60000020):
            _bad("gap PE section differs")
        for start, expected_offset, expected_raw, label in (
            (0x378A37, 0x377E37, left_raw, "left gap"),
            (0x378AD0, 0x377ED0, right_raw, "right gap"),
        ):
            offset = image.rva_span_to_file_offset(start, len(expected_raw))
            observed = image.data[offset : offset + len(expected_raw)]
            if (
                offset != expected_offset
                or observed != expected_raw
                or hashlib.sha256(observed).hexdigest()
                != hashlib.sha256(expected_raw).hexdigest()
            ):
                _bad(f"{label} backing differs")
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
        "file_offset": "0x00377e40",
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
        ) != (".text", 0x1000, 0x3D4B4E, 0x3D4C00, 0x400, 0x60000020, 0x377E40):
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
        == 0x378B92
        and _rva(row.get("source_entry_rva"), "parent source") == 0x378B87
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
        23,
        "00a48f1b6eb852efff2b66f536e59bcdffe8c722348a1127d976604a5c3cc994",
        "6cb344ca1b46add4cfae6c7a40acda49140fff99365b33a5d0f572e8047fc5b3",
        _SIZE,
        _BODY,
        _ATLAS,
        "1a687bc71257cdaf1d441abfa82445df6d72210f99f6859310e0aa5bfbde2c7d",
    ) or not _same(
        match.get("instruction"), _instruction(0x378B92, "e8a9feffff")
    ):
        _bad("parent direct-edge cross-join differs")
    return matches


def _second_callee_rejoin(
    second: Mapping[str, Any], outgoing: list[dict[str, Any]]
) -> dict[str, Any]:
    scan = _mapping(
        second.get("whole_atlas_reference_scan"),
        "second-callee whole-atlas reference scan",
    )
    references = [
        dict(_mapping(row, "second-callee reference"))
        for row in _array(scan.get("references"), "second-callee references")
    ]
    matches = [
        row
        for row in references
        if _rva(row.get("instruction_rva"), "second-callee site") == 0x378AAE
        and _rva(row.get("owner_entry_rva"), "second-callee owner") == _ENTRY
        and _rva(row.get("target_rva"), "second-callee target") == 0x378A15
    ]
    edges = [
        row
        for row in outgoing
        if _rva(
            _mapping(row.get("instruction"), "outgoing instruction").get("rva"),
            "outgoing site",
        )
        == 0x378AAE
    ]
    if len(references) != 4 or len(matches) != 1 or len(edges) != 1:
        _bad("second-callee dependent rejoin differs")
    reference, edge = matches[0], edges[0]
    if (
        reference.get("instruction_sha256")
        != _mapping(edge.get("instruction"), "outgoing instruction").get("sha256")
        or reference.get("owner_atlas_record_sha256")
        != edge.get("source_atlas_record_sha256")
        or reference.get("target_atlas_record_sha256")
        != edge.get("target_atlas_record_sha256")
        or not _same(
            reference.get("ghidra_declared_direct_edge"),
            edge.get("ghidra_declared_direct_edge"),
        )
    ):
        _bad("second-callee reference does not rejoin outgoing edge")
    return {
        "dependent_analysis_kind": SECOND_KIND,
        "dependent_canonical_sha256": _SECOND,
        "instruction_rva": "0x00378aae",
        "owner_entry_rva": _hex(_ENTRY),
        "target_entry_rva": "0x00378a15",
        "reference_rejoined": True,
    }


def _pe_address_operands(image: Any | None = None) -> list[dict[str, Any]]:
    specs = (
        (
            0x378A54,
            "68d08a7700",
            "immediate",
            0,
            "none",
            0x378AD0,
            "opaque_un_atlased_text_address",
            "8b4c2404",
        ),
        (
            0x378A60,
            "a1283f8900",
            "absolute_memory",
            1,
            "read",
            0x493F28,
            "opaque_absolute_memory_operand",
            "4ee640bb",
        ),
        (
            0x378A85,
            "743b",
            "immediate",
            0,
            "none",
            0x378AC2,
            "body_local_control_target",
            "648f0500",
        ),
        (
            0x378A8E,
            "7404",
            "immediate",
            0,
            "none",
            0x378A94,
            "body_local_control_target",
            "8d34768d",
        ),
        (
            0x378A92,
            "762e",
            "immediate",
            0,
            "none",
            0x378AC2,
            "body_local_control_target",
            "648f0500",
        ),
        (
            0x378AA4,
            "75cc",
            "immediate",
            0,
            "none",
            0x378A72,
            "body_local_control_target",
            "8b442430",
        ),
        (
            0x378AAE,
            "e862ffffff",
            "immediate",
            0,
            "none",
            0x378A15,
            "declared_direct_call_target",
            "5351bb10",
        ),
        (
            0x378ABB,
            "e874ffffff",
            "immediate",
            0,
            "none",
            0x378A34,
            "declared_direct_call_target",
            "ffd0c3cc",
        ),
        (
            0x378AC0,
            "ebb0",
            "immediate",
            0,
            "none",
            0x378A72,
            "body_local_control_target",
            "8b442430",
        ),
    )
    result = []
    for site, raw, operand_class, index, access, target, role, backing_hex in specs:
        is_data = target == 0x493F28
        expected_offset = 0x492128 if is_data else target - 0x1000 + 0x400
        expected_backing = bytes.fromhex(backing_hex)
        section_fields = (
            {
                "section_name": ".data",
                "section_rva": "0x00492000",
                "section_virtual_size": "0x000471cc",
                "section_raw_size": "0x00024800",
                "section_raw_offset": "0x00490200",
                "section_characteristics": "0xc0000040",
                "section_writable": True,
            }
            if is_data
            else {
                "section_name": ".text",
                "section_rva": "0x00001000",
                "section_virtual_size": "0x003d4b4e",
                "section_raw_size": "0x003d4c00",
                "section_raw_offset": "0x00000400",
                "section_characteristics": "0x60000020",
                "section_writable": False,
            }
        )
        record = {
            "role": role,
            "instruction": _instruction(site, raw),
            "operand_class": operand_class,
            "operand_index": index,
            "operand_access": access,
            "operand_va": _hex(_BASE + target),
            "operand_rva": _hex(target),
            **section_fields,
            "file_backed": True,
            "file_offset": _hex(expected_offset),
            "opaque_file_bytes_size": 4,
            "opaque_file_bytes_sha256": hashlib.sha256(expected_backing).hexdigest(),
            "contents_or_runtime_behavior_opaque": True,
        }
        if image is not None:
            section = next(
                (
                    row
                    for row in image.sections
                    if row.virtual_address
                    <= target
                    < row.virtual_address + row.virtual_size
                ),
                None,
            )
            offset = image.rva_span_to_file_offset(target, 4)
            observed = image.data[offset : offset + 4]
            expected_geometry = (
                (".data", 0x492000, 0x471CC, 0x24800, 0x490200, 0xC0000040)
                if is_data
                else (".text", 0x1000, 0x3D4B4E, 0x3D4C00, 0x400, 0x60000020)
            )
            if (
                section is None
                or (
                    section.name,
                    section.virtual_address,
                    section.virtual_size,
                    section.raw_size,
                    section.raw_offset,
                    section.characteristics,
                )
                != expected_geometry
            ):
                _bad("PE-address operand section differs")
            if (
                offset != expected_offset
                or observed != expected_backing
                or hashlib.sha256(observed).hexdigest()
                != record["opaque_file_bytes_sha256"]
            ):
                _bad("PE-address operand backing differs")
        result.append(record)
    return result


def _native_calls(
    facts: Mapping[str, Any],
    second: Mapping[str, Any],
    image: Any | None = None,
) -> dict[str, Any]:
    source = _target(facts)
    functions, edges = _atlas_functions(facts), _edges(facts)
    specs = (
        (
            0x378AAE,
            "e862ffffff",
            0x378A15,
            31,
            "bfc32dca1a2879c053683385362acc34071b244f56f0724b2ec96d15f6660f29",
            "6bf2ee0e68ff7a0c12250248e928bae616b939421135f8b679081c4903dedb81",
            "__NLG_Notify",
            "ANALYSIS",
        ),
        (
            0x378ABB,
            "e874ffffff",
            0x378A34,
            3,
            "94abb6fadbcdb595e2ba8c9a673e591fec8944a2eb04edee55a9ecc56b893047",
            "28e6f200d780328c2667ced90607e5aa26165fa2b59903ba8ae560419766abd1",
            "FUN_00778a34",
            "DEFAULT",
        ),
    )
    observed_sites = {
        site
        for site, edge in edges.items()
        if _rva(edge.get("source_entry_rva"), "direct source") == _ENTRY
    }
    if observed_sites != {site for site, *_rest in specs}:
        _bad("outgoing native direct-edge partition differs")
    outgoing = []
    for (
        site,
        raw,
        target_entry,
        target_size,
        target_body,
        target_atlas,
        target_name,
        target_name_source,
    ) in specs:
        edge, target = edges.get(site), functions.get(target_entry)
        if (
            edge is None
            or target is None
            or (
                _rva(edge.get("source_entry_rva"), "outgoing source"),
                _rva(edge.get("target_entry_rva"), "outgoing target"),
                _rva(edge.get("target_rva"), "outgoing target"),
                target.get("body_size"),
                target.get("body_sha256"),
                atlas_record_sha256(target),
                target.get("name"),
                target.get("namespace"),
                target.get("name_source"),
                target.get("thunk"),
            )
            != (
                _ENTRY,
                target_entry,
                target_entry,
                target_size,
                target_body,
                target_atlas,
                target_name,
                "Global",
                target_name_source,
                False,
            )
        ):
            _bad("outgoing native direct-edge cross-join differs")
        if not _same(
            target.get("ranges"),
            [{"start_rva": _hex(target_entry), "size": target_size}],
        ):
            _bad("outgoing target atlas range differs")
        record = {
            "instruction": _instruction(site, raw),
            "source_entry_rva": _hex(_ENTRY),
            "source_body_size": _SIZE,
            "source_body_sha256": _BODY,
            "source_atlas_record_sha256": _ATLAS,
            "target_entry_rva": _hex(target_entry),
            "target_body_size": target_size,
            "target_body_sha256": target_body,
            "target_atlas_record_sha256": target_atlas,
            "ghidra_declared_direct_edge": _normalized_edge(edge),
            "target_ghidra_analysis_metadata": {
                "name": target_name,
                "namespace": "Global",
                "name_source": target_name_source,
                "thunk": False,
                "metadata_only": True,
            },
            "target_behavior_opaque": True,
        }
        if image is not None:
            target_offset = image.rva_span_to_file_offset(target_entry, target_size)
            expected_target = (
                bytes.fromhex(_RAW)
                if target_entry == _ENTRY
                else (
                    bytes.fromhex(
                        "5351bb104089008b4c240c894b08894304896b0c55515058595d595bc20400"
                    )
                    if target_entry == 0x378A15
                    else bytes.fromhex("ffd0c3")
                )
            )
            if (
                image.data[target_offset : target_offset + target_size]
                != expected_target
            ):
                _bad("outgoing target PE bytes differ")
        outgoing.append(record)
    rejoin = _second_callee_rejoin(second, outgoing)
    pe_operands = _pe_address_operands(image)
    return {
        "outgoing_direct": outgoing,
        "outgoing_direct_partition_complete": True,
        "second_callee_dependent_rejoin": rejoin,
        "direct_lua_calls": [],
        "direct_lua_partition_complete": True,
        "staged_lua_dispatches": [],
        "staged_lua_partition_complete": True,
        "opaque_indirect_controls": [],
        "indirect_control_partition_complete": True,
        "pe_address_operands": pe_operands,
        "pe_address_operand_partition_complete": True,
        "non_pe_immediate_literals": [
            {
                "instruction_rva": "0x00378a82",
                "operand_index": 1,
                "value": "0xfffffffe",
                "syntax": "x86_cmp_imm8_sign_extended",
            },
            {
                "instruction_rva": "0x00378a8b",
                "operand_index": 1,
                "value": "0xfffffffe",
                "syntax": "x86_cmp_imm8_sign_extended",
            },
            {
                "instruction_rva": "0x00378aa0",
                "operand_index": 1,
                "value": "0x00000000",
                "syntax": "x86_cmp_imm8",
            },
            {
                "instruction_rva": "0x00378aa6",
                "operand_index": 0,
                "value": "0x00000101",
                "syntax": "x86_push_imm32",
            },
            {
                "instruction_rva": "0x00378ab3",
                "operand_index": 1,
                "value": "0x00000001",
                "syntax": "x86_mov_imm32",
            },
            {
                "instruction_rva": "0x00378ac9",
                "operand_index": 1,
                "value": "0x00000018",
                "syntax": "x86_add_imm8",
            },
        ],
        "non_pe_immediate_literal_partition_complete": True,
        "segment_qualified_memory_syntax": [
            {
                "instruction": _instruction(0x378A59, "64ff3500000000"),
                "operand_index": 0,
                "operand_access": "read",
                "segment_register": "fs",
                "base_register": None,
                "index_register": None,
                "displacement": "0x00000000",
                "contents_or_runtime_behavior_opaque": True,
            },
            {
                "instruction": _instruction(0x378A6B, "64892500000000"),
                "operand_index": 0,
                "operand_access": "write",
                "segment_register": "fs",
                "base_register": None,
                "index_register": None,
                "displacement": "0x00000000",
                "contents_or_runtime_behavior_opaque": True,
            },
            {
                "instruction": _instruction(0x378AC2, "648f0500000000"),
                "operand_index": 0,
                "operand_access": "write",
                "segment_register": "fs",
                "base_register": None,
                "index_register": None,
                "displacement": "0x00000000",
                "contents_or_runtime_behavior_opaque": True,
            },
        ],
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
            "reference_count": 3,
            "owner_count": 3,
        }
    ]
    target_owner_partition = [
        {"target_rva": _hex(_ENTRY), **row} for row in owner_partition
    ]
    target_reference_partition = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 3,
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
            "reference_count": 3,
            "target_count": 1,
            "owner_count": 3,
            "target_owner_count": 3,
            "direct_call_count": 3,
            "comparison_count": 0,
            "other_address_count": 0,
            "memory_operand_count": 0,
        },
    }


def _expected_endpoint_scan(facts: Mapping[str, Any]) -> dict[str, Any]:
    functions, edges = _atlas_functions(facts), _edges(facts)
    owner = functions.get(_ENTRY)
    if owner is None or atlas_record_sha256(owner) != _ATLAS:
        _bad("endpoint owner atlas record differs")
    if functions.get(_ENDPOINT) is not None or edges.get(0x378A54) is not None:
        _bad("endpoint unexpectedly has atlas ownership or a declared edge")
    for function in functions.values():
        for raw_range in _array(function.get("ranges"), "atlas range"):
            span = _mapping(raw_range, "atlas range")
            start = _rva(span.get("start_rva"), "range start")
            size = span.get("size")
            if type(size) is not int or size <= 0:
                _bad("invalid atlas range")
            if start <= _ENDPOINT < start + size:
                _bad("endpoint unexpectedly belongs to an atlas range")
    record = {
        "instruction_rva": "0x00378a54",
        "instruction_size": 5,
        "instruction_sha256": hashlib.sha256(bytes.fromhex("68d08a7700")).hexdigest(),
        "owner_entry_rva": _hex(_ENTRY),
        "owner_atlas_record_sha256": _ATLAS,
        "target_rva": _hex(_ENDPOINT),
        "target_va": _hex(_BASE + _ENDPOINT),
        "atlas_target_record_present": False,
        "operand_class": "immediate",
        "operand_index": 0,
        "use_class": "other_address",
        "ghidra_declared_direct_edge": None,
    }
    records = [record]
    owner_partition = [
        {
            "owner_entry_rva": _hex(_ENTRY),
            "owner_atlas_record_sha256": _ATLAS,
            "reference_count": 1,
        }
    ]
    target_partition = [
        {
            "target_rva": _hex(_ENDPOINT),
            "atlas_target_record_present": False,
            "reference_count": 1,
            "owner_count": 1,
        }
    ]
    target_owner_partition = [
        {
            "target_rva": _hex(_ENDPOINT),
            **owner_partition[0],
        }
    ]
    target_reference_partition = [
        {
            "target_rva": _hex(_ENDPOINT),
            "atlas_target_record_present": False,
            "reference_count": 1,
        }
    ]
    hashes = {
        "owner_partition": _compact(owner_partition),
        "target_partition": _compact(target_partition),
        "target_owner_partition": _compact(target_owner_partition),
        "target_reference_partition": _compact(target_reference_partition),
    }
    if (
        hashes != _ENDPOINT_PARTITION_HASHES
        or _compact(records) != _ENDPOINT_REFERENCE_HASH
    ):
        _bad("endpoint-reference hash differs")
    return {
        "target_rvas": [_hex(_ENDPOINT)],
        "target_vas": [_hex(_BASE + _ENDPOINT)],
        "scope": dict(_SCOPE),
        "references": records,
        "target_partition": target_partition,
        "owner_partition": owner_partition,
        "target_owner_partition": target_owner_partition,
        "target_reference_partition": target_reference_partition,
        "partition_sha256": hashes,
        "references_canonical_sha256": _ENDPOINT_REFERENCE_HASH,
        "aggregates": {
            "reference_count": 1,
            "target_count": 1,
            "owner_count": 1,
            "target_owner_count": 1,
            "direct_call_count": 0,
            "comparison_count": 0,
            "other_address_count": 1,
            "memory_operand_count": 0,
        },
    }


def _whole_atlas_reference_scan(
    data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]
) -> dict[str, Any]:
    import capstone.x86_const as x86

    found_entry: list[tuple[Any, ...]] = []
    found_endpoint: list[tuple[Any, ...]] = []
    totals = [0, 0, 0]
    entry_va, endpoint_va = image.image_base + _ENTRY, image.image_base + _ENDPOINT
    decoder.detail = True
    for owner, function in sorted(_atlas_functions(facts).items()):
        for raw_range in _array(function.get("ranges"), "atlas range"):
            span = _mapping(raw_range, "atlas range")
            start = _rva(span.get("start_rva"), "range start")
            size = span.get("size")
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
                    record = (
                        row.address - image.image_base,
                        owner,
                        index,
                        bytes(row.bytes),
                        kind,
                    )
                    if value == entry_va:
                        found_entry.append(record)
                    if value == endpoint_va:
                        found_endpoint.append(record)
    expected_entry = [
        (site, owner, 0, bytes.fromhex(raw), "immediate")
        for site, owner, raw, _atlas in _REFS
    ]
    expected_endpoint = [
        (0x378A54, _ENTRY, 0, bytes.fromhex("68d08a7700"), "immediate")
    ]
    if (
        tuple(totals) != (25490, 3735718, 1153814)
        or found_entry != expected_entry
        or found_endpoint != expected_endpoint
    ):
        _bad("all-operand target or endpoint traversal differs")
    return {
        "target_entry": _expected_scan(facts),
        "target_end_pointer": _expected_endpoint_scan(facts),
    }


def _evidence(
    parent: Mapping[str, Any],
    second: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    rows: list[Any] | None = None,
    image: Any | None = None,
    scans: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prerequisite = _preflight(parent, second, direct, facts)
    decoded = _decode() if rows is None else rows
    body = b"".join(bytes(row.bytes) for row in decoded)
    if body != bytes.fromhex(_RAW) or hashlib.sha256(body).hexdigest() != _BODY:
        _bad("target body bytes differ")
    _target(facts)
    expected_entry = _expected_scan(facts)
    expected_endpoint = _expected_endpoint_scan(facts)
    receipts = (
        {
            "target_entry": expected_entry,
            "target_end_pointer": expected_endpoint,
        }
        if scans is None
        else dict(_mapping(scans, "whole-atlas scans"))
    )
    if (
        not _same(receipts.get("target_entry"), expected_entry)
        or not _same(receipts.get("target_end_pointer"), expected_endpoint)
        or set(receipts) != {"target_entry", "target_end_pointer"}
    ):
        _bad("target or endpoint reference receipt differs")
    receipt = expected_entry
    parent_edges = _parent_edge(parent)
    parent_reference = next(
        item
        for item in receipt["references"]
        if item["instruction_rva"] == "0x00378b92"
    )
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
            "sealed_instruction_count": 48,
            "register_call_encoding_audit": [
                {"register": r, "encoding": f"ff{0xd0+i:02x}"}
                for i, r in enumerate(_REGISTER_NAMES)
            ],
        },
        "function_body": {
            "role": "relationship_defined_adjacent_cluster_fourth_callee_static_boundary",
            "entry_rva": _hex(_ENTRY),
            "atlas_record_sha256": _ATLAS,
            "body_size": _SIZE,
            "body_sha256": _BODY,
            "range_start_rva": _hex(_ENTRY),
            "range_size": _SIZE,
            "target_pe_backing": _target_pe_backing(image),
            "adjacent_atlas_boundaries": _adjacent_atlas_boundaries(facts, image),
            "control_flow_graph_canonical_sha256": _CFG,
            "reviewed_points": _points(decoded),
            "direct_lua_calls": [],
            "staged_lua_dispatches": [],
            "call_r32_audit": _audit(),
            "register_call_partition_complete": True,
            "ghidra_analysis_metadata": {
                "name": "__local_unwind4",
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
        "native_calls": _native_calls(facts, second, image),
        "whole_atlas_reference_scan": receipt,
        "whole_atlas_target_end_pointer_scan": expected_endpoint,
        "method": {
            "structural_boundary": "The receipt seals 144 decoded bytes, exact predecessor and successor atlas and gap geometry, target PE backing, all nine PE-address operands, opaque FS syntax, two declared outgoing edges, and exhaustive all-atlas target-entry and target-end operand traversals.",
            "not_claimed": [
                "analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return",
                "runtime reachability, invocation, ordering, frequency, or effects",
                "contents or runtime meaning of the .data operand, either gap, or the target-end pointer",
                "computed, indirect, data-originated, un-atlased, dynamic, or Lua-side references",
            ],
        },
        "summary": {
            "reviewed_target_count": 1,
            "reviewed_target_bytes": _SIZE,
            "sealed_adjacent_boundary_count": 2,
            "sealed_gap_count": 2,
            "sealed_un_atlased_gap_bytes": 119,
            "sealed_target_pe_backing_count": 1,
            "sealed_instruction_count": 48,
            "sealed_control_flow_graph_count": 1,
            "sealed_control_flow_graph_node_count": 48,
            "sealed_control_flow_graph_edge_count": 51,
            "native_direct_edge_count": 2,
            "direct_lua_call_count": 0,
            "staged_lua_dispatch_count": 0,
            "call_r32_count": 0,
            "opaque_indirect_control_count": 0,
            "pe_address_operand_count": 9,
            "pe_immediate_operand_count": 8,
            "pe_absolute_memory_operand_count": 1,
            "non_pe_immediate_literal_count": 6,
            "segment_qualified_memory_syntax_count": 3,
            "bnd_prefixed_control_syntax_count": 0,
            "opaque_interrupt_syntax_count": 0,
            "predecessor_parent_edge_count": 1,
            "target_reference_count": 3,
            "target_reference_target_count": 1,
            "target_reference_owner_count": 3,
            "target_reference_direct_call_count": 3,
            "target_reference_other_address_count": 0,
            "target_reference_memory_operand_count": 0,
            "target_end_pointer_reference_count": 1,
            "target_end_pointer_owner_count": 1,
            "target_end_pointer_other_address_count": 1,
            "schema_violations": 0,
        },
    }
    return result


def _normalize(operation):
    try:
        return operation()
    except NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeStaticBoundaryError:
        raise
    except Exception as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeStaticBoundaryError(
            str(exc)
        ) from exc


def validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary_structure(
    evidence: Mapping[str, Any],
    adjacent_callee_cluster_static_boundary: Mapping[str, Any],
    second_callee_static_boundary: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    def run():
        evidence_object = _mapping(evidence, "evidence")
        parent_object = _mapping(
            adjacent_callee_cluster_static_boundary, "cluster parent"
        )
        second_object = _mapping(
            second_callee_static_boundary, "second-callee boundary"
        )
        direct_object = _mapping(direct_calls, "direct calls")
        facts_object = _mapping(program_facts, "program facts")
        for value, label in (
            (evidence_object, "evidence"),
            (parent_object, "cluster parent"),
            (second_object, "second-callee boundary"),
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
        expected = _evidence(parent_object, second_object, direct_object, facts_object)
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


def build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary(
    executable: Path,
    adjacent_callee_cluster_static_boundary: Mapping[str, Any],
    second_callee_static_boundary: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run():
        parent_object = _mapping(
            adjacent_callee_cluster_static_boundary, "cluster parent"
        )
        second_object = _mapping(
            second_callee_static_boundary, "second-callee boundary"
        )
        direct_object = _mapping(direct_calls, "direct calls")
        facts_object = _mapping(program_facts, "program facts")
        inventory_object = _mapping(inventory, "inventory")
        for value, label in (
            (parent_object, "cluster parent"),
            (second_object, "second-callee boundary"),
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
        scans = _whole_atlas_reference_scan(data, image, decoder, facts_object)
        result = _evidence(
            parent_object,
            second_object,
            direct_object,
            facts_object,
            rows=rows,
            image=image,
            scans=scans,
        )
        replay, replay_image, replay_digest = _load_executable(executable)
        if (
            replay_digest != digest
            or replay != data
            or replay_image.image_base != _BASE
        ):
            _bad("executable changed during exact rebuild")
        _assert_publication_safe(result)
        validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary_structure(
            result, parent_object, second_object, direct_object, facts_object
        )
        return result

    return _normalize(run)


def validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary(
    executable: Path,
    evidence: Mapping[str, Any],
    adjacent_callee_cluster_static_boundary: Mapping[str, Any],
    second_callee_static_boundary: Mapping[str, Any],
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
        second_object = _mapping(
            second_callee_static_boundary, "second-callee boundary"
        )
        direct_object = _mapping(direct_calls, "direct calls")
        facts_object = _mapping(program_facts, "program facts")
        inventory_object = _mapping(inventory, "inventory")
        _validate_json_tree(evidence_object, "evidence")
        rebuilt = build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary(
            executable,
            parent_object,
            second_object,
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


def encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary(
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
