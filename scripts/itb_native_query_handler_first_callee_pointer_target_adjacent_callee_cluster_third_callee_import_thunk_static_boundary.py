#!/usr/bin/env python3
"""Build or verify the adjacent-cluster third-callee import-thunk receipt."""

from __future__ import annotations
import argparse, json, os, stat, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.itb_native_assertion_helper_static_boundary import (
    NativeAssertionHelperStaticBoundaryError,
    _locked_output,
    _read_locked_json_document,
    _regular_child,
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
from src.observatory.native_lua_class_return_helper_chain import _canonical_bytes
from src.observatory.native_lua_property_factory_chain import (
    NativeLuaPropertyFactoryChainError,
)
from src.observatory.native_lua_direct_calls import NativeLuaDirectCallError
from src.observatory.native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary import *


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "verify-structure"):
        q = s.add_parser(command)
        for name in ("parent-static-boundary", "direct-calls", "program-facts"):
            q.add_argument("--" + name, required=True, type=Path)
        if command != "verify-structure":
            q.add_argument("--executable", required=True, type=Path)
            q.add_argument("--inventory", required=True, type=Path)
        if command == "build":
            q.add_argument("--output", type=Path)
        else:
            q.add_argument("--evidence", required=True, type=Path)
    return p


def _identity(value):
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != SCHEMA_VERSION
        or value.get("analysis_kind") != ANALYSIS_KIND
        or not isinstance(value.get("build_identity"), dict)
    ):
        raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError(
            "evidence schema differs"
        )
    parent = value.get("parent_static_boundary")
    if not isinstance(parent, dict) or type(parent.get("canonical_sha256")) is not str:
        raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError(
            "evidence lacks parent identity"
        )
    return _canonical_bytes(
        {
            "schema_version": value["schema_version"],
            "analysis_kind": value["analysis_kind"],
            "build_identity": value["build_identity"],
            "parent_canonical_sha256": parent["canonical_sha256"],
        }
    )


def _same_output(value, payload, identity, expected):
    return (
        _identity(value) == identity
        and _canonical_bytes(value) == _canonical_bytes(json.loads(expected))
        and payload == expected
    )


def _write_immutably_impl(output, rendered, value):
    configured, resolved, before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured:
        raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError(
            "output must be a direct child of data observatory programs"
        )
    dest = resolved / output.name
    expected = rendered.encode("utf-8")
    identity = _identity(value)
    if os.path.lexists(dest):
        initial = _regular_child(dest, resolved)
        existing, payload = _read_json_document(dest, "existing output")
        final = _regular_child(dest, resolved, (initial.st_dev, initial.st_ino))
        _recheck_output_root(configured, resolved, before)
        if not _same_output(existing, payload, identity, expected):
            raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError(
                "refusing to overwrite differing import-thunk evidence"
            )
        with _locked_output(dest, resolved, (final.st_dev, final.st_ino)) as fd:
            _recheck_output_root(configured, resolved, before)
            value2, payload2 = _read_locked_json_document(fd, "final existing output")
            if not _same_output(value2, payload2, identity, expected):
                raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError(
                    "existing output changed during final content validation"
                )
        return
    fd, name = tempfile.mkstemp(
        prefix="." + output.name + ".", suffix=".tmp", dir=resolved
    )
    tmp = Path(name)
    linked = False
    source = None
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(rendered)
            f.flush()
            os.fsync(f.fileno())
        st = tmp.lstat()
        if stat.S_ISLNK(st.st_mode) or _is_reparse(st) or not stat.S_ISREG(st.st_mode):
            raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError(
                "temporary output is not a real regular file"
            )
        source = (st.st_dev, st.st_ino)
        _recheck_output_root(configured, resolved, before)
        os.link(tmp, dest)
        linked = True
        _regular_child(dest, resolved, source)
        _recheck_output_root(configured, resolved, before)
        tmp.unlink()
        _regular_child(dest, resolved, source)
        with _locked_output(dest, resolved, source) as lock:
            _recheck_output_root(configured, resolved, before)
            value2, payload2 = _read_locked_json_document(lock, "final created output")
            if not _same_output(value2, payload2, identity, expected):
                raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError(
                    "created output changed during final content validation"
                )
    except Exception:
        if linked and source is not None:
            try:
                made = dest.lstat()
                if (made.st_dev, made.st_ino) == source:
                    dest.unlink()
            except FileNotFoundError:
                pass
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise


def _write_immutably(output, rendered, value):
    try:
        _write_immutably_impl(output, rendered, value)
    except (
        NativeAssertionHelperStaticBoundaryError,
        NativeLuaDirectCallError,
        NativeLuaPropertyFactoryChainError,
    ) as exc:
        raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError(
            str(exc)
        ) from exc


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        get = lambda name: _read_json_object(
            getattr(args, name.replace("-", "_")), name
        )
        parent, direct, facts = (
            get(x) for x in ("parent-static-boundary", "direct-calls", "program-facts")
        )
        common = (parent, direct, facts)
        if args.command == "build":
            result = build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
                args.executable, *common, inventory=get("inventory")
            )
            rendered = encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
                result
            )
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_immutably(args.output, rendered, result)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            rendered = encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
                evidence
            ).encode()
            if payload != rendered:
                raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError(
                    "evidence is not deterministically encoded"
                )
            result = (
                validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
                    args.executable, evidence, *common, inventory=get("inventory")
                )
                if args.command == "verify"
                else validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary_structure(
                    evidence, *common
                )
            )
            sys.stdout.write(
                encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
                    result
                )
            )
        return 0
    except (
        NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError,
        NativeAssertionHelperStaticBoundaryError,
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
