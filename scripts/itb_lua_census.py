#!/usr/bin/env python3
"""Build or verify an exact-build compiled Lua 5.1 census."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT_ROOT = _REPO_ROOT / "data" / "observatory" / "lua"
_MAX_JSON_BYTES = 512 * 1024 * 1024
sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.lua_census import (  # noqa: E402
    ANALYSIS_KIND,
    LuaCensusError,
    build_lua_census,
    encode_lua_census,
    validate_lua_census,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="census one sealed installation")
    build.add_argument("--install-dir", required=True, type=Path)
    build.add_argument("--inventory", required=True, type=Path)
    build.add_argument("--callback-index", required=True, type=Path)
    build.add_argument("--rustc", type=Path, default=Path("rustc"))
    build.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify", help="verify one committed census")
    verify.add_argument("--install-dir", required=True, type=Path)
    verify.add_argument("--inventory", required=True, type=Path)
    verify.add_argument("--callback-index", required=True, type=Path)
    verify.add_argument("--rustc", type=Path, default=Path("rustc"))
    verify.add_argument("--evidence", required=True, type=Path)
    return parser


def _reject_json_constant(value: str) -> None:
    raise LuaCensusError(f"invalid JSON constant: {value}")


def _read_json_object(path: Path, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise LuaCensusError(f"{label} is not a regular non-symlink file")
    before = path.stat()
    if before.st_size > _MAX_JSON_BYTES:
        raise LuaCensusError(f"{label} exceeds the JSON size limit")
    payload = path.read_bytes()
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(payload) != before.st_size
    ):
        raise LuaCensusError(f"{label} changed while being read")
    value = json.loads(
        payload.decode("utf-8"),
        parse_constant=_reject_json_constant,
    )
    if not isinstance(value, dict):
        raise LuaCensusError(f"{label} must contain a JSON object")
    return value


def _write_evidence_atomically(output: Path, rendered: str) -> None:
    output_root = _OUTPUT_ROOT.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    if output.parent.resolve() != output_root:
        raise LuaCensusError(
            "output must be a direct child of data/observatory/lua"
        )
    destination = output_root / output.name
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise LuaCensusError("refusing to replace non-regular output")
        try:
            existing = _read_json_object(destination, "existing output")
        except (
            LuaCensusError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise LuaCensusError(
                "refusing to replace an existing non-Lua-census artifact"
            ) from exc
        if existing.get("analysis_kind") != ANALYSIS_KIND:
            raise LuaCensusError(
                "refusing to replace an existing non-Lua-census artifact"
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
        os.replace(temporary_name, destination)
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
        callback_index = _read_json_object(args.callback_index, "callback index")
        if args.command == "build":
            result = build_lua_census(
                args.install_dir,
                inventory=inventory,
                callback_index=callback_index,
                rustc=args.rustc,
            )
            rendered = encode_lua_census(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_evidence_atomically(args.output, rendered)
        else:
            evidence = _read_json_object(args.evidence, "evidence")
            result = validate_lua_census(
                args.install_dir,
                evidence,
                inventory=inventory,
                callback_index=callback_index,
                rustc=args.rustc,
            )
            sys.stdout.write(encode_lua_census(result))
        return 0
    except (
        LuaCensusError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
