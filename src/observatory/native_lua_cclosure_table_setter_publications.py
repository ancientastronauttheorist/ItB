"""Exact direct-table-setter publications from prior-unmatched Lua closures.

This deliberately narrow census starts at the complete unmatched frontier of
the exact ``lua_setfield`` publication census.  It retains only a contiguous
fall-through from one already-resolved immediate C callback construction to a
direct ``lua_settable`` or ``lua_rawset`` import call.
"""

from __future__ import annotations

import hashlib
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
    ANALYSIS_KIND as SETFIELD_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as SETFIELD_STRUCTURE_VERIFICATION_KIND,
    NativeLuaCClosurePublicationError,
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _canonical_bytes,
    _canonical_sha256,
    _containing_range,
    _count,
    _decode_range,
    _exact_keys,
    _instruction_fact,
    _instruction_sha256,
    _instruction_structure,
    _mapping,
    _require_register_push,
    _rva,
    _sha256,
    _validate_json_tree,
    validate_native_lua_cclosure_setfield_publication_census,
    validate_native_lua_cclosure_setfield_publication_structure,
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
ANALYSIS_KIND = "pe_native_lua_immediate_cclosure_direct_table_setter_publication_census"
VERIFICATION_KIND = (
    "pe_native_lua_immediate_cclosure_direct_table_setter_publication_census_"
    "verification"
)
STRUCTURE_VERIFICATION_KIND = (
    "pe_native_lua_immediate_cclosure_direct_table_setter_publication_census_"
    "structure_verification"
)
PUBLICATION_FORM = (
    "x86_optional_cleanup_push_table_index_same_state_direct_table_setter_ff15"
)
UNMATCHED_RESOLUTION = "no_exact_contiguous_direct_table_setter_publication"
LUA_LIBRARY = "lua5.1.dll"
SETTER_IMPORTS = frozenset({"lua_settable", "lua_rawset"})
ABI_NONVOLATILE_STATE_PUSH_OPCODES = frozenset({0x53, 0x55, 0x56, 0x57})
ABI_NONVOLATILE_STATE_PUSH_SHA256 = frozenset(
    _instruction_sha256(bytes([opcode]))
    for opcode in ABI_NONVOLATILE_STATE_PUSH_OPCODES
)
INVALID_TABLE_INDICES = frozenset({-1, 0})

_METHOD = {
    "setfield_publication_prerequisite_exactly_verified": True,
    "accepted_publication": (
        "From one prior-unmatched exactly resolved direct lua_pushcclosure "
        "site, the same atlas range must contain a contiguous fall-through of "
        "zero instructions or one exact add esp,imm8 cleanup where imm8 is "
        "positive and divisible by four; push a signed immediate table index "
        "other than the definitely invalid "
        "zero and -1 forms; push the same ABI-nonvolatile Lua-state register; "
        "and a direct FF 15 call to the same caller's exact lua_settable or "
        "lua_rawset import record."
    ),
    "relation_semantics": (
        "The direct static sequence establishes that the newly constructed C "
        "closure is immediately on top of the Lua stack when the retained "
        "table setter consumes its value argument."
    ),
    "partition": (
        "Every prior unmatched resolved callback site occurs exactly once as "
        "one retained table-setter publication or one still-unmatched site."
    ),
    "publication_boundary": (
        "The artifact publishes normalized RVAs, fixed-size instruction hashes, "
        "direct-call identities, signed table indices, callback upvalue metadata, "
        "and deterministic aggregates. It omits instruction bytes, disassembly, "
        "decompiler output, local paths, variables, and reconstructed source."
    ),
    "not_claimed": [
        "runtime reachability, execution, frequency, persistence, or lifetime",
        "table identity, ownership, contents beyond the immediate setter edge, or later mutation",
        "global export, ordinary Lua lookup reachability, binding-system completeness, or a Lua-visible name",
        "publication through non-direct, computed, non-FF15, or other Lua APIs",
        "function ownership, subsystem, purpose, inputs, outputs, source-level, or behavioral equivalence",
    ],
}


class NativeLuaCClosureTableSetterPublicationError(RuntimeError):
    """Raised for invalid or stale direct table-setter publication evidence."""


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _source_identity(
    setfield_publications: Mapping[str, Any],
) -> dict[str, Any]:
    artifact = _mapping(setfield_publications, "setfield_publications")
    if artifact.get("analysis_kind") != SETFIELD_ANALYSIS_KIND:
        raise NativeLuaCClosureTableSetterPublicationError(
            "setfield publication prerequisite has the wrong kind"
        )
    summary = _mapping(artifact.get("summary"), "setfield_publications.summary")
    return {
        "analysis_kind": SETFIELD_ANALYSIS_KIND,
        "canonical_sha256": _canonical_sha256(artifact),
        "unmatched_resolved_callback_sites": summary.get(
            "unmatched_resolved_callback_sites"
        ),
    }


