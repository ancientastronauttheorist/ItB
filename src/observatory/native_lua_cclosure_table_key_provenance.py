"""Exact key and destination provenance for native Lua closure publications.

This census composes the four direct and three staged-indirect table-setter
publication sites.  It recognizes four finite x86/Lua-stack grammars and
proves the NUL-terminated literal that remains below each constructed closure
until the retained setter consumes the key/value pair.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_lua_cclosure_callbacks import (
    ANALYSIS_KIND as CALLBACK_ANALYSIS_KIND,
)
from src.observatory.native_lua_cclosure_indirect_settable_publications import (
    ANALYSIS_KIND as INDIRECT_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as INDIRECT_STRUCTURE_VERIFICATION_KIND,
    NativeLuaCClosureIndirectSettablePublicationError,
    _build_cfg as _build_base_cfg,
    _dominators,
    _entry_audit,
    _graph_maps,
    _path_nodes,
    _reachable,
    validate_native_lua_cclosure_indirect_settable_publication_census,
    validate_native_lua_cclosure_indirect_settable_publication_structure,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    ANALYSIS_KIND as SETFIELD_ANALYSIS_KIND,
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
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_cclosure_table_setter_publications import (
    ANALYSIS_KIND as DIRECT_ANALYSIS_KIND,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_CALL_ANALYSIS_KIND,
    CALL_FORM as DIRECT_CALL_FORM,
    SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_cclosure_table_key_provenance_census"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
LUA_LIBRARY = "lua5.1.dll"
LUA_GLOBALSINDEX = -10002
MAX_KEY_BYTES = 64
PE_SECTION_WRITABLE = 0x80000000
CALL_EBX = b"\xff\xd3"
MOV_EBX_ABSOLUTE = b"\x8b\x1d"

FAMILY_STRAIGHT_ZERO = "literal_key_staged_pushstring_immediate_zero"
FAMILY_GUARDED_ZERO = "literal_key_guarded_register_zero"
FAMILY_DIRECT_TWO = "literal_key_direct_pushstring_two_pushvalue_upvalues"
FAMILY_DEFERRED_TWO = "deferred_literal_key_two_mixed_upvalues"

# The deferred family has native arguments live below this one exact interior.
# Pinning every instruction identity is deliberately narrower than inferring
# safety from ESP register writes: a memory store through [esp] (or an alias)
# could otherwise overwrite the already-pushed Lua state or key pointer.
_DEFERRED_ARGUMENT_INTERIOR = (
    (
        0x002EB262,
        3,
        "46c0a35388ffeea6b7b7d4630921b409a81d597ae38ab2ceed59f5e0970a80a2",
        "fallthrough",
    ),
    (
        0x002EB265,
        3,
        "d17bddef22a785fc990a432aac8fd00c6a11270dedadbd2fe02c3d4df45cdc2f",
        "fallthrough",
    ),
    (
        0x002EB268,
        3,
        "1c01cae36ef9e8aba23d072bb32b0079c25d0f01d4307d35c087ce86f249ac8e",
        "fallthrough",
    ),
    (
        0x002EB26B,
        2,
        "3bd1fbb2400f6799924aa6bca033b5be2a53f4c382f6633f4a87980b33d66a80",
        "direct_conditional_branch",
    ),
)

_METHOD = {
    "publication_prerequisites_exactly_verified": True,
    "accepted_families": [
        FAMILY_DEFERRED_TWO,
        FAMILY_DIRECT_TWO,
        FAMILY_GUARDED_ZERO,
        FAMILY_STRAIGHT_ZERO,
    ],
    "native_register_provenance": (
        "Every call ebx used as a Lua API call has an exact mov ebx,[IAT] "
        "stage that dominates the call in the fully decoded caller CFG. No "
        "node on any stage-to-call path after the stage writes EBX; calls are "
        "accepted under the explicit 32-bit Windows cdecl nonvolatile-EBX premise."
    ),
    "lua_stack_model": (
        "Under the exact Lua 5.1 API premise, lua_pushstring and each retained "
        "upvalue producer push one Lua value; lua_pushcclosure(L,f,n) consumes "
        "exactly n top upvalues and pushes one closure; lua_settable and lua_rawset "
        "then consume the surviving key and closure value. Native x86 argument "
        "pushes and add-esp cleanup do not themselves change the Lua VM stack."
    ),
    "destination_model": (
        "The Lua 5.1 ABI defines -10002 as LUA_GLOBALSINDEX. A -3 destination "
        "is retained only when an exact same-state lua_createtable call and the "
        "complete intervening stack grammar prove that the new table occupies "
        "the relative -3 slot at the setter."
    ),
    "literal_boundary": (
        "Keys are bounded printable-ASCII NUL-terminated byte strings in one "
        "file-backed non-writable PE section. The artifact publishes their RVA, "
        "display text, byte length, section metadata, and complete bytes-including-"
        "NUL SHA-256, never executable bytes or disassembly."
    ),
    "cfg_boundary": (
        "CFG edges model ordinary fallthrough, immediate conditional and "
        "unconditional branches, returning-call fallthrough, and terminal or "
        "indirect-jump stops. Atlas entries and Ghidra-declared direct targets "
        "into each proved dominated region are rejected; unmodeled indirect, "
        "exception, or externally fabricated entries remain an explicit premise."
    ),
    "structural_boundary": (
        "PE-free validation rechecks prerequisite partitions, graph continuity, "
        "stored edges, dominance, path sets, register-write exclusions, entry "
        "audits, reconstructible x86 hashes, Lua-stack traces, literals, and "
        "aggregates. Branch opcodes, decoded register-write classifications, "
        "and literal bytes still require an exact executable rebuild."
    ),
    "not_claimed": [
        "runtime reachability, execution, frequency, persistence, or lifetime",
        "a stable global export, ordinary Lua lookup success, or absence of later mutation",
        "a semantic name, metatable identity, module identity, class identity, or ownership for either fresh table",
        "that lua_settable bypasses __newindex or performs a raw store",
        "source-level reconstruction, function purpose, or behavioral equivalence beyond the retained stack grammar",
        "binary-only proof that arbitrary callees obey the Windows cdecl EBX-preservation premise",
    ],
}


class NativeLuaCClosureTableKeyProvenanceError(RuntimeError):
    """Raised for invalid or stale native Lua table-key evidence."""


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _source_identity(document: Mapping[str, Any], kind: str) -> dict[str, Any]:
    if document.get("analysis_kind") != kind:
        raise NativeLuaCClosureTableKeyProvenanceError(
            "publication prerequisite has the wrong analysis kind"
        )
    return {"analysis_kind": kind, "canonical_sha256": _canonical_sha256(document)}


def _imports(direct_calls: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(_array(direct_calls.get("lua_imports"), "direct_calls.lua_imports")):
        item = _mapping(raw, f"direct_calls.lua_imports[{index}]")
        name = item.get("name")
        if type(name) is not str or item.get("library") != LUA_LIBRARY or name in result:
            raise NativeLuaCClosureTableKeyProvenanceError("Lua import facts disagree")
        result[name] = item
    required = {
        "lua_createtable",
        "lua_pushcclosure",
        "lua_pushlightuserdata",
        "lua_pushnil",
        "lua_pushstring",
        "lua_pushvalue",
        "lua_rawset",
        "lua_settable",
    }
    if not required <= set(result):
        raise NativeLuaCClosureTableKeyProvenanceError("required Lua imports are absent")
    return result


def _direct_calls(
    direct_calls: Mapping[str, Any],
) -> dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]]:
    result: dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    for record_index, raw_record in enumerate(_array(direct_calls.get("records"), "direct_calls.records")):
        record = _mapping(raw_record, f"direct_calls.records[{record_index}]")
        for raw_call in _array(record.get("direct_lua_import_calls"), "direct Lua calls"):
            call = _mapping(raw_call, "direct Lua call")
            rva = _rva(call.get("call_rva"), "direct Lua call RVA")
            if rva in result:
                raise NativeLuaCClosureTableKeyProvenanceError("direct Lua call RVAs repeat")
            result[rva] = (record, call)
    return result


def _call_bytes(image_base: int, imported: Mapping[str, Any]) -> bytes:
    iat = _rva(imported.get("iat_rva"), "Lua import IAT RVA")
    if image_base + iat > 0xFFFFFFFF:
        raise NativeLuaCClosureTableKeyProvenanceError("Lua import VA overflows x86")
    return b"\xff\x15" + struct.pack("<I", image_base + iat)


def _push_i32(value: int) -> bytes:
    if -128 <= value <= 127:
        return b"\x6a" + struct.pack("<b", value)
    return b"\x68" + struct.pack("<i", value)


def _require_bytes(instruction: Any, expected: bytes, label: str) -> None:
    if bytes(instruction.bytes) != expected:
        raise NativeLuaCClosureTableKeyProvenanceError(f"{label} differs from exact grammar")


def _require_direct_call(
    instruction: Any,
    api_name: str,
    imports: Mapping[str, Mapping[str, Any]],
    calls: Mapping[int, tuple[Mapping[str, Any], Mapping[str, Any]]],
    image_base: int,
    caller_entry: str,
    label: str,
) -> dict[str, Any]:
    _require_bytes(instruction, _call_bytes(image_base, imports[api_name]), label)
    rva = instruction.address - image_base
    joined = calls.get(rva)
    if (
        joined is None
        or joined[0].get("entry_rva") != caller_entry
        or joined[1].get("import_name") != api_name
        or joined[1].get("library") != LUA_LIBRARY
        or joined[1].get("call_form") != DIRECT_CALL_FORM
        or joined[1].get("iat_rva") != imports[api_name].get("iat_rva")
        or joined[1].get("instruction_sha256") != _instruction_sha256(bytes(instruction.bytes))
    ):
        raise NativeLuaCClosureTableKeyProvenanceError(f"{label} does not join direct-call census")
    return _instruction_fact(instruction, image_base)


def _register_writes(instruction: Any, register: int) -> bool:
    try:
        _reads, writes = instruction.regs_access()
    except Exception as exc:  # pragma: no cover - decoder contract failure
        raise NativeLuaCClosureTableKeyProvenanceError(
            "Capstone could not classify register writes"
        ) from exc
    return register in writes


def _enhanced_cfg(
    instructions: list[Any],
    image_base: int,
    caller_range: tuple[int, int],
    capstone_module: Any,
    x86: Any,
) -> dict[str, Any]:
    graph = _build_base_cfg(
        instructions, image_base, caller_range, capstone_module, x86
    )
    if graph is None:
        raise NativeLuaCClosureTableKeyProvenanceError(
            "caller range has unsupported or incomplete control flow"
        )
    if len(graph["nodes"]) != len(instructions):
        raise NativeLuaCClosureTableKeyProvenanceError("CFG instruction count differs")
    nodes = []
    for node, instruction in zip(graph["nodes"], instructions):
        nodes.append(
            {
                **node,
                "writes_ebx": _register_writes(instruction, x86.X86_REG_EBX),
                "writes_esp": _register_writes(instruction, x86.X86_REG_ESP),
            }
        )
    return {**graph, "nodes": nodes}


def _graph_instruction_maps(
    graph: Mapping[str, Any], instructions: list[Any], image_base: int
) -> tuple[dict[int, Mapping[str, Any]], dict[int, set[int]], dict[int, Any]]:
    nodes, edges = _graph_maps(graph)
    decoded = {instruction.address - image_base: instruction for instruction in instructions}
    if set(nodes) != set(decoded):
        raise NativeLuaCClosureTableKeyProvenanceError("CFG and decoder node sets differ")
    return nodes, edges, decoded


def _register_api_proof(
    *,
    api_name: str,
    call_instruction: Any,
    graph: Mapping[str, Any],
    instructions: list[Any],
    image_base: int,
    imports: Mapping[str, Mapping[str, Any]],
    program_facts: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
    caller_entry: int,
) -> dict[str, Any]:
    _require_bytes(call_instruction, CALL_EBX, f"{api_name} register call")
    nodes, edges, decoded = _graph_instruction_maps(graph, instructions, image_base)
    call_rva = call_instruction.address - image_base
    dominators = _dominators(edges, caller_entry)
    imported = imports[api_name]
    iat = _rva(imported.get("iat_rva"), f"{api_name} IAT")
    expected_stage = MOV_EBX_ABSOLUTE + struct.pack("<I", image_base + iat)
    candidates = [
        rva
        for rva, instruction in decoded.items()
        if bytes(instruction.bytes) == expected_stage
        and call_rva in dominators
        and rva in dominators[call_rva]
    ]
    if len(candidates) != 1:
        raise NativeLuaCClosureTableKeyProvenanceError(
            f"{api_name} call lacks one dominating EBX import stage"
        )
    stage_rva = candidates[0]
    path = _path_nodes(edges, stage_rva, call_rva)
    if call_rva not in path or any(nodes[rva]["writes_ebx"] for rva in path - {stage_rva}):
        raise NativeLuaCClosureTableKeyProvenanceError(
            f"{api_name} EBX provenance is clobbered on a stage-to-call path"
        )
    dominated = {node for node, values in dominators.items() if stage_rva in values}
    atlas_entries, declared_entries = _entry_audit(
        program_facts, functions, caller_entry, dominated
    )
    if atlas_entries or declared_entries:
        raise NativeLuaCClosureTableKeyProvenanceError(
            f"{api_name} EBX proof region has an alternate modeled entry"
        )
    stage = decoded[stage_rva]
    return {
        "api_name": api_name,
        "library": LUA_LIBRARY,
        "iat_rva": imported["iat_rva"],
        "register": "ebx",
        "stage": _instruction_fact(stage, image_base),
        "call": _instruction_fact(call_instruction, image_base),
        "stage_dominates_call": True,
        "stage_to_call_path_rvas": [_hex(rva) for rva in sorted(path)],
        "stage_to_call_path_node_count": len(path),
        "post_stage_ebx_writers": [],
        "alternate_atlas_entry_rvas": atlas_entries,
        "declared_direct_call_entries": declared_entries,
        "abi_premise": "x86_windows_cdecl_nonvolatile_ebx",
    }


def _read_key_literal(data: bytes, image: Any, push_instruction: Any) -> dict[str, Any]:
    encoded = bytes(push_instruction.bytes)
    if len(encoded) != 5 or encoded[0] != 0x68:
        raise NativeLuaCClosureTableKeyProvenanceError("key address is not push imm32")
    (va,) = struct.unpack("<I", encoded[1:])
    if va < image.image_base:
        raise NativeLuaCClosureTableKeyProvenanceError("key VA precedes image base")
    rva = va - image.image_base
    raw = bytearray()
    first_offset: int | None = None
    previous_offset: int | None = None
    for delta in range(MAX_KEY_BYTES + 1):
        offset = image.rva_to_file_offset(rva + delta)
        if offset is None or offset >= len(data):
            raise NativeLuaCClosureTableKeyProvenanceError("key is not file-backed")
        if first_offset is None:
            first_offset = offset
        if previous_offset is not None and offset != previous_offset + 1:
            raise NativeLuaCClosureTableKeyProvenanceError("key bytes are not contiguous")
        previous_offset = offset
        byte = data[offset]
        raw.append(byte)
        if byte == 0:
            break
        if byte < 0x20 or byte > 0x7E:
            raise NativeLuaCClosureTableKeyProvenanceError("key is not printable ASCII")
    else:  # pragma: no cover
        raise NativeLuaCClosureTableKeyProvenanceError("key exceeds bounded length")
    if len(raw) < 2 or raw[-1] != 0 or len(raw) - 1 > MAX_KEY_BYTES:
        raise NativeLuaCClosureTableKeyProvenanceError("key lacks bounded NUL terminator")
    section = image.section_for_offset(first_offset)
    if section is None or section.characteristics & PE_SECTION_WRITABLE:
        raise NativeLuaCClosureTableKeyProvenanceError(
            "key literal is not in one non-writable PE section"
        )
    if image.section_for_offset(previous_offset) != section:
        raise NativeLuaCClosureTableKeyProvenanceError("key crosses a PE section")
    text = bytes(raw[:-1]).decode("ascii")
    return {
        "text": text,
        "rva": _hex(rva),
        "byte_length_excluding_nul": len(raw) - 1,
        "nul_terminated_bytes_sha256": hashlib.sha256(bytes(raw)).hexdigest(),
        "section_name": section.name,
        "section_rva": _hex(section.virtual_address),
        "section_characteristics": _hex(section.characteristics),
        "section_writable": False,
    }


def _zero_guard_proof(
    *,
    callback_rva: int,
    graph: Mapping[str, Any],
    instructions: list[Any],
    image_base: int,
    x86: Any,
) -> dict[str, Any]:
    nodes, edges, decoded = _graph_instruction_maps(graph, instructions, image_base)
    ordered = sorted(decoded)
    candidates: list[tuple[int, int, int, int, set[int]]] = []
    for left, right in zip(ordered, ordered[1:]):
        if bytes(decoded[left].bytes) != b"\x85\xf6" or right != left + decoded[left].size:
            continue
        branch = decoded[right]
        if branch.id != x86.X86_INS_JNE:
            continue
        successors = edges[right]
        fallthrough = right + branch.size
        nonzero = next((item for item in successors if item != fallthrough), None)
        if nonzero is None or callback_rva not in _reachable(edges, fallthrough) or callback_rva in _reachable(edges, nonzero):
            continue
        path = _path_nodes(edges, fallthrough, callback_rva)
        if callback_rva not in path or any(nodes[rva]["writes_esi"] for rva in path):
            continue
        dominators = _dominators(edges, _rva(graph["caller_entry_rva"], "CFG caller"))
        if right not in dominators.get(callback_rva, set()):
            continue
        candidates.append((left, right, fallthrough, nonzero, path))
    if len(candidates) != 1:
        raise NativeLuaCClosureTableKeyProvenanceError(
            "register upvalue count lacks one exact ESI-zero publication guard"
        )
    test, branch, zero, nonzero, path = candidates[0]
    return {
        "register": "esi",
        "test": _instruction_fact(decoded[test], image_base),
        "nonzero_branch": _instruction_fact(decoded[branch], image_base),
        "zero_fallthrough_rva": _hex(zero),
        "nonzero_successor_rva": _hex(nonzero),
        "branch_dominates_callback": True,
        "zero_path_rvas": [_hex(rva) for rva in sorted(path)],
        "zero_path_node_count": len(path),
        "zero_path_esi_writers": [],
    }


def _deferred_argument_proof(
    *,
    key_push: Any,
    state_push: Any,
    key_call: Any,
    graph: Mapping[str, Any],
    instructions: list[Any],
    image_base: int,
    program_facts: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
    caller_entry: int,
) -> dict[str, Any]:
    nodes, edges, _decoded = _graph_instruction_maps(graph, instructions, image_base)
    key_rva = key_push.address - image_base
    state_rva = state_push.address - image_base
    call_rva = key_call.address - image_base
    dominators = _dominators(edges, caller_entry)
    if (
        state_rva != key_rva + key_push.size
        or key_rva not in dominators.get(call_rva, set())
        or state_rva not in dominators.get(call_rva, set())
    ):
        raise NativeLuaCClosureTableKeyProvenanceError(
            "deferred key arguments do not dominate the pushstring call"
        )
    path = _path_nodes(edges, state_rva, call_rva)
    interior = tuple(
        (
            rva,
            nodes[rva]["size"],
            nodes[rva]["sha256"],
            nodes[rva]["flow_kind"],
        )
        for rva in sorted(path - {state_rva, call_rva})
    )
    if call_rva not in path or any(
        nodes[rva]["writes_esp"] for rva in path - {state_rva, call_rva}
    ) or interior != _DEFERRED_ARGUMENT_INTERIOR:
        raise NativeLuaCClosureTableKeyProvenanceError(
            "deferred key arguments are changed on a path to pushstring"
        )
    dominated = {node for node, values in dominators.items() if key_rva in values}
    atlas_entries, declared_entries = _entry_audit(
        program_facts, functions, caller_entry, dominated
    )
    if atlas_entries or declared_entries:
        raise NativeLuaCClosureTableKeyProvenanceError(
            "deferred key argument region has an alternate modeled entry"
        )
    return {
        "key_push_dominates_call": True,
        "state_push_dominates_call": True,
        "state_to_call_path_rvas": [_hex(rva) for rva in sorted(path)],
        "state_to_call_path_node_count": len(path),
        "interior_esp_writers": [],
        "alternate_atlas_entry_rvas": atlas_entries,
        "declared_direct_call_entries": declared_entries,
    }


def _upvalue_producer(
    *,
    argument: Any,
    state: Any,
    call: Any,
    api_name: str,
    state_bytes: bytes,
    graph: Mapping[str, Any],
    instructions: list[Any],
    image_base: int,
    imports: Mapping[str, Mapping[str, Any]],
    calls: Mapping[int, tuple[Mapping[str, Any], Mapping[str, Any]]],
    program_facts: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
    caller_entry: int,
    caller_entry_text: str,
    register_call: bool,
) -> dict[str, Any]:
    _require_bytes(state, state_bytes, f"{api_name} state")
    if register_call:
        proof = _register_api_proof(
            api_name=api_name,
            call_instruction=call,
            graph=graph,
            instructions=instructions,
            image_base=image_base,
            imports=imports,
            program_facts=program_facts,
            functions=functions,
            caller_entry=caller_entry,
        )
        form = "staged_ebx"
    else:
        _require_direct_call(
            call, api_name, imports, calls, image_base, caller_entry_text, api_name
        )
        proof = None
        form = "direct_ff15"
    return {
        "api_name": api_name,
        "argument_push": _instruction_fact(argument, image_base),
        "state_push": _instruction_fact(state, image_base),
        "call": _instruction_fact(call, image_base),
        "call_form": form,
        "register_api_proof": proof,
        "vm_stack_effect": "push_one_upvalue",
    }


def _fresh_table_destination(
    *,
    key_index: int,
    instructions: list[Any],
    state_bytes: bytes,
    zero_guard: Mapping[str, Any] | None,
    image_base: int,
    imports: Mapping[str, Mapping[str, Any]],
    calls: Mapping[int, tuple[Mapping[str, Any], Mapping[str, Any]]],
    caller_entry_text: str,
) -> dict[str, Any]:
    cursor = key_index - 1
    cleanup = None
    encoded = bytes(instructions[cursor].bytes)
    if len(encoded) == 3 and encoded[:2] == b"\x83\xc4":
        cleanup = _instruction_fact(instructions[cursor], image_base)
        cursor -= 1
    call = instructions[cursor]
    _require_direct_call(
        call,
        "lua_createtable",
        imports,
        calls,
        image_base,
        caller_entry_text,
        "fresh-table creator",
    )
    interior = None
    if bytes(instructions[cursor - 1].bytes) == b"\x89\x45\xf0":
        # One reviewed compiler scheduling form stores the immediately prior
        # allocation result after pushing the three createtable arguments.
        interior = _instruction_fact(instructions[cursor - 1], image_base)
        first, second, state = instructions[cursor - 4 : cursor - 1]
    else:
        first, second, state = instructions[cursor - 3 : cursor]
    _require_bytes(state, state_bytes, "fresh-table state")
    immediate_zero = bytes(first.bytes) == b"\x6a\x00" and bytes(second.bytes) == b"\x6a\x00"
    guarded_zero = bytes(first.bytes) == b"\x56" and bytes(second.bytes) == b"\x56" and zero_guard is not None
    if not (immediate_zero or guarded_zero):
        raise NativeLuaCClosureTableKeyProvenanceError(
            "fresh-table creator lacks two proved zero size arguments"
        )
    return {
        "class": "fresh_unnamed_table_at_relative_index_minus_3",
        "lua_table_index": -3,
        "creator_api": "lua_createtable",
        "creator_call": _instruction_fact(call, image_base),
        "array_size_push": _instruction_fact(first, image_base),
        "hash_size_push": _instruction_fact(second, image_base),
        "size_argument_proof": "immediate_zero" if immediate_zero else "guarded_esi_zero",
        "state_push": _instruction_fact(state, image_base),
        "native_argument_interior": interior,
        "native_argument_cleanup": cleanup,
        "semantic_table_identity": None,
    }


def _alternate_clear(
    *,
    key_call_index: int,
    instructions: list[Any],
    state_bytes: bytes,
    graph: Mapping[str, Any],
    image_base: int,
    imports: Mapping[str, Mapping[str, Any]],
    calls: Mapping[int, tuple[Mapping[str, Any], Mapping[str, Any]]],
    program_facts: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
    caller_entry: int,
    caller_entry_text: str,
    capstone_module: Any,
) -> dict[str, Any]:
    publication_call = instructions[key_call_index]
    publication_rva = publication_call.address - image_base
    # The alternate arm is the lexical fallthrough of the conditional branch
    # immediately before the publication target and ends in a jump over it.
    branch_index = key_call_index - 1
    while branch_index >= 0 and instructions[branch_index].address + instructions[branch_index].size <= publication_call.address:
        instruction = instructions[branch_index]
        if instruction.group(capstone_module.CS_GRP_JUMP):
            operands = list(instruction.operands)
            if operands and int(getattr(operands[0], "imm", 0)) - image_base == publication_rva:
                break
        branch_index -= 1
    if branch_index < 0:
        raise NativeLuaCClosureTableKeyProvenanceError("deferred publication lacks alternate branch")
    alt = instructions[branch_index + 1 : key_call_index]
    if len(alt) != 8:
        raise NativeLuaCClosureTableKeyProvenanceError("alternate clear arm has another shape")
    key_call, nil_state, nil_call, index_push, setter_state, setter_call, cleanup, jump = alt
    key_proof = _register_api_proof(
        api_name="lua_pushstring",
        call_instruction=key_call,
        graph=graph,
        instructions=instructions,
        image_base=image_base,
        imports=imports,
        program_facts=program_facts,
        functions=functions,
        caller_entry=caller_entry,
    )
    _require_bytes(nil_state, state_bytes, "alternate nil state")
    _require_direct_call(nil_call, "lua_pushnil", imports, calls, image_base, caller_entry_text, "alternate nil")
    _require_bytes(index_push, _push_i32(LUA_GLOBALSINDEX), "alternate global index")
    _require_bytes(setter_state, state_bytes, "alternate setter state")
    _require_direct_call(setter_call, "lua_settable", imports, calls, image_base, caller_entry_text, "alternate setter")
    encoded_cleanup = bytes(cleanup.bytes)
    if (
        len(encoded_cleanup) != 3
        or encoded_cleanup[:2] != b"\x83\xc4"
        or not jump.group(capstone_module.CS_GRP_JUMP)
    ):
        raise NativeLuaCClosureTableKeyProvenanceError("alternate clear tail differs")
    return {
        "condition_branch": _instruction_fact(instructions[branch_index], image_base),
        "key_call": _instruction_fact(key_call, image_base),
        "key_register_api_proof": key_proof,
        "nil_state_push": _instruction_fact(nil_state, image_base),
        "nil_call": _instruction_fact(nil_call, image_base),
        "table_index": LUA_GLOBALSINDEX,
        "table_index_push": _instruction_fact(index_push, image_base),
        "setter_state_push": _instruction_fact(setter_state, image_base),
        "setter_call": _instruction_fact(setter_call, image_base),
        "native_cleanup": _instruction_fact(cleanup, image_base),
        "branch_around_publication": _instruction_fact(jump, image_base),
        "effect_under_lua51_api_premise": "globals[key] receives nil on alternate arm",
    }


def _aggregates(publications: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    literals: dict[str, Mapping[str, Any]] = {}
    by_key: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for publication in publications:
        key = publication["key"]["text"]
        prior = literals.setdefault(key, publication["key"])
        if prior != publication["key"]:
            raise NativeLuaCClosureTableKeyProvenanceError("one key text has multiple literal identities")
        by_key[key].append(publication)
    literal_records = [dict(literals[key]) for key in sorted(literals)]
    key_records = [
        {
            "key": key,
            "publication_site_count": len(items),
            "callback_call_rvas": sorted(item["callback_call_rva"] for item in items),
            "callback_entry_rvas": sorted({item["callback_entry_rva"] for item in items}),
            "destination_classes": sorted({item["destination"]["class"] for item in items}),
        }
        for key, items in sorted(by_key.items())
    ]
    return literal_records, key_records


_FLOW_KINDS = {
    "fallthrough",
    "call_fallthrough",
    "direct_conditional_branch",
    "direct_unconditional_branch",
    "terminal",
    "indirect_jump",
}


def _validated_graphs(
    evidence: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
) -> dict[int, tuple[Mapping[str, Any], dict[int, Mapping[str, Any]], dict[int, set[int]]]]:
    result: dict[int, tuple[Mapping[str, Any], dict[int, Mapping[str, Any]], dict[int, set[int]]]] = {}
    previous = -1
    graph_keys = {
        "caller_entry_rva", "range_start_rva", "range_size", "nodes", "node_count", "edge_count"
    }
    node_keys = {
        "rva", "size", "sha256", "writes_esi", "writes_ebx", "writes_esp",
        "flow_kind", "successor_rvas",
    }
    for index, raw_graph in enumerate(_array(evidence.get("control_flow_graphs"), "control_flow_graphs")):
        label = f"control_flow_graphs[{index}]"
        graph = _mapping(raw_graph, label)
        _exact_keys(graph, graph_keys, label)
        entry = _rva(graph.get("caller_entry_rva"), f"{label}.caller_entry_rva")
        start = _rva(graph.get("range_start_rva"), f"{label}.range_start_rva")
        size = graph.get("range_size")
        if (
            entry <= previous
            or entry in result
            or type(size) is not int
            or size <= 0
            or entry not in functions
        ):
            raise NativeLuaCClosureTableKeyProvenanceError("CFG identities are not canonical")
        previous = entry
        ranges = [
            (_rva(item.get("start_rva"), "atlas range start"), item.get("size"))
            for item in _array(functions[entry].get("ranges"), "atlas ranges")
            if isinstance(item, Mapping)
        ]
        if (start, size) not in ranges:
            raise NativeLuaCClosureTableKeyProvenanceError("CFG does not join one exact atlas range")
        nodes: dict[int, Mapping[str, Any]] = {}
        edges: dict[int, set[int]] = {}
        ordered: list[int] = []
        for node_index, raw_node in enumerate(_array(graph.get("nodes"), f"{label}.nodes")):
            node_label = f"{label}.nodes[{node_index}]"
            node = _mapping(raw_node, node_label)
            _exact_keys(node, node_keys, node_label)
            rva = _rva(node.get("rva"), f"{node_label}.rva")
            node_size = node.get("size")
            sha = node.get("sha256")
            successors = [_rva(item, f"{node_label}.successor") for item in _array(node.get("successor_rvas"), f"{node_label}.successors")]
            if (
                rva in nodes
                or type(node_size) is not int
                or node_size <= 0
                or node_size > 15
                or type(sha) is not str
                or len(sha) != 64
                or any(character not in "0123456789abcdef" for character in sha)
                or any(type(node.get(field)) is not bool for field in ("writes_esi", "writes_ebx", "writes_esp"))
                or node.get("flow_kind") not in _FLOW_KINDS
                or successors != sorted(set(successors))
            ):
                raise NativeLuaCClosureTableKeyProvenanceError("CFG node is malformed")
            nodes[rva] = node
            edges[rva] = set(successors)
            ordered.append(rva)
        if (
            not ordered
            or ordered[0] != start
            or ordered != sorted(ordered)
            or any(left + nodes[left]["size"] != right for left, right in zip(ordered, ordered[1:]))
            or ordered[-1] + nodes[ordered[-1]]["size"] != start + size
            or set().union(*edges.values(), set()) - set(nodes)
        ):
            raise NativeLuaCClosureTableKeyProvenanceError("CFG nodes are not one exact contiguous range")
        for rva, node in nodes.items():
            count = len(edges[rva])
            flow = node["flow_kind"]
            expected_count = 0 if flow in {"terminal", "indirect_jump"} else 2 if flow == "direct_conditional_branch" else 1
            if count != expected_count:
                raise NativeLuaCClosureTableKeyProvenanceError("CFG successor count differs from flow kind")
            fallthrough = rva + node["size"]
            if (
                flow in {"fallthrough", "call_fallthrough"}
                and edges[rva] != {fallthrough}
            ) or (
                flow == "direct_conditional_branch"
                and fallthrough not in edges[rva]
            ):
                raise NativeLuaCClosureTableKeyProvenanceError(
                    "CFG fallthrough edge differs from instruction layout"
                )
        if graph.get("node_count") != len(nodes) or graph.get("edge_count") != sum(map(len, edges.values())):
            raise NativeLuaCClosureTableKeyProvenanceError("CFG aggregate counts differ")
        result[entry] = (graph, nodes, edges)
    return result


def _fact_matches_node(
    raw_fact: Any,
    nodes: Mapping[int, Mapping[str, Any]],
    label: str,
) -> tuple[int, int, str]:
    fact = _instruction_structure(raw_fact, label)
    node = nodes.get(fact[0])
    if node is None or (node.get("size"), node.get("sha256")) != fact[1:]:
        raise NativeLuaCClosureTableKeyProvenanceError(f"{label} does not join stored CFG")
    return fact


def _validate_register_proof_structure(
    raw_proof: Any,
    *,
    graph_data: tuple[Mapping[str, Any], dict[int, Mapping[str, Any]], dict[int, set[int]]],
    api_imports: Mapping[str, Mapping[str, Any]],
    image_base: int,
    program_facts: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
    caller_entry: int,
    label: str,
) -> None:
    proof = _mapping(raw_proof, label)
    fields = {
        "api_name", "library", "iat_rva", "register", "stage", "call",
        "stage_dominates_call", "stage_to_call_path_rvas",
        "stage_to_call_path_node_count", "post_stage_ebx_writers",
        "alternate_atlas_entry_rvas", "declared_direct_call_entries", "abi_premise",
    }
    _exact_keys(proof, fields, label)
    graph, nodes, edges = graph_data
    api_name = proof.get("api_name")
    imported = api_imports.get(api_name)
    stage = _fact_matches_node(proof.get("stage"), nodes, f"{label}.stage")
    call = _fact_matches_node(proof.get("call"), nodes, f"{label}.call")
    if (
        imported is None
        or proof.get("library") != LUA_LIBRARY
        or proof.get("iat_rva") != imported.get("iat_rva")
        or proof.get("register") != "ebx"
        or proof.get("abi_premise") != "x86_windows_cdecl_nonvolatile_ebx"
        or stage[1:] != (
            6,
            _instruction_sha256(
                MOV_EBX_ABSOLUTE
                + struct.pack("<I", image_base + _rva(imported.get("iat_rva"), "IAT"))
            ),
        )
        or call[1:] != (2, _instruction_sha256(CALL_EBX))
    ):
        raise NativeLuaCClosureTableKeyProvenanceError(f"{label} API identity differs")
    dominators = _dominators(edges, caller_entry)
    path = _path_nodes(edges, stage[0], call[0])
    stored_path = [_rva(item, f"{label}.path") for item in _array(proof.get("stage_to_call_path_rvas"), f"{label}.path")]
    dominated = {node for node, values in dominators.items() if stage[0] in values}
    atlas_entries, declared_entries = _entry_audit(program_facts, functions, caller_entry, dominated)
    if (
        proof.get("stage_dominates_call") is not True
        or stage[0] not in dominators.get(call[0], set())
        or stored_path != sorted(path)
        or proof.get("stage_to_call_path_node_count") != len(path)
        or proof.get("post_stage_ebx_writers") != []
        or any(nodes[rva]["writes_ebx"] for rva in path - {stage[0]})
        or proof.get("alternate_atlas_entry_rvas") != atlas_entries
        or proof.get("declared_direct_call_entries") != declared_entries
        or atlas_entries
        or declared_entries
    ):
        raise NativeLuaCClosureTableKeyProvenanceError(f"{label} CFG proof differs")


def _validate_zero_guard_structure(
    raw_proof: Any,
    *,
    graph_data: tuple[Mapping[str, Any], dict[int, Mapping[str, Any]], dict[int, set[int]]],
    caller_entry: int,
    callback_rva: int,
    label: str,
) -> None:
    proof = _mapping(raw_proof, label)
    fields = {
        "register", "test", "nonzero_branch", "zero_fallthrough_rva",
        "nonzero_successor_rva", "branch_dominates_callback", "zero_path_rvas",
        "zero_path_node_count", "zero_path_esi_writers",
    }
    _exact_keys(proof, fields, label)
    _graph, nodes, edges = graph_data
    test = _fact_matches_node(proof.get("test"), nodes, f"{label}.test")
    branch = _fact_matches_node(proof.get("nonzero_branch"), nodes, f"{label}.branch")
    zero = _rva(proof.get("zero_fallthrough_rva"), f"{label}.zero")
    nonzero = _rva(proof.get("nonzero_successor_rva"), f"{label}.nonzero")
    path = _path_nodes(edges, zero, callback_rva)
    stored = [_rva(item, f"{label}.path") for item in _array(proof.get("zero_path_rvas"), f"{label}.path")]
    dominators = _dominators(edges, caller_entry)
    if (
        proof.get("register") != "esi"
        or test[1:] != (2, _instruction_sha256(b"\x85\xf6"))
        or branch[0] != test[0] + test[1]
        or edges.get(branch[0]) != {zero, nonzero}
        or callback_rva not in _reachable(edges, zero)
        or callback_rva in _reachable(edges, nonzero)
        or proof.get("branch_dominates_callback") is not True
        or branch[0] not in dominators.get(callback_rva, set())
        or stored != sorted(path)
        or proof.get("zero_path_node_count") != len(path)
        or proof.get("zero_path_esi_writers") != []
        or any(nodes[rva]["writes_esi"] for rva in path)
    ):
        raise NativeLuaCClosureTableKeyProvenanceError(f"{label} zero proof differs")


def _validate_deferred_structure(
    raw_proof: Any,
    *,
    graph_data: tuple[Mapping[str, Any], dict[int, Mapping[str, Any]], dict[int, set[int]]],
    caller_entry: int,
    key_push: tuple[int, int, str],
    state_push: tuple[int, int, str],
    key_call: tuple[int, int, str],
    program_facts: Mapping[str, Any],
    functions: Mapping[int, Mapping[str, Any]],
    label: str,
) -> None:
    proof = _mapping(raw_proof, label)
    fields = {
        "key_push_dominates_call", "state_push_dominates_call",
        "state_to_call_path_rvas", "state_to_call_path_node_count",
        "interior_esp_writers", "alternate_atlas_entry_rvas", "declared_direct_call_entries",
    }
    _exact_keys(proof, fields, label)
    _graph, nodes, edges = graph_data
    dominators = _dominators(edges, caller_entry)
    path = _path_nodes(edges, state_push[0], key_call[0])
    interior = tuple(
        (
            rva,
            nodes[rva]["size"],
            nodes[rva]["sha256"],
            nodes[rva]["flow_kind"],
        )
        for rva in sorted(path - {state_push[0], key_call[0]})
    )
    stored = [_rva(item, f"{label}.path") for item in _array(proof.get("state_to_call_path_rvas"), f"{label}.path")]
    dominated = {node for node, values in dominators.items() if key_push[0] in values}
    atlas_entries, declared_entries = _entry_audit(program_facts, functions, caller_entry, dominated)
    if (
        state_push[0] != key_push[0] + key_push[1]
        or proof.get("key_push_dominates_call") is not True
        or proof.get("state_push_dominates_call") is not True
        or key_push[0] not in dominators.get(key_call[0], set())
        or state_push[0] not in dominators.get(key_call[0], set())
        or stored != sorted(path)
        or proof.get("state_to_call_path_node_count") != len(path)
        or proof.get("interior_esp_writers") != []
        or any(nodes[rva]["writes_esp"] for rva in path - {state_push[0], key_call[0]})
        or interior != _DEFERRED_ARGUMENT_INTERIOR
        or proof.get("alternate_atlas_entry_rvas") != atlas_entries
        or proof.get("declared_direct_call_entries") != declared_entries
        or atlas_entries
        or declared_entries
    ):
        raise NativeLuaCClosureTableKeyProvenanceError(f"{label} deferred proof differs")


def build_native_lua_cclosure_table_key_provenance_census(
    executable: Path,
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build exact key provenance for all direct and staged setter publications."""
    for value, label in (
        (direct_calls, "direct_calls"),
        (callback_census, "callback_census"),
        (setfield_publications, "setfield_publications"),
        (direct_table_setter_publications, "direct_table_setter_publications"),
        (indirect_settable_publications, "indirect_settable_publications"),
        (program_facts, "program_facts"),
        (inventory, "inventory"),
    ):
        _validate_json_tree(value, label)
    if direct_calls.get("analysis_kind") != DIRECT_CALL_ANALYSIS_KIND:
        raise NativeLuaCClosureTableKeyProvenanceError("direct-call prerequisite has wrong kind")
    try:
        prerequisite = validate_native_lua_cclosure_indirect_settable_publication_census(
            executable,
            indirect_settable_publications,
            direct_calls,
            callback_census,
            setfield_publications,
            direct_table_setter_publications,
            program_facts,
            inventory=inventory,
        )
        data, image, executable_sha256 = _load_executable(executable)
        decoder, _call_id = _decoder()
        decoder.detail = True
        import capstone
        import capstone.x86_const as x86
    except (
        NativeLuaCClosureIndirectSettablePublicationError,
        NativeLuaDirectCallError,
        PEAnchorError,
    ) as exc:
        raise NativeLuaCClosureTableKeyProvenanceError(
            f"publication prerequisite failed exact verification: {exc}"
        ) from exc
    identity = _mapping(indirect_settable_publications.get("build_identity"), "indirect build identity")
    if (
        prerequisite.get("status") != "verified"
        or prerequisite.get("evidence_sha256") != _canonical_sha256(indirect_settable_publications)
        or identity.get("executable_sha256") != executable_sha256
        or identity.get("executable_size") != len(data)
        or identity.get("architecture") != image.architecture
    ):
        raise NativeLuaCClosureTableKeyProvenanceError("executable identity changed after verification")

    imports = _imports(direct_calls)
    calls = _direct_calls(direct_calls)
    functions = _atlas_functions(program_facts)
    sources: list[tuple[str, Mapping[str, Any]]] = []
    for raw in _array(direct_table_setter_publications.get("publications"), "direct publications"):
        sources.append(("direct", _mapping(raw, "direct publication")))
    for raw in _array(indirect_settable_publications.get("publications"), "indirect publications"):
        sources.append(("staged_indirect", _mapping(raw, "indirect publication")))
    sources.sort(key=lambda pair: _rva(pair[1].get("callback_call_rva"), "callback call"))
    calls_seen = [_rva(item.get("callback_call_rva"), "callback call") for _, item in sources]
    if not calls_seen or len(set(calls_seen)) != len(calls_seen):
        raise NativeLuaCClosureTableKeyProvenanceError("setter publication sites are not a unique union")

    grouped: dict[tuple[int, int, int], list[tuple[str, Mapping[str, Any]]]] = defaultdict(list)
    for source_kind, source in sources:
        caller_entry = _rva(source.get("caller_entry_rva"), "caller entry")
        caller = functions.get(caller_entry)
        if caller is None:
            raise NativeLuaCClosureTableKeyProvenanceError("publication caller is absent from atlas")
        caller_range = _containing_range(caller, _rva(source.get("callback_call_rva"), "callback call"))
        grouped[(caller_entry, caller_range[0], caller_range[1])].append((source_kind, source))

    decoded_by_group: dict[tuple[int, int, int], list[Any]] = {}
    graph_by_group: dict[tuple[int, int, int], dict[str, Any]] = {}
    control_flow_graphs: list[dict[str, Any]] = []
    for group in sorted(grouped):
        caller_entry, start, size = group
        instructions = _decode_range(data, image, start, size, decoder)
        graph = _enhanced_cfg(instructions, image.image_base, (start, size), capstone, x86)
        graph["caller_entry_rva"] = _hex(caller_entry)
        decoded_by_group[group] = instructions
        graph_by_group[group] = graph
        control_flow_graphs.append(graph)

    publications: list[dict[str, Any]] = []
    for source_kind, source in sources:
        caller_entry_text = source["caller_entry_rva"]
        caller_entry = _rva(caller_entry_text, "caller entry")
        caller = functions[caller_entry]
        caller_range = _containing_range(caller, _rva(source["callback_call_rva"], "callback call"))
        group = (caller_entry, caller_range[0], caller_range[1])
        instructions = decoded_by_group[group]
        graph = graph_by_group[group]
        index_by_rva = {instruction.address - image.image_base: index for index, instruction in enumerate(instructions)}
        callback_rva = _rva(source["callback_call_rva"], "callback call")
        callback_index = index_by_rva.get(callback_rva)
        if callback_index is None:
            raise NativeLuaCClosureTableKeyProvenanceError("callback call is not decoded")
        callback = instructions[callback_index]
        state = instructions[callback_index - 1]
        state_bytes = bytes(state.bytes)
        if len(state_bytes) != 1 or state_bytes[0] not in {0x53, 0x55, 0x56, 0x57}:
            raise NativeLuaCClosureTableKeyProvenanceError("callback state is not one nonvolatile register push")
        zero_guard: dict[str, Any] | None = None
        deferred: dict[str, Any] | None = None
        alternate: dict[str, Any] | None = None
        upvalues: list[dict[str, Any]] = []

        count_kind = source.get("upvalue_argument_kind")
        count = source.get("literal_upvalue_count")
        if count_kind == "register":
            family = FAMILY_GUARDED_ZERO
            key_index = callback_index - 6
            key_push, key_state, key_call, count_push = instructions[key_index : key_index + 4]
            _require_bytes(count_push, b"\x56", "guarded closure count")
            zero_guard = _zero_guard_proof(
                callback_rva=callback_rva,
                graph=graph,
                instructions=instructions,
                image_base=image.image_base,
                x86=x86,
            )
            effective_count = 0
        elif count_kind == "immediate" and count == 0:
            family = FAMILY_STRAIGHT_ZERO
            key_index = callback_index - 6
            key_push, key_state, key_call, count_push = instructions[key_index : key_index + 4]
            _require_bytes(count_push, b"\x6a\x00", "zero closure count")
            effective_count = 0
        elif count_kind == "immediate" and count == 2:
            _require_bytes(instructions[callback_index - 3], b"\x6a\x02", "two-upvalue closure count")
            direct_key_index = callback_index - 12
            direct_key = instructions[direct_key_index : callback_index - 3]
            if len(direct_key) == 9 and bytes(direct_key[2].bytes) == _call_bytes(image.image_base, imports["lua_pushstring"]):
                family = FAMILY_DIRECT_TWO
                key_index = direct_key_index
                key_push, key_state, key_call = direct_key[:3]
                _require_direct_call(key_call, "lua_pushstring", imports, calls, image.image_base, caller_entry_text, "key pushstring")
                _require_bytes(direct_key[3], b"\x6a\x01", "first pushvalue index")
                _require_bytes(direct_key[6], b"\x6a\xfd", "second pushvalue index")
                upvalues = [
                    _upvalue_producer(
                        argument=direct_key[3], state=direct_key[4], call=direct_key[5],
                        api_name="lua_pushvalue", state_bytes=state_bytes, graph=graph,
                        instructions=instructions, image_base=image.image_base, imports=imports,
                        calls=calls, program_facts=program_facts, functions=functions,
                        caller_entry=caller_entry, caller_entry_text=caller_entry_text,
                        register_call=True,
                    ),
                    _upvalue_producer(
                        argument=direct_key[6], state=direct_key[7], call=direct_key[8],
                        api_name="lua_pushvalue", state_bytes=state_bytes, graph=graph,
                        instructions=instructions, image_base=image.image_base, imports=imports,
                        calls=calls, program_facts=program_facts, functions=functions,
                        caller_entry=caller_entry, caller_entry_text=caller_entry_text,
                        register_call=True,
                    ),
                ]
            else:
                family = FAMILY_DEFERRED_TWO
                key_call_index = callback_index - 10
                key_call = instructions[key_call_index]
                mixed = instructions[key_call_index + 1 : callback_index - 3]
                if len(mixed) != 6:
                    raise NativeLuaCClosureTableKeyProvenanceError("deferred two-upvalue tail differs")
                first_arg, first_state, first_call, second_arg, second_state, second_call = mixed
                _require_bytes(first_arg, b"\x56", "lightuserdata upvalue argument")
                _require_bytes(second_arg, _push_i32(-10004), "pushvalue upvalue index")
                upvalues = [
                    _upvalue_producer(
                        argument=first_arg, state=first_state, call=first_call,
                        api_name="lua_pushlightuserdata", state_bytes=state_bytes, graph=graph,
                        instructions=instructions, image_base=image.image_base, imports=imports,
                        calls=calls, program_facts=program_facts, functions=functions,
                        caller_entry=caller_entry, caller_entry_text=caller_entry_text,
                        register_call=False,
                    ),
                    _upvalue_producer(
                        argument=second_arg, state=second_state, call=second_call,
                        api_name="lua_pushvalue", state_bytes=state_bytes, graph=graph,
                        instructions=instructions, image_base=image.image_base, imports=imports,
                        calls=calls, program_facts=program_facts, functions=functions,
                        caller_entry=caller_entry, caller_entry_text=caller_entry_text,
                        register_call=False,
                    ),
                ]
                nodes, edges, decoded = _graph_instruction_maps(graph, instructions, image.image_base)
                incoming = [rva for rva, successors in edges.items() if key_call.address - image.image_base in successors]
                if len(incoming) != 1:
                    raise NativeLuaCClosureTableKeyProvenanceError("deferred key call has another entry")
                branch_index = index_by_rva[incoming[0]]
                key_index = branch_index - 5
                key_push, key_state = instructions[key_index : key_index + 2]
                deferred = _deferred_argument_proof(
                    key_push=key_push, state_push=key_state, key_call=key_call,
                    graph=graph, instructions=instructions, image_base=image.image_base,
                    program_facts=program_facts, functions=functions, caller_entry=caller_entry,
                )
                alternate = _alternate_clear(
                    key_call_index=key_call_index, instructions=instructions,
                    state_bytes=state_bytes, graph=graph, image_base=image.image_base,
                    imports=imports, calls=calls, program_facts=program_facts,
                    functions=functions, caller_entry=caller_entry,
                    caller_entry_text=caller_entry_text,
                    capstone_module=capstone,
                )
            effective_count = 2
        else:
            raise NativeLuaCClosureTableKeyProvenanceError("publication has unsupported upvalue grammar")

        _require_bytes(key_state, state_bytes, "key Lua state")
        key_literal = _read_key_literal(data, image, key_push)
        if bytes(key_call.bytes) == CALL_EBX:
            key_api_proof = _register_api_proof(
                api_name="lua_pushstring", call_instruction=key_call, graph=graph,
                instructions=instructions, image_base=image.image_base, imports=imports,
                program_facts=program_facts, functions=functions, caller_entry=caller_entry,
            )
            key_call_form = "staged_ebx"
        else:
            _require_direct_call(key_call, "lua_pushstring", imports, calls, image.image_base, caller_entry_text, "key pushstring")
            key_api_proof = None
            key_call_form = "direct_ff15"

        table_index = source.get("table_index")
        if table_index == LUA_GLOBALSINDEX:
            destination = {
                "class": "lua51_global_environment_pseudo_index",
                "lua_table_index": LUA_GLOBALSINDEX,
                "abi_constant": "LUA_GLOBALSINDEX",
                "stable_export_claimed": False,
            }
        elif table_index == -3:
            destination = _fresh_table_destination(
                key_index=key_index,
                instructions=instructions,
                state_bytes=state_bytes,
                zero_guard=zero_guard,
                image_base=image.image_base,
                imports=imports,
                calls=calls,
                caller_entry_text=caller_entry_text,
            )
        else:
            raise NativeLuaCClosureTableKeyProvenanceError("publication has unsupported destination index")

        publication = {
            "source_publication_kind": source_kind,
            "caller_entry_rva": source["caller_entry_rva"],
            "caller_atlas_record_sha256": source["caller_atlas_record_sha256"],
            "callback_call_rva": source["callback_call_rva"],
            "callback_entry_rva": source["callback_entry_rva"],
            "callback_atlas_record_sha256": source["callback_atlas_record_sha256"],
            "setter_import_name": source["setter_import_name"],
            "setter_call_rva": source["setter_call_rva"],
            "table_index": table_index,
            "grammar_family": family,
            "key": key_literal,
            "key_pointer_push": _instruction_fact(key_push, image.image_base),
            "key_state_push": _instruction_fact(key_state, image.image_base),
            "key_call": _instruction_fact(key_call, image.image_base),
            "key_call_form": key_call_form,
            "key_register_api_proof": key_api_proof,
            "closure_effective_upvalue_count": effective_count,
            "upvalue_producers": upvalues,
            "zero_guard_proof": zero_guard,
            "deferred_argument_proof": deferred,
            "destination": destination,
            "alternate_global_clear": alternate,
            "vm_stack_trace": {
                "after_key": ["K"],
                "before_closure": ["K"] + [f"U{index + 1}" for index in range(effective_count)],
                "after_closure": ["K", "C"],
                "setter_consumes": ["K", "C"],
            },
        }
        publications.append(publication)

    literals, keys = _aggregates(publications)
    family_counts = Counter(item["grammar_family"] for item in publications)
    destination_counts = Counter(item["destination"]["class"] for item in publications)
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(identity),
        "atlas": {
            "analysis_kind": program_facts.get("analysis_kind"),
            "canonical_sha256": _canonical_sha256(program_facts),
            "function_count": _mapping(program_facts.get("summary"), "atlas summary").get("function_count"),
        },
        "direct_call_census": _source_identity(direct_calls, DIRECT_CALL_ANALYSIS_KIND),
        "callback_census": _source_identity(callback_census, CALLBACK_ANALYSIS_KIND),
        "setfield_publication_census": _source_identity(
            setfield_publications, SETFIELD_ANALYSIS_KIND
        ),
        "direct_table_setter_publication_census": _source_identity(direct_table_setter_publications, DIRECT_ANALYSIS_KIND),
        "indirect_settable_publication_census": _source_identity(indirect_settable_publications, INDIRECT_ANALYSIS_KIND),
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "detail": True,
            "cfg_register_write_fields": ["writes_ebx", "writes_esi", "writes_esp"],
        },
        "lua51_abi": {
            "library": LUA_LIBRARY,
            "globals_index": LUA_GLOBALSINDEX,
            "globals_index_name": "LUA_GLOBALSINDEX",
            "cdecl_nonvolatile_register": "ebx",
        },
        "control_flow_graphs": control_flow_graphs,
        "publications": publications,
        "key_literals": literals,
        "keys": keys,
        "method": _METHOD,
        "summary": {
            "table_setter_publication_sites": len(publications),
            "direct_publication_sites": sum(item["source_publication_kind"] == "direct" for item in publications),
            "staged_indirect_publication_sites": sum(item["source_publication_kind"] == "staged_indirect" for item in publications),
            "unique_key_literals": len(literals),
            "global_environment_destinations": destination_counts["lua51_global_environment_pseudo_index"],
            "fresh_unnamed_table_destinations": destination_counts["fresh_unnamed_table_at_relative_index_minus_3"],
            "alternate_global_clear_sites": sum(item["alternate_global_clear"] is not None for item in publications),
            "grammar_family_counts": [
                {"grammar_family": family, "publication_sites": family_counts[family]}
                for family in sorted(family_counts)
            ],
            "schema_violations": 0,
        },
    }
    _assert_publication_safe(result)
    return result


