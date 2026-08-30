"""Exact direct ``lua_setfield`` publications of immediate Lua C closures.

This census is deliberately narrower than a general Lua-registration graph.
It starts from the exact immediate-callback census and accepts only one finite
x86 instruction grammar in which the newly pushed closure is immediately
stored into a table field through the imported ``lua_setfield`` API.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_callbacks import (
    ANALYSIS_KIND as CALLBACK_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as CALLBACK_STRUCTURE_VERIFICATION_KIND,
    NativeLuaCClosureError,
    validate_native_lua_cclosure_callback_census,
    validate_native_lua_cclosure_callback_structure,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_CALL_ANALYSIS_KIND,
    CALL_FORM as DIRECT_CALL_FORM,
    NativeLuaDirectCallError,
    SUPPORTED_CAPSTONE_VERSION,
    _decoder,
    _load_executable,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_immediate_cclosure_setfield_publication_census"
VERIFICATION_KIND = (
    "pe_native_lua_immediate_cclosure_setfield_publication_census_verification"
)
STRUCTURE_VERIFICATION_KIND = (
    "pe_native_lua_immediate_cclosure_setfield_publication_census_"
    "structure_verification"
)
LUA_LIBRARY = "lua5.1.dll"
LUA_SETFIELD = "lua_setfield"
PUBLICATION_FORM = (
    "x86_cdecl_cleanup12_key_imm32_table_minus2_same_state_"
    "lua_setfield_ff15"
)
UNMATCHED_RESOLUTION = "no_exact_contiguous_setfield_publication"
MAX_KEY_BYTES = 128
MAX_TEXT = 1024
_RVA_RE = re.compile(r"0x[0-9a-f]{8}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

_METHOD = {
    "callback_prerequisite_exactly_verified": True,
    "accepted_publication": (
        "Immediately after one exactly resolved direct lua_pushcclosure call, "
        "the same atlas range must contain contiguous x86 instructions with "
        "bytes for add esp,12; push imm32 key VA; push -2; push the same "
        "Lua-state register; and an exact direct FF 15 lua_setfield import "
        "call. The pointed key must be a bounded NUL-terminated ASCII string."
    ),
    "partition": (
        "Every resolved immediate callback site is retained exactly once as "
        "either an accepted setfield publication or an unmatched resolved "
        "site. Unmatched sites do not acquire a publication target."
    ),
    "relation_semantics": (
        "An accepted edge proves that the newly constructed C closure is the "
        "value immediately consumed by lua_setfield for one exact table index "
        "and key in this static instruction sequence."
    ),
    "publication_boundary": (
        "The artifact publishes normalized RVAs, atlas and instruction hashes, "
        "the bounded field key, prerequisite identities, and aggregates. It "
        "omits instruction bytes, disassembly text, decompiler output, local "
        "paths, variables, and reconstructed source."
    ),
    "not_claimed": [
        "runtime reachability, execution, frequency, or persistence",
        "the dynamic identity, ownership, or lifetime of the target table",
        "global export, ordinary Lua lookup reachability, or later mutation",
        "publication through lua_settable, lua_rawset, or indirect API calls",
        "publication for unmatched or computed callback arguments",
        "function ownership, subsystem, purpose, inputs, or outputs",
        "source-level or behavioral equivalence",
    ],
}


class NativeLuaCClosurePublicationError(RuntimeError):
    """Raised when exact C-closure publication evidence is invalid or stale."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NativeLuaCClosurePublicationError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if type(value) is not list:
        raise NativeLuaCClosurePublicationError(f"{label} must be an array")
    return value


def _rva(value: Any, label: str) -> int:
    if type(value) is not str or _RVA_RE.fullmatch(value) is None:
        raise NativeLuaCClosurePublicationError(
            f"{label} must be a canonical 32-bit RVA"
        )
    return int(value, 16)


def _exact_keys(
    value: Mapping[str, Any], expected: set[str], label: str
) -> None:
    if set(value) != expected:
        raise NativeLuaCClosurePublicationError(
            f"{label} fields differ: expected {sorted(expected)}, got {sorted(value)}"
        )


