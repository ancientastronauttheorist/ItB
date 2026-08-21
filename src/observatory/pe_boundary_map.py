"""Validate reviewed, build-keyed native-boundary evidence for a PE image.

The evidence contains addresses, normalized claims, and hashes of reviewed code
regions.  It deliberately contains neither executable bytes nor decompiled
source.  Validation proves identity, region integrity, and selected direct call
edges decoded relative to the declared reviewed region starts.  It does not
independently discover those starts; boundary selection and prose semantics
remain explicitly classified analyst evidence.
"""

from __future__ import annotations

import hashlib
import re
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.pe_anchor_map import (
    MAX_EXECUTABLE_BYTES,
    PEAnchorError,
    PEImage,
    _inventory_identity,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_reviewed_boundary_map"
SUPPORTED_CAPSTONE_VERSION = "5.0.7"
MAX_REGION_BYTES = 16 * 1024 * 1024
_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")
_RVA_PATTERN = re.compile(r"0x[0-9a-f]{8}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_EVIDENCE_CLASSES = {"fact", "inference", "hypothesis"}
_HOOK_STATUSES = {
    "proven_static_boundary",
    "partial_static_boundary",
    "disproven_boundary",
    "unresolved",
}


class PEBoundaryError(PEAnchorError):
    """Raised when reviewed native-boundary evidence cannot be verified."""


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PEBoundaryError(f"{label} must be an object")
    return value


def _exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise PEBoundaryError(
            f"{label} fields differ; missing={missing}, unknown={unknown}"
        )


def _string(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        raise PEBoundaryError(f"{label} must be a non-empty string")
    return value


def _identifier(value: Any, label: str) -> str:
    result = _string(value, label)
    if _ID_PATTERN.fullmatch(result) is None:
        raise PEBoundaryError(f"{label} is not a canonical identifier")
    return result


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise PEBoundaryError(f"{label} must be an array")
    return [_string(item, f"{label}[{index}]") for index, item in enumerate(value)]


def _rva(value: Any, label: str) -> int:
    if type(value) is not str or _RVA_PATTERN.fullmatch(value) is None:
        raise PEBoundaryError(f"{label} must be a canonical 32-bit RVA")
    return int(value, 16)


def _evidence_class(value: Any, label: str) -> str:
    result = _string(value, label)
    if result not in _EVIDENCE_CLASSES:
        raise PEBoundaryError(f"{label} has an unsupported evidence class")
    return result


def _load_executable(executable: Path) -> tuple[bytes, PEImage, str]:
    if executable.is_symlink() or not executable.is_file():
        raise PEBoundaryError(
            f"executable is not a regular non-symlink file: {executable}"
        )
    before = executable.stat()
    if before.st_size > MAX_EXECUTABLE_BYTES:
        raise PEBoundaryError("executable exceeds analysis size limit")
    data = executable.read_bytes()
    after = executable.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(data) != before.st_size
    ):
        raise PEBoundaryError("executable changed during validation")
    return data, PEImage(data), hashlib.sha256(data).hexdigest()


def _region_bytes(
    image: PEImage,
    data: bytes,
    start: int,
    size: int,
    expected_section: str,
    label: str,
) -> bytes:
    offset = image.rva_span_to_file_offset(start, size)
    if offset is None:
        raise PEBoundaryError(f"{label} is not contiguous file-backed data")
    section = None
    for candidate in image.sections:
        if (
            candidate.virtual_address <= start
            and start + size
            <= candidate.virtual_address + candidate.raw_size
        ):
            section = candidate
            break
    if section is None or not section.executable:
        raise PEBoundaryError(f"{label} is not wholly executable code")
    if section.name != expected_section:
        raise PEBoundaryError(
            f"{label} section mismatch: {expected_section!r} != {section.name!r}"
        )
    return data[offset : offset + size]


def _validate_regions(
    value: Any,
    image: PEImage,
    data: bytes,
) -> dict[str, tuple[int, int]]:
    if not isinstance(value, list) or not value:
        raise PEBoundaryError("regions must be a non-empty array")
    regions: dict[str, tuple[int, int]] = {}
    for index, raw in enumerate(value):
        label = f"regions[{index}]"
        item = _object(raw, label)
        _exact_keys(
            item,
            {
                "id",
                "evidence_class",
                "start_rva",
                "end_rva_exclusive",
                "size",
                "sha256",
                "section",
                "boundary_basis",
            },
            label,
        )
        region_id = _identifier(item["id"], f"{label}.id")
        if region_id in regions:
            raise PEBoundaryError(f"duplicate region id: {region_id}")
        if _evidence_class(item["evidence_class"], f"{label}.evidence_class") != "fact":
            raise PEBoundaryError(f"{label} region integrity must be a fact")
        start = _rva(item["start_rva"], f"{label}.start_rva")
        end = _rva(item["end_rva_exclusive"], f"{label}.end_rva_exclusive")
        size = item["size"]
        if (
            type(size) is not int
            or size < 1
            or size > MAX_REGION_BYTES
            or end <= start
            or end - start != size
        ):
            raise PEBoundaryError(f"{label} has an invalid range or size")
        digest = item["sha256"]
        if type(digest) is not str or _SHA256_PATTERN.fullmatch(digest) is None:
            raise PEBoundaryError(f"{label}.sha256 is not lowercase SHA-256")
        section = _string(item["section"], f"{label}.section")
        _string(item["boundary_basis"], f"{label}.boundary_basis")
        body = _region_bytes(image, data, start, size, section, label)
        actual_digest = hashlib.sha256(body).hexdigest()
        if actual_digest != digest:
            raise PEBoundaryError(
                f"{label} SHA-256 mismatch: {digest} != {actual_digest}"
            )
        regions[region_id] = (start, end)
    return regions


def _inside_region(
    address: int,
    size: int,
    region: tuple[int, int],
) -> bool:
    return region[0] <= address and address + size <= region[1]


def _decode_x86_regions(
    image: PEImage,
    data: bytes,
    regions: Mapping[str, tuple[int, int]],
) -> dict[str, dict[int, tuple[str, bytes]]]:
    """Decode each region from its declared start to constrain alleged calls."""
    try:
        from capstone import (
            CS_ARCH_X86,
            CS_MODE_32,
            Cs,
            CsError,
            __version__ as capstone_version,
        )
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise PEBoundaryError(
            f"Capstone {SUPPORTED_CAPSTONE_VERSION} is required for x86 decoding"
        ) from exc
    if capstone_version != SUPPORTED_CAPSTONE_VERSION:
        raise PEBoundaryError(
            "unsupported Capstone version for native-boundary schema 1: "
            f"{capstone_version} != {SUPPORTED_CAPSTONE_VERSION}"
        )

    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    decoded: dict[str, dict[int, tuple[str, bytes]]] = {}
    for region_id, (start, end) in regions.items():
        size = end - start
        offset = image.rva_span_to_file_offset(start, size)
        if offset is None:  # Region validation already rejects this condition.
            raise PEBoundaryError(f"region {region_id} is not file-backed")
        body = data[offset : offset + size]
        instructions: dict[int, tuple[str, bytes]] = {}
        cursor = start
        try:
            for instruction in decoder.disasm(body, start):
                encoded = bytes(instruction.bytes)
                if (
                    instruction.address != cursor
                    or instruction.size < 1
                    or len(encoded) != instruction.size
                ):
                    raise PEBoundaryError(
                        f"region {region_id} has a non-contiguous x86 decode "
                        f"at 0x{cursor:08x}"
                    )
                instructions[instruction.address] = (
                    instruction.mnemonic,
                    encoded,
                )
                cursor += instruction.size
        except CsError as exc:
            raise PEBoundaryError(
                f"Capstone failed while decoding region {region_id}: {exc}"
            ) from exc
        if cursor != end:
            raise PEBoundaryError(
                f"region {region_id} does not decode completely from its entry; "
                f"stopped at 0x{cursor:08x}, expected 0x{end:08x}"
            )
        decoded[region_id] = instructions
    return decoded


def _validate_call_edges(
    value: Any,
    image: PEImage,
    data: bytes,
    regions: Mapping[str, tuple[int, int]],
) -> None:
    if not isinstance(value, list):
        raise PEBoundaryError("direct_call_edges must be an array")
    edge_ids: set[str] = set()
    imports = image.imports()
    decoded_regions = _decode_x86_regions(image, data, regions)
    for index, raw in enumerate(value):
        label = f"direct_call_edges[{index}]"
        item = _object(raw, label)
        _exact_keys(
            item,
            {
                "id",
                "evidence_class",
                "source_region",
                "from_rva",
                "kind",
                "target",
                "meaning",
            },
            label,
        )
        edge_id = _identifier(item["id"], f"{label}.id")
        if edge_id in edge_ids:
            raise PEBoundaryError(f"duplicate direct-call edge id: {edge_id}")
        edge_ids.add(edge_id)
        if _evidence_class(item["evidence_class"], f"{label}.evidence_class") != "fact":
            raise PEBoundaryError(f"{label} direct-call decoding must be a fact")
        source_id = _identifier(item["source_region"], f"{label}.source_region")
        if source_id not in regions:
            raise PEBoundaryError(f"{label} names an unknown source region")
        from_rva = _rva(item["from_rva"], f"{label}.from_rva")
        kind = _string(item["kind"], f"{label}.kind")
        target = _object(item["target"], f"{label}.target")
        _string(item["meaning"], f"{label}.meaning")

        if kind == "direct_rel32":
            _exact_keys(target, {"type", "region", "rva"}, f"{label}.target")
            if target["type"] != "region":
                raise PEBoundaryError(f"{label} direct target type must be region")
            target_id = _identifier(target["region"], f"{label}.target.region")
            if target_id not in regions:
                raise PEBoundaryError(f"{label} names an unknown target region")
            target_rva = _rva(target["rva"], f"{label}.target.rva")
            if not _inside_region(target_rva, 1, regions[target_id]):
                raise PEBoundaryError(f"{label} target lies outside its region")
            if target_rva not in decoded_regions[target_id]:
                raise PEBoundaryError(
                    f"{label} target is not an x86 instruction boundary"
                )
            if not _inside_region(from_rva, 5, regions[source_id]):
                raise PEBoundaryError(f"{label} call lies outside its source region")
            instruction = decoded_regions[source_id].get(from_rva)
            if instruction is None:
                raise PEBoundaryError(
                    f"{label} call is not an x86 instruction boundary"
                )
            mnemonic, encoded = instruction
            if mnemonic != "call" or len(encoded) != 5 or encoded[0] != 0xE8:
                raise PEBoundaryError(f"{label} is not an x86 rel32 call")
            (relative,) = struct.unpack_from("<i", encoded, 1)
            decoded = (from_rva + 5 + relative) & 0xFFFFFFFF
            if decoded != target_rva:
                raise PEBoundaryError(
                    f"{label} target mismatch: 0x{target_rva:08x} != 0x{decoded:08x}"
                )
        elif kind == "iat_indirect":
            _exact_keys(
                target,
                {"type", "library", "name", "iat_rva"},
                f"{label}.target",
            )
            if target["type"] != "import":
                raise PEBoundaryError(f"{label} IAT target type must be import")
            library = _string(target["library"], f"{label}.target.library")
            name = _string(target["name"], f"{label}.target.name")
            iat_rva = _rva(target["iat_rva"], f"{label}.target.iat_rva")
            if not _inside_region(from_rva, 6, regions[source_id]):
                raise PEBoundaryError(f"{label} call lies outside its source region")
            instruction = decoded_regions[source_id].get(from_rva)
            if instruction is None:
                raise PEBoundaryError(
                    f"{label} call is not an x86 instruction boundary"
                )
            mnemonic, encoded = instruction
            if (
                mnemonic != "call"
                or len(encoded) != 6
                or encoded[:2] != b"\xff\x15"
            ):
                raise PEBoundaryError(f"{label} is not an x86 absolute IAT call")
            (slot_va,) = struct.unpack_from("<I", encoded, 2)
            expected_va = image.image_base + iat_rva
            if slot_va != expected_va:
                raise PEBoundaryError(
                    f"{label} IAT slot mismatch: 0x{expected_va:08x} != 0x{slot_va:08x}"
                )
            if not any(
                record["iat_rva"] == f"0x{iat_rva:08x}"
                and str(record["library"]).casefold() == library.casefold()
                and record["name"] == name
                for record in imports
            ):
                raise PEBoundaryError(f"{label} target is not the named PE import")
        else:
            raise PEBoundaryError(f"{label} has unsupported call kind: {kind}")


def _validate_method(value: Any) -> None:
    method = _object(value, "method")
    _exact_keys(method, {"tools", "procedure", "limitations"}, "method")
    tools = method["tools"]
    if not isinstance(tools, list) or not tools:
        raise PEBoundaryError("method.tools must be a non-empty array")
    for index, raw in enumerate(tools):
        label = f"method.tools[{index}]"
        item = _object(raw, label)
        _exact_keys(item, {"name", "version", "role"}, label)
        for field in ("name", "version", "role"):
            _string(item[field], f"{label}.{field}")
    if not _string_list(method["procedure"], "method.procedure"):
        raise PEBoundaryError("method.procedure must not be empty")
    if not _string_list(method["limitations"], "method.limitations"):
        raise PEBoundaryError("method.limitations must not be empty")


def _validate_findings(
    value: Any,
    regions: Mapping[str, tuple[int, int]],
) -> int:
    if not isinstance(value, list) or not value:
        raise PEBoundaryError("findings must be a non-empty array")
    finding_ids: set[str] = set()
    for index, raw in enumerate(value):
        label = f"findings[{index}]"
        item = _object(raw, label)
        _exact_keys(
            item,
            {
                "id",
                "evidence_class",
                "regions",
                "claim",
                "implications",
                "limitations",
            },
            label,
        )
        finding_id = _identifier(item["id"], f"{label}.id")
        if finding_id in finding_ids:
            raise PEBoundaryError(f"duplicate finding id: {finding_id}")
        finding_ids.add(finding_id)
        _evidence_class(item["evidence_class"], f"{label}.evidence_class")
        region_ids = _string_list(item["regions"], f"{label}.regions")
        if not region_ids:
            raise PEBoundaryError(f"{label}.regions must not be empty")
        for region_id in region_ids:
            if _ID_PATTERN.fullmatch(region_id) is None or region_id not in regions:
                raise PEBoundaryError(f"{label} names an unknown region: {region_id}")
        _string(item["claim"], f"{label}.claim")
        _string_list(item["implications"], f"{label}.implications")
        _string_list(item["limitations"], f"{label}.limitations")
    return len(finding_ids)


def _validate_hook_boundaries(
    value: Any,
    regions: Mapping[str, tuple[int, int]],
) -> int:
    if not isinstance(value, list) or not value:
        raise PEBoundaryError("hook_boundaries must be a non-empty array")
    hook_ids: set[str] = set()
    for index, raw in enumerate(value):
        label = f"hook_boundaries[{index}]"
        item = _object(raw, label)
        _exact_keys(
            item,
            {
                "id",
                "evidence_class",
                "status",
                "boundary",
                "regions",
                "captures",
                "misses",
                "runtime_proof_required",
            },
            label,
        )
        hook_id = _identifier(item["id"], f"{label}.id")
        if hook_id in hook_ids:
            raise PEBoundaryError(f"duplicate hook-boundary id: {hook_id}")
        hook_ids.add(hook_id)
        _evidence_class(item["evidence_class"], f"{label}.evidence_class")
        status = _string(item["status"], f"{label}.status")
        if status not in _HOOK_STATUSES:
            raise PEBoundaryError(f"{label} has unsupported hook status")
        _string(item["boundary"], f"{label}.boundary")
        for region_id in _string_list(item["regions"], f"{label}.regions"):
            if _ID_PATTERN.fullmatch(region_id) is None or region_id not in regions:
                raise PEBoundaryError(f"{label} names an unknown region: {region_id}")
        _string_list(item["captures"], f"{label}.captures")
        _string_list(item["misses"], f"{label}.misses")
        _string_list(
            item["runtime_proof_required"],
            f"{label}.runtime_proof_required",
        )
    return len(hook_ids)


def _validate_unresolved(value: Any) -> int:
    if not isinstance(value, list):
        raise PEBoundaryError("unresolved must be an array")
    unresolved_ids: set[str] = set()
    for index, raw in enumerate(value):
        label = f"unresolved[{index}]"
        item = _object(raw, label)
        _exact_keys(
            item,
            {"id", "question", "static_status", "next_evidence"},
            label,
        )
        unresolved_id = _identifier(item["id"], f"{label}.id")
        if unresolved_id in unresolved_ids:
            raise PEBoundaryError(f"duplicate unresolved id: {unresolved_id}")
        unresolved_ids.add(unresolved_id)
        for field in ("question", "static_status", "next_evidence"):
            _string(item[field], f"{label}.{field}")
    return len(unresolved_ids)


def validate_pe_boundary_map(
    executable: Path,
    evidence: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed unless reviewed evidence matches the exact executable."""
    record = _object(evidence, "evidence")
    _exact_keys(
        record,
        {
            "schema_version",
            "analysis_kind",
            "identity",
            "pe",
            "method",
            "regions",
            "direct_call_edges",
            "findings",
            "hook_boundaries",
            "unresolved",
            "summary",
        },
        "evidence",
    )
    if record["schema_version"] != SCHEMA_VERSION:
        raise PEBoundaryError("unsupported native-boundary schema version")
    if record["analysis_kind"] != ANALYSIS_KIND:
        raise PEBoundaryError("unexpected native-boundary analysis kind")

    data, image, executable_sha256 = _load_executable(executable)
    if image.architecture != "x86" or image.bits != 32:
        raise PEBoundaryError("reviewed x86 call decoding requires a PE32 x86 image")
    identity = _inventory_identity(
        inventory,
        sha256=executable_sha256,
        size=len(data),
        architecture=image.architecture,
    )
    if record["identity"] != identity:
        raise PEBoundaryError("evidence identity does not match executable inventory")

    pe = _object(record["pe"], "pe")
    _exact_keys(pe, {"bits", "image_base"}, "pe")
    expected_pe = {"bits": image.bits, "image_base": f"0x{image.image_base:08x}"}
    if pe != expected_pe:
        raise PEBoundaryError("PE metadata does not match the executable")

    _validate_method(record["method"])
    regions = _validate_regions(record["regions"], image, data)
    _validate_call_edges(record["direct_call_edges"], image, data, regions)
    finding_count = _validate_findings(record["findings"], regions)
    hook_count = _validate_hook_boundaries(record["hook_boundaries"], regions)
    unresolved_count = _validate_unresolved(record["unresolved"])

    summary = _object(record["summary"], "summary")
    _exact_keys(
        summary,
        {
            "region_count",
            "direct_call_edge_count",
            "finding_count",
            "hook_boundary_count",
            "unresolved_count",
        },
        "summary",
    )
    expected_summary = {
        "region_count": len(regions),
        "direct_call_edge_count": len(record["direct_call_edges"]),
        "finding_count": finding_count,
        "hook_boundary_count": hook_count,
        "unresolved_count": unresolved_count,
    }
    if summary != expected_summary:
        raise PEBoundaryError("native-boundary summary counts are inconsistent")

    return {
        "analysis_kind": ANALYSIS_KIND,
        "schema_version": SCHEMA_VERSION,
        "status": "verified",
        "identity": identity,
        "summary": expected_summary,
    }


def encode_boundary_verification(value: Mapping[str, Any]) -> str:
    """Return deterministic JSON for a successful verification result."""
    import json

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
