#!/usr/bin/env python3
"""Build or verify the 0x00378ad0 un-atlased-span static receipt."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from scripts.itb_native_assertion_helper_static_boundary import (  # noqa: E402
    NativeAssertionHelperStaticBoundaryError,
    _locked_output,
    _read_locked_json_document,
)
from scripts.itb_native_lua_direct_calls import (  # noqa: E402
    _is_reparse,
    _read_json_document,
    _read_json_object,
)
from scripts.itb_native_lua_property_factory_chain import (  # noqa: E402
    NativeLuaPropertyFactoryChainError,
    _prepare_output_root,
    _recheck_output_root,
)
from src.observatory.native_lua_cclosure_setfield_publications import (  # noqa: E402
    NativeLuaCClosurePublicationError,
)
from src.observatory.native_lua_direct_calls import (  # noqa: E402
    NativeLuaDirectCallError,
)
from src.observatory.native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary import (  # noqa: E402
    ANALYSIS_KIND,
    SCHEMA_VERSION,
    NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeRightUnatlasedSpanStaticBoundaryError as BoundaryError,
    _canonical_bytes,
    build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary as build,
    encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary as encode,
    validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary as validate,
    validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary_structure as validate_structure,
)

_PREREQUISITE_FLAGS = (
    "fourth-callee-static-boundary",
    "fourth-callee-child-static-boundary",
    "residual-direct-target-set-static-boundary",
    "residual-direct-target-set-callee-static-boundary",
    "direct-calls",
    "program-facts",
)
_IDENTITY_FIELDS = (
    "fourth_callee_static_boundary",
    "fourth_callee_child_static_boundary",
    "residual_direct_target_set_static_boundary",
    "residual_direct_target_set_callee_static_boundary",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "verify-structure"):
        item = commands.add_parser(command)
        for name in _PREREQUISITE_FLAGS:
            item.add_argument("--" + name, required=True, type=Path)
        if command != "verify-structure":
            item.add_argument("--executable", required=True, type=Path)
            item.add_argument("--inventory", required=True, type=Path)
        if command == "build":
            item.add_argument("--output", type=Path)
        else:
            item.add_argument("--evidence", required=True, type=Path)
    return parser


def _identity(value: dict[str, Any]) -> bytes:
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != SCHEMA_VERSION
        or value.get("analysis_kind") != ANALYSIS_KIND
        or not isinstance(value.get("build_identity"), dict)
    ):
        raise BoundaryError("evidence schema, kind, or build identity differs")
    prerequisites: dict[str, str] = {}
    for field in _IDENTITY_FIELDS:
        source = value.get(field)
        if (
            not isinstance(source, dict)
            or type(source.get("canonical_sha256")) is not str
        ):
            raise BoundaryError("evidence lacks prerequisite identity")
        prerequisites[field + "_canonical_sha256"] = source["canonical_sha256"]
    return _canonical_bytes(
        {
            "schema_version": value["schema_version"],
            "analysis_kind": value["analysis_kind"],
            "build_identity": value["build_identity"],
            **prerequisites,
        }
    )


def _same_expected(
    value: dict[str, Any], payload: bytes, identity: bytes, expected: bytes
) -> bool:
    return (
        _identity(value) == identity
        and _canonical_bytes(value) == _canonical_bytes(json.loads(expected))
        and payload == expected
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
        raise BoundaryError("output failed regular-file identity check")
    return value


def _write_immutably_impl(output: Path, rendered: str, value: dict[str, Any]) -> None:
    configured, resolved, before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured:
        raise BoundaryError(
            "output must be a direct child of data observatory programs"
        )
    destination = resolved / output.name
    expected = rendered.encode("utf-8")
    identity = _identity(value)
    if os.path.lexists(destination):
        initial = _regular_child(destination, resolved)
        existing, payload = _read_json_document(destination, "existing output")
        final = _regular_child(destination, resolved, (initial.st_dev, initial.st_ino))
        _recheck_output_root(configured, resolved, before)
        if not _same_expected(existing, payload, identity, expected):
            raise BoundaryError("refusing to overwrite differing un-atlased evidence")
        with _locked_output(
            destination, resolved, (final.st_dev, final.st_ino)
        ) as descriptor:
            _regular_child(destination, resolved, (final.st_dev, final.st_ino))
            _recheck_output_root(configured, resolved, before)
            locked, payload = _read_locked_json_document(
                descriptor, "final existing output"
            )
            if not _same_expected(locked, payload, identity, expected):
                raise BoundaryError(
                    "existing output changed during final content validation"
                )
        return

    descriptor, name = tempfile.mkstemp(
        prefix="." + output.name + ".", suffix=".tmp", dir=resolved
    )
    temporary = Path(name)
    linked = False
    inode: tuple[int, int] | None = None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        source = temporary.lstat()
        if (
            stat.S_ISLNK(source.st_mode)
            or _is_reparse(source)
            or not stat.S_ISREG(source.st_mode)
        ):
            raise BoundaryError("temporary output is not a real regular file")
        inode = (source.st_dev, source.st_ino)
        _recheck_output_root(configured, resolved, before)
        os.link(temporary, destination)
        linked = True
        _regular_child(destination, resolved, inode)
        _recheck_output_root(configured, resolved, before)
        temporary.unlink()
        _regular_child(destination, resolved, inode)
        with _locked_output(destination, resolved, inode) as locked_descriptor:
            _regular_child(destination, resolved, inode)
            _recheck_output_root(configured, resolved, before)
            locked, payload = _read_locked_json_document(
                locked_descriptor, "final created output"
            )
            if not _same_expected(locked, payload, identity, expected):
                raise BoundaryError(
                    "created output changed during final content validation"
                )
    except Exception:
        if linked and inode is not None:
            try:
                published = destination.lstat()
                if (published.st_dev, published.st_ino) == inode:
                    destination.unlink()
            except FileNotFoundError:
                pass
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def _write_immutably(output: Path, rendered: str, value: dict[str, Any]) -> None:
    try:
        _write_immutably_impl(output, rendered, value)
    except (
        NativeAssertionHelperStaticBoundaryError,
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        NativeLuaPropertyFactoryChainError,
    ) as exc:
        raise BoundaryError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        get = lambda name: _read_json_object(
            getattr(args, name.replace("-", "_")), name
        )
        prerequisites = tuple(get(name) for name in _PREREQUISITE_FLAGS)
        if args.command == "build":
            result = build(
                args.executable,
                *prerequisites,
                inventory=get("inventory"),
            )
            rendered = encode(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_immutably(args.output, rendered, result)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode(evidence).encode("utf-8"):
                raise BoundaryError("evidence is not deterministically encoded")
            result = (
                validate(
                    args.executable,
                    evidence,
                    *prerequisites,
                    inventory=get("inventory"),
                )
                if args.command == "verify"
                else validate_structure(evidence, *prerequisites)
            )
            sys.stdout.write(encode(result))
        return 0
    except (
        BoundaryError,
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        NativeLuaPropertyFactoryChainError,
        OSError,
        TypeError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
