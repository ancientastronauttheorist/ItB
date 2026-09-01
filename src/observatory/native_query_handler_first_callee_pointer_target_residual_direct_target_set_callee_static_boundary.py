"""Static boundary for the callee of the query-pointer residual target set.

The target is selected only by the two edges retained in the prerequisite
receipt.  Analysis labels, BND-prefixed controls, and address syntax remain
opaque structural evidence and do not establish source semantics or behavior.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capstone import CsError

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
    NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError,
)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = (
    "pe_native_query_handler_first_callee_pointer_target_"
    "residual_direct_target_set_callee_static_boundary"
)
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_RESIDUAL = "0783fffcd973eca3937ce01faa4d4f93b974540cfdaf004a301ce7ef0198fd5d"

_IMAGE_BASE = 0x400000
_ENTRY = 0x3574CA
_BODY_SIZE = 17
_BODY_SHA256 = (
    "5eafe60e37cdb82b85f6df218e4b490940c6fb2545895c2cef644fb38ab97375"
)
_ATLAS_SHA256 = (
    "931454ae86cb6a227c6182c1abea3b232ee77a68a443b5a98f358f2418ff44b0"
)
_CFG_SHA256 = (
    "96b4b9365583495d1aa25d002d4833a064caf3792125584a8a6916bda9eb1a9d"
)
_POINTS = (
    (0x3574CA, "3b0d283f8900"),
    (0x3574D0, "f27502"),
    (0x3574D3, "f2c3"),
    (0x3574D5, "f2e98f060000"),
)

_PARENT_ENTRY = 0x372970
_PARENT_BODY_SIZE = 50
_PARENT_BODY_SHA256 = (
    "507263aae961bb903352a36e523f1a156c735dd59b51f683f55fa1470119a0cb"
)
_PARENT_ATLAS_SHA256 = (
    "1c4fcb33ad57b15dd5609533bb859b2d740aa6d39bfada8c6b0e6d93280f9316"
)
_PARENT_SITES = {0x37298A: "e8", 0x37299D: "e9"}

_OUTGOING_SITE = 0x3574D5
_OUTGOING_TARGET = 0x357B6A
_OUTGOING_TARGET_SIZE = 251
_OUTGOING_TARGET_BODY_SHA256 = (
    "0a7f470e5151d95873547c1201fe9ad8d4c502d6afc9b530de59d9390eb9c0ed"
)
_OUTGOING_TARGET_ATLAS_SHA256 = (
    "324c7636ddd286b956053bb39fa045719f388d5254e441ce98b33d77d11fb074"
)

_BND_CALL_SITES = frozenset({0x3581D3, 0x3581E4, 0x39D7BE})
_E9_REFERENCE_SITES = frozenset({0x37299D})
_REFERENCE_COUNT = 1794
_REFERENCE_OWNER_COUNT = 1620
_OWNER_PARTITION_SHA256 = (
    "2496424b11c54f2dc558861a9469e4364f470a1b373cb93ed0b00eb4944790de"
)
_TARGET_OWNER_PARTITION_SHA256 = (
    "e581d35f505204c2623a22d21e63fa5852d323a9e59ac2248ad6b681a178bfbb"
)
_TARGET_REFERENCE_PARTITION_SHA256 = (
    "64e5b02dda9ed08d40341ce46043a78eb705724bdf057ad885d59ef36feb993e"
)

_SUCCESSOR_POLICY = (
    "only targets within the declared atlas range appear in successor_rvas"
)
_METHOD = {
    "structural_boundary": (
        "PE-free validation reconstructs the complete target body, every "
        "instruction point, the body-local CFG, BND-prefixed control syntax, "
        "typed PE operands, the external transfer, both prerequisite parent "
        "edges, all 1,794 declared incoming reference rows, and every owner "
        "partition. Exact reconstruction decodes the sealed executable and "
        "exhaustively traverses every declared atlas range."
    ),
    "body_local_successor_policy": _SUCCESSOR_POLICY,
    "not_claimed": [
        "analysis-label meaning, security-check or cookie purpose, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return",
        "runtime reachability, invocation, ordering, frequency, state mutation, termination, or effect",
        "BND-prefix runtime semantics or contents and runtime meaning of PE-address operands",
        "computed, indirect, data, un-atlased, dynamic, or Lua-side references",
    ],
}


class NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError(
    RuntimeError
):
    """Raised when the sealed residual-target-set callee cannot be reproduced."""


def _error(message: str) -> None:
    raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError(
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


def _expected_point(rva: int, encoded: str) -> dict[str, Any]:
    return {
        **_instruction_fact(rva, encoded),
        "writes_ebx": False,
        "writes_esi": False,
        "writes_edi": False,
        "writes_esp": rva == 0x3574D3,
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
        _error("reviewed instruction differs")
    try:
        _reads, writes = instruction.regs_access()
        written_names = {
            instruction.reg_name(register).lower() for register in writes
        }
    except Exception as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError(
            "decoder register-write classification failed"
        ) from exc
    observed = {
        **_instruction_fact(expected_rva, encoded),
        "writes_ebx": "ebx" in written_names,
        "writes_esi": "esi" in written_names,
        "writes_edi": "edi" in written_names,
        "writes_esp": "esp" in written_names,
    }
    if observed != _expected_point(expected_rva, encoded):
        _error("reviewed instruction register writes differ")
    return observed


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
    residual: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    identity = _mapping(program_facts.get("identity"), "program facts identity")
    if identity.get("executable_sha256") != _EXE:
        _error("program-facts executable identity differs")
    for prerequisite, label in (
        (residual, "residual target set"),
        (direct_calls, "direct calls"),
    ):
        if not _same(prerequisite.get("build_identity"), dict(identity)):
            _error(f"{label} build identity differs")
    if _canonical_json_sha256(residual) != _RESIDUAL:
        _error("residual-target-set prerequisite differs")
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
        "residual_direct_target_set_static_boundary": _identity(
            residual,
            RESIDUAL_KIND,
            _RESIDUAL,
            "residual target set",
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
        "sealed_instruction_count": 4,
        "range_union_cfg_projection": "body_local_instruction_cfg_v1",
        "register_call_encoding_audit": [
            {"register": register, "encoding": f"ff{0xD0 + index:02x}"}
            for index, register in enumerate(_REGISTER_NAMES)
        ],
        "bnd_prefixed_control_encoding_audit": [
            {"site_rva": "0x003574d0", "encoding": "f27502"},
            {"site_rva": "0x003574d3", "encoding": "f2c3"},
            {"site_rva": "0x003574d5", "encoding": "f2e98f060000"},
        ],
    }


def _expected_graph() -> dict[str, Any]:
    points = [_expected_point(rva, encoded) for rva, encoded in _POINTS]
    flows = (
        ("fallthrough", ["0x003574d0"]),
        ("direct_conditional_branch", ["0x003574d3", "0x003574d5"]),
        ("terminal", []),
        ("direct_unconditional_external_branch", []),
    )
    nodes = [
        {**point, "flow_kind": flow, "successor_rvas": successors}
        for point, (flow, successors) in zip(points, flows)
    ]
    graph = {
        "caller_entry_rva": _hex(_ENTRY),
        "range_start_rva": _hex(_ENTRY),
        "range_size": _BODY_SIZE,
        "projection_kind": "body_local_instruction_cfg_v1",
        "body_local_successor_policy": _SUCCESSOR_POLICY,
        "nodes": nodes,
        "node_count": 4,
        "edge_count": 3,
    }
    if _canonical_json_sha256(graph) != _CFG_SHA256:
        _error("expected body-local CFG identity differs")
    return graph


def _local_cfg(
    instructions: list[Any],
    image_base: int,
    reviewed_points: list[dict[str, Any]],
) -> dict[str, Any]:
    import capstone
    import capstone.x86_const as x86

    if len(instructions) != 4 or len(reviewed_points) != 4:
        _error("body instruction count differs")
    body_rvas = {instruction.address - image_base for instruction in instructions}
    nodes: list[dict[str, Any]] = []
    edge_count = 0
    for instruction, point in zip(instructions, reviewed_points):
        rva = instruction.address - image_base
        fallthrough = rva + instruction.size
        immediate_targets = [
            int(operand.imm) - image_base
            for operand in instruction.operands
            if operand.type == x86.X86_OP_IMM
        ]
        if instruction.id == x86.X86_INS_RET:
            flow_kind, successors = "terminal", []
        elif instruction.group(capstone.CS_GRP_JUMP):
            if len(immediate_targets) != 1:
                _error("BND branch operand syntax differs")
            target = immediate_targets[0]
            if instruction.id == x86.X86_INS_JMP:
                if target in body_rvas:
                    flow_kind = "direct_unconditional_branch"
                    successors = [_hex(target)]
                else:
                    flow_kind = "direct_unconditional_external_branch"
                    successors = []
            else:
                if fallthrough not in body_rvas or target not in body_rvas:
                    _error("BND conditional leaves the declared body")
                flow_kind = "direct_conditional_branch"
                successors = sorted([_hex(fallthrough), _hex(target)])
        elif fallthrough in body_rvas:
            flow_kind, successors = "fallthrough", [_hex(fallthrough)]
        else:
            flow_kind, successors = "range_boundary", []
        edge_count += len(successors)
        nodes.append(
            {**point, "flow_kind": flow_kind, "successor_rvas": successors}
        )
    graph = {
        "caller_entry_rva": _hex(_ENTRY),
        "range_start_rva": _hex(_ENTRY),
        "range_size": _BODY_SIZE,
        "projection_kind": "body_local_instruction_cfg_v1",
        "body_local_successor_policy": _SUCCESSOR_POLICY,
        "nodes": nodes,
        "node_count": len(nodes),
        "edge_count": edge_count,
    }
    if not _same(graph, _expected_graph()):
        _error("decoded body-local CFG differs")
    return graph


def _empty_call_r32_audit() -> list[dict[str, Any]]:
    return [
        {"register": register, "call_rvas": []}
        for register in _REGISTER_NAMES
    ]


def _direct_lua_partition(
    direct_calls: Mapping[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw_record in _array(direct_calls.get("records"), "direct-call records"):
        record = _mapping(raw_record, "direct-call record")
        if _rva(record.get("entry_rva"), "direct-call entry") != _ENTRY:
            continue
        result.extend(
            dict(_mapping(call, "direct Lua call"))
            for call in _array(
                record.get("direct_lua_import_calls"), "direct Lua calls"
            )
        )
    if result:
        _error("residual-callee direct-Lua-call partition differs")
    return result


def _expected_body(
    program_facts: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    reviewed_points: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    function = _functions(program_facts).get(_ENTRY)
    if function is None or (
        function.get("body_size"),
        function.get("body_sha256"),
        atlas_record_sha256(function),
    ) != (_BODY_SIZE, _BODY_SHA256, _ATLAS_SHA256):
        _error("residual-callee atlas body differs")
    return {
        "role": "residual_direct_target_set_callee_opaque_static_boundary",
        "entry_rva": _hex(_ENTRY),
        "atlas_record_sha256": _ATLAS_SHA256,
        "body_size": _BODY_SIZE,
        "body_sha256": _BODY_SHA256,
        "range_start_rva": _hex(_ENTRY),
        "range_size": _BODY_SIZE,
        "control_flow_graph_canonical_sha256": _CFG_SHA256,
        "reviewed_points": (
            [_expected_point(rva, encoded) for rva, encoded in _POINTS]
            if reviewed_points is None
            else reviewed_points
        ),
        "direct_lua_calls": _direct_lua_partition(direct_calls),
        "staged_lua_dispatches": [],
        "call_r32_audit": _empty_call_r32_audit(),
        "register_call_partition_complete": True,
        "semantic_facts": {
            "relationship_defined_only": True,
            "analysis_labels_opaque": True,
            "security_or_cookie_semantics_claimed": False,
            "source_semantic_names_assigned": False,
            "runtime_or_success_claimed": False,
        },
    }


def _parent_instruction(site: int) -> tuple[str, str]:
    encoding = _PARENT_SITES.get(site)
    if encoding is None:
        _error("parent site differs")
    opcode = 0xE8 if encoding == "e8" else 0xE9
    raw = bytes((opcode,)) + int(_ENTRY - (site + 5)).to_bytes(
        4, "little", signed=True
    )
    return encoding, raw.hex()


def _parent_rows(
    residual: Mapping[str, Any], program_facts: Mapping[str, Any]
) -> list[dict[str, Any]]:
    native = _mapping(residual.get("native_calls"), "residual native calls")
    all_rows = [
        dict(_mapping(row, "residual outgoing direct edge"))
        for row in _array(native.get("outgoing_direct"), "residual outgoing edges")
    ]
    rows = [
        row
        for row in all_rows
        if _rva(row.get("source_entry_rva"), "parent source") == _PARENT_ENTRY
        and _rva(row.get("target_entry_rva"), "parent target") == _ENTRY
    ]
    rows.sort(
        key=lambda row: _rva(
            _mapping(row.get("instruction"), "parent instruction").get("rva"),
            "parent site",
        )
    )
    if len(rows) != 2 or len(all_rows) != 2:
        _error("residual-callee parent edge count differs")
    functions = _functions(program_facts)
    declared = _declared_edges(program_facts)
    parent_function = functions.get(_PARENT_ENTRY)
    target_function = functions.get(_ENTRY)
    if parent_function is None or (
        parent_function.get("body_size"),
        parent_function.get("body_sha256"),
        atlas_record_sha256(parent_function),
    ) != (_PARENT_BODY_SIZE, _PARENT_BODY_SHA256, _PARENT_ATLAS_SHA256):
        _error("residual-callee parent atlas identity differs")
    if target_function is None or (
        target_function.get("body_size"),
        target_function.get("body_sha256"),
        atlas_record_sha256(target_function),
    ) != (_BODY_SIZE, _BODY_SHA256, _ATLAS_SHA256):
        _error("residual-callee target atlas identity differs")
    for row in rows:
        instruction = _mapping(row.get("instruction"), "parent instruction")
        site = _rva(instruction.get("rva"), "parent site")
        encoding, raw = _parent_instruction(site)
        edge = declared.get(site)
        if edge is None or (
            row.get("role") != "opaque_declared_direct_edge"
            or row.get("control_encoding") != encoding
            or not _same(instruction, _instruction_fact(site, raw))
            or row.get("source_body_size") != _PARENT_BODY_SIZE
            or row.get("source_body_sha256") != _PARENT_BODY_SHA256
            or row.get("source_atlas_record_sha256")
            != _PARENT_ATLAS_SHA256
            or row.get("target_body_size") != _BODY_SIZE
            or row.get("target_body_sha256") != _BODY_SHA256
            or row.get("target_atlas_record_sha256") != _ATLAS_SHA256
            or not _same(
                row.get("ghidra_declared_direct_edge"),
                _normalized_declared_edge(edge),
            )
        ):
            _error("residual-callee parent edge identity differs")
    transfers = [
        dict(_mapping(row, "out-of-body transfer"))
        for row in _array(
            residual.get("out_of_body_direct_transfers"),
            "out-of-body transfers",
        )
    ]
    e9_parent = next(
        row
        for row in rows
        if _rva(
            _mapping(row.get("instruction"), "parent instruction").get("rva"),
            "parent site",
        )
        == 0x37299D
    )
    if len(transfers) != 1 or not _same(transfers[0], e9_parent):
        _error("residual-callee external parent join differs")
    return rows


def _outgoing_rows(program_facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions = _functions(program_facts)
    declared = _declared_edges(program_facts)
    source = functions.get(_ENTRY)
    target = functions.get(_OUTGOING_TARGET)
    edge = declared.get(_OUTGOING_SITE)
    if source is None or target is None or edge is None:
        _error("residual-callee outgoing edge join differs")
    if (
        _rva(edge.get("source_entry_rva"), "outgoing source") != _ENTRY
        or _rva(edge.get("target_entry_rva"), "outgoing target entry")
        != _OUTGOING_TARGET
        or _rva(edge.get("target_rva"), "outgoing target")
        != _OUTGOING_TARGET
        or (
            source.get("body_size"),
            source.get("body_sha256"),
            atlas_record_sha256(source),
        )
        != (_BODY_SIZE, _BODY_SHA256, _ATLAS_SHA256)
        or (
            target.get("body_size"),
            target.get("body_sha256"),
            atlas_record_sha256(target),
        )
        != (
            _OUTGOING_TARGET_SIZE,
            _OUTGOING_TARGET_BODY_SHA256,
            _OUTGOING_TARGET_ATLAS_SHA256,
        )
    ):
        _error("residual-callee outgoing edge identity differs")
    other = [
        candidate
        for candidate in declared.values()
        if _rva(candidate.get("source_entry_rva"), "declared source") == _ENTRY
    ]
    if len(other) != 1:
        _error("residual-callee outgoing edge partition differs")
    return [
        {
            "role": "opaque_declared_direct_edge",
            "instruction": _instruction_fact(
                _OUTGOING_SITE, "f2e98f060000"
            ),
            "source_entry_rva": _hex(_ENTRY),
            "source_body_size": _BODY_SIZE,
            "source_body_sha256": _BODY_SHA256,
            "source_atlas_record_sha256": _ATLAS_SHA256,
            "target_entry_rva": _hex(_OUTGOING_TARGET),
            "target_body_size": _OUTGOING_TARGET_SIZE,
            "target_body_sha256": _OUTGOING_TARGET_BODY_SHA256,
            "target_atlas_record_sha256": _OUTGOING_TARGET_ATLAS_SHA256,
            "ghidra_declared_direct_edge": _normalized_declared_edge(edge),
            "control_encoding": "f2e9",
        }
    ]


def _operand_access(value: int) -> str:
    names = {0: "none", 1: "read", 2: "write", 3: "read_write"}
    if value not in names:
        _error("unsupported operand access mask")
    return names[value]


def _expected_pe_address_operands() -> list[dict[str, Any]]:
    specs = (
        (
            0x3574CA,
            "3b0d283f8900",
            "absolute_memory",
            1,
            "read",
            0x893F28,
            "noncontrol_absolute_memory",
            ".data",
            0x492000,
            0xC0000040,
        ),
        (
            0x3574D0,
            "f27502",
            "immediate",
            0,
            "none",
            0x7574D5,
            "bnd_conditional_branch_target",
            ".text",
            0x1000,
            0x60000020,
        ),
        (
            0x3574D5,
            "f2e98f060000",
            "immediate",
            0,
            "none",
            0x757B6A,
            "bnd_external_branch_target",
            ".text",
            0x1000,
            0x60000020,
        ),
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


def _expected_bnd_syntax() -> list[dict[str, Any]]:
    specs = (
        (
            0x3574D0,
            "f27502",
            "bnd jne",
            "direct_conditional_branch",
            "0x003574d5",
            "body_local",
        ),
        (
            0x3574D3,
            "f2c3",
            "bnd ret",
            "terminal_return",
            None,
            "terminal",
        ),
        (
            0x3574D5,
            "f2e98f060000",
            "bnd jmp",
            "direct_unconditional_branch",
            "0x00357b6a",
            "external",
        ),
    )
    return [
        {
            "role": "opaque_bnd_prefixed_control_syntax",
            "instruction": _instruction_fact(site, encoded),
            "decoded_mnemonic": mnemonic,
            "control_class": control_class,
            "target_rva": target,
            "target_scope": scope,
            "runtime_semantics_opaque": True,
        }
        for site, encoded, mnemonic, control_class, target, scope in specs
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
        "bnd_prefixed_control_syntax": _expected_bnd_syntax(),
        "bnd_prefixed_control_partition_complete": True,
        "call_r32_audit": _empty_call_r32_audit(),
        "register_call_partition_complete": True,
    }


def _native_syntax(
    image: Any,
    instructions: list[Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    import capstone
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
    pe_roles = {
        0x3574CA: "noncontrol_absolute_memory",
        0x3574D0: "bnd_conditional_branch_target",
        0x3574D5: "bnd_external_branch_target",
    }
    bnd_by_site = {
        _rva(row["instruction"]["rva"], "BND site"): row
        for row in _expected_bnd_syntax()
    }
    call_r32_sites: dict[str, list[int]] = {
        register: [] for register in _REGISTER_NAMES
    }
    indirect_controls: list[dict[str, Any]] = []
    pe_operands: list[dict[str, Any]] = []
    segment_syntax: list[dict[str, Any]] = []
    bnd_syntax: list[dict[str, Any]] = []
    for instruction in instructions:
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
                    or raw[1] != 0xD0 + _REGISTER_NAMES.index(register)
                ):
                    _error("unrecognized register-call encoding")
                call_r32_sites[register].append(rva)
        if raw.startswith(b"\xf2"):
            expected_bnd = bnd_by_site.get(rva)
            if expected_bnd is None or instruction.mnemonic != expected_bnd[
                "decoded_mnemonic"
            ]:
                _error("unreviewed BND-prefixed instruction syntax")
            target = expected_bnd["target_rva"]
            if target is None:
                if instruction.id != x86.X86_INS_RET or instruction.operands:
                    _error("BND return syntax differs")
            else:
                operands = [
                    operand
                    for operand in instruction.operands
                    if operand.type == x86.X86_OP_IMM
                ]
                if len(operands) != 1 or _hex(
                    int(operands[0].imm) - image.image_base
                ) != target:
                    _error("BND branch target syntax differs")
                if (
                    expected_bnd["control_class"]
                    == "direct_conditional_branch"
                    and (
                        instruction.id == x86.X86_INS_JMP
                        or not instruction.group(capstone.CS_GRP_JUMP)
                    )
                ):
                    _error("BND conditional control class differs")
                if (
                    expected_bnd["control_class"]
                    == "direct_unconditional_branch"
                    and instruction.id != x86.X86_INS_JMP
                ):
                    _error("BND unconditional control class differs")
            bnd_syntax.append(dict(expected_bnd))
        for operand_index, operand in enumerate(instruction.operands):
            if (
                operand.type == x86.X86_OP_MEM
                and operand.mem.segment != x86.X86_REG_INVALID
            ):
                segment_syntax.append(
                    {"instruction": fact, "operand_index": operand_index}
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
            role = pe_roles.get(rva)
            if role is None:
                _error("unreviewed PE-address operand")
            pe_operands.append(
                {
                    "role": "typed_pe_address_operand",
                    "instruction": fact,
                    "operand_class": operand_class,
                    "operand_index": operand_index,
                    "operand_access": _operand_access(operand.access),
                    "operand_va": _hex(value),
                    "operand_rva": _hex(target_rva),
                    "control_syntax": role,
                    "section_name": section.name,
                    "section_rva": _hex(section.virtual_address),
                    "section_characteristics": _hex(section.characteristics),
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
        "bnd_prefixed_control_syntax": sorted(
            bnd_syntax,
            key=lambda row: _rva(
                row["instruction"]["rva"], "BND syntax site"
            ),
        ),
        "bnd_prefixed_control_partition_complete": True,
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


def _reference_encoding(
    site: int, target: int
) -> tuple[bytes, str, str | None]:
    if site in _BND_CALL_SITES:
        raw = b"\xf2\xe8" + int(target - (site + 6)).to_bytes(
            4, "little", signed=True
        )
        return raw, "direct_call", "x86_bnd_relative_near_call_f2e8"
    if site in _E9_REFERENCE_SITES:
        raw = b"\xe9" + int(target - (site + 5)).to_bytes(
            4, "little", signed=True
        )
        return raw, "other_address", None
    raw = b"\xe8" + int(target - (site + 5)).to_bytes(
        4, "little", signed=True
    )
    return raw, "direct_call", "x86_relative_near_call_e8"


def _reference_record(
    *,
    site: int,
    owner: int,
    functions: Mapping[int, Mapping[str, Any]],
    declared: Mapping[int, Mapping[str, Any]],
    image_base: int,
    observed_raw: bytes | None = None,
    operand_index: int = 0,
) -> dict[str, Any]:
    function = functions.get(owner)
    target_function = functions.get(_ENTRY)
    edge = declared.get(site)
    if function is None or target_function is None or edge is None:
        _error("reference atlas or declared-edge join differs")
    if (
        _rva(edge.get("source_entry_rva"), "reference source") != owner
        or _rva(edge.get("target_entry_rva"), "reference target entry")
        != _ENTRY
        or _rva(edge.get("target_rva"), "reference target") != _ENTRY
    ):
        _error("reference declared edge differs")
    raw, use_class, call_form = _reference_encoding(site, _ENTRY)
    if observed_raw is not None and observed_raw != raw:
        _error("reference instruction encoding differs")
    if operand_index != 0:
        _error("reference operand index differs")
    if (
        target_function.get("body_size"),
        target_function.get("body_sha256"),
        atlas_record_sha256(target_function),
    ) != (_BODY_SIZE, _BODY_SHA256, _ATLAS_SHA256):
        _error("reference target atlas identity differs")
    return {
        "instruction_rva": _hex(site),
        "instruction_size": len(raw),
        "instruction_sha256": hashlib.sha256(raw).hexdigest(),
        "owner_entry_rva": _hex(owner),
        "owner_atlas_record_sha256": atlas_record_sha256(function),
        "target_rva": _hex(_ENTRY),
        "target_atlas_record_sha256": _ATLAS_SHA256,
        "target_va": _hex(image_base + _ENTRY),
        "operand_class": "immediate",
        "operand_index": 0,
        "use_class": use_class,
        "call_form": call_form,
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
    keys = [
        (row["instruction_rva"], row["operand_index"]) for row in references
    ]
    if len(references) != _REFERENCE_COUNT or len(keys) != len(set(keys)):
        _error("entry-reference count or uniqueness differs")
    owner_counts: dict[tuple[str, str], int] = {}
    target_owner_counts: dict[tuple[str, str, str], int] = {}
    for row in references:
        if row["target_rva"] != _hex(_ENTRY):
            _error("entry-reference target differs")
        owner_key = (
            row["owner_entry_rva"],
            row["owner_atlas_record_sha256"],
        )
        owner_counts[owner_key] = owner_counts.get(owner_key, 0) + 1
        target_owner_key = (row["target_rva"], *owner_key)
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
    target_partition = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS_SHA256,
            "reference_count": _REFERENCE_COUNT,
            "owner_count": _REFERENCE_OWNER_COUNT,
        }
    ]
    target_reference_partition = [
        {
            "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS_SHA256,
            "reference_count": _REFERENCE_COUNT,
        }
    ]
    partition_sha256 = {
        "owner_partition": _compact_sha256(owner_partition),
        "target_owner_partition": _compact_sha256(target_owner_partition),
        "target_reference_partition": _compact_sha256(
            target_reference_partition
        ),
    }
    if len(owner_partition) != _REFERENCE_OWNER_COUNT or len(
        target_owner_partition
    ) != _REFERENCE_OWNER_COUNT:
        _error("entry-reference owner partition differs")
    if partition_sha256 != {
        "owner_partition": _OWNER_PARTITION_SHA256,
        "target_owner_partition": _TARGET_OWNER_PARTITION_SHA256,
        "target_reference_partition": _TARGET_REFERENCE_PARTITION_SHA256,
    }:
        _error("entry-reference partition identity differs")
    standard_calls = sum(
        row["call_form"] == "x86_relative_near_call_e8"
        for row in references
    )
    bnd_calls = sum(
        row["call_form"] == "x86_bnd_relative_near_call_f2e8"
        for row in references
    )
    other_addresses = sum(
        row["use_class"] == "other_address" for row in references
    )
    aggregates = {
        "reference_count": len(references),
        "target_count": 1,
        "owner_count": len(owner_partition),
        "target_owner_count": len(target_owner_partition),
        "direct_call_count": sum(
            row["use_class"] == "direct_call" for row in references
        ),
        "standard_e8_direct_call_count": standard_calls,
        "bnd_f2e8_direct_call_count": bnd_calls,
        "other_address_count": other_addresses,
        "e9_other_address_count": sum(
            row["use_class"] == "other_address"
            and row["call_form"] is None
            and row["instruction_size"] == 5
            for row in references
        ),
        "memory_operand_count": sum(
            row["operand_class"] == "absolute_memory"
            for row in references
        ),
    }
    if aggregates != {
        "reference_count": 1794,
        "target_count": 1,
        "owner_count": 1620,
        "target_owner_count": 1620,
        "direct_call_count": 1793,
        "standard_e8_direct_call_count": 1790,
        "bnd_f2e8_direct_call_count": 3,
        "other_address_count": 1,
        "e9_other_address_count": 1,
        "memory_operand_count": 0,
    }:
        _error("entry-reference aggregate partition differs")
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
        "aggregates": aggregates,
    }


def _expected_scan(program_facts: Mapping[str, Any]) -> dict[str, Any]:
    functions = _functions(program_facts)
    declared = _declared_edges(program_facts)
    image_base = _rva(
        _mapping(program_facts.get("ghidra"), "ghidra").get("image_base"),
        "image base",
    )
    references = []
    for site, edge in sorted(declared.items()):
        if _rva(edge.get("target_entry_rva"), "declared target") != _ENTRY:
            continue
        references.append(
            _reference_record(
                site=site,
                owner=_rva(edge.get("source_entry_rva"), "declared source"),
                functions=functions,
                declared=declared,
                image_base=image_base,
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
                    if value != target_va:
                        continue
                    raw = bytes(instruction.bytes)
                    site = instruction.address - image_base
                    if operand_class != "immediate" or operand_index != 0:
                        _error("unexpected residual-callee reference operand")
                    expected_raw, use_class, call_form = _reference_encoding(
                        site, _ENTRY
                    )
                    if raw != expected_raw:
                        _error("unexpected residual-callee reference encoding")
                    if use_class == "direct_call":
                        if instruction.id != x86.X86_INS_CALL:
                            _error("residual-callee call classification differs")
                    elif instruction.id != x86.X86_INS_JMP:
                        _error("residual-callee address-use classification differs")
                    if call_form == "x86_bnd_relative_near_call_f2e8" and not raw.startswith(
                        b"\xf2\xe8"
                    ):
                        _error("BND call prefix differs")
                    references.append(
                        _reference_record(
                            site=site,
                            owner=owner,
                            functions=functions,
                            declared=declared,
                            image_base=image_base,
                            observed_raw=raw,
                            operand_index=operand_index,
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
    reference_by_site = {
        _rva(row.get("instruction_rva"), "reference site"): row
        for row in references
        if _rva(row.get("instruction_rva"), "reference site")
        in _PARENT_SITES
    }
    if len(parents) != 2 or set(reference_by_site) != set(_PARENT_SITES):
        _error("parent/reference site partition differs")
    for parent in parents:
        instruction = _mapping(parent.get("instruction"), "parent instruction")
        site = _rva(instruction.get("rva"), "parent site")
        reference = reference_by_site[site]
        expected_use = "direct_call" if _PARENT_SITES[site] == "e8" else "other_address"
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
            or reference.get("use_class") != expected_use
            or not _same(
                parent.get("ghidra_declared_direct_edge"),
                reference.get("ghidra_declared_direct_edge"),
            )
        ):
            _error("parent/reference join differs")


def _outgoing_graph_join(
    outgoing: list[dict[str, Any]], graph: Mapping[str, Any]
) -> None:
    nodes = {
        _rva(row.get("rva"), "CFG node RVA"): row
        for row in _array(graph.get("nodes"), "CFG nodes")
    }
    if len(outgoing) != 1 or _OUTGOING_SITE not in nodes:
        _error("outgoing/CFG partition differs")
    edge = outgoing[0]
    node = nodes[_OUTGOING_SITE]
    if (
        edge.get("instruction")
        != {
            "rva": node.get("rva"),
            "size": node.get("size"),
            "sha256": node.get("sha256"),
        }
        or edge.get("target_entry_rva") != _hex(_OUTGOING_TARGET)
        or node.get("flow_kind")
        != "direct_unconditional_external_branch"
        or node.get("successor_rvas") != []
    ):
        _error("outgoing/CFG join differs")


def _summary() -> dict[str, Any]:
    return {
        "reviewed_target_count": 1,
        "reviewed_target_bytes": 17,
        "sealed_instruction_count": 4,
        "sealed_control_flow_graph_count": 1,
        "sealed_control_flow_graph_node_count": 4,
        "sealed_control_flow_graph_edge_count": 3,
        "native_direct_edge_count": 1,
        "direct_lua_call_count": 0,
        "staged_lua_dispatch_count": 0,
        "call_r32_count": 0,
        "opaque_indirect_control_count": 0,
        "pe_address_operand_count": 3,
        "pe_immediate_operand_count": 2,
        "pe_absolute_memory_operand_count": 1,
        "segment_qualified_memory_syntax_count": 0,
        "bnd_prefixed_control_syntax_count": 3,
        "residual_direct_target_parent_edge_count": 2,
        "target_reference_count": 1794,
        "target_reference_target_count": 1,
        "target_reference_owner_count": 1620,
        "target_reference_direct_call_count": 1793,
        "target_reference_standard_e8_call_count": 1790,
        "target_reference_bnd_f2e8_call_count": 3,
        "target_reference_other_address_count": 1,
        "target_reference_memory_operand_count": 0,
        "schema_violations": 0,
    }


def _evidence(
    residual: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    reviewed_points: list[dict[str, Any]] | None = None,
    graph: Mapping[str, Any] | None = None,
    native_syntax: Mapping[str, Any] | None = None,
    scan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prerequisites = _preflight(residual, direct_calls, program_facts)
    expected_graph = _expected_graph()
    expected_native = _expected_native_syntax(program_facts)
    expected_scan = _expected_scan(program_facts)
    graph_value = expected_graph if graph is None else dict(graph)
    native_value = expected_native if native_syntax is None else dict(native_syntax)
    scan_value = expected_scan if scan is None else dict(scan)
    if (
        not _same(graph_value, expected_graph)
        or not _same(native_value, expected_native)
        or not _same(scan_value, expected_scan)
    ):
        _error("exact component differs from the sealed structural receipt")
    parents = _parent_rows(residual, program_facts)
    _parent_scan_join(parents, scan_value)
    outgoing = _array(native_value.get("outgoing_direct"), "outgoing edges")
    _outgoing_graph_join([dict(_mapping(row, "outgoing edge")) for row in outgoing], graph_value)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(
            _mapping(program_facts.get("identity"), "program facts identity")
        ),
        "program_facts": prerequisites["program_facts"],
        "residual_direct_target_set_static_boundary": prerequisites[
            "residual_direct_target_set_static_boundary"
        ],
        "direct_call_census": prerequisites["direct_call_census"],
        "decoder": _decoder_contract(),
        "function_body": _expected_body(
            program_facts, direct_calls, reviewed_points
        ),
        "control_flow_graph": graph_value,
        "residual_direct_target_parent_edges": parents,
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
    NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError,
    PEAnchorError,
)


def validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary_structure(
    evidence: Mapping[str, Any],
    residual: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate every finite receipt field without opening the executable."""
    try:
        for item, label in (
            (evidence, "evidence"),
            (residual, "residual target set"),
            (direct_calls, "direct calls"),
            (program_facts, "program facts"),
        ):
            _validate_json_tree(item, label)
        value = _mapping(evidence, "evidence")
        expected = _evidence(residual, direct_calls, program_facts)
        if not _same(value, expected):
            _error("residual-target-set callee receipt differs")
        _assert_publication_safe(value)
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
            "build_identity": dict(value["build_identity"]),
            "evidence_sha256": _canonical_sha256(value),
            "summary": dict(value["summary"]),
        }
    except NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError:
        raise
    except _NORMALIZED_ERRORS as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError(
            str(exc)
        ) from exc