def _count(value: Any, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < 0 or (positive and value == 0):
        raise NativeLuaCClosurePublicationError(
            f"{label} must be a non-negative count"
        )
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise NativeLuaCClosurePublicationError(
            f"{label} must be a lowercase SHA-256"
        )
    return value


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
                raise NativeLuaCClosurePublicationError(
                    f"{label} has a non-text key"
                )
            _validate_json_tree(item, f"{label}.{key}")
        return
    raise NativeLuaCClosurePublicationError(
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
        raise NativeLuaCClosurePublicationError(
            f"value cannot be canonically encoded: {exc}"
        ) from exc
    return (rendered + "\n").encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _assert_publication_safe(value: Any, label: str = "artifact") -> None:
    if type(value) is str:
        if len(value) > MAX_TEXT or "\0" in value:
            raise NativeLuaCClosurePublicationError(
                f"{label} contains unbounded text"
            )
        if "/" in value or "\\" in value or re.search(r"[A-Za-z]:", value):
            raise NativeLuaCClosurePublicationError(
                f"{label} contains path-like text"
            )
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
                raise NativeLuaCClosurePublicationError(
                    f"{label} has an invalid field name"
                )
            _assert_publication_safe(item, f"{label}.{key}")
        return
    raise NativeLuaCClosurePublicationError(
        f"{label} contains a non-publication value"
    )


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
        raise NativeLuaCClosurePublicationError(
            f"atlas range {_hex(start)} is not contiguous file-backed data"
        )
    expected_va = image.image_base + start
    instructions = list(decoder.disasm(data[offset : offset + size], expected_va))
    decoded_size = 0
    for instruction in instructions:
        if instruction.address != expected_va + decoded_size:
            raise NativeLuaCClosurePublicationError(
                f"atlas range {_hex(start)} decoded non-contiguously"
            )
        decoded_size += instruction.size
    if decoded_size != size:
        raise NativeLuaCClosurePublicationError(
            f"atlas range {_hex(start)} did not decode completely"
        )
    return instructions


def _read_ascii_key(
    data: bytes,
    image: Any,
    key_rva: int,
) -> tuple[str, bytes]:
    raw = bytearray()
    previous_offset: int | None = None
    for delta in range(MAX_KEY_BYTES + 1):
        offset = image.rva_to_file_offset(key_rva + delta)
        if offset is None or offset >= len(data):
            raise NativeLuaCClosurePublicationError(
                "setfield key is not a bounded file-backed string"
            )
        if previous_offset is not None and offset != previous_offset + 1:
            raise NativeLuaCClosurePublicationError(
                "setfield key is not contiguously file-backed"
            )
        previous_offset = offset
        value = data[offset]
        if value == 0:
            if not raw:
                raise NativeLuaCClosurePublicationError(
                    "setfield key must not be empty"
                )
            break
        if value < 0x20 or value > 0x7E:
            raise NativeLuaCClosurePublicationError(
                "setfield key must be printable ASCII"
            )
        raw.append(value)
    else:  # pragma: no cover - loop always terminates or raises
        raise NativeLuaCClosurePublicationError(
            "setfield key exceeds the publication limit"
        )
    if len(raw) > MAX_KEY_BYTES:
        raise NativeLuaCClosurePublicationError(
            "setfield key exceeds the publication limit"
        )
    return raw.decode("ascii"), bytes(raw)


def _atlas_functions(
    program_facts: Mapping[str, Any],
) -> dict[int, Mapping[str, Any]]:
    functions: dict[int, Mapping[str, Any]] = {}
    for index, raw in enumerate(
        _array(program_facts.get("functions"), "program_facts.functions")
    ):
        function = _mapping(raw, f"program_facts.functions[{index}]")
        entry = _rva(function.get("entry_rva"), f"function {index}.entry_rva")
        if entry in functions:
            raise NativeLuaCClosurePublicationError(
                "program-facts atlas entries must be unique"
            )
        functions[entry] = function
    return functions


def _direct_setfield_calls(
    direct_calls: Mapping[str, Any],
) -> dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]]:
    imports = [
        _mapping(item, "direct_calls.lua_imports item")
        for item in _array(
            direct_calls.get("lua_imports"), "direct_calls.lua_imports"
        )
        if isinstance(item, Mapping) and item.get("name") == LUA_SETFIELD
    ]
    if len(imports) != 1 or imports[0].get("library") != LUA_LIBRARY:
        raise NativeLuaCClosurePublicationError(
            "direct-call census must contain one lua_setfield import"
        )
    calls: dict[int, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    for record_index, raw_record in enumerate(
        _array(direct_calls.get("records"), "direct_calls.records")
    ):
        record = _mapping(raw_record, f"direct_calls.records[{record_index}]")
        for raw_call in _array(
            record.get("direct_lua_import_calls"),
            f"direct_calls.records[{record_index}].direct_lua_import_calls",
        ):
            call = _mapping(raw_call, "direct Lua call")
            if call.get("import_name") != LUA_SETFIELD:
                continue
            if (
                call.get("library") != LUA_LIBRARY
                or call.get("call_form") != DIRECT_CALL_FORM
                or call.get("iat_rva") != imports[0].get("iat_rva")
            ):
                raise NativeLuaCClosurePublicationError(
                    "lua_setfield direct-call facts disagree"
                )
            call_rva = _rva(call.get("call_rva"), "lua_setfield.call_rva")
            if call_rva in calls:
                raise NativeLuaCClosurePublicationError(
                    "lua_setfield direct-call RVAs must be unique"
                )
            calls[call_rva] = (record, call)
    expected = imports[0].get("direct_call_sites")
    if type(expected) is not int or expected != len(calls):
        raise NativeLuaCClosurePublicationError(
            "lua_setfield call partition differs from import aggregate"
        )
    return calls


def _containing_range(
    function: Mapping[str, Any],
    call_rva: int,
) -> tuple[int, int]:
    matches: list[tuple[int, int]] = []
    for index, raw_range in enumerate(
        _array(function.get("ranges"), "caller.ranges")
    ):
        body_range = _mapping(raw_range, f"caller.ranges[{index}]")
        start = _rva(body_range.get("start_rva"), "caller range start_rva")
        size = body_range.get("size")
        if type(size) is not int or size <= 0:
            raise NativeLuaCClosurePublicationError(
                "caller range size must be positive"
            )
        if start <= call_rva and call_rva + 6 <= start + size:
            matches.append((start, size))
    if len(matches) != 1:
        raise NativeLuaCClosurePublicationError(
            "callback call must lie in exactly one caller atlas range"
        )
    return matches[0]


def build_native_lua_cclosure_setfield_publication_census(
    executable: Path,
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact immediate-closure direct-setfield publication census."""
    for value, label in (
        (direct_calls, "direct_calls"),
        (callback_census, "callback_census"),
        (program_facts, "program_facts"),
        (inventory, "inventory"),
    ):
        _validate_json_tree(value, label)
    if direct_calls.get("analysis_kind") != DIRECT_CALL_ANALYSIS_KIND:
        raise NativeLuaCClosurePublicationError(
            "direct-call prerequisite has the wrong kind"
        )
    if callback_census.get("analysis_kind") != CALLBACK_ANALYSIS_KIND:
        raise NativeLuaCClosurePublicationError(
            "callback prerequisite has the wrong kind"
        )
    try:
        callback_verification = validate_native_lua_cclosure_callback_census(
            executable,
            callback_census,
            direct_calls,
            program_facts,
            inventory=inventory,
        )
        data, image, executable_sha256 = _load_executable(executable)
        decoder, _call_id = _decoder()
    except (
        NativeLuaCClosureError,
        NativeLuaDirectCallError,
        PEAnchorError,
    ) as exc:
        raise NativeLuaCClosurePublicationError(
            f"callback prerequisite failed exact verification: {exc}"
        ) from exc
    identity = _mapping(
        callback_census.get("build_identity"),
        "callback_census.build_identity",
    )
    if (
        identity.get("executable_sha256") != executable_sha256
        or identity.get("executable_size") != len(data)
        or identity.get("architecture") != image.architecture
    ):
        raise NativeLuaCClosurePublicationError(
            "executable changed after callback prerequisite verification"
        )
    callback_sha256 = _canonical_sha256(callback_census)
    if callback_verification.get("evidence_sha256") != callback_sha256:
        raise NativeLuaCClosurePublicationError(
            "callback canonical identity disagrees"
        )

    functions = _atlas_functions(program_facts)
    setfield_calls = _direct_setfield_calls(direct_calls)
    resolved_sites = [
        _mapping(item, f"callback_census.resolved_sites[{index}]")
        for index, item in enumerate(
            _array(
                callback_census.get("resolved_sites"),
                "callback_census.resolved_sites",
            )
        )
    ]
    resolved_sites.sort(
        key=lambda site: _rva(site.get("call_rva"), "resolved call_rva")
    )

    publications: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    decoded_ranges: dict[tuple[int, int], list[Any]] = {}
    for site in resolved_sites:
        callback_call_rva = _rva(site.get("call_rva"), "resolved call_rva")
        caller_entry = _rva(
            site.get("caller_entry_rva"), "resolved caller_entry_rva"
        )
        callback_entry = _rva(
            site.get("callback_entry_rva"), "resolved callback_entry_rva"
        )
        if (
            site.get("upvalue_argument_kind") != "immediate"
            or site.get("literal_upvalue_count") != 0
        ):
            unmatched.append(
                {
                    "caller_entry_rva": site["caller_entry_rva"],
                    "caller_atlas_record_sha256": site[
                        "caller_atlas_record_sha256"
                    ],
                    "callback_call_rva": site["call_rva"],
                    "callback_entry_rva": site["callback_entry_rva"],
                    "callback_atlas_record_sha256": site[
                        "callback_atlas_record_sha256"
                    ],
                    "resolution": UNMATCHED_RESOLUTION,
                }
            )
            continue
        caller = functions.get(caller_entry)
        callback = functions.get(callback_entry)
        if caller is None or callback is None:
            raise NativeLuaCClosurePublicationError(
                "resolved callback site does not join the exact atlas"
            )
        if site.get("caller_atlas_record_sha256") != atlas_record_sha256(caller):
            raise NativeLuaCClosurePublicationError(
                "resolved callback caller hash differs from atlas"
            )
        if site.get("callback_atlas_record_sha256") != atlas_record_sha256(
            callback
        ):
            raise NativeLuaCClosurePublicationError(
                "resolved callback target hash differs from atlas"
            )
        body_range = _containing_range(caller, callback_call_rva)
        if body_range not in decoded_ranges:
            decoded_ranges[body_range] = _decode_range(
                data, image, body_range[0], body_range[1], decoder
            )
        instructions = decoded_ranges[body_range]
        index_by_rva = {
            instruction.address - image.image_base: index
            for index, instruction in enumerate(instructions)
        }
        call_index = index_by_rva.get(callback_call_rva)
        state_push_rva = _rva(
            _mapping(site.get("state_push"), "resolved state_push").get("rva"),
            "resolved state_push.rva",
        )
        state_index = index_by_rva.get(state_push_rva)
        if call_index is None or state_index is None:
            raise NativeLuaCClosurePublicationError(
                "resolved callback instructions are absent from caller decode"
            )
        callback_instruction = instructions[call_index]
        state_instruction = instructions[state_index]
        if (
            hashlib.sha256(bytes(callback_instruction.bytes)).hexdigest()
            != site.get("call_instruction_sha256")
            or hashlib.sha256(bytes(state_instruction.bytes)).hexdigest()
            != _mapping(site.get("state_push"), "resolved state_push").get(
                "sha256"
            )
        ):
            raise NativeLuaCClosurePublicationError(
                "resolved callback instruction hashes differ from executable"
            )

        following = instructions[call_index + 1 : call_index + 6]
        accepted = len(following) == 5
        if accepted:
            cleanup, key_push, table_push, publication_state, setter = following
            setter_rva = setter.address - image.image_base
            expected_setter = setfield_calls.get(setter_rva)
            expected_setter_bytes = None
            if expected_setter is not None:
                iat_rva = _rva(
                    expected_setter[1].get("iat_rva"),
                    "lua_setfield.iat_rva",
                )
                expected_setter_bytes = b"\xff\x15" + struct.pack(
                    "<I", image.image_base + iat_rva
                )
            accepted = (
                bytes(cleanup.bytes) == b"\x83\xc4\x0c"
                and len(key_push.bytes) == 5
                and bytes(key_push.bytes[:1]) == b"\x68"
                and bytes(table_push.bytes) == b"\x6a\xfe"
                and bytes(publication_state.bytes) == bytes(state_instruction.bytes)
                and len(publication_state.bytes) == 1
                and 0x50 <= publication_state.bytes[0] <= 0x57
                and expected_setter is not None
                and expected_setter[0].get("entry_rva")
                == site.get("caller_entry_rva")
                and bytes(setter.bytes) == expected_setter_bytes
                and hashlib.sha256(bytes(setter.bytes)).hexdigest()
                == expected_setter[1].get("instruction_sha256")
            )
        if not accepted:
            unmatched.append(
                {
                    "caller_entry_rva": site["caller_entry_rva"],
                    "caller_atlas_record_sha256": site[
                        "caller_atlas_record_sha256"
                    ],
                    "callback_call_rva": site["call_rva"],
                    "callback_entry_rva": site["callback_entry_rva"],
                    "callback_atlas_record_sha256": site[
                        "callback_atlas_record_sha256"
                    ],
                    "resolution": UNMATCHED_RESOLUTION,
                }
            )
            continue

        key_va = struct.unpack("<I", bytes(key_push.bytes)[1:5])[0]
        if key_va < image.image_base:
            raise NativeLuaCClosurePublicationError(
                "setfield key VA precedes the PE image"
            )
        key_rva = key_va - image.image_base
        key_text, key_bytes = _read_ascii_key(data, image, key_rva)
        setter_record, setter_call = expected_setter
        publications.append(
            {
                "publication_form": PUBLICATION_FORM,
                "caller_entry_rva": site["caller_entry_rva"],
                "caller_atlas_record_sha256": site[
                    "caller_atlas_record_sha256"
                ],
                "callback_call_rva": site["call_rva"],
                "callback_call_instruction_sha256": site[
                    "call_instruction_sha256"
                ],
                "callback_entry_rva": site["callback_entry_rva"],
                "callback_atlas_record_sha256": site[
                    "callback_atlas_record_sha256"
                ],
                "cleanup_instruction": _instruction_fact(
                    cleanup, image.image_base
                ),
                "key_push": _instruction_fact(key_push, image.image_base),
                "key_rva": _hex(key_rva),
                "key_text": key_text,
                "key_byte_length": len(key_bytes),
                "key_sha256": hashlib.sha256(key_bytes).hexdigest(),
                "table_index": -2,
                "table_index_push": _instruction_fact(
                    table_push, image.image_base
                ),
                "state_push": _instruction_fact(
                    publication_state, image.image_base
                ),
                "setter_call_rva": setter_call["call_rva"],
                "setter_call_instruction_sha256": setter_call[
                    "instruction_sha256"
                ],
                "library": LUA_LIBRARY,
                "setter_import_name": LUA_SETFIELD,
                "setter_iat_rva": setter_call["iat_rva"],
            }
        )

    if len(publications) + len(unmatched) != len(resolved_sites):
        raise NativeLuaCClosurePublicationError(
            "resolved callback publication partition disagrees"
        )
    publications.sort(key=lambda item: _rva(item["callback_call_rva"], "call"))
    unmatched.sort(key=lambda item: _rva(item["callback_call_rva"], "call"))

    by_builder: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for publication in publications:
        by_builder[publication["caller_entry_rva"]].append(publication)
        by_target[publication["callback_entry_rva"]].append(publication)
    builders = [
        {
            "builder_entry_rva": entry,
            "builder_atlas_record_sha256": items[0][
                "caller_atlas_record_sha256"
            ],
            "publication_site_count": len(items),
            "registered_callback_entry_rvas": sorted(
                {item["callback_entry_rva"] for item in items}
            ),
            "key_texts": sorted({item["key_text"] for item in items}),
        }
        for entry, items in sorted(
            by_builder.items(), key=lambda pair: _rva(pair[0], "builder entry")
        )
    ]
    registered_targets = [
        {
            "callback_entry_rva": entry,
            "callback_atlas_record_sha256": items[0][
                "callback_atlas_record_sha256"
            ],
            "publication_site_count": len(items),
            "builder_entry_rvas": sorted(
                {item["caller_entry_rva"] for item in items}
            ),
            "key_texts": sorted({item["key_text"] for item in items}),
        }
        for entry, items in sorted(
            by_target.items(), key=lambda pair: _rva(pair[0], "callback entry")
        )
    ]

    direct_atlas = _mapping(direct_calls.get("atlas"), "direct_calls.atlas")
    callback_summary = _mapping(
        callback_census.get("summary"), "callback_census.summary"
    )
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
            "canonical_sha256": callback_sha256,
            "resolved_immediate_callback_sites": callback_summary.get(
                "resolved_immediate_callback_sites"
            ),
        },
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "accepted_publication_form": PUBLICATION_FORM,
        },
        "publications": publications,
        "unmatched_resolved_sites": unmatched,
        "builders": builders,
        "registered_targets": registered_targets,
        "method": _METHOD,
        "summary": {
            "resolved_immediate_callback_sites": len(resolved_sites),
            "matched_setfield_publication_sites": len(publications),
            "unmatched_resolved_callback_sites": len(unmatched),
            "unique_registered_callback_targets": len(registered_targets),
            "unique_registration_builders": len(builders),
            "unique_key_texts": len(
                {item["key_text"] for item in publications}
            ),
            "schema_violations": 0,
        },
    }
    _assert_publication_safe(result)
    return result


def validate_native_lua_cclosure_setfield_publication_census(
    executable: Path,
    evidence: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and canonical-byte-compare one setfield publication census."""
    _validate_json_tree(evidence, "evidence")
    rebuilt = build_native_lua_cclosure_setfield_publication_census(
        executable,
        direct_calls,
        callback_census,
        program_facts,
        inventory=inventory,
    )
    if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
        raise NativeLuaCClosurePublicationError(
            "native Lua setfield publication evidence differs from exact rebuild"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": dict(
            _mapping(rebuilt["build_identity"], "build_identity")
        ),
        "evidence_sha256": _canonical_sha256(rebuilt),
        "summary": dict(_mapping(rebuilt["summary"], "summary")),
    }


def _instruction_structure(value: Any, label: str) -> tuple[int, int, str]:
    """Validate one normalized instruction fact without reading PE bytes."""
    fact = _mapping(value, label)
    _exact_keys(fact, {"rva", "size", "sha256"}, label)
    return (
        _rva(fact["rva"], f"{label}.rva"),
        _count(fact["size"], f"{label}.size", positive=True),
        _sha256(fact["sha256"], f"{label}.sha256"),
    )


def _instruction_sha256(encoded: bytes) -> str:
    return hashlib.sha256(encoded).hexdigest()


def _register_push_sha256es() -> set[str]:
    return {
        _instruction_sha256(bytes([opcode])) for opcode in range(0x50, 0x58)
    }


def _require_register_push(fact: tuple[int, int, str], label: str) -> None:
    _rva_value, size, digest = fact
    if size != 1 or digest not in _register_push_sha256es():
        raise NativeLuaCClosurePublicationError(
            f"{label} must be one exact x86 register PUSH encoding"
        )


def validate_native_lua_cclosure_setfield_publication_structure(
    evidence: Mapping[str, Any],
    direct_calls: Mapping[str, Any],
    callback_census: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the whole publication artifact without reading an executable.

    This first validates the complete callback structural prerequisite, then
    checks every published join, partition, and finite x86 encoding derivable
    from the documents.  It is not binary proof: the key pointer's file bytes
    and decoded control-flow/instruction existence at the published RVAs still
    require :func:`validate_native_lua_cclosure_setfield_publication_census`.
    """
    for value, label in (
        (evidence, "evidence"),
        (direct_calls, "direct_calls"),
        (callback_census, "callback_census"),
        (program_facts, "program_facts"),
    ):
        _validate_json_tree(value, label)
    evidence = _mapping(evidence, "evidence")
    direct_calls = _mapping(direct_calls, "direct_calls")
    callback_census = _mapping(callback_census, "callback_census")
    facts = _mapping(program_facts, "program_facts")
    try:
        callback_verification = validate_native_lua_cclosure_callback_structure(
            callback_census, direct_calls, facts
        )
    except NativeLuaCClosureError as exc:
        raise NativeLuaCClosurePublicationError(
            f"callback structural prerequisite failed: {exc}"
        ) from exc
    if (
        callback_verification.get("analysis_kind")
        != CALLBACK_STRUCTURE_VERIFICATION_KIND
        or callback_verification.get("status") != "structurally_verified"
    ):
        raise NativeLuaCClosurePublicationError(
            "callback structural prerequisite returned an unexpected result"
        )

    _exact_keys(
        evidence,
        {
            "schema_version",
            "analysis_kind",
            "build_identity",
            "atlas",
            "direct_call_census",
            "callback_census",
            "decoder",
            "publications",
            "unmatched_resolved_sites",
            "builders",
            "registered_targets",
            "method",
            "summary",
        },
        "evidence",
    )
    if type(evidence["schema_version"]) is not int or evidence["schema_version"] != SCHEMA_VERSION:
        raise NativeLuaCClosurePublicationError(
            "unsupported native Lua setfield publication schema"
        )
    if evidence["analysis_kind"] != ANALYSIS_KIND:
        raise NativeLuaCClosurePublicationError(
            "unexpected native Lua setfield publication analysis kind"
        )
    identity = _mapping(facts.get("identity"), "program_facts.identity")
    if (
        evidence["build_identity"] != dict(identity)
        or evidence["build_identity"] != callback_census.get("build_identity")
        or evidence["build_identity"] != direct_calls.get("build_identity")
    ):
        raise NativeLuaCClosurePublicationError(
            "publication build identity does not match prerequisites and program facts"
        )
    ghidra = _mapping(facts.get("ghidra"), "program_facts.ghidra")
    image_base = _rva(ghidra.get("image_base"), "program_facts.ghidra.image_base")

    direct_atlas = _mapping(direct_calls.get("atlas"), "direct_calls.atlas")
    atlas = _mapping(evidence["atlas"], "evidence.atlas")
    _exact_keys(
        atlas,
        {"analysis_kind", "canonical_sha256", "function_count"},
        "evidence.atlas",
    )
    expected_atlas = {
        "analysis_kind": direct_atlas.get("analysis_kind"),
        "canonical_sha256": direct_atlas.get("canonical_sha256"),
        "function_count": direct_atlas.get("function_count"),
    }
    if atlas != expected_atlas:
        raise NativeLuaCClosurePublicationError(
            "publication atlas identity or aggregate differs from direct calls"
        )
    _sha256(atlas["canonical_sha256"], "evidence.atlas.canonical_sha256")
    _count(atlas["function_count"], "evidence.atlas.function_count")

    direct_census = _mapping(
        evidence["direct_call_census"], "evidence.direct_call_census"
    )
    _exact_keys(
        direct_census,
        {"analysis_kind", "canonical_sha256"},
        "evidence.direct_call_census",
    )
    if direct_census != {
        "analysis_kind": DIRECT_CALL_ANALYSIS_KIND,
        "canonical_sha256": _canonical_sha256(direct_calls),
    }:
        raise NativeLuaCClosurePublicationError(
            "publication direct-call prerequisite identity differs"
        )
    _sha256(
        direct_census["canonical_sha256"],
        "evidence.direct_call_census.canonical_sha256",
    )

    callback_summary = _mapping(
        callback_census.get("summary"), "callback_census.summary"
    )
    callback_identity = _mapping(
        evidence["callback_census"], "evidence.callback_census"
    )
    _exact_keys(
        callback_identity,
        {
            "analysis_kind",
            "canonical_sha256",
            "resolved_immediate_callback_sites",
        },
        "evidence.callback_census",
    )
    expected_callback_identity = {
        "analysis_kind": CALLBACK_ANALYSIS_KIND,
        "canonical_sha256": _canonical_sha256(callback_census),
        "resolved_immediate_callback_sites": callback_summary.get(
            "resolved_immediate_callback_sites"
        ),
    }
    if callback_identity != expected_callback_identity:
        raise NativeLuaCClosurePublicationError(
            "publication callback prerequisite identity or aggregate differs"
        )
    _sha256(
        callback_identity["canonical_sha256"],
        "evidence.callback_census.canonical_sha256",
    )
    _count(
        callback_identity["resolved_immediate_callback_sites"],
        "evidence.callback_census.resolved_immediate_callback_sites",
    )

    decoder = _mapping(evidence["decoder"], "evidence.decoder")
    _exact_keys(
        decoder,
        {
            "name",
            "version",
            "architecture",
            "mode_bits",
            "accepted_publication_form",
        },
        "evidence.decoder",
    )
    if decoder != {
        "name": "capstone",
        "version": SUPPORTED_CAPSTONE_VERSION,
        "architecture": "x86",
        "mode_bits": 32,
        "accepted_publication_form": PUBLICATION_FORM,
    }:
        raise NativeLuaCClosurePublicationError(
            "publication decoder contract has drifted"
        )
    if _canonical_bytes(evidence["method"]) != _canonical_bytes(_METHOD):
        raise NativeLuaCClosurePublicationError(
            "publication method contract has drifted"
        )

    functions = _atlas_functions(facts)
    resolved_by_call: dict[int, Mapping[str, Any]] = {}
    for index, raw_site in enumerate(
        _array(callback_census.get("resolved_sites"), "callback_census.resolved_sites")
    ):
        site = _mapping(raw_site, f"callback_census.resolved_sites[{index}]")
        call_rva = _rva(site.get("call_rva"), "callback resolved call_rva")
        if call_rva in resolved_by_call:
            raise NativeLuaCClosurePublicationError(
                "callback resolved call RVAs must be unique"
            )
        resolved_by_call[call_rva] = site
    setfield_calls = _direct_setfield_calls(direct_calls)

    publication_keys = {
        "publication_form",
        "caller_entry_rva",
        "caller_atlas_record_sha256",
        "callback_call_rva",
        "callback_call_instruction_sha256",
        "callback_entry_rva",
        "callback_atlas_record_sha256",
        "cleanup_instruction",
        "key_push",
        "key_rva",
        "key_text",
        "key_byte_length",
        "key_sha256",
        "table_index",
        "table_index_push",
        "state_push",
        "setter_call_rva",
        "setter_call_instruction_sha256",
        "library",
        "setter_import_name",
        "setter_iat_rva",
    }
    unmatched_keys = {
        "caller_entry_rva",
        "caller_atlas_record_sha256",
        "callback_call_rva",
        "callback_entry_rva",
        "callback_atlas_record_sha256",
        "resolution",
    }
    seen_calls: set[int] = set()
    previous_publication = -1
    by_builder: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_target: dict[str, list[Mapping[str, Any]]] = defaultdict(list)

    def source_site(site: Mapping[str, Any], label: str) -> tuple[int, Mapping[str, Any], tuple[int, int]]:
        callback_call = _rva(site["callback_call_rva"], f"{label}.callback_call_rva")
        source = resolved_by_call.get(callback_call)
        if source is None:
            raise NativeLuaCClosurePublicationError(
                f"{label}.callback_call_rva is not a resolved callback site"
            )
        for key in (
            "caller_entry_rva",
            "caller_atlas_record_sha256",
            "callback_entry_rva",
            "callback_atlas_record_sha256",
        ):
            if site[key] != source.get(key):
                raise NativeLuaCClosurePublicationError(
                    f"{label}.{key} does not join the exact callback site"
                )
        caller_entry = _rva(site["caller_entry_rva"], f"{label}.caller_entry_rva")
        caller = functions.get(caller_entry)
        if caller is None:
            raise NativeLuaCClosurePublicationError(
                f"{label}.caller_entry_rva is absent from the atlas"
            )
        if site["caller_atlas_record_sha256"] != atlas_record_sha256(caller):
            raise NativeLuaCClosurePublicationError(
                f"{label}.caller_atlas_record_sha256 does not match atlas"
            )
        ranges = []
        for range_index, raw_range in enumerate(
            _array(caller.get("ranges"), f"{label}.caller_ranges")
        ):
            body_range = _mapping(raw_range, f"{label}.caller_ranges[{range_index}]")
            start = _rva(
                body_range.get("start_rva"),
                f"{label}.caller_ranges[{range_index}].start_rva",
            )
            size = _count(
                body_range.get("size"),
                f"{label}.caller_ranges[{range_index}].size",
                positive=True,
            )
            if start <= callback_call and callback_call + 6 <= start + size:
                ranges.append((start, size))
        if len(ranges) != 1:
            raise NativeLuaCClosurePublicationError(
                f"{label}.callback_call_rva must lie in one caller atlas range"
            )
        return callback_call, source, ranges[0]

    def require_range(
        fact: tuple[int, int, str], caller_range: tuple[int, int], label: str
    ) -> None:
        if fact[0] < caller_range[0] or fact[0] + fact[1] > caller_range[0] + caller_range[1]:
            raise NativeLuaCClosurePublicationError(
                f"{label} does not lie within the exact caller atlas range"
            )

    for index, raw_publication in enumerate(
        _array(evidence["publications"], "evidence.publications")
    ):
        label = f"evidence.publications[{index}]"
        publication = _mapping(raw_publication, label)
        _exact_keys(publication, publication_keys, label)
        callback_call, source, caller_range = source_site(publication, label)
        if (
            source.get("upvalue_argument_kind") != "immediate"
            or source.get("literal_upvalue_count") != 0
        ):
            raise NativeLuaCClosurePublicationError(
                f"{label} source must preserve the exact zero-upvalue acceptance gate"
            )
        if callback_call <= previous_publication or callback_call in seen_calls:
            raise NativeLuaCClosurePublicationError(
                "publications must be unique and callback-call-RVA ordered"
            )
        previous_publication = callback_call
        seen_calls.add(callback_call)
        if publication["publication_form"] != PUBLICATION_FORM:
            raise NativeLuaCClosurePublicationError(
                f"{label}.publication_form has drifted"
            )
        if publication["callback_call_instruction_sha256"] != source.get(
            "call_instruction_sha256"
        ):
            raise NativeLuaCClosurePublicationError(
                f"{label}.callback_call_instruction_sha256 does not join callback"
            )
        _sha256(
            publication["callback_call_instruction_sha256"],
            f"{label}.callback_call_instruction_sha256",
        )
        callback_entry = _rva(
            publication["callback_entry_rva"], f"{label}.callback_entry_rva"
        )
        callback = functions.get(callback_entry)
        if callback is None or callback.get("thunk") is not False:
            raise NativeLuaCClosurePublicationError(
                f"{label}.callback_entry_rva must be a non-thunk atlas entry"
            )
        if publication["callback_atlas_record_sha256"] != atlas_record_sha256(callback):
            raise NativeLuaCClosurePublicationError(
                f"{label}.callback_atlas_record_sha256 does not match atlas"
            )

        cleanup = _instruction_structure(
            publication["cleanup_instruction"], f"{label}.cleanup_instruction"
        )
        key_push = _instruction_structure(publication["key_push"], f"{label}.key_push")
        table_push = _instruction_structure(
            publication["table_index_push"], f"{label}.table_index_push"
        )
        state_push = _instruction_structure(
            publication["state_push"], f"{label}.state_push"
        )
        for fact, fact_label in (
            (cleanup, f"{label}.cleanup_instruction"),
            (key_push, f"{label}.key_push"),
            (table_push, f"{label}.table_index_push"),
            (state_push, f"{label}.state_push"),
        ):
            require_range(fact, caller_range, fact_label)
        if (
            cleanup != (
                callback_call + 6,
                3,
                _instruction_sha256(b"\x83\xc4\x0c"),
            )
            or key_push[0] != cleanup[0] + cleanup[1]
            or table_push[0] != key_push[0] + key_push[1]
            or state_push[0] != table_push[0] + table_push[1]
        ):
            raise NativeLuaCClosurePublicationError(
                f"{label} publication instructions are not the exact contiguous sequence"
            )
        if publication["table_index"] != -2 or table_push[1:] != (
            2,
            _instruction_sha256(b"\x6a\xfe"),
        ):
            raise NativeLuaCClosurePublicationError(
                f"{label}.table_index_push does not reconstruct table index -2"
            )
        _require_register_push(state_push, f"{label}.state_push")
        source_state = _instruction_structure(
            source.get("state_push"), f"{label}.callback_state_push"
        )
        if state_push[2] != source_state[2]:
            raise NativeLuaCClosurePublicationError(
                f"{label}.state_push does not match callback state register"
            )

        key_rva = _rva(publication["key_rva"], f"{label}.key_rva")
        key_text = publication["key_text"]
        if (
            type(key_text) is not str
            or not key_text
            or len(key_text) > MAX_KEY_BYTES
            or "\0" in key_text
        ):
            raise NativeLuaCClosurePublicationError(
                f"{label}.key_text must be bounded non-empty ASCII"
            )
        try:
            key_bytes = key_text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise NativeLuaCClosurePublicationError(
                f"{label}.key_text must be printable ASCII"
            ) from exc
        if any(byte < 0x20 or byte > 0x7E for byte in key_bytes):
            raise NativeLuaCClosurePublicationError(
                f"{label}.key_text must be printable ASCII"
            )
        if (
            publication["key_byte_length"] != len(key_bytes)
            or publication["key_sha256"] != _instruction_sha256(key_bytes)
        ):
            raise NativeLuaCClosurePublicationError(
                f"{label} key text, length, or SHA-256 disagrees"
            )
        _sha256(publication["key_sha256"], f"{label}.key_sha256")
        key_va = image_base + key_rva
        if key_va > 0xFFFFFFFF:
            raise NativeLuaCClosurePublicationError(
                f"{label}.key_rva overflows the x86 image VA"
            )
        if key_push[1:] != (
            5,
            _instruction_sha256(b"\x68" + key_va.to_bytes(4, "little")),
        ):
            raise NativeLuaCClosurePublicationError(
                f"{label}.key_push does not reconstruct from key_rva"
            )

        setter_call = _rva(
            publication["setter_call_rva"], f"{label}.setter_call_rva"
        )
        expected_setter = setfield_calls.get(setter_call)
        if expected_setter is None or expected_setter[0].get("entry_rva") != publication["caller_entry_rva"]:
            raise NativeLuaCClosurePublicationError(
                f"{label}.setter_call_rva does not join the exact direct lua_setfield call"
            )
        direct_setter = expected_setter[1]
        if (
            publication["library"] != LUA_LIBRARY
            or publication["setter_import_name"] != LUA_SETFIELD
            or publication["setter_iat_rva"] != direct_setter.get("iat_rva")
            or publication["setter_call_instruction_sha256"]
            != direct_setter.get("instruction_sha256")
            or setter_call != state_push[0] + state_push[1]
        ):
            raise NativeLuaCClosurePublicationError(
                f"{label} setter fields do not join the exact direct lua_setfield call"
            )
        setter_iat = _rva(
            publication["setter_iat_rva"], f"{label}.setter_iat_rva"
        )
        setter_va = image_base + setter_iat
        if setter_va > 0xFFFFFFFF:
            raise NativeLuaCClosurePublicationError(
                f"{label}.setter_iat_rva overflows the x86 image VA"
            )
        if publication["setter_call_instruction_sha256"] != _instruction_sha256(
            b"\xff\x15" + setter_va.to_bytes(4, "little")
        ):
            raise NativeLuaCClosurePublicationError(
                f"{label}.setter_call_instruction_sha256 does not reconstruct from IAT"
            )
        if setter_call + 6 > caller_range[0] + caller_range[1]:
            raise NativeLuaCClosurePublicationError(
                f"{label}.setter_call_rva does not lie within the exact caller atlas range"
            )
        by_builder[publication["caller_entry_rva"]].append(publication)
        by_target[publication["callback_entry_rva"]].append(publication)

    previous_unmatched = -1
    for index, raw_unmatched in enumerate(
        _array(evidence["unmatched_resolved_sites"], "evidence.unmatched_resolved_sites")
    ):
        label = f"evidence.unmatched_resolved_sites[{index}]"
        unmatched = _mapping(raw_unmatched, label)
        _exact_keys(unmatched, unmatched_keys, label)
        callback_call, _source, _caller_range = source_site(unmatched, label)
        if callback_call <= previous_unmatched or callback_call in seen_calls:
            raise NativeLuaCClosurePublicationError(
                "unmatched resolved sites must be unique and callback-call-RVA ordered"
            )
        previous_unmatched = callback_call
        seen_calls.add(callback_call)
        if unmatched["resolution"] != UNMATCHED_RESOLUTION:
            raise NativeLuaCClosurePublicationError(
                f"{label}.resolution must preserve unmatched status"
            )

    if seen_calls != set(resolved_by_call):
        raise NativeLuaCClosurePublicationError(
            "publication and unmatched sites do not exactly partition resolved callbacks"
        )

    expected_builders = [
        {
            "builder_entry_rva": entry,
            "builder_atlas_record_sha256": items[0]["caller_atlas_record_sha256"],
            "publication_site_count": len(items),
            "registered_callback_entry_rvas": sorted(
                {item["callback_entry_rva"] for item in items}
            ),
            "key_texts": sorted({item["key_text"] for item in items}),
        }
        for entry, items in sorted(
            by_builder.items(), key=lambda item: _rva(item[0], "builder entry")
        )
    ]
    expected_targets = [
        {
            "callback_entry_rva": entry,
            "callback_atlas_record_sha256": items[0][
                "callback_atlas_record_sha256"
            ],
            "publication_site_count": len(items),
            "builder_entry_rvas": sorted(
                {item["caller_entry_rva"] for item in items}
            ),
            "key_texts": sorted({item["key_text"] for item in items}),
        }
        for entry, items in sorted(
            by_target.items(), key=lambda item: _rva(item[0], "callback entry")
        )
    ]

    builder_keys = {
        "builder_entry_rva",
        "builder_atlas_record_sha256",
        "publication_site_count",
        "registered_callback_entry_rvas",
        "key_texts",
    }
    for index, raw_builder in enumerate(
        _array(evidence["builders"], "evidence.builders")
    ):
        builder = _mapping(raw_builder, f"evidence.builders[{index}]")
        _exact_keys(builder, builder_keys, f"evidence.builders[{index}]")
    if evidence["builders"] != expected_builders:
        raise NativeLuaCClosurePublicationError(
            "builders do not exactly aggregate publication sites"
        )
    target_keys = {
        "callback_entry_rva",
        "callback_atlas_record_sha256",
        "publication_site_count",
        "builder_entry_rvas",
        "key_texts",
    }
    for index, raw_target in enumerate(
        _array(evidence["registered_targets"], "evidence.registered_targets")
    ):
        target = _mapping(raw_target, f"evidence.registered_targets[{index}]")
        _exact_keys(target, target_keys, f"evidence.registered_targets[{index}]")
    if evidence["registered_targets"] != expected_targets:
        raise NativeLuaCClosurePublicationError(
            "registered targets do not exactly aggregate publication sites"
        )

    publications = _array(evidence["publications"], "evidence.publications")
    unmatched_sites = _array(
        evidence["unmatched_resolved_sites"], "evidence.unmatched_resolved_sites"
    )
    expected_summary = {
        "resolved_immediate_callback_sites": len(resolved_by_call),
        "matched_setfield_publication_sites": len(publications),
        "unmatched_resolved_callback_sites": len(unmatched_sites),
        "unique_registered_callback_targets": len(expected_targets),
        "unique_registration_builders": len(expected_builders),
        "unique_key_texts": len(
            {
                _mapping(item, "publication")["key_text"]
                for item in publications
            }
        ),
        "schema_violations": 0,
    }
    summary = _mapping(evidence["summary"], "evidence.summary")
    _exact_keys(summary, set(expected_summary), "evidence.summary")
    for key, value in summary.items():
        _count(value, f"evidence.summary.{key}")
    if summary != expected_summary:
        raise NativeLuaCClosurePublicationError(
            "publication summary aggregates or partitions disagree"
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


def encode_native_lua_cclosure_setfield_publication_census(
    value: Mapping[str, Any],
) -> str:
    """Return deterministic pretty JSON for a publication artifact/result."""
    _validate_json_tree(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
