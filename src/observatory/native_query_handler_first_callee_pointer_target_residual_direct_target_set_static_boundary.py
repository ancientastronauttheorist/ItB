"""Static receipt for the non-cluster direct targets of the pointer target.

The three bodies are grouped only because together they cover the pointer
target's direct callees that are neither in the adjacent-callee receipt nor the
deferred multi-range callee. Decoded controls, operands, and references remain
opaque structural facts; this receipt does not infer purpose or runtime behavior.
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
    _canonical_sha256,
    _normalized_declared_edge,
    _source_identity,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError,
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _decode_range,
    _exact_keys,
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
from src.observatory.native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary import (
    ANALYSIS_KIND as CLUSTER_KIND,
    _canonical_sha256 as _cluster_canonical_sha256,
)
from src.observatory.native_query_handler_first_callee_pointer_target_static_boundary import (
    ANALYSIS_KIND as POINTER_KIND,
    _canonical_sha256 as _pointer_canonical_sha256,
)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = (
    "pe_native_query_handler_first_callee_pointer_target_"
    "residual_direct_target_set_static_boundary"
)
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_POINTER = "41ee47debe789243dfe9fd9566958846cd79cb82549acb99eafc9e2b5cfd9349"
_CLUSTER = "1385ca599a7442b2b18a45206619d520b19db1b5a2fa9c0ba5b54908831462a5"

_TARGETS = (0x372970, 0x7E70, 0x3581B3)
_BODIES = {
    0x372970: (
        50,
        "507263aae961bb903352a36e523f1a156c735dd59b51f683f55fa1470119a0cb",
        "1c4fcb33ad57b15dd5609533bb859b2d740aa6d39bfada8c6b0e6d93280f9316",
        21,
        "4765431b2eb37a03825a57399101d2fd0b893a2a64a1fd265ef64fcf6f2eb15a",
        21,
    ),
    0x7E70: (
        1,
        "ae3f4619b0413d70d3004b9131c3752153074e45725be13b9a148978895e359e",
        "63019d9648749d9eb320c21859057b6fdf9dfc1aedfe3ab0d7eb2e6461fcdcb1",
        1,
        "058b44cea2c58031b850cb70a7e210903ba8cf09163bfc2671e61185129d9778",
        0,
    ),
    0x3581B3: (
        6,
        "830f019638817ae10a1187ae4c3e39e8c131975cd1b098f357c6b74bb026cfd9",
        "5800bbedd2bf56defb8512ec1185966e6d6b4b21adee1d7df3147106559fccf5",
        1,
        "bfc11525c53b449009167bf3f1962df65c7c691d882eaa63af4e92e0d11400a9",
        0,
    ),
}
_POINT_BYTES = {
    0x372970: (
        (0x372970, "55"), (0x372971, "8bec"), (0x372973, "56"),
        (0x372974, "8b7508"), (0x372977, "57"), (0x372978, "8b7d0c"),
        (0x37297B, "8b06"), (0x37297D, "83f8fe"), (0x372980, "740d"),
        (0x372982, "8b4e04"), (0x372985, "03cf"), (0x372987, "330c38"),
        (0x37298A, "e83b4bfeff"), (0x37298F, "8b4608"),
        (0x372992, "8b4e0c"), (0x372995, "03cf"), (0x372997, "330c38"),
        (0x37299A, "5f"), (0x37299B, "5e"), (0x37299C, "5d"),
        (0x37299D, "e9284bfeff"),
    ),
    0x7E70: ((0x7E70, "c3"),),
    0x3581B3: ((0x3581B3, "ff2580657d00"),),
}
_WRITES = {
    "ebx": frozenset(),
    "esi": frozenset((0x372974, 0x37299B)),
    "edi": frozenset((0x372978, 0x37299A)),
    "esp": frozenset(
        (0x372970, 0x372973, 0x372977, 0x37298A, 0x37299A, 0x37299B, 0x37299C, 0x7E70)
    ),
}
_CFG_SUCCESSOR_POLICY = (
    "only targets within the declared atlas range appear in successor_rvas"
)

_RESIDUAL_PARENTS = (
    (0x3729DB, 0x372970), (0x3729E4, 0x7E70), (0x372A6C, 0x3581B3),
    (0x372AD2, 0x372970), (0x372B00, 0x372970),
)
_CLUSTER_PARENTS = (
    (0x372A2A, 0x378B3E), (0x372A80, 0x378B6E), (0x372AC9, 0x378B87),
    (0x372AF1, 0x378B87), (0x372B10, 0x378B55),
)
_DEFERRED_PARENTS = ((0x372A53, 0x39D580),)
_OUTGOING = (
    (0x37298A, 0x372970, 0x3574CA, "e8"),
    (0x37299D, 0x372970, 0x3574CA, "e9"),
)
_E9_REFERENCE_SITES = frozenset(
    (
        0x344108, 0x3D33A2, 0x3D3502, 0x3D37D2, 0x3D38E2,
        0x3D3993, 0x3D3B75, 0x3D3BC5, 0x3D3DD2, 0x3D3F82,
        0x3D3FE2, 0x3D4042, 0x3D4662, 0x3D4902, 0x3D4C22,
        0x3D4CE2, 0x3D57F2,
    )
)
_SCAN_COUNTS = {0x372970: (3, 1), 0x7E70: (252, 246), 0x3581B3: (481, 316)}
_OWNER_PARTITION_SHA256 = "7208e20dcdff5e939aef709c668036da819b44bd609ee34b5bbfe09109492587"
_TARGET_OWNER_PARTITION_SHA256 = "cf1feca3f9046f1e0f2f06230bc009518f70b2f3926981fbcdf5e7848416bdac"
_TARGET_REFERENCE_PARTITION_SHA256 = "e66aafd7e8153496d8f89842adb8ee37412180600ff09edd908f341a2a7187f8"

_METHOD = {
    "structural_boundary": (
        "PE-free validation reconstructs the three atlas bodies, every decoded "
        "point, body-local CFG, parent partition, declared transfer, typed PE "
        "operand, indirect-control, call-r32, and whole-atlas reference receipt. "
        "Exact bytes and the exhaustive atlas traversal require the sealed executable."
    ),
    "body_local_successor_policy": _CFG_SUCCESSOR_POLICY,
    "not_claimed": [
        "semantic kinship, analysis-label equivalence, ABI, purpose, inputs, outputs, behavior, success, or normal return",
        "runtime reachability, invocation, ordering, frequency, state mutation, termination, or effect",
        "dynamic target identity or behavior of the absolute-memory indirect jump",
        "staged Lua dispatch beyond the complete absence of local call-r32 syntax",
        "computed, indirect, data, un-atlased, dynamic, or Lua-side references",
    ],
}


class NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError(RuntimeError):
    """The residual direct-target-set receipt cannot be reproduced exactly."""


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _compact_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _identity(value: Mapping[str, Any], kind: str, digest: str, label: str) -> dict[str, Any]:
    return _source_identity(value, kind, digest, label)


def _facts_identity(program_facts: Mapping[str, Any]) -> dict[str, Any]:
    summary = _mapping(program_facts.get("summary"), "program facts summary")
    return {
        **_identity(program_facts, "pe_ghidra_program_facts", _FACTS, "program facts"),
        "function_count": summary.get("function_count"),
        "body_range_count": summary.get("body_range_count"),
        "function_body_bytes": summary.get("function_body_bytes"),
    }


def _preflight(pointer: Mapping[str, Any], cluster: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    identity = _mapping(facts.get("identity"), "program facts identity")
    if identity.get("executable_sha256") != _EXE or not all(
        _same(value.get("build_identity"), dict(identity)) for value in (pointer, cluster, direct)
    ):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("prerequisite build identity differs")
    if _pointer_canonical_sha256(pointer) != _POINTER:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("pointer-target prerequisite differs")
    if _cluster_canonical_sha256(cluster) != _CLUSTER:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("adjacent-cluster prerequisite differs")
    return (
        _facts_identity(facts),
        _identity(pointer, POINTER_KIND, _POINTER, "pointer target"),
        _identity(cluster, CLUSTER_KIND, _CLUSTER, "adjacent cluster"),
        _identity(direct, DIRECT_KIND, _DIRECT, "direct calls"),
    )


def _decoder_contract() -> dict[str, Any]:
    return {
        "name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION,
        "architecture": "x86", "mode_bits": 32, "sealed_instruction_count": 23,
        "register_call_encoding_audit": [
            {"register": register, "encoding": f"ff{0xD0 + index:02x}"}
            for index, register in enumerate(_REGISTER_NAMES)
        ],
    }


def _expected_point(rva: int, encoded: str) -> dict[str, Any]:
    raw = bytes.fromhex(encoded)
    return {
        "rva": _hex(rva), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "writes_ebx": rva in _WRITES["ebx"], "writes_esi": rva in _WRITES["esi"],
        "writes_edi": rva in _WRITES["edi"], "writes_esp": rva in _WRITES["esp"],
    }


def _decoded_point(instruction: Any, image_base: int, expected_rva: int, encoded: str) -> dict[str, Any]:
    raw = bytes.fromhex(encoded)
    if instruction.address - image_base != expected_rva or bytes(instruction.bytes) != raw:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("reviewed instruction differs")
    try:
        _reads, writes = instruction.regs_access()
        written_names = {instruction.reg_name(register).lower() for register in writes}
    except Exception as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("decoder register-write classification failed") from exc
    observed = {
        "rva": _hex(expected_rva), "size": instruction.size,
        "sha256": hashlib.sha256(bytes(instruction.bytes)).hexdigest(),
        "writes_ebx": "ebx" in written_names, "writes_esi": "esi" in written_names,
        "writes_edi": "edi" in written_names, "writes_esp": "esp" in written_names,
    }
    if observed != _expected_point(expected_rva, encoded):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("reviewed instruction register writes differ")
    return observed


def _expected_graph(entry: int) -> dict[str, Any]:
    points = [_expected_point(rva, encoded) for rva, encoded in _POINT_BYTES[entry]]
    nodes: list[dict[str, Any]] = []
    for index, point in enumerate(points):
        rva = _rva(point["rva"], "point RVA")
        next_rva = points[index + 1]["rva"] if index + 1 < len(points) else None
        if rva == 0x372980:
            flow, successors = "direct_conditional_branch", [next_rva, "0x0037298f"]
        elif rva == 0x37298A:
            flow, successors = "call_fallthrough", [next_rva]
        elif rva == 0x37299D:
            flow, successors = "direct_unconditional_external_branch", []
        elif rva == 0x7E70:
            flow, successors = "terminal", []
        elif rva == 0x3581B3:
            flow, successors = "indirect_jump", []
        elif next_rva is not None:
            flow, successors = "fallthrough", [next_rva]
        else:  # pragma: no cover
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("unclassified body-local endpoint")
        nodes.append({**point, "flow_kind": flow, "successor_rvas": sorted(successors)})
    return {
        "caller_entry_rva": _hex(entry), "range_start_rva": _hex(entry),
        "range_size": _BODIES[entry][0], "projection_kind": "body_local_instruction_cfg_v1",
        "body_local_successor_policy": _CFG_SUCCESSOR_POLICY, "nodes": nodes,
        "node_count": len(nodes), "edge_count": sum(len(node["successor_rvas"]) for node in nodes),
    }


def _local_cfg(entry: int, instructions: list[Any], image_base: int) -> dict[str, Any]:
    specs = _POINT_BYTES[entry]
    if len(instructions) != len(specs):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("body instruction count differs")
    points = [
        _decoded_point(instruction, image_base, rva, encoded)
        for instruction, (rva, encoded) in zip(instructions, specs)
    ]
    expected = _expected_graph(entry)
    graph = {**expected, "nodes": [
        {**point, "flow_kind": node["flow_kind"], "successor_rvas": list(node["successor_rvas"])}
        for point, node in zip(points, expected["nodes"])
    ]}
    if not _same(graph, expected):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("body-local CFG differs")
    return graph


def _empty_call_r32_audit() -> list[dict[str, Any]]:
    return [{"register": register, "call_rvas": []} for register in _REGISTER_NAMES]


def _direct_lua_partition(direct_calls: Mapping[str, Any]) -> dict[int, list[dict[str, Any]]]:
    result = {entry: [] for entry in _TARGETS}
    for raw_record in _array(direct_calls.get("records"), "direct-call records"):
        record = _mapping(raw_record, "direct-call record")
        entry = _rva(record.get("entry_rva"), "direct-call record entry")
        if entry in result:
            result[entry].extend(
                dict(_mapping(call, "direct Lua call"))
                for call in _array(record.get("direct_lua_import_calls"), "direct Lua calls")
            )
    if any(result.values()):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("residual direct-Lua-call partition differs")
    return result


def _expected_body(entry: int, program_facts: Mapping[str, Any]) -> dict[str, Any]:
    size, body_sha, atlas_sha, instruction_count, cfg_sha, _edge_count = _BODIES[entry]
    function = _atlas_functions(program_facts).get(entry)
    if function is None or (function.get("body_size"), function.get("body_sha256"), atlas_record_sha256(function)) != (size, body_sha, atlas_sha):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("residual atlas body differs")
    points = [_expected_point(rva, encoded) for rva, encoded in _POINT_BYTES[entry]]
    if len(points) != instruction_count:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("sealed point count differs")
    return {
        "role": "pointer_target_residual_direct_target_opaque_static_boundary",
        "entry_rva": _hex(entry), "atlas_record_sha256": atlas_sha,
        "body_size": size, "body_sha256": body_sha, "range_start_rva": _hex(entry),
        "range_size": size, "control_flow_graph_canonical_sha256": cfg_sha,
        "reviewed_points": points, "direct_lua_calls": [], "staged_lua_dispatches": [],
        "call_r32_audit": _empty_call_r32_audit(), "register_call_partition_complete": True,
        "semantic_facts": {
            "residual_grouping_only": True, "analysis_labels_opaque": True,
            "source_semantic_names_assigned": False, "runtime_or_success_claimed": False,
        },
    }


def _pointer_direct_rows(pointer: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        _mapping(row, "pointer direct row")
        for row in _array(_mapping(pointer.get("native_calls"), "pointer native calls").get("direct"), "pointer direct rows")
    ]


def _parent_pair(row: Mapping[str, Any]) -> tuple[int, int]:
    instruction = _mapping(row.get("instruction"), "parent instruction")
    return _rva(instruction.get("rva"), "parent site"), _rva(row.get("target_entry_rva"), "parent target")


def _partition_pointer_rows(pointer: Mapping[str, Any], cluster: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = _pointer_direct_rows(pointer)
    pairs = [_parent_pair(row) for row in rows]
    expected = set(_RESIDUAL_PARENTS) | set(_CLUSTER_PARENTS) | set(_DEFERRED_PARENTS)
    if len(rows) != 11 or len(pairs) != len(set(pairs)) or set(pairs) != expected:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("pointer-target direct-parent partition differs")
    by_pair = {pair: dict(row) for pair, row in zip(pairs, rows)}
    residual = [by_pair[pair] for pair in _RESIDUAL_PARENTS]
    adjacent = [by_pair[pair] for pair in _CLUSTER_PARENTS]
    deferred = [by_pair[pair] for pair in _DEFERRED_PARENTS]
    if not _same(adjacent, _array(cluster.get("pointer_target_parent_edges"), "cluster parent rows")):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("adjacent-cluster parent-row join differs")
    return residual, adjacent, deferred


def _declared_edges(program_facts: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for raw in _array(program_facts.get("ghidra_declared_direct_calls"), "declared edges"):
        edge = _mapping(raw, "declared edge")
        site = _rva(edge.get("instruction_rva"), "declared edge site")
        if site in result:
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("declared edge sites repeat")
        result[site] = edge
    return result


def _edge_rows(program_facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    declared = _declared_edges(program_facts)
    functions = _atlas_functions(program_facts)
    observed = {
        (site, _rva(edge.get("source_entry_rva"), "source"), _rva(edge.get("target_rva"), "target"))
        for site, edge in declared.items()
        if _rva(edge.get("source_entry_rva"), "source") in _TARGETS
    }
    if observed != {(site, source, target) for site, source, target, _ in _OUTGOING}:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("residual outgoing declared-edge partition differs")
    rows: list[dict[str, Any]] = []
    for site, source, target, opcode in _OUTGOING:
        edge, source_function, target_function = declared.get(site), functions.get(source), functions.get(target)
        if edge is None or source_function is None or target_function is None:
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("residual outgoing atlas join differs")
        if (_rva(edge.get("source_entry_rva"), "source"), _rva(edge.get("target_entry_rva"), "target entry"), _rva(edge.get("target_rva"), "target")) != (source, target, target):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("residual outgoing declared edge differs")
        raw = bytes((int(opcode, 16),)) + int(target - (site + 5)).to_bytes(4, "little", signed=True)
        rows.append({
            "role": "opaque_declared_direct_edge",
            "instruction": {"rva": _hex(site), "size": 5, "sha256": hashlib.sha256(raw).hexdigest()},
            "source_entry_rva": _hex(source), "source_atlas_record_sha256": atlas_record_sha256(source_function),
            "source_body_size": source_function.get("body_size"), "source_body_sha256": source_function.get("body_sha256"),
            "target_entry_rva": _hex(target), "target_atlas_record_sha256": atlas_record_sha256(target_function),
            "target_body_size": target_function.get("body_size"), "target_body_sha256": target_function.get("body_sha256"),
            "ghidra_declared_direct_edge": _normalized_declared_edge(edge), "control_encoding": opcode,
        })
    return rows


def _instruction_fact(rva: int, encoded: str) -> dict[str, Any]:
    raw = bytes.fromhex(encoded)
    return {"rva": _hex(rva), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _expected_opaque_indirect_controls() -> list[dict[str, Any]]:
    return [{
        "role": "opaque_absolute_memory_indirect_jmp_syntax",
        "instruction": _instruction_fact(0x3581B3, "ff2580657d00"),
        "control_kind": "jmp", "encoding": "ff25", "operand_class": "absolute_memory",
        "operand_index": 0, "operand_access": "read", "operand_va": "0x007d6580",
        "operand_rva": "0x003d6580", "section_name": ".rdata", "section_rva": "0x003d6000",
        "section_characteristics": "0x40000040", "section_writable": False,
        "file_backed": True, "dynamic_target_identity_or_runtime_behavior_opaque": True,
    }]


def _expected_pe_address_operands() -> list[dict[str, Any]]:
    specs = (
        (0x372980, "740d", "immediate", 0, "none", 0x77298F, "direct_conditional_branch_target", ".text", 0x1000, 0x60000020),
        (0x37298A, "e83b4bfeff", "immediate", 0, "none", 0x7574CA, "declared_direct_call_target", ".text", 0x1000, 0x60000020),
        (0x37299D, "e9284bfeff", "immediate", 0, "none", 0x7574CA, "declared_external_branch_target", ".text", 0x1000, 0x60000020),
        (0x3581B3, "ff2580657d00", "absolute_memory", 0, "read", 0x7D6580, "opaque_indirect_target_pointer_location", ".rdata", 0x3D6000, 0x40000040),
    )
    return [{
        "role": "typed_pe_address_operand", "instruction": _instruction_fact(site, encoded),
        "operand_class": operand_class, "operand_index": operand_index, "operand_access": access,
        "operand_va": _hex(value), "operand_rva": _hex(value - 0x400000),
        "control_syntax": control_syntax, "section_name": section_name,
        "section_rva": _hex(section_rva), "section_characteristics": _hex(characteristics),
        "section_writable": bool(characteristics & 0x80000000), "file_backed": True,
        "contents_or_runtime_behavior_opaque": True,
    } for (
        site, encoded, operand_class, operand_index, access, value,
        control_syntax, section_name, section_rva, characteristics,
    ) in specs]


def _operand_access(value: int) -> str:
    names = {0: "none", 1: "read", 2: "write", 3: "read_write"}
    if value not in names:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("unsupported operand access mask")
    return names[value]


def _native_syntax(image: Any, instructions: Mapping[int, list[Any]]) -> dict[str, Any]:
    import capstone.x86_const as x86

    flattened = [instruction for entry in _TARGETS for instruction in instructions[entry]]
    call_r32_sites: list[int] = []
    indirect: list[tuple[int, Any]] = []
    pe_operands: list[dict[str, Any]] = []
    for instruction in flattened:
        rva, raw = instruction.address - image.image_base, bytes(instruction.bytes)
        if len(raw) == 2 and raw[0] == 0xFF and 0xD0 <= raw[1] <= 0xD7:
            call_r32_sites.append(rva)
        if instruction.id in {x86.X86_INS_CALL, x86.X86_INS_JMP} and any(
            operand.type in {x86.X86_OP_REG, x86.X86_OP_MEM} for operand in instruction.operands
        ):
            indirect.append((rva, instruction))
        for operand_index, operand in enumerate(instruction.operands):
            if operand.type == x86.X86_OP_IMM:
                value, operand_class = int(operand.imm) & 0xFFFFFFFF, "immediate"
            elif (
                operand.type == x86.X86_OP_MEM
                and operand.mem.segment == x86.X86_REG_INVALID
                and operand.mem.base == x86.X86_REG_INVALID
                and operand.mem.index == x86.X86_REG_INVALID
            ):
                value, operand_class = int(operand.mem.disp) & 0xFFFFFFFF, "absolute_memory"
            else:
                continue
            target_rva = value - image.image_base
            section = next((
                candidate for candidate in image.sections
                if candidate.virtual_address <= target_rva < candidate.virtual_address + candidate.virtual_size
            ), None)
            if section is None:
                continue
            role_by_site = {
                0x372980: "direct_conditional_branch_target",
                0x37298A: "declared_direct_call_target",
                0x37299D: "declared_external_branch_target",
                0x3581B3: "opaque_indirect_target_pointer_location",
            }
            if rva not in role_by_site:
                raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("unreviewed PE-address operand")
            pe_operands.append({
                "role": "typed_pe_address_operand",
                "instruction": {"rva": _hex(rva), "size": instruction.size, "sha256": hashlib.sha256(raw).hexdigest()},
                "operand_class": operand_class, "operand_index": operand_index,
                "operand_access": _operand_access(operand.access), "operand_va": _hex(value),
                "operand_rva": _hex(target_rva), "control_syntax": role_by_site[rva],
                "section_name": section.name, "section_rva": _hex(section.virtual_address),
                "section_characteristics": _hex(section.characteristics),
                "section_writable": bool(section.characteristics & 0x80000000),
                "file_backed": image.rva_to_file_offset(target_rva) is not None,
                "contents_or_runtime_behavior_opaque": True,
            })
    if call_r32_sites:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("call-r32 partition differs")
    if len(indirect) != 1:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("indirect-control partition differs")
    site, instruction = indirect[0]
    if (
        site != 0x3581B3 or instruction.id != x86.X86_INS_JMP
        or bytes(instruction.bytes) != bytes.fromhex("ff2580657d00")
        or len(instruction.operands) != 1 or instruction.operands[0].type != x86.X86_OP_MEM
        or instruction.operands[0].mem.segment != x86.X86_REG_INVALID
        or instruction.operands[0].mem.base != x86.X86_REG_INVALID
        or instruction.operands[0].mem.index != x86.X86_REG_INVALID
        or (int(instruction.operands[0].mem.disp) & 0xFFFFFFFF) != 0x7D6580
        or _operand_access(instruction.operands[0].access) != "read"
    ):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("opaque indirect-jump syntax differs")
    key = lambda row: (_rva(row["instruction"]["rva"], "site"), row["operand_index"])
    pe_operands.sort(key=key)
    if not _same(pe_operands, sorted(_expected_pe_address_operands(), key=key)):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("PE-address operand partition differs")
    return {
        "opaque_indirect_controls": _expected_opaque_indirect_controls(),
        "indirect_control_partition_complete": True,
        "pe_address_operands": pe_operands,
        "pe_address_operand_partition_complete": True,
    }


_REFERENCE_KEYS = {
    "instruction_rva", "instruction_size", "instruction_sha256", "owner_entry_rva",
    "owner_atlas_record_sha256", "target_rva", "target_atlas_record_sha256",
    "target_va", "operand_class", "operand_index", "use_class", "call_form",
    "ghidra_declared_direct_edge",
}


def _reference_record(*, site: int, owner: int, target: int, functions: Mapping[int, Mapping[str, Any]], declared: Mapping[int, Mapping[str, Any]], image_base: int, opcode: int) -> dict[str, Any]:
    function, edge = functions.get(owner), declared.get(site)
    if function is None or edge is None:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("reference atlas or declared-edge join differs")
    if (_rva(edge.get("source_entry_rva"), "reference source"), _rva(edge.get("target_entry_rva"), "reference target entry"), _rva(edge.get("target_rva"), "reference target")) != (owner, target, target):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("reference declared edge differs")
    raw = bytes((opcode,)) + int(target - (site + 5)).to_bytes(4, "little", signed=True)
    return {
        "instruction_rva": _hex(site), "instruction_size": 5,
        "instruction_sha256": hashlib.sha256(raw).hexdigest(),
        "owner_entry_rva": _hex(owner), "owner_atlas_record_sha256": atlas_record_sha256(function),
        "target_rva": _hex(target), "target_atlas_record_sha256": _BODIES[target][2],
        "target_va": _hex(image_base + target), "operand_class": "immediate", "operand_index": 0,
        "use_class": "other_address" if opcode == 0xE9 else "direct_call",
        "call_form": None if opcode == 0xE9 else "x86_relative_near_call_e8",
        "ghidra_declared_direct_edge": _normalized_declared_edge(edge),
    }


def _scan(data: bytes | None, image: Any | None, decoder: Any | None, program_facts: Mapping[str, Any]) -> dict[str, Any]:
    if data is None or image is None or decoder is None:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("exact whole-atlas scan requires the sealed executable")
    import capstone.x86_const as x86

    functions, declared = _atlas_functions(program_facts), _declared_edges(program_facts)
    image_base = _rva(_mapping(program_facts.get("ghidra"), "ghidra").get("image_base"), "image base")
    targets_by_va = {image_base + target: target for target in _TARGETS}
    references: list[dict[str, Any]] = []
    range_count = byte_count = instruction_count = 0
    decoder.detail = True
    for owner, function in sorted(functions.items()):
        for raw_span in _array(function.get("ranges"), "atlas ranges"):
            span = _mapping(raw_span, "atlas range")
            start, size = _rva(span.get("start_rva"), "atlas range start"), span.get("size")
            if type(size) is not int or size <= 0:
                raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("atlas range size differs")
            instructions = _decode_range(data, image, start, size, decoder)
            range_count += 1; byte_count += size; instruction_count += len(instructions)
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
                    target = targets_by_va.get(value)
                    if target is None:
                        continue
                    raw = bytes(instruction.bytes)
                    if operand.type != x86.X86_OP_IMM or operand_index != 0 or len(raw) != 5 or raw[0] not in {0xE8, 0xE9}:
                        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("unexpected residual-target reference syntax")
                    references.append(_reference_record(
                        site=instruction.address - image_base, owner=owner, target=target,
                        functions=functions, declared=declared, image_base=image_base, opcode=raw[0],
                    ))
    if (range_count, byte_count, instruction_count) != (25490, 3735718, 1153814):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("whole-atlas scan scope differs")
    references.sort(key=lambda row: (row["target_rva"], row["instruction_rva"], row["operand_index"]))
    target_partition: list[dict[str, Any]] = []
    for target in _TARGETS:
        subset = [row for row in references if row["target_rva"] == _hex(target)]
        count, owners = _SCAN_COUNTS[target]
        if len(subset) != count or len({row["owner_entry_rva"] for row in subset}) != owners:
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("target reference partition differs")
        target_partition.append({
            "target_rva": _hex(target), "target_atlas_record_sha256": _BODIES[target][2],
            "reference_count": count, "owner_count": owners,
        })
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
    target_reference_partition = sorted([{
        "target_rva": row["target_rva"], "target_atlas_record_sha256": row["target_atlas_record_sha256"],
        "reference_count": row["reference_count"],
    } for row in target_partition], key=lambda row: row["target_rva"])
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
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("whole-atlas partition identity differs")
    return {
        "scope": {"atlas_function_count": 25312, "atlas_body_range_count": 25490,
                  "decoded_bytes": 3735718, "decoded_instructions": 1153814,
                  "all_declared_ranges_decoded": True, "operand_classes": ["absolute_memory", "immediate"]},
        "references": references, "target_partition": target_partition,
        "target_reference_partition": target_reference_partition, "owner_partition": owner_partition,
        "target_owner_partition": target_owner_partition, "partition_sha256": partition_sha256,
        "aggregates": {
            "reference_count": len(references), "target_count": 3, "owner_count": len(owner_counts),
            "target_owner_count": len(target_owner_counts),
            "direct_call_count": sum(row["use_class"] == "direct_call" for row in references),
            "other_address_count": sum(row["use_class"] == "other_address" for row in references),
            "memory_operand_count": sum(row["operand_class"] == "absolute_memory" for row in references),
        },
    }


def _reference_row(raw_row: Any, functions: Mapping[int, Mapping[str, Any]], declared: Mapping[int, Mapping[str, Any]], image_base: int) -> None:
    try:
        row = _mapping(raw_row, "reference row")
        _exact_keys(row, _REFERENCE_KEYS, "reference row")
        site = _rva(row.get("instruction_rva"), "reference site")
        owner = _rva(row.get("owner_entry_rva"), "reference owner")
        target = _rva(row.get("target_rva"), "reference target")
        if target not in _TARGETS:
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("reference target differs")
        expected = _reference_record(
            site=site, owner=owner, target=target, functions=functions, declared=declared,
            image_base=image_base, opcode=0xE9 if site in _E9_REFERENCE_SITES else 0xE8,
        )
        if not _same(row, expected):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("reference row differs")
    except NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaClassReturnHelperChainError) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError(str(exc)) from exc


def _scan_structure(scan: Any, program_facts: Mapping[str, Any]) -> None:
    value = _mapping(scan, "whole-atlas scan")
    _exact_keys(value, {
        "scope", "references", "target_partition", "target_reference_partition",
        "owner_partition", "target_owner_partition", "partition_sha256", "aggregates",
    }, "whole-atlas scan")
    expected_scope = {
        "atlas_function_count": 25312, "atlas_body_range_count": 25490,
        "decoded_bytes": 3735718, "decoded_instructions": 1153814,
        "all_declared_ranges_decoded": True, "operand_classes": ["absolute_memory", "immediate"],
    }
    if not _same(value.get("scope"), expected_scope):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("scan scope differs")
    functions, declared = _atlas_functions(program_facts), _declared_edges(program_facts)
    image_base = _rva(_mapping(program_facts.get("ghidra"), "ghidra").get("image_base"), "image base")
    references = _array(value.get("references"), "scan references")
    for row in references:
        _reference_row(row, functions, declared, image_base)
    keys = [(row["target_rva"], row["instruction_rva"], row["operand_index"]) for row in references]
    if keys != sorted(keys) or len(keys) != len(set(keys)) or len(references) != 736:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("scan reference ordering differs")
    target_partition = [{
        "target_rva": _hex(target), "target_atlas_record_sha256": _BODIES[target][2],
        "reference_count": count, "owner_count": owners,
    } for target, (count, owners) in _SCAN_COUNTS.items()]
    if not _same(value.get("target_partition"), target_partition):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("scan target partition differs")
    target_reference_partition = sorted([{
        "target_rva": row["target_rva"], "target_atlas_record_sha256": row["target_atlas_record_sha256"],
        "reference_count": row["reference_count"],
    } for row in target_partition], key=lambda row: row["target_rva"])
    if not _same(value.get("target_reference_partition"), target_reference_partition):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("scan target-reference partition differs")
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
    if not _same(value.get("owner_partition"), owner_partition):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("scan owner partition differs")
    if not _same(value.get("target_owner_partition"), target_owner_partition):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("scan target-owner partition differs")
    partition_sha256 = {
        "owner_partition": _compact_sha256(owner_partition),
        "target_owner_partition": _compact_sha256(target_owner_partition),
        "target_reference_partition": _compact_sha256(target_reference_partition),
    }
    expected_hashes = {
        "owner_partition": _OWNER_PARTITION_SHA256,
        "target_owner_partition": _TARGET_OWNER_PARTITION_SHA256,
        "target_reference_partition": _TARGET_REFERENCE_PARTITION_SHA256,
    }
    if partition_sha256 != expected_hashes or not _same(value.get("partition_sha256"), partition_sha256):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("scan partition hashes differ")
    aggregates = {
        "reference_count": 736, "target_count": 3, "owner_count": len(owner_counts),
        "target_owner_count": len(target_owner_counts),
        "direct_call_count": sum(row["use_class"] == "direct_call" for row in references),
        "other_address_count": sum(row["use_class"] == "other_address" for row in references),
        "memory_operand_count": sum(row["operand_class"] == "absolute_memory" for row in references),
    }
    if aggregates != {
        "reference_count": 736, "target_count": 3, "owner_count": 560,
        "target_owner_count": 563, "direct_call_count": 719,
        "other_address_count": 17, "memory_operand_count": 0,
    } or not _same(value.get("aggregates"), aggregates):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("scan aggregates differ")


def _pointer_partition_summary() -> dict[str, Any]:
    return {
        "pointer_target_parent_count": 11, "adjacent_cluster_parent_count": 5,
        "residual_parent_count": 5, "deferred_multirange_count": 1,
        "all_parent_edges_partitioned": True, "semantic_grouping_claimed": False,
    }


def _summary(_: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "reviewed_residual_target_count": 3, "reviewed_residual_target_bytes": 57,
        "sealed_instruction_count": 23, "sealed_control_flow_graph_count": 3,
        "sealed_control_flow_graph_node_count": 23, "sealed_control_flow_graph_edge_count": 21,
        "direct_lua_call_count": 0, "staged_lua_dispatch_count": 0, "call_r32_count": 0,
        "native_direct_edge_count": 2, "out_of_body_direct_transfer_count": 1,
        "opaque_indirect_control_count": 1, "pe_address_operand_count": 4,
        "pe_immediate_operand_count": 3, "pe_absolute_memory_operand_count": 1,
        "pointer_target_parent_edge_count": 11, "residual_parent_edge_count": 5,
        "target_reference_count": 736, "target_reference_target_count": 3,
        "target_reference_direct_call_count": 719, "target_reference_other_address_count": 17,
        "target_reference_memory_operand_count": 0, "target_reference_owner_count": 560,
        "target_reference_target_owner_count": 563, "schema_violations": 0,
    }


def build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary(
    executable: Path,
    pointer_target_static_boundary: Mapping[str, Any],
    adjacent_cluster_static_boundary: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *, inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact residual direct-target-set receipt."""
    try:
        for item, label in (
            (pointer_target_static_boundary, "pointer target"),
            (adjacent_cluster_static_boundary, "adjacent cluster"),
            (direct_calls, "direct calls"), (program_facts, "program facts"),
            (inventory, "inventory"),
        ):
            _validate_json_tree(item, label)
        direct_receipt = validate_native_lua_direct_call_census(
            executable, direct_calls, program_facts, inventory=inventory
        )
        if direct_receipt.get("status") != "verified" or direct_receipt.get("evidence_sha256") != _DIRECT:
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("direct-call prerequisite differs")
        atlas, pointer, cluster, direct = _preflight(
            pointer_target_static_boundary, adjacent_cluster_static_boundary, direct_calls, program_facts
        )
        residual_parents, cluster_parents, deferred_parents = _partition_pointer_rows(
            pointer_target_static_boundary, adjacent_cluster_static_boundary
        )
        _direct_lua_partition(direct_calls)
        data, image, executable_sha256 = _load_executable(executable)
        if executable_sha256 != _EXE:
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("executable differs")
        decoder, _ = _decoder(); decoder.detail = True
        bodies: list[dict[str, Any]] = []
        graphs: list[dict[str, Any]] = []
        instructions_by_entry: dict[int, list[Any]] = {}
        for entry in _TARGETS:
            size, body_sha, _atlas_sha, instruction_count, cfg_sha, edge_count = _BODIES[entry]
            instructions = _decode_range(data, image, entry, size, decoder)
            instructions_by_entry[entry] = instructions
            if len(instructions) != instruction_count or hashlib.sha256(b"".join(bytes(item.bytes) for item in instructions)).hexdigest() != body_sha:
                raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("residual body bytes differ")
            graph = _local_cfg(entry, instructions, image.image_base)
            if _canonical_sha256(graph) != cfg_sha or graph["node_count"] != instruction_count or graph["edge_count"] != edge_count:
                raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("residual body-local CFG identity differs")
            body = _expected_body(entry, program_facts)
            body["reviewed_points"] = [
                _decoded_point(instruction, image.image_base, rva, encoded)
                for instruction, (rva, encoded) in zip(instructions, _POINT_BYTES[entry])
            ]
            bodies.append(body); graphs.append(graph)
        native_syntax = _native_syntax(image, instructions_by_entry)
        outgoing = _edge_rows(program_facts)
        result: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND,
            "build_identity": dict(_mapping(program_facts.get("identity"), "program facts identity")),
            "atlas": atlas, "pointer_target_static_boundary": pointer,
            "adjacent_cluster_static_boundary": cluster, "direct_call_census": direct,
            "decoder": _decoder_contract(), "pointer_target_direct_partition": _pointer_partition_summary(),
            "residual_parent_rows": residual_parents, "adjacent_cluster_parent_rows": cluster_parents,
            "deferred_multirange_parent_rows": deferred_parents, "function_bodies": bodies,
            "control_flow_graphs": graphs, "out_of_body_direct_transfers": [outgoing[1]],
            "native_calls": {"outgoing_direct": outgoing, **native_syntax},
            "whole_atlas_reference_scan": _scan(data, image, decoder, program_facts),
            "method": _METHOD,
        }
        result["summary"] = _summary(result)
        _assert_publication_safe(result)
        if _load_executable(executable)[2] != executable_sha256:
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("executable changed during exact rebuild")
        validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary_structure(
            result, pointer_target_static_boundary, adjacent_cluster_static_boundary, direct_calls, program_facts
        )
        return result
    except NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassReturnHelperChainError, PEAnchorError, OSError) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError(str(exc)) from exc


