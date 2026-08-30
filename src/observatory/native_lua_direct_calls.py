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
STRUCTURE_VERIFICATION_KIND = (
    "pe_native_lua_direct_import_call_census_structure_verification"
)
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


def validate_native_lua_direct_call_structure(
    evidence: Mapping[str, Any],
    program_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Check a complete census's normalized structure without reading the PE.

    This is intentionally *not* a substitute for
    :func:`validate_native_lua_direct_call_census`: it validates the supplied
    document's exact join to the supplied whole-atlas facts and all of its
    internal partitions, but cannot establish that either document still
    matches an executable.  It exists for tightly scoped downstream consumers
    that need to reject a malformed or partially substituted census before
    deriving a deliberately bounded fact from it.
    """
    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(program_facts, "program_facts")
    evidence = _mapping(evidence, "evidence")
    facts = _mapping(program_facts, "program_facts")
    _exact_keys(
        evidence,
        {
            "schema_version",
            "analysis_kind",
            "build_identity",
            "atlas",
            "decoder",
            "lua_imports",
            "records",
            "method",
            "summary",
        },
        "evidence",
    )
    if (
        type(evidence["schema_version"]) is not int
        or evidence["schema_version"] != SCHEMA_VERSION
    ):
        raise NativeLuaDirectCallError("unsupported native Lua direct-call schema")
    if evidence["analysis_kind"] != ANALYSIS_KIND:
        raise NativeLuaDirectCallError("unexpected native Lua direct-call analysis kind")

    _exact_keys(
        facts,
        {
            "schema_version",
            "analysis_kind",
            "identity",
            "ghidra",
            "functions",
            "ghidra_declared_direct_calls",
            "summary",
            "method",
        },
        "program_facts",
    )
    if type(facts["schema_version"]) is not int or facts["schema_version"] != 1:
        raise NativeLuaDirectCallError("unsupported program-facts schema")
    if facts["analysis_kind"] != "pe_ghidra_program_facts":
        raise NativeLuaDirectCallError("unexpected program-facts analysis kind")
    identity = _mapping(facts["identity"], "program_facts.identity")
    if evidence["build_identity"] != dict(identity):
        raise NativeLuaDirectCallError(
            "census build identity does not match program facts"
        )
    if identity.get("architecture") != "x86":
        raise NativeLuaDirectCallError(
            "native Lua direct-call structure requires an x86 atlas"
        )
    ghidra = _mapping(facts["ghidra"], "program_facts.ghidra")
    _exact_keys(
        ghidra,
        {
            "facts_format_version",
            "version",
            "program_name",
            "language_id",
            "compiler_spec_id",
            "image_base",
            "facts_sha256",
        },
        "program_facts.ghidra",
    )
    if ghidra["facts_format_version"] != "1":
        raise NativeLuaDirectCallError("unsupported Ghidra facts format")
    for key in ("version", "program_name", "language_id", "compiler_spec_id"):
        _text(ghidra[key], f"program_facts.ghidra.{key}")
    image_base = _rva(ghidra["image_base"], "program_facts.ghidra.image_base")
    _sha256(ghidra["facts_sha256"], "program_facts.ghidra.facts_sha256")
    facts_summary = _mapping(facts["summary"], "program_facts.summary")

    raw_functions = _array(facts["functions"], "program_facts.functions")
    functions_by_entry: dict[int, Mapping[str, Any]] = {}
    ranges_by_entry: dict[int, tuple[tuple[int, int], ...]] = {}
    atlas_ranges = 0
    atlas_bytes = 0
    previous_function_entry = -1
    for function_index, raw_function in enumerate(raw_functions):
        label = f"program_facts.functions[{function_index}]"
        function = _mapping(raw_function, label)
        _exact_keys(
            function,
            {
                "entry_rva",
                "name",
                "namespace",
                "name_source",
                "thunk",
                "body_size",
                "body_sha256",
                "ranges",
            },
            label,
        )
        entry = _rva(function["entry_rva"], f"{label}.entry_rva")
        if entry <= previous_function_entry:
            raise NativeLuaDirectCallError(
                "program-facts function entries must be strictly increasing"
            )
        previous_function_entry = entry
        if type(function["thunk"]) is not bool:
            raise NativeLuaDirectCallError(f"{label}.thunk must be boolean")
        _text(function["name"], f"{label}.name")
        if (
            type(function["namespace"]) is not str
            or len(function["namespace"]) > MAX_TEXT
            or "\0" in function["namespace"]
        ):
            raise NativeLuaDirectCallError(
                f"{label}.namespace must be bounded text"
            )
        _text(function["name_source"], f"{label}.name_source")
        body_size = _count(function["body_size"], f"{label}.body_size")
        _sha256(function["body_sha256"], f"{label}.body_sha256")
        raw_ranges = _array(function["ranges"], f"{label}.ranges")
        if not raw_ranges:
            raise NativeLuaDirectCallError(f"{label}.ranges must be non-empty")
        normalized_ranges: list[tuple[int, int]] = []
        previous_end = -1
        for range_index, raw_range in enumerate(raw_ranges):
            range_label = f"{label}.ranges[{range_index}]"
            body_range = _mapping(raw_range, range_label)
            _exact_keys(body_range, {"start_rva", "size"}, range_label)
            start = _rva(body_range["start_rva"], f"{range_label}.start_rva")
            size = _count(body_range["size"], f"{range_label}.size", positive=True)
            if start < previous_end:
                raise NativeLuaDirectCallError(
                    f"{range_label} overlaps or is not ordered"
                )
            previous_end = start + size
            normalized_ranges.append((start, size))
        if body_size != sum(size for _start, size in normalized_ranges):
            raise NativeLuaDirectCallError(f"{label}.body_size disagrees with ranges")
        functions_by_entry[entry] = function
        ranges_by_entry[entry] = tuple(normalized_ranges)
        atlas_ranges += len(normalized_ranges)
        atlas_bytes += body_size

    _exact_keys(
        _mapping(evidence["atlas"], "evidence.atlas"),
        {
            "analysis_kind",
            "canonical_sha256",
            "ghidra_facts_sha256",
            "function_count",
            "body_range_count",
            "function_body_bytes",
            "discovery_coverage_basis_points",
        },
        "evidence.atlas",
    )
    atlas = _mapping(evidence["atlas"], "evidence.atlas")
    expected_atlas = {
        "analysis_kind": facts["analysis_kind"],
        "canonical_sha256": _canonical_sha256(facts),
        "ghidra_facts_sha256": ghidra.get("facts_sha256"),
        "function_count": len(raw_functions),
        "body_range_count": atlas_ranges,
        "function_body_bytes": atlas_bytes,
        "discovery_coverage_basis_points": facts_summary.get(
            "ghidra_function_discovery_coverage_basis_points"
        ),
    }
    if atlas != expected_atlas:
        raise NativeLuaDirectCallError(
            "census atlas identity or aggregate differs from program facts"
        )
    _sha256(atlas["canonical_sha256"], "evidence.atlas.canonical_sha256")
    _sha256(atlas["ghidra_facts_sha256"], "evidence.atlas.ghidra_facts_sha256")
    for key in (
        "function_count",
        "body_range_count",
        "function_body_bytes",
        "discovery_coverage_basis_points",
    ):
        _count(atlas[key], f"evidence.atlas.{key}")

    decoder = _mapping(evidence["decoder"], "evidence.decoder")
    _exact_keys(
        decoder,
        {"name", "version", "architecture", "mode_bits", "accepted_call_form"},
        "evidence.decoder",
    )
    expected_decoder = {
        "name": "capstone",
        "version": SUPPORTED_CAPSTONE_VERSION,
        "architecture": "x86",
        "mode_bits": 32,
        "accepted_call_form": CALL_FORM,
    }
    if decoder != expected_decoder:
        raise NativeLuaDirectCallError("census decoder contract has drifted")
    if _canonical_bytes(evidence["method"]) != _canonical_bytes(_METHOD):
        raise NativeLuaDirectCallError("census method contract has drifted")

    imports_by_name: dict[str, tuple[int, Mapping[str, Any]]] = {}
    imports_by_iat: dict[int, Mapping[str, Any]] = {}
    raw_imports = _array(evidence["lua_imports"], "evidence.lua_imports")
    if not raw_imports:
        raise NativeLuaDirectCallError("census must include named Lua imports")
    previous_iat = -1
    for import_index, raw_import in enumerate(raw_imports):
        label = f"evidence.lua_imports[{import_index}]"
        imported = _mapping(raw_import, label)
        _exact_keys(
            imported,
            {
                "library",
                "name",
                "hint",
                "iat_rva",
                "direct_call_sites",
                "direct_calling_functions",
            },
            label,
        )
        if imported["library"] != LUA_LIBRARY:
            raise NativeLuaDirectCallError(f"{label}.library must be {LUA_LIBRARY}")
        name = _text(imported["name"], f"{label}.name")
        _count(imported["hint"], f"{label}.hint")
        iat = _rva(imported["iat_rva"], f"{label}.iat_rva")
        _count(imported["direct_call_sites"], f"{label}.direct_call_sites")
        _count(
            imported["direct_calling_functions"],
            f"{label}.direct_calling_functions",
        )
        if iat <= previous_iat or name in imports_by_name or iat in imports_by_iat:
            raise NativeLuaDirectCallError(
                "Lua imports must be unique and IAT-RVA ordered"
            )
        previous_iat = iat
        imports_by_name[name] = (iat, imported)
        imports_by_iat[iat] = imported

    import_sites: Counter[str] = Counter()
    import_callers: dict[str, set[int]] = {name: set() for name in imports_by_name}
    all_call_rvas: set[int] = set()
    raw_records = _array(evidence["records"], "evidence.records")
    previous_record_entry = -1
    for record_index, raw_record in enumerate(raw_records):
        label = f"evidence.records[{record_index}]"
        record = _mapping(raw_record, label)
        _exact_keys(
            record,
            {
                "entry_rva",
                "atlas_record_sha256",
                "direct_lua_import_calls",
                "direct_call_count",
                "import_names",
            },
            label,
        )
        entry = _rva(record["entry_rva"], f"{label}.entry_rva")
        if entry <= previous_record_entry:
            raise NativeLuaDirectCallError(
                "census records must have unique increasing entries"
            )
        previous_record_entry = entry
        function = functions_by_entry.get(entry)
        if function is None:
            raise NativeLuaDirectCallError(f"{label}.entry_rva is absent from the atlas")
        if record["atlas_record_sha256"] != _canonical_sha256(function):
            raise NativeLuaDirectCallError(f"{label}.atlas_record_sha256 does not match atlas")
        _sha256(record["atlas_record_sha256"], f"{label}.atlas_record_sha256")
        calls = _array(
            record["direct_lua_import_calls"],
            f"{label}.direct_lua_import_calls",
        )
        if not calls:
            raise NativeLuaDirectCallError(f"{label}.direct_lua_import_calls must be non-empty")
        if (
            _count(
                record["direct_call_count"],
                f"{label}.direct_call_count",
                positive=True,
            )
            != len(calls)
        ):
            raise NativeLuaDirectCallError(
                f"{label}.direct_call_count disagrees with calls"
            )
        seen_record_calls: set[int] = set()
        previous_call_rva = -1
        names: set[str] = set()
        for call_index, raw_call in enumerate(calls):
            call_label = f"{label}.direct_lua_import_calls[{call_index}]"
            call = _mapping(raw_call, call_label)
            _exact_keys(
                call,
                {
                    "call_rva",
                    "instruction_size",
                    "instruction_sha256",
                    "call_form",
                    "library",
                    "import_name",
                    "iat_rva",
                },
                call_label,
            )
            call_rva = _rva(call["call_rva"], f"{call_label}.call_rva")
            if (
                call_rva <= previous_call_rva
                or call_rva in seen_record_calls
                or call_rva in all_call_rvas
            ):
                raise NativeLuaDirectCallError(
                    "Lua call sites must be globally unique and ordered"
                )
            previous_call_rva = call_rva
            seen_record_calls.add(call_rva)
            all_call_rvas.add(call_rva)
            if (
                type(call["instruction_size"]) is not int
                or call["instruction_size"] != 6
            ):
                raise NativeLuaDirectCallError(
                    f"{call_label}.instruction_size must be 6"
                )
            _sha256(call["instruction_sha256"], f"{call_label}.instruction_sha256")
            if call["call_form"] != CALL_FORM or call["library"] != LUA_LIBRARY:
                raise NativeLuaDirectCallError(
                    f"{call_label} has an unsupported Lua call form"
                )
            name = _text(call["import_name"], f"{call_label}.import_name")
            iat = _rva(call["iat_rva"], f"{call_label}.iat_rva")
            expected_import = imports_by_name.get(name)
            if expected_import is None or expected_import[0] != iat:
                raise NativeLuaDirectCallError(
                    f"{call_label} does not match a published Lua import"
                )
            absolute_iat = image_base + iat
            if absolute_iat > 0xFFFFFFFF:
                raise NativeLuaDirectCallError(
                    f"{call_label}.iat_rva overflows the x86 absolute address"
                )
            expected_instruction_sha256 = hashlib.sha256(
                b"\xff\x15" + absolute_iat.to_bytes(4, "little")
            ).hexdigest()
            if call["instruction_sha256"] != expected_instruction_sha256:
                raise NativeLuaDirectCallError(
                    f"{call_label}.instruction_sha256 does not match the "
                    "declared FF15 IAT call encoding"
                )
            if not any(
                start <= call_rva and call_rva + 6 <= start + size
                for start, size in ranges_by_entry[entry]
            ):
                raise NativeLuaDirectCallError(
                    f"{call_label}.call_rva is outside its atlas body ranges"
                )
            import_sites[name] += 1
            import_callers[name].add(entry)
            names.add(name)
        import_names = _array(record["import_names"], f"{label}.import_names")
        if any(type(name) is not str for name in import_names) or import_names != sorted(names):
            raise NativeLuaDirectCallError(f"{label}.import_names disagrees with calls")

    for name, (_iat, imported) in imports_by_name.items():
        if (
            imported["direct_call_sites"] != import_sites[name]
            or imported["direct_calling_functions"] != len(import_callers[name])
        ):
            raise NativeLuaDirectCallError("Lua import aggregates disagree with records")

    summary = _mapping(evidence["summary"], "evidence.summary")
    _exact_keys(
        summary,
        {
            "atlas_functions",
            "atlas_body_ranges",
            "atlas_body_bytes",
            "decoded_ranges",
            "decoded_bytes",
            "decoded_instructions",
            "lua_named_imports",
            "lua_imports_with_direct_calls",
            "lua_imports_without_direct_calls",
            "direct_lua_import_call_sites",
            "atlas_functions_with_direct_lua_import_calls",
            "schema_violations",
        },
        "evidence.summary",
    )
    for key, value in summary.items():
        _count(value, f"evidence.summary.{key}")
    expected_summary = {
        "atlas_functions": len(raw_functions),
        "atlas_body_ranges": atlas_ranges,
        "atlas_body_bytes": atlas_bytes,
        "decoded_ranges": atlas_ranges,
        "decoded_bytes": atlas_bytes,
        "decoded_instructions": summary["decoded_instructions"],
        "lua_named_imports": len(raw_imports),
        "lua_imports_with_direct_calls": sum(
            import_sites[name] > 0 for name in imports_by_name
        ),
        "lua_imports_without_direct_calls": sum(
            import_sites[name] == 0 for name in imports_by_name
        ),
        "direct_lua_import_call_sites": len(all_call_rvas),
        "atlas_functions_with_direct_lua_import_calls": len(raw_records),
        "schema_violations": 0,
    }
    if summary != expected_summary:
        raise NativeLuaDirectCallError("census summary aggregates or partitions disagree")
    if summary["decoded_instructions"] < summary["direct_lua_import_call_sites"]:
        raise NativeLuaDirectCallError("decoded instruction count is below direct call count")
    _assert_publication_safe(evidence)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": STRUCTURE_VERIFICATION_KIND,
        "status": "structurally_verified",
        "build_identity": dict(identity),
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": dict(summary),
    }


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
