#!/usr/bin/env python3
"""Build or verify the relationship-defined query local-helper callee boundary."""
from __future__ import annotations
import argparse, json, os, stat, sys, tempfile
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(_ROOT))
from scripts.itb_native_assertion_helper_static_boundary import NativeAssertionHelperStaticBoundaryError, _locked_output, _read_locked_json_document, _regular_child
from scripts.itb_native_lua_direct_calls import _is_reparse, _read_json_document, _read_json_object
from scripts.itb_native_lua_property_factory_chain import _prepare_output_root, _recheck_output_root
from src.observatory.native_query_local_helper_callee_static_boundary import (
    ANALYSIS_KIND, SCHEMA_VERSION, NativeQueryLocalHelperCalleeStaticBoundaryError, _canonical_bytes,
    build_native_query_local_helper_callee_static_boundary, encode_native_query_local_helper_callee_static_boundary,
    validate_native_query_local_helper_callee_static_boundary,
    validate_native_query_local_helper_callee_static_boundary_structure,
)
from src.observatory.native_lua_cclosure_setfield_publications import NativeLuaCClosurePublicationError
from src.observatory.native_lua_direct_calls import NativeLuaDirectCallError
from src.observatory.native_lua_property_factory_chain import NativeLuaPropertyFactoryChainError

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "verify-structure"):
        item = commands.add_parser(command)
        for name in ("local-helper-static-boundary", "direct-calls", "program-facts"): item.add_argument("--" + name, required=True, type=Path)
        if command != "verify-structure": item.add_argument("--executable", required=True, type=Path); item.add_argument("--inventory", required=True, type=Path)
        if command == "build": item.add_argument("--output", type=Path)
        else: item.add_argument("--evidence", required=True, type=Path)
    return parser

def _identity(value: dict[str, Any]) -> bytes:
    if type(value.get("schema_version")) is not int or value.get("schema_version") != SCHEMA_VERSION or value.get("analysis_kind") != ANALYSIS_KIND or not isinstance(value.get("build_identity"), dict): raise NativeQueryLocalHelperCalleeStaticBoundaryError("evidence has another schema, kind, or lacks build identity")
    prerequisite = value.get("local_helper_static_boundary")
    if not isinstance(prerequisite, dict) or type(prerequisite.get("canonical_sha256")) is not str: raise NativeQueryLocalHelperCalleeStaticBoundaryError("evidence lacks local-helper prerequisite identity")
    return _canonical_bytes({"schema_version": value["schema_version"], "analysis_kind": value["analysis_kind"], "build_identity": value["build_identity"], "local_helper_canonical_sha256": prerequisite["canonical_sha256"]})

def _same(value, payload, identity, expected): return _identity(value) == identity and _canonical_bytes(value) == _canonical_bytes(json.loads(expected)) and payload == expected

def _write_immutably_impl(output: Path, rendered: str, value: dict[str, Any]):
    configured, resolved, before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured: raise NativeQueryLocalHelperCalleeStaticBoundaryError("output must be a direct child of data observatory programs")
    destination, expected, identity = resolved / output.name, rendered.encode("utf-8"), _identity(value)
    if os.path.lexists(destination):
        initial = _regular_child(destination, resolved); existing, payload = _read_json_document(destination, "existing output"); final = _regular_child(destination, resolved, (initial.st_dev, initial.st_ino)); _recheck_output_root(configured, resolved, before)
        if not _same(existing, payload, identity, expected): raise NativeQueryLocalHelperCalleeStaticBoundaryError("refusing to overwrite differing local-helper callee evidence")
        with _locked_output(destination, resolved, (final.st_dev, final.st_ino)) as descriptor:
            _recheck_output_root(configured, resolved, before); final_value, final_payload = _read_locked_json_document(descriptor, "final existing output")
            if not _same(final_value, final_payload, identity, expected): raise NativeQueryLocalHelperCalleeStaticBoundaryError("existing output changed during final content validation")
            return
    fd, name = tempfile.mkstemp(prefix="." + output.name + ".", suffix=".tmp", dir=resolved); temporary, linked, source_identity = Path(name), False, None
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream: stream.write(rendered); stream.flush(); os.fsync(stream.fileno())
        source = temporary.lstat()
        if stat.S_ISLNK(source.st_mode) or _is_reparse(source) or not stat.S_ISREG(source.st_mode): raise NativeQueryLocalHelperCalleeStaticBoundaryError("temporary output is not a real regular file")
        source_identity = (source.st_dev, source.st_ino); _recheck_output_root(configured, resolved, before); os.link(temporary, destination); linked = True
        _regular_child(destination, resolved, source_identity); _recheck_output_root(configured, resolved, before); temporary.unlink(); _regular_child(destination, resolved, source_identity); _recheck_output_root(configured, resolved, before)
        with _locked_output(destination, resolved, source_identity) as descriptor:
            _recheck_output_root(configured, resolved, before); final_value, final_payload = _read_locked_json_document(descriptor, "final created output")
            if not _same(final_value, final_payload, identity, expected): raise NativeQueryLocalHelperCalleeStaticBoundaryError("created output changed during final content validation")
            return
    except Exception:
        if linked and source_identity is not None:
            try:
                created = destination.lstat()
                if (created.st_dev, created.st_ino) == source_identity: destination.unlink()
            except FileNotFoundError: pass
        try: temporary.unlink()
        except FileNotFoundError: pass
        raise

def _write_immutably(output: Path, rendered: str, value: dict[str, Any]):
    try:
        _write_immutably_impl(output, rendered, value)
    except (NativeAssertionHelperStaticBoundaryError, NativeLuaPropertyFactoryChainError) as exc:
        raise NativeQueryLocalHelperCalleeStaticBoundaryError(str(exc)) from exc

def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        get = lambda name: _read_json_object(getattr(args, name.replace("-", "_")), name)
        helper, direct, facts = (get(name) for name in ("local-helper-static-boundary", "direct-calls", "program-facts")); common = (helper, direct, facts)
        if args.command == "build":
            result = build_native_query_local_helper_callee_static_boundary(args.executable, *common, inventory=get("inventory")); rendered = encode_native_query_local_helper_callee_static_boundary(result)
            if args.output is None: sys.stdout.write(rendered)
            else: _write_immutably(args.output, rendered, result)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode_native_query_local_helper_callee_static_boundary(evidence).encode("utf-8"): raise NativeQueryLocalHelperCalleeStaticBoundaryError("evidence is not deterministically encoded")
            result = validate_native_query_local_helper_callee_static_boundary(args.executable, evidence, *common, inventory=get("inventory")) if args.command == "verify" else validate_native_query_local_helper_callee_static_boundary_structure(evidence, *common)
            sys.stdout.write(encode_native_query_local_helper_callee_static_boundary(result))
        return 0
    except (NativeQueryLocalHelperCalleeStaticBoundaryError, NativeAssertionHelperStaticBoundaryError, NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaPropertyFactoryChainError, OSError, UnicodeError, json.JSONDecodeError) as exc: print(f"error: {exc}", file=sys.stderr); return 1

if __name__ == "__main__": raise SystemExit(main())