def _validate_graph_structure(graphs: Any, bodies: list[Any]) -> None:
    values = _array(graphs, "control-flow graphs")
    expected = [_expected_graph(entry) for entry in _TARGETS]
    if not _same(values, expected):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("control-flow graphs differ")
    for entry, raw_graph, raw_body in zip(_TARGETS, values, bodies):
        graph, body = _mapping(raw_graph, "control-flow graph"), _mapping(raw_body, "function body")
        points = {
            _rva(_mapping(point, "reviewed point").get("rva"), "point RVA"): _mapping(point, "reviewed point")
            for point in _array(body.get("reviewed_points"), "reviewed points")
        }
        nodes = _array(graph.get("nodes"), "CFG nodes")
        if len(points) != len(nodes):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("point-to-CFG cardinality differs")
        node_rvas: set[int] = set()
        derived_edges = 0
        for raw_node in nodes:
            node = _mapping(raw_node, "CFG node")
            rva = _rva(node.get("rva"), "CFG node RVA")
            successors = [_rva(item, "CFG successor") for item in _array(node.get("successor_rvas"), "CFG successors")]
            point = points.get(rva)
            point_projection = {
                key: node.get(key)
                for key in ("rva", "size", "sha256", "writes_ebx", "writes_esi", "writes_edi", "writes_esp")
            }
            if point is None or not _same(point, point_projection):
                raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("point-to-CFG join differs")
            if rva in node_rvas or successors != sorted(set(successors)) or set(successors) - set(points):
                raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("body-local CFG successor partition differs")
            node_rvas.add(rva); derived_edges += len(successors)
        if graph.get("node_count") != len(nodes) or graph.get("edge_count") != derived_edges:
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("CFG aggregate counts differ")
        if body.get("control_flow_graph_canonical_sha256") != _BODIES[entry][4]:
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("body-to-CFG identity differs")


