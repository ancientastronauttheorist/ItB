#!/usr/bin/env python3
"""Build and attest the dormant, build-keyed x86 RNG-core observer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "native" / "observatory_rng_core_observer.c"
OBSERVER_VERSION = "observatory-rng-core-observer/1"
EXPORT_NAME = "luaopen_itb_observatory_rng_core_observer"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_ARCHITECTURE = "x86"
EXPECTED_PE_TIMESTAMP = 0x65F16972
EXPECTED_PE_SIZE_OF_IMAGE = 0x0056F000
EXPECTED_RNG_CORE_RVA = 0x00387F16
EXPECTED_RNG_CORE_SIZE = 33
EXPECTED_RNG_CORE_SHA256 = (
    "3d7a67186e320b23a31d2ca6f9281211b373b60d44f35531cf4369da45cf0179"
)
EXPECTED_RNG_STATE_OWNER_RVA = 0x0038ED32
EXPECTED_CALLER_COUNT = 118
EXPECTED_RETURN_MAP_SHA256 = (
    "7da4ababb6aa91d7b834e68ea6d42a8a40b6ae379531f42cbbc96556cdcaae48"
)
MAX_CALLER_ID = 255

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RVA_RE = re.compile(r"^0x[0-9a-f]{8}$")


class ObserverBuildError(RuntimeError):
    """Raised when observer compilation or attestation cannot be trusted."""


@dataclass(frozen=True)
class Section:
    name: str
    virtual_address: int
    virtual_size: int
    raw_offset: int
    raw_size: int
    characteristics: int

    @property
    def executable(self) -> bool:
        return bool(self.characteristics & 0x20000000)


@dataclass(frozen=True)
class PEImage:
    machine: int
    timestamp: int
    entry_point: int
    size_of_image: int
    image_base: int
    sections: tuple[Section, ...]
    export_rva: int
    export_size: int
    import_rva: int
    import_size: int

    def rva_to_offset(self, rva: int, size: int = 1) -> int:
        if rva < 0 or size < 0:
            raise ObserverBuildError("negative PE RVA or size")
        for section in self.sections:
            extent = max(section.virtual_size, section.raw_size)
            if section.virtual_address <= rva and rva + size <= (
                section.virtual_address + extent
            ):
                delta = rva - section.virtual_address
                if delta + size > section.raw_size:
                    raise ObserverBuildError("PE RVA is not file-backed")
                return section.raw_offset + delta
        raise ObserverBuildError(f"PE RVA 0x{rva:08x} is outside sections")

    def section_for_rva(self, rva: int) -> Section:
        for section in self.sections:
            if section.virtual_address <= rva < (
                section.virtual_address + max(section.virtual_size, section.raw_size)
            ):
                return section
        raise ObserverBuildError(f"PE RVA 0x{rva:08x} has no section")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--native-boundaries", type=Path, required=True)
    parser.add_argument("--rng-return-map", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _stable_bytes(path: Path, label: str) -> bytes:
    path = Path(os.path.abspath(path.expanduser()))
    if path.is_symlink() or not path.is_file():
        raise ObserverBuildError(f"{label} is not a regular file: {path}")
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(data) != before.st_size
    ):
        raise ObserverBuildError(f"{label} changed while being read")
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    data = _stable_bytes(path, label)
    try:
        value = json.loads(data.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ObserverBuildError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ObserverBuildError(f"{label} must be an object")
    return value, data


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _compact_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _canonical_object_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256(encoded)


def _u16(data: bytes, offset: int, label: str) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ObserverBuildError(f"truncated PE while reading {label}")
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int, label: str) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ObserverBuildError(f"truncated PE while reading {label}")
    return struct.unpack_from("<I", data, offset)[0]


def _parse_pe(data: bytes) -> PEImage:
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ObserverBuildError("image is not an MZ executable")
    pe_offset = _u32(data, 0x3C, "PE offset")
    if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ObserverBuildError("image has an invalid PE signature")
    coff = pe_offset + 4
    machine = _u16(data, coff, "machine")
    section_count = _u16(data, coff + 2, "section count")
    timestamp = _u32(data, coff + 4, "timestamp")
    optional_size = _u16(data, coff + 16, "optional header size")
    optional = coff + 20
    if optional + optional_size > len(data) or optional_size < 104:
        raise ObserverBuildError("PE optional header is truncated")
    if _u16(data, optional, "optional magic") != 0x10B:
        raise ObserverBuildError("image is not PE32")
    image_base = _u32(data, optional + 28, "image base")
    entry_point = _u32(data, optional + 16, "entry point")
    size_of_image = _u32(data, optional + 56, "size of image")
    directory_count = _u32(data, optional + 92, "directory count")
    export_rva = export_size = import_rva = import_size = 0
    if directory_count >= 1 and optional_size >= 104:
        export_rva = _u32(data, optional + 96, "export RVA")
        export_size = _u32(data, optional + 100, "export size")
    if directory_count >= 2 and optional_size >= 112:
        import_rva = _u32(data, optional + 104, "import RVA")
        import_size = _u32(data, optional + 108, "import size")
    section_offset = optional + optional_size
    if not 1 <= section_count <= 96 or section_offset + section_count * 40 > len(data):
        raise ObserverBuildError("PE section table is invalid")
    sections: list[Section] = []
    for index in range(section_count):
        offset = section_offset + index * 40
        raw_name = data[offset : offset + 8].split(b"\0", 1)[0]
        try:
            name = raw_name.decode("ascii", errors="strict")
        except UnicodeDecodeError as exc:
            raise ObserverBuildError("PE section name is not ASCII") from exc
        sections.append(
            Section(
                name=name,
                virtual_size=_u32(data, offset + 8, "section virtual size"),
                virtual_address=_u32(data, offset + 12, "section RVA"),
                raw_size=_u32(data, offset + 16, "section raw size"),
                raw_offset=_u32(data, offset + 20, "section raw offset"),
                characteristics=_u32(data, offset + 36, "section characteristics"),
            )
        )
    for section in sections:
        if section.raw_offset + section.raw_size > len(data):
            raise ObserverBuildError(f"PE section {section.name} exceeds the file")
    return PEImage(
        machine=machine,
        timestamp=timestamp,
        entry_point=entry_point,
        size_of_image=size_of_image,
        image_base=image_base,
        sections=tuple(sections),
        export_rva=export_rva,
        export_size=export_size,
        import_rva=import_rva,
        import_size=import_size,
    )


def _read_c_string(data: bytes, offset: int, label: str) -> str:
    if offset < 0 or offset >= len(data):
        raise ObserverBuildError(f"{label} string offset is invalid")
    end = data.find(b"\0", offset, min(len(data), offset + 4096))
    if end < 0:
        raise ObserverBuildError(f"{label} string is unterminated")
    try:
        return data[offset:end].decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise ObserverBuildError(f"{label} string is not ASCII") from exc


def _pe_exports(data: bytes, image: PEImage) -> list[str]:
    if image.export_rva == 0 or image.export_size < 40:
        return []
    directory = image.rva_to_offset(image.export_rva, 40)
    name_count = _u32(data, directory + 24, "export name count")
    names_rva = _u32(data, directory + 32, "export names RVA")
    if name_count > 1024:
        raise ObserverBuildError("compiled observer has too many exports")
    names_offset = image.rva_to_offset(names_rva, name_count * 4)
    result = []
    for index in range(name_count):
        name_rva = _u32(data, names_offset + index * 4, "export name RVA")
        result.append(
            _read_c_string(data, image.rva_to_offset(name_rva), "export name")
        )
    return result


def _pe_imports(data: bytes, image: PEImage) -> list[str]:
    if image.import_rva == 0:
        return []
    offset = image.rva_to_offset(image.import_rva, 20)
    result: list[str] = []
    for _index in range(128):
        if offset + 20 > len(data):
            raise ObserverBuildError("compiled observer import table is truncated")
        descriptor = data[offset : offset + 20]
        if descriptor == b"\0" * 20:
            return result
        name_rva = _u32(data, offset + 12, "import name RVA")
        result.append(
            _read_c_string(data, image.rva_to_offset(name_rva), "import name")
        )
        offset += 20
    raise ObserverBuildError("compiled observer import table is unterminated")


def _unique_masked_stub(
    body: bytes,
    pattern: bytes,
    mask: bytes,
    label: str,
) -> int:
    if len(pattern) != len(mask):
        raise AssertionError("masked stub pattern lengths differ")
    matches = []
    for offset in range(len(body) - len(pattern) + 1):
        if all(
            not mask[index] or body[offset + index] == pattern[index]
            for index in range(len(pattern))
        ):
            matches.append(offset)
    if len(matches) != 1:
        raise ObserverBuildError(
            f"compiled observer needs one exact {label} stub; found {len(matches)}"
        )
    return matches[0]


def _attest_hot_function(
    body: bytes,
    *,
    start_rva: int,
    end_rva: int,
    image_base: int,
    label: str,
) -> dict[str, Any]:
    try:
        import capstone
        import capstone.x86_const as x86_const
        from capstone.x86 import X86_OP_IMM
    except ImportError as exc:
        raise ObserverBuildError("Capstone 5.0.7 is required for hot-path proof") from exc
    if capstone.__version__ != "5.0.7":
        raise ObserverBuildError(
            f"unreviewed Capstone version for hot-path proof: {capstone.__version__}"
        )
    if not 0 <= start_rva < end_rva <= len(body):
        raise ObserverBuildError(f"compiled {label} range is invalid")
    raw_with_padding = body[start_rva:end_rva]
    raw = raw_with_padding.rstrip(b"\xcc")
    if not raw or len(raw_with_padding) - len(raw) < 4:
        raise ObserverBuildError(f"compiled {label} lacks a guarded padding boundary")
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    instructions = list(decoder.disasm(raw, image_base + start_rva))
    if not instructions or sum(item.size for item in instructions) != len(raw):
        raise ObserverBuildError(f"compiled {label} does not decode contiguously")
    return_count = 0
    branch_count = 0
    vector_or_fpu_groups = tuple(
        getattr(x86_const, name)
        for name in (
            "X86_GRP_FPU",
            "X86_GRP_MMX",
            "X86_GRP_SSE1",
            "X86_GRP_SSE2",
            "X86_GRP_SSE3",
            "X86_GRP_SSSE3",
            "X86_GRP_SSE41",
            "X86_GRP_SSE42",
            "X86_GRP_AVX",
            "X86_GRP_AVX2",
            "X86_GRP_AVX512",
        )
        if hasattr(x86_const, name)
    )
    for instruction in instructions:
        if instruction.group(capstone.CS_GRP_CALL):
            raise ObserverBuildError(f"compiled {label} contains a hot-path call")
        if instruction.mnemonic in {"int", "int1", "int3", "syscall", "sysenter", "hlt"}:
            raise ObserverBuildError(
                f"compiled {label} contains {instruction.mnemonic}"
            )
        if any(instruction.group(group) for group in vector_or_fpu_groups):
            raise ObserverBuildError(
                f"compiled {label} changes vector, MMX, or x87 state"
            )
        registers = instruction.regs_access()[0] + instruction.regs_access()[1]
        if any(
            instruction.reg_name(register).lower().startswith(
                ("st", "mm", "xmm", "ymm", "zmm", "mxcsr")
            )
            for register in registers
        ):
            raise ObserverBuildError(
                f"compiled {label} references vector, MMX, or x87 registers"
            )
        if instruction.group(capstone.CS_GRP_JUMP):
            branch_count += 1
            if (
                len(instruction.operands) != 1
                or instruction.operands[0].type != X86_OP_IMM
                or not (
                    image_base + start_rva
                    <= instruction.operands[0].imm
                    < image_base + start_rva + len(raw)
                )
            ):
                raise ObserverBuildError(
                    f"compiled {label} has an external or indirect hot-path jump"
                )
        if instruction.group(capstone.CS_GRP_RET):
            return_count += 1
    if return_count == 0:
        raise ObserverBuildError(f"compiled {label} has no return path")
    return {
        "rva": f"0x{start_rva:08x}",
        "size": len(raw),
        "sha256": _sha256(raw),
        "instruction_count": len(instructions),
        "branch_count": branch_count,
        "return_count": return_count,
        "direct_or_indirect_call_count": 0,
    }


def _attest_machine_contract(data: bytes, image: PEImage) -> dict[str, Any]:
    executable_sections = [section for section in image.sections if section.executable]
    if len(executable_sections) != 1:
        raise ObserverBuildError("compiled observer must have one executable section")
    section = executable_sections[0]
    body = data[section.raw_offset : section.raw_offset + section.raw_size]

    post_pattern = bytes.fromhex(
        "9c608b44241c50e80000000083c404894424fcf0ff0d00000000619dff7424d8c3"
    )
    post_mask = bytes(
        0 if 8 <= index < 12 or 22 <= index < 26 else 1
        for index in range(len(post_pattern))
    )
    entry_pattern = bytes.fromhex(
        "9c608b44242450e80000000083c40485c07409b80000000089442424619dff2500000000"
    )
    entry_mask = bytes(
        0 if 8 <= index < 12 or 20 <= index < 24 or 32 <= index < 36 else 1
        for index in range(len(entry_pattern))
    )
    post_offset = _unique_masked_stub(body, post_pattern, post_mask, "post-core")
    entry_offset = _unique_masked_stub(body, entry_pattern, entry_mask, "entry")
    post_rva = section.virtual_address + post_offset
    entry_rva = section.virtual_address + entry_offset
    post = body[post_offset : post_offset + len(post_pattern)]
    entry = body[entry_offset : entry_offset + len(entry_pattern)]
    (exit_relative,) = struct.unpack_from("<i", post, 8)
    (enter_relative,) = struct.unpack_from("<i", entry, 8)
    exit_rva = post_rva + 12 + exit_relative
    enter_rva = entry_rva + 12 + enter_relative
    embedded_post = struct.unpack_from("<I", entry, 20)[0]
    gateway_pointer = struct.unpack_from("<I", entry, 32)[0]
    if embedded_post != image.image_base + post_rva:
        raise ObserverBuildError("entry stub does not install the exact post-core address")
    if not (section.virtual_address <= enter_rva < exit_rva < post_rva < entry_rva):
        raise ObserverBuildError("compiled hot helper/stub ordering differs")
    gateway_pointer_rva = gateway_pointer - image.image_base
    gateway_section = image.section_for_rva(gateway_pointer_rva)
    if gateway_section.executable or not (
        gateway_section.characteristics & 0x80000000
    ):
        raise ObserverBuildError("entry gateway pointer is not fixed writable data")

    enter = _attest_hot_function(
        body,
        start_rva=enter_rva - section.virtual_address,
        end_rva=exit_rva - section.virtual_address,
        image_base=image.image_base + section.virtual_address,
        label="observer_enter",
    )
    exit_result = _attest_hot_function(
        body,
        start_rva=exit_rva - section.virtual_address,
        end_rva=post_rva - section.virtual_address,
        image_base=image.image_base + section.virtual_address,
        label="observer_exit",
    )
    enter["rva"] = f"0x{enter_rva:08x}"
    exit_result["rva"] = f"0x{exit_rva:08x}"
    return {
        "pe_entry_point_rva": f"0x{image.entry_point:08x}",
        "loader_entry_absent": image.entry_point == 0,
        "post_core_stub": {
            "rva": f"0x{post_rva:08x}",
            "size": len(post),
            "sha256": _sha256(post),
            "saved_result_offset": 28,
            "return_scratch_offset": -40,
            "exit_target_rva": f"0x{exit_rva:08x}",
        },
        "entry_stub": {
            "rva": f"0x{entry_rva:08x}",
            "size": len(entry),
            "sha256": _sha256(entry),
            "saved_return_offset": 36,
            "post_core_rva": f"0x{post_rva:08x}",
            "enter_target_rva": f"0x{enter_rva:08x}",
            "gateway_pointer_rva": f"0x{gateway_pointer_rva:08x}",
        },
        "observer_enter": enter,
        "observer_exit": exit_result,
    }


def _parse_rva(value: Any, label: str) -> int:
    if type(value) is not str or _RVA_RE.fullmatch(value) is None:
        raise ObserverBuildError(f"{label} is not a canonical RVA")
    return int(value, 16)


def _region(boundaries: dict[str, Any], region_id: str) -> dict[str, Any]:
    regions = boundaries.get("regions")
    if not isinstance(regions, list):
        raise ObserverBuildError("boundary map regions must be an array")
    matches = [
        item
        for item in regions
        if isinstance(item, dict) and item.get("id") == region_id
    ]
    if len(matches) != 1:
        raise ObserverBuildError(f"boundary map needs one {region_id} region")
    return matches[0]


def _validate_inputs(
    executable_path: Path,
    boundaries_path: Path,
    return_map_path: Path,
) -> dict[str, Any]:
    executable = _stable_bytes(executable_path, "Breach.exe")
    executable_sha = _sha256(executable)
    if executable_sha != EXPECTED_EXECUTABLE_SHA256 or len(executable) != (
        EXPECTED_EXECUTABLE_SIZE
    ):
        raise ObserverBuildError("Breach.exe does not match the pinned observer build")
    image = _parse_pe(executable)
    if (
        image.machine != 0x014C
        or image.timestamp != EXPECTED_PE_TIMESTAMP
        or image.size_of_image != EXPECTED_PE_SIZE_OF_IMAGE
    ):
        raise ObserverBuildError("Breach.exe PE identity does not match the observer")

    boundaries, boundary_bytes = _load_json(boundaries_path, "native boundaries")
    return_map, return_map_bytes = _load_json(return_map_path, "RNG return map")
    identity = boundaries.get("identity")
    if (
        boundaries.get("schema_version") != 1
        or boundaries.get("analysis_kind") != "pe_reviewed_boundary_map"
        or not isinstance(identity, dict)
        or identity.get("executable_sha256") != executable_sha
        or identity.get("executable_size") != len(executable)
        or identity.get("build_id") != EXPECTED_BUILD_ID
        or identity.get("architecture") != EXPECTED_ARCHITECTURE
    ):
        raise ObserverBuildError("native boundaries do not match the observer")
    boundary_sha = _canonical_object_sha256(boundaries)

    core = _region(boundaries, "rng_core")
    owner = _region(boundaries, "rng_state_owner")
    if (
        _parse_rva(core.get("start_rva"), "rng_core.start_rva")
        != EXPECTED_RNG_CORE_RVA
        or core.get("size") != EXPECTED_RNG_CORE_SIZE
        or core.get("sha256") != EXPECTED_RNG_CORE_SHA256
        or _parse_rva(owner.get("start_rva"), "rng_state_owner.start_rva")
        != EXPECTED_RNG_STATE_OWNER_RVA
    ):
        raise ObserverBuildError("native RNG boundaries are not the pinned regions")
    core_offset = image.rva_to_offset(EXPECTED_RNG_CORE_RVA, EXPECTED_RNG_CORE_SIZE)
    core_bytes = executable[core_offset : core_offset + EXPECTED_RNG_CORE_SIZE]
    if _sha256(core_bytes) != EXPECTED_RNG_CORE_SHA256:
        raise ObserverBuildError("Breach.exe RNG core bytes differ from the boundary")
    if core_bytes[0] != 0xE8:
        raise ObserverBuildError("RNG core does not begin with a direct call")
    (owner_relative,) = struct.unpack_from("<i", core_bytes, 1)
    owner_target = (EXPECTED_RNG_CORE_RVA + 5 + owner_relative) & 0xFFFFFFFF
    if owner_target != EXPECTED_RNG_STATE_OWNER_RVA:
        raise ObserverBuildError("RNG core entry call does not target the state owner")

    return_identity = return_map.get("identity")
    sources = return_map.get("sources")
    rng_core = return_map.get("rng_core")
    callers = return_map.get("callers")
    if (
        return_map.get("schema_version") != 1
        or return_map.get("analysis_kind") != "native_rng_return_id_map"
        or return_identity != identity
        or not isinstance(sources, dict)
        or sources.get("boundary_map_canonical_sha256") != boundary_sha
        or type(sources.get("inventory_canonical_sha256")) is not str
        or _SHA256_RE.fullmatch(sources["inventory_canonical_sha256"]) is None
        or not isinstance(rng_core, dict)
        or rng_core.get("entry_rva") != f"0x{EXPECTED_RNG_CORE_RVA:08x}"
        or rng_core.get("unknown_caller_id") != 0
        or rng_core.get("maximum_caller_id") != MAX_CALLER_ID
        or not isinstance(callers, list)
        or len(callers) != EXPECTED_CALLER_COUNT
        or _sha256(return_map_bytes) != EXPECTED_RETURN_MAP_SHA256
        or _canonical_json(return_map) != return_map_bytes
    ):
        raise ObserverBuildError("RNG return map is not the canonical pinned catalog")

    reviewed: dict[int, dict[str, Any]] = {}
    for edge in boundaries.get("direct_call_edges", []):
        if not isinstance(edge, dict):
            raise ObserverBuildError("boundary direct-call edge is malformed")
        target = edge.get("target")
        if (
            edge.get("kind") == "direct_rel32"
            and isinstance(target, dict)
            and target.get("region") == "rng_core"
            and target.get("type") == "region"
        ):
            reviewed[_parse_rva(edge.get("from_rva"), "edge.from_rva")] = edge

    call_rvas: list[int] = []
    return_rvas: list[int] = []
    for index, caller in enumerate(callers, start=1):
        if not isinstance(caller, dict) or caller.get("caller_id") != index:
            raise ObserverBuildError("RNG caller IDs are not contiguous")
        call_rva = _parse_rva(caller.get("call_rva"), "caller.call_rva")
        return_rva = _parse_rva(caller.get("return_rva"), "caller.return_rva")
        if return_rva != call_rva + 5 or (call_rvas and call_rva <= call_rvas[-1]):
            raise ObserverBuildError("RNG caller RVAs are not sorted five-byte calls")
        call_offset = image.rva_to_offset(call_rva, 5)
        call_bytes = executable[call_offset : call_offset + 5]
        if call_bytes[0] != 0xE8:
            raise ObserverBuildError("RNG caller catalog contains a non-call")
        (relative,) = struct.unpack_from("<i", call_bytes, 1)
        if (return_rva + relative) & 0xFFFFFFFF != EXPECTED_RNG_CORE_RVA:
            raise ObserverBuildError("RNG caller does not target the core")
        section = image.section_for_rva(call_rva)
        if not section.executable or caller.get("section") != section.name:
            raise ObserverBuildError("RNG caller section attribution differs")
        classification = caller.get("classification")
        edge = reviewed.get(call_rva)
        expected_classification = (
            {
                "status": "unclassified_raw_candidate",
                "edge_id": None,
                "source_region": None,
                "meaning": None,
            }
            if edge is None
            else {
                "status": "reviewed_direct_call",
                "edge_id": edge.get("id"),
                "source_region": edge.get("source_region"),
                "meaning": edge.get("meaning"),
            }
        )
        if classification != expected_classification:
            raise ObserverBuildError("RNG caller classification differs")
        call_rvas.append(call_rva)
        return_rvas.append(return_rva)

    scanned: list[int] = []
    for section in image.sections:
        if not section.executable:
            continue
        body = executable[
            section.raw_offset : section.raw_offset + section.raw_size
        ]
        for offset in range(max(0, len(body) - 4)):
            if body[offset] != 0xE8:
                continue
            (relative,) = struct.unpack_from("<i", body, offset + 1)
            call_rva = section.virtual_address + offset
            if (call_rva + 5 + relative) & 0xFFFFFFFF == EXPECTED_RNG_CORE_RVA:
                scanned.append(call_rva)
    if sorted(set(scanned)) != call_rvas or len(scanned) != len(call_rvas):
        raise ObserverBuildError("RNG return map differs from the raw executable scan")

    return {
        "executable": executable,
        "image": image,
        "core_bytes": core_bytes,
        "return_rvas": return_rvas,
        "boundary_map_canonical_sha256": boundary_sha,
        "boundary_map_file_sha256": _sha256(boundary_bytes),
        "return_map_sha256": _sha256(return_map_bytes),
        "inventory_canonical_sha256": sources["inventory_canonical_sha256"],
    }


def _hook_plan(source_sha256: str, identities: dict[str, Any]) -> dict[str, Any]:
    core_bytes: bytes = identities["core_bytes"]
    return {
        "schema_version": 1,
        "kind": "observatory_rng_core_hook_plan",
        "observer_version": OBSERVER_VERSION,
        "identity": {
            "platform": "windows",
            "architecture": EXPECTED_ARCHITECTURE,
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "inventory_sha256": identities["inventory_canonical_sha256"],
            "boundary_map_sha256": identities["boundary_map_canonical_sha256"],
            "rng_return_map_sha256": identities["return_map_sha256"],
            "source_sha256": source_sha256,
        },
        "patch": {
            "region_id": "rng_core",
            "entry_rva": f"0x{EXPECTED_RNG_CORE_RVA:08x}",
            "overwrite_size": 5,
            "expected_bytes_hex": core_bytes[:5].hex(),
            "expected_bytes_sha256": _sha256(core_bytes[:5]),
            "detour_kind": "x86_e9_rel32_to_pinned_module",
            "gateway_kind": "relocated_e8_then_e9_tail_jump",
            "relocated_call_target_rva": f"0x{EXPECTED_RNG_STATE_OWNER_RVA:08x}",
            "continuation_rva": f"0x{EXPECTED_RNG_CORE_RVA + 5:08x}",
            "return_strategy": "bounded_per_thread_return_address_substitution",
        },
        "limits": {
            "record_capacity": 4096,
            "thread_capacity": 32,
            "nesting_capacity": 8,
            "caller_count": EXPECTED_CALLER_COUNT,
            "unknown_caller_id": 0,
        },
        "cold_transaction": {
            "arm_requires_exact_full_file_sha256": True,
            "arm_requires_exact_live_core_bytes": True,
            "other_threads_suspended": True,
            "new_thread_start_serialized_by_loader_lock": True,
            "entry_instruction_pointer_rejected": True,
            "post_core_instruction_pointer_rejected": True,
            "write_size": 5,
            "protection_restored": True,
            "instruction_cache_flushed": True,
            "readback_required": True,
            "failed_arm_rollback_required": True,
            "failed_resume_handles_retained_for_retry": True,
        },
        "hot_contract": {
            "allocation": False,
            "file_io": False,
            "lua_or_game_calls": False,
            "locks": False,
            "clocks": False,
            "addresses_published": False,
        },
    }


def _c_bytes(name: str, data: bytes) -> str:
    rows = []
    for offset in range(0, len(data), 12):
        values = ", ".join(f"0x{value:02x}" for value in data[offset : offset + 12])
        rows.append(f"    {values},")
    return f"static const unsigned char {name}[{len(data)}] = {{\n" + "\n".join(rows) + "\n};\n"


def _generated_include(
    identities: dict[str, Any],
    hook_plan_sha256: str,
    restore_manifest_sha256: str,
) -> bytes:
    digest_bytes = bytes.fromhex(EXPECTED_EXECUTABLE_SHA256)
    core_bytes: bytes = identities["core_bytes"]
    return_rvas: list[int] = identities["return_rvas"]
    return_rows = []
    for offset in range(0, len(return_rvas), 6):
        values = ", ".join(
            f"0x{value:08x}u" for value in return_rvas[offset : offset + 6]
        )
        return_rows.append(f"    {values},")
    text = f"""/* Generated by scripts/build_itb_observatory_rng_core_observer.py. */
