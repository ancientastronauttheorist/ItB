"""Exact structural joins for the assertion second child's direct callees.

Only normalized facts and hashes are published. Interrupt/call fallthrough is
syntactic possibility, never a claim that the operation returns at runtime.
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
ANALYSIS_KIND = "pe_native_assertion_helper_second_child_callee_frontier"
SEALED_SHA256 = "39a712704c58f0789580ebac647ce13ae23681a1df12f0dc93d549159e37ddeb"
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
ENTRY, SIZE, BASE = 0x379F1F, 51, 0x400000
BODY_SHA256 = "cee94b4583219523725afbfd16dbcf538173e6cfe47800c70d3246796b6c6a20"
ATLAS_SHA256 = "697696782a1427361f7866422ee2ca01fb0144a34fcacc55b5bb5f73125d7ae5"
SOURCE_PINS = {
    "second_child": (
        "pe_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_v2",
        "918628e05e4579a40127416853ed5e1af91fa6516e86798a48107a65f433be19",
    ),
    "first_child": (
        "pe_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary",
        "314c5817e3a1560c446853474cc0f86fbf3a8195fb60f48c85822a3ed8aca3bc",
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


class FrontierError(RuntimeError):
    """An exact identity, decoded partition, or structural join differs."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FrontierError(message)


def _normalize(operation: Any) -> Any:
    try:
        return operation()
    except FrontierError:
        raise
    except Exception as exc:
        raise FrontierError(str(exc)) from exc


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _preflight(sources: Mapping[str, Any]) -> dict[str, Any]:
    _validate_json_tree(sources, "sources")
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    identities = {
        name: _source_identity(sources[name], kind, digest, name)
        for name, (kind, digest) in SOURCE_PINS.items()
    }
    identity = sources["program_facts"]["identity"]
    _require(identity["executable_sha256"] == EXE_SHA256, "build identity differs")
    for name in SOURCE_PINS.keys() - {"program_facts"}:
        _require(
            _canonical_bytes(sources[name]["build_identity"])
            == _canonical_bytes(identity),
            "source build differs",
        )
    return identities


def _point(row: Any) -> dict[str, Any]:
    return {
        "rva": _hex(row.address - BASE),
        "size": len(row.bytes),
        "sha256": hashlib.sha256(bytes(row.bytes)).hexdigest(),
    }


def _edge(
    facts: Mapping[str, Any], site: int, owner: int, target: int
) -> dict[str, Any]:
    matches = [
        r
        for r in facts["ghidra_declared_direct_calls"]
        if int(r["instruction_rva"], 16) == site
    ]
    _require(len(matches) == 1, "declared edge missing or duplicated")
    row = matches[0]
    _require(
        (
            int(row["source_entry_rva"], 16),
            int(row["target_entry_rva"], 16),
            int(row["target_rva"], 16),
        )
        == (owner, target, target),
        "declared edge differs",
    )
    return {
        k: row[k]
        for k in (
            "instruction_rva",
            "source_entry_rva",
            "target_entry_rva",
            "target_rva",
        )
    } | {"target_name_sha256": hashlib.sha256(row["target_name"].encode()).hexdigest()}


