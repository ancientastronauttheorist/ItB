"""Normalized exact boundaries for two relationship-selected leaf callees.

Operand/access and register facts describe decoder syntax, not runtime effects.
The PE-free check recognizes a sealed receipt; it cannot substitute for the PE.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import capstone as cs
import capstone.x86_const as x86

from src.observatory.native_assertion_helper_second_child_callee_frontier import (
    _decode_body,
    _edge,
    _point,
    _witness,
)
from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_setfield_publications import (
    _assert_publication_safe,
    _atlas_functions,
    _decode_range,
    _validate_json_tree,
)
from src.observatory.native_lua_class_return_helper_chain import (
    _canonical_bytes,
    _canonical_sha256,
    _source_identity,
)
from src.observatory.native_lua_direct_calls import (
    _decoder,
    _load_executable,
    SUPPORTED_CAPSTONE_VERSION,
    validate_native_lua_direct_call_census,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_assertion_helper_leaf_callees"
SEALED_SHA256 = "1ef7c1874b83e871f3afa9d482c2c6f01cd541c50f81b342605d80946a93f3c2"
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
BASE = 0x400000
TARGETS = {
    0x3586B6: {
        "size": 8,
        "body_sha256": "f8a6075ff89f74e881840fcfc83e2b42f7bb95a5c3a1de7c269d37871bb6462c",
        "atlas_sha256": "487bf1f213ec3f1d5ef5a3f3ab4f5e9de1c7c3738a69edb7e0f810f12557ed7d",
        "instructions": 2,
        "cfg_edges": 1,
    },
    0x370960: {
        "size": 346,
        "body_sha256": "2607fbcc1ed351e6ec2189f6d8dbc41cd852954cce218e92cd8bf4b6aa976aa9",
        "atlas_sha256": "7daad6a811e51b3a97da0b3ffe13bd3bde971b8d8fdedb31e0c51732a6233be3",
        "instructions": 89,
        "cfg_edges": 102,
    },
}
SOURCE_PINS = {
    "pair": (
        "pe_native_assertion_helper_descendant_pair",
        "47421700f38e3dbf3f5283bf89d3beb5d6421d32eaf05938ad58989908f93d0b",
    ),
    "reused_callee": (
        "pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary",
        "8e8a4c0d5c462bf20417b529313e634a76030214c34c35f0875e506a4f57f8b1",
    ),
    "direct_calls": (
        "pe_native_lua_direct_import_call_census",
        "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608",
    ),
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
}
SCOPE = {"functions": 25312, "ranges": 25490, "bytes": 3735718, "instructions": 1153814}
REGISTERS = ("EAX", "ECX", "EDX", "EBX", "ESP", "EBP", "ESI", "EDI")


class LeafError(RuntimeError):
    """Exact identity, decoded partition, or a receipt join differs."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LeafError(message)


def _normalize(operation: Any) -> Any:
    try:
        return operation()
    except LeafError:
        raise
    except Exception as exc:
        raise LeafError(str(exc)) from exc


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _preflight(sources: Mapping[str, Any]) -> dict[str, Any]:
    _validate_json_tree(sources, "sources")
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    result = {
        name: _source_identity(sources[name], kind, digest, name)
        for name, (kind, digest) in SOURCE_PINS.items()
    }
    identity = sources["program_facts"]["identity"]
    _require(identity["executable_sha256"] == EXE_SHA256, "build identity differs")
    for name in ("pair", "reused_callee", "direct_calls"):
        _require(
            _canonical_bytes(sources[name]["build_identity"])
            == _canonical_bytes(identity),
            "source build differs",
        )
    return result