#ifndef OBSERVATORY_RNG_CORE_BUILD_INC
#define OBSERVATORY_RNG_CORE_BUILD_INC

#define OBS_BUILD_ID \"{EXPECTED_BUILD_ID}\"
#define OBS_EXECUTABLE_SHA256 \"{EXPECTED_EXECUTABLE_SHA256}\"
#define OBS_EXECUTABLE_SIZE {EXPECTED_EXECUTABLE_SIZE}L
#define OBS_PE_TIMESTAMP 0x{EXPECTED_PE_TIMESTAMP:08x}u
#define OBS_PE_SIZE_OF_IMAGE 0x{EXPECTED_PE_SIZE_OF_IMAGE:08x}u
#define OBS_BOUNDARY_MAP_SHA256 \"{identities['boundary_map_canonical_sha256']}\"
#define OBS_INVENTORY_SHA256 \"{identities['inventory_canonical_sha256']}\"
#define OBS_RNG_RETURN_MAP_SHA256 \"{identities['return_map_sha256']}\"
#define OBS_HOOK_PLAN_SHA256 \"{hook_plan_sha256}\"
#define OBS_RESTORE_MANIFEST_SHA256 \"{restore_manifest_sha256}\"
#define OBS_RNG_CORE_RVA 0x{EXPECTED_RNG_CORE_RVA:08x}u
#define OBS_RNG_CORE_RVA_TEXT \"0x{EXPECTED_RNG_CORE_RVA:08x}\"
#define OBS_RNG_CORE_SIZE {EXPECTED_RNG_CORE_SIZE}u
#define OBS_RNG_CORE_SHA256 \"{EXPECTED_RNG_CORE_SHA256}\"
#define OBS_RNG_STATE_OWNER_RVA 0x{EXPECTED_RNG_STATE_OWNER_RVA:08x}u
#define OBS_RETURN_RVA_COUNT {len(return_rvas)}u

