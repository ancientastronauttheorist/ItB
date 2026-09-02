"""Fail-closed structural receipt for the second direct-callee pair child.

This seals the finite bytes at ``0x00379e77`` and their atlas relationships.
All analysis labels, imports, control syntax, and execution semantics remain
opaque.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import capstone.x86_const as x86

from src.observatory import (
    native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary as _base,
)
from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_setfield_publications import (
    _array,
    _atlas_functions,
    _hex,
    _mapping,
    _rva,
)
from src.observatory.native_lua_class_return_helper_chain import _canonical_sha256

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

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
    ) != (_PARENT[0], _PARENT[1], _ENTRY, _ATLAS) or not _base._same(
        instruction, _base._instruction(_PARENT[0], _PARENT[2])
    ):
        _bad("second child predecessor edge differs")
    return [row]


def _decode(raw: bytes = bytes.fromhex(_RAW)) -> list[Any]:
    decoder, _ = _base._decoder()
    decoder.detail = True
    rows = list(decoder.disasm(raw, _base._BASE + _ENTRY))
    if len(rows) != 43 or b"".join(bytes(row.bytes) for row in rows) != raw:
        _bad("second child bytes do not decode exactly")
    return rows


def _graph(rows: list[Any] | None = None) -> dict[str, Any]:
    """Build the deliberately finite graph with final E8 treated as terminal.

    The declared body ends immediately after E8 at 0x379eec; accepting a
    fallthrough would silently extend it into unowned CC bytes.
    """
    if rows is None:
        decoder, _ = _base._decoder()
        decoder.detail = True
        decoded = list(decoder.disasm(bytes.fromhex(_RAW), _base._BASE + _ENTRY))
    else:
        decoded = rows
    if len(decoded) != 43 or b"".join(
        bytes(row.bytes) for row in decoded
    ) != bytes.fromhex(_RAW):
        _bad("second child instruction decode differs")
    by_rva = {row.address - _base._BASE: row for row in decoded}
    nodes = []
    for row in decoded:
        rva = row.address - _base._BASE
        raw = bytes(row.bytes)
        _, writes = row.regs_access()
        names = {row.reg_name(value).lower() for value in writes}
        successor: list[int]
        if rva in (0x379E8F, 0x379E99, 0x379EEA):
            target = int(row.operands[0].imm) - _base._BASE
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
                "value_rva": _hex(value - _base._BASE),
            }
            for site, at, file, value, raw in _RELOCS
        ],
    }


def _native_calls(facts: Mapping[str, Any], image: Any | None = None) -> dict[str, Any]:
    _target(facts)
    edges = _base._edges(facts)
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
                "instruction": _base._instruction(site, raw),
                "source_entry_rva": _hex(_ENTRY),
                "target_entry_rva": _hex(target),
                "target_rva": _hex(target),
                "target_atlas_record_sha256": atlas_record_sha256(function),
                "callee_behavior_opaque": True,
                "ghidra_declared_direct_edge": _base._edge(edge),
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
        rva = va - _base._BASE
        backed = rva == 0x493F28
        data.append(
            {
                "role": "opaque_absolute_memory_data_address_syntax",
                "instruction": _base._instruction(site, raw),
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
            "instruction": _base._instruction(0x379EB2, "ffd6"),
            "register": "esi",
            "contents_or_runtime_behavior_opaque": True,
        },
        {
            "role": "opaque_absolute_memory_indirect_control_syntax",
            "instruction": _base._instruction(0x379EAC, "ff1580657d00"),
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
            "instruction": _base._instruction(0x379EAC, "ff1580657d00"),
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
                "instruction": _base._instruction(0x379EB7, "83c414"),
                "operand_index": 1,
                "value_u32": "0x00000014",
            },
            {
                "role": "opaque_data_literal",
                "instruction": _base._instruction(0x379EDA, "83e11f"),
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
        "call_r32_audit": [
            {"register": name, "call_rvas": ["0x00379eb2"] if name == "esi" else []}
            for name in _base._REGISTER_NAMES
        ],
        "register_call_partition_complete": True,
        "base_relocation_scan": _relocations(image),
    }


def _expected_scan(facts: Mapping[str, Any]) -> dict[str, Any]:
    edges, functions = _base._edges(facts), _atlas_functions(facts)
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
                "target_va": _hex(_base._BASE + _ENTRY),
                "operand_class": "immediate",
                "operand_index": 0,
                "use_class": "direct_call",
                "call_form": "x86_relative_near_call_e8",
                "ghidra_declared_direct_edge": _base._edge(edge),
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
        "references": _base._compact(rows),
        "target_partition": _base._compact(target),
        "owner_partition": _base._compact(owners),
        "target_owner_partition": _base._compact(target_owner),
        "target_reference_partition": _base._compact(target_ref),
    }
    return {
        "target_rvas": [_hex(_ENTRY)],
        "target_vas": [_hex(_base._BASE + _ENTRY)],
        "scope": dict(_base._SCOPE),
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
            rows = _base._decode_range(data, image, start, size, decoder)
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
    value = _ORIGINAL_EVIDENCE(
        predecessor, direct, facts, rows=rows, image=image, scan=scan
    )
    body = value["function_body"]
    body.update(
        {
            "role": "relationship_defined_direct_callee_pair_second_target_child_static_boundary",
            "control_flow_graph_canonical_sha256": _CFG,
            "call_r32_audit": [
                {
                    "register": name,
                    "call_rvas": ["0x00379eb2"] if name == "ESI" else [],
                }
                for name in _base._REGISTER_NAMES
            ],
            "ghidra_analysis_metadata": {
                "name": "FUN_00779e77",
                "namespace": "Global",
                "name_source": "DEFAULT",
                "thunk": False,
                "metadata_only": True,
            },
        }
    )
    value["decoder"]["sealed_instruction_count"] = 43
    value["method"][
        "structural_boundary"
    ] = "The receipt seals 122 decoded PE bytes, three opaque direct edges, two opaque indirect controls, four PE address operands including a raw-backed rdata control slot, four HIGHLOW sites, one declared predecessor edge, and an exhaustive all-operand atlas frontier."
    value["method"]["not_claimed"] = [
        "CRT, assertion, security-cookie, Watson, CFG-guard, ABI, purpose, source identity, input, output, behavior, success, failure, or normal-return semantics",
        "a noreturn property for the final E8 whose syntactic fallthrough lies outside the declared atlas body",
        "runtime identity, target, invocation, ordering, frequency, mutation, or effects for either indirect control",
        "contents or runtime meaning of the PE-address operands or the raw .rdata control-slot initializer",
        "computed, data, un-atlased, generated, runtime-fabricated, dynamic, or Lua-side references",
    ]
    value["summary"].update(
        {
            "reviewed_target_bytes": 122,
            "sealed_instruction_count": 43,
            "sealed_control_flow_graph_node_count": 43,
            "sealed_control_flow_graph_edge_count": value["control_flow_graph"][
                "edge_count"
            ],
            "native_direct_edge_count": 3,
            "call_r32_count": 1,
            "opaque_indirect_control_count": 2,
            "import_and_iat_body_control_count": 0,
            "highlow_relocation_site_count": 4,
            "non_pe_immediate_literal_count": 2,
            "pe_address_operand_count": 4,
            "target_reference_count": 2,
            "target_reference_owner_count": 2,
            "target_reference_direct_call_count": 2,
        }
    )
    return value


_ORIGINAL_EVIDENCE = _base._evidence


@contextmanager
def _configured() -> Iterator[None]:
    values = {
        name: getattr(_base, name)
        for name in (
            "ANALYSIS_KIND",
            "VERIFICATION_KIND",
            "STRUCTURE_VERIFICATION_KIND",
            "_ENTRY",
            "_SIZE",
            "_RAW",
            "_BODY",
            "_ATLAS",
            "_CFG",
            "_PREDECESSOR",
            "_PARENT",
            "_OUTGOING",
            "_INCOMING",
            "_target",
            "_parent",
            "_decode",
            "_graph",
            "_native_calls",
            "_expected_scan",
            "_scan",
            "_evidence",
        )
    }
    try:
        (
            _base.ANALYSIS_KIND,
            _base.VERIFICATION_KIND,
            _base.STRUCTURE_VERIFICATION_KIND,
        ) = (ANALYSIS_KIND, VERIFICATION_KIND, STRUCTURE_VERIFICATION_KIND)
        (
            _base._ENTRY,
            _base._SIZE,
            _base._RAW,
            _base._BODY,
            _base._ATLAS,
            _base._CFG,
            _base._PREDECESSOR,
            _base._PARENT,
            _base._OUTGOING,
            _base._INCOMING,
        ) = (
            _ENTRY,
            _SIZE,
            _RAW,
            _BODY,
            _ATLAS,
            _CFG,
            _PREDECESSOR,
            _PARENT,
            _OUTGOING,
            _INCOMING,
        )
        (
            _base._target,
            _base._parent,
            _base._decode,
            _base._graph,
            _base._native_calls,
            _base._expected_scan,
            _base._scan,
            _base._evidence,
        ) = (
            _target,
            _parent,
            _decode,
            _graph,
            _native_calls,
            _expected_scan,
            _scan,
            _evidence,
        )
        yield
    finally:
        for name, value in values.items():
            setattr(_base, name, value)


def build_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary(
    executable: Path,
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        with _configured():
            return _base.build_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
                executable, predecessor, direct, facts, inventory=inventory
            )
    except NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError:
        raise
    except Exception as exc:
        raise NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError(
            str(exc)
        ) from exc


def encode_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary(
    value: Mapping[str, Any],
) -> str:
    try:
        with _configured():
            return _base.encode_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
                value
            )
    except NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError:
        raise
    except Exception as exc:
        raise NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError(
            str(exc)
        ) from exc


def validate_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_structure(
    evidence: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        with _configured():
            return _base.validate_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary_structure(
                evidence, predecessor, direct, facts
            )
    except NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError:
        raise
    except Exception as exc:
        raise NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError(
            str(exc)
        ) from exc


def validate_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary(
    executable: Path,
    evidence: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        with _configured():
            return _base.validate_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
                executable, evidence, predecessor, direct, facts, inventory=inventory
            )
    except NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError:
        raise
    except Exception as exc:
        raise NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError(
            str(exc)
        ) from exc
