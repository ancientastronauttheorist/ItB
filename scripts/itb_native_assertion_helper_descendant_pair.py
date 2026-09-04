#!/usr/bin/env python3
"""Build or verify the assertion descendant pair."""

from __future__ import annotations
import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
from scripts.itb_native_assertion_helper_static_boundary import (
    _locked_output,
    _read_locked_json_document,
)
from scripts.itb_native_lua_direct_calls import (
    _is_reparse,
    _read_json_document,
    _read_json_object,
)
from scripts.itb_native_lua_property_factory_chain import (
    _prepare_output_root,
    _recheck_output_root,
)
from src.observatory.native_assertion_helper_descendant_pair import (
    ANALYSIS_KIND,
    SCHEMA_VERSION,
    SEALED_SHA256,
    SOURCE_PINS,
    PairError as Error,
    _canonical_bytes,
    _canonical_sha256,
    build_pair as build,
    encode_pair as encode,
    validate_pair as validate,
    validate_structure,
)

_STAGE_PREFIX = ".itb-observatory-stage-"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "verify-structure"):
        item = commands.add_parser(command)
        for name in SOURCE_PINS:
            item.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
        if command != "verify-structure":
            item.add_argument("--executable", required=True, type=Path)
            item.add_argument("--inventory", required=True, type=Path)
        item.add_argument(
            "--output" if command == "build" else "--evidence",
            required=command != "build",
            type=Path,
        )
    return parser


def _identity(value: dict[str, Any]) -> bytes:
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != SCHEMA_VERSION
        or value.get("analysis_kind") != ANALYSIS_KIND
        or _canonical_sha256(value) != SEALED_SHA256
    ):
        raise Error("publication requires the exact sealed pair identity")
    return _canonical_bytes(
        {
            "schema_version": SCHEMA_VERSION,
            "analysis_kind": ANALYSIS_KIND,
            "canonical_sha256": SEALED_SHA256,
        }
    )


def _regular_child(
    path: Path, root: Path, identity: tuple[int, int] | None = None
) -> os.stat_result:
    value = path.lstat()
    if (
        stat.S_ISLNK(value.st_mode)
        or _is_reparse(value)
        or not stat.S_ISREG(value.st_mode)
        or path.resolve(strict=True).parent != root
        or (identity is not None and (value.st_dev, value.st_ino) != identity)
    ):
        raise Error("output failed regular-file identity check")
    return value


def _same_expected(
    value: dict[str, Any], payload: bytes, identity: bytes, expected: bytes
) -> bool:
    return (
        _identity(value) == identity
        and _canonical_bytes(value) == _canonical_bytes(json.loads(expected))
        and payload == expected
    )


def _validate_exact_child(
    path: Path,
    root: Path,
    configured: Path,
    root_identity: os.stat_result,
    evidence_identity: bytes,
    expected: bytes,
    *,
    label: str,
    mismatch: str,
    required_identity: tuple[int, int] | None = None,
) -> os.stat_result:
    initial = _regular_child(path, root, required_identity)
    value, payload = _read_json_document(path, label)
    identity = (initial.st_dev, initial.st_ino)
    final = _regular_child(path, root, identity)
    _recheck_output_root(configured, root, root_identity)
    if not _same_expected(value, payload, evidence_identity, expected):
        raise Error(mismatch)
    with _locked_output(path, root, identity) as descriptor:
        _regular_child(path, root, identity)
        _recheck_output_root(configured, root, root_identity)
        locked, locked_payload = _read_locked_json_document(
            descriptor, f"final {label}"
        )
        if not _same_expected(locked, locked_payload, evidence_identity, expected):
            raise Error(f"{label} changed during final content validation")
    return final


def _retained_stage_path(root: Path, expected: bytes) -> Path:
    return root / f"{_STAGE_PREFIX}{hashlib.sha256(expected).hexdigest()}.json"


def _create_retained_stage(path: Path, rendered: str) -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        return
    try:
        value = os.fstat(descriptor)
        if (
            stat.S_ISLNK(value.st_mode)
            or _is_reparse(value)
            or not stat.S_ISREG(value.st_mode)
        ):
            raise Error("retained stage descriptor is not a real regular file")
        stream = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        descriptor = -1
        with stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _write_immutably_impl(output: Path, rendered: str, value: dict[str, Any]) -> None:
    configured, resolved, before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured or output.name.startswith(_STAGE_PREFIX):
        raise Error(
            "output must be a non-stage direct child of data observatory programs"
        )
    destination, expected, identity = (
        resolved / output.name,
        rendered.encode("utf-8"),
        _identity(value),
    )
    if os.path.lexists(destination):
        _validate_exact_child(
            destination,
            resolved,
            configured,
            before,
            identity,
            expected,
            label="existing output",
            mismatch="refusing to overwrite differing child evidence",
        )
        return
    stage = _retained_stage_path(resolved, expected)
    if stage == destination:
        raise Error("output name collides with retained content-addressed stage")
    _create_retained_stage(stage, rendered)
    stage_stat = _validate_exact_child(
        stage,
        resolved,
        configured,
        before,
        identity,
        expected,
        label="retained stage",
        mismatch="retained content-addressed stage differs",
    )
    stage_identity = (stage_stat.st_dev, stage_stat.st_ino)
    _recheck_output_root(configured, resolved, before)
    try:
        os.link(stage, destination, follow_symlinks=False)
    except FileExistsError:
        linked = False
    else:
        linked = True
    _recheck_output_root(configured, resolved, before)
    _validate_exact_child(
        destination,
        resolved,
        configured,
        before,
        identity,
        expected,
        label="created output" if linked else "concurrent existing output",
        mismatch=(
            "created output differs from retained stage"
            if linked
            else "refusing to overwrite differing concurrent evidence"
        ),
        required_identity=stage_identity if linked else None,
    )


def _write_immutably(output: Path, rendered: str, value: dict[str, Any]) -> None:
    try:
        _write_immutably_impl(output, rendered, value)
    except Error:
        raise
    except Exception as exc:
        raise Error(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        sources = {
            name: _read_json_object(getattr(args, name), name) for name in SOURCE_PINS
        }
        if args.command == "build":
            result = build(
                args.executable,
                sources,
                inventory=_read_json_object(args.inventory, "inventory"),
            )
            rendered = encode(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_immutably(args.output, rendered, result)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode(evidence).encode("utf-8"):
                raise Error("evidence is not deterministically encoded")
            result = (
                validate_structure(evidence, sources)
                if args.command == "verify-structure"
                else validate(
                    args.executable,
                    evidence,
                    sources,
                    inventory=_read_json_object(args.inventory, "inventory"),
                )
            )
            sys.stdout.write(encode(result))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