def _joins(sources: Mapping[str, Any]) -> list[dict[str, Any]]:
    facts = sources["program_facts"]
    functions = _atlas_functions(facts)
    parent = sources["second_child"]
    edges = parent["native_calls"]["outgoing_direct"]
    expected = [
        (0x379E88, 0x38EDB6, "first_child"),
        (0x379EBD, 0x3574CA, "reused_callee"),
        (0x379EEC, ENTRY, None),
    ]
    _require(
        len(edges) == 3
        and parent["native_calls"]["outgoing_direct_partition_complete"] is True,
        "parent frontier differs",
    )
    result = []
    for edge, (site, target, source) in zip(edges, expected):
        _require(
            (
                int(edge["instruction"]["rva"], 16),
                int(edge["source_entry_rva"], 16),
                int(edge["target_entry_rva"], 16),
            )
            == (site, 0x379E77, target),
            "parent edge differs",
        )
        target_hash = atlas_record_sha256(functions[target])
        _require(
            edge["target_atlas_record_sha256"] == target_hash,
            "parent target identity differs",
        )
        _require(
            edge["ghidra_declared_direct_edge"] == _edge(facts, site, 0x379E77, target),
            "parent atlas edge differs",
        )
        joined = {
            "parent_edge": dict(edge),
            "target_atlas_record_sha256": target_hash,
            "evidence": source or "new_function_body",
            "behavior_opaque": True,
        }
        if source is not None:
            receipt = sources[source]
            body = receipt["function_body"]
            _require(
                int(body["entry_rva"], 16) == target
                and body["body_sha256"] == functions[target]["body_sha256"],
                "reused body identity differs",
            )
            refs = receipt["whole_atlas_reference_scan"]["references"]
            matches = [
                (i, r)
                for i, r in enumerate(refs)
                if int(r["instruction_rva"], 16) == site
            ]
            _require(len(matches) == 1, "reused incoming reference differs")
            index, reference = matches[0]
            _require(
                reference["owner_entry_rva"] == "0x00379e77"
                and reference["target_rva"] == _hex(target)
                and reference["target_atlas_record_sha256"] == target_hash
                and reference["instruction_sha256"] == edge["instruction"]["sha256"]
                and reference["ghidra_declared_direct_edge"]
                == edge["ghidra_declared_direct_edge"],
                "cross-receipt reference differs",
            )
            joined.update(
                {
                    "source_canonical_sha256": SOURCE_PINS[source][1],
                    "reference_path": [
                        "whole_atlas_reference_scan",
                        "references",
                        index,
                    ],
                    "incoming_reference": dict(reference),
                }
            )
        result.append(joined)
    return result


def _decode_body(
    data: bytes, image: Any, facts: Mapping[str, Any], entry: int
) -> list[Any]:
    function = _atlas_functions(facts)[entry]
    spans = function["ranges"]
    _require(
        len(spans) == 1 and int(spans[0]["start_rva"], 16) == entry,
        "body range differs",
    )
    size = spans[0]["size"]
    decoder, _ = _decoder()
    decoder.detail = True
    rows = _decode_range(data, image, entry, size, decoder)
    _require(
        hashlib.sha256(b"".join(bytes(r.bytes) for r in rows)).hexdigest()
        == function["body_sha256"],
        "body bytes differ",
    )
    return rows


def _graph(rows: list[Any]) -> dict[str, Any]:
    nodes = []
    for row in rows:
        site = row.address - BASE
        successors, flow = [site + len(row.bytes)], "fallthrough"
        if row.group(cs.CS_GRP_JUMP):
            _require(
                site == 0x379F28 and row.id == x86.X86_INS_JE, "unreviewed jump syntax"
            )
            successors = sorted({successors[0], int(row.operands[0].imm) - BASE})
            flow = "direct_conditional_branch"
        elif row.group(cs.CS_GRP_RET):
            successors, flow = [], "return_syntax"
        elif row.group(cs.CS_GRP_INT):
            flow = "opaque_interrupt_possible_fallthrough"
        elif row.group(cs.CS_GRP_CALL):
            flow = "call_possible_fallthrough"
        _, writes = row.regs_access()
        nodes.append(
            _point(row)
            | {
                "flow_kind": flow,
                "successor_rvas": [_hex(s) for s in successors],
                "writes_registers": sorted({row.reg_name(r) for r in writes}),
            }
        )
    _require(
        len(nodes) == 20 and sum(len(n["successor_rvas"]) for n in nodes) == 20,
        "CFG size differs",
    )
    return {
        "entry_rva": _hex(ENTRY),
        "nodes": nodes,
        "node_count": len(nodes),
        "edge_count": sum(len(n["successor_rvas"]) for n in nodes),
    }


def _witness(image: Any, rva: int, size: int) -> dict[str, Any]:
    offset = image.rva_span_to_file_offset(rva, size)
    _require(offset is not None, "required raw-backed span missing")
    return {
        "rva": _hex(rva),
        "file_offset": _hex(offset),
        "size": size,
        "sha256": hashlib.sha256(image.data[offset : offset + size]).hexdigest(),
    }


