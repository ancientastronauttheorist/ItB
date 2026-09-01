#!/usr/bin/env python3
"""Build or verify exact native assertion-helper static-boundary evidence."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import stat
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from scripts.itb_native_lua_direct_calls import (  # noqa: E402
    _MAX_JSON_BYTES, _is_reparse, _object_without_duplicates, _read_json_document,
    _read_json_object, _reject_json_constant, _reject_json_float, _same_stat,
)
from scripts.itb_native_lua_property_factory_chain import _prepare_output_root, _recheck_output_root  # noqa: E402
from src.observatory.native_assertion_helper_static_boundary import (  # noqa: E402
    ANALYSIS_KIND, SCHEMA_VERSION, NativeAssertionHelperStaticBoundaryError, _canonical_bytes,
    build_native_assertion_helper_static_boundary, encode_native_assertion_helper_static_boundary,
    validate_native_assertion_helper_static_boundary, validate_native_assertion_helper_static_boundary_structure,
)
from src.observatory.native_lua_class_initializer_chain import NativeLuaClassInitializerChainError  # noqa: E402
from src.observatory.native_lua_cclosure_setfield_publications import NativeLuaCClosurePublicationError  # noqa: E402
from src.observatory.native_lua_direct_calls import NativeLuaDirectCallError  # noqa: E402
from src.observatory.native_lua_property_factory_chain import NativeLuaPropertyFactoryChainError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "verify-structure"):
        item = commands.add_parser(command)
        for name in ("class-initializer", "direct-calls", "program-facts"):
            item.add_argument("--" + name, required=True, type=Path)
        if command != "verify-structure":
            item.add_argument("--executable", required=True, type=Path)
            item.add_argument("--inventory", required=True, type=Path)
        if command == "build":
            item.add_argument("--output", type=Path)
        else:
            item.add_argument("--evidence", required=True, type=Path)
    return parser


def _initializer_identity(value: dict[str, Any]) -> str:
    candidate = value.get("class_initializer_chain")
    if not isinstance(candidate, dict) or type(candidate.get("canonical_sha256")) is not str:
        raise NativeAssertionHelperStaticBoundaryError("evidence lacks class-initializer identity")
    return candidate["canonical_sha256"]


def _identity(value: dict[str, Any]) -> bytes:
    if type(value.get("schema_version")) is not int or value.get("schema_version") != SCHEMA_VERSION or type(value.get("analysis_kind")) is not str or value.get("analysis_kind") != ANALYSIS_KIND:
        raise NativeAssertionHelperStaticBoundaryError("evidence has another schema or analysis kind")
    if not isinstance(value.get("build_identity"), dict):
        raise NativeAssertionHelperStaticBoundaryError("evidence lacks build identity")
    return _canonical_bytes({"schema_version": value["schema_version"], "analysis_kind": value["analysis_kind"], "build_identity": value["build_identity"], "class_initializer_canonical_sha256": _initializer_identity(value)})


def _regular_child(path: Path, root: Path, identity: tuple[int, int] | None = None) -> os.stat_result:
    value = path.lstat()
    if stat.S_ISLNK(value.st_mode) or _is_reparse(value) or not stat.S_ISREG(value.st_mode) or path.resolve(strict=True).parent != root or (identity is not None and (value.st_dev, value.st_ino) != identity):
        raise NativeAssertionHelperStaticBoundaryError("output failed regular-file identity check")
    return value


def _open_windows_guard(path: Path) -> tuple[int, Any]:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _Overlapped(ctypes.Structure):
        _fields_ = [
            ("Internal", ctypes.c_size_t),
            ("InternalHigh", ctypes.c_size_t),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    lock_file = kernel32.LockFileEx
    lock_file.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_Overlapped),
    ]
    lock_file.restype = wintypes.BOOL
    unlock_file = kernel32.UnlockFileEx
    unlock_file.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_Overlapped),
    ]
    unlock_file.restype = wintypes.BOOL

    handle = create_file(
        str(path),
        0x80000000,  # GENERIC_READ
        0x00000001,  # FILE_SHARE_READ: deny write and delete sharing
        None,
        3,  # OPEN_EXISTING
        0x00200000,  # FILE_FLAG_OPEN_REPARSE_POINT
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise OSError(ctypes.get_last_error(), "destination guard could not be opened")
    overlapped = _Overlapped()
    if not lock_file(handle, 0x00000003, 0, 0xFFFFFFFF, 0xFFFFFFFF, ctypes.byref(overlapped)):
        error = ctypes.get_last_error()
        close_handle(handle)
        raise OSError(error, "destination guard could not be locked")
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except Exception:
        unlock_file(handle, 0, 0xFFFFFFFF, 0xFFFFFFFF, ctypes.byref(overlapped))
        close_handle(handle)
        raise

    def release() -> None:
        try:
            if not unlock_file(handle, 0, 0xFFFFFFFF, 0xFFFFFFFF, ctypes.byref(overlapped)):
                raise OSError(ctypes.get_last_error(), "destination guard could not be unlocked")
        finally:
            os.close(descriptor)

    return descriptor, release


@contextmanager
def _locked_output(path: Path, root: Path, identity: tuple[int, int]) -> Iterator[int]:
    """Hold the output stable through one final point-in-time validation.

    Windows denies write/delete sharing and takes a mandatory full-range lock.
    POSIX uses an advisory exclusive lock, so its guarantee covers cooperating
    writers.  Neither platform claims perpetual immutability after release.
    """
    descriptor: int | None = None
    release = None
    try:
        if os.name == "nt":
            descriptor, release = _open_windows_guard(path)
        else:
            import fcntl

            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException:
                os.close(descriptor)
                descriptor = None
                raise
            locked_descriptor = descriptor

            def release() -> None:
                try:
                    fcntl.flock(locked_descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(locked_descriptor)

        handle = os.fstat(descriptor)
        child = _regular_child(path, root, identity)
        if not stat.S_ISREG(handle.st_mode) or (handle.st_dev, handle.st_ino) != identity or (child.st_dev, child.st_ino) != identity:
            raise NativeAssertionHelperStaticBoundaryError("locked output identity differs")
        yield descriptor
    except NativeAssertionHelperStaticBoundaryError:
        raise
    except OSError as exc:
        raise NativeAssertionHelperStaticBoundaryError("output could not be held for final validation") from exc
    finally:
        if release is not None:
            release()


def _read_locked_json_document(descriptor: int, label: str) -> tuple[dict[str, Any], bytes]:
    before = os.fstat(descriptor)
    if before.st_size > _MAX_JSON_BYTES:
        raise NativeAssertionHelperStaticBoundaryError(f"{label} exceeds the JSON size limit")
    os.lseek(descriptor, 0, os.SEEK_SET)
    payload = os.read(descriptor, before.st_size + 1)
    after = os.fstat(descriptor)
    if len(payload) != before.st_size or not _same_stat(before, after):
        raise NativeAssertionHelperStaticBoundaryError(f"{label} changed while being read")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
            parse_float=_reject_json_float,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeAssertionHelperStaticBoundaryError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise NativeAssertionHelperStaticBoundaryError(f"{label} must contain a JSON object")
    return value, payload


def _write_immutably(output: Path, rendered: str, value: dict[str, Any]) -> None:
    configured, resolved, before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured:
        raise NativeAssertionHelperStaticBoundaryError("output must be a direct child of data observatory programs")
    destination, expected, identity = resolved / output.name, rendered.encode("utf-8"), _identity(value)
    if os.path.lexists(destination):
        initial = _regular_child(destination, resolved)
        existing, payload = _read_json_document(destination, "existing output")
        final = _regular_child(destination, resolved, (initial.st_dev, initial.st_ino))
        _recheck_output_root(configured, resolved, before)
        if _identity(existing) != identity or _canonical_bytes(existing) != _canonical_bytes(value) or payload != expected:
            raise NativeAssertionHelperStaticBoundaryError("refusing to overwrite differing assertion boundary evidence")
        final_identity = (final.st_dev, final.st_ino)
        with _locked_output(destination, resolved, final_identity) as descriptor:
            _recheck_output_root(configured, resolved, before)
            final_value, final_payload = _read_locked_json_document(descriptor, "final existing output")
            if _identity(final_value) != identity or _canonical_bytes(final_value) != _canonical_bytes(value) or final_payload != expected:
                raise NativeAssertionHelperStaticBoundaryError("existing output changed during final content validation")
            _regular_child(destination, resolved, final_identity)
            _recheck_output_root(configured, resolved, before)
            return
    fd, name = tempfile.mkstemp(prefix="." + output.name + ".", suffix=".tmp", dir=resolved)
    temporary, linked, source_identity = Path(name), False, None
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        source = temporary.lstat()
        if stat.S_ISLNK(source.st_mode) or _is_reparse(source) or not stat.S_ISREG(source.st_mode):
            raise NativeAssertionHelperStaticBoundaryError("temporary output is not a real regular file")
        source_identity = (source.st_dev, source.st_ino)
        _recheck_output_root(configured, resolved, before)
        os.link(temporary, destination)
        linked = True
        _regular_child(destination, resolved, source_identity)
        _recheck_output_root(configured, resolved, before)
        temporary.unlink()
        _regular_child(destination, resolved, source_identity)
        _recheck_output_root(configured, resolved, before)
        with _locked_output(destination, resolved, source_identity) as descriptor:
            _recheck_output_root(configured, resolved, before)
            final_value, final_payload = _read_locked_json_document(descriptor, "final created output")
            if _identity(final_value) != identity or _canonical_bytes(final_value) != _canonical_bytes(value) or final_payload != expected:
                raise NativeAssertionHelperStaticBoundaryError("created output changed during final content validation")
            _regular_child(destination, resolved, source_identity)
            _recheck_output_root(configured, resolved, before)
            return
    except Exception:
        if linked and source_identity is not None:
            try:
                created = destination.lstat()
                if (created.st_dev, created.st_ino) == source_identity:
                    destination.unlink()
            except FileNotFoundError:
                pass
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        get = lambda name: _read_json_object(getattr(args, name.replace("-", "_")), name)
        initializer, direct, facts = (get(name) for name in ("class-initializer", "direct-calls", "program-facts"))
        common = (initializer, direct, facts)
        if args.command == "build":
            result = build_native_assertion_helper_static_boundary(args.executable, *common, inventory=get("inventory"))
            rendered = encode_native_assertion_helper_static_boundary(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_immutably(args.output, rendered, result)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode_native_assertion_helper_static_boundary(evidence).encode("utf-8"):
                raise NativeAssertionHelperStaticBoundaryError("evidence is not deterministically encoded")
            if args.command == "verify":
                result = validate_native_assertion_helper_static_boundary(args.executable, evidence, *common, inventory=get("inventory"))
            else:
                result = validate_native_assertion_helper_static_boundary_structure(evidence, *common)
            sys.stdout.write(encode_native_assertion_helper_static_boundary(result))
        return 0
    except (NativeAssertionHelperStaticBoundaryError, NativeLuaClassInitializerChainError, NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaPropertyFactoryChainError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