def _parents(sources: Mapping[str, Any]) -> list[dict[str, Any]]:
    facts = sources["program_facts"]
    functions = _atlas_functions(facts)
    body = sources["pair"]["bodies"][0]
    _require(body["entry_rva"] == "0x00379d28", "source caller differs")
    edges = body["native_controls"]["direct_calls"]
    expected = [
        (0x379D47, 0x3586B6),
        (0x379D58, 0x370960),
        (0x379D6B, 0x370960),
        (0x379E4E, 0x3586B6),
        (0x379E5A, 0x3574CA),
    ]
    _require(len(edges) == len(expected), "parent direct partition differs")
    result = []
    for index, (row, (site, target)) in enumerate(zip(edges, expected)):
        target_hash = atlas_record_sha256(functions[target])
        _require(
            int(row["instruction"]["rva"], 16) == site
            and int(row["target_entry_rva"], 16) == target
            and row["target_atlas_record_sha256"] == target_hash,
            "parent target differs",
        )
        _require(
            row["declared_edge"] == _edge(facts, site, 0x379D28, target),
            "parent declared edge differs",
        )
        joined = {
            "source_path": ["bodies", 0, "native_controls", "direct_calls", index],
            "source_canonical_sha256": SOURCE_PINS["pair"][1],
            "edge": dict(row),
            "target_evidence": "new_body" if target in TARGETS else "reused_callee",
        }
        if target not in TARGETS:
            receipt = sources["reused_callee"]
            reused = receipt["function_body"]
            _require(
                reused["entry_rva"] == "0x003574ca"
                and reused["body_sha256"] == functions[target]["body_sha256"]
                and reused["atlas_record_sha256"] == target_hash,
                "reused body differs",
            )
            refs = receipt["whole_atlas_reference_scan"]["references"]
            matches = [
                (i, r)
                for i, r in enumerate(refs)
                if int(r["instruction_rva"], 16) == site
            ]
            _require(len(matches) == 1, "reused incoming reference differs")
            i, r = matches[0]
            _require(
                r["owner_entry_rva"] == "0x00379d28"
                and r["target_rva"] == "0x003574ca"
                and r["target_atlas_record_sha256"] == target_hash
                and r["instruction_sha256"] == row["instruction"]["sha256"]
                and r["instruction_size"] == row["instruction"]["size"]
                and r["ghidra_declared_direct_edge"] == row["declared_edge"],
                "reused reference join differs",
            )
            joined.update(
                reused_source_canonical_sha256=SOURCE_PINS["reused_callee"][1],
                reference_path=["whole_atlas_reference_scan", "references", i],
                incoming_reference=dict(r),
            )
        result.append(joined)
    return result


def _graph(rows: list[Any], entry: int) -> dict[str, Any]:
    nodes = []
    for row in rows:
        site = row.address - BASE
        successors, flow = [site + len(row.bytes)], "fallthrough"
        _require(
            not row.group(cs.CS_GRP_CALL) and not row.group(cs.CS_GRP_INT),
            "unreviewed call or interrupt",
        )
        if row.group(cs.CS_GRP_JUMP):
            _require(row.operands[0].type == x86.X86_OP_IMM, "unreviewed indirect jump")
            target = int(row.operands[0].imm) - BASE
            if row.id == x86.X86_INS_JMP:
                successors, flow = [target], "direct_unconditional_branch"
            else:
                _require(
                    row.id
                    in (
                        x86.X86_INS_JE,
                        x86.X86_INS_JNE,
                        x86.X86_INS_JAE,
                        x86.X86_INS_JB,
                        x86.X86_INS_JL,
                        x86.X86_INS_JLE,
                    ),
                    "unreviewed conditional branch",
                )
                successors, flow = (
                    sorted({successors[0], target}),
                    "direct_conditional_branch",
                )
        elif row.group(cs.CS_GRP_RET):
            successors, flow = [], "return_syntax"
        repeated = row.id == x86.X86_INS_STOSB and 0xF3 in row.prefix
        _require(all(p in (0, 0x66, 0xF3) for p in row.prefix), "unreviewed prefix")
        _require(0xF3 not in row.prefix or repeated, "unreviewed repeat prefix")
        if repeated:
            flow = "repeated_string_possible_completion"
        reads, writes = row.regs_access()
        nodes.append(
            _point(row)
            | {
                "flow_kind": flow,
                "successor_rvas": [_hex(s) for s in successors],
                "decoder_reads_registers": sorted({row.reg_name(r) for r in reads}),
                "decoder_writes_registers": sorted({row.reg_name(r) for r in writes}),
                "legacy_66_prefix": 0x66 in row.prefix,
                "repeat_prefix": repeated,
            }
        )
    sites = {n["rva"] for n in nodes}
    _require(
        len(nodes) == TARGETS[entry]["instructions"] and len(sites) == len(nodes),
        "CFG count differs",
    )
    _require(
        all(s in sites for n in nodes for s in n["successor_rvas"]), "CFG escapes body"
    )
    _require(
        sum(len(n["successor_rvas"]) for n in nodes) == TARGETS[entry]["cfg_edges"],
        "CFG edge count differs",
    )
    return {
        "entry_rva": _hex(entry),
        "nodes": nodes,
        "node_count": len(nodes),
        "edge_count": sum(len(n["successor_rvas"]) for n in nodes),
        "granularity": "instruction_syntax",
        "repeat_micro_iterations_expanded": False,
    }


