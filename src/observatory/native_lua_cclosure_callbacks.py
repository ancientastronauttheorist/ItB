"""Exact callback arguments passed to direct ``lua_pushcclosure`` calls.

This census builds on the independently decoded native-to-Lua import-call
relation.  It accepts only an immediate callback address in the exact x86
argument sequence described by :data:`CALLBACK_ARGUMENT_FORM`.  Register- and
memory-sourced callback arguments remain explicitly unresolved.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_CALL_ANALYSIS_KIND,
    CALL_FORM as DIRECT_CALL_FORM,
    NativeLuaDirectCallError,
    SUPPORTED_CAPSTONE_VERSION,
    _decoder,
    _load_executable,
    validate_native_lua_direct_call_census,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_immediate_cclosure_callback_census"
VERIFICATION_KIND = (
    "pe_native_lua_immediate_cclosure_callback_census_verification"
)
LUA_LIBRARY = "lua5.1.dll"
LUA_PUSHCLOSURE = "lua_pushcclosure"
CALLBACK_ARGUMENT_FORM = "x86_cdecl_pushes_n_callback_imm32_state_register"
UNRESOLVED_ARGUMENT_KINDS = {"memory", "register"}
MAX_TEXT = 1024
_RVA_RE = re.compile(r"0x[0-9a-f]{8}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

_METHOD = {
    "direct_call_prerequisite_exactly_verified": True,
    "accepted_callback_edge": (
        "The final three contiguous instructions before an exact direct "
        "lua_pushcclosure import call must be PUSH instructions for the upvalue "
        "count, callback, and Lua-state arguments. The callback instruction must "
        "be exact x86 opcode 68 with one image VA, the Lua-state instruction must "
        "be a one-byte register PUSH, and the VA must equal one atlas entry."
    ),
    "unresolved_partition": (
        "Every other direct lua_pushcclosure site in this build is retained only "
        "when its immediately passed callback argument is register- or "
        "memory-sourced. No target is inferred for either form."
    ),
    "relation_semantics": (
        "A resolved edge proves only that one atlas entry is statically passed as "
        "the C-closure callback argument at one decoded call site."
    ),
    "publication_boundary": (
        "The artifact publishes RVAs, canonical atlas hashes, instruction hashes "
        "and sizes, normalized argument forms, and counts. It omits instruction "
        "bytes, disassembly text, decompiler output, local paths, variables, and "
        "reconstructed source."
    ),
    "not_claimed": [
        "runtime reachability, callback execution, or call frequency",
        "Lua-visible registration, exported name, table identity, or lifetime",
        "targets for register- or memory-sourced callback arguments",
        "indirect or computed lua_pushcclosure calls",
        "function ownership, subsystem, purpose, inputs, or outputs",
        "exclusive native-to-Lua roles",
        "source-level or behavioral equivalence",
    ],
}


class NativeLuaCClosureError(RuntimeError):
    """Raised when native Lua C-closure callback evidence is invalid or stale."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NativeLuaCClosureError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if type(value) is not list:
        raise NativeLuaCClosureError(f"{label} must be an array")
    return value


