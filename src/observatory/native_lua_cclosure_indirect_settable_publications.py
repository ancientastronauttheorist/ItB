"""Exact indirect-``lua_settable`` publications from residual Lua closures.

This deliberately narrow census consumes only the still-unmatched frontier of
the exact direct-table-setter publication census.  It recognizes one x86
Windows cdecl pattern: a caller-local ``mov esi,[lua_settable IAT]`` stage and
later contiguous closure-call cleanup, table-index, state, and ``call esi``
tails for which no decoded instruction writes ESI after the stage.
"""

from __future__ import annotations

import json
import struct
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_callbacks import (
    ANALYSIS_KIND as CALLBACK_ANALYSIS_KIND,
    NativeLuaCClosureError,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _canonical_bytes,
    _canonical_sha256,
    _containing_range,
    _decode_range,
    _exact_keys,
    _instruction_fact,
    _instruction_sha256,
    _instruction_structure,
    _mapping,
    _require_register_push,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_cclosure_table_setter_publications import (
    ANALYSIS_KIND as DIRECT_SETTER_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as DIRECT_SETTER_STRUCTURE_VERIFICATION_KIND,
    NativeLuaCClosureTableSetterPublicationError,
    validate_native_lua_cclosure_table_setter_publication_census,
    validate_native_lua_cclosure_table_setter_publication_structure,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_CALL_ANALYSIS_KIND,
    SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = (
    "pe_native_lua_immediate_cclosure_indirect_settable_publication_census"
)
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
PUBLICATION_FORM = (
    "x86_staged_esi_cleanup_push_table_index_same_state_call_esi"
)
UNMATCHED_RESOLUTION = "no_exact_staged_indirect_settable_publication"
LUA_LIBRARY = "lua5.1.dll"
SETTER_IMPORT = "lua_settable"
ABI_NONVOLATILE_STATE_PUSH_OPCODES = frozenset({0x53, 0x55, 0x56, 0x57})
ABI_NONVOLATILE_STATE_PUSH_SHA256 = frozenset(
    _instruction_sha256(bytes([opcode]))
    for opcode in ABI_NONVOLATILE_STATE_PUSH_OPCODES
)
INVALID_TABLE_INDICES = frozenset({-1, 0})
CALL_ESI_BYTES = b"\xff\xd6"
CALL_ESI_SHA256 = _instruction_sha256(CALL_ESI_BYTES)
MOV_ESI_ABSOLUTE_BYTES_PREFIX = b"\x8b\x35"
ESI_PRESERVATION_CLASSIFIER = (
    "capstone_5.0.1_x86_regs_access_with_windows_cdecl_nonvolatile_esi_premise"
)

_METHOD = {
    "direct_table_setter_prerequisite_exactly_verified": True,
    "accepted_stage": (
        "Within the exact caller atlas range, the first residual callback "
        "call is followed immediately by the unique exact x86 mov esi,[abs] "
        "whose absolute address is image_base plus the uniquely named "
        "lua5.1.dll lua_settable IAT RVA."
    ),
    "accepted_publication": (
        "After the callback call (and, only for the first callback, after the "
        "contiguous setter stage), require exact contiguous add esp,imm8 with "
        "a positive <=0x7f multiple-of-four cleanup; signed immediate table "
        "index PUSH excluding definitely invalid zero and -1; the same "
        "ABI-nonvolatile Lua-state register PUSH; and exact FF D6 call esi."
    ),
    "esi_preservation": (
        "A deterministic CFG is built over the fully decoded caller range. "
        "The stage must be caller-entry reachable and dominate every setter "
        "call plus every later callback call. The bootstrap callback immediately "
        "precedes the stage and is the sole callback dominance exception. Every "
        "node on any reachable stage-to-setter path other than the stage must "
        "have writes_esi=false according to Capstone regs_access. Calls are "
        "accepted under the explicit x86 Windows cdecl ABI premise that ESI is "
        "callee-preserved."
    ),
    "cfg_semantics": (
        "CFG edges use ordinary fallthrough, immediate conditional and "
        "unconditional branch targets, returning-call fallthrough, and no "
        "fallthrough for returns, interrupts, halts, undefined instructions, or "
        "indirect jumps. Unsupported or unresolved transfers reject the range."
    ),
    "entry_assumption": (
        "The exact caller atlas entry is the sole modeled external entry. Atlas "
        "function entries and Ghidra-declared direct-call targets into every "
        "stage-dominated proof region are rejected. Complete exclusion of "
        "unmodeled indirect, exception, or externally fabricated entries is an "
        "explicit atlas-entry assumption rather than a binary-only proof."
    ),
    "structural_boundary": (
        "PE-free validation reconstructs the finite stage, cleanup, immediate "
        "PUSH, state PUSH, and call-ESI hashes; validates the normalized stored "
        "CFG; and recomputes reachability, dominance, path sets, entry audits, "
        "and the ordered lexical witness. It cannot derive branch semantics or "
        "writes_esi classifications from instruction hashes; exact PE rebuild "
        "is required for those byte-to-decoder claims."
    ),
    "partition": (
        "Every site in the direct-table-setter still-unmatched frontier occurs "
        "exactly once as a retained indirect publication or still-unmatched site."
    ),
    "publication_boundary": (
        "The artifact publishes normalized RVAs, fixed-size instruction "
        "hashes, decoded ESI-write classifications, prerequisite identities, "
        "callback upvalue metadata, and deterministic aggregates. It omits "
        "instruction bytes, disassembly, decompiler output, and local paths."
    ),
    "not_claimed": [
        "binary-only proof that arbitrary callees obey the x86 Windows cdecl ESI-preservation rule",
        "complete exclusion of indirect, exception, callback, or external entries absent from atlas functions and declared direct-call facts",
        "runtime reachability, execution, frequency, persistence, or lifetime",
        "table identity, ownership, global export, Lua-visible name, or later mutation",
        "publication through another register, setter API, or non-contiguous tail grammar",
        "function purpose, source-level reconstruction, or behavioral equivalence",
    ],
}


class NativeLuaCClosureIndirectSettablePublicationError(RuntimeError):
    """Raised for invalid or stale indirect-settable publication evidence."""


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _source_identity(source: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(source, "direct_table_setter_publications")
    if source.get("analysis_kind") != DIRECT_SETTER_ANALYSIS_KIND:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "direct table-setter prerequisite has the wrong kind"
        )
    summary = _mapping(source.get("summary"), "direct_table_setter.summary")
    return {
        "analysis_kind": DIRECT_SETTER_ANALYSIS_KIND,
        "canonical_sha256": _canonical_sha256(source),
        "still_unmatched_resolved_callback_sites": summary.get(
            "still_unmatched_resolved_callback_sites"
        ),
    }


def _lua_settable_import(direct_calls: Mapping[str, Any]) -> Mapping[str, Any]:
    matches = []
    for index, raw in enumerate(
        _array(direct_calls.get("lua_imports"), "direct_calls.lua_imports")
    ):
        item = _mapping(raw, f"direct_calls.lua_imports[{index}]")
        if item.get("name") == SETTER_IMPORT:
            matches.append(item)
    if len(matches) != 1 or matches[0].get("library") != LUA_LIBRARY:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "direct-call census must contain one lua5.1.dll lua_settable import"
        )
    _rva(matches[0].get("iat_rva"), "lua_settable import iat_rva")
    return matches[0]


def _site_key(site: Mapping[str, Any], label: str) -> int:
    return _rva(
        site.get("callback_call_rva", site.get("call_rva")),
        f"{label}.callback_call_rva",
    )


def _frontier(
    direct_setters: Mapping[str, Any], callback_census: Mapping[str, Any]
) -> tuple[dict[int, Mapping[str, Any]], dict[int, Mapping[str, Any]]]:
    resolved: dict[int, Mapping[str, Any]] = {}
    for index, raw in enumerate(
        _array(callback_census.get("resolved_sites"), "callback_census.resolved_sites")
    ):
        site = _mapping(raw, f"callback_census.resolved_sites[{index}]")
        call = _rva(site.get("call_rva"), f"resolved_sites[{index}].call_rva")
        if call in resolved:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                "resolved callback call RVAs must be unique"
            )
        resolved[call] = site
    frontier: dict[int, Mapping[str, Any]] = {}
    previous = -1
    for index, raw in enumerate(
        _array(
            direct_setters.get("still_unmatched_resolved_sites"),
            "direct_table_setter.still_unmatched_resolved_sites",
        )
    ):
        label = f"direct_table_setter.still_unmatched_resolved_sites[{index}]"
        site = _mapping(raw, label)
        call = _site_key(site, label)
        if call <= previous or call in frontier:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                "direct table-setter residual frontier must be uniquely ordered"
            )
        previous = call
        source = resolved.get(call)
        if source is None:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                "residual frontier does not join callback census"
            )
        for key in (
            "caller_entry_rva",
            "caller_atlas_record_sha256",
            "callback_entry_rva",
            "callback_atlas_record_sha256",
        ):
            if site.get(key) != source.get(key):
                raise NativeLuaCClosureIndirectSettablePublicationError(
                    "residual frontier identity differs from callback census"
                )
        frontier[call] = site
    expected = _mapping(direct_setters.get("summary"), "direct_setter.summary").get(
        "still_unmatched_resolved_callback_sites"
    )
    if len(frontier) != expected:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "residual frontier count differs from prerequisite summary"
        )
    return resolved, frontier