def _direct_setter_calls(
    direct_calls: Mapping[str, Any],
) -> dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]]:
    direct_calls = _mapping(direct_calls, "direct_calls")
    imports: dict[str, Mapping[str, Any]] = {}
    for index, raw_import in enumerate(_array(direct_calls.get("lua_imports"), "direct_calls.lua_imports")):
        item = _mapping(raw_import, f"direct_calls.lua_imports[{index}]")
        name = item.get("name")
        if name in SETTER_IMPORTS:
            if item.get("library") != LUA_LIBRARY or name in imports:
                raise NativeLuaCClosureTableSetterPublicationError(
                    "direct-call setter imports disagree"
                )
            imports[name] = item
    if set(imports) != SETTER_IMPORTS:
        raise NativeLuaCClosureTableSetterPublicationError(
            "direct-call census must contain exactly lua_settable and lua_rawset"
        )
    calls: dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    observed = {name: 0 for name in SETTER_IMPORTS}
    for record_index, raw_record in enumerate(_array(direct_calls.get("records"), "direct_calls.records")):
        record = _mapping(raw_record, f"direct_calls.records[{record_index}]")
        for raw_call in _array(record.get("direct_lua_import_calls"), f"direct_calls.records[{record_index}].direct_lua_import_calls"):
            call = _mapping(raw_call, "direct Lua call")
            name = call.get("import_name")
            if name not in SETTER_IMPORTS:
                continue
            if (
                call.get("library") != LUA_LIBRARY
                or call.get("call_form") != DIRECT_CALL_FORM
                or call.get("iat_rva") != imports[name].get("iat_rva")
            ):
                raise NativeLuaCClosureTableSetterPublicationError(
                    "direct-call setter facts disagree"
                )
            call_rva = _rva(call.get("call_rva"), "direct setter call_rva")
            if call_rva in calls:
                raise NativeLuaCClosureTableSetterPublicationError(
                    "direct setter call RVAs must be unique"
                )
            calls[call_rva] = (record, call)
            observed[name] += 1
    for name, item in imports.items():
        if item.get("direct_call_sites") != observed[name]:
            raise NativeLuaCClosureTableSetterPublicationError(
                "direct setter call partition differs from import aggregate"
            )
    return calls


def _site_key(site: Mapping[str, Any], label: str) -> int:
    return _rva(site.get("callback_call_rva", site.get("call_rva")), f"{label}.callback_call_rva")


