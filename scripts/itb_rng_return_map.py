#!/usr/bin/env python3
"""Build or verify exact-build native RNG return-address IDs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))
_NATIVE_ROOT = (_REPO_ROOT / "data" / "observatory" / "native").resolve()

from src.observatory.rng_return_map import (  # noqa: E402
    RNGReturnMapError,
    build_rng_return_map,
    encode_rng_return_map,
    validate_rng_return_map,
)


MAX_JSON_BYTES = 16 * 1024 * 1024


def _reject_constant(value: str) -> None:
    raise RNGReturnMapError(f"invalid JSON constant: {value}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise RNGReturnMapError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise RNGReturnMapError(f"{label} is not a regular non-symlink file")
    before = path.stat()
    if before.st_size > MAX_JSON_BYTES:
        raise RNGReturnMapError(f"{label} exceeds the JSON size limit")
    text = path.read_text(encoding="utf-8")
    after = path.stat()
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise RNGReturnMapError(f"{label} changed while being read")
    value = json.loads(
        text,
        parse_constant=_reject_constant,
        object_pairs_hook=_reject_duplicates,
    )
    if not isinstance(value, dict):
        raise RNGReturnMapError(f"{label} must contain a JSON object")
    return value


def _write_create_only(path: Path, encoded: str) -> None:
    if path.exists() or path.is_symlink():
        raise RNGReturnMapError("output already exists; publication is create-only")
    parent = path.parent.resolve()
    if (
        parent != _NATIVE_ROOT
        or path.parent.is_symlink()
        or not parent.is_dir()
        or not path.name.endswith(".json")
    ):
        raise RNGReturnMapError(
            "file output is restricted to data/observatory/native JSON artifacts; "
            "use stdout elsewhere"
        )
    target = parent / path.name
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(target, flags, 0o444)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = -1
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify"):
        child = subparsers.add_parser(command)
        child.add_argument("--executable", required=True, type=Path)
        child.add_argument("--inventory", required=True, type=Path)
        child.add_argument("--boundaries", required=True, type=Path)
        if command == "build":
            child.add_argument("--output", type=Path)
        else:
            child.add_argument("--catalog", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inventory = _read_json(args.inventory, "inventory")
        boundaries = _read_json(args.boundaries, "boundary map")
        if args.command == "build":
            result = build_rng_return_map(
                args.executable,
                boundaries,
                inventory=inventory,
            )
            encoded = encode_rng_return_map(result)
            if args.output is None:
                sys.stdout.write(encoded)
            else:
                _write_create_only(args.output, encoded)
        else:
            catalog = _read_json(args.catalog, "RNG return catalog")
            result = validate_rng_return_map(
                args.executable,
                catalog,
                boundaries,
                inventory=inventory,
            )
            sys.stdout.write(encode_rng_return_map(result))
        return 0
    except (
        RNGReturnMapError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
