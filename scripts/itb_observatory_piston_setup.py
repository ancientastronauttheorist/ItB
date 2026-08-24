#!/usr/bin/env python3
"""Build, verify, or replay the exact-build Mission_Piston setup boundary."""

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
    "windows_build_13725832_31fe35265598_piston_setup_boundary.json"
)

from src.observatory.piston_setup_boundary import (  # noqa: E402
    MAP_SPECS,
    PistonSetupBoundaryError,
    build_piston_setup_boundary_map,
    encode_piston_setup_boundary_map,
    replay_piston_start_mission,
    validate_piston_setup_boundary_map,
    validate_piston_setup_boundary_map_binding,
)


def _reject_constant(value: str) -> None:
    raise PistonSetupBoundaryError(f"invalid JSON constant: {value}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise PistonSetupBoundaryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise PistonSetupBoundaryError(
            "Piston setup boundary map is not a regular non-symlink file"
        )
    if path.stat().st_size > 16 * 1024 * 1024:
        raise PistonSetupBoundaryError("Piston setup boundary map exceeds size limit")
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=_reject_duplicates,
    )
    if not isinstance(value, dict):
        raise PistonSetupBoundaryError(
            "Piston setup boundary map must contain an object"
        )
    return value


def _write_create_only(path: Path, encoded: str) -> None:
    if path.exists() or path.is_symlink():
        raise PistonSetupBoundaryError(
            "output already exists; publication is create-only"
        )
    parent = path.parent.resolve()
    if (
        parent != NATIVE_ROOT
        or path.parent.is_symlink()
        or not parent.is_dir()
        or not path.name.endswith(".json")
    ):
        raise PistonSetupBoundaryError(
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


def _rng_state(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "RNG state must be an integer such as 0x12345678"
        ) from exc
    if not 0 <= parsed <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("RNG state must fit in 32 unsigned bits")
    return parsed


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

    replay = subparsers.add_parser("replay")
    replay.add_argument(
        "--boundary-map",
        type=Path,
        default=DEFAULT_BOUNDARY_MAP,
        help="immutable setup artifact to bind before replay",
    )
    replay.add_argument(
        "--map-name",
        required=True,
        choices=[spec["name"] for spec in MAP_SPECS],
    )
    replay.add_argument("--rng-state", required=True, type=_rng_state)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            value = build_piston_setup_boundary_map(
                args.executable,
                args.content_root,
            )
            encoded = encode_piston_setup_boundary_map(value)
            if args.output is None:
                sys.stdout.write(encoded)
            else:
                _write_create_only(args.output, encoded)
        elif args.command == "verify":
            result = validate_piston_setup_boundary_map(
                args.executable,
                args.content_root,
                _read_json(args.boundary_map),
            )
            sys.stdout.write(encode_piston_setup_boundary_map(result))
        else:
            validate_piston_setup_boundary_map_binding(
                _read_json(args.boundary_map)
            )
            result = replay_piston_start_mission(args.map_name, args.rng_state)
            sys.stdout.write(encode_piston_setup_boundary_map(result))
        return 0
    except (
        PistonSetupBoundaryError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
