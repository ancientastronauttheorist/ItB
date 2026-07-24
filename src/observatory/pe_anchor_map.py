"""Build-keyed, read-only named-anchor maps for Windows PE executables.

The mapper records string locations and conservative literal-address reference
candidates. It does not disassemble functions, recover proprietary source, or
claim that a candidate reference is a Lua registration site.
"""

from __future__ import annotations

import hashlib
import json
import struct
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
MAX_EXECUTABLE_BYTES = 512 * 1024 * 1024
DEFAULT_ANCHORS = (
    "random_int",
    "random_bool",
    "aiSeed",
    "GetTargetScore",
    "ScorePositioning",
)
_PE32_MAGIC = 0x10B
_PE32_PLUS_MAGIC = 0x20B
_IMAGE_SCN_MEM_EXECUTE = 0x20000000
_IMAGE_DIRECTORY_ENTRY_IMPORT = 1
_IMAGE_DEBUG_TYPE_CODEVIEW = 2


class PEAnchorError(RuntimeError):
    """Raised when PE evidence is malformed or mismatched."""


@dataclass(frozen=True)
class PESection:
    name: str
    virtual_size: int
    virtual_address: int
    raw_size: int
    raw_offset: int
    characteristics: int

    @property
    def executable(self) -> bool:
        return bool(self.characteristics & _IMAGE_SCN_MEM_EXECUTE)


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}x}"


def _unpack(fmt: str, data: bytes, offset: int, label: str) -> tuple[Any, ...]:
    size = struct.calcsize(fmt)
    if offset < 0 or offset + size > len(data):
        raise PEAnchorError(f"truncated PE while reading {label}")
    return struct.unpack_from(fmt, data, offset)


def _architecture(machine: int) -> str:
    return {
        0x014C: "x86",
        0x8664: "x86_64",
        0x01C0: "arm",
        0x01C4: "armv7",
        0xAA64: "arm64",
    }.get(machine, f"machine_0x{machine:04x}")


