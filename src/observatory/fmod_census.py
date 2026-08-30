"""Build-keyed, payload-free census of Into the Breach's FMOD interface."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import struct
from collections import Counter
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from src.observatory.content_inventory import InventoryError, create_inventory
from src.observatory.pe_anchor_map import PEAnchorError, PEImage, _inventory_identity


SCHEMA_VERSION = 1
ANALYSIS_KIND = "itb_fmod_bank_interface_census"
VERIFICATION_KIND = "itb_fmod_bank_interface_census_verification"
BANK_PATHS = (
    "resources/ambience.bank",
    "resources/Master Bank.bank",
    "resources/Master Bank.strings.bank",
    "resources/music.bank",
    "resources/sfx.bank",
)
FMOD_LIBRARY_PATHS = ("fmod.dll", "fmodstudio.dll")
MAX_BANK_BYTES = 512 * 1024 * 1024
MAX_AGGREGATE_BANK_BYTES = 1024 * 1024 * 1024
MAX_RIFF_NODES = 100_000
MAX_RIFF_DEPTH = 64
MAX_RESOURCE_DIRECTORY_ENTRIES = 10_000
MAX_PE_BYTES = 512 * 1024 * 1024
MAX_EXPORT_NAMES = 100_000
MAX_EXPORT_NAME_BYTES = 512
MAX_VERSION_RESOURCE_BYTES = 1024 * 1024
MAX_VERSION_BLOCK_DEPTH = 16
MAX_VERSION_BLOCKS = 1024
_CHUNK_BYTES = 1024 * 1024
_STABLE_STAT_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_FILE_VERSION_RE = re.compile(
    r"(?P<version>[0-9]{1,10}(?:\.[0-9]{1,10}){2}) "
    r"\(build (?P<build>[0-9]{1,10})\)\Z"
)
_PRODUCT_VERSION_RE = re.compile(
    r"[0-9]{1,10}(?:\.[0-9]{1,10}){2}\Z"
)
_VERSION_STRING_TABLE_RE = re.compile(r"[0-9A-Fa-f]{8}\Z")
_ABSOLUTE_WINDOWS_PATH_RE = re.compile(r"(?:^|\s)[A-Za-z]:[\\/]")
_FORBIDDEN_PUBLICATION_MARKERS = ("event:/", "bus:/", "vca:/")
_IMAGE_DIRECTORY_ENTRY_EXPORT = 0
_IMAGE_DIRECTORY_ENTRY_RESOURCE = 2
_RT_VERSION = 16
_VS_FIXEDFILEINFO_SIGNATURE = 0xFEEF04BD


class FmodCensusError(RuntimeError):
    """Raised when FMOD inputs or normalized evidence are untrustworthy."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FmodCensusError(f"{label} must be an object")
    return value


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
                raise FmodCensusError(f"{label} contains a non-text key")
            _validate_json_tree(item, f"{label}.{key}")
        return
    raise FmodCensusError(f"{label} contains a non-JSON or floating-point value")


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
        raise FmodCensusError(f"value cannot be canonically encoded: {exc}") from exc
    return (rendered + "\n").encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _same_stat(left: os.stat_result, right: os.stat_result, label: str) -> None:
    if any(
        getattr(left, field) != getattr(right, field)
        for field in _STABLE_STAT_FIELDS
    ):
        raise FmodCensusError(f"{label} changed during analysis")


def _is_reparse(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & marker)


def _require_regular_path(path: Path, root: Path, label: str) -> os.stat_result:
    try:
        link_info = path.lstat()
        resolved = path.resolve(strict=True)
        path_info = path.stat()
    except OSError as exc:
        raise FmodCensusError(f"cannot inspect {label}") from exc
    if (
        stat.S_ISLNK(link_info.st_mode)
        or _is_reparse(link_info)
        or not stat.S_ISREG(path_info.st_mode)
        or not resolved.is_relative_to(root)
    ):
        raise FmodCensusError(f"{label} is not a contained regular file")
    return path_info


def _require_directory(path: Path, root: Path, label: str) -> os.stat_result:
    try:
        link_info = path.lstat()
        resolved = path.resolve(strict=True)
        path_info = path.stat()
    except OSError as exc:
        raise FmodCensusError(f"cannot inspect {label}") from exc
    if (
        stat.S_ISLNK(link_info.st_mode)
        or _is_reparse(link_info)
        or not stat.S_ISDIR(path_info.st_mode)
        or not resolved.is_relative_to(root)
    ):
        raise FmodCensusError(f"{label} is not a contained regular directory")
    return path_info


def _build_identity(inventory: Mapping[str, Any]) -> dict[str, Any]:
    executable = _mapping(inventory.get("executable"), "inventory.executable")
    try:
        return _inventory_identity(
            inventory,
            sha256=executable["sha256"],
            size=executable["size"],
            architecture=executable["architecture"],
        )
    except (KeyError, PEAnchorError) as exc:
        raise FmodCensusError(f"invalid inventory identity: {exc}") from exc


def _normalized_inventory_path(value: Any, label: str) -> PurePosixPath:
    if type(value) is not str or not value or "\\" in value:
        raise FmodCensusError(f"{label} must be a normalized relative path")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != value
    ):
        raise FmodCensusError(f"{label} must be a normalized relative path")
    return relative


def _attest_installation(
    install_root: Path,
    inventory: Mapping[str, Any],
) -> tuple[Path, Path, dict[str, Any], Mapping[str, Any]]:
    if not isinstance(inventory, Mapping):
        raise FmodCensusError("inventory must be an object")
    _validate_json_tree(inventory, "inventory")
    platform_name = inventory.get("platform")
    label = inventory.get("label")
    if type(platform_name) is not str or not platform_name:
        raise FmodCensusError("inventory.platform must be text")
    if label is not None and type(label) is not str:
        raise FmodCensusError("inventory.label must be text or null")
    try:
        live_inventory = create_inventory(
            install_root,
            platform_name=platform_name,
            label=label,
        )
    except (InventoryError, OSError, UnicodeError) as exc:
        raise FmodCensusError(
            f"could not rebuild the installation inventory: {exc}"
        ) from exc
    if _canonical_bytes(live_inventory) != _canonical_bytes(inventory):
        raise FmodCensusError(
            "installation does not match the supplied sealed inventory"
        )

    root = install_root.expanduser().resolve()
    content_relative = _normalized_inventory_path(
        live_inventory.get("content_root"), "inventory.content_root"
    )
    content_root = root.joinpath(*content_relative.parts)
    if not content_root.resolve().is_relative_to(root):
        raise FmodCensusError("inventory content root escapes the installation")
    return root, content_root, _build_identity(live_inventory), live_inventory


