"""Deterministic, read-only inventories of Into the Breach installations.

The inventory intentionally records content bytes rather than filesystem
timestamps.  This keeps snapshots stable across repeated runs and makes hashes,
not filenames or sizes, the basis for cross-platform comparisons.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform as host_platform
import re
import struct
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


APP_ID = "590380"
SCHEMA_VERSION = 1
CONTENT_DIRS = ("scripts", "maps")
NATIVE_SUFFIXES = (".dll", ".dylib", ".so")


class InventoryError(RuntimeError):
    """Raised when a requested installation cannot be inventoried safely."""


_STABLE_STAT_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns")


def _require_stable_file(
    path: Path,
    before: os.stat_result,
    after: os.stat_result,
) -> None:
    if any(
        getattr(before, field) != getattr(after, field)
        for field in _STABLE_STAT_FIELDS
    ):
        raise InventoryError(f"file changed while it was being inventoried: {path}")


def normalize_platform(value: str | None = None) -> str:
    """Return one of ``windows``, ``macos``, or ``linux``."""
    raw = (value or host_platform.system()).strip().lower()
    aliases = {
        "darwin": "macos",
        "mac": "macos",
        "macos": "macos",
        "linux": "linux",
        "win32": "windows",
        "windows": "windows",
    }
    try:
        return aliases[raw]
    except KeyError as exc:
        raise InventoryError(f"unsupported platform: {value!r}") from exc


def _path_key(path: Path) -> tuple[str, str]:
    normalized = path.as_posix()
    return normalized.casefold(), normalized


def _stable_file_fingerprint(
    path: Path,
    chunk_size: int = 1024 * 1024,
) -> tuple[str, os.stat_result]:
    """Return one hash/stat snapshot or reject a concurrent mutation."""
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    after = path.stat()
    _require_stable_file(path, before, after)
    return digest.hexdigest(), after


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash *path* without opening it for writing."""
    digest, _ = _stable_file_fingerprint(path, chunk_size)
    return digest


