#!/usr/bin/env python3
"""Build or verify exact direct Lua 5.1 import calls in native atlas bodies."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT_ROOT = _REPO_ROOT / "data" / "observatory" / "programs"
_MAX_JSON_BYTES = 256 * 1024 * 1024
_STABLE_STAT_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
_DIRECTORY_ID_FIELDS = ("st_dev", "st_ino")
sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.native_lua_direct_calls import (  # noqa: E402
    ANALYSIS_KIND,
    NativeLuaDirectCallError,
    _canonical_bytes,
    build_native_lua_direct_call_census,
    encode_native_lua_direct_call_census,
    validate_native_lua_direct_call_census,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build the exact call census")
    build.add_argument("--executable", required=True, type=Path)
    build.add_argument("--inventory", required=True, type=Path)
    build.add_argument("--program-facts", required=True, type=Path)
    build.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify", help="verify committed evidence")
    verify.add_argument("--executable", required=True, type=Path)
    verify.add_argument("--inventory", required=True, type=Path)
    verify.add_argument("--program-facts", required=True, type=Path)
    verify.add_argument("--evidence", required=True, type=Path)
    return parser


def _reject_json_constant(value: str) -> None:
    raise NativeLuaDirectCallError(f"invalid JSON constant: {value}")


def _reject_json_float(value: str) -> None:
    raise NativeLuaDirectCallError(
        f"floating-point JSON values are unsupported: {value}"
    )


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise NativeLuaDirectCallError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _is_reparse(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & marker)


def _same_stat(left: os.stat_result, right: os.stat_result) -> bool:
    return all(
        getattr(left, field) == getattr(right, field)
        for field in _STABLE_STAT_FIELDS
    )


def _require_real_parent_chain(
    path: Path,
    label: str,
) -> list[tuple[Path, os.stat_result]]:
    current = Path(os.path.abspath(path)).parent
    chain: list[tuple[Path, os.stat_result]] = []
    while True:
        try:
            info = current.lstat()
        except OSError as exc:
            raise NativeLuaDirectCallError(
                f"{label} parent chain cannot be inspected"
            ) from exc
        if (
            stat.S_ISLNK(info.st_mode)
            or _is_reparse(info)
            or not stat.S_ISDIR(info.st_mode)
        ):
            raise NativeLuaDirectCallError(
                f"{label} parent chain contains a link/reparse entry"
            )
        chain.append((current, info))
        parent = current.parent
        if parent == current:
            return chain
        current = parent


def _read_json_document(
    path: Path,
    label: str,
) -> tuple[dict[str, Any], bytes]:
    path = Path(os.path.abspath(path))
    parent_chain = _require_real_parent_chain(path, label)
    try:
        link_before = path.lstat()
        path_before = path.stat()
    except OSError as exc:
        raise NativeLuaDirectCallError(
            f"{label} is not a readable regular file"
        ) from exc
    if (
        stat.S_ISLNK(link_before.st_mode)
        or _is_reparse(link_before)
        or not stat.S_ISREG(path_before.st_mode)
    ):
        raise NativeLuaDirectCallError(f"{label} is not a regular non-link file")
    if path_before.st_size > _MAX_JSON_BYTES:
        raise NativeLuaDirectCallError(f"{label} exceeds the JSON size limit")
    try:
        with path.open("rb") as stream:
            handle_before = os.fstat(stream.fileno())
            if not _same_stat(path_before, handle_before):
                raise NativeLuaDirectCallError(f"{label} changed while being opened")
            payload = stream.read(handle_before.st_size + 1)
            handle_after = os.fstat(stream.fileno())
    except OSError as exc:
        raise NativeLuaDirectCallError(f"{label} could not be read") from exc
    try:
        path_after = path.stat()
        link_after = path.lstat()
    except OSError as exc:
        raise NativeLuaDirectCallError(f"{label} changed while being read") from exc
    parents_changed = False
    for parent, parent_before in parent_chain:
        try:
            parent_after = parent.lstat()
        except OSError:
            parents_changed = True
            break
        if (
            stat.S_ISLNK(parent_after.st_mode)
            or _is_reparse(parent_after)
            or not stat.S_ISDIR(parent_after.st_mode)
            or any(
                getattr(parent_before, field) != getattr(parent_after, field)
                for field in _DIRECTORY_ID_FIELDS
            )
        ):
            parents_changed = True
            break
    if (
        len(payload) != handle_before.st_size
        or parents_changed
        or not _same_stat(handle_before, handle_after)
        or not _same_stat(handle_after, path_after)
        or not _same_stat(link_before, link_after)
        or stat.S_ISLNK(link_after.st_mode)
        or _is_reparse(link_after)
    ):
        raise NativeLuaDirectCallError(f"{label} changed while being read")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
            parse_float=_reject_json_float,
        )
    except UnicodeError as exc:
        raise NativeLuaDirectCallError(f"{label} is not UTF-8") from exc
    if not isinstance(value, dict):
        raise NativeLuaDirectCallError(f"{label} must contain a JSON object")
    return value, payload


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    value, _payload = _read_json_document(path, label)
    return value


def _prepare_output_root() -> tuple[Path, Path, os.stat_result]:
    repo_root = Path(os.path.abspath(_REPO_ROOT))
    configured_root = Path(os.path.abspath(_OUTPUT_ROOT))
    expected_root = repo_root / "data" / "observatory" / "programs"
    if configured_root != expected_root:
        raise NativeLuaDirectCallError(
            "configured direct-call output root is not repository-local"
        )
    try:
        repo_info = repo_root.lstat()
    except OSError as exc:
        raise NativeLuaDirectCallError(
            "repository root is not a readable directory"
        ) from exc
    if (
        stat.S_ISLNK(repo_info.st_mode)
        or _is_reparse(repo_info)
        or not stat.S_ISDIR(repo_info.st_mode)
    ):
        raise NativeLuaDirectCallError("repository root is not a real directory")
    current = repo_root
    for part in ("data", "observatory", "programs"):
        current /= part
        try:
            current.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise NativeLuaDirectCallError(
                "cannot create direct-call output directory"
            ) from exc
        try:
            info = current.lstat()
        except OSError as exc:
            raise NativeLuaDirectCallError(
                "cannot inspect direct-call output directory"
            ) from exc
        if (
            stat.S_ISLNK(info.st_mode)
            or _is_reparse(info)
            or not stat.S_ISDIR(info.st_mode)
        ):
            raise NativeLuaDirectCallError(
                "direct-call output chain contains a link/reparse entry"
            )
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(repo_root.resolve(strict=True)):
        raise NativeLuaDirectCallError(
            "direct-call output directory escapes the repository"
        )
    return current, resolved, current.stat()


def _recheck_output_root(
    configured: Path,
    resolved: Path,
    expected: os.stat_result,
) -> None:
    try:
        link_info = configured.lstat()
        path_info = configured.stat()
        current_resolved = configured.resolve(strict=True)
    except OSError as exc:
        raise NativeLuaDirectCallError(
            "direct-call output directory changed during writing"
        ) from exc
    if (
        stat.S_ISLNK(link_info.st_mode)
        or _is_reparse(link_info)
        or not stat.S_ISDIR(path_info.st_mode)
        or current_resolved != resolved
        or any(
            getattr(path_info, field) != getattr(expected, field)
            for field in _DIRECTORY_ID_FIELDS
        )
    ):
        raise NativeLuaDirectCallError(
            "direct-call output directory changed during writing"
        )


def _replacement_identity(value: dict[str, Any], label: str) -> tuple[bytes, str]:
    if value.get("analysis_kind") != ANALYSIS_KIND:
        raise NativeLuaDirectCallError(f"{label} has another analysis kind")
    identity = value.get("build_identity")
    atlas = value.get("atlas")
    if not isinstance(identity, dict) or not isinstance(atlas, dict):
        raise NativeLuaDirectCallError(f"{label} lacks replacement identity")
    atlas_sha = atlas.get("canonical_sha256")
    if type(atlas_sha) is not str:
        raise NativeLuaDirectCallError(f"{label} lacks atlas identity")
    return _canonical_bytes(identity), atlas_sha


def _write_evidence_atomically(
    output: Path,
    rendered: str,
    result: dict[str, Any],
) -> None:
    configured_root, output_root, root_before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured_root:
        raise NativeLuaDirectCallError(
            "output must be a direct child of data/observatory/programs"
        )
    destination = output_root / output.name
    new_identity = _replacement_identity(result, "new evidence")
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise NativeLuaDirectCallError("refusing to replace non-regular output")
        try:
            existing, existing_payload = _read_json_document(
                destination, "existing output"
            )
            existing_identity = _replacement_identity(existing, "existing output")
        except (NativeLuaDirectCallError, json.JSONDecodeError) as exc:
            raise NativeLuaDirectCallError(
                "refusing to replace an unrelated direct-call artifact"
            ) from exc
        if existing_identity != new_identity:
            raise NativeLuaDirectCallError(
                "refusing to replace evidence for another build or atlas"
            )
        if _canonical_bytes(existing) != _canonical_bytes(result):
            raise NativeLuaDirectCallError(
                "refusing to overwrite differing direct-call evidence"
            )
        expected_payload = rendered.encode("utf-8")
        if existing_payload != expected_payload:
            raise NativeLuaDirectCallError(
                "existing direct-call evidence is not deterministically encoded"
            )
        confirmation, confirmation_payload = _read_json_document(
            destination, "existing output confirmation"
        )
        if (
            _canonical_bytes(confirmation) != _canonical_bytes(result)
            or confirmation_payload != expected_payload
        ):
            raise NativeLuaDirectCallError(
                "existing direct-call evidence changed during comparison"
            )
        _recheck_output_root(configured_root, output_root, root_before)
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=output_root,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        _recheck_output_root(configured_root, output_root, root_before)
        try:
            os.link(temporary_name, destination)
        except FileExistsError as exc:
            raise NativeLuaDirectCallError(
                "output appeared concurrently; refusing to overwrite it"
            ) from exc
        except OSError as exc:
            raise NativeLuaDirectCallError(
                "could not publish output without overwriting a destination"
            ) from exc
        os.unlink(temporary_name)
        _recheck_output_root(configured_root, output_root, root_before)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inventory = _read_json_object(args.inventory, "inventory")
        program_facts = _read_json_object(args.program_facts, "program facts")
        if args.command == "build":
            result = build_native_lua_direct_call_census(
                args.executable,
                program_facts,
                inventory=inventory,
            )
            rendered = encode_native_lua_direct_call_census(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_evidence_atomically(args.output, rendered, result)
        else:
            evidence, evidence_payload = _read_json_document(
                args.evidence, "evidence"
            )
            if evidence_payload != encode_native_lua_direct_call_census(
                evidence
            ).encode("utf-8"):
                raise NativeLuaDirectCallError(
                    "evidence is not deterministically encoded"
                )
            result = validate_native_lua_direct_call_census(
                args.executable,
                evidence,
                program_facts,
                inventory=inventory,
            )
            sys.stdout.write(encode_native_lua_direct_call_census(result))
        return 0
    except (
        NativeLuaDirectCallError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
