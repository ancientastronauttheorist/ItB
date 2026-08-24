#!/usr/bin/env python3
"""Build or verify the exact-build specialized-enemy death boundary map."""

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

from src.observatory.specialized_enemy_death_boundary import (  # noqa: E402
    SpecializedEnemyDeathBoundaryError,
    build_specialized_enemy_death_boundary_map,
    encode_specialized_enemy_death_boundary_map,
    validate_specialized_enemy_death_boundary_map,
)


def _reject_constant(value: str) -> None:
    raise SpecializedEnemyDeathBoundaryError(f"invalid JSON constant: {value}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SpecializedEnemyDeathBoundaryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise SpecializedEnemyDeathBoundaryError(
            "specialized-death map is not a regular non-symlink file"
        )
    if path.stat().st_size > 16 * 1024 * 1024:
        raise SpecializedEnemyDeathBoundaryError(
            "specialized-death map exceeds size limit"
        )
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=_reject_duplicates,
    )
    if not isinstance(value, dict):
        raise SpecializedEnemyDeathBoundaryError(
            "specialized-death map must contain an object"
        )
    return value


def _write_create_only(path: Path, encoded: str) -> None:
    if path.exists() or path.is_symlink():
        raise SpecializedEnemyDeathBoundaryError(
            "output already exists; publication is create-only"
        )
    parent = path.parent.resolve()
    if (
        parent != NATIVE_ROOT
        or path.parent.is_symlink()
        or not parent.is_dir()
        or not path.name.endswith(".json")
    ):
        raise SpecializedEnemyDeathBoundaryError(
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
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify"):
        child = subparsers.add_parser(command)
        child.add_argument("--executable", required=True, type=Path)
        child.add_argument("--content-root", required=True, type=Path)
        if command == "build":
            child.add_argument("--output", type=Path)
        else:
            child.add_argument("--boundary-map", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            value = build_specialized_enemy_death_boundary_map(
                args.executable,
                args.content_root,
            )
            encoded = encode_specialized_enemy_death_boundary_map(value)
            if args.output is None:
                sys.stdout.write(encoded)
            else:
                _write_create_only(args.output, encoded)
        else:
            result = validate_specialized_enemy_death_boundary_map(
                args.executable,
                args.content_root,
                _read_json(args.boundary_map),
            )
            sys.stdout.write(encode_specialized_enemy_death_boundary_map(result))
        return 0
    except (
        SpecializedEnemyDeathBoundaryError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
