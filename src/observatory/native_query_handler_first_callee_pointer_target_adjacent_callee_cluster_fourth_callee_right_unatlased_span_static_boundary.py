"""Fail-closed relationship receipt for the un-atlased bytes at 0x378ad0.

The bytes in this interval deliberately do not acquire function names or
runtime/source semantics here.  The receipt proves only PE backing, decode,
local control geometry, and the finite cross-references recorded below.
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
from src.observatory.native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary import (
    ANALYSIS_KIND as FOURTH_KIND,
)
from src.observatory.native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary import (
    ANALYSIS_KIND as CHILD_KIND,
)
from src.observatory.native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary import (
    ANALYSIS_KIND as RESIDUAL_KIND,
)
from src.observatory.native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary import (
    ANALYSIS_KIND as RESIDUAL_CALLEE_KIND,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = (
    "pe_native_query_handler_first_callee_pointer_target_adjacent_callee_"
    "cluster_fourth_callee_right_unatlased_span_static_boundary"
)
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_FOURTH = "1faeeefe0ee5d9bc9a85ad673133dc7936a02cfea50beb5cd70d72fc36bcb9c5"
_CHILD = "71f87f861758ba8ef7f7d9a6ac435bb05df38d81e7ff5c8e7fe8c95a4fb0e193"
_RESIDUAL = "0783fffcd973eca3937ce01faa4d4f93b974540cfdaf004a301ce7ef0198fd5d"
_RESIDUAL_CALLEE = "8e8a4c0d5c462bf20417b529313e634a76030214c34c35f0875e506a4f57f8b1"
_BASE, _START, _END = 0x400000, 0x378AD0, 0x378B3E
_RAW = (
    "8b4c2404f7410406000000b80100000074338b4424088b480833c8e8dae9fdff"
    "558b6818ff700cff7010ff7014e83effffff83c40c5d8b4424088b5424108902"
    "b803000000c355ff742408e850f3c8ff83c4048b4c24088b29ff711cff7118ff"
    "7128e809ffffff83c40c5dc20400"
)
_BODY = "79918540d44f66d64da5620cce2f34dcdba4277a8d396276abe8df5acd5a10c9"
_COMPONENTS = (
    (
        "component_a",
        _START,
        0x378B16,
        "362901c6f1880f39236b392b27695b25f670e71590060792d31ace4fc43fce70",
        21,
        21,
        "98aa27328f1ae8921f5d1bcebe36df65c20f976a2d4f2395f6109bc01ee9cc16",
    ),
    (
        "component_b",
        0x378B16,
        _END,
        "30bef2a089bcd83f642fb24f3b3c86226d5823e75422bb52157a3c1972b6a756",
        13,
        12,
        "5f700c73d746b980e5a50b239d12f3c657443099e9162f907f3e8652071c00aa",
    ),
)
_UNION_CFG = "deb134905a073ba12848269e0135bc23b42da162edefa6351a54e73be24d15b7"
_SECTION = (".text", 0x1000, 0x3D4B4E, 0x3D4C00, 0x400, 0x60000020)
_SCOPE = (25312, 25490, 3735718, 1153814)
_ENDPOINT_REFERENCE_HASH = (
    "48ed8f067c8d1fac9217dff84c769f96fbf9e1900b3bf0ed64741f6dc9aef9c8"
)
_ENDPOINT_SCAN_HASH = "8aced656b1f51133685c975d8d0f01173cc46919c7fc4c97b4a407f57a72ffb0"
_IMPORT_DIRECTORY = (
    0x48ECA4,
    220,
    0x48DCA4,
    "788f7357cb31ba62895740d67e0d8a0f6bf962c467ec801a29cf9044d522fd65",
)
_RELOCATION_DIRECTORY = (
    0x539000,
    218648,
    0x510A00,
    "06630f9047636fb68afba81d89dbc1ef2f21c459b684d57d1d2bcaeb3750dfa3",
)
_CALLS = (
    (
        0x378AEB,
        "e8dae9fdff",
        0x3574CA,
        17,
        "5eafe60e37cdb82b85f6df218e4b490940c6fb2545895c2cef644fb38ab97375",
        "931454ae86cb6a227c6182c1abea3b232ee77a68a443b5a98f358f2418ff44b0",
    ),
    (
        0x378AFD,
        "e83effffff",
        0x378A40,
        144,
        "c75af58d5bf56eae591044575adab9c6c3a2861576a9524fa38e4854960c99da",
        "e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6",
    ),
    (
        0x378B1B,
        "e850f3c8ff",
        0x7E70,
        1,
        "ae3f4619b0413d70d3004b9131c3752153074e45725be13b9a148978895e359e",
        "63019d9648749d9eb320c21859057b6fdf9dfc1aedfe3ab0d7eb2e6461fcdcb1",
    ),
    (
        0x378B32,
        "e809ffffff",
        0x378A40,
        144,
        "c75af58d5bf56eae591044575adab9c6c3a2861576a9524fa38e4854960c99da",
        "e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6",
    ),
)
_PE_CONTROL_OPERANDS = (
    (0x378AE0, "7433", 0, 0x378B15, "x86_relative_conditional_branch_imm8"),
    (0x378AEB, "e8dae9fdff", 0, 0x3574CA, "x86_relative_direct_call_e8"),
    (0x378AFD, "e83effffff", 0, 0x378A40, "x86_relative_direct_call_e8"),
    (0x378B1B, "e850f3c8ff", 0, 0x7E70, "x86_relative_direct_call_e8"),
    (0x378B32, "e809ffffff", 0, 0x378A40, "x86_relative_direct_call_e8"),
)
_NON_PE_IMMEDIATES = (
    (0x378AD4, 1, 6, "x86_test_imm32"),
    (0x378ADB, 1, 1, "x86_mov_imm32"),
    (0x378B02, 1, 12, "x86_add_imm8"),
    (0x378B10, 1, 3, "x86_mov_imm32"),
    (0x378B20, 1, 4, "x86_add_imm8"),
    (0x378B37, 1, 12, "x86_add_imm8"),
)


class NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeRightUnatlasedSpanStaticBoundaryError(
    RuntimeError
):
    """The bounded structural proof failed."""


def _bad(message: str) -> None:
    raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeRightUnatlasedSpanStaticBoundaryError(
        message
    )


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _compact_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def _instruction(rva: int, raw: str) -> dict[str, Any]:
    value = bytes.fromhex(raw)
    result = {
        "rva": _hex(rva),
        "size": len(value),
        "sha256": hashlib.sha256(value).hexdigest(),
    }
    return result


def _normalize(operation):
    try:
        return operation()
    except NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeRightUnatlasedSpanStaticBoundaryError:
        raise
    except Exception as exc:
        _bad(str(exc))


def _preflight(
    fourth: Mapping[str, Any],
    child: Mapping[str, Any],
    residual: Mapping[str, Any],
    residual_callee: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    identity = dict(_mapping(facts.get("identity"), "program facts identity"))
    if identity.get("executable_sha256") != _EXE:
        _bad("program facts executable identity differs")
    specs = (
        (fourth, FOURTH_KIND, _FOURTH, "fourth_callee_static_boundary"),
        (child, CHILD_KIND, _CHILD, "fourth_callee_child_static_boundary"),
        (
            residual,
            RESIDUAL_KIND,
            _RESIDUAL,
            "residual_direct_target_set_static_boundary",
        ),
        (
            residual_callee,
            RESIDUAL_CALLEE_KIND,
            _RESIDUAL_CALLEE,
            "residual_direct_target_set_callee_static_boundary",
        ),
    )
    result = {
        "program_facts": _source_identity(
            facts, "pe_ghidra_program_facts", _FACTS, "program facts"
        ),
        "direct_call_census": _source_identity(
            direct, DIRECT_KIND, _DIRECT, "direct calls"
        ),
    }
    for value, kind, digest, name in specs:
        if (
            not _same(value.get("build_identity"), identity)
            or value.get("analysis_kind") != kind
            or _canonical_sha256(value) != digest
        ):
            _bad(f"{name} prerequisite differs")
        result[name] = _source_identity(value, kind, digest, name)
    return result


def _ranges(facts: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    result = []
    for owner, function in _atlas_functions(facts).items():
        for raw in _array(function.get("ranges"), "atlas range"):
            item = _mapping(raw, "atlas range")
            start = _rva(item.get("start_rva"), "range start")
            size = item.get("size")
            if type(size) is not int or isinstance(size, bool) or size <= 0:
                _bad("invalid atlas range")
            result.append((start, start + size, owner))
    return result


def _geometry(facts: Mapping[str, Any], image: Any | None = None) -> dict[str, Any]:
    functions, ranges = _atlas_functions(facts), _ranges(facts)
    if [item for item in ranges if item[0] < _END and _START < item[1]]:
        _bad("atlas range overlaps un-atlased span")
    left, right = functions.get(0x378A40), functions.get(_END)
    expected = (
        (
            left,
            144,
            "c75af58d5bf56eae591044575adab9c6c3a2861576a9524fa38e4854960c99da",
            "e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6",
        ),
        (
            right,
            23,
            "6e2b3bd553f0ffdd43df815cf3341fce2e76a73e8f9b243867c06b12310701fb",
            "21bfa842aaa26c0306ff5b8da85ba63bc13daaa71cd930aaa24b91da1e34ed6c",
        ),
    )
    if any(
        row is None
        or (row.get("body_size"), row.get("body_sha256"), atlas_record_sha256(row))
        != tuple(values)
        for row, *values in expected
    ):
        _bad("neighbor atlas identity differs")
    if not _same(
        left.get("ranges"), [{"start_rva": "0x00378a40", "size": 144}]
    ) or not _same(right.get("ranges"), [{"start_rva": "0x00378b3e", "size": 23}]):
        _bad("neighbor atlas range differs")
    if max((x for x in ranges if x[1] <= _START), key=lambda x: (x[1], x[0])) != (
        0x378A40,
        _START,
        0x378A40,
    ) or min((x for x in ranges if x[0] >= _END), key=lambda x: (x[0], x[1])) != (
        _END,
        0x378B55,
        _END,
    ):
        _bad("span neighbor geometry differs")
    result = {
        "atlas_range_overlap_count": 0,
        "span_range": {
            "start_rva": _hex(_START),
            "end_rva_exclusive": _hex(_END),
            "start_va": _hex(_BASE + _START),
            "end_va_exclusive": _hex(_BASE + _END),
            "size": _END - _START,
        },
        "target_pe_backing": {
            "section_name": _SECTION[0],
            "section_rva": _hex(_SECTION[1]),
            "section_virtual_size": _SECTION[2],
            "section_raw_size": _SECTION[3],
            "section_raw_offset": _hex(_SECTION[4]),
            "section_characteristics": _hex(_SECTION[5]),
            "section_executable": True,
            "section_writable": False,
            "file_offset": "0x00377ed0",
            "file_end_offset_exclusive": "0x00377f3e",
            "raw_bytes_sha256": _BODY,
            "file_backed": True,
        },
        "left_neighbor": {
            "entry_rva": _hex(0x378A40),
            "body_size": 144,
            "body_sha256": expected[0][2],
            "atlas_record_sha256": expected[0][3],
            "range_start_rva": "0x00378a40",
            "range_end_rva_exclusive": "0x00378ad0",
            "ends_at_span": True,
            "terminal_instruction": _instruction(0x378ACF, "c3"),
            "terminal_prevents_linear_fallthrough": True,
        },
        "right_neighbor": {
            "entry_rva": _hex(_END),
            "body_size": 23,
            "body_sha256": expected[1][2],
            "atlas_record_sha256": expected[1][3],
            "range_start_rva": "0x00378b3e",
            "range_end_rva_exclusive": "0x00378b55",
            "begins_at_span_end": True,
        },
        "layout_only": True,
    }
    if image is not None:
        section = next(
            (
                s
                for s in image.sections
                if s.virtual_address <= _START < s.virtual_address + s.virtual_size
            ),
            None,
        )
        offset = image.rva_span_to_file_offset(_START, _END - _START)
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
            != _SECTION
            or offset != 0x377ED0
            or image.data[offset : offset + _END - _START] != bytes.fromhex(_RAW)
        ):
            _bad("span PE backing differs")
        for rva, size, body in (
            (0x378A40, 144, expected[0][2]),
            (_END, 23, expected[1][2]),
        ):
            off = image.rva_span_to_file_offset(rva, size)
            if hashlib.sha256(image.data[off : off + size]).hexdigest() != body:
                _bad("neighbor PE backing differs")
    return result


def _decode(
    data: bytes | None = None, image: Any | None = None, decoder: Any | None = None
) -> list[Any]:
    raw = bytes.fromhex(_RAW)
    if data is None:
        decoder, _ = _decoder()
        decoder.detail = True
        rows = list(decoder.disasm(raw, _BASE + _START))
    else:
        if image is None or decoder is None:
            _bad("exact decode lacks PE inputs")
        decoder.detail = True
        rows = _decode_range(data, image, _START, _END - _START, decoder)
    if len(rows) != 34 or b"".join(bytes(x.bytes) for x in rows) != raw:
        _bad("span linear decode differs")
    return rows


def _reachable_rvas(graph: Mapping[str, Any], entry_rva: int) -> set[str]:
    nodes = {
        _mapping(raw, "CFG node").get("rva"): _mapping(raw, "CFG node")
        for raw in _array(graph.get("nodes"), "CFG nodes")
    }
    entry = _hex(entry_rva)
    if entry not in nodes or None in nodes:
        _bad("CFG entry/node identity differs")
    reached: set[str] = set()
    pending = [entry]
    while pending:
        current = pending.pop()
        if current in reached:
            continue
        if current not in nodes:
            _bad("CFG successor leaves sealed node set")
        reached.add(current)
        for successor in _array(nodes[current].get("successor_rvas"), "successors"):
            if successor not in nodes:
                _bad("CFG successor leaves sealed node set")
            pending.append(successor)
    return reached


def _graphs(
    rows: list[Any], base: int = _BASE
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import capstone.x86_const as x86
    import capstone

    components = []
    for role, start, end, body, nodes, edges, digest in _COMPONENTS:
        subset = [x for x in rows if start <= x.address - base < end]
        if hashlib.sha256(b"".join(bytes(x.bytes) for x in subset)).hexdigest() != body:
            _bad("component body differs")
        graph = _with_edi_writes(
            _enhanced_cfg(subset, base, (start, end - start), capstone, x86),
            subset,
            x86,
        )
        if (graph.get("node_count"), graph.get("edge_count")) != (
            nodes,
            edges,
        ) or _canonical_sha256(graph) != digest:
            _bad("component CFG differs")
        reachable = _reachable_rvas(graph, start)
        if len(reachable) != nodes:
            _bad("component CFG contains locally unreachable nodes")
        terminal = subset[-1]
        expected_terminal = (
            (0x378B15, "c3") if start == _START else (0x378B3B, "c20400")
        )
        if (terminal.address - base, bytes(terminal.bytes).hex()) != expected_terminal:
            _bad("component terminal instruction differs")
        components.append(
            {
                "role": role,
                "start_rva": _hex(start),
                "end_rva_exclusive": _hex(end),
                "size": end - start,
                "body_sha256": body,
                "control_flow_graph": graph,
                "all_nodes_locally_reachable_from_candidate_entry": True,
                "terminal_instruction": _instruction(*expected_terminal),
                "terminal_prevents_linear_fallthrough": True,
                "linear_decode_complete": True,
                "undecoded_byte_count": 0,
                "padding_classification_claimed": False,
            }
        )
    union = _with_edi_writes(
        _enhanced_cfg(rows, base, (_START, _END - _START), capstone, x86), rows, x86
    )
    if _canonical_sha256(union) != _UNION_CFG:
        _bad("union control-flow graph differs")
    reachable_sets = [_reachable_rvas(union, item[1]) for item in _COMPONENTS]
    union_nodes = {
        _mapping(raw, "union CFG node").get("rva")
        for raw in _array(union.get("nodes"), "union CFG nodes")
    }
    if (
        reachable_sets[0] & reachable_sets[1]
        or reachable_sets[0] | reachable_sets[1] != union_nodes
        or len(reachable_sets) != 2
    ):
        _bad("union CFG component partition differs")
    return components, {
        "candidate_entry_components": [_hex(x[1]) for x in _COMPONENTS],
        "node_count": union["node_count"],
        "edge_count": union["edge_count"],
        "disconnected_component_count": len(reachable_sets),
        "component_node_counts": [len(item) for item in reachable_sets],
        "semantic_function_boundary_claimed": False,
        "control_flow_graph": union,
        "canonical_sha256": _UNION_CFG,
    }


def _calls(
    rows: list[Any], facts: Mapping[str, Any], base: int = _BASE
) -> dict[str, Any]:
    import capstone
    import capstone.x86_const as x86

    functions = _atlas_functions(facts)
    observed = []
    indirect = []
    register_calls: dict[str, list[str]] = {
        name: [] for name in ("EAX", "ECX", "EDX", "EBX", "ESP", "EBP", "ESI", "EDI")
    }
    for row in rows:
        rva = row.address - base
        if (
            row.id == x86.X86_INS_CALL
            and len(row.bytes) == 5
            and bytes(row.bytes)[0] == 0xE8
        ):
            if len(row.operands) != 1 or row.operands[0].type != x86.X86_OP_IMM:
                _bad("direct E8 operand differs")
            observed.append(
                (rva, bytes(row.bytes).hex(), int(row.operands[0].imm) - base)
            )
        if row.group(capstone.CS_GRP_CALL) or row.group(capstone.CS_GRP_JUMP):
            if len(row.operands) != 1:
                _bad("control-transfer operand count differs")
            operand = row.operands[0]
            if operand.type != x86.X86_OP_IMM:
                register = None
                if operand.type == x86.X86_OP_REG:
                    register = row.reg_name(operand.reg).upper()
                    if row.id == x86.X86_INS_CALL and register in register_calls:
                        register_calls[register].append(_hex(rva))
                indirect.append(
                    {
                        "instruction": _instruction(rva, bytes(row.bytes).hex()),
                        "control_kind": (
                            "x86_call_r32"
                            if row.id == x86.X86_INS_CALL and register is not None
                            else "opaque_indirect_control"
                        ),
                        "register": register,
                        "static_target_proved": False,
                        "target_and_runtime_effect_opaque": True,
                    }
                )
    if [(a, b, c) for a, b, c, *_ in _CALLS] != observed:
        _bad("span E8 partition differs")
    if indirect or any(register_calls.values()):
        _bad("span indirect-control partition differs")
    result = []
    for site, raw, target, size, body, atlas in _CALLS:
        target_row = functions.get(target)
        if target_row is None or (
            target_row.get("body_size"),
            target_row.get("body_sha256"),
            atlas_record_sha256(target_row),
        ) != (size, body, atlas):
            _bad("E8 target atlas rejoin differs")
        result.append(
            {
                "instruction": _instruction(site, raw),
                "source_rva": _hex(site),
                "source_component_start_rva": _hex(
                    _START if site < 0x378B16 else 0x378B16
                ),
                "target_entry_rva": _hex(target),
                "target_body_size": size,
                "target_body_sha256": body,
                "target_atlas_record_sha256": atlas,
                "ghidra_declared_direct_edge": None,
                "source_atlas_owned": False,
            }
        )
    return {
        "outgoing_direct": result,
        "outgoing_direct_partition_complete": True,
        "direct_lua_calls": [],
        "direct_lua_partition_complete": True,
        "staged_lua_dispatches": [],
        "staged_lua_partition_complete": True,
        "opaque_indirect_controls": indirect,
        "indirect_control_partition_complete": True,
        "call_r32_audit": [
            {"register": register, "call_rvas": register_calls[register]}
            for register in register_calls
        ],
        "register_call_partition_complete": True,
    }


def _operand_frontier(
    rows: list[Any], base: int = _BASE, image: Any | None = None
) -> dict[str, Any]:
    import capstone
    import capstone.x86_const as x86

    row_by_rva = {row.address - base: row for row in rows}
    pe_operands = []
    observed_pe = []
    for rva, raw, index, target, syntax in _PE_CONTROL_OPERANDS:
        row = row_by_rva.get(rva)
        if row is None or bytes(row.bytes).hex() != raw or len(row.operands) <= index:
            _bad("PE control operand instruction differs")
        operand = row.operands[index]
        if operand.type != x86.X86_OP_IMM or operand.access != 0:
            _bad("PE control operand shape differs")
        observed_target = (int(operand.imm) & 0xFFFFFFFF) - base
        observed_pe.append((rva, raw, index, observed_target, syntax))
        if image is not None:
            section = next(
                (
                    item
                    for item in image.sections
                    if item.virtual_address
                    <= observed_target
                    < item.virtual_address + max(item.virtual_size, item.raw_size)
                ),
                None,
            )
            if (
                section is None
                or section.name != ".text"
                or section.characteristics != _SECTION[5]
                or image.rva_span_to_file_offset(observed_target, 1) is None
            ):
                _bad("PE control target backing differs")
        pe_operands.append(
            {
                "instruction": _instruction(rva, raw),
                "operand_index": index,
                "operand_access": "control_transfer",
                "operand_va": _hex(base + target),
                "operand_rva": _hex(target),
                "control_syntax": syntax,
                "target_section_name": ".text",
                "target_section_characteristics": _hex(_SECTION[5]),
                "target_section_writable": False,
                "target_file_backed": True,
                "target_within_candidate_span": _START <= target < _END,
                "contents_or_runtime_behavior_opaque": True,
            }
        )
    if observed_pe != list(_PE_CONTROL_OPERANDS):
        _bad("PE control operand partition differs")

    literals = []
    observed_literals = []
    rets = []
    branches = []
    absolute_memory = []
    segment_qualified = []
    bnd_controls = []
    interrupts = []
    all_immediates = []
    for row in rows:
        rva = row.address - base
        if row.id == x86.X86_INS_RET and row.operands:
            rets.append(
                {
                    "instruction": _instruction(rva, bytes(row.bytes).hex()),
                    "operand_index": 0,
                    "immediate": int(row.operands[0].imm),
                    "syntax": "x86_ret_imm16",
                }
            )
        if row.id == x86.X86_INS_JE:
            branches.append(
                {
                    "instruction": _instruction(rva, bytes(row.bytes).hex()),
                    "target_rva": _hex(int(row.operands[0].imm) - base),
                    "internal_span_target": True,
                }
            )
        for index, operand in enumerate(row.operands):
            if operand.type == x86.X86_OP_IMM:
                value = int(operand.imm) & 0xFFFFFFFF
                all_immediates.append((rva, index, value))
                if row.id not in {
                    x86.X86_INS_CALL,
                    x86.X86_INS_JE,
                    x86.X86_INS_RET,
                }:
                    observed_literals.append((rva, index, value))
                    literals.append(
                        {
                            "instruction": _instruction(rva, bytes(row.bytes).hex()),
                            "operand_index": index,
                            "value": _hex(value),
                            "syntax": next(
                                (
                                    item[3]
                                    for item in _NON_PE_IMMEDIATES
                                    if item[:3] == (rva, index, value)
                                ),
                                "unsealed",
                            ),
                        }
                    )
            elif operand.type == x86.X86_OP_MEM:
                memory = operand.mem
                if memory.segment != x86.X86_REG_INVALID:
                    segment_qualified.append((rva, index))
                if (
                    memory.segment == x86.X86_REG_INVALID
                    and memory.base == x86.X86_REG_INVALID
                    and memory.index == x86.X86_REG_INVALID
                ):
                    absolute_memory.append((rva, index, int(memory.disp) & 0xFFFFFFFF))
        if bytes(row.bytes).startswith(b"\xf2") and (
            row.group(capstone.CS_GRP_CALL) or row.group(capstone.CS_GRP_JUMP)
        ):
            bnd_controls.append(rva)
        if row.group(capstone.CS_GRP_INT):
            interrupts.append(rva)
    if observed_literals != [item[:3] for item in _NON_PE_IMMEDIATES]:
        _bad("non-PE immediate literal partition differs")
    if any(row["syntax"] == "unsealed" for row in literals):
        _bad("non-PE immediate literal syntax differs")
    if (
        [(x["instruction"]["rva"], x["immediate"]) for x in rets] != [("0x00378b3b", 4)]
        or [(x["instruction"]["rva"], x["target_rva"]) for x in branches]
        != [("0x00378ae0", "0x00378b15")]
        or absolute_memory
        or segment_qualified
        or bnd_controls
        or interrupts
    ):
        _bad("RET/JE frontier differs")
    expected_immediates = (
        {
            (rva, index, base + target)
            for rva, _raw, index, target, _syntax in _PE_CONTROL_OPERANDS
        }
        | {(rva, index, value) for rva, index, value, _syntax in _NON_PE_IMMEDIATES}
        | {(0x378B3B, 0, 4)}
    )
    if set(all_immediates) != expected_immediates or len(all_immediates) != 12:
        _bad("immediate operand partition differs")
    return {
        "pe_address_operands": pe_operands,
        "pe_address_operand_partition_complete": True,
        "pe_immediate_control_operand_count": len(pe_operands),
        "absolute_memory_or_iat_operands": [],
        "absolute_memory_or_iat_partition_complete": True,
        "non_pe_immediate_literals": literals,
        "non_pe_immediate_literal_partition_complete": True,
        "immediate_operand_partition_complete": True,
        "segment_qualified_memory_syntax": [],
        "segment_qualified_memory_partition_complete": True,
        "bnd_prefixed_control_syntax": [],
        "bnd_prefixed_control_partition_complete": True,
        "opaque_interrupt_syntax": [],
        "opaque_interrupt_partition_complete": True,
        "explicit_ret_immediates": rets,
        "explicit_ret_immediate_partition_complete": True,
        "internal_direct_branch_syntax": branches,
    }


def _atlas_reference_scan(
    data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]
) -> dict[str, Any]:
    import capstone.x86_const as x86

    targets = range(_BASE + _START, _BASE + _END)
    found = []
    functions = _atlas_functions(facts)
    counts = [0, 0, 0]
    decoder.detail = True
    for owner, function in sorted(functions.items()):
        for raw in _array(function.get("ranges"), "atlas range"):
            item = _mapping(raw, "atlas range")
            start = _rva(item.get("start_rva"), "range start")
            size = item.get("size")
            if type(size) is not int or isinstance(size, bool) or size <= 0:
                _bad("invalid atlas range")
            decoded = _decode_range(data, image, start, size, decoder)
            counts[0] += 1
            counts[1] += size
            counts[2] += len(decoded)
            for row in decoded:
                for index, operand in enumerate(row.operands):
                    value = None
                    operand_class = None
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
                    if value in targets:
                        instruction = _instruction(
                            row.address - image.image_base, bytes(row.bytes).hex()
                        )
                        found.append(
                            {
                                "instruction_rva": instruction["rva"],
                                "instruction_size": instruction["size"],
                                "instruction_sha256": instruction["sha256"],
                                "owner_entry_rva": _hex(owner),
                                "owner_atlas_record_sha256": atlas_record_sha256(
                                    function
                                ),
                                "operand_index": index,
                                "operand_class": operand_class,
                                "target_rva": _hex(value - image.image_base),
                                "target_va": _hex(value),
                                "atlas_target_record_present": False,
                                "ghidra_declared_direct_edge": None,
                                "use_class": "other_address",
                            }
                        )
    expected = _expected_atlas_reference_scan()
    if (len(functions), *counts) != _SCOPE or found != expected["references"]:
        _bad("whole-atlas span reference scan differs")
    return expected


def _expected_atlas_reference_scan() -> dict[str, Any]:
    """The structural form of the exhaustive scan, independent of an EXE read."""
    instruction = _instruction(0x378A54, "68d08a7700")
    references = [
        {
            "instruction_rva": instruction["rva"],
            "instruction_size": instruction["size"],
            "instruction_sha256": instruction["sha256"],
            "owner_entry_rva": "0x00378a40",
            "owner_atlas_record_sha256": "e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6",
            "operand_index": 0,
            "operand_class": "immediate",
            "target_rva": "0x00378ad0",
            "target_va": "0x00778ad0",
            "atlas_target_record_present": False,
            "ghidra_declared_direct_edge": None,
            "use_class": "other_address",
        }
    ]
    if _compact_sha256(references) != _ENDPOINT_REFERENCE_HASH:
        _bad("sealed endpoint reference hash differs")
    result = {
        "target_rva_range": {
            "start_rva": _hex(_START),
            "end_rva_exclusive": _hex(_END),
        },
        "scope": {
            "atlas_function_count": _SCOPE[0],
            "atlas_body_range_count": _SCOPE[1],
            "decoded_bytes": _SCOPE[2],
            "decoded_instructions": _SCOPE[3],
            "all_declared_ranges_decoded": True,
            "operand_classes": ["absolute_memory", "immediate"],
        },
        "references": references,
        "references_canonical_sha256": _ENDPOINT_REFERENCE_HASH,
        "target_partition": [
            {
                "target_rva": "0x00378ad0",
                "atlas_target_record_present": False,
                "reference_count": 1,
                "owner_count": 1,
            }
        ],
        "owner_partition": [
            {
                "owner_entry_rva": "0x00378a40",
                "owner_atlas_record_sha256": "e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6",
                "reference_count": 1,
            }
        ],
        "target_owner_partition": [
            {
                "target_rva": "0x00378ad0",
                "owner_entry_rva": "0x00378a40",
                "owner_atlas_record_sha256": "e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6",
                "reference_count": 1,
            }
        ],
        "target_reference_partition": [
            {
                "target_rva": "0x00378ad0",
                "atlas_target_record_present": False,
                "reference_count": 1,
            }
        ],
        "partition_sha256": {
            "owner_partition": "440be2af21a71fc5f2984b2d60f2da7ecdad1b5b88499efb28ee36d591d2a28b",
            "target_partition": "f56f4da87465da8362261b0fd66fd4960f27be8c220041c021f91f074ee97845",
            "target_owner_partition": "45b076de44a32dec6074aceee5dc165265da871538498414ba84c7c98b8ac115",
            "target_reference_partition": "780373015d234ba91a043ef678b28b3d3399a120079e39a68a5d6136bcf7c706",
        },
        "aggregates": {
            "reference_count": 1,
            "direct_call_count": 0,
            "other_address_count": 1,
            "owner_count": 1,
            "target_count": 1,
            "target_owner_count": 1,
            "memory_operand_count": 0,
            "interior_or_component_b_reference_count": 0,
        },
    }
    if any(
        _compact_sha256(result[name]) != digest
        for name, digest in result["partition_sha256"].items()
    ):
        _bad("sealed atlas reference partition hash differs")
    return result


def _file_and_relocations(image: Any) -> dict[str, Any]:
    if image.bits != 32 or len(image.data_directories) <= 5:
        _bad("PE directory layout differs")
    for index, expected, label in (
        (1, _IMPORT_DIRECTORY, "import"),
        (5, _RELOCATION_DIRECTORY, "relocation"),
    ):
        directory_rva, directory_size, expected_offset, expected_sha256 = expected
        if image.data_directories[index] != (directory_rva, directory_size):
            _bad(f"{label} directory differs")
        directory_offset = image.rva_span_to_file_offset(directory_rva, directory_size)
        if (
            directory_offset != expected_offset
            or hashlib.sha256(
                image.data[directory_offset : directory_offset + directory_size]
            ).hexdigest()
            != expected_sha256
        ):
            _bad(f"{label} directory backing differs")

    imports = image.imports()
    iat_rvas = [_rva(item.get("iat_rva"), "PE import IAT RVA") for item in imports]
    if (
        len(imports) != 342
        or sum(item.get("name") is not None for item in imports) != 342
        or sum(item.get("ordinal") is not None for item in imports) != 0
        or min(iat_rvas) != 0x3D6000
        or max(iat_rvas) != 0x3D6578
        or any(_START <= rva < _END for rva in iat_rvas)
    ):
        _bad("PE import/IAT span frontier differs")

    target_values = {_BASE + r for r in range(_START, _END)}
    occurrences = []
    for off in range(0, len(image.data) - 3):
        value = struct.unpack_from("<I", image.data, off)[0]
        if value in target_values:
            occurrences.append((off, value))
    if occurrences != [(0x377E55, _BASE + _START)]:
        _bad("whole-file span dword scan differs")
    directory_rva, directory_size = image.data_directories[5]
    offset = image.rva_span_to_file_offset(directory_rva, directory_size)
    if offset is None:
        _bad("relocation directory is not file-backed")
    end = offset + directory_size
    sites_inside = []
    values_into = []
    cursor = offset
    while cursor < end:
        page, size = struct.unpack_from("<II", image.data, cursor)
        if size < 8 or cursor + size > end:
            _bad("relocation block malformed")
        for at in range(cursor + 8, cursor + size, 2):
            entry = struct.unpack_from("<H", image.data, at)[0]
            typ = entry >> 12
            rva = page + (entry & 0xFFF)
            if typ and (_START <= rva < _END):
                sites_inside.append((rva, typ, at))
            if typ == 3:
                file = image.rva_span_to_file_offset(rva, 4)
                if file is None:
                    _bad("HIGHLOW relocation site is not file-backed")
                value = struct.unpack_from("<I", image.data, file)[0]
                if value in target_values:
                    values_into.append((rva, typ, at, value, file))
        cursor += size
    if (
        cursor != end
        or sites_inside
        or values_into != [(0x378A55, 3, 0x532E08, _BASE + _START, 0x377E55)]
        or image.data[0x532E08:0x532E0A].hex() != "553a"
    ):
        _bad("base-relocation span frontier differs")
    observed = {
        "pe_directories": {
            "import": {
                "rva": _hex(_IMPORT_DIRECTORY[0]),
                "size": _IMPORT_DIRECTORY[1],
                "file_offset": _hex(_IMPORT_DIRECTORY[2]),
                "sha256": _IMPORT_DIRECTORY[3],
            },
            "base_relocation": {
                "rva": _hex(_RELOCATION_DIRECTORY[0]),
                "size": _RELOCATION_DIRECTORY[1],
                "file_offset": _hex(_RELOCATION_DIRECTORY[2]),
                "sha256": _RELOCATION_DIRECTORY[3],
            },
        },
        "whole_file_dword_scan": {
            "reference_count": 1,
            "references": [
                {
                    "file_offset": "0x00377e55",
                    "value_va": "0x00778ad0",
                    "target_rva": "0x00378ad0",
                }
            ],
        },
        "base_relocation_scan": {
            "relocation_site_inside_span_count": 0,
            "highlow_value_into_span_count": 1,
            "references": [
                {
                    "site_rva": "0x00378a55",
                    "file_offset": "0x00377e55",
                    "type": "HIGHLOW",
                    "entry_file_offset": "0x00532e08",
                    "entry_raw": "553a",
                    "value_va": "0x00778ad0",
                    "target_rva": "0x00378ad0",
                }
            ],
        },
        "import_and_iat_scan": {
            "parsed_import_record_count": 342,
            "named_import_count": 342,
            "ordinal_import_count": 0,
            "iat_rva_min": "0x003d6000",
            "iat_rva_max": "0x003d6578",
            "import_or_iat_slot_inside_span_count": 0,
            "all_import_records_parsed_from_pinned_directory": True,
        },
    }
    if not _same(observed, _expected_file_and_relocations()):
        _bad("file/relocation receipt differs")
    return observed


def _expected_file_and_relocations() -> dict[str, Any]:
    return {
        "pe_directories": {
            "import": {
                "rva": "0x0048eca4",
                "size": 220,
                "file_offset": "0x0048dca4",
                "sha256": "788f7357cb31ba62895740d67e0d8a0f6bf962c467ec801a29cf9044d522fd65",
            },
            "base_relocation": {
                "rva": "0x00539000",
                "size": 218648,
                "file_offset": "0x00510a00",
                "sha256": "06630f9047636fb68afba81d89dbc1ef2f21c459b684d57d1d2bcaeb3750dfa3",
            },
        },
        "whole_file_dword_scan": {
            "reference_count": 1,
            "references": [
                {
                    "file_offset": "0x00377e55",
                    "value_va": "0x00778ad0",
                    "target_rva": "0x00378ad0",
                }
            ],
        },
        "base_relocation_scan": {
            "relocation_site_inside_span_count": 0,
            "highlow_value_into_span_count": 1,
            "references": [
                {
                    "site_rva": "0x00378a55",
                    "file_offset": "0x00377e55",
                    "type": "HIGHLOW",
                    "entry_file_offset": "0x00532e08",
                    "entry_raw": "553a",
                    "value_va": "0x00778ad0",
                    "target_rva": "0x00378ad0",
                }
            ],
        },
        "import_and_iat_scan": {
            "parsed_import_record_count": 342,
            "named_import_count": 342,
            "ordinal_import_count": 0,
            "iat_rva_min": "0x003d6000",
            "iat_rva_max": "0x003d6578",
            "import_or_iat_slot_inside_span_count": 0,
            "all_import_records_parsed_from_pinned_directory": True,
        },
    }


def _declared_edges(facts: Mapping[str, Any]) -> dict[str, Any]:
    edges = _array(facts.get("ghidra_declared_direct_calls"), "declared direct calls")
    for raw in edges:
        edge = _mapping(raw, "edge")
        for field in ("source_entry_rva", "instruction_rva", "target_entry_rva"):
            if _START <= _rva(edge.get(field), field) < _END:
                _bad("declared direct edge crosses un-atlased span")
    return {
        "declared_direct_edge_count_with_source_inside_span": 0,
        "declared_direct_edge_count_with_instruction_inside_span": 0,
        "declared_direct_edge_count_with_target_inside_span": 0,
        "all_declared_edges_audited": True,
    }


def _body_rejoin(
    value: Mapping[str, Any],
    *,
    entry: int,
    size: int,
    body: str,
    atlas: str,
    label: str,
) -> dict[str, Any]:
    if (
        value.get("entry_rva"),
        value.get("range_start_rva"),
        value.get("range_size"),
        value.get("body_size"),
        value.get("body_sha256"),
        value.get("atlas_record_sha256"),
    ) != (_hex(entry), _hex(entry), size, size, body, atlas):
        _bad(f"{label} body rejoin differs")
    return {
        "entry_rva": _hex(entry),
        "body_size": size,
        "body_sha256": body,
        "atlas_record_sha256": atlas,
        "range_start_rva": _hex(entry),
        "range_end_rva_exclusive": _hex(entry + size),
    }


def _rejoins(
    fourth: Mapping[str, Any],
    child: Mapping[str, Any],
    residual: Mapping[str, Any],
    residual_callee: Mapping[str, Any],
    controls: Mapping[str, Any],
    scan: Mapping[str, Any],
) -> dict[str, Any]:
    gap = _mapping(
        _mapping(
            _mapping(fourth.get("function_body"), "fourth body").get(
                "adjacent_atlas_boundaries"
            ),
            "fourth boundaries",
        ).get("right_un_atlased_gap"),
        "fourth right gap",
    )
    expected_gap = {
        "start_rva": "0x00378ad0",
        "end_rva_exclusive": "0x00378b3e",
        "size": 110,
        "section_name": ".text",
        "file_offset": "0x00377ed0",
        "bytes_sha256": _BODY,
        "atlas_owned": False,
        "contents_or_runtime_behavior_opaque": True,
    }
    if not _same(gap, expected_gap):
        _bad("fourth right-gap rejoin differs")

    boundary = _mapping(
        _mapping(child.get("function_body"), "child body").get(
            "adjacent_atlas_boundaries"
        ),
        "child boundaries",
    )
    child_neighbor = _mapping(boundary.get("right_neighbor"), "child right neighbor")
    expected_child_neighbor = {
        "entry_rva": "0x00378a40",
        "body_size": 144,
        "body_sha256": "c75af58d5bf56eae591044575adab9c6c3a2861576a9524fa38e4854960c99da",
        "atlas_record_sha256": "e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6",
        "range_start_rva": "0x00378a40",
        "range_end_rva_exclusive": "0x00378ad0",
        "ghidra_analysis_metadata": {
            "name": "__local_unwind4",
            "namespace": "Global",
            "name_source": "ANALYSIS",
            "thunk": False,
            "metadata_only": True,
        },
    }
    if not _same(child_neighbor, expected_child_neighbor):
        _bad("child neighbor rejoin differs")

    endpoint = _mapping(
        fourth.get("whole_atlas_target_end_pointer_scan"),
        "fourth endpoint reference scan",
    )
    if (
        _canonical_sha256(endpoint) != _ENDPOINT_SCAN_HASH
        or endpoint.get("references_canonical_sha256") != _ENDPOINT_REFERENCE_HASH
        or not _same(endpoint.get("references"), scan.get("references"))
        or endpoint.get("target_rvas") != ["0x00378ad0"]
        or endpoint.get("target_vas") != ["0x00778ad0"]
    ):
        _bad("fourth endpoint reference scan rejoin differs")

    fourth_body = _body_rejoin(
        _mapping(fourth.get("function_body"), "fourth function body"),
        entry=0x378A40,
        size=144,
        body="c75af58d5bf56eae591044575adab9c6c3a2861576a9524fa38e4854960c99da",
        atlas="e4355b9ed70a7a29fd028431b4a0ed4d63dbe0727cfd1e13832aab61407b9cd6",
        label="fourth-callee target",
    )
    residual_matches = [
        _mapping(item, "residual function body")
        for item in _array(residual.get("function_bodies"), "residual function bodies")
        if isinstance(item, Mapping) and item.get("entry_rva") == "0x00007e70"
    ]
    if len(residual_matches) != 1:
        _bad("residual target body selection differs")
    residual_body = _body_rejoin(
        residual_matches[0],
        entry=0x7E70,
        size=1,
        body="ae3f4619b0413d70d3004b9131c3752153074e45725be13b9a148978895e359e",
        atlas="63019d9648749d9eb320c21859057b6fdf9dfc1aedfe3ab0d7eb2e6461fcdcb1",
        label="residual target",
    )
    residual_callee_body = _body_rejoin(
        _mapping(residual_callee.get("function_body"), "residual callee body"),
        entry=0x3574CA,
        size=17,
        body="5eafe60e37cdb82b85f6df218e4b490940c6fb2545895c2cef644fb38ab97375",
        atlas="931454ae86cb6a227c6182c1abea3b232ee77a68a443b5a98f358f2418ff44b0",
        label="residual-callee target",
    )
    outgoing = _array(controls.get("outgoing_direct"), "outgoing direct calls")
    call_sites_by_target: dict[str, list[str]] = {}
    for raw in outgoing:
        item = _mapping(raw, "outgoing direct call")
        call_sites_by_target.setdefault(item.get("target_entry_rva"), []).append(
            _mapping(item.get("instruction"), "call instruction").get("rva")
        )
    expected_sites = {
        "0x003574ca": ["0x00378aeb"],
        "0x00378a40": ["0x00378afd", "0x00378b32"],
        "0x00007e70": ["0x00378b1b"],
    }
    if call_sites_by_target != expected_sites:
        _bad("dependent target call-site rejoin differs")

    target_rows = (
        (residual_callee_body, "residual_direct_target_set_callee_static_boundary"),
        (fourth_body, "fourth_callee_static_boundary"),
        (residual_body, "residual_direct_target_set_static_boundary"),
    )
    return {
        "fourth_right_un_atlased_gap": {
            **expected_gap,
            "canonical_sha256": _canonical_sha256(gap),
            "rejoined": True,
        },
        "child_right_neighbor": {
            **expected_child_neighbor,
            "canonical_sha256": _canonical_sha256(child_neighbor),
            "rejoined": True,
        },
        "fourth_endpoint_reference_scan": {
            "canonical_sha256": _ENDPOINT_SCAN_HASH,
            "references_canonical_sha256": _ENDPOINT_REFERENCE_HASH,
            "reference_count": 1,
            "rejoined_to_current_whole_atlas_scan": True,
        },
        "outgoing_target_receipt_rejoins": [
            {
                **body,
                "source_receipt": source,
                "call_rvas": expected_sites[body["entry_rva"]],
                "call_count": len(expected_sites[body["entry_rva"]]),
                "rejoined": True,
            }
            for body, source in target_rows
        ],
        "outgoing_target_receipt_rejoin_count": len(target_rows),
    }


def _evidence(
    fourth: Mapping[str, Any],
    child: Mapping[str, Any],
    residual: Mapping[str, Any],
    residual_callee: Mapping[str, Any],
    direct: Mapping[str, Any],
    facts: Mapping[str, Any],
    *,
    data: bytes | None = None,
    image: Any | None = None,
    decoder: Any | None = None,
) -> dict[str, Any]:
    prerequisites = _preflight(fourth, child, residual, residual_callee, direct, facts)
    rows = _decode(data, image, decoder)
    components, union = _graphs(rows, image.image_base if image else _BASE)
    controls = _calls(rows, facts, image.image_base if image else _BASE)
    operands = _operand_frontier(
        rows, image.image_base if image else _BASE, image=image
    )
    geometry = _geometry(facts, image)
    scan = _expected_atlas_reference_scan()
    file_scan = _expected_file_and_relocations()
    if data is not None:
        observed_scan = _atlas_reference_scan(data, image, decoder, facts)
        observed_file_scan = _file_and_relocations(image)
        if not _same(observed_scan, scan) or not _same(observed_file_scan, file_scan):
            _bad("exact span scan differs from sealed partition")
    declared_edges = _declared_edges(facts)
    rejoins = _rejoins(fourth, child, residual, residual_callee, controls, scan)
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(_mapping(facts.get("identity"), "identity")),
        **prerequisites,
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "sealed_instruction_count": 34,
        },
        "span": {
            "role": "code_candidate_components",
            "start_rva": _hex(_START),
            "end_rva_exclusive": _hex(_END),
            "start_va": _hex(_BASE + _START),
            "end_va_exclusive": _hex(_BASE + _END),
            "size": _END - _START,
            "raw_bytes_sha256": _BODY,
            "atlas_owned": False,
            "linear_decode_complete": True,
            "undecoded_byte_count": 0,
            "padding_classification_claimed": False,
            "code_candidate_components": components,
            "union_control_flow_graph": union,
            "geometry": geometry,
        },
        "native_controls": controls,
        "operand_frontier": operands,
        "whole_atlas_reference_scan": scan,
        "whole_file_and_relocations": file_scan,
        "ghidra_declared_direct_edge_audit": declared_edges,
        "dependent_receipt_rejoins": rejoins,
        "method": {
            "structural_boundary": "The relationship-only receipt seals 110 file-backed .text bytes, a complete 34-instruction linear decode split into two locally reachable code-candidate CFG components, four direct E8 controls, five PE-address control immediates, six ordinary immediates, one RET immediate, exact atlas, whole-file, relocation, and import frontiers, plus prerequisite target joins.",
            "static_only": True,
            "relationship_only": True,
            "source_or_runtime_semantics_assigned": False,
            "not_claimed": [
                "function names, compiler, EH, security, ABI, arguments, register meaning, source semantics, or semantic kinship",
                "runtime reachability, invocation, order, frequency, normal return, success, effects, or state continuity",
                "proof that component B is addressed or any computed, indirect, data, or Lua reference beyond the sealed scans",
            ],
        },
        "nonclaims": [
            "The two locally decoded components are code candidates only, not atlas functions.",
            "No runtime or source-level behavior is inferred from this span.",
        ],
        "summary": {
            "span_bytes": 110,
            "sealed_instruction_count": 34,
            "code_candidate_component_count": 2,
            "union_cfg_node_count": 34,
            "union_cfg_edge_count": 33,
            "outgoing_direct_e8_count": 4,
            "outgoing_target_receipt_rejoin_count": 3,
            "opaque_indirect_control_count": 0,
            "call_r32_count": 0,
            "direct_lua_call_count": 0,
            "staged_lua_dispatch_count": 0,
            "pe_address_operand_count": 5,
            "pe_immediate_control_operand_count": 5,
            "pe_absolute_memory_operand_count": 0,
            "non_pe_immediate_literal_count": 6,
            "explicit_ret_immediate_count": 1,
            "segment_qualified_memory_syntax_count": 0,
            "bnd_prefixed_control_syntax_count": 0,
            "opaque_interrupt_syntax_count": 0,
            "atlas_span_reference_count": 1,
            "whole_file_span_dword_count": 1,
            "relocation_backed_span_value_count": 1,
            "relocation_site_inside_span_count": 0,
            "parsed_import_record_count": 342,
            "import_or_iat_slot_inside_span_count": 0,
            "declared_direct_edge_count_crossing_span": 0,
            "schema_violations": 0,
        },
    }
    _assert_publication_safe(result)
    return result


def validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary_structure(
    evidence: Mapping[str, Any],
    fourth_callee_static_boundary: Mapping[str, Any],
    fourth_callee_child_static_boundary: Mapping[str, Any],
    residual_direct_target_set_static_boundary: Mapping[str, Any],
    residual_direct_target_set_callee_static_boundary: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    def run():
        for value, label in (
            (evidence, "evidence"),
            (fourth_callee_static_boundary, "fourth"),
            (fourth_callee_child_static_boundary, "child"),
            (residual_direct_target_set_static_boundary, "residual"),
            (residual_direct_target_set_callee_static_boundary, "residual callee"),
            (direct_calls, "direct"),
            (program_facts, "facts"),
        ):
            _validate_json_tree(_mapping(value, label), label)
        receipt = validate_native_lua_direct_call_structure(direct_calls, program_facts)
        if (
            receipt.get("status") != "structurally_verified"
            or receipt.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct-call structural prerequisite differs")
        observed = _evidence(
            fourth_callee_static_boundary,
            fourth_callee_child_static_boundary,
            residual_direct_target_set_static_boundary,
            residual_direct_target_set_callee_static_boundary,
            direct_calls,
            program_facts,
        )
        if not _same(evidence, observed):
            _bad("evidence structure differs from reconstructed receipt")
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


def build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary(
    executable: str | Path,
    fourth_callee_static_boundary: Mapping[str, Any],
    fourth_callee_child_static_boundary: Mapping[str, Any],
    residual_direct_target_set_static_boundary: Mapping[str, Any],
    residual_direct_target_set_callee_static_boundary: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run():
        for value, label in (
            (fourth_callee_static_boundary, "fourth"),
            (fourth_callee_child_static_boundary, "child"),
            (residual_direct_target_set_static_boundary, "residual"),
            (residual_direct_target_set_callee_static_boundary, "residual callee"),
            (direct_calls, "direct"),
            (program_facts, "facts"),
            (inventory, "inventory"),
        ):
            _validate_json_tree(_mapping(value, label), label)
        path = Path(executable)
        receipt = validate_native_lua_direct_call_census(
            path, direct_calls, program_facts, inventory=inventory
        )
        if (
            receipt.get("status") != "verified"
            or receipt.get("evidence_sha256") != _DIRECT
        ):
            _bad("direct-call exact prerequisite differs")
        data, image, digest = _load_executable(path)
        if digest != _EXE or image.image_base != _BASE:
            _bad("executable identity differs")
        decoder, _ = _decoder()
        decoder.detail = True
        result = _evidence(
            fourth_callee_static_boundary,
            fourth_callee_child_static_boundary,
            residual_direct_target_set_static_boundary,
            residual_direct_target_set_callee_static_boundary,
            direct_calls,
            program_facts,
            data=data,
            image=image,
            decoder=decoder,
        )
        replay, replay_image, replay_digest = _load_executable(path)
        if (
            replay_digest != digest
            or replay != data
            or replay_image.image_base != _BASE
        ):
            _bad("executable changed during rebuild")
        _assert_publication_safe(result)
        validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary_structure(
            result,
            fourth_callee_static_boundary,
            fourth_callee_child_static_boundary,
            residual_direct_target_set_static_boundary,
            residual_direct_target_set_callee_static_boundary,
            direct_calls,
            program_facts,
        )
        return result

    return _normalize(run)


def validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary(
    executable: str | Path,
    evidence: Mapping[str, Any],
    fourth_callee_static_boundary: Mapping[str, Any],
    fourth_callee_child_static_boundary: Mapping[str, Any],
    residual_direct_target_set_static_boundary: Mapping[str, Any],
    residual_direct_target_set_callee_static_boundary: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run():
        _validate_json_tree(_mapping(evidence, "evidence"), "evidence")
        rebuilt = build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary(
            executable,
            fourth_callee_static_boundary,
            fourth_callee_child_static_boundary,
            residual_direct_target_set_static_boundary,
            residual_direct_target_set_callee_static_boundary,
            direct_calls,
            program_facts,
            inventory=inventory,
        )
        if not _same(evidence, rebuilt):
            _bad("exact executable reconstruction differs")
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": VERIFICATION_KIND,
            "status": "verified",
            "build_identity": dict(rebuilt["build_identity"]),
            "evidence_sha256": _canonical_sha256(rebuilt),
            "summary": dict(rebuilt["summary"]),
        }

    return _normalize(run)


def encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary(
    value: Mapping[str, Any],
) -> str:
    def run():
        item = _mapping(value, "encoded value")
        _validate_json_tree(item, "encoded value")
        return (
            json.dumps(
                item, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2
            )
            + "\n"
        )

    return _normalize(run)