def _address(image: Any, value: int) -> dict[str, Any]:
    rva = value - BASE
    matches = [
        s
        for s in image.sections
        if s.virtual_address
        <= rva
        < s.virtual_address + max(s.virtual_size, s.raw_size)
    ]
    _require(len(matches) == 1, "absolute address section differs")
    section = matches[0]
    offset = image.rva_to_file_offset(rva)
    return {
        "va": _hex(value),
        "rva": _hex(rva),
        "section_name": section.name,
        "section_rva": _hex(section.virtual_address),
        "section_characteristics": _hex(section.characteristics),
        "section_writable": bool(section.characteristics & 0x80000000),
        "file_backed": offset is not None,
        "file_offset": None if offset is None else _hex(offset),
        "contents_and_runtime_meaning_opaque": True,
    }


def _operands(rows: list[Any], image: Any) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        control = row.group(cs.CS_GRP_CALL) or row.group(cs.CS_GRP_JUMP)
        for index, operand in enumerate(row.operands):
            value = {
                "instruction": _point(row),
                "operand_index": index,
                "size": operand.size,
                "decoder_access": int(operand.access),
            }
            if operand.type == x86.X86_OP_REG:
                value.update(kind="register", register=row.reg_name(operand.reg))
            elif operand.type == x86.X86_OP_IMM:
                value.update(
                    kind="immediate",
                    value_u32=_hex(int(operand.imm) & 0xFFFFFFFF),
                    control_target=bool(control),
                )
            elif operand.type == x86.X86_OP_MEM:
                memory = operand.mem
                value.update(
                    kind="memory_expression",
                    segment=row.reg_name(memory.segment) or None,
                    base=row.reg_name(memory.base) or None,
                    index=row.reg_name(memory.index) or None,
                    scale=memory.scale,
                    displacement=memory.disp,
                )
                if memory.base == memory.index == memory.segment == 0:
                    value["absolute_pe_address"] = _address(
                        image, memory.disp & 0xFFFFFFFF
                    )
                # LEA and register-relative operands remain syntax only.
            else:
                raise LeafError("unsupported operand class")
            result.append(value)
    return result


def _controls(
    rows: list[Any], entry: int, image: Any, facts: Mapping[str, Any]
) -> dict[str, Any]:
    _require(
        not any(r.group(cs.CS_GRP_CALL) or r.group(cs.CS_GRP_INT) for r in rows),
        "unexpected call or interrupt",
    )
    _require(
        not any(
            int(r["source_entry_rva"], 16) == entry
            for r in facts["ghidra_declared_direct_calls"]
        ),
        "declared outgoing calls differ",
    )
    return {
        "direct_calls": [],
        "import_controls": [],
        "register_calls": [{"register": r, "call_rvas": []} for r in REGISTERS],
        "interrupts": [],
        "partitions_complete_for_pinned_bodies": True,
    }


def _small_effect(rows: list[Any], image: Any) -> dict[str, Any]:
    first, last = rows
    _require(
        first.id == x86.X86_INS_AND
        and len(first.operands) == 2
        and first.operands[0].type == x86.X86_OP_MEM
        and first.operands[0].size == 4
        and first.operands[0].mem.base
        == first.operands[0].mem.index
        == first.operands[0].mem.segment
        == 0
        and first.operands[0].mem.disp == BASE + 0x4B6E58
        and first.operands[1].type == x86.X86_OP_IMM
        and first.operands[1].imm == 0
        and last.id == x86.X86_INS_RET
        and len(last.operands) == 0,
        "small-body effect grammar differs",
    )
    return {
        "instruction": _point(first),
        "location": _address(image, BASE + 0x4B6E58),
        "width_bits": 32,
        "operation_class": "read_modify_write",
        "result_on_normal_instruction_completion": "zero",
        "following_return": _point(last),
        "evidence_class": "static_instruction_semantics",
        "scope": "Conditional effect of the first instruction, not proof of execution, normal function return, global purpose, ownership, concurrency behavior or accounting promotion.",
    }