def _unmatched(site: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "caller_entry_rva": site["caller_entry_rva"],
        "caller_atlas_record_sha256": site["caller_atlas_record_sha256"],
        "callback_call_rva": site["callback_call_rva"],
        "callback_entry_rva": site["callback_entry_rva"],
        "callback_atlas_record_sha256": site["callback_atlas_record_sha256"],
        "resolution": UNMATCHED_RESOLUTION,
    }


def _decode_table_index(instruction: Any) -> int | None:
    encoded = bytes(instruction.bytes)
    if len(encoded) == 2 and encoded[0] == 0x6A:
        return struct.unpack("<b", encoded[1:])[0]
    if len(encoded) == 5 and encoded[0] == 0x68:
        return struct.unpack("<i", encoded[1:])[0]
    return None


def _cleanup_value(instruction: Any) -> int | None:
    encoded = bytes(instruction.bytes)
    if (
        len(encoded) == 3
        and encoded[:2] == b"\x83\xc4"
        and 0 < encoded[2] <= 0x7F
        and encoded[2] % 4 == 0
    ):
        return encoded[2]
    return None


def _contiguous(instructions: list[Any]) -> bool:
    return all(
        left.address + left.size == right.address
        for left, right in zip(instructions, instructions[1:])
    )


def _writes_esi(instruction: Any, esi_register: int) -> bool:
    try:
        _reads, writes = instruction.regs_access()
    except Exception as exc:  # pragma: no cover - decoder contract failure
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "Capstone could not classify register writes"
        ) from exc
    return esi_register in writes


def _witness(
    instructions: list[Any], image_base: int, esi_register: int
) -> list[dict[str, Any]]:
    return [
        {
            **_instruction_fact(instruction, image_base),
            "writes_esi": _writes_esi(instruction, esi_register),
        }
        for instruction in instructions
    ]


_TERMINAL_FLOW_KINDS = frozenset({"terminal", "indirect_jump"})
_FLOW_KINDS = frozenset(
    {
        "fallthrough",
        "call_fallthrough",
        "direct_conditional_branch",
        "direct_unconditional_branch",
        "terminal",
        "indirect_jump",
    }
)


def _build_cfg(
    instructions: list[Any],
    image_base: int,
    caller_range: tuple[int, int],
    capstone_module: Any,
    x86: Any,
) -> dict[str, Any] | None:
    """Build one exact normalized instruction CFG, or reject unsupported input."""
    if not instructions or instructions[0].address - image_base != caller_range[0]:
        return None
    if not _contiguous(instructions):
        return None
    if instructions[-1].address + instructions[-1].size != (
        image_base + caller_range[0] + caller_range[1]
    ):
        return None
    by_rva = {
        instruction.address - image_base: instruction for instruction in instructions
    }
    terminal_ids = {
        getattr(x86, name)
        for name in (
            "X86_INS_HLT",
            "X86_INS_INT",
            "X86_INS_INT1",
            "X86_INS_INT3",
            "X86_INS_INTO",
            "X86_INS_UD2",
        )
        if hasattr(x86, name)
    }
    unconditional_ids = {
        getattr(x86, name)
        for name in ("X86_INS_JMP", "X86_INS_LJMP")
        if hasattr(x86, name)
    }
    nodes: list[dict[str, Any]] = []
    for instruction in instructions:
        rva = instruction.address - image_base
        fallthrough = rva + instruction.size
        has_fallthrough = fallthrough in by_rva
        successors: list[int]
        if instruction.group(capstone_module.CS_GRP_JUMP):
            operands = list(instruction.operands)
            if len(operands) != 1:
                return None
            operand = operands[0]
            if operand.type != x86.X86_OP_IMM:
                flow_kind = "indirect_jump"
                successors = []
            else:
                target = int(operand.imm) - image_base
                if target not in by_rva:
                    return None
                if instruction.id in unconditional_ids:
                    flow_kind = "direct_unconditional_branch"
                    successors = [target]
                else:
                    if not has_fallthrough:
                        return None
                    flow_kind = "direct_conditional_branch"
                    successors = [target, fallthrough]
        elif instruction.group(capstone_module.CS_GRP_CALL):
            if not has_fallthrough:
                return None
            flow_kind = "call_fallthrough"
            successors = [fallthrough]
        elif (
            instruction.group(capstone_module.CS_GRP_RET)
            or instruction.group(capstone_module.CS_GRP_IRET)
            or instruction.id in terminal_ids
        ):
            flow_kind = "terminal"
            successors = []
        elif has_fallthrough:
            flow_kind = "fallthrough"
            successors = [fallthrough]
        else:
            return None
        nodes.append(
            {
                **_instruction_fact(instruction, image_base),
                "writes_esi": _writes_esi(instruction, x86.X86_REG_ESI),
                "flow_kind": flow_kind,
                "successor_rvas": [_hex(value) for value in sorted(set(successors))],
            }
        )
    return {
        "caller_entry_rva": _hex(caller_range[0]),
        "range_start_rva": _hex(caller_range[0]),
        "range_size": caller_range[1],
        "nodes": nodes,
        "node_count": len(nodes),
        "edge_count": sum(len(node["successor_rvas"]) for node in nodes),
    }


