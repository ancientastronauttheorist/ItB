#!/usr/bin/env python3
"""Build or verify exact direct-setfield publications of native Lua closures."""

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
_DIRECTORY_ID_FIELDS = ("st_dev", "st_ino")
sys.path.insert(0, str(_REPO_ROOT))

from scripts.itb_native_lua_direct_calls import (  # noqa: E402
    _is_reparse,
    _read_json_document,
    _read_json_object,
)
from src.observatory.native_lua_cclosure_callbacks import (  # noqa: E402
    NativeLuaCClosureError,
)
from src.observatory.native_lua_cclosure_setfield_publications import (  # noqa: E402
    ANALYSIS_KIND,
    SCHEMA_VERSION,
    NativeLuaCClosurePublicationError,
    _canonical_bytes,
    build_native_lua_cclosure_setfield_publication_census,
    encode_native_lua_cclosure_setfield_publication_census,
    validate_native_lua_cclosure_setfield_publication_census,
)
from src.observatory.native_lua_direct_calls import (  # noqa: E402
    NativeLuaDirectCallError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser(
        "build", help="build exact closure-publication evidence"
    )
    build.add_argument("--executable", required=True, type=Path)
    build.add_argument("--inventory", required=True, type=Path)
    build.add_argument("--program-facts", required=True, type=Path)
    build.add_argument("--direct-calls", required=True, type=Path)
    build.add_argument("--callbacks", required=True, type=Path)
    build.add_argument("--output", type=Path)

    verify = subparsers.add_parser(
        "verify", help="verify closure-publication evidence"
    )
    verify.add_argument("--executable", required=True, type=Path)
    verify.add_argument("--inventory", required=True, type=Path)
    verify.add_argument("--program-facts", required=True, type=Path)
    verify.add_argument("--direct-calls", required=True, type=Path)
    verify.add_argument("--callbacks", required=True, type=Path)
    verify.add_argument("--evidence", required=True, type=Path)
    return parser


def _prepare_output_root() -> tuple[Path, Path, os.stat_result]:
    repo_root = Path(os.path.abspath(_REPO_ROOT))
    configured_root = Path(os.path.abspath(_OUTPUT_ROOT))
    expected_root = repo_root / "data" / "observatory" / "programs"
    if configured_root != expected_root:
        raise NativeLuaCClosurePublicationError(
            "configured publication output root is not repository-local"
        )
    try:
        repo_info = repo_root.lstat()
    except OSError as exc:
        raise NativeLuaCClosurePublicationError(
            "repository root is not a readable directory"
        ) from exc
    if (
        stat.S_ISLNK(repo_info.st_mode)
        or _is_reparse(repo_info)
        or not stat.S_ISDIR(repo_info.st_mode)
    ):
        raise NativeLuaCClosurePublicationError(
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
            raise NativeLuaCClosurePublicationError(
                "cannot create publication output directory"
            ) from exc
        try:
            info = current.lstat()
        except OSError as exc:
            raise NativeLuaCClosurePublicationError(
                "cannot inspect publication output directory"
            ) from exc
        if (
            stat.S_ISLNK(info.st_mode)
            or _is_reparse(info)
            or not stat.S_ISDIR(info.st_mode)
        ):
            raise NativeLuaCClosurePublicationError(
                "publication output chain contains a link or reparse entry"
            )
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(repo_root.resolve(strict=True)):
        raise NativeLuaCClosurePublicationError(
            "publication output directory escapes the repository"
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
        raise NativeLuaCClosurePublicationError(
            "publication output directory changed during writing"
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
        raise NativeLuaCClosurePublicationError(
            "publication output directory changed during writing"
        )


def _replacement_identity(value: dict[str, Any], label: str) -> bytes:
    if value.get("schema_version") != SCHEMA_VERSION:
        raise NativeLuaCClosurePublicationError(
            f"{label} has another schema version"
        )
    if value.get("analysis_kind") != ANALYSIS_KIND:
        raise NativeLuaCClosurePublicationError(
            f"{label} has another analysis kind"
        )
    identity = value.get("build_identity")
    atlas = value.get("atlas")
    direct = value.get("direct_call_census")
    callbacks = value.get("callback_census")
    if not isinstance(identity, dict):
        raise NativeLuaCClosurePublicationError(f"{label} lacks build identity")
    if not all(isinstance(item, dict) for item in (atlas, direct, callbacks)):
        raise NativeLuaCClosurePublicationError(
            f"{label} lacks prerequisite identity"
        )
    atlas_sha = atlas.get("canonical_sha256")
    direct_sha = direct.get("canonical_sha256")
    callback_sha = callbacks.get("canonical_sha256")
    if not all(type(item) is str for item in (atlas_sha, direct_sha, callback_sha)):
        raise NativeLuaCClosurePublicationError(
            f"{label} lacks canonical prerequisites"
        )
    return _canonical_bytes(
        {
            "schema_version": value["schema_version"],
            "analysis_kind": value["analysis_kind"],
            "build_identity": identity,
            "atlas_canonical_sha256": atlas_sha,
            "direct_call_census_canonical_sha256": direct_sha,
            "callback_census_canonical_sha256": callback_sha,
        }
    )


def _write_evidence_immutably(
    output: Path,
    rendered: str,
    result: dict[str, Any],
) -> None:
    configured_root, output_root, root_before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured_root:
        raise NativeLuaCClosurePublicationError(
            "output must be a direct child of data observatory programs"
        )
    destination = output_root / output.name
    new_identity = _replacement_identity(result, "new evidence")
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise NativeLuaCClosurePublicationError(
                "refusing to replace non-regular output"
            )
        try:
            existing, existing_payload = _read_json_document(
                destination, "existing output"
            )
            existing_identity = _replacement_identity(
                existing, "existing output"
            )
        except (
            NativeLuaCClosurePublicationError,
            NativeLuaCClosureError,
            NativeLuaDirectCallError,
            OSError,
        ) as exc:
            raise NativeLuaCClosurePublicationError(
                "refusing to replace an unrelated publication artifact"
            ) from exc
        if existing_identity != new_identity:
            raise NativeLuaCClosurePublicationError(
                "refusing to replace publication evidence for other prerequisites"
            )
        if _canonical_bytes(existing) != _canonical_bytes(result):
            raise NativeLuaCClosurePublicationError(
                "refusing to overwrite differing publication evidence"
            )
        expected_payload = rendered.encode("utf-8")
        if existing_payload != expected_payload:
            raise NativeLuaCClosurePublicationError(
                "existing publication evidence is not deterministically encoded"
            )
        confirmation, confirmation_payload = _read_json_document(
            destination, "existing output confirmation"
        )
        if (
            _canonical_bytes(confirmation) != _canonical_bytes(result)
            or confirmation_payload != expected_payload
        ):
            raise NativeLuaCClosurePublicationError(
                "existing publication evidence changed during comparison"
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
            raise NativeLuaCClosurePublicationError(
                "output appeared concurrently and was preserved"
            ) from exc
        except OSError as exc:
            raise NativeLuaCClosurePublicationError(
                "could not publish evidence without overwriting"
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
        direct_calls = _read_json_object(args.direct_calls, "direct calls")
        callbacks = _read_json_object(args.callbacks, "callbacks")
        if args.command == "build":
            result = build_native_lua_cclosure_setfield_publication_census(
                args.executable,
                direct_calls,
                callbacks,
                program_facts,
                inventory=inventory,
            )
            rendered = encode_native_lua_cclosure_setfield_publication_census(
                result
            )
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_evidence_immutably(args.output, rendered, result)
        else:
            evidence, evidence_payload = _read_json_document(
                args.evidence, "evidence"
            )
            if evidence_payload != (
                encode_native_lua_cclosure_setfield_publication_census(
                    evidence
                ).encode("utf-8")
            ):
                raise NativeLuaCClosurePublicationError(
                    "evidence is not deterministically encoded"
                )
            result = validate_native_lua_cclosure_setfield_publication_census(
                args.executable,
                evidence,
                direct_calls,
                callbacks,
                program_facts,
                inventory=inventory,
            )
            sys.stdout.write(
                encode_native_lua_cclosure_setfield_publication_census(result)
            )
        return 0
    except (
        NativeLuaCClosurePublicationError,
        NativeLuaCClosureError,
        NativeLuaDirectCallError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
