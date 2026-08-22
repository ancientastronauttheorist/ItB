#!/usr/bin/env python3
"""Build or verify the exact-build native path occupancy-lifecycle map."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
NATIVE_ROOT = (ROOT / "data" / "observatory" / "native").resolve()

from src.observatory.path_occupancy_lifecycle import (  # noqa: E402
    PathOccupancyLifecycleError,
    build_path_occupancy_lifecycle_map,
    encode_path_occupancy_lifecycle_map,
    validate_path_occupancy_lifecycle_map,
)


def _reject_constant(value: str) -> None:
    raise PathOccupancyLifecycleError(f"invalid JSON constant: {value}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise PathOccupancyLifecycleError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise PathOccupancyLifecycleError(
            "path occupancy map is not a regular non-symlink file"
        )
    if path.stat().st_size > 16 * 1024 * 1024:
        raise PathOccupancyLifecycleError(
            "path occupancy map exceeds the JSON size limit"
        )
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=_reject_duplicates,
    )
    if not isinstance(value, dict):
        raise PathOccupancyLifecycleError(
            "path occupancy map must contain a JSON object"
        )
    return value


def _write_create_only(path: Path, encoded: str) -> None:
    if path.exists() or path.is_symlink():
        raise PathOccupancyLifecycleError(
            "output already exists; publication is create-only"
        )
    parent = path.parent.resolve()
    if (
        parent != NATIVE_ROOT
        or path.parent.is_symlink()
        or not parent.is_dir()
        or not path.name.endswith(".json")
    ):
        raise PathOccupancyLifecycleError(
            "file output is restricted to data/observatory/native JSON artifacts"
        )
    descriptor = os.open(
        parent / path.name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o444,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = -1
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--executable", required=True, type=Path)
    build.add_argument("--output", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--executable", required=True, type=Path)
    verify.add_argument("--path-occupancy-map", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            result = build_path_occupancy_lifecycle_map(args.executable)
            encoded = encode_path_occupancy_lifecycle_map(result)
            if args.output is None:
                sys.stdout.write(encoded)
            else:
                _write_create_only(args.output, encoded)
        else:
            result = validate_path_occupancy_lifecycle_map(
                args.executable,
                _read_json(args.path_occupancy_map),
            )
            sys.stdout.write(encode_path_occupancy_lifecycle_map(result))
        return 0
    except (
        PathOccupancyLifecycleError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