def _graph_maps(graph: Mapping[str, Any]) -> tuple[dict[int, Mapping[str, Any]], dict[int, set[int]]]:
    nodes: dict[int, Mapping[str, Any]] = {}
    edges: dict[int, set[int]] = {}
    for raw in graph["nodes"]:
        item = _mapping(raw, "cfg node")
        rva = _rva(item["rva"], "cfg node.rva")
        nodes[rva] = item
        edges[rva] = {
            _rva(value, "cfg node.successor_rvas")
            for value in item["successor_rvas"]
        }
    return nodes, edges


def _reachable(edges: Mapping[int, set[int]], start: int) -> set[int]:
    if start not in edges:
        return set()
    seen: set[int] = set()
    pending = [start]
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(edges[node] - seen)
    return seen


def _dominators(edges: Mapping[int, set[int]], entry: int) -> dict[int, set[int]]:
    reachable = _reachable(edges, entry)
    predecessors = {node: set() for node in reachable}
    for source in reachable:
        for target in edges[source] & reachable:
            predecessors[target].add(source)
    dominators = {
        node: ({entry} if node == entry else set(reachable)) for node in reachable
    }
    changed = True
    while changed:
        changed = False
        for node in sorted(reachable - {entry}):
            incoming = predecessors[node]
            if not incoming:
                replacement = {node}
            else:
                replacement = {node} | set.intersection(
                    *(dominators[parent] for parent in incoming)
                )
            if replacement != dominators[node]:
                dominators[node] = replacement
                changed = True
    return dominators


def _path_nodes(edges: Mapping[int, set[int]], start: int, target: int) -> set[int]:
    forward = _reachable(edges, start)
    reverse = {node: set() for node in edges}
    for source, successors in edges.items():
        for successor in successors:
            reverse[successor].add(source)
    return forward & _reachable(reverse, target)


def _entry_audit(
    facts: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
    caller_entry: int,
    dominated_region: set[int],
) -> tuple[list[str], list[dict[str, str]]]:
    atlas_entries = [
        _hex(entry)
        for entry in sorted((set(functions) & dominated_region) - {caller_entry})
    ]
    declared: list[dict[str, str]] = []
    for index, raw in enumerate(
        _array(
            facts.get("ghidra_declared_direct_calls", []),
            "program_facts.ghidra_declared_direct_calls",
        )
    ):
        item = _mapping(raw, f"ghidra_declared_direct_calls[{index}]")
        target = _rva(item.get("target_rva"), "declared target_rva")
        if target in dominated_region:
            declared.append(
                {
                    "instruction_rva": item["instruction_rva"],
                    "source_entry_rva": item["source_entry_rva"],
                    "target_rva": item["target_rva"],
                }
            )
    declared.sort(
        key=lambda item: (
            _rva(item["target_rva"], "target"),
            _rva(item["instruction_rva"], "instruction"),
        )
    )
    return atlas_entries, declared