def _import_binding(image: Any, slot: int) -> dict[str, Any]:
    imports = [r for r in image.imports() if r["iat_rva"] == _hex(slot)]
    _require(len(imports) == 1, "required import missing or duplicated")
    item = imports[0]
    expected = {
        0x3D60F0: ("GetCurrentProcess", 448),
        0x3D6014: ("TerminateProcess", 1216),
    }
    _require(
        (item["name"], item["hint"]) == expected[slot]
        and item["library"] == "KERNEL32.dll"
        and item["ordinal"] is None,
        "required import syntax differs",
    )
    descriptor = _witness(image, 0x48ED30, 20)
    offset = int(descriptor["file_offset"], 16)
    original, timestamp, forwarder, name, first = struct.unpack_from(
        "<IIIII", image.data, offset
    )
    _require(
        (original, timestamp, forwarder, name, first)
        == (0x48ED80, 0, 0, 0x4905FE, 0x3D6000),
        "import descriptor differs",
    )
    ilt = _witness(image, original + slot - first, 4)
    iat = _witness(image, slot, 4)
    at = int(ilt["file_offset"], 16)
    name_rva = struct.unpack_from("<I", image.data, at)[0]
    _require(
        not name_rva & 0x80000000
        and image.data[at : at + 4]
        == image.data[int(iat["file_offset"], 16) : int(iat["file_offset"], 16) + 4],
        "ILT/IAT binding differs",
    )
    by_name = _witness(image, name_rva, len(item["name"].encode("ascii")) + 3)
    at = int(by_name["file_offset"], 16)
    _require(
        struct.unpack_from("<H", image.data, at)[0] == item["hint"]
        and image.data[at + 2 : at + by_name["size"]]
        == item["name"].encode("ascii") + b"\0",
        "raw import name differs",
    )
    return {
        "metadata": item,
        "descriptor": descriptor,
        "ilt_entry": ilt,
        "iat_slot": iat,
        "import_by_name": by_name,
        "import_name_metadata_only": True,
    }


def _relocations(image: Any) -> dict[str, Any]:
    rva, size = image.data_directories[5]
    _require((rva, size) == (0x539000, 0x35618), "relocation directory differs")
    directory = _witness(image, rva, size)
    cursor, end = (
        int(directory["file_offset"], 16),
        int(directory["file_offset"], 16) + size,
    )
    sites = []
    while cursor < end:
        page, length = struct.unpack_from("<II", image.data, cursor)
        _require(
            length >= 8 and length % 2 == 0 and cursor + length <= end,
            "malformed relocation block",
        )
        for offset in range(cursor + 8, cursor + length, 2):
            item = struct.unpack_from("<H", image.data, offset)[0]
            site, kind = page + (item & 0xFFF), item >> 12
            if kind and ENTRY <= site < ENTRY + SIZE:
                _require(kind == 3, "unreviewed relocation type")
                operand = _witness(image, site, 4)
                value = struct.unpack_from(
                    "<I", image.data, int(operand["file_offset"], 16)
                )[0]
                sites.append(
                    {
                        "site_rva": _hex(site),
                        "type": "HIGHLOW",
                        "entry_file_offset": _hex(offset),
                        "entry_sha256": hashlib.sha256(
                            image.data[offset : offset + 2]
                        ).hexdigest(),
                        "operand": operand,
                        "value_va": _hex(value),
                    }
                )
        cursor += length
    _require(
        [(int(r["site_rva"], 16), int(r["value_va"], 16)) for r in sites]
        == [(0x379F45, 0x7D60F0), (0x379F4C, 0x7D6014)],
        "relocation frontier differs",
    )
    return {"directory": directory, "sites": sites}


