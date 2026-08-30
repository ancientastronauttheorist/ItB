"""Validate and inventory Into the Breach's deterministic resource archive.

The inventory records paths, offsets, sizes, types, and payload hashes.  It
never extracts or returns asset payload bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
from collections import Counter
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from src.observatory.content_inventory import InventoryError, create_inventory
from src.observatory.pe_anchor_map import PEAnchorError, _inventory_identity


SCHEMA_VERSION = 1
ANALYSIS_KIND = "itb_resource_archive_inventory"
VERIFICATION_KIND = "itb_resource_archive_inventory_verification"
ARCHIVE_PATH = "resources/resource.dat"
MAX_ARCHIVE_BYTES = 4 * 1024 * 1024 * 1024
MAX_ENTRY_COUNT = 1_000_000
MAX_PATH_BYTES = 16 * 1024
_CHUNK_SIZE = 1024 * 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_TRUETYPE_SIGNATURES = {b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"}
_METHOD = {
    "archive_grammar": (
        "little-endian u32 entry_count, followed by entry_count u32 absolute "
        "record offsets; each record is u32 payload_size, u32 UTF-8 path_size, "
        "path bytes, then payload bytes"
    ),
    "validation": (
        "offsets must be unique, strictly increasing, contiguous from the end "
        "of the table through EOF, and every path/payload span must be exact"
    ),
    "provenance": (
        "the supplied installation inventory is independently rebuilt from "
        "the installation root and must match exactly; resource.dat is then "
        "resolved beneath that inventory's content root and must match its "
        "sealed path, size, and SHA-256 record"
    ),
    "recorded": [
        "record ordinal and offsets",
        "UTF-8 resource path and extension class",
        "payload size and SHA-256",
        "archive size and SHA-256",
    ],
    "omitted": [
        "asset payload bytes",
        "decoded images",
        "font glyphs",
        "bulk proprietary resource content",
    ],
    "not_claimed": [
        "asset rendering semantics",
        "custom .font payload grammar",
        "resource reachability from the executable or Lua",
        "cross-build resource equivalence",
    ],
}


class ResourceArchiveError(PEAnchorError):
    """Raised when an ITB resource archive or inventory is invalid."""


def _read_exact(stream: BinaryIO, size: int, label: str) -> bytes:
    if size < 0:
        raise ResourceArchiveError(f"{label} has a negative size")
    value = stream.read(size)
    if len(value) != size:
        raise ResourceArchiveError(f"truncated archive while reading {label}")
    return value


_STABLE_STAT_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns")


def _require_same_file(
    left: os.stat_result,
    right: os.stat_result,
    label: str,
) -> None:
    if any(
        getattr(left, field) != getattr(right, field)
        for field in _STABLE_STAT_FIELDS
    ):
        raise ResourceArchiveError(f"{label} changed during analysis")


def _validate_path(raw: bytes, ordinal: int) -> str:
    if not raw or len(raw) > MAX_PATH_BYTES:
        raise ResourceArchiveError(f"record {ordinal} has an invalid path size")
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResourceArchiveError(
            f"record {ordinal} path is not valid UTF-8"
        ) from exc
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or "\0" in value
        or any(ord(character) < 0x20 for character in value)
    ):
        raise ResourceArchiveError(f"record {ordinal} path is not canonical")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ResourceArchiveError(f"record {ordinal} path is not canonical")
    return value


def _resource_kind(path: str, prefix: bytes) -> tuple[str, str]:
    extension = PurePosixPath(path).suffix.casefold()
    if extension == ".png":
        if not prefix.startswith(_PNG_SIGNATURE):
            raise ResourceArchiveError(f"PNG resource has an invalid signature: {path}")
        return extension, "png"
    if extension == ".ttf":
        if prefix[:4] not in _TRUETYPE_SIGNATURES:
            raise ResourceArchiveError(
                f"TrueType resource has an invalid signature: {path}"
            )
        return extension, "truetype_font"
    if extension == ".font":
        return extension, "custom_font"
    return extension, "other"


def _identity_from_inventory(inventory: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(inventory, Mapping):
        raise ResourceArchiveError("inventory must be an object")
    executable = inventory.get("executable")
    if not isinstance(executable, Mapping):
        raise ResourceArchiveError("inventory.executable must be an object")
    try:
        sha256 = executable["sha256"]
        size = executable["size"]
        architecture = executable["architecture"]
    except KeyError as exc:
        raise ResourceArchiveError(
            "inventory executable identity is incomplete"
        ) from exc
    if (
        type(sha256) is not str
        or len(sha256) != 64
        or any(character not in "0123456789abcdef" for character in sha256)
        or type(size) is not int
        or size < 0
        or type(architecture) is not str
        or not architecture
    ):
        raise ResourceArchiveError("inventory executable identity is malformed")
    try:
        return _inventory_identity(
            inventory,
            sha256=sha256,
            size=size,
            architecture=architecture,
        )
    except PEAnchorError as exc:
        raise ResourceArchiveError(str(exc)) from exc


def _attest_installation(
    install_root: Path,
    inventory: Mapping[str, Any],
) -> tuple[Path, dict[str, Any], Mapping[str, Any]]:
    """Rebuild one sealed installation inventory and locate its resource.dat."""
    if not isinstance(inventory, Mapping):
        raise ResourceArchiveError("inventory must be an object")
    platform_name = inventory.get("platform")
    label = inventory.get("label")
    if type(platform_name) is not str or not platform_name:
        raise ResourceArchiveError("inventory.platform must be text")
    if label is not None and type(label) is not str:
        raise ResourceArchiveError("inventory.label must be text or null")
    try:
        live_inventory = create_inventory(
            install_root,
            platform_name=platform_name,
            label=label,
        )
    except (InventoryError, OSError, UnicodeError) as exc:
        raise ResourceArchiveError(
            f"could not rebuild the installation inventory: {exc}"
        ) from exc
    if live_inventory != inventory:
        raise ResourceArchiveError(
            "installation does not match the supplied sealed inventory"
        )

    identity = _identity_from_inventory(live_inventory)
    resource_archives = live_inventory.get("resource_archives")
    if not isinstance(resource_archives, list):
        raise ResourceArchiveError("inventory.resource_archives must be an array")
    matching = [
        entry
        for entry in resource_archives
        if isinstance(entry, Mapping) and entry.get("path") == ARCHIVE_PATH
    ]
    if len(matching) != 1:
        raise ResourceArchiveError(
            f"sealed inventory must contain exactly one {ARCHIVE_PATH} record"
        )
    content_root = live_inventory.get("content_root")
    if type(content_root) is not str or not content_root:
        raise ResourceArchiveError("inventory.content_root must be text")
    root = install_root.expanduser().resolve()
    relative_content = PurePosixPath(content_root)
    if relative_content.is_absolute() or ".." in relative_content.parts:
        raise ResourceArchiveError("inventory.content_root is not canonical")
    archive = root.joinpath(
        *relative_content.parts,
        *PurePosixPath(ARCHIVE_PATH).parts,
    )
    if not archive.resolve().is_relative_to(root):
        raise ResourceArchiveError("resource archive escapes the installation root")
    return archive, identity, matching[0]


def scan_resource_archive(archive: Path) -> dict[str, Any]:
    """Parse, hash, and structurally validate an archive without extracting it."""
    if archive.is_symlink() or not archive.is_file():
        raise ResourceArchiveError(
            f"archive is not a regular non-symlink file: {archive}"
        )
    path_before = archive.stat()
    archive_digest = hashlib.sha256()
    records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    seen_casefolded_paths: set[str] = set()

    with archive.open("rb") as stream:
        handle_before = os.fstat(stream.fileno())
        _require_same_file(path_before, handle_before, "archive")
        if handle_before.st_size > MAX_ARCHIVE_BYTES:
            raise ResourceArchiveError("archive exceeds the analysis size limit")
        archive_size = handle_before.st_size
        count_bytes = _read_exact(stream, 4, "entry count")
        archive_digest.update(count_bytes)
        (entry_count,) = struct.unpack("<I", count_bytes)
        if entry_count < 1 or entry_count > MAX_ENTRY_COUNT:
            raise ResourceArchiveError(
                f"implausible resource entry count: {entry_count}"
            )
        table_bytes = _read_exact(stream, entry_count * 4, "offset table")
        archive_digest.update(table_bytes)
        offsets = list(struct.unpack(f"<{entry_count}I", table_bytes))
        table_end = 4 + entry_count * 4
        if offsets[0] != table_end:
            raise ResourceArchiveError("first record does not begin after the table")
        if any(left >= right for left, right in zip(offsets, offsets[1:])):
            raise ResourceArchiveError("record offsets are not strictly increasing")
        if offsets[-1] >= archive_size:
            raise ResourceArchiveError("final record offset is outside the archive")

        type_counts: Counter[str] = Counter()
        type_bytes: Counter[str] = Counter()
        for ordinal, record_offset in enumerate(offsets):
            expected_offset = stream.tell()
            if record_offset != expected_offset:
                raise ResourceArchiveError(
                    f"record {ordinal} is not contiguous with the prior record"
                )
            header = _read_exact(stream, 8, f"record {ordinal} header")
            archive_digest.update(header)
            payload_size, path_size = struct.unpack("<II", header)
            if path_size < 1 or path_size > MAX_PATH_BYTES:
                raise ResourceArchiveError(
                    f"record {ordinal} has an invalid path size"
                )
            next_offset = (
                offsets[ordinal + 1] if ordinal + 1 < entry_count else archive_size
            )
            record_end = record_offset + 8 + path_size + payload_size
            if record_end != next_offset:
                raise ResourceArchiveError(
                    f"record {ordinal} span does not end at the next offset"
                )
            path_bytes = _read_exact(stream, path_size, f"record {ordinal} path")
            archive_digest.update(path_bytes)
            path = _validate_path(path_bytes, ordinal)
            if path in seen_paths or path.casefold() in seen_casefolded_paths:
                raise ResourceArchiveError(f"duplicate resource path: {path}")
            seen_paths.add(path)
            seen_casefolded_paths.add(path.casefold())

            payload_offset = stream.tell()
            payload_digest = hashlib.sha256()
            prefix = bytearray()
            remaining = payload_size
            while remaining:
                chunk = _read_exact(
                    stream,
                    min(_CHUNK_SIZE, remaining),
                    f"record {ordinal} payload",
                )
                if len(prefix) < 8:
                    prefix.extend(chunk[: 8 - len(prefix)])
                archive_digest.update(chunk)
                payload_digest.update(chunk)
                remaining -= len(chunk)
            extension, kind = _resource_kind(path, bytes(prefix))
            type_counts[kind] += 1
            type_bytes[kind] += payload_size
            records.append(
                {
                    "ordinal": ordinal,
                    "record_offset": record_offset,
                    "payload_offset": payload_offset,
                    "payload_size": payload_size,
                    "payload_sha256": payload_digest.hexdigest(),
                    "path": path,
                    "path_size": path_size,
                    "extension": extension,
                    "kind": kind,
                }
            )
        if stream.tell() != archive_size:
            raise ResourceArchiveError("archive has unaccounted trailing bytes")
        handle_after = os.fstat(stream.fileno())
        _require_same_file(handle_before, handle_after, "archive")

    path_after = archive.stat()
    _require_same_file(handle_after, path_after, "archive")
    return {
        "path": ARCHIVE_PATH,
        "size": archive_size,
        "sha256": archive_digest.hexdigest(),
        "entry_count": len(records),
        "records": records,
        "types": [
            {
                "kind": kind,
                "file_count": type_counts[kind],
                "payload_bytes": type_bytes[kind],
            }
            for kind in sorted(type_counts)
        ],
    }


def build_resource_inventory(
    install_root: Path,
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Build normalized metadata for one exact archive and build inventory."""
    archive, identity, sealed_archive = _attest_installation(
        install_root,
        inventory,
    )
    archive_facts = scan_resource_archive(archive)
    sealed_identity = {
        key: sealed_archive.get(key)
        for key in ("path", "size", "sha256")
    }
    observed_identity = {
        key: archive_facts.get(key)
        for key in ("path", "size", "sha256")
    }
    if observed_identity != sealed_identity:
        raise ResourceArchiveError(
            "resource archive does not match its sealed installation record"
        )
    records = archive_facts.pop("records")
    types = archive_facts.pop("types")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "identity": identity,
        "archive": archive_facts,
        "records": records,
        "summary": {
            "entry_count": len(records),
            "payload_bytes": sum(record["payload_size"] for record in records),
            "metadata_bytes": archive_facts["size"]
            - sum(record["payload_size"] for record in records),
            "types": types,
        },
        "method": _METHOD,
    }


def validate_resource_inventory(
    install_root: Path,
    evidence: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and compare the complete metadata inventory."""
    if not isinstance(evidence, Mapping):
        raise ResourceArchiveError("evidence must be an object")
    expected = build_resource_inventory(install_root, inventory=inventory)
    if evidence != expected:
        raise ResourceArchiveError(
            "resource inventory does not match the exact archive and build"
        )
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
        "identity": expected["identity"],
        "archive": expected["archive"],
        "evidence_sha256": hashlib.sha256(
            (canonical + "\n").encode("utf-8")
        ).hexdigest(),
        "summary": expected["summary"],
    }


def encode_resource_inventory(value: Mapping[str, Any]) -> str:
    """Encode inventory or verification output deterministically."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