def _aggregates(
    publications: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_builder: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_target: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_stage: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for publication in publications:
        by_builder[publication["caller_entry_rva"]].append(publication)
        by_target[publication["callback_entry_rva"]].append(publication)
        by_stage[publication["setter_stage"]["rva"]].append(publication)
    builders = [
        {
            "builder_entry_rva": entry,
            "builder_atlas_record_sha256": items[0]["caller_atlas_record_sha256"],
            "publication_site_count": len(items),
            "registered_callback_entry_rvas": sorted(
                {item["callback_entry_rva"] for item in items}
            ),
            "setter_stage_rvas": sorted({item["setter_stage"]["rva"] for item in items}),
            "table_indices": sorted({item["table_index"] for item in items}),
            "upvalue_argument_kinds": sorted(
                {item["upvalue_argument_kind"] for item in items}
            ),
        }
        for entry, items in sorted(by_builder.items(), key=lambda pair: _rva(pair[0], "builder"))
    ]
    targets = [
        {
            "callback_entry_rva": entry,
            "callback_atlas_record_sha256": items[0]["callback_atlas_record_sha256"],
            "publication_site_count": len(items),
            "builder_entry_rvas": sorted({item["caller_entry_rva"] for item in items}),
            "setter_stage_rvas": sorted({item["setter_stage"]["rva"] for item in items}),
            "table_indices": sorted({item["table_index"] for item in items}),
            "upvalue_argument_kinds": sorted(
                {item["upvalue_argument_kind"] for item in items}
            ),
        }
        for entry, items in sorted(by_target.items(), key=lambda pair: _rva(pair[0], "target"))
    ]
    stages = [
        {
            "setter_stage_rva": entry,
            "setter_stage_instruction_sha256": items[0]["setter_stage"]["sha256"],
            "caller_entry_rva": items[0]["caller_entry_rva"],
            "publication_site_count": len(items),
            "indirect_call_rvas": sorted({item["setter_call_rva"] for item in items}),
        }
        for entry, items in sorted(by_stage.items(), key=lambda pair: _rva(pair[0], "stage"))
    ]
    return builders, targets, stages


def build_native_lua_cclosure_indirect_settable_publication_census(
    executable: Path,
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact residual indirect-``lua_settable`` publication census."""
    for value, label in (
        (direct_calls, "direct_calls"),
        (callback_census, "callback_census"),
        (setfield_publications, "setfield_publications"),
        (direct_table_setter_publications, "direct_table_setter_publications"),
        (program_facts, "program_facts"),
        (inventory, "inventory"),
    ):
        _validate_json_tree(value, label)
    if (
        direct_calls.get("analysis_kind") != DIRECT_CALL_ANALYSIS_KIND
        or callback_census.get("analysis_kind") != CALLBACK_ANALYSIS_KIND
    ):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "direct-call or callback prerequisite has the wrong kind"
        )
    try:
        prerequisite = validate_native_lua_cclosure_table_setter_publication_census(
            executable,
            direct_table_setter_publications,
            direct_calls,
            callback_census,
            setfield_publications,
            program_facts,
            inventory=inventory,
        )
        data, image, executable_sha256 = _load_executable(executable)
        decoder, _ = _decoder()
        decoder.detail = True
        import capstone
        import capstone.x86_const as x86
    except (
        NativeLuaCClosureTableSetterPublicationError,
        NativeLuaCClosureError,
        NativeLuaDirectCallError,
        PEAnchorError,
    ) as exc:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"direct table-setter prerequisite failed exact verification: {exc}"
        ) from exc
    identity = _mapping(
        direct_table_setter_publications.get("build_identity"),
        "direct_table_setter.build_identity",
    )
    if (
        identity.get("executable_sha256") != executable_sha256
        or identity.get("executable_size") != len(data)
        or identity.get("architecture") != image.architecture
        or prerequisite.get("evidence_sha256")
        != _canonical_sha256(direct_table_setter_publications)
    ):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "executable or prerequisite identity changed after verification"
        )

    functions = _atlas_functions(program_facts)
    resolved, frontier = _frontier(
        direct_table_setter_publications, callback_census
    )
    setter_import = _lua_settable_import(direct_calls)
    setter_iat = _rva(setter_import.get("iat_rva"), "lua_settable.iat_rva")
    setter_va = image.image_base + setter_iat
    if setter_va > 0xFFFFFFFF:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "lua_settable IAT VA overflows x86"
        )
    stage_bytes = MOV_ESI_ABSOLUTE_BYTES_PREFIX + struct.pack("<I", setter_va)

    grouped: dict[tuple[int, int], list[int]] = defaultdict(list)
    for callback_call in frontier:
        source = resolved[callback_call]
        caller_entry = _rva(source.get("caller_entry_rva"), "caller_entry_rva")
        callback_entry = _rva(source.get("callback_entry_rva"), "callback_entry_rva")
        caller = functions.get(caller_entry)
        callback = functions.get(callback_entry)
        if caller is None or callback is None or callback.get("thunk") is not False:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                "frontier callback does not join non-thunk atlas entries"
            )
        if (
            source.get("caller_atlas_record_sha256") != atlas_record_sha256(caller)
            or source.get("callback_atlas_record_sha256")
            != atlas_record_sha256(callback)
        ):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                "frontier callback atlas hashes differ"
            )
        grouped[_containing_range(caller, callback_call)].append(callback_call)

    publications: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    control_flow_graphs: list[dict[str, Any]] = []
    for caller_range, calls in sorted(grouped.items()):
        caller_entry = _rva(
            resolved[min(calls)].get("caller_entry_rva"), "caller_entry_rva"
        )
        if caller_range[0] != caller_entry:
            for call in calls:
                unmatched.append(_unmatched(frontier[call]))
            continue
        instructions = _decode_range(
            data, image, caller_range[0], caller_range[1], decoder
        )
        graph = _build_cfg(
            instructions, image.image_base, caller_range, capstone, x86
        )
        if graph is None:
            for call in calls:
                unmatched.append(_unmatched(frontier[call]))
            continue
        graph_nodes, graph_edges = _graph_maps(graph)
        dominators = _dominators(graph_edges, caller_entry)
        by_rva = {
            instruction.address - image.image_base: index
            for index, instruction in enumerate(instructions)
        }
        first_call = min(calls)
        first_index = by_rva.get(first_call)
        stage_index = None if first_index is None else first_index + 1
        if (
            stage_index is None
            or stage_index >= len(instructions)
            or bytes(instructions[stage_index].bytes) != stage_bytes
            or instructions[stage_index].address - image.image_base != first_call + 6
            or sum(bytes(item.bytes) == stage_bytes for item in instructions) != 1
        ):
            for call in calls:
                unmatched.append(_unmatched(frontier[call]))
            continue
        stage = instructions[stage_index]
        stage_end = stage.address + stage.size
        stage_rva = stage.address - image.image_base
        dominated_region = {
            node for node, values in dominators.items() if stage_rva in values
        }
        alternate_atlas_entries, declared_direct_entries = _entry_audit(
            program_facts,
            functions,
            caller_entry,
            dominated_region,
        )
        range_publication_start = len(publications)

        for callback_call in sorted(calls):
            source = resolved[callback_call]
            call_index = by_rva.get(callback_call)
            source_state_rva = _rva(
                _mapping(source.get("state_push"), "callback.state_push").get("rva"),
                "callback.state_push.rva",
            )
            source_state_index = by_rva.get(source_state_rva)
            if call_index is None or source_state_index is None:
                raise NativeLuaCClosureIndirectSettablePublicationError(
                    "frontier callback instructions are absent from caller decode"
                )
            callback_instruction = instructions[call_index]
            source_state = instructions[source_state_index]
            if (
                _instruction_sha256(bytes(callback_instruction.bytes))
                != source.get("call_instruction_sha256")
                or _instruction_sha256(bytes(source_state.bytes))
                != _mapping(source.get("state_push"), "callback.state_push").get(
                    "sha256"
                )
            ):
                raise NativeLuaCClosureIndirectSettablePublicationError(
                    "frontier callback instruction hashes differ from executable"
                )
            tail_index = call_index + 1
            stage_between = callback_call == first_call
            if stage_between:
                tail_index += 1
            if tail_index + 4 > len(instructions):
                unmatched.append(_unmatched(frontier[callback_call]))
                continue
            cleanup, table_push, state_push, indirect_call = instructions[
                tail_index : tail_index + 4
            ]
            cleanup_bytes = _cleanup_value(cleanup)
            table_index = _decode_table_index(table_push)
            witness_instructions = [
                item
                for item in instructions
                if stage_end <= item.address < indirect_call.address
            ]
            preservation = _witness(
                witness_instructions, image.image_base, x86.X86_REG_ESI
            )
            setter_call_rva = indirect_call.address - image.image_base
            path_nodes = _path_nodes(graph_edges, stage_rva, setter_call_rva)
            stage_dominates_callback = (
                callback_call in dominators
                and stage_rva in dominators[callback_call]
            )
            stage_dominates_setter = (
                setter_call_rva in dominators
                and stage_rva in dominators[setter_call_rva]
            )
            bootstrap_exception = callback_call == first_call
            path_esi_writes = [
                node
                for node in path_nodes - {stage_rva}
                if graph_nodes[node]["writes_esi"]
            ]
            accepted = (
                cleanup_bytes is not None
                and table_index is not None
                and table_index not in INVALID_TABLE_INDICES
                and bytes(state_push.bytes) == bytes(source_state.bytes)
                and len(state_push.bytes) == 1
                and state_push.bytes[0] in ABI_NONVOLATILE_STATE_PUSH_OPCODES
                and bytes(indirect_call.bytes) == CALL_ESI_BYTES
                and _contiguous(
                    [callback_instruction]
                    + ([stage] if stage_between else [])
                    + [cleanup, table_push, state_push, indirect_call]
                )
                and witness_instructions
                and witness_instructions[0].address == stage_end
                and _contiguous(witness_instructions + [indirect_call])
                and not any(item["writes_esi"] for item in preservation)
                and stage_rva in dominators
                and callback_call in dominators
                and setter_call_rva in dominators
                and stage_dominates_setter
                and (bootstrap_exception or stage_dominates_callback)
                and setter_call_rva in path_nodes
                and not path_esi_writes
                and not alternate_atlas_entries
                and not declared_direct_entries
            )
            if not accepted:
                unmatched.append(_unmatched(frontier[callback_call]))
                continue
            publications.append(
                {
                    "publication_form": PUBLICATION_FORM,
                    "caller_entry_rva": source["caller_entry_rva"],
                    "caller_atlas_record_sha256": source[
                        "caller_atlas_record_sha256"
                    ],
                    "callback_call_rva": source["call_rva"],
                    "callback_call_instruction_sha256": source[
                        "call_instruction_sha256"
                    ],
                    "callback_entry_rva": source["callback_entry_rva"],
                    "callback_atlas_record_sha256": source[
                        "callback_atlas_record_sha256"
                    ],
                    "upvalue_argument_kind": source["upvalue_argument_kind"],
                    "literal_upvalue_count": source["literal_upvalue_count"],
                    "setter_stage": _instruction_fact(stage, image.image_base),
                    "setter_stage_iat_rva": _hex(setter_iat),
                    "stage_between_callback_and_tail": stage_between,
                    "cleanup_instruction": _instruction_fact(cleanup, image.image_base),
                    "cleanup_stack_bytes": cleanup_bytes,
                    "table_index": table_index,
                    "table_index_push": _instruction_fact(table_push, image.image_base),
                    "state_push": _instruction_fact(state_push, image.image_base),
                    "setter_call_rva": _hex(setter_call_rva),
                    "setter_call_instruction_sha256": CALL_ESI_SHA256,
                    "library": LUA_LIBRARY,
                    "setter_import_name": SETTER_IMPORT,
                    "esi_preservation_classifier": ESI_PRESERVATION_CLASSIFIER,
                    "esi_preservation_witness": preservation,
                    "esi_preservation_instruction_count": len(preservation),
                    "cfg_proof": {
                        "caller_entry_rva": _hex(caller_entry),
                        "range_start_rva": _hex(caller_range[0]),
                        "range_size": caller_range[1],
                        "stage_reachable": stage_rva in dominators,
                        "callback_reachable": callback_call in dominators,
                        "setter_call_reachable": setter_call_rva in dominators,
                        "bootstrap_callback_dominance_exception": bootstrap_exception,
                        "stage_dominates_callback": stage_dominates_callback,
                        "stage_dominates_setter_call": stage_dominates_setter,
                        "stage_to_setter_path_rvas": [
                            _hex(node) for node in sorted(path_nodes)
                        ],
                        "stage_to_setter_path_node_count": len(path_nodes),
                        "alternate_atlas_entry_rvas": alternate_atlas_entries,
                        "declared_direct_call_entries": declared_direct_entries,
                    },
                }
            )
        if len(publications) > range_publication_start:
            control_flow_graphs.append(graph)

    publications.sort(key=lambda item: _rva(item["callback_call_rva"], "publication"))
    unmatched.sort(key=lambda item: _rva(item["callback_call_rva"], "unmatched"))
    if len(publications) + len(unmatched) != len(frontier):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "residual frontier partition disagrees"
        )
    builders, targets, stages = _aggregates(publications)
    direct_atlas = _mapping(direct_calls.get("atlas"), "direct_calls.atlas")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(identity),
        "atlas": {
            "analysis_kind": direct_atlas.get("analysis_kind"),
            "canonical_sha256": direct_atlas.get("canonical_sha256"),
            "function_count": direct_atlas.get("function_count"),
        },
        "direct_call_census": {
            "analysis_kind": DIRECT_CALL_ANALYSIS_KIND,
            "canonical_sha256": _canonical_sha256(direct_calls),
        },
        "callback_census": {
            "analysis_kind": CALLBACK_ANALYSIS_KIND,
            "canonical_sha256": _canonical_sha256(callback_census),
        },
        "direct_table_setter_publication_census": _source_identity(
            direct_table_setter_publications
        ),
        "lua_settable_import": {
            "library": LUA_LIBRARY,
            "name": SETTER_IMPORT,
            "iat_rva": setter_import["iat_rva"],
        },
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "detail": True,
            "accepted_publication_form": PUBLICATION_FORM,
        },
        "control_flow_graphs": control_flow_graphs,
        "publications": publications,
        "still_unmatched_resolved_sites": unmatched,
        "builders": builders,
        "registered_targets": targets,
        "setter_stages": stages,
        "method": _METHOD,
        "summary": {
            "prior_unmatched_resolved_callback_sites": len(frontier),
            "matched_indirect_settable_publication_sites": len(publications),
            "still_unmatched_resolved_callback_sites": len(unmatched),
            "unique_registered_callback_targets": len(targets),
            "unique_registration_builders": len(builders),
            "unique_setter_stages": len(stages),
            "unique_table_indices": len({item["table_index"] for item in publications}),
            "esi_preservation_witness_instructions": sum(
                item["esi_preservation_instruction_count"] for item in publications
            ),
            "cfg_instruction_nodes": sum(
                item["node_count"] for item in control_flow_graphs
            ),
            "cfg_edges": sum(item["edge_count"] for item in control_flow_graphs),
            "stage_to_setter_path_nodes": sum(
                item["cfg_proof"]["stage_to_setter_path_node_count"]
                for item in publications
            ),
            "schema_violations": 0,
        },
    }
    _assert_publication_safe(result)
    return result


def validate_native_lua_cclosure_indirect_settable_publication_census(
    executable: Path,
    evidence: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and canonical-byte-compare one indirect-settable census."""
    _validate_json_tree(evidence, "evidence")
    rebuilt = build_native_lua_cclosure_indirect_settable_publication_census(
        executable,
        direct_calls,
        callback_census,
        setfield_publications,
        direct_table_setter_publications,
        program_facts,
        inventory=inventory,
    )
    if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "native Lua indirect-settable evidence differs from exact rebuild"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": dict(_mapping(rebuilt["build_identity"], "build_identity")),
        "evidence_sha256": _canonical_sha256(rebuilt),
        "summary": dict(_mapping(rebuilt["summary"], "summary")),
    }


def _require_range(
    fact: tuple[int, int, str], caller_range: tuple[int, int], label: str
) -> None:
    if (
        fact[0] < caller_range[0]
        or fact[0] + fact[1] > caller_range[0] + caller_range[1]
    ):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"{label} does not lie within the exact caller atlas range"
        )