class PEImage:
    """Minimal dependency-free PE layout parser."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        if len(data) < 64 or data[:2] != b"MZ":
            raise PEAnchorError("input is not a DOS/PE image")
        (pe_offset,) = _unpack("<I", data, 0x3C, "PE offset")
        if data[pe_offset : pe_offset + 4] != b"PE\0\0":
            raise PEAnchorError("missing PE signature")
        coff = pe_offset + 4
        (
            self.machine,
            section_count,
            self.timestamp,
            _symbol_table,
            _symbol_count,
            optional_size,
            _characteristics,
        ) = _unpack("<HHIIIHH", data, coff, "COFF header")
        if section_count < 1 or section_count > 96:
            raise PEAnchorError(f"implausible PE section count: {section_count}")
        optional = coff + 20
        if optional + optional_size > len(data):
            raise PEAnchorError("truncated PE optional header")
        (magic,) = _unpack("<H", data, optional, "optional-header magic")
        if magic == _PE32_MAGIC:
            if optional_size < 96:
                raise PEAnchorError("PE32 optional header is undersized")
            self.bits = 32
            (self.image_base,) = _unpack(
                "<I", data, optional + 28, "PE32 image base"
            )
            directory_count_offset = optional + 92
            directory_offset = optional + 96
        elif magic == _PE32_PLUS_MAGIC:
            if optional_size < 112:
                raise PEAnchorError("PE32+ optional header is undersized")
            self.bits = 64
            (self.image_base,) = _unpack(
                "<Q", data, optional + 24, "PE32+ image base"
            )
            directory_count_offset = optional + 108
            directory_offset = optional + 112
        else:
            raise PEAnchorError(f"unsupported PE optional-header magic: {magic:#x}")
        known_32_bit_machines = {0x014C, 0x01C0, 0x01C4}
        known_64_bit_machines = {0x8664, 0xAA64}
        if (
            self.bits == 32
            and self.machine in known_64_bit_machines
        ) or (
            self.bits == 64
            and self.machine in known_32_bit_machines
        ):
            raise PEAnchorError(
                "PE machine and optional-header bitness are incompatible"
            )
        (self.entrypoint_rva,) = _unpack(
            "<I", data, optional + 16, "entrypoint RVA"
        )
        (self.size_of_headers,) = _unpack(
            "<I", data, optional + 60, "size of headers"
        )
        (directory_count,) = _unpack(
            "<I", data, directory_count_offset, "data-directory count"
        )
        available_directories = max(
            0, (optional + optional_size - directory_offset) // 8
        )
        if directory_count > 16:
            raise PEAnchorError(
                f"unsupported PE data-directory count: {directory_count}"
            )
        if directory_count > available_directories:
            raise PEAnchorError(
                "PE data-directory count exceeds the optional header"
            )
        self.data_directories: list[tuple[int, int]] = []
        for index in range(directory_count):
            self.data_directories.append(
                _unpack(
                    "<II",
                    data,
                    directory_offset + index * 8,
                    f"data directory {index}",
                )
            )

        section_table = optional + optional_size
        self.sections: list[PESection] = []
        names: set[str] = set()
        for index in range(section_count):
            offset = section_table + index * 40
            raw_name = data[offset : offset + 8]
            if len(raw_name) != 8:
                raise PEAnchorError("truncated PE section table")
            name = raw_name.split(b"\0", 1)[0].decode("ascii", errors="replace")
            (
                virtual_size,
                virtual_address,
                raw_size,
                raw_offset,
            ) = _unpack("<IIII", data, offset + 8, f"section {index} layout")
            (characteristics,) = _unpack(
                "<I", data, offset + 36, f"section {index} characteristics"
            )
            if name in names:
                raise PEAnchorError(f"duplicate PE section name: {name!r}")
            names.add(name)
            if raw_size and raw_offset + raw_size > len(data):
                raise PEAnchorError(f"section {name!r} extends beyond the file")
            self.sections.append(
                PESection(
                    name=name,
                    virtual_size=virtual_size,
                    virtual_address=virtual_address,
                    raw_size=raw_size,
                    raw_offset=raw_offset,
                    characteristics=characteristics,
                )
            )
        max_virtual_address = (1 << self.bits) - 1
        if self.image_base > max_virtual_address:
            raise PEAnchorError("PE image base exceeds its address width")
        if self.image_base + self.entrypoint_rva > max_virtual_address:
            raise PEAnchorError("PE entrypoint exceeds its address width")
        for section in self.sections:
            extent = max(section.virtual_size, section.raw_size)
            if (
                extent
                and self.image_base
                + section.virtual_address
                + extent
                - 1
                > max_virtual_address
            ):
                raise PEAnchorError(
                    f"section {section.name!r} exceeds PE address width"
                )

    @property
    def architecture(self) -> str:
        return _architecture(self.machine)

    def section_for_offset(self, offset: int) -> PESection | None:
        for section in self.sections:
            if section.raw_offset <= offset < section.raw_offset + section.raw_size:
                return section
        return None

    def file_offset_to_rva(self, offset: int) -> int | None:
        section = self.section_for_offset(offset)
        if section is not None:
            return section.virtual_address + offset - section.raw_offset
        if 0 <= offset < min(self.size_of_headers, len(self.data)):
            return offset
        return None

    def rva_to_file_offset(self, rva: int) -> int | None:
        for section in self.sections:
            extent = max(section.virtual_size, section.raw_size)
            if section.virtual_address <= rva < section.virtual_address + extent:
                delta = rva - section.virtual_address
                if delta < section.raw_size:
                    return section.raw_offset + delta
                return None
        if 0 <= rva < min(self.size_of_headers, len(self.data)):
            return rva
        return None

    def rva_span_to_file_offset(self, rva: int, size: int) -> int | None:
        """Map a span only when every byte is contiguous file-backed image data."""
        if type(rva) is not int or type(size) is not int or rva < 0 or size < 0:
            return None
        if rva < min(self.size_of_headers, len(self.data)):
            if rva + size <= min(self.size_of_headers, len(self.data)):
                return rva
            return None
        for section in self.sections:
            if section.virtual_address <= rva:
                delta = rva - section.virtual_address
                if delta <= section.raw_size and delta + size <= section.raw_size:
                    return section.raw_offset + delta
        return None

    def rva_span_is_mapped(self, rva: int, size: int) -> bool:
        """Return whether a span belongs to one contiguous mapped image region."""
        if type(rva) is not int or type(size) is not int or rva < 0 or size < 0:
            return False
        if rva < self.size_of_headers:
            return rva + size <= self.size_of_headers
        for section in self.sections:
            extent = max(section.virtual_size, section.raw_size)
            if section.virtual_address <= rva:
                delta = rva - section.virtual_address
                if delta <= extent and delta + size <= extent:
                    return True
        return False

    def codeview_records(self) -> list[dict[str, Any]]:
        """Return deterministic CodeView fingerprints from the debug directory."""
        if len(self.data_directories) <= 6:
            return []
        debug_rva, debug_size = self.data_directories[6]
        if not debug_rva or debug_size < 28:
            return []
        debug_offset = self.rva_to_file_offset(debug_rva)
        if debug_offset is None or debug_offset + debug_size > len(self.data):
            return []
        records = []
        for index in range(debug_size // 28):
            offset = debug_offset + index * 28
            (
                _characteristics,
                timestamp,
                major,
                minor,
                record_type,
                data_size,
                _data_rva,
                data_offset,
            ) = _unpack("<IIHHIIII", self.data, offset, "debug record")
            if (
                record_type != _IMAGE_DEBUG_TYPE_CODEVIEW
                or data_size < 24
                or data_offset + data_size > len(self.data)
            ):
                continue
            record = self.data[data_offset : data_offset + data_size]
            if record[:4] != b"RSDS":
                continue
            guid = record[4:20]
            (age,) = _unpack("<I", record, 20, "CodeView age")
            path_bytes = record[24:].split(b"\0", 1)[0]
            records.append(
                {
                    "evidence_class": "fact",
                    "format": "RSDS",
                    "guid": str(uuid.UUID(bytes_le=guid)),
                    "raw_guid_bytes_hex": guid.hex(),
                    "age": age,
                    "pdb_path": path_bytes.decode(
                        "utf-8", errors="backslashreplace"
                    ),
                    "debug_timestamp": timestamp,
                    "debug_version": f"{major}.{minor}",
                }
            )
        return records

    def _read_rva_c_string(
        self,
        rva: int,
        label: str,
        *,
        maximum_bytes: int = 4096,
    ) -> str:
        offset = self.rva_span_to_file_offset(rva, 1)
        if offset is None:
            raise PEAnchorError(f"{label} RVA is not file-backed")
        if rva < min(self.size_of_headers, len(self.data)):
            available = min(self.size_of_headers, len(self.data)) - rva
        else:
            available = 0
            for section in self.sections:
                if section.virtual_address <= rva:
                    delta = rva - section.virtual_address
                    if delta < section.raw_size:
                        available = section.raw_size - delta
                        break
        end_limit = offset + min(maximum_bytes, available)
        terminator = self.data.find(b"\0", offset, end_limit)
        if terminator < 0:
            raise PEAnchorError(f"{label} is not null-terminated")
        try:
            return self.data[offset:terminator].decode("ascii")
        except UnicodeDecodeError as exc:
            raise PEAnchorError(f"{label} is not ASCII") from exc

    def imports(self) -> list[dict[str, Any]]:
        """Parse named PE imports with their exact IAT slot RVAs."""
        if len(self.data_directories) <= _IMAGE_DIRECTORY_ENTRY_IMPORT:
            return []
        import_rva, import_size = self.data_directories[
            _IMAGE_DIRECTORY_ENTRY_IMPORT
        ]
        if not import_rva or not import_size:
            return []
        import_offset = self.rva_span_to_file_offset(import_rva, import_size)
        if import_offset is None:
            raise PEAnchorError(
                "import directory is not contiguous file-backed data"
            )
        if import_size < 20:
            raise PEAnchorError("import directory is undersized")
        pointer_format = "<I" if self.bits == 32 else "<Q"
        pointer_size = struct.calcsize(pointer_format)
        ordinal_mask = 1 << (self.bits - 1)
        address_mask = ordinal_mask - 1
        records: list[dict[str, Any]] = []
        terminated = False
        for descriptor_index in range(import_size // 20):
            descriptor_offset = import_offset + descriptor_index * 20
            (
                original_thunk_rva,
                timestamp,
                forwarder_chain,
                name_rva,
                first_thunk_rva,
            ) = _unpack(
                "<IIIII",
                self.data,
                descriptor_offset,
                f"import descriptor {descriptor_index}",
            )
            if not any(
                (
                    original_thunk_rva,
                    timestamp,
                    forwarder_chain,
                    name_rva,
                    first_thunk_rva,
                )
            ):
                terminated = True
                break
            if not name_rva or not first_thunk_rva:
                raise PEAnchorError(
                    f"import descriptor {descriptor_index} is incomplete"
                )
            library = self._read_rva_c_string(
                name_rva, f"import library {descriptor_index}"
            )
            lookup_rva = original_thunk_rva or first_thunk_rva
            thunk_terminated = False
            for thunk_index in range(65536):
                entry_rva = lookup_rva + thunk_index * pointer_size
                entry_offset = self.rva_span_to_file_offset(
                    entry_rva, pointer_size
                )
                if entry_offset is None:
                    raise PEAnchorError(
                        f"import thunk {descriptor_index}:{thunk_index} "
                        "is not file-backed"
                    )
                (entry,) = _unpack(
                    pointer_format,
                    self.data,
                    entry_offset,
                    f"import thunk {descriptor_index}:{thunk_index}",
                )
                if entry == 0:
                    thunk_terminated = True
                    break
                iat_rva = first_thunk_rva + thunk_index * pointer_size
                if self.image_base + iat_rva > (1 << self.bits) - 1:
                    raise PEAnchorError("import IAT slot exceeds address width")
                if not self.rva_span_is_mapped(iat_rva, pointer_size):
                    raise PEAnchorError("import IAT slot is outside the image")
                if self.rva_span_to_file_offset(iat_rva, pointer_size) is None:
                    raise PEAnchorError(
                        "import IAT slot is not file-backed"
                    )
                if entry & ordinal_mask:
                    records.append(
                        {
                            "evidence_class": "fact",
                            "library": library,
                            "name": None,
                            "ordinal": entry & 0xFFFF,
                            "hint": None,
                            "iat_rva": _hex(iat_rva),
                        }
                    )
                    continue
                name_entry_rva = entry & address_mask
                name_entry_offset = self.rva_span_to_file_offset(
                    name_entry_rva, 2
                )
                if name_entry_offset is None:
                    raise PEAnchorError(
                        "import-by-name entry is not file-backed"
                    )
                (hint,) = _unpack(
                    "<H",
                    self.data,
                    name_entry_offset,
                    "import hint",
                )
                name = self._read_rva_c_string(
                    name_entry_rva + 2,
                    f"import name {descriptor_index}:{thunk_index}",
                )
                records.append(
                    {
                        "evidence_class": "fact",
                        "library": library,
                        "name": name,
                        "ordinal": None,
                        "hint": hint,
                        "iat_rva": _hex(iat_rva),
                    }
                )
            if not thunk_terminated:
                raise PEAnchorError("import thunk table lacks a terminator")
        if not terminated:
            raise PEAnchorError("import descriptor table lacks a terminator")
        return records


def _find_all(data: bytes, needle: bytes, start: int, end: int) -> list[int]:
    results: list[int] = []
    cursor = start
    while cursor < end:
        found = data.find(needle, cursor, end)
        if found < 0:
            break
        results.append(found)
        cursor = found + 1
    return results


def _reference_kind(
    data: bytes,
    operand_offset: int,
    architecture: str,
) -> tuple[str, int]:
    if architecture != "x86":
        return "literal_address_candidate", operand_offset
    if operand_offset >= 1:
        opcode = data[operand_offset - 1]
        if opcode == 0x68:
            return "push_imm_address_candidate", operand_offset - 1
        if 0xB8 <= opcode <= 0xBF:
            return "mov_reg_imm_address_candidate", operand_offset - 1
    if (
        operand_offset >= 2
        and data[operand_offset - 2] == 0x8D
        and data[operand_offset - 1] & 0xC7 == 0x05
    ):
        return "lea_absolute_address_candidate", operand_offset - 2
    # Common x86 ``mov r/m32, imm32`` layouts. These are conservative byte
    # classifications, not a substitute for decoding from a proven boundary.
    for instruction_size_before_operand in (2, 3, 6):
        start = operand_offset - instruction_size_before_operand
        if start >= 0 and data[start] == 0xC7:
            return "mov_mem_imm_address_candidate", start
    return "literal_address_candidate", operand_offset


def _inventory_identity(
    inventory: Mapping[str, Any] | None,
    *,
    sha256: str,
    size: int,
    architecture: str,
) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "platform": "windows",
        "format": "pe",
        "architecture": architecture,
        "executable_sha256": sha256,
        "executable_size": size,
        "build_id": None,
        "depot_manifests": [],
        "appmanifest_sha256": None,
        "scripts_revision_sha256": None,
        "maps_revision_sha256": None,
        "native_libraries": [],
    }
    if inventory is None:
        return identity
    if not isinstance(inventory, Mapping):
        raise PEAnchorError("inventory must be an object")
    label = inventory.get("label")
    if label is not None and type(label) is not str:
        raise PEAnchorError("inventory.label must be text or null")
    executable = inventory.get("executable")
    if inventory.get("platform") != "windows" or not isinstance(
        executable, Mapping
    ):
        raise PEAnchorError("inventory is not a Windows executable inventory")
    expected = (
        executable.get("sha256"),
        executable.get("size"),
        executable.get("format"),
        executable.get("architecture"),
    )
    actual = (sha256, size, "pe", architecture)
    if expected != actual:
        raise PEAnchorError(
            "executable does not match the supplied inventory identity"
        )
    steam = inventory.get("steam")
    content = inventory.get("content")
    native_libraries = inventory.get("native_libraries")
    if not isinstance(steam, Mapping):
        raise PEAnchorError("inventory.steam must be an object")
    if not isinstance(content, Mapping):
        raise PEAnchorError("inventory.content must be an object")
    if not isinstance(native_libraries, list):
        raise PEAnchorError("inventory.native_libraries must be an array")
    evidence = steam.get("evidence")
    depots = steam.get("installed_depots")
    scripts = content.get("scripts")
    maps = content.get("maps")
    if not isinstance(evidence, Mapping):
        raise PEAnchorError("inventory.steam.evidence must be an object")
    if not isinstance(depots, list):
        raise PEAnchorError("inventory.steam.installed_depots must be an array")
    if not isinstance(scripts, Mapping) or not isinstance(maps, Mapping):
        raise PEAnchorError(
            "inventory content scripts/maps must be objects"
        )
    build_id = steam.get("build_id")
    appmanifest_sha256 = evidence.get("sha256")
    scripts_revision = scripts.get("revision_sha256")
    maps_revision = maps.get("revision_sha256")
    if type(build_id) is not str or not build_id.isdigit():
        raise PEAnchorError("inventory.steam.build_id must be numeric text")
    for value, label in (
        (appmanifest_sha256, "inventory appmanifest SHA-256"),
        (scripts_revision, "inventory scripts revision"),
        (maps_revision, "inventory maps revision"),
    ):
        if (
            type(value) is not str
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise PEAnchorError(f"{label} must be lowercase SHA-256")
    normalized_depots = []
    for index, item in enumerate(depots):
        if not isinstance(item, Mapping):
            raise PEAnchorError(
                f"inventory depot {index} must be an object"
            )
        depot_id = item.get("depot_id")
        manifest = item.get("manifest")
        if (
            type(depot_id) not in (str, int)
            or type(manifest) not in (str, int)
            or not str(depot_id).isdigit()
            or not str(manifest).isdigit()
        ):
            raise PEAnchorError(
                f"inventory depot {index} has invalid identity"
            )
        normalized_depots.append(
            {"depot_id": str(depot_id), "manifest": str(manifest)}
        )
    normalized_libraries = []
    for index, item in enumerate(native_libraries):
        if not isinstance(item, Mapping):
            raise PEAnchorError(
                f"inventory native library {index} must be an object"
            )
        library = {
            key: item.get(key)
            for key in (
                "path",
                "size",
                "sha256",
                "format",
                "architecture",
            )
        }
        if (
            type(library["path"]) is not str
            or not library["path"]
            or type(library["size"]) is not int
            or library["size"] < 0
            or type(library["format"]) is not str
            or not library["format"]
            or type(library["architecture"]) is not str
            or not library["architecture"]
            or type(library["sha256"]) is not str
            or len(library["sha256"]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in library["sha256"]
            )
        ):
            raise PEAnchorError(
                f"inventory native library {index} is malformed"
            )
        normalized_libraries.append(library)
    identity.update(
        {
            "build_id": build_id,
            "depot_manifests": sorted(
                normalized_depots,
                key=lambda item: (item["depot_id"], item["manifest"]),
            ),
            "appmanifest_sha256": appmanifest_sha256,
            "scripts_revision_sha256": scripts_revision,
            "maps_revision_sha256": maps_revision,
            "native_libraries": sorted(
                normalized_libraries,
                key=lambda item: str(item["path"]),
            ),
        }
    )
    return identity


def build_pe_anchor_map(
    executable: Path,
    *,
    anchors: Sequence[str] = DEFAULT_ANCHORS,
    inventory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Map named ASCII anchors and conservative code-reference candidates."""
    if executable.is_symlink() or not executable.is_file():
        raise PEAnchorError(f"executable is not a regular non-symlink file: {executable}")
    before = executable.stat()
    if before.st_size > MAX_EXECUTABLE_BYTES:
        raise PEAnchorError("executable exceeds analysis size limit")
    data = executable.read_bytes()
    after = executable.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(data) != before.st_size
    ):
        raise PEAnchorError("executable changed during analysis")
    image = PEImage(data)
    sha256 = hashlib.sha256(data).hexdigest()
    identity = _inventory_identity(
        inventory,
        sha256=sha256,
        size=len(data),
        architecture=image.architecture,
    )
    supplied_anchors = tuple(anchors)
    if (
        not supplied_anchors
        or any(
            type(anchor) is not str
            or not anchor
            or "\0" in anchor
            or not anchor.isascii()
            for anchor in supplied_anchors
        )
        or len(set(supplied_anchors)) != len(supplied_anchors)
    ):
        raise PEAnchorError("anchors must be unique non-empty ASCII strings")
    normalized_anchors = tuple(sorted(supplied_anchors))

    anchor_records: list[dict[str, Any]] = []
    pointer_format = "<I" if image.bits == 32 else "<Q"
    for name in normalized_anchors:
        needle = name.encode("ascii")
        occurrences: list[dict[str, Any]] = []
        reference_candidates: list[dict[str, Any]] = []
        for file_offset in _find_all(data, needle, 0, len(data)):
            rva = image.file_offset_to_rva(file_offset)
            section = image.section_for_offset(file_offset)
            occurrence: dict[str, Any] = {
                "evidence_class": "fact",
                "file_offset": _hex(file_offset),
                "rva": _hex(rva) if rva is not None else None,
                "virtual_address": (
                    _hex(image.image_base + rva, 16 if image.bits == 64 else 8)
                    if rva is not None
                    else None
                ),
                "section": section.name if section is not None else None,
                "null_terminated": (
                    file_offset + len(needle) < len(data)
                    and data[file_offset + len(needle)] == 0
                ),
            }
            occurrences.append(occurrence)
            if rva is None:
                continue
            address = image.image_base + rva
            address_bytes = struct.pack(pointer_format, address)
            for code_section in image.sections:
                if not code_section.executable or not code_section.raw_size:
                    continue
                start = code_section.raw_offset
                end = start + code_section.raw_size
                for operand_offset in _find_all(
                    data, address_bytes, start, end
                ):
                    kind, instruction_offset = _reference_kind(
                        data, operand_offset, image.architecture
                    )
                    instruction_rva = image.file_offset_to_rva(
                        instruction_offset
                    )
                    operand_rva = image.file_offset_to_rva(operand_offset)
                    reference_candidates.append(
                        {
                            "evidence_class": "inference",
                            "candidate_kind": kind,
                            "section": code_section.name,
                            "instruction_rva": (
                                _hex(instruction_rva)
                                if instruction_rva is not None
                                else None
                            ),
                            "operand_rva": (
                                _hex(operand_rva)
                                if operand_rva is not None
                                else None
                            ),
                            "target_string_rva": _hex(rva),
                        }
                    )
        anchor_records.append(
            {
                "name": name,
                "string_occurrences": occurrences,
                "address_reference_candidates": sorted(
                    reference_candidates,
                    key=lambda item: (
                        item["instruction_rva"] or "",
                        item["target_string_rva"],
                        item["candidate_kind"],
                    ),
                ),
                "status": (
                    "string_and_reference_candidates"
                    if reference_candidates
                    else "string_only"
                    if occurrences
                    else "not_found"
                ),
            }
        )

    imports = image.imports()
    lua_api_imports = sorted(
        [
            item
            for item in imports
            if (
                item["name"] is not None
                and (
                    str(item["library"]).casefold().startswith("lua")
                    or str(item["name"]).startswith("lua")
                )
            )
        ],
        key=lambda item: (
            str(item["library"]).casefold(),
            str(item["name"]),
            item["iat_rva"],
        ),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": "pe_named_anchor_map",
        "identity": identity,
        "pe": {
            "bits": image.bits,
            "image_base": _hex(
                image.image_base, 16 if image.bits == 64 else 8
            ),
            "entrypoint_rva": _hex(image.entrypoint_rva),
            "coff_timestamp": image.timestamp,
            "sections": [
                {
                    "name": section.name,
                    "rva": _hex(section.virtual_address),
                    "virtual_size": section.virtual_size,
                    "raw_size": section.raw_size,
                    "executable": section.executable,
                }
                for section in image.sections
            ],
            "codeview": image.codeview_records(),
            "lua_api_imports": lua_api_imports,
        },
        "method": {
            "string_occurrences": "fact: exact ASCII bytes in the sampled PE",
            "address_reference_candidates": (
                "inference: pointer-sized target addresses found in executable "
                "sections; candidates are not decoded or proven call sites"
            ),
            "not_claimed": [
                "Lua registration ownership",
                "function boundaries or behavior",
                "RNG algorithm or state",
                "cross-build or cross-platform offset stability",
            ],
        },
        "anchors": anchor_records,
        "summary": {
            "requested_anchors": len(anchor_records),
            "anchors_found": sum(
                bool(item["string_occurrences"]) for item in anchor_records
            ),
            "string_occurrences": sum(
                len(item["string_occurrences"]) for item in anchor_records
            ),
            "address_reference_candidates": sum(
                len(item["address_reference_candidates"])
                for item in anchor_records
            ),
            "lua_api_imports": len(lua_api_imports),
        },
    }


def encode_anchor_map(value: Mapping[str, Any]) -> str:
    """Return deterministic UTF-8 JSON without an absolute input path."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
