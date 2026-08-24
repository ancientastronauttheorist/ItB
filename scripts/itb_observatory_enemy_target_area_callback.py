#!/usr/bin/env python3
"""Build, verify, or replay the exact native target-area callback wrapper."""

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
DEFAULT_BOUNDARY_MAP = NATIVE_ROOT / (
    "windows_build_13725832_31fe35265598_"
    "enemy_target_area_callback_boundary.json"
)

from src.observatory.enemy_target_area_callback_boundary import (  # noqa: E402
    EnemyTargetAreaCallbackBoundaryError,
    build_enemy_target_area_callback_boundary_map,
    encode_enemy_target_area_callback_boundary_map,
    replay_enemy_target_area_callback,
    validate_enemy_target_area_callback_boundary_map,
    validate_enemy_target_area_callback_boundary_map_binding,
)


def _reject_constant(value: str) -> None:
    raise EnemyTargetAreaCallbackBoundaryError(f"invalid JSON constant: {value}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise EnemyTargetAreaCallbackBoundaryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise EnemyTargetAreaCallbackBoundaryError(
            f"{label} is not a regular non-symlink file"
        )
    if path.stat().st_size > 16 * 1024 * 1024:
        raise EnemyTargetAreaCallbackBoundaryError(f"{label} exceeds size limit")
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=_reject_duplicates,
    )
    if not isinstance(value, dict):
        raise EnemyTargetAreaCallbackBoundaryError(f"{label} must contain an object")
    return value


def _write_create_only(path: Path, encoded: str) -> None:
    if path.exists() or path.is_symlink():
        raise EnemyTargetAreaCallbackBoundaryError(
            "output already exists; publication is create-only"
        )
    parent = path.parent.resolve()
    if (
        parent != NATIVE_ROOT
        or path.parent.is_symlink()
        or not parent.is_dir()
        or not path.name.endswith(".json")
    ):
        raise EnemyTargetAreaCallbackBoundaryError(
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

    build = subparsers.add_parser("build")
    build.add_argument("--executable", required=True, type=Path)
    build.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--executable", required=True, type=Path)
    verify.add_argument("--boundary-map", required=True, type=Path)

    replay = subparsers.add_parser("replay")
    replay.add_argument("--boundary-map", type=Path, default=DEFAULT_BOUNDARY_MAP)
    replay.add_argument("--payload", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            value = build_enemy_target_area_callback_boundary_map(args.executable)
            encoded = encode_enemy_target_area_callback_boundary_map(value)
            if args.output is None:
                sys.stdout.write(encoded)
            else:
                _write_create_only(args.output, encoded)
        elif args.command == "verify":
            result = validate_enemy_target_area_callback_boundary_map(
                args.executable,
                _read_json(args.boundary_map, "target-area callback boundary map"),
            )
            sys.stdout.write(encode_enemy_target_area_callback_boundary_map(result))
        else:
            validate_enemy_target_area_callback_boundary_map_binding(
                _read_json(args.boundary_map, "target-area callback boundary map")
            )
            payload = _read_json(args.payload, "target-area callback payload")
            expected_fields = {
                "board_width",
                "board_height",
                "origin",
                "cached_points",
                "two_click",
                "second_target",
                "get_target_area_points",
                "get_second_target_area_points",
            }
            if set(payload) != expected_fields:
                raise EnemyTargetAreaCallbackBoundaryError(
                    "target-area callback payload fields differ from the exact schema"
                )
            result = replay_enemy_target_area_callback(**payload)
            sys.stdout.write(encode_enemy_target_area_callback_boundary_map(result))
        return 0
    except (
        EnemyTargetAreaCallbackBoundaryError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
