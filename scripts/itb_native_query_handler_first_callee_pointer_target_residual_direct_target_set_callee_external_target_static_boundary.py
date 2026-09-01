#!/usr/bin/env python3
"""Build or verify the residual-target-set callee external-target receipt."""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from scripts.itb_native_assertion_helper_static_boundary import (  # noqa: E402
    NativeAssertionHelperStaticBoundaryError,
    _locked_output,
    _read_locked_json_document,
    _regular_child,
)
from scripts.itb_native_lua_direct_calls import (  # noqa: E402
    _is_reparse,
    _read_json_document,
    _read_json_object,
)
from scripts.itb_native_lua_property_factory_chain import (  # noqa: E402
    _prepare_output_root,
    _recheck_output_root,
)
from src.observatory.native_lua_class_return_helper_chain import (  # noqa: E402
    _canonical_bytes,
)
from src.observatory.native_lua_cclosure_setfield_publications import (  # noqa: E402
    NativeLuaCClosurePublicationError,
)
from src.observatory.native_lua_direct_calls import (  # noqa: E402
    NativeLuaDirectCallError,
)
from src.observatory.native_lua_property_factory_chain import (  # noqa: E402
    NativeLuaPropertyFactoryChainError,
)
from src.observatory.native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary import (  # noqa: E402
    ANALYSIS_KIND,
    SCHEMA_VERSION,
    NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError,
    build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary,
    encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary,
    validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary,
    validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary_structure,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "verify-structure"):
        subparser = commands.add_parser(command)
        for name in (
            "predecessor-static-boundary",
            "direct-calls",
            "program-facts",
        ):
            subparser.add_argument("--" + name, required=True, type=Path)
        if command != "verify-structure":
            subparser.add_argument("--executable", required=True, type=Path)
            subparser.add_argument("--inventory", required=True, type=Path)
        if command == "build":
            subparser.add_argument("--output", type=Path)
        else:
            subparser.add_argument("--evidence", required=True, type=Path)
    return parser


def _identity(value: dict[str, object]) -> bytes:
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != SCHEMA_VERSION
        or value.get("analysis_kind") != ANALYSIS_KIND
        or not isinstance(value.get("build_identity"), dict)
    ):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError(
            "evidence has another schema, kind, or lacks build identity"
        )
    predecessor = value.get("predecessor_static_boundary")
    if (
        not isinstance(predecessor, dict)
        or type(predecessor.get("canonical_sha256")) is not str
    ):
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError(
            "evidence lacks prerequisite identities"
        )
    return _canonical_bytes(
        {
            "schema_version": value["schema_version"],
            "analysis_kind": value["analysis_kind"],
            "build_identity": value["build_identity"],
            "predecessor_static_boundary_canonical_sha256": predecessor[
                "canonical_sha256"
            ],
        }
    )


def _same_output(
    value: dict[str, object], payload: bytes, identity: bytes, expected: bytes
) -> bool:
    return (
        _identity(value) == identity
        and _canonical_bytes(value) == _canonical_bytes(json.loads(expected))
        and payload == expected
    )


def _write_immutably_impl(
    output: Path, rendered: str, value: dict[str, object]
) -> None:
    configured, resolved, before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError(
            "output must be a direct child of data observatory programs"
        )
    destination = resolved / output.name
    expected = rendered.encode("utf-8")
    identity = _identity(value)
    if os.path.lexists(destination):
        initial = _regular_child(destination, resolved)
        existing, payload = _read_json_document(destination, "existing output")
        final = _regular_child(
            destination, resolved, (initial.st_dev, initial.st_ino)
        )
        _recheck_output_root(configured, resolved, before)
        if not _same_output(existing, payload, identity, expected):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError(
                "refusing to overwrite differing external-target evidence"
            )
        with _locked_output(
            destination, resolved, (final.st_dev, final.st_ino)
        ) as descriptor:
            _recheck_output_root(configured, resolved, before)
            final_value, final_payload = _read_locked_json_document(
                descriptor, "final existing output"
            )
            if not _same_output(final_value, final_payload, identity, expected):
                raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError(
                    "existing output changed during final content validation"
                )
            return
    descriptor, name = tempfile.mkstemp(
        prefix="." + output.name + ".", suffix=".tmp", dir=resolved
    )
    temporary = Path(name)
    linked = False
    source_identity: tuple[int, int] | None = None
    try:
        with os.fdopen(
            descriptor, "w", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        source = temporary.lstat()
        if (
            stat.S_ISLNK(source.st_mode)
            or _is_reparse(source)
            or not stat.S_ISREG(source.st_mode)
        ):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError(
                "temporary output is not a real regular file"
            )
        source_identity = (source.st_dev, source.st_ino)
        _recheck_output_root(configured, resolved, before)
        os.link(temporary, destination)
        linked = True
        _regular_child(destination, resolved, source_identity)
        _recheck_output_root(configured, resolved, before)
        temporary.unlink()
        _regular_child(destination, resolved, source_identity)
        _recheck_output_root(configured, resolved, before)
        with _locked_output(destination, resolved, source_identity) as locked:
            _recheck_output_root(configured, resolved, before)
            final_value, final_payload = _read_locked_json_document(
                locked, "final created output"
            )
            if not _same_output(final_value, final_payload, identity, expected):
                raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError(
                    "created output changed during final content validation"
                )
    except Exception:
        if linked and source_identity is not None:
            try:
                made = destination.lstat()
                if (made.st_dev, made.st_ino) == source_identity:
                    destination.unlink()
            except FileNotFoundError:
                pass
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def _write_immutably(
    output: Path, rendered: str, value: dict[str, object]
) -> None:
    try:
        _write_immutably_impl(output, rendered, value)
    except (
        NativeAssertionHelperStaticBoundaryError,
        NativeLuaPropertyFactoryChainError,
    ) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError(
            str(exc)
        ) from exc


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        get = lambda name: _read_json_object(  # noqa: E731
            getattr(args, name.replace("-", "_")), name
        )
        residual, direct_calls, program_facts = (
            get(name)
            for name in (
                "predecessor-static-boundary",
                "direct-calls",
                "program-facts",
            )
        )
        common = residual, direct_calls, program_facts
        if args.command == "build":
            result = build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(
                args.executable,
                *common,
                inventory=get("inventory"),
            )
            rendered = encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(
                result
            )
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_immutably(args.output, rendered, result)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            rendered = encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(
                evidence
            ).encode("utf-8")
            if payload != rendered:
                raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError(
                    "evidence is not deterministically encoded"
                )
            if args.command == "verify":
                result = validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(
                    args.executable,
                    evidence,
                    *common,
                    inventory=get("inventory"),
                )
            else:
                result = validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary_structure(
                    evidence, *common
                )
            sys.stdout.write(
                encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(
                    result
                )
            )
        return 0
    except (
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError,
        NativeAssertionHelperStaticBoundaryError,
        NativeLuaCClosurePublicationError,
        NativeLuaDirectCallError,
        NativeLuaPropertyFactoryChainError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
