#!/usr/bin/env python3
"""Build, verify, or replay the exact-build enemy candidate-score boundary."""

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
    "windows_build_13725832_31fe35265598_enemy_candidate_score_boundary.json"
)

from src.observatory.enemy_candidate_score_boundary import (  # noqa: E402
    EnemyCandidateScoreBoundaryError,
    build_enemy_candidate_score_boundary_map,
    encode_enemy_candidate_score_boundary_map,
    replay_enemy_candidate_target_score,
    replay_enemy_positioning_clamp,
    replay_enemy_target_score_wrapper,
    validate_enemy_candidate_score_boundary_map,
    validate_enemy_candidate_score_boundary_map_binding,
)


def _reject_constant(value: str) -> None:
    raise EnemyCandidateScoreBoundaryError(f"invalid JSON constant: {value}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise EnemyCandidateScoreBoundaryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise EnemyCandidateScoreBoundaryError(
            f"{label} is not a regular non-symlink file"
        )
    if path.stat().st_size > 16 * 1024 * 1024:
        raise EnemyCandidateScoreBoundaryError(f"{label} exceeds size limit")
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=_reject_duplicates,
    )
    if not isinstance(value, dict):
        raise EnemyCandidateScoreBoundaryError(f"{label} must contain an object")
    return value


def _write_create_only(path: Path, encoded: str) -> None:
    if path.exists() or path.is_symlink():
        raise EnemyCandidateScoreBoundaryError(
            "output already exists; publication is create-only"
        )
    parent = path.parent.resolve()
    if (
        parent != NATIVE_ROOT
        or path.parent.is_symlink()
        or not parent.is_dir()
        or not path.name.endswith(".json")
    ):
        raise EnemyCandidateScoreBoundaryError(
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

    positioning = subparsers.add_parser("replay-positioning")
    positioning.add_argument("--boundary-map", type=Path, default=DEFAULT_BOUNDARY_MAP)
    positioning.add_argument("--payload", required=True, type=Path)

    target = subparsers.add_parser("replay-target-score")
    target.add_argument("--boundary-map", type=Path, default=DEFAULT_BOUNDARY_MAP)
    target.add_argument("--payload", required=True, type=Path)
    target.add_argument(
        "--wrapper-only",
        action="store_true",
        help="Skip the candidate loop's selected-weapon normalization.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            value = build_enemy_candidate_score_boundary_map(args.executable)
            encoded = encode_enemy_candidate_score_boundary_map(value)
            if args.output is None:
                sys.stdout.write(encoded)
            else:
                _write_create_only(args.output, encoded)
        elif args.command == "verify":
            result = validate_enemy_candidate_score_boundary_map(
                args.executable,
                _read_json(args.boundary_map, "candidate score map"),
            )
            sys.stdout.write(encode_enemy_candidate_score_boundary_map(result))
        elif args.command == "replay-positioning":
            validate_enemy_candidate_score_boundary_map_binding(
                _read_json(args.boundary_map, "candidate score map")
            )
            payload = _read_json(args.payload, "positioning payload")
            expected_fields = {
                "raw_score",
                "injured",
                "moved",
                "current_health",
                "mode",
            }
            if set(payload) != expected_fields:
                raise EnemyCandidateScoreBoundaryError(
                    "positioning payload fields differ from the exact schema"
                )
            result = replay_enemy_positioning_clamp(
                payload["raw_score"],
                injured=payload["injured"],
                moved=payload["moved"],
                current_health=payload["current_health"],
                mode=payload["mode"],
            )
            sys.stdout.write(encode_enemy_candidate_score_boundary_map(result))
        else:
            validate_enemy_candidate_score_boundary_map_binding(
                _read_json(args.boundary_map, "candidate score map")
            )
            payload = _read_json(args.payload, "target score payload")
            expected_fields = {
                "weapon_index",
                "weapon_count",
                "callback_score",
                "target",
                "target_history",
                "priority_target",
            }
            if set(payload) != expected_fields:
                raise EnemyCandidateScoreBoundaryError(
                    "target score payload fields differ from the exact schema"
                )
            replay = (
                replay_enemy_target_score_wrapper
                if args.wrapper_only
                else replay_enemy_candidate_target_score
            )
            result = replay(**payload)
            sys.stdout.write(encode_enemy_candidate_score_boundary_map(result))
        return 0
    except (
        EnemyCandidateScoreBoundaryError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
