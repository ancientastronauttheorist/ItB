"""Exact terminal dispositions for the residual native Lua C closures.

This deliberately finite analysis consumes only the unmatched frontier left by
the direct table-setter census.  It recognizes two reviewed return tails and
one reviewed registry-reference holder construction.  Everything else remains
explicitly unmatched.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_callbacks import (
    ANALYSIS_KIND as CALLBACK_ANALYSIS_KIND,
    NativeLuaCClosureError,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError,
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
    ANALYSIS_KIND as TABLE_SETTER_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as TABLE_SETTER_STRUCTURE_VERIFICATION_KIND,
    NativeLuaCClosureTableSetterPublicationError,
    validate_native_lua_cclosure_table_setter_publication_census,
    validate_native_lua_cclosure_table_setter_publication_structure,
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
ANALYSIS_KIND = "pe_native_lua_cclosure_terminal_disposition_census"
VERIFICATION_KIND = "pe_native_lua_cclosure_terminal_disposition_census_verification"
STRUCTURE_VERIFICATION_KIND = (
    "pe_native_lua_cclosure_terminal_disposition_census_structure_verification"
)
RETURN_KIND = "lua_callback_single_result"
HOLDER_KIND = "registry_reference_holder"
UNMATCHED_RESOLUTION = "no_exact_reviewed_terminal_disposition"
LUA_LIBRARY = "lua5.1.dll"
REGISTRY_INDEX = -10000
NOREF_SENTINEL = -2
ESI_PUSH_SHA256 = _instruction_sha256(b"\x56")
EDI_PUSH_SHA256 = _instruction_sha256(b"\x57")
RETURN_EPILOGUES: dict[str, list[tuple[str, bytes]]] = {
    "simple_saved_edi_esi_ebp": [
        ("closure_argument_cleanup", b"\x83\xc4\x0c"),
        ("lua_result_count_one", b"\xb8\x01\x00\x00\x00"),
        ("restore_edi", b"\x5f"),
        ("restore_esi", b"\x5e"),
        ("restore_ebp", b"\x5d"),
        ("return", b"\xc3"),
    ],
    "seh_saved_edi_esi_ebx_frame": [
        ("closure_and_prior_argument_cleanup", b"\x83\xc4\x24"),
        ("lua_result_count_one", b"\xb8\x01\x00\x00\x00"),
        ("load_seh_predecessor", b"\x8b\x4d\xf4"),
        ("restore_seh_head", b"\x64\x89\x0d\x00\x00\x00\x00"),
        ("discard_seh_record", b"\x59"),
        ("restore_edi", b"\x5f"),
        ("restore_esi", b"\x5e"),
        ("restore_ebx", b"\x5b"),
        ("restore_frame_stack", b"\x8b\xe5"),
        ("restore_ebp", b"\x5d"),
        ("return", b"\xc3"),
    ],
}
_METHOD = {
    "table_setter_prerequisite_exactly_verified": True,
    "accepted_dispositions": (
        "A prior-unmatched immediate lua_pushcclosure site is retained only when "
        "it matches one complete reviewed x86 sequence. A single-result callback "
        "tail must be contiguous through mov eax,1 and an enumerated epilogue, and "
        "its caller must independently be an exact callback target. The registry "
        "holder must match the complete two-rawgeti upvalue, pushvalue, luaL_ref, "
        "lua_settop, holder-store, cleanup, and return sequence."
    ),
    "partition": (
        "Every site in the table-setter artifact's still-unmatched frontier occurs "
        "exactly once as a retained disposition or a still-unmatched site."
    ),
    "boundary": (
        "Published facts are normalized RVAs, finite instruction hashes, exact "
        "prerequisite joins, reviewed sequence roles, and deterministic aggregates."
    ),
    "not_claimed": [
        "runtime reachability, execution, frequency, persistence, or lifetime",
        "a Lua-visible name, global export, ordinary lookup, or table identity",
        "behavioral or source equivalence beyond the exact terminal sequence",
        "ownership, purpose, inputs, outputs, or completeness for other closure forms",
        "registry-reference validity after the reviewed constructor returns",
    ],
}


class NativeLuaCClosureTerminalDispositionError(RuntimeError):
    """Raised for invalid or stale terminal-disposition evidence."""


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _site_key(site: Mapping[str, Any], label: str) -> int:
    return _rva(site.get("callback_call_rva", site.get("call_rva")), f"{label}.callback_call_rva")


def _source_identity(table_setters: Mapping[str, Any]) -> dict[str, Any]:
    artifact = _mapping(table_setters, "table_setters")
    if artifact.get("analysis_kind") != TABLE_SETTER_ANALYSIS_KIND:
        raise NativeLuaCClosureTerminalDispositionError("table-setter prerequisite has the wrong kind")
    summary = _mapping(artifact.get("summary"), "table_setters.summary")
    return {
        "analysis_kind": TABLE_SETTER_ANALYSIS_KIND,
        "canonical_sha256": _canonical_sha256(artifact),
        "still_unmatched_resolved_callback_sites": summary.get("still_unmatched_resolved_callback_sites"),
    }


def _frontier(table_setters: Mapping[str, Any], callbacks: Mapping[str, Any]) -> tuple[dict[int, Mapping[str, Any]], dict[int, Mapping[str, Any]]]:
    resolved: dict[int, Mapping[str, Any]] = {}
    for index, raw in enumerate(_array(callbacks.get("resolved_sites"), "callbacks.resolved_sites")):
        site = _mapping(raw, f"callbacks.resolved_sites[{index}]")
        call = _rva(site.get("call_rva"), "callback call")
        if call in resolved:
            raise NativeLuaCClosureTerminalDispositionError("callback call RVAs are not unique")
        resolved[call] = site
    frontier: dict[int, Mapping[str, Any]] = {}
    previous = -1
    for index, raw in enumerate(_array(table_setters.get("still_unmatched_resolved_sites"), "table_setters.still_unmatched_resolved_sites")):
        site = _mapping(raw, f"table_setters.still_unmatched_resolved_sites[{index}]")
        call = _site_key(site, "frontier site")
        source = resolved.get(call)
        if call <= previous or call in frontier or source is None:
            raise NativeLuaCClosureTerminalDispositionError("table-setter residual frontier is not a unique ordered callback partition")
        previous = call
        for key in ("caller_entry_rva", "caller_atlas_record_sha256", "callback_entry_rva", "callback_atlas_record_sha256"):
            if site.get(key) != source.get(key):
                raise NativeLuaCClosureTerminalDispositionError("residual frontier differs from callback census")
        frontier[call] = site
    expected = _mapping(table_setters.get("summary"), "table_setters.summary").get("still_unmatched_resolved_callback_sites")
    if len(frontier) != expected:
        raise NativeLuaCClosureTerminalDispositionError("residual frontier count differs from table-setter summary")
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


def _direct_calls(direct: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]]]:
    imports: dict[str, Mapping[str, Any]] = {}
    for raw in _array(direct.get("lua_imports"), "direct.lua_imports"):
        item = _mapping(raw, "direct import")
        name = item.get("name")
        if type(name) is str and item.get("library") == LUA_LIBRARY:
            if name in imports:
                raise NativeLuaCClosureTerminalDispositionError("duplicate Lua import")
            imports[name] = item
    calls: dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    observed: Counter[str] = Counter()
    for raw_record in _array(direct.get("records"), "direct.records"):
        record = _mapping(raw_record, "direct record")
        for raw_call in _array(record.get("direct_lua_import_calls"), "direct calls"):
            call = _mapping(raw_call, "direct call")
            rva = _rva(call.get("call_rva"), "direct call RVA")
            name = call.get("import_name")
            imported = imports.get(name)
            if rva in calls or imported is None or call.get("library") != LUA_LIBRARY or call.get("call_form") != DIRECT_CALL_FORM or call.get("iat_rva") != imported.get("iat_rva"):
                raise NativeLuaCClosureTerminalDispositionError("direct Lua call facts disagree")
            calls[rva] = (record, call)
            observed[name] += 1
    for name, imported in imports.items():
        if imported.get("direct_call_sites") != observed[name]:
            raise NativeLuaCClosureTerminalDispositionError("direct Lua import aggregate disagrees")
    return imports, calls


def _call_bytes(image_base: int, imported: Mapping[str, Any]) -> bytes:
    iat = _rva(imported.get("iat_rva"), "Lua import IAT")
    if image_base + iat > 0xFFFFFFFF:
        raise NativeLuaCClosureTerminalDispositionError("Lua import VA overflows x86")
    return b"\xff\x15" + struct.pack("<I", image_base + iat)


def _registry_template(image_base: int, source: Mapping[str, Any], imports: Mapping[str, Mapping[str, Any]]) -> list[tuple[str, bytes]]:
    required = ("lua_rawgeti", "lua_pushcclosure", "lua_pushvalue", "luaL_ref", "lua_settop")
    if any(name not in imports for name in required):
        raise NativeLuaCClosureTerminalDispositionError("registry-holder Lua imports are incomplete")
    callback = _rva(source.get("callback_entry_rva"), "callback entry")
    if image_base + callback > 0xFFFFFFFF:
        raise NativeLuaCClosureTerminalDispositionError("callback VA overflows x86")
    return [
        ("first_reference_push", b"\xff\x72\x04"), ("load_state_edi", b"\x8b\x3a"),
        ("load_holder_ebx", b"\x8b\xd9"), ("first_registry_index", b"\x68\xf0\xd8\xff\xff"),
        ("first_state_push", b"\x57"), ("first_rawgeti", _call_bytes(image_base, imports["lua_rawgeti"])),
        ("load_second_reference_owner", b"\x8b\x45\x08"), ("second_reference_push", b"\xff\x70\x04"),
        ("second_registry_index", b"\x68\xf0\xd8\xff\xff"), ("second_state_push", b"\x57"),
        ("second_rawgeti", _call_bytes(image_base, imports["lua_rawgeti"])), ("upvalue_count_two", b"\x6a\x02"),
        ("callback_push", b"\x68" + struct.pack("<I", image_base + callback)), ("closure_state_push", b"\x57"),
        ("pushcclosure", _call_bytes(image_base, imports["lua_pushcclosure"])), ("top_index_minus_one", b"\x6a\xff"),
        ("pushvalue_state", b"\x57"), ("store_holder_state", b"\x89\x3b"),
        ("store_holder_noref", b"\xc7\x43\x04\xfe\xff\xff\xff"), ("pushvalue", _call_bytes(image_base, imports["lua_pushvalue"])),
        ("ref_registry_index", b"\x68\xf0\xd8\xff\xff"), ("ref_state_push", b"\x57"),
        ("luaL_ref", _call_bytes(image_base, imports["luaL_ref"])), ("settop_index_minus_two", b"\x6a\xfe"),
        ("settop_state_push", b"\x57"), ("store_holder_reference", b"\x89\x43\x04"),
        ("lua_settop", _call_bytes(image_base, imports["lua_settop"])), ("argument_cleanup", b"\x83\xc4\x3c"),
        ("return_holder", b"\x8b\xc3"), ("restore_edi", b"\x5f"), ("restore_ebx", b"\x5b"),
        ("restore_ebp", b"\x5d"), ("return", b"\xc3"),
    ]


def _match(instructions: list[Any], start: int, template: list[tuple[str, bytes]]) -> list[Any] | None:
    if start < 0 or start + len(template) > len(instructions):
        return None
    chosen = instructions[start : start + len(template)]
    for (role, expected), instruction in zip(template, chosen):
        del role
        if bytes(instruction.bytes) != expected:
            return None
    for left, right in zip(chosen, chosen[1:]):
        if left.address + left.size != right.address:
            return None
    return chosen


def _sequence(template: list[tuple[str, bytes]], instructions: list[Any], image_base: int) -> list[dict[str, Any]]:
    return [{"role": role, **_instruction_fact(ins, image_base)} for (role, _), ins in zip(template, instructions)]


def _base_disposition(source: Mapping[str, Any], kind: str) -> dict[str, Any]:
    return {
        "disposition_kind": kind,
        "caller_entry_rva": source["caller_entry_rva"],
        "caller_atlas_record_sha256": source["caller_atlas_record_sha256"],
        "callback_call_rva": source["call_rva"],
        "callback_call_instruction_sha256": source["call_instruction_sha256"],
        "callback_entry_rva": source["callback_entry_rva"],
        "callback_atlas_record_sha256": source["callback_atlas_record_sha256"],
        "upvalue_argument_kind": source["upvalue_argument_kind"],
        "literal_upvalue_count": source["literal_upvalue_count"],
    }


def _aggregates(items: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_caller: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_target: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in items:
        by_caller[item["caller_entry_rva"]].append(item)
        by_target[item["callback_entry_rva"]].append(item)
    callers = [{"caller_entry_rva": key, "caller_atlas_record_sha256": values[0]["caller_atlas_record_sha256"], "disposition_site_count": len(values), "disposition_kinds": sorted({v["disposition_kind"] for v in values}), "callback_entry_rvas": sorted({v["callback_entry_rva"] for v in values})} for key, values in sorted(by_caller.items(), key=lambda pair: _rva(pair[0], "caller"))]
    targets = [{"callback_entry_rva": key, "callback_atlas_record_sha256": values[0]["callback_atlas_record_sha256"], "disposition_site_count": len(values), "disposition_kinds": sorted({v["disposition_kind"] for v in values}), "caller_entry_rvas": sorted({v["caller_entry_rva"] for v in values})} for key, values in sorted(by_target.items(), key=lambda pair: _rva(pair[0], "target"))]
    return callers, targets


def build_native_lua_cclosure_terminal_disposition_census(
    executable: Path, direct_calls: Mapping[str, Any], callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any], table_setter_publications: Mapping[str, Any],
    program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact residual terminal-disposition census."""
    for value, label in ((direct_calls, "direct_calls"), (callback_census, "callback_census"), (setfield_publications, "setfield_publications"), (table_setter_publications, "table_setter_publications"), (program_facts, "program_facts"), (inventory, "inventory")):
        _validate_json_tree(value, label)
    try:
        prerequisite = validate_native_lua_cclosure_table_setter_publication_census(executable, table_setter_publications, direct_calls, callback_census, setfield_publications, program_facts, inventory=inventory)
        data, image, executable_sha256 = _load_executable(executable)
        decoder, _ = _decoder()
    except (NativeLuaCClosureTableSetterPublicationError, NativeLuaCClosurePublicationError, NativeLuaCClosureError, NativeLuaDirectCallError, PEAnchorError) as exc:
        raise NativeLuaCClosureTerminalDispositionError(f"table-setter prerequisite failed exact verification: {exc}") from exc
    identity = _mapping(table_setter_publications.get("build_identity"), "table_setters.build_identity")
    if identity.get("executable_sha256") != executable_sha256 or identity.get("executable_size") != len(data) or identity.get("architecture") != image.architecture or prerequisite.get("evidence_sha256") != _canonical_sha256(table_setter_publications):
        raise NativeLuaCClosureTerminalDispositionError("executable or prerequisite identity changed")
    functions = _atlas_functions(program_facts)
    resolved, frontier = _frontier(table_setter_publications, callback_census)
    imports, lua_calls = _direct_calls(direct_calls)
    callback_target_witnesses: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for source in resolved.values():
        callback_target_witnesses[_rva(source.get("callback_entry_rva"), "callback target")].append(source)
    decoded: dict[tuple[int, int], list[Any]] = {}
    dispositions: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for call_rva, frontier_site in frontier.items():
        source = resolved[call_rva]
        caller_entry = _rva(source.get("caller_entry_rva"), "caller entry")
        callback_entry = _rva(source.get("callback_entry_rva"), "callback entry")
        caller, callback = functions.get(caller_entry), functions.get(callback_entry)
        if caller is None or callback is None or callback.get("thunk") is not False or source.get("caller_atlas_record_sha256") != atlas_record_sha256(caller) or source.get("callback_atlas_record_sha256") != atlas_record_sha256(callback):
            raise NativeLuaCClosureTerminalDispositionError("frontier site does not join exact atlas records")
        caller_range = _containing_range(caller, call_rva)
        instructions = decoded.get(caller_range)
        if instructions is None:
            instructions = _decode_range(data, image, caller_range[0], caller_range[1], decoder)
            decoded[caller_range] = instructions
        index_by_rva = {ins.address - image.image_base: i for i, ins in enumerate(instructions)}
        call_index = index_by_rva.get(call_rva)
        if call_index is None or _instruction_sha256(bytes(instructions[call_index].bytes)) != source.get("call_instruction_sha256"):
            raise NativeLuaCClosureTerminalDispositionError("callback call is absent from exact caller decode")
        retained: dict[str, Any] | None = None
        witnesses = sorted(callback_target_witnesses.get(caller_entry, []), key=lambda item: _rva(item.get("call_rva"), "witness"))
        source_state = _mapping(source.get("state_push"), "callback state push")
        source_state_sha256 = source_state.get("sha256")
        source_state_size = source_state.get("size")
        if witnesses and source_state_size == 1 and source_state_sha256 == ESI_PUSH_SHA256:
            for epilogue_kind, template in RETURN_EPILOGUES.items():
                matched = _match(instructions, call_index + 1, template)
                if matched is not None:
                    witness = witnesses[0]
                    retained = _base_disposition(source, RETURN_KIND)
                    retained.update({"result_count": 1, "caller_callback_target_witness": {"construction_call_rva": witness["call_rva"], "constructor_entry_rva": witness["caller_entry_rva"], "constructor_atlas_record_sha256": witness["caller_atlas_record_sha256"], "callback_target_entry_rva": witness["callback_entry_rva"], "callback_target_atlas_record_sha256": witness["callback_atlas_record_sha256"]}, "epilogue_kind": epilogue_kind, "reviewed_sequence": _sequence(template, matched, image.image_base)})
                    break
        if retained is None and source.get("literal_upvalue_count") == 2 and source_state_size == 1 and source_state_sha256 == EDI_PUSH_SHA256:
            template = _registry_template(image.image_base, source, imports)
            matched = _match(instructions, call_index - 14, template)
            required_calls = {"first_rawgeti": "lua_rawgeti", "second_rawgeti": "lua_rawgeti", "pushcclosure": "lua_pushcclosure", "pushvalue": "lua_pushvalue", "luaL_ref": "luaL_ref", "lua_settop": "lua_settop"}
            if matched is not None:
                facts = {role: ins.address - image.image_base for (role, _), ins in zip(template, matched)}
                joins = all(facts[role] in lua_calls and lua_calls[facts[role]][0].get("entry_rva") == source.get("caller_entry_rva") and lua_calls[facts[role]][1].get("import_name") == name for role, name in required_calls.items())
                if joins:
                    retained = _base_disposition(source, HOLDER_KIND)
                    retained.update({"state_register": "edi", "holder_register": "ebx", "registry_index": REGISTRY_INDEX, "initial_reference_sentinel": NOREF_SENTINEL, "returned_register": "ebx", "reviewed_sequence": _sequence(template, matched, image.image_base)})
        if retained is None:
            unmatched.append(_unmatched(frontier_site))
        else:
            dispositions.append(retained)
    dispositions.sort(key=lambda item: _rva(item["callback_call_rva"], "disposition call"))
    unmatched.sort(key=lambda item: _rva(item["callback_call_rva"], "unmatched call"))
    callers, targets = _aggregates(dispositions)
    direct_atlas = _mapping(direct_calls.get("atlas"), "direct_calls.atlas")
    result = {
        "schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(identity),
        "atlas": {"analysis_kind": direct_atlas.get("analysis_kind"), "canonical_sha256": direct_atlas.get("canonical_sha256"), "function_count": direct_atlas.get("function_count")},
        "direct_call_census": {"analysis_kind": DIRECT_CALL_ANALYSIS_KIND, "canonical_sha256": _canonical_sha256(direct_calls)},
        "callback_census": {"analysis_kind": CALLBACK_ANALYSIS_KIND, "canonical_sha256": _canonical_sha256(callback_census)},
        "table_setter_publication_census": _source_identity(table_setter_publications),
        "decoder": {"name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION, "architecture": "x86", "mode_bits": 32, "accepted_disposition_kinds": [RETURN_KIND, HOLDER_KIND], "return_epilogue_kinds": sorted(RETURN_EPILOGUES)},
        "dispositions": dispositions, "still_unmatched_resolved_sites": unmatched,
        "callers": callers, "callback_targets": targets, "method": _METHOD,
        "summary": {"prior_unmatched_resolved_callback_sites": len(frontier), "matched_terminal_disposition_sites": len(dispositions), "still_unmatched_resolved_callback_sites": len(unmatched), "lua_callback_single_result_sites": sum(item["disposition_kind"] == RETURN_KIND for item in dispositions), "registry_reference_holder_sites": sum(item["disposition_kind"] == HOLDER_KIND for item in dispositions), "unique_disposition_callers": len(callers), "unique_disposition_callback_targets": len(targets), "schema_violations": 0},
    }
    _assert_publication_safe(result)
    return result


def validate_native_lua_cclosure_terminal_disposition_census(executable: Path, evidence: Mapping[str, Any], direct_calls: Mapping[str, Any], callback_census: Mapping[str, Any], setfield_publications: Mapping[str, Any], table_setter_publications: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    _validate_json_tree(evidence, "evidence")
    rebuilt = build_native_lua_cclosure_terminal_disposition_census(executable, direct_calls, callback_census, setfield_publications, table_setter_publications, program_facts, inventory=inventory)
    if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
        raise NativeLuaCClosureTerminalDispositionError("native Lua terminal-disposition evidence differs from exact rebuild")
    return {"schema_version": SCHEMA_VERSION, "analysis_kind": VERIFICATION_KIND, "status": "verified", "build_identity": dict(rebuilt["build_identity"]), "evidence_sha256": _canonical_sha256(rebuilt), "summary": dict(rebuilt["summary"])}


def _expected_sequence(template: list[tuple[str, bytes]], start: int) -> list[dict[str, Any]]:
    result = []
    rva = start
    for role, encoded in template:
        result.append({"role": role, "rva": _hex(rva), "size": len(encoded), "sha256": _instruction_sha256(encoded)})
        rva += len(encoded)
    return result


def _require_sequence(raw: Any, template: list[tuple[str, bytes]], start: int, caller_range: tuple[int, int], label: str) -> None:
    sequence = _array(raw, label)
    expected = _expected_sequence(template, start)
    if sequence != expected:
        raise NativeLuaCClosureTerminalDispositionError(f"{label} does not reconstruct the reviewed finite instruction sequence")
    for index, item in enumerate(sequence):
        mapped = _mapping(item, f"{label}[{index}]")
        fact = _instruction_structure(
            {key: mapped[key] for key in ("rva", "size", "sha256")},
            f"{label}[{index}]",
        )
        if fact[0] < caller_range[0] or fact[0] + fact[1] > caller_range[0] + caller_range[1]:
            raise NativeLuaCClosureTerminalDispositionError(f"{label} lies outside the caller atlas range")


def validate_native_lua_cclosure_terminal_disposition_structure(evidence: Mapping[str, Any], direct_calls: Mapping[str, Any], callback_census: Mapping[str, Any], setfield_publications: Mapping[str, Any], table_setter_publications: Mapping[str, Any], program_facts: Mapping[str, Any]) -> dict[str, Any]:
    """Validate all joins and finite hashes without loading the executable."""
    for value, label in ((evidence, "evidence"), (direct_calls, "direct_calls"), (callback_census, "callback_census"), (setfield_publications, "setfield_publications"), (table_setter_publications, "table_setter_publications"), (program_facts, "program_facts")):
        _validate_json_tree(value, label)
    try:
        prerequisite = validate_native_lua_cclosure_table_setter_publication_structure(table_setter_publications, direct_calls, callback_census, setfield_publications, program_facts)
    except NativeLuaCClosureTableSetterPublicationError as exc:
        raise NativeLuaCClosureTerminalDispositionError(f"table-setter structural prerequisite failed: {exc}") from exc
    if prerequisite.get("analysis_kind") != TABLE_SETTER_STRUCTURE_VERIFICATION_KIND or prerequisite.get("status") != "structurally_verified":
        raise NativeLuaCClosureTerminalDispositionError("table-setter structural prerequisite returned an unexpected result")
    evidence = _mapping(evidence, "evidence")
    top_keys = {"schema_version", "analysis_kind", "build_identity", "atlas", "direct_call_census", "callback_census", "table_setter_publication_census", "decoder", "dispositions", "still_unmatched_resolved_sites", "callers", "callback_targets", "method", "summary"}
    _exact_keys(evidence, top_keys, "evidence")
    if type(evidence["schema_version"]) is not int or evidence["schema_version"] != SCHEMA_VERSION or evidence["analysis_kind"] != ANALYSIS_KIND:
        raise NativeLuaCClosureTerminalDispositionError("unsupported terminal-disposition schema or analysis kind")
    facts = _mapping(program_facts, "program_facts")
    identity = _mapping(facts.get("identity"), "program_facts.identity")
    if evidence["build_identity"] != dict(identity) or any(evidence["build_identity"] != doc.get("build_identity") for doc in (direct_calls, callback_census, table_setter_publications)):
        raise NativeLuaCClosureTerminalDispositionError("build identity differs from prerequisites")
    ghidra = _mapping(facts.get("ghidra"), "program_facts.ghidra")
    image_base = _rva(ghidra.get("image_base"), "image base")
    functions = _atlas_functions(facts)
    resolved, frontier = _frontier(table_setter_publications, callback_census)
    imports, lua_calls = _direct_calls(direct_calls)
    direct_atlas = _mapping(direct_calls.get("atlas"), "direct atlas")
    expected_atlas = {"analysis_kind": direct_atlas.get("analysis_kind"), "canonical_sha256": direct_atlas.get("canonical_sha256"), "function_count": direct_atlas.get("function_count")}
    if evidence["atlas"] != expected_atlas or evidence["direct_call_census"] != {"analysis_kind": DIRECT_CALL_ANALYSIS_KIND, "canonical_sha256": _canonical_sha256(direct_calls)} or evidence["callback_census"] != {"analysis_kind": CALLBACK_ANALYSIS_KIND, "canonical_sha256": _canonical_sha256(callback_census)} or evidence["table_setter_publication_census"] != _source_identity(table_setter_publications):
        raise NativeLuaCClosureTerminalDispositionError("prerequisite identity differs")
    expected_decoder = {"name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION, "architecture": "x86", "mode_bits": 32, "accepted_disposition_kinds": [RETURN_KIND, HOLDER_KIND], "return_epilogue_kinds": sorted(RETURN_EPILOGUES)}
    if evidence["decoder"] != expected_decoder or _canonical_bytes(evidence["method"]) != _canonical_bytes(_METHOD):
        raise NativeLuaCClosureTerminalDispositionError("decoder or method contract drifted")
    common = {"disposition_kind", "caller_entry_rva", "caller_atlas_record_sha256", "callback_call_rva", "callback_call_instruction_sha256", "callback_entry_rva", "callback_atlas_record_sha256", "upvalue_argument_kind", "literal_upvalue_count", "reviewed_sequence"}
    return_extra = {"result_count", "caller_callback_target_witness", "epilogue_kind"}
    holder_extra = {"state_register", "holder_register", "registry_index", "initial_reference_sentinel", "returned_register"}
    seen: set[int] = set()
    previous = -1
    dispositions: list[Mapping[str, Any]] = []
    for index, raw in enumerate(_array(evidence["dispositions"], "evidence.dispositions")):
        label = f"evidence.dispositions[{index}]"
        item = _mapping(raw, label)
        kind = item.get("disposition_kind")
        _exact_keys(item, common | (return_extra if kind == RETURN_KIND else holder_extra if kind == HOLDER_KIND else set()), label)
        call = _site_key(item, label)
        source, frontier_site = resolved.get(call), frontier.get(call)
        if source is None or frontier_site is None or call <= previous or call in seen:
            raise NativeLuaCClosureTerminalDispositionError("dispositions are not a unique ordered frontier partition")
        previous = call; seen.add(call)
        for key in ("caller_entry_rva", "caller_atlas_record_sha256", "callback_entry_rva", "callback_atlas_record_sha256"):
            if item[key] != source.get(key) or item[key] != frontier_site.get(key):
                raise NativeLuaCClosureTerminalDispositionError(f"{label} does not join the exact residual site")
        if item["callback_call_instruction_sha256"] != source.get("call_instruction_sha256") or item["upvalue_argument_kind"] != source.get("upvalue_argument_kind") or item["literal_upvalue_count"] != source.get("literal_upvalue_count"):
            raise NativeLuaCClosureTerminalDispositionError(f"{label} callback metadata differs")
        caller = functions.get(_rva(item["caller_entry_rva"], "caller")); callback = functions.get(_rva(item["callback_entry_rva"], "callback"))
        if caller is None or callback is None or callback.get("thunk") is not False or item["caller_atlas_record_sha256"] != atlas_record_sha256(caller) or item["callback_atlas_record_sha256"] != atlas_record_sha256(callback):
            raise NativeLuaCClosureTerminalDispositionError(f"{label} atlas join differs")
        caller_range = _containing_range(caller, call)
        if kind == RETURN_KIND:
            epilogue = item.get("epilogue_kind")
            if epilogue not in RETURN_EPILOGUES or type(item.get("result_count")) is not int or item.get("result_count") != 1:
                raise NativeLuaCClosureTerminalDispositionError(f"{label} return disposition fields differ")
            source_state = _instruction_structure(source.get("state_push"), f"{label}.callback_state_push")
            if source_state != (call - 1, 1, ESI_PUSH_SHA256):
                raise NativeLuaCClosureTerminalDispositionError(f"{label} is not constructed from the reviewed ESI Lua-state form")
            _require_sequence(item["reviewed_sequence"], RETURN_EPILOGUES[epilogue], call + 6, caller_range, f"{label}.reviewed_sequence")
            witness = _mapping(item.get("caller_callback_target_witness"), f"{label}.witness")
            witness_keys = {"construction_call_rva", "constructor_entry_rva", "constructor_atlas_record_sha256", "callback_target_entry_rva", "callback_target_atlas_record_sha256"}
            _exact_keys(witness, witness_keys, f"{label}.witness")
            witness_source = resolved.get(_rva(witness.get("construction_call_rva"), "witness call"))
            if witness_source is None or witness != {"construction_call_rva": witness_source["call_rva"], "constructor_entry_rva": witness_source["caller_entry_rva"], "constructor_atlas_record_sha256": witness_source["caller_atlas_record_sha256"], "callback_target_entry_rva": witness_source["callback_entry_rva"], "callback_target_atlas_record_sha256": witness_source["callback_atlas_record_sha256"]} or witness["callback_target_entry_rva"] != item["caller_entry_rva"] or witness["callback_target_atlas_record_sha256"] != item["caller_atlas_record_sha256"]:
                raise NativeLuaCClosureTerminalDispositionError(f"{label} caller is not independently an exact callback target")
        else:
            if item.get("literal_upvalue_count") != 2 or (item.get("state_register"), item.get("holder_register"), item.get("registry_index"), item.get("initial_reference_sentinel"), item.get("returned_register")) != ("edi", "ebx", REGISTRY_INDEX, NOREF_SENTINEL, "ebx"):
                raise NativeLuaCClosureTerminalDispositionError(f"{label} registry-holder fields differ")
            template = _registry_template(image_base, source, imports)
            sequence = _array(item["reviewed_sequence"], f"{label}.reviewed_sequence")
            start = call - sum(len(encoded) for _, encoded in template[:14])
            _require_sequence(sequence, template, start, caller_range, f"{label}.reviewed_sequence")
            required_calls = {"first_rawgeti": "lua_rawgeti", "second_rawgeti": "lua_rawgeti", "pushcclosure": "lua_pushcclosure", "pushvalue": "lua_pushvalue", "luaL_ref": "luaL_ref", "lua_settop": "lua_settop"}
            by_role = {entry["role"]: _rva(entry["rva"], "sequence RVA") for entry in sequence}
            source_state = _instruction_structure(source.get("state_push"), f"{label}.callback_state_push")
            closure_state = next(entry for entry in sequence if entry["role"] == "closure_state_push")
            closure_state_fact = _instruction_structure(
                {key: closure_state[key] for key in ("rva", "size", "sha256")},
                f"{label}.closure_state_push",
            )
            if source_state != closure_state_fact or source_state != (call - 1, 1, EDI_PUSH_SHA256):
                raise NativeLuaCClosureTerminalDispositionError(f"{label} callback state does not match the reviewed EDI holder state")
            for role, name in required_calls.items():
                joined = lua_calls.get(by_role[role])
                if joined is None or joined[0].get("entry_rva") != item["caller_entry_rva"] or joined[1].get("import_name") != name:
                    raise NativeLuaCClosureTerminalDispositionError(f"{label} {role} does not join the direct-call census")
        dispositions.append(item)
    previous = -1
    unmatched_keys = {"caller_entry_rva", "caller_atlas_record_sha256", "callback_call_rva", "callback_entry_rva", "callback_atlas_record_sha256", "resolution"}
    for index, raw in enumerate(_array(evidence["still_unmatched_resolved_sites"], "evidence.still_unmatched_resolved_sites")):
        item = _mapping(raw, "unmatched site"); _exact_keys(item, unmatched_keys, "unmatched site")
        call = _site_key(item, "unmatched site")
        if call <= previous or call in seen or call not in frontier or item != _unmatched(frontier[call]):
            raise NativeLuaCClosureTerminalDispositionError("unmatched sites do not preserve the ordered residual frontier")
        previous = call; seen.add(call)
    if seen != set(frontier):
        raise NativeLuaCClosureTerminalDispositionError("dispositions and unmatched sites do not exactly partition the residual frontier")
    callers, targets = _aggregates(dispositions)
    if evidence["callers"] != callers or evidence["callback_targets"] != targets:
        raise NativeLuaCClosureTerminalDispositionError("disposition aggregates differ")
    expected_summary = {"prior_unmatched_resolved_callback_sites": len(frontier), "matched_terminal_disposition_sites": len(dispositions), "still_unmatched_resolved_callback_sites": len(evidence["still_unmatched_resolved_sites"]), "lua_callback_single_result_sites": sum(item["disposition_kind"] == RETURN_KIND for item in dispositions), "registry_reference_holder_sites": sum(item["disposition_kind"] == HOLDER_KIND for item in dispositions), "unique_disposition_callers": len(callers), "unique_disposition_callback_targets": len(targets), "schema_violations": 0}
    summary = _mapping(evidence["summary"], "evidence.summary"); _exact_keys(summary, set(expected_summary), "evidence.summary")
    if summary != expected_summary or any(type(value) is not int or value < 0 for value in summary.values()):
        raise NativeLuaCClosureTerminalDispositionError("summary partition or aggregates differ")
    _assert_publication_safe(evidence)
    return {"schema_version": SCHEMA_VERSION, "analysis_kind": STRUCTURE_VERIFICATION_KIND, "status": "structurally_verified", "build_identity": dict(identity), "evidence_sha256": _canonical_sha256(evidence), "summary": dict(summary)}


def encode_native_lua_cclosure_terminal_disposition_census(value: Mapping[str, Any]) -> str:
    _validate_json_tree(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