def _controls(rows: list[Any], image: Any, facts: Mapping[str, Any]) -> dict[str, Any]:
    direct, imports, interrupts, literals = [], [], [], []
    functions = _atlas_functions(facts)
    for row in rows:
        site = row.address - BASE
        _require(not any(row.prefix), "unreviewed prefixed syntax")
        if row.group(cs.CS_GRP_CALL):
            operand = row.operands[0]
            if operand.type == x86.X86_OP_IMM:
                target = int(operand.imm) - BASE
                direct.append(
                    {
                        "instruction": _point(row),
                        "target_entry_rva": _hex(target),
                        "target_atlas_record_sha256": atlas_record_sha256(
                            functions[target]
                        ),
                        "declared_edge": _edge(facts, site, ENTRY, target),
                        "behavior_opaque": True,
                    }
                )
            else:
                _require(
                    operand.type == x86.X86_OP_MEM
                    and operand.mem.base
                    == operand.mem.index
                    == operand.mem.segment
                    == 0,
                    "unreviewed indirect control",
                )
                imports.append(
                    {
                        "instruction": _point(row),
                        "operand_index": 0,
                        "slot_rva": _hex(operand.mem.disp - BASE),
                        "binding": _import_binding(image, operand.mem.disp - BASE),
                        "behavior_opaque": True,
                    }
                )
        elif row.group(cs.CS_GRP_INT):
            _require(
                site == 0x379F2D
                and row.id == x86.X86_INS_INT
                and row.operands[0].imm == 0x29,
                "unreviewed interrupt",
            )
            interrupts.append(
                {
                    "instruction": _point(row),
                    "vector": 0x29,
                    "runtime_behavior_opaque": True,
                }
            )
        elif not row.group(cs.CS_GRP_JUMP):
            for index, operand in enumerate(row.operands):
                _require(
                    operand.type != x86.X86_OP_MEM, "unreviewed data memory operand"
                )
                if operand.type == x86.X86_OP_IMM:
                    literals.append(
                        {
                            "instruction": _point(row),
                            "operand_index": index,
                            "value_u32": _hex(int(operand.imm) & 0xFFFFFFFF),
                            "meaning_opaque": True,
                        }
                    )
    _require(
        [
            (int(r["instruction"]["rva"], 16), int(r["target_entry_rva"], 16))
            for r in direct
        ]
        == [(0x379F21, 0x39CB92), (0x379F3A, 0x379D28)],
        "outgoing native partition differs",
    )
    _require(
        {
            int(r["instruction_rva"], 16)
            for r in facts["ghidra_declared_direct_calls"]
            if int(r["source_entry_rva"], 16) == ENTRY
        }
        == {0x379F21, 0x379F3A},
        "atlas outgoing partition differs",
    )
    _require(
        len(imports) == 2 and len(interrupts) == 1 and len(literals) == 6,
        "control/literal counts differ",
    )
    return {
        "direct_calls": direct,
        "import_calls": imports,
        "interrupts": interrupts,
        "ordinary_immediates": literals,
        "register_calls": [{"register": r, "call_rvas": []} for r in REGISTERS],
        "partitions_complete_for_pinned_body": True,
    }