def _instruction_join(row: Any, reviewed: Mapping[str, Mapping[str, Any]], label: str) -> None:
    record = _mapping(row, label)
    instruction = _mapping(record.get("instruction"), f"{label} instruction")
    point = reviewed.get(instruction.get("rva"))
    projection = {key: point.get(key) for key in ("rva", "size", "sha256")} if point is not None else None
    if point is None or not _same(projection, instruction):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError(f"{label} does not join a reviewed point")


def _parent_scan_join(parent_rows: list[Any], scan: Mapping[str, Any]) -> None:
    references = {
        (row.get("instruction_rva"), row.get("target_rva")): _mapping(row, "scan reference")
        for row in _array(scan.get("references"), "scan references")
    }
    for raw_parent in parent_rows:
        parent = _mapping(raw_parent, "residual parent row")
        instruction = _mapping(parent.get("instruction"), "parent instruction")
        reference = references.get((instruction.get("rva"), parent.get("target_entry_rva")))
        if reference is None or (
            instruction.get("rva"), instruction.get("size"), instruction.get("sha256"),
            parent.get("source_entry_rva"), parent.get("source_atlas_record_sha256"),
            parent.get("target_entry_rva"), parent.get("target_atlas_record_sha256"),
            parent.get("ghidra_declared_direct_edge"),
        ) != (
            reference.get("instruction_rva"), reference.get("instruction_size"),
            reference.get("instruction_sha256"), reference.get("owner_entry_rva"),
            reference.get("owner_atlas_record_sha256"), reference.get("target_rva"),
            reference.get("target_atlas_record_sha256"), reference.get("ghidra_declared_direct_edge"),
        ):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("residual parent-to-scan join differs")


def validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary_structure(
    evidence: Mapping[str, Any],
    pointer_target_static_boundary: Mapping[str, Any],
    adjacent_cluster_static_boundary: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate every finite receipt field without opening the executable."""
    try:
        for item, label in (
            (evidence, "evidence"), (pointer_target_static_boundary, "pointer target"),
            (adjacent_cluster_static_boundary, "adjacent cluster"),
            (direct_calls, "direct calls"), (program_facts, "program facts"),
        ):
            _validate_json_tree(item, label)
        direct_receipt = validate_native_lua_direct_call_structure(direct_calls, program_facts)
        if direct_receipt.get("status") != "structurally_verified" or direct_receipt.get("evidence_sha256") != _DIRECT:
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("direct-call prerequisite differs")
        atlas, pointer, cluster, direct = _preflight(
            pointer_target_static_boundary, adjacent_cluster_static_boundary, direct_calls, program_facts
        )
        residual_parents, cluster_parents, deferred_parents = _partition_pointer_rows(
            pointer_target_static_boundary, adjacent_cluster_static_boundary
        )
        _direct_lua_partition(direct_calls)
        value = _mapping(evidence, "evidence")
        _exact_keys(value, {
            "schema_version", "analysis_kind", "build_identity", "atlas",
            "pointer_target_static_boundary", "adjacent_cluster_static_boundary",
            "direct_call_census", "decoder", "pointer_target_direct_partition",
            "residual_parent_rows", "adjacent_cluster_parent_rows",
            "deferred_multirange_parent_rows", "function_bodies", "control_flow_graphs",
            "out_of_body_direct_transfers", "native_calls", "whole_atlas_reference_scan",
            "method", "summary",
        }, "evidence")
        if type(value.get("schema_version")) is not int or value.get("schema_version") != SCHEMA_VERSION or value.get("analysis_kind") != ANALYSIS_KIND:
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("schema differs")
        if not all((
            _same(value.get("build_identity"), dict(_mapping(program_facts.get("identity"), "program facts identity"))),
            _same(value.get("atlas"), atlas), _same(value.get("pointer_target_static_boundary"), pointer),
            _same(value.get("adjacent_cluster_static_boundary"), cluster),
            _same(value.get("direct_call_census"), direct), _same(value.get("decoder"), _decoder_contract()),
            _same(value.get("pointer_target_direct_partition"), _pointer_partition_summary()),
            _same(value.get("method"), _METHOD),
        )):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("pinned prerequisite or method differs")
        if not all((
            _same(value.get("residual_parent_rows"), residual_parents),
            _same(value.get("adjacent_cluster_parent_rows"), cluster_parents),
            _same(value.get("deferred_multirange_parent_rows"), deferred_parents),
        )):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("pointer-target parent rows differ")
        bodies = _array(value.get("function_bodies"), "function bodies")
        expected_bodies = [_expected_body(entry, program_facts) for entry in _TARGETS]
        if not _same(bodies, expected_bodies):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("function bodies differ")
        _validate_graph_structure(value.get("control_flow_graphs"), bodies)
        outgoing = _edge_rows(program_facts)
        out_of_body = [outgoing[1]]
        if not _same(value.get("out_of_body_direct_transfers"), out_of_body):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("out-of-body transfer differs")
        key = lambda row: (_rva(row["instruction"]["rva"], "site"), row["operand_index"])
        expected_native = {
            "outgoing_direct": outgoing,
            "opaque_indirect_controls": _expected_opaque_indirect_controls(),
            "indirect_control_partition_complete": True,
            "pe_address_operands": sorted(_expected_pe_address_operands(), key=key),
            "pe_address_operand_partition_complete": True,
        }
        native_calls = _mapping(value.get("native_calls"), "native calls")
        if not _same(native_calls, expected_native):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("native control or operand receipt differs")
        reviewed = {
            point.get("rva"): _mapping(point, "reviewed point")
            for body in bodies
            for point in _array(_mapping(body, "function body").get("reviewed_points"), "reviewed points")
        }
        for row in outgoing:
            _instruction_join(row, reviewed, "outgoing direct edge")
        for row in _array(native_calls.get("opaque_indirect_controls"), "opaque indirect controls"):
            _instruction_join(row, reviewed, "opaque indirect control")
        for row in _array(native_calls.get("pe_address_operands"), "PE-address operands"):
            _instruction_join(row, reviewed, "PE-address operand")
        graph_nodes = {
            node.get("rva"): _mapping(node, "CFG node")
            for graph in _array(value.get("control_flow_graphs"), "control-flow graphs")
            for node in _array(_mapping(graph, "control-flow graph").get("nodes"), "CFG nodes")
        }
        external_node, indirect_node = graph_nodes.get("0x0037299d"), graph_nodes.get("0x003581b3")
        if (
            external_node is None or external_node.get("flow_kind") != "direct_unconditional_external_branch"
            or external_node.get("successor_rvas") != [] or indirect_node is None
            or indirect_node.get("flow_kind") != "indirect_jump" or indirect_node.get("successor_rvas") != []
            or not _same(out_of_body[0], outgoing[1])
        ):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("external or indirect body-local CFG join differs")
        scan = _mapping(value.get("whole_atlas_reference_scan"), "whole-atlas scan")
        _scan_structure(scan, program_facts)
        _parent_scan_join(residual_parents, scan)
        if not _same(value.get("summary"), _summary(value)):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("summary differs")
        _assert_publication_safe(value)
        return {
            "schema_version": SCHEMA_VERSION, "analysis_kind": STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified", "build_identity": dict(value["build_identity"]),
            "evidence_sha256": _canonical_sha256(value), "summary": dict(value["summary"]),
        }
    except NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassReturnHelperChainError, PEAnchorError) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError(str(exc)) from exc


def validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary(
    executable: Path,
    evidence: Mapping[str, Any],
    pointer_target_static_boundary: Mapping[str, Any],
    adjacent_cluster_static_boundary: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *, inventory: Mapping[str, Any],
) -> dict[str, Any]:
    rebuilt = build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary(
        executable, pointer_target_static_boundary, adjacent_cluster_static_boundary,
        direct_calls, program_facts, inventory=inventory,
    )
    if not _same(evidence, rebuilt):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError("evidence differs from exact rebuild")
    return {
        "schema_version": SCHEMA_VERSION, "analysis_kind": VERIFICATION_KIND,
        "status": "verified", "build_identity": dict(rebuilt["build_identity"]),
        "evidence_sha256": _canonical_sha256(rebuilt), "summary": dict(rebuilt["summary"]),
    }


def encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary(value: Mapping[str, Any]) -> str:
    try:
        _validate_json_tree(value)
        return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    except NativeLuaCClosurePublicationError as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError(str(exc)) from exc
