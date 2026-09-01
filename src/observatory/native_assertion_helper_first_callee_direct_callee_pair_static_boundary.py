"""Fail-closed paired static boundary for assertion-helper first-callee children.

The pair is structural only: analysis labels, data contents, ABI, control
meaning, and run-time behaviour are deliberately retained as opaque.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections import Counter, defaultdict
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
from src.observatory.native_assertion_helper_first_callee_static_boundary import (
    ANALYSIS_KIND as PREDECESSOR_KIND,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = (
    "pe_native_assertion_helper_first_callee_direct_callee_pair_static_boundary"
)
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_PREDECESSOR = "e99d2b76879c1456c6ec44bf3fcbc38f2f50a456aae6416687f0cf1f09898da0"
_BASE = 0x400000
_TARGETS = (
    {
        "entry": 0x385BCC,
        "size": 19,
        "raw": "e8e591000085c07506b8d0408900c383c010c3",
        "body": "28c011bc3ef2bcde2aa753d405ed6eb2be53c64f42af3613725ba23fb91ae619",
        "atlas": "a8859e2355301186727a01e26a0ba71246f402b520df1907d3949e338b077b42",
        "instructions": 7,
        "cfg": "11949588cdafd6ed16fc06369d47e49d1dc92550d60d279bb596bc47d101a740",
        "nodes": 7,
        "edges": 6,
        "metadata": ("__errno", "ANALYSIS"),
        "parent": (0x38E3BC, "e80b78ffff"),
        "outgoing": (0x385BCC, 0x38EDB6, "e8e5910000"),
    },
    {
        "entry": 0x379EF2,
        "size": 16,
        "raw": "33c05050505050e879ffffff83c414c3",
        "body": "518dd4976a3fd19ac24d226d76a4e153c9abd83272da1a8ff0e1bc541c29c7ff",
        "atlas": "6835b0add89fbccbc3b5d3b7cc62209df6ad0833f48dba6047797d5769a449c6",
        "instructions": 9,
        "cfg": "93e1f9ae1f6c272859a61fd7d6b3f6a9b2e5742984d9da2dab01102e12410f63",
        "nodes": 9,
        "edges": 8,
        "metadata": ("FUN_00779ef2", "DEFAULT"),
        "parent": (0x38E3C7, "e826bbfeff"),
        "outgoing": (0x379EF9, 0x379E77, "e879ffffff"),
    },
)
_BY_ENTRY = {item["entry"]: item for item in _TARGETS}
_SCOPE = {
    "atlas_function_count": 25312,
    "atlas_body_range_count": 25490,
    "decoded_bytes": 3735718,
    "decoded_instructions": 1153814,
    "all_declared_ranges_decoded": True,
    "operand_classes": ["absolute_memory", "immediate"],
}
_SCAN_HASHES = {
    "references": "dd8b397a3e99127bca1b4a08c5be71049bccac5fe9397de827ac47adfc81dac6",
    "target_partition": "00e2038bbe88558b841ae2ea183cc228e7979033315f968371a92db86b558e9d",
    "owner_partition": "515d8ec972c02a84838d669326b121a05bd41c3f74b79d20876fef4fbca886a9",
    "target_owner_partition": "0fd6cda494caab56ec7195ab00931caed92567c3e0decf673da934e8d650e996",
    "target_reference_partition": "e5e96330374278a1164ff2e22fc6090a3836f0df411c35639fad043ede5021ea",
}
_RELOCATION_DIRECTORY = (
    0x539000,
    0x35618,
    0x510A00,
    "06630f9047636fb68afba81d89dbc1ef2f21c459b684d57d1d2bcaeb3750dfa3",
)


class NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError(RuntimeError):
    """Raised when this finite paired boundary cannot be reproduced."""


def _bad(message: str) -> None:
    raise NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError(message)


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


def _target_function(
    facts: Mapping[str, Any], item: Mapping[str, Any]
) -> Mapping[str, Any]:
    entry = item["entry"]
    function = _atlas_functions(facts).get(entry)
    metadata = item["metadata"]
    if function is None or (
        function.get("body_size"),
        function.get("body_sha256"),
        atlas_record_sha256(function),
        function.get("name"),
        function.get("name_source"),
        function.get("namespace"),
        function.get("thunk"),
    ) != (
        item["size"],
        item["body"],
        item["atlas"],
        metadata[0],
        metadata[1],
        "Global",
        False,
    ):
        _bad("target atlas record differs")
    return function


def _decode_target(item: Mapping[str, Any], raw: bytes | None = None) -> list[Any]:
    payload = bytes.fromhex(item["raw"]) if raw is None else raw
    decoder, _ = _decoder()
    decoder.detail = True
    rows = list(decoder.disasm(payload, _BASE + item["entry"]))
    if (
        len(rows) != item["instructions"]
        or b"".join(bytes(row.bytes) for row in rows) != payload
    ):
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


def _graph(item: Mapping[str, Any], rows: list[Any] | None = None) -> dict[str, Any]:
    import capstone
    import capstone.x86_const as x86

    decoded = _decode_target(item) if rows is None else rows
    graph = _with_edi_writes(
        _enhanced_cfg(decoded, _BASE, (item["entry"], item["size"]), capstone, x86),
        decoded,
        x86,
    )
    graph["caller_entry_rva"] = _hex(item["entry"])
    if (
        graph.get("node_count"),
        graph.get("edge_count"),
        _canonical_sha256(graph),
    ) != (item["nodes"], item["edges"], item["cfg"]):
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
        _bad("first-callee predecessor receipt differs")
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
            predecessor, PREDECESSOR_KIND, _PREDECESSOR, "first-callee predecessor"
        ),
        "direct_call_census": _source_identity(
            direct, DIRECT_KIND, _DIRECT, "direct-call census"
        ),
    }


def _parent_edges(predecessor: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        dict(_mapping(raw, "predecessor outgoing direct edge"))
        for raw in _array(
            _mapping(predecessor.get("native_calls"), "predecessor native calls").get(
                "outgoing_direct"
            ),
            "predecessor outgoing direct edges",
        )
    ]
    expected = {
        (item["parent"][0], item["entry"], item["parent"][1]) for item in _TARGETS
    }
    observed = set()
    for row in rows:
        instruction = _mapping(row.get("instruction"), "parent instruction")
        observed.add(
            (
                _rva(instruction.get("rva"), "parent site"),
                _rva(row.get("target_entry_rva"), "parent target"),
                None,
            )
        )
    if len(rows) != 2 or {(site, target) for site, target, _ in observed} != {
        (site, target) for site, target, _ in expected
    }:
        _bad("predecessor outgoing child edge set differs")
    result = []
    for item in _TARGETS:
        site, encoded = item["parent"]
        match = [
            row
            for row in rows
            if _rva(
                _mapping(row.get("instruction"), "parent instruction").get("rva"),
                "parent site",
            )
            == site
            and _rva(row.get("source_entry_rva"), "parent source") == 0x38E392
            and _rva(row.get("target_entry_rva"), "parent target") == item["entry"]
        ]
        if len(match) != 1 or not _same(
            match[0].get("instruction"), _instruction(site, encoded)
        ):
            _bad("predecessor parent edge differs")
        result.append(match[0])
    return result


def _relocation_receipt(image: Any | None) -> dict[str, Any]:
    result = {
        "directory": {
            "rva": _hex(_RELOCATION_DIRECTORY[0]),
            "size": _RELOCATION_DIRECTORY[1],
            "file_offset": _hex(_RELOCATION_DIRECTORY[2]),
            "sha256": _RELOCATION_DIRECTORY[3],
        },
        "highlow_site_count_inside_target": 1,
        "highlow_sites": [
            {
                "site_rva": "0x00385bd6",
                "file_offset": "0x00384fd6",
                "entry_file_offset": "0x00533160",
                "entry_raw": "d63b",
                "type": "HIGHLOW",
                "value_va": "0x008940d0",
                "value_rva": "0x004940d0",
            }
        ],
    }
    if image is None:
        return result
    rva, size, offset, digest = _RELOCATION_DIRECTORY
    if (
        image.bits != 32
        or len(image.data_directories) <= 5
        or image.data_directories[5] != (rva, size)
    ):
        _bad("base-relocation directory differs")
    if (
        image.rva_span_to_file_offset(rva, size) != offset
        or hashlib.sha256(image.data[offset : offset + size]).hexdigest() != digest
    ):
        _bad("base-relocation directory backing differs")
    cursor, end = offset, offset + size
    sites_by_target: dict[int, list[tuple[int, int, int, int, str]]] = {
        item["entry"]: [] for item in _TARGETS
    }
    while cursor < end:
        page, block_size = struct.unpack_from("<II", image.data, cursor)
        if block_size < 8 or cursor + block_size > end:
            _bad("base-relocation block malformed")
        for at in range(cursor + 8, cursor + block_size, 2):
            entry = struct.unpack_from("<H", image.data, at)[0]
            site = page + (entry & 0xFFF)
            if entry >> 12 == 3:
                owner = next(
                    (
                        item
                        for item in _TARGETS
                        if item["entry"] <= site < item["entry"] + item["size"]
                    ),
                    None,
                )
                if owner is not None:
                    file_offset = image.rva_span_to_file_offset(site, 4)
                    if file_offset is None:
                        _bad("HIGHLOW relocation site is not file-backed")
                    sites_by_target[owner["entry"]].append(
                        (
                            site,
                            at,
                            file_offset,
                            struct.unpack_from("<I", image.data, file_offset)[0],
                            image.data[at : at + 2].hex(),
                        )
                    )
        cursor += block_size
    if (
        cursor != end
        or sites_by_target[0x385BCC]
        != [(0x385BD6, 0x533160, 0x384FD6, 0x8940D0, "d63b")]
        or sites_by_target[0x379EF2]
    ):
        _bad("HIGHLOW relocation frontier differs")
    return result


def _native_calls(facts: Mapping[str, Any], image: Any | None = None) -> dict[str, Any]:
    functions, edges = _atlas_functions(facts), _edges(facts)
    targets = []
    for item in _TARGETS:
        _target_function(facts, item)
        site, target, encoded = item["outgoing"]
        edge = edges.get(site)
        if edge is None or (
            _rva(edge.get("source_entry_rva"), "outgoing source"),
            _rva(edge.get("target_entry_rva"), "outgoing target entry"),
            _rva(edge.get("target_rva"), "outgoing target"),
        ) != (item["entry"], target, target):
            _bad("outgoing direct edge differs")
        source_sites = {
            at
            for at, candidate in edges.items()
            if _rva(candidate.get("source_entry_rva"), "outgoing source")
            == item["entry"]
        }
        if source_sites != {site} or target not in functions:
            _bad("outgoing direct-edge partition differs")
        targets.append(
            {
                "entry_rva": _hex(item["entry"]),
                "outgoing_direct": [
                    {
                        "role": "opaque_native_direct_edge",
                        "instruction": _instruction(site, encoded),
                        "source_entry_rva": _hex(item["entry"]),
                        "target_entry_rva": _hex(target),
                        "target_rva": _hex(target),
                        "target_atlas_record_sha256": atlas_record_sha256(
                            functions[target]
                        ),
                        "callee_behavior_opaque": True,
                        "ghidra_declared_direct_edge": _normalized_edge(edge),
                    }
                ],
                "outgoing_direct_partition_complete": True,
            }
        )
    operand = {
        "role": "opaque_pe_immediate_data_address_syntax",
        "instruction": _instruction(0x385BD5, "b8d0408900"),
        "operand_class": "immediate",
        "operand_index": 1,
        "operand_access": "read",
        "operand_va": "0x008940d0",
        "operand_rva": "0x004940d0",
        "section_name": ".data",
        "section_rva": "0x00492000",
        "section_characteristics": "0xc0000040",
        "section_writable": True,
        "section_virtual_size": "0x000471cc",
        "section_raw_size": "0x00024800",
        "section_raw_offset": "0x00490200",
        "file_backed": True,
        "file_offset": "0x004922d0",
        "contents_or_runtime_behavior_opaque": True,
    }
    if image is not None:
        rva = 0x4940D0
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
            image.rva_to_file_offset(rva),
        ) != (".data", 0x492000, 0xC0000040, 0x471CC, 0x24800, 0x490200, 0x4922D0):
            _bad("PE data-address section binding differs")
    return {
        "targets": targets,
        "direct_lua_calls": [],
        "direct_lua_partition_complete": True,
        "staged_lua_dispatches": [],
        "staged_lua_dispatch_partition_complete": True,
        "opaque_indirect_controls": [],
        "indirect_control_partition_complete": True,
        "pe_address_operands": [operand],
        "pe_address_operand_partition_complete": True,
        "non_pe_immediate_literals": [
            {
                "target_entry_rva": "0x00385bcc",
                "role": "opaque_data_literal",
                "instruction": _instruction(0x385BDB, "83c010"),
                "operand_index": 1,
                "value_u32": "0x00000010",
            },
            {
                "target_entry_rva": "0x00379ef2",
                "role": "opaque_data_literal",
                "instruction": _instruction(0x379EFE, "83c414"),
                "operand_index": 1,
                "value_u32": "0x00000014",
            },
        ],
        "non_pe_immediate_literal_partition_complete": True,
        "segment_qualified_memory_syntax": [],
        "segment_qualified_memory_partition_complete": True,
        "bnd_prefixed_control_syntax": [],
        "bnd_prefixed_control_partition_complete": True,
        "opaque_interrupt_syntax": [],
        "opaque_interrupt_partition_complete": True,
        "call_r32_audit": _empty_register_calls(),
        "register_call_partition_complete": True,
        "import_and_iat_body_controls": [],
        "import_and_iat_body_control_partition_complete": True,
        "first_target_base_relocation_scan": _relocation_receipt(image),
        "second_target_base_relocation_scan": {
            "highlow_site_count_inside_target": 0,
            "highlow_sites": [],
        },
    }


def _e8(site: int, target: int) -> bytes:
    return b"\xe8" + struct.pack("<i", target - (site + 5))


def _expected_scan(facts: Mapping[str, Any]) -> dict[str, Any]:
    functions, edges = _atlas_functions(facts), _edges(facts)
    records = []
    for site, edge in sorted(edges.items()):
        target = _rva(edge.get("target_entry_rva"), "reference target entry")
        if target not in _BY_ENTRY:
            continue
        owner = _rva(edge.get("source_entry_rva"), "reference source")
        if owner not in functions:
            _bad("reference owner is missing from atlas")
        encoded = _e8(site, target)
        records.append(
            {
                "instruction_rva": _hex(site),
                "instruction_size": 5,
                "instruction_sha256": hashlib.sha256(encoded).hexdigest(),
                "owner_entry_rva": _hex(owner),
                "owner_atlas_record_sha256": atlas_record_sha256(functions[owner]),
                "target_rva": _hex(target),
                "target_atlas_record_sha256": _BY_ENTRY[target]["atlas"],
                "target_va": _hex(_BASE + target),
                "operand_class": "immediate",
                "operand_index": 0,
                "use_class": "direct_call",
                "call_form": "x86_relative_near_call_e8",
                "ghidra_declared_direct_edge": _normalized_edge(edge),
            }
        )
    records.sort(key=lambda row: (row["target_rva"], row["instruction_rva"]))
    by_target = Counter(row["target_rva"] for row in records)
    by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_target_owner: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_owner[row["owner_entry_rva"]].append(row)
        by_target_owner[(row["target_rva"], row["owner_entry_rva"])].append(row)
    target_partition = [
        {
            "target_rva": _hex(item["entry"]),
            "target_atlas_record_sha256": item["atlas"],
            "reference_count": by_target[_hex(item["entry"])],
            "owner_count": len(
                {
                    row["owner_entry_rva"]
                    for row in records
                    if row["target_rva"] == _hex(item["entry"])
                }
            ),
        }
        for item in _TARGETS
    ]
    owner_partition = [
        {
            "owner_entry_rva": owner,
            "owner_atlas_record_sha256": rows[0]["owner_atlas_record_sha256"],
            "reference_count": len(rows),
        }
        for owner, rows in sorted(by_owner.items())
    ]
    target_owner_partition = [
        {
            "target_rva": target,
            "owner_entry_rva": owner,
            "owner_atlas_record_sha256": rows[0]["owner_atlas_record_sha256"],
            "reference_count": len(rows),
        }
        for (target, owner), rows in sorted(by_target_owner.items())
    ]
    target_reference_partition = [
        {
            "target_rva": _hex(item["entry"]),
            "target_atlas_record_sha256": item["atlas"],
            "reference_count": by_target[_hex(item["entry"])],
        }
        for item in _TARGETS
    ]
    hashes = {
        "references": _compact(records),
        "target_partition": _compact(target_partition),
        "owner_partition": _compact(owner_partition),
        "target_owner_partition": _compact(target_owner_partition),
        "target_reference_partition": _compact(target_reference_partition),
    }
    if (
        hashes != _SCAN_HASHES
        or (len(records), len(owner_partition), len(target_owner_partition))
        != (479, 202, 350)
        or target_partition
        != [
            {
                "target_rva": "0x00385bcc",
                "target_atlas_record_sha256": _TARGETS[0]["atlas"],
                "reference_count": 308,
                "owner_count": 202,
            },
            {
                "target_rva": "0x00379ef2",
                "target_atlas_record_sha256": _TARGETS[1]["atlas"],
                "reference_count": 171,
                "owner_count": 148,
            },
        ]
    ):
        _bad("paired target reference partition differs")
    return {
        "target_rvas": [_hex(item["entry"]) for item in _TARGETS],
        "target_vas": [_hex(_BASE + item["entry"]) for item in _TARGETS],
        "scope": dict(_SCOPE),
        "references": records,
        "target_partition": target_partition,
        "owner_partition": owner_partition,
        "target_owner_partition": target_owner_partition,
        "target_reference_partition": target_reference_partition,
        "partition_sha256": hashes,
        "references_canonical_sha256": hashes["references"],
        "aggregates": {
            "reference_count": 479,
            "target_count": 2,
            "owner_count": 202,
            "target_owner_count": 350,
            "direct_call_count": 479,
            "comparison_count": 0,
            "other_address_count": 0,
            "memory_operand_count": 0,
        },
    }


def _whole_atlas_reference_scan(
    data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]
) -> dict[str, Any]:
    import capstone.x86_const as x86

    found, totals = [], [0, 0, 0]
    targets = {_BASE + item["entry"]: item["entry"] for item in _TARGETS}
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
                    if value in targets:
                        found.append(
                            (
                                row.address - image.image_base,
                                owner,
                                index,
                                bytes(row.bytes),
                                kind,
                                targets[value],
                            )
                        )
    expected = _expected_scan(facts)
    expected_rows = [
        (
            _rva(row["instruction_rva"], "expected scan site"),
            _rva(row["owner_entry_rva"], "expected scan owner"),
            row["operand_index"],
            _e8(
                _rva(row["instruction_rva"], "expected scan site"),
                _rva(row["target_rva"], "expected scan target"),
            ),
            "immediate",
            _rva(row["target_rva"], "expected scan target"),
        )
        for row in expected["references"]
    ]
    found.sort(key=lambda row: (_hex(row[5]), _hex(row[0])))
    if tuple(totals) != (25490, 3735718, 1153814) or found != expected_rows:
        _bad("all-operand paired target reference traversal differs")
    return expected


def _evidence(
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    rows_by_target: Mapping[int, list[Any]] | None = None,
    image: Any | None = None,
    scan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prerequisites = _preflight(predecessor, direct, facts)
    bodies = []
    for item in _TARGETS:
        rows = (
            _decode_target(item)
            if rows_by_target is None
            else rows_by_target[item["entry"]]
        )
        raw = b"".join(bytes(row.bytes) for row in rows)
        if (
            raw != bytes.fromhex(item["raw"])
            or hashlib.sha256(raw).hexdigest() != item["body"]
        ):
            _bad("target body bytes differ")
        _target_function(facts, item)
        bodies.append(
            {
                "role": "relationship_defined_assertion_helper_first_callee_direct_callee_static_boundary",
                "entry_rva": _hex(item["entry"]),
                "atlas_record_sha256": item["atlas"],
                "body_size": item["size"],
                "body_sha256": item["body"],
                "range_start_rva": _hex(item["entry"]),
                "range_size": item["size"],
                "control_flow_graph_canonical_sha256": item["cfg"],
                "reviewed_points": _points(rows),
                "ghidra_analysis_metadata": {
                    "name": item["metadata"][0],
                    "namespace": "Global",
                    "name_source": item["metadata"][1],
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
        )
    expected = _expected_scan(facts)
    supplied = expected if scan is None else dict(scan)
    if not _same(supplied, expected):
        _bad("paired target reference receipt differs")
    parents = _parent_edges(predecessor)
    if {row["instruction"]["rva"] for row in parents} != {
        row["instruction_rva"]
        for row in supplied["references"]
        if row["owner_entry_rva"] == "0x0038e392"
    }:
        _bad("predecessor edges do not join exhaustive reference scan")
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
            "sealed_instruction_count": 16,
            "sealed_instruction_count_total": 16,
            "register_call_encoding_audit": [
                {"register": register, "encoding": f"ff{0xD0 + index:02x}"}
                for index, register in enumerate(_REGISTER_NAMES)
            ],
        },
        "function_bodies": bodies,
        "control_flow_graphs": [
            _graph(
                item,
                (
                    _decode_target(item)
                    if rows_by_target is None
                    else rows_by_target[item["entry"]]
                ),
            )
            for item in _TARGETS
        ],
        "predecessor_parent_edges": parents,
        "native_calls": calls,
        "whole_atlas_reference_scan": supplied,
        "method": {
            "structural_boundary": "The paired receipt seals 35 decoded PE bytes, both CFGs, two retained opaque child edges, one raw-backed writable .data address plus its HIGHLOW relocation, two predecessor joins, and the exhaustive 479-reference atlas partition.",
            "not_claimed": [
                "analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return",
                "runtime reachability, invocation, ordering, frequency, or effects",
                "contents or runtime meaning of the PE data address",
                "computed, indirect, data, un-atlased, dynamic, or Lua-side references",
            ],
        },
        "summary": {
            "reviewed_target_count": 2,
            "reviewed_target_bytes": 35,
            "sealed_instruction_count": 16,
            "sealed_control_flow_graph_count": 2,
            "sealed_control_flow_graph_node_count": 16,
            "sealed_control_flow_graph_edge_count": 14,
            "native_direct_edge_count": 2,
            "direct_lua_call_count": 0,
            "staged_lua_dispatch_count": 0,
            "call_r32_count": 0,
            "opaque_indirect_control_count": 0,
            "bnd_prefixed_control_syntax_count": 0,
            "segment_qualified_memory_syntax_count": 0,
            "opaque_interrupt_syntax_count": 0,
            "import_and_iat_body_control_count": 0,
            "non_pe_immediate_literal_count": 2,
            "pe_address_operand_count": 1,
            "highlow_relocation_site_count": 1,
            "target_reference_count": 479,
            "target_reference_owner_count": 202,
            "target_reference_direct_call_count": 479,
            "target_reference_memory_operand_count": 0,
            "target_reference_other_address_count": 0,
            "schema_violations": 0,
        },
    }


def _normalize(operation: Any) -> Any:
    try:
        return operation()
    except NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError:
        raise
    except Exception as exc:
        raise NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError(
            str(exc)
        ) from exc


def build_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
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
        decoded = {}
        for item in _TARGETS:
            offset = image.rva_to_file_offset(item["entry"])
            if offset is None or data[offset : offset + item["size"]] != bytes.fromhex(
                item["raw"]
            ):
                _bad("executable target bytes differ")
            decoded[item["entry"]] = _decode_target(
                item, data[offset : offset + item["size"]]
            )
        decoder, _ = _decoder()
        result = _evidence(
            predecessor,
            direct,
            facts,
            rows_by_target=decoded,
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
        validate_native_assertion_helper_first_callee_direct_callee_pair_static_boundary_structure(
            result, predecessor, direct, facts
        )
        return result

    return _normalize(run)


def encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
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


def validate_native_assertion_helper_first_callee_direct_callee_pair_static_boundary_structure(
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


def validate_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
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
        rebuilt = build_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
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
