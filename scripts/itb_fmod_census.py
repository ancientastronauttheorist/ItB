#!/usr/bin/env python3
"""Build or verify a payload-free ITB FMOD bank/native interface census."""

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
_OUTPUT_ROOT = _REPO_ROOT / "data" / "observatory" / "fmod"
_MAX_JSON_BYTES = 64 * 1024 * 1024
_STABLE_STAT_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
_DIRECTORY_ID_FIELDS = ("st_dev", "st_ino")
sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.fmod_census import (  # noqa: E402
    ANALYSIS_KIND,
    FmodCensusError,
    build_fmod_census,
    encode_fmod_census,
    validate_fmod_census,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="census one sealed installation")
    build.add_argument("--install-dir", required=True, type=Path)
    build.add_argument("--inventory", required=True, type=Path)
    build.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify", help="verify committed evidence")
    verify.add_argument("--install-dir", required=True, type=Path)
    verify.add_argument("--inventory", required=True, type=Path)
    verify.add_argument("--evidence", required=True, type=Path)
    return parser


def _reject_json_constant(value: str) -> None:
    raise FmodCensusError(f"invalid JSON constant: {value}")


def _reject_json_float(value: str) -> None:
    raise FmodCensusError(f"floating-point JSON values are unsupported: {value}")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FmodCensusError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _is_reparse(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & marker)


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        link_before = path.lstat()
        before = path.stat()
    except OSError as exc:
        raise FmodCensusError(f"{label} is not a readable regular file") from exc
    if (
        stat.S_ISLNK(link_before.st_mode)
        or _is_reparse(link_before)
        or not stat.S_ISREG(before.st_mode)
    ):
        raise FmodCensusError(f"{label} is not a regular non-link file")
    if before.st_size > _MAX_JSON_BYTES:
        raise FmodCensusError(f"{label} exceeds the JSON size limit")
    try:
        with path.open("rb") as stream:
            handle_before = os.fstat(stream.fileno())
            if any(
                getattr(before, field) != getattr(handle_before, field)
                for field in _STABLE_STAT_FIELDS
            ):
                raise FmodCensusError(f"{label} changed while being opened")
            payload = stream.read(handle_before.st_size + 1)
            handle_after = os.fstat(stream.fileno())
    except OSError as exc:
        raise FmodCensusError(f"{label} could not be read") from exc
    after = path.stat()
    link_after = path.lstat()
    if (
        any(
            getattr(handle_before, field) != getattr(handle_after, field)
            or getattr(handle_after, field) != getattr(after, field)
            or getattr(link_before, field) != getattr(link_after, field)
            for field in _STABLE_STAT_FIELDS
        )
        or stat.S_ISLNK(link_after.st_mode)
        or _is_reparse(link_after)
        or len(payload) != handle_before.st_size
    ):
        raise FmodCensusError(f"{label} changed while being read")
    value = json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_object_without_duplicates,
        parse_constant=_reject_json_constant,
        parse_float=_reject_json_float,
    )
    if not isinstance(value, dict):
        raise FmodCensusError(f"{label} must contain a JSON object")
    return value


def _prepare_output_root() -> tuple[Path, Path, os.stat_result]:
    repo_root = Path(os.path.abspath(_REPO_ROOT))
    configured_root = Path(os.path.abspath(_OUTPUT_ROOT))
    expected_root = repo_root / "data" / "observatory" / "fmod"
    if configured_root != expected_root:
        raise FmodCensusError("configured FMOD output root is not repository-local")
    try:
        repo_info = repo_root.lstat()
    except OSError as exc:
        raise FmodCensusError("repository root is not a readable directory") from exc
    if (
        stat.S_ISLNK(repo_info.st_mode)
        or _is_reparse(repo_info)
        or not stat.S_ISDIR(repo_info.st_mode)
    ):
        raise FmodCensusError("repository root is not a real directory")

    current = repo_root
    for part in ("data", "observatory", "fmod"):
        current /= part
        try:
            current.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise FmodCensusError("cannot create FMOD output directory") from exc
        try:
            info = current.lstat()
        except OSError as exc:
            raise FmodCensusError("cannot inspect FMOD output directory") from exc
        if (
            stat.S_ISLNK(info.st_mode)
            or _is_reparse(info)
            or not stat.S_ISDIR(info.st_mode)
        ):
            raise FmodCensusError(
                "FMOD output directory chain contains a link/reparse entry"
            )
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(repo_root.resolve(strict=True)):
        raise FmodCensusError("FMOD output directory escapes the repository")
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
        raise FmodCensusError("FMOD output directory changed during writing") from exc
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
        raise FmodCensusError("FMOD output directory changed during writing")


def _write_evidence_atomically(output: Path, rendered: str) -> None:
    configured_root, output_root, root_before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured_root:
        raise FmodCensusError("output must be a direct child of data/observatory/fmod")
    destination = output_root / output.name
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise FmodCensusError("refusing to replace non-regular output")
        try:
            existing = _read_json_object(destination, "existing output")
        except (
            FmodCensusError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise FmodCensusError(
                "refusing to replace an existing non-FMOD-census artifact"
            ) from exc
        if existing.get("analysis_kind") != ANALYSIS_KIND:
            raise FmodCensusError(
                "refusing to replace an existing non-FMOD-census artifact"
            )

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
        os.replace(temporary_name, destination)
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
        if args.command == "build":
            result = build_fmod_census(args.install_dir, inventory=inventory)
            rendered = encode_fmod_census(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_evidence_atomically(args.output, rendered)
        else:
            evidence = _read_json_object(args.evidence, "evidence")
            result = validate_fmod_census(
                args.install_dir,
                evidence,
                inventory=inventory,
            )
            sys.stdout.write(encode_fmod_census(result))
        return 0
    except (
        FmodCensusError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