def _read_stable_binary(
    path: Path,
    root: Path,
    label: str,
    *,
    maximum_bytes: int,
) -> tuple[bytes, dict[str, Any]]:
    path_before = _require_regular_path(path, root, label)
    if path_before.st_size > maximum_bytes:
        raise FmodCensusError(f"{label} exceeds the analysis size limit")
    try:
        with path.open("rb") as stream:
            handle_before = os.fstat(stream.fileno())
            _same_stat(path_before, handle_before, label)
            data = stream.read(handle_before.st_size + 1)
            if len(data) != handle_before.st_size:
                raise FmodCensusError(f"{label} size changed while being read")
            handle_after = os.fstat(stream.fileno())
            _same_stat(handle_before, handle_after, label)
    except OSError as exc:
        raise FmodCensusError(f"could not read {label}") from exc
    path_after = path.stat()
    link_after = path.lstat()
    _same_stat(handle_after, path_after, label)
    _same_stat(path_before, link_after, label)
    if stat.S_ISLNK(link_after.st_mode) or _is_reparse(link_after):
        raise FmodCensusError(f"{label} became a link during analysis")
    return data, {
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _inventory_file_record(
    value: Any,
    expected_path: str,
    label: str,
) -> Mapping[str, Any]:
    record = _mapping(value, label)
    if record.get("path") != expected_path:
        raise FmodCensusError(f"{label}.path differs from {expected_path}")
    size = record.get("size")
    sha256 = record.get("sha256")
    if (
        type(size) is not int
        or size < 0
        or type(sha256) is not str
        or not _SHA256_RE.fullmatch(sha256)
    ):
        raise FmodCensusError(f"{label} has an invalid size or SHA-256")
    return record


def _enumerate_banks(
    content_root: Path,
    install_root: Path,
) -> tuple[os.stat_result, list[tuple[str, Path, os.stat_result]]]:
    resources = content_root / "resources"
    directory_before = _require_directory(
        resources, install_root, "resources directory"
    )
    discovered: list[tuple[str, Path, os.stat_result]] = []
    children: list[Path] = []
    try:
        for child in resources.iterdir():
            if len(children) >= MAX_RESOURCE_DIRECTORY_ENTRIES:
                raise FmodCensusError(
                    "resources directory entry count exceeds the analysis limit"
                )
            children.append(child)
    except OSError as exc:
        raise FmodCensusError("could not enumerate resources directory") from exc
    for child in children:
        try:
            info = child.lstat()
        except OSError as exc:
            raise FmodCensusError("could not inspect resources entry") from exc
        if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
            raise FmodCensusError("resources directory contains a link/reparse entry")
        if stat.S_ISDIR(info.st_mode):
            raise FmodCensusError("nested resources directories are unsupported")
        if not stat.S_ISREG(info.st_mode):
            raise FmodCensusError("resources directory contains a non-regular entry")
        if child.suffix.casefold() == ".bank":
            relative = child.relative_to(content_root).as_posix()
            discovered.append((relative, child, info))
    directory_after = resources.stat()
    _same_stat(directory_before, directory_after, "resources directory")
    discovered.sort(key=lambda item: (item[0].casefold(), item[0]))
    paths = [path for path, _child, _info in discovered]
    if paths != list(BANK_PATHS):
        raise FmodCensusError(
            "bank surface differs from the exact expected five canonical paths"
        )
    if len({path.casefold() for path in paths}) != len(paths):
        raise FmodCensusError("bank surface contains a case-insensitive collision")
    return directory_after, discovered


def _bank_surface_identity(
    discovered: list[tuple[str, Path, os.stat_result]],
) -> list[tuple[str, tuple[int, ...]]]:
    return [
        (
            relative,
            tuple(getattr(info, field) for field in _STABLE_STAT_FIELDS),
        )
        for relative, _path, info in discovered
    ]


def _require_unchanged_bank_surface(
    directory_before: os.stat_result,
    discovered_before: list[tuple[str, Path, os.stat_result]],
    content_root: Path,
    install_root: Path,
) -> None:
    directory_after, discovered_after = _enumerate_banks(content_root, install_root)
    _same_stat(directory_before, directory_after, "resources directory")
    if _bank_surface_identity(discovered_before) != _bank_surface_identity(
        discovered_after
    ):
        raise FmodCensusError("bank surface changed during complete analysis")


def _read_at(
    stream: BinaryIO,
    offset: int,
    size: int,
    file_size: int,
    label: str,
) -> bytes:
    if offset < 0 or size < 0 or offset + size > file_size:
        raise FmodCensusError(f"{label} is outside the bank")
    stream.seek(offset)
    value = stream.read(size)
    if len(value) != size:
        raise FmodCensusError(f"truncated bank while reading {label}")
    return value


def _fourcc(raw: bytes, label: str) -> str:
    if len(raw) != 4 or any(value < 0x20 or value > 0x7E for value in raw):
        raise FmodCensusError(f"{label} is not a printable FourCC")
    return raw.decode("ascii")


def _find_signature_offsets(
    stream: BinaryIO,
    file_size: int,
    signature: bytes,
    *,
    maximum_occurrences: int,
) -> tuple[str, list[int]]:
    digest = hashlib.sha256()
    offsets: list[int] = []
    tail = b""
    consumed = 0
    stream.seek(0)
    while consumed < file_size:
        chunk = stream.read(min(_CHUNK_BYTES, file_size - consumed))
        if not chunk:
            raise FmodCensusError("bank ended during stable hashing")
        digest.update(chunk)
        window = tail + chunk
        base = consumed - len(tail)
        cursor = 0
        while True:
            found = window.find(signature, cursor)
            if found < 0:
                break
            if len(offsets) >= maximum_occurrences:
                raise FmodCensusError("bank signature count exceeds its limit")
            offsets.append(base + found)
            cursor = found + 1
        consumed += len(chunk)
        tail = window[-(len(signature) - 1) :]
    if stream.read(1):
        raise FmodCensusError("bank grew during stable hashing")
    return digest.hexdigest(), offsets


def _parse_chunk_sequence(
    stream: BinaryIO,
    *,
    start: int,
    end: int,
    file_size: int,
    depth: int,
    state: dict[str, Any],
) -> None:
    if depth > MAX_RIFF_DEPTH:
        raise FmodCensusError("RIFF LIST nesting exceeds the depth limit")
    position = start
    while position < end:
        if end - position < 8:
            raise FmodCensusError("RIFF container has a truncated chunk header")
        header = _read_at(stream, position, 8, file_size, "RIFF chunk header")
        chunk_id = _fourcc(header[:4], "RIFF chunk identifier")
        (payload_size,) = struct.unpack_from("<I", header, 4)
        payload_offset = position + 8
        payload_end = payload_offset + payload_size
        padded_end = payload_end + (payload_size & 1)
        if payload_end < payload_offset or padded_end > end:
            raise FmodCensusError("RIFF chunk escapes its containing span")
        state["node_count"] += 1
        if state["node_count"] > MAX_RIFF_NODES:
            raise FmodCensusError("RIFF node count exceeds the analysis limit")
        state["maximum_depth"] = max(state["maximum_depth"], depth)
        state["chunk_counts"][chunk_id] += 1
        if depth == 0:
            state["top_level"].append(
                {
                    "ordinal": len(state["top_level"]),
                    "id": chunk_id,
                    "offset": position,
                    "payload_size": payload_size,
                }
            )
        if chunk_id == "FMT ":
            state["fmt_chunks"].append((position, payload_offset, payload_size, depth))
        if chunk_id == "SND ":
            state["snd_chunks"].append((position, payload_offset, payload_size, depth))
        if chunk_id == "LIST":
            if payload_size < 4:
                raise FmodCensusError("RIFF LIST payload is shorter than its type")
            list_type = _fourcc(
                _read_at(stream, payload_offset, 4, file_size, "RIFF LIST type"),
                "RIFF LIST type",
            )
            state["list_type_counts"][list_type] += 1
            _parse_chunk_sequence(
                stream,
                start=payload_offset + 4,
                end=payload_end,
                file_size=file_size,
                depth=depth + 1,
                state=state,
            )
        if payload_size & 1:
            padding = _read_at(stream, payload_end, 1, file_size, "RIFF padding")
            if padding != b"\0":
                raise FmodCensusError("RIFF odd-sized chunk has nonzero padding")
            state["padding_bytes"] += 1
        position = padded_end
    if position != end:
        raise FmodCensusError("RIFF child chunks do not consume their container")


def _scan_bank(
    path: Path,
    relative_path: str,
    install_root: Path,
    expected_stat: os.stat_result | None = None,
) -> dict[str, Any]:
    path_before = _require_regular_path(path, install_root, relative_path)
    if expected_stat is not None:
        _same_stat(expected_stat, path_before, relative_path)
    if path_before.st_size > MAX_BANK_BYTES:
        raise FmodCensusError(f"bank exceeds the analysis size limit: {relative_path}")
    file_size = path_before.st_size
    try:
        with path.open("rb") as stream:
            handle_before = os.fstat(stream.fileno())
            _same_stat(path_before, handle_before, relative_path)
            sha256, fsb_offsets = _find_signature_offsets(
                stream,
                file_size,
                b"FSB5",
                maximum_occurrences=1,
            )
            header = _read_at(stream, 0, 12, file_size, "RIFF header")
            if header[:4] != b"RIFF":
                raise FmodCensusError(f"bank is not RIFF: {relative_path}")
            (declared_size,) = struct.unpack_from("<I", header, 4)
            form_type = _fourcc(header[8:12], "RIFF form type")
            if declared_size + 8 != file_size:
                raise FmodCensusError("RIFF declared size does not span the file")
            if form_type != "FEV ":
                raise FmodCensusError("RIFF form type is not the observed FEV form")

            state: dict[str, Any] = {
                "node_count": 0,
                "maximum_depth": 0,
                "padding_bytes": 0,
                "chunk_counts": Counter(),
                "list_type_counts": Counter(),
                "top_level": [],
                "fmt_chunks": [],
                "snd_chunks": [],
            }
            _parse_chunk_sequence(
                stream,
                start=12,
                end=file_size,
                file_size=file_size,
                depth=0,
                state=state,
            )
            expected_top_level = (
                ["FMT ", "LIST"]
                if relative_path.endswith(".strings.bank")
                else ["FMT ", "LIST", "SND "]
            )
            if [chunk["id"] for chunk in state["top_level"]] != expected_top_level:
                raise FmodCensusError("bank has an unsupported top-level RIFF grammar")
            if len(state["fmt_chunks"]) != 1:
                raise FmodCensusError("bank must contain exactly one FMT chunk")
            (
                _fmt_offset,
                fmt_payload_offset,
                fmt_size,
                fmt_depth,
            ) = state["fmt_chunks"][0]
            if fmt_depth != 0 or fmt_size != 8:
                raise FmodCensusError("bank FMT chunk has an unsupported shape")
            fmt_words = list(
                struct.unpack(
                    "<II",
                    _read_at(stream, fmt_payload_offset, 8, file_size, "FMT payload"),
                )
            )
            if fmt_words != [99, 99]:
                raise FmodCensusError("bank FMT raw words differ from the exact corpus")

            is_strings_bank = relative_path.endswith(".strings.bank")
            fsb5: dict[str, Any] | None
            if is_strings_bank:
                if state["snd_chunks"] or fsb_offsets:
                    raise FmodCensusError(
                        "strings bank has an unexpected SND chunk or FSB5 signature"
                    )
                fsb5 = None
            else:
                if len(state["snd_chunks"]) != 1 or len(fsb_offsets) != 1:
                    raise FmodCensusError(
                        "non-strings bank needs one SND chunk and one FSB5 signature"
                    )
                _snd_offset, snd_payload_offset, snd_size, snd_depth = state[
                    "snd_chunks"
                ][0]
                fsb_offset = fsb_offsets[0]
                if (
                    snd_depth != 0
                    or fsb_offset < snd_payload_offset
                    or fsb_offset + 60 > snd_payload_offset + snd_size
                ):
                    raise FmodCensusError(
                        "FSB5 header is outside the top-level SND span"
                    )
                fsb_header = _read_at(stream, fsb_offset, 60, file_size, "FSB5 header")
                if fsb_header[:4] != b"FSB5":
                    raise FmodCensusError(
                        "FSB5 signature scan disagrees with header read"
                    )
                raw_words = list(struct.unpack_from("<5I", fsb_header, 4))
                candidate_end = fsb_offset + 60 + sum(raw_words[2:5])
                if (
                    candidate_end != file_size
                    or candidate_end != snd_payload_offset + snd_size
                ):
                    raise FmodCensusError("FSB5 raw candidate span does not reach EOF")
                wav_count = state["chunk_counts"]["WAV "]
                fsb5 = {
                    "occurrences": 1,
                    "offsets": [fsb_offset],
                    "raw_u32le_after_magic": raw_words,
                    "candidate_span_end": candidate_end,
                    "candidate_span_matches_eof": True,
                    "recursive_wav_chunk_count": wav_count,
                    "raw_word_2_matches_wav_count": raw_words[1] == wav_count,
                }
                if fsb5["raw_word_2_matches_wav_count"] is not True:
                    raise FmodCensusError("FSB5 raw word/WAV count equality differs")
            handle_after = os.fstat(stream.fileno())
            _same_stat(handle_before, handle_after, relative_path)
    except OSError as exc:
        raise FmodCensusError(f"could not scan bank: {relative_path}") from exc
    path_after = path.stat()
    link_after = path.lstat()
    _same_stat(handle_after, path_after, relative_path)
    _same_stat(path_before, link_after, relative_path)
    if stat.S_ISLNK(link_after.st_mode) or _is_reparse(link_after):
        raise FmodCensusError(f"bank became a link during analysis: {relative_path}")
    return {
        "path": relative_path,
        "size": file_size,
        "sha256": sha256,
        "riff": {
            "magic": "RIFF",
            "declared_size": declared_size,
            "form_type": form_type,
            "exact_file_span": True,
            "top_level_chunks": state["top_level"],
            "node_count": state["node_count"],
            "maximum_depth": state["maximum_depth"],
            "padding_bytes": state["padding_bytes"],
            "chunk_id_counts": [
                {"id": key, "occurrences": state["chunk_counts"][key]}
                for key in sorted(state["chunk_counts"])
            ],
            "list_type_counts": [
                {"type": key, "occurrences": state["list_type_counts"][key]}
                for key in sorted(state["list_type_counts"])
            ],
            "parsed_to_eof": True,
        },
        "fmt_payload_u32le": fmt_words,
        "fsb5": fsb5,
    }


def _unpack(fmt: str, data: bytes, offset: int, label: str) -> tuple[Any, ...]:
    size = struct.calcsize(fmt)
    if offset < 0 or offset + size > len(data):
        raise FmodCensusError(f"truncated PE while reading {label}")
    return struct.unpack_from(fmt, data, offset)


def _pe_named_exports(
    data: bytes,
    image: PEImage,
) -> tuple[dict[str, Any], set[str], set[int]]:
    if len(image.data_directories) <= _IMAGE_DIRECTORY_ENTRY_EXPORT:
        raise FmodCensusError("FMOD library has no export directory")
    export_rva, export_size = image.data_directories[_IMAGE_DIRECTORY_ENTRY_EXPORT]
    if not export_rva or export_size < 40:
        raise FmodCensusError("FMOD library export directory is absent or undersized")
    if export_size > MAX_PE_BYTES:
        raise FmodCensusError("FMOD library export directory exceeds its limit")
    export_offset = image.rva_span_to_file_offset(export_rva, export_size)
    directory_offset = image.rva_span_to_file_offset(export_rva, 40)
    if export_offset is None or directory_offset is None:
        raise FmodCensusError("FMOD export directory is not file-backed")
    (
        _characteristics,
        _timestamp,
        _major,
        _minor,
        _module_name_rva,
        ordinal_base,
        function_count,
        name_count,
        functions_rva,
        names_rva,
        ordinals_rva,
    ) = _unpack("<IIHHIIIIIII", data, directory_offset, "export directory")
    if (
        function_count < 1
        or name_count < 1
        or function_count > MAX_EXPORT_NAMES
        or name_count > MAX_EXPORT_NAMES
    ):
        raise FmodCensusError("FMOD export counts are unsupported")
    functions_offset = image.rva_span_to_file_offset(functions_rva, function_count * 4)
    names_offset = image.rva_span_to_file_offset(names_rva, name_count * 4)
    ordinals_offset = image.rva_span_to_file_offset(ordinals_rva, name_count * 2)
    if None in {functions_offset, names_offset, ordinals_offset}:
        raise FmodCensusError("FMOD export arrays are not file-backed")
    names: set[str] = set()
    named_ordinal_indices: set[int] = set()
    for index in range(name_count):
        (name_rva,) = _unpack("<I", data, names_offset + index * 4, "export name RVA")
        try:
            name = image._read_rva_c_string(  # noqa: SLF001
                name_rva,
                f"export name {index}",
                maximum_bytes=MAX_EXPORT_NAME_BYTES,
            )
        except PEAnchorError as exc:
            raise FmodCensusError(str(exc)) from exc
        if (
            not name
            or name in names
            or any(ord(character) < 0x20 for character in name)
        ):
            raise FmodCensusError("FMOD export name is empty, duplicate, or invalid")
        (ordinal_index,) = _unpack(
            "<H", data, ordinals_offset + index * 2, "export ordinal index"
        )
        if ordinal_index >= function_count:
            raise FmodCensusError("FMOD export ordinal index exceeds function table")
        names.add(name)
        named_ordinal_indices.add(ordinal_index)

    nonzero_function_slots = 0
    forwarder_count = 0
    valid_ordinals: set[int] = set()
    for ordinal_index in range(function_count):
        (function_rva,) = _unpack(
            "<I", data, functions_offset + ordinal_index * 4, "export function RVA"
        )
        if ordinal_base + ordinal_index > 0xFFFFFFFF:
            raise FmodCensusError("FMOD export ordinal exceeds u32")
        if function_rva == 0:
            if ordinal_index in named_ordinal_indices:
                raise FmodCensusError("named FMOD export resolves to an empty slot")
            continue
        nonzero_function_slots += 1
        if export_rva <= function_rva < export_rva + export_size:
            forwarder_offset = export_offset + (function_rva - export_rva)
            forwarder_limit = min(
                export_offset + export_size,
                forwarder_offset + MAX_EXPORT_NAME_BYTES + 1,
            )
            terminator = data.find(b"\0", forwarder_offset, forwarder_limit)
            if terminator <= forwarder_offset:
                raise FmodCensusError("FMOD export forwarder is empty or unterminated")
            try:
                forwarder = data[forwarder_offset:terminator].decode("ascii")
            except UnicodeDecodeError as exc:
                raise FmodCensusError("FMOD export forwarder is not ASCII") from exc
            if any(
                ord(character) < 0x20 or ord(character) > 0x7E
                for character in forwarder
            ):
                raise FmodCensusError("FMOD export forwarder is not bounded text")
            forwarder_count += 1
        elif not image.rva_span_is_mapped(function_rva, 1):
            raise FmodCensusError("FMOD export target is outside the image")
        valid_ordinals.add(ordinal_base + ordinal_index)
    sorted_names = sorted(names)
    return {
        "function_slots": function_count,
        "nonzero_function_slots": nonzero_function_slots,
        "named_count": len(sorted_names),
        "named_ordinal_slots": len(named_ordinal_indices),
        "named_alias_count": len(sorted_names) - len(named_ordinal_indices),
        "ordinal_only_count": (
            nonzero_function_slots - len(named_ordinal_indices)
        ),
        "forwarder_count": forwarder_count,
        "sorted_named_identity_sha256": _canonical_sha256(sorted_names),
    }, names, valid_ordinals


def _resource_directory_entries(
    data: bytes,
    *,
    base_offset: int,
    resource_size: int,
    relative_offset: int,
    label: str,
) -> list[tuple[int, int]]:
    if relative_offset < 0 or relative_offset + 16 > resource_size:
        raise FmodCensusError(f"{label} resource directory is outside its span")
    offset = base_offset + relative_offset
    (
        _characteristics,
        _timestamp,
        _major,
        _minor,
        named_count,
        id_count,
    ) = _unpack("<IIHHHH", data, offset, f"{label} resource directory")
    count = named_count + id_count
    if count > 4096 or relative_offset + 16 + count * 8 > resource_size:
        raise FmodCensusError(f"{label} resource entry table is invalid")
    return [
        _unpack("<II", data, offset + 16 + index * 8, f"{label} resource entry")
        for index in range(count)
    ]


def _pe_version_blob(data: bytes, image: PEImage) -> bytes:
    if len(image.data_directories) <= _IMAGE_DIRECTORY_ENTRY_RESOURCE:
        raise FmodCensusError("FMOD library has no resource directory")
    resource_rva, resource_size = image.data_directories[
        _IMAGE_DIRECTORY_ENTRY_RESOURCE
    ]
    if not resource_rva or resource_size < 16:
        raise FmodCensusError("FMOD resource directory is absent or undersized")
    base_offset = image.rva_span_to_file_offset(resource_rva, resource_size)
    if base_offset is None:
        raise FmodCensusError("FMOD resource directory is not file-backed")
    root_entries = _resource_directory_entries(
        data,
        base_offset=base_offset,
        resource_size=resource_size,
        relative_offset=0,
        label="root",
    )
    version_entries = [
        target
        for name, target in root_entries
        if not (name & 0x80000000) and name == _RT_VERSION
    ]
    if len(version_entries) != 1 or not (version_entries[0] & 0x80000000):
        raise FmodCensusError("FMOD library needs one version resource tree")
    name_entries = _resource_directory_entries(
        data,
        base_offset=base_offset,
        resource_size=resource_size,
        relative_offset=version_entries[0] & 0x7FFFFFFF,
        label="version-name",
    )
    data_entry_relatives: list[int] = []
    for name, target in name_entries:
        if name & 0x80000000 or not (target & 0x80000000):
            raise FmodCensusError("version resource name level is unsupported")
        language_entries = _resource_directory_entries(
            data,
            base_offset=base_offset,
            resource_size=resource_size,
            relative_offset=target & 0x7FFFFFFF,
            label="version-language",
        )
        for language, data_target in language_entries:
            if language & 0x80000000 or data_target & 0x80000000:
                raise FmodCensusError("version resource language level is unsupported")
            data_entry_relatives.append(data_target)
    if len(data_entry_relatives) != 1:
        raise FmodCensusError("FMOD library needs exactly one version resource")
    data_relative = data_entry_relatives[0]
    if data_relative + 16 > resource_size:
        raise FmodCensusError("version resource data entry is outside its span")
    data_rva, size, _codepage, reserved = _unpack(
        "<IIII", data, base_offset + data_relative, "version resource data entry"
    )
    if reserved != 0 or size < 1 or size > MAX_VERSION_RESOURCE_BYTES:
        raise FmodCensusError("version resource data entry is invalid")
    if data_rva < resource_rva or data_rva + size > resource_rva + resource_size:
        raise FmodCensusError("version resource payload escapes its resource span")
    data_offset = image.rva_span_to_file_offset(data_rva, size)
    if data_offset is None:
        raise FmodCensusError("version resource payload is not file-backed")
    return data[data_offset : data_offset + size]


def _align4(value: int) -> int:
    return (value + 3) & ~3


def _read_utf16_key(blob: bytes, start: int, end: int) -> tuple[str, int]:
    cursor = start
    units = bytearray()
    while cursor + 2 <= end:
        unit = blob[cursor : cursor + 2]
        cursor += 2
        if unit == b"\0\0":
            break
        units.extend(unit)
        if len(units) > 256:
            raise FmodCensusError("version resource key exceeds its limit")
    else:
        raise FmodCensusError("version resource key is unterminated")
    try:
        value = bytes(units).decode("utf-16-le")
    except UnicodeDecodeError as exc:
        raise FmodCensusError("version resource key is invalid UTF-16") from exc
    if not value or any(
        ord(character) < 0x20 or ord(character) > 0x7E
        for character in value
    ):
        raise FmodCensusError("version resource key is not bounded ASCII")
    return value, cursor


def _parse_version_block(
    blob: bytes,
    offset: int,
    container_end: int,
    depth: int,
    counter: list[int],
) -> tuple[dict[str, Any], int]:
    if depth > MAX_VERSION_BLOCK_DEPTH:
        raise FmodCensusError("version resource nesting exceeds its limit")
    counter[0] += 1
    if counter[0] > MAX_VERSION_BLOCKS:
        raise FmodCensusError("version resource block count exceeds its limit")
    length, value_length, value_type = _unpack(
        "<HHH", blob, offset, "version block header"
    )
    if length < 6 or offset + length > container_end:
        raise FmodCensusError("version block length escapes its container")
    end = offset + length
    key, after_key = _read_utf16_key(blob, offset + 6, end)
    value_offset = _align4(after_key)
    value_bytes = value_length * 2 if value_type == 1 else value_length
    value_end = value_offset + value_bytes
    if value_type not in {0, 1} or value_offset > end or value_end > end:
        raise FmodCensusError("version block value is outside its block")
    if any(blob[after_key:value_offset]):
        raise FmodCensusError("version block has nonzero key/value padding")
    value = blob[value_offset:value_end]
    children: list[dict[str, Any]] = []
    child_offset = _align4(value_end)
    if child_offset > end:
        if value_end != end:
            raise FmodCensusError("version block child alignment escapes its block")
        child_offset = end
    elif any(blob[value_end:child_offset]):
        raise FmodCensusError("version block has nonzero value padding")
    while child_offset < end:
        if child_offset + 6 > end:
            raise FmodCensusError("version block has truncated child padding")
        child, child_end = _parse_version_block(
            blob,
            child_offset,
            end,
            depth + 1,
            counter,
        )
        children.append(child)
        next_offset = end if child_end == end else _align4(child_end)
        if next_offset <= child_offset or next_offset > end:
            raise FmodCensusError("version child alignment is invalid")
        if any(blob[child_end:next_offset]):
            raise FmodCensusError("version block has nonzero child padding")
        child_offset = next_offset
    if child_offset != end:
        raise FmodCensusError("version children do not consume their block")
    return {
        "key": key,
        "value_type": value_type,
        "value_length": value_length,
        "value": value,
        "children": children,
    }, end


def _text_version_value(block: Mapping[str, Any], label: str) -> str:
    if block.get("value_type") != 1:
        raise FmodCensusError(f"{label} version value is not text")
    raw = block.get("value")
    if type(raw) is not bytes:
        raise FmodCensusError(f"{label} version value is malformed")
    try:
        value = raw.decode("utf-16-le")
    except UnicodeDecodeError as exc:
        raise FmodCensusError(f"{label} version value is invalid UTF-16") from exc
    if not value.endswith("\0") or "\0" in value[:-1]:
        raise FmodCensusError(
            f"{label} version value is not exactly NUL-terminated"
        )
    value = value[:-1]
    if not value or len(value) > 256:
        raise FmodCensusError(f"{label} version value is not bounded text")
    return value


def _version_resource_facts(blob: bytes, expected_filename: str) -> dict[str, Any]:
    root, end = _parse_version_block(blob, 0, len(blob), 0, [0])
    if end != len(blob) or root["key"] != "VS_VERSION_INFO":
        raise FmodCensusError("version resource root is not exact")
    fixed = root["value"]
    if root["value_type"] != 0 or len(fixed) != 52:
        raise FmodCensusError("version resource fixed info has an invalid shape")
    words = list(struct.unpack("<13I", fixed))
    if words[0] != _VS_FIXEDFILEINFO_SIGNATURE or words[1] != 0x00010000:
        raise FmodCensusError("version resource fixed-info signature differs")
    root_children = [
        _mapping(child, "version root child") for child in root["children"]
    ]
    root_by_key: dict[str, list[Mapping[str, Any]]] = {}
    for child in root_children:
        key = child.get("key")
        if type(key) is not str:
            raise FmodCensusError("version resource hierarchy is malformed")
        root_by_key.setdefault(key, []).append(child)
    if (
        set(root_by_key) - {"StringFileInfo", "VarFileInfo"}
        or len(root_by_key.get("StringFileInfo", [])) != 1
        or len(root_by_key.get("VarFileInfo", [])) > 1
    ):
        raise FmodCensusError("version resource hierarchy is unsupported")

    string_info = root_by_key["StringFileInfo"][0]
    if (
        string_info.get("value_type") != 1
        or string_info.get("value_length") != 0
        or string_info.get("value") != b""
    ):
        raise FmodCensusError("StringFileInfo has an invalid shape")
    string_tables = string_info.get("children")
    if type(string_tables) is not list or len(string_tables) != 1:
        raise FmodCensusError("StringFileInfo needs exactly one string table")
    string_table = _mapping(string_tables[0], "version string table")
    if (
        type(string_table.get("key")) is not str
        or _VERSION_STRING_TABLE_RE.fullmatch(string_table["key"]) is None
        or string_table.get("value_type") != 1
        or string_table.get("value_length") != 0
        or string_table.get("value") != b""
    ):
        raise FmodCensusError("version string table has an invalid shape")
    string_entries = string_table.get("children")
    if type(string_entries) is not list:
        raise FmodCensusError("version string table child list is malformed")
    selected: dict[str, list[str]] = {
        "FileVersion": [],
        "ProductVersion": [],
        "OriginalFilename": [],
    }
    seen_keys: set[str] = set()
    for raw_entry in string_entries:
        entry = _mapping(raw_entry, "version string entry")
        key = entry.get("key")
        children = entry.get("children")
        if (
            type(key) is not str
            or key in seen_keys
            or type(children) is not list
            or children
        ):
            raise FmodCensusError("version string entry hierarchy is invalid")
        seen_keys.add(key)
        value = _text_version_value(entry, key)
        if key in selected:
            selected[key].append(value)

    var_infos = root_by_key.get("VarFileInfo", [])
    if var_infos:
        var_info = var_infos[0]
        translations = var_info.get("children")
        if (
            var_info.get("value_type") != 1
            or var_info.get("value_length") != 0
            or var_info.get("value") != b""
            or type(translations) is not list
            or len(translations) != 1
        ):
            raise FmodCensusError("VarFileInfo has an invalid shape")
        translation = _mapping(translations[0], "version translation")
        if (
            translation.get("key") != "Translation"
            or translation.get("value_type") != 0
            or translation.get("value_length") != 4
            or type(translation.get("value")) is not bytes
            or len(translation["value"]) != 4
            or translation.get("children") != []
        ):
            raise FmodCensusError("version translation has an invalid shape")
    if any(len(values) != 1 for values in selected.values()):
        raise FmodCensusError("version resource needs one whitelisted value each")
    file_version = selected["FileVersion"][0]
    product_version = selected["ProductVersion"][0]
    original_filename = selected["OriginalFilename"][0]
    match = _FILE_VERSION_RE.fullmatch(file_version)
    if match is None or _PRODUCT_VERSION_RE.fullmatch(product_version) is None:
        raise FmodCensusError("FMOD version resource has an unsupported version shape")
    if match.group("version") != product_version:
        raise FmodCensusError("FMOD file/product versions disagree")
    if original_filename.casefold() != expected_filename.casefold():
        raise FmodCensusError("FMOD version original filename disagrees with path")
    return {
        "version": product_version,
        "build": int(match.group("build")),
        "fixed_file_version_u32le": words[2:4],
        "fixed_product_version_u32le": words[4:6],
        "original_filename_matches_path": True,
    }


def _scan_library(
    root: Path,
    path: str,
    sealed_record: Mapping[str, Any],
) -> tuple[dict[str, Any], set[str], set[int]]:
    data, observed = _read_stable_binary(
        root.joinpath(*PurePosixPath(path).parts),
        root,
        path,
        maximum_bytes=MAX_PE_BYTES,
    )
    expected = _inventory_file_record(sealed_record, path, f"inventory {path}")
    if observed != {"size": expected["size"], "sha256": expected["sha256"]}:
        raise FmodCensusError(f"{path} does not match its sealed inventory identity")
    try:
        image = PEImage(data)
    except PEAnchorError as exc:
        raise FmodCensusError(f"could not parse {path}: {exc}") from exc
    if image.architecture != expected.get("architecture"):
        raise FmodCensusError(f"{path} architecture differs from inventory")
    exports, export_names, export_ordinals = _pe_named_exports(data, image)
    version = _version_resource_facts(_pe_version_blob(data, image), path)
    return {
        "path": path,
        "size": observed["size"],
        "sha256": observed["sha256"],
        "format": expected.get("format"),
        "architecture": image.architecture,
        "bits": image.bits,
        "version_resource": version,
        "exports": exports,
    }, export_names, export_ordinals


def _executable_interface(
    root: Path,
    inventory: Mapping[str, Any],
    export_names: Mapping[str, set[str]],
    export_ordinals: Mapping[str, set[int]],
) -> dict[str, Any]:
    executable_record = _mapping(inventory.get("executable"), "inventory.executable")
    executable_relative = _normalized_inventory_path(
        executable_record.get("path"), "inventory.executable.path"
    )
    data, observed = _read_stable_binary(
        root.joinpath(*executable_relative.parts),
        root,
        executable_relative.as_posix(),
        maximum_bytes=MAX_PE_BYTES,
    )
    expected = _inventory_file_record(
        executable_record,
        executable_relative.as_posix(),
        "inventory.executable",
    )
    if observed != {"size": expected["size"], "sha256": expected["sha256"]}:
        raise FmodCensusError("executable does not match its sealed identity")
    try:
        image = PEImage(data)
        all_imports = image.imports()
    except PEAnchorError as exc:
        raise FmodCensusError(
            f"could not parse executable FMOD interface: {exc}"
        ) from exc

    canonical_library = {path.casefold(): path for path in FMOD_LIBRARY_PATHS}
    named_counts: Counter[tuple[str, str]] = Counter()
    ordinal_counts: Counter[str] = Counter()
    for record in all_imports:
        library = record.get("library")
        if type(library) is not str or library.casefold() not in canonical_library:
            continue
        normalized_library = canonical_library[library.casefold()]
        name = record.get("name")
        if name is None:
            ordinal = record.get("ordinal")
            if (
                type(ordinal) is not int
                or ordinal not in export_ordinals[normalized_library]
            ):
                raise FmodCensusError(
                    "executable FMOD ordinal import is absent from sealed DLL "
                    "exports"
                )
            ordinal_counts[normalized_library] += 1
            continue
        if type(name) is not str or not name or len(name) > MAX_EXPORT_NAME_BYTES:
            raise FmodCensusError("executable FMOD import name is malformed")
        if name not in export_names[normalized_library]:
            raise FmodCensusError(
                "executable FMOD import is absent from sealed DLL exports"
            )
        named_counts[(normalized_library, name)] += 1
    if any(
        not any(library == expected_library for library, _name in named_counts)
        for expected_library in FMOD_LIBRARY_PATHS
    ):
        raise FmodCensusError("executable does not import both FMOD libraries")

    literals = []
    for path in BANK_PATHS:
        basename = PurePosixPath(path).name
        needle = basename.encode("ascii")
        offsets: list[int] = []
        cursor = 0
        while True:
            found = data.find(needle, cursor)
            if found < 0:
                break
            offsets.append(found)
            cursor = found + 1
        if len(offsets) != 1:
            raise FmodCensusError(
                f"executable needs one exact byte occurrence of {basename}"
            )
        literals.append(
            {
                "basename": basename,
                "occurrence_count": len(offsets),
                "file_offsets": offsets,
            }
        )
    return {
        "path": executable_relative.as_posix(),
        "size": observed["size"],
        "sha256": observed["sha256"],
        "named_imports": [
            {
                "library": key[0],
                "name": key[1],
                "occurrences": named_counts[key],
            }
            for key in sorted(named_counts)
        ],
        "ordinal_import_counts": [
            {"library": library, "occurrences": ordinal_counts[library]}
            for library in FMOD_LIBRARY_PATHS
        ],
        "bank_basename_literals": literals,
    }


def _assert_publication_safe(value: Any, label: str = "artifact") -> None:
    if type(value) is str:
        if len(value) > 1024 or "\0" in value:
            raise FmodCensusError(f"{label} contains an unbounded string")
        lowered = value.casefold()
        if (
            _ABSOLUTE_WINDOWS_PATH_RE.search(value)
            or value.startswith(("/", "\\\\"))
            or any(marker in lowered for marker in _FORBIDDEN_PUBLICATION_MARKERS)
            or (
                re.fullmatch(r"[0-9A-Fa-f]{32,}", value) is not None
                and _SHA256_RE.fullmatch(value) is None
            )
        ):
            raise FmodCensusError(f"{label} contains forbidden path/string data")
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
                raise FmodCensusError(f"{label} has an invalid field name")
            _assert_publication_safe(item, f"{label}.{key}")
        return
    raise FmodCensusError(f"{label} contains a non-publication value")


def build_fmod_census(
    install_root: Path,
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a metadata-only FMOD bank/native interface census."""
    root, content_root, identity, live_inventory = _attest_installation(
        install_root,
        inventory,
    )
    directory_before, discovered = _enumerate_banks(content_root, root)
    banks = [
        _scan_bank(path, relative, root, expected_stat)
        for relative, path, expected_stat in discovered
    ]
    _require_unchanged_bank_surface(
        directory_before,
        discovered,
        content_root,
        root,
    )
    bank_bytes = sum(bank["size"] for bank in banks)
    if bank_bytes > MAX_AGGREGATE_BANK_BYTES:
        raise FmodCensusError("aggregate bank bytes exceed the analysis limit")
    bank_manifest_files = [
        {key: bank[key] for key in ("path", "size", "sha256")} for bank in banks
    ]

    native_values = live_inventory.get("native_libraries")
    if not isinstance(native_values, list):
        raise FmodCensusError("inventory.native_libraries must be an array")
    by_path: dict[str, list[Mapping[str, Any]]] = {
        path: [] for path in FMOD_LIBRARY_PATHS
    }
    for index, value in enumerate(native_values):
        record = _mapping(value, f"inventory.native_libraries[{index}]")
        path = record.get("path")
        if type(path) is str and path.casefold() in by_path:
            by_path[path.casefold()].append(record)
    if any(len(by_path[path]) != 1 for path in FMOD_LIBRARY_PATHS):
        raise FmodCensusError("sealed inventory needs one record per FMOD library")

    libraries = []
    export_names: dict[str, set[str]] = {}
    export_ordinals: dict[str, set[int]] = {}
    for path in FMOD_LIBRARY_PATHS:
        library, names, ordinals = _scan_library(root, path, by_path[path][0])
        libraries.append(library)
        export_names[path] = names
        export_ordinals[path] = ordinals
    executable_interface = _executable_interface(
        root,
        live_inventory,
        export_names,
        export_ordinals,
    )
    _require_unchanged_bank_surface(
        directory_before,
        discovered,
        content_root,
        root,
    )
    named_import_occurrences = sum(
        record["occurrences"] for record in executable_interface["named_imports"]
    )
    ordinal_import_occurrences = sum(
        record["occurrences"]
        for record in executable_interface["ordinal_import_counts"]
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": identity,
        "baseline_inventory": {
            "label": live_inventory.get("label"),
            "canonical_sha256": _canonical_sha256(live_inventory),
        },
        "bank_manifest": {
            "root": "resources",
            "file_count": len(bank_manifest_files),
            "byte_count": bank_bytes,
            "canonical_sha256": _canonical_sha256(bank_manifest_files),
            "expected_paths": list(BANK_PATHS),
        },
        "banks": banks,
        "native_libraries": libraries,
        "executable_interface": executable_interface,
        "method": {
            "source_execution": False,
            "audio_extraction": False,
            "string_table_decoding": False,
            "payload_bytes_published": False,
            "semantic_inference": False,
            "bank_parser": (
                "bounded RIFF/FEV header and recursive LIST-container validation; "
                "only top-level chunk facts, aggregate FourCC counts, and bounded "
                "raw FMT/FSB5 header words are retained"
            ),
            "native_parser": (
                "dependency-free bounded PE export-slot/version parsing plus "
                "exact named imports from the existing PE image parser"
            ),
            "export_identity": (
                "SHA-256 of canonical JSON for the sorted complete named-export "
                "set; unnamed exports remain aggregate ordinal-slot counts"
            ),
            "limitations": [
                "RIFF FourCCs and FSB5 raw words are byte facts, not semantic "
                "field interpretations",
                "absence of SND or FSB5 does not prove that a bank is audio-free",
                "DLL version resources are publisher metadata, not ABI or "
                "runtime-load proof",
                "imports describe available executable calls, not reachability "
                "or successful calls",
                "bank basename bytes do not prove load order, reachability, or "
                "successful loading",
                "no event paths, bus/VCA paths, string-table values, codec facts, "
                "sample records, recursive node topology, or audio payload "
                "bytes/isolated fingerprints are published",
            ],
        },
        "summary": {
            "bank_files": len(banks),
            "bank_bytes": bank_bytes,
            "riff_nodes": sum(bank["riff"]["node_count"] for bank in banks),
            "top_level_chunks": sum(
                len(bank["riff"]["top_level_chunks"]) for bank in banks
            ),
            "recursive_wav_chunks": sum(
                next(
                    (
                        item["occurrences"]
                        for item in bank["riff"]["chunk_id_counts"]
                        if item["id"] == "WAV "
                    ),
                    0,
                )
                for bank in banks
            ),
            "fsb5_signatures": sum(bank["fsb5"] is not None for bank in banks),
            "native_libraries": len(libraries),
            "named_exports": sum(
                library["exports"]["named_count"] for library in libraries
            ),
            "ordinal_only_exports": sum(
                library["exports"]["ordinal_only_count"] for library in libraries
            ),
            "executable_named_imports": named_import_occurrences,
            "executable_ordinal_imports": ordinal_import_occurrences,
            "bank_basename_literal_occurrences": sum(
                literal["occurrence_count"]
                for literal in executable_interface["bank_basename_literals"]
            ),
            "schema_violations": 0,
        },
    }
    _assert_publication_safe(result)
    return result


def validate_fmod_census(
    install_root: Path,
    evidence: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and canonical-byte-compare one normalized FMOD census."""
    if not isinstance(evidence, Mapping):
        raise FmodCensusError("evidence must be an object")
    _validate_json_tree(evidence, "evidence")
    expected = build_fmod_census(install_root, inventory=inventory)
    if _canonical_bytes(evidence) != _canonical_bytes(expected):
        raise FmodCensusError(
            "FMOD census does not match the exact installation and inventory"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": expected["build_identity"],
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": expected["summary"],
    }


def encode_fmod_census(value: Mapping[str, Any]) -> str:
    """Encode census or verification output deterministically."""
    _validate_json_tree(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
