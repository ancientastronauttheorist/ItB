#!/usr/bin/env python3
"""Build, verify, or replay the exact-build enemy record selector boundary."""

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
    "windows_build_13725832_31fe35265598_enemy_record_selector_boundary.json"
)

from src.observatory.enemy_record_selector_boundary import (  # noqa: E402
    EnemyRecordSelectorBoundaryError,
    build_enemy_record_selector_boundary_map,
    encode_enemy_record_selector_boundary_map,
    replay_enemy_record_selector,
    replay_enemy_target_tie,
    validate_enemy_record_selector_boundary_map,
    validate_enemy_record_selector_boundary_map_binding,
)


def _reject_constant(value: str) -> None:
    raise EnemyRecordSelectorBoundaryError(f"invalid JSON constant: {value}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise EnemyRecordSelectorBoundaryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise EnemyRecordSelectorBoundaryError(
            f"{label} is not a regular non-symlink file"
        )
    if path.stat().st_size > 16 * 1024 * 1024:
        raise EnemyRecordSelectorBoundaryError(f"{label} exceeds size limit")
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=_reject_duplicates,
    )
    if not isinstance(value, dict):
        raise EnemyRecordSelectorBoundaryError(f"{label} must contain an object")
    return value


def _write_create_only(path: Path, encoded: str) -> None:
    if path.exists() or path.is_symlink():
        raise EnemyRecordSelectorBoundaryError(
            "output already exists; publication is create-only"
        )
    parent = path.parent.resolve()
    if (
        parent != NATIVE_ROOT
        or path.parent.is_symlink()
        or not parent.is_dir()
        or not path.name.endswith(".json")
    ):
        raise EnemyRecordSelectorBoundaryError(
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
    build = subparsers.add_parser("build")
    build.add_argument("--executable", required=True, type=Path)
    build.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--executable", required=True, type=Path)
    verify.add_argument("--boundary-map", required=True, type=Path)

    selector = subparsers.add_parser("replay-selector")
    selector.add_argument("--boundary-map", type=Path, default=DEFAULT_BOUNDARY_MAP)
    selector.add_argument("--records", required=True, type=Path)
    selector.add_argument("--rng-state", required=True, type=_rng_state)
    selector.add_argument("--board-width", type=int, default=8)
    selector.add_argument("--board-height", type=int, default=8)

    target = subparsers.add_parser("replay-target-tie")
    target.add_argument("--boundary-map", type=Path, default=DEFAULT_BOUNDARY_MAP)
    target.add_argument("--targets", required=True, type=Path)
    target.add_argument("--destination-x", required=True, type=int)
    target.add_argument("--destination-y", required=True, type=int)
    target.add_argument("--positioning-score", required=True, type=int)
    target.add_argument("--rng-state", required=True, type=_rng_state)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            value = build_enemy_record_selector_boundary_map(args.executable)
            encoded = encode_enemy_record_selector_boundary_map(value)
            if args.output is None:
                sys.stdout.write(encoded)
            else:
                _write_create_only(args.output, encoded)
        elif args.command == "verify":
            result = validate_enemy_record_selector_boundary_map(
                args.executable,
                _read_json(args.boundary_map, "enemy selector map"),
            )
            sys.stdout.write(encode_enemy_record_selector_boundary_map(result))
        elif args.command == "replay-selector":
            validate_enemy_record_selector_boundary_map_binding(
                _read_json(args.boundary_map, "enemy selector map")
            )
            payload = _read_json(args.records, "records payload")
            if set(payload) != {"records"}:
                raise EnemyRecordSelectorBoundaryError(
                    "records payload must contain exactly the records field"
                )
            result = replay_enemy_record_selector(
                payload["records"],
                args.rng_state,
                board_width=args.board_width,
                board_height=args.board_height,
            )
            sys.stdout.write(encode_enemy_record_selector_boundary_map(result))
        else:
            validate_enemy_record_selector_boundary_map_binding(
                _read_json(args.boundary_map, "enemy selector map")
            )
            payload = _read_json(args.targets, "targets payload")
            if set(payload) != {"targets"}:
                raise EnemyRecordSelectorBoundaryError(
                    "targets payload must contain exactly the targets field"
                )
            result = replay_enemy_target_tie(
                args.destination_x,
                args.destination_y,
                args.positioning_score,
                payload["targets"],
                args.rng_state,
            )
            sys.stdout.write(encode_enemy_record_selector_boundary_map(result))
        return 0
    except (
        EnemyRecordSelectorBoundaryError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