def _relocations(image: Any) -> dict[str, Any]:
    rva, size = image.data_directories[5]
    _require((rva, size) == (0x539000, 0x35618), "relocation directory differs")
    directory = _witness(image, rva, size)
    cursor = int(directory["file_offset"], 16)
    end = cursor + size
    sites = []
    while cursor < end:
        page, length = struct.unpack_from("<II", image.data, cursor)
        _require(
            length >= 8 and length % 2 == 0 and cursor + length <= end,
            "malformed relocation block",
        )
        for at in range(cursor + 8, cursor + length, 2):
            item = struct.unpack_from("<H", image.data, at)[0]
            site, kind = page + (item & 0xFFF), item >> 12
            owners = [
                entry
                for entry, p in TARGETS.items()
                if entry <= site < entry + p["size"]
            ]
            if kind and owners:
                _require(len(owners) == 1 and kind == 3, "unreviewed body relocation")
                operand = _witness(image, site, 4)
                value = struct.unpack_from(
                    "<I", image.data, int(operand["file_offset"], 16)
                )[0]
                sites.append(
                    {
                        "owner_entry_rva": _hex(owners[0]),
                        "site_rva": _hex(site),
                        "type": "HIGHLOW",
                        "entry_file_offset": _hex(at),
                        "entry_sha256": hashlib.sha256(
                            image.data[at : at + 2]
                        ).hexdigest(),
                        "operand": operand,
                        "value_va": _hex(value),
                    }
                )
        cursor += length
    _require(len(sites) == 4, "relocation frontier count differs")
    return {"directory": directory, "sites": sites}


def _scan(data: bytes, image: Any, facts: Mapping[str, Any]) -> dict[str, Any]:
    decoder, _ = _decoder()
    decoder.detail = True
    refs = []
    counts = Counter(functions=0, ranges=0, bytes=0, instructions=0)
    for owner, function in sorted(_atlas_functions(facts).items()):
        counts["functions"] += 1
        for span in function["ranges"]:
            rows = _decode_range(
                data, image, int(span["start_rva"], 16), span["size"], decoder
            )
            counts.update(ranges=1, bytes=span["size"], instructions=len(rows))
            for row in rows:
                for index, operand in enumerate(row.operands):
                    if operand.type == x86.X86_OP_IMM:
                        target = (int(operand.imm) & 0xFFFFFFFF) - BASE
                        operand_class = "immediate"
                    elif (
                        operand.type == x86.X86_OP_MEM
                        and operand.mem.base
                        == operand.mem.index
                        == operand.mem.segment
                        == 0
                    ):
                        target = (int(operand.mem.disp) & 0xFFFFFFFF) - BASE
                        operand_class = "absolute_memory"
                    else:
                        continue
                    if target not in TARGETS:
                        continue
                    _require(
                        index == 0
                        and row.id == x86.X86_INS_CALL
                        and len(row.bytes) == 5
                        and row.bytes[0] == 0xE8,
                        "unreviewed target-entry reference syntax",
                    )
                    refs.append(
                        {
                            "instruction": _point(row),
                            "owner_entry_rva": _hex(owner),
                            "owner_atlas_record_sha256": atlas_record_sha256(function),
                            "target_entry_rva": _hex(target),
                            "target_atlas_record_sha256": TARGETS[target][
                                "atlas_sha256"
                            ],
                            "operand_class": operand_class,
                            "operand_index": index,
                            "declared_edge": _edge(
                                facts, row.address - BASE, owner, target
                            ),
                        }
                    )
    _require(dict(counts) == SCOPE, "atlas decode scope differs")
    partitions = [
        {
            "entry_rva": _hex(entry),
            "reference_count": sum(r["target_entry_rva"] == _hex(entry) for r in refs),
            "owner_count": len(
                {
                    r["owner_entry_rva"]
                    for r in refs
                    if r["target_entry_rva"] == _hex(entry)
                }
            ),
        }
        for entry in sorted(TARGETS)
    ]
    return {
        "scope": dict(counts),
        "references": refs,
        "reference_count": len(refs),
        "owner_count": len({r["owner_entry_rva"] for r in refs}),
        "target_partitions": partitions,
        "references_canonical_sha256": _canonical_sha256(refs),
    }


