#!/usr/bin/env python3
"""Build or verify an exact-build, non-executing ITB map-data census."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT_ROOT = _REPO_ROOT / "data" / "observatory" / "maps"
_MAX_JSON_BYTES = 512 * 1024 * 1024
sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.map_census import (  # noqa: E402
    ANALYSIS_KIND,
    MapCensusError,
    build_map_census,
    encode_map_census,
    validate_map_census,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="census one sealed map corpus")
    build.add_argument("--install-dir", required=True, type=Path)
    build.add_argument("--inventory", required=True, type=Path)
    build.add_argument("--lua-census", required=True, type=Path)
    build.add_argument("--callback-index", required=True, type=Path)
    build.add_argument("--rustc", type=Path, default=Path("rustc"))
    build.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify", help="verify one committed census")
    verify.add_argument("--install-dir", required=True, type=Path)
    verify.add_argument("--inventory", required=True, type=Path)
    verify.add_argument("--lua-census", required=True, type=Path)
    verify.add_argument("--callback-index", required=True, type=Path)
    verify.add_argument("--rustc", type=Path, default=Path("rustc"))
    verify.add_argument("--evidence", required=True, type=Path)
    return parser


def _reject_json_constant(value: str) -> None:
    raise MapCensusError(f"invalid JSON constant: {value}")


def _read_json_object(path: Path, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise MapCensusError(f"{label} is not a regular non-symlink file")
    before = path.stat()
    if before.st_size > _MAX_JSON_BYTES:
        raise MapCensusError(f"{label} exceeds the JSON size limit")
    payload = path.read_bytes()
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(payload) != before.st_size
    ):
        raise MapCensusError(f"{label} changed while being read")
    value = json.loads(
        payload.decode("utf-8"),
        parse_constant=_reject_json_constant,
    )
    if not isinstance(value, dict):
        raise MapCensusError(f"{label} must contain a JSON object")
    return value


def _write_evidence_atomically(output: Path, rendered: str) -> None:
    output_root = _OUTPUT_ROOT.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    if output.parent.resolve() != output_root:
        raise MapCensusError(
            "output must be a direct child of data/observatory/maps"
        )
    destination = output_root / output.name
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise MapCensusError("refusing to replace non-regular output")
        try:
            existing = _read_json_object(destination, "existing output")
        except (
            MapCensusError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise MapCensusError(
                "refusing to replace an existing non-map-census artifact"
            ) from exc
        if existing.get("analysis_kind") != ANALYSIS_KIND:
            raise MapCensusError(
                "refusing to replace an existing non-map-census artifact"
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
        lua_census = _read_json_object(args.lua_census, "Lua census")
        callback_index = _read_json_object(args.callback_index, "callback index")
        if args.command == "build":
            result = build_map_census(
                args.install_dir,
                inventory=inventory,
                lua_census=lua_census,
                callback_index=callback_index,
                rustc=args.rustc,
            )
            rendered = encode_map_census(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_evidence_atomically(args.output, rendered)
        else:
            evidence = _read_json_object(args.evidence, "evidence")
            result = validate_map_census(
                args.install_dir,
                evidence,
                inventory=inventory,
                lua_census=lua_census,
                callback_index=callback_index,
                rustc=args.rustc,
            )
            sys.stdout.write(encode_map_census(result))
        return 0
    except (
        MapCensusError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
