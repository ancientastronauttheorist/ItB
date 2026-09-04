"""Normalized exact boundaries for two relationship-selected descendants.

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
ANALYSIS_KIND = "pe_native_assertion_helper_descendant_pair"
SEALED_SHA256 = "47421700f38e3dbf3f5283bf89d3beb5d6421d32eaf05938ad58989908f93d0b"
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
BASE = 0x400000
TARGETS = {
    0x379D28: {
        "size": 315,
        "body_sha256": "636d0da8095430211856a90a00a74b292186f6931c9043a1d9fd26b44351c95a",
        "atlas_sha256": "f965c1e4051ac1d32b50a9d5d1cbc494aa0071606fad8bf2b34cdcc58f27bb9b",
        "instructions": 78,
        "cfg_edges": 81,
    },
    0x39CB92: {
        "size": 6,
        "body_sha256": "247575b8ff280345c05bf6c58c3620b861c076bb718663401c6c729f4542cee7",
        "atlas_sha256": "495f4729075f0f38c369905e1cd00f3f3d9b1eb5247caf5ce112fec3e6066f4e",
        "instructions": 1,
        "cfg_edges": 0,
    },
}
SOURCE_PINS = {
    "frontier": (
        "pe_native_assertion_helper_second_child_callee_frontier",
        "39a712704c58f0789580ebac647ce13ae23681a1df12f0dc93d549159e37ddeb",
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
IMPORTS = {
    0x3D6008: ("IsDebuggerPresent", 768),
    0x3D6010: ("IsProcessorFeaturePresent", 772),
    0x3D6018: ("UnhandledExceptionFilter", 1235),
    0x3D60E4: ("SetUnhandledExceptionFilter", 1189),
}
REGISTERS = ("EAX", "ECX", "EDX", "EBX", "ESP", "EBP", "ESI", "EDI")


class PairError(RuntimeError):
    """Exact identity, decoded partition, or a receipt join differs."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PairError(message)


def _normalize(operation: Any) -> Any:
    try:
        return operation()
    except PairError:
        raise
    except Exception as exc:
        raise PairError(str(exc)) from exc


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
    for name in ("frontier", "direct_calls"):
        _require(
            _canonical_bytes(sources[name]["build_identity"])
            == _canonical_bytes(identity),
            "source build differs",
        )
    return result


