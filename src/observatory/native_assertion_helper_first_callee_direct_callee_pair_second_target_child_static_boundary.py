"""Fail-closed structural receipt for the second direct-callee pair child.

This seals the finite bytes at ``0x00379e77`` and their atlas relationships.
All analysis labels, imports, control syntax, and execution semantics remain
opaque.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import capstone.x86_const as x86

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
    _source_identity,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_KIND,
    SUPPORTED_CAPSTONE_VERSION,
    _decoder,
    _load_executable,
    validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_assertion_helper_first_callee_direct_callee_pair_static_boundary import (
    ANALYSIS_KIND as PREDECESSOR_KIND,
)

SCHEMA_VERSION = 2
ANALYSIS_KIND = "pe_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_v2"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_SUPERSEDES = {
    "artifact": "windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary.json",
    "raw_sha256": "25b174666130d3a5120dc4f01a66cdf3c5cdf657dd9010a2ba89f4137c902d0e",
    "canonical_sha256": "149115c259e411889adc3acee6bccb5c84a09b7ac8acafa0060726d5ee3703ed",
    "reason": "Correct the case-sensitive ESI register-call audit generator; executable "
    "and structural boundary unchanged.",
    "corrected_path": "native_calls.call_r32_audit[6].call_rvas",
}

_BASE = 0x400000
_SCOPE = {
    "atlas_function_count": 25312,
    "atlas_body_range_count": 25490,
    "decoded_bytes": 3735718,
    "decoded_instructions": 1153814,
    "all_declared_ranges_decoded": True,
    "operand_classes": ["absolute_memory", "immediate"],
}

_ENTRY, _SIZE = 0x379E77, 122
_RAW = "8bff558bec51a1283f890033c58945fc56e8294f010085c074358bb05c03000085f6742bff7518ff7514ff7510ff750cff75088bceff1580657d00ffd68b4dfc83c41433cd5ee808d6fdff8be55dc3ff75188b35283f89008bceff7514333580708b0083e11fff7510d3ceff750cff750885f675bee82e000000"
_BODY = "75be7b046154abadb4a60fb861c968167e700151dae6527a6e49186be2f67a6c"
_ATLAS = "7c9d8be241338ff5da672410792f04d2c6e1f74186ea42a3881000790bbafd2f"
_CFG = "1a93ebedb419e86b6ddd0c7bde28fe2fc0f151c130ae7229e73ccdec1b77dd1f"
_PREDECESSOR = "e1a04d9e847b1ec61e57e24cb02c03eea6b35aae5a1ad059cdd4339ebb939378"
_PARENT = (
    0x379EF9,
    0x379EF2,
    "e879ffffff",
    "6835b0add89fbccbc3b5d3b7cc62209df6ad0833f48dba6047797d5769a449c6",
)
_OUTGOING = (
    (0x379E88, 0x38EDB6, "e8294f0100"),
    (0x379EBD, 0x3574CA, "e808d6fdff"),
    (0x379EEC, 0x379F1F, "e82e000000"),
)
_INCOMING = ((0x379EF9, 0x379EF2, "e879ffffff"), (0x379F0C, 0x379F02, "e866ffffff"))
_RELOCS = (
    (0x379E7E, 0x532E90, 0x37927E, 0x893F28, "7e3e"),
    (0x379EAE, 0x532E92, 0x3792AE, 0x7D6580, "ae3e"),
    (0x379ECB, 0x532E94, 0x3792CB, 0x893F28, "cb3e"),
    (0x379ED6, 0x532E96, 0x3792D6, 0x8B7080, "d63e"),
)


class NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError(
    RuntimeError
):
    """Raised when this relationship-defined child cannot be reproduced."""


def _bad(message: str) -> None:
    raise NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError(
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
    value = bytes.fromhex(raw)
    return {
        "rva": _hex(rva),
        "size": len(value),
        "sha256": hashlib.sha256(value).hexdigest(),
    }


def _edges(facts: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for value in _array(facts.get("ghidra_declared_direct_calls"), "declared calls"):
        edge = _mapping(value, "declared call")
        site = _rva(edge.get("instruction_rva"), "declared call site")
        if site in result:
            _bad("duplicate declared direct call")
        result[site] = edge
    return result


def _edge(edge: Mapping[str, Any]) -> dict[str, Any]:
    name = edge.get("target_name")
    if type(name) is not str:
        _bad("declared edge lacks analysis name")
    return {
        "instruction_rva": _hex(_rva(edge.get("instruction_rva"), "edge site")),
        "source_entry_rva": _hex(_rva(edge.get("source_entry_rva"), "edge source")),
        "target_entry_rva": _hex(
            _rva(edge.get("target_entry_rva"), "edge target entry")
        ),
        "target_rva": _hex(_rva(edge.get("target_rva"), "edge target")),
        "target_name_sha256": hashlib.sha256(name.encode()).hexdigest(),
    }


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


def _preflight(
    predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]
) -> dict[str, Any]:
    identity = dict(_mapping(facts.get("identity"), "program facts identity"))
    if (
        identity.get("executable_sha256") != _EXE
        or not _same(predecessor.get("build_identity"), identity)
        or not _same(direct.get("build_identity"), identity)
    ):
        _bad("prerequisite identity differs")
    if (
        predecessor.get("analysis_kind") != PREDECESSOR_KIND
        or _canonical_sha256(predecessor) != _PREDECESSOR
    ):
        _bad("direct-callee pair predecessor differs")
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
        "direct_callee_pair_static_boundary": _source_identity(
            predecessor,
            PREDECESSOR_KIND,
            _PREDECESSOR,
            "direct-callee pair predecessor",
        ),
        "direct_call_census": _source_identity(
            direct, DIRECT_KIND, _DIRECT, "direct-call census"
        ),
    }


def _target(facts: Mapping[str, Any]) -> Mapping[str, Any]:
    function = _atlas_functions(facts).get(_ENTRY)
    if function is None or (
        function.get("body_size"),
        function.get("body_sha256"),
        atlas_record_sha256(function),
        function.get("name"),
        function.get("name_source"),
        function.get("namespace"),
        function.get("thunk"),
    ) != (_SIZE, _BODY, _ATLAS, "FUN_00779e77", "DEFAULT", "Global", False):
        _bad("second child target atlas record differs")
    return function


def _parent(
    predecessor: Mapping[str, Any], facts: Mapping[str, Any]
) -> list[dict[str, Any]]:
    del facts
    calls = _mapping(predecessor.get("native_calls"), "predecessor native calls")
    targets = [
        dict(_mapping(value, "predecessor target row"))
        for value in _array(calls.get("targets"), "predecessor targets")
    ]
    matches = [
        row
        for row in targets
        if _rva(row.get("entry_rva"), "predecessor target entry") == _PARENT[1]
    ]
    if len(matches) != 1:
        _bad("second child predecessor target partition differs")
    outgoing = _array(matches[0].get("outgoing_direct"), "predecessor outgoing")
    if len(outgoing) != 1:
        _bad("second child predecessor outgoing partition differs")
    row = dict(_mapping(outgoing[0], "predecessor child edge"))
    instruction = _mapping(row.get("instruction"), "predecessor instruction")
    if (
        _rva(instruction.get("rva"), "predecessor site"),
        _rva(row.get("source_entry_rva"), "predecessor source"),
        _rva(row.get("target_entry_rva"), "predecessor target"),
        row.get("target_atlas_record_sha256"),
    ) != (_PARENT[0], _PARENT[1], _ENTRY, _ATLAS) or not _same(
        instruction, _instruction(_PARENT[0], _PARENT[2])
    ):
        _bad("second child predecessor edge differs")
    return [row]


def _decode(raw: bytes = bytes.fromhex(_RAW)) -> list[Any]:
    decoder, _ = _decoder()
    decoder.detail = True
    rows = list(decoder.disasm(raw, _BASE + _ENTRY))
    if len(rows) != 43 or b"".join(bytes(row.bytes) for row in rows) != raw:
        _bad("second child bytes do not decode exactly")
    return rows


def _graph(rows: list[Any] | None = None) -> dict[str, Any]:
    """Build the deliberately finite graph with final E8 treated as terminal.

    The declared body ends immediately after E8 at 0x379eec; accepting a
    fallthrough would silently extend it into unowned CC bytes.
    """
    if rows is None:
        decoder, _ = _decoder()
        decoder.detail = True
        decoded = list(decoder.disasm(bytes.fromhex(_RAW), _BASE + _ENTRY))
    else:
        decoded = rows
    if len(decoded) != 43 or b"".join(
        bytes(row.bytes) for row in decoded
    ) != bytes.fromhex(_RAW):
        _bad("second child instruction decode differs")
    by_rva = {row.address - _BASE: row for row in decoded}
    nodes = []
    for row in decoded:
        rva = row.address - _BASE
        raw = bytes(row.bytes)
        _, writes = row.regs_access()
        names = {row.reg_name(value).lower() for value in writes}
        successor: list[int]
        if rva in (0x379E8F, 0x379E99, 0x379EEA):
            target = int(row.operands[0].imm) - _BASE
            successor = sorted({target, rva + len(raw)})
            flow = "direct_conditional_branch"
        elif rva == 0x379EEC:
            successor, flow = [], "terminal"
        elif row.group(1):  # Capstone CS_GRP_JUMP is handled above.
            _bad("unexpected control syntax")
        elif row.group(2):  # CS_GRP_CALL; all remaining calls fall through.
            successor, flow = [rva + len(raw)], "call_fallthrough"
        elif row.group(3):
            successor, flow = [], "terminal"
        else:
            successor, flow = [rva + len(raw)], "fallthrough"
        if any(value not in by_rva for value in successor):
            _bad("second child CFG escapes declared body")
        nodes.append(
            {
                "rva": _hex(rva),
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "writes_esi": "esi" in names,
                "writes_ebx": "ebx" in names,
                "writes_edi": "edi" in names,
                "writes_esp": "esp" in names,
                "flow_kind": flow,
                "successor_rvas": [_hex(value) for value in successor],
            }
        )
    graph = {
        "caller_entry_rva": _hex(_ENTRY),
        "range_start_rva": _hex(_ENTRY),
        "range_size": _SIZE,
        "nodes": nodes,
        "node_count": len(nodes),
        "edge_count": sum(len(row["successor_rvas"]) for row in nodes),
    }
    if (graph["node_count"], graph["edge_count"], _canonical_sha256(graph)) != (
        43,
        44,
        _CFG,
    ):
        _bad("second child control-flow graph differs")
    return graph


def _control_slot(image: Any | None) -> dict[str, Any]:
    expected = {
        "slot_va": "0x007d6580",
        "slot_rva": "0x003d6580",
        "slot_file_offset": "0x003d5580",
        "slot_raw": "707e4000",
        "slot_raw_sha256": "1a72a46736a7f349cfdc7c8851816c53aabe6830052b8b24e431d93ee4e8f52b",
        "section_name": ".rdata",
        "section_rva": "0x003d6000",
        "section_characteristics": "0x40000040",
        "section_writable": False,
        "contents_or_runtime_behavior_opaque": True,
    }
    # This slot is exactly at the exclusive end of the IAT directory.  It is
    # therefore an ordinary raw-backed rdata pointer, never an import binding.
    if image is not None:
        if (
            image.data_directories[12] != (0x3D6000, 0x580)
            or image.rva_to_file_offset(0x3D6580) != 0x3D5580
        ):
            _bad("second child raw control-slot binding differs")
        if image.data[0x3D5580:0x3D5584].hex() != "707e4000":
            _bad("second child raw control-slot bytes differ")
    return expected


def _relocations(image: Any | None) -> dict[str, Any]:
    if image is not None:
        if (
            image.data_directories[5] != (0x539000, 0x35618)
            or image.rva_span_to_file_offset(0x539000, 0x35618) != 0x510A00
        ):
            _bad("second child relocation directory differs")
    return {
        "directory": {
            "rva": "0x00539000",
            "size": 0x35618,
            "file_offset": "0x00510a00",
            "sha256": "06630f9047636fb68afba81d89dbc1ef2f21c459b684d57d1d2bcaeb3750dfa3",
        },
        "highlow_site_count_inside_target": len(_RELOCS),
        "highlow_sites": [
            {
                "site_rva": _hex(site),
                "entry_file_offset": _hex(at),
                "file_offset": _hex(file),
                "entry_raw": raw,
                "type": "HIGHLOW",
                "value_va": _hex(value),
                "value_rva": _hex(value - _BASE),
            }
            for site, at, file, value, raw in _RELOCS
        ],
    }


def _register_calls() -> list[dict[str, Any]]:
    return [
        {"register": name, "call_rvas": ["0x00379eb2"] if name == "ESI" else []}
        for name in _REGISTER_NAMES
    ]


def _native_calls(facts: Mapping[str, Any], image: Any | None = None) -> dict[str, Any]:
    _target(facts)
    edges = _edges(facts)
    functions = _atlas_functions(facts)
    outgoing = []
    for site, target, raw in _OUTGOING:
        edge, function = edges.get(site), functions.get(target)
        if (
            edge is None
            or function is None
            or (
                _rva(edge.get("source_entry_rva"), "source"),
                _rva(edge.get("target_entry_rva"), "target"),
            )
            != (_ENTRY, target)
        ):
            _bad("second child outgoing direct edge differs")
        outgoing.append(
            {
                "role": "opaque_native_direct_edge",
                "instruction": _instruction(site, raw),
                "source_entry_rva": _hex(_ENTRY),
                "target_entry_rva": _hex(target),
                "target_rva": _hex(target),
                "target_atlas_record_sha256": atlas_record_sha256(function),
                "callee_behavior_opaque": True,
                "ghidra_declared_direct_edge": _edge(edge),
            }
        )
    if {
        site
        for site, edge in edges.items()
        if _rva(edge.get("source_entry_rva"), "source") == _ENTRY
    } != {item[0] for item in _OUTGOING}:
        _bad("second child outgoing direct partition differs")
    data = []
    for site, raw, va in (
        (0x379E7D, "a1283f8900", 0x893F28),
        (0x379EC9, "8b35283f8900", 0x893F28),
        (0x379ED4, "333580708b00", 0x8B7080),
    ):
        rva = va - _BASE
        backed = rva == 0x493F28
        data.append(
            {
                "role": "opaque_absolute_memory_data_address_syntax",
                "instruction": _instruction(site, raw),
                "operand_class": "absolute_memory",
                "operand_index": 1,
                "operand_access": "read",
                "operand_va": _hex(va),
                "operand_rva": _hex(rva),
                "section_name": ".data",
                "section_rva": "0x00492000",
                "section_characteristics": "0xc0000040",
                "section_writable": True,
                "section_virtual_size": "0x000471cc",
                "section_raw_size": "0x00024800",
                "section_raw_offset": "0x00490200",
                "file_backed": backed,
                "file_offset": "0x00492128" if backed else None,
                "contents_or_runtime_behavior_opaque": True,
            }
        )
    controls = [
        {
            "role": "opaque_register_indirect_call",
            "instruction": _instruction(0x379EB2, "ffd6"),
            "register": "esi",
            "contents_or_runtime_behavior_opaque": True,
        },
        {
            "role": "opaque_absolute_memory_indirect_control_syntax",
            "instruction": _instruction(0x379EAC, "ff1580657d00"),
            "control_syntax": "call_absolute_memory",
            "operand_class": "absolute_memory",
            "operand_index": 0,
            "operand_access": "read",
            "control_slot": _control_slot(image),
            "contents_or_runtime_behavior_opaque": True,
        },
    ]
    data.append(
        {
            "role": "opaque_absolute_memory_rdata_control_slot_syntax",
            "instruction": _instruction(0x379EAC, "ff1580657d00"),
            "operand_class": "absolute_memory",
            "operand_index": 0,
            "operand_access": "read",
            "operand_va": "0x007d6580",
            "operand_rva": "0x003d6580",
            "section_name": ".rdata",
            "section_rva": "0x003d6000",
            "section_characteristics": "0x40000040",
            "section_writable": False,
            "file_backed": True,
            "file_offset": "0x003d5580",
            "contents_or_runtime_behavior_opaque": True,
        }
    )
    return {
        "outgoing_direct": outgoing,
        "outgoing_direct_partition_complete": True,
        "direct_lua_calls": [],
        "direct_lua_partition_complete": True,
        "staged_lua_dispatches": [],
        "staged_lua_dispatch_partition_complete": True,
        "opaque_indirect_controls": controls,
        "indirect_control_partition_complete": True,
        "import_and_iat_body_controls": [],
        "import_and_iat_body_control_partition_complete": True,
        "pe_address_operands": data,
        "pe_address_operand_partition_complete": True,
        "non_pe_immediate_literals": [
            {
                "role": "opaque_data_literal",
                "instruction": _instruction(0x379EB7, "83c414"),
                "operand_index": 1,
                "value_u32": "0x00000014",
            },
            {
                "role": "opaque_data_literal",
                "instruction": _instruction(0x379EDA, "83e11f"),
                "operand_index": 1,
                "value_u32": "0x0000001f",
            },
        ],
        "non_pe_immediate_literal_partition_complete": True,
        "segment_qualified_memory_syntax": [],
        "segment_qualified_memory_partition_complete": True,
        "bnd_prefixed_control_syntax": [],
        "bnd_prefixed_control_partition_complete": True,
        "opaque_interrupt_syntax": [],
        "opaque_interrupt_partition_complete": True,
        "call_r32_audit": _register_calls(),
        "register_call_partition_complete": True,
        "base_relocation_scan": _relocations(image),
    }


def _expected_scan(facts: Mapping[str, Any]) -> dict[str, Any]:
    edges, functions = _edges(facts), _atlas_functions(facts)
    rows = []
    for site, owner, raw in _INCOMING:
        edge, function = edges.get(site), functions.get(owner)
        if edge is None or function is None:
            _bad("second child incoming edge differs")
        rows.append(
            {
                "instruction_rva": _hex(site),
                "instruction_size": 5,
                "instruction_sha256": hashlib.sha256(bytes.fromhex(raw)).hexdigest(),
                "owner_entry_rva": _hex(owner),
                "owner_atlas_record_sha256": atlas_record_sha256(function),
                "target_rva": _hex(_ENTRY),
                "target_atlas_record_sha256": _ATLAS,
                "target_va": _hex(_BASE + _ENTRY),
                "operand_class": "immediate",
                "operand_index": 0,
                "use_class": "direct_call",
                "call_form": "x86_relative_near_call_e8",
                "ghidra_declared_direct_edge": _edge(edge),
            }
        )
    owners = [
        {
            "owner_entry_rva": row["owner_entry_rva"],
            "owner_atlas_record_sha256": row["owner_atlas_record_sha256"],
            "reference_count": 1,
        }
        for row in rows
    ]
    target = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 2,
            "owner_count": 2,
        }
    ]
    target_owner = [{"target_rva": _hex(_ENTRY), **row} for row in owners]
    target_ref = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS,
            "reference_count": 2,
        }
    ]
    hashes = {
        "references": _compact(rows),
        "target_partition": _compact(target),
        "owner_partition": _compact(owners),
        "target_owner_partition": _compact(target_owner),
        "target_reference_partition": _compact(target_ref),
    }
    return {
        "target_rvas": [_hex(_ENTRY)],
        "target_vas": [_hex(_BASE + _ENTRY)],
        "scope": dict(_SCOPE),
        "references": rows,
        "target_partition": target,
        "owner_partition": owners,
        "target_owner_partition": target_owner,
        "target_reference_partition": target_ref,
        "partition_sha256": hashes,
        "references_canonical_sha256": hashes["references"],
        "aggregates": {
            "reference_count": 2,
            "target_count": 1,
            "owner_count": 2,
            "target_owner_count": 2,
            "direct_call_count": 2,
            "comparison_count": 0,
            "other_address_count": 0,
            "memory_operand_count": 0,
        },
    }


def _scan(
    data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]
) -> dict[str, Any]:
    """Exact replay scans every atlas operand, then requires the sealed result."""
    expected = _expected_scan(facts)
    found = []
    decoder.detail = True
    for owner, function in sorted(_atlas_functions(facts).items()):
        for span in _array(function.get("ranges"), "atlas range"):
            item = _mapping(span, "atlas range")
            start = _rva(item.get("start_rva"), "range start")
            size = item.get("size")
            if type(size) is not int or size <= 0:
                _bad("invalid atlas range")
            rows = _decode_range(data, image, start, size, decoder)
            for row in rows:
                for index, operand in enumerate(row.operands):
                    if operand.type == x86.X86_OP_IMM:
                        target = int(operand.imm) & 0xFFFFFFFF
                    elif (
                        operand.type == x86.X86_OP_MEM
                        and operand.mem.segment
                        == operand.mem.base
                        == operand.mem.index
                        == x86.X86_REG_INVALID
                    ):
                        target = int(operand.mem.disp) & 0xFFFFFFFF
                    else:
                        continue
                    if target == image.image_base + _ENTRY:
                        if not (
                            index == 0
                            and row.id == x86.X86_INS_CALL
                            and bytes(row.bytes)[0] == 0xE8
                        ):
                            _bad("unreviewed second-child target reference syntax")
                        found.append(row.address - image.image_base)
    if found != [site for site, _, _ in _INCOMING]:
        _bad("second child exhaustive reference frontier differs")
    return expected


def _evidence(
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    rows: list[Any] | None = None,
    image: Any | None = None,
    scan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    decoded = _decode() if rows is None else rows
    raw = b"".join(bytes(row.bytes) for row in decoded)
    if raw != bytes.fromhex(_RAW) or hashlib.sha256(raw).hexdigest() != _BODY:
        _bad("child body differs")
    _target(facts)
    expected_scan = _expected_scan(facts)
    received_scan = expected_scan if scan is None else dict(scan)
    if not _same(received_scan, expected_scan):
        _bad("target-reference receipt differs")
    parent = _parent(predecessor, facts)
    if parent[0]["instruction"]["rva"] not in {
        row["instruction_rva"] for row in received_scan["references"]
    }:
        _bad("predecessor edge does not join scan")
    value = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "supersedes": dict(_SUPERSEDES),
        "build_identity": dict(
            _mapping(facts.get("identity"), "program facts identity")
        ),
        **_preflight(predecessor, direct, facts),
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "sealed_instruction_count": 43,
            "register_call_encoding_audit": [
                {"register": name, "encoding": f"ff{0xD0 + index:02x}"}
                for index, name in enumerate(_REGISTER_NAMES)
            ],
        },
        "function_body": {
            "role": "relationship_defined_direct_callee_pair_second_target_child_static_boundary",
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
            "call_r32_audit": _register_calls(),
            "register_call_partition_complete": True,
            "ghidra_analysis_metadata": {
                "name": "FUN_00779e77",
                "namespace": "Global",
                "name_source": "DEFAULT",
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
        "predecessor_parent_edges": parent,
        "native_calls": _native_calls(facts, image),
        "whole_atlas_reference_scan": received_scan,
        "method": {
            "not_claimed": [
                "CRT, assertion, security-cookie, Watson, CFG-guard, ABI, purpose, "
                "source identity, input, output, behavior, success, failure, or "
                "normal-return semantics",
                "a noreturn property for the final E8 whose syntactic fallthrough "
                "lies outside the declared atlas body",
                "runtime identity, target, invocation, ordering, frequency, mutation, "
                "or effects for either indirect control",
                "contents or runtime meaning of the PE-address operands or the raw "
                ".rdata control-slot initializer",
                "computed, data, un-atlased, generated, runtime-fabricated, dynamic, "
                "or Lua-side references",
            ],
            "structural_boundary": "The receipt seals 122 decoded PE bytes, three opaque direct "
            "edges, two opaque indirect controls, four PE address operands "
            "including a raw-backed rdata control slot, four HIGHLOW "
            "sites, one declared predecessor edge, and an exhaustive "
            "all-operand atlas frontier.",
        },
        "summary": {
            "bnd_prefixed_control_syntax_count": 0,
            "call_r32_count": 1,
            "direct_lua_call_count": 0,
            "highlow_relocation_site_count": 4,
            "import_and_iat_body_control_count": 0,
            "native_direct_edge_count": 3,
            "non_pe_immediate_literal_count": 2,
            "opaque_indirect_control_count": 2,
            "opaque_interrupt_syntax_count": 0,
            "pe_address_operand_count": 4,
            "reviewed_target_bytes": 122,
            "reviewed_target_count": 1,
            "schema_violations": 0,
            "sealed_control_flow_graph_count": 1,
            "sealed_control_flow_graph_edge_count": 44,
            "sealed_control_flow_graph_node_count": 43,
            "sealed_instruction_count": 43,
            "segment_qualified_memory_syntax_count": 0,
            "staged_lua_dispatch_count": 0,
            "target_reference_count": 2,
            "target_reference_direct_call_count": 2,
            "target_reference_memory_operand_count": 0,
            "target_reference_other_address_count": 0,
            "target_reference_owner_count": 2,
        },
    }
    return value


def _normalize(operation: Any) -> Any:
    try:
        return operation()
    except NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError:
        raise
    except Exception as exc:
        raise NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError(
            str(exc)
        ) from exc


def build_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary(
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
            _bad("executable child bytes differ")
        decoder, _ = _decoder()
        result = _evidence(
            predecessor,
            direct,
            facts,
            rows=_decode(data[offset : offset + _SIZE]),
            image=image,
            scan=_scan(data, image, decoder, facts),
        )
        replay, replay_image, replay_digest = _load_executable(executable)
        if (
            replay_digest != digest
            or replay != data
            or replay_image.image_base != _BASE
        ):
            _bad("executable changed during exact rebuild")
        _assert_publication_safe(result)
        validate_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_structure(
            result, predecessor, direct, facts
        )
        return result

    return _normalize(run)


def encode_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary(
    value: Mapping[str, Any],
) -> str:
    return _normalize(
        lambda: json.dumps(
            _mapping(value, "encoded evidence"),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def validate_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_structure(
    evidence: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        prerequisite = validate_native_lua_direct_call_structure(direct, facts)
        if (
            prerequisite.get("status") != "structurally_verified"
            or prerequisite.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct-call structural prerequisite failed")
        if not _same(evidence, _evidence(predecessor, direct, facts)):
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


def validate_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary(
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
        rebuilt = build_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary(
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
