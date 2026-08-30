"""Exact, build-keyed census of direct Lua 5.1 IAT calls in native atlas bodies.

The census independently decodes every byte in every Ghidra-atlas body range
with one pinned Capstone version.  It records only exact ``call [IAT]`` edges
to named ``lua5.1.dll`` imports.  It does not infer ownership, runtime
reachability, registration roles, callback roles, or source-level semantics.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.pe_anchor_map import MAX_EXECUTABLE_BYTES, PEAnchorError, PEImage
from src.observatory.program_facts import ProgramFactsError, validate_program_facts


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_direct_import_call_census"
VERIFICATION_KIND = "pe_native_lua_direct_import_call_census_verification"
SUPPORTED_CAPSTONE_VERSION = "5.0.7"
LUA_LIBRARY = "lua5.1.dll"
CALL_FORM = "x86_absolute_iat_indirect_call_ff15"
MAX_TEXT = 1024
_RVA_RE = re.compile(r"0x[0-9a-f]{8}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_STABLE_STAT_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns")

_METHOD = {
    "atlas_prerequisite_exactly_verified": True,
    "decoder_scope": (
        "Every byte of every file-backed Ghidra-atlas function body range is "
        "decoded linearly from that range's recorded start with Capstone 5.0.7; "
        "any undecoded byte fails the build."
    ),
    "accepted_edge": (
        "Only a six-byte x86 FF 15 absolute indirect CALL whose encoded address "
        "equals one exact named lua5.1.dll IAT slot is retained."
    ),
    "publication_boundary": (
        "The artifact publishes function and instruction RVAs, canonical atlas "
        "record hashes, instruction hashes and sizes, import names and IAT RVAs, and "
        "counts. It omits instruction bytes, disassembly text, decompiler output, "
        "local paths, variables, and reconstructed source."
    ),
    "relation_semantics": (
        "A retained record proves a direct static call relation from an atlas "
        "body to a named Lua 5.1 import. Direct consumer, registration-builder, "
        "and registered-callable relations may overlap and are not collapsed into "
        "one mutually exclusive classification."
    ),
    "not_claimed": [
        "complete native-function discovery beyond the Ghidra atlas",
        "correct function boundaries beyond the recorded Ghidra analysis",
        "runtime reachability, call success, or call frequency",
        "indirect, computed, dynamically resolved, or non-FF15 Lua calls",
        "absence of Lua interaction for functions without retained calls",
        "function ownership, subsystem, purpose, inputs, or outputs",
        "registration-builder or registered-Lua-callable classification",
        "source-level or behavioral equivalence",
    ],
}


class NativeLuaDirectCallError(RuntimeError):
    """Raised when direct native-to-Lua call evidence is malformed or stale."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NativeLuaDirectCallError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if type(value) is not list:
        raise NativeLuaDirectCallError(f"{label} must be an array")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise NativeLuaDirectCallError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _text(value: Any, label: str) -> str:
    if type(value) is not str or not value or len(value) > MAX_TEXT or "\0" in value:
        raise NativeLuaDirectCallError(f"{label} must be bounded non-empty text")
    return value