def _parents(sources: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = sources["frontier"]
    _require(
        source["function_body"]["entry_rva"] == "0x00379f1f", "source caller differs"
    )
    edges = source["native_controls"]["direct_calls"]
    _require(len(edges) == 2, "parent direct partition differs")
    expected = [(0x379F21, 0x39CB92), (0x379F3A, 0x379D28)]
    result = []
    for index, (row, (site, target)) in enumerate(zip(edges, expected)):
        _require(
            int(row["instruction"]["rva"], 16) == site
            and int(row["target_entry_rva"], 16) == target
            and row["target_atlas_record_sha256"] == TARGETS[target]["atlas_sha256"],
            "parent target differs",
        )
        _require(
            row["declared_edge"]
            == _edge(sources["program_facts"], site, 0x379F1F, target),
            "parent declared edge differs",
        )
        result.append(
            {
                "source_path": ["native_controls", "direct_calls", index],
                "source_canonical_sha256": SOURCE_PINS["frontier"][1],
                "edge": dict(row),
            }
        )
    return result


def _graph(rows: list[Any], entry: int) -> dict[str, Any]:
    nodes = []
    for row in rows:
        site = row.address - BASE
        successors, flow = [site + len(row.bytes)], "fallthrough"
        if row.group(cs.CS_GRP_JUMP):
            if row.operands[0].type == x86.X86_OP_IMM:
                _require(
                    row.id in (x86.X86_INS_JE, x86.X86_INS_JNE), "unreviewed branch"
                )
                successors = sorted({successors[0], int(row.operands[0].imm) - BASE})
                flow = "direct_conditional_branch"
            else:
                _require(
                    entry == 0x39CB92 and row.id == x86.X86_INS_JMP,
                    "unreviewed indirect jump",
                )
                successors, flow = [], "opaque_import_jump"
        elif row.group(cs.CS_GRP_CALL):
            flow = "call_possible_fallthrough"
        elif row.group(cs.CS_GRP_RET):
            successors, flow = [], "return_syntax"
        _require(not row.group(cs.CS_GRP_INT), "unreviewed interrupt")
        reads, writes = row.regs_access()
        _require(all(p in (0, 0x66) for p in row.prefix), "unreviewed prefix")
        nodes.append(
            _point(row)
            | {
                "flow_kind": flow,
                "successor_rvas": [_hex(s) for s in successors],
                "decoder_reads_registers": sorted({row.reg_name(r) for r in reads}),
                "decoder_writes_registers": sorted({row.reg_name(r) for r in writes}),
                "operand_size_override": 0x66 in row.prefix,
            }
        )
    count = sum(len(n["successor_rvas"]) for n in nodes)
    _require(
        len(nodes) == TARGETS[entry]["instructions"]
        and count == TARGETS[entry]["cfg_edges"],
        "CFG counts differ",
    )
    sites = {n["rva"] for n in nodes}
    _require(
        all(s in sites for n in nodes for s in n["successor_rvas"]), "CFG escapes body"
    )
    return {
        "entry_rva": _hex(entry),
        "nodes": nodes,
        "node_count": len(nodes),
        "edge_count": count,
    }


def _import_binding(image: Any, slot: int) -> dict[str, Any]:
    matches = [r for r in image.imports() if r["iat_rva"] == _hex(slot)]
    _require(slot in IMPORTS and len(matches) == 1, "unreviewed import slot")
    item = matches[0]
    _require(
        (item["name"], item["hint"]) == IMPORTS[slot]
        and item["library"] == "KERNEL32.dll"
        and item["ordinal"] is None,
        "import metadata differs",
    )
    descriptor = _witness(image, 0x48ED30, 20)
    at = int(descriptor["file_offset"], 16)
    original, timestamp, forwarder, name, first = struct.unpack_from(
        "<IIIII", image.data, at
    )
    _require(
        (original, timestamp, forwarder, name, first)
        == (0x48ED80, 0, 0, 0x4905FE, 0x3D6000),
        "import descriptor differs",
    )
    ilt, iat = _witness(image, original + slot - first, 4), _witness(image, slot, 4)
    at = int(ilt["file_offset"], 16)
    target = struct.unpack_from("<I", image.data, at)[0]
    _require(
        not target & 0x80000000
        and image.data[at : at + 4]
        == image.data[int(iat["file_offset"], 16) : int(iat["file_offset"], 16) + 4],
        "ILT/IAT binding differs",
    )
    by_name = _witness(image, target, len(item["name"].encode("ascii")) + 3)
    at = int(by_name["file_offset"], 16)
    _require(
        struct.unpack_from("<H", image.data, at)[0] == item["hint"]
        and image.data[at + 2 : at + by_name["size"]]
        == item["name"].encode("ascii") + b"\0",
        "raw name differs",
    )
    return {
        "metadata": item,
        "descriptor": descriptor,
        "ilt_entry": ilt,
        "iat_slot": iat,
        "import_by_name": by_name,
        "name_metadata_only": True,
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
                raise PairError("unsupported operand class")
            result.append(value)
    return result


def _controls(
    rows: list[Any], entry: int, image: Any, facts: Mapping[str, Any]
) -> dict[str, Any]:
    direct, imports = [], []
    functions = _atlas_functions(facts)
    for row in rows:
        is_call = row.group(cs.CS_GRP_CALL)
        is_jump = row.group(cs.CS_GRP_JUMP)
        if not (is_call or is_jump):
            continue
        operand = row.operands[0]
        if operand.type == x86.X86_OP_IMM:
            if not is_call:
                continue
            target = int(operand.imm) - BASE
            direct.append(
                {
                    "instruction": _point(row),
                    "target_entry_rva": _hex(target),
                    "target_atlas_record_sha256": atlas_record_sha256(
                        functions[target]
                    ),
                    "declared_edge": _edge(facts, row.address - BASE, entry, target),
                    "behavior_opaque": True,
                }
            )
        else:
            _require(
                operand.type == x86.X86_OP_MEM
                and operand.mem.base == operand.mem.index == operand.mem.segment == 0,
                "unreviewed indirect control",
            )
            slot = operand.mem.disp - BASE
            imports.append(
                {
                    "instruction": _point(row),
                    "control_kind": "call" if is_call else "jump",
                    "slot_rva": _hex(slot),
                    "binding": _import_binding(image, slot),
                    "behavior_opaque": True,
                }
            )
    expected = (
        []
        if entry == 0x39CB92
        else [
            (0x379D47, 0x3586B6),
            (0x379D58, 0x370960),
            (0x379D6B, 0x370960),
            (0x379E4E, 0x3586B6),
            (0x379E5A, 0x3574CA),
        ]
    )
    _require(
        [
            (int(r["instruction"]["rva"], 16), int(r["target_entry_rva"], 16))
            for r in direct
        ]
        == expected,
        "direct native partition differs",
    )
    _require(
        {
            int(r["instruction_rva"], 16)
            for r in facts["ghidra_declared_direct_calls"]
            if int(r["source_entry_rva"], 16) == entry
        }
        == {s for s, _ in expected},
        "declared outgoing partition differs",
    )
    _require(
        len(imports) == (1 if entry == 0x39CB92 else 3), "import control count differs"
    )
    return {
        "direct_calls": direct,
        "import_controls": imports,
        "register_calls": [{"register": r, "call_rvas": []} for r in REGISTERS],
        "interrupts": [],
        "partitions_complete_for_pinned_bodies": True,
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
    _require(len(sites) == 5, "relocation frontier count differs")
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
        "parent_edges": 2,
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
    caller = {r.address - BASE: r for r in _decode_body(data, image, facts, 0x379F1F)}
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
            "scope": "Both direct native callees of the pinned 51-byte assertion descendant; all explicit decoded operands and body control partitions are retained.",
            "structural_validation": "Hash-pinned normalized receipt consistency and recomputed source, parent, graph, operand and count joins; not independent binary evidence.",
            "exact_validation": "Exact PE and direct-call census verification, caller edge and target body byte checks, decoded bodies, raw import and relocation witnesses, and a complete all-operand atlas entry-reference scan. The source frontier is canonical-pinned without rerunning its entire original analysis.",
            "not_claimed": [
                "CRT identity, ABI, ownership, context-record identity, exception or reporting semantics, runtime behavior, or accounting-level promotion",
                "Decoder memory expressions, register accesses and operand-size overrides are syntax; LEA does not establish a memory read, nor do segment-register operands establish runtime state",
                "Call fallthrough is a syntactic possibility, and the indirect import jump is a transfer boundary; neither establishes continuation, termination or normal return",
                "Global IAT consumer closure, computed, indirect, data-only, un-atlased, generated or Lua-side target-entry references",
                "Recursive closure of native descendants or either imported implementation",
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
            _canonical_sha256(evidence) == SEALED_SHA256, "sealed pair receipt differs"
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
            edge = parent["edge"]
            _require(
                sum(
                    r["instruction"] == edge["instruction"]
                    and r["target_entry_rva"] == edge["target_entry_rva"]
                    and r["owner_entry_rva"] == "0x00379f1f"
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


def build_pair(
    executable: Path, sources: Mapping[str, Any], *, inventory: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(executable, sources, inventory)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_pair(
    executable: Path,
    evidence: Mapping[str, Any],
    sources: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        rebuilt = build_pair(executable, sources, inventory=inventory)
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


def encode_pair(value: Mapping[str, Any]) -> str:
    def run() -> str:
        _require(isinstance(value, Mapping), "encoded pair is not a mapping")
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
