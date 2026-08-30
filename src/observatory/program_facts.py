"""Build and verify a normalized whole-program Ghidra function atlas.

The atlas is deliberately narrower than a decompiler database.  It records
only build-keyed identities, function ranges and hashes, analyst/auto-analysis
names, and direct internal call edges.  It never stores executable bytes,
disassembly, decompiler output, variables, or reconstructed source text.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.observatory.pe_anchor_map import (
    MAX_EXECUTABLE_BYTES,
    PEAnchorError,
    PEImage,
    _inventory_identity,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_ghidra_program_facts"
VERIFICATION_KIND = "pe_ghidra_program_facts_verification"
GHIDRA_FACTS_FORMAT_VERSION = "1"
MAX_FACTS_BYTES = 256 * 1024 * 1024
MAX_FACT_ROWS = 2_000_000
MAX_TEXT_FIELD = 16 * 1024
_RVA_PATTERN = re.compile(r"0x(?:[0-9a-f]{8}|[0-9a-f]{16})\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_META_KEYS = {
    "format_version",
    "ghidra_version",
    "program_name",
    "language_id",
    "compiler_spec_id",
    "image_base",
    "function_count",
    "range_count",
    "direct_internal_call_count",
    "omitted_call_target_count",
}
_METHOD = {
    "facts": (
        "Ghidra-discovered function entries, body ranges, analysis names, body "
        "SHA-256 values, and Ghidra-declared direct internal call flows"
    ),
    "verification": (
        "Every function range is re-read from the exact inventoried executable; "
        "range concatenation, body size, body SHA-256, entry membership, and "
        "declared-call source/target body membership and target-name consistency "
        "are checked"
    ),
    "not_claimed": [
        "complete function discovery",
        "correct function boundaries beyond the recorded Ghidra analysis",
        "independent instruction decoding of Ghidra-declared call flows",
        "indirect-call resolution",
        "semantic understanding",
        "source-level equivalence",
        "cross-build or cross-platform equivalence",
    ],
    "omitted": [
        "executable bytes",
        "disassembly",
        "decompiler text",
        "local variables and types",
        "reconstructed proprietary source",
    ],
}


class ProgramFactsError(PEAnchorError):
    """Raised when whole-program facts are malformed or build-mismatched."""


@dataclass(frozen=True)
class _FunctionRecord:
    entry: int
    name: str
    namespace: str
    name_source: str
    thunk: bool
    body_size: int
    body_sha256: str
    ranges: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class _CallRecord:
    source_entry: int
    instruction: int
    target: int
    target_entry: int | None
    target_name: str


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ProgramFactsError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProgramFactsError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProgramFactsError(f"{label} must be an array")
    return value


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value):
        qualifier = "text" if allow_empty else "non-empty text"
        raise ProgramFactsError(f"{label} must be {qualifier}")
    if len(value) > MAX_TEXT_FIELD or "\0" in value:
        raise ProgramFactsError(f"{label} is too long or contains NUL")
    return value


def _count(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ProgramFactsError(f"{label} must be a non-negative integer")
    return value


def _decimal_count(value: str, label: str) -> int:
    if not value or not value.isascii() or not value.isdecimal():
        raise ProgramFactsError(f"{label} must be decimal text")
    return _count(int(value), label)


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ProgramFactsError(f"{label} must be lowercase SHA-256")
    return value


def _rva(value: Any, label: str) -> int:
    if type(value) is not str or _RVA_PATTERN.fullmatch(value) is None:
        raise ProgramFactsError(f"{label} must be a canonical RVA")
    return int(value, 16)


def _hex(value: int, bits: int) -> str:
    return f"0x{value:0{16 if bits == 64 else 8}x}"


def _unescape_tsv_field(value: str, label: str) -> str:
    output: list[str] = []
    index = 0
    escapes = {"\\": "\\", "t": "\t", "r": "\r", "n": "\n"}
    while index < len(value):
        character = value[index]
        if character != "\\":
            output.append(character)
            index += 1
            continue
        index += 1
        if index >= len(value) or value[index] not in escapes:
            raise ProgramFactsError(f"{label} contains an invalid escape")
        output.append(escapes[value[index]])
        index += 1
    result = "".join(output)
    return _text(result, label, allow_empty=True)


def _load_regular_file(path: Path, label: str, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ProgramFactsError(f"{label} is not a regular non-symlink file")
    before = path.stat()
    if before.st_size > limit:
        raise ProgramFactsError(f"{label} exceeds the analysis size limit")
    data = path.read_bytes()
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(data) != before.st_size
    ):
        raise ProgramFactsError(f"{label} changed while being read")
    return data


def _load_executable(executable: Path) -> tuple[bytes, PEImage, str]:
    data = _load_regular_file(executable, "executable", MAX_EXECUTABLE_BYTES)
    return data, PEImage(data), hashlib.sha256(data).hexdigest()


def _parse_fact_rows(
    payload: bytes,
) -> tuple[
    dict[str, str],
    dict[int, dict[str, Any]],
    list[tuple[int, int, int]],
    list[_CallRecord],
]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProgramFactsError("Ghidra facts are not valid UTF-8") from exc
    metadata: dict[str, str] = {}
    functions: dict[int, dict[str, Any]] = {}
    ranges: list[tuple[int, int, int]] = []
    calls: list[_CallRecord] = []
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        if line_number > MAX_FACT_ROWS:
            raise ProgramFactsError("Ghidra facts exceed the row limit")
        if not raw_line:
            raise ProgramFactsError(f"Ghidra facts line {line_number} is empty")
        fields = [
            _unescape_tsv_field(field, f"line {line_number} field {index}")
            for index, field in enumerate(raw_line.split("\t"))
        ]
        kind = fields[0]
        if kind == "meta":
            if len(fields) != 3:
                raise ProgramFactsError(f"line {line_number} has malformed meta fields")
            key = _text(fields[1], f"line {line_number} metadata key")
            if key in metadata:
                raise ProgramFactsError(f"duplicate Ghidra metadata key: {key}")
            metadata[key] = fields[2]
        elif kind == "function":
            if len(fields) != 8:
                raise ProgramFactsError(
                    f"line {line_number} has malformed function fields"
                )
            entry = _rva(fields[1], f"line {line_number} function entry")
            if entry in functions:
                raise ProgramFactsError(f"duplicate function entry: {fields[1]}")
            if fields[5] not in {"0", "1"}:
                raise ProgramFactsError(
                    f"line {line_number} function thunk must be 0 or 1"
                )
            functions[entry] = {
                "name": _text(fields[2], f"line {line_number} function name"),
                "namespace": _text(
                    fields[3], f"line {line_number} function namespace", allow_empty=True
                ),
                "name_source": _text(
                    fields[4], f"line {line_number} function name source"
                ),
                "thunk": fields[5] == "1",
                "body_size": _decimal_count(
                    fields[6], f"line {line_number} function body size"
                ),
                "body_sha256": _sha256(
                    fields[7], f"line {line_number} function body SHA-256"
                ),
            }
        elif kind == "range":
            if len(fields) != 4:
                raise ProgramFactsError(f"line {line_number} has malformed range fields")
            ranges.append(
                (
                    _rva(fields[1], f"line {line_number} range function entry"),
                    _rva(fields[2], f"line {line_number} range start"),
                    _decimal_count(fields[3], f"line {line_number} range size"),
                )
            )
        elif kind == "call":
            if len(fields) != 6:
                raise ProgramFactsError(f"line {line_number} has malformed call fields")
            calls.append(
                _CallRecord(
                    source_entry=_rva(
                        fields[1], f"line {line_number} call source entry"
                    ),
                    instruction=_rva(
                        fields[2], f"line {line_number} call instruction"
                    ),
                    target=_rva(fields[3], f"line {line_number} call target"),
                    target_entry=(
                        _rva(fields[4], f"line {line_number} call target entry")
                        if fields[4]
                        else None
                    ),
                    target_name=_text(
                        fields[5], f"line {line_number} call target name", allow_empty=True
                    ),
                )
            )
        else:
            raise ProgramFactsError(
                f"line {line_number} has unsupported row kind: {kind!r}"
            )
    if set(metadata) != _META_KEYS:
        raise ProgramFactsError(
            "Ghidra metadata fields differ; "
            f"missing={sorted(_META_KEYS - set(metadata))}, "
            f"unknown={sorted(set(metadata) - _META_KEYS)}"
        )
    return metadata, functions, ranges, calls


def _section_for_span(image: PEImage, start: int, size: int) -> str:
    if size <= 0:
        raise ProgramFactsError("function ranges must be non-empty")
    for section in image.sections:
        if (
            section.virtual_address <= start
            and start + size <= section.virtual_address + section.raw_size
        ):
            if not section.executable:
                raise ProgramFactsError("function range is not executable code")
            return section.name
    raise ProgramFactsError("function range is not contiguous file-backed code")


def _range_bytes(image: PEImage, data: bytes, start: int, size: int) -> bytes:
    _section_for_span(image, start, size)
    offset = image.rva_span_to_file_offset(start, size)
    if offset is None:
        raise ProgramFactsError("function range is not contiguous file-backed data")
    return data[offset : offset + size]


def _normalize_functions(
    raw_functions: Mapping[int, Mapping[str, Any]],
    raw_ranges: list[tuple[int, int, int]],
    *,
    image: PEImage,
    data: bytes,
) -> list[_FunctionRecord]:
    ranges_by_entry: dict[int, list[tuple[int, int]]] = {
        entry: [] for entry in raw_functions
    }
    seen_ranges: set[tuple[int, int, int]] = set()
    for entry, start, size in raw_ranges:
        row = (entry, start, size)
        if row in seen_ranges:
            raise ProgramFactsError("duplicate function body range")
        seen_ranges.add(row)
        if entry not in raw_functions:
            raise ProgramFactsError("function body range references an unknown entry")
        ranges_by_entry[entry].append((start, size))

    records: list[_FunctionRecord] = []
    for entry in sorted(raw_functions):
        raw = raw_functions[entry]
        ranges = sorted(ranges_by_entry[entry])
        if not ranges:
            raise ProgramFactsError(f"function {_hex(entry, image.bits)} has no ranges")
        previous_end = -1
        digest = hashlib.sha256()
        body_size = 0
        entry_is_in_body = False
        for start, size in ranges:
            if start < previous_end:
                raise ProgramFactsError("function body ranges overlap")
            previous_end = start + size
            body = _range_bytes(image, data, start, size)
            digest.update(body)
            body_size += size
            entry_is_in_body = entry_is_in_body or start <= entry < start + size
        if not entry_is_in_body:
            raise ProgramFactsError("function entry is outside its body ranges")
        if body_size != raw["body_size"]:
            raise ProgramFactsError("function body size disagrees with its ranges")
        if digest.hexdigest() != raw["body_sha256"]:
            raise ProgramFactsError("function body SHA-256 disagrees with the executable")
        records.append(
            _FunctionRecord(
                entry=entry,
                name=str(raw["name"]),
                namespace=str(raw["namespace"]),
                name_source=str(raw["name_source"]),
                thunk=bool(raw["thunk"]),
                body_size=body_size,
                body_sha256=digest.hexdigest(),
                ranges=tuple(ranges),
            )
        )
    return records


def _contains(ranges: tuple[tuple[int, int], ...], address: int) -> bool:
    return any(start <= address < start + size for start, size in ranges)


def _normalize_calls(
    raw_calls: list[_CallRecord],
    functions: list[_FunctionRecord],
    *,
    image: PEImage,
    data: bytes,
) -> list[_CallRecord]:
    by_entry = {function.entry: function for function in functions}
    normalized = sorted(
        raw_calls,
        key=lambda item: (
            item.source_entry,
            item.instruction,
            item.target,
            -1 if item.target_entry is None else item.target_entry,
            item.target_name,
        ),
    )
    if len(set(normalized)) != len(normalized):
        raise ProgramFactsError("duplicate direct call edge")
    for call in normalized:
        source = by_entry.get(call.source_entry)
        if source is None:
            raise ProgramFactsError("direct call references an unknown source function")
        if not _contains(source.ranges, call.instruction):
            raise ProgramFactsError("direct call instruction is outside its source body")
        _range_bytes(image, data, call.target, 1)
        if call.target_entry is not None:
            target = by_entry.get(call.target_entry)
            if target is None:
                raise ProgramFactsError("direct call references an unknown target function")
            if not _contains(target.ranges, call.target):
                raise ProgramFactsError(
                    "direct call target is outside its declared target function"
                )
            accepted_names = {target.name}
            if target.namespace:
                accepted_names.add(f"{target.namespace}::{target.name}")
            if call.target_name not in accepted_names:
                raise ProgramFactsError(
                    "direct call target name disagrees with its target function"
                )
        elif call.target_name:
            raise ProgramFactsError(
                "direct call without a target function must not claim a target name"
            )
    return normalized


def _union_size(ranges: list[tuple[int, int]]) -> int:
    if not ranges:
        return 0
    total = 0
    start, size = sorted(ranges)[0]
    end = start + size
    for next_start, next_size in sorted(ranges)[1:]:
        next_end = next_start + next_size
        if next_start <= end:
            end = max(end, next_end)
        else:
            total += end - start
            start, end = next_start, next_end
    return total + end - start


def _summary(
    functions: list[_FunctionRecord],
    calls: list[_CallRecord],
    image: PEImage,
    omitted_call_targets: int,
) -> dict[str, int]:
    all_ranges = [body_range for function in functions for body_range in function.ranges]
    unique_bytes = _union_size(all_ranges)
    executable_bytes = sum(
        section.raw_size for section in image.sections if section.executable
    )
    return {
        "function_count": len(functions),
        "body_range_count": len(all_ranges),
        "ghidra_declared_direct_internal_call_count": len(calls),
        "omitted_call_target_count": omitted_call_targets,
        "function_body_bytes": sum(function.body_size for function in functions),
        "unique_function_body_bytes": unique_bytes,
        "executable_file_bytes": executable_bytes,
        "ghidra_function_discovery_coverage_basis_points": (
            unique_bytes * 10_000 // executable_bytes if executable_bytes else 0
        ),
    }


def _function_json(function: _FunctionRecord, bits: int) -> dict[str, Any]:
    return {
        "entry_rva": _hex(function.entry, bits),
        "name": function.name,
        "namespace": function.namespace,
        "name_source": function.name_source,
        "thunk": function.thunk,
        "body_size": function.body_size,
        "body_sha256": function.body_sha256,
        "ranges": [
            {"start_rva": _hex(start, bits), "size": size}
            for start, size in function.ranges
        ],
    }


def _call_json(call: _CallRecord, bits: int) -> dict[str, Any]:
    return {
        "source_entry_rva": _hex(call.source_entry, bits),
        "instruction_rva": _hex(call.instruction, bits),
        "target_rva": _hex(call.target, bits),
        "target_entry_rva": (
            _hex(call.target_entry, bits) if call.target_entry is not None else None
        ),
        "target_name": call.target_name,
    }


def build_program_facts(
    executable: Path,
    ghidra_facts: Path,
    *,
    inventory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized, executable-verified function atlas."""
    data, image, executable_sha256 = _load_executable(executable)
    facts_payload = _load_regular_file(
        ghidra_facts, "Ghidra facts", MAX_FACTS_BYTES
    )
    metadata, raw_functions, raw_ranges, raw_calls = _parse_fact_rows(facts_payload)
    if metadata["format_version"] != GHIDRA_FACTS_FORMAT_VERSION:
        raise ProgramFactsError("unsupported Ghidra facts format version")
    if metadata["program_name"].casefold() != executable.name.casefold():
        raise ProgramFactsError("Ghidra program name does not match the executable")
    image_base = _rva(metadata["image_base"], "Ghidra image base")
    if image_base != image.image_base:
        raise ProgramFactsError("Ghidra image base does not match the executable")
    functions = _normalize_functions(
        raw_functions,
        raw_ranges,
        image=image,
        data=data,
    )
    calls = _normalize_calls(raw_calls, functions, image=image, data=data)
    expected_counts = {
        "function_count": len(functions),
        "range_count": len(raw_ranges),
        "direct_internal_call_count": len(calls),
    }
    for key, expected in expected_counts.items():
        if _decimal_count(metadata[key], f"Ghidra metadata {key}") != expected:
            raise ProgramFactsError(f"Ghidra metadata {key} disagrees with rows")
    omitted = _decimal_count(
        metadata["omitted_call_target_count"],
        "Ghidra metadata omitted_call_target_count",
    )
    identity = _inventory_identity(
        inventory,
        sha256=executable_sha256,
        size=len(data),
        architecture=image.architecture,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "identity": identity,
        "ghidra": {
            "facts_format_version": GHIDRA_FACTS_FORMAT_VERSION,
            "version": _text(metadata["ghidra_version"], "Ghidra version"),
            "program_name": metadata["program_name"],
            "language_id": _text(metadata["language_id"], "Ghidra language ID"),
            "compiler_spec_id": _text(
                metadata["compiler_spec_id"], "Ghidra compiler spec ID"
            ),
            "image_base": _hex(image.image_base, image.bits),
            "facts_sha256": hashlib.sha256(facts_payload).hexdigest(),
        },
        "functions": [_function_json(function, image.bits) for function in functions],
        "ghidra_declared_direct_calls": [
            _call_json(call, image.bits) for call in calls
        ],
        "summary": _summary(functions, calls, image, omitted),
        "method": _METHOD,
    }