def validate_native_lua_cclosure_table_key_provenance_structure(
    evidence: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate identities, partitions, aggregates, and CFG proofs without a PE."""
    for value, label in (
        (evidence, "evidence"),
        (direct_calls, "direct_calls"),
        (callback_census, "callback_census"),
        (setfield_publications, "setfield_publications"),
        (direct_table_setter_publications, "direct_table_setter_publications"),
        (indirect_settable_publications, "indirect_settable_publications"),
        (program_facts, "program_facts"),
    ):
        _validate_json_tree(value, label)
    try:
        prerequisite = validate_native_lua_cclosure_indirect_settable_publication_structure(
            indirect_settable_publications,
            direct_calls,
            callback_census,
            setfield_publications,
            direct_table_setter_publications,
            program_facts,
        )
    except NativeLuaCClosureIndirectSettablePublicationError as exc:
        raise NativeLuaCClosureTableKeyProvenanceError(
            f"indirect-settable structural prerequisite failed: {exc}"
        ) from exc
    if prerequisite.get("analysis_kind") != INDIRECT_STRUCTURE_VERIFICATION_KIND:
        raise NativeLuaCClosureTableKeyProvenanceError("structural prerequisite returned another kind")
    top_keys = {
        "schema_version", "analysis_kind", "build_identity", "atlas",
        "direct_call_census", "callback_census", "setfield_publication_census",
        "direct_table_setter_publication_census",
        "indirect_settable_publication_census", "decoder", "lua51_abi",
        "control_flow_graphs", "publications", "key_literals", "keys", "method", "summary",
    }
    _exact_keys(evidence, top_keys, "evidence")
    if evidence.get("schema_version") != SCHEMA_VERSION or evidence.get("analysis_kind") != ANALYSIS_KIND:
        raise NativeLuaCClosureTableKeyProvenanceError("unsupported key-provenance schema")
    identity = _mapping(program_facts.get("identity"), "program_facts.identity")
    if evidence.get("build_identity") != dict(identity):
        raise NativeLuaCClosureTableKeyProvenanceError("build identity differs")
    expected_sources = {
        "direct_call_census": _source_identity(direct_calls, DIRECT_CALL_ANALYSIS_KIND),
        "callback_census": _source_identity(callback_census, CALLBACK_ANALYSIS_KIND),
        "setfield_publication_census": _source_identity(
            setfield_publications, SETFIELD_ANALYSIS_KIND
        ),
        "direct_table_setter_publication_census": _source_identity(direct_table_setter_publications, DIRECT_ANALYSIS_KIND),
        "indirect_settable_publication_census": _source_identity(indirect_settable_publications, INDIRECT_ANALYSIS_KIND),
    }
    for key, expected in expected_sources.items():
        if evidence.get(key) != expected:
            raise NativeLuaCClosureTableKeyProvenanceError(f"{key} identity differs")
    if _canonical_bytes(evidence.get("method")) != _canonical_bytes(_METHOD):
        raise NativeLuaCClosureTableKeyProvenanceError("method contract drifted")
    functions = _atlas_functions(program_facts)
    graphs = _validated_graphs(evidence, functions)
    api_imports = _imports(direct_calls)
    image_base = _rva(
        _mapping(program_facts.get("ghidra"), "program_facts.ghidra").get("image_base"),
        "program_facts.ghidra.image_base",
    )
    expected_atlas = {
        "analysis_kind": program_facts.get("analysis_kind"),
        "canonical_sha256": _canonical_sha256(program_facts),
        "function_count": _mapping(program_facts.get("summary"), "atlas summary").get("function_count"),
    }
    if evidence.get("atlas") != expected_atlas:
        raise NativeLuaCClosureTableKeyProvenanceError("atlas identity differs")
    expected_decoder = {
        "name": "capstone",
        "version": SUPPORTED_CAPSTONE_VERSION,
        "architecture": "x86",
        "mode_bits": 32,
        "detail": True,
        "cfg_register_write_fields": ["writes_ebx", "writes_esi", "writes_esp"],
    }
    expected_abi = {
        "library": LUA_LIBRARY,
        "globals_index": LUA_GLOBALSINDEX,
        "globals_index_name": "LUA_GLOBALSINDEX",
        "cdecl_nonvolatile_register": "ebx",
    }
    if evidence.get("decoder") != expected_decoder or evidence.get("lua51_abi") != expected_abi:
        raise NativeLuaCClosureTableKeyProvenanceError("decoder or Lua ABI contract differs")
    expected_sites: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for source_kind, document in (
        ("direct", direct_table_setter_publications),
        ("staged_indirect", indirect_settable_publications),
    ):
        for raw in _array(document.get("publications"), "publication prerequisite"):
            source = _mapping(raw, "publication source")
            call = source["callback_call_rva"]
            if call in expected_sites:
                raise NativeLuaCClosureTableKeyProvenanceError("prerequisites overlap")
            expected_sites[call] = (source_kind, source)
    publications = [_mapping(raw, "evidence publication") for raw in _array(evidence.get("publications"), "evidence.publications")]
    if [item.get("callback_call_rva") for item in publications] != sorted(expected_sites, key=lambda item: _rva(item, "callback call")):
        raise NativeLuaCClosureTableKeyProvenanceError("publication union is not a complete ordered partition")
    publication_keys = {
        "source_publication_kind", "caller_entry_rva", "caller_atlas_record_sha256",
        "callback_call_rva", "callback_entry_rva", "callback_atlas_record_sha256",
        "setter_import_name", "setter_call_rva", "table_index", "grammar_family",
        "key", "key_pointer_push", "key_state_push", "key_call", "key_call_form",
        "key_register_api_proof", "closure_effective_upvalue_count", "upvalue_producers",
        "zero_guard_proof", "deferred_argument_proof", "destination",
        "alternate_global_clear", "vm_stack_trace",
    }
    for item in publications:
        _exact_keys(item, publication_keys, "evidence publication")
        expected_source_kind, source = expected_sites[item["callback_call_rva"]]
        if item.get("source_publication_kind") != expected_source_kind:
            raise NativeLuaCClosureTableKeyProvenanceError(
                "publication source-kind classification differs"
            )
        for key in (
            "caller_entry_rva", "caller_atlas_record_sha256", "callback_entry_rva",
            "callback_atlas_record_sha256", "setter_import_name", "setter_call_rva", "table_index",
        ):
            if item.get(key) != source.get(key):
                raise NativeLuaCClosureTableKeyProvenanceError(f"publication {key} differs from prerequisite")
        caller_entry = _rva(item.get("caller_entry_rva"), "publication caller")
        graph_data = graphs.get(caller_entry)
        if graph_data is None:
            raise NativeLuaCClosureTableKeyProvenanceError("publication lacks its caller CFG")
        _graph, nodes, _edges = graph_data
        key = _mapping(item.get("key"), "publication.key")
        _exact_keys(
            key,
            {"text", "rva", "byte_length_excluding_nul", "nul_terminated_bytes_sha256", "section_name", "section_rva", "section_characteristics", "section_writable"},
            "publication.key",
        )
        text = key.get("text")
        literal_rva = _rva(key.get("rva"), "key.rva")
        section_rva = _rva(key.get("section_rva"), "key.section_rva")
        section_characteristics = _rva(
            key.get("section_characteristics"), "key.section_characteristics"
        )
        section_name = key.get("section_name")
        if (
            type(text) is not str or not text or len(text) > MAX_KEY_BYTES
            or any(ord(char) < 0x20 or ord(char) > 0x7E for char in text)
            or key.get("byte_length_excluding_nul") != len(text.encode("ascii"))
            or key.get("section_writable") is not False
            or type(section_name) is not str
            or not section_name
            or len(section_name) > 8
            or key.get("rva") != _hex(literal_rva)
            or key.get("section_rva") != _hex(section_rva)
            or key.get("section_characteristics") != _hex(section_characteristics)
            or section_characteristics & PE_SECTION_WRITABLE
            or literal_rva < section_rva
            or key.get("nul_terminated_bytes_sha256") != hashlib.sha256(text.encode("ascii") + b"\0").hexdigest()
        ):
            raise NativeLuaCClosureTableKeyProvenanceError("key literal fields disagree")
        key_push = _fact_matches_node(item.get("key_pointer_push"), nodes, "key pointer push")
        key_state = _fact_matches_node(item.get("key_state_push"), nodes, "key state push")
        key_call = _fact_matches_node(item.get("key_call"), nodes, "key call")
        key_rva = _rva(key.get("rva"), "key.rva")
        if (
            key_push[1:] != (
                5,
                _instruction_sha256(b"\x68" + struct.pack("<I", image_base + key_rva)),
            )
            or key_state[1] != 1
            or key_state[2]
            not in {_instruction_sha256(bytes([opcode])) for opcode in (0x53, 0x55, 0x56, 0x57)}
        ):
            raise NativeLuaCClosureTableKeyProvenanceError("key native arguments do not reconstruct")
        if key_state[0] != key_push[0] + key_push[1]:
            raise NativeLuaCClosureTableKeyProvenanceError("key arguments are not contiguous")
        if item.get("key_call_form") == "staged_ebx":
            _validate_register_proof_structure(
                item.get("key_register_api_proof"),
                graph_data=graph_data,
                api_imports=api_imports,
                image_base=image_base,
                program_facts=program_facts,
                functions=functions,
                caller_entry=caller_entry,
                label="key register API proof",
            )
        elif item.get("key_call_form") == "direct_ff15":
            if (
                item.get("key_register_api_proof") is not None
                or key_call[1:]
                != (
                    6,
                    _instruction_sha256(_call_bytes(image_base, api_imports["lua_pushstring"])),
                )
            ):
                raise NativeLuaCClosureTableKeyProvenanceError("direct key-call proof differs")
        else:
            raise NativeLuaCClosureTableKeyProvenanceError("unknown key call form")
        count = item.get("closure_effective_upvalue_count")
        producers = [_mapping(raw, "upvalue producer") for raw in _array(item.get("upvalue_producers"), "upvalue producers")]
        if count not in {0, 2} or len(producers) != count:
            raise NativeLuaCClosureTableKeyProvenanceError("upvalue stack model differs")
        producer_fields = {
            "api_name", "argument_push", "state_push", "call", "call_form",
            "register_api_proof", "vm_stack_effect",
        }
        producer_facts: list[tuple[tuple[int, int, str], tuple[int, int, str], tuple[int, int, str], str]] = []
        for producer in producers:
            _exact_keys(producer, producer_fields, "upvalue producer")
            api_name = producer.get("api_name")
            producer_argument = _fact_matches_node(producer.get("argument_push"), nodes, "upvalue argument")
            producer_state = _fact_matches_node(producer.get("state_push"), nodes, "upvalue state")
            producer_call = _fact_matches_node(producer.get("call"), nodes, "upvalue call")
            if api_name not in {"lua_pushvalue", "lua_pushlightuserdata"} or producer.get("vm_stack_effect") != "push_one_upvalue":
                raise NativeLuaCClosureTableKeyProvenanceError("upvalue API semantics differ")
            if producer.get("call_form") == "staged_ebx":
                _validate_register_proof_structure(
                    producer.get("register_api_proof"),
                    graph_data=graph_data,
                    api_imports=api_imports,
                    image_base=image_base,
                    program_facts=program_facts,
                    functions=functions,
                    caller_entry=caller_entry,
                    label="upvalue register API proof",
                )
            elif producer.get("call_form") == "direct_ff15":
                if (
                    producer.get("register_api_proof") is not None
                    or producer_call[1:]
                    != (6, _instruction_sha256(_call_bytes(image_base, api_imports[api_name])))
                ):
                    raise NativeLuaCClosureTableKeyProvenanceError("direct upvalue call differs")
            else:
                raise NativeLuaCClosureTableKeyProvenanceError("unknown upvalue call form")
            if (
                producer_state[0] != producer_argument[0] + producer_argument[1]
                or producer_call[0] != producer_state[0] + producer_state[1]
                or producer_state[1:] != key_state[1:]
            ):
                raise NativeLuaCClosureTableKeyProvenanceError(
                    "upvalue producer native arguments are not contiguous or same-state"
                )
            producer_facts.append(
                (producer_argument, producer_state, producer_call, api_name)
            )
        expected_trace = {
            "after_key": ["K"],
            "before_closure": ["K"] + [f"U{index + 1}" for index in range(count)],
            "after_closure": ["K", "C"],
            "setter_consumes": ["K", "C"],
        }
        if item.get("vm_stack_trace") != expected_trace:
            raise NativeLuaCClosureTableKeyProvenanceError("VM stack trace differs")
        family = item.get("grammar_family")
        callback_rva = _rva(item.get("callback_call_rva"), "callback call")
        ordered_nodes = sorted(nodes)
        callback_position = ordered_nodes.index(callback_rva)
        if callback_position < 3:
            raise NativeLuaCClosureTableKeyProvenanceError("callback lacks native argument tail")
        count_node = nodes[ordered_nodes[callback_position - 3]]
        callback_state_node = nodes[ordered_nodes[callback_position - 1]]
        if callback_state_node.get("size") != key_state[1] or callback_state_node.get("sha256") != key_state[2]:
            raise NativeLuaCClosureTableKeyProvenanceError("closure and key use different Lua states")
        if family == FAMILY_GUARDED_ZERO:
            if count != 0 or item.get("deferred_argument_proof") is not None or item.get("alternate_global_clear") is not None:
                raise NativeLuaCClosureTableKeyProvenanceError("guarded family fields differ")
            _validate_zero_guard_structure(
                item.get("zero_guard_proof"),
                graph_data=graph_data,
                caller_entry=caller_entry,
                callback_rva=_rva(item.get("callback_call_rva"), "callback call"),
                label="zero guard proof",
            )
            if (count_node.get("size"), count_node.get("sha256")) != (
                1,
                _instruction_sha256(b"\x56"),
            ) or key_call[0] != key_state[0] + key_state[1]:
                raise NativeLuaCClosureTableKeyProvenanceError("guarded zero count tail differs")
        elif family == FAMILY_DEFERRED_TWO:
            if count != 2 or item.get("zero_guard_proof") is not None or item.get("alternate_global_clear") is None:
                raise NativeLuaCClosureTableKeyProvenanceError("deferred family fields differ")
            _validate_deferred_structure(
                item.get("deferred_argument_proof"),
                graph_data=graph_data,
                caller_entry=caller_entry,
                key_push=key_push,
                state_push=key_state,
                key_call=key_call,
                program_facts=program_facts,
                functions=functions,
                label="deferred argument proof",
            )
            alternate = _mapping(item.get("alternate_global_clear"), "alternate clear")
            alternate_fields = {
                "condition_branch", "key_call", "key_register_api_proof",
                "nil_state_push", "nil_call", "table_index", "table_index_push",
                "setter_state_push", "setter_call", "native_cleanup",
                "branch_around_publication", "effect_under_lua51_api_premise",
            }
            _exact_keys(alternate, alternate_fields, "alternate clear")
            condition = _fact_matches_node(alternate.get("condition_branch"), nodes, "alternate condition")
            alternate_key_call = _fact_matches_node(alternate.get("key_call"), nodes, "alternate key call")
            nil_state = _fact_matches_node(alternate.get("nil_state_push"), nodes, "alternate nil state")
            nil_call = _fact_matches_node(alternate.get("nil_call"), nodes, "alternate nil call")
            alternate_index = _fact_matches_node(alternate.get("table_index_push"), nodes, "alternate table index")
            alternate_state = _fact_matches_node(alternate.get("setter_state_push"), nodes, "alternate setter state")
            alternate_setter = _fact_matches_node(alternate.get("setter_call"), nodes, "alternate setter call")
            alternate_cleanup = _fact_matches_node(alternate.get("native_cleanup"), nodes, "alternate cleanup")
            around = _fact_matches_node(alternate.get("branch_around_publication"), nodes, "alternate branch around")
            _validate_register_proof_structure(
                alternate.get("key_register_api_proof"),
                graph_data=graph_data,
                api_imports=api_imports,
                image_base=image_base,
                program_facts=program_facts,
                functions=functions,
                caller_entry=caller_entry,
                label="alternate key register API proof",
            )
            alternate_proof_call = _instruction_structure(
                _mapping(alternate.get("key_register_api_proof"), "alternate proof").get("call"),
                "alternate proof call",
            )
            _graph, _nodes, edges = graph_data
            around_successors = edges.get(around[0], set())
            if (
                alternate.get("table_index") != LUA_GLOBALSINDEX
                or alternate.get("effect_under_lua51_api_premise")
                != "globals[key] receives nil on alternate arm"
                or alternate_proof_call != alternate_key_call
                or edges.get(condition[0]) != {alternate_key_call[0], key_call[0]}
                or nil_state[0] != alternate_key_call[0] + alternate_key_call[1]
                or nil_state[1:] != key_state[1:]
                or nil_call[0] != nil_state[0] + nil_state[1]
                or nil_call[1:]
                != (6, _instruction_sha256(_call_bytes(image_base, api_imports["lua_pushnil"])))
                or alternate_index[0] != nil_call[0] + nil_call[1]
                or alternate_index[1:]
                != (5, _instruction_sha256(_push_i32(LUA_GLOBALSINDEX)))
                or alternate_state[0] != alternate_index[0] + alternate_index[1]
                or alternate_state[1:] != key_state[1:]
                or alternate_setter[0] != alternate_state[0] + alternate_state[1]
                or alternate_setter[1:]
                != (6, _instruction_sha256(_call_bytes(image_base, api_imports["lua_settable"])))
                or alternate_cleanup[0] != alternate_setter[0] + alternate_setter[1]
                or around[0] != alternate_cleanup[0] + alternate_cleanup[1]
                or nodes[condition[0]].get("flow_kind") != "direct_conditional_branch"
                or nodes[around[0]].get("flow_kind") != "direct_unconditional_branch"
                or len(around_successors) != 1
                or key_call[0] in _reachable(edges, next(iter(around_successors), -1))
            ):
                raise NativeLuaCClosureTableKeyProvenanceError("alternate clear semantics differ")
            if (
                (count_node.get("size"), count_node.get("sha256"))
                != (2, _instruction_sha256(b"\x6a\x02"))
                or [fact[3] for fact in producer_facts]
                != ["lua_pushlightuserdata", "lua_pushvalue"]
                or producer_facts[0][0][1:] != (1, _instruction_sha256(b"\x56"))
                or producer_facts[1][0][1:]
                != (5, _instruction_sha256(_push_i32(-10004)))
                or producer_facts[0][0][0] != key_call[0] + key_call[1]
                or producer_facts[1][0][0]
                != producer_facts[0][2][0] + producer_facts[0][2][1]
            ):
                raise NativeLuaCClosureTableKeyProvenanceError("deferred upvalue chain differs")
        elif family in {FAMILY_STRAIGHT_ZERO, FAMILY_DIRECT_TWO}:
            expected_count = 0 if family == FAMILY_STRAIGHT_ZERO else 2
            if (
                count != expected_count
                or item.get("zero_guard_proof") is not None
                or item.get("deferred_argument_proof") is not None
                or item.get("alternate_global_clear") is not None
            ):
                raise NativeLuaCClosureTableKeyProvenanceError("straight family fields differ")
            if key_call[0] != key_state[0] + key_state[1]:
                raise NativeLuaCClosureTableKeyProvenanceError("straight key call is not contiguous")
            expected_count_bytes = b"\x6a\x00" if expected_count == 0 else b"\x6a\x02"
            if (count_node.get("size"), count_node.get("sha256")) != (
                len(expected_count_bytes),
                _instruction_sha256(expected_count_bytes),
            ):
                raise NativeLuaCClosureTableKeyProvenanceError("literal closure count differs")
            if family == FAMILY_DIRECT_TWO and (
                [fact[3] for fact in producer_facts] != ["lua_pushvalue", "lua_pushvalue"]
                or producer_facts[0][0][1:] != (2, _instruction_sha256(b"\x6a\x01"))
                or producer_facts[1][0][1:] != (2, _instruction_sha256(b"\x6a\xfd"))
                or producer_facts[0][0][0] != key_call[0] + key_call[1]
                or producer_facts[1][0][0]
                != producer_facts[0][2][0] + producer_facts[0][2][1]
            ):
                raise NativeLuaCClosureTableKeyProvenanceError("two-pushvalue chain differs")
        else:
            raise NativeLuaCClosureTableKeyProvenanceError("unknown grammar family")
        destination = _mapping(item.get("destination"), "publication.destination")
        if item["table_index"] == LUA_GLOBALSINDEX:
            _exact_keys(
                destination,
                {"class", "lua_table_index", "abi_constant", "stable_export_claimed"},
                "publication.destination",
            )
            if (
                destination.get("class") != "lua51_global_environment_pseudo_index"
                or destination.get("lua_table_index") != LUA_GLOBALSINDEX
                or destination.get("abi_constant") != "LUA_GLOBALSINDEX"
                or destination.get("stable_export_claimed") is not False
            ):
                raise NativeLuaCClosureTableKeyProvenanceError("global destination overclaims")
        elif item["table_index"] == -3:
            fresh_fields = {
                "class", "lua_table_index", "creator_api", "creator_call",
                "array_size_push", "hash_size_push", "size_argument_proof",
                "state_push", "native_argument_interior", "native_argument_cleanup",
                "semantic_table_identity",
            }
            _exact_keys(destination, fresh_fields, "publication.destination")
            creator = _fact_matches_node(destination.get("creator_call"), nodes, "fresh-table creator")
            array_push = _fact_matches_node(destination.get("array_size_push"), nodes, "fresh-table array size")
            hash_push = _fact_matches_node(destination.get("hash_size_push"), nodes, "fresh-table hash size")
            table_state = _fact_matches_node(destination.get("state_push"), nodes, "fresh-table state")
            interior = (
                None
                if destination.get("native_argument_interior") is None
                else _fact_matches_node(destination.get("native_argument_interior"), nodes, "fresh-table interior")
            )
            cleanup = (
                None
                if destination.get("native_argument_cleanup") is None
                else _fact_matches_node(destination.get("native_argument_cleanup"), nodes, "fresh-table cleanup")
            )
            proof_kind = destination.get("size_argument_proof")
            expected_arg = (
                (2, _instruction_sha256(b"\x6a\x00"))
                if proof_kind == "immediate_zero"
                else (1, _instruction_sha256(b"\x56"))
                if proof_kind == "guarded_esi_zero"
                else None
            )
            after_state = interior[0] if interior is not None else creator[0]
            after_creator = cleanup[0] if cleanup is not None else key_push[0]
            if (
                destination.get("class") != "fresh_unnamed_table_at_relative_index_minus_3"
                or destination.get("lua_table_index") != -3
                or destination.get("creator_api") != "lua_createtable"
                or destination.get("semantic_table_identity") is not None
                or expected_arg is None
                or array_push[1:] != expected_arg
                or hash_push[1:] != expected_arg
                or hash_push[0] != array_push[0] + array_push[1]
                or table_state[0] != hash_push[0] + hash_push[1]
                or table_state[1:] != key_state[1:]
                or after_state != table_state[0] + table_state[1]
                or (interior is not None and creator[0] != interior[0] + interior[1])
                or creator[1:]
                != (
                    6,
                    _instruction_sha256(_call_bytes(image_base, api_imports["lua_createtable"])),
                )
                or after_creator != creator[0] + creator[1]
                or (cleanup is not None and key_push[0] != cleanup[0] + cleanup[1])
                or (proof_kind == "guarded_esi_zero" and family != FAMILY_GUARDED_ZERO)
            ):
                raise NativeLuaCClosureTableKeyProvenanceError("fresh table destination overclaims")
        else:
            raise NativeLuaCClosureTableKeyProvenanceError("unexpected table index")
    if set(graphs) != {_rva(item["caller_entry_rva"], "publication caller") for item in publications}:
        raise NativeLuaCClosureTableKeyProvenanceError("CFG set differs from publication callers")
    literals, keys = _aggregates(publications)
    if evidence.get("key_literals") != literals or evidence.get("keys") != keys:
        raise NativeLuaCClosureTableKeyProvenanceError("key aggregates differ")
    family_counts = Counter(item["grammar_family"] for item in publications)
    destination_counts = Counter(item["destination"]["class"] for item in publications)
    expected_summary = {
        "table_setter_publication_sites": len(publications),
        "direct_publication_sites": sum(item["source_publication_kind"] == "direct" for item in publications),
        "staged_indirect_publication_sites": sum(item["source_publication_kind"] == "staged_indirect" for item in publications),
        "unique_key_literals": len(literals),
        "global_environment_destinations": destination_counts["lua51_global_environment_pseudo_index"],
        "fresh_unnamed_table_destinations": destination_counts["fresh_unnamed_table_at_relative_index_minus_3"],
        "alternate_global_clear_sites": sum(item["alternate_global_clear"] is not None for item in publications),
        "grammar_family_counts": [
            {"grammar_family": family, "publication_sites": family_counts[family]}
            for family in sorted(family_counts)
        ],
        "schema_violations": 0,
    }
    if evidence.get("summary") != expected_summary:
        raise NativeLuaCClosureTableKeyProvenanceError("summary differs")
    _assert_publication_safe(evidence)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": STRUCTURE_VERIFICATION_KIND,
        "status": "structurally_verified",
        "build_identity": dict(identity),
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": dict(expected_summary),
    }


def validate_native_lua_cclosure_table_key_provenance_census(
    executable: Path,
    evidence: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    direct_table_setter_publications: Mapping[str, Any],
    indirect_settable_publications: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and canonical-byte-compare one exact key-provenance census."""
    _validate_json_tree(evidence, "evidence")
    rebuilt = build_native_lua_cclosure_table_key_provenance_census(
        executable,
        direct_calls,
        callback_census,
        setfield_publications,
        direct_table_setter_publications,
        indirect_settable_publications,
        program_facts,
        inventory=inventory,
    )
    if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
        raise NativeLuaCClosureTableKeyProvenanceError(
            "native Lua table-key evidence differs from exact rebuild"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": dict(_mapping(rebuilt["build_identity"], "build identity")),
        "evidence_sha256": _canonical_sha256(rebuilt),
        "summary": dict(_mapping(rebuilt["summary"], "summary")),
    }


def encode_native_lua_cclosure_table_key_provenance_census(
    value: Mapping[str, Any],
) -> str:
    """Return deterministic pretty JSON for an artifact or verification result."""
    _validate_json_tree(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