def _count(value: Any, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < int(positive):
        qualifier = "positive" if positive else "non-negative"
        raise NativeLuaDirectCallError(f"{label} must be a {qualifier} integer")
    return value


def _rva(value: Any, label: str) -> int:
    if type(value) is not str or _RVA_RE.fullmatch(value) is None:
        raise NativeLuaDirectCallError(f"{label} must be a canonical 32-bit RVA")
    return int(value, 16)


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise NativeLuaDirectCallError(f"{label} must be lowercase SHA-256")
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
                raise NativeLuaDirectCallError(f"{label} contains a non-text key")
            _validate_json_tree(item, f"{label}.{key}")
        return
    raise NativeLuaDirectCallError(
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
        raise NativeLuaDirectCallError(
            f"value cannot be canonically encoded: {exc}"
        ) from exc
    return (rendered + "\n").encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_reparse(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & marker)


def _same_stat(left: os.stat_result, right: os.stat_result) -> bool:
    return all(
        getattr(left, field) == getattr(right, field)
        for field in _STABLE_STAT_FIELDS
    )


def _load_executable(path: Path) -> tuple[bytes, PEImage, str]:
    try:
        link_before = path.lstat()
        path_before = path.stat()
    except OSError as exc:
        raise NativeLuaDirectCallError("executable cannot be inspected") from exc
    if (
        stat.S_ISLNK(link_before.st_mode)
        or _is_reparse(link_before)
        or not stat.S_ISREG(path_before.st_mode)
    ):
        raise NativeLuaDirectCallError(
            "executable must be a regular non-link file"
        )
    if path_before.st_size > MAX_EXECUTABLE_BYTES:
        raise NativeLuaDirectCallError("executable exceeds the analysis size limit")
    try:
        with path.open("rb") as stream:
            handle_before = os.fstat(stream.fileno())
            if not _same_stat(path_before, handle_before):
                raise NativeLuaDirectCallError(
                    "executable changed while being opened"
                )
            data = stream.read(handle_before.st_size + 1)
            handle_after = os.fstat(stream.fileno())
    except OSError as exc:
        raise NativeLuaDirectCallError("executable could not be read") from exc
    try:
        path_after = path.stat()
        link_after = path.lstat()
    except OSError as exc:
        raise NativeLuaDirectCallError(
            "executable changed while being read"
        ) from exc
    if (
        len(data) != handle_before.st_size
        or not _same_stat(handle_before, handle_after)
        or not _same_stat(handle_after, path_after)
        or not _same_stat(link_before, link_after)
        or stat.S_ISLNK(link_after.st_mode)
        or _is_reparse(link_after)
    ):
        raise NativeLuaDirectCallError("executable changed while being read")
    try:
        return data, PEImage(data), hashlib.sha256(data).hexdigest()
    except PEAnchorError as exc:
        raise NativeLuaDirectCallError(f"invalid PE executable: {exc}") from exc


def _decoder() -> tuple[Any, int]:
    try:
        import capstone
        import capstone.x86_const as x86
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise NativeLuaDirectCallError(
            f"Capstone {SUPPORTED_CAPSTONE_VERSION} is required"
        ) from exc
    if capstone.__version__ != SUPPORTED_CAPSTONE_VERSION:
        raise NativeLuaDirectCallError(
            "unsupported Capstone version for native Lua call schema 1: "
            f"{capstone.__version__} != {SUPPORTED_CAPSTONE_VERSION}"
        )
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    return decoder, x86.X86_INS_CALL


def _lua_imports(image: PEImage) -> list[dict[str, Any]]:
    if image.bits != 32 or image.architecture != "x86":
        raise NativeLuaDirectCallError("schema 1 supports only 32-bit x86 PE images")
    try:
        raw_imports = image.imports()
    except PEAnchorError as exc:
        raise NativeLuaDirectCallError(f"PE import parsing failed: {exc}") from exc
    imports: list[dict[str, Any]] = []
    seen_iat: set[int] = set()
    seen_names: set[str] = set()
    for index, raw in enumerate(raw_imports):
        item = _mapping(raw, f"PE import {index}")
        library = _text(item.get("library"), f"PE import {index}.library")
        if library.casefold() != LUA_LIBRARY:
            continue
        name = item.get("name")
        if type(name) is not str or not name or len(name) > MAX_TEXT:
            raise NativeLuaDirectCallError(
                "lua5.1.dll imports must all be bounded named imports"
            )
        if item.get("ordinal") is not None:
            raise NativeLuaDirectCallError(
                "lua5.1.dll named imports cannot also carry ordinals"
            )
        hint = _count(item.get("hint"), f"PE import {index}.hint")
        iat_rva = _rva(item.get("iat_rva"), f"PE import {index}.iat_rva")
        if iat_rva in seen_iat or name in seen_names:
            raise NativeLuaDirectCallError(
                "lua5.1.dll import names and IAT slots must be unique"
            )
        seen_iat.add(iat_rva)
        seen_names.add(name)
        imports.append(
            {
                "library": LUA_LIBRARY,
                "name": name,
                "hint": hint,
                "iat_rva": _hex(iat_rva),
            }
        )
    imports.sort(key=lambda item: int(item["iat_rva"], 16))
    if not imports:
        raise NativeLuaDirectCallError("executable has no named lua5.1.dll imports")
    return imports


def _decode_atlas(
    data: bytes,
    image: PEImage,
    program_facts: Mapping[str, Any],
    imports: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int], Counter[str], dict[str, set[str]]]:
    decoder, call_id = _decoder()
    imports_by_va = {
        image.image_base + int(item["iat_rva"], 16): item for item in imports
    }
    raw_functions = _array(program_facts.get("functions"), "program_facts.functions")
    records: list[dict[str, Any]] = []
    global_call_rvas: set[int] = set()
    import_calls: Counter[str] = Counter()
    import_callers: dict[str, set[str]] = {
        item["name"]: set() for item in imports
    }
    decoded_ranges = 0
    decoded_bytes = 0
    decoded_instructions = 0
    previous_entry = -1
    for function_index, raw_function in enumerate(raw_functions):
        label = f"program_facts.functions[{function_index}]"
        function = _mapping(raw_function, label)
        entry = _rva(function.get("entry_rva"), f"{label}.entry_rva")
        if entry <= previous_entry:
            raise NativeLuaDirectCallError(
                "program-facts functions must have increasing entry RVAs"
            )
        previous_entry = entry
        calls: list[dict[str, Any]] = []
        raw_ranges = _array(function.get("ranges"), f"{label}.ranges")
        if not raw_ranges:
            raise NativeLuaDirectCallError(f"{label}.ranges must be non-empty")
        for range_index, raw_range in enumerate(raw_ranges):
            range_label = f"{label}.ranges[{range_index}]"
            body_range = _mapping(raw_range, range_label)
            _exact_keys(body_range, {"start_rva", "size"}, range_label)
            start = _rva(body_range["start_rva"], f"{range_label}.start_rva")
            size = _count(body_range["size"], f"{range_label}.size", positive=True)
            offset = image.rva_span_to_file_offset(start, size)
            if offset is None:
                raise NativeLuaDirectCallError(
                    f"{range_label} is not contiguous file-backed image data"
                )
            body = data[offset : offset + size]
            expected_va = image.image_base + start
            decoded_size = 0
            for instruction in decoder.disasm(body, expected_va):
                if instruction.address != expected_va + decoded_size:
                    raise NativeLuaDirectCallError(
                        f"{range_label} decoder produced a non-contiguous stream"
                    )
                decoded_size += instruction.size
                decoded_instructions += 1
                encoded = bytes(instruction.bytes)
                if (
                    instruction.id != call_id
                    or len(encoded) != 6
                    or encoded[:2] != b"\xff\x15"
                ):
                    continue
                target_va = int.from_bytes(encoded[2:], "little")
                imported = imports_by_va.get(target_va)
                if imported is None:
                    continue
                call_rva = instruction.address - image.image_base
                if call_rva in global_call_rvas:
                    raise NativeLuaDirectCallError(
                        f"duplicate decoded Lua call site: {_hex(call_rva)}"
                    )
                global_call_rvas.add(call_rva)
                import_name = imported["name"]
                call = {
                    "call_rva": _hex(call_rva),
                    "instruction_size": len(encoded),
                    "instruction_sha256": hashlib.sha256(encoded).hexdigest(),
                    "call_form": CALL_FORM,
                    "library": LUA_LIBRARY,
                    "import_name": import_name,
                    "iat_rva": imported["iat_rva"],
                }
                calls.append(call)
                import_calls[import_name] += 1
                import_callers[import_name].add(_hex(entry))
            if decoded_size != size:
                raise NativeLuaDirectCallError(
                    f"{range_label} did not decode completely: {decoded_size}/{size}"
                )
            decoded_ranges += 1
            decoded_bytes += size
        calls.sort(key=lambda item: int(item["call_rva"], 16))
        if calls:
            records.append(
                {
                    "entry_rva": _hex(entry),
                    "atlas_record_sha256": _canonical_sha256(function),
                    "direct_lua_import_calls": calls,
                    "direct_call_count": len(calls),
                    "import_names": sorted({item["import_name"] for item in calls}),
                }
            )
    return (
        records,
        {
            "decoded_ranges": decoded_ranges,
            "decoded_bytes": decoded_bytes,
            "decoded_instructions": decoded_instructions,
        },
        import_calls,
        import_callers,
    )


def _assert_publication_safe(value: Any, label: str = "artifact") -> None:
    if type(value) is str:
        if len(value) > MAX_TEXT or "\0" in value:
            raise NativeLuaDirectCallError(f"{label} contains unbounded text")
        if "/" in value or "\\" in value or re.search(r"[A-Za-z]:", value):
            raise NativeLuaDirectCallError(f"{label} contains an absolute path")
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
                raise NativeLuaDirectCallError(f"{label} has an invalid field name")
            _assert_publication_safe(item, f"{label}.{key}")
        return
    raise NativeLuaDirectCallError(f"{label} contains a non-publication value")


def build_native_lua_direct_call_census(
    executable: Path,
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact direct-Lua-IAT-call relation over one verified atlas."""
    _validate_json_tree(program_facts, "program_facts")
    _validate_json_tree(inventory, "inventory")
    try:
        atlas_verification = validate_program_facts(
            executable,
            program_facts,
            inventory=inventory,
        )
    except ProgramFactsError as exc:
        raise NativeLuaDirectCallError(
            f"program-facts prerequisite failed verification: {exc}"
        ) from exc
    atlas_sha256 = _canonical_sha256(program_facts)
    if atlas_verification.get("evidence_sha256") != atlas_sha256:
        raise NativeLuaDirectCallError(
            "program-facts verifier canonical identity disagrees"
        )
    data, image, executable_sha256 = _load_executable(executable)
    atlas_identity = _mapping(
        program_facts.get("identity"), "program_facts.identity"
    )
    if (
        atlas_identity.get("executable_sha256") != executable_sha256
        or type(atlas_identity.get("executable_size")) is not int
        or atlas_identity.get("executable_size") != len(data)
        or atlas_identity.get("architecture") != image.architecture
    ):
        raise NativeLuaDirectCallError(
            "executable changed after program-facts prerequisite verification"
        )
    imports = _lua_imports(image)
    records, decode_counts, import_calls, import_callers = _decode_atlas(
        data,
        image,
        program_facts,
        imports,
    )
    atlas_summary = _mapping(program_facts.get("summary"), "program_facts.summary")
    if decode_counts["decoded_ranges"] != atlas_summary.get("body_range_count"):
        raise NativeLuaDirectCallError("decoded range count differs from the atlas")
    if decode_counts["decoded_bytes"] != atlas_summary.get("function_body_bytes"):
        raise NativeLuaDirectCallError("decoded byte count differs from the atlas")
    normalized_imports = [
        {
            **item,
            "direct_call_sites": import_calls[item["name"]],
            "direct_calling_functions": len(import_callers[item["name"]]),
        }
        for item in imports
    ]
    direct_call_sites = sum(import_calls.values())
    if direct_call_sites != sum(item["direct_call_count"] for item in records):
        raise NativeLuaDirectCallError("direct Lua call partitions disagree")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(atlas_identity),
        "atlas": {
            "analysis_kind": program_facts.get("analysis_kind"),
            "canonical_sha256": atlas_sha256,
            "ghidra_facts_sha256": _mapping(
                program_facts.get("ghidra"), "program_facts.ghidra"
            ).get("facts_sha256"),
            "function_count": atlas_summary.get("function_count"),
            "body_range_count": atlas_summary.get("body_range_count"),
            "function_body_bytes": atlas_summary.get("function_body_bytes"),
            "discovery_coverage_basis_points": atlas_summary.get(
                "ghidra_function_discovery_coverage_basis_points"
            ),
        },
        "decoder": {
            "name": "capstone",
            "version": SUPPORTED_CAPSTONE_VERSION,
            "architecture": "x86",
            "mode_bits": 32,
            "accepted_call_form": CALL_FORM,
        },
        "lua_imports": normalized_imports,
        "records": records,
        "method": _METHOD,
        "summary": {
            "atlas_functions": atlas_summary.get("function_count"),
            "atlas_body_ranges": atlas_summary.get("body_range_count"),
            "atlas_body_bytes": atlas_summary.get("function_body_bytes"),
            "decoded_ranges": decode_counts["decoded_ranges"],
            "decoded_bytes": decode_counts["decoded_bytes"],
            "decoded_instructions": decode_counts["decoded_instructions"],
            "lua_named_imports": len(imports),
            "lua_imports_with_direct_calls": sum(
                import_calls[item["name"]] > 0 for item in imports
            ),
            "lua_imports_without_direct_calls": sum(
                import_calls[item["name"]] == 0 for item in imports
            ),
            "direct_lua_import_call_sites": direct_call_sites,
            "atlas_functions_with_direct_lua_import_calls": len(records),
            "schema_violations": 0,
        },
    }
    _assert_publication_safe(result)
    return result


def validate_native_lua_direct_call_census(
    executable: Path,
    evidence: Mapping[str, Any],
    program_facts: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and canonical-byte-compare one direct-Lua-call census."""
    _validate_json_tree(evidence, "evidence")
    rebuilt = build_native_lua_direct_call_census(
        executable,
        program_facts,
        inventory=inventory,
    )
    if _canonical_bytes(evidence) != _canonical_bytes(rebuilt):
        raise NativeLuaDirectCallError(
            "evidence does not match the exact rebuilt native Lua call census"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": rebuilt["build_identity"],
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": rebuilt["summary"],
    }


def encode_native_lua_direct_call_census(value: Mapping[str, Any]) -> str:
    """Encode evidence or verification output deterministically."""
    _validate_json_tree(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