def _require_state_push(fact: tuple[int, int, str], label: str) -> None:
    _require_register_push(fact, label)
    if fact[2] not in ABI_NONVOLATILE_STATE_PUSH_SHA256:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"{label} is not an ABI-nonvolatile x86 register PUSH"
        )


def _require_table_index_push(
    fact: tuple[int, int, str], value: Any, label: str
) -> None:
    if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"{label} table index must be a signed 32-bit integer"
        )
    if value in INVALID_TABLE_INDICES:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"{label} table index is definitely invalid"
        )
    if fact[1] == 2 and -128 <= value <= 127:
        expected = _instruction_sha256(b"\x6a" + struct.pack("<b", value))
    elif fact[1] == 5:
        expected = _instruction_sha256(b"\x68" + struct.pack("<i", value))
    else:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"{label} is not an exact signed immediate PUSH"
        )
    if fact[2] != expected:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"{label} does not reconstruct its table index"
        )


def _validate_witness(
    raw: Any,
    *,
    stage_end: int,
    call_rva: int,
    caller_range: tuple[int, int],
    label: str,
) -> list[dict[str, Any]]:
    witness: list[dict[str, Any]] = []
    cursor = stage_end
    for index, raw_fact in enumerate(_array(raw, label)):
        fact_label = f"{label}[{index}]"
        item = _mapping(raw_fact, fact_label)
        _exact_keys(item, {"rva", "size", "sha256", "writes_esi"}, fact_label)
        fact = _instruction_structure(
            {key: item[key] for key in ("rva", "size", "sha256")}, fact_label
        )
        _require_range(fact, caller_range, fact_label)
        if fact[0] != cursor or type(item["writes_esi"]) is not bool:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{fact_label} breaks the contiguous classified ESI witness"
            )
        if item["writes_esi"]:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{fact_label} records an ESI clobber"
            )
        cursor += fact[1]
        witness.append(dict(item))
    if not witness or cursor != call_rva:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"{label} does not span stage end through call esi"
        )
    return witness


