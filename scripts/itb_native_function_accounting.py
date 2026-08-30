#!/usr/bin/env python3
"""Build or verify an exact review ledger over the native function atlas."""

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
_MAX_JSON_BYTES = 512 * 1024 * 1024
_STABLE_STAT_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
_DIRECTORY_ID_FIELDS = ("st_dev", "st_ino")
sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.native_function_accounting import (  # noqa: E402
    ANALYSIS_KIND,
    SCHEMA_VERSION,
    NativeFunctionAccountingError,
    _canonical_bytes,
    build_native_function_accounting,
    encode_native_function_accounting,
    validate_native_function_accounting,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build the exact atlas ledger")
    build.add_argument("--executable", required=True, type=Path)
    build.add_argument("--inventory", required=True, type=Path)
    build.add_argument("--program-facts", required=True, type=Path)
    build.add_argument("--registry", required=True, type=Path)
    build.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify", help="verify a committed ledger")
    verify.add_argument("--executable", required=True, type=Path)
    verify.add_argument("--inventory", required=True, type=Path)
    verify.add_argument("--program-facts", required=True, type=Path)
    verify.add_argument("--registry", required=True, type=Path)
    verify.add_argument("--evidence", required=True, type=Path)
    return parser


def _reject_json_constant(value: str) -> None:
    raise NativeFunctionAccountingError(f"invalid JSON constant: {value}")


def _reject_json_float(value: str) -> None:
    raise NativeFunctionAccountingError(
        f"floating-point JSON values are unsupported: {value}"
    )


def _object_without_duplicates(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise NativeFunctionAccountingError(
                f"duplicate JSON object key: {key}"
            )
        result[key] = value
    return result


def _is_reparse(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & marker)


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
            raise NativeFunctionAccountingError(
                f"{label} parent chain cannot be inspected"
            ) from exc
        if (
            stat.S_ISLNK(info.st_mode)
            or _is_reparse(info)
            or not stat.S_ISDIR(info.st_mode)
        ):
            raise NativeFunctionAccountingError(
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
        before = path.stat()
    except OSError as exc:
        raise NativeFunctionAccountingError(
            f"{label} is not a readable regular file"
        ) from exc
    if (
        stat.S_ISLNK(link_before.st_mode)
        or _is_reparse(link_before)
        or not stat.S_ISREG(before.st_mode)
    ):
        raise NativeFunctionAccountingError(
            f"{label} is not a regular non-link file"
        )
    if before.st_size > _MAX_JSON_BYTES:
        raise NativeFunctionAccountingError(
            f"{label} exceeds the JSON size limit"
        )
    try:
        with path.open("rb") as stream:
            handle_before = os.fstat(stream.fileno())
            if any(
                getattr(before, field) != getattr(handle_before, field)
                for field in _STABLE_STAT_FIELDS
            ):
                raise NativeFunctionAccountingError(
                    f"{label} changed while being opened"
                )
            payload = stream.read(handle_before.st_size + 1)
            handle_after = os.fstat(stream.fileno())
    except OSError as exc:
        raise NativeFunctionAccountingError(f"{label} could not be read") from exc
    try:
        after = path.stat()
        link_after = path.lstat()
    except OSError as exc:
        raise NativeFunctionAccountingError(
            f"{label} changed while being read"
        ) from exc
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
        parents_changed
        or any(
            getattr(handle_before, field) != getattr(handle_after, field)
            or getattr(handle_after, field) != getattr(after, field)
            or getattr(link_before, field) != getattr(link_after, field)
            for field in _STABLE_STAT_FIELDS
        )
        or stat.S_ISLNK(link_after.st_mode)
        or _is_reparse(link_after)
        or len(payload) != handle_before.st_size
    ):
        raise NativeFunctionAccountingError(
            f"{label} changed while being read"
        )
    value = json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_object_without_duplicates,
        parse_constant=_reject_json_constant,
        parse_float=_reject_json_float,
    )
    if not isinstance(value, dict):
        raise NativeFunctionAccountingError(
            f"{label} must contain a JSON object"
        )
    return value, payload


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    value, _payload = _read_json_document(path, label)
    return value


def _prepare_output_root() -> tuple[Path, Path, os.stat_result]:
    repo_root = Path(os.path.abspath(_REPO_ROOT))
    configured_root = Path(os.path.abspath(_OUTPUT_ROOT))
    expected_root = repo_root / "data" / "observatory" / "programs"
    if configured_root != expected_root:
        raise NativeFunctionAccountingError(
            "configured native-accounting output root is not repository-local"
        )
    try:
        repo_info = repo_root.lstat()
    except OSError as exc:
        raise NativeFunctionAccountingError(
            "repository root is not a readable directory"
        ) from exc
    if (
        stat.S_ISLNK(repo_info.st_mode)
        or _is_reparse(repo_info)
        or not stat.S_ISDIR(repo_info.st_mode)
    ):
        raise NativeFunctionAccountingError(
            "repository root is not a real directory"
        )

    current = repo_root
    for part in ("data", "observatory", "programs"):
        current /= part
        try:
            current.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise NativeFunctionAccountingError(
                "cannot create native-accounting output directory"
            ) from exc
        try:
            info = current.lstat()
        except OSError as exc:
            raise NativeFunctionAccountingError(
                "cannot inspect native-accounting output directory"
            ) from exc
        if (
            stat.S_ISLNK(info.st_mode)
            or _is_reparse(info)
            or not stat.S_ISDIR(info.st_mode)
        ):
            raise NativeFunctionAccountingError(
                "native-accounting output directory chain contains a "
                "link/reparse entry"
            )
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(repo_root.resolve(strict=True)):
        raise NativeFunctionAccountingError(
            "native-accounting output directory escapes the repository"
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
        raise NativeFunctionAccountingError(
            "native-accounting output directory changed during writing"
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
        raise NativeFunctionAccountingError(
            "native-accounting output directory changed during writing"
        )


def _replacement_identity(
    value: dict[str, Any],
    label: str,
) -> bytes:
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != SCHEMA_VERSION
    ):
        raise NativeFunctionAccountingError(
            f"{label} has an invalid native-accounting schema"
        )
    if value.get("analysis_kind") != ANALYSIS_KIND:
        raise NativeFunctionAccountingError(
            f"{label} is not a native-accounting artifact"
        )
    build_identity = value.get("build_identity")
    atlas = value.get("atlas")
    if not isinstance(build_identity, dict) or not isinstance(atlas, dict):
        raise NativeFunctionAccountingError(
            f"{label} lacks native-accounting replacement identity"
        )
    atlas_sha256 = atlas.get("canonical_sha256")
    if (
        type(atlas_sha256) is not str
        or len(atlas_sha256) != 64
        or any(character not in "0123456789abcdef" for character in atlas_sha256)
    ):
        raise NativeFunctionAccountingError(
            f"{label} has an invalid atlas replacement identity"
        )
    return (
        json.dumps(
            {
                "schema_version": value["schema_version"],
                "analysis_kind": value["analysis_kind"],
                "build_identity": build_identity,
                "atlas_canonical_sha256": atlas_sha256,
            },
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _write_evidence_atomically(output: Path, rendered: str) -> None:
    configured_root, output_root, root_before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured_root:
        raise NativeFunctionAccountingError(
            "output must be a direct child of data/observatory/programs"
        )
    try:
        rendered_value = json.loads(
            rendered,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
            parse_float=_reject_json_float,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeFunctionAccountingError(
            "refusing to write invalid native-accounting JSON"
        ) from exc
    if not isinstance(rendered_value, dict):
        raise NativeFunctionAccountingError(
            "refusing to write non-object native-accounting JSON"
        )
    rendered_identity = _replacement_identity(rendered_value, "new output")
    destination = output_root / output.name
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise NativeFunctionAccountingError(
                "refusing to replace non-regular output"
            )
        try:
            existing, existing_payload = _read_json_document(
                destination, "existing output"
            )
        except (
            NativeFunctionAccountingError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise NativeFunctionAccountingError(
                "refusing to replace an existing non-native-accounting artifact"
            ) from exc
        try:
            existing_identity = _replacement_identity(existing, "existing output")
        except NativeFunctionAccountingError as exc:
            raise NativeFunctionAccountingError(
                "refusing to replace an existing non-native-accounting artifact"
            ) from exc
        if existing_identity != rendered_identity:
            raise NativeFunctionAccountingError(
                "refusing to replace a different native-accounting identity"
            )
        if _canonical_bytes(existing) != _canonical_bytes(rendered_value):
            raise NativeFunctionAccountingError(
                "refusing to overwrite differing native-accounting evidence"
            )
        expected_payload = rendered.encode("utf-8")
        if existing_payload != expected_payload:
            raise NativeFunctionAccountingError(
                "existing native-accounting evidence is not deterministically encoded"
            )
        confirmation, confirmation_payload = _read_json_document(
            destination, "existing output confirmation"
        )
        if (
            _canonical_bytes(confirmation) != _canonical_bytes(rendered_value)
            or confirmation_payload != expected_payload
        ):
            raise NativeFunctionAccountingError(
                "existing native-accounting evidence changed during comparison"
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
            raise NativeFunctionAccountingError(
                "output appeared concurrently; refusing to overwrite it"
            ) from exc
        except OSError as exc:
            raise NativeFunctionAccountingError(
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
        registry = _read_json_object(args.registry, "review registry")
        if args.command == "build":
            result = build_native_function_accounting(
                args.executable,
                program_facts,
                registry,
                inventory=inventory,
                repo_root=_REPO_ROOT,
            )
            rendered = encode_native_function_accounting(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_evidence_atomically(args.output, rendered)
        else:
            evidence, evidence_payload = _read_json_document(
                args.evidence, "evidence"
            )
            if evidence_payload != encode_native_function_accounting(
                evidence
            ).encode("utf-8"):
                raise NativeFunctionAccountingError(
                    "evidence is not deterministically encoded"
                )
            result = validate_native_function_accounting(
                args.executable,
                evidence,
                program_facts,
                registry,
                inventory=inventory,
                repo_root=_REPO_ROOT,
            )
            sys.stdout.write(encode_native_function_accounting(result))
        return 0
    except (
        NativeFunctionAccountingError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