def _summary(
    bodies: list[dict[str, Any]],
    scan: Mapping[str, Any],
    relocations: Mapping[str, Any],
) -> dict[str, int]:
    operands = [o for b in bodies for o in b["operands"]]
    return {
        "target_count": len(bodies),
        "target_bytes": sum(b["body_size"] for b in bodies),
        "instructions": sum(len(b["points"]) for b in bodies),
        "cfg_nodes": sum(b["control_flow_graph"]["node_count"] for b in bodies),
        "cfg_edges": sum(b["control_flow_graph"]["edge_count"] for b in bodies),
        "parent_edges": 5,
        "reused_targets": 1,
        "outgoing_native_edges": sum(
            len(b["native_controls"]["direct_calls"]) for b in bodies
        ),
        "import_controls": sum(
            len(b["native_controls"]["import_controls"]) for b in bodies
        ),
        "explicit_operands": len(operands),
        "ordinary_immediates": sum(
            o["kind"] == "immediate" and not o["control_target"] for o in operands
        ),
        "absolute_pe_address_operands": sum(
            "absolute_pe_address" in o for o in operands
        ),
        "memory_expression_operands": sum(
            o["kind"] == "memory_expression" for o in operands
        ),
        "segment_register_operands": sum(
            o.get("register") in ("ss", "cs", "ds", "es", "fs", "gs") for o in operands
        ),
        "highlow_sites": len(relocations["sites"]),
        "incoming_references": scan["reference_count"],
        "incoming_owners": scan["owner_count"],
    }