def _frontier(
    setfield_publications: Mapping[str, Any],
    callback_census: Mapping[str, Any],
) -> tuple[dict[int, Mapping[str, Any]], dict[int, Mapping[str, Any]]]:
    resolved: dict[int, Mapping[str, Any]] = {}
    for index, raw_site in enumerate(_array(callback_census.get("resolved_sites"), "callback_census.resolved_sites")):
        site = _mapping(raw_site, f"callback_census.resolved_sites[{index}]")
        call = _rva(site.get("call_rva"), f"callback_census.resolved_sites[{index}].call_rva")
        if call in resolved:
            raise NativeLuaCClosureTableSetterPublicationError(
                "resolved callback call RVAs must be unique"
            )
        resolved[call] = site
    frontier: dict[int, Mapping[str, Any]] = {}
    previous = -1
    for index, raw_site in enumerate(_array(setfield_publications.get("unmatched_resolved_sites"), "setfield_publications.unmatched_resolved_sites")):
        site = _mapping(raw_site, f"setfield_publications.unmatched_resolved_sites[{index}]")
        call = _site_key(site, f"setfield_publications.unmatched_resolved_sites[{index}]")
        if call <= previous or call in frontier:
            raise NativeLuaCClosureTableSetterPublicationError(
                "setfield unmatched frontier must be unique and callback-call-RVA ordered"
            )
        previous = call
        source = resolved.get(call)
        if source is None:
            raise NativeLuaCClosureTableSetterPublicationError(
                "setfield unmatched frontier does not join callback census"
            )
        for key in (
            "caller_entry_rva",
            "caller_atlas_record_sha256",
            "callback_entry_rva",
            "callback_atlas_record_sha256",
        ):
            if site.get(key) != source.get(key):
                raise NativeLuaCClosureTableSetterPublicationError(
                    "setfield unmatched frontier identity differs from callback census"
                )
        frontier[call] = site
    if len(frontier) != _mapping(setfield_publications.get("summary"), "setfield_publications.summary").get("unmatched_resolved_callback_sites"):
        raise NativeLuaCClosureTableSetterPublicationError(
            "setfield unmatched frontier count differs from summary"
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


def _aggregates(publications: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_builder: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_target: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for publication in publications:
        by_builder[publication["caller_entry_rva"]].append(publication)
        by_target[publication["callback_entry_rva"]].append(publication)
    builders = [
        {
            "builder_entry_rva": entry,
            "builder_atlas_record_sha256": items[0]["caller_atlas_record_sha256"],
            "publication_site_count": len(items),
            "registered_callback_entry_rvas": sorted({item["callback_entry_rva"] for item in items}),
            "setter_import_names": sorted({item["setter_import_name"] for item in items}),
            "table_indices": sorted({item["table_index"] for item in items}),
            "upvalue_argument_kinds": sorted({item["upvalue_argument_kind"] for item in items}),
        }
        for entry, items in sorted(by_builder.items(), key=lambda item: _rva(item[0], "builder entry"))
    ]
    targets = [
        {
            "callback_entry_rva": entry,
            "callback_atlas_record_sha256": items[0]["callback_atlas_record_sha256"],
            "publication_site_count": len(items),
            "builder_entry_rvas": sorted({item["caller_entry_rva"] for item in items}),
            "setter_import_names": sorted({item["setter_import_name"] for item in items}),
            "table_indices": sorted({item["table_index"] for item in items}),
            "upvalue_argument_kinds": sorted({item["upvalue_argument_kind"] for item in items}),
        }
        for entry, items in sorted(by_target.items(), key=lambda item: _rva(item[0], "target entry"))
    ]
    return builders, targets


def build_native_lua_cclosure_table_setter_publication_census(
    executable: Path,
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact direct-table-setter publication census."""
    for value, label in ((direct_calls, "direct_calls"), (callback_census, "callback_census"), (setfield_publications, "setfield_publications"), (program_facts, "program_facts"), (inventory, "inventory")):
        _validate_json_tree(value, label)
    if direct_calls.get("analysis_kind") != DIRECT_CALL_ANALYSIS_KIND or callback_census.get("analysis_kind") != CALLBACK_ANALYSIS_KIND:
        raise NativeLuaCClosureTableSetterPublicationError("direct or callback prerequisite has the wrong kind")
    try:
        setfield_verification = validate_native_lua_cclosure_setfield_publication_census(
            executable, setfield_publications, direct_calls, callback_census, program_facts, inventory=inventory
        )
        data, image, executable_sha256 = _load_executable(executable)
        decoder, _ = _decoder()
    except (NativeLuaCClosurePublicationError, NativeLuaCClosureError, NativeLuaDirectCallError, PEAnchorError) as exc:
        raise NativeLuaCClosureTableSetterPublicationError(
            f"setfield publication prerequisite failed exact verification: {exc}"
        ) from exc
    identity = _mapping(setfield_publications.get("build_identity"), "setfield_publications.build_identity")
    if identity.get("executable_sha256") != executable_sha256 or identity.get("executable_size") != len(data) or identity.get("architecture") != image.architecture:
        raise NativeLuaCClosureTableSetterPublicationError("executable changed after prerequisite verification")
    if setfield_verification.get("evidence_sha256") != _canonical_sha256(setfield_publications):
        raise NativeLuaCClosureTableSetterPublicationError("setfield prerequisite canonical identity disagrees")

    functions = _atlas_functions(program_facts)
    resolved, frontier = _frontier(setfield_publications, callback_census)
    setters = _direct_setter_calls(direct_calls)
    decoded: dict[tuple[int, int], list[Any]] = {}
    publications: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for callback_call, frontier_site in frontier.items():
        source = resolved[callback_call]
        caller_entry = _rva(source.get("caller_entry_rva"), "callback caller_entry_rva")
        callback_entry = _rva(source.get("callback_entry_rva"), "callback callback_entry_rva")
        caller = functions.get(caller_entry)
        callback = functions.get(callback_entry)
        if caller is None or callback is None or callback.get("thunk") is not False:
            raise NativeLuaCClosureTableSetterPublicationError("frontier callback site does not join non-thunk atlas entries")
        if source.get("caller_atlas_record_sha256") != atlas_record_sha256(caller) or source.get("callback_atlas_record_sha256") != atlas_record_sha256(callback):
            raise NativeLuaCClosureTableSetterPublicationError("frontier callback atlas hashes differ")
        caller_range = _containing_range(caller, callback_call)
        instructions = decoded.get(caller_range)
        if instructions is None:
            instructions = _decode_range(
                data, image, caller_range[0], caller_range[1], decoder
            )
            decoded[caller_range] = instructions
        by_rva = {ins.address - image.image_base: index for index, ins in enumerate(instructions)}
        call_index = by_rva.get(callback_call)
        state_rva = _rva(_mapping(source.get("state_push"), "callback state_push").get("rva"), "callback state_push.rva")
        state_index = by_rva.get(state_rva)
        if call_index is None or state_index is None:
            raise NativeLuaCClosureTableSetterPublicationError("frontier callback instructions are absent from caller decode")
        callback_instruction = instructions[call_index]
        source_state = instructions[state_index]
        if _instruction_sha256(bytes(callback_instruction.bytes)) != source.get("call_instruction_sha256") or _instruction_sha256(bytes(source_state.bytes)) != _mapping(source.get("state_push"), "callback state_push").get("sha256"):
            raise NativeLuaCClosureTableSetterPublicationError("frontier callback instruction hashes differ from executable")
        following = instructions[call_index + 1 : call_index + 5]
        position = 0
        cleanup = None
        cleanup_bytes = None
        if following and _cleanup_value(following[0]) is not None:
            cleanup = following[0]
            cleanup_bytes = _cleanup_value(cleanup)
            position = 1
        if len(following) < position + 3:
            unmatched.append(_unmatched(frontier_site))
            continue
        table_push, state_push, setter = following[position : position + 3]
        table_index = _decode_table_index(table_push)
        setter_rva = setter.address - image.image_base
        direct_setter = setters.get(setter_rva)
        accepted = (
            table_index is not None
            and table_index not in INVALID_TABLE_INDICES
            and bytes(state_push.bytes) == bytes(source_state.bytes)
            and len(state_push.bytes) == 1
            and state_push.bytes[0] in ABI_NONVOLATILE_STATE_PUSH_OPCODES
            and direct_setter is not None
            and direct_setter[0].get("entry_rva") == source.get("caller_entry_rva")
        )
        if accepted:
            setter_call = direct_setter[1]
            setter_iat = _rva(setter_call.get("iat_rva"), "direct setter iat_rva")
            expected = b"\xff\x15" + struct.pack("<I", image.image_base + setter_iat)
            accepted = (
                bytes(setter.bytes) == expected
                and _instruction_sha256(bytes(setter.bytes)) == setter_call.get("instruction_sha256")
            )
        if not accepted:
            unmatched.append(_unmatched(frontier_site))
            continue
        publications.append(
            {
                "publication_form": PUBLICATION_FORM,
                "caller_entry_rva": source["caller_entry_rva"],
                "caller_atlas_record_sha256": source["caller_atlas_record_sha256"],
                "callback_call_rva": source["call_rva"],
                "callback_call_instruction_sha256": source["call_instruction_sha256"],
                "callback_entry_rva": source["callback_entry_rva"],
                "callback_atlas_record_sha256": source["callback_atlas_record_sha256"],
                "upvalue_argument_kind": source["upvalue_argument_kind"],
                "literal_upvalue_count": source["literal_upvalue_count"],
                "cleanup_instruction": None if cleanup is None else _instruction_fact(cleanup, image.image_base),
                "cleanup_stack_bytes": cleanup_bytes,
                "table_index": table_index,
                "table_index_push": _instruction_fact(table_push, image.image_base),
                "state_push": _instruction_fact(state_push, image.image_base),
                "setter_call_rva": setter_call["call_rva"],
                "setter_call_instruction_sha256": setter_call["instruction_sha256"],
                "library": LUA_LIBRARY,
                "setter_import_name": setter_call["import_name"],
                "setter_iat_rva": setter_call["iat_rva"],
            }
        )
    publications.sort(key=lambda item: _rva(item["callback_call_rva"], "publication call"))
    unmatched.sort(key=lambda item: _rva(item["callback_call_rva"], "unmatched call"))
    if len(publications) + len(unmatched) != len(frontier):
        raise NativeLuaCClosureTableSetterPublicationError("prior-unmatched frontier partition disagrees")
    builders, targets = _aggregates(publications)
    direct_atlas = _mapping(direct_calls.get("atlas"), "direct_calls.atlas")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(identity),
        "atlas": {"analysis_kind": direct_atlas.get("analysis_kind"), "canonical_sha256": direct_atlas.get("canonical_sha256"), "function_count": direct_atlas.get("function_count")},
        "direct_call_census": {"analysis_kind": DIRECT_CALL_ANALYSIS_KIND, "canonical_sha256": _canonical_sha256(direct_calls)},
        "callback_census": {"analysis_kind": CALLBACK_ANALYSIS_KIND, "canonical_sha256": _canonical_sha256(callback_census)},
        "setfield_publication_census": _source_identity(setfield_publications),
        "decoder": {"name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION, "architecture": "x86", "mode_bits": 32, "accepted_publication_form": PUBLICATION_FORM},
        "publications": publications,
        "still_unmatched_resolved_sites": unmatched,
        "builders": builders,
        "registered_targets": targets,
        "method": _METHOD,
        "summary": {
            "prior_unmatched_resolved_callback_sites": len(frontier),
            "matched_direct_table_setter_publication_sites": len(publications),
            "still_unmatched_resolved_callback_sites": len(unmatched),
            "settable_publication_sites": sum(item["setter_import_name"] == "lua_settable" for item in publications),
            "rawset_publication_sites": sum(item["setter_import_name"] == "lua_rawset" for item in publications),
            "unique_registered_callback_targets": len(targets),
            "unique_registration_builders": len(builders),
            "unique_table_indices": len({item["table_index"] for item in publications}),
            "schema_violations": 0,
        },
    }
    _assert_publication_safe(result)
    return result


def validate_native_lua_cclosure_table_setter_publication_census(
    executable: Path,
    evidence: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and canonical-byte-compare one table-setter publication census."""
    _validate_json_tree(evidence, "evidence")
    rebuilt = build_native_lua_cclosure_table_setter_publication_census(executable, direct_calls, callback_census, setfield_publications, program_facts, inventory=inventory)
    if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
        raise NativeLuaCClosureTableSetterPublicationError("native Lua table-setter publication evidence differs from exact rebuild")
    return {"schema_version": SCHEMA_VERSION, "analysis_kind": VERIFICATION_KIND, "status": "verified", "build_identity": dict(_mapping(rebuilt["build_identity"], "build_identity")), "evidence_sha256": _canonical_sha256(rebuilt), "summary": dict(_mapping(rebuilt["summary"], "summary"))}


def _require_range(fact: tuple[int, int, str], caller_range: tuple[int, int], label: str) -> None:
    if fact[0] < caller_range[0] or fact[0] + fact[1] > caller_range[0] + caller_range[1]:
        raise NativeLuaCClosureTableSetterPublicationError(f"{label} does not lie within the exact caller atlas range")


def _require_abi_nonvolatile_state_push(
    fact: tuple[int, int, str], label: str
) -> None:
    _require_register_push(fact, label)
    if fact[2] not in ABI_NONVOLATILE_STATE_PUSH_SHA256:
        raise NativeLuaCClosureTableSetterPublicationError(
            f"{label} is not an ABI-nonvolatile x86 register PUSH"
        )


def _require_table_index_push(fact: tuple[int, int, str], value: Any, label: str) -> None:
    if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
        raise NativeLuaCClosureTableSetterPublicationError(f"{label} table index must be a signed 32-bit integer")
    if value in INVALID_TABLE_INDICES:
        raise NativeLuaCClosureTableSetterPublicationError(
            f"{label} table index is definitely invalid for the retained setter form"
        )
    if fact[1] == 2:
        if not -128 <= value <= 127:
            raise NativeLuaCClosureTableSetterPublicationError(
                f"{label} int8 PUSH is outside signed int8 range"
            )
        expected = (2, _instruction_sha256(b"\x6a" + struct.pack("<b", value)))
    elif fact[1] == 5:
        expected = (5, _instruction_sha256(b"\x68" + struct.pack("<i", value)))
    else:
        raise NativeLuaCClosureTableSetterPublicationError(
            f"{label} must be an exact x86 immediate PUSH"
        )
    if fact[1:] != expected:
        raise NativeLuaCClosureTableSetterPublicationError(f"{label} does not reconstruct the signed table index PUSH")


def validate_native_lua_cclosure_table_setter_publication_structure(
    evidence: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    setfield_publications: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the whole artifact without reading an executable.

    This is structural-only: it verifies joins, finite x86 hash reconstruction,
    range arithmetic, partitions, aggregates, and prerequisites, but does not
    prove that instructions exist at the published RVAs in an executable.
    """
    for value, label in ((evidence, "evidence"), (direct_calls, "direct_calls"), (callback_census, "callback_census"), (setfield_publications, "setfield_publications"), (program_facts, "program_facts")):
        _validate_json_tree(value, label)
    evidence = _mapping(evidence, "evidence")
    try:
        prerequisite = validate_native_lua_cclosure_setfield_publication_structure(setfield_publications, direct_calls, callback_census, program_facts)
    except NativeLuaCClosurePublicationError as exc:
        raise NativeLuaCClosureTableSetterPublicationError(f"setfield structural prerequisite failed: {exc}") from exc
    if prerequisite.get("analysis_kind") != SETFIELD_STRUCTURE_VERIFICATION_KIND or prerequisite.get("status") != "structurally_verified":
        raise NativeLuaCClosureTableSetterPublicationError("setfield structural prerequisite returned an unexpected result")
    _exact_keys(evidence, {"schema_version", "analysis_kind", "build_identity", "atlas", "direct_call_census", "callback_census", "setfield_publication_census", "decoder", "publications", "still_unmatched_resolved_sites", "builders", "registered_targets", "method", "summary"}, "evidence")
    if (
        type(evidence["schema_version"]) is not int
        or evidence["schema_version"] != SCHEMA_VERSION
        or evidence["analysis_kind"] != ANALYSIS_KIND
    ):
        raise NativeLuaCClosureTableSetterPublicationError("unsupported table-setter publication schema or analysis kind")
    facts = _mapping(program_facts, "program_facts")
    identity = _mapping(facts.get("identity"), "program_facts.identity")
    if evidence["build_identity"] != dict(identity) or evidence["build_identity"] != direct_calls.get("build_identity") or evidence["build_identity"] != callback_census.get("build_identity") or evidence["build_identity"] != setfield_publications.get("build_identity"):
        raise NativeLuaCClosureTableSetterPublicationError("table-setter build identity does not match prerequisites")
    ghidra = _mapping(facts.get("ghidra"), "program_facts.ghidra")
    image_base = _rva(ghidra.get("image_base"), "program_facts.ghidra.image_base")
    if image_base > 0xFFFFFFFF:
        raise NativeLuaCClosureTableSetterPublicationError("program image base overflows x86 VA")
    direct_atlas = _mapping(direct_calls.get("atlas"), "direct_calls.atlas")
    expected_atlas = {"analysis_kind": direct_atlas.get("analysis_kind"), "canonical_sha256": direct_atlas.get("canonical_sha256"), "function_count": direct_atlas.get("function_count")}
    atlas = _mapping(evidence["atlas"], "evidence.atlas")
    _exact_keys(atlas, set(expected_atlas), "evidence.atlas")
    if atlas != expected_atlas:
        raise NativeLuaCClosureTableSetterPublicationError("table-setter atlas identity differs")
    for key, prerequisite_document, kind in (("direct_call_census", direct_calls, DIRECT_CALL_ANALYSIS_KIND), ("callback_census", callback_census, CALLBACK_ANALYSIS_KIND)):
        value = _mapping(evidence[key], f"evidence.{key}")
        _exact_keys(value, {"analysis_kind", "canonical_sha256"}, f"evidence.{key}")
        if value != {"analysis_kind": kind, "canonical_sha256": _canonical_sha256(prerequisite_document)}:
            raise NativeLuaCClosureTableSetterPublicationError(f"{key} prerequisite identity differs")
    setfield_identity = _mapping(evidence["setfield_publication_census"], "evidence.setfield_publication_census")
    expected_setfield_identity = _source_identity(setfield_publications)
    _exact_keys(setfield_identity, set(expected_setfield_identity), "evidence.setfield_publication_census")
    if setfield_identity != expected_setfield_identity:
        raise NativeLuaCClosureTableSetterPublicationError("setfield publication prerequisite identity differs")
    decoder = _mapping(evidence["decoder"], "evidence.decoder")
    expected_decoder = {"name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION, "architecture": "x86", "mode_bits": 32, "accepted_publication_form": PUBLICATION_FORM}
    _exact_keys(decoder, set(expected_decoder), "evidence.decoder")
    if decoder != expected_decoder or _canonical_bytes(evidence["method"]) != _canonical_bytes(_METHOD):
        raise NativeLuaCClosureTableSetterPublicationError("table-setter decoder or method contract has drifted")

    functions = _atlas_functions(facts)
    resolved, frontier = _frontier(setfield_publications, callback_census)
    setters = _direct_setter_calls(direct_calls)
    publication_keys = {"publication_form", "caller_entry_rva", "caller_atlas_record_sha256", "callback_call_rva", "callback_call_instruction_sha256", "callback_entry_rva", "callback_atlas_record_sha256", "upvalue_argument_kind", "literal_upvalue_count", "cleanup_instruction", "cleanup_stack_bytes", "table_index", "table_index_push", "state_push", "setter_call_rva", "setter_call_instruction_sha256", "library", "setter_import_name", "setter_iat_rva"}
    unmatched_keys = {"caller_entry_rva", "caller_atlas_record_sha256", "callback_call_rva", "callback_entry_rva", "callback_atlas_record_sha256", "resolution"}
    seen: set[int] = set()
    previous = -1
    publications: list[Mapping[str, Any]] = []
    for index, raw in enumerate(_array(evidence["publications"], "evidence.publications")):
        label = f"evidence.publications[{index}]"
        item = _mapping(raw, label)
        _exact_keys(item, publication_keys, label)
        call = _site_key(item, label)
        frontier_site = frontier.get(call)
        source = resolved.get(call)
        if frontier_site is None or source is None or call <= previous or call in seen:
            raise NativeLuaCClosureTableSetterPublicationError("publications must uniquely and canonically partition the prior unmatched frontier")
        previous = call
        seen.add(call)
        for key in ("caller_entry_rva", "caller_atlas_record_sha256", "callback_entry_rva", "callback_atlas_record_sha256"):
            if item[key] != source.get(key) or item[key] != frontier_site.get(key):
                raise NativeLuaCClosureTableSetterPublicationError(f"{label}.{key} does not join the exact frontier callback site")
        if item["callback_call_instruction_sha256"] != source.get("call_instruction_sha256") or item["upvalue_argument_kind"] != source.get("upvalue_argument_kind") or item["literal_upvalue_count"] != source.get("literal_upvalue_count"):
            raise NativeLuaCClosureTableSetterPublicationError(f"{label} callback or upvalue metadata does not join the exact callback site")
        caller = functions.get(_rva(item["caller_entry_rva"], f"{label}.caller_entry_rva"))
        callback = functions.get(_rva(item["callback_entry_rva"], f"{label}.callback_entry_rva"))
        if caller is None or callback is None or callback.get("thunk") is not False or item["caller_atlas_record_sha256"] != atlas_record_sha256(caller) or item["callback_atlas_record_sha256"] != atlas_record_sha256(callback):
            raise NativeLuaCClosureTableSetterPublicationError(f"{label} atlas join differs")
        caller_range = _containing_range(caller, call)
        table_push = _instruction_structure(item["table_index_push"], f"{label}.table_index_push")
        state_push = _instruction_structure(item["state_push"], f"{label}.state_push")
        _require_range(table_push, caller_range, f"{label}.table_index_push")
        _require_range(state_push, caller_range, f"{label}.state_push")
        cleanup = item["cleanup_instruction"]
        if cleanup is None:
            if item["cleanup_stack_bytes"] is not None or table_push[0] != call + 6:
                raise NativeLuaCClosureTableSetterPublicationError(f"{label} no-cleanup sequence is not contiguous")
        else:
            cleanup_fact = _instruction_structure(cleanup, f"{label}.cleanup_instruction")
            cleanup_value = item["cleanup_stack_bytes"]
            if type(cleanup_value) is not int or cleanup_value <= 0 or cleanup_value > 0x7F or cleanup_value % 4 or cleanup_fact != (call + 6, 3, _instruction_sha256(b"\x83\xc4" + bytes([cleanup_value]))) or table_push[0] != cleanup_fact[0] + cleanup_fact[1]:
                raise NativeLuaCClosureTableSetterPublicationError(f"{label} cleanup instruction does not reconstruct the exact contiguous form")
            _require_range(cleanup_fact, caller_range, f"{label}.cleanup_instruction")
        _require_table_index_push(table_push, item["table_index"], f"{label}.table_index_push")
        if state_push[0] != table_push[0] + table_push[1]:
            raise NativeLuaCClosureTableSetterPublicationError(f"{label} table-index and state pushes are not contiguous")
        _require_abi_nonvolatile_state_push(state_push, f"{label}.state_push")
        source_state = _instruction_structure(source.get("state_push"), f"{label}.callback_state_push")
        if state_push[2] != source_state[2]:
            raise NativeLuaCClosureTableSetterPublicationError(f"{label}.state_push does not match callback state register")
        setter_call = _rva(item["setter_call_rva"], f"{label}.setter_call_rva")
        direct_setter = setters.get(setter_call)
        if direct_setter is None or direct_setter[0].get("entry_rva") != item["caller_entry_rva"]:
            raise NativeLuaCClosureTableSetterPublicationError(f"{label}.setter_call_rva does not join the exact direct setter call")
        setter = direct_setter[1]
        if item["publication_form"] != PUBLICATION_FORM or item["library"] != LUA_LIBRARY or item["setter_import_name"] not in SETTER_IMPORTS or item["setter_import_name"] != setter.get("import_name") or item["setter_iat_rva"] != setter.get("iat_rva") or item["setter_call_instruction_sha256"] != setter.get("instruction_sha256") or setter_call != state_push[0] + state_push[1]:
            raise NativeLuaCClosureTableSetterPublicationError(f"{label} setter fields do not join the exact direct table setter")
        iat = _rva(item["setter_iat_rva"], f"{label}.setter_iat_rva")
        if image_base + iat > 0xFFFFFFFF or item["setter_call_instruction_sha256"] != _instruction_sha256(b"\xff\x15" + (image_base + iat).to_bytes(4, "little")):
            raise NativeLuaCClosureTableSetterPublicationError(f"{label}.setter_call_instruction_sha256 does not reconstruct from IAT")
        if setter_call + 6 > caller_range[0] + caller_range[1]:
            raise NativeLuaCClosureTableSetterPublicationError(f"{label}.setter_call_rva lies outside caller range")
        publications.append(item)
    previous = -1
    for index, raw in enumerate(_array(evidence["still_unmatched_resolved_sites"], "evidence.still_unmatched_resolved_sites")):
        label = f"evidence.still_unmatched_resolved_sites[{index}]"
        item = _mapping(raw, label)
        _exact_keys(item, unmatched_keys, label)
        call = _site_key(item, label)
        source = resolved.get(call)
        if call not in frontier or source is None or call <= previous or call in seen:
            raise NativeLuaCClosureTableSetterPublicationError("still-unmatched sites must uniquely and canonically partition the prior frontier")
        previous = call
        seen.add(call)
        if item != _unmatched(frontier[call]):
            raise NativeLuaCClosureTableSetterPublicationError(f"{label} does not preserve the exact prior frontier site")
    if seen != set(frontier):
        raise NativeLuaCClosureTableSetterPublicationError("publications and still-unmatched sites do not exactly partition the prior frontier")
    builders, targets = _aggregates(publications)
    for name, expected in (("builders", builders), ("registered_targets", targets)):
        records = _array(evidence[name], f"evidence.{name}")
        if records != expected:
            raise NativeLuaCClosureTableSetterPublicationError(f"{name} do not exactly aggregate publication sites")
    summary = _mapping(evidence["summary"], "evidence.summary")
    expected_summary = {"prior_unmatched_resolved_callback_sites": len(frontier), "matched_direct_table_setter_publication_sites": len(publications), "still_unmatched_resolved_callback_sites": len(evidence["still_unmatched_resolved_sites"]), "settable_publication_sites": sum(item["setter_import_name"] == "lua_settable" for item in publications), "rawset_publication_sites": sum(item["setter_import_name"] == "lua_rawset" for item in publications), "unique_registered_callback_targets": len(targets), "unique_registration_builders": len(builders), "unique_table_indices": len({item["table_index"] for item in publications}), "schema_violations": 0}
    _exact_keys(summary, set(expected_summary), "evidence.summary")
    if any(type(value) is not int or value < 0 for value in summary.values()) or summary != expected_summary:
        raise NativeLuaCClosureTableSetterPublicationError("summary aggregates or partitions disagree")
    _assert_publication_safe(evidence)
    return {"schema_version": SCHEMA_VERSION, "analysis_kind": STRUCTURE_VERIFICATION_KIND, "status": "structurally_verified", "build_identity": dict(identity), "evidence_sha256": _canonical_sha256(evidence), "summary": dict(summary)}


def encode_native_lua_cclosure_table_setter_publication_census(value: Mapping[str, Any]) -> str:
    """Return deterministic pretty JSON for an artifact or verification result."""
    _validate_json_tree(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