def _scan(data: bytes, image: Any, facts: Mapping[str, Any]) -> dict[str, Any]:
    decoder, _ = _decoder()
    decoder.detail = True
    refs, counts = [], Counter(functions=0, ranges=0, bytes=0, instructions=0)
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
                        value = int(operand.imm) & 0xFFFFFFFF
                    elif (
                        operand.type == x86.X86_OP_MEM
                        and operand.mem.base
                        == operand.mem.index
                        == operand.mem.segment
                        == 0
                    ):
                        value = int(operand.mem.disp) & 0xFFFFFFFF
                    else:
                        continue
                    if value != BASE + ENTRY:
                        continue
                    _require(
                        index == 0
                        and row.id == x86.X86_INS_CALL
                        and len(row.bytes) == 5
                        and row.bytes[0] == 0xE8,
                        "unreviewed incoming reference syntax",
                    )
                    refs.append(
                        {
                            "instruction": _point(row),
                            "owner_entry_rva": _hex(owner),
                            "owner_atlas_record_sha256": atlas_record_sha256(function),
                            "target_rva": _hex(ENTRY),
                            "operand_class": "immediate",
                            "operand_index": index,
                            "declared_edge": _edge(
                                facts, row.address - BASE, owner, ENTRY
                            ),
                        }
                    )
    _require(dict(counts) == SCOPE, "whole-atlas decode scope differs")
    return {
        "scope": dict(counts),
        "references": refs,
        "reference_count": len(refs),
        "owner_count": len({r["owner_entry_rva"] for r in refs}),
        "references_canonical_sha256": _canonical_sha256(refs),
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
    _require(
        digest == EXE_SHA256 and image.image_base == BASE, "exact executable differs"
    )
    functions = _atlas_functions(facts)
    _require(
        atlas_record_sha256(functions[ENTRY]) == ATLAS_SHA256
        and functions[ENTRY]["body_size"] == SIZE
        and functions[ENTRY]["body_sha256"] == BODY_SHA256,
        "new target atlas differs",
    )
    joins = _joins(sources)
    # Recheck the source caller and both reused body identities against the PE.
    parent_rows = {
        r.address - BASE: r for r in _decode_body(data, image, facts, 0x379E77)
    }
    for join in joins:
        instruction = join["parent_edge"]["instruction"]
        row = parent_rows[int(instruction["rva"], 16)]
        _require(
            _point(row) == instruction
            and row.id == x86.X86_INS_CALL
            and row.operands[0].type == x86.X86_OP_IMM
            and row.operands[0].imm - BASE
            == int(join["parent_edge"]["target_entry_rva"], 16),
            "exact parent edge differs",
        )
    for entry in (0x38EDB6, 0x3574CA):
        _decode_body(data, image, facts, entry)
    rows = _decode_body(data, image, facts, ENTRY)
    _require(len(rows) == 20, "instruction count differs")
    graph, controls, scan = (
        _graph(rows),
        _controls(rows, image, facts),
        _scan(data, image, facts),
    )
    replay, replay_image, replay_digest = _load_executable(executable)
    _require(
        replay == data and replay_digest == digest and replay_image.image_base == BASE,
        "executable changed during rebuild",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(facts["identity"]),
        "source_receipts": identities,
        "direct_callee_joins": joins,
        "function_body": {
            "entry_rva": _hex(ENTRY),
            "body_size": SIZE,
            "body_sha256": BODY_SHA256,
            "atlas_record_sha256": ATLAS_SHA256,
            "points": [_point(r) for r in rows],
            "analysis_metadata": {
                "name": functions[ENTRY]["name"],
                "name_source": functions[ENTRY]["name_source"],
                "metadata_only": True,
            },
        },
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
        },
        "control_flow_graph": graph,
        "native_controls": controls,
        "base_relocations": _relocations(image),
        "whole_atlas_reference_scan": scan,
        "method": {
            "scope": "All three immediate direct callees of the pinned second-child receipt; two prior body receipts are joined without duplicating their evidence.",
            "structural_validation": "Hash-pinned normalized receipt consistency plus source, edge, graph and count joins; no executable evidence is inferred from consistency alone.",
            "exact_validation": "Exact PE and direct-call census verification, caller and reused body byte checks, new body decoding, raw import and relocation witnesses, and a complete atlas operand scan. Prior receipts are canonical-pinned; their entire original analyses are not rerun.",
            "not_claimed": [
                "CRT identity, ABI, ownership, source equivalence, runtime reachability, effects, or callee behavior",
                "Interrupt and call fallthrough edges are syntactic possibilities, not evidence of runtime continuation, termination or normal return",
                "Computed, indirect, data-only, un-atlased, generated or Lua-side entry references",
                "Recursive closure of the assertion helper graph or any accounting-level promotion",
            ],
        },
        "summary": {
            "parent_direct_edges": 3,
            "reused_target_bodies": 2,
            "new_target_bodies": 1,
            "new_body_bytes": SIZE,
            "instructions": 20,
            "cfg_nodes": 20,
            "cfg_edges": 20,
            "outgoing_native_edges": 2,
            "import_controls": 2,
            "interrupt_controls": 1,
            "ordinary_literals": 6,
            "highlow_sites": 2,
            "incoming_references": scan["reference_count"],
            "incoming_owners": scan["owner_count"],
        },
    }


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        identities = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256,
            "sealed frontier receipt differs",
        )
        _require(
            evidence["schema_version"] == SCHEMA_VERSION
            and evidence["analysis_kind"] == ANALYSIS_KIND
            and evidence["source_receipts"] == identities
            and evidence["direct_callee_joins"] == _joins(sources),
            "frontier source joins differ",
        )
        nodes = evidence["control_flow_graph"]["nodes"]
        sites = {n["rva"] for n in nodes}
        _require(
            len(nodes) == len(sites) == 20
            and all(s in sites for n in nodes for s in n["successor_rvas"]),
            "CFG node closure differs",
        )
        _require(
            sum(n["size"] for n in nodes) == SIZE
            and sum(len(n["successor_rvas"]) for n in nodes) == 20,
            "CFG extents/counts differ",
        )
        refs = evidence["whole_atlas_reference_scan"]["references"]
        _require(
            sum(
                r["instruction"]["rva"] == "0x00379eec"
                and r["owner_entry_rva"] == "0x00379e77"
                for r in refs
            )
            == 1,
            "new parent reference missing",
        )
        _require(
            evidence["whole_atlas_reference_scan"]["references_canonical_sha256"]
            == _canonical_sha256(refs),
            "reference hash differs",
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


def build_frontier(
    executable: Path, sources: Mapping[str, Any], *, inventory: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(executable, sources, inventory)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_frontier(
    executable: Path,
    evidence: Mapping[str, Any],
    sources: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        rebuilt = build_frontier(executable, sources, inventory=inventory)
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


def encode_frontier(value: Mapping[str, Any]) -> str:
    def run() -> str:
        _require(isinstance(value, Mapping), "encoded receipt is not a mapping")
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