def _records_from_evidence(
    evidence: Mapping[str, Any], image: PEImage, data: bytes
) -> tuple[list[_FunctionRecord], list[_CallRecord], int]:
    raw_functions: dict[int, dict[str, Any]] = {}
    raw_ranges: list[tuple[int, int, int]] = []
    for index, raw in enumerate(_array(evidence.get("functions"), "functions")):
        label = f"functions[{index}]"
        item = _object(raw, label)
        _exact_keys(
            item,
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
        entry = _rva(item["entry_rva"], f"{label}.entry_rva")
        if entry in raw_functions:
            raise ProgramFactsError("duplicate function entry in evidence")
        if type(item["thunk"]) is not bool:
            raise ProgramFactsError(f"{label}.thunk must be boolean")
        raw_functions[entry] = {
            "name": _text(item["name"], f"{label}.name"),
            "namespace": _text(
                item["namespace"], f"{label}.namespace", allow_empty=True
            ),
            "name_source": _text(item["name_source"], f"{label}.name_source"),
            "thunk": item["thunk"],
            "body_size": _count(item["body_size"], f"{label}.body_size"),
            "body_sha256": _sha256(
                item["body_sha256"], f"{label}.body_sha256"
            ),
        }
        for range_index, raw_range in enumerate(
            _array(item["ranges"], f"{label}.ranges")
        ):
            range_label = f"{label}.ranges[{range_index}]"
            body_range = _object(raw_range, range_label)
            _exact_keys(body_range, {"start_rva", "size"}, range_label)
            raw_ranges.append(
                (
                    entry,
                    _rva(body_range["start_rva"], f"{range_label}.start_rva"),
                    _count(body_range["size"], f"{range_label}.size"),
                )
            )
    functions = _normalize_functions(
        raw_functions, raw_ranges, image=image, data=data
    )

    raw_calls: list[_CallRecord] = []
    for index, raw in enumerate(
        _array(
            evidence.get("ghidra_declared_direct_calls"),
            "ghidra_declared_direct_calls",
        )
    ):
        label = f"ghidra_declared_direct_calls[{index}]"
        item = _object(raw, label)
        _exact_keys(
            item,
            {
                "source_entry_rva",
                "instruction_rva",
                "target_rva",
                "target_entry_rva",
                "target_name",
            },
            label,
        )
        target_entry_value = item["target_entry_rva"]
        raw_calls.append(
            _CallRecord(
                source_entry=_rva(
                    item["source_entry_rva"], f"{label}.source_entry_rva"
                ),
                instruction=_rva(
                    item["instruction_rva"], f"{label}.instruction_rva"
                ),
                target=_rva(item["target_rva"], f"{label}.target_rva"),
                target_entry=(
                    None
                    if target_entry_value is None
                    else _rva(target_entry_value, f"{label}.target_entry_rva")
                ),
                target_name=_text(
                    item["target_name"], f"{label}.target_name", allow_empty=True
                ),
            )
        )
    calls = _normalize_calls(raw_calls, functions, image=image, data=data)
    summary = _object(evidence.get("summary"), "summary")
    omitted = _count(
        summary.get("omitted_call_target_count"),
        "summary.omitted_call_target_count",
    )
    return functions, calls, omitted


def validate_program_facts(
    executable: Path,
    evidence: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify a normalized atlas against the exact executable and inventory."""
    evidence = _object(evidence, "evidence")
    _exact_keys(
        evidence,
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
        "evidence",
    )
    if (
        type(evidence["schema_version"]) is not int
        or evidence["schema_version"] != SCHEMA_VERSION
    ):
        raise ProgramFactsError("unsupported program-facts schema version")
    if evidence["analysis_kind"] != ANALYSIS_KIND:
        raise ProgramFactsError("unexpected program-facts analysis kind")
    if evidence["method"] != _METHOD:
        raise ProgramFactsError("program-facts method contract has drifted")

    data, image, executable_sha256 = _load_executable(executable)
    expected_identity = _inventory_identity(
        inventory,
        sha256=executable_sha256,
        size=len(data),
        architecture=image.architecture,
    )
    if evidence["identity"] != expected_identity:
        raise ProgramFactsError("program-facts identity does not match the executable")

    ghidra = _object(evidence["ghidra"], "ghidra")
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
        "ghidra",
    )
    if ghidra["facts_format_version"] != GHIDRA_FACTS_FORMAT_VERSION:
        raise ProgramFactsError("unsupported recorded Ghidra facts version")
    _text(ghidra["version"], "ghidra.version")
    if _text(ghidra["program_name"], "ghidra.program_name").casefold() != executable.name.casefold():
        raise ProgramFactsError("recorded Ghidra program name does not match")
    _text(ghidra["language_id"], "ghidra.language_id")
    _text(ghidra["compiler_spec_id"], "ghidra.compiler_spec_id")
    if _rva(ghidra["image_base"], "ghidra.image_base") != image.image_base:
        raise ProgramFactsError("recorded Ghidra image base does not match")
    _sha256(ghidra["facts_sha256"], "ghidra.facts_sha256")

    functions, calls, omitted = _records_from_evidence(evidence, image, data)
    expected_summary = _summary(functions, calls, image, omitted)
    summary = _object(evidence["summary"], "summary")
    _exact_keys(summary, set(expected_summary), "summary")
    for key, expected in expected_summary.items():
        if _count(summary[key], f"summary.{key}") != expected:
            raise ProgramFactsError(f"program-facts summary {key} has drifted")

    canonical = json.dumps(
        evidence,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "identity": expected_identity,
        "evidence_sha256": hashlib.sha256(
            (canonical + "\n").encode("utf-8")
        ).hexdigest(),
        "summary": expected_summary,
    }


def encode_program_facts(value: Mapping[str, Any]) -> str:
    """Encode evidence or verification output deterministically."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
