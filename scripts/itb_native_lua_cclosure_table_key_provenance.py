#!/usr/bin/env python3
"""Build or verify exact Lua C-closure table-key provenance evidence."""

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
from src.observatory.native_lua_cclosure_table_key_provenance import (  # noqa: E402
    ANALYSIS_KIND,
    SCHEMA_VERSION,
    NativeLuaCClosureTableKeyProvenanceError,
    _canonical_bytes,
    build_native_lua_cclosure_table_key_provenance_census,
    encode_native_lua_cclosure_table_key_provenance_census,
    validate_native_lua_cclosure_table_key_provenance_census,
)
from src.observatory.native_lua_direct_calls import NativeLuaDirectCallError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("build", "build exact table-key provenance evidence"),
        ("verify", "verify table-key provenance evidence"),
    ):
        item = subparsers.add_parser(command, help=help_text)
        item.add_argument("--executable", required=True, type=Path)
        item.add_argument("--inventory", required=True, type=Path)
        item.add_argument("--program-facts", required=True, type=Path)
        item.add_argument("--direct-calls", required=True, type=Path)
        item.add_argument("--callbacks", required=True, type=Path)
        item.add_argument("--setfield-publications", required=True, type=Path)
        item.add_argument(
            "--direct-table-setter-publications", required=True, type=Path
        )
        item.add_argument(
            "--indirect-settable-publications", required=True, type=Path
        )
        if command == "build":
            item.add_argument("--output", type=Path)
        else:
            item.add_argument("--evidence", required=True, type=Path)
    return parser


def _prepare_output_root() -> tuple[Path, Path, os.stat_result]:
    repo_root = Path(os.path.abspath(_REPO_ROOT))
    configured = Path(os.path.abspath(_OUTPUT_ROOT))
    if configured != repo_root / "data" / "observatory" / "programs":
        raise NativeLuaCClosureTableKeyProvenanceError(
            "configured output root is not repository-local"
        )
    try:
        repo_info = repo_root.lstat()
    except OSError as exc:
        raise NativeLuaCClosureTableKeyProvenanceError(
            "repository root is unreadable"
        ) from exc
    if (
        stat.S_ISLNK(repo_info.st_mode)
        or _is_reparse(repo_info)
        or not stat.S_ISDIR(repo_info.st_mode)
    ):
        raise NativeLuaCClosureTableKeyProvenanceError(
            "repository root is not a real directory"
        )
    current = repo_root
    for part in ("data", "observatory", "programs"):
        current /= part
        try:
            current.mkdir()
        except FileExistsError:
            pass
        info = current.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or _is_reparse(info)
            or not stat.S_ISDIR(info.st_mode)
        ):
            raise NativeLuaCClosureTableKeyProvenanceError(
                "output chain contains a link or reparse entry"
            )
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(repo_root.resolve(strict=True)):
        raise NativeLuaCClosureTableKeyProvenanceError(
            "output directory escapes repository"
        )
    return current, resolved, current.stat()


def _recheck_output_root(
    configured: Path, resolved: Path, expected: os.stat_result
) -> None:
    try:
        link_info, path_info = configured.lstat(), configured.stat()
        current = configured.resolve(strict=True)
    except OSError as exc:
        raise NativeLuaCClosureTableKeyProvenanceError(
            "output directory changed during writing"
        ) from exc
    if (
        stat.S_ISLNK(link_info.st_mode)
        or _is_reparse(link_info)
        or not stat.S_ISDIR(path_info.st_mode)
        or current != resolved
        or any(
            getattr(path_info, field) != getattr(expected, field)
            for field in _DIRECTORY_ID_FIELDS
        )
    ):
        raise NativeLuaCClosureTableKeyProvenanceError(
            "output directory changed during writing"
        )