def _build_unsealed(
    executable: Path, sources: Mapping[str, Any], inventory: Mapping[str, Any]
) -> dict[str, Any]:
    identities = _preflight(sources)
    facts = sources["program_facts"]
    checked = validate_native_lua_direct_call_census(
        executable, sources["direct_calls"], facts, inventory=inventory
    )
    _require(
        checked["status"] == "verified"
        and checked["evidence_sha256"] == SOURCE_PINS["direct_calls"][1],
        "exact direct-call prerequisite failed",
    )
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    parents = _parents(sources)
    caller = {r.address - BASE: r for r in _decode_body(data, image, facts, 0x379D28)}
    for item in parents:
        edge = item["edge"]
        row = caller[int(edge["instruction"]["rva"], 16)]
        _require(
            _point(row) == edge["instruction"]
            and row.id == x86.X86_INS_CALL
            and row.operands[0].type == x86.X86_OP_IMM
            and row.operands[0].imm - BASE == int(edge["target_entry_rva"], 16),
            "exact parent edge differs",
        )
    bodies = []
    functions = _atlas_functions(facts)
    for entry, profile in sorted(TARGETS.items()):
        function = functions[entry]
        _require(
            function["body_size"] == profile["size"]
            and function["body_sha256"] == profile["body_sha256"]
            and atlas_record_sha256(function) == profile["atlas_sha256"],
            "target atlas differs",
        )
        rows = _decode_body(data, image, facts, entry)
        _require(len(rows) == profile["instructions"], "instruction count differs")
        bodies.append(
            {
                "entry_rva": _hex(entry),
                "body_size": profile["size"],
                "body_sha256": profile["body_sha256"],
                "atlas_record_sha256": profile["atlas_sha256"],
                "points": [_point(r) for r in rows],
                "analysis_metadata": {
                    k: function[k]
                    for k in ("name", "name_source", "namespace", "thunk")
                }
                | {"metadata_only": True},
                "control_flow_graph": _graph(rows, entry),
                "native_controls": _controls(rows, entry, image, facts),
                "operands": _operands(rows, image),
            }
        )
        if entry == 0x3586B6:
            bodies[-1]["conditional_effect"] = _small_effect(rows, image)
    scan, relocations = _scan(data, image, facts), _relocations(image)
    replay, replay_image, replay_digest = _load_executable(executable)
    _require(
        data == replay and replay_digest == digest and replay_image.image_base == BASE,
        "executable changed during build",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(facts["identity"]),
        "source_receipts": identities,
        "parent_edges": parents,
        "bodies": bodies,
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
        },
        "base_relocations": relocations,
        "whole_atlas_reference_scan": scan,
        "summary": _summary(bodies, scan, relocations),
        "method": {
            "scope": "Both previously unsealed native callees of the 315-byte assertion descendant, plus a source and incoming-reference join to the previously sealed third target.",
            "structural_validation": "Hash-pinned normalized receipt consistency with recomputed source, parent, graph, operand and count joins; not independent binary evidence.",
            "exact_validation": "Exact PE and direct-call census verification, caller edge and target body byte checks, decoded bodies, raw relocation witnesses, and a complete all-operand atlas entry-reference scan. Parent and reused receipts are canonical-pinned without rerunning their original analyses.",
            "not_claimed": [
                "CRT or memset identity, ABI, global ownership, runtime behavior, or accounting-level promotion",
                "Decoder access flags are syntax; LEA does not establish a memory read. Legacy 66 prefixes may select SIMD opcodes rather than word operands.",
                "REP STOSB is one syntactic node with possible completion fallthrough, not an expanded loop or proof of direction, bounds, completion, exception behavior or runtime memory effects.",
                "Return syntax does not prove normal completion. SIMD paths require independent operational and platform assumptions before behavior can be promoted.",
                "Global data ownership and consumers; computed, indirect, data-only, un-atlased, generated or Lua-side target-entry references",
            ],
        },
    }


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        identities = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256, "sealed leaf receipt differs"
        )
        _require(
            evidence["schema_version"] == SCHEMA_VERSION
            and evidence["analysis_kind"] == ANALYSIS_KIND
            and evidence["source_receipts"] == identities
            and evidence["parent_edges"] == _parents(sources),
            "source or parent joins differ",
        )
        bodies = evidence["bodies"]
        _require(
            [int(b["entry_rva"], 16) for b in bodies] == sorted(TARGETS),
            "body partition differs",
        )
        for body in bodies:
            graph = body["control_flow_graph"]
            nodes = graph["nodes"]
            sites = {n["rva"] for n in nodes}
            _require(
                len(nodes) == len(sites) == graph["node_count"]
                and sum(len(n["successor_rvas"]) for n in nodes) == graph["edge_count"]
                and sum(n["size"] for n in nodes) == body["body_size"],
                "CFG counts differ",
            )
            _require(
                all(s in sites for n in nodes for s in n["successor_rvas"]),
                "CFG node closure differs",
            )
            _require(
                all(o["instruction"]["rva"] in sites for o in body["operands"]),
                "operand point join differs",
            )
        scan = evidence["whole_atlas_reference_scan"]
        refs = scan["references"]
        for parent in evidence["parent_edges"]:
            if parent["target_evidence"] != "new_body":
                continue
            edge = parent["edge"]
            _require(
                sum(
                    r["instruction"] == edge["instruction"]
                    and r["target_entry_rva"] == edge["target_entry_rva"]
                    and r["owner_entry_rva"] == "0x00379d28"
                    for r in refs
                )
                == 1,
                "parent incoming join differs",
            )
        _require(
            scan["references_canonical_sha256"] == _canonical_sha256(refs),
            "reference hash differs",
        )
        _require(
            evidence["summary"] == _summary(bodies, scan, evidence["base_relocations"]),
            "summary differs",
        )
        _assert_publication_safe(evidence)
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": ANALYSIS_KIND + "_structure_verification",
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_leaves(
    executable: Path, sources: Mapping[str, Any], *, inventory: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(executable, sources, inventory)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_leaves(
    executable: Path,
    evidence: Mapping[str, Any],
    sources: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        rebuilt = build_leaves(executable, sources, inventory=inventory)
        _require(
            _canonical_bytes(evidence) == _canonical_bytes(rebuilt),
            "exact rebuild differs",
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": ANALYSIS_KIND + "_verification",
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(rebuilt["summary"]),
        }

    return _normalize(run)


def encode_leaves(value: Mapping[str, Any]) -> str:
    def run() -> str:
        _require(isinstance(value, Mapping), "encoded leaf receipt is not a mapping")
        return (
            json.dumps(
                dict(value),
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        )

    return _normalize(run)