def _validate_cfg_graph(
    raw: Any, *, label: str
) -> tuple[Mapping[str, Any], dict[int, Mapping[str, Any]], dict[int, set[int]]]:
    graph = _mapping(raw, label)
    _exact_keys(
        graph,
        {
            "caller_entry_rva",
            "range_start_rva",
            "range_size",
            "nodes",
            "node_count",
            "edge_count",
        },
        label,
    )
    entry = _rva(graph["caller_entry_rva"], f"{label}.caller_entry_rva")
    start = _rva(graph["range_start_rva"], f"{label}.range_start_rva")
    size = graph["range_size"]
    if entry != start or type(size) is not int or size <= 0:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"{label} must begin at the exact caller entry"
        )
    nodes: dict[int, Mapping[str, Any]] = {}
    edges: dict[int, set[int]] = {}
    cursor = start
    for index, raw_node in enumerate(_array(graph["nodes"], f"{label}.nodes")):
        node_label = f"{label}.nodes[{index}]"
        node = _mapping(raw_node, node_label)
        _exact_keys(
            node,
            {
                "rva",
                "size",
                "sha256",
                "writes_esi",
                "flow_kind",
                "successor_rvas",
            },
            node_label,
        )
        fact = _instruction_structure(
            {key: node[key] for key in ("rva", "size", "sha256")},
            node_label,
        )
        if fact[0] != cursor or type(node["writes_esi"]) is not bool:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{node_label} breaks exact-range CFG continuity/classification"
            )
        if node["flow_kind"] not in _FLOW_KINDS:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{node_label} has an unsupported flow kind"
            )
        successor_values = _array(
            node["successor_rvas"], f"{node_label}.successor_rvas"
        )
        successors = [
            _rva(value, f"{node_label}.successor_rvas")
            for value in successor_values
        ]
        if successors != sorted(set(successors)):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{node_label} successors are not canonically unique"
            )
        if node["flow_kind"] in _TERMINAL_FLOW_KINDS and successors:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{node_label} terminal flow has successors"
            )
        if node["flow_kind"] in {"fallthrough", "call_fallthrough"} and len(successors) != 1:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{node_label} fallthrough flow has wrong edge count"
            )
        if node["flow_kind"] == "direct_unconditional_branch" and len(successors) != 1:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{node_label} unconditional branch has wrong edge count"
            )
        if node["flow_kind"] == "direct_conditional_branch" and len(successors) not in {1, 2}:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{node_label} conditional branch has wrong edge count"
            )
        nodes[fact[0]] = node
        edges[fact[0]] = set(successors)
        cursor += fact[1]
    if cursor != start + size or set(nodes) != set(edges):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"{label} does not exactly cover its range"
        )
    if any(successor not in nodes for values in edges.values() for successor in values):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"{label} contains an unresolved CFG successor"
        )
    for rva, node in nodes.items():
        fallthrough = rva + node["size"]
        if node["flow_kind"] in {"fallthrough", "call_fallthrough"} and edges[rva] != {fallthrough}:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} stored fallthrough edge is inconsistent with instruction extent"
            )
        if (
            node["flow_kind"] == "direct_conditional_branch"
            and fallthrough not in edges[rva]
        ):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} conditional branch omits its standard fallthrough"
            )
    if (
        type(graph["node_count"]) is not int
        or graph["node_count"] != len(nodes)
        or type(graph["edge_count"]) is not int
        or graph["edge_count"] != sum(len(values) for values in edges.values())
    ):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"{label} graph aggregates differ"
        )
    return graph, nodes, edges


