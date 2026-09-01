#!/usr/bin/env python3
"""Build or verify exact native Lua ``class`` return-helper evidence."""

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
sys.path.insert(0, str(_REPO_ROOT))

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
    ANALYSIS_KIND,
    SCHEMA_VERSION,
    NativeLuaClassReturnHelperChainError,
    _canonical_bytes,
    build_native_lua_class_return_helper_chain,
    encode_native_lua_class_return_helper_chain,
    validate_native_lua_class_return_helper_chain,
    validate_native_lua_class_return_helper_chain_structure,
)
from src.observatory.native_lua_class_factory_chain import (  # noqa: E402
    NativeLuaClassFactoryChainError,
)
from src.observatory.native_lua_cclosure_setfield_publications import (  # noqa: E402
    NativeLuaCClosurePublicationError,
)
from src.observatory.native_lua_direct_calls import NativeLuaDirectCallError  # noqa: E402
from src.observatory.native_lua_property_factory_chain import (  # noqa: E402
    NativeLuaPropertyFactoryChainError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "verify-structure"):
        item = subparsers.add_parser(command)
        for name in ("class-factory", "direct-calls", "program-facts"):
            item.add_argument("--" + name, required=True, type=Path)
        if command != "verify-structure":
            item.add_argument("--executable", required=True, type=Path)
            item.add_argument("--inventory", required=True, type=Path)
        if command == "build":
            item.add_argument("--output", type=Path)
        else:
            item.add_argument("--evidence", required=True, type=Path)
    return parser


def _class_factory_identity(value: dict[str, Any]) -> str:
    """Return the sealed factory prerequisite digest without accepting ambiguity."""
    candidates: list[Any] = [
        value.get("class_factory_chain"),
        value.get("class_factory"),
    ]
    prerequisites = value.get("prerequisites")
    if isinstance(prerequisites, dict):
        candidates.extend(
            prerequisites.get(key)
            for key in ("class_factory_chain", "class_factory")
        )
    hashes = [
        item.get("canonical_sha256")
        for item in candidates
        if isinstance(item, dict) and type(item.get("canonical_sha256")) is str
    ]
    if len(set(hashes)) != 1:
        raise NativeLuaClassReturnHelperChainError(
            "evidence lacks an unambiguous class-factory prerequisite identity"
        )
    return hashes[0]


def _identity(value: dict[str, Any]) -> bytes:
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != SCHEMA_VERSION
        or value.get("analysis_kind") != ANALYSIS_KIND
    ):
        raise NativeLuaClassReturnHelperChainError(
            "evidence has another schema or analysis kind"
        )
    build_identity = value.get("build_identity")
    if not isinstance(build_identity, dict):
        raise NativeLuaClassReturnHelperChainError("evidence lacks build identity")
    return _canonical_bytes(
        {
            "schema_version": value["schema_version"],
            "analysis_kind": value["analysis_kind"],
            "build_identity": build_identity,
            "class_factory_canonical_sha256": _class_factory_identity(value),
        }
    )


def _write_immutably(output: Path, rendered: str, value: dict[str, Any]) -> None:
    """Publish a new regular file once, or byte-for-byte replay an existing one."""
    configured, resolved, before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured:
        raise NativeLuaClassReturnHelperChainError(
            "output must be a direct child of data observatory programs"
        )
    destination = resolved / output.name
    expected = rendered.encode("utf-8")
    identity = _identity(value)
    if os.path.lexists(destination):
        initial = destination.lstat()
        if (
            stat.S_ISLNK(initial.st_mode)
            or _is_reparse(initial)
            or not stat.S_ISREG(initial.st_mode)
            or destination.resolve(strict=True).parent != resolved
        ):
            raise NativeLuaClassReturnHelperChainError(
                "refusing to replace a linked, reparse, or non-regular output"
            )
        existing, payload = _read_json_document(destination, "existing output")
        final = destination.lstat()
        _recheck_output_root(configured, resolved, before)
        if (
            stat.S_ISLNK(final.st_mode)
            or _is_reparse(final)
            or not stat.S_ISREG(final.st_mode)
            or destination.resolve(strict=True).parent != resolved
            or (initial.st_dev, initial.st_ino) != (final.st_dev, final.st_ino)
        ):
            raise NativeLuaClassReturnHelperChainError(
                "existing output changed during validation"
            )
        if (
            _identity(existing) != identity
            or _canonical_bytes(existing) != _canonical_bytes(value)
            or payload != expected
        ):
            raise NativeLuaClassReturnHelperChainError(
                "refusing to overwrite differing class return-helper evidence"
            )
        return

    fd, temporary_name = tempfile.mkstemp(
        prefix="." + output.name + ".", suffix=".tmp", dir=resolved
    )
    temporary = Path(temporary_name)
    linked = False
    source_identity: tuple[int, int] | None = None
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        source = temporary.lstat()
        if (
            stat.S_ISLNK(source.st_mode)
            or _is_reparse(source)
            or not stat.S_ISREG(source.st_mode)
        ):
            raise NativeLuaClassReturnHelperChainError(
                "temporary output is not a real regular file"
            )
        source_identity = (source.st_dev, source.st_ino)
        _recheck_output_root(configured, resolved, before)
        os.link(temporary, destination)
        linked = True
        created = destination.lstat()
        if (
            stat.S_ISLNK(created.st_mode)
            or _is_reparse(created)
            or not stat.S_ISREG(created.st_mode)
            or destination.resolve(strict=True).parent != resolved
            or (created.st_dev, created.st_ino) != source_identity
        ):
            raise NativeLuaClassReturnHelperChainError(
                "created output failed the regular-file identity check"
            )
        _recheck_output_root(configured, resolved, before)
        temporary.unlink()
        final = destination.lstat()
        if (
            stat.S_ISLNK(final.st_mode)
            or _is_reparse(final)
            or not stat.S_ISREG(final.st_mode)
            or (final.st_dev, final.st_ino) != source_identity
        ):
            raise NativeLuaClassReturnHelperChainError(
                "created output changed after publication"
            )
        _recheck_output_root(configured, resolved, before)
    except Exception:
        if linked and source_identity is not None:
            try:
                created = destination.lstat()
                if (created.st_dev, created.st_ino) == source_identity:
                    destination.unlink()
            except FileNotFoundError:
                pass
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        get = lambda name: _read_json_object(getattr(args, name.replace("-", "_")), name)
        class_factory, direct_calls, program_facts = (
            get(name) for name in ("class-factory", "direct-calls", "program-facts")
        )
        common = (class_factory, direct_calls, program_facts)
        if args.command == "build":
            inventory = get("inventory")
            result = build_native_lua_class_return_helper_chain(
                args.executable, *common, inventory=inventory
            )
            rendered = encode_native_lua_class_return_helper_chain(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_immutably(args.output, rendered, result)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode_native_lua_class_return_helper_chain(evidence).encode("utf-8"):
                raise NativeLuaClassReturnHelperChainError(
                    "evidence is not deterministically encoded"
                )
            if args.command == "verify":
                inventory = get("inventory")
                result = validate_native_lua_class_return_helper_chain(
                    args.executable, evidence, *common, inventory=inventory
                )
            else:
                result = validate_native_lua_class_return_helper_chain_structure(
                    evidence, *common
                )
            sys.stdout.write(encode_native_lua_class_return_helper_chain(result))
        return 0
    except (
        NativeLuaClassReturnHelperChainError,
        NativeLuaClassFactoryChainError,
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