def build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary(
    executable: Path,
    residual: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact receipt from the sealed Windows executable."""
    try:
        for item, label in (
            (residual, "residual target set"),
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
        _preflight(residual, direct_calls, program_facts)
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
        instructions = _decode_range(
            data, image, _ENTRY, _BODY_SIZE, decoder
        )
        raw = b"".join(bytes(instruction.bytes) for instruction in instructions)
        if (
            len(raw) != _BODY_SIZE
            or hashlib.sha256(raw).hexdigest() != _BODY_SHA256
            or len(instructions) != len(_POINTS)
        ):
            _error("residual-callee body bytes differ")
        reviewed_points = [
            _decoded_point(
                instruction,
                image_base,
                expected_rva,
                encoded,
            )
            for instruction, (expected_rva, encoded) in zip(
                instructions, _POINTS
            )
        ]
        graph = _local_cfg(instructions, image_base, reviewed_points)
        native_syntax = _native_syntax(image, instructions, program_facts)
        scan = _scan(data, image, decoder, program_facts)
        result = _evidence(
            residual,
            direct_calls,
            program_facts,
            reviewed_points=reviewed_points,
            graph=graph,
            native_syntax=native_syntax,
            scan=scan,
        )
        if _load_executable(executable)[2] != executable_sha256:
            _error("executable changed during exact reconstruction")
        validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary_structure(
            result, residual, direct_calls, program_facts
        )
        return result
    except NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError:
        raise
    except (*_NORMALIZED_ERRORS, CsError, OSError) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError(
            str(exc)
        ) from exc


def validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary(
    executable: Path,
    evidence: Mapping[str, Any],
    residual: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and verify the exact receipt."""
    try:
        _validate_json_tree(evidence, "evidence")
        rebuilt = build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary(
            executable,
            residual,
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
    except NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError:
        raise
    except (*_NORMALIZED_ERRORS, CsError, OSError) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError(
            str(exc)
        ) from exc


def encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary(
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
    except NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError:
        raise
    except (*_NORMALIZED_ERRORS, TypeError, ValueError) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError(
            str(exc)
        ) from exc