def validate_native_lua_cclosure_indirect_settable_publication_structure(
    evidence: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the whole artifact without reading an executable."""
    for value, label in (
        (evidence, "evidence"),
        (direct_calls, "direct_calls"),
        (callback_census, "callback_census"),
        (setfield_publications, "setfield_publications"),
        (direct_table_setter_publications, "direct_table_setter_publications"),
        (program_facts, "program_facts"),
    ):
        _validate_json_tree(value, label)
    evidence = _mapping(evidence, "evidence")
    try:
        prerequisite = validate_native_lua_cclosure_table_setter_publication_structure(
            direct_table_setter_publications,
            direct_calls,
            callback_census,
            setfield_publications,
            program_facts,
        )
    except NativeLuaCClosureTableSetterPublicationError as exc:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            f"direct table-setter structural prerequisite failed: {exc}"
        ) from exc
    if (
        prerequisite.get("analysis_kind")
        != DIRECT_SETTER_STRUCTURE_VERIFICATION_KIND
        or prerequisite.get("status") != "structurally_verified"
    ):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "direct table-setter structural prerequisite returned unexpected result"
        )
    top_keys = {
        "schema_version",
        "analysis_kind",
        "build_identity",
        "atlas",
        "direct_call_census",
        "callback_census",
        "direct_table_setter_publication_census",
        "lua_settable_import",
        "decoder",
        "control_flow_graphs",
        "publications",
        "still_unmatched_resolved_sites",
        "builders",
        "registered_targets",
        "setter_stages",
        "method",
        "summary",
    }
    _exact_keys(evidence, top_keys, "evidence")
    if (
        type(evidence["schema_version"]) is not int
        or evidence["schema_version"] != SCHEMA_VERSION
        or evidence["analysis_kind"] != ANALYSIS_KIND
    ):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "unsupported indirect-settable schema or analysis kind"
        )
    facts = _mapping(program_facts, "program_facts")
    identity = _mapping(facts.get("identity"), "program_facts.identity")
    if not all(
        evidence["build_identity"] == item.get("build_identity")
        for item in (
            direct_calls,
            callback_census,
            setfield_publications,
            direct_table_setter_publications,
        )
    ) or evidence["build_identity"] != dict(identity):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "build identity differs from prerequisites"
        )
    ghidra = _mapping(facts.get("ghidra"), "program_facts.ghidra")
    image_base = _rva(ghidra.get("image_base"), "program_facts.ghidra.image_base")
    direct_atlas = _mapping(direct_calls.get("atlas"), "direct_calls.atlas")
    expected_atlas = {
        "analysis_kind": direct_atlas.get("analysis_kind"),
        "canonical_sha256": direct_atlas.get("canonical_sha256"),
        "function_count": direct_atlas.get("function_count"),
    }
    if evidence["atlas"] != expected_atlas:
        raise NativeLuaCClosureIndirectSettablePublicationError("atlas identity differs")
    for key, document, kind in (
        ("direct_call_census", direct_calls, DIRECT_CALL_ANALYSIS_KIND),
        ("callback_census", callback_census, CALLBACK_ANALYSIS_KIND),
    ):
        if evidence[key] != {
            "analysis_kind": kind,
            "canonical_sha256": _canonical_sha256(document),
        }:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{key} prerequisite identity differs"
            )
    if evidence["direct_table_setter_publication_census"] != _source_identity(
        direct_table_setter_publications
    ):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "direct table-setter prerequisite identity differs"
        )
    setter_import = _lua_settable_import(direct_calls)
    expected_import = {
        "library": LUA_LIBRARY,
        "name": SETTER_IMPORT,
        "iat_rva": setter_import["iat_rva"],
    }
    if evidence["lua_settable_import"] != expected_import:
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "lua_settable import identity differs"
        )
    expected_decoder = {
        "name": "capstone",
        "version": SUPPORTED_CAPSTONE_VERSION,
        "architecture": "x86",
        "mode_bits": 32,
        "detail": True,
        "accepted_publication_form": PUBLICATION_FORM,
    }
    if (
        evidence["decoder"] != expected_decoder
        or _canonical_bytes(evidence["method"]) != _canonical_bytes(_METHOD)
    ):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "decoder or method contract drifted"
        )

    cfg_by_range: dict[tuple[int, int], tuple[Mapping[str, Any], dict[int, Mapping[str, Any]], dict[int, set[int]]]] = {}
    previous_cfg_start = -1
    for index, raw_graph in enumerate(
        _array(evidence["control_flow_graphs"], "evidence.control_flow_graphs")
    ):
        label = f"evidence.control_flow_graphs[{index}]"
        graph, graph_nodes, graph_edges = _validate_cfg_graph(raw_graph, label=label)
        start = _rva(graph["range_start_rva"], f"{label}.range_start_rva")
        size = graph["range_size"]
        if start <= previous_cfg_start or (start, size) in cfg_by_range:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                "control-flow graphs are not uniquely range ordered"
            )
        previous_cfg_start = start
        cfg_by_range[(start, size)] = (graph, graph_nodes, graph_edges)

    functions = _atlas_functions(facts)
    resolved, frontier = _frontier(
        direct_table_setter_publications, callback_census
    )
    publication_keys = {
        "publication_form",
        "caller_entry_rva",
        "caller_atlas_record_sha256",
        "callback_call_rva",
        "callback_call_instruction_sha256",
        "callback_entry_rva",
        "callback_atlas_record_sha256",
        "upvalue_argument_kind",
        "literal_upvalue_count",
        "setter_stage",
        "setter_stage_iat_rva",
        "stage_between_callback_and_tail",
        "cleanup_instruction",
        "cleanup_stack_bytes",
        "table_index",
        "table_index_push",
        "state_push",
        "setter_call_rva",
        "setter_call_instruction_sha256",
        "library",
        "setter_import_name",
        "esi_preservation_classifier",
        "esi_preservation_witness",
        "esi_preservation_instruction_count",
        "cfg_proof",
    }
    unmatched_keys = {
        "caller_entry_rva",
        "caller_atlas_record_sha256",
        "callback_call_rva",
        "callback_entry_rva",
        "callback_atlas_record_sha256",
        "resolution",
    }
    seen: set[int] = set()
    previous = -1
    publications: list[Mapping[str, Any]] = []
    first_by_range: dict[tuple[int, int], int] = {}
    for call in frontier:
        source = resolved[call]
        caller = functions[_rva(source["caller_entry_rva"], "caller")]
        caller_range = _containing_range(caller, call)
        first_by_range[caller_range] = min(first_by_range.get(caller_range, call), call)
    stage_by_range: dict[tuple[int, int], tuple[int, int, str]] = {}
    used_cfg_ranges: set[tuple[int, int]] = set()
    for index, raw in enumerate(_array(evidence["publications"], "evidence.publications")):
        label = f"evidence.publications[{index}]"
        item = _mapping(raw, label)
        _exact_keys(item, publication_keys, label)
        call = _site_key(item, label)
        source = resolved.get(call)
        frontier_site = frontier.get(call)
        if source is None or frontier_site is None or call <= previous or call in seen:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                "publications do not canonically partition the residual frontier"
            )
        previous = call
        seen.add(call)
        for key in (
            "caller_entry_rva",
            "caller_atlas_record_sha256",
            "callback_entry_rva",
            "callback_atlas_record_sha256",
        ):
            if item[key] != source.get(key) or item[key] != frontier_site.get(key):
                raise NativeLuaCClosureIndirectSettablePublicationError(
                    f"{label}.{key} does not join the exact frontier"
                )
        if (
            item["callback_call_instruction_sha256"]
            != source.get("call_instruction_sha256")
            or item["upvalue_argument_kind"] != source.get("upvalue_argument_kind")
            or item["literal_upvalue_count"] != source.get("literal_upvalue_count")
        ):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} callback/upvalue metadata differs"
            )
        caller = functions.get(_rva(item["caller_entry_rva"], f"{label}.caller"))
        callback = functions.get(_rva(item["callback_entry_rva"], f"{label}.callback"))
        if (
            caller is None
            or callback is None
            or callback.get("thunk") is not False
            or item["caller_atlas_record_sha256"] != atlas_record_sha256(caller)
            or item["callback_atlas_record_sha256"] != atlas_record_sha256(callback)
        ):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} atlas join differs"
            )
        caller_range = _containing_range(caller, call)
        caller_entry = _rva(item["caller_entry_rva"], f"{label}.caller_entry_rva")
        if caller_range[0] != caller_entry or caller_range not in cfg_by_range:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} lacks an exact caller-entry CFG"
            )
        graph, graph_nodes, graph_edges = cfg_by_range[caller_range]
        used_cfg_ranges.add(caller_range)
        stage = _instruction_structure(item["setter_stage"], f"{label}.setter_stage")
        _require_range(stage, caller_range, f"{label}.setter_stage")
        iat = _rva(item["setter_stage_iat_rva"], f"{label}.setter_stage_iat_rva")
        if (
            item["setter_stage_iat_rva"] != setter_import["iat_rva"]
            or image_base + iat > 0xFFFFFFFF
            or stage[1:] != (
                6,
                _instruction_sha256(
                    MOV_ESI_ABSOLUTE_BYTES_PREFIX
                    + struct.pack("<I", image_base + iat)
                ),
            )
        ):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} setter stage does not reconstruct exact mov esi,[IAT]"
            )
        existing_stage = stage_by_range.setdefault(caller_range, stage)
        if existing_stage != stage:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} uses more than one setter stage in a caller range"
            )
        first = first_by_range[caller_range]
        expected_between = call == first
        if (
            type(item["stage_between_callback_and_tail"]) is not bool
            or item["stage_between_callback_and_tail"] != expected_between
            or stage[0] != first + 6
        ):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} stage ordering relative to first callback differs"
            )
        stage_node = graph_nodes.get(stage[0])
        callback_node = graph_nodes.get(call)
        if (
            stage_node is None
            or (stage_node["size"], stage_node["sha256"]) != stage[1:]
            or stage_node["writes_esi"] is not True
            or callback_node is None
            or callback_node["sha256"] != item["callback_call_instruction_sha256"]
        ):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} stage/callback facts do not join the stored CFG"
            )
        cleanup = _instruction_structure(
            item["cleanup_instruction"], f"{label}.cleanup_instruction"
        )
        cleanup_value = item["cleanup_stack_bytes"]
        expected_cleanup_rva = call + 6 + (stage[1] if expected_between else 0)
        if (
            type(cleanup_value) is not int
            or cleanup_value <= 0
            or cleanup_value > 0x7F
            or cleanup_value % 4
            or cleanup
            != (
                expected_cleanup_rva,
                3,
                _instruction_sha256(b"\x83\xc4" + bytes([cleanup_value])),
            )
        ):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} cleanup does not reconstruct exact contiguous form"
            )
        table_push = _instruction_structure(
            item["table_index_push"], f"{label}.table_index_push"
        )
        state_push = _instruction_structure(item["state_push"], f"{label}.state_push")
        if table_push[0] != cleanup[0] + cleanup[1]:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} table-index PUSH is not contiguous"
            )
        _require_table_index_push(table_push, item["table_index"], label)
        if state_push[0] != table_push[0] + table_push[1]:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} state PUSH is not contiguous"
            )
        _require_state_push(state_push, f"{label}.state_push")
        source_state = _instruction_structure(
            source.get("state_push"), f"{label}.callback_state_push"
        )
        if state_push[2] != source_state[2]:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} state register differs from callback construction"
            )
        setter_call = _rva(item["setter_call_rva"], f"{label}.setter_call_rva")
        if (
            setter_call != state_push[0] + state_push[1]
            or item["setter_call_instruction_sha256"] != CALL_ESI_SHA256
            or item["publication_form"] != PUBLICATION_FORM
            or item["library"] != LUA_LIBRARY
            or item["setter_import_name"] != SETTER_IMPORT
            or item["esi_preservation_classifier"]
            != ESI_PRESERVATION_CLASSIFIER
        ):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} does not reconstruct exact call esi publication"
            )
        _require_range((setter_call, 2, CALL_ESI_SHA256), caller_range, f"{label}.setter_call")
        setter_node = graph_nodes.get(setter_call)
        if (
            setter_node is None
            or setter_node["size"] != 2
            or setter_node["sha256"] != CALL_ESI_SHA256
        ):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} call esi does not join the stored CFG"
            )
        witness = _validate_witness(
            item["esi_preservation_witness"],
            stage_end=stage[0] + stage[1],
            call_rva=setter_call,
            caller_range=caller_range,
            label=f"{label}.esi_preservation_witness",
        )
        if (
            type(item["esi_preservation_instruction_count"]) is not int
            or item["esi_preservation_instruction_count"] != len(witness)
        ):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} preservation witness count differs"
            )
        witness_by_rva = {_rva(fact["rva"], "witness.rva"): fact for fact in witness}
        for fact, fact_label in (
            (cleanup, "cleanup"),
            (table_push, "table index"),
            (state_push, "state"),
        ):
            retained = witness_by_rva.get(fact[0])
            if retained is None or (retained["size"], retained["sha256"]) != fact[1:]:
                raise NativeLuaCClosureIndirectSettablePublicationError(
                    f"{label} witness does not retain exact {fact_label} instruction"
                )
        dominators = _dominators(graph_edges, caller_entry)
        path_nodes = _path_nodes(graph_edges, stage[0], setter_call)
        dominated_region = {
            node for node, values in dominators.items() if stage[0] in values
        }
        alternate_atlas_entries, declared_direct_entries = _entry_audit(
            facts, functions, caller_entry, dominated_region
        )
        bootstrap_exception = call == first
        stage_dominates_callback = call in dominators and stage[0] in dominators[call]
        stage_dominates_setter = (
            setter_call in dominators and stage[0] in dominators[setter_call]
        )
        if (
            stage[0] not in dominators
            or call not in dominators
            or setter_call not in dominators
            or not stage_dominates_setter
            or (not bootstrap_exception and not stage_dominates_callback)
            or setter_call not in path_nodes
            or any(
                graph_nodes[node]["writes_esi"]
                for node in path_nodes - {stage[0]}
            )
            or alternate_atlas_entries
            or declared_direct_entries
        ):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} stored CFG does not prove dominance and ESI preservation"
            )
        proof = _mapping(item["cfg_proof"], f"{label}.cfg_proof")
        expected_proof = {
            "caller_entry_rva": _hex(caller_entry),
            "range_start_rva": _hex(caller_range[0]),
            "range_size": caller_range[1],
            "stage_reachable": stage[0] in dominators,
            "callback_reachable": call in dominators,
            "setter_call_reachable": setter_call in dominators,
            "bootstrap_callback_dominance_exception": bootstrap_exception,
            "stage_dominates_callback": stage_dominates_callback,
            "stage_dominates_setter_call": stage_dominates_setter,
            "stage_to_setter_path_rvas": [
                _hex(node) for node in sorted(path_nodes)
            ],
            "stage_to_setter_path_node_count": len(path_nodes),
            "alternate_atlas_entry_rvas": alternate_atlas_entries,
            "declared_direct_call_entries": declared_direct_entries,
        }
        _exact_keys(proof, set(expected_proof), f"{label}.cfg_proof")
        if proof != expected_proof:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} CFG proof differs from graph recomputation"
            )
        publications.append(item)

    previous = -1
    for index, raw in enumerate(
        _array(
            evidence["still_unmatched_resolved_sites"],
            "evidence.still_unmatched_resolved_sites",
        )
    ):
        label = f"evidence.still_unmatched_resolved_sites[{index}]"
        item = _mapping(raw, label)
        _exact_keys(item, unmatched_keys, label)
        call = _site_key(item, label)
        if call not in frontier or call <= previous or call in seen:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                "still-unmatched sites do not canonically partition the frontier"
            )
        previous = call
        seen.add(call)
        if item != _unmatched(frontier[call]):
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{label} does not preserve exact frontier identity"
            )
    if seen != set(frontier):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "publication and unmatched partitions do not cover the frontier"
        )
    if used_cfg_ranges != set(cfg_by_range):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "control-flow graphs do not exactly cover publication caller ranges"
        )
    builders, targets, stages = _aggregates(publications)
    for key, expected in (
        ("builders", builders),
        ("registered_targets", targets),
        ("setter_stages", stages),
    ):
        if evidence[key] != expected:
            raise NativeLuaCClosureIndirectSettablePublicationError(
                f"{key} do not exactly aggregate publications"
            )
    expected_summary = {
        "prior_unmatched_resolved_callback_sites": len(frontier),
        "matched_indirect_settable_publication_sites": len(publications),
        "still_unmatched_resolved_callback_sites": len(
            evidence["still_unmatched_resolved_sites"]
        ),
        "unique_registered_callback_targets": len(targets),
        "unique_registration_builders": len(builders),
        "unique_setter_stages": len(stages),
        "unique_table_indices": len({item["table_index"] for item in publications}),
        "esi_preservation_witness_instructions": sum(
            item["esi_preservation_instruction_count"] for item in publications
        ),
        "cfg_instruction_nodes": sum(
            item[0]["node_count"] for item in cfg_by_range.values()
        ),
        "cfg_edges": sum(item[0]["edge_count"] for item in cfg_by_range.values()),
        "stage_to_setter_path_nodes": sum(
            item["cfg_proof"]["stage_to_setter_path_node_count"]
            for item in publications
        ),
        "schema_violations": 0,
    }
    summary = _mapping(evidence["summary"], "evidence.summary")
    _exact_keys(summary, set(expected_summary), "evidence.summary")
    if (
        any(type(value) is not int or value < 0 for value in summary.values())
        or summary != expected_summary
    ):
        raise NativeLuaCClosureIndirectSettablePublicationError(
            "summary aggregates or partitions disagree"
        )
    _assert_publication_safe(evidence)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": STRUCTURE_VERIFICATION_KIND,
        "status": "structurally_verified",
        "build_identity": dict(identity),
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": dict(summary),
    }


def encode_native_lua_cclosure_indirect_settable_publication_census(
    value: Mapping[str, Any],
) -> str:
    """Return deterministic pretty JSON for evidence or verification."""
    _validate_json_tree(value)
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True
    ) + "\n"