{_c_bytes('OBS_EXECUTABLE_SHA256_BYTES', digest_bytes)}
{_c_bytes('OBS_RNG_CORE_BYTES', core_bytes)}
static const uint32_t OBS_RETURN_RVAS[OBS_RETURN_RVA_COUNT] = {{
{chr(10).join(return_rows)}
}};

#endif
"""
    return text.encode("ascii")


def _attest_source(source: bytes) -> dict[str, str]:
    try:
        text = source.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise ObserverBuildError("observer source must remain ASCII") from exc
    if text.count("__declspec(dllexport)") != 1 or text.count(EXPORT_NAME) != 1:
        raise ObserverBuildError("observer source must expose exactly one Lua opener")
    if "DllMain" in text:
        raise ObserverBuildError("observer source must not define loader-time behavior")
    start = text.find("/* OBS_HOT_PATH_BEGIN")
    end = text.find("/* OBS_HOT_PATH_END */")
    if start < 0 or end <= start:
        raise ObserverBuildError("observer hot-path markers are missing")
    hot = text[start:end]
    banned = (
        "CreateFile",
        "VirtualProtect",
        "VirtualAlloc",
        "HeapAlloc",
        "lua_",
        "luaL_",
        "GetCurrent",
        "QueryPerformance",
        "fopen",
        "malloc",
        "free(",
    )
    found = [name for name in banned if name in hot]
    if found:
        raise ObserverBuildError(f"observer hot path contains cold APIs: {found}")
    entry_contract = re.search(
        r"static __declspec\(naked\) void observer_rng_core_entry\(void\) \{(.+?)\n\}",
        text,
        flags=re.DOTALL,
    )
    post_contract = re.search(
        r"static __declspec\(naked\) void observer_post_core\(void\) \{(.+?)\n\}",
        text,
        flags=re.DOTALL,
    )
    if entry_contract is None or post_contract is None:
        raise ObserverBuildError("observer naked ABI stubs are missing")
    required_entry = (
        "pushfd",
        "pushad",
        "[esp + 36]",
        "call observer_enter",
        "mov dword ptr [esp + 36], eax",
        "popad",
        "popfd",
        "jmp dword ptr [g_gateway]",
    )
    required_post = (
        "pushfd",
        "pushad",
        "[esp + 28]",
        "call observer_exit",
        "mov dword ptr [esp - 4], eax",
        "lock dec dword ptr [g_active_frames]",
        "popad",
        "popfd",
        "push dword ptr [esp - 40]",
        "ret",
    )
    if any(item not in entry_contract.group(1) for item in required_entry) or any(
        item not in post_contract.group(1) for item in required_post
    ):
        raise ObserverBuildError("observer return-substitution ABI contract differs")
    return {
        "hot_source_sha256": _sha256(hot.encode("ascii")),
        "entry_abi_source_sha256": _sha256(entry_contract.group(1).encode("ascii")),
        "post_abi_source_sha256": _sha256(post_contract.group(1).encode("ascii")),
    }


def _vswhere() -> Path:
    candidate = Path(os.environ.get("ProgramFiles(x86)", "")) / (
        "Microsoft Visual Studio/Installer/vswhere.exe"
    )
    if not candidate.is_file():
        raise ObserverBuildError("Visual Studio vswhere.exe is unavailable")
    return candidate


def _msvc_environment() -> tuple[dict[str, str], str]:
    result = subprocess.run(
        [
            str(_vswhere()),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    installation = Path(result.stdout.strip())
    vcvars = installation / "VC" / "Auxiliary" / "Build" / "vcvars32.bat"
    if not vcvars.is_file():
        raise ObserverBuildError("Visual C++ x86 environment is unavailable")
    with tempfile.TemporaryDirectory(prefix="itb_observatory_msvc_env_") as raw:
        environment_script = Path(raw) / "environment.cmd"
        environment_script.write_text(
            f'@call "{vcvars}" >nul\n@set\n',
            encoding="utf-8",
        )
        env_result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(environment_script)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    if env_result.returncode != 0:
        detail = (env_result.stderr or env_result.stdout).strip()
        raise ObserverBuildError(
            "vcvars32.bat failed to configure MSVC"
            + (f": {detail}" if detail else "")
        )
    environment = {key.upper(): value for key, value in os.environ.items()}
    for line in env_result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            environment[key.upper()] = value
    cl = shutil.which("cl.exe", path=environment.get("PATH"))
    if cl is None:
        raise ObserverBuildError("cl.exe was not configured by vcvars32.bat")
    version = subprocess.run(
        [cl], env=environment, capture_output=True, text=True, timeout=15
    )
    banner = (version.stderr or version.stdout).splitlines()
    return environment, (banner[0].strip() if banner else "unknown MSVC")


def _write_create_only(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ObserverBuildError(f"immutable output already exists: {path.name}") from exc


def _normalize_compiler_stdout(value: str, temporary_root: Path) -> str:
    result = value.strip()
    for spelling in {
        str(temporary_root),
        temporary_root.as_posix(),
        str(ROOT),
        ROOT.as_posix(),
    }:
        result = result.replace(spelling, "<source-root>" if Path(spelling) == ROOT else "<temporary-build>")
    return result


def _compile_observer_once(
    environment: dict[str, str],
    include_data: bytes,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="itb_observatory_rng_core_") as raw:
        temp = Path(raw)
        include_path = temp / "observatory_rng_core_build.inc"
        include_path.write_bytes(include_data)
        dll = temp / "itb_observatory_rng_core_observer.dll"
        obj = temp / "observatory_rng_core_observer.obj"
        cl = shutil.which("cl.exe", path=environment.get("PATH"))
        linker = shutil.which("link.exe", path=environment.get("PATH"))
        if cl is None or linker is None:
            raise ObserverBuildError("MSVC compiler or linker disappeared")
        compile_command = [
            cl,
            "/nologo",
            "/c",
            "/TC",
            "/O2",
            "/Oi",
            "/Oy",
            "/W4",
            "/WX",
            "/GS-",
            "/Gy",
            "/Zl",
            f"/I{temp}",
            f"/Fo{obj}",
            str(SOURCE),
        ]
        compile_completed = subprocess.run(
            compile_command,
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        link_command = [
            linker,
            "/NOLOGO",
            "/DLL",
            "/NOENTRY",
            "/NODEFAULTLIB",
            f"/OUT:{dll}",
            "/INCREMENTAL:NO",
            "/Brepro",
            "/OPT:REF",
            "/OPT:ICF",
            str(obj),
            "kernel32.lib",
            "bcrypt.lib",
        ]
        link_completed = subprocess.run(
            link_command,
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        compiler_stdout = _normalize_compiler_stdout(
            "\n".join(
                item
                for item in (compile_completed.stdout, link_completed.stdout)
                if item.strip()
            ),
            temp,
        )
        observer_data = _stable_bytes(dll, "compiled observer")
    observer_image = _parse_pe(observer_data)
    if observer_image.machine != 0x014C:
        raise ObserverBuildError("compiled observer is not x86")
    machine_attestation = _attest_machine_contract(observer_data, observer_image)
    if not machine_attestation["loader_entry_absent"]:
        raise ObserverBuildError("compiled observer has loader-time code")
    exports = _pe_exports(observer_data, observer_image)
    if exports != [EXPORT_NAME]:
        raise ObserverBuildError(f"compiled observer exports differ: {exports}")
    imports = sorted(name.lower() for name in _pe_imports(observer_data, observer_image))
    allowed_imports = {"bcrypt.dll", "kernel32.dll"}
    if not set(imports) <= allowed_imports or "kernel32.dll" not in imports:
        raise ObserverBuildError(f"compiled observer imports differ: {imports}")
    return {
        "module": observer_data,
        "module_sha256": _sha256(observer_data),
        "compiler_stdout": compiler_stdout,
        "machine_attestation": machine_attestation,
        "exports": exports,
        "imports": imports,
    }


def build_observer(args: argparse.Namespace) -> int:
    identities = _validate_inputs(
        args.executable, args.native_boundaries, args.rng_return_map
    )
    source_data = _stable_bytes(SOURCE, "observer source")
    source_attestation = _attest_source(source_data)
    source_sha = _sha256(source_data)
    restore_hashes = {"rng_core": EXPECTED_RNG_CORE_SHA256}
    restore_data = _compact_json(restore_hashes)
    restore_sha = _sha256(restore_data)
    hook_plan = _hook_plan(source_sha, identities)
    hook_plan_data = _canonical_json(hook_plan)
    hook_plan_sha = _sha256(hook_plan_data)
    include_data = _generated_include(identities, hook_plan_sha, restore_sha)

    environment, compiler = _msvc_environment()
    first_build = _compile_observer_once(environment, include_data)
    second_build = _compile_observer_once(environment, include_data)
    for field in (
        "module",
        "module_sha256",
        "compiler_stdout",
        "machine_attestation",
        "exports",
        "imports",
    ):
        if first_build[field] != second_build[field]:
            raise ObserverBuildError(
                f"independent reproducibility builds differ: {field}"
            )
    observer_data = first_build["module"]
    observer_sha = first_build["module_sha256"]
    compiler_stdout = first_build["compiler_stdout"]
    machine_attestation = first_build["machine_attestation"]
    imports = first_build["imports"]

    output_root = Path(os.path.abspath(args.output_root.expanduser()))
    stem = f"itb_observatory_rng_core_observer_{observer_sha}"
    observer_path = output_root / f"{stem}.dll"
    receipt_path = output_root / f"{stem}.dll.receipt.json"
    plan_path = output_root / (
        f"windows_build_{EXPECTED_BUILD_ID}_rng_core_hook_plan_"
        f"{hook_plan_sha[:12]}.json"
    )
    restore_path = output_root / (
        f"windows_build_{EXPECTED_BUILD_ID}_rng_core_restore_hashes_"
        f"{restore_sha[:12]}.json"
    )
    _write_create_only(observer_path, observer_data)
    _write_create_only(plan_path, hook_plan_data)
    _write_create_only(restore_path, restore_data)
    receipt = {
        "schema_version": 1,
        "kind": "observatory_rng_core_observer_build",
        "observer_version": OBSERVER_VERSION,
        "module_filename": observer_path.name,
        "module_sha256": observer_sha,
        "module_size": len(observer_data),
        "architecture": EXPECTED_ARCHITECTURE,
        "export_name": EXPORT_NAME,
        "imports": imports,
        "source_path": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": source_sha,
        "generated_include_sha256": _sha256(include_data),
        "source_attestation": source_attestation,
        "machine_attestation": machine_attestation,
        "compiler": compiler,
        "compiler_stdout": compiler_stdout,
        "reproducibility": {
            "independent_build_count": 2,
            "module_bytes_identical": True,
            "attestations_identical": True,
        },
        "compile_flags": [
            "/c",
            "/TC",
            "/O2",
            "/Oi",
            "/Oy",
            "/W4",
            "/WX",
            "/GS-",
            "/Gy",
            "/Zl",
            "/DLL",
            "/NOENTRY",
            "/NODEFAULTLIB",
            "/INCREMENTAL:NO",
            "/Brepro",
            "/OPT:REF",
            "/OPT:ICF",
        ],
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        "executable_size": EXPECTED_EXECUTABLE_SIZE,
        "build_id": EXPECTED_BUILD_ID,
        "boundary_map_canonical_sha256": identities[
            "boundary_map_canonical_sha256"
        ],
        "boundary_map_file_sha256": identities["boundary_map_file_sha256"],
        "rng_return_map_sha256": identities["return_map_sha256"],
        "inventory_canonical_sha256": identities[
            "inventory_canonical_sha256"
        ],
        "rng_core_rva": f"0x{EXPECTED_RNG_CORE_RVA:08x}",
        "rng_core_region_sha256": EXPECTED_RNG_CORE_SHA256,
        "caller_count": len(identities["return_rvas"]),
        "hook_plan_filename": plan_path.name,
        "hook_plan_sha256": hook_plan_sha,
        "restore_hashes_filename": restore_path.name,
        "restore_manifest_sha256": restore_sha,
        "loaded_or_armed": False,
    }
    _write_create_only(receipt_path, _canonical_json(receipt))
    if _stable_bytes(observer_path, "published observer") != observer_data:
        raise ObserverBuildError("published observer failed byte verification")
    print(
        f"observer={observer_path} sha256={observer_sha} "
        f"size={len(observer_data)} receipt={receipt_path}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return build_observer(args)
    except (ObserverBuildError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