def _rva(value: Any, label: str) -> int:
    if type(value) is not str or _RVA_RE.fullmatch(value) is None:
        raise NativeLuaCClosureError(f"{label} must be a canonical 32-bit RVA")
    return int(value, 16)


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _validate_json_tree(value: Any, label: str = "value") -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _validate_json_tree(item, f"{label}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise NativeLuaCClosureError(f"{label} has a non-text key")
            _validate_json_tree(item, f"{label}.{key}")
        return
    raise NativeLuaCClosureError(
        f"{label} contains a non-JSON or floating-point value"
    )


def _canonical_bytes(value: Any) -> bytes:
    _validate_json_tree(value)
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise NativeLuaCClosureError(
            f"value cannot be canonically encoded: {exc}"
        ) from exc
    return (rendered + "\n").encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _assert_publication_safe(value: Any, label: str = "artifact") -> None:
    if type(value) is str:
        if len(value) > MAX_TEXT or "\0" in value:
            raise NativeLuaCClosureError(f"{label} contains unbounded text")
        if "/" in value or "\\" in value or re.search(r"[A-Za-z]:", value):
            raise NativeLuaCClosureError(f"{label} contains path-like text")
        return
    if value is None or type(value) in {bool, int}:
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _assert_publication_safe(item, f"{label}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str or len(key) > 128:
                raise NativeLuaCClosureError(f"{label} has an invalid field name")
            _assert_publication_safe(item, f"{label}.{key}")
        return
    raise NativeLuaCClosureError(f"{label} contains a non-publication value")


def _instruction_fact(instruction: Any, image_base: int) -> dict[str, Any]:
    encoded = bytes(instruction.bytes)
    return {
        "rva": _hex(instruction.address - image_base),
        "size": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _decode_range(
    data: bytes,
    image: Any,
    start: int,
    size: int,
    decoder: Any,
) -> list[Any]:
    offset = image.rva_span_to_file_offset(start, size)
    if offset is None:
        raise NativeLuaCClosureError(
            f"atlas range {_hex(start)} is not contiguous file-backed data"
        )
    expected_va = image.image_base + start
    instructions = list(decoder.disasm(data[offset : offset + size], expected_va))
    decoded_size = 0
    for instruction in instructions:
        if instruction.address != expected_va + decoded_size:
            raise NativeLuaCClosureError(
                f"atlas range {_hex(start)} decoded non-contiguously"
            )
        decoded_size += instruction.size
    if decoded_size != size:
        raise NativeLuaCClosureError(
            f"atlas range {_hex(start)} did not decode completely"
        )
    return instructions


def _argument_kind(instruction: Any, x86: Any) -> str:
    if instruction.id != x86.X86_INS_PUSH or len(instruction.operands) != 1:
        return "other"
    operand_type = instruction.operands[0].type
    return {
        x86.X86_OP_IMM: "immediate",
        x86.X86_OP_MEM: "memory",
        x86.X86_OP_REG: "register",
    }.get(operand_type, "other")


def _pushcclosure_calls(
    direct_calls: Mapping[str, Any],
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    imports = [
        _mapping(item, "direct_calls.lua_imports item")
        for item in _array(direct_calls.get("lua_imports"), "direct_calls.lua_imports")
        if isinstance(item, Mapping) and item.get("name") == LUA_PUSHCLOSURE
    ]
    if len(imports) != 1 or imports[0].get("library") != LUA_LIBRARY:
        raise NativeLuaCClosureError(
            "direct-call census must contain one lua_pushcclosure import"
        )
    expected_sites = imports[0].get("direct_call_sites")
    if type(expected_sites) is not int or expected_sites <= 0:
        raise NativeLuaCClosureError(
            "lua_pushcclosure import must have direct call sites"
        )
    calls: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for record_index, raw_record in enumerate(
        _array(direct_calls.get("records"), "direct_calls.records")
    ):
        record = _mapping(raw_record, f"direct_calls.records[{record_index}]")
        for raw_call in _array(
            record.get("direct_lua_import_calls"),
            f"direct_calls.records[{record_index}].direct_lua_import_calls",
        ):
            call = _mapping(raw_call, "direct Lua call")
            if call.get("import_name") == LUA_PUSHCLOSURE:
                if (
                    call.get("library") != LUA_LIBRARY
                    or call.get("call_form") != DIRECT_CALL_FORM
                    or call.get("iat_rva") != imports[0].get("iat_rva")
                ):
                    raise NativeLuaCClosureError(
                        "lua_pushcclosure direct-call facts disagree"
                    )
                calls.append((record, call))
    calls.sort(key=lambda pair: _rva(pair[1].get("call_rva"), "call_rva"))
    if len(calls) != expected_sites:
        raise NativeLuaCClosureError(
            "lua_pushcclosure call partition differs from import aggregate"
        )
    return calls


def build_native_lua_cclosure_callback_census(
    executable: Path,
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build exact immediate C-closure callback edges for one verified build."""
    _validate_json_tree(direct_calls, "direct_calls")
    _validate_json_tree(program_facts, "program_facts")
    _validate_json_tree(inventory, "inventory")
    try:
        verification = validate_native_lua_direct_call_census(
            executable,
            direct_calls,
            program_facts,
            inventory=inventory,
        )
        data, image, executable_sha256 = _load_executable(executable)
    except NativeLuaDirectCallError as exc:
        raise NativeLuaCClosureError(
            f"direct-call prerequisite failed exact verification: {exc}"
        ) from exc
    if direct_calls.get("analysis_kind") != DIRECT_CALL_ANALYSIS_KIND:
        raise NativeLuaCClosureError("direct-call prerequisite has the wrong kind")
    direct_identity = _mapping(
        direct_calls.get("build_identity"), "direct_calls.build_identity"
    )
    if (
        direct_identity.get("executable_sha256") != executable_sha256
        or direct_identity.get("executable_size") != len(data)
        or direct_identity.get("architecture") != image.architecture
    ):
        raise NativeLuaCClosureError(
            "executable changed after direct-call prerequisite verification"
        )
    if verification.get("evidence_sha256") != _canonical_sha256(direct_calls):
        raise NativeLuaCClosureError("direct-call canonical identity disagrees")

    raw_functions = _array(program_facts.get("functions"), "program_facts.functions")
    atlas_by_entry: dict[int, Mapping[str, Any]] = {}
    for index, raw_function in enumerate(raw_functions):
        function = _mapping(raw_function, f"program_facts.functions[{index}]")
        entry = _rva(function.get("entry_rva"), f"function {index}.entry_rva")
        if entry in atlas_by_entry:
            raise NativeLuaCClosureError("atlas function entries must be unique")
        atlas_by_entry[entry] = function

    try:
        import capstone.x86_const as x86
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise NativeLuaCClosureError(
            f"Capstone {SUPPORTED_CAPSTONE_VERSION} is required"
        ) from exc
    decoder, call_id = _decoder()
    decoder.detail = True
    decoded_cache: dict[tuple[int, int], list[Any]] = {}
    direct_consumer_entries = {
        _rva(_mapping(record, "direct call record").get("entry_rva"), "entry_rva")
        for record in _array(direct_calls.get("records"), "direct_calls.records")
    }
    pushcclosure_calls = _pushcclosure_calls(direct_calls)
    pushcclosure_caller_entries = {
        _rva(record.get("entry_rva"), "pushcclosure caller entry")
        for record, _call in pushcclosure_calls
    }

    resolved_sites: list[dict[str, Any]] = []
    unresolved_sites: list[dict[str, Any]] = []
    target_sites: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen_call_rvas: set[int] = set()
    for direct_record, direct_call in pushcclosure_calls:
        caller_entry = _rva(direct_record.get("entry_rva"), "caller entry_rva")
        caller_function = atlas_by_entry.get(caller_entry)
        if caller_function is None:
            raise NativeLuaCClosureError("direct-call caller is absent from atlas")
        caller_hash = atlas_record_sha256(caller_function)
        if direct_record.get("atlas_record_sha256") != caller_hash:
            raise NativeLuaCClosureError("direct-call caller atlas hash differs")
        call_rva = _rva(direct_call.get("call_rva"), "call_rva")
        if call_rva in seen_call_rvas:
            raise NativeLuaCClosureError("duplicate lua_pushcclosure call RVA")
        seen_call_rvas.add(call_rva)
        containing_ranges = []
        for raw_range in _array(caller_function.get("ranges"), "caller ranges"):
            body_range = _mapping(raw_range, "caller range")
            start = _rva(body_range.get("start_rva"), "range start_rva")
            size = body_range.get("size")
            if type(size) is not int or size <= 0:
                raise NativeLuaCClosureError("atlas range size must be positive")
            if start <= call_rva < start + size:
                containing_ranges.append((start, size))
        if len(containing_ranges) != 1:
            raise NativeLuaCClosureError(
                "lua_pushcclosure call must join exactly one caller range"
            )
        start, size = containing_ranges[0]
        cache_key = (start, size)
        if cache_key not in decoded_cache:
            decoded_cache[cache_key] = _decode_range(
                data, image, start, size, decoder
            )
        instructions = decoded_cache[cache_key]
        matching = [
            index
            for index, instruction in enumerate(instructions)
            if instruction.address - image.image_base == call_rva
        ]
        if len(matching) != 1:
            raise NativeLuaCClosureError(
                "lua_pushcclosure call does not join one decoded instruction"
            )
        call_index = matching[0]
        call_instruction = instructions[call_index]
        call_bytes = bytes(call_instruction.bytes)
        if (
            call_instruction.id != call_id
            or len(call_bytes) != direct_call.get("instruction_size")
            or hashlib.sha256(call_bytes).hexdigest()
            != direct_call.get("instruction_sha256")
        ):
            raise NativeLuaCClosureError(
                "decoded lua_pushcclosure instruction differs from prerequisite"
            )
        if call_index < 2:
            raise NativeLuaCClosureError("call lacks immediate argument instructions")
        callback_push = instructions[call_index - 2]
        state_push = instructions[call_index - 1]
        callback_kind = _argument_kind(callback_push, x86)
        state_kind = _argument_kind(state_push, x86)
        if (
            callback_push.address + callback_push.size != state_push.address
            or state_push.address + state_push.size != call_instruction.address
            or state_kind != "register"
            or len(bytes(state_push.bytes)) != 1
            or not 0x50 <= bytes(state_push.bytes)[0] <= 0x57
        ):
            raise NativeLuaCClosureError(
                "unsupported lua_pushcclosure callback or state argument sequence"
            )
        shared = {
            "caller_entry_rva": _hex(caller_entry),
            "caller_atlas_record_sha256": caller_hash,
            "call_rva": _hex(call_rva),
            "call_instruction_sha256": direct_call.get("instruction_sha256"),
            "callback_push": _instruction_fact(callback_push, image.image_base),
            "state_push": _instruction_fact(state_push, image.image_base),
            "library": LUA_LIBRARY,
            "import_name": LUA_PUSHCLOSURE,
            "iat_rva": direct_call.get("iat_rva"),
        }
        immediate_form = False
        if call_index >= 3:
            upvalue_push = instructions[call_index - 3]
            immediate_form = (
                upvalue_push.id == x86.X86_INS_PUSH
                and len(upvalue_push.operands) == 1
                and upvalue_push.address + upvalue_push.size
                == callback_push.address
                and callback_kind == "immediate"
                and len(bytes(callback_push.bytes)) == 5
                and bytes(callback_push.bytes)[0] == 0x68
            )
        if immediate_form:
            callback_va = int.from_bytes(bytes(callback_push.bytes)[1:], "little")
            if callback_va < image.image_base:
                raise NativeLuaCClosureError("callback immediate is below image base")
            callback_entry = callback_va - image.image_base
            callback_function = atlas_by_entry.get(callback_entry)
            if callback_function is None:
                raise NativeLuaCClosureError(
                    "immediate callback does not equal an atlas entry"
                )
            if callback_function.get("thunk") is not False:
                raise NativeLuaCClosureError("immediate callback atlas entry is a thunk")
            upvalue_kind = _argument_kind(upvalue_push, x86)
            upvalue_count = None
            if upvalue_kind == "immediate":
                raw_count = int(upvalue_push.operands[0].imm)
                if raw_count < 0 or raw_count > 255:
                    raise NativeLuaCClosureError(
                        "literal lua_pushcclosure upvalue count is out of range"
                    )
                upvalue_count = raw_count
            site = {
                **shared,
                "argument_form": CALLBACK_ARGUMENT_FORM,
                "upvalue_push": _instruction_fact(
                    upvalue_push, image.image_base
                ),
                "upvalue_argument_kind": upvalue_kind,
                "literal_upvalue_count": upvalue_count,
                "callback_entry_rva": _hex(callback_entry),
                "callback_atlas_record_sha256": atlas_record_sha256(
                    callback_function
                ),
                "self_callback": callback_entry == caller_entry,
            }
            resolved_sites.append(site)
            target_sites[callback_entry].append(site)
        else:
            if callback_kind not in UNRESOLVED_ARGUMENT_KINDS:
                raise NativeLuaCClosureError(
                    "unsupported unresolved callback argument kind"
                )
            unresolved_sites.append(
                {
                    **shared,
                    "callback_argument_kind": callback_kind,
                    "resolution": "unresolved_non_immediate_callback",
                }
            )

    resolved_sites.sort(key=lambda item: _rva(item["call_rva"], "call_rva"))
    unresolved_sites.sort(key=lambda item: _rva(item["call_rva"], "call_rva"))
    callback_targets = []
    for target_entry in sorted(target_sites):
        sites = target_sites[target_entry]
        callback_targets.append(
            {
                "callback_entry_rva": _hex(target_entry),
                "callback_atlas_record_sha256": sites[0][
                    "callback_atlas_record_sha256"
                ],
                "resolved_site_count": len(sites),
                "caller_entry_rvas": sorted(
                    {site["caller_entry_rva"] for site in sites}
                ),
                "also_direct_lua_import_caller": (
                    target_entry in direct_consumer_entries
                ),
                "also_pushcclosure_caller": (
                    target_entry in pushcclosure_caller_entries
                ),
            }
        )
    unresolved_kinds = Counter(
        item["callback_argument_kind"] for item in unresolved_sites
    )
    direct_atlas = _mapping(direct_calls.get("atlas"), "direct_calls.atlas")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(direct_identity),
        "atlas": {
            "analysis_kind": direct_atlas.get("analysis_kind"),
            "canonical_sha256": direct_atlas.get("canonical_sha256"),
            "function_count": direct_atlas.get("function_count"),
        },
        "direct_call_census": {
            "analysis_kind": direct_calls.get("analysis_kind"),
            "canonical_sha256": _canonical_sha256(direct_calls),
            "direct_lua_import_call_sites": _mapping(
                direct_calls.get("summary"), "direct_calls.summary"
            ).get("direct_lua_import_call_sites"),
            "lua_pushcclosure_call_sites": len(pushcclosure_calls),
        },
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "accepted_argument_form": CALLBACK_ARGUMENT_FORM,
        },
        "resolved_sites": resolved_sites,
        "unresolved_sites": unresolved_sites,
        "callback_targets": callback_targets,
        "method": _METHOD,
        "summary": {
            "direct_pushcclosure_call_sites": len(pushcclosure_calls),
            "resolved_immediate_callback_sites": len(resolved_sites),
            "unresolved_callback_sites": len(unresolved_sites),
            "unresolved_register_callback_sites": unresolved_kinds["register"],
            "unresolved_memory_callback_sites": unresolved_kinds["memory"],
            "unique_callback_targets": len(callback_targets),
            "duplicate_callback_targets": sum(
                item["resolved_site_count"] > 1 for item in callback_targets
            ),
            "self_callback_sites": sum(
                bool(item["self_callback"]) for item in resolved_sites
            ),
            "callback_targets_with_direct_lua_import_calls": sum(
                bool(item["also_direct_lua_import_caller"])
                for item in callback_targets
            ),
            "callback_targets_that_call_pushcclosure": sum(
                bool(item["also_pushcclosure_caller"])
                for item in callback_targets
            ),
            "schema_violations": 0,
        },
    }
    if (
        len(resolved_sites) + len(unresolved_sites) != len(pushcclosure_calls)
        or sum(item["resolved_site_count"] for item in callback_targets)
        != len(resolved_sites)
    ):
        raise NativeLuaCClosureError("callback site partitions disagree")
    _assert_publication_safe(result)
    return result


def validate_native_lua_cclosure_callback_census(
    executable: Path,
    evidence: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and canonical-byte-compare one callback-argument census."""
    _validate_json_tree(evidence, "evidence")
    rebuilt = build_native_lua_cclosure_callback_census(
        executable,
        direct_calls,
        program_facts,
        inventory=inventory,
    )
    if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
        raise NativeLuaCClosureError(
            "evidence does not match the exact rebuilt C-closure callback census"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": rebuilt["build_identity"],
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": rebuilt["summary"],
    }


def encode_native_lua_cclosure_callback_census(
    value: Mapping[str, Any],
) -> str:
    """Encode callback evidence or verification output deterministically."""
    _validate_json_tree(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