def _revision_hash(files: Sequence[Mapping[str, Any]]) -> str:
    """Hash a canonical manifest, including names, sizes, and content hashes."""
    digest = hashlib.sha256()
    for entry in files:
        digest.update(str(entry["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(entry["size"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(entry["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def build_manifest(content_root: Path, directory: str) -> dict[str, Any]:
    """Return a normalized SHA-256 manifest for one content directory."""
    root = content_root / directory
    entries: list[dict[str, Any]] = []
    if root.is_dir():
        paths = _contained_regular_files(root, content_root)
        for path in paths:
            sha256, stable_stat = _stable_file_fingerprint(path)
            entries.append(
                {
                    "path": path.relative_to(content_root).as_posix(),
                    "size": stable_stat.st_size,
                    "sha256": sha256,
                }
            )
    return {
        "root": directory,
        "file_count": len(entries),
        "byte_count": sum(entry["size"] for entry in entries),
        "revision_sha256": _revision_hash(entries),
        "files": entries,
    }


def resolve_content_root(install_root: Path) -> Path:
    """Locate the directory containing the shipped ``scripts`` and ``maps``."""
    candidates = [install_root]
    candidates.extend(
        sorted(
            install_root.glob("*.app/Contents/Resources"),
            key=_path_key,
        )
    )
    containment = install_root.resolve()
    for candidate in candidates:
        if not candidate.resolve().is_relative_to(containment):
            continue
        if all(
            (candidate / name).is_dir()
            and (candidate / name).resolve().is_relative_to(containment)
            for name in CONTENT_DIRS
        ):
            return candidate
    raise InventoryError(
        f"{install_root} does not contain scripts/ and maps/ directly or in "
        "an app bundle"
    )


def _machine_name(machine: int) -> str:
    return {
        0x014C: "x86",
        0x8664: "x86_64",
        0x01C0: "arm",
        0x01C4: "armv7",
        0xAA64: "arm64",
    }.get(machine, f"machine_0x{machine:04x}")


def _macho_cpu_name(cpu_type: int) -> str:
    return {
        7: "x86",
        0x01000007: "x86_64",
        12: "arm",
        0x0100000C: "arm64",
    }.get(cpu_type, f"cpu_0x{cpu_type:08x}")


def inspect_executable_format(path: Path) -> dict[str, Any] | None:
    """Identify PE, ELF, and Mach-O binaries using their headers."""
    with path.open("rb") as stream:
        header = stream.read(4096)
    if len(header) >= 64 and header[:2] == b"MZ":
        pe_offset = struct.unpack_from("<I", header, 0x3C)[0]
        with path.open("rb") as stream:
            stream.seek(pe_offset)
            pe_header = stream.read(6)
        if len(pe_header) == 6 and pe_header[:4] == b"PE\0\0":
            machine = struct.unpack_from("<H", pe_header, 4)[0]
            return {"format": "pe", "architecture": _machine_name(machine)}
    if len(header) >= 20 and header[:4] == b"\x7fELF":
        byte_order = "<" if header[5] == 1 else ">"
        machine = struct.unpack_from(f"{byte_order}H", header, 18)[0]
        arch = {
            3: "x86",
            40: "arm",
            62: "x86_64",
            183: "arm64",
        }.get(machine, f"machine_{machine}")
        bits = {1: 32, 2: 64}.get(header[4])
        return {"format": "elf", "architecture": arch, "bits": bits}

    magics = {
        b"\xfe\xed\xfa\xce": (">", 32),
        b"\xce\xfa\xed\xfe": ("<", 32),
        b"\xfe\xed\xfa\xcf": (">", 64),
        b"\xcf\xfa\xed\xfe": ("<", 64),
    }
    if header[:4] in magics and len(header) >= 8:
        byte_order, bits = magics[header[:4]]
        cpu_type = struct.unpack_from(f"{byte_order}I", header, 4)[0]
        arch = _macho_cpu_name(cpu_type)
        return {"format": "mach-o", "architecture": arch, "bits": bits}
    fat_magics = {
        b"\xca\xfe\xba\xbe": (">", 20, "mach-o-fat"),
        b"\xbe\xba\xfe\xca": ("<", 20, "mach-o-fat"),
        b"\xca\xfe\xba\xbf": (">", 32, "mach-o-fat64"),
        b"\xbf\xba\xfe\xca": ("<", 32, "mach-o-fat64"),
    }
    if header[:4] in fat_magics and len(header) >= 8:
        byte_order, record_size, format_name = fat_magics[header[:4]]
        count = struct.unpack_from(f"{byte_order}I", header, 4)[0]
        required = 8 + count * record_size
        with path.open("rb") as stream:
            fat_header = stream.read(required)
        if count == 0 or len(fat_header) < required:
            return None
        architectures = []
        for index in range(count):
            cpu_type = struct.unpack_from(
                f"{byte_order}I",
                fat_header,
                8 + index * record_size,
            )[0]
            architectures.append(_macho_cpu_name(cpu_type))
        return {
            "format": format_name,
            "architecture": "universal",
            "architectures": architectures,
        }
    return None


def _contained_regular_files(scan_root: Path, containment_root: Path) -> list[Path]:
    """Return stable files without following symlinks outside the install."""
    containment = containment_root.resolve()
    paths: list[Path] = []
    for path in scan_root.rglob("*"):
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(containment):
            raise InventoryError(f"file escapes installation root: {path} -> {resolved}")
        paths.append(path)
    return sorted(paths, key=_path_key)


def _relative_record(
    path: Path,
    install_root: Path,
    *,
    inspection_stat: os.stat_result | None = None,
) -> dict[str, Any]:
    try:
        relative = path.relative_to(install_root).as_posix()
    except ValueError:
        relative = path.name
    sha256, stable_stat = _stable_file_fingerprint(path)
    if inspection_stat is not None:
        _require_stable_file(path, inspection_stat, stable_stat)
    return {
        "path": relative,
        "size": stable_stat.st_size,
        "sha256": sha256,
    }


def find_executable(install_root: Path, platform_name: str | None = None) -> Path:
    """Find the primary game executable without relying on execute bits."""
    preferred_by_platform = {
        "windows": ("Breach.exe",),
        "macos": (
            "Into the Breach.app/Contents/MacOS/Into the Breach",
            "Into the Breach.app/Contents/MacOS/Breach",
        ),
        "linux": ("Breach", "IntoTheBreach", "Into the Breach"),
    }
    if platform_name is None:
        preferred = tuple(
            path
            for name in ("windows", "macos", "linux")
            for path in preferred_by_platform[name]
        )
    else:
        preferred = preferred_by_platform[normalize_platform(platform_name)]
    for relative in preferred:
        candidate = install_root / relative
        if (
            not candidate.is_symlink()
            and candidate.is_file()
            and candidate.resolve().is_relative_to(install_root.resolve())
        ):
            return candidate

    candidates: list[Path] = []
    for path in _contained_regular_files(install_root, install_root):
        if path.suffix.lower() in NATIVE_SUFFIXES or ".so." in path.name.lower():
            continue
        try:
            if inspect_executable_format(path) is not None:
                candidates.append(path)
        except OSError:
            continue
    if not candidates:
        raise InventoryError(f"no native executable found under {install_root}")
    return sorted(candidates, key=_path_key)[0]


def inventory_native_libraries(
    install_root: Path,
    *,
    exclude: Path | None = None,
) -> list[dict[str, Any]]:
    """Hash native shared libraries shipped inside the installation."""
    libraries: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    excluded = exclude.resolve() if exclude is not None else None
    for path in _contained_regular_files(install_root, install_root):
        if excluded is not None and path.resolve() == excluded:
            continue
        inspection_stat = path.stat()
        lower_name = path.name.lower()
        named_library = path.suffix.lower() in NATIVE_SUFFIXES or ".so." in lower_name
        binary_format = inspect_executable_format(path)
        if named_library or binary_format is not None:
            libraries.append(
                (
                    path,
                    _relative_record(
                        path,
                        install_root,
                        inspection_stat=inspection_stat,
                    ),
                    binary_format or {"format": "unknown", "architecture": "unknown"},
                )
            )
    return [
        {
            **record,
            **binary_format,
        }
        for path, record, binary_format in sorted(
            libraries,
            key=lambda item: _path_key(item[0]),
        )
    ]


_VDF_TOKEN = re.compile(r'"((?:\\.|[^"])*)"|([{}])')


def parse_vdf(text: str) -> dict[str, Any]:
    """Parse the brace-and-quoted-string subset used by Steam VDF files."""
    tokens: list[str] = []
    for match in _VDF_TOKEN.finditer(text):
        quoted, brace = match.groups()
        if brace:
            tokens.append(brace)
        else:
            tokens.append(quoted.replace(r"\\", "\\").replace(r"\"", '"'))

    def parse_object(index: int, expect_close: bool) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        while index < len(tokens):
            token = tokens[index]
            if token == "}":
                if not expect_close:
                    raise InventoryError("unexpected VDF closing brace")
                return result, index + 1
            if token == "{":
                raise InventoryError("unexpected VDF opening brace")
            key = token
            index += 1
            if index >= len(tokens):
                raise InventoryError(f"missing VDF value for {key!r}")
            if tokens[index] == "{":
                value, index = parse_object(index + 1, True)
            else:
                if tokens[index] == "}":
                    raise InventoryError(f"missing VDF value for {key!r}")
                value = tokens[index]
                index += 1
            result[key] = value
        if expect_close:
            raise InventoryError("unterminated VDF object")
        return result, index

    parsed, final_index = parse_object(0, False)
    if final_index != len(tokens):
        raise InventoryError("trailing VDF tokens")
    return parsed


def _steamapps_ancestor(path: Path) -> Path | None:
    for ancestor in (path, *path.parents):
        if ancestor.name.casefold() == "steamapps":
            return ancestor
    return None


def read_steam_evidence(install_root: Path) -> dict[str, Any] | None:
    """Read stable build/depot evidence from the adjacent Steam manifest."""
    steamapps = _steamapps_ancestor(install_root)
    if steamapps is None:
        return None
    manifest_path = steamapps / f"appmanifest_{APP_ID}.acf"
    if not manifest_path.is_file():
        return None
    parsed = parse_vdf(manifest_path.read_text(encoding="utf-8-sig", errors="strict"))
    state = parsed.get("AppState")
    if not isinstance(state, Mapping) or state.get("appid") != APP_ID:
        raise InventoryError(f"unexpected app manifest schema: {manifest_path}")
    expected_root = steamapps / "common" / str(state.get("installdir", ""))
    if expected_root.resolve() != install_root.resolve():
        raise InventoryError(
            "Steam app manifest does not describe the inventoried directory: "
            f"{expected_root} != {install_root}"
        )
    depots = state.get("InstalledDepots", {})
    installed_depots = []
    if isinstance(depots, Mapping):
        for depot_id, value in sorted(depots.items()):
            if isinstance(value, Mapping):
                installed_depots.append(
                    {
                        "depot_id": str(depot_id),
                        "manifest": value.get("manifest"),
                        "size": int(value["size"]) if str(value.get("size", "")).isdigit() else None,
                    }
                )
    return {
        "app_id": APP_ID,
        "evidence": {
            "path": manifest_path.name,
            "sha256": sha256_file(manifest_path),
        },
        "build_id": state.get("buildid"),
        "install_dir_name": state.get("installdir"),
        "last_updated_epoch": (
            int(state["LastUpdated"]) if str(state.get("LastUpdated", "")).isdigit() else None
        ),
        "size_on_disk": (
            int(state["SizeOnDisk"]) if str(state.get("SizeOnDisk", "")).isdigit() else None
        ),
        "installed_depots": installed_depots,
    }


def create_inventory(
    install_root: Path,
    *,
    platform_name: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Inventory an installation without mutating it."""
    root = install_root.expanduser().resolve()
    if not root.is_dir():
        raise InventoryError(f"installation directory does not exist: {root}")
    content_root = resolve_content_root(root)
    requested_platform = normalize_platform(platform_name) if platform_name else None
    executable_path = find_executable(root, requested_platform)
    executable_inspection_stat = executable_path.stat()
    executable_format = inspect_executable_format(executable_path)
    if executable_format is None:
        raise InventoryError(f"unrecognized executable format: {executable_path}")
    build_platform = {
        "pe": "windows",
        "elf": "linux",
        "mach-o": "macos",
        "mach-o-fat": "macos",
        "mach-o-fat64": "macos",
    }[executable_format["format"]]
    if requested_platform is not None and requested_platform != build_platform:
        raise InventoryError(
            f"requested {requested_platform} build but executable is "
            f"{executable_format['format']} ({build_platform})"
        )
    executable = {
        **_relative_record(
            executable_path,
            root,
            inspection_stat=executable_inspection_stat,
        ),
        **executable_format,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "app_id": APP_ID,
        "platform": build_platform,
        "label": label,
        "content_root": content_root.relative_to(root).as_posix() or ".",
        "executable": executable,
        "native_libraries": inventory_native_libraries(root, exclude=executable_path),
        "steam": read_steam_evidence(root),
        "content": {
            name: build_manifest(content_root, name)
            for name in CONTENT_DIRS
        },
    }


def _candidate_steam_roots(platform_name: str, environ: Mapping[str, str]) -> list[Path]:
    home = Path(environ.get("USERPROFILE") or environ.get("HOME") or Path.home())
    if platform_name == "windows":
        roots = [
            Path(environ["PROGRAMFILES(X86)"]) / "Steam"
            if environ.get("PROGRAMFILES(X86)")
            else None,
            Path(environ["PROGRAMFILES"]) / "Steam"
            if environ.get("PROGRAMFILES")
            else None,
        ]
    elif platform_name == "macos":
        roots = [home / "Library/Application Support/Steam"]
    else:
        roots = [
            home / ".local/share/Steam",
            home / ".steam/steam",
            Path(environ["XDG_DATA_HOME"]) / "Steam"
            if environ.get("XDG_DATA_HOME")
            else None,
        ]
    return [root for root in roots if root is not None]


def _library_paths(steam_root: Path) -> Iterable[Path]:
    yield steam_root
    libraries = steam_root / "steamapps/libraryfolders.vdf"
    if not libraries.is_file():
        return
    try:
        parsed = parse_vdf(libraries.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, InventoryError):
        return
    folders = parsed.get("libraryfolders", {})
    if not isinstance(folders, Mapping):
        return
    for entry in folders.values():
        if isinstance(entry, Mapping) and isinstance(entry.get("path"), str):
            yield Path(entry["path"])


def detect_installations(
    *,
    platform_name: str | None = None,
    environ: Mapping[str, str] | None = None,
    extra_steam_roots: Sequence[Path] = (),
) -> list[Path]:
    """Detect Steam installations on Windows, macOS, and Linux.

    Registry discovery is intentionally left to the thin CLI layer so this
    module remains portable and straightforward to test.
    """
    normalized_platform = normalize_platform(platform_name)
    environment = environ if environ is not None else os.environ
    steam_roots = [
        *_candidate_steam_roots(normalized_platform, environment),
        *extra_steam_roots,
    ]
    found: dict[str, Path] = {}
    for steam_root in steam_roots:
        for library in _library_paths(steam_root):
            steamapps = library if library.name.casefold() == "steamapps" else library / "steamapps"
            manifest = steamapps / f"appmanifest_{APP_ID}.acf"
            if not manifest.is_file():
                continue
            try:
                state = parse_vdf(manifest.read_text(encoding="utf-8-sig"))["AppState"]
                if not isinstance(state, Mapping):
                    continue
                if state.get("appid") != APP_ID:
                    continue
                install_name = state["installdir"]
            except (OSError, UnicodeError, InventoryError, KeyError, TypeError):
                continue
            candidate = steamapps / "common" / str(install_name)
            if candidate.is_dir():
                resolved = candidate.resolve()
                found[str(resolved).casefold()] = resolved
    return sorted(found.values(), key=_path_key)


def _manifest_entries(inventory: Mapping[str, Any], collection: str) -> dict[str, Mapping[str, Any]]:
    if collection in CONTENT_DIRS:
        raw = inventory.get("content", {}).get(collection, {}).get("files", [])
    elif collection == "native_libraries":
        raw = inventory.get("native_libraries", [])
    elif collection == "executable":
        executable = inventory.get("executable")
        raw = [executable] if isinstance(executable, Mapping) else []
    else:
        raise InventoryError(f"unknown comparison collection: {collection}")
    return {
        str(entry["path"]): entry
        for entry in raw
        if isinstance(entry, Mapping) and "path" in entry
    }


def compare_inventories(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify inventory entries by content hash.

    A native file that exists on only one of two different platforms is
    ``platform_specific``.  Missing Lua or map content remains ``missing``:
    cross-platform provenance must not silently excuse a mechanics gap.
    """
    results: list[dict[str, Any]] = []
    platforms_differ = left.get("platform") != right.get("platform")
    for collection in (*CONTENT_DIRS, "executable", "native_libraries"):
        left_entries = _manifest_entries(left, collection)
        right_entries = _manifest_entries(right, collection)
        for path in sorted(set(left_entries) | set(right_entries), key=lambda item: (item.casefold(), item)):
            left_entry = left_entries.get(path)
            right_entry = right_entries.get(path)
            if left_entry is not None and right_entry is not None:
                status = (
                    "identical"
                    if left_entry.get("sha256") == right_entry.get("sha256")
                    else "changed"
                )
            elif platforms_differ and collection in {"executable", "native_libraries"}:
                status = "platform_specific"
            else:
                status = "missing"
            results.append(
                {
                    "collection": collection,
                    "path": path,
                    "status": status,
                    "present_in": (
                        "both"
                        if left_entry is not None and right_entry is not None
                        else "left"
                        if left_entry is not None
                        else "right"
                    ),
                    "left_sha256": left_entry.get("sha256") if left_entry else None,
                    "right_sha256": right_entry.get("sha256") if right_entry else None,
                }
            )
    summary = {
        status: sum(1 for entry in results if entry["status"] == status)
        for status in ("identical", "changed", "missing", "platform_specific")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "left": {
            "platform": left.get("platform"),
            "label": left.get("label"),
            "executable_sha256": left.get("executable", {}).get("sha256"),
            "build_id": (left.get("steam") or {}).get("build_id"),
        },
        "right": {
            "platform": right.get("platform"),
            "label": right.get("label"),
            "executable_sha256": right.get("executable", {}).get("sha256"),
            "build_id": (right.get("steam") or {}).get("build_id"),
        },
        "summary": summary,
        "entries": results,
    }


def write_json(data: Mapping[str, Any], path: Path | None = None) -> str:
    """Serialize with stable ordering and optionally write the result."""
    rendered = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")
    return rendered