def _replacement_identity(value: dict[str, Any], label: str) -> bytes:
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != SCHEMA_VERSION
        or value.get("analysis_kind") != ANALYSIS_KIND
    ):
        raise NativeLuaCClosureTableKeyProvenanceError(
            f"{label} has another schema or analysis kind"
        )
    identity = value.get("build_identity")
    fields = (
        value.get("atlas"),
        value.get("direct_call_census"),
        value.get("callback_census"),
        value.get("setfield_publication_census"),
        value.get("direct_table_setter_publication_census"),
        value.get("indirect_settable_publication_census"),
    )
    if not isinstance(identity, dict) or not all(
        isinstance(item, dict) for item in fields
    ):
        raise NativeLuaCClosureTableKeyProvenanceError(
            f"{label} lacks prerequisite identity"
        )
    hashes = tuple(item.get("canonical_sha256") for item in fields)
    if not all(type(item) is str for item in hashes):
        raise NativeLuaCClosureTableKeyProvenanceError(
            f"{label} lacks canonical prerequisites"
        )
    return _canonical_bytes(
        {
            "schema_version": value["schema_version"],
            "analysis_kind": value["analysis_kind"],
            "build_identity": identity,
            "prerequisite_hashes": list(hashes),
        }
    )


def _write_evidence_immutably(
    output: Path, rendered: str, result: dict[str, Any]
) -> None:
    configured, resolved, before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured:
        raise NativeLuaCClosureTableKeyProvenanceError(
            "output must be a direct child of data observatory programs"
        )
    destination = resolved / output.name
    identity = _replacement_identity(result, "new evidence")
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise NativeLuaCClosureTableKeyProvenanceError(
                "refusing to replace non-regular output"
            )
        try:
            existing, payload = _read_json_document(destination, "existing output")
            existing_identity = _replacement_identity(existing, "existing output")
        except (
            NativeLuaCClosureTableKeyProvenanceError,
            NativeLuaDirectCallError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise NativeLuaCClosureTableKeyProvenanceError(
                "refusing to replace an unrelated table-key provenance artifact"
            ) from exc
        if existing_identity != identity:
            raise NativeLuaCClosureTableKeyProvenanceError(
                "refusing to replace evidence for other prerequisites"
            )
        expected = rendered.encode("utf-8")
        if _canonical_bytes(existing) != _canonical_bytes(result) or payload != expected:
            raise NativeLuaCClosureTableKeyProvenanceError(
                "refusing to overwrite differing table-key provenance evidence"
            )
        _recheck_output_root(configured, resolved, before)
        try:
            confirmation, confirmation_payload = _read_json_document(
                destination, "existing output confirmation"
            )
        except (
            NativeLuaDirectCallError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise NativeLuaCClosureTableKeyProvenanceError(
                "existing table-key provenance evidence changed during comparison"
            ) from exc
        if (
            _canonical_bytes(confirmation) != _canonical_bytes(result)
            or confirmation_payload != expected
        ):
            raise NativeLuaCClosureTableKeyProvenanceError(
                "existing table-key provenance evidence changed during comparison"
            )
        _recheck_output_root(configured, resolved, before)
        return
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=resolved
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        _recheck_output_root(configured, resolved, before)
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise NativeLuaCClosureTableKeyProvenanceError(
                "output appeared concurrently and was preserved"
            ) from exc
        os.unlink(temporary)
        _recheck_output_root(configured, resolved, before)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inventory = _read_json_object(args.inventory, "inventory")
        facts = _read_json_object(args.program_facts, "program facts")
        direct = _read_json_object(args.direct_calls, "direct calls")
        callbacks = _read_json_object(args.callbacks, "callbacks")
        setfield = _read_json_object(args.setfield_publications, "setfield publications")
        direct_setters = _read_json_object(
            args.direct_table_setter_publications,
            "direct table-setter publications",
        )
        indirect_setters = _read_json_object(
            args.indirect_settable_publications,
            "indirect settable publications",
        )
        common = (
            args.executable,
            direct,
            callbacks,
            setfield,
            direct_setters,
            indirect_setters,
            facts,
        )
        if args.command == "build":
            result = build_native_lua_cclosure_table_key_provenance_census(
                *common, inventory=inventory
            )
            rendered = encode_native_lua_cclosure_table_key_provenance_census(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_evidence_immutably(args.output, rendered, result)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode_native_lua_cclosure_table_key_provenance_census(
                evidence
            ).encode("utf-8"):
                raise NativeLuaCClosureTableKeyProvenanceError(
                    "evidence is not deterministically encoded"
                )
            result = validate_native_lua_cclosure_table_key_provenance_census(
                args.executable,
                evidence,
                *common[1:],
                inventory=inventory,
            )
            sys.stdout.write(
                encode_native_lua_cclosure_table_key_provenance_census(result)
            )
        return 0
    except (
        NativeLuaCClosureTableKeyProvenanceError,
        NativeLuaDirectCallError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
